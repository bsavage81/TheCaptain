# Staging and rollback checklist

No live checks below were executed during implementation. Run them with a dedicated staging
Discord application, staging guilds, separate MySQL schema and synthetic copies of the Sheets.
Never use a production token, applicant records, or production Sheets for validation.

## Before startup

1. Review the local commits and `file-mapping.md`. Preserve a copy of current deployment code,
   its Python environment/lock, private config and service manager configuration outside Git.
   Record current `main` revision; the supplied baseline is `24535b9`.
2. Confirm repository identity. The local origin still says TheOldKing; verify the intended
   bsavage81/TheCaptain destination before any future push. No remote configuration was changed.
3. Install `requirements-dev.txt` into a clean Python 3.12 environment; run pip check,
   compileall and pytest. Review the dependency audit and hosted CI results when available.
4. Configure every guild/channel/role ID for staging, including legacy default overrides.
   Use `bot_type=BETA`, explicit staging owner_ids, and a dedicated MySQL schema. Test both
   a fresh schema and a copy of the existing Captain schema with synthetic rows only.
5. Prepare isolated staging service account access to files with the exact titles
   `CCS9 Realm Application` and `Coastal Markers`. Preserve worksheet names, metadata rows,
   question columns, formulas/formatting, insert positions and status values. Duplicate titles
   can be ambiguous under gspread title lookup; ensure only intended staging files are accessible.
6. Confirm only one process can write these Sheets. BETA/STABLE must not share them. Set host
   timezone deliberately. Configure Discord members/message-content intents and role hierarchy.

## Live staging checks

1. Start from a directory other than the checkout. Verify only intended extensions/cogs load,
   one selected BotData row exists, original fields/defaults persist, configured owners seed only
   an empty administrator table, and no commands sync automatically.
2. Explicitly sync only staging guild commands with a staging administrator. Check the MRP
   application command, Coastal/PBtest command sets (including every End variant), global repeat,
   and upstream jishaku. Test authorized/unauthorized tier-3 sync; cancel/timeout its confirmation.
   Global/all sync is outside this validation checklist.
3. Check avatar policy, MRP channel rejection, OP Team allow/deny (name and opted-in ID), and
   guide role intent with the owner. Do not silently broaden guide access if intent differs.
4. Complete all three application pages with synthetic data. Attempt another user's buttons/modal,
   expire a view, restart midway, double-click Start/Continue, and try a duplicate final callback.
   Verify E:S order, A:T row 3 insertion, timestamp, notification embeds/reactions and no log data.
5. Approve/deny synthetic IDs after inserting a newer application. Verify column U Yes/No and
   the intended member (username lookup, then numeric-ID fallback). Test absent member, blocked DM,
   missing invite channel and invite failure. Confirm saved decision remains visible on DM failure.
6. Test wrong guide answer then corrected case/whitespace, timeouts at first/retry/agreement waits,
   another user's message, overlapping sessions and blocked DMs. Verify both Coastal roles and
   response channel notification; reconcile partial role assignment if hierarchy blocks one role.
   Season 9 prompts/links were preserved; operators must confirm their continuing suitability.
7. Submit each of five POI commands using synthetic coordinates. Verify row 2, dimensions,
   fonts/icons/colors, prompt labels, notification routing, ownership and timeout handling.
8. Submit concurrent applications/POIs within this single process and check distinct max+1 IDs.
   Simulate transient Sheets errors and failures after successful writes; confirm no blind insert
   retry. Disconnect after a write and reconcile the possible saved row before retrying manually.
   Check notification/DM/invite partial failures and lack of applicant content in logs.
9. Restart twice, confirm temporary views expire and unrelated inherited question views never load.
   Inspect MySQL schema against the original; no migration should have occurred.

## Rollback

1. Stop the new process; ensure it cannot restart automatically or overlap another writer.
2. Snapshot the current database and Sheets before any rollback. Inspect uncertain writes and
   pending notifications/invites; record IDs rather than reposting applications. Do not delete
   valid applications or overwrite the entire Sheet with an older copy.
3. Restore the previously saved deployment code and matching dependency environment/config.
   Existing table/column and Sheet contracts remain compatible; no reverse migration is expected.
   Fresh BETA row 2 may be left in place, and original persistent_views flags were not modified.
4. Review startup before restarting the old revision: it has documented import-time bootstrap
   defects and may require its original environment. Do not assume `24535b9` runs cleanly on
   the newly pinned dependencies. Prefer a known operational deployment snapshot.
5. Verify only one writer is running. Slash commands are not automatically reverted by code
   rollback; any separately authorized staging/production command changes need an explicit
   operator sync against the reviewed target guild. Never run global sync as a rollback shortcut.
6. Reconcile saved status vs failed Discord notifications and revoke unused one-use invites.
   Preserve audit evidence without storing applicant answers in logs or repository fixtures.

## Remaining uncertainties

Discord API delivery/permissions, MySQL server auth/TLS and existing schema compatibility,
service-account authorization, current season content suitability and real Sheet formulas/formatting
require staging evidence. Multiple writers and durable exactly-once delivery are unsupported;
see `baseline.md`. No production deployment, command sync, Discord messages or production service
access took place during implementation.
