# Phase 6: Stories activity semantics and controlled verification

November 3, 2026 (America/Chicago). Branch `codex/realms-phase6`, baseline `72c30ab`.
Initial scope: existing Stories evidence, synthetic tests and an approval-ready
diagnostic plan. The separately authorized short D1 execution is recorded below.
**No production writes, deployment, restart, main merge, profile activation,
Realm/Timeline changes or archive work occurred.**
Paused local historical-review files are outside this change and are not committed.

## Readiness decision

Short D1 update: access and an online/offline transition were verified, but all
three Stories snapshots were identical. The system remains unsuitable for confirmed
session durations or production playtime statistics; see the execution record below.

**Ready to propose a limited external diagnostic, not ready to activate a production
playtime/statistics pilot.** Account access and interval structure are verified from
the prior one-shot probe. Current-session semantics, time accuracy, publication delay,
corrections and completeness remain unknown. MariaDB staging/restore validation and
production activation approvals also remain separate gates.

Existing statistics are mathematically useful as **coverage of retained, plausible
Stories intervals in a specified window**. They are not verified historical playtime,
a guaranteed lower bound on playtime, or confirmed login/logout/session counts.
Leave the Phase 4 panel's first-observed **Online for** unchanged. Do not publish
leaderboards, assign roles, change check-in eligibility or activate profiles here.

## What the existing evidence establishes

The [Stories investigation](realms-stories-investigation.md) records one successful
GET with TheCaptain4322 and the existing Realms XSTS audience: HTTP 200, 27 identifier
keys, 95 intervals, integer `s,e`, and approximately 19.458 days between earliest
plausible start and latest plausible end. One integer end exceeded the plausible
current-time range. No independent player join/leave log was collected alongside it;
raw bodies and the exact anomalous end were not retained.

| Question | Verified evidence | Remaining limit |
| --- | --- | --- |
| Authentication/access | Prior 200 using existing account/audience; no changed opt-ins/scopes | Availability and privacy coverage can change; no new test here |
| Timestamp types | All 95 entries had integer `s,e`; source model interprets epoch seconds | Integer type does not prove event meaning, precision or completion |
| Historical intervals | Per-identifier interval lists were returned | Not all members, all seasons, or the full retention period |
| Currently online representation | **Not established** | No synchronized live snapshot/independent session was correlated with Stories |
| Updates while online | **Not established** | One snapshot cannot distinguish final ends, rolling ends, placeholders or post-disconnect publication |
| Rounding | Recorded extrema fell on hour boundaries | No full modulo/distribution measurement; cannot claim all entries are hourly rounded |
| Anomalous end | One integer was outside the plausibility bound | No exact value retained; cannot name it an active-session sentinel |
| Overlapping/revised intervals | Code can retain and union them | Their occurrence, revision rules and session meaning were not established live |

The earlier live-activity pilot and the Stories probe were not a controlled simultaneous
comparison. Their player counts must not be correlated to label any specific Stories
entry online. Absence from Stories never establishes offline status or no play.

## Synthetic validation results

Focused run: **60 passed** across `test_stories_semantics.py`, `test_realm_history.py`
and `test_realms_client.py`; Ruff F checks passed. The external-network test fixture
remains active. Synthetic SQLite contains only test identities; no production schema,
records or credentials were opened. These are verified **code behaviors**, not new
observations of Microsoft's service.

| Synthetic case | Result and implication |
| --- | --- |
| Null, zero, negative, huge and far-future hypothetical open ends | Quarantined; none is interpreted as online or converted into a fabricated disconnect |
| Plausible finite end at observation time | Accepted as observed interval, but has no online/completed flag; finite e does not prove departure |
| Same start with ends at +10, +20 and +30 minutes | Three records, one merged span, 30 minutes of union coverage rather than 60 minutes; **not three sessions** |
| Later end shrinks from +30 to +10 minutes | Both immutable observations remain; union remains 30 minutes. Latest-correction semantics are not modeled |
| Hypothetical hourly interval around independently known ten-minute play | Reports an hour of interval coverage, demonstrating possible overstatement if the upstream API uses coarse bins |
| Delayed interval and later empty snapshot | Existing evidence is retained, not deleted or reclassified offline; an initially empty store is no proof of zero actual playtime |
| Overlapping and adjacent entries | Union avoids double-counting; merged spans still cannot determine connection count or an unseen brief rejoin |
| End within current five-minute clock tolerance | Accepted, but a window ending now clips future time; asking for a future-ended window can include it |
| UTC day boundary and a real gap in the synthetic intervals | Window clipping preserves the gap and counts only the intersection |

