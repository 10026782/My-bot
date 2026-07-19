# core/turn_envelope.py — TurnCoordinator Phase 0: observation only.
#
# See docs/architecture/turn-coordinator/TURN_COORDINATOR_PROPOSAL_V2.md and
# docs/architecture/f52-unified-approval-runtime/audits/phase-4c/
# TURN_OWNERSHIP_EXTENSION.md for the design and the call-site inventory this
# module is Phase 0 of.
#
# Phase 0 scope (Gate A of the proposal's DoD) — everything this module does:
#   - builds a TurnEnvelope snapshot from state the CALLER already knows
#     (this module does not query app.py/action_gateway/event_bus/session
#     stores itself — see "no God Object" in the proposal; the caller passes
#     in already-resolved flags)
#   - logs it, structured, once per turn
#   - never raises into the caller (build_turn_envelope has no side effects
#     that can fail; log_turn_envelope is wrapped defensively by callers)
#
# Explicitly NOT in Phase 0 (do not add here without a phase bump + DoD review):
#   - no injection into the agent's prompt/context
#   - no new persistence (no ConversationState, no TurnStateProjection — see
#     the proposal's Persistence section; this is a pure in-memory snapshot,
#     rebuilt every turn from live sources, never stored)
#   - no resolve_numbered_reference() (Phase 2)
#   - no real Policy Source evaluator (Phase 1) — policy_snapshot_version
#     below is a static marker for the classification table in this file,
#     not a live policy engine snapshot
#   - no ModelProviderRegistry (Phase 2) — agent_availability below is a
#     placeholder value, not backed by real provider selection yet

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal, Optional

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════
# Part 1 — Pending Awareness (multi-queue)
# ══════════════════════════════════════════════════

# Sources a pending queue can come from. "file_flow" also temporarily covers
# _pending_voice_edits (media_handler.py) — see TURN_OWNERSHIP_EXTENSION.md
# finding 4: this is an explicit, provisional placeholder pending a schema
# decision by whoever owns the proposal, not a permanent classification.
PendingQueueSource = Literal[
    "action_gateway", "lead_capture", "file_flow", "task_flow", "system"
]


@dataclass(frozen=True)
class PendingItem:
    index: int
    id: str
    kind: str
    label: str


@dataclass(frozen=True)
class PendingQueueAwareness:
    queue_id: str
    source: PendingQueueSource
    kind: str
    summary: str
    items: tuple[PendingItem, ...] = ()
    approval_granularity: Literal["all_or_nothing", "per_item", "single_choice", "none"] = "none"
    priority: int = 0


# ══════════════════════════════════════════════════
# Part 2 — Capability Awareness (static classification only, Phase 0)
# ══════════════════════════════════════════════════

class ExecutionKind(Enum):
    CONVERSATIONAL = "conversational"
    DETERMINISTIC = "deterministic"
    AGENT_INTERPRETED = "agent_interpreted"


