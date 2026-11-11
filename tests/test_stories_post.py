from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest

from test_realms_discord import settings, interaction, runtime
from test_realms_client import client
from realms_fakes import FakeHTTP
from utils.integrations.realms.transport import Response, STORIES_HOST
from utils.integrations.realms.errors import HTTPFailure, ProtocolError
from utils.realms.cog import RealmCommands
from utils.realms.stories_feed import render_feed, image_url, EVENT_ARTWORK


def feed():
    return {'activityItems': [{'feedItemId': 'private-id', 'date': '2026-11-11T09:00:00Z',
            'ugcCaption': 'A new build @everyone', 'authorInfo': {'modernGamertag': 'Builder'},
            'activityItemType': 'Screenshot', 'contentType': 'Game',
            'screenshotUri': 'https://images-eds.xboxlive.com/story/image.png',
            'token': 'secret-token', 'xuid': '123456789'}]}


def context():
    ctx = interaction()
    ctx.guild.me = NS()
    ctx.channel = NS(id=303, guild=ctx.guild, send=AsyncMock(),
        permissions_for=lambda member: NS(view_channel=True, send_messages=True, embed_links=True, attach_files=True))
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
    body = feed(); body['activityItems'][0]['ugcCaption'] = 'x' * 9000
    assert len(render_feed(body)[0][0][1]) <= 1800


def test_unknown_items_and_private_metadata_are_not_dumped():
    assert render_feed({'activityItems': [{'feedItemId': 'a', 'date': 'bad', 'unknown': 'secret', 'xuid': '123'}]}) == ([], 1, 0)
    assert render_feed({'activityItems': []}) == ([], 0, 0)
    with pytest.raises(ProtocolError):
        render_feed({'activityItems': {'activity': {}}})
    body = feed(); body['activityItems'] *= 12
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
    api = NS(club_story_feed=AsyncMock())
    cog = RealmCommands(NS(settings=settings()), runtime=api)
    await RealmCommands.storiespost.callback(cog, ctx)
    api.club_story_feed.assert_not_awaited()
    assert ctx.response.send_message.call_args.kwargs['ephemeral']


async def test_one_shot_posts_to_invoking_channel_and_guards_duplicates():
    ctx = context()
    api = NS(club_story_feed=AsyncMock(return_value=feed()))
    cog = RealmCommands(NS(settings=settings()), runtime=api)
    await RealmCommands.storiespost.callback(cog, ctx)
    assert api.club_story_feed.await_count == 1 and ctx.channel.send.await_count == 1
    assert ctx.channel.send.call_args.kwargs['allowed_mentions'].to_dict()['parse'] == []
    assert ctx.followup.send.call_args.kwargs['ephemeral']
    await RealmCommands.storiespost.callback(cog, ctx)
    assert ctx.channel.send.await_count == 1
    assert '1 already posted' in ctx.followup.send.call_args.args[0]


async def test_missing_embed_permission_stops_before_realm_io():
    ctx = context()
    ctx.channel.permissions_for = lambda member: NS(view_channel=True, send_messages=True, embed_links=False)
    api = NS(club_story_feed=AsyncMock())
    cog = RealmCommands(NS(settings=settings()), runtime=api)
    await RealmCommands.storiespost.callback(cog, ctx)
    api.club_story_feed.assert_not_awaited()
    ctx.channel.send.assert_not_awaited()


async def test_revoked_role_after_get_prevents_publication():
    ctx = context()
    async def read():
        ctx.user.roles = []
        return feed()
    cog = RealmCommands(NS(settings=settings()), runtime=NS(club_story_feed=read))
    await RealmCommands.storiespost.callback(cog, ctx)
    ctx.channel.send.assert_not_awaited()


async def test_partial_send_failure_reports_count_and_retains_sent_guard():
    ctx = context(); body = feed()
    body['activityItems'].append(dict(body['activityItems'][0], feedItemId='second'))
    ctx.channel.send.side_effect = [None, RuntimeError('canary-token')]
    cog = RealmCommands(NS(settings=settings()), runtime=NS(club_story_feed=AsyncMock(return_value=body)))
    await RealmCommands.storiespost.callback(cog, ctx)
    message = ctx.followup.send.call_args.args[0]
    assert 'Posted 1' in message and 'canary' not in message and len(cog._stories_sent) == 1


