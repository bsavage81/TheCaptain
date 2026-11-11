"""Shared serialized observations using the Phase 2 service; no interactive login."""
import asyncio
from contextlib import AsyncExitStack
from dataclasses import dataclass, replace
import json
import logging
import math
import os
import time

from utils.integrations.realms.configuration import Principal, from_bot_settings
from utils.integrations.realms.errors import ConfigurationError, HTTPFailure
from utils.integrations.realms.models import Secret
from utils.integrations.realms.service import RealmsService
from utils.integrations.realms.token_store import EncryptedTokenStore
from utils.integrations.realms.transport import AiohttpTransport

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Observation:
    realm: object = None
    activity: object = None
    realm_available: bool = False
    activity_available: bool = False


def host_store(config, environ):
    invalid = False
    try:
        keys = json.loads(environ.get("CAPTAIN_REALMS_KEYS", ""))
        directory = environ["CAPTAIN_REALMS_STORE_DIR"]
        active = environ["CAPTAIN_REALMS_KEY_ID"]
        if not directory or not isinstance(keys, dict) or not keys or not all(isinstance(v, str) for v in keys.values()):
            raise ValueError()
        store = EncryptedTokenStore(directory, config.binding, {k: Secret(v) for k, v in keys.items()}, active)
    except (KeyError, TypeError, ValueError):
        invalid = True
    if invalid:
        raise ConfigurationError()
    return store


