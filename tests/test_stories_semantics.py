"""Synthetic semantic counterexamples; these do not establish live API behavior."""
from datetime import datetime, timedelta, timezone

from peewee import SqliteDatabase
import pytest

from utils.database.__database import db
from utils.integrations.realms.models import Snapshot
from utils.integrations.realms.stories import parse_stories
from utils.players.activity import ingest, observed_statistics
from utils.players.activity_models import RealmActivity
from utils.players.models import Player, Identity

NOW = datetime(2026, 11, 3, 22, tzinfo=timezone.utc)
START = int((NOW-timedelta(hours=2)).timestamp())
XUID = "123456"


def story(entries, observed=NOW):
    body = {"result": {"activity": {XUID: entries}}}
    return Snapshot(parse_stories(body, observed), observed)


@pytest.fixture
def backend():
    backend = SqliteDatabase(":memory:")
    db.initialize(backend)
    with backend.connection_context():
        backend.create_tables([Player, Identity, RealmActivity])
        player = Player.create(xuid=XUID)
        yield player


def statistics(player, start=NOW-timedelta(days=1), end=NOW):
    return observed_statistics(player.id, start=start, end=end, selected_realm="42")


@pytest.mark.parametrize("end", [None, 0, -1, 2**63-1, int(NOW.timestamp())+3600])
def test_possible_open_markers_remain_quarantined_not_assumed_online(end):
    entry = story([{"s": START, "e": end}]).data[0]
    assert entry.status == "quarantined"
    assert entry.start is None and entry.end is None
    assert "online" not in entry.reason


def test_finite_end_does_not_establish_disconnection_or_current_presence(backend):
    # Could be a rolling active-session endpoint in a hypothetical API.
    entry = story([{"s": START, "e": int(NOW.timestamp())}]).data[0]
    assert entry.status == "observed"
    ingest(Snapshot((entry,), NOW), "42")
    result = statistics(backend)
    assert result["observed_seconds"] == 7200
    assert result["confirmed_sessions"] is None
    assert not hasattr(entry, "online")


def test_rolling_ends_do_not_double_count_but_interval_count_is_not_sessions(backend):
    for offset in (600, 1200, 1800):
        ingest(story([{"s": START, "e": START+offset}]), "42")
    result = statistics(backend)
    assert result["observed_seconds"] == 1800  # union, not 600+1200+1800
    assert result["recorded_intervals"] == 3
    assert result["merged_activity_spans"] == 1
    assert result["confirmed_sessions"] is None


def test_later_shorter_end_cannot_retract_prior_immutable_observation(backend):
    ingest(story([{"s": START, "e": START+1800}]), "42")
    ingest(story([{"s": START, "e": START+600}], observed=NOW+timedelta(minutes=1)), "42")
    # Evidence is retained; the model has no documented upstream revision/session ID.
    # Coverage is not automatically a corrected actual-playtime total.
    assert statistics(backend)["observed_seconds"] == 1800
    assert RealmActivity.select().count() == 2


def test_hour_bins_can_overstate_independently_known_playtime(backend):
    actual_join, actual_leave = START+600, START+1200
    ingest(story([{"s": START, "e": START+3600}]), "42")
    assert actual_leave-actual_join == 600
    assert statistics(backend)["observed_seconds"] == 3600
    assert statistics(backend)["coverage"] == "incomplete_unverified_stories"


def test_unknown_publication_delay_and_missing_snapshots_never_delete_history(backend):
    assert statistics(backend)["observed_seconds"] == 0
    assert statistics(backend)["confirmed_sessions"] is None  # zero retained coverage, not proof of zero play
    ingest(story([{"s": START, "e": START+600}], observed=NOW+timedelta(days=2)), "42")
    ingest(Snapshot((), NOW+timedelta(days=3)), "42")
    assert statistics(backend)["observed_seconds"] == 600
    assert RealmActivity.select().count() == 1


def test_overlapping_and_adjacent_records_do_not_prove_connection_count(backend):
    ingest(story([{"s": START, "e": START+600}, {"s": START+300, "e": START+900},
                  {"s": START+900, "e": START+1200}]), "42")
    result = statistics(backend)
    assert result["observed_seconds"] == 1200
    assert result["recorded_intervals"] == 3 and result["merged_activity_spans"] == 1
    assert result["confirmed_sessions"] is None


def test_clock_tolerance_is_not_permission_to_count_future_time(backend):
    end = int(NOW.timestamp())+120
    assert story([{"s": START, "e": end}]).data[0].status == "observed"
    ingest(story([{"s": START, "e": end}]), "42")
    assert statistics(backend)["observed_seconds"] == 7200  # clipped at requested NOW
    assert statistics(backend, end=NOW+timedelta(seconds=120))["observed_seconds"] == 7320


def test_utc_daily_windows_clip_across_midnight_without_losing_gap(backend):
    midnight = datetime(2026, 11, 3, tzinfo=timezone.utc)
    first = int((midnight-timedelta(minutes=10)).timestamp())
    ingest(story([{"s": first, "e": first+1200},
                  {"s": first+1800, "e": first+2400}]), "42")
    result = statistics(backend, start=midnight, end=midnight+timedelta(days=1))
    assert result["observed_seconds"] == 1200
    assert result["merged_activity_spans"] == 2
