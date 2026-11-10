"""Separate persistent aggregate metrics panel; no player/session data."""
import discord

from .panel import PanelController


def metrics_embed(snapshot, available, interval):
    data = snapshot.data if snapshot is not None and available else None
    online = data.online if data else None
    label, colour = {True: ("🟢 ONLINE", 0x2ECC71), False: ("🔴 OFFLINE", 0xE74C3C)}.get(
        online, ("🟡 UNAVAILABLE", 0xF1C40F))
    embed = discord.Embed(title="📊 Coastal Craft | Live Server Metrics", colour=colour)
    embed.add_field(name="Server", value=label, inline=False)
    fields = (("CPU Usage", "server.cpu", "%"), ("Memory Usage", "server.memory", "%"),
              ("Tick Time", "server.tick-time", " ms"), ("Players Online", "server.players", ""))
    for title, key, unit in fields:
        value = data.values.get(key) if data and online else None
        rendered = (f"{int(value)}" if key == "server.players" else f"{value:.2f}{unit}") if value is not None else "Unavailable"
        embed.add_field(name=title, value=rendered, inline=True)
    observed = f"<t:{int(snapshot.observed_at.timestamp())}:T>" if snapshot else "Unavailable"
    embed.add_field(name="Last successful reading", value=observed, inline=False)
    embed.set_footer(text=f"Realms Pro telemetry • Refresh: {interval}s • " +
                     ("Aggregate server metrics" if available else "Readings unavailable; retrying with backoff"))
    return embed


class MetricsRuntime:
    """Adapt shared metrics reads to the existing persistent-message lifecycle."""
    def __init__(self, runtime):
        self.runtime = runtime
        if hasattr(runtime, "config"):
            self.config = runtime.config

    async def observe(self, **kwargs):
        return await self.runtime.metrics(), 0


class MetricsController(PanelController):
    setting_key = "realm_metrics_panel"

    def __init__(self, bot, runtime, **kwargs):
        super().__init__(bot, MetricsRuntime(runtime), **kwargs)

    async def update_sessions(self, view):
        # Metrics never read or write the player-duration cache.
        pass

    def render(self, view, interval):
        return metrics_embed(*view, interval)

    async def create(self, channel):
        snapshot, available = await self.runtime.runtime.metrics()
        if not available or snapshot is None:
            raise RuntimeError("Realm Pro metrics access unavailable")
        return await super().create(channel)
