#!/usr/bin/env python3
"""
test_bug154_date_marker_prefix_parser.py — BUG-154
(parse_deterministic_create_task() crashed on "ל־<date>"-style phrasing).

Problem (staging, 03/08/2026): "צור משימה ... ל־5/8/26 בשעה 10:30" crashed
with AttributeError: 'NoneType' object has no attribute 'start'.
_CREATE_TASK_DATE_WORD_MARKER_RE (r"\bעד\b") found no match (the input uses
"ל־" instead of "עד"), leaving date_marker=None, while date_match still
found "5/8/26" — the old code called date_marker.start() unconditionally
inside `if date_match:`, crashing. app.py's _safe_route() caught the
exception and fell back to intent=unknown/handler=APPROVAL/confidence=0.0 —
a non-canonical generic approval instead of either a certain deterministic
parse or a clean clarification.

Fix: date_marker is looked up first by the "עד" word marker; if not found
AND a date_match exists, a second check looks for a "ל" + maqaf/hyphen/
en-dash/em-dash marker immediately (optional whitespace) before the date's
own start position — never a whole-body search for "ל" alone, since it's
far too common a Hebrew letter/prefix to use as an unscoped marker. If
neither marker is found, the existing uncertain=True fail-closed path
applies — same as any other unrecognized date-marker shape — instead of a
crash.
"""

from __future__ import annotations

from core.router.router import parse_deterministic_create_task

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


# ══════════════════════════════════════════════════════════════════
print("── 1. exact staging repro: 'ל־5/8/26' (Hebrew maqaf) no longer crashes ──")
r1 = parse_deterministic_create_task(
    "צור משימה לבדוק את אימות 546 המעודכן, ל־5/8/26 בשעה 10:30"
)
chk("parse succeeds without raising", r1 is not None)
chk("parse is certain (no clarification fallback)", r1.certain)
chk("title excludes the 'ל־<date>' suffix", r1.title == "לבדוק את אימות 546 המעודכן")
chk("due_date parsed correctly", r1.due_date == "2026-08-05")
chk("due_time parsed correctly", r1.due_time == "10:30")


# ══════════════════════════════════════════════════════════════════
print("\n── 2. Unicode variants of the '-' after ל ──")
for label, dash in (
    ("plain hyphen", "-"),
    ("en dash", "–"),
    ("em dash", "—"),
):
    r = parse_deterministic_create_task(f"צור משימה X ל{dash}5/8/26 בשעה 10:30")
    chk(f"'{label}' variant parses as certain", r.certain and r.due_date == "2026-08-05")


# ══════════════════════════════════════════════════════════════════
print("\n── 3. regression: existing 'עד' marker phrasing unaffected ──")
r_regress = parse_deterministic_create_task(
    "צור משימה פרסום מודעות עד לחמישי הקרוב 6/8/26 בשעה19:00"
)
chk("'עד' marker still parses as certain", r_regress.certain)
chk("'עד' marker title unchanged", r_regress.title == "פרסום מודעות")
chk("'עד' marker due_date unchanged", r_regress.due_date == "2026-08-06")
chk("'עד' marker due_time unchanged", r_regress.due_time == "19:00")


# ══════════════════════════════════════════════════════════════════
print("\n── 4. fail-closed (not fail-crash): a date-shaped token with NO recognized marker ──")
r_no_marker = parse_deterministic_create_task("צור משימה X 5/8/26 בשעה 10:30")
chk("no marker at all -> matched but uncertain (clarify), not certain", r_no_marker.matched and r_no_marker.uncertain)
chk("no marker at all -> does not raise", True)  # reaching this line proves no exception


# ══════════════════════════════════════════════════════════════════
print("\n── 5. 'ל' not immediately followed by a dash is not mistaken for a marker ──")
r_no_dash = parse_deterministic_create_task("צור משימה לבדוק דוח כספי 5/8/26 בשעה 10:30")
chk(
    "'ל' as an ordinary word-initial letter (no dash) does not falsely match "
    "as a date marker -> still uncertain (fail-closed), not a false-certain parse",
    r_no_dash.matched and r_no_dash.uncertain,
)


print()
print("=" * 50)
print(f"BUG-154 (date marker prefix parser crash) tests: {passed} passed, {failed} failed")
if failed:
    raise SystemExit(1)
