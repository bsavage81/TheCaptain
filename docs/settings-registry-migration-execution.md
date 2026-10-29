# Settings and registry migration — executed October 28, 2026

The owner provided the existing server `.env` privately in the local checkout and
authorized completing the database rollout. No credentials or row contents are recorded here.

## Verified backup

- Connected through the existing encrypted MariaDB 12.3.3 connection and owner-approved
  `self_signed` TLS setting. The driver enforced encrypted transport.
- Preflight found `botdata` (one row), `administrators` (one row), and
  `captain_botdata_legacy` (two rows), all InnoDB. Row 1 and the production `%` prefix existed.
- Created a consistent, independent typed backup of every table, including CREATE TABLE
  definitions and all original columns/rows, in the private Git-ignored backup directory.
- Verified the serialized backup and its SHA-256 checksum by restoring all three tables
  into connection-scoped temporary InnoDB tables and comparing all values. No existing
  live table was replaced during verification; temporary tables vanished on disconnect.

Private backup basename: `captain-before-settings-registry-20261029T021510Z.json`, with
matching `.sha256`, `.verified.json`, and `.migration-result.json` evidence. Keep these
in the owner's independent private backup storage; none is committed.

## Applied and verified

- Explicitly applied `migrations.botdata_settings` after the verified backup.
- `botdata.settings_json` now exists on row 1 and contains all 40 reviewed operational
  settings plus 19 preserved legacy settings. The document checksum matches the reviewed
  seed exactly. There is no duplicate JSON prefix; the existing SQL prefix remains `%`.
- Original typed bot identifiers were preserved, including values that differ from old
  JSON aliases. No identifier was silently replaced using ambiguous legacy settings.
- Explicitly applied `migrations.player_registry`, creating all eight registry tables
  as InnoDB with their foreign keys and uniqueness constraints.
- Compared every pre-existing row/column against the backup after migration: original
  botdata values, all administrator values and the entire legacy settings archive matched.
- Repeated both migration preflights: no settings changes and no missing registry tables.
- Ran the actual `initialize_database` using the private environment: it successfully
  loaded the operational document before returning production row 1 and preserved the prefix.
- Confirmed all eight registry tables are empty. No historical import or application
  identity capture was performed as part of migration.

## Activation and remaining checks

`profiles_enabled`, `checkin_enabled`, `checkin_announcements_enabled` and
`checkin_reminders_enabled` remain **false**. No announcement, reminder, role change,
historical import or command sync was executed. Historical-source access and identity
review still follow the registry runbook before importing real players.

The settings document is visible in the `settings_json` cell of `botdata` row 1; it is
one versioned JSON document rather than one SQL column per setting. Refresh the database
viewer or inspect `SELECT id, prefix, JSON_PRETTY(settings_json) FROM botdata WHERE id=1`.

The deployment workflow requests a restart after the execution report is published.
Its successful completion proves only that the workflow ran; it does not establish
application health or live Google access. Server startup logs must confirm full readiness.

Rollback retains the added column and registry tables. Restore settings through the
documented configuration workflow or restore the verified independent database backup
only under an explicitly authorized maintenance procedure. Do not delete historical records.
