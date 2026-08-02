# Agent Admission Policy

| Condition | Agent allowed | Deterministic pre-check | Fallback | Forbidden |
|---|---:|---|---|---|
| Material semantic ambiguity | Yes | classify intent and risk | clarify | mutation by guess |
| Multi-step reasoning | Yes | identify tools/resources and approval boundary | explain limitation | hidden execution |
| Unstructured business question | Yes | read-only scope check | answer limitation | write without builder |
| Complex comparison/synthesis | Yes | gather bounded sources | partial answer | claim unsupported evidence |
| Missing domain interpretation | Yes | resolver returns unresolved semantics | clarify | fabricate entity/state |
| Known status/approval query | No | exact lifecycle/status resolver | deterministic response | Agent prose as state |
| Bare confirmation/cancellation | No | exact pending-contract lookup | disambiguate/terminal response | Agent approval |
| Unambiguous create_task | No | required fields + policy | clarify missing field | Agent tool choice |
| Known entity update after one match | No | identity-scoped resolver | ask when 0/multiple | broad scan |
| Callback lifecycle | No | callback signature, role, contract/version | fail closed | direct dispatcher fallback |
| Terminal replay | No | terminal state lookup | replay-safe response | re-execution |

Agent output is advisory. It cannot authorize, prove execution, close an
ActionContract, or become the final speaker on a Gateway-owned turn.
