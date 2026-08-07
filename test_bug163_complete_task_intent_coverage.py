#!/usr/bin/env python3
"""
test_bug163_complete_task_intent_coverage.py — BUG-163 regression suite.

Root cause: core/router/intent_router.py's COMPLETE_TASK rule
(r"(סגור|סיים|סמן.*סיים|complete).*(משימ|טאסק|task)") missed two common
natural-language phrasings, discovered during Turn Coordinator E2E staging
verification (07/08/2026):
  1. "השלם" (a common "complete/finish" verb) was not in the verb group at
     all.
  2. "סמן <משימה> כבוצע/כבוצעה" ("mark <task> as done") failed because the
     completion marker appears AFTER the task noun, but the original regex
     required a verb-then-target order, and the only "mark"-shaped
     alternative was the compound "סמן.*סיים" (requires BOTH "סמן" and
     "סיים" in the same sentence) — "סמן ... כבוצעה" alone never matched
     any alternative.

Both real phrasings previously landed on Intent.UNKNOWN (confidence 0.00),
never reaching COMPLETE_TASK at all — routed to the generic Agent fallback
with zero deterministic priority.

Fix: added "השלם" to the existing verb-then-target COMPLETE_TASK rule, and
added a second, order-flexible COMPLETE_TASK rule scoped to "סמן"/"mark"
followed (in either relative order to the task noun, within 40/20 chars)
by a task noun and a completion marker (כבוצע/בוצעה/done/complete) — not a
bare "task mentions בוצע anywhere" match, to avoid colliding with
LIST_TASKS ("אילו משימות כבר בוצעו").

This file proves:
  1. The two exact reported phrasings now resolve to COMPLETE_TASK.
  2. Existing COMPLETE_TASK phrasings (סגור/סיים/complete) are unchanged.
  3. UPDATE_TASK, CREATE_TASK, DELETE_TASK routing is unchanged.
  4. LIST_TASKS still wins for a "which tasks are already done" query that
     mentions both "משימות" and "בוצעו" but has no "סמן"/"mark" verb —
     the false-positive risk the narrower "סמן"-scoped rule was designed
     to avoid.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from core.router.intent_router import detect_intent  # noqa: E402
from core.router.route_decision import Intent  # noqa: E402

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


# ── 1. The two exact phrasings reported in the Turn Coordinator E2E
#      staging validation (07/08/2026) ──────────────────────────────────
_intent, _conf, _rule = detect_intent("השלם את המשימה בדיקת Complete לא קיימת")
chk("'השלם את המשימה ...' -> COMPLETE_TASK (was UNKNOWN)",
    _intent == Intent.COMPLETE_TASK)

_intent, _conf, _rule = detect_intent("סמן משימת מעקב כבוצעה")
chk("'סמן משימת מעקב כבוצעה' -> COMPLETE_TASK (was UNKNOWN)",
    _intent == Intent.COMPLETE_TASK)

_intent, _conf, _rule = detect_intent("סמן את המשימה X כבוצע")
chk("'סמן את המשימה X כבוצע' -> COMPLETE_TASK (כבוצע without ה)",
    _intent == Intent.COMPLETE_TASK)

# ── 2. Existing COMPLETE_TASK phrasings unchanged ───────────────────────
_intent, _conf, _rule = detect_intent("סגור משימה בדיקה")
chk("'סגור משימה בדיקה' -> COMPLETE_TASK (unchanged)",
    _intent == Intent.COMPLETE_TASK)

_intent, _conf, _rule = detect_intent("סיים משימה בדיקה")
chk("'סיים משימה בדיקה' -> COMPLETE_TASK (unchanged)",
    _intent == Intent.COMPLETE_TASK)

_intent, _conf, _rule = detect_intent("complete task testing")
chk("'complete task testing' -> COMPLETE_TASK (unchanged)",
    _intent == Intent.COMPLETE_TASK)

_intent, _conf, _rule = detect_intent("סמן לי לסיים את המשימה")
chk("'סמן לי לסיים את המשימה' -> COMPLETE_TASK (original סמן.*סיים alt. unchanged)",
    _intent == Intent.COMPLETE_TASK)

# ── 3. Sibling intents unchanged ─────────────────────────────────────────
_intent, _conf, _rule = detect_intent("עדכן משימת מעקב לסטטוס בוצע")
chk("'עדכן משימת מעקב לסטטוס בוצע' -> UPDATE_TASK (unchanged, unrelated verb)",
    _intent == Intent.UPDATE_TASK)

_intent, _conf, _rule = detect_intent("צור משימה חדשה")
chk("'צור משימה חדשה' -> CREATE_TASK (unchanged)",
    _intent == Intent.CREATE_TASK)

_intent, _conf, _rule = detect_intent("מחק משימה בדיקה")
chk("'מחק משימה בדיקה' -> DELETE_TASK (unchanged)",
    _intent == Intent.DELETE_TASK)

# ── 4. No collision with LIST_TASKS — the exact false-positive risk the
#      narrower "סמן"-scoped rule (not a bare משימה+בוצע co-occurrence
#      match) was designed to avoid. ─────────────────────────────────────
_intent, _conf, _rule = detect_intent("תראה לי אילו משימות כבר בוצעו")
chk("'תראה לי אילו משימות כבר בוצעו' -> LIST_TASKS (no false COMPLETE_TASK)",
    _intent == Intent.LIST_TASKS)

_intent, _conf, _rule = detect_intent("רשימת משימות")
chk("'רשימת משימות' -> LIST_TASKS (unchanged)",
    _intent == Intent.LIST_TASKS)

# ── 5. Code-review addendum (07/08/2026): word-boundary + negation guard
#      false positives — "complete"/"done" matched as a substring inside
#      "incomplete", and negated phrasings ("do not mark ... done") were
#      wrongly accepted as COMPLETE_TASK. ────────────────────────────────
_intent, _conf, _rule = detect_intent("mark task X incomplete")
chk("'mark task X incomplete' -> not COMPLETE_TASK ('complete' substring guard)",
    _intent != Intent.COMPLETE_TASK)

_intent, _conf, _rule = detect_intent("incomplete task X")
chk("'incomplete task X' -> not COMPLETE_TASK ('complete' substring guard)",
    _intent != Intent.COMPLETE_TASK)

_intent, _conf, _rule = detect_intent("do not mark task X done")
chk("'do not mark task X done' -> not COMPLETE_TASK (negation guard)",
    _intent != Intent.COMPLETE_TASK)

_intent, _conf, _rule = detect_intent("don't mark task X done")
chk("\"don't mark task X done\" -> not COMPLETE_TASK (negation guard)",
    _intent != Intent.COMPLETE_TASK)

_intent, _conf, _rule = detect_intent("mark task X done")
chk("'mark task X done' -> COMPLETE_TASK (valid phrasing still matches)",
    _intent == Intent.COMPLETE_TASK)

print(f"\n{'═'*45}")
print(f"  {passed}/{passed+failed} passed")

sys.exit(0 if failed == 0 else 1)
