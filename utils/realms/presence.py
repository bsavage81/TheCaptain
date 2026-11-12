"""Timestamped complete presence samples and precedence over coarse Stories history."""
import json
from datetime import timedelta
from peewee import CharField, DateTimeField, TextField
from utils.database.__database import BaseModel


class PresenceSample(BaseModel):
    realm = CharField(max_length=20)
    observed = DateTimeField()
    online = TextField()

    class Meta:
        table_name = 'captain_realm_presence'
        indexes = ((('realm', 'observed'), True),)


def save_sample(view, realm):
    from .panel import Sessions
    if not Sessions.authoritative(view):
        return
    from datetime import timezone
    observed = view.activity.observed_at.astimezone(timezone.utc).replace(tzinfo=None)
    online = sorted(p.xuid for p in view.activity.data.players if p.online is True)
    PresenceSample.get_or_create(realm=realm, observed=observed, defaults={'online': json.dumps(online)})


def prefer_presence(stories, samples, *, max_gap=45):
    """Use complete polling windows as authoritative; retain Stories only in gaps.

    A transition is timestamped at its first observation, not claimed as an exact login.
    Never extend online state past the final sample or across a polling outage.
    """
    coverage, primary = [], []
    previous = None
    for stamp, online in sorted(samples, key=lambda item: item[0]):
        if previous:
            start, before = previous
            if 0 < (stamp-start).total_seconds() <= max_gap:
                coverage.append((start, stamp))
                primary.extend((xuid, start, stamp) for xuid in before)
        previous = stamp, set(online)
    # Merge contiguous coverage to avoid per-sample subtraction work.
    merged = []
    for a, b in coverage:
        if merged and a <= merged[-1][1]:
            merged[-1] = merged[-1][0], max(b, merged[-1][1])
        else:
            merged.append((a, b))
    output = list(primary)
    for xuid, a, b in stories:
        pieces = [(a, b)]
        for lo, hi in merged:
            pieces = [(c, d) for start, end in pieces for c, d in
                      ((start, min(end, lo)), (max(start, hi), end)) if c < d]
        output.extend((xuid, start, end) for start, end in pieces)
    return output


def verify_future_intervals(snapshot, view, now):
    """Cross-check identities against fresh complete presence, never a future endpoint."""
    from .panel import Sessions
    future = {item.xuid for item in snapshot.data
              if item.reason == 'future_timestamp' and item.xuid}
    fresh = (Sessions.authoritative(view) and
             0 <= (now-view.activity.observed_at).total_seconds() <= 45)
    online = {p.xuid for p in view.activity.data.players if p.online is True} if fresh else set()
    return {xuid: ('online' if xuid in online else 'offline') if fresh else 'unknown'
            for xuid in future}
