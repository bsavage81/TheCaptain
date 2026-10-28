import asyncio


async def wait_answer(bot, channel, author):
    def check(message):
        return message.content is not None and message.channel == channel and message.author == author
    try:
        return await bot.wait_for("message", timeout=60, check=check)
    except asyncio.TimeoutError:
        await channel.send("I grow tired of waiting, try again later...")
        raise


import discord


async def addpoi_end_returngateway(self, interaction, x_coord, z_coord):
    responseguild = self.bot.get_guild(self.bot.settings['Coastal'])
    responseChannel = responseguild.get_channel(
        self.bot.settings['CoastalMapUpdates'])
    admin = responseguild.get_role(self.bot.settings['CoastalOPTeam'])
    channel = interaction.channel
    author = interaction.user
    dimension = "End"
    entryID = None
    dname = str(author.name + '#' + author.discriminator)
    if author.display_name == author.name:
        dnick = str(author.name)
    else:
        dnick = str(author.display_name)
    # Answer Check
    def check(m):
        return m.content is not None and m.channel == channel and m.author == author
    
    
    await interaction.response.send_message("Marker added")

    # Spreadsheet Data
      
    font = "900 10px 'Font Awesome 6 Free'"
    row = [
        entryID, x_coord, z_coord, "-1", "", "", "\uf52b",
        "Return Portal", "", "red", "#ffffff", "0", "0",
        font
    ]
    entryID = await self.bot.sheets.submit_poi(dimension, row)

    await channel.send("Success!")

    # Actual Embed with Responses
    embed1 = discord.Embed(
        title="New POI Entered",
        description="From\nDiscord - " + dname + "\nAKA - " + dnick +
        "\n============================================",
        color=0x336F75)
    embed1.set_thumbnail(
        url=
        "https://cdn.discordapp.com/attachments/488792053002534920/1157338182392741999/coastal_logo_final_s9.png"
    )
    embed1.add_field(name="X_Coord", value=str(x_coord), inline=True)
    embed1.add_field(name="Z_Coord", value=str(z_coord), inline=True)
    embed1.add_field(name="Marker Type",
                     value=str("End Return Gateway"),
                     inline=True)
    embed1.add_field(name="Text Line 1",
                     value=str("\uf52b"),
                     inline=False)
    embed1.add_field(name="Text Line 2",
                     value=str("Return Gateway"),
                     inline=False)

    await responseChannel.send(admin.mention)
    await responseChannel.send(embed=embed1)

async def addpoi_endcity_claim(self, interaction, x_coord, z_coord):
    responseguild = self.bot.get_guild(self.bot.settings['Coastal'])
    responseChannel = responseguild.get_channel(
        self.bot.settings['CoastalMapUpdates'])
    admin = responseguild.get_role(self.bot.settings['CoastalOPTeam'])
    channel = interaction.channel
    author = interaction.user
    dimension = "End"
    entryID = None
    dname = str(author.name + '#' + author.discriminator)
    if author.display_name == author.name:
        dnick = str(author.name)
    else:
        dnick = str(author.display_name)
    # Answer Check
    def check(m):
        return m.content is not None and m.channel == channel and m.author == author
    
    await interaction.response.send_message("Complete the Form")

    # Questions
    introem = discord.Embed(title="New POI Entry",
                            description=self.bot.poi_content.poidesc +
                            "\n**Questions will start in 3 seconds.**",
                            color=0x336F75)
    await channel.send(embed=introem)
    await asyncio.sleep(3)

    await channel.send("What is your gamertag?")
    answer1 = await wait_answer(self.bot, channel, author)
    await asyncio.sleep(.5)

    await channel.send(self.bot.poi_content.Qtextcolor)
    answer2 = await wait_answer(self.bot, channel, author)
    await asyncio.sleep(.5)

    # Spreadsheet Data
      
    font = "900 10px 'Font Awesome 6 Free'"
    row = [
        entryID, x_coord, z_coord, "-1", "", "", "\uf06a",
        answer1.content, "", answer2.content, "#ffffff", "0", "0",
        font
    ]
    entryID = await self.bot.sheets.submit_poi(dimension, row)

    await channel.send("Success!")

    # Actual Embed with Responses
    embed1 = discord.Embed(
        title="New POI Entered",
        description="From\nDiscord - " + dname + "\nAKA - " + dnick +
        "\n============================================",
        color=0x336F75)
    embed1.set_thumbnail(
        url=
        "https://cdn.discordapp.com/attachments/488792053002534920/1157338182392741999/coastal_logo_final_s9.png"
    )
    embed1.add_field(name="X_Coord", value=str(x_coord), inline=True)
    embed1.add_field(name="Z_Coord", value=str(z_coord), inline=True)
    embed1.add_field(name="Marker Type",
                     value=str("End City Claim"),
                     inline=True)
    embed1.add_field(name="Text Line 1",
                     value=str("\uf06a"),
                     inline=False)
    embed1.add_field(name="Text Line 2",
                     value=str(answer1.content),
                     inline=False)

    await responseChannel.send(admin.mention)
    await responseChannel.send(embed=embed1)

