"""Fixed, read-only Xbox batch gamertag lookup. No generic profile API surface."""
from .errors import AccessDenied, HTTPFailure, ProtocolError
from .transport import PROFILE_BATCH, XBOX_RP


def valid_xuid(value):
    return (isinstance(value, str) and value.isascii() and value.isdigit()
            and 0 < len(value) <= 20 and str(int(value)) == value and 0 < int(value) < 2**64)


def valid_gamertag(value):
    return (isinstance(value, str) and bool(value.strip()) and len(value) <= 64
            and not any(ord(c) < 32 or ord(c) == 127 for c in value))


class ProfileClient:
    def __init__(self, transport, authorization, config, principal):
        self.transport, self.authorization = transport, authorization
        self.config, self.principal = config, principal

    async def gamertags(self, xuids):
        self.config.authorize(self.principal)
        if not isinstance(xuids, (list, tuple)) or not 1 <= len(xuids) <= 100 or not all(valid_xuid(x) for x in xuids) or len(set(xuids)) != len(xuids):
            raise AccessDenied()
        token = await self.authorization(self.principal, audience=XBOX_RP)
        for attempt in range(2):
            self.config.authorize(self.principal)
            response = await self.transport.request("POST", PROFILE_BATCH, headers={
                "Authorization": token.authorization.value, "x-xbl-contract-version": "2",
                "Content-Type": "application/json", "Accept": "application/json",
            }, payload={"userIds": list(xuids), "settings": ["Gamertag"]})
            if response.status == 401 and attempt == 0:
                token = await self.authorization(self.principal, audience=XBOX_RP, rejected=token)
                continue
            if response.status != 200:
                raise HTTPFailure(response.status, response.retry_after)
            body = response.body
            if not isinstance(body, dict) or not isinstance(body.get("profileUsers"), list):
                raise ProtocolError()
            result, seen = {}, set()
            for profile in body["profileUsers"]:
                if not isinstance(profile, dict):
                    raise ProtocolError()
                xuid = profile.get("id")
                if not valid_xuid(xuid) or xuid not in xuids or xuid in seen or not isinstance(profile.get("settings"), list):
                    raise ProtocolError()
                seen.add(xuid)
                settings = profile["settings"]
                if any(not isinstance(s, dict) or s.get("id") != "Gamertag" for s in settings) or len(settings) > 1:
                    raise ProtocolError()
                if settings and settings[0].get("value") is not None:
                    name = settings[0]["value"]
                    if not valid_gamertag(name):
                        raise ProtocolError()
                    result[xuid] = name
            return result
