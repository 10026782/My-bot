# boss_doctor.py — BOSS Doctor, Phase 1 (read-only diagnostic aggregator)
#
# Aggregates EXISTING readiness/authorization signals (ToolAvailability,
# feature flags, health_monitor, atomic_claims_health) into one redacted,
# read-only report. It computes nothing new about provider health — it only
# calls what already exists and relabels the result.
#
# Hard invariants:
#   - Never mutates anything (no Airtable/Postgres write, no flag change,
#     no approval/ActionContract creation, no scheduler/job change).
#   - Never bypasses tool_registry.enforce() / ActionGateway authority.
#   - "configured" != "runtime-observed" != "production-verified" — see
#     docs/research/HERMES_DEFERRED_PATTERNS_REVISIT_2026-08.md §"boss doctor".
#   - Unknown/unreliable signal -> UNKNOWN, never guessed.

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

from tool_registry import _redact_operator_detail, get_availability
from tools.schemas import TOOL_SCHEMAS

logger = logging.getLogger(__name__)

_STATUSES = frozenset({"OK", "DEGRADED", "UNAVAILABLE", "UNKNOWN"})

_EMERGENCY_STOP_FLAGS = (
    "EMERGENCY_STOP_ALL",
    "EMERGENCY_STOP_WHATSAPP",
    "EMERGENCY_STOP_EMAIL",
    "EMERGENCY_STOP_AUTOMATION",
    "EMERGENCY_STOP_AI",
)


@dataclass(frozen=True)
class DiagnosticCheck:
    """One redacted, side-effect-free diagnostic result."""

    name:   str
    status: str
    code:   str
    detail: str
    source: str

    def __post_init__(self) -> None:
        if self.status not in _STATUSES:
            raise ValueError(f"invalid DiagnosticCheck status: {self.status!r}")


@dataclass(frozen=True)
class DoctorReport:
    checks: tuple[DiagnosticCheck, ...]

    def by_status(self, status: str) -> tuple[DiagnosticCheck, ...]:
        return tuple(c for c in self.checks if c.status == status)


def _safe(name: str, source: str, fn) -> DiagnosticCheck:
    """Run one check; an exception never takes down the whole report."""
    try:
        return fn()
    except Exception:
        logger.warning("[BossDoctor] check=%s failed", name)
        return DiagnosticCheck(
            name=name,
            status="UNKNOWN",
            code="check_error",
            detail="Diagnostic check raised an exception; details were redacted.",
            source=source,
        )


# ══════════════════════════════════════════════════
# A. Tool readiness — reuses tool_registry.get_availability(), no new logic
# ══════════════════════════════════════════════════

def _check_tools() -> DiagnosticCheck:
    names = [s["name"] for s in TOOL_SCHEMAS]
    ready = 0
    for name in names:
        # role=None: pure registration + provider-config readiness, independent
        # of any one caller's role — matches this check's job (fleet summary,
        # not "what can this user do").
        if get_availability(name, role=None).available:
            ready += 1
    total = len(names)
    unavailable = total - ready
    if total == 0:
        status = "UNKNOWN"
    elif ready == 0:
        status = "UNAVAILABLE"
    elif unavailable == 0:
        status = "OK"
    else:
        status = "DEGRADED"
    return DiagnosticCheck(
        name="tools",
        status=status,
        code="tools_summary",
        detail=f"{ready} ready / {unavailable} unavailable (of {total} model-exposed tools)",
        source="tool_registry.get_availability",
    )


# ══════════════════════════════════════════════════
# B. Safety-critical feature flags — reuses feature_flags accessors
# ══════════════════════════════════════════════════

def _check_emergency_stop(flag_name: str) -> DiagnosticCheck:
    from feature_flags import is_enabled
    active = is_enabled(flag_name)
    return DiagnosticCheck(
        name=flag_name.lower(),
        status="DEGRADED" if active else "OK",
        code="stop_active" if active else "clear",
        detail=f"{flag_name} is {'ACTIVE (blocking)' if active else 'clear'}",
        source="feature_flags.is_enabled",
    )


