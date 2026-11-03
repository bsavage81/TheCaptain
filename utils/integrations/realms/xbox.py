"""Xbox user and XSTS exchanges, with no Minecraft game-session login."""
from datetime import datetime
import time

from .errors import AccessDenied, HTTPFailure, ProtocolError
from .models import Secret, XboxToken, text
from .transport import REALMS_RP, USER_AUTH, XBOX_RP, XSTS_AUTH


class XboxAuth:
    def __init__(self, transport, *, clock=time.time):
        self.transport = transport
        self.clock = clock

    def parse(self, response, audience):
        if response.status != 200:
            raise HTTPFailure(response.status, response.retry_after)
        data = response.body
        invalid = False
        try:
            claims = data["DisplayClaims"]["xui"]
            if not isinstance(claims, list) or len(claims) != 1 or not isinstance(claims[0], dict):
                raise ValueError()
            claim = claims[0]
            expiry = datetime.fromisoformat(data["NotAfter"].replace("Z", "+00:00"))
            if expiry.tzinfo is None or expiry.timestamp() <= self.clock() + 60:
                raise ValueError()
            token = XboxToken(Secret(text(data["Token"])), Secret(text(claim["uhs"])),
                              expiry.timestamp(), audience, claim.get("xid"), claim.get("gtg"))
        except (KeyError, TypeError, ValueError, AttributeError):
            invalid = True
        if invalid:
            raise ProtocolError()
        return token

    async def user_token(self, oauth):
        if oauth.expires_at <= self.clock() + 60:
            raise ProtocolError()
        response = await self.transport.request("POST", USER_AUTH,
            headers={"x-xbl-contract-version": "1", "Accept": "application/json"}, payload={
                "RelyingParty": "http://auth.xboxlive.com", "TokenType": "JWT",
                "Properties": {"AuthMethod": "RPS", "SiteName": "user.auth.xboxlive.com",
                               "RpsTicket": "d=" + oauth.access.value},
            })
        return self.parse(response, "http://auth.xboxlive.com")

    async def authorize(self, user_token, audience):
        if audience not in {REALMS_RP, XBOX_RP}:
            raise AccessDenied()
        if user_token.expires_at <= self.clock() + 60:
            raise ProtocolError()
        response = await self.transport.request("POST", XSTS_AUTH,
            headers={"x-xbl-contract-version": "1", "Accept": "application/json"}, payload={
                "RelyingParty": audience, "TokenType": "JWT",
                "Properties": {"UserTokens": [user_token.token.value], "SandboxId": "RETAIL"},
            })
        token = self.parse(response, audience)
        if token.user_hash != user_token.user_hash:
            raise ProtocolError()
        return token
