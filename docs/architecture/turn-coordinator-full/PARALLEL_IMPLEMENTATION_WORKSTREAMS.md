# Parallel Implementation Workstreams

## Current execution status — 2026-08-02

The frozen WS1 contracts are available after PR #536. The single-integrator
runtime integration in PR #545 (head `1d117ab`) was merged as `46db9af`, and
follow-up PR #546 is also merged. WS2 and WS3 remain downstream workstreams;
they must use the frozen contracts and pass their staging gates. `app.py`
continues to have one integrator owner.

Planning-only execution pack for three independent agents. Base every future
branch on the canonical `origin/main` commit recorded by the fresh Librarian
bundle. Current planning base: `fb4ab4af57d8e5986a06219638e1145af019cf6e`.

The agents may begin scoped design, new-module work, and tests in parallel.
They may not begin authority-changing integration until the contract freeze and
the integration owner approve the seam.

## Workstream 1 — Routing, Builders and Resolvers

| Field | Plan |
|---|---|
| Goal | Make known business intents deterministic where inputs are sufficient; admit Agent only for genuine semantic/reasoning ambiguity. |
| Current verified state | `core/router/router.py::route_request()` returns `RouteDecision`; `core/router/intent_router.py` classifies task/lead/contact/system/report intents; structured create-task is the only narrow deterministic builder gate. No `TurnCoordinator` or canonical proposal type exists. |
| Exact scope | Intent ownership registry; deterministic admission; `CreateTaskBuilder`, `UpdateTaskBuilder`, `CompleteTaskBuilder`, `CreateLeadBuilder`, `UpdateLeadBuilder`; bounded task/lead/contact/deal resolvers; identity/tenant/domain-scoped reads; explicit 0/1/many outcomes; deterministic read/status intents outside lifecycle. |
| Explicitly out of scope | ActionContract lifecycle; callback approval/rejection; execution claims; Evidence Finalizer; MessageContract rendering; `app.py` integration; flags; catalog; production rollout. |
| Owned intents | `create_task`, `update_task`, `complete_task`, `search_task`, `create_lead`, `update_lead`, `search_lead`, known entity update, and deterministic read/status intents that are not approval/execution lifecycle signals. |
| Owned interfaces | `RouteDecision` input; planned `IntentOwnershipDecision`, `CanonicalActionProposal`, `ResolverResult`; existing `route_request()` and `deterministic_create_task_title()` contracts preserved until an approved adapter exists. |
| Owned files | `core/router/router.py` (`route_request`, `deterministic_create_task_title`); `core/router/route_decision.py` (`Intent`, `Handler`, `RouteDecision`); `core/router/intent_router.py`; `core/router/risk_router.py`; `core/lead_candidate_handler.py`; `core/adapters/leads_adapter.py`; new resolver/builder modules only. |
| Shared files | `app.py` integration seam only through the integrator; `core/turn_envelope.py` read-only observation; `feature_flags.py` read-only. |
| Forbidden files | `core/action_gateway.py`, `core/action_contract_repository.py`, `core/action_gateway_atomic_executor.py`, `event_bus.py`, `tma_api.py`, MessageContract/formatter/approval adapters, `feature_flags.py` edits. |
| Existing tests | `test_create_task_deterministic_route.py`, router tests, `test_bug104_*`, `test_tier2_silent_preview.py`, `test_turn_envelope.py`. |
| New tests required | One test per builder; resolver 0/1/many, tenant/identity scope, bounded-read and cold-cache tests; Agent forbidden for known deterministic paths; unsupported intent test. |
| Entry criteria | Fresh `turn_coordinator_routing` bundle; all mandatory receipts; contract freeze approved for inputs/outputs; no unresolved authority conflict. |
| Exit criteria | All owned intents have deterministic/Agent/unsupported decisions; builders emit named canonical proposals; resolver behavior is bounded and tested; no approval or reply authority moved. |
| Dependencies | Contract freeze; existing `RouteDecision`; no runtime dependency on Workstreams 2/3 for local modules. |
| Expected commits | `tc1: ownership registry`; `tc2: task builders`; `tc3: task/entity resolvers`; `tc4: lead builders and deterministic admission`. |
| Rollback strategy | Remove the new coordinator/builder/resolver entry point or keep it dark; preserve existing router/Agent path; no data migration. |
| Feature flag strategy | No flag edits. Any future activation remains off/shadow until the integration plan gates it. |
| Librarian profile | Primary `turn_coordinator_routing`; secondary `core_reasoning_change` for lead reasoning boundaries; `tool_execution` only when canonical tool metadata is touched. |
| Required source receipts | Profile checklist plus direct receipts for router, RouteDecision, lead handler/adapters, current-state authority docs, relevant deterministic tests, and every newly discovered caller/callee. |

