"""Public RFC fixtures and temporary backups only; no real keyring or accounts."""

import base64
import copy
import json
import sys
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from backend import Backend, read_backup
from core import MfaError, empty_vault, normalize_account, parse_uri, revision, to_uri, totp
from models import Account, Vault


def fixture(name: str = "Example") -> Account:
    return normalize_account({"name": name, "secret": "JBSWY3DPEHPK3PXP"})


class MemoryStore:
    def __init__(self) -> None:
        self.value = empty_vault()
        self.fail = False

    def unlock(self) -> None:
        pass

    def transaction(self) -> nullcontext[None]:
        return nullcontext()

    def load(self) -> Vault:
        return copy.deepcopy(self.value)

    def save(self, vault: Vault) -> None:
        if self.fail:
            raise MfaError("keyring_write_failed")
        self.value = copy.deepcopy(vault)


class AlgorithmTests(unittest.TestCase):
    def test_rfc6238_all_algorithms_and_timestamps(self):
        times = [59, 1111111109, 1111111111, 1234567890, 2000000000, 20000000000]
        expected = {
            "SHA1": ["94287082", "07081804", "14050471", "89005924", "69279037", "65353130"],
            "SHA256": ["46119246", "68084774", "67062674", "91819424", "90698825", "77737706"],
            "SHA512": ["90693936", "25091201", "99943326", "93441116", "38618901", "47863826"],
        }
        for algorithm, length in [("SHA1", 20), ("SHA256", 32), ("SHA512", 64)]:
            key = (b"1234567890" * 7)[:length]
            account = normalize_account(
                {
                    "name": "RFC",
                    "secret": base64.b32encode(key).decode(),
                    "digits": 8,
                    "algorithm": algorithm,
                }
            )
            for timestamp, code in zip(times, expected[algorithm], strict=True):
                with self.subTest(algorithm=algorithm, timestamp=timestamp):
                    self.assertEqual(totp(account, timestamp), code)

    def test_custom_period_digits_and_leading_zero(self):
        account = fixture()
        for digits in (6, 7, 8):
            account.update(period=45, digits=digits)
            self.assertEqual(totp(account, 44), totp(account, 0))
            self.assertNotEqual(totp(account, 44), totp(account, 45))
            self.assertEqual(len(totp(account, 59)), digits)

    def test_uri_roundtrip_unicode_reserved_characters(self):
        account = normalize_account(
            dict(fixture("GitHub:测试 & + / account"), period=60, digits=7, algorithm="SHA512")
        )
        restored = parse_uri(to_uri(account))
        for field in ("name", "secret", "algorithm", "digits", "period"):
            self.assertEqual(restored[field], account[field])

    def test_invalid_inputs_do_not_echo_secrets(self):
        for change, error in [
            ({"secret": "PRIVATE!"}, "invalid_secret"),
            ({"name": "\n"}, "invalid_name"),
            ({"algorithm": "MD5"}, "invalid_algorithm"),
            ({"period": "0"}, "invalid_options"),
            ({"digits": 5}, "invalid_options"),
        ]:
            with self.assertRaisesRegex(MfaError, "^" + error + "$"):
                normalize_account(dict(fixture(), **change))
        with self.assertRaisesRegex(MfaError, "invalid_uri"):
            parse_uri("otpauth://hotp/Example?secret=PRIVATE!")


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.directory = Path(self.tmp.name)
        self.store = MemoryStore()
        self.backend = Backend(self.store)

    def tearDown(self):
        self.tmp.cleanup()

    def backup(self, lines):
        path = self.directory / "backup.txt"
        path.write_text("\n".join(lines))
        return str(path)

    def preview(self, lines):
        return self.backend.dispatch({"op": "preview", "path": self.backup(lines)})

    def test_preview_redacts_secrets_and_reports_invalid(self):
        preview = self.preview([to_uri(fixture()), "bad-secret-uri"])
        self.assertEqual(preview["rows"][1]["error"], "invalid_uri")
        self.assertNotIn(fixture()["secret"], json.dumps(preview))
        self.assertEqual(self.store.value["accounts"], [])

    def test_partial_import_reports_result_and_exports_private_file(self):
        preview = self.preview([to_uri(fixture()), "invalid", to_uri(fixture("Skip"))])
        result = self.backend.dispatch(
            {"op": "import", "token": preview["token"], "selections": [{"index": 0}]}
        )
        self.assertEqual(
            result["result"], {"added": 1, "overwritten": 0, "invalid": 1, "skipped": 1}
        )
        exported = self.backend.dispatch(
            {"op": "export", "confirmed": True, "path": str(self.directory)}
        )
        output = Path(exported["path"])
        self.assertEqual(output.stat().st_mode & 0o777, 0o600)
        self.assertEqual(read_backup(str(output))[0]["account"]["secret"], fixture()["secret"])

    def test_automatic_backup_creates_private_directory_and_unique_files(self):
        self.store.value["accounts"] = [fixture()]
        original = copy.deepcopy(self.store.value)
        with patch("backend.Path.home", return_value=self.directory):
            first = Path(self.backend.dispatch({"op": "export", "confirmed": True})["path"])
            content = first.read_bytes()
            second = Path(self.backend.dispatch({"op": "export", "confirmed": True})["path"])
        self.assertEqual(first.parent, self.directory / "Backups" / "omarchy-mfa")
        self.assertEqual(first.parent.stat().st_mode & 0o777, 0o700)
        self.assertNotEqual(first, second)
        self.assertEqual(first.read_bytes(), content)
        for output in (first, second):
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            self.assertEqual(read_backup(output)[0]["account"]["secret"], fixture()["secret"])
        self.assertEqual(self.store.value, original)

    def test_automatic_backup_requires_confirmation_and_accounts_before_creating_files(self):
        with patch("backend.Path.home", return_value=self.directory):
            with self.assertRaisesRegex(MfaError, "export_confirmation"):
                self.backend.dispatch({"op": "export"})
            with self.assertRaisesRegex(MfaError, "empty_source"):
                self.backend.dispatch({"op": "export", "confirmed": True})
        self.assertFalse((self.directory / "Backups").exists())

    def test_automatic_backup_reports_unusable_destination_without_changing_accounts(self):
        self.store.value["accounts"] = [fixture()]
        original = copy.deepcopy(self.store.value)
        (self.directory / "Backups").write_text("existing file")
        with patch("backend.Path.home", return_value=self.directory):
            with self.assertRaises(OSError):
                self.backend.dispatch({"op": "export", "confirmed": True})
        self.assertEqual(self.store.value, original)
        self.assertEqual((self.directory / "Backups").read_text(), "existing file")

    def test_overwrite_is_explicit_and_preserves_id(self):
        original = fixture()
        self.store.value["accounts"].append(original)
        new = dict(original, period=60)
        preview = self.preview([to_uri(new)])
        self.assertTrue(preview["rows"][0]["conflict"])
        with self.assertRaisesRegex(MfaError, "name_conflict"):
            self.backend.dispatch(
                {"op": "import", "token": preview["token"], "selections": [{"index": 0}]}
            )
        self.assertEqual(self.store.value["accounts"][0]["period"], 30)
        result = self.backend.dispatch(
            {
                "op": "import",
                "token": preview["token"],
                "selections": [{"index": 0, "overwrite": True}],
            }
        )
        self.assertEqual(result["result"]["overwritten"], 1)
        self.assertEqual(self.store.value["accounts"][0]["id"], original["id"])

    def test_duplicate_batch_names_cannot_silently_overwrite(self):
        preview = self.preview([to_uri(fixture()), to_uri(fixture())])
        with self.assertRaisesRegex(MfaError, "duplicate_selection"):
            self.backend.dispatch(
                {
                    "op": "import",
                    "token": preview["token"],
                    "selections": [{"index": 0}, {"index": 1}],
                }
            )
        self.assertEqual(self.store.value["accounts"], [])

    def test_stale_preview_and_write_failure_leave_old_vault(self):
        preview = self.preview([to_uri(fixture())])
        self.store.value["accounts"].append(fixture("Another window"))
        with self.assertRaisesRegex(MfaError, "stale_data"):
            self.backend.dispatch(
                {"op": "import", "token": preview["token"], "selections": [{"index": 0}]}
            )
        preview = self.preview([to_uri(fixture())])
        self.store.fail = True
        with self.assertRaisesRegex(MfaError, "keyring_write_failed"):
            self.backend.dispatch(
                {"op": "import", "token": preview["token"], "selections": [{"index": 0}]}
            )
        self.assertEqual(len(self.store.value["accounts"]), 1)

    def test_rename_self_and_copy_recompute_via_backend(self):
        account = fixture()
        self.store.value["accounts"] = [account]
        self.backend.dispatch(
            {
                "op": "rename",
                "revision": revision(self.store.value),
                "accountId": account["id"],
                "name": account["name"],
            }
        )
        copied = []
        self.backend.copier = lambda a, paste: copied.append((a["id"], paste))
        self.backend.dispatch({"op": "copy", "accountId": account["id"], "paste": True})
        self.assertEqual(copied, [(account["id"], True)])
        self.assertGreater(self.store.value["accounts"][0]["lastUsed"], 0)
        visible = self.backend.dispatch({"op": "list"})
        self.assertNotIn(account["secret"], json.dumps(visible))


if __name__ == "__main__":
    unittest.main()
