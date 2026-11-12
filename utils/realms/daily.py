"""Opt-in hourly collection and one recoverable public daily message."""
import asyncio
from datetime import date, datetime, timedelta, timezone
import hashlib
import io
import json
import logging

import discord
from discord.ext import tasks
from utils.database.__database import db
from utils.players.activity import ingest, verified_player
from utils.players.activity_models import RealmActivity
from utils.players.models import Player, utcnow
from .daily_models import DailyCollection, DailyReport
from .presence import PresenceSample, save_sample, prefer_presence
from .daily_timeline import ZONE, aggregate, window, render

log = logging.getLogger(__name__)


class DailyUnavailable(RuntimeError):
    """Safe actionable staff error."""


def validate_daily(value):
    if (not isinstance(value, dict) or set(value) != {'enabled', 'channel_id'}
            or type(value['enabled']) is not bool
            or type(value['channel_id']) is not int
            or not 0 < value['channel_id'] < 2**63):
        raise ValueError('Invalid realm_daily settings')


async def database(call):
    def run():
        with db.connection_context():
            return call()
    # Finish DB commits before propagating shutdown cancellation.
    task = asyncio.create_task(asyncio.to_thread(run))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        await task
        raise


def matches_report(message, marker):
    # Existing embed reports remain recoverable during the switch to attachments.
    filename = marker.replace(':', '-') + '.png'
    return (any(a.filename == filename for a in getattr(message, 'attachments', ()))
            or any(e.footer.text == marker for e in message.embeds))


