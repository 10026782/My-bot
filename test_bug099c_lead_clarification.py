# test_bug099c_lead_clarification.py — BUG-099c (clarification instead of
# denial when a create_lead request is missing the name)
#
# Production evidence (12/07/2026, same log that verified BUG-099b.1):
#   "צור ליד חדש מעוניין בדירת 4 חדרים בקומה חמישית טלפון 0501234571"
#   -> Router: intent=create_lead confidence=0.95
#   -> LCH: Tier 5, no_lead_candidates, correctly skips (BUG-099b.1 fixed)
#   -> falls through to DeterministicDenial, which returns the generic
#      "יצירת ליד חדש ידנית דרך הצ׳אט חסומה כרגע" — WRONG: the system
#      understood the request perfectly, it's just missing one field. That
#      is not the same thing as a denied/blocked request.
#
# Fix: when Tier 5/no_lead_candidates + Router confirms Intent.CREATE_LEAD
# + a phone number IS present in the text, ask for the missing name instead
# of falling through to the denial gate. State lives in session_store's
# EXISTING active_lead_candidate key (BUG-106 made cross-message session
# selection deterministic — a prerequisite this flow depends on), extended
# with a distinct {"state": "needs_clarification"} shape that never
# conflicts with the pre-existing post-write bookmark shape (which has zero
# live readers today).
#
# LL-11 (test_session_snapshot.py): Sessions may be read exactly once per
# request. handle_lead_candidate()'s `session` parameter carries the
# caller's ALREADY-LOADED snapshot (app.py's run_agent() loads it once and
# threads it through) — every call below fetches its own snapshot the same
# way app.py would (lead_sessions.get_or_create/.get BEFORE calling
# handle_lead_candidate, never from inside it) to mirror the real flow
# instead of letting handle_lead_candidate() re-read Sessions itself.
#
# Leads-specific fix only — BUG-104 (general Understanding Layer /
# ReasoningEntity, see BUG_AUDIT_LOG.md) remains open as a separate
# architecture decision. A future BUG-104 implementation may refactor this
# flow without invalidating its correctness.

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

FIRST_MESSAGE = "צור ליד חדש מעוניין בדירת 4 חדרים בקומה חמישית טלפון 0501234571"
OK_RESULT = GatewayResult(ok=True, reason="", contract_id="c1", user_message="")


def _snap(chat_id: str) -> dict:
    """Loads the session snapshot exactly the way app.py's run_agent() does
    (ONE read, passed explicitly) — never call this from inside LCH itself."""
    return lead_sessions.get_or_create(chat_id)


def _send(chat_id: str, text: str, intent: str = "") -> "str | None":
    return lch.handle_lead_candidate(
        identity, text, chat_id, "telegram", intent=intent, session=_snap(chat_id),
    )


def _start(chat_id: str):
    with patch.object(lch, "_at_find_lead", return_value=None):
        return _send(chat_id, FIRST_MESSAGE, intent="create_lead")


# ── Happy path ─────────────────────────────────────────────────────────────
print("── Happy path: two messages, one preview, correct payload ──")

c = "happy"
reply1 = _start(c)
chk("T1: first message asks for the missing name, exact wording",
    reply1 == "זיהיתי בקשה ליצור ליד ואת מספר הטלפון 0501234571, אבל לא מצאתי שם. מה שם הליד?")
snap = _snap(c)
chk("T2: no ActionContract yet — active_lead_candidate is a clarification, not resolved",
    snap.get("active_lead_candidate") is not None
    and snap["active_lead_candidate"].get("state") == "needs_clarification")

with patch.object(lch, "_at_find_lead", return_value=None), \
     patch.object(lch, "_propose_lead_write", return_value=OK_RESULT) as propose_mock:
    reply2 = _send(c, "יוסי כהן")

chk("T3: second message returns the standard single-lead preview",
    reply2 == "📋 זיהיתי ליד: *יוסי כהן* (0501234571)\nלשמור? ענה *כן* לאישור או *לא* לביטול.")
