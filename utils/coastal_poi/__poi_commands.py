import os
from os import system
from logging import exception
import discord  
from discord.ext import commands    
from discord import app_commands
import time
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import asyncio
from utils.core_features.__common import load_config

config, _ = load_config()
i = 1
time_convert = {"s": 1, "m": 60, "h": 3600, "d": 86400}
import logging

logger = logging.getLogger(__name__)

# -------------------------------------------------------


def next_available_row(sheet):
    str_list = list(filter(None, sheet.col_values(1)))
    return str(len(str_list) + 1)


def entryid_number(sheet):
    str_list = list(filter(None, sheet.col_values(1)))
    return str(len(str_list) - 2)


scope = [
    "https://spreadsheets.google.com/feeds",
    'https://www.googleapis.com/auth/spreadsheets',
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive"
]

creds = ServiceAccountCredentials.from_json_keyfile_name("creds.json", scope)

client = gspread.authorize(creds)

cmsheet = client.open("Coastal Markers")

overworldsheet = cmsheet.worksheet("Overworld")

nethersheet = cmsheet.worksheet("Nether")

endsheet = cmsheet.worksheet("End")

questionsheet = cmsheet.worksheet("Questions")

# ---CONSTANTS----------------------------------------------------

newmarkerrow = 2
entryidcol = 1
xcol = 2
ycol = 3
minmapzoomcol = 4
imagecol = 5
imageanchorcol = 6
text1col = 7
text2col = 8
text3col = 9
textcolorcol = 10
strokecolorcol = 11
offsetxcol = 12
offsetycol = 13
fontcol = 14
poidesc = questionsheet.acell("B1").value
Qtext1 = questionsheet.acell("B2").value
Qtext2 = questionsheet.acell("B3").value
Qtext3 = questionsheet.acell("B4").value
Qtextcolor = questionsheet.acell("B5").value
Qmarkertype = questionsheet.acell("B6").value

# -------------------------------------------------------

def convert(time):
    try:
        return int(time[:-1]) * time_convert[time[-1]]
    except:
        return time


