# Phase 6: existing production database rollout preparation

November 4, 2026 (America/Chicago). Reviewed branch `codex/realms-phase6`, starting
revision `bb73acd48ed43b0129b3b715c62389861c47e490`.

**The owner waived separate staging. Staging is no longer a release requirement.**
This document supersedes the Docker/staging gates in the earlier readiness and
development-closeout notes. No Docker/WSL/Podman or separate-environment investigation
was performed here. Historical work and automated Stories corroboration remain deferred.

**Read-only production inspection is complete. Production DDL/deployment remains
blocked on backup/recovery evidence and separate approval.** No production data,
schema, flag, credentials, Realm settings, bot process or Discord registration was
changed. No production restore, temporary table or transaction commit was executed.

## 1. Actual production findings

The existing repository `.env` database bootstrap was used privately, without
changing it or propagating secrets to child processes. The established database
class enforces encrypted transport; its existing self-signed policy was preserved.
The audit used `SET TRANSACTION READ ONLY`, then a consistent-snapshot transaction,
SELECT/SHOW statements and a final ROLLBACK. An additional SQL guard rejects writes,
locking reads, multi-statements and file-output SELECTs. There is no audit apply mode.

| Property | Actual result |
| --- | --- |
| Server | `12.3.3-MariaDB` |
| SQL mode | `PIPES_AS_CONCAT` |
| Server character set / collation | `utf8mb4` / `utf8mb4_unicode_ci` |
| Existing profile tables | All original eight exist, all InnoDB |
| Registry table/column collation | Text columns use table collation `utf8mb4_unicode_ci` |
| Schema comparison | **No incompatibilities found** in the eight tables under the checks below |
| Ninth activity table | `captain_realm_activity` **absent** |
| New flags | Profiles, check-ins, announcements and reminders explicitly false; history absent, effective false |
| Migration ledger | No migration/schema-version table found |
| Registry triggers | None found |

Current table inventory and aggregate row counts:

| Table | Rows |
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

The audit retrieved complete CREATE TABLE definitions, ordered columns and types,
nullability, SQL defaults, generated/auto-update behavior, datetime precision,
character sets/collations, ordered index columns/uniqueness/prefix/type, table
constraints, primary/foreign keys and FK actions. Comparison is against the current
Peewee models, not merely the older migration preflight. Integer display widths are
normalized (`int(11)` and `bigint(20)`); signedness/type changes are not ignored.
Unexpected defaults, CHECK constraints, cross-schema FKs and ignored/descending
indexes require review. An offline recheck of the captured definitions with those
extended checks also found no incompatibilities. Registry types include signed
int/bigint, `tinyint(1)`, varchar, text and second-precision `datetime` as modeled.

The complete structural report, without player rows or settings contents, is private
and Git-ignored at `.test-tmp/phase6-production-readonly/audit-20261104.json`.
It includes actual DDL, indexes, constraints and aggregate counts, plus private
target/settings fingerprints. Do not publish host/account values or whole settings.
Tool: [`scripts/phase6_production_audit.py`](../scripts/phase6_production_audit.py).

Migration history is evidence-based: the earlier
[executed settings/registry record](settings-registry-migration-execution.md) reports
the original eight-table apply and repeat preflight. Their present definitions and
empty state corroborate the current schema, not an exact migration execution time
or a claim that no rows have ever existed. There is no authoritative in-database
migration ledger to reconstruct later activity. The ninth table has not been applied.

## 2. Backup and recovery gate — not satisfied

The available local `captain-before-settings-registry-20261029T021510Z.json` backup
matches both its SHA-256 sidecar and the checksum in its existing verification
receipt. It covers **only** `administrators`, `botdata`, and
`captain_botdata_legacy`. It predates registry creation and does **not** cover any
of the eight registry tables or today's current settings snapshot. Older cleanup
and identifier-restoration artifacts are also historical, not complete current backups.
The protected later settings-only snapshot is not a complete database backup either.

