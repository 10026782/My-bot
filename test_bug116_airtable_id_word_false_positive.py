# test_bug116_airtable_id_word_false_positive.py — BUG-116
#
# core.ingress_classifier._AIRTABLE_ID_RE ("\b(?:fld|rec)[A-Za-z0-9]{8,}\b")
# matched ordinary English words starting with "rec"/"fld" followed by 8+
# letters — e.g. "recruitment" ("rec" + "ruitment", 8 letters, no digits).
# Production evidence: "צור ליד חדש לדומיין recruitment \nיהודה גרוס
# 0533968395" was classified tier=4/reason=airtable_id and blocked with
# "📄 זה נראה כמו טבלה/ייצוא/פלט מודבק" before lead extraction ever ran —
# a plain, unambiguous lead-creation sentence with a real name and phone.
#
# Fix: require at least one digit in the matched run. Every genuine-ID test
# fixture already in this suite (recABC1234567890, recRvK6hFTNgyj8ag,
# rec3YS5Zcr2FenX7z, rec62b86WqBpaWPaG, ...) mixes letters and digits — a
# real English word never does. This is a pure tightening: true-positive
# detection of pasted Airtable IDs (test_c89_tier4_precedence.py's own
# "Airtable rec ID" case) is unaffected; see full-suite re-run note below.

import sys

from core.ingress_classifier import classify_ingress, _AIRTABLE_ID_RE

passed = failed = 0


def chk(desc: str, cond: bool, extra: str = "") -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}{(' — ' + extra) if extra else ''}")
        failed += 1


# ══════════════════════════════════════════════════
# 1. Exact production reproduction
# ══════════════════════════════════════════════════
TEXT_1 = "צור ליד חדש לדומיין recruitment \nיהודה גרוס  0533968395"
ic1 = classify_ingress(TEXT_1)
chk("1. plain lead sentence containing 'recruitment' is NOT tier=4",
    ic1.tier != 4, f"got tier={ic1.tier} reason={ic1.reason}")
chk("1. reason is not airtable_id",
    ic1.reason != "airtable_id", f"got reason={ic1.reason}")
chk("1. a lead candidate is extracted (name + phone survive)",
    len(ic1.candidates) == 1, f"got {ic1.candidates}")

# ══════════════════════════════════════════════════
# 2. Other plain English "rec"/"fld" words must not false-positive either
# ══════════════════════════════════════════════════
for word in ("recruitment", "recommendation", "reconnect", "reciprocity", "fieldwork"):
    chk(f"2. _AIRTABLE_ID_RE does not match plain word {word!r}",
        _AIRTABLE_ID_RE.search(word) is None)

# ══════════════════════════════════════════════════
# 3. Real Airtable IDs (with digits) still match — no regression to true
#    positives. Same fixtures already relied on elsewhere in this suite.
# ══════════════════════════════════════════════════
for rid in (
    "recABC1234567890", "recRvK6hFTNgyj8ag", "rec3YS5Zcr2FenX7z",
    "rec62b86WqBpaWPaG", "recTIER3TESTREC001", "fldSNAPFILE12345",
):
    chk(f"3. _AIRTABLE_ID_RE still matches real-looking id {rid!r}",
        _AIRTABLE_ID_RE.search(rid) is not None)

# ══════════════════════════════════════════════════
# 4. A pasted real Airtable ID still forces tier=4 end-to-end
# ══════════════════════════════════════════════════
TEXT_4 = "נוצרה רשומה: recABC1234567890 בטבלת Leads"
ic4 = classify_ingress(TEXT_4)
chk("4. genuine pasted record id still triggers tier=4",
    ic4.tier == 4, f"got tier={ic4.tier} reason={ic4.reason}")

print(f"\n{'='*50}")
print(f"BUG-116 airtable_id word false-positive tests: {passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
