"""Add back owner-requested identifiers from archived production row 1. Plan by default."""
import argparse
import json
import os
from peewee import MySQLDatabase, SqliteDatabase
from utils.database import __database as database
from utils.core_features.__constants import ROOT
from .cleanup_botdata import ACTIVE, ARCHIVE, CLEAN_COLUMNS, ORIGINAL_CLEAN_COLUMNS, CleanupRefused, _dependencies

FIELDS = ("bot_id", "bot_spam_channel_coastal", "server_id_coastal")


def restore(backend, *, apply=False):
    database.db.initialize(backend)
    with backend.connection_context():
        names = backend.get_tables()
        if ACTIVE not in names or ARCHIVE not in names:
            raise CleanupRefused("Both active settings and the original settings archive are required")
        columns = {column.name for column in backend.get_columns(ACTIVE)}
        if not ORIGINAL_CLEAN_COLUMNS <= columns <= CLEAN_COLUMNS:
            raise CleanupRefused("Unexpected active settings schema")
        if not {"id", *FIELDS} <= {c.name for c in backend.get_columns(ARCHIVE)}:
            raise CleanupRefused("Original production identifiers are missing from the archive")
        _dependencies(backend)
        if backend.execute_sql("SELECT id FROM botdata").fetchall() not in ([(1,)], ((1,),)):
            raise CleanupRefused("Active settings must contain only production row 1")
        quoted = ", ".join(f"`{name}`" for name in FIELDS)
        source = backend.execute_sql(f"SELECT {quoted} FROM `{ARCHIVE}` WHERE id=1").fetchone()
        if source is None or any(type(value) is not int or value < 0 or value > 2**63-1 for value in source):
            raise CleanupRefused("Archived production identifiers need review")
        existing = {}
        for name, value in zip(FIELDS, source):
            if name in columns:
                current = backend.execute_sql(f"SELECT `{name}` FROM botdata WHERE id=1").fetchone()[0]
                if current is not None and current != value:
                    raise CleanupRefused("An existing identifier differs from the archive; nothing was overwritten")
                existing[name] = current
        missing = [name for name in FIELDS if name not in columns]
        pending = [name for name in FIELDS if existing.get(name) is None]
        if not missing and not pending:
            return {"state": "already_restored", "applied": False}
        if not apply:
            return {"state": "planned", "applied": False, "add_columns": missing, "restore_fields": pending}
        if not isinstance(backend, (MySQLDatabase, SqliteDatabase)):
            raise CleanupRefused("Unsupported database backend")
        # Nullable additions make an interrupted MariaDB/MySQL DDL step safely resumable.
        # Only the known singleton is updated; conflicts are rejected above on every retry.
        for name in missing:
            backend.execute_sql(f"ALTER TABLE `{ACTIVE}` ADD COLUMN `{name}` BIGINT NULL DEFAULT NULL")
        placeholder = "%s" if isinstance(backend, MySQLDatabase) else "?"
        with backend.atomic():
            for name, value in zip(FIELDS, source):
                backend.execute_sql(f"UPDATE `{ACTIVE}` SET `{name}`={placeholder} WHERE id=1 AND `{name}` IS NULL", (value,))
            actual = backend.execute_sql(f"SELECT {quoted} FROM botdata WHERE id=1").fetchone()
            if tuple(actual) != tuple(source):
                raise CleanupRefused("Identifier restoration did not verify")
        return {"state": "restored", "applied": True, "fields": list(FIELDS)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    try:
        print(json.dumps(restore(database.make_database(os.environ), apply=args.apply), indent=2))
    except CleanupRefused as error:
        parser.exit(1, f"Restoration refused: {error}\n")
    except Exception as error:
        parser.exit(1, f"Identifier restoration failed ({type(error).__name__}); inspect the preserved archive before retrying.\n")


if __name__ == "__main__":
    main()
