"""BOSS Doctor Phase 1 — read-only diagnostic aggregator tests."""

from __future__ import annotations

import pytest

import boss_doctor
import tool_registry
from boss_doctor import DiagnosticCheck, DoctorReport, format_report, run_doctor
from tool_registry import ToolAvailability, ToolMeta


# ══════════════════════════════════════════════════
# 1. Read-only — no mutation of any kind
# ══════════════════════════════════════════════════

def test_run_doctor_never_calls_a_mutating_function(monkeypatch: pytest.MonkeyPatch):
    def _boom(*a, **k):
        raise AssertionError("boss_doctor must never call a mutating function")

    import feature_flags
    monkeypatch.setattr(feature_flags, "set_flag", _boom, raising=False)
    monkeypatch.setattr(feature_flags, "set_emergency_stop", _boom, raising=False)
    monkeypatch.setattr(feature_flags, "clear_emergency_stop", _boom, raising=False)

    import core.action_gateway as ag
    monkeypatch.setattr(ag.ActionGateway, "propose_action", _boom, raising=False)

    report = run_doctor()
    assert isinstance(report, DoctorReport)


def test_run_doctor_does_not_change_environment(monkeypatch: pytest.MonkeyPatch):
    import os
    before = dict(os.environ)
    run_doctor()
    assert dict(os.environ) == before


# ══════════════════════════════════════════════════
# 2. Tool availability is consumed from the existing ToolAvailability contract
# ══════════════════════════════════════════════════

def test_tools_check_uses_tool_registry_get_availability(monkeypatch: pytest.MonkeyPatch):
    calls = []
    original = tool_registry.get_availability

    def spy(name, **kw):
        calls.append(name)
        return original(name, **kw)

    monkeypatch.setattr(boss_doctor, "get_availability", spy)
    report = run_doctor()
    tools_check = next(c for c in report.checks if c.name == "tools")
    assert tools_check.source == "tool_registry.get_availability"
    assert len(calls) > 0


# ══════════════════════════════════════════════════
# 3. Missing configuration -> unavailable / not-configured, never guessed OK
# ══════════════════════════════════════════════════

