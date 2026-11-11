"""Synthetic-only privacy, single-request, and staff authorization coverage."""
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest

from realms_fakes import FakeHTTP
from test_realms_client import client
from test_realms_discord import interaction, settings, runtime
from test_realms_transport import Session, HTTPResponse
from utils.integrations.realms.errors import AccessDenied, HTTPFailure, ReauthRequired
from utils.integrations.realms.stories_debug import summarize, FIELDS
from utils.integrations.realms.transport import AiohttpTransport, STORIES_HOST, Response
from utils.realms.cog import RealmCommands

PATH = '/api/v1.0/worlds/42/stories'


def test_only_schema_and_fixed_labels_escape():
    secrets = ['canary-token', '123456789123456789', 'Private Player', 'private post', 'https://secret.invalid/image?token=secret']
    body = {'result': {'posts': [{'id': secrets[0], 'author': {'xuid': secrets[1], 'playerName': secrets[2]},
            'text': secrets[3], 'screenshots': [{'url': secrets[4]}], 'eventType': 'AUTOMATIC_EVENT'}],
            secrets[1]: {secrets[2]: secrets[3]}, 'type': secrets[4]}}
    report = summarize(body)
    assert all(secret not in report for secret in secrets)
    assert all(label + ': structural evidence detected' in report for label in ('Posts', 'Screenshots', 'Automatic events'))
    assert 'posts=1' in report and 'xuid:string' in report
    assert '<redacted-key>' in report and len(report) < 2000


def test_empty_and_bounded_reports_do_not_claim_absence():
    assert 'presence unknown' in summarize({'posts': [], 'screenshots': None})
    assert 'Scan truncated: yes' in summarize([{}] * 20000)
    assert len(summarize({key: [None] for key in FIELDS})) < 2000
    deep = {}; node = deep
    for _ in range(20):
        node['data'] = {}; node = node['data']
    assert 'Scan truncated: yes' in summarize(deep)


@pytest.mark.parametrize('status', [200, 401, 403, 404, 429, 503])
async def test_one_feed_get_even_on_retriable_status(status):
    http = FakeHTTP(Response(status, {'posts': []}))
    api = client(http)
    if status == 200:
        assert 'HTTP status: 200' in await api.stories_debug()
    else:
        with pytest.raises(HTTPFailure) as exc:
            await api.stories_debug()
        assert exc.value.status == status
    assert api.authorization.await_count == 1
    assert len(http.calls) == 1
    assert http.calls[0][:2] == ('GET', STORIES_HOST + PATH)
    assert http.calls[0][2]['headers']['Cache-Control'] == 'no-cache, no-store'


async def test_transport_feed_allowlist_stays_selected_and_get_only():
    session = Session(HTTPResponse())
    async with AiohttpTransport(selected_realm_id='42', session_factory=lambda **kw: session) as transport:
        await transport.request('GET', STORIES_HOST + PATH)
        for method, path in [('POST', PATH), ('GET', PATH.replace('42', '43')), ('GET', PATH + '/extra')]:
            with pytest.raises(AccessDenied):
                await transport.request(method, STORIES_HOST + path)
    assert len(session.calls) == 1


@pytest.mark.parametrize('guild,roles', [(None, (404,)), (999, (404,)), (202, ())])
async def test_debug_denied_before_io(guild, roles):
    api = NS(stories_debug=AsyncMock())
    cog = RealmCommands(NS(settings=settings()), runtime=api)
    ctx = interaction(guild=guild, roles=roles)
    await RealmCommands.storiesdebug.callback(cog, ctx)
    api.stories_debug.assert_not_awaited()
    assert ctx.response.send_message.call_args.kwargs['ephemeral']


@pytest.mark.parametrize('error', [None, HTTPFailure(401), HTTPFailure(429), ReauthRequired(), RuntimeError('canary-private-error')])
async def test_debug_private_and_sanitized_errors(error):
    ctx = interaction()
    async def probe():
        ctx.response.defer.assert_awaited_once_with(ephemeral=True, thinking=True)
        if error:
            raise error
        return 'HTTP status: 200\nTop-level JSON: object'
    cog = RealmCommands(NS(settings=settings()), runtime=NS(stories_debug=probe))
    await RealmCommands.storiesdebug.callback(cog, ctx)
    sent = ctx.followup.send.call_args
    assert sent.kwargs['ephemeral'] and 'canary' not in sent.args[0]
    assert sent.kwargs['allowed_mentions'].to_dict()['parse'] == []


async def test_debug_role_revoked_during_probe():
    ctx = interaction()
    async def probe():
        ctx.user.roles = []
        return 'private schema'
    cog = RealmCommands(NS(settings=settings()), runtime=NS(stories_debug=probe))
    await RealmCommands.storiesdebug.callback(cog, ctx)
    assert 'private schema' not in ctx.followup.send.call_args.args[0]


async def test_debug_runtime_does_not_enable_history_or_persist():
    api = runtime()
    api.client.stories_debug = AsyncMock(return_value='HTTP status: 200')
    assert await api.stories_debug() == 'HTTP status: 200'
    assert api._history_snapshot is None and api._history_retry_at == 0
    assert not api._tasks
    await api.close()


@pytest.mark.parametrize('status', [200, 302, 401, 403, 429, 503])
async def test_non_json_feed_responses_preserve_status_without_leaking(status):
    session = Session(HTTPResponse(b'canary-private-html', status))
    async with AiohttpTransport(selected_realm_id='42', session_factory=lambda **kw: session) as transport:
        if status == 200:
            with pytest.raises(HTTPFailure) as exc:
                await transport.request('GET', STORIES_HOST + PATH)
            assert exc.value.status == 200 and 'canary' not in str(exc.value)
        else:
            response = await transport.request('GET', STORIES_HOST + PATH)
            assert response.status == status and response.body is None
    assert len(session.calls) == 1
    assert not session.calls[0][1]['allow_redirects']


async def test_auth_failure_and_missing_selection_make_no_feed_request():
    http = FakeHTTP()
    api = client(http)
    api.authorization.side_effect = ReauthRequired()
    with pytest.raises(ReauthRequired):
        await api.stories_debug()
    assert not http.calls
    api = client(http, selected_realm_id=None)
    with pytest.raises(AccessDenied):
        await api.stories_debug()
    api.authorization.assert_not_awaited()
    assert not http.calls
