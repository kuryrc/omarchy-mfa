# Development contract

The implementation stack is **QML + Python**. QML and small QML JavaScript
helpers own presentation, keyboard navigation, and RPC lifecycle. Python owns
TOTP calculation, validation, the Secret Service vault, backup files, and
Wayland clipboard lifetime. No Node/TypeScript runtime or build step is required.

Use Omarchy theme tokens and `qs.Ui` components. Keep desktop integration out of
`core.py`. `models.py` defines internal `TypedDict` records and the `VaultStore`
protocol; untrusted JSON is validated at the boundary, never cast directly into
an account or vault. Production Python is checked with **mypy strict**. The
PyGObject/libsecret binding is the sole dynamic external API boundary in
`store.py`; do not spread `Any` or blanket type ignores into business logic.
See [the wire protocol](docs/protocol.md) before changing either side of RPC.

Use four spaces and Ruff's formatter/import ordering for Python, and the Qt 6
`qmlformat` output for QML/JavaScript (no import reordering). Formatter rules live
in `pyproject.toml` and `scripts/check_qml_format.py`; development tools are pinned
in `requirements-dev.txt`. Formatting owns line wrapping; the linter checks
imports, undefined names, common bugs, and supported modern Python syntax.

## Local checks

Runtime uses `/usr/bin/python3` so Arch's GI bindings are available. Development
tools may live in a virtual environment and are not plugin runtime dependencies:

```sh
/usr/bin/python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy
/usr/bin/python3 -B scripts/check_qml_format.py
/usr/bin/python3 -B -m unittest discover -s tests -v
/usr/bin/python3 -B tests/check_ui_refresh.py
/usr/bin/python3 -B tests/check_backup_ui.py
/usr/bin/python3 -B tests/check_paste_ui.py
omarchy plugin validate .
```

Apply formatting with `.venv/bin/ruff format .` and
`/usr/bin/python3 -B scripts/check_qml_format.py --write`.

The UI suite requires Quickshell, Qt 6.11+, and Omarchy's `shell/Commons` and
`shell/Ui`. Override `OMARCHY_SHELL_DIR` to test another source checkout; override
`QMLFORMAT` for a different Qt 6 binary path. UI fixtures are normal QML/Python
files under `tests/fixtures`, so formatters also cover the test code. The harness
adapts only the platform window and backend command, and asserts each rewrite
matches exactly once. Visibility handlers remain intact for paste testing.

GitHub Actions checks Python 3.12 and 3.14, Ruff, strict mypy, and unit/worker
regressions. A separate Arch Linux job checks QML/JS formatting and runs all three
offscreen UI suites against pinned Omarchy 4.0.3 sources. Arch Qt/Quickshell
packages follow the distribution, exposing future host compatibility changes.
Offscreen tests do not prove compositor focus behavior: run the optional live
backup test and a dummy-account paste smoke test on Wayland when changing those
integration paths. Never use a real OTP secret in a test or log.

## Change discipline

- Validate inputs before persistence. Periods are integer seconds in
  `1..2147483647`, bounded to the signed 32-bit range and exactly representable
  by both Python and QML. Settings have one shared validator.
- Generate codes after any potentially slow vault write. Paste starts only after
  QML hides its panel and explicitly acknowledges that handoff. A fixed delay
  is not an acknowledgment. A worker checks ownership and expiry again at paste.
- Keep protocol stdout machine-readable. Errors are translated identifiers,
  never raw exceptions, account secrets, or URLs.
- Add regression tests at the affected boundary: pure functions for OTP,
  in-memory storage for mutations, fake commands for clipboard workers, and
  actual QML events for UI behavior. Tests must not access personal accounts,
  backups, keyrings, or clipboard contents.
- Preserve kuryrc authorship and Raycast/Omarchy attribution and licenses.

The source and installed checkout are separate repositories. Commit source
changes before updating a locally installed plugin. On the tested host, stop
Omarchy Shell before updating, then restart it, to avoid Quickshell's IPC hot
reload crash. Do not edit `/usr/share/omarchy` or symlink files into the plugin.
