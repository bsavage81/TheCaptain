import asyncio
from datetime import datetime, timezone
import json

import aiohttp
import pytest

from utils.integrations.realms.errors import AccessDenied, ProtocolError, TransportError
from utils.integrations.realms.transport import AiohttpTransport, AUTHORITY, MAX_RESPONSE_BYTES, REALMS_HOST, retry_delay


class Content:
    def __init__(self, data):
        self.data = data

    async def iter_chunked(self, size):
        for i in range(0, len(self.data), size):
            yield self.data[i:i + size]


class HTTPResponse:
    def __init__(self, data=b"{}", status=200):
        self.content = Content(data)
        self.status = status
        self.headers = {"Retry-After": "9"}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


class Session:
    def __init__(self, response=None, error=None):
        self.response = response or HTTPResponse()
        self.error = error
        self.closed = False
        self.calls = []

    def request(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if self.error:
            raise self.error
        return self.response

    async def close(self):
        self.closed = True


async def test_session_security_and_shutdown_on_error():
    options = {}
    session = Session(HTTPResponse(json.dumps({"ok": True}).encode()))
    def factory(**kwargs):
        options.update(kwargs)
        return session
    with pytest.raises(RuntimeError):
        async with AiohttpTransport(session_factory=factory) as transport:
            response = await transport.request("GET", REALMS_HOST + "/worlds")
            assert response.body == {"ok": True} and response.retry_after == 9
            raise RuntimeError("synthetic caller failure")
    assert session.closed and transport._session is None
    assert options["trust_env"] is False
    assert isinstance(options["cookie_jar"], aiohttp.DummyCookieJar)
    assert options["timeout"].total == 30
    assert session.calls[0][1]["allow_redirects"] is False
    assert "ssl" not in session.calls[0][1]  # TLS verification defaults retained.


@pytest.mark.parametrize("response", [HTTPResponse(b"canary-secret-invalid-json"),
    HTTPResponse(b"x" * (MAX_RESPONSE_BYTES + 1)), HTTPResponse(b"{}", 302)])
async def test_redirect_invalid_json_and_oversize(response):
    session = Session(response)
    async with AiohttpTransport(session_factory=lambda **k: session) as transport:
        with pytest.raises(ProtocolError) as raised:
            await transport.request("GET", REALMS_HOST + "/worlds")
        assert "canary-secret" not in str(raised.value)
        assert raised.value.__context__ is None


@pytest.mark.parametrize("error", [aiohttp.ClientError("canary-secret"), TimeoutError("canary-secret"), OSError("canary-secret")])
async def test_transport_exception_context_has_no_original(error, caplog):
    async with AiohttpTransport(session_factory=lambda **k: Session(error=error)) as transport:
        with pytest.raises(TransportError) as raised:
            await transport.request("GET", REALMS_HOST + "/worlds", headers={"Authorization": "canary-secret"})
        assert raised.value.__context__ is None
        assert "canary-secret" not in str(raised.value) + caplog.text


@pytest.mark.parametrize("method,url", [("GET", REALMS_HOST + "/worlds/42/join"),
    ("GET", REALMS_HOST + "/worlds/43"), ("PUT", REALMS_HOST + "/worlds/42"),
    ("GET", "https://pocket.realms.minecraft.net.evil/worlds"), ("POST", "https://evil.invalid/token"),
    ("GET", AUTHORITY + "/token")])
async def test_transport_second_allowlist(method, url):
    session = Session()
    async with AiohttpTransport(selected_realm_id="42", session_factory=lambda **k: session) as transport:
        with pytest.raises(AccessDenied):
            await transport.request(method, url)
    assert not session.calls


async def test_cancelled_request_is_not_wrapped():
    async with AiohttpTransport(session_factory=lambda **k: Session(error=asyncio.CancelledError())) as transport:
        with pytest.raises(asyncio.CancelledError):
            await transport.request("GET", REALMS_HOST + "/worlds")


def test_retry_after_numeric_date_and_garbage():
    now = datetime(2030, 1, 1, tzinfo=timezone.utc)
    assert retry_delay("Tue, 01 Jan 2030 00:00:10 GMT", now) == 10
    assert retry_delay("5") == 5 and retry_delay("-1") == 0
    assert retry_delay("garbage") is None and retry_delay("NaN") is None
