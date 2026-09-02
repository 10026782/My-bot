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
import json
import sys
import threading
from pathlib import Path
from unittest.mock import patch

logging.basicConfig(level=logging.WARNING)

from core.runtime_schema_provider import RuntimeSchemaProvider
from tools.airtable_gateway import AirtableLookupError, validate_airtable_fields
import airtable_schema as schema

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


def _string_constants(fields_class) -> set[str]:
    return {
        value
        for name, value in vars(fields_class).items()
        if not name.startswith("_") and isinstance(value, str)
    }


# ══════════════════════════════════════════════════════════════════
# 0. Seed/cache contract alignment for the scoped Audit #2 finding
# ══════════════════════════════════════════════════════════════════
print("\n── seed/cache contract alignment ────")

_CACHE_TABLES = json.loads(
    Path(__file__).with_name("schema_cache.json").read_text(encoding="utf-8")
)["tables"]
_EXPECTED_CACHE_TABLES = {
    "Leads": _string_constants(schema.LeadFields),
    "Assets": _string_constants(schema.AssetsFields),
    "Media Files": _string_constants(schema.MediaFileFields),
}

for _table, _expected in _EXPECTED_CACHE_TABLES.items():
    _actual = set(_CACHE_TABLES.get(_table, []))
    chk(f"{_table}: cache entry exists", _table in _CACHE_TABLES)
    # schema_cache.json is now a live-fetched snapshot (Track 8B/8C), not a
    # hand-seeded mirror of *Fields constants — it legitimately carries extra
    # live fields (auto-generated link/lookup columns, etc.) code never
    # references. Extra fields don't cause false "unknown field" validation
    # rejections, so only missing fields — which would — are a real regression.
    chk(f"{_table}: no missing fields", not (_expected - _actual))


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
# 0b. Live Meta API transport boundary and contract preservation
# ══════════════════════════════════════════════════════════════════
print("\n── live metadata fetch via gateway ─────")

_LIVE_METADATA = {
    "tables": [{
        "id": "tblLIVE",
        "name": "Leads",
        "fields": [{
            "id": "fldSTATUS",
            "name": "Status",
            "type": "singleSelect",
            "options": {"choices": [{"name": "New"}, {"name": "Won"}]},
        }],
    }],
}

with patch.dict("os.environ", {"AIRTABLE_API_KEY": "key", "AIRTABLE_BASE_ID": "base"}), \
     patch("tools.airtable_gateway.get_base_metadata", return_value=_LIVE_METADATA) as mock_metadata:
    live = RuntimeSchemaProvider()._fetch_live("Leads")
    chk("live fetch: uses gateway metadata primitive", mock_metadata.call_args.kwargs == {"timeout": 15})
    chk("live fetch: table id preserved", live["table_id"] == "tblLIVE")
    chk("live fetch: field type preserved", live["fields"]["Status"]["type"] == "singleSelect")
    chk("live fetch: select choices preserved", live["fields"]["Status"]["choices"] == ["New", "Won"])

with patch.dict("os.environ", {"AIRTABLE_API_KEY": "key", "AIRTABLE_BASE_ID": "base"}), \
     patch("tools.airtable_gateway.get_base_metadata", return_value={"tables": []}):
    chk("live fetch: missing requested table returns None", RuntimeSchemaProvider()._fetch_live("Leads") is None)

with patch.dict("os.environ", {"AIRTABLE_API_KEY": "key", "AIRTABLE_BASE_ID": "base"}), \
     patch("tools.airtable_gateway.get_base_metadata", return_value=None):
    chk("live fetch: malformed payload returns None", RuntimeSchemaProvider()._fetch_live("Leads") is None)

for _live_failure in (RuntimeError("HTTP 500"), OSError("network down"), ValueError("bad payload")):
    with patch.dict("os.environ", {"AIRTABLE_API_KEY": "key", "AIRTABLE_BASE_ID": "base"}), \
         patch("tools.airtable_gateway.get_base_metadata", side_effect=_live_failure):
        chk(
            f"live fetch: {_live_failure.__class__.__name__} is fail-soft",
            RuntimeSchemaProvider()._fetch_live("Leads") is None,
        )

with patch.dict("os.environ", {}, clear=True), \
     patch("tools.airtable_gateway.get_base_metadata") as mock_missing_credentials:
    chk("live fetch: missing credentials returns None", RuntimeSchemaProvider()._fetch_live("Leads") is None)
    chk("live fetch: missing credentials skips gateway", not mock_missing_credentials.called)


