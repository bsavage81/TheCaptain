# Phase 6 development closeout

Current rollout: [production database inspection and migration preparation](phase6-production-database-rollout.md).
The owner waived separate staging; backup/recovery and production-action approvals remain required.

Follow-up: [production readiness, isolated MariaDB setup and approval-gated rollout](phase6-production-readiness.md).

November 3, 2026 (America/Chicago). Branch: `codex/realms-phase6`.
Reviewed starting revision: `05d6a49400f6fddfcc35616206fd3fee6aee09b1`.

**Development closed within the scope below; production activation remains gated.**
This closeout records the owner's decision to retain the existing live observation
system and use Stories only as supporting activity evidence. It authorizes no
deployment, restart, main merge, database migration/import, feature activation,
Realm setting change or announcement. This is a documentation-only closeout.

This document supersedes earlier proposals to use Stories for precise durations
and any implication that further archive research is required to finish development.
The original [integration notes](player-profiles-realm-integration.md),
[release review](phase6-release-validation.md) and
[D1 evidence](realms-activity-verification.md) remain supporting records; their
historical investigations and proposed diagnostics are not new execution instructions.

## Final behavior and evidence policy

| Information | Authority and permitted interpretation |
| --- | --- |
| Current presence and current observed duration | Existing live endpoint observations and Phase 4 session state; first observed online is not exact login time |
| Stories intervals | Private, unverified activity coverage; observed hour alignment supports coarse corroboration, not precise joins/departures or playtime |
| Matching Stories activity | Supporting evidence consistent with activity around that period; never promotes a live estimate to an exact/confirmed session |
| Stories activity without matching live evidence | Possible observation gap to review; never invent a session, fill its duration or infer uninterrupted play |
| Missing, stale, quarantined or inaccessible Stories data | Inconclusive; never infer offline status or no play, penalize a member, or erase live evidence |
| Roles, inactive status and monthly eligibility | Existing role/check-in policy; Realm activity is not an input |

The word **corroboration** is intentional: Stories can support an activity observation
but cannot verify exact session boundaries. Its hourly timestamp pattern is observed;
the general partial-hour rounding rule, publication delay and coverage remain unknown.
Do not call Stories union coverage "total playtime" or its interval count "sessions."

## Implementation review

| Component | Verified implementation and boundary |
| --- | --- |
| `utils/realms/panel.py` — `Sessions` | Tracks current first-observed online starts and the latest authoritative observation. Unknown activity does not fabricate departure. The panel labels durations as observed estimates. State contains active starts, not a completed-session archive. |
| `utils/realms/runtime.py` | Live observations and explicit Stories requests are separate paths sharing existing authentication and serialization. The scheduled live path does not request Stories. Stories failure does not replace live observations or session starts. |
| `utils/players/cog.py` | Staff/guild-only private activity command defaults to preview. Retention requires explicit confirmation and the independent history gate. No public activity statistics or automated corroboration output is implemented. |
| `utils/integrations/realms/stories.py` | Validates bounded envelopes and quarantines invalid identifiers, malformed/reversed/nonpositive timestamps and implausible future ends. Plausible values remain observed, not confirmed sessions; no inferred open-session sentinel. |
| `utils/players/activity.py` | Stable-ID evidence linking, transactional deduplicated ingestion, and internal clipped interval-union statistics. `confirmed_sessions` remains unknown and coverage is explicitly unverified Stories. No live-session reconciliation or duration replacement. |
| Configuration and migration | History defaults off and requires profiles. Additive schema preparation exists; importing modules/startup does not apply it. No flag or schema changes made during closeout. |

The implementation already preserves the required separation. **No runtime code
change is needed to close this scope.** Stories is available as a private evidence
foundation, not a finished automatic verifier. Building automatic corroboration,
persisting completed live sessions, gap reports, confidence badges or statistical
displays would be separately scoped feature work, not silently included here.

## Evidence and validation

Short D1 obtained three successful Stories snapshots across independently reported
arrival/departure and live online/offline observations. The snapshots were identical,
all sampled timestamps were hour-aligned, and an anomalous future end persisted
after departure. A later user-authorized own-data read returned plausible hour-aligned
intervals with no remaining future anomaly. Its individual activity records are not
included in Git. These findings support conservative treatment; they establish no
exact session matching, rounding algorithm, publication-lag bound or retention guarantee.

Closeout verification:

