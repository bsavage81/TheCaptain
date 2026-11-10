# Realms Pro endpoint investigation

Inspected 2026-11-09. Research only; no bot, production configuration, database,
credentials, or Realm settings changed. Historical archive research remains deferred.

## Evidence and verification boundary

The owner signed into Minecraft.net directly. The requested dashboard rendered
Coastal Craft's live gauges and historical table successfully. Its normal page
requests ran in the browser; no standalone authenticated API probes were made,
no browser credentials were extracted, and no HTTP status codes were captured.
Live dashboard polling was paused after inspection.

Public application source establishes the requests below. They are absent from
the existing Phase 5 inventory in `realms-api-capabilities.md`. Successful owner
dashboard access does **not** establish that TheCaptain4322, an invited account,
can access these APIs.

## New telemetry endpoints

Base: `https://frontend.realms.minecraft-services.net`

| Method and path | Parameters | Client-consumed response structure |
| --- | --- | --- |
| GET `/api/v1.0/telemetry/metrics/available` | None | `result.metrics`: array of objects with `key`; `result.windows`: array of duration strings |
| GET `/api/v1.0/telemetry/worlds/{id}/metrics/live` | Repeated `names` query parameters | `result.realmOnline`: boolean; `result.values`: object keyed by requested metric names |
| GET `/api/v1.0/telemetry/worlds/{id}/metrics` | Repeated `names`; required `window`; optional `aggregation` | `result.timestamps`: array; `result.series`: object mapping metric names to parallel value arrays |

Known metric keys: `server.cpu`, `server.memory`, `server.tick-time`,
`server.players`. CPU and memory are displayed as percentages, tick time in
milliseconds, and players as a concurrent count. The UI handles numeric values
and historical `null` values (displayed as Offline). Exact timestamp wire type
was not independently captured: the client passes timestamps directly to
`new Date(timestamp)` without multiplying by 1,000. Do not assume epoch seconds.
The client also defines an internal `datetime` key; it is excluded from fallback
metric requests and should not be assumed to be a supported server metric.

Supported client window allowlist: `PT30M`, `PT1H`, `P1D`, `P7D`, `P28D`.
The last is labeled **Last Month**, meaning 28 days in the request, not a calendar
month. This proves the offered query range, not guaranteed retention or complete
coverage. The dashboard's 30-minute view displayed approximately one-minute
samples. Resolution and aggregation for longer windows remain unverified.
The wrapper supports `aggregation`, but the dashboard caller omits it; accepted
values and server defaults are unknown.

Example request shape (not executed outside the browser):

```text
GET /api/v1.0/telemetry/worlds/{id}/metrics?names=server.cpu&names=server.memory&names=server.tick-time&names=server.players&window=PT30M
```

## Authentication and headers

The telemetry functions pass the site's Realms token as `authorization`:
`XBL3.0 x=<user-hash>;<XSTS-token>`. Its production relying party is
`https://pocket.realms.minecraft.net/`, matching The Captain's existing Realms
audience. The generic helper adds `content-type: application/json` and optionally
`X-WEB-PREAUTH-SECRET` if the site's preauth cookie exists. Whether that optional
web header is required by these endpoints is untested; do not copy browser cookies
or token storage into the bot. Telemetry wrappers do not explicitly add
`Client-Version` or `x-xbl-contract-version`.

The same bundle reveals another GET absent from the inventory:
`https://bedrock.frontendlegacy.realms.minecraft-services.net/worlds/{id}/configuration/tier`.
It uses Realms authorization, `Client-Version: 1.21.7` (the website's bundled
constant), and `x-xbl-contract-version: 2`. The client reads
`playerCount.current` or `playerCount.defaultValue` to determine capacity.
Other fields and access restrictions remain unverified. This old-looking web
client version is evidence of website behavior, not a recommendation to change
The Captain's version header.

## Observed dashboard behavior and cautions

- Live metrics refresh every five seconds. The client stops polling when the
  server reports offline and has bounded handling of repeated errors.
- The historical page explicitly warns that recent data may take **up to ten
  minutes** to become available; historical views require refreshing.
- The latest historical row displayed Offline while live gauges showed an
  online server and players. The chart rendered that row at zero. Therefore a
  missing/recent/null sample must not independently be treated as a confirmed
  outage or a real zero-valued measurement.
- Historical tables contain all four metrics even when the chart selects one.
  A CSV/data download control is present; no download was necessary.
- No individual identities, joins, departures, or session intervals occur in the
  client-consumed telemetry schema. Aggregate player counts cannot reconstruct
  individual playtime. Nothing here changes the Stories accuracy findings.

## Value to The Captain and remaining gate

These endpoints could support a server-health panel, load trends, historical
concurrency charts, and capacity reporting. Preserve live player observations
as the primary source of individual session estimates. Keep null/missing metrics
distinct from zero, preserve source timestamps, show publication delay, and avoid
inferring exact session durations or TPS from aggregate tick-time samples.

Before implementation, perform a separately bounded read-only access check with
TheCaptain4322 using the established protected credential-isolation procedure.
Confirm permissions, actual HTTP statuses/schema/timestamp type, units, limits,
and longer-window resolution. Owner-only authorization remains a possible
blocker; do not introduce owner credentials, new permissions, or automated
collection based on this research alone. No deployment is part of this task.

## Primary sources

- [Inspected dashboard](https://www.minecraft.net/en-us/msaprofile/realms/bedrockpro/metrics?realmid=35868436)
- [Official Realms Pro product page](https://www.minecraft.net/en-us/store/realms-pro)
- [Official launch article, published November 9](https://www.minecraft.net/ja-jp/article/introducing-realms-pro)
- [Public application bootstrap](https://www.minecraft.net/msaprofilejs/msaapps.js)
- [Public API/authentication bundle](https://www.minecraft.net/msaprofilejs/4b0ceb1d0f5e001c558e_03112026_1141/5900.chunk.b153e412f9523561e29e.js)
- [Public metrics UI bundle](https://www.minecraft.net/msaprofilejs/4b0ceb1d0f5e001c558e_03112026_1141/1835.chunk.dce6232467ebde88c426.js)
- [Public Realm state/model bundle](https://www.minecraft.net/msaprofilejs/4b0ceb1d0f5e001c558e_03112026_1141/59.chunk.7df9cc10d3c5702915ed.js)

Public assets were downloaded without authentication into ignored scratch space.
These are undocumented client APIs and may change independently of the bot.
