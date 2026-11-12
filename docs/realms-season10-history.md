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
