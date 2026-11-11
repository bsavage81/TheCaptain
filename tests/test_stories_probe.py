import json
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest

from realms_fakes import FakeHTTP
from test_realms_client import client
from test_realms_discord import settings, interaction
from test_realms_transport import Session, HTTPResponse
from utils.integrations.realms.errors import AccessDenied, ReauthRequired
from utils.integrations.realms.stories_probe import probe_urls
from utils.integrations.realms.transport import AiohttpTransport, STORIES_HOST, XBOX_RP, Response
from utils.realms.cog import RealmCommands

REF = 'userposts.xboxlive.com/users/xuid(123456)/posts/12345678-1234-1234-1234-123456789abc/timelines/Club/654321'
BODY = {'result': [{'id': 'private-id', 'clubsPostId': REF}]}
FEED = STORIES_HOST + '/api/v1.0/worlds/42/stories'


@pytest.mark.parametrize('ref', [REF + '?token=x', REF + '/extra', 'https://' + REF,
    REF.replace('userposts.xboxlive.com', 'evil.invalid'), REF.replace('654321', '../42'),
    REF.replace('123456)', '18446744073709551616)'), REF.replace('123456)', '0123456)'), None])
def test_invalid_reference_never_creates_xbox_routes(ref):
    assert probe_urls({'result': [{'clubsPostId': ref}]}) is None


async def test_investigation_has_three_gets_correct_audiences_and_contract():
    http = FakeHTTP(Response(200, BODY), Response(200, {'postContentLocators': []}),
                    Response(200, {'activityItems': [{'ugcCaption': 'private text'}]}))
    api = client(http)
    report = await api.stories_investigation()
    assert report['realm_feed']['body'] == BODY
    assert report['club_feed']['body']['activityItems'][0]['ugcCaption'] == 'private text'
    assert len(http.calls) == 3 and all(c[0] == 'GET' for c in http.calls)
    assert tuple(c[1] for c in http.calls[1:]) == probe_urls(BODY)
    assert api.authorization.await_count == 2
    assert api.authorization.call_args.kwargs == {'audience': XBOX_RP}
    assert 'x-xbl-contract-version' not in http.calls[1][2]['headers']
    assert http.calls[2][2]['headers']['x-xbl-contract-version'] == '13'
    assert 'Authorization' not in json.dumps(report)


@pytest.mark.parametrize('status', [301, 401, 403, 429, 503])
async def test_post_failure_still_collects_club_feed_without_retries(status):
    http = FakeHTTP(Response(200, BODY), Response(status, {'private-error': 'secret'}), Response(200, {}))
    api = client(http); report = await api.stories_investigation()
    assert report['xbox_post']['http_status'] == status and report['club_feed']['http_status'] == 200
    assert len(http.calls) == 3 and 'secret' not in json.dumps(report)


async def test_no_reference_or_auth_failure_skips_xbox():
    http = FakeHTTP(Response(200, {'result': []})); api = client(http)
    assert (await api.stories_investigation())['xbox_probes']['state'] == 'skipped'
    assert len(http.calls) == 1
    http = FakeHTTP(Response(200, BODY)); api = client(http)
    token = api.authorization.return_value
    api.authorization.side_effect = [token, ReauthRequired()]
    report = await api.stories_investigation()
    assert report['xbox_probes']['state'] == 'authentication_failed' and len(http.calls) == 1


async def test_transport_grants_only_exact_realm_derived_gets_and_resets():
    session = Session(HTTPResponse(json.dumps(BODY).encode()))
    async with AiohttpTransport(selected_realm_id='42', session_factory=lambda **kw: session) as transport:
        post, club = probe_urls(BODY)
        with pytest.raises(AccessDenied):
            await transport.request('GET', post)
        await transport.request('GET', FEED)
        session.response = HTTPResponse(b'{}')
        await transport.request('GET', post)
        await transport.request('GET', club)
        for method, url in [('POST', post), ('DELETE', post), ('GET', post + '/comments'),
                            ('GET', club.replace('numItems=10', 'numItems=100')), ('GET', post.replace('654321', '654322'))]:
            with pytest.raises(AccessDenied):
                await transport.request(method, url)
        await transport.request('GET', FEED)  # New feed has no valid reference.
        with pytest.raises(AccessDenied):
            await transport.request('GET', post)
    assert len(session.calls) == 4


async def test_probe_html_error_preserves_status_no_body():
    session = Session(HTTPResponse(json.dumps(BODY).encode()))
    async with AiohttpTransport(selected_realm_id='42', session_factory=lambda **kw: session) as transport:
        await transport.request('GET', FEED)
        session.response = HTTPResponse(b'private-html', 403)
        response = await transport.request('GET', probe_urls(BODY)[0])
        assert response.status == 403 and response.body is None


async def test_investigation_attached_privately_and_revocation_prevents_delivery():
    ctx = interaction(); report = {'realm_feed': {'http_status': 200, 'body': BODY}}
    cog = RealmCommands(NS(settings=settings()), runtime=NS(stories_debug=AsyncMock(return_value=report)))
    await RealmCommands.storiesdebug.callback(cog, ctx)
    sent = ctx.followup.send.call_args
    assert sent.kwargs['ephemeral'] and sent.kwargs['file'].filename == 'realm-stories-investigation.json'
    assert json.load(sent.kwargs['file'].fp) == report
    async def revoke():
        ctx.user.roles = []
        return report
    cog.runtime.stories_debug = revoke
    await RealmCommands.storiesdebug.callback(cog, ctx)
    assert 'file' not in ctx.followup.send.call_args.kwargs


async def test_transport_authorizes_only_returned_same_club_pagination_cursor():
    from utils.integrations.realms.stories_probe import next_club_page
    session = Session(HTTPResponse(json.dumps(BODY).encode()))
    async with AiohttpTransport(selected_realm_id='42', session_factory=lambda **kwargs: session) as transport:
        await transport.request('GET', FEED)
        base = probe_urls(BODY)[1]
        unauthorized = base + '&contToken=not-returned'
        with pytest.raises(AccessDenied):
            await transport.request('GET', unauthorized)
        page = {'activityItems': [], 'contToken': 'https://evil.invalid/?secret=opaque'}
        session.response = HTTPResponse(json.dumps(page).encode())
        await transport.request('GET', base)
        next_url = next_club_page(base, page)
        assert next_url.startswith(base + '&contToken=https%3A%2F%2Fevil.invalid')
        with pytest.raises(AccessDenied):
            await transport.request('GET', page['contToken'])
        session.response = HTTPResponse(json.dumps({'activityItems': []}).encode())
        await transport.request('GET', next_url)
        with pytest.raises(AccessDenied):
            await transport.request('GET', next_url)
        # A fresh Realm feed read reauthorizes the first club page on the next run.
        session.response = HTTPResponse(json.dumps(BODY).encode())
        await transport.request('GET', FEED)
        session.response = HTTPResponse(json.dumps({'activityItems': []}).encode())
        await transport.request('GET', base)


async def test_transport_does_not_authorize_exhausted_zero_cursor():
    session = Session(HTTPResponse(json.dumps(BODY).encode()))
    async with AiohttpTransport(selected_realm_id='42', session_factory=lambda **kwargs: session) as transport:
        await transport.request('GET', FEED)
        base = probe_urls(BODY)[1]
        session.response = HTTPResponse(json.dumps({'activityItems': [], 'contToken': '0'}).encode())
        await transport.request('GET', base)
        with pytest.raises(AccessDenied):
            await transport.request('GET', base + '&contToken=0')
