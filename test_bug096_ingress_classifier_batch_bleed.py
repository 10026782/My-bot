# test_bug096_ingress_classifier_batch_bleed.py — BUG-096 (LIVE-PATH-BATCH-BLEED)
#
# Correction of a real mistake: BUG-094/BUG-095 (see test_bug094_batch_name_bleed.py)
# were fixed in core/lead_candidate_handler.py's parse_batch_dictation()/
# parse_lead_dictation() — functions with ZERO live callers (grep confirms;
# the only callers were this session's own test files). The actual live path
# is core/ingress_classifier.py's _extract_lead_candidates(), a separate,
# duplicate implementation with the identical defect. Those earlier PRs never
# fixed the production bug — this file fixes and tests the real location.
#
# Root cause (identical shape to BUG-094/095, confirmed by exact production
# log reproduction): _extract_lead_candidates() built a fixed +/-80-char
# window around each recognized phone number with no neighbor-phone or
# block-boundary clipping. A malformed phone in the middle of a batch (not
# matched by _PHONE_RE at all) let that candidate's whole block — including
# their name — bleed into the next candidate's window, producing a garbled
# name attached to the wrong phone number.
#
# Fix: _extract_lead_candidates() now splits on _BLOCK_SEP (new in this
# file) before any phone/name extraction, mirroring the correct BUG-095
# design but applied where it actually matters. Each candidate also now
# carries "raw_text" (its own block only) — BUG-096-B, a distinct symptom
# found in the same production log: every candidate in a batch was written
# with the ENTIRE multi-lead message as its Summary/Lead-Event/memory text,
# leaking other candidates' details into each lead's own record.
#
# BUG-097 (also covered below) is a follow-up found in a second live
# production test after BUG-096 shipped: block-splitting correctly handled
# a malformed phone in the middle of a 3-candidate batch, but an interest
# verb ("מעוניין") right after a name — with the phone at the END of the
# block — leaked into the extracted name. Fixed via _NAME_STOP.