async def addpoi_end(self, interaction, x_coord, z_coord):
    responseguild = self.bot.get_guild(self.bot.settings['Coastal'])
    responseChannel = responseguild.get_channel(
        self.bot.settings['CoastalMapUpdates'])
    admin = responseguild.get_role(self.bot.settings['CoastalOPTeam'])
    channel = interaction.channel
    author = interaction.user
    dimension = "End"
    entryID = None
    dname = str(author.name + '#' + author.discriminator)
    if author.display_name == author.name:
        dnick = str(author.name)
    else:
        dnick = str(author.display_name)
    # Answer Check
    def check(m):
        return m.content is not None and m.channel == channel and m.author == author
    
    await interaction.response.send_message("Complete the Form")

    # Questions
    introem = discord.Embed(title="New End City Entry",
                            description=self.bot.poi_content.poidesc +
                            "\n**Questions will start in 3 seconds.**",
                            color=0x336F75)
    await channel.send(embed=introem)
    await asyncio.sleep(3)

    await channel.send(self.bot.poi_content.Qtext1)
    answer1 = await wait_answer(self.bot, channel, author)
    await asyncio.sleep(.5)

    await channel.send(self.bot.poi_content.Qtext2)
    answer2 = await wait_answer(self.bot, channel, author)
    await asyncio.sleep(.5)

    await channel.send(self.bot.poi_content.Qtext3)
    answer3 = await wait_answer(self.bot, channel, author)
    await asyncio.sleep(.5)

    await channel.send(self.bot.poi_content.Qtextcolor)
    answer4 = await wait_answer(self.bot, channel, author)
    await asyncio.sleep(.5)

    await channel.send(self.bot.poi_content.Qmarkertype)
    answer5 = await wait_answer(self.bot, channel, author)
    await asyncio.sleep(.5)
    
    # Spreadsheet Data
    if answer2.content == "no" or answer2.content == "No":
        text2content = ""
    else:
        text2content = answer2.content

    if answer3.content == "no" or answer3.content == "No":
        text3content = ""
    else:
        text3content = answer3.content

    if answer5.content == "base" or answer5.content == "Base":
        font = "900 8px 'Font Awesome 6 Free'"
    elif answer5.content == "shop" or answer5.content == "Shop":
        font = "900 10px 'Font Awesome 6 Free'"
    elif answer5.content == "portal" or answer5.content == "Portal":
        font = "900 12px 'Font Awesome 6 Free'"
    else:
        font = "900 8px 'Font Awesome 6 Free'"

    row = [
        entryID, x_coord, z_coord, "-1", "", "", answer1.content,
        text2content, text3content, answer4.content, "#ffffff", "0", "0",
        font
    ]
    entryID = await self.bot.sheets.submit_poi(dimension, row)

    await channel.send("Success!")

    # Actual Embed with Responses
    embed1 = discord.Embed(
        title="New POI Entered",
        description="From\nDiscord - " + dname + "\nAKA - " + dnick +
        "\n============================================",
        color=0x336F75)
    embed1.set_thumbnail(
        url=
        "https://cdn.discordapp.com/attachments/488792053002534920/1157338182392741999/coastal_logo_final_s9.png"
    )
    embed1.add_field(name="X_Coord", value=str(x_coord), inline=True)
    embed1.add_field(name="Z_Coord", value=str(z_coord), inline=True)
    embed1.add_field(name="Marker Type",
                     value=str(answer5.content),
                     inline=True)
    embed1.add_field(name="Text Line 1",
                     value=str(answer1.content),
                     inline=False)
    embed1.add_field(name="Text Line 2",
                     value=str(answer2.content),
                     inline=False)
    embed1.add_field(name="Text Line 3",
                     value=str(answer3.content),
                     inline=False)

    await responseChannel.send(admin.mention)
    await responseChannel.send(embed=embed1)

