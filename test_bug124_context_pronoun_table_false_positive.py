#!/usr/bin/env python3
"""
test_bug124_context_pronoun_table_false_positive.py — BUG-124 regression suite.

Live incident: an ordinary message containing the word "זה" ("this/it" — one
of the most common words in Hebrew, e.g. "כמה זה עולה") got silently
misclassified as tier=4/table_separator and blocked with the generic "📄 זה
נראה כמו טבלה" fallback, even though the user's message had nothing to do
with a pasted table.

Root cause: app.py's resolve_context_pronouns() (C60, runs before Router/
intent detection) does a substring replace of CONTEXT_PRONOUNS entries
("זה"/"אותו"/"ההוא"/"הקודם"/"הנספח"/"הקובץ"/"הקובץ האחרון") with a quoted
business summary from the session's last_tool_result/last_uploaded_file.
Real tool-result summaries commonly use " | " as a field separator (the
standard "✅ בוצע: ... | מזהה: ..." style used throughout this codebase) —
once spliced into an otherwise plain sentence, the message now contains 2+
pipe characters, which core.ingress_classifier._TABLE_RE reads as a pasted
table. Reproduced with two independent live messages ("כמה זה 5 כפול 7",
"כמה זה 5+5") against the same session state; a message with no pronoun
("5 כפול 5") was unaffected — proving the substitution, not the classifier
itself, injected the trigger.

Fix: app.py's resolve_context_pronouns() now sanitizes the substituted
value (pipes -> middle dot, tabs -> space, box-drawing chars stripped) via
a new _sanitize_for_free_text() helper, applied uniformly to both
substitution branches (last_file / last_tool_result) — covers all 7
CONTEXT_PRONOUNS entries, not just "זה", since they share the same two code
paths. Does NOT touch core.ingress_classifier._TABLE_RE itself (relied on
for many legitimate table detections elsewhere) and does NOT change when a
pronoun gets substituted — only sanitizes what gets substituted in.

Scope: resolve_context_pronouns()'s substitution values only. The deeper,
separate question of whether these common words should be substituted at
all in every grammatical context (e.g. "אני מכיר אותו" — ordinary use of
"him", not a reference to a prior tool result) is explicitly out of scope
for this fix — flagged to the user, narrow fix chosen over a broader
semantic-disambiguation rework.

Follow-up (same investigation, same branch): the pipe/tab/box-char
sanitization above only covered ONE of core.ingress_classifier._is_tier4()'s
7 trigger classes. Real _MEMORABLE_TOOLS summaries for airtable_add,
airtable_update, and tma_write all embed the raw Airtable record_id
verbatim (e.g. "✅ רשומה recABC123XY עודכנה.") — which still matches
_AIRTABLE_ID_RE even after pipes are translated away, so a follow-up like
"תעדכן גם את זה" right after any of those 3 tools was STILL silently
blocked, just under reason=airtable_id instead of table_separator. Fixed by
checking the actual quoted snippet against the real _is_tier4() before
splicing it in (_safe_context_quote()), falling back to a plain reference
with no quoted content when quoting would trip Tier-4 — self-healing
against any future trigger _is_tier4() gains, not just today's known list.
"""

from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-bug125-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:BUG125_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patBug125Test")
os.environ.setdefault("AIRTABLE_BASE_ID", "appBug125Test")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import app  # noqa: E402  (env vars above must be set before import)
from core.ingress_classifier import _is_tier4  # noqa: E402

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


# The exact class of trigger from the live incident — a real C53-A-style
# tool-result summary with 2+ " | " separated fields.
_LTR_SESSION = {
    "last_tool_result": {
        "summary": "✅ נוצר follow-up: משה חביב | טבלה: Tasks | סטטוס: ממתין",
    },
}
_LUF_SESSION = {
    "last_uploaded_file": {"original_filename": "report | q3 | final.pdf"},
}

# The same Tier-4 table regex from core/ingress_classifier.py, reproduced
# here deliberately (not imported) so this test independently verifies the
# actual production trigger shape rather than trusting the module's own
# internals not to have drifted.
_TABLE_RE = re.compile(
    r"[│┃]"
    r"|[|]{2,}"
    r"|[^|\n]+\|[^|\n]+\|[^|\n]+"
    r"|^\s*[\|\+][-\s\|\+]{5,}"
    r"|\t[^\t]+\t[^\t]+\t",
    re.MULTILINE,
)


# ══════════════════════════════════════════════════
# Live-incident reproductions
# ══════════════════════════════════════════════════

print("── live-incident reproductions ─────────────────")

for msg in ("כמה זה 5 כפול 7", "כמה זה 5+5"):
    resolved = app.resolve_context_pronouns(msg, "chat1", _LTR_SESSION)
    chk(f"{msg!r}: substituted text no longer trips the Tier-4 table regex",
        _TABLE_RE.search(resolved) is None)

# Regression: no pronoun in the text -> no substitution, message untouched.
chk('"5 כפול 5" (no pronoun) is untouched by resolve_context_pronouns()',
    app.resolve_context_pronouns("5 כפול 5", "chat1", _LTR_SESSION) == "5 כפול 5")


