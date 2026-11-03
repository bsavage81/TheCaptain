"""Bounded encrypted Xbox name cache; driven by observations, never a new task."""
import asyncio
from dataclasses import replace
import logging
import math
import time

from utils.integrations.realms.errors import HTTPFailure
from utils.integrations.realms.models import Snapshot
from utils.integrations.realms.profiles import valid_xuid, valid_gamertag

log = logging.getLogger(__name__)


class GamertagCache:
    positive_ttl = 86400
    negative_ttl = 900
    lookup_interval = 60
    max_entries = 100

    def __init__(self, client, store, *, clock=time.time):
        self.client, self.store, self.clock = client, store, clock
        self.entries = {}
        self.next_lookup = 0
        self.failures = 0
        self.loaded = False

    async def _io(self, method, *args):
        task = asyncio.create_task(asyncio.to_thread(method, *args))
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            await task
            raise

    def _restore(self, data):
        if data is None:
            return
        if not isinstance(data, dict) or set(data) != {"entries", "next_lookup"}:
            raise ValueError()
        entries, next_lookup = data["entries"], data["next_lookup"]
        if not isinstance(entries, dict) or len(entries) > self.max_entries or not self._timestamp(next_lookup):
            raise ValueError()
        for xuid, record in entries.items():
            if (not valid_xuid(xuid) or not isinstance(record, dict) or set(record) != {"name", "expires"}
                    or not self._timestamp(record["expires"])
                    or record["name"] is not None and not valid_gamertag(record["name"])):
                raise ValueError()
        self.entries = entries
        self.next_lookup = next_lookup

    @staticmethod
    def _timestamp(value):
        return type(value) in (float, int) and math.isfinite(value) and value >= 0

    def _apply(self, snapshot):
        now = self.clock()
        players = []
        for player in snapshot.data.players:
            record = self.entries.get(player.xuid)
            name = record["name"] if record and record["expires"] > now else None
            players.append(replace(player, name=player.name or name))
        return Snapshot(replace(snapshot.data, players=tuple(players)), snapshot.observed_at)

    async def enrich(self, snapshot):
        now = self.clock()
        if not self.loaded:
            if now < self.next_lookup:
                return snapshot
            try:
                self._restore(await self._io(self.store.load_gamertags))
                self.loaded = True
            except Exception:
                self.next_lookup = now + 900
                log.warning("Xbox gamertag cache unavailable")
                return snapshot
        wanted = sorted({p.xuid for p in snapshot.data.players
                         if p.online is True and not p.name and valid_xuid(p.xuid)
                         and (p.xuid not in self.entries or self.entries[p.xuid]["expires"] <= now)})[:100]
        if wanted and now >= self.next_lookup:
            self.next_lookup = now + self.lookup_interval
            try:
                async with asyncio.timeout(8):
                    names = await self.client.gamertags(wanted)
                self.failures = 0
                self.entries = {x: r for x, r in self.entries.items() if r["expires"] > now}
                for xuid in wanted:
                    name = names.get(xuid)
                    self.entries[xuid] = dict(name=name, expires=now + (self.positive_ttl if name else self.negative_ttl))
                if len(self.entries) > self.max_entries:
                    keep = sorted(self.entries, key=lambda x: self.entries[x]["expires"], reverse=True)[:self.max_entries]
                    self.entries = {x: self.entries[x] for x in keep}
            except Exception as error:
                self.failures += 1
                delay = min(3600, 60 * 2 ** min(self.failures - 1, 6))
                if isinstance(error, HTTPFailure) and error.retry_after is not None:
                    delay = max(delay, error.retry_after)
                self.next_lookup = self.clock() + delay
                log.warning("Xbox gamertag lookup unavailable; backing off")
            try:
                await self._io(self.store.save_gamertags, dict(entries=self.entries, next_lookup=self.next_lookup))
            except Exception:
                self.next_lookup = max(self.next_lookup, self.clock() + 900)
                log.warning("Xbox gamertag cache persistence unavailable")
        return self._apply(snapshot)
