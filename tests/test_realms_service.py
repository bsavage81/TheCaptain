import asyncio
from dataclasses import replace
from unittest.mock import AsyncMock

import pytest

from realms_fakes import FakeHTTP, FakeTime, MemoryStore, PRINCIPAL, account, config, device, oauth, xbox
from utils.integrations.realms.configuration import Principal, RealmsConfig
from utils.integrations.realms.errors import AccessDenied, Disabled, IdentityMismatch, ReauthRequired, StorageError
from utils.integrations.realms.models import Identity
from utils.integrations.realms.service import RealmsService
from utils.integrations.realms.transport import REALMS_RP, Response, XBOX_RP


def service(http, clock, store=None, settings=None):
    return RealmsService(settings or config(), http, store or MemoryStore(account()),
                         clock=clock, monotonic=clock, sleep=clock.sleep)


async def test_login_identity_before_storage_no_realms_access():
    clock = FakeTime()
    http = FakeHTTP(device(), oauth(), xbox(clock), xbox(clock))
    store = MemoryStore()
    api = service(http, clock, store)
    pending = await api.begin_device_login(PRINCIPAL)
    identity = await api.complete_device_login(PRINCIPAL, pending)
    assert identity == Identity("123456", "Synthetic Player")
    assert len(store.saved) == 1
    assert all("pocket.realms" not in call[1] for call in http.calls)
    assert "canary" not in repr(pending) + repr(identity)
    await api.close()


@pytest.mark.parametrize("claim", [{"gtg": "Wrong Player"}, {"xid": None}, {"gtg": None}, {"xid": "invalid"}])
async def test_wrong_or_missing_identity_never_persists(claim):
    clock = FakeTime()
    store = MemoryStore()
    api = service(FakeHTTP(device(), oauth(), xbox(clock), xbox(clock, claim=claim)), clock, store)
    pending = await api.begin_device_login(PRINCIPAL)
    with pytest.raises(IdentityMismatch):
        await api.complete_device_login(PRINCIPAL, pending)
    assert not store.saved
    assert api._pending is None


async def test_renewal_singleflight_expiry_and_audience_isolation():
    clock = FakeTime()
    http = FakeHTTP(oauth(), xbox(clock), xbox(clock), xbox(clock),
                    oauth(), xbox(clock), xbox(clock), xbox(clock))
    store = MemoryStore(account())
    api = service(http, clock, store)
    tokens = await asyncio.gather(*(api.authorization_for(PRINCIPAL) for _ in range(12)))
    assert all(t is tokens[0] for t in tokens)
    assert len(store.saved) == 1 and len(http.calls) == 4
    xbox_token = await api.authorization_for(PRINCIPAL, audience=XBOX_RP)
    assert xbox_token is not tokens[0]
    assert xbox_token.audience == XBOX_RP
    renewed = await asyncio.gather(*(api.authorization_for(PRINCIPAL, rejected=tokens[0]) for _ in range(10)))
    assert all(t is renewed[0] for t in renewed)
    assert len(store.saved) == 2 and len(http.calls) == 8
    assert renewed[0] is not tokens[0]
    await api.close()
    with pytest.raises(AccessDenied):
        await api.authorization_for(PRINCIPAL)


async def test_restart_refresh_and_durable_rotation_precedes_xbox():
    clock = FakeTime()
    store = MemoryStore(account())
    http = FakeHTTP(oauth(), Response(403, {}))
    api = service(http, clock, store)
    from utils.integrations.realms.errors import HTTPFailure
    with pytest.raises(HTTPFailure):
        await api.authorization_for(PRINCIPAL)
    assert store.account.refresh.value == "canary-refresh-new"
    # New process/service has no access token and must use the durable rotated token.
    http2 = FakeHTTP(oauth(), xbox(clock), xbox(clock), xbox(clock))
    await service(http2, clock, store).authorization_for(PRINCIPAL)
    assert http2.calls[0][2]["form"]["refresh_token"] == "canary-refresh-new"


async def test_revocation_tombstone_survives_restart_without_retry_loop():
    clock = FakeTime()
    store = MemoryStore(account())
    http = FakeHTTP(Response(400, {"error": "invalid_grant"}))
    api = service(http, clock, store)
    for _ in range(2):
        with pytest.raises(ReauthRequired):
            await api.authorization_for(PRINCIPAL)
    with pytest.raises(ReauthRequired):
        await service(FakeHTTP(), clock, store).authorization_for(PRINCIPAL)
    assert store.account.revoked and store.account.refresh.value == "revoked"
    assert len(http.calls) == 1


