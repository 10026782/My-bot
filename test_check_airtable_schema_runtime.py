#!/usr/bin/env python3
"""
test_check_airtable_schema_runtime.py — PR3C (rev.2) regression tests for
tools/check_airtable_schema_runtime.py, the on-demand Airtable runtime
schema diagnostic.

מאמת:
1. env vars חסרים → fail closed, env_present=False, לא קורס.
2. Meta API נכשל → meta_api_reachable=False, לא קורס.
3. השוואת טבלאות: missing_in_airtable / unknown_to_code מדויקים.
4. snapshot_table_exists מזוהה נכון.
5. per-table contract: mode/source/field_count/select_field_count נכונים.
6. warnings ברמת טבלה: mode_not_full, source_is_seed.
7. warnings ברמת ערך: leading_space, trailing_space, repeated_space,
   punctuation_suspect, casing_variant, visually_similar_duplicate,
   hidden_control_chars.
8. אין נורמליזציה — הערכים המדווחים זהים בדיוק לערכי המקור (exact-string).
9. overall PASS/WARN מחושב נכון, כולל התאמה בין ה-marker לכל טבלה לבין ה-overall.
10. --json ו--dry-run: פלט תקין, אין secrets בפלט.
"""

from __future__ import annotations

import json
import logging
import sys
from unittest.mock import patch

logging.basicConfig(level=logging.WARNING)

from tools.check_airtable_schema_runtime import (
    run_diagnostic,
    _value_warnings,
    _examine_table_contract,
    _table_has_any_warning,
)
from core.runtime_schema_provider import RuntimeSchemaProvider

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
# 1. Missing env vars → fail closed
# ══════════════════════════════════════════════════════════════════
print("\n── missing env vars ──────────────────")

with patch.dict("os.environ", {"AIRTABLE_API_KEY": "", "AIRTABLE_BASE_ID": ""}, clear=False):
    r = run_diagnostic()
    chk("env_present False when vars missing", r["env_present"] is False)
    chk("does not crash, overall=FAIL", r["overall"] == "FAIL")
    chk("no secret-looking values in result", "fake_key" not in json.dumps(r))

# ══════════════════════════════════════════════════════════════════
# 2. Meta API failure → fail closed
# ══════════════════════════════════════════════════════════════════
print("\n── meta API failure ──────────────────")

with patch.dict("os.environ", {"AIRTABLE_API_KEY": "k", "AIRTABLE_BASE_ID": "appFAKE"}, clear=False), \
     patch("tools.schema_snapshot.fetch_live_schema", return_value=None):
    r = run_diagnostic()
    chk("meta_api_reachable False on failure", r["meta_api_reachable"] is False)
    chk("does not crash, overall=FAIL", r["overall"] == "FAIL")

# ══════════════════════════════════════════════════════════════════
# 3-6. Full run against a mocked live schema
# ══════════════════════════════════════════════════════════════════
print("\n── full run (mocked live schema) ─────")

_RAW_META = {
    "tables": [
        {"id": "tblLEADS", "name": "Leads", "fields": [
            {"id": "fldNAME", "name": "Name", "type": "singleLineText"},
            {"id": "fldDOM", "name": "Domain", "type": "singleSelect", "options": {"choices": [
                {"name": "Real Estate"},
                {"name": "Real .Estate "},
                {"name": "real estate"},
                {"name": "Import"},
            ]}},
        ]},
        {"id": "tblSNAP", "name": "System Schema Snapshots", "fields": []},
        {"id": "tblGHOST", "name": "Ghost Table Not In Code", "fields": []},
    ]
}


def _fake_fetch_live(self, table):
    for t in _RAW_META["tables"]:
        if t["name"] == table:
            return RuntimeSchemaProvider._build_entry(t)
    return None


import types

_fake_tables_ns = types.SimpleNamespace(
    LEADS="Leads",
    SCHEMA_SNAPSHOTS="System Schema Snapshots",
    SOME_MISSING_TABLE="Table Known To Code But Not Live",
)

with patch.dict("os.environ", {"AIRTABLE_API_KEY": "k", "AIRTABLE_BASE_ID": "appFAKE"}, clear=False), \
     patch("tools.schema_snapshot.fetch_live_schema", return_value=_RAW_META), \
     patch("core.runtime_schema_provider.RuntimeSchemaProvider._fetch_live", _fake_fetch_live), \
     patch("airtable_schema.Tables", _fake_tables_ns):
    r = run_diagnostic()

chk("tables_fetched matches live table count", r["tables_fetched"] == 3)
chk("live_table_names sorted and complete", r["live_table_names"] == [
    "Ghost Table Not In Code", "Leads", "System Schema Snapshots",
])
chk("missing_in_airtable finds code-only table",
    r["missing_in_airtable"] == ["Table Known To Code But Not Live"])
chk("unknown_to_code finds live-only table",
    r["unknown_to_code"] == ["Ghost Table Not In Code"])
chk("snapshot_table_exists True", r["snapshot_table_exists"] is True)

leads_report = r["table_reports"]["Leads"]
chk("Leads report mode=full", leads_report["mode"] == "full")
chk("Leads report source=live", leads_report["source"] == "live")
chk("Leads report field_count=2", leads_report["field_count"] == 2)
chk("Leads report select_field_count=1", leads_report["select_field_count"] == 1)
chk("Leads table-level warnings empty (mode=full, source=live)", leads_report["warnings"] == [])

snap_report = r["table_reports"]["System Schema Snapshots"]
chk("snapshot table report has no fields", snap_report["field_count"] == 0)