`observed_statistics()` exposes `observed_seconds`, `recorded_intervals`, merged
span count and a clipped latest observed end, with `confirmed_sessions:null` and
`coverage:incomplete_unverified_stories`. A latest end clipped to a reporting window
is not necessarily the original disconnect time. Empty coverage is zero retained
interval coverage, not zero play. For a future report, use a window ending no later
than now and explicitly disclose sampling/privacy/retention uncertainty.

## Parser and statistics recommendations

No production parser/statistics behavior was changed in this task. The current
conservative checks are appropriate until live semantics are established:

1. Keep malformed/noninteger/nonpositive/reversed/pre-Minecraft/far-future values
   quarantined, with raw bounded evidence preserved. Do not convert null/0/negative/
   huge e to now, drop the end silently, infer online, or globally whitelist a guessed sentinel.
2. Keep `observed` separate from confirmed sessions. Plausibility acceptance means
   only that a timestamp can be represented and passes current bounds; it does not
   establish a completed session or an independently observed connection.
3. Treat public/display labels as a gate: describe union coverage, never “total
   played,” “exact sessions,” an AFK-adjusted statistic or all-member participation.
   Do not add live duration correction before open-interval matching and freshness
   are demonstrated. Statistics have no online-player input and cannot do that now.
4. If repeated reads establish an active-end sentinel or rolling end convention,
   design an explicit active/provisional state separately from completed history.
   Preserve the original observation and test transitions; do not promote all
   existing quarantine rows automatically. This is a future evidence-dependent change.
5. If upstream ends can be revised downward, immutable union coverage needs a
   reviewed revision/supersession model before actual-playtime reporting. Matching
   solely by XUID/start can incorrectly merge distinct or hour-bucketed sessions.
   The API supplies no verified stable session/revision ID; do not invent one.
6. If hourly rounding or delayed publication is observed, retain a qualified historical
   activity metric and disclose its resolution/lag. More sampling cannot recover exact
   within-bin connections. Any correction/estimator needs separately validated rules.

## Diagnostic D1 — exact plan requiring approval

This plan supersedes the broader optional comparison budget in earlier release notes
**for this proposed D1 only**. Previous one-shot authorization is exhausted and does
not authorize these requests. No diagnostic sampling has started.

### Preconditions and fixed boundaries

- One consenting participant already authorized to play Coastal Craft, a privately
  verified test XUID available beforehand, and an agreed UTC start T. No profile API
  lookup, account-link write, invitation, membership change or opt-in change is part
  of D1. If the identity or existing Timeline visibility cannot be established, stop.
- Start with the participant offline from the Realm. Use their ordinary Minecraft
  client to join and voluntarily leave once; no injected game client or bot connection.
  Proposed join at T+02:15 and departure at T+10:35, recorded as actually observed
  rather than assumed. Choose T near UTC minute :50 to cross an hour; do not change
  any system clock. No automatic extra sessions/rejoins under this budget.
- Max **20 minutes** after T, **5 live-activity GET attempts + 5 Stories GET attempts**,
  spaced at least 60 seconds apart across both routes, plus at most **4 authentication
  POST attempts**. A missed slot is skipped, not retried or caught up in a burst.
- Only existing Microsoft/Xbox auth endpoints and two exact fixed read routes for
  the configured Realm. No `/worlds`, profile lookup, Stories settings, People Hub,
  address/join, archive or other service routes. No Realm POST/PUT/PATCH/DELETE.

### Credential handling and transport

