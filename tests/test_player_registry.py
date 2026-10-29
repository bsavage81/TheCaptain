"""Synthetic, network-blocked registry/import/monthly-delivery regression tests."""
from datetime import datetime
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock
import discord
from discord import app_commands
import pytest
from peewee import SqliteDatabase
from migrations.player_registry import migrate
from utils.database.__database import db
from utils.players import checkins, registry
from utils.players.history import ArchiveDiscovery, parse_rows
from utils.players.models import (CheckIn, Identity, ImportRecord, MODELS, Participation,
                                  Period, Player, Reminder)
from utils.players.cog import Players, CheckInView

UID = 123456789012345678
OTHER = 223456789012345678


@pytest.fixture
def backend(tmp_path):
    backend = SqliteDatabase(tmp_path / "registry.sqlite", pragmas={"foreign_keys": 1})
    db.initialize(backend)
    migrate(backend, apply=True, backup_verified=True)
    with backend.connection_context():
        yield backend


@pytest.fixture
def config():
    return {"Coastal": 100, "profiles_enabled": True, "checkin_enabled": True,
            "checkin_season": 10, "checkin_channel_id": 200,
            "checkin_timezone": "America/Chicago", "checkin_reminder_days": [15, 25]}


def record(**kwargs):
    return dict(source="synthetic-sheet#entry=1", season=10, gamertag="SyntheticTag",
                discord_id=UID, discord_id_verified=True, discord_name="SyntheticName",
                application_date="2026-10-01T10:00:00", application_status="approved", **kwargs)


def import_one(data=None, member=None):
    data = data or record()
    registry.stage([data])
    row = ImportRecord.get(ImportRecord.key == registry.record_key(data))
    registry.review(row.id, 999, discord_id=member)
    assert registry.import_record(row.id)
    return Player.get_by_id(ImportRecord.get_by_id(row.id).player_id)


def member(uid=UID, roles=()):
    return NS(id=uid, bot=False, roles=[NS(id=r) for r in roles], name="synthetic", display_name="synthetic", send=AsyncMock())


def cog(config, guild=None):
    bot = NS(settings=config, sheets=NS(), get_guild=Mock(return_value=guild),
             get_channel=Mock(), wait_until_ready=AsyncMock(), add_view=Mock())
    result = Players(bot)
    result.view = CheckInView(result)
    return result


def interaction(config, user=None, message=300):
    return NS(guild_id=config["Coastal"], channel_id=config["checkin_channel_id"],
        user=user or member(), message=NS(id=message),
        response=NS(defer=AsyncMock()), followup=NS(send=AsyncMock()))


def test_migration_read_only_and_backup_gate(tmp_path):
    backend = SqliteDatabase(tmp_path / "migration.sqlite")
    assert len(migrate(backend)["missing_tables"]) == len(MODELS)
    assert not backend.get_tables()
    with pytest.raises(ValueError, match="backup"):
        migrate(backend, apply=True)
    migrate(backend, apply=True, backup_verified=True)
    assert migrate(backend)["missing_tables"] == []
    with backend.connection_context():
        p = Player.create(discord_id=UID)
    migrate(backend, apply=True, backup_verified=True)
    with backend.connection_context():
        assert Player.get_by_id(p.id).discord_id == UID


def test_migration_rejects_incomplete_schema(tmp_path):
    backend = SqliteDatabase(tmp_path / "incomplete.sqlite")
    backend.execute_sql("CREATE TABLE captain_player (id INTEGER PRIMARY KEY)")
    with pytest.raises(ValueError, match="schema differs"):
        migrate(backend, apply=True, backup_verified=True)
    assert backend.get_tables() == ["captain_player"]


def test_migration_rejects_missing_unique_index(backend):
    indexes = backend.get_indexes(CheckIn._meta.table_name)
    name = next(i.name for i in indexes if i.unique)
    backend.execute_sql(f'DROP INDEX "{name}"')
    with pytest.raises(ValueError, match="uniqueness"):
        migrate(backend)


