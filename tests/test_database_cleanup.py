from unittest.mock import Mock
import pytest
from peewee import SqliteDatabase, MySQLDatabase
from legacy_database import LegacyBotData, make_legacy
from utils.database import __database as database
from migrations.cleanup_botdata import cleanup, _swap, _dependencies, ARCHIVE, STAGING, ROLLED_BACK

APPLY = dict(apply=True, maintenance_window=True, exclusive_database=True, backup_verified=True)


def seed(tmp_path):
    backend=SqliteDatabase(tmp_path/"cleanup.sqlite",pragmas={"foreign_keys":1})
    make_legacy(backend)
    with backend.connection_context():
        LegacyBotData.create(id=1,prefix="⚓!",persistent_views=True,bot_type="Stable",server_id_coastal=123)
        LegacyBotData.create(id=2,prefix="beta!",bot_type="BETA",server_id_aurafall=456)
        database.Administrators.create(discordID=999,TierLevel=4)
        database.Administrators.create(discordID=998,TierLevel=1)
    return backend


def test_cleanup_roundtrip_preserves_every_record(tmp_path):
    backend=seed(tmp_path)
    with backend.connection_context():
        original=backend.execute_sql("SELECT * FROM botdata ORDER BY id").fetchall()
        admins=list(database.Administrators.select().dicts())
    result=cleanup(backend)
    assert result["state"]=="planned" and not result["applied"]
    assert cleanup(backend,**APPLY)["legacy_rows_archived"]==2
    with backend.connection_context():
        assert {c.name for c in backend.get_columns("botdata")}=={"id","prefix"}
        assert backend.execute_sql("SELECT * FROM botdata").fetchall()==[(1,"⚓!")]
        assert backend.execute_sql(f"SELECT * FROM {ARCHIVE} ORDER BY id").fetchall()==original
        assert list(database.Administrators.select().dicts())==admins
    assert cleanup(backend,**APPLY)["state"]=="already_clean"
    assert database.initialize_database({"owner_ids":[997]},backend).prefix=="⚓!"
    assert cleanup(backend,rollback=True)["state"]=="planned"
    assert cleanup(backend,rollback=True,**APPLY)["state"]=="rolled_back"
    assert cleanup(backend,rollback=True,**APPLY)["state"]=="already_rolled_back"
    with backend.connection_context():
        assert backend.execute_sql("SELECT * FROM botdata ORDER BY id").fetchall()==original
        assert backend.execute_sql(f"SELECT * FROM {ROLLED_BACK}").fetchall()==[(1,"⚓!")]
        assert list(database.Administrators.select().dicts())==admins


@pytest.mark.parametrize("missing",["maintenance_window","exclusive_database","backup_verified"])
def test_apply_requires_operational_prerequisites(tmp_path,missing):
    backend=seed(tmp_path);options={**APPLY,missing:False}
    with pytest.raises(ValueError,match="Apply requires"):
        cleanup(backend,**options)
    with backend.connection_context():
        assert ARCHIVE not in backend.get_tables() and STAGING not in backend.get_tables()
        assert LegacyBotData.select().count()==2


@pytest.mark.parametrize("kind",["unknown_column","foreign_key","trigger","view","index","staging","archive"])
def test_unknown_dependencies_and_interrupted_state_fail_without_changes(tmp_path,kind):
    backend=seed(tmp_path)
    with backend.connection_context():
        if kind=="unknown_column":backend.execute_sql("ALTER TABLE botdata ADD COLUMN external_setting TEXT")
        elif kind=="foreign_key":backend.execute_sql("CREATE TABLE external_consumer (id INTEGER REFERENCES botdata(id))")
        elif kind=="trigger":backend.execute_sql("CREATE TRIGGER external_log AFTER INSERT ON botdata BEGIN SELECT 1; END")
        elif kind=="view":backend.execute_sql("CREATE VIEW external_view AS SELECT prefix FROM botdata")
        elif kind=="index":backend.execute_sql("CREATE INDEX external_index ON botdata(prefix)")
        elif kind=="staging":backend.execute_sql(f"CREATE TABLE {STAGING} (id INTEGER)")
        elif kind=="archive":backend.execute_sql(f"CREATE TABLE {ARCHIVE} (id INTEGER PRIMARY KEY)")
        original=backend.execute_sql("SELECT * FROM botdata ORDER BY id").fetchall()
    with pytest.raises(ValueError):cleanup(backend,**APPLY)
    with backend.connection_context():assert backend.execute_sql("SELECT * FROM botdata ORDER BY id").fetchall()==original