After approval, re-establish the already reviewed isolated encrypted-copy method
using the existing private diagnostic source, not the active production token store.
Verify identity/config binding, stable bounded source read, no links/hardlinks,
private ACLs and an independently locked copy. Persist any refresh only in that copy;
never copy back. Saved configuration remains disabled; enable only an in-memory
diagnostic instance. No interactive login, new app/scope/key or account change.
If isolation cannot be established, do not attempt authentication or GETs.

Authentication attempt caps, using the established service:

| Endpoint | Maximum POST attempts |
| --- | ---: |
| `https://login.microsoftonline.com/consumers/oauth2/v2.0/token` (existing refresh only) | 1 |
| `https://user.auth.xboxlive.com/user/authenticate` | 1 |
| `https://xsts.auth.xboxlive.com/xsts/authorize` (general Xbox identity check and Realms audience) | 2 |
| **Total** | **4** |

Use Realms audience `https://pocket.realms.minecraft.net/` and the configured
Bedrock Client-Version, `User-Agent: MCPE/UWP`, `Accept: application/json` and
XBL3.0 authorization. Stories additionally uses `Cache-Control: no-cache, no-store`.
The frontend hostname does not introduce a new XSTS audience. No token is printed.

The isolated sampler must enforce the attempt budget itself, disable automatic
retries, redirects, device login and rejection-triggered renewal, and use existing
TLS verification, no proxy/cookies, a 30-second request timeout and 1 MiB body cap.
Do not sample via `/playerprofiles activity` or the runtime's one-hour history cache:
five cached observations cannot measure publication changes. Do not change the
running bot's cache/polling/allowlists. At proposal time no live sampler had been
implemented/executed; the reviewed short-run sampler and execution are recorded below.

### Read schedule

`L` is `GET https://pocket.realms.minecraft.net/activities/live/players`.
`S` is `GET https://frontend.realms.minecraft-services.net/api/v1.0/worlds/{selected-id}/stories/playeractivity`.

| Time after T | Action | Measurement |
| --- | --- | --- |
| 00:00 | L1 | Offline baseline for test identity, if explicitly known |
| 01:00 | S1 | Historical baseline; participant still offline |
| 02:15 | Participant joins normally | Record join initiation and terrain-ready arrival in independent UTC log |
| 03:00 | L2 | First scheduled online observation |
| 04:00 | S2 | Early active-session representation |
| 07:00 | L3 | Later scheduled online observation |
| 08:00 | S3 | Compare start/end appearance and changes while still playing |
| 10:35 | Participant voluntarily leaves | Record disconnect request and return-to-menu separately |
| 11:00 | L4 | First scheduled offline observation |
| 12:00 | S4 | Initial post-departure publication |
| 17:00 | L5 | Later offline check; no scheduled rejoin |
| 18:00 | S5 | Delayed publication/end correction check |
| 20:00 | Hard stop | Close service/store; verify source unchanged and remove temporary credential copy |

Record both wall-clock UTC and monotonic request start/end times, HTTP status and
latency. L/S are not simultaneous; do not pair them as exact atomic observations.
Independent client event logs must record clock/synchronization uncertainty and
actual actions. UI arrival/departure times bound behavior, not exact server packet
acceptance. If the participant's schedule changes, preserve the real timestamps;
do not make extra calls or claim a successfully controlled session.

Abort remaining network work on auth failure, 401/403/429, malformed/bounded-body
failure, timeout, identity/Realm mismatch or source-store instability. No retry,
fallback account or privacy-setting change. Record Retry-After if available and
honor it; D1 does not resume after a rate-limit abort. A partial run is inconclusive,
not a successful empty/offline session. Stop if consent is withdrawn.

### Analysis and privacy

Filter to the selected Realm and consenting XUID in memory. Discard all other
players; no full response/body/error dumps, XUIDs, gamertags, Realm IDs, tokens or
per-player timeline in Git/public output. Do not create profile/activity database
records. Privately correlate observations under a temporary opaque test alias.
Use a protected, minimal participant event log; agree on retention before collection,
and discard any identity link after the comparison under that policy.

Compare S2/S3 to S1: missing/present entry, stable/moving s, finite/null/zero/huge e,
e movement, overlap and apparent timestamp modulo 60/3600. Compare S4/S5 after
departure for publication lag and corrections. A malformed e may be inspected as a
**type/range category** in memory for D1, but the production parser still quarantines
it. No special end value is treated as a confirmed sentinel by this test alone.

