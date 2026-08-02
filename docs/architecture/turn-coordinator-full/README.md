# Turn Coordinator — Full Planning

Status: planning baseline plus implementation review. Planning base:
`fb4ab4af57d8e5986a06219638e1145af019cf6e`.

## Current implementation status — 2026-08-02

- WS1 foundation contracts are merged (`PR #536`).
- PR #545 was merged via `46db9af` (source head `1d117ab`).
- Follow-up PR #546 is also merged into `main`.
- The PR diff is limited to `app.py`,
  `core/turn_coordinator_runtime.py`, `tools/airtable_tools.py`, and its
  integration test file.
- Local verification is green: 252 focused tests, all 11 standalone suites,
  compileall, and `git diff --check`.
- The implementation PR is closed; this branch contains documentation-only
  status alignment. Staging/production verification remains a separate gate.
- The next controlled step is the ordered WS2/WS3 review and staging plan. Do
  not infer production readiness from the merge alone.

This plan defines a future ownership boundary for turns. It does not create a
`TurnCoordinator`, change routing, enable flags, alter handlers, or change
approval, queue, reply, or evidence authority.

## Decision

Introduce ownership in small PRs, starting with a registry and verification
harness. The coordinator chooses the owner of a turn; it must not execute
tools, own ActionContract lifecycle, manufacture evidence, or become a second
reply composer.

## Current state in one page

- `route_request()` returns a typed `RouteDecision`, but no `TurnCoordinator`
  exists on main.
- The live flow is distributed across `app.py`, router modules,
  `lead_candidate_handler.py`, ActionGateway, EventBus, TMA, session state, and
  the Agent loop.
- ActionContracts are lifecycle authority, but four approval/pending
  mechanisms remain independently reachable.
- `FEATURE_SINGLE_SPEAKER_APPROVAL_UX` gives Gateway ownership only for the
  specific approval-queued path when enabled; it is not a general ownership
  protocol.
- `TurnEnvelope` is observation-only and intentionally non-durable.
- Agent admission is still broader than the target policy: unknown text is a
  safety-net Agent path, while several known intents have no deterministic
  builder yet.

## Gates

| Gate | Result |
|---|---|
| Librarian validation | PASS: 16 nodes, 24 edges, 7 profiles |
| Profile selection | `turn_coordinator_routing`, unique suggestion; secondary coverage: `approval_ux`, `core_reasoning_change`, `tool_execution` |
| Bundle build | PASS: two byte-identical 89,024-byte current-checkout bundles; SHA-256 `c6f58c5265f7ee516e8a7cc7c43dcaf2e7f53d2ff1ccec6907e3124f1e08a1c7` |
| Authority coverage | 100% |
| Workflow gate | `REVIEW_REQUIRED`; 4 stale nodes, no STOP reason |
| Consumption verifier | `CONCLUSION_PROCEED` after 75 direct receipts; current-checkout provenance warning is documented |
| Planning verdict | `PLANNING_READY` |

## Reading boundary

The bundle supplied the authority map, current ownership claims, known gaps,
and canonical source list. Direct verification was then limited to router and
turn-envelope code, Agent/callback precedence, ActionGateway and repository
lifecycle, current Turn Coordinator documents, authority contracts, and the
named tests/gap records. Catalog changes and runtime changes are out of scope.

See the companion matrices for the canonical inventory, target routing,
builder/resolver designs, gaps, and implementation sequence.

The parallel execution pack, three agent prompts, file ownership map, frozen
contracts, integration seams, and merge/rollback plan are in
`PARALLEL_IMPLEMENTATION_WORKSTREAMS.md` and
`INTEGRATION_AND_MERGE_PLAN.md`. Future agents must use those documents before
implementation. The planning artifacts remain authoritative after PR #545's
merge; they do not authorize production activation without separate staging
and rollout gates.
