"""Regressions use public dummy secrets and an in-memory vault."""

import copy
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from core import (
    MAX_PERIOD,
    MfaError,
    normalize_account,
    parse_uri,
    revision,
    to_uri,
    totp,
    validate_vault,
)
from test_mfa import Backend, MemoryStore, fixture


class RegressionTests(unittest.TestCase):
    def test_failed_save_must_not_start_a_paste(self):
        store = MemoryStore()
        account = fixture()
        store.value["accounts"] = [account]
        store.fail = True
        copies = []
        backend = Backend(store, copier=lambda account, paste: copies.append(paste))
        with self.assertRaisesRegex(MfaError, "keyring_write_failed"):
            backend.dispatch({"op": "copy", "accountId": account["id"], "paste": True})
        self.assertEqual(copies, [], "clipboard work must start only after saving succeeds")

    def test_oversized_period_is_rejected_before_save(self):
        store = MemoryStore()
        original = copy.deepcopy(store.value)
        account = dict(fixture(), period=10**309)
        with self.assertRaisesRegex(MfaError, "invalid_options"):
            Backend(store).dispatch(
                {"op": "add", "account": account, "revision": revision(store.value)}
            )
        self.assertEqual(store.value, original)

    def test_oversized_period_is_invalid_in_preview(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "backup.txt"
            path.write_text(to_uri(dict(fixture(), period=10**309)))
            result = Backend(MemoryStore()).dispatch({"op": "preview", "path": str(path)})
        self.assertEqual(result["rows"][0]["error"], "invalid_options")

    def test_period_boundaries_survive_add_list_and_uri_roundtrip(self):
        for period in (1, MAX_PERIOD):
            with self.subTest(period=period):
                store = MemoryStore()
                result = Backend(store).dispatch(
                    {
                        "op": "add",
                        "account": dict(fixture(), period=period),
                        "revision": revision(store.value),
                    }
                )
                account = store.value["accounts"][0]
                self.assertEqual(result["accounts"][0]["period"], period)
                self.assertEqual(parse_uri(to_uri(account))["period"], period)
                self.assertEqual(len(totp(account)), 6)
        for period in (0, -1, MAX_PERIOD + 1, "1.5", True):
            with self.subTest(period=period), self.assertRaisesRegex(MfaError, "invalid_options"):
                normalize_account(dict(fixture(), period=period))

    def test_invalid_existing_period_is_a_vault_error(self):
        store = MemoryStore()
        store.value["accounts"] = [dict(fixture(), period=10**309)]
        original = copy.deepcopy(store.value)
        with self.assertRaisesRegex(MfaError, "invalid_vault"):
            validate_vault(store.value)
        self.assertEqual(store.value, original)

    def test_preview_allows_valid_subset_when_other_period_is_invalid(self):
        store = MemoryStore()
        backend = Backend(store)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "backup.txt"
            path.write_text(
                to_uri(fixture()) + "\n" + to_uri(dict(fixture("Invalid"), period=MAX_PERIOD + 1))
            )
            preview = backend.dispatch({"op": "preview", "path": str(path)})
            result = backend.dispatch(
                {"op": "import", "token": preview["token"], "selections": [{"index": 0}]}
            )
        self.assertEqual(
            result["result"], {"added": 1, "overwritten": 0, "invalid": 1, "skipped": 0}
        )
        self.assertEqual(len(store.value["accounts"]), 1)

    def test_settings_validation_is_shared_and_bad_shapes_do_not_write(self):
        store = MemoryStore()
        backend = Backend(store)
        original = copy.deepcopy(store.value)
        for settings in (None, [], "en", {"language": "fr", "defaultAction": "copy"}):
            with (
                self.subTest(settings=settings),
                self.assertRaisesRegex(MfaError, "invalid_options"),
            ):
                backend.dispatch(
                    {"op": "settings", "settings": settings, "revision": revision(store.value)}
                )
            self.assertEqual(store.value, original)
        backend.dispatch(
            {
                "op": "settings",
                "settings": {"language": "zh", "defaultAction": "paste", "unknown": "ignored"},
                "revision": revision(store.value),
            }
        )
        self.assertEqual(store.value["settings"], {"language": "zh", "defaultAction": "paste"})
        self.assertEqual(validate_vault(store.value), store.value)


if __name__ == "__main__":
    unittest.main()
