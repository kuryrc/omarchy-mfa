"""Run the actual detached worker with fake Wayland commands and public dummy codes."""

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from clipboard import Clipboard, read_reply
from core import MAX_PERIOD, MfaError
from test_mfa import Backend, MemoryStore, fixture

ROOT = Path(__file__).resolve().parents[1]


class ClipboardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        self.trace = self.work / "paste"
        self.replaced = self.work / "replaced"
        self.started = self.work / "started"
        scripts = {
            "wl-copy": """import os,sys,time
from pathlib import Path
sys.stdin.buffer.read()
Path(os.environ['TEST_STARTED']).touch()
while not Path(os.environ['TEST_REPLACED']).exists():
    time.sleep(0.01)
""",
            "wtype": """import os,sys
from pathlib import Path
Path(os.environ['TEST_PASTE']).touch()
sys.exit(int(os.environ.get('TEST_PASTE_EXIT', '0')))
""",
        }
        for name, source in scripts.items():
            path = self.work / name
            path.write_text(f"#!{sys.executable}\n" + source)
            path.chmod(0o700)
        self.environment = patch.dict(
            os.environ,
            {
                "PATH": str(self.work) + os.pathsep + os.environ.get("PATH", ""),
                "XDG_RUNTIME_DIR": str(self.work),
                "TEST_STARTED": str(self.started),
                "TEST_REPLACED": str(self.replaced),
                "TEST_PASTE": str(self.trace),
            },
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.workers = []
        self.addCleanup(self.stop_workers)

    def stop_workers(self):
        self.replaced.touch()
        for worker in self.workers:
            if worker.stdin and not worker.stdin.closed:
                worker.stdin.close()
            try:
                worker.wait(timeout=2)
            except subprocess.TimeoutExpired:
                worker.terminate()
                worker.wait(timeout=2)
            if worker.stdout:
                worker.stdout.close()

    def raw_worker(self, lifetime=2):
        worker = subprocess.Popen(
            [sys.executable, "-B", str(ROOT / "backend/clipboard.py"), "worker"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        self.workers.append(worker)
        worker.stdin.write(
            (json.dumps({"code": "123456", "expiresAt": time.time() + lifetime}) + "\n").encode()
        )
        worker.stdin.flush()
        read_reply(worker.stdout, "ready")
        return worker

    def test_slow_save_cannot_paste_before_explicit_hidden_ack(self):
        store = MemoryStore()
        account = fixture()
        account["period"] = MAX_PERIOD
        store.value["accounts"] = [account]
        save = store.save

        def slow_save(vault):
            time.sleep(0.4)
            self.assertFalse(
                self.trace.exists(), "paste started while the panel still waited for save"
            )
            save(vault)

        store.save = slow_save
        backend = Backend(store)
        response = backend.dispatch({"op": "copy", "accountId": account["id"], "paste": True})
        self.workers.append(backend.clipboard.pending[1])
        time.sleep(0.35)  # Longer than the previous implementation's blind 250 ms delay.
        self.assertFalse(self.trace.exists())
        backend.dispatch({"op": "paste", "token": response["pasteToken"]})
        self.assertTrue(self.trace.exists())
        with self.assertRaisesRegex(MfaError, "paste_expired"):
            backend.dispatch({"op": "paste", "token": response["pasteToken"]})

    def test_expiry_stops_source_without_pasting(self):
        worker = self.raw_worker(lifetime=1)
        worker.wait(timeout=3)
        self.assertFalse(self.trace.exists())
        # The worker waits for wl-copy to exit before completing.
        self.assertEqual(worker.returncode, 0)

    def test_new_clipboard_owner_cancels_pending_paste(self):
        worker = self.raw_worker()
        self.replaced.touch()
        worker.wait(timeout=2)
        self.assertFalse(self.trace.exists())

    def test_backend_exit_cancels_paste_but_keeps_copy_until_expiry(self):
        worker = self.raw_worker(lifetime=1)
        worker.stdin.close()
        time.sleep(0.15)
        self.assertIsNone(worker.poll())
        worker.wait(timeout=3)
        self.assertFalse(self.trace.exists())

    def test_failed_wtype_is_reported_and_token_is_consumed(self):
        clipboard = Clipboard()
        account = fixture()
        account["period"] = MAX_PERIOD
        token = clipboard.copy(account, True)
        self.workers.append(clipboard.pending[1])
        # Environment is inherited when the worker is spawned.
        self.trace.unlink(missing_ok=True)
        (self.work / "wtype").write_text(f"#!{sys.executable}\nraise SystemExit(1)\n")
        with self.assertRaisesRegex(MfaError, "paste_failed"):
            clipboard.paste(token)
        self.assertIsNone(clipboard.pending)
        self.assertFalse(self.trace.exists())


if __name__ == "__main__":
    unittest.main()
