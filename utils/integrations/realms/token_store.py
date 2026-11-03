"""Single-writer authenticated-encrypted storage with a private Apollo exception.

Call open/close using a context manager. Local service identity is trusted; ACLs
and encryption cannot protect against an attacker controlling that identity.
"""
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
from typing import Protocol

from cryptography.fernet import Fernet, InvalidToken

from .errors import ProtocolError, StorageBusy, StorageError
from .models import Identity, Secret, StoredAccount, text

MAX_CACHE_BYTES = 65536
CHECKOUT_ROOT = Path(__file__).resolve().parents[3]
APOLLO_PRIVATE_DIRECTORY = ".captain-realms-private"


def validate_location(directory):
    """Only the designated, ignored, untracked Apollo folder may be in checkout.

    Check again at each storage boundary so removing ignore protection or tracking
    a private file makes subsequent use fail closed. Git output is never logged.
    """
    root = CHECKOUT_ROOT.resolve()
    if not directory.is_relative_to(root):
        return
    if directory != root / APOLLO_PRIVATE_DIRECTORY / "tokens":
        raise StorageError()
    private_permissions(directory.parent)
    failed = False
    environment = {k: v for k, v in os.environ.items() if k.upper() in {
        "PATH", "SYSTEMROOT", "WINDIR", "HOME", "USERPROFILE", "TEMP", "TMP",
    }}
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    try:
        common = dict(capture_output=True, stdin=subprocess.DEVNULL, timeout=5, env=environment,
                      creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        ignored = subprocess.run(["git", "-C", str(root), "check-ignore", "--quiet", "--",
                                  APOLLO_PRIVATE_DIRECTORY + "/"], **common)
        tracked = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "--",
                                  APOLLO_PRIVATE_DIRECTORY + "/"], **common)
        failed = ignored.returncode != 0 or tracked.returncode != 0 or bool(tracked.stdout)
    except (OSError, subprocess.SubprocessError):
        failed = True
    if failed:
        raise StorageError()


class TokenStore(Protocol):
    def open(self): ...
    def close(self): ...
    def load(self) -> StoredAccount | None: ...
    def save(self, account: StoredAccount): ...


def reject_links(path):
    """Reject existing symlink/junction/reparse components, not just the leaf."""
    for component in (path, *path.parents):
        if component.is_symlink() or (hasattr(component, "is_junction") and component.is_junction()):
            raise StorageError()
        if component.exists() and getattr(component.lstat(), "st_file_attributes", 0) & 0x400:
            raise StorageError()


def _windows_permissions(path, create=False):
    # Fixed script; path is passed via environment, never interpolated in shell text.
    # Only current identity, SYSTEM and local Administrators may have allow entries.
    script = r"""$ErrorActionPreference = 'Stop'
 $p = $env:CAPTAIN_PRIVATE_PATH
 $sid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User
 if ($env:CAPTAIN_PRIVATE_CREATE -eq '1') {
   $acl = [System.IO.Directory]::GetAccessControl($p)
   $acl.SetAccessRuleProtection($true, $false)
   foreach ($rule in @($acl.Access)) { [void]$acl.RemoveAccessRuleSpecific($rule) }
   $rule = [System.Security.AccessControl.FileSystemAccessRule]::new($sid, 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow')
   $acl.AddAccessRule($rule)
   [System.IO.Directory]::SetAccessControl($p, $acl)
 }
 if ([System.IO.Directory]::Exists($p)) { $acl = [System.IO.Directory]::GetAccessControl($p) }
 else { $acl = [System.IO.File]::GetAccessControl($p) }
 $trusted = @($sid.Value, 'S-1-5-18', 'S-1-5-32-544')
 if ($acl.GetOwner([System.Security.Principal.SecurityIdentifier]).Value -notin $trusted) { exit 1 }
 foreach ($rule in $acl.Access) {
   if ($rule.AccessControlType -eq 'Allow' -and $rule.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value -notin $trusted) { exit 1 }
 }
"""
    # Do not propagate token/key environment variables to the ACL helper process.
    environment = {k: v for k, v in os.environ.items() if k.upper() in {"SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP"}}
    environment.update(CAPTAIN_PRIVATE_PATH=str(path), CAPTAIN_PRIVATE_CREATE="1" if create else "0")
    result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                            env=environment, capture_output=True, timeout=15, check=False,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode:
        raise StorageError()


