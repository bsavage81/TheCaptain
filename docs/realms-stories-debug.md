# Temporary Stories feed diagnostic

Deploy these changes with the existing Python dependencies, Realms configuration,
and encrypted credential store. Restart The Captain, then use the existing
operator command-sync procedure for the Coastal Craft guild (see
`realms-discord-deployment.md`). No migration, new settings, history enablement,
or additional credentials are required. Do not start a second bot against the
production token store.

An OP Team member in Coastal Craft can invoke `/realm storiesdebug` once. The
command defers and replies ephemerally; guild/role authorization is checked before
I/O and again before delivery. Administrators and authentication owners do not
bypass the OP Team requirement. Discord command visibility settings can further
hide the command, but runtime checks enforce access regardless of visibility.

The request uses the existing RealmsClient authorization callback, transport,
selected Realm ID and headers. The frontend base includes `/api/v1.0`: the full
route is `https://frontend.realms.minecraft-services.net/api/v1.0/worlds/{realmId}/stories`.
There is exactly one feed GET per successful invocation, including on HTTP 401,
429 or 5xx: no feed retry, redirect, image fetch, pagination, or 401 replay.
Pre-request authentication may use the normal Microsoft/Xbox token refresh
lifecycle and encrypted-store rotation. If authentication fails, no feed GET is
made. Existing activity and `/stories/playeractivity` behavior is unchanged.

The response reports HTTP status, root type/count, recognized top-level fields,
field/type occurrence counts, array item totals, JSON types, and heuristic
presence indicators for posts, screenshots and automatic events. Raw scalar
values never appear; arbitrary field names are replaced with `<redacted-key>`
because map keys may contain identities or private text. Recognized type values
are mapped only to fixed content categories; unknown values are never echoed.
A missing indicator means unverified, not absent. Empty feeds cannot establish
which content types the endpoint supports. Array totals aggregate by field name,
not unique posts. Scanning and output are bounded and omissions are indicated.
No response bodies, image URLs, or raw exceptions are logged or persisted.
Non-JSON successful responses report status 200 but cannot be inspected. Transport
failures or size-limit rejection may leave HTTP status unavailable.

The command does not save history, create tables, start polling, fetch media, or
forward feed content. Only the redacted diagnostic summary is returned to the
invoking staff member. Remove the command and its feed-specific client/transport
allowlist entries after the investigation, restart, and sync the guild commands
again. Do not remove the existing playeractivity route.

Offline verification uses synthetic responses only. This workspace has no live
Realm credentials, so no live feed result is claimed. Run the command after
deployment to obtain that result.

The separate opt-in `/realm storiespost` command can now publish supported feed
content on staff invocation; see [Stories posting](realms-stories-post.md). The
debug command itself remains private and never forwards content.

## Expanded schema report

The diagnostic now also includes a detailed, bounded schema tree. Feed record
field names that look like ordinary schema identifiers are visible even when not
in the original field allowlist. Numeric IDs, UUID-like keys, URL/text-shaped keys,
and arbitrary keys inside unknown maps remain redacted. Known schema containers
(such as result, author, content, metadata and images) are expanded. This reveals
field names for mapping without printing any scalar values. Field names are
structural clues, not proof of a field's meaning.

Each path shows its type and container count or string length. Strings receive
per-report opaque equality labels, making repeated IDs/references recognizable
without exposing the values or reusable hashes. Fixed shape indicators identify
decimal/UUID-like identifiers, ISO-like timestamps, URL-like values, common media
extensions, path-segment counts and whether a URL query is present. URLs, hostnames,
path components, query names/values, actual IDs, timestamps, names and post text
are withheld. JSON encoded inside strings is decoded only to inspect its structure;
its scalar values remain withheld. Unknown event discriminator values are still
not printed.

The detailed scan expands up to 20 items per array, 80 fields per object, 12 levels,
1,500 nodes and approximately 48,000 characters; truncation is explicitly reported.
Long reports are sent as an ephemeral `realm-stories-schema.txt` attachment built
in memory from the sanitized text. No raw response file is created and no extra
API or image requests are made. The short aggregate summary remains in the report.
After updating/restarting the bot, run `/realm storiesdebug` again. Its command
signature has not changed, so an additional command sync is unnecessary if it is
already registered.
