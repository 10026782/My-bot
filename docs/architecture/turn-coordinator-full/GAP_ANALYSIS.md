# Gap Analysis

| Class | Gap | Current source | Target | Risk | Recommended PR | Evidence |
|---|---|---|---|---|---|---|
| BLOCKER | callback fallback can dispatch directly when AC lookup fails | `app.py`, callback path | fail closed through Gateway | unauthorized/duplicate write | TC3/TC7 | direct verification + callback tests |
| BLOCKER | four pending/approval stores coexist | app, EventBus, AC, TMA | AC lifecycle + projections only | divergent state/replay | TC8 | bundle + current-state audit |
| BLOCKER | no durable turn ownership/concurrency record | TurnEnvelope is snapshot only | durable identity-scoped turn state | callback/text race | TC8 | turn-envelope docs/code |
| BEFORE_FLAG_ON | deterministic intents still reach Agent/tool paths | router + app | coordinator admission gate | non-deterministic mutation | TC1–TC4 | router and intent tests |
| BEFORE_FLAG_ON | direct dispatcher does not universally enforce approval metadata | dispatcher/registry | execution proof gate | approval bypass | TC7 | phase-4C audit |
| NEXT_IMPLEMENTATION | canonical builders absent | scattered handlers | named typed outputs | positional payload/canonicalization drift | TC2/TC4 | router/current code |
| NEXT_IMPLEMENTATION | resolver behavior differs by entity/surface | adapters, TMA, Agent | bounded identity-scoped map | wrong entity/update | TC3/TC5 | resolver sources |
| NEXT_IMPLEMENTATION | reply ownership is conditional and renderer paths drift | app/Gateway/F52 | explicit reply policy + one speaker | duplicate/conflicting text | TC6/TC9 | ownership research |
| FOLLOW_UP | evidence shadow observes Gateway-owned turns but is not finalizer | app/RP5 | finalizer at execution boundary | false completion claims | TC7 | RP5 node/direct check |
| FOLLOW_UP | surface-specific rendering is not one public composer | Gateway/F52/formatters | MessageContract at all surfaces | UX inconsistency/leaks | TC9 | F52 docs |
| FOLLOW_UP | batch/session preview has separate lifecycle semantics | lead capture/session | explicit resolver or observation-only | false approval affordance | TC5 | BUG audit |
| LEGACY_ONLY | legacy EventBus IDs remain presentation pointers | EventBus/callback | migrate to exact AC IDs | stale callback | TC3/TC8 | approval audit |
| LIBRARIAN_COVERAGE_GAP | catalog stale metadata and adjacent BUG-140 discovery | `BUG_AUDIT_LOG.md`, stale nodes | separate catalog review | missed context | separate PR | bundle expansion |

No runtime or catalog changes are made by this planning PR.
