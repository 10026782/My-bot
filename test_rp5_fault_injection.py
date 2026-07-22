# test_rp5_fault_injection.py — RP5 staging-only fault-injection regression suite.
#
# Proves core/rp5_fault_injection.py is fully inert unless ALL FOUR hard
# safety gates hold (staging env, RP5_FAULT_INJECTION_ENABLED=true, allowlisted
# canonical_user_id, explicit [rp5-test:<scenario>] marker), and that once
# active it produces EvidenceFinalizerShadow-compatible failed evidence
# through the REAL tools.dispatcher.dispatch_tool() entry point — no
# TurnCoordinator, no RP5/F52 enforcement flip, no real Google/Airtable
# credentials required.

from __future__ import annotations

import pytest

from core import rp5_fault_injection as rp5
from core.anti_hallucination import verify_execution
from core.turn_evidence import TurnEvidenceSummary
from identity import Identity
from tools.dispatcher import dispatch_tool

import emergency_stop_test_support  # noqa: E402
# PATCH 3B Step 6 (post-dates this file): is_enabled() for EMERGENCY_STOP_*
# fails closed to blocked=True when no EmergencyStopManager is configured —
# this suite predates that cutover and doesn't test emergency-stop behavior,
# so it needs the same "all clear" fixture used by other pre-existing tests.
emergency_stop_test_support.configure_all_clear_emergency_stop()


_OWNER = Identity(
    user_id="eliyahu", role="owner", tenant_id="boss_hq",
    external_id="1", channel="telegram",
)
_CANONICAL = _OWNER.memory_key  # "boss_hq:eliyahu" — matches the task's example allowlist entry
_MARKED_TEXT = "בדוק את המייל [rp5-test:google-401] בבקשה"


@pytest.fixture(autouse=True)
def _reset_env(monkeypatch):
    """Every test starts from a clean slate: no RP5_FAULT_*/APP_ENV leakage
    between tests, and no leftover per-turn fault state."""
    for var in (
        "APP_ENV", "RP5_FAULT_INJECTION_ENABLED", "RP5_FAULT_ALLOWLIST",
        "RP5_FAULT_REQUIRE_MARKER", "RP5_FAULT_MARKER_PREFIX",
    ):
        monkeypatch.delenv(var, raising=False)
    rp5.end_turn()
    yield
    rp5.end_turn()


def _enable_staging(monkeypatch, *, allowlist: str = _CANONICAL) -> None:
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("RP5_FAULT_INJECTION_ENABLED", "true")
    monkeypatch.setenv("RP5_FAULT_ALLOWLIST", allowlist)


# ══════════════════════════════════════════════════
# get_fault_marker()
# ══════════════════════════════════════════════════

def test_marker_extracted_from_free_text():
    assert rp5.get_fault_marker("תוסיף ליד חדש [rp5-test:write-403] תודה") == "write-403"


def test_marker_absent_returns_none():
    assert rp5.get_fault_marker("תוסיף ליד חדש בבקשה") is None


def test_unrecognized_scenario_name_returns_none():
    assert rp5.get_fault_marker("[rp5-test:not-a-real-scenario]") is None


def test_unterminated_marker_returns_none():
    assert rp5.get_fault_marker("[rp5-test:write-403") is None


def test_empty_text_returns_none():
    assert rp5.get_fault_marker("") is None


def test_custom_marker_prefix_is_honored(monkeypatch):
    monkeypatch.setenv("RP5_FAULT_MARKER_PREFIX", "<<fault:")
    assert rp5.get_fault_marker("hi <<fault:connection-reset] bye") == "connection-reset"
    # default prefix no longer matches once a custom prefix is configured
    assert rp5.get_fault_marker("[rp5-test:connection-reset]") is None


def test_all_seven_supported_markers_recognized():
    for scenario in (
        "google-401", "write-403", "write-validation-400", "write-timeout",
        "tool-empty-response", "tool-malformed-response", "connection-reset",
    ):
        assert rp5.get_fault_marker(f"x [rp5-test:{scenario}] y") == scenario


# ══════════════════════════════════════════════════
# is_staging()
# ══════════════════════════════════════════════════

