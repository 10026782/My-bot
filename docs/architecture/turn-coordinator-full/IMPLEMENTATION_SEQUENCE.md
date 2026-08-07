# Implementation Sequence

## Current execution note — 2026-08-02

WS1 foundation work is merged through PR #536. The narrow runtime integration
PR #545 was merged as `46db9af` from head `1d117ab`; follow-up PR #546 is also
merged. Staging and rollout gates remain mandatory before claiming readiness
for the next WS2/WS3 step. The merge order remains WS1 → WS2 → WS3.

**TC6 status update (07/08/2026):** TC6 ("explicit reply ownership") itself
has **not** been implemented — still `NEXT_IMPLEMENTATION` per
`GAP_ANALYSIS.md`. `ActionGateway.approval_status()`/`execution_status()`
(WS2's own projection methods) exist in code but their return value is
discarded at both call sites (`core/action_gateway.py:3459,3486`) — the
legacy `build_approval_lifecycle_result()` path still produces the actual
user-facing text everywhere, confirmed by direct code read, not just prose.
An **interim, narrowly-scoped tactical patch** was applied directly to that
legacy path (`app.py::_queue_approval_detailed_impl()`'s generic ok=False
branch, BUG-162, 07/08/2026) to close one specific missing-`reply_owner`
defect discovered in production staging — see
`docs/architecture/action-gateway/BUG-162_SINGLE_SPEAKER_CLOSURE_AUDIT_20260807.md`.
This patch does **not** constitute TC6 and does not reduce TC6's scope when
it is eventually implemented — TC6 must still perform the full cutover to
WS2's `ActionLifecycleResult` projection as an explicit reply-ownership
authority, and must review/absorb or explicitly supersede this interim
patch at that time, not leave it as a permanent parallel mechanism. The
patch was also applied as a direct `app.py` edit outside the WS2
agent-prompt/Librarian-bundle/integrator-review workflow this plan defines
(`app.py` is "Integrator only" per `PARALLEL_IMPLEMENTATION_WORKSTREAMS.md`'s
file ownership map) — flagged here so TC6's actual implementer is aware of
it and does not discover it as an unexplained drift later.

This is an internal milestone view of exactly three implementation
workstreams—not ten independent tracks: TC1–TC4 belong to Workstream 1,
TC5–TC8 to Workstream 2, and TC9–TC10 to Workstream 3. Development may run in
parallel after contract freeze; merge order is WS1 → WS2 → WS3.

| PR | Scope | Depends on | Likely files/tests | Dependency/flag | Entry/exit | Rollback/not included | Librarian gate |
|---|---|---|---|---|---|---|---|
| TC1 | intent ownership registry and typed decision | — | router, new planning-owned registry, router tests | off/shadow | inventory validated; no behavior change | delete registry; no handlers | `turn_coordinator_routing`, receipts |
| TC2 | deterministic task builders/handlers | TC1 | task adapters, task tests | off then flag | structured create/update/complete tests | flag off; no lead work | same + `tool_execution` |
| TC3 | task resolver and known-task updates | TC1, TC2 | resolver + task paths | off | 0/1/multi tests | revert resolver gate | same |
| TC5 | bounded entity resolver framework | TC3 | task/lead/contact/deal/AC/session/callback resolvers | off | bounded/identity/durable tests | disable coordinator path | same |
| TC4 | deterministic lead builders/handlers | TC1, TC5 | lead candidate/adapters/TMA tests | `FEATURE_AUTO_CAPTURE` unchanged | policy matrix passes | flag off; no approval authority move | same + `core_reasoning_change` |
| TC6 | explicit reply ownership | TC3, TC4 | app/Gateway/formatter tests | single-speaker flag unchanged | one speaker per turn | flag off | same + `approval_ux` |
| TC7 | evidence finalizer and dispatcher proof | TC6 | dispatcher/Gateway/RP5 tests | evidence flag remains off until gates | tool/result/claim matrix passes | flag off | same + `tool_execution` |
| TC8 | durable turn state and concurrency | TC5, TC6 | turn state repository, callback/text races | rollout gated | restart/multi-instance tests | stop writes, preserve old path | same + approvals |
| TC9 | MessageContract across surfaces | TC7, TC8 | Telegram/WhatsApp/TMA formatters/tests | surface flags unchanged | no internal IDs/tools, one public payload | per-surface rollback | same + `approval_ux` |
| TC10 | verification harness and rollout gates | TC9 | focused integration tests, static checks/docs | no production flag change | shadow evidence and rollback drill | keep shadow/off | `cross_layer_architecture` plus primary |

Every implementation PR must begin with a fresh bundle, record profile,
base SHA, mandatory source receipts, direct expansions, and verifier result.
No PR may claim `CONCLUSION_PROCEED` without a real verifier result.

The explicit dependency column is part of the plan. The prior table had an
ordered list but no machine-reviewable dependency declaration; this was a
planning defect because acyclicness could not be checked from the artifact.
The corrected graph is acyclic and topologically ordered.
