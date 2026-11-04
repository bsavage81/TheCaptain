# Phase 6 final backup and recovery verification

November 4, 2026 (America/Chicago). Branch `codex/realms-phase6`, starting revision
`c8d6f687e433d0558a025dea4e180a3138bfcbe9`.

**A new complete logical database backup has been created and verified for integrity
and coverage. An actual MariaDB restore has not been tested.** Migration remains
unexecuted and requires the explicit approval at the end, including acceptance of
that recovery limitation or additional recovery evidence. No staging requirement
is reintroduced. No merge, restart, feature activation, Realm call or production
database write was performed.

## Mechanism, destination and protection

Available earlier backups were owner-controlled typed logical exports made through
the existing encrypted database connection. The old verified settings/registry-preparation
backup covered only three tables, so it was insufficient for the current schema.
Apollo's native database-backup coverage and restore service remain unverified; a
hosting-files backup is not assumed to include MariaDB. No panel credentials were
created/requested and no host setting was changed.

The supported existing access path is the application's established TLS-enforced
MariaDB connection. A client-side logical export using SHOW CREATE TABLE and a
consistent read-only snapshot avoids new server software, production temporary
tables, locks for backup, changes to grants, or running-bot/token-store interference.
The new tool explicitly requests REPEATABLE READ / READ ONLY transaction isolation,
then uses SELECT/SHOW and ROLLBACK only, via the read-only audit guard.
It checks existing metadata visibility privileges before claiming object completeness.
All exported tables must be InnoDB; otherwise it stops.

Before connecting, the tool confirmed an existing backup parent, Git exclusion,
no symlink/junction path, a new random exclusive subdirectory, and restrictive
owner permissions. Only then were credentials read in memory and the snapshot
opened. Each file uses exclusive creation (`O_EXCL`), restrictive permissions,
flush/fsync and byte-for-byte read-back. Existing backups cannot be overwritten.
Credentials are not written into backup files or printed.

Private off-database-host destination on this Windows workstation:

```text
.database-backups/phase6-20261104T133911Z-2dedb0fcb4d4/
  backup.json       typed data, complete table definitions and structural metadata
  recovery.sql      standard MariaDB CREATE/INSERT recovery script
  verification.json checksums, counts and explicit untested-restore status
  independent-verification.json fresh-process integrity/permission check receipt
```

Capture completed at approximately **07:39 AM CST**, November 4. These files are
Git-ignored, private and **not committed or uploaded**. Protection is restrictive
filesystem ACLs, not a claim of additional encryption at rest. Retain the directory
in owner-approved durable private backup storage; do not synchronize it to GitHub
or a public/shareable folder. The receipt alone cannot recover the database.

The first attempt safely stopped at a too-strict grant check before table-data
capture and left only an empty protected directory. The guard was corrected to
recognize existing Apollo explicit privilege lists and escaped/wildcard schema
grants, tested offline, and the successful attempt used a different fresh directory.
No privileges were changed and no failed artifact was overwritten.
An earlier complete copy was also retained; the final copy makes REPEATABLE READ
explicit rather than relying on server defaults. The two recovery SQL files have
identical SHA-256 values; the final directory above is the approval baseline.

## Verified snapshot coverage

Actual source: **MariaDB 12.3.3**. The backup has **11 table definitions and four
rows**, including all eight registry tables. Full current settings and the legacy
settings archive are included as private data, not merely a flag summary.

| Table | Verified rows |
| --- | ---: |
| `administrators` | 1 |
| `botdata` | 1 |
| `captain_botdata_legacy` | 2 |
| `captain_player` | 0 |
| `captain_identity` | 0 |
| `captain_participation` | 0 |
| `captain_import_record` | 0 |
| `captain_checkin_period` | 0 |
| `captain_checkin` | 0 |
| `captain_reminder` | 0 |
| `captain_discovery_run` | 0 |

No views, triggers, stored routines or events were found with the existing grants
that establish schema-wide visibility of those objects. If such objects are present
on a future run, this exporter stops rather than silently omitting them. The ninth
table is still absent. All new flags remain off, and no schema incompatibilities
were found. Source table names/CREATE definitions were checked again before closing
the snapshot and remained stable. Snapshot row counts match exported row counts.

Integrity checks performed:

- Typed JSON preserves integers (including unsigned-64-bit-sized values), strings,
  binary, nulls, decimals and supported date/time types without lossy stringification.
  Every actual value round-tripped through serialization before acceptance.
- Each table has schema/data hashes. The complete JSON and SQL artifacts have
  SHA-256 hashes in the private receipt. Files were read back and compared to the
  captured snapshot, including all row counts and definitions.
- A fresh process rechecked directory/file ACLs, both whole-file checksums, Git
  exclusion and exact recovery-SQL regeneration from the stored JSON. All passed.
- The SQL preserves SHOW CREATE definitions, indexes/FKs/engines/collations and
  restores tables/rows in FK dependency order. Strings use UTF-8 hex expressions,
  so quotes, backslashes and SQL modes cannot turn values into statements. No DROP,
  schema-selection or overwrite logic is generated. It is not run by the backup tool.

Creation command executed (read-only against production):

```sh
python -m scripts.phase6_database_backup --bootstrap-file .env --destination-parent .database-backups
```