def test_missing_airtable_env_reports_unavailable(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("AIRTABLE_API_KEY", raising=False)
    monkeypatch.delenv("AIRTABLE_BASE_ID", raising=False)
    report = run_doctor()
    check = next(c for c in report.checks if c.name == "airtable_configured")
    assert check.status == "UNAVAILABLE"
    assert check.code == "airtable_config_missing"


def test_missing_database_url_reports_unavailable(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    report = run_doctor()
    check = next(c for c in report.checks if c.name == "postgres_configured")
    assert check.status == "UNAVAILABLE"
    assert check.code == "database_url_missing"


def test_present_database_url_reports_ok(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@host/db")
    report = run_doctor()
    check = next(c for c in report.checks if c.name == "postgres_configured")
    assert check.status == "OK"


# ══════════════════════════════════════════════════
# 4. Unknown signal stays UNKNOWN — never guessed
# ══════════════════════════════════════════════════

def test_scheduler_with_no_registered_jobs_is_unknown_not_unavailable(monkeypatch: pytest.MonkeyPatch):
    import schedule
    monkeypatch.setattr(schedule, "jobs", [], raising=False)
    report = run_doctor()
    check = next(c for c in report.checks if c.name == "scheduler")
    assert check.status == "UNKNOWN"
    assert check.code == "no_jobs_observed"


def test_approval_legacy_path_is_always_unknown():
    report = run_doctor()
    check = next(c for c in report.checks if c.name == "approval_legacy_path")
    assert check.status == "UNKNOWN"
    assert check.code == "not_checked"


# ══════════════════════════════════════════════════
# 5. A raising check never takes down the whole report
# ══════════════════════════════════════════════════

def test_tools_check_exception_is_isolated(monkeypatch: pytest.MonkeyPatch):
    def _boom():
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(boss_doctor, "_check_tools", _boom)
    report = run_doctor()  # must not raise
    check = next(c for c in report.checks if c.name == "tools")
    assert check.status == "UNKNOWN"
    assert check.code == "check_error"
    # every other check still ran
    assert len(report.checks) > 1


# ══════════════════════════════════════════════════
# 6. No secret leakage — from a raised exception or from a check's own detail
# ══════════════════════════════════════════════════

def test_availability_check_exception_does_not_leak_secret(monkeypatch: pytest.MonkeyPatch):
    secret = "SECRET_MARKER_DOCTOR_1"

    def exploding_check():
        raise RuntimeError(f"provider blew up with key={secret}")

    monkeypatch.setitem(
        tool_registry._REGISTRY,
        "airtable_get",
        ToolMeta(
            name="airtable_get",
            roles_allowed=tool_registry._REGISTRY["airtable_get"].roles_allowed,
            tenant_scoped=True,
            availability_check=exploding_check,
        ),
    )
    report = run_doctor()
    check = next(c for c in report.checks if c.name == "airtable_configured")
    assert secret not in check.detail
    for c in report.checks:
        assert secret not in c.detail


def test_env_secret_value_is_redacted_from_detail(monkeypatch: pytest.MonkeyPatch):
    secret = "SECRET_MARKER_DOCTOR_2"
    monkeypatch.setenv("AIRTABLE_API_KEY", secret)
    monkeypatch.setenv("AIRTABLE_BASE_ID", "base123")
    monkeypatch.setitem(
        tool_registry._REGISTRY,
        "airtable_get",
        ToolMeta(
            name="airtable_get",
            roles_allowed=tool_registry._REGISTRY["airtable_get"].roles_allowed,
            tenant_scoped=True,
            availability_check=lambda: ToolAvailability(
                False, "provider_error", f"failed with key={secret}"
            ),
        ),
    )
    report = run_doctor()
    for c in report.checks:
        assert secret not in c.detail


# ══════════════════════════════════════════════════
# 7. Owner/role restriction — N/A in Phase 1 (no command wired yet; see report)
# ══════════════════════════════════════════════════

def test_run_doctor_takes_no_identity_argument_no_command_surface_yet():
    import inspect
    sig = inspect.signature(run_doctor)
    assert list(sig.parameters) == []


# ══════════════════════════════════════════════════
# 8 & 9. Doctor never bypasses ActionGateway and never creates an ActionContract
# ══════════════════════════════════════════════════

def test_run_doctor_never_touches_action_gateway(monkeypatch: pytest.MonkeyPatch):
    import core.action_gateway as ag

    def _boom(*a, **k):
        raise AssertionError("boss_doctor must never construct an ActionContract")

    monkeypatch.setattr(ag, "ActionContract", _boom, raising=False)
    report = run_doctor()
    assert isinstance(report, DoctorReport)


# ══════════════════════════════════════════════════
# 10. Doctor never changes a feature flag
# ══════════════════════════════════════════════════

def test_run_doctor_flag_values_unchanged_before_and_after(monkeypatch: pytest.MonkeyPatch):
    from feature_flags import is_enabled
    before = {name: is_enabled(name) for name in boss_doctor._EMERGENCY_STOP_FLAGS}
    run_doctor()
    after = {name: is_enabled(name) for name in boss_doctor._EMERGENCY_STOP_FLAGS}
    assert before == after


# ══════════════════════════════════════════════════
# 11. Doctor performs no external business action (no dispatcher call)
# ══════════════════════════════════════════════════

def test_run_doctor_never_calls_dispatcher(monkeypatch: pytest.MonkeyPatch):
    import tools.dispatcher as dispatcher

    def _boom(*a, **k):
        raise AssertionError("boss_doctor must never call dispatch_tool")

    monkeypatch.setattr(dispatcher, "dispatch_tool", _boom, raising=False)
    report = run_doctor()
    assert isinstance(report, DoctorReport)


# ══════════════════════════════════════════════════
# Contract / formatting sanity
# ══════════════════════════════════════════════════

def test_diagnostic_check_rejects_invalid_status():
    with pytest.raises(ValueError):
        DiagnosticCheck(name="x", status="HEALTHY", code="x", detail="x", source="x")


def test_format_report_has_no_secret_env_dump(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "SECRET_MARKER_DOCTOR_3")
    report = run_doctor()
    text = format_report(report)
    assert "SECRET_MARKER_DOCTOR_3" not in text
    assert "BOSS Doctor" in text
    assert "Production verification: not checked" in text


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-q"]))
