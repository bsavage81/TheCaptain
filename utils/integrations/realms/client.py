"""Read-only, selected-Realm API surface. No join, acceptance or write helpers."""
import asyncio
import random

from .errors import AccessDenied, HTTPFailure, ProtocolError, StoriesError
from .models import Activity, Invitation, Realm, Snapshot, members, realm_id, text, utcnow
from .transport import REALMS_HOST, STORIES_HOST


class RealmsClient:
    def __init__(self, transport, authorization, config, principal, *, clock=utcnow,
                 sleep=asyncio.sleep, jitter=random.random):
        self.transport = transport
        self.authorization = authorization
        self.config = config
        self.principal = principal
        self.clock = clock
        self.sleep = sleep
        self.jitter = jitter

    async def request(self, method, path):
        self.config.authorize(self.principal)
        allowed = {"/worlds", "/activities/live/players", "/invites/pending", "/invites/count/pending"}
        if self.config.selected_realm_id:
            allowed.add("/worlds/" + self.config.selected_realm_id)
        feed_path = "/api/v1.0/worlds/" + (self.config.selected_realm_id or "") + "/stories"
        stories_path = "/api/v1.0/worlds/" + (self.config.selected_realm_id or "") + "/stories/playeractivity"
        if self.config.selected_realm_id:
            allowed.add(stories_path)
            allowed.add(feed_path)
            from .metrics import live_path
            allowed.add(live_path(self.config.selected_realm_id))
        if method != "GET" or path not in allowed:
            raise AccessDenied()
        token = await self.authorization(self.principal)
        renewed = False
        attempts = 0
        while True:
            self.config.authorize(self.principal)
            headers = {
                "Authorization": token.authorization.value, "Client-Version": self.config.client_version,
                "User-Agent": "MCPE/UWP", "Accept": "application/json",
            }
            if path in {stories_path, feed_path}:
                headers["Cache-Control"] = "no-cache, no-store"
            frontend = path in {stories_path, feed_path} or path.startswith("/api/v1.0/telemetry/")
            response = await self.transport.request("GET", (STORIES_HOST if frontend else REALMS_HOST) + path,
                                                    headers=headers)
            if response.status == 200:
                return response.body
            if path == feed_path:
                # Temporary probe: exactly one feed GET, including on 401/429.
                raise HTTPFailure(response.status, response.retry_after)
            if response.status == 401 and not renewed:
                token = await self.authorization(self.principal, rejected=token)
                renewed = True
                continue
            if response.status in {429, 502, 503, 504} and attempts < 2:
                delay = response.retry_after if response.retry_after is not None else 2 ** attempts + self.jitter()
                # Long Retry-After goes back to the operator; never retry sooner than requested.
                if delay > 30:
                    raise HTTPFailure(response.status, delay)
                await self.sleep(delay)
                attempts += 1
                continue
            raise HTTPFailure(response.status, response.retry_after)

    async def story_feed(self):
        """One selected-Realm feed GET, independent of player activity."""
        if not self.config.selected_realm_id:
            raise AccessDenied()
        return await self.request("GET", "/api/v1.0/worlds/" + self.config.selected_realm_id + "/stories")

    async def old_stories_realm_id(self):
        """Resolve the archive from names/IDs without parsing unrelated live state."""
        import re
        try:
            body = await self.request('GET', '/worlds')
        except HTTPFailure:
            raise
        except Exception:
            raise StoriesError('realm_list') from None
        if not isinstance(body, dict) or not isinstance(body.get('servers'), list):
            raise StoriesError('realm_list')
        matches = []
        for server in body['servers']:
            if not isinstance(server, dict) or not isinstance(server.get('name'), str):
                continue
            name = re.sub(r'\u00a7[0-9a-z]', '', server['name'], flags=re.IGNORECASE)
            if name.strip().casefold() == 'old coastal s10':
                try:
                    matches.append(realm_id(server.get('id')))
                except ProtocolError:
                    raise StoriesError('realm_list') from None
        if not matches:
            raise StoriesError('realm_missing')
        if len(matches) != 1:
            raise StoriesError('realm_ambiguous')
        return matches[0]

    async def club_story_feed(self, *, all_pages=False):
        """Read club Stories, optionally following every returned continuation token."""
        from .stories_probe import probe_urls
        from .transport import XBOX_RP
        try:
            realm_feed = await self.story_feed()
        except ProtocolError:
            raise StoriesError('realm_feed') from None
        urls = probe_urls(realm_feed)
        if urls is None:
            raise StoriesError('club_reference')
        from .stories_probe import next_club_page
        self.config.authorize(self.principal)
        token = await self.authorization(self.principal, audience=XBOX_RP)
        url, seen, items = urls[1], set(), []
        while url is not None:
            if url in seen:
                raise StoriesError('cursor_repeat')
            seen.add(url)
            self.config.authorize(self.principal)
            response = await self.transport.request("GET", url, headers={
                "Authorization": token.authorization.value,
                "x-xbl-contract-version": "13", "Accept": "application/json",
                "Accept-Language": "en-US", "Cache-Control": "no-cache, no-store",
            })
            if response.status != 200:
                raise HTTPFailure(response.status, response.retry_after)
            if not isinstance(response.body, dict) or not isinstance(response.body.get('activityItems'), list):
                raise StoriesError('club_page')
            if not all_pages:
                return dict(response.body, realmEvents=realm_feed["result"])
            items.extend(response.body['activityItems'])
            url = next_club_page(urls[1], response.body)
        return dict(activityItems=items, realmEvents=realm_feed["result"])

    async def stories_investigation(self):
        """One Realm feed read, then at most two derived Xbox GET probes."""
        from .stories_probe import investigate
        return await investigate(self)

    async def stories_debug(self):
        """One feed GET; return the complete response body for staff inspection."""
        import json
        body = await self.story_feed()
        serialized = json.dumps(body, ensure_ascii=True, indent=2)
        # Keep whitespace expansion below Discord attachment limits.
        if len(serialized) > 7 * 1024 * 1024:
            serialized = json.dumps(body, ensure_ascii=True, separators=(",", ":"))
        return "HTTP status: 200\n\n" + serialized

    async def metrics(self):
        from .metrics import Metrics, live_path
        if not self.config.selected_realm_id:
            raise AccessDenied()
        body = await self.request("GET", live_path(self.config.selected_realm_id))
        return Snapshot(Metrics.parse(body), self.clock())

    async def stories(self):
        """Selected-Realm observed history; never claims exact connection semantics."""
        if not self.config.selected_realm_id:
            raise AccessDenied()
        from .stories import parse_stories
        data = await self.request("GET", "/api/v1.0/worlds/" + self.config.selected_realm_id + "/stories/playeractivity")
        observed = self.clock()
        return Snapshot(parse_stories(data, observed), observed)

    async def list_realms(self):
        data = await self.request("GET", "/worlds")
        if not isinstance(data, dict) or not isinstance(data.get("servers"), list):
            raise ProtocolError()
        result = tuple(Realm.parse(item) for item in data["servers"])
        if len({r.id for r in result}) != len(result):
            raise ProtocolError()
        return Snapshot(result, self.clock())

    async def realm(self):
        if not self.config.selected_realm_id:
            raise AccessDenied()
        result = Realm.parse(await self.request("GET", "/worlds/" + self.config.selected_realm_id))
        if result.id != self.config.selected_realm_id:
            raise ProtocolError()
        return Snapshot(result, self.clock())

    async def activities(self):
        data = await self.request("GET", "/activities/live/players")
        if not isinstance(data, dict) or not isinstance(data.get("servers"), list):
            raise ProtocolError()
        result = []
        for server in data["servers"]:
            if not isinstance(server, dict):
                raise ProtocolError()
            players = members(server.get("players"))
            if players is None:
                raise ProtocolError()
            result.append(Activity(realm_id(server.get("id")), players))
        if len({a.realm_id for a in result}) != len(result):
            raise ProtocolError()
        return Snapshot(tuple(result), self.clock())

    async def pending_invites(self):
        data = await self.request("GET", "/invites/pending")
        if not isinstance(data, dict) or not isinstance(data.get("invites"), list):
            raise ProtocolError()
        result = []
        for item in data["invites"]:
            if not isinstance(item, dict):
                raise ProtocolError()
            result.append(Invitation(text(item.get("invitationId")), text(item.get("worldName"))))
        return Snapshot(tuple(result), self.clock())

    async def pending_invite_count(self):
        data = await self.request("GET", "/invites/count/pending")
        if type(data) is not int or data < 0:
            raise ProtocolError()
        return Snapshot(data, self.clock())