Publish only call/status counts, structural categories, valid/anomalous interval
counts and aggregate error/lag/rounding ranges with uncertainty. The sparse live
samples give join/departure brackets, not an exact server clock. Five Stories reads
can show changes between samples but only bound publication lag. No change within
18 minutes does not establish that publication happens only on disconnect or never.

D1 is a single-session first check, not a proof of retention, short rejoin handling,
all-player visibility or stable semantics. Further consenting sessions/windows and
their request budgets require separate approval. Before live-duration use, agree an
error target (for a minute-resolution panel, propose <=60s including clock/observation
uncertainty) and demonstrate open-session identification and bounded publication
lag repeatedly. If D1 cannot measure that precision, the result remains inconclusive.

## Approval and remaining uncertainty

Approval requested only for the concrete D1 diagnostic scope above: participant/time
coordination, **at most 10 read-only service GETs and 4 existing authentication POSTs**,
one normal client join/leave and no production changes. A production statistics pilot
would need a separate decision after evidence review, MariaDB staging and identity/
privacy gates. This document does not grant any of those approvals.

After short D1: online representation, active versus post-disconnect
updates, end sentinels, rounding, publication delay, revision rules, overlapping-session
semantics and retention remain **unknown**. The existing observed-activity model
can retain qualified evidence; it cannot yet certify historical playtime.

## Short D1 execution record — November 3, 2026 (America/Chicago)

The participant consented, confirmed existing Timeline visibility and authorized
one additional Xbox profile GET to verify the supplied test identity. The original
20-minute proposal was shortened at the participant's request. Only aggregate
results are retained here; no identifiers, raw timestamps or individual histories
are recorded. No historical source work or production functionality was changed.

### Partial attempt and explicit continuation approval

The first short attempt used four authentication POSTs, one profile GET and two
live GETs, all HTTP 200. Both live reads reported the participant absent. Its
60-second active-state cutoff stopped the sampler before the participant's join
confirmation reached the operator. That cutoff was too aggressive for client/chat
coordination. There were **zero Stories reads** and no valid session comparison.
The process closed, discarded its in-memory tokens/identity mapping and removed
its isolated credential copy; the encrypted source remained unchanged.

The participant subsequently returned offline. Before any additional network
requests, the operator presented the revised sampler and exact additional budget.
The participant explicitly approved up to four additional established authentication
POSTs, one additional profile GET, three live GETs and three Stories GETs. The Realm
reads stayed within the original D1 total caps. This was a separately coordinated
continuation join/departure, not uninterrupted observation of the first attempt.

The continuation waited for identity verification and the participant's independent
world-loaded confirmation **before starting any timed Realm reads**. It prompted
departure at approximately +140 seconds, then recorded the participant's return-to-menu
confirmation. The control-file receipt was +188.1 seconds; this is an operator/chat
receipt, not the actual client or server disconnect time. No exact client event log
or clock synchronization measurement was collected.

### Preparation and safety validation

The disposable sampler and its synthetic tests remain under ignored
`.test-tmp/d1-short/`; they are not bot features or an unattended recurring job.
Review covered fixed route/audience allowlists, per-route attempt caps, at least
60 seconds between Realm GET starts, no redirects, bounded response bodies,
fail-closed identity/presence checks and no automatic retries. aiohttp's implicit
connection retry was explicitly disabled. No extra endpoints, refresh-on-error,
interactive login or scope changes were allowed. The continuation had a six-minute
hard observation window and a bounded pre-start coordination wait.

**11 offline synthetic tests passed; Ruff F checks passed.** The tests use fake
HTTP sessions and block external network access. A sandboxed Windows asyncio run
stalled and was stopped; the same tests passed outside the sandbox with local
loopback available. These tests verify sampler guards, not service semantics.