@pytest.mark.parametrize("season,headers,values", [
    (4, ["Timestamp", "Contact", "Gamertag"], ["1/2/2018 12:00:00", "private@example.invalid", "Synthetic"]),
    (5, ["Contact", "Gamertag", "Timestamp"], ["forum-user", "Synthetic", "1/2/2019 12:00:00"]),
    (8, ["entryID", "Discord Name", "Discord Long ID", "What is your Gamertag?", "Timestamp", "Approved?"],
        ["1", "Synthetic", str(UID), "Synthetic", "1/2/2022 12:00:00", "Yes"]),
    (10, ["entryID", "Timestamp", "Approved?", "What is your Gamertag?", "Discord Long ID"],
        ["1", "2026-10-01 12:00:00", "No", "Synthetic", str(UID)]),
])
def test_historical_layouts(season, headers, values):
    parsed = parse_rows([headers, values], season=season, source="synthetic", header_row=1, trusted_ids=season >= 8)
    assert len(parsed) == 1
    assert parsed[0]["application_date"]
    assert "private@example" not in json.dumps(parsed)
    assert bool(parsed[0]["discord_id_verified"]) == (season >= 8)


def test_roster_does_not_prove_current_membership(backend):
    data = parse_rows([["Band Name", "Gamertag", "Realm?"], ["Synthetic", "SyntheticTag", "Yes"]],
        season=3, source="roster", header_row=1)[0]
    p = import_one(data)
    assert p.discord_id is None
    assert p.first_application is None
    assert p.seasons.get().realm_status == "unknown"


def test_bad_and_missing_ids_require_review():
    for raw in ("1.23456789012346E+17", "1234", "12.0", "<@123456789012345678>"):
        data = parse_rows([["Gamertag", "Discord Long ID"], ["Synthetic", raw]], season=10,
                          source="synthetic", header_row=1, trusted_ids=True)[0]
        assert data["discord_id"] is None
        assert data["issues"] == ["malformed_discord_id"]
    assert registry.stable_id(str(UID)) == UID
    assert registry.stable_id("") is None


def test_import_requires_review_and_is_repeatable(backend):
    data = record()
    summary = registry.stage([data, data])
    row = ImportRecord.get()
    assert summary["existing"] == 1
    assert not registry.import_record(row.id)
    assert Player.select().count() == 0
    registry.review(row.id, 999)
    assert registry.import_record(row.id)
    assert not registry.import_record(row.id)
    registry.stage([dict(data, application_status="denied")])
    assert ImportRecord.select().count() == 1
    assert Participation.get().application_status == "approved"
    assert Identity.select().count() == 3
    assert Player.get().membership == "unknown"


def test_seasons_names_and_verified_values_preserved(backend):
    p = import_one()
    data = dict(record(), source="old-sheet#entry=2", season=3, gamertag="OldTag", discord_name="OldName", application_date="2017-01-01T10:00:00")
    import_one(data)
    p = Player.get_by_id(p.id)
    assert p.gamertag == "SyntheticTag"
    assert p.discord_name == "SyntheticName"
    assert p.first_season == 3
    assert p.first_application.startswith("2017")
    assert p.seasons.count() == 2
    assert Identity.select().where(Identity.value == "OldTag").exists()


def test_names_are_suggestions_only(backend):
    import_one()
    data = dict(record(), discord_id=None, discord_id_verified=False, gamertag="SyntheticTa")
    match = registry.matches(data)
    assert match["state"] == "review"
    data["gamertag"] = "SyntheticTag"
    assert registry.matches(data)["state"] == "review"


def test_conflicting_verified_identities_block_import(backend):
    p = import_one()
    p.xuid = "verified-xuid"
    p.save()
    second = Player.create(discord_id=OTHER, xuid="other-xuid")
    data = dict(record(), source="conflict#entry=2", xuid=second.xuid, xuid_verified=True)
    assert registry.matches(data)["state"] == "conflict"
    registry.stage([data])
    row = ImportRecord.get(ImportRecord.key == registry.record_key(data))
    registry.review(row.id, 999, player_id=p.id)
    assert registry.import_approved()["blocked"] == [row.id]
    assert ImportRecord.get_by_id(row.id).state == "approved"
    assert Player.select().count() == 2


def test_review_reject_and_confirmed_association(backend):
    data = dict(record(), discord_id=None, discord_id_verified=False)
    registry.stage([data])
    row = ImportRecord.get()
    registry.review(row.id, 999, reject=True)
    assert not registry.import_record(row.id)
    registry.review(row.id, 999, discord_id=UID)
    registry.import_record(row.id)
    assert Player.get().discord_id == UID
    assert ImportRecord.get().reviewed_by == 999
    with pytest.raises(ValueError, match="Already imported"):
        registry.review(row.id, 999, reject=True)


def test_unverified_id_does_not_link_profile(backend):
    data = dict(record(), discord_id_verified=False)
    p = import_one(data)
    assert p.discord_id is None
    assert not Identity.get(Identity.kind == "discord_id").verified


