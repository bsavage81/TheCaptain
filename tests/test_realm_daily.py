from datetime import date, timedelta
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
import io

import discord
import pytest
from peewee import SqliteDatabase
from migrations.realm_activity import migrate as activity_migrate
from migrations.realm_daily import migrate
from utils.realms.daily_models import DailyReport
from utils.realms.daily import DailyController
from utils.realms.daily_timeline import aggregate, window, render, fallback


def test_clipping_union_and_dst():
    for day, hours in [(date(2026, 3, 8), 23), (date(2026, 11, 1), 25), (date(2026, 11, 5), 24)]:
        lo, hi = window(day)
        assert (hi-lo).total_seconds() == hours*3600
        groups, count, seconds = aggregate([
            ('a', lo-timedelta(hours=1), lo+timedelta(hours=2)),
            ('a', lo+timedelta(hours=1), lo+timedelta(hours=3)),
            ('b', hi-timedelta(hours=1), hi+timedelta(hours=1)),
            ('c', hi, hi+timedelta(hours=1))], day)
        assert count == 3 and len(groups) == 2 and seconds == 4*3600
        assert groups['a'] == [(lo, lo+timedelta(hours=3))]


def test_renderer_smoke():
    from PIL import Image
    day = date(2026, 11, 1)
    lo, hi = window(day)
    for groups in ({}, {'1234567890123456': [(lo, hi)]}):
        png = render(day, groups, {}, lo+timedelta(hours=12))
        image = Image.open(io.BytesIO(png))
        assert image.format == 'PNG' and image.width == 1200
        image.verify()
    assert '1234567890123456' not in fallback('1234567890123456')


@pytest.mark.asyncio
async def test_delivery_restarts_and_uncertain_send(tmp_path, monkeypatch):
    backend = SqliteDatabase(tmp_path / 'daily.sqlite')
    activity_migrate(backend, apply=True, backup_verified=True)
    migrate(backend, apply=True, backup_verified=True)
    assert migrate(backend)['missing_tables'] == []
    messages = []
    class Channel:
        guild = NS(id=1)
        async def send(self, **kwargs):
            assert 'embed' not in kwargs and 'content' not in kwargs
            message = NS(id=100, author=NS(id=99), embeds=[],
                         attachments=[NS(filename=kwargs['file'].filename)], edit=AsyncMock())
            messages.append(message)
            if len(messages) == 1:
                raise TimeoutError('accepted but response lost')
            return message
        async def history(self, **kwargs):
            for message in messages:
                yield message
        async def fetch_message(self, identity):
            return next(m for m in messages if m.id == identity)
    channel = Channel()
    bot = NS(settings={'Coastal': 1, 'realm_daily': {'enabled': True, 'channel_id': 2}},
             user=NS(id=99), get_channel=lambda _: channel)
    runtime = NS(config=NS(selected_realm_id='3'))
    day = date(2026, 11, 5)
    async def report(_):
        return discord.Embed(title='Observed Realm Activity'), 'abc', {}, {}
    monkeypatch.setattr('utils.realms.daily.render', lambda *args: b'png')
    first = DailyController(bot, runtime)
    first.report = report
    with pytest.raises(TimeoutError):
        await first.publish(day)
    second = DailyController(bot, runtime)
    second.report = report
    assert not await second.publish(day)  # uncertain outcome settling period
    with backend.connection_context():
        DailyReport.update(pending_since=DailyReport.get().pending_since-timedelta(minutes=6)).execute()
    assert await second.publish(day)
    assert await second.publish(day)
    with backend.connection_context():
        row = DailyReport.get()
        assert row.message == 100 and row.signature == 'abc'
        assert DailyReport.select().count() == 1
    assert len(messages) == 1
    assert messages[0].edit.await_count == 1
    assert messages[0].edit.call_args.kwargs['embeds'] == []
    assert messages[0].edit.call_args.kwargs['content'] is None


def test_display_order_names_colors_and_ticks():
    from utils.realms.daily_timeline import player_color, ordered_players, row_names, axis_ticks
    day = date(2026, 11, 5)
    lo, _ = window(day)
    groups = {'b': [(lo, lo+timedelta(hours=1))], 'a': [(lo, lo+timedelta(hours=3))]}
    assert ordered_players(groups) == ['a', 'b']
    assert row_names('a', {'a': {'discord': 'Savage', 'gamertag': 'TheCaptain4322'}}) == ('Savage', 'TheCaptain4322')
    assert row_names('a', {'a': {'discord': 'CAPTAIN', 'gamertag': 'Captain'}}) == ('Captain', None)
    assert row_names('a', {'a': {'gamertag': 'Captain'}}) == ('Captain', None)
    assert player_color('123456') == '#80aefa'
    for d, first_gap in [(date(2026, 3, 8), 5), (date(2026, 11, 1), 7), (day, 6)]:
        ticks = axis_ticks(d)
        assert (ticks[1][0]-ticks[0][0]).total_seconds() == first_gap*3600
        assert ticks[0][0] == window(d)[0] and ticks[-1][0] == window(d)[1]


