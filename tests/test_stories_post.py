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
    assert len(entries) == 1 and skipped == remaining == 0


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
    assert entries[0][1].title == 'Realm created'
    assert 'A new build' in entries[1][1].description and entries[1][1].image.url


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
    rt.names.resolve.assert_awaited_once_with(['123', '456'])
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


async def test_old_stories_command_uses_archive_and_separate_duplicate_scope():
    ctx = context()
    body = dict(feed(), sourceRealmId='77')
    api = NS(club_story_feed=AsyncMock(return_value=body))
    cog = RealmCommands(NS(settings=settings()), runtime=api)
    await RealmCommands.oldstoriespost.callback(cog, ctx)
    api.club_story_feed.assert_awaited_once_with(old_realm=True)
    assert 'OLD Coastal S10' in ctx.followup.send.call_args.args[0]
    await RealmCommands.storiespost.callback(cog, ctx)
    assert ctx.channel.send.await_count == 2
    await RealmCommands.oldstoriespost.callback(cog, ctx)
    assert ctx.channel.send.await_count == 2


async def test_old_stories_requires_op_team():
    ctx = interaction(roles=())
    api = NS(club_story_feed=AsyncMock())
    cog = RealmCommands(NS(settings=settings()), runtime=api)
    await RealmCommands.oldstoriespost.callback(cog, ctx)
    api.club_story_feed.assert_not_awaited()


async def test_archive_runtime_resolves_name_and_isolates_client(monkeypatch):
    from contextlib import asynccontextmanager
    from unittest.mock import Mock
    rt = runtime()
    rt.client.old_stories_realm_id = AsyncMock(return_value='77')
    rt.client.authorization = AsyncMock()
    rt.client.principal = object()
    original_config = rt.config
    @asynccontextmanager
    async def transport(**kwargs):
        assert kwargs == {'selected_realm_id': '77'}
        yield 'archive-transport'
    rt._transport_factory = transport
    archive = NS(club_story_feed=AsyncMock(return_value=feed()))
    factory = Mock(return_value=archive)
    monkeypatch.setattr('utils.integrations.realms.client.RealmsClient', factory)
    result = await rt.club_story_feed(old_realm=True)
    assert result['sourceRealmId'] == '77'
    args = factory.call_args.args
    assert args[0] == 'archive-transport' and args[2].selected_realm_id == '77'
    assert rt.config is original_config and rt.client is not archive
    assert rt._history_snapshot is None
    await rt.close()


@pytest.mark.parametrize('names', [[], ['Unrelated Realm'], ['OLD Coastal S10', 'old coastal s10']])
async def test_archive_missing_or_ambiguous_name_never_reads_feed(names):
    from utils.integrations.realms.errors import StoriesError
    response = {'servers': [{'id': i+70, 'name': name, 'state': 'UNINITIALIZED'}
                            for i, name in enumerate(names)]}
    http = FakeHTTP(Response(200, response))
    with pytest.raises(StoriesError) as error:
        await client(http).old_stories_realm_id()
    assert error.value.reason == ('realm_ambiguous' if len(names) == 2 else 'realm_missing')
    assert len(http.calls) == 1


async def test_archive_reads_every_cursor_page_with_encoded_same_club_url():
    from test_stories_probe import BODY, probe_urls
    http = FakeHTTP(Response(200, BODY),
                    Response(200, dict(feed(), contToken='opaque+/&cursor')),
                    Response(200, {'activityItems': [], 'contToken': 'last'}),
                    Response(200, {'activityItems': [dict(feed()['activityItems'][0], feedItemId='oldest')]}))
    result = await client(http).club_story_feed(all_pages=True)
    assert [item['feedItemId'] for item in result['activityItems']] == ['private-id', 'oldest']
    base = probe_urls(BODY)[1]
    assert http.calls[2][1] == base + '&contToken=opaque%2B%2F%26cursor'
    assert http.calls[3][1] == base + '&contToken=last'
    assert all(call[0] == 'GET' for call in http.calls)


async def test_repeated_archive_cursor_stops_before_publishing_incomplete_archive():
    from test_stories_probe import BODY
    http = FakeHTTP(Response(200, BODY), Response(200, dict(feed(), contToken='repeat')),
                    Response(200, dict(feed(), contToken='repeat')))
    with pytest.raises(ProtocolError):
        await client(http).club_story_feed(all_pages=True)
    assert len(http.calls) == 3


