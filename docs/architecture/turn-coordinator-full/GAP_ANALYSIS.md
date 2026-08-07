# Gap Analysis

**עדכון-סטטוס (07/08/2026):** שורת TC6 למטה קיבלה **interim patch תחום-היקף**
(BUG-162, `app.py::_queue_approval_detailed_impl()`'s generic ok=False branch
— `reply_owner`/`lifecycle_result` היו חסרים בפועל בענף אחד מתוך 11) — **לא**
את מימוש TC6 עצמו. ה-patch תוקן ונבדק (32/32,
`test_bug162_gateway_reply_owner_on_generic_block.py`), אך נשאר בתוך המנגנון
הישן (`build_approval_lifecycle_result()`) — לא עבר cutover ל-WS2's projection
methods (`ActionGateway.approval_status()`/`execution_status()`, שכבר קיימות
בקוד אך תוצאתן נזרקת בפועל, ראו `docs/architecture/action-gateway/BUG-162_
SINGLE_SPEAKER_CLOSURE_AUDIT_20260807.md`). TC6 עצמו **נשאר `NEXT_IMPLEMENTATION`**
— ה-patch לא סוגר את השורה, רק מקטין את הנזק-בפועל של הפער עד ש-TC6 ירוץ.
כשקוד TC6 עצמו יתחיל, השינוי הנקודתי הזה ב-`app.py` צריך להיסקר/להתאחד לתוכו,
לא להישאר side-patch נפרד לצמיתות.

| Class | Gap | Primary workstream | Current source | Target | Risk | Internal milestone | Evidence |
|---|---|---|---|---|---|---|---|
| BLOCKER | callback fallback can dispatch directly when AC lookup fails | Workstream 2 | app.py, callback path | fail closed through Gateway | unauthorized/duplicate write | TC7 | direct verification + callback tests |
| BLOCKER | four pending/approval stores coexist | Workstream 2 | app, EventBus, AC, TMA | AC lifecycle + projections only | divergent state/replay | TC8 | bundle + current-state audit |
| BLOCKER | no durable turn ownership/concurrency record | Workstream 2 | TurnEnvelope is snapshot only | durable identity-scoped turn state | callback/text race | TC8 | turn-envelope docs/code |
| BEFORE_FLAG_ON | deterministic intents still reach Agent/tool paths | Workstream 1 | router + app | coordinator admission gate | non-deterministic mutation | TC1/TC4 | router and intent tests |
| BEFORE_FLAG_ON | direct dispatcher does not universally enforce approval metadata | Workstream 2 | dispatcher/registry | execution proof gate | approval bypass | TC7 | phase-4C audit |
| NEXT_IMPLEMENTATION | canonical builders absent | Workstream 1 | scattered handlers | named typed outputs | positional payload/canonicalization drift | TC2/TC4 | router/current code |
| NEXT_IMPLEMENTATION | resolver behavior differs by entity/surface | Workstream 1 | adapters, TMA, Agent | bounded identity-scoped map | wrong entity/update | TC3/TC5 | resolver sources |
| NEXT_IMPLEMENTATION (interim patch applied 07/08/2026, gap not closed — see note above) | reply ownership is conditional and renderer paths drift | Workstream 2 | app/Gateway/F52 | explicit reply policy + one speaker | duplicate/conflicting text | TC6 | ownership research; BUG-162 interim patch: `BUG-162_SINGLE_SPEAKER_CLOSURE_AUDIT_20260807.md` |
| FOLLOW_UP | evidence shadow observes Gateway-owned turns but is not finalizer | Workstream 2 | app/RP5 | finalizer at execution boundary | false completion claims | TC7 | RP5 node/direct check |
| FOLLOW_UP | surface-specific rendering is not one public composer | Workstream 3 | Gateway/F52/formatters | MessageContract at all surfaces | UX inconsistency/leaks | TC9 | F52 docs |
| FOLLOW_UP | batch/session preview has separate lifecycle semantics | Workstream 1 | lead capture/session | explicit resolver or observation-only | false approval affordance | TC5 | BUG audit |
| LEGACY_ONLY | legacy EventBus IDs remain presentation pointers | Workstream 2 | EventBus/callback | migrate to exact AC IDs | stale callback | TC8 | approval audit |
| LIBRARIAN_COVERAGE_GAP | catalog stale metadata and adjacent BUG-140 discovery | Deferred follow-up | BUG_AUDIT_LOG.md, stale nodes | separate catalog review | missed context | separate review PR | bundle expansion |

## Coverage rule

Every gap has exactly one primary workstream. A workstream may consult another
stream's contract, but it may not implement that stream's authority. The
catalog gap is deliberately deferred and is not owned by any implementation
workstream.
