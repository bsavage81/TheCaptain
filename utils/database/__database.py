"""Captain schema. Importing this module never connects or creates tables."""
from peewee import AutoField, Model, IntegerField, TextField, BigIntegerField, BooleanField, DatabaseProxy, MySQLDatabase

db = DatabaseProxy()

class BaseModel(Model):
    """Base Model class used for creating new tables."""

    class Meta:
        database = db


class BotData(BaseModel):
    """
    BotData:
    Information used across the bot.

    `id`: AutoField()
    Database Entry ID (ALWAYS QUERY 1)

    `last_question_posted`: DateTimeField()
    Last time a question was posted

    `persistent_views`: BooleanField()
    Whether or not persistent views are enabled

    `prefix`: TextField()
    Bot prefix

    `blacklist_response_channel`: BigIntegerField()
    Channel ID for blacklist responses

    `question_suggest_channel`: BigIntegerField()
    Channel ID for question suggestions

    `bot_spam_channel`: BigIntegerField()
    Channel ID for bot spam

    `realm_channel_response`: BigIntegerField()
    Channel ID for realm channel responses

    `bot_type`: TextField()
    Bot type

    `other_bot_id`: BigIntegerField()
    Other bot ID

    `bot_id`: BigIntegerField()
    Bot ID

    `server_id`: BigIntegerField()
    Server ID
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
    backend = backend if backend is not None else MySQLDatabase(
        settings["database_schema"], host=settings["database_ip"],
        port=int(settings.get("database_port", 3306)),
        user=settings["database_username"], password=settings["database_password"])
    db.initialize(backend)
    with backend.connection_context():
        backend.create_tables(list(tables.values()), safe=True)
        row_id = {"STABLE": 1, "BETA": 2}[settings.get("bot_type", "STABLE")]
        row, _ = BotData.get_or_create(id=row_id, defaults={"bot_type": settings.get("bot_type", "STABLE")})
        if not Administrators.select().exists():
            for owner in settings.get("owner_ids", [306070011028439041]):
                Administrators.get_or_create(discordID=owner, defaults={"TierLevel": 4})
        return row


def is_administrator(user_id, tier=3):
    with db.connection_context():
        return Administrators.select().where(
            (Administrators.discordID == user_id) & (Administrators.TierLevel >= tier)).exists()
