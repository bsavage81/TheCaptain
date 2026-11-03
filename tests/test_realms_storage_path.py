"""Focused path-policy regressions using temporary Git repositories and fake data."""
import subprocess

import pytest

from realms_fakes import account
from test_realms_store import store
from utils.integrations.realms import token_store
from utils.integrations.realms.errors import StorageError


@pytest.fixture
def checkout(tmp_path, monkeypatch):
    root = tmp_path / "checkout"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
    (root / ".gitignore").write_text("/.captain-realms-private/\n")
    private = root / ".captain-realms-private"
    private.mkdir(mode=0o700)
    token_store.private_permissions(private, create=True)
    monkeypatch.setattr(token_store, "CHECKOUT_ROOT", root)
    return root


def test_designated_ignored_untracked_store_preserves_encryption_and_locking(checkout):
    from utils.integrations.realms.errors import StorageBusy
    directory = checkout / ".captain-realms-private" / "tokens"
    with store(directory) as cache:
        cache.save(account())
        assert cache.load() == account()
        assert b"canary-refresh" not in cache.path.read_bytes()
        with pytest.raises(StorageBusy):
            store(directory).open()


@pytest.mark.parametrize("relative", [".", "private", "utils/tokens", ".captain-realms-private",
    ".captain-realms-private/config", ".captain-realms-private/tokens/child", ".captain-realms-private-copy/tokens"])
def test_no_other_checkout_directory_is_permitted(checkout, relative):
    with pytest.raises(StorageError):
        store(checkout / relative)


def test_missing_ignore_rule_blocks_even_the_designated_path(checkout):
    (checkout / ".gitignore").write_text("*.realms.enc\n")
    with pytest.raises(StorageError):
        store(checkout / ".captain-realms-private" / "tokens")


def test_git_local_exclusion_is_supported(checkout):
    (checkout / ".gitignore").write_text("")
    (checkout / ".git" / "info" / "exclude").write_text("/.captain-realms-private/\n")
    assert store(checkout / ".captain-realms-private" / "tokens").directory.name == "tokens"


def test_tracking_any_private_file_blocks_store(checkout):
    path = checkout / ".captain-realms-private" / "dummy.txt"
    path.write_text("synthetic non-secret")
    subprocess.run(["git", "-C", str(checkout), "add", "-f", "--", str(path)], check=True, capture_output=True)
    with pytest.raises(StorageError):
        store(checkout / ".captain-realms-private" / "tokens")


def test_removing_git_protection_blocks_further_reads_and_writes(checkout):
    with store(checkout / ".captain-realms-private" / "tokens") as cache:
        cache.save(account())
        before = cache.path.read_bytes()
        (checkout / ".gitignore").write_text("")
        for operation in (cache.load, lambda: cache.save(account())):
            with pytest.raises(StorageError):
                operation()
        assert cache.path.read_bytes() == before


def test_private_parent_permissions_required(checkout, monkeypatch):
    original = token_store.private_permissions
    def check(path, **kwargs):
        if path == checkout / ".captain-realms-private":
            raise StorageError()
        return original(path, **kwargs)
    monkeypatch.setattr(token_store, "private_permissions", check)
    with pytest.raises(StorageError):
        store(checkout / ".captain-realms-private" / "tokens")


def test_git_failure_is_sanitized_and_fails_closed(checkout, monkeypatch):
    def unavailable(*args, **kwargs):
        raise OSError("canary-private-environment")
    monkeypatch.setattr(token_store.subprocess, "run", unavailable)
    # Bypass only the OS-specific ACL helper to isolate unavailable Git.
    monkeypatch.setattr(token_store, "private_permissions", lambda *a, **k: None)
    with pytest.raises(StorageError) as raised:
        store(checkout / ".captain-realms-private" / "tokens")
    assert raised.value.__context__ is None and "canary" not in str(raised.value)


def test_external_windows_store_still_needs_no_git(tmp_path, monkeypatch):
    monkeypatch.setattr(token_store, "CHECKOUT_ROOT", tmp_path / "checkout")
    def unavailable(*a, **k):
        raise AssertionError("External store should not call Git")
    monkeypatch.setattr(token_store.subprocess, "run", unavailable)
    assert store(tmp_path / "external").directory == (tmp_path / "external").resolve()
