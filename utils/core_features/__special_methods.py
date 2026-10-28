"""Ready display and sanitized error reporting without import-time service access."""
import asyncio
import logging
import subprocess
from datetime import datetime
from .__constants import ROOT
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


CAPTAIN_BANNER = r"""
  _____ _            ____            _        _
 |_   _| |__   ___  / ___|__ _ _ __ | |_ __ _(_)_ __
   | | | '_ \ / _ \| |   / _` | '_ \| __/ _` | | '_ \
   | | | | | |  __/| |__| (_| | |_) | || (_| | | | | |
   |_| |_| |_|\___| \____\__,_| .__/ \__\__,_|_|_| |_|
                              |_|
"""


def get_revision():
    """Read the checkout's current commit at ready time, with no extra Git library."""
    try:
        result = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                                text=True, capture_output=True, check=True, timeout=3)
        return result.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def format_ready_banner(bot, revision, now=None):
    import discord
    host = bot.settings.get("database_ip") or "not configured"
    location = "Local" if host in {"localhost", "127.0.0.1", "::1"} else "External"
    timestamp = (now or datetime.now().astimezone()).strftime("%Y-%m-%d %H:%M:%S.%f %Z").rstrip()
    account = bot.user.name if bot.user is not None else "unavailable"
    return f"""{CAPTAIN_BANNER}
        Bot Account: {account}
        Discord API Wrapper Version: {discord.__version__}
        The Captain Version: {revision}

        Selected Database: {location} ({host})

        Current Time: {timestamp}
        Cogs, libraries, and views have successfully been initialized.
        ==================================================
        Statistics

        Guilds: {len(bot.guilds)}
        Members: {len(bot.users)}
"""


async def on_ready_(bot):
    revision = await asyncio.to_thread(get_revision)
    print(format_ready_banner(bot, revision), flush=True)
