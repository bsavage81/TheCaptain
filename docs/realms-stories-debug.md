# Temporary full Stories feed diagnostic

`/realm storiesdebug` now returns the **complete, unredacted JSON response body**
as an ephemeral `realm-stories-feed.json` attachment to the invoking staff member.
This explicitly authorized diagnostic includes any player identifiers, names,
post text, timestamps, media references, signed image URLs, and other fields
returned by the endpoint. It remains enabled until the command is changed or
removed. It does not include request headers, authorization tokens from the
request, the token store, or authentication-service state. Raw upstream errors
remain suppressed, and response bodies are not logged or saved to local files.

Deploy the changes and restart The Captain with the existing Realms credentials
and configured Realm ID. Run `/realm storiesdebug` in Coastal Craft as an OP Team
member. Existing command registration continues to work; a Coastal-guild command
sync is needed only to refresh the updated description. No migration, new
settings, or extra dependencies are required. No server restart or Discord sync
is performed by publishing this code to GitHub.

Guild and OP Team checks run before the request and again before delivery. A role
revocation clears the diagnostic result before any attachment is sent. Bot
administrators and authentication owners do not bypass the role requirement.
Although the test channel is private, the attachment is also ephemeral and is
not posted as a normal channel message.

The existing RealmsClient authorization callback, transport, headers and selected
Realm ID are reused. The full route is
`https://frontend.realms.minecraft-services.net/api/v1.0/worlds/{realmId}/stories`.
There is one feed GET per invocation, with no feed retry, redirect, pagination,
image fetch, or 401 replay. Pre-request authentication can use the normal
Microsoft/Xbox refresh lifecycle and encrypted-store rotation. Authentication
failure prevents the feed GET. Other failures return a fixed, private error
message and HTTP status when available; error bodies are not attached.

Successful JSON is pretty-printed, with compact JSON used if indentation exceeds
7 MiB. The original transport response limit remains 1 MiB. The attachment is
constructed in memory from the parsed JSON, preserving values rather than exact
wire formatting. It is sent for small and large successful responses alike.

This command does not create tables, save history, start polling, fetch media, or
publish normal channel embeds. Player activity and `/stories/playeractivity`
remain unchanged. `/realm storiespost` remains a separate, manually invoked
posting command; see [Stories posting](realms-stories-post.md).

After investigation, remove the diagnostic command and sync Coastal guild
commands to remove its registration. The feed route is also used by
`/realm storiespost`; retain it while that command is installed. The earlier
redacted schema helpers remain available in source but are no longer used by
the debug command.
