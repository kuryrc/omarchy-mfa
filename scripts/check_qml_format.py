#!/usr/bin/python3
"""Check (or apply) the same Qt 6 formatting for production QML/JS and UI fixtures."""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    formatter = os.environ.get("QMLFORMAT", "/usr/lib/qt6/bin/qmlformat")
    files = [ROOT / "Mfa.qml", ROOT / "I18n.js", *sorted((ROOT / "tests/fixtures").glob("*.qml"))]
    failed = False
    for path in files:
        command = [formatter, "--ignore-settings", "--newline", "unix", str(path)]
        if "--write" in sys.argv:
            subprocess.run([*command, "--inplace"], check=True)
        else:
            result = subprocess.run(command, check=True, capture_output=True)
            if result.stdout != path.read_bytes():
                print(f"Needs qmlformat: {path.relative_to(ROOT)}")
                failed = True
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