## Workstream 2 — Approval, Lifecycle, Evidence and Concurrency

| Field | Plan |
|---|---|
| Goal | Keep ActionContracts as lifecycle authority, make execution fail-closed and evidenced, and serialize approval/callback/text ownership. |
| Current verified state | `core/action_gateway.py` owns lifecycle APIs; `core/action_contract_repository.py` is durable lifecycle storage; `core/action_gateway_atomic_executor.py` gates claims when enabled; `app.py`, EventBus, session state, and TMA still expose parallel pending/presentation paths. |
| Exact scope | ActionContract lifecycle; ActionGateway confirmation/cancellation; callback approve/reject; terminal replay; stale/expired/duplicate protection; durable turn state; callback/text race; explicit reply owner for lifecycle turns; Evidence Finalizer at execution boundary; verified completion only. |
| Explicitly out of scope | Business intent classification/builders/resolvers; MessageContract schema/rendering and channel parity; feature-flag changes; catalog; production configuration; direct dispatcher policy expansion beyond the approved seam. |
| Owned intents | `approval_status`, `execution_status`, `pending_queue_query`, `confirmation`, `cancellation`, `terminal_replay`, `callback_approve`, `callback_reject`, `stale_callback`, `expired_action`, `duplicate_callback`. |
| Owned interfaces | Planned `ActionLifecycleResult`, `EvidenceResult`; existing ActionGateway lifecycle methods, `ActionContractRepository`, atomic claim executor, and callback result semantics. |
| Owned files | `core/action_gateway.py`; `core/action_contract_repository.py`; `core/action_gateway_atomic_executor.py`; `core/action_resolution_projection.py`; `core/approval_turn_metrics.py`; `app.py` callback/confirmation integration only through the integrator; `event_bus.py` lifecycle-pointer migration only through an approved patch; `tma_api.py` approval execution helpers only through an approved patch. |
| Shared files | `app.py` single integration owner; `core/turn_envelope.py` read-only signal consumption; `core/agent_message_formatter.py` reply-owner input only, not rendering. |
| Forbidden files | Router and builder modules; `core/message_contract.py`; `core/agent_message_formatter.py` rendering; surface adapters; `feature_flags.py` edits; catalog. |
| Existing tests | `test_action_gateway.py`, `test_approval_concurrency.py`, `test_bug056_legacy_cancel_replay_guard.py`, `test_bug_approval_callback_hardening.py`, `test_bug_post_completion_callback_fallthrough.py`, `test_bug_stale_callback_ux.py`, atomic-claims and durable-lifecycle tests. |
| New tests required | Exact callback-to-contract resolution; stale/expired/terminal/duplicate callbacks; callback/text race; restart and multi-instance ownership; every approval-required direct dispatcher path; evidence `completed` vs `outcome_unknown`; one final responder. |
| Entry criteria | Fresh `turn_coordinator_routing` plus `approval_ux` coverage; ActionLifecycleResult/EvidenceResult freeze; Workstream 1 proposal seam frozen; no direct-fallback authority exception. |
| Exit criteria | Lifecycle and execution claims are canonical and durable; callback/text races are bounded; no tool call is reported as verified completion without evidence; reply owner is explicit. |
| Dependencies | Contract freeze; Workstream 1 `CanonicalActionProposal` seam for new mutations. Workstream 3 MessageContract adapter is a downstream integration seam, not a hard dependency for WS2 development or merge. |
| Expected commits | `tc5: lifecycle resolver`; `tc6: reply ownership`; `tc7: evidence/dispatcher proof`; `tc8: durable turn concurrency`. |
| Rollback strategy | Disable only the new lifecycle integration path; never restore direct execution fallback; retain canonical contract history and fail closed on ambiguous state. |
| Feature flag strategy | No flag edits. Existing flags remain unchanged and are evaluated only by current policy until a separately approved rollout. |
| Librarian profile | Primary `turn_coordinator_routing`; secondary `approval_ux` and `tool_execution`; `rp5_evidence_mismatch` when Evidence Finalizer logic is touched. |
| Required source receipts | ActionGateway/repository/atomic executor, app callback paths, EventBus/TMA projection paths, approval/evidence authority docs, concurrency/replay tests, and direct dispatcher callers. |

