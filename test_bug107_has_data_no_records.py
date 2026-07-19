#!/usr/bin/env python3
"""
test_bug107_has_data_no_records.py — BUG-107A: false MISMATCH on legitimate
empty results.

core/anti_hallucination.py::_has_data() treated ANY non-empty,
non-"❌"-prefixed tool-result string as "has data" — including the
codebase-wide "📭 ..." convention for a legitimate empty result (e.g.
airtable_tools.py's "📭 אין רשומות בטבלה '{table}'.", crm.py's
"📭 אין אנשי קשר פעילים", contact_resolver.py's "📭 אין אנשי קשר במערכת.").

That meant: whenever the agent said "לא מצאתי" (or similar) after ANY
combination of tool calls that legitimately found 0 records — with or
without an unrelated real error also present — verify_result_claim()
raised a false MISMATCH. This was NOT specific to the Deals table or to
any field-name typo; it could fire on any table, any time a search
legitimately came back empty.

Fix: "📭" now excluded from _has_data(), the same way "❌" already was.

Does not touch RP5/F52, UnifiedStatusFormatter, EvidenceFinalizer taxonomy,
ActionGateway lifecycle, TurnEnvelope, or feature flags.
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-bug107-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:BUG107_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patBug107Test")
os.environ.setdefault("AIRTABLE_BASE_ID", "appBug107Test")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

from core.anti_hallucination import _has_data, verify_result_claim  # noqa: E402
from core_knowledge import STATIC_MANIFEST  # noqa: E402

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


def _r(content):
    return {"content": content}


print("── Test 1: single legitimate empty-table result ───────────")
chk(
    '_has_data(["📭 אין רשומות בטבלה"]) is False',
    _has_data([_r("📭 אין רשומות בטבלה 'Deals'.")]) is False,
)

print("\n── Test 2: multiple legitimate empty results ───────────")
chk(
    "multiple 📭 results still == False",
    _has_data([
        _r("📭 אין רשומות בטבלה 'Deals'."),
        _r("📭 אין אנשי קשר פעילים"),
        _r("📭 אין עסקאות"),
    ]) is False,
)

print("\n── Test 3: empty results + agent says לא מצאתי => no false MISMATCH ──")
result3 = verify_result_claim(
    "לא מצאתי רשומות מתאימות.",
    [
        _r("📭 אין רשומות בטבלה 'Deals'."),
        _r("📭 אין אנשי קשר פעילים"),
    ],
)
chk("no MISMATCH when all results legitimately empty", result3.status == "ok")

print("\n── Test 4: real record/data result => has_data True (unchanged) ──")
chk(
    "structured dict with external_id => True",
    _has_data([_r({"ok": True, "external_id": "rec123"})]) is True,
)
chk(
    "non-empty, non-❌, non-📭 string => True",
    _has_data([_r("נמצאו 3 רשומות: ...")]) is True,
)

print("\n── Test 5: error/422 result is not data, but not clean no-data either ──")
chk(
    "❌ error alone still excluded from has_data (unchanged)",
    _has_data([_r("❌ Airtable 422: invalid formula")]) is False,
)
result5 = verify_result_claim(
    "לא מצאתי רשומות מתאימות.",
    [_r("❌ Airtable 422: invalid formula")],
)
chk(
    "an error result does not itself trigger MISMATCH",
    result5.status == "ok",
)

print("\n── Test 6: mixed 📭 + real ❌ error + negative claim (BUG-107's original scenario) ──")
result6 = verify_result_claim(
    "לא מצאתי את שמואל כהן במערכת.",
    [
        _r("📭 אין רשומות בטבלה 'Leads'."),
        _r("📭 אין אנשי קשר פעילים"),
        _r("❌ Airtable 422: invalid formula for Deals"),
    ],
)
chk(
    "no false MISMATCH for the registered BUG-107 scenario (📭 + 📭 + ❌)",
    result6.status == "ok",
)

print("\n── Test 7: 📭 + a real data result still counts as has_data (unchanged) ──")
chk(
    "one real result among 📭 results => has_data True",
    _has_data([
        _r("📭 אין רשומות בטבלה 'Deals'."),
        _r("נמצאה רשומה אחת: ..."),
    ]) is True,
)

print("\n── Test 8 (BUG-107B): Deals search guidance uses correct field name ──")
chk(
    "STATIC_MANIFEST documents the correct Deals name field {שם העסקה}",
    "{שם העסקה}" in STATIC_MANIFEST,
)
chk(
    "STATIC_MANIFEST does not instruct SEARCH(..., {שם}) for Deals",
    "SEARCH('[שם]', {שם})" not in STATIC_MANIFEST,
)

print(f"\n{'='*50}")
print(f"BUG-107 tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
