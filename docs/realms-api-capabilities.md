# Phase 5: Bedrock Realms API capabilities

Research date: November 3, 2026 (America/Chicago). Local baseline: `a3a8925`.
Branch: `codex/realms-phase5`. Documentation only; Phase 6 is not authorized.

## Executive summary

Three Realm capabilities are **Verified** for TheCaptain4322 by the recorded
[November 3 pilot](realms-live-pilot-results.md): discovery, selected-Realm
details, and live player activity (HTTP 200 each). This research made **zero new
authenticated calls**. The private Windows diagnostic remains disabled; its
selected Realm is configured. Enabling it would change the existing policy, so
credentials were not decrypted, renewed, regenerated, or copied. Production
configuration, database, bot process, request allowlists, and PortalBot are unchanged.

The inventory below contains **53 unique method/path templates**: **23 GET,
12 POST, 14 PUT, 4 DELETE, 0 PATCH**, including four existing authentication
routes, related Xbox reads, and explicitly uncertain source conflicts. These are
discovered candidates, **not 48 guaranteed working Bedrock endpoints**. Parameter
values, alternate request bodies, and `latest` versus a backup ID count once.
No finite public source establishes an exhaustive server contract.

Live activity has no join-time field in the inspected implementations. A separate
**Realms Stories** endpoint models historical start/end timestamps; account access,
privacy opt-in, retention, completeness, and current service behavior are unverified.
Phase 4's first-observed **Online for** remains the supported session measure.

## Evidence and classification

**Verified** means a successful account test recorded in this repository;
**Implemented** means code exists without independent successful account evidence;
**Documented** means a reference describes it; **Permission restricted** requires
evidence our account lacks the required privilege; **Unknown** means evidence is
insufficient; **Deprecated** requires evidence of retirement. No endpoint here is
classified Deprecated, and no account ownership restriction is independently proven.
An operator flag in a player record is not proof of Realm ownership or API admin access.

Source keys are linked in the source register. Confidence H = actual client source
or official contract; M = older author research/shared Java-Bedrock abstraction;
L = conflicting/commented code. Confidence concerns the reference, not account access.

## Current implementation and security boundary

`utils/integrations/realms/{microsoft,xbox,service,token_store}.py` implement the
Captain-owned public-client consumers-v2 flow, `XboxLive.signin offline_access`,
RPS user token, separate general-Xbox and Realms XSTS audiences, expected identity
validation, encrypted refresh persistence, expiry/401 renewal, account binding and
single-writer locking. No game login, borrowed application, or account switch is needed.

`client.py` and `transport.py` both restrict Realms to five GET templates: `/worlds`,
the exact selected `/worlds/{id}`, `/activities/live/players`, `/invites/pending`,
and `/invites/count/pending`. The last two are helpers, not current Discord commands.
`profiles.py` permits only a fixed batch Gamertag POST with 1–100 unique valid XUIDs.
Other hosts, routes, methods, profile settings, cookies, proxy environment and redirects
are denied. Transport concurrency is two, total timeout 30 seconds, body cap 1 MiB.

`utils/realms/{runtime,cog,panel,names}.py` provide serialized shared observations,
Coastal guild/CoastalOPTeam authorization, ephemeral commands, persistent public panel,
encrypted active-session and name-cache records. Discord role permission and Microsoft
account permission are separate checks. Public panels expose names/counts and estimated
durations, never XUIDs or raw bodies. See [response fields](realms-api-response-fields.md).

## HTTP method and authorization matrix

Every numbered row below is a distinct method/path template. Unless stated otherwise,
base **R** is `https://pocket.realms.minecraft.net`, auth **R** is Realms-audience XSTS
in `Authorization: XBL3.0 x=<userhash>;<token>`, plus configured `Client-Version`,
`User-Agent: MCPE/UWP`, and JSON Accept. No query/body means none in inspected code.
`id` is a Realm ID, `xuid` a player ID, `inv` an invitation ID, `code` a secret link.

Permission codes: **A** authenticated account; **M** accessible/member Realm;
**O?** ownership expected from operation/client documentation, not tested; **S** self
invitation/membership; **P** profile access subject to privacy/title policy;
**T?** Stories eligibility/opt-in unknown. O? operations may require the owner's account;
in-game operator status should not be assumed sufficient. Every non-GET is prohibited
from live execution in Phase 5, including read-only POSTs and authentication exchanges.

