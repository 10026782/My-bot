# Librarian Consumption Report

## Run identity

- Planning base commit: `fb4ab4af57d8e5986a06219638e1145af019cf6e`
- Bundle generated commit: `fd1623e4f28da73326b48c500b6da741ffd825d2`
- Branch: `codex/turn-coordinator-full-planning`
- Query: complete current/target Turn Coordinator plan covering ownership,
  deterministic routing, Agent admission, builders, resolvers,
  approval/evidence policy, reply ownership, and sequencing.
- Primary profile: `turn_coordinator_routing`
- Secondary coverage considered: `approval_ux`, `core_reasoning_change`,
  `tool_execution`; no secondary bundle was needed because the primary profile
  included their authority dependencies and conditional evidence.
- Manual override: no. The suggestion was unique (score 4).

## Gate results

- Validation: PASS — 16 nodes, 24 edges, 7 profiles.
- Catalog status: valid.
- Provenance: generated from the current planning checkout; `on_main_history=false` and `at_origin_main_tip=false` because the planning commit is documentation-only and is not on main.
- Bundle builds: PASS, byte-identical; same SHA-256, source ordering, node
  ordering, mandatory checklist, and token estimate.
- Bundle size: 89,024 bytes; SHA-256 `c6f58c5265f7ee516e8a7cc7c43dcaf2e7f53d2ff1ccec6907e3124f1e08a1c7`; estimate 18,268/19,000 approximate tokens.
- Mandatory source count: 75 checklist items.
- Mandatory authority coverage: 100%.
- Workflow status: `REVIEW_REQUIRED`; stale nodes are approvals,
  turn_coordinator, rp5, and ux_f52. No authority STOP was emitted.

## Consumption contract

`verify-consumption` was invoked against the exact profile, query, branch, and
current bundle commit. It returns the canonical tool result `CONSUMPTION: COMPLETE`
after 75 direct review receipts (the implementation does not emit the literal
`CONCLUSION_PROCEED`). The bundle itself carries the expected warning that this planning
commit is not on main; no production claim is made.

## Bundle sufficiency

Answered from bundle: current authority boundaries, live layer ownership,
router/Agent/Gateway relationships, known approval queues, canonical docs,
known defects, feature-flag caveats, and the required verification invariants.

Answered with direct verification: exact current router rules, `RouteDecision`
shape, `TurnEnvelope` observation-only scope, `run_agent()` precedence and
callback branches, ActionGateway lifecycle entry points, repository state
authority, and the current tests/gap records used in the matrices.

Not established: a production deployment state for future flags, a complete
runtime inventory of every non-Agent background mutation, and an approved
pre-merge consumption ledger with independent reviewer receipts.

## Direct sources opened

`core/router/router.py`, `core/router/route_decision.py`,
`core/router/intent_router.py`, `core/router/risk_router.py`,
`core/turn_envelope.py`, `app.py`, `core/action_gateway.py`,
`core/action_contract_repository.py`, `core/action_resolution_projection.py`,
`core/lead_candidate_handler.py`, `event_bus.py`, `feature_flags.py`,
`tma_api.py`, the Turn Coordinator architecture documents, the cross-layer
authority contract, the current-state approval audit, `BUG_AUDIT_LOG.md`, and
the named routing/approval/evidence tests.

## Pilot verdict

`LIBRARIAN_PILOT_PASS` — the Librarian reduced the search surface, exposed the
stale-node and adjacent BUG-140 coverage issue, and the consumption contract
was completed with 75 direct receipts. Catalog gaps are recorded separately;
none are changed here.
