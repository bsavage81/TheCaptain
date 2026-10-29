"""Thin Captain lifecycle. Import is safe without configuration or credentials."""
import asyncio
import logging
import time
import discord
from discord import app_commands
from discord.ext import commands
from utils.core_features.__constants import EXTENSIONS, ROOT
from utils.configuration import load_bootstrap
from utils.core_features.__special_methods import on_app_command_error_, on_command_error_, on_ready_
from utils.database.__database import initialize_database, is_administrator
from utils.integrations.__google_sheets import SheetsService


class CaptainCommandTree(app_commands.CommandTree):
    async def interaction_check(self, interaction):
        if interaction.user.avatar is None:
            await interaction.response.send_message("Due to a discord limitation, you must have an avatar set to use this command.")
            return False
        return True

    async def on_error(self, interaction, error):
        await on_app_command_error_(self.client, interaction, error)


class TheCaptain(commands.Bot):
    def __init__(self, settings, *, sheets=None, database_initializer=initialize_database, admin_check=is_administrator):
        super().__init__(command_prefix=commands.when_mentioned_or(">"), intents=discord.Intents.all(),
                         case_insensitive=True, tree_cls=CaptainCommandTree)
        self.settings = settings
        self.sheets = sheets if sheets is not None else SheetsService(settings)
        self.database_initializer = database_initializer
        self.admin_check = admin_check
        self.help_command = None
        self._start_time = time.time()

    async def setup_hook(self):
        row = await asyncio.to_thread(self.database_initializer, self.settings)
        self.command_prefix = commands.when_mentioned_or(row.prefix)
        await self.sheets.initialize()
        self.application_content = self.sheets.application_content
        self.poi_content = self.sheets.poi_content
        self.guide_content = self.sheets.guide_content
        for extension in EXTENSIONS:
            if extension not in self.extensions:
                await self.load_extension(extension)
        if self.settings.get("profiles_enabled") and "utils.players.cog" not in self.extensions:
            await self.load_extension("utils.players.cog")

    async def on_ready(self):
        logging.getLogger(__name__).info("TheCaptain ready")
        await on_ready_(self)

    async def is_owner(self, user):
        return await asyncio.to_thread(self.admin_check, user.id, 3) or await super().is_owner(user)

    async def on_command_error(self, ctx, error):
        await on_command_error_(self, ctx, error)

    async def on_command(self, ctx):
        if ctx.command and ctx.command.name not in {"sync", "ping", "kill", "jsk", "py", "jishaku"}:
            await ctx.reply(f":x: This command usage is deprecated. Use `/{ctx.command.name}` instead.")

    @property
    def start_time(self):
        return self._start_time


def main():
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    settings = load_bootstrap()
    if not settings.get("token"):
        raise ValueError("Configure token before startup")
    logging.basicConfig(level=logging.INFO)
    TheCaptain(settings).run(settings["token"])


if __name__ == "__main__":
    main()
