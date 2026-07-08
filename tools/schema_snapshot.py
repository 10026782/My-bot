# tools/schema_snapshot.py — PR3A: Airtable schema snapshot archive.
#
# Fetches the live Airtable schema via Meta API (keeping table/field IDs,
# unlike schema_validator.refresh_cache which discards them), normalizes it
# to canonical JSON, builds a human-readable XLSX report via
# document_converter, and archives both as native attachments on
# Tables.SCHEMA_SNAPSHOTS.
#
# XLSX is for humans. JSON is for machines. Gateway validation
# (schema_validator.py / RuntimeSchemaProvider) never depends on this
# module or on document_converter.

from __future__ import annotations

import csv
import hashlib
import json
import logging
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import httpx

from airtable_schema import SchemaSnapshotFields, SchemaSnapshotStatus, Tables

logger = logging.getLogger(__name__)

_META_URL_TMPL = "https://api.airtable.com/v0/meta/bases/{base_id}/tables"

# Retention: keep the last N snapshot records (simplest to implement first —
# see spec "10 snapshots OR 30 days, implementer's choice"). The latest
# Status=OK record is never deleted regardless of this count.
_RETENTION_KEEP = 10


def _env_ready() -> tuple[str, str] | None:
    key = os.environ.get("AIRTABLE_API_KEY", "")
    base = os.environ.get("AIRTABLE_BASE_ID", "")
    if not key or not base:
        logger.error(
            "[schema_snapshot] AIRTABLE_API_KEY/AIRTABLE_BASE_ID missing — snapshot skipped"
        )
        return None
    return key, base


