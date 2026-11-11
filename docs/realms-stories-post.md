# One-shot Stories posting from Realm events and the Xbox club feed

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
| Timestamp | Matched Realm event `timestamp`, otherwise club `date` |
| Author | `authorInfo.modernGamertag` (fallback `name`), optional numeric suffix |
| Author icon | Supported HTTPS `authorInfo.imageUrl` |
| Screenshot | Direct screenshot locator, then `screenshotUri`/`screenshotThumbnail` |
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

## Combining the two sources

The Realm response is retained alongside the club response as internal
`realmEvents` data. Exact `clubsPostId == feedItemId` matching enriches each event;
there is no timestamp, author, or text-based guess. Known event names get readable
titles/descriptions for NewMember, FirstCraftedNetherite, FirstEnchantment and
RealmCreated. Realm timestamps take precedence for matched events. Unknown event
names get a neutral Realm Event message. Club-only items, including screenshot
posts, retain their captions and authors. Realm events missing from the returned
club page are included once, subject to the existing 10-item total limit.

Player references are displayed separately from the event text. Names are resolved
only when an exact player identifier matches an author identity already present
in the club response; other names are counted as unavailable. No additional profile
requests occur and raw XUIDs are never published. A posting author is not assumed
to be the player who performed an automatic event, so matched event embeds omit
the club posting-author header. A NewMember event listing several player IDs does
not establish that all those players joined; these are labeled player references.

For screenshot media, direct `gameMediaContentLocators` HTTPS URLs are preferred:
Download, then Thumbnail_Large, then Thumbnail_Small. The existing screenshotUri
and screenshotThumbnail image-proxy URLs remain fallbacks. No URLs are downloaded
by The Captain and no extra requests are added. The latest supplied sample renders
six embeds, five enriched events and one direct screenshot reference, without the
generic club event placeholder text. Discord image rendering remains a live check.

Duplicate IDs remain unchanged, so already-posted items are skipped within the
same bot session; restarting the bot permits reposting the updated embeds.
