# test_bug094_batch_name_bleed.py — BUG-094 (BATCH-NAME-WINDOW-BLEED)
#
# parse_batch_dictation() built a fixed ±60-char text window around each
# phone number, then called _extract_name(window), which always returns the
# FIRST Hebrew-name match in the window (re.search/.finditer order), not the
# one nearest that candidate's own phone. When two lead blocks in a dictated
# batch sit close together (well within 120 combined chars — the common case
# for a short list like "אבי יוספי 050... אלי ישראלי 052..."), candidate 2's
# window still contained candidate 1's name, so _extract_name() returned
# candidate 1's name again for candidate 2.
#
# Observed in production (10/07/2026, via BUG-058's newly-working Tier-2
# resolver, which just forwarded the already-broken candidate list to
# _handle_batch): both leads got the same name ("אבי יוספי" for both), and
# _at_find_lead()'s loose SEARCH-by-name fallback formula then matched the
# just-created record for candidate 1 when looking up candidate 2, so both
# writes landed on the SAME Airtable record (one "create" + one silent
# "update" overwriting it) instead of two separate leads.
#
# Fix: each candidate's window is now also clipped at the neighboring phone
# match's position (previous phone's end / next phone's start), not just a
# fixed ±60 radius — so one candidate's window can no longer include another
# candidate's name at all.

