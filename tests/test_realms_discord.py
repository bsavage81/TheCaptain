import asyncio
import copy
from dataclasses import asdict
from datetime import datetime, timezone
import json
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock

import discord
import pytest

from realms_fakes import config, FakeTime
from utils.integrations.realms.configuration import from_bot_settings
from utils.integrations.realms.errors import ConfigurationError, ReauthRequired
from utils.integrations.realms.models import Activity, Member, Realm, Snapshot
from utils.realms.cog import RealmCommands, permitted, render, setup
from utils.realms.runtime import Observation, RealmRuntime


def settings():
    values = asdict(config())
    values["auth_owner_ids"] = list(values["auth_owner_ids"])
    values.pop("guild_id")
    return {"Coastal": 202, "CoastalOPTeam": 404, "realms": values}


def interaction(*, guild=202, roles=(404,)):
    return NS(guild_id=guild, guild=NS(id=guild), user=NS(id=505, roles=[NS(id=r) for r in roles]),
              response=NS(send_message=AsyncMock(), defer=AsyncMock(), is_done=lambda: False),
              followup=NS(send=AsyncMock()))


def view(players=(), *, available=True):
    now = datetime(2030, 1, 1, tzinfo=timezone.utc)
    return Observation(Snapshot(Realm("42", "Synthetic Realm", "OPEN", None), now),
                       Snapshot(Activity("42", players), now), True, available)


@pytest.mark.parametrize("kind", ["status", "players", "refresh"])
@pytest.mark.parametrize("reason", ["missing_role", "other_guild", "dm", "missing_config", "administrator_only"])
async def test_all_commands_check_current_db_role_and_guild(kind, reason):
    bot = NS(settings=settings())
    runtime = NS(observe=AsyncMock())
    ctx = interaction()
    if reason in {"missing_role", "administrator_only"}:
        ctx.user.roles = []
        ctx.user.guild_permissions = NS(administrator=True)
    elif reason == "other_guild":
        ctx.guild_id = 999
        ctx.guild.id = 999
    elif reason == "dm":
        ctx.guild = None
        ctx.guild_id = None
    else:
        bot.settings.pop("CoastalOPTeam")
    cog = RealmCommands(bot, runtime=runtime)
    await getattr(RealmCommands, kind).callback(cog, ctx)
    runtime.observe.assert_not_awaited()
    assert ctx.response.send_message.call_args.kwargs["ephemeral"] is True


@pytest.mark.parametrize("kind", ["status", "players", "refresh"])
async def test_defer_before_io_and_all_results_private(kind):
    ctx = interaction()
    async def observe(**kwargs):
        ctx.response.defer.assert_awaited_once_with(ephemeral=True, thinking=True)
        assert kwargs["force"] is (kind == "refresh")
        return view((Member("111111111111111111", "API Name", online=True), Member("222222222222222222", online=True))), 0
    cog = RealmCommands(NS(settings=settings()), runtime=NS(observe=observe))
    await getattr(RealmCommands, kind).callback(cog, ctx)
    message = ctx.followup.send.call_args.args[0]
    assert "2030" not in message and "<t:" in message
    if kind != "players":
        assert "OPEN" in message and "Synthetic Realm" in message
    if kind != "status":
        assert "Online players: 2" in message and "API Name" in message
        assert "111111111111111111" not in message and "222222222222222222" not in message
    assert ctx.followup.send.call_args.kwargs["ephemeral"] is True
    assert ctx.followup.send.call_args.kwargs["allowed_mentions"].to_dict() == discord.AllowedMentions.none().to_dict()


async def test_role_rechecked_after_observation():
    ctx = interaction()
    async def observe(**kwargs):
        ctx.user.roles = []
        return view(), 0
    cog = RealmCommands(NS(settings=settings()), runtime=NS(observe=observe))
    await cog.respond(ctx, "status")
    assert "no longer have access" in ctx.followup.send.call_args.args[0]


def test_db_role_changes_and_no_auth_owner_bypass():
    cfg = settings()
    ctx = interaction()
    assert permitted(cfg, ctx)
    cfg["CoastalOPTeam"] = 999
    assert not permitted(cfg, ctx)
    ctx.user.id = cfg["realms"]["auth_owner_ids"][0]
    assert not permitted(cfg, ctx)


