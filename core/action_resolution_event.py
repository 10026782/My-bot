# core/action_resolution_event.py — BUG-149
#
# A dependency-free event type describing a terminal ActionContract outcome.
# Zero imports beyond stdlib on purpose: core/action_gateway.py (Layer 4)
# depends on this module directly, but must never import memory_store or any
# other consumer of this event — see ActionGateway.set_resolution_sink()/
# _emit_resolution() and core/action_resolution_projection.py (the one
# module allowed to know about both this type and memory_store).
#
# Real terminal ActionContract.status values, verified against
# core/action_gateway.py (dataclass comment + every update_status()/
# _persist_execution_status() call site): rejected, completed (or its legacy
# RAM-only alias "executed"), failed, outcome_unknown. "approved" is
# deliberately NOT a member here — it is not terminal; execution can still
# fail/timeout after approval. "expired"/"cancelled" are not modeled as real
# ActionContract.status values anywhere in the codebase today (verified by
# grep — CONTRACT_PENDING_TTL_SECONDS/_is_expired() is a read-time filter in
# find_live_contracts(), never a status write; "cancelled" appears only as a
# TMA Approvals-table query filter, a separate non-authoritative projection)
# — out of scope for this event type until a real write-time transition for
# either exists.

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import time


class ActionResolutionOutcome(str, Enum):
    REJECTED        = "rejected"
    COMPLETED       = "completed"   # also covers the legacy RAM-only "executed" alias
    FAILED          = "failed"
    OUTCOME_UNKNOWN = "outcome_unknown"


_NO_RETRY_INSTRUCTION_DEFAULT = (
    "אל תציע או תבצע פעולה זו שוב ביוזמתך. פעל על כך רק אם המשתמש "
    "יבקש זאת שוב באופן מפורש בהודעה חדשה."
)


@dataclass(frozen=True)
class ActionResolutionEvent:
    """Terminal-outcome event for one ActionContract. Emitted at most once
    per (contract_id, outcome, contract_version) tuple — see dedupe_key.

    routing_key MUST be contract.canonical_user_id, unchanged — proven equal
    to identity.memory_key at every current propose_action() call site
    (app.py:1156/1215, tma_api.py:561), and independently equal to
    ctx.memory_key (context.py:289), which is what memory_store.py's
    add_context_event()/get_context_events_for_claude() are keyed by. Never
    re-derive this from `approver` — for owner-approves-someone-else's-
    request flows, the resolution belongs in the ORIGINAL REQUESTER's future
    context, not the approver's.

    contract_version is whatever ActionContract.version held immediately
    after the transition that produced this event (see ActionGateway.
    _emit_resolution(), which re-fetches the contract by id rather than
    trusting a possibly-stale pre-transition reference — durable-repository
    transitions replace the cached object, in-place RAM mutation does not).
    Caveat, documented rather than hidden: with FEATURE_ACTION_CONTRACT_
    PERSISTENCE at its current default (off), version never increments
    (core/action_gateway.py's RAM-only update_status() path does not bump
    it) — so contract_version is always 1 in the current default
    configuration, and contract_id+outcome alone is what actually carries
    the dedupe power today (which is already sufficient: a contract can only
    reach a given terminal outcome once — reject() guards status!="pending",
    and _persist_execution_status() fires once per successful terminal
    transition). contract_version becomes a genuinely independent
    dimension once durable persistence is enabled, where the version int
    real-increments per transition.
    """

    contract_id:           str
    routing_key:            str
    tenant_id:               str
    tool_name:                str
    outcome:                  ActionResolutionOutcome
    terminal:                  bool
    action_summary:             str
    contract_version:            int
    no_retry_instruction:         str = _NO_RETRY_INSTRUCTION_DEFAULT
    created_at:                    float = field(default_factory=time.time)

    @property
    def dedupe_key(self) -> str:
        """Deterministic idempotency key: contract_id + outcome + resulting
        contract version. A repeated callback/retry that produces the exact
        same (contract_id, outcome, version) tuple must project at most
        once — see memory_store.MemoryStore.add_context_event()."""
        return f"{self.contract_id}:{self.outcome.value}:v{self.contract_version}"
