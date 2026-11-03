import json
from types import SimpleNamespace

import pytest

from realms_fakes import FakeHTTP, FakeTime, config
from utils.integrations.realms.configuration import Principal, RealmsConfig
from utils.integrations.realms.errors import AccessDenied, ConfigurationError
from utils.integrations.realms.service import RealmsService
from scripts import realms_diagnostic as diagnostic


@pytest.mark.parametrize("principal", [Principal(999, 202), Principal(101, 999), Principal(True, 202),
    SimpleNamespace(user_id=101, guild_id=202, administrator=True, tier=4), None])
async def test_allowlist_and_guild_independent_of_admin_roles(principal):
    api = RealmsService(config(), FakeHTTP(), None, clock=FakeTime())
    with pytest.raises(AccessDenied):
        await api.begin_device_login(principal)
    with pytest.raises(AccessDenied):
        await api.authorization_for(principal)
    assert not api.transport.calls


@pytest.mark.parametrize("change", [dict(client_id="borrowed-title"), dict(auth_owner_ids=()), dict(guild_id=True),
    dict(expected_gamertag=""), dict(client_version="bad\r\nheader"), dict(account_ref="../escape"),
    dict(selected_realm_id="42/join"), dict(enabled="false")])
def test_enabled_config_is_strict(change):
    with pytest.raises(ConfigurationError):
        config(**change)


@pytest.mark.parametrize("doc", [{}, {"version": True, "realms": {}}, {"version": 1, "realms": {"token": "canary"}},
    {"version": 1, "realms": {}, "other": 1}])
def test_reject_unknown_config_envelope(doc):
    with pytest.raises(ConfigurationError):
        RealmsConfig.from_document(doc)


def test_diagnostic_default_check_needs_no_credentials(tmp_path, capsys, monkeypatch):
    path = tmp_path / "disabled.json"
    path.write_text('{"version":1,"realms":{"enabled":false}}')
    monkeypatch.setattr(diagnostic, "live", lambda *a: pytest.fail("Live path reached"))
    assert diagnostic.main(["--config", str(path)]) == 0
    assert "offline" in capsys.readouterr().out


