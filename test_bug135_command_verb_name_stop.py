# test_bug135_command_verb_name_stop.py — BUG-135 (command-verb/self-quote
# words missing from _NAME_STOP produced fake candidate names)
#
# Two related production repros, both traced to the same class of gap:
#
# 1. Self-quote: "📋 זיהיתי ליד: *משה חביב* (0501112222)" — pasting/quoting
#    the bot's OWN confirmation-template text. "זיהיתי" sat right before the
#    real name inside one contiguous _HEBREW_NAME_RE match ("ליד" was
#    already a stop-word, "זיהיתי" was not) — segmentation isolated
#    "זיהיתי" alone as a bogus >=4-char candidate, and
#    _extract_name_from_window() returns on the FIRST regex match that
#    clears validation, so the real name in the second match ("משה חביב")
#    was never reached.
#
# 2. Delete commands: "תמחק איש קשר 0536272637" (no real name at all — just
#    the delete verb + the generic "contact" role-noun). This module has no
#    delete-specific handling (see core/router/intent_router.py's
#    DELETE_TASK pattern for the only delete intent that exists — nothing
#    for contacts/leads), so the text falls through to the same generic
#    name+phone extraction used for create/update. None of "תמחק"/"מחק"/
#    "הסר" were stop-words, so the verb survived as part of the fake name.
#
# Fix: add "זיהיתי" and the delete-verb set ("תמחק"/"מחק"/"הסר", mirroring
# the router's own DELETE_TASK verb vocabulary) to _NAME_STOP. That alone
# still leaves "איש קשר" (the bare role-noun-only remainder, e.g. from
# "תמחק איש קשר 0536272637") as a >=4-char surviving segment — "איש"/"קשר"
# are deliberately NOT blanket stop-words, since "איש קשר X" is a legitimate
# way to phrase a real candidate name (e.g. "תוסיף איש קשר בדיקה טלפון X"
# must keep extracting "איש קשר בדיקה" verbatim — existing, working
# production behavior, confirmed with the owner not to regress). So a
# narrow exact-phrase reject list (_GENERIC_NAME_PHRASES = {"איש קשר"})
# rejects ONLY the bare phrase with nothing else surviving alongside it.

import os, sys
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:TEST")
os.environ.setdefault("AIRTABLE_API_KEY", "patTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

from core.ingress_classifier import _extract_lead_candidates, classify_ingress

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


# ── Production repro 1: self-quoted bot confirmation text ─────────────────
print("── Self-quote: bot's own '📋 זיהיתי ליד: ...' template pasted back ──")

SELF_QUOTE = "📋 זיהיתי ליד: *משה חביב* (0501112222)"
cands = _extract_lead_candidates(SELF_QUOTE)
chk("T1: real name 'משה חביב' recovered (was: 'זיהיתי')",
    len(cands) == 1 and cands[0]["name"] == "משה חביב")
chk("T2: phone correct", len(cands) == 1 and cands[0]["phone"] == "0501112222")


# ── Production repro 2: delete-by-phone, no real name ──────────────────────
print()
print("── Delete commands with no real name (only 'איש קשר' role-noun) ──")

for verb in ("תמחק", "מחק", "הסר"):
    text = f"{verb} איש קשר 0536272637"
    cands = _extract_lead_candidates(text)
    chk(f"T3 ({verb}): no fake candidate produced for '{text}'", cands == [])

result = classify_ingress("תמחק איש קשר 0536272637", source_type="text")
chk("T4: classify_ingress degrades to Tier 5 (no_lead_candidates), not a false Tier 1",
    result.tier == 5)


# ── Regression: real names after these same verbs still extracted ─────────
print()
print("── Regression: a REAL name after תעדכן/delete verbs still recovered ──")

UPDATE_CASE = "תעדכן טלפון של ביבי נתניהו ל053434444"
cands = _extract_lead_candidates(UPDATE_CASE)
chk("T5: 'ביבי נתניהו' still recovered from an update command",
    len(cands) == 1 and cands[0]["name"] == "ביבי נתניהו")

DELETE_WITH_NAME = "תמחק את משה כהן טלפון 0501112222"
cands = _extract_lead_candidates(DELETE_WITH_NAME)
chk("T6: a real name after a delete verb is still recovered, not swallowed",
    len(cands) == 1 and cands[0]["name"] == "משה כהן")


# ── Regression: the working "test contact" case must NOT change ──────────
print()
print("── Regression: 'איש קשר X' (X present) must keep the FULL phrase ──")

ADD_CASE = "תוסיף איש קשר בדיקה טלפון 0500000000"
cands = _extract_lead_candidates(ADD_CASE)
chk("T7: 'איש קשר בדיקה' extracted verbatim, unchanged by the generic-phrase reject",
    len(cands) == 1 and cands[0]["name"] == "איש קשר בדיקה")
chk("T8: phone correct", len(cands) == 1 and cands[0]["phone"] == "0500000000")


print(f"\n{'='*50}")
print(f"BUG-135 (command-verb/self-quote name-stop) tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