async def test_changed_xuid_blocks_realms_and_empty_store_needs_login():
    clock = FakeTime()
    api = service(FakeHTTP(oauth(), xbox(clock), xbox(clock, claim={"xid": "789"})), clock)
    with pytest.raises(IdentityMismatch):
        await api.authorization_for(PRINCIPAL)
    with pytest.raises(ReauthRequired):
        await api.authorization_for(PRINCIPAL)
    with pytest.raises(ReauthRequired):
        await service(FakeHTTP(), clock, MemoryStore()).authorization_for(PRINCIPAL)


async def test_storage_failure_blocks_token_use():
    clock = FakeTime()
    store = MemoryStore(account())
    def denied(account):
        raise StorageError()
    store.save = denied
    api = service(FakeHTTP(oauth()), clock, store)
    with pytest.raises(StorageError):
        await api.authorization_for(PRINCIPAL)
    with pytest.raises(ReauthRequired):
        await api.authorization_for(PRINCIPAL)


async def test_pending_bound_to_owner_cancel_and_close():
    clock = FakeTime()
    api = service(FakeHTTP(device()), clock, settings=config(auth_owner_ids=(101, 303)))
    pending = await api.begin_device_login(PRINCIPAL)
    with pytest.raises(AccessDenied):
        await api.begin_device_login(PRINCIPAL)
    with pytest.raises(AccessDenied):
        await api.complete_device_login(Principal(303, 202), pending)
    with pytest.raises(AccessDenied):
        api.cancel_device_login(Principal(303, 202), pending)
    entered = asyncio.Event()
    async def wait(challenge):
        entered.set()
        await asyncio.Event().wait()
    api.microsoft.poll_device_login = wait
    task = asyncio.create_task(api.complete_device_login(PRINCIPAL, pending))
    await entered.wait()
    api.cancel_device_login(PRINCIPAL, pending)
    with pytest.raises(asyncio.CancelledError):
        await task
    assert api._pending is None
    await api.close()


async def test_cancelled_rotation_waits_for_storage_before_unlock():
    import threading
    clock = FakeTime()
    store = MemoryStore(account())
    started = threading.Event()
    finish = threading.Event()
    original = store.save
    def save(value):
        started.set()
        assert finish.wait(10)
        original(value)
    store.save = save
    api = service(FakeHTTP(oauth()), clock, store)
    task = asyncio.create_task(api.authorization_for(PRINCIPAL))
    await asyncio.to_thread(started.wait, 10)
    task.cancel()
    await asyncio.sleep(0)
    assert api._lock.locked()
    finish.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert store.saved and not api._lock.locked()
    with pytest.raises(ReauthRequired):
        await api.authorization_for(PRINCIPAL)


async def test_disabled_never_touches_dependencies():
    http, store = AsyncMock(), AsyncMock()
    api = RealmsService(RealmsConfig(), http, store)
    for operation in (api.begin_device_login, api.authorization_for):
        with pytest.raises(Disabled):
            await operation(PRINCIPAL)
    assert not http.mock_calls and not store.mock_calls


async def test_expiring_tokens_rebuild_without_cross_account_cache():
    clock = FakeTime()
    http = FakeHTTP(oauth(), xbox(clock), xbox(clock), xbox(clock))
    api = service(http, clock)
    first = await api.authorization_for(PRINCIPAL)
    api._tokens[REALMS_RP] = replace(first, expires_at=clock() + 59)
    http.responses.append(xbox(clock))
    assert await api.authorization_for(PRINCIPAL) is not first
    assert len(http.calls) == 5


async def test_missing_or_forged_login_handle_is_denied_cleanly():
    api = service(FakeHTTP(), FakeTime())
    for pending in (None, object()):
        with pytest.raises(AccessDenied):
            await api.complete_device_login(PRINCIPAL, pending)
        with pytest.raises(AccessDenied):
            api.cancel_device_login(PRINCIPAL, pending)
    assert not api.transport.calls


async def test_relogin_cannot_replace_existing_pinned_xuid():
    clock = FakeTime()
    store = MemoryStore(account(identity=Identity("789", "Synthetic Player")))
    api = service(FakeHTTP(device(), oauth(), xbox(clock), xbox(clock)), clock, store)
    pending = await api.begin_device_login(PRINCIPAL)
    with pytest.raises(IdentityMismatch):
        await api.complete_device_login(PRINCIPAL, pending)
    assert not store.saved and store.account.identity.xuid == "789"


async def test_login_identity_rejects_control_characters_before_print_or_save():
    clock = FakeTime()
    store = MemoryStore()
    api = service(FakeHTTP(device(), oauth(), xbox(clock), xbox(clock, claim={"gtg": "Synthetic Player\r\n"})), clock, store)
    pending = await api.begin_device_login(PRINCIPAL)
    with pytest.raises(IdentityMismatch):
        await api.complete_device_login(PRINCIPAL, pending)
    assert not store.saved
