import json
from contextlib import nullcontext
from unittest.mock import Mock

from cryptography.fernet import Fernet
import pytest

from realms_fakes import account
from test_realms_store import store
from utils.configuration import SEED
from utils.integrations.realms.errors import StorageError
from utils.integrations.realms.models import Secret
from utils.integrations.realms import token_store
from utils.realms.panel import PanelRepository


def test_session_encryption_restart_binding_and_credentials_unchanged(tmp_path):
    keys = {"key-one": Secret(Fernet.generate_key().decode())}
    data = dict(realm_id="42", active={"9876543210987654": 1234}, last_observation=1234)
    directory = tmp_path / "private"
    with store(directory, keys) as cache:
        cache.save(account())
        original = cache.path.read_bytes()
        assert cache.load_panel_sessions() is None
        cache.save_panel_sessions(data)
        cache.save_gamertags({"entries":{"9876543210987654":{"name":"Private Sailor","expires":2000000000}},"next_lookup":0})
        assert cache.path.read_bytes() == original
        assert b"9876543210987654" not in (directory / "panel-sessions.realms.enc").read_bytes()
        assert b"Private Sailor" not in (directory / "gamertags.realms.enc").read_bytes()
    with store(directory, keys) as restarted:
        assert restarted.load_panel_sessions() == data
        assert restarted.load_gamertags()["entries"]["9876543210987654"]["name"] == "Private Sailor"
        assert restarted.load() == account()
    with store(directory, keys, binding={"account_ref":"other"}) as wrong:
        with pytest.raises(StorageError):
            wrong.load_panel_sessions()
    with store(directory, keys) as corrupt:
        (directory / "panel-sessions.realms.enc").write_bytes(b"private-corrupt-canary")
        with pytest.raises(StorageError) as error:
            corrupt.load_panel_sessions()
        assert error.value.__context__ is None


def test_atomic_session_write_failure_preserves_previous_and_token_record(tmp_path, monkeypatch):
    with store(tmp_path / "private") as cache:
        cache.save(account())
        credentials = cache.path.read_bytes()
        cache.save_panel_sessions({"old":"synthetic"})
        def fail(*args):
            raise OSError("private-canary")
        monkeypatch.setattr(token_store.os, "replace", fail)
        with pytest.raises(StorageError) as error:
            cache.save_panel_sessions({"new":"synthetic"})
        assert error.value.__context__ is None
        assert cache.load_panel_sessions() == {"old":"synthetic"}
        assert cache.path.read_bytes() == credentials
        assert not list(cache.directory.glob("sessions-*"))


def test_name_cache_unicode_bound_and_auxiliary_kind_isolation(tmp_path):
    with store(tmp_path / "private") as cache:
        data = {"entries": {str(x): {"name":"🦜" * 64,"expires":2000000000} for x in range(1,101)}, "next_lookup":0}
        cache.save_gamertags(data)
        assert cache.load_gamertags() == data
        assert (cache.directory / "gamertags.realms.enc").stat().st_size <= token_store.MAX_CACHE_BYTES
        cache.save_panel_sessions({"private":"synthetic"})
        (cache.directory / "gamertags.realms.enc").write_bytes((cache.directory / "panel-sessions.realms.enc").read_bytes())
        with pytest.raises(StorageError):
            cache.load_gamertags()


@pytest.mark.parametrize("key", ["realm_panel", "realm_metrics_panel"])
def test_panel_database_update_preserves_other_settings_and_schema(monkeypatch, key):
    from utils.database import __database
    document = json.loads(SEED.read_text())
    original = json.loads(json.dumps(document))
    guild = document["settings"]["Coastal"]
    cursor = Mock()
    cursor.fetchone.return_value = (json.dumps(document),)
    backend = Mock()
    backend.connection_context.side_effect = nullcontext
    backend.atomic.side_effect = nullcontext
    backend.execute_sql.return_value = cursor
    monkeypatch.setattr(__database, "db", backend)
    panel = dict(guild_id=guild, channel_id=123, message_id=456, interval_seconds=15)
    PanelRepository(key).save(panel, guild)
    sql, params = backend.execute_sql.call_args.args
    assert sql == "UPDATE botdata SET settings_json=%s WHERE id=1"
    updated = json.loads(params[0])
    assert updated["settings"].pop(key) == panel
    assert updated == original
    assert "FOR UPDATE" in backend.execute_sql.call_args_list[0].args[0]
    cursor.fetchone.return_value = (json.dumps(dict(original, settings=dict(original["settings"], realm_panel=panel))),)
    PanelRepository().save(None, guild)
    assert json.loads(backend.execute_sql.call_args.args[1][0]) == original
