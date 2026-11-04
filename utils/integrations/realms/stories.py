"""Private, bounded Stories observations. Timestamps are not confirmed sessions."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import hashlib

from .errors import ProtocolError
from .profiles import valid_xuid


@dataclass(frozen=True)
class StoryInterval:
    xuid: str | None = field(repr=False)
    identity_key: str = field(repr=False)
    raw_start: str = field(repr=False)
    raw_end: str = field(repr=False)
    start: datetime | None = field(repr=False)
    end: datetime | None = field(repr=False)
    status: str
    reason: str


def parse_stories(body, observed_at):
    if observed_at.tzinfo is None:
        raise ProtocolError()
    if not isinstance(body, dict) or not isinstance(body.get("result"), dict):
        raise ProtocolError()
    activity = body["result"].get("activity")
    if not isinstance(activity, dict) or len(activity) > 10000:
        raise ProtocolError()
    result = []
    for identity, entries in activity.items():
        if not isinstance(identity, str) or not isinstance(entries, list):
            raise ProtocolError()
        for entry in entries:
            if len(result) >= 10000:
                raise ProtocolError()
            if not isinstance(entry, dict):
                raise ProtocolError()
            start, end = entry.get("s"), entry.get("e")
            try:
                raw_start = json.dumps(start, sort_keys=True, allow_nan=False)
                raw_end = json.dumps(end, sort_keys=True, allow_nan=False)
            except (ValueError, TypeError):
                raise ProtocolError() from None
            reason = ""
            parsed_start = parsed_end = None
            if not valid_xuid(identity):
                reason = "invalid_identity"
            elif type(start) is not int or type(end) is not int:
                reason = "invalid_timestamp_type"
            elif start <= 0 or end <= 0:
                reason = "nonpositive_timestamp"
            elif start < 1242518400:
                reason = "predates_minecraft"
            elif end <= start:
                reason = "nonpositive_interval"
            elif start > observed_at.timestamp() + 300 or end > observed_at.timestamp() + 300:
                reason = "future_timestamp"
            else:
                try:
                    parsed_start = datetime.fromtimestamp(start, timezone.utc)
                    parsed_end = datetime.fromtimestamp(end, timezone.utc)
                except (ValueError, OverflowError, OSError):
                    reason = "timestamp_out_of_range"
            # Unexpected malformed fields can be large; retain a bounded fingerprint
            # instead of overflowing SQL TEXT or retaining unrelated payload content.
            if len(raw_start) > 512:
                raw_start = json.dumps({"oversize_sha256": hashlib.sha256(raw_start.encode()).hexdigest()})
            if len(raw_end) > 512:
                raw_end = json.dumps({"oversize_sha256": hashlib.sha256(raw_end.encode()).hexdigest()})
            result.append(StoryInterval(identity if valid_xuid(identity) else None,
                hashlib.sha256(identity.encode()).hexdigest(), raw_start, raw_end,
                parsed_start, parsed_end, "quarantined" if reason else "observed", reason))
    return tuple(result)