async def test_api_error_sanitized_no_channel_send():
    ctx = context()
    cog = RealmCommands(NS(settings=settings()), runtime=NS(club_story_feed=AsyncMock(side_effect=HTTPFailure(403))))
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


async def test_club_posting_reads_two_gets_and_skips_direct_post_endpoint():
    from utils.integrations.realms.transport import XBOX_RP
    from test_stories_probe import BODY, probe_urls
    http = FakeHTTP(Response(200, BODY), Response(200, feed()))
    api = client(http)
    assert await api.club_story_feed() == dict(feed(), realmEvents=BODY["result"])
    assert len(http.calls) == 2 and all(c[0] == 'GET' for c in http.calls)
    assert http.calls[1][1] == probe_urls(BODY)[1]
    assert api.authorization.call_args.kwargs == {'audience': XBOX_RP}
    assert http.calls[1][2]['headers']['x-xbl-contract-version'] == '13'
    rt = runtime(); rt.client.club_story_feed = AsyncMock(return_value=feed())
    assert await rt.club_story_feed() == feed()
    assert rt._history_snapshot is None and not rt._tasks
    await rt.close()


@pytest.mark.parametrize('status', [401, 403, 429, 503])
async def test_club_posting_error_never_retries_or_replays(status):
    from test_stories_probe import BODY
    http = FakeHTTP(Response(200, BODY), Response(status, {'secret': 'do-not-render'}))
    with pytest.raises(HTTPFailure) as error:
        await client(http).club_story_feed()
    assert error.value.status == status and len(http.calls) == 2


async def test_missing_realm_reference_stops_club_posting():
    http = FakeHTTP(Response(200, {'result': []}))
    api = client(http)
    with pytest.raises(ProtocolError):
        await api.club_story_feed()
    assert len(http.calls) == 1 and api.authorization.await_count == 1


def test_system_event_text_fallback_and_screenshot_priority():
    body = feed(); item = body['activityItems'][0]
    item.update(ugcCaption='', itemText='An automatic event', contentType='System', activityItemType='TextPost')
    item.pop('screenshotUri')
    item['contentImageUri'] = 'https://images-eds.xboxlive.com/game-cover.png'
    embed = render_feed(body)[0][0][1]
    assert embed.title == 'Realm Event' and embed.description == 'An automatic event'
    assert not embed.image.url
    item.update(activityItemType='Screenshot', contentType='Game',
                screenshotUri='https://images-eds.xboxlive.com/full.png',
                screenshotThumbnail='https://images-eds.xboxlive.com/thumb.png')
    item['authorInfo']['modernGamertagSuffix'] = '1234'
    embed = render_feed(body)[0][0][1]
    assert embed.image.url.endswith('/full.png') and embed.author.name == 'Builder#1234'


def test_legacy_xbox_cdn_image_is_upgraded_without_changing_query():
    assert image_url('http://images-eds.xboxlive.com/image/path?sig=sample') == 'https://images-eds.xboxlive.com/image/path?sig=sample'
    assert image_url('http://user:password@images-eds.xboxlive.com/image') is None
    assert image_url('http://images-eds.xboxlive.com.evil.invalid/image') is None


def test_merge_realm_event_replaces_generic_text_using_exact_reference():
    body = feed(); item = body['activityItems'][0]
    item.update(activityItemType='TextPost', contentType='System', ugcCaption='Generic fallback')
    item.pop('screenshotUri')
    item['authorInfo']['id'] = '123456'
    body['realmEvents'] = [{'clubsPostId': item['feedItemId'], 'eventName': 'FirstEnchantment',
        'timestamp': '2026-11-10T10:00:00Z', 'players': ['123456', '654321']}]
    entries, skipped, remaining = render_feed(body)
    embed = entries[0][1]
    assert len(entries) == 1 and skipped == remaining == 0
    assert embed.title == 'Discovered enchanting' and 'Generic fallback' not in embed.description
    assert embed.timestamp.day == 10
    assert embed.description == 'Builder and 1 other player discovered enchanting.'
    assert not embed.fields
    assert '123456' not in str(embed.to_dict()) and '654321' not in str(embed.to_dict())
    assert not embed.author.name  # Posting author is not assumed to be event actor.


def test_realm_only_event_is_included_and_screenshot_caption_retained():
    body = feed()
    body['realmEvents'] = [{'clubsPostId': 'other-reference', 'eventName': 'RealmCreated', 'players': []}]
    entries, skipped, remaining = render_feed(body)
    assert len(entries) == 2 and skipped == remaining == 0
    assert 'A new build' in entries[0][1].description and entries[0][1].image.url
    assert entries[1][1].title == 'Realm created'


