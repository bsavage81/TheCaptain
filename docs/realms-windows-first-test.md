# Private Windows preparation and first-live-test approval

Status: **offline review only — no live OAuth or Realms access authorized**. These are operator instructions, not commands executed by Codex. The account selected by the owner is **TheCaptain4322**. That value belongs only in the operator's private configuration; library defaults, committed example configuration and synthetic tests remain account-independent.

Use `codex/realms-phase2` in TheCaptain. Do not start the bot, modify PortalBot, merge, deploy, use the primary Realm owner's credentials or accept invitations through the diagnostic. An ordinary member account is supported; ownership and Coastal Craft access are not assumed.

## Confirm the registration without authenticating

The referenced planning chat reports that a Captain app was registered with personal-account support and public client flows enabled. Its screenshots/client ID were not available as verifiable configuration in this review. Confirm these directly in the already-created Captain-owned Entra registration; do not create a duplicate merely because no ID is committed.

1. On Overview, copy **Application (client) ID**, not Directory (tenant) ID or Object ID. Verify app ownership/publisher in your private operations inventory.
2. Supported account types must accept personal Microsoft accounts; Authentication → Allow public client flows must be enabled. Pure device authorization needs no client secret or redirect URI. [Microsoft public-client configuration](https://learn.microsoft.com/en-us/entra/identity-platform/scenario-desktop-app-configuration).
3. Leave **Expose an API** alone. Defining a Captain-owned scope named XboxLive.signin does not grant Xbox permissions. Do not grant Graph permissions or add a borrowed Minecraft application ID to work around an absent Xbox entry in the portal.
4. The implementation requests `XboxLive.signin offline_access` at `https://login.microsoftonline.com/consumers/oauth2/v2.0`. Entra UI configuration alone does not prove that Xbox/Realms will accept this app/scope tuple. That remains a separately approved compatibility test. [Microsoft device protocol](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-device-code).

## Prepare the private configuration offline

Use a private interactive PowerShell terminal under your own Windows identity. Do not use terminal recording, transcription, shared screen capture or cloud-synced folders. None of the setup snippets below calls Microsoft or Realms. They contain no real client ID, Discord ID, token or key. Do not paste their private output/configuration into chat.

From the TheCaptain repository root:

```powershell
$captainPython = (Resolve-Path '.\.venv\Scripts\python.exe').Path
$captainPrivateRoot = Join-Path $env:LOCALAPPDATA 'TheCaptain-Realms-Private'
$captainConfigPath = Join-Path $captainPrivateRoot 'config\realms.private.json'
$captainKeyPath = Join-Path $captainPrivateRoot 'keys\key-one.dpapi'
$captainStorePath = Join-Path $captainPrivateRoot 'tokens'
```

Create the new private root and its config/key directories **before** writing configuration. This refuses an existing root rather than overwriting its contents/ACLs. If it exists already, inspect and validate it through a separate operator review; do not delete it or regenerate its key blindly.

```powershell
& $captainPython -c "from pathlib import Path; import sys; from utils.integrations.realms.token_store import reject_links,private_permissions; p=Path(sys.argv[1]); reject_links(p); p.mkdir(); private_permissions(p,create=True); [(q.mkdir(),private_permissions(q,create=True)) for q in (p/'config',p/'keys')]" $captainPrivateRoot
if ($LASTEXITCODE -ne 0) { throw 'Private directory preparation failed; stop.' }
```

The token directory is intentionally absent: the diagnostic creates and validates it before opening its HTTP session. Keep the keys outside that token directory and outside Git/deployment sync. All parent locations must be controlled by the operator. Windows PowerShell/.NET must be available for the store's ACL checks.

Obtain your Discord **user** ID through Discord Developer Mode → Copy User ID, and the explicitly approved **guild/server** ID through Copy Server ID. Use the human account authorized to initiate this diagnostic, not the bot ID, application ID, channel ID or role ID. Do not automatically copy every bot administrator into this allowlist. These IDs are local policy inputs; the CLI trusts the Windows operator and does not authenticate Discord merely because an ID was typed.

Choose the stable Bedrock client version visible in the intended installed stable game's title/settings screen, without joining any world. Do not use the Java version, protocol number, Preview build or the synthetic version in unit tests. Its current Realms acceptance is still unverified.

```powershell
$captainOwnerId = [UInt64](Read-Host 'Explicitly authorized human Discord user ID')
$captainGuildId = [UInt64](Read-Host 'Approved Discord guild/server ID')
$captainClientId = Read-Host 'Captain-owned Application (client) ID'
$captainVersion = Read-Host 'Stable Bedrock version, for example format major.minor.patch'
$captainConfig = @{
    version = 1
    realms = @{
        enabled = $false
        client_id = $captainClientId
        auth_owner_ids = @($captainOwnerId)
        guild_id = $captainGuildId
        account_ref = 'captain-test-member'
        expected_gamertag = 'TheCaptain4322'
        client_version = $captainVersion
        selected_realm_id = $null
    }
}
$captainConfig | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $captainConfigPath -Encoding UTF8
```

Windows PowerShell 5.1 writes a UTF-8 BOM with `-Encoding UTF8`; the diagnostic accepts that encoding. Check every enabled field while leaving the file disabled:

```powershell
& $captainPython -m scripts.realms_diagnostic check --config $captainConfigPath --validate-enabled
if ($LASTEXITCODE -ne 0) { throw 'Configuration is incomplete or invalid; stop.' }
```

This flag validates settings only, without creating a session, loading keys, changing the file or enabling the integration. A plain disabled `check` validates only the disabled document, so it is insufficient as a readiness test. Do not add keys to `botdata.settings_json`; that production schema remains unchanged.

## Provision and protect a key — operator action only

These optional local provisioning instructions generate an encryption key, not Microsoft credentials. They have **not** been executed in this review. Use a provider/organization secret manager instead if available. Do not print the key, store its plaintext beside the cache or put a key literal into shell history. Use the same Windows user/machine for provisioning and later diagnostics.

The following captures a new Fernet key directly into memory and saves only a Windows DPAPI-protected representation. It refuses to replace an existing protected key. Windows `ConvertFrom-SecureString` without an explicit AES key uses DPAPI. [Microsoft documentation](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.security/convertfrom-securestring?view=powershell-7.5).

```powershell
if (Test-Path -LiteralPath $captainKeyPath) { throw 'Key already exists; reuse or review rotation, never overwrite blindly.' }
$captainFernetKey = & $captainPython -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode('ascii'))"
if ($LASTEXITCODE -ne 0) { throw 'Key generation failed.' }
try {
    $captainSecureKey = ConvertTo-SecureString -String $captainFernetKey -AsPlainText -Force
    $captainProtectedKey = ConvertFrom-SecureString -SecureString $captainSecureKey
    $captainProtectedKey | Set-Content -LiteralPath $captainKeyPath -Encoding ASCII -NoNewline
} finally {
    Remove-Variable captainFernetKey,captainSecureKey,captainProtectedKey -ErrorAction SilentlyContinue
}
```

DPAPI user protection is tied to Windows identity/machine recovery; copying this file alone is not a portable secret backup. Establish a separately protected secret-manager backup/recovery process before live use. Do not copy the unprotected key into a document to make it portable. Losing the only key means reauthentication. Rotating a key requires both old/new key IDs until the encrypted record has been re-saved and restart-tested; generating a new unrelated key for the same existing cache will not decrypt it. Do not restore an old refresh-token backup to bypass a revoked state.

Only in the future approved diagnostic session, load the protected key into a **process-scoped** environment variable without echoing it:

```powershell
$captainSecureKey = Get-Content -LiteralPath $captainKeyPath -Raw | ConvertTo-SecureString
$captainKeyPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($captainSecureKey)
try {
    $captainFernetKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($captainKeyPointer)
    $env:CAPTAIN_REALMS_KEYS = @{ 'key-one' = $captainFernetKey } | ConvertTo-Json -Compress
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($captainKeyPointer)
    Remove-Variable captainFernetKey,captainSecureKey,captainKeyPointer -ErrorAction SilentlyContinue
}
```

Never use `setx`, user/machine-wide environment persistence, `Get-ChildItem Env:` or a secret value in CLI arguments. Clear `$env:CAPTAIN_REALMS_KEYS` when done. Windows host/debug administrators can still read the process environment/memory; DPAPI and file ACLs do not protect against a compromised trusted operator.

## First live test: request approval for login only

The next approval should be narrowly stated: **Authorize one private device-code login and Xbox identity verification for TheCaptain4322 using the Captain-owned public client, with encrypted token storage; no Realms calls.** This review does not supply that approval.

After approval, reload the private config (not a stale in-memory copy), temporarily set `realms.enabled` to true, save it privately, load the existing protected key as above, then run:

```powershell
$captainConfig = Get-Content -LiteralPath $captainConfigPath -Raw | ConvertFrom-Json
$captainConfig.realms.enabled = $true
$captainConfig | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $captainConfigPath -Encoding UTF8
& $captainPython -m scripts.realms_diagnostic login --config $captainConfigPath --user-id $captainOwnerId --guild-id $captainGuildId --store-dir $captainStorePath --key-id key-one --allow-live
```

1. Type `AUTHORIZE LOGIN` only after the explicit approval. This action contacts Microsoft and Xbox, not Realms. It does not open a browser automatically.
2. Use a private/separate browser profile to avoid silently selecting a different Microsoft account. Confirm the Microsoft verification domain, Captain's application identity and the intended account before consent/MFA. Enter account passwords only on Microsoft's own page, never into the terminal/chat.
3. The diagnostic must print `Verified configured Xbox account: TheCaptain4322`, then confirm encrypted credential saving. Missing identity claims, a different gamertag/XUID or existing differently bound credentials fail closed. Use a fresh independently bound account/cache only through reviewed setup; do not overwrite a prior identity to bypass that check.
4. Stop after this login. Report only success or the fixed error category/status; never share the one-time code, token file, environment contents or raw upstream response. A successful login does not prove any Realm is visible.
5. In a `finally` block or immediately after the run, clear the process key and re-disable the private config:

```powershell
Remove-Item Env:CAPTAIN_REALMS_KEYS -ErrorAction SilentlyContinue
$captainConfig = Get-Content -LiteralPath $captainConfigPath -Raw | ConvertFrom-Json
$captainConfig.realms.enabled = $false
$captainConfig | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $captainConfigPath -Encoding UTF8
```

An empty/denied/missing Xbox scope or failed XSTS step is a compatibility blocker to investigate, not permission to change client IDs/accounts. No owner-account fallback.

## Separate later approval: read-only discovery, then selected-Realm observations

After the login report has been reviewed, request explicit approval for the read-only probe. Re-enable the private config and reload its existing key only for that session. Keep `selected_realm_id` null for first discovery. Use:

```powershell
& $captainPython -m scripts.realms_diagnostic probe --config $captainConfigPath --user-id $captainOwnerId --guild-id $captainGuildId --store-dir $captainStorePath --key-id key-one --allow-live --show-realm-ids
```

Type `AUTHORIZE PROBE`. The optional flag prints accessible Realm IDs/names **only in the private terminal**, so an operator can choose a permitted ID; omit it for count-only output. It does not add API endpoints. Ordinary members may see no Realms or be denied some reads. Do not assume Coastal Craft is listed, grant membership automatically or switch to the owner's account.

Only after confirming an approved accessible Realm, update `selected_realm_id` in the private file to that exact numeric string, run offline `check --validate-enabled`, and repeat the approved probe for details/activity. Presence is a timestamped observation; missing data stays unknown. Stop if denied. Do not accept invitations, join the game or use mutations to prepare a test. Clear keys and disable the config afterward as above.

Remaining live gates: app/scope acceptance; general-XSTS gamertag/XUID claim availability; accepted stable Client-Version; actual ordinary-member visibility; provider storage/backup suitability. Linux permission behavior requires Linux CI. None is resolved by a mocked test or the registration screenshots.
