# Bundle Sufficiency Matrix

| Planning question | Bundle | Source/node | Confidence | Direct verification |
|---|---|---|---|---|
| Live intents | Bundle + direct | `layer.turn_coordinator`, router code | High | Yes |
| Current turn holders | Bundle + direct | turn-coordinator and approvals nodes | High | Yes |
| Deterministic paths | Bundle + direct | router, PA-01, tests | High | Yes |
| Agent admission | Bundle + direct | router/risk notes, `app.py` | Medium | Yes |
| Approval lifecycle owner | Bundle only for authority; direct for paths | `decision.actioncontracts_authority` | High | Yes |
| Evidence authority | Bundle + direct | RP5 and ActionContract decisions | High | Yes |
| MessageContract flow | Bundle + direct | `ux_f52` node and F52 docs | Medium | Targeted |
| Existing gaps | Bundle + direct | BUG audit and phase-4C risk report | High | Yes |
| Canonical authority files | Bundle only | canonical-doc manifest | High | No broad reread |
| Production flag state | Not supported | Librarian safety rule | High | Requires deployment evidence |
| Complete background mutation inventory | Not supported | out of bounded profile | Low | Separate inventory required |
| Final consumption conclusion | Not supported | contract requires receipts | High | Blocked |

The bundle was sufficient to plan ownership and sequencing. It was not a
substitute for source verification or production evidence.