chk("T4: the ORIGINAL first message (with phone+summary) is what gets proposed as the "
    "write payload's text, not the bare name reply — the interest/summary is not lost",
    propose_mock.call_args.args[0] is identity
    and propose_mock.call_args.args[1] == "יוסי כהן"
    and propose_mock.call_args.args[2] == "0501234571"
    and propose_mock.call_args.args[3] == FIRST_MESSAGE)
chk("T5: clarification state cleared only after propose_action() succeeded",
    _snap(c).get("active_lead_candidate") is None)


# ── Cancellation ────────────────────────────────────────────────────────────
print()
print("── Cancellation ──")

c = "cancel"
_start(c)
reply = _send(c, "לא")
chk("T6: cancellation returns the exact expected message", reply == "ביטלתי את יצירת הליד.")
chk("T7: state cleared, no lead created", _snap(c).get("active_lead_candidate") is None)


# ── TTL expiry ───────────────────────────────────────────────────────────────
print()
print("── TTL expiry ──")

c = "ttl"
_start(c)
sess = lead_sessions.get(c)
sess["active_lead_candidate"]["set_at"] -= 2000  # force >1800s expiry
reply = _send(c, "יוסי כהן")
chk("T8: after TTL expiry, a bare name reply is NOT swallowed as the answer "
    "(falls through to normal routing instead — a bare name with no phone "
    "resolves to Tier 5/None through the ordinary pipeline)",
    reply is None)
chk("T9: expired state is actually gone (not just skipped this one time)",
    _snap(c).get("active_lead_candidate") is None)


# ── Explicit new command interrupts the pending clarification ──────────────
print()
print("── New command interruption ──")

c = "newcmd"
_start(c)
reply = _send(c, "צור משימה לבדוק חוזה מחר", intent="create_task")
chk("T10: a real, different intent is not swallowed as a name reply "
    "(no lead named 'צור משימה...')", reply is None)
chk("T11: the stale clarification is cleared, not left dangling",
    _snap(c).get("active_lead_candidate") is None)


# ── Unclear reply ────────────────────────────────────────────────────────────
print()
print("── Unclear reply — not a cancel, not a new command, not a valid name ──")

c = "unclear"
_start(c)
reply = _send(c, "נדבר אחר כך")
chk("T12: unclear reply gets the exact re-ask message",
    reply == "עדיין חסר לי שם הליד. מה השם?")
snap = _snap(c)
chk("T13: 'נדבר אחר כך' is NOT saved as a name (would be a 3-word false positive "
    "on a plain stop-word blocklist check)",
    snap.get("active_lead_candidate") is not None
    and snap["active_lead_candidate"].get("state") == "needs_clarification")


# ── Invalid name: "בקומה" itself ────────────────────────────────────────────
print()
print("── Invalid name reply (the BUG-099b.1 stop-word itself) ──")

c = "invalidname"
_start(c)
reply = _send(c, "בקומה")
chk("T14: 'בקומה' is rejected as a name, asks again", reply == "עדיין חסר לי שם הליד. מה השם?")
chk("T15: state still pending", _snap(c).get("active_lead_candidate") is not None)


# ── ActionGateway failure keeps state alive, no false success ──────────────
print()
print("── ActionGateway propose_action() failure ──")

c = "gwfail"
_start(c)
fail_result = GatewayResult(ok=False, reason="duplicate_pending", contract_id="",
                             user_message="כבר יש בקשה ממתינה לאישור עבור ליד זה.")
with patch.object(lch, "_at_find_lead", return_value=None), \
     patch.object(lch, "_propose_lead_write", return_value=fail_result):
    reply = _send(c, "יוסי כהן")
chk("T16: on propose_action() failure, the Gateway's own message is returned "
    "(no false success)", reply == "כבר יש בקשה ממתינה לאישור עבור ליד זה.")
snap = _snap(c)
chk("T17: clarification state SURVIVES a failed proposal (no partial action, "
    "no payload loss)",
    snap.get("active_lead_candidate") is not None
    and snap["active_lead_candidate"].get("state") == "needs_clarification")


# ── Entry conditions: when clarification does / doesn't start ──────────────
print()
print("── Entry conditions for starting a clarification ──")

