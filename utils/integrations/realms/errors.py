"""Errors carry fixed categories only, never upstream bodies or credentials."""


class RealmsError(Exception):
    category = "realms_failed"

    def __init__(self):
        super().__init__(self.category)


class ConfigurationError(RealmsError):
    category = "invalid_realms_configuration"


class AccessDenied(RealmsError):
    category = "realms_access_denied"


class Disabled(RealmsError):
    category = "realms_disabled"


class ProtocolError(RealmsError):
    category = "invalid_upstream_response"


class ReauthRequired(RealmsError):
    category = "reauth_required"


class LoginExpired(RealmsError):
    category = "device_login_expired"


class LoginDenied(RealmsError):
    category = "device_login_denied"


class IdentityMismatch(RealmsError):
    category = "account_identity_mismatch"


class StorageError(RealmsError):
    category = "private_token_storage_failed"


class StorageBusy(StorageError):
    category = "token_store_already_in_use"


class TransportError(RealmsError):
    category = "upstream_transport_failed"


class HTTPFailure(RealmsError):
    def __init__(self, status, retry_after=None):
        self.status = status
        self.retry_after = retry_after
        super().__init__()

    category = "upstream_http_failed"