def _check_tool_availability_filter_state() -> DiagnosticCheck:
    from feature_flags import get_tool_availability_filter_state
    state = get_tool_availability_filter_state()
    return DiagnosticCheck(
        name="feature_tool_availability_filter",
        status="OK",
        code=f"state_{state}",
        detail=f"FEATURE_TOOL_AVAILABILITY_FILTER={state}",
        source="feature_flags.get_tool_availability_filter_state",
    )


# ══════════════════════════════════════════════════
# C. Airtable — configured (env presence) vs runtime-observed (live health probe)
# ══════════════════════════════════════════════════

def _check_airtable_configured() -> DiagnosticCheck:
    result = get_availability("airtable_get", role=None)
    return DiagnosticCheck(
        name="airtable_configured",
        status="OK" if result.available else "UNAVAILABLE",
        code=result.code,
        detail=_redact_operator_detail(result.detail),
        source="tool_registry.get_availability",
    )


def _check_airtable_runtime_observed() -> DiagnosticCheck:
    import health_monitor
    checks = health_monitor.get_health_status()["checks"]
    ok = bool(checks.get("airtable_live"))
    return DiagnosticCheck(
        name="airtable_runtime_observed",
        status="OK" if ok else "UNAVAILABLE",
        code="live_read_ok" if ok else "live_read_failed",
        detail=_redact_operator_detail(checks.get("airtable_detail", "")),
        source="health_monitor.get_health_status",
    )


# ══════════════════════════════════════════════════
# D. Postgres — configured (env presence, no connection) + atomic-claims readiness
# ══════════════════════════════════════════════════

def _check_postgres_configured() -> DiagnosticCheck:
    configured = bool(os.environ.get("DATABASE_URL", "").strip())
    return DiagnosticCheck(
        name="postgres_configured",
        status="OK" if configured else "UNAVAILABLE",
        code="configured" if configured else "database_url_missing",
        detail="DATABASE_URL is present." if configured else "DATABASE_URL is not set.",
        source="os.environ",
    )


def _check_atomic_claims() -> DiagnosticCheck:
    from core.atomic_claims_health import check_health
    health = check_health()
    if not health.enabled:
        status, code = "OK", "disabled"
    elif health.is_ready():
        status, code = "OK", "ready"
    else:
        status, code = "UNAVAILABLE", "not_ready"
    return DiagnosticCheck(
        name="atomic_claims",
        status=status,
        code=code,
        detail=_redact_operator_detail(health.summary()),
        source="core.atomic_claims_health.check_health",
    )


# ══════════════════════════════════════════════════
# E. Scheduler — registered job count from the live `schedule` process state
# ══════════════════════════════════════════════════

def _check_scheduler() -> DiagnosticCheck:
    import schedule
    count = len(schedule.jobs)
    return DiagnosticCheck(
        name="scheduler",
        status="OK" if count > 0 else "UNKNOWN",
        code="jobs_registered" if count > 0 else "no_jobs_observed",
        detail=(
            f"{count} jobs registered in this process."
            if count > 0
            else "No jobs registered in this process — scheduler.start_scheduler() "
                 "may not have run here (e.g. run outside the live server process); "
                 "this does not prove the scheduler is down."
        ),
        source="schedule.jobs",
    )


# ══════════════════════════════════════════════════
# F. Providers — Google OAuth configuration (Airtable is reported under C)
# ══════════════════════════════════════════════════

def _check_google_oauth_configured() -> DiagnosticCheck:
    result = get_availability("search_drive", role=None)
    return DiagnosticCheck(
        name="google_oauth_configured",
        status="OK" if result.available else "UNAVAILABLE",
        code=result.code,
        detail=_redact_operator_detail(result.detail),
        source="tool_registry.get_availability",
    )