import os, sys
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:TEST")
os.environ.setdefault("AIRTABLE_API_KEY", "patTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

from unittest.mock import patch

from core.ingress_classifier import _extract_lead_candidates, classify_ingress
import core.lead_candidate_handler as lch

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


PROD_REPRO = (
    "אבי אבן 0543546354 מעוניין ב3 חדרים\n"
    "משה אבני 05647389 מעוניין ב4 חדרים\n"
    "שמואל גרין 0368028368 מעוניין ב5 חדרים"
)


# ══════════════════════════════════════════════════
# BUG-096: exact production reproduction, on the real live function
# ══════════════════════════════════════════════════
print("\n── BUG-096: production text via _extract_lead_candidates (the live path) ──")
result = _extract_lead_candidates(PROD_REPRO)
chk("2 candidates extracted (malformed-phone block dropped, not merged)", len(result) == 2)
if len(result) == 2:
    chk("candidate 1 is אבי אבן with his own phone",
        result[0]["name"] == "אבי אבן" and result[0]["phone"] == "0543546354")
    chk("candidate 2 is שמואל גרין (not garbled with משה אבני's leftovers)",
        result[1]["name"] == "שמואל גרין")
    chk("candidate 2 keeps HIS OWN phone, not misattributed",
        result[1]["phone"] == "0368028368")
    chk("'משה אבני' does not appear in any candidate's name",
        all("משה אבני" not in c["name"] for c in result))
    chk("no leftover context word ('חדרים') leaked into a name",
        all("חדרים" not in c["name"] for c in result))


# ══════════════════════════════════════════════════
# BUG-096: classify_ingress() end-to-end (the actual entry point used by
# handle_lead_candidate() in production)
# ══════════════════════════════════════════════════
print("\n── BUG-096: classify_ingress() end-to-end ──")
ic = classify_ingress(text=PROD_REPRO, source_type="text")
chk("tier=2 (clean batch)", ic.tier == 2)
chk("2 candidates on the IngressClassification (matches production log candidates=2)",
    len(ic.candidates) == 2)
if len(ic.candidates) == 2:
    chk("names correct and distinct via classify_ingress",
        ic.candidates[0]["name"] == "אבי אבן" and ic.candidates[1]["name"] == "שמואל גרין")


# ══════════════════════════════════════════════════
# BUG-096: regression guards — shapes already covered by BUG-094/095 must
# still work correctly through the real live function.
# ══════════════════════════════════════════════════
print("\n── BUG-096: regression guards (already-working shapes) ──")
REGRESSION_CASES = {
    "comma-separated same line": (
        "אבי יוספי 0501112223, אלי ישראלי 0523334445",
        ["אבי יוספי", "אלי ישראלי"],
    ),
    "prefixed newline": (
        "ליד חדש: אבי יוספי 0501112223\nליד חדש: אלי ישראלי 0523334445",
        ["אבי יוספי", "אלי ישראלי"],
    ),
    "3-way comma chained": (
        "דני כהן 0501112223, רונית לוי 0523334445, יוסי מזרחי 0541112223",
        ["דני כהן", "רונית לוי", "יוסי מזרחי"],
    ),
    "spaced newline": (
        "משה כהן 0501234567\nדנה לוי 0521234567",
        ["משה כהן", "דנה לוי"],
    ),
}
for label, (text, expected_names) in REGRESSION_CASES.items():
    result = _extract_lead_candidates(text)
    names = [c["name"] for c in result]
    chk(f"regression ({label}): correct candidate count", len(result) == len(expected_names))
    chk(f"regression ({label}): names match exactly", names == expected_names)


# ══════════════════════════════════════════════════
# BUG-097 (NAME-TRAILING-INTENT-VERB) — found in a second live production
# test, after BUG-096 shipped: with 3 candidates (one with a malformed
# phone), block-splitting correctly dropped the malformed one without
# corrupting a neighbor (BUG-096 working as intended) — but a NEW, narrower
# defect surfaced: when the phone sits at the END of a block (name ->
# interest-phrase -> phone, e.g. "משה אבני מעוניין ב3 חדרים 0546546345"),
# _HEBREW_NAME_RE greedily matches the whole contiguous Hebrew-word run
# including the interest verb ("מעוניין"), and _NAME_STOP had no entry to
# trim it off. Fixed: intent/interest verbs (מעוניין/רוצה/מחפש/צריך/מבקש +
# feminine/plural forms) added to _NAME_STOP so the existing trailing-word
# trim in _extract_name_from_window() strips them like any other stop-word.
# ══════════════════════════════════════════════════
print("\n── BUG-097: trailing intent verb no longer leaks into the name ──")
PROD_REPRO_2 = (
    "משה אבני  מעוניין ב3 חדרים 0546546345\n"
    "אורי כדורי 0768767  4 חדרים\n"
    "אלי חוטי 0768765678 דירת 5 חדרים"
)
result2 = _extract_lead_candidates(PROD_REPRO_2)
chk("BUG-097: 2 candidates extracted (אורי כדורי's malformed 7-digit phone dropped cleanly)",
    len(result2) == 2)
if len(result2) == 2:
    chk("BUG-097: candidate 1 name is exactly 'משה אבני' — 'מעוניין' not included",
        result2[0]["name"] == "משה אבני")
    chk("BUG-097: candidate 1 keeps the correct phone",
        result2[0]["phone"] == "0546546345")
    chk("BUG-097: candidate 2 is אלי חוטי, untouched by the fix",
        result2[1]["name"] == "אלי חוטי" and result2[1]["phone"] == "0768765678")
    chk("BUG-097: 'אורי כדורי' (malformed-phone block) does not appear as any candidate",
        all("אורי כדורי" not in c["name"] for c in result2))


# ══════════════════════════════════════════════════
# BUG-096-B: each candidate carries its own raw_text (its block only), not
# the whole batch message.
# ══════════════════════════════════════════════════
print("\n── BUG-096-B: per-candidate raw_text segmentation ──")
result = _extract_lead_candidates(PROD_REPRO)
if len(result) == 2:
    chk("candidate 1's raw_text contains only their own line",
        "אבי אבן" in result[0]["raw_text"] and "שמואל גרין" not in result[0]["raw_text"])
    chk("candidate 2's raw_text contains only their own line",
        "שמואל גרין" in result[1]["raw_text"] and "אבי אבן" not in result[1]["raw_text"])


# ══════════════════════════════════════════════════
# BUG-096-B: end-to-end through handle_lead_candidate() -> _handle_batch() ->
# _write_one_lead() — each lead must be written with its OWN segment as the
# Summary/Lead-Event/memory text, not the full multi-lead batch text.
# ══════════════════════════════════════════════════
print("\n── BUG-096-B: end-to-end write uses per-candidate text ──")

from dataclasses import dataclass


@dataclass
class MockIdentity:
    user_id:   str = "owner_1"
    role:      str = "owner"
    tenant_id: str = "boss_hq"
    domain_id: str = "general"

    @property
    def is_internal(self) -> bool:
        # Mirrors identity.Identity.is_internal (role-derived), not a
        # hardcoded True — Audit #9-2 fidelity fix.
        return self.role in ("owner", "partner", "manager", "employee")

    @property
    def memory_key(self) -> str:
        return f"{self.tenant_id}:{self.user_id}"


# Audit #9-2 fidelity: is_internal must be role-derived, not a fixed True.
chk("MockIdentity.is_internal True for internal role (owner)", MockIdentity(role="owner").is_internal is True)
chk("MockIdentity.is_internal False for external role (lead)", MockIdentity(role="lead").is_internal is False)


captured = []


def _fake_write_one_lead(identity, name, phone, text, channel, domain):
    captured.append((name, phone, text))
    return True, f"rec_{name}", "create"


identity = MockIdentity()
with patch.object(lch, "_write_one_lead", _fake_write_one_lead), \
     patch("feature_flags.is_enabled", return_value=True):
    lch.handle_lead_candidate(identity, PROD_REPRO, "chat_bug096_e2e", "whatsapp")

chk("both candidates were written", len(captured) == 2)
if len(captured) == 2:
    name1, phone1, text1 = captured[0]
    name2, phone2, text2 = captured[1]
    chk("candidate 1 written with own name/phone", name1 == "אבי אבן" and phone1 == "0543546354")
    chk("candidate 2 written with own name/phone", name2 == "שמואל גרין" and phone2 == "0368028368")
    chk("candidate 1's write text does NOT contain candidate 2's name",
        "שמואל גרין" not in text1)
    chk("candidate 2's write text does NOT contain candidate 1's name",
        "אבי אבן" not in text2)


print(f"\n{'='*50}")
print(f"BUG-096 (live-path batch bleed) tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
