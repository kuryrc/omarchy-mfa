#!/usr/bin/python3
"""Verify real QML hides the panel before requesting paste, and recovers on failure."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from ui_harness import ROOT, prepare_view, replace_once


def main():
    for mode in (
        "success",
        "paste_failed",
        "copy_failed",
        "malformed",
        "malformed_null",
        "malformed_id",
        "copy_only",
    ):
        with tempfile.TemporaryDirectory(prefix="omarchy-mfa-paste-") as directory:
            work = Path(directory)
            prepare_view(
                work,
                [sys.executable, "-B", "-u", str(ROOT / "tests/fixtures/paste_backend.py")],
                "    property alias testPanel: panel",
            )
            source = (work / "Mfa.qml").read_text()
            source = replace_once(
                source,
                "    function rpc(request, callback, background) {",
                """    function rpc(request, callback, background) {
        if (request.op === "paste")
            console.log("MFA_PASTE_CHECK " + (!panel.visible && root.pasteToken ? "PASS " : "FAIL ") + "paste request follows hidden panel");
""",
            )
            (work / "Mfa.qml").write_text(source)
            (work / "shell.qml").write_text((ROOT / "tests/fixtures/paste.qml").read_text())
            env = dict(
                os.environ,
                QT_QPA_PLATFORM="offscreen",
                QT_QUICK_BACKEND="software",
                QS_DISABLE_CRASH_HANDLER="1",
                QS_DISABLE_FILE_WATCHER="1",
                MFA_TEST_MODE=mode,
                MFA_TEST_TRACE=str(work / "trace"),
            )
            result = subprocess.run(
                ["quickshell", "-p", str(work / "shell.qml"), "--no-color"],
                capture_output=True,
                text=True,
                env=env,
                timeout=8,
            )
            output = result.stdout + result.stderr
            signals = [line for line in output.splitlines() if "MFA_PASTE_CHECK" in line]
            print("\n".join(signals) if signals else output)
            if (
                result.returncode
                or "MFA_PASTE_DONE" not in output
                or any("FAIL" in line for line in signals)
            ):
                return 1
            operations = (work / "trace").read_text().splitlines()
            assert operations.count("copy") == 1
            expects_paste = mode in ("success", "paste_failed")
            assert operations.count("paste") == int(expects_paste)
            assert len(signals) == (2 if expects_paste else 1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
