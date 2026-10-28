# Historical report — prior modernization

# Offline validation report

Completed October 27, 2026 (America/Chicago), on Windows with CPython 3.12.14.

- Remote public main/dev heads match both supplied snapshots; no fetch/merge/push occurred.
- Structural moves recorded independently before initialization and feature behavior repairs.
- Conservative dependency baseline: 17 tests passed before upgrades.
- Selected upgraded runtime: original 17 tests passed; expanded suite subsequently passed.
- Final clean virtual environment installed only from `requirements-dev.txt`: **32 tests passed**.
- `python -m compileall -q main.py utils tests`: passed.
- `pip check` in the clean environment: no broken requirements.
- `pip-audit 2.10.1 -r requirements-dev.txt --no-deps --disable-pip`: no known vulnerabilities;
  machine-readable result retained in `dependency-audit.json`. Public advisory lookup required
  network access; no bot service was contacted. Earlier pytest advisory was resolved before final audit.
- `git diff --check`: passed.
- PortalBot working tree remains unchanged.

Tests cover safe imports without configuration/credentials; fresh/existing STABLE and BETA bootstrap;
legacy field names; deterministic registration without command syncing; every End command and
coordinate option; MRP channel scope; OP Team name/ID permissions; inherited tier-3 sync check;
injected owner checks; all three application pages and ownership; temporary view lifetime;
long modal titles; complete application/POI row builders; lazy Sheet initialization/titles/worksheets;
concurrent max+1 inserts; application status row re-resolution; worker thread execution and cancellation
serialization; guide corrected answers, conversation ownership and all timeout phases; POI timeout and
overlap rejection; failed inserts without automatic retry; saved application/decision delivery failures.

External socket connections are blocked by an autouse test fixture. Loopback is allowed for Windows
asyncio's internal socketpair. The desktop sandbox restricted that loopback, so executable test runs
used an elevated local tool context while the fixture continued blocking external connections.
No production token, credentials, database or spreadsheet was read or needed for these checks.
All synthetic SQLite databases and virtual environments are ignored by Git.

One upstream warning remains: discord.py imports Python's deprecated `audioop` on Python 3.12.
Python 3.13+ compatibility was not claimed or tested. Hosted Windows/Linux CI has been authored but
not run on GitHub. MySQL server behavior, Discord deliveries/scope enforcement, actual service-account
permissions, Sheet formatting/formulas, and current Season 9 content require staging validation.
See `staging.md` for concrete validation and rollback steps; `baseline.md` states concurrency and
partial-failure limitations. No deployment, merge, production command sync or live Discord messaging
was performed.
