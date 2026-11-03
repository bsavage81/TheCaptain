import asyncio
from datetime import timedelta
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock

import discord
import pytest

from test_realms_discord import settings, interaction, view, runtime
from realms_fakes import FakeTime
from utils.integrations.realms.models import Activity, Member, Snapshot
from utils.realms.cog import RealmCommands
from utils.realms.panel import PanelController, Sessions, panel_embed, validate_panel


def observation(players, seconds=0, available=True):
    v = view(players, available=available)
    return type(v)(v.realm, Snapshot(Activity("42", players), v.activity.observed_at + timedelta(seconds=seconds)), True, available)


def player(xuid="123", name="Sailor", online=True):
    return Member(xuid, name, online=online)


def test_sessions_join_failure_unknown_leave_rejoin_and_restart():
    s = Sessions("42")
    first = observation((player(),))
    assert s.observe(first)
    start = s.active["123"]
    assert not s.observe(observation((), 100, available=False))
    assert not s.observe(observation((player(online=None),), 101))
    assert s.active["123"] == start
    restored = Sessions("42", s.document())
    assert not restored.observe(observation((player(name="Renamed"),), 200))
    assert restored.active["123"] == start
    assert restored.duration(player(), start + 9240, reliable=True) == "Tracked for 2h 34m"
    assert restored.observe(observation((), 300))
    assert restored.active == {}
    assert restored.observe(observation((player(),), 400))
    assert restored.active["123"] == start + 400
    assert restored.duration(player(), start + 400, reliable=False) == "Duration unavailable"


def test_non_authoritative_or_old_snapshots_never_end_sessions():
    s = Sessions("42")
    s.observe(observation((player(),), 20))
    assert not s.observe(observation((), 10))
    assert not s.observe(observation((player(xuid=""),), 30))
    assert "123" in s.active


@pytest.mark.parametrize("data", [{}, {"realm_id":"other"}, {"realm_id":"42", "active":{"1":float('nan')}, "last_observation":10}])
def test_invalid_persistent_sessions_rejected(data):
    with pytest.raises(ValueError):
        Sessions("42", data)


def test_embed_truthful_names_durations_unknown_zero_and_no_ids():
    v = observation((player(name="@everyone **Captain**"), player("4567890123456789", None)))
    s = Sessions("42")
    s.observe(v)
    embed = panel_embed(v, s, 15, now=v.activity.observed_at + timedelta(minutes=8)).to_dict()
    text = "\n".join(f["value"] for f in embed["fields"])
    assert "Tracked for 8m" in text and "Duration unavailable" in text
    assert "123" not in text and "4567890123456789" not in text
    assert "@\u200beveryone" in text and "\\*" in text
    assert "/10" not in text and "<t:" in text
    assert "No players online" in str(panel_embed(observation(()), s, 15).to_dict())
    assert "No players online" not in str(panel_embed(observation((), available=False), s, 15).to_dict())
    assert "Stale" in str(panel_embed(observation((), available=False), s, 15).to_dict())


@pytest.mark.parametrize("action", ["create", "remove", "refresh"])
@pytest.mark.parametrize("reason", ["role", "guild", "dm"])
async def test_panel_management_permission_and_ephemeral_denial(action, reason):
    ctx = interaction(roles=() if reason == "role" else (404,), guild=999 if reason == "guild" else 202)
    if reason == "dm":
        ctx.guild = None
    cog = RealmCommands(NS(settings=settings()), runtime=NS())
    cog.panels = NS(create=AsyncMock(), remove=AsyncMock(), refresh=AsyncMock())
    await cog.manage_panel(ctx, action)
    assert ctx.response.send_message.call_args.kwargs["ephemeral"]
    cog.panels.create.assert_not_awaited()
    cog.panels.remove.assert_not_awaited()
    cog.panels.refresh.assert_not_awaited()


def controller(configured=True):
    cfg = settings()
    if configured:
        cfg["realm_panel"] = dict(guild_id=202, channel_id=303, message_id=404, interval_seconds=15)
    message = NS(id=404, channel=NS(id=303), author=NS(id=606), edit=AsyncMock(), delete=AsyncMock(), jump_url="https://discord.com/channels/202/303/404")
    channel = NS(id=303, guild=NS(id=202), fetch_message=AsyncMock(return_value=message), send=AsyncMock(return_value=message))
    guild = NS(get_channel=Mock(return_value=channel))
    bot = NS(settings=cfg, get_guild=Mock(return_value=guild), user=NS(id=606), wait_until_ready=AsyncMock())
    api = NS(config=NS(selected_realm_id="42"), observe=AsyncMock(return_value=(observation((player(),)), 0)),
             store=NS(load_panel_sessions=Mock(return_value=None), save_panel_sessions=Mock()))
    repo = NS(save=Mock())
    return PanelController(bot, api, repository=repo), message, channel


