#!/usr/bin/env python3
"""
test_preview_content_fix.py — SPEC Preview Content Fix (Sites #3 + #4)

מאמת:
1. _describe_tool_call (Site #3): airtable_add/airtable_update מציגים שדות
   וערכים אמיתיים, שדות רגישים (כולל שדות בעברית שנמצאו ב-Contract Chain —
   "טלפון"/"אימייל") ממוסכים, ערכים ארוכים נחתכים, שאר הכלים ללא שינוי.
2. approval_response (Site #4): ה-preview כולל את CONFIRMATION_SUFFIX,
   ואחסון ה-pending entry (טקסט/domain/channel) ללא שינוי.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-preview-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:PREVIEW_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patPreviewTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appPreviewTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import app  # noqa: E402  (env vars above must be set before import)
from core.router.route_decision import RouteDecision, Intent, RouterDomain, Risk, Handler  # noqa: E402

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


# ══════════════════════════════════════════════════════════════════
# Site #3 — _describe_tool_call / _format_field_value
# ══════════════════════════════════════════════════════════════════

print("\n── Site #3: _describe_tool_call ────────────────────────")

# Test 1: airtable_add with 3 regular fields → all shown with values
desc = app._describe_tool_call("airtable_add", {
    "table": "Leads",
    "fields": {"Name": "דני כהן", "status": "new", "source": "whatsapp"},
})
chk("airtable_add: field 1 (Name) shown with value", "Name: דני כהן" in desc)
chk("airtable_add: field 2 (status) shown with value", "status: new" in desc)
chk("airtable_add: field 3 (source) shown with value", "source: whatsapp" in desc)

# Test 2: airtable_add with English "phone" field → masked (8-char value
# matches the SPEC's own worked example: "05" + 4 stars + "54")
desc = app._describe_tool_call("airtable_add", {
    "table": "Leads",
    "fields": {"phone": "05123454"},
})
chk('airtable_add: "phone" masked to 05****54', "05****54" in desc)
chk('airtable_add: raw phone value not leaked', "05123454" not in desc)

# Test 2b (Contract Chain finding): Hebrew-named phone/email fields on the
# Contacts table ("טלפון"/"אימייל", ContactFields) must ALSO be masked —
# the original 4-key English-only list would have missed these entirely.
desc = app._describe_tool_call("airtable_add", {
    "table": "אנשי קשר (Contacts)",
    "fields": {"טלפון": "05123454", "אימייל": "d@example.com"},
})
chk('airtable_add: Hebrew "טלפון" field masked', "05123454" not in desc and "*" in desc)
chk('airtable_add: Hebrew "אימייל" field masked', "d@example.com" not in desc)

# Test 3: long value (>80 chars) truncated
long_val = "א" * 100
desc = app._describe_tool_call("airtable_add", {
    "table": "Leads",
    "fields": {"summary": long_val},
})
chk("airtable_add: long value truncated with '...'", desc.count("א") == 80 and desc.endswith("...\n") is False and "..." in desc)

# Test 4: airtable_update with changing fields → shown (regression: was empty before)
desc = app._describe_tool_call("airtable_update", {
    "table": "Leads",
    "record_id": "recABC123",
    "fields": {"status": "hot", "Score": 90},
})
# BUG-123-FU: raw Airtable record_id must NOT appear in user-facing text
# (technical identifiers belong only in callback_data) — this was
# intentionally changed by the approval-message-rendering fix.
chk("airtable_update: record_id no longer shown (BUG-123-FU)", "recABC123" not in desc)
chk("airtable_update: changed field 'status' shown with value", "status: hot" in desc)
chk("airtable_update: changed field 'Score' shown with value", "Score: 90" in desc)

# Test 4b (Contract Chain finding — action_validator param-shape defense):
# fields present but not a dict must not crash _describe_tool_call.
try:
    desc = app._describe_tool_call("airtable_update", {
        "table": "Leads", "record_id": "recXYZ", "fields": "not-a-dict",
    })
    chk("airtable_update: non-dict 'fields' does not crash", True)
except Exception as e:
    chk(f"airtable_update: non-dict 'fields' does not crash (raised {e!r})", False)

try:
    desc = app._describe_tool_call("airtable_add", {
        "table": "Leads", "fields": ["not", "a", "dict"],
    })
    chk("airtable_add: non-dict 'fields' does not crash", True)
except Exception as e:
    chk(f"airtable_add: non-dict 'fields' does not crash (raised {e!r})", False)

# Test 5: regression — gmail_send_draft / calendar_create_event / sheets_append unchanged
# BUG-123-FU: draft_id is a raw internal identifier — no longer shown in
# user-facing approval text (was "📧 שלח מייל (draft: d123)" before the fix).
chk(
    "gmail_send_draft: no raw draft_id shown (BUG-123-FU)",
    app._describe_tool_call("gmail_send_draft", {"draft_id": "d123"})
    == "📧 שלח מייל",
)
chk(
    "calendar_create_event unchanged",
    app._describe_tool_call(
        "calendar_create_event",
        {"summary": "פגישה", "start_time": "2026-07-15T10:00:00"},
    ) == "📅 קבע: פגישה ב-2026-07-15T10:00",
)
chk(
    "sheets_append unchanged",
    app._describe_tool_call("sheets_append", {"sheet_name": "Sheet1"})
    == "📊 כתוב ל-Sheet1",
)


# ══════════════════════════════════════════════════════════════════
# Site #4 — approval_response CONFIRMATION_SUFFIX
# ══════════════════════════════════════════════════════════════════

print("\n── Site #4: approval_response ──────────────────────────")

_route = RouteDecision(
    channel="telegram", intent=Intent.SEND_EMAIL, domain=RouterDomain.GENERAL,
    risk=Risk.NEEDS_APPROVAL, handler=Handler.APPROVAL, needs_approval=True,
    confidence=0.9, matched_rule="test", response_override="",
)

_chat_id = "test-preview-suffix-chat"
with app._pending_approvals_lock:
    app._pending_approvals.pop(_chat_id, None)

reply = app.approval_response(_route, "שלח מייל לדני על הפגישה", _chat_id, "telegram", "general")

chk("approval_response: reply includes CONFIRMATION_SUFFIX", app.CONFIRMATION_SUFFIX in reply)
chk("approval_response: original preview text still present", "שלח מייל לדני על הפגישה" in reply)
chk("approval_response: confirm/cancel instructions still present", "כן" in reply and "לא" in reply)

# storage regression: pending entry still holds raw text/channel/domain, unchanged shape
with app._pending_approvals_lock:
    bucket = app._pending_approvals.get(_chat_id, {})
    chk("approval_response: exactly one pending entry stored", len(bucket) == 1)
    entry = next(iter(bucket.values())) if bucket else {}
    chk("approval_response: stored entry text unchanged", entry.get("text") == "שלח מייל לדני על הפגישה")
    chk("approval_response: stored entry domain unchanged", entry.get("domain") == "general")
    chk("approval_response: stored entry channel unchanged", entry.get("channel") == "telegram")
    app._pending_approvals.pop(_chat_id, None)


# ══════════════════════════════════════════════════════════════════
# Summary
# ══════════════════════════════════════════════════════════════════

print(f"\n{'='*40}")
print(f"  {passed}/{passed+failed} passed")
if failed:
    print(f"  {failed} FAILED")
    sys.exit(1)
else:
    print("  All OK ✅")
