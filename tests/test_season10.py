import json
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock, AsyncMock
import pytest
from peewee import SqliteDatabase
from test_captain import Sheet, settings, interaction
from main import TheCaptain
from utils.core_features.__common import load_settings, coastal_command_guilds
from utils.core_features.__constants import ROOT, CAPTAIN_SERVICE_ACCOUNT
from utils.database import __database as database
from utils.integrations.__google_sheets import SheetsService, SheetsInitializationError, SCOPES
from utils.coastal_guide.__cg_logic import GuideContent, load_guide_content, run_guide
from migrations.single_production import inventory, migrate


def client_fixture():
    app=Sheet()
    worksheets={n:Sheet() for n in ("Overworld","Nether","End","Questions")}
    book=NS(worksheet=Mock(side_effect=worksheets.__getitem__))
    client=Mock()
    client.open.side_effect=lambda title: NS(sheet1=app) if title=="CCS10 Realm Application" else book
    client.open_by_key.side_effect=lambda key: NS(sheet1=app) if key=="synthetic-application-key" else book
    return client, worksheets


@pytest.mark.parametrize("ids", [False,True])
async def test_season10_selection(ids):
    client,worksheets=client_fixture()
    cfg={}
    if ids:
        cfg.update(application_sheet_id="synthetic-application-key",markers_sheet_id="synthetic-marker-key")
    service=SheetsService(cfg,client_factory=lambda:client)
    await service.initialize()
    assert service.ready
    if ids:
        client.open.assert_not_called()
        assert [c.args[0] for c in client.open_by_key.call_args_list]==["synthetic-application-key","synthetic-marker-key"]
    else:
        client.open_by_key.assert_not_called()
        assert [c.args[0] for c in client.open.call_args_list]==["CCS10 Realm Application","Coastal Markers S10"]
    assert set(service.markers)=={"Overworld","Nether","End"}
    assert service.poi_content.poidesc=="Prompt B1" and service.poi_content.Qmarkertype=="Prompt B6"


async def test_title_overrides_and_mixed_key_selection():
    client,worksheets=client_fixture()
    client.open.side_effect=None;client.open.return_value=NS(worksheet=lambda name:worksheets[name])
    service=SheetsService(dict(application_sheet_id="synthetic-application-key",markers_sheet="Synthetic copy"),client_factory=lambda:client)
    await service.initialize()
    client.open_by_key.assert_called_once_with("synthetic-application-key")
    client.open.assert_called_once_with("Synthetic copy")


@pytest.mark.parametrize("stage", ["application","markers","Overworld","Nether","End","Questions"])
async def test_missing_or_inaccessible_sheets_fail_without_half_ready_state(stage):
    client,worksheets=client_fixture()
    original=client.open.side_effect
    def open_book(title):
        if (stage=="application" and title.startswith("CCS10")) or (stage=="markers" and title.startswith("Coastal Markers")):
            raise RuntimeError("private payload must not be exposed")
        result=original(title)
        if hasattr(result,"worksheet") and stage in worksheets:
            def worksheet(name):
                if name==stage:raise RuntimeError("private payload must not be exposed")
                return worksheets[name]
            result.worksheet=worksheet
        return result
    client.open.side_effect=open_book
    service=SheetsService({},client_factory=lambda:client)
    with pytest.raises(SheetsInitializationError) as error:
        await service.initialize()
    assert "private payload" not in str(error.value)
    assert not service.ready and not hasattr(service,"applications")


async def test_retry_after_read_only_initialization_failure():
    client,_=client_fixture();factory=Mock(side_effect=[RuntimeError("synthetic"),client])
    service=SheetsService({},client_factory=factory)
    with pytest.raises(SheetsInitializationError):await service.initialize()
    await service.initialize()
    assert service.ready and factory.call_count==2


