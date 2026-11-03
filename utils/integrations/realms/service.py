"""Explicit auth lifecycle and renewal serialization. No scheduler or Discord imports."""
import asyncio
from dataclasses import dataclass, field
import time

from .client import RealmsClient
from .errors import AccessDenied, IdentityMismatch, ReauthRequired, StorageError
from .microsoft import MicrosoftAuth
from .models import Identity, Secret, StoredAccount
from .transport import REALMS_RP, XBOX_RP
from .xbox import XboxAuth


@dataclass(frozen=True)
class PendingLogin:
    challenge: object = field(repr=False)
    principal: object


class RealmsService:
    """Caller owns store/transport context lifetimes; no automatic authentication.

    Principal IDs must come from a trusted authenticated Discord interaction in a
    future adapter. The local CLI is instead protected by the OS operator boundary.
    """
    def __init__(self, config, transport, store, *, clock=time.time, monotonic=time.monotonic,
                 sleep=asyncio.sleep):
        self.config = config
        self.transport = transport
        self.store = store
        self.clock = clock
        self.microsoft = MicrosoftAuth(transport, config.client_id, clock=clock, monotonic=monotonic, sleep=sleep)
        self.xbox = XboxAuth(transport, clock=clock)
        self._lock = asyncio.Lock()
        self._pending = None
        self._tokens = {}
        self._oauth = None
        self._user = None
        self._account = None
        self._loaded = False
        self._closed = False
        self._blocked = False
        self._login_task = None

    def _check(self, principal):
        self.config.authorize(principal)
        if self._closed:
            raise AccessDenied()

    async def _storage(self, method, *args):
        # Atomic file rotation must finish before cancellation releases the renewal lock.
        task = asyncio.create_task(asyncio.to_thread(method, *args))
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            try:
                await task
            finally:
                raise

    def _identity(self, token):
        if not isinstance(token.xuid, str) or not token.xuid.isascii() or not token.xuid.isdigit() or not isinstance(token.gamertag, str) or any(ord(c) < 32 for c in token.gamertag):
            raise IdentityMismatch()
        if token.gamertag.strip().casefold() != self.config.expected_gamertag.strip().casefold():
            raise IdentityMismatch()
        return Identity(token.xuid, token.gamertag)

    async def begin_device_login(self, principal):
        self._check(principal)
        async with self._lock:
            self._check(principal)
            if self._pending:
                raise AccessDenied()
            challenge = await self.microsoft.begin_device_login()
            self._pending = PendingLogin(challenge, principal)
            return self._pending

    async def complete_device_login(self, principal, pending):
        self._check(principal)
        async with self._lock:
            self._check(principal)
            if not isinstance(pending, PendingLogin) or self._pending is not pending or pending.principal != principal:
                raise AccessDenied()
            self._login_task = asyncio.current_task()
            try:
                oauth = await self.microsoft.poll_device_login(pending.challenge)
                self._check(principal)
                if self._pending is not pending:
                    raise AccessDenied()
                user = await self.xbox.user_token(oauth)
                identity_token = await self.xbox.authorize(user, XBOX_RP)
                identity = self._identity(identity_token)
                previous = await self._storage(self.store.load)
                if previous is not None and previous.identity.xuid != identity.xuid:
                    raise IdentityMismatch()
                # Confirm identity BEFORE storing new account credentials or accessing any Realm.
                self._check(principal)
                account = StoredAccount(oauth.refresh, identity)
                await self._storage(self.store.save, account)
                self._account, self._oauth, self._user = account, oauth, user
                self._loaded, self._blocked = True, False
                self._tokens = {XBOX_RP: identity_token}
                return identity
            finally:
                self._pending = None
                self._login_task = None

    def cancel_device_login(self, principal, pending):
        self._check(principal)
        if not isinstance(pending, PendingLogin) or pending is not self._pending or pending.principal != principal:
            raise AccessDenied()
        self._pending = None
        if self._login_task:
            self._login_task.cancel()

    async def _load(self):
        if not self._loaded:
            self._account = await self._storage(self.store.load)
            self._loaded = True
        if self._blocked or self._account is None or self._account.revoked:
            raise ReauthRequired()
        if self._account.identity.gamertag.strip().casefold() != self.config.expected_gamertag.strip().casefold():
            raise IdentityMismatch()

    async def _renew_oauth(self):
        try:
            oauth = await self.microsoft.refresh(self._account.refresh)
        except ReauthRequired:
            self._blocked = True
            self._tokens.clear()
            self._oauth = self._user = None
            revoked = StoredAccount(Secret("revoked"), self._account.identity, True)
            await self._storage(self.store.save, revoked)
            self._account = revoked
            raise
        # Persist rotation even if the downstream Xbox exchange subsequently fails.
        account = StoredAccount(oauth.refresh, self._account.identity)
        try:
            await self._storage(self.store.save, account)
        except (StorageError, asyncio.CancelledError):
            self._blocked = True
            self._tokens.clear()
            raise
        self._account, self._oauth = account, oauth
        self._user = None
        self._tokens.clear()

    async def authorization_for(self, principal, *, audience=REALMS_RP, rejected=None):
        self._check(principal)
        if audience not in {REALMS_RP, XBOX_RP}:
            raise AccessDenied()
        async with self._lock:
            self._check(principal)
            await self._load()
            current = self._tokens.get(audience)
            # Concurrent 401s share a single renewal; do not rotate again for an obsolete generation.
            if current and current.expires_at > self.clock() + 60 and current is not rejected:
                return current
            if rejected is not None or self._oauth is None or self._oauth.expires_at <= self.clock() + 60:
                await self._renew_oauth()
            if self._user is None or self._user.expires_at <= self.clock() + 60:
                self._user = await self.xbox.user_token(self._oauth)
            identity_token = self._tokens.get(XBOX_RP)
            if identity_token is None or identity_token.expires_at <= self.clock() + 60:
                identity_token = await self.xbox.authorize(self._user, XBOX_RP)
                identity = self._identity(identity_token)
                if identity.xuid != self._account.identity.xuid:
                    self._blocked = True
                    raise IdentityMismatch()
                self._tokens[XBOX_RP] = identity_token
            self._check(principal)
            token = identity_token if audience == XBOX_RP else await self.xbox.authorize(self._user, REALMS_RP)
            if token.xuid is not None and token.xuid != self._account.identity.xuid:
                self._blocked = True
                raise IdentityMismatch()
            self._tokens[audience] = token
            return token

    def client(self, principal, **kwargs):
        self._check(principal)
        return RealmsClient(self.transport, self.authorization_for, self.config, principal, **kwargs)

    async def close(self):
        if self._login_task and self._login_task is not asyncio.current_task():
            self._login_task.cancel()
            try:
                await self._login_task
            except asyncio.CancelledError:
                pass
        async with self._lock:
            self._closed = True
            self._pending = None
            self._tokens.clear()
            self._oauth = self._user = self._account = None
