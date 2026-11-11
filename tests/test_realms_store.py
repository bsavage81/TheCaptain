import json
import os
from pathlib import Path
import subprocess
import sys

from cryptography.fernet import Fernet
import pytest

from realms_fakes import account, config
from utils.integrations.realms.errors import StorageBusy, StorageError
from utils.integrations.realms.models import Secret
from utils.integrations.realms import token_store
from utils.integrations.realms.token_store import EncryptedTokenStore


def store(path, keys=None, active="key-one", binding=None):
    return EncryptedTokenStore(path, binding or config().binding,
        keys or {"key-one": Secret(Fernet.generate_key().decode())}, active)


def test_encrypted_roundtrip_locking_and_key_rotation(tmp_path):
    directory = tmp_path / "private"
    keys = {"key-one": Secret(Fernet.generate_key().decode())}
    with store(directory, keys) as first:
        assert first.load() is None
        first.save(account())
        assert first.load() == account()
        data = first.path.read_text()
        assert all(canary not in data for canary in ("canary-refresh-old", "Synthetic Player", "123456"))
        with pytest.raises(StorageBusy):
            store(directory, keys).open()
    with store(directory, keys) as restarted:
        assert restarted.load() == account()
    keys["key-two"] = Secret(Fernet.generate_key().decode())
    with store(directory, keys, active="key-two") as rotated:
        rotated.save(rotated.load())
        assert json.loads(rotated.path.read_text())["key_id"] == "key-two"
    with store(directory, {"key-two": keys["key-two"]}, active="key-two") as final:
        assert final.load() == account()


def test_wrong_key_corrupt_cache_and_binding_fail_closed(tmp_path):
    directory = tmp_path / "private"
    keys = {"key-one": Secret(Fernet.generate_key().decode())}
    with store(directory, keys) as first:
        first.save(account())
    with store(directory) as wrong_key:
        with pytest.raises(StorageError):
            wrong_key.load()
    binding = dict(config().binding, account_ref="different-account")
    with store(directory, keys, binding=binding) as wrong_account:
        with pytest.raises(StorageError):
            wrong_account.load()
    with store(directory, keys) as corrupt:
        corrupt.path.write_bytes(b"canary-corrupt")
        with pytest.raises(StorageError) as raised:
            corrupt.load()
        assert "canary" not in str(raised.value) and raised.value.__context__ is None


def test_failed_atomic_rotation_preserves_previous_cache(tmp_path, monkeypatch):
    with store(tmp_path / "private") as cache:
        cache.save(account())
        previous = cache.path.read_bytes()
        def fail(*args):
            raise OSError("canary-secret")
        monkeypatch.setattr(token_store.os, "replace", fail)
        with pytest.raises(StorageError) as raised:
            cache.save(account(refresh=Secret("canary-new")))
        assert raised.value.__context__ is None
        assert cache.path.read_bytes() == previous
        assert not list(cache.directory.glob("rotation-*"))


def test_missing_key_closed_store_and_in_checkout_refused(tmp_path):
    with pytest.raises(StorageError):
        EncryptedTokenStore(tmp_path / "private", config().binding, {}, "none")
    with pytest.raises(StorageError):
        store(Path(__file__).resolve().parents[1] / "private")
    cache = store(tmp_path / "private")
    with pytest.raises(StorageError):
        cache.load()
    with pytest.raises(StorageError):
        cache.save(account())


def test_second_process_cannot_take_writer_lock(tmp_path):
    directory = tmp_path / "private"
    with store(directory):
        script = """
import sys
from cryptography.fernet import Fernet
from utils.integrations.realms.token_store import EncryptedTokenStore
from utils.integrations.realms.models import Secret
from utils.integrations.realms.errors import StorageBusy
try:
    EncryptedTokenStore(sys.argv[1], {}, {'test': Secret(Fernet.generate_key().decode())}, 'test').open()
except StorageBusy:
    print('busy')
else:
    raise SystemExit(1)
"""
        result = subprocess.run([sys.executable, "-c", script, str(directory)], capture_output=True, timeout=30)
        assert result.returncode == 0 and result.stdout.strip() == b"busy"


def test_symlink_or_junction_refused(tmp_path):
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "linked"
    if os.name == "nt":
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True)
        if result.returncode:
            pytest.skip("Junction creation unavailable")
    else:
        link.symlink_to(target, target_is_directory=True)
    with pytest.raises(StorageError):
        store(link)


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission branch")
def test_posix_broad_permissions_refused(tmp_path):
    path = tmp_path / "public"
    path.mkdir(mode=0o755)
    with pytest.raises(StorageError):
        store(path).open()


@pytest.mark.skipif(os.name != "nt", reason="Windows ACL branch")
def test_windows_broad_acl_refused(tmp_path):
    path = tmp_path / "public"
    path.mkdir()
    # SID avoids locale-dependent account names. Read-only grant is still unacceptable.
    result = subprocess.run(["icacls", str(path), "/grant", "*S-1-1-0:(OI)(CI)R"], capture_output=True)
    assert result.returncode == 0
    with pytest.raises(StorageError):
        store(path).open()


@pytest.mark.parametrize("document", [None, [], {"version": True},
    {"version": 1, "key_id": "key-one", "binding": config().binding, "revoked": False,
     "xuid": "123456", "gamertag": "Synthetic Player", "refresh": "canary\nsecret"}])
def test_authenticated_but_malformed_payload_is_sanitized(tmp_path, document):
    with store(tmp_path / "private") as cache:
        ciphertext = cache._keys["key-one"].encrypt(json.dumps(document).encode()).decode()
        cache.path.write_text(json.dumps({"key_id": "key-one", "ciphertext": ciphertext}))
        # New file inherits the private directory ACL; POSIX requires explicit private mode.
        if os.name != "nt":
            cache.path.chmod(0o600)
        with pytest.raises(StorageError) as raised:
            cache.load()
        assert raised.value.__context__ is None


def test_acl_helper_does_not_inherit_secret_environment(monkeypatch, tmp_path):
    from types import SimpleNamespace
    captured = {}
    monkeypatch.setenv("CAPTAIN_REALMS_KEYS", "canary-key")
    monkeypatch.setenv("OTHER_PRIVATE_TOKEN", "canary-token")
    def run(*args, **kwargs):
        captured.update(kwargs["env"])
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(token_store.subprocess, "run", run)
    token_store._windows_permissions(tmp_path)
    assert "CAPTAIN_REALMS_KEYS" not in captured and "OTHER_PRIVATE_TOKEN" not in captured
    assert "canary" not in repr(captured)


async def test_story_delivery_encrypted_roundtrip_survives_restart(tmp_path):
    from utils.realms.story_deliveries import StoryDeliveries
    keys = {'key-one': Secret(Fernet.generate_key().decode())}
    directory = tmp_path / 'private'
    with store(directory, keys) as cache:
        cache.save(account())
        credential_bytes = cache.path.read_bytes()
        ledger = StoryDeliveries(cache)
        await ledger.load()
        key = ledger.key(202, 303, '42', 'canary-private-story')
        await ledger.save(key, 987654321, 'hearts 3 comments 1')
        assert cache.path.read_bytes() == credential_bytes
        raw = (directory / 'story-deliveries.realms.enc').read_text()
        assert 'hearts 3' not in raw and '987654321' not in raw and 'canary-private-story' not in raw
    with store(directory, keys) as cache:
        ledger = StoryDeliveries(cache)
        await ledger.load()
        assert ledger.entries[key] == {'message_id': 987654321, 'footer': 'hearts 3 comments 1'}
