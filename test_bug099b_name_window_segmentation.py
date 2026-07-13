# test_bug099b_name_window_segmentation.py — BUG-099b (name recovery beyond
# the +-80-char window's first-match limitation)
#
# BUG-099 (see BUG_AUDIT_LOG.md) split into three parts:
#   099a — extend _NAME_STOP with property-description vocabulary, so a
#          description like "חדרים קומה ראשונה" is rejected rather than
#          written as a lead's Name. Fixed the corruption (garbage Name),
#          but a description-before-phone candidate degraded to "no
#          candidate" — the real name was safely dropped, not recovered.
#   099b — THIS FILE. Recovers the real name instead of just dropping it.
#   099c — not started (fallback form when LCH can't extract at all).
#
# Root cause (confirmed by direct reproduction, not assumed): a single
# _HEBREW_NAME_RE match is one CONTIGUOUS run of Hebrew words, broken only
# by digits/punctuation — not by stop-words. In
# "צור ליד חדש יעל רייס  מעוניינת בדירת 2 חדרים..." the whole run
# "צור ליד חדש יעל רייס  מעוניינת בדירת" is ONE match (no digit/punctuation
# breaks it), with "ליד"/"חדש" sitting between the command prefix and the
# real name "יעל רייס", and "מעוניינת" right after it. The prior logic only
# trimmed stop-words off the END of a match and rejected the whole thing if
# ANY stop-word remained — so the whole run (containing "ליד"/"חדש") was
# discarded, "יעל רייס" included.
#
# Fix (_extract_name_from_window, core/ingress_classifier.py): stop-words
# now split a matched run into segments (acting as separators, not just a
# trim target), and the LONGEST surviving segment is used. This changes
# ONLY which words within an already-bounded match get picked as the name —
# it does not touch the +-80-char phone window, neighbor-phone clipping, or
# _BLOCK_SEP (BUG-096/097/101b), so it cannot reopen the cross-candidate or
# cross-message bleed those fixes closed. Verified below (T7-T9).

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


# ── Required scenario 1: property-description BEFORE the phone ───────────
print("── Scenario 1: description before phone (recRvK6hFTNgyj8ag repro) ──")

T1 = "צור ליד חדש יעל רייס  מעוניינת בדירת 2 חדרים קומה ראשונה   065726763"
cands = _extract_lead_candidates(T1)
chk("T1: exactly one candidate", len(cands) == 1)
chk("T1: real name 'יעל רייס' recovered (not the garbage description, not dropped)",
    len(cands) == 1 and cands[0]["name"] == "יעל רייס")
chk("T1: phone correct", len(cands) == 1 and cands[0]["phone"] == "065726763")

ic = classify_ingress(T1, source_type="text")
chk("T1: classify_ingress resolves to Tier 1 (single high-confidence candidate)", ic.tier == 1)

T1b = "יוסי יהלום מעוניין בדירת 4 חדרים בקומה חמישית, טלפון 0736637363"
cands = _extract_lead_candidates(T1b)
chk("T1b: comma variant also recovers the real name", len(cands) == 1 and cands[0]["name"] == "יוסי יהלום")


# ── Required scenario 2: property-description AFTER the phone ────────────
print()
print("── Scenario 2: description after phone (already worked — must stay working) ──")

T2 = "יוסי יהלום טלפון 0736637363, מעוניין בדירת 4 חדרים בקומה חמישית"
cands = _extract_lead_candidates(T2)
chk("T2: name still correct when description trails the phone",
    len(cands) == 1 and cands[0]["name"] == "יוסי יהלום")

T2b = "צור ליד: ישראל כהן, טלפון 0521234567, מעוניין בדירת 3 חדרים"
cands = _extract_lead_candidates(T2b)
chk("T2b: plain control case (no collision) unaffected",
    any(c["name"] == "ישראל כהן" for c in cands))


# ── Coordination guards: 096/097/101b's fixes are not reopened ───────────
print()
print("── Coordination: 096 (batch window-bleed) is not reopened ──")

BATCH = "אבי יוספי 0501112223, אלי ישראלי 0523334445"
cands = _extract_lead_candidates(BATCH)
names = sorted(c["name"] for c in cands)
chk("T3: two distinct candidates, not the same name bled across both",
    names == ["אבי יוספי", "אלי ישראלי"])

print()
print("── Coordination: 097 (trailing intent-verb) is not reopened ──")

VERB = "משה אבני מעוניין ב3 חדרים 0546546345"
cands = _extract_lead_candidates(VERB)
chk("T4: 'מעוניין' still excluded from the name",
    len(cands) == 1 and cands[0]["name"] == "משה אבני")

print()
print("── Coordination: 101b (chat-export block boundary) is not reopened ──")

EXPORT = (
    "[12.9.2023, 14:38] אורי צדוק: ד דב אטינגר טבריה\n"
    "0527118045\n"
    "לחזור בערב. רוצה להתקדם.\n"
    "[8.4.2024, 20:18] אליהו: ד שמואל טבריה\n"
    "+972527163148\n"
    "עומד להתקשר. רציני.\n"
)
cands = _extract_lead_candidates(EXPORT)
phones = {c["name"]: c["phone"] for c in cands}
chk("T5: דב אטינגר still isolated to his own block/phone (no cross-message bleed)",
    phones.get("דב אטינגר") == "0527118045")
chk("T6: שמואל still isolated to his own block/phone",
    phones.get("שמואל") == "0527163148")


# ── Direct segmentation-logic checks ──────────────────────────────────────
print()
print("── Direct: stop-words split a run into segments, longest one wins ──")

from core.ingress_classifier import _extract_name_from_window, _HEBREW_NAME_RE

chk("T7: a name flanked by stop-words on both sides is isolated",
    _extract_name_from_window("ליד חדש דוד לוי מעוניין עכשיו", set()) == "דוד לוי")
chk("T8: no surviving segment >= 4 chars -> None (pure stop-word run)",
    _extract_name_from_window("קומה ראשונה שנייה", set()) is None)
chk("T9: sender-name exclusion still applies to the selected segment",
    _extract_name_from_window("דני כהן", {"דני כהן"}) is None)


print(f"\n{'='*50}")
print(f"BUG-099b (name-window segmentation) tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