@pytest.mark.asyncio
async def test_preview_disabled_reads_stored_data(tmp_path):
    from utils.realms.daily import DailyUnavailable
    backend = SqliteDatabase(tmp_path / 'preview.sqlite')
    activity_migrate(backend, apply=True, backup_verified=True)
    migrate(backend, apply=True, backup_verified=True)
    bot = NS(settings={'Coastal': 1}, get_guild=lambda _: None)
    runtime = NS(config=NS(selected_realm_id='3'), names=None)
    controller = DailyController(bot, runtime)
    controller.collect = AsyncMock(side_effect=AssertionError('Preview must not collect'))
    embed, png = await controller.refresh(preview=True)
    assert png.startswith(b'\x89PNG') and embed.fields[0].value == '0'
    controller.collect.assert_not_awaited()
    with pytest.raises(DailyUnavailable, match='disabled'):
        await controller.refresh()
    with backend.connection_context():
        DailyReport.drop_table()
    with pytest.raises(DailyUnavailable, match='tables are missing'):
        await controller.refresh(preview=True)


def test_database_startup_creates_daily_tables_and_preserves_records(tmp_path):
    from utils.database.__database import db, BotData, Administrators, initialize_database
    from utils.realms.daily_models import DailyCollection
    backend = SqliteDatabase(tmp_path / 'startup.sqlite')
    db.initialize(backend)
    with backend.connection_context():
        backend.create_tables([BotData, Administrators])
        BotData.create(id=1, prefix='!')
    settings = {'owner_ids': [123]}
    initialize_database(settings, backend=backend)
    with backend.connection_context():
        DailyCollection.create(realm='35868436', outcome='available')
        report = DailyReport.create(guild=1, channel=2, realm='35868436', day=date(2026, 11, 11), message=456)
        identity = report.id
    initialize_database(settings, backend=backend)
    with backend.connection_context():
        assert DailyCollection.get().outcome == 'available'
        assert DailyReport.get_by_id(identity).message == 456
        assert DailyReport.select().count() == 1
        assert BotData.get_by_id(1).prefix == '!'


def test_attachment_and_legacy_report_markers():
    from utils.realms.daily import matches_report
    marker = 'realm-daily:abc'
    legacy = discord.Embed().set_footer(text=marker)
    assert matches_report(NS(embeds=[legacy], attachments=[]), marker)
    assert matches_report(NS(embeds=[], attachments=[NS(filename='realm-daily-abc.png')]), marker)
    assert not matches_report(NS(embeds=[], attachments=[NS(filename='realm-daily-other.png')]), marker)


@pytest.mark.asyncio
async def test_current_day_rollover_finalizes_previous_message(monkeypatch):
    from datetime import datetime
    from utils.realms.daily import ZONE
    import utils.realms.daily as module
    class FixedTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 11, 12, 0, 5, tzinfo=ZONE).astimezone(tz)
    monkeypatch.setattr(module, 'datetime', FixedTime)
    monkeypatch.setattr(module, 'database', AsyncMock(return_value=True))
    bot = NS(settings={'Coastal': 1, 'realms': {'enabled': True}, 'realm_history_enabled': True,
                       'realm_daily': {'enabled': True, 'channel_id': 2}})
    controller = DailyController(bot, NS(config=NS(selected_realm_id='3')))
    controller.runtime.observe = AsyncMock()
    controller.collect = AsyncMock()
    controller.publish = AsyncMock(return_value=True)
    await controller.scheduled_refresh()
    assert [call.args[0] for call in controller.publish.call_args_list] == [date(2026, 11, 11), date(2026, 11, 12)]
    await controller.scheduled_refresh()
    assert controller.publish.await_count == 2
    class LaterTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 11, 12, 0, 10, tzinfo=ZONE).astimezone(tz)
    monkeypatch.setattr(module, 'datetime', LaterTime)
    await controller.scheduled_refresh()
    assert controller.publish.await_count == 3
    assert controller.publish.call_args.args[0] == date(2026, 11, 12)



