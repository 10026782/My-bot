#!/usr/bin/env python3
# test_agent_message_formatter.py
# F52 — Unified Approval Runtime · PR 1 — Message Contract Foundation
#
# Tests the standalone semantic formatter core/agent_message_formatter.py.
# Runs with pytest OR as a plain script (python3 test_agent_message_formatter.py).
#
# Layer under test: WORDING only. The formatter renders the state it is told and
# must never upgrade a non-success state into success, never expose technical
# identifiers, and never emit Markdown.

from __future__ import annotations

import re
import sys

from core.agent_message_formatter import (
    format_agent_message as fmt,
    format_agent_message_with_meta as fmt_meta,
    FORMATTER_VERSION,
    CANONICAL_STATES,
)

# ── shared assertions ─────────────────────────────────────────────────────────

_MARKDOWN_CHARS = set("*_`~#>[]")
_RAW_ID_PATTERNS = [
    re.compile(r"\brec[A-Za-z0-9]{10,}\b"),                                   # Airtable record id
    re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"),  # UUID
    re.compile(r"\b(?=[0-9a-fA-F]*[a-fA-F])[0-9a-fA-F]{16,}\b"),             # long hex id
    re.compile(r"https?://"),                                                 # url
]
_TOOL_NAMES = ["airtable_add", "calendar_create_event", "crm_mark_payment_paid",
               "gmail_send_draft", "airtable_update"]
_SUCCESS_MARKERS = ["✓", "✅", "✔"]


def _assert_no_markdown(text: str) -> None:
    assert not (set(text) & _MARKDOWN_CHARS), f"markdown chars leaked: {text!r}"


def _assert_no_raw_ids(text: str) -> None:
    for pat in _RAW_ID_PATTERNS:
        assert not pat.search(text), f"raw technical id leaked: {text!r}"


def _assert_no_tool_names(text: str) -> None:
    low = text.lower()
    for tn in _TOOL_NAMES:
        assert tn not in low, f"tool name leaked: {tn} in {text!r}"
    # generic snake_case token guard
    assert not re.search(r"\b[a-z][a-z0-9]*_[a-z0-9]+\b", low), f"snake_case token leaked: {text!r}"


def _assert_no_success_marker(text: str) -> None:
    for mk in _SUCCESS_MARKERS:
        assert mk not in text, f"success marker leaked into non-success state: {text!r}"


# ── test collection ───────────────────────────────────────────────────────────

_results = []


def _run(name, fn):
    try:
        fn()
        _results.append((name, True, ""))
    except AssertionError as e:
        _results.append((name, False, str(e)))


# ── 1. success ────────────────────────────────────────────────────────────────

def test_success_formats_with_human_wording():
    out = fmt("success", {"action": "create", "entity_name": "דני כהן",
                          "business_identifier": "0501234567"})
    assert "דני כהן" in out
    assert "0501234567" in out          # phone preserved
    assert "יצרתי" in out               # first-person verb, not passive "בוצע"
    assert "בוצע" not in out
    _assert_no_markdown(out)


def test_success_does_not_expose_raw_ids():
    out = fmt("success", {"human_summary": "שמרתי את דני כהן recABC1234567890XYZ"})
    assert "recABC1234567890XYZ" not in out
    _assert_no_raw_ids(out)


def test_success_does_not_expose_tool_names():
    out = fmt("success", {"human_summary": "יצרתי ליד דרך airtable_add",
                          "action": "create", "entity_name": "דני"})
    _assert_no_tool_names(out)


def test_success_first_person_verbs_per_action():
    for action, verb in (("update", "עדכנתי"), ("delete", "מחקתי"), ("send", "שלחתי")):
        out = fmt("success", {"action": action, "entity_name": "משהו"})
        assert verb in out, f"{action} -> expected {verb} in {out!r}"


def test_success_missing_data_neutral_fallback_not_technical():
    out = fmt("success", {})
    assert out                              # non-empty
    _assert_no_tool_names(out)
    _assert_no_raw_ids(out)


