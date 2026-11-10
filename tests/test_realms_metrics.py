from datetime import datetime, timezone
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock

import pytest

from test_realms_client import client
from test_realms_panel import controller
from test_realms_discord import settings, interaction
from realms_fakes import FakeHTTP, FakeTime
from utils.integrations.realms.errors import ProtocolError, HTTPFailure, AccessDenied
from utils.integrations.realms.metrics import Metrics, live_path
from utils.integrations.realms.models import Snapshot
from utils.integrations.realms.transport import Response, STORIES_HOST, AiohttpTransport
from utils.realms.metrics import MetricsController, metrics_embed
from utils.realms.runtime import RealmRuntime
from utils.realms.cog import RealmCommands


def body(**values):
    return {"result": {"realmOnline": True, "values": values}}


@pytest.mark.parametrize("value", [-1, float("nan"), float("inf"), True, "1"])
def test_malformed_values_rejected(value):
    with pytest.raises(ProtocolError):
        Metrics.parse(body(**{"server.cpu": value}))


def test_missing_zero_offline_and_stale_are_distinct():
    data = Metrics.parse(body(**{"server.cpu": 0, "server.players": 0}))
    snapshot = Snapshot(data, datetime.now(timezone.utc))
    fields = {f.name: f.value for f in metrics_embed(snapshot, True, 15).fields}
    assert fields["CPU Usage"] == "0.00%"
    assert fields["Memory Usage"] == "Unavailable"
    assert fields["Players Online"] == "0"
    stale = metrics_embed(snapshot, False, 15).to_dict()
    assert stale["fields"][0]["value"] == "🟡 UNAVAILABLE"
    assert stale["fields"][1]["value"] == "Unavailable"
    offline = Snapshot(Metrics(False, data.values), snapshot.observed_at)
    assert metrics_embed(offline, True, 15).fields[1].value == "Unavailable"


async def test_selected_realm_only_and_fixed_metric_query():
    http = FakeHTTP(Response(200, body(**{"server.players": 3})))
    api = client(http)
    assert (await api.metrics()).data.values["server.players"] == 3
    transport = AiohttpTransport(selected_realm_id="42")
    assert STORIES_HOST + live_path("42") in transport._reads
    for path in (live_path("43"), live_path("42") + "&names=secret", live_path("42").replace("live?", "?")):
        with pytest.raises(AccessDenied):
            await api.request("GET", path)


async def test_runtime_cache_failure_and_permission_backoff():
    clock = FakeTime()
    runtime = RealmRuntime(settings(), monotonic=clock)
    runtime.client = NS(metrics=AsyncMock(return_value=Snapshot(Metrics.parse(body()), datetime.now(timezone.utc))))
    first = await runtime.metrics()
    assert first[1]
    assert await runtime.metrics() == first
    runtime.client.metrics.assert_awaited_once()
    await clock.sleep(16)
    runtime.client.metrics.side_effect = HTTPFailure(403)
    assert await runtime.metrics() == (first[0], False)
    await clock.sleep(60)
    assert await runtime.metrics() == (first[0], False)
    assert runtime.client.metrics.await_count == 2
    await runtime.close()


async def test_separate_message_persistence_restart_and_no_session_writes():
    original, message, channel = controller()
    runtime = original.runtime
    runtime.metrics = AsyncMock(return_value=(Snapshot(Metrics.parse(body()), datetime.now(timezone.utc)), True))
    panel = MetricsController(original.bot, runtime, repository=NS(save=Mock()))
    url = await panel.create(channel)
    assert url == message.jump_url
    assert "realm_panel" in original.bot.settings
    assert "realm_metrics_panel" in original.bot.settings
    runtime.store.save_panel_sessions.assert_not_called()
    restored = MetricsController(original.bot, runtime, repository=NS(save=Mock()))
    await restored.refresh()
    assert channel.send.await_count == 1
    await restored.remove()
    assert "realm_metrics_panel" not in original.bot.settings
    assert "realm_panel" in original.bot.settings


async def test_access_failure_does_not_post_and_nonstaff_cannot_poll():
    original, _, channel = controller()
    original.runtime.metrics = AsyncMock(return_value=(None, False))
    panel = MetricsController(original.bot, original.runtime, repository=NS(save=Mock()))
    with pytest.raises(RuntimeError):
        await panel.create(channel)
    channel.send.assert_not_awaited()
    cog = RealmCommands(original.bot, runtime=original.runtime)
    await cog.manage_metrics(interaction(roles=()), "create")
    assert original.runtime.metrics.await_count == 1
