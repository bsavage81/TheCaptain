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
        png = render(day, groups, {})
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
            message = NS(id=100, author=NS(id=99), embeds=[kwargs['embed']], edit=AsyncMock())
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