# ── 2. failure ────────────────────────────────────────────────────────────────

def test_failure_maps_to_safe_human_text():
    out = fmt("failure", {"reason_code": "GOOGLE_AUTH_REQUIRED"})
    assert "Google" in out
    _assert_no_success_marker(out)
    _assert_no_markdown(out)


def test_failure_unknown_code_is_generic_not_raw_exception():
    out = fmt("failure", {"reason_code": "SOME_INTERNAL_TRACEBACK",
                          "reason": "KeyError at line 42 airtable_add"})
    _assert_no_tool_names(out)
    _assert_no_success_marker(out)


def test_failure_never_exposes_raw_exception_ids():
    out = fmt("failure", {"reason": "boom recABC1234567890XYZ https://internal/x"})
    _assert_no_raw_ids(out)


# ── 3. approval_pending ───────────────────────────────────────────────────────

def test_approval_pending_says_approval_required_before_action():
    out = fmt("approval_pending", {"human_summary": "יצירת ליד עבור דני כהן (0501234567)"})
    assert "אישור" in out
    assert "כן" in out and "לא" in out
    _assert_no_success_marker(out)


def test_approval_pending_uses_business_summary_not_tool_name():
    out = fmt("approval_pending", {"human_summary": "יצירת ליד עבור דני כהן",
                                   "reason": "airtable_add"})
    _assert_no_tool_names(out)


# ── 3b. approval_pending: new-prompt vs. status-query wording (F52 D-015) ──────
# D-015 (F52 Decision Log): a NEW approval prompt (right after the user's
# request is queued) and a STATUS QUERY about an already-pending action need
# distinct framing. "approval_pending" (STATE_APPROVAL_PENDING) renders the
# new-prompt wording — it is the only state reachable via the MessageContract
# crossing (ActionGateway._render_pending_prompt(), the live pending caller).
# "approval_pending_query" (STATE_APPROVAL_PENDING_QUERY) renders the
# status-query wording — not part of core.message_contract.MessageState, not
# reachable via MessageContract, only via a direct format_agent_message_*()
# call. No live call site uses it yet (see core/agent_message_formatter.py).

def test_approval_pending_new_prompt_wording_distinct_from_status_query():
    new_prompt = fmt("approval_pending", {"human_summary": "יצירת ליד עבור דני כהן"})
    status_query = fmt("approval_pending_query", {"human_summary": "יצירת ליד עבור דני כהן"})
    assert new_prompt.startswith("כדי לבצע את הפעולה הזו נדרש אישור:")
    assert status_query.startswith("יש פעולה שממתינה לאישור:")
    assert new_prompt != status_query
    for out in (new_prompt, status_query):
        assert "לאשר" in out and "כן" in out and "לא" in out
        assert "דני כהן" in out


def test_approval_pending_task_noun_new_prompt_vs_status_query():
    task_new_prompt = fmt("approval_pending", {"entity_name": "חזרה לספק", "entity_type": "task"})
    task_status_query = fmt("approval_pending_query", {"entity_name": "חזרה לספק", "entity_type": "task"})
    assert task_new_prompt.startswith("כדי ליצור את המשימה הזו נדרש אישור:")
    assert task_status_query.startswith("יש משימה שממתינה לאישור:")
    assert "חזרה לספק" in task_new_prompt and "חזרה לספק" in task_status_query


def test_approval_pending_non_task_entity_type_keeps_generic_noun():
    out_new = fmt("approval_pending", {"entity_name": "פגישה עם רונית", "entity_type": "meeting"})
    out_query = fmt("approval_pending_query", {"entity_name": "פגישה עם רונית", "entity_type": "meeting"})
    assert out_new.startswith("כדי לבצע את הפעולה הזו נדרש אישור:")
    assert out_query.startswith("יש פעולה שממתינה לאישור:")


