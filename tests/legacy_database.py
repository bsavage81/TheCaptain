"""Synthetic historical schema fixture; never used by runtime."""
from peewee import Model, AutoField, TextField, BooleanField, BigIntegerField
from utils.database import __database as database


class LegacyBotData(Model):
    id = AutoField()
    persistent_views = BooleanField(default=False)
    prefix = TextField(default=">")
    bot_spam_channel_coastal = BigIntegerField(default=0)
    bot_spam_channel_aurafall = BigIntegerField(default=0)
    bot_type = TextField(default="Stable")
    bot_id = BigIntegerField(default=0)
    server_id_aurafall = BigIntegerField(default=0)
    server_id_coastal = BigIntegerField(default=0)

    class Meta:
        database = database.db
        table_name = "botdata"


def make_legacy(backend):
    database.db.initialize(backend)
    with backend.connection_context():
        backend.create_tables([LegacyBotData, database.Administrators])
