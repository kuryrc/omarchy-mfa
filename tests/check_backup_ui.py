#!/usr/bin/python3
"""Automatic backup and restore UI with the real backend and a fixture vault.

Default: offscreen. --wayland: a separate visible Quickshell test window.
Never opens the user's keyring or clipboard. All files are temporary.
"""

import json
import os
import re
import resource
import subprocess
import sys
import tempfile
from pathlib import Path

from ui_harness import ROOT, prepare_view


def main():
    wayland = "--wayland" in sys.argv
    with tempfile.TemporaryDirectory(prefix="omarchy-mfa-backup-") as directory:
        work = Path(directory)
        fixture_home = work / "home 中文"
        destination = fixture_home / "Backups" / "omarchy-mfa"
        prepare_view(
            work,
            [
                sys.executable,
                "-B",
                "-u",
                str(ROOT / "tests/fixtures/backup_backend.py"),
                str(fixture_home),
                str(work / "trace"),
                str(work / "state"),
            ],
            """
    property alias testActions: actionsList
    property alias testFile: fileDialog
    property alias testConfirmation: confirmation
    property alias testSource: sourceInput
    property alias testRows: previewModel
    property alias testPreview: previewList
    property var testWindow: keyRoot.Window.window
""",
            wayland=wayland,
        )
        qml = (ROOT / "tests/fixtures/backup.qml").read_text()
        if wayland:
            qml, count = re.subn(
                r"    Window \{.*?\n    \}", "    Mfa {id: testMfa}", qml, count=1, flags=re.S
            )
            assert count == 1
        (work / "shell.qml").write_text(qml)
        env = dict(
            os.environ,
            QT_QPA_PLATFORM="wayland" if wayland else "offscreen",
            QT_QPA_PLATFORMTHEME="gtk3" if wayland else "",
            QT_QUICK_CONTROLS_STYLE="Fusion",
            QS_DISABLE_CRASH_HANDLER="1",
            QS_DISABLE_FILE_WATCHER="1",
            QT_QUICK_BACKEND="software",
        )
        env.update(
            MFA_TEST_DESTINATION_PATH=str(destination), MFA_TEST_DESTINATION=destination.as_uri()
        )
        if wayland:
            env.setdefault("WAYLAND_DISPLAY", "wayland-1")
            env.setdefault("XDG_RUNTIME_DIR", "/run/user/1000")
            env.setdefault(
                "DBUS_SESSION_BUS_ADDRESS", "unix:path=" + env["XDG_RUNTIME_DIR"] + "/bus"
            )
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        result = subprocess.run(
            ["quickshell", "-p", str(work / "shell.qml"), "--no-color"],
            env=env,
            capture_output=True,
            text=True,
            timeout=20,
        )
        output = result.stdout + result.stderr
        print(output)
        if (
            result.returncode
            or "MFA_BACKUP_DONE" not in output
            or "MFA_BACKUP_CHECK FAIL" in output
        ):
            return 1
        backups = list(destination.glob("*.txt"))
        assert len(backups) == 1, "Cancel must not write a backup"
        assert destination.stat().st_mode & 0o777 == 0o700
        assert backups[0].stat().st_mode & 0o777 == 0o600
        sys.path.insert(0, str(ROOT / "backend"))
        from backend import read_backup

        restored = json.loads((work / "state").read_text())["accounts"]
        exported = [row["account"] for row in read_backup(backups[0])]
        fields = ("name", "secret", "algorithm", "digits", "period")

        def values(rows):
            return sorted(tuple(row[field] for field in fields) for row in rows)

        assert values(restored) == values(exported)
        operations = (work / "trace").read_text().splitlines()
        assert operations.count("export") == operations.count("import") == 1
        print(
            "PASS: automatic 0700 directory and 0600 backup, cancel wrote nothing, restored OTP fields match"
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
