from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest

from test_realms_discord import settings, interaction, runtime
from test_realms_client import client
from realms_fakes import FakeHTTP
from utils.integrations.realms.transport import Response, STORIES_HOST
from utils.integrations.realms.errors import HTTPFailure, ProtocolError
from utils.realms.cog import RealmCommands
from utils.realms.stories_feed import render_feed, image_url


def feed():
    return {'result': [{'id': 'private-id', 'timestamp': '2026-11-11T09:00:00Z',
            'message': 'A new build @everyone', 'author': {'gamertag': 'Builder'},
            'images': [{'url': 'https://example.blob.core.windows.net/story/image.png'}],
            'token': 'secret-token', 'xuid': '123456789'}]}


def context():
    ctx = interaction()
    ctx.guild.me = NS()
    ctx.channel = NS(id=303, guild=ctx.guild, send=AsyncMock(),
        permissions_for=lambda member: NS(view_channel=True, send_messages=True, embed_links=True))
    return ctx


def test_renderer_uses_only_explicit_content_and_bounded_embeds():
    entries, skipped, remaining = render_feed(feed())
    assert len(entries) == 1 and skipped == remaining == 0
    identity, embed = entries[0]
    assert identity == 'private-id' and 'A new build' in embed.description
    payload = str(embed.to_dict())
    assert 'secret-token' not in payload and '123456789' not in payload and 'private-id' not in payload
    assert '@everyone' not in embed.description
    assert embed.author.name == 'Builder' and embed.timestamp.tzinfo
    assert embed.image.url.endswith('image.png')
    body = feed(); body['result'][0]['message'] = 'x' * 9000
    assert len(render_feed(body)[0][0][1]) <= 1800


def test_unknown_items_and_private_metadata_are_not_dumped():
    assert render_feed({'result': [{'id': 'a', 'timestamp': 'bad', 'unknown': 'secret', 'xuid': '123'}]}) == ([], 1, 0)
    assert render_feed({'result': []}) == ([], 0, 0)
    with pytest.raises(ProtocolError):
        render_feed({'result': {'activity': {}}})
    body = feed(); body['result'] *= 12
    entries, skipped, remaining = render_feed(body)
    assert len(entries) == 1 and skipped == 9 and remaining == 2


@pytest.mark.parametrize('url', ['http://example.blob.core.windows.net/a', 'https://localhost/a',
    'https://127.0.0.1/a', 'https://blob.core.windows.net.evil.invalid/a',
    'https://user:password@example.blob.core.windows.net/a', 'https://example.blob.core.windows.net:1234/a'])
def test_bad_media_not_embedded(url):
    assert image_url(url) is None


@pytest.mark.parametrize('guild,roles', [(None, (404,)), (999, (404,)), (202, ())])
async def test_post_requires_coastal_op_team_before_io(guild, roles):
    ctx = interaction(guild=guild, roles=roles)
    api = NS(story_feed=AsyncMock())
    cog = RealmCommands(NS(settings=settings()), runtime=api)
    await RealmCommands.storiespost.callback(cog, ctx)
    api.story_feed.assert_not_awaited()
    assert ctx.response.send_message.call_args.kwargs['ephemeral']


async def test_one_shot_posts_to_invoking_channel_and_guards_duplicates():
    ctx = context()
    api = NS(story_feed=AsyncMock(return_value=feed()))
    cog = RealmCommands(NS(settings=settings()), runtime=api)
    await RealmCommands.storiespost.callback(cog, ctx)
    assert api.story_feed.await_count == 1 and ctx.channel.send.await_count == 1
    assert ctx.channel.send.call_args.kwargs['allowed_mentions'].to_dict()['parse'] == []
    assert ctx.followup.send.call_args.kwargs['ephemeral']
    await RealmCommands.storiespost.callback(cog, ctx)
    assert ctx.channel.send.await_count == 1
    assert '1 already posted' in ctx.followup.send.call_args.args[0]


async def test_missing_embed_permission_stops_before_realm_io():
    ctx = context()
    ctx.channel.permissions_for = lambda member: NS(view_channel=True, send_messages=True, embed_links=False)
    api = NS(story_feed=AsyncMock())
    cog = RealmCommands(NS(settings=settings()), runtime=api)
    await RealmCommands.storiespost.callback(cog, ctx)
    api.story_feed.assert_not_awaited()
    ctx.channel.send.assert_not_awaited()


async def test_revoked_role_after_get_prevents_publication():
    ctx = context()
    async def read():
        ctx.user.roles = []
        return feed()
    cog = RealmCommands(NS(settings=settings()), runtime=NS(story_feed=read))
    await RealmCommands.storiespost.callback(cog, ctx)
    ctx.channel.send.assert_not_awaited()


async def test_partial_send_failure_reports_count_and_retains_sent_guard():
    ctx = context(); body = feed()
    body['result'].append(dict(body['result'][0], id='second'))
    ctx.channel.send.side_effect = [None, RuntimeError('canary-token')]
    cog = RealmCommands(NS(settings=settings()), runtime=NS(story_feed=AsyncMock(return_value=body)))
    await RealmCommands.storiespost.callback(cog, ctx)
    message = ctx.followup.send.call_args.args[0]
    assert 'Posted 1' in message and 'canary' not in message and len(cog._stories_sent) == 1


async def test_api_error_sanitized_no_channel_send():
    ctx = context()
    cog = RealmCommands(NS(settings=settings()), runtime=NS(story_feed=AsyncMock(side_effect=HTTPFailure(403))))
    await RealmCommands.storiespost.callback(cog, ctx)
    assert 'HTTP 403' in ctx.followup.send.call_args.args[0]
    ctx.channel.send.assert_not_awaited()


async def test_feed_client_reuses_auth_single_get_and_runtime_no_history_writes():
    http = FakeHTTP(Response(200, feed()))
    api = client(http)
    assert await api.story_feed() == feed()
    assert len(http.calls) == 1 and api.authorization.await_count == 1
    assert http.calls[0][:2] == ('GET', STORIES_HOST + '/api/v1.0/worlds/42/stories')
    rt = runtime(); rt.client.story_feed = AsyncMock(return_value=feed())
    assert await rt.story_feed() == feed()
    assert rt._history_snapshot is None and not rt._tasks
    await rt.close()