def test_checkin_atomic_unique_per_season_and_month(backend, config):
    p = import_one()
    current = checkins.period(config)
    assert checkins.record_checkin(p, UID, current)
    assert not checkins.record_checkin(p, UID, current)
    with pytest.raises(ValueError):
        checkins.record_checkin(p, OTHER, current)
    future = checkins.period(dict(config, checkin_season=11))
    assert checkins.record_checkin(p, UID, future)
    assert CheckIn.select().count() == 2


@pytest.mark.parametrize("instant,expected", [
    ("2027-01-01T05:59:59+00:00", (10, 2026, 12, 31)),
    ("2027-01-01T06:00:00+00:00", (10, 2027, 1, 1)),
    ("2026-11-01T05:00:00+00:00", (10, 2026, 11, 1)),
    ("2028-03-01T05:59:59+00:00", (10, 2028, 2, 29)),
])
def test_timezone_month_year_leap_rollover(config, instant, expected):
    assert checkins.calendar(config, datetime.fromisoformat(instant)) == expected


def test_calendar_rejects_naive_datetime(config):
    with pytest.raises(ValueError):
        checkins.calendar(config, datetime(2026, 1, 1))


def test_eligibility_is_explicit(backend, config):
    p = import_one()
    assert not checkins.eligible(p, member(), config)
    Participation.create(player=p, season=10, source="staff", realm_status="staff_eligible")
    assert checkins.eligible(p, member(), config)
    assert not checkins.eligible(p, member(), dict(config, checkin_eligible_role_id=42))
    assert checkins.eligible(p, member(roles=[42]), dict(config, checkin_eligible_role_id=42))
    assert not checkins.eligible(p, None, config)


async def test_button_restart_repeats_and_old_messages(backend, config):
    p = import_one()
    Participation.create(player=p, season=10, source="staff", realm_status="staff_eligible")
    period = checkins.period(config)
    period.message_id, period.channel_id = 300, 200
    period.save()
    first = cog(config)
    assert first.view.is_persistent()
    event = interaction(config)
    assert "You're checked in" in await first.check_in(event)
    restarted = cog(config)
    assert "already" in await restarted.check_in(event)
    assert "closed" in await restarted.check_in(interaction(config, message=301))
    event.guild_id = 999
    assert "unavailable" in await restarted.check_in(event)
    assert CheckIn.select().count() == 1


async def test_button_missing_profile_and_ineligible(backend, config):
    period = checkins.period(config)
    period.message_id, period.channel_id = 300, 200
    period.save()
    first = cog(config)
    assert "No linked" in await first.check_in(interaction(config))
    import_one()
    assert "eligibility" in await first.check_in(interaction(config))
    assert not CheckIn.select().exists()


async def test_announcement_restart_safe_claim_and_repair(backend, config):
    first = cog(config)
    channel = NS(id=200, guild=NS(id=100), send=AsyncMock(return_value=NS(id=300)),
                 fetch_message=AsyncMock(return_value=NS(edit=AsyncMock())))
    first.bot.get_channel.return_value = channel
    assert "posted" in await first.post_announcement()
    restarted = cog(config)
    restarted.bot.get_channel.return_value = channel
    assert "repaired" in await restarted.post_announcement()
    assert channel.send.await_count == 1
    assert Period.get().message_id == 300


async def test_uncertain_send_never_retried_automatically(backend, config):
    first = cog(config)
    channel = NS(id=200, guild=NS(id=100), send=AsyncMock(side_effect=RuntimeError("uncertain")))
    first.bot.get_channel.return_value = channel
    with pytest.raises(RuntimeError):
        await first.post_announcement()
    channel.send.side_effect = None
    channel.send.return_value = NS(id=300)
    assert "uncertain" in await first.post_announcement()
    assert channel.send.await_count == 1
    assert "posted" in await first.post_announcement(confirmed_absent=True)


async def test_deleted_announcement_can_be_replaced(backend, config):
    current = checkins.period(config)
    current.message_id, current.channel_id, current.announcement_state = 300, 200, "sent"
    current.save()
    first = cog(config)
    first.bot.get_channel.return_value = NS(id=200, guild=NS(id=100), send=AsyncMock(return_value=NS(id=301)),
        fetch_message=AsyncMock(side_effect=discord.NotFound(NS(status=404, reason="Not Found"), "gone")))
    assert "posted" in await first.post_announcement()
    assert Period.get().message_id == 301