def test_unknown_zero_stale_missing_names_and_no_identity_guess():
    assert "Unknown / unavailable" in render(Observation(), "players")
    assert "Online players: 0" in render(view(), "players")
    data = view((Member("123", online=True), Member("456", "Offline name", online=False), Member("789", online=None)))
    message = render(data, "players")
    assert "at least 1" in message and "unknown for 1" in message
    assert "Offline name" not in message and "123" not in message
    stale = Observation(data.realm, data.activity, False, False)
    message = render(stale, "refresh", cooldown=20)
    assert "Unknown / unavailable" in message and "State: Unavailable" in message
    assert "Last known state (stale): OPEN" in message and "20 seconds" in message


def test_names_sanitized_and_message_bounded():
    message = render(view(tuple(Member(str(i), "@everyone_*`" * 20, online=True) for i in range(100))), "refresh")
    assert "@everyone" not in message and len(message) < 2000
    assert "100" in message


async def test_cog_error_never_exposes_payload():
    ctx = interaction()
    cog = RealmCommands(NS(settings=settings()), runtime=NS())
    await cog.cog_app_command_error(ctx, RuntimeError("canary-token-response"))
    assert "canary" not in ctx.response.send_message.call_args.args[0]
    assert ctx.response.send_message.call_args.kwargs["ephemeral"] is True


def runtime(clock=None):
    api = RealmRuntime(settings(), monotonic=clock or FakeTime())
    sample = view((Member("123", online=True),))
    api.client = NS(realm=AsyncMock(return_value=sample.realm),
                    activities=AsyncMock(return_value=Snapshot((sample.activity.data,), sample.activity.observed_at)))
    return api


async def test_cache_cooldown_singleflight_and_manual_refresh():
    clock = FakeTime()
    api = runtime(clock)
    results = await asyncio.gather(*(api.observe() for _ in range(10)))
    assert all(item[0].activity_available for item in results)
    assert api.client.realm.await_count == 1
    assert (await api.observe(force=True))[1] == 30
    clock.value += 30
    await api.observe(force=True)
    assert api.client.realm.await_count == 2
    await api.close()


async def test_failure_and_missing_selected_activity_never_become_zero(caplog):
    clock = FakeTime()
    api = runtime(clock)
    await api.observe()
    clock.value += 60
    api.client.realm.side_effect = ReauthRequired()
    api.client.activities.side_effect = RuntimeError("canary-private-payload")
    latest, _ = await api.observe()
    assert not latest.realm_available and not latest.activity_available
    assert latest.realm is not None and latest.activity is not None
    assert "Unknown / unavailable" in render(latest, "refresh")
    assert "canary" not in caplog.text
    api.client.activities.side_effect = None
    api.client.activities.return_value = Snapshot((), latest.activity.observed_at)
    clock.value += 60
    assert not (await api.observe())[0].activity_available


async def test_shutdown_cancels_inflight_and_releases_resources():
    api = runtime()
    entered = asyncio.Event()
    async def wait():
        entered.set()
        await asyncio.Event().wait()
    api.client.realm.side_effect = wait
    close = AsyncMock()
    api._stack.push_async_callback(close)
    task = asyncio.create_task(api.observe())
    await entered.wait()
    await api.close()
    assert task.cancelled() and api.client is None
    close.assert_awaited_once()
    assert not (await api.observe())[0].realm_available


async def test_start_stop_and_partial_failure_clean_up_without_login():
    calls = []
    store = NS(open=Mock(side_effect=lambda: calls.append("open")), close=Mock(side_effect=lambda: calls.append("store-close")))
    class Transport:
        async def __aenter__(self):
            calls.append("session-open")
            return self
        async def __aexit__(self, *args):
            calls.append("session-close")
    service = NS(client=Mock(return_value=NS()), close=AsyncMock(side_effect=lambda: calls.append("service-close")))
    api = RealmRuntime(settings(), environ={}, store_factory=lambda *a: store,
                       transport_factory=lambda **k: Transport(), service_factory=lambda *a: service)
    await api.start()
    await api.start()
    assert calls == ["open", "session-open"]
    principal = service.client.call_args.args[0]
    assert principal.user_id == settings()["realms"]["auth_owner_ids"][0]
    await api.close()
    assert calls[-3:] == ["service-close", "session-close", "store-close"]
    service.client.side_effect = RuntimeError("canary")
    calls.clear()
    api = RealmRuntime(settings(), environ={}, store_factory=lambda *a: store,
                       transport_factory=lambda **k: Transport(), service_factory=lambda *a: service)
    await api.start()
    assert api.client is None and calls[-3:] == ["service-close", "session-close", "store-close"]


