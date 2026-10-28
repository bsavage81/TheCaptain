import discord
from discord import app_commands
from discord.ext import commands
from utils.helpers.__checks import op_team
from .__cg_logic import run_guide


class CoastalGuideCMD(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.sessions = set()

    @app_commands.command(name="guide", description="Agree to the Coastal Craft Players Guide!")
    @op_team()
    async def guide(self, interaction: discord.Interaction):
        await run_guide(self, interaction)


async def setup(bot):
    cog = CoastalGuideCMD(bot)
    for command in cog.get_app_commands():
        command._guild_ids = list(dict.fromkeys([bot.settings["PBtest"], bot.settings["Coastal"]]))
    await bot.add_cog(cog)
