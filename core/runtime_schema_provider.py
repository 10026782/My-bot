# core/runtime_schema_provider.py — PR3B (rev.2) + PR3B.1 (snapshot tier)
#
# One schema provider that Airtable write validation reads from, per table:
#   1. Fresh live Meta API fetch (when the TTL for that table has expired).
#   2. Last-good in-memory result for that table, served while its TTL is
#      still valid — no Meta API call at all in this case.
#   3. If the TTL expired and the live re-fetch fails: the same last-good
#      result, served stale, with a WARNING log (age included).
#   4. (PR3B.1) If there is no last-good result at all (cold start, e.g.
#      right after a restart) and the live fetch fails: read the latest
#      successful (Status=OK) canonical JSON snapshot from PR3A's
#      Tables.SCHEMA_SNAPSHOTS archive (read-only — tools/schema_snapshot.py
#      itself is not modified by this tier). Closes the gap where a cold
#      start + Meta API outage used to fall straight to the seed, which is
#      exactly the BUG-020 failure mode this tier exists to prevent.
#   5. If no snapshot is usable either (table missing from the archive, no
#      OK record, download/parse failure): schema_cache.json seed via the
#      existing, unchanged schema_validator.get_known_fields() —
#      mode="name_only", table_id=None, choices=[] always (schema_cache.json
#      has never stored choices).
#
# This module owns no on-disk state — schema_cache.json is never written
# here. document_converter is never touched (tier 4 reads the already-
# uploaded JSON attachment directly, never the XLSX report).

from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_DEFAULT_TTL_SECONDS = 300


