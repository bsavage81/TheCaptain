from datetime import datetime,timedelta
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
import io
import time
import pytest
from peewee import SqliteDatabase
from migrations.realm_activity import migrate
from utils.players.activity_models import RealmActivity
from utils.realms.leaderboard import rankings,page_bounds,render_page,LeaderboardController,LeaderboardView


def test_union_and_tie_order():
    start=datetime(2026,11,1)
    rows=[('b',start,start+timedelta(hours=2)),('b',start+timedelta(hours=1),start+timedelta(hours=3)),
          ('a',start,start+timedelta(hours=3)),('a',start,start+timedelta(hours=3)),
          ('c',start+timedelta(hours=5),start+timedelta(hours=6))]
    assert rankings(rows,start+timedelta(hours=4))==[('a',10800),('b',10800)]
    assert page_bounds(9,21)==(2,3)
    assert page_bounds(-1,0)==(0,1)


def test_renderer_pages():
    from PIL import Image
    data=([(str(i),3600*(21-i)) for i in range(21)],{'0':{'discord':'Captain','gamertag':'TheCaptain4322'}},datetime(2026,11,12))
    for page in (0,2):
        png=render_page(data,page)
        image=Image.open(io.BytesIO(png))
        assert image.width==1200
        assert image.height==286+(10 if page==0 else 1)*76
        image.verify()
    Image.open(io.BytesIO(render_page(([],{},None),0))).verify()


@pytest.mark.asyncio
async def test_source_filter_and_pagination_lifecycle(tmp_path):
    backend=SqliteDatabase(tmp_path/'leaderboard.sqlite')
    migrate(backend,apply=True,backup_verified=True)
    start=datetime(2026,11,1)
    with backend.connection_context():
        for i,(realm,status) in enumerate([('35868436','observed'),('11451943','observed'),('35868436','quarantined')]):
            RealmActivity.create(key=str(i),realm_id=realm,xuid=str(123456+i),raw_start='1',raw_end='2',
                                 start=start,end=start+timedelta(hours=1),status=status)
    bot=NS(settings={'Coastal':1},get_guild=lambda _:None)
    controller=LeaderboardController(bot,NS(config=NS(selected_realm_id='35868436'),names=None,view=NS(activity=None)))
    data=await controller.load()
    assert data[0]==[('123456',1800),('123457',1800)]
    large=([(str(i),3600-i) for i in range(21)],{},data[2])
    view=LeaderboardView(controller,10,large)
    controller.views.add(view)
    assert view.previous.disabled and not view.next.disabled
    outsider=NS(user=NS(id=11),response=NS(send_message=AsyncMock()))
    assert not await view.interaction_check(outsider)
    owner=NS(user=NS(id=10),response=NS(send_message=AsyncMock()))
    deadline=view.deadline
    assert await view.interaction_check(owner)
    assert view.deadline==deadline and view.timeout<=300
    view.message=NS(edit=AsyncMock())
    view.edit=AsyncMock()
    await view.update(large)
    view.edit.assert_not_awaited()
    view.page=2
    await view.update(data)
    assert view.page==0 and view.previous.disabled and view.next.disabled
    view.edit.assert_awaited_once()
    await view.on_timeout()
    assert view not in controller.views and all(item.disabled for item in view.children)


@pytest.mark.asyncio
async def test_permanent_post_recovers_send_survives_restart_and_skips_unchanged(tmp_path):
    from migrations.realm_daily import migrate as daily_migrate
    from utils.realms.daily_models import DailyReport
    backend=SqliteDatabase(tmp_path/'permanent.sqlite')
    daily_migrate(backend,apply=True,backup_verified=True)
    messages=[]
    class Channel:
        id=2
        guild=NS(id=1,me=NS())
        def permissions_for(self,member):
            return NS(view_channel=True,read_message_history=True,send_messages=True,attach_files=True)
        async def send(self,**kwargs):
            message=NS(id=50,author=NS(id=99),attachments=[NS(filename=kwargs['file'].filename)],
                       edit=AsyncMock(),jump_url='https://discord.com/channels/1/2/50')
            messages.append(message)
            raise TimeoutError('accepted but response lost')
        async def history(self,**kwargs):
            for message in messages:
                yield message
        async def fetch_message(self,identity):
            return messages[0]
    bot=NS(settings={'Coastal':1},user=NS(id=99))
    runtime=NS(config=NS(selected_realm_id='35868436'))
    channel=Channel()
    first=LeaderboardController(bot,runtime)
    first.load=AsyncMock(return_value=([('123456',3600)],{},datetime(2026,11,12)))
    with pytest.raises(TimeoutError):
        await first.post(channel)
    restarted=LeaderboardController(bot,runtime)
    restarted.load=first.load
    with pytest.raises(ValueError,match='reconciled'):
        await restarted.post(channel)
    with backend.connection_context():
        DailyReport.update(pending_since=DailyReport.get().pending_since-timedelta(minutes=6)).execute()
    assert await restarted.post(channel)==messages[0].jump_url
    assert restarted.post_view.is_persistent()
    assert await restarted.post(channel)==messages[0].jump_url
    assert len(messages)==1 and messages[0].edit.await_count==1
    with backend.connection_context():
        assert DailyReport.get().message==50
        assert DailyReport.select().count()==1


@pytest.mark.asyncio
async def test_leaderboard_matches_timeline_across_server_move_and_presence(tmp_path):
    import json
    from datetime import date
    from migrations.realm_daily import migrate as daily_migrate
    from utils.realms.daily import DailyController
    from utils.realms.daily_timeline import window
    from utils.realms.presence import PresenceSample
    backend=SqliteDatabase(tmp_path/'combined-leaderboard.sqlite')
    migrate(backend,apply=True,backup_verified=True)
    daily_migrate(backend,apply=True,backup_verified=True)
    day=date(2026,10,31)
    lo=window(day)[0].replace(tzinfo=None)
    with backend.connection_context():
        backend.create_tables([PresenceSample])
        for i,realm,xuid,start,end,status in [
            (1,'11451943','123456',0,2,'observed'),
            (2,'35868436','123456',1,3,'observed'),
            (3,'999','123456',5,9,'observed'),
            (4,'11451943','123456',5,9,'quarantined'),
            (5,'35868436','654321',4,5,'observed')]:
            RealmActivity.create(key=str(i),realm_id=realm,xuid=xuid,raw_start='0',raw_end='1',
                start=lo+timedelta(hours=start),end=lo+timedelta(hours=end),status=status,last_observed=lo)
        # Live empty coverage replaces 30 seconds of current Stories, but does
        # not remove a different player's old-Realm presence in the same window.
        for seconds in (0,15,30):
            stamp=lo+timedelta(hours=4,seconds=seconds)
            PresenceSample.create(realm='35868436',observed=stamp,online='[]')
            PresenceSample.create(realm='11451943',observed=stamp,online=json.dumps(['789123']))
    bot=NS(settings={'Coastal':1},get_guild=lambda _:None)
    runtime=NS(config=NS(selected_realm_id='35868436'),names=None,view=NS(activity=None))
    board=await LeaderboardController(bot,runtime).load()
    _,_,groups,_=await DailyController(bot,runtime).report(day)
    daily=groups.credits
    assert dict(board[0])==daily=={'123456':5400,'654321':1785,'789123':30}
    assert board[2]==lo+timedelta(hours=4,seconds=30)