async def test_dedicated_credentials_boundary(monkeypatch,tmp_path):
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
    client,_=client_fixture()
    path=str(tmp_path / "not-created.json")
    loader=Mock(return_value=NS(service_account_email=CAPTAIN_SERVICE_ACCOUNT))
    authorize=Mock(return_value=client)
    monkeypatch.setattr(ServiceAccountCredentials,"from_json_keyfile_name",loader)
    monkeypatch.setattr(gspread,"authorize",authorize)
    await SheetsService({"credentials_path":path}).initialize()
    loader.assert_called_once_with(path,SCOPES)
    assert not Path(path).exists()
    loader.return_value=NS(service_account_email="synthetic@example.invalid")
    authorize.reset_mock()
    with pytest.raises(SheetsInitializationError,match="dedicated service account"):
        await SheetsService({"credentials_path":path}).initialize()
    authorize.assert_not_called()


def test_credentials_path_and_optional_test_guild(tmp_path,monkeypatch):
    cfg=settings();cfg.pop("PBtest")
    cfg["credentials_path"]="private/captain.json"
    cfg["application_sheet_id"]=" synthetic-application-key "
    path=tmp_path/"config.json";path.write_text(json.dumps(cfg))
    monkeypatch.chdir(tmp_path)
    result=load_settings(path,{})
    assert result["credentials_path"]==str((ROOT/"private/captain.json").resolve())
    assert result["application_sheet"]=="CCS10 Realm Application"
    assert result["markers_sheet"]=="Coastal Markers S10"
    assert result["application_sheet_id"]=="synthetic-application-key"
    assert coastal_command_guilds(result)==[cfg["Coastal"]]
    cfg["credentials_path"]=str(tmp_path/"absolute.json");path.write_text(json.dumps(cfg))
    assert load_settings(path,{})["credentials_path"]==str(tmp_path/"absolute.json")
    assert not (tmp_path/"absolute.json").exists()


@pytest.mark.parametrize("old_mode", ["BETA","unexpected"])
def test_retired_mode_is_not_silently_repurposed(tmp_path,old_mode):
    path=tmp_path/"config.json";path.write_text(json.dumps(settings()))
    with pytest.raises(ValueError,match="Retired"):
        load_settings(path,{"bot_type":old_mode})
    with pytest.raises(ValueError,match="Retired"):
        database.initialize_database({"bot_type":old_mode},SqliteDatabase(tmp_path/"unused.sqlite"))
    assert not (tmp_path/"unused.sqlite").exists()
    result=load_settings(path,{"bot_type":"STABLE"})
    assert "bot_type" not in result


def test_production_values_and_legacy_rows_preserved(tmp_path):
    backend=SqliteDatabase(tmp_path/"legacy.sqlite")
    migrate(backend,apply=True)
    database.initialize_database({"owner_ids":[999]},backend)
    with backend.connection_context():
        database.BotData.update(prefix="!",bot_id=123,server_id_coastal=456,bot_type="Stable",persistent_views=True).where(database.BotData.id==1).execute()
        database.BotData.create(id=2,prefix="?",bot_type="BETA",server_id_aurafall=789)
        before=list(database.BotData.select().dicts());admins=list(database.Administrators.select().dicts())
    planned=migrate(backend)
    assert planned["production_row_present"] and planned["legacy_row_2_present"] and not planned["applied"]
    for _ in range(2):
        assert migrate(backend,apply=True)["applied"]
    row=database.initialize_database({"owner_ids":[1000]},backend)
    assert row.id==1 and row.prefix=="!"
    with backend.connection_context():
        assert list(database.BotData.select().dicts())==before
        assert list(database.Administrators.select().dicts())==admins


def test_migration_default_read_only_and_repeat_safe(tmp_path):
    backend=SqliteDatabase(tmp_path/"fresh.sqlite")
    assert migrate(backend)["tables"]=={}
    with backend.connection_context():assert backend.get_tables()==[]
    migrate(backend,apply=True);migrate(backend,apply=True)
    assert inventory(backend)["production_row_present"]
    with backend.connection_context():
        assert database.BotData.select().count()==1
        # Migration never grants permissions. Runtime retains its original empty-admin seeding.
        assert database.Administrators.select().count()==0