# ══════════════════════════════════════════════════════════════════
# 1. TTL valid → no Meta API call at all
# ══════════════════════════════════════════════════════════════════
print("\n── TTL valid — no Meta API call ──────")

p1 = RuntimeSchemaProvider(ttl_seconds=300)
p1._last_good["Leads"] = _fresh_entry()
with patch.object(p1, "_fetch_live") as mock_fetch, \
     patch("core.runtime_schema_provider.logger") as mock_logger_1:
    contract = p1.get_table_contract("Leads")
    chk("TTL valid: _fetch_live never called", not mock_fetch.called)
    chk("TTL valid: source=cached", contract["source"] == "cached")
    chk("TTL valid: mode=full", contract["mode"] == "full")
    chk("TTL valid: table_id preserved", contract["table_id"] == "tblAAA")
    chk("TTL valid: fields preserved", "Domain" in contract["fields"])
    chk("TTL valid: result marker emitted (fresh cached)", mock_logger_1.info.called)
    _msg1 = mock_logger_1.info.call_args
    chk(
        "TTL valid: marker reports table/source/mode/table_id_present",
        _msg1.args[1:] == ("Leads", "cached", "full", True, True),
    )

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
with patch.object(p2, "_fetch_live", return_value=_NEW_ENTRY), \
     patch("core.runtime_schema_provider.logger") as mock_logger_2:
    contract = p2.get_table_contract("Leads")
    chk("TTL expired + pull success: source=live", contract["source"] == "live")
    chk("TTL expired + pull success: uses fresh fields", "Domain" not in contract["fields"])
    chk("TTL expired + pull success: result marker emitted (fresh live)", mock_logger_2.info.called)
    _msg2 = mock_logger_2.info.call_args
    chk(
        "live result marker reports table/source/mode/table_id_present",
        _msg2.args[1:] == ("Leads", "live", "full", True, True),
    )

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
    chk("stale fallback: result marker also emitted", mock_logger.info.called)
    _msg3 = mock_logger.info.call_args
    chk(
        "stale fallback marker reports source=cached/mode=full/table_id_present=True",
        _msg3.args[1:] == ("Leads", "cached", "full", True, True),
    )

# ══════════════════════════════════════════════════════════════════
# 4. Cold start + no last_good + live fails + snapshot also unavailable
#    → seed + CRITICAL + name_only
# ══════════════════════════════════════════════════════════════════
print("\n── cold start — seed fallback ────────")

p4 = RuntimeSchemaProvider(ttl_seconds=300)
with patch.object(p4, "_fetch_live", return_value=None), \
     patch.object(p4, "_load_snapshot", return_value=None), \
     patch("schema_validator.get_known_fields", return_value={"Name", "Score"}), \
     patch("core.runtime_schema_provider.logger") as mock_logger:
    contract = p4.get_table_contract("Leads")
    chk("cold start: source=seed", contract["source"] == "seed")
    chk("cold start: mode=name_only", contract["mode"] == "name_only")
    chk("cold start: table_id is None", contract["table_id"] is None)
    chk("cold start: choices always empty", all(f["choices"] == [] for f in contract["fields"].values()))
    chk("cold start: field names from seed", contract["fields"].keys() == {"Name", "Score"})
    chk("cold start: logs CRITICAL", mock_logger.critical.called)
    chk("cold start: result marker also emitted (seed)", mock_logger.info.called)
    _msg4 = mock_logger.info.call_args
    chk(
        "seed marker reports source=seed/mode=name_only/table_id_present=False",
        _msg4.args[1:] == ("Leads", "seed", "name_only", False, False),
    )

# ══════════════════════════════════════════════════════════════════
# 4b. PR3B.1 — snapshot tier (tier 3): cold start + live fails +
#     canonical snapshot succeeds → source=snapshot, mode=full
# ══════════════════════════════════════════════════════════════════
print("\n── PR3B.1 snapshot tier ──────────────")

_SNAPSHOT_RECORDS_OK = [
    {"id": "recSNAP1", "fields": {
        "Status": "OK",
        "Snapshot Date": "2026-07-08T00:00:00+00:00",
        "Snapshot File": [
            {"filename": "airtable_schema_snapshot.json", "url": "https://example.com/snap.json"},
            {"filename": "airtable_schema_report.xlsx", "url": "https://example.com/snap.xlsx"},
        ],
    }},
    {"id": "recSNAP0", "fields": {
        "Status": "OK",
        "Snapshot Date": "2026-07-01T00:00:00+00:00",
        "Snapshot File": [{"filename": "airtable_schema_snapshot.json", "url": "https://old.example.com/snap.json"}],
    }},
]

