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

Event participant names are resolved with Captain's existing Xbox gamertag cache.
The same positive/negative TTLs, 100-entry bound, batching, cooldown and backoff
apply to both live observations and Story participants. Resolution does not require
players to be online and does not create presence observations. Missing names can
trigger the existing read-only Xbox profile batch lookup (an HTTP POST that reads
Gamertag settings); cache updates use the existing encrypted file store, with no
new tables or configuration. Profile failures/cooldowns do not block Stories.

Names from the cache take precedence over club posting-author names. Posting
identity remains separate from event participant identity: a club author is never
assumed to be an event actor without an exact XUID match. Known events now use
natural sentences, for example a named player joined the Realm, discovered
enchanting or upgraded to Netherite. Grouped joins list up to five names and an
"N other players" count, matching the supplied Minecraft screenshots. Missing
names become "A player" or a player count; raw XUIDs and technical player-reference
fields are never shown. Realm creation uses the supplied in-game welcome wording.

For screenshot media, direct `gameMediaContentLocators` HTTPS URLs are preferred:
Download, then Thumbnail_Large, then Thumbnail_Small. The existing screenshotUri
and screenshotThumbnail image-proxy URLs remain fallbacks. No URLs are downloaded
by The Captain and no extra requests are added. The latest supplied sample renders
six embeds, five enriched events and one direct screenshot reference, without the
generic club event placeholder text. Discord image rendering remains a live check.

Duplicate IDs remain unchanged, so already-posted items are skipped within the
same bot session; restarting the bot permits reposting the updated embeds.

## Default event artwork investigation

Mojang's `bedrock-samples` main tree was searched recursively, avoiding GitHub's
1,000-item directory listing limit. Realms UI icons and promotional art are present,
including `resource_pack/textures/ui/realmsStoriesIcon.png` and
`resource_pack/textures/ui/realms_header_art.png`, but no clearly identified matching
NewMember, FirstEnchantment, FirstCraftedNetherite or RealmCreated card illustrations
were found. Icons, block textures and unrelated art have not been substituted for
those illustrations. This is a search finding, not proof the assets are absent or
that a particular client bundle contains them. No sample-repository images were
added to the embeds. Player screenshot rendering continues to use the verified
club media URLs.

Repository inspected: https://github.com/Mojang/bedrock-samples/tree/main/resource_pack/textures

## Bundled event artwork

`images/realms-stories/` contains 31 PNG assets sourced
from the installed Minecraft for Windows `Content/data/gui/dist/hbui/assets` folder.
Hashed source filenames were renamed to their event names. The additional names
are assumed event mappings, pending confirmation in live feed responses; no new
API event semantics or participant wording is inferred from those filenames.

The 29 small 64×36 originals are enlarged to 640×360 with nearest-neighbor
scaling so Discord displays readable pixel art without smoothing. The two
1024×576 boss illustrations remain at their original resolution. Git history
retains the original small files.

Matched events without screenshot media use their local PNG as a Discord attachment.
Existing screenshot URLs retain priority. Unknown event names or missing asset files
retain text-only rendering. An explicit allowlist prevents upstream names from
selecting arbitrary local files. The bot needs Attach Files in the destination
channel; missing permission stops publication before any entries are sent.
Attachments are closed after each send, including failures. The assets deploy with
the repository and do not require Minecraft to be installed on the bot host.

Restart after deployment before repeating `/realm storiespost`, because its existing
session duplicate guard still skips previously sent entries. No command sync needed.

## Verified event text

All 30 event types from the installed English language file now have text handling;
see `minecraft-stories-text-reference.md` for the source templates. Grouped variants
apply only where defined by Minecraft, including impersonal boss rematches and
plural diamond-set wording. Other player events use the first participant, matching
the installed UI formatter. Existing grouped name limits and safe escaping remain.

Mob-name and world-name payload fields have not been verified. NamedMob therefore
uses the first participant with "has a new friend", NamedMobDies uses "A named mob
met an untimely death", and SlotSwitch uses "The Realm world changed". These do not
substitute a player name for a mob or world, or expose arbitrary metadata. EasyAndSafe
retains the generic fallback because no event text was found for that asset.

## OLD Coastal S10

`/realm oldstoriespost` posts one Stories page from the accessible Realm currently
named `OLD Coastal S10` into the invoking channel. It requires the same Coastal
OP Team role and channel permissions as `/realm storiespost` and uses the same
artwork, participant lookup, 10-item bound and per-session duplicate protection.
Duplicate scopes are separate for current and archived Stories.

The command lists accessible Realms and requires exactly one case-insensitive,
trimmed name match. A missing or ambiguous name stops the command; it never falls
back to the active Realm. A temporary client and transport allow only the resolved
Realm ID and reuse existing authentication. The configured target, presence,
metrics, history and background polling remain unchanged. This pulls all pages exposed by the service,
not deleted or expired Stories. The new slash command requires command sync after
deployment using the bot's existing sync procedure.

## Chronological backfill

Both Stories posting commands now send oldest first, sorting available event and
screenshot timestamps together. Undated entries reverse the upstream feed order.
The current-Realm command keeps its existing one-page/10-item scope.