async def addpoi_nether(self, interaction, x_coord, z_coord):
    responseguild = self.bot.get_guild(self.bot.settings['Coastal'])
    responseChannel = responseguild.get_channel(
        self.bot.settings['CoastalMapUpdates'])
    admin = responseguild.get_role(self.bot.settings['CoastalOPTeam'])
    channel = interaction.channel
    author = interaction.user
    dimension = "Nether"
    entryID = None
    dname = str(author.name + '#' + author.discriminator)
    if author.display_name == author.name:
        dnick = str(author.name)
    else:
        dnick = str(author.display_name)
    # Answer Check
    def check(m):
        return m.content is not None and m.channel == channel and m.author == author
    
    await interaction.response.send_message("Complete the Form")

    # Questions
    introem = discord.Embed(title="New POI Entry",
                            description=self.bot.poi_content.poidesc +
                            "\n**Questions will start in 3 seconds.**",
                            color=0x336F75)
    await channel.send(embed=introem)
    await asyncio.sleep(3)

    await channel.send(self.bot.poi_content.Qtext1)
    answer1 = await wait_answer(self.bot, channel, author)
    await asyncio.sleep(.5)

    await channel.send(self.bot.poi_content.Qtext2)
    answer2 = await wait_answer(self.bot, channel, author)
    await asyncio.sleep(.5)

    await channel.send(self.bot.poi_content.Qtext3)
    answer3 = await wait_answer(self.bot, channel, author)
    await asyncio.sleep(.5)

    await channel.send(self.bot.poi_content.Qtextcolor)
    answer4 = await wait_answer(self.bot, channel, author)
    await asyncio.sleep(.5)

    await channel.send(self.bot.poi_content.Qmarkertype)
    answer5 = await wait_answer(self.bot, channel, author)
    await asyncio.sleep(.5)
    # Spreadsheet Data
    if answer2.content == "no" or answer2.content == "No":
        text2content = ""
    else:
        text2content = answer2.content

    if answer3.content == "no" or answer3.content == "No":
        text3content = ""
    else:
        text3content = answer3.content

    if answer5.content == "base" or answer5.content == "Base":
        font = "900 8px 'Font Awesome 6 Free'"
    elif answer5.content == "shop" or answer5.content == "Shop":
        font = "900 10px 'Font Awesome 6 Free'"
    elif answer5.content == "portal" or answer5.content == "Portal":
        font = "900 12px 'Font Awesome 6 Free'"
    else:
        font = "900 8px 'Font Awesome 6 Free'"

    row = [
        entryID, x_coord, z_coord, "-1", "", "", answer1.content,
        text2content, text3content, answer4.content, "#ffffff", "0", "0",
        font
    ]
    entryID = await self.bot.sheets.submit_poi(dimension, row)

    await channel.send("Success!")

    # Actual Embed with Responses
    embed1 = discord.Embed(
        title="New POI Entered",
        description="From\nDiscord - " + dname + "\nAKA - " + dnick +
        "\n============================================",
        color=0x336F75)
    embed1.set_thumbnail(
        url=
        "https://cdn.discordapp.com/attachments/488792053002534920/1157338182392741999/coastal_logo_final_s9.png"
    )
    embed1.add_field(name="X_Coord", value=str(x_coord), inline=True)
    embed1.add_field(name="Z_Coord", value=str(z_coord), inline=True)
    embed1.add_field(name="Marker Type",
                     value=str(answer5.content),
                     inline=True)
    embed1.add_field(name="Text Line 1",
                     value=str(answer1.content),
                     inline=False)
    embed1.add_field(name="Text Line 2",
                     value=str(answer2.content),
                     inline=False)
    embed1.add_field(name="Text Line 3",
                     value=str(answer3.content),
                     inline=False)

    await responseChannel.send(admin.mention)
    await responseChannel.send(embed=embed1)

