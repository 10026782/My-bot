# test_c89_tier4_precedence.py — BUG-C89-TIER4-PRECEDENCE
#
# Table/export/system-output markers must win over lead extraction, not just
# for the original narrow set (WhatsApp export, pipe tables, bot-emoji
# blocks) but for the full marker set added here: CSV/table headers, Hebrew
# fixed-width tables, Airtable status/score readouts, memory_key/
# owner_dictation field leaks, and dotted-date WhatsApp timestamps.
#
# All checks run through core.ingress_classifier.classify_ingress() —
# the single Tier-4 gate reused by router.py's stop-gate and by
# core.lead_candidate_handler.handle_lead_candidate() (LCH). Fixing it here
# fixes both call sites; no separate late-stage patch.

import sys

from core.ingress_classifier import classify_ingress

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
# 1. View in Airtable + Status/Score
# ══════════════════════════════════════════════════
TEXT_1 = (
    "משה כהן\n"
    "Status: Warm\n"
    "Score: 50/100\n"
    "View in Airtable: https://airtable.com/appXXX/tblYYY/recZZZ"
)
ic1 = classify_ingress(TEXT_1)
chk("1. View in Airtable + Status/Score -> tier=4", ic1.tier == 4, f"got tier={ic1.tier} reason={ic1.reason}")
chk("1. no lead candidates extracted", len(ic1.candidates) == 0)

# ══════════════════════════════════════════════════
# 2. Bot output pasted with ✅/📋/🌤️
# ══════════════════════════════════════════════════
TEXT_2 = (
    "✅ בוצע: עדכון ליד\n"
    "📋 סיכום: 3 לידים נוספו\n"
    "🌤️ מזג אוויר: בהיר, 24 מעלות"
)
ic2 = classify_ingress(TEXT_2)
chk("2. bot output (✅/📋/🌤️) -> tier=4", ic2.tier == 4, f"got tier={ic2.tier} reason={ic2.reason}")

# ══════════════════════════════════════════════════
# 3. owner_dictation + boss_hq/...@lead + 50/100
# ══════════════════════════════════════════════════
TEXT_3 = "source: owner_dictation, memory_key: boss_hq/0501234567@lead, score: 50/100"
ic3 = classify_ingress(TEXT_3)
chk("3. owner_dictation/memory_key/score leak -> tier=4", ic3.tier == 4, f"got tier={ic3.tier} reason={ic3.reason}")

# ══════════════════════════════════════════════════
# 4. CSV headers
# ══════════════════════════════════════════════════
TEXT_4 = (
    "Name, Phone, City, Status\n"
    "Moshe Cohen, 0501234567, Tel Aviv, New\n"
    "Dana Levi, 0521234567, Haifa, New"
)
ic4 = classify_ingress(TEXT_4)
chk("4. CSV headers -> tier=4", ic4.tier == 4, f"got tier={ic4.tier} reason={ic4.reason}")
chk("4. no lead batch extracted", len(ic4.candidates) == 0)

# ══════════════════════════════════════════════════
# 5. Hebrew fixed-width table
# ══════════════════════════════════════════════════
TEXT_5 = (
    "שם        טלפון        עיר\n"
    "משה כהן    0501234567    תל אביב\n"
    "דנה לוי    0521234567    חיפה"
)
ic5 = classify_ingress(TEXT_5)
chk("5. Hebrew fixed-width table -> tier=4", ic5.tier == 4, f"got tier={ic5.tier} reason={ic5.reason}")
chk("5. not misclassified as clean_batch", not ic5.reason.startswith("clean_batch"))

# ══════════════════════════════════════════════════
# 6. Airtable rec ID
# ══════════════════════════════════════════════════
TEXT_6 = "נוצרה רשומה: recABC1234567890 בטבלת Leads"
ic6 = classify_ingress(TEXT_6)
chk("6. Airtable rec ID -> tier=4", ic6.tier == 4, f"got tier={ic6.tier} reason={ic6.reason}")

# ══════════════════════════════════════════════════
# Extra: WhatsApp dotted-date timestamp (explicit format from the bug report)
# ══════════════════════════════════════════════════
TEXT_7 = "[04.07.2026, 10:15] משה: היי מה קורה"
ic7 = classify_ingress(TEXT_7)
chk("7. WhatsApp dotted-date timestamp -> tier=4", ic7.tier == 4, f"got tier={ic7.tier} reason={ic7.reason}")

# ══════════════════════════════════════════════════
# Regression guards — must NOT become Tier 4
# ══════════════════════════════════════════════════
CONTROL_LEAD = "משה כהן 0501234567 לחזור מחר"
ic_control = classify_ingress(CONTROL_LEAD)
chk("control: plain lead dictation stays tier=1", ic_control.tier == 1, f"got tier={ic_control.tier} reason={ic_control.reason}")

CONTROL_SYSTEM_CHECK = "תבדוק עכשיו את Airtable"
ic_sys = classify_ingress(CONTROL_SYSTEM_CHECK)
chk(
    "control: explicit system-check phrase ('תבדוק עכשיו את Airtable') is NOT tier=4",
    ic_sys.tier != 4,
    f"got tier={ic_sys.tier} reason={ic_sys.reason} — this must stay reachable for the real SYSTEM_STATUS check (BUG-IC-01/C89)",
)

CONTROL_BATCH = "משה כהן 0501234567\nדנה לוי 0521234567"
ic_batch = classify_ingress(CONTROL_BATCH)
chk(
    "control: genuine clean two-lead batch stays tier=2 (not swallowed by new markers)",
    ic_batch.tier == 2,
    f"got tier={ic_batch.tier} reason={ic_batch.reason}",
)

print(f"\n{'='*50}")
print(f"BUG-C89-TIER4-PRECEDENCE tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
