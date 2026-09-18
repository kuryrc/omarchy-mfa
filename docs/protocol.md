# QML ↔ Python protocol

The child process reads one UTF-8 JSON object per line and returns one reply per
request. QML assigns a numeric `id` and allows one outstanding request. Stdout is
reserved for this protocol. Error replies contain a stable translated identifier,
not an exception string. Python receives requests as `Mapping[str, object]` and
validates their fields before using them; `backend/models.py` defines the typed
internal and public records.

```json
{"id": 1, "op": "list"}
{"id": 1, "ok": true, "data": {"accounts": [], "settings": {"language": "auto", "defaultAction": "copy"}, "revision": "…", "now": 0}}
{"id": 2, "ok": false, "error": "keyring_locked"}
```

| Operation | Request fields besides `id`, `op` | Success data |
| --- | --- | --- |
| `list`, `unlock` | none | Account list |
| `add` | `revision`, `account` or `uri`; optional `overwrite: true` | Account list |
| `rename` | `revision`, `accountId`, `name` | Account list |
| `delete` | `revision`, `accountId` | Account list |
| `settings` | `revision`, `settings` | Account list |
| `copy` | `accountId`, `paste` (boolean) | `{}` or `{pasteToken}` |
| `paste` | `token` from the preceding copy | `{}` |
| `preview` | `path` (backup filename) | `{token, rows}` |
| `cancel_preview` | none | `{}` |
| `import` | `token`, `selections: [{index, overwrite?}]` | Account list plus `result` |
| `export` | `confirmed: true`; optional existing directory `path` | `{path, count}` |

An account list contains `accounts`, `settings`, `revision`, and `now` (Unix
seconds). A public account contains `id`, `name`, `algorithm`, `digits`, `period`,
`lastUsed` (Unix milliseconds), `code`, and `expiresAt` (Unix seconds). **No stored
secret is included.** Internal accounts add `secret` instead of `code` and
`expiresAt`. A version-1 vault contains `version`, internal `accounts`, and
`settings`. Languages are `auto | en | zh`; default actions are `copy | paste`.

Account input permits SHA1/SHA256/SHA512, 6/7/8 digits, and periods from 1 through
2147483647 whole seconds. Digit/period strings from QML form fields are accepted
and normalized to integers. Names and Base32 secrets are validated in `core.py`.
Invalid stored accounts fail the whole vault validation without modifying it.

Preview rows contain `index`, original line `row`, `name`, `error`, and `conflict`.
Invalid rows have a translated error identifier. No row exposes a secret.
An import result contains `added`, `overwritten`, `skipped`, and `invalid` counts.
Mutations use the vault revision; imports bind the preview token to that revision.
Every selected row is validated before the batch is written once.

## Copy/paste lifecycle

1. Save recent-use metadata. A write failure starts no clipboard or paste work.
2. Generate a fresh code and start a detached clipboard owner. Return only when
   `wl-copy` is running. A paste request also returns an opaque, single-use token.
3. QML hides the panel, then sends `paste` in a later event-loop turn. The backend
   stays alive for this acknowledgment. Copy-only closes immediately.
4. The backend consumes the token and sends the worker a command through its
   private stdin pipe. The worker checks its source and deadline before `wtype`.
5. Success closes the plugin; failure restores the panel with a translated error.
   Expiry or another clipboard owner prevents the pending paste. Closing the
   control pipe cancels paste while allowing a copied code to live until expiry.

The worker outlives the popup solely to terminate its own `wl-copy` source at
expiry. Secrets/codes are never command-line arguments or disk handoff files.
Malformed backend replies clear the busy state and stop the backend so Retry is
available; they cannot leave the interface permanently waiting.