def private_permissions(path, *, create=False):
    failed = False
    try:
        if os.name == "nt":
            _windows_permissions(path, create)
        else:
            mode = path.stat()
            if mode.st_uid != os.getuid() or stat.S_IMODE(mode.st_mode) & 0o077:
                raise StorageError()
    except (OSError, subprocess.SubprocessError):
        failed = True
    if failed:
        raise StorageError()


class EncryptedTokenStore:
    def __init__(self, directory, binding, keys, active_key_id):
        candidate = Path(directory).absolute()
        reject_links(candidate)
        self.directory = candidate.resolve()
        self.binding = dict(binding)
        self.active_key_id = active_key_id
        self._lock = None
        self._keys = {}
        invalid = False
        try:
            if not keys or active_key_id not in keys or any(not isinstance(k, str) or not k or len(k) > 64 for k in keys):
                raise ValueError()
            self._keys = {name: Fernet(key.value.encode("ascii")) for name, key in keys.items()}
        except (ValueError, TypeError, AttributeError, UnicodeError):
            invalid = True
        if invalid:
            raise StorageError()
        validate_location(self.directory)
        self.path = self.directory / "account.realms.enc"

    def __repr__(self):
        return "EncryptedTokenStore(<private>)"

    def open(self):
        if self._lock is not None:
            raise StorageBusy()
        failed = False
        busy = False
        handle = None
        try:
            reject_links(self.directory)
            validate_location(self.directory)
            if not self.directory.exists():
                # Parent must be provisioned by the operator, never create a path tree implicitly.
                self.directory.mkdir(mode=0o700)
                private_permissions(self.directory, create=True)
            private_permissions(self.directory)
            lock_path = self.directory / "writer.lock"
            reject_links(lock_path)
            fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
            handle = os.fdopen(fd, "r+b", buffering=0)
            private_permissions(lock_path)
            if os.name == "nt":
                import msvcrt
                if os.fstat(handle.fileno()).st_size == 0:
                    handle.write(b"0")
                handle.seek(0)
                try:
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                except OSError:
                    busy = True
            else:
                import fcntl
                try:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except OSError:
                    busy = True
            if not busy:
                self._lock = handle
        except (OSError, ValueError, subprocess.SubprocessError):
            failed = True
        except StorageError:
            if handle:
                handle.close()
            raise
        if failed or busy:
            if handle:
                handle.close()
            if busy:
                raise StorageBusy()
            raise StorageError()
        return self

    def close(self):
        if self._lock:
            self._lock.close()  # OS releases the lock even after an unclean process exit.
            self._lock = None

    def __enter__(self):
        return self.open()

    def __exit__(self, *args):
        self.close()

    def _check(self):
        if self._lock is None:
            raise StorageError()
        reject_links(self.directory)
        validate_location(self.directory)
        private_permissions(self.directory)
        reject_links(self.path)

    def load(self):
        self._check()
        if not self.path.exists():
            return None
        invalid = False
        account = None
        try:
            private_permissions(self.path)
            if self.path.stat().st_size > MAX_CACHE_BYTES or self.path.stat().st_nlink != 1:
                raise ValueError()
            with self.path.open("rb") as stream:
                outer = json.loads(stream.read(MAX_CACHE_BYTES + 1))
            key = self._keys[outer["key_id"]]
            document = json.loads(key.decrypt(outer["ciphertext"].encode("ascii")))
            if not isinstance(document, dict) or set(document) != {"version", "binding", "key_id", "revoked", "xuid", "gamertag", "refresh"} or type(document["version"]) is not int or document["version"] != 1 or document["binding"] != self.binding or document["key_id"] != outer["key_id"]:
                raise ValueError()
            revoked = document["revoked"]
            xuid = text(document["xuid"])
            if type(revoked) is not bool or not xuid.isascii() or not xuid.isdigit():
                raise ValueError()
            account = StoredAccount(Secret(text(document["refresh"])), Identity(xuid, text(document["gamertag"])), revoked)
        except (ValueError, KeyError, TypeError, OSError, UnicodeError, InvalidToken, ProtocolError, AttributeError):
            invalid = True
        if invalid:
            raise StorageError()
        return account

    def save(self, account):
        self._check()
        invalid = False
        temporary = None
        try:
            document = dict(version=1, binding=self.binding, key_id=self.active_key_id,
                            refresh=account.refresh.value, xuid=account.identity.xuid,
                            gamertag=account.identity.gamertag, revoked=account.revoked)
            ciphertext = self._keys[self.active_key_id].encrypt(json.dumps(document).encode()).decode("ascii")
            payload = json.dumps({"key_id": self.active_key_id, "ciphertext": ciphertext}).encode()
            if len(payload) > MAX_CACHE_BYTES:
                raise ValueError()
            fd, temporary = tempfile.mkstemp(prefix="rotation-", suffix=".realms.enc", dir=self.directory)
            with os.fdopen(fd, "wb") as stream:
                private_permissions(Path(temporary))
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            temporary = None
            # Persist directory entry on POSIX; Windows replace is atomic on same volume.
            if os.name != "nt":
                fd = os.open(self.directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
        except (ValueError, TypeError, OSError, subprocess.SubprocessError):
            invalid = True
        finally:
            if temporary is not None:
                Path(temporary).unlink(missing_ok=True)
        if invalid:
            raise StorageError()

    def load_panel_sessions(self):
        """Separate encrypted auxiliary record; never reads/writes account credentials."""
        return self._load_auxiliary("panel-sessions.realms.enc", "panel-sessions-v1")

    def load_gamertags(self):
        return self._load_auxiliary("gamertags.realms.enc", "gamertags-v1")

    def save_gamertags(self, data):
        self._save_auxiliary("gamertags.realms.enc", "gamertags-v1", data)

    def _load_auxiliary(self, filename, kind):
        self._check()
        path = self.directory / filename
        reject_links(path)
        if not path.exists():
            return None
        try:
            private_permissions(path)
            if path.stat().st_size > MAX_CACHE_BYTES or path.stat().st_nlink != 1:
                raise ValueError()
            with path.open("rb") as stream:
                raw = stream.read(MAX_CACHE_BYTES + 1)
            if len(raw) > MAX_CACHE_BYTES:
                raise ValueError()
            outer = json.loads(raw)
            inner = json.loads(self._keys[outer["key_id"]].decrypt(outer["ciphertext"].encode("ascii")))
            if inner["binding"] != self.binding or inner["kind"] != kind:
                raise ValueError()
            return inner["data"]
        except (ValueError, KeyError, TypeError, OSError, UnicodeError, InvalidToken, AttributeError):
            pass
        raise StorageError()

    def save_panel_sessions(self, data):
        self._save_auxiliary("panel-sessions.realms.enc", "panel-sessions-v1", data)

    def _save_auxiliary(self, filename, kind, data):
        self._check()
        path = self.directory / filename
        reject_links(path)
        if path.exists():
            private_permissions(path)
            if path.stat().st_nlink != 1:
                raise StorageError()
        temporary = None
        invalid = False
        try:
            inner = dict(binding=self.binding, kind=kind, data=data)
            ciphertext = self._keys[self.active_key_id].encrypt(json.dumps(inner, ensure_ascii=False).encode()).decode("ascii")
            payload = json.dumps(dict(key_id=self.active_key_id, ciphertext=ciphertext)).encode()
            if len(payload) > MAX_CACHE_BYTES:
                raise ValueError()
            fd, temporary = tempfile.mkstemp(prefix="sessions-", suffix=".realms.enc", dir=self.directory)
            with os.fdopen(fd, "wb") as stream:
                private_permissions(Path(temporary))
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
            temporary = None
            if os.name != "nt":
                fd = os.open(self.directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
        except (ValueError, TypeError, OSError):
            invalid = True
        finally:
            if temporary is not None:
                Path(temporary).unlink(missing_ok=True)
        if invalid:
            raise StorageError()