_SNAPSHOT_JSON_BODY = {
    "base_id": "appFAKE",
    "fetched_at": "2026-07-08T00:00:00+00:00",
    "tables": [
        {
            "table_id": "tblLEADS",
            "table_name": "Leads",
            "fields": [
                {"field_id": "fldDOM", "field_name": "Domain", "field_type": "singleSelect",
                 "choices": ["Real Estate", "Import"]},
            ],
        },
    ],
}


p4b = RuntimeSchemaProvider(ttl_seconds=300)
with patch.object(p4b, "_fetch_live", return_value=None), \
     patch("tools.airtable_tools.airtable_get_records", return_value=_SNAPSHOT_RECORDS_OK), \
     patch("tools.airtable_gateway.get_attachment_json", return_value=_SNAPSHOT_JSON_BODY), \
     patch("core.runtime_schema_provider.logger") as mock_logger:
    contract = p4b.get_table_contract("Leads")
    chk("PR3B.1 DoD: source=snapshot when live fails + no last_good", contract["source"] == "snapshot")
    chk("PR3B.1 DoD: mode=full (snapshot has real field data)", contract["mode"] == "full")
    chk("PR3B.1: table_id from snapshot", contract["table_id"] == "tblLEADS")
    chk("PR3B.1: fields loaded from snapshot", "Domain" in contract["fields"])
    chk("PR3B.1: choices preserved from snapshot", contract["fields"]["Domain"]["choices"] == ["Real Estate", "Import"])
    chk("PR3B.1: warning logged (not silent)", mock_logger.warning.called)
    chk("PR3B.1: snapshot result cached into last_good", "Leads" in p4b._last_good)
    chk("PR3B.1: result marker also emitted (snapshot)", mock_logger.info.called)
    _msg4b = mock_logger.info.call_args
    chk(
        "snapshot marker reports source=snapshot/mode=full/table_id_present=True",
        _msg4b.args[1:] == ("Leads", "snapshot", "full", True, True),
    )

# picks the LATEST OK record (by Snapshot Date), not just any OK record
with patch.object(p4b, "_fetch_live", return_value=None), \
     patch("tools.airtable_tools.airtable_get_records", return_value=_SNAPSHOT_RECORDS_OK), \
     patch("tools.airtable_gateway.get_attachment_json", return_value=_SNAPSHOT_JSON_BODY) as mock_attachment:
    p_latest = RuntimeSchemaProvider(ttl_seconds=300)
    p_latest.get_table_contract("Leads")
    chk(
        "PR3B.1: downloads the LATEST OK snapshot's attachment, not an older one",
        mock_attachment.call_args.args[0] == "https://example.com/snap.json",
    )
    chk(
        "PR3B.1: attachment download uses timeout=15",
        mock_attachment.call_args.kwargs == {"timeout": 15},
    )

# attachment failures remain fail-soft, regardless of gateway exception type
for _attachment_failure in (
    AirtableLookupError("attachment download: HTTP 500", status_code=500),
    OSError("network down"),
    ValueError("malformed JSON"),
):
    p_failure = RuntimeSchemaProvider(ttl_seconds=300)
    with patch.object(p_failure, "_fetch_live", return_value=None), \
         patch("tools.airtable_tools.airtable_get_records", return_value=_SNAPSHOT_RECORDS_OK), \
         patch("tools.airtable_gateway.get_attachment_json", side_effect=_attachment_failure), \
         patch("schema_validator.get_known_fields", return_value={"Name"}):
        contract = p_failure.get_table_contract("Leads")
        chk(
            f"PR3B.1: attachment {_attachment_failure.__class__.__name__} → seed fallback",
            contract["source"] == "seed",
        )

# no JSON attachment remains a clean snapshot miss and does not call the downloader
_SNAPSHOT_RECORDS_NO_JSON = [{"id": "recNOJSON", "fields": {
    "Status": "OK",
    "Snapshot Date": "2026-07-08T00:00:00+00:00",
    "Snapshot File": [{"filename": "report.xlsx", "url": "https://example.com/report.xlsx"}],
}}]
p_no_attachment = RuntimeSchemaProvider(ttl_seconds=300)
with patch.object(p_no_attachment, "_fetch_live", return_value=None), \
     patch("tools.airtable_tools.airtable_get_records", return_value=_SNAPSHOT_RECORDS_NO_JSON), \
     patch("tools.airtable_gateway.get_attachment_json") as mock_no_attachment, \
     patch("schema_validator.get_known_fields", return_value={"Name"}):
    contract = p_no_attachment.get_table_contract("Leads")
    chk("PR3B.1: missing JSON attachment → seed fallback", contract["source"] == "seed")
    chk("PR3B.1: missing JSON attachment skips download", not mock_no_attachment.called)

