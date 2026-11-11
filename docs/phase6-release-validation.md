# Phase 6 release validation and private identity review

Date: November 3, 2026 (America/Chicago). Branch: `codex/realms-phase6`.
Starting revision: `8f3f5258eef2d5afe4a62802d6338bd36f491530`.
This review does not authorize activation, migration, staging/import of real
records, deployment, restart, main merge, Realm changes or announcements.

## Approved attribution and revised review preparation (after 72c30ab)

The owner approved **source attribution only** for the older `Season 3` application
tab (`gid=107533011`, Season 3) and `Coastal Members Season 4` / `Sheet1`
(`gid=0`, header row 4, Season 4). Neither approval verifies player identity or
authorizes any production staging/import. The unnamed `Form Responses 1` tab
(`gid=1332515138`), `Easy View` and removal/warning register remain excluded.
These current decisions supersede the earlier pending-attribution wording below.

Exact mappings are prepared in [the review-only manifest](../config/player-history-review.json).
It names all ten approved worksheet/gid/header/season combinations, marks roster
versus application evidence, retains the existing Discord-ID trust assumptions,
and explicitly sets `import_authorized:false`. It is **not** runtime configuration;
no `botdata` settings or Google files changed. The approved older `Season 3` tab
is an explicit separate review batch, avoiding the runtime discovery system's
one-worksheet-per-workbook limitation. The unapproved first tab is never a fallback.

A fresh bounded read of identity/date/approval columns across all ten sources was
processed through the existing `parse_rows`, `record_key` and no-write `preview`
functions. The review wrapper validates exact worksheet identity and preserves
canonical `/edit#gid=...` source URLs and existing fingerprints. Five embedded header
rows were excluded. Repeated rows retain all source-row locators in private material.
No contact fields, application answers, coordinates, moderation narratives, current
Discord membership or Realm history were fetched. No production database was accessed.

### Revised aggregate preview

| Measure | Fresh result and unit |
| --- | --- |
| Source observations | **765**, after excluding five embedded headers, before same-source deduplication |
| Distinct source fingerprints | **524**, not a unique-person count |
| Repeated source observations | **241**: 239 in the approved older Season 3 application tab and two in the original sources |
| Conservative proposed canonical profiles | **352** under the existing empty-registry preview; proposals, not verified people or approved links |
| Ambiguous distinct records | **172**; raw-row-weighted ambiguity is 272 because repeated rows also appear in ambiguous groups |
| Duplicate-name groups | **75**, across gamertag/Discord-name field groups; groups can overlap |
| Cross-worksheet/source name-overlap groups | **53**, involving **132** distinct record candidates; suggestions only |
| Exact gamertag + parsed application-date groups across approved sources | **0**; the five known matches belong to the excluded unnamed tab |
| Trusted Discord-ID records | **73**, grouped into **59** IDs; ten repeated-ID groups, two differing-gamertag groups |
| Records lacking trusted Discord IDs | **451 distinct records** requiring independent identity evidence before association |
| Verified XUID evidence | **0** source records; all Discord-to-Xbox ownership links still require independent evidence |
| Source issues / conflicting payloads under one fingerprint | **0 / 0** in this selected snapshot |
| Identity decisions / production imports | **0 / 0**; all 524 distinct records remain unapproved for import |

The preview used **empty local in-memory SQLite**, not a current production snapshot.
The old read-only empty-production count is historical evidence only. No current
existing-profile matches or current guild membership are claimed. The 352 proposals
are the established preview's conservative standalone/stable-key proposals; do not
add 59 trusted-ID groups to that number, or treat ambiguity as an automatic merge.
Full aggregate output is in [player-history-review-summary.json](player-history-review-summary.json).

| Season | Raw observations | Distinct source fingerprints |
| --- | ---: | ---: |
| 3 | 317 | 77 |
| 4 | 85 | 85 |
| 5 | 96 | 96 |
| 6 | 134 | 133 |
| 7 | 60 | 60 |
| 8 | 34 | 34 |
| 9 | 17 | 17 |
| 10 | 22 | 22 |
| **Total** | **765** | **524** |

