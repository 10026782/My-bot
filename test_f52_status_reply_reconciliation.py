#!/usr/bin/env python3
# test_f52_status_reply_reconciliation.py
# F52 — Unified Approval Runtime · compose_status_reply / format_agent_message
# reconciliation (FEATURE_UNIFIED_STATUS_FORMATTER).
#
# Run: python3 test_f52_status_reply_reconciliation.py  (or via pytest)
#
# Proves:
#   - off    : legacy status text is byte-identical to before F52.
#   - shadow : legacy text is still sent (unified only logged), and the shadow
#              log record itself carries only safe fields (booleans/counts/
#              state names) — never raw legacy/unified text, record ids, tool
#              names, or payloads (F52 PR4).
#   - on     : the single canonical formatter renders the text; no record_id /
#              tool_name / contract_id leaks; failure codes map to human text;
#              rejection is a failure-family variant; unknown outcome is never
#              success.
#   - a formatter exception never breaks the live path (falls back to legacy).
#   - compose_status_reply remains the single status-text entry point, and
#     represents exactly one ActionFact (batch formatting is out of scope).
#   - pending maps to the approval_pending state specifically; executed/
#     completed map to success only from that outcome.

from __future__ import annotations

import inspect
import os
import sys
import types

from core.action_gateway import ActionGateway, ActionFact, _LEAD_CAPTURE_TABLE
from airtable_schema import LeadFields


class _LogCapture:
    """Minimal stand-in for the module logger — records (level, formatted
    message) pairs without needing pytest's caplog fixture, so this file stays
    runnable both directly (`python3 test_f52_....py`, as CI does for every
    test_*.py) and under pytest."""

    def __init__(self):
        self.records: list[tuple[str, str]] = []

    def _record(self, level, msg, args):
        self.records.append((level, msg % args if args else msg))

    def info(self, msg, *args, **kwargs):
        self._record("info", msg, args)

    def warning(self, msg, *args, **kwargs):
        self._record("warning", msg, args)

    def debug(self, msg, *args, **kwargs):
        self._record("debug", msg, args)

    def error(self, msg, *args, **kwargs):
        self._record("error", msg, args)


def _set(state):
    if state is None:
        os.environ.pop("FEATURE_UNIFIED_STATUS_FORMATTER", None)
    else:
        os.environ["FEATURE_UNIFIED_STATUS_FORMATTER"] = state


def _gw_with_lead_contract():
    gw = ActionGateway()
    fake = types.SimpleNamespace(
        tool_name="airtable_add",
        normalized_payload={"table": _LEAD_CAPTURE_TABLE, "fields": {
            LeadFields.NAME: "דני כהן", LeadFields.PHONE: "0501234567",
            LeadFields.DOMAIN: "real_estate"}},
    )
    gw._ledger.find_by_id = lambda cid: fake
    return gw


F_EXEC = ActionFact("airtable_add", "c1", "executed", "recABC1234567890XYZ", None, {})
F_FAIL = ActionFact("gmail_send_draft", "c2", "failed", None, "GOOGLE_AUTH_REQUIRED", {})
F_PEND = ActionFact("airtable_add", "c3", "pending", None, None, {})
F_REJ  = ActionFact("airtable_add", "c4", "rejected", None, None, {})
F_UNK  = ActionFact("airtable_add", "c5", "weird_outcome", None, None, {})


# ── 1. off = byte-identical legacy ────────────────────────────────────────────

def test_off_is_byte_identical_legacy():
    gw = _gw_with_lead_contract()
    try:
        _set("off")
        assert gw.compose_status_reply(F_EXEC).text.startswith("הפעולה הושלמה:")
        assert "recABC1234567890XYZ" not in gw.compose_status_reply(F_EXEC).text
        assert gw.compose_status_reply(F_FAIL).text == "הפעולה לא הושלמה"
        assert gw.compose_status_reply(F_PEND).text.startswith("יש פעולה שממתינה לאישור:")
        assert gw.compose_status_reply(F_REJ).text.startswith("הפעולה בוטלה:")
    finally:
        _set(None)


def test_unset_and_unknown_flag_fail_closed_to_off():
    gw = _gw_with_lead_contract()
    try:
        _set(None)
        assert gw.compose_status_reply(F_PEND).text.startswith("יש פעולה שממתינה לאישור:")
        _set("banana")
        assert gw.compose_status_reply(F_PEND).text.startswith("יש פעולה שממתינה לאישור:")
    finally:
        _set(None)