async def test_restart_recovers_existing_message_edits_only_on_change_and_persists_sessions():
    c, message, channel = controller()
    assert await c.refresh()
    channel.fetch_message.assert_awaited_once_with(404)
    c.runtime.observe.assert_awaited_once_with(force=False, scheduled=True)
    message.edit.assert_awaited_once()
    channel.send.assert_not_awaited()
    c.runtime.store.save_panel_sessions.assert_called_once()
    saved = c.runtime.store.save_panel_sessions.call_args.args[0]
    assert await c.refresh()
    assert message.edit.await_count == 1
    assert c.runtime.store.save_panel_sessions.call_count == 1
    restart, new_message, _ = controller()
    restart.runtime.store.load_panel_sessions.return_value = saved
    restart.runtime.observe.return_value = (observation((player(),), 3600), 0)
    assert await restart.refresh()
    assert restart.sessions.active == c.sessions.active
    assert new_message.edit.await_count == 1


async def test_deleted_message_stops_until_explicit_create():
    c, message, channel = controller()
    channel.fetch_message.side_effect = discord.NotFound(NS(status=404, reason="missing"), "missing")
    assert not await c.refresh()
    assert c.missing
    assert not await c.refresh()
    assert channel.fetch_message.await_count == 1
    c.runtime.observe.assert_not_awaited()
    await c.create(channel)
    channel.send.assert_awaited_once()
    assert not c.missing


async def test_create_reuses_same_panel_and_relocation_deletes_old_first():
    c, message, channel = controller()
    assert await c.create(channel) == message.jump_url
    channel.send.assert_not_awaited()
    new = NS(id=505, guild=NS(id=202), send=AsyncMock(return_value=message))
    await c.create(new)
    message.delete.assert_awaited_once()
    new.send.assert_awaited_once()
    assert c.config["channel_id"] == 505


async def test_permission_failure_never_creates_duplicate_and_backs_off():
    c, message, channel = controller()
    message.delete.side_effect = discord.Forbidden(NS(status=403, reason="forbidden"), "forbidden")
    with pytest.raises(discord.Forbidden):
        await c.create(NS(id=505, guild=NS(id=202), send=AsyncMock()))
    message.edit.side_effect = discord.Forbidden(NS(status=403, reason="forbidden"), "forbidden")
    assert not await c.refresh()
    assert c.retry_at > asyncio.get_running_loop().time()
    assert not await c.refresh(manual=True)
    assert message.edit.await_count == 1


async def test_failed_config_save_removes_new_message():
    c, message, channel = controller(False)
    c.repository.save.side_effect = RuntimeError()
    with pytest.raises(RuntimeError):
        await c.create(channel)
    message.delete.assert_awaited_once()
    assert c.config is None


async def test_remove_stops_requests_and_shutdown_cancels_waiting_task():
    c, message, _ = controller()
    await c.remove()
    message.delete.assert_awaited_once()
    c.repository.save.assert_called_once_with(None, 202)
    assert not await c.refresh()
    c.runtime.observe.assert_not_awaited()
    async def wait_ready():
        await asyncio.sleep(3600)
    c.bot.wait_until_ready = wait_ready
    c.start()
    await asyncio.sleep(0)
    await c.close()
    assert c.poll.get_task().done()


async def test_encrypted_storage_failure_does_not_publish_unpersisted_durations():
    c, message, _ = controller()
    c.runtime.store.save_panel_sessions.side_effect = RuntimeError("private canary")
    assert await c.refresh()
    assert "Duration unavailable" in str(message.edit.call_args.kwargs["embed"].to_dict())
    assert "private canary" not in str(message.edit.call_args)


@pytest.mark.parametrize("interval", [0, 14, 3601, True])
def test_invalid_interval(interval):
    with pytest.raises(ValueError):
        validate_panel(dict(guild_id=202, channel_id=303, message_id=404, interval_seconds=interval), 202)


async def test_poll_bypasses_60_second_cache_but_serializes_with_commands():
    clock = FakeTime()
    api = runtime(clock)
    await api.observe(scheduled=True)
    clock.value += 15
    await asyncio.gather(api.observe(scheduled=True), api.observe(scheduled=True))
    assert api.client.realm.await_count == 2
    await api.observe()
    assert api.client.realm.await_count == 2


async def test_api_failures_exponential_backoff_preserve_last_observation():
    clock = FakeTime()
    api = runtime(clock)
    good, _ = await api.observe(scheduled=True)
    clock.value += 15
    api.client.realm.side_effect = TimeoutError()
    stale, delay = await api.observe(scheduled=True)
    assert delay == 15 and stale.realm is good.realm and not stale.realm_available
    clock.value += 15
    assert (await api.observe(scheduled=True))[1] == 30
