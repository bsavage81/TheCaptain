"""Five-minute current-Realm Stories sync, using the cog's shared publisher."""
import asyncio
import json
import logging

from discord.ext import tasks

log = logging.getLogger(__name__)
DESTINATION = 1570170968775590079


def validate_sync(value, guild):
    if (not isinstance(value, dict) or set(value) != {'enabled', 'guild_id', 'channel_id', 'realm_id', 'interval_seconds'}
            or type(value['enabled']) is not bool or value['guild_id'] != guild
            or type(value['guild_id']) is not int or value['guild_id'] <= 0
            or type(value['channel_id']) is not int or not 0 < value['channel_id'] < 2**64
            or value['interval_seconds'] != 300 or type(value['interval_seconds']) is not int
            or not isinstance(value['realm_id'], str) or not value['realm_id'].isascii()
            or not value['realm_id'].isdigit() or not 0 < int(value['realm_id']) < 2**64):
        raise ValueError('Invalid Stories sync configuration')


class StoriesRepository:
    def save(self, value, guild):
        from utils.database.__database import db
        from utils.configuration import validate_document
        validate_sync(value, guild)
        with db.connection_context(), db.atomic():
            row = db.execute_sql('SELECT settings_json FROM botdata WHERE id=1 FOR UPDATE').fetchone()
            document = json.loads(row[0])
            document['settings']['realm_stories'] = value
            validate_document(document)
            db.execute_sql('UPDATE botdata SET settings_json=%s WHERE id=1', (json.dumps(document),))


class StoriesController:
    def __init__(self, bot, runtime, publish, *, repository=None, clock=None):
        self.bot, self.runtime, self.publish = bot, runtime, publish
        self.repository = repository or StoriesRepository()
        self.clock = clock or (lambda: asyncio.get_running_loop().time())
        self.config = bot.settings.get('realm_stories')
        if self.config is not None:
            validate_sync(self.config, bot.settings.get('Coastal'))
        self.lock = asyncio.Lock()
        self.failures = 0
        self.retry_at = 0

    def start(self):
        if not self.poll.is_running():
            log.info('Stories scheduler starting; interval_seconds=300; enabled=%s', self.config['enabled'] if self.config else 'pending_initial_setup')
            self.poll.start()

    async def close(self):
        task = self.poll.get_task()
        self.poll.cancel()
        if task is not None:
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def configure(self, enabled):
        async with self.lock:
            value = dict(enabled=enabled, guild_id=self.bot.settings['Coastal'],
                         channel_id=self.config['channel_id'] if self.config else DESTINATION,
                         realm_id=self.bot.settings['realms']['selected_realm_id'], interval_seconds=300)
            await asyncio.to_thread(self.repository.save, value, self.bot.settings['Coastal'])
            self.config = value
            self.bot.settings['realm_stories'] = value
            self.failures = 0
            self.retry_at = 0

    def authorized(self, config):
        realms = self.bot.settings.get('realms', {})
        return (self.config == config and config['enabled'] and realms.get('enabled') is True
                and realms.get('selected_realm_id') == config['realm_id']
                and self.bot.settings.get('Coastal') == config['guild_id']
                and getattr(getattr(self.runtime, 'config', None), 'selected_realm_id', config['realm_id']) == config['realm_id'])

    async def refresh(self):
        async with self.lock:
            owner_retry = getattr(getattr(self.publish, '__self__', None), '_stories_retry_at', 0)
            if self.clock() < max(self.retry_at, owner_retry):
                return False
            try:
                realms = self.bot.settings.get('realms', {})
                if not realms.get('enabled'):
                    return False
                if self.config is None:
                    # Initial destination explicitly authorized by the operator.
                    value = dict(enabled=True, guild_id=self.bot.settings['Coastal'], channel_id=DESTINATION,
                                 realm_id=realms['selected_realm_id'], interval_seconds=300)
                    await asyncio.to_thread(self.repository.save, value, self.bot.settings['Coastal'])
                    self.config = value
                    self.bot.settings['realm_stories'] = value
                config = dict(self.config)
                if not self.authorized(config):
                    return False
                channel = self.bot.get_channel(config['channel_id'])
                if channel is None:
                    channel = await self.bot.fetch_channel(config['channel_id'])
                if getattr(getattr(channel, 'guild', None), 'id', None) != config['guild_id']:
                    raise ValueError('Wrong Stories guild')
                success, report = await self.publish(channel, config['guild_id'], lambda: self.authorized(config))
                if not success:
                    # Publisher reports are composed from fixed messages/codes,
                    # never raw upstream exceptions or response content.
                    log.warning('Stories publication failed: %s', report)
                    raise RuntimeError('Stories sync unavailable')
                if self.failures:
                    log.info('Stories sync recovered')
                self.failures = 0
                return True
            except Exception as error:
                self.failures += 1
                self.retry_at = self.clock() + min(3600, 300 * 2 ** min(self.failures - 1, 4))
                log.warning('Stories sync unavailable; category=%s; retry_in_seconds=%s', type(error).__name__, int(self.retry_at - self.clock()))
                return False

    @tasks.loop(seconds=300)
    async def poll(self):
        await self.refresh()

    @poll.before_loop
    async def wait_ready(self):
        await self.bot.wait_until_ready()
