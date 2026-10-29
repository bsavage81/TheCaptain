# Database-backed Captain configuration

**Live status:** the settings and registry migrations have now been applied and verified
against the owner's MariaDB database. See [execution evidence](settings-registry-migration-execution.md).

This supersedes the old botconfig.json-plus-constants startup instructions. Operational
configuration is stored on **botdata row 1**, in a versioned `settings_json` LONGTEXT
column (TEXT for offline SQLite tests). Existing `prefix` remains authoritative in its
SQL column; it is not duplicated in JSON. The five original typed model fields, every
administrator row and the old settings archive are preserved.

## Sources of truth

| Data | Location |
| --- | --- |
| Command prefix | `botdata.prefix`, row 1 |
| Coastal guide command destination | `botdata.bot_spam_channel_coastal`, row 1; verified Coastal channel `415213466522091542` |
| Guild/channel/role IDs, owner IDs, Sheets IDs/titles, guide settings, logo, realm label, profile/check-in flags and timing | `botdata.settings_json.settings`, row 1 |
| Unused server config keys, including Aurafall IDs and old BotID/ServerID aliases | `botdata.settings_json.legacy_settings`, row 1; retained for reference, not runtime routing |
| Discord token and database connection/SSL parameters | Existing environment / private `.env` |
| Google service-account private key | Existing private `creds.json`; only its path is a database setting |

`main()` loads only bootstrap environment values. Database initialization validates and
loads the operational document before Sheets connects or extensions register. Missing,
unsupported or incomplete database settings stop startup with no JSON-file/constant
fallback and without seeding a default administrator. After configuration is valid, the
existing empty-administrator owner-seeding behavior uses the database's `owner_ids`.

The existing constants and explicit `load_settings(path, ...)` converter remain for legacy
compatibility/tests. They do not supply the production runtime's operational settings.
Strict database mode requires guide values and sheet selections rather than using these
fallbacks. `realm_name` from the database controls guide messages. Current settings are
loaded at startup; restart the bot after changing them. There is no background settings reload.

`config/botdata-settings.seed.json` is a **one-time migration input**, not a runtime config
file. It includes every non-secret value supplied from the server configuration, the
owner-confirmed Season 10 defaults for omitted fields, both supplied check-in channel IDs,
and inactive role `547138462357258242`. All new activation flags remain false. The
obsolete `botconfig.example.json` has been removed so it cannot suggest a second runtime
source. Editing a seed after import does not change database settings.

Typed columns `bot_id`, `bot_spam_channel_coastal`, `server_id_coastal` retain their
verified historical values. Their meanings are not inferred from ambiguous old JSON aliases
such as `ServerID`/`ServerID2` (the supplied values point to the test guild). Active routing
uses explicit named operational keys. The guide announcement specifically uses the typed
`bot_spam_channel_coastal` field, which is loaded into runtime settings without duplicating
its value in the JSON document. The generic legacy `botspamChannel` and MRP's `CoastalMRP`
are different destinations and must never be substituted for Coastal's bot command channel.

## Initial migration

Use the existing database environment on the bot's server. Token/Google credentials are
not needed by the migration. Stop writers in the maintenance window, take an independent
consistent database backup, and verify it restores into an isolated database. Keep the
original server botconfig.json privately for rollback; this migration never edits it.

Preview using the owner-reviewed seed:

```shell
python -m migrations.botdata_settings
```

Or preview import of the server's current file (explicit values override the seed):

```shell
python -m migrations.botdata_settings --config botconfig.json
```

After review/approval and verified backup:

```shell
python -m migrations.botdata_settings --config botconfig.json --apply --backup-verified
```

Omit `--config botconfig.json` to import the reviewed seed instead. The existing database
prefix is preserved unless an imported flat file explicitly requests another value.
The supplied server prefix `%` is already the documented production prefix. The migration
only adds nullable `settings_json` and populates row 1; no tables/columns are removed.
It refuses to create/guess a missing production row and requires InnoDB for MySQL/MariaDB.
Preview output lists keys/hash/counts, never settings values or credential contents.
Known token/database keys from an old flat input are filtered out of the stored document.
Unknown keys and retired BETA configurations require review rather than silent import.

Existing different settings or a different requested prefix require an additional explicit
`--replace-existing`. Preview first: it reports the changed key names and replacement need.
Identical repeat imports are no-ops and do not require another backup assertion. DDL may
auto-commit on MySQL/MariaDB; an interrupted nullable-column addition can safely be retried.
The data update is transactional and compares the previous document and prefix to avoid
overwriting concurrent edits (binary comparisons on MySQL avoid collation ambiguities).

Apply this migration **before merging/restarting the database-configured runtime**. The
older runtime ignores the extra column on a healthy existing row, allowing migration before
code rollout. The new runtime deliberately stops if the document is missing. GitHub main
currently triggers a panel restart; coordinate merge with this prerequisite.

## Later settings changes

Use the database operator account through the CLI, or an authorized database admin tool.
Do not update botconfig.json, constants or the seed to configure the running deployment.
For example, preview a single key without creating another settings file:

```shell
python -m migrations.botdata_settings --set checkin_channel_id --value 504140612019421184
```

After reviewing the preview and verifying a current independent backup:

```shell
python -m migrations.botdata_settings --set checkin_channel_id --value 504140612019421184 --replace-existing --apply --backup-verified
```

`--value` is a JSON value: booleans use `true`/`false`, IDs are integers, strings must be
properly shell-quoted JSON strings, and nullable settings use `null`. Unsupported keys,
invalid types or incompatible schema versions are rejected. Prefix changes use the existing
prefix column or an explicit flat-file import; there is no duplicate JSON prefix setting.
The migration does not post Discord messages or start scheduled tasks. Enabling flags takes
effect on the next bot restart and still requires profile table preparation and owner approval.

## Recovery and rollback

- Interrupted column creation: rerun preview and apply after inspecting the nullable column.
- Wrong settings update: restore the backed-up versioned document through the same migration
  with `--config <private-backup-document>` and explicit replacement after review. Retain the
  original SQL prefix separately; a full independent database backup includes both.
- Code rollback: stop the new bot, retain the additive settings column and all registry history,
  restore the old runtime and its saved private JSON/environment. Do not drop new tables.
- Do not rerun old destructive/rename cleanup workflows against the consolidated schema.
  Their strict schema checks intentionally refuse the extra column; any future cleanup needs
  a separate reviewed migration that preserves this document.

The live settings and registry migrations were subsequently executed using the privately
provided existing `.env`; backup restoration, unchanged original data and the runtime database
initializer were verified. See the execution report above. Full bot readiness and Google/Discord
delivery remain server checks; no historical import or messaging was performed.

Validation: 171 offline tests passed on the exact committed release, including 23 new
database configuration tests. Ruff F checks and compilation passed. The existing private
server `.env` remains the database connection source; the owner subsequently provided a private
local copy for the authorized migration. It is Git-ignored and was never committed.