Tool: [`scripts/phase6_database_backup.py`](../scripts/phase6_database_backup.py).
Only schema/aggregate information and checksums were printed. Private table rows,
settings, credentials, account/host names and backup contents are excluded from Git.

## Recovery procedure and unverified steps

**No isolated recovery target has been supplied or identified. No restore was run.**
The earlier production-temporary-table verification of a three-table backup is not
evidence that this new eleven-table backup has been restored. Offline round trips
and SQL generation verify the artifact, not MariaDB's execution of that SQL.

For a future separately approved recovery verification:

1. Confirm an isolated, empty MariaDB 12.3.3 recovery target and private client
   profile. It must not be the production endpoint/schema. Verify identity, TLS,
   version and zero existing objects before any recovery write. Keep real backup
   data private; a target is not automatically authorized merely because it exists.
2. Verify the receipt's SHA-256 values against both artifacts before use. Protect
   the backup and private client-options file; never put passwords in command args.
3. On the approved recovery executor only, use the recovery connection profile:

   ```sh
   mariadb --defaults-extra-file=/private/captain-recovery-target.cnf --batch --skip-reconnect --database=APPROVED_EMPTY_RECOVERY_SCHEMA < /private/phase6-backup/recovery.sql
   ```

   Do not use `--force`, an implicit schema, the production profile or a prepopulated
   target. All CREATE statements intentionally fail on an existing table. No automatic
   cleanup/retry follows an error; preserve the partially created recovery schema.
4. Compare all eleven complete definitions, indexes/FKs, engines/collations and
   typed rows/counts with `backup.json`; run read-only application configuration/
   registry checks against that target. Record results privately. Only an actual
   successful comparison closes the tested-restore limitation.

Residual risk: restore syntax/privilege/definer/server behavior has not been exercised
on a real recovery database; provider restore support and recovery time are unverified.
This is a full logical database backup, not point-in-time/binlog recovery, a server
image, account/grant backup or complete host/token/secret-manager backup. Existing
host configuration, database account provisioning/TLS, and sole-writer credential
store recovery must remain independently available. Snapshot freshness also ends
at capture: refresh the backup if approved production state changes before migration.

DDL is not recovered by ROLLBACK. If the proposed ninth-table CREATE fails, inspect
the resulting table state read-only and stop. Do not drop an existing table, reset
settings, restore the old database over new records or repair indexes automatically.
With all new features off, an unused additive table can remain while recovery is
reviewed. Any destructive/state-changing recovery needs separate owner approval.

## Backup gate decision

**Complete-backup coverage and integrity gate: satisfied for this capture.**
**Tested MariaDB restore assurance: not satisfied.** The backup is prepared for
independent recovery, but cannot honestly be called restore-tested. The owner may
accept this documented residual risk for the single additive migration, or require
provider/recovery verification first. Either way, no production DDL is authorized
by creating or verifying these files.

### Legacy Git-tracking privacy finding

The final tracking audit found **five pre-existing legacy backup/checksum/verification
files already tracked despite `.gitignore`**. None of today's artifacts was tracked.
The legacy files were removed from the branch's tracked set with `git rm --cached`,
not deleted locally. Their bytes were hash-compared before/after and preserved.
The existing backup parent directory ACL was hardened, all five legacy file ACLs
then verified private, and the backup tool now also refuses an unprotected parent.
This prevents those files remaining in the new branch snapshot; it **does not erase
prior Git history**. Historical removal would be a separately approved repository
privacy/history-cleanup operation; no force-push or history rewrite was attempted.

## Exact production migration approval request — not executed

Please review the final CI-green Phase 6 commit and the unchanged artifact
[`migrations/sql/phase6-activity-only.sql`](../migrations/sql/phase6-activity-only.sql).
The canonical Git artifact SHA-256 (LF bytes) is:

```text
3d342c71a5bde23c9956cebd2fac38f8620e574656371d46c146fae01d3712f4
```

Requested approval is **only**:

> Accept the documented absence of a tested MariaDB restore for this backup, or
> first supply additional recovery evidence; then authorize one reviewed CREATE
> TABLE for `captain_realm_activity` in the existing Captain production schema,
> including its modeled FK, unique key and indexes. Require a fresh read-only
> before check matching the approved target/schema/flags/backup state. Stop on
> any unexpected state. Verify all original definitions/records and the new empty
> table afterward. No other DDL, data import, flag update, merge, restart, Discord
> sync, profile activation or Realm operation is included.

The exact SQL and future execution procedure remain in the
[production rollout preparation](phase6-production-database-rollout.md#3-exact-additive-migration-prepared--approval-required).
Expected post-migration state: **12 application tables**, nine Phase 6 tables matching
the model, zero new activity rows, no changes to the original eleven tables/rows or
settings, and all new flags still off. If data/settings/schema changed since this
backup, stop and refresh/review it rather than rely on stale recovery evidence.
Deployment and profile activation still need separate approvals after that checkpoint.

Offline validation: **389 passed, 1 platform skip** across the Phase 4/6 regressions,
audit and backup tests. After the final isolation/parent-permission guard changes,
all **52 focused audit/backup tests passed**. Ruff F and compilation checks passed. The only
warning was the existing discord.py `audioop` deprecation. These tests prove software
guards/serialization behavior, not a database restore. Final branch CI must also
pass before selecting the production migration revision.
