from typing import Any
import discord
from discord import app_commands
from discord.ext import commands
from utils.helpers.__checks import op_team
from .__ca_views import CoastalApplicationStartView


def _safe_int(value):
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


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
        await interaction.response.defer(thinking=True)
        DMStatus = "FALSE"
        author = interaction.user
        guild = interaction.guild
        mrpguild = self.bot.get_guild(self.bot.settings["MRP"])

        if guild is None or mrpguild is None:
            await interaction.followup.send(
                "Could not find the required server data.",
                ephemeral=True,
            )
            return

        invitechannel = guild.get_channel(self.bot.settings["CoastalInviteChannel"])

        if invitechannel is None:
            await interaction.followup.send(
                "Invite channel could not be found.",
                ephemeral=True,
            )
            return

        applicant = await self.bot.sheets.application_record(appnumber)
        userid = applicant[1]
        user = mrpguild.get_member_named(userid)

        if user is None:
            userlongid = _safe_int(applicant[3])

            if userlongid is not None:
                user = mrpguild.get_member(userlongid)

                if user is None:
                    user = await mrpguild.fetch_member(userlongid)

        invite = await invitechannel.create_invite(max_uses=1)
        await self.bot.sheets.decide_application(appnumber, "Yes")

        DMStatus = "FAILED"

        embed = discord.Embed(
            title="Congratulations",
            description="You made it to the next step!",
            color=0x008000,
        )

        embed.add_field(
            name="Welcome to Coastal Craft!!!",
            value=(
                "In this step you need to join our Discord, tell us about yourself, "
                "get to know us, and if it is a good fit, the Realm invite will be the next step. "
                "We are glad to have you and hope you enjoy your time in Coastal Craft!"
            ),
            inline=False,
        )

        embed.set_thumbnail(
            url="https://cdn.discordapp.com/attachments/488792053002534920/1157338182392741999/coastal_logo_final_s9.png"
        )

        try:
            if user is not None:
                await user.send(embed=embed)
                await user.send(invite.url)
                DMStatus = "DONE"

        except discord.HTTPException:
            DMStatus = "FAILED (decision saved; delivery failed)"
        finally:
            response_embed = discord.Embed(
                title=f"Application {appnumber} Approved",
                description=f"Approved by: {author.mention}",
                color=0x008000,
            )

            response_embed.add_field(name="**Applicant**", value=str(user))
            response_embed.add_field(
                name="**Console Logs**",
                value=f"**DMStatus:** {DMStatus}",
            )

            response_embed.set_footer(text="The command has finished all of its tasks")
            response_embed.set_thumbnail(
                url="https://cdn.discordapp.com/attachments/488792053002534920/1157338182392741999/coastal_logo_final_s9.png"
            )

            await interaction.followup.send(embed=response_embed)

    @app_commands.command(
        name="denyapp",
        description="Deny an Application!",
    )
    @app_commands.describe(appnumber="Application number to deny")
    @op_team()
    async def denyapp(self, interaction: discord.Interaction, appnumber: str):
        await interaction.response.defer(thinking=True)
        DMStatus = "FALSE"
        author = interaction.user
        mrpguild = self.bot.get_guild(self.bot.settings["MRP"])

        if mrpguild is None:
            await interaction.followup.send(
                "MRP server could not be found.",
                ephemeral=True,
            )
            return

        applicant = await self.bot.sheets.application_record(appnumber)
        userid = applicant[1]
        user = mrpguild.get_member_named(userid)

        if user is None:
            userlongid = _safe_int(applicant[3])

            if userlongid is not None:
                user = mrpguild.get_member(userlongid)

                if user is None:
                    user = await mrpguild.fetch_member(userlongid)

        await self.bot.sheets.decide_application(appnumber, "No")

        DMStatus = "FAILED"

        embed = discord.Embed(
            title="Sorry",
            description="Your app has been denied",
            color=0xFF0000,
        )

        embed.add_field(
            name="You can try again!",
            value=(
                "Just because you have been denied does not mean it is the end. "
                "Keep chatting in the Minecraft Realm Portal, and try again at a later time."
            ),
            inline=False,
        )

        embed.set_thumbnail(
            url="https://cdn.discordapp.com/attachments/488792053002534920/1157338182392741999/coastal_logo_final_s9.png"
        )

        try:
            if user is not None:
                await user.send(embed=embed)
                DMStatus = "DONE"

        except discord.HTTPException:
            DMStatus = "FAILED (decision saved; delivery failed)"
        finally:
            response_embed = discord.Embed(
                title=f"Application {appnumber} Denied",
                description=f"Denied by: {author.mention}",
                color=0xFF0000,
            )

            response_embed.add_field(name="**Applicant**", value=str(user))
            response_embed.add_field(
                name="**Console Logs**",
                value=f"**DMStatus:** {DMStatus}",
            )

            response_embed.set_footer(text="The command has finished all of its tasks")
            response_embed.set_thumbnail(
                url="https://cdn.discordapp.com/attachments/488792053002534920/1157338182392741999/coastal_logo_final_s9.png"
            )

            await interaction.followup.send(embed=response_embed)


async def setup(bot):
    cog = CoastalAppCMD(bot)
    for command in cog.get_app_commands():
        ids = [bot.settings["MRP"]] if command.name == "applycoastal" else [bot.settings["PBtest"], bot.settings["Coastal"]]
        command._guild_ids = list(dict.fromkeys(ids))
    await bot.add_cog(cog)