Season 3's approved additional tab contributes 48 distinct observations; its 239
repeats collapse within that same source. The approved Season 4 roster contributes
43 distinct membership observations, with no invented application dates or application
status. Seventeen of the additional Season 3 records and 25 of the additional roster
records have exact normalized name candidates in the original eight sources.
Those are observation counts, not verified common players. Records with matching
names in a roster and application remain separate source evidence until identity review.

### Prepared private batches

The local private staff package is under
`.test-tmp/phase6-identity-review-20261103-final/`, protected by the existing Windows
private-ACL helper and confirmed Git-ignored. It was **not committed, uploaded or
sent to staff**. Only source mappings and aggregate counts are in GitHub.

- `identity-review.json`: source-keyed identity evidence, normalized/raw application
  timestamps, all repeated-row locators, review groups and name suggestions. All
  identity approvals remain false. No profile ID or XUID is invented.
- `unnamed-tab-review.json`: 29 separate observations with `season:null` and explicit
  exclusion, preserving their five exact name/date links to approved-source fingerprints.

Access is for the owner and designated Coastal OP reviewers; do not place this
package in a public Discord channel, public Drive folder or repository. Owner approval
of reviewers, sharing destination and retention/deletion policy is still needed
before distributing it. Temporary source-input copies were removed after preparation;
the protected review evidence remains available locally for the requested review.

Priority A contains the **73 records / 59 stable-ID groups**, preserving every
associated season and flagging both differing-gamertag groups. These are unapproved
identity proposals, not automatically reviewed associations. Discord ID evidence is
not proof of Xbox ownership.

Priority B contains **360 original-source name-only records** after setting aside
Priority A for review. Priority C contains the **91 additional approved-source
observations** (48 applications + 43 roster entries). B and C are disjoint source
queues; a person may still be represented in either or both. Of all 451 remaining
name-only records, **137** have duplicate-name or Priority-A name suggestions;
there are **56 remaining name-only duplicate groups**, and **33 records** have
name-only suggestions to Priority A. These counts overlap and must not be added.
Actual identity approvals are still zero, so this is queue stratification, not a
claim that 73 identities were already resolved. Recalculate after each independently
reviewed stable-ID batch; never materialize guessed profiles to make ambiguity disappear.

### Unnamed tab: further evidence, still excluded

Fresh reads confirm 29 observations spanning September 30, 2017–February 17, 2018,
with five exact normalized gamertag/parsed-date matches to the audited Season 4 sheet.
The workbook was created **June 8, 2017 UTC** and last modified **August 3, 2018 UTC**.
The explicitly named Season 4 application workbook was created **February 19, 2018 UTC**,
yet contains application dates beginning February 12. Both currently share the same
Drive parent. Workbook creation therefore cannot be treated as application or season
start; copying/backfill is possible. Current folder placement and modification times
do not establish the historical season of each row.

The approved Season 3 tab ends September 30, the same date the unnamed tab begins;
that suggests a transition/split. Continuity and five exact overlaps with the named
Season 4 source support an **early Season 4 hypothesis**, but neither a historical
season boundary nor whole-tab attribution is proven. No row is assigned a season.

**Owner decision remains required:** approve the whole tab as Season 4 after checking
independent season chronology, specify an evidenced transition/date split, or leave it
excluded. Until then all 29 observations, including the 24 without the known exact
cross-file matches, stay outside the approved ten-source preview/import batches.

### Review tooling, tests and remaining gates

`scripts.player_history_review.py` is an offline wrapper around the existing source
parser/fingerprint/preview. It adds only the counts and private docket preparation
needed here: exact mapping/completeness checks, raw-versus-distinct measures, no-write
priority grouping and fresh private-directory output. It never reads `.env`, contacts
a live database, stages `ImportRecord` rows, creates profiles or runs imports. It
rejects excluded/missing/duplicate/tampered worksheet batches and refuses private
output under tracked repository paths. Existing Phase 4/6 runtime code is unchanged.