@pytest.mark.parametrize("apply",[False,True])
def test_only_legacy_row_needs_review_not_inferred_production(tmp_path,apply):
    backend=SqliteDatabase(tmp_path/"retired.sqlite");database.db.initialize(backend)
    with backend.connection_context():
        backend.create_tables(list(database.tables.values()))
        database.BotData.create(id=2,bot_type="BETA",prefix="?")
    with pytest.raises(ValueError,match="No production row 1"):
        migrate(backend,apply=apply)
    with pytest.raises(ValueError,match="Production BotData row 1 is missing"):
        database.initialize_database({},backend)
    with backend.connection_context():
        assert database.BotData.select().count()==1
        assert database.BotData.get().id==2


async def test_startup_without_beta_or_test_guild_never_syncs():
    cfg=settings();cfg.pop("PBtest")
    sheets=NS(initialize=AsyncMock(),application_content=NS(),poi_content=NS(),guide_content=GuideContent())
    bot=TheCaptain(cfg,sheets=sheets,database_initializer=lambda cfg:NS(prefix="!"))
    bot.tree.sync=AsyncMock(side_effect=AssertionError("No automatic command sync"))
    await bot.setup_hook()
    assert bot.tree.get_commands(guild=__import__("discord").Object(cfg["Coastal"]))
    assert not bot.tree.get_commands(guild=__import__("discord").Object(102))
    bot.tree.sync.assert_not_called()
    await bot.close()


def test_guide_config_and_opt_in_sheet_cells():
    values={"D10":"https://example.invalid/season10","D11":"Synthetic question","D12":"  Synthetic Answer  "}
    questions=NS(acell=Mock(side_effect=lambda address:NS(value=values[address])))
    content=load_guide_content({"guide_cells":{"web_url":"D10","question":"D11","answer":"D12"}},questions)
    assert content.configured and content.answer=="Synthetic Answer"
    assert [call.args[0] for call in questions.acell.call_args_list]==["D10","D11","D12"]
    assert load_guide_content({}).configured
    with pytest.raises(ValueError):load_guide_content({"guide_cells":{"question":"not a cell"}},questions)
    with pytest.raises(ValueError):load_guide_content({"guide_web_url":"not-a-url"})


async def test_unverified_guide_content_never_assigns_roles():
    cog=NS(bot=NS(guide_content=GuideContent()))
    i=interaction()
    await run_guide(cog,i)
    assert "awaiting operator configuration" in i.response.send_message.call_args.args[0]


@pytest.mark.parametrize("response", ["armadillo","The ARMADILLO knows!","I think the armadillo does."])
def test_owner_confirmed_guide_defaults_and_loose_acceptance(response):
    content=load_guide_content({})
    assert content.question=="Who knows?"
    assert "1FGK84rUyrC6LX0UrnW7IxzjupYPEbOCo7ccpQlSmvu8" in content.web_url
    assert "1zMmjQTzZeEHUHgjxNZsNnGe9ubw-3QCW" in content.pdf_url
    assert content.accepts(response)
    assert not content.accepts("the cat knows")
    assert not content.accepts("")


def test_guide_match_validation_and_exact_option():
    content=load_guide_content({"guide_answer_match":"exact"})
    assert content.accepts(" ARMADILLO ")
    assert not content.accepts("the armadillo knows")
    with pytest.raises(ValueError):load_guide_content({"guide_answer_match":"invalid"})


def test_logo_default_matches_owner_cdn_selection(tmp_path):
    path=tmp_path/"config.json";path.write_text(json.dumps(settings()))
    cfg=load_settings(path,{})
    assert cfg["logo_url"].startswith("https://cdn.discordapp.com/attachments/488792053002534920/1561597489516384357/IMG_8282.png?")
    assert "drive.google.com" not in cfg["logo_url"]


def test_runtime_never_creates_database_tables(tmp_path):
    backend=SqliteDatabase(tmp_path/"fresh-no-ddl.sqlite")
    with pytest.raises(ValueError,match="tables are missing"):
        database.initialize_database({},backend)
    with backend.connection_context():assert backend.get_tables()==[]