async def test_reminder_failed_dm_durable_and_checked_players_skipped(backend, config):
    p = import_one()
    Participation.create(player=p, season=10, source="staff", realm_status="staff_eligible")
    user = member()
    user.send.side_effect = discord.Forbidden(NS(status=403, reason="Forbidden"), "cannot DM")
    guild = NS(get_member=Mock(return_value=user))
    current = checkins.period(config)
    first = cog(config, guild)
    await first.remind(guild, current, 15)
    await cog(config, guild).remind(guild, current, 15)
    assert user.send.await_count == 1
    assert Reminder.get().state == "failed"
    checkins.record_checkin(p, UID, current)
    await first.remind(guild, current, 25)
    assert Reminder.select().count() == 1


async def test_scheduled_latest_due_only_and_no_duplicate(backend, config, monkeypatch):
    config.update(checkin_announcements_enabled=True, checkin_reminders_enabled=True)
    guild = NS(chunked=True)
    first = cog(config, guild)
    first.post_announcement = AsyncMock()
    first.remind = AsyncMock()
    first.staff_summary = AsyncMock()
    monkeypatch.setattr(checkins, "calendar", lambda *a, **k: (10, 2026, 11, 26))
    await first.schedule.coro(first)
    assert first.remind.await_args.args[2] == 25
    first.post_announcement.assert_awaited_once()
    first.staff_summary.assert_awaited_once()


async def test_staff_report_requires_private_channel(backend, config):
    guild = NS(id=100, default_role=NS())
    first = cog(config, guild)
    channel = NS(guild=guild, permissions_for=Mock(return_value=NS(view_channel=True)), send=AsyncMock())
    first.bot.get_channel.return_value = channel
    current = checkins.period(config)
    await first.staff_summary(guild, current)
    channel.send.assert_not_awaited()
    channel.permissions_for.return_value.view_channel = False
    guild.get_member = Mock(return_value=None)
    await first.staff_summary(guild, current)
    await first.staff_summary(guild, current)
    channel.send.assert_awaited_once()


async def test_staff_checks_and_guild_restriction(config):
    first = cog(config)
    event = interaction(config)
    event.client = first.bot
    first.settings["OPTeamRole"] = 55
    with pytest.raises(app_commands.MissingRole):
        await Players.review.checks[0](event)
    event.user.roles = [NS(id=55)]
    assert await Players.review.checks[0](event)
    event.guild_id = 999
    with pytest.raises(app_commands.CheckFailure):
        await first.scope(event)
    for group in (first.profiles, first.checkin):
        for cmd in group.commands:
            if cmd.name != "status":
                assert cmd.checks, cmd.name


@pytest.mark.parametrize("changes", [{"checkin_reminder_days": [0]}, {"checkin_reminder_days": [15, 15]},
    {"checkin_timezone": "invalid"}, {"checkin_season": 0}, {"checkin_enabled": "false"},
    {"checkin_eligible_role_id": 0}, {"checkin_reminders_enabled": True}])
def test_invalid_configuration(config, changes):
    config.update(changes)
    with pytest.raises((ValueError, KeyError)):
        checkins.validate(config)


def test_discovery_reports_inaccessible_sources():
    discovery = ArchiveDiscovery(NS(), {})
    discovery._children = Mock(side_effect=PermissionError)
    result = discovery.discover()
    assert result["issues"][0]["issue"] == "inaccessible_folder"
    assert result["issues"][1]["source"] == "configured_current_applications"


def test_discovery_pagination_and_resource_key():
    request = Mock(side_effect=[NS(json=lambda: {"files": [{"id": "a"}], "nextPageToken": "next"}),
                                NS(json=lambda: {"files": [{"id": "b"}]})])
    discovery = ArchiveDiscovery(NS(client=NS(http_client=NS(request=request))), {})
    assert list(discovery._children("synthetic", "resource")) == [{"id": "a"}, {"id": "b"}]
    assert request.call_args.kwargs["params"]["pageToken"] == "next"
    assert request.call_args.kwargs["headers"] == {"X-Goog-Drive-Resource-Keys": "synthetic/resource"}


def test_source_change_does_not_silently_overwrite_review(backend):
    data = record()
    registry.stage([data])
    registry.review(ImportRecord.get().id, 999)
    summary = registry.stage([dict(data, gamertag="Changed")])
    assert summary["changed_sources_require_review"] == 1
    assert json.loads(ImportRecord.get().payload)["gamertag"] == "SyntheticTag"


