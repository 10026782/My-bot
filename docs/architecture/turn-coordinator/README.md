# TurnCoordinator + TurnEnvelope

## Current implementation status — 2026-08-09 (supersedes the TC6/flag claims in the 07/08/2026 note below)

**TC6 is merged and production-verified as of today.** WS2's exact-contract
reply-ownership projection (`reply_ownership_for_contract()` in
`core/action_gateway.py`, PR #566, merge `684d299`) and the `app.py`
integrator cutover (PR #569, merge `d0a8620`) both landed on `origin/main`
09/08/2026. This replaces the 07/08/2026 "TC6 remains `NEXT_IMPLEMENTATION`"
claim below and the BUG-162 note's framing — TC6 itself, not just the BUG-162
interim patch, is now live.

`FEATURE_SINGLE_SPEAKER_APPROVAL_UX`: the code fallback/default remains
`false` (`feature_flags.py`), and that does not change with PR #569 — this
PR does not touch the environment variable itself. But the **active deployed
production runtime has this flag set to `true`**, confirmed via a read-only
Render dashboard environment-variable check and a live application-log +
Telegram transcript check performed by the owner on 09/08/2026 against the
deployed commit (`origin/main` HEAD `7dbddddbe84bbdffd813704094a7d583d948ea96`,
deploy live 03:25). TC6 reply-ownership enforcement is therefore **live**,
not pending activation. Turning the flag OFF remains the verified rollback/
kill-switch path and restores the pre-TC6 legacy producer/tool-loop
behavior (`build_approval_lifecycle_result()`).

This round of verification covered three scenarios end-to-end (fresh
create → pending; status query for the same pending contract; a second
create blocked by BUG-122's pending gate) for a single ActionContract
(`90671635-7dd9-42c7-a467-cc928b18a2a4`) and confirmed the Gateway was the
sole reply owner with the Agent suppressed in each. It did **not** cover:
the Telegram callback-button (approve/reject) path, RP5's classification of
these turns, or replay/stale-callback behavior — those remain open per
`../turn-coordinator-full/GAP_ANALYSIS.md` and `ROADMAP.md`'s N17 item 4
checklist, and per this repo's own Rule 15/GOVERNANCE_RULES.md should not be
described as verified until they have their own direct evidence.

## Current implementation status — 2026-08-07 (TC6/flag status above is newer; rest of this note still applies)

The architecture documents remain the authority for the staged Turn
Coordinator plan. WS1 foundation contracts were merged in PR #536. The narrow
runtime integration PR #545, head `1d117ab`, was merged as `46db9af`; follow-up
PR #546 is also merged. WS1 is live and unflagged: `app.py`'s `run_agent()`
calls `core/turn_coordinator_runtime.py`'s `queue_task_request()` directly for
deterministic create/update/complete-task routing — `core/router/router.py`
itself never imports `ownership_contracts.py`/`task_builders.py`/
`task_resolvers.py`; that module's own docstring previously said "not wired
into the live router," which described a state that had already changed.

"WS2 and WS3 remain downstream" undersold what's actually merged, so it's
being corrected here rather than repeated: both landed as code in PRs
#537–#544, but neither affects user-facing output today. WS2
(`lifecycle_projection.py`/`evidence_projection.py`, via
`ActionGateway.approval_status()`/`execution_status()`) is imported and
called from `core/action_gateway.py`'s deterministic status-query path, but
its return value is discarded at both call sites — the actual reply text
still comes from the older `build_approval_lifecycle_result()` path. WS3
(`lifecycle_message_adapter.py`/`evidence_message_adapter.py`/
`message_surface_harness.py`) is pure and unwired — imported only by its own
tests. The approved rollout order (WS1 → WS2 → WS3, staging and rollout
gates required) is unchanged; this update only corrects what "merged" means
for each workstream today.

## Single source of truth (added 07/08/2026)

Two directories describe the same Turn Coordinator program and, until this
note, did not reference each other: this one, and
`../turn-coordinator-full/` (the WS1/WS2/WS3 parallel-execution plan — task
breakdown TC1–TC10, file ownership map, gap analysis, agent prompts).
**This file (`turn-coordinator/README.md`) is canonical for current merge/
implementation status** — it is actively kept current (as of the date above)
and is the file wired into `docs/context_librarian/layers/turn_coordinator.
json`'s `canonical_docs`. **`turn-coordinator-full/` is canonical for the
WS1/WS2/WS3 task breakdown, DoD items (TC1–TC10), and gap-to-workstream
ownership** — read it for "which item owns this gap," not for "is it merged
yet," since its own status notes drift between updates (see its
`DECISION_LOG.md` entry 15 for the same cross-reference in the other
direction). Neither directory supersedes the other's own domain.

**BUG-162 note (historical — see the 09/08/2026 status above for current
state):** WS2's TC6 ("explicit reply ownership") generalizes PR #471's
conditional mechanism described below. As of 07/08/2026 it was still
`NEXT_IMPLEMENTATION`, and a narrow **interim tactical patch** (not TC6
itself) was applied that day to the legacy `_queue_approval_detailed_impl()`
path — see
`docs/architecture/action-gateway/BUG-162_SINGLE_SPEAKER_CLOSURE_AUDIT_20260807.md`
and `turn-coordinator-full/DECISION_LOG.md` entry 14. TC6 itself merged and
was production-verified 09/08/2026 (PR #566/#569); the real cutover now
supersedes this interim patch, which has not yet had a separate cleanup pass
to confirm it was fully absorbed rather than left as a parallel mechanism.

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

**Erratum (27/07/2026, PR #471, `c64da20`, added by a Context Librarian
metadata audit):** the paragraph above is still accurate for the *formal*
`reply_owner` claim mechanism this research proposes (§1.5 Alternative A) —
that remains unbuilt, and PR #471 was not derived from this research doc.
But PR #471 did independently ship a narrower, code-level conditional
ownership assignment for one specific case: when `FEATURE_SINGLE_SPEAKER_APPROVAL_UX`
is on and a turn queues an approval, `run_agent()` hands the reply to the
Gateway (`reply_owner="gateway"`) and returns without a further Agent turn
(`app.py:3761-3819`). Read "no code changes have been made based on that
research" as scoped to *this specific research document's recommendations*,
not as "reply ownership is entirely unimplemented in any form" — it no
longer is, for the approval-queuing case. The cross-request concurrency race
(§1.3c) this research names is unaffected by PR #471 and remains open.

**Added requirement (this round):** `PERFORMANCE_CALL_VOLUME_AUDIT.md`'s
closing section requires that whichever phase is implemented next (Phase 2
Shadow runtime completion, or Phase 3, per owner decision on sequencing)
also close the Flow 4 recursion gap it identifies, record which
pending-state store resolved an approval-reply turn (and that turn's
Anthropic-call count) as a Shadow-decision observability field, and lazily
load Business Memory / the turn-start session snapshot behind the handler
decision. This is a requirement to carry forward, not an implementation —
no code has been written for it yet.
