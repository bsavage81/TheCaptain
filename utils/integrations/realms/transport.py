"""Bounded, fixed-host aiohttp boundary. No raw upstream error escapes."""
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
import math
import re

import aiohttp

from .errors import AccessDenied, HTTPFailure, ProtocolError, TransportError

AUTHORITY = "https://login.microsoftonline.com/consumers/oauth2/v2.0"
USER_AUTH = "https://user.auth.xboxlive.com/user/authenticate"
XSTS_AUTH = "https://xsts.auth.xboxlive.com/xsts/authorize"
REALMS_HOST = "https://pocket.realms.minecraft.net"
STORIES_HOST = "https://frontend.realms.minecraft-services.net"
REALMS_RP = REALMS_HOST + "/"
XBOX_RP = "http://xboxlive.com"
PROFILE_BATCH = "https://profile.xboxlive.com/users/batch/profile/settings"
AUTH_URLS = {AUTHORITY + "/devicecode", AUTHORITY + "/token", USER_AUTH, XSTS_AUTH}
MAX_RESPONSE_BYTES = 1024 * 1024


def retry_delay(value, now=None):
    if not isinstance(value, str):
        return None
    try:
        delay = float(value)
        if not math.isfinite(delay):
            return None
    except ValueError:
        try:
            delay = (parsedate_to_datetime(value) - (now or datetime.now(timezone.utc))).total_seconds()
        except (ValueError, TypeError, OverflowError):
            return None
    return max(0.0, delay)


@dataclass(frozen=True)
class Response:
    status: int
    body: object = field(repr=False)
    retry_after: float | None = None


class AiohttpTransport:
    """Only the service owns this session. No proxy env, cookies, tracing or redirects."""
    def __init__(self, *, selected_realm_id=None, session_factory=aiohttp.ClientSession):
        self._factory = session_factory
        self._session = None
        self._semaphore = asyncio.Semaphore(2)
        self._stories_feed = None
        self._story_probe_reads = frozenset()
        self._club_feed_base = None
        self._reads = {REALMS_HOST + p for p in ("/worlds", "/activities/live/players", "/invites/pending", "/invites/count/pending")}
        if selected_realm_id is not None:
            if not isinstance(selected_realm_id, str) or not re.fullmatch(r"[1-9][0-9]{0,19}", selected_realm_id):
                raise AccessDenied()
            self._reads.add(REALMS_HOST + "/worlds/" + selected_realm_id)
            self._reads.add(STORIES_HOST + "/api/v1.0/worlds/" + selected_realm_id + "/stories/playeractivity")
            self._stories_feed = STORIES_HOST + "/api/v1.0/worlds/" + selected_realm_id + "/stories"
            self._reads.add(self._stories_feed)
            from .metrics import live_path
            self._reads.add(STORIES_HOST + live_path(selected_realm_id))

    async def __aenter__(self):
        self._session = self._factory(
            timeout=aiohttp.ClientTimeout(total=30, connect=10, sock_read=20),
            cookie_jar=aiohttp.DummyCookieJar(), trust_env=False,
        )
        return self

    async def __aexit__(self, *args):
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def request(self, method, url, *, headers=None, form=None, payload=None):
        if method == "POST" and url == PROFILE_BATCH:
            from .profiles import valid_xuid
            if (form is not None or not isinstance(payload, dict) or set(payload) != {"userIds", "settings"}
                    or payload["settings"] != ["Gamertag"] or not isinstance(payload["userIds"], list)
                    or not 1 <= len(payload["userIds"]) <= 100 or not all(valid_xuid(x) for x in payload["userIds"])
                    or len(set(payload["userIds"])) != len(payload["userIds"])):
                raise AccessDenied()
        if not ((method == "POST" and url in AUTH_URLS) or
                (method == "POST" and url == PROFILE_BATCH) or
                (method == "GET" and (url in self._reads or url in self._story_probe_reads))):
            raise AccessDenied()
        if url == self._stories_feed:
            self._story_probe_reads = frozenset()
        service = ('realm_stories' if url == self._stories_feed else
                   'xbox_stories' if url in self._story_probe_reads else
                   'authentication' if url in AUTH_URLS else
                   'profiles' if url == PROFILE_BATCH else 'realms')
        if self._session is None:
            raise TransportError('session_unavailable', service)
        failed = None
        result = None
        try:
            async with self._semaphore:
                async with self._session.request(method, url, headers=headers, data=form, json=payload,
                                                 allow_redirects=False) as response:
                    # The diagnostic needs the status even for non-JSON errors.
                    # Never read, report, or follow error/redirect content for this feed.
                    if (url == self._stories_feed or url in self._story_probe_reads) and response.status != 200:
                        return Response(response.status, None, retry_delay(response.headers.get("Retry-After")))
                    if 300 <= response.status < 400:
                        raise ProtocolError()
                    raw = bytearray()
                    async for chunk in response.content.iter_chunked(65536):
                        raw.extend(chunk)
                        if len(raw) > MAX_RESPONSE_BYTES:
                            raise ProtocolError()
                    malformed = False
                    try:
                        body = json.loads(raw)
                    except (ValueError, UnicodeError):
                        malformed = True
                    if malformed:
                        if url == self._stories_feed or url in self._story_probe_reads:
                            raise HTTPFailure(response.status)
                        raise ProtocolError()
                    if url == self._stories_feed:
                        from .stories_probe import probe_urls
                        routes = probe_urls(body)
                        self._story_probe_reads = frozenset(routes or ())
                        self._club_feed_base = routes[1] if routes else None
                    elif url in self._story_probe_reads and self._club_feed_base is not None and url.startswith(self._club_feed_base):
                        from .stories_probe import next_club_page
                        next_url = next_club_page(self._club_feed_base, body)
                        # Only the immediately returned cursor is authorized.
                        self._story_probe_reads = frozenset(
                            route for route in self._story_probe_reads
                            if not route.startswith(self._club_feed_base))
                        if next_url:
                            self._story_probe_reads |= frozenset({next_url})
                    result = Response(response.status, body, retry_delay(response.headers.get("Retry-After")))
        except (aiohttp.ClientSSLError, aiohttp.ClientConnectorCertificateError):
            failed = 'tls'
        except TimeoutError:
            failed = 'timeout'
        except (aiohttp.ClientError, OSError):
            failed = 'connection'
        except ValueError:
            failed = 'invalid_request'
        # Raise outside except: raw errors can contain request headers or body fragments.
        if failed:
            raise TransportError(failed, service)
        return result