def test_unknown_tables_preserved_even_when_not_referenced(tmp_path):
    backend=seed(tmp_path)
    with backend.connection_context():
        backend.execute_sql("CREATE TABLE unrelated_historical_data (id INTEGER, value TEXT)")
        backend.execute_sql("INSERT INTO unrelated_historical_data VALUES (1, 'synthetic historical data')")
    cleanup(backend,**APPLY)
    with backend.connection_context():
        assert backend.execute_sql("SELECT value FROM unrelated_historical_data").fetchone()[0]=="synthetic historical data"


def test_copy_failure_keeps_original_and_recoverable_staging(tmp_path,monkeypatch):
    backend=seed(tmp_path);original_execute=backend.execute_sql
    def fail(sql,*args,**kwargs):
        if sql.startswith("INSERT INTO `captain_botdata_new`"):
            raise RuntimeError("synthetic failure")
        return original_execute(sql,*args,**kwargs)
    monkeypatch.setattr(backend,"execute_sql",fail)
    with pytest.raises(RuntimeError):cleanup(backend,**APPLY)
    with backend.connection_context():
        assert LegacyBotData.select().count()==2
        assert ARCHIVE not in backend.get_tables() and STAGING in backend.get_tables()
    with pytest.raises(ValueError,match="staging table remains"):
        cleanup(backend,**APPLY)


def test_sqlite_second_rename_failure_is_atomic(tmp_path,monkeypatch):
    backend=seed(tmp_path);original_execute=backend.execute_sql
    def fail(sql,*args,**kwargs):
        if sql.startswith("ALTER TABLE `captain_botdata_new`"):
            raise RuntimeError("synthetic rename failure")
        return original_execute(sql,*args,**kwargs)
    monkeypatch.setattr(backend,"execute_sql",fail)
    with pytest.raises(RuntimeError):cleanup(backend,**APPLY)
    with backend.connection_context():
        assert LegacyBotData.select().count()==2
        assert ARCHIVE not in backend.get_tables()


def test_mysql_uses_single_multi_table_rename_statement():
    backend=MySQLDatabase("synthetic")
    backend.execute_sql=Mock()
    _swap(backend,"botdata",ARCHIVE,STAGING)
    backend.execute_sql.assert_called_once_with("RENAME TABLE `botdata` TO `captain_botdata_legacy`, `captain_botdata_new` TO `botdata`")


@pytest.mark.parametrize("version",["5.7.44","10.5.0-MariaDB"])
def test_mysql_older_server_rejected_without_ddl(version):
    backend=MySQLDatabase("synthetic")
    backend.get_tables=Mock(return_value=["botdata"])
    backend.get_foreign_keys=Mock(return_value=[])
    backend.get_primary_keys=Mock(return_value=["id"])
    backend.get_indexes=Mock(return_value=[])
    backend.get_views=Mock(return_value=[])
    backend.execute_sql=Mock(return_value=Mock(fetchone=Mock(return_value=(version,))))
    with pytest.raises(ValueError,match="MySQL 8"):_dependencies(backend)
    backend.execute_sql.assert_called_once_with("SELECT VERSION()")


