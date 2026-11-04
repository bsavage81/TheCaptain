"""Preview private exported source rows, without staging/importing or production DB access.

Input JSON: {"sources":[{"season":3,"source":"...","header_row":4,
"rows":[...],"trusted_discord_ids":false}],"issues":[]}.
Defaults to an empty synthetic registry baseline; optional SQLite snapshot is read-only.
Only aggregate counts are printed. No credentials or environment configuration are read.
"""
import argparse
import json
from pathlib import Path
from peewee import SqliteDatabase
from utils.database.__database import db
from utils.players.history import parse_rows
from utils.players.models import MODELS
from utils.players.registry import preview


def preview_bundle(bundle, *, members=()):
    records = []
    issues = len(bundle.get("issues", []))
    sources = bundle.get("sources", [])
    for source in sources:
        if type(source.get("season")) is not int or not 3 <= source["season"] <= 10:
            issues += 1
            continue
        try:
            records.extend(parse_rows(source["rows"], season=source["season"], source=source["source"],
                header_row=source["header_row"], trusted_ids=source.get("trusted_discord_ids") is True))
        except (KeyError, TypeError, ValueError):
            issues += 1
    return {"preview": preview(records, members), "source_count": len(sources),
            "source_issue_count": issues, "complete": issues == 0,
            "required_approval": "Review source completeness and each identity before import"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--registry-snapshot", type=Path)
    args = parser.parse_args()
    try:
        bundle = json.loads(args.input.read_text(encoding="utf-8-sig"))
        if args.registry_snapshot:
            path = args.registry_snapshot.resolve(strict=True)
            backend = SqliteDatabase(path.as_uri() + "?mode=ro", uri=True)
        else:
            backend = SqliteDatabase(":memory:")
        db.initialize(backend)
        with backend.connection_context():
            if not args.registry_snapshot:
                backend.create_tables(MODELS)
            report = preview_bundle(bundle)
            report["registry_baseline"] = "read_only_snapshot" if args.registry_snapshot else "empty_local_registry_not_production"
            report["discord_member_snapshot_available"] = False
            print(json.dumps(report, indent=2))
    except Exception as error:
        parser.exit(1, f"Preview stopped ({type(error).__name__}); no records imported.\n")


if __name__ == "__main__":
    main()
