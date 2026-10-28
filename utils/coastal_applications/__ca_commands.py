from typing import Any, Optional
import logging
from datetime import datetime

import discord
from discord import app_commands, ui
from discord.ext import commands

import gspread
from oauth2client.service_account import ServiceAccountCredentials

from utils.core_features.__common import load_config

config, _ = load_config()
logger = logging.getLogger(__name__)

time_convert = {"s": 1, "m": 60, "h": 3600, "d": 86400}


def _safe_int(value: object) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def convert(time_value):
    try:
        return int(time_value[:-1]) * time_convert[time_value[-1]]
    except Exception:
        return time_value


scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive",
]

creds = ServiceAccountCredentials.from_json_keyfile_name("creds.json", scope)
client = gspread.authorize(creds)
sheet = client.open("CCS9 Realm Application").sheet1


appinforow = 1
apptitlecol = 1
appdesccol = 2
appreftitlecol = 3
apprefdesccol = 4
appTYtitlecol = 5
appTYdesccol = 6
questiontitle1col = 7
questiontitle2col = 8
questiontitle3col = 9

apptitle = sheet.cell(appinforow, apptitlecol).value
appdesc = sheet.cell(appinforow, appdesccol).value
appreftitle = sheet.cell(appinforow, appreftitlecol).value
apprefdesc = sheet.cell(appinforow, apprefdesccol).value
appTYtitle = sheet.cell(appinforow, appTYtitlecol).value
appTYdesc = sheet.cell(appinforow, appTYdesccol).value
questiontitle1 = sheet.cell(appinforow, questiontitle1col).value
questiontitle2 = sheet.cell(appinforow, questiontitle2col).value
questiontitle3 = sheet.cell(appinforow, questiontitle3col).value

questionrow = 2
gamertagcol = 5
countrycol = 6
agecol = 7
gendercol = 8
platformcol = 9
q1col = 10
q2col = 11
q3col = 12
q4col = 13
q5col = 14
rule1col = 15
rule2col = 16
refq1col = 17
refq2col = 18
refq3col = 19

Qgamertag = sheet.cell(questionrow, gamertagcol).value
Qcountry = sheet.cell(questionrow, countrycol).value
Qage = sheet.cell(questionrow, agecol).value
Qgender = sheet.cell(questionrow, gendercol).value
Qplatform = sheet.cell(questionrow, platformcol).value
Question1 = sheet.cell(questionrow, q1col).value
Question2 = sheet.cell(questionrow, q2col).value
Question3 = sheet.cell(questionrow, q3col).value
Question4 = sheet.cell(questionrow, q4col).value
Question5 = sheet.cell(questionrow, q5col).value
Qrule1 = sheet.cell(questionrow, rule1col).value
Qrule2 = sheet.cell(questionrow, rule2col).value
Qref1 = sheet.cell(questionrow, refq1col).value
Qref2 = sheet.cell(questionrow, refq2col).value
Qref3 = sheet.cell(questionrow, refq3col).value


COASTAL_APPLICATION_PAGES = [
    {
        "title": questiontitle1 or "Personal Information",
        "questions": [
            ("gamertag", Qgamertag),
            ("country", Qcountry),
            ("age", Qage),
            ("gender", Qgender),
            ("platform", Qplatform),
        ],
    },
    {
        "title": questiontitle2 or "Application Questions",
        "questions": [
            ("question_1", Question1),
            ("question_2", Question2),
            ("question_3", Question3),
            ("question_4", Question4),
            ("question_5", Question5),
        ],
    },
    {
        "title": questiontitle3 or "Rules and References",
        "questions": [
            ("rule_1", Qrule1),
            ("rule_2", Qrule2),
            ("ref_1", Qref1),
            ("ref_2", Qref2),
            ("ref_3", Qref3),
        ],
    },
]


