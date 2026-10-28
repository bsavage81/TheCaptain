from typing import Union, Literal

import discord
from discord import ui, ButtonStyle
from discord.ext import commands

from utils.helpers.__checks import is_botAdmin3
from utils.core_features.__common import Colors, ButtonHandler
from utils.helpers.__logging_module import get_log

_log = get_log(__name__)


class BackupRegularCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @is_botAdmin3
    async def sync(
        self,
        ctx: commands.Context,
        action: Union[Literal["global"], Literal["all"], discord.Guild],
    ):
        if isinstance(action, discord.Guild):
            guild = action

            embed_processing = discord.Embed(
                color=discord.Color.gold(),
                title="Sync",
                description=f"Syncing slash commands for guild `{guild.name}`...",
            )
            message_sync = await ctx.send(embed=embed_processing)

            await self.bot.tree.sync(guild=discord.Object(guild.id))

            embed_done = discord.Embed(
                color=discord.Color.green(),
                title="Sync",
                description=f"Successfully synced slash commands for guild `{guild.name}`!",
            )
            await message_sync.edit(embed=embed_done)

        elif action == "global":

            view = ui.View(timeout=30)
            button_confirm = ButtonHandler(
                style=ButtonStyle.green,
                label="Confirm",
                emoji="✅",
                button_user=ctx.author,
            )
            button_cancel = ButtonHandler(
                style=ButtonStyle.red, label="Cancel", emoji="❌", button_user=ctx.author
            )
            view.add_item(button_confirm)
            view.add_item(button_cancel)

            embed_confirm = discord.Embed(
                color=discord.Color.gold(),
                title="Sync Confirmation",
                description="Are you sure you want to sync globally? This may take 1 hour.",
            )
            message_confirm = await ctx.send(embed=embed_confirm, view=view)

            timeout = await view.wait()
            if not timeout:
                if view.value == "Confirm":

                    embed_processing = discord.Embed(
                        color=discord.Color.gold(),
                        title="Sync",
                        description="Syncing slash commands globally..."
                        "\nThis may take a while.",
                    )
                    await message_confirm.edit(embed=embed_processing, view=None)

                    await self.bot.tree.sync()

                    embed_processing = discord.Embed(
                        color=discord.Color.green(),
                        title="Sync",
                        description="Successfully synced slash commands globally!",
                    )
                    await message_confirm.edit(embed=embed_processing)

                elif view.value == "Cancel":
                    embed_cancel = discord.Embed(
                        color=Colors.red, title="Sync", description="Sync canceled."
                    )
                    await message_confirm.edit(embed=embed_cancel, view=None)

            else:
                embed_timeout = discord.Embed(
                    color=Colors.red,
                    title="Sync",
                    description="Sync canceled due to timeout.",
                )
                await message_confirm.edit(embed=embed_timeout, view=None)

        elif action == "all":

            view = ui.View(timeout=30)
            button_confirm = ButtonHandler(
                style=ButtonStyle.green,
                label="Confirm",
                emoji="✅",
                button_user=ctx.author,
            )
            button_cancel = ButtonHandler(
                style=ButtonStyle.red, label="Cancel", emoji="❌", button_user=ctx.author
            )
            view.add_item(button_confirm)
            view.add_item(button_cancel)

            embed_confirm = discord.Embed(
                color=discord.Color.gold(),
                title="Sync Confirmation",
                description="Are you sure you want to sync all local guild commands?",
            )
            message_confirm = await ctx.send(embed=embed_confirm, view=view)

            timeout = await view.wait()
            if not timeout:
                if view.value == "Confirm":

                    embed_processing = discord.Embed(
                        color=discord.Color.gold(),
                        title="Sync",
                        description="Syncing all local guild slash commands ..."
                        "\nThis may take a while.",
                    )
                    await message_confirm.edit(embed=embed_processing, view=None)

                    for guild in self.bot.guilds:
                        await self.bot.tree.sync(guild=discord.Object(guild.id))

                    embed_processing = discord.Embed(
                        color=discord.Color.green(),
                        title="Sync",
                        description="Successfully synced slash commands in all servers!",
                    )
                    await message_confirm.edit(embed=embed_processing)

                elif view.value == "Cancel":
                    embed_cancel = discord.Embed(
                        color=Colors.red, title="Sync", description="Sync canceled."
                    )
                    await message_confirm.edit(embed=embed_cancel, view=None)

            else:
                embed_timeout = discord.Embed(
                    color=Colors.red,
                    title="Sync",
                    description="Sync canceled due to timeout.",
                )
                await message_confirm.edit(embed=embed_timeout, view=None)


async def setup(bot):
    await bot.add_cog(BackupRegularCommands(bot))