"""Shared Season 10 Realm scope and presence-aware stored activity reads."""
from datetime import timedelta
import json

from utils.core_features.__constants import ROOT
from utils.integrations.realms.models import realm_id
from utils.players.activity_models import RealmActivity
from .presence import PresenceSample, prefer_presence
from .activity_credit import ActivityRows


def season_realms(current):
    """A server move does not start a new season or discard its history."""
    old = json.loads((ROOT / 'config' / 'old-coastal-s10-stories.json').read_text(encoding='utf-8'))['realm_id']
    return tuple(dict.fromkeys((realm_id(current), realm_id(old))))


def read_activity(realms, *, lo=None, hi=None):
    """Caller owns DB connection. Presence overrides Stories per source Realm."""
    rows, samples, updates = ActivityRows(), [], []
    has_presence = PresenceSample.table_exists()
    for source in realms:
        query = RealmActivity.select(RealmActivity.xuid, RealmActivity.start,
                                     RealmActivity.end, RealmActivity.last_observed).where(
            (RealmActivity.realm_id == source) & (RealmActivity.status == 'observed') &
            RealmActivity.start.is_null(False) & RealmActivity.end.is_null(False) &
            (RealmActivity.end > RealmActivity.start))
        if lo is not None:
            query = query.where(RealmActivity.end > lo)
        if hi is not None:
            query = query.where(RealmActivity.start < hi)
        records = list(query)
        source_samples = []
        if has_presence:
            query = PresenceSample.select().where(PresenceSample.realm == source)
            if lo is not None:
                query = query.where(PresenceSample.observed >= lo-timedelta(seconds=45))
            if hi is not None:
                query = query.where(PresenceSample.observed <= hi+timedelta(seconds=45))
            source_samples = [(s.observed, json.loads(s.online)) for s in query.order_by(PresenceSample.observed)]
        # An empty roster on the new server cannot erase time on the old server.
        rows.extend(prefer_presence([(r.xuid, r.start, r.end) for r in records], source_samples))
        rows.presence.extend(prefer_presence([], source_samples))
        samples.extend(source_samples)
        updates.extend(r.last_observed for r in records if r.last_observed is not None)
    samples.sort(key=lambda item: item[0])
    updates.extend(stamp for stamp, _ in samples)
    return rows, samples, max(updates, default=None)