### GET inventory (complete list discovered in inspected sources)

All are nominal retrieval operations. GET alone is not sufficient proof of safety:
join/address provisioning, archive preparation and invitation-secret retrieval are
excluded from the proposed initial probe. None outside the existing five are allowlisted.

| # | Base/path | Purpose; parameters → response fields | Permission; risk | Captain status | Source/confidence |
| --- | --- | --- | --- | --- | --- |
| 1 | R `/worlds` | Accessible Realms → `servers[]`, Realm metadata | A; roster/IDs | Verified, 200 pilot | C,E,B / H |
| 2 | R `/worlds/{id}` | Selected details → Realm object | M; roster/IDs | Verified, 200 pilot | C,E,B / H |
| 3 | R `/activities/live/players` | All visible activity → `servers[{id,full,players}]` | M; presence privacy | Verified, 200 pilot | C,E / H |
| 4 | R `/invites/pending` | Account's incoming invitations → `invites[]` | S; other Realm/owner identities | Implemented | C,E,B / H |
| 5 | R `/invites/count/pending` | Incoming count → nonnegative integer | S; low disclosure | Implemented | C,E,B / H |
| 6 | R `/worlds/{id}/join` | Connection provisioning → `address` host:port | M; address, possible provisioning | Documented | B / H |
| 7 | R `/worlds/v1/link/{code}` | Resolve link → Realm | A + valid secret; wrapper can auto-accept | Documented | B,E / H |
| 8 | R `/links/v1?worldId={id}` | Existing link metadata → array: `linkId,profileUuid,type,ts,url,deepLinkUrl` | O?; join secrets | Documented | B / H |
| 9 | R `/worlds/{id}/backups` | Backup list → `backups[{backupId,lastModifiedDate,size,metadata}]` | O?; world metadata | Documented | B shared / M |
| 10 | R `/subscriptions/{id}` | Subscription summary → `startDate,daysLeft,subscriptionType` | O?; billing metadata | Documented | B shared / M |
| 11 | R `/subscriptions/{id}/details` | Details → `type,store,startDate,endDate,renewalPeriod,daysLeft,subscriptionId` | O?; billing identifiers | Documented | B shared / M |
| 12 | R `/archive/download/world/{id}/{slot}/{backup}` | `backup=latest` or ID → `downloadLink`/`downloadUrl,token,size` | O?; whole-world export, bearer URL | Documented | B / H |
| 13 | R `/clubs/membercount` | Account Realm membership limits → `memberCount,memberLimit,overLimit` | A; account metadata | Documented | E / H |
| 14 | R `/worlds/{id}/stories/settings` | Stories configuration → opt-in/settings object | T?; privacy settings | Documented | E / H |
| 15 | `https://frontend.realms.minecraft-services.net/api/v1.0/worlds/{id}/stories/playeractivity` | History → `result.activity`, XUID-keyed lists of `{s,e}` | T?; historical behavior | Documented; audience compatibility Unknown | E / H |
| 16 | R `/worlds/{id}/blocklist` | Blocked players → schema not established | O?; moderation data | Documented | I / M |
| 17 | R `/mco/v1/news` | Service news → schema not established | A?; low disclosure | Documented | I / M |
| 18 | R `/mco/stageAvailable` | Environment compatibility → schema not established | A?; low disclosure | Documented | I / M |
| 19 | R `/mco/client/compatible` | Client compatibility → schema not established | A?; version-dependent | Documented | I / M |
| 20 | R `/trial/new` | Trial eligibility → schema not established | A; commercial/account metadata | Documented | I / M |
| 21 | `https://profile.xboxlive.com/users/xuid({xuid})/profile/settings?settings=Gamertag` | Identity → `profileUsers[].id,settings[]` | P; general Xbox XSTS; identifiers | Documented; Captain denies route | X / H |
| 22 | `https://profile.xboxlive.com/users/gt({gamertag})/profile/settings?settings=Gamertag` | Reverse identity lookup → same profile structure | P; general Xbox XSTS; encode gamertag | Documented; Captain denies route | X / H |
| 23 | `https://userpresence.xboxlive.com/users/xuid({xuid})` | Xbox presence → `xuid,state,devices[].type,titles[]` | P; general Xbox XSTS; gaming privacy | Documented; Captain denies route | U / H |