import os, sys
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:TEST")
os.environ.setdefault("AIRTABLE_API_KEY", "patTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

os.environ["AIRTABLE_BASE_ID"] = "appTest"
os.environ["AIRTABLE_API_KEY"] = "patTest"

from unittest.mock import patch, MagicMock

import core.lead_candidate_handler as lch
from core.lead_candidate_handler import parse_batch_dictation

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


# ══════════════════════════════════════════════════
# The exact production shape: two close-together blocks, comma-separated
# ══════════════════════════════════════════════════
result = parse_batch_dictation("אבי יוספי 0501112223, אלי ישראלי 0523334445")
chk("BUG-094: 2 candidates extracted", len(result) == 2)
chk("BUG-094: candidate 1 keeps its own name",
    result[0]["name"] == "אבי יוספי" if len(result) == 2 else False)
chk("BUG-094: candidate 2 gets its OWN name, not candidate 1's",
    len(result) == 2 and result[1]["name"] == "אלי ישראלי")
chk("BUG-094: candidate 2's phone is correct",
    len(result) == 2 and result[1]["phone"] == "0523334445")
chk("BUG-094: names are not accidentally identical",
    len(result) == 2 and result[0]["name"] != result[1]["name"])


# ══════════════════════════════════════════════════
# Same bug shape with an explicit "ליד חדש:" prefix on each block
# ══════════════════════════════════════════════════
result2 = parse_batch_dictation("ליד חדש: אבי יוספי 0501112223\nליד חדש: אלי ישראלי 0523334445")
chk("BUG-094 (prefixed): 2 candidates extracted", len(result2) == 2)
chk("BUG-094 (prefixed): candidate 2 gets its own name",
    len(result2) == 2 and result2[1]["name"] == "אלי ישראלי")


# ══════════════════════════════════════════════════
# 3 close-together blocks — bleed could chain across more than 2
# ══════════════════════════════════════════════════
result3 = parse_batch_dictation("דני כהן 0501112223, רונית לוי 0523334445, יוסי מזרחי 0541112223")
chk("BUG-094 (3-way): 3 candidates extracted", len(result3) == 3)
if len(result3) == 3:
    names = [c["name"] for c in result3]
    chk("BUG-094 (3-way): all 3 names distinct", len(set(names)) == 3)
    chk("BUG-094 (3-way): candidate 1 correct", names[0] == "דני כהן")
    chk("BUG-094 (3-way): candidate 2 correct", names[1] == "רונית לוי")
    chk("BUG-094 (3-way): candidate 3 correct", names[2] == "יוסי מזרחי")


# ══════════════════════════════════════════════════
# Regression guard: existing well-separated batch (pre-existing test shape
# from test_tier2_silent_preview.py's BATCH_TEXT) must still work correctly —
# the clipping fix must not break the already-working case.
# ══════════════════════════════════════════════════
result4 = parse_batch_dictation("משה כהן 0501234567\nדנה לוי 0521234567")
chk("regression: 2 candidates extracted (newline-separated)", len(result4) == 2)
chk("regression: candidate 1 correct", len(result4) == 2 and result4[0]["name"] == "משה כהן")
chk("regression: candidate 2 correct", len(result4) == 2 and result4[1]["name"] == "דנה לוי")


# ══════════════════════════════════════════════════
# Regression guard: single-lead parsing (parse_lead_dictation, not touched
# by this fix) must still work — sanity only, not the bug's surface.
# ══════════════════════════════════════════════════
from core.lead_candidate_handler import parse_lead_dictation
single = parse_lead_dictation("שמו יוסי כהן 0501234567")
chk("regression: single-lead parse still works", single is not None and single["name"] == "יוסי כהן")


# ══════════════════════════════════════════════════
# _at_find_lead — the second, compounding root cause: a phone-blind
# name-only fallback match. Even with distinct names (BUG-094 fixed above),
# a genuinely new lead sharing a name substring with an unrelated existing
# lead must NOT be silently treated as "the same lead" when its phone
# doesn't match any returned record.
# ══════════════════════════════════════════════════

def _fake_get_factory(formula_to_records: dict):
    """Returns a fake httpx.get that maps filterByFormula -> canned records."""
    def _fake_get(url, headers=None, params=None, timeout=None):
        formula = params.get("filterByFormula", "")
        resp = MagicMock()
        resp.status_code = 200
        records = formula_to_records.get(formula, [])
        # Fallback: substring match for formulas we didn't enumerate exactly
        if not records:
            for key, recs in formula_to_records.items():
                if key in formula:
                    records = recs
                    break
        resp.json.return_value = {"records": records}
        return resp
    return _fake_get


UNRELATED_RECORD = [{
    "id": "recUNRELATED000001",
    "fields": {"Name": "אבי יוספי", "phone": "0509999999"},  # different phone
}]

with patch("httpx.get", side_effect=_fake_get_factory({"SEARCH": UNRELATED_RECORD})):
    result_id = lch._at_find_lead("אבי יוספי", "0501112223")

chk("BUG-094-B: name-only match with mismatched phone is NOT treated as existing",
    result_id is None)


EXACT_PHONE_RECORD = [{
    "id": "recEXACTMATCH00001",
    "fields": {"Name": "אבי יוספי", "phone": "0501112223"},
}]

with patch("httpx.get", side_effect=_fake_get_factory({"SEARCH": EXACT_PHONE_RECORD})):
    result_id2 = lch._at_find_lead("אבי יוספי", "0501112223")

chk("BUG-094-B: exact phone match still resolves correctly (no regression)",
    result_id2 == "recEXACTMATCH00001")


with patch("httpx.get", side_effect=_fake_get_factory({"SEARCH": UNRELATED_RECORD})):
    result_id3 = lch._at_find_lead("אבי יוספי", "")  # no phone at all — needs_phone path

chk("BUG-094-B: no phone given -> name-only match still used (unchanged intended fallback)",
    result_id3 == "recUNRELATED000001")


# ══════════════════════════════════════════════════
# BUG-094-C: RouterDomain meta-values (crm/internal) must never reach
# Airtable's Leads/Lead Events Domain field — normalized to "general".
# ══════════════════════════════════════════════════
chk("BUG-094-C: 'crm' (Router meta-domain) normalizes to 'general'",
    lch._lead_domain_key("crm") == "general")
chk("BUG-094-C: 'internal' (Router meta-domain) normalizes to 'general'",
    lch._lead_domain_key("internal") == "general")
chk("BUG-094-C: empty domain still normalizes to 'general' (unchanged)",
    lch._lead_domain_key("") == "general")
chk("BUG-094-C: 'general' stays 'general' (unchanged)",
    lch._lead_domain_key("general") == "general")
chk("BUG-094-C: real business domain passes through unchanged",
    lch._lead_domain_key("real_estate") == "real_estate")
chk("BUG-094-C: another real business domain passes through unchanged",
    lch._lead_domain_key("import") == "import")


print(f"\n{'='*50}")
print(f"BUG-094 (batch name-window bleed) tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