@pytest.mark.asyncio
async def test_history_without_observations_is_not_published(tmp_path):
    from utils.realms.daily import DailyUnavailable
    backend = SqliteDatabase(tmp_path / 'history-empty.sqlite')
    activity_migrate(backend, apply=True, backup_verified=True)
    migrate(backend, apply=True, backup_verified=True)
    controller = DailyController(NS(settings={'Coastal': 1}, get_guild=lambda _: None),
                                 NS(config=NS(selected_realm_id='3'), names=None))
    with pytest.raises(DailyUnavailable, match='No stored activity'):
        await controller.refresh(preview=True, day=date(2026, 10, 31))


def test_dual_realm_import_keeps_hourly_intervals_separate_and_deduplicated(tmp_path):
    from datetime import datetime, timezone
    from utils.players.activity import ingest
    from utils.players.activity_models import RealmActivity
    from utils.integrations.realms.stories import parse_stories
    from utils.integrations.realms.models import Snapshot
    backend = SqliteDatabase(tmp_path / 'dual.sqlite')
    activity_migrate(backend, apply=True, backup_verified=True)
    now = datetime(2026, 11, 12, tzinfo=timezone.utc)
    start = int(datetime(2026, 10, 31, tzinfo=timezone.utc).timestamp())
    snapshot = Snapshot(parse_stories({'result': {'activity': {'123456': [{'s': start, 'e': start+3600}]}}}, now), now)
    with backend.connection_context():
        for realm in ('35868436', '11451943'):
            assert ingest(snapshot, realm)['created'] == 1
            assert ingest(snapshot, realm)['existing'] == 1
        assert RealmActivity.select().count() == 2
        assert {r.realm_id for r in RealmActivity.select()} == {'35868436', '11451943'}
        assert all((r.end-r.start).total_seconds() == 3600 for r in RealmActivity.select())


def test_presence_overrides_hourly_history_without_bridging_outages():
    from utils.realms.presence import prefer_presence
    from datetime import datetime
    start = datetime(2026, 11, 12, 12)
    at = lambda seconds: start+timedelta(seconds=seconds)
    stories = [('a', start, at(3600))]
    samples = [(at(0), []), (at(15), ['a']), (at(30), ['a']), (at(45), []),
               (at(180), ['a']), (at(195), [])]
    rows = prefer_presence(stories, samples)
    groups, _, seconds = aggregate(rows, date(2026, 11, 12))
    # Primary 15..45 and 180..195; fallback only outside observed windows.
    spans = groups['a']
    assert spans[0] == (at(15).replace(tzinfo=window(date(2026,11,12))[0].tzinfo),
                        at(3600).replace(tzinfo=window(date(2026,11,12))[0].tzinfo))
    assert seconds == 3585
    primary_only = prefer_presence([], samples)
    assert sum((b-a).total_seconds() for _, a, b in primary_only) == 45


def test_presence_samples_persist_empty_observations_and_deduplicate(tmp_path):
    from datetime import datetime, timezone
    from utils.realms.presence import PresenceSample, save_sample
    from utils.database.__database import db
    from utils.realms.runtime import Observation
    from utils.integrations.realms.models import Snapshot
    backend = SqliteDatabase(tmp_path / 'presence.sqlite')
    db.initialize(backend)
    with backend.connection_context():
        backend.create_tables([PresenceSample])
        snapshot = Snapshot(NS(players=()), datetime(2026,11,12,12,0,15,tzinfo=timezone.utc))
        view = Observation(activity=snapshot, activity_available=True)
        save_sample(view, '3')
        save_sample(view, '3')
        assert PresenceSample.select().count() == 1
        assert PresenceSample.get().online == '[]'
        assert PresenceSample.get().observed.second == 15
        save_sample(Observation(activity=snapshot, activity_available=False), '3')
        assert PresenceSample.select().count() == 1


@pytest.mark.parametrize('seconds, expected', [
    (0, '0m'), (0.1, '<1m'), (15, '<1m'), (29, '<1m'), (59, '<1m'),
    (60, '1m'), (89, '1m'), (90, '2m'), (119, '2m'),
    (3569, '59m'), (3570, '1h 00m'), (3660, '1h 01m')])
def test_display_duration_keeps_subminute_visits_and_rounds_longer_totals(seconds, expected):
    from utils.realms.daily_timeline import duration
    assert duration(seconds) == expected


