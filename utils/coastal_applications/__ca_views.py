from typing import Optional
from datetime import datetime
import logging
import discord
from discord import ui
from discord.ext import commands

logger = logging.getLogger(__name__)

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
        self.stop()
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
        self.stop()
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
        page = bot.application_content.pages[page_index]

        super().__init__(
            title=f"{page['title']} {page_index + 1}/{len(bot.application_content.pages)}",
            timeout=300,
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

        if next_page_index < len(self.bot.application_content.pages):
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
                url="https://cdn.discordapp.com/attachments/488792053002534920/1157338182392741999/coastal_logo_final_s9.png"
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


