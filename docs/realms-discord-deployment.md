# Phase 3: private Discord Realm commands

Development branch: `codex/realms-phase3`, based on the live-verified Phase 2 branch. No deployment, main merge, production database update or Discord command sync has been performed.

## Commands and permission policy

`/realm status`, `/realm players` and `/realm refresh` are registered only in the database-configured `Coastal` guild. Each invocation checks the current interaction's guild and member role IDs against `bot.settings['Coastal']` and `bot.settings['CoastalOPTeam']`, which are loaded from `botdata` using the existing startup path. Role names, OPTeamRole, Discord administrator privileges and bot/auth-owner IDs do not bypass this check. No role ID is hardcoded or supplied by a second configuration source. As with existing bot settings, database changes require a restart to reload; member roles are checked on each invocation, with access checked again before returning data.

Authorized interactions defer immediately and reply ephemerally. Denials and failures are also ephemeral. API-supplied names are escaped, mentions are suppressed, and XUIDs, credentials, invite links and raw response bodies are never sent to Discord. The Realm commands bypass the old global avatar restriction so that it cannot produce a public denial before their private policy check; other commands retain their behavior.

- **status:** Realm name, OPEN/CLOSED state and latest successful status timestamp. Failed reads show unavailable state with any older successful state explicitly marked stale.
- **players:** selected-Realm activity and its own successful observation timestamp. Only explicitly online records count as known online; absent online flags are labeled unknown. Display names appear only when actually supplied by the API; no Xbox lookup or guessed Discord identity is added. Missing Realm activity or an API error is unknown, while a successful empty player array is zero.
- **refresh:** fresh read-only details/activity observations, subject to a shared 30-second minimum between attempts. Ordinary status/players reads reuse a 60-second cache. Concurrent requests share observations. Upstream Retry-After delays also block subsequent commands/endpoint calls. These are demand-driven reads, with no background polling or automatic login.

The 45-second observation deadline is after the interaction has been deferred. Missing credentials, refresh revocation, startup storage failure and API exceptions leave Realm data unavailable without preventing unrelated Captain features from starting. Errors log only exception type, not messages/bodies. Shutdown/unload cancels in-flight observations and closes the existing Phase 2 service, aiohttp session and writer lock.

## Deployment configuration — approval required before applying

1. **Host secrets/storage:** provision a persistent private directory outside source checkout/deployment sync. Supply these process environment values through the bot host's secret facility, not Git:

   | Variable | Purpose |
   | --- | --- |
   | `CAPTAIN_REALMS_STORE_DIR` | Absolute persistent private token-directory path |
   | `CAPTAIN_REALMS_KEY_ID` | Active key ID matching the existing cache/key map |
   | `CAPTAIN_REALMS_KEYS` | JSON key-ID → Fernet-key map, injected privately |

   Existing encryption, path/ACL checks, single-writer lock, token rotation and Microsoft/Xbox refresh implementation are reused. The one supported in-checkout exception is `<checkout>/.captain-realms-private/tokens`, requiring a private parent and the whole folder ignored/untracked; all other in-checkout locations remain prohibited. See [Apollo preparation](realms-apollo-preparation.md). Do not put keys or tokens into botdata or environment command arguments. No Windows DPAPI decryption happens inside the bot.

2. **Same existing database settings JSON:** add one optional `realms` block to `botdata.settings_json` row 1, under `settings`. No new database tables/columns, schema-version bump, seed replacement or second role/guild source is required. Existing documents without this key remain valid and disabled. Prepare the following values privately, preserving the rest of the existing document:

   ```json
   {
     "enabled": false,
     "client_id": "CAPTAIN_OWNED_APP_GUID",
     "auth_owner_ids": [123456789012345678],
     "account_ref": "SAME_ACCOUNT_REF_AS_PHASE_2",
     "expected_gamertag": "DESIGNATED_TEST_ACCOUNT_GAMERTAG",
     "client_version": "VALIDATED_STABLE_BEDROCK_VERSION",
     "selected_realm_id": "SELECTED_DISCOVERED_REALM_ID"
   }
   ```

   This is a schematic template: substitute the validated private values. The IDs/names above are placeholders. Do **not** add `guild_id` or `CoastalOPTeam` inside this block; those come exclusively from the existing canonical database settings. Auth owner IDs are the narrow Phase 2 credential-operator allowlist, not the list of OP Team members. The bot performs delegated reads through that internal service identity; OP Team commands do not initiate or own OAuth sessions.