class DailyController:
    def __init__(self, bot, runtime):
        self.bot, self.runtime = bot, runtime
        self.lock = asyncio.Lock()
        self.slot = None
        self.finalized_day = None
        self.retry_at = None
        self.runtime.activity_recorder = self.record_presence

    async def record_presence(self, view):
        if self.enabled():
            await database(lambda: save_sample(view, self.runtime.config.selected_realm_id))

    def enabled(self):
        return (self.bot.settings.get('realm_daily', {}).get('enabled') is True
                and self.bot.settings.get('realms', {}).get('enabled') is True
                and self.bot.settings.get('realm_history_enabled') is True)

    def start(self):
        if self.enabled() and not self.poll.is_running():
            self.poll.start()

    async def close(self):
        task = self.poll.get_task()
        self.poll.cancel()
        if task:
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def configure(self, enabled, channel=None):
        async with self.lock:
            current = self.bot.settings.get('realm_daily')
            if not enabled and current is None:
                return
            if enabled:
                if not self.bot.settings.get('realms', {}).get('enabled'):
                    raise ValueError('Enable the Realms integration before daily reports.')
                if channel is None or channel.guild.id != self.bot.settings['Coastal']:
                    raise ValueError('Choose a text channel in Coastal Craft.')
                permissions = channel.permissions_for(channel.guild.me)
                if not all(getattr(permissions, name, False) for name in
                           ('view_channel', 'read_message_history', 'send_messages', 'attach_files')):
                    raise ValueError('I need View Channel, Read Message History, Send Messages, and Attach Files in that channel.')
            value = dict(enabled=enabled, channel_id=channel.id if enabled else current['channel_id'])
            validate_daily(value)
            def save():
                from utils.configuration import validate_document
                if enabled and not all(model.table_exists() for model in (DailyReport, DailyCollection, RealmActivity)):
                    raise ValueError('Run the explicit Realm activity and daily report migrations before enabling reports.')
                with db.atomic():
                    row = db.execute_sql('SELECT settings_json FROM botdata WHERE id=1 FOR UPDATE').fetchone()
                    document = json.loads(row[0])
                    document['settings']['realm_daily'] = value
                    if enabled:
                        document['settings']['realm_history_enabled'] = True
                    validate_document(document)
                    db.execute_sql('UPDATE botdata SET settings_json=%s WHERE id=1', (json.dumps(document),))
            await database(save)
            self.bot.settings['realm_daily'] = value
            if enabled:
                self.bot.settings['realm_history_enabled'] = True
                self.runtime._history_enabled = True
            self.slot = None
            self.retry_at = None
        if enabled:
            self.start()
        else:
            await self.close()

    async def collect(self):
        realm = self.runtime.config.selected_realm_id
        now = utcnow()
        def claim():
            row, _ = DailyCollection.get_or_create(realm=realm)
            return DailyCollection.update(attempted=now, outcome='pending').where(
                (DailyCollection.id == row.id) & ((DailyCollection.attempted.is_null()) |
                (DailyCollection.attempted <= now-timedelta(seconds=295)))).execute()
        if not await database(claim):
            return
        try:
            snapshot = await self.runtime.stories()
            def save():
                with db.atomic():
                    ingest(snapshot, realm)
                    DailyCollection.update(succeeded=snapshot.observed_at.astimezone(timezone.utc).replace(tzinfo=None),
                                           outcome='available').where(DailyCollection.realm == realm).execute()
            await database(save)
        except Exception:
            await database(lambda: DailyCollection.update(outcome='unavailable').where(
                DailyCollection.realm == realm).execute())
            log.warning('Daily Realm collection unavailable')

    def report_realms(self, day):
        current = self.runtime.config.selected_realm_id
        if day >= datetime.now(ZONE).date():
            return (current,)
        # The reviewed archive mapping is the same one used by old Stories restoration.
        from utils.core_features.__constants import ROOT
        old = json.loads((ROOT / 'config' / 'old-coastal-s10-stories.json').read_text(encoding='utf-8'))['realm_id']
        return tuple(dict.fromkeys((current, old)))

    async def report(self, day):
        realm = self.runtime.config.selected_realm_id
        realms = self.report_realms(day)
        lo, hi = (v.replace(tzinfo=None) for v in window(day))
        def read():
            rows, samples = [], []
            has_presence = PresenceSample.table_exists()
            for source in realms:
                source_rows = list(RealmActivity.select(RealmActivity.xuid, RealmActivity.start, RealmActivity.end).where(
                    (RealmActivity.realm_id == source) & (RealmActivity.status == 'observed') &
                    (RealmActivity.start < hi) & (RealmActivity.end > lo)).tuples())
                source_samples = []
                if has_presence:
                    source_samples = [(sample.observed, json.loads(sample.online)) for sample in
                               PresenceSample.select().where((PresenceSample.realm == source) &
                               (PresenceSample.observed >= lo-timedelta(seconds=45)) &
                               (PresenceSample.observed <= hi+timedelta(seconds=45))).order_by(PresenceSample.observed)]
                # Presence on one Realm cannot invalidate activity on the other.
                rows.extend(prefer_presence(source_rows, source_samples))
                samples.extend(source_samples)
            samples.sort(key=lambda item: item[0])
            names, linked = {}, {}
            for xuid in {r[0] for r in rows if r[0]}:
                player_id = verified_player(xuid)
                player = Player.get_or_none(Player.id == player_id) if player_id else None
                if player:
                    if player.gamertag:
                        names[xuid] = player.gamertag
                    if player.discord_id:
                        linked[xuid] = (player.discord_id, player.discord_name)
            state = DailyCollection.get_or_none(DailyCollection.realm == realm)
            success = max([v for v in [state.succeeded if state else None,
                                       samples[-1][0] if samples else None] if v], default=None)
            return rows, names, linked, (success, state.outcome if state else 'unavailable')
        rows, names, linked, (success, outcome) = await database(read)
        groups, count, seconds = aggregate(rows, day)
        if self.runtime.names is not None:
            try:
                for start in range(0, len(groups), 100):
                    names.update(await self.runtime.names.resolve(list(groups)[start:start+100]))
            except Exception:
                pass
        guild = self.bot.get_guild(self.bot.settings['Coastal'])
        display = {}
        for xuid in groups:
            discord_name = None
            if xuid in linked:
                discord_id, stored_name = linked[xuid]
                member = guild.get_member(discord_id) if guild else None
                discord_name = member.display_name if member else stored_name
            display[xuid] = {'gamertag': names.get(xuid), 'discord': discord_name}
        names = display
        status = ('Last successful collection: ' + f'<t:{int(success.replace(tzinfo=timezone.utc).timestamp())}:f>'
                  if success else 'No successful automatic collection recorded.')
        status += ('\nIn progress; future hours have not elapsed.' if day == datetime.now(ZONE).date() else '\nScheduled updates finalized; observations may be incomplete.')
        status += '\nLatest collection: ' + outcome + '. Coverage is partial and unverified.'
        embed = discord.Embed(title='Daily Realm Activity Summary',
                              description='Missing data does not establish inactivity.', color=0x78B84A)
        embed.add_field(name='Unique observed players', value=str(len(groups)))
        embed.add_field(name='Combined observed activity', value=f'{int(seconds//3600)}h {int(seconds%3600//60)}m')
        embed.add_field(name='Observed activity intervals', value=str(count))
        embed.add_field(name='Collection status', value=status, inline=False)
        if success:
            embed.timestamp = success.replace(tzinfo=timezone.utc)
        embed.set_image(url='attachment://realm-daily.png')
        # Include source interval count and merged spans; never publish identifiers.
        content = ['season10-unified-history-v8', day.isoformat(), embed.to_dict(), [(x, names.get(x), [(a.isoformat(), b.isoformat()) for a, b in spans])
                                     for x, spans in sorted(groups.items())]]
        signature = hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()
        return embed, signature, groups, names

    async def publish(self, day):
        async with asyncio.timeout(480):
            return await self._publish(day)

    async def _publish(self, day):
        config = self.bot.settings['realm_daily']
        guild, channel_id, realm = self.bot.settings['Coastal'], config['channel_id'], self.runtime.config.selected_realm_id
        now = utcnow()
        def claim():
            row, _ = DailyReport.get_or_create(guild=guild, channel=channel_id, realm=realm, day=day)
            changed = DailyReport.update(lease=now+timedelta(minutes=10)).where(
                (DailyReport.id == row.id) & ((DailyReport.lease.is_null()) | (DailyReport.lease < now))).execute()
            return DailyReport.get_by_id(row.id) if changed else None
        row = await database(claim)
        if row is None:
            return False
        try:
            channel = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id)
            if getattr(getattr(channel, 'guild', None), 'id', None) != guild:
                raise ValueError('Wrong daily report guild')
            marker = 'realm-daily:' + hashlib.sha256(f'{guild}:{channel_id}:{realm}:{day}'.encode()).hexdigest()[:24]
            message = None
            if row.message:
                # A deleted original needs staff intervention; never silently republish.
                message = await channel.fetch_message(row.message)
                if message.author.id != self.bot.user.id or not matches_report(message, marker):
                    raise ValueError('Daily report identity mismatch')
            elif row.pending_since:
                if now < row.pending_since+timedelta(minutes=5):
                    return False
                # Exhaust the relevant history. Any read failure prevents a retry.
                async for candidate in channel.history(limit=None, after=row.pending_since.replace(tzinfo=timezone.utc)-timedelta(minutes=1), oldest_first=True):
                    if candidate.author.id == self.bot.user.id and matches_report(candidate, marker):
                        message = candidate
                        break
                if message:
                    await database(lambda: DailyReport.update(message=message.id).where(DailyReport.id == row.id).execute())
            embed, signature, groups, names = await self.report(day)
            if message and row.signature == signature:
                return True
            png = await asyncio.to_thread(render, day, groups, names, embed.timestamp)
            attachment = discord.File(io.BytesIO(png), filename=marker.replace(':', '-') + '.png')
            try:
                if message:
                    await message.edit(content=None, embeds=[], attachments=[attachment], allowed_mentions=discord.AllowedMentions.none())
                else:
                    await database(lambda: DailyReport.update(pending_since=utcnow()).where(DailyReport.id == row.id).execute())
                    message = await channel.send(file=attachment, allowed_mentions=discord.AllowedMentions.none())
            finally:
                attachment.close()
            await database(lambda: DailyReport.update(message=message.id, signature=signature, pending_since=None).where(
                DailyReport.id == row.id).execute())
            return True
        finally:
            await database(lambda: DailyReport.update(lease=None).where(DailyReport.id == row.id).execute())

    async def refresh(self, *, preview=False, day=None):
        async with self.lock:
            if not preview and not self.enabled():
                raise DailyUnavailable('Daily reports are disabled. Use /realm daily enable and choose a channel first.')
            stage = 'database'
            try:
                def check_schema():
                    return all(model.table_exists() for model in (RealmActivity, DailyCollection, DailyReport))
                if not await database(check_schema):
                    raise DailyUnavailable('Daily report tables are missing. An operator must run the explicit Realm activity and daily report migrations; preview does not create tables.')
                # Preview needs stored observations, not enabled reporting or working auth.
                if not preview:
                    stage = 'collection'
                    await self.collect()
                today = datetime.now(ZONE).date()
                day = day or today
                if day > today:
                    raise DailyUnavailable('Choose today or a past date in YYYY-MM-DD format.')
                if day < today:
                    lo, hi = (v.replace(tzinfo=None) for v in window(day))
                    realms = self.report_realms(day)
                    if not await database(lambda: RealmActivity.select().where(
                            (RealmActivity.realm_id.in_(realms)) &
                            (RealmActivity.status == 'observed') & (RealmActivity.start < hi) &
                            (RealmActivity.end > lo)).exists() or (PresenceSample.table_exists() and
                            PresenceSample.select().where((PresenceSample.realm.in_(realms)) &
                            (PresenceSample.observed >= lo) & (PresenceSample.observed < hi) &
                            (PresenceSample.online != '[]')).exists())):
                        raise DailyUnavailable('No stored activity observations overlap that date for Coastal Craft (current or old Realm). Missing history does not establish inactivity.')
                if preview:
                    stage = 'report data'
                    embed, _, groups, names = await self.report(day)
                    stage = 'PNG rendering'
                    png = await asyncio.to_thread(render, day, groups, names, embed.timestamp)
                    return embed, png
                stage = 'Discord delivery'
                return await self.publish(day)
            except DailyUnavailable:
                raise
            except ModuleNotFoundError as error:
                log.warning('Daily report failed at %s (%s)', stage, type(error).__name__)
                if error.name == 'PIL':
                    raise DailyUnavailable('Timeline rendering needs Pillow. An operator must install the pinned requirements and restart the bot.') from None
                raise DailyUnavailable('A daily report Python dependency is missing. An operator must check the installed requirements.') from None
            except Exception as error:
                log.warning('Daily report failed at %s (%s)', stage, type(error).__name__)
                raise DailyUnavailable(f'Daily report unavailable at {stage}. An operator should check the bot logs for this stage.') from None

    async def scheduled_refresh(self):
        now = datetime.now(ZONE)
        if not self.enabled():
            return
        try:
            async with self.lock:
                await self.collect()
                # One image per five-minute slot; roll over at 00:05, not 00:00.
                slot = (now.date(), now.hour, now.minute // 5)
                if (now.hour != 0 or now.minute >= 5) and self.slot != slot and (self.retry_at is None or utcnow() >= self.retry_at):
                    yesterday = now.date()-timedelta(days=1)
                    if self.finalized_day != yesterday:
                        config = self.bot.settings['realm_daily']
                        existing = await database(lambda: DailyReport.select().where(
                            (DailyReport.guild == self.bot.settings['Coastal']) &
                            (DailyReport.channel == config['channel_id']) &
                            (DailyReport.realm == self.runtime.config.selected_realm_id) &
                            (DailyReport.day == yesterday)).exists())
                        if not existing or await self.publish(yesterday):
                            self.finalized_day = yesterday
                    if await self.publish(now.date()):
                        self.slot = slot
        except Exception:
            self.retry_at = utcnow()+timedelta(minutes=5)
            log.warning('Daily Realm report unavailable; retry deferred')

    @tasks.loop(seconds=15)
    async def poll(self):
        # Only presence sampling has its own fast cadence. Stories owns the shared
        # five-minute collection/render timer, independent of forwarding enablement.
        if self.enabled():
            try:
                await self.runtime.observe(scheduled=True)
            except Exception:
                log.warning('Daily Realm presence observation unavailable')

    @poll.before_loop
    async def wait_ready(self):
        await self.bot.wait_until_ready()
