# Agent Prompt — Workstream 2: Approval, Lifecycle, Evidence and Concurrency

## Current execution note — 2026-08-02

WS2 remains downstream of the merged PR #545 integration (`46db9af`, source
head `1d117ab`). Do not begin authority-changing WS2 rollout until its own
review, CI, and staging gates pass.

## Base and Librarian gate

Branch from the canonical current `origin/main` SHA. Run the full Librarian
suggestion command, select `turn_coordinator_routing`, and add secondary
coverage `approval_ux` and `tool_execution` (plus `rp5_evidence_mismatch` for
Evidence Finalizer work). Build/read the bundle and complete direct receipts.

## Read exactly

`core/action_gateway.py`, `core/action_contract_repository.py`,
`core/action_gateway_atomic_executor.py`, `core/action_resolution_projection.py`,
`core/approval_turn_metrics.py`, `app.py` callback/confirmation sections,
`event_bus.py`, `tma_api.py` approval helpers, `core/turn_envelope.py`,
approval/current-state/cross-layer/F52 authority docs, and all callback,
concurrency, replay, durable-lifecycle, and evidence tests cited by the bundle.

## Scope

Own `approval_status`, `execution_status`, `pending_queue_query`,
`confirmation`, `cancellation`, `terminal_replay`, `callback_approve`,
`callback_reject`, `stale_callback`, `expired_action`, and
`duplicate_callback`. Implement lifecycle resolution, exact contract lookup,
durable turn/concurrency state, callback/text race protection, explicit reply
ownership, Evidence Finalizer enforcement, and verified-completion semantics.

## Forbidden

Do not edit router/builders/resolvers, MessageContract/rendering/surface
adapters, feature flags, catalog, or `app.py` directly. Submit an isolated
integration patch for `app.py`, EventBus, or TMA to the integrator. Never
restore direct dispatcher fallback, infer success from Agent text, or make a
projection an authority.

## Interfaces and tests

Use frozen `CanonicalActionProposal`, `ActionLifecycleResult`, and
`EvidenceResult`. Run lifecycle, callback, stale/expired/replay, concurrency,
atomic-claim, direct-dispatch, and single-speaker tests. Add restart,
multi-instance, callback/text race, one-provider-call, forged-reference,
outcome-unknown, and evidence-precedence tests.

## Acceptance and delivery

ActionContracts remain lifecycle authority; approval success is not execution
success; pending is not completed; one final responder exists; duplicate,
stale, expired, and ambiguous actions fail closed. Commit in TC5–TC8-sized
changes, push a separate branch, and open a Draft PR to `main`. Do not merge.

## Final report

Return base SHA, profiles/bundle hash, receipts, lifecycle states covered,
race/duplicate guarantees, evidence behavior, changed files/functions,
integration patch for `app.py` if any, tests, rollback/flag statement, commit
SHAs, PR URL, and verifier result.
