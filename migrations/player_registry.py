"""Read-only preflight by default. Additive DDL requires approval and verified backup."""
import argparse
import json
import os
from peewee import MySQLDatabase
from utils.database.__database import db, make_database
from utils.players.models import MODELS
from utils.core_features.__constants import ROOT


def migrate(backend, *, apply=False, backup_verified=False):
    db.initialize(backend)
    with backend.connection_context():
        existing = set(backend.get_tables())
        missing = []
        for model in MODELS:
            name = model._meta.table_name
            if name not in existing:
                missing.append(name)
            else:
                if isinstance(backend, MySQLDatabase):
                    engine = backend.execute_sql(
                        "SELECT ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s",
                        (name,)).fetchone()
                    if not engine or str(engine[0]).casefold() != "innodb":
                        raise ValueError("Registry tables require InnoDB transaction support")
                columns = {c.name for c in backend.get_columns(name)}
                if columns != {f.column_name for f in model._meta.sorted_fields}:
                    raise ValueError("Existing registry schema differs; operator review required")
                indexes = backend.get_indexes(name)
                required = [(f.column_name,) for f in model._meta.sorted_fields if f.unique]
                required += [tuple(model._meta.fields[n].column_name for n in fields)
                             for fields, unique in model._meta.indexes if unique]
                if any(not any(i.unique and tuple(i.columns) == r for i in indexes) for r in required):
                    raise ValueError("Registry uniqueness constraints differ; operator review required")
        if apply:
            if not backup_verified:
                raise ValueError("Verify an independent backup before applying registry DDL")
            if isinstance(backend, MySQLDatabase):
                backend.execute_sql("SET SESSION default_storage_engine=InnoDB")
            backend.create_tables(MODELS, safe=True)
        return {"missing_tables": missing, "applied": apply,
                "plan": "Create missing registry tables only; preserve all existing data"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup-verified", action="store_true")
    args = parser.parse_args()
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    try:
        print(json.dumps(migrate(make_database(os.environ), apply=args.apply,
                                 backup_verified=args.backup_verified), indent=2))
    except Exception as error:
        parser.exit(1, f"Registry migration stopped ({type(error).__name__}); inspect schema and backup.\n")


if __name__ == "__main__":
    main()
