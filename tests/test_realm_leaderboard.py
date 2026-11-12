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
    assert data[0]==[('123456',3600)]
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
