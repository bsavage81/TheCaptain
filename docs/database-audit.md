# Captain database audit and consolidation plan

Initial source-based audit, October 28, 2026; subsequently verified and applied to the owner's new dedicated MariaDB database. See database-cleanup-execution.md for exact live evidence.
The original production database and historical application records were not accessed.
The original database's table contents, triggers, scheduled jobs, grants and external consumers
remain unverified. The new database table contents and cleanup dependencies were verified separately. The owner subsequently authorized completion of database cleanup. The implemented cleanup
archives the known BotData legacy objects rather than deleting records; unknown tables and
permission changes still need a live inventory. The authorized new-database cleanup is complete; original-database cleanup was not performed.

## Object inventory

| Object | Purpose | Referenced by | Recommendation |
| --- | --- | --- | --- |
| `botdata` table | Legacy bot settings; current prefix store | `initialize_database`, `ensure_production_row`, `main.setup_hook`; migration tool | Keep existing physical table |
| `botdata.id` | Configuration identity | Runtime always selects 1; migration checks 1/2 presence | Keep primary key; never infer production from row 2 |
| `botdata.prefix` | Prefix for sync/jishaku/legacy commands | `main.setup_hook` | Keep production value unchanged |
| `botdata.persistent_views` | Old view-registration flag | Historical schema only; no runtime behavior | Archived by reversible cleanup; absent from clean runtime model |
| `botdata.bot_spam_channel_coastal` | Retained Coastal channel identifier | Owner-requested model/storage; JSON still routes messages | Keep active, restored from original row 1 |
| `botdata.bot_spam_channel_aurafall` | Historical Aurafall routing | Historical schema only | Archived by reversible cleanup; verify external consumers first |
| `botdata.bot_type` | Retired row routing metadata | Historical schema only; no row selection | Archived unchanged; no runtime deployment routing |
| `botdata.bot_id` | Retained Discord bot identity | Owner-requested model/storage | Keep active, restored from original row 1 |
| `botdata.server_id_aurafall` | Historical Aurafall guild | Historical schema only | Archived by reversible cleanup; verify external consumers first |
| `botdata.server_id_coastal` | Retained Coastal guild identifier | Owner-requested model/storage; JSON still controls scope | Keep active, restored from original row 1 |
| `botdata` row 1 | Previous STABLE production configuration | Previously STABLE→1; now explicit singleton | Keep production id/prefix active; preserve every original field in the legacy archive |
| `botdata` row 2 | Previous BETA configuration | Read-only presence check in migration; never used for startup | Retained in captain_botdata_legacy, never selected by runtime |
| Other `botdata` rows | Unknown/historical | Not selected by current runtime | Uncertain; preserve and inventory externally |
| `administrators` table | Bot operator permissions | `is_administrator`, empty-table owner seeding | Required shared infrastructure; keep |
| `administrators.id` | Row identity | Peewee primary key | Keep |
| `administrators.discordID` | Unique Discord user identity | Database owner check / sync predicate | Keep BigInteger + unique constraint |
| `administrators.TierLevel` | Permission tiers (1..4 historically) | Runtime checks >=3; archive admin tools use all tiers | Keep Integer; do not delete lower tiers or historical users without review |
| `MRP_Blacklist_Data` historical model | Old community blacklist | `!archive/BlacklistMODAL.py`, commented archived events | Physical table/name unknown; candidate only after live inventory and consumer sign-off |
| `PortalbotProfile` historical model | Community profiles | `!archive/Events.py` | Physical table/name unknown; retain data pending review |
| `Tag` historical model | Legacy tag storage | `!archive/tags.py` | Physical table/name unknown; retain data pending review |
| Other tables/views/triggers/relationships | Unknown | No evidence in active source | No removal recommendation until authorized inventory |

There are no ForeignKeyField relationships in the active models. That does not prove the live
schema has none. The read-only migration inventory reports table names, column names, foreign-key
metadata and row-1/row-2 presence, not values or administrator identities. Archived model names are
not reliable SQL table identifiers; no DROP templates are generated for inferred names.

## Implemented cleanup target — completed in the new database

The runtime model now retains only:

- `botdata`: `id` AutoField/primary key, `prefix` TextField, and BigInteger `bot_id`,
  `bot_spam_channel_coastal`, `server_id_coastal`; active singleton row 1.
- `administrators`: `id` AutoField, unique BigInteger `discordID`, Integer `TierLevel`.
- All existing administrator records; no permission/tier policy change.

`migrations/cleanup_botdata.py` moves the **entire original BotData table**, including all retired
rows and unused typed columns, to `captain_botdata_legacy`. The new active table receives the
exact production row-1 prefix and retained identifiers. No row, column value or unknown table is deleted. The archive
is retained for rollback and is not a substitute for an independent verified database backup.
Legacy models exist only in synthetic test fixtures, not in runtime startup.

A new runtime can read an existing legacy row 1 before cleanup. An old runtime that still selects
legacy columns cannot read the cleaned table, so migration and code rollout require an approved
maintenance window. Empty legacy tables fail for explicit review rather than guessing values.

## Forward migration preparation

Production routing previously came from source mapping STABLE→row 1, BETA→row 2. Only prefix was
consumed by startup. All current guild/channel/role mappings come from private JSON; preserve those
values and the current production schema. Actual deployment row 1 contents cannot be verified offline.

1. Owner exports a consistent production database backup and its DDL/grants to private storage;
   verify restore in an isolated database. Preserve existing config/environment and deployed revision.
