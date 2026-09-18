#!/usr/bin/python3
"""Line-delimited JSON RPC for the QML view; stdout is protocol, never a log."""

import copy
import datetime
import json
import os
import secrets
import sys
import time
from pathlib import Path

from clipboard import Clipboard
from core import (
    MfaError,
    normalize_account,
    object_fields,
    parse_uri,
    public_account,
    revision,
    string_field,
    to_uri,
    validate_settings,
)
from models import (
    Account,
    AccountList,
    BackupRow,
    Copier,
    ImportResult,
    Paster,
    Preview,
    PreviewRow,
    Reply,
    Request,
    Response,
    Vault,
    VaultStore,
)
from store import KeyringStore

MAX_SOURCE_BYTES = 10 * 1024 * 1024


def read_backup(filename: str | Path) -> list[BackupRow]:
    """Read the portable, line-oriented otpauth backup format."""
    path = Path(filename).expanduser().resolve(strict=True)
    if not path.is_file():
        raise MfaError("invalid_source")
    rows: list[BackupRow] = []
    if path.stat().st_size > MAX_SOURCE_BYTES:
        raise MfaError("source_too_large")
    for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append({"row": number, "account": parse_uri(line)})
        except MfaError as error:
            rows.append({"row": number, "error": str(error)})
    if not rows:
        raise MfaError("empty_source")
    return rows


