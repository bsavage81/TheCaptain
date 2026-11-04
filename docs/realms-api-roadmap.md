# Research roadmap after Phase 5 review

November 3, 2026. Research candidates only; no commands, polling changes, database
changes, administration or Phase 6 implementation authorized. Evidence and access
classifications: [capabilities](realms-api-capabilities.md),
[response fields](realms-api-response-fields.md).

## Priority 1: useful read-only information

| Rank | Candidate and value | Feasibility/permissions | Risks and dependencies |
| --- | --- | --- | --- |
| 1 | Monitoring health and freshness alerts: distinguish API outages, stale player data and configuration CLOSED | High; existing observations and errors, same member account | Aggregate/deduplicate alerts; avoid notification storms; define outage thresholds; expose no raw errors |
| 2 | Verified capacity, active slot, expiration summary in existing information views | Medium; discovery/details source fields; owner subscription read may be required for exact dates | First verify actual field presence/semantics; no hardcoded 10-player limit, no billing identifiers; avoid false renewal alarms |
| 3 | Realm member directory with accepted/permission flags | Medium; roster visibility unknown for bot account; existing detail parser is partial | Roster is distinct from activity; validate null/missing handling and account access; restrict to OP Team, cache names, avoid public XUIDs |
| 4 | Backup status and age monitoring | Medium; likely owner-authorized metadata GET; additional allowlist approval | Metadata only; define expected backup behavior before missing-backup alarms; do not fetch archive tokens/world bytes |

The existing fixed Gamertag lookup is already implemented, not a new feature to
build again. Obtain permitted live evidence for that route in a later authorized
verification scope; retain counts and unknown-name behavior when denied.

## Priority 2: activity and monitoring improvements

| Rank | Candidate and value | Feasibility/permissions | Risks and dependencies |
| --- | --- | --- | --- |
| 5 | Separate metadata/activity/Discord cadence to reduce requests while keeping useful display updates | High engineering feasibility; existing account | 15s sustainability unproven; review 60s activity precedent and slower details; preserve serialized access, Retry-After and stale semantics |
| 6 | Session history plus daily/weekly summaries and activity statistics | High for locally observed estimates; same member activity access | New encrypted retention/storage design required; disclose sampled coverage and outages, define timezone/DST and retention, do not count gaps as continuous play |
| 7 | Join/leave notifications | High for sampled transitions; same member activity access | Baseline suppression, restart/gap handling, configurable consent/channel/rate limits; short visits may be missed; cannot call transitions exact login times |
| 8 | Realms Stories history research to supplement local monitoring | Uncertain; documented separate host/history schema, account eligibility and opt-ins unknown | New host/audience/allowlist approval; privacy-sensitive historical records; prove time units, incomplete/open intervals, retention, accuracy and opt-out behavior first |

Do not use Xbox presence as a substitute for connection to Coastal Craft. Platform
enrichment has lower value than reliable names/history, adds privacy exposure and
cannot prove which device is connected to this Realm. Defer People Hub until a
specific justified use and minimal-data response policy exist.

## Priority 3: administration after explicit future authorization

| Rank | Candidate and value | Feasibility/permissions | Risks and dependencies |
| --- | --- | --- | --- |
| 9 | Incoming invitation review and deliberate accept/reject | Read list/count implemented; self-account mutations documented | Bot's incoming invites are not Coastal outgoing invites. Never auto-accept; explicit membership-change authorization and audit trail required |
| 10 | Realm member invite/remove and permission commands | Documented routes; owner eligibility unproven, operator not enough evidence | Privilege escalation, mistaken targets and access loss; verify owner role, exact XUID identity and method/path; restricted Discord policy and concrete confirmations |
| 11 | Open/close and moderation alerts/actions | Technically documented; expected owner authorization | Service disruption/kicks; separate observation-only alerts from deliberately approved actions; ban/unban requires moderation privacy and audit policy |
| 12 | Invitation link management | Documented; likely owner authorization | Link disclosure grants access; regeneration may invalidate existing links. Never publish raw links in public panels/logs |

Do not switch to the owner's credentials as an automatic fallback. Establish
whether the current account owns Coastal Craft before classifying any capability
Permission restricted. Future owner authentication would require its own review.

## Priority 4: advanced worlds and backups

| Rank | Candidate and value | Feasibility/permissions | Risks and dependencies |
| --- | --- | --- | --- |
| 13 | World-slot selection and settings tools | Documented shared/client paths; owner expected | World disruption; configuration POST/PUT and singular/plural permission paths conflict in sources; verify contract outside production first |
| 14 | On-demand backup/world export | Documented metadata/archive preparation; owner expected | Whole-world data and bearer download URL; private destination, access/size/retention limits; not ordinary GET monitoring |
| 15 | Backup restore, reset and world replacement | Restore/reset documented; upload protocol unresolved | Highest data-loss risk; require tested independent recovery/export and explicit target confirmation. Do not infer upload protocol from marketing overview |

## Safe verification sequence and decision gates

First review the concrete probe plan in capabilities. It proposes existing allowlisted
metadata reads, then separately approved Stories/settings and backup metadata reads,
with privacy summaries and one attempt per route. The on-disk disabled diagnostic,
production store lock, no-POST rule and current allowlists remain intact in Phase 5.

Before approving Phase 6, decide the first feature, sampling cadence, public versus
OP Team visibility, history retention and alert thresholds. Validate API field presence
and account authorization before promising a Discord feature. New owner-sensitive
or destructive operations need separate scope and a safe non-production verification
strategy; documentation is not execution authorization.