2. Check external consumers: panel startup/cron jobs, dashboards, other bots, reports, scheduled SQL,
   database views/triggers and shared grants. Obtain owner confirmation for every destructive candidate.
3. Run `python -m migrations.single_production` with the intended database environment. Default is
   read-only, including on an empty schema. It reports metadata without printing connection secrets.
   Errors are sanitized. Do not paste private database dumps into issues or repository fixtures.
4. For a fresh database only, `python -m migrations.single_production --apply` explicitly creates
   the minimal Captain tables and row 1. This additive tool does not clean existing legacy data or
   grant permissions. Default remains a read-only preflight.
5. For existing legacy settings, run `python -m migrations.cleanup_botdata` to review the plan.
   It refuses unknown columns, foreign keys to/from settings, views, triggers, routines/events,
   custom settings indexes, unsupported servers/engines and unexpected recovery tables.
6. After verified backup/restore, external-consumer review, exclusive Captain ownership and an
   approved stopped-writer maintenance window, the operator applies:

   ```shell
   python -m migrations.cleanup_botdata --apply --maintenance-window --exclusive-database --backup-verified
   ```

   These declarations are prerequisites, not an automatic bot shutdown or proof that other writers
   are stopped. The tool copies production id/prefix to `captain_botdata_new`, verifies equality,
   then swaps names so the active table is minimal and the complete original becomes the archive.
   It never updates Administrators or touches application/POI Sheets.
7. MySQL uses a single multi-table RENAME statement, requiring InnoDB and MySQL 8+ or MariaDB
   10.6.1+. SQLite offline tests use a transactional pair of renames after rejecting dependencies.
   DDL staging/copy is not claimed to be transactional on MySQL. Any interrupted staging table
   remains intact and blocks reruns for inspection; it is never auto-dropped.
8. An already-clean singleton is a no-op. Missing production row 1, unexpected columns or an
   existing archive that would be overwritten stops the operation. Unknown historical tables,
   permissions and cross-service consumers are never guessed or deleted.

The tools are repeat-safe for serial, inspected runs. Runtime startup performs no schema DDL.
The owner supplied the new database connection transiently, and live cleanup completed after
export comparison, encrypted-transport verification and a real temporary-table restore check.
Connection credentials were not persisted in repository files. These prerequisites still apply to
any later operation or another database; the original database was not inspected or modified.

## Rollback/restoration procedure

Stop all writers in an approved maintenance window. Preview with
`python -m migrations.cleanup_botdata --rollback`. Then explicitly restore the original table:

```shell
python -m migrations.cleanup_botdata --rollback --apply --maintenance-window --exclusive-database --backup-verified
```

Rollback renames the current clean table to `captain_botdata_clean_rollback` and restores
`captain_botdata_legacy` to `botdata`. Thus it preserves any new prefix edits separately while
restoring the original complete rows/columns. Reconcile such edits before restarting the old code.
Administrator records never change. Restore the matching old code/config/dependencies; older
code may require `bot_type=STABLE`. Never revive a retired writer against shared Sheets.

If a staging table remains after failure, the tool refuses to overwrite/delete it. Determine whether
activation occurred using schema/table metadata, preserve all recovery tables, and use the verified
private backup if necessary. No DROP/DELETE/TRUNCATE statements exist in this cleanup or rollback.
Do not discard archive/rollback tables until a separately reviewed retention decision confirms the
rollback window is closed. Their names are fixed to avoid overwriting earlier recovery artifacts.

Official behavior references: [MySQL RENAME TABLE](https://dev.mysql.com/doc/refman/8.0/en/rename-table.html),
[MariaDB atomic rename](https://mariadb.com/docs/server/reference/sql-statements/data-definition/rename-table),
and [SQLite ALTER TABLE dependencies](https://www.sqlite.org/lang_altertable.html).
Foreign keys/views/triggers are rejected because table renaming can retarget their references.

## Further data deletion or unknown-object removal (not implemented or executed)

- Archive/delete retired row 2 or other unused BotData rows after proving no deployment reads them.
- Permanently discard archived compatibility columns/rows after the retention and rollback window closes.
- Remove administrator records or change tier meaning, including apparently unused tiers 1/2.
- Drop any physical table associated with historical blacklist/profile/tag models or unknown objects.
- Change foreign keys, indexes, triggers, grants, relationships or shared schemas.

Approval prerequisites are a verified backup/restore, live inventory, external-consumer sign-off,
a bounded maintenance plan, explicit object names and a reviewed restoration path. The owner authorized the known settings cleanup, which this tool implements reversibly.
Deleting recovery/history data or guessing unknown live table ownership is not part of that tool.

## Owner-requested retained identifiers

Following the initial cleanup, the owner requested bot_id and the two Coastal IDs be retained.
The live new database now contains bot_id, bot_spam_channel_coastal and server_id_coastal with their
exact original row-1 values. Administrators, prefix and the archive were verified unchanged.
The runtime model and future cleanup copy all five retained fields. The remaining retired settings
stay archived. JSON routing remains authoritative; merely retaining these values does not change
command scope or notification destinations.

Earlier two-column installations use `migrations.restore_coastal_ids` (plan by default, `--apply`
explicitly). It validates archive values, rejects conflicts, adds nullable BIGINT columns for safe
recovery after interrupted DDL, and fills only missing values on row 1. Retries preserve already
restored values. Fresh schemas use the model's non-null BIGINT/default-zero definitions. No existing
record or legacy archive is deleted. The original full-table rollback continues to support both
older two-column and current five-column clean schemas.
