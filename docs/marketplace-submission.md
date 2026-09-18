# Publish Omarchy MFA

The plugin lives in its own public repository, `https://github.com/kuryrc/omarchy-mfa`.
The marketplace lists that repository; it does not require copying the plugin
into Omarchy's source tree or submitting the plugin files as a marketplace PR.

Follow the current [marketplace submission guide](https://github.com/omacom/omarchy-plugin-marketplace/blob/main/SUBMISSION.md).
This document is a preparation draft, not a record of publication or approval.

## Prepare the first release

1. Complete the checks in [CONTRIBUTING.md](../CONTRIBUTING.md). Keep source,
   tests, CI, development configuration, documentation, and license notices in
   Git. Keep local OTP exports, credentials, caches, and logs out of Git.
2. Set the public Git author identity. A single initial commit is an optional
   presentation choice for the first release, not a marketplace requirement.
   Back up the local development history outside this repository before
   rewriting it. Existing local plugin clones need their history realigned if
   the original root commit changes; an ordinary fast-forward update cannot do it.
3. Create the public repository and push the release branch. Confirm that GitHub
   Actions passes on the exact commit to be submitted. Ensure `manifest.json`
   and `pyproject.toml` agree on version `1.0.0` before tagging `v1.0.0`.
4. Optionally add a root `preview.png` showing public dummy accounts. Marketplace
   previews are optional; normal screenshots do not need manual resizing.
   Never include personal account names, real secrets, or real backup contents.
5. Check that `kuryrc.mfa` remains available in the marketplace registry. Plugin
   IDs are permanent, including retired IDs; retain this ID after publication.
6. Review the issue draft below with the owner. Confirm every checklist statement,
   change each checkbox to checked only when true, and approve the completed
   title and body before creating the issue. Do not submit unchecked placeholders.

The current supported category is **Productivity** and the tags are
**security, quickshell**. `Utilities`, `authentication`, `totp`, and `productivity`
are not valid category/tag values in the current submission form.

## Submission draft

Title: `[Plugin]: MFA`

The issue body is the following block. Its six headings, their order, and the
checklist wording match the marketplace template. Checkboxes intentionally remain
unchecked until the public repository and owner confirmations are ready.

```markdown
### Repository URL

https://github.com/kuryrc/omarchy-mfa

### Category

Productivity

### Tags

security, quickshell

### Suggest a missing tag

_No response_

### Maintainer notes

MFA is a keyboard-driven TOTP search overlay by kuryrc, built with QML and
Python using Omarchy's native UI and theme. It supports account management,
copy/paste, English and Simplified Chinese, system keyring storage, and
Raycast-compatible backup/restore with preview and explicit overwrite confirmation.

This independent adaptation references the Two-Factor Authentication Code
Generator Raycast extension by Caleb Denio (cjdenio) and contributors. Both
READMEs link the upstream source and fixed reference commit, explain intentional
differences, and preserve Raycast and Omarchy license notices. The plugin is MIT licensed.

The READMEs document system Python, PyGObject/libsecret, Secret Service,
wl-clipboard 2.3+, and wtype dependencies. This plugin starts local processes,
accesses its own keyring item, reads user-selected backups, writes confirmed
plaintext backups, and manages its own expiring clipboard source. It does not
install dependencies, invoke sudo, contact network services, or use install hooks.
Removing it preserves account data in the keyring. The user adds a launcher
shortcut manually using the documented instructions; installation does not
change existing keybindings.

### Submission checklist

- [ ] The repository is public and contains installation and removal instructions.
- [ ] I have documented the plugin license and any external dependencies.
- [ ] I confirm that I own or have permission to submit this plugin and its preview assets.
- [ ] The plugin does not overwrite user configuration without explicit consent.
- [ ] I understand that approval is for listing and is not a security review.
```

Save only the reviewed issue body to a temporary Markdown file. Once the owner
explicitly approves submission, use `gh issue create` with repository
`omacom/omarchy-plugin-marketplace`, title `[Plugin]: MFA`, and `--body-file`
pointing to that file. Do not pass this entire preparation document as the body.

Automated compatibility validation and the security baseline inspect the exact
commit. Publication requires a maintainer's `approved-and-verified` decision.
Fix failures on the existing submission rather than opening duplicates.
Later releases use the marketplace's plugin verification form to publish a newer
exact commit; pushing a new GitHub commit alone does not approve the new snapshot.
