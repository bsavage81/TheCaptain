import copy
from dataclasses import replace
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock

import pytest

from realms_fakes import FakeHTTP, FakeTime, PRINCIPAL, config
from test_realms_panel import observation, player
from test_realms_transport import Session
from utils.integrations.realms.errors import AccessDenied, HTTPFailure, ProtocolError
from utils.integrations.realms.models import Secret
from utils.integrations.realms.profiles import ProfileClient
from utils.integrations.realms.transport import AiohttpTransport, PROFILE_BATCH, Response, XBOX_RP
from utils.realms.names import GamertagCache
from utils.realms.panel import Sessions, panel_embed


def response(xuid="123", name="Synthetic Sailor"):
    return Response(200, {"profileUsers": [{"id": xuid, "settings": [{"id":"Gamertag", "value": name}]}]})


def client(*responses):
    http = FakeHTTP(*responses)
    auth = AsyncMock(return_value=NS(authorization=Secret("synthetic-auth")))
    return ProfileClient(http, auth, config(), PRINCIPAL), http, auth


async def test_batch_request_uses_xbox_audience_only_and_fixed_read_payload():
    api, http, auth = client(response())
    assert await api.gamertags(["123", "456"]) == {"123": "Synthetic Sailor"}
    auth.assert_awaited_once_with(PRINCIPAL, audience=XBOX_RP)
    method, url, kwargs = http.calls[0]
    assert (method, url) == ("POST", PROFILE_BATCH)
    assert kwargs["payload"] == {"userIds":["123","456"], "settings":["Gamertag"]}
    assert kwargs["headers"]["x-xbl-contract-version"] == "2"


async def test_401_renews_once_and_429_returns_without_looping():
    api, http, auth = client(Response(401, {}), response())
    await api.gamertags(["123"])
    assert auth.await_count == 2 and "rejected" in auth.call_args.kwargs
    api, http, _ = client(Response(429, {}, 7200))
    with pytest.raises(HTTPFailure) as error:
        await api.gamertags(["123"])
    assert error.value.retry_after == 7200 and len(http.calls) == 1


@pytest.mark.parametrize("ids", [[], ["0"], ["01"], ["abc"], ["123","123"], ["18446744073709551616"], ["123"] * 101])
async def test_invalid_batch_rejected_before_authentication(ids):
    api, http, auth = client()
    with pytest.raises(AccessDenied):
        await api.gamertags(ids)
    auth.assert_not_awaited()
    assert not http.calls


@pytest.mark.parametrize("body", [{}, {"profileUsers":None}, {"profileUsers":[{"id":"456","settings":[]}]},
    {"profileUsers":[{"id":"123","settings":[{"id":"Gamertag","value":"bad\nname"}]}]},
    {"profileUsers":[{"id":"123","settings":[{"id":"GameDisplayName","value":"Wrong setting"}]}]},
    {"profileUsers":[{"id":"123","settings":[]},{"id":"123","settings":[]}]}])
async def test_profile_response_rejects_malformed_or_unrequested_identities(body):
    api, _, _ = client(Response(200, body))
    with pytest.raises(ProtocolError):
        await api.gamertags(["123"])


@pytest.mark.parametrize("method,url,payload", [
    ("GET",PROFILE_BATCH,None), ("POST",PROFILE_BATCH+"/",{}),
    ("POST",PROFILE_BATCH,{"userIds":["123"],"settings":["Gamerscore"]}),
    ("POST",PROFILE_BATCH,{"userIds":["0"],"settings":["Gamertag"]}),
    ("POST","https://peoplehub.xboxlive.com/users/batch",{}),
    ("PUT",PROFILE_BATCH,{"userIds":["123"],"settings":["Gamertag"]}),
])
async def test_transport_does_not_broaden_to_profile_writes_or_other_hosts(method,url,payload):
    session = Session()
    async with AiohttpTransport(session_factory=lambda **k: session) as transport:
        with pytest.raises(AccessDenied):
            await transport.request(method,url,payload=payload)
    assert not session.calls


async def test_transport_accepts_only_the_verified_batch_shape():
    session = Session()
    async with AiohttpTransport(session_factory=lambda **k: session) as transport:
        await transport.request("POST",PROFILE_BATCH,payload={"userIds":["123"],"settings":["Gamertag"]})
    assert len(session.calls) == 1
    assert session.calls[0][1]["allow_redirects"] is False


def cache():
    clock = FakeTime()
    store = NS(load_gamertags=Mock(return_value=None), save_gamertags=Mock())
    api = NS(gamertags=AsyncMock(return_value={"123":"Synthetic Sailor"}))
    return GamertagCache(api, store, clock=clock), clock, store, api


def snapshot(*players):
    return observation(players).activity


async def test_cached_names_persist_restart_and_expire_without_changing_activity_time_or_sessions():
    names, clock, store, api = cache()
    activity = snapshot(player(name=None))
    enriched = await names.enrich(activity)
    assert enriched.data.players[0].name == "Synthetic Sailor"
    assert enriched.observed_at == activity.observed_at
    state = copy.deepcopy(store.save_gamertags.call_args.args[0])
    for _ in range(10):
        await names.enrich(activity)
        clock.value += 15
    assert api.gamertags.await_count == 1 and store.save_gamertags.call_count == 1
    restored = GamertagCache(api, NS(load_gamertags=Mock(return_value=state), save_gamertags=Mock()), clock=clock)
    assert (await restored.enrich(activity)).data.players[0].name == "Synthetic Sailor"
    assert api.gamertags.await_count == 1
    clock.value += 86400
    api.gamertags.return_value = {"123":"Renamed Sailor"}
    assert (await restored.enrich(activity)).data.players[0].name == "Renamed Sailor"
    assert api.gamertags.await_count == 2
    sessions = Sessions("42")
    sessions.observe(observation((player(name=None),)))
    result = replace(observation((player(name=None),)), activity=enriched)
    assert "Tracked for" in str(panel_embed(result, sessions,15).to_dict())
    assert sessions.active.keys() == {"123"}


