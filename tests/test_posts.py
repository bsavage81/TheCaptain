from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock

import discord
import pytest

from utils.admin.bot_management.posts import PostModal


def context():
    interaction = NS(
        user=NS(id=1, roles=[NS(name="OP Team")]), guild=NS(me=NS(id=2)),
        client=NS(settings={}), response=NS(send_message=AsyncMock(), defer=AsyncMock()),
        followup=NS(send=AsyncMock()),
    )
    channel = NS(permissions_for=Mock(return_value=NS(view_channel=True, send_messages=True)),
                 send=AsyncMock(return_value=NS(jump_url="https://discord.com/test")))
    return interaction, channel


@pytest.mark.asyncio
async def test_post_allows_user_role_and_everyone_notifications():
    interaction, channel = context()
    modal = PostModal(1, channel)
    modal.content._value = "Hello **crew**!\n@everyone"
    await modal.on_submit(interaction)
    args, kwargs = channel.send.call_args
    assert args == ("Hello **crew**!\n@everyone",)
    assert kwargs["allowed_mentions"].to_dict() == discord.AllowedMentions.all().to_dict()
    interaction.followup.send.assert_awaited_once_with("Posted: https://discord.com/test", ephemeral=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("reason", ["other_user", "lost_role", "lost_permissions", "blank"])
async def test_post_rechecks_author_and_access(reason):
    interaction, channel = context()
    modal = PostModal(1, channel)
    modal.content._value = "Hello"
    if reason == "other_user":
        interaction.user.id = 9
    elif reason == "lost_role":
        interaction.user.roles = []
    elif reason == "lost_permissions":
        channel.permissions_for.return_value.send_messages = False
    else:
        modal.content._value = "  "
    if reason == "lost_role":
        with pytest.raises(discord.app_commands.MissingRole):
            await modal.on_submit(interaction)
    else:
        await modal.on_submit(interaction)
        assert interaction.response.send_message.call_args.kwargs["ephemeral"] is True
    channel.send.assert_not_awaited()
