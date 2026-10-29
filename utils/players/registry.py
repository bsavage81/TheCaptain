"""Conservative, evidence-based matching and repeatable reviewed imports."""
import hashlib
import json
from difflib import SequenceMatcher
from peewee import DatabaseError
from utils.database.__database import db
from .models import Identity, ImportRecord, Participation, Player, utcnow


def stable_id(value):
    value = str(value or "").strip()
    # Do not accept rounded scientific notation, floats, mentions or arbitrary contact text.
    return int(value) if value.isascii() and value.isdigit() and 15 <= len(value) <= 20 and int(value) < 2**63 else None


def record_key(record):
    # Bot-assigned entry IDs are stable across decisions and row movement.
    identity = {"source": record["source"], "season": record["season"]}
    if "#entry=" not in record["source"]:
        identity.update({k: record.get(k) for k in ("discord_id", "gamertag", "discord_name", "application_date")})
    return hashlib.sha256(json.dumps(identity, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def matches(record, members=()):
    """Return confident target only for independently verified stable identifiers."""
    targets = set()
    for kind, field in (("discord_id", Player.discord_id), ("xuid", Player.xuid)):
        value = record.get(kind)
        if value and record.get(f"{kind}_verified"):
            targets.update(p.id for p in Player.select().where(field == value))
            targets.update(i.player_id for i in Identity.select().where(
                (Identity.kind == kind) & (Identity.value == str(value)) & Identity.verified))
    if len(targets) > 1:
        return {"state": "conflict", "candidates": sorted(targets)}
    if targets:
        target = Player.get_by_id(next(iter(targets)))
        # Even one matched identifier cannot override a conflicting current stable identity.
        for kind in ("discord_id", "xuid"):
            if record.get(kind) and record.get(f"{kind}_verified") and getattr(target, kind) not in (None, record[kind]):
                return {"state": "conflict", "candidates": [target.id]}
        return {"state": "confident", "candidates": [target.id]}
    suggestions = []
    names = {str(record.get(k, "")).strip().casefold() for k in ("gamertag", "discord_name")}
    names.discard("")
    for player in Player.select():
        known = {player.gamertag.casefold(), player.discord_name.casefold()}
        known.update(i.value.casefold() for i in player.identities if i.kind in ("gamertag", "discord_name"))
        if names & known or any(SequenceMatcher(None, a, b).ratio() >= .85 for a in names for b in known if b):
            suggestions.append(f"player:{player.id}")
    for member in members:
        if member.bot:
            continue
        if stable_id(record.get("discord_id")) == member.id and record.get("discord_id_verified"):
            continue  # A trusted ID can create a profile without name matching.
        known = {str(member.name).casefold(), str(member.display_name).casefold()}
        if names & known or any(SequenceMatcher(None, a, b).ratio() >= .85 for a in names for b in known if b):
            suggestions.append(f"discord:{member.id}")
    return {"state": "review" if suggestions or record.get("issues") else "new", "candidates": suggestions}


def stage(records, members=()):
    """Persist review queue only. No profiles/participation are imported."""
    counts = {}
    records = list(records)
    name_groups = {}
    id_groups = {}
    for record in records:
        key = record_key(record)
        for kind in ("gamertag", "discord_name"):
            name = str(record.get(kind, "")).strip().casefold()
            if name:
                name_groups.setdefault((kind, name), set()).add(key)
        if record.get("discord_id_verified") and record.get("discord_id"):
            id_groups.setdefault(record["discord_id"], set()).add(key)
    counts["possible_duplicate_name_groups"] = sum(len(keys) > 1 for keys in name_groups.values())
    counts["repeated_verified_identity_groups"] = sum(len(keys) > 1 for keys in id_groups.values())
    member_ids = {m.id for m in members}
    for record in records:
        with db.atomic():
            match = matches(record, members)
            related = set()
            for kind in ("gamertag", "discord_name"):
                related.update(name_groups.get((kind, str(record.get(kind, "")).strip().casefold()), set()))
            related.discard(record_key(record))
            if related:
                match["other_source_candidates"] = sorted(related)
                if match["state"] == "new":
                    match["state"] = "review"
            if record.get("discord_id_verified"):
                record = dict(record, discord_membership="present_at_discovery" if record["discord_id"] in member_ids else "absent_at_discovery")
            row, created = ImportRecord.get_or_create(key=record_key(record), defaults={
                "source": record["source"], "season": record["season"],
                "payload": json.dumps(record), "note": json.dumps(match),
                "state": "pending"})
            if not created and json.loads(row.payload) != record:
                counts["changed_sources_require_review"] = counts.get("changed_sources_require_review", 0) + 1
        counts["discovered"] = counts.get("discovered", 0) + 1
        counts[match["state"]] = counts.get(match["state"], 0) + 1
        counts["staged" if created else "existing"] = counts.get("staged" if created else "existing", 0) + 1
        key = f"season_{record['season']}"
        counts[key] = counts.get(key, 0) + 1
    counts["members_without_profile"] = sum(not m.bot and not Player.select().where(Player.discord_id == m.id).exists() for m in members)
    counts["unique_candidates"] = len({(r.get("discord_id") if r.get("discord_id_verified") else record_key(r)) for r in records})
    counts["unmatched_historical"] = sum(r.get("discord_id") not in member_ids for r in records)
    return counts


def review(record_id, actor, *, player_id=None, discord_id=None, reject=False):
    with db.atomic():
        row = ImportRecord.get_by_id(record_id)
        if row.state == "imported":
            raise ValueError("Already imported; cannot change its identity mapping")
        if player_id is not None:
            Player.get_by_id(player_id)
        record = json.loads(row.payload)
        if discord_id is not None:
            if not stable_id(discord_id):
                raise ValueError("Invalid verified Discord ID")
            if record.get("discord_id_verified") and record.get("discord_id") != discord_id:
                raise ValueError("Conflicting verified Discord ID requires separate evidence review")
            record["discord_id"] = discord_id
            record["discord_id_verified"] = True
            record["identity_confirmation"] = f"staff:{actor}"
        # Identity corrections remain in the reviewed payload; source key stays immutable.
        changed = ImportRecord.update(payload=json.dumps(record), player=player_id,
            state="rejected" if reject else "approved", reviewed_by=actor, reviewed_at=utcnow()).where(
                (ImportRecord.id == row.id) & (ImportRecord.state.not_in(["imported", "importing"]))).execute()
        if not changed:
            raise ValueError("Record was imported concurrently; review was not changed")


def import_record(record_id):
    """One transaction per approved source; retries cannot duplicate profiles or history."""
    with db.atomic():
        # Conditional claim serializes concurrent importers on both supported backends.
        if not ImportRecord.update(state="importing").where(
                (ImportRecord.id == record_id) & (ImportRecord.state == "approved")).execute():
            return False
        row = ImportRecord.get_by_id(record_id)
        record = json.loads(row.payload)
        found = matches(record)
        if found["state"] == "conflict":
            raise ValueError("Conflicting verified identity; import blocked")
        target = row.player_id or (found["candidates"][0] if found["state"] == "confident" else None)
        if row.player_id and found["state"] == "confident" and target != found["candidates"][0]:
            raise ValueError("Reviewed target conflicts with verified identifier")
        player = Player.get_by_id(target) if target else Player.create()
        for kind in ("discord_id", "xuid"):
            value = record.get(kind)
            if value and record.get(f"{kind}_verified"):
                if getattr(player, kind) not in (None, value):
                    raise ValueError("Cannot overwrite verified identity")
                setattr(player, kind, value)
        for kind in ("discord_name", "gamertag"):
            value = record.get(kind, "")
            if value and not getattr(player, kind):
                setattr(player, kind, value)
        if player.first_season is None or row.season < player.first_season:
            player.first_season = row.season
        date = record.get("application_date")
        if date and (not player.first_application or date < player.first_application):
            player.first_application = date
        player.updated_at = utcnow()
        player.save()
        for kind in ("discord_id", "xuid", "discord_name", "gamertag"):
            if record.get(kind):
                Identity.get_or_create(player=player, kind=kind, value=str(record[kind]), source=row.key,
                                       defaults={"verified": bool(record.get(f"{kind}_verified"))})
        Participation.get_or_create(player=player, season=row.season, source=row.key, defaults={
            "application_date": date, "application_status": record.get("application_status", "unknown"),
            "discord_membership": record.get("discord_membership", "unknown"),
            "realm_status": "unknown"})
        row.player = player
        row.state = "imported"
        row.save()
        return True


def import_approved():
    result = {"imported": 0, "blocked": []}
    for row in ImportRecord.select().where(ImportRecord.state == "approved"):
        try:
            result["imported"] += int(import_record(row.id))
        except (ValueError, DatabaseError):
            result["blocked"].append(row.id)
    return result


def capture_current(record, *, fresh_submission=False):
    """Trusted live bot submission, distinct from administrator-confirmed archive imports."""
    with db.atomic():
        row, created = ImportRecord.get_or_create(key=record_key(record), defaults={
            "source": record["source"], "season": record["season"], "payload": json.dumps(record),
            "state": "approved", "note": "live_bot_submission"})
        if created:
            import_record(row.id)
        if row.state == "imported" or created:
            row = ImportRecord.get_by_id(row.id)
            if created and fresh_submission:
                player = Player.get_by_id(row.player_id)
                for kind in ("discord_name", "gamertag"):
                    value = record.get(kind)
                    protected = Identity.select().where((Identity.player == player) &
                        (Identity.kind == kind) & (Identity.value == getattr(player, kind)) & Identity.verified).exists()
                    if value and not protected:
                        setattr(player, kind, value)
                player.updated_at = utcnow()
                player.save()
            Participation.update(application_status=record.get("application_status", "unknown")).where(
                (Participation.player == row.player_id) & (Participation.source == row.key)).execute()


def observe_discord(player, username, guild_id):
    """An authenticated interaction proves the current Discord username association."""
    username = str(username)[:255]
    Identity.get_or_create(player=player, kind="discord_name", value=username,
                           source=f"discord_guild:{guild_id}", defaults={"verified": True})
    if player.discord_name != username:
        player.discord_name = username
        player.updated_at = utcnow()
        player.save()
