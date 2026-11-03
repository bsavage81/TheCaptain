"""One persistent, on-demand configured panel using the shared Realm runtime."""
import asyncio
from datetime import datetime, timezone
import json
import logging
import math

import discord
from discord.ext import tasks

log = logging.getLogger(__name__)


def validate_panel(value, guild):
    if value is None:
        return
    if not isinstance(value, dict) or set(value) != {"guild_id", "channel_id", "message_id", "interval_seconds"}:
        raise ValueError("Invalid Realm panel configuration")
    if any(type(value[k]) is not int or not 0 < value[k] < 2**64 for k in ("guild_id", "channel_id", "message_id")):
        raise ValueError("Invalid Realm panel IDs")
    if value["guild_id"] != guild or type(value["interval_seconds"]) is not int or not 15 <= value["interval_seconds"] <= 3600:
        raise ValueError("Invalid Realm panel guild or interval")


class PanelRepository:
    """Only update the optional panel block in the existing singleton JSON column."""
    def save(self, value, guild):
        from utils.database.__database import db
        from utils.configuration import validate_document
        validate_panel(value, guild)
        with db.connection_context(), db.atomic():
            row = db.execute_sql("SELECT settings_json FROM botdata WHERE id=1 FOR UPDATE").fetchone()
            document = json.loads(row[0])
            if value is None:
                document["settings"].pop("realm_panel", None)
            else:
                document["settings"]["realm_panel"] = value
            validate_document(document)
            db.execute_sql("UPDATE botdata SET settings_json=%s WHERE id=1", (json.dumps(document),))


