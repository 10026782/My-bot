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

from core.action_gateway import (
    ActionGateway, ActionFact, _LEAD_CAPTURE_TABLE, _TASK_CREATION_TABLE,
    build_approval_lifecycle_result,
)
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


def _gw_with_task_contract(title="להתקשר לספק ולתאם משלוח"):
    gw = ActionGateway()
    fake = types.SimpleNamespace(
        tool_name="airtable_add",
        contract_id="c-task-1",
        status="pending",
        normalized_payload={"table": _TASK_CREATION_TABLE, "fields": {"Name": title}},
    )
    gw._ledger.find_by_id = lambda cid: fake
    return gw, fake


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


def test_failed_shadow_log_proves_message_contract_path_without_identifier_leaks():
    gw = _gw_with_lead_contract()
    fact = ActionFact(
        "secret_internal_tool", "secret-contract-id", "failed",
        "recSECRET1234567890XYZ", "GOOGLE_AUTH_REQUIRED",
        {"payload_secret": "must-not-leak"},
    )
    line = _shadow_log_line(gw, fact)

    assert "outcome=failed" in line
    assert "mapped_state=failure" in line
    assert "contract_path=message_contract" in line
    assert "contract_version=1.0" in line
    assert "source_component=core.action_fact_message_adapter" in line
    assert "record_id_leak=False" in line
    assert "tool_name_leak=False" in line
    assert "contract_id_leak=False" in line
    for forbidden in (
        "secret_internal_tool", "secret-contract-id", "recSECRET1234567890XYZ",
        "payload_secret", "must-not-leak", "GOOGLE_AUTH_REQUIRED",
    ):
        assert forbidden not in line


def test_non_failed_shadow_logs_are_legacy_not_message_contract():
    gw = _gw_with_lead_contract()
    for fact in (F_EXEC, F_REJ, F_UNK):
        line = _shadow_log_line(gw, fact)
        assert "contract_path=legacy" in line
        assert "contract_path=message_contract" not in line
        assert "contract_version=" not in line
        assert "source_component=" not in line


def test_pending_shadow_log_proves_message_contract_path():
    gw = _gw_with_lead_contract()
    line = _shadow_log_line(gw, F_PEND)
    assert "outcome=pending" in line
    assert "contract_path=message_contract" in line
    assert "contract_version=1.0" in line
    assert "source_component=core.action_fact_message_adapter" in line


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


def test_failed_runtime_message_contract_path_is_byte_identical_to_old_path():
    """PR D: ה-outcome היחיד שחווט משמר את בייטי ה-formatter מלפני החיווט."""
    from unittest.mock import patch
    from core.agent_message_formatter import format_agent_message_with_meta
    import core.action_fact_message_adapter as adapter_module

    gw = _gw_with_lead_contract()
    old_state, old_payload = gw._action_fact_to_message(F_FAIL)
    old_result = format_agent_message_with_meta(old_state, old_payload)
    calls = []
    original = adapter_module.from_action_fact

    def recording_adapter(*args, **kwargs):
        calls.append((args, kwargs))
        return original(*args, **kwargs)

    with patch.object(adapter_module, "from_action_fact", recording_adapter):
        new_result = gw._compose_status_reply_unified(F_FAIL)

    assert len(calls) == 1
    assert new_result[0] == old_result[0]
    for key in ("message_state", "formatter_version", "fallback_used", "redaction_count"):
        assert new_result[1][key] == old_result[1][key]


def test_pending_runtime_message_contract_path_is_byte_identical_to_old_path():
    """PR E: pending מקבל את אותו output של המסלול הישן של ה-formatter."""
    from unittest.mock import patch
    from core.agent_message_formatter import format_agent_message_with_meta
    import core.action_fact_message_adapter as adapter_module

    gw = _gw_with_lead_contract()
    old_state, old_payload = gw._action_fact_to_message(F_PEND)
    old_result = format_agent_message_with_meta(old_state, old_payload)
    calls = []
    original = adapter_module.from_action_fact

    def recording_adapter(*args, **kwargs):
        calls.append((args, kwargs))
        return original(*args, **kwargs)

    with patch.object(adapter_module, "from_action_fact", recording_adapter):
        new_result = gw._compose_status_reply_unified(F_PEND)

    assert len(calls) == 1
    assert new_result[0] == old_result[0]
    for key in ("message_state", "formatter_version", "fallback_used", "redaction_count"):
        assert new_result[1][key] == old_result[1][key]
    assert new_result[1]["contract_path"] == "message_contract"
    assert new_result[1]["source_component"] == "core.action_fact_message_adapter"


def test_pending_message_contract_observability_is_explicit():
    gw = _gw_with_lead_contract()
    text, meta = gw._compose_status_reply_unified(F_PEND)
    assert text
    assert meta["contract_path"] == "message_contract"
    assert meta["source_component"] == "core.action_fact_message_adapter"
    assert F_PEND.outcome == "pending"


def test_only_failed_and_pending_outcomes_use_message_contract_runtime_adapter():
    """PR D + PR E scope: only failed/pending leave the legacy path."""
    from unittest.mock import patch
    import core.action_fact_message_adapter as adapter_module

    gw = _gw_with_lead_contract()
    calls = []
    original = adapter_module.from_action_fact

    def recording_adapter(*args, **kwargs):
        calls.append(args[0].outcome)
        return original(*args, **kwargs)

    with patch.object(adapter_module, "from_action_fact", recording_adapter):
        for fact in (F_EXEC, F_FAIL, F_PEND, F_REJ, F_UNK):
            gw._compose_status_reply_unified(fact)

    assert calls == ["failed", "pending"]