# Grounded directly in TURN_OWNERSHIP_EXTENSION.md's agent_interpreted /
# deterministic_without_agent columns (audit revision 9383905) — not a fresh
# invention. Each key is a call-site identifier, not a tool name, because the
# audit found the two don't line up 1:1 (e.g. a single tool_registry tool can
# only be *reached* via agent interpretation today, per AP-01/AP-33).
KNOWN_EXECUTION_KINDS: dict[str, ExecutionKind] = {
    # AP-01/AP-33 — every tool_registry-gated tool call is only reachable by
    # the agent choosing to call it from free text today; see the audit's
    # AP-04..AP-08 "Y in principle / N in wiring" note — the underlying
    # parsers ARE deterministic, but only run inside run_agent() (§Routing-
    # order gap), so from a call-site-reachability standpoint they are
    # listed under their own keys below, not folded into this one.
    "agent_tool_call": ExecutionKind.AGENT_INTERPRETED,
    # AP-04..AP-08 — ActionGateway text parsers. Deterministic once reached;
    # the routing-order gap is a wiring issue, not a classification issue.
    "confirm_word": ExecutionKind.DETERMINISTIC,
    "combined_word": ExecutionKind.DETERMINISTIC,
    "disambiguation": ExecutionKind.DETERMINISTIC,
    "cancellation_word": ExecutionKind.DETERMINISTIC,
    "reconfirmation": ExecutionKind.DETERMINISTIC,
    "override_word": ExecutionKind.DETERMINISTIC,
    # AP-02/AP-03 — Telegram callback approve/reject.
    "telegram_callback_approve": ExecutionKind.DETERMINISTIC,
    "telegram_callback_reject": ExecutionKind.DETERMINISTIC,
    # AP-12 — lead batch preview confirm/cancel (all-or-nothing only; see
    # finding 1b — the missing partial-selection ability is a scope gap, not
    # an agent-dependency question, so confirm/cancel themselves stay
    # deterministic).
    "lead_batch_preview_confirm": ExecutionKind.DETERMINISTIC,
    # AP-13..AP-25 — TMA REST routes, no LLM involved.
    "tma_write_route": ExecutionKind.DETERMINISTIC,
    # AP-48/AP-49 — slash commands.
    "slash_command": ExecutionKind.DETERMINISTIC,
    # AP-41 and the lead_qualifier.py sub-flow of AP-50 — background LLM
    # calls. Per finding 6, these are AGENT_INTERPRETED in the ExecutionKind
    # sense but are NOT the live per-turn conversational agent; kept as
    # distinct keys so AGENTLESS scoping (does it suspend background jobs
    # too?) can be decided explicitly later instead of being silently
    # conflated with "agent_tool_call".
    "background_job_llm_analysis": ExecutionKind.AGENT_INTERPRETED,
    "lead_qualifier_scoring": ExecutionKind.AGENT_INTERPRETED,
    # AP-50 sub-flow — furniture_lead_funnel.py is an explicit deterministic
    # FSM per CLAUDE.md, not the general agent flow.
    "furniture_lead_funnel": ExecutionKind.DETERMINISTIC,
}

# Version marker for KNOWN_EXECUTION_KINDS above — bump when entries change.
# Not a live policy engine snapshot (that's Phase 1's Policy Source); logged
# so a later drift between this static table and real dispatcher/registry
# behavior can be dated.
POLICY_SNAPSHOT_VERSION = "phase0-static-v1"


def execution_kind_of(call_site_id: str) -> Optional[ExecutionKind]:
    """Static lookup only. Returns None for an unrecognized call_site_id —
    callers must treat that as "not yet classified", never guess."""
    return KNOWN_EXECUTION_KINDS.get(call_site_id)


# ══════════════════════════════════════════════════
# Part 3 — Agent availability (placeholder, Phase 0)
# ══════════════════════════════════════════════════

class AgentAvailability(Enum):
    PRIMARY = "primary"
    FALLBACK = "fallback"
    AGENTLESS = "agentless"


@dataclass(frozen=True)
class AgentAvailabilityStatus:
    mode: AgentAvailability
    active_provider_id: Optional[str] = None
    selection_reason: Optional[str] = None


# Phase 0 placeholder: run_agent() only calls this builder when it is about
# to invoke the live agent, so PRIMARY is observationally correct today. Not
# backed by ModelProviderRegistry/select_provider() (Phase 2) — do not read
# this as proof AGENTLESS detection exists yet.
_PHASE0_AGENT_AVAILABILITY = AgentAvailabilityStatus(
    mode=AgentAvailability.PRIMARY,
    active_provider_id=None,
    selection_reason="phase0_not_tracked",
)


# ══════════════════════════════════════════════════
# TurnEnvelope
# ══════════════════════════════════════════════════

TurnMode = Literal[
    "approval_pending", "reconfirmation_required", "partial_selection_ambiguous", "free_agent"
]

# Priority order per the proposal's §Policy Source — explicit reference to a
# named queue is highest priority but requires the caller to have already
# resolved that (not something this module can determine); the remaining
# order matches the proposal exactly.
_MODE_PRIORITY: dict[str, int] = {
    "reconfirmation_required": 1,
    "partial_selection_ambiguous": 2,
    "approval_pending": 3,
    "free_agent": 4,
}


