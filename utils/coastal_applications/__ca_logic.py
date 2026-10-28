import logging
from datetime import datetime
import discord

logger = logging.getLogger(__name__)

def _safe_int(value):
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


from types import SimpleNamespace

CONTENT_CELLS = {'apptitle': (1, 1), 'appdesc': (1, 2), 'appreftitle': (1, 3), 'apprefdesc': (1, 4), 'appTYtitle': (1, 5), 'appTYdesc': (1, 6), 'questiontitle1': (1, 7), 'questiontitle2': (1, 8), 'questiontitle3': (1, 9), 'Qgamertag': (2, 5), 'Qcountry': (2, 6), 'Qage': (2, 7), 'Qgender': (2, 8), 'Qplatform': (2, 9), 'Question1': (2, 10), 'Question2': (2, 11), 'Question3': (2, 12), 'Question4': (2, 13), 'Question5': (2, 14), 'Qrule1': (2, 15), 'Qrule2': (2, 16), 'Qref1': (2, 17), 'Qref2': (2, 18), 'Qref3': (2, 19)}


def load_content(sheet):
    apptitle = sheet.cell(1, 1).value
    appdesc = sheet.cell(1, 2).value
    appreftitle = sheet.cell(1, 3).value
    apprefdesc = sheet.cell(1, 4).value
    appTYtitle = sheet.cell(1, 5).value
    appTYdesc = sheet.cell(1, 6).value
    questiontitle1 = sheet.cell(1, 7).value
    questiontitle2 = sheet.cell(1, 8).value
    questiontitle3 = sheet.cell(1, 9).value
    Qgamertag = sheet.cell(2, 5).value
    Qcountry = sheet.cell(2, 6).value
    Qage = sheet.cell(2, 7).value
    Qgender = sheet.cell(2, 8).value
    Qplatform = sheet.cell(2, 9).value
    Question1 = sheet.cell(2, 10).value
    Question2 = sheet.cell(2, 11).value
    Question3 = sheet.cell(2, 12).value
    Question4 = sheet.cell(2, 13).value
    Question5 = sheet.cell(2, 14).value
    Qrule1 = sheet.cell(2, 15).value
    Qrule2 = sheet.cell(2, 16).value
    Qref1 = sheet.cell(2, 17).value
    Qref2 = sheet.cell(2, 18).value
    Qref3 = sheet.cell(2, 19).value

    pages = [
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
    return SimpleNamespace(pages=pages, apptitle=apptitle, appdesc=appdesc, appreftitle=appreftitle, apprefdesc=apprefdesc, appTYtitle=appTYtitle, appTYdesc=appTYdesc, questiontitle1=questiontitle1, questiontitle2=questiontitle2, questiontitle3=questiontitle3, Qgamertag=Qgamertag, Qcountry=Qcountry, Qage=Qage, Qgender=Qgender, Qplatform=Qplatform, Question1=Question1, Question2=Question2, Question3=Question3, Question4=Question4, Question5=Question5, Qrule1=Qrule1, Qrule2=Qrule2, Qref1=Qref1, Qref2=Qref2, Qref3=Qref3)


async def finish_application(self, interaction):
    await interaction.response.defer(ephemeral=True, thinking=True)
    try:
        timestamp = datetime.now()
        author = interaction.user
        responseguild = self.bot.get_guild(self.bot.settings["Coastal"])
        if responseguild is None:
            await interaction.followup.send(
                "Coastal Craft server could not be found.",
                ephemeral=True,
            )
            return
        responseChannel = responseguild.get_channel(self.bot.settings["CoastalApplications"])
        admin = responseguild.get_role(self.bot.settings["CoastalOPTeam"])
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
        entryID = None
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
        if getattr(self, "submission_attempted", False):
            await interaction.followup.send("Submission already attempted. Contact an OP before retrying.", ephemeral=True)
            return
        self.submission_attempted = True
        entryID = await self.bot.sheets.submit_application(row)
        self.saved_entry_id = entryID
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
            url=self.bot.settings.get("logo_url")
        )
        embed1.add_field(name=self.bot.application_content.Qgamertag, value=str(answerlist[0]), inline=True)
        embed1.add_field(name=self.bot.application_content.Qcountry, value=str(answerlist[1]), inline=True)
        embed1.add_field(name=self.bot.application_content.Qage, value=str(answerlist[2]), inline=True)
        embed1.add_field(name=self.bot.application_content.Qgender, value=str(answerlist[3]), inline=True)
        embed1.add_field(name=self.bot.application_content.Qplatform, value=str(answerlist[4]), inline=False)
        embed1.add_field(name=self.bot.application_content.Question1, value=str(answerlist[5]), inline=False)
        embed1.add_field(name=self.bot.application_content.Question2, value=str(answerlist[6]), inline=False)
        embed1.add_field(name=self.bot.application_content.Question3, value=str(answerlist[7]), inline=False)
        embed1.add_field(name=self.bot.application_content.Question4, value=str(answerlist[8]), inline=False)
        embed1.add_field(name=self.bot.application_content.Question5, value=str(answerlist[9]), inline=False)
        embed2 = discord.Embed(
            title=self.bot.application_content.appreftitle,
            description=f"{self.bot.application_content.apprefdesc}\n============================================",
            color=0x20F6B3,
        )
        embed2.add_field(name=self.bot.application_content.Qrule1, value=str(answerlist[10]), inline=False)
        embed2.add_field(name=self.bot.application_content.Qrule2, value=str(answerlist[11]), inline=False)
        embed2.add_field(name=self.bot.application_content.Qref1, value=str(answerlist[12]), inline=False)
        embed2.add_field(name=self.bot.application_content.Qref2, value=str(answerlist[13]), inline=False)
        embed2.add_field(name=self.bot.application_content.Qref3, value=str(answerlist[14]), inline=False)
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
            name=self.bot.application_content.appTYtitle,
            value=self.bot.application_content.appTYdesc,
            inline=False,
        )
        await interaction.followup.send(
            embed=confirm_embed,
            ephemeral=True,
        )
    except Exception as e:
        logger.warning("Application submission failed (%s)", type(e).__name__)
        await interaction.followup.send(
            f"Application #{self.saved_entry_id} was saved, but notification failed. Contact an OP; do not resubmit." if hasattr(self, "saved_entry_id") else "Submission failed; its write status may be uncertain. Contact an OP before retrying.",
            ephemeral=True,
        )


async def denyapp(self, interaction, appnumber):
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
        url=self.bot.settings.get("logo_url")
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
            url=self.bot.settings.get("logo_url")
        )
        await interaction.followup.send(embed=response_embed)


async def approveapp(self, interaction, appnumber):
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
        url=self.bot.settings.get("logo_url")
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
            url=self.bot.settings.get("logo_url")
        )
        await interaction.followup.send(embed=response_embed)