def test_batch_duplicates_are_review_candidates_without_merges(backend):
    a = dict(record(), discord_id=None, discord_id_verified=False)
    b = dict(a, source="second-sheet", season=3)
    summary = registry.stage([a, b])
    assert summary["possible_duplicate_name_groups"] == 2
    assert summary["review"] == 2
    assert Player.select().count() == 0
    assert "other_source_candidates" in json.loads(ImportRecord.get(ImportRecord.key == registry.record_key(a)).note)


async def test_live_application_capture_preserves_sheet_success(backend):
    from test_captain import service
    sheets = service()
    sheets.settings = {"profiles_enabled": True, "checkin_season": 10}
    sheets.applications.spreadsheet_id = "synthetic-sheet"
    sheets.applications.id = 12
    values = [0, "SyntheticName", "SyntheticNickname", str(UID), "SyntheticTag"] + ["unused-private-answer"] * 14 + ["2026-10-01 12:00:00"]
    assert await sheets.submit_application(values) == 1
    assert Player.get().discord_id == UID
    assert Player.get().membership == "unknown"
    assert Participation.get().application_status == "unknown"
    assert "unused-private-answer" not in ImportRecord.get().payload
    await sheets.decide_application(1, "Yes")
    assert Participation.get().application_status == "approved"
    assert Player.select().count() == 1
    assert Participation.get().realm_status == "unknown"
    renamed = list(values)
    renamed[1], renamed[4] = "NewName", "NewTag"
    assert await sheets.submit_application(renamed) == 2
    assert Player.get().gamertag == "NewTag"
    assert Identity.select().where(Identity.value == "SyntheticTag").exists()
    # A subsequent decision on an old application must not revert current names.
    await sheets.decide_application(1, "Yes")
    assert Player.get().gamertag == "NewTag"


async def test_live_registry_failure_never_retries_successful_sheet_write(monkeypatch):
    from test_captain import service
    sheets = service()
    sheets.settings = {"profiles_enabled": True}
    # Missing worksheet metadata forces only the registry mirror to fail.
    assert await sheets.submit_application([0, "SyntheticName"]) == 1
    assert len(sheets.applications.inserts) == 1


async def test_opt_in_cog_registers_persistent_view(backend, config):
    first = cog(config)
    config["checkin_enabled"] = False
    await first.cog_load()
    first.bot.add_view.assert_called_once_with(first.view)
    assert first.view.is_persistent()
    first.cog_unload()


async def test_opt_in_group_registration_and_no_automatic_sync(backend, config):
    from main import TheCaptain
    from test_captain import settings, Sheet
    from utils.coastal_applications.__ca_logic import load_content
    from utils.coastal_guide.__cg_logic import GuideContent
    cfg = dict(settings(), **{k: v for k, v in config.items() if k != "Coastal"})
    cfg["checkin_enabled"] = False
    sheets = NS(initialize=AsyncMock(), application_content=load_content(Sheet()), poi_content=NS(), guide_content=GuideContent())
    bot = TheCaptain(cfg, sheets=sheets, database_initializer=Mock(return_value=NS(prefix=">")))
    await bot.setup_hook()
    await bot.setup_hook()
    names = [cmd.name for cmd in bot.tree.get_commands(guild=discord.Object(cfg["Coastal"]))]
    assert names.count("playerprofiles") == 1
    assert names.count("checkin") == 1
    assert len(bot.extensions) == 7
    await bot.close()


def test_concurrent_checkin_and_announcement_claims(backend, config):
    p = import_one()
    current = checkins.period(config)
    def write():
        with backend.connection_context():
            return checkins.record_checkin(p, UID, current)
    def claim():
        with backend.connection_context():
            return checkins.claim_announcement(current, 200)
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: write(), range(2))) == [False, True]
        assert sorted(pool.map(lambda _: claim(), range(2))) == [False, True]
    assert CheckIn.select().count() == 1


async def test_discovery_pages_yield_integration_lock():
    from test_captain import service
    sheets = service()
    sheets.client = NS(http_client=NS(request=Mock(return_value=NS(json=lambda: {"files": []}))))
    sheets._run = AsyncMock(wraps=sheets._run)
    discovery = ArchiveDiscovery(sheets, {})
    result = await asyncio.wait_for(discovery.run(), 5)
    assert result["sources"] == []
    assert sheets._run.await_count == 1