@dataclass(frozen=True)
class TurnEnvelope:
    turn_mode: TurnMode
    pending_queues: tuple[PendingQueueAwareness, ...]
    active_queue_id: Optional[str]  # logged verbatim by to_log_dict() — callers building
                                     # PendingQueueAwareness.queue_id must fingerprint any
                                     # identifier embedded in it (see app.py's
                                     # _build_and_log_turn_envelope, which uses _sanitize_id())
    resolved_reference: Optional[str]  # always None in Phase 0 — no resolve_numbered_reference() yet
    reply_owner: Optional[str]  # best-effort label of who WOULD reply today, not a new mechanism
    message_kind: Optional[str]  # always None in Phase 0 — not computed until Phase 4
    policy_snapshot_version: str
    agent_availability: AgentAvailabilityStatus

    def to_log_dict(self) -> dict:
        """Structured fields for log_turn_envelope() — matches Gate A's
        required log-only field list from the proposal's Phase 0 description.
        multi_contract_conflict is the Case C1 signal (see
        docs/architecture/turn-coordinator/CASE_C_CLARIFICATION_CONTINUITY.md)
        — more than one live ActionContract simultaneously pending for the
        same identity, which BatchQueueStore's own design treats as an
        invariant violation regardless of how it happened."""
        return {
            "turn_mode": self.turn_mode,
            "queue_count": len(self.pending_queues),
            "queue_sources": [q.source for q in self.pending_queues],
            "active_queue_id": self.active_queue_id,
            "resolved_reference": self.resolved_reference,
            "reply_owner": self.reply_owner,
            "message_kind": self.message_kind,
            "multi_contract_conflict": any(
                q.source == "action_gateway" and q.kind == "action_contract" and len(q.items) > 1
                for q in self.pending_queues
            ),
            "policy_snapshot_version": self.policy_snapshot_version,
            "agent_availability_mode": self.agent_availability.mode.value,
        }


def build_turn_envelope(
    *,
    live_contract_reply_owner: Optional[str] = None,
    reconfirmation_required: bool = False,
    disambiguation_active: bool = False,
    action_gateway_queue: Optional[PendingQueueAwareness] = None,
    lead_capture_queue: Optional[PendingQueueAwareness] = None,
    other_queues: tuple[PendingQueueAwareness, ...] = (),
) -> TurnEnvelope:
    """
    Pure function — no I/O, no imports of app.py/action_gateway/event_bus/
    session_store. The caller (app.py) already resolves these flags for its
    own routing today; this only reshapes what's already known into one
    snapshot for logging. See module docstring for what Phase 0 does and does
    not do.

    live_contract_reply_owner: if the caller already knows a live
        ActionContract exists and who its natural reply owner is today
        (e.g. "gateway" for AP-02/04-08 flows), pass it through — this
        function does not infer it.
    """
    queues: list[PendingQueueAwareness] = []
    if action_gateway_queue is not None:
        queues.append(action_gateway_queue)
    if lead_capture_queue is not None:
        queues.append(lead_capture_queue)
    queues.extend(other_queues)

    if reconfirmation_required:
        mode: TurnMode = "reconfirmation_required"
    elif disambiguation_active:
        mode = "partial_selection_ambiguous"
    elif queues:
        mode = "approval_pending"
    else:
        mode = "free_agent"

    active_queue_id = None
    if queues:
        # Priority order per §Policy Source: explicit-queue-reference is the
        # caller's job to resolve (not available here); this picks the
        # highest-priority queue among what's currently pending as a
        # Phase-0 best-effort default, matching the mode just computed.
        ordered = sorted(queues, key=lambda q: q.priority)
        active_queue_id = ordered[0].queue_id

    reply_owner = live_contract_reply_owner if queues else "agent"

    return TurnEnvelope(
        turn_mode=mode,
        pending_queues=tuple(queues),
        active_queue_id=active_queue_id,
        resolved_reference=None,
        reply_owner=reply_owner,
        message_kind=None,
        policy_snapshot_version=POLICY_SNAPSHOT_VERSION,
        agent_availability=_PHASE0_AGENT_AVAILABILITY,
    )


