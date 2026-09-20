#!/usr/bin/python3
"""Capture the real QML card with synthetic data and an isolated desktop environment."""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from ui_harness import ROOT, prepare_view, replace_once

FILES = ("accounts.png", "actions.png", "add-account.png", "restore-preview.png", "settings-zh.png")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="omarchy-mfa-previews-") as directory:
        work = Path(directory)
        prepare_view(
            work,
            [sys.executable, "-B", "-u", str(ROOT / "tests/fixtures/previews_backend.py")],
            """
    property alias captureCard: card
    property alias captureClock: previewClock
    property alias captureActions: actionsList
    property alias captureName: nameInput
    property alias captureSecret: secretInput
""",
        )
        view = work / "Mfa.qml"
        view.write_text(
            replace_once(
                view.read_text(),
                "    Timer {\n        interval: 250",
                "    Timer {\n        id: previewClock\n        interval: 250",
            )
        )
        shutil.copyfile(ROOT / "tests/fixtures/previews.qml", work / "shell.qml")
        home, output = work / "home", work / "images"
        home.mkdir()
        output.mkdir()
        # A fixed public Tokyo Night palette; do not read the user's selected theme.
        theme = home / ".local/state/omarchy/current/theme"
        theme.mkdir(parents=True)
        (theme / "colors.toml").write_text(
            'background = "#1a1b26"\nforeground = "#a9b1d6"\n'
            'accent = "#7aa2f7"\nurgent = "#f7768e"\n'
        )
        env = {
            "PATH": "/usr/bin:/bin",
            "HOME": str(home),
            "LANG": "en_US.UTF-8",
            "LC_ALL": "en_US.UTF-8",
            "QT_QPA_PLATFORM": "offscreen",
            "QSG_RHI_BACKEND": "software",
            "QT_SCALE_FACTOR": "1",
            "QML_DISABLE_DISK_CACHE": "1",
            "MFA_PREVIEW_OUTPUT": str(output),
        }
        for name in ("CONFIG", "DATA", "CACHE", "STATE", "RUNTIME"):
            path = work / name.lower()
            path.mkdir(mode=0o700)
            env[f"XDG_{name}_HOME" if name != "RUNTIME" else "XDG_RUNTIME_DIR"] = str(path)
        result = subprocess.run(
            ["dbus-run-session", "--", "quickshell", "-p", str(work / "shell.qml"), "--no-color"],
            env=env,
            capture_output=True,
            text=True,
            timeout=25,
        )
        log = result.stdout + result.stderr
        if result.returncode or "MFA_PREVIEW_DONE" not in log or "MFA_PREVIEW_FAILED" in log:
            print(log)
            return 1
        for name in FILES:
            if not (output / name).is_file():
                raise RuntimeError(f"Missing preview: {name}")
        target = ROOT / "docs/previews"
        target.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(output / "accounts.png", ROOT / "preview.png")
        for name in FILES[1:]:
            shutil.copyfile(output / name, target / name)
        print("Rendered five synthetic previews without the real backend or desktop session.")
        print("preview.png\n" + "\n".join(f"docs/previews/{name}" for name in FILES[1:]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
