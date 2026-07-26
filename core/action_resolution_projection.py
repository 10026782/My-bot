# core/action_resolution_projection.py — BUG-149
#
# The one adapter allowed to import both core.action_resolution_event and
# memory_store. core/action_gateway.py (Layer 4) never imports memory_store
# directly — it emits ActionResolutionEvent through an injected callable
# (ActionGateway.set_resolution_sink()); this module is that callable's
# real implementation, wired in once from app.py at startup.
#
# NON-DURABLE, PROCESS-LOCAL: memory_store.MemoryStore is an in-process dict
# (see its own module docstring) — a restart loses everything projected
# here, same as the rest of conversation memory. This projection only
# improves what a FUTURE same-process model call sees; it is never the
# lifecycle source of truth. ActionContract/ExecutionLedger/
# ActionContractRepository remain that, exclusively, unaffected by whether
# this projection succeeds, is delayed, or is lost entirely on restart. The
# deterministic MULTI_MUTATION_CONTEXT_MISMATCH guard in app.py's tool loop
# is the actual safety invariant against stale-context re-proposals — this
# projection is a best-effort mitigation on top of it, not a substitute.

from __future__ import annotations

import logging

from core.action_resolution_event import ActionResolutionEvent

logger = logging.getLogger(__name__)


def _render_context_event(event: ActionResolutionEvent) -> str:
    """Structured, clearly-tagged block — deliberately NOT ordinary
    assistant prose. outcome/terminality/the no-retry rule are each on
    their own labeled line so the model can parse them reliably rather than
    having to infer status from conversational tone."""
    return (
        f"[ACTION_RESOLUTION outcome={event.outcome.value} "
        f"terminal={str(event.terminal).lower()} contract={event.contract_id[:8]}]\n"
        f"פעולה: {event.action_summary}\n"
        f"כלל: {event.no_retry_instruction}\n"
        f"[/ACTION_RESOLUTION]"
    )


def project_resolution_event_to_memory(event: ActionResolutionEvent) -> None:
    """Writes one ActionResolutionEvent into memory_store's distinct
    context-event channel (NOT the ordinary user/assistant conversation
    history — see MemoryStore.add_context_event()'s own docstring for why).
    Idempotent via event.dedupe_key: memory_store itself is the layer that
    enforces at-most-once, not this function — this function only computes
    what to write and where.

    Callers (ActionGateway._emit_resolution()) are responsible for the
    try/except around this call — this function does not swallow its own
    exceptions, so a memory_store-side failure surfaces to the caller's
    WARNING-level, no-sensitive-payload log rather than being silently lost
    here twice."""
    from memory_store import memory

    memory.add_context_event(
        event.routing_key, event.dedupe_key, _render_context_event(event),
    )
