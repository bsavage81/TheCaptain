"""Error reporting intentionally excludes exception text and applicant input."""
import logging
from discord import app_commands
from discord.ext import commands

log = logging.getLogger(__name__)


async def on_app_command_error_(bot, interaction, error):
    message = "You cannot run this command!" if isinstance(error, app_commands.CheckFailure) else "The operation failed. Contact an OP before retrying a submission."
    log.warning("Application command failed (%s)", type(getattr(error, "original", error)).__name__)
    send = interaction.followup.send if interaction.response.is_done() else interaction.response.send_message
    await send(message, ephemeral=True)


async def on_command_error_(bot, ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    log.warning("Prefix command failed (%s)", type(getattr(error, "original", error)).__name__)
    await ctx.send("Command failed. Check permissions and arguments.")