chk("overall is WARN due to select-value + comparison issues", r["overall"] == "WARN")

# ══════════════════════════════════════════════════════════════════
# 6. mode_not_full / source_is_seed table-level warnings
# ══════════════════════════════════════════════════════════════════
print("\n── table-level warnings (mode/source) ─")

seed_contract = {"table_id": None, "mode": "name_only", "source": "seed", "fields": {}}
seed_report = _examine_table_contract(seed_contract)
chk("mode_not_full warning present", "mode_not_full" in seed_report["warnings"])
chk("source_is_seed warning present", "source_is_seed" in seed_report["warnings"])
chk("_table_has_any_warning True for seed report", _table_has_any_warning(seed_report) is True)

full_contract = {"table_id": "tblX", "mode": "full", "source": "cached", "fields": {}}
full_report = _examine_table_contract(full_contract)
chk("no table warnings for mode=full/source=cached", full_report["warnings"] == [])
chk("_table_has_any_warning False for clean report", _table_has_any_warning(full_report) is False)

# ══════════════════════════════════════════════════════════════════
# 7. Value-level warnings — exact detection
# ══════════════════════════════════════════════════════════════════
print("\n── value-level warnings ──────────────")

chk("leading_space detected", "leading_space" in _value_warnings(" Real Estate", [" Real Estate"]))
chk("trailing_space detected", "trailing_space" in _value_warnings("Real Estate ", ["Real Estate "]))
chk("repeated_space detected", "repeated_space" in _value_warnings("Real  Estate", ["Real  Estate"]))
chk("punctuation_suspect detected (glued period)", "punctuation_suspect" in _value_warnings("Real .Estate", ["Real .Estate"]))
chk("no punctuation_suspect for normal value", "punctuation_suspect" not in _value_warnings("Real Estate", ["Real Estate"]))

siblings = ["Real Estate", "real estate", "Import"]
chk("casing_variant detected (case-only difference)", "casing_variant" in _value_warnings("Real Estate", siblings))
chk("casing_variant detected on the other side too", "casing_variant" in _value_warnings("real estate", siblings))
chk("no casing_variant for a value with no case-collision", "casing_variant" not in _value_warnings("Import", siblings))

similar_siblings = ["Real Estate", "Real Estatee", "Import"]
chk(
    "visually_similar_duplicate detected (near-identical, not case-collision)",
    "visually_similar_duplicate" in _value_warnings("Real Estate", similar_siblings),
)

chk("hidden_control_chars detected", "hidden_control_chars" in _value_warnings("Real\x00Estate", ["Real\x00Estate"]))
chk("no hidden_control_chars for Hebrew text with niqqud", "hidden_control_chars" not in _value_warnings("נדלַ\"ן", ["נדלַ\"ן"]))

chk("clean value has zero warnings", _value_warnings("Real Estate", ["Real Estate", "Import"]) == [])

# ══════════════════════════════════════════════════════════════════
# 8. No normalization — exact values preserved verbatim
# ══════════════════════════════════════════════════════════════════
print("\n── exact-value, no normalization ─────")

domain_field = leads_report["select_fields"][0]
raw_values = {c["value"] for c in domain_field["choices"]}
chk(
    "raw choice values preserved exactly (including the deliberate typo/trailing space)",
    raw_values == {"Real Estate", "Real .Estate ", "real estate", "Import"},
)
typo_choice = next(c for c in domain_field["choices"] if c["value"] == "Real .Estate ")
chk("quoted field uses JSON-escaped exact value", typo_choice["quoted"] == json.dumps("Real .Estate ", ensure_ascii=False))
chk("repr field is Python repr() of exact value", typo_choice["repr"] == repr("Real .Estate "))
chk("length field matches exact value length", typo_choice["length"] == len("Real .Estate "))

# ══════════════════════════════════════════════════════════════════
# 9. Per-table marker matches overall aggregation logic
# ══════════════════════════════════════════════════════════════════
print("\n── marker/overall consistency ────────")

chk(
    "Leads report (has select-value warnings) flagged by _table_has_any_warning",
    _table_has_any_warning(leads_report) is True,
)
chk(
    "System Schema Snapshots report (clean) NOT flagged by _table_has_any_warning",
    _table_has_any_warning(snap_report) is False,
)

# ══════════════════════════════════════════════════════════════════
# 10. CLI: --json output is valid JSON, --dry-run required, no secrets
# ══════════════════════════════════════════════════════════════════
print("\n── CLI behavior ──────────────────────")

import subprocess

with patch.dict("os.environ", {"AIRTABLE_API_KEY": "super_secret_value_123", "AIRTABLE_BASE_ID": ""}, clear=False):
    proc = subprocess.run(
        [sys.executable, "tools/check_airtable_schema_runtime.py", "--dry-run", "--json"],
        capture_output=True, text=True, timeout=30,
    )
    chk("CLI --dry-run --json exits cleanly", proc.returncode in (0, 1))
    try:
        json.loads(proc.stdout)
        cli_json_valid = True
    except (json.JSONDecodeError, ValueError):
        cli_json_valid = False
    chk("CLI output is valid JSON", cli_json_valid)
    chk("CLI output never contains the secret key value", "super_secret_value_123" not in proc.stdout)

proc_no_flag = subprocess.run(
    [sys.executable, "tools/check_airtable_schema_runtime.py"],
    capture_output=True, text=True, timeout=30,
)
chk("CLI without --dry-run exits non-zero (refuses to run)", proc_no_flag.returncode == 1)

print(f"\n{'='*50}\n{passed} passed, {failed} failed\n{'='*50}")
sys.exit(1 if failed else 0)