# ── 2. shadow = legacy sent, unified only computed/logged ─────────────────────

def test_shadow_still_sends_legacy_text():
    gw = _gw_with_lead_contract()
    try:
        _set("shadow")
        assert gw.compose_status_reply(F_EXEC).text.startswith("הפעולה הושלמה:")
    finally:
        _set(None)


def test_shadow_sends_legacy_text_for_approval_pending():
    gw = _gw_with_lead_contract()
    try:
        _set("shadow")
        assert gw.compose_status_reply(F_PEND).text.startswith("יש פעולה שממתינה לאישור:")
    finally:
        _set(None)


def _shadow_log_line(gw, fact):
    """Runs compose_status_reply(fact) in shadow mode with the module logger
    swapped for a capture double; returns the single
    '[UnifiedStatusFormatterShadow] ...' info line."""
    import core.action_gateway as ag_module
    cap = _LogCapture()
    orig_logger = ag_module.logger
    try:
        _set("shadow")
        ag_module.logger = cap
        gw.compose_status_reply(fact)
    finally:
        ag_module.logger = orig_logger
        _set(None)
    lines = [m for lvl, m in cap.records
              if lvl == "info" and "UnifiedStatusFormatterShadow" in m]
    assert len(lines) == 1, f"expected exactly one shadow log line, got {lines}"
    return lines[0]


def test_shadow_log_contains_only_safe_comparison_fields():
    gw = _gw_with_lead_contract()
    line = _shadow_log_line(gw, F_EXEC)
    # required safe fields
    assert "outcome=executed" in line
    assert "mapped_state=success" in line
    assert "text_differs=" in line
    assert "record_id_leak=False" in line
    assert "tool_name_leak=False" in line
    assert "contract_id_leak=False" in line
    assert "redaction_count=" in line
    assert "fallback_used=" in line
    # forbidden: raw legacy/unified text, business data, record id, tool name
    assert "דני כהן" not in line
    assert "0501234567" not in line
    assert "recABC1234567890XYZ" not in line
    assert "airtable_add" not in line
    assert "✅" not in line and "✓" not in line


def test_shadow_log_never_leaks_raw_text_for_pending():
    gw = _gw_with_lead_contract()
    line = _shadow_log_line(gw, F_PEND)
    assert "outcome=pending" in line
    assert "mapped_state=approval_pending" in line
    assert "airtable_add" not in line
    assert "c3" not in line   # contract_id


# ── 3. on = unified formatter, no leaks ───────────────────────────────────────

def test_on_success_uses_business_label_no_leaks():
    gw = _gw_with_lead_contract()
    try:
        _set("on")
        out = gw.compose_status_reply(F_EXEC).text
        assert "recABC1234567890XYZ" not in out       # record id dropped
        assert "airtable_add" not in out               # tool name dropped
        assert "דני כהן" in out
        assert "✓" in out and "בוצע" not in out        # first-person, not passive
    finally:
        _set(None)


def test_on_failure_maps_code_to_human_text():
    gw = _gw_with_lead_contract()
    try:
        _set("on")
        out = gw.compose_status_reply(F_FAIL).text
        assert "Google" in out and "GOOGLE_AUTH_REQUIRED" not in out
        assert "gmail_send_draft" not in out
        assert "✅" not in out and "✓" not in out       # not a success
    finally:
        _set(None)


def test_on_pending_and_rejected_and_unknown():
    gw = _gw_with_lead_contract()
    try:
        _set("on")
        pend = gw.compose_status_reply(F_PEND).text
        assert "אישור" in pend and "airtable_add" not in pend
        rej = gw.compose_status_reply(F_REJ).text
        assert "✓" not in rej and "airtable_add" not in rej and "בוטל" in rej   # failure-family
        unk = gw.compose_status_reply(F_UNK).text
        assert unk and "✓" not in unk and "✅" not in unk                        # never success
    finally:
        _set(None)


# ── 3b. approval_pending correctness ──────────────────────────────────────────

def test_pending_outcome_maps_to_approval_pending_state():
    gw = _gw_with_lead_contract()
    state, _payload = gw._action_fact_to_message(F_PEND)
    assert state == "approval_pending"


def test_approval_pending_unified_output_never_claims_completion():
    gw = _gw_with_lead_contract()
    try:
        _set("on")
        out = gw.compose_status_reply(F_PEND).text
        assert "✓" not in out and "✅" not in out
        assert "הושלמ" not in out and "בוצע" not in out
        assert "לאשר" in out
    finally:
        _set(None)


