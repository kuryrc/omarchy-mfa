"""Internal records and the storage/clipboard seams; JSON enters as untrusted objects."""

from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from typing import Literal, NotRequired, Protocol, TypedDict

Algorithm = Literal["SHA1", "SHA256", "SHA512"]
Language = Literal["auto", "en", "zh"]
Action = Literal["copy", "paste"]


class AccountMetadata(TypedDict):
    id: str
    name: str
    algorithm: Algorithm
    digits: Literal[6, 7, 8]
    period: int
    lastUsed: float


class Account(AccountMetadata):
    secret: str


class PublicAccount(AccountMetadata):
    code: str
    expiresAt: int


class Settings(TypedDict):
    language: Language
    defaultAction: Action


class Vault(TypedDict):
    version: Literal[1]
    accounts: list[Account]
    settings: Settings


class BackupRow(TypedDict):
    row: int
    account: NotRequired[Account]
    error: NotRequired[str]


class Preview(TypedDict):
    token: str
    revision: str
    rows: list[BackupRow]


class PreviewRow(TypedDict):
    index: int
    row: int
    name: str
    error: str
    conflict: bool


class ImportResult(TypedDict):
    added: int
    overwritten: int
    invalid: int
    skipped: int


class AccountList(TypedDict):
    accounts: list[PublicAccount]
    settings: Settings
    revision: str
    now: float


class VaultStore(Protocol):
    def unlock(self) -> None: ...
    def transaction(self) -> AbstractContextManager[None]: ...
    def load(self) -> Vault: ...
    def save(self, vault: Vault) -> None: ...


# Request fields must be validated before use; never cast wire data to an Account.
Request = Mapping[str, object]
Response = Mapping[str, object]
Copier = Callable[[Account, bool], str | None]
Paster = Callable[[str], None]


class SuccessReply(TypedDict):
    id: int | None
    ok: Literal[True]
    data: Response


class ErrorReply(TypedDict):
    id: int | None
    ok: Literal[False]
    error: str


Reply = SuccessReply | ErrorReply
