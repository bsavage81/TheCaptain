# Phase 4: live Realm panel and observed sessions

Development branch: `codex/realms-phase4`. This document does not authorize release,
production configuration changes, command synchronization or a restart.

## Commands and visibility

The existing status, players and refresh commands remain ephemeral. The new guild-only
group has `/realm panel create`, `/realm panel remove` and `/realm panel refresh`.
Every invocation requires the existing database-configured Coastal guild and
CoastalOPTeam role, independently of administrator or authentication-owner status.
Interactions defer before database/API/message work. Confirmation is ephemeral.

`create` posts in the invoking channel. Everyone able to read that channel can read
the panel, so choose an appropriate channel. Repeating it in the same channel reuses
the existing panel. Relocation deletes the old message before posting another;
inability to access/delete it fails safely rather than making a duplicate. Removal
deletes the message and removes its configuration. A missing message/channel stops
updates until an OP Team member explicitly uses `create`; no automatic recreation.

The bot needs View Channel, Send Messages, Embed Links and Read Message History.
The saved message must belong to The Captain. Mentions are disabled and supplied
names are escaped. The panel never displays XUIDs, Realm IDs or API bodies.

## Persistence and session meaning

The optional `realm_panel` object lives in the existing `botdata.settings_json`
settings section: `guild_id`, `channel_id`, `message_id`, `interval_seconds`.
`create` writes it; no manual seed/database preparation is required. Updates lock
the singleton row and change only this block, without a new table or schema change.
Startup restores its message instead of sending a new one. Configuration writes
occur on create/relocate/remove, not each poll. Default interval is 15 seconds;
operators can configure an integer from 15 through 3600 using the existing reviewed
database settings process, then restart. Do not edit production settings as part
of development verification.

Active sessions are stored separately as `panel-sessions.realms.enc` inside the
existing private token directory. They use the existing Fernet key map, account
binding, private-permission/location checks, atomic replacement and already-held
single-writer lock. The auxiliary record is additionally bound to the selected
Realm in its validated payload. Authentication credentials and `account.realms.enc`
are not replaced by session writes. Back up the encrypted auxiliary record with
the private token directory and retain the key securely. Never commit or log it.
No new environment variables, keys or Microsoft authentication are required.

The approved API model and pilot records establish no reliable join timestamp.
No undocumented timestamp is interpreted as an exact login time. Sessions therefore
begin with the first successful online observation and always display **Tracked for**
(`8m`, `47m`, `2h 34m`). This is sampled monitoring time, not an exact login or a
guarantee of uninterrupted presence during bot downtime or failed observations.
Sampling can miss departures/rejoins between polls, including during a restart.

Sessions use XUIDs, never gamertags as identity keys. A changed gamertag with the
same XUID retains its first observation. Only a successful selected-Realm activity
snapshot with known Boolean presence for every record is authoritative for session
transitions. Omitted selected Realm, failed API request, unknown presence, or invalid
identity never imply an empty Realm. A confirmed absence/explicit offline record
ends a session; a later online observation starts a new session. Only active XUIDs
and observation times are retained; departures are removed, not archived. Writes
occur only on membership transitions. Restart loads existing active timestamps.

Unavailable/unnamed players display `Duration unavailable`; identifiers are never
substituted for names. Unknown presence/counts remain unknown rather than zero.
If encrypted session storage cannot be read/written, the panel continues with
unavailable durations and a sanitized warning; it never overwrites corrupt state
or publishes newly started sessions that failed to persist. An operator must inspect
the private storage problem; do not regenerate authentication credentials.

## Refresh, failures and rate limits

Exactly one `discord.ext.tasks` loop belongs to the Realm cog. Without a configured
panel it makes no API requests. It waits for bot readiness and is cancelled/awaited
before the existing runtime closes. Panel mutations/edits are serialized. The shared
runtime also serializes API calls across commands and polling.

Scheduled observations bypass the old 60-second command cache and require at least
15 seconds between attempts. Status/player requests share the fresh result. The
existing 30-second manual refresh cooldown still applies; a panel refresh near a
scheduled observation may reuse that observation. Session calculations introduce
no API requests: they consume the existing details/activity observation.

Failures retain successful snapshots and session starts; stale/unavailable information
is labelled. Runtime failures back off 15, 30, 60 seconds up to 15 minutes, honoring
longer upstream Retry-After values. Existing transport/client bounded retries remain.
Discord edits use discord.py rate-limit handling plus a separate exponential delay
after failed updates. No redundant edit occurs when the rendered embed is unchanged.
Fresh observation timestamps or displayed duration changes legitimately require edits.
Discord timestamp markup is in an embed field because Discord footers do not render it;
the footer states auto-refresh cadence, stale state and duration estimates.

## Release and activation, after explicit approval

1. Review/push CI for `codex/realms-phase4`. Merge only when approved: the existing
   main workflow restarts Apollo automatically and verifies the running revision.
2. Preserve the existing `.env`, key map, token directory and all ignored private
   files during release. Existing Python 3.14 hosting/dependencies are reused; this
   change adds no packages or credential migration.
3. Synchronize **only Coastal Craft's guild commands**, using the existing authorized
   guild-only sync command with the configured Coastal guild ID. Do not globally sync
   or replace the guild command set with a partial tree.
4. As an OP Team member, run `/realm panel create` in the selected channel. Verify
   the public panel, ephemeral link, observation timestamps and fresh 15-second updates.
   No production database change is needed before this command; it saves its own IDs.
5. Verify same-channel reuse, a denied non-OP invocation, manual refresh, restart
   recovery and a controlled join/leave/rejoin. Check duration continuity after
   restart and safe stale behavior during temporary errors. Remove with
   `/realm panel remove` when testing is complete if a permanent panel is not desired.

## Known limits

The deployed pilot supplied counts but no player names. Unless a later API response
supplies gamertags, this panel cannot show named session durations. No new Xbox profile
lookup or permission scope is introduced. Capacity is not verified, so `/10` is omitted.
The suitability of sustained 15-second live polling is unverified until the approved
release; backoff protects services if rate-limited. These offline changes do not
establish a new live API result. No production changes are performed by tests.

## Offline verification

Focused Python 3.12 run: **92 passed** across `test_realms_panel.py`,
`test_realms_panel_storage.py`, `test_realms_discord.py` and `test_realms_client.py`.
This includes synthetic encrypted persistence/atomic failure checks, DB-block
preservation, permissions, command registration, restart recovery, cache bypass,
session transitions and API backoff. Network is blocked by the offline test fixture.
Ruff F checks and whitespace checks passed. Dependencies remain unchanged for the
existing Apollo Python 3.14 host; no new host-specific setup was introduced.
