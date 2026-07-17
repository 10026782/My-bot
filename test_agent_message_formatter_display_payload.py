#!/usr/bin/env python3
# test_agent_message_formatter_display_payload.py
# F52 — display_payload / unified payload mapping.
#
# Run: python3 test_agent_message_formatter_display_payload.py  (or via pytest)
#
# Proves the formatter accepts the UX standard's canonical display_payload
# contract, that legacy field names still work (compatibility), and that the
# human_summary migration rule holds (hint-only; ignored when structured).

from __future__ import annotations

import sys

from core.agent_message_formatter import (
    format_agent_message as fmt,
    _normalize_payload,
)


# ── canonical display_payload is accepted ─────────────────────────────────────

def test_canonical_display_payload_success():
    out = fmt("success", {
        "action": "create", "entity_type": "lead", "entity_name": "דני כהן",
        "key_fields": [{"label": "טלפון", "value": "0501234567"}],
        "occurred_at": "2026-07-17T09:30:00+03:00", "execution_verified": True,
    })
    assert "יצרתי" in out and "דני כהן" in out
    assert "טלפון: 0501234567" in out          # key_fields rendered
    assert "17/07/2026" in out                 # occurred_at -> human date
    assert "2026-07-17T09:30:00" not in out    # never raw ISO


def test_canonical_key_fields_capped_at_two():
    out = fmt("success", {"action": "create", "entity_name": "x", "key_fields": [
        {"label": "a", "value": "1"}, {"label": "b", "value": "2"},
        {"label": "c", "value": "3"},
    ]})
    assert out.count("\n- ") <= 2


def test_canonical_failure_reason_code():
    out = fmt("failure", {"reason_code": "PERMISSION_DENIED"})
    assert "הרשאה" in out
    assert "PERMISSION_DENIED" not in out


def test_canonical_batch_items_and_count():
    out = fmt("approval_pending_batch", {"count": 2, "items": [
        {"entity_name": "דני כהן"}, {"human_summary": "עדכון משימה"},
    ]})
    assert "יש 2 פעולות" in out
    assert "1. דני כהן" in out and "2. עדכון משימה" in out


# ── execution_verified gate ───────────────────────────────────────────────────

def test_execution_verified_false_never_renders_success():
    out = fmt("success", {"action": "create", "entity_name": "דני",
                          "execution_verified": False})
    assert "✓" not in out and "יצרתי" not in out
    assert "לאמת" in out                       # honest "cannot verify" message


def test_execution_verified_absent_or_true_renders_success():
    for ev in (None, True):
        payload = {"action": "create", "entity_name": "דני"}
        if ev is not None:
            payload["execution_verified"] = ev
        out = fmt("success", payload)
        assert out.startswith("✓")


# ── legacy compatibility (loose shape still works) ────────────────────────────

def test_legacy_fields_name_still_supported():
    out = fmt("success", {"action": "update", "entity_name": "משימה",
                          "fields": [{"label": "סטטוס", "value": "סגור"}]})
    assert "עדכנתי משימה" in out and "סטטוס: סגור" in out


def test_legacy_business_identifier_and_reason():
    out_ap = fmt("approval_pending", {"entity_name": "דני כהן",
                                      "business_identifier": "0501234567"})
    assert "דני כהן (0501234567)" in out_ap
    out_f = fmt("failure", {"reason": "משהו לא תקין"})   # legacy human reason
    assert "משהו לא תקין" in out_f


# ── human_summary migration rule ──────────────────────────────────────────────

def test_human_summary_used_only_when_no_structured_payload():
    # No structured fields -> hint is the descriptor.
    out = fmt("success", {"human_summary": "שמרתי את דני כהן"})
    assert "שמרתי את דני כהן" in out
    # Structured present -> hint ignored.
    out2 = fmt("success", {"action": "create", "entity_name": "רון",
                           "human_summary": "טקסט שצריך להתעלם ממנו"})
    assert "רון" in out2 and "להתעלם" not in out2


def test_human_summary_never_enables_success_content_leak():
    # A hint that smuggles a success glyph/claim is neutralized, and when a
    # structured payload exists the hint is dropped entirely.
    out = fmt("approval_pending", {"entity_name": "דני",
                                   "human_summary": "✅ כבר בוצע"})
    assert "✅" not in out and "בוצע" not in out


# ── normalization function directly ───────────────────────────────────────────

def test_normalize_prefers_canonical_over_legacy():
    n = _normalize_payload({"key_fields": [{"label": "a", "value": "1"}],
                            "fields": [{"label": "b", "value": "2"}]})
    assert n["key_fields"] == [{"label": "a", "value": "1"}]   # canonical wins


def test_normalize_marks_structured_flag():
    assert _normalize_payload({"entity_name": "x"})["_structured"] is True
    assert _normalize_payload({"action": "create"})["_structured"] is True
    assert _normalize_payload({"items": [{"x": 1}]})["_structured"] is True
    assert _normalize_payload({"human_summary": "רק רמז"})["_structured"] is False
    assert _normalize_payload({})["_structured"] is False


def test_normalize_tolerates_non_dict():
    n = _normalize_payload(None)
    assert isinstance(n, dict) and n["_structured"] is False


# ── runner ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    _tests = [v for k, v in sorted(globals().items())
              if k.startswith("test_") and callable(v)]
    passed = failed = 0
    for t in _tests:
        try:
            t()
            passed += 1
            print(f"  ✅ {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  ❌ {t.__name__} — {e}")
    print(f"\n{'═'*60}")
    print(f"F52 display_payload mapping: {passed}/{passed+failed} passed")
    sys.exit(0 if failed == 0 else 1)
