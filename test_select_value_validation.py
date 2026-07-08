#!/usr/bin/env python3
"""
test_select_value_validation.py — Regression tests for PR2 rev.2 select-value
validation in tools/airtable_gateway.py (_provider_invalid_select_values(),
and its off/shadow/enforce integration into validate_airtable_fields()).

מאמת:
1. mode="full", ערך singleSelect תקין → עובר.
2. mode="full", ערך singleSelect לא תקין, state=enforce → מוסר, שגיאה נרשמת.
3. אותו ערך לא תקין, state=shadow → השדה נשאר ב-clean, רק מלוגג אזהרה.
4. multipleSelects כולו תקין → עובר; ערך אחד לא תקין → כל השדה מוסר ב-enforce
   (ללא סינון חלקי).
5. mode="name_only" (seed fallback) → value validation מדולג לגמרי, תמיד.
6. שדה עם choices ריק גם ב-mode="full" → מדולג (אין false positive).
7. state=off → הפרובידר לא נקרא כלל לבדיקת ערכים.
8. הרכבה נכונה עם unknown-field guard (PR3B) — שדה לא ידוע מדווח כ"unknown"
   בלבד, לא גם כ-value error כפול.
"""

from __future__ import annotations

import logging
import sys
from unittest.mock import patch

logging.basicConfig(level=logging.WARNING)

from tools.airtable_gateway import validate_airtable_fields

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


def _contract(fields: dict, mode: str = "full") -> dict:
    return {
        "table_id": "tblAAA",
        "mode": mode,
        "source": "live",
        "fetched_at": "now",
        "fields": fields,
    }


class _FakeProvider:
    def __init__(self, contract: dict):
        self._contract = contract

    def get_table_contract(self, table):
        return self._contract


_LEADS_CONTRACT_FULL = _contract({
    "Name": {"field_id": "fldZZZ", "type": "singleLineText", "choices": []},
    "Domain": {"field_id": "fldYYY", "type": "singleSelect", "choices": ["Real Estate", "Import"]},
    "Tags": {"field_id": "fldTAG", "type": "multipleSelects", "choices": ["Hot", "Cold", "VIP"]},
    "Notes": {"field_id": "fldNOT", "type": "multilineText", "choices": []},
    "EmptyChoiceSelect": {"field_id": "fldEMP", "type": "singleSelect", "choices": []},
})

_LEADS_CONTRACT_SEED = {
    "table_id": None,
    "mode": "name_only",
    "source": "seed",
    "fetched_at": None,
    "fields": {"Name": {"field_id": None, "type": None, "choices": []},
               "Domain": {"field_id": None, "type": None, "choices": []}},
}


def _patched(contract, state):
    # schema_validator.validate_fields is patched to [] so the (unrelated,
    # already-shipped) unknown-field guard never interferes with these
    # value-validation-only tests — real schema_cache.json doesn't have
    # "Domain"/"Tags" for Leads, which would otherwise get dropped as
    # "unknown" before value validation even runs.
    return (
        patch("feature_flags.get_select_value_validation_state", return_value=state),
        patch("feature_flags.get_runtime_schema_provider_state", return_value="off"),
        patch("core.runtime_schema_provider.get_provider", return_value=_FakeProvider(contract)),
        patch("schema_validator.validate_fields", return_value=[]),
    )


# ══════════════════════════════════════════════════════════════════
# 1. mode=full, valid singleSelect value → passes
# ══════════════════════════════════════════════════════════════════
print("\n── valid singleSelect (mode=full) ────")

p1, p2, p3, p4 = _patched(_LEADS_CONTRACT_FULL, "enforce")
with p1, p2, p3, p4:
    clean, errs = validate_airtable_fields("Leads", {"Domain": "Real Estate"})
    chk("valid singleSelect value passes in enforce", clean.get("Domain") == "Real Estate")
    chk("no value-validation error for a valid value", not any("value validation" in e for e in errs))

# ══════════════════════════════════════════════════════════════════
# 2. mode=full, invalid singleSelect, state=enforce → dropped
# ══════════════════════════════════════════════════════════════════
print("\n── invalid singleSelect, enforce ─────")

p1, p2, p3, p4 = _patched(_LEADS_CONTRACT_FULL, "enforce")
with p1, p2, p3, p4:
    clean, errs = validate_airtable_fields("Leads", {"Domain": "real_estate"})
    chk("enforce: invalid singleSelect value dropped", "Domain" not in clean)
    chk(
        "enforce: error message matches required format",
        any(
            "Airtable value validation failed: table=Leads field=Domain value='real_estate'" in e
            for e in errs
        ),
    )

# ══════════════════════════════════════════════════════════════════
# 3. Same invalid value, state=shadow → not dropped, only logged
# ══════════════════════════════════════════════════════════════════
print("\n── invalid singleSelect, shadow ──────")

