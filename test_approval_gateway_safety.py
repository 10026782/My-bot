#!/usr/bin/env python3
"""
test_approval_gateway_safety.py — Regression suite for Approval Gateway safety
(Section 1 bugs from 30/06/2026 production report).

Covers:
  BUG-ROUTER-TEST-WORD-COLLISION     — "בדיקה" inside a sheet name must NOT
                                        route to BOT_STATUS_CHECK.
  BUG-V1-A32-SHEETS-FALSE-SUCCESS    — A32 must block Sheets success claims
                                        without sheets_append evidence.
  BUG-V1-FAKE-APPROVAL-STATE         — A32 must block "⏳ ממתינה לאישור" text
                                        emitted without a real pending approval.
  BUG-V1-MULTI-PENDING-PAYLOAD-CONTAMINATION / BUG-BATCH-DISCARD
                                     — CORRECTED 15/07/2026: the original fix
                                        blocked (discarded) any mutating
                                        approval beyond the first in a turn
                                        outright — a regression from working
                                        batch behavior, since the payload-
                                        contamination it cited was never
                                        actually reproduced (each
                                        _queue_approval() call already made
                                        its own independent copy/contract,
                                        both before and after that fix). Now:
                                        every mutating tool call in a turn is
                                        durably preserved — the first becomes
                                        a live ActionContract + notification,
                                        the rest are held in
                                        event_bus.batch_queue and promoted
                                        one at a time via
                                        app._promote_next_batch_item(), only
                                        once nothing is live for that
                                        identity. See
                                        test_bug_batch_approval_preserved.py
                                        for the live-path regression
                                        coverage.
  BUG-V1-APPROVAL-REQUEUE-AFTER-CONFIRM
                                     — ExecutedActionCache blocks re-queuing
                                        the same action within the TTL window.
  BUG-V1-UNAUTHORIZED-PAYLOAD-AUGMENTATION (basic)
                                     — approved_payload == executed_payload
                                        (verified via PendingActionsStore
                                        immutability: pop returns what add stored).
"""

from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("TELEGRAM_TOKEN",     "123:stub_token_for_tests")
os.environ.setdefault("AIRTABLE_API_KEY",   "stub")
os.environ.setdefault("AIRTABLE_BASE_ID",   "stub")
os.environ.setdefault("ANTHROPIC_API_KEY",  "stub")
os.environ.setdefault("ELIYAHU_CHAT_ID",    "99999")
os.environ.setdefault("RENDER_APP_URL",     "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK",      "0")

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"  ✅ {desc}")
        passed += 1
    else:
        print(f"  ❌ {desc}")
        failed += 1


# ══════════════════════════════════════════════════
# BUG-ROUTER-TEST-WORD-COLLISION
# ══════════════════════════════════════════════════

print("\n── BUG-ROUTER-TEST-WORD-COLLISION ───────────────────────────")

from core.router.intent_router import detect_intent
from core.router.route_decision import Intent

# הקלט המקורי שגרם לרגרסיה
sheet_action = "תוסיף לקובץ שיטס לגליון בשם בדיקה תוצאת ניסוי ב אישור התקבל"
intent, conf, _ = detect_intent(sheet_action)
chk(
    "test_router_sheet_name_bedika_not_bot_status: "
    f"got intent={intent!r} (expected ≠ BOT_STATUS_CHECK)",
    intent != Intent.BOT_STATUS_CHECK,
)

# "בדיקה" לבד עדיין צריכה להיות BOT_STATUS_CHECK
standalone_bedika = "בדיקה"
intent2, _, _ = detect_intent(standalone_bedika)
chk(
    "standalone 'בדיקה' → BOT_STATUS_CHECK",
    intent2 == Intent.BOT_STATUS_CHECK,
)

# "test" לבד
standalone_test = "test"
intent3, _, _ = detect_intent(standalone_test)
chk(
    "standalone 'test' → BOT_STATUS_CHECK",
    intent3 == Intent.BOT_STATUS_CHECK,
)

# "אתה עובד?" לבד עדיין contextual (ללא "היי" שמפעיל GREETING קודם)
contextual = "אתה עובד?"
intent4, _, _ = detect_intent(contextual)
chk(
    "'אתה עובד?' → BOT_STATUS_CHECK (contextual phrase still works)",
    intent4 == Intent.BOT_STATUS_CHECK,
)

# "test" בתוך משפט פעולה — לא BOT_STATUS_CHECK
test_in_sentence = "תוסיף test row לגיליון"
intent5, _, _ = detect_intent(test_in_sentence)
chk(
    "'test' inside action sentence → NOT BOT_STATUS_CHECK",
    intent5 != Intent.BOT_STATUS_CHECK,
)


