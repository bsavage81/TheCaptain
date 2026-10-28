import asyncio
import importlib
import pkgutil
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock
import pytest
from peewee import SqliteDatabase
import discord
from discord import app_commands
from main import TheCaptain
from utils.core_features.__common import load_settings
from utils.database.__database import initialize_database, BotData, Administrators
from utils.integrations.__google_sheets import SheetsService
from utils.coastal_applications.__ca_logic import CONTENT_CELLS, load_content
from utils.coastal_applications.__ca_views import CoastalApplicationModal, CoastalApplicationStartView, CoastalApplicationContinueView
from utils.coastal_guide.__cg_logic import converse, GuideContent
from utils.helpers.__checks import op_team


def settings():
    return dict(MRP=101, PBtest=102, Coastal=103, CoastalMRP=104, CoastalApplications=105,
                CoastalOPTeam=106, CoastalMapUpdates=107, OPTeamRole="OP Team")


class Sheet:
    def __init__(self, rows=None):
        self.rows = rows or [["metadata"], ["questions"]]
        self.inserts = []
    def cell(self, row, col):
        return NS(value=f"Question {row}/{col}")
    def acell(self, address):
        return NS(value=f"Prompt {address}")
    def col_values(self, col):
        return [str(r[col-1]) if len(r) >= col else "" for r in self.rows]
    def insert_row(self, row, position, **kwargs):
        self.inserts.append((list(row), position, kwargs))
        self.rows.insert(position-1, list(row))
    def row_values(self, row):
        return self.rows[row-1]
    def update_cell(self, row, col, value):
        while len(self.rows[row-1]) < col:
            self.rows[row-1].append("")
        self.rows[row-1][col-1] = value


def service():
    result = SheetsService({})
    result.applications = Sheet()
    result.markers = {d: Sheet([["header"]]) for d in ("Overworld", "Nether", "End")}
    return result


def interaction(user=1):
    return NS(user=NS(id=user, mention="<synthetic>", display_name="Synthetic", avatar=True),
              response=NS(send_message=AsyncMock(), send_modal=AsyncMock(), defer=AsyncMock(), is_done=Mock(return_value=False)),
              followup=NS(send=AsyncMock()), channel=NS(id=104), channel_id=104, message=NS(edit=AsyncMock()))


def test_imports_no_config_or_writes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import main, utils
    importlib.reload(main)
    for info in pkgutil.walk_packages(utils.__path__, "utils."):
        importlib.import_module(info.name)
    assert list(tmp_path.iterdir()) == []


def test_fresh_and_existing_schema(tmp_path):
    backend = SqliteDatabase(tmp_path / "test.sqlite")
    cfg = dict(owner_ids=[999])
    from migrations.single_production import migrate
    with pytest.raises(ValueError, match="tables are missing"):
        initialize_database(cfg, backend)
    migrate(backend, apply=True)
    row = initialize_database(cfg, backend)
    assert row.id == 1
    with backend.connection_context():
        assert set(backend.get_tables()) == {"botdata", "administrators"}
        assert set(BotData._meta.fields) == {"id","prefix"}
        row.prefix = "!"
        row.save()
    again = initialize_database(cfg, backend)
    assert again.prefix == "!"
    with backend.connection_context():
        assert Administrators.get().discordID == 999
        assert BotData.select().count() == 1


def test_settings_no_writes_and_legacy_ids(tmp_path):
    import json
    path = tmp_path / "settings.json"
    path.write_text(json.dumps(settings()))
    cfg = load_settings(path, {"token":"synthetic"})
    assert cfg["CoastalInviteChannel"] == 443614533815369728
    assert "bot_type" not in cfg
    assert cfg["token"] == "synthetic"
    with pytest.raises(ValueError):
        load_settings(tmp_path / "missing", {})
    assert not (tmp_path / "missing").exists()


async def test_registration_exactly_once():
    sheets = NS(initialize=AsyncMock(), application_content=load_content(Sheet()), poi_content=NS(), guide_content=GuideContent())
    initializer = Mock(return_value=NS(prefix=">"))
    bot = TheCaptain(settings(), sheets=sheets, database_initializer=initializer)
    await bot.setup_hook()
    await bot.setup_hook()
    assert len(bot.extensions) == 6
    assert len(bot.cogs) == 6  # jishaku plus five Captain cogs
    names = lambda guild: sorted(c.name for c in bot.tree.get_commands(guild=discord.Object(guild)))
    assert names(101) == ["applycoastal"]
    expected = ["addpoi_end", "addpoi_end_returngateway", "addpoi_endcity_claim", "addpoi_nether", "addpoi_overworld", "approveapp", "denyapp", "guide"]
    assert names(102) == sorted(expected)
    assert names(103) == sorted(expected)
    assert [c.name for c in bot.tree.get_commands()] == ["repeat"]
    assert bot.get_command("sync") is not None
    for cmd in bot.tree.get_commands(guild=discord.Object(103)):
        if cmd.name.startswith("addpoi"):
            assert [p.name for p in cmd.parameters] == ["x_coord", "z_coord"]
    await bot.close()