class RealmRuntime:
    cache_seconds = 60
    refresh_seconds = 30

    def __init__(self, settings, *, environ=None, store_factory=host_store,
                 transport_factory=AiohttpTransport, service_factory=RealmsService, monotonic=time.monotonic):
        self.config = from_bot_settings(settings)
        self._environ = environ
        self._store_factory = store_factory
        self._transport_factory = transport_factory
        self._service_factory = service_factory
        self._clock = monotonic
        self._stack = AsyncExitStack()
        self._lock = asyncio.Lock()
        self._tasks = set()
        self._last_attempt = None
        self._retry_at = 0
        self.view = Observation()
        self.client = None
        self.store = None
        self.names = None
        self._failures = 0
        self._closed = False
        self._history_enabled = settings.get("realm_history_enabled", False) is True
        self._history_retry_at = 0
        self._history_failures = 0
        self._history_snapshot = None
        self._metrics_snapshot = None
        self._metrics_retry_at = 0
        self._metrics_available = False
        self._metrics_failures = 0

    async def start(self):
        if not self.config.enabled or self.client is not None or self._closed:
            return
        try:
            store = self._store_factory(self.config, os.environ if self._environ is None else self._environ)
            task = asyncio.create_task(asyncio.to_thread(store.open))
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                try:
                    await task
                finally:
                    await asyncio.to_thread(store.close)
                raise
            self._stack.push_async_callback(asyncio.to_thread, store.close)
            self.store = store
            transport = await self._stack.enter_async_context(self._transport_factory(selected_realm_id=self.config.selected_realm_id))
            service = self._service_factory(self.config, transport, store)
            self._stack.push_async_callback(service.close)
            # Internal delegated service identity; OP Team users are never granted auth ownership.
            principal = Principal(self.config.auth_owner_ids[0], self.config.guild_id)
            self.client = service.client(principal)
            if hasattr(service, "profile_client"):
                from .names import GamertagCache
                self.names = GamertagCache(service.profile_client(principal), store)
        except asyncio.CancelledError:
            await self._stack.aclose()
            raise
        except Exception as error:
            log.warning("Realms initialization unavailable (%s)", type(error).__name__)
            await self._stack.aclose()
            self.client = None

    async def observe(self, *, force=False, scheduled=False):
        if self._closed or self.client is None:
            return self.view, 0
        task = asyncio.current_task()
        self._tasks.add(task)
        try:
            async with self._lock:
                if self._closed:
                    return self.view, 0
                if self._retry_at > self._clock():
                    return self.view, math.ceil(self._retry_at - self._clock())
                age = float("inf") if self._last_attempt is None else self._clock() - self._last_attempt
                if scheduled and age < 15:
                    return self.view, 0
                if force and not scheduled and age < self.refresh_seconds:
                    return self.view, math.ceil(self.refresh_seconds - age)
                if not force and not scheduled and age < self.cache_seconds:
                    return self.view, 0
                self._last_attempt = self._clock()
                realm, activity = self.view.realm, self.view.activity
                realm_ok = activity_ok = False
                try:
                    async with asyncio.timeout(45):
                        try:
                            realm = await self.client.realm()
                            realm_ok = True
                        except Exception as error:
                            log.warning("Realms details unavailable (%s)", type(error).__name__)
                            self._backoff(error)
                        if self._retry_at <= self._clock():
                            try:
                                snapshot = await self.client.activities()
                                selected = next((a for a in snapshot.data if a.realm_id == self.config.selected_realm_id), None)
                                if selected is not None:
                                    from utils.integrations.realms.models import Snapshot
                                    activity = Snapshot(selected, snapshot.observed_at)
                                    activity_ok = True
                            except Exception as error:
                                log.warning("Realms activity unavailable (%s)", type(error).__name__)
                                self._backoff(error)
                except TimeoutError:
                    log.warning("Realms observation timed out")
                    self._backoff(TimeoutError())
                if realm_ok and activity_ok:
                    self._failures = 0
                if activity_ok and self.names is not None:
                    activity = await self.names.enrich(activity)
                self.view = Observation(realm, activity, realm_ok, activity_ok)
                return self.view, math.ceil(max(0, self._retry_at - self._clock()))
        finally:
            self._tasks.discard(task)

    def _backoff(self, error):
        self._failures += 1
        delay = min(900, 15 * 2 ** min(self._failures - 1, 6))
        if isinstance(error, HTTPFailure) and error.retry_after is not None:
            delay = max(delay, error.retry_after)
        self._retry_at = max(self._retry_at, self._clock() + delay)

    async def metrics(self):
        """On-demand Pro polling; shares auth, serialization, and shutdown tracking."""
        if self._closed or self.client is None:
            return None, False
        task = asyncio.current_task()
        self._tasks.add(task)
        try:
            async with self._lock:
                if self._closed:
                    return self._metrics_snapshot, False
                if self._clock() < self._metrics_retry_at:
                    return self._metrics_snapshot, self._metrics_available
                self._metrics_retry_at = self._clock() + 15
                try:
                    async with asyncio.timeout(45):
                        self._metrics_snapshot = await self.client.metrics()
                    self._metrics_available = True
                    self._metrics_failures = 0
                    self._metrics_retry_at = self._clock() + 15
                except Exception as error:
                    self._metrics_available = False
                    self._metrics_failures += 1
                    delay = min(900, 30 * 2 ** min(self._metrics_failures - 1, 5))
                    if isinstance(error, HTTPFailure):
                        if error.status in {401, 403}:
                            delay = 3600
                        if error.retry_after is not None:
                            delay = max(delay, error.retry_after)
                    self._metrics_retry_at = self._clock() + delay
                    log.warning("Realm Pro metrics unavailable (%s)", type(error).__name__)
                return self._metrics_snapshot, self._metrics_available
        finally:
            self._tasks.discard(task)

    async def story_feed(self):
        """On-demand feed only; share lifecycle/lock without saving history."""
        from utils.integrations.realms.errors import AccessDenied
        if self._closed or self.client is None:
            raise AccessDenied()
        task = asyncio.current_task()
        self._tasks.add(task)
        try:
            async with self._lock:
                if self._closed:
                    raise AccessDenied()
                if self._retry_at > self._clock():
                    raise HTTPFailure(429, self._retry_at - self._clock())
                async with asyncio.timeout(45):
                    return await self.client.story_feed()
        finally:
            self._tasks.discard(task)

    async def club_story_feed(self, *, old_realm=False):
        """Read current Stories or all archived pages; no history writes or polling."""
        from utils.integrations.realms.errors import AccessDenied
        if self._closed or self.client is None:
            raise AccessDenied()
        task = asyncio.current_task()
        self._tasks.add(task)
        try:
            async with self._lock:
                if self._closed:
                    raise AccessDenied()
                if self._retry_at > self._clock():
                    raise HTTPFailure(429, self._retry_at - self._clock())
                async with asyncio.timeout(None if old_realm else 120):
                    if old_realm:
                        from utils.integrations.realms.client import RealmsClient
                        from utils.integrations.realms.errors import StoriesError
                        target_id = await self.client.old_stories_realm_id()
                        # Separate client and transport: never mutate the live target,
                        # its caches, or the transport's selected-Realm allowlist.
                        async with self._transport_factory(selected_realm_id=target_id) as transport:
                            archive = RealmsClient(transport, self.client.authorization,
                                                  replace(self.config, selected_realm_id=target_id),
                                                  self.client.principal)
                            try:
                                body = await archive.club_story_feed(all_pages=True)
                            except (StoriesError, HTTPFailure):
                                raise
                            except Exception:
                                raise StoriesError('archive_fetch') from None
                        body = dict(body, sourceRealmId=target_id)
                    else:
                        body = await self.client.club_story_feed(all_pages=True)
                    if self.names is not None:
                        # The existing name cache handles batching, TTLs and backoff.
                        events = body.get("realmEvents", [])
                        identities = {x for event in events if isinstance(event, dict)
                                      for x in (event.get("players") if isinstance(event.get("players"), list) else [])
                                      if isinstance(x, str)}
                        try:
                            resolved = {}
                            identities = sorted(identities)
                            for start in range(0, len(identities), 100):
                                resolved.update(await self.names.resolve(identities[start:start + 100]))
                            body = dict(body, playerNames=resolved)
                        except Exception:
                            log.warning("Stories participant names unavailable")
                    return body
        finally:
            self._tasks.discard(task)

    async def stories_debug(self):
        """Temporary on-demand feed probe; no history persistence or polling."""
        from utils.integrations.realms.errors import AccessDenied
        if self._closed or self.client is None:
            raise AccessDenied()
        task = asyncio.current_task()
        self._tasks.add(task)
        try:
            async with self._lock:
                if self._closed:
                    raise AccessDenied()
                if self._retry_at > self._clock():
                    raise HTTPFailure(429, self._retry_at - self._clock())
                async with asyncio.timeout(150):
                    return await self.client.stories_investigation()
        finally:
            self._tasks.discard(task)

    async def stories(self):
        """Explicit private history requests share auth/lock, never the panel loop."""
        from utils.integrations.realms.errors import AccessDenied
        if not self._history_enabled or self._closed or self.client is None:
            raise AccessDenied()
        task = asyncio.current_task()
        self._tasks.add(task)
        try:
            async with self._lock:
                if self._closed:
                    raise AccessDenied()
                if self._retry_at > self._clock():
                    raise HTTPFailure(429, self._retry_at - self._clock())
                if self._history_retry_at > self._clock():
                    if self._history_snapshot is not None:
                        return self._history_snapshot
                    raise HTTPFailure(429, self._history_retry_at - self._clock())
                # Gate before I/O; callers cannot hammer a failing service.
                self._history_retry_at = self._clock() + 3600
                try:
                    async with asyncio.timeout(45):
                        snapshot = await self.client.stories()
                except Exception as error:
                    self._history_failures += 1
                    delay = min(3600, 60 * 2 ** min(self._history_failures - 1, 6))
                    if isinstance(error, HTTPFailure) and error.retry_after is not None:
                        delay = max(delay, error.retry_after)
                    self._history_retry_at = self._clock() + delay
                    raise
                self._history_failures = 0
                self._history_snapshot = snapshot
                self._history_retry_at = self._clock() + 3600
                return snapshot
        finally:
            self._tasks.discard(task)

    async def close(self):
        self._closed = True
        tasks = [t for t in self._tasks if t is not asyncio.current_task()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        await self._stack.aclose()
        self.client = None