@pytest.mark.parametrize("rename_failure",[False,True])
def test_mysql_forward_path_with_realistic_tuple_results(rename_failure):
    from contextlib import nullcontext
    from types import SimpleNamespace as NS
    from migrations.cleanup_botdata import LEGACY_COLUMNS
    backend=MySQLDatabase("synthetic")
    tables={"botdata":{"columns":LEGACY_COLUMNS,"rows":[(1,"⚓!"),(2,"retired")]}}
    statements=[]
    backend.connection_context=lambda:nullcontext()
    backend.get_tables=lambda:list(tables)
    backend.get_columns=lambda table:[NS(name=c) for c in tables[table]["columns"]]
    backend.get_primary_keys=lambda table:["id"]
    backend.get_indexes=lambda table:[]
    backend.get_foreign_keys=lambda table:[]
    backend.get_views=lambda:[]
    def execute(sql,params=None):
        statements.append(sql)
        rows=()
        if sql=="SELECT VERSION()":rows=(("8.0.44",),)
        elif "SELECT ENGINE" in sql:rows=(("InnoDB",),)
        elif "COUNT(*) FROM information_schema" in sql:rows=((0,),)
        elif sql=="SELECT id FROM botdata":rows=tuple((r[0],) for r in tables["botdata"]["rows"])
        elif sql.startswith("CREATE TABLE"):
            assert sql.endswith(") ENGINE=InnoDB")
            tables[STAGING]={"columns":{"id","prefix"},"rows":[]}
        elif sql.startswith("INSERT INTO"):
            tables[STAGING]["rows"]=[tables["botdata"]["rows"][0]]
        elif sql=="SELECT id, prefix FROM botdata WHERE id=1":rows=(tables["botdata"]["rows"][0],)
        elif sql==f"SELECT id, prefix FROM `{STAGING}`":rows=tuple(tables[STAGING]["rows"])
        elif sql.startswith("RENAME TABLE"):
            if rename_failure:raise RuntimeError("synthetic atomic rename failure")
            tables[ARCHIVE]=tables.pop("botdata");tables["botdata"]=tables.pop(STAGING)
        else:raise AssertionError(sql)
        return NS(fetchone=lambda:rows[0] if rows else None,fetchall=lambda:rows)
    backend.execute_sql=execute
    if rename_failure:
        with pytest.raises(RuntimeError):cleanup(backend,**APPLY)
        assert tables["botdata"]["columns"]==LEGACY_COLUMNS
        assert ARCHIVE not in tables and STAGING in tables
    else:
        assert cleanup(backend,**APPLY)["state"]=="cleaned"
        assert tables["botdata"]["rows"]==[(1,"⚓!")]
        assert tables[ARCHIVE]["rows"]==[(1,"⚓!"),(2,"retired")]
    assert not any(sql.startswith(("DROP ","DELETE ","TRUNCATE ")) for sql in statements)


def test_custom_check_constraint_blocks_cleanup(tmp_path):
    backend=SqliteDatabase(tmp_path/"checked.sqlite")
    database.db.initialize(backend)
    with backend.connection_context():
        backend.execute_sql("CREATE TABLE botdata(id INTEGER PRIMARY KEY, prefix TEXT NOT NULL CHECK(length(prefix)>0))")
        backend.execute_sql("INSERT INTO botdata VALUES (1, '!')")
    with pytest.raises(ValueError,match="CHECK constraints"):
        cleanup(backend,**APPLY)


def test_database_tls_defaults_and_explicit_self_signed_mode():
    import ssl
    cfg=dict(database_schema="synthetic",database_ip="example.invalid",database_username="synthetic",database_password="synthetic")
    verified=database.make_database(cfg)
    context=verified.connect_params["ssl"]
    assert context.check_hostname and context.verify_mode==ssl.CERT_REQUIRED
    opted_in=database.make_database({**cfg,"database_ssl_mode":"self_signed"})
    context=opted_in.connect_params["ssl"]
    assert not context.check_hostname and context.verify_mode==ssl.CERT_NONE
    with pytest.raises(ValueError):database.make_database({**cfg,"database_ssl_mode":"disabled"})


@pytest.mark.parametrize("cipher",["TLS_AES_256_GCM_SHA384",""])
def test_runtime_refuses_unencrypted_database_connections(monkeypatch,cipher):
    from types import SimpleNamespace as NS
    cursor=Mock();cursor.fetchone.return_value=("Ssl_cipher",cipher)
    manager=Mock();manager.__enter__=Mock(return_value=cursor);manager.__exit__=Mock(return_value=False)
    connection=NS(cursor=lambda:manager,close=Mock())
    monkeypatch.setattr(MySQLDatabase,"_connect",lambda self:connection)
    backend=database.EncryptedMySQLDatabase("synthetic")
    if cipher:
        assert backend._connect() is connection
        connection.close.assert_not_called()
    else:
        with pytest.raises(ConnectionError):backend._connect()
        connection.close.assert_called_once()
