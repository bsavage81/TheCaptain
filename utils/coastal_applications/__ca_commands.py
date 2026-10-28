from utils.core_features.__common import coastal_command_guilds
from typing import Any
import discord
from discord import app_commands
from discord.ext import commands
from utils.helpers.__checks import op_team
from . import __ca_logic as logic
from .__ca_views import CoastalApplicationStartView


class CoastalAppCMD(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="applycoastal",
        description="Apply to the Coastal Craft Discord Server",
    )
    async def applycoastal(self, interaction: discord.Interaction[Any]):
        channel = interaction.channel

        if channel is None or channel.id != self.bot.settings["CoastalMRP"]:
            noGoAway = discord.Embed(
                title="Woah Woah Woah, Slow Down There Buddy!",
                description="This belongs over in Coastal Craft, no one here wants to hear it here!",
                color=0x20F6B3,
            )

            await interaction.response.send_message(
                embed=noGoAway,
                ephemeral=True,
            )
            return

        introem = discord.Embed(
            title=self.bot.application_content.apptitle,
            description=self.bot.application_content.appdesc,
            color=0x336F75,
        )

        introem2 = discord.Embed(
            title=self.bot.application_content.appreftitle,
            description=self.bot.application_content.apprefdesc,
            color=0x336F75,
        )

        view = CoastalApplicationStartView(
            bot=self.bot,
            user_id=interaction.user.id,
        )

        await interaction.response.send_message(
            content="Click below to start the Coastal Craft application.",
            embeds=[introem, introem2],
            view=view,
            ephemeral=True,
        )

    @app_commands.command(
        name="approveapp",
        description="Approve an Application!",
    )
    @app_commands.describe(appnumber="Application number to approve")
    @op_team()
    async def approveapp(self, interaction: discord.Interaction, appnumber: str):
        await logic.approveapp(self, interaction, appnumber)

    @app_commands.command(
        name="denyapp",
        description="Deny an Application!",
    )
    @app_commands.describe(appnumber="Application number to deny")
    @op_team()
    async def denyapp(self, interaction: discord.Interaction, appnumber: str):
        await logic.denyapp(self, interaction, appnumber)


async def setup(bot):
    cog = CoastalAppCMD(bot)
    for command in cog.get_app_commands():
        ids = (
            [bot.settings["MRP"], bot.settings["Coastal"]]
            if command.name == "applycoastal"
            else coastal_command_guilds(bot.settings)
        )
        command._guild_ids = list(dict.fromkeys(ids))
    await bot.add_cog(cog)