### POST inventory

| # | Base/path | Purpose; body → response | Permission; effect/risk | Captain status | Source/confidence |
| --- | --- | --- | --- | --- | --- |
| 24 | R `/links/v1` | `{type:"INFINITE",worldId}` → link metadata | O?; changes join link/access | Documented | B / H |
| 25 | R `/invites/v1/link/accept/{code}` | No body → Realm | S; joins membership | Documented | B,E / H |
| 26 | R `/worlds/{id}` | `{name,description}` → not established | O?; rename/configuration | Documented | B shared / M |
| 27 | R `/worlds/{id}/blocklist/{xuid}` | No body → not established | O?; ban/disconnection | Documented | B / H |
| 28 | R `/worlds/{id}/stories/settings` | Optional `autostories,coordinates,notifications,playerOptIn,realmOptIn,timeline` → not established | T?; changes privacy and visibility | Documented | E / H |
| 29 | R `/worlds/{id}/configuration` | Description/options including mode, difficulty, rules, packs → not established | O?; broad world changes | Unknown (POST vs PUT conflict) | I vs B comment / L |
| 30 | `https://profile.xboxlive.com/users/batch/profile/settings` | `{userIds:[xuid],settings:["Gamertag"]}` → `profileUsers[{id,settings:[{id,value}]}]` | P; read-only, contract 2, Xbox XSTS | Implemented; not live tested here | C,X,F / H |
| 31 | `https://peoplehub.xboxlive.com/users/me/people/batch/decoration/{decoration}` | `{xuids:[]}`, default `presencedetail` → `people[]` | P; read-only, contract 3; excessive profile exposure | Documented; audience acceptance untested | X / H |
| 32 | `https://login.microsoftonline.com/consumers/oauth2/v2.0/devicecode` | Form `client_id,scope` → challenge/expiry/interval | Public client; initiates login | Verified in pilot | C,A / H |
| 33 | `https://login.microsoftonline.com/consumers/oauth2/v2.0/token` | Device grant or refresh form → access/refresh tokens | Device grant/refresh secret; credential rotation | Verified in pilot | C,A / H |

Two further authentication routes are listed in the supplemental inventory below.

### PUT inventory

| # | Base/path | Purpose; body/query → response | Permission; effect/risk | Captain status | Source/confidence |
| --- | --- | --- | --- | --- | --- |
| 34 | R `/invites/accept/{inv}` | No body → not established | S; accepts membership | Documented | B,E / H |
| 35 | R `/invites/reject/{inv}` | No body → not established | S; rejects invitation | Documented | B,E / H |
| 36 | R `/invites/{id}/invite/update` | `{invites:{xuid:"ADD"/"REMOVE"/"OP"/"DEOP"}}` → Realm; `invites:null` only older issue | O?; membership/privilege changes | Documented | B,E,I / H (null M) |
| 37 | R `/worlds/{id}/open` | No body → not established | O?; service availability | Documented | B shared / M |
| 38 | R `/worlds/{id}/close` | No body → not established | O?; kicks/disrupts players | Documented | B shared / M |
| 39 | R `/worlds/{id}/slot/{slot}` | Slot 1–3 → not established | O?; active world replacement | Documented | B shared / M |
| 40 | R `/worlds/{id}/reset` | No body in client → not established | O?; world loss | Documented | B / H |
| 41 | R `/worlds/{id}/backups?backupId={backup}&clientSupportsRetries` | Encoded backup ID → client passes raw result | O?; rollback/lost progress | Documented | B shared / M |
| 42 | R `/world/{id}/content/texturePacksRequired` | No body → not established | O?; forced pack policy | Documented | B / H |
| 43 | R `/world/{id}/defaultPermission` | `{permission:"VISITOR"/"MEMBER"/"OPERATOR"}` → not established | O?; broad privileges | Unknown path conflict: I uses `/worlds/` | B / L |
| 44 | R `/world/{id}/userPermission` | `{permission,xuid}` → not established | O?; player privileges | Unknown path conflict: I uses `/worlds/` | B / L |

