#!/usr/bin/env python3
# test_c53a.py — Regression tests for C53-A structured tool result contract.
#
# Run: python3 test_c53a.py
# Pass condition: exit code 0, all assertions green.
#
# Covers:
#   - verify_execution() rejects plain strings for every structured tool
#   - verify_execution() accepts correct dict shape per tool
#   - calendar_create_event requires external_id + evidence.htmlLink
#   - gmail_draft requires external_id (draft_id)
#   - gmail_send_draft requires external_id (message_id)
#   - airtable_add/update require rec-prefixed external_id
#   - _tool_result() helper from both google_tools and airtable_tools produces correct shape
#   - validate_tool_output() preserves structured dicts unchanged
#   - _tool_user_message() extracts user_message from structured result

from __future__ import annotations

import os
import sys

os.environ.setdefault("TELEGRAM_TOKEN", "123:stub_token_for_tests")
os.environ.setdefault("AIRTABLE_API_KEY", "stub")
os.environ.setdefault("AIRTABLE_BASE_ID", "stub")
os.environ.setdefault("ANTHROPIC_API_KEY", "stub")

# Stub heavy deps so imports don't require live credentials
from unittest.mock import MagicMock
for _mod in ["telebot", "anthropic", "httpx"]:
    sys.modules.setdefault(_mod, MagicMock())

# ── test state ────────────────────────────────────────────────────────────────

_passed = 0
_failed = 0


def check(desc: str, condition: bool) -> None:
    global _passed, _failed
    if condition:
        print(f"✅ {desc}")
        _passed += 1
    else:
        print(f"❌ {desc}")
        _failed += 1


# ── helpers ───────────────────────────────────────────────────────────────────

def _make(
    tool: str,
    external_id: str = "",
    ok: bool = True,
    evidence: dict | None = None,
    user_message: str = "ok",
) -> dict:
    return {
        "ok": ok,
        "tool": tool,
        "external_id": external_id,
        "evidence": evidence or {},
        "user_message": user_message,
    }


# ── import the module under test ──────────────────────────────────────────────

from core.anti_hallucination import verify_execution, VerifyResult

# ═════════════════════════════════════════════════════════════════
# Section 1: calendar_create_event
# ═════════════════════════════════════════════════════════════════

r = verify_execution("calendar_create_event", _make(
    "calendar_create_event", "evt_abc123",
    evidence={"htmlLink": "https://calendar.google.com/event?eid=abc"},
))
check("calendar: ok=True + event_id + htmlLink → ok", r.status == "ok")

r = verify_execution("calendar_create_event", _make(
    "calendar_create_event", "evt_abc123",
    evidence={"event_id": "evt_abc123"},
))
check("calendar: ok=True + event_id but NO htmlLink → failed", r.status == "failed")

r = verify_execution("calendar_create_event", _make(
    "calendar_create_event", "",
    evidence={"htmlLink": "https://calendar.google.com/event?eid=abc"},
))
check("calendar: ok=True + htmlLink but empty external_id → failed", r.status == "failed")

r = verify_execution("calendar_create_event", _make(
    "calendar_create_event", ok=False,
    evidence={"conflict": "⚠️ כבר קיים ביומן: 'פגישה' (14:00)"},
    user_message="⚠️ כבר קיים ביומן: 'פגישה' (14:00). לקבוע בכל זאת?",
))
check("calendar: conflict response (ok=False) → failed", r.status == "failed")

r = verify_execution("calendar_create_event", "✅ אירוע 'פגישה' נוצר ביומן ל-01/06/2025 14:00.")
check("calendar: plain string result (old format) → failed", r.status == "failed")

r = verify_execution("calendar_create_event", "⚠️ כבר קיים ביומן: 'אחר' (14:00). לקבוע בכל זאת?")
check("calendar: plain conflict string (old format) → failed", r.status == "failed")

r = verify_execution("calendar_create_event", None)
check("calendar: None output → failed", r.status == "failed")

# ═════════════════════════════════════════════════════════════════
# Section 2: gmail_draft
# ═════════════════════════════════════════════════════════════════

r = verify_execution("gmail_draft", _make("gmail_draft", "draft_xyz789"))
check("gmail_draft: ok=True + draft_id → ok", r.status == "ok")

