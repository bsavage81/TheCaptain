import asyncio
from dataclasses import replace

import pytest

from realms_fakes import FakeHTTP, FakeTime, config, device, oauth, xbox
from utils.integrations.realms.errors import AccessDenied, HTTPFailure, LoginDenied, LoginExpired, ProtocolError, ReauthRequired
from utils.integrations.realms.microsoft import MicrosoftAuth, SCOPES
from utils.integrations.realms.models import Secret
from utils.integrations.realms.transport import AUTHORITY, REALMS_RP, Response, USER_AUTH, XBOX_RP
from utils.integrations.realms.xbox import XboxAuth


def auth(http, clock):
    return MicrosoftAuth(http, config().client_id, clock=clock, monotonic=clock, sleep=clock.sleep)


async def test_device_pending_slowdown_and_payloads():
    clock = FakeTime()
    http = FakeHTTP(device(), Response(400, {"error": "authorization_pending"}),
                    Response(400, {"error": "slow_down"}), Response(429, {}, 20), oauth())
    msa = auth(http, clock)
    challenge = await msa.begin_device_login()
    tokens = await msa.poll_device_login(challenge)
    assert clock.delays == [5, 5, 10, 20]
    assert http.calls[0][2]["form"] == {"client_id": config().client_id, "scope": SCOPES}
    assert http.calls[1][2]["form"]["device_code"] == "canary-device"
    assert http.calls[1][1] == AUTHORITY + "/token"
    assert tokens.refresh.value == "canary-refresh-new"
    assert "canary" not in repr(tokens) + repr(challenge)


@pytest.mark.parametrize("error,kind", [("authorization_declined", LoginDenied), ("access_denied", LoginDenied),
    ("expired_token", LoginExpired), ("bad_verification_code", HTTPFailure), ("invalid_client", HTTPFailure)])
async def test_device_terminal_errors(error, kind):
    clock = FakeTime()
    http = FakeHTTP(device(), Response(400, {"error": error, "error_description": "canary-secret"}))
    msa = auth(http, clock)
    challenge = await msa.begin_device_login()
    with pytest.raises(kind) as raised:
        await msa.poll_device_login(challenge)
    assert "canary" not in str(raised.value)
    assert len(http.calls) == 2


@pytest.mark.parametrize("change", [dict(verification_uri="http://microsoft.com/link"),
    dict(verification_uri="https://microsoft.com.evil/link"), dict(verification_uri="https://microsoft.com/link?code=secret"),
    dict(expires_in=-1), dict(interval=0), dict(expires_in=float("nan")), dict(device_code="bad\nvalue")])
async def test_device_rejects_bad_response(change):
    with pytest.raises(ProtocolError):
        await auth(FakeHTTP(device(**change)), FakeTime()).begin_device_login()


async def test_expiration_before_request_and_cancellation():
    clock = FakeTime()
    http = FakeHTTP(device(expires_in=5))
    msa = auth(http, clock)
    with pytest.raises(LoginExpired):
        await msa.poll_device_login(await msa.begin_device_login())
    assert len(http.calls) == 1
    clock = FakeTime()
    msa = auth(FakeHTTP(device()), clock)
    challenge = await msa.begin_device_login()
    entered = asyncio.Event()
    async def blocked_sleep(delay):
        entered.set()
        await asyncio.Event().wait()
    msa.sleep = blocked_sleep
    task = asyncio.create_task(msa.poll_device_login(challenge))
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert len(msa.transport.calls) == 1


async def test_refresh_rotation_missing_optional_refresh_and_revocation():
    clock = FakeTime()
    data = oauth().body.copy()
    del data["refresh_token"]
    http = FakeHTTP(oauth(), Response(200, data), Response(400, {"error": "invalid_grant"}))
    msa = auth(http, clock)
    first = await msa.refresh(Secret("canary-old"))
    second = await msa.refresh(first.refresh)
    assert second.refresh == first.refresh
    assert http.calls[0][2]["form"]["grant_type"] == "refresh_token"
    with pytest.raises(ReauthRequired):
        await msa.refresh(second.refresh)


@pytest.mark.parametrize("change", [dict(refresh_token=None), dict(access_token=""), dict(token_type="MAC"),
    dict(scope="User.Read"), dict(expires_in=True), dict(expires_in="3600")])
def test_invalid_oauth_tokens(change):
    with pytest.raises(ProtocolError):
        auth(FakeHTTP(), FakeTime()).parse_tokens(oauth(**change).body)


async def test_xbox_exact_chain_and_audience():
    clock = FakeTime()
    http = FakeHTTP(xbox(clock), xbox(clock))
    msa_tokens = auth(FakeHTTP(), clock).parse_tokens(oauth().body)
    api = XboxAuth(http, clock=clock)
    user = await api.user_token(msa_tokens)
    result = await api.authorize(user, REALMS_RP)
    assert http.calls[0][1] == USER_AUTH
    assert http.calls[0][2]["payload"]["Properties"]["RpsTicket"] == "d=canary-access"
    assert http.calls[1][2]["payload"] == {"RelyingParty": REALMS_RP, "TokenType": "JWT",
        "Properties": {"UserTokens": ["canary-xbox"], "SandboxId": "RETAIL"}}
    assert result.authorization.value == "XBL3.0 x=synthetic-hash;canary-xbox"
    assert result.xuid != result.user_hash.value
    with pytest.raises(AccessDenied):
        await api.authorize(user, "https://arbitrary.invalid/")
    with pytest.raises(ProtocolError):
        await api.authorize(replace(user, expires_at=0), XBOX_RP)


@pytest.mark.parametrize("change", [dict(DisplayClaims={"xui": []}), dict(DisplayClaims={"xui": [{}, {}]}),
    dict(NotAfter="invalid"), dict(NotAfter="2000-01-01T00:00:00+00:00"), dict(Token="bad\r\nvalue"), dict(claim={"uhs": ""})])
def test_xbox_malformed_or_expired(change):
    clock = FakeTime()
    with pytest.raises(ProtocolError):
        XboxAuth(FakeHTTP(), clock=clock).parse(xbox(clock, **change), REALMS_RP)


async def test_xbox_denial_and_hash_mismatch():
    clock = FakeTime()
    api = XboxAuth(FakeHTTP(Response(403, {"XErr": "canary-secret"})), clock=clock)
    with pytest.raises(HTTPFailure):
        await api.user_token(auth(FakeHTTP(), clock).parse_tokens(oauth().body))
    api = XboxAuth(FakeHTTP(xbox(clock, claim={"uhs": "other"})), clock=clock)
    user = api.parse(xbox(clock), "http://auth.xboxlive.com")
    with pytest.raises(ProtocolError):
        await api.authorize(user, REALMS_RP)