### DELETE inventory

| # | Base/path | Purpose; body → response | Permission; effect/risk | Captain status | Source/confidence |
| --- | --- | --- | --- | --- | --- |
| 45 | R `/worlds/{id}/blocklist/{xuid}` | No body → not established | O?; removes ban | Documented | B / H |
| 46 | R `/invites/{id}` | No body → not established | S; leaves/removes joined Realm | Documented | B,E / H |
| 47 | R `/world/{id}/content/texturePacksRequired` | No body → not established | O?; disables forced packs | Documented | B / H |
| 48 | R `/worlds/{id}` | No body → not established | O?; destructive deletion | Documented | B shared / M |

### Additional authentication and conflicting candidates

For clarity these are counted in the final totals too:

| # | Method/base/path | Request → response | Permission/risk; status | Source |
| --- | --- | --- | --- | --- |
| 49 | POST `https://user.auth.xboxlive.com/user/authenticate` | RPS ticket, `RelyingParty:http://auth.xboxlive.com`, `TokenType:JWT` → `Token,NotAfter,DisplayClaims.xui` | OAuth access secret; Verified pilot | C,A |
| 50 | POST `https://xsts.auth.xboxlive.com/xsts/authorize` | `UserTokens`, `SandboxId:RETAIL`, target `RelyingParty` → token/claims | User token; Verified pilot for both existing audiences | C,A |
| 51 | PUT R `/worlds/{id}/configuration` | Commented client accepts configuration → unknown | O?; Unknown, conflicts with POST #29 | B commented code |
| 52 | PUT R `/worlds/{id}/defaultPermission` | `{permission}` → unknown | O?; Unknown, conflicts with #43 | I |
| 53 | PUT R `/worlds/{id}/userPermission` | `{permission,xuid}` → unknown | O?; Unknown, conflicts with #44 | I |

**Final inventory total: 53 templates: GET 23, POST 12, PUT 14, DELETE 4,
PATCH 0.** This includes all five supplemental rows.
No evidence established PATCH, HEAD, OPTIONS, or WebSocket operations as supported
Bedrock capabilities; do not infer absence from this research. Signed world-file
download URLs are dynamic outputs, not an additional fixed API template here.

## Realm information and reliability

Direct metadata candidates from B/E are `id,name,owner,ownerUUID,state,daysLeft,
expired,expiredTrial,gracePeriod,maxPlayers,activeSlot,slots,defaultPermission,
worldType,member,clubId,motd,subscriptionRefreshStatus,remoteSubscriptionId` and
minigame fields. These are source-model candidates, not a schema observed for our
account. E explicitly distinguishes discovery from individual details: individual
details need not contain expiration/owner-name fields. Captain retains only ID,
name, state, nullable players and nullable expired; additional fields are discarded.

Capacity must be read and validated; never infer `/10` or owner slot semantics.
OPEN means configured state, not game-protocol reachability. Client-Version is a
request compatibility header, not the running world's version. The pilot accepted
1.26.61; this is dated acceptance, not a recommendation to pin it indefinitely.
Postman's 1.18.2 example is historical. Client updates can invalidate assumptions.

Slots/settings may expose world names, mode, difficulty and rules, but `slots` is
loosely typed in E and unavailable/null in some responses. B's backup metadata
models `game_difficulty,name,game_server_version,enabled_packs,description,game_mode,
world_type`, plus backup ID/time/size. A backup version describes that backup, not
necessarily the current running world. Exact subscription dates/store require
additional summary/detail requests, normally owner-sensitive. Never publish billing
IDs, download tokens or invitation URLs.

World upload/replacement, kick, pack application and full configuration are advertised
in Postman's overview, but its rendered documentation did not expose individual
requests in this session. No exact upload/kick protocol is invented here. Reset,
slot switch and restore are documented separately; none is a safe upload substitute.

## Player information, history and Xbox lookup

`uuid` in Bedrock player objects represents a decimal Xbox XUID, not a Java UUID.
The Captain uses it as stable identity, keeping gamertags as changeable display names.
Available modeled flags include `accepted,operator,online,permission`; their presence
and correctness are not independently established field-by-field in the pilot.
Discovery/detail `players` may be null and describe membership rather than live
connection. Use dedicated activity for presence; unknown/omitted data is never zero.

