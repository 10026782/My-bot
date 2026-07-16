"""PR-RP2 tests for diagnostic-only tool availability metadata."""

from __future__ import annotations

import logging
import socket
import urllib.request

import pytest
import requests

import context
import tool_registry
from feature_flags import get_tool_availability_filter_state
from identity import Role
from tool_registry import ToolAvailability, ToolMeta, get_availability


def _install_meta(monkeypatch: pytest.MonkeyPatch, meta: ToolMeta) -> None:
    monkeypatch.setitem(tool_registry._REGISTRY, meta.name, meta)


def _schema_names(role: str) -> list[str]:
    return [schema["name"] for schema in context._filter_tools(role)]


def test_tools_without_checks_remain_available(monkeypatch: pytest.MonkeyPatch):
    _install_meta(monkeypatch, ToolMeta(name="legacy_tool", roles_allowed={Role.OWNER}))

    result = get_availability("legacy_tool", role=Role.OWNER)

    assert result == ToolAvailability(
        available=True,
        code="available_by_default",
        detail="No availability check is declared; legacy availability is preserved.",
    )


def test_unavailable_check_returns_stable_code_and_redacted_reason(
    monkeypatch: pytest.MonkeyPatch,
):
    secret = "SECRET_MARKER_RP2_123"
    monkeypatch.setenv("TEST_API_KEY", secret)
    _install_meta(
        monkeypatch,
        ToolMeta(
            name="unavailable_tool",
            roles_allowed={Role.OWNER},
            availability_check=lambda: ToolAvailability(
                False,
                "provider_config_missing",
                f"Provider is unavailable; key={secret}",
            ),
        ),
    )

    result = get_availability("unavailable_tool", role=Role.OWNER)

    assert result.available is False
    assert result.code == "provider_config_missing"
    assert "Provider is unavailable" in result.detail
    assert secret not in result.detail
    assert "[REDACTED]" in result.detail


def test_check_exception_fails_closed_without_logging_exception_secret(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
):
    secret = "SECRET_MARKER_EXCEPTION_RP2"

    def broken_check() -> ToolAvailability:
        raise RuntimeError(f"provider exploded with token={secret}")

    _install_meta(
        monkeypatch,
        ToolMeta(
            name="broken_tool",
            roles_allowed={Role.OWNER},
            availability_check=broken_check,
        ),
    )

    with caplog.at_level(logging.WARNING, logger="tool_registry"):
        result = get_availability("broken_tool", role=Role.OWNER)

    assert result == ToolAvailability(
        available=False,
        code="availability_check_error",
        detail="Availability check raised an exception; details were redacted.",
    )
    assert secret not in caplog.text
    assert secret not in result.detail


def test_role_denial_precedes_and_skips_availability_check(
    monkeypatch: pytest.MonkeyPatch,
):
    calls = 0

    def available_check() -> ToolAvailability:
        nonlocal calls
        calls += 1
        return ToolAvailability(True, "available", "ready")

    _install_meta(
        monkeypatch,
        ToolMeta(
            name="owner_only_tool",
            roles_allowed={Role.OWNER},
            availability_check=available_check,
        ),
    )

    result = get_availability("owner_only_tool", role=Role.LEAD)

    assert result.code == "role_denied"
    assert result.available is False
    assert calls == 0


def test_declared_availability_checks_never_call_network_or_providers(
    monkeypatch: pytest.MonkeyPatch,
):
    def forbidden(*args, **kwargs):
        raise AssertionError("availability checks must not call network/provider clients")

    monkeypatch.setattr(requests.sessions.Session, "request", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    for name in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REFRESH_TOKEN"):
        monkeypatch.setenv(name, "configured-test-value")
    monkeypatch.setenv("AIRTABLE_API_KEY", "configured-test-value")
    monkeypatch.setenv("AIRTABLE_BASE_ID", "configured-test-value")

    results = [
        get_availability(name)
        for name, meta in tool_registry._REGISTRY.items()
        if meta.availability_check is not None
    ]

    assert results
    assert all(result.available for result in results)


@pytest.mark.parametrize("state", ["shadow", "enforce"])
def test_shadow_and_requested_enforce_do_not_change_exposed_schema_list(
    monkeypatch: pytest.MonkeyPatch,
    state: str,
):
    monkeypatch.setattr(context, "get_tool_availability_filter_state", lambda: "off")
    off_names = _schema_names(Role.OWNER)

    monkeypatch.setattr(context, "get_tool_availability_filter_state", lambda: state)
    diagnostic_names = _schema_names(Role.OWNER)

    assert diagnostic_names == off_names


def test_shadow_diagnostics_log_unavailability_without_secret_values(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
):
    secret = "SECRET_MARKER_GOOGLE_RP2"
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", secret)
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_REFRESH_TOKEN", raising=False)
    monkeypatch.setattr(context, "get_tool_availability_filter_state", lambda: "shadow")

    with caplog.at_level(logging.INFO, logger="context"):
        shadow_names = _schema_names(Role.OWNER)

    assert shadow_names
    assert "available=false" in caplog.text
    assert "google_oauth_missing" in caplog.text
    assert secret not in caplog.text


def test_tool_availability_flag_defaults_off_and_accepts_three_states(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.delenv("FEATURE_TOOL_AVAILABILITY_FILTER", raising=False)
    assert get_tool_availability_filter_state() == "off"

    for state in ("off", "shadow", "enforce"):
        monkeypatch.setenv("FEATURE_TOOL_AVAILABILITY_FILTER", state)
        assert get_tool_availability_filter_state() == state

    monkeypatch.setenv("FEATURE_TOOL_AVAILABILITY_FILTER", "unexpected")
    assert get_tool_availability_filter_state() == "off"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
