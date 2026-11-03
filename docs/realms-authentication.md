# Realms Phase 2: private authentication and read-only diagnostic

For exact private Windows setup and the login-only approval boundary, see
[Windows preparation and first-test procedure](realms-windows-first-test.md).
It uses the owner's updated test identity only in the private configuration.

Implemented against main's `REALMS_INTEGRATION_PLAN.md` at `694cd90`. Status: **offline implementation only; live authentication is not authorized**. This runbook does not grant that authorization. No Microsoft account or Coastal Craft Realm has been contacted during implementation. No production initialization, command registration, database migration or background polling was added.

## Components and dependency decision

`utils/integrations/realms/` contains:

| Module | Responsibility |
| --- | --- |
| `configuration.py` | Disabled-by-default immutable settings and exact Discord user-ID/guild allowlist |
| `models.py`, `errors.py` | Typed observations, redacted credentials/identity representations, fixed error categories |
| `microsoft.py` | Public-client device authorization, bounded device-token polling and refresh |
| `xbox.py` | RPS user-token exchange and audience-specific XSTS authorization |
| `token_store.py` | Authenticated encryption, private permissions, single writer and atomic token rotation |
| `transport.py` | aiohttp HTTPS session, two concurrent requests maximum, 30-second total timeout, 1 MiB response limit, fixed URLs, no redirects/proxy environment/cookies |
| `client.py` | Allowlisted GETs, typed responses, at most one 401 renewal, bounded transient retry/Retry-After |
| `service.py` | Explicit login lifecycle, identity validation, serialized refresh, durable revocation state and cleanup; no scheduler |

The diagnostic is `python -m scripts.realms_diagnostic`. Run it from the repository root; direct script execution is not its supported entry point. It never imports `main`, opens MySQL/Sheets or starts Discord. Runtime code does not use the approved account's literal name, a fixed XUID, real credentials or any application ID. All test identities, tokens, IDs and versions are synthetic.

