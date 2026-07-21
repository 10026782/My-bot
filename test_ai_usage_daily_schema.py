#!/usr/bin/env python3
"""
test_ai_usage_daily_schema.py — Regression test for the AI_Usage_Daily
Airtable-field-name bug (Cost Telemetry Reliability PR, Part B).

The live Airtable field was "﻿Date" (BOM-prefixed, from a historical
CSV import) while every write path sent plain "Date" — a mismatch
Airtable's REST API rejects with 422 UNKNOWN_FIELD_NAME. Because
schema_cache.json had no entry at all for AI_Usage_Daily,
schema_validator.validate_fields() "failed open" (no info about the table
-> don't block), so the bad write reached Airtable and failed there,
silently, on every scheduled run.

The field has since been corrected manually in Airtable (BOM -> plain
"Date", via a Date_tmp swap — see PR description). This test does NOT
adapt code to the BOM; it guards against the schema regressing again:
  1. schema_cache.json has an AI_Usage_Daily entry at all (empty/missing
     is what let this slip through unnoticed).
  2. The known field names are exactly what core/cost_watchdog.py writes,
     and none of them contain a BOM or other non-printable character.
  3. normalize_airtable_fields() + validate_airtable_fields() round-trip
     that exact field set with zero fields dropped (offline — no network).
"""

from __future__ import annotations

import json
import sys

from tools.airtable_gateway import normalize_airtable_fields, validate_airtable_fields

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


TABLE = "AI_Usage_Daily"
EXPECTED_FIELDS = {"Date", "claude_sonnet", "claude_haiku", "whatsapp_conversation", "total_units"}

with open("schema_cache.json", "r", encoding="utf-8") as f:
    cache = json.load(f)

print("\n── AI_Usage_Daily schema regression ────────────────")

known = set(cache.get("tables", {}).get(TABLE, []))
chk("schema_cache.json has an AI_Usage_Daily entry", bool(known))
chk("known fields == expected projection fields", known == EXPECTED_FIELDS)

for field in known:
    chk(f"field name {field!r} has no BOM/control chars", field.isprintable() and not field.startswith("\ufeff"))

# Simulate exactly what core/cost_watchdog.py::_write_airtable_row() sends.
write_payload = {
    "Date": "2026-07-21",
    "claude_sonnet": 100,
    "claude_haiku": 200,
    "whatsapp_conversation": 0,
    "total_units": 300,
}
normalized = normalize_airtable_fields(TABLE, write_payload)
clean, errors = validate_airtable_fields(TABLE, normalized)

chk("normalize_airtable_fields() is a no-op for this table (no aliases)", normalized == write_payload)
chk("validate_airtable_fields() drops nothing (the exact 422 regression)", set(clean.keys()) == set(write_payload.keys()))
chk("validate_airtable_fields() reports no errors", errors == [])

print(f"\n{'='*40}")
print(f"  {passed}/{passed+failed} passed")
if failed:
    print(f"  {failed} FAILED")
    sys.exit(1)
else:
    print("  All OK ✅")