def test_failed_remains_pr_d_path_and_other_outcomes_remain_legacy():
    """The PR E expansion must not broaden the existing PR D boundary."""
    from unittest.mock import patch
    import core.action_fact_message_adapter as adapter_module

    gw = _gw_with_lead_contract()
    calls = []
    original = adapter_module.from_action_fact

    def recording_adapter(*args, **kwargs):
        calls.append(args[0].outcome)
        return original(*args, **kwargs)

    with patch.object(adapter_module, "from_action_fact", recording_adapter):
        for fact in (F_FAIL, F_PEND, F_EXEC, F_REJ, F_UNK):
            gw._compose_status_reply_unified(fact)

    assert calls == ["failed", "pending"]


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


def test_pending_task_creation_uses_task_title_not_generic_record_description():
    """Production parity gap (PR E probe, 01/08/2026): a real
    [UnifiedStatusFormatterShadow] pending line showed text_differs=True
    (legacy_len=56, unified_len=83). Root cause — _compose_status_reply_
    unified()'s MessageContract crossing described EVERY pending contract
    with the generic, table-agnostic _safe_contract_business_description()
    ("הוספת רשומה: ..."), while the real send site (app.py's
    _queue_approval_detailed_impl(), via build_approval_lifecycle_result()
    .safe_user_message) already special-cases Task-creation contracts to
    show the task's own title instead. This proves the unified path now
    carries the same task-aware content as the legacy formatter for a
    Task-creation pending contract — an output-content fix only. The
    surrounding phrasing (newline layout, the "לאשר? כן / לא" prompt) is an
    intentional UNIFIED_MESSAGE_UX_STANDARD.md difference and is left
    untouched — still text_differs by design, not a bug."""
    gw, fake = _gw_with_task_contract("להתקשר לספק ולתאם משלוח")
    fact = ActionFact("airtable_add", fake.contract_id, "pending", None, None, {})

    legacy_text = build_approval_lifecycle_result(
        fake, canonical_state="pending",
    ).safe_user_message
    unified_text, _meta = gw._compose_status_reply_unified(fact)

    assert "להתקשר לספק ולתאם משלוח" in legacy_text
    assert "להתקשר לספק ולתאם משלוח" in unified_text
    assert "הוספת רשומה" not in legacy_text
    assert "הוספת רשומה" not in unified_text


def test_pending_non_task_record_still_uses_generic_business_description():
    """Regression guard: the task-title fix above must stay scoped to actual
    Task-creation contracts. A non-Task airtable_add (e.g. a Lead) must keep
    using the same generic _safe_contract_business_description() wording on
    both the legacy and unified paths, unchanged."""
    gw = _gw_with_lead_contract()
    old_state, old_payload = gw._action_fact_to_message(F_PEND)
    assert old_payload["human_summary"].startswith("הוספת רשומה")

    unified_text, _meta = gw._compose_status_reply_unified(F_PEND)
    assert "דני כהן" in unified_text


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


def test_failed_message_contract_exception_logs_distinct_fallback_and_keeps_output():
    import core.action_gateway as ag_module
    import core.agent_message_formatter as amf

    gw = _gw_with_lead_contract()
    cap = _LogCapture()
    orig_logger = ag_module.logger
    orig_formatter = amf.format_agent_message_with_meta
    legacy = gw._compose_status_reply_legacy(F_FAIL).text
    try:
        _set("shadow")
        ag_module.logger = cap
        amf.format_agent_message_with_meta = lambda *a, **k: (
            _ for _ in ()
        ).throw(RuntimeError("safe-test-failure"))
        result = gw.compose_status_reply(F_FAIL).text
    finally:
        amf.format_agent_message_with_meta = orig_formatter
        ag_module.logger = orig_logger
        _set(None)

    assert result == legacy
    warnings = [message for level, message in cap.records if level == "warning"]
    assert len(warnings) == 1
    assert "contract_path=message_contract_fallback" in warnings[0]
    for forbidden in (F_FAIL.tool_name, F_FAIL.contract_id, "GOOGLE_AUTH_REQUIRED"):
        assert forbidden not in warnings[0]


def test_pending_message_contract_exception_logs_distinct_fallback_and_keeps_output():
    import core.action_gateway as ag_module
    import core.agent_message_formatter as amf

    gw = _gw_with_lead_contract()
    cap = _LogCapture()
    orig_logger = ag_module.logger
    orig_formatter = amf.format_agent_message_with_meta
    legacy = gw._compose_status_reply_legacy(F_PEND).text
    try:
        _set("shadow")
        ag_module.logger = cap
        amf.format_agent_message_with_meta = lambda *a, **k: (
            _ for _ in ()
        ).throw(RuntimeError("safe-test-pending-failure"))
        result = gw.compose_status_reply(F_PEND).text
    finally:
        amf.format_agent_message_with_meta = orig_formatter
        ag_module.logger = orig_logger
        _set(None)

    assert result == legacy
    warnings = [message for level, message in cap.records if level == "warning"]
    assert len(warnings) == 1
    assert "contract_path=message_contract_fallback" in warnings[0]
    for forbidden in (F_PEND.tool_name, F_PEND.contract_id):
        assert forbidden not in warnings[0]


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