def _fingerprint(raw_id: str) -> str:
    """Same BUG-072 pattern as app.py's _sanitize_id() — a short,
    non-reversible fingerprint instead of a raw phone number/chat/user id.
    Duplicated (not imported from app.py) so this module has zero dependency
    on app.py and can never accidentally log an identifier verbatim even if
    a future caller forgets to sanitize before calling this function — see
    module docstring's "no God Object" note: this module owns its own output
    safety, it does not trust the caller for it."""
    if not raw_id:
        return "-"
    return hashlib.sha256(str(raw_id).encode()).hexdigest()[:8]


def log_turn_envelope(envelope: TurnEnvelope, *, canonical_user_id: str = "") -> None:
    """
    The only place this module writes anything — a single structured log
    line. Never raises: a logging failure must never affect the turn (Phase 0
    is observation-only). Callers should still wrap the whole build+log call
    defensively, since this function does not swallow errors from a
    misbehaving logging handler — see run_agent()'s usage in app.py.

    canonical_user_id is always fingerprinted before logging (never logged
    raw), since it is frequently tenant_id:phone_number for WhatsApp
    identities — this runs unconditionally, unflagged, on every turn, so
    there is no flag boundary protecting against a raw phone number ending
    up in logs the way there would be for a flag-gated feature.

    Fields intentionally NEVER logged here (Phase 0 log content boundary):
    no action/tool payload, no user message text, no phone numbers/emails/
    addresses, no lead/business record field values. TurnEnvelope.to_log_dict()
    only exposes counts, enum values, and (now-fingerprinted) identifiers —
    see its own docstring. Do not widen what to_log_dict() returns to include
    PendingQueueAwareness.items/summary without re-reviewing this boundary.
    """
    try:
        logger.info(
            "[TurnEnvelope] user=%s %s",
            _fingerprint(canonical_user_id),
            json.dumps(envelope.to_log_dict(), ensure_ascii=False, default=str),
        )
    except Exception:
        logger.debug("[TurnEnvelope] logging failed", exc_info=True)


# ══════════════════════════════════════════════════
# Case C — clarification continuity signals (log-only)
# ══════════════════════════════════════════════════
# See docs/architecture/turn-coordinator/CASE_C_CLARIFICATION_CONTINUITY.md
# for the verified failure modes this distinguishes. Both signals are pure
# detection — neither blocks nor alters anything; that is explicitly Phase 1+
# (materialization, invariants 1-3) and Phase 5 (Commitment Grounding,
# invariant 4) work, not Phase 0. Invariant 5 ("Phase 0 must log enough state
# to distinguish C1 from C2") is the entire scope of what follows.


def _agent_text_claims_pending(final_reply: str) -> bool:
    """
    Raw pattern match only — does this text READ like a pending-approval
    claim, independent of whether anything is actually pending. Reuses
    core/anti_hallucination.py's own _AGENT_PENDING_STATUS_PATTERN (single
    source of truth, not a duplicated regex that could drift). Extracted so
    both detect_case_c2_signal() (which combines this with turn state to
    decide "is this claim false") and OwnershipSignal (which records the raw
    claim itself, alongside the turn state, as separate fields — see
    log_ownership_signal()) share one check.
    """
    try:
        from core.anti_hallucination import _AGENT_PENDING_STATUS_PATTERN
        return bool(_AGENT_PENDING_STATUS_PATTERN.search(final_reply or ""))
    except Exception:
        return False


