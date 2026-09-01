#!/usr/bin/env python3
"""
test_bug_lead_02_single_word_name_clarification.py — BUG-LEAD-02
(guided Lead-capture clarification rejected a legitimate single-word Hebrew
name, inconsistent with every other live Lead-name entry path).

Live evidence (R10 bug report, 01/09/2026): after the bot asked "אבל לא
מצאתי שם. מה שם הליד?", replying with a single Hebrew given name ("דולב",
"יבגני") was rejected with "עדיין חסר לי שם הליד. מה השם?" — the user had
to add a (sometimes fabricated) second word before the lead was accepted.
Historical evidence (structured "ליד חדש | שם | טלפון" parser, 23/08/2026)
already proved a single Hebrew name ("סרגי") is a legitimate, acceptable
lead name; core/lead_service.py::set_draft_field() (the Lead Draft flow)
accepts any non-empty name with no word-count or charset restriction at
all. Only this one flow — the needs_clarification reply resolver — imposed
an undocumented "exactly 2 words" requirement.

Root cause: core/lead_candidate_handler.py::_validate_clarification_name()
required an exact-2-words fullmatch against _HEBREW_NAME_RE, which itself
only matches 2+ space-separated Hebrew groups — a single Hebrew word never
matched at all, regardless of content.

Fix: accept 1 or 2 Hebrew words (still never 3+, preserving the original
false-positive guard against a full Hebrew sentence like "נדבר אחר כך"
being misread as a name), reusing the already-existing _HEBREW_WORD_RE
single-word matcher. The stop-word check (_is_name_stop_token) is
unchanged, so single-token chat noise ("כן", "לא", "תודה") remains
rejected — proven below.

Out of scope (explicitly NOT fixed by this test/change): non-Hebrew-script
(Latin) names ("Jenya Bondorenko", "Karen Avanisyan") — a separate, larger
scope decision, unrelated to the word-count defect this file proves.
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
from core.action_gateway import GatewayResult
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
OK_RESULT = GatewayResult(ok=True, reason="", contract_id="c1", user_message="")


def _snap(chat_id: str) -> dict:
    return lead_sessions.get_or_create(chat_id)


def _send(chat_id: str, text: str, intent: str = "") -> "str | None":
    return lch.handle_lead_candidate(
        identity, text, chat_id, "telegram", intent=intent, session=_snap(chat_id),
    )


def _start(chat_id: str, phone_text: str):
    with patch.object(lch, "_at_find_lead", return_value=None):
        return _send(chat_id, phone_text, intent="create_lead")


# ══════════════════════════════════════════════════════════════════
print("── Unit: _validate_clarification_name() directly ──")

chk("single Hebrew word ACCEPTED (live failure case: דולב)",
    lch._validate_clarification_name("דולב") == "דולב")
chk("single Hebrew word ACCEPTED (live failure case: יבגני)",
    lch._validate_clarification_name("יבגני") == "יבגני")
chk("single Hebrew word ACCEPTED (historical proven case: סרגי)",
    lch._validate_clarification_name("סרגי") == "סרגי")
chk("two Hebrew words still ACCEPTED (unchanged existing behavior)",
    lch._validate_clarification_name("יוסי כהן") == "יוסי כהן")
chk("two Hebrew words still ACCEPTED (live success case: גיא וולושין)",
    lch._validate_clarification_name("גיא וולושין") == "גיא וולושין")

print("\n── Negative: guardrails against false positives are unchanged ──")
chk("single stop-word 'כן' still REJECTED (not treated as a name)",
    lch._validate_clarification_name("כן") is None)
chk("single stop-word 'לא' still REJECTED",
    lch._validate_clarification_name("לא") is None)
chk("single-letter Hebrew token REJECTED (below _HEBREW_WORD_RE's 2-char minimum)",
    lch._validate_clarification_name("ב") is None)
chk("3-word Hebrew sentence still REJECTED (BUG-099's original false-positive guard)",
    lch._validate_clarification_name("נדבר אחר כך") is None)
chk("empty string REJECTED",
    lch._validate_clarification_name("") is None)
chk("stop-word pair REJECTED ('בקומה חמישית' — property description, not a name)",
    lch._validate_clarification_name("בקומה חמישית") is None)
chk("Latin single word still REJECTED (out of scope for this fix, unchanged)",
    lch._validate_clarification_name("Dolev") is None)


# ══════════════════════════════════════════════════════════════════
print("\n── End-to-end: single Hebrew name completes the real clarification flow ──")

c = "bug_lead_02_e2e"
reply1 = _start(c, "צור ליד חדש טלפון 0524863292")
chk("T1: bot asks for the missing name",
    isinstance(reply1, str) and "לא מצאתי שם" in reply1)

with patch.object(lch, "_at_find_lead", return_value=None), \
     patch.object(lch, "_propose_lead_write", return_value=OK_RESULT) as propose_mock:
    reply2 = _send(c, "דולב")

chk("T2: single-word reply 'דולב' resolves to the standard lead preview "
    "(previously stuck asking again)",
    reply2 == "📋 זיהיתי ליד: דולב (0524863292)\nלשמור? ענה כן לאישור או לא לביטול.")
chk("T3: _propose_lead_write was actually called with the single-word name",
    propose_mock.call_count == 1 and propose_mock.call_args.args[1] == "דולב")

snap_after = _snap(c)
chk("T4: clarification state cleared after successful resolution",
    snap_after.get("active_lead_candidate") is None
    or snap_after["active_lead_candidate"].get("state") != "needs_clarification")


# ══════════════════════════════════════════════════════════════════
print("\n── End-to-end: an unclear single-token reply still re-asks (regression guard) ──")

c2 = "bug_lead_02_unclear"
_start(c2, "צור ליד חדש טלפון 0587041554")
reply_unclear = _send(c2, "כן")
chk("T5: a stop-word reply ('כן') does NOT get accepted as a name — bot asks again",
    reply_unclear == "עדיין חסר לי שם הליד. מה השם?")


print()
print("=" * 50)
print(f"BUG-LEAD-02 (single-word name clarification) tests: {passed} passed, {failed} failed")
if failed:
    raise SystemExit(1)
