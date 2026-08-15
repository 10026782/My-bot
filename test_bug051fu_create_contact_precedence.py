# test_bug051fu_create_contact_precedence.py — BUG-051-FU
#
# Manual production QA (14/08/2026): "צור איש קשר רמי לוי 0547653453" sent by
# an internal (owner) sender. Router correctly classified
# intent=create_contact, confidence=0.90 — but LCH (core/lead_candidate_
# handler.handle_lead_candidate), gated only on identity.is_internal
# (BUG-051/PR#205 design), still saw a Tier-1 single_high_confidence lead
# candidate and proposed an airtable_add/Leads write, silently overriding
# the explicit Router intent.
#
# Fix: a closed set of explicit, lead-disjoint non-lead mutation intents
# (_NON_LEAD_MUTATION_INTENTS in core/lead_candidate_handler.py) now makes
# handle_lead_candidate() return None immediately for Tier 1-3 whenever the
# Router has confidently recognized one of them for this turn — the explicit
# intent owns the turn, LCH does not reinterpret it as a lead. Genuine lead
# dictation (no such intent, or intent=create_lead) is unaffected.

import os, sys
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:TEST")
os.environ.setdefault("AIRTABLE_API_KEY", "patTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

from unittest.mock import patch

import core.lead_candidate_handler as lch
from core.action_gateway import GatewayResult
from core.ingress_classifier import classify_ingress
from session_store import lead_sessions

passed = failed = 0


def chk(desc: str, cond: bool, extra: str = "") -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}{(' — ' + extra) if extra else ''}")
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


# ══════════════════════════════════════════════════
# 1. Production repro: create_contact must NOT become a Leads capture
# ══════════════════════════════════════════════════
print("── create_contact owns the turn — no Leads ActionContract proposed ──")

REPRO_TEXT = "צור איש קשר רמי לוי 0547653453"

_repro_ic = classify_ingress(REPRO_TEXT)
chk("T0: precondition — REPRO_TEXT actually classifies Tier 1-3 (the guard's "
    "own reachability gate; if this drifts to Tier 4/5 the suppression checks "
    "below would pass vacuously via the pre-existing Tier>=4 early-return)",
    _repro_ic.tier in (1, 2, 3), f"got tier={_repro_ic.tier} reason={_repro_ic.reason}")

with patch.object(lch, "_at_find_lead", return_value=None), \
     patch.object(lch, "_propose_lead_write", return_value=OK_RESULT) as propose_mock:
    reply = _send("contact1", REPRO_TEXT, intent="create_contact")

chk("T1: handle_lead_candidate returns None (falls through, does not own the turn)",
    reply is None, f"got reply={reply!r}")
chk("T2: no Leads write was ever proposed", not propose_mock.called)
chk("T3: no clarification/preview state was left dangling",
    _snap("contact1").get("active_lead_candidate") is None)


# ══════════════════════════════════════════════════
# 2. Positive control: a genuine lead is still captured (intent=create_lead)
# ══════════════════════════════════════════════════
print()
print("── Positive control: genuine create_lead intent still captured ──")

LEAD_TEXT = "משה כהן 0501234567 מעוניין בדירת 4 חדרים"

with patch.object(lch, "_at_find_lead", return_value=None), \
     patch.object(lch, "_propose_lead_write", return_value=OK_RESULT) as propose_mock:
    reply = _send("lead1", LEAD_TEXT, intent="create_lead")

chk("T4: a real lead with matching create_lead intent is still captured (Tier-1 preview)",
    isinstance(reply, str) and "משה כהן" in reply, f"got reply={reply!r}")
chk("T5: the write was actually proposed for the real lead", propose_mock.called)


# ══════════════════════════════════════════════════
# 3. Positive control: no intent at all (empty string) — unaffected
# ══════════════════════════════════════════════════
print()
print("── Positive control: no Router intent passed (empty string, back-compat) ──")

with patch.object(lch, "_at_find_lead", return_value=None), \
     patch.object(lch, "_propose_lead_write", return_value=OK_RESULT) as propose_mock:
    reply = _send("lead2", "דנה לוי 0521234567 רוצה לשמוע פרטים", intent="")

chk("T6: empty intent (back-compat callers) does not trigger the guard",
    isinstance(reply, str) and "דנה לוי" in reply, f"got reply={reply!r}")


# ══════════════════════════════════════════════════
# 4. Closed-set coverage: other explicit non-lead mutation intents
# ══════════════════════════════════════════════════
print()
print("── Closed-set coverage: other non-lead mutation intents also suppress capture ──")

_OTHER_MUTATION_CASES = [
    ("task1",  "צור משימה לבדוק חוזה עם רמי לוי 0547653453", "create_task"),
    ("event1", "קבע פגישה עם רמי לוי 0547653453 מחר",         "create_event"),
    ("email1", "כתוב מייל לרמי לוי 0547653453 בנושא הצעת מחיר", "draft_email"),
]

for chat_id, text, intent in _OTHER_MUTATION_CASES:
    _ic = classify_ingress(text)
    chk(f"T7[{intent}] precondition: text classifies Tier 1-3",
        _ic.tier in (1, 2, 3), f"got tier={_ic.tier} reason={_ic.reason}")
    with patch.object(lch, "_at_find_lead", return_value=None), \
         patch.object(lch, "_propose_lead_write", return_value=OK_RESULT) as propose_mock:
        reply = _send(chat_id, text, intent=intent)
    chk(f"T7[{intent}]: suppressed, no Leads write proposed",
        reply is None and not propose_mock.called,
        f"got reply={reply!r} propose_called={propose_mock.called}")


# ══════════════════════════════════════════════════
# 5. Deliberate exclusions: STORE_MEMORY / ADMIN_ACTION must NOT suppress
#    capture (see _NON_LEAD_MUTATION_INTENTS docstring for rationale — both
#    patterns overlap with genuine lead-save/business phrasing)
# ══════════════════════════════════════════════════
print()
print("── Deliberate exclusions: store_memory / admin_action still allow capture ──")

with patch.object(lch, "_at_find_lead", return_value=None), \
     patch.object(lch, "_propose_lead_write", return_value=OK_RESULT) as propose_mock:
    reply = _send("excl1", "שמור את המידע על יוסי לוי 0501112223", intent="store_memory")
chk("T8: store_memory does NOT suppress a genuine-looking lead save (excluded by design)",
    isinstance(reply, str), f"got reply={reply!r}")

with patch.object(lch, "_at_find_lead", return_value=None), \
     patch.object(lch, "_propose_lead_write", return_value=OK_RESULT) as propose_mock:
    reply = _send("excl2", "אבי גל 0501112224 מתעניין בניהול נכסים", intent="admin_action")
chk("T9: admin_action does NOT suppress a genuine-looking lead save (excluded by design)",
    isinstance(reply, str), f"got reply={reply!r}")


print(f"\n{'='*50}")
print(f"BUG-051-FU tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
