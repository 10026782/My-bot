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
# token and was not recognized as a stop-word at all.
#
# Fix: a single SHARED helper, _is_name_stop_token(), replaces every direct
# `token in _NAME_STOP` membership check in the name-segmentation/
# name-validation path (there were two: the segmentation loop in
# _extract_name_from_window(), and the "no stop-words" confidence bonus in
# _candidate_confidence() — fixing only one would have left the other on
# the old, incomplete check). Checks the exact token AND, if it starts with
# one of the single-letter Hebrew prefixes (ב/ל/כ/מ/ש/ו/ה), the remainder on
# its own. Scoped ONLY to this recognition check: no change to the +-80-char
# phone window, neighbor-phone clipping, or _BLOCK_SEP. Deliberately does
# NOT recurse (no stacked-prefix handling, e.g. "ובקומה" = ו+ב+קומה — no
# production reproduction for that shape) and does no stemming/morphology.

import os, sys
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:TEST")
os.environ.setdefault("AIRTABLE_API_KEY", "patTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

from unittest.mock import patch

import core.ingress_classifier as ic
from core.ingress_classifier import (
    _extract_lead_candidates,
    _is_name_stop_token,
    _NAME_STOP,
    classify_ingress,
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


# ── Required behavior: _is_name_stop_token() itself ───────────────────────
print("── Direct: _is_name_stop_token() required behaviors ──")

chk("T1: 'קומה' (bare) is a stop token", _is_name_stop_token("קומה"))
chk("T2: 'בקומה' (single prefix) is a stop token", _is_name_stop_token("בקומה"))
chk("T3: 'לקומה' (single prefix) is a stop token", _is_name_stop_token("לקומה"))
chk("T4: 'מהדירה' (two stacked prefixes: מ+ה+דירה) is NOT matched — "
    "out of scope, no reproduction for stacked prefixes",
    not _is_name_stop_token("מהדירה"))
chk("T5: 'בנימין' remains a valid name token", not _is_name_stop_token("בנימין"))
chk("T6: 'משה' remains a valid name token", not _is_name_stop_token("משה"))
chk("T7: 'הלל' remains a valid name token", not _is_name_stop_token("הלל"))
chk("T8: 'שחר' remains a valid name token", not _is_name_stop_token("שחר"))


# ── The exact production failure: no name at all ──────────────────────────
print()
print("── Production repro: no real name in the text at all ──")

NO_NAME = "צור ליד חדש מעוניין בדירת 4 חדרים בקומה חמישית טלפון 0501234571"
cands = _extract_lead_candidates(NO_NAME)
chk("T9: no candidate produced (was: name='בקומה')", cands == [])

result = classify_ingress(NO_NAME, source_type="text")
chk("T10: classify_ingress degrades to Tier 5 (no_lead_candidates), not a false Tier 1",
    result.tier == 5)


# ── Required regression case: a real name with "בקומה" in the description ─
print()
print("── Required: real name still recovered when the description uses 'בקומה' ──")

REAL_NAME = "צור ליד חדש יעל רייך מעוניינת בדירת 2 חדרים בקומה ראשונה טלפון 0503234568"
cands = _extract_lead_candidates(REAL_NAME)
chk("T11: name='יעל רייך' recovered correctly", len(cands) == 1 and cands[0]["name"] == "יעל רייך")
chk("T12: phone correct", len(cands) == 1 and cands[0]["phone"] == "0503234568")


# ── Mutation check: prove the helper is load-bearing, not incidental ─────
print()
print("── Mutation check: naive `token in _NAME_STOP` (no helper) reintroduces the bug ──")


def _naive_membership_only(token: str) -> bool:
    """The OLD, incomplete check this fix replaces — exact-match only."""
    return token.strip() in _NAME_STOP


with patch.object(ic, "_is_name_stop_token", side_effect=_naive_membership_only):
    mutated_cands = ic._extract_lead_candidates(NO_NAME)
chk("T13: with the helper swapped for naive membership-only, the bug REAPPEARS "
    "('בקומה' comes back as a fake candidate) — proves the helper is load-bearing",
    len(mutated_cands) == 1 and mutated_cands[0]["name"] == "בקומה")

# Same check with the helper restored (guards against a broken `with` scope above)
cands_after = _extract_lead_candidates(NO_NAME)
chk("T14: with the helper restored, the no-name case is clean again", cands_after == [])


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
    chk(f"T{14+i}: case {i} still extracts '{expected_name}' correctly",
        len(cands) == 1 and cands[0]["name"] == expected_name and cands[0]["phone"] == expected_phone)

BATCH = (
    "אבי יוסף מעוניין בדירת 3 חדרים טלפון 0501934572\n"
    "משה אבן מחפש דירת 4 חדרים טלפון 0501284573"
)
cands = _extract_lead_candidates(BATCH)
names = sorted(c["name"] for c in cands)
chk("T18: batch case still extracts both names correctly",
    names == ["אבי יוסף", "משה אבן"])


# ── Regression: BUG-099b's own scenarios stay correct ─────────────────────
print()
print("── Regression: BUG-099b's description-before/after-phone scenarios ──")

T19 = "צור ליד חדש יעל רייס  מעוניינת בדירת 2 חדרים קומה ראשונה   065726763"
cands = _extract_lead_candidates(T19)
chk("T19: description-before-phone (099b's original repro) still recovers the name",
    len(cands) == 1 and cands[0]["name"] == "יעל רייס")

T20 = "יוסי יהלום טלפון 0736637363, מעוניין בדירת 4 חדרים בקומה חמישית"
cands = _extract_lead_candidates(T20)
chk("T20: description-after-phone still works",
    len(cands) == 1 and cands[0]["name"] == "יוסי יהלום")


print(f"\n{'='*50}")
print(f"BUG-099b.1 (no-name validation) tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
