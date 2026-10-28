# New Captain database cleanup — executed October 28, 2026

Current state includes the three owner-requested identifiers restored after the initial cleanup below.

The owner supplied the connection to a newly created dedicated Captain database and exports of
botdata/administrators. No connection URI, host account, password or administrator identity is
recorded here. The original production database was not accessed or modified.

## Verified before activation

- Actual new server: MariaDB 12.3.3, InnoDB settings table, only botdata and administrators present.
- Both live tables exactly matched the owner-provided SQL exports; no unknown records were inferred.
- Encrypted TLS was verified. The provider certificate was self-signed; the owner explicitly approved
  accepting it over an encrypted connection. Runtime supports explicit database_ssl_mode=self_signed,
  defaults to verify_identity when unspecified, and refuses unencrypted operational connections.
- No other visible sessions were present in the new database at preflight/activation checks.
- Dependency/version/schema checks passed; no unknown columns, foreign keys, views, triggers,
  scheduled routines/events, custom indexes or additional settings constraints were found.
- An independent typed backup, complete table definitions and checksum were written to the local
  Git-ignored .database-backups directory. Both tables were restored into connection-scoped temporary
  MariaDB tables and their entire data compared successfully. Temporary verification tables vanished
  with the connection; no existing tables were dropped or data deleted.

## Applied and verified

- Active botdata now contains only id and prefix, one production row (ID 1, prefix %).
- Complete original settings schema/data, including both historical configuration rows, is retained
  unchanged in captain_botdata_legacy using an atomic multi-table rename.
- The existing administrators table, including the owner's discord_name column and full record,
  is byte/value-equivalent to the saved snapshot. No owner/admin record was inserted or changed.
- Only administrators, botdata and captain_botdata_legacy remain in this new database.
- Repeating cleanup preflight reports already_clean and applies nothing.
- Captain's actual initialize_database and administrator-check functions passed against the cleaned
  new database over encrypted TLS; they preserved the production prefix and administrator data.

Private backup: .database-backups/captain-before-cleanup-20261028T192159Z.json, with matching
.sha256 and post-cleanup-verification.json. These files are excluded from Git and are not fixtures
or logs. Preserve them in the owner's private backup storage. Do not commit/export their contents.

## What was not done

No original production database changes, unknown-table deletion, historical value deletion,
Discord/Sheets access, running-bot termination/restart, PR merge or deployment. Live rollback was
not executed because activation verified successfully; the complete rollback is tested offline
and the archive remains available. New code and the new database must be selected together during
an approved deployment: old code still expects the legacy columns. Use the supplied connection in
private deployment environment variables and explicitly configure database_ssl_mode=self_signed.
The read-only-by-default cleanup/rollback command and restoration runbook are in database-audit.md.

## Follow-up: retained identifiers restored

The owner requested bot_id, bot_spam_channel_coastal and server_id_coastal be added back from
botdata.sql. All three columns were added to the active table and populated from archived production
row 1. Values were compared against the original verified export backup and matched exactly.
Prefix %, every administrator value and the entire legacy archive remained unchanged. Runtime
initialization passed with the five-field model. Repeating restoration reports already_restored,
and the updated cleanup preflight reports already_clean.

A separate private before-restoration snapshot/checksum is stored in the Git-ignored backup folder
as captain-before-id-restore-20261028T193453Z.json. No credentials or record contents were committed.
No bot restart/deployment, original database change or main merge occurred.
