"""Offline history safety, identity review and aggregate correctness."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock

import pytest
from peewee import IntegrityError, SqliteDatabase

from migrations.realm_activity import migrate
from realms_fakes import FakeHTTP, PRINCIPAL, config, FakeTime, xbox
from utils.integrations.realms.client import RealmsClient
from utils.integrations.realms.errors import AccessDenied, HTTPFailure, ProtocolError
from utils.integrations.realms.models import Snapshot
from utils.integrations.realms.stories import parse_stories
from utils.integrations.realms.transport import AiohttpTransport, STORIES_HOST, REALMS_RP, Response
from utils.integrations.realms.xbox import XboxAuth
from utils.players import registry
from utils.players.activity import ingest, link_xbox, observed_statistics, verified_player
from utils.players.activity_models import RealmActivity
from utils.players.models import Player, Identity, ImportRecord, Participation, CheckIn
from utils.players.cog import Players
from utils.realms.runtime import RealmRuntime
from scripts.player_history_preview import preview_bundle
from test_realms_transport import Session

NOW = datetime(2026, 11, 3, 20, tzinfo=timezone.utc)
START = int((NOW - timedelta(hours=4)).timestamp())
XUID = "123456"


def payload(entries=None, xuid=XUID):
    return {"result": {"activity": {xuid: entries if entries is not None else [{"s": START, "e": START+3600}]}}}


def snapshot(entries=None, xuid=XUID, now=NOW):
    return Snapshot(parse_stories(payload(entries, xuid), now), now)


@pytest.fixture
def backend(tmp_path):
    backend = SqliteDatabase(tmp_path / "history.sqlite", pragmas={"foreign_keys": 1})
    migrate(backend, apply=True, backup_verified=True)
    with backend.connection_context():
        yield backend


def test_additive_migration_backup_and_repeat(tmp_path):
    backend = SqliteDatabase(tmp_path / "schema.sqlite")
    assert "captain_realm_activity" in migrate(backend)["missing_tables"]
    assert not backend.get_tables()
    with pytest.raises(ValueError, match="backup"):
        migrate(backend, apply=True)
    migrate(backend, apply=True, backup_verified=True)
    with backend.connection_context():
        Player.create(discord_id=123456789012345678)
    migrate(backend, apply=True, backup_verified=True)
    with backend.connection_context():
        assert Player.select().count() == 1


@pytest.mark.parametrize("s,e,reason", [
    (True, START+1, "invalid_timestamp_type"), (None, START+1, "invalid_timestamp_type"),
    ("123", START+1, "invalid_timestamp_type"), (0, START+1, "nonpositive_timestamp"),
    (START, START, "nonpositive_interval"), (START, START-1, "nonpositive_interval"),
    (START, 2**63-1, "future_timestamp"), (START*1000, (START+3600)*1000, "future_timestamp"),
    (1, START, "predates_minecraft"),
])
def test_anomalies_quarantined(s, e, reason):
    item = snapshot([{"s": s, "e": e}]).data[0]
    assert item.status == "quarantined" and item.reason == reason
    assert item.start is None and item.end is None
    assert XUID not in repr(item)


def test_identity_invalid_zero_and_snapshot_envelope():
    for identity in ("0", "01", "bad", str(2**64)):
        item = snapshot(xuid=identity).data[0]
        assert item.xuid is None and item.reason == "invalid_identity"
    for body in ({}, {"result": None}, {"result": {"activity": []}}, payload([None])):
        with pytest.raises(ProtocolError):
            parse_stories(body, NOW)
    with pytest.raises(ProtocolError):
        parse_stories(payload(), NOW.replace(tzinfo=None))
    assert parse_stories({"result": {"activity": {}}}, NOW) == ()


def test_repeated_ingest_unmatched_and_later_link(backend):
    first = ingest(snapshot(), "42")
    assert first == dict(created=1, existing=0, quarantined=0, unmatched=1)
    assert Player.select().count() == 0
    assert ingest(snapshot(now=NOW+timedelta(hours=1)), "42")["existing"] == 1
    assert RealmActivity.select().count() == 1
    p = Player.create(discord_id=123456789012345678, gamertag="Current")
    assert link_xbox(p.id, XUID, actor=999, evidence="reviewed independent evidence", gamertag="OldName") == 1
    assert RealmActivity.get().player_id == p.id
    assert Player.get_by_id(p.id).gamertag == "Current"
    assert Identity.select().where(Identity.kind == "gamertag").count() == 1
    assert not Player.get_by_id(p.id).inactive
    assert not Participation.select().count() and not CheckIn.select().count()


def test_verified_links_conflicts_and_duplicate_prevention(backend):
    p, other = Player.create(), Player.create()
    link_xbox(p.id, XUID, actor=999, evidence="independently reviewed")
    assert link_xbox(p.id, XUID, actor=999, evidence="independently reviewed") == 0
    assert Identity.select().where(Identity.kind == "xuid").count() == 1
    for player, value in ((other.id, XUID), (p.id, "234567")):
        with pytest.raises(ValueError, match="Conflicting"):
            link_xbox(player, value, actor=999, evidence="independently reviewed")
    with pytest.raises(IntegrityError):
        Player.create(xuid=XUID)
    Identity.create(player=other, kind="xuid", value=XUID, verified=True, source="legacy_conflict")
    assert verified_player(XUID) is None
    ingest(snapshot(), "42")
    assert RealmActivity.get().player_id is None


def test_quarantine_retention_repeat_and_statistics_union(backend):
    p = Player.create(xuid=XUID)
    entries = [{"s": START, "e": START+3600}, {"s": START+1800, "e": START+5400},
               {"s": START+5400, "e": START+7200}, {"s": START, "e": 2**63-1}]
    assert ingest(snapshot(entries), "42")["quarantined"] == 1
    ingest(snapshot(entries), "42")
    assert RealmActivity.select().count() == 4
    ingest(Snapshot((), NOW+timedelta(days=40)), "42")
    assert RealmActivity.select().count() == 4  # absence never purges retained history
    stats = observed_statistics(p.id, start=NOW-timedelta(days=1), end=NOW, selected_realm="42")
    assert stats["observed_seconds"] == 7200
    assert stats["recorded_intervals"] == 3 and stats["confirmed_sessions"] is None
    assert stats["merged_activity_spans"] == 1
    clipped = observed_statistics(p.id, start=datetime.fromtimestamp(START+900, timezone.utc),
                                  end=datetime.fromtimestamp(START+2700, timezone.utc))
    assert clipped["observed_seconds"] == 1800
    assert observed_statistics(p.id, start=NOW-timedelta(days=1), end=NOW, selected_realm="43")["observed_seconds"] == 0


def test_quarantine_never_silently_promoted_and_utc_normalized(backend):
    local = NOW.astimezone(timezone(timedelta(hours=-6)))
    entries = [{"s": START, "e": int((NOW+timedelta(hours=1)).timestamp())}]
    ingest(snapshot(entries, now=local), "42")
    assert RealmActivity.get().first_observed == NOW.replace(tzinfo=None)
    assert ingest(snapshot(entries, now=NOW+timedelta(hours=2)), "42")["quarantined"] == 1
    assert RealmActivity.get().status == "quarantined"


def test_verified_history_cannot_be_overwritten_by_reviewed_import(backend):
    p = Player.create(discord_id=123456789012345678)
    Identity.create(player=p, kind="xuid", value=XUID, verified=True, source="reviewed_legacy")
    data = dict(source="synthetic#entry=1", season=10, discord_id=p.discord_id,
                discord_id_verified=True, xuid="234567", xuid_verified=True)
    registry.stage([data])
    row = ImportRecord.get()
    registry.review(row.id, 999, player_id=p.id)
    with pytest.raises(ValueError, match="history"):
        registry.import_record(row.id)
    assert Player.get_by_id(p.id).xuid is None
    assert ImportRecord.get().state == "approved"


def test_invalid_verified_xuid_blocked_before_match(backend):
    assert registry.matches({"xuid": "0", "xuid_verified": True})["state"] == "conflict"


def test_link_does_not_require_optional_history_table(backend):
    RealmActivity.drop_table()
    p = Player.create()
    assert link_xbox(p.id, XUID, actor=999, evidence="independently reviewed") == 0
    assert Player.get_by_id(p.id).xuid == XUID


def test_preview_no_writes_and_cross_record_conflicts(backend):
    p = Player.create(discord_id=123456789012345678)
    records = [dict(source="a#entry=1", season=3, discord_id=p.discord_id, discord_id_verified=True, gamertag="known"),
               dict(source="b#entry=2", season=4, gamertag="Ambiguous"),
               dict(source="c#entry=3", season=5, gamertag="ambiguous"),
               dict(source="d#entry=4", season=6, gamertag="Fresh")]
    counts = registry.preview(records)
    assert counts["total_records"] == 4 and counts["existing_matches"] == 1
    assert counts["ambiguous_identities"] == 2 and counts["proposed_profiles"] == 1
    assert ImportRecord.select().count() == 0 and Player.select().count() == 1
    conflicts = [dict(records[0], xuid=XUID, xuid_verified=True),
                 dict(records[0], source="other", xuid="234567", xuid_verified=True)]
    assert registry.preview(conflicts)["conflicting_links"] == 2
    bundle = {"sources": [{"source": "synthetic", "season": 10, "header_row": 1,
        "rows": [["Gamertag", "Discord Long ID"], ["Fresh", "123456789012345679"]],
        "trusted_discord_ids": True}]}
    assert preview_bundle(bundle)["preview"]["total_records"] == 1
    assert ImportRecord.select().count() == 0


async def test_exact_stories_host_selection_and_token_audience():
    clock = FakeTime()
    token = XboxAuth(FakeHTTP(), clock=clock).parse(xbox(clock), REALMS_RP)
    auth = AsyncMock(return_value=token)
    http = FakeHTTP(Response(200, payload()))
    api = RealmsClient(http, auth, config(), PRINCIPAL, clock=lambda: NOW)
    assert (await api.stories()).data[0].status == "observed"
    method, url, kwargs = http.calls[0]
    assert method == "GET" and url == STORIES_HOST + "/api/v1.0/worlds/42/stories/playeractivity"
    assert kwargs["headers"]["Cache-Control"] == "no-cache, no-store"
    assert auth.await_args.args == (PRINCIPAL,)
    with pytest.raises(AccessDenied):
        await api.request("GET", "/api/v1.0/worlds/43/stories/playeractivity")


async def test_transport_stories_read_allowlist():
    url = STORIES_HOST + "/api/v1.0/worlds/42/stories/playeractivity"
    async with AiohttpTransport(selected_realm_id="42", session_factory=lambda **k: Session()) as transport:
        assert (await transport.request("GET", url)).status == 200
        for method, target in (("POST", url), ("PUT", url), ("GET", url + "?x=1"),
                               ("GET", url.replace("42", "43")), ("GET", url.replace("playeractivity", "settings"))):
            with pytest.raises(AccessDenied):
                await transport.request(method, target)


async def test_history_runtime_gate_cache_backoff_and_live_independence():
    settings = {"realms": {"enabled": False}, "realm_history_enabled": True}
    clock = FakeTime()
    runtime = RealmRuntime(settings, monotonic=clock)
    runtime.client = NS(stories=AsyncMock(return_value=snapshot()))
    runtime.config = config()
    first = await runtime.stories()
    assert await runtime.stories() is first and runtime.client.stories.await_count == 1
    assert runtime.view.realm is None and runtime._retry_at == 0
    clock.value += 3601
    runtime.client.stories.side_effect = HTTPFailure(429, 7200)
    with pytest.raises(HTTPFailure):
        await runtime.stories()
    assert runtime._history_retry_at == clock.value+7200
    assert runtime._retry_at == 0
    disabled = RealmRuntime({"realms": {"enabled": False}})
    with pytest.raises(AccessDenied):
        await disabled.stories()


async def test_private_activity_command_uses_shared_cog_and_confirmation(backend, monkeypatch):
    settings = {"Coastal": 100, "profiles_enabled": True, "realm_history_enabled": True}
    runtime = NS(stories=AsyncMock(return_value=snapshot()), config=config())
    bot = NS(settings=settings, sheets=NS(), get_cog=Mock(return_value=NS(runtime=runtime)))
    cog = Players(bot)
    interaction = NS(guild_id=100, response=NS(defer=AsyncMock()), followup=NS(send=AsyncMock()))
    async def database(operation):
        return operation()
    monkeypatch.setattr("utils.players.cog.database", database)
    await Players.import_activity.callback(cog, interaction, False)
    assert RealmActivity.select().count() == 0
    await Players.import_activity.callback(cog, interaction, True)
    assert RealmActivity.select().count() == 1
    bot.get_cog.assert_called_with("RealmCommands")
    assert all(call.kwargs.get("ephemeral") is True for call in interaction.followup.send.await_args_list)
    assert all(command.checks for command in (Players.import_activity, Players.xbox_link, Players.preview_history))
