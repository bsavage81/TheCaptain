"""Focused offline review preparation: no imports or identity approval."""
import copy
from pathlib import Path

from peewee import SqliteDatabase
import pytest

from scripts.player_history_review import records_from_bundle, prepare_review, write_private
from utils.database.__database import db
from utils.players.models import MODELS, Player, ImportRecord, Identity, Participation
from utils.players.registry import record_key


@pytest.fixture
def backend():
    backend = SqliteDatabase(":memory:")
    db.initialize(backend)
    with backend.connection_context():
        backend.create_tables(MODELS)
        yield backend


def source(batch, *, season=3, kind="application", additional=False, trusted=False):
    return dict(batch_id=batch, spreadsheet_id="synthetic-"+batch, worksheet="Audited",
                gid=0, season=season, header_row=1, evidence_kind=kind,
                trusted_discord_ids=trusted, additional_source=additional)


def bundle_source(option, rows):
    return dict(option, source=f"https://docs.google.com/spreadsheets/d/{option['spreadsheet_id']}/edit#gid=0", rows=rows)


def manifest(*sources):
    return dict(review_only=True, import_authorized=False, sources=list(sources))


def test_approved_mapping_dedup_and_roster_provenance(backend):
    app, roster = source("app", additional=True), source("roster", season=4, kind="roster", additional=True)
    h = ["Timestamp", "Gamertag"]
    bundle = {"sources": [bundle_source(app, [h, ["6/14/2017 12:00:00", "Synthetic"], h,
                                            ["6/14/2017 12:00:00", "Synthetic"]]),
                           bundle_source(roster, [["Gamertag"], ["Synthetic"]])]}
    rows, skipped = records_from_bundle(bundle, manifest(app, roster))
    assert len(rows) == 3 and skipped == 1
    assert record_key(rows[0]) == record_key(rows[1])
    assert rows[2]["application_date"] is None and rows[2]["_evidence_kind"] == "roster"
    assert rows[0]["_row"] == 2 and rows[1]["_row"] == 4
    summary, private = prepare_review(rows, headers_skipped=skipped)
    assert summary["source_observations"] == 3
    assert summary["distinct_source_fingerprints"] == 2
    assert summary["repeated_source_observations"] == 1
    assert summary["cross_source_name_groups"] == 1
    assert summary["priority_c_additional_records"] == 2
    assert len(private["source_row_occurrences"][record_key(rows[0])]) == 2
    for model in (Player, ImportRecord, Identity, Participation):
        assert model.select().count() == 0


@pytest.mark.parametrize("change", ["gid", "season", "worksheet", "source", "excluded", "missing"])
def test_mapping_is_fail_closed(change):
    option = source("approved")
    bundle = {"sources": [bundle_source(option, [["Gamertag"], ["Synthetic"]])]}
    if change == "missing":
        bundle["sources"] = []
    elif change == "excluded":
        bundle["sources"][0]["batch_id"] = "unnamed_unapproved"
    else:
        bundle["sources"][0][change] = "tampered"
    with pytest.raises(ValueError):
        records_from_bundle(bundle, manifest(option))


def test_stable_id_groups_are_proposals_not_synthetic_profile_links(backend):
    one, two, extra = source("one", trusted=True), source("two", season=4, trusted=True), source("extra", additional=True)
    header = ["Timestamp", "Gamertag", "Discord Long ID"]
    uid = "123456789012345678"
    bundle = {"sources": [bundle_source(one, [header, ["1/1/2017 12:00:00", "Before", uid]]),
                           bundle_source(two, [header, ["1/1/2018 12:00:00", "After", uid]]),
                           bundle_source(extra, [["Gamertag"], ["Before"]])]}
    rows, _ = records_from_bundle(bundle, manifest(one, two, extra))
    summary, private = prepare_review(rows)
    assert summary["priority_a"] == dict(trusted_records=2, discord_id_groups=1, repeated_id_groups=1, differing_gamertag_groups=1)
    assert summary["name_only_candidate_records_to_priority_a"] == 1
    assert summary["remaining_without_trusted_discord_id"] == 1
    assert private["priority_a"][0]["identity_approved"] is False
    assert Player.select().count() == 0 and Identity.select().count() == 0


def test_same_source_names_and_payload_conflicts_remain_reviewable(backend):
    option = source("one", trusted=True)
    header = ["entryID", "Gamertag", "Discord Long ID"]
    bundle = {"sources": [bundle_source(option, [header, ["1", "Synthetic", "123456789012345678"],
        ["1", "Changed", "123456789012345678"], ["2", "Synthetic", "223456789012345678"]])]}
    rows, _ = records_from_bundle(bundle, manifest(option))
    summary, private = prepare_review(rows)
    assert summary["conflicting_payload_fingerprints"] == 1
    assert summary["cross_source_name_groups"] == 0
    assert len(private["name_groups"]) == 1 and private["name_groups"][0]["cross_source"] is False


def test_private_material_cannot_enter_tracked_docs():
    root = Path(__file__).resolve().parents[1]
    with pytest.raises(ValueError, match="tracked"):
        write_private(root / "docs" / "never-created-private", {})
    assert not (root / "docs" / "never-created-private").exists()


def test_manifest_never_grants_import_authority():
    option = source("one")
    unsafe = copy.deepcopy(manifest(option))
    unsafe["import_authorized"] = True
    with pytest.raises(ValueError, match="no-import"):
        records_from_bundle({"sources": []}, unsafe)
