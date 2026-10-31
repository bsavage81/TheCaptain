# The Captain — Coastal Craft Season 10

The Captain is a standalone bot for **Coastal Craft Season 10: The Mighty Mesa Reborn**.
It handles Coastal applications in the Realm Portal community and keeps its own service account,
configuration, database and deployment. PortalBot is a read-only architectural reference.
There is one production bot. Git development branches do not select different bots or database rows.

The optional [Google Sites application portal](docs/application-web-portal.md) uses the existing
question/response schema and bot review flow. Its Apps Script source is in `apps_script/coastal_application`.
Enable it with the same private `APPLICATION_WEB_SECRET` configured in Apps Script; the deployed
Coastal form URL and private inbox ID are included as defaults.

Player profiles and monthly check-ins are implemented as **disabled-by-default** features.
See the [registry, historical import and check-in runbook](docs/player-registry.md) for the
additive migration, inspected Season 3–10 sources, identity review commands, eligibility rules,
configuration and recovery. Production migration, historical imports, announcements and reminders
require explicit owner/administrator approval before use. Startup never creates registry tables.

## Install and test locally

OP Team members can use `/post` to write a multiline message as The Captain. Choose an
optional destination text channel, or post in the current channel. The command requires
both the author and bot to have access to send there. Confirmation is private; mentions
in the post can notify users, roles, and everyone, subject to Discord permissions. After deployment, use the existing
administrator `%sync all` command to register the new slash command.

Tested runtime: CPython 3.12.14. CI runs on Python 3.12 on Windows and Linux.

```shell
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux: source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pip check
python -m compileall -q main.py utils migrations tests
python -m ruff check --select F main.py utils migrations tests
python -m pytest -q
```

For runtime only, install `requirements.txt`. No Discord, MySQL or Google credentials are needed
for tests. Tests block external connections, use synthetic data and temporary SQLite databases,
and allow loopback only for Windows asyncio internals. Never use production data as fixtures.

## Private production configuration

Operational settings now live in **botdata row 1**, with the existing SQL `prefix` column and
a versioned `settings_json` document. Follow the [database configuration migration runbook](docs/database-configuration.md)
**before merging or restarting this runtime**. Its reviewed seed contains the exact server values
supplied by the owner; explicit import of the server's existing `botconfig.json` preserves overrides.
Preview first, verify an independent backup, then apply explicitly. Existing different database
settings require explicit replacement. The source JSON file is never modified.

Keep lower-case `token` and `database_*` bootstrap keys in the existing private environment or
`.env` (see `.env.example`), and preserve private `creds.json`. These secrets are not stored in
the settings document. Startup does not read botconfig.json or fall back to operational constants;
missing/incomplete database configuration fails closed. Editing the one-time migration seed does
not configure a running bot. Future changes use the database or the migration CLI's `--set` mode.
For the new owner-approved MariaDB connection use `database_ssl_mode=self_signed`: encryption is
required, while the provider's self-signed certificate is accepted explicitly. The code defaults to
`verify_identity` if this setting is absent; `database_ssl_ca` optionally supplies a provider CA path.
Startup reads `botdata` row **1**. Remove `bot_type` from the production
environment. A legacy `STABLE` value is tolerated and discarded; any other value is rejected,
so a retired BETA instance cannot silently become another production writer. Nothing in this
repository stops either currently running bot; retirement and rollout require operator action.

Required operational IDs include `MRP`, `Coastal`, `CoastalMRP`, `CoastalApplications`, `CoastalOPTeam`,
`CoastalMapUpdates`. `MRP`/`CoastalMRP` are still required for applications in Realm Portal.
`PBtest` is an optional existing guild scope, not another deployment: set it to null when unused or retain
its current ID to preserve command availability. `OPTeamRole` retains the `OP Team` name check;
an integer opts into a role-ID check. Notification roles use `CoastalOPTeam` separately.
The settings seed preserves the server's supplied guide/invite IDs, including guide role
`1565125349044527184`. Unused old server settings are retained under `legacy_settings`.

## Season 10 Sheets and service account

Use the existing private `creds.json` for:
`thecaptain@thecaptain-513018.iam.gserviceaccount.com`.
Both production files have already been shared with that account, per the owner. Enable the
required Google Sheets/Drive APIs and preserve the existing scopes. No credentials are created,
replaced or stored in this repository. Startup rejects another service account before authorization.
The supplied file is read only during explicit startup, never during imports or offline tests.

```json
{
  "credentials_path": "creds.json",
  "application_sheet": "CCS10 Realm Application",
  "markers_sheet": "Coastal Markers S10",
  "application_sheet_id": "1ltMnItNgDBk5FhgsC-afi0l17OBnfOTcKPIkcSw9zvE",
  "markers_sheet_id": "11xN9e9hXOsj0oBlrVYHxPFEJJoWAzfBPRR-5bOk4Hy8"
}
```

These are operational database settings. By title, use explicit accessible file titles. Duplicate accessible
titles may be ambiguous. Prefer keys when available: set `application_sheet_id` and/or
`markers_sheet_id` to the actual key from `/spreadsheets/d/<key>/...`. A nonempty key uses
`open_by_key()` and takes precedence over the title for that file. No spreadsheet IDs are invented.
Relative credential paths resolve from the repository root, independently of the launch directory.

