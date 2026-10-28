import asyncio
import discord


async def run_guide(cog, interaction):
    bot = cog.bot
    guild = bot.get_guild(bot.settings["Coastal"])
    role = guild.get_role(bot.settings["CoastalGuideRole"]) if guild else None
    active = guild.get_role(bot.settings["CoastalActiveRole"]) if guild else None
    responsechannel = guild.get_channel(bot.settings["CoastalGuideResponses"]) if guild else None
    author = guild.get_member(interaction.user.id) if guild else None
    if not all((role, active, responsechannel, author)):
        await interaction.response.send_message("Coastal guide roles, channel or member unavailable.", ephemeral=True)
        return
    if author.id in cog.sessions:
        await interaction.response.send_message("Finish your current guide first.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True, thinking=True)
    cog.sessions.add(author.id)
    try:
        channel = await interaction.user.create_dm()
        await interaction.followup.send("Check your DMs", ephemeral=True)
        await converse(bot, channel, author, role, active, responsechannel)
    except discord.HTTPException:
        await interaction.followup.send("Guide delivery or role assignment failed. Contact an OP.", ephemeral=True)
    finally:
        cog.sessions.discard(author.id)


async def converse(bot, channel, author, role, realmactiverole, responsechannel):
    def check(message):
        return message.content is not None and message.channel == channel and message.author.id == author.id

    embed = discord.Embed(
        title="Season 9 Guide Agreement",
        description="Read the guide, and then answer the questions that follow.",
        color=0x336F75,
    )
    embed.add_field(
        name="Online version of the guide",
        value="https://bit.ly/CoastalPlayersGuide9",
        inline=False,
    )
    embed.add_field(
        name="PDF version of the guide",
        value="https://bit.ly/Coastal9PGpdf",
        inline=False,
    )
    embed.set_thumbnail(
        url="https://cdn.discordapp.com/attachments/488792053002534920/1157338182392741999/coastal_logo_final_s9.png"
    )
    await channel.send(embed=embed)
    await channel.send("What drink do the OPs think is good?")
    try:
        while True:
            answer = await bot.wait_for("message", timeout=60.0, check=check)
            if answer.content.strip().casefold() == "cappuccino":
                await channel.send("Great Job!!!")
                break
            await channel.send("Wrong! Try again: ")
        await channel.send("Do you agree to the guide? Please answer yes or no.")
        answer = await bot.wait_for("message", timeout=60.0, check=check)
    except asyncio.TimeoutError:
        await channel.send("I grow tired of waiting, try again later...")
        return
    if answer.content.strip().casefold() == "yes":
        await author.add_roles(role)
        await author.add_roles(realmactiverole)
        await channel.send("Great! Have fun Playing Coastal Craft 9: Sakura Shores")
        embed = discord.Embed(title="Season 9 Guide Agreement", description=author.name + " has agreed to the season 9 guide!", color=0x000800)
        embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/488792053002534920/1157338182392741999/coastal_logo_final_s9.png")
        await responsechannel.send(embed=embed)
    else:
        await channel.send("Please get with an OP to discuss your concerns")
