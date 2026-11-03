# Apollo preparation: November 3, 2026

Prepared directly against the Captain server over authenticated, pinned-host SFTP. The endpoint accepts file access and rejects SSH exec requests; it does not provide a remote shell. No Phase 3 deployment, merge, bot restart, Discord sync or production database update was performed.

## Completed preparation

- The existing Windows files were located and validated privately:
  - `C:\Users\beauj\AppData\Local\TheCaptain-Realms-Private\tokens\account.realms.enc`
  - `C:\Users\beauj\AppData\Local\TheCaptain-Realms-Private\keys\key-one.dpapi`
- The original DPAPI-wrapped Fernet key successfully decrypted the original record in memory. Its client/account binding matched the successful pilot. No replacement key/token was generated; no refresh or OAuth call was made.
- The existing record was copied over encrypted SFTP to `/.captain-realms-private/tokens/account.realms.enc` in Apollo's SFTP view. A separate download proved byte-for-byte equality with the unchanged Windows original.
- The existing Fernet key was unwrapped locally in memory, encoded as the existing key-ID map, and transferred as a pending `.env` fragment to `/.captain-realms-private/config/.env`. The key was never printed or placed in a shell command argument/history. This is a private plaintext environment file at rest, protected by mode 0600 and a mode-0700 parent; it is not claimed to be a hosting secret vault. The Windows DPAPI blob was not uploaded.
- Disabled operational settings were staged at `/.captain-realms-private/config/realms.settings.json`. They preserve the pilot's application, account reference, designated gamertag, auth operator, validated client version and selected Realm, without duplicating the guild/OP role settings.
- The private root and its config/token directories were set to 0700; staged files were set to 0600 and read back to verify permissions/content. `/.git/info/exclude` now excludes `/.captain-realms-private/`, preserving its existing rules. No tracked ignore file or production source was changed.
- The active `/.env` was downloaded only into restrictive Windows staging for analysis. Its final bytes match the initial download exactly. It contains the existing database/Discord bootstrap values and no CAPTAIN_REALMS variables. Its existing SFTP-reported mode is 0644; it was not replaced or chmodded. Tighten to 0600 under the verified application owner during approved activation.

