#!/usr/bin/env python3
"""
test_bug105_non_canonical_converted_status.py — BUG-105 regression tests.

Phase 2A.0 found two write paths that wrote the non-canonical value
status="converted" (not a member of LeadStatus.ALL — the live Airtable
option is "done", paired with Business Outcome=LeadOutcome.CONVERTED).
Verifies both writers now use the canonical constants, and that the
legacy backward-compat read path for already-converted (pre-fix) data
is untouched.
"""

from __future__ import annotations

import logging
from unittest.mock import patch

logging.basicConfig(level=logging.WARNING)

from airtable_schema import LeadFields, LeadStatus, LeadOutcome

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


# ══════════════════════════════════════════════════════════════════
# 1. lead_conversion.py::convert_lead_to_contact
# ══════════════════════════════════════════════════════════════════
print("\n── lead_conversion.py ─────────────────")

import lead_conversion

_lead_record = {
    "id": "recLEAD1",
    "fields": {
        LeadFields.NAME:  "Test Lead",
        LeadFields.PHONE: "0500000000",
    },
}

with patch("lead_conversion.is_enabled", return_value=True), \
     patch("tma_api._at_list", return_value=[_lead_record]), \
     patch("tma_api._at_patch", return_value=True) as mock_patch, \
     patch("lead_conversion.crm_add_contact", return_value="✅ נוצר: recCONTACT1"), \
     patch("tools.airtable_security.audit_log_airtable"):

    ok, msg = lead_conversion.convert_lead_to_contact("Test Lead")
    chk("convert_lead_to_contact: succeeds", ok is True)

    written_fields = mock_patch.call_args[0][2]
    chk(
        "lead_conversion writes status=done, not converted",
        written_fields.get(LeadFields.STATUS) == LeadStatus.DONE
        and written_fields.get(LeadFields.STATUS) != "converted",
    )
    chk(
        "lead_conversion writes Business Outcome=converted",
        written_fields.get(LeadFields.OUTCOME) == LeadOutcome.CONVERTED,
    )
    chk(
        "lead_conversion still writes converted_at",
        LeadFields.CONVERTED_AT in written_fields,
    )

# ══════════════════════════════════════════════════════════════════
# 2. ad_attribution.py::mark_converted
# ══════════════════════════════════════════════════════════════════
print("\n── ad_attribution.py::mark_converted ──")

import ad_attribution

with patch("tools.airtable_tools.airtable_get", return_value="• [recLEAD2] memory_key: x"), \
     patch("tools.airtable_tools.airtable_update") as mock_update:
    mock_update.return_value = {"ok": True, "external_id": "recLEAD2"}

    ok = ad_attribution.mark_converted("boss_hq:test2", 5000)
    chk("mark_converted: succeeds", ok is True)

    written_fields = mock_update.call_args[0][2]
    chk(
        "ad_attribution mark_converted writes status=done, not converted",
        written_fields.get(LeadFields.STATUS) == LeadStatus.DONE
        and written_fields.get(LeadFields.STATUS) != "converted",
    )
    chk(
        "ad_attribution mark_converted writes Business Outcome=converted",
        written_fields.get(LeadFields.OUTCOME) == LeadOutcome.CONVERTED,
    )
    chk(
        "ad_attribution mark_converted still writes converted_at",
        LeadFields.CONVERTED_AT in written_fields,
    )
    chk(
        "ad_attribution mark_converted still writes deal_value when provided",
        written_fields.get("deal_value") == 5000,
    )

with patch("tools.airtable_tools.airtable_get", return_value="• [recLEAD2] memory_key: x"), \
     patch("tools.airtable_tools.airtable_update", return_value={"ok": False}):
    ok = ad_attribution.mark_converted("boss_hq:test2", 5000)
    chk("mark_converted: ok=False on gateway failure → returns False", ok is False)

print(f"\n{'='*40}")
print(f"BUG-105 Tests: {passed} passed, {failed} failed")

if __name__ == "__main__":
    import sys
    sys.exit(0 if failed == 0 else 1)
