# Unified Season 10 timeline and leaderboard history

The old and current Coastal Season 10 Realm IDs represent one continuing world.
Both daily timelines (including today) and the all-time leaderboard now use
`activity_history.season_realms` and `read_activity` for the same stored data.
The old Realm ID comes from the existing reviewed archive mapping; the current
ID comes from the existing runtime configuration. No new settings are introduced.

For each Realm separately, valid observed Stories intervals are combined with
stored live-presence samples. Complete presence windows override Stories within
that Realm, while Stories fill polling gaps. Presence from the new server never
removes activity on the old server. The resulting intervals are unioned per XUID
across both sources, so overlaps and duplicate observations count only once.
Leaderboard totals stop at the current time. Quarantined, invalid and unrelated
Realm data remain excluded. A player's identity is joined by XUID, never a name.
The leaderboard's last-update timestamp includes both Stories and presence data.

Daily reports apply their existing America/Chicago day boundaries; the leaderboard
covers all stored history. Per-day display rounding and different update times
can cause small differences when manually adding displayed daily totals. Missing
observations still mean incomplete coverage, not inactivity. This change does not
reclassify stored sessions or prove the exact discrepancy for any individual.

Deploy the code and restart The Captain. The permanent leaderboard will update
through its existing refresh flow; `/realm leaderboard` reads the combined totals
when opened. No command sync, database migration, history reimport, configuration
change, additional polling or data mutation is required.

Validation includes a SQLite regression proving that combined daily and all-time
totals match for synthetic old/new server overlaps, current-Realm empty presence,
old-Realm presence-only activity, quarantined rows and unrelated Realm rows.
The timeline and leaderboard suites pass. A broader stored-history test,
`test_quarantine_never_silently_promoted_and_utc_normalized`, also fails on unchanged
main (f666493); its quarantine-promotion expectation is outside this change.

## Playtime credit policy

Timeline API coverage without supporting live-presence observations now earns
50% credit: one recorded hour earns 30 minutes. Live-presence coverage earns 100%.
For mixed coverage, only the API-only portion is discounted. For example, an hour
covered by the API with 20 minutes also observed live earns 20 + 40/2 = 40 minutes.
The rule applies retrospectively when reading stored history, without altering
raw timestamps, observations or database records.

Source provenance is retained by `ActivityRows`. Coverage and live intervals are
unioned across both Season 10 Realm IDs before calculating credit. Duplicate or
overlapping API intervals never multiply credit, and live coverage on either
server keeps full credit even when overlapping the other server's API history.
Presence overrides on each source still exclude periods known to be offline.

Daily reports, per-player timeline totals, timeline ordering and leaderboard
rankings use the same policy. Timeline bars retain the original coverage positions;
they are not shortened to pretend the API identified a particular half-hour.
Labels explain that live data gets 100% and timeline-only data 50%. Daily clipping
uses the existing local-day/DST boundaries; leaderboard credit stops at now.
Small display-rounding differences can remain when adding formatted daily totals.

No migration, historical reimport, new setting or command sync is needed. Restart
with the new code to recalculate leaderboard views through the existing refresh
flow. Previously published/finalized daily images need a fresh report/preview to
show the new credited totals. The policy is a credit convention, not a claim that
API-only sessions lasted exactly half of their returned span.

## Deleted daily-report message recovery

A `NotFound` during Discord delivery can mean that a saved report message or its
channel no longer exists. Daily publishing now distinguishes a confirmed Unknown
Message (Discord code 10008) from other failures. Scheduled updates preserve the
saved checkpoint and do not automatically repost deleted messages. An explicit
staff publish, such as `/realm daily history day:2026-10-31 publish:true`, can
replace that confirmed deleted message in the configured report channel.

Replacement uses the normal lease and pending-send checkpoint. If Discord accepts
a replacement but the response is lost, the settling period/history scan recovers
it rather than creating another post. Missing channels, permission failures,
unknown 404 codes and message-identity mismatches never authorize replacement.
Errors now explain the relevant channel or checkpoint problem instead of only
reporting the Discord delivery stage.

`/realm daily history day:2026-10-31` without publish remains a private preview
and does not read, edit or replace a saved Discord message. No activity records
are changed by delivery recovery. Deploy and restart; no migration or command
sync is required because existing command arguments are unchanged.
