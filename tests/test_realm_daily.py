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
        assert image.format == 'PNG' and image.width == 1280
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