c = "no_phone_no_start"
with patch.object(lch, "_at_find_lead", return_value=None):
    reply = _send(c, "מעוניין בדירה יפה באזור המרכז", intent="create_lead")
chk("T18: no phone number in the text -> no clarification starts, even with "
    "intent=create_lead (nothing concrete to clarify FROM)",
    reply is None and _snap(c).get("active_lead_candidate") is None)

c = "wrong_intent_no_start"
with patch.object(lch, "_at_find_lead", return_value=None):
    # Same Tier-5/no_lead_candidates text as the production repro (confirmed
    # via classify_ingress directly), only the Router's intent differs —
    # isolates the intent-gate specifically, not phone/tier detection.
    reply = _send(c, FIRST_MESSAGE, intent="create_task")
chk("T19: same Tier-5 text, but a DIFFERENT Router intent (not create_lead) "
    "-> no clarification starts (the intent gate, not just phone presence, "
    "decides whether to open a clarification)",
    reply is None and _snap(c).get("active_lead_candidate") is None)

c = "tier4_no_start"
with patch.object(lch, "_at_find_lead", return_value=None):
    reply = _send(
        c, "[12.9.2023, 14:25] אורי צדוק: ד טבריה מוכר במעלה עמוס 0501234571",
        intent="create_lead",
    )
chk("T20: Tier 4 content (chat-export/log shape) never triggers clarification "
    "— that's not a lead dictation attempt at all",
    reply is None and _snap(c).get("active_lead_candidate") is None)

c = "no_session_cannot_resolve"
_start(c)  # a real pending clarification now exists for this chat_id
with patch.object(lch, "_at_find_lead", return_value=None):
    # A caller that passes session=None (never loaded a snapshot) cannot
    # safely resolve an existing pending clarification without an extra
    # read — the resolver must degrade to "nothing to check", not crash,
    # and must NOT silently drop/corrupt the still-pending state.
    reply = lch.handle_lead_candidate(
        identity, "יוסי כהן", c, "telegram", intent="", session=None,
    )
chk("T21: session=None on a caller with an existing pending clarification "
    "safely returns None (deferred, not crashed, not falsely resolved) "
    "instead of erroring or guessing",
    reply is None)
chk("T21b: the pending clarification itself is untouched — still resolvable "
    "by a caller that DOES pass the snapshot",
    _snap(c).get("active_lead_candidate", {}).get("state") == "needs_clarification")


# ── Consumer-safety: the OLD post-write bookmark shape is never confused
#    with a pending clarification ──────────────────────────────────────────
print()
print("── Consumer audit: old bookmark shape vs. new clarification shape ──")

c = "old_bookmark_shape"
lead_sessions.get_or_create(c)
lead_sessions.set_active_lead_candidate(c, "שם קודם", record_id="recOLD123")
reply = _send(c, "יוסי כהן")
chk("T22: a plain post-write bookmark (no 'state' key) is NOT treated as a "
    "pending clarification — resolver returns None, doesn't hijack the message",
    reply is None)
chk("T23: the old bookmark itself is left untouched (not cleared, not read as garbage)",
    lead_sessions.get(c)["active_lead_candidate"] == {
        "name": "שם קודם", "record_id": "recOLD123",
        "set_at": lead_sessions.get(c)["active_lead_candidate"]["set_at"],
    })


# ── LL-11: handle_lead_candidate() must not read Sessions itself ───────────
print()
print("── LL-11: no extra Sessions read from inside handle_lead_candidate() ──")

c = "ll11_no_extra_read"
snap = _snap(c)  # the ONE load a real caller would do
calls = []
real_get = lead_sessions.get


def _counting_get(sender):
    calls.append(sender)
    return real_get(sender)


with patch.object(lead_sessions, "get", side_effect=_counting_get):
    lch.handle_lead_candidate(
        identity, "שלום", c, "telegram", intent="", session=snap,
    )
chk("T24: handle_lead_candidate() itself never calls lead_sessions.get() when "
    "a snapshot is already provided — zero extra Sessions reads",
    len(calls) == 0)


print(f"\n{'='*50}")
print(f"BUG-099c (lead clarification) tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