def test_archive_renderer_has_no_ten_or_thousand_item_limit_and_orders_oldest_first():
    body = {'activityItems': [dict(feed()['activityItems'][0], feedItemId=str(i), date=None)
                              for i in range(1105)]}
    entries, skipped, remaining = render_feed(body, limit=None)
    assert len(entries) == 1105 and skipped == remaining == 0
    assert entries[0][0] == '1104' and entries[-1][0] == '0'


def test_both_commands_order_dated_events_and_screenshots_chronologically():
    body = feed()
    body['activityItems'].append(dict(body['activityItems'][0], feedItemId='older', date='2026-11-01T12:00:00Z'))
    body['realmEvents'] = [{'clubsPostId': 'event', 'eventName': 'RealmCreated', 'timestamp': '2026-10-01T00:00:00Z'}]
    for limit in (10, None):
        assert [key for key, _ in render_feed(body, limit=limit)[0]] == ['event', 'older', 'private-id']


async def test_archive_posts_past_session_guard_and_ten_item_limit():
    ctx = context()
    body = {'sourceRealmId': '77', 'activityItems': [dict(feed()['activityItems'][0], feedItemId=str(i)) for i in range(12)]}
    cog = RealmCommands(NS(settings=settings()), runtime=NS(club_story_feed=AsyncMock(return_value=body)))
    cog._stories_sent = {(202, 303, ('old', '77'), 'earlier-' + str(i)) for i in range(1000)}
    await RealmCommands.oldstoriespost.callback(cog, ctx)
    assert ctx.channel.send.await_count == 12
    assert '10-item limit' not in ctx.followup.send.call_args.args[0]


async def test_archive_lookup_ignores_uninitialized_slots_and_minecraft_name_formatting():
    body = {'servers': [{'id': 99, 'name': None, 'state': 'UNINITIALIZED'},
                        {'id': 77, 'name': '  \u00a7aOld \u00a7lCoastal S10\u00a7r ', 'state': 'CLOSED'}]}
    http = FakeHTTP(Response(200, body))
    assert await client(http).old_stories_realm_id() == '77'
    assert len(http.calls) == 1


@pytest.mark.parametrize('reason', ['realm_missing', 'realm_ambiguous', 'realm_list',
                                  'realm_feed', 'club_reference', 'club_page',
                                  'cursor_repeat', 'cursor_invalid', 'archive_fetch'])
async def test_archive_error_reports_fixed_reason_and_never_posts(reason):
    from utils.integrations.realms.errors import StoriesError
    ctx = context()
    api = NS(club_story_feed=AsyncMock(side_effect=StoriesError(reason)))
    cog = RealmCommands(NS(settings=settings()), runtime=api)
    await RealmCommands.oldstoriespost.callback(cog, ctx)
    assert reason in ctx.followup.send.call_args.args[0]
    assert ctx.followup.send.call_args.kwargs['ephemeral']
    ctx.channel.send.assert_not_awaited()


@pytest.mark.parametrize('date,included', [
    ('2026-10-31T04:59:59Z', False),
    ('2026-10-31T05:00:00Z', True),
    ('2026-11-01T12:00:00Z', True),
    ('2026-11-11T12:00:00Z', True),
    ('2026-11-11T12:00:01Z', False),
    (None, False), ('invalid', False),
])
def test_archive_date_window_uses_chicago_midnight_and_excludes_undated_or_future(date, included):
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo
    body = feed()
    body['activityItems'][0]['date'] = date
    entries, skipped, remaining = render_feed(body, limit=None,
        since=datetime(2026, 10, 31, tzinfo=ZoneInfo('America/Chicago')),
        until=datetime(2026, 11, 11, 12, tzinfo=timezone.utc))
    assert len(entries) == int(included)
    assert skipped == int(not included) and remaining == 0


def test_archive_date_filter_uses_event_timestamp_over_club_post_date():
    from datetime import datetime, timezone
    body = feed()
    body['realmEvents'] = [{'clubsPostId': 'private-id', 'eventName': 'NewMember',
                            'timestamp': '2026-10-01T00:00:00Z'}]
    assert not render_feed(body, limit=None, since=datetime(2026, 10, 31, 5, tzinfo=timezone.utc))[0]


