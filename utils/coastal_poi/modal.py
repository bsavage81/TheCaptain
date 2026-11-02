"""Private marker entry using the existing Season 10 row contract."""
import logging
import re

import discord

from .__poi_logic import MARKER_TYPES

log = logging.getLogger(__name__)
FONT_AWESOME_URL = "https://fontawesome.com/search?ic=free"


class POIModal(discord.ui.Modal):
    def __init__(self, bot, author_id, dimension, x, z, marker_type):
        super().__init__(title=f"New {dimension} marker", timeout=600)
        self.bot = bot
        self.author_id = author_id
        self.dimension = dimension
        self.x, self.z = x, z
        self.category, self.font_size = MARKER_TYPES[marker_type]
        self.submitted = False
        self.text1 = discord.ui.TextInput(label="Text line 1 / icon", max_length=200,
            placeholder="Marker name, text, or a pasted icon character")
        self.text2 = discord.ui.TextInput(label="Text line 2 (optional)", required=False, max_length=200)
        self.text3 = discord.ui.TextInput(label="Text line 3 (optional)", required=False, max_length=200)
        self.color = discord.ui.TextInput(label="Text color", default="white", max_length=64,
            placeholder="A color name such as blue, or a hex code such as #33aaff")
        for field in (self.text1, self.text2, self.text3, self.color):
            self.add_item(field)
        self.radius = None
        if marker_type in {"base", "community"}:
            self.radius = discord.ui.TextInput(label="Border radius in blocks (optional)", required=False,
                max_length=10, placeholder="Distance from X/Z center to border; blank or 0 = no border")
            self.add_item(self.radius)

    def marker_row(self, text1, color, radius):
        def optional(field):
            value = field.value.strip()
            return "" if value.casefold() == "no" else value
        return [None, self.x, self.z, "-1", "", "", text1, optional(self.text2), optional(self.text3),
                color, "#ffffff", "0", "0", f"900 {self.font_size}px 'Font Awesome 6 Free'", self.category, radius]

    async def on_submit(self, interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("This marker form belongs to another player.", ephemeral=True)
            return
        if self.submitted:
            await interaction.response.send_message("This form was already submitted. Check your confirmation.", ephemeral=True)
            return
        text1, color = self.text1.value.strip(), self.color.value.strip()
        if not text1 or not color:
            await interaction.response.send_message("Text line 1 and text color cannot be blank. Open a new form.", ephemeral=True)
            return
        radius = ""
        if self.radius is not None:
            value = self.radius.value.strip()
            if value and not re.fullmatch(r"[0-9]+", value):
                await interaction.response.send_message(
                    "Border radius must be a whole number of blocks, 0, or blank. Open a new form.", ephemeral=True)
                return
            radius = int(value) if value else ""
        self.submitted = True
        await interaction.response.defer(ephemeral=True, thinking=True)
        row = self.marker_row(text1, color, radius)
        try:
            entry_id = await self.bot.sheets.submit_poi(self.dimension, row)
        except Exception as error:
            log.warning("poi_modal_save_failed error=%s", type(error).__name__)
            await interaction.followup.send(
                "The save could not be confirmed. Contact an OP before retrying to avoid a duplicate marker.", ephemeral=True)
            return
        notification_failed = False
        try:
            guild = self.bot.get_guild(self.bot.settings["Coastal"])
            channel = guild.get_channel(self.bot.settings["CoastalMapUpdates"])
            role = guild.get_role(self.bot.settings["CoastalOPTeam"])
            embed = discord.Embed(title="New POI Entered", color=0x336F75,
                                  description=f"Submitted by {interaction.user} • {self.dimension} • ID {entry_id}")
            for name, value in (("X", self.x), ("Z", self.z), ("Category", self.category),
                                ("Text line 1", row[6]), ("Text line 2", row[7]),
                                ("Text line 3", row[8]), ("Text color", color)):
                embed.add_field(name=name, value=str(value) or "—", inline=False)
            if self.radius is not None:
                embed.add_field(name="Border radius", value=f"{radius} blocks" if radius else "No border", inline=False)
            await channel.send(content=role.mention, embed=embed,
                               allowed_mentions=discord.AllowedMentions(roles=[role], users=False, everyone=False))
        except Exception as error:
            notification_failed = True
            log.warning("poi_modal_notification_failed entry=%s error=%s", entry_id, type(error).__name__)
        message = f"Marker #{entry_id} saved in {self.dimension} at X {self.x}, Z {self.z}. Category: {self.category}."
        if self.radius is not None:
            message += f" Border radius: {radius} blocks." if radius else " No border radius set."
        if notification_failed:
            message += " Staff notification failed; your marker is saved. Please do not resubmit."
        await interaction.followup.send(message, ephemeral=True, allowed_mentions=discord.AllowedMentions.none())

    async def on_error(self, interaction, error):
        await interaction.client.tree.on_error(interaction, error)


class EndCityClaimModal(POIModal):
    def __init__(self, bot, author_id, x, z):
        super().__init__(bot, author_id, "End", x, z, "community")
        self.title = "Claim a raided End city"
        self.clear_items()
        self.radius = None
        self.text1 = discord.ui.TextInput(label="Gamertag", max_length=200,
                                         placeholder="Who raided this End city?")
        self.add_item(self.text1)
        self.add_item(self.color)

    def marker_row(self, text1, color, radius):
        # The claim icon and gamertag occupy G/H, matching the existing map contract.
        return [None, self.x, self.z, "-1", "", "", "\uf06a", text1, "", color,
                "#ffffff", "0", "0", "900 10px 'Font Awesome 6 Free'", "Community", ""]


class POIStartView(discord.ui.View):
    def __init__(self, bot, author_id, dimension, x, z, marker_type):
        super().__init__(timeout=600)
        self.bot, self.author_id = bot, author_id
        self.dimension, self.x, self.z, self.marker_type = dimension, x, z, marker_type
        self.opened = False

    async def interaction_check(self, interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("These marker instructions belong to another player.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Open marker form", style=discord.ButtonStyle.primary)
    async def open_form(self, interaction, button):
        if not await self.interaction_check(interaction):
            return
        if self.opened:
            await interaction.response.send_message("The form was already opened. Run the command again if you closed it.", ephemeral=True)
            return
        self.opened = True
        try:
            await interaction.response.send_modal(POIModal(
                self.bot, self.author_id, self.dimension, self.x, self.z, self.marker_type))
        except Exception:
            self.opened = False
            raise
        button.disabled = True
        try:
            await interaction.message.edit(view=self)
        except discord.HTTPException:
            # The form is open; logical single-use protection still applies.
            pass


async def open_poi_modal(bot, interaction, dimension, x, z, marker_type):
    await interaction.response.send_message(
        f"Read these instructions, then click **Open marker form** below to enter your marker text and color. "
        f"Browse free Font Awesome icons: {FONT_AWESOME_URL}\n"
        "The map uses Font Awesome 6 Free; newer or Pro-only icons may not render. Paste an icon character, not its web address.\n"
        "The button is available for 10 minutes. If you close the form, run the command again.",
        view=POIStartView(bot, interaction.user.id, dimension, x, z, marker_type),
        ephemeral=True, allowed_mentions=discord.AllowedMentions.none())
