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
