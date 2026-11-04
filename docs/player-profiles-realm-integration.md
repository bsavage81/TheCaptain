# Phase 6: player profiles and observed Realm history

Development branch: `codex/realms-phase6`, based on Phase 5 plus the successful
Stories investigation. Production remains disabled; no deployment or live imports.

## Audit before implementation

The existing eight-table Peewee registry already supports canonical player IDs,
unique nullable Discord IDs and XUIDs, identifier evidence/history, Season 3–10
source adapters, staff review and idempotent approved imports. Names are suggestions,
not automatic merge keys. Monthly buttons, calendar periods, reminder delivery
claims, private OP Team reports and inactive-role reconciliation already exist.
The registry schema was previously created in production but the registry and
announcement features remain disabled according to the existing execution notes.
No production flags or database records were changed. A later read-only table-count
check is recorded in the preview section below.

Inactive role `547138462357258242` remains the source of the inactive profile tag;
human guild members without that role must check in. Realm activity must not
change roles, inactive status or check-in eligibility.

Gaps identified: no persistent Stories activity table, no shared authenticated
Stories client entry point, no explicit staff Xbox evidence-link workflow, and
archive setup's existing dry-run stages review records (database writes). A pure
read-only preview is needed before historical import approval. XUIDs are already
modeled; a second player registry or authentication system is unnecessary.

## Implemented relationships and behavior

`captain_player.id` remains canonical. Its unique nullable `discord_id` and `xuid`
hold reviewed stable links; `captain_identity` retains identifier/name evidence and
`captain_participation` retains historical seasons. No competing registry was added.

`utils/players/activity_models.py` adds **one** table, `captain_realm_activity`:

| Field | Purpose |
| --- | --- |
| `id`, unique `key` | Local row and deterministic SHA-256 deduplication key |
| nullable `player_id` | Foreign key to canonical profile, only when a unique stable identity resolves |
| nullable indexed `xuid`, indexed `realm_id` | Stable Xbox/Realm identities; not public display names |
| `source` | `realms_stories` |
| `raw_start`, `raw_end` | JSON timestamp representations; oversized malformed values become bounded fingerprints |
| nullable `start`, `end` | Normalized UTC datetimes for plausible intervals |
| `status`, `reason` | `observed` or `quarantined`, with fixed validation category |
| `first_observed`, `last_observed` | UTC ingestion/observation timestamps, distinct from player activity time |

DateTimeField values follow the existing database convention: naive datetime values
whose meaning is UTC. API/model boundaries require timezone-aware observation times.
The schema retains unmatched data and anomalous intervals; it does not manufacture
profiles, memberships, check-ins or season participation from API presence.

`migrations.realm_activity` reuses the existing schema checks and additive migration
conventions for all original tables plus the new table. Default execution is a
read-only preflight; apply requires `--apply --backup-verified`. It validates
existing columns/uniqueness and InnoDB, creates missing tables only, and performs
no destructive down-migration. Importing code or starting the bot performs no DDL.
Original registry migration defaults still cover the original eight tables.
**No migration was applied to production in this phase.** MariaDB DDL and concurrency
must be staged before activation; local tests use SQLite.

## Identity review rules

- Stable identifiers can resolve a canonical profile; gamertag/Discord display names
  can only suggest candidates. No name-based automatic merge was added.
- `/playerprofiles xboxlink` requires the existing Coastal OP Team/guild checks,
  a canonical profile ID, canonical positive unsigned-64-bit decimal XUID, independent
  evidence reference, and explicit `confirm:True`. Replies are ephemeral and omit XUIDs.
- The reviewed link records staff actor and a digest of the evidence reference in
  existing identity history. Keep the independently reviewable evidence in private
  staff records; the digest does not prove account ownership by itself. A gamertag
  lookup proves display mapping, not which Discord member owns that account.
- Existing current XUIDs and verified identifier history cannot be overwritten.
  Conflicting profile/identifier owners block linking. Database uniqueness and a
  conditional player update protect competing links; transaction rollback preserves
  prior identity when a conflict occurs.
- Linking reconciles only previously unmatched rows for that uniquely resolved XUID.
  Already assigned activity is never reassigned automatically. Legacy conflicts in
  identity history remain unmatched and require separate evidence review.
- Historical imports now reject malformed verified XUIDs and attempts to replace
  prior verified identifier history. Existing season review/import semantics remain.

Xbox linking works with the original registry alone; optional activity reconciliation
is skipped when its table does not exist. Enabling history requires the new table.

## Stories retrieval and ingestion

The [successful investigation](realms-stories-investigation.md) established account
visibility: HTTP 200, 27 identifier keys, 95 intervals and roughly 19.5 days of
plausible historical activity. Exact join/leave precision, retention and the meaning
of an anomalous future end remain unresolved. **No additional live Stories request
was made during this implementation.** All integration tests use synthetic responses.