async def test_three_pages_and_ownership():
    bot = NS(application_content=load_content(Sheet()))
    answers = {}
    for page in range(3):
        modal = CoastalApplicationModal(bot, page, answers, 1)
        assert len(modal.children) == 5
        assert modal.timeout == 300
        for value in modal.inputs.values():
            value._value = "Synthetic answer"
        wrong = interaction(2)
        await modal.on_submit(wrong)
        assert answers == {} if page == 0 else len(answers) == page * 5
        modal.finish_application = AsyncMock()
        right = interaction()
        await modal.on_submit(right)
        answers = modal.application_data
        assert len(answers) == (page+1)*5
        if page < 2:
            view = right.response.send_message.call_args.kwargs["view"]
            assert view.page_index == page+1 and view.user_id == 1
        else:
            modal.finish_application.assert_awaited_once()
    for view in (CoastalApplicationStartView(bot, 1), CoastalApplicationContinueView(bot, 1, {}, 1)):
        assert not await view.interaction_check(interaction(2))
        assert await view.interaction_check(interaction(1))
        assert not view.is_persistent()


async def test_application_channel_scope():
    from utils.coastal_applications.__ca_commands import CoastalAppCMD
    cog = CoastalAppCMD(NS(settings=settings(), application_content=load_content(Sheet())))
    wrong = interaction(); wrong.channel.id = 999
    await cog.applycoastal.callback(cog, wrong)
    assert "view" not in wrong.response.send_message.call_args.kwargs
    right = interaction()
    await cog.applycoastal.callback(cog, right)
    assert isinstance(right.response.send_message.call_args.kwargs["view"], CoastalApplicationStartView)


async def test_role_policy():
    async def callback(interaction):
        pass
    predicate = op_team()(callback).__discord_app_commands_checks__[0]
    i = interaction(); i.client = NS(settings=settings()); i.user.roles = []
    with pytest.raises(app_commands.MissingRole):
        await predicate(i)
    i.user.roles = [NS(id=9, name="OP Team")]
    assert await predicate(i)
    i.client.settings["OPTeamRole"] = 10
    with pytest.raises(app_commands.MissingRole):
        await predicate(i)
    i.user.roles = [NS(id=10, name="Renamed")]
    assert await predicate(i)


async def test_sheet_mappings_serialization_and_row_shift():
    s = service()
    s.applications.rows += [[3,"Synthetic","", "1000"], [8,"Synthetic","","1001"]]
    ids = await asyncio.gather(*(s.submit_application([None]+["synthetic"]*19) for _ in range(10)))
    assert ids == list(range(9,19))
    row, position, options = s.applications.inserts[0]
    assert len(row) == 20 and position == 3 and options == {"value_input_option":"USER_ENTERED"}
    record = await s.application_record(3)
    await s.submit_application([None]+["synthetic"]*19)
    await s.decide_application(3, "Yes")
    assert record[20] == "Yes"
    await s.decide_application(8,"No")
    assert (await s.application_record(8))[20] == "No"
    with pytest.raises(ValueError):
        await s.decide_application(8,"Approved")
    for dim in s.markers:
        await s.submit_poi(dim,[None]+["synthetic"]*13)
        assert len(s.markers[dim].inserts[0][0]) == 14
        assert s.markers[dim].inserts[0][1] == 2
    assert CONTENT_CELLS["Qgamertag"] == (2,5)
    assert CONTENT_CELLS["Qref3"] == (2,19)
    assert CONTENT_CELLS["questiontitle3"] == (1,9)


