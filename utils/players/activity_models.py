"""Additive private history, separate migration; importing never creates tables."""
from peewee import CharField, DateTimeField, ForeignKeyField, TextField
from utils.database.__database import BaseModel
from .models import Player, utcnow


class RealmActivity(BaseModel):
    key = CharField(max_length=64, unique=True)
    player = ForeignKeyField(Player, null=True, backref="realm_activity")
    xuid = CharField(max_length=20, null=True, index=True)
    realm_id = CharField(max_length=20, index=True)
    source = CharField(default="realms_stories", max_length=32)
    raw_start = TextField()
    raw_end = TextField()
    start = DateTimeField(null=True)
    end = DateTimeField(null=True)
    status = CharField(max_length=32)
    reason = CharField(max_length=64, default="")
    first_observed = DateTimeField(default=utcnow)
    last_observed = DateTimeField(default=utcnow)

    class Meta:
        table_name = "captain_realm_activity"
        indexes = ((("realm_id", "xuid", "start", "end"), False),)