class Backend:
    def __init__(
        self,
        store: VaultStore | None = None,
        copier: Copier | None = None,
        paster: Paster | None = None,
    ) -> None:
        self.store = store if store is not None else KeyringStore()
        self.clipboard = Clipboard()
        self.copier = copier or self.clipboard.copy
        self.paster = paster or self.clipboard.paste
        self.preview: Preview | None = None

    def list_accounts(self, vault: Vault) -> AccountList:
        now = time.time()
        ordered = sorted(vault["accounts"], key=lambda a: (-a["lastUsed"], a["name"].casefold()))
        return {
            "accounts": [public_account(a, now) for a in ordered],
            "settings": vault["settings"],
            "revision": revision(vault),
            "now": now,
        }

    def dispatch(self, request: Request) -> Response:
        op = request.get("op")
        if op == "paste":
            self.paster(string_field(request.get("token")))
            return {}
        if op == "unlock":
            self.store.unlock()
        with self.store.transaction():
            vault = self.store.load()
            if op in ("list", "unlock"):
                return self.list_accounts(vault)
            if op == "preview":
                rows = read_backup(string_field(request.get("path", ""), "invalid_source"))
                existing_names = {a["name"]: a for a in vault["accounts"]}
                token = secrets.token_hex(16)
                self.preview = {"token": token, "revision": revision(vault), "rows": rows}
                visible: list[PreviewRow] = []
                for index, row in enumerate(rows):
                    a = row.get("account")
                    visible.append(
                        {
                            "index": index,
                            "row": row["row"],
                            "name": a["name"] if a else "",
                            "error": row.get("error", ""),
                            "conflict": bool(a and a["name"] in existing_names),
                        }
                    )
                return {"token": token, "rows": visible}
            if op == "cancel_preview":
                self.preview = None
                return {}
            if op == "import":
                return self.commit_import(vault, request)
            if op == "export":
                return self.export(vault, request)
            if op == "copy":
                account = self.account(vault, request.get("accountId"))
                account["lastUsed"] = time.time() * 1000
                self.store.save(vault)
                paste_token = self.copier(account, request.get("paste") is True)
                return {"pasteToken": paste_token} if paste_token else {}
            # All edits carry a revision so stale forms cannot overwrite a newer vault.
            if request.get("revision") != revision(vault):
                raise MfaError("stale_data")
            if op == "add":
                account = (
                    parse_uri(request["uri"])
                    if "uri" in request
                    else normalize_account(request.get("account"))
                )
                existing = next(
                    (a for a in vault["accounts"] if a["name"] == account["name"]), None
                )
                if existing:
                    if not request.get("overwrite"):
                        raise MfaError("name_conflict")
                    account["id"] = existing["id"]
                    vault["accounts"].remove(existing)
                account["lastUsed"] = time.time() * 1000
                vault["accounts"].append(account)
            elif op == "rename":
                account = self.account(vault, request.get("accountId"))
                updated = normalize_account(dict(account, name=request.get("name", "")))
                if any(
                    a["id"] != account["id"] and a["name"] == updated["name"]
                    for a in vault["accounts"]
                ):
                    raise MfaError("name_conflict")
                account["name"] = updated["name"]
            elif op == "delete":
                account = self.account(vault, request.get("accountId"))
                vault["accounts"].remove(account)
            elif op == "settings":
                vault["settings"] = validate_settings(request.get("settings"))
            else:
                raise MfaError("unknown_operation")
            self.store.save(vault)
            return self.list_accounts(vault)

    @staticmethod
    def account(vault: Vault, account_id: object) -> Account:
        account = next((a for a in vault["accounts"] if a["id"] == account_id), None)
        if account is None:
            raise MfaError("account_missing")
        return account

    def commit_import(self, vault: Vault, request: Request) -> Response:
        preview = self.preview
        if not preview or request.get("token") != preview["token"]:
            raise MfaError("preview_expired")
        if preview["revision"] != revision(vault):
            raise MfaError("stale_data")
        selections = request.get("selections", [])
        if not isinstance(selections, list) or not selections:
            raise MfaError("nothing_selected")
        selected: set[int] = set()
        names: set[str] = set()
        result: ImportResult = {
            "added": 0,
            "overwritten": 0,
            "invalid": sum("error" in r for r in preview["rows"]),
            "skipped": 0,
        }
        updated = copy.deepcopy(vault)
        for selection in selections:
            selection = object_fields(selection, "invalid_selection")
            index = selection.get("index")
            if type(index) is not int or index in selected or not 0 <= index < len(preview["rows"]):
                raise MfaError("invalid_selection")
            row = preview["rows"][index]
            if "account" not in row:
                raise MfaError("invalid_selection")
            account = copy.deepcopy(row["account"])
            if account["name"] in names:
                raise MfaError("duplicate_selection")
            names.add(account["name"])
            selected.add(index)
            existing = next((a for a in updated["accounts"] if a["name"] == account["name"]), None)
            if existing:
                if not selection.get("overwrite"):
                    raise MfaError("name_conflict")
                account["id"] = existing["id"]
                updated["accounts"].remove(existing)
                result["overwritten"] += 1
            else:
                result["added"] += 1
            updated["accounts"].append(account)
        result["skipped"] = len(preview["rows"]) - len(selected) - result["invalid"]
        self.store.save(updated)
        self.preview = None
        return {**self.list_accounts(updated), "result": result}

    @staticmethod
    def export(vault: Vault, request: Request) -> Response:
        if request.get("confirmed") is not True:
            raise MfaError("export_confirmation")
        if not vault["accounts"]:
            raise MfaError("empty_source")
        if "path" in request:
            directory = (
                Path(string_field(request["path"], "invalid_source"))
                .expanduser()
                .resolve(strict=True)
            )
        else:
            directory = Path.home() / "Backups" / "omarchy-mfa"
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            directory = directory.resolve(strict=True)
        if not directory.is_dir():
            raise MfaError("invalid_source")
        timestamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%S.%fZ")
        filename = directory / f"omarchy-mfa-{timestamp}.txt"
        fd = os.open(filename, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                for account in vault["accounts"]:
                    stream.write(to_uri(account) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
        except Exception:
            filename.unlink(missing_ok=True)
            raise
        return {"path": str(filename), "count": len(vault["accounts"])}


def main() -> None:
    backend = None
    for line in sys.stdin:
        request_id: int | None = None
        try:
            if len(line) > MAX_SOURCE_BYTES:
                raise MfaError("source_too_large")
            request = object_fields(json.loads(line))
            raw_id = request.get("id")
            if raw_id is not None and type(raw_id) is not int:
                raise MfaError("invalid_request")
            request_id = raw_id
            if backend is None:
                backend = Backend()
            result = backend.dispatch(request)
            reply: Reply = {"id": request_id, "ok": True, "data": result}
        except MfaError as error:
            reply = {"id": request_id, "ok": False, "error": str(error)}
        except (OSError, UnicodeError):
            reply = {"id": request_id, "ok": False, "error": "file_error"}
        except Exception:
            reply = {"id": request_id, "ok": False, "error": "internal_error"}
        print(json.dumps(reply, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