@pytest.mark.parametrize("answers", [["wrong", " ARMADILLO ", "YES"], ["armadillo", "no"], [], ["wrong"], ["armadillo"]])
async def test_guide_retries_all_timeouts_and_ownership(answers):
    messages = [NS(content=a) for a in answers]
    channel = NS(send=AsyncMock())
    author = NS(id=1,name="Synthetic",add_roles=AsyncMock())
    response = NS(send=AsyncMock())
    async def wait_for(event, timeout, check):
        assert not check(NS(content="x",channel=channel,author=NS(id=2)))
        assert not check(NS(content="x",channel=NS(),author=author))
        assert check(NS(content="x",channel=channel,author=author))
        if not messages:
            raise asyncio.TimeoutError
        return messages.pop(0)
    await converse(NS(wait_for=wait_for, settings=settings(), guide_content=GuideContent(web_url="https://example.invalid/guide",question="Synthetic question",answer="armadillo")), channel, author, "guide-role", "active-role", response)
    if answers and answers[-1] == "YES":
        assert author.add_roles.await_count == 2
        response.send.assert_awaited_once()
    else:
        author.add_roles.assert_not_awaited()
    if not answers or answers[-1] in ("wrong", "armadillo"):
        assert "tired of waiting" in channel.send.call_args.args[0]


async def test_application_row_and_notification_failure():
    cfg = settings()
    channel = NS(send=AsyncMock(side_effect=RuntimeError("synthetic")))
    guild = NS(get_channel=Mock(return_value=channel), get_role=Mock(return_value=NS(mention="synthetic")))
    s = service()
    bot = NS(settings=cfg, application_content=load_content(Sheet()), sheets=s, get_guild=Mock(return_value=guild))
    modal = CoastalApplicationModal(bot, user_id=1)
    keys = [key for page in bot.application_content.pages for key, _ in page["questions"]]
    modal.application_data = dict(zip(keys, [f"answer-{n}" for n in range(15)]))
    i = interaction()
    await modal.finish_application(i)
    i.response.defer.assert_awaited_once()
    row = s.applications.inserts[0][0]
    assert row[4:19] == [f"answer-{n}" for n in range(15)]
    assert row[3] == "1" and len(row) == 20
    assert "was saved" in i.followup.send.call_args.args[0]
    await modal.finish_application(interaction())
    assert len(s.applications.inserts) == 1


async def test_failed_insert_is_not_retried():
    s = service()
    s.applications.insert_row = Mock(side_effect=TimeoutError("uncertain transport"))
    with pytest.raises(TimeoutError):
        await s.submit_application([None]*20)
    assert s.applications.insert_row.call_count == 1


async def test_worker_is_off_loop():
    import threading
    s = service()
    caller = threading.get_ident()
    assert await s._run(threading.get_ident) != caller


async def test_lazy_service_initialization_and_titles():
    app = Sheet()
    marker = Mock()
    marker.worksheet.side_effect = lambda name: Sheet()
    client = Mock()
    client.open.side_effect = lambda name: NS(sheet1=app) if name == "CCS10 Realm Application" else marker
    factory = Mock(return_value=client)
    s = SheetsService({}, client_factory=factory)
    factory.assert_not_called()
    await s.initialize()
    await s.initialize()
    factory.assert_called_once()
    assert [call.args[0] for call in client.open.call_args_list] == ["CCS10 Realm Application", "Coastal Markers S10"]
    assert [call.args[0] for call in marker.worksheet.call_args_list] == ["Overworld", "Nether", "End", "Questions"]
    client.set_timeout.assert_called_once_with(30)


@pytest.mark.parametrize("method,dimension,answers", [
    ("addpoi_overworld","Overworld",["First","No","no","blue","shop"]),
    ("addpoi_nether","Nether",["First","No","no","blue","portal"]),
    ("addpoi_end","End",["First","No","no","blue","base"]),
    ("addpoi_endcity_claim","End",["Synthetic","green"]),
    ("addpoi_end_returngateway","End",[]),
])
async def test_actual_poi_rows(method, dimension, answers, monkeypatch):
    from utils.coastal_poi import __poi_logic as logic
    monkeypatch.setattr(logic.asyncio,"sleep", AsyncMock())
    s = service()
    channel = NS(send=AsyncMock())
    guild = NS(get_channel=Mock(return_value=channel), get_role=Mock(return_value=NS(mention="synthetic")))
    user = NS(id=1,name="Synthetic",display_name="Synthetic",discriminator="0")
    async def wait_for(event, timeout, check):
        assert timeout == 60
        assert not check(NS(content="x",channel=channel,author=NS(id=2)))
        return NS(content=answers.pop(0))
    bot = NS(settings=settings(), sheets=s, get_guild=Mock(return_value=guild), wait_for=wait_for,
             poi_content=NS(**{n:n for n in ["poidesc","Qtext1","Qtext2","Qtext3","Qtextcolor","Qmarkertype"]}))
    i = interaction(); i.user=user; i.channel=channel
    await logic.run_poi(NS(bot=bot),i,12,-34,getattr(logic,method))
    row,position,options = s.markers[dimension].inserts[0]
    assert row[:6] == [1,12,-34,"-1","",""]
    assert row[10:13] == ["#ffffff","0","0"]
    assert len(row)==14 and position==2
    if method.endswith("claim"):
        assert row[6:10] == ["\uf06a","Synthetic","","green"]
    elif method.endswith("returngateway"):
        assert row[6:10] == ["\uf52b","Return Portal","","red"]
    else:
        assert row[6:10] == ["First","","","blue"]
    i.response.send_message.assert_awaited_once()