def _classify_agent_leak_pattern(final_reply: str) -> str:
    """
    Best-effort classification of WHICH known Single-Speaker pattern
    final_reply still matches, for diagnosing a TurnOwnershipShadow
    violation (see OwnershipSignal.is_gateway_owned_leak below) — purely
    observational, never used to suppress/alter text. Reuses
    core/anti_hallucination.py's own patterns (single source of truth) in
    the same specificity order sanitize_agent_response()'s call sites
    imply: the BUG-113 approval-invite call-to-action first (most
    specific), then generic pending-narration, then generic
    completion-status wording; "unknown" covers empty text or a genuinely
    novel phrasing none of the three catch. Matches against
    markdown-stripped text for the same reason sanitize_agent_response()
    does (BUG-113-FU) — bold/italic wrapping must not hide the pattern
    class either.
    """
    if not final_reply or not final_reply.strip():
        return "unknown"
    try:
        from core.anti_hallucination import (
            _AGENT_ACTION_STATUS_PATTERN,
            _AGENT_APPROVAL_INVITE_PATTERN,
            _AGENT_PENDING_STATUS_PATTERN,
            _strip_markdown_emphasis,
        )
        norm = _strip_markdown_emphasis(final_reply)
        if _AGENT_APPROVAL_INVITE_PATTERN.search(norm):
            return "approval_invite"
        if _AGENT_PENDING_STATUS_PATTERN.search(norm):
            return "pending_status"
        if _AGENT_ACTION_STATUS_PATTERN.search(norm):
            return "action_status"
    except Exception:
        pass
    return "unknown"


def detect_case_c2_signal(
    final_reply: str, *, queue_count: int, approval_queued_this_turn: bool,
) -> bool:
    """
    True when this turn's reply is shaped like a pending-approval claim
    while nothing is actually pending: queue_count == 0 (this turn's
    post-action state, not the turn-start snapshot — see app.py's call site)
    AND no __approval_queued__ evidence was produced this turn either.

    This is the C2 signature: exactly the gap in sanitize_agent_response()
    documented in CASE_C_CLARIFICATION_CONTINUITY.md — _AGENT_PENDING_STATUS_PATTERN
    is only checked there when FEATURE_ACTION_GATEWAY is on; this function
    checks it unconditionally, but only to log, never to block.
    """
    if queue_count > 0 or approval_queued_this_turn:
        return False
    return _agent_text_claims_pending(final_reply)


def log_case_c_signal(kind: Literal["C1", "C2"], *, canonical_user_id: str = "", detail: str = "") -> None:
    """
    A distinct, visible (WARNING-level) log line — not folded into the
    routine per-turn INFO line — because these are anomaly signatures, not
    routine state, and per the same "fail-open, not silent" principle
    app._build_and_log_turn_envelope()'s build_failed log follows, evidence
    of an anomaly must not disappear into routine noise.

    detail must be a short, fixed, enum-like string only (e.g.
    "live_contracts=2") — never raw text/payload; canonical_user_id is
    fingerprinted the same as log_turn_envelope(). Never raises.
    """
    try:
        logger.warning(
            "[TurnEnvelope] case_c_signal kind=%s user=%s detail=%s",
            kind, _fingerprint(canonical_user_id), detail or "-",
        )
    except Exception:
        logger.debug("[TurnEnvelope] case_c_signal logging failed", exc_info=True)


# ══════════════════════════════════════════════════
# Ownership signal — routine, per-turn (not anomaly-only)
# ══════════════════════════════════════════════════
# Requested explicitly to prove PRECISELY where the agent takes over reply
# ownership without any backing action, across every entry point that routes
# through the agent — not just the rare case where it's already wrong (that
# is what log_case_c_signal("C2", ...) is for). Logged on EVERY turn that
# reaches this checkpoint (any agent-handled turn, any recognized intent),
# routine INFO level, so the population of turns can be analyzed later — not
# just the anomalies. Still log-only: no blocking, no prompt injection, no
# behavior change. See docs/architecture/turn-coordinator/ for the design
# this extends.

