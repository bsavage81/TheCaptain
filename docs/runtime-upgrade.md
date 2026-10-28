# Current Python and Peewee target — October 28, 2026

Target: Python **3.15.2** and Peewee **4.5.3**, the latest stable releases checked against
[Python.org](https://www.python.org/downloads/release/python-3152/) and the
[Peewee release](https://github.com/coleifer/peewee/releases/tag/4.5.3).
Python 3.14 remains in the compatibility CI matrix for the current hosting image; use its latest
patch if the host has not yet made Python 3.15 available. No downgrade to 3.12 is required.

## Changes

- .python-version selects 3.15.2; requirements.in/requirements.txt pin Peewee 4.5.3.
- audioop-lts 0.2.2 is explicitly pinned for Python >=3.13, matching discord.py's dependency
  after stdlib audioop removal. Voice remains unused; the separate voice-support warning is not fatal.
- Both runtime model table names are explicit: botdata and administrators. Existing ID, prefix,
  Coastal identifiers, case-sensitive column spelling, records and schema contracts are unchanged.
  This upgrade executes no database migration or production writes.
- CI runs all tests, compilation and Ruff on Python 3.14/3.15, Windows/Linux. Security audit targets
  Python 3.15. Existing main-only panel restart workflow is unchanged.
- [Peewee's changelog](https://github.com/coleifer/peewee/blob/master/CHANGELOG.md) was reviewed:
  MySQL now leaves server sql_mode intact and defaults charset to utf8mb4 (Captain already specifies
  utf8mb4). Captain does not depend on removed extensions or Postgres JSON/RETURNING behavior.

## Local evidence

Official Windows Python 3.15.2 embeddable runtime downloaded into Git-ignored .runtimes for isolated
validation; SHA-256 matched the checksum published by Python.org. No system Python/registry was
modified. Clean installation from requirements-dev.txt succeeded with Peewee 4.5.3 and CPython 3.15
wheels or pure-Python packages. Full suite: **86 passed**, 0 failed/skipped. Compilation, Ruff F
checks and pip check passed. Explicit schema/query tests cover the ORM upgrade. Upstream discord.py
emits 95 deprecation warnings for asyncio.iscoroutinefunction scheduled for removal in Python 3.16;
these do not fail Python 3.15 tests and no monkeypatch/suppression was introduced.
The refreshed dependency audit is saved in dependency-audit.json. Hosted four-way CI is tracked by
the upgrade PR; local results do not claim a Linux or Python 3.14 run until CI reports success.
No Discord, Google Sheets or live database credentials were used in these upgrade tests.

## Deployment settings remain separate

The supplied server log shows Python 3.14.0 and a certificate-verification crash. Set the actual
private .env or panel environment variable database_ssl_mode=self_signed for the previously
approved self-signed database certificate; panel environment values override .env. The .env.example
file is not loaded at runtime. Encryption remains enforced. Python/Peewee upgrades alone do not
change that setting or fix a wrong database target.

Select the latest stable Python 3.15 panel image, leave STARTUP_FILE=main.py and clear legacy
PY_PACKAGES so only the pinned requirements install. Otherwise the old startup package list may
upgrade packages before requirements.txt reinstalls pinned versions. .python-version is advisory
for tooling and does not switch the panel's Docker image. Do not overwrite private credentials,
production guild/role/channel mappings or the selected database when changing the runtime.

The old operational environment and previous Git revision should be preserved for rollback.
Restore code and matching dependencies together; no database schema reversal is needed for this
ORM/runtime upgrade. Main has an owner-configured restart-on-push workflow, so this work is kept
on a separate PR branch until an explicitly approved merge/deployment.