async def test_poi_timeout_and_duplicate_session():
    from utils.coastal_poi.__poi_logic import run_poi, wait_answer
    channel = NS(send=AsyncMock())
    bot=NS(wait_for=AsyncMock(side_effect=asyncio.TimeoutError))
    with pytest.raises(asyncio.TimeoutError):
        await wait_answer(bot,channel,NS(id=1))
    assert "tired of waiting" in channel.send.call_args.args[0]
    cog=NS(sessions={(104,1)})
    operation=AsyncMock()
    await run_poi(cog,interaction(),1,2,operation)
    operation.assert_not_awaited()


@pytest.mark.parametrize("status,method", [("Yes","approveapp"),("No","denyapp")])
async def test_decision_saved_when_dm_fails(status, method):
    from utils.coastal_applications.__ca_commands import CoastalAppCMD
    s=service(); s.applications.rows.append([1,"Synthetic","Synthetic","1"])
    user=NS(send=AsyncMock(side_effect=discord.Forbidden(NS(status=403,reason="Forbidden"),"synthetic")))
    invitechannel=NS(create_invite=AsyncMock(return_value=NS(url="synthetic")))
    guild=NS(get_channel=Mock(return_value=invitechannel), get_member_named=Mock(return_value=user))
    bot=NS(settings={**settings(),"CoastalInviteChannel":108},sheets=s,get_guild=Mock(return_value=guild))
    cog=CoastalAppCMD(bot); i=interaction();i.guild=guild
    await getattr(cog,method).callback(cog,i,"1")
    i.response.defer.assert_awaited_once()
    assert (await s.application_record(1))[20]==status
    embed=i.followup.send.call_args.kwargs["embed"]
    assert "delivery failed" in embed.fields[1].value


async def test_failed_application_write_suppresses_retry():
    s=NS(submit_application=AsyncMock(side_effect=TimeoutError("synthetic")))
    guild=NS(get_channel=Mock(return_value=NS()),get_role=Mock(return_value=NS()))
    bot=NS(settings=settings(),sheets=s,application_content=load_content(Sheet()),get_guild=Mock(return_value=guild))
    modal=CoastalApplicationModal(bot,user_id=1)
    await modal.finish_application(interaction())
    await modal.finish_application(interaction())
    assert s.submit_application.await_count==1


async def test_database_owner_check_is_injected():
    admin=Mock(return_value=True)
    bot=TheCaptain(settings(),admin_check=admin)
    assert await bot.is_owner(NS(id=999))
    admin.assert_called_once_with(999,3)
    await bot.close()


async def test_admin_sync_remains_tier_three():
    from utils.admin.bot_management.__bm_commands import BackupRegularCommands
    assert len(BackupRegularCommands.sync.checks)==1
    assert BackupRegularCommands.sync.checks[0].__name__=="predicate_LV3"


async def test_concurrent_initialization_runs_once():
    s=SheetsService({})
    s._connect=Mock(side_effect=lambda: setattr(s,"ready",True))
    await asyncio.gather(s.initialize(),s.initialize())
    s._connect.assert_called_once()


async def test_long_modal_title_keeps_page_number():
    content=load_content(Sheet());content.pages[0]["title"]="Synthetic "*10
    modal=CoastalApplicationModal(NS(application_content=content),user_id=1)
    assert len(modal.title)==45 and modal.title.endswith("1/3")


async def test_sheet_worker_cancellation_holds_lock():
    import threading
    s=service();started=threading.Event();release=threading.Event()
    def slow():
        started.set()
        release.wait(5)
    task=asyncio.create_task(s._run(slow))
    await asyncio.to_thread(started.wait,5)
    task.cancel()
    other=asyncio.create_task(s._run(lambda: "second"))
    await asyncio.sleep(0)
    assert not other.done()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert await other == "second"