Authentication used the established TheCaptain4322 implementation and a protected,
isolated copy of the existing encrypted local diagnostic store. Refresh persistence
was confined to that copy. The source store was not opened for writing, and no
running bot token store was accessed. The continuation's source SHA-256 comparison
confirmed unchanged encrypted bytes; the isolated directory was removed on exit.
Identity links and raw interval pairs were held in process memory only and discarded.

### Sanitized observations

Times below are approximate elapsed **response completion** times after the timed
start, not player event timestamps. The two active Stories samples were between
the independent arrival confirmation and departure prompt; presence snapshots are
not simultaneous with Stories reads.

| Elapsed seconds | Read | HTTP | Aggregate result |
| --- | --- | --- | --- |
| 0.4 | Live | 200 | Consenting participant online |
| 60.7 | Stories | 200 | 13 intervals; all `s,e` integers |
| 120.8 | Stories | 200 | Same 13 interval pairs; no value changes |
| 180.4 | Live | 200 | Consenting participant offline |
| 240.5 | Stories | 200 | Same 13 interval pairs; no value changes |
| 300.4 | Live | 200 | Consenting participant still offline |

Stories had the expected object envelope `result.activity`, whose identifier keys
map to arrays of interval objects. Only the consenting identity's `(s,e)` pairs
were retained for comparison; other players' data was discarded. All 13 sampled
starts and ends were positive integers divisible by 3,600, and all ends exceeded
their respective starts. One end exceeded observation time by more than five minutes;
no starts did. That anomaly remained unchanged after independently confirmed departure.
Every successive pair-set comparison reported **zero additions, zero removals and
zero same-start/changed-end candidates**. GET latencies were approximately
0.17–0.55 seconds. No exact anomalous value or player-level dates are retained.

Continuation totals: four authentication POSTs, one profile GET, three live GETs,
three Stories GETs; every response HTTP 200. Combined with the partial attempt:
**eight authentication POSTs, two profile GETs, five live GETs and three Stories
GETs**, covered by the original authorization and explicit continuation approval.
No other live requests or retries were made in these two attempts.

### Interpretation and remaining gates

- **Access and transition verified:** existing credentials accessed both read
  endpoints, and independent client reports plus live snapshots establish an
  online-to-offline transition. Sparse snapshots do not give exact connection times.
- **Active representation unresolved:** no changed pair could be attributed to the
  controlled session. A persistent far-future end is an anomaly, not a proven active
  sentinel; it also existed in the post-departure snapshot. Keep it quarantined.
- **No updates observed:** pairs were identical across two active reads and one
  post-departure read. This does not prove publication only on disconnect, absence
  of the session, or a particular cache/aggregation policy. Request cache-control
  cannot guarantee origin freshness or bypass server-side aggregation.
- **Publication delay unmeasured:** the last Stories read was about 100 seconds after
  the departure prompt and 60 seconds after the first offline live snapshot. Without
  an identifiable session interval or offline Stories baseline, there is no valid
  numerical publication-lag estimate or lower bound. Longer follow-up was not authorized.
- **Hour alignment observed, rounding rule unknown:** every sampled timestamp was
  hour-aligned. This supports concern about coarse time representation but does not
  establish floor/ceiling rules, exact precision or general behavior for all players.
- **Overlap/revisions unresolved:** no pair changes were observed. Overlap counts,
  raw date extrema, current-session matching and correction direction were not
  measured by this sampler. No new retention range was established; the earlier
  approximately 19.458-day envelope remains a separate observation, not a guarantee.

No parser or statistics change is justified by D1. Preserve anomalous-value
quarantine, independent live presence and the distinction between observed interval
coverage and confirmed sessions. Existing union coverage cannot safely be labelled
historical playtime, connection count or exact live duration. Do not use D1 to
activate profiles, announcements, leaderboards or production statistics.

**Not ready for a production playtime/statistics pilot.** A further diagnostic would
need separately approved participant/session coordination, endpoint/authentication
budgets and a longer observation window, with a genuine offline Stories baseline
and independently timed client events. It should explicitly test coarse boundaries,
identify which interval belongs to the session, and measure delayed updates and
overlap without presuming sentinel semantics. No further calls are authorized by
this document. Production rollout still requires the existing staging, privacy,
identity and activation gates plus separate user approval.
