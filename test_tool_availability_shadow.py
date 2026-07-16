"""PR-RP2/RP3 tests for tool availability diagnostics and schema enforcement."""

from __future__ import annotations

import logging
import socket
import urllib.request
from dataclasses import replace

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


def test_context_availability_checks_never_call_network_or_providers(
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

    monkeypatch.setattr(context, "get_tool_availability_filter_state", lambda: "enforce")
    assert _schema_names(Role.OWNER)


def test_off_mode_returns_current_schema_list_without_evaluating_availability(
    monkeypatch: pytest.MonkeyPatch,
):
    expected = [
        schema["name"]
        for schema in context.TOOL_SCHEMAS
        if schema["name"] in context._ROLE_TOOLS[Role.OWNER]
    ]
    monkeypatch.setattr(context, "get_tool_availability_filter_state", lambda: "off")
    monkeypatch.setattr(
        context,
        "get_availability",
        lambda *args, **kwargs: pytest.fail("off mode evaluated availability"),
    )

    assert _schema_names(Role.OWNER) == expected


def test_shadow_mode_returns_identical_schema_list(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(context, "get_tool_availability_filter_state", lambda: "off")
    off_names = _schema_names(Role.OWNER)

    monkeypatch.setattr(context, "get_tool_availability_filter_state", lambda: "shadow")
    shadow_names = _schema_names(Role.OWNER)

    assert shadow_names == off_names


def test_enforce_hides_unavailable_and_keeps_available_role_allowed_tools(
    monkeypatch: pytest.MonkeyPatch,
):
    for name in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REFRESH_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AIRTABLE_API_KEY", "configured-test-key")
    monkeypatch.setenv("AIRTABLE_BASE_ID", "configured-test-base")
    monkeypatch.setattr(context, "get_tool_availability_filter_state", lambda: "enforce")

    names = _schema_names(Role.OWNER)

    assert "search_drive" not in names
    assert "gmail_read" not in names
    assert "airtable_get" in names
    assert "airtable_get_schema" in names


@pytest.mark.parametrize("state", ["off", "shadow", "enforce"])
def test_role_denied_tools_stay_hidden_in_all_modes_and_availability_cannot_grant(
    monkeypatch: pytest.MonkeyPatch,
    state: str,
):
    monkeypatch.setattr(context, "get_tool_availability_filter_state", lambda: state)
    monkeypatch.setattr(
        context,
        "get_availability",
        lambda *args, **kwargs: ToolAvailability(True, "available", "ready"),
    )

    names = _schema_names(Role.LEAD)

    assert names == ["airtable_get"]
    assert "gmail_read" not in names
    assert "search_drive" not in names


def test_direct_or_stale_calls_remain_rejected_by_registry_policy():
    from tools.dispatcher import dispatch_tool

    class LeadIdentity:
        role = Role.LEAD
        tenant_id = "test-tenant"
        user_id = "test-lead"

    class OwnerIdentity:
        role = Role.OWNER
        tenant_id = "test-tenant"
        user_id = "test-owner"

    with pytest.raises(tool_registry.ToolDenied):
        tool_registry.enforce("gmail_read", LeadIdentity())
    with pytest.raises(tool_registry.ToolDenied):
        tool_registry.enforce("stale_removed_tool", OwnerIdentity())

    denied = dispatch_tool("gmail_read", {}, LeadIdentity())
    stale = dispatch_tool("stale_removed_tool", {}, OwnerIdentity())
    assert denied.startswith("❌ גישה נחסמה:")
    assert stale.startswith("❌ גישה נחסמה:")


def test_availability_exception_fails_closed_for_enforce_schema_exposure(
    monkeypatch: pytest.MonkeyPatch,
):
    def broken_check() -> ToolAvailability:
        raise RuntimeError("provider readiness failed")

    search_drive = tool_registry.get("search_drive")
    assert search_drive is not None
    monkeypatch.setitem(
        tool_registry._REGISTRY,
        "search_drive",
        replace(search_drive, availability_check=broken_check),
    )
    monkeypatch.setattr(context, "get_tool_availability_filter_state", lambda: "enforce")

    assert "search_drive" not in _schema_names(Role.OWNER)


@pytest.mark.parametrize("state", ["shadow", "enforce"])
def test_diagnostics_log_unavailability_without_secret_values(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    state: str,
):
    secret = "SECRET_MARKER_GOOGLE_RP2"
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", secret)
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_REFRESH_TOKEN", raising=False)
    monkeypatch.setenv("AIRTABLE_API_KEY", "configured-test-key")
    monkeypatch.setenv("AIRTABLE_BASE_ID", "configured-test-base")
    monkeypatch.setattr(context, "get_tool_availability_filter_state", lambda: state)

    with caplog.at_level(logging.INFO, logger="context"):
        names = _schema_names(Role.OWNER)

    assert "available=false" in caplog.text
    assert "google_oauth_missing" in caplog.text
    assert secret not in caplog.text
    assert ("search_drive" in names) is (state == "shadow")


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
