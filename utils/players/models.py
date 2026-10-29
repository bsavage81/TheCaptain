"""Additive registry schema; never creates tables on import or startup."""
from datetime import datetime, timezone
from peewee import (AutoField, BigIntegerField, BooleanField, CharField, DateTimeField,
                    ForeignKeyField, IntegerField, TextField)
from utils.database.__database import BaseModel


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Player(BaseModel):
    id = AutoField()
    discord_id = BigIntegerField(null=True, unique=True)
    discord_name = CharField(default="")
    gamertag = CharField(default="")
    xuid = CharField(null=True, unique=True)
    first_application = CharField(null=True)
    first_season = IntegerField(null=True)
    membership = CharField(default="unknown")
    created_at = DateTimeField(default=utcnow)
    updated_at = DateTimeField(default=utcnow)

    class Meta:
        table_name = "captain_player"


class Identity(BaseModel):
    player = ForeignKeyField(Player, backref="identities")
    kind = CharField()
    value = CharField()
    verified = BooleanField(default=False)
    source = CharField(max_length=191)
    observed_at = DateTimeField(default=utcnow)

    class Meta:
        table_name = "captain_identity"
        indexes = ((("player", "kind", "value", "source"), True),)


class Participation(BaseModel):
    player = ForeignKeyField(Player, backref="seasons")
    season = IntegerField()
    application_date = CharField(null=True)
    application_status = CharField(default="unknown")
    source = CharField(max_length=191)
    discord_membership = CharField(default="unknown")
    realm_status = CharField(default="unknown")

    class Meta:
        table_name = "captain_participation"
        indexes = ((("player", "season", "source"), True),)


class ImportRecord(BaseModel):
    key = CharField(max_length=64, unique=True)
    source = TextField()
    season = IntegerField()
    payload = TextField()
    state = CharField(default="pending")
    player = ForeignKeyField(Player, null=True)
    reviewed_by = BigIntegerField(null=True)
    reviewed_at = DateTimeField(null=True)
    note = TextField(default="")

    class Meta:
        table_name = "captain_import_record"


class Period(BaseModel):
    guild_id = BigIntegerField()
    season = IntegerField()
    year = IntegerField()
    month = IntegerField()
    channel_id = BigIntegerField(null=True)
    message_id = BigIntegerField(null=True)
    announcement_state = CharField(default="new")
    staff_report_state = CharField(default="new")

    class Meta:
        table_name = "captain_checkin_period"
        indexes = ((("guild_id", "season", "year", "month"), True),)


class CheckIn(BaseModel):
    player = ForeignKeyField(Player, backref="checkins")
    season = IntegerField()
    year = IntegerField()
    month = IntegerField()
    checked_at = DateTimeField(default=utcnow)
    source = CharField(default="discord_button")
    discord_id = BigIntegerField()
    message_id = BigIntegerField(null=True)

    class Meta:
        table_name = "captain_checkin"
        indexes = ((("player", "season", "year", "month"), True),)


class Reminder(BaseModel):
    period = ForeignKeyField(Period)
    player = ForeignKeyField(Player)
    day = IntegerField()
    state = CharField(default="claimed")
    attempted_at = DateTimeField(default=utcnow)

    class Meta:
        table_name = "captain_reminder"
        indexes = ((("period", "player", "day"), True),)


class DiscoveryRun(BaseModel):
    actor = BigIntegerField()
    created_at = DateTimeField(default=utcnow)
    report = TextField()

    class Meta:
        table_name = "captain_discovery_run"


MODELS = [Player, Identity, Participation, ImportRecord, Period, CheckIn, Reminder, DiscoveryRun]
