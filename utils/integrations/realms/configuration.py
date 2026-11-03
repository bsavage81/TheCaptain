"""Versioned local diagnostic configuration; deliberately not botdata settings."""
from dataclasses import dataclass, field
import re
from uuid import UUID

from .errors import AccessDenied, ConfigurationError, Disabled


@dataclass(frozen=True)
class Principal:
    user_id: int
    guild_id: int


@dataclass(frozen=True)
class RealmsConfig:
    enabled: bool = False
    client_id: str = ""
    auth_owner_ids: tuple[int, ...] = ()
    guild_id: int = 0
    account_ref: str = ""
    expected_gamertag: str = field(default="", repr=False)
    client_version: str = ""
    selected_realm_id: str | None = None

    def __post_init__(self):
        try:
            if type(self.enabled) is not bool:
                raise ValueError()
            if not self.enabled:
                return
            if str(UUID(self.client_id)) != self.client_id.lower():
                raise ValueError()
            if not isinstance(self.auth_owner_ids, tuple) or not self.auth_owner_ids or any(
                    type(i) is not int or not 0 < i < 2**64 for i in self.auth_owner_ids):
                raise ValueError()
            if type(self.guild_id) is not int or not 0 < self.guild_id < 2**64:
                raise ValueError()
            if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", self.account_ref):
                raise ValueError()
            if not isinstance(self.expected_gamertag, str) or not self.expected_gamertag.strip() or len(self.expected_gamertag) > 64 or any(ord(c) < 32 for c in self.expected_gamertag):
                raise ValueError()
            if not re.fullmatch(r"[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}(?:\.[0-9]{1,3})?", self.client_version):
                raise ValueError()
            if self.selected_realm_id is not None and not re.fullmatch(r"[1-9][0-9]{0,19}", self.selected_realm_id):
                raise ValueError()
        except (ValueError, TypeError, AttributeError):
            raise ConfigurationError() from None

    @classmethod
    def from_document(cls, document):
        try:
            if not isinstance(document, dict) or set(document) != {"version", "realms"} or type(document["version"]) is not int or document["version"] != 1:
                raise ValueError()
            values = document["realms"]
            if not isinstance(values, dict) or set(values) - set(cls.__dataclass_fields__):
                raise ValueError()
            values = dict(values)
            if "auth_owner_ids" in values:
                if not isinstance(values["auth_owner_ids"], list):
                    raise ValueError()
                values["auth_owner_ids"] = tuple(values["auth_owner_ids"])
            return cls(**values)
        except (ValueError, TypeError):
            raise ConfigurationError() from None

    def authorize(self, principal):
        if not self.enabled:
            raise Disabled()
        if not isinstance(principal, Principal) or type(principal.user_id) is not int or type(principal.guild_id) is not int or principal.user_id not in self.auth_owner_ids or principal.guild_id != self.guild_id:
            raise AccessDenied()

    @property
    def binding(self):
        return {"client_id": self.client_id, "account_ref": self.account_ref,
                "authority": "consumers-v2", "scopes": "XboxLive.signin offline_access"}