def test_direct_screenshot_locator_preferred_to_legacy_image_proxy():
    body = feed(); body['activityItems'][0]['gameMediaContentLocators'] = [
        {'LocatorType': 'Download', 'Uri': 'https://screenshotscontent-d3001.media.xboxlive.com/direct.png'},
        {'LocatorType': 'Thumbnail_Large', 'Uri': 'https://screenshotscontent-t3001.media.xboxlive.com/thumb.png'}]
    assert render_feed(body)[0][0][1].image.url.endswith('/direct.png')
    body['activityItems'][0]['gameMediaContentLocators'][0]['Uri'] = 'https://evil.invalid/image'
    assert render_feed(body)[0][0][1].image.url.endswith('/thumb.png')


def test_large_new_member_reference_list_does_not_claim_all_joined():
    body = feed(); body['realmEvents'] = [{'clubsPostId': 'private-id', 'eventName': 'NewMember',
        'players': [str(i) for i in range(14)]}]
    embed = render_feed(body)[0][0][1]
    assert embed.description == '14 players joined the Realm.'
    assert not embed.fields
    assert 'Players referenced' not in str(embed.to_dict())


def test_resolved_event_names_and_group_join_wording():
    body = feed()
    body['realmEvents'] = [{'clubsPostId': 'private-id', 'eventName': 'NewMember',
                            'players': [str(i) for i in range(1, 15)]}]
    body['playerNames'] = {str(i): f'Sailor{i}' for i in range(1, 15)}
    embed = render_feed(body)[0][0][1]
    assert embed.description == 'Sailor1, Sailor2, Sailor3, Sailor4, Sailor5 and 9 other players joined the Realm.'
    body['realmEvents'][0].update(eventName='FirstCraftedNetherite', players=['2'])
    assert render_feed(body)[0][0][1].description == 'Sailor2 upgraded to Netherite.'
    body['realmEvents'][0].update(eventName='FirstEnchantment', players=['2'])
    assert render_feed(body)[0][0][1].description == 'Sailor2 discovered enchanting.'


def test_pillager_captain_uses_event_participant_not_posting_author():
    body = feed()
    body['activityItems'][0].pop('screenshotUri')
    body['activityItems'][0]['authorInfo'].update(id='999')
    body['realmEvents'] = [{'clubsPostId': 'private-id',
                            'eventName': 'PillagerCaptainDefeated', 'players': ['123']}]
    body['playerNames'] = {'123': 'SyntheticSailor'}
    embed = render_feed(body)[0][0][1]
    assert embed.title == 'Pillager Captain defeated'
    assert embed.description == 'SyntheticSailor defeated a Pillager Captain.'
    assert embed.image.url == 'attachment://PillagerCaptainDefeated.png'
    assert 'Builder' not in embed.description
    body['playerNames'] = {}
    assert render_feed(body)[0][0][1].description == 'A player defeated a Pillager Captain.'


async def test_runtime_resolves_event_ids_with_existing_cache_and_keeps_feed_on_failure():
    body = dict(feed(), realmEvents=[{'players': ['123', '456', '123']}])
    rt = runtime(); rt.client.club_story_feed = AsyncMock(return_value=body)
    rt.names = NS(resolve=AsyncMock(return_value={'123': 'Sailor'}))
    result = await rt.club_story_feed()
    rt.names.resolve.assert_awaited_once_with({'123', '456'})
    assert result['playerNames'] == {'123': 'Sailor'}
    rt.names.resolve.side_effect = RuntimeError('canary-secret')
    assert await rt.club_story_feed() == body
    await rt.close()


@pytest.mark.parametrize('kind', sorted(EVENT_ARTWORK))
def test_all_bundled_event_artwork_opens_with_matching_attachment(kind):
    from utils.realms.stories_feed import artwork_file
    body = {'activityItems': [], 'realmEvents': [{'clubsPostId': 'event', 'eventName': kind}]}
    embed = render_feed(body)[0][0][1]
    assert embed.image.url == f'attachment://{kind}.png'
    attachment = artwork_file(embed)
    try:
        assert attachment.filename == f'{kind}.png'
        assert attachment.fp.read(8) == b'\x89PNG\r\n\x1a\n'
    finally:
        attachment.close()


