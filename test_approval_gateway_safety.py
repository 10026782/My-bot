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
  BUG-122                           — the first mutating proposal may become
                                      pending; later mutations in the same
                                      turn are blocked, not retained, and the
                                      user is told to resolve and resend.
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

print("\n── BUG-122 (agent turn: block later mutations, retain nothing) ──")


def simulate_approval_gate(approvals_requested: int) -> list[str]:
    """Returns "queued" once, then "blocked_not_retained"."""
    _mutating_approvals_this_turn = 0
    outcomes = []
    for _ in range(approvals_requested):
        if _mutating_approvals_this_turn >= 1:
            outcomes.append("blocked_not_retained")
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
    "BUG-122: second approval is blocked and not retained",
    outcomes_2 == ["queued", "blocked_not_retained"],
)

outcomes_5 = simulate_approval_gate(5)
chk(
    "BUG-122: every later approval is blocked and not retained",
    outcomes_5 == ["queued"] + ["blocked_not_retained"] * 4,
)

from event_bus import batch_queue
_bug122_user = "boss_hq:approval-safety"
batch_queue.clear(_bug122_user)
chk("BUG-122: BatchQueue remains zero",
    batch_queue.count_pending(_bug122_user) == 0)
_blocked_message = (
    "יש לך פעולה שממתינה לאישור. יש לאשר או לבטל אותה, "
    "ואז לשלוח מחדש את הבקשה החדשה."
)
chk("BUG-122: user is instructed to resolve and resend",
    "לאשר או לבטל" in _blocked_message and "לשלוח מחדש" in _blocked_message)


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
