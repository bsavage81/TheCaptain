# Temporary Stories and Xbox post investigation

`/realm storiesdebug` returns an ephemeral `realm-stories-investigation.json`
attachment to the invoking Coastal Craft OP Team member. Successful response
bodies are **complete and unredacted**, including player identifiers, text, media
references and signed URLs returned by the services. Request authorization headers,
token-store contents and authentication-service state are excluded. Responses are
not logged or saved to local files. The command remains installed until removed.

Deploy and restart The Captain using the existing configuration and credentials.
Run `/realm storiesdebug` as an OP Team member in Coastal Craft. There are no new
settings, dependencies or database migrations. The command name/signature has not
changed, so existing registration works without another sync; a Coastal-only sync
refreshes its description. Publishing this code does not restart the production bot.

## Content requests per invocation

1. GET the selected Realm's frontend `/api/v1.0/worlds/{realmId}/stories` feed,
   using the existing RealmsClient and Realms XSTS audience.
2. Select the first valid `clubsPostId` reference returned by that feed and GET
   `https://userposts.xboxlive.com/users/xuid({author})/posts/{uuid}/timelines/Club/{clubId}`.
3. GET one page of
   `https://avty.xboxlive.com/clubs/clubId({clubId})/activity/feed?numItems=10`
   using the club ID from that same reference.

The Xbox requests use the existing `authorization_for(..., audience=XBOX_RP)`
callback (`http://xboxlive.com`), Accept JSON and Accept-Language en-US. The club
feed sets `x-xbl-contract-version: 13`; the direct-post request omits that header,
matching the public Minecraft investigation example. This is a diagnostic choice,
not proof of a current Microsoft API contract. It does not try other versions if
a request fails.

The client validates the exact reference shape, hostname, UUID, positive decimal
identifiers and numeric bounds. Query strings, alternate hosts, extra paths,
user-supplied URLs and references not supplied by the selected Realm are rejected.
Independently, the transport grants exactly those two GET URLs only after a
successful Realm feed response contains a valid reference, and clears the grant
on the next feed request. It never grants mutations or general access to Xbox hosts.

The attachment contains `realm_feed`, `xbox_post` and `club_feed` entries with HTTP
statuses and successful JSON bodies. Missing references/auth failures instead
produce an `xbox_probes` state. If one Xbox request fails, the other is still tried
once. Non-200 error bodies are withheld; malformed JSON and transport failures
produce fixed categories and a status when available. There are no retries,
redirects, pagination, image downloads, version probing or public embed sends.
The club-feed item count is requested as 10; the entire actual response is
included even if the server returns a different count.

Normal authentication may perform the existing Microsoft/Xbox refresh exchanges
and encrypted-store rotation before these GETs. An Xbox auth failure preserves the
Realm response and skips both Xbox probes. Initial Realm auth/feed failure returns
the existing private error message. Maximum upstream body size remains 1 MiB per
request. JSON attachments are generated in memory, with compact serialization as
a fallback for large formatting output. The runtime serializes probes with other
Realm operations and tracks cancellation/shutdown; its overall diagnostic timeout
is 150 seconds. No history persistence or polling is introduced.

Guild/OP Team authorization is checked before I/O, before each Xbox request, and
before delivery (the runtime service principal's account authorization and the
invoking staff member's guild/role checks remain separate). If the invoker loses
access before delivery, no attachment is sent. `/realm storiespost` and
`/stories/playeractivity` are unchanged. Earlier single-feed/schema helper methods
remain available in source, but the command now invokes the combined investigation.

## Evidence and remaining validation

The direct-reference GET and `postContentLocators`/`MinecraftContent` clues come
from [minecraft-realms-playground](https://github.com/caburum/minecraft-realms-playground/blob/db371c87907fec611d06bb55f979f4f355792257/experimenting.ipynb).
The club-feed route and contract version come from
[RealmHelper](https://github.com/MrSterdy/RealmHelper/blob/a21ea091cefdc178d8c8b747157a01220d9ee5dc/src/RealmHelper.Infrastructure/Api/XboxLiveApi.cs).
Development tests use synthetic data. Live Xbox access, current schemas and
screenshot availability remain unverified until this command runs on the server.

## Inspect old-Realm heart changes

`/realm storiesdebug old_realm:true` privately attaches the combined club feed
(all available pages) and Realm-event references for OLD Coastal S10, using the
existing archive fetch path. It does not post Stories or add Discord reactions.
The current-Realm diagnostic remains the default. Sync commands after deploying
the new optional argument.

Capture one attachment immediately before adding a heart to one known Story in
Minecraft, then another immediately afterward. Compare post IDs, activity types,
like/count fields and target references. Exact API fields must be established from
these captures; synthetic test field names are not evidence of the live schema.
The attachment contains private content, but no request headers or auth tokens.

Generic system notices in the pasted backfill are not proof of heart activity:
the renderer also emits club-system text when its exact feedItemId has no matching
Realm clubsPostId. Inspect IDs and reference shapes before suppressing such items.
Future reaction synchronization needs an original Story-to-Discord-message mapping.
A bot can add one heart of its own per message, not impersonate Minecraft players
or create multiple identical bot reactions to reproduce a like count.
