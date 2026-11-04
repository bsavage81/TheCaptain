# Realms Stories player activity investigation

Date: November 3, 2026 (America/Chicago). Code baseline: `a3a8925`;
Phase 5 documentation: `d1c844c`. Isolated branch:
`codex/realms-stories-investigation`. Documentation only.

## Result and execution decision

**Verified: one authenticated Stories GET returned HTTP 200 for Coastal Craft
using TheCaptain4322.** The response matched `result.activity` and contained
**27 player identifier keys and 95 interval objects**, each with integer `s,e`.
Existing authentication/audience sufficed; no interactive login, new scope,
consent, account change or privacy change was needed.

The initial investigation stopped under the original no-authentication-POST rule.
The user subsequently authorized the minimum established authentication exchanges
and persistence in an isolated protected store copy. This update records the
result of that authorized follow-up, not a change to production functionality.

Four authentication POSTs returned 200: Microsoft refresh, Xbox user token, general
Xbox XSTS for identity validation, and Realms XSTS. Exactly one Realm-service GET
was attempted, with no retry or redirect. Source encrypted account bytes were
unchanged after the run; all refresh persistence occurred in the temporary copy.
That copy was removed after the service and store closed. No live store lock was
acquired, no running-process memory inspected, and no production process contacted.
No production allowlist, configuration, database, privacy setting or opt-in was
changed. No bot restart, deployment, or PortalBot modification occurred.

## Exact request established by source

elytra-ms's `BedrockRealmsAPI.fetch_realm_story_player_activity(realm_id)` issues:

```http
GET https://frontend.realms.minecraft-services.net/api/v1.0/worlds/{id}/stories/playeractivity
Authorization: XBL3.0 x=<userhash>;<xsts_token>
Client-Version: <Bedrock client version>
User-Agent: MCPE/UWP
Cache-Control: no-cache, no-store
```

| Property | Source-established behavior | Remaining uncertainty |
| --- | --- | --- |
| Method | GET; `use_url_as_is=True` selects the absolute external URL | HTTP 200 in this probe |
| Audience | `https://pocket.realms.minecraft.net/` with trailing slash | Accepted in this single probe; continued availability not guaranteed |
| Token format | XBL3.0 header from existing XSTS user hash and token | Fresh token obtained through established auth using isolated copy |
| Path parameter | Realm ID, passed as integer or string | Selected Coastal ID stays private |
| Query parameters | None in inspected helper | No supported date range, cursor, page size or pagination contract found |
| Request body | None | Do not add a JSON body to the GET |
| Explicit headers | Four headers shown above | These reproduce a client implementation, not an official minimum-required-header contract |
| Accept | Not explicitly supplied by this helper/base headers; HTTP library may supply defaults | A future diagnostic can request JSON, but this is not a proven required header |
| Xbox contract version | Not supplied by this Stories helper | Do not borrow Profile/People Hub contract versions |
| Client version | elytra constant is historical `1.21.21` | Captain pilot accepted `1.26.61` for other Realms routes; neither establishes Stories compatibility |

Important: the frontend hostname is **not** used as a new relying-party audience
in elytra. `BedrockRealmsAPI.RELYING_PATH` is the pocket Realms base URL.
`BaseMicrosoftAPI.request()` combines the same base headers with the absolute
URL; `use_url_as_is` changes routing, not authentication. Captain already supports
this Realms audience. This is strong implementation evidence for token reuse,
not successful account verification and not authorization to export a live token.

The reference transport automatically checks/refreshes authentication before
every request, can refresh after rejection, and uses retry infrastructure.
Calling that helper directly would not guarantee exactly one GET or zero POSTs.
It was inspected as source only, not installed or run.

## Response structure: reference and live confirmation

Source: elytra's `RealmStoryPlayerActivityResponse`, `RealmStoryPlayerActivity`,
and `RealmStoryPlayerActivityEntry`. The successful Coastal response confirmed
this structure and the integer timestamp types:

```text
object
  result: object
    activity: object/map
      <player identifier string>: array
        entry: object
          s: integer
          e: integer
```