3. The existing `migrations.botdata_settings` preview/apply tool now permits adding/updating this optional key with `--set realms --value '<private JSON object>'`. Preview first, retain an independent backup, then apply only after deployment approval using the existing `--apply --backup-verified --replace-existing` gates. Because the block is non-secret, its private file can be loaded into an operator shell variable for the JSON argument; do not pass secret key/token material. Adding this key preserves every unrelated setting, including CoastalOPTeam. Disabling uses the same tool with the block's `enabled` set false; do not reset to the seed document, which may discard existing settings.

4. After host credential provisioning is approved, set `enabled: true` in that database block and restart only the approved bot host. There is no automatic interactive login at startup. Enabled configuration requires all operational fields plus a selected Realm; disabled/absent configuration loads no Realm cog, credential store or session. Missing host secrets for enabled mode keep the cog available to return unavailable information; fix provisioning and restart/reload it.

5. The extension uses Captain's existing cog registration/lifecycle and existing administrator sync command. After approval, sync only the configured Coastal guild using the existing `%sync <guild-id>` style (substitute the actual configured prefix). Do not globally sync or add the Realm group to PBtest. Revoking the feature means disabling the block, restarting, then syncing the guild to remove the remote commands; merely removing local commands does not remove already registered Discord commands.

## Can the tested credentials be reused on the actual bot host?

**The encrypted token record is portable with the same Fernet key, client ID, account_ref, scope/authority binding and verified account. The Windows DPAPI-wrapped key file is not a portable key source.**

On the exact same Windows machine and Windows identity, an approved private launcher may unwrap the existing DPAPI key and inject the process-scoped key map before starting the bot, using the Phase 2 private setup procedure. Do not run the CLI and bot against the same token directory at the same time: the single-writer lock deliberately refuses that.

On a different machine/Windows identity or a Linux/container host, copying `key-one.dpapi` will not work. An authorized operator must securely transfer the existing Fernet key through the hosting secret manager and transfer only `account.realms.enc` into a persistent token directory. Do not copy `writer.lock`, stale rotation files or plaintext token exports. Preserve encrypted-file contents/binding, set Linux directory/file ownership to the bot service UID and modes 0700/0600 (or restrictive Windows ACLs), and ensure a single bot instance owns the store. Protect the parent directory and backup/recovery path too. The host can then refresh credentials without passwords or a new interactive login if the refresh token is still valid; revoked credentials require an operator's separately approved Phase 2 reauthentication.

The actual bot host's OS, persistent mount and secret-injection readiness were not remotely inspected in Phase 3. Therefore host credential reuse is **conditional**, not already provisioned or deployed. Never upload the DPAPI blob as if it were the Fernet key, place a key beside the cache, or use the primary Realm owner's account as a fallback.

## Verification and remaining gates

Focused offline tests cover command permission denial, role changes, private replies, prompt deferral, missing names, zero/unknown/stale observations, bounded output, cooldown/cache sharing, long Retry-After handling, revoked credentials, startup/partial cleanup, actual discord.py guild registration and Bot.close unloading. They also exercise optional-key persistence through the existing SQLite-backed config tool, verifying unchanged columns and preserved CoastalOPTeam. Existing Phase 2 service/client/policy tests are included; unrelated Windows store tests and the full repository suite are not repeated.

No live Discord command was invoked or synced. Remaining deployment gates are host credential/secret provisioning, operator review of the database block, approved restart and guild-only sync, then a Discord smoke test with an OP Team member plus a denied non-member. There are no Realm management endpoints or scheduled tasks in this change.

Verification on November 3, 2026: **134 focused tests passed** (1.78 seconds), with one existing upstream audioop deprecation warning. Ruff F checks, compilation of changed Python paths and diff whitespace checks passed. No new dependencies were installed; Python 3.12 and discord.py 2.7.1 remain unchanged.
# Phase 4 follow-up

The development-only live panel, encrypted observed-session durations, management
commands and activation steps are documented in [realms-live-panel.md](realms-live-panel.md).
Phase 4 requires separate release approval; existing Phase 3 credentials are reused.

