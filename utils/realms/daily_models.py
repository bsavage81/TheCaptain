"""Durable daily checkpoints; registered by database initialization, never on import."""
from peewee import CharField, DateField, DateTimeField, BigIntegerField
from utils.database.__database import BaseModel


class DailyReport(BaseModel):
    guild = BigIntegerField()
    channel = BigIntegerField()
    realm = CharField(max_length=20)
    day = DateField()
    message = BigIntegerField(null=True)
    signature = CharField(max_length=64, default='')
    pending_since = DateTimeField(null=True)
    lease = DateTimeField(null=True)

    class Meta:
        table_name = 'captain_realm_daily'
        indexes = ((('guild', 'channel', 'realm', 'day'), True),)


class DailyCollection(BaseModel):
    realm = CharField(max_length=20, unique=True)
    attempted = DateTimeField(null=True)
    succeeded = DateTimeField(null=True)
    outcome = CharField(max_length=32, default='unavailable')

    class Meta:
        table_name = 'captain_realm_collection'
