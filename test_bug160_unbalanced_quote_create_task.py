#!/usr/bin/env python3
"""
test_bug160_unbalanced_quote_create_task.py — BUG-160 regression suite.

Root cause: `core/router/router.py::_normalize_create_task_input()` only
stripped a wrapping quote/bracket pair when BOTH the opening and closing
character were present (`value.startswith(opening) and
value.endswith(closing)`). A single unbalanced leading quote (e.g. a stray
`"` at the start of a Telegram message with no closing `"` anywhere) was
never removed, so it stayed part of the normalized string.
`_STRUCTURED_CREATE_TASK_RE.fullmatch()` requires the string to start
directly with a trigger verb (צור/תיצור/הוסף/תוסיף) — a stuck leading quote
broke the match entirely. `parse_deterministic_create_task()` then returned
the `matched=False` default, so `route_request()` fell through to the
general `intent_router.py`-based routing (`Handler.AGENT`) instead of the
deterministic `Handler.TOOL` path — the exact same silent-bypass shape as
BUG-159, but caused by punctuation instead of a missing verb/noun form.

Fix: `_normalize_create_task_input()`'s existing bounded strip loop gained
one more narrow case: if the (already prefix/balanced-pair-stripped) value
starts with an opening quote/bracket character AND its matching closer does
NOT appear anywhere later in the string, strip only the single leading
character (never assume a matching closer exists elsewhere and strip both
sides). If the closer DOES appear somewhere later — just not at the exact
end — the shape stays genuinely ambiguous and is left untouched, same
unmatched-fallthrough behavior as before this fix (no new false-positive
stripping introduced).

This file proves:
  1. The exact reported phrasing (unbalanced leading `"`, no closing quote
     anywhere) now resolves to a certain, deterministic create_task parse.
  2. The existing balanced-pair stripping (both quote/bracket types) is
     unchanged.
  3. The existing `>`-prefix and `Eli:`/`אלי:` prefix stripping are
     unchanged.
  4. A genuinely ambiguous case (closing quote appears mid-string, not at
     the end) is deliberately left unmatched — no new stripping invented
     for a shape that isn't clearly "unbalanced wrapper noise".
  5. Unrelated CREATE_TASK/CREATE_EVENT/CREATE_LEAD routing is unaffected.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from core.router.intent_router import detect_intent  # noqa: E402
from core.router.route_decision import Intent  # noqa: E402
from core.router.router import (  # noqa: E402
    _normalize_create_task_input,
    parse_deterministic_create_task,
)

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


# ── 1. The exact phrasing from the staging validation report (07/08/2026)
_text = '"צור משימה בדיקת PR546 עד תאריך 12-08-26 בשעה 14:54'
_parse = parse_deterministic_create_task(_text)
chk("unbalanced leading '\"' -> matched=True (was False, silent Agent bypass)",
    _parse.matched)
chk("unbalanced leading '\"' -> certain=True (deterministic path taken)",
    _parse.certain)
chk("unbalanced leading '\"' -> title correctly extracted",
    _parse.title == "בדיקת PR546")
chk("unbalanced leading '\"' -> due_date parsed",
    _parse.due_date == "2026-08-12")

# ── 2. Existing balanced-pair stripping unchanged ───────────────────────
for opening, closing in (('"', '"'), ("'", "'"), ("(", ")"), ("[", "]"), ("{", "}")):
    _norm = _normalize_create_task_input(f"{opening}צור משימה בדיקה{closing}")
    chk(f"balanced pair {opening!r}/{closing!r} still stripped -> 'צור משימה בדיקה'",
        _norm == "צור משימה בדיקה")

# ── 3. Existing prefix stripping unchanged ──────────────────────────────
chk("'> Eli: צור משימה בדיקה' -> prefix still stripped",
    _normalize_create_task_input("> Eli: צור משימה בדיקה") == "צור משימה בדיקה")
chk("'אלי: צור משימה בדיקה' -> prefix still stripped",
    _normalize_create_task_input("אלי: צור משימה בדיקה") == "צור משימה בדיקה")

# ── 4. Genuinely ambiguous shape (closer appears mid-string, not at the
#      end) is deliberately left unmatched — no new stripping invented. ──
_ambiguous = parse_deterministic_create_task('"say hi" צור משימה בדיקה')
chk("closing quote mid-string (not at end) -> still NOT matched "
    "(deliberately conservative, unchanged behavior)",
    not _ambiguous.matched)

# ── 5. Unrelated routing unaffected ─────────────────────────────────────
_intent, _conf, _rule = detect_intent("קבע פגישה עם הספק מחר")
chk("'קבע פגישה עם הספק מחר' -> CREATE_EVENT (unaffected)",
    _intent == Intent.CREATE_EVENT)

_intent, _conf, _rule = detect_intent("תוסיף ליד חדש על דירה")
chk("'תוסיף ליד חדש על דירה' -> CREATE_LEAD (unaffected)",
    _intent == Intent.CREATE_LEAD)

_normal_parse = parse_deterministic_create_task("צור משימה בדיקה רגילה")
chk("plain 'צור משימה בדיקה רגילה' (no punctuation at all) still parses correctly",
    _normal_parse.matched and _normal_parse.title == "בדיקה רגילה")

print(f"\n{'═'*45}")
print(f"  {passed}/{passed+failed} passed")

sys.exit(0 if failed == 0 else 1)