@pytest.mark.parametrize('kind', ['UnknownEvent', '../../private', None])
def test_unknown_event_artwork_is_not_invented(kind):
    body = {'activityItems': [], 'realmEvents': [{'clubsPostId': 'event', 'eventName': kind}]}
    assert not render_feed(body)[0][0][1].image.url


async def test_event_attachment_sent_and_closed():
    ctx = context()
    body = {'activityItems': [], 'realmEvents': [{'clubsPostId': 'event', 'eventName': 'NewMember'}]}
    observed = []
    async def send(**kwargs):
        attachment = kwargs['file']
        assert not attachment.fp.closed
        assert kwargs['embed'].image.url == 'attachment://' + attachment.filename
        observed.append(attachment)
    ctx.channel.send.side_effect = send
    cog = RealmCommands(NS(settings=settings()), runtime=NS(club_story_feed=AsyncMock(return_value=body)))
    await RealmCommands.storiespost.callback(cog, ctx)
    assert len(observed) == 1 and observed[0].fp.closed
    assert len(cog._stories_sent) == 1


async def test_missing_attach_permission_prevents_partial_posting():
    ctx = context()
    ctx.channel.permissions_for = lambda member: NS(view_channel=True, send_messages=True, embed_links=True, attach_files=False)
    body = dict(feed(), realmEvents=[{'clubsPostId': 'event', 'eventName': 'RealmCreated'}])
    cog = RealmCommands(NS(settings=settings()), runtime=NS(club_story_feed=AsyncMock(return_value=body)))
    await RealmCommands.storiespost.callback(cog, ctx)
    ctx.channel.send.assert_not_awaited()
    assert 'Attach Files' in ctx.followup.send.call_args.args[0]


def test_missing_artwork_keeps_text(monkeypatch, tmp_path):
    import utils.realms.stories_feed as renderer
    monkeypatch.setattr(renderer, 'ARTWORK_DIR', tmp_path)
    body = {'activityItems': [], 'realmEvents': [{'clubsPostId': 'event', 'eventName': 'NewMember'}]}
    embed = render_feed(body)[0][0][1]
    assert embed.description == 'A player joined the Realm.'
    assert not embed.image.url


@pytest.mark.parametrize('kind,expected', [
    ('FirstDiamondFound', 'SyntheticSailor found a diamond.'),
    ('FirstConduit', 'SyntheticSailor now commands the sea.'),
    ('FirstEndPortal', 'SyntheticSailor traveled to the End?'),
    ('FirstPoweredBeacon', 'SyntheticSailor powered a Beacon!'),
    ('FirstEnderDragonDefeated', 'The Ender Dragon was defeated!'),
    ('FirstWitherDefeated', 'The Wither was defeated!'),
    ('NamedMob', 'SyntheticSailor has a new friend.'),
    ('NamedMobDies', 'A named mob met an untimely death.'),
    ('SlotSwitch', 'The Realm world changed.'),
])
def test_verified_event_wording_and_nonplayer_fallbacks(kind, expected):
    from utils.realms.stories_feed import realm_event_text
    event = {'eventName': kind, 'players': ['123'], 'metadata': 'private-canary'}
    assert realm_event_text(event, {'123': 'SyntheticSailor'})[1] == expected


@pytest.mark.parametrize('kind,expected', [
    ('DefeatEnderdragon', 'The Ender Dragon was defeated!... again.'),
    ('DefeatWither', 'The Wither was defeated!... again.'),
    ('DiamondEverything', 'Sailor1 and Sailor2 have full diamond sets.'),
    ('FirstDiamondFound', 'Sailor1 found a diamond.'),
])
def test_grouped_variants_and_single_actor_events(kind, expected):
    from utils.realms.stories_feed import realm_event_text
    assert realm_event_text({'eventName': kind, 'players': ['1', '2']},
                            {'1': 'Sailor1', '2': 'Sailor2'})[1] == expected


def test_all_verified_event_templates_render_without_placeholders():
    from utils.realms.stories_feed import EVENT_TEXT, realm_event_text
    kinds = [kind for kind in EVENT_TEXT if not kind.endswith('.grouped')]
    assert len(kinds) == 30
    for kind in kinds:
        for players in (None, [], ['1'], ['1', '2']):
            text = realm_event_text({'eventName': kind, 'players': players}, {'1': 'Sailor'})[1]
            assert '%1$s' not in text and '%2$s' not in text
            assert text != 'A Realm event was recorded.'
