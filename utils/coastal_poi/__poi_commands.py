from utils.core_features.__common import coastal_command_guilds
import discord
from discord import app_commands
from discord.ext import commands
from . import __poi_logic as logic
from .__poi_logic import run_poi


class CoastalPOICMD(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="addpoi_overworld",
                   description="Add a POI to the Overworld!")
    async def addpoi_overworld(self, interaction: discord.Interaction, x_coord: int, z_coord: int):
        await run_poi(self, interaction, x_coord, z_coord, logic.addpoi_overworld)

    @app_commands.command(name="addpoi_nether",
                   description="Add a POI to the Nether!")
    async def addpoi_nether(self, interaction: discord.Interaction, x_coord: int, z_coord: int):
        await run_poi(self, interaction, x_coord, z_coord, logic.addpoi_nether)

    @app_commands.command(name="addpoi_end",
                   description="Add a POI to the End!")
    async def addpoi_end(self, interaction: discord.Interaction, x_coord: int, z_coord: int):
        await run_poi(self, interaction, x_coord, z_coord, logic.addpoi_end)


    @app_commands.command(name="addpoi_endcity_claim",
                   description="Add an End city that you hae raided!")
    async def addpoi_endcity_claim(self, interaction: discord.Interaction, x_coord: int, z_coord: int):
        await run_poi(self, interaction, x_coord, z_coord, logic.addpoi_endcity_claim)

    @app_commands.command(name="addpoi_end_returngateway",
                   description="Mark a return gateway in the End")
    async def addpoi_end_returngateway(self, interaction: discord.Interaction, x_coord: int, z_coord: int):
        await run_poi(self, interaction, x_coord, z_coord, logic.addpoi_end_returngateway)


async def setup(bot):
    cog = CoastalPOICMD(bot)
    for command in cog.get_app_commands():
        command._guild_ids = list(dict.fromkeys(coastal_command_guilds(bot.settings)))
    await bot.add_cog(cog)