def test_diagnostic_rejects_live_without_opt_in_or_terminal(tmp_path, capsys, monkeypatch):
    from dataclasses import asdict
    path = tmp_path / "enabled.json"
    path.write_text(json.dumps({"version": 1, "realms": asdict(config())}))
    monkeypatch.setattr(diagnostic.sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr(diagnostic, "live", lambda *a: pytest.fail("Live path reached"))
    args = ["login", "--config", str(path), "--user-id", "101", "--guild-id", "202"]
    assert diagnostic.main(args) == 2
    assert diagnostic.main(args + ["--allow-live"]) == 2
    assert "canary" not in str(capsys.readouterr())


def test_config_check_redacts_malformed_file(tmp_path, capsys):
    path = tmp_path / "bad.json"
    path.write_text('{"canary-secret"')
    assert diagnostic.main(["--config", str(path)]) == 1
    assert "canary-secret" not in str(capsys.readouterr())


def test_diagnostic_key_errors_have_no_secret_context(monkeypatch):
    monkeypatch.setenv("CAPTAIN_REALMS_KEYS", "canary-secret")
    with pytest.raises(ConfigurationError) as raised:
        diagnostic.load_keys()
    assert raised.value.__context__ is None
    assert "canary" not in repr(raised.value)


async def test_private_diagnostic_login_and_probe_use_fake_http_only(monkeypatch, capsys):
    from realms_fakes import MemoryStore, account, device, oauth, xbox
    from utils.integrations.realms.transport import Response
    from types import SimpleNamespace
    clock = FakeTime()
    class ContextStore(MemoryStore):
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
    store = ContextStore()
    monkeypatch.setattr(diagnostic, "EncryptedTokenStore", lambda *args: store)
    monkeypatch.setattr(diagnostic, "load_keys", lambda: {})
    original_service = diagnostic.RealmsService
    monkeypatch.setattr(diagnostic, "RealmsService", lambda c, h, s: original_service(
        c, h, s, clock=clock, monotonic=clock, sleep=clock.sleep))
    class ContextHTTP(FakeHTTP):
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
    http = ContextHTTP(device(), oauth(), xbox(clock), xbox(clock))
    args = SimpleNamespace(user_id=101, guild_id=202, store_dir=None, key_id="synthetic", action="login")
    await diagnostic.live(args, config(), transport_factory=lambda **k: http)
    output = capsys.readouterr().out
    assert "CANARY-CODE" in output and "Synthetic Player" in output
    assert "canary-refresh" not in output and "canary-access" not in output and "canary-xbox" not in output
    store.account = account()
    args.action = "probe"
    http = ContextHTTP(oauth(), xbox(clock), xbox(clock), xbox(clock),
        Response(200, {"servers": []}))
    await diagnostic.live(args, config(selected_realm_id=None), transport_factory=lambda **k: http)
    assert "Accessible Realm count: 0" in capsys.readouterr().out


def test_cli_restores_logging_state(tmp_path):
    import logging
    path = tmp_path / "disabled.json"
    path.write_text('{"version":1,"realms":{}}')
    previous = logging.root.manager.disable
    assert diagnostic.main(["--config", str(path)]) == 0
    assert logging.root.manager.disable == previous


def test_private_live_confirmation_decline_never_opens_transport(tmp_path, monkeypatch):
    from dataclasses import asdict
    path = tmp_path / "enabled.json"
    path.write_text(json.dumps({"version": 1, "realms": asdict(config())}))
    monkeypatch.setattr(diagnostic.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(diagnostic.sys.stdout, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt: "NO")
    monkeypatch.setattr(diagnostic, "live", lambda *a: pytest.fail("Live path reached"))
    assert diagnostic.main(["login", "--config", str(path), "--user-id", "101", "--guild-id", "202",
        "--store-dir", str(tmp_path), "--key-id", "test", "--allow-live"]) == 2


@pytest.mark.parametrize("show_ids", [False, True])
async def test_private_discovery_identifiers_require_output_opt_in(monkeypatch, capsys, show_ids):
    from unittest.mock import AsyncMock
    from utils.integrations.realms.models import Realm, Snapshot, utcnow
    from realms_fakes import MemoryStore
    class ContextStore(MemoryStore):
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
    class ContextHTTP:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
    fake_client = SimpleNamespace(list_realms=AsyncMock(return_value=Snapshot(
        (Realm("42", "Private Synthetic Realm", "OPEN", None),), utcnow())))
    fake_service = SimpleNamespace(client=lambda p: fake_client, close=AsyncMock())
    monkeypatch.setattr(diagnostic, "RealmsService", lambda *a: fake_service)
    monkeypatch.setattr(diagnostic, "load_keys", lambda: {})
    monkeypatch.setattr(diagnostic, "EncryptedTokenStore", lambda *a: ContextStore())
    args = SimpleNamespace(user_id=101, guild_id=202, store_dir=None, key_id="test", action="probe", show_realm_ids=show_ids)
    await diagnostic.live(args, config(selected_realm_id=None), transport_factory=lambda **k: ContextHTTP())
    output = capsys.readouterr().out
    assert ("Private Synthetic Realm" in output) is show_ids
    assert ("Private Realm selection: 42" in output) is show_ids


def test_validate_enabled_checks_disabled_config_without_activating_it(tmp_path, monkeypatch, capsys):
    from dataclasses import asdict
    path = tmp_path / "prepared.json"
    values = asdict(config())
    values["enabled"] = False
    path.write_text(json.dumps({"version": 1, "realms": values}))
    before = path.read_bytes()
    monkeypatch.setattr(diagnostic, "live", lambda *a: pytest.fail("Live path reached"))
    assert diagnostic.main(["check", "--config", str(path), "--validate-enabled"]) == 0
    assert path.read_bytes() == before
    assert "Enabled settings valid" in capsys.readouterr().out
    values["client_id"] = ""
    path.write_text(json.dumps({"version": 1, "realms": values}))
    assert diagnostic.main(["check", "--config", str(path), "--validate-enabled"]) == 1


def test_windows_powershell_utf8_bom_config_is_supported(tmp_path):
    path = tmp_path / "private.json"
    path.write_text('{"version":1,"realms":{"enabled":false}}', encoding="utf-8-sig")
    assert diagnostic.load_config(path).enabled is False


def test_diagnostic_exposes_only_fixed_http_status_and_retry(monkeypatch, tmp_path, capsys):
    from utils.integrations.realms.errors import HTTPFailure
    def failure(path):
        raise HTTPFailure(429, 120)
    monkeypatch.setattr(diagnostic, "load_config", failure)
    assert diagnostic.main(["check", "--config", str(tmp_path / "unused")]) == 1
    assert capsys.readouterr().err == "Diagnostic stopped: upstream_http_failed\nHTTP status: 429\nRetry after seconds: 120\n"
