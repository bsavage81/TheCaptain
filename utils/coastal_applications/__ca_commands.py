from utils.core_features.__common import coastal_command_guilds
from typing import Any
import logging
import discord
from discord import app_commands
from discord.ext import commands
from utils.helpers.__checks import op_team
from . import __ca_logic as logic
from .__ca_views import CoastalApplicationStartView
from .web_portal import WebPortal, portal_config, issue_ticket


class CoastalAppCMD(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.web_portal = None

    async def cog_load(self):
        config = portal_config()
        if config:
            self.web_portal = WebPortal(self.bot, config)
            self.web_portal.start()
            logging.getLogger(__name__).info("application_web_portal_enabled")
        else:
            logging.getLogger(__name__).info("application_web_portal_disabled")

    async def cog_unload(self):
        if self.web_portal:
            await self.web_portal.stop()

    @app_commands.command(
        name="applycoastal",
        description="Apply to the Coastal Craft Discord Server",
    )
    async def applycoastal(self, interaction: discord.Interaction[Any]):
        channel = interaction.channel
        guild = interaction.guild

        if channel is None or (
            channel.id != self.bot.settings["CoastalMRP"]
            and (guild is None or guild.id != self.bot.settings["Coastal"])
        ):
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

        if self.web_portal:
            code = issue_ticket(interaction.user, self.web_portal.config.secret)
            view = discord.ui.View()
            view.add_item(discord.ui.Button(label="Open application form", url=self.web_portal.config.url))
            await interaction.response.send_message(
                "Open the form below, or use the form on our Google Site, and paste the private access code "
                "from the next message. It expires in 24 hours. Keep it private.",
                view=view, ephemeral=True,
            )
            await interaction.followup.send(code, ephemeral=True)
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