@pytest.mark.parametrize('terminal', ['0', 0])
async def test_archive_zero_cursor_completes_without_requesting_zero_page(terminal):
    from test_stories_probe import BODY, probe_urls
    http = FakeHTTP(Response(200, BODY),
                    Response(200, dict(feed(), contToken='older')),
                    Response(200, {'activityItems': [dict(feed()['activityItems'][0], feedItemId='oldest')],
                                   'contToken': terminal}))
    result = await client(http).club_story_feed(all_pages=True)
    assert [item['feedItemId'] for item in result['activityItems']] == ['private-id', 'oldest']
    assert len(http.calls) == 3
    assert http.calls[-1][1] == probe_urls(BODY)[1] + '&contToken=older'


async def test_archive_empty_last_page_with_zero_cursor_returns_collected_stories():
    from test_stories_probe import BODY
    http = FakeHTTP(Response(200, BODY), Response(200, dict(feed(), contToken='last')),
                    Response(200, {'activityItems': [], 'numItems': 0, 'contToken': '0'}))
    result = await client(http).club_story_feed(all_pages=True)
    assert len(result['activityItems']) == 1
    assert len(http.calls) == 3


async def test_archive_first_page_zero_cursor_still_keeps_posts():
    from test_stories_probe import BODY
    http = FakeHTTP(Response(200, BODY), Response(200, dict(feed(), contToken='0')))
    result = await client(http).club_story_feed(all_pages=True)
    assert len(result['activityItems']) == 1 and len(http.calls) == 2


async def test_old_realm_debug_captures_feed_without_publishing_stories():
    import json
    ctx = context()
    body = dict(feed(), sourceRealmId='77', contToken='0')
    body['activityItems'][0].update(numLikes=2, hasLiked=True)
    api = NS(club_story_feed=AsyncMock(return_value=body), stories_debug=AsyncMock())
    cog = RealmCommands(NS(settings=settings()), runtime=api)
    await RealmCommands.storiesdebug.callback(cog, ctx, old_realm=True)
    api.club_story_feed.assert_awaited_once_with(old_realm=True)
    api.stories_debug.assert_not_awaited()
    ctx.channel.send.assert_not_awaited()
    kwargs = ctx.followup.send.call_args.kwargs
    assert kwargs['ephemeral']
    attachment = kwargs['file']
    try:
        report = json.load(attachment.fp)
        assert report['club_feed']['body']['activityItems'][0]['numLikes'] == 2
        assert report['club_feed']['body']['activityItems'][0]['hasLiked'] is True
        assert report['source'] == 'old_realm'
    finally:
        attachment.close()


async def test_old_realm_debug_checks_role_before_io():
    ctx = interaction(roles=())
    api = NS(club_story_feed=AsyncMock(), stories_debug=AsyncMock())
    cog = RealmCommands(NS(settings=settings()), runtime=api)
    await RealmCommands.storiesdebug.callback(cog, ctx, old_realm=True)
    api.club_story_feed.assert_not_awaited()
    api.stories_debug.assert_not_awaited()


@pytest.mark.parametrize('likes,comments,expected', [(3, 2, '\u2764\ufe0f 3 \u00b7 \U0001f4ac 2'),
    (None, None, '\u2764\ufe0f 0 \u00b7 \U0001f4ac 0'), (True, -1, '\u2764\ufe0f 0 \u00b7 \U0001f4ac 0')])
def test_story_counter_footers(likes, comments, expected):
    body = feed()
    body['activityItems'][0].update(numLikes=likes, numComments=comments)
    assert render_feed(body)[0][0][1].footer.text == expected


