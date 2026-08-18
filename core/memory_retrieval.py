"""build_memory_snapshot() — Phase 2 read-only retrieval over Business
Memory and Episodic Memory.

SHADOW-ONLY: nothing in this module is called from app.py, context.py, or
memory_store.py. It queries the existing sources of truth directly (the
same pattern context.py's Business Memory injection already uses — a live
Airtable read on every call) and returns a MemorySnapshot; it never writes,
never calls the LLM, never calls the approval/tool-execution pipeline, and never
mutates memory_store's live state. See
docs/research/BOSS_MEMORY_RETRIEVAL_ARCHITECTURE_2026-08.md.

Failure semantics: a request with a missing tenant_id/canonical_user_id is
a caller bug — MemoryRetrievalRequest.__post_init__ raises. A store being
down (Episodic Postgres unreachable, Business Memory Airtable call
failing) is an operational condition, not a caller bug: it is caught,
recorded in SnapshotMetadata, and yields an empty result for that category
only. This mirrors cmd_update.get_recent_business_context()'s existing
"never blocks" try/except contract, extended to the new Episodic source.
"""

from __future__ import annotations

import logging
import time
from datetime import date

from core.episodic_entry import EpisodicEntry
from core.episodic_memory_repository import EpisodicMemoryError, EpisodicMemoryRepository
from core.memory_retrieval_contract import (
    BusinessMemoryItem,
    MemoryRetrievalRequest,
    MemorySnapshot,
    SnapshotMetadata,
)

logger = logging.getLogger(__name__)

# Business Memory (Airtable) carries no tenant_id field today — every row is
# implicitly scoped to the single tenant this deployment actually runs (see
# identity.py's Identity.tenant_id default and _load_registry()). Rather
# than pretend to enforce a per-row tenant filter the schema can't express,
# retrieval only attaches Business Memory for that one known tenant and
# returns empty (not an error, not a leak) for any other tenant_id — a real
# multi-tenant Business Memory needs a schema change, out of scope here.
_SINGLE_TENANT_BUSINESS_MEMORY_SCOPE = "boss_hq"

# ponytail: Airtable reads have no server-side sort; both caps below
# over-fetch, then sort/slice in Python for deterministic recency ordering.
# Fine at current data volume — upgrade path is a server-side sorted query
# (or a filtered+descending EpisodicMemoryRepository method) if either
# source grows enough for this to matter.
_BUSINESS_MEMORY_QUERY_CAP = 200
_EPISODIC_SCOPED_QUERY_CAP = 500


def _fetch_episodic_entries(
    request: MemoryRetrievalRequest,
) -> tuple[list[EpisodicEntry], bool, str | None]:
    if request.episodic_memory_budget == 0:
        return [], True, None
    repo = EpisodicMemoryRepository()
    try:
        if request.session_id is None and request.entity_type is None and request.entity_id is None:
            entries = repo.list_recent(request.tenant_id, limit=request.episodic_memory_budget)
        else:
            candidates = repo.list_by_tenant(
                request.tenant_id,
                session_id=request.session_id,
                entity_type=request.entity_type,
                entity_id=request.entity_id,
                limit=_EPISODIC_SCOPED_QUERY_CAP,
            )
            candidates.sort(key=lambda e: (e.occurred_at, e.id or ""), reverse=True)
            entries = candidates[: request.episodic_memory_budget]
        return entries, True, None
    except EpisodicMemoryError as exc:
        logger.warning("[MemoryRetrieval] episodic memory unavailable: %s", exc)
        return [], False, str(exc)[:200]


def _parse_event_date(raw: object) -> float | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        return time.mktime(date.fromisoformat(raw.strip()).timetuple())
    except ValueError:
        return None


def _fetch_business_memory(
    request: MemoryRetrievalRequest,
) -> tuple[list[BusinessMemoryItem], bool, str | None]:
    if request.business_memory_budget == 0:
        return [], True, None
    if request.tenant_id != _SINGLE_TENANT_BUSINESS_MEMORY_SCOPE:
        return [], True, None
    try:
        from airtable_schema import BusinessMemoryFields as BMF
        from airtable_schema import Tables
        from cmd_update import resolve_business_memory_domain
        from tools.airtable_tools import airtable_get_records

        domain = request.domain_id or ""
        if domain and domain != "general":
            resolved = resolve_business_memory_domain(domain)
            airtable_domain = resolved["value"] if resolved["ok"] else "General"
            formula = (
                f"OR("
                f"{{{BMF.DOMAIN}}}='{airtable_domain}',"
                f"{{{BMF.DOMAIN}}}='General',"
                f"FIND('{domain}',ARRAYJOIN({{{BMF.TAGS}}}))"
                f")"
            )
        else:
            formula = ""

        records = airtable_get_records(
            Tables.BUSINESS_MEMORY, formula, max_records=_BUSINESS_MEMORY_QUERY_CAP
        )
        items = []
        for rec in records:
            fields = rec.get("fields", {})
            items.append(
                BusinessMemoryItem(
                    record_id=rec.get("id", ""),
                    title=fields.get(BMF.TITLE, ""),
                    description=fields.get(BMF.DESCRIPTION, ""),
                    event_type=fields.get(BMF.EVENT_TYPE),
                    domain=fields.get(BMF.DOMAIN),
                    occurred_at=_parse_event_date(fields.get(BMF.DATE)),
                )
            )
        items.sort(key=lambda i: (i.occurred_at or 0.0, i.record_id), reverse=True)
        return items[: request.business_memory_budget], True, None
    except Exception as exc:
        logger.warning("[MemoryRetrieval] business memory unavailable: %s", exc)
        return [], False, str(exc)[:200]


def build_memory_snapshot(request: MemoryRetrievalRequest) -> MemorySnapshot:
    """Read-only. Never raises for a store being unavailable — only for an
    invalid request (see MemoryRetrievalRequest.__post_init__)."""
    business_items, business_ok, business_err = _fetch_business_memory(request)
    episodic_items, episodic_ok, episodic_err = _fetch_episodic_entries(request)

    metadata = SnapshotMetadata(
        generated_at=time.time(),
        tenant_id=request.tenant_id,
        canonical_user_id=request.canonical_user_id,
        session_id=request.session_id,
        entity_type=request.entity_type,
        entity_id=request.entity_id,
        domain_id=request.domain_id,
        business_memory_available=business_ok,
        business_memory_error=business_err,
        business_memory_returned=len(business_items),
        business_memory_budget=request.business_memory_budget,
        episodic_memory_available=episodic_ok,
        episodic_memory_error=episodic_err,
        episodic_memory_returned=len(episodic_items),
        episodic_memory_budget=request.episodic_memory_budget,
    )
    return MemorySnapshot(
        business_facts=tuple(business_items),
        episodic_entries=tuple(episodic_items),
        metadata=metadata,
    )
