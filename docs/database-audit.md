# Captain database audit and consolidation plan

Source-based audit, October 28, 2026. No live database, credentials or applicant records were read.
Actual table existence, row contents/counts, indexes, triggers, scheduled jobs, grants, external
consumers and cross-application dependencies remain unverified. No object below is approved for
deletion merely because it has no active Python caller.

## Object inventory

| Object | Purpose | Referenced by | Recommendation |
| --- | --- | --- | --- |
| `botdata` table | Legacy bot settings; current prefix store | `initialize_database`, `ensure_production_row`, `main.setup_hook`; migration tool | Keep existing physical table |
| `botdata.id` | Configuration identity | Runtime always selects 1; migration checks 1/2 presence | Keep primary key; never infer production from row 2 |
| `botdata.prefix` | Prefix for sync/jishaku/legacy commands | `main.setup_hook` | Keep production value unchanged |
| `botdata.persistent_views` | Old view-registration flag | Model mapping only; no runtime behavior | Cleanup candidate; retain for schema/rollback compatibility until approved |
| `botdata.bot_spam_channel_coastal` | Historical Coastal routing | Model mapping only; actual routing uses JSON | Candidate; verify panel/scripts/archived tooling before removal |
| `botdata.bot_spam_channel_aurafall` | Historical Aurafall routing | Model mapping only | Candidate; verify external consumers |
| `botdata.bot_type` | Retired row routing metadata | Legacy field mapping/default insertion only; no row selection | Candidate; existing values preserved; no uppercase normalization of existing rows |
| `botdata.bot_id` | Historical Discord bot identity | Model mapping only | Candidate; verify operational consumers |
| `botdata.server_id_aurafall` | Historical Aurafall guild | Model mapping only | Candidate; verify external consumers |
| `botdata.server_id_coastal` | Historical Coastal guild | Model mapping only; JSON is current source | Candidate; verify external consumers |
| `botdata` row 1 | Previous STABLE production configuration | Previously STABLE→1; now explicit singleton | Keep every value unchanged |
| `botdata` row 2 | Previous BETA configuration | Read-only presence check in migration; never used for startup | Retirement/archive candidate; preserve pending owner approval |
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

## Proposed cleaned Captain schema (future approval only)

The minimal runtime target would retain:

- `botdata`: `id` AutoField/primary key and `prefix` TextField, singleton row 1.
- `administrators`: `id` AutoField, unique BigInteger `discordID`, Integer `TierLevel`.
- Existing permission records; no role/owner policy change.

This branch **does not implement physical column/row removal**. Current model fields remain mapped
so inserts and rollback continue to work with Captain's existing schema. Removing a mapped column
would break the current compatibility model; a future approved migration must update the model,
verify all external consumers, preserve a typed backup and validate both directions together.
No PortalBot schema is substituted, and no application/POI records are moved into MySQL.

## Forward migration preparation

Production routing previously came from source mapping STABLE→row 1, BETA→row 2. Only prefix was
read from that row. All current guild/channel/role mappings come from private JSON; preserve those
values and the current production schema. Actual deployment row 1 contents cannot be verified offline.

1. Owner exports a consistent production database backup and its DDL/grants to private storage;
   verify restore in an isolated database. Preserve existing config/environment and deployed revision.
2. Check external consumers: panel startup/cron jobs, dashboards, other bots, reports, scheduled SQL,
   database views/triggers and shared grants. Obtain owner confirmation for every destructive candidate.
3. Run `python -m migrations.single_production` with the intended database environment. Default is
   read-only, including on an empty schema. It reports metadata without printing connection secrets.
   Errors are sanitized. Do not paste private database dumps into issues or repository fixtures.
4. If both Captain tables exist with all expected columns and row 1 exists, consolidation is a
   **data-preserving no-op**: keep row 1 and all rows/permissions exactly as they are. No SQL migration
   is needed to choose production unconditionally. Remove obsolete bot_type from production config.
5. For a fresh/empty schema only, review and explicitly run
   `python -m migrations.single_production --apply`. It creates missing Captain tables with the
   existing model definitions and inserts row 1 using the existing defaults if no rows exist.
   It never seeds Administrators; normal startup retains its original empty-admin seeding.
6. An incomplete existing schema or a nonempty BotData table missing row 1 fails closed. Restore the
   verified production row or resolve the schema through an owner-reviewed process. Row 2 is never
   renamed/copied into row 1, and a retired BETA prefix cannot overwrite production.

The additive script is repeat-safe for serial execution; run it while bots are stopped during an
approved maintenance window. `create_tables(safe=True)` preserves existing objects. MySQL DDL can
autocommit, so Python transactions are not a rollback guarantee for table creation. Runtime startup
performs **no schema DDL** and tells operators to run the explicit tool if tables are missing.

## Rollback/restoration procedure

Existing production data is never rewritten, so there is no reverse data migration for a normal
row-1 deployment. Stop the new process manually in an approved window; restore the saved code,
dependency environment, `.env` and JSON config. If restoring the previous release, keep
`bot_type=STABLE` to select the same production row. Never revive the retired bot against shared
Sheets. Preserve row 2 and all compatibility fields so the prior model remains readable.

For a fresh schema created by an explicitly applied bootstrap, leave the new tables/row in place;
do not auto-delete them on rollback because they may have acquired live data. If restoration is
necessary, use the tested private database backup and DBA-approved restoration process. Any
reversal that drops objects, deletes rows or overwrites newer records requires separate approval.
No rollback script containing executable destructive SQL is included.

## Destructive changes requiring owner approval (none executed)

- Archive/delete retired row 2 or other unused BotData rows after proving no deployment reads them.
- Remove any compatibility column listed above, coupled with a separate ORM model migration.
- Remove administrator records or change tier meaning, including apparently unused tiers 1/2.
- Drop any physical table associated with historical blacklist/profile/tag models or unknown objects.
- Change foreign keys, indexes, triggers, grants, relationships or shared schemas.

Approval prerequisites are a verified backup/restore, live inventory, external-consumer sign-off,
a bounded maintenance plan, explicit object names and a reviewed restoration path. This PR requests
review of the plan only; it does not grant approval to perform these operations.