MSAL Python was considered. Its supported device API uses a synchronous polling/cache abstraction; an executor wrapper would need its own cancellation and secure persistence integration. For this small explicitly reviewed pilot, a native aiohttp state machine provides directly testable timing, cancellation and separate encrypted refresh storage without adding a second HTTP/cache stack. It follows the published device protocol; it is not a claim that custom OAuth is preferable for all applications. Revisit MSAL if authentication scope grows. [MSAL public API](https://msal-python.readthedocs.io/en/latest/#msal.PublicClientApplication.acquire_token_by_device_flow).

Existing pins are retained: Python 3.12.14, discord.py 2.7.1, aiohttp 3.14.5 and cryptography 50.0.2. The latter two are now direct declarations in `requirements.in`, at the exact versions already in `requirements.txt`. The pinned dependency closure is unchanged; no packages were installed. No third-party Realms/auth library or source implementation was vendored.

## Protocol evidence and remaining gates

| Reference | Recorded evidence |
| --- | --- |
| [Microsoft device protocol](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-device-code) | Device grant, interval/expiry and separate-browser sign-in; retrieved November 3, 2026 |
| [Public-client configuration](https://learn.microsoft.com/en-us/entra/identity-platform/scenario-desktop-app-configuration) | Enable public client flows; no redirect URI required for pure device flow |
| [Microsoft refresh lifecycle](https://learn.microsoft.com/en-us/entra/identity-platform/refresh-tokens) | Rotation/revocation; no guaranteed forever-valid refresh token |
| [Official Xbox exchange](https://learn.microsoft.com/en-us/gaming/gdk/docs/services/fundamentals/s2s-auth-calls/service-authentication/live-website-authentication) | RPS/Xbox user-token/XSTS stages; its website authorization-code example is not the device-flow recipe |
| [elytra source at ec666db90d719806475e0c161420ae17cd1efe9c](https://github.com/Astrea-Stellarium-Labs/elytra-ms/blob/ec666db90d719806475e0c161420ae17cd1efe9c/elytra/core.py) | RETAIL and XSTS claims/authorization shape; resolved main commit dated October 2, 2024. Treat as historical reference, not proof of maintenance. |
| [elytra metadata](https://github.com/Astrea-Stellarium-Labs/elytra-ms/blob/ec666db90d719806475e0c161420ae17cd1efe9c/pyproject.toml), [dependency declarations](https://github.com/Astrea-Stellarium-Labs/elytra-ms/blob/ec666db90d719806475e0c161420ae17cd1efe9c/requirements.txt) | MIT, Python >=3.10, alpha classification; HTTPX/HTTP2, AnyIO, websockets, dateutil, typing_extensions, msgspec, exceptiongroup. Broad dependency ranges are not an approved closure. Metadata includes a device-code helper entry point, correcting the Phase 1 README-only impression; helper behavior was not adopted. |
| [Prismarine constants at fad98435fd834e4d2280ab86a636561630a25f19](https://github.com/PrismarineJS/prismarine-realms/blob/fad98435fd834e4d2280ab86a636561630a25f19/src/constants.js), [formatter](https://github.com/PrismarineJS/prismarine-realms/blob/fad98435fd834e4d2280ab86a636561630a25f19/src/util.js) | Resolved master commit dated October 6, 2026; Realms RP has trailing slash and uses XBL3.0 authorization. No Node bridge used. |

The fixed candidate scope tuple is **`XboxLive.signin offline_access`** at the Microsoft consumers v2 endpoints. It has not been accepted by a real Captain-owned registration yet. Do not silently change endpoint family, scope tuple or application identity on failure. The exact registration/permissions, Xbox eligibility, Realms client version and ordinary-member visibility remain live gates. Do not use a borrowed first-party ID or the primary Realm owner's account as a workaround.

## Captain-owned application registration — future operator steps

Do not perform sign-in or create live secrets as part of this implementation review.

1. In Microsoft Entra app registrations, use an account authorized to register an application for Captain. Create a dedicated Captain registration, recording its ownership and application ID in your private operations inventory.
2. Select personal Microsoft accounts as the supported audience. In Authentication → Advanced settings, enable **Allow public client flows**. This diagnostic uses pure device authorization, so it needs neither a redirect URI nor a client secret. Do not follow a confidential website example's secret/callback steps.
3. Use only this registration's Application (client) ID in the private diagnostic configuration. The code validates GUID syntax but cannot prove that an app is Captain-owned: ownership must be checked operationally before a live test.
4. Review the exact `XboxLive.signin offline_access` consent/eligibility requirements with Microsoft. Do not add Graph/User.Read or application permissions speculatively. Retain MFA and account protection. Registration, consent or Xbox/title access may still be denied; stop and establish the supported path if so.
5. During a separately approved future test, verify that Microsoft's page identifies the Captain application before consenting. Type account credentials only into Microsoft's browser UI; never into this tool, chat or Discord.

## Configuration boundaries

The committed `config/realms.example.json` is disabled and contains no real identifiers. `check` performs validation only:

```powershell
.\.venv\Scripts\python.exe -m scripts.realms_diagnostic --config config/realms.example.json
```

For a future approved test, copy the example to an operator-controlled private file outside the checkout. Required enabled settings:

| Key | Value |
| --- | --- |
| `version` | local document version 1 |
| `realms.enabled` | false until the approved manual test |
| `client_id` | Captain-owned GUID, never a library default |
| `auth_owner_ids` | exact list of authorized Discord user IDs; no administrator or OP Team inheritance |
| `guild_id` | authorized Discord guild ID |
| `account_ref` | opaque local account reference, 1–64 letters/numbers/underscore/hyphen |
| `expected_gamertag` | designated test account's expected gamertag, supplied privately; no hardcoded fallback |
| `client_version` | explicitly selected stable Bedrock version; example/test versions are not live recommendations |
| `selected_realm_id` | null for initial discovery; later, a discovered permitted Realm's numeric string ID |

The designated test account can be an ordinary member. Discovery lists whatever that identity is permitted to see; details do not require an `owner` claim or assume Coastal Craft access. No automatic joining/invitation acceptance occurs. Missing data or a denied read stops that operation instead of escalating to the Realm owner.

**Production settings migration design:** this local versioned document is deliberately separate from existing `botdata.settings_json` version 1. Do not insert these keys into the exact-key production schema or change the deployment environment to enable them. A future bot adapter must introduce a separately reviewed schema version 2: explicitly transform an existing validated v1 document by adding a disabled Realms block, preserve all existing values, validate both the source and target, preview the change, require a verified backup before applying, and support rollback to the preserved v1 snapshot. No startup migration, database writes or schema-version bump is included in Phase 2 because no bot consumer is activated. The service is usable/testable without changing production configuration.

`Principal(user_id, guild_id)` is a policy check, not Discord authentication. A future Discord adapter must obtain those IDs from the authenticated interaction, never from command-supplied IDs. The local diagnostic accepts IDs from a trusted **OS operator** and enforces the same policy; someone with control of that operator account can edit local config or execute Python. This CLI does not pretend that typing a Discord ID proves Discord identity.

## Identity verification and refresh lifecycle

Device authorization is initiated explicitly; challenge/session state is bound to the requesting principal, single-use and expiring. The owner can cancel; cancellation stops the active device-token task. Login retrieves a general Xbox-audience XSTS identity and requires `xid`, `gtg` and `uhs`, matching the configured gamertag before saving a new refresh token. It does not call any Realm endpoint during login.

On restart/refresh the encrypted account's XUID remains pinned. A renewed general Xbox identity must match both that XUID and configured gamertag before issuing Realms-audience authorization. Realms XSTS uses `https://pocket.realms.minecraft.net/`, distinct from general Xbox `http://xboxlive.com`. A mismatched supplied Realm XUID also blocks use. Missing identity claims fail closed; there is no profile lookup or owner-account fallback. A renamed gamertag requires deliberate private configuration review/re-authentication, not an automatic account switch.

Tokens are renewed using expiry metadata with a 60-second margin. An asyncio lock serializes renewals; simultaneous 401s share a replacement token. Refresh-token rotation is saved before downstream exchanges; a failure after rotation can restart using the durable value. Cancellation waits for an in-flight disk operation before releasing the lock. `invalid_grant` records an encrypted revoked tombstone without the refresh secret and blocks repeated attempts, including after restart. A storage failure blocks use rather than falling back to plaintext or continuing with an unsaved refresh token.

## Encrypted storage and host controls

Provision a persistent private parent directory outside the repository, deployment sync tree and shared download locations. Supply an unused child directory to the store; it creates that leaf only, not an entire path tree. Each store directory represents **one account/client binding** and uses `account.realms.enc` plus a persistent `writer.lock`. Do not share it across deployment instances. A crash releases the OS lock; do not delete a lock file to defeat another running instance.

- **Encryption:** Fernet authenticated encryption from cryptography. Refresh token, XUID, gamertag, revoked status, schema version, client/account/scope binding and key ID are all inside the ciphertext. Outer key ID selects a separately managed key; mismatch, corruption, wrong binding or unknown key fails closed. Short-lived access/Xbox/XSTS tokens remain in memory.
- **Key injection:** the trusted operator environment provides `CAPTAIN_REALMS_KEYS`, a JSON map of key IDs to Fernet keys. Use a provider secret facility or a private secret loader. Never put key material in command-line arguments, shell history, config examples, token directories, source-controlled `.env`, logs or CI artifacts. Do not generate/print real keys in this chat. Environment contents and process memory remain accessible to sufficiently privileged host/debug operators.
- **Permissions:** Linux directory 0700/files 0600 and current UID ownership are checked. Windows creates a leaf ACL for the current identity and validates allow entries against that identity, SYSTEM and local Administrators; broad read access is rejected. Windows ACL handling uses Windows PowerShell/.NET, which must be present for this backend. No chmod-only Windows fallback exists. Keep the parent directory operator-controlled too.
- **Paths:** symlinks/junctions/reparse components are rejected; repository-local stores are rejected. Cache hardlinks and oversized cache files fail on read. Checks assume the operator/service identity and trusted administrators are not racing filesystem replacements; a compromised trusted identity is outside this backend's protection.
- **Rotation:** write encrypted content to a private same-directory temporary file, flush/fsync, then atomically replace. POSIX additionally fsyncs the directory. Windows file replacement/ACL behavior is tested locally; full machine/power-loss durability is not simulated. Do not interpret an atomic replacement test as disaster-recovery validation.
- **Key rotation:** provision old and new keys together, select the new active key ID, load the existing record then save it once through the store. Verify restart with only the new key before retiring old keys/backups. No diagnostic rotation command is included; use a reviewed offline operator procedure. Missing keys require reauthentication; they never create a plaintext cache.
- **Backups/revocation:** back up ciphertext and configuration separately from the secret key, restrict access, and test recovery under the correct service identity. Protect against restoring an older unrevoked backup. Local deletion is not Microsoft-side revocation; use Microsoft account/application consent/session controls after compromise.

The private diagnostic acquires and validates storage before opening its aiohttp session. It suppresses logging during its execution and prints fixed error categories, HTTP status/retry timing, counts and state except the deliberately displayed private Microsoft user code and verified gamertag. A separately approved probe can explicitly opt into private Realm ID/name output with `--show-realm-ids`; default output remains count-only. Do not redirect login output to files, record the terminal or attach debugger locals. The library emits no token/body logging; external callers must likewise avoid wire tracing, traceback-local capture or logging request objects. No Python code can prevent a privileged debugger from inspecting live process memory.

## Allowed Realms calls

Both client and HTTP transport enforce method/URL allowlists:

| Method/path | Behavior |
| --- | --- |
| `GET /worlds` | Discover accessible Realms |
| `GET /worlds/{selected_realm_id}` | Read only the exact configured ID |
| `GET /activities/live/players` | Activity observations; no game connection |
| `GET /invites/pending` | Read incoming invitations without accepting |
| `GET /invites/count/pending` | Read incoming invitation count |

Authentication POSTs are allowed only to the fixed Microsoft device/token and Xbox user/XSTS endpoints. No Realms POST/PUT/DELETE exists. Join address, invite links, acceptance, permissions, opening/closing and Java live-player routes are denied before HTTP/auth I/O at the client boundary. Disabling read-only behavior is not configurable.

Successful typed observations contain UTC timestamps; null rosters and missing activity entries remain unknown. Failures return categorized errors instead of synthetic zero-player snapshots. HTTP 403 does not start a refresh loop; 401 retries authentication once. Reads retry 429/502/503/504 at most twice, honoring Retry-After up to 30 seconds per wait; a longer requested wait is returned to the operator rather than retried early. There is no scheduler, historical session inference or automatic reconciliation with Captain player/check-in records.

## First live-test checklist — blocked pending explicit approval

- [ ] Obtain explicit approval for this separate live test using the designated secondary account. No primary owner-account fallback.
- [ ] Review the implementation/offline results and any outstanding limitations below.
- [ ] Confirm Captain owns the registered application and verify its personal-account/public-client settings, exact scopes and Microsoft consent display.
- [ ] Protect the operator terminal, allowlist configuration, persistent private volume and separately managed encryption keys; check service identity, ACLs, backup and recovery.
- [ ] Privately configure the designated gamertag; do not hardcode it into source or test fixtures. Begin with `selected_realm_id: null`. Choose an appropriate stable Client-Version deliberately.
- [ ] Run `check` offline. Only then enable the private manual configuration for the approved session.
- [ ] Invoke the diagnostic `login` action with private config/store paths, allowlisted `--user-id`/`--guild-id`, `--key-id` and `--allow-live`; type its terminal confirmation only after approval. The environment supplies keys. Do not pass tokens/passwords as arguments.
- [ ] Complete Microsoft sign-in/MFA in the browser as the designated account; confirm the diagnostic's verified gamertag. Missing/mismatched Xbox identity stops the session. Verify ciphertext permissions and absence of plaintext/token logs.
- [ ] With separate consent to read Realm data in that session, run `probe` with the same arguments and confirm again. Check accessible Realm count without assuming ownership or access to Coastal Craft.
- [ ] Select only an approved discovered Realm ID in the private config. Probe selected details/activity; compare a consenting member's controlled join/leave against observations. Missing/denied data remains unknown.
- [ ] Verify restart, an actual refresh cycle, 401 behavior and revocation/reauthentication. Do not confuse cached unexpired XSTS reuse with refresh validation. Never use writes to manufacture test setup.
- [ ] Record only redacted schemas/error categories and observed compatibility; disable manual configuration afterward. No deployment/merge/Discord sync without separate approval.

The `login` and `probe` actions have not been run against a real service. They require `--allow-live`, private interactive stdin/stdout and a typed action-specific confirmation. Their existence is not authorization to run them.

## Offline validation and limitations

Tests use fake HTTP transports/responses, fake clocks and synthetic credentials, plus real encryption and temporary local filesystem/ACL operations. The repository's existing test network guard remains active. No test needs a Microsoft app, a live account, Discord, MySQL or a Realm. Windows asyncio requires an internal loopback socket pair; the Codex sandbox blocked its creation, so the test suite was run outside that sandbox while preserving the offline fixture's external-network prohibition.

Run the complete repository checks using the existing environment:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check --select F main.py utils migrations scripts tests
.\.venv\Scripts\python.exe -m compileall -q main.py utils migrations scripts tests
node --test apps_script/coastal_application/test-backend.cjs
```

Latest offline review results, November 3, 2026:

| Check | Result |
| --- | --- |
| Full Python offline suite | **424 passed, 1 skipped**, 23.65 seconds; includes 126 passing Realms tests |
| Platform skip | POSIX permission test skipped on Windows; Windows ACL tests executed |
| Apps Script regression suite | Previous Phase 2 verification: **11 passed**; unchanged in this review |
| Ruff F checks and compileall, full existing paths | Passed |
| Existing environment dependency consistency | No broken requirements (`.venv` Python running existing `.audit-tools/pip --python .venv check`) |
| Python 3.12 AST syntax check for the 11 new modules/diagnostic | Passed |
| Default diagnostic `check` | Configuration valid, disabled, offline |
| Diff/whitespace checks | Passed |

The five full-suite warnings are existing upstream audioop and modal TextInput label deprecations. Linux-specific permission code must also pass existing Linux CI; Windows execution cannot certify it. No fresh online vulnerability audit or live protocol test is implied by passing offline tests. Remaining gates: actual Captain app/scope acceptance, current Bedrock headers, general-XSTS identity claim availability, ordinary-member read permissions, provider storage/backup suitability and approved host deployment. If any authentication gate fails, stop; do not substitute account credentials or an owner's token.

## Offline review findings and fixes

Reviewed on `codex/realms-phase2` starting at `d2b2dbd`, with a clean working tree. All edits remain confined to the Realms modules, diagnostic, tests and documentation. No live-account configuration/key was created. The committed example remains disabled.

| Finding | Fix and regression evidence |
| --- | --- |
| Missing/forged login handle could raise AttributeError instead of policy denial | Validate PendingLogin type before accessing its fields; clean denial without HTTP |
| Explicit re-login could overwrite an existing XUID pin if a different account presented the same expected gamertag | Load existing encrypted identity before saving a new login; require matching XUID and preserve old cache on mismatch |
| Leading/trailing control characters in returned gamertag could pass strip-based matching and reach terminal output | Reject control characters before identity output/storage |
| Authenticated but malformed encrypted payload could raise an unsanitized schema error or accept a boolean schema version | Enforce exact schema/type and map malformed payload failures to fixed StorageError without raw exception context |
| Windows ACL helper inherited the process's encryption-key/token environment unnecessarily | Pass only required OS environment and private path/control fields; canary test proves secret variables excluded |
| Windows PowerShell 5.1 UTF-8 BOM configuration was rejected | Read UTF-8 with optional BOM; offline regression covers that format |
| Disabled check did not validate fields needed for future enabled mode | Add `check --validate-enabled`, proving the disabled file remains unchanged and no live path is entered |
| Count-only discovery did not expose an ID to select for the next approved probe | Add optional private `--show-realm-ids` output with default-output privacy tests; no new endpoints |
| Fixed HTTP category alone hid useful non-secret troubleshooting data | Print numeric status/Retry-After without upstream bodies; exact-output test |

No failing offline tests remain after these fixes. The 14 additional regressions account for the increase from 410 to 424 passing tests. The private Windows guide supplies setup prompts for the app/client ID, explicitly allowed human Discord ID, guild ID and stable Bedrock version; no values were inferred from unavailable screenshots or administrator permissions. A Windows-only DPAPI provisioning procedure is documented but was not executed with real key material. No push, deployment, merge, live OAuth or Realms call was performed during this review.
