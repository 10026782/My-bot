#!/usr/bin/env python3
"""
test_runtime_schema_provider.py — Regression tests for
core/runtime_schema_provider.py (PR3B) and its Gateway SHADOW/ENFORCE
integration in tools/airtable_gateway.py.

מאמת:
1. Fresh schema משמש כשזמין.
2. refresh() כושל לא מוחק את ה-last_good.
3. fallback ל-snapshot JSON כשמוגדר וזמין.
4. fallback ל-schema_cache.json seed.
5. fail closed (schema ריק) כשכלום לא זמין.
6. Gateway קורא לפרובידר (לא ל-cache ישיר) כש-mode != off.
7. unknown-field blocking קיים ב-mode=off (ללא שינוי התנהגות).
8. SHADOW מלוגג discrepancy בלי לחסום כתיבה.
9. ENFORCE חוסם כתיבה ש-SHADOW רק היה מלוגג.
10. אין PR2 value validation עדיין (non-goal).
"""

from __future__ import annotations

import logging
import sys
from unittest.mock import MagicMock, patch

logging.basicConfig(level=logging.WARNING)

from core.runtime_schema_provider import RuntimeSchemaProvider
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


_FRESH_SCHEMA = {"Leads": {"Name": {"type": "singleLineText", "choices": []},
                            "Domain": {"type": "singleSelect", "choices": ["Real Estate", "Import"]}}}
_SNAPSHOT_SCHEMA = {"Leads": {"Name": {"type": "singleLineText", "choices": []}}}
_SEED_SCHEMA = {"Leads": {"Name": {"type": None, "choices": []}}}

# ══════════════════════════════════════════════════════════════════
# 1. Fresh schema used when available
# ══════════════════════════════════════════════════════════════════
print("\n── get_schema / refresh ──────────────")

p = RuntimeSchemaProvider()
with patch.object(p, "_fetch_fresh", return_value=_FRESH_SCHEMA):
    schema = p.get_schema()
    chk("get_schema returns fresh schema when fetch succeeds", schema == _FRESH_SCHEMA)
    chk("last_good_source is live_meta_api", p.last_good_source == "live_meta_api")

# ══════════════════════════════════════════════════════════════════
# 2. Failed refresh must not erase last_good
# ══════════════════════════════════════════════════════════════════
p2 = RuntimeSchemaProvider()
with patch.object(p2, "_fetch_fresh", return_value=_FRESH_SCHEMA):
    p2.refresh()
with patch.object(p2, "_fetch_fresh", return_value=None):
    ok = p2.refresh()
    chk("refresh() returns False on fetch failure", ok is False)
    chk("failed refresh does not erase last_good", p2.get_last_good() == _FRESH_SCHEMA)

# ══════════════════════════════════════════════════════════════════
# 3. Falls back to snapshot JSON when live fetch unavailable
# ══════════════════════════════════════════════════════════════════
p3 = RuntimeSchemaProvider()
with patch.object(p3, "_fetch_fresh", return_value=None), \
     patch.object(p3, "_load_latest_snapshot", return_value=_SNAPSHOT_SCHEMA):
    schema = p3.get_schema()
    chk("get_schema falls back to snapshot JSON", schema == _SNAPSHOT_SCHEMA)
    chk("last_good_source is snapshot", p3.last_good_source == "snapshot")

# ══════════════════════════════════════════════════════════════════
# 4. Falls back to schema_cache.json seed
# ══════════════════════════════════════════════════════════════════
p4 = RuntimeSchemaProvider()
with patch.object(p4, "_fetch_fresh", return_value=None), \
     patch.object(p4, "_load_latest_snapshot", return_value=None), \
     patch.object(p4, "load_seed_schema", return_value=_SEED_SCHEMA):
    schema = p4.get_schema()
    chk("get_schema falls back to schema_cache.json seed", schema == _SEED_SCHEMA)
    chk("last_good_source is seed", p4.last_good_source == "seed")

# ══════════════════════════════════════════════════════════════════
# 5. Fails closed when nothing available
# ══════════════════════════════════════════════════════════════════
p5 = RuntimeSchemaProvider()
with patch.object(p5, "_fetch_fresh", return_value=None), \
     patch.object(p5, "_load_latest_snapshot", return_value=None), \
     patch.object(p5, "load_seed_schema", return_value={}):
    schema = p5.get_schema()
    chk("get_schema returns empty (fail closed) when nothing is available", schema == {})
    chk("last_good_source is none", p5.last_good_source == "none")

# ══════════════════════════════════════════════════════════════════
# 6-10. Gateway integration — SHADOW / ENFORCE / OFF
# ══════════════════════════════════════════════════════════════════
print("\n── Gateway SHADOW/ENFORCE integration ─")


def _provider_with(schema):
    prov = RuntimeSchemaProvider()
    prov._last_good = schema
    return prov


# mode=off (default) — unchanged existing behavior, provider never consulted
with patch("feature_flags.get_schema_provider_mode", return_value="off"):
    clean, errs = validate_airtable_fields("Leads", {"Score": 80})
    chk("mode=off: existing unknown-field blocking behavior unchanged", "Score" in clean)

# A field the legacy schema_cache.json knows (e.g. "Score" in Leads) but the
# provider (deliberately) does NOT know, to exercise a real discrepancy.
_PROVIDER_MISSING_SCORE = {"Leads": {"Name": {"type": "singleLineText", "choices": []}}}

with patch("feature_flags.get_schema_provider_mode", return_value="shadow"), \
     patch("core.runtime_schema_provider.get_provider", return_value=_provider_with(_PROVIDER_MISSING_SCORE)):
    clean, errs = validate_airtable_fields("Leads", {"Score": 80})
    chk("SHADOW: does not block a write the provider would flag", "Score" in clean)

with patch("feature_flags.get_schema_provider_mode", return_value="enforce"), \
     patch("core.runtime_schema_provider.get_provider", return_value=_provider_with(_PROVIDER_MISSING_SCORE)):
    clean, errs = validate_airtable_fields("Leads", {"Score": 80})
    chk("ENFORCE: blocks a write SHADOW would have only logged", "Score" not in clean)
    chk("ENFORCE: error message reports unknown field", any("Score" in e for e in errs))

# Non-goal: no select-value (PR2) validation implemented yet — an
# out-of-choice value for a known field must still pass in this PR.
with patch("feature_flags.get_schema_provider_mode", return_value="enforce"), \
     patch("core.runtime_schema_provider.get_provider",
           return_value=_provider_with({"Leads": {"Domain": {"type": "singleSelect", "choices": ["Real Estate"]}}})):
    clean, errs = validate_airtable_fields("Leads", {"Domain": "real_estate"})
    chk(
        "non-goal: invalid select VALUE still passes in PR3B (PR2 not implemented yet)",
        clean.get("Domain") == "real_estate",
    )

print(f"\n{'='*50}\n{passed} passed, {failed} failed\n{'='*50}")
sys.exit(1 if failed else 0)
