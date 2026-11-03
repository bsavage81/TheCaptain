# Bedrock Realms response fields and evidence limits

November 3, 2026. Baseline `a3a8925`. Companion:
[capabilities, endpoint inventory and sources](realms-api-capabilities.md).

## What was actually verified

The [pilot](realms-live-pilot-results.md) records HTTP 200 for `/worlds`, selected
`/worlds/{id}`, and `/activities/live/players`. Its successful parsing establishes
required parser fields, but it did not save raw response schemas or enumerate
optional fields. This phase did not make a new authenticated request. Accordingly,
tables below distinguish **parser contract** from **observed presence**. Missing and
null often normalize identically; a type accepted by the parser is not proof that
the service returned every such variant. Unknown upstream fields are discarded.
All example values are synthetic; none is a captured account response.

## Verified endpoint parser contracts

| Endpoint/field | Type accepted | Missing/null behavior | Evidence/reliability |
| --- | --- | --- | --- |
| `/worlds`: root | object | Required | Successful typed pilot result |
| `servers` | array of Realm objects | Required, non-null; may be empty | Pilot recorded one accessible Realm |
| `/worlds/{id}`: root | Realm object | Required | Pilot parsed selected object and matched configured ID |
| Realm `id` | positive integer or decimal string up to 20 digits | Required; normalized to string | Required for successful parse; value private |
| Realm `name` | nonempty string, <=16,384 chars, no control chars | Required | Pilot confirmed a name; no need to repeat it in a schema |
| Realm `state` | string `OPEN` or `CLOSED` | Required; other values rejected | OPEN observed; configured state, not connectivity |
| Realm `players` | array of Member objects | Missing/null becomes unknown (`None`), not empty | Optional presence not recorded by pilot |
| Realm `expired` | Boolean | Missing/null becomes unknown | Optional presence not recorded by pilot; not exact subscription date |
| `/activities/live/players`: root | object | Required | Successful typed pilot result |
| `servers` | array | Required/non-null | All visible Realm snapshots; not just selected Realm |
| `servers[].id` | same ID types as Realm | Required | Normalized and compared to private selected ID |
| `servers[].players` | array of Member objects | Required/non-null, unlike Realm metadata players | Two selected-Realm records in pilot; not a field-by-field presence capture |
| `servers[].full` | Boolean in upstream E model | Captain ignores; own parser does not require it | Documented upstream, not independently account-verified |

Duplicate Realm IDs or duplicate Member identities within a player list cause
ProtocolError. An absent selected Realm is unknown, never an empty online set.

### Member shape, shared by metadata and activity

| Raw field | Type accepted | Missing/null | Reliability and privacy |
| --- | --- | --- | --- |
| `uuid` | nonempty ASCII decimal string | Rejected | Bedrock XUID, despite name; stable private identity, not Java UUID |
| `name` | nonempty validated string | Accepted as unknown | Upstream E models null; resolve separately; do not display identifiers as fallback |
| `accepted` | Boolean | Accepted as unknown | Invitation/membership flag; not an online timestamp |
| `operator` | Boolean | Accepted as unknown | In-game flag; not ownership proof |
| `online` | Boolean | Accepted as unknown | Session transitions require known presence; unknown never means offline |
| `permission` | `VISITOR`, `MEMBER`, `OPERATOR` | Accepted as unknown | Enum validated; not a guarantee caller may administer players |

The general Member parser accepts `"0"` as decimal text. Profile resolution and
session handling apply stronger identity rules: zero is not stable identity; no
lookup/duration is assigned. Profile XUID validation requires canonical decimal
strings in 1..2^64-1. No identifiers are published by this documentation.

### Synthetic shapes (optional fields intentionally omitted)

```json
{"servers":[{"id":"1","name":"Example Realm","state":"OPEN"}]}
```

```json
{"id":"1","name":"Example Realm","state":"OPEN","players":null,"expired":null}
```

```json
{"servers":[{"id":"1","players":[{"uuid":"1","name":null,"online":true}]}]}
```

These illustrate code acceptance only; they do not assert these exact bodies were
observed. No join time, duration, session ID, device or source IP is parsed. Snapshot
`observed_at` is a locally generated UTC datetime after successful retrieval, not
an upstream timestamp. Phase 4 first-observed times are also local estimates.

## Implemented, not independently account-verified

