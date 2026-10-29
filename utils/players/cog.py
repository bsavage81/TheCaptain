"""Private staff workflows and restart-safe monthly Discord check-ins."""
import asyncio
import io
import json
import logging
from datetime import date
import discord
from discord import app_commands
from discord.ext import commands, tasks
from utils.database.__database import db
from utils.helpers.__checks import op_team
from . import checkins, registry
from .history import ArchiveDiscovery
from .models import CheckIn, DiscoveryRun, Identity, ImportRecord, MODELS, Participation, Period, Player, Reminder

log = logging.getLogger(__name__)


async def database(operation):
    def run():
        with db.connection_context():
            return operation()
    return await asyncio.to_thread(run)


async def private_report(interaction, content):
    """Bounded ephemeral attachment avoids public PII and Discord message limits."""
    text = content if isinstance(content, str) else json.dumps(content, indent=2, default=str)
    if len(text) <= 1800:
        await interaction.followup.send(text, ephemeral=True, allowed_mentions=discord.AllowedMentions.none())
    else:
        await interaction.followup.send("Private report attached.", ephemeral=True,
            file=discord.File(io.BytesIO(text.encode()), filename="captain-report.txt"))


class CheckInView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="Check In", emoji="✅", style=discord.ButtonStyle.success,
                       custom_id="captain:monthly-checkin:v1")
    async def check_in(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            message = await self.cog.check_in(interaction)
        except Exception as error:
            log.warning("checkin_failed error=%s", type(error).__name__)
            message = "Check-in could not be confirmed. Try again safely or contact staff."
        await interaction.followup.send(message, ephemeral=True)


class Players(commands.Cog):
    profiles = app_commands.Group(name="playerprofiles", description="Player registry and historical review")
    checkin = app_commands.Group(name="checkin", description="Monthly Coastal Craft participation")

    def __init__(self, bot):
        self.bot = bot
        self.settings = bot.settings
        self.discovery = ArchiveDiscovery(bot.sheets, self.settings)
        self.setup_lock = asyncio.Lock()
        self.announcement_lock = asyncio.Lock()

    async def cog_load(self):
        checkins.validate(self.settings)
        def preflight():
            missing = {m._meta.table_name for m in MODELS} - set(db.get_tables())
            if missing:
                raise ValueError("Registry tables missing; review migrations.player_registry before enabling profiles")
        await database(preflight)
        self.view = CheckInView(self)
        self.bot.add_view(self.view)
        if self.settings.get("checkin_enabled"):
            self.schedule.start()

    def cog_unload(self):
        self.schedule.cancel()
        if hasattr(self, "view"):
            self.view.stop()

    async def scope(self, interaction):
        if interaction.guild_id != self.settings["Coastal"]:
            raise app_commands.CheckFailure("Use this command in Coastal Craft")

    async def check_in(self, interaction):
        if not self.settings.get("checkin_enabled") or interaction.guild_id != self.settings["Coastal"]:
            return "Monthly check-ins are unavailable here."
        message_id = interaction.message.id if interaction.message else None
        def write():
            current = checkins.period(self.settings)
            if current.message_id != message_id or not message_id or current.channel_id != interaction.channel_id:
                return "This announcement is closed. Use the current month's check-in message."
            player = Player.get_or_none(Player.discord_id == interaction.user.id)
            if player is None:
                return "No linked player profile. Ask an OP to review your application and link your Discord ID."
            if not checkins.eligible(player, interaction.user, self.settings):
                return "Your current Realm eligibility needs staff review. Please contact an OP."
            registry.observe_discord(player, interaction.user.name, interaction.guild_id)
            label = date(current.year, current.month, 1).strftime("%B %Y")
            if checkins.record_checkin(player, interaction.user.id, current, message_id=message_id):
                return f"You're checked in for {label}! Thanks for being part of Coastal Craft."
            return f"You've already completed your {label} check-in."
        return await database(write)

    @profiles.command(name="setup", description="Discover historical sources and stage a dry-run review queue")
    @op_team()
    async def setup_profiles(self, interaction: discord.Interaction):
        await self.scope(interaction)
        await interaction.response.defer(ephemeral=True, thinking=True)
        if self.setup_lock.locked():
            await interaction.followup.send("Discovery is already running.", ephemeral=True)
            return
        async with self.setup_lock:
            # Work survives interaction-token expiry. Queue is persisted; reconcile retrieves it.
            guild = interaction.guild
            if not guild.chunked:
                await guild.chunk(cache=True)
            result = await self.discovery.run()
            summary = await database(lambda: registry.stage(result["records"], list(guild.members)))
            report = {"dry_run": summary, "sources": result["sources"], "issues": result["issues"],
                      "next": "Review each row; then /playerprofiles import confirm:True"}
            await database(lambda: DiscoveryRun.create(actor=interaction.user.id, report=json.dumps(report)))
            try:
                await private_report(interaction, report)
            except discord.HTTPException:
                log.info("profile_discovery_complete response_expired=true")

    @profiles.command(name="discovery", description="Retrieve the last durable discovery summary and source failures")
    @op_team()
    async def discovery_report(self, interaction: discord.Interaction):
        await self.scope(interaction)
        await interaction.response.defer(ephemeral=True)
        def report():
            run = DiscoveryRun.select().order_by(-DiscoveryRun.id).first()
            return json.loads(run.report) if run else "No completed discovery yet."
        await private_report(interaction, await database(report))

    @profiles.command(name="reconcile", description="Page through pending, conflicting or unmatched sources")
    @op_team()
    async def reconcile(self, interaction: discord.Interaction, page: app_commands.Range[int, 1] = 1):
        await self.scope(interaction)
        await interaction.response.defer(ephemeral=True)
        def report():
            return [{"id": r.id, "state": r.state, "target": r.player_id, "match": r.note,
                     "record": json.loads(r.payload)} for r in ImportRecord.select().where(
                         ImportRecord.state != "imported").order_by(ImportRecord.id).paginate(page, 20)]
        await private_report(interaction, await database(report))

    @profiles.command(name="review", description="Approve/reject one identity association using independent evidence")
    @op_team()
    async def review(self, interaction: discord.Interaction, record_id: int, reject: bool,
                     player_id: int | None = None, member: discord.Member | None = None):
        await self.scope(interaction)
        await interaction.response.defer(ephemeral=True)
        try:
            await database(lambda: registry.review(record_id, interaction.user.id, player_id=player_id,
                discord_id=member.id if member else None, reject=reject))
            await interaction.followup.send("Review saved. No data imported yet.", ephemeral=True)
        except (ValueError, ImportRecord.DoesNotExist, Player.DoesNotExist) as error:
            await private_report(interaction, str(error))

    @profiles.command(name="import", description="Explicitly import only individually approved source records")
    @op_team()
    async def import_profiles(self, interaction: discord.Interaction, confirm: bool):
        await self.scope(interaction)
        await interaction.response.defer(ephemeral=True, thinking=True)
        if not confirm:
            await interaction.followup.send("Import cancelled. Review the queue first.", ephemeral=True)
            return
        await private_report(interaction, await database(registry.import_approved))

    @profiles.command(name="view", description="Privately inspect a profile and season history")
    @op_team()
    async def view_profile(self, interaction: discord.Interaction, member: discord.Member | None = None,
                           player_id: int | None = None, page: app_commands.Range[int, 1] = 1):
        await self.scope(interaction)
        await interaction.response.defer(ephemeral=True)
        def report():
            p = Player.get_or_none(Player.id == player_id) if player_id else Player.get_or_none(
                Player.discord_id == member.id) if member else None
            if p is None:
                return "No linked profile; use setup and review."
            return {"profile": p.__data__, "seasons": [r.__data__ for r in p.seasons.order_by(Participation.season).paginate(page, 20)],
                    "identity_history": [r.__data__ for r in p.identities.order_by(-Identity.id).paginate(page, 20)]}
        await private_report(interaction, await database(report))

    @profiles.command(name="link", description="Confirm a member identity when no historical application exists")
    @op_team()
    async def link_profile(self, interaction: discord.Interaction, member: discord.Member, gamertag: str, confirm: bool):
        await self.scope(interaction)
        await interaction.response.defer(ephemeral=True)
        if not confirm or member.bot or not 1 <= len(gamertag.strip()) <= 255:
            await private_report(interaction, "Confirm a human member and a valid gamertag after reviewing identity evidence.")
            return
        def write():
            record = dict(source=f"staff_profile#entry={member.id}", season=self.settings.get("checkin_season", 10),
                discord_id=member.id, discord_id_verified=True, discord_name=str(member), gamertag=gamertag.strip(),
                application_date=None, application_status="unknown", identity_confirmation=f"staff:{interaction.user.id}")
            registry.stage([record], [member])
            row = ImportRecord.get(ImportRecord.key == registry.record_key(record))
            if row.state != "imported":
                registry.review(row.id, interaction.user.id)
                registry.import_record(row.id)
            return "Identity profile linked. Set eligibility separately after staff review of current Realm participation."
        await private_report(interaction, await database(write))

    @profiles.command(name="eligibility", description="Explicitly manage current-season check-in eligibility")
    @op_team()
    async def eligibility(self, interaction: discord.Interaction, member: discord.Member, eligible: bool):
        await self.scope(interaction)
        await interaction.response.defer(ephemeral=True)
        def write():
            p = Player.get_or_none(Player.discord_id == member.id)
            if p is None:
                return "Link a reviewed profile first."
            season = self.settings.get("checkin_season", 10)
            with db.atomic():
                Participation.update(realm_status="unknown").where((Participation.player == p) &
                    (Participation.season == season) & (Participation.realm_status == "staff_eligible")).execute()
                row, _ = Participation.get_or_create(player=p, season=season, source="staff_managed")
                row.realm_status = "staff_eligible" if eligible else "staff_ineligible"
                row.save()
            return "Staff-managed eligibility saved; configured role rules take precedence."
        await private_report(interaction, await database(write))

    @checkin.command(name="status", description="See your current monthly check-in status")
    async def status(self, interaction: discord.Interaction):
        await self.scope(interaction)
        await interaction.response.defer(ephemeral=True)
        def report():
            current = checkins.period(self.settings)
            p = Player.get_or_none(Player.discord_id == interaction.user.id)
            return {"season": current.season, "year": current.year, "month": current.month,
                    "profile_linked": p is not None, "eligible": bool(p and checkins.eligible(p, interaction.user, self.settings)),
                    "checked_in": bool(p and checkins.checked(p, current))}
        await private_report(interaction, await database(report))

    @checkin.command(name="report", description="Private eligible roster, missing check-ins and DM results")
    @op_team()
    async def report(self, interaction: discord.Interaction, page: app_commands.Range[int, 1] = 1):
        await self.scope(interaction)
        await interaction.response.defer(ephemeral=True)
        if not interaction.guild.chunked:
            await interaction.guild.chunk(cache=True)
        def report():
            current = checkins.period(self.settings)
            roster = checkins.roster(interaction.guild, self.settings, current)
            total, done = len(roster), sum(r[2] for r in roster)
            return {"season": current.season, "year": current.year, "month": current.month,
                    "eligibility_basis": "configured_role" if self.settings.get("checkin_eligible_role_id") else "staff_managed",
                    "eligible": total, "checked_in": done, "completion_percent": round(100 * done / total, 1) if total else 0,
                    "missing": [r[:2] for r in roster if not r[2]][(page-1)*20:page*20],
                    "reminders": [r.__data__ for r in Reminder.select().where(Reminder.period == current).order_by(Reminder.id).paginate(page, 20)],
                    "announcement_state": current.announcement_state, "staff_report_state": current.staff_report_state}
        await private_report(interaction, await database(report))

    @checkin.command(name="history", description="Private check-in history for a player")
    @op_team()
    async def history(self, interaction: discord.Interaction, member: discord.Member | None = None,
                      player_id: int | None = None, page: app_commands.Range[int, 1] = 1):
        await self.scope(interaction)
        await interaction.response.defer(ephemeral=True)
        if member is None and player_id is None:
            await private_report(interaction, "Select a member or internal player ID.")
            return
        await private_report(interaction, await database(lambda: [r.__data__ for r in CheckIn.select().join(Player).where(
            Player.id == player_id if player_id else Player.discord_id == member.id).order_by(-CheckIn.checked_at).paginate(page, 20)]))

    @checkin.command(name="announce", description="Create/repair the current announcement; confirm uncertain sends explicitly")
    @op_team()
    async def announce(self, interaction: discord.Interaction, confirmed_absent: bool = False):
        await self.scope(interaction)
        await interaction.response.defer(ephemeral=True)
        if not self.settings.get("checkin_enabled") or not self.settings.get("checkin_announcements_enabled"):
            await private_report(interaction, "Announcements are disabled in configuration.")
            return
        result = await self.post_announcement(confirmed_absent=confirmed_absent)
        await private_report(interaction, result)

    async def post_announcement(self, *, confirmed_absent=False):
        async with self.announcement_lock:
            return await self._post_announcement(confirmed_absent=confirmed_absent)

    async def _post_announcement(self, *, confirmed_absent=False):
        current = await database(lambda: checkins.period(self.settings))
        channel_id = current.channel_id or self.settings.get("checkin_channel_id")
        channel = self.bot.get_channel(channel_id)
        if not channel or channel.guild.id != self.settings["Coastal"]:
            return "Announcement channel missing or outside Coastal Craft."
        if current.message_id:
            try:
                message = await channel.fetch_message(current.message_id)
                await message.edit(view=self.view)
                return "Existing announcement repaired."
            except discord.NotFound:
                # Confirmed deletion is safe to replace, unlike permission/network failures.
                confirmed_absent = True
        if confirmed_absent:
            await database(lambda: Period.update(announcement_state="new", message_id=None).where(
                (Period.id == current.id) & (Period.announcement_state != "new")).execute())
        if not await database(lambda: checkins.claim_announcement(current, channel.id)):
            return "Announcement already claimed or uncertain. Check channel history before confirming absence."
        label = date(current.year, current.month, 1).strftime("%B %Y")
        embed = discord.Embed(title="Coastal Craft Monthly Check-In",
            description="It's time for your monthly Coastal Craft check-in!\n\nIf you're still participating in the Realm and want to remain on the active player list, click the button below.")
        embed.add_field(name="Month", value=label)
        embed.add_field(name="Season", value=f"Season {current.season}, {self.settings.get('checkin_season_name', 'The Mighty Mesa Reborn')}")
        message = await channel.send(embed=embed, view=self.view, allowed_mentions=discord.AllowedMentions.none())
        await database(lambda: Period.update(message_id=message.id, channel_id=channel.id,
            announcement_state="sent").where(Period.id == current.id).execute())
        return "Monthly announcement posted."

    async def remind(self, guild, current, day):
        roster = await database(lambda: checkins.roster(guild, self.settings, current))
        for player_id, discord_id, done in roster:
            if done:
                continue
            claim = await database(lambda: checkins.claim_reminder(current, player_id, day))
            if claim is None:
                continue
            member = guild.get_member(discord_id)
            try:
                # Recheck immediately before delivery after any preceding slow Discord requests.
                if await database(lambda: checkins.checked(Player.get_by_id(player_id), current)):
                    state = "skipped_checked_in"
                elif checkins.calendar(self.settings)[1:3] != (current.year, current.month):
                    state = "skipped_closed"
                else:
                    await member.send(f"Coastal Craft check-in reminder: please check in for {date(current.year, current.month, 1):%B %Y} in the monthly announcement. Contact an OP if you need help.")
                    state = "sent"
            except discord.HTTPException:
                state = "failed"
            await database(lambda: Reminder.update(state=state).where(Reminder.id == claim.id).execute())

    async def staff_summary(self, guild, current):
        channel = self.bot.get_channel(self.settings.get("checkin_staff_channel_id"))
        if channel is None or channel.guild.id != guild.id:
            return
        # Staff channel must deny @everyone view access; command reports remain ephemeral.
        if channel.permissions_for(guild.default_role).view_channel:
            log.warning("checkin_staff_channel_not_private")
            return
        claimed = await database(lambda: Period.update(staff_report_state="claimed").where(
            (Period.id == current.id) & (Period.staff_report_state == "new")).execute())
        if not claimed:
            return
        roster = await database(lambda: checkins.roster(guild, self.settings, current))
        failed = await database(lambda: Reminder.select().where((Reminder.period == current) &
            (Reminder.state.in_(["failed", "claimed"]))).count())
        await channel.send(f"Monthly check-in {current.year}-{current.month:02} / Season {current.season}: "
            f"{sum(r[2] for r in roster)}/{len(roster)} eligible players checked in. "
            f"{failed} failed/uncertain reminders. Use /checkin report for private details.",
            allowed_mentions=discord.AllowedMentions.none())
        await database(lambda: Period.update(staff_report_state="sent").where(Period.id == current.id).execute())

    @tasks.loop(minutes=15)
    async def schedule(self):
        try:
            guild = self.bot.get_guild(self.settings["Coastal"])
            if guild is None:
                return
            current = await database(lambda: checkins.period(self.settings))
            if self.settings.get("checkin_announcements_enabled"):
                # A saved message needs repair only through the explicit staff command.
                if current.announcement_state == "new":
                    await self.post_announcement()
            if not self.settings.get("checkin_reminders_enabled"):
                return
            if not guild.chunked:
                await guild.chunk(cache=True)
            day = checkins.calendar(self.settings)[3]
            due = [d for d in self.settings.get("checkin_reminder_days", [15, 25]) if d <= day]
            if due:
                # After downtime send only the latest due reminder, avoiding a burst of catch-up DMs.
                await self.remind(guild, current, max(due))
                if day >= max(self.settings.get("checkin_reminder_days", [15, 25])):
                    await self.staff_summary(guild, current)
        except Exception as error:
            log.warning("monthly_checkin_job_failed error=%s", type(error).__name__)

    @schedule.before_loop
    async def before_schedule(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    if not bot.settings.get("profiles_enabled", False):
        return
    cog = Players(bot)
    await bot.add_cog(cog, guilds=[discord.Object(id=bot.settings["Coastal"])])
