from datetime import datetime
from types import SimpleNamespace as NS
from unittest.mock import Mock, AsyncMock
import subprocess
import pytest
import discord
from utils.core_features import __special_methods as lifecycle
from utils.core_features.__constants import ROOT


def test_banner_uses_live_metadata_and_never_prints_credentials():
    bot=NS(user=NS(name="The Captain"), settings={"database_ip":"db.example.invalid", "database_username":"private-user", "database_password":"private-password", "token":"private-token"}, guilds=[1,2,3], users=list(range(560)))
    banner=lifecycle.format_ready_banner(bot,"abc1234",datetime(2026,10,28,12,30))
    assert "Bot Account: The Captain" in banner
    assert f"Discord API Wrapper Version: {discord.__version__}" in banner
    assert "The Captain Version: abc1234" in banner
    assert "Selected Database: External (db.example.invalid)" in banner
    assert "Current Time: 2026-10-28 12:30:00.000000" in banner
    assert "Guilds: 3" in banner and "Members: 560" in banner
    assert "private-" not in banner


@pytest.mark.parametrize("error",[FileNotFoundError(),subprocess.TimeoutExpired("git",3)])
def test_missing_git_or_timeout_does_not_break_ready(monkeypatch,error):
    monkeypatch.setattr(lifecycle.subprocess,"run",Mock(side_effect=error))
    assert lifecycle.get_revision()=="unknown"


def test_git_revision_is_cwd_independent(monkeypatch,tmp_path):
    monkeypatch.chdir(tmp_path)
    run=Mock(return_value=NS(stdout="abc1234\n"))
    monkeypatch.setattr(lifecycle.subprocess,"run",run)
    assert lifecycle.get_revision()=="abc1234"
    assert run.call_args.kwargs["cwd"]==ROOT
    assert run.call_args.kwargs["timeout"]==3
    assert run.call_args.args[0]==["git","rev-parse","--short","HEAD"]


async def test_ready_prints_banner(monkeypatch,capsys):
    monkeypatch.setattr(lifecycle.asyncio,"to_thread",AsyncMock(return_value="abc1234"))
    bot=NS(user=NS(name="The Captain"),settings={"database_ip":"localhost"},guilds=[],users=[])
    await lifecycle.on_ready_(bot)
    output=capsys.readouterr().out
    assert "Selected Database: Local (localhost)" in output
    assert "The Captain Version: abc1234" in output
    assert "Cogs, libraries, and views have successfully been initialized." in output