`RealmsClient.stories()` uses the existing Realms XSTS authorization and renewal,
the verified frontend host, selected Realm's exact path and reference headers.
Both the client and transport permit only the selected Stories GET; arbitrary
Realms/paths/query variants/settings and all Stories mutation methods remain denied.
Existing live endpoints and their headers retain their behavior. Existing bounds,
401 renewal and 429/502/503/504 retries/Retry-After handling are reused.

`RealmRuntime.stories()` shares the running runtime's auth service, token store,
serialization lock and shutdown tracking. It never opens a second credential store.
It has a one-hour success cache and separate 60s–1h error backoff, honoring longer
Retry-After. Its requests respect an existing live-runtime retry deadline. History
failure does not clear/change live observations or session starts. A manual history
request can briefly occupy the shared lock (45s observation budget); history has no
background loop and is never called by the 15-second panel scheduler. Cache/backoff
are memory-only and reset at process restart, a documented operational limitation.

History is independently gated by optional database setting
`realm_history_enabled`, absent/false by default. It requires profiles enabled;
no flags were enabled here. `/playerprofiles activity` is OP Team/guild-only,
ephemeral, and previews aggregate counts by default. `confirm:True` explicitly
retains the returned/cached snapshot in the database. It exposes observation time
so cached data is not presented as a new server observation. No public statistics,
leaderboard, new announcement or automated archive import is implemented.

The parser rejects malformed envelopes rather than inventing empty activity.
It bounds players/intervals and uses the existing 1 MiB transport limit. Per-entry
validation quarantines invalid/zero/noncanonical XUIDs; noninteger (including Boolean),
missing/null, nonpositive, pre-Minecraft (before May 17, 2009), reversed/equal or
more-than-five-minutes-future timestamps. Unexpected huge malformed values retain
only fingerprints. No timestamp sentinel is silently treated as a disconnect.
Records passing structural/plausibility checks remain **observed**, never confirmed
sessions. Invalid containers stop the snapshot; no partial import is claimed complete.

Deduplication uses Realm/source/identity and raw s/e values, not mutable gamertags.
Repeated imports are transactional/idempotent; `last_observed` only advances.
Changing end values can produce distinct rows; aggregate calculations merge overlaps.
Quarantined records are immutable through normal reimport and are never silently
promoted when a formerly future time becomes plausible. Absence from a later API
response never deletes history or implies offline status. Retained rows persist
beyond the service window; no automatic purge exists.

## Private statistics foundation

`observed_statistics()` requires an explicit aware UTC-convertible window and can
filter by Realm. It clips intervals to that window and computes their union, so
overlapping/duplicate/rolling intervals do not double-count time. It reports observed
seconds, recorded interval count, merged spans and latest observed end; confirmed
session count deliberately remains unknown. Daily/weekly windows can use the same
function. It is internal only, with no public leaderboard or activity-history output.

Future season views require reviewed Realm/season date boundaries; no current
season is assigned retroactively to all Stories history. Historical Season 3–10
participation does not establish API coverage for those years. Continue Phase 4's
first-observed **Online for**; do not substitute `now - s` without a controlled
timing/freshness/open-interval validation and separate approval.

## Historical import preview: actual source reads

The Coastal Craft Drive connection was used read-only for eight previously audited
sources, with fresh worksheet metadata/header checks and bounded **identity/date/
approval column reads only**. Contact fields, ages, personal answers and references
were not read for this preview. Google files were not changed. Private scratch
identity rows were processed by the existing source parser and new read-only
preview against a local empty registry; a **read-only production transaction**
independently confirmed `captain_player`, `captain_identity`, `captain_import_record`
and `captain_participation` each still contained zero rows. No production records
were staged or imported. No Discord member snapshot was fetched.

