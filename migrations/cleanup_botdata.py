"""Reversible Captain settings cleanup. Plan by default; never deletes legacy data.

All bot writers must be stopped and external consumers reviewed before applying.
The old table remains in the same database for rollback, alongside a separate DBA backup.
"""
import argparse
import json
import os
import re
from peewee import MySQLDatabase, SqliteDatabase
from utils.database import __database as database
from utils.core_features.__constants import ROOT

ACTIVE = "botdata"
ARCHIVE = "captain_botdata_legacy"
STAGING = "captain_botdata_new"
ROLLED_BACK = "captain_botdata_clean_rollback"
CLEAN_COLUMNS = {"id", "prefix"}
LEGACY_COLUMNS = CLEAN_COLUMNS | {
    "persistent_views", "bot_spam_channel_coastal", "bot_spam_channel_aurafall",
    "bot_type", "bot_id", "server_id_aurafall", "server_id_coastal",
}


class CleanupRefused(ValueError):
    """Reviewed, non-sensitive refusal reason safe for operator output."""


class StagedBotData(database.BotData):
    class Meta:
        table_name = STAGING


def _columns(backend, table):
    return {column.name for column in backend.get_columns(table)}


def _dependencies(backend):
    names = backend.get_tables()
    for table in names:
        for fk in backend.get_foreign_keys(table):
            if table in (ACTIVE, ARCHIVE) or fk.dest_table in (ACTIVE, ARCHIVE):
                raise CleanupRefused("Settings foreign keys need manual review before any rename")
    if backend.get_views():
        raise CleanupRefused("Views exist in this schema; external dependencies need manual review")
    for table in (ACTIVE, ARCHIVE):
        if table in names:
            if backend.get_primary_keys(table) != ["id"]:
                raise CleanupRefused("Unexpected settings primary key; no schema changed")
            if any(index.name != "PRIMARY" for index in backend.get_indexes(table)):
                raise CleanupRefused("Custom settings indexes need manual review")
    if isinstance(backend, SqliteDatabase):
        for table in (ACTIVE, ARCHIVE):
            if table in names:
                ddl = backend.execute_sql("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()[0]
                if re.search(r"\bCHECK\s*\(", ddl, re.IGNORECASE):
                    raise CleanupRefused("Settings CHECK constraints need manual review")
        if backend.execute_sql("SELECT name FROM sqlite_master WHERE type='trigger'").fetchone():
            raise CleanupRefused("Triggers exist; no schema changed")
    elif isinstance(backend, MySQLDatabase):
        version = backend.execute_sql("SELECT VERSION()").fetchone()[0]
        numbers = re.match(r"(\d+)\.(\d+)\.(\d+)", version)
        if not numbers:
            raise CleanupRefused("Unrecognized database version")
        version_tuple = tuple(map(int, numbers.groups()))
        minimum = (10, 6, 1) if "MariaDB" in version else (8, 0, 0)
        if version_tuple < minimum:
            raise CleanupRefused("Cleanup requires MySQL 8+ or MariaDB 10.6.1+ for supported atomic rename behavior")
        for table in (ACTIVE, ARCHIVE):
            if table in names:
                engine = backend.execute_sql(
                    "SELECT ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s", (table,)).fetchone()
                if not engine or engine[0] != "InnoDB":
                    raise CleanupRefused("Cleanup requires InnoDB settings tables")
        checks = backend.execute_sql(
            "SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS WHERE CONSTRAINT_SCHEMA=DATABASE() AND TABLE_NAME IN ('botdata','captain_botdata_legacy') AND CONSTRAINT_TYPE <> 'PRIMARY KEY'").fetchone()[0]
        if checks:
            raise CleanupRefused("Additional settings constraints need manual review")
        for catalog in ("TRIGGERS", "ROUTINES", "EVENTS"):
            schema_column = {"TRIGGERS": "TRIGGER_SCHEMA", "ROUTINES": "ROUTINE_SCHEMA", "EVENTS": "EVENT_SCHEMA"}[catalog]
            query = f"SELECT COUNT(*) FROM information_schema.{catalog} WHERE {schema_column}=DATABASE()"
            if backend.execute_sql(query).fetchone()[0]:
                raise CleanupRefused("Triggers, routines or scheduled events exist; review dependencies before cleanup")
    else:
        raise CleanupRefused("Unsupported database backend")


def _swap(backend, source, destination, replacement):
    # All identifiers are constants owned by this module, never user-supplied SQL.
    if isinstance(backend, MySQLDatabase):
        backend.execute_sql(f"RENAME TABLE `{source}` TO `{destination}`, `{replacement}` TO `{source}`")
    else:
        # SQLite DDL is transactional. Dependencies were rejected before any rename.
        with backend.atomic():
            backend.execute_sql(f"ALTER TABLE `{source}` RENAME TO `{destination}`")
            backend.execute_sql(f"ALTER TABLE `{replacement}` RENAME TO `{source}`")


def cleanup(backend, *, apply=False, maintenance_window=False, exclusive_database=False, backup_verified=False, rollback=False):
    database.db.initialize(backend)
    with backend.connection_context():
        names = backend.get_tables()
        if ACTIVE not in names:
            raise CleanupRefused("No Captain botdata table found")
        columns = _columns(backend, ACTIVE)
        if columns not in (CLEAN_COLUMNS, LEGACY_COLUMNS):
            raise CleanupRefused("Unrecognized BotData columns; no objects will be guessed or removed")
        _dependencies(backend)
        rows = backend.execute_sql("SELECT id FROM botdata").fetchall()
        ids = [row[0] for row in rows]
        if 1 not in ids:
            raise CleanupRefused("Production row 1 must exist before cleanup or rollback")
        if STAGING in names:
            raise CleanupRefused("A staging table remains from an interrupted attempt; preserve it and review recovery")
        if rollback:
            if ARCHIVE not in names:
                if ROLLED_BACK in names:
                    return {"state": "already_rolled_back", "applied": False}
                raise CleanupRefused("No cleanup archive exists to restore")
            if columns != CLEAN_COLUMNS or ids != [1] or ROLLED_BACK in names:
                raise CleanupRefused("Unexpected rollback state; preserve all tables for manual review")
            if _columns(backend, ARCHIVE) not in (CLEAN_COLUMNS, LEGACY_COLUMNS):
                raise CleanupRefused("Unrecognized archived settings schema")
            if not backend.execute_sql(f"SELECT id FROM `{ARCHIVE}` WHERE id=1").fetchone():
                raise CleanupRefused("Archived production row is missing")
            plan = "Restore original settings table; preserve current clean settings in rollback table"
        else:
            if columns == CLEAN_COLUMNS and ids == [1]:
                return {"state": "already_clean", "applied": False, "archive_present": ARCHIVE in names}
            if ARCHIVE in names or ROLLED_BACK in names:
                raise CleanupRefused("Existing recovery tables must not be overwritten")
            plan = "Keep production id/prefix in active BotData; archive all original columns and rows"
        if not apply:
            return {"state": "planned", "applied": False, "plan": plan,
                    "active_columns": sorted(columns), "configuration_rows": len(ids)}
        if not maintenance_window or not exclusive_database or not backup_verified:
            raise CleanupRefused("Apply requires stopped writers, a verified independent backup and owner-confirmed exclusive database use")
        if rollback:
            _swap(backend, ACTIVE, ROLLED_BACK, ARCHIVE)
            return {"state": "rolled_back", "applied": True}
        # New table/copy can leave a recoverable staging table if interrupted; never auto-delete it.
        if isinstance(backend, MySQLDatabase):
            backend.execute_sql(f"CREATE TABLE `{STAGING}` (`id` INTEGER NOT NULL AUTO_INCREMENT PRIMARY KEY, `prefix` TEXT NOT NULL) ENGINE=InnoDB")
        else:
            StagedBotData.create_table(safe=False)
        backend.execute_sql(f"INSERT INTO `{STAGING}` (`id`, `prefix`) SELECT `id`, `prefix` FROM `{ACTIVE}` WHERE `id`=1")
        original = backend.execute_sql("SELECT id, prefix FROM botdata WHERE id=1").fetchone()
        copied = list(backend.execute_sql(f"SELECT id, prefix FROM `{STAGING}`").fetchall())
        if copied != [original]:
            raise CleanupRefused("Production settings copy mismatch; active settings remain unchanged")
        _swap(backend, ACTIVE, ARCHIVE, STAGING)
        return {"state": "cleaned", "applied": True, "legacy_rows_archived": len(ids)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--rollback", action="store_true")
    parser.add_argument("--backup-verified", action="store_true", help="Declare that an independent backup restore was verified")
    parser.add_argument("--maintenance-window", action="store_true", help="Declare that all writers are stopped")
    parser.add_argument("--exclusive-database", action="store_true", help="Declare external consumer review and exclusive Captain ownership")
    args = parser.parse_args()
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    try:
        result = cleanup(database.make_database(os.environ), apply=args.apply, rollback=args.rollback,
                         maintenance_window=args.maintenance_window, exclusive_database=args.exclusive_database, backup_verified=args.backup_verified)
        print(json.dumps(result, indent=2))
    except CleanupRefused as error:
        parser.exit(1, f"Settings cleanup refused: {error}\n")
    except Exception as error:
        parser.exit(1, f"Settings cleanup failed ({type(error).__name__}). No recovery table is deleted automatically. Review the runbook without printing database connection details.\n")


if __name__ == "__main__":
    main()
