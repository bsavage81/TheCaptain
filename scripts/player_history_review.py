"""Offline review preparation only: existing adapters/preview, no live DB or imports.

Input is an identity-column-only source bundle grounded against the explicit review
manifest. Only aggregates go to stdout. Private dockets require a fresh protected
directory and are never written into the tracked documentation/config directories.
"""
import argparse
from collections import defaultdict
import json
from pathlib import Path

from peewee import SqliteDatabase
from utils.database.__database import db
from utils.integrations.realms.token_store import private_permissions, reject_links
from utils.players.history import parse_rows
from utils.players.models import MODELS
from utils.players.registry import preview, record_key


def records_from_bundle(bundle, manifest):
    if manifest.get("review_only") is not True or manifest.get("import_authorized") is not False:
        raise ValueError("Explicit no-import review manifest required")
    expected = {s["batch_id"]: s for s in manifest["sources"]}
    if len(expected) != len(manifest["sources"]):
        raise ValueError("Repeated review batch ID")
    seen, records = set(), []
    headers_skipped = 0
    for source in bundle["sources"]:
        batch = source["batch_id"]
        if batch not in expected or batch in seen:
            raise ValueError("Unexpected or repeated source batch")
        option = expected[batch]
        for key in ("spreadsheet_id", "worksheet", "gid", "season", "header_row",
                    "trusted_discord_ids", "evidence_kind", "additional_source"):
            if type(source.get(key)) is not type(option.get(key)) or source.get(key) != option.get(key):
                raise ValueError("Source differs from approved review mapping")
        url = f"https://docs.google.com/spreadsheets/d/{option['spreadsheet_id']}/edit#gid={option['gid']}"
        if source["source"] != url:
            raise ValueError("Source URL/gid must preserve canonical fingerprint provenance")
        seen.add(batch)
        header = source["rows"][option["header_row"]-1]
        # Keep row locators outside the source fingerprint; use the established parser.
        for row_number, row in enumerate(source["rows"][option["header_row"]:], option["header_row"]+1):
            parsed = parse_rows([header, row], season=option["season"], source=url,
                                header_row=1, trusted_ids=option["trusted_discord_ids"])
            if not parsed:
                normalized = {str(v or "").strip().casefold() for v in row}
                headers_skipped += "timestamp" in normalized and bool(
                    normalized & {"gamertag", "what is your gamertag?"})
                continue
            record = parsed[0]
            if option["evidence_kind"] == "roster" and record["application_date"] is not None:
                raise ValueError("Roster must not invent application submissions")
            record.update(_batch_id=batch, _row=row_number, _worksheet_source=url,
                          _evidence_kind=option["evidence_kind"],
                          _additional_source=option["additional_source"])
            records.append(record)
    if seen != set(expected):
        raise ValueError("Review preview is incomplete")
    return records, headers_skipped