# ══════════════════════════════════════════════════
# BUG-V1-A32-SHEETS-FALSE-SUCCESS
# ══════════════════════════════════════════════════

print("\n── BUG-V1-A32-SHEETS-FALSE-SUCCESS ─────────────────────────")

from core.anti_hallucination import sanitize_agent_response, _NO_TOOL_EVIDENCE_FALLBACK

# ① "השורה נוספה" ללא sheets_append → חסום
blocked1 = sanitize_agent_response("השורה נוספה לגליון 'בדיקה'.", [])
chk(
    "test_a32_blocks_sheets_success_without_sheets_append: 'השורה נוספה' → blocked",
    blocked1 == _NO_TOOL_EVIDENCE_FALLBACK,
)

# ② "הוספתי לגליון" ללא sheets_append → חסום
blocked2 = sanitize_agent_response("הוספתי לגליון בדיקה.", [])
chk(
    "'הוספתי לגליון' with no sheets_append → blocked",
    blocked2 == _NO_TOOL_EVIDENCE_FALLBACK,
)

# ③ "נוסף ל-Google Sheets" → חסום
blocked3 = sanitize_agent_response("הנתונים נוספו ל-Google Sheets.", [])
chk(
    "'נוסף ל-Google Sheets' with no sheets_append → blocked",
    blocked3 == _NO_TOOL_EVIDENCE_FALLBACK,
)

# ④ עם sheets_append אמיתי → עובר
with_sheets = sanitize_agent_response(
    "השורה נוספה לגליון בהצלחה.",
    [{"tool": "sheets_append", "content": "✅ שורה נוספה", "ok": True}],
)
chk(
    "'השורה נוספה' WITH real sheets_append → passes through",
    with_sheets not in (_NO_TOOL_EVIDENCE_FALLBACK,),
)

# ⑤ sheets_append נכשל → חסום (ok=False not enough as positive evidence)
with_failed_sheets = sanitize_agent_response(
    "השורה נוספה לגליון.",
    [{"tool": "sheets_append", "content": "❌ שגיאה", "ok": False}],
)
chk(
    "'השורה נוספה' with FAILED sheets_append (ok=False) → blocked",
    with_failed_sheets == _NO_TOOL_EVIDENCE_FALLBACK,
)


# ══════════════════════════════════════════════════
# BUG-V1-FAKE-APPROVAL-STATE
# ══════════════════════════════════════════════════

print("\n── BUG-V1-FAKE-APPROVAL-STATE ───────────────────────────────")

# ① "⏳ הפעולה ממתינה לאישור" בלי sentinel → חסום
fake_pending = sanitize_agent_response(
    "⏳ הפעולה ממתינה לאישור הבעלים. כשתאשר — השורה תתווסף מיד.",
    [],
)
chk(
    "test_a32_blocks_fake_pending_approval_without_pending_id: "
    "'⏳ ממתינה לאישור' no sentinel → blocked",
    fake_pending == _NO_TOOL_EVIDENCE_FALLBACK,
)

# ② עם sentinel אמיתי → עובר
real_pending = sanitize_agent_response(
    "⏳ הפעולה ממתינה לאישור הבעלים.",
    [{"tool": "__approval_queued__", "content": "⏳ ...", "ok": True}],
)
chk(
    "'⏳ ממתינה' WITH real __approval_queued__ sentinel → passes through",
    real_pending not in (_NO_TOOL_EVIDENCE_FALLBACK,),
)

# ③ "כשתאשר — תישלח" בלי sentinel
fake2 = sanitize_agent_response("כשתאשר — ההודעה תישלח.", [])
chk(
    "'כשתאשר — תישלח' no sentinel → blocked",
    fake2 == _NO_TOOL_EVIDENCE_FALLBACK,
)


# ══════════════════════════════════════════════════
# BUG-V1-MULTI-PENDING-PAYLOAD-CONTAMINATION / BUG-BATCH-DISCARD
# ══════════════════════════════════════════════════

print("\n── BUG-BATCH-DISCARD (agent turn: queue+promote, not discard) ──")


