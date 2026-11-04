"""Exclusive private logical backup via the existing read-only production audit.

Creates a NEW directory before connecting. Never restores, changes production or
overwrites files. JSON retains types; SQL is for a separately approved empty recovery
database only. No restore target is inferred from production bootstrap credentials.
"""
import argparse
import base64
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import uuid

from dotenv import dotenv_values

from scripts.phase6_production_audit import audit, quote
from utils.database.__database import make_database
from utils.integrations.realms.token_store import private_permissions, reject_links


def encode(value):
    if value is None or type(value) in (str, int, bool):
        return {'type': type(value).__name__, 'value': value}
    if type(value) is float and math.isfinite(value):
        return {'type': 'float', 'value': repr(value)}
    if type(value) is bytes:
        return {'type': 'bytes', 'value': base64.b64encode(value).decode('ascii')}
    if type(value) in (datetime, date, time):
        return {'type': type(value).__name__, 'value': value.isoformat()}
    if type(value) is timedelta:
        return {'type': 'timedelta', 'value': [value.days, value.seconds, value.microseconds]}
    if type(value) is Decimal and value.is_finite():
        return {'type': 'Decimal', 'value': str(value)}
    raise ValueError('Unsupported/nonfinite database value')


def decode(item):
    kind, value = item['type'], item['value']
    if kind in ('NoneType', 'str', 'int', 'bool'):
        expected = {'NoneType': type(None), 'str': str, 'int': int, 'bool': bool}[kind]
        if type(value) is not expected:
            raise ValueError('Typed backup value differs')
        return value
    if kind == 'bytes':
        return base64.b64decode(value, validate=True)
    if kind in ('datetime', 'date', 'time'):
        return {'datetime': datetime, 'date': date, 'time': time}[kind].fromisoformat(value)
    if kind == 'timedelta':
        return timedelta(days=value[0], seconds=value[1], microseconds=value[2])
    if kind == 'Decimal':
        return Decimal(value)
    if kind == 'float':
        return float(value)
    raise ValueError('Unsupported backup type')


def literal(value):
    if value is None:
        return 'NULL'
    if type(value) is bool:
        return str(int(value))
    if type(value) is int:
        return str(value)
    if type(value) in (float, Decimal):
        if not math.isfinite(value):
            raise ValueError('Nonfinite numeric SQL value')
        return str(value)
    if type(value) is str:
        return "CONVERT(X'" + value.encode('utf-8').hex() + "' USING utf8mb4)"
    if type(value) is bytes:
        return "X'" + value.hex() + "'"
    if type(value) in (datetime, date, time):
        if getattr(value, 'tzinfo', None) is not None:
            raise ValueError('Unexpected timezone-aware database value')
        text = value.isoformat(sep=' ') if type(value) is datetime else value.isoformat()
        return "'" + text + "'"
    if type(value) is timedelta:
        total = (value.days*86400 + value.seconds)*1000000 + value.microseconds
        sign = '-' if total < 0 else ''
        hours, rest = divmod(abs(total), 3600000000)
        minutes, rest = divmod(rest, 60000000)
        seconds, micros = divmod(rest, 1000000)
        return f"'{sign}{hours:02}:{minutes:02}:{seconds:02}.{micros:06}'"
    raise ValueError('Unsupported SQL value')


def table_order(tables):
    pending = set(tables)
    ordered = []
    while pending:
        ready = sorted(t for t in pending if all(f['referenced_table_name'] in ordered
                       for f in tables[t]['foreign_keys']))
        if not ready:
            raise ValueError('External/cyclic foreign keys need recovery review')
        ordered.extend(ready)
        pending.difference_update(ready)
    return ordered


def render_sql(snapshot):
    mode = snapshot['sql_mode']
    if not re.fullmatch(r'[A-Z0-9_,]*', mode):
        raise ValueError('Unexpected SQL mode')
    lines = ['-- PRIVATE. Restore only to an approved EMPTY recovery database.',
             '-- No DROP/USE/overwrite logic. DDL is not transactionally rollbackable.',
             'SET NAMES utf8mb4;', f"SET SESSION sql_mode='{mode}';"]
    order = table_order(snapshot['tables'])
    for name in order:
        ddl = snapshot['tables'][name]['ddl']
        if (not ddl.startswith('CREATE TABLE ') or ';' in ddl
                or re.search(r'\bREFERENCES\s+`[^`]+`\.', ddl, re.I)):
            raise ValueError('Unexpected CREATE definition')
        lines.append(ddl + ';')
    lines.append('START TRANSACTION;')
    for name in order:
        table = snapshot['tables'][name]
        columns = ','.join(quote(c) for c in table['data_columns'])
        for row in table['data_rows']:
            values = ','.join(literal(decode(cell)) for cell in row)
            lines.append(f'INSERT INTO {quote(name)} ({columns}) VALUES ({values});')
    lines.append('COMMIT;')
    return ('\n'.join(lines)+'\n').encode('utf-8')