class Sessions:
    """First observed online, never an inferred login time. XUIDs stay private."""
    def __init__(self, realm_id, data=None):
        self.realm_id = realm_id
        self.active = {}
        self.last_observation = 0
        if data is not None:
            if not isinstance(data, dict) or data.get("realm_id") != realm_id:
                raise ValueError("Invalid private session state")
            active = data.get("active")
            last = data.get("last_observation")
            if not isinstance(active, dict) or len(active) > 1000 or type(last) not in (int, float) or not math.isfinite(last) or last < 0:
                raise ValueError("Invalid private session state")
            for xuid, start in active.items():
                if not isinstance(xuid, str) or not xuid.isascii() or not xuid.isdigit() or len(xuid) > 32 or type(start) not in (int, float) or not math.isfinite(start) or not 0 <= start <= last:
                    raise ValueError("Invalid private session state")
            self.active = dict(active)
            self.last_observation = last

    def document(self):
        return dict(realm_id=self.realm_id, active=self.active, last_observation=self.last_observation)

    @staticmethod
    def authoritative(view):
        return bool(view.activity_available and view.activity and all(
            type(p.online) is bool and isinstance(p.xuid, str) and p.xuid.isascii() and p.xuid.isdigit()
            for p in view.activity.data.players))

    def observe(self, view):
        if not self.authoritative(view):
            return False
        now = view.activity.observed_at.timestamp()
        if now <= self.last_observation:
            return False
        online = {p.xuid for p in view.activity.data.players if p.online is True}
        updated = {xuid: self.active.get(xuid, now) for xuid in online}
        changed = updated != self.active
        self.active = updated
        # Persist observation boundary as well, but only when membership changes.
        self.last_observation = now
        return changed

    def duration(self, player, now, *, reliable):
        start = self.active.get(player.xuid) if reliable and player.online is True else None
        if start is None:
            return "Duration unavailable"
        minutes = max(0, int((now - start) // 60))
        value = f"{minutes}m" if minutes < 60 else f"{minutes // 60}h {minutes % 60}m"
        return "Tracked for " + value


def panel_embed(view, sessions, interval, *, now=None, storage_ok=True):
    from .cog import safe_name
    now = now or datetime.now(timezone.utc)
    realm = view.realm.data if view.realm else None
    state = realm.state if realm and view.realm_available else None
    label, colour = {"OPEN": ("🟢 ONLINE", 0x2ECC71), "CLOSED": ("🔴 OFFLINE", 0xE74C3C)}.get(
        state, ("🟡 UNAVAILABLE", 0xF1C40F))
    embed = discord.Embed(title="🏴‍☠️ Coastal Craft | Realm Status", colour=colour)
    embed.add_field(name="Realm", value=safe_name(realm.name) if realm else "Unavailable", inline=False)
    embed.add_field(name="Status", value=label)
    available = view.activity_available and view.activity is not None
    players = view.activity.data.players if available else ()
    online = [p for p in players if p.online is True]
    unknown = any(p.online is None for p in players)
    count = str(len(online)) if available and not unknown else (f"At least {len(online)} (incomplete)" if available else "Unknown")
    embed.add_field(name="Players Online", value=count)
    reliable = storage_ok and sessions.authoritative(view)
    lines = []
    named = [p for p in online if p.name]
    for player in named[:20]:
        lines.append(f"{safe_name(player.name, 40)} — {sessions.duration(player, now.timestamp(), reliable=reliable)}")
    unnamed = len(online) - len(named)
    if unnamed:
        lines.append(f"Player names unavailable for {unnamed} player(s) — Duration unavailable")
    if not available or unknown:
        lines.append("Player activity unavailable or incomplete")
    elif not online:
        lines.append("No players online")
    if len(named) > 20:
        lines.append("Additional players omitted")
    # Discord fields cap at 1024 characters. Never include private IDs.
    content = "\n".join(lines)
    if len(content) > 1024:
        content = content[:990].rsplit("\n", 1)[0] + "\nAdditional players omitted"
    embed.add_field(name="Current Players", value=content, inline=False)
    observed = []
    for name, snapshot in (("Status", view.realm), ("Activity", view.activity)):
        observed.append(f"{name}: <t:{int(snapshot.observed_at.timestamp())}:T>" if snapshot else f"{name}: unavailable")
    embed.add_field(name="Last successful observations", value=" • ".join(observed), inline=False)
    stale = not view.realm_available or not view.activity_available
    embed.set_footer(text=("Stale / unavailable • " if stale else "") + f"Auto-refresh: {interval} seconds • Durations are observed estimates")
    return embed


class PanelController:
    def __init__(self, bot, runtime, *, repository=None):
        self.bot, self.runtime = bot, runtime
        self.repository = repository or PanelRepository()
        self.config = bot.settings.get("realm_panel")
        validate_panel(self.config, bot.settings.get("Coastal"))
        self.lock = asyncio.Lock()
        self.sessions = Sessions(runtime.config.selected_realm_id) if hasattr(runtime, "config") else None
        self.loaded_sessions = False
        self.storage_ok = False
        self.message = None
        self.missing = False
        self.last_embed = None
        self.failures = 0
        self.retry_at = 0

    def start(self):
        self.poll.start()

    async def close(self):
        task = self.poll.get_task()
        self.poll.cancel()
        if task:
            await asyncio.gather(task, return_exceptions=True)

    async def save(self, value):
        await asyncio.to_thread(self.repository.save, value, self.bot.settings["Coastal"])
        self.config = value
        if value is None:
            self.bot.settings.pop("realm_panel", None)
        else:
            self.bot.settings["realm_panel"] = value

    async def update_sessions(self, view):
        store = self.runtime.store
        if not store:
            self.storage_ok = False
            return
        try:
            if not self.loaded_sessions:
                data = await asyncio.to_thread(store.load_panel_sessions)
                self.sessions = Sessions(self.runtime.config.selected_realm_id, data)
                self.loaded_sessions = True
            candidate = Sessions(self.sessions.realm_id, self.sessions.document())
            changed = candidate.observe(view)
            if changed:
                await asyncio.to_thread(store.save_panel_sessions, candidate.document())
            self.sessions = candidate
            self.storage_ok = True
        except Exception:
            self.storage_ok = False
            log.warning("Realm panel session storage unavailable")

    async def resolve(self):
        if self.message is not None:
            return self.message
        guild = self.bot.get_guild(self.config["guild_id"])
        if guild is None:
            raise RuntimeError("Panel guild unavailable")
        channel = guild.get_channel(self.config["channel_id"])
        if channel is None:
            channel = await guild.fetch_channel(self.config["channel_id"])
        self.message = await channel.fetch_message(self.config["message_id"])
        if self.message.author.id != self.bot.user.id:
            raise RuntimeError("Panel message is not Captain-owned")
        return self.message

    async def refresh(self, *, manual=False):
        async with self.lock:
            if not self.config or self.missing:
                return False
            clock = asyncio.get_running_loop().time()
            if clock < self.retry_at:
                return False
            try:
                message = await self.resolve()
                view, _ = await self.runtime.observe(force=manual, scheduled=not manual)
                await self.update_sessions(view)
                embed = panel_embed(view, self.sessions, self.config["interval_seconds"], storage_ok=self.storage_ok)
                value = embed.to_dict()
                if value != self.last_embed:
                    await message.edit(embed=embed, allowed_mentions=discord.AllowedMentions.none())
                    self.last_embed = value
                self.failures = 0
                return True
            except discord.NotFound:
                self.missing = True
                self.message = None
                log.warning("Realm panel message/channel missing; use /realm panel create")
            except Exception:
                self.failures += 1
                self.retry_at = clock + min(900, 15 * 2 ** min(self.failures - 1, 6))
                log.warning("Realm panel update unavailable; backing off")
            return False

    async def create(self, channel):
        async with self.lock:
            if channel.guild.id != self.bot.settings["Coastal"]:
                raise ValueError("Wrong panel guild")
            interval = self.config["interval_seconds"] if self.config else 15
            if self.config and not self.missing:
                try:
                    old = await self.resolve()
                except discord.NotFound:
                    old = None
                if old is not None and old.channel.id == channel.id:
                    return old.jump_url
                # Delete before relocation. A permission failure must not create a duplicate.
                if old is not None:
                    await old.delete()
                await self.save(None)
                self.message = None
            elif self.config:
                await self.save(None)
            view, _ = await self.runtime.observe()
            await self.update_sessions(view)
            embed = panel_embed(view, self.sessions, interval, storage_ok=self.storage_ok)
            message = await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
            try:
                await self.save(dict(guild_id=channel.guild.id, channel_id=channel.id, message_id=message.id, interval_seconds=interval))
            except BaseException:
                await message.delete()
                raise
            self.message, self.missing = message, False
            self.last_embed = embed.to_dict()
            self.retry_at = 0
            return message.jump_url

    async def remove(self):
        async with self.lock:
            if self.config:
                try:
                    await (await self.resolve()).delete()
                except discord.NotFound:
                    pass
                await self.save(None)
            self.message, self.last_embed = None, None
            self.missing = False

    @tasks.loop(seconds=15)
    async def poll(self):
        try:
            if self.config:
                interval = self.config["interval_seconds"]
                if self.poll.seconds != interval:
                    self.poll.change_interval(seconds=interval)
                await self.refresh()
        except Exception:
            log.warning("Realm panel scheduler unavailable")

    @poll.before_loop
    async def wait_ready(self):
        await self.bot.wait_until_ready()
