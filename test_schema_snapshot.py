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
