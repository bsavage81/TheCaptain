"""Deployment must fail closed on bad HTTP responses or stale server code."""
import json
from types import SimpleNamespace as NS
from unittest.mock import Mock
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
import pytest
from scripts import panel_deploy as deploy

REVISION = "a" * 40


class Response:
    def __init__(self, status=204, body=b""):
        self.status, self.body = status, body
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, *args):
        return self.body


def test_restart_normalizes_url_and_requires_acknowledgement():
    client = deploy.Panel("https://example.invalid/", "synthetic-key")
    client.opener = NS(open=Mock(return_value=Response()))
    client.restart()
    request = client.opener.open.call_args.args[0]
    assert request.full_url == "https://example.invalid/api/client/servers/5ff9cb52/power"
    assert request.method == "POST"
    assert json.loads(request.data) == {"signal": "restart"}


@pytest.mark.parametrize("status", [200, 301, 401, 403, 404, 500])
def test_restart_http_failures_never_report_success(status):
    client = deploy.Panel("https://example.invalid", "synthetic-key")
    client.opener = NS(open=Mock(return_value=Response(status)))
    with pytest.raises(deploy.PanelError) as error:
        client.restart()
    assert error.value.status == status
    assert "synthetic-key" not in str(error.value)


def test_redirects_cannot_forward_credentials():
    assert deploy.NoRedirect().redirect_request(None, None, 302, "redirect", {}, "https://other.invalid") is None
    client = deploy.Panel("https://example.invalid", "synthetic-key")
    client.opener = NS(open=Mock(side_effect=HTTPError("https://example.invalid", 302, "redirect", {}, None)))
    with pytest.raises(deploy.PanelError) as error:
        client.get("/servers/5ff9cb52")
    assert error.value.status == 302


@pytest.mark.parametrize("url", ["http://example.invalid", "https://secret@example.invalid", "https://example.invalid?token=secret"])
def test_panel_url_requires_verified_https_origin(url):
    with pytest.raises(ValueError):
        deploy.Panel(url, "synthetic-key")


def main_fixture(monkeypatch, report):
    client = NS(get=Mock(return_value={"attributes": {"identifier": deploy.EXPECTED_SERVER}}), restart=Mock())
    monkeypatch.setenv("PANEL_URL", "https://example.invalid/")
    monkeypatch.setenv("PANEL_API_KEY", "synthetic-key")
    monkeypatch.setenv("PANEL_SERVER_ID", deploy.EXPECTED_SERVER)
    monkeypatch.setattr(deploy, "Panel", Mock(return_value=client))
    monkeypatch.setattr(deploy.sys, "argv", ["panel_deploy.py", "--restart-and-verify", "--expected-revision", REVISION])
    monkeypatch.setattr(deploy, "inspect", Mock(return_value=report))
    monkeypatch.setattr(deploy.time, "sleep", Mock())
    monkeypatch.setattr(deploy.time, "monotonic", Mock(side_effect=[0, 0, 181]))
    return client


@pytest.mark.parametrize("report", [
    {"guide_matches_checkout": False, "server_commit": "b" * 40},
    {"guide_matches_checkout": True, "server_commit": REVISION, "console_signals": {"ready_revisions": ["bbbbbbb"]}},
    {"guide_matches_checkout": True, "server_commit": "b" * 40, "console_signals": {"ready_revisions": [REVISION[:7]]}},
    {"guide_matches_checkout": True, "portal_source_matches_checkout": False,
     "server_commit": REVISION, "console_signals": {"ready_revisions": [REVISION[:7]]}},
])
def test_stale_source_or_old_ready_banner_fails_deployment(monkeypatch, capsys, report):
    client = main_fixture(monkeypatch, report)
    with pytest.raises(ValueError, match="expected source"):
        deploy.main()
    client.restart.assert_called_once()
    output = capsys.readouterr().out
    assert '"deployment_verified": false' in output
    assert "synthetic-key" not in output


def test_only_matching_files_commit_and_ready_banner_pass(monkeypatch, capsys):
    client = main_fixture(monkeypatch, {"guide_matches_checkout": True, "server_commit": REVISION,
        "console_signals": {"ready_revisions": [REVISION[:7]]}})
    deploy.main()
    client.restart.assert_called_once()
    assert '"deployment_verified": true' in capsys.readouterr().out


def test_wrong_server_cannot_be_restarted(monkeypatch):
    client = main_fixture(monkeypatch, {})
    monkeypatch.setenv("PANEL_SERVER_ID", "another-server")
    with pytest.raises(ValueError):
        deploy.main()
    client.restart.assert_not_called()


class FilesPanel:
    def __init__(self):
        self.files = {"/.git/refs/heads/main": deploy.LEGACY_REVISION + "\n",
                      "/botconfig.example.json": '{"Coastal":123}',
                      "/botconfig.json": "private-runtime-config", "/.env": "private-environment"}
        self.writes = []
    def get(self, path, raw=False):
        if "/files/list?" in path:
            return {"data": [{"attributes": {"name": ".database-backups", "is_file": False}}]}
        name = parse_qs(urlsplit(path).query)["file"][0]
        return self.files[name]
    def post(self, path, body, **kwargs):
        name = parse_qs(urlsplit(path).query)["file"][0]
        self.writes.append(name)
        self.files[name] = body


def test_example_repair_preserves_edits_and_changes_only_tracked_example(monkeypatch):
    panel = FilesPanel()
    monkeypatch.setattr(deploy, "legacy_example", lambda: '{"Coastal":0}\n')
    result = deploy.repair_tracked_example(panel)
    backup = result["backup_path"]
    assert panel.files[backup] == '{"Coastal":123}'
    assert panel.writes == [backup, "/botconfig.example.json"]
    assert panel.files["/botconfig.example.json"] == '{"Coastal":0}\n'
    assert panel.files["/botconfig.json"] == "private-runtime-config"
    assert panel.files["/.env"] == "private-environment"


def test_example_repair_stops_on_unverified_backup(monkeypatch):
    panel = FilesPanel()
    monkeypatch.setattr(deploy, "legacy_example", lambda: '{"Coastal":0}\n')
    original_get = panel.get
    def broken_backup(path, **kwargs):
        if ".database-backups" in path:
            return "mismatched-backup"
        return original_get(path, **kwargs)
    monkeypatch.setattr(panel, "get", broken_backup)
    with pytest.raises(ValueError, match="backup did not verify"):
        deploy.repair_tracked_example(panel)
    assert panel.files["/botconfig.example.json"] == '{"Coastal":123}'


def test_example_repair_will_not_touch_another_revision(monkeypatch):
    panel = FilesPanel()
    panel.files["/.git/refs/heads/main"] = "b" * 40
    monkeypatch.setattr(deploy, "legacy_example", lambda: '{"Coastal":0}\n')
    with pytest.raises(ValueError, match="checkout changed"):
        deploy.repair_tracked_example(panel)
    assert panel.writes == []
