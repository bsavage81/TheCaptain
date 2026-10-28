import discord
from discord.ext import commands
from discord import app_commands

class RepeatCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='repeat', description='Repeats what you type')
    @app_commands.describe(
        message="Phrase to repeat"
    )    
    async def repeat(self, interaction: discord.Interaction, message: str):
        await interaction.response.send_message(message)

async def setup(bot):
    await bot.add_cog(RepeatCog(bot))