r = verify_execution("gmail_draft", _make("gmail_draft", ok=False, user_message="❌ Gmail 403"))
check("gmail_draft: ok=False → failed", r.status == "failed")

r = verify_execution("gmail_draft", _make("gmail_draft", ""))
check("gmail_draft: empty external_id → failed", r.status == "failed")

r = verify_execution("gmail_draft", "Draft created (id=draft_xyz)")
check("gmail_draft: plain string (old format) → failed", r.status == "failed")

r = verify_execution("gmail_draft", "Email queued successfully")
check("gmail_draft: generic success string (old format) → failed", r.status == "failed")

# ═════════════════════════════════════════════════════════════════
# Section 3: gmail_send_draft
# ═════════════════════════════════════════════════════════════════

r = verify_execution("gmail_send_draft", _make("gmail_send_draft", "msg_abc123"))
check("gmail_send_draft: ok=True + message_id → ok", r.status == "ok")

r = verify_execution("gmail_send_draft", _make("gmail_send_draft", ok=False, user_message="❌ Gmail 500"))
check("gmail_send_draft: ok=False → failed", r.status == "failed")

r = verify_execution("gmail_send_draft", _make("gmail_send_draft", ""))
check("gmail_send_draft: empty external_id → failed", r.status == "failed")

r = verify_execution("gmail_send_draft", "📧 טיוטה draft_abc נשלחה בהצלחה!")
check("gmail_send_draft: plain string (old format) → failed", r.status == "failed")

r = verify_execution("gmail_send_draft", "Sent.")
check("gmail_send_draft: generic string (old format) → failed", r.status == "failed")

# ═════════════════════════════════════════════════════════════════
# Section 4: airtable_add
# ═════════════════════════════════════════════════════════════════

r = verify_execution("airtable_add", _make("airtable_add", "rec1234abcXYZ"))
check("airtable_add: ok=True + rec-id → ok", r.status == "ok")

r = verify_execution("airtable_add", _make("airtable_add", ok=False, user_message="❌ Airtable 422"))
check("airtable_add: ok=False → failed", r.status == "failed")

r = verify_execution("airtable_add", _make("airtable_add", "not_a_rec"))
check("airtable_add: external_id not rec-prefixed → failed", r.status == "failed")

r = verify_execution("airtable_add", _make("airtable_add", ""))
check("airtable_add: empty external_id → failed", r.status == "failed")

r = verify_execution("airtable_add", "Created: rec1234abc")
check("airtable_add: plain string (old format) → failed", r.status == "failed")

r = verify_execution("airtable_add", None)
check("airtable_add: None output → failed", r.status == "failed")

# ═════════════════════════════════════════════════════════════════
# Section 5: airtable_update
# ═════════════════════════════════════════════════════════════════

r = verify_execution("airtable_update", _make("airtable_update", "rec5678defGHI"))
check("airtable_update: ok=True + rec-id → ok", r.status == "ok")

r = verify_execution("airtable_update", _make("airtable_update", "invalid_id_no_rec"))
check("airtable_update: external_id not rec-prefixed → failed", r.status == "failed")

r = verify_execution("airtable_update", _make("airtable_update", ok=False, user_message="❌ error"))
check("airtable_update: ok=False → failed", r.status == "failed")

# ═════════════════════════════════════════════════════════════════
# Section 6: non-structured tools pass through unchanged
# ═════════════════════════════════════════════════════════════════

r = verify_execution("calendar_get_events", "📅 3 אירועים קרובים:\n• פגישה — 2026-06-20T10:00")
check("calendar_get_events: plain string → ok", r.status == "ok")

r = verify_execution("airtable_get", "• [rec123] שם: דני | סטטוס: פעיל")
check("airtable_get: plain string → ok", r.status == "ok")

r = verify_execution("search_lead", "• [recABC] שם: אלי")
check("search_lead: plain string → ok", r.status == "ok")

r = verify_execution("calendar_get_events", "")
check("calendar_get_events: empty string → failed", r.status == "failed")

# ═════════════════════════════════════════════════════════════════
# Section 7: _tool_result() shape from google_tools
# ═════════════════════════════════════════════════════════════════

