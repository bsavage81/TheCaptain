"""Aggregate Pro telemetry, with missing values kept distinct from zero."""
from dataclasses import dataclass
import math

from .errors import ProtocolError

METRIC_NAMES = ("server.cpu", "server.memory", "server.tick-time", "server.players")


def live_path(world):
    return f"/api/v1.0/telemetry/worlds/{world}/metrics/live?" + "&".join(
        "names=" + name for name in METRIC_NAMES)


@dataclass(frozen=True)
class Metrics:
    online: bool
    values: dict

    @classmethod
    def parse(cls, body):
        result = body.get("result") if isinstance(body, dict) else None
        if not isinstance(result, dict) or type(result.get("realmOnline")) is not bool:
            raise ProtocolError()
        values = result.get("values", {})
        if not isinstance(values, dict):
            raise ProtocolError()
        clean = {}
        for name in METRIC_NAMES:
            value = values.get(name)
            if value is not None:
                if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                    raise ProtocolError()
                if name == "server.players" and value != int(value):
                    raise ProtocolError()
            clean[name] = value
        return cls(result["realmOnline"], clean)
