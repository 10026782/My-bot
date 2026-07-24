# TurnCoordinator + TurnEnvelope

## Purpose

Architectural proposal for a `TurnCoordinator` that owns per-turn context
(`TurnEnvelope`) and reply ownership, so the agent is always aware of pending
state and capability boundaries from one unified source instead of drifting
mechanisms.

## Relationship to F52

This does not replace F52 (`../f52-unified-approval-runtime/`). F52's audit
maps (tool map, approval flow map, state flow map, bypass map, contract
coverage map) are the input this proposal's Phase 0 consumes and extends —
not re-derives. Phase 0 adds turn-ownership dimensions on top of the existing
F52/Phase 4C audits (reply ownership, pending queue source, outbound sender,
agent dependency, deterministic availability, message kind) rather than
starting a new full-system audit.

## Documents

- `TURN_COORDINATOR_PROPOSAL_V2.md` — the current proposal (v2). Status:
  architectural proposal, ready for Phase 0 implementation planning, not yet
  ready for implementation until Phase 0 turns it into an exact list of call
  sites and state sources.
- `CASE_C_CLARIFICATION_CONTINUITY.md` — verified failure case: a multi-item
  request needing clarification for one item can lose queue ownership (C1)
  or produce an unevidenced "pending approval" claim (C2). Both confirmed
  against current `main` with file:line citations. Required invariants 1-4
  are Phase 1+/Phase 5 (behavioral); invariant 5 (Phase 0 must log enough to
  tell C1 from C2 apart) is implemented in `core/turn_envelope.py`.
- `REPLY_OWNERSHIP_AND_APPROVAL_AUTHORITY_RESEARCH.md` — research only, no
  implementation: Agent Ownership Hijack (who can select handler/create
  ActionContract/queue approval/cancel/complete/compose the reply, per
  channel, and where two layers could both become reply owner) and Case C /
  "Phantom Approval Prompt" (the single-turn, no-clarification-needed
  fabricated-approval scenario — a sharper, standalone case of the same
  underlying gap `CASE_C_CLARIFICATION_CONTINUITY.md`'s C2 already names).
  **Naming collision, unresolved:** this doc's Case C and the existing
  `CASE_C_CLARIFICATION_CONTINUITY.md`'s Case C are not the same scenario —
  flagged in both documents, not resolved by either; owner decision needed
  on final naming.
- `PERFORMANCE_CALL_VOLUME_AUDIT.md` — read-only audit, no runtime code
  changed, not a Planning Gate: external-call-volume (Anthropic/Airtable/
  Telegram) map of the Telegram create-task→approve→execute lifecycle. Its
  headline finding is TurnCoordinator-relevant: a plain "מאשר" approval can
  resolve via either the legacy `_pending_approvals` dict (which recursively
  re-invokes `run_agent()`, costing 2 extra Anthropic calls) or the
  `ActionGateway` path (0 Anthropic calls), depending on which store queued
  the action — the same class of "multiple non-unified pending-state
  stores" gap `PHASE_2_SHADOW_PLANNING_GATE.md` §1.5 already documents
  structurally, now with a cost dimension attached. Ends with an explicit
  requirement for whichever phase is implemented next (see Status below).

## Status

Phase 0: implemented and pushed (`core/turn_envelope.py`,
`app._build_and_log_turn_envelope()`, `OwnershipSignal`), covering
`run_agent()`, Telegram callbacks, TMA's approval entry point, and the two
scheduler proposal functions — see
`../f52-unified-approval-runtime/audits/phase-4c/TURN_OWNERSHIP_EXTENSION.md`
for the full call-site touch list and what remains uninstrumented.
`REPLY_OWNERSHIP_AND_APPROVAL_AUTHORITY_RESEARCH.md` found real gaps
`OwnershipSignal` does not cover (cancellation/completion fabrication, a
cross-request concurrency race) — see that doc's §1.4. Phase 1 (structural
enforcement) not started; no code changes have been made based on that
research yet — it is research only, pending owner decisions listed in its
Summary section.

**Added requirement (this round):** `PERFORMANCE_CALL_VOLUME_AUDIT.md`'s
closing section requires that whichever phase is implemented next (Phase 2
Shadow runtime completion, or Phase 3, per owner decision on sequencing)
also close the Flow 4 recursion gap it identifies, record which
pending-state store resolved an approval-reply turn (and that turn's
Anthropic-call count) as a Shadow-decision observability field, and lazily
load Business Memory / the turn-start session snapshot behind the handler
decision. This is a requirement to carry forward, not an implementation —
no code has been written for it yet.
