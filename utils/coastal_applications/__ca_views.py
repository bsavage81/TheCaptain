from typing import Optional
import discord
from discord import ui
from discord.ext import commands

from . import __ca_logic as logic

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
        if getattr(self, "consumed", False):
            await interaction.response.send_message("This page is already open.", ephemeral=True)
            return
        self.consumed = True
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
        if getattr(self, "consumed", False):
            await interaction.response.send_message("This page is already open.", ephemeral=True)
            return
        self.consumed = True
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

        suffix = f" {page_index + 1}/{len(bot.application_content.pages)}"
        super().__init__(title=str(page["title"])[:45 - len(suffix)] + suffix, timeout=300)

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
        await logic.finish_application(self, interaction)


