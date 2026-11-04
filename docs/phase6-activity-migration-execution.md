# Phase 6 limited production activity migration — executed

November 4, 2026 (America/Chicago). Authorized preparation revision:
`7ed265f4d06581a3537be8c1382fd5011eacabc7`, branch `codex/realms-phase6`.

**The approved ninth-table migration succeeded in production, on one attempt.**
No retry, automatic repair, destructive recovery, import, flag update, merge,
deployment, restart, Discord sync or Realm operation occurred. The owner explicitly
accepted that the complete backup was integrity/coverage verified but not restore-tested.
This authorization did not include any deployment or feature activation.

## Preconditions verified before execution

- Working SQL bytes matched both the approved commit and the approved SHA-256:
  `3d342c71a5bde23c9956cebd2fac38f8620e574656371d46c146fae01d3712f4`.
  Artifact: [`phase6-activity-only.sql`](../migrations/sql/phase6-activity-only.sql).
- The existing encrypted production connection identified MariaDB **12.3.3** and
  the exact private target/account/SQL-mode/charset identity bound to the backup.
  Connection identity was checked again immediately before sending the DDL.
- The [complete backup](phase6-backup-recovery-verification.md) remained private,
  accessible and intact. Both approved artifact checksums, per-table schema/data
  hashes and recovery-SQL regeneration passed. No backup was overwritten or restored.
- A new explicit REPEATABLE READ / READ ONLY capture verified all **11** original
  tables, their full definitions, engines, indexes, keys/constraints and records.
  No schema incompatibilities or additional database objects were found.
- All original definitions and typed records matched the approved backup exactly.
  All eight registry tables were empty; original application records totaled four.
  Current settings also matched the backed-up settings fingerprint.
- `captain_realm_activity` was absent in the complete preflight and a final presence
  check on the DDL connection. Profiles, check-ins, announcements and reminders
  remained explicitly false; Realm history remained absent/effective false.

The disposable controller was reviewed before execution. Offline checks exercised
successful pre/post validation and seven stop conditions: changed identity, version,
flags, records, inventory, missing-table plan and schema compatibility. Backup
integrity/ACL checks and Ruff F passed. Its evidence directory was created exclusively;
a persisted attempt marker was written before the one permitted DDL call. A repeat
invocation would stop rather than reconnect/reexecute under the same evidence path.

## Executed scope

The approved SQL file was sent unchanged as **one CREATE TABLE statement**, once,
through the established TLS-enforced database connection. All indexes were included
inline in that statement. No broad migration apply command was used; no existing
table was recreated or altered. The driver returned success before verification.

The new `captain_realm_activity` table has the modeled columns, nullable player FK,
primary key, unique evidence key and four nonunique indexes, using InnoDB and
`utf8mb4_unicode_ci`. Timestamps retain the existing naive-UTC database convention.
No interval/profile data was ingested and no application process was restarted.

## Postconditions verified read-only

| Check | Actual result |
| --- | --- |
| Application base tables | **Exactly 12** |
| Phase 6 schema | All nine modeled tables present, no incompatibilities |
| New activity table | Present, expected columns/PK/FK/indexes/engine/collation |
| New activity rows | **0** |
| Original eleven full definitions | Unchanged from preflight and approved backup |
| Original eleven typed records | Unchanged, four rows total |
| Original eight registry tables | Still empty |
| Settings/feature flags | Unchanged; all new features remain off |
| DDL attempts | **1**, success; **0 retries/repairs** |

Comparisons used complete CREATE definitions, ordered data columns and canonical
typed row sets, not just table/row counts. The existing read-only audit also compared
column types/nullability/defaults/precision, primary/unique/nonunique indexes,
foreign keys/actions and collation against the models. The fresh after snapshot
contained no missing Phase 6 table or incompatible schema.

Private Git-ignored receipts are under
`.test-tmp/phase6-migration-approved-20261104/`: `preflight.json`,
`ddl-attempt.json` and `postflight.json`. They contain aggregate counts, flags and
comparison hashes; no identifiers, connection secrets or player histories are
published here. The scratch controller is not an automatic/unattended migration tool.
Do not rerun the CREATE artifact: the table now exists and that file deliberately
does not hide the condition with IF NOT EXISTS.

## Recovery status

The pre-migration backup remains a complete snapshot of the original eleven tables.
It intentionally predates the new unused table, which can be reconstructed from the
approved SQL if a separately approved recovery ever requires it. No restore has
been tested or executed, and no recovery action was necessary. DDL is not assumed
transactionally rollbackable. Preserve additive schema/data; do not drop the table
as a routine code rollback. A production restore or repair still requires separate,
state-specific approval.

## Next checkpoint: exact deployment approval

**Database migration is complete; deployment is not authorized or performed.**
Before requesting deployment approval, select the final immutable CI-green Phase 6
release/merge SHA and inspect the actual current host/rollback revision, startup
checkout behavior and interpreter/dependency compatibility. Preserve the existing
private authentication/token store and `realms`/`realm_panel` configuration. Keep
all new feature flags off.

The owner must explicitly approve the exact main update/merge and its automatic
production restart: main push triggers the existing deployment workflow. Initial
acceptance must verify the existing panel/message, names/live observations,
observed online durations, authentication persistence, existing commands and
encrypted database connectivity without enabling profiles/history or importing
records. Do not run a second manual restart alongside the workflow.

Profile activation, its inactive-role/live-submission/persistent-view side effects,
guild command sync, check-ins/messaging and history each remain separately gated.
Historical archive work and automatic Stories corroboration remain deferred.
