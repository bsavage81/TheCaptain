from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock

import pytest

from test_realms_discord import settings, interaction
from utils.realms.stories_sync import StoriesController, DESTINATION, validate_sync
from utils.realms.cog import RealmCommands


def controller():
    channel = NS(id=DESTINATION, guild=NS(id=202))
    bot = NS(settings=settings(), get_channel=Mock(return_value=channel), fetch_channel=AsyncMock())
    publish = AsyncMock(return_value=(True, 'ok'))
    repository = NS(save=Mock())
    clock = NS(value=0)
    sync = StoriesController(bot, NS(), publish, repository=repository, clock=lambda: clock.value)
    return sync, channel, publish, repository, clock


async def test_initial_destination_saved_and_shared_publisher_used_every_five_minutes():
    sync, channel, publish, repository, clock = controller()
    assert sync.poll.seconds == 300
    assert await sync.refresh()
    assert sync.config['channel_id'] == DESTINATION and sync.config['interval_seconds'] == 300
    repository.save.assert_called_once()
    args = publish.call_args.args
    assert args[:2] == (channel, 202) and args[2]() is True
    await sync.refresh()
    assert publish.await_count == 2 and repository.save.call_count == 1


async def test_pause_persists_and_survives_controller_restart():
    sync, channel, publish, repository, clock = controller()
    await sync.configure(False)
    assert not await sync.refresh()
    publish.assert_not_awaited()
    restarted = StoriesController(sync.bot, NS(), publish, repository=repository)
    assert not await restarted.refresh()
    await restarted.configure(True)
    assert await restarted.refresh()


async def test_selected_realm_change_stops_automatic_posting_until_reenabled():
    sync, channel, publish, repository, clock = controller()
    await sync.configure(True)
    sync.bot.settings['realms']['selected_realm_id'] = '88'
    assert not await sync.refresh()
    publish.assert_not_awaited()
    await sync.configure(True)
    assert await sync.refresh()


async def test_wrong_guild_or_failure_backs_off_and_never_uses_another_channel():
    sync, channel, publish, repository, clock = controller()
    channel.guild.id = 999
    assert not await sync.refresh()
    publish.assert_not_awaited()
    assert sync.retry_at == 300
    channel.guild.id = 202
    assert not await sync.refresh()
    clock.value = 300
    publish.return_value = (False, 'private-error')
    assert not await sync.refresh()
    assert sync.retry_at == 900
    clock.value = 900
    publish.return_value = (True, 'ok')
    assert await sync.refresh()


async def test_pause_command_requires_op_team_before_persistence():
    cog = RealmCommands(NS(settings=settings()), runtime=NS())
    cog.stories_sync.configure = AsyncMock()
    ctx = interaction(roles=())
    await RealmCommands.storiesauto.callback(cog, ctx, False)
    cog.stories_sync.configure.assert_not_awaited()


@pytest.mark.parametrize('field,value', [('interval_seconds',15),('channel_id',True),
                                       ('enabled',1),('guild_id',999),('realm_id','../42')])
def test_sync_configuration_rejects_invalid_scope_and_interval(field,value):
    config = dict(enabled=True,guild_id=202,channel_id=DESTINATION,realm_id='42',interval_seconds=300)
    config[field] = value
    with pytest.raises(ValueError):
        validate_sync(config,202)


async def test_scheduler_shutdown_cancels_wait_ready_without_network():
    import asyncio
    sync, channel, publish, repository, clock = controller()
    ready = asyncio.Event()
    sync.bot.wait_until_ready = ready.wait
    sync.start()
    task = sync.poll.get_task()
    await asyncio.sleep(0)
    await sync.close()
    assert task.done()
    publish.assert_not_awaited()
    repository.save.assert_not_called()


async def test_runtime_target_mismatch_prevents_publication():
    sync, channel, publish, repository, clock = controller()
    await sync.configure(True)
    sync.runtime.config = NS(selected_realm_id='99')
    assert not await sync.refresh()
    publish.assert_not_awaited()