The old-Realm command follows Xbox `contToken` pagination until there is no next
token, then renders all retrieved entries. It has no post-count limit, renderer
1,000-item cutoff, or 120-second archive-fetch timeout. Per-request timeouts and
response-size protections still apply. Cursor URLs are built on the exact same
club endpoint using encoded opaque tokens; arbitrary returned URLs are never
followed. Repeated cursors and failed pages stop fetching before publication.
Only Stories still available from the service can be recovered; live pagination
behavior has not been verified by these offline tests.

Discord's client handles send rate limits. Duplicate protection remains in memory
for the current bot session, with separate old/current scopes; successful sends
survive a later send failure in that session. Restarting loses that protection.
Persistent delivery checkpoints should be added before enabling recurring automatic
posting. No automation is enabled by this change. Long backfills can outlast the
Discord interaction token, although channel sends use the bot's authentication.

## Archive date window and lookup diagnostics

Old-Realm posts are limited to October 31, 2026 at midnight America/Chicago
(inclusive) through the command's current time. Items with no usable timestamp,
older items, and future-dated items are skipped. Event timestamps take priority
over club-post dates. The current-Realm command is unchanged by this date filter.
All exposed archive pages are still read so page ordering cannot hide eligible posts.

Archive name resolution ignores Minecraft formatting codes and parses only the
matched Realm's ID/name, avoiding unrelated uninitialized slots. Missing/ambiguous
names, malformed club responses, and cursor failures now return fixed diagnostic
codes without private IDs, names, tokens, URLs or response content. These lookup
edge cases and date boundaries are covered offline; the actual production failure
has not been reproduced locally.

## Exhausted Xbox cursors

The Xbox activity-feed fixture in XboxReplay/xboxlive-api's
`__tests__/e2e.test.js` returns `contToken: "0"` on an empty feed. Zero is now
handled as an exhausted cursor (also accepting numeric zero), alongside absent
or empty cursors. Collected pages are retained and no zero-cursor request is made.
Nonzero repeated cursors still fail rather than reporting an incomplete archive
as complete. This fix is based on the public client fixture; the actual cursor
from the production failure has not been inspected.

## Heart/comment counters and message updates

All rendered Stories carry a `heart N / comments N` footer using the observed
`numLikes` and `numComments` fields. Omitted counters mean zero in the supplied
before/after captures; malformed, negative and boolean values are ignored.
`hasLiked` is not used to calculate the total. Comments themselves are not fetched.

MinecraftContent UUID locators provide the canonical event identity, separate from
Xbox feedItemId. Duplicate references collapse to one Story; counter maxima across
the duplicate entries avoid adding the same event's counters twice. Screenshot IDs
remain separate. Exact Realm-event IDs also enrich aliases whose Xbox post ID differs.
No grouping by nearby time, text or author is used, and missing participant data is
not replaced with the posting author's identity. Historical events without metadata
can still retain generic upstream wording.

After successful publication, encrypted auxiliary storage records the canonical
Story key, destination, message ID and last footer. Re-running either posting command
edits only changed footers on known bot-authored messages and retains existing embed
artwork. Records survive restarts, and removed hearts/comments can decrease counts.
No polling or scheduled automation is enabled. Deleted/unreadable original messages
stop the operation rather than silently reposting. Checkpoints use the existing
auxiliary store size protection; a failed save stops the operation. A process crash
between Discord send and checkpoint save can still leave an untracked message.

Older Discord posts created before this mapping existed cannot be identified safely
and are not adopted by guessing their text. The first rebuilt backfill should use a
fresh destination or an operator-managed cleanup of the previous backfill.

Microsoft documents `minecraft://openRealmsStories?realmId=...` for opening a Realm's
Stories feed, not an individual Story. The completion message includes a copyable
feed URI. No unsupported custom-scheme Discord URL button or fabricated per-Story
link is emitted. Launching it still depends on the user's installed Minecraft client.
Source: https://learn.microsoft.com/en-us/minecraft/creator/reference/content/deep-links

## Screenshot-verified OLD Coastal S10 reconstruction

`config/old-coastal-s10-stories.json` contains the operator-supplied historical
participant lists and pet names for the 26 event cards shown in the screenshots.
It is bound to the captured old Realm ID and exact MinecraftContent event UUIDs,
and applied only by oldstoriespost. It restores the 28-card backfill (26 events,
two original screenshot posts). The initial October 31 join cards are reconstructed
as the verified five-player and nine-player groups; all nine names are displayed.
The two simultaneous join cards have identical captured counters, so the screenshots
do not independently establish which Xbox reference belongs to which join group.
These are historical corrections, not a general-purpose inference rule.

The live API still supplies counters, screenshot media, and available timestamps.
Source data is not mutated. Live Stories commands never use this historical file.
Later command runs refresh saved embeds when rendered content changes, including
text changes without counter changes. Existing artwork is retained, and missing
artwork is attached when restoring generic event posts. Pet names use the observed
`metadata.metatext` field with normal escaping and length limits.

This reconstruction does not guarantee future live responses will always include
complete metadata; missing-data handling remains necessary for live posts too.
