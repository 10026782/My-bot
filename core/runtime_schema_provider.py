# core/runtime_schema_provider.py — PR3B (rev.2): RuntimeSchemaProvider
#
# One schema provider that Airtable write validation reads from, per table:
#   1. Fresh live Meta API fetch (when the TTL for that table has expired).
#   2. Last-good in-memory result for that table, served while its TTL is
#      still valid — no Meta API call at all in this case.
#   3. If the TTL expired and the live re-fetch fails: the same last-good
#      result, served stale, with a WARNING log (age included).
#   4. If there is no last-good result at all (cold start) and the live
#      fetch fails: schema_cache.json seed via the existing, unchanged
#      schema_validator.get_known_fields() — mode="name_only", table_id=None,
#      choices=[] always (schema_cache.json has never stored choices).
#
# This module owns no on-disk state — schema_cache.json is never written
# here, and this provider does not depend on PR3A's snapshot archive or on
# document_converter in any way.

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
            "source": "live" | "cached" | "seed",
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

            logger.critical(
                "[RuntimeSchemaProvider] no live/cached schema for %s — "
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
