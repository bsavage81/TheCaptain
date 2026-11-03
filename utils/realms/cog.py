"""Private Coastal OP Team views of the selected Realm."""
import discord
from discord import app_commands
from discord.ext import commands

from .runtime import RealmRuntime
from .panel import PanelController


def permitted(settings, interaction):
    guild = settings.get("Coastal")
    role = settings.get("CoastalOPTeam")
    return (type(guild) is int and guild > 0 and type(role) is int and role > 0
            and interaction.guild_id == guild
            and getattr(getattr(interaction, "guild", None), "id", None) == guild
            and any(r.id == role for r in getattr(interaction.user, "roles", ())))


def timestamp(snapshot):
    return f"<t:{int(snapshot.observed_at.timestamp())}:F>" if snapshot is not None else "Unavailable"


def safe_name(value, limit=100):
    # Preserve only supplied names; suppress mentions and Markdown/code formatting.
    return discord.utils.escape_mentions(discord.utils.escape_markdown(value[:limit]))


def render(view, kind, cooldown=0):
    lines = []
    if cooldown:
        lines.append(f"Refresh cooldown: try again in {cooldown} seconds. Showing cached observations.")
    realm = view.realm.data if view.realm else None
    lines.append("Realm: " + (safe_name(realm.name) if realm else "Unavailable"))
    if kind != "players":
        state = realm.state if view.realm_available and realm else "Unavailable"
        lines.append("State: " + state)
        lines.append("Last successful status observation: " + timestamp(view.realm))
        if realm and not view.realm_available:
            lines.append("Last known state (stale): " + realm.state)
    if kind != "status":
        if view.activity_available and view.activity:
            players = view.activity.data.players
            online = [p for p in players if p.online is True]
            unknown = sum(p.online is None for p in players)
            if unknown:
                lines.append(f"Online players: at least {len(online)}; activity unknown for {unknown} record(s).")
            else:
                lines.append(f"Online players: {len(online)}")
            names = [safe_name(p.name, 40) for p in online if p.name]
            if names:
                lines.append("Names supplied by API: " + ", ".join(names[:10]))
                if len(names) > 10:
                    lines.append("Additional API-supplied names omitted for message length.")
            unnamed = len(online) - len(names)
            if unnamed:
                lines.append(f"Names unavailable for {unnamed} player(s); no lookup or identity guess was made.")
        else:
            lines.append("Player activity: Unknown / unavailable (not a zero-player observation).")
        lines.append("Last successful activity observation: " + timestamp(view.activity))
    if not view.realm_available or kind != "status" and not view.activity_available:
        lines.append("Unavailable data may require an operator to restore credentials or service access.")
    return "\n".join(lines)


class RealmCommands(commands.Cog):
    realm = app_commands.Group(name="realm", description="Coastal Craft Realm observations", guild_only=True)
    panel = app_commands.Group(name="panel", description="Manage the live Realm status panel", parent=realm)

    def __init__(self, bot, *, runtime=None):
        self.bot = bot
        self.runtime = runtime if runtime is not None else RealmRuntime(bot.settings)
        self.panels = PanelController(bot, self.runtime)

    async def cog_load(self):
        await self.runtime.start()
        if hasattr(self.bot, "wait_until_ready"):
            self.panels.start()

    async def cog_unload(self):
        await self.panels.close()
        await self.runtime.close()

    async def manage_panel(self, interaction, action):
        if not permitted(self.bot.settings, interaction):
            await interaction.response.send_message("Realm commands require the Coastal OP Team role in Coastal Craft.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        if action == "create":
            url = await self.panels.create(interaction.channel)
            await self.panels.refresh(manual=True)
            response = "Realm panel ready: " + url
        elif action == "remove":
            await self.panels.remove()
            response = "Realm panel removed; automatic updates stopped."
        else:
            ok = await self.panels.refresh(manual=True)
            response = "Realm panel updated (upstream cooldowns respected)." if ok else "Panel unavailable or cooling down. Use /realm panel create if it was deleted."
        if permitted(self.bot.settings, interaction):
            await interaction.followup.send(response, ephemeral=True, allowed_mentions=discord.AllowedMentions.none())

    @panel.command(name="create", description="Create or relocate the live panel to this channel")
    async def panel_create(self, interaction: discord.Interaction):
        await self.manage_panel(interaction, "create")

    @panel.command(name="remove", description="Remove the panel and stop its updates")
    async def panel_remove(self, interaction: discord.Interaction):
        await self.manage_panel(interaction, "remove")

    @panel.command(name="refresh", description="Request a read-only update of the existing panel")
    async def panel_refresh(self, interaction: discord.Interaction):
        await self.manage_panel(interaction, "refresh")

    async def respond(self, interaction, kind):
        if not permitted(self.bot.settings, interaction):
            await interaction.response.send_message("Realm commands require the Coastal OP Team role in Coastal Craft.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        view, cooldown = await self.runtime.observe(force=kind == "refresh")
        if not permitted(self.bot.settings, interaction):
            await interaction.followup.send("You no longer have access to this Realm command.", ephemeral=True)
            return
        await interaction.followup.send(render(view, kind, cooldown), ephemeral=True,
                                        allowed_mentions=discord.AllowedMentions.none())

    async def cog_app_command_error(self, interaction, error):
        send = interaction.followup.send if interaction.response.is_done() else interaction.response.send_message
        await send("Realm information is unavailable. An operator may need to restore credentials or service access.", ephemeral=True)

    @realm.command(name="status", description="View the selected Realm state and observation time")
    async def status(self, interaction: discord.Interaction):
        await self.respond(interaction, "status")

    @realm.command(name="players", description="View player activity supplied by the Realm API")
    async def players(self, interaction: discord.Interaction):
        await self.respond(interaction, "players")

    @realm.command(name="refresh", description="Refresh the selected Realm's read-only observations")
    async def refresh(self, interaction: discord.Interaction):
        await self.respond(interaction, "refresh")


async def setup(bot):
    cog = RealmCommands(bot)
    cog.realm._guild_ids = [bot.settings["Coastal"]]
    try:
        await bot.add_cog(cog)
    except BaseException:
        await cog.runtime.close()
        raise
