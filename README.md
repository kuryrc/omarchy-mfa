# Omarchy MFA

[简体中文](README.zh-CN.md)

A native Omarchy MFA plugin by **kuryrc**, based on the **Two-Factor
Authentication Code Generator** Raycast extension by **Caleb Denio (cjdenio)
and its contributors**. Search your accounts, copy a time-based code, and get
back to the app you were using.

Reference: [Raycast Store](https://www.raycast.com/cjdenio/two-factor-authentication-code-generator)
and [upstream source at 3c654737b0d566d3103fcdf72221a9f34664bdf2](https://github.com/raycast/extensions/tree/3c654737b0d566d3103fcdf72221a9f34664bdf2/extensions/two-factor-authentication-code-generator).
The interface uses Omarchy's native shell components and theme tokens.

## Features

- Keyboard-driven search, codes, countdowns, and recently used ordering.
- Copy or paste; choose the default action in Settings.
- Add an account by Base32 secret or `otpauth://totp/` URL; rename or delete it.
- SHA1 / SHA256 / SHA512, 6 / 7 / 8 digits, and a whole-second period from 1 to 2147483647.
- System keyring storage through Secret Service; no plaintext storage fallback.
- Compatible line-oriented `otpauth://` backups, with preview, per-entry selection,
  explicit overwrite confirmation, and errors for invalid entries.
- English and Simplified Chinese, with automatic system-language selection.
- Sensitive clipboard marking and expiration of codes owned by the plugin.

There is no direct Vicinae database import, QR scanner, HOTP, or cloud sync.

## Requirements

Omarchy's Quickshell plugin host and UI components are required. Local testing
uses Omarchy **4.0.3**; current 4.0.4 ships the same required base packages, but
has not yet been runtime-tested for this plugin.

- `/usr/bin/python3`, `python-gobject`, and `libsecret` (GI namespace `Secret-1`).
- A running Secret Service with a default keyring, such as GNOME Keyring.
- `wl-clipboard` **2.3+** (`wl-copy --sensitive --foreground`).
- `wtype` for paste, and a Wayland session with a private `XDG_RUNTIME_DIR`.

These are included in standard recent Omarchy installations. No pip, npm,
build step, network service, or background system service is installed by this
plugin. A missing or locked keyring produces an actionable message. Use the
**Unlock keyring** action when needed. Dependencies are not automatically
installed by Omarchy's plugin installer.

## Install and open

Once the repository is published:

```sh
omarchy plugin add https://github.com/kuryrc/omarchy-mfa.git --enable
omarchy-shell shell toggle kuryrc.mfa
```

For a local checkout during development:

```sh
omarchy plugin add /absolute/path/to/omarchy-mfa --enable
```

Add a binding to `~/.config/hypr/bindings.lua` after other binding imports.
This replaces any existing binding on the same key; choose a different key if
you want to keep it:

```lua
hl.unbind("SUPER + SHIFT + L")
o.bind("SUPER + SHIFT + L", "MFA", "omarchy-shell shell toggle kuryrc.mfa")
```

Then run `hyprctl reload` and check `hyprctl configerrors`.

## Use

On first launch, choose **Add account** or **Add by otpauth URL**. Unless your
provider specifies otherwise, the defaults are SHA1, 6 digits, and 30 seconds.

| Shortcut | Action |
| --- | --- |
| Type | Search accounts |
| Up / Down or Ctrl + p / Ctrl + n | Move selection up / down in accounts, Actions, or import preview |
| Enter | Copy, or the configured default action |
| Shift + Enter | The other action: paste or copy |
| Ctrl + k | Open the action menu |
| Ctrl + Shift + n | Add an account |
| Ctrl + U | Add an otpauth URL |
| Ctrl + E | Rename the selected account |
| Esc | Return to the previous page; close from the main list |

**Actions → Settings** changes the default action and language. Paste hides
the panel and explicitly acknowledges that handoff before sending Shift+Insert. The
destination application must support this shortcut; copying works independently.

Esc and the Back button retrace the page you came from: Add account opened
through Actions returns to Actions, preserving its selection. The same form
opened with Ctrl+Shift+n returns to the main list. A successful save returns to the
main list.

**Back up accounts** asks for confirmation, then automatically creates a new
`0600` text file under `~/Backups/omarchy-mfa/`. The directory is created with
`0700` permissions if missing. Filenames contain a UTC timestamp; existing
backups are kept, and the full path is displayed after saving. No file or
directory selection is needed. The file contains plaintext secrets.
Backups preserve account names, secrets, algorithms, periods, and
digits; like the upstream format, they do not preserve recent-use ordering
or plugin settings.

**Restore backup** previews every nonempty line. Valid new entries start
selected; existing names start skipped. Select an existing entry to mark it
for overwrite, then confirm the batch. Invalid entries include a reason and
are not imported. Only one selected entry per name is allowed. The selected
batch replaces the keyring vault in one write; an outdated preview is rejected.

The restore file picker uses Qt Quick inside the MFA panel to avoid native GTK
dialog crashes taking down the shared shell. On Qt 6.11.2, the picker can show
the wrong directory when its name contains `#` or percent-encoded sequences.
For those paths, paste the full backup filename into **Restore backup** directly.

## Data and clipboard behavior

Accounts and preferences are in one versioned Secret Service item labeled
`Omarchy MFA (kuryrc.mfa)`, with application attribute `kuryrc.mfa`. Secrets
do not live in this checkout or in `shell.json`. The plugin's runtime lock
file contains no credentials. No account data is sent over the network.

**System keyring does not necessarily mean encryption at rest.** Omarchy's
default keyring is passwordless. Actual protection follows your desktop
keyring configuration. The UI shares the Omarchy shell process with other
plugins and is not a security sandbox.

Each copy uses a separate foreground `wl-copy` data source, marked sensitive.
At expiry, the plugin ends only that source. It never issues a global clipboard
clear, so content subsequently copied by another application is preserved.
The expiry process outlives the popup. Clipboard temporary data uses the
user's runtime directory. Omarchy's clipboard history respects the sensitive
marker. Other clipboard managers may ignore it or retain their own copies;
the plugin cannot remove copies held by another process.

## Update and uninstall

```sh
omarchy plugin update kuryrc.mfa
omarchy plugin disable kuryrc.mfa
omarchy plugin remove kuryrc.mfa
```

Remove your custom keybinding when uninstalling. Account data remains in the
keyring so reinstalling does not lose it. To erase it, remove the specifically
labeled `Omarchy MFA (kuryrc.mfa)` item with your keyring manager after making
any backup you need. Removing the plugin never erases other keyring entries.

## Development and validation

The implementation stack is **QML + Python**. See [CONTRIBUTING.md](CONTRIBUTING.md)
for formatting, strict typing, local checks, and CI, and [the protocol](docs/protocol.md)
for the QML/Python boundary.

If an update still shows the old interface, close the popup and run
`omarchy-restart-shell`, then open it again. On the tested Omarchy 4.0.3
session, rescanning plugins left the previous QML interface in memory; a
shell restart loaded the updated files. The bar briefly reloads while
application windows remain open.

The source checkout and installed checkout are separate Git repositories.
Commit in the source checkout, then use `omarchy plugin update kuryrc.mfa` if
the installation's origin points to that local checkout. Do not use symlinks
inside the plugin: Omarchy's validator rejects them.

```sh
/usr/bin/python3 -B -m unittest discover -s tests -v
/usr/bin/python3 -B tests/check_ui_refresh.py
/usr/bin/python3 -B tests/check_backup_ui.py
/usr/bin/python3 -B tests/check_paste_ui.py
# Optional: opens a separate test overlay in your Wayland session.
/usr/bin/python3 -B tests/check_backup_ui.py --wayland
omarchy plugin validate .
/usr/bin/python3 -B scripts/check_qml_format.py
```

The UI regression runs the real QML layout and RPC lifecycle with an offscreen
viewport and fake accounts; it neither reads a keyring nor touches the clipboard.
It checks that refresh preserves viewport height, scroll offset, and selection,
and sends real Qt key events to verify Ctrl+k from the search field and during
background refresh without disrupting normal typing. Menu checks cover arrow
and hover selection, Return, keypad Enter, and Space activation.
They also cover Ctrl+p/n navigation and a single selection highlight when
the mouse stays over another action.
Backend tests use public RFC 6238 vectors and temporary backup files.
The backup UI test confirms automatic export without a chooser, selects the
exported file for restore with mouse events, and confirms overwrite with key
events. It repeats backup confirmation and the restore picker five times. It
uses the real backend with an in-memory fixture store, verifies automatic
directory creation, `0700`/`0600` permissions and every restored OTP field, and
checks canceled actions wrote nothing. It does not access real accounts.

On the tested Quickshell 0.3.1 / Omarchy 4.0.3 combination, updating an installed
plugin while the shell is running has also crashed during IPC registration on
reload. Stop the shell before updating during local development, then start it
again. A stopped shell makes the update command's final rescan fail even if the
Git update and validation succeeded; verify the installed revision after restart.

The backend uses newline-delimited JSON over a private child-process pipe.
Do not log requests: add-account requests contain secrets. The UI receives
account metadata, codes, and expiry times rather than stored secrets during
normal listing. Stale mutations are rejected by a vault revision check.

## Attribution and license

This is an independent Omarchy adaptation, not an official Raycast extension
or a claim of endorsement. The upstream Raycast extension defines the feature
and backup-format baseline. Intentional differences include confirmed
overwrites, reported invalid backup entries, action-time code generation,
system keyring storage, and expiring sensitive clipboard ownership.

Plugin author: **kuryrc**. [MIT license](LICENSE).
Preserved upstream notices: [Raycast](LICENSES/Raycast-MIT.txt) and
[Omarchy](LICENSES/Omarchy-MIT.txt). Omarchy's shell components and overlay
patterns informed the QML implementation.
