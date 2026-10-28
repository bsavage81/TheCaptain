from types import SimpleNamespace as NS
import pytest
from utils.integrations.__google_sheets import _safe_failure_details


@pytest.mark.parametrize("kind,hint",[("SpreadsheetNotFound","No accessible spreadsheet"),("WorksheetNotFound","required worksheet"),("RefreshError","authentication failed"),("ReadTimeout","outbound HTTPS")])
def test_safe_classification_never_echoes_private_message(kind,hint):
    error=type(kind,(Exception,),{})("private credentials and applicant data must not be echoed")
    text=_safe_failure_details(error)
    assert kind in text and hint in text
    assert "private credentials" not in text and "applicant data" not in text


def test_disabled_api_reason_and_http_status_are_safe():
    error=RuntimeError("private payload")
    error.response=NS(status_code=403)
    error.error={"status":"PERMISSION_DENIED","message":"private payload", "details":[{"reason":"SERVICE_DISABLED","metadata":{"secret":"private payload"}}]}
    text=_safe_failure_details(error)
    assert "HTTP 403" in text and "SERVICE_DISABLED" in text and "Enable the required Google Sheets API" in text
    assert "private payload" not in text


def test_permission_wrapper_keeps_safe_cause_status():
    cause=RuntimeError("private token")
    cause.response=NS(status_code=403)
    error=PermissionError("private account")
    error.__cause__=cause
    text=_safe_failure_details(error)
    assert "HTTP 403" in text and "denied access" in text
    assert "private" not in text


def test_unrecognized_payload_reason_is_not_echoed():
    error=RuntimeError("private payload")
    error.error={"details":[{"reason":"private secret"}],"errors":[{"reason":["untrusted"]}]}
    assert "private" not in _safe_failure_details(error)


@pytest.mark.parametrize("status,hint",[(400,"native Google spreadsheet"),(401,"rejected authentication"),(429,"temporary/rate-limit"),(503,"temporary/rate-limit")])
def test_http_failure_hints_are_specific_without_payloads(status,hint):
    error=RuntimeError("private response data")
    error.response=NS(status_code=status)
    text=_safe_failure_details(error)
    assert f"HTTP {status}" in text and hint in text
    assert "private response data" not in text
