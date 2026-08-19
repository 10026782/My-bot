"""Debug/observation-only shadow comparison: today's live assembly paths vs.
the new Phase 2 retrieval contract.

Never called from context.py or any live prompt-assembly path — see
core/memory_retrieval.py's module docstring for why. This exists so a
comparison (Phase 2B: on-demand via the owner's /memory_shadow command;
this-follow-up: a low-frequency scheduler job, see scheduler.py's
_job_memory_shadow_scan) can run memory_store.get_for_claude() +
cmd_update.get_recent_business_context() (today's live behavior, both
completely untouched) against build_memory_snapshot() (new, side path)
without either one influencing the other. No prompt, no model call, no
mutation of either source's state. record_shadow_comparison() below is the
only thing that writes anywhere, and it writes structured counts only (see
core/migrations/004_memory_shadow_comparisons.sql) — never memory content.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from core.memory_retrieval import build_memory_snapshot
from core.memory_retrieval_contract import (
    MemoryRetrievalRequest,
    MemoryRetrievalValidationError,
    MemorySnapshot,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ShadowComparison:
    request: MemoryRetrievalRequest
    live_conversation_message_count: int
    live_business_memory_char_count: int
    new_snapshot: MemorySnapshot


def compare_with_live_paths(request: MemoryRetrievalRequest, *, memory_key: str) -> ShadowComparison:
    """Read-only comparison. Both live-path calls below are the exact same
    read calls the live turn loop already makes — memory_store.get_for_claude()
    (guarded by a lock, no writes) and cmd_update.get_recent_business_context()
    (Airtable read only) — unmodified and uninfluenced by the new path."""
    from cmd_update import get_recent_business_context
    from memory_store import memory as _memory_store

    live_messages = _memory_store.get_for_claude(memory_key)
    live_business_text = get_recent_business_context(domain=request.domain_id or "general", limit=5)
    new_snapshot = build_memory_snapshot(request)

    return ShadowComparison(
        request=request,
        live_conversation_message_count=len(live_messages),
        live_business_memory_char_count=len(live_business_text),
        new_snapshot=new_snapshot,
    )


def build_shadow_request(identity) -> MemoryRetrievalRequest | None:
    """Builds a MemoryRetrievalRequest from proven identity fields only —
    tenant_id/canonical_user_id/domain_id come straight from resolve_identity's
    result. session_id/entity_type/entity_id are left unset: nothing in the
    live runtime today produces a provable session/entity id to attach here,
    and guessing one would violate the read-only/no-fabrication contract this
    whole subsystem follows. Returns None (caller should report
    NOT_ENOUGH_CONTEXT) if even tenant_id/canonical_user_id aren't provable."""
    try:
        return MemoryRetrievalRequest(
            tenant_id=identity.tenant_id,
            canonical_user_id=identity.user_id,
            domain_id=identity.domain_id,
        )
    except MemoryRetrievalValidationError:
        return None


def format_shadow_comparison(comparison: ShadowComparison) -> str:
    """Short, diff-focused summary — never a dump of memory content itself
    (no message text, no business-memory text, no episodic payloads)."""
    meta = comparison.new_snapshot.metadata
    bm_count = len(comparison.new_snapshot.business_facts)
    ep_count = len(comparison.new_snapshot.episodic_entries)

    def _truncated(returned: int, budget: int) -> str:
        return "possibly (returned == budget)" if budget and returned == budget else "no"

    lines = [
        "Memory Shadow", "",
        f"tenant={meta.tenant_id} user={meta.canonical_user_id} domain={meta.domain_id or '-'}",
        "",
        "Legacy paths:",
        f"  conversation messages: {comparison.live_conversation_message_count}",
        f"  business memory: {comparison.live_business_memory_char_count} chars (opaque blob, no item boundaries)",
        "",
        "New retrieval contract:",
        f"  business memory: {bm_count} items (available={meta.business_memory_available}"
        f"{', error=' + meta.business_memory_error if meta.business_memory_error else ''})"
        f" budget={meta.business_memory_budget} truncated={_truncated(bm_count, meta.business_memory_budget)}",
        f"  episodic: {ep_count} items (available={meta.episodic_memory_available}"
        f"{', error=' + meta.episodic_memory_error if meta.episodic_memory_error else ''})"
        f" budget={meta.episodic_memory_budget} truncated={_truncated(ep_count, meta.episodic_memory_budget)}",
        "",
        "Items only in legacy / items only in new: not computable — legacy paths return"
        " unstructured output (text blob / differently-shaped message list) with no item"
        " identity comparable to the new structured items.",
        "Ordering: new path is deterministic-recency sorted; legacy Business Memory has no"
        " defined ordering (raw Airtable API order).",
    ]
    return "\n".join(lines)


def record_shadow_comparison(comparison: ShadowComparison) -> bool:
    """Durably records one comparison's structured counts (never memory
    content — mirrors core/usage_telemetry.py's record_usage() fail-soft
    pattern). Returns True if the row was written, False if PostgreSQL is
    unavailable or the write failed. Never raises."""
    meta = comparison.new_snapshot.metadata
    bm_count = len(comparison.new_snapshot.business_facts)
    ep_count = len(comparison.new_snapshot.episodic_entries)

    from core.database import get_conn, release_conn

    conn = get_conn()
    if conn is None:
        logger.error(
            "[MemoryShadow] PostgreSQL unavailable — comparison NOT durably "
            "recorded (tenant=%s user=%s). Shadow-only observation; the gap "
            "itself should still be investigated.",
            meta.tenant_id, meta.canonical_user_id,
        )
        return False

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO memory_shadow_comparisons
                    (ts, tenant_id, canonical_user_id, domain_id,
                     legacy_message_count, legacy_business_char_count,
                     new_business_count, new_business_available, new_business_error, new_business_budget,
                     new_episodic_count, new_episodic_available, new_episodic_error, new_episodic_budget)
                VALUES (NOW(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                """,
                (
                    meta.tenant_id, meta.canonical_user_id, meta.domain_id,
                    comparison.live_conversation_message_count, comparison.live_business_memory_char_count,
                    bm_count, meta.business_memory_available, meta.business_memory_error, meta.business_memory_budget,
                    ep_count, meta.episodic_memory_available, meta.episodic_memory_error, meta.episodic_memory_budget,
                ),
            )
            conn.commit()
        logger.debug(
            "[MemoryShadow] recorded comparison tenant=%s user=%s bm=%d ep=%d",
            meta.tenant_id, meta.canonical_user_id, bm_count, ep_count,
        )
        return True
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        logger.error("[MemoryShadow] record_shadow_comparison failed: %s", e, exc_info=True)
        return False
    finally:
        release_conn(conn)
