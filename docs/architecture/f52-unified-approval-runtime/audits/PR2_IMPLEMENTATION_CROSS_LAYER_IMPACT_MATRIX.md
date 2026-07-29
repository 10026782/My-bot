# PR2 implementation — Cross-Layer Impact Matrix

Status: implementation evidence for `codex/pr2-deterministic-approval-cost-cuts`.
Base: `origin/main` `12e2a4530da63160fb98c9e9fbf33cb3f08813a7`.

## Layer 1 — Core Reasoning / BUG-104

touched: not touched
input impact: none.
output impact: none.
authority impact: none.
shared identifiers: none.
invariants: Core Reasoning remains read-only and has no dispatcher use.
failure semantics: not applicable.
observability: none added.
cross-layer tests: no BUG-104 suite is exercised by this narrow approval patch.

## Layer 2 — TurnCoordinator

touched: indirectly.
input impact: only anchored approval-lifecycle text is short-circuited before
the de-facto router/capture owners; all other text falls through unchanged.
output impact: no new route decision or handler signal.
authority impact: none; the resolver delegates lifecycle decisions to Layer 4.
shared identifiers: no new TurnCoordinator identifier.
invariants: business create/update/delete decisions are never made by capture.
failure semantics: non-matching input is fail-safe fall-through; it is never
auto-approved.
observability: request-local `deterministic_path_used`.
cross-layer tests: `test_bug141_pending_query_dispatch_order.py` remains green.

## Layer 3 — F52 / Phase 4C Action & Tool Contract

touched: not touched directly.
input impact: none.
output impact: none.
authority impact: no policy or tool mapping changes.
shared identifiers: none.
invariants: no dispatcher/tool-registry/schema import was added.
failure semantics: not applicable.
observability: metrics are counters only, never evidence or policy.
cross-layer tests: no C53a suite is changed.

## Layer 4 — Durable Atomic Approval

touched: directly.
input impact: one supplied live-contract snapshot is reused by confirmation,
cancellation, pending rendering, and `יצרת?`; terminal replay is restricted
to a 24-hour terminal-only lookup.
output impact: existing `ApprovalLifecycleResult` text and existing lifecycle
mutation entry points are reused.
authority impact: unchanged — ActionContracts remains the sole lifecycle
authority; metrics do not gate decisions.
shared identifiers: new flag `FEATURE_DETERMINISTIC_APPROVAL_COST_CUTS`; no
ActionContract schema/status literal is added.
invariants: no Session bookmark is read on the PR2 confirmation path; multiple
live contracts list/disambiguate without mutation only while PR2 is enabled.
failure semantics: ambiguous/multiple live requests fail closed; flag-off and
PR1-off make the PR2 resolver inert, preserving the legacy route.
observability: request-local agent/read/final/deterministic counters with
content-free per-turn log records.
cross-layer tests: `test_pr2_deterministic_approval_cost_cuts.py`,
`test_pending_contract_read_amplification.py`,
`test_pr1_single_speaker_approval_ux.py`, and
`test_bug_approval_callback_hardening.py` are green.

## Proof of non-impact

`git diff --name-only origin/main` produced no entries for
`core/leads_reasoning_projection.py`, `core/adapters/leads_adapter.py`,
`core/router/router.py`, `core/lead_candidate_handler.py`, `tool_registry.py`,
`tools/dispatcher.py`, or `tools/schemas.py`; there are no new imports from
those modules. The post-change regression runs listed above, plus
`test_session_snapshot.py`, passed. For before/after read-amplification proof,
`python3 test_pending_contract_read_amplification.py` passed on both an
`origin/main` archive and this branch (6/6 in each run). This implementation
does not claim a new runtime behavior for Layers 1 or 3.

## Cross-Cutting Guard — RP5 Evidence Finalization

applies: yes. PR2 adds action-status-facing metrics and reuses existing
lifecycle wording. It does not introduce a grounding/evidence mechanism or
call `core/turn_evidence.py`; counters are observability-only and no status
claim is derived from them.
