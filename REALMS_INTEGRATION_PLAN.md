# The Captain: Bedrock Realms integration plan

Phase 1 — repository audit, research, and architecture. Reviewed November 3, 2026 (America/Chicago).
Local checkout inspected: `ded674cd740c17b3c82d12ee85c6533b86d58c20` plus an existing working-tree edit to `docs/dependencies.md`.

## 1. Executive summary

Proceed to a gated, read-only Python pilot after owner approval. Use passwordless Microsoft device authorization, exchange the resulting delegated token for Xbox Live and Realms-audience XSTS tokens, and call the Bedrock Realms HTTPS service. An asynchronous client can fit Captain without a Node bridge or permanently connected Minecraft player.

This is a feasibility recommendation, not an end-to-end authentication verification. No account was authenticated, no Realms endpoint was called, no package was installed, and no production code/configuration was changed in Phase 1. PortalBot was not modified. The existing dependency-document edit is preserved.

The principal go/no-go gate is whether Captain's own registered public client can obtain the necessary scopes and complete Xbox/XSTS authorization for the intended account. Do not substitute another application's client ID, a password flow, or a first-party title identity if that fails. Establish the permitted registration/approval path first.

The source-supported API surface includes discovery, Realm details, pending invitations, live activity, membership changes, and permissions. These are reverse-engineered interfaces, not a Microsoft-supported public Realms API contract. All capabilities remain untested against Coastal Craft. Initial access must allow only explicitly selected read routes; owner credentials may still carry write authority upstream.

## 2. Evidence and research findings

### Evidence labels and limits

- **Official documentation:** Microsoft/Mojang describes the particular behavior; this does not imply an official Realms API contract.
- **Reverse-engineered:** executable third-party source contains the request; this proves implementation intent, not current service behavior.
- **Unverified:** inaccessible content, conflicting claims, or a hypothesis requiring controlled validation.
- **Obsolete/inapplicable:** wrong platform or historical flow; do not use for this pilot.
- **Live-verified:** requires an authorized account test. No findings in this document have that status.

Research used public documentation and source available through web retrieval. Some GitHub files returned cache errors; Postman's page exposed its shell but no request collection. Exact upstream revision dates/SHAs and complete dependency metadata could not be established reliably. Links to branch heads are mutable: Phase 2 must record immutable revisions and release metadata before reuse. Recent crawler dates are not proof of maintenance.

### Requested sources and reuse assessment