def test_approval_pending_missing_data_fallback_differs_new_prompt_vs_query():
    new_fallback = fmt("approval_pending", {})
    query_fallback = fmt("approval_pending_query", {})
    assert new_fallback != query_fallback
    assert "אישור" in new_fallback and "אישור" in query_fallback
    _assert_no_success_marker(new_fallback)
    _assert_no_success_marker(query_fallback)


def test_approval_pending_query_state_not_in_message_contract_schema():
    """F52 D-015: approval_pending_query must stay reachable only via a direct
    format_agent_message_*() call, never via the MessageContract crossing —
    no MessageContract/MessageState schema change for this decision."""
    from core.message_contract import MessageState
    assert "approval_pending_query" not in {s.value for s in MessageState}
    assert "approval_pending_query" in CANONICAL_STATES


# ── 4. approval_pending_batch ─────────────────────────────────────────────────

def test_approval_pending_batch_uses_business_summaries_not_tool_names():
    out = fmt("approval_pending_batch", {"items": [
        {"human_summary": "יצירת ליד עבור דני כהן"},
        {"human_summary": "עדכון משימה: חזרה לספק"},
        {"human_summary": "שליחת מייל לרונית"},
    ]})
    assert "1." in out and "2." in out and "3." in out
    assert "דני כהן" in out
    assert "מספר" in out                    # "שלח מספר כדי לבחור"
    _assert_no_tool_names(out)
    _assert_no_success_marker(out)


def test_approval_pending_batch_alias_approval_batch():
    out = fmt("approval_batch", {"items": [{"human_summary": "פעולה א"}]})
    assert "אישור" in out


# ── 5. clarification_needed ───────────────────────────────────────────────────

def test_clarification_asks_one_focused_question():
    out = fmt("clarification_needed", {"human_summary": "לאיזה דני התכוונת?",
                                       "user_options": ["דני כהן", "דני לוי"]})
    assert out.count("?") <= 1
    assert "דני כהן" in out
    _assert_no_success_marker(out)


def test_clarification_caps_at_three_choices():
    out = fmt("clarification_needed", {"human_summary": "מי מהם?",
                                       "user_options": ["א", "ב", "ג", "ד", "ה"]})
    assert out.count("\n- ") <= 3, f"more than three choices rendered: {out!r}"


# ── 6. idle ───────────────────────────────────────────────────────────────────

def test_idle_is_short_and_does_not_list_capabilities():
    out = fmt("idle", {})
    assert len(out) < 120
    # No enumerated capability list.
    assert not re.search(r"(?:^|\n)\s*[1-9]\.", out), f"idle enumerated a list: {out!r}"
    _assert_no_success_marker(out)


# ── 7. outcome_unknown ────────────────────────────────────────────────────────

def test_outcome_unknown_says_cannot_verify_and_no_auto_retry():
    out = fmt("outcome_unknown", {})
    assert "לאמת" in out
    assert "שוב" in out                     # references retry
    _assert_no_success_marker(out)


# ── 8. unverified_effect ──────────────────────────────────────────────────────

def test_unverified_effect_requires_manual_check():
    out = fmt("unverified_effect", {})
    assert "ידני" in out                    # manual check
    _assert_no_success_marker(out)
    _assert_no_tool_names(out)


# ── 9. mixed / mixed_with_unknown ─────────────────────────────────────────────

def test_mixed_does_not_collapse_into_full_success():
    out = fmt("mixed", {"items": ["יצירת ליד: הצליח", "שליחת מייל: נכשל"]})
    _assert_no_success_marker(out)
    assert "לא" in out                      # acknowledges partial non-success


def test_mixed_with_unknown_does_not_collapse_into_full_success():
    out = fmt("mixed_with_unknown", {"items": ["פעולה א"]})
    _assert_no_success_marker(out)
    assert "לאמת" in out                    # references the unverifiable part


# ── 10. sanitization / security ───────────────────────────────────────────────

