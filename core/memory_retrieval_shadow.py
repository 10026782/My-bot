"""Debug/test-only shadow comparison: today's live assembly paths vs. the
new Phase 2 retrieval contract.

Never called from app.py, context.py, or any live request path — see
core/memory_retrieval.py's module docstring for why. This exists so a
developer (Phase 2B: the owner, via /memory_shadow) can manually compare
memory_store.get_for_claude() + cmd_update.get_recent_business_context()
(today's live behavior, both completely untouched) against
build_memory_snapshot() (new, side path) without either one influencing the
other. No prompt, no model call, no mutation of either source's state.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.memory_retrieval import build_memory_snapshot
from core.memory_retrieval_contract import (
    MemoryRetrievalRequest,
    MemoryRetrievalValidationError,
    MemorySnapshot,
)


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
