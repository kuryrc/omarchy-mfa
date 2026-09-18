#!/usr/bin/python3
"""Exercise real overlay refresh and keyboard events with a fake backend.

Only the platform window and process command are adapted. No real account,
keyring, clipboard, or visible desktop surface is accessed.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from ui_harness import ROOT, prepare_view


def main():
    with tempfile.TemporaryDirectory(prefix="omarchy-mfa-ui-") as directory:
        work = Path(directory)
        prepare_view(
            work,
            [sys.executable, "-u", str(ROOT / "tests/fixtures/refresh_backend.py")],
            """
    width: 1000
    height: 800
    property alias testView: accountList
    property alias testSearch: search
    property alias testActions: actionsList
    property alias testPreview: previewList
""",
        )
        (work / "shell.qml").write_text((ROOT / "tests/fixtures/refresh.qml").read_text())
        env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QSG_RHI_BACKEND="software")
        env.pop("WAYLAND_DISPLAY", None)
        result = subprocess.run(
            ["quickshell", "-p", str(work / "shell.qml"), "--no-color"],
            env=env,
            capture_output=True,
            text=True,
            timeout=8,
        )
        output = result.stdout + result.stderr
        signals = [line for line in output.splitlines() if "MFA_UI_CHECK" in line]
        print("\n".join(signals) if signals else output)
        return (
            0
            if result.returncode == 0
            and "MFA_UI_DONE" in output
            and signals
            and all("PASS" in line for line in signals)
            else 1
        )


if __name__ == "__main__":
    raise SystemExit(main())