def test_authenticated_discord_name_updates_preserve_history(backend):
    p = import_one()
    registry.observe_discord(p, "NewName", 100)
    assert Player.get_by_id(p.id).discord_name == "NewName"
    assert Identity.select().where(Identity.value == "SyntheticName").exists()
    assert Identity.get(Identity.value == "NewName").verified


def test_inactive_role_excludes_and_syncs_profile_tag(backend, config):
    config["checkin_inactive_role_id"] = 547138462357258242
    p = import_one()
    user = member()
    assert checkins.eligible(p, user, config)  # No staff attestation needed.
    user.roles = [NS(id=config["checkin_inactive_role_id"])]
    assert not checkins.eligible(p, user, config)
    assert Player.get_by_id(p.id).inactive
    assert Player.get_by_id(p.id).membership == "unknown"
    user.roles = []
    assert checkins.eligible(p, user, config)
    assert not Player.get_by_id(p.id).inactive
    assert p.seasons.get().realm_status == "unknown"


def test_inactive_rule_precedes_staff_and_positive_role(backend, config):
    config.update(checkin_inactive_role_id=42, checkin_eligible_role_id=43)
    p = import_one()
    Participation.create(player=p, season=10, source="staff", realm_status="staff_eligible")
    assert not checkins.eligible(p, member(roles=[42, 43]), config)
    assert checkins.eligible(p, member(), config)
    assert not checkins.eligible(p, NS(id=OTHER, bot=True, roles=[]), config)


async def test_role_change_listener_and_restart_reconciliation(backend, config):
    config["checkin_inactive_role_id"] = 42
    p = import_one()
    before, after = member(), member(roles=[42])
    guild = NS(id=100, chunked=True, get_role=Mock(return_value=NS(id=42)),
               get_member=Mock(return_value=after))
    before.guild = after.guild = guild
    first = cog(config, guild)
    await first.on_member_update(before, after)
    assert Player.get_by_id(p.id).inactive
    after.roles = []
    await first.role_sync.coro(first)
    assert not Player.get_by_id(p.id).inactive
    # Missing/removed configured role fails closed, preserving last-known tag.
    guild.get_role.return_value = None
    assert not checkins.eligible(p, after, config)


def test_inactive_sync_preserves_departed_profiles_and_unlinked_members(backend, config):
    config["checkin_inactive_role_id"] = 42
    p = import_one()
    p.inactive = True
    p.save()
    checkins.sync_inactive(p, None, config)
    assert Player.get_by_id(p.id).inactive
    active = member(OTHER)
    inactive = member(323456789012345678, roles=[42])
    guild = NS(members=[active, inactive], get_member=Mock(return_value=None))
    assert checkins.unlinked_required(guild, config) == [OTHER]
    assert Player.select().count() == 1


async def test_inactive_button_syncs_tag_without_deleting_checkin(backend, config):
    config["checkin_inactive_role_id"] = 42
    p = import_one()
    current = checkins.period(config)
    current.message_id, current.channel_id = 300, 200
    current.save()
    first = cog(config)
    user = member()
    assert "You're checked in" in await first.check_in(interaction(config, user))
    user.roles = [NS(id=42)]
    assert "eligibility" in await first.check_in(interaction(config, user))
    assert Player.get_by_id(p.id).inactive
    assert CheckIn.select().count() == 1


async def test_report_counts_required_unlinked_members(backend, config):
    config["checkin_inactive_role_id"] = 42
    p = import_one()
    linked, unlinked, inactive = member(), member(OTHER), member(323456789012345678, roles=[42])
    guild = NS(id=100, chunked=True, members=[linked, unlinked, inactive],
               get_member=Mock(side_effect=lambda uid: linked if uid == UID else None))
    event = interaction(config)
    event.guild = guild
    first = cog(config, guild)
    await Players.report.callback(first, event)
    report = json.loads(event.followup.send.await_args.args[0])
    assert report["eligibility_basis"] == "without_inactive_role"
    assert report["eligible"] == 2
    assert report["linked_eligible"] == 1
    assert report["required_members_without_profile"] == [OTHER]
    assert report["missing"] == [[p.id, UID]]


async def test_profile_view_displays_inactive_tag(backend, config):
    config["checkin_inactive_role_id"] = 42
    p = import_one()
    user = member(roles=[42])
    guild = NS(get_member=Mock(return_value=user))
    event = interaction(config)
    event.guild = guild
    await Players.view_profile.callback(cog(config, guild), event, player_id=p.id)
    report = json.loads(event.followup.send.await_args.args[0])
    assert report["tags"] == ["inactive"]
    assert report["profile"]["inactive"] is True