async def test_unconfigured_storage_and_disabled_mode_do_not_break_bot():
    api = RealmRuntime(settings(), environ={})
    await api.start()
    assert api.client is None
    assert "Unknown / unavailable" in render((await api.observe())[0], "players")
    factory = Mock(side_effect=AssertionError("Should not open storage"))
    disabled = RealmRuntime({"Coastal": 202}, store_factory=factory)
    await disabled.start()
    factory.assert_not_called()


async def test_command_registration_is_coastal_only_and_unload_closes_runtime(monkeypatch):
    bot = NS(settings=settings(), add_cog=AsyncMock())
    fake = NS(start=AsyncMock(), close=AsyncMock())
    monkeypatch.setattr("utils.realms.cog.RealmRuntime", lambda cfg: fake)
    await setup(bot)
    cog = bot.add_cog.call_args.args[0]
    assert cog.realm._guild_ids == [202]
    assert sorted(c.name for c in cog.realm.commands) == ["metrics", "panel", "players", "refresh", "status"]
    await cog.cog_load()
    await cog.cog_unload()
    fake.start.assert_awaited_once()
    fake.close.assert_awaited_once()


def test_optional_db_settings_preserve_existing_schema_and_ignore_private_file():
    from utils.configuration import SEED, validate_document
    original = json.loads(SEED.read_text())
    assert "realms" not in original["settings"]
    assert validate_document(copy.deepcopy(original)) == original
    original["settings"]["realms"] = settings()["realms"]
    original["settings"]["Coastal"] = 202
    assert validate_document(original)["settings"]["CoastalOPTeam"]
    assert from_bot_settings(original["settings"]).binding == config().binding
    original["settings"]["realms"]["guild_id"] = 999
    with pytest.raises(ValueError):
        validate_document(original)


@pytest.mark.parametrize("key,value", [("guild_id", 999), ("token", "canary"), ("selected_realm_id", None)])
def test_bot_config_rejects_duplicate_guild_secrets_and_no_selection(key, value):
    cfg = settings()
    cfg["realms"][key] = value
    with pytest.raises(ConfigurationError):
        from_bot_settings(cfg)


async def test_tree_does_not_publicly_block_realm_users_without_avatar():
    from main import CaptainCommandTree
    ctx = interaction(roles=())
    ctx.user.avatar = None
    ctx.command = NS(qualified_name="realm status")
    assert await CaptainCommandTree.interaction_check(None, ctx)
    ctx.response.send_message.assert_not_awaited()


async def test_real_bot_registers_only_in_coastal_and_close_unloads(monkeypatch):
    from main import TheCaptain
    fake = NS(start=AsyncMock(), close=AsyncMock())
    # load_extension freshly imports the cog module; patch its stable dependency.
    monkeypatch.setattr("utils.realms.runtime.RealmRuntime.start", fake.start)
    monkeypatch.setattr("utils.realms.runtime.RealmRuntime.close", fake.close)
    bot = TheCaptain(settings())
    await bot.load_extension("utils.realms.cog")
    group = bot.tree.get_command("realm", guild=discord.Object(202))
    assert group is not None and sorted(c.name for c in group.commands) == ["metrics", "panel", "players", "refresh", "status"]
    assert bot.tree.get_command("realm") is None
    assert bot.tree.get_command("realm", guild=discord.Object(999)) is None
    await bot.close()
    fake.start.assert_awaited_once()
    fake.close.assert_awaited_once()


async def test_bot_startup_enables_realms_after_loading_db_settings():
    from main import TheCaptain
    events = []
    cfg = {}
    def initialize(values):
        values.update(settings())
        events.append("db")
        return NS(prefix=">")
    sheets = NS(initialize=AsyncMock(side_effect=lambda: events.append("sheets")),
                application_content=NS(), poi_content=NS(), guide_content=NS())
    bot = TheCaptain(cfg, sheets=sheets, database_initializer=initialize)
    bot.load_extension = AsyncMock(side_effect=lambda name: events.append(name))
    await bot.setup_hook()
    assert events[:2] == ["db", "sheets"]
    assert events[-1] == "utils.realms.cog"
    await bot.close()


async def test_long_upstream_retry_after_blocks_all_commands_and_second_endpoint():
    from utils.integrations.realms.errors import HTTPFailure
    clock = FakeTime()
    api = runtime(clock)
    api.client.realm.side_effect = HTTPFailure(429, 120)
    result, delay = await api.observe()
    assert delay == 120 and not result.activity_available
    api.client.activities.assert_not_awaited()
    clock.value += 30
    assert (await api.observe(force=True))[1] == 90
    assert (await api.observe())[1] == 90
    assert api.client.realm.await_count == 1