**A current complete independently restorable backup has not been established.**
Apollo backup inventory/coverage/retention and a database restore procedure were not
verified: no existing panel API credentials are available in the inspected process
or repository bootstrap. A bot/server-files backup must not be assumed to include
the externally managed MariaDB database. No Apollo backup is claimed absent; its
scope and recoverability are simply unverified from available evidence.

Stop before DDL. Required evidence is an owner/provider-confirmed current backup
covering the entire affected schema: all 11 current tables, complete definitions,
indexes/FKs/constraints, current rows and operational settings. Inventory routines,
events, triggers/views and any external dependencies before calling the backup complete.
Keep the encrypted Realms store and host environment recovery separate and protected;
do not read/rotate them or open another running-store writer during backup preparation.

Acceptable next action is a separately approved **backup-only** operation or verified
Apollo database-backup evidence. For a complete logical dump, a designated executor
with the MariaDB client can use an owner-only client option file with the existing
approved TLS/target/account, never secrets in shell arguments:

```sh
mariadb-dump --defaults-extra-file=/private/captain-approved.cnf --single-transaction --routines --events --triggers --hex-blob --skip-add-drop-table --result-file=/private/captain-before-phase6.sql APPROVED_SCHEMA
sha256sum /private/captain-before-phase6.sql
```

These commands are **prepared, not run**. Confirm encrypted transport and target,
exit status, complete object inventory, durable independent storage/checksum and
the operator/provider's actual recovery procedure/restore evidence. Coordinate no
concurrent DDL during the consistent dump. No separate application staging database
is required by this plan; restore verification is a recovery assurance question,
not a revived staging project. No restore into production is authorized.

DDL recovery must not rely on ROLLBACK: MariaDB schema changes can commit independently
of surrounding transactions. On a failure, preserve the private before/after metadata,
check whether the ninth table exists and whether its full definition matches the
approved SQL, then stop. Do not automatically drop it, rebuild existing tables or
restore an old whole database over newer writes. A data restore or index repair
would require a separately reviewed state-specific recovery approval. Keeping all
new feature flags off isolates the unused new table if deployment/activation is halted.

## 3. Exact additive migration prepared — approval required

Approved scope to propose: **one new, empty `captain_realm_activity` table only**.
No existing table needs alteration. The exact artifact is
[`migrations/sql/phase6-activity-only.sql`](../migrations/sql/phase6-activity-only.sql).
It contains one CREATE TABLE statement, InnoDB/utf8mb4 with the observed collation,
the modeled nullable player FK, primary key, unique evidence key and all five modeled
secondary/unique indexes inline. No ALTER, DROP, data manipulation, schema selection
or IF NOT EXISTS is present. The no-op masking behavior of IF NOT EXISTS is intentionally
avoided: an unexpectedly existing table must stop execution, not be silently accepted.

The artifact's columns, FK and index definitions are checked offline against the
actual Peewee SQL compiler output. Combining the indexes into the one CREATE reduces
the separate-table/index partial-apply surface. It does not make DDL transactionally
rollbackable or establish recovery readiness. The artifact has not been executed.
Do not substitute the broad nine-model `--apply` CLI: this rollout approves only
the observed missing object, not CREATE/repair attempts across existing tables.

Before requesting owner DDL approval:

1. Close the backup/recovery gate and identify the exact maintenance executor,
   private connection profile and reviewed commit/artifact checksum.
2. Coordinate no other schema/configuration changes; keep all new flags off.
3. Repeat the read-only audit against the explicitly approved existing `.env`,
   creating a **new** protected report rather than overwriting the baseline:

   ```sh
   python -m scripts.phase6_production_audit --bootstrap-file /private/captain-existing.env --output /private/phase6-audit-before.json
   ```

   The report parent must already be private (0700 / restrictive Windows ACL), and
   the output must not exist. No token or Discord bootstrap value is consumed.
   Require no incompatibilities, exactly the one missing ninth table, the same
   approved private target and unchanged expected definitions/flags. If rows or
   settings have changed since the approved backup, refresh/review recovery evidence.