async def test_negative_cache_and_new_players_do_not_trigger_calls_every_poll():
    names, clock, _, api = cache()
    api.gamertags.return_value = {}
    assert (await names.enrich(snapshot(player(name=None)))).data.players[0].name is None
    clock.value += 15
    await names.enrich(snapshot(player(name=None),player("456",None)))
    assert api.gamertags.await_count == 1
    clock.value += 45
    await names.enrich(snapshot(player(name=None),player("456",None)))
    assert api.gamertags.call_args.args[0] == ["456"]
    clock.value += 900
    await names.enrich(snapshot(player(name=None)))
    assert api.gamertags.call_args.args[0] == ["123"]


async def test_zero_xuids_offline_players_and_supplied_names_need_no_lookup():
    names, _, _, api = cache()
    activity = snapshot(player("0",None),player("123",None,False),player("456","Supplied"))
    result = await names.enrich(activity)
    api.gamertags.assert_not_awaited()
    assert result.data.players[2].name == "Supplied"
    assert not Sessions.authoritative(observation((player("0",None),)))


async def test_rate_limit_backoff_persists_and_keeps_other_names_and_presence(caplog):
    names, clock, store, api = cache()
    await names.enrich(snapshot(player(name=None)))
    clock.value += 60
    api.gamertags.side_effect = HTTPFailure(429,7200)
    activity = snapshot(player(name=None),player("456",None))
    result = await names.enrich(activity)
    assert result.data.players[0].name == "Synthetic Sailor"
    assert result.data.players[1].name is None
    assert result.data.players[1].online is True
    assert names.next_lookup == clock.value + 7200
    state = copy.deepcopy(store.save_gamertags.call_args.args[0])
    restarted = GamertagCache(api,NS(load_gamertags=Mock(return_value=state),save_gamertags=Mock()),clock=clock)
    await restarted.enrich(activity)
    assert api.gamertags.await_count == 2
    assert "456" not in caplog.text and "synthetic-auth" not in caplog.text


async def test_corrupt_private_cache_fails_closed_without_overwrite_or_profile_call():
    names, clock, store, api = cache()
    store.load_gamertags.return_value = {"entries":{"bad":"corrupt"},"next_lookup":0}
    result = await names.enrich(snapshot(player(name=None)))
    assert result.data.players[0].name is None
    clock.value += 15
    await names.enrich(result)
    assert store.load_gamertags.call_count == 1
    store.save_gamertags.assert_not_called()
    api.gamertags.assert_not_awaited()


async def test_profile_failure_never_removes_presence_or_resets_existing_session(caplog):
    names, _, _, api = cache()
    api.gamertags.side_effect = TimeoutError("private-id-canary")
    original = observation((player(name=None),))
    sessions = Sessions("42")
    sessions.observe(original)
    starts = dict(sessions.active)
    enriched = await names.enrich(original.activity)
    assert enriched.data.players[0].online is True and enriched.data.players[0].name is None
    sessions.observe(replace(original,activity=enriched))
    assert sessions.active == starts
    assert "private-id-canary" not in caplog.text


async def test_cache_and_batch_size_are_bounded():
    names, clock, _, api = cache()
    api.gamertags.side_effect = lambda ids: {x:"Sailor" for x in ids}
    for offset in (0,100,200):
        await names.enrich(snapshot(*(player(str(x),None) for x in range(offset+1,offset+101))))
        clock.value += 60
    assert len(names.entries) == 100
    assert all(len(call.args[0]) <= 100 for call in api.gamertags.call_args_list)


async def test_service_profile_client_reuses_existing_refresh_without_realms_audience():
    from realms_fakes import MemoryStore, account, oauth, xbox
    from utils.integrations.realms.service import RealmsService
    clock = FakeTime()
    http = FakeHTTP(oauth(),xbox(clock),xbox(clock),response())
    api = RealmsService(config(),http,MemoryStore(account()),clock=clock,monotonic=clock)
    assert await api.profile_client(PRINCIPAL).gamertags(["123"]) == {"123":"Synthetic Sailor"}
    assert http.calls[2][2]["payload"]["RelyingParty"] == XBOX_RP
    assert not any("pocket.realms" in url for _,url,_ in http.calls)
    await api.close()


async def test_shared_runtime_enriches_once_and_commands_reuse_observation():
    from test_realms_discord import runtime
    clock = FakeTime()
    api = runtime(clock)
    names, _, _, lookup = cache()
    api.names = names
    api.client.activities.return_value = NS(data=(snapshot(player(name=None)).data,), observed_at=observation(()).activity.observed_at)
    first, _ = await api.observe(scheduled=True)
    second, _ = await api.observe()
    assert first.activity.data.players[0].name == "Synthetic Sailor"
    assert second is first
    lookup.gamertags.assert_awaited_once_with(["123"])
    api.client.activities.assert_awaited_once()


async def test_expired_names_are_not_displayed_when_lookup_fails():
    names, clock, _, api = cache()
    activity = snapshot(player(name=None))
    await names.enrich(activity)
    clock.value += 86401
    api.gamertags.side_effect = HTTPFailure(403)
    assert (await names.enrich(activity)).data.players[0].name is None
