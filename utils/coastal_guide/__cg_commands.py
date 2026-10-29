from utils.core_features.__common import coastal_command_guilds
import discord
from discord import app_commands
from discord.ext import commands
from utils.helpers.__checks import op_team
from .__cg_logic import run_guide, post_guide_announcement


class CoastalGuideCMD(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.sessions = set()

    @app_commands.command(
        name="guide", description="Agree to the Coastal Craft Players Guide!"
    )
    async def guide(self, interaction: discord.Interaction):
        await run_guide(self, interaction)

    @app_commands.command(
        name="guide-announcement",
        description="Post the Season 10 guide announcement in this channel (pings everyone).",
    )
    @app_commands.guild_only()
    @op_team()
    async def guide_announcement(self, interaction: discord.Interaction):
        await post_guide_announcement(self.bot, interaction)


async def setup(bot):
    cog = CoastalGuideCMD(bot)
    for command in cog.get_app_commands():
        command._guild_ids = list(dict.fromkeys(coastal_command_guilds(bot.settings)))
    await bot.add_cog(cog)