4. Review the artifact's SHA-256 and exact CREATE statement with the owner:

   ```sh
   sha256sum migrations/sql/phase6-activity-only.sql
   ```

Only after separate explicit approval of that artifact and plan, a designated
executor may run this **future production DDL command**:

```sh
mariadb --defaults-extra-file=/private/captain-approved.cnf --batch --skip-reconnect --database=APPROVED_SCHEMA < migrations/sql/phase6-activity-only.sql
```

Replace `APPROVED_SCHEMA` only from the private matched inventory. Match the client
profile to the audit target/TLS policy; don't run with `--force`, implicit defaults
or a different schema. Current local availability of a MariaDB client/approved host
executor is not established. SFTP access is not an execution shell. This command
must not be attempted until an actual executor is agreed.

Then rerun the read-only audit to a fresh `/private/phase6-audit-after.json`.
Expected outcome: 12 base tables, all nine Phase 6 tables match, no missing table,
the new table has zero rows, all existing table definitions/counts/settings unchanged,
and every new flag remains off. Also compare the original eight full definitions
and unrelated table definitions against the private before report. Any unexpected
state stops rollout. Do not reapply the CREATE if it already exists. No history
import, profile link, settings update or deployment is included in DDL approval.

## 4. Exact deployment preparation — separate approval required

The new readiness/audit artifacts will be committed on the Phase 6 branch. Select
the **resulting immutable reviewed SHA** with all branch CI checks passing; do not
deploy the mutable branch name or assume the starting `bb73acd` contains these fixes.
Any merge commit's resulting main SHA is a separate exact release identity.

Before owner deployment approval, record actual running/rollback SHA, startup
checkout behavior, Python/dependency compatibility and current flag/settings
baseline privately. They were not freshly inspected by the database audit. Prior
Apollo evidence reports Python 3.14, whereas CI uses 3.12. Existing host execution
and dependency checks still need an approved executor; no new runtime/credential
configuration is required merely by this database plan.

Pushing main triggers `.github/workflows/my_workflow.yml`, which serializes the
deployment and executes:

```sh
python scripts/panel_deploy.py --restart-and-verify --expected-revision REVIEWED_MAIN_SHA
```

Hosting secrets are supplied by the existing secret manager, never embedded in this
command. This is the workflow's command, **not** permission for an additional manual
restart. Approve the exact merge/main update and resulting restart together. Keep
profiles/check-ins/announcements/reminders/history false; preserve the existing
`realms` and `realm_panel` settings exactly so Phase 4 remains enabled as configured.
The workflow does not migrate the database or activate features.

Initial deployment acceptance:

- Verify exact source SHA and ready revision; one bot process, correct existing
  database, encrypted connectivity and no startup schema error. No DDL at startup.
- Verify the existing Realm panel message refreshes rather than creating duplicates,
  names/live observations remain available, stale/unknown observations are handled
  correctly, and current observed online-duration estimates retain their behavior.
- Verify established authentication/store persistence without opening a second
  store or copying credentials back. Do not refresh/login diagnostically or restart
  again as a test; ordinary bot behavior is observed within the approved window.
- Verify existing staff/member command and application/guide/POI entry points remain
  present without generating test submissions or republishing persistent messages.
  All new profile/check-in/history flags remain off throughout this checkpoint.

No code merge, deploy, restart, command sync, token-store inspection or extra live
Realm API call was performed by this preparation. If acceptance fails, stop and use
only an explicitly approved flag/code recovery; retain the additive unused table.

## 5. Profiles alone — later independent activation approval