Applications use the first worksheet: row 1 metadata, row 2 question labels, applicant insertion
at row 3. Markers use `Overworld`, `Nether`, `End`, `Questions`; prompts remain `Questions!B1:B6`,
marker insertion remains row 2. Existing column order and Yes/No approval statuses are unchanged.
Startup validates worksheet access and question labels without writing any Sheet data. Failures
are sanitized so Google responses or credential contents are not printed in error messages.
Exactly one bot process may write these files. The in-process lock is not a distributed lock;
uncertain writes and failed notifications still require operator reconciliation.

## Season 10 guide and logo

Defaults are the owner-confirmed [web guide](https://docs.google.com/document/d/1FGK84rUyrC6LX0UrnW7IxzjupYPEbOCo7ccpQlSmvu8/edit?usp=drive_link)
and [PDF guide](https://drive.google.com/file/d/1zMmjQTzZeEHUHgjxNZsNnGe9ubw-3QCW/view?usp=drive_link).
Question: **Who knows?** Accepted keyword: **armadillo**, anywhere in the response,
case-insensitively (for example, “The Armadillo knows”). This deliberately follows the owner's
loose-acceptance instruction. Existing retries, timeouts, ownership and role checks remain.
The default logo is the owner's replacement Discord CDN image, configured in `logo_url`.

Override `guide_web_url`, `guide_pdf_url`, `guide_question`, `guide_answer`, `guide_answer_match`
(`contains` or `exact`) and `logo_url` in the database settings as needed. To source guide values from the Season 10
markers `Questions` worksheet, set `guide_cells` to an object mapping any of `web_url`, `pdf_url`,
`question`, `answer` to owner-verified uppercase A1 addresses. These cells override the corresponding
database values. No guide cells are assumed: B1:B6 belongs to POI prompts. At least one guide
link, a question and an answer are required; explicitly blank/missing content produces a clear
operator-configuration response without assigning roles. No old Season 9 links or logo remain active.

## Database preparation and startup

Review [database inventory and migration](docs/database-audit.md) first. The runtime model keeps production `botdata.id`, `prefix`, `bot_id`, `bot_spam_channel_coastal`,
`server_id_coastal`, and the administrator table.
The explicit cleanup archives all original settings rows/columns for rollback and never deletes
administrator records. Startup
performs no table/schema DDL. For a fresh database, the explicit additive migration must be reviewed
and run by an operator; existing healthy production data needs no physical migration:

```shell
python -m migrations.single_production
# Read-only metadata/preflight by default. Only after backup and approval:
python -m migrations.single_production --apply
```

The tool reads database environment keys from the root `.env`, prints schema/row-presence metadata
only, and never deletes, drops, alters or copies a retired row into production. An existing nonempty
`botdata` table missing row 1 fails for owner-reviewed restoration. `--apply` only creates missing
Captain tables and bootstraps a default row 1 in a fresh/empty table. It does not grant permissions.
Runtime retains configured owner seeding only when Administrators is empty.

For an existing legacy settings table, preview `python -m migrations.cleanup_botdata`. After a verified
independent backup, confirmed exclusive database ownership and an approved maintenance window,
explicitly apply with `--apply --maintenance-window --exclusive-database --backup-verified`.
The full old table becomes `captain_botdata_legacy`; production row-1 prefix and the three Coastal identifiers remain active. Use the same
command with `--rollback` to preview restoration; explicit rollback preserves current clean data in
`captain_botdata_clean_rollback`. No unknown tables, administrator records or historical values
are dropped. See the database runbook before code rollout: the older runtime needs the legacy schema.


After approved configuration review, start `python /absolute/path/to/TheCaptain/main.py`.
Database and Sheets initialization are explicit; extensions register once in a fixed order.
On ready, the console prints Captain's ASCII banner with the live account/wrapper version, current
Git commit, configured database host, server-local time and cached guild/member counts. Missing
Git metadata displays unknown without blocking readiness; database credentials are never printed.
There is no automatic slash-command sync. Tier-3 manual `sync <guild|global|all>` and upstream
owner-only jishaku are preserved. Application views/modals expire in five minutes and lose state
on restart; the retained `persistent_views` database field no longer drives registration.
Main pushes now use the existing panel secrets for a checked restart and verify the actual
server commit, guide source and ready-banner revision. See [deployment verification](docs/deployment-verification.md).

## Review and rollout

See [Season 10 discovery](docs/season10-discovery.md), [database audit](docs/database-audit.md),
[file mapping](docs/file-mapping.md), [validation](docs/validation.md), and
[deployment verification and rollback](docs/staging.md). Historical contracts and prior reports
are explicitly labelled as history. Archive source remains unchanged and never loads.
The new MariaDB settings cleanup and runtime initialization/permissions were verified live; see
[execution report](docs/database-cleanup-execution.md). The original database was unchanged.
No Discord/Sheets access, deployment, PR merge, bot retirement or running-bot restart was performed.

The owner-requested bot/Coastal identifiers have been restored to the new database from the exact
original production row. For an earlier two-column cleanup, preview
`python -m migrations.restore_coastal_ids`, then explicitly use `--apply` to restore missing fields
from captain_botdata_legacy. Existing differing values are never overwritten. These retained IDs do
not silently replace the named operational guild/channel mappings in the new settings document.
