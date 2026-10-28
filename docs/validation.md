# Season 10 offline validation — October 28, 2026

Base: latest main `646413257f0a8670dad9e3611c9fab2d8e689108`. Dedicated branch:
`maintenance/season10-consolidation`. Tested on Windows, CPython 3.12.14.

| Check | Exact result |
| --- | --- |
| Latest-main baseline pytest | 31 passed, 1 failed (old Season 9 title expectation after owner's main change) |
| Final pytest | **77 passed**, 0 failed, 0 skipped; 1 upstream audioop deprecation warning |
| Compilation: main.py utils migrations tests | Passed |
| Ruff 0.17.3, select F, active source/migrations/tests | Passed; initial 11 unused-import/extraneous-f-string findings fixed |
| pip check | No broken requirements |
| pip-audit 2.10.1, locked runtime/dev set | No known vulnerabilities; JSON in dependency-audit.json |
| git diff --check | Passed |
| Archive comparison against main | No changed files under !archive/ |
| Live Discord/MySQL/Google Sheets | Not run; no credentials used |
| Production migration / destructive SQL | Not run; none executed |
| Deployment / restart / BETA shutdown / merge | Not performed |

The suite retains application page progression/ownership, permissions, command registration,
application and decision storage contracts, all five POI row builders and concurrent inserts,
worker thread/cancellation serialization, guide retry/timeout ownership, and partial-failure checks.
New cases cover Season 10 title defaults, key precedence/mixed selection, inaccessible files,
all missing required marker worksheets, sanitized initialization and retry, dedicated-account
credential boundary without reading a credential file, cwd-independent path resolution,
optional test guild, retired-mode guard, production row-1 preservation, safe/repeatable migration,
missing-production-row refusal, no runtime DDL, startup without BETA/test-guild configuration,
no automatic sync, explicit guide cells, confirmed guide defaults and loose armadillo matching,
incomplete-guide refusal, and the owner's replacement Discord logo default.

Tests block external socket connections (loopback only for Windows asyncio) and use synthetic
Discord/Sheets objects plus temporary SQLite databases. The credential loader is mocked in tests;
no private creds.json, environment token or production database is needed or printed. Tests ran
outside the desktop sandbox only to allow Windows' local asyncio socketpair. The security audit
queried public advisory data separately; audit warnings recommend hashes for the pinned lock files.
Runtime dependency versions remain unchanged; Ruff is a development-only addition.

## Limits and manual verification

No live database contents/external consumers were inspected; database-audit.md is source-based.
SQLite tests do not prove MySQL auth/TLS, server DDL privileges, triggers or backup restoration.
No production rows or Sheets were read or changed. The production row-1 convention is confirmed
from source, not a live data assertion. Required metadata/columns are tested at fake boundaries;
real formulas, formatting and current share permissions remain operator checks.

The owner confirmed Season 10 guide links, “Who knows?”, armadillo substring acceptance and the
replacement Discord CDN logo. Link accessibility, logo retrieval/expiry, actual guild/channel IDs,
role hierarchy, notifications and command publication still need authorized manual verification.
The published CI workflow is maintained for Windows/Linux, but local Windows results alone do not
claim a hosted/Linux pass. Main still requires separate owner approval before merge/deployment.
No bot is terminated automatically and no global commands are synced at startup.

Historical modernization results are preserved in validation-2026-10-27.md. See staging.md for
single-deployment verification/rollback and database-audit.md for destructive items requiring approval.

## Database cleanup completion follow-up

The minimal runtime model and reversible cleanup/rollback were tested offline. New coverage verifies
all typed legacy rows/columns and production Unicode prefix survive archival and rollback; all
administrator records (including lower tiers) remain unchanged; repeated runs are safe; missing
operational declarations and unknown columns/FKs/views/triggers/indexes block writes; interrupted
copy/rename leaves recoverable state; and MySQL uses a single multi-table rename. A realistic fake
MySQL boundary returns tuples and tests atomic rename failure; SQLite exercises the full round trip.
Compilation and Ruff F checks pass. The unchanged dependency set retains the preceding clean audit.
No credentials, .env or botconfig.json are present in this workspace; actual database cleanup has
not been executed. Connection location, exclusive ownership, backups and a coordinated code/schema
maintenance window remain required. No merge/deployment or running-bot shutdown was performed.
