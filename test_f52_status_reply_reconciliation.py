#!/usr/bin/env python3
# test_f52_status_reply_reconciliation.py
# F52 — Unified Approval Runtime · compose_status_reply / format_agent_message
# reconciliation (FEATURE_UNIFIED_STATUS_FORMATTER).
#
# Run: python3 test_f52_status_reply_reconciliation.py  (or via pytest)
#
# Proves:
#   - off    : legacy status text is byte-identical to before F52.
#   - shadow : legacy text is still sent (unified only logged).
#   - on     : the single canonical formatter renders the text; no record_id /
#              tool_name leaks; failure codes map to human text; rejection is a
#              failure-family variant; unknown outcome is never success.
#   - a formatter exception never breaks the live path (falls back to legacy).
#   - compose_status_reply remains the single status-text entry point.

from __future__ import annotations

import os
import sys
import types

from core.action_gateway import ActionGateway, ActionFact, _LEAD_CAPTURE_TABLE
from airtable_schema import LeadFields


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
        assert gw.compose_status_reply(F_EXEC).text == \
            "✅ בוצע: יצירת ליד: דני כהן, 0501234567, real_estate | מזהה: `recABC1234567890XYZ`"
        assert gw.compose_status_reply(F_FAIL).text == "❌ נכשל: gmail_send_draft (GOOGLE_AUTH_REQUIRED)"
        assert gw.compose_status_reply(F_PEND).text == "⏳ ממתין לאישור: airtable_add"
        assert gw.compose_status_reply(F_REJ).text == "⚠️ נדחה: airtable_add"
    finally:
        _set(None)


def test_unset_and_unknown_flag_fail_closed_to_off():
    gw = _gw_with_lead_contract()
    try:
        _set(None)
        assert gw.compose_status_reply(F_PEND).text == "⏳ ממתין לאישור: airtable_add"
        _set("banana")
        assert gw.compose_status_reply(F_PEND).text == "⏳ ממתין לאישור: airtable_add"
    finally:
        _set(None)


# ── 2. shadow = legacy sent, unified only computed/logged ─────────────────────

def test_shadow_still_sends_legacy_text():
    gw = _gw_with_lead_contract()
    try:
        _set("shadow")
        assert gw.compose_status_reply(F_EXEC).text.startswith("✅ בוצע:")
    finally:
        _set(None)


# ── 3. on = unified formatter, no leaks ───────────────────────────────────────

def test_on_success_uses_business_label_no_leaks():
    gw = _gw_with_lead_contract()
    try:
        _set("on")
        out = gw.compose_status_reply(F_EXEC).text
        assert "recABC1234567890XYZ" not in out       # record id dropped
        assert "airtable_add" not in out               # tool name dropped
        assert "דני כהן" in out and "0501234567" in out
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
        assert "✓" not in rej and "airtable_add" not in rej and "נדחת" in rej   # failure-family
        unk = gw.compose_status_reply(F_UNK).text
        assert unk and "✓" not in unk and "✅" not in unk                        # never success
    finally:
        _set(None)


# ── 4. formatter exception never breaks the live path ─────────────────────────

def test_formatter_exception_falls_back_to_legacy():
    gw = _gw_with_lead_contract()
    import core.agent_message_formatter as amf
    orig = amf.format_agent_message
    try:
        _set("on")
        amf.format_agent_message = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
        assert gw.compose_status_reply(F_PEND).text == "⏳ ממתין לאישור: airtable_add"
    finally:
        amf.format_agent_message = orig
        _set(None)


# ── 5. single entry point ─────────────────────────────────────────────────────

def test_single_status_text_entry_point():
    assert callable(getattr(ActionGateway, "compose_status_reply", None))
    assert callable(getattr(ActionGateway, "_compose_status_reply_legacy", None))
    assert callable(getattr(ActionGateway, "_compose_status_reply_unified", None))


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
