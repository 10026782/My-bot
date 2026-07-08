#!/usr/bin/env python3
"""
test_runtime_schema_provider.py — Regression tests for
core/runtime_schema_provider.py (PR3B rev.2) and its Gateway shadow/enforce
integration in tools/airtable_gateway.py.

מאמת (DoD):
1. TTL בתוקף → אין Meta API call.
2. TTL פג + pull מצליח.
3. TTL פג + pull נכשל + last_good קיים → cached + WARNING.
4. cold start + אין last_good → seed + CRITICAL + mode="name_only".
5. Gateway: state=off משמר התנהגות קיימת, לא נוגע בפרובידר.
6. Gateway: state=shadow משווה ומלוגג, לא חוסם.
7. Gateway: state=enforce חוסם כתיבה ש-shadow רק היה מלוגג.
8. thread-safety: קריאות מקבילות לא קורסות ולא כופלות state בצורה לא עקבית.
"""

from __future__ import annotations

import logging
import sys
import threading
from unittest.mock import patch

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


_LIVE_ENTRY_LEADS = {
    "table_id": "tblAAA",
    "fields": {
        "Name": {"field_id": "fldZZZ", "type": "singleLineText", "choices": []},
        "Domain": {"field_id": "fldYYY", "type": "singleSelect", "choices": ["Real Estate", "Import"]},
    },
}


def _fresh_entry():
    import time
    entry = dict(_LIVE_ENTRY_LEADS)
    entry["fetched_at"] = "2026-07-08T00:00:00+00:00"
    entry["fetched_at_mono"] = time.monotonic()
    return entry


# ══════════════════════════════════════════════════════════════════
# 1. TTL valid → no Meta API call at all
# ══════════════════════════════════════════════════════════════════
print("\n── TTL valid — no Meta API call ──────")

p1 = RuntimeSchemaProvider(ttl_seconds=300)
p1._last_good["Leads"] = _fresh_entry()
with patch.object(p1, "_fetch_live") as mock_fetch:
    contract = p1.get_table_contract("Leads")
    chk("TTL valid: _fetch_live never called", not mock_fetch.called)
    chk("TTL valid: source=cached", contract["source"] == "cached")
    chk("TTL valid: mode=full", contract["mode"] == "full")
    chk("TTL valid: table_id preserved", contract["table_id"] == "tblAAA")
    chk("TTL valid: fields preserved", "Domain" in contract["fields"])

# ══════════════════════════════════════════════════════════════════
# 2. TTL expired + pull succeeds
# ══════════════════════════════════════════════════════════════════
print("\n── TTL expired + pull succeeds ───────")

p2 = RuntimeSchemaProvider(ttl_seconds=0)  # TTL=0 → always expired
p2._last_good["Leads"] = _fresh_entry()
_NEW_ENTRY = {
    "table_id": "tblAAA",
    "fields": {"Name": {"field_id": "fldZZZ", "type": "singleLineText", "choices": []}},
    "fetched_at": "2026-07-08T01:00:00+00:00",
}
import time as _time
_NEW_ENTRY["fetched_at_mono"] = _time.monotonic()
with patch.object(p2, "_fetch_live", return_value=_NEW_ENTRY):
    contract = p2.get_table_contract("Leads")
    chk("TTL expired + pull success: source=live", contract["source"] == "live")
    chk("TTL expired + pull success: uses fresh fields", "Domain" not in contract["fields"])

# ══════════════════════════════════════════════════════════════════
# 3. TTL expired + pull fails + last_good exists → cached + WARNING
# ══════════════════════════════════════════════════════════════════
print("\n── TTL expired + pull fails (stale) ──")

p3 = RuntimeSchemaProvider(ttl_seconds=0)
p3._last_good["Leads"] = _fresh_entry()
with patch.object(p3, "_fetch_live", return_value=None), \
     patch("core.runtime_schema_provider.logger") as mock_logger:
    contract = p3.get_table_contract("Leads")
    chk("stale fallback: source=cached", contract["source"] == "cached")
    chk("stale fallback: mode=full (still)", contract["mode"] == "full")
    chk("stale fallback: still serves old fields", contract["table_id"] == "tblAAA")
    chk("stale fallback: logs WARNING", mock_logger.warning.called)

