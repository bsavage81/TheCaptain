"""Private idempotent observed activity; never drives roles or check-in policy."""
from datetime import timezone
import hashlib
import json

from utils.database.__database import db
from utils.integrations.realms.models import realm_id
from utils.integrations.realms.profiles import valid_xuid, valid_gamertag
from .models import Identity, Player, utcnow
from .activity_models import RealmActivity


def verified_player(xuid):
    targets = {p.id for p in Player.select().where(Player.xuid == xuid)}
    targets.update(i.player_id for i in Identity.select().where(
        (Identity.kind == "xuid") & (Identity.value == xuid) & Identity.verified))
    return next(iter(targets)) if len(targets) == 1 else None


def link_xbox(player_id, xuid, *, actor, evidence, gamertag=None):
    """Staff-reviewed evidence links a stable ID; never merge by name or overwrite."""
    if not valid_xuid(xuid) or type(actor) is not int or actor <= 0 or not isinstance(evidence, str) or not 8 <= len(evidence.strip()) <= 1000:
        raise ValueError("Reviewed identity evidence and valid identifiers required")
    if gamertag is not None and not valid_gamertag(gamertag):
        raise ValueError("Invalid display name")
    with db.atomic():
        player = Player.get_by_id(player_id)
        owners = {p.id for p in Player.select().where(Player.xuid == xuid)}
        owners.update(i.player_id for i in Identity.select().where(
            (Identity.kind == "xuid") & (Identity.value == xuid) & Identity.verified))
        old = {i.value for i in player.identities.where((Identity.kind == "xuid") & Identity.verified)}
        if owners - {player.id} or player.xuid not in (None, xuid) or old - {xuid}:
            raise ValueError("Conflicting verified Xbox link; manual review required")
        # Conditional write plus unique Player.xuid serializes competing linkers.
        changed = Player.update(xuid=xuid, updated_at=utcnow()).where(
            (Player.id == player.id) & ((Player.xuid.is_null()) | (Player.xuid == xuid))).execute()
        # MySQL may report zero affected rows for an identical link in the same
        # timestamp second. Accept that idempotent case, not a different identity.
        if not changed and Player.get_by_id(player.id).xuid != xuid:
            raise ValueError("Concurrent identity change; review again")
        source = "staff_xbox:" + str(actor) + ":" + hashlib.sha256(evidence.strip().encode()).hexdigest()
        Identity.get_or_create(player=player.id, kind="xuid", value=xuid, source=source,
                               defaults={"verified": True})
        if gamertag:
            Identity.get_or_create(player=player.id, kind="gamertag", value=gamertag, source=source,
                                   defaults={"verified": False})
            # Display observations must not overwrite existing names/verified links.
            Player.update(gamertag=gamertag).where((Player.id == player.id) & (Player.gamertag == "")).execute()
        return reconcile_unmatched(xuid)


def reconcile_unmatched(xuid):
    target = verified_player(xuid)
    if target is None or not RealmActivity.table_exists():
        return 0
    return RealmActivity.update(player=target).where(
        (RealmActivity.xuid == xuid) & RealmActivity.player.is_null()).execute()


def ingest(snapshot, selected_realm):
    """Caller owns DB connection; one transactional import, no profile creation."""
    selected_realm = realm_id(selected_realm)
    if snapshot.observed_at.tzinfo is None:
        raise ValueError("Observation must be UTC-aware")
    observed = snapshot.observed_at.astimezone(timezone.utc).replace(tzinfo=None)
    counts = dict(created=0, existing=0, quarantined=0, unmatched=0)
    with db.atomic():
        for item in snapshot.data:
            fingerprint = json.dumps([selected_realm, "realms_stories", item.identity_key,
                                      item.raw_start, item.raw_end], separators=(",", ":"))
            key = hashlib.sha256(fingerprint.encode()).hexdigest()
            target = verified_player(item.xuid) if item.xuid else None
            row, created = RealmActivity.get_or_create(key=key, defaults={
                "player": target, "realm_id": selected_realm, "xuid": item.xuid,
                "raw_start": item.raw_start, "raw_end": item.raw_end,
                "start": item.start.replace(tzinfo=None) if item.start else None,
                "end": item.end.replace(tzinfo=None) if item.end else None,
                "status": item.status, "reason": item.reason,
                "first_observed": observed, "last_observed": observed})
            if not created:
                RealmActivity.update(last_observed=observed).where(
                    (RealmActivity.id == row.id) & (RealmActivity.last_observed < observed)).execute()
                if row.player_id is None and target is not None:
                    RealmActivity.update(player=target).where(
                        (RealmActivity.id == row.id) & RealmActivity.player.is_null()).execute()
            counts["created" if created else "existing"] += 1
            counts["quarantined"] += row.status == "quarantined"
            counts["unmatched"] += row.player_id is None and target is None
    return counts


def observed_statistics(player_id, *, start, end, selected_realm=None):
    """Private design foundation: clipped UTC union, not verified session totals."""
    if start.tzinfo is None or end.tzinfo is None or end <= start:
        raise ValueError("Explicit aware start/end window required")
    lo, hi = (v.astimezone(timezone.utc).replace(tzinfo=None) for v in (start, end))
    query = RealmActivity.select().where((RealmActivity.player == player_id) &
        (RealmActivity.status == "observed") & (RealmActivity.end > lo) & (RealmActivity.start < hi))
    if selected_realm is not None:
        query = query.where(RealmActivity.realm_id == realm_id(selected_realm))
    intervals = sorted((max(lo, row.start), min(hi, row.end)) for row in query)
    merged = []
    for a, b in intervals:
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(b, merged[-1][1]))
        else:
            merged.append((a, b))
    return {"observed_seconds": sum((b-a).total_seconds() for a, b in merged),
            "recorded_intervals": len(intervals), "merged_activity_spans": len(merged),
            "most_recent_observed_end": max((b for _, b in intervals), default=None),
            "confirmed_sessions": None, "coverage": "incomplete_unverified_stories"}
