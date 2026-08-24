#!/usr/bin/env python3
"""
test_schema_snapshot.py — Regression tests for tools/schema_snapshot.py (PR3A).

מאמת:
1. normalize_schema בונה JSON קנוני דטרמיניסטי (כולל table_id/field_id/choices).
2. write_csv_report בונה CSV עם העמודות הנכונות.
3. build_xlsx_report קורא ל-convert_document נכון.
4. airtable_upload_attachment בונה endpoint נכון (לא PATCH רגיל).
5. env vars חסרים → fail closed.
6. טבלת snapshot חסרה → fail closed עם לוג ברור.
7. upload שנכשל מסומן/מלוגג בלי לקרוס.
8. retention policy מוחקת רק רשומות מעבר למגבלה.
9. retention policy אף פעם לא מוחקת את ה-snapshot המוצלח האחרון.
10. BUG-085 — run_snapshot_archive מזהה ומדווח DRIFT_DETECTED כשטבלה
    שהקוד מכיר חסרה מהתגובה החיה, ולא רק OK/Error.
11. BUG-085 — כש"הכל תקין" (כל הטבלאות שהקוד מכיר קיימות חי), עדיין נכתב OK.
"""

from __future__ import annotations

import logging
import sys
from unittest.mock import MagicMock, patch

logging.basicConfig(level=logging.WARNING)

from airtable_schema import SchemaSnapshotFields, SchemaSnapshotStatus, Tables
from tools.schema_snapshot import (
    normalize_schema,
    schema_hash,
    write_csv_report,
    build_xlsx_report,
    fetch_live_schema,
    run_snapshot_archive,
    apply_retention_policy,
    _snapshot_table_exists,
    _missing_tables,
)
from tools.airtable_gateway import airtable_upload_attachment

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


_RAW_META = {
    "tables": [
        {
            "id": "tblAAA",
            "name": "Leads",
            "fields": [
                {"id": "fldZZZ", "name": "Name", "type": "singleLineText"},
                {
                    "id": "fldYYY", "name": "Domain", "type": "singleSelect",
                    "options": {"choices": [{"name": "Real Estate"}, {"name": "Import"}]},
                },
            ],
        },
        {
            "id": "tblBBB",
            "name": Tables.SCHEMA_SNAPSHOTS,
            "fields": [
                {"id": "fldSNAP", "name": SchemaSnapshotFields.SNAPSHOT_FILE, "type": "multipleAttachments"},
            ],
        },
    ]
}

# ══════════════════════════════════════════════════════════════════
# 1. normalize_schema
# ══════════════════════════════════════════════════════════════════
print("\n── normalize_schema ──────────────────")

snap = normalize_schema(_RAW_META, "appFAKE")
chk("normalize_schema keeps base_id", snap["base_id"] == "appFAKE")
chk("normalize_schema has 2 tables", len(snap["tables"]) == 2)
leads_table = next(t for t in snap["tables"] if t["table_name"] == "Leads")
chk("normalize_schema keeps table_id", leads_table["table_id"] == "tblAAA")
domain_field = next(f for f in leads_table["fields"] if f["field_name"] == "Domain")
chk("normalize_schema keeps field_id", domain_field["field_id"] == "fldYYY")
chk("normalize_schema keeps choices", domain_field["choices"] == ["Real Estate", "Import"])
name_field = next(f for f in leads_table["fields"] if f["field_name"] == "Name")
chk("normalize_schema empty choices for non-select field", name_field["choices"] == [])

snap2 = normalize_schema(_RAW_META, "appFAKE")
chk(
    "schema_hash deterministic across calls (fetched_at excluded)",
    schema_hash(snap) == schema_hash(snap2),
)

chk("_snapshot_table_exists True when present", _snapshot_table_exists(_RAW_META))
chk(
    "_snapshot_table_exists False when absent",
    not _snapshot_table_exists({"tables": [_RAW_META["tables"][0]]}),
)

# ══════════════════════════════════════════════════════════════════
# 2. write_csv_report
# ══════════════════════════════════════════════════════════════════
print("\n── write_csv_report ──────────────────")

