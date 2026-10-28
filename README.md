# TheCaptain

Separately configured Coastal Craft bot, including Coastal applications in Realm Portal.
PortalBot is an architectural reference only. Captain retains its own database and Sheets contracts.

## Installation and offline checks

Tested locally with CPython 3.12.14 on Windows. CI targets Python 3.12 on Windows and Linux.
Use a separate virtual environment, then install the complete pinned dependency closure:

```shell
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux: source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pip check
python -m compileall -q main.py utils tests
python -m pytest -q
```

For runtime only, install `requirements.txt`. `requirements.in` inventories direct dependencies.
Tests use synthetic Discord/Sheets objects and temporary SQLite databases; they block external
connections and need no credentials. Windows asyncio requires local loopback socketpairs.
Never point test configuration at a live database or Sheet.

## Configuration and startup

Copy `botconfig.example.json` to `botconfig.json` and `.env.example` to `.env` beside `main.py`.
Replace every zero with the intended guild/channel/role ID. Keep `creds.json` private; share only
staging spreadsheets with the staging service account. Relative configuration and credential paths
resolve from the repository root, independently of the current directory. The service account must
have the existing Sheets/Drive scopes. The bot needs members/message-content intents for legacy
member lookups and conversational commands, plus suitable channel permissions and role hierarchy.

The existing lower-case `token`, `bot_type`, and `database_*` environment keys remain supported;
environment values override JSON for these keys. `bot_type` is exactly `STABLE` (row 1) or `BETA`
(row 2); default is STABLE. Existing BotData row values are preserved. New rows use Captain model
defaults. Owners are seeded only when Administrators is empty; `owner_ids` defaults to the legacy
owner. Never rely on Discord application owner IDs before login. Admin/owner queries run off-loop.

`OPTeamRole` defaults to the existing role **name** `OP Team`; an integer opts into checking a role
ID in the invoking guild. `CoastalOPTeam` remains the Coastal notification role ID. The four new
Coastal guide/invite keys default to the legacy IDs shown in the example; override all four for
staging. `MRP`, `PBtest`, `Coastal`, `CoastalMRP`, `CoastalApplications`, `CoastalMapUpdates`, and
`CoastalOPTeam` keep their existing meanings. Unknown legacy JSON keys are tolerated.

Run `python /absolute/path/to/TheCaptain/main.py` only after reviewing staging configuration.
Startup explicitly initializes the database, bootstraps the selected row, loads Sheets metadata in
a worker, and registers six extensions in fixed order. It never syncs commands automatically.
The existing tier-3 `sync <guild|global|all>` prefix command remains an explicit operator action;
use only a staging guild during validation. Jishaku remains owner-only upstream functionality.

Inherited Flask hooks, public traceback gists, question suggestions, pygit2 version reporting,
and Flask/Sentry wiring were removed after active dependency tracing. There is no HTTP server.
`sentry_dsn` is tolerated but does not enable telemetry; introducing sanitized telemetry is a
separate change. Legacy archived features and images are preserved and excluded from loading.
No current feature needs a persistent view: application/start/continue views and modals expire
after five minutes and lose their state on restart. The old BotData `persistent_views` column
is retained for schema compatibility and no longer controls process registration.

## Review, staging and rollback

See [file mapping](docs/file-mapping.md), [baseline and contracts](docs/baseline.md),
[dependency review](docs/dependencies.md), [offline validation report](docs/validation.md),
and the [staging/rollback checklist](docs/staging.md).
The single-writer and partial-failure limitations in those documents are deployment requirements.
No deployment or live Discord/MySQL/Sheets validation was performed as part of this refactor.
