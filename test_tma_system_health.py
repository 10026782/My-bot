"""Regression tests for the TMA system-health Airtable read boundary."""

from __future__ import annotations

import ast
import inspect
from types import SimpleNamespace
from unittest.mock import patch

import tma_api
from tools.airtable_read_adapter import AirtableReadError


def _payload(read_side_effect=None):
    with patch.object(tma_api, "_BOT_TOKEN", ""), \
         patch.object(tma_api, "_read_list_records", side_effect=read_side_effect) as read, \
         patch("feature_flags.get_emergency_stop_status", return_value=SimpleNamespace(manager_status=None)):
        result = tma_api._system_health_payload(object())
    return result, read


def test_airtable_health_success_preserves_payload_and_read_contract():
    result, read = _payload()

    assert result["services"]["airtable"] == "ok"
    assert set(result) == {"status", "services", "emergency_flags", "active_emergency", "checked_at"}
    read.assert_called_once_with("Leads", max_records=1, paginate=False, timeout=5)


def test_airtable_http_error_preserves_status_message():
    result, _ = _payload(AirtableReadError("Leads list: HTTP 500", status_code=500))
    assert result["services"]["airtable"] == "error:500"


def test_airtable_transport_error_preserves_legacy_message_and_never_raises():
    result, _ = _payload(TimeoutError("timed out"))
    assert result["services"]["airtable"] == "error:timed out"


def test_airtable_read_boundary_has_no_direct_http():
    source = inspect.getsource(tma_api._system_health_payload)
    ast.parse(source)
    assert "_read_list_records" in source
    assert "api.airtable.com" not in source
    assert "_at_url" not in source
    assert "_at_headers" not in source


if __name__ == "__main__":
    tests = [value for name, value in globals().items() if name.startswith("test_")]
    for test in tests:
        test()
    print(f"passed {len(tests)}")
