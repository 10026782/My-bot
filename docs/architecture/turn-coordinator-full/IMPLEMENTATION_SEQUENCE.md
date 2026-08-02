# Implementation Sequence

| PR | Scope | Likely files/tests | Dependency/flag | Entry/exit | Rollback/not included | Librarian gate |
|---|---|---|---|---|---|---|
| TC1 | intent ownership registry and typed decision | router, new planning-owned registry, router tests | off/shadow | inventory validated; no behavior change | delete registry; no handlers | `turn_coordinator_routing`, receipts |
| TC2 | deterministic task builders/handlers | task adapters, task tests | off then flag | structured create/update/complete tests | flag off; no lead work | same + `tool_execution` |
| TC3 | task resolver and known-task updates | resolver + task paths | off | 0/1/multi tests | revert resolver gate | same |
| TC4 | deterministic lead builders/handlers | lead candidate/adapters/TMA tests | `FEATURE_AUTO_CAPTURE` unchanged | policy matrix passes | flag off; no approval authority move | same + `core_reasoning_change` |
| TC5 | bounded entity resolver framework | task/lead/contact/deal/AC/session/callback resolvers | off | bounded/identity/durable tests | disable coordinator path | same |
| TC6 | explicit reply ownership | app/Gateway/formatter tests | single-speaker flag unchanged | one speaker per turn | flag off | same + `approval_ux` |
| TC7 | evidence finalizer and dispatcher proof | dispatcher/Gateway/RP5 tests | evidence flag remains off until gates | tool/result/claim matrix passes | flag off | same + `tool_execution` |
| TC8 | durable turn state and concurrency | turn state repository, callback/text races | rollout gated | restart/multi-instance tests | stop writes, preserve old path | same + approvals |
| TC9 | MessageContract across surfaces | Telegram/WhatsApp/TMA formatters/tests | surface flags unchanged | no internal IDs/tools, one public payload | per-surface rollback | same + `approval_ux` |
| TC10 | verification harness and rollout gates | focused integration tests, static checks/docs | no production flag change | shadow evidence and rollback drill | keep shadow/off | `cross_layer_architecture` plus primary |

Every implementation PR must begin with a fresh bundle, record profile,
base SHA, mandatory source receipts, direct expansions, and verifier result.
No PR may claim `CONCLUSION_PROCEED` without a real verifier result.