# ══════════════════════════════════════════════════
# G. Approval / ActionGateway — flag state only; no legacy-store probe exists
# ══════════════════════════════════════════════════

def _check_flag_state(flag_name: str, check_name: str) -> DiagnosticCheck:
    from feature_flags import is_enabled
    value = is_enabled(flag_name)
    return DiagnosticCheck(
        name=check_name,
        status="OK",
        code="on" if value else "off",
        detail=f"{flag_name}={'on' if value else 'off'}",
        source="feature_flags.is_enabled",
    )


def _check_approval_legacy_path() -> DiagnosticCheck:
    return DiagnosticCheck(
        name="approval_legacy_path",
        status="UNKNOWN",
        code="not_checked",
        detail=(
            "No reliable read-only readiness signal exists for the legacy "
            "Airtable Approvals path in this Phase 1 slice; not guessed."
        ),
        source="boss_doctor",
    )


# ══════════════════════════════════════════════════
# Aggregator
# ══════════════════════════════════════════════════

def run_doctor() -> DoctorReport:
    """Run every Phase 1 check. Read-only: performs no writes anywhere."""
    checks: list[DiagnosticCheck] = [
        _safe("tools", "tool_registry", _check_tools),
    ]
    for flag_name in _EMERGENCY_STOP_FLAGS:
        checks.append(
            _safe(flag_name.lower(), "feature_flags", lambda f=flag_name: _check_emergency_stop(f))
        )
    checks.append(_safe("feature_tool_availability_filter", "feature_flags", _check_tool_availability_filter_state))
    checks.append(_safe("airtable_configured", "tool_registry", _check_airtable_configured))
    checks.append(_safe("airtable_runtime_observed", "health_monitor", _check_airtable_runtime_observed))
    checks.append(_safe("postgres_configured", "os.environ", _check_postgres_configured))
    checks.append(_safe("atomic_claims", "core.atomic_claims_health", _check_atomic_claims))
    checks.append(_safe("scheduler", "schedule", _check_scheduler))
    checks.append(_safe("google_oauth_configured", "tool_registry", _check_google_oauth_configured))
    checks.append(_safe("action_gateway_flag", "feature_flags",
                         lambda: _check_flag_state("FEATURE_ACTION_GATEWAY", "action_gateway_flag")))
    checks.append(_safe("action_contract_persistence_flag", "feature_flags",
                         lambda: _check_flag_state("FEATURE_ACTION_CONTRACT_PERSISTENCE", "action_contract_persistence_flag")))
    checks.append(_safe("approval_legacy_path", "boss_doctor", _check_approval_legacy_path))
    return DoctorReport(checks=tuple(checks))


def format_report(report: DoctorReport) -> str:
    """Short operator-facing summary. No env/secret dump."""
    by_name = {c.name: c for c in report.checks}
    tools = by_name["tools"]
    airtable_cfg = by_name["airtable_configured"]
    postgres = by_name["postgres_configured"]
    atomic = by_name["atomic_claims"]
    scheduler = by_name["scheduler"]
    google = by_name["google_oauth_configured"]

    stopped = [c.name for c in report.checks if c.name.startswith("emergency_stop_") and c.status == "DEGRADED"]

    lines = ["BOSS Doctor", ""]
    lines.append(f"Tools: {tools.detail}")
    lines.append(f"Airtable: {'configured' if airtable_cfg.status == 'OK' else 'not configured'}")
    lines.append(f"Postgres: {'configured' if postgres.status == 'OK' else 'not configured'}"
                 f" | atomic claims: {atomic.code}")
    lines.append(f"Scheduler: {scheduler.detail}")
    lines.append(f"Google OAuth: {'configured' if google.status == 'OK' else 'not configured'}")
    lines.append(f"Emergency stops active: {', '.join(stopped) if stopped else 'none'}")
    lines.append("Approvals: flag state known; legacy path readiness not checked")
    lines.append("")
    lines.append("Production verification: not checked")
    return "\n".join(lines)