After successful deployment acceptance, review and approve profile activation's
side effects: guild-only profile/check-in commands, stable persistent check-in view
`captain:monthly-checkin:v1`, existing live submission capture into profile records,
member/role event listeners and 15-minute linked-profile inactive-state mirroring.
These can write registry rows even with check-in scheduling disabled. The existing
Discord inactive role remains authoritative; code does not assign/remove roles.

The shared profile OP check uses `OPTeamRole` (a configured name or numeric ID),
whereas Realm commands use numeric `CoastalOPTeam`. Confirm the actual approved
policy before activation; any selector change is a separate configuration decision.
No identifier values are recorded here. Scope/permission checks and private replies
remain required; command visibility alone is not authorization.

Prepared future commands, each preview reviewed before separately approved apply:

```sh
python -m migrations.botdata_settings --set profiles_enabled --value true
python -m migrations.botdata_settings --set profiles_enabled --value true --replace-existing --apply --backup-verified
```

Unlike the read-only audit, that settings CLI loads the maintenance checkout's
`.env`; ensure the deliberately approved production target. A same-reviewed-code
restart is separately required because settings are loaded at startup. Approve
only Coastal guild command sync using the existing administrator flow, never global
sync or an unrelated main push. Private OP/non-OP/wrong-guild command checks follow.
`/playerprofiles view` can refresh inactive state; `/checkin status` can create a
period even with scheduling off, so neither is assumed no-write testing.

Keep `checkin_enabled`, announcements and reminders false. Keep history absent/false
and never confirm activity retention. Historical `setup`, discovery, previews,
staging/review/import and bulk identity operations remain prohibited by scope;
there is no separate "historical imports enabled" flag to toggle. Staff command
discipline/permissions and individually authorized writes enforce that boundary.
No automatic Stories collection, corroboration, public statistics or leaderboard
is activated or implemented by this rollout. Optional check-ins/history need future
privacy/retention/channel/identity approvals, not automatic continuation of profiles.

## 6. Completion and approvals ledger

Completed: authorized live read-only schema/flag/count inspection, expanded full-schema
comparison, local backup checksum/coverage review, single-object SQL preparation,
recovery/deployment/profile procedures and offline safety tests. No existing runtime
behavior or credential handling was changed. No incompatibility was found requiring
an existing-table fix; the only missing object is the ninth activity table.

Offline validation: **366 passed, 1 platform skip** across the tracked Phase 4/6
regressions and **28** new audit/SQL-artifact cases. Ruff F, Python compilation and
whitespace checks passed. The only warning was the existing discord.py `audioop`
deprecation. Tests block external network and use fake metadata/synthetic databases;
only the separately authorized audit connected to production, read-only. The CREATE
artifact was compiler-compared, never executed as a test or migration. Final branch
CI must also pass before release selection. No separate staging validation is claimed.

Remaining blockers and exact approvals:

1. **Backup/recovery:** supply current complete Apollo database backup evidence and
   its verified recovery path, or authorize a bounded backup-only operation with
   protected independent storage and a provider/DBA recovery procedure. Historical
   three-table receipts do not meet this requirement.
2. **Execution/identity:** agree the maintenance executor and private target/client
   profile, no-concurrent-DDL window, release/rollback SHA and actual host checks.
3. **DDL:** explicitly approve only the reviewed single CREATE artifact/checksum
   after a fresh matching before audit and verified recovery evidence. Nothing
   else is migrated, repaired or enabled.
4. **Deployment:** explicitly approve the exact reviewed main SHA/update and its
   restart, with the new flags off and a Phase 4 acceptance window.
5. **Profiles:** after deployment acceptance, separately approve activation side
   effects, private permissions/identity policy, same-code restart and guild sync.
   Historical imports, check-in messaging, history retention and public statistics
   remain disabled/deferred unless separately authorized later.

There is **no remaining staging gate** and no request to provision Docker. The
current authorization stops before production DDL, production backup restore,
settings writes, deployment, restart or profile activation.
