"""Consolidate operational configuration on botdata row 1. Preview by default.

Uses only the existing database connection environment. Never reads Google credentials,
starts Discord, modifies the original configuration file or prints setting values.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
from peewee import MySQLDatabase, SqliteDatabase
from utils.configuration import COLUMN, SEED, import_document, validate_document
from utils.core_features.__constants import ROOT
from utils.database.__database import make_database


def fingerprint(document):
    return hashlib.sha256(json.dumps(document, sort_keys=True).encode()).hexdigest()


def migrate(backend, source=None, *, apply=False, backup_verified=False,
            replace_existing=False, set_key=None, value=None):
    if not isinstance(backend, (MySQLDatabase, SqliteDatabase)):
        raise ValueError("Unsupported database engine")
    with backend.connection_context():
        if "botdata" not in backend.get_tables():
            raise ValueError("Run the existing single_production migration first")
        if backend.get_primary_keys("botdata") != ["id"]:
            raise ValueError("Unexpected botdata primary key")
        if isinstance(backend, MySQLDatabase):
            engine = backend.execute_sql("SELECT ENGINE FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s", ("botdata",)).fetchone()
            if not engine or str(engine[0]).casefold() != "innodb":
                raise ValueError("Configuration updates require InnoDB transactions")
        columns = {c.name for c in backend.get_columns("botdata")}
        if not {"id", "prefix"} <= columns:
            raise ValueError("Existing botdata schema requires review")
        existing_row = backend.execute_sql("SELECT prefix FROM botdata WHERE id=1").fetchone()
        if existing_row is None:
            raise ValueError("Restore the verified production row 1 before importing settings")
        if not isinstance(existing_row[0], str) or not existing_row[0].strip():
            raise ValueError("Production prefix requires review")
        original = backend.execute_sql("SELECT settings_json FROM botdata WHERE id=1").fetchone()[0] if COLUMN in columns else None
        old = validate_document(json.loads(original)) if original is not None else None
        if set_key is not None:
            if old is None or source is not None or set_key not in old["settings"]:
                raise ValueError("Update requires existing settings and one supported key")
            document = json.loads(json.dumps(old))
            document["settings"][set_key] = value
            validate_document(document)
            prefix = existing_row[0]
        else:
            source = json.loads(SEED.read_text(encoding="utf-8")) if source is None else source
            document, requested_prefix = import_document(source)
            prefix = existing_row[0] if requested_prefix is None else requested_prefix
        changed = sorted(key for key in document["settings"] if old is None or old["settings"].get(key) != document["settings"][key])
        conflicts = old is not None and fingerprint(old) != fingerprint(document)
        if (conflicts or prefix != existing_row[0]) and not replace_existing:
            # Preview remains useful for reviewing conflicts without allowing writes.
            if apply:
                raise ValueError("Existing settings differ; review preview and explicitly allow replacement")
        result = {"applied": False, "add_column": COLUMN not in columns,
                  "changed_keys": changed, "legacy_keys_preserved": len(document["legacy_settings"]),
                  "prefix_changed": prefix != existing_row[0], "requires_replace_existing": bool(conflicts or prefix != existing_row[0]),
                  "settings_sha256": fingerprint(document)}
        if not apply or original is not None and not conflicts and prefix == existing_row[0]:
            return result
        if not backup_verified:
            raise ValueError("Verify an independent backup before applying configuration changes")
        if COLUMN not in columns:
            kind = "LONGTEXT" if isinstance(backend, MySQLDatabase) else "TEXT"
            backend.execute_sql(f"ALTER TABLE botdata ADD COLUMN settings_json {kind} NULL")
        placeholder = "%s" if isinstance(backend, MySQLDatabase) else "?"
        with backend.atomic():
            # Compare both settings and prefix so concurrent operator edits are not lost.
            binary = "BINARY " if isinstance(backend, MySQLDatabase) else ""
            predicate = "settings_json IS NULL" if original is None else f"{binary}settings_json={placeholder}"
            parameters = [json.dumps(document, sort_keys=True), prefix, existing_row[0]]
            if original is not None:
                parameters.append(original)
            cursor = backend.execute_sql(f"UPDATE botdata SET settings_json={placeholder}, prefix={placeholder} "
                f"WHERE id=1 AND {binary}prefix={placeholder} AND {predicate}", parameters)
            if cursor.rowcount != 1:
                raise ValueError("Settings changed concurrently; rerun preview without overwriting")
            saved = backend.execute_sql("SELECT settings_json, prefix FROM botdata WHERE id=1").fetchone()
            if fingerprint(json.loads(saved[0])) != fingerprint(document) or saved[1] != prefix:
                raise ValueError("Settings verification failed")
        return dict(result, applied=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", help="Existing server botconfig.json or versioned settings document; default is the reviewed seed")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup-verified", action="store_true")
    parser.add_argument("--replace-existing", action="store_true")
    parser.add_argument("--set", dest="set_key", help="One operational key to update; preview by default")
    parser.add_argument("--value", help="New JSON value for --set")
    args = parser.parse_args()
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    try:
        if (args.set_key is None) != (args.value is None):
            raise ValueError("Supply --set and --value together")
        source = json.loads(Path(args.config).read_text(encoding="utf-8-sig")) if args.config else None
        result = migrate(make_database(os.environ), source, apply=args.apply,
            backup_verified=args.backup_verified, replace_existing=args.replace_existing,
            set_key=args.set_key, value=json.loads(args.value) if args.set_key else None)
        print(json.dumps(result, indent=2))
    except Exception as error:
        parser.exit(1, f"Settings migration stopped ({type(error).__name__}). Review the configuration, schema, backup and explicit replacement flags. No settings values were logged.\n")


if __name__ == "__main__":
    main()