## Workstream 3 — MessageContract, Surfaces and Verification Harness

| Field | Plan |
|---|---|
| Goal | Make one public MessageContract projection safe and consistent across Telegram, WhatsApp, TMA/API, while providing staging evidence and rollout gates. |
| Current verified state | `core/message_contract.py` is the planned public contract; `core/agent_message_formatter.py` renders it; ApprovalLifecycleResult, ActionFact, GatewayReply, and legacy surface paths still require adapters. Internal identifiers/tool names must not leak. |
| Exact scope | MessageContract projection; `display_payload` rendering; Telegram/WhatsApp/TMA/API parity; pending/rejected/completed/failed wording; redaction; automated staging harness; readiness reports; canary and rollback gates. |
| Explicitly out of scope | Intent classification; builders/resolvers; ActionContract lifecycle; approval authorization; execution claims; feature flags; catalog; production activation. |
| Owned intents | User-facing projections for approval pending, rejected/cancelled, completed, failed, and outcome-unknown states; no lifecycle decision ownership. |
| Owned interfaces | `MessageContract`; `ActionFact` → MessageContract; `ApprovalLifecycleResult` → MessageContract; planned `EvidenceResult` consumption; surface adapter input/output contracts. |
| Owned files | `core/message_contract.py`; `core/agent_message_formatter.py`; `core/action_fact_message_adapter.py`; `core/approval_lifecycle_message_adapter.py`; surface formatter modules/tests; new verification harness and readiness-report modules. |
| Shared files | `app.py` final integration only through the integrator; `core/action_gateway.py` result adapter seam only; `tma_api.py` response adapter seam only. |
| Forbidden files | Router, builders/resolvers, ActionContract repository/lifecycle, atomic claims, `event_bus.py`, `feature_flags.py` edits, catalog. |
| Existing tests | `test_message_contract.py`, `test_agent_message_formatter.py`, `test_agent_message_formatter_display_payload.py`, action-fact and approval-lifecycle adapter tests, F52 status reconciliation and redaction tests. |
| New tests required | Cross-surface golden cases; no internal IDs/tool names; pending/rejected/completed/failed/outcome-unknown precedence; adapter compatibility; harness readiness and rollback reports. |
| Entry criteria | MessageContract freeze; ActionLifecycleResult/EvidenceResult field mapping approved; Workstream 2 reply/evidence seam frozen. |
| Exit criteria | Every supported surface consumes the public contract; wording and redaction are parity-tested; harness produces a readiness report without claiming deployment or completion. |
| Dependencies | MessageContract freeze; Workstream 2 lifecycle/evidence result seam; no hard dependency on Workstream 1 implementation. |
| Expected commits | `tc9: MessageContract adapters and surface parity`; `tc10: verification harness and rollout gates`. |
| Rollback strategy | Keep existing adapters/renderers as compatibility path; disable only new projection/formatting path; never change lifecycle state during UX rollback. |
| Feature flag strategy | No flag edits. Formatter/evidence flags can change only after staging gates and owner approval described in the integration plan. |
| Librarian profile | Primary `turn_coordinator_routing`; secondary `approval_ux`; `rp5_evidence_mismatch` for evidence/status wording; `tool_execution` only for displayed execution results. |
| Required source receipts | MessageContract, formatter/adapters, ActionGateway result contracts, surface handlers, UX authority docs, evidence docs, and parity/redaction tests. |