class CoastalApplicationContinueView(ui.View):
    def __init__(
        self,
        bot: commands.Bot,
        page_index: int,
        application_data: dict[str, str],
        user_id: int,
    ):
        super().__init__(timeout=300)
        self.bot = bot
        self.page_index = page_index
        self.application_data = application_data
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "This application belongs to another user.",
                ephemeral=True,
            )
            return False

        return True

    @ui.button(label="Continue Application", style=discord.ButtonStyle.primary)
    async def continue_application(
        self,
        interaction: discord.Interaction,
        button: ui.Button,
    ):
        try:
            await interaction.message.edit(
                content="✅ Continuing application...",
                view=None,
            )
        except Exception:
            logger.debug("Could not edit previous continue message.", exc_info=True)

        modal = CoastalApplicationModal(
            bot=self.bot,
            page_index=self.page_index,
            application_data=self.application_data,
            user_id=self.user_id,
        )

        await interaction.response.send_modal(modal)


class CoastalApplicationStartView(ui.View):
    def __init__(
        self,
        bot: commands.Bot,
        user_id: int,
    ):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "This application belongs to another user.",
                ephemeral=True,
            )
            return False

        return True

    @ui.button(label="Start Application", style=discord.ButtonStyle.primary)
    async def start_application(
        self,
        interaction: discord.Interaction,
        button: ui.Button,
    ):
        try:
            await interaction.message.edit(
                content="✅ Starting application...",
                embed=None,
                view=None,
            )
        except Exception:
            logger.debug("Could not edit previous start message.", exc_info=True)

        modal = CoastalApplicationModal(
            bot=self.bot,
            user_id=self.user_id,
        )

        await interaction.response.send_modal(modal)


