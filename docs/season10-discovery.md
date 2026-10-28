# Season 10 discovery — October 28, 2026

Baseline: main `646413257f0a8670dad9e3611c9fab2d8e689108`. Clean worktree. Origin is
bsavage81/TheCaptain; PortalBot is read-only. No applicable AGENTS.md found. Latest main already
contains configurable Season 10 title defaults; preserve that change. Existing offline suite:
31 passed, 1 failed because the title-selection test still expects Season 9 names.

| Candidate | Classification | Decision |
| --- | --- | --- |
| Applications, guide, all five POI commands | Required Captain functionality | Keep names, permissions, flow and storage contracts |
| MRP guild / CoastalMRP channel | Shared infrastructure still in use | Keep Realm Portal application entry and member lookup |
| OP Team role, Coastal destination IDs | Required Captain functionality | Keep all configured IDs and named-role policy; no evidence IDs changed |
| PBtest guild ID | Shared infrastructure / uncertain operational use | Keep existing configured scope; make optional so production needs no test guild |
| Administrators table / tier >=3 / jishaku | Shared infrastructure still in use | Keep owner fallback and manual sync; do not delete permission records |
| Repeat command | Uncertain operational use | Keep existing public command; origin alone is not evidence it is unused |
| bot_type row routing | Confirmed retired deployment machinery | Pin production to row 1; reject retired BETA settings rather than silently redirecting an old instance |
| BotData unused columns and row 2 | Runtime-unused; external consumers unknown | Preserve physically; propose cleanup only after owner approval |
| DATA constant, unused management imports, empty events package | Confirmed unused code | Remove after reference search |
| Root workflows/ duplicate security definitions | Confirmed inactive examples | Remove; active CI lives in .github/workflows |
| sentry_dsn loader support | Confirmed unused setting | Remove active handling; no telemetry exists |
| !archive/ including Aurafall, blacklist/profile/tag code | Historical source | Preserve byte-for-byte; exclude from loading and dependency inference |
| _config.yml and .deepsource.toml | Possible external Pages/DeepSource consumers | Keep pending owner review |
| Local images and daily-question text | Historical assets; external use unknown | Preserve; not runtime dependencies |

Active database reads are BotData.prefix at startup and Administrators.discordID/TierLevel for
permissions. Previous STABLE selects row 1, BETA row 2; no source evidence that any other BotData
fields drive live routing. Guild/channel/role routing is JSON configuration, not those legacy columns.
Archive-only references mention MRP_Blacklist_Data, PortalbotProfile and Tag models; physical tables
and external consumers cannot be determined without an authorized database inventory. No live
MySQL/Google/Discord access is needed or permitted for this source-based audit.

Guide content is hardcoded rather than sourced from Sheets. Questions B1:B6 belongs to POI prompts,
so no guide cell mapping can safely be inferred. Season 9 links/question/answer/logo need review.
The confirmed new realm name is Coastal Craft Season 10: The Mighty Mesa Reborn. Owner has been
asked for current guide content; no replacement URLs, cells or Discord IDs will be invented.

Deployment remains manual on main. No panel API key, restart workflow or bot shutdown is part of
this task. A single production writer must own each Sheet; retiring BETA is an operator action,
not something this branch does to running services.