@pytest.mark.asyncio
async def test_history_combines_realms_without_double_counting(tmp_path):
    from datetime import datetime, timezone
    from utils.players.activity_models import RealmActivity
    from utils.realms.presence import PresenceSample
    backend = SqliteDatabase(tmp_path / 'combined.sqlite')
    activity_migrate(backend, apply=True, backup_verified=True)
    migrate(backend, apply=True, backup_verified=True)
    day = date(2026, 10, 31)
    lo = window(day)[0].replace(tzinfo=None)
    with backend.connection_context():
        backend.create_tables([PresenceSample])
        for index, realm, xuid, start, end in [(1,'35868436','123456',0,2),
                (2,'11451943','123456',1,3), (3,'11451943','654321',4,5)]:
            RealmActivity.create(key=str(index), realm_id=realm, xuid=xuid,
                raw_start='0', raw_end='1', start=lo+timedelta(hours=start),
                end=lo+timedelta(hours=end), status='observed')
        # Empty current-Realm polling must not erase old-Realm activity.
        PresenceSample.create(realm='35868436', observed=lo+timedelta(hours=4), online='[]')
        PresenceSample.create(realm='35868436', observed=lo+timedelta(hours=4,seconds=15), online='[]')
    controller = DailyController(NS(settings={'Coastal':1}, get_guild=lambda _: None),
        NS(config=NS(selected_realm_id='35868436'), names=None))
    embed, _, groups, _ = await controller.report(day)
    assert len(groups) == 2
    assert sum((b-a).total_seconds() for spans in groups.values() for a,b in spans) == 4*3600
    assert embed.fields[0].value == '2'
    assert controller.report_realms(datetime.now(timezone.utc).astimezone(__import__('utils.realms.daily',fromlist=['ZONE']).ZONE).date()) == ('35868436', '11451943')


def test_future_rounded_interval_is_revalidated_on_later_import(tmp_path):
    from datetime import datetime, timezone
    from utils.players.activity import ingest
    from utils.players.activity_models import RealmActivity
    from utils.integrations.realms.stories import parse_stories
    from utils.integrations.realms.models import Snapshot
    backend = SqliteDatabase(tmp_path / 'revalidation.sqlite')
    activity_migrate(backend, apply=True, backup_verified=True)
    start = datetime(2026,11,12,14,tzinfo=timezone.utc)
    end = start+timedelta(hours=2)
    body = {'result': {'activity': {'123456': [{'s':int(start.timestamp()),'e':int(end.timestamp())}]}}}
    with backend.connection_context():
        first = start+timedelta(minutes=90)
        assert ingest(Snapshot(parse_stories(body,first),first),'35868436')['quarantined'] == 1
        later = end+timedelta(minutes=1)
        result = ingest(Snapshot(parse_stories(body,later),later),'35868436')
        assert result['created'] == 0 and result['existing'] == 1 and result['quarantined'] == 0
        row = RealmActivity.get()
        assert row.status == 'observed' and row.reason == ''
        assert row.end == end.replace(tzinfo=None)
        assert RealmActivity.select().count() == 1


def test_future_interval_verification_uses_fresh_presence():
    from datetime import datetime, timezone
    from utils.realms.presence import verify_future_intervals
    from utils.realms.runtime import Observation
    from utils.integrations.realms.models import Snapshot
    now = datetime(2026,11,12,17,8,tzinfo=timezone.utc)
    history = Snapshot((NS(xuid='123456',reason='future_timestamp'),
                        NS(xuid='654321',reason='future_timestamp')),now)
    activity = Snapshot(NS(players=(NS(xuid='123456',online=True),NS(xuid='654321',online=False))),now)
    view = Observation(activity=activity,activity_available=True)
    assert verify_future_intervals(history,view,now) == {'123456':'online','654321':'offline'}
    assert set(verify_future_intervals(history,view,now+timedelta(seconds=46)).values()) == {'unknown'}
    assert set(verify_future_intervals(history,Observation(activity=activity),now).values()) == {'unknown'}