import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory() as td:
    csv_path = Path(td) / "report.csv"
    write_csv_report(snap, csv_path)
    content = csv_path.read_text(encoding="utf-8")
    chk("CSV header has expected columns", content.startswith(
        "table_id,table_name,field_id,field_name,field_type,choices"
    ))
    chk("CSV contains Domain row with pipe-joined choices", "Real Estate|Import" in content)

    # ══════════════════════════════════════════════════════════════════
    # 3. build_xlsx_report calls convert_document correctly
    # ══════════════════════════════════════════════════════════════════
    print("\n── build_xlsx_report ─────────────────")

    fake_result = {"status": "success", "confidence": "high", "warnings": [], "output_file": str(Path(td) / "report.xlsx")}
    Path(fake_result["output_file"]).write_bytes(b"fake-xlsx-bytes")
    with patch("document_converter.engine.convert_document", return_value=fake_result) as mock_convert:
        out = build_xlsx_report(csv_path)
        chk("build_xlsx_report calls convert_document(csv_path, 'csv', 'xlsx')",
            mock_convert.call_args.args[1:] == ("csv", "xlsx"))
        chk("build_xlsx_report returns output path on success", out == Path(fake_result["output_file"]))

    with patch("document_converter.engine.convert_document",
               return_value={"status": "error: bad", "confidence": "low", "warnings": [], "output_file": None}):
        out2 = build_xlsx_report(csv_path)
        chk("build_xlsx_report returns None on conversion failure", out2 is None)

# ══════════════════════════════════════════════════════════════════
# 4. airtable_upload_attachment — endpoint shape
# ══════════════════════════════════════════════════════════════════
print("\n── airtable_upload_attachment ────────")

captured_calls: list[dict] = []


def fake_post(url, *, headers, json, timeout):
    captured_calls.append({"url": url, "headers": headers, "json": json})
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"id": "recSNAP1"}
    return resp


with patch("tools.airtable_gateway.httpx.post", side_effect=fake_post), \
     patch("tools.airtable_gateway._at_base", return_value="appFAKE"):
    captured_calls.clear()
    result = airtable_upload_attachment(
        "recSNAP1", "fldSNAP", "snapshot.json", b'{"a":1}', "application/json", source="test"
    )
    chk("airtable_upload_attachment returns ok=True on 200", result["ok"] is True)
    chk(
        "airtable_upload_attachment uses content.airtable.com uploadAttachment endpoint",
        captured_calls
        and captured_calls[0]["url"]
        == "https://content.airtable.com/v0/appFAKE/recSNAP1/fldSNAP/uploadAttachment",
    )
    chk(
        "airtable_upload_attachment does not use raw PATCH-style fields body",
        "fields" not in captured_calls[0]["json"] and "file" in captured_calls[0]["json"],
    )

with patch("tools.airtable_gateway.httpx.post", side_effect=Exception("boom")), \
     patch("tools.airtable_gateway._at_base", return_value="appFAKE"):
    result = airtable_upload_attachment("recX", "fldX", "f.json", b"{}", "application/json", source="test")
    chk("airtable_upload_attachment fails closed (ok=False) on exception, no crash", result["ok"] is False)

# ══════════════════════════════════════════════════════════════════
# 5. Missing env vars fail closed
# ══════════════════════════════════════════════════════════════════
print("\n── missing env vars ──────────────────")

with patch.dict("os.environ", {"AIRTABLE_API_KEY": "", "AIRTABLE_BASE_ID": ""}, clear=False):
    chk("fetch_live_schema returns None when env vars missing", fetch_live_schema() is None)

print("\n── live metadata via gateway ─────────")

with patch.dict("os.environ", {"AIRTABLE_API_KEY": "key", "AIRTABLE_BASE_ID": "appFAKE"}, clear=False), \
     patch("tools.airtable_gateway.get_base_metadata", return_value=_RAW_META) as mock_metadata:
    live = fetch_live_schema()
    chk("fetch_live_schema returns the full gateway payload", live == _RAW_META)
    chk("fetch_live_schema uses the gateway timeout 20", mock_metadata.call_args.kwargs == {"timeout": 20})