## File ownership map

| File/module | Primary owner | Allowed secondary owner | Reason | Concurrent edits allowed | Integration required |
|---|---|---|---|---:|---:|
| `app.py` | Integrator only | WS1/2/3: patch proposal, no direct branch edits | all ingress, callback, Agent, and surface seams converge here | No | Yes, one integration commit |
| `core/router/router.py` | WS1 | Integrator for seam review | routing/admission | Yes, WS1 only | No unless API changes |
| `core/router/route_decision.py` | WS1 | all agents review-only | shared routing contract | No contract edits in parallel | Yes if fields change |
| `core/turn_envelope.py` | WS2 | WS1/3 review-only | ownership/concurrency observation | No | Yes if signal fields change |
| `core/action_gateway.py` | WS2 | WS3 adapter review-only | lifecycle authority | No | Yes for MessageContract adapter seam |
| `core/action_contract_repository.py` | WS2 | none | durable lifecycle source | No | Yes |
| `core/action_gateway_atomic_executor.py` | WS2 | none | execution claim/evidence boundary | No | Yes |
| `core/message_contract.py` | WS3 | WS2 review-only | public presentation contract | No contract edits in parallel | Yes |
| `core/agent_message_formatter.py` | WS3 | WS2 reply-owner review-only | final user-facing rendering | No | Yes |
| `core/action_fact_message_adapter.py` | WS3 | WS2 review-only | ActionFact projection | Yes, WS3 only | No unless fields change |
| `core/approval_lifecycle_message_adapter.py` | WS3 | WS2 review-only | lifecycle result projection | Yes, WS3 only | No unless fields change |
| `event_bus.py` | WS2 | none | legacy presentation pointers/replay | No | Yes |
| `feature_flags.py` | Integrator/release owner | all agents read-only | deployment policy | No | Only separately approved rollout |
| `tma_api.py` | WS2 | WS3 response adapter review-only | TMA approval/projection execution | No | Yes |

`app.py` has a single integration owner. The three agents must not edit it in
parallel; WS1/2/3 submit isolated integration patches against the same base.

## Shared contract freeze

| Contract | Purpose | Owner | Fields | Producer | Consumer | Backward compatibility | May change during workstream? |
|---|---|---|---|---|---|---|---:|
| `RouteDecision` | Existing classifier/risk result | WS1 | channel, intent, domain, risk, handler, approval, confidence, tool/capture signals | router | coordinator/legacy Agent path | preserve existing fields/defaults | No |
| `IntentOwnershipDecision` | Select one owner without executing | WS1 | intent, owner, reason, confidence, resolver requirement, proposal/evidence/reply policy refs | WS1 registry | handlers, WS2/WS3 adapters | new additive type; legacy route adapts | No |
| `CanonicalActionProposal` | Named, validated mutation proposal | WS1 | intent, canonical_tool, resource, fields, risk, approval_required, evidence_requirement, reply_policy | builders | ActionGateway | legacy tools remain behind adapter | No |
| `ResolverResult` | Bounded entity/reference outcome | WS1 | entity kind, scope, match_count, stable reference, source/version, freshness, error | resolvers | builders/coordinator | 0/1/many required; no silent fallback | No |
| `ActionLifecycleResult` | Canonical lifecycle projection | WS2 | contract ref, lifecycle state, approval state, execution state, reply owner, error/replay classification | ActionGateway | WS3 adapter/surfaces | existing Gateway reply remains compatibility input | No |
| `EvidenceResult` | Execution/completion evidence | WS2 | result, evidence_ref, provider result, verified state, outcome_unknown/error | executor/finalizer | ActionGateway, WS3 | no success inference from text | No |
| `MessageContract` | Sole public presentation input | WS3 | state, display_payload, reply_owner, turn context, evidence metadata, redacted content | adapters | formatter/surfaces | adapters preserve current internal result contracts | No |

