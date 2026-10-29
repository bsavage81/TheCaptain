from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest
from discord import app_commands

from utils.coastal_guide.__cg_commands import CoastalGuideCMD
from utils.coastal_guide.__cg_logic import load_guide_content, post_guide_announcement


def announcement_context():
    bot = NS(settings={"CoastalMRP": 123, "botspamChannel": 456,
                       "bot_spam_channel_coastal": 789, "OPTeamRole": "OP Team"},
             guide_content=load_guide_content({"guide_web_url": "https://example.com/season10",
                                               "guide_pdf_url": "https://example.com/season10.pdf"}))
    interaction = NS(client=bot, guild=NS(), channel=NS(send=AsyncMock()),
                     user=NS(roles=[]), response=NS(send_message=AsyncMock(), defer=AsyncMock()),
                     followup=NS(send=AsyncMock()))
    return bot, interaction


async def test_announcement_posts_current_links_and_explicit_everyone_mention():
    bot, interaction = announcement_context()
    await post_guide_announcement(bot, interaction)
    call = interaction.channel.send.call_args
    message = call.args[0]
    assert "@everyone" in message and "Season 10" in message
    assert "Season 9" not in message and "armadillo" not in message
    assert "<#789>" in message
    assert "<#456>" not in message
    assert "<#123>" not in message
    assert bot.guide_content.web_url in message and bot.guide_content.pdf_url in message
    mentions = call.kwargs["allowed_mentions"]
    assert mentions.everyone and not mentions.roles and not mentions.users
    interaction.response.defer.assert_awaited_once_with(ephemeral=True, thinking=True)


async def test_announcement_requires_op_role():
    bot, interaction = announcement_context()
    command = CoastalGuideCMD(bot).guide_announcement
    with pytest.raises(app_commands.MissingRole):
        await command.checks[0](interaction)
    interaction.user.roles = [NS(id=1, name="OP Team")]
    assert await command.checks[0](interaction)


async def test_unconfigured_guide_does_not_publish():
    bot, interaction = announcement_context()
    bot.guide_content = load_guide_content({"guide_answer": ""})
    await post_guide_announcement(bot, interaction)
    interaction.channel.send.assert_not_awaited()
    assert interaction.response.send_message.call_args.kwargs["ephemeral"]
