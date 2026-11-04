"""Synthetic Docker-only validation. Never load .env or production bootstrap.

Requires the dedicated compose containers, explicit image/version and a fresh
staging password in CAPTAIN_STAGE_PASSWORD. No arbitrary host/schema parameters.
Failure leaves containers intact for review; cleanup is an explicit operator step.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
import re
import subprocess
from threading import Barrier

from peewee import IntegrityError, MySQLDatabase

from migrations.player_registry import migrate as registry_migrate
from migrations.realm_activity import migrate
from utils.database.__database import db
from utils.integrations.realms.models import Snapshot
from utils.integrations.realms.stories import parse_stories
from utils.players.activity import ingest, link_xbox, observed_statistics
from utils.players.activity_models import RealmActivity
from utils.players.models import Identity, MODELS, Player

SCHEMA = USER = 'captain_phase6_stage'
NAMES = ('captain-phase6-stage-db', 'captain-phase6-stage-restore')
TABLES = [*MODELS, RealmActivity]


def require(condition, message):
    if not condition:
        raise ValueError(message)


class Docker:
    def __init__(self, context):
        self.context = context

    def call(self, *args, data=None):
        environment = {k: v for k, v in os.environ.items()
                       if k not in {'DOCKER_HOST', 'DOCKER_CONTEXT', 'DOCKER_TLS_VERIFY', 'DOCKER_CERT_PATH'}}
        result = subprocess.run(['docker', '--context', self.context, *args], input=data,
                                capture_output=True, timeout=120, env=environment)
        # Docker errors/inspect output may contain staging secrets. Never print them.
        require(result.returncode == 0, 'Docker command failed; private stderr suppressed')
        require(len(result.stdout) <= 16 * 1024 * 1024, 'Docker response too large')
        return result.stdout

    def local_context(self):
        info = json.loads(self.call('context', 'inspect', self.context))[0]
        endpoint = info['Endpoints']['docker']['Host']
        require(endpoint in {'npipe:////./pipe/docker_engine',
                             'npipe:////./pipe/dockerDesktopLinuxEngine', 'unix:///var/run/docker.sock'}
                or (endpoint.startswith('unix:///') and endpoint.endswith('/.docker/run/docker.sock')),
                'Only a local Docker daemon is allowed')
        network = json.loads(self.call('network', 'inspect', 'captain-phase6-stage_stage'))[0]
        require(network.get('Internal') is True and network.get('Driver') == 'bridge',
                'Dedicated internal bridge network required')
        require({v['Name'] for v in network.get('Containers', {}).values()} == set(NAMES),
                'Network must contain only the two staging containers')

    def inspect(self, name, image):
        require(name in NAMES, 'Unexpected container name')
        value = json.loads(self.call('inspect', '--type', 'container', name))[0]
        return validate_container(value, name, image)

    def sql_stream(self, name, *, dump=False, data=None):
        # Fixed script, no user SQL/shell interpolation. Password stays in container env.
        command = ('exec mariadb-dump --user="$MARIADB_USER" --single-transaction '
                   '--skip-lock-tables --skip-comments --hex-blob captain_phase6_stage' if dump else
                   'exec mariadb --user="$MARIADB_USER" captain_phase6_stage')
        script = 'export MYSQL_PWD="$MARIADB_PASSWORD"; ' + command
        return self.call('exec', '-i', name, 'sh', '-c', script, data=data)


def validate_container(value, name, image):
    require(value['Name'] == '/' + name and value['State']['Running'], 'Container not running')
    require(value['Config']['Hostname'] == name, 'Container hostname differs')
    require(value['Config']['Image'] == image, 'Container does not use the approved digest')
    require(value['Config'].get('Labels', {}).get('org.thecaptain.phase6') == 'synthetic-only',
            'Staging label missing')
    require(not value['HostConfig'].get('Privileged') and not value['HostConfig'].get('Binds'),
            'Privileged containers and bind mounts are refused')
    require(all(m.get('Type') == 'tmpfs' for m in value.get('Mounts', [])),
            'Persistent/host mounts are refused')
    require('/var/lib/mysql' in value['HostConfig'].get('Tmpfs', {}), 'Disposable data tmpfs required')
    ports = value['NetworkSettings']['Ports']
    require(set(ports) <= {'3306/tcp'} and len(ports.get('3306/tcp') or []) == 1,
            'Unexpected published ports')
    binding = ports['3306/tcp'][0]
    require(binding['HostIp'] == '127.0.0.1', 'Staging port must bind IPv4 loopback only')
    port = int(binding['HostPort'])
    require(1024 <= port <= 65535, 'Unexpected staging port')
    require(value['HostConfig'].get('NetworkMode') == 'captain-phase6-stage_stage',
            'Dedicated staging network required')
    return port, value['Image']


def explicit_backend(port, password):
    # Local synthetic transport only. Production TLS is a separate rollout gate.
    return MySQLDatabase(SCHEMA, host='127.0.0.1', port=port, user=USER,
                         password=password, charset='utf8mb4', connect_timeout=5,
                         read_timeout=30, write_timeout=30)


def server_identity(backend, name, expected_version):
    with backend.connection_context():
        version, hostname, schema, user, mode, charset = backend.execute_sql(
            'SELECT VERSION(), @@hostname, DATABASE(), CURRENT_USER(), @@sql_mode, @@character_set_server').fetchone()
        require('MariaDB' in version and version.split('-')[0] == expected_version, 'Version mismatch')
        require(hostname == name and schema == SCHEMA and user.split('@')[0] == USER, 'Server identity mismatch')
        grants = [row[0] for row in backend.execute_sql('SHOW GRANTS').fetchall()]
        for grant in grants:
            scope = grant.split(' ON ', 1)[1].split(' TO ', 1)[0]
            require(scope == f'`{SCHEMA}`.*' or (scope == '*.*' and grant.startswith('GRANT USAGE ON ')),
                    'Staging account has unexpected grants')
        require(set(backend.get_tables()) == set(), 'Both staging schemas must initially be empty')
        return {'version': version, 'sql_mode': mode, 'server_charset': charset}


def contents(backend):
    with backend.connection_context():
        result = {}
        for table in sorted(backend.get_tables()):
            require(table in {m._meta.table_name for m in TABLES}, 'Unexpected table')
            cursor = backend.execute_sql(f'SELECT * FROM `{table}` ORDER BY id')
            result[table] = {'columns': [c[0] for c in cursor.description],
                             'rows': [list(row) for row in cursor.fetchall()]}
        return json.dumps(result, default=str, sort_keys=True)


def validate_schema(backend):
    with backend.connection_context():
        require(set(backend.get_tables()) == {m._meta.table_name for m in TABLES}, 'Expected nine tables')
        for model in TABLES:
            name = model._meta.table_name
            require(backend.get_primary_keys(name) == ['id'], 'Unexpected primary key')
            columns = {c.name: c for c in backend.get_columns(name)}
            require(set(columns) == {f.column_name for f in model._meta.sorted_fields}, 'Column mismatch')
            require(all(columns[f.column_name].null == f.null for f in model._meta.sorted_fields),
                    'Column nullability mismatch')
            keys = {(fk.column, fk.dest_table, fk.dest_column) for fk in backend.get_foreign_keys(name)}
            expected = {(f.column_name, f.rel_model._meta.table_name, f.rel_field.column_name)
                        for f in model._meta.sorted_fields if hasattr(f, 'rel_model')}
            require(keys == expected, 'Foreign key mismatch')
    migrate(backend)  # Existing column names, unique indexes and InnoDB checks.


def definitions(backend):
    with backend.connection_context():
        tables = set(backend.get_tables())
        require(tables <= {m._meta.table_name for m in TABLES}, 'Unexpected table definition')
        return {t: backend.execute_sql(f'SHOW CREATE TABLE `{t}`').fetchone()[1] for t in tables}


def exercise_data(backend):
    with backend.connection_context():
        Player.create(discord_id=123456789012345678, xuid='18446744073709551615')
        for values in ({'discord_id': 123456789012345678}, {'xuid': '18446744073709551615'}):
            try:
                with backend.atomic():
                    Player.create(**values)
            except IntegrityError:
                pass
            else:
                raise ValueError('Unique identifier constraint missing')
        Player.create()  # Multiple null identifiers must remain allowed.
        Player.create()
        first, second = Player.create(), Player.create()

    def race(player_ids, xuids):
        barrier = Barrier(2)
        def worker(player_id, xuid):
            with backend.connection_context():
                barrier.wait(timeout=10)
                try:
                    link_xbox(player_id, xuid, actor=123456789012345678,
                              evidence='synthetic ownership evidence')
                    return True
                except (IntegrityError, ValueError):
                    return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            jobs = [pool.submit(worker, pid, xid) for pid, xid in zip(player_ids, xuids)]
            outcomes = [job.result(timeout=45) for job in jobs]
        require(sum(outcomes) == 1, 'Concurrent link must have exactly one winner')

    race([first.id, second.id], ['123456', '123456'])
    with backend.connection_context():
        require(Player.select().where(Player.xuid == '123456').count() == 1, 'XUID has multiple owners')
        require(Identity.select().where((Identity.kind == 'xuid') & (Identity.value == '123456')).count() == 1,
                'Losing link left identity evidence')
        third = Player.create()
    race([third.id, third.id], ['234567', '345678'])
    with backend.connection_context():
        require(Identity.select().where(Identity.player == third.id).count() == 1, 'Concurrent overwrite occurred')
        owner = Player.get(Player.xuid == '123456')
        now = datetime(2026, 11, 3, 18, tzinfo=timezone.utc)
        start = int((now - timedelta(hours=3)).timestamp())
        body = {'result': {'activity': {'123456': [
            {'s': start, 'e': start+3600}, {'s': start+1800, 'e': start+5400},
            {'s': start+6000, 'e': 2**63-1}]}}}
        snapshot = Snapshot(parse_stories(body, now), now)
        require(ingest(snapshot, '42')['created'] == 3, 'Initial ingestion failed')
        require(ingest(snapshot, '42')['created'] == 0, 'Repeated ingestion duplicated records')
        result = observed_statistics(owner.id, start=now-timedelta(days=1), end=now, selected_realm='42')
        require(result['observed_seconds'] == 5400 and result['confirmed_sessions'] is None,
                'Overlapping activity double-counted or promoted to sessions')
        require(RealmActivity.select().where(RealmActivity.status == 'quarantined').count() == 1,
                'Huge future end not quarantined')


def reset_synthetic(backend):
    # Called only after local Docker identity/empty-baseline checks, on synthetic data.
    with backend.connection_context():
        require(set(backend.get_tables()) <= {m._meta.table_name for m in TABLES}, 'Unknown table: refuse cleanup')
        backend.drop_tables(TABLES, safe=True)


def failure_cases(backend):
    reset_synthetic(backend)
    try:
        migrate(backend, apply=True)
    except ValueError:
        pass
    else:
        raise ValueError('Backup assertion not enforced')
    with backend.connection_context():
        require(not backend.get_tables(), 'Refused migration wrote tables')
    original = backend.create_tables
    def interrupted(models, **kwargs):
        original([Player], **kwargs)
        raise RuntimeError('synthetic DDL interruption')
    backend.create_tables = interrupted
    try:
        try:
            migrate(backend, apply=True, backup_verified=True)
        except RuntimeError:
            pass
        else:
            raise ValueError('Injected interruption did not run')
    finally:
        backend.create_tables = original
    with backend.connection_context():
        require(set(backend.get_tables()) == {'captain_player'}, 'Partial DDL not visible')
        sentinel = Player.create(gamertag='Synthetic sentinel').id
    migrate(backend, apply=True, backup_verified=True)
    with backend.connection_context():
        require(Player.get_by_id(sentinel).gamertag == 'Synthetic sentinel', 'Resume lost sentinel')
        backend.execute_sql('ALTER TABLE captain_player ADD COLUMN staging_unexpected INT NULL')
    expect_refusal(backend)
    reset_synthetic(backend)
    with backend.connection_context():
        backend.create_tables([Player])
        index = next(i.name for i in backend.get_indexes('captain_player') if i.unique and i.columns == ['discord_id'])
        require(re.fullmatch(r'[A-Za-z0-9_]+', index), 'Unexpected generated index name')
        backend.execute_sql(f'ALTER TABLE captain_player DROP INDEX `{index}`')
    expect_refusal(backend)
    reset_synthetic(backend)
    with backend.connection_context():
        backend.create_tables([Player])
        backend.execute_sql('ALTER TABLE captain_player ENGINE=MyISAM')
    expect_refusal(backend)


def expect_refusal(backend):
    before = contents(backend)
    schema_before = definitions(backend)
    try:
        migrate(backend, apply=True, backup_verified=True)
    except ValueError:
        pass
    else:
        raise ValueError('Incompatible schema accepted')
    require(contents(backend) == before, 'Refused migration altered data/schema tables')
    require(schema_before == definitions(backend), 'Refused migration altered definitions')


def run(docker, image, version, password):
    docker.local_context()
    endpoints = [docker.inspect(name, image) for name in NAMES]
    require(endpoints[0][0] != endpoints[1][0] and endpoints[0][1] == endpoints[1][1],
            'Need separate ports and identical images')
    backends = [explicit_backend(port, password) for port, _ in endpoints]
    evidence = [server_identity(b, n, version) for b,n in zip(backends, NAMES)]
    stage, restore = backends
    try:
        require(len(registry_migrate(stage)['missing_tables']) == 8, 'Expected original eight-table plan')
        with stage.connection_context():
            require(not stage.get_tables(), 'Preflight wrote tables')
        registry_migrate(stage, apply=True, backup_verified=True)
        with stage.connection_context():
            sentinel = Player.create(gamertag='Synthetic baseline').id
        require(migrate(stage)['missing_tables'] == ['captain_realm_activity'], 'Additive plan differs')
        migrate(stage, apply=True, backup_verified=True)
        before = contents(stage)
        migrate(stage, apply=True, backup_verified=True)
        require(contents(stage) == before, 'Repeat migration altered records')
        with stage.connection_context():
            require(Player.get_by_id(sentinel).gamertag == 'Synthetic baseline', 'Additive migration lost data')
        validate_schema(stage)
        db.initialize(stage)
        exercise_data(stage)
        baseline = contents(stage)
        schema_baseline = definitions(stage)
        dump = docker.sql_stream(NAMES[0], dump=True)
        require(bool(dump), 'Empty backup')
        docker.sql_stream(NAMES[1], data=dump)
        validate_schema(restore)
        require(contents(restore) == baseline, 'Independent restore differs')
        require(definitions(restore) == schema_baseline, 'Restored table definitions differ')
        db.initialize(stage)
        failure_cases(stage)
        return {'status': 'passed', 'servers': evidence, 'image': image,
                'backup_sha256': hashlib.sha256(dump).hexdigest(),
                'checks': ['eight_table_schema', 'additive_ninth_table', 'repeat_apply',
                           'unique_and_nullable_ids', 'two_connection_identity_races',
                           'repeat_overlap_quarantine_ingestion', 'independent_restore_all_rows',
                           'backup_gate', 'partial_ddl_resume', 'schema_index_engine_refusal'],
                'production_accessed': False,
                'limitation': 'Synthetic SQL behavior only; production TLS/configuration and deployment not tested'}
    finally:
        for backend in backends:
            if not backend.is_closed():
                backend.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--docker-context', choices=['default', 'desktop-linux'], default='default')
    parser.add_argument('--image', required=True, help='Approved official mariadb@sha256 digest')
    parser.add_argument('--version', required=True, help='Exact approved MariaDB version, e.g. 12.3.3')
    parser.add_argument('--allow-synthetic-ddl', action='store_true')
    args = parser.parse_args()
    try:
        require(args.allow_synthetic_ddl, 'Explicit synthetic DDL acknowledgment required')
        require(re.fullmatch(r'mariadb@sha256:[0-9a-f]{64}', args.image), 'Pinned official image required')
        require(re.fullmatch(r'\d+\.\d+\.\d+', args.version), 'Exact version required')
        password = os.environ.get('CAPTAIN_STAGE_PASSWORD', '')
        require(len(password) >= 24, 'Fresh staging password required')
        result = run(Docker(args.docker_context), args.image, args.version, password)
        print(json.dumps(result, indent=2))
    except Exception as error:
        # Neither SQL errors nor subprocess output may expose passwords/row values.
        print(json.dumps({'status': 'failed', 'category': type(error).__name__,
                          'detail': str(error) if type(error) is ValueError else 'Private error details suppressed',
                          'action': 'Stop. Preserve isolated containers; no automatic retry/drop/production fallback.'}))
        raise SystemExit(1) from None


if __name__ == '__main__':
    main()
