# Realms live read-only pilot results

Date: November 3, 2026 (America/Chicago). Branch: `codex/realms-phase2`.

The operator explicitly authorized device-code authentication and subsequent read-only discovery/details/activity checks. The operator completed Microsoft browser sign-in. The existing diagnostic was used without production code changes or a full test-suite rerun.

## Verified behavior

| Step | Actual sanitized result |
| --- | --- |
| Captain-owned Entra public-client device authorization | Device-code request accepted; browser authorization completed |
| Microsoft → Xbox user-token → general-XSTS identity | Succeeded; returned identity matched the privately configured designated test gamertag |
| Credential persistence | Refresh credentials saved with authenticated encryption; encryption key stored separately with Windows DPAPI protection |
| Fresh-process credential reuse | Both subsequent probe processes loaded the encrypted record and successfully refreshed/rebuilt the authorization chain without another browser sign-in |
| Realms-specific XSTS authorization | Succeeded for `https://pocket.realms.minecraft.net/` |
| `GET /worlds` | HTTP 200, successfully parsed; one accessible Realm: **Coastal S10: The Mighty Mesa Reborn** |
| `GET /worlds/{selected_realm_id}` | HTTP 200, successfully parsed; configured Realm state **OPEN** |
| `GET /activities/live/players` | HTTP 200, successfully parsed; selected Realm activity contained **2 player records** |
| `Client-Version` | Operator-provided installed stable version **1.26.61** was accepted for these requests |

HTTP 200 is established by the client's success branch: non-200 responses cannot produce the successful typed observations printed by the diagnostic. No raw response bodies, tokens, one-time codes, XUIDs, operator/guild IDs, key material or private Realm identifier are reproduced here.

## Limits and actual blockers

No authentication or API error occurred in the exercised paths. The Captain can now read the selected Realm through the private diagnostic using its own registered application and the designated secondary account. No primary Realm-owner credentials were used as a fallback. Success establishes access for this account; this pilot did not independently establish its exact membership/ownership privileges.

The activity result is one API snapshot, not a controlled join/leave comparison, exact session history, or independent verification inside the game. OPEN is the service's configured state, not a game-protocol reachability test. Invitation endpoints, rate limits, revocation, long-duration unattended renewal and Linux hosting were not exercised in this live session.

## State after completion

The private configuration retains the selected Realm for later approved diagnostics and is disabled again. Process-scoped key variables were removed after each diagnostic. Encrypted refresh credentials and the separately protected key remain outside the checkout for future authorized use. Host/key backup and recovery remain operational responsibilities.

No Realm mutation, invitation acceptance, Minecraft player connection, Discord command, background poller, deployment, merge or PortalBot modification occurred. This result does not enable bot startup integration or authorize those further phases.