class CoastalPOICMD(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        logger.info("RealmCMD: Cog Loaded!")

    @app_commands.command(name="addpoi_overworld",
                   description="Add a POI to the Overworld!")
    @app_commands.guilds(config['PBtest'], config['Coastal'])
    async def addpoi_overworld(self, interaction: discord.Interaction, x_coord: int, z_coord: int):
        responseguild = self.bot.get_guild(config['Coastal'])
        responseChannel = responseguild.get_channel(
            config['CoastalMapUpdates'])
        admin = responseguild.get_role(config['CoastalOPTeam'])
        channel = interaction.channel
        author = interaction.user
        currentsheet = overworldsheet
        entryID = (int(currentsheet.acell('A2').value) + 1)
        print(entryID)
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
                                description=poidesc +
                                "\n**Questions will start in 3 seconds.**",
                                color=0x336F75)
        await channel.send(embed=introem)
        await asyncio.sleep(3)

        await channel.send(Qtext1)
        answer1 = await self.bot.wait_for('message', check=check)
        await asyncio.sleep(.5)

        await channel.send(Qtext2)
        answer2 = await self.bot.wait_for('message', check=check)
        await asyncio.sleep(.5)

        await channel.send(Qtext3)
        answer3 = await self.bot.wait_for('message', check=check)
        await asyncio.sleep(.5)

        await channel.send(Qtextcolor)
        answer4 = await self.bot.wait_for('message', check=check)
        await asyncio.sleep(.5)

        await channel.send(Qmarkertype)
        answer5 = await self.bot.wait_for('message', check=check)
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
        currentsheet.insert_row(row, 2, value_input_option='USER_ENTERED')

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

    @app_commands.command(name="addpoi_nether",
                   description="Add a POI to the Nether!")
    @app_commands.guilds(config['PBtest'], config['Coastal'])
    async def addpoi_nether(self, interaction: discord.Interaction, x_coord: int, z_coord: int):
        responseguild = self.bot.get_guild(config['Coastal'])
        responseChannel = responseguild.get_channel(
            config['CoastalMapUpdates'])
        admin = responseguild.get_role(config['CoastalOPTeam'])
        channel = interaction.channel
        author = interaction.user
        currentsheet = nethersheet
        entryID = (int(currentsheet.acell('A2').value) + 1)
        print(entryID)
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
                                description=poidesc +
                                "\n**Questions will start in 3 seconds.**",
                                color=0x336F75)
        await channel.send(embed=introem)
        await asyncio.sleep(3)

        await channel.send(Qtext1)
        answer1 = await self.bot.wait_for('message', check=check)
        await asyncio.sleep(.5)

        await channel.send(Qtext2)
        answer2 = await self.bot.wait_for('message', check=check)
        await asyncio.sleep(.5)

        await channel.send(Qtext3)
        answer3 = await self.bot.wait_for('message', check=check)
        await asyncio.sleep(.5)

        await channel.send(Qtextcolor)
        answer4 = await self.bot.wait_for('message', check=check)
        await asyncio.sleep(.5)

        await channel.send(Qmarkertype)
        answer5 = await self.bot.wait_for('message', check=check)
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
        currentsheet.insert_row(row, 2, value_input_option='USER_ENTERED')

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

    @app_commands.command(name="addpoi_end",
                   description="Add a POI to the End!")
    @app_commands.guilds(config['PBtest'], config['Coastal'])
    async def addpoi_end(self, interaction: discord.Interaction, x_coord: int, z_coord: int):
        responseguild = self.bot.get_guild(config['Coastal'])
        responseChannel = responseguild.get_channel(
            config['CoastalMapUpdates'])
        admin = responseguild.get_role(config['CoastalOPTeam'])
        channel = interaction.channel
        author = interaction.user
        currentsheet = endsheet
        entryID = (int(currentsheet.acell('A2').value) + 1)
        print(entryID)
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
                                description=poidesc +
                                "\n**Questions will start in 3 seconds.**",
                                color=0x336F75)
        await channel.send(embed=introem)
        await asyncio.sleep(3)

        await channel.send(Qtext1)
        answer1 = await self.bot.wait_for('message', check=check)
        await asyncio.sleep(.5)

        await channel.send(Qtext2)
        answer2 = await self.bot.wait_for('message', check=check)
        await asyncio.sleep(.5)

        await channel.send(Qtext3)
        answer3 = await self.bot.wait_for('message', check=check)
        await asyncio.sleep(.5)

        await channel.send(Qtextcolor)
        answer4 = await self.bot.wait_for('message', check=check)
        await asyncio.sleep(.5)

        await channel.send(Qmarkertype)
        answer5 = await self.bot.wait_for('message', check=check)
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
        currentsheet.insert_row(row, 2, value_input_option='USER_ENTERED')

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


    @app_commands.command(name="addpoi_endcity_claim",
                   description="Add an End city that you hae raided!")
    @app_commands.guilds(config['PBtest'], config['Coastal'])
    async def addpoi_end(self, interaction: discord.Interaction, x_coord: int, z_coord: int):
        responseguild = self.bot.get_guild(config['Coastal'])
        responseChannel = responseguild.get_channel(
            config['CoastalMapUpdates'])
        admin = responseguild.get_role(config['CoastalOPTeam'])
        channel = interaction.channel
        author = interaction.user
        currentsheet = endsheet
        entryID = (int(currentsheet.acell('A2').value) + 1)
        print(entryID)
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
                                description=poidesc +
                                "\n**Questions will start in 3 seconds.**",
                                color=0x336F75)
        await channel.send(embed=introem)
        await asyncio.sleep(3)

        await channel.send("What is your gamertag?")
        answer1 = await self.bot.wait_for('message', check=check)
        await asyncio.sleep(.5)

        await channel.send(Qtextcolor)
        answer2 = await self.bot.wait_for('message', check=check)
        await asyncio.sleep(.5)

        # Spreadsheet Data
          
        font = "900 10px 'Font Awesome 6 Free'"
        row = [
            entryID, x_coord, z_coord, "-1", "", "", "\uf06a",
            answer1.content, "", answer2.content, "#ffffff", "0", "0",
            font
        ]
        currentsheet.insert_row(row, 2, value_input_option='USER_ENTERED')

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

    @app_commands.command(name="addpoi_end_returngateway",
                   description="Mark a return gateway in the End")
    @app_commands.guilds(config['PBtest'], config['Coastal'])
    async def addpoi_end(self, interaction: discord.Interaction, x_coord: int, z_coord: int):
        responseguild = self.bot.get_guild(config['Coastal'])
        responseChannel = responseguild.get_channel(
            config['CoastalMapUpdates'])
        admin = responseguild.get_role(config['CoastalOPTeam'])
        channel = interaction.channel
        author = interaction.user
        currentsheet = endsheet
        entryID = (int(currentsheet.acell('A2').value) + 1)
        print(entryID)
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
        currentsheet.insert_row(row, 2, value_input_option='USER_ENTERED')

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

async def setup(bot):
    await bot.add_cog(CoastalPOICMD(bot))