p1, p2, p3, p4 = _patched(_LEADS_CONTRACT_FULL, "shadow")
with p1, p2, p3, p4, patch("tools.airtable_gateway.logger") as mock_logger:
    clean, errs = validate_airtable_fields("Leads", {"Domain": "real_estate"})
    chk("shadow: invalid value NOT dropped", clean.get("Domain") == "real_estate")
    chk("shadow: no value-validation error recorded", not any("value validation" in e for e in errs))
    chk("shadow: warning logged", mock_logger.warning.called)

# ══════════════════════════════════════════════════════════════════
# 4. multipleSelects — all valid passes; one invalid drops whole field
# ══════════════════════════════════════════════════════════════════
print("\n── multipleSelects whole-field drop ──")

p1, p2, p3, p4 = _patched(_LEADS_CONTRACT_FULL, "enforce")
with p1, p2, p3, p4:
    clean, errs = validate_airtable_fields("Leads", {"Tags": ["Hot", "VIP"]})
    chk("multipleSelects all-valid passes", clean.get("Tags") == ["Hot", "VIP"])

    clean, errs = validate_airtable_fields("Leads", {"Tags": ["Hot", "Bogus"]})
    chk("multipleSelects with one invalid: whole field dropped", "Tags" not in clean)
    chk(
        "multipleSelects: no partial-list filtering happened",
        not any(isinstance(clean.get("Tags"), list) for _ in [0]),
    )

p1, p2, p3, p4 = _patched(_LEADS_CONTRACT_FULL, "shadow")
with p1, p2, p3, p4:
    clean, errs = validate_airtable_fields("Leads", {"Tags": ["Hot", "Bogus"]})
    chk("multipleSelects shadow: field kept whole (no partial filtering)", clean.get("Tags") == ["Hot", "Bogus"])

# ══════════════════════════════════════════════════════════════════
# 5. mode=name_only (seed) → value validation always skipped
# ══════════════════════════════════════════════════════════════════
print("\n── mode=name_only always skips ───────")

p1, p2, p3, p4 = _patched(_LEADS_CONTRACT_SEED, "enforce")
with p1, p2, p3, p4:
    clean, errs = validate_airtable_fields("Leads", {"Domain": "real_estate"})
    chk("name_only + enforce: invalid-looking value still passes (skipped)", clean.get("Domain") == "real_estate")
    chk("name_only: no value-validation error", not any("value validation" in e for e in errs))

# ══════════════════════════════════════════════════════════════════
# 6. Select field with empty choices even in mode=full → skipped
# ══════════════════════════════════════════════════════════════════
print("\n── empty choices → no false positive ─")

p1, p2, p3, p4 = _patched(_LEADS_CONTRACT_FULL, "enforce")
with p1, p2, p3, p4:
    clean, errs = validate_airtable_fields("Leads", {"EmptyChoiceSelect": "anything"})
    chk("select field with empty choices list is not blocked", clean.get("EmptyChoiceSelect") == "anything")

# ══════════════════════════════════════════════════════════════════
# 7. state=off → provider never called for value checks
# ══════════════════════════════════════════════════════════════════
print("\n── state=off ─────────────────────────")

with patch("feature_flags.get_select_value_validation_state", return_value="off"), \
     patch("feature_flags.get_runtime_schema_provider_state", return_value="off"), \
     patch("schema_validator.validate_fields", return_value=[]), \
     patch("core.runtime_schema_provider.get_provider") as mock_get_provider:
    clean, errs = validate_airtable_fields("Leads", {"Domain": "real_estate"})
    chk("state=off: value not touched at all", clean.get("Domain") == "real_estate")
    chk("state=off: provider never even called", not mock_get_provider.called)

# ══════════════════════════════════════════════════════════════════
# 8. Composition with unknown-field guard — no double reporting
# ══════════════════════════════════════════════════════════════════
print("\n── composition with unknown-field guard ─")

with patch("feature_flags.get_select_value_validation_state", return_value="enforce"), \
     patch("feature_flags.get_runtime_schema_provider_state", return_value="enforce"), \
     patch("core.runtime_schema_provider.get_provider", return_value=_FakeProvider(_LEADS_CONTRACT_FULL)):
    clean, errs = validate_airtable_fields("Leads", {"NotAField": "whatever"})
    chk("unknown field dropped once, as 'unknown field' only", "NotAField" not in clean)
    chk(
        "unknown field not double-reported as a value error",
        sum(1 for e in errs if "NotAField" in e) == 1,
    )

print(f"\n{'='*50}\n{passed} passed, {failed} failed\n{'='*50}")
sys.exit(1 if failed else 0)
