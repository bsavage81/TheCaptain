"""Synthetic protocol fixtures shared by offline Realms tests."""
from datetime import datetime, timezone

from utils.integrations.realms.configuration import Principal, RealmsConfig
from utils.integrations.realms.models import Identity, Secret, StoredAccount
from utils.integrations.realms.transport import Response

PRINCIPAL = Principal(101, 202)


def config(**changes):
    values = dict(enabled=True, client_id="12345678-1234-1234-1234-123456789abc",
                  auth_owner_ids=(101,), guild_id=202, account_ref="synthetic-account",
                  expected_gamertag="Synthetic Player", client_version="1.99.1", selected_realm_id="42")
    values.update(changes)
    return RealmsConfig(**values)


class FakeTime:
    def __init__(self):
        self.value = 2000000000.0
        self.delays = []

    def __call__(self):
        return self.value

    async def sleep(self, delay):
        self.delays.append(delay)
        self.value += delay


class FakeHTTP:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    async def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        assert self.responses, "Unexpected extra HTTP request"
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class MemoryStore:
    def __init__(self, account=None):
        self.account = account
        self.saved = []

    def load(self):
        return self.account

    def save(self, account):
        self.saved.append(account)
        self.account = account


def account(**changes):
    values = dict(refresh=Secret("canary-refresh-old"), identity=Identity("123456", "Synthetic Player"))
    values.update(changes)
    return StoredAccount(**values)


def oauth(**changes):
    values = dict(token_type="Bearer", access_token="canary-access", refresh_token="canary-refresh-new",
                  scope="XboxLive.signin offline_access", expires_in=3600)
    values.update(changes)
    return Response(200, values)


def xbox(clock, **changes):
    claim = dict(uhs="synthetic-hash", xid="123456", gtg="Synthetic Player")
    claim.update(changes.pop("claim", {}))
    values = dict(Token="canary-xbox", NotAfter=datetime.fromtimestamp(clock() + 7200, timezone.utc).isoformat(),
                  DisplayClaims={"xui": [claim]})
    values.update(changes)
    return Response(200, values)


def device(**changes):
    values = dict(device_code="canary-device", user_code="CANARY-CODE", verification_uri="https://microsoft.com/devicelogin",
                  expires_in=900, interval=5)
    values.update(changes)
    return Response(200, values)
