# Player registry and monthly check-ins

Implemented in development on October 28, 2026. No production database migration,
historical import, Discord announcement, reminder, command sync or deployment was performed.
Every feature defaults off. Obtain owner approval before those production actions.

## Inspection and architecture

The active runtime uses discord.py 2.7.1, Peewee 3.19 and encrypted MySQL/MariaDB.
`DatabaseProxy` and per-worker `connection_context()` remain the connection boundary.
Existing migrations are explicit Python modules with read-only default preflights;
startup does no schema DDL. Production `botdata` and `administrators` remain untouched.
Historical `PortalbotProfile` references in `!archive` do not establish a usable current
registry. No active profile, XUID resolution, scheduler or persistent check-in view existed.

Applications are in the configured first Sheets worksheet. The current bot writes the
Discord ID directly from the interaction into D, gamertag into E, timestamp into T,
and approval into U. Row 1 is metadata, row 2 labels. Approval invites someone to the
Discord community; it does not prove Realm access. Guide verification assigns guide/active
roles under existing rules; their names alone do not prove the intended check-in eligibility.
Markers, guide verification and existing application commands retain their contracts.

Google authentication retains Captain's existing dedicated service account, gspread
client, existing scopes and serialized worker. Spreadsheet key/title precedence is unchanged.
Archive discovery uses that same authenticated HTTP client for paginated Drive v3 listing
and bounded Sheets reads. It performs no Google writes. No additional Google SDK is required.

Implementation order: additive registry and migration; source adapters and review queue;
confirmed imports; period/check-in tracking; persistent button; delivery claims/scheduler;
private commands, tests and this runbook. The plan was reported before implementation.

## Archive inspection evidence

