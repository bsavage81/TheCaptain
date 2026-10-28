"""Captain schema. Importing this module never connects or creates tables."""
from peewee import AutoField, Model, IntegerField, TextField, BigIntegerField, DatabaseProxy, MySQLDatabase

db = DatabaseProxy()

class BaseModel(Model):
    """Base Model class used for creating new tables."""

    class Meta:
        database = db


class BotData(BaseModel):
    """Production singleton. Retired settings live only in the migration archive."""
    id = AutoField()
    prefix = TextField(default=">")


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
    if {column.name for column in db.get_columns("botdata")} != {"id", "prefix"}:
        raise ValueError("Empty legacy BotData schema requires an explicit reviewed migration before startup")
    row, _ = BotData.get_or_create(id=1)
    return row
