# Phase 6 production readiness and controlled rollout

**Superseded staging decision (November 4):** the owner waived separate staging.
Use [the live database findings and current approval-gated rollout](phase6-production-database-rollout.md).
The Docker setup below is retained historical preparation, not an outstanding requirement.

November 3, 2026 (America/Chicago). Branch `codex/realms-phase6`, development
closeout `712dc7a3462c7e7121205dfb4f4eea196a14da21`.

**Production rollout is blocked at MariaDB staging.** Development closeout remains
valid; it is not production activation approval. Historical archives/imports and
automatic Stories corroboration remain deferred. This review made no production
connection, Realm/authentication request, configuration change, merge, deployment,
restart or production migration. The architecture audit below is source review
against recorded deployment evidence, not a fresh inspection of production state.

## Staging availability and compatibility

Read-only checks found no Docker, Podman, MariaDB/MySQL server or client executable
on Windows PATH, no matching Windows service, and no Docker Desktop or checked
MariaDB/MySQL installation at the usual Program Files paths. Ubuntu is installed
under WSL, but its PATH also contains none of those tools. No engine was installed,
service started, image pulled, port probed or database provisioned. Stop at this gate.

The simplest proposed setup is **Docker Desktop with its WSL 2/Linux-container
backend**, two local disposable MariaDB containers and the existing Python venv.
Installation/host changes are an owner action; they are not performed by this task.
See [Docker's Windows installation requirements](https://docs.docker.com/desktop/setup/install/windows-install/).

Prior [database cleanup](database-cleanup-execution.md) and
[registry execution](settings-registry-migration-execution.md) record **MariaDB
12.3.3**, InnoDB, encrypted transport with explicitly approved self-signed certificate
handling, and the eight registry tables already created. That is historical evidence;
the current server version, SQL mode, charset/collation and schema must be reconfirmed
by the owner before claiming production compatibility. No current value was queried.
Use the matching official image only after verifying its availability and digest.
Do not silently substitute a nearby version if `mariadb:12.3.3` is unavailable.

### Prepared validation harness — not yet executed on MariaDB

- Compose: [`config/phase6-staging.compose.yml`](../config/phase6-staging.compose.yml).
  Two fixed staging containers on an internal bridge, random **IPv4-loopback-only**
  ports, tmpfs data directories, no host bind mounts, restart disabled, fresh
  staging-only credentials. Each has its own `captain_phase6_stage` schema and a
  user granted access only to that schema; neither is a production schema/server.
- Harness: [`scripts/phase6_mariadb_validation.py`](../scripts/phase6_mariadb_validation.py).
  Explicit `MySQLDatabase` backends with fixed loopback host/schema/user. No `.env`
  loader, production factory, bot startup or arbitrary host option. Requires an
  official-image digest, exact version and `--allow-synthetic-ddl`. Refuses remote
  Docker contexts, wrong containers/image/hostname, non-tmpfs mounts, exposed ports,
  a shared/non-internal network, unexpected grants or a nonempty initial schema.
  The local container transport is unencrypted synthetic loopback traffic; production
  TLS and certificate validation are separate gates, not claimed tested here.
- The harness uses thread-local independent database connections for two identity
  races: two profiles claiming one XUID, and one profile receiving conflicting XUIDs.
  A lost race must leave no conflicting verified evidence. No retry is hidden.
- Backup uses `mariadb-dump --single-transaction --skip-lock-tables`, holds the
  synthetic dump in memory, restores it into the **second container**, and compares
  every table/column/typed row, primary/foreign keys and migration preflight. No
  concurrent DDL occurs during the dump. Only a SHA-256/result summary is printed.
  This is not durable/off-host production backup or recovery evidence.
- Expected failure tests deliberately leave one committed DDL table, preserve a
  sentinel across resume, refuse a missing backup assertion, extra column, missing
  unique index and MyISAM engine. Only known synthetic tables are reset between
  expected cases. An unexpected failure stops and preserves containers for review;
  there is no automatic production fallback or destructive recovery.

| Required MariaDB validation | Current result |
| --- | --- |
| Empty preflight and original eight-table apply | Harness prepared; **not executed** |
| Additive ninth table preserving original sentinel | Harness prepared; **not executed** |
| Repeat migration and nullable/unique Discord/XUID constraints, max unsigned XUID string | Harness prepared; **not executed** |
| Concurrent identity claims/overwrite refusal | Harness prepared; **not executed** |
| Repeated ingestion, overlap union and anomalous-end quarantine | Harness prepared; **not executed** |
| Independent dump/restore and full row comparison | Harness prepared; **not executed** |
| Partial DDL resume and incompatible schema refusal | Harness prepared; **not executed** |

Offline guard tests are not substitutes for this table. The harness has not yet
demonstrated real MariaDB behavior, container startup or dump/client compatibility.

Offline validation: **359 passed, 1 platform skip** across the tracked Phase 4/6
regressions plus the initial 21 harness guard cases. After adding three positive
Docker Desktop/Unix-context cases, all **24 harness tests passed**. Ruff F and Python
compilation checks passed. Tests use fake Docker responses and synthetic SQLite;
they neither provisioned MariaDB nor loaded production credentials. The only suite
warning was the existing discord.py `audioop` deprecation. Final branch CI is an
additional release gate, not a replacement for the unexecuted MariaDB checks.

### Exact local setup after the owner installs Docker Desktop

All commands below are prospective, from the repository root in PowerShell.
Use a clean maintenance checkout of the reviewed Phase 6 revision, Python 3.12
with the pinned development dependencies, and a local Docker context. Never copy
production `.env`, keys, data or credentials into this setup. If Docker Desktop
cannot be installed, use a separately approved local Linux machine with Docker;
do not point the harness at a remote or production database as a shortcut.

1. Install/start Docker Desktop following the linked official instructions, select
   Linux containers/WSL 2, and verify its prerequisites. An installation/reboot or
   virtualization change needs owner control. Confirm:

   ```powershell
   docker --context default version
   docker --context default compose version
   docker --context default context inspect default
   ```

   The harness accepts a local named pipe or local Unix socket only. If the local
   Desktop context is `desktop-linux`, use that context consistently in all commands
   and pass `--docker-context desktop-linux` to the harness. Do not use TCP/SSH Docker.

2. After the owner confirms the target version, pull and pin the official image:

   ```powershell
   docker --context default manifest inspect mariadb:12.3.3
   docker --context default pull mariadb:12.3.3
   $captainStageImage = (docker --context default image inspect --format '{{index .RepoDigests 0}}' mariadb:12.3.3).Trim()
   ```

   **Stop on any failure.** Review the digest and use the same digest for both
   containers; the tag's availability is not established by this audit.

3. Create a new protected staging-only env file. Do not reuse an existing one.
   The password generator is local; no Microsoft/Discord credentials are involved.

   ```powershell
   $env:CAPTAIN_STAGE_IMAGE = $captainStageImage
   @'
   from pathlib import Path
   import os, secrets
   from utils.integrations.realms.token_store import private_permissions, reject_links
   root = Path('.test-tmp/phase6-mariadb').absolute()
   reject_links(root)
   root.mkdir(mode=0o700, parents=True, exist_ok=False)
   private_permissions(root, create=True)
   target = root / 'stage.env'
   descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
   with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
       stream.write('CAPTAIN_STAGE_IMAGE=' + os.environ['CAPTAIN_STAGE_IMAGE'] + '\n')
       stream.write('CAPTAIN_STAGE_PASSWORD=' + secrets.token_hex(32) + '\n')
       stream.write('CAPTAIN_STAGE_ROOT_PASSWORD=' + secrets.token_hex(32) + '\n')
   private_permissions(target)
   '@ | .\.venv\Scripts\python.exe -
   if ($LASTEXITCODE -ne 0) { throw 'Private staging setup failed' }
   Remove-Item Env:CAPTAIN_STAGE_IMAGE -ErrorAction SilentlyContinue
   Remove-Item Env:CAPTAIN_STAGE_PASSWORD -ErrorAction SilentlyContinue
   Remove-Item Env:CAPTAIN_STAGE_ROOT_PASSWORD -ErrorAction SilentlyContinue
   ```

   Stop if permission/file creation fails. Keep this file Git-ignored and private.
   Explicit `--env-file` below avoids Compose's implicit repository `.env` loading.
   Do not print `docker inspect`, `compose config`, container env or initialization
   logs: those can expose the synthetic database passwords.

4. Provision only the two disposable containers, then execute the bounded harness:

   ```powershell
   docker --context default compose --env-file .test-tmp/phase6-mariadb/stage.env -p captain-phase6-stage -f config/phase6-staging.compose.yml up -d --wait
   ```

   Stop if this command fails; do not reuse an existing/nonempty schema. Then:

   ```powershell
   try {
     $env:CAPTAIN_STAGE_PASSWORD = (Get-Content -LiteralPath '.test-tmp/phase6-mariadb/stage.env' | Where-Object { $_.StartsWith('CAPTAIN_STAGE_PASSWORD=') }).Substring('CAPTAIN_STAGE_PASSWORD='.Length)
     .\.venv\Scripts\python.exe -m scripts.phase6_mariadb_validation --image $captainStageImage --version 12.3.3 --allow-synthetic-ddl
     if ($LASTEXITCODE -ne 0) { throw 'Staging validation failed; preserve containers for review' }
   } finally {
     Remove-Item Env:CAPTAIN_STAGE_PASSWORD -ErrorAction SilentlyContinue
   }
   ```

   A pass must list all checks and both observed server versions/SQL modes/charsets.
   Compare those against owner-supplied production metadata before closing compatibility.
   Review information_schema column types/precision/collations as well as nullability,
   keys and engines. The existing timestamps use naive UTC database values and
   MariaDB `DATETIME` precision; do not assume microseconds survive.

5. Preserve the sanitized result and reviewed digest in the readiness record. Only
   after success or explicit failure-review approval, remove the owned containers:

   ```powershell
   docker --context default compose --env-file .test-tmp/phase6-mariadb/stage.env -p captain-phase6-stage -f config/phase6-staging.compose.yml down --timeout 10
   Remove-Item -LiteralPath '.test-tmp/phase6-mariadb/stage.env'
   Remove-Item -LiteralPath '.test-tmp/phase6-mariadb'
   ```

   This discards only disposable synthetic databases. Do not run Docker-wide prune,
   delete other containers/volumes or automatically retry a failed harness.

## Production architecture audit

| Area | Source-verified behavior / release requirement |
| --- | --- |
| Database configuration | `utils/configuration.py` loads secret connection bootstrap from environment; operational settings come from `botdata.settings_json` row 1. Prefix remains the SQL field. No seed/reset import is needed for Phase 6. `make_database` requires encrypted transport; prior self-signed acceptance is explicit, never silently downgrade TLS. |
| Migration | Recorded production already has the eight profile tables. `migrations.realm_activity` plans all eight plus `captain_realm_activity`, creating only missing tables after schema preflight and backup assertion. Import/startup does no DDL. Current production schema is unqueried; preflight must determine the actual plan. |
| Preflight limitation | Existing migration checks column **names**, unique indexes and InnoDB, but does not establish matching column types, nullability, primary/foreign keys or collation. The staging harness adds PK/FK/nullability checks; a production operator must inspect complete definitions before apply. Do not treat an empty missing-table plan as full schema equivalence. |
| Flags | Seed has `profiles_enabled`, `checkin_enabled`, `checkin_announcements_enabled`, `checkin_reminders_enabled` false. `realm_history_enabled` is optional, absent/false by default, requires profiles. Existing runtime values were not read. Preserve `realms` and `realm_panel` blocks exactly; do not disable Phase 4 while keeping new flags off. |
| Profile permissions | Profile operations use `@op_team()` plus Coastal guild scope, are registered only to that guild, and report privately. The role check uses `OPTeamRole`, default **name** `OP Team` (or a configured integer ID). This differs from Realm commands, which require numeric `CoastalOPTeam`. Owner must approve that policy or separately authorize setting `OPTeamRole` to the independently verified role ID. No role/config change made here. |
| Check-in permissions | `/checkin report`, `history`, `announce` and staff eligibility operations require OP checks; `/checkin status` and the button are intentionally member-facing. Status can create the current period and refresh the member's inactive profile flag even when scheduling is off. A status command is not a no-write validation probe. The button refuses check-ins when `checkin_enabled` is false. |
| Profile activation side effects | `Players.cog_load` checks existing tables, registers a persistent check-in view, and starts 15-minute inactive reconciliation if configured. Member join/role-update listeners also mirror inactive state. Existing application submissions can capture current profiles/identities/participation when profiles are enabled. These are real database writes independent of historical imports and require explicit activation approval. |
| Inactive role | Discord's configured inactive role is authoritative. Synchronization updates existing linked profile flags; it never grants/removes roles or uses activity to change eligibility. Missing guild role/membership makes eligibility unavailable rather than guessing. Verify member-cache/intents and role existence before activation. |
| Persistent views | Monthly view uses `timeout=None` and stable `captain:monthly-checkin:v1`; it is registered only when profiles load and checks the saved current period/message/channel on click. No historical announcement repair/new send is implied by startup. Existing application/guide/POI flows must keep their messages/interactions; do not recreate or republish them as a rollout test. |
| Phase 4 panel | Existing runtime/store/name cache/session persistence and panel message configuration remain unchanged. Panel durations use first observed live presence, never Stories starts/ends. Staff history uses the shared runtime with independent cache/backoff and no scheduler. Private history requests can briefly share its lock; do not test/retain history during the initial Phase 4 regression window. |
| Host/runtime | Recorded Apollo access is SFTP, not an SSH execution shell. Prior preparation reports Python 3.14, whereas repository CI tests Python 3.12. A designated maintenance executor and actual-host interpreter/dependency checks are required; no fresh host revision/runtime was verified here. |
| Restart workflow | `.github/workflows/my_workflow.yml` runs on **main push**, serializes deployments without cancelling earlier ones, installs pinned dependencies in its runner and calls `scripts/panel_deploy.py --restart-and-verify --expected-revision "$GITHUB_SHA"`. It verifies source/ready revision after the restart; it does not apply migrations/flags. An immutable expected SHA is verified, not automatically pinned into an arbitrary host startup command. |
| Recovery | Independent private database/config backup and sole-writer Realms-store recovery are required. Roll back flags/code through separately approved maintenance; retain additive tables/data. Never drop the ninth table, reset settings from the seed or restore an old whole database over new writes automatically. |

No confirmed production runtime defect was fixed during this audit. The material
findings are preflight coverage limits, activation side effects, different staff-role
selectors, an unverified deployed revision/runtime, and unavailable staging. They
must be addressed by the checkpoints below; no current readiness claim hides them.

## Deployment runbook — do not execute without checkpoint approval

Every checkpoint is independent. This document grants none of the production actions.
Use an approved maintenance executor with the exact reviewed checkout and protected
environment; SFTP file access alone cannot execute these commands. No new interactive
Minecraft login, Realm setting/permission change, archive work or automated verifier
is needed. Stop on failed checks instead of proceeding to the next checkpoint.

### 1. Recovery baseline and backup — owner approval A

Before production access, approve read-only inventory and private backup/restore
handling, maintenance owner, connection target and rollback revision. Reconfirm:

```sql
SELECT VERSION(), DATABASE(), CURRENT_USER(), @@hostname,
       @@sql_mode, @@character_set_server, @@collation_server;
SHOW SESSION STATUS LIKE 'Ssl_cipher';
```

Keep host/account values private. Compare target and TLS to the owner's inventory.
Record table definitions/counts, FK/index/engine/type/precision/nullability/collation,
all five new feature flags (including an absent history flag), current `realms`/
`realm_panel` checksums, configured message IDs, private-store ownership and current
running/rollback SHA. Do not print settings documents or encrypted-store keys/tokens.

Use a private client-options file populated by the owner/secret manager with only
the approved backup target/account and the existing TLS policy (never password args).
For an approved executor with MariaDB clients, the backup command template is:

```sh
mariadb-dump --defaults-extra-file=/private/captain-backup.cnf --single-transaction --routines --events --triggers --hex-blob --skip-add-drop-table --result-file=/private/captain-before-phase6.sql APPROVED_SCHEMA
sha256sum /private/captain-before-phase6.sql
```

`APPROVED_SCHEMA` is replaced only after matching the inventory. Require restrictive
owner-only file permissions and independent/off-host storage. Coordinate a no-DDL
window; verify dump completeness, permissions and exit status. Obtain separate
approval to restore this real-data backup into a **private isolated recovery target**,
not the synthetic harness, and compare definitions/typed values/counts. Any definer,
routine, privilege or restoration error stops release. Back up canonical settings,
approved host runtime configuration and Realms state through the established protected
sole-writer method; do not acquire a second token-store lock or copy back credentials.

**Checkpoint:** fresh independent backup + actual restore evidence, exact target,
recovery owner, staging pass, proposed release SHA and all new flags off. No DDL yet.

### 2. Additive schema only — owner approval B

Use the exact reviewed Phase 6 code in an isolated maintenance checkout, with its
root `.env` deliberately supplied for the approved **production** target only at this
checkpoint. These are production commands, never the local staging recipe:

```sh
python -m migrations.player_registry
python -m migrations.realm_activity
```

They connect for preflight and load that checkout's `.env`. Expect no missing original
tables if the recorded baseline remains accurate and, at most, the ninth activity
table. Inspect full existing definitions independently because of the noted preflight
limits. Any unexpected original-table absence, schema mismatch or engine stops review.

After explicit approval of the exact plan and backup evidence:

```sh
python -m migrations.realm_activity --apply --backup-verified
python -m migrations.realm_activity
```

Verify nine expected tables, definitions/indexes/FKs/engines and unchanged original
records/settings. A partial failure may leave committed DDL: preserve evidence,
inspect actual tables, obtain approval of a revised plan before resume. No automatic
drop, rollback transaction assumption, import or feature enablement.

### 3. Exact code rollout with flags off — owner approval C

Confirm the exact full reviewed SHA and all its CI checks, clean release checkout,
protected sole-writer store, unchanged configuration, and actual host Python/dependency
compatibility. On the approved host executor, `python --version` and
`python -m pip check` must pass against the selected runtime; Python 3.12 CI alone
does not validate Apollo's recorded 3.14 environment. Review the startup checkout/update
behavior before changing main; no workflow run is a substitute for that evidence.

The owner then approves a specific merge/main update and its automatic restart.
Use the repository's normal reviewed PR flow; do not blindly merge the development
branch's latest mutable head. The resulting main SHA is the release target, including
any merge commit. Check its exact diff/CI and coordinate the main-push trigger.
The workflow executes, with hosting secrets already configured:

```sh
python scripts/panel_deploy.py --restart-and-verify --expected-revision REVIEWED_MAIN_SHA
```

`PANEL_URL`, `PANEL_API_KEY`, `PANEL_SERVER_ID` must be supplied privately by the
existing secret manager; never put values in Git/arguments. **Do not also run this
command manually when the main-push workflow is deploying**: it is the documented
workflow command, not an instruction for a second restart. If actual source/ready
revision differs, stop and review the startup behavior instead of retrying restarts.

### 4. Phase 4 regression with new features off — checkpoint D

During the approved rollout observation window, check the existing configured panel
message refreshes, uses the same Realm, preserves private session state, resolves
names, labels observed duration, handles unknown/stale data without fabricating
offline, and shows no unexpected duplicate messages/commands. Verify private Realm
command permissions and cooldowns using the approved staff identity. Check application,
guide and POI entry points remain present; do not submit new applications or republish
messages solely to test them. No Stories request, archive read, profile write or
credential renewal diagnostic is implied by these checks. Approve any extra live
sampling budget separately. New profile/check-in/history flags must remain off.

**Checkpoint:** exact ready revision, Phase 4 acceptance and unchanged recovery/config
baseline. Failure stops activation and invokes only an approved flag/code recovery.

### 5. Profiles alone — owner approval E

Approve profile side effects listed in the audit, numeric-vs-name staff-role policy,
private access/retention, member-cache/intents, and manual staff identity-link policy.
No archive source investigation or import is part of this step. The settings tool
changes only one reviewed key and preserves unrelated operational settings:

```sh
python -m migrations.botdata_settings --set profiles_enabled --value true
python -m migrations.botdata_settings --set profiles_enabled --value true --replace-existing --apply --backup-verified
```

The first command is a preview, not permission for the second. Verify its changed
key list, the saved document checksum and all remaining new flags false. Existing
runtime reads settings on startup; the approved profile activation therefore also
needs an explicitly approved controlled restart of the **same reviewed release**,
not a second merge. Do not hot-edit `bot.settings` to evade startup gates.

If the owner elects numeric OP-role enforcement, separately preview/apply
`--set OPTeamRole --value VERIFIED_ROLE_ID` through the same settings tool after
verifying that ID; this affects all users of the shared OP check, not only profiles.
Do not substitute `CoastalOPTeam`'s private value without verification/approval.

### 6. Staff-only commands and view checks — owner approval F

After profile startup, synchronize **only the Coastal guild** through the existing
administrator command (`%sync COASTAL_GUILD_ID` if the recorded `%` prefix remains
current), not global/all-guild sync. This is a Discord write and needs approval.

- Verify authorized staff can access private profile commands and ordinary members
  cannot; verify wrong-guild calls are denied and attachments remain ephemeral.
- Prefer permission/empty-result checks; `/playerprofiles view` can refresh inactive
  state, and `/checkin status` can create a period. Approve these writes explicitly
  before invoking them. Do not run `setup`, `preview`, discovery, `review`, `import`,
  `link`, `xboxlink`, eligibility changes or `reconcile` as an accidental archive/identity
  workstream. Profile creation/linking needs its own evidence/write approval.
- Verify `captain:monthly-checkin:v1` is registered once, existing buttons fail closed
  while check-ins are disabled, and no scheduler announcements/reminders or history
  collection starts. No new announcement/message is required for this validation.
- Observe that inactive-role mirroring and live submission capture match the approved
  profile side effects. No Discord role assignment/removal is permitted by Phase 6.

### 7. Optional later check-ins and history — separate approvals G/H

Check-ins: approve timezone/season, linked-member policy, existing inactive role,
channel privacy, announcement duplicate-delivery recovery and reminder handling.
Preview each setting separately using `migrations.botdata_settings --set KEY --value JSON`;
apply only with the existing replacement/backup flags after approval. Enabling
`checkin_enabled` starts period scheduling after restart even while announcements
and reminders remain false. Enable each messaging flag only with separate approval;
the first announcement/send is a production action, not a preview. No bulk archive
import is required or authorized.

History: only after schema, verified Xbox ownership, privacy and retention approval,
preview `--set realm_history_enabled --value true`, then separately approve apply
and restart. Approve one staff `/playerprofiles activity confirm:false` request with
the shared runtime's cache/retry policy understood. Inspect age/quarantine/unmatched
counts before separately authorizing `confirm:true` to retain that snapshot. Flag
enablement is not blanket retention approval. Keep all data private and label it
observed interval coverage, never exact playtime. No automatic corroboration,
leaderboard, duration replacement or collection scheduler is implemented or approved.

## Recovery and remaining approvals

On a Phase 4 regression, wrong identity/Realm, mismatched schema/ready SHA, unexpected
write/send, privacy error or duplicate delivery: stop the rollout. Preserve private
diagnostics and obtain owner approval for the recovery action. Disable history and
new messaging first through the reviewed settings tool; disable profiles only after
dependent flags are off because configuration validation rejects invalid combinations.
Apply settings changes and restart the approved runtime only under recovery approval.
Guild command removal/sync is a separate Discord write. Retain additive tables and
new records; neither rollback code nor purge/reset settings automatically. Never run
two bot instances or two writers against the credential store.

Current approvals still needed: Docker installation/setup and matching-image/version
confirmation; a successful synthetic MariaDB run and metadata comparison; current
production inventory/private backup and restore authorization; a maintenance executor
and runtime confirmation; exact schema/release approvals B/C; then optional profiles,
command sync, identity/retention, check-ins and history approvals E–H. Current task
authorization covers preparing the harness/runbook and synthetic validation only;
**none of these production approvals has been exercised**.
