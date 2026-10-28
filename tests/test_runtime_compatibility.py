"""Storage contracts that must survive ORM/runtime upgrades."""
from peewee import MySQLDatabase
from utils.database import __database as database


def test_existing_table_and_column_names_are_explicit():
    assert database.BotData._meta.table_name == "botdata"
    assert database.Administrators._meta.table_name == "administrators"
    assert {field.column_name for field in database.BotData._meta.sorted_fields} == {
        "id", "prefix", "bot_id", "bot_spam_channel_coastal", "server_id_coastal"}
    assert {field.column_name for field in database.Administrators._meta.sorted_fields} == {
        "id", "discordID", "TierLevel"}


def test_mysql_queries_keep_captain_schema_on_peewee_four():
    backend=MySQLDatabase("synthetic")
    database.db.initialize(backend)
    query=database.BotData.select().where(database.BotData.id == 1)
    sql,params=query.sql()
    assert "FROM `botdata`" in sql and "bot_data" not in sql
    assert params == [1]
    sql,params=database.Administrators.select().where(database.Administrators.TierLevel >= 3).sql()
    assert "FROM `administrators`" in sql and "`TierLevel`" in sql
    assert params == [3]