for error in (RuntimeError("HTTP 500"), OSError("network down"), ValueError("malformed JSON")):
    with patch.dict("os.environ", {"AIRTABLE_API_KEY": "key", "AIRTABLE_BASE_ID": "appFAKE"}, clear=False), \
         patch("tools.airtable_gateway.get_base_metadata", side_effect=error):
        chk(f"fetch_live_schema maps {type(error).__name__} to None", fetch_live_schema() is None)

with patch.dict("os.environ", {"AIRTABLE_API_KEY": "key", "AIRTABLE_BASE_ID": "appFAKE"}, clear=False), \
     patch("tools.airtable_gateway.get_base_metadata", return_value={}):
    chk("fetch_live_schema preserves an empty metadata payload", fetch_live_schema() == {})

# ══════════════════════════════════════════════════════════════════
# 6. Missing snapshot table fails closed
# ══════════════════════════════════════════════════════════════════
print("\n── missing snapshot table ────────────")

_META_WITHOUT_SNAPSHOT_TABLE = {"tables": [_RAW_META["tables"][0]]}

with patch("tools.schema_snapshot.is_enabled" if False else "feature_flags.is_enabled", return_value=True), \
     patch("tools.schema_snapshot.fetch_live_schema", return_value=_META_WITHOUT_SNAPSHOT_TABLE), \
     patch.dict("os.environ", {"AIRTABLE_API_KEY": "key", "AIRTABLE_BASE_ID": "appFAKE"}, clear=False):
    result = run_snapshot_archive()
    chk("run_snapshot_archive fails closed when snapshot table missing", result["ok"] is False)
    chk("run_snapshot_archive reports snapshot_table_missing reason",
        result.get("reason") == "snapshot_table_missing")

# ══════════════════════════════════════════════════════════════════
# 7. flag off — job is a no-op
# ══════════════════════════════════════════════════════════════════
print("\n── flag off ──────────────────────────")

with patch("feature_flags.is_enabled", return_value=False):
    result = run_snapshot_archive()
    chk("run_snapshot_archive no-ops when flag is off", result == {"ok": False, "reason": "flag_off"})

# ══════════════════════════════════════════════════════════════════
# 10/11. BUG-085 — DRIFT_DETECTED actually gets set
# ══════════════════════════════════════════════════════════════════
print("\n── BUG-085: drift detection ──────────")

import types

# Small fake Tables namespace (same pattern as test_check_airtable_schema_runtime.py)
# so "no drift" is achievable without having to mirror the entire real
# airtable_schema.Tables class in a test fixture.
_fake_tables_ns = types.SimpleNamespace(
    LEADS="Leads",
    SCHEMA_SNAPSHOTS=Tables.SCHEMA_SNAPSHOTS,
)

with patch("tools.schema_snapshot.Tables", _fake_tables_ns):
    chk("_missing_tables: none missing when live has every fake-code table",
        _missing_tables(_RAW_META) == [])

    _RAW_META_MISSING_LEADS = {"tables": [_RAW_META["tables"][1]]}  # only SCHEMA_SNAPSHOTS, no Leads
    chk("_missing_tables: reports a code table absent from live",
        _missing_tables(_RAW_META_MISSING_LEADS) == ["Leads"])


def _fake_run_snapshot_archive(raw_meta: dict, tmp_path):
    """Drives run_snapshot_archive() end-to-end with every network call mocked,
    so the DRIFT_DETECTED/OK status actually written can be inspected."""
    xlsx_file = tmp_path / "fake.xlsx"
    xlsx_file.write_bytes(b"fake-xlsx-bytes")
    fake_xlsx_result = {"status": "success", "confidence": "high", "warnings": [], "output_file": str(xlsx_file)}

    created_fields: dict = {}
    patched_fields: list[dict] = []

    def _fake_create(table, fields, source=""):
        created_fields.update(fields)
        return {"id": "recSNAPNEW"}

    def _fake_patch(table, record_id, fields, source=""):
        patched_fields.append(fields)
        return True

    with patch("tools.schema_snapshot.Tables", _fake_tables_ns), \
         patch("feature_flags.is_enabled", side_effect=lambda flag: flag == "FEATURE_AIRTABLE_SCHEMA_SNAPSHOT"), \
         patch("tools.schema_snapshot.fetch_live_schema", return_value=raw_meta), \
         patch("document_converter.engine.convert_document", return_value=fake_xlsx_result), \
         patch("tools.airtable_gateway.airtable_create", side_effect=_fake_create), \
         patch("tools.airtable_gateway.airtable_patch", side_effect=_fake_patch), \
         patch("tools.airtable_gateway.resolve_table_and_field_ids", return_value=("tblSNAP", "fldSNAPFILE")), \
         patch("tools.airtable_gateway.airtable_upload_attachment", return_value={"ok": True}), \
         patch.dict("os.environ", {"AIRTABLE_API_KEY": "key", "AIRTABLE_BASE_ID": "appFAKE"}, clear=False):
        result = run_snapshot_archive()
    return result, created_fields, patched_fields


