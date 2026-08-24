from __future__ import annotations

from unittest.mock import patch

import health_monitor
from tools.airtable_gateway import AirtableLookupError


def test_success_and_timeout(monkeypatch):
    monkeypatch.setenv("AIRTABLE_BASE_ID", "app-base")
    monkeypatch.setenv("AIRTABLE_API_KEY", "key")
    with patch("tools.airtable_gateway.get_base_metadata", return_value={}) as fetch:
        assert health_monitor._check_airtable() == (True, "ok")
    fetch.assert_called_once_with(timeout=3)


def test_missing_credentials(monkeypatch):
    monkeypatch.delenv("AIRTABLE_BASE_ID", raising=False)
    monkeypatch.delenv("AIRTABLE_API_KEY", raising=False)
    assert health_monitor._check_airtable() == (False, "missing credentials")


def test_http_errors_preserve_status(monkeypatch):
    monkeypatch.setenv("AIRTABLE_BASE_ID", "app-base")
    monkeypatch.setenv("AIRTABLE_API_KEY", "key")
    for status in (401, 403, 500):
        error = AirtableLookupError("metadata failed", status_code=status)
        with patch("tools.airtable_gateway.get_base_metadata", side_effect=error):
            assert health_monitor._check_airtable() == (False, f"HTTP {status}")


def test_transport_error_preserves_underlying_type(monkeypatch):
    monkeypatch.setenv("AIRTABLE_BASE_ID", "app-base")
    monkeypatch.setenv("AIRTABLE_API_KEY", "key")
    cause = TimeoutError("timed out")
    error = AirtableLookupError("metadata failed", cause=cause)
    with patch("tools.airtable_gateway.get_base_metadata", side_effect=error):
        assert health_monitor._check_airtable() == (False, "error: TimeoutError")


def test_unexpected_error_never_escapes(monkeypatch):
    monkeypatch.setenv("AIRTABLE_BASE_ID", "app-base")
    monkeypatch.setenv("AIRTABLE_API_KEY", "key")
    with patch("tools.airtable_gateway.get_base_metadata", side_effect=ValueError("bad")):
        assert health_monitor._check_airtable() == (False, "error: ValueError")


def test_health_aggregation_uses_check_result(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setenv("TELEGRAM_TOKEN", "x")
    with patch.object(health_monitor, "_check_airtable", return_value=(False, "HTTP 500")), \
         patch.object(health_monitor, "_check_scheduler", return_value=(True, "1 jobs")), \
         patch.object(health_monitor, "_check_emergency", return_value=(True, "clear")), \
         patch.object(health_monitor, "_check_emergency_stop_manager", return_value=(True, "durable, 5 flags")):
        result = health_monitor.get_health_status()
    assert result["checks"]["airtable_live"] is False
    assert result["checks"]["airtable_detail"] == "HTTP 500"
    assert result["status"] == "degraded"
