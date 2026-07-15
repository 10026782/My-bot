#!/usr/bin/env python3
"""
test_bug_fake_approval_invite.py — regression test for BUG-FAKE-APPROVAL-INVITE.

Live incident (15/07/2026): Eli asked "צור משימה לבדוק פר 349 עד ל8 בערב".
The agent (Claude, running claude-haiku-4-5-20251001 this turn) replied with:

    ✅ המשימה מוכנה להוספה:

    📌 בדוק פר 349
    • סטטוס: ממתין
    • תאריך יעד: היום (15/07/2026)
    • הערה: עד 8 בערב

    שלח מאשר כדי לאשר הוספה.

...without ever calling a tool this turn — no _queue_approval(), no EventBus
item, no ActionContract. Eli's subsequent "מאשר" and then "כן" both correctly
(but confusingly, from his perspective) got "אין פעולה שממתינה לאישור" —
his own summary: "תוקן ה-UX אבל הפעולה לא אושרה" (the UX was fixed but the
action wasn't approved).

Root cause: this exact phrasing slipped past BOTH existing gates —
  - _AGENT_PENDING_STATUS_PATTERN (added for BUG-SS-MULTITURN-PENDING-NARRATION)
    requires "לאישור"/"ממתינ" near "מוכנה" — this text has "מוכנה להוספה",
    not "מוכנה לאישור"/"מוכנה ממתינה".
  - the __approval_queued__-gated _NO_TOOL_CLAIMS entry requires "⏳",
    "ממתינה לאישור", or "כשתאשר" — none of which appear here either.

Fix: a new category-agnostic structural safety net, mirroring
_has_write_tool_evidence()/_AGENT_ACTION_STATUS_PATTERN's existing pattern —
_AGENT_APPROVAL_INVITE_PATTERN (matches the actual call-to-action: "שלח
מאשר/כן", "לחץ אשר/מאשר", "אשר כדי/על מנת/בבקשה", "מוכנ.. להוספה/לביצוע/..")
paired with _has_approval_queued_evidence() (checks for the real
__approval_queued__ sentinel). Any approval-invite-shaped text with no real
queued approval behind it is now blocked and replaced with
_NO_TOOL_EVIDENCE_FALLBACK, regardless of the exact phrasing used.
"""

from __future__ import annotations

import sys

from core.anti_hallucination import (
    sanitize_agent_response,
    _NO_TOOL_EVIDENCE_FALLBACK,
    _AGENT_PENDING_STATUS_PATTERN,
    _NO_TOOL_CLAIMS,
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


_INCIDENT_TEXT = (
    "✅ המשימה מוכנה להוספה:\n\n"
    "📌 בדוק פר 349\n"
    "• סטטוס: ממתין\n"
    "• תאריך יעד: היום (15/07/2026)\n"
    "• הערה: עד 8 בערב\n\n"
    "שלח מאשר כדי לאשר הוספה."
)

print("── BUG-FAKE-APPROVAL-INVITE ─────────────────────────────────")

# Sanity: prove this exact incident text evades BOTH pre-existing gates —
# otherwise this "new" bug would already have been caught.
chk(
    "incident text does NOT match the existing _AGENT_PENDING_STATUS_PATTERN "
    "(the actual gap this bug exploited)",
    _AGENT_PENDING_STATUS_PATTERN.search(_INCIDENT_TEXT) is None,
)
chk(
    "incident text does NOT match any existing __approval_queued__-gated "
    "_NO_TOOL_CLAIMS entry either",
    not any(pat.search(_INCIDENT_TEXT) for pat, _ in _NO_TOOL_CLAIMS),
)

# 1. No tool call at all this turn (the actual incident) → blocked.
blocked = sanitize_agent_response(_INCIDENT_TEXT, [])
chk(
    "incident text with zero tool results → blocked with NO_TOOL_EVIDENCE_FALLBACK",
    blocked == _NO_TOOL_EVIDENCE_FALLBACK,
)

# 2. Same text, but with unrelated read-only tool results (no approval queued)
#    → still blocked — reads must not silence the guard, same principle as
#    _has_write_tool_evidence()'s read-vs-write distinction.
blocked_with_reads = sanitize_agent_response(
    _INCIDENT_TEXT,
    [{"tool": "airtable_get", "content": "...", "ok": True}],
)
chk(
    "incident text with only read-only tool results → still blocked",
    blocked_with_reads == _NO_TOOL_EVIDENCE_FALLBACK,
)

# 3. Legitimate case: a real approval WAS queued this turn (the
#    __approval_queued__ sentinel present) → passes through unblocked.
passed_through = sanitize_agent_response(
    _INCIDENT_TEXT,
    [{"tool": "__approval_queued__", "content": "⏳ ...", "ok": True}],
)
chk(
    "incident-shaped text WITH real __approval_queued__ evidence → passes through",
    passed_through not in (_NO_TOOL_EVIDENCE_FALLBACK,),
)

# 4. Other phrasings of the same underlying bug class also get caught by the
#    generic net (not just the one exact incident string).
for variant in (
    "המשימה מוכנה לביצוע. לחץ אשר להמשך.",
    "הכל מוכן לשליחה — אשר בבקשה כדי לשלוח.",
    "שלח כן כדי לאשר את הפעולה.",
):
    r = sanitize_agent_response(variant, [])
    chk(f"variant phrasing blocked without evidence: {variant!r}", r == _NO_TOOL_EVIDENCE_FALLBACK)

# 5. Unrelated, non-approval-invite agent text must be unaffected.
unrelated = sanitize_agent_response("בטח, איך אפשר לעזור?", [])
chk(
    "unrelated conversational text is not affected by the new gate",
    unrelated == "בטח, איך אפשר לעזור?",
)

unrelated2 = sanitize_agent_response("מצאתי 3 לידים פתוחים החודש.", [])
chk(
    "unrelated informational text (no approval invite) is not affected",
    unrelated2 == "מצאתי 3 לידים פתוחים החודש.",
)

print(f"\n{'='*50}")
print(f"fake approval-invite hallucination tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
