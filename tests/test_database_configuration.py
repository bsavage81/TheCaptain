"""Configuration migration/precedence tests; no production services or secrets."""
import copy
import json
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
import pytest
from peewee import SqliteDatabase
from main import TheCaptain
from migrations.botdata_settings import migrate
from migrations.single_production import migrate as bootstrap_schema
from utils.configuration import (SEED, SETTING_KEYS, import_document, load_bootstrap,
                                 read_database_settings, validate_document)
from utils.database.__database import Administrators, BotData, initialize_database


@pytest.fixture
def backend(tmp_path):
    backend = SqliteDatabase(tmp_path / "settings.sqlite")
    bootstrap_schema(backend, apply=True)
    with backend.connection_context():
        BotData.update(prefix="%", bot_id=987, server_id_coastal=123, bot_spam_channel_coastal=456).execute()
    return backend


@pytest.fixture
def document():
    return json.loads(SEED.read_text(encoding="utf-8"))


def apply(backend, source=None, **kwargs):
    return migrate(backend, source, apply=True, backup_verified=True, **kwargs)


def test_seed_captures_owner_settings_without_secrets(document):
    assert set(document["settings"]) == SETTING_KEYS
    config = validate_document(document)["settings"]
    assert config["CoastalGuideRole"] == 1565125349044527184
    assert config["Coastal"] == 305767872410419211
    assert config["botspamChannel"] == 411566709359509504
    assert config["checkin_inactive_role_id"] == 547138462357258242
    assert not config["profiles_enabled"]
    assert "Aurafall" not in config
    assert document["legacy_settings"]["Aurafall"] == 298995889551310848
    assert "database_password" not in json.dumps(document)


def test_migration_preview_and_backup_gate(backend):
    preview = migrate(backend)
    assert preview["add_column"] and not preview["applied"]
    with backend.connection_context():
        assert "settings_json" not in {c.name for c in backend.get_columns("botdata")}
    with pytest.raises(ValueError, match="backup"):
        migrate(backend, apply=True)
    with backend.connection_context():
        assert "settings_json" not in {c.name for c in backend.get_columns("botdata")}


def test_apply_preserves_legacy_values_and_is_idempotent(backend):
    assert apply(backend)["applied"]
    assert not apply(backend)["applied"]
    with backend.connection_context():
        row = BotData.get_by_id(1)
        assert (row.prefix, row.bot_id, row.server_id_coastal, row.bot_spam_channel_coastal) == ("%", 987, 123, 456)
        assert not Administrators.select().exists()
        assert read_database_settings(backend)["prefix"] == "%"
        assert read_database_settings(backend)["bot_spam_channel_coastal"] == 456


def test_flat_server_file_import_preserves_values_and_filters_secrets(backend):
    source = {"prefix": "%", "CoastalGuideRole": 123456789012345678,
              "BotType": "STABLE", "Aurafall": 298995889551310848,
              "token": "synthetic-token", "database_password": "synthetic-password"}
    original = copy.deepcopy(source)
    assert apply(backend, source)["applied"]
    assert source == original
    with backend.connection_context():
        text = backend.execute_sql("SELECT settings_json FROM botdata WHERE id=1").fetchone()[0]
        assert "synthetic-token" not in text and "synthetic-password" not in text
        assert read_database_settings(backend)["CoastalGuideRole"] == 123456789012345678


def test_existing_configuration_requires_explicit_replacement(backend, document):
    apply(backend, document)
    newer = copy.deepcopy(document)
    newer["settings"]["checkin_channel_id"] = 123456789012345678
    assert migrate(backend, newer)["requires_replace_existing"]
    with pytest.raises(ValueError, match="differ"):
        apply(backend, newer)
    with backend.connection_context():
        assert read_database_settings(backend)["checkin_channel_id"] == 504140612019421184
    apply(backend, newer, replace_existing=True)
    with backend.connection_context():
        assert read_database_settings(backend)["checkin_channel_id"] == 123456789012345678


def test_prefix_uses_existing_column_not_json_duplicate(backend):
    with pytest.raises(ValueError, match="differ"):
        apply(backend, {"prefix": "!"})
    apply(backend, {"prefix": "!"}, replace_existing=True)
    with backend.connection_context():
        config = read_database_settings(backend)
        document = json.loads(backend.execute_sql("SELECT settings_json FROM botdata WHERE id=1").fetchone()[0])
        assert config["prefix"] == "!"
        assert "prefix" not in document["settings"]


def test_explicit_one_setting_updates_and_safe_rollback(backend, document):
    apply(backend, document)
    preview = migrate(backend, set_key="checkin_channel_id", value=123456789012345678)
    assert preview["changed_keys"] == ["checkin_channel_id"]
    apply(backend, set_key="checkin_channel_id", value=123456789012345678, replace_existing=True)
    # Rollback uses the reviewed, backed-up settings document, retaining the column.
    apply(backend, document, replace_existing=True)
    with backend.connection_context():
        assert read_database_settings(backend)["checkin_channel_id"] == document["settings"]["checkin_channel_id"]


def test_incomplete_ddl_can_resume(backend):
    with backend.connection_context():
        backend.execute_sql("ALTER TABLE botdata ADD COLUMN settings_json TEXT NULL")
    assert not migrate(backend)["add_column"]
    assert apply(backend)["applied"]


