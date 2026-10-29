"""Calendar periods, eligibility and durable delivery claims."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from peewee import IntegrityError
from utils.database.__database import db
from .models import CheckIn, Participation, Period, Player, Reminder, utcnow


def validate(settings):
    ZoneInfo(settings.get("checkin_timezone", "America/Chicago"))
    for key in ("profiles_enabled", "checkin_enabled", "checkin_announcements_enabled", "checkin_reminders_enabled"):
        if key in settings and type(settings[key]) is not bool:
            raise ValueError(f"{key} must be a boolean")
    if type(settings.get("checkin_season", 10)) is not int or settings.get("checkin_season", 10) < 1:
        raise ValueError("checkin_season must be positive")
    days = settings.get("checkin_reminder_days", [15, 25])
    if not isinstance(days, list) or len(set(days)) != len(days) or any(type(d) is not int or not 1 <= d <= 28 for d in days):
        raise ValueError("Reminder days must be distinct integers 1 through 28")
    for key in ("checkin_channel_id", "checkin_staff_channel_id", "checkin_eligible_role_id", "checkin_inactive_role_id"):
        if settings.get(key) is not None and (type(settings[key]) is not int or settings[key] <= 0):
            raise ValueError(f"{key} must be a positive ID or null")
    if settings.get("checkin_announcements_enabled") and not settings.get("checkin_channel_id"):
        raise ValueError("Configure checkin_channel_id before enabling announcements")
    if settings.get("checkin_reminders_enabled") and not settings.get("checkin_staff_channel_id"):
        raise ValueError("Configure a private staff channel before enabling reminders")


def calendar(settings, now=None):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("Calendar time must be timezone aware")
    local = now.astimezone(ZoneInfo(settings.get("checkin_timezone", "America/Chicago")))
    return settings.get("checkin_season", 10), local.year, local.month, local.day


def period(settings, now=None):
    season, year, month, _ = calendar(settings, now)
    return Period.get_or_create(guild_id=settings["Coastal"], season=season, year=year, month=month)[0]


def sync_inactive(player, member, settings):
    role = settings.get("checkin_inactive_role_id")
    if not role or member is None or member.bot or player.discord_id != member.id:
        return
    guild = getattr(member, "guild", None)
    if guild is not None and (guild.id != settings["Coastal"] or guild.get_role(role) is None):
        return
    inactive = any(r.id == role for r in member.roles)
    if player.inactive != inactive:
        Player.update(inactive=inactive, updated_at=utcnow()).where(Player.id == player.id).execute()
        player.inactive = inactive


def member_required(member, settings):
    if member is None or member.bot:
        return False
    inactive_role = settings.get("checkin_inactive_role_id")
    if inactive_role:
        guild = getattr(member, "guild", None)
        if guild is not None and (guild.id != settings["Coastal"] or guild.get_role(inactive_role) is None):
            return False
        return not any(r.id == inactive_role for r in member.roles)
    return False


def eligible(player, member, settings):
    if member is None or member.bot:
        return False
    sync_inactive(player, member, settings)
    if settings.get("checkin_inactive_role_id"):
        return member_required(member, settings)
    role = settings.get("checkin_eligible_role_id")
    if role:
        return any(r.id == role for r in member.roles)
    return Participation.select().where((Participation.player == player) &
        (Participation.season == settings.get("checkin_season", 10)) &
        (Participation.realm_status == "staff_eligible")).exists()


def sync_guild(guild, settings):
    role = settings.get("checkin_inactive_role_id")
    if not role or guild.id != settings["Coastal"]:
        return
    if guild.get_role(role) is None:
        raise ValueError("Configured inactive role is missing; check-ins remain unavailable")
    for player in Player.select().where(Player.discord_id.is_null(False)):
        sync_inactive(player, guild.get_member(player.discord_id), settings)


def record_checkin(player, discord_id, current, *, message_id=None):
    if player.discord_id != discord_id:
        raise ValueError("Discord identity does not own this profile")
    try:
        with db.atomic():
            CheckIn.create(player=player, season=current.season, year=current.year,
                           month=current.month, discord_id=discord_id, message_id=message_id)
        return True
    except IntegrityError:
        if CheckIn.select().where((CheckIn.player == player) & (CheckIn.season == current.season) &
                (CheckIn.year == current.year) & (CheckIn.month == current.month)).exists():
            return False
        raise


def checked(player, current):
    return CheckIn.select().where((CheckIn.player == player) & (CheckIn.season == current.season) &
        (CheckIn.year == current.year) & (CheckIn.month == current.month)).exists()


def roster(guild, settings, current):
    result = []
    for player in Player.select().where(Player.discord_id.is_null(False)):
        member = guild.get_member(player.discord_id)
        if eligible(player, member, settings):
            result.append((player.id, player.discord_id, checked(player, current)))
    return result


def unlinked_required(guild, settings):
    linked = {p.discord_id for p in Player.select(Player.discord_id).where(Player.discord_id.is_null(False))}
    return [m.id for m in guild.members if member_required(m, settings) and m.id not in linked]


def claim_announcement(current, channel_id):
    return bool(Period.update(announcement_state="claimed", channel_id=channel_id).where(
        (Period.id == current.id) & (Period.announcement_state == "new")).execute())


def claim_reminder(current, player_id, day):
    try:
        with db.atomic():
            return Reminder.create(period=current, player=player_id, day=day)
    except IntegrityError:
        return None
