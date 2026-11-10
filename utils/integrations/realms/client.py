"""Read-only, selected-Realm API surface. No join, acceptance or write helpers."""
import asyncio
import random

from .errors import AccessDenied, HTTPFailure, ProtocolError
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
        stories_path = "/api/v1.0/worlds/" + (self.config.selected_realm_id or "") + "/stories/playeractivity"
        if self.config.selected_realm_id:
            allowed.add(stories_path)
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
            if path == stories_path:
                headers["Cache-Control"] = "no-cache, no-store"
            frontend = path == stories_path or path.startswith("/api/v1.0/telemetry/")
            response = await self.transport.request("GET", (STORIES_HOST if frontend else REALMS_HOST) + path,
                                                    headers=headers)
            if response.status == 200:
                return response.body
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
