# Single-deployment verification and rollback

This is an operator checklist, not an executed deployment log. There is one production bot;
no separate BETA deployment or database is required. Offline tests use synthetic SQLite and fake
Discord/Sheets. Any manual integration checks must be separately authorized and use isolated
resources/synthetic records; do not exercise writes against production Sheets as a test.

## Before an approved rollout

1. Review the PR against current main; do not merge/deploy until the owner approves. Save current
   operational code, dependencies, private `.env`/JSON and panel settings outside Git. Verify restore.
2. Confirm repository `bsavage81/TheCaptain`, branch main and correct panel server `5ff9cb52`.
   Main now has an owner-configured panel restart workflow. Review its deployment effect before
   merging; this compatibility branch does not change panel credentials or restart the server.
3. Install locked requirements into Python 3.15; run compileall, Ruff, pytest and pip check. Review
   hosted CI/security checks and `docs/validation.md`. No live secrets belong in CI.
4. Keep the current production schema and existing row 1. Follow `database-audit.md` for a private
   backup, read-only inventory and explicit fresh-schema bootstrap if needed. Startup does no DDL.
   The reversible cleanup archives original settings rows/columns; never delete that archive or
   administrator records. Preview cleanup_botdata and verify exclusive database ownership and backup
   before its explicit apply. Coordinate schema cleanup with the new runtime; old code needs rollback. Remove production bot_type;
   a leftover non-STABLE value is intentionally rejected to avoid starting the wrong instance.
5. Preserve all configured guild/channel/role/owner IDs. PBtest is optional; retain an existing value
   if its command scope is still wanted. Verify OP Team permission intent and role hierarchy.
6. Supply the existing private Captain creds.json through the deployment's secret-file mechanism.
   Confirm it belongs to the documented dedicated account and that both Season 10 files are shared.
   Prefer configured file IDs over ambiguous duplicate titles. Do not modify their data for validation.
7. For the new owner-approved MariaDB server, configure database_ssl_mode=self_signed in private
   deployment settings; the driver still requires encrypted transport. The live cleanup has already
   completed there; do not re-import old settings over the clean table. See database-cleanup-execution.md.
   Review the confirmed Season 10 guide defaults and owner-supplied Discord logo. Confirm links are
   accessible to the intended members and Discord can retrieve the image. Refresh configurable
   signed CDN links if the supplied URL is no longer fetchable; do not invent replacement assets.
8. Ensure only one process can write these Sheets. Permanently retiring/stopping BETA is an explicit
   operator action during the maintenance window, never something this branch does automatically.
   Do not overlap old/new writers or use Git branch names as deployment-mode selectors.

## Manual checks on isolated resources, with authorization

1. Launch from another working directory. Verify production row 1 prefix, unchanged administrator
   records, six intended extensions, shutdown and reconnect behavior. No startup slash-command sync.
2. Check MRP application scope and Coastal staff/POI/guide scopes, plus optional existing PBtest scope.
   Check owner/tier-3 sync access, OP Team allow/deny, avatar policy and user-owned UI callbacks.
   Manual sync remains available; target only the reviewed test guild. Global/all sync is not a test.
3. Complete three application pages with synthetic values. Verify ownership, expiration/restart,
   duplicate callbacks, row-3 insertion, E:S answer order, timestamp and U=Yes/No review status.
   Check failed notifications/DMs and member lookup without resubmitting an uncertain write.
4. Test guide “Who knows?” with “The ARMADILLO knows”, wrong-answer retry, first/retry/agreement
   timeout, another user's messages, blocked DMs, role hierarchy and both Coastal role assignments.
   Confirm notifications say Season 10 and the new realm name; no roles when guide config is incomplete.
5. Submit each five POI variants using synthetic coordinates against isolated copied Sheets. Verify
   dimensions, row 2, 14 columns, icons/fonts/colors and notifications. Preserve Questions B1:B6.
6. Verify application title/ID selection independently, all four marker worksheets, account mismatch,
   inaccessible files and invalid metadata. Initialization failures must be clear and sanitized.
7. Check concurrent application/POI IDs within one process, worker cancellation, status-row shifts,
   timeout/partial failures, no automatic insert retry and absence of applicant answers in logs.

## Rollback

1. Owner stops the new process and prevents overlap. Capture current database/Sheet backups and
   reconcile uncertain saved rows, decisions, roles and unused invites before any retry.
2. Restore the saved operational code and matching environment/config, preserving existing data.
   The prior main supports title-configured Season 10 Sheets, but its guide is Season 9; review
   that limitation before using it. Restore `bot_type=STABLE` only if the old code requires it.
3. Physical legacy rows/columns remain in the cleanup archive; use cleanup_botdata --rollback
   with its documented prerequisites before restoring older code. Administrator records are intact. A fresh bootstrap needs
   no reverse SQL. Newly bootstrapped tables/row should be left intact unless a separate approved
   restoration plan proves they can be removed without losing data.
4. Verify one writer, the production row/prefix and current guild/channel mappings. Do not revive
   the retired deployment or use global command sync as a rollback shortcut. Any separately approved
   command publication needs an explicit reviewed operator sync.
5. Keep audit evidence in private storage without applicant content or credentials in repository logs.

MySQL server compatibility/permissions, service account sharing, real Sheet formatting/formulas,
Discord delivery and the exact live bot-retirement state remain manual verification items.
