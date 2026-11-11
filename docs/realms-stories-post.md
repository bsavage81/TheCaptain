# One-shot Stories posting

`/realm storiespost` posts existing Realm Stories as normal, channel-visible embeds
in the channel where an authorized Coastal OP Team member invokes it. It is
registered only in the configured Coastal Craft guild and uses the same runtime
guild/role checks as other Realm commands. The progress/result message is
private; **the Story embeds are visible to everyone who can view that channel**.
Invoke it only in the intended destination. Bot administrators do not bypass the
OP Team check.

Deploy the changed code, restart The Captain, and sync only Coastal guild commands
with the existing operator sync procedure. No database migration, setting change,
or new dependency is needed. The existing Realms credentials and selected Realm
are reused. Then invoke `/realm storiespost` in the destination channel. The bot
needs View Channel, Send Messages (Send Messages in Threads for a thread), and
Embed Links. Automatic activity panels and player activity functionality remain
unchanged.

Each invocation reads the feed once, without feed retries, redirects, pagination,
polling or media API calls. It considers the first 10 records in API order and
sends one embed per recognizable record. It renders supported text fields,
ISO timestamps, explicitly supplied author display names, and the first supported
direct Minecraft/Xbox/Azure-hosted HTTPS image URL. Mentions are disabled, formatting
escaped, and embed lengths bounded. It does not resolve XUIDs, publish identifiers,
dump raw metadata, interpret unknown automatic event payloads, or expose raw errors.
Posts containing only unsupported fields or media IDs are skipped and counted.
The debug result verified IDs/timestamps and record counts, but did not establish
the remaining live field names: **live rendering and screenshot coverage are not
yet verified**. Missing fields may require a targeted mapping update. No private
feed data is available in the development workspace to test this mapping.

Posting is serialized. Successfully sent record IDs are remembered only in bot
memory, per destination channel, so repeating the command during the same bot
session skips those records. Restarting/reloading clears this guard and permits
reposting. A failure partway through reports the successful count and preserves
the sent-record guard; there is no automatic retry of Discord sends. An ambiguous
network timeout after Discord accepts a message can still produce a duplicate on
a manual retry. Memory is capped at 1,000 sent records and posting then stops until
restart. Nothing is stored in the database.

The command does not fetch images itself: Discord loads the image URL supplied in
the embed. Media represented only by an ID, a separate authenticated endpoint,
or an unsupported host remains unavailable. Automatic events render only if they
already contain a supported text/image field; their metadata is never dumped as
fallback text. The ephemeral `/realm storiesdebug` command remains available and
continues to show only a redacted structural summary.
