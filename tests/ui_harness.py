"""Isolate the real QML view from the desktop and inject a fixture backend."""

import json
import os
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(source: str, old: str, new: str) -> str:
    assert source.count(old) == 1, f"UI adapter needs updating: {old!r}"
    return source.replace(old, new, 1)


def prepare_view(work: Path, command: list[str], aliases: str, wayland: bool = False) -> None:
    for module in ("Commons", "Ui"):
        shell = Path(os.environ.get("OMARCHY_SHELL_DIR", "/usr/share/omarchy/shell"))
        (work / module).symlink_to(shell / module)
    shutil.copyfile(ROOT / "I18n.js", work / "I18n.js")
    source = (ROOT / "Mfa.qml").read_text()
    source = replace_once(source, "id: root\n", "id: root\n" + aliases + "\n")
    source = replace_once(
        source, '["/usr/bin/python3", "-B", "-u", root.backendPath]', json.dumps(command)
    )
    if not wayland:
        start = source.index("    PanelWindow {")
        end = source.index("        Rectangle {", start)
        before, after = source[:start], source[end:]
        source = replace_once(source[start:end], "    PanelWindow {", "    Item {")
        # Preserve visibility and its handlers: they implement the paste handoff.
        source, count = re.subn(
            r"        anchors \{\n(?:            (?:top|bottom|left|right): true\n){4}        \}",
            "        anchors.fill: parent",
            source,
            count=1,
        )
        assert count == 1, "Panel anchors adapter needs updating"
        for line in (
            "        exclusionMode: ExclusionMode.Ignore\n",
            '        color: "transparent"\n',
            '        WlrLayershell.namespace: "omarchy-mfa"\n',
            "        WlrLayershell.layer: WlrLayer.Overlay\n",
            "        WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive\n",
        ):
            source = replace_once(source, line, "")
        source = before + source + after
    (work / "Mfa.qml").write_text(source)