def prepare_review(records, *, headers_skipped=0):
    observations = defaultdict(list)
    for record in records:
        observations[record_key(record)].append(record)
    unique = {key: items[0] for key, items in observations.items()}
    trusted = defaultdict(list)
    name_groups = defaultdict(set)
    name_dates = defaultdict(set)
    for key, record in unique.items():
        if record.get("discord_id") and record.get("discord_id_verified"):
            trusted[str(record["discord_id"])].append(key)
        for kind in ("gamertag", "discord_name"):
            name = str(record.get(kind, "")).strip().casefold()
            if name:
                name_groups[kind, name].add(key)
        if record.get("application_date"):
            name_dates[record["gamertag"].strip().casefold(), record["application_date"]].add(key)
    cross = {group: keys for group, keys in name_groups.items()
             if len({unique[k]["_worksheet_source"] for k in keys}) > 1}
    cross_dates = [keys for keys in name_dates.values()
                   if len({unique[k]["_worksheet_source"] for k in keys}) > 1]
    priority_a, trusted_keys, trusted_names = [], set(), set()
    for number, (discord_id, keys) in enumerate(sorted(trusted.items()), 1):
        trusted_keys.update(keys)
        variants = {unique[k]["gamertag"].strip().casefold() for k in keys if unique[k].get("gamertag")}
        for k in keys:
            trusted_names.update(str(unique[k].get(kind, "")).strip().casefold()
                                 for kind in ("gamertag", "discord_name") if unique[k].get(kind))
        priority_a.append({"review_group": f"A-{number:03}", "discord_id": discord_id,
                          "source_fingerprints": sorted(keys),
                          "seasons": sorted({unique[k]["season"] for k in keys}),
                          "differing_gamertags": len(variants) > 1,
                          "identity_approved": False, "xbox_ownership_verified": False})
    remaining = set(unique) - trusted_keys
    remaining_groups = {group: keys & remaining for group, keys in name_groups.items()
                        if len(keys & remaining) > 1}
    name_ambiguous = set().union(*remaining_groups.values()) if remaining_groups else set()
    candidates_to_a = {key for key in remaining if any(
        str(unique[key].get(kind, "")).strip().casefold() in trusted_names
        for kind in ("gamertag", "discord_name") if unique[key].get(kind))}
    priority_b = sorted(key for key in remaining if not unique[key]["_additional_source"])
    priority_c = sorted(key for key in remaining if unique[key]["_additional_source"])
    payload_fields = ("discord_id", "discord_name", "gamertag", "application_date", "application_status")
    payload_conflicts = sum(len({json.dumps({f: r.get(f) for f in payload_fields}, sort_keys=True)
                                 for r in items}) > 1 for items in observations.values())
    summary = {
        "review_only": True, "import_authorized": False,
        "registry_baseline": "empty_local_registry_not_current_production_snapshot",
        "source_observations": len(records), "distinct_source_fingerprints": len(unique),
        "repeated_source_observations": len(records)-len(unique),
        "embedded_header_rows_excluded": headers_skipped,
        "conflicting_payload_fingerprints": payload_conflicts,
        "distinct_record_preview": preview(list(unique.values())),
        "raw_observation_preview": preview(records),
        "cross_source_name_groups": len(cross),
        "cross_source_name_candidate_records": len(set().union(*cross.values())) if cross else 0,
        "cross_source_exact_gamertag_date_groups": len(cross_dates),
        "priority_a": {"trusted_records": len(trusted_keys), "discord_id_groups": len(trusted),
                       "repeated_id_groups": sum(len(v) > 1 for v in trusted.values()),
                       "differing_gamertag_groups": sum(g["differing_gamertags"] for g in priority_a)},
        "priority_b_original_name_only_records": len(priority_b),
        "priority_c_additional_records": len(priority_c),
        "remaining_without_trusted_discord_id": len(remaining),
        "remaining_name_only_duplicate_groups": len(remaining_groups),
        "remaining_ambiguous_name_records": len(name_ambiguous | candidates_to_a),
        "name_only_candidate_records_to_priority_a": len(candidates_to_a),
        "independent_xbox_ownership_required_for_all_links": True,
    }
    private = {"summary": summary, "records_by_fingerprint": unique,
               "source_row_occurrences": {k: [{"batch_id": r["_batch_id"], "row": r["_row"]} for r in v]
                                          for k, v in observations.items()},
               "priority_a": priority_a, "priority_b": priority_b, "priority_c": priority_c,
               "name_groups": [{"kind": kind, "display_value": name, "source_fingerprints": sorted(keys),
                                "cross_source": (kind, name) in cross}
                               for (kind, name), keys in name_groups.items() if len(keys) > 1],
               "name_only_suggestions_to_a": sorted(candidates_to_a),
               "notice": "Private staff evidence only; no identity or import approval has been granted."}
    return summary, private


def write_private(directory, material):
    root = Path(__file__).resolve().parents[1]
    if directory.is_relative_to(root) and not directory.is_relative_to(root / ".test-tmp"):
        raise ValueError("Private review material must stay outside tracked repository paths")
    reject_links(directory)
    directory.mkdir()  # Refuse an existing destination and never overwrite a docket.
    private_permissions(directory, create=True)
    target = directory / "identity-review.json"
    with target.open("x", encoding="utf-8") as stream:
        json.dump(material, stream, ensure_ascii=False, indent=2)
    private_permissions(target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--private-output", type=Path)
    args = parser.parse_args()
    try:
        private_permissions(args.input)
        records, headers = records_from_bundle(json.loads(args.input.read_text(encoding="utf-8-sig")),
                                               json.loads(args.manifest.read_text(encoding="utf-8-sig")))
        backend = SqliteDatabase(":memory:")
        db.initialize(backend)
        with backend.connection_context():
            backend.create_tables(MODELS)
            summary, material = prepare_review(records, headers_skipped=headers)
        if args.private_output:
            write_private(args.private_output.resolve(), material)
        print(json.dumps(summary, indent=2))
    except Exception as error:
        parser.exit(1, f"Review preparation stopped ({type(error).__name__}); no imports or live database access.\n")


if __name__ == "__main__":
    main()
