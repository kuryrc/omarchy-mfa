"""TOTP and portable account formats. No desktop, storage, or clipboard access."""

import base64
import binascii
import hashlib
import hmac
import json
import math
import time
import uuid
from collections.abc import Mapping
from typing import Literal, cast
from urllib.parse import parse_qs, quote, unquote, urlencode, urlparse

from models import Account, Algorithm, PublicAccount, Settings, Vault


class MfaError(Exception):
    """Stable, translatable error identifier; never includes a secret or URL."""


MAX_PERIOD = 2**31 - 1


def object_fields(value: object, error: str = "invalid_request") -> Mapping[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise MfaError(error)
    return cast(Mapping[str, object], value)


def string_field(value: object, error: str = "invalid_request") -> str:
    if not isinstance(value, str):
        raise MfaError(error)
    return value


def normalize_account(value: object) -> Account:
    value = object_fields(value, "invalid_account")
    name = str(value.get("name", "")).strip()
    if not name or len(name) > 256 or any(ord(c) < 32 for c in name):
        raise MfaError("invalid_name")
    secret = value.get("secret", "")
    if not isinstance(secret, str):
        raise MfaError("invalid_secret")
    secret = "".join(c for c in secret if not c.isspace() and c != "-").upper().rstrip("=")
    if not secret or len(secret) > 4096:
        raise MfaError("invalid_secret")
    try:
        decoded = base64.b32decode(secret + "=" * (-len(secret) % 8))
        if not decoded:
            raise ValueError()
    except (binascii.Error, ValueError):
        raise MfaError("invalid_secret") from None
    algorithm = str(value.get("algorithm", "SHA1")).upper()
    if algorithm not in ("SHA1", "SHA256", "SHA512"):
        raise MfaError("invalid_algorithm")
    try:
        digits = int(str(value.get("digits", 6)))
        period = int(str(value.get("period", 30)))
    except (TypeError, ValueError):
        raise MfaError("invalid_options") from None
    if digits not in (6, 7, 8) or not 1 <= period <= MAX_PERIOD:
        raise MfaError("invalid_options")
    try:
        last_used = float(str(value.get("lastUsed", 0)))
        if not math.isfinite(last_used) or last_used < 0:
            raise ValueError()
    except (TypeError, ValueError, OverflowError):
        raise MfaError("invalid_account") from None
    return {
        "id": str(value.get("id") or uuid.uuid4()),
        "name": name,
        "secret": secret,
        "algorithm": cast(Algorithm, algorithm),
        "digits": cast(Literal[6, 7, 8], digits),
        "period": period,
        "lastUsed": last_used,
    }


def totp(account: Account, timestamp: float | None = None) -> str:
    now = time.time() if timestamp is None else timestamp
    counter = int(now // account["period"])
    key = base64.b32decode(account["secret"] + "=" * (-len(account["secret"]) % 8))
    digest = hmac.new(key, counter.to_bytes(8, "big"), account["algorithm"].lower()).digest()
    offset = digest[-1] & 15
    number = int.from_bytes(digest[offset : offset + 4], "big") & 0x7FFFFFFF
    return str(number % (10 ** account["digits"])).zfill(account["digits"])


def parse_uri(uri: object) -> Account:
    uri = string_field(uri, "invalid_uri")
    try:
        url = urlparse(uri.strip())
        if url.scheme != "otpauth" or url.netloc != "totp":
            raise MfaError("invalid_uri")
        query = parse_qs(url.query, keep_blank_values=True)
        fields: dict[str, object] = {
            key: query[key][0]
            for key in ("secret", "algorithm", "digits", "period")
            if key in query
        }
        fields["name"] = unquote(url.path.lstrip("/"))
        return normalize_account(fields)
    except (ValueError, AttributeError):
        raise MfaError("invalid_uri") from None


def to_uri(account: Account) -> str:
    query = urlencode(
        {
            "secret": account["secret"],
            "algorithm": account["algorithm"],
            "period": account["period"],
            "digits": account["digits"],
        }
    )
    return "otpauth://totp/" + quote(account["name"], safe="") + "?" + query


def public_account(account: Account, timestamp: float) -> PublicAccount:
    return {
        "id": account["id"],
        "name": account["name"],
        "algorithm": account["algorithm"],
        "digits": account["digits"],
        "period": account["period"],
        "lastUsed": account["lastUsed"],
        "code": totp(account, timestamp),
        "expiresAt": (int(timestamp // account["period"]) + 1) * account["period"],
    }


def empty_vault() -> Vault:
    return {"version": 1, "accounts": [], "settings": {"language": "auto", "defaultAction": "copy"}}


def validate_settings(value: object) -> Settings:
    fields = object_fields(value, "invalid_options")
    language, action = fields.get("language"), fields.get("defaultAction")
    if language not in ("auto", "en", "zh") or action not in ("copy", "paste"):
        raise MfaError("invalid_options")
    # Only validated fields are persisted, including when restoring older vaults.
    return {"language": language, "defaultAction": action}


def validate_vault(value: object) -> Vault:
    fields = object_fields(value, "invalid_vault")
    raw_accounts = fields.get("accounts")
    if fields.get("version") != 1 or not isinstance(raw_accounts, list):
        raise MfaError("invalid_vault")
    try:
        accounts = [normalize_account(a) for a in raw_accounts]
        if len({a["id"] for a in accounts}) != len(accounts) or len(
            {a["name"] for a in accounts}
        ) != len(accounts):
            raise MfaError("invalid_vault")
        settings = validate_settings(fields.get("settings"))
    except MfaError:
        raise MfaError("invalid_vault") from None
    return {"version": 1, "accounts": accounts, "settings": settings}


def revision(vault: Vault) -> str:
    return hashlib.sha256(
        json.dumps(vault, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
