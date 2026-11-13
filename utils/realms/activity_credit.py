"""Playtime credit policy: presence 100%, timeline-only coverage 50%."""
from datetime import timezone


class ActivityRows(list):
    def __init__(self):
        super().__init__()
        self.presence = []


class ActivityGroups(dict):
    def __init__(self, groups, credits):
        super().__init__(groups)
        self.credits = credits


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def union_totals(rows, lo=None, hi=None):
    groups = {}
    lo, hi = utc(lo) if lo else None, utc(hi) if hi else None
    for xuid, start, end in rows:
        if not xuid or start is None or end is None:
            continue
        a, b = utc(start), utc(end)
        if lo:
            a = max(a, lo)
        if hi:
            b = min(b, hi)
        if a < b:
            groups.setdefault(xuid, []).append((a, b))
    totals = {}
    for xuid, spans in groups.items():
        merged = []
        for a, b in sorted(spans):
            if merged and a <= merged[-1][1]:
                merged[-1] = merged[-1][0], max(b, merged[-1][1])
            else:
                merged.append((a, b))
        totals[xuid] = sum((b-a).total_seconds() for a, b in merged)
    return totals


def credited_totals(rows, *, lo=None, hi=None):
    all_time = union_totals(rows, lo, hi)
    if not isinstance(rows, ActivityRows):
        return all_time  # Legacy callers supply already authoritative intervals.
    presence = union_totals(rows.presence, lo, hi)
    # Presence is a subset of the combined coverage. Union across both Realm IDs
    # before assigning credit: an overlapping timeline never halves live credit.
    return {xuid: (seconds + presence.get(xuid, 0)) / 2 for xuid, seconds in all_time.items()}


def group_credit(groups, xuid):
    if isinstance(groups, ActivityGroups):
        return groups.credits.get(xuid, 0)
    return sum((b-a).total_seconds() for a, b in groups[xuid])