@pytest.mark.asyncio
async def test_deleted_daily_message_requires_manual_publish_and_recovers_uncertain_send(tmp_path, monkeypatch):
    from utils.realms.daily import DailyUnavailable
    backend = SqliteDatabase(tmp_path/'deleted-report.sqlite')
    activity_migrate(backend,apply=True,backup_verified=True)
    migrate(backend,apply=True,backup_verified=True)
    day=date(2026,10,31)
    with backend.connection_context():
        DailyReport.create(guild=1,channel=2,realm='3',day=day,message=42,signature='old')
    messages=[]
    class Channel:
        guild=NS(id=1)
        async def fetch_message(self, identity):
            if identity==42:
                raise discord.NotFound(NS(status=404,reason='Not Found'), {'code':10008,'message':'Unknown Message'})
            return next(m for m in messages if m.id==identity)
        async def send(self, **kwargs):
            message=NS(id=100,author=NS(id=99),embeds=[],
                attachments=[NS(filename=kwargs['file'].filename)],edit=AsyncMock())
            messages.append(message)
            raise TimeoutError('accepted but response lost')
        async def history(self, **kwargs):
            for message in messages:
                yield message
    channel=Channel()
    bot=NS(settings={'Coastal':1,'realm_daily':{'enabled':True,'channel_id':2}},
           user=NS(id=99),get_channel=lambda _:channel)
    controller=DailyController(bot,NS(config=NS(selected_realm_id='3')))
    controller.report=AsyncMock(return_value=(discord.Embed(), 'new', {}, {}))
    monkeypatch.setattr('utils.realms.daily.render',lambda *args:b'png')
    with pytest.raises(DailyUnavailable,match='original daily report message was deleted'):
        await controller.publish(day)
    with backend.connection_context():
        assert DailyReport.get().message==42 and DailyReport.get().lease is None
    assert not messages
    with pytest.raises(TimeoutError):
        await controller.publish(day,replace_missing=True)
    with backend.connection_context():
        row=DailyReport.get()
        assert row.message is None and row.pending_since is not None and row.lease is None
        DailyReport.update(pending_since=row.pending_since-timedelta(minutes=6)).execute()
    assert await controller.publish(day,replace_missing=True)
    assert await controller.publish(day)
    assert len(messages)==1
    with backend.connection_context():
        assert DailyReport.get().message==100 and DailyReport.get().signature=='new'
        assert DailyReport.get().pending_since is None


@pytest.mark.asyncio
@pytest.mark.parametrize('code',[10003,0])
async def test_other_not_found_errors_never_clear_message_or_republish(tmp_path, code):
    from utils.realms.daily import DailyUnavailable
    backend=SqliteDatabase(tmp_path/f'not-found-{code}.sqlite')
    activity_migrate(backend,apply=True,backup_verified=True)
    migrate(backend,apply=True,backup_verified=True)
    day=date(2026,10,31)
    with backend.connection_context():
        DailyReport.create(guild=1,channel=2,realm='3',day=day,message=42,signature='old')
    channel=NS(guild=NS(id=1),send=AsyncMock(),fetch_message=AsyncMock(side_effect=
        discord.NotFound(NS(status=404,reason='Not Found'),{'code':code,'message':'Not Found'})))
    bot=NS(settings={'Coastal':1,'realm_daily':{'enabled':True,'channel_id':2}},get_channel=lambda _:channel)
    controller=DailyController(bot,NS(config=NS(selected_realm_id='3')))
    with pytest.raises(DailyUnavailable,match='checkpoint was preserved'):
        await controller.publish(day,replace_missing=True)
    channel.send.assert_not_awaited()
    with backend.connection_context():
        assert DailyReport.get().message==42 and DailyReport.get().signature=='old'
        assert DailyReport.get().lease is None


@pytest.mark.asyncio
async def test_missing_report_channel_is_actionable_and_preserves_checkpoint(tmp_path):
    from utils.realms.daily import DailyUnavailable
    backend=SqliteDatabase(tmp_path/'missing-channel.sqlite')
    activity_migrate(backend,apply=True,backup_verified=True)
    migrate(backend,apply=True,backup_verified=True)
    bot=NS(settings={'Coastal':1,'realm_daily':{'enabled':True,'channel_id':2}},
        get_channel=lambda _:None,fetch_channel=AsyncMock(side_effect=
            discord.NotFound(NS(status=404,reason='Not Found'),{'code':10003,'message':'Unknown Channel'})))
    controller=DailyController(bot,NS(config=NS(selected_realm_id='3')))
    with pytest.raises(DailyUnavailable,match='configured daily report channel was not found'):
        await controller.publish(date(2026,10,31),replace_missing=True)
    with backend.connection_context():
        assert DailyReport.get().message is None and DailyReport.get().pending_since is None
        assert DailyReport.get().lease is None


@pytest.mark.asyncio
async def test_staff_publish_requests_deleted_message_recovery_but_preview_does_not():
    from test_realms_discord import settings, interaction
    from utils.realms.cog import RealmCommands
    day=date(2026,10,31)
    reports=NS(refresh=AsyncMock(return_value=True))
    cog=NS(bot=NS(settings=settings()),daily_reports=reports)
    await RealmCommands.daily_response(cog,interaction(),preview=False,day=day)
    reports.refresh.assert_awaited_once_with(preview=False,day=day,replace_missing=True)
    reports.refresh.reset_mock()
    reports.refresh.return_value=(discord.Embed(),b'png')
    await RealmCommands.daily_response(cog,interaction(),preview=True,day=day)
    reports.refresh.assert_awaited_once_with(preview=True,day=day,replace_missing=False)
