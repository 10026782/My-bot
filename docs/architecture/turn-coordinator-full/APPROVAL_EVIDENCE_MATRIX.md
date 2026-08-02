# Approval, Evidence, and Reply Ownership

| Intent | Approval | Approval owner | ActionContract | Execution evidence | Completion evidence | Replay/duplicate | Reply owner | Forbidden speakers |
|---|---|---|---|---|---|---|---|---|
| read/status/search | No | none | no | source read result | n/a | idempotent read | deterministic handler | Agent claim of mutation |
| task/lead mutation | policy-dependent | ActionGateway | required when approval applies | provider result + verified write | final state readback | contract/claim at-most-once | Gateway for approval turn | Agent |
| confirmation/cancellation | yes/no lifecycle action | ActionGateway | existing contract only | lifecycle result | terminal state | terminal replay safe | Gateway | Agent |
| callback approve/reject | yes/no lifecycle action | ActionGateway | exact contract | claim + provider/evidence | lifecycle finalizer | duplicate/stale fail closed | Gateway | callback fallback |
| pending/approval status | No new approval | ActionGateway | read canonical AC | lifecycle snapshot | not completed | no state mutation | Gateway | Agent |
| execution status | No | ActionGateway | reference existing contract | execution result/unknown | never infer success | repeat read safe | Gateway | Agent |

Invariants: pending approval is not completed; tool call is not verified write;
Agent statement is not evidence; approval success is not execution success; one
final responder per turn. ActionContracts remain lifecycle authority, and
MessageContract/display payload remains the user-facing contract once the
surface-wide migration is approved.
