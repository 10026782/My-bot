#!/usr/bin/env python3
"""
test_hotfix_c_create_task_verb.py — Hotfix C regression suite.

Root cause: core/router/intent_router.py's CREATE_TASK rule matched only
(פתח|צור|הוסף|תוסיף) as the verb group, so "תייצר משימה..." fell through
to Intent.UNKNOWN instead of Intent.CREATE_TASK — the router never got a
chance to route the request at all.

Fix: added the exact verb "תייצר" to the CREATE_TASK verb alternation.
Nothing else in intent_router.py changed — no other verb, no other
intent's regex, no confidence value, no rule ordering.

This file proves:
  1. "תייצר משימה להיום" -> CREATE_TASK.
  2. "תייצר אירוע להיום" -> NOT CREATE_TASK (noun group still requires
     משימ/טאסק/task; "אירוע" doesn't match it).
  3. "תייצר ליד חדש" -> NOT CREATE_TASK (same noun-group guard).
  4. "תייצר סיכום" (no משימה/מטלה) -> NOT CREATE_TASK.
  5. Existing CREATE_EVENT and CREATE_LEAD routing is unchanged — known-good
     phrases from core/router/test_router.py still resolve the same way,
     and CREATE_EVENT/CREATE_LEAD's own verb groups do NOT gain "תייצר"
     (it was added only to the CREATE_TASK group).
  6. Routing precedence remains specific-before-general: a phrase combining
     a CREATE_TASK trigger with a later, more generic rule's keyword
     (e.g. "דוח" / GENERATE_REPORT) still resolves to CREATE_TASK, because
     the CREATE_TASK rule is still evaluated before it in _RULES.
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


# ── 1. "תייצר משימה" -> CREATE_TASK ─────────────────────────────────────
_intent, _conf, _rule = detect_intent("תייצר משימה להיום")
chk("'תייצר משימה להיום' -> CREATE_TASK", _intent == Intent.CREATE_TASK)
chk("'תייצר משימה להיום' -> confidence unchanged (0.95)", _conf == 0.95)

# ── 2. "תייצר אירוע" -> NOT CREATE_TASK ─────────────────────────────────
_intent, _conf, _rule = detect_intent("תייצר אירוע להיום")
chk("'תייצר אירוע להיום' -> NOT CREATE_TASK", _intent != Intent.CREATE_TASK)

# ── 3. "תייצר ליד חדש" -> NOT CREATE_TASK ───────────────────────────────
_intent, _conf, _rule = detect_intent("תייצר ליד חדש")
chk("'תייצר ליד חדש' -> NOT CREATE_TASK", _intent != Intent.CREATE_TASK)

# ── 4. "תייצר סיכום" (no משימה/מטלה) -> NOT CREATE_TASK ─────────────────
_intent, _conf, _rule = detect_intent("תייצר סיכום")
chk("'תייצר סיכום' -> NOT CREATE_TASK", _intent != Intent.CREATE_TASK)

# ── CodeRabbit finding on PR #498: "exact verb only" must be enforced by
#    the regex itself, not just claimed in a comment — "תייצר" as a bare
#    substring also matched longer conjugated forms like "תייצרי". Fixed
#    with \b around the new verb only (the other four verbs in the group
#    are untouched — no broader conjugation sweep). ─────────────────────
_intent, _conf, _rule = detect_intent("תייצרי משימה להיום")
chk("'תייצרי משימה להיום' -> NOT CREATE_TASK (exact verb boundary enforced)",
    _intent != Intent.CREATE_TASK)

# ── 5a. Existing CREATE_EVENT phrasing unchanged ────────────────────────
_intent, _conf, _rule = detect_intent("קבע פגישה עם הספק מחר")
chk("'קבע פגישה עם הספק מחר' -> CREATE_EVENT (unchanged)",
    _intent == Intent.CREATE_EVENT)

# ── 5b. Existing CREATE_LEAD phrasing unchanged ─────────────────────────
_intent, _conf, _rule = detect_intent("תוסיף ליד חדש על דירה")
chk("'תוסיף ליד חדש על דירה' -> CREATE_LEAD (unchanged)",
    _intent == Intent.CREATE_LEAD)

# ── 5c. Existing CREATE_TASK verb ("צור") still works, untouched ───────
_intent, _conf, _rule = detect_intent("צור משימה בנושא תזרים")
chk("'צור משימה בנושא תזרים' -> CREATE_TASK (pre-existing verb unaffected)",
    _intent == Intent.CREATE_TASK)

# ── 5d. "תייצר" was NOT added to CREATE_EVENT's or CREATE_LEAD's own
#        verb groups — only to CREATE_TASK's. ───────────────────────────
_intent, _conf, _rule = detect_intent("תייצר פגישה מחר")
chk("'תייצר פגישה מחר' -> NOT CREATE_EVENT (verb not added there)",
    _intent != Intent.CREATE_EVENT)

_intent, _conf, _rule = detect_intent("תייצר לקוח פוטנציאלי")
chk("'תייצר לקוח פוטנציאלי' -> NOT CREATE_LEAD (verb not added there)",
    _intent != Intent.CREATE_LEAD)

# ── 6. Precedence: CREATE_TASK (line ~45) still wins over a later,
#      more generic rule (GENERATE_REPORT, "דוח") when both could match. ─
_intent, _conf, _rule = detect_intent("תייצר משימה בנושא דוח")
chk("'תייצר משימה בנושא דוח' -> CREATE_TASK (specific-before-general holds)",
    _intent == Intent.CREATE_TASK)

print(f"\n{'═'*45}")
print(f"  {passed}/{passed+failed} passed")

sys.exit(0 if failed == 0 else 1)
