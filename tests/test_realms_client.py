from unittest.mock import AsyncMock

import pytest

from realms_fakes import FakeHTTP, FakeTime, PRINCIPAL, config, xbox
from utils.integrations.realms.client import RealmsClient
from utils.integrations.realms.errors import AccessDenied, HTTPFailure, ProtocolError
from utils.integrations.realms.transport import REALMS_HOST, REALMS_RP, Response
from utils.integrations.realms.xbox import XboxAuth


def client(http, clock=None, **changes):
    clock = clock or FakeTime()
    token = XboxAuth(FakeHTTP(), clock=clock).parse(xbox(clock), REALMS_RP)
    auth = AsyncMock(return_value=token)
    return RealmsClient(http, auth, config(**changes), PRINCIPAL, sleep=clock.sleep, jitter=lambda: 0)


@pytest.mark.parametrize("method,path", [("PUT", "/worlds/42"), ("POST", "/invites/pending"),
    ("DELETE", "/worlds/42"), ("GET", "/worlds/42/join"), ("GET", "/worlds/43"),
    ("GET", "/invites/accept/42"), ("GET", "/worlds?x=1"), ("GET", "/worlds/42/../43"),
    ("GET", "https://evil.invalid/worlds"), ("GET", "/activities/liveplayerlist"), ("GET", "/links/v1")])
async def test_mutations_and_nonallowlisted_reads_rejected_before_auth(method, path):
    http = FakeHTTP()
    api = client(http)
    with pytest.raises(AccessDenied):
        await api.request(method, path)
    assert not api.authorization.mock_calls and not http.calls


async def test_selected_realm_nullable_roster_and_unknown_fields():
    http = FakeHTTP(Response(200, {"servers": [{"id": 42, "name": "Synthetic Realm", "state": "OPEN", "players": None, "extra": "ignored"}]}),
                    Response(200, {"id": 42, "name": "Synthetic Realm", "state": "CLOSED"}))
    api = client(http)
    result = await api.list_realms()
    assert result.data[0].players is None and result.observed_at.tzinfo is not None
    assert (await api.realm()).data.state == "CLOSED"
    headers = http.calls[0][2]["headers"]
    assert headers["Client-Version"] == "1.99.1"
    assert headers["Authorization"].startswith("XBL3.0 x=")
    assert "Synthetic Realm" not in repr(result)


async def test_activities_and_invites_are_observations_only():
    player = {"uuid": "123456", "name": None, "accepted": True, "online": True, "operator": False, "permission": "MEMBER"}
    http = FakeHTTP(Response(200, {"servers": [{"id": 42, "players": [player]}]}),
                    Response(200, {"invites": [{"invitationId": "synthetic-invite", "worldName": "Synthetic Realm"}]}),
                    Response(200, 1))
    api = client(http)
    assert (await api.activities()).data[0].players[0].xuid == "123456"
    assert len((await api.pending_invites()).data) == 1
    assert (await api.pending_invite_count()).data == 1
    assert all(c[0] == "GET" and c[1].startswith(REALMS_HOST) for c in http.calls)


@pytest.mark.parametrize("body", [{}, {"servers": None}, {"servers": [{"id": 42}]},
    {"servers": [{"id": 42, "players": None}]}, {"servers": [{"id": 42, "players": [{"uuid": "bad"}]}]}])
async def test_bad_activity_never_means_no_players(body):
    with pytest.raises(ProtocolError):
        await client(FakeHTTP(Response(200, body))).activities()


async def test_missing_realm_is_not_empty_player_list_and_no_selection_blocks_details():
    snapshot = await client(FakeHTTP(Response(200, {"servers": []}))).activities()
    assert not any(a.realm_id == "42" for a in snapshot.data)
    api = client(FakeHTTP(), selected_realm_id=None)
    with pytest.raises(AccessDenied):
        await api.realm()


@pytest.mark.parametrize("status", [403, 404, 500])
async def test_errors_are_sanitized_and_do_not_retry_auth(status):
    api = client(FakeHTTP(Response(status, {"secret": "canary-secret"})))
    with pytest.raises(HTTPFailure) as raised:
        await api.list_realms()
    assert api.authorization.await_count == 1
    assert raised.value.status == status and "canary" not in str(raised.value)


async def test_401_has_one_renewal_only():
    http = FakeHTTP(Response(401, {}), Response(401, {}))
    api = client(http)
    with pytest.raises(HTTPFailure):
        await api.list_realms()
    assert api.authorization.await_count == 2
    assert "rejected" in api.authorization.call_args.kwargs
    assert len(http.calls) == 2


async def test_throttling_backoff_bounded_and_honors_retry_after():
    clock = FakeTime()
    http = FakeHTTP(Response(429, {}, 7), Response(503, {}), Response(200, {"servers": []}))
    assert (await client(http, clock).list_realms()).data == ()
    assert clock.delays == [7, 2]
    clock.delays.clear()
    with pytest.raises(HTTPFailure) as raised:
        await client(FakeHTTP(Response(429, {}, 100)), clock).list_realms()
    assert raised.value.retry_after == 100 and not clock.delays
    http = FakeHTTP(*(Response(503, {}) for _ in range(3)))
    with pytest.raises(HTTPFailure):
        await client(http, clock).list_realms()
    assert len(http.calls) == 3
