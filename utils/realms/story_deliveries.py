"""Encrypted Story-to-message checkpoints; no Discord or Realm content stored."""
import asyncio
import hashlib
import json

from utils.integrations.realms.errors import StorageError


class StoryDeliveries:
    def __init__(self, store):
        self.store = store
        self.entries = None

    @staticmethod
    def key(guild, channel, source, identity):
        return hashlib.sha256(json.dumps([guild, channel, source, identity]).encode()).hexdigest()

    async def load(self):
        if self.entries is not None:
            return
        data = await asyncio.to_thread(self.store.load_story_deliveries) if self.store is not None else None
        data = {} if data is None else data
        if not isinstance(data, dict):
            raise StorageError()
        for key, value in data.items():
            if (not isinstance(key, str) or len(key) != 64 or not isinstance(value, dict)
                    or type(value.get('message_id')) is not int or value['message_id'] <= 0
                    or not isinstance(value.get('footer'), str) or len(value['footer']) > 2048):
                raise StorageError()
        self.entries = data

    async def save(self, key, message_id, footer):
        self.entries[key] = {'message_id': message_id, 'footer': footer}
        if self.store is not None:
            task = asyncio.create_task(asyncio.to_thread(self.store.save_story_deliveries, dict(self.entries)))
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                await task
                raise