# ══════════════════════════════════════════════════════════════════
# 4. Cold start + no last_good + live fails → seed + CRITICAL + name_only
# ══════════════════════════════════════════════════════════════════
print("\n── cold start — seed fallback ────────")

p4 = RuntimeSchemaProvider(ttl_seconds=300)
with patch.object(p4, "_fetch_live", return_value=None), \
     patch("schema_validator.get_known_fields", return_value={"Name", "Score"}), \
     patch("core.runtime_schema_provider.logger") as mock_logger:
    contract = p4.get_table_contract("Leads")
    chk("cold start: source=seed", contract["source"] == "seed")
    chk("cold start: mode=name_only", contract["mode"] == "name_only")
    chk("cold start: table_id is None", contract["table_id"] is None)
    chk("cold start: choices always empty", all(f["choices"] == [] for f in contract["fields"].values()))
    chk("cold start: field names from seed", contract["fields"].keys() == {"Name", "Score"})
    chk("cold start: logs CRITICAL", mock_logger.critical.called)

# ══════════════════════════════════════════════════════════════════
# 5-7. Gateway integration — off / shadow / enforce
# ══════════════════════════════════════════════════════════════════
print("\n── Gateway off/shadow/enforce ────────")


def _provider_with(contract: dict) -> RuntimeSchemaProvider:
    prov = RuntimeSchemaProvider()
    prov.get_table_contract = lambda table: contract  # type: ignore[assignment]
    return prov


# A contract that deliberately does NOT know "Score" (a field the legacy
# schema_cache.json path does know), to exercise a real discrepancy.
_CONTRACT_MISSING_SCORE = {
    "table_id": "tblAAA",
    "mode": "full",
    "source": "live",
    "fetched_at": "now",
    "fields": {"Name": {"field_id": "fldZZZ", "type": "singleLineText", "choices": []}},
}

with patch("feature_flags.get_runtime_schema_provider_state", return_value="off"), \
     patch("core.runtime_schema_provider.get_provider") as mock_get_provider:
    clean, errs = validate_airtable_fields("Leads", {"Score": 80})
    chk("state=off: existing unknown-field blocking behavior unchanged", "Score" in clean)
    chk("state=off: provider never even called", not mock_get_provider.called)

with patch("feature_flags.get_runtime_schema_provider_state", return_value="shadow"), \
     patch("core.runtime_schema_provider.get_provider",
           return_value=_provider_with(_CONTRACT_MISSING_SCORE)):
    clean, errs = validate_airtable_fields("Leads", {"Score": 80})
    chk("state=shadow: does not block a write the provider would flag", "Score" in clean)

with patch("feature_flags.get_runtime_schema_provider_state", return_value="enforce"), \
     patch("core.runtime_schema_provider.get_provider",
           return_value=_provider_with(_CONTRACT_MISSING_SCORE)):
    clean, errs = validate_airtable_fields("Leads", {"Score": 80})
    chk("state=enforce: blocks a write shadow would have only logged", "Score" not in clean)
    chk("state=enforce: error message reports unknown field", any("Score" in e for e in errs))

# ══════════════════════════════════════════════════════════════════
# 8. Thread-safety smoke test — concurrent calls don't crash or corrupt state
# ══════════════════════════════════════════════════════════════════
print("\n── thread-safety smoke test ──────────")

p8 = RuntimeSchemaProvider(ttl_seconds=300)
call_count = {"n": 0}
_lock = threading.Lock()


def _slow_fetch(table):
    with _lock:
        call_count["n"] += 1
    entry = dict(_LIVE_ENTRY_LEADS)
    entry["fetched_at"] = "2026-07-08T00:00:00+00:00"
    entry["fetched_at_mono"] = _time.monotonic()
    return entry


results = []
errors_seen = []


def _worker():
    try:
        results.append(p8.get_table_contract("Leads"))
    except Exception as e:
        errors_seen.append(e)


with patch.object(p8, "_fetch_live", side_effect=_slow_fetch):
    threads = [threading.Thread(target=_worker) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

chk("thread-safety: no exceptions across 20 concurrent calls", not errors_seen)
chk("thread-safety: all 20 calls got a contract", len(results) == 20)

print(f"\n{'='*50}\n{passed} passed, {failed} failed\n{'='*50}")
sys.exit(1 if failed else 0)
