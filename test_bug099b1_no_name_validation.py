# test_bug099b1_no_name_validation.py — BUG-099b.1 (name-validation gap:
# no-name input still produced a candidate)
#
# BUG-099b (see BUG_AUDIT_LOG.md) fixed name RECOVERY when a real name
# existed, flanked by stop-words in the same contiguous _HEBREW_NAME_RE
# match. It did not fix the inverse case: when there is NO real name in the
# text at all, the segment-splitting logic could still pick a leftover
# non-stop-word fragment as if it were a name.
#
# Live production repro (12/07/2026, after PR #305 merged): a message with
# no name at all —
#   "צור ליד חדש מעוניין בדירת 4 חדרים בקומה חמישית טלפון 0501234571"
# — was identified as lead "*בקומה*" (0501234571).
#
# Root cause (confirmed by direct reproduction): "קומה" (floor) is in
# _NAME_STOP, but "בקומה" ("on/at-the-floor" — the same word with the
# single-letter Hebrew preposition "ב" attached, no space) is a DIFFERENT
# token and was not recognized as a stop-word at all. In the Hebrew-word run
# "חדרים בקומה חמישית טלפון", "חדרים"/"חמישית"/"טלפון" are all stop-words and
# split into their own (empty) segments, but "בקומה" survived as the only
# non-empty segment and was returned as the name.
#
# Fix: _is_stopword() (core/ingress_classifier.py) checks the exact word
# AND, if it starts with one of the single-letter Hebrew prefixes
# (ב/ל/כ/מ/ש/ו/ה), the remainder on its own — so "בקומה" now matches via its
# "קומה" remainder. Scoped ONLY to this recognition check: no change to the
# +-80-char phone window, neighbor-phone clipping, or _BLOCK_SEP.

import os, sys
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:TEST")
os.environ.setdefault("AIRTABLE_API_KEY", "patTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

from core.ingress_classifier import _extract_lead_candidates, _is_stopword, classify_ingress

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


# ── The exact production failure: no name at all ──────────────────────────
print("── Production repro: no real name in the text at all ──")

NO_NAME = "צור ליד חדש מעוניין בדירת 4 חדרים בקומה חמישית טלפון 0501234571"
cands = _extract_lead_candidates(NO_NAME)
chk("T1: no candidate produced (was: name='בקומה')", cands == [])

ic = classify_ingress(NO_NAME, source_type="text")
chk("T2: classify_ingress degrades to Tier 5 (no_lead_candidates), not a false Tier 1",
    ic.tier == 5)


# ── Direct check: the stop-word helper itself ─────────────────────────────
print()
print("── Direct: _is_stopword recognizes a single-letter-prefixed stop-word ──")

chk("T3: 'בקומה' (prefixed) is now a stop-word", _is_stopword("בקומה"))
chk("T4: 'קומה' (bare) is still a stop-word (regression)", _is_stopword("קומה"))
chk("T5: 'לחדרים' (prefixed) is a stop-word", _is_stopword("לחדרים"))
chk("T6: a real name is NOT treated as a stop-word just for starting with one of these letters",
    not _is_stopword("משה") and not _is_stopword("בר") and not _is_stopword("הדס"))


# ── Regression: the 4 other production cases from the same test round ────
print()
print("── Regression: the 4 cases that already worked in production stay correct ──")

cases = [
    ("צור ליד חדש יעל רייך מעוניינת בדירת 2 חדרים קומה ראשונה טלפון 0503234567",
     "יעל רייך", "0503234567"),
    ("צור ליד חדש יוני יהלום מעוניין בדירת 4 חדרים בקומה חמישית טלפון 0501534568",
     "יוני יהלום", "0501534568"),
    ("צור ליד חדש משה ישרלי מעוניין בדירת 3 חדרים קומה שנייה טלפון 0506234569",
     "משה ישרלי", "0506234569"),
]
for i, (text, expected_name, expected_phone) in enumerate(cases, start=1):
    cands = _extract_lead_candidates(text)
    chk(f"T{6+i}: case {i} still extracts '{expected_name}' correctly",
        len(cands) == 1 and cands[0]["name"] == expected_name and cands[0]["phone"] == expected_phone)

BATCH = (
    "אבי יוסף מעוניין בדירת 3 חדרים טלפון 0501934572\n"
    "משה אבן מחפש דירת 4 חדרים טלפון 0501284573"
)
cands = _extract_lead_candidates(BATCH)
names = sorted(c["name"] for c in cands)
chk("T10: batch case still extracts both names correctly",
    names == ["אבי יוסף", "משה אבן"])


# ── Regression: BUG-099b's own scenarios stay correct ─────────────────────
print()
print("── Regression: BUG-099b's description-before/after-phone scenarios ──")

T11 = "צור ליד חדש יעל רייס  מעוניינת בדירת 2 חדרים קומה ראשונה   065726763"
cands = _extract_lead_candidates(T11)
chk("T11: description-before-phone (099b's original repro) still recovers the name",
    len(cands) == 1 and cands[0]["name"] == "יעל רייס")

T12 = "יוסי יהלום טלפון 0736637363, מעוניין בדירת 4 חדרים בקומה חמישית"
cands = _extract_lead_candidates(T12)
chk("T12: description-after-phone still works",
    len(cands) == 1 and cands[0]["name"] == "יוסי יהלום")


print(f"\n{'='*50}")
print(f"BUG-099b.1 (no-name validation) tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