# Simulate the corrected logic directly (same logic as in app.py's tool loop
# — see the BUG-BATCH-DISCARD comment there): the first mutating approval
# this turn queues normally; every one beyond it is deferred (not discarded).
# Replaces the old simulate_approval_gate() which asserted the removed
# "queued, blocked, blocked" hard-discard behavior — see
# test_bug_batch_approval_preserved.py for the live-path (real
# _queue_approval()/ActionGateway/batch_queue) regression coverage of the
# actual fix, including promotion order and dispatch-exactly-once guarantees.
def simulate_approval_gate(approvals_requested: int) -> list[str]:
    """Returns list of outcomes per request: "queued" (live now) or
    "deferred" (durably held, promoted later — never discarded)."""
    _mutating_approvals_this_turn = 0
    outcomes = []
    for _ in range(approvals_requested):
        if _mutating_approvals_this_turn >= 1:
            outcomes.append("deferred")
        else:
            _mutating_approvals_this_turn += 1
            outcomes.append("queued")
    return outcomes

outcomes_1 = simulate_approval_gate(1)
chk(
    "1 approval in turn → queued",
    outcomes_1 == ["queued"],
)

outcomes_2 = simulate_approval_gate(2)
chk(
    "BUG-BATCH-DISCARD: 2 approvals in 1 turn → both preserved "
    "(first queued live, second deferred — never discarded)",
    outcomes_2 == ["queued", "deferred"],
)

outcomes_5 = simulate_approval_gate(5)
chk(
    "BUG-BATCH-DISCARD: 5 approvals in 1 turn → all 5 preserved",
    outcomes_5 == ["queued"] + ["deferred"] * 4,
)


# ══════════════════════════════════════════════════
# BUG-V1-APPROVAL-REQUEUE-AFTER-CONFIRM (ExecutedActionCache)
# ══════════════════════════════════════════════════

print("\n── BUG-V1-APPROVAL-REQUEUE ExecutedActionCache ─────────────")

from event_bus import ExecutedActionCache

cache = ExecutedActionCache()
fp1 = ExecutedActionCache.compute("chat_1", "sheets_append", {"sheet_name": "בדיקה", "row": ["x"]})
fp2 = ExecutedActionCache.compute("chat_1", "sheets_append", {"sheet_name": "אחר",   "row": ["x"]})
fp3 = ExecutedActionCache.compute("chat_2", "sheets_append", {"sheet_name": "בדיקה", "row": ["x"]})

chk("new fingerprint: is_recently_executed → False", not cache.is_recently_executed(fp1))
cache.mark_executed(fp1)
chk("after mark_executed: is_recently_executed → True", cache.is_recently_executed(fp1))
chk("different inputs same chat → different fingerprint, not blocked", not cache.is_recently_executed(fp2))
chk("same inputs different chat → different fingerprint, not blocked", not cache.is_recently_executed(fp3))

# Fingerprint is deterministic
fp1b = ExecutedActionCache.compute("chat_1", "sheets_append", {"sheet_name": "בדיקה", "row": ["x"]})
chk("fingerprint is deterministic (same inputs → same hash)", fp1 == fp1b)

# Input key order does not affect fingerprint (normalized via sort_keys)
fp_ordered   = ExecutedActionCache.compute("c", "t", {"b": 2, "a": 1})
fp_reordered = ExecutedActionCache.compute("c", "t", {"a": 1, "b": 2})
chk("fingerprint is order-independent (sort_keys normalization)", fp_ordered == fp_reordered)


# ══════════════════════════════════════════════════
# BUG-V1-UNAUTHORIZED-PAYLOAD-AUGMENTATION (basic)
# PendingActionsStore.pop returns the immutable payload that was stored —
# exactly what was queued, nothing added.
# ══════════════════════════════════════════════════

print("\n── BUG-V1-UNAUTHORIZED-PAYLOAD-AUGMENTATION (payload integrity) ─")

from event_bus import PendingActionsStore

store = PendingActionsStore()
original_inputs = {"sheet_name": "בדיקה", "row_data": ["תוצאת ניסוי ב", "אישור התקבל"]}
aid = store.add(
    chat_id  = "chat_1",
    action   = "sheets_append",
    payload  = {"tool_name": "sheets_append", "tool_inputs": original_inputs, "user_chat_id": "chat_1"},
    label    = "כתוב לגליון",
)
item = store.pop(aid)
chk("test_approved_payload_equals_executed_payload: payload retrieved intact", item is not None)
retrieved_inputs = item["payload"]["tool_inputs"]
chk(
    "approved tool_inputs == originally queued inputs (no augmentation)",
    retrieved_inputs == original_inputs,
)
chk(
    "pop is atomic — second pop returns None",
    store.pop(aid) is None,
)


# ══════════════════════════════════════════════════

print(f"\n{'═'*52}")
print(f"  Approval Gateway Safety: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
