# Turn Coordinator — Full Planning

Status: planning only. Base: `fb4ab4af57d8e5986a06219638e1145af019cf6e` (`origin/main`).

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
| Bundle build | PASS: two byte-identical 89,024-byte current-checkout bundles; SHA-256 `96d679f94cb3f39c73d3eb782064c14c9fc1f534de81d87693387a8b4718f531` |
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
