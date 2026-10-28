"""Source-compatible consolidation preflight and safe fresh-schema bootstrap.

Default is read-only. --apply is an explicit operator action; no destructive SQL exists.
No credentials are loaded on import. Output includes only schema and row-presence metadata.
"""
import argparse
import json
import os
from utils.database import __database as database
from utils.core_features.__constants import ROOT


def inventory(backend):
    database.db.initialize(backend)
    with backend.connection_context():
        names = backend.get_tables()
        objects = {name: [column.name for column in backend.get_columns(name)] for name in names}
        production = retired = False
        if "botdata" in names and "id" in objects["botdata"]:
            production = database.BotData.select(database.BotData.id).where(database.BotData.id == 1).exists()
            retired = database.BotData.select(database.BotData.id).where(database.BotData.id == 2).exists()
        relationships = {name: [dict(column=fk.column, target_table=fk.dest_table, target_column=fk.dest_column)
                                for fk in backend.get_foreign_keys(name)] for name in names}
        return {"tables": objects, "relationships": relationships,
                "production_row_present": production, "legacy_row_2_present": retired}


def migrate(backend, *, apply=False):
    before = inventory(backend)
    names = before["tables"]
    for name, model in database.tables.items():
        if name in names:
            missing = set(model._meta.fields) - set(names[name])
            if missing:
                raise ValueError(f"Existing {name} schema is incomplete; restore/review missing columns before migration")
    database.db.initialize(backend)
    with backend.connection_context():
        if "botdata" in names and not before["production_row_present"] and database.BotData.select().exists():
            raise ValueError("No production row 1; nonempty legacy table needs owner-reviewed restoration. No records changed.")
        if not apply:
            return {**before, "applied": False, "plan": "Keep existing row 1 unchanged; create missing Captain tables and a default row 1 only for a fresh/empty table. Preserve every legacy row, column and permission record."}
        backend.create_tables(list(database.tables.values()), safe=True)
        with backend.atomic():
            database.ensure_production_row()
        return {**before, "applied": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Explicit additive bootstrap; default is read-only preflight")
    args = parser.parse_args()
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    try:
        result = migrate(database.make_database(os.environ), apply=args.apply)
        print(json.dumps(result, indent=2))
    except Exception as error:
        # Database driver exception strings may contain connection data. Do not print them.
        parser.exit(1, f"Database preflight/migration failed ({type(error).__name__}). Review the schema inventory and production row 1 using an authorized database tool.\n")


if __name__ == "__main__":
    main()