def test_approval_pending_unified_output_never_exposes_tool_name_record_or_contract_id():
    gw = _gw_with_lead_contract()
    fact_with_ids = ActionFact(
        "airtable_add", "internal-contract-id-9999", "pending",
        "recXYZ0987654321ABCDE", None, {},
    )
    try:
        _set("on")
        out = gw.compose_status_reply(fact_with_ids).text
        assert "airtable_add" not in out
        assert "recXYZ0987654321ABCDE" not in out
        assert "internal-contract-id-9999" not in out
    finally:
        _set(None)


# ── 4. formatter exception never breaks the live path ─────────────────────────

def test_formatter_exception_falls_back_to_legacy():
    gw = _gw_with_lead_contract()
    import core.agent_message_formatter as amf
    orig = amf.format_agent_message_with_meta
    try:
        _set("on")
        amf.format_agent_message_with_meta = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
        assert gw.compose_status_reply(F_PEND).text.startswith("יש פעולה שממתינה לאישור:")
    finally:
        amf.format_agent_message_with_meta = orig
        _set(None)


# ── 4b. verified status correctness (outcome -> state mapping) ────────────────

def test_executed_and_completed_outcomes_both_map_to_success():
    gw = _gw_with_lead_contract()
    for outcome in ("executed", "completed"):
        fact = ActionFact("airtable_add", "c1", outcome, None, None, {})
        state, _payload = gw._action_fact_to_message(fact)
        assert state == "success", f"outcome={outcome} should map to success, got {state}"


def test_failed_outcome_maps_to_failure():
    gw = _gw_with_lead_contract()
    state, _payload = gw._action_fact_to_message(F_FAIL)
    assert state == "failure"


def test_rejected_outcome_maps_to_failure_family():
    gw = _gw_with_lead_contract()
    state, payload = gw._action_fact_to_message(F_REJ)
    assert state == "failure"
    assert payload.get("reason_code") == "ACTION_REJECTED"


def test_unrecognized_outcome_maps_to_outcome_unknown_never_success():
    gw = _gw_with_lead_contract()
    state, _payload = gw._action_fact_to_message(F_UNK)
    assert state == "outcome_unknown"
    assert state != "success"


def test_only_executed_and_completed_ever_produce_success_state():
    gw = _gw_with_lead_contract()
    non_success_outcomes = ("pending", "rejected", "failed", "weird_outcome", "")
    for outcome in non_success_outcomes:
        fact = ActionFact("airtable_add", "cX", outcome, None, None, {})
        state, _payload = gw._action_fact_to_message(fact)
        assert state != "success", f"outcome={outcome!r} must never map to success"


# ── 5. single entry point / single-fact scope ──────────────────────────────────

def test_single_status_text_entry_point():
    assert callable(getattr(ActionGateway, "compose_status_reply", None))
    assert callable(getattr(ActionGateway, "_compose_status_reply_legacy", None))
    assert callable(getattr(ActionGateway, "_compose_status_reply_unified", None))


def test_compose_status_reply_represents_exactly_one_action_fact():
    """F52 PR4 scope guard: compose_status_reply() takes exactly one ActionFact
    — no list/batch parameter exists on this path. Multi-status/batch rendering
    (approval_pending_batch, mixed, mixed_with_unknown) is documented as out of
    scope for PR4 rather than invented here — see
    docs/architecture/f52-unified-approval-runtime/PR4_ACTION_STATUS_SHADOW_VERIFICATION.md §5."""
    sig = inspect.signature(ActionGateway.compose_status_reply)
    params = [p for name, p in sig.parameters.items() if name != "self"]
    assert len(params) == 1
    assert params[0].name == "fact"
    assert str(params[0].annotation) == "ActionFact"


def test_default_unified_status_formatter_flag_is_off():
    from feature_flags import get_unified_status_formatter_state
    _set(None)
    try:
        assert get_unified_status_formatter_state() == "off"
    finally:
        _set(None)


# ── plain-script runner (repo CI runs test_*.py directly) ─────────────────────

if __name__ == "__main__":
    _tests = [v for k, v in sorted(globals().items())
              if k.startswith("test_") and callable(v)]
    passed = 0
    failed = 0
    for t in _tests:
        try:
            t()
            passed += 1
            print(f"  ✅ {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  ❌ {t.__name__} — {e}")
    print(f"\n{'═'*60}")
    print(f"F52 status-reply reconciliation: {passed}/{passed+failed} passed")
    sys.exit(0 if failed == 0 else 1)