class CoastalApplicationModal(ui.Modal):
    def __init__(
        self,
        bot: commands.Bot,
        page_index: int = 0,
        application_data: Optional[dict[str, str]] = None,
        user_id: Optional[int] = None,
    ):
        page = COASTAL_APPLICATION_PAGES[page_index]

        super().__init__(
            title=f"{page['title']} {page_index + 1}/{len(COASTAL_APPLICATION_PAGES)}",
            timeout=None,
        )

        self.bot = bot
        self.page_index = page_index
        self.application_data = application_data or {}
        self.user_id = user_id
        self.inputs: dict[str, ui.TextInput] = {}

        for key, question in page["questions"]:
            text_input = ui.TextInput(
                label=str(question)[:45],
                required=True,
                min_length=2,
                max_length=200,
                style=discord.TextStyle.long,
                default=self.application_data.get(key),
            )

            self.inputs[key] = text_input
            self.add_item(text_input)

    async def on_submit(self, interaction: discord.Interaction):
        if self.user_id is not None and interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "This application belongs to another user.",
                ephemeral=True,
            )
            return

        if self.user_id is None:
            self.user_id = interaction.user.id

        for key, text_input in self.inputs.items():
            self.application_data[key] = str(text_input.value).strip()

        next_page_index = self.page_index + 1

        if next_page_index < len(COASTAL_APPLICATION_PAGES):
            view = CoastalApplicationContinueView(
                bot=self.bot,
                page_index=next_page_index,
                application_data=self.application_data,
                user_id=self.user_id,
            )

            await interaction.response.send_message(
                f"✅ Page {self.page_index + 1} saved. Continue when ready.",
                view=view,
                ephemeral=True,
            )
            return

        await self.finish_application(interaction)

    async def finish_application(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            timestamp = datetime.now()
            author = interaction.user

            responseguild = self.bot.get_guild(config["Coastal"])

            if responseguild is None:
                await interaction.followup.send(
                    "Coastal Craft server could not be found.",
                    ephemeral=True,
                )
                return

            responseChannel = responseguild.get_channel(config["CoastalApplications"])
            admin = responseguild.get_role(config["CoastalOPTeam"])

            if responseChannel is None:
                await interaction.followup.send(
                    "Coastal application response channel is not configured correctly.",
                    ephemeral=True,
                )
                return

            if admin is None:
                await interaction.followup.send(
                    "Coastal OP Team role is not configured correctly.",
                    ephemeral=True,
                )
                return

            submittime = timestamp.strftime("%m/%d/%Y %H:%M:%S")
            entryID = int(sheet.acell("A3").value) + 1

            dname = str(author)
            dnick = str(author.display_name)
            longid = str(author.id)

            answerlist = [
                self.application_data.get("gamertag", ""),
                self.application_data.get("country", ""),
                self.application_data.get("age", ""),
                self.application_data.get("gender", ""),
                self.application_data.get("platform", ""),
                self.application_data.get("question_1", ""),
                self.application_data.get("question_2", ""),
                self.application_data.get("question_3", ""),
                self.application_data.get("question_4", ""),
                self.application_data.get("question_5", ""),
                self.application_data.get("rule_1", ""),
                self.application_data.get("rule_2", ""),
                self.application_data.get("ref_1", ""),
                self.application_data.get("ref_2", ""),
                self.application_data.get("ref_3", ""),
            ]

            row = [
                entryID,
                dname,
                dnick,
                longid,
                str(answerlist[0]),
                str(answerlist[1]),
                str(answerlist[2]),
                str(answerlist[3]),
                str(answerlist[4]),
                str(answerlist[5]),
                str(answerlist[6]),
                str(answerlist[7]),
                str(answerlist[8]),
                str(answerlist[9]),
                str(answerlist[10]),
                str(answerlist[11]),
                str(answerlist[12]),
                str(answerlist[13]),
                str(answerlist[14]),
                submittime,
            ]

            sheet.insert_row(row, 3, value_input_option="USER_ENTERED")

            embed1 = discord.Embed(
                title="Realm Application",
                description=(
                    "From\n"
                    f"Discord - {dname}\n"
                    f"AKA - {dnick}\n"
                    f"Long ID - {longid}\n"
                    "============================================"
                ),
                color=0x336F75,
            )

            embed1.set_thumbnail(
                url="https://cdn.discordapp.com/attachments/488792053002534920/1157338182392741999/coastal_logo_final_s9.png"
            )

            embed1.add_field(name=Qgamertag, value=str(answerlist[0]), inline=True)
            embed1.add_field(name=Qcountry, value=str(answerlist[1]), inline=True)
            embed1.add_field(name=Qage, value=str(answerlist[2]), inline=True)
            embed1.add_field(name=Qgender, value=str(answerlist[3]), inline=True)
            embed1.add_field(name=Qplatform, value=str(answerlist[4]), inline=False)
            embed1.add_field(name=Question1, value=str(answerlist[5]), inline=False)
            embed1.add_field(name=Question2, value=str(answerlist[6]), inline=False)
            embed1.add_field(name=Question3, value=str(answerlist[7]), inline=False)
            embed1.add_field(name=Question4, value=str(answerlist[8]), inline=False)
            embed1.add_field(name=Question5, value=str(answerlist[9]), inline=False)

            embed2 = discord.Embed(
                title=appreftitle,
                description=f"{apprefdesc}\n============================================",
                color=0x20F6B3,
            )

            embed2.add_field(name=Qrule1, value=str(answerlist[10]), inline=False)
            embed2.add_field(name=Qrule2, value=str(answerlist[11]), inline=False)
            embed2.add_field(name=Qref1, value=str(answerlist[12]), inline=False)
            embed2.add_field(name=Qref2, value=str(answerlist[13]), inline=False)
            embed2.add_field(name=Qref3, value=str(answerlist[14]), inline=False)

            embed2.add_field(
                name="__**Reaction Codes**__",
                value="Please react with the following codes to show your thoughts on this applicant.",
                inline=False,
            )
            embed2.add_field(name="----💚----", value="Approved", inline=True)
            embed2.add_field(name="----💛----", value="Not Sure", inline=True)
            embed2.add_field(name="----❤️----", value="Denied", inline=True)

            embed2.set_footer(text=f"Application #{entryID} | {submittime}")

            await responseChannel.send(admin.mention)
            await responseChannel.send(embed=embed1)
            msg2 = await responseChannel.send(embed=embed2)

            for emoji in ["💚", "💛", "❤️"]:
                await msg2.add_reaction(emoji)

            confirm_embed = discord.Embed(
                title="Realm Application Sent",
                description=f"{interaction.user.mention}",
                color=0x336F75,
            )
            confirm_embed.add_field(
                name=appTYtitle,
                value=appTYdesc,
                inline=False,
            )

            await interaction.followup.send(
                embed=confirm_embed,
                ephemeral=True,
            )

        except Exception as e:
            logger.exception(f"Error submitting Coastal application: {e}")

            await interaction.followup.send(
                "An error occurred while submitting your application.",
                ephemeral=True,
            )


class CoastalAppCMD(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="applycoastal",
        description="Apply to the Coastal Craft Discord Server",
    )
    @app_commands.guilds(config["MRP"])
    async def applycoastal(self, interaction: discord.Interaction[Any]):
        channel = interaction.channel

        if channel is None or channel.id != config["CoastalMRP"]:
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
            title=apptitle,
            description=appdesc,
            color=0x336F75,
        )

        introem2 = discord.Embed(
            title=appreftitle,
            description=apprefdesc,
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
    @app_commands.guilds(config["PBtest"], config["Coastal"])
    @app_commands.describe(appnumber="Application number to approve")
    @app_commands.checks.has_role("OP Team")
    async def approveapp(self, interaction: discord.Interaction, appnumber: str):
        DMStatus = "FALSE"
        author = interaction.user
        guild = interaction.guild
        mrpguild = self.bot.get_guild(config["MRP"])

        if guild is None or mrpguild is None:
            await interaction.response.send_message(
                "Could not find the required server data.",
                ephemeral=True,
            )
            return

        invitechannel = guild.get_channel(443614533815369728)

        if invitechannel is None:
            await interaction.response.send_message(
                "Invite channel could not be found.",
                ephemeral=True,
            )
            return

        invite = await invitechannel.create_invite(max_uses=1)
        row = sheet.find(str(appnumber), in_column=1).row

        userid = sheet.cell(row, 2).value
        user = mrpguild.get_member_named(userid)

        if user is None:
            userlongid = _safe_int(sheet.cell(row, 4).value)

            if userlongid is not None:
                user = mrpguild.get_member(userlongid)

                if user is None:
                    user = await mrpguild.fetch_member(userlongid)

        sheet.update_cell(row, 21, "Yes")

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

            await interaction.response.send_message(embed=response_embed)

    @app_commands.command(
        name="denyapp",
        description="Deny an Application!",
    )
    @app_commands.guilds(config["PBtest"], config["Coastal"])
    @app_commands.describe(appnumber="Application number to deny")
    @app_commands.checks.has_role("OP Team")
    async def denyapp(self, interaction: discord.Interaction, appnumber: str):
        DMStatus = "FALSE"
        author = interaction.user
        mrpguild = self.bot.get_guild(config["MRP"])

        if mrpguild is None:
            await interaction.response.send_message(
                "MRP server could not be found.",
                ephemeral=True,
            )
            return

        row = sheet.find(str(appnumber), in_column=1).row

        userid = sheet.cell(row, 2).value
        user = mrpguild.get_member_named(userid)

        if user is None:
            userlongid = _safe_int(sheet.cell(row, 4).value)

            if userlongid is not None:
                user = mrpguild.get_member(userlongid)

                if user is None:
                    user = await mrpguild.fetch_member(userlongid)

        sheet.update_cell(row, 21, "No")

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

            await interaction.response.send_message(embed=response_embed)


async def setup(bot):
    await bot.add_cog(CoastalAppCMD(bot))