def test_duplicate_minecraft_event_reference_combines_counts_and_matches_metadata_alias():
    body = feed()
    event_id = '12345678-1234-1234-1234-123456789abc'
    first = body['activityItems'][0]
    first.update(postContentLocators=[{'locatorType': 'MinecraftContent', 'locatorUri': event_id}], numLikes=3)
    body['activityItems'].append(dict(first, feedItemId='second-id', numLikes=1, numComments=2))
    body['realmEvents'] = [{'id': event_id, 'clubsPostId': 'second-id', 'eventName': 'NewMember', 'players': ['1']}]
    body['playerNames'] = {'1': 'Sailor'}
    entries, _, _ = render_feed(body)
    assert len(entries) == 1 and entries[0][0] == 'event:' + event_id
    assert entries[0][1].description == 'Sailor joined the Realm.'
    assert entries[0][1].footer.text == '\u2764\ufe0f 3 \u00b7 \U0001f4ac 2'


async def test_footer_updates_original_message_after_restart_and_handles_removed_hearts():
    from unittest.mock import Mock
    data = {}
    store = NS(load_story_deliveries=Mock(side_effect=lambda: dict(data)),
               save_story_deliveries=Mock(side_effect=lambda entries: data.update(entries)))
    ctx = context()
    body = feed()
    body['activityItems'][0].update(numLikes=1, numComments=1)
    api = NS(club_story_feed=AsyncMock(return_value=body), store=store)
    bot = NS(settings=settings(), user=NS(id=999))
    ctx.channel.send.return_value = NS(id=123)
    cog = RealmCommands(bot, runtime=api)
    await RealmCommands.storiespost.callback(cog, ctx)
    embed = ctx.channel.send.call_args.kwargs['embed'].copy()
    embed.set_image(url='https://cdn.discordapp.com/attachments/existing.png')
    original = NS(id=123, author=NS(id=999), embeds=[embed], edit=AsyncMock())
    ctx.channel.fetch_message = AsyncMock(return_value=original)
    body['activityItems'][0].pop('numLikes')  # Omitted zero after removing a heart.
    cog = RealmCommands(bot, runtime=api)  # New process/cog with persisted mapping.
    await RealmCommands.storiespost.callback(cog, ctx)
    assert ctx.channel.send.await_count == 1
    ctx.channel.fetch_message.assert_awaited_once_with(123)
    edited = original.edit.call_args.kwargs['embed']
    assert edited.footer.text == '\u2764\ufe0f 0 \u00b7 \U0001f4ac 1'
    assert edited.image.url == 'https://cdn.discordapp.com/attachments/existing.png'
    await RealmCommands.storiespost.callback(cog, ctx)
    assert original.edit.await_count == 1


def test_named_mob_uses_verified_metatext_and_escapes_it():
    from utils.realms.stories_feed import realm_event_text
    event = {'eventName': 'NamedMob', 'players': ['1'], 'metadata': {'metatext': 'Shadow'}}
    assert realm_event_text(event, {'1': 'Sailor'})[1] == 'Sailor has a new friend, Shadow.'
    event['metadata']['metatext'] = '@everyone **pet**'
    text = realm_event_text(event, {'1': 'Sailor'})[1]
    assert '@everyone' not in text and '\\*' in text
    event['metadata'] = {'unverified': 'private-canary'}
    assert realm_event_text(event, {'1': 'Sailor'})[1] == 'Sailor has a new friend.'



def test_archive_restore_is_realm_scoped_and_does_not_mutate_api_data(tmp_path):
    import copy
    import json
    from utils.realms.stories_archive import restore_archive
    event_id = '12345678-1234-1234-1234-123456789abc'
    record = {'version': 1, 'realm_id': '77', 'events': [{'event_id': event_id,
              'event_name': 'NewMember', 'participants': [f'Sailor{i}' for i in range(9)], 'pet_name': None}]}
    path = tmp_path / 'archive.json'
    path.write_text(json.dumps(record))
    body = dict(feed(), sourceRealmId='77')
    body['activityItems'][0]['postContentLocators'] = [{'locatorType': 'MinecraftContent', 'locatorUri': event_id}]
    original = copy.deepcopy(body)
    result = restore_archive(body, path=path)
    assert body == original
    embed = render_feed(result)[0][0][1]
    assert all(f'Sailor{i}' in embed.description for i in range(9))
    assert 'other players' not in embed.description
    body['sourceRealmId'] = '42'
    assert restore_archive(body, path=path) is body