| Field | Reference type | Meaning and limits |
| --- | --- | --- |
| `result` | object, required | Wrapper; no default/null alternative in model |
| `result.activity` | string-keyed map, required | Per-player interval lists; empty map is structurally possible |
| Map key | string | Expected Xbox player identifier/XUID in this Bedrock context; model does not validate format or resolve names |
| Map value | array of entry objects | Empty list structurally possible; no declared maximum/history window |
| `s` | integer, required | Named `start_timestamp`; converted with `datetime.fromtimestamp(value, tz=UTC)` |
| `e` | integer, required | Named `end_timestamp`; converted identically |

The reference decoder expects epoch **seconds**, not milliseconds. It specifies
neither null end times nor defaults. It does not validate `e >= s`, current-session
sentinels, ordering, overlaps, identifier format or retention. An integer end does
not prove the player has disconnected: an active session could be represented by
a rolling boundary, sentinel or other convention not described by this model.
No field provides a gamertag, device, disconnect reason or independently verifiable
connection event identifier in this schema.

The map structure can distinguish individual players and associate multiple
intervals with each identifier. It is therefore sensitive behavioral data even
without names; existing gamertag resolution could potentially identify people.
No identifiers, per-person intervals, or examples copied from account data are
included here.

## Do s/e mean actual connection and disconnection?

**Historical activity boundaries are accessible, but exact network connection/
disconnection semantics are not proven.** The strongest reference evidence is the explicit
start/end naming and UTC timestamp conversion in elytra. Mojang describes Timeline
as showing when Realm members played and supporting concurrent-activity planning.
That supports a history interpretation, not an exactness or latency guarantee.

Unresolved: server versus client clock, time granularity, rounding, delayed ingestion,
short-session omission, Realm restarts, interval merging, incomplete sessions, and
whether `e` changes while a player remains online. No fixture, authoritative wire
contract or controlled connection comparison was found to settle these questions.
The successful response adds evidence of per-player integer intervals, but one
end value lies outside the plausible current-time range. Do not call `s` an exact
login time or `e` a confirmed disconnect event yet.

## Privacy, permissions and retention

Official Mojang 1.21.50 release notes distinguish Timeline opt-in from Story Feed
and Members access: the latter can remain visible regardless of Timeline opt-in.
Thus membership, roster access, or a working live-activity request does not prove
Timeline access. Mojang's 1.21.90 notes describe the owner's optional requirement
that members opt into Timeline before playing, while owners can still play without
opting in. It follows that seeing someone online does not prove they have historical
Timeline coverage. These feature settings are not Microsoft OAuth consent scopes.

The reference Stories settings model includes `playerOptIn`, `realmOptIn`,
`timeline`, `autostories`, `coordinates`, `notifications`, `inGameChatMessages` and
`storageShard`. It alone does not specify current enforcement, data deletion on
opt-out, historical backfill after opt-in, or whether a caller can see opted-out
members. Coastal's actual settings were **not queried**. The successful GET proves
read access under the account's existing settings, not which opt-ins are enabled
or whether all Realm members are represented. Nothing was enabled; no attempt is
made to recover data hidden by privacy controls.

Mojang's introductory article confirms owner-controlled Timeline visibility.
Xbox/family/account eligibility may also affect access, but the inspected endpoint
helper does not state its exact claim/age/privacy checks or error responses.
Do not assert owner-only access, universal member access, or that a 403 necessarily
means the OAuth scope is wrong.

**The returned plausible timestamp envelope spans approximately 19.458 days;
the service retention policy remains unknown.** No authoritative numeric retention
period or date-query contract was found for this endpoint.
A seven-day Timeline display is not evidence of seven-day backend retention, and
invite expiry or Story Feed deletion rules are unrelated. No 7/30-day limit is
claimed. This single response establishes only its returned minimum/maximum
plausible timestamp and observed span, not the service's retention policy.
Opt-in dates, inactivity, truncation and filtering can all shorten observed coverage.

## Credential isolation and authorization assessment