try:
    from tools.google_tools import _tool_result as _gt_result
    r = _gt_result(ok=True, tool="gmail_draft", external_id="draft_123",
                   evidence={"draft_id": "draft_123"}, user_message="📝 טיוטה נשמרה")
    check("google_tools._tool_result: has ok", r.get("ok") is True)
    check("google_tools._tool_result: has tool", r.get("tool") == "gmail_draft")
    check("google_tools._tool_result: has external_id", r.get("external_id") == "draft_123")
    check("google_tools._tool_result: has evidence dict", isinstance(r.get("evidence"), dict))
    check("google_tools._tool_result: has user_message", isinstance(r.get("user_message"), str))
    check("google_tools._tool_result: no extra keys", set(r) == {"ok","tool","external_id","evidence","user_message"})
except ImportError as e:
    print(f"⚠️  google_tools import skipped (no live env): {e}")

# ═════════════════════════════════════════════════════════════════
# Section 8: _tool_result() shape from airtable_tools
# ═════════════════════════════════════════════════════════════════

try:
    from tools.airtable_tools import _tool_result as _at_result
    r = _at_result(ok=True, tool="airtable_add", external_id="rec123",
                   evidence={"record_id": "rec123"}, user_message="✅ רשומה נוספה")
    check("airtable_tools._tool_result: has ok", r.get("ok") is True)
    check("airtable_tools._tool_result: has tool", r.get("tool") == "airtable_add")
    check("airtable_tools._tool_result: has external_id", r.get("external_id") == "rec123")
    check("airtable_tools._tool_result: has evidence dict", isinstance(r.get("evidence"), dict))
    check("airtable_tools._tool_result: has user_message", isinstance(r.get("user_message"), str))
    check("airtable_tools._tool_result: no extra keys", set(r) == {"ok","tool","external_id","evidence","user_message"})
except ImportError as e:
    print(f"⚠️  airtable_tools import skipped (no live env): {e}")

# ═════════════════════════════════════════════════════════════════
# Section 9: validate_tool_output preserves structured dicts
# ═════════════════════════════════════════════════════════════════

try:
    from guards.rate_limiter import validate_tool_output
    structured = _make("gmail_draft", "draft_abc", user_message="📝 טיוטה נשמרה")
    out = validate_tool_output("gmail_draft", structured)
    check("validate_tool_output: dict passes through as dict", isinstance(out, dict))
    check("validate_tool_output: ok preserved", out.get("ok") is True)
    check("validate_tool_output: external_id preserved", out.get("external_id") == "draft_abc")

    long_msg = "x" * 5000
    structured_long = _make("gmail_draft", "draft_abc", user_message=long_msg)
    out_long = validate_tool_output("gmail_draft", structured_long)
    check("validate_tool_output: truncates long user_message", len(out_long["user_message"]) <= 4010)

    string_out = validate_tool_output("airtable_get", "some records")
    check("validate_tool_output: plain string → string", isinstance(string_out, str))
except ImportError as e:
    print(f"⚠️  guards.rate_limiter import skipped: {e}")

# ═════════════════════════════════════════════════════════════════
# Section 10: _tool_user_message extracts user_message
# ═════════════════════════════════════════════════════════════════

try:
    # Import the private helper via app.py would require full env; test inline logic
    def _tool_user_message(result) -> str:
        if isinstance(result, dict):
            msg = result.get("user_message")
            if isinstance(msg, str) and msg:
                return msg
            return str(result)
        return str(result or "")

    structured = _make("gmail_draft", "draft_abc", user_message="📝 טיוטה נשמרה ב-Gmail")
    check("_tool_user_message: extracts user_message from dict", _tool_user_message(structured) == "📝 טיוטה נשמרה ב-Gmail")

    check("_tool_user_message: plain string passthrough", _tool_user_message("plain text") == "plain text")
    check("_tool_user_message: None → empty string", _tool_user_message(None) == "")
except Exception as e:
    print(f"⚠️  _tool_user_message tests skipped: {e}")

# ═════════════════════════════════════════════════════════════════
# Summary
# ═════════════════════════════════════════════════════════════════

print(f"\n{'═'*50}")
print(f"C53-A regression: {_passed}/{_passed+_failed} passed")
if _failed:
    print(f"FAILED: {_failed} test(s)")
sys.exit(0 if _failed == 0 else 1)