def fetch_live_schema() -> dict | None:
    """Fetch the live schema via Meta API. Returns the raw Meta API JSON, or
    None (logged) on any failure — callers must fail closed."""
    env = _env_ready()
    if not env:
        return None
    key, base = env
    try:
        r = httpx.get(
            _META_URL_TMPL.format(base_id=base),
            headers={"Authorization": f"Bearer {key}"},
            timeout=20,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        logger.error("[schema_snapshot] Meta API fetch failed: %s", e)
        return None


def normalize_schema(raw_meta: dict, base_id: str) -> dict:
    """Build the canonical, deterministic snapshot JSON shape."""
    tables = []
    for t in sorted(raw_meta.get("tables", []), key=lambda t: t.get("name", "")):
        fields = []
        for f in sorted(t.get("fields", []), key=lambda f: f.get("name", "")):
            options = f.get("options") or {}
            choices = [c.get("name") for c in options.get("choices", [])]
            fields.append({
                "field_id": f.get("id"),
                "field_name": f.get("name"),
                "field_type": f.get("type"),
                "choices": choices,
            })
        tables.append({
            "table_id": t.get("id"),
            "table_name": t.get("name"),
            "fields": fields,
        })
    return {
        "base_id": base_id,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "tables": tables,
    }


def schema_hash(snapshot: dict) -> str:
    """Deterministic hash of the snapshot (excludes fetched_at) for drift detection."""
    stable = {"base_id": snapshot["base_id"], "tables": snapshot["tables"]}
    blob = json.dumps(stable, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def write_json_snapshot(snapshot: dict, path: Path) -> None:
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv_report(snapshot: dict, path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["table_id", "table_name", "field_id", "field_name", "field_type", "choices"])
        for t in snapshot["tables"]:
            for f in t["fields"]:
                writer.writerow([
                    t["table_id"], t["table_name"],
                    f["field_id"], f["field_name"], f["field_type"],
                    "|".join(str(c) for c in f["choices"]),
                ])


def build_xlsx_report(csv_path: Path) -> Path | None:
    """document_converter's first schema-report caller — CSV -> XLSX."""
    from document_converter.engine import convert_document

    result = convert_document(str(csv_path), "csv", "xlsx")
    if result["status"] != "success":
        logger.error("[schema_snapshot] XLSX conversion failed: %s", result["status"])
        return None
    return Path(result["output_file"])


def _snapshot_table_exists(raw_meta: dict) -> bool:
    return any(t.get("name") == Tables.SCHEMA_SNAPSHOTS for t in raw_meta.get("tables", []))


def run_snapshot_archive() -> dict:
    """
    Full snapshot flow: fetch -> normalize -> CSV -> XLSX -> create record ->
    upload JSON + XLSX -> patch status -> (optional) retention.
    Never raises — always returns a result dict for logging/tests.
    """
    from feature_flags import is_enabled

    if not is_enabled("FEATURE_AIRTABLE_SCHEMA_SNAPSHOT"):
        return {"ok": False, "reason": "flag_off"}

    raw_meta = fetch_live_schema()
    if raw_meta is None:
        return {"ok": False, "reason": "meta_api_unreachable"}

    if not _snapshot_table_exists(raw_meta):
        logger.error(
            "[schema_snapshot] '%s' table not found — snapshot job disabled until it is "
            "created manually in Airtable (see PR3A pre-activation checklist)",
            Tables.SCHEMA_SNAPSHOTS,
        )
        return {"ok": False, "reason": "snapshot_table_missing"}

    base_id = os.environ.get("AIRTABLE_BASE_ID", "")
    snapshot = normalize_schema(raw_meta, base_id)
    h = schema_hash(snapshot)

    tmpdir = Path(tempfile.mkdtemp(prefix="schema_snapshot_"))
    try:
        json_path = tmpdir / "airtable_schema_snapshot.json"
        csv_path = tmpdir / "airtable_schema_report.csv"
        write_json_snapshot(snapshot, json_path)
        write_csv_report(snapshot, csv_path)
        xlsx_path = build_xlsx_report(csv_path)

        from tools.airtable_gateway import (
            airtable_create,
            airtable_patch,
            airtable_upload_attachment,
            resolve_table_and_field_ids,
        )

        record = airtable_create(
            Tables.SCHEMA_SNAPSHOTS,
            {
                SchemaSnapshotFields.SNAPSHOT_DATE: datetime.now(timezone.utc).isoformat(),
                SchemaSnapshotFields.TABLES_COUNT: len(snapshot["tables"]),
                SchemaSnapshotFields.STATUS: (
                    SchemaSnapshotStatus.OK if xlsx_path else SchemaSnapshotStatus.ERROR
                ),
                SchemaSnapshotFields.SCHEMA_HASH: h,
                SchemaSnapshotFields.BASE_ID: base_id,
            },
            source="schema_snapshot",
        )
        if not record:
            return {"ok": False, "reason": "record_create_failed"}
        record_id = record.get("id", "")

        try:
            _, field_id = resolve_table_and_field_ids(
                Tables.SCHEMA_SNAPSHOTS, SchemaSnapshotFields.SNAPSHOT_FILE
            )
        except Exception as e:
            logger.error("[schema_snapshot] could not resolve attachment field id: %s", e)
            airtable_patch(
                Tables.SCHEMA_SNAPSHOTS, record_id,
                {
                    SchemaSnapshotFields.STATUS: SchemaSnapshotStatus.ERROR,
                    SchemaSnapshotFields.NOTES: f"field id resolution failed: {e}",
                },
                source="schema_snapshot",
            )
            return {"ok": False, "reason": "field_id_resolution_failed", "record_id": record_id}

        upload_errors: list[str] = []

        json_res = airtable_upload_attachment(
            record_id, field_id, json_path.name, json_path.read_bytes(),
            "application/json", source="schema_snapshot",
        )
        if not json_res["ok"]:
            upload_errors.append(f"json: {json_res['error']}")

        if xlsx_path:
            xlsx_res = airtable_upload_attachment(
                record_id, field_id, xlsx_path.name, xlsx_path.read_bytes(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                source="schema_snapshot",
            )
            if not xlsx_res["ok"]:
                upload_errors.append(f"xlsx: {xlsx_res['error']}")
        else:
            upload_errors.append("xlsx: conversion failed")

        final_status = SchemaSnapshotStatus.OK if not upload_errors else SchemaSnapshotStatus.ERROR
        airtable_patch(
            Tables.SCHEMA_SNAPSHOTS, record_id,
            {
                SchemaSnapshotFields.STATUS: final_status,
                SchemaSnapshotFields.NOTES: (
                    "; ".join(upload_errors) if upload_errors else "snapshot archived successfully"
                ),
            },
            source="schema_snapshot",
        )

        if is_enabled("FEATURE_AIRTABLE_SCHEMA_SNAPSHOT_CLEANUP"):
            apply_retention_policy()

        return {
            "ok": not upload_errors,
            "record_id": record_id,
            "tables_count": len(snapshot["tables"]),
            "errors": upload_errors,
        }
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def apply_retention_policy() -> dict:
    """
    Delete snapshot records beyond the retention window (default: keep last
    _RETENTION_KEEP). The latest Status=OK record is never deleted, no matter
    its age or position — only Error/other records beyond the window are
    eligible alongside older OK ones.
    """
    from tools.airtable_gateway import airtable_delete
    from tools.airtable_tools import airtable_get_records

    try:
        records = airtable_get_records(Tables.SCHEMA_SNAPSHOTS, "")
    except Exception as e:
        logger.error("[schema_snapshot] retention: could not list records: %s", e)
        return {"ok": False, "reason": "list_failed"}

    def _sort_key(rec: dict) -> str:
        return str(rec.get("fields", {}).get(SchemaSnapshotFields.SNAPSHOT_DATE, ""))

    records_sorted = sorted(records, key=_sort_key, reverse=True)

    latest_ok_id = next(
        (
            rec["id"] for rec in records_sorted
            if rec.get("fields", {}).get(SchemaSnapshotFields.STATUS) == SchemaSnapshotStatus.OK
        ),
        None,
    )

    to_delete = [rec for rec in records_sorted[_RETENTION_KEEP:] if rec["id"] != latest_ok_id]
    if not to_delete:
        return {"ok": True, "deleted": 0}

    deleted = 0
    for rec in to_delete:
        if airtable_delete(Tables.SCHEMA_SNAPSHOTS, rec["id"], source="schema_snapshot_retention"):
            deleted += 1

    return {"ok": True, "deleted": deleted}