| Source | What was established | Reuse decision |
| --- | --- | --- |
| [Minecraft Realms](https://www.minecraft.net/en-us/realms) | Official product context for hosted private worlds; does not supply an automation API specification. | Product context only. |
| [BedrockRelay](https://bedrockrelay.com/) and its [Realm developer guide](https://bedrockrelay.com/developers/realms.html) | The documented Realm mode places a bot player in the world and installs plugins through a Realm pack. | Does not meet this pilot's no-permanent-player requirement. No source/license/dependency audit sufficient for reuse was obtained. Do not delegate credentials to the service. |
| [Home Assistant integration research](https://github.com/LucaFSmart/ha-minecraft-bedrock-realms/blob/main/docs/research.md) and [architecture](https://github.com/LucaFSmart/ha-minecraft-bedrock-realms/blob/main/docs/architecture.md) | Useful leads about activity polling and service separation. The research both asserts self-registration is confirmed and retains that question as an open PoC item. Its portrayal of elytra's registration differs from elytra's README. | Secondary lead only. License, release health, dependency closure, and actual auth implementation were not sufficiently verified; do not copy or install. Do not inherit its storage-security claims. |
| [Postman collection](https://www.postman.com/lucienhh/bedrock-realms/documentation/pda92ab/bedrock-realms-api) | Collection landing page exists; endpoint bodies, headers, provenance, and update history were unavailable in retrieved content. | Unverified; no capability below is attributed to unseen Postman requests. |
| [RealmsPlayerlistBot](https://github.com/AstreaTSS/RealmsPlayerlistBot), [polling source](https://github.com/AstreaTSS/RealmsPlayerlistBot/blob/main/exts/playerlist.py), [requirements](https://github.com/AstreaTSS/RealmsPlayerlistBot/blob/main/requirements.txt) | Polls `fetch_activities()` on a minute schedule. Uses `discord-py-interactions`, elytra-ms 0.7.3, HTTPX, PostgreSQL/Tortoise, and Valkey; includes a Git-pinned HTTPcore fork. Repository declares AGPL-3.0. | Behavioral evidence only; its framework and infrastructure do not match Captain. Do not transplant code without a license review. Operational history is not a security audit. |
| [elytra-ms](https://github.com/Astrea-Stellarium-Labs/elytra-ms), [core](https://github.com/Astrea-Stellarium-Labs/elytra-ms/blob/main/elytra/core.py), [Bedrock client](https://github.com/Astrea-Stellarium-Labs/elytra-ms/blob/main/elytra/bedrock_realms/__init__.py) | MIT-licensed async Python implementation; inspected source imports HTTPX, msgspec, typing_extensions and a retry transport. README documents authorization-code login with a client secret and local OAuth file, not the proposed device-code onboarding. | Strong protocol reference; not a drop-in approved authentication/storage solution. Complete published dependency closure, advisories, release recency and Python 3.12 compatibility require a fresh review. |
| [prismarine-realms](https://github.com/PrismarineJS/prismarine-realms), [package metadata](https://github.com/PrismarineJS/prismarine-realms/blob/master/package.json), [prismarine-auth flow](https://github.com/PrismarineJS/prismarine-auth/blob/master/src/MicrosoftAuthFlow.js) | Realms package declares MIT and version 1.6.0; runtime dependencies include node-fetch 2 and debug, with prismarine-auth in development dependencies. Auth flow exposes multiple auth strategies and file caching. | Independent request/header reference, not a Python dependency or reason to adopt its credential cache. Review auth package licensing/closure separately before copying anything. |

No third-party package is approved for reuse by this document. Source inspection supports feasibility; it does not certify present maintenance, license compatibility of a derivative, or secure defaults.

### Microsoft device authorization

Use an owner-controlled Entra app registration accepting personal Microsoft accounts and enable public client flows. Pure device authorization needs no inbound callback or client secret. Microsoft documents public-client configuration separately from confidential website login. [Public-client configuration](https://learn.microsoft.com/en-us/entra/identity-platform/scenario-desktop-app-configuration).

The proposed authority is `https://login.microsoftonline.com/consumers/oauth2/v2.0`. Start `/devicecode`, display the returned verification URI/user code privately, and poll `/token` with the device grant. Respect the returned interval/expiry and handle pending, denial, expiration, cancellation, and throttling. Microsoft documents refresh-token issuance with `offline_access`. This works on a headless host while the owner completes sign-in in a separate browser. [Device authorization protocol](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-device-code).

Candidate scope set: `XboxLive.signin offline_access` for this v2 device flow. **Exact acceptance for Captain's registration is unverified.** Microsoft's Xbox website documentation instead illustrates `XboxLive.signin XboxLive.offline_access` in an authorization-code flow; elytra uses the latter with `login.live.com/oauth20_token.srf`. These are separate endpoint/flow examples, not interchangeable recipes. No Graph `User.Read`, Minecraft Java scope, application permission, or client-credentials grant is justified here. [Xbox website authentication](https://learn.microsoft.com/en-us/gaming/gdk/docs/services/fundamentals/s2s-auth-calls/service-authentication/live-website-authentication), [elytra token requests](https://github.com/Astrea-Stellarium-Labs/elytra-ms/blob/main/elytra/core.py).

Validate approved scopes, account audience, token audience and Realms authorization as one tuple. Retain MFA; missing Xbox profile, family/age consent, region, enforcement, consent policies, registration restrictions or title authorization may prevent access. Treat denial as a setup problem; never bypass it. Java Minecraft Services app approval and Bedrock game-session authentication are different concerns and do not settle Bedrock Realms eligibility.

Microsoft refresh tokens can expire or be revoked; its general documentation describes a 90-day default in many non-SPA scenarios, not guaranteed unattended access. Persist a newly returned refresh token atomically before discarding the previous durable value; do not assume the old token is immediately revoked. On `invalid_grant`, stop automatic refresh and require private reauthentication. Use server expiry metadata, not token parsing or a fixed lifetime. [Refresh-token lifecycle](https://learn.microsoft.com/en-us/entra/identity-platform/refresh-tokens).

### Xbox Live, XSTS and Realms headers

Microsoft documents an RPS exchange at `POST https://user.auth.xboxlive.com/user/authenticate`: `AuthMethod=RPS`, `SiteName=user.auth.xboxlive.com`, `RpsTicket=d=<MSA access token>`, `RelyingParty=http://auth.xboxlive.com`, `TokenType=JWT`, JSON and `x-xbl-contract-version: 1`. Then exchange the returned user token at `https://xsts.auth.xboxlive.com/xsts/authorize`. Its website example is not a device-code/Realms recipe. [Official Xbox exchange](https://learn.microsoft.com/en-us/gaming/gdk/docs/services/fundamentals/s2s-auth-calls/service-authentication/live-website-authentication).

For consumer Realms, elytra source supplies `SandboxId=RETAIL`, `UserTokens=[user token]`, `TokenType=JWT` and the target relying party. It reads `DisplayClaims.xui[0].uhs`; this user hash is distinct from the XUID (`xid`). Validate required claims and reject missing/ambiguous identities. Xbox stages return `NotAfter`; renew before expiry with a clock-skew margin. No separate Xbox refresh token is assumed: renew through the Microsoft → Xbox → XSTS chain. [elytra authentication source](https://github.com/Astrea-Stellarium-Labs/elytra-ms/blob/main/elytra/core.py).

Independent source evidence sets the Realms relying party to **`https://pocket.realms.minecraft.net/` (trailing slash)** and formats **`Authorization: XBL3.0 x=<uhs>;<XSTS token>`**. This is not a Java session cookie or a Bearer Minecraft Services token. [Prismarine constants](https://github.com/PrismarineJS/prismarine-realms/blob/master/src/constants.js), [header formatter](https://github.com/PrismarineJS/prismarine-realms/blob/master/src/util.js).

Observed Realms headers include `Client-Version` and `User-Agent: MCPE/UWP`. The inspected elytra constant is `1.21.21`, while Prismarine defaults to `0.0.0`; neither establishes the version accepted today. Make an explicitly validated stable Bedrock version configurable; never blindly copy a stale constant. Preview access remains disabled. Separate XSTS caches by account and relying party; Xbox profile lookups need their own appropriate audience. [elytra constants](https://github.com/Astrea-Stellarium-Labs/elytra-ms/blob/main/elytra/const.py), [Prismarine transport](https://github.com/PrismarineJS/prismarine-realms/blob/master/src/rest.js).

## 3. Proposed authentication sequence

The diagram describes a future approved pilot; it has not been executed.

```mermaid
sequenceDiagram
    actor Owner
    participant Command as Private owner workflow
    participant MSA as Microsoft identity
    participant Store as Private token store
    participant XBL as Xbox user authentication
    participant XSTS as Xbox XSTS
    participant Realms as Bedrock Realms HTTPS
    Owner->>Command: Explicitly start device authorization
    Command->>MSA: POST /consumers/oauth2/v2.0/devicecode
    MSA-->>Command: user_code, device_code, URI, expiry, interval
    Command-->>Owner: Private verification URI and user_code
    Owner->>MSA: Browser sign-in, MFA and consent
    loop Until authorized, cancelled, denied or expired
        Command->>MSA: POST /token with device grant, respecting interval
        MSA-->>Command: Pending or access/refresh tokens
    end
    Command->>Store: Atomically persist encrypted refresh token
    Command->>XBL: RPS exchange with MSA access token
    XBL-->>Command: User token, claims, NotAfter
    Command->>XSTS: RETAIL + UserTokens + Realms relying party
    XSTS-->>Command: XSTS token, uhs, NotAfter
    Command->>Realms: Allowlisted GET with XBL3.0 authorization
    Realms-->>Command: Realm data or classified error
    Command-->>Owner: Sanitized private result and freshness
    Note over Command,Store: Serialize renewal; replace rotated refresh token durably
    Note over Command,MSA: Revocation requires explicit reauthentication
```

## 4. Repository audit and integration points

| Area / files inspected | Findings and architectural consequence |
| --- | --- |
| `main.py` | Safe import; dependency-injected database/Sheets initialization in `setup_hook`; extensions load afterward. Add an optional Realms service only after configuration is loaded. Do not authenticate in `on_ready`, which can repeat. No Captain-specific HTTP shutdown override exists; add deterministic service cleanup in a later phase. |
| `utils/core_features/__constants.py`; `cf_main.py` layout | Explicit `EXTENSIONS` tuple loads core, administration, applications, guide, POI and jishaku. Optional players cog is separately gated. Follow the optional pattern rather than loading Realms globally. |
| `utils/configuration.py`; `.env.example`; `config/` and `migrations/` layout | Bootstrap environment contains secrets; operational settings come from `botdata.settings_json` row 1. Exact-key/version validation rejects arbitrary new settings. New Realms settings require an explicit schema/seed/migration design; editing `.env` or a seed alone will not configure runtime. Private `.env` contents were not read. |
| `utils/database/__database.py` | Peewee/MySQL; initialization runs through a worker. Keep tokens out of botdata, player tables and backups. No automatic new table creation. |
| `utils/integrations/__google_sheets.py` | Existing injected service, lock and worker boundary provide a lifecycle/testing precedent. Realms should use native async HTTP; do not share Google credentials or scopes. |
| `utils/helpers/__checks.py`; `main.py:is_owner`; `utils/admin/bot_management/{bm_main.py,__bm_commands.py}` | OP Team is a role check; prefix administration uses tier 3. `TheCaptain.is_owner` also accepts tier-3 administrators. Neither means a strict authentication owner allowlist. Add an explicit owner-ID check for Realms sensitive workflows; do not rely solely on `commands.is_owner()`. |
| `utils/core_features/__special_methods.py`; `utils/helpers/__logging_module.py` | User-facing errors are generic and ephemeral for slash commands; error logging normally emits exception type. Custom formatter can emit tracebacks and DEBUG logs. Integration exceptions must never retain credentials, payload bodies or secret URLs for generic handlers to expose. |
| `utils/players/{cog.py,models.py}` and repository search across `utils/`, `tests/`, README | Existing gamertags, optional XUID, verified identities, season participation and Discord check-ins. No existing Microsoft/Xbox/Realms HTTP integration found in active paths. Keep API observations separate from verified Discord↔XUID links, check-ins and staff eligibility. |
| `requirements.in`, `requirements.txt`, `requirements-dev.txt`, `.python-version`, `docs/dependencies.md` | Already targets discord.py **2.7.1**, CPython **3.12.14**; closure pins aiohttp **3.14.5**, cryptography **50.0.2**. Existing `.venv` metadata reports those same versions. Do not repeat the planned upgrade or infer deployed versions from local pins. |
| `pytest.ini`, `tests/conftest.py`, `tests/test_captain.py`; test inventory | pytest-asyncio auto mode, synthetic service fixtures and network guard; SQLite-backed testing exists. Guard blocks external socket connections and permits loopback for Windows internals. Retain offline defaults. |
| `.github/workflows/*`, README, `.gitignore` | Windows/Linux Python 3.12 offline checks, dependency audit and deployment workflows exist. Main pushes can restart production; do not publish/merge this pilot casually. Current ignore rules exclude `.env`/some credential files but do not generically exclude all OAuth JSON caches. |

No regression suite was run for this documentation-only change. Prior test totals in `docs/dependencies.md` are historical reports, not results produced by this audit. Phase 1 verification consists of source review, local installed-version inspection, document structure and change-scope checks.

## 5. Proposed modules and contracts

All paths below are proposals, not files created in Phase 1.

```text
utils/integrations/realms/
    __init__.py         # public service interfaces, no import side effects
    microsoft.py        # device state machine and Microsoft token renewal
    xbox.py             # RPS, XSTS, audience-keyed expiring token cache
    token_store.py      # TokenStore protocol and encrypted backend
    client.py           # narrowly scoped asynchronous Realms API
    models.py           # typed Realm, member, invitation and activity snapshots
    errors.py           # sanitized domain errors
    service.py          # lifecycle, refresh serialization and polling coordinator
    configuration.py    # typed operational config validation
utils/realms/
    cog.py              # owner-only private testing adapter, later phase
tests/
    test_realms_auth.py
    test_realms_store.py
    test_realms_client.py
    test_realms_service.py
    test_realms_permissions.py
```

Design decisions:

1. Inject HTTP session/transport, TokenStore, UTC clock, monotonic timer and sleep into services. Expose `begin_device_login`, bounded `poll_device_login`, `authorization_for(relying_party)`, and typed read methods. Keep Discord imports out of reusable integration modules. Secret values use redacted representations and are never included in exception messages.
2. Own one reusable aiohttp session for the integration; use per-request audience-specific authorization, not global session credentials. Fix outbound HTTPS hosts; disable redirects on authenticated calls. Bound connection/total timeouts, response sizes and concurrency; retain TLS verification. Never accept user-supplied API base URLs.
3. `service.py` owns one renewal lock per account and a single poll task. Capture a generation when refreshing; prevent duplicate rotations and cross-account cache reuse. File-backed operation supports one writer process; refuse concurrent deployments rather than relying on an asyncio lock across processes.
4. After ordinary database/Sheets startup, construct the optional service without network login. Disabled mode creates no tasks, sessions or commands. Missing/revoked tokens put only Realms into `reauth_required`; outages must not prevent existing Captain commands from operating. Invalid enabled configuration fails locally with a sanitized actionable diagnostic.
5. Close/cancel tasks and await session shutdown on bot close, extension unload and partial initialization failure. Do not duplicate pollers on reconnect/reload. Retain dependency injection used by existing startup tests.
6. Initial Realms client has no mutation methods and permits only exact GET routes listed for the pilot below. Authentication POSTs use separate fixed-host adapters. This is an application guard, not a read-only OAuth permission.
7. Later monitoring may start with 60-second activity polling and a slower metadata cadence (for example five minutes), sharing cached snapshots with commands. These are conservative design defaults, not documented rate limits. Pause on 429/Retry-After and use bounded exponential backoff/jitter for safe reads on transient failures. At most one serialized renewal/retry for 401; classify 403 without endless refresh. Never replay writes automatically.
8. Snapshots carry observation time, last success and freshness. Failed/missing/malformed polls become unknown/stale, never zero players or confirmed departure. Baseline the first successful observation without emitting mass joins. Membership, subscription expiry, configured OPEN/CLOSED state and actual reachability are different facts.
9. Gamertag lookup is a separate optional Xbox service with TTL caching and audience isolation. Preserve XUIDs as strings. Do not overwrite player-registry identity verification or derive check-in eligibility from online observations.

## 6. Required configuration and secrets

Proposed operational keys belong in a reviewed versioned settings schema, not arbitrary environment overrides. Defaults must be supplied through an explicit migration compatible with current exact-key validation.

| Proposed setting | Meaning / initial value |
| --- | --- |
| `realms_enabled` | false; activation requires later approval |
| `realms_client_id` | Captain-owned public app ID; identifier, not a secret |
| `realms_auth_owner_ids` | explicit narrow Discord allowlist; no implicit tier-3/OP Team inclusion |
| `realms_realm_id` | selected stable numeric Realm ID represented as a validated string; never identify by display name alone |
| `realms_account_ref` | opaque token-store account reference; no email needed in command output |
| `realms_client_version` | stable Bedrock client version proven in the pilot |
| `realms_poll_seconds` | 60 for later monitoring; polling off for first manual probe |
| `realms_read_only` | true; additionally enforce the method/path allowlist |
| `realms_guild_id` | existing Coastal guild identity; restrict commands and callbacks to it |

Fixed protocol configuration: consumers authority, scope tuple established by pilot, RETAIL sandbox and Realms relying party. Changes require code/configuration review rather than a command-supplied arbitrary host or scope.

Secrets: Microsoft refresh token, temporary access/Xbox/XSTS tokens, device code and private user code during onboarding, plus any token-store encryption key. Public-client design needs no Microsoft client secret and no account password. No real values belong in examples, Git, Sheets, botdata, Discord attachments or CI artifacts.

Preferred store: hosting-provider secret facility with access limited to Captain's service identity. If unavailable, use an authenticated-encrypted file on a persistent private volume **outside the checkout/deployment-sync tree**, with a separately injected encryption key and versioned key ID. Use existing cryptography primitives; never invent encryption. Windows ACLs restrict the service identity; Linux file mode 0600/directory 0700. Validate access and reject symlinks/unsafe paths. Atomic same-volume replace, restrictive temporary-file permissions and durable rotation are required. Key loss means reauthentication; a missing key must not silently create plaintext storage. OS keyrings are an option only after proving noninteractive service/container support.

Store account/client/audience metadata alongside ciphertext to prevent accidental account swapping. Keep short-lived Xbox/XSTS values in memory where practical. Define encrypted backups, key rotation, revocation and recovery before live use. Encryption with a key beside the cache is insufficient; encryption also cannot protect a running process from an attacker who controls its service identity. Add specific future ignore/secret-scan coverage for fallback caches; current `.gitignore` is not enough.

## 7. Dependency recommendations

- Keep discord.py 2.7.1 and Python 3.12.14. There is no Realms-driven Discord upgrade requirement.
- Prefer aiohttp already present in the runtime closure. If Captain starts importing it directly, declare it explicitly in `requirements.in` and regenerate/review the pinned closure in Phase 2. No dependency files change now.
- Cryptography is already present transitively. If encrypted file storage is selected, promote it to a direct reviewed dependency instead of assuming a transitive guarantee. Provider-secret storage may avoid application-managed encryption keys.
- Evaluate official MSAL Python for Microsoft token management before implementing the protocol manually. Its synchronous calls require a bounded worker and explicit cancellation handling; do not run blocking device polling on the event loop. Choose it only after validating Xbox scopes, personal-account device flow and secure cache persistence. Otherwise use a small audited aiohttp adapter with protocol tests. MSAL does not replace Xbox/XSTS/Realms adapters.
- Do not install elytra-ms, a Discord framework replacement, a Bedrock game-protocol client or a Node bridge for this plan. A later elytra adoption decision needs pinned release/source/license and full dependency/advisory review plus storage and device-flow validation.
- Reuse pytest/pytest-asyncio and injected fake transports; no new HTTP mocking library is inherently required. A future dependency change must pass existing pip consistency and security checks on Windows/Linux.

## 8. API endpoint capability matrix

Base URL: `https://pocket.realms.minecraft.net`. **Every Realms route below is reverse-engineered unless explicitly marked otherwise; none is live-verified here or officially documented by Microsoft as a public automation API.** The Postman collection is community documentation with unavailable request content, not an official contract.

Sources: [E = elytra Bedrock client](https://github.com/Astrea-Stellarium-Labs/elytra-ms/blob/main/elytra/bedrock_realms/__init__.py), [B = Prismarine Bedrock methods](https://github.com/PrismarineJS/prismarine-realms/blob/master/src/bedrock/api.js), [C = common Realm methods](https://github.com/PrismarineJS/prismarine-realms/blob/master/src/index.js), [P = playerlist polling](https://github.com/AstreaTSS/RealmsPlayerlistBot/blob/main/exts/playerlist.py).

| Capability | Request / evidence | Confidence, limitations and pilot policy |
| --- | --- | --- |
| Accessible Realms | `GET /worlds` — E, C | Reverse-engineered; owned/joined visibility depends on account. Initial allowlist. |
| Realm details | `GET /worlds/{id}` — E, C | Reverse-engineered; inspect field availability/permissions. Initial allowlist only for selected ID. |
| State/status | Read details/list state and expiry fields | Reverse-engineered data, not proof of uptime. No independently verified health endpoint. |
| Membership roster | `players` when provided in Realm details | Partial/unverified completeness; null/absent roster must remain unknown. Member, invite acceptance, operator and online flags are distinct. |
| Pending invitations | `GET /invites/pending`, `GET /invites/count/pending` — E, B | Reverse-engineered; account's incoming invitations, not necessarily all invitations sent by the owner. Initial optional allowlist. |
| Current online activity | `GET /activities/live/players` — E; called by P | Reverse-engineered with direct consumer evidence. Initial allowlist. Validate Realm/account visibility and response shape; return XUIDs when names are absent. No persistent game connection. |
| Invite link information | `GET /links/v1?worldId={id}`; `GET /worlds/v1/link/{code}` — B | Reverse-engineered; link/code sensitive. Excluded from pilot. Some library helpers automatically accept links: do not use them. |
| Invite/remove member | `PUT /invites/{id}/invite/update`, body `invites: {<XUID>: ADD/REMOVE}` — B; ADD also E | Reverse-engineered; expected owner authority requires verification. Write operations excluded. |
| Operator changes | Same update route with `OP` / `DEOP` — B | Reverse-engineered; excluded writes. |
| Explicit permissions | `PUT /world/{id}/userPermission` (`permission`, `xuid`); `/world/{id}/defaultPermission` (`permission`) — B | Reverse-engineered; note singular `world`. Accepted values and visitor/member/operator behavior require validation. Excluded writes. |
| Accept/reject incoming invitation | `PUT /invites/accept/{invitationId}`, `/invites/reject/{invitationId}` — E, B | Reverse-engineered writes; excluded even if a library labels them discovery/setup. |
| Connection address | `GET /worlds/{id}/join` — B | Reverse-engineered, potentially session-related. Excluded; unnecessary for monitoring. |
| Open/close | `PUT /worlds/{id}/open` or `/close` — C | Reverse-engineered administrative writes; excluded. |
| Java live player list | `/activities/liveplayerlist` in Java-oriented implementations | Inapplicable to Bedrock; do not substitute for `/activities/live/players`. |
| Dedicated health, complete outgoing invites, chat/RCON, arbitrary game commands | No suitable contract established in inspected sources | Unverified/unsupported by this plan; no invented endpoints or claims of API capability. |

The inspected [elytra response models](https://github.com/Astrea-Stellarium-Labs/elytra-ms/blob/main/elytra/bedrock_realms/models.py) distinguish full/individual Realm responses from activity snapshots, allow nullable membership lists, and model player names as absent. These are library expectations, not a validated service schema. Online membership flags are not selected as the presence source. Activity polling gives observations with possible gaps, not exact event times or a complete historical ledger. No universal owner/member visibility guarantee, service rate-limit number or supported-version guarantee was established.

## 9. Security requirements and operational risks

1. **Strict owner boundary:** check explicit IDs and Coastal guild at command execution, login completion and every component callback. Reject ordinary administrators/OP Team unless explicitly allowlisted. Use ephemeral output, suppress mentions, defer promptly, bind the login session to requester/account and expire it. Prefer a private operator CLI for the first live probe, reducing Discord exposure.
2. **Device-code phishing:** show codes only in an owner-requested flow; never accept codes supplied by other users or automatically trigger login. Validate returned verification hosts against Microsoft's expected hosts. Do not log/store device codes in generic interaction telemetry. Disconnect/cancel ends polling.
3. **Upstream privilege:** there is no established read-only Realms OAuth scope. An owner's stolen refresh token may enable management beyond this client. Use a dedicated adult monitoring account invited through the official client where possible; verify whether it can read activities. If owner access is required, document the wider exposure and obtain explicit approval before that account's pilot.
4. **Logging:** allow only operation name, sanitized error category/status, duration and correlation ID. Strip authorization, cookies, device/token fields, invite codes/URLs and sensitive response data. Disable HTTP wire tracing; test normal logs, tracebacks, reprs, Discord replies and exception chains with canary secrets. Do not feed raw upstream errors into generic handlers.
5. **No write path initially:** method/path allowlist and absent mutation methods; no auto-join, invite acceptance or account enrollment by a helper. Authentication POSTs are permitted only on fixed auth hosts. Future writes require a separate approval gate, preview of exact Realm/XUID/action, short-lived one-use confirmation bound to the owner and payload, fresh authorization at execution and sanitized audit events.
6. **Privacy:** online activity and XUID↔Discord associations are personal data. Minimize retention/access; keep initial results private, show observation timestamps, establish a retention policy before session history. Do not store full responses as fixtures or attach token caches to support reports.
7. **Availability:** fail Realms independently, apply rate-limit backoff and stop refresh loops. Treat no data as unknown. A process restart must not lose rotated credentials or launch duplicate pollers. Expose only token-free readiness/reauth state.
8. **Operator access:** jishaku is already loaded and authorized debugging can inspect process memory. Protect bot owner/debug rights, host/panel administrators and backups. App-layer encryption does not remove those trust boundaries.
9. **Undocumented service:** endpoints, headers, eligibility and versions can change without notice; account enforcement or throttling can interrupt operation. Review terms and applicable developer requirements before production use; third-party success is not permission or an availability promise.

## 10. Phased implementation checklist

### Phase 1 — this document

- [x] Inspect Captain's startup, configuration, services, permissions, logging, dependencies and tests.
- [x] Investigate all five requested sources; record inaccessible evidence and contradictions.
- [x] Define module boundaries, auth sequence, capability matrix, storage and acceptance gates.
- [x] Leave production code, dependencies, account state and PortalBot unchanged.
- [ ] Owner approval to begin Phase 2. Stop here until granted.

### Phase 2 — approved authentication and manual read-only proof

- [ ] Recheck working-tree state and dependency upgrade work; preserve unrelated edits.
- [ ] Record immutable upstream source revisions, release/dependency metadata and licenses; settle MSAL versus native async adapter.
- [ ] Establish Captain-owned public registration and exact permitted scope/authority tuple; no borrowed IDs.
- [ ] Approve account, narrow owner allowlist and persistent secure storage backend; prove recovery and key isolation.
- [ ] Implement integration modules with injected dependencies and offline tests first; default disabled and no background polling or write methods.
- [ ] Design explicit compatible settings schema migration; no implicit production schema changes.
- [ ] Add private local operator probe before Discord onboarding. Keep fake transport the default in automated tests.
- [ ] Perform separately owner-authorized device login and allowlisted reads; record only redacted response schemas/statuses. Stop if scopes/title eligibility fail.
- [ ] Verify restart/refresh/revocation, activities versus roster, account visibility and stable Client-Version. Report evidence and stop before production deployment or broader scope.

### Phase 3 — separately approved Discord read-only pilot

- [ ] Add optional guild-scoped owner-only private status/list/player commands and explicit login/cancel flow if desired.
- [ ] Add one bounded polling coordinator with freshness, rate-limit handling and safe reload/shutdown.
- [ ] Run existing regression/CI checks and a limited observation window; verify ordinary Captain features under Realms outage.
- [ ] Decide privacy/retention, host access controls, monitoring and rollback before activation. Register/sync commands explicitly; no automatic global sync.

### Phase 4 — separately approved administration

- [ ] Validate each mutation independently on a disposable/test Realm with known account authority.
- [ ] Add preview/confirmation/re-authorization, no automatic write replay, and an auditable recovery path.
- [ ] Treat invite removal, operator/permission changes and Realm open/close as separate capabilities. Do not couple check-ins or application approvals to automatic Realms writes.

## 11. Testing and acceptance criteria

Offline tests must retain the existing external-network prohibition and synthetic fixtures:

| Area | Required acceptance evidence |
| --- | --- |
| Microsoft auth | Pending respects interval; slow-down/throttle increases delay; deny/expire/cancel terminates. Grant payload, scope/authority selection and missing refresh token are handled. No password path. |
| Xbox/XSTS | Exact RPS/RETAIL/Realms audience and header construction; user hash is not XUID; malformed/missing claims rejected; expiry skew, audience isolation and one renewal under concurrent requests. |
| Storage | Wrong key/corrupt cache fails closed; atomic replacement/crash simulation preserves a usable durable state; restrictive permissions; no plaintext fallback; second writer refused; revocation and key rotation recovery documented. |
| Client | All non-allowlisted methods/routes rejected before I/O, including auto-accept and GET join. Test nullable roster, absent names, unknown fields, bad JSON, oversized response, timeouts, 401, 403, 429/Retry-After and 5xx; redirects cannot leak auth. |
| Service | Disabled mode has no network/tasks; reconnect/reload creates no duplicate workers; cancellation closes resources; startup/partial failure cleans up. Poll error/missing Realm never invents mass departures; timestamps show stale data. |
| Authorization/privacy | Unauthorized user, tier-3-only user, OP Team-only user, wrong guild, another user's component and expired callback all fail. Canary secrets absent from logs, exceptions, reprs, replies and attachments. |
| Regression | Existing startup/Sheets/application/POI/guide/player tests pass without Microsoft credentials. Windows/Linux Python 3.12 checks, pip consistency, lint and dependency audit pass if code/dependencies change. |

Live acceptance requires explicit owner authorization outside default CI: authenticate through Microsoft's browser UI with MFA; confirm the expected account and selected Realm; successfully read discovery/details/activities without a connected game bot; compare activity to a consenting player's controlled join/leave; verify freshness and unknown-state behavior; restart using persisted credentials and exercise renewal/revocation. Distinguish a true refresh exercise from simply reusing an unexpired XSTS token. Check that denied permissions and unknown versions produce useful sanitized failures. Do not invoke management endpoints, accept invitations, join the world or change membership as a side effect of testing.

Rollback: disable Realms and unload its optional cog/service; existing Captain behavior must continue. For compromise, stop the process, revoke Microsoft consent/sessions as appropriate, remove caches/keys and reauthenticate only after host review. A local cache deletion alone is not server-side token revocation.

## 12. Open questions and decision gates

1. Does an owner-controlled public registration work with the candidate device scopes through the Realms XSTS audience? Are additional Xbox/title approvals necessary for this exact account/app? This is the first live gate, not a presumed success.
2. Can a dedicated ordinary member account read adequate Realm metadata and activity, or is owner authority necessary? What does a missing Realm/activity entry mean for that account?
3. What stable Bedrock `Client-Version` and response schema are accepted today? How should updates be validated without unreviewed automatic header changes?
4. What are actual throttling and Retry-After behaviors? A 60-second precedent is not a documented quota.
5. Are complete membership and outgoing-invitation details available to the selected identity? Do not infer roster completeness or presence accuracy from model field names.
6. Which persistent private storage and separately managed keys are available on Captain's panel host? Do deploy/restart operations preserve that volume and exclude it from source sync/backups exposed to other operators?
7. What upstream releases/SHAs, licenses and dependency closure will be approved if an auth package is added? Home Assistant license and implementation remained unverified; no code reuse is authorized by this plan.
8. Who may view activity, how long may it be retained, and who can start reauthentication? No history collection or registry reconciliation is part of the first probe.
9. The current checkout and installed virtual environment match the requested Discord version, but the deployed runtime was not inspected. Reconcile concurrent upgrade work before any implementation/deployment.

## 13. Recommended Phase 2 implementation prompt

> Implement Phase 2 of The Captain's REALMS_INTEGRATION_PLAN.md only, following the approved account, client registration and storage choices. Work solely in TheCaptain; do not modify PortalBot or overwrite unrelated working-tree edits. Reinspect dependencies and configuration before changing them; retain discord.py 2.7.1 and Python 3.12 compatibility. First settle the public-client device-code scope/authority and Xbox authorization gates using primary documentation and record immutable references. Implement a reusable asynchronous integration with separate Microsoft, Xbox/XSTS, secure token-store and read-only Realms adapters, dependency injection and focused offline tests. Default disabled; preserve current exact-key database configuration through an explicit reviewed migration. Use Captain-owned registration, no passwords or borrowed client IDs, private durable refresh-token storage and sanitized logs. Provide a private operator probe; allow only discovery, selected Realm details, pending-invite reads and live activities. Do not add polling, Discord commands, membership/permission writes, auto-accept invitations or a game-client connection. Automated tests must not contact external services. Before live authentication, establish explicit owner authorization for the selected account and demonstrate storage/permission controls. Report what was actually live-verified versus source-inferred. Stop at a reviewable Phase 2 result; do not deploy, merge, sync Discord commands or proceed to Phase 3 without approval.
