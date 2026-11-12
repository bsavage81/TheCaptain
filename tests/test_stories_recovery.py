import pytest

from realms_fakes import FakeHTTP
from test_realms_client import client
from test_realms_transport import Session
from test_stories_post import feed
from test_stories_probe import BODY
from utils.integrations.realms.errors import HTTPFailure, TransportError
from utils.integrations.realms.transport import AiohttpTransport, Response, STORIES_HOST


async def test_realm_and_club_transient_get_failures_recover_with_same_urls():
    http = FakeHTTP(TransportError('timeout', 'realm_stories'), Response(200, BODY),
                    TransportError('connection', 'xbox_stories'), Response(200, feed()))
    api = client(http)
    body = await api.club_story_feed(all_pages=True)
    assert len(body['activityItems']) == 1
    assert len(http.calls) == 4
    assert http.calls[0][1] == http.calls[1][1]
    assert http.calls[2][1] == http.calls[3][1]
    assert all(call[0] == 'GET' for call in http.calls)
    assert api.authorization.await_count == 2


async def test_transport_retries_are_bounded():
    http = FakeHTTP(TransportError(), TransportError())
    with pytest.raises(TransportError):
        await client(http).story_feed()
    assert len(http.calls) == 2


@pytest.mark.parametrize('reason', ['tls', 'invalid_request', 'session_unavailable'])
async def test_nontransient_transport_failures_not_retried(reason):
    http = FakeHTTP(TransportError(reason, 'realm_stories'))
    with pytest.raises(TransportError):
        await client(http).story_feed()
    assert len(http.calls) == 1


async def test_http_failure_not_retried_as_transport_failure():
    http = FakeHTTP(Response(429, None, 900))
    with pytest.raises(HTTPFailure) as caught:
        await client(http).story_feed()
    assert caught.value.retry_after == 900 and len(http.calls) == 1


async def test_transport_classifies_timeout_without_retaining_secret_context():
    async with AiohttpTransport(selected_realm_id='42', session_factory=lambda **kwargs:
                                Session(error=TimeoutError('canary-secret'))) as transport:
        with pytest.raises(TransportError) as caught:
            await transport.request('GET', STORIES_HOST + '/api/v1.0/worlds/42/stories')
        error = caught.value
        assert error.reason == 'timeout' and error.service == 'realm_stories'
        assert error.__context__ is None and 'canary' not in str(error)