| Audited source | Parsed records |
| --- | ---: |
| [Season 3 roster](https://docs.google.com/spreadsheets/d/1-3s1Q_TxEm0jVp5g0QVJ8dwlatfBiw5VSRekViIQRDk/edit) | 30 |
| [Season 4 applications](https://docs.google.com/spreadsheets/d/1eqlTwo1NgyVKv0g6m42AuAtEhPnBmE2Q-2ABX5e8VIE/edit) | 42 |
| [Season 5 applications](https://docs.google.com/spreadsheets/d/1xErJYBCcwEDsYQsOAvtCXhJmQvLE0nln8Pw6hYuqR_g/edit) | 96 |
| [Season 6 applications](https://docs.google.com/spreadsheets/d/1tKv8yT5G_FigFj4AgQ0VjNH3WZ74ue2hZzaPzxV-pMw/edit) | 134 |
| [Season 7 applications](https://docs.google.com/spreadsheets/d/1Gp739udTdrJ9sFyk6xJYtIZQl7k73u06Cs1uxXp1I9M/edit) | 60 |
| [Season 8 applications](https://docs.google.com/spreadsheets/d/1TudYa9i1509mN0xVAh0zRjm8gi69LsSBhy5QMWRjp_g/edit) | 34 |
| [Season 9 applications](https://docs.google.com/spreadsheets/d/1tgIB6ge4xYWY0IOIVqGN70Bv8-xJ-wminoIphNCqjt0/edit) | 17 |
| [Season 10 applications](https://docs.google.com/spreadsheets/d/1ltMnItNgDBk5FhgsC-afi0l17OBnfOTcKPIkcSw9zvE/edit) | 22 |
| **Total** | **435** |

| Preview category | Count / interpretation |
| --- | --- |
| Existing profile matches | 0; verified empty registry baseline |
| Proposed standalone profiles | 329 conservative proposals, not verified unique people |
| Ambiguous records | 104; name matches across records require review, never automatic merges |
| Potential duplicate-name groups | 52; groups are not a count of duplicate people |
| Repeated source fingerprints | 2; repeated source records, not new people |
| Known conflicting stable links | 0 in this snapshot; absence of Xbox evidence is not proof of no conflicts |
| Records carrying trusted Discord IDs | 73; existing bot-generated Season 8+ source trust assumption |
| Records with verified Xbox XUIDs | 0; all Xbox associations require independent review |
| Parser source-issue records | 0 for these eight audited layouts |
| Records requiring approval | All 435; none imported |

This is complete for the **eight selected audited sources**, not a claim that the
entire Drive archive is reconciled. The previously documented extra untitled-season
application workbook and Season 4 roster filed under Season 5 remain excluded until
source/season overrides are reviewed. Season 3 Sheet2 and guide-agreement sheets
are also not audited application sources. Grid row capacity is not a record count.
Current Discord name candidates/departed-member counts could not be assessed without
a current member snapshot. Captain's production service-account access remains a
separate check from the interactive Coastal Craft Drive account used for this preview.

Two ways to reproduce future previews after review:

- `/playerprofiles preview`: uses the existing archive adapter, returns aggregate
  counts without persisting a queue, DiscoveryRun, profiles or season rows.
- `python -m scripts.player_history_preview <private-source-bundle.json>`: accepts
  private exported row bundles; defaults to an in-memory empty registry and labels
  that baseline. `--registry-snapshot <private.sqlite>` uses SQLite URI read-only
  mode. No environment credentials or production database configuration are read.
  Existing `/playerprofiles setup` still intentionally stages a review queue; it
  is not the new no-write preview. Neither preview approves/imports records.

## Privacy, deployment boundaries and activation sequence

Raw identifiers/activity stay in the existing restricted database and private
staff workflows; no public output or logging of records is added. Database access,
TLS, backup protection and staff-channel privacy remain operator responsibilities;
this extension does not claim a new encryption-at-rest mechanism. Evidence references
and scratch exports must remain private. No dependencies or new credentials were added.

After owner review, activate in separate authorized steps:

1. Review branch/CI and the source exclusions, preview counts and identity policy.
   Resolve source ownership/layout assumptions and protect independently verified backups.
2. In an isolated MariaDB staging database, run `python -m migrations.realm_activity`
   preflight, then explicitly approved `--apply --backup-verified`; test repeat apply,
   restore procedure, unique links and activity deduplication. Production apply needs
   its own approval/maintenance window because DDL can auto-commit.
3. Approve deployment separately. **Do not merge to main casually:** the existing
   main push workflow restarts production. No merge, deployment or restart occurred here.
4. Enable profiles only after schema/access validation; keep check-in announcements,
   reminders and `realm_history_enabled` off. Manually synchronize Coastal guild
   commands through the existing authorized flow; no global command sync.
5. Reproduce the source preview with the actual runtime service account and current
   guild snapshot. Review individual associations, then separately approve historical
   staging and imports. Never mass-approve uncertain name matches.
6. Review a small number of independently evidenced Xbox links. Separately approve
   `realm_history_enabled:true`, then preview one cached/rate-limited Stories snapshot
   and explicitly confirm retention only after reviewing privacy and quarantine counts.
   No activity-derived role/eligibility changes are permitted.
7. Keep announcements/reminders disabled until their own channel privacy, eligibility,
   delivery and operator activation checks pass. Any automatic history collection or
   public statistics is a future scoped change, not activated by this implementation.

Rollback: disable history/profiles/new messaging flags, use the previously approved
runtime, retain all additive tables and records. No destructive rollback/purge was added.

## Verification

Focused initial registry/client/transport/configuration run: **139 passed**. The
expanded final run: **350 passed, 1 skipped** (Windows platform skip), exercising
auth, names, panel/session storage, permissions, shared runtime and encrypted
credentials. Ruff F checks and whitespace checks passed. The test temp directory
was outside the checkout, respecting the unchanged private-store location policy.
After the final MySQL identical-link handling adjustment, all **23 focused history
tests** passed again, including repeat linking without duplicate identity evidence.
All tests block external network and use synthetic identities plus local SQLite.
Private source reads and the read-only zero-row registry count are operational
preview evidence, not production import or migration tests. No new live Stories
calls or historical imports were performed in this development phase.

Remaining gates: exact Stories timestamp/open-session/retention semantics, reviewed
Xbox ownership evidence, cross-file season ambiguities, production service-account
archive access, current Discord member reconciliation, staging MariaDB DDL/concurrency,
and explicit owner approval for every production activation step.
