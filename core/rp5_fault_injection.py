# core/rp5_fault_injection.py — RP5 staging-only fault injection
#
# Narrow, centralized mechanism for producing REAL bot-driven RP5/F52 evidence
# samples in staging, through the full runtime chain (Router -> IngressClassifier
# -> Lead handler -> ActionGateway -> A32 -> EvidenceFinalizer -> rendering)
# without touching production behavior and without building any new
# coordination layer (no TurnCoordinator, no broad architecture change).
#
# RP5 (EvidenceFinalizer) and F52 (UnifiedStatusFormatter) remain shadow-only —
# this module never flips FEATURE_EVIDENCE_FINALIZER/FEATURE_UNIFIED_STATUS_FORMATTER
# and never changes their taxonomy/logic. It only lets a staging tester provoke
# controlled tool failures so those shadow layers have real production-shaped
# evidence to observe.
#
# Hard safety gates — fault injection activates ONLY when ALL of these hold:
#   1. runtime environment is staging, not production (APP_ENV)
#   2. RP5_FAULT_INJECTION_ENABLED=true
#   3. the canonical user (tenant_id:user_id — Identity.memory_key) is in
#      RP5_FAULT_ALLOWLIST (comma-separated)
#   4. the triggering message contains an explicit [rp5-test:<scenario>] marker
# If any gate is false, behavior is byte-identical to today's production path —
# see is_enabled_for_turn(), which fails closed on any missing/malformed input.

from __future__ import annotations

import contextvars
import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_ENABLED_VAR       = "RP5_FAULT_INJECTION_ENABLED"
_ALLOWLIST_VAR     = "RP5_FAULT_ALLOWLIST"
_REQUIRE_MARKER_VAR = "RP5_FAULT_REQUIRE_MARKER"
_PREFIX_VAR        = "RP5_FAULT_MARKER_PREFIX"

_DEFAULT_PREFIX = "[rp5-test:"

# Supported markers (task spec) — anything else is not a recognized scenario
# and is treated the same as "no marker at all" (fail closed).
SCENARIOS = frozenset({
    "google-401",
    "write-403",
    "write-validation-400",
    "write-timeout",
    "tool-empty-response",
    "tool-malformed-response",
    "connection-reset",
})

_GOOGLE_TOOL_PREFIXES = ("gmail_", "calendar_")
_GOOGLE_TOOL_NAMES    = frozenset({"search_drive", "read_drive_file"})

# Stable reason codes — reuse core/agent_message_formatter.py's vocabulary so a
# future shadow->on cutover of F52 renders these the same as a real failure.
_REASON_CODE = {
    "google-401":              "GOOGLE_AUTH_REQUIRED",
    "write-403":                "PERMISSION_DENIED",
    "write-validation-400":     "VALIDATION_FAILED",
    "write-timeout":            "PROVIDER_UNAVAILABLE",
    "tool-malformed-response":  "STRUCTURED_RESULT_INVALID",
}

_USER_MESSAGE = {
    "google-401":             "צריך לחבר מחדש את חשבון Google כדי להמשיך.",
    "write-403":               "אין הרשאה לבצע את הפעולה הזאת.",
    "write-validation-400":    "חלק מהפרטים חסרים או לא תקינים.",
    "write-timeout":           "השירות אינו זמין כרגע.",
    "tool-malformed-response": "התקבלה תשובה לא תקינה מהמערכת.",
}


class RP5InjectedTransportError(Exception):
    """Raised for write-timeout / connection-reset. tools/dispatcher.py's
    existing `except Exception` handler around tool execution already turns
    any such exception into a ❌-prefixed failed result — no new exception
    handling was added anywhere for this."""


@dataclass(frozen=True)
class _TurnFault:
    scenario: str
    canonical_user_id: str


# Per-turn state. Deliberately NOT a broad TurnCoordinator: a single
# contextvar, set once at the top of run_agent() (begin_turn) and cleared when
# it returns (end_turn), scoped to one synchronous request-handling call
# stack — the same stack that also carries any ActionGateway approve()
# dispatch_tool() call triggered by a confirmation word within that same turn.
_turn_fault: "contextvars.ContextVar[_TurnFault | None]" = contextvars.ContextVar(
    "rp5_fault_turn", default=None
)


