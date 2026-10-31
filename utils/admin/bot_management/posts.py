"""Staff-authored messages posted by The Captain."""
import discord
from discord import app_commands
from discord.ext import commands

from utils.core_features.__common import coastal_command_guilds
from utils.helpers.__checks import op_team, require_op_team


class PostModal(discord.ui.Modal, title="Post as The Captain"):
    content = discord.ui.TextInput(
        label="Message", style=discord.TextStyle.paragraph, max_length=2000,
        placeholder="Write your post here. Discord formatting is supported.",
    )

    def __init__(self, author_id, channel):
        super().__init__(timeout=600)
        self.author_id = author_id
        self.channel = channel

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("This composer belongs to another staff member.", ephemeral=True)
            return
        # Recheck access at submission in case roles or channel permissions changed.
        await require_op_team(interaction)
        permissions = self.channel.permissions_for(interaction.user)
        bot_permissions = self.channel.permissions_for(interaction.guild.me)
        if not (permissions.view_channel and permissions.send_messages
                and bot_permissions.view_channel and bot_permissions.send_messages):
            await interaction.response.send_message(
                "You and The Captain must both be able to view and send messages in that channel.", ephemeral=True)
            return
        content = self.content.value.strip()
        if not content:
            await interaction.response.send_message("Please enter a message.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            message = await self.channel.send(content, allowed_mentions=discord.AllowedMentions.all())
        except discord.HTTPException:
            await interaction.followup.send(
                "Discord did not confirm the post. Check the destination before trying again.", ephemeral=True)
            return
        await interaction.followup.send(f"Posted: {message.jump_url}", ephemeral=True)

    async def on_error(self, interaction, error):
        await interaction.client.tree.on_error(interaction, error)


class CaptainPosts(commands.Cog):
    @app_commands.command(name="post", description="Write a message for The Captain to post.")
    @app_commands.guild_only()
    @op_team()
    @app_commands.describe(channel="Destination channel; defaults to this channel.")
    async def post(self, interaction: discord.Interaction, channel: discord.TextChannel | None = None):
        destination = channel or interaction.channel
        if not isinstance(destination, discord.TextChannel) or destination.guild.id != interaction.guild_id:
            await interaction.response.send_message("Choose a text channel in this server.", ephemeral=True)
            return
        await interaction.response.send_modal(PostModal(interaction.user.id, destination))


async def setup(bot):
    cog = CaptainPosts()
    for command in cog.get_app_commands():
        command._guild_ids = list(dict.fromkeys(coastal_command_guilds(bot.settings)))
    await bot.add_cog(cog)