| Endpoint | Fields/types | Optional/null behavior and limits |
| --- | --- | --- |
| GET `/invites/pending` | object with `invites` array; entries `invitationId:string, worldName:string` | Root/array/entry strings required; empty array valid. Other owner/description/date fields ignored |
| GET `/invites/count/pending` | JSON integer >=0 | Boolean, null, negative and string rejected; not all outgoing Coastal invitations |
| POST Profile batch | object `profileUsers:array`; entries `id:string,settings:array` | IDs must be valid requested XUIDs, unique; omitted users allowed |
| `profileUsers[].settings[]` | `id:"Gamertag",value:string` | Empty settings or null/missing value yields unresolved name; >1 setting rejected |
| Gamertag value | nonblank string <=64 chars, no control/DEL | Invalid names rejected, never used as a stable identity |

Synthetic Profile response:

```json
{"profileUsers":[{"id":"1","settings":[{"id":"Gamertag","value":"ExamplePlayer"}]}]}
```

Profile omission is not proof of an invalid account or offline player. Cache positive
24h/negative 15m; max 100 records, minimum 60s between lookups. Names can change.

## Additional documented fields — not a verified account schema

Upstream B/E sources, linked in the capabilities document, model the following:

| Area | Fields and source types | Reliability/optional behavior |
| --- | --- | --- |
| Discovery metadata | `owner:string|null,ownerUUID:string,defaultPermission:enum,daysLeft:int,expired:bool,expiredTrial:bool,gracePeriod:bool,worldType:enum,maxPlayers:int,activeSlot:int` | FullRealm E model; not all required by Captain and not guaranteed on individual details |
| Other Realm metadata | `member:bool` (E default false), `slots:any|null,clubId:int|null,motd:string|null`; B also maps `remoteSubscriptionId,subscriptionRefreshStatus,minigameName,minigameId,minigameImage` | B mapping alone does not establish types or field presence; E models several minigame/subscription values as null |
| Individual details | `isHardcore:bool` (E default false), `storiesSettings:object|null` | Different E model from discovery; do not assume the two endpoints have identical schemas |
| Backup | `backupId`, `lastModifiedDate`, `size`, `metadata` | B maps values without primitive validation; timestamp encoding/size units not independently established here |
| Backup metadata | `game_difficulty,name,game_server_version,enabled_packs,description,game_mode,world_type` | B JSON-parses enabled_packs; schema may vary. Historical backup attributes, not current-world proof |
| Subscription summary | `startDate,daysLeft,subscriptionType` | B maps without validating types; unknown optional fields/account access |
| Subscription detail | `type,store,startDate,endDate,renewalPeriod,daysLeft,subscriptionId` | Same caution; billing identifiers private |
| Incoming invite extras | `worldDescription,worldOwnerName,worldOwnerUuid,date` | E uses date integer as epoch seconds; not a player login time |
| Link | `linkId,profileUuid,type,ts,url,deepLinkUrl` | Join secrets; no public examples or account request |
| Stories settings | `autostories,coordinates,inGameChatMessages,notifications,timeline:bool`, `playerOptIn,realmOptIn:string`, `storageShard:int` | E model, optionality/account behavior unverified |
| Stories history | `result.activity:object`, identifier keys → arrays of `{s:int,e:int}` | E converts both to epoch seconds. Missing/end/open-session conventions and retention unknown |
| Membership counts | `memberCount:int,memberLimit:int,overLimit:bool` | Account Realm count/limit, not player capacity |
| World archive | `downloadLink` or `downloadUrl`, `token`, `size` | B uses bearer token for world bytes. Secret output, no fetch/download authorized |

No raw payload field census was available from the pilot; these must not be relabeled
Verified merely because the enclosing endpoint once returned 200. Follow the proposed
metadata-only field/type probe in the capabilities document before exposing them.

## Authentication responses (successful chain; secrets excluded)

Device challenge parser requires string `device_code,user_code,verification_uri`,
positive bounded `expires_in` and interval (defaults to 5 when omitted). Token parser
requires Bearer `token_type`, sign-in `scope`, `access_token`, `refresh_token` (may
reuse previous refresh if omitted during renewal), and bounded `expires_in`.
Xbox parser requires `Token,NotAfter,DisplayClaims.xui` with exactly one claim and
`uhs`; `xid,gtg` supply expected-identity checks where present. Token expiration and
audience are validated. These fields describe code and pilot chain success, not
permission to export responses. Codes/tokens/user hashes/XUIDs are always secret.

HTTP status and Retry-After are transport metadata, not Realm schema fields.
Malformed JSON, redirects, >1 MiB responses and invalid typed structures fail closed;
exceptions do not synthesize empty successful observations.