The supplied [archive](https://drive.google.com/drive/folders/0B43virBKP-AQQk9EX0duN2pjQ1E)
and season folders were listed read-only using the connected **Coastal Craft** Google
account. Only bounded header/metadata reads were needed; player rows were not exported.
These are inspected source layouts, not an assertion that all applications are complete.
Grid row counts include empty capacity and are **not application counts**.

| Season | Discovered source ID | Observed layout |
| --- | --- | --- |
| 3 | `1-3s1Q_TxEm0jVp5g0QVJ8dwlatfBiw5VSRekViIQRDk` | Coastal Members Season 3; Sheet1, header row 4, five frozen rows, roster with Band Name / Gamertag / Realm?; Sheet2 also exists and is not an audited source |
| 4 | `1eqlTwo1NgyVKv0g6m42AuAtEhPnBmE2Q-2ABX5e8VIE` | Form Responses 1; timestamp A, mixed contact B, gamertag C; invitation field is not treated as approved/current membership |
| 5 | `1xErJYBCcwEDsYQsOAvtCXhJmQvLE0nln8Pw6hYuqR_g` | Form Responses 1; mixed contact A, gamertag B, timestamp K |
| 6 | `1tKv8yT5G_FigFj4AgQ0VjNH3WZ74ue2hZzaPzxV-pMw` | Same identity layout as Season 5; spreadsheet timezone Etc/GMT |
| 7 | `1Gp739udTdrJ9sFyk6xJYtIZQl7k73u06Cs1uxXp1I9M` | Same identity layout as Season 5 |
| 8 | `1TudYa9i1509mN0xVAh0zRjm8gi69LsSBhy5QMWRjp_g` | Form Responses 1; row 2 labels; Discord ID D, tag E, timestamp Q, approval R |
| 9 | `1tgIB6ge4xYWY0IOIVqGN70Bv8-xJ-wminoIphNCqjt0` | Form Responses 1; row 2 labels; timestamp T, approval U |
| 10 | `1ltMnItNgDBk5FhgsC-afi0l17OBnfOTcKPIkcSw9zvE` | Form Responses 1; current application layout, timestamp T, approval U |

Additional sources requiring season/source review: Season 4 Files also contains
`1P0xHNd-Y9xWfxwfTIn2CyYteQ4DYT0pvJ49zdeshwU0`, an older untitled-season application
response workbook; Season 5 Files contains `1nOm20g7W3zGhh-kCMWw33OrFIDz67zZPQxDZlqJ198g`,
named Coastal Members Season 4. Folder season is only a proposal: override that workbook's
season/header before discovery. Forms themselves are reported unsupported; response
spreadsheets are the supported source. Guide-agreement sheets were discovered but are not
application adapters. Alternative Coastal8, Coastal Season 6 and Coastal Season 4 folders
contain world/game files; no application file was visible at those roots. World databases,
packs, screenshots and arbitrary nested world folders are deliberately not parsed.

No inspected season source was inaccessible to the connected account. **Captain service-account
access to the archive has not been tested in this change.** Sharing with the interactive account
does not establish service-account access. Share needed folders/workbooks read-only with
`thecaptain@thecaptain-513018.iam.gserviceaccount.com`, retain existing Sheets/Drive API
enablement/scopes, and run discovery after approved deployment. Inaccessible folder/file IDs,
unsupported forms/layouts and partial read failures appear in the durable discovery report;
never interpret a partial discovery as a complete archive. No permissions were changed here.

## Schema and migration

All tables use the existing Peewee proxy and database engine; SQLite is used only for tests.

| Table | Purpose and constraints |
| --- | --- |
| `captain_player` | Stable AutoField player ID; nullable unique Discord ID and XUID; current names, first known application/season, membership, UTC create/update timestamps |
| `captain_identity` | Player, identifier kind/value, verified flag, source record key, observation timestamp; unique player/kind/value/source |
| `captain_participation` | Player/season/source unique; application date/status, observed Discord membership, explicit Realm tracking status |
| `captain_import_record` | Immutable unique SHA-256 source key, identity-only payload, state, linked player, reviewer/time, matching evidence; full source reference retained |
| `captain_discovery_run` | Durable source inventory, source failures and dry-run counts; actor and UTC run timestamp |
| `captain_checkin_period` | Unique guild/season/year/month, announcement channel/message IDs, delivery/report states |
| `captain_checkin` | Unique player/season/year/month, UTC check-in timestamp, actor Discord ID, source and announcement message |
| `captain_reminder` | Unique period/player/reminder-day; durable claim, delivery status and attempt timestamp |

Peewee foreign keys link identities, participation, imports and check-ins to players, and
reminders to periods/players. No cascade-delete workflow or retention purge exists.
Imported identity history references `captain_import_record.key`; join it to recover the
original workbook/entry URL and identity payload. Observation time is import time, not an
invented historical verification timestamp. Authenticated check-in interactions record current
Discord usernames with a `discord_guild:<id>` source, retaining prior username observations.
Parsed application timestamps retain their raw
source value in the import payload; old local timestamps do not assert a UTC instant.
Roster records have no invented application date or application approval.

Development/operator commands from the repository root:

```shell
python -m migrations.player_registry
# After owner approval, verified independent backup, and a maintenance window:
python -m migrations.player_registry --apply --backup-verified
```

Preflight lists missing tables and checks existing columns/unique indexes. It refuses
unexpected existing registry schemas and non-InnoDB registry tables. MySQL/MariaDB apply sets
the migration session's default engine to InnoDB so new tables support transactions.
Apply creates missing registry tables only, never
alters/deletes old tables or application data. MariaDB DDL can auto-commit: take a consistent
independent backup with the deployment's approved backup procedure and verify restoration
in an isolated database first. Keep backup files and credentials outside Git. Partial additive
DDL can be retried after inspection; do not drop partially created tables containing records.

Rollback: disable all new feature flags, restart the prior runtime, and retain the additive
tables and all check-in history. Old runtime ignores them. Restore the independent backup
only as an explicitly approved maintenance operation with all writers stopped; it can discard
post-backup records. There is deliberately no destructive automated down-migration.
Live MySQL DDL/locking has not been exercised here; validate in staging before production.

## Identity discovery, review and import

1. Enable `profiles_enabled` only after migration approval and staging validation. Keep all
   check-in switches off. Sync guild commands manually through the existing staff sync workflow.
2. Run `/playerprofiles setup`. It chunks the Coastal guild member cache when needed, paginates
   Drive files, reads at most 200 worksheet rows per request and stores a private review queue.
   It does **not** create player profiles or import season records. This is a data dry run,
   although it intentionally persists the review queue and aggregate report in the database.
3. Retrieve `/playerprofiles discovery` for the durable summary, including source failures,
   counts by season, candidate counts, repeated stable identities, duplicate-name groups,
   unmatched historical records and current members without linked profiles. Candidate counts
   are conservative estimates, not verified unique people. Fuzzy suggestions are not identities.
4. `/playerprofiles reconcile page:1` pages pending/rejected/approved records (20 per page).
   Reports and larger text attachments are ephemeral. Keep copies private if staff downloads them.
5. Independently review each association. `/playerprofiles review record_id:... reject:False`
   approves a separate new profile; supply `player_id` to attach that source to an existing
   profile, and/or `member` to confirm a missing/unverified Discord association. Use `reject:True`
   to exclude a source. Existing verified identifiers cannot be overwritten through this flow.
6. Only after explicit administrator confirmation run `/playerprofiles import confirm:True`.
   Only individually approved records are imported. Each record is its own transaction.
   Interrupted operations leave approved rows retryable; conditional claims and unique keys
   prevent duplicate history. Review conflicts remain blocked and are listed by record ID.
7. View historical players with `/playerprofiles view player_id:...`, including applicants who
   left Discord. A selected Discord `member` is also supported. Pagination applies to history.

Matching uses verified Discord IDs, then verified XUID associations, with conflicts blocked if
they point to different players. Stored verified identifier history is consulted. Exact names,
old names and fuzzy names are suggestions only. Older mixed contact columns are **not** treated
as Discord usernames or IDs and are not stored: they can contain emails or forum handles.
No live XUID verification service was found, so none is invented. The observed bot-generated
Season 8+ ID columns are trusted by default; set `trusted_discord_ids: false` per source if its
provenance cannot be established. Malformed/rounded IDs are rejected. Imported names fill empty
current fields and retain history; they do not overwrite populated current profile fields.

Bot application entry IDs provide stable source keys despite row insertions/sorts. Older
form/roster keys hash source, season, available identity and parsed application date. Truly
identical old identity/date records collapse; missing dates can make this uncertain. Changed
source snapshots are counted for staff review and never silently replace approved/imported
payloads. There is no automatic destructive player-to-player merge, identity correction or
history deletion command. Conflicting verified identifiers and already imported source
corrections require an evidence-backed, separately authorized maintenance change.

New live submissions mirror identity into the registry when profiles are enabled, and live
approval changes update the associated participation application status. These are trusted bot
events, distinct from historical import approval. Fresh submissions can refresh unverified current
names while preserving history; decisions on old applications do not revert current names.
A failed registry mirror never retries the
successful Sheet write or changes the user's application result; sanitized logs direct staff
to reconcile the current Sheet. A previously staged archive source still requires review.

## Configuration and eligibility

See `botconfig.example.json`. Defaults preserve existing behavior:

```json
{
  "profiles_enabled": false,
  "checkin_enabled": false,
  "checkin_announcements_enabled": false,
  "checkin_reminders_enabled": false,
  "checkin_timezone": "America/Chicago",
  "checkin_season": 10,
  "checkin_season_name": "The Mighty Mesa Reborn",
  "checkin_channel_id": 504140612019421184,
  "checkin_staff_channel_id": 1565171730480111716,
  "checkin_eligible_role_id": null,
  "checkin_reminder_days": [15, 25],
  "profile_sources": {}
}
```

`profile_sources` maps observed workbook IDs to audited overrides: `season`, `header_row`,
`worksheet`, `trusted_discord_ids`. It does not grant access. For the cross-filed Season 4
roster in Season 5 Files, configure its ID with `season:4` and verify its header/worksheet
before importing. Unknown layouts are reported and need a tested adapter; do not guess columns.

The owner supplied announcement channel `504140612019421184` and staff-report channel
`1565171730480111716`. These are included in the configuration example; live guild ownership,
bot permissions and staff-channel privacy still need verification. Leaving
`checkin_eligible_role_id` null selects staff-managed eligibility. No separate deployment
configuration format is needed: add these keys to the running bot's existing private
`botconfig.json`; existing environment variables retain the token/database connection settings.
Do not replace the running configuration with the example, which includes zero placeholder
IDs for other required settings. The private files are not present in this development checkout.

Eligibility requires a linked profile, a current human Coastal guild member and **either**
the explicitly configured eligibility role **or**, when no role is configured, a current-season
`staff_eligible` participation record. The configured role takes precedence. Existing active/
guide roles are not selected automatically. Configure a role only after staff confirms its
meaning. Role-based eligibility is an administrative assumption about membership; staff-managed
eligibility is an explicit attestation, and neither asserts automatic Realm API verification.
Historical applications and Discord membership alone never qualify someone.

`/playerprofiles link member:... gamertag:... confirm:True` provides a staff-confirmed identity
path when there is no application; it grants no eligibility. `/playerprofiles eligibility
member:... eligible:True|False` sets the staff-managed current-season tracking status. It does
not assign Discord roles or modify Realm access. Existing status values distinguish unknown,
staff eligible and staff ineligible. Do not delete profiles when someone leaves Discord.

All registry commands and administrative check-in commands use the existing `op_team()`
runtime role check and enforce the configured Coastal guild. `/checkin status` is available
to the requesting player. No sensitive reports are sent publicly. Staff reports require a
channel in Coastal that denies @everyone View Channel; also review all role overrides before
enabling it. The bot requires member intent/cache access, announcement View Channel/Send Messages/
Embed Links/Read Message History and staff-channel send permissions; recipients must allow DMs.

`tzdata` is the one added runtime dependency, needed for IANA timezone rules on Windows.
Reminder dates are distinct integers 1–28 so every configured date exists in every month.
No scheduling or reminder switch can cause a production action until deployed and enabled.

## Monthly operation and recovery

Periods are computed in the configured timezone at use time and explicitly store year/month/
season. Calendar months, leap years, DST and December/January rollover use `zoneinfo`.
The scheduler checks every 15 minutes after Discord readiness and catches up after restarts;
the first announcement may therefore be up to 15 minutes after midnight (or bot recovery).
Only the current configured season is scheduled; changing seasons preserves old records.

The persistent `captain:monthly-checkin:v1` button is registered at startup whenever profiles
are enabled. Each click defers privately, checks guild/channel/current announcement message,
linked Discord ID and current eligibility, then atomically inserts the unique player/season/
year/month check-in. Repeated clicks return an already-completed response. An old announcement
cannot check someone into a new period. No profile is implicitly approved by a click.

Announcements use a unique period row and a conditional **claim before send**. Successful sends
store message/channel IDs. A network error or crash between claim/send/save leaves a claimed
state; the scheduler does not resend automatically. Discord and MySQL cannot share a transaction,
so exactly-once delivery across that crash window is impossible. Inspect channel history first:
`/checkin announce` repairs the saved existing message; a confirmed 404 deletion is safely
replaced. For an uncertain claim with no saved message, only after verifying no message exists
use `/checkin announce confirmed_absent:True`. Permission failures are not treated as deletion.
Exactly one bot writer is still required, as for existing Sheets operations.

Due reminders use the same claim-before-send policy per period/player/day. Restarting never
retries a failed/uncertain DM for that reminder stage. A later configured stage is a separate
attempt. After downtime, only the latest due stage is delivered; earlier stages are not blasted
in succession. Checked-in players are skipped and records are rechecked immediately before send.
Claimed attempts mean uncertain/interrupted; failed means Discord rejected delivery; sent means
the API returned success. There is no automatic kick, role removal or Realm removal.

After the final configured reminder date, one private staff-channel summary reports completion
and failed/uncertain DM totals; `/checkin report` supplies paged player IDs and delivery results.
The report state is claimed before sending, so an interrupted staff summary also needs manual
inspection. The summary is a snapshot; use the command for fresh counts. Scheduling does not
backfill announcements or DMs for completely missed historical months.

Commands:

| Command | Behavior |
| --- | --- |
| `/checkin status` | Requester's current month, linkage, eligibility and completion |
| `/checkin report page` | Staff: period, eligibility basis/count, completion %, missing player/Discord IDs, reminder outcomes and announcement/report states |
| `/checkin history member|player_id page` | Staff: retained historical monthly records, including departed players via internal ID |
| `/checkin announce [confirmed_absent]` | Staff: explicitly create/repair current announcement; respects enable switches |
| `/playerprofiles setup` | Staff: source discovery and staged dry-run matching |
| `/playerprofiles discovery` | Staff: durable latest discovery summary and source failures |
| `/playerprofiles reconcile page` | Staff: review queue and identity suggestions |
| `/playerprofiles review record_id reject [player_id] [member]` | Staff: explicit per-source approval/rejection and confirmed identity association |
| `/playerprofiles import confirm` | Staff: import approved records only |
| `/playerprofiles view [member] [player_id] page` | Staff: profile, participation and identity history |
| `/playerprofiles link member gamertag confirm` | Staff: independently confirmed member identity without an application |
| `/playerprofiles eligibility member eligible` | Staff: current-season eligibility attestation |

## Deployment checklist and development validation

1. Review code, source mapping, MySQL preflight and a restorable private backup in staging.
2. Obtain explicit owner approval for production migration; run the explicit additive apply.
3. Install pinned requirements, deploy code with only profiles enabled, and manually sync guild
   commands through the existing sync command. Verify service-account access via discovery.
4. Review inaccessible/unsupported sources and ambiguous identities before authorizing imports.
   Run confirmed imports only with administrator approval; re-run safely after interruption.
5. Staff must establish eligibility, configure real channels and timezone/season, and approve
   enabling check-ins/announcements. Verify one announcement and the restart-persistent button.
6. Obtain separate approval before enabling reminders; confirm staff channel privacy and DM timing.
7. Monitor sanitized failure logs and private reports. Roll back by disabling flags and retaining data.

Automated tests block external connections and use synthetic temporary SQLite files plus mocked
Google/Discord calls. Coverage includes migrations and backup gates; form/roster/bot parsers;
missing/conflicting IDs; exact/fuzzy name suggestions; review/rejection; idempotent imports;
season history; live application mirroring; atomic check-ins/repeated clicks; current-message/
guild checks; restart-safe view and delivery claims; month/year/DST/leap boundaries; reminders;
failed DMs; staff permissions; private staff reports; source failure reporting and Drive pagination.

```shell
python -m compileall -q main.py utils migrations tests
python -m ruff check --select F main.py utils migrations tests
python -m pytest -q
```

On restricted Windows runners, pytest needs access to asyncio's local loopback socket and a
writable temporary directory. It still blocks external network calls through the test fixture.
Two existing test expectations were stale before this work (the existing guide-announcement
command and an interaction mock without `guild`); they were corrected to match existing behavior.
Production Discord delivery, live MariaDB migration/concurrency and archive completeness remain
operator/staging checks, not claims inferred from mocked tests.

Final development validation: **141 tests passed**, with one existing discord.py `audioop`
deprecation warning. Compileall, Ruff undefined/unused-name checks, `git diff --check`, and the
installed dependency consistency check passed. No production actions were performed.