def test_formatter_redacts_raw_technical_identifiers():
    # Dirty technical content in a RENDERED location (human_summary with no
    # structured display_payload, so it is used as the descriptor) is redacted.
    payload = {"human_summary": "עשיתי recABC1234567890XYZ "
                                 "550e8400-e29b-41d4-a716-446655440000 "
                                 "https://internal.example/secret "
                                 "deadbeefdeadbeef01 airtable_add"}
    out, meta = fmt_meta("success", payload)
    _assert_no_raw_ids(out)
    _assert_no_tool_names(out)
    assert meta["redaction_count"] >= 3, f"expected redactions, meta={meta}"


def test_human_summary_ignored_when_structured_payload_present():
    # Spec 'human_summary migration': a valid structured display_payload wins,
    # and the human_summary hint is ignored (never leaks, never renders).
    out = fmt("success", {"action": "update", "entity_name": "דני",
                          "human_summary": "recABC1234567890XYZ airtable_add דבר מלוכלך"})
    assert "דני" in out and "עדכנתי" in out
    assert "דבר מלוכלך" not in out           # hint ignored when structured present
    _assert_no_raw_ids(out)
    _assert_no_tool_names(out)


def test_formatter_output_contains_no_bold_markdown():
    for state, payload in (
        ("success", {"human_summary": "**מודגש** _נטוי_ `קוד`", "entity_name": "x"}),
        ("failure", {"reason": "**boom**"}),
        ("approval_pending", {"human_summary": "יצירת *ליד*"}),
        ("clarification_needed", {"human_summary": "מה?", "user_options": ["`a`", "_b_"]}),
    ):
        _assert_no_markdown(fmt(state, payload))


def test_formatter_output_contains_no_raw_provider_payload():
    out = fmt("success", {"human_summary": 'ok {"table":"Leads","apiKey":"keyABCDEF0123456789XYZ"}',
                          "entity_name": "דני", "action": "create"})
    assert "keyABCDEF0123456789XYZ" not in out
    assert "apiKey" not in out
    _assert_no_raw_ids(out)


def test_injected_execution_claim_in_field_value_is_neutralized():
    # A field value must not smuggle a success glyph/claim; only the state marker
    # may express status.
    out = fmt("approval_pending", {"human_summary": "יצירת ליד ✅ הפעולה בוצעה"})
    _assert_no_success_marker(out)


def test_success_marker_appears_at_most_once():
    out = fmt("success", {"human_summary": "✓ ✅ הצלחתי", "entity_name": "x"})
    assert sum(out.count(m) for m in _SUCCESS_MARKERS) <= 1, f"multiple markers: {out!r}"


def test_iso_date_rendered_human_not_raw():
    out = fmt("success", {"action": "create", "entity_name": "פגישה",
                          "fields": [{"label": "מתי", "value": "2026-07-17T09:30:00+03:00",
                                      "occurred_at": True}]})
    assert "2026-07-17T09:30:00" not in out
    assert "17/07/2026" in out


def test_unknown_state_is_neutral_never_success():
    out = fmt("totally_bogus_state", {"human_summary": "✅ הצלחתי"})
    _assert_no_success_marker(out)
    assert out


def test_all_canonical_states_render_without_error():
    for state in CANONICAL_STATES:
        out = fmt(state, {})
        assert isinstance(out, str) and out


def test_meta_reports_state_and_version():
    _, meta = fmt_meta("idle", {})
    assert meta["message_state"] == "idle"
    assert meta["formatter_version"] == FORMATTER_VERSION


# ── runner ────────────────────────────────────────────────────────────────────

_TESTS = [obj for name, obj in sorted(globals().items())
          if name.startswith("test_") and callable(obj)]

if __name__ == "__main__":
    for t in _TESTS:
        _run(t.__name__, t)
    passed = sum(1 for _, ok, _ in _results if ok)
    for name, ok, err in _results:
        print(f"  {'✅' if ok else '❌'} {name}" + (f" — {err}" if not ok else ""))
    print(f"\n{'═'*60}")
    print(f"F52 PR1 agent_message_formatter: {passed}/{len(_results)} passed")
    sys.exit(0 if passed == len(_results) else 1)
