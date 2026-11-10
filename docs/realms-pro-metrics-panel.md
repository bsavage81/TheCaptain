# Live Realms Pro metrics panel

The OP Team can post a separate persistent embed alongside the existing player
list by running `/realm metrics create` in that channel. `/realm metrics refresh`
respects the shared 15-second metrics cooldown. `/realm metrics remove` removes
the metrics message and stops its polling. Creation in another channel relocates
the single metrics panel; the player panel is independent.

The embed shows server status, CPU percentage, memory percentage, tick time in
milliseconds, player count, and the last successful read time. Missing or failed
readings display Unavailable, never a fabricated zero. Offline servers do not
display cached values as live. There are no names, XUIDs, or player histories.

Polling starts only after staff create the message. Its IDs/interval persist in
the optional `realm_metrics_panel` settings block in the existing botdata JSON.
No schema migration or new credentials are required. Deleted messages stop
updates until recreated; permission and upstream failures back off. The existing
player observations and duration cache are not used or modified by this panel.

## Access verification, November 9, 2026

One fixed-query live telemetry GET against the selected Coastal Craft Realm
returned HTTP 200 using TheCaptain4322 and the existing Realms XSTS audience.
All four metric values were numeric and `realmOnline` was boolean. The identity
was verified by the established authentication implementation. There were four
successful authentication POSTs, one GET, no GET retries, and no interactive login.
Refresh persistence was confined to an independently locked, protected encrypted
copy of the local diagnostic credentials. The encrypted source bytes were
unchanged and the temporary copy was removed. Production was not modified.

## Release

Deploy the reviewed metrics branch using the existing main deployment workflow,
then synchronize Coastal guild commands using the existing owner workflow. Staff
can run `/realm metrics create` beside the player list. Verify the four values,
last-read timestamp advances, and existing player panel continues updating.
The bot needs View Channel, Send Messages, Embed Links, and Read Message History
in the target channel. No panel is posted or metrics polling enabled merely by
deploying. Deployment/restart and command synchronization have not been performed
as part of implementation.

Rollback by removing the metrics panel before reverting code. An older revision
does not accept the new optional settings key, so remove `realm_metrics_panel`
using `/realm metrics remove` before deploying an older revision. Never overwrite
the full settings document or restore database backups for this feature rollback.
