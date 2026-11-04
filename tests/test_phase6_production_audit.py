"""Offline SQL read boundary and full-schema comparator checks."""
from copy import deepcopy

import pytest

from scripts.phase6_production_audit import compare, expected_type, quote, readonly_sql
from utils.players.models import Player
from utils.players.activity_models import RealmActivity


@pytest.mark.parametrize('sql', ['INSERT INTO x VALUES (1)', 'CREATE TEMPORARY TABLE x (id INT)',
    'ALTER TABLE x ADD id INT', 'UPDATE x SET id=1', 'DELETE FROM x', 'COMMIT',
    'SELECT 1; SELECT 2', "SELECT 1 INTO OUTFILE '/tmp/a'", 'SELECT * FROM x FOR UPDATE',
    "SELECT GET_LOCK('x',0)"])
def test_nonread_operations_denied(sql):
    with pytest.raises(ValueError):
        readonly_sql(sql)


def metadata():
    return {'engine': 'InnoDB', 'collation': 'utf8mb4_general_ci',
        'columns': [{'column_name': f.column_name, 'column_type': expected_type(f),
                     'is_nullable': 'YES' if f.null else 'NO', 'column_default': None,
                     'extra': 'auto_increment' if f.field_type == 'AUTO' else '',
                     'datetime_precision': 0 if f.field_type == 'DATETIME' else None,
                     'collation_name': 'utf8mb4_general_ci' if f.field_type == 'VARCHAR' else None}
                    for f in Player._meta.sorted_fields],
        'indexes': [{'index_name': name, 'non_unique': 0, 'seq_in_index': 1,
                     'column_name': col, 'sub_part': None, 'index_type': 'BTREE'}
                    for name,col in [('PRIMARY','id'),('discord','discord_id'),('xbox','xuid')]],
        'foreign_keys': [], 'constraints': [{'constraint_type': 'PRIMARY KEY'}, {'constraint_type':'UNIQUE'}]}


def test_expected_schema_and_mariadb_integer_display_widths():
    value = metadata()
    assert compare(Player, value) == []
    value['columns'][0]['column_type'] = 'int(11)'
    assert compare(Player, value) == []


@pytest.mark.parametrize('change', [
    lambda v: v.update(engine='MyISAM'),
    lambda v: v['columns'][0].update(column_type='bigint'),
    lambda v: v['columns'][0].update(is_nullable='YES'),
    lambda v: v['columns'][0].update(extra=''),
    lambda v: v['columns'][1].update(column_default='123'),
    lambda v: v['columns'][-1].update(datetime_precision=6),
    lambda v: v['columns'][2].update(collation_name='latin1_swedish_ci'),
    lambda v: v['indexes'].pop(),
    lambda v: v['indexes'][1].update(non_unique=1),
    lambda v: v['indexes'][1].update(sub_part=10),
    lambda v: v['foreign_keys'].append({'column_name':'id','referenced_table_name':'other',
        'referenced_column_name':'id','update_rule':'CASCADE','delete_rule':'CASCADE'}),
    lambda v: v['constraints'].append({'constraint_type':'CHECK'}),
    lambda v: v.update(ddl='FOREIGN KEY (`id`) REFERENCES `other_schema`.`captain_player` (`id`)'),
    lambda v: v.update(ddl='KEY (`discord_id` DESC)'),
    lambda v: v.update(ddl='KEY x (`discord_id`) IGNORED'),
])
def test_differences_beyond_old_preflight_are_reported(change):
    value = deepcopy(metadata())
    change(value)
    assert compare(Player, value)


def test_reads_and_only_read_transaction_controls_allowed():
    for sql in ['SELECT VERSION()', 'SHOW CREATE TABLE `captain_player`',
                'SET TRANSACTION READ ONLY', 'START TRANSACTION WITH CONSISTENT SNAPSHOT', 'ROLLBACK']:
        readonly_sql(sql)
    assert quote('a`b') == '`a``b`'


def test_prepared_single_create_matches_compiled_model_and_all_indexes():
    from pathlib import Path
    import re
    from peewee import MySQLDatabase
    from utils.database.__database import db
    db.initialize(MySQLDatabase('synthetic'))
    script = Path('migrations/sql/phase6-activity-only.sql').read_text()
    script = '\n'.join(line for line in script.splitlines() if not line.lstrip().startswith('--'))
    normalized = re.sub(r'\s+', ' ', script).strip()
    normalized = re.sub(r'\(\s+', '(', normalized)
    normalized = re.sub(r'\s+\)', ')', normalized)
    ddl, params = RealmActivity._schema._create_table(safe=False).query()
    assert not params and normalized.startswith(ddl[:-1] + ',')
    assert normalized.count(';') == 1
    assert not re.search(r'\b(ALTER|DROP|INSERT|UPDATE|DELETE|USE|IF NOT EXISTS)\b', script)
    for context in RealmActivity._schema._create_indexes(safe=False):
        index_sql, params = context.query()
        match = re.fullmatch(r'CREATE (UNIQUE )?INDEX (`[^`]+`) ON `captain_realm_activity` (\(.*\))', index_sql)
        assert not params and match is not None
        assert ('UNIQUE KEY ' if match[1] else 'KEY ') + match[2] + ' ' + match[3] in normalized
    assert normalized.endswith('ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;')
