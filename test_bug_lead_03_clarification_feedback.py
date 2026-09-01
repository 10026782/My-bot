#!/usr/bin/env python3
"""
test_bug_lead_03_clarification_feedback.py — BUG-LEAD-03 (guided Lead
clarification gave no actionable feedback on a rejected name).

Live evidence (R10 bug report, 01/09/2026): when a supplied name was
rejected in the guided single-phone clarification flow, the bot's only
response was the generic "עדיין חסר לי שם הליד. מה השם?" — it never named
the rejected value, explained why it failed, or showed the accepted
format/example. Historical evidence (structured "ליד חדש | שם | טלפון"
parser, 23/08/2026) already established the UX principle this module
should follow on invalid input: name the bad value, explain briefly, show
the accepted format, give an example. This module's own sibling function,
_resolve_batch_name_clarification() (the 2+-phone batch case), already
quoted the rejected line — only the single-phone path lagged behind.

Fix: core/lead_candidate_handler.py::_resolve_lead_clarification()'s
unclear-reply branch (single-phone case) now quotes the rejected value and
states the accepted format with an example, instead of the generic re-ask.
No change to WHEN a reply is accepted/rejected (see BUG-LEAD-02 for that) —
only the wording of the re-ask when a reply IS rejected.
"""

from __future__ import annotations

import os

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:TEST")
os.environ.setdefault("AIRTABLE_API_KEY", "patTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

from unittest.mock import patch

import core.lead_candidate_handler as lch
from session_store import lead_sessions

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


class MockIdentity:
    is_internal = True
    tenant_id   = "boss_hq"
    memory_key  = "boss_hq/eliyahu@owner"
    domain_id   = "general"
    role        = "owner"


identity = MockIdentity()


def _snap(chat_id: str) -> dict:
    return lead_sessions.get_or_create(chat_id)


def _send(chat_id: str, text: str, intent: str = "") -> "str | None":
    return lch.handle_lead_candidate(
        identity, text, chat_id, "telegram", intent=intent, session=_snap(chat_id),
    )


def _start(chat_id: str, phone_text: str):
    with patch.object(lch, "_at_find_lead", return_value=None):
        return _send(chat_id, phone_text, intent="create_lead")


def _expected(rejected_value: str) -> str:
    return (
        f"'{rejected_value}' לא נראה כמו שם תקין. שם ליד צריך להיות מילה "
        f"אחת או שתיים בעברית (לדוגמה: \"דולב\" או \"יוסי כהן\"). מה שם הליד?"
    )


# ══════════════════════════════════════════════════════════════════
print("── Rejected replies now name the value + show format/example ──")

cases = {
    "stop-word (chat noise)":        "כן",
    "stop-word (property term)":     "בקומה",
    "3-word sentence (false positive guard)": "נדבר אחר כך",
    "Latin name (out of Hebrew-only scope)":  "Jenya",
}

for i, (label, value) in enumerate(cases.items()):
    c = f"bug_lead_03_{i}"
    _start(c, f"צור ליד חדש טלפון 050000000{i}")
    reply = _send(c, value)
    chk(f"{label}: reply quotes '{value}' and shows format/example",
        reply == _expected(value))
    chk(f"{label}: state stays needs_clarification (still re-asking, not dropped)",
        _snap(c).get("active_lead_candidate", {}).get("state") == "needs_clarification")


# ══════════════════════════════════════════════════════════════════
print("\n── Control: a VALID reply is unaffected — no feedback wording, "
      "normal preview ──")

from core.action_gateway import GatewayResult
OK_RESULT = GatewayResult(ok=True, reason="", contract_id="c1", user_message="")

c = "bug_lead_03_valid"
_start(c, "צור ליד חדש טלפון 0501234567")
with patch.object(lch, "_at_find_lead", return_value=None), \
     patch.object(lch, "_propose_lead_write", return_value=OK_RESULT):
    reply_valid = _send(c, "יוסי כהן")
chk("a valid two-word name reply gets the normal lead preview, not "
    "feedback wording",
    reply_valid == "📋 זיהיתי ליד: יוסי כהן (0501234567)\nלשמור? ענה כן לאישור או לא לביטול.")


print()
print("=" * 50)
print(f"BUG-LEAD-03 (clarification feedback) tests: {passed} passed, {failed} failed")
if failed:
    raise SystemExit(1)
