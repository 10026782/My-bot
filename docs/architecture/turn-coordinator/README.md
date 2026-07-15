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

## Status

Phase 0: implemented and pushed (`core/turn_envelope.py`,
`app._build_and_log_turn_envelope()`), covering `run_agent()` only — see
`../f52-unified-approval-runtime/audits/phase-4c/TURN_OWNERSHIP_EXTENSION.md`
for the full call-site touch list, most of which is not yet instrumented.
Phase 1 onward not started.
