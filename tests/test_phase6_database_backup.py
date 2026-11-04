"""Offline backup encoding, recovery SQL, integrity and no-overwrite checks."""
from datetime import datetime, date, time, timedelta
from decimal import Decimal
import json
from unittest.mock import Mock

import pytest

from scripts import phase6_database_backup as backup
from scripts.phase6_production_audit import backup_visibility


@pytest.mark.parametrize('value', [None, True, False, 2**64-1, -123, 1.25, Decimal('1.2300'),
    'quote\' slash\\ newline\n unicode 🏝️', b'\x00\xff', datetime(2026,11,4,1,2,3,456789),
    date(2026,11,4), time(1,2,3,456789), timedelta(hours=-25, microseconds=123)])
def test_types_roundtrip_through_json(value):
    restored = backup.decode(json.loads(json.dumps(backup.encode(value))))
    assert type(restored) is type(value) and restored == value


@pytest.mark.parametrize('value', [float('nan'), float('inf'), Decimal('NaN'), object()])
def test_unsupported_values_refused(value):
    with pytest.raises(ValueError):
        backup.encode(value)


def test_strings_hex_encoded_without_injection_or_sql_mode_dependency():
    value = "'); DROP TABLE x; -- \\unicode Ω"
    sql = backup.literal(value)
    assert 'DROP' not in sql
    raw = sql.split("'")[1]
    assert bytes.fromhex(raw).decode() == value
    assert backup.literal(b'\x00\xff') == "X'00ff'"
    assert backup.literal(None) == 'NULL'
    assert backup.literal(timedelta(hours=-25)) == "'-25:00:00.000000'"


def snapshot():
    table = {'ddl': 'CREATE TABLE `parent` (`id` int PRIMARY KEY, `name` text)',
             'foreign_keys': [], 'data_columns': ['id','name'], 'row_count':1,
             'data_rows': [(1,"private \u03a9 '\\value")], 'columns':[], 'indexes':[]}
    return {'tables': {'parent':table}, 'sql_mode':'PIPES_AS_CONCAT',
            'server_version':'12.3.3-MariaDB', 'additional_objects': {'routines':[], 'events':[], 'triggers':[], 'views':[]}}


def test_backup_readback_and_sql_regeneration(tmp_path, monkeypatch):
    monkeypatch.setattr(backup, 'private_permissions', lambda *a,**kw: None)
    receipt = backup.save(tmp_path, snapshot())
    assert receipt['readback_and_typed_roundtrip_verified']
    assert receipt['restore_executed'] is False and receipt['production_writes'] is False
    loaded = json.loads((tmp_path/'backup.json').read_text())
    assert backup.render_sql(loaded) == (tmp_path/'recovery.sql').read_bytes()
    sql = (tmp_path/'recovery.sql').read_text()
    assert 'DROP TABLE' not in sql and 'USE ' not in sql and 'IF NOT EXISTS' not in sql
    assert sql.count('CREATE TABLE') == 1 and sql.count('INSERT INTO') == 1
    with pytest.raises(FileExistsError):
        backup.save(tmp_path, snapshot())


def test_exclusive_write_never_overwrites(tmp_path, monkeypatch):
    monkeypatch.setattr(backup, 'private_permissions', lambda *a,**kw: None)
    path = tmp_path/'backup.json'
    backup.exclusive(path, b'first')
    with pytest.raises(FileExistsError):
        backup.exclusive(path, b'second')
    assert path.read_bytes() == b'first'


def test_missing_destination_stops_before_credentials_or_connection(monkeypatch, tmp_path):
    monkeypatch.setattr('sys.argv', ['backup','--bootstrap-file','private.env',
                                   '--destination-parent',str(tmp_path/'absent')])
    secret_reader = Mock(side_effect=AssertionError('No credentials before destination'))
    monkeypatch.setattr(backup, 'dotenv_values', secret_reader)
    with pytest.raises(SystemExit):
        backup.main()
    secret_reader.assert_not_called()


def test_parent_before_child_and_cycles_refused():
    tables = {'child': {'foreign_keys':[{'referenced_table_name':'parent'}]},
              'parent': {'foreign_keys':[]}}
    assert backup.table_order(tables) == ['parent','child']
    tables['parent']['foreign_keys'] = [{'referenced_table_name':'child'}]
    with pytest.raises(ValueError):
        backup.table_order(tables)


def test_backup_visibility_accepts_explicit_apollo_privileges_and_escaped_schema():
    rights = 'SELECT, SHOW VIEW, TRIGGER, EVENT, SHOW CREATE ROUTINE'
    assert backup_visibility([(f'GRANT {rights} ON `s2\\_captain`.* TO private',)], 's2_captain')
    assert backup_visibility([(f'GRANT {rights} ON `s2\\_%`.* TO private',)], 's2_captain')
    assert backup_visibility([('GRANT ALL PRIVILEGES ON *.* TO private',)], 's2_captain')
    assert not backup_visibility([('GRANT SELECT ON `s2\\_captain`.* TO private',)], 's2_captain')
    assert not backup_visibility([(f'GRANT {rights} ON `other`.* TO private',)], 's2_captain')