Live activity supplies a multi-Realm snapshot, not an event stream. Inspected models
have no session ID, device, IP, login timestamp or join/leave event. Name is explicitly
null in E's model; Captain permits a future non-null string. Compare consecutive
successful snapshots to estimate transitions. First observation may be later than
login; short sessions/rejoins between polls and downtime can be missed. Phase 4
retains only active session starts, not departed-session history.

Stories #15 is a separate history candidate: `result.activity` maps identifiers to
entries `s,e`, interpreted by E as epoch seconds. These are potentially historical
session intervals, not a verified exact-login API for this account. Open intervals,
timezone boundaries, opt-outs, retention and fidelity require a separately approved
probe. Do not replace the live clock or treat missing history as player absence.

Incoming invitations (#4–5) belong to the bot account. They are not all pending
outgoing invitations to Coastal Craft. A member directory would need validated
membership records, accepted flags and roster visibility; it is not the live list.

Official Profile batch #30 uses general Xbox XSTS and contract 2; E uses contract 3
in its own lookup helpers. Captain correctly follows the official contract and
must not change versions speculatively. The minimal request returns ID/Gamertag
settings. Official examples also describe display name/picture and gamerscore, but
Captain intentionally forbids those settings. Single profile GET helpers are not
proof an arbitrary app can use them: Microsoft's batch page warns about client
route restrictions. No account test establishes access to either variant.

People Hub #31 models gamertag/modern gamertag/suffix, picture, score, social flags,
presence state/text and optional title/device decorations. It can also return real
names and other unrelated data: high privacy cost for a name lookup. Xbox presence
#23 and People Hub may identify a device/title when visible, but Minecraft activity
does not identify Coastal Craft and cloaking/privacy can omit data. Do not use it
as Realm presence or as authoritative device attribution to a specific Realm session.
Presence GET supports an optional `level=user|device|title|all` filter and requires
Xbox contract-version, Accept and locale headers. Its official contract permits
HTTP 200 with content suppressed by privacy rules; status alone does not establish
visible presence. Title-presence timestamps are not Realm login timestamps.

No account-specific numeric Xbox quota was established. Captain limits name batches
to once per 60 seconds, 100 entries, positive TTL 24h, negative TTL 15m, timeout 8s,
and persisted error backoff 60s–1h (or longer Retry-After). Names and next-lookup time
are encrypted; stale names expire. These are local limits, not Microsoft's quota.

## Live verification and account capability matrix

| Capability group | Classification for TheCaptain4322 | Evidence/limit |
| --- | --- | --- |
| Discovery, selected details, live activity | Verified: **3 Realm capabilities** | Three pilot HTTP 200s; one activity snapshot with two records, no controlled login comparison |
| Microsoft device login, token exchange/refresh, Xbox user token, general and Realms XSTS | Verified separately from Realm capability count | Pilot account match and fresh-process encrypted credential reuse; do not count renewal as a new Realm feature |
| Incoming invitation list/count | Implemented: **2** | Allowlisted parser helpers, no recorded account test |
| Gamertag batch lookup | Implemented: **1** | Fixed route/cache; Phase 4 notes say access not live verified |
| Session estimates/panel | Implemented local features; user reports functioning production | No independent Phase 5 live verification; not extra upstream endpoints |
| Other retrieval and management rows | Documented or Unknown as individually labeled | No successful account calls; owner role unknown |
| Owner-only administration | Unknown account eligibility | May require owner account; cannot mark Permission restricted without proof of missing ownership |
| Deprecated capabilities | None established | Old examples and conflicting paths are not retirement evidence |

Pilot schemas were not retained as raw bodies. Only typed success, count and OPEN
were recorded; optional-field presence cannot be reconstructed. No new HTTP status,
429 rate observation, raw-schema capture or Profile success is claimed. A private
configuration presence/enabled check was read-only; disabled remained false.

## Phase 4 polling and continuous-operation assessment

Source review: `runtime.py` serializes commands/polls; normal cache 60s, forced
refresh cooldown 30s, scheduled observations bypass cache with 15s minimum spacing.
Each successful cycle fetches details then activity, under a 45s observation budget.
One activity request can cover all visible Realms, although Captain intentionally
selects one; per-Realm detail requests would scale separately.

At 15s: 5,760 cycles/day, **11,520 Realm GETs/day**, excluding retries/auth/name reads.
At 60s with both calls: 2,880 GETs/day. RealmsPlayerlistBot's current source schedules
activity on minute boundaries. That is useful operational precedent, not a published
quota or proof that any interval is universally safe. No sustained measurement
establishes 15s safety for Captain; it is defensively implemented but unvalidated.

Client retries 429/502/503/504 twice with exponential delay+jitter, honoring
Retry-After seconds or HTTP date; delays >30s propagate instead of early retry.
One 401 renewal is allowed. Runtime failure delay doubles 15s to 900s and honors
longer Retry-After. A details failure postpones activity in that cycle. Retained
snapshots are labeled unavailable/stale; missing Realm data does not end sessions.

Discord edits have separate failure backoff and discord.py rate-limit handling.
Unchanged embeds are skipped, though observation timestamps/durations often change.
API polling and rendering/error handling are logically separated but driven by the
same panel schedule; there is no independent slower metadata poller. Session math
adds no requests. Recommend separately scheduling slower details and 60s activity,
with optional local duration rendering, after review. No cadence/config changes here.

Potential reliability gaps for a future phase: Realms runtime backoff is in memory
(restart resets it, unlike persisted profile lookup timing); a missing selected Realm
does not itself raise an HTTP error/backoff; finite retries plus timeout do not prove
long-duration renewal or service stability. Monitor sanitized success ages/status
counts before changing behavior. No load test should be run against production.

## Proposed safe verification plan — approval required before expanded access

This is a reviewable plan, not executed permission to widen the boundary:

1. Authorize a temporary isolated diagnostic configuration in memory using the
   existing account/store and explicit operator identity. Keep the on-disk disabled
   configuration unchanged; never compete with the production single-writer store.
   If existing credential reuse requires rotation/storage outside approved scope,
   stop. Do not log tokens, names, XUIDs, Realm/invitation IDs or raw errors.
2. Reuse only currently allowlisted GETs once each: discovery, exact selected details,
   activity, then incoming invitation count. List invitations only if needed; retain
   structure/count, not unrelated owners/Realm names. Record status, field paths,
   types, nullability and array counts; use synthetic placeholders in published docs.
3. Obtain explicit approval for **both client and transport allowlist additions**:
   selected `/worlds/{id}/stories/settings`, external Stories playeractivity host/path,
   selected `/worlds/{id}/backups`, then subscription summary only if owner eligibility
   and need are established. Separate approvals by privacy scope; no generic URL access.
   Confirm correct Stories audience/headers from references before sending a token
   to the new host. Metadata-only archive analysis is not a download authorization.
4. Space probes at least 60s, one attempt each, stop on 401/403/429, respect Retry-After,
   never switch accounts, retry aggressively or infer access denial from a missing field.
   No `/join`, secret links, archive generation, world bytes, profile POST, mutations,
   Stories opt-in changes or auth re-enrollment in this plan.
5. Separately review whether to allow the already implemented read-only Profile POST;
   Phase 5's no-POST rule excludes live testing it here. For Stories, first retain
   key/type/time-range summaries, not per-player historical intervals. A controlled
   in-game comparison, if later approved, can assess timestamp accuracy and polling gaps.

Unanswered: exact account ownership; optional fields by access level; maximum-player
semantics; Stories eligibility/retention/accuracy; current upload/kick/configuration
contracts; effective app-specific Xbox quota; long-running 15s stability. See the
[ranked roadmap](realms-api-roadmap.md) for feature value and dependencies.

## Source register

Public references retrieved November 3, 2026. GitHub commit timestamps, not repository
`pushed_at`, determine inspected code age. No dependency or upstream code was imported.

- **C:** Captain baseline `a3a8925`, files cited above, [pilot](realms-live-pilot-results.md),
  [Phase 4 panel](realms-live-panel.md), [authentication](realms-authentication.md).
- **B:** [Prismarine Realms Bedrock client](https://github.com/PrismarineJS/prismarine-realms/blob/fad98435fd834e4d2280ab86a636561630a25f19/src/bedrock/api.js),
  [shared API](https://github.com/PrismarineJS/prismarine-realms/blob/fad98435fd834e4d2280ab86a636561630a25f19/src/index.js),
  [structures](https://github.com/PrismarineJS/prismarine-realms/tree/fad98435fd834e4d2280ab86a636561630a25f19/src/structures).
  October 6, 2026 revision; shared abstractions are weaker Bedrock evidence.
- **A:** [Prismarine authentication](https://github.com/PrismarineJS/prismarine-auth/blob/edd7aca2f4158da5f64542f138cdd18592f619a2/src/MicrosoftAuthFlow.js),
  October 6, 2026. Supports multiple flows; Captain keeps its own already working flow.
- **E:** [elytra Bedrock client](https://github.com/Astrea-Stellarium-Labs/elytra-ms/blob/ec666db90d719806475e0c161420ae17cd1efe9c/elytra/bedrock_realms/__init__.py),
  [models](https://github.com/Astrea-Stellarium-Labs/elytra-ms/blob/ec666db90d719806475e0c161420ae17cd1efe9c/elytra/bedrock_realms/models.py).
  Main resolves to historical October 2, 2024 code; recent push metadata does not prove code maintenance.
- **X:** [elytra Profile](https://github.com/Astrea-Stellarium-Labs/elytra-ms/blob/ec666db90d719806475e0c161420ae17cd1efe9c/elytra/xbox/profile/__init__.py),
  [People Hub](https://github.com/Astrea-Stellarium-Labs/elytra-ms/blob/ec666db90d719806475e0c161420ae17cd1efe9c/elytra/xbox/peoplehub/__init__.py),
  [People models](https://github.com/Astrea-Stellarium-Labs/elytra-ms/blob/ec666db90d719806475e0c161420ae17cd1efe9c/elytra/xbox/peoplehub/models.py).
- **F:** [Microsoft batch Profile contract](https://learn.microsoft.com/en-us/windows/uwp/xbox-live/xbox-live-rest/uri/profilev2/uri-usersbatchprofilesettingspost),
  [Microsoft native Profile implementation](https://github.com/microsoft/xbox-live-api/blob/main/Source/Services/Social/profile_service.cpp).
- **U:** [Microsoft Presence GET contract](https://learn.microsoft.com/en-us/gaming/gdk/docs/reference/live/rest/uri/presence/uri-usersxuidget).
- **I:** [Prismarine coverage issue #34](https://github.com/PrismarineJS/prismarine-realms/issues/34).
  Older author-maintained checklist, contains singular/plural paths and method conflicts;
  checked boxes are not account tests. Java-only activity/minigame routes excluded.
- [Postman requested documentation](https://www.postman.com/lucienhh/bedrock-realms/documentation/pda92ab/bedrock-realms-api),
  [accessible collection overview](https://www.postman.com/LucienHH/bedrock-realms/collection/pda92ab/bedrock-realms-api).
  Overview available, full request bodies unavailable from rendered page. Historical
  version/password/proxy examples were not adopted or used for authentication.
- [Home Assistant research](https://github.com/LucaFSmart/ha-minecraft-bedrock-realms/blob/72b2063b670faba56b37d9c43d66d531c9ec88de/docs/research.md),
  [architecture](https://github.com/LucaFSmart/ha-minecraft-bedrock-realms/blob/72b2063b670faba56b37d9c43d66d531c9ec88de/docs/architecture.md).
  Useful secondary analysis, not Captain evidence. Its blanket claims about live names,
  permissions and cadence are not assumed service guarantees; source-model differences
  and historical revision dates above take precedence.
- [RealmsPlayerlistBot polling](https://github.com/AstreaTSS/RealmsPlayerlistBot/blob/383881782c2a2fd38796f5ba8adf70409f2e341b/exts/playerlist.py),
  October 24, 2026 revision: minute scheduling, activity fetch, separately requested
  device enrichment. Mechanism inspected; no AGPL implementation copied.

Java uses different paths/authentication (for example `/activities/liveplayerlist`
and `/activities/{id}`); neither is established as a Bedrock history substitute.