with tempfile.TemporaryDirectory() as td:
    tdp = Path(td)

    # 10a. All fake-code tables present live → still OK (regression: the
    # common "everything is fine" case must not start reporting drift).
    result_ok, created_ok, patched_ok = _fake_run_snapshot_archive(_RAW_META, tdp)
    chk("BUG-085 regression: no drift → run_snapshot_archive still reports ok",
        result_ok["ok"] is True)
    chk("BUG-085 regression: no drift → missing_tables empty in result",
        result_ok.get("missing_tables") == [])
    chk("BUG-085 regression: no drift → final patched Status is OK",
        patched_ok[-1][SchemaSnapshotFields.STATUS] == SchemaSnapshotStatus.OK)

    # 10b. Leads missing from the live response → DRIFT_DETECTED, not OK.
    result_drift, created_drift, patched_drift = _fake_run_snapshot_archive(_RAW_META_MISSING_LEADS, tdp)
    chk("BUG-085: drift detected → missing_tables reports 'Leads'",
        result_drift.get("missing_tables") == ["Leads"])
    chk("BUG-085: drift detected → initial created Status is Drift Detected",
        created_drift[SchemaSnapshotFields.STATUS] == SchemaSnapshotStatus.DRIFT_DETECTED)
    chk("BUG-085: drift detected → final patched Status is Drift Detected (not OK)",
        patched_drift[-1][SchemaSnapshotFields.STATUS] == SchemaSnapshotStatus.DRIFT_DETECTED)
    chk("BUG-085: drift detected → Notes mentions the missing table",
        "Leads" in patched_drift[-1][SchemaSnapshotFields.NOTES])

# ══════════════════════════════════════════════════════════════════
# 8/9. Retention policy
# ══════════════════════════════════════════════════════════════════
print("\n── retention policy ──────────────────")

_FAKE_RECORDS = [
    {"id": f"rec{i}", "fields": {
        SchemaSnapshotFields.SNAPSHOT_DATE: f"2026-07-{i:02d}",
        SchemaSnapshotFields.STATUS: SchemaSnapshotStatus.OK if i in (1, 15) else SchemaSnapshotStatus.ERROR,
    }}
    for i in range(1, 16)  # 15 records, dates 01..15 (15 = most recent, OK)
]

deleted_ids: list[str] = []


def fake_delete(table, record_id, source="unknown"):
    deleted_ids.append(record_id)
    return True


with patch("tools.airtable_gateway.airtable_delete", side_effect=fake_delete), \
     patch("tools.airtable_tools.airtable_get_records", return_value=_FAKE_RECORDS):
    deleted_ids.clear()
    result = apply_retention_policy()
    chk("retention deletes only records beyond the keep-10 window", len(deleted_ids) == 5)
    chk("retention never deletes the latest OK snapshot (rec15)", "rec15" not in deleted_ids)

# rec1 is OK but old — it's within the deleted range (beyond top 10) and is NOT the latest OK,
# so it should be deleted; only rec15 (latest OK) is protected.
chk("retention deletes an old OK record that isn't the latest", "rec1" in deleted_ids)

print(f"\n{'='*50}\n{passed} passed, {failed} failed\n{'='*50}")
sys.exit(1 if failed else 0)