async def addpoi_overworld(self, interaction, x_coord, z_coord):
    responseguild = self.bot.get_guild(self.bot.settings['Coastal'])
    responseChannel = responseguild.get_channel(
        self.bot.settings['CoastalMapUpdates'])
    admin = responseguild.get_role(self.bot.settings['CoastalOPTeam'])
    channel = interaction.channel
    author = interaction.user
    dimension = "Overworld"
    entryID = None
    dname = str(author.name + '#' + author.discriminator)
    if author.display_name == author.name:
        dnick = str(author.name)
    else:
        dnick = str(author.display_name)
    # Answer Check
    def check(m):
        return m.content is not None and m.channel == channel and m.author == author
    
    await interaction.response.send_message("Complete the Form")

    # Questions
    introem = discord.Embed(title="New POI Entry",
                            description=self.bot.poi_content.poidesc +
                            "\n**Questions will start in 3 seconds.**",
                            color=0x336F75)
    await channel.send(embed=introem)
    await asyncio.sleep(3)

    await channel.send(self.bot.poi_content.Qtext1)
    answer1 = await wait_answer(self.bot, channel, author)
    await asyncio.sleep(.5)

    await channel.send(self.bot.poi_content.Qtext2)
    answer2 = await wait_answer(self.bot, channel, author)
    await asyncio.sleep(.5)

    await channel.send(self.bot.poi_content.Qtext3)
    answer3 = await wait_answer(self.bot, channel, author)
    await asyncio.sleep(.5)

    await channel.send(self.bot.poi_content.Qtextcolor)
    answer4 = await wait_answer(self.bot, channel, author)
    await asyncio.sleep(.5)

    await channel.send(self.bot.poi_content.Qmarkertype)
    answer5 = await wait_answer(self.bot, channel, author)
    await asyncio.sleep(.5)
    # Spreadsheet Data
    if answer2.content == "no" or answer2.content == "No":
        text2content = ""
    else:
        text2content = answer2.content

    if answer3.content == "no" or answer3.content == "No":
        text3content = ""
    else:
        text3content = answer3.content

    if answer5.content == "base" or answer5.content == "Base":
        font = "900 8px 'Font Awesome 6 Free'"
    elif answer5.content == "shop" or answer5.content == "Shop":
        font = "900 10px 'Font Awesome 6 Free'"
    elif answer5.content == "portal" or answer5.content == "Portal":
        font = "900 12px 'Font Awesome 6 Free'"
    else:
        font = "900 8px 'Font Awesome 6 Free'"

    row = [
        entryID, x_coord, z_coord, "-1", "", "", answer1.content,
        text2content, text3content, answer4.content, "#ffffff", "0", "0",
        font
    ]
    entryID = await self.bot.sheets.submit_poi(dimension, row)

    await channel.send("Success!")

    # Actual Embed with Responses
    embed1 = discord.Embed(
        title="New POI Entered",
        description="From\nDiscord - " + dname + "\nAKA - " + dnick +
        "\n============================================",
        color=0x336F75)
    embed1.set_thumbnail(
        url=
        "https://cdn.discordapp.com/attachments/488792053002534920/1157338182392741999/coastal_logo_final_s9.png"
    )
    embed1.add_field(name="X_Coord", value=str(x_coord), inline=True)
    embed1.add_field(name="Z_Coord", value=str(z_coord), inline=True)
    embed1.add_field(name="Marker Type",
                     value=str(answer5.content),
                     inline=True)
    embed1.add_field(name="Text Line 1",
                     value=str(answer1.content),
                     inline=False)
    embed1.add_field(name="Text Line 2",
                     value=str(answer2.content),
                     inline=False)
    embed1.add_field(name="Text Line 3",
                     value=str(answer3.content),
                     inline=False)

    await responseChannel.send(admin.mention)
    await responseChannel.send(embed=embed1)


async def run_poi(cog, interaction, x_coord, z_coord, operation):
    # One conversation per user/channel, avoiding messages satisfying multiple sessions.
    key = (interaction.channel_id, interaction.user.id)
    sessions = getattr(cog, "sessions", None)
    if sessions is None:
        cog.sessions = sessions = set()
    if key in sessions:
        await interaction.response.send_message("Finish your current POI first.", ephemeral=True)
        return
    sessions.add(key)
    try:
        await operation(cog, interaction, x_coord, z_coord)
    except asyncio.TimeoutError:
        return
    except Exception:
        await interaction.followup.send("POI operation failed. A write or notification may have completed; contact an OP before retrying.", ephemeral=True)
    finally:
        sessions.discard(key)
