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


class StoriesError(ProtocolError):
    """Fixed diagnostic codes only; no names, IDs, cursors or response bodies."""
    category = 'stories_failed'
    reasons = {
        'realm_missing': 'No accessible Realm named Old Coastal 10 was found.',
        'realm_ambiguous': 'More than one accessible Realm matches Old Coastal 10.',
        'realm_list': 'The accessible Realm list could not be read.',
        'realm_feed': 'The old Realm Stories response could not be read.',
        'club_reference': 'The Realm Stories response has no usable Xbox club reference.',
        'club_page': 'An Xbox Stories page had an unsupported response format.',
        'cursor_repeat': 'Xbox repeated a Stories page cursor; archive fetching stopped to avoid a loop.',
        'cursor_invalid': 'Xbox returned an unsupported Stories page cursor.',
        'archive_fetch': 'The old Realm Stories fetch failed before publication.',
    }

    def __init__(self, reason):
        if reason not in self.reasons:
            raise ValueError('Unsupported Stories error reason')
        self.reason = reason
        super().__init__()