def test_is_staging_default_is_production_false(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    assert rp5.is_staging() is False


def test_is_staging_true_only_for_literal_staging():
    assert rp5.is_staging("staging") is True
    assert rp5.is_staging("Staging") is True
    assert rp5.is_staging("production") is False
    assert rp5.is_staging("dev") is False
    assert rp5.is_staging("") is False


# ══════════════════════════════════════════════════
# Hard safety gates — the 5 required acceptance scenarios
# ══════════════════════════════════════════════════

def test_gate_1_production_env_marker_ignored(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("RP5_FAULT_INJECTION_ENABLED", "true")
    monkeypatch.setenv("RP5_FAULT_ALLOWLIST", _CANONICAL)
    assert rp5.is_enabled_for_turn("production", _CANONICAL, _MARKED_TEXT) is False


def test_gate_2_staging_but_disabled_marker_ignored(monkeypatch):
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("RP5_FAULT_INJECTION_ENABLED", "false")
    monkeypatch.setenv("RP5_FAULT_ALLOWLIST", _CANONICAL)
    assert rp5.is_enabled_for_turn("staging", _CANONICAL, _MARKED_TEXT) is False


def test_gate_3_staging_enabled_user_not_allowlisted(monkeypatch):
    _enable_staging(monkeypatch, allowlist="boss_hq:someone_else")
    assert rp5.is_enabled_for_turn("staging", _CANONICAL, _MARKED_TEXT) is False


def test_gate_4_staging_enabled_allowlisted_no_marker(monkeypatch):
    _enable_staging(monkeypatch)
    assert rp5.is_enabled_for_turn("staging", _CANONICAL, "בדוק את המייל בבקשה") is False


def test_gate_5_staging_enabled_allowlisted_marker_activates(monkeypatch):
    _enable_staging(monkeypatch)
    assert rp5.is_enabled_for_turn("staging", _CANONICAL, _MARKED_TEXT) is True


def test_require_marker_false_still_needs_a_marker_to_pick_a_scenario(monkeypatch):
    """RP5_FAULT_REQUIRE_MARKER=false must never become a way to activate a
    fault WITHOUT a marker — there is nothing to select without one. This
    flag can only ever be as permissive as gate 4, never more."""
    _enable_staging(monkeypatch)
    monkeypatch.setenv("RP5_FAULT_REQUIRE_MARKER", "false")
    assert rp5.is_enabled_for_turn("staging", _CANONICAL, "בדוק את המייל בבקשה") is False
    assert rp5.is_enabled_for_turn("staging", _CANONICAL, _MARKED_TEXT) is True


def test_missing_canonical_user_id_never_activates(monkeypatch):
    _enable_staging(monkeypatch)
    assert rp5.is_enabled_for_turn("staging", "", _MARKED_TEXT) is False


# ══════════════════════════════════════════════════
# begin_turn() / end_turn() / maybe_raise_or_return_fault() plumbing
# ══════════════════════════════════════════════════

def test_begin_turn_inert_when_gates_fail(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    rp5.begin_turn(_CANONICAL, _MARKED_TEXT)
    assert rp5.maybe_raise_or_return_fault("gmail_read", read_only=True) is None


def test_begin_turn_activates_when_all_gates_pass(monkeypatch):
    _enable_staging(monkeypatch)
    rp5.begin_turn(_CANONICAL, _MARKED_TEXT)
    result = rp5.maybe_raise_or_return_fault("gmail_read", read_only=True)
    assert result is not None
    assert result["ok"] is False


def test_end_turn_clears_active_fault(monkeypatch):
    _enable_staging(monkeypatch)
    rp5.begin_turn(_CANONICAL, _MARKED_TEXT)
    assert rp5.maybe_raise_or_return_fault("gmail_read", read_only=True) is not None
    rp5.end_turn()
    assert rp5.maybe_raise_or_return_fault("gmail_read", read_only=True) is None


def test_scenario_scoped_to_applicable_tools_only(monkeypatch):
    """google-401 must not fire for a non-Google tool (e.g. airtable_get)."""
    _enable_staging(monkeypatch)
    rp5.begin_turn(_CANONICAL, _MARKED_TEXT)  # google-401
    assert rp5.maybe_raise_or_return_fault("airtable_get", read_only=True) is None
    assert rp5.maybe_raise_or_return_fault("gmail_read", read_only=True) is not None
    assert rp5.maybe_raise_or_return_fault("calendar_get_events", read_only=True) is not None


def test_write_only_scenarios_do_not_fire_on_reads(monkeypatch):
    _enable_staging(monkeypatch)
    rp5.begin_turn(_CANONICAL, "עדכן [rp5-test:write-403] רשומה")
    assert rp5.maybe_raise_or_return_fault("airtable_get", read_only=True) is None
    assert rp5.maybe_raise_or_return_fault("airtable_add", read_only=False) is not None


def test_tool_empty_response_returns_empty_string(monkeypatch):
    _enable_staging(monkeypatch)
    rp5.begin_turn(_CANONICAL, "בדוק [rp5-test:tool-empty-response] סטטוס")
    assert rp5.maybe_raise_or_return_fault("airtable_get", read_only=True) == ""


def test_tool_malformed_response_has_no_ok_key(monkeypatch):
    _enable_staging(monkeypatch)
    rp5.begin_turn(_CANONICAL, "בדוק [rp5-test:tool-malformed-response] סטטוס")
    result = rp5.maybe_raise_or_return_fault("airtable_add", read_only=False)
    assert isinstance(result, dict)
    assert "ok" not in result


@pytest.mark.parametrize("scenario", ["write-timeout", "connection-reset"])
def test_transport_scenarios_raise(monkeypatch, scenario):
    _enable_staging(monkeypatch)
    rp5.begin_turn(_CANONICAL, f"עדכן [rp5-test:{scenario}] רשומה")
    with pytest.raises(rp5.RP5InjectedTransportError):
        rp5.maybe_raise_or_return_fault("airtable_add", read_only=False)


def test_structured_log_line_emitted_on_activation(monkeypatch, caplog):
    _enable_staging(monkeypatch)
    rp5.begin_turn(_CANONICAL, _MARKED_TEXT)
    with caplog.at_level("WARNING", logger="core.rp5_fault_injection"):
        rp5.maybe_raise_or_return_fault("gmail_read", read_only=True)
    assert "[RP5FaultInjection]" in caplog.text
    assert "scenario=google-401" in caplog.text
    assert f"user={_CANONICAL}" in caplog.text
    assert "provider=google" in caplog.text
    assert "op=read" in caplog.text
    assert "tool=gmail_read" in caplog.text


# ══════════════════════════════════════════════════
# Integration: real tools.dispatcher.dispatch_tool() entry point
#
# No real Google/Airtable credentials anywhere below — when a fault is
# active it short-circuits BEFORE the real tool implementation would ever
# run, and when inactive the underlying provider call is mocked out.
# ══════════════════════════════════════════════════

def test_dispatcher_inert_in_production_even_with_marker(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("RP5_FAULT_INJECTION_ENABLED", "true")
    monkeypatch.setenv("RP5_FAULT_ALLOWLIST", _CANONICAL)
    rp5.begin_turn(_CANONICAL, _MARKED_TEXT)

    from unittest.mock import patch
    with patch("tools.dispatcher.gmail_read", return_value="📬 3 מיילים חדשים"):
        result = dispatch_tool("gmail_read", {}, _OWNER)
    assert result == "📬 3 מיילים חדשים"


def test_dispatcher_read_failure_produces_failed_evidence(monkeypatch):
    """Expected behavior #1: google-401 on a Gmail/Calendar read must not
    claim success, and must classify as a genuine A32 failure (not ok)."""
    _enable_staging(monkeypatch)
    rp5.begin_turn(_CANONICAL, _MARKED_TEXT)  # [rp5-test:google-401]

    result = dispatch_tool("gmail_read", {}, _OWNER)

    assert isinstance(result, dict)
    assert result["ok"] is False
    check = verify_execution("gmail_read", result)
    assert check.status == "failed"

    evidence = TurnEvidenceSummary()
    evidence.record_verification(check.status, read_only=True)
    assert evidence.classification() == "failure"
    assert evidence.failed_calls == 1
    assert evidence.verified_reads == 0


def test_dispatcher_write_failure_produces_failed_evidence(monkeypatch):
    """Expected behavior #2: write-403 on a write flow must not claim
    success, and must classify as a genuine A32 failure (outcome_unknown-
    compatible: never verified_write_success)."""
    _enable_staging(monkeypatch)
    rp5.begin_turn(_CANONICAL, "תוסיף איש קשר [rp5-test:write-403] בבקשה")

    result = dispatch_tool(
        "airtable_add", {"table": "Contacts", "fields": {"name": "Test"}}, _OWNER,
        trusted_source="agent",
    )

    assert isinstance(result, dict)
    assert result["ok"] is False
    assert result["reason_code"] == "PERMISSION_DENIED"
    check = verify_execution("airtable_add", result)
    assert check.status == "failed"

    evidence = TurnEvidenceSummary()
    evidence.record_verification(check.status, read_only=False)
    assert evidence.classification() == "failure"
    assert evidence.failed_calls == 1
    assert evidence.verified_writes == 0


def test_dispatcher_connection_reset_becomes_dispatcher_failure(monkeypatch):
    """connection-reset raises RP5InjectedTransportError; dispatch_tool's
    own generic `except Exception` (unchanged, pre-existing code) converts
    it into the same ❌-prefixed failed shape as any other tool crash —
    proves no new exception handling had to be added at the call site."""
    _enable_staging(monkeypatch)
    rp5.begin_turn(_CANONICAL, "תוסיף איש קשר [rp5-test:connection-reset] בבקשה")

    result = dispatch_tool(
        "airtable_add", {"table": "Contacts", "fields": {"name": "Test"}}, _OWNER,
        trusted_source="agent",
    )

    assert isinstance(result, str)
    assert result.startswith("❌")
    check = verify_execution("airtable_add", result)
    assert check.status == "failed"


def test_dispatcher_never_bypasses_role_enforcement(monkeypatch):
    """A fault must never fabricate access for a role the registry would
    have denied — the permission gate still runs first."""
    lead_identity = Identity(
        user_id="lead1", role="lead", tenant_id="boss_hq",
        external_id="lead1", channel="whatsapp",
    )
    _enable_staging(monkeypatch, allowlist=lead_identity.memory_key)
    rp5.begin_turn(lead_identity.memory_key, "[rp5-test:google-401]")

    result = dispatch_tool("gmail_read", {}, lead_identity)
    assert isinstance(result, str)
    assert result.startswith("❌ גישה נחסמה")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