# ══════════════════════════════════════════════════
# Generalizes to every CONTEXT_PRONOUNS entry, not just "זה"
# ══════════════════════════════════════════════════

print("\n── generalizes across all context pronouns ─────")

_ORDINARY_SENTENCES = {
    "זה":    "כמה זה עולה",
    "אותו":  "אני מכיר אותו כבר שנים",
    "ההוא":  "שמעתי על זה מההוא בעבודה",
    "הקודם": "זה קרה בחודש הקודם",
}
for pronoun, sentence in _ORDINARY_SENTENCES.items():
    resolved = app.resolve_context_pronouns(sentence, "chat1", _LTR_SESSION)
    chk(f'ordinary sentence using "{pronoun}" ({sentence!r}) no longer trips Tier-4',
        _TABLE_RE.search(resolved) is None)
    # sanity: substitution still actually happened (fix must not silently
    # disable the pronoun-resolution feature itself)
    chk(f'"{pronoun}" substitution still occurred (feature not silently disabled)',
        resolved != sentence)

for pronoun, ref_type in app.CONTEXT_PRONOUNS.items():
    if ref_type != "last_file":
        continue
    resolved = app.resolve_context_pronouns(f"תעלה את {pronoun} בבקשה", "chat1", _LUF_SESSION)
    chk(f'"{pronoun}" (last_file) substitution with a pipe-bearing filename does not trip Tier-4',
        _TABLE_RE.search(resolved) is None)


# ══════════════════════════════════════════════════
# Follow-up: real _MEMORABLE_TOOLS summaries embedding raw Airtable
# record_ids — a trigger class the pipe/tab/box-char sanitizer alone does
# NOT cover (_AIRTABLE_ID_RE is independent of _TABLE_RE). Checked against
# the REAL classify_ingress()/_is_tier4(), not the reproduced _TABLE_RE
# above, since the whole point is these trip a DIFFERENT trigger.
# ══════════════════════════════════════════════════

print("\n── record_id-bearing tool summaries (airtable_add/update, tma_write) ──")

_RECORD_ID_SUMMARIES = {
    "airtable_update": "✅ רשומה recABC123XYZ עודכנה.",
    "airtable_add":    "✅ רשומה נוספה | ID: recXYZ789ABC",
    "tma_write":       "✅ בוצע: עדכון ליד | מזהה: recQWE456RTY",
}
for tool_name, summary in _RECORD_ID_SUMMARIES.items():
    session = {"last_tool_result": {"tool": tool_name, "summary": summary}}
    msg = "תעדכן גם את זה בבקשה"
    resolved = app.resolve_context_pronouns(msg, "chat1", session)
    t4, reason = _is_tier4(resolved)
    chk(f"{tool_name} summary substitution no longer trips the real Tier-4 classifier "
        f"(was reason=airtable_id): {resolved!r}",
        t4 is False)
    chk(f"{tool_name}: substitution still occurred (feature not silently disabled)",
        resolved != msg)

# Sanity: a summary with NO trigger content at all still gets quoted verbatim
# — the fallback only kicks in when quoting would actually be unsafe.
_safe_session = {"last_tool_result": {"tool": "calendar_create_event", "summary": "📅 אירוע נוצר בהצלחה"}}
_safe_resolved = app.resolve_context_pronouns("תעדכן את זה", "chat1", _safe_session)
chk("safe summary (no trigger content) is still quoted verbatim, not degraded to the generic fallback",
    "📅 אירוע נוצר בהצלחה" in _safe_resolved)


# ══════════════════════════════════════════════════
# _safe_context_quote() unit checks
# ══════════════════════════════════════════════════

print("\n── _safe_context_quote() unit checks ───────────")

chk("safe raw text is quoted verbatim",
    app._safe_context_quote("הפעולה", "שלום עולם", "FALLBACK") == "הפעולה «שלום עולם»")
chk("record_id-bearing raw text falls back instead of being quoted",
    app._safe_context_quote("הפעולה", "✅ רשומה recABC123XYZ עודכנה.", "FALLBACK") == "FALLBACK")
chk("pipe-bearing raw text (already sanitized away) is still quoted, not degraded",
    app._safe_context_quote("הפעולה", "a | b | c", "FALLBACK") == "הפעולה «a · b · c»")


# ══════════════════════════════════════════════════
# _sanitize_for_free_text() unit checks
# ══════════════════════════════════════════════════

print("\n── _sanitize_for_free_text() unit checks ───────")

chk("pipes replaced with middle dot",
    app._sanitize_for_free_text("a | b | c") == "a · b · c")
chk("tabs replaced with space",
    app._sanitize_for_free_text("a\tb\tc") == "a b c")
chk("box-drawing chars stripped",
    app._sanitize_for_free_text("a│b┃c") == "abc")
chk("plain text unaffected",
    app._sanitize_for_free_text("שלום עולם") == "שלום עולם")


# ══════════════════════════════════════════════════
# Summary
# ══════════════════════════════════════════════════

print(f"\n{'='*40}")
print(f"  {passed}/{passed+failed} passed")
if failed:
    print(f"  {failed} FAILED")
    sys.exit(1)
else:
    print("  All OK ✅")
