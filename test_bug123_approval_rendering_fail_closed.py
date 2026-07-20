#!/usr/bin/env python3
"""
test_bug123_approval_rendering_fail_closed.py — BUG-123 regression suite
(approval message rendering).

Observed in staging: "⏳ בקשת אישור\\n➕ הוסף ל-?:\\nID: eeefa1d6 | פג תוקף
בעוד 10 דקות" — the user could not tell what they were being asked to
approve. Three concrete problems, all from the same root cause
(app._describe_tool_call()'s inputs.get("table", "?") fallback and friends):

  1. Missing business description ("הוסף ל-?:" — a broken placeholder).
  2. A technical short ID (contract_id) visible in user-facing text.
  3. The user cannot understand what they're approving from either of the
     above.

Fix: app._describe_tool_call() and event_bus._default_label() now fail
closed — a fixed, honest "couldn't build a clear description, please
restate" message — instead of interpolating a raw "?" placeholder when
required business fields (table/fields/summary/sheet_name) are missing.
Raw contract IDs, record IDs, and tool names are never shown in user-facing
text (callback_data is the only place technical identifiers belong) —
app._legacy_pending_text and event_bus's analogous label builder were both
audited and fixed the same way.

Scope: approval message rendering only. No RP5/F52 enforcement change, no
approval execution logic change.
"""

from __future__ import annotations

import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-bug122-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:BUG122_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patBug122Test")
os.environ.setdefault("AIRTABLE_BASE_ID", "appBug122Test")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import app  # noqa: E402  (env vars above must be set before import)
import event_bus  # noqa: E402

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


# ══════════════════════════════════════════════════
# app._describe_tool_call — fail-closed fallback
# ══════════════════════════════════════════════════

print("── app._describe_tool_call: fail-closed fallback ───────")

# The exact live-incident shape: airtable_add with no "table" key at all.
desc_no_table = app._describe_tool_call("airtable_add", {"fields": {"Name": "x"}})
chk('airtable_add missing "table" -> fail-closed fallback, not "הוסף ל-?:"',
    desc_no_table == app._APPROVAL_DESCRIPTION_FALLBACK)
chk('fail-closed fallback never contains a bare "?" placeholder',
    "?" not in app._APPROVAL_DESCRIPTION_FALLBACK)

desc_no_fields = app._describe_tool_call("airtable_add", {"table": "Leads"})
chk("airtable_add missing fields dict entirely -> fail-closed fallback",
    desc_no_fields == app._APPROVAL_DESCRIPTION_FALLBACK)

desc_empty_fields = app._describe_tool_call("airtable_add", {"table": "Leads", "fields": {}})
chk("airtable_add with an empty fields dict -> fail-closed fallback",
    desc_empty_fields == app._APPROVAL_DESCRIPTION_FALLBACK)

desc_update_no_table = app._describe_tool_call(
    "airtable_update", {"record_id": "recABC123", "fields": {"status": "hot"}},
)
chk("airtable_update missing table -> fail-closed fallback",
    desc_update_no_table == app._APPROVAL_DESCRIPTION_FALLBACK)

desc_cal_no_summary = app._describe_tool_call("calendar_create_event", {"start_time": "2026-07-15T10:00:00"})
chk("calendar_create_event missing summary -> fail-closed fallback",
    desc_cal_no_summary == app._APPROVAL_DESCRIPTION_FALLBACK)

desc_sheets_no_name = app._describe_tool_call("sheets_append", {})
chk("sheets_append missing sheet_name -> fail-closed fallback",
    desc_sheets_no_name == app._APPROVAL_DESCRIPTION_FALLBACK)

desc_unknown_tool = app._describe_tool_call("some_future_tool_nobody_registered_yet", {"a": 1, "b": 2})
chk("unknown/uncovered tool -> fail-closed fallback (never leaks tool_name or inputs repr)",
    desc_unknown_tool == app._APPROVAL_DESCRIPTION_FALLBACK)


# ══════════════════════════════════════════════════
# app._describe_tool_call — no raw technical identifiers, ever
# ══════════════════════════════════════════════════

print("\n── app._describe_tool_call: no raw identifiers ─────────")

desc_update_ok = app._describe_tool_call(
    "airtable_update",
    {"table": "Leads", "record_id": "recABC123", "fields": {"status": "hot", "Score": 90}},
)
chk("airtable_update: raw record_id never shown, even with a valid description",
    "recABC123" not in desc_update_ok)
chk("airtable_update: the actual changed fields are still shown (business content)",
    "status: hot" in desc_update_ok and "Score: 90" in desc_update_ok)

desc_gmail = app._describe_tool_call("gmail_send_draft", {"draft_id": "d123"})
chk("gmail_send_draft: raw draft_id never shown", "d123" not in desc_gmail)


# ══════════════════════════════════════════════════
# event_bus._default_label — analogous fail-closed behavior
# ══════════════════════════════════════════════════

print("\n── event_bus._default_label: fail-closed fallback ──────")

chk('airtable_add missing "table" -> fail-closed fallback (event_bus)',
    event_bus._default_label("airtable_add", {"fields": {"Name": "x"}})
    == event_bus._DEFAULT_LABEL_FALLBACK)

chk("calendar_create_event missing summary -> fail-closed fallback (event_bus)",
    event_bus._default_label("calendar_create_event", {}) == event_bus._DEFAULT_LABEL_FALLBACK)

chk("sheets_append missing sheet_name -> fail-closed fallback (event_bus)",
    event_bus._default_label("sheets_append", {}) == event_bus._DEFAULT_LABEL_FALLBACK)

chk("unknown action -> fail-closed fallback (event_bus), never the raw action string",
    event_bus._default_label("some_unregistered_action", {"x": 1})
    == event_bus._DEFAULT_LABEL_FALLBACK)

chk("airtable_add with a real table -> real business label, not the fallback",
    event_bus._default_label("airtable_add", {"table": "Leads"}) == "➕ הוסף ל-Leads")

chk("gmail_send_draft with a recipient -> real business label including the recipient",
    event_bus._default_label("gmail_send_draft", {"to": "dani@example.com"})
    == "📧 שלח מייל ל-dani@example.com")


# ══════════════════════════════════════════════════
# app._legacy_pending_text — no raw contract/action_id in visible text
# (static source check: the live prompt-building code path requires a real
# telebot bot + owner chat id + ActionGateway wiring to exercise end-to-end;
# the f-string template itself is what BUG-123-FU changed, so this asserts
# directly on that template rather than reconstructing the whole send flow)
# ══════════════════════════════════════════════════

print("\n── app._legacy_pending_text template: no raw action_id ─")

_src = inspect.getsource(app)
_template_line = next(
    (line for line in _src.splitlines() if "_legacy_pending_text = f" in line), None,
)
chk("_legacy_pending_text template found in app.py", _template_line is not None)
if _template_line is not None:
    chk('_legacy_pending_text template no longer interpolates "{action_id}"',
        "{action_id}" not in _template_line)
    chk('_legacy_pending_text template still shows the expiry countdown',
        "פג תוקף" in _template_line)


# ══════════════════════════════════════════════════
# Summary
# ══════════════════════════════════════════════════

print(f"\n{'='*40}")
print(f"  {passed}/{passed+failed} passed")
if failed:
    print(f"  {failed} FAILED")
    sys.exit(1)
else:
    print("  All OK ✅")