`IntentOwnershipDecision`, `CanonicalActionProposal`, `ResolverResult`, and
`EvidenceResult` are not current stable runtime contracts. They are
`PRE_PARALLEL_BLOCKER` for authority-changing implementation: agents may draft
schemas/tests independently, but no three-way integration starts until the
fields above are frozen. `RouteDecision`, `ActionLifecycleResult`, and
`MessageContract` exist in current code/planning and still require compatibility
review before field changes.

## Dependency graph and merge order

| Workstream | Can start immediately | Hard dependency | Soft dependency | Integration dependency | Merge dependency |
|---|---|---|---|---|---|
| WS1 | Yes: inventory, schema drafts, isolated builders/resolvers | contract freeze before runtime behavior | WS3 naming/redaction policy | integrator for `app.py` | first |
| WS2 | Yes: lifecycle/replay/evidence tests and isolated modules | ActionLifecycleResult/EvidenceResult freeze | WS1 proposal shape | integrator for app/EventBus/TMA | after WS1 seam |
| WS3 | Yes: adapter/harness tests and isolated modules | MessageContract freeze | WS2 lifecycle/evidence fields | integrator for app/TMA/surfaces | after WS2 seam |

Development can run in parallel. Merge must be ordered: **freeze → WS1 → WS2
→ WS3 → integration harness/canary**. If a workstream is delayed, the others
may continue only with frozen contracts and no edits to its owned/shared files.

## Integration seams

| Producer | Consumer | Interface | Example payload | Error behavior | Ownership behavior | Compatibility test |
|---|---|---|---|---|---|---|
| Routing | builders | `IntentOwnershipDecision` | `{intent:"update_task", owner:"RESOLVER", resolver:"tasks"}` | clarify/unsupported, never Agent guess | WS1 selects only | route + ownership tests |
| Builders | ActionGateway | `CanonicalActionProposal` | `{intent:"create_task", canonical_tool:"task_create", fields:{title:"..."}, approval_required:true}` | reject invalid/missing named fields | WS1 proposes; WS2 authorizes | builder/Gateway contract test |
| ActionGateway/Evidence | MessageContract | `ActionLifecycleResult` + `EvidenceResult` adapter | `{lifecycle:"completed", evidence:{verified:true,evidence_ref:"..."}}` | `outcome_unknown` never becomes success | WS2 owns lifecycle/evidence; WS3 renders | lifecycle/formatter precedence tests |
| MessageContract | surfaces | `format_agent_message(MessageContract)` | `{state:"approval_pending", display_payload:{...}, reply_owner:"gateway"}` | redacted safe fallback | WS3 owns wording; surface does not reinterpret state | Telegram/WhatsApp/TMA/API parity tests |
| Harness | runtime observability/evidence | readiness report/telemetry inputs | `{case:"duplicate_callback", provider_calls:1, result:"pass"}` | report blocked/incomplete, never completion claim | harness observes; no authority | staging harness and rollback tests |

## Conflict prevention and coverage audit

- Each agent branches from the canonical `origin/main` SHA and runs its own
  Librarian profile before implementation.
- No cross-agent cherry-pick without the integrator’s decision.
- Any shared-contract change updates all three workstream plans before code.
- No local authority change, scope expansion, test/guard/validation/telemetry
  deletion, or feature-flag edit.
- No parallel `app.py` edits. The integrator owns all integration commits.
- Every future PR returns a consumption report with receipts and verifier
  result.

| Existing gap | Exactly one owner |
|---|---|
| callback direct fallback | Workstream 2 |
| four pending/approval stores | Workstream 2 |
| durable turn/concurrency state | Workstream 2 |
| known deterministic intents reach Agent | Workstream 1 |
| dispatcher approval metadata bypass | Workstream 2 |
| canonical builders | Workstream 1 |
| entity resolver divergence | Workstream 1 |
| conditional reply ownership | Workstream 2 |
| Evidence Finalizer missing | Workstream 2 |
| surface rendering drift | Workstream 3 |
| batch/session preview lifecycle | Workstream 1 |
| legacy EventBus presentation pointers | Workstream 2 |
| catalog stale metadata/BUG-140 coverage | Deferred follow-up |