- **338 passed, 1 skipped** in the tracked Realms authentication/client/transport,
  permissions/storage, panel/session/name/runtime, player registry, Realm history and
  Stories semantics tests. The skip is platform-conditional. The only warning is
  discord.py's existing Python 3.12 `audioop` deprecation.
- Ruff F checks passed for **100 tracked application, migration, script and test
  Python files**. No pending archive-review tooling was included. The initial broad
  lint invocation exceeded Windows command limits/included vendored Python files;
  the successful check used bounded batches of the application's tracked paths.
- Tests block external network and use synthetic identities and temporary SQLite.
  The Windows run used local loopback outside the sandbox. Synthetic migration
  tests are not MariaDB staging or production migration evidence.
- Local dependency checking could not run because this existing virtual environment
  has no `pip` module. No environment/dependency changes were made. The starting
  revision's [Linux/Windows offline CI](https://github.com/bsavage81/TheCaptain/actions/runs/41764185074),
  [CodeQL](https://github.com/bsavage81/TheCaptain/actions/runs/41764185058) and
  [dependency audit](https://github.com/bsavage81/TheCaptain/actions/runs/41764185116)
  all passed. The offline workflow includes `pip check`; final closeout head checks
  must also pass before release selection.
- No new live API/authentication calls, database connections, archive previews,
  imports or production inspections were performed during closeout. Existing paused
  historical modifications and private artifacts remain untouched and outside this commit.

## Deferred work

Historical source investigation, previews, identity dockets and imports are paused
at the owner's direction. They are not required to close this development scope.
Any future use requires fresh authorization and appropriate private identity review;
name similarity alone never establishes an identity. No pending historical files
are included in the closeout release.

Additional Stories diagnostics are also deferred. Existing evidence is sufficient
to reject precise-duration use. A future proposed automatic corroboration feature
would need explicit matching/freshness/privacy rules and evidence that those rules
work; the earlier D1 budget is not reusable authorization for more requests.

## Production activation gates and incremental rollout

Development closeout does not mean deployment-ready activation. None of the steps
below has been executed or approved by this closeout.

1. **Select an immutable CI-green revision.** Review the exact diff and exclude
   paused/untracked historical files. Verify all head checks and the deployment
   effect: pushing `main` triggers the production restart workflow.
2. **Validate MariaDB on a verified isolated instance.** No safely available instance
   has been identified. Obtain an explicit staging target and staging-only grants,
   distinct from production; do not reuse `.env`, production credentials or defaults.
   Use the reviewed explicit-backend `migrate(backend, ...)` entry point rather than
   the migration CLI, which loads production bootstrap settings. Obtain approval
   for synthetic staging DDL, repeat/concurrency checks and backup/restore tests.
   SQLite success does not close this gate.
3. **Approve production recovery and schema independently.** Verify a restorable
   backup, baseline tables/flags, maintenance owner and stop conditions. Only then
   separately authorize additive DDL in a maintenance window. DDL may auto-commit;
   do not automatically drop tables or restore over new records on failure.
4. **Approve code rollout separately.** Authorize the exact main merge/deployment/
   restart only after preceding gates. Keep profiles, history and new messaging
   disabled, then verify Phase 4 presence, names and observed durations unchanged.
5. **Approve profiles separately, if desired.** Confirm guild/staff permissions and
   command-sync scope. Enabling profiles registers the persistent check-in view
   and can reconcile linked-profile inactive flags/submission mirrors even while
   monthly scheduling is off. Keep history, check-ins, announcements and reminders
   disabled. Historical import is optional and remains deferred; it is not implied
   by profile enablement. Any manual profile creation or Xbox link is a separately
   approved write requiring reviewed ownership evidence.
6. **Approve private Stories access and retention separately, if desired.** Agree
   access, identity ownership, retention/deletion and backup protection first.
   Gate enablement permits previews, not blanket retention. Inspect snapshot age,
   unmatched/quarantine counts and private visibility before approving one snapshot's
   retention. There is no automatic history scheduler or corroboration system to enable.
7. **Keep public statistics and messaging off.** D1 and the own-data read authorize
   neither public histories nor automated statistics, announcements or reminders.
   Any such feature needs separate implementation, privacy review and activation approval.

Stop on schema mismatch, failed backup/restore evidence, identity conflicts,
unexpected side effects, privacy failure or a Phase 4 regression. Use only an
approved flag/code rollback; retain additive records/tables. No further participant
coordination or archive research is needed to accept this development closeout.