Focused tests: **68 passed** across `test_player_history_review.py` and the existing
`test_player_registry.py`; Ruff F checks passed. Coverage includes fingerprint
preservation, header exclusion, roster dates, zero registry/queue writes, exact
worksheet enforcement, unapproved-source rejection, same-ID name changes, conflicting
payloads, same-source name groups and private-output location refusal.

Resolved: attribution approval for the 48 Season 3 application observations and
43 Season 4 roster observations, plus their explicit review manifest/batches.
Still unresolved: unnamed-tab attribution; individual identity/Xbox ownership
evidence; designated reviewers/private evidence handling; a current approved registry/
guild baseline; production service-account source access; isolated MariaDB staging
validation/restore evidence; and separate approvals for every production write,
deployment, feature flag, messaging and timestamp comparison. The incremental rollout
below is unchanged. **Attribution approval is not identity or production import approval.**

## Release evidence and staging decision

The branch was clean at `8f3f525` when validation began. Existing GitHub checks
for that exact revision all succeeded:

- [Offline regression tests](https://github.com/bsavage81/TheCaptain/actions/runs/41754342791).
- [CodeQL](https://github.com/bsavage81/TheCaptain/actions/runs/41754342779).
- [Dependency security audit](https://github.com/bsavage81/TheCaptain/actions/runs/41754342790).

The original 350-pass/one-skip local evidence remains recorded in the integration
notes. The focused archive-header fix in this review passed **80 offline tests**
across `test_player_registry.py` and `test_realm_history.py`, plus Ruff F and
whitespace checks. Tests use synthetic data and temporary SQLite, not live imports.
The new branch head must also pass CI; base-revision success is not head validation.

**MariaDB staging validation was not executed.** Read-only environment checks
found no `docker`, `mariadb`, `mysqld` or `mysql` executable on PATH, no matching
MariaDB/MySQL/Docker Windows service or installation directory under Program Files,
and no explicit staging/test-database environment variable names. This establishes
no safely identified staging target, not that no remote staging server could exist.
No server was installed, container started, port probed or database provisioned.
No production connection, migration CLI, database migration or real-data import was
run in this review. The repository's `.env` was not used as a staging source.

Important migration boundary: `python -m migrations.realm_activity` loads `.env`
and derives its database from existing bootstrap settings. A generic terminal
invocation is therefore **not a safe staging recipe**, even without `--apply`.
The Python `migrate(backend, ...)` function accepts an explicitly supplied backend;
future staging validation must use that entry point with a separately verified
staging connection, not silently reuse production bootstrap configuration.

To close the MariaDB gate, the owner must first identify/provision an isolated
instance and authorize its synthetic DDL test. Require:

1. An independently confirmed staging host, port and schema, server version and
   TLS/connection policy. A distinct schema name alone on the production server
   is insufficient for this plan. No production data or credentials are copied.
2. A staging-only account whose grants are limited to the staging schema; no
   access to production. Compare the explicitly supplied target to the separately
   held production inventory **before** connection. After connection, verify server
   identity, `DATABASE()` and `CURRENT_USER()` privately; mismatch aborts before DDL.
3. A reviewed harness that does not import/load `.env` or instantiate `make_database`
   from production settings. No full application startup, Discord or Google access.
4. Read-only preflight; owner-approved apply against an empty synthetic staging
   schema; inspect all nine tables, InnoDB engines, primary/foreign keys, columns,
   nullable fields and unique indexes. Repeat apply must preserve sentinel rows.
5. Test the original eight-table schema followed by the additive ninth table;
   incompatible columns/indexes and non-InnoDB must be refused. Include unsigned
   64-bit XUID strings, null links, large anomalous ends, UTC microseconds/precision,
   identical Xbox linking in the same second, competing links, repeat imports and
   overlapping intervals under two independent connections.
6. Demonstrate a consistent independent backup/restoration in another isolated
   schema/instance. Inspect partial-DDL recovery (MariaDB DDL can auto-commit);
   never drop populated tables as an automatic recovery step.

No such harness or instance is claimed validated here. This remains a release
blocker; SQLite success cannot establish MariaDB DDL/locking behavior.

## Previously excluded archive sources: initial findings at 72c30ab

The current attribution decisions and fresh ten-source totals above supersede
the pending decisions in this retained initial investigation.

Reads used the existing **Coastal Craft** Google Drive connection. Fresh workbook
metadata grounded the tab names and bounds. Only headers, gamertags, and application
timestamps were read for this review; contact details, coordinates, personal answers,
age, references and moderation narratives were not collected. No Google writes.
Names and IDs remain out of this document; comparisons below are candidate evidence,
not ownership verification or unique-person counts.

### Older application workbook in Season 4 Files

Source: [Coastal Craft Pe Realm Application (Responses)](https://docs.google.com/spreadsheets/d/1P0xHNd-Y9xWfxwfTIn2CyYteQ4DYT0pvJ49zdeshwU0/edit).
Metadata shows `Form Responses 1`, `Season 3` and `Easy View`.

| Tab | Bounded findings | Release treatment |
| --- | --- | --- |
| `Season 3` (`gid=107533011`) | 292 nonblank gamertag rows, including **5 embedded Timestamp/Gamertag headers**. Excluding headers: **287 application rows**, **48 distinct exact trimmed gamertag/timestamp pairs**, **239 repeated application rows**. All nonheader dates parse as dates spanning June 14–September 30, 2017 | Valid additional Season 3 application candidates, explicit tab-label evidence. Review the 48 source observations, not 287 proposed people. Preserve duplicate provenance; do not auto-approve names |
| `Form Responses 1` (`gid=1332515138`) | **29 dated application rows**, all distinct name/timestamp pairs; September 30, 2017–February 17, 2018. **5** exact formatted name/timestamp pairs also occur in the previously audited Season 4 application sheet | Likely early Season 4 material based on folder and chronology, but workbook/tab does not explicitly name the season. Owner must approve season attribution. **24** pairs are additional relative to the audited Season 4 sheet; not 24 proven new players |
| `Easy View` (`gid=1511099061`) | One nonblank gamertag, already present in the application tabs; no independent season/identity evidence established. No formula was found in the inspected A2:B3 range | Keep excluded as a secondary view. Do not assert the whole tab is formula-generated or import it as an independent source |

For context, the audited Season 4 application's observed date range is February 12–
July 1, 2018. Its five exact name/date overlaps support continuity with the older
tab; folder placement and chronology are still not conclusive season boundaries.
Sixteen names in the older Season 3 tab also appear in the audited Season 3 roster;
those are name candidates, not verified stable links.

**Focused fix:** the existing parser previously accepted embedded headers as a
profile named “Gamertag,” with an unparsed application date. It now skips a row only
when both its gamertag and timestamp cells contain the corresponding header labels,
case-insensitively with surrounding whitespace removed. A genuinely dated player
named “Gamertag” remains valid. A synthetic regression also verifies repeat real
application rows retain the existing equal source fingerprint. No import was run.

Source-key caution: older keys include workbook/tab URL, season, parsed date and
identity. Existing same-tab repeated rows collapse, but identical applications in
**different** workbooks retain different source keys. The five cross-file overlaps
must be explicitly reviewed as duplicate observations; the importer will not dedup
them globally by name/date or merge the players automatically.

### Season 4 roster stored in Season 5 Files

Source: [Coastal Members Season 4](https://docs.google.com/spreadsheets/d/1nOm20g7W3zGhh-kCMWw33OrFIDz67zZPQxDZlqJ198g/edit).

| Tab | Bounded findings | Release treatment |
| --- | --- | --- |
| `Sheet1` (`gid=0`) | Header row **4**, **43** nonblank/unique trimmed gamertags below it. Workbook title explicitly says Season 4; folder placement says Season 5. Twenty-one names also appear in the audited Season 3 roster | Additional Season 4 roster candidates, subject to owner approval of the season override. Read as historical roster observations, never applications or current Realm membership; do not invent an application date |
| `Sheet2` (`gid=1455322091`) | Header includes Gamertag, Related to, Removal reason, Warning dates and Removal date; **5** nonblank gamertags | Removal/warning register, not an active-member roster or application adapter. Keep excluded. No moderation details read or used to infer current inactive status |

The source title supported proposed `season:4`, `worksheet:"Sheet1"`, `header_row:4`,
`trusted_discord_ids:false` at the initial review. These mappings are now approved
in the review-only manifest above; production settings remain untouched. Neither excluded
workbook provides an explicit trusted Discord-ID or XUID column in its inspected
application/roster headers. Do not reinterpret contact, Band Name or Related to as
authenticated Discord identity.

Taken as proposed separately attributed sources, the two application tabs and
roster contain **120 distinct source-local observations** (48 + 29 + 43), including
the five cross-workbook duplicates identified above. This is **not** 120 additional
people or an approved revised registry total. The original eight-source 435-record
preview remains a separately scoped baseline, not overwritten by this review.

Current discovery supports **one worksheet override per workbook**. It cannot read
both the older workbook's application tabs in one discovery pass. Prepare separate
explicit, tab-bound review batches with their actual gids using the existing source
adapters/export preview, or approve two separately documented source-override passes.
Do not silently switch overrides or assume the default first tab covers Season 3.
No new multi-tab discovery feature was added in this release-validation task.

## Privacy-safe identity review workflow

Fresh bounded D:E reads of the audited Season 8–10 sheets confirm **73 trusted-ID
records**: 34 + 17 + 22. They group into **59 distinct syntactically valid Discord
IDs**; **10 IDs** have multiple records, and **2 groups** have differing normalized
display gamertags. No malformed ID was found in that selected set. “Trusted” retains
the existing assumption that these are bot-generated ID columns; it is not new
independent proof that the sheets were never edited or that gamertags prove Xbox ownership.

No current Discord member snapshot, direct message, production review queue or
staff-channel post was created. No actual association was approved or imported.

1. **Prepare a private review docket**, outside Git/public channels, restricted to
   designated Coastal OP Team reviewers. Use existing source fingerprints plus
   worksheet/gid/row locator, proposed season/profile, evidence references, review
   decision, actor and UTC time. Raw Discord/Xbox IDs belong only in this restricted
   docket/registry; published summaries contain counts and opaque review references.
   Rows are locators, not stable import keys. Restrict retention/backup access and
   agree on a retention policy before exporting a full docket.
2. **Priority A: the 59 stable-ID groups / 73 source records.** Check source provenance,
   exact unrounded ID and current canonical links; all seasons for one ID travel
   together for review. In a later approved read-only guild snapshot, compare exact
   IDs to present/departed accounts; missing membership must not delete history.
   Propose one canonical profile only when stable evidence agrees. Attach seasons
   individually, preserving dates and source provenance. Stop conflicting IDs; no
   bulk approval merely because this group was prioritized.
3. **Escalate the two differing-gamertag groups.** Distinguish an ordinary display
   rename from another person's reused/incorrect application. Preserve historical
   names. Neither source ID provenance nor a matching Xbox profile name proves a
   Discord-to-XUID association. Use independently reviewed ownership evidence before
   `/playerprofiles xboxlink`; record the evidence privately, with staff actor and
   reference digest retained by the existing link path. Never overwrite verified links.
4. **Priority B: ambiguous names.** The original preview's 104 ambiguous records and
   52 duplicate-name groups are overlapping record/group measures, not extra people
   after Priority A. Remove already resolved source keys from the review workload,
   then recompute suggestions. Exact/fuzzy names are hints only. Require independent
   evidence and a second reviewer for proposed cross-source identity associations;
   otherwise leave unresolved or propose separate profiles, never auto-merge.
5. **Priority C: newly reviewed archive observations.** First approve the tab/season
   mapping above, remove embedded headers through the focused fix, collapse repeated
   same-source fingerprints, and flag the five cross-file application duplicates.
   Do not create two people for an application and roster with the same name, but
   also do not merge them without evidence. Resolve or defer the evidence question.
6. **Approve bounded import batches separately.** A docket decision is preparation,
   not production approval. Future `/playerprofiles setup` persists a review queue,
   `/review` persists decisions, and `/import confirm:True` writes profiles/history;
   all remain prohibited in this review. Start with an owner-approved small stable-ID
   batch (for example five groups), verify resulting links and source counts privately,
   then obtain approval for the next batch. Rejected/deferred records remain traceable.

Membership, Realm activity, application approval and monthly check-in requirement
are distinct. The inactive Discord role remains authoritative; no activity or old
moderation register changes roles, inactive tags or eligibility. Members without
the inactive role remain required to check in.

## Independent timestamp comparison plan (not executed)

The previous Stories success proves existing-account visibility, not precision or
complete opt-in coverage. This review made **zero** live Realms/Stories/authentication
calls and did not read the running bot's session/cache/token files.

A safe comparison can use a consenting member's **normal Minecraft client** and
an independent UTC event log. It needs no bot change, deployment, restart, config,
membership/permission or Timeline change. The participant must already have access
and appropriate existing Timeline visibility; if missing, stop rather than enable it.

Proposed approval scope for an initial comparison: one consenting participant,
one <=30-minute window, two ordinary join/leave sessions (one crossing an hour
boundary, one shorter rejoin after a gap), **at most 30 live-activity GET attempts
at >=60-second spacing and 4 Stories GET attempts**. This budget is a proposal,
not permission to repeat the previously authorized one-shot probe. Count attempts,
including errors; disable automatic HTTP retry, redirects and hidden renewal-on-error.
Honor Retry-After/abort on 401/403/429; do not probe limits.

- Before the window, record clock synchronization/estimated clock error and the
  consenting test identity privately. Use one opaque participant alias in reports.
  Record UTC join initiation, terrain-ready arrival, voluntary disconnect request
  and return-to-menu separately; client UI times bound an event, not exact server
  acceptance/disconnection. Exclude unrelated chat/player data from any evidence.
- An independent fixed-host diagnostic may take a baseline Stories read, a read
  during the first session, a read after its departure, and a delayed read after
  the final departure. Choose the event schedule so the last read remains within
  the approved window (for example a 12-minute session, two-minute gap, three-minute
  rejoin, final read ten minutes later). Do not read or alter Phase 4's private store.
- Reuse the established account/authentication through the previously reviewed
  private isolated-copy approach **only after authorizing that new diagnostic and
  its minimum authentication POSTs**. Confirm source stability, private ACLs, separate
  lock and refresh persistence, no production-store writes/copy-back; abort if safe
  isolation cannot be re-established. No new login, account or credentials.
- In memory, select only the configured Realm/test participant from activity results
  and Stories; discard other players. Record the last known offline / first known
  online observation and last online / first offline observation. Their brackets
  express sampling uncertainty. Missing/unknown data is not departure.
- Compare raw integer s/e changes across the four reads to independent UI and live
  observation brackets. Test whether e is final, rolling, capped, future or a sentinel;
  do not clamp anomalous ends into a fabricated logout. Check apparent hour rounding,
  delayed publication, overlapping/merged intervals and whether the rejoin stays
  separate. Do not call these fields confirmed connections just because types parse.
- Publish only aggregate test coverage, observation spacing, clock/error bounds,
  valid/anomalous counts and offset/rounding/lag ranges. Keep the raw event docket
  private under the agreed retention policy; no real identifiers/per-player history
  in Git or public output. This test is not a backfill or stats import.

For live-duration use, require repeatable complete sessions across additional approved
windows and an agreed acceptable error bound (propose <=60s for a minute-resolution
display, including sampling/clock uncertainty). If data is hour-bucketed, delayed,
incomplete or cannot reliably identify the open interval, keep it for explicitly
qualified historical analysis only. Even a successful initial comparison does not
prove retention or all-player visibility. **Phase 4's Online for remains unchanged.**

## Remaining gates and incremental rollout

Every step below is prospective and requires the owner's explicit approval for its
effects. No generic “Phase 6 approved” should obscure which writes/actions are allowed.

| Gate | Required evidence/decision | Current state |
| --- | --- | --- |
| Exact release revision | Review focused diff, all head CI checks and immutable commit SHA | Base CI green; follow-up head CI must pass |
| MariaDB isolation and validation | Verified distinct staging instance, grants, synthetic DDL/repeat/concurrency/restore results | **Blocked: no safely available instance identified** |
| Source inclusion | Approved `Season 3` tab and Season 4 roster prepared as exact review batches; unnamed tab and its five overlaps remain excluded | Attribution resolved for ten sources; no identity/import approval |
| Identity/privacy review | Designated reviewers, source trust, private evidence retention, current guild-ID snapshot, conflict decisions | Workflow prepared; 73 records / 59 groups prioritized; no approvals made |
| Production recovery | Independent restorable backup, table/flag baseline, maintenance owner and rollback trigger | Not performed/approved here |
| Production DDL | Approve only additive ninth-table apply after staging evidence | Not approved/applied |
| Code rollout | Exact SHA and approved maintenance deployment/restart; keep new flags off | No deployment; main push would auto-restart |
| Profiles enablement | Explicit consent to profile-cog side effects and guild-only command sync | Disabled; not approved |
| Historical writes | Separate queue-staging, per-record decisions and bounded import approvals | No staging/import |
| Xbox links/history retention | Independent ownership evidence, private retention policy, history flag and per-snapshot retain decision | Disabled; no links/history writes |
| Timestamp precision | Separately approved independent comparison, error budget and visibility findings | Unverified; no duration replacement |
| Announcements/reminders/public stats | Separate privacy/role/channel/delivery approval | Disabled; public stats not implemented |

Recommended order after review:

1. Close staging and source-review gates first. Select a tested, CI-green release SHA.
   Do not run the CLI against production defaults as a staging shortcut.
2. In a separately approved maintenance window, verify independent backup and baseline,
   apply only reviewed additive production DDL, inspect it and stop on mismatch. No
   import, feature enablement or messaging is implied by schema approval.
3. Obtain separate approval for main merge/deployment/restart: `.github/workflows/my_workflow.yml`
   restarts production on **main push**. A merge is a production action, not merely
   administrative branch cleanup. Verify Phase 4 status/player/name/session behavior
   with all new features disabled before approving any profile activation.
4. Approve profiles alone and Coastal guild command synchronization. Keep
   `checkin_enabled`, `checkin_announcements_enabled`, `checkin_reminders_enabled`
   and `realm_history_enabled` false. **Enabling profiles already starts inactive-role
   reconciliation when configured and registers the persistent check-in view**, even
   while monthly scheduling is off. Its linked-profile inactive writes and existing
   submission mirrors are part of that approval; it never assigns/removes Discord roles.
5. Re-run the no-write preview through the actual service account and approved current
   guild snapshot. Approve queue staging separately, then review/import the first
   small stable-ID batch. Verify counts, preserved seasons, deduplication and role
   eligibility before approving further stable-ID, ambiguous or legacy-source batches.
6. Approve evidenced Xbox links separately. Then approve the history flag and preview
   only; inspect observation age and quarantine/unmatched counts before authorizing
   one snapshot's retention. A preview/flag is not blanket import authorization. There
   is no automatic history scheduler; ongoing collection remains a future decision.
7. Conduct only the separately approved timestamp comparison. Keep inferred intervals
   private and qualified. Monthly check-ins, announcements and reminders need their
   own channel/privacy/eligibility/duplicate-delivery acceptance and activation approval;
   do not turn them on as part of profiles/history validation. Public activity histories
   or leaderboards require a distinct feature/privacy review.

Stop on unexpected counts, verified-link conflicts, missing flags/schema, failed
privacy checks or a Phase 4 regression. Roll back operational flags/code only through
an approved procedure; retain additive tables and histories. Do not drop tables or
restore over new production records without a separate recovery authorization.