Captain's `StoredAccount` and encrypted account serializer persist refresh
credential, identity and revoked state; they do not persist reusable access/XSTS
tokens. `service.py` keeps `_oauth`, `_user`, and audience-specific `_tokens` in
memory. A fresh instance must refresh, persist rotation, and perform Xbox exchanges.
The follow-up authorization permits those POSTs and isolated persistence.

The production store and bot process were not opened for diagnostic use. Before
authentication, the diagnostic rejected links/reparse paths, checked private source/
key ACLs, the single-link source file and size bounds, and verified an encrypted
copy against a stable source read. It did not acquire/create a source writer lock.
The existing DPAPI-protected key was loaded without printing it or persisting a
plaintext key; no encryption key was generated. A generated temporary directory
outside the checkout was restricted through Captain's existing Windows ACL helper
before encrypted account bytes were written. The copied store acquired its own
lock, validated binding/identity, and persisted refresh rotation only there.
Diagnostic configuration was enabled in memory only; saved configuration was unchanged.

Microsoft documents that obtaining new access tokens does not revoke the old
refresh token. This supports isolated reuse without replacing the source credential;
it is not a guarantee against unrelated service revocation or expiration. Auth
failure would have stopped without interactive recovery or copying back to production.
The source encrypted account record was byte-for-byte unchanged after execution.

Captain's production client/transport continue to deny this external route. A
one-off diagnostic reused the existing auth service and encrypted-store class,
with a separate fixed-URL GET implementation. It allowed at most one Microsoft
refresh POST, one Xbox user-token POST and two XSTS POSTs. All four succeeded,
including established expected-account checks. No device-code/login route was allowed.

The single Stories GET used the reference headers plus `Accept: application/json`,
a 30s timeout, 1 MiB response cap, no redirects and no automatic retry/401 refresh.
Raw content was discarded after computing aggregate/type/date summaries. No XUID,
per-player interval, token or raw upstream error was emitted. The isolated copy
was removed after closing service and store; no refreshed credential was copied back.

## Sanitized verification record

| Item | Result |
| --- | --- |
| Authenticated Stories GETs | Exactly 1; no redirect or retry |
| Authentication POSTs | 4, all HTTP 200; established endpoints/implementation |
| Realm/Stories mutation requests | 0 |
| Endpoint HTTP status | **200** |
| Response size | 3,635 bytes |
| Actual response structure | Root object with one field `result`; result object with one field `activity`; activity map values arrays of objects |
| Identifier structure | 27 string keys; all positive decimal; identifiers withheld |
| Activity counts | 95 entry objects; all 95 have integer `s` and integer `e`; no extra entry fields |
| Earliest/latest plausible `s` | **2026-10-15 13:00:00 UTC** through **2026-11-03 23:00:00 UTC** |
| Earliest/latest plausible `e` | **2026-10-15 14:00:00 UTC** through **2026-11-04 00:00:00 UTC** |
| Observed envelope | Approximately **19.458 days** from earliest plausible start to latest plausible end; not continuous coverage or a retention guarantee |
| Timestamp anomaly | One integer `e` outside positive plausible epoch-second range; 94 plausible ends; zero `e < s` entries |
| Account Timeline access/opt-in | Read access Verified; actual setting values and all-member completeness unknown |
| Source preservation | Encrypted source record bytes unchanged; no copy-back or source-store writes |
| Temporary store | Closed and removed after probe |
| Tracked implementation changes | None; this document is the only deliverable |

The plausibility filter accepted positive integer epoch seconds no later than
probe wall-clock time plus five minutes. All 95 starts passed. One end failed;
because none of the integer ends precedes its positive start, that end is beyond
the upper time bound rather than zero/negative. Its meaning is unknown: do not
interpret it as a real future disconnection or assign an unverified sentinel
meaning. It was excluded from date ranges. The min/max boundaries above fall on
hours, but that alone does not establish rounding/granularity of every interval.
The count of 27 identifiers is not a current-online count, membership count, or
independently verified count of opted-in people. November 4 00:00 UTC is November 3
18:00 America/Chicago; this does not imply future data relative to the local research date.

