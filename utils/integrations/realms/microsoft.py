"""Passwordless public-client device authorization with bounded polling."""
import asyncio
import time
from urllib.parse import urlsplit

from .errors import HTTPFailure, LoginDenied, LoginExpired, ProtocolError, ReauthRequired
from .models import DeviceChallenge, OAuthTokens, Secret, seconds, text
from .transport import AUTHORITY

SCOPES = "XboxLive.signin offline_access"


class MicrosoftAuth:
    def __init__(self, transport, client_id, *, clock=time.time, monotonic=time.monotonic, sleep=asyncio.sleep):
        self.transport = transport
        self.client_id = client_id
        self.clock = clock
        self.monotonic = monotonic
        self.sleep = sleep

    async def begin_device_login(self):
        response = await self.transport.request("POST", AUTHORITY + "/devicecode", form={
            "client_id": self.client_id, "scope": SCOPES,
        })
        if response.status != 200:
            raise HTTPFailure(response.status, response.retry_after)
        data = response.body
        if not isinstance(data, dict):
            raise ProtocolError()
        uri = text(data.get("verification_uri"))
        invalid_uri = False
        try:
            parsed = urlsplit(uri)
        except ValueError:
            invalid_uri = True
        if invalid_uri:
            raise ProtocolError()
        if parsed.scheme != "https" or parsed.netloc not in {"microsoft.com", "www.microsoft.com", "login.microsoftonline.com"} or parsed.query or parsed.fragment or parsed.path not in {"/devicelogin", "/link", "/common/oauth2/deviceauth"}:
            raise ProtocolError()
        return DeviceChallenge(Secret(text(data.get("device_code"))), Secret(text(data.get("user_code"))),
                               uri, self.monotonic() + seconds(data.get("expires_in"), 1800),
                               seconds(data.get("interval", 5), 60))

    def parse_tokens(self, data, previous_refresh=None):
        if not isinstance(data, dict) or str(data.get("token_type", "")).lower() != "bearer":
            raise ProtocolError()
        scope = data.get("scope")
        if not isinstance(scope, str) or "xboxlive.signin" not in scope.lower().split():
            raise ProtocolError()
        refresh = data.get("refresh_token", previous_refresh)
        return OAuthTokens(Secret(text(data.get("access_token"))), Secret(text(refresh)),
                           self.clock() + seconds(data.get("expires_in")))

    async def poll_device_login(self, challenge):
        interval = challenge.interval
        while True:
            remaining = challenge.expires_at - self.monotonic()
            if remaining <= interval:
                raise LoginExpired()
            await self.sleep(interval)
            if self.monotonic() >= challenge.expires_at:
                raise LoginExpired()
            response = await self.transport.request("POST", AUTHORITY + "/token", form={
                "client_id": self.client_id,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "device_code": challenge.device_code.value,
            })
            if self.monotonic() >= challenge.expires_at:
                raise LoginExpired()
            if response.status == 200:
                return self.parse_tokens(response.body)
            error = response.body.get("error") if isinstance(response.body, dict) else None
            if response.status == 429:
                interval = max(interval + 5, response.retry_after or 0)
            elif response.status == 400 and error == "authorization_pending":
                continue
            elif response.status == 400 and error == "slow_down":
                interval += 5
            elif error in {"authorization_declined", "access_denied"}:
                raise LoginDenied()
            elif error in {"expired_token", "code_expired"}:
                raise LoginExpired()
            else:
                raise HTTPFailure(response.status, response.retry_after)

    async def refresh(self, refresh):
        response = await self.transport.request("POST", AUTHORITY + "/token", form={
            "client_id": self.client_id, "grant_type": "refresh_token",
            "scope": SCOPES, "refresh_token": refresh.value,
        })
        error = response.body.get("error") if isinstance(response.body, dict) else None
        if response.status == 400 and error == "invalid_grant":
            raise ReauthRequired()
        if response.status != 200:
            raise HTTPFailure(response.status, response.retry_after)
        return self.parse_tokens(response.body, refresh.value)
