"""Private Coastal OP Team views of the selected Realm."""
import asyncio
import io
import json

import discord
from discord import app_commands
from discord.ext import commands

from .runtime import RealmRuntime
from .panel import PanelController
from .metrics import MetricsController


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
    daily_group = app_commands.Group(name="daily", description="Manage observed daily Realm timelines", parent=realm)
    metrics_panel = app_commands.Group(name="metrics", description="Manage the live Realms Pro metrics panel", parent=realm)

    def __init__(self, bot, *, runtime=None):
        self.bot = bot
        self._stories_post_lock = asyncio.Lock()
        self._stories_sent = set()
        self._story_deliveries = None
        self._stories_retry_at = 0
        self.runtime = runtime if runtime is not None else RealmRuntime(bot.settings)
        self.panels = PanelController(bot, self.runtime)
        self.metrics_panels = MetricsController(bot, self.runtime)
        from .daily import DailyController
        self.daily_reports = DailyController(bot, self.runtime)
        from .stories_sync import StoriesController
        self.stories_sync = StoriesController(bot, self.runtime, self._publish_stories)
        self.stories_sync.daily_refresh = self.daily_reports.scheduled_refresh

    async def cog_load(self):
        await self.runtime.start()
        if hasattr(self.bot, "wait_until_ready"):
            self.panels.start()
            self.metrics_panels.start()
            self.stories_sync.start()
            self.daily_reports.start()

    async def cog_unload(self):
        await self.daily_reports.close()
        await self.stories_sync.close()
        await self.metrics_panels.close()
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

    async def manage_metrics(self, interaction, action):
        if not permitted(self.bot.settings, interaction):
            await interaction.response.send_message("Realm commands require the Coastal OP Team role in Coastal Craft.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        if action == "create":
            try:
                url = await self.metrics_panels.create(interaction.channel)
            except RuntimeError:
                await interaction.followup.send("Realms Pro metrics are unavailable to the Captain account. No metrics panel was posted. Owner access may be required.", ephemeral=True)
                return
            response = "Live metrics panel ready: " + url
        elif action == "remove":
            await self.metrics_panels.remove()
            response = "Metrics panel removed; updates stopped."
        else:
            ok = await self.metrics_panels.refresh(manual=True)
            response = "Metrics panel refreshed; upstream cooldowns respected." if ok else "Metrics panel unavailable or cooling down."
        await interaction.followup.send(response, ephemeral=True, allowed_mentions=discord.AllowedMentions.none())

    @metrics_panel.command(name="create", description="Post a separate auto-updating Pro metrics embed in this channel")
    async def metrics_create(self, interaction: discord.Interaction):
        await self.manage_metrics(interaction, "create")

    @metrics_panel.command(name="refresh", description="Refresh the existing Pro metrics panel")
    async def metrics_refresh(self, interaction: discord.Interaction):
        await self.manage_metrics(interaction, "refresh")

    @metrics_panel.command(name="remove", description="Remove the Pro metrics panel and stop polling")
    async def metrics_remove(self, interaction: discord.Interaction):
        await self.manage_metrics(interaction, "remove")

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

    @realm.command(name="storiespost", description="Post current Realm Stories once in this channel (OP Team)")
    async def storiespost(self, interaction: discord.Interaction):
        await self._post_stories(interaction)

    @realm.command(name="oldstoriespost", description="Post Stories from OLD Coastal S10 here (OP Team)")
    async def oldstoriespost(self, interaction: discord.Interaction):
        await self._post_stories(interaction, old_realm=True)

    async def _post_stories(self, interaction, *, old_realm=False):
        if not permitted(self.bot.settings, interaction):
            await interaction.response.send_message("Realm commands require the Coastal OP Team role in Coastal Craft.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        _, message = await self._publish_stories(interaction.channel, interaction.guild_id,
                                                  lambda: permitted(self.bot.settings, interaction), old_realm=old_realm)
        await interaction.followup.send(message, ephemeral=True, allowed_mentions=discord.AllowedMentions.none())

    async def _publish_stories(self, channel, guild_id, authorized, *, old_realm=False):
        from .stories_feed import render_feed, artwork_file
        from utils.integrations.realms.errors import HTTPFailure, StoriesError, RealmsError, TransportError
        posted = updated = 0
        stage = 'read_stories'
        success = False
        try:
            async with self._stories_post_lock:
                if asyncio.get_running_loop().time() < self._stories_retry_at:
                    return False, 'Stories service requested a cooldown; try again later.'
                if (channel is None or getattr(getattr(channel, "guild", None), "id", None) != guild_id
                        or not authorized()):
                    raise RuntimeError()
                permissions = channel.permissions_for(channel.guild.me)
                can_send = permissions.send_messages_in_threads if isinstance(channel, discord.Thread) else permissions.send_messages
                if not permissions.view_channel or not can_send or not permissions.embed_links:
                    return False, "I need View Channel, Send Messages, and Embed Links here."
                body = await self.runtime.club_story_feed(old_realm=True) if old_realm else await self.runtime.club_story_feed()
                if old_realm:
                    from .stories_archive import restore_archive
                    stage = 'restore_archive'
                    body = restore_archive(body)
                    from datetime import datetime, timezone
                    from zoneinfo import ZoneInfo
                    since = datetime(2026, 10, 31, tzinfo=ZoneInfo('America/Chicago'))
                    entries, skipped, remaining = render_feed(body, limit=None, since=since,
                                                              until=datetime.now(timezone.utc))
                else:
                    entries, skipped, remaining = render_feed(body, limit=None)
                if any((embed.image.url or '').startswith('attachment://') for _, embed in entries) and not permissions.attach_files:
                    return False, "I need Attach Files here to include Realm event artwork."
                from .story_deliveries import StoryDeliveries
                if self._story_deliveries is None:
                    self._story_deliveries = StoryDeliveries(getattr(self.runtime, 'store', None))
                stage = 'load_delivery_records'
                await self._story_deliveries.load()
                duplicates = 0
                source = body['sourceRealmId'] if old_realm else self.bot.settings['realms']['selected_realm_id']
                for identity, embed in entries:
                    if not authorized():
                        raise RuntimeError()
                    key = (guild_id, channel.id, source, identity)
                    delivery_key = StoryDeliveries.key(guild_id, channel.id, source, identity)
                    signature = StoryDeliveries.signature(embed)
                    previous = self._story_deliveries.entries.get(delivery_key)
                    stage = 'fetch_original_message'
                    original = None
                    if previous is not None:
                        try:
                            original = await channel.fetch_message(previous['message_id'])
                        except discord.NotFound as error:
                            if error.code != 10008:
                                raise
                            # Only Unknown Message confirms deletion. Preserve the
                            # checkpoint on permission/channel/transient failures.
                            previous = None
                            self._stories_sent.discard(key)
                    if not authorized():
                        raise RuntimeError()
                    if previous is not None:
                        if original.author.id != self.bot.user.id or not original.embeds:
                            raise RuntimeError()
                        if previous['footer'] != embed.footer.text or previous.get('signature') != signature:
                            if not authorized():
                                raise RuntimeError()
                            if original.author.id != self.bot.user.id or not original.embeds:
                                raise RuntimeError()
                            # Refresh reconstructed text as well as counters. Reuse
                            # Discord's existing artwork URL when one is available.
                            existing = embed.copy()
                            attachment = None
                            if original.embeds[0].image.url:
                                existing.set_image(url=original.embeds[0].image.url)
                            elif (embed.image.url or '').startswith('attachment://'):
                                attachment = artwork_file(embed)
                            try:
                                stage = 'edit_original_message'
                                await original.edit(embed=existing, allowed_mentions=discord.AllowedMentions.none(),
                                                    **({'attachments': [attachment]} if attachment else {}))
                            finally:
                                if attachment is not None:
                                    attachment.close()
                            await self._story_deliveries.save(delivery_key, original.id, embed.footer.text,
                                                              signature=signature)
                            updated += 1
                        else:
                            duplicates += 1
                        continue
                    if key in self._stories_sent:
                        duplicates += 1
                        continue
                    attachment = artwork_file(embed)
                    try:
                        stage = 'send_story'
                        sent_message = await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none(),
                                           **({'file': attachment} if attachment is not None else {}))
                    finally:
                        if attachment is not None:
                            attachment.close()
                    self._stories_sent.add(key)
                    posted += 1
                    # Memory guard is already set if checkpoint persistence fails.
                    if type(getattr(sent_message, 'id', None)) is int:
                        stage = 'save_delivery_record'
                        await self._story_deliveries.save(delivery_key, sent_message.id, embed.footer.text, signature=signature)
                source_label = " from OLD Coastal S10 (October 31, 2026 to now, America/Chicago)" if old_realm else ""
                message = f"Posted {posted} Stories embed(s){source_label} in this channel, oldest first. Updated {updated} existing post(s). Skipped {skipped} unsupported item(s), {duplicates} already posted."
                message += f" Realm feed in Minecraft (copy this address): `minecraft://openRealmsStories?realmId={source}`"
                if skipped:
                    message += " Items outside the date range, without a usable date, or with unsupported content were skipped." if old_realm else " Some feed fields or media references are not yet recognized; no raw metadata was published."
                success = True
        except discord.Forbidden:
            message = f"Posted {posted} Stories embed(s), updated {updated}. Discord denied permission at {stage}. I need View Channel, Read Message History, Send Messages, Embed Links and Attach Files here."
        except discord.HTTPException as error:
            message = f"Posted {posted} Stories embed(s), updated {updated}. Discord request failed at {stage} (HTTP {error.status}, code {error.code}). No private error details shown."
        except StoriesError as error:
            message = f"Posted {posted} Stories embed(s). {StoriesError.reasons[error.reason]} (Code: {error.reason}.)"
        except HTTPFailure as error:
            if error.retry_after is not None:
                self._stories_retry_at = asyncio.get_running_loop().time() + max(0, error.retry_after)
            message = f"Posted {posted} Stories embed(s). Feed unavailable (HTTP {error.status}); no feed retry made."
        except TransportError as error:
            message = f"Posted {posted} Stories embed(s), updated {updated}. Stopped at {stage}: {error.service} {error.reason}. Transient Stories reads are retried once; a later run can recover missing posts."
        except RealmsError as error:
            message = f"Posted {posted} Stories embed(s). Stopped: {error.category}. No private error details shown."
        except Exception:
            message = f"Posted {posted} Stories embed(s). Stopped at {stage}: Stories access, response format, channel permissions, or authorization unavailable. No private error details shown."
        return success, message

    @realm.command(name="storiesauto", description="Enable or pause the five-minute Stories sync (OP Team)")
    async def storiesauto(self, interaction: discord.Interaction, enabled: bool):
        if not permitted(self.bot.settings, interaction):
            await interaction.response.send_message("Realm commands require the Coastal OP Team role in Coastal Craft.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        await self.stories_sync.configure(enabled)
        await interaction.followup.send("Stories auto-update " + ("enabled every five minutes." if enabled else "paused."), ephemeral=True)

    @realm.command(name="storiesdebug", description="Inspect Realm Stories and referenced Xbox posts (staff only)")
    @app_commands.describe(old_realm="Inspect OLD Coastal S10 instead of the current Realm")
    async def storiesdebug(self, interaction: discord.Interaction, old_realm: bool = False):
        if not permitted(self.bot.settings, interaction):
            await interaction.response.send_message("Realm commands require the Coastal OP Team role in Coastal Craft.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        from utils.integrations.realms.errors import HTTPFailure, ReauthRequired
        try:
            if old_realm:
                message = {'source': 'old_realm', 'club_feed': {
                    'http_status': 200, 'body': await self.runtime.club_story_feed(old_realm=True)}}
            else:
                message = await self.runtime.stories_debug()
        except HTTPFailure as error:
            message = f"Stories feed HTTP status: {error.status}. Response not inspected or request rejected; no feed retry made."
            if error.status in {401, 403}:
                message += " Authentication or Stories access was rejected. Ask the operator to check access."
        except ReauthRequired:
            message = "Stories feed unavailable: operator reauthentication required. No feed response inspected."
        except Exception:
            message = "Stories feed unavailable: configuration, authentication, transport, or JSON response failure. HTTP status unavailable; no private error details shown."
        if not permitted(self.bot.settings, interaction):
            message = "You no longer have access to this Realm command."
        if isinstance(message, dict):
            serialized = json.dumps(message, ensure_ascii=False, indent=2)
            if len(serialized.encode("utf-8", errors="backslashreplace")) > 7 * 1024 * 1024:
                serialized = json.dumps(message, ensure_ascii=False, separators=(",", ":"))
            report = discord.File(io.BytesIO(serialized.encode("utf-8", errors="backslashreplace")), filename="realm-stories-investigation.json")
            await interaction.followup.send(
                ("Old Realm Stories diagnostic attached: all available Xbox club-feed pages and Realm event references. "
                 "Run before and after giving one heart to the same Story, then compare the attachments. "
                 "The attachment includes private Realm content; no auth headers or tokens are included. No Discord Stories were posted."
                 if old_realm else
                 "Stories investigation attached: Realm feed, one referenced Xbox post, and one club-feed page (up to 10 items). Successful response bodies are unredacted; failures include status when available. No retries or images fetched."),
                file=report, ephemeral=True, allowed_mentions=discord.AllowedMentions.none())
        elif message.startswith("HTTP status: 200\n\n"):
            # Only the response body is attached. Request headers and auth state
            # never enter this diagnostic. Role revocation above clears the body.
            body = message.split("\n\n", 1)[1]
            report = discord.File(io.BytesIO(body.encode("utf-8")), filename="realm-stories-feed.json")
            await interaction.followup.send(
                "HTTP status: 200. Full, unredacted Stories feed JSON attached.",
                file=report, ephemeral=True, allowed_mentions=discord.AllowedMentions.none())
        else:
            await interaction.followup.send(message, ephemeral=True, allowed_mentions=discord.AllowedMentions.none())

    @daily_group.command(name="enable", description="Enable daily reports in a chosen public channel")
    @app_commands.describe(channel="Public Coastal Craft text channel for daily reports")
    async def daily_enable(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await self.configure_daily(interaction, True, channel)

    @daily_group.command(name="disable", description="Stop daily collection and automatic report updates")
    async def daily_disable(self, interaction: discord.Interaction):
        await self.configure_daily(interaction, False)

    async def configure_daily(self, interaction, enabled, channel=None):
        if not permitted(self.bot.settings, interaction):
            await interaction.response.send_message("Realm commands require the Coastal OP Team role in Coastal Craft.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            await self.daily_reports.configure(enabled, channel)
        except ValueError as error:
            await interaction.followup.send(str(error), ephemeral=True, allowed_mentions=discord.AllowedMentions.none())
            return
        message = (f"Daily Realm reports enabled in {channel.mention}. Activity history collection is enabled; reports use America/Chicago time."
                   if enabled else "Daily Realm reports disabled. Existing messages are preserved.")
        await interaction.followup.send(message, ephemeral=True, allowed_mentions=discord.AllowedMentions.none())

    @daily_group.command(name="preview", description="Privately preview today's observed Realm timeline")
    async def daily_preview(self, interaction: discord.Interaction):
        await self.daily_response(interaction, preview=True)

    @daily_group.command(name="refresh", description="Refresh today's public report")
    async def daily_refresh(self, interaction: discord.Interaction):
        await self.daily_response(interaction, preview=False)

    @daily_group.command(name="import", description="Import available activity timelines from current and OLD Coastal S10")
    async def daily_import(self, interaction: discord.Interaction):
        if not permitted(self.bot.settings, interaction):
            await interaction.response.send_message("Realm commands require the Coastal OP Team role in Coastal Craft.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        from .daily import database
        from utils.players.activity import ingest
        from utils.players.activity_models import RealmActivity
        from .daily_timeline import ZONE
        async with self.daily_reports.lock:
            if not self.bot.settings.get('realm_history_enabled'):
                await interaction.followup.send("Enable activity history with /realm daily enable first.", ephemeral=True)
                return
            if not await database(RealmActivity.table_exists):
                await interaction.followup.send("The Realm activity table is missing; an operator must apply the activity migration.", ephemeral=True)
                return
            results = []
            for label, old in (('Current Realm', False), ('OLD Coastal S10', True)):
                if not permitted(self.bot.settings, interaction):
                    return
                try:
                    if old:
                        realm, snapshot = await self.runtime.archive_stories()
                    else:
                        realm = self.runtime.config.selected_realm_id
                        view, _ = await self.runtime.observe(scheduled=True)
                        snapshot = await self.runtime.stories()
                    if not permitted(self.bot.settings, interaction):
                        return
                    counts = await database(lambda: ingest(snapshot, realm))
                    valid = [item for item in snapshot.data if item.status == 'observed']
                    coverage = (f" Returned coverage: {min(i.start for i in valid).astimezone(ZONE):%Y-%m-%d %H:%M %Z} to "
                                f"{max(i.end for i in valid).astimezone(ZONE):%Y-%m-%d %H:%M %Z}." if valid
                                else ' No usable activity intervals returned; history may be unavailable.')
                    results.append(f"{label}: {counts['created']} added, {counts['existing']} already stored, {counts['quarantined']} quarantined." + coverage)
                    if not old:
                        from datetime import datetime, timezone
                        from .presence import verify_future_intervals, save_sample, PresenceSample
                        verification = verify_future_intervals(snapshot, view, datetime.now(timezone.utc))
                        if verification:
                            if await database(PresenceSample.table_exists):
                                await database(lambda: save_sample(view, realm))
                            names = {p.xuid: p.name for p in view.activity.data.players} if view.activity else {}
                            details = []
                            for xuid, state in verification.items():
                                name = safe_name(names[xuid], 40) if names.get(xuid) else 'Unnamed player'
                                details.append(f"{name}: {state}")
                            results.append('Future-ended history / fresh player-list check: ' + '; '.join(details) +
                                '. Online time is taken from saved presence samples only; future end times remain excluded. Unknown means the player-list observation was unavailable, incomplete, or over 45 seconds old.')

                except Exception as error:
                    import logging
                    logging.getLogger(__name__).warning('Manual timeline import unavailable for %s (%s)', label, type(error).__name__)
                    results.append(f"{label}: activity import unavailable or cooling down; no missing history was interpreted as inactivity.")
            await interaction.followup.send('\n'.join(results) +
                '\nAPI timestamps are preserved, including hourly boundaries. These are observed intervals, not verified sessions. Each Realm is stored separately; repeated imports do not duplicate intervals. No timeline is inferred from Story posts.',
                ephemeral=True, allowed_mentions=discord.AllowedMentions.none())

    @daily_group.command(name="history", description="Preview or post combined Coastal Realm history for a date")
    @app_commands.describe(day="Report date in YYYY-MM-DD format (America/Chicago)",
                           publish="Post to the configured report channel; otherwise preview privately")
    async def daily_history(self, interaction: discord.Interaction, day: str, publish: bool = False):
        if not permitted(self.bot.settings, interaction):
            await interaction.response.send_message("Realm commands require the Coastal OP Team role in Coastal Craft.", ephemeral=True)
            return
        from datetime import date
        try:
            selected = date.fromisoformat(day)
            if selected.isoformat() != day:
                raise ValueError()
        except ValueError:
            await interaction.response.send_message("Use a date in YYYY-MM-DD format.", ephemeral=True)
            return
        await self.daily_response(interaction, preview=not publish, day=selected)

    async def daily_response(self, interaction, *, preview, day=None):
        if not permitted(self.bot.settings, interaction):
            await interaction.response.send_message("Realm commands require the Coastal OP Team role in Coastal Craft.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        from .daily import DailyUnavailable
        try:
            result = await self.daily_reports.refresh(preview=preview, day=day)
        except DailyUnavailable as error:
            await interaction.followup.send(str(error), ephemeral=True, allowed_mentions=discord.AllowedMentions.none())
            return
        if preview:
            embed, png = result
            if permitted(self.bot.settings, interaction):
                attachment = discord.File(io.BytesIO(png), filename="realm-daily.png")
                try:
                    await interaction.followup.send(file=attachment, ephemeral=True,
                                                    allowed_mentions=discord.AllowedMentions.none())
                finally:
                    attachment.close()
        elif permitted(self.bot.settings, interaction):
            ok = result
            await interaction.followup.send("Daily report refreshed." if ok else "Report recovery is pending; try again later.", ephemeral=True)

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
