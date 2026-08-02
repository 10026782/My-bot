# Implementation Sequence

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