## Value for Phase 4 and future statistics

Historical completed intervals could eventually improve retrospective play-time
summaries, concurrent-player charts and coverage during bot downtime, **for the
visible opted-in population only**. They would not establish all-member statistics
or reconstruct missing opted-out sessions. User review should determine retention
and whether individual history should be displayed outside the game's Timeline.

For the live Status panel, keep the current first-observed **Online for** behavior.
Do not replace it with `now - s`: this endpoint has no verified current-session
flag or guaranteed freshness. A future validation must correlate a currently online
XUID with the correct open interval, determine e/sentinel behavior, compare a
controlled join/leave against UTC observation, and measure reporting delay. Completed
intervals can support historical analysis sooner than trustworthy live-duration correction.
Keep live presence independent; absence from Stories never means offline.

The authorized one-request budget is consumed; no second GET or settings probe
was attempted. Disposable local probe tooling lives only under ignored `.test-tmp`;
it was not integrated into the bot. Any controlled timing comparison, sentinel
investigation, settings read or repeated sampling needs a separately scoped next
step. No account switch, opt-in change or new consent is justified by this result.

## Sources and confidence

Public references retrieved November 3, 2026. The authorized live follow-up
used four authentication POSTs and one Stories GET as recorded above.

- [elytra endpoint and base headers](https://github.com/Astrea-Stellarium-Labs/elytra-ms/blob/ec666db90d719806475e0c161420ae17cd1efe9c/elytra/bedrock_realms/__init__.py),
  [response models](https://github.com/Astrea-Stellarium-Labs/elytra-ms/blob/ec666db90d719806475e0c161420ae17cd1efe9c/elytra/bedrock_realms/models.py),
  [transport/authentication](https://github.com/Astrea-Stellarium-Labs/elytra-ms/blob/ec666db90d719806475e0c161420ae17cd1efe9c/elytra/core.py),
  [constants](https://github.com/Astrea-Stellarium-Labs/elytra-ms/blob/ec666db90d719806475e0c161420ae17cd1efe9c/elytra/const.py).
  Main still resolves to this October 2024 revision. High confidence in what this
  implementation sends/parses; no guarantee of current service behavior.
- [Mojang: Discover Realms Stories](https://www.minecraft.net/en-us/article/discover-realms-stories):
  primary explanation of Timeline activity and owner visibility; no HTTP schema,
  precision or retention guarantee.
- [Mojang 1.21.50 changelog](https://www.minecraft.net/en-us/article/minecraft-1-21-50-bedrock-changelog):
  Timeline-specific opt-in versus Feed/Members visibility.
- [Mojang 1.21.90 changelog](https://www.minecraft.net/en-us/article/minecraft-1-21-90-bedrock-changelog):
  optional required Timeline opt-in for members, owner exception. Feature policy,
  not a complete endpoint authorization contract.
- [gophertunnel Realms source](https://github.com/sandertv/gophertunnel/blob/0e179fc4bb082c13e946c7d81ab1cf9f623d942c/minecraft/realms/realms.go):
  newer independent model of `playerOptIn`, `realmOptIn`, `timeline` and explicit
  opt-in helper. No matching playeractivity implementation found in inspected
  Realms Go files. Its opt-in helper performs a write and was not invoked.
- [Prismarine Realms source](https://github.com/PrismarineJS/prismarine-realms/tree/fad98435fd834e4d2280ab86a636561630a25f19/src):
  no Stories/playeractivity match in inspected JavaScript source; no independent
  precision, pagination or retention confirmation obtained.
- Captain `utils/integrations/realms/{models,token_store,service,transport,client}.py`
  and [Phase 5 inventory](realms-api-capabilities.md): current local constraints
  and persistence behavior, stronger evidence for probe feasibility than third-party
  assumptions about reusable on-disk tokens.

- [Microsoft refresh-token lifecycle](https://learn.microsoft.com/en-us/entra/identity-platform/refresh-tokens):
  token replacement and non-revocation on refresh, checked before using the
  isolated copy. Source and production credentials remained untouched.
