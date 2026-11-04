"""Offline staging guard tests. These are not MariaDB execution evidence."""
from copy import deepcopy
import importlib
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from scripts import phase6_mariadb_validation as stage

IMAGE = 'mariadb@sha256:' + 'a'*64


def container():
    return {'Name': '/'+stage.NAMES[0], 'State': {'Running': True},
            'Config': {'Hostname': stage.NAMES[0], 'Image': IMAGE,
                       'Labels': {'org.thecaptain.phase6': 'synthetic-only'}},
            'HostConfig': {'Privileged': False, 'Binds': None,
                           'Tmpfs': {'/var/lib/mysql': 'size=536870912'},
                           'NetworkMode': 'captain-phase6-stage_stage'},
            'Mounts': [{'Type': 'tmpfs'}],
            'NetworkSettings': {'Ports': {'3306/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '33307'}]}},
            'Image': 'sha256:synthetic-image'}


@pytest.mark.parametrize('change', [
    lambda v: v['Config'].update(Image='mariadb:latest'),
    lambda v: v['Config'].update(Labels={}),
    lambda v: v['Config'].update(Hostname='production'),
    lambda v: v['State'].update(Running=False),
    lambda v: v['HostConfig'].update(Privileged=True),
    lambda v: v['HostConfig'].update(Binds=['/host:/data']),
    lambda v: v['HostConfig'].update(Tmpfs={}),
    lambda v: v['HostConfig'].update(NetworkMode='host'),
    lambda v: v.update(Mounts=[{'Type': 'volume'}]),
    lambda v: v['NetworkSettings']['Ports']['3306/tcp'][0].update(HostIp='0.0.0.0'),
    lambda v: v['NetworkSettings']['Ports'].update({'33060/tcp': []}),
    lambda v: v['NetworkSettings']['Ports']['3306/tcp'][0].update(HostPort='330'),
])
def test_container_must_be_disposable_local_and_pinned(change):
    value = deepcopy(container())
    change(value)
    with pytest.raises(ValueError):
        stage.validate_container(value, stage.NAMES[0], IMAGE)


def test_only_loopback_backend_and_fixed_schema():
    port, _ = stage.validate_container(container(), stage.NAMES[0], IMAGE)
    backend = stage.explicit_backend(port, 'synthetic-password')
    assert backend.database == stage.SCHEMA
    assert backend.connect_params['host'] == '127.0.0.1'
    assert backend.connect_params['user'] == stage.USER
    assert backend.is_closed()


@pytest.mark.parametrize('host', ['tcp://127.0.0.1:2375', 'ssh://database', 'tcp://production:2376'])
def test_remote_daemon_refused_before_inspection(host):
    docker = stage.Docker('default')
    docker.call = Mock(return_value=json.dumps([{'Endpoints': {'docker': {'Host': host}}}]).encode())
    with pytest.raises(ValueError, match='local Docker'):
        docker.local_context()
    assert docker.call.call_count == 1


def test_network_cannot_be_shared():
    docker = stage.Docker('default')
    docker.call = Mock(side_effect=[
        json.dumps([{'Endpoints': {'docker': {'Host': 'unix:///var/run/docker.sock'}}}]).encode(),
        json.dumps([{'Internal': True, 'Driver': 'bridge', 'Containers': {
            'one': {'Name': stage.NAMES[0]}, 'two': {'Name': stage.NAMES[1]}, 'other': {'Name': 'production'}}}]).encode()])
    with pytest.raises(ValueError, match='only the two'):
        docker.local_context()


@pytest.mark.parametrize('host', ['npipe:////./pipe/docker_engine',
                                 'npipe:////./pipe/dockerDesktopLinuxEngine',
                                 'unix:///var/run/docker.sock'])
def test_local_dedicated_network_allowed(host):
    docker = stage.Docker('default')
    docker.call = Mock(side_effect=[
        json.dumps([{'Endpoints': {'docker': {'Host': host}}}]).encode(),
        json.dumps([{'Internal': True, 'Driver': 'bridge', 'Containers': {
            'one': {'Name': stage.NAMES[0]}, 'two': {'Name': stage.NAMES[1]}}}]).encode()])
    docker.local_context()


def test_import_cannot_load_dotenv_or_production_factory(monkeypatch):
    import dotenv
    from utils.database import __database
    poison = Mock(side_effect=AssertionError('Production configuration touched'))
    monkeypatch.setattr(dotenv, 'load_dotenv', poison)
    monkeypatch.setattr(__database, 'make_database', poison)
    importlib.reload(stage)
    poison.assert_not_called()


def test_docker_cli_is_argument_list_without_inherited_remote_context(monkeypatch):
    monkeypatch.setenv('DOCKER_HOST', 'tcp://production:2375')
    monkeypatch.setenv('DOCKER_CONTEXT', 'production')
    execute = Mock(return_value=SimpleNamespace(returncode=0, stdout=b'{}', stderr=b''))
    monkeypatch.setattr(stage.subprocess, 'run', execute)
    stage.Docker('default').call('inspect', 'container')
    args, kwargs = execute.call_args
    assert args[0] == ['docker', '--context', 'default', 'inspect', 'container']
    assert 'DOCKER_HOST' not in kwargs['env'] and 'DOCKER_CONTEXT' not in kwargs['env']
    assert kwargs.get('shell', False) is False


def test_failure_does_not_print_private_stderr(monkeypatch):
    monkeypatch.setattr(stage.subprocess, 'run', Mock(return_value=SimpleNamespace(
        returncode=1, stdout=b'', stderr=b'synthetic-secret-must-not-appear')))
    with pytest.raises(ValueError) as error:
        stage.Docker('default').call('inspect', 'container')
    assert 'synthetic-secret' not in str(error.value)


def test_explicit_acknowledgment_before_any_docker_or_database(monkeypatch, capsys):
    monkeypatch.setattr('sys.argv', ['stage', '--image', IMAGE, '--version', '12.3.3'])
    execute = Mock(side_effect=AssertionError('No Docker before acknowledgment'))
    monkeypatch.setattr(stage, 'run', execute)
    with pytest.raises(SystemExit):
        stage.main()
    execute.assert_not_called()
    assert json.loads(capsys.readouterr().out)['status'] == 'failed'
