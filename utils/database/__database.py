"""Captain schema. Importing this module never connects or creates tables."""
from peewee import AutoField, Model, IntegerField, TextField, BigIntegerField, BooleanField, DatabaseProxy, MySQLDatabase

db = DatabaseProxy()

class BaseModel(Model):
    """Base Model class used for creating new tables."""

    class Meta:
        database = db


class BotData(BaseModel):
    """Legacy-compatible storage; production reads row 1.prefix only.

    Other columns remain mapped for safe inserts and rollback. They are not evidence
    of active features and may not be removed without a database consumer audit.
    """
    id = AutoField()
    persistent_views = BooleanField(default=False)
    prefix = TextField(default=">")
    bot_spam_channel_coastal = BigIntegerField(default=0)
    bot_spam_channel_aurafall = BigIntegerField(default=0)
    bot_type = TextField(default="Stable")
    bot_id = BigIntegerField(default=0)
    server_id_aurafall = BigIntegerField(default=0)
    server_id_coastal = BigIntegerField(default=0)

class Administrators(BaseModel):
    """
    Administrators:
    List of users who are whitelisted on the bot.

    `id`: AutoField()
    Database Entry

    `discordID`: BigIntegerField()
    Discord ID

    `TierLevel`: IntegerField()
    TIER LEVEL

    1 - Bot Manager\n
    2 - Admin\n
    3 - Sudo Admin\n
    4 - Owner
    """

    id = AutoField()
    discordID = BigIntegerField(unique=True)
    TierLevel = IntegerField(default=1)


tables = {"administrators": Administrators, "botdata": BotData}


def initialize_database(settings, backend=None):
    if settings.get("bot_type", "STABLE") != "STABLE":
        raise ValueError("Retired deployment configuration cannot initialize production")
    backend = backend if backend is not None else make_database(settings)
    db.initialize(backend)
    with backend.connection_context():
        if set(tables) - set(backend.get_tables()):
            raise ValueError("Captain database tables are missing. Review and run python -m migrations.single_production --apply explicitly before startup.")
        row = ensure_production_row()
        if not Administrators.select().exists():
            for owner in settings.get("owner_ids", [306070011028439041]):
                Administrators.get_or_create(discordID=owner, defaults={"TierLevel": 4})
        return row


def is_administrator(user_id, tier=3):
    with db.connection_context():
        return Administrators.select().where(
            (Administrators.discordID == user_id) & (Administrators.TierLevel >= tier)).exists()


def make_database(settings):
    return MySQLDatabase(
        settings["database_schema"], host=settings["database_ip"],
        port=int(settings.get("database_port", 3306)),
        user=settings["database_username"], password=settings["database_password"])


def ensure_production_row():
    """Preserve row 1 exactly; never infer production from a retired deployment."""
    row = BotData.get_or_none(BotData.id == 1)
    if row is not None:
        return row
    if BotData.select().exists():
        raise ValueError("Production BotData row 1 is missing in a nonempty table. Restore the verified production row before startup; no legacy row was copied.")
    row, _ = BotData.get_or_create(id=1, defaults={"bot_type": "STABLE"})
    return row