def _env_true(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def is_staging(env: str | None = None) -> bool:
    """env defaults to APP_ENV (same var/pattern as tools/telegram_adapter.py
    and tools/whatsapp_adapter.py's _assert_gateway_context()). Anything other
    than the literal "staging" is treated as not-staging — fail closed."""
    if env is None:
        env = os.environ.get("APP_ENV", "production")
    return str(env).strip().lower() == "staging"


def _allowlist() -> frozenset[str]:
    raw = os.environ.get(_ALLOWLIST_VAR, "")
    return frozenset(x.strip() for x in raw.split(",") if x.strip())


def get_fault_marker(text: str) -> str | None:
    """Extract a supported [rp5-test:<scenario>] marker from free text.
    Returns None if there is no marker, or if the marker names a scenario not
    in SCENARIOS (an unrecognized marker is inert, not a wildcard)."""
    if not text:
        return None
    prefix = os.environ.get(_PREFIX_VAR, _DEFAULT_PREFIX) or _DEFAULT_PREFIX
    idx = text.find(prefix)
    if idx == -1:
        return None
    rest = text[idx + len(prefix):]
    end = rest.find("]")
    if end == -1:
        return None
    scenario = rest[:end].strip().lower()
    return scenario if scenario in SCENARIOS else None


def is_enabled_for_turn(env: str, canonical_user_id: str, text: str) -> bool:
    """All four hard safety gates, ANDed. False on any missing/unset/
    malformed input — fail closed to current production behavior."""
    if not is_staging(env):
        return False
    if not _env_true(_ENABLED_VAR, False):
        return False
    if not canonical_user_id or canonical_user_id not in _allowlist():
        return False
    require_marker = _env_true(_REQUIRE_MARKER_VAR, True)
    marker = get_fault_marker(text)
    if require_marker and marker is None:
        return False
    # Even with RP5_FAULT_REQUIRE_MARKER=false there is no scenario to pick
    # without a marker, so a marker is always effectively required — this is
    # deliberately fail-safe, never fail-open.
    return marker is not None


def begin_turn(canonical_user_id: str, text: str) -> None:
    """Compute this turn's active fault scenario (if any) and stash it for the
    duration of the turn. Call once, at the very top of run_agent(), always
    paired with end_turn() in a finally block. Never raises — any internal
    error fails closed to "no fault active", identical to today's behavior."""
    scenario = None
    try:
        env = os.environ.get("APP_ENV", "production")
        if is_enabled_for_turn(env, canonical_user_id, text):
            scenario = get_fault_marker(text)
    except Exception:
        logger.debug("[RP5FaultInjection] begin_turn failed closed", exc_info=True)
        scenario = None
    _turn_fault.set(_TurnFault(scenario, canonical_user_id) if scenario else None)


def end_turn() -> None:
    _turn_fault.set(None)


def _provider_for_tool(tool_name: str) -> str:
    if tool_name in _GOOGLE_TOOL_NAMES or tool_name.startswith(_GOOGLE_TOOL_PREFIXES):
        return "google"
    if tool_name.startswith("airtable_") or tool_name == "tma_write":
        return "airtable"
    if tool_name.startswith("sheets_"):
        return "sheets"
    return "other"


def maybe_raise_or_return_fault(tool: str, *, read_only: bool):
    """Single injection point — call from tools/dispatcher.py's dispatch_tool()
    immediately before the real tool implementation runs (after identity/role/
    action_validator checks have already passed, so this never bypasses a real
    permission gate).

    Returns None the overwhelming majority of the time (no active turn fault,
    or the active scenario doesn't apply to this tool) — the caller proceeds
    exactly as before. Returns a value the caller must return AS-IS instead of
    calling the real tool: either a structured {"ok": False, ...} dict (same
    C53-A shape real tools use) or "" (empty result). May raise
    RP5InjectedTransportError, which the caller's existing generic
    `except Exception` already converts into a ❌-prefixed failed result.
    """
    fault = _turn_fault.get()
    if fault is None:
        return None
    scenario = fault.scenario

    provider = _provider_for_tool(tool)
    op = "read" if read_only else "write"

    if scenario == "google-401":
        applies = provider == "google"
    elif scenario in ("write-403", "write-validation-400", "write-timeout"):
        applies = not read_only
    elif scenario in ("tool-empty-response", "tool-malformed-response", "connection-reset"):
        applies = True
    else:
        applies = False

    if not applies:
        return None

    logger.warning(
        "[RP5FaultInjection] scenario=%s user=%s provider=%s op=%s tool=%s",
        scenario, fault.canonical_user_id, provider, op, tool,
    )

    if scenario in ("write-timeout", "connection-reset"):
        raise RP5InjectedTransportError(
            f"RP5 staging fault injection: simulated {scenario} for {tool}"
        )

    if scenario == "tool-empty-response":
        return ""

    if scenario == "tool-malformed-response":
        # No "ok" key at all -> core.anti_hallucination.verify_execution()'s
        # `if not raw_output.get("ok")` branch fires for every tool, read or
        # write, exactly like a real unparseable/ambiguous provider payload.
        return {"rp5_fault": scenario, "unexpected_shape": True}

    return {
        "ok":          False,
        "tool":        tool,
        "reason_code": _REASON_CODE.get(scenario, "UNKNOWN_ERROR"),
        "external_id": "",
        "evidence":    {},
        "user_message": f"❌ {_USER_MESSAGE.get(scenario, 'משהו השתבש.')}",
    }