Local staging is inside `C:\Users\beauj\AppData\Local\TheCaptain-Realms-Private\apollo-staging\`, with restrictive Windows ACLs. It includes the private pending fragment, private downloads and the original environment backup. Do not attach, print, commit or synchronize that directory to a public/shared location.

## Prepared environment configuration

The private pending fragment contains exactly these three variables. Secret content is deliberately omitted from this report:

```dotenv
CAPTAIN_REALMS_STORE_DIR=/home/container/.captain-realms-private/tokens
CAPTAIN_REALMS_KEY_ID=key-one
CAPTAIN_REALMS_KEYS='<existing key-one Fernet map; present only in the private prepared file>'
```

The displayed KEYS line is explanatory, not a usable replacement: transfer/merge the prepared fragment itself, not this redacted illustration. Existing `.env` values must be preserved. The store path uses Apollo's conventional in-container `/home/container` volume mapping; SFTP exposes the jailed volume as `/`, without a shell to independently inspect the mount namespace. Confirm that internal mount path during activation.

The Phase 3 development branch now permits this exact private token location under the conditions below. Production still runs its existing code; do not activate or restart it until the reviewed release is approved.

## Resolved layout blocker

The code checkout occupies the SFTP root and `ls /..` stays in that root. Previously, `EncryptedTokenStore.__init__` rejected every directory equal to or beneath the repository root, including the designated staged path.

The smallest adjustment now permits exactly `<checkout>/.captain-realms-private/tokens`. It does not permit the checkout root, arbitrary subdirectories, the private config directory, similarly named directories or descendants of the token directory. External stores, including the successful Windows setup, retain their previous behavior.

For this one in-checkout exception, the private parent must pass the existing ownership/private-permission checks, the entire `.captain-realms-private/` directory must be effectively ignored by Git, and `git ls-files` must report no tracked file anywhere under it. The branch adds a durable root `.gitignore` rule; the existing server-local `.git/info/exclude` also works. Checks run at construction/open and each read/write boundary. Removing ignore protection, tracking a private file, unsafe permissions or missing/failing Git makes storage fail closed. Git subprocesses receive only basic OS environment values, without the Fernet key/token environment. No raw Git output is logged.

Existing symlink/junction rejection, token-file permissions, encrypted schema/binding validation, atomic saves, single-writer locking and cryptography/DPAPI handling are unchanged. The already-staged key and encrypted record need no replacement or new Microsoft authentication. No production code or staged credential was modified by this development fix.

## Apollo panel variables

The panel's Environment Variables page is a suitable alternative to adding these three values to the active `.env`, provided Apollo injects them into the bot process at startup. The runtime already reads them from `os.environ`; python-dotenv's default `override=False` preserves process-provided values. Prefer that option for `CAPTAIN_REALMS_KEYS` so the active key can be kept separate from the token files. Use the existing private staged fragment for provisioning; do not copy its secret into chat, logs or shell arguments. A panel password-style mask does not by itself prove encrypted-at-rest storage or prevent panel administrators from reading the value.

If using the panel's Import File function after approval, import only the three-variable private fragment, not the full existing production `.env`, and verify the key value remains masked. Do not change the existing `TOKEN` variable or duplicate role/guild/database settings there. This development task did not import or change any panel variable. The existing pending key file remains private staging; do not delete it until the approved activation and backup/recovery review are complete.

## Python 3.14 findings

The actual SFTP filesystem contains installed package metadata under `/.local/lib/python3.14/site-packages/` for discord.py 2.7.1, aiohttp 3.14.5, cryptography 50.0.2, cffi 2.1.1, audioop-lts 0.2.2 and the pinned runtime dependencies. Downloaded WHEEL metadata establishes:

| Package | Installed Linux wheel evidence |
| --- | --- |
| aiohttp | CPython 3.14, manylinux x86_64 |
| cffi | CPython 3.14, manylinux x86_64 |
| cryptography | CPython 3.11+ stable ABI, manylinux x86_64 |
| audioop-lts | CPython 3.13+ stable ABI, manylinux x86_64 |

All pinned packages' public Requires-Python metadata permits Python 3.14. discord.py declares audioop-lts for Python >=3.13, and it is already installed here. No version upgrade/downgrade or dependency installation is presently indicated. [discord.py metadata](https://pypi.org/pypi/discord.py/2.7.1/json), [aiohttp metadata](https://pypi.org/pypi/aiohttp/3.14.5/json), [cryptography metadata](https://pypi.org/pypi/cryptography/50.0.2/json).

The checkout's `.python-version` still says 3.12.14; that file is not evidence that the Apollo image uses 3.12. User-provided runtime information plus installed native cp314 wheels support Python 3.14. SFTP-only access cannot execute `python --version`, `pip check` or an import test in the running container. No full test suite or extra Windows setup testing was run. There is no observed Python 3.14 package blocker, but no new host runtime execution was claimed.

## Database preview and exact future activation sequence

The existing configuration tool was executed in read-only preview mode using the privately downloaded bootstrap environment. Its result was:

```json
{
  "applied": false,
  "add_column": false,
  "changed_keys": ["realms"],
  "prefix_changed": false,
  "requires_replace_existing": true
}
```

An additional read-only query confirmed that the current CoastalOPTeam value matches the role supplied by the owner and the guild matches the verified pilot. No role ID, guild ID or token was added to the private Realm block. The database currently has no Realm block. The exact existing guild-only sync command is `%sync 305767872410419211`.

After explicit deployment approval:

1. Confirm the in-container path is `/home/container/.captain-realms-private/tokens` under the checkout and verify ownership is the running application's UID. Existing staged directories report 0700/files 0600. Keep one writer process and the whole private directory ignored/untracked. Do not run the Windows diagnostic against an independently copied record once the server becomes the writer.
2. Provision the three keys from the existing private pending fragment through Apollo's process Environment Variables, or merge them into the active `.env` while preserving all existing values. Keep STORE_DIR as above, KEY_ID as `key-one`, and use the exact existing secret key map. Do not generate another key. If choosing `.env`, use mode 0600 under the application owner. Existing `main.py` loads the root `.env`, so no bootstrap allowlist change is needed.
3. Release the reviewed `codex/realms-phase3` changes, including this storage fix and its `.gitignore` rule. Control startup/CI deliberately: merging to main currently triggers the production deployment workflow and restart. Do not merge first and assume it is a staging-only operation. Preserve `.captain-realms-private/` during all file synchronization; do not use a cleanup operation that deletes ignored files.
4. Re-run the existing configuration-tool preview from Phase 3 source using the prepared `realms.settings.json` values with `enabled` changed to true in memory. It must still show only `realms` changing. Verify an independent backup; then apply with the existing tool's `--apply --backup-verified --replace-existing` flags. Do not edit the seed, replace the entire botdata JSON or change CoastalOPTeam. The staged file remains false until this approved step.
5. Start/restart the bot only after code, environment and approved database settings agree. A first `/realm` read performs authentication refresh on demand; startup does not initiate interactive login or background polling. If credentials have been revoked since the pilot, stop and arrange an operator-approved reauthentication; do not generate replacements automatically.
6. As an existing authorized bot administrator in Coastal Craft, run `%sync 305767872410419211`. Do not use `%sync all` or `%sync global`. Test `/realm status`, `/realm players`, then `/realm refresh` as an OP Team member, and confirm a non-member receives an ephemeral denial.

These are queued activation steps, not actions performed. Because Apollo exposes SFTP rather than a shell, any runtime command needs an approved execution channel; it cannot be sent as an SSH exec command through this endpoint. Production `.env`, database state, code and bot process remain unchanged by this preparation.

The storage code blocker is resolved on the development branch. Remaining work is approved release/activation and the host ownership/runtime check, not credential regeneration. SFTP alone cannot execute migration/sync commands; the existing approved database administration/deployment channel and a Discord administrator must perform those activation actions. No full test suite or live authentication is required for this storage-policy change.

## Focused verification of the storage adjustment

November 3, 2026: **27 tests passed, 1 POSIX-specific test skipped on Windows** in 54.13 seconds. The focused run covered the new path policy with temporary Git repositories plus the existing encrypted-store compatibility tests: designated ignored/untracked directory allowed; all other in-checkout paths denied; tracked private files, removed ignore protection, unsafe parent permissions and failed Git rejected; encryption/rotation/locking retained; external Windows stores still need no Git. Tests used synthetic data only. Ruff F checks, compilation and diff whitespace checks passed. No real credential record, key, active `.env`, production database or server code was modified by this development change.