# no OK record at all → falls through to seed
p4c = RuntimeSchemaProvider(ttl_seconds=300)
with patch.object(p4c, "_fetch_live", return_value=None), \
     patch("tools.airtable_tools.airtable_get_records", return_value=[
         {"id": "recERR", "fields": {"Status": "Error", "Snapshot Date": "2026-07-08T00:00:00+00:00"}},
     ]), \
     patch("schema_validator.get_known_fields", return_value={"Name"}):
    contract = p4c.get_table_contract("Leads")
    chk("PR3B.1: no Status=OK record → falls through to seed", contract["source"] == "seed")

# snapshot JSON download fails → falls through to seed
p4d = RuntimeSchemaProvider(ttl_seconds=300)
with patch.object(p4d, "_fetch_live", return_value=None), \
     patch("tools.airtable_tools.airtable_get_records", return_value=_SNAPSHOT_RECORDS_OK), \
     patch("tools.airtable_gateway.get_attachment_json", side_effect=Exception("network down")), \
     patch("schema_validator.get_known_fields", return_value={"Name"}):
    contract = p4d.get_table_contract("Leads")
    chk("PR3B.1: snapshot download failure → falls through to seed", contract["source"] == "seed")

# requested table not present in the snapshot content → falls through to seed
p4e = RuntimeSchemaProvider(ttl_seconds=300)
with patch.object(p4e, "_fetch_live", return_value=None), \
     patch("tools.airtable_tools.airtable_get_records", return_value=_SNAPSHOT_RECORDS_OK), \
     patch("tools.airtable_gateway.get_attachment_json", return_value=_SNAPSHOT_JSON_BODY), \
     patch("schema_validator.get_known_fields", return_value={"Name"}):
    contract = p4e.get_table_contract("SomeOtherTable")
    chk("PR3B.1: table absent from snapshot content → falls through to seed", contract["source"] == "seed")

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


# ══════════════════════════════════════════════════════════════════
# 9. resolve_live_select_value() — BUG-CRM-BYPASS-DOMAIN-SELECT-CASING
# ══════════════════════════════════════════════════════════════════
print("\n── resolve_live_select_value(): canonical slug -> live Airtable value ──")

import core.runtime_schema_provider as _rsp_module
from core.runtime_schema_provider import resolve_live_select_value

p9 = RuntimeSchemaProvider(ttl_seconds=300)
with patch.object(p9, "_fetch_live", side_effect=lambda table: _fresh_entry()), \
     patch.object(_rsp_module, "_provider", p9):
    chk("exact live choice passes through unchanged",
        resolve_live_select_value("Leads", "Domain", "Import") == "Import")
    chk("case-insensitive canonical slug resolves to the exact live casing",
        resolve_live_select_value("Leads", "Domain", "import") == "Import")
    chk("live choice with different internal spacing still resolves case-insensitively",
        resolve_live_select_value("Leads", "Domain", "real estate") == "Real Estate")
    chk("a genuinely unknown value returns None (fail closed, never invented)",
        resolve_live_select_value("Leads", "Domain", "שטויות") is None)
    chk("a non-select field (Name) is left completely unchecked",
        resolve_live_select_value("Leads", "Name", "anything at all") == "anything at all")
    chk("empty canonical_value passes through unchanged (nothing to resolve)",
        resolve_live_select_value("Leads", "Domain", "") == "")

p9b = RuntimeSchemaProvider(ttl_seconds=300)
with patch.object(p9b, "_fetch_live", return_value=None), \
     patch.object(p9b, "_load_snapshot", return_value=None), \
     patch.object(_rsp_module, "_provider", p9b):
    # cold start, no live/cached/snapshot -> falls to the seed contract,
    # mode="name_only", choices=[] always -- must never risk a false
    # rewrite (or false rejection) from a contract with no real choices.
    chk("name_only seed contract (nothing to check against) -> unchanged, never None",
        resolve_live_select_value("Leads", "Domain", "import") == "import")

print(f"\n{'='*50}\n{passed} passed, {failed} failed\n{'='*50}")
sys.exit(1 if failed else 0)
