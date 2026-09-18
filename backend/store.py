"""One versioned Secret Service item, so an import replaces the vault in one write."""

import fcntl
import json
import os
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from core import MfaError, empty_vault, validate_vault
from models import Vault


def runtime_dir() -> Path:
    path = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
    info = path.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise MfaError("unsafe_runtime")
    return path


class KeyringStore:
    def __init__(self) -> None:
        try:
            import gi

            gi.require_version("Secret", "1")
            from gi.repository import Secret

            self.secret = Secret
            self.schema = Secret.Schema.new(
                "org.omarchy.mfa",
                Secret.SchemaFlags.NONE,
                {"application": Secret.SchemaAttributeType.STRING},
            )
            self.attributes = {"application": "kuryrc.mfa"}
        except (ImportError, ValueError):
            raise MfaError("missing_libsecret") from None

    def collection(self, unlock: bool = False) -> Any:
        # PyGObject creates these binding types at runtime. Keep this dynamic seam here.
        try:
            service = self.secret.Service.get_sync(self.secret.ServiceFlags.OPEN_SESSION, None)
            collection = self.secret.Collection.for_alias_sync(
                service, "default", self.secret.CollectionFlags.NONE, None
            )
            if collection is None:
                raise MfaError("keyring_unavailable")
            if collection.get_locked():
                if not unlock:
                    raise MfaError("keyring_locked")
                _, unlocked = service.unlock_sync([collection], None)
                if not unlocked:
                    raise MfaError("keyring_locked")
            return collection
        except MfaError:
            raise
        except Exception:
            raise MfaError("keyring_unavailable") from None

    def unlock(self) -> None:
        self.collection(unlock=True)

    @contextmanager
    def transaction(self) -> Iterator[None]:
        fd = os.open(
            runtime_dir() / "kuryrc.mfa.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600
        )
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            os.close(fd)

    def load(self) -> Vault:
        self.collection()
        try:
            raw = self.secret.password_lookup_sync(self.schema, self.attributes, None)
            return empty_vault() if raw is None else validate_vault(json.loads(raw))
        except MfaError:
            raise
        except (ValueError, TypeError):
            raise MfaError("invalid_vault") from None
        except Exception:
            raise MfaError("keyring_unavailable") from None

    def save(self, vault: Vault) -> None:
        collection = self.collection()
        vault = validate_vault(vault)
        try:
            ok = self.secret.password_store_sync(
                self.schema,
                self.attributes,
                collection.get_object_path(),
                "Omarchy MFA (kuryrc.mfa)",
                json.dumps(vault, ensure_ascii=False),
                None,
            )
            if not ok:
                raise MfaError("keyring_write_failed")
        except MfaError:
            raise
        except Exception:
            raise MfaError("keyring_write_failed") from None
