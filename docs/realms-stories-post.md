# One-shot Stories posting from the Xbox club feed

`/realm storiespost` posts current Realm club-feed items as channel-visible embeds
in the invoking channel. The command remains restricted to the configured Coastal
Craft guild and OP Team role; bot administrators do not bypass those checks.
Progress/results are ephemeral, while the embeds are visible to everyone who can
view the destination channel.

Deploy this code, restart The Captain, and invoke the existing command in the
intended channel. No migration, setting changes, new dependencies or additional
command sync are required if `/realm storiespost` is already registered. The bot
needs View Channel, Send Messages (Send Messages in Threads for threads), and
Embed Links. Publishing to GitHub does not update or restart the production bot.

## Requests and rendering

Each invocation performs two content GETs: the configured Realm's Stories feed,
then one Xbox club activity feed page requesting 10 items. The club ID comes from
a strictly validated `clubsPostId` returned by that Realm. The existing transport
independently permits only the exact derived GET URL. The club request reuses the
Xbox Live token audience, `x-xbl-contract-version: 13` and English language headers.
It does not fetch the individual Xbox post used by the separate debug command.
If the Realm feed contains no valid club reference, posting stops; there is no
fallback to an arbitrary club, stale reference, or user-supplied destination URL.

The verified club response is `activityItems`, with this mapping:

| Embed | Source |
| --- | --- |
| Body | First non-empty `ugcCaption`, `itemText`, `description`, `shortDescription` |
| Timestamp | `date` |
| Author | `authorInfo.modernGamertag` (fallback `name`), optional numeric suffix |
| Author icon | Supported HTTPS `authorInfo.imageUrl` |
| Screenshot | `screenshotUri`, fallback `screenshotThumbnail` |
| Duplicate key | `feedItemId` |

The title is Realm Screenshot for Screenshot activities, Realm Event for System
content, and Realm Story otherwise. Raw identifiers and unknown metadata are not
dumped. User content is bounded and formatting/mentions escaped; Discord sends
disable mentions. A game-cover image or author avatar is never substituted for
a missing screenshot. Legacy HTTP URLs on exactly `images-eds.xboxlive.com` are
upgraded to HTTPS while preserving the path/query. Other insecure image hosts
remain rejected. Discord fetches images from the embed URLs; The Captain makes
no image-download requests. HTTPS image delivery still requires a live Discord
render check; the supplied sample was tested offline only.

Up to the first 10 records of the returned page are considered in API order.
Unsupported records and duplicate feed IDs are skipped and counted. A source
response above 1,000 items is rejected. The supplied investigation sample renders
six embeds: five events and one screenshot, with six authors and timestamps.
No sample content is committed to the repository.

## Failure handling and duplicate guard

Posting is serialized and uses the shared Realm runtime lock for retrieval and
shutdown tracking. The combined read has a 120-second timeout. There is no feed
retry, 401 replay, redirect, pagination, polling or history persistence. Existing
Microsoft/Xbox authentication can refresh and rotate the normal encrypted token
store. Activity/player-history functionality and the debug command are unchanged.

Successfully sent IDs are remembered in memory per destination channel. Repeating
the command during the same bot session skips those records. Restarting/reloading
clears the guard and permits reposting. A partial Discord failure reports the
successful count and preserves the sent-ID guard; no send is automatically retried.
An ambiguous network timeout after Discord accepts a message can still cause a
duplicate on manual retry. Memory is capped at 1,000 sent records; posting then
stops until restart. Nothing is saved to the database.
