# core/runtime_schema_provider.py — PR3B: RuntimeSchemaProvider
#
# One schema provider that all Airtable write validation reads from.
# Resolves the best available schema in priority order:
#   1. Fresh runtime schema (live Meta API fetch via refresh())
#   2. Last good schema already held in memory
#   3. Latest successful canonical JSON snapshot from Tables.SCHEMA_SNAPSHOTS (PR3A)
#   4. schema_cache.json seed/fallback
# If none are available: fail closed for unsafe writes (empty schema —
# callers must treat "table/field unknown" conservatively).
#
# Reuses tools.schema_snapshot's fetch_live_schema()/normalize_schema() for
# the live-fetch path so there is exactly one Meta-API-normalization
# implementation, not two. Reads only the canonical JSON attachment from a
# snapshot record — never parses XLSX, never depends on document_converter.

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Internal schema shape: {table_name: {field_name: {"type": str|None, "choices": list[str]}}}
SchemaDict = dict


class RuntimeSchemaProvider:
    """Injectable for tests — construct your own instance rather than relying
    on the module-level singleton when a test needs isolation."""

    def __init__(self) -> None:
        self._last_good: SchemaDict | None = None
        self._last_good_source: str | None = None

    # ── Public provider API (required by spec) ──────────────────────

    def get_schema(self) -> SchemaDict:
        """Best available schema; never raises. Lazily resolves the full
        fallback chain on cold start, otherwise serves the last good
        in-memory schema without hitting the network on every call."""
        if self._last_good is not None:
            return self._last_good

        if self.refresh():
            return self._last_good  # type: ignore[return-value]

        snapshot = self._load_latest_snapshot()
        if snapshot is not None:
            self._last_good = snapshot
            self._last_good_source = "snapshot"
            return snapshot

        seed = self.load_seed_schema()
        self._last_good = seed
        self._last_good_source = "seed" if seed else "none"
        return seed

    def refresh(self) -> bool:
        """Fetch fresh schema from the Meta API. On success, updates the
        in-memory last-good schema and returns True. On failure, leaves
        last_good untouched (refresh failure must never erase last good)
        and returns False."""
        fresh = self._fetch_fresh()
        if fresh is None:
            return False
        self._last_good = fresh
        self._last_good_source = "live_meta_api"
        return True

    def get_last_good(self) -> SchemaDict | None:
        return self._last_good

    def load_seed_schema(self) -> SchemaDict:
        """schema_cache.json seed — field names only, no types/choices."""
        path = Path(__file__).resolve().parent.parent / "schema_cache.json"
        if not path.exists():
            return {}
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning("[RuntimeSchemaProvider] failed to read schema_cache.json seed: %s", e)
            return {}
        return {
            table: {field: {"type": None, "choices": []} for field in fields}
            for table, fields in raw.get("tables", {}).items()
        }

    @property
    def last_good_source(self) -> str | None:
        return self._last_good_source

    # ── Convenience read helpers used by Gateway integration ─────────

    def get_known_fields(self, table: str) -> set[str]:
        return set(self.get_schema().get(table, {}).keys())

    def get_field_info(self, table: str, field: str) -> dict | None:
        return self.get_schema().get(table, {}).get(field)

    # ── Internal fetch paths ─────────────────────────────────────────

    def _fetch_fresh(self) -> SchemaDict | None:
        try:
            from tools.schema_snapshot import fetch_live_schema, normalize_schema
            import os
        except Exception as e:
            logger.warning("[RuntimeSchemaProvider] import failure during fresh fetch: %s", e)
            return None

        raw_meta = fetch_live_schema()
        if raw_meta is None:
            return None
        base_id = os.environ.get("AIRTABLE_BASE_ID", "")
        snapshot = normalize_schema(raw_meta, base_id)
        return self._snapshot_to_provider_shape(snapshot)

    def _load_latest_snapshot(self) -> SchemaDict | None:
        try:
            from tools.airtable_tools import airtable_get_records
            from airtable_schema import SchemaSnapshotFields, SchemaSnapshotStatus, Tables
            import httpx
        except Exception as e:
            logger.warning("[RuntimeSchemaProvider] import failure during snapshot fallback: %s", e)
            return None

        try:
            records = airtable_get_records(
                Tables.SCHEMA_SNAPSHOTS,
                f"{{{SchemaSnapshotFields.STATUS}}}='{SchemaSnapshotStatus.OK}'",
            )
        except Exception as e:
            logger.warning("[RuntimeSchemaProvider] could not list snapshot records: %s", e)
            return None
        if not records:
            return None

        latest = max(
            records,
            key=lambda r: str(r.get("fields", {}).get(SchemaSnapshotFields.SNAPSHOT_DATE, "")),
        )
        attachments = latest.get("fields", {}).get(SchemaSnapshotFields.SNAPSHOT_FILE, []) or []
        json_attachment = next(
            (a for a in attachments if a.get("filename", "").endswith(".json")), None
        )
        if not json_attachment:
            logger.warning("[RuntimeSchemaProvider] latest snapshot record has no JSON attachment")
            return None

        try:
            r = httpx.get(json_attachment["url"], timeout=15)
            r.raise_for_status()
            raw_snapshot = r.json()
        except Exception as e:
            logger.warning("[RuntimeSchemaProvider] failed to download snapshot JSON: %s", e)
            return None

        return self._snapshot_to_provider_shape(raw_snapshot)

    @staticmethod
    def _snapshot_to_provider_shape(snapshot: dict) -> SchemaDict:
        """Convert tools.schema_snapshot's canonical {tables: [...]} shape
        into {table_name: {field_name: {type, choices}}}."""
        out: SchemaDict = {}
        for t in snapshot.get("tables", []):
            fields = {}
            for f in t.get("fields", []):
                fields[f["field_name"]] = {
                    "type": f.get("field_type"),
                    "choices": list(f.get("choices", [])),
                }
            out[t["table_name"]] = fields
        return out


# ══════════════════════════════════════════════════════════════════
# Module-level singleton for production use — construct a fresh
# RuntimeSchemaProvider() directly in tests for isolation instead.
# ══════════════════════════════════════════════════════════════════

_provider: RuntimeSchemaProvider | None = None


def get_provider() -> RuntimeSchemaProvider:
    global _provider
    if _provider is None:
        _provider = RuntimeSchemaProvider()
    return _provider
