"""Small immutable models; credentials and identity are redacted in reprs."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
import math

from .errors import ProtocolError


def utcnow():
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class Secret:
    value: str = field(repr=False)

    def __repr__(self):
        return "Secret(<redacted>)"

    __str__ = __repr__


def text(value):
    if not isinstance(value, str) or not value or len(value) > 16384 or any(ord(c) < 32 for c in value):
        raise ProtocolError()
    return value


def seconds(value, maximum=86400 * 30):
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= maximum:
        raise ProtocolError()
    return float(value)


@dataclass(frozen=True)
class OAuthTokens:
    access: Secret
    refresh: Secret
    expires_at: float


@dataclass(frozen=True)
class DeviceChallenge:
    device_code: Secret
    user_code: Secret
    verification_uri: str
    expires_at: float
    interval: float


@dataclass(frozen=True)
class XboxToken:
    token: Secret
    user_hash: Secret
    expires_at: float
    audience: str
    xuid: str | None = field(default=None, repr=False)
    gamertag: str | None = field(default=None, repr=False)

    @property
    def authorization(self):
        return Secret(f"XBL3.0 x={self.user_hash.value};{self.token.value}")


@dataclass(frozen=True)
class Identity:
    xuid: str = field(repr=False)
    gamertag: str = field(repr=False)


@dataclass(frozen=True)
class StoredAccount:
    refresh: Secret
    identity: Identity
    revoked: bool = False


@dataclass(frozen=True)
class Member:
    xuid: str = field(repr=False)
    name: str | None = field(default=None, repr=False)
    accepted: bool | None = None
    operator: bool | None = None
    online: bool | None = None
    permission: str | None = None


def members(data):
    if data is None:
        return None
    if not isinstance(data, list):
        raise ProtocolError()
    result = []
    for p in data:
        if not isinstance(p, dict):
            raise ProtocolError()
        xuid = text(p.get("uuid"))
        if not xuid.isascii() or not xuid.isdigit():
            raise ProtocolError()
        name = p.get("name")
        if name is not None:
            text(name)
        flags = [p.get(k) for k in ("accepted", "operator", "online")]
        if any(f is not None and type(f) is not bool for f in flags):
            raise ProtocolError()
        permission = p.get("permission")
        if permission is not None and permission not in {"VISITOR", "MEMBER", "OPERATOR"}:
            raise ProtocolError()
        result.append(Member(xuid, name, *flags, permission))
    if len({p.xuid for p in result}) != len(result):
        raise ProtocolError()
    return tuple(result)


def realm_id(value):
    if type(value) is int and value > 0:
        return str(value)
    if isinstance(value, str) and value.isascii() and value.isdigit() and 0 < len(value) <= 20 and int(value) > 0:
        return value
    raise ProtocolError()


@dataclass(frozen=True)
class Realm:
    id: str
    name: str = field(repr=False)
    state: str
    players: tuple[Member, ...] | None = field(repr=False)
    expired: bool | None = None

    @classmethod
    def parse(cls, data):
        if not isinstance(data, dict):
            raise ProtocolError()
        state = data.get("state")
        if state not in {"OPEN", "CLOSED"}:
            raise ProtocolError()
        expired = data.get("expired")
        if expired is not None and type(expired) is not bool:
            raise ProtocolError()
        return cls(realm_id(data.get("id")), text(data.get("name")), state, members(data.get("players")), expired)


@dataclass(frozen=True)
class Activity:
    realm_id: str
    players: tuple[Member, ...] = field(repr=False)


@dataclass(frozen=True)
class Invitation:
    id: str = field(repr=False)
    world_name: str = field(repr=False)


@dataclass(frozen=True)
class Snapshot:
    """A successful observation only. Exceptions never synthesize an empty snapshot."""
    data: object = field(repr=False)
    observed_at: datetime
