# Current Intent Inventory

The inventory includes requested intents only when the router, handler, or a
test provides evidence. “Current handler” means the current de-facto path, not
an intended future owner.

| Intent | Trigger/examples | Classifier | Current handler/reply owner | Tool path | Approval/evidence | Agent now | Deterministic candidate | Evidence/gap |
|---|---|---|---|---|---|---|---|---|
| create_task | צור/פתח משימה; structured `צור משימה:` | `intent_router`, `router` | Agent or tool; Gateway for approval | task/Airtable adapters | mutation approval; write evidence | Sometimes | Yes for structured builder | `router.py`, create-task test |
| update_task | עדכן/שנה משימה | `intent_router` | Agent/tool path | task adapter | approval + write evidence | Yes | After resolver | router; no canonical builder |
| complete_task | סגור/סיים משימה | `intent_router` | Agent/tool path | task adapter | approval + completion evidence | Yes | After resolver | router; no canonical builder |
| search_task | list/show tasks | list-task rules | Agent/read tool | task search | no mutation approval; source result | Yes | Resolver then deterministic | intent rules |
| create_lead | הוסף/צור ליד | `intent_router`, lead capture | lead candidate handler/Agent | Airtable/Gateway | policy-dependent approval; write evidence | Yes | After canonical builder | `lead_candidate_handler.py` |
| update_lead | עדכן ליד | `intent_router` | Agent/Gateway/TMA variants | lead adapter | approval + write evidence | Yes | After resolver | lead adapter/TMA |
| search_lead | חפש/מצא ליד | `FIND_LEAD` | Agent/read path | CRM resolver | read evidence | Yes | Resolver then deterministic | intent rules |
| approval_status | status/approval words and pending path | Gateway confirmation/status logic | ActionGateway projection | ActionContract read | no write; lifecycle state | No | Now, bounded | action gateway tests |
| execution_status | execution/result query | Gateway/result paths | Gateway/provider projection | execution repository/provider | execution evidence only | Sometimes | Now after resolver | ActionGateway |
| pending_queue_query | pending/what awaits | pending query path | Gateway/EventBus/app/TMA projections | multiple stores | no completion claim | Sometimes | After queue unification | four queue sources |
| confirmation | כן/yes/approve | confirmation router | ActionGateway; legacy EventBus fallback | approve path | approval authority AC | No | Now, canonicalized | callback/approval tests |
| cancellation | לא/no/cancel | cancellation router | ActionGateway reject plus legacy branches | reject path | terminal lifecycle evidence | No | Now | replay tests |
| terminal_replay | repeat on terminal contract | lifecycle/replay guard | Gateway/callback/UI | no new execution | terminal state | No | Now | replay policy tests |
| callback_approve | approve callback | app callback handler | app + Gateway/fallback | callback dispatch | role + AC claim | No | Resolver then Gateway | callback path |
| callback_reject | reject callback | app callback handler | app + Gateway/legacy | reject path | AC terminal state | No | Resolver then Gateway | callback path |
| stale_callback | old/missing callback | callback resolver | app/EventBus/Gateway branches | none or fail-closed | no execution evidence | No | Resolver-only | stale callback tests |
| expired_action | TTL elapsed | stores/Gateway | varies by queue | no execution | expired lifecycle | No | Resolver-only | TTLs in approval node |
| duplicate_callback | same callback twice | replay/claim logic | varies; Gateway is target | at-most-once claim | execution claim/evidence | No | Resolver-only | concurrency tests |

Known router catalog also contains calendar, contacts, communications,
knowledge, reporting, research, system, and engineering intents. They are not
expanded here because this plan’s requested builder/resolver scope is tasks,
leads, approval, execution, queues, and lifecycle callbacks.
