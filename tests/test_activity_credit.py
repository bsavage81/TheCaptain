from datetime import datetime, timedelta, date, timezone

import pytest

from utils.realms.activity_credit import ActivityRows, credited_totals
from utils.realms.daily_timeline import aggregate, ordered_players, window
from utils.realms.leaderboard import rankings


def test_hour_of_timeline_only_receives_half_an_hour():
    start = datetime(2026, 11, 1)
    rows = ActivityRows()
    rows.append(('a', start, start+timedelta(hours=1)))
    assert credited_totals(rows) == {'a': 1800}


def test_mixed_hour_keeps_live_credit_and_halves_only_remaining_time():
    start = datetime(2026, 11, 1)
    rows = ActivityRows()
    rows.extend([('a', start, start+timedelta(hours=1))] * 2)
    rows.presence.append(('a', start, start+timedelta(minutes=20)))
    rows.extend(rows.presence)
    assert credited_totals(rows) == {'a': 2400}
    assert rankings(rows, start+timedelta(hours=1)) == [('a', 2400)]


def test_live_overlap_across_servers_is_not_discounted_or_double_counted():
    start = datetime(2026, 11, 1)
    rows = ActivityRows()
    rows.presence = [('a',start,start+timedelta(hours=1))] * 2
    rows.extend(rows.presence + [('a',start,start+timedelta(hours=2))])
    assert credited_totals(rows) == {'a': 5400}


@pytest.mark.parametrize('day', [date(2026, 11, 1), date(2026, 3, 8)])
def test_daily_credit_uses_local_day_bounds_and_keeps_full_coverage_bars(day):
    lo, hi = window(day)
    rows = ActivityRows()
    rows.append(('a',lo-timedelta(hours=1),hi+timedelta(hours=1)))
    groups, count, total = aggregate(rows, day)
    assert groups['a'] == [(lo,hi)] and count == 1
    assert total == (hi-lo).total_seconds()/2 == groups.credits['a']


def test_daily_order_and_leaderboard_use_credited_not_raw_duration():
    lo, hi = window(date(2026, 11, 1))
    rows = ActivityRows()
    rows.append(('history',lo,lo+timedelta(hours=3)))
    rows.presence.append(('live',lo,lo+timedelta(hours=2)))
    rows.extend(rows.presence)
    groups, _, total = aggregate(rows,date(2026,11,1))
    assert ordered_players(groups) == ['live','history']
    assert rankings(rows, hi) == [('live',7200),('history',5400)]
    assert total == 12600


def test_credit_clips_future_time_and_ignores_malformed_intervals():
    start = datetime(2026,11,1)
    rows = ActivityRows()
    rows.extend([('a',start,start+timedelta(hours=2)),('b',None,None),('c',start,start)])
    rows.presence.append(('a',start,start+timedelta(minutes=30)))
    rows.extend(rows.presence)
    assert rankings(rows,start+timedelta(hours=1)) == [('a',2700)]
    # Aware and naive DB datetimes refer to the same UTC interval.
    assert credited_totals(rows,hi=(start+timedelta(hours=1)).replace(tzinfo=timezone.utc)) == {'a':2700}