def test_archive_reconstruction_data_has_26_distinct_verified_event_records():
    import json
    from utils.realms.stories_archive import ARCHIVE
    data = json.loads(ARCHIVE.read_text(encoding='utf8'))
    records = data['events']
    assert len(records) == len({r['event_id'] for r in records}) == 26
    assert sorted(len(r['participants']) for r in records if r['event_name'] == 'NewMember') == [1, 1, 1, 2, 5, 9]
    assert len([r for r in records if r.get('pet_name')]) == 4


async def test_saved_embed_text_refreshes_when_footer_is_unchanged():
    from utils.realms.story_deliveries import StoryDeliveries
    ctx = context()
    api = NS(club_story_feed=AsyncMock(return_value=feed()))
    bot = NS(settings=settings(), user=NS(id=999))
    cog = RealmCommands(bot, runtime=api)
    cog._story_deliveries = StoryDeliveries(None)
    await cog._story_deliveries.load()
    key = StoryDeliveries.key(202,303,settings()['realms']['selected_realm_id'],'private-id')
    desired = render_feed(feed())[0][0][1]
    await cog._story_deliveries.save(key,123,desired.footer.text,signature='previous-render')
    original = NS(id=123,author=NS(id=999),embeds=[desired.copy()],edit=AsyncMock())
    ctx.channel.fetch_message=AsyncMock(return_value=original)
    await RealmCommands.storiespost.callback(cog,ctx)
    original.edit.assert_awaited_once()
    ctx.channel.send.assert_not_awaited()


@pytest.mark.parametrize('changed', [False, True])
async def test_deleted_tracked_story_is_recreated_and_checkpoint_replaced(changed):
    import discord
    from utils.realms.story_deliveries import StoryDeliveries
    ctx = context()
    body = feed()
    api = NS(club_story_feed=AsyncMock(return_value=body))
    bot = NS(settings=settings(), user=NS(id=999))
    cog = RealmCommands(bot, runtime=api)
    ledger = StoryDeliveries(None)
    await ledger.load()
    cog._story_deliveries = ledger
    source = settings()['realms']['selected_realm_id']
    key = ledger.key(202,303,source,'private-id')
    embed = render_feed(body)[0][0][1]
    await ledger.save(key,123,embed.footer.text,signature='old' if changed else ledger.signature(embed))
    cog._stories_sent.add((202,303,source,'private-id'))
    ctx.channel.fetch_message = AsyncMock(side_effect=discord.NotFound(NS(status=404,reason='Not Found'),
        {'code':10008,'message':'Unknown Message'}))
    ctx.channel.send.return_value = NS(id=456)
    await RealmCommands.storiespost.callback(cog,ctx)
    ctx.channel.send.assert_awaited_once()
    assert ledger.entries[key]['message_id'] == 456
    original=NS(id=456,author=NS(id=999),embeds=[embed],edit=AsyncMock())
    ctx.channel.fetch_message.side_effect = None
    ctx.channel.fetch_message.return_value = original
    await RealmCommands.storiespost.callback(cog,ctx)
    assert ctx.channel.send.await_count == 1
    original.edit.assert_not_awaited()


@pytest.mark.parametrize('status,code', [(403,50001),(404,10003),(500,0)])
async def test_fetch_permission_channel_or_server_failure_never_recreates_story(status,code):
    import discord
    from utils.realms.story_deliveries import StoryDeliveries
    ctx=context()
    cog=RealmCommands(NS(settings=settings(),user=NS(id=999)),runtime=NS(club_story_feed=AsyncMock(return_value=feed())))
    ledger=StoryDeliveries(None)
    await ledger.load()
    cog._story_deliveries=ledger
    key=ledger.key(202,303,settings()['realms']['selected_realm_id'],'private-id')
    await ledger.save(key,123,'previous')
    error_type=discord.Forbidden if status==403 else discord.NotFound if status==404 else discord.HTTPException
    ctx.channel.fetch_message=AsyncMock(side_effect=error_type(NS(status=status,reason='failed'),{'code':code,'message':'private-canary'}))
    await RealmCommands.storiespost.callback(cog,ctx)
    ctx.channel.send.assert_not_awaited()
    assert ledger.entries[key]['message_id']==123
    report=ctx.followup.send.call_args.args[0]
    assert 'fetch_original_message' in report and 'private-canary' not in report