def test_missing_or_invalid_settings_fail_closed(backend):
    with backend.connection_context():
        with pytest.raises(ValueError, match="migrations.botdata_settings"):
            read_database_settings(backend)
        backend.execute_sql("ALTER TABLE botdata ADD COLUMN settings_json TEXT NULL")
        with pytest.raises(ValueError, match="missing"):
            read_database_settings(backend)
        backend.execute_sql("UPDATE botdata SET settings_json='{}'")
        with pytest.raises(ValueError, match="version"):
            read_database_settings(backend)


def test_no_runtime_json_file_or_seed_precedence(backend, document, monkeypatch):
    document["settings"]["CoastalGuideRole"] = 123456789012345678
    apply(backend, document)
    from pathlib import Path
    def denied(*args, **kwargs):
        raise AssertionError("Runtime must not read settings files")
    monkeypatch.setattr(Path, "read_text", denied)
    with backend.connection_context():
        assert read_database_settings(backend)["CoastalGuideRole"] == 123456789012345678


def test_coastal_bot_spam_uses_authoritative_sql_column(backend):
    apply(backend)
    with backend.connection_context():
        before = backend.execute_sql("SELECT settings_json FROM botdata WHERE id=1").fetchone()[0]
        BotData.update(bot_spam_channel_coastal=789).where(BotData.id == 1).execute()
        config = read_database_settings(backend)
        assert config["bot_spam_channel_coastal"] == 789
        assert config["botspamChannel"] != 789
        assert config["CoastalMRP"] != 789
        assert backend.execute_sql("SELECT settings_json FROM botdata WHERE id=1").fetchone()[0] == before


def test_missing_coastal_bot_spam_never_uses_mrp_or_generic_channel(backend):
    apply(backend)
    with backend.connection_context():
        BotData.update(bot_spam_channel_coastal=0).where(BotData.id == 1).execute()
        with pytest.raises(ValueError, match="bot_spam_channel_coastal"):
            read_database_settings(backend)


def test_database_startup_loads_config_before_owner_seeding(backend, document):
    document["settings"]["owner_ids"] = [999]
    apply(backend, document)
    config = {"configuration_source": "database"}
    assert initialize_database(config, backend).prefix == "%"
    assert config["Coastal"] == document["settings"]["Coastal"]
    with backend.connection_context():
        assert Administrators.get().discordID == 999


def test_missing_database_settings_never_seeds_default_owner(backend):
    with pytest.raises(ValueError):
        initialize_database({"configuration_source": "database"}, backend)
    with backend.connection_context():
        assert not Administrators.select().exists()


def test_bootstrap_environment_only(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "botconfig.json").write_text('{"Coastal": 999}')
    config = load_bootstrap({"token": "synthetic", "database_ip": "synthetic.invalid",
        "database_username": "synthetic", "database_password": "synthetic", "database_schema": "synthetic",
        "Coastal": "999", "checkin_enabled": "true"})
    assert config["configuration_source"] == "database"
    assert "Coastal" not in config and "checkin_enabled" not in config
    with pytest.raises(ValueError, match="bootstrap"):
        load_bootstrap({})
    with pytest.raises(ValueError, match="Retired"):
        load_bootstrap({"bot_type": "BETA"})


@pytest.mark.parametrize("changes", [{"BotType": "BETA"}, {"unknown_key": 1}, {"prefix": ""}])
def test_invalid_legacy_input_rejected(changes):
    with pytest.raises(ValueError):
        import_document(changes)


@pytest.mark.parametrize("key,value", [("Coastal", True), ("guide_cells", {"answer": "bad-cell"}),
    ("profile_sources", {"synthetic": {"token": "synthetic"}}), ("owner_ids", []),
    ("checkin_enabled", True)])
def test_invalid_database_settings_rejected(document, key, value):
    document["settings"][key] = value
    with pytest.raises(ValueError):
        validate_document(document)


async def test_startup_publishes_database_values_before_sheets(backend, document):
    apply(backend, document)
    from utils.coastal_guide.__cg_logic import GuideContent
    sheets = NS(initialize=AsyncMock(), application_content=NS(), poi_content=NS(), guide_content=GuideContent())
    config = {"configuration_source": "database"}
    def initialize(settings):
        return initialize_database(settings, backend)
    bot = TheCaptain(config, sheets=sheets, database_initializer=initialize)
    bot.load_extension = AsyncMock()
    await bot.setup_hook()
    assert sheets.initialize.await_count == 1
    assert bot.settings["application_sheet_id"] == document["settings"]["application_sheet_id"]
    assert bot.settings["CoastalGuideRole"] == document["settings"]["CoastalGuideRole"]
    await bot.close()


def test_concurrent_update_is_not_overwritten(backend, document, monkeypatch):
    apply(backend, document)
    execute = backend.execute_sql
    def race(sql, params=None, *args, **kwargs):
        if sql.startswith("UPDATE botdata SET settings_json="):
            return NS(rowcount=0)
        return execute(sql, params, *args, **kwargs)
    monkeypatch.setattr(backend, "execute_sql", race)
    with pytest.raises(ValueError, match="concurrently"):
        apply(backend, set_key="checkin_channel_id", value=123456789012345678, replace_existing=True)
    with backend.connection_context():
        assert read_database_settings(backend)["checkin_channel_id"] == 504140612019421184