@dataclass(frozen=True)
class OwnershipSignal:
    recognized_intent: str
    selected_handler: str
    tool_use_emitted: bool
    approval_queued: bool
    agent_claimed_approval: bool
    reply_owner: str
    # TurnOwnershipShadow (BUG-113-FU2): whether final_reply (post-A32) was
    # still non-empty, and — only meaningful when it was — a best-effort
    # classification of which known pattern it still matched. Neither field
    # stores the raw text itself, same content boundary as
    # agent_claimed_approval above.
    final_reply_nonempty: bool = False
    leaked_pattern_class: str = "unknown"

    def to_log_dict(self) -> dict:
        return {
            "recognized_intent": self.recognized_intent,
            "selected_handler": self.selected_handler,
            "tool_use_emitted": self.tool_use_emitted,
            "approval_queued": self.approval_queued,
            "agent_claimed_approval": self.agent_claimed_approval,
            "reply_owner": self.reply_owner,
            "final_reply_nonempty": self.final_reply_nonempty,
        }

    @property
    def is_hijack(self) -> bool:
        """The exact pattern this signal exists to catch: the agent claims
        an approval is pending, emitted no tool call at all, and nothing was
        actually queued — a claim with zero backing action of any kind, not
        even an attempted (later-blocked) one."""
        return (
            self.agent_claimed_approval
            and not self.tool_use_emitted
            and not self.approval_queued
        )

    @property
    def is_gateway_owned_leak(self) -> bool:
        """TurnOwnershipShadow: reply_owner=="gateway" means A32's
        Single-Speaker gate (anti_hallucination.sanitize_agent_response's
        __approval_queued__-gated suppression branches) should have already
        reduced the agent's own final_reply to "" this turn — ActionGateway,
        not the agent, is the one turn's sole legitimate speaker. If
        final_reply_nonempty is still True here, that suppression didn't
        fire (a live gap, same shape as BUG-113/BUG-113-FU, just not
        necessarily the same pattern), independent of whatever caused it.
        Log-only signal — never used to block or alter final_reply."""
        return (
            self.approval_queued
            and self.reply_owner == "gateway"
            and self.final_reply_nonempty
        )


def build_ownership_signal(
    *, recognized_intent: str, selected_handler: str, tool_use_emitted: bool,
    approval_queued: bool, final_reply: str, reply_owner: str = "agent",
) -> OwnershipSignal:
    """Pure function — no I/O. final_reply is checked, never stored: only
    the boolean/enum matches (agent_claimed_approval, final_reply_nonempty,
    leaked_pattern_class) survive into the returned signal, never the text
    itself (log content boundary — see log_ownership_signal())."""
    _nonempty = bool(final_reply and final_reply.strip())
    return OwnershipSignal(
        recognized_intent=recognized_intent or "unknown",
        selected_handler=selected_handler or "unknown",
        tool_use_emitted=bool(tool_use_emitted),
        approval_queued=bool(approval_queued),
        agent_claimed_approval=_agent_text_claims_pending(final_reply),
        reply_owner=reply_owner,
        final_reply_nonempty=_nonempty,
        leaked_pattern_class=_classify_agent_leak_pattern(final_reply) if _nonempty else "unknown",
    )


def log_ownership_signal(signal: OwnershipSignal, *, canonical_user_id: str = "") -> None:
    """
    Routine per-turn log (INFO) — the full field set, every time, so the
    hijack pattern's actual frequency can be measured against the full
    population of agent-handled turns, not just logged when already
    suspected. When signal.is_hijack is True, ALSO emits a distinct
    WARNING-level line (same fail-open-not-silent principle as
    log_case_c_signal()) so the anomaly is independently greppable without
    parsing JSON out of every routine INFO line. Same treatment for
    signal.is_gateway_owned_leak (TurnOwnershipShadow, BUG-113-FU2) — a
    third, independent anomaly class from is_hijack (this one has a real
    backing approval; the agent just also spoke when it shouldn't have).

    canonical_user_id is fingerprinted (never logged raw) — same PII
    boundary as log_turn_envelope()/log_case_c_signal(). Never raises.
    """
    try:
        logger.info(
            "[TurnEnvelope] ownership_signal user=%s %s",
            _fingerprint(canonical_user_id),
            json.dumps(signal.to_log_dict(), ensure_ascii=False, default=str),
        )
        if signal.is_hijack:
            logger.warning(
                "[TurnEnvelope] ownership_hijack user=%s intent=%s handler=%s",
                _fingerprint(canonical_user_id), signal.recognized_intent, signal.selected_handler,
            )
        if signal.is_gateway_owned_leak:
            logger.warning(
                "[TurnOwnershipShadow] violation=agent_spoke_in_gateway_owned_approval_turn "
                "user=%s pattern_class=%s",
                _fingerprint(canonical_user_id), signal.leaked_pattern_class,
            )
    except Exception:
        logger.debug("[TurnEnvelope] ownership_signal logging failed", exc_info=True)
