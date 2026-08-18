"""Debug/test-only shadow comparison: today's live assembly paths vs. the
new Phase 2 retrieval contract.

Never called from app.py, context.py, or any live request path — see
core/memory_retrieval.py's module docstring for why. This exists so a
developer can manually compare memory_store.get_for_claude() +
cmd_update.get_recent_business_context() (today's live behavior, both
completely untouched) against build_memory_snapshot() (new, side path)
without either one influencing the other. No prompt, no model call, no
mutation of either source's state.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.memory_retrieval import build_memory_snapshot
from core.memory_retrieval_contract import MemoryRetrievalRequest, MemorySnapshot


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