def exclusive(path, content):
    reject_links(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    private_permissions(path)
    if path.read_bytes() != content:
        raise ValueError('Backup file read-back mismatch')


def prepare_destination(parent):
    parent = Path(parent).absolute()
    reject_links(parent)
    if not parent.is_dir():
        raise ValueError('Existing backup parent required')
    private_permissions(parent)
    root = parent / ('phase6-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:12])
    # Refuse an unignored location before any secret or database value is read.
    check = subprocess.run(['git', 'check-ignore', '--quiet', str(root/'backup.json')], capture_output=True)
    if check.returncode:
        raise ValueError('Backup destination must be Git-ignored')
    root.mkdir(mode=0o700, exist_ok=False)
    private_permissions(root, create=True)
    reject_links(root)
    private_permissions(root)
    print(json.dumps({'destination_validated': True, 'directory': str(root),
                      'private_permissions_verified': True, 'overwrite_possible': False}), flush=True)
    return root


def save(root, snapshot):
    for table in snapshot['tables'].values():
        original = table['data_rows']
        encoded = [[encode(v) for v in row] for row in original]
        restored = [tuple(decode(v) for v in row) for row in encoded]
        if restored != [tuple(row) for row in original]:
            raise ValueError('Typed values failed roundtrip')
        table['data_rows'] = encoded
        table['rows_sha256'] = hashlib.sha256(json.dumps(encoded, sort_keys=True).encode()).hexdigest()
        table['ddl_sha256'] = hashlib.sha256(table['ddl'].encode()).hexdigest()
    snapshot['backup_format'] = 'captain-typed-logical-v1'
    snapshot['captured_at_utc'] = datetime.now(timezone.utc).isoformat()
    data = json.dumps(snapshot, sort_keys=True, indent=2).encode('utf-8')
    sql = render_sql(snapshot)
    exclusive(root/'backup.json', data)
    exclusive(root/'recovery.sql', sql)
    loaded = json.loads((root/'backup.json').read_text(encoding='utf-8'))
    if loaded != snapshot or render_sql(loaded) != (root/'recovery.sql').read_bytes():
        raise ValueError('Independent read-back/regeneration failed')
    for table in loaded['tables'].values():
        if len(table['data_rows']) != table['row_count']:
            raise ValueError('Backup row coverage differs')
        if hashlib.sha256(json.dumps(table['data_rows'], sort_keys=True).encode()).hexdigest() != table['rows_sha256']:
            raise ValueError('Table data digest differs')
        if hashlib.sha256(table['ddl'].encode()).hexdigest() != table['ddl_sha256']:
            raise ValueError('Table schema digest differs')
    receipt = {'backup_format': snapshot['backup_format'], 'captured_at_utc': snapshot['captured_at_utc'],
        'server_version': snapshot['server_version'], 'table_counts': {n:t['row_count'] for n,t in loaded['tables'].items()},
        'sha256': {'backup.json': hashlib.sha256(data).hexdigest(), 'recovery.sql': hashlib.sha256(sql).hexdigest()},
        'additional_object_counts': {k:len(v) for k,v in loaded['additional_objects'].items()},
        'readback_and_typed_roundtrip_verified': True, 'schema_stable_during_capture': True,
        'snapshot_isolation': snapshot.get('snapshot_isolation', 'not recorded'),
        'restore_executed': False, 'production_writes': False}
    exclusive(root/'verification.json', json.dumps(receipt, indent=2).encode())
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bootstrap-file', required=True)
    parser.add_argument('--destination-parent', required=True)
    args = parser.parse_args()
    try:
        root = prepare_destination(args.destination_parent)  # Must precede connection/credentials.
        values = dotenv_values(args.bootstrap_file)
        settings = {k:v for k,v in values.items() if k.startswith('database_')}
        snapshot = audit(make_database(settings), capture_rows=True)
        if snapshot['incompatibilities'] or snapshot['missing_phase6_tables'] != ['captain_realm_activity']:
            raise ValueError('Unexpected Phase 6 state; stop backup workflow')
        print(json.dumps(save(root, snapshot), indent=2))
    except Exception as error:
        print(json.dumps({'status': 'stopped', 'category': type(error).__name__,
                          'private_details_suppressed': True, 'production_restore_attempted': False}))
        raise SystemExit(1) from None


if __name__ == '__main__':
    main()