class RuntimeSchemaProvider:
    """Singleton (see get_provider()), thread-safe. Construct your own
    instance directly in tests for isolation."""

    def __init__(self, ttl_seconds: int | None = None) -> None:
        self._lock = threading.Lock()
        # table -> {"table_id", "mode", "fields", "fetched_at" (iso str),
        #           "fetched_at_mono" (time.monotonic() float)}
        self._last_good: dict[str, dict] = {}
        self._ttl = (
            ttl_seconds
            if ttl_seconds is not None
            else int(os.environ.get("SCHEMA_PROVIDER_TTL_SECONDS", _DEFAULT_TTL_SECONDS))
        )

    def get_table_contract(self, table: str) -> dict:
        """
        Returns:
        {
            "table_id": str | None,
            "mode": "full" | "name_only",
            "source": "live" | "cached" | "snapshot" | "seed",
            "fetched_at": iso str | None,
            "fields": {field_name: {"field_id", "type", "choices"}},
        }
        Never raises.
        """
        with self._lock:
            entry = self._last_good.get(table)

            if entry is not None and (time.monotonic() - entry["fetched_at_mono"]) < self._ttl:
                return self._contract_from_entry(entry, source="cached")

            fresh = self._fetch_live(table)
            if fresh is not None:
                self._last_good[table] = fresh
                return self._contract_from_entry(fresh, source="live")

            if entry is not None:
                age = time.monotonic() - entry["fetched_at_mono"]
                logger.warning(
                    "[RuntimeSchemaProvider] stale schema used for %s, age=%.0fs", table, age
                )
                return self._contract_from_entry(entry, source="cached")

            snapshot_entry = self._load_snapshot(table)
            if snapshot_entry is not None:
                self._last_good[table] = snapshot_entry
                logger.warning(
                    "[RuntimeSchemaProvider] no live/cached schema for %s — "
                    "using canonical snapshot fallback (tier 3, PR3B.1)",
                    table,
                )
                return self._contract_from_entry(snapshot_entry, source="snapshot")

            logger.critical(
                "[RuntimeSchemaProvider] no live/cached/snapshot schema for %s — "
                "falling back to seed, name_only mode",
                table,
            )
            return self._seed_contract(table)

    # ── Internal ──────────────────────────────────────────────────────

    @staticmethod
    def _contract_from_entry(entry: dict, source: str) -> dict:
        return {
            "table_id": entry["table_id"],
            "mode": "full",
            "source": source,
            "fetched_at": entry["fetched_at"],
            "fields": entry["fields"],
        }

    def _fetch_live(self, table: str) -> dict | None:
        key = os.environ.get("AIRTABLE_API_KEY", "")
        base = os.environ.get("AIRTABLE_BASE_ID", "")
        if not key or not base:
            logger.warning(
                "[RuntimeSchemaProvider] AIRTABLE_API_KEY/AIRTABLE_BASE_ID missing — "
                "cannot fetch live schema for %s",
                table,
            )
            return None
        try:
            import httpx

            r = httpx.get(
                f"https://api.airtable.com/v0/meta/bases/{base}/tables",
                headers={"Authorization": f"Bearer {key}"},
                timeout=15,
            )
            r.raise_for_status()
        except Exception as e:
            logger.warning(
                "[RuntimeSchemaProvider] Meta API fetch failed for table=%s: %s", table, e
            )
            return None

        for t in r.json().get("tables", []):
            if t.get("name") == table:
                return self._build_entry(t)

        logger.warning("[RuntimeSchemaProvider] table '%s' not found via Meta API", table)
        return None

    @staticmethod
    def _build_entry(t: dict) -> dict:
        fields: dict = {}
        for f in t.get("fields", []):
            options = f.get("options") or {}
            choices = [c.get("name") for c in options.get("choices", [])]
            fields[f["name"]] = {
                "field_id": f.get("id"),
                "type": f.get("type"),
                "choices": choices,
            }
        return {
            "table_id": t.get("id"),
            "fields": fields,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "fetched_at_mono": time.monotonic(),
        }

    @staticmethod
    def _load_snapshot(table: str) -> dict | None:
        """
        PR3B.1 tier 3: read the latest successful (Status=OK) canonical JSON
        snapshot from Tables.SCHEMA_SNAPSHOTS (PR3A's archive) and extract
        this table's entry from it. Read-only against PR3A's data — does
        not call tools/schema_snapshot.py's write path, does not touch
        document_converter (only the already-uploaded JSON attachment is
        read, never the XLSX report). Returns None (logged) on any failure
        — callers must fail through to the seed tier, never raise.
        """
        try:
            from tools.airtable_tools import airtable_get_records
            from airtable_schema import SchemaSnapshotFields, SchemaSnapshotStatus, Tables
            import httpx
        except Exception as e:
            logger.warning("[RuntimeSchemaProvider] snapshot tier import failure: %s", e)
            return None

        try:
            records = airtable_get_records(Tables.SCHEMA_SNAPSHOTS, "")
        except Exception as e:
            logger.warning("[RuntimeSchemaProvider] snapshot tier: could not list records: %s", e)
            return None

        ok_records = [
            r for r in records
            if r.get("fields", {}).get(SchemaSnapshotFields.STATUS) == SchemaSnapshotStatus.OK
        ]
        if not ok_records:
            logger.warning("[RuntimeSchemaProvider] snapshot tier: no Status=OK snapshot record found")
            return None

        latest = max(
            ok_records,
            key=lambda r: str(r.get("fields", {}).get(SchemaSnapshotFields.SNAPSHOT_DATE, "")),
        )
        attachments = latest.get("fields", {}).get(SchemaSnapshotFields.SNAPSHOT_FILE, []) or []
        json_attachment = next(
            (a for a in attachments if a.get("filename", "").endswith(".json")), None
        )
        if not json_attachment:
            logger.warning("[RuntimeSchemaProvider] snapshot tier: latest OK record has no JSON attachment")
            return None

        try:
            r = httpx.get(json_attachment["url"], timeout=15)
            r.raise_for_status()
            snapshot = r.json()
        except Exception as e:
            logger.warning("[RuntimeSchemaProvider] snapshot tier: failed to download/parse JSON: %s", e)
            return None

        for t in snapshot.get("tables", []):
            if t.get("table_name") == table:
                fields = {
                    f["field_name"]: {
                        "field_id": f.get("field_id"),
                        "type": f.get("field_type"),
                        "choices": list(f.get("choices", [])),
                    }
                    for f in t.get("fields", [])
                }
                return {
                    "table_id": t.get("table_id"),
                    "fields": fields,
                    "fetched_at": snapshot.get("fetched_at"),
                    "fetched_at_mono": time.monotonic(),
                }

        logger.warning(
            "[RuntimeSchemaProvider] snapshot tier: table '%s' not found in latest snapshot", table
        )
        return None

    @staticmethod
    def _seed_contract(table: str) -> dict:
        """schema_cache.json seed via the existing, unchanged
        schema_validator.get_known_fields(). Always mode="name_only",
        table_id=None, choices=[] — schema_cache.json has never stored
        select-option choices, so this is not a special case to fix here."""
        import schema_validator as _sv

        known = _sv.get_known_fields(table)
        return {
            "table_id": None,
            "mode": "name_only",
            "source": "seed",
            "fetched_at": None,
            "fields": {name: {"field_id": None, "type": None, "choices": []} for name in known},
        }


# ══════════════════════════════════════════════════════════════════
# Module-level singleton for production use — construct a fresh
# RuntimeSchemaProvider() directly in tests for isolation.
# ══════════════════════════════════════════════════════════════════

_provider: RuntimeSchemaProvider | None = None


def get_provider() -> RuntimeSchemaProvider:
    global _provider
    if _provider is None:
        _provider = RuntimeSchemaProvider()
    return _provider
