"""Read-only Phase 6 inventory. No migration, backup restore or bot startup.

Only the explicitly supplied existing bootstrap file is read; environment values
do not override it. Output contains schema metadata, aggregate counts and flags,
never credentials, settings documents or player rows. No apply mode exists.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

from dotenv import dotenv_values

from utils.database.__database import db, make_database
from utils.players.models import MODELS
from utils.players.activity_models import RealmActivity

MODELS_ALL = [*MODELS, RealmActivity]
FLAGS = ('profiles_enabled', 'checkin_enabled', 'checkin_announcements_enabled',
         'checkin_reminders_enabled', 'realm_history_enabled')


def readonly_sql(sql):
    statement = sql.strip()
    controls = {'SET TRANSACTION READ ONLY', 'START TRANSACTION WITH CONSISTENT SNAPSHOT', 'ROLLBACK'}
    if statement in controls:
        return
    if (';' in statement or not re.match(r'^(SELECT|SHOW)\b', statement, re.I)
            or re.search(r'\b(INTO|FOR\s+UPDATE|LOCK|GET_LOCK|RELEASE_LOCK)\b', statement, re.I)):
        raise ValueError('Read-only audit refused a non-read statement')


def quote(name):
    return '`' + name.replace('`', '``') + '`'


def rows(backend, sql, params=()):
    cursor = backend.execute_sql(sql, params)
    names = [item[0].lower() for item in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def expected_type(field):
    kind = field.field_type
    if kind in {'AUTO', 'INT'}:
        return 'int'
    if kind == 'BIGINT':
        return 'bigint'
    if kind == 'BOOL':
        return 'tinyint(1)'
    if kind == 'VARCHAR':
        return f'varchar({field.max_length})'
    if kind in {'TEXT', 'DATETIME'}:
        return kind.lower()
    raise ValueError('Unexpected model field type')


def compare(model, metadata):
    issues = []
    name = model._meta.table_name
    def issue(detail):
        issues.append(name + ': ' + detail)
    if str(metadata['engine']).casefold() != 'innodb':
        issue('engine is not InnoDB')
    columns = {c['column_name']: c for c in metadata['columns']}
    if set(columns) != {f.column_name for f in model._meta.sorted_fields}:
        issue('column set differs')
    for field in model._meta.sorted_fields:
        col = columns.get(field.column_name)
        if col is None:
            continue
        actual = col['column_type'].lower()
        if field.field_type != 'BOOL':
            actual = re.sub(r'\b(int|bigint)\(\d+\)', r'\1', actual)
        if actual != expected_type(field):
            issue(field.column_name + ': column type differs')
        if (col['is_nullable'] == 'YES') != field.null:
            issue(field.column_name + ': nullability differs')
        default = col['column_default']
        if default not in (None, 'NULL'):
            issue(field.column_name + ': unexpected SQL default')
        extra = str(col['extra'] or '').lower()
        if extra != ('auto_increment' if field.field_type == 'AUTO' else ''):
            issue(field.column_name + ': extra/generated/update behavior differs')
        if field.field_type == 'DATETIME' and col['datetime_precision'] != 0:
            issue(field.column_name + ': datetime precision differs')
        if col['collation_name'] is not None and col['collation_name'] != metadata['collation']:
            issue(field.column_name + ': per-column collation differs from table')
    grouped = {}
    for item in metadata['indexes']:
        grouped.setdefault(item['index_name'], []).append(item)
    observed = set()
    for index_name, parts in grouped.items():
        parts = sorted(parts, key=lambda p: p['seq_in_index'])
        if any(p['sub_part'] is not None or p['index_type'] != 'BTREE' for p in parts):
            issue('prefix/non-BTREE index requires review')
        observed.add((tuple(p['column_name'] for p in parts), not bool(parts[0]['non_unique'])))
    expected = {(('id',), True)}
    for field in model._meta.sorted_fields:
        if field.unique or field.index:
            expected.add(((field.column_name,), field.unique))
    expected.update((tuple(model._meta.fields[n].column_name for n in fields), unique)
                    for fields, unique in model._meta.indexes)
    if observed != expected:
        issue('index columns/uniqueness differ')
    primary = tuple(p['column_name'] for p in sorted(grouped.get('PRIMARY', []), key=lambda p: p['seq_in_index']))
    if primary != ('id',):
        issue('primary key differs')
    expected_fk = {(f.column_name, f.rel_model._meta.table_name, f.rel_field.column_name)
                   for f in model._meta.sorted_fields if hasattr(f, 'rel_model')}
    actual_fk = {(f['column_name'], f['referenced_table_name'], f['referenced_column_name'])
                 for f in metadata['foreign_keys']}
    if actual_fk != expected_fk:
        issue('foreign keys differ')
    if any(f['update_rule'] not in {'RESTRICT', 'NO ACTION'} or f['delete_rule'] not in {'RESTRICT', 'NO ACTION'}
           for f in metadata['foreign_keys']):
        issue('foreign key actions differ')
    if any(c['constraint_type'] not in {'PRIMARY KEY', 'UNIQUE', 'FOREIGN KEY'} for c in metadata['constraints']):
        issue('unexpected constraint')
    ddl = metadata.get('ddl', '')
    if re.search(r'\bREFERENCES\s+`[^`]+`\.', ddl, re.I):
        issue('cross-schema foreign key requires review')
    if re.search(r'\bIGNORED\b|`\s+DESC\b', ddl, re.I):
        issue('ignored/descending index requires review')
    return issues


def audit(backend):
    original = backend.execute_sql
    def guarded(sql, params=None, **kwargs):
        readonly_sql(sql)
        return original(sql, params, **kwargs)
    backend.execute_sql = guarded
    db.initialize(backend)  # Model SQL compilation only; no migration functions called.
    try:
        with backend.connection_context():
            backend.execute_sql('SET TRANSACTION READ ONLY')
            backend.execute_sql('START TRANSACTION WITH CONSISTENT SNAPSHOT')
            try:
                identity = rows(backend, 'SELECT VERSION() AS version, DATABASE() AS schema_name, '
                                '@@hostname AS host_name, CURRENT_USER() AS account_name, '
                                '@@sql_mode AS sql_mode, @@character_set_server AS charset, '
                                '@@collation_server AS collation')[0]
                if identity['schema_name'] != backend.database or 'MariaDB' not in identity['version']:
                    raise ValueError('Database identity mismatch')
                tables = rows(backend, 'SELECT TABLE_NAME, ENGINE, TABLE_COLLATION, TABLE_TYPE '
                              'FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() ORDER BY TABLE_NAME')
                inventory = {}
                for item in tables:
                    table = item['table_name']
                    inventory[table] = {'engine': item['engine'], 'collation': item['table_collation'],
                                        'kind': item['table_type']}
                    if item['table_type'] != 'BASE TABLE':
                        continue
                    metadata = inventory[table]
                    metadata['ddl'] = rows(backend, 'SHOW CREATE TABLE ' + quote(table))[0]['create table']
                    metadata['columns'] = rows(backend, 'SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT, '
                        'EXTRA, CHARACTER_SET_NAME, COLLATION_NAME, DATETIME_PRECISION '
                        'FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s '
                        'ORDER BY ORDINAL_POSITION', (table,))
                    metadata['indexes'] = rows(backend, 'SELECT INDEX_NAME, NON_UNIQUE, SEQ_IN_INDEX, COLUMN_NAME, '
                        'SUB_PART, INDEX_TYPE FROM information_schema.STATISTICS '
                        'WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s ORDER BY INDEX_NAME,SEQ_IN_INDEX', (table,))
                    metadata['constraints'] = rows(backend, 'SELECT CONSTRAINT_NAME, CONSTRAINT_TYPE '
                        'FROM information_schema.TABLE_CONSTRAINTS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s', (table,))
                    metadata['foreign_keys'] = rows(backend, 'SELECT k.COLUMN_NAME, k.REFERENCED_TABLE_NAME, '
                        'k.REFERENCED_COLUMN_NAME, r.UPDATE_RULE, r.DELETE_RULE '
                        'FROM information_schema.KEY_COLUMN_USAGE k JOIN information_schema.REFERENTIAL_CONSTRAINTS r '
                        'ON k.CONSTRAINT_SCHEMA=r.CONSTRAINT_SCHEMA AND k.CONSTRAINT_NAME=r.CONSTRAINT_NAME '
                        'AND k.TABLE_NAME=r.TABLE_NAME WHERE k.TABLE_SCHEMA=DATABASE() AND k.TABLE_NAME=%s '
                        'AND k.REFERENCED_TABLE_NAME IS NOT NULL', (table,))
                    metadata['row_count'] = rows(backend, 'SELECT COUNT(*) AS count FROM ' + quote(table))[0]['count']
                issues, missing = [], []
                for model in MODELS_ALL:
                    table = model._meta.table_name
                    if table not in inventory:
                        missing.append(table)
                    elif inventory[table]['kind'] != 'BASE TABLE':
                        issues.append(table + ': expected a base table')
                    else:
                        issues.extend(compare(model, inventory[table]))
                settings_row = rows(backend, 'SELECT settings_json FROM botdata WHERE id=1')
                if len(settings_row) != 1:
                    raise ValueError('Canonical settings row missing')
                settings = json.loads(settings_row[0]['settings_json'])['settings']
                triggers = rows(backend, 'SELECT TRIGGER_NAME, EVENT_OBJECT_TABLE FROM information_schema.TRIGGERS '
                                'WHERE TRIGGER_SCHEMA=DATABASE()')
                if any(t['event_object_table'] in {m._meta.table_name for m in MODELS_ALL} for t in triggers):
                    issues.append('Registry trigger requires independent review')
                flags = {k: {'present': k in settings, 'value': settings.get(k, False)} for k in FLAGS}
                if any(type(v['value']) is not bool or v['value'] for v in flags.values()):
                    issues.append('New feature flags are enabled or malformed; owner review required')
                return {'server_version': identity['version'], 'sql_mode': identity['sql_mode'],
                        'server_charset': identity['charset'], 'server_collation': identity['collation'],
                        'private_target_sha256': hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest(),
                        'tables': inventory, 'missing_phase6_tables': missing, 'incompatibilities': issues,
                        'flags': flags, 'triggers': triggers,
                        'settings_sha256': hashlib.sha256(settings_row[0]['settings_json'].encode()).hexdigest(),
                        'migration_ledger_tables': [t for t in inventory if re.search('migrat|schema_version', t, re.I)],
                        'production_writes': False}
            finally:
                backend.execute_sql('ROLLBACK')
    finally:
        backend.execute_sql = original


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bootstrap-file', required=True)
    parser.add_argument('--output', required=True, help='New private metadata report, never player records')
    args = parser.parse_args()
    try:
        output = Path(args.output).absolute()
        from utils.integrations.realms.token_store import private_permissions, reject_links
        reject_links(output)
        private_permissions(output.parent)
        if output.exists():
            raise ValueError('Refuse to overwrite report')
        values = dotenv_values(args.bootstrap_file)
        settings = {k: v for k,v in values.items() if k.startswith('database_')}
        result = audit(make_database(settings))
        import os
        descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            json.dump(result, stream, indent=2, default=str)
        private_permissions(output)
        print(json.dumps({k: result[k] for k in ('server_version', 'sql_mode', 'server_charset',
            'server_collation', 'missing_phase6_tables', 'incompatibilities', 'flags', 'migration_ledger_tables',
            'production_writes')}, indent=2))
        print(json.dumps({'table_counts': {k:v.get('row_count') for k,v in result['tables'].items()}}))
    except Exception as error:
        print(json.dumps({'status': 'stopped', 'category': type(error).__name__, 'private_details_suppressed': True}))
        raise SystemExit(1) from None


if __name__ == '__main__':
    main()
