# Agent-Last Cost Architecture

STATUS:
ARCHITECTURE SPEC — APPROVED FOR IMPLEMENTATION PLANNING
NOT IMPLEMENTED
NOT RUNTIME VERIFIED

Created: 2026-08-25  
Last Updated: 2026-08-25  
Planning baseline SHA: `7e3dcf94e76a33e9e1bb5b0ad3570fb1c7919703`  
Track: D-STRUCTURE  
Audit: #23 Cost Audit

This document is a target architecture and implementation-planning boundary. It does not claim that the target architecture exists in runtime.

## 1. Current Verified Baseline

The following statements describe `origin/main` at the planning baseline above.

### CURRENT VERIFIED STATE

- `app.py:3774` still exposes `run_agent()`, the broad Agent execution path.
- `core/router/route_decision.py:151` defines `RouteDecision`; `core/router/router.py` already provides partial deterministic routing for known structured operations.
- `core/action_gateway.py` and `core/action_contract_repository.py` provide a canonical captured-operation lifecycle for covered paths, while `FEATURE_ACTION_GATEWAY` remains a compatibility/shadow boundary in existing callers.
- Legacy approval and confirmation paths remain in `app.py` and related components.
- `core/migrations/002_usage_events.sql:35` defines the provider-neutral `usage_events` ledger foundation; `core/usage_telemetry.py:73` records usage and `:208` aggregates it, but its module documentation describes the ledger as shadow-only for policy decisions.
- `core/model_pricing.py` is the intended provider/model pricing boundary for new usage instrumentation; legacy cost code still contains private pricing logic.
- `cost_monitor.py` and `core/cost_watchdog.py` both perform usage/cost monitoring work; they overlap with the durable ledger rather than constituting one unified target authority.
- `cost_monitor.py:_trigger_daily_stop()` can request a durable `EMERGENCY_STOP_AI` write, while `app.py:4661-4665` checks that stop immediately before the Agent loop. Coverage across all paid paths is incomplete.

These facts are migration inputs, not evidence of target compliance.

### TARGET ARCHITECTURE

The target is an Agent-last execution hierarchy, one capability authority, one canonical raw usage ledger, one pricing authority, and one automatic cost-policy watchdog. Implementation is deferred to dependency-ordered slices below.

## 2. Architectural Principles

These are normative:

1. **AGENT LAST.** Full Agent is residual, not the default for known executable work.
2. **CAPABILITY BEFORE EXECUTION.** Known executable work resolves capability ownership before choosing an executor.
3. **DECIDE → EXECUTE → VERIFY.** Routing/ownership, execution, and verification are separate authorities.
4. **CAPTURE ONCE.** Approval continuation executes a captured operation rather than reinterpreting raw text.
5. **BUSINESS IDENTITY ≠ IMPLEMENTATION IDENTITY.** `capability_id` survives semantically equivalent executor/provider replacement.
6. **CANONICAL COST TRUTH.** Paid-call measurement comes from one canonical ledger and one pricing authority.
7. **EVIDENCE BEFORE SUCCESS.** Generated text alone cannot prove execution success.

## 3. Route Outcome Contract

Conceptual route outcomes are:

| Category | Outcomes | Contract |
|---|---|---|
| Terminal | `CLARIFY`, `BLOCK`, `ENGINEERING_NOTE` | End the route; never silently execute. `BLOCK` and `CLARIFY` cannot fall through. |
| Pre-execution gate | `APPROVAL` | Approval is orthogonal to `ExecutionClass`; it gates execution and is not execution evidence. |
| Executable | `DETERMINISTIC`, `NARROW_MODEL`, `FULL_AGENT` | Exactly one class owns an executable route. |
| Modifier | `RESTRICTED` | Restricts `FULL_AGENT`; it is not a separate `ExecutionClass`. |

An unknown bounded capability must not silently become `FULL_AGENT`.

## 4. ExecutionClass Contract

### `DETERMINISTIC`

Bounded known behavior, validated bounded input, deterministic executor, explicit verification, and zero paid inference calls per operation.

### `NARROW_MODEL`

Bounded inference with an explicit input/output contract, bounded calls/tokens/time, no dynamic full-Agent tool loop, an explicit verifier, explicit cost attribution, and an explicit fallback policy.

### `FULL_AGENT`

Residual open-ended reasoning with a bounded Agent/tool loop, explicit verification, and no default use for unresolved bounded capability ownership.

ExecutionClass cannot silently escalate. If execution under the frozen class fails, the result is fail-closed or a new explicit routing decision.

## 5. Capability Contract

`capability_id` is the stable business capability identity. Examples include `lead.create`, `lead.update`, `task.create`, `task.complete`, `approval.list`, and `general.reasoning`.

- `capability_id` answers **what**.
- `ExecutionClass` answers **how**.
- Tool/provider/adapter answers **with what implementation**.

The conceptual `CapabilityContract` contains:

| Boundary | Required meaning |
|---|---|
| Identity | `capability_id` and immutable version/reference where required |
| Execution | `ExecutionClass` and executor binding policy |
| Input | Validator and normalizer contract |
| Policy | Risk, approval requirements, restrictions |
| Verification | Verifier and evidence policy |
| Output | Canonical result/reply ownership |
| Attribution | Business workflow/capability dimension |
| Escalation | Explicit allowed fallback policy |

This SPEC deliberately does not choose a concrete class or file implementation.

## 6. Capability Authority

Current main contains multiple specialized registry-like authorities. The target is one canonical capability API that composes them rather than duplicating them. It may compose router intent ownership, `IntentOwnershipRegistry`, tool policy/schema authority, ActionGateway operation contracts, external capability registration, and task-specific Turn Coordinator ownership.

`business_tool_registry` remains recommendation/catalog authority only. This SPEC does not create or require a new concrete registry class or file.

## 7. Routing / Turn Coordinator Handoff

The target conceptual chain is:

```text
TurnInput → RouteDecision → capability resolution → CapabilityContract
          → ExecutionClass → executor → verifier
```

The existing router may remain a temporary decision authority. The formal Turn Coordinator becomes the long-term capability-resolution authority as its architecture is completed.

**CROSS-TRACK → #24 Architecture Drift:** earlier capability-resolution and Turn Coordinator authority migration. This SPEC does not implement #24.

## 8. Approval / Captured Operation Contract

The normative flow is:

```text
route once → resolve capability → normalize/validate → create captured contract
→ approval → revalidate → execute exact captured operation → verify
```

Raw user text is audit/display context only after capture. The prohibited path is:

```text
approval → original raw text → run_agent() → reinterpretation
```

Approval is not execution evidence.

## 9. ActionContract Freeze Requirements

The conceptual handoff is:

```text
RouteDecision → ResolvedCapability → normalized payload → ActionContract
```

An ActionContract must eventually freeze or reference:

- `capability_id` and immutable capability version/reference;
- `ExecutionClass`;
- normalized executable payload;
- selected executor when semantics require it;
- proposal-time approval/risk decision;
- requester, actor, tenant, and origin;
- fingerprint/idempotency data; and
- request/operation correlation.

Pending approval must not resolve silently against the latest capability. Contract-breaking changes require fail-closed behavior, new routing/approval, or an explicitly proven semantically equivalent migration.

## 10. Executor Replacement

An executor/provider may retain the same `capability_id` only when equivalence is proven for input contract, output contract, business semantics, side effects, approval/risk behavior, idempotency/retry behavior, verification evidence, and failure/outcome-unknown semantics.

Conceptually, `lead.create → executor A → executor B` may retain `lead.create` only under those equivalence conditions.

## 11. Verification Contract

- `DETERMINISTIC` ends in a structured result, lifecycle evidence, or ActionGateway evidence.
- `NARROW_MODEL` ends in schema validation plus applicable domain evidence.
- `FULL_AGENT` ends in tool receipts, execution verification, an evidence projection, and anti-hallucination sanitization.

Every executable path terminates in a verified result or explicit failure/outcome-unknown. Generated success text is never sole proof.

## 12. Cost Attribution Contract

`capability_id` is the primary business cost dimension. Every paid inference event must be attributable to:

- capability;
- `ExecutionClass`;
- workflow/source;
- operation ID;
- request/turn/run correlation where applicable; and
- ActionContract ID where applicable.

Runtime observation additionally records provider, service, concrete model identifier, usage quantities, provider request ID, cost, fallback/retry role, and outcome where available. Provider/model are observations, not business identity.

## 13. Operation Correlation

One logical operation may have zero, one, multiple Agent, retry, or fallback calls. Paid calls share operation correlation but remain separate usage events. Background work uses job/workflow/run identity without inventing a human user identity. ActionContract ID is correlation metadata, not capability identity.

## 14. Deterministic Zero-Call Contract

`ExecutionClass=DETERMINISTIC` implies zero paid inference events for the operation. Measurement requires positive proof that the deterministic operation occurred plus zero correlated paid inference events. Missing telemetry is not evidence of zero calls.

## 15. Canonical Usage Ledger

`usage_events` is the canonical raw usage authority. Its current provider-neutral schema remains the foundation; target attribution is a small additive semantic extension. This SPEC does not define migration SQL or exact database field names.

Telemetry producer failure is fail-soft for ordinary business execution but must mark an observability gap. Telemetry incompleteness blocks promotion to enforcement.

## 16. Pricing Authority

`core/model_pricing.py` is the canonical target pricing authority. Legacy private pricing tables are transitional only. Provider/model pricing changes do not change capability identity.

## 17. Canonical Aggregation

The target flow is:

```text
usage_events → canonical aggregation/query boundary → watchdog
```

Aggregation must support time windows, capability, ExecutionClass, workflow, operation, provider/service, exact versus estimated cost, fallback/retry visibility, and background usage. The watchdog consumes aggregation; it is not provider instrumentation authority.

## 18. Unified Watchdog Authority

One canonical watchdog owns automatic cost-policy decisions: canonical aggregate queries, threshold evaluation, owner alerts, soft enforcement, hard enforcement, automatic `EMERGENCY_STOP_AI` writes, write verification, and auditable decision evidence.

It does not own provider instrumentation, business routing, model selection, duplicate pricing, or private counters as cost truth.

## 19. Watchdog Control Modes

| Mode | Behavior |
|---|---|
| `OFF` | No policy action |
| `SHADOW` | Calculate/report only |
| `ALERT` | Calculate and notify; no stop |
| `ENFORCE` | Verified automatic stop where policy requires |

One canonical policy controls mode. Legacy flags are migration adapters only.

## 20. Emergency Stop Contract

Automatic cost stop and manual operator stop are distinct authorities. Only the unified cost-policy authority may trigger an automatic cost stop; manual owner/admin control remains separately authorized.

The automatic sequence is:

```text
threshold breach → watchdog decision → durable write → readback verification
→ enforcement evidence → notification
```

Without a verified write, the system must not claim enforcement succeeded.

## 21. Failure Semantics

- Telemetry write failure: fail-soft for the business operation; mark an observability gap.
- Aggregation/query failure: never interpret as zero usage; enforcement decision fails safely.
- Unknown pricing: explicit unknown/conservative estimate; never silent zero.
- Hard-stop write/readback failure: never report enforcement success.
- Executor failure: never silently escalate `ExecutionClass`.

## 22. Promotion Gates

`ENFORCE` cannot activate until all gates pass:

| Gate | Evidence required |
|---|---|
| G1 | Paid-call telemetry completeness |
| G2 | Capability and ExecutionClass attribution completeness |
| G3 | Representative post-Turn-Coordinator measurement |
| G4 | Provider billing reconciliation |
| G5 | Approved threshold policy |
| G6 | Emergency-stop canary and rollback proof |

Required sequence:

```text
IMPLEMENT → SHADOW → RECONCILE → POST-TC MEASURE → CALIBRATE
→ ALERT → CANARY → ENFORCE
```

## 23. Legacy Migration

- `cost_monitor.py`: migration adapter, then retire private counters and private pricing authority.
- `core/cost_watchdog.py`: reporting/migration adapter, then retire JSONL/count authority.
- `AI_Usage_Daily` and similar stores: reporting projections only; never cost truth, threshold authority, or enforcement authority.
- Legacy raw-text approval: retire after canonical captured-contract coverage exists.
- Legacy `Handler` values: remain compatibility metadata during additive migration.

## 24. Migration Order

1. Introduce capability semantics and identity.
2. Establish the capability-resolution handoff.
3. Freeze capability ownership into captured operations.
4. Migrate bounded approval continuations away from raw-text rerouting.
5. Add canonical cost-attribution dimensions.
6. Ensure all paid paths emit canonical events.
7. Consolidate pricing authority.
8. Add canonical aggregation.
9. Introduce the unified watchdog in `SHADOW`.
10. Reconcile provider usage and billing.
11. Collect representative post-Turn-Coordinator measurements.
12. Approve and calibrate threshold policy.
13. Promote to `ALERT`.
14. Canary stop and rollback.
15. Promote to `ENFORCE`.
16. Retire duplicate counter/JSONL authorities.
17. Retire obsolete compatibility paths only after reachability proof.

This is a planning sequence, not an implementation commit plan.

## 25. Cross-Track Dependencies

- **#24 Architecture Drift:** Turn Coordinator and earlier capability-resolution authority implementation.
- **Approval-owning track:** raw-text approval retirement and approval-continuation migration.
- **#16 Tool Contract:** only where executor/tool contract changes become necessary.

These dependencies do not change the #23 architectural contract. No implementation ownership is reassigned here.

## 26. Non-Goals

This SPEC excludes exact class/file design, exact migration SQL, concrete database field names, vendor/provider selection, exact threshold values, full Turn Coordinator implementation, broad approval UX redesign, broad tool refactor, immediate hard enforcement, production activation, unrelated #23 cost guesses, and monetary savings estimates without runtime evidence.

## 27. Required KPIs

Measure at least:

- `model_calls_per_operation`
- `deterministic_zero_model_rate`
- `agent_required_rate`
- `narrow_model_rate`
- `background_model_call_rate`
- `provider_cost_per_workflow`
- `cost_per_capability`
- `model_calls_avoided_by_deterministic_orchestration`
- `telemetry_unknown_attribution_rate`
- `fallback_rate`

No numeric targets are set here except `DETERMINISTIC → zero paid model calls`.

## 28. Acceptance Criteria

Implementation is complete only when evidence proves, as applicable:

1. Known deterministic capability resolves before Agent fallback.
2. `capability_id` is stable and observable.
3. Exactly one ExecutionClass owns each executable route.
4. Deterministic execution performs zero paid inference calls.
5. Narrow inference cannot enter the full Agent loop.
6. Raw-text approval rerouting is not executable authority.
7. Captured operations preserve capability ownership across approval delay.
8. Executor/provider replacement cannot silently change business semantics.
9. Every paid call reaches the canonical usage ledger.
10. Paid events carry capability, ExecutionClass, and operation attribution.
11. Canonical pricing has one authority.
12. The watchdog reads canonical aggregates.
13. Legacy private counters are not enforcement truth.
14. Automatic hard stop is owned by one canonical watchdog.
15. Hard-stop writes are durably verified.
16. All paid execution paths honor the stop boundary before `ENFORCE`.
17. Provider billing reconciliation passes before `ENFORCE`.
18. Post-Turn-Coordinator measurement occurs before threshold calibration/enforcement.
19. Rollback and manual control are proven.
20. No success claim exists without evidence.

## 29. Verification Plan

Required verification categories are:

- static contract tests;
- capability resolution tests;
- deterministic zero-call tests;
- approval-continuation tests;
- ActionContract freeze and legacy-compatibility tests;
- telemetry attribution tests;
- retry/fallback correlation tests;
- background attribution tests;
- pricing consistency tests;
- watchdog aggregation tests;
- `SHADOW` and `ALERT` mode tests;
- emergency-stop write/readback tests;
- paid-path stop-coverage tests;
- rollback/manual-stop precedence tests;
- provider billing reconciliation evidence; and
- post-Turn-Coordinator runtime measurement evidence.

Every result is labeled `STATIC VERIFIED`, `RUNTIME VERIFIED`, or `PRODUCTION VERIFIED`. Tests alone do not establish production verification.

## 30. Implementation Decomposition

Each implementation slice must state purpose, owned contract, verified likely files/areas, cross-track dependency, required tests/evidence, and rollback/compatibility constraint. The following phases are dependency-ordered planning slices, not implementation:

| Phase | Scope | Likely verified areas | Ownership note |
|---|---|---|---|
| A | Capability semantics and compatibility | `core/router`, capability/tool contracts | #23 boundary |
| B | Capability-resolution handoff | router and Turn Coordinator boundaries | #24 dependency-only where TC-owned |
| C | Captured-operation capability freeze | `core/action_gateway.py`, ActionContract repository | #23 boundary; approval dependency |
| D | Approval-continuation migration | approval handlers and continuation stores | Approval-owning track dependency |
| E | Canonical cost attribution | `core/usage_telemetry.py`, paid-call producers | #23 boundary |
| F | Canonical paid-path coverage | Agent and paid provider call sites | #23 boundary |
| G | Pricing consolidation and aggregation | `core/model_pricing.py`, usage query boundary | #23 boundary |
| H | Unified watchdog `SHADOW` | `cost_monitor.py`, `core/cost_watchdog.py` adapters | #23 boundary |
| I | Measurement and reconciliation | runtime telemetry and provider billing evidence | #23 boundary |
| J | `ALERT` and canary | watchdog policy and stop boundary | #23 boundary |
| K | `ENFORCE` | paid-path gates and `core/emergency_stop.py` | #23 boundary, gated by all evidence |
| L | Legacy authority retirement | legacy watchdog/counter/reporting reachability | #23 boundary after reachability proof |

No phase authorizes bundling all work into one PR.

## 31. Rollback Principles

- Migrate additively first.
- Keep legacy behavior only behind an explicit compatibility boundary.
- Never silently fall back to Agent.
- Never silently resolve the latest capability for a pending contract.
- Run `SHADOW` before policy action and `ALERT` before `ENFORCE`.
- Manual operator stop cannot be accidentally cleared by automated logic.
- Evidence remains available after rollback.

## 32. Status Matrix

| Area | Current State | Target State | Implementation Owner | Verification Gate |
|---|---|---|---|---|
| Routing/capability | Partial router decision; multiple authorities | Canonical capability-resolution API | #23 with #24 dependency | Capability resolution |
| ExecutionClass | Not yet a unified runtime contract | Exactly one class per executable route | #23 | Static + route tests |
| Approval continuation | Legacy and canonical paths coexist | Captured operation only | Approval-owning track | Freeze/continuation |
| ActionContract freeze | Covered lifecycle exists; target fields remain additive | Capability/class frozen or referenced | #23 / ActionGateway owner | Contract tests |
| Usage attribution | Provider-neutral ledger foundation | Complete capability/class/operation attribution | #23 | Telemetry completeness |
| Paid-path coverage | Incomplete | Every paid path at stop boundary and ledger | #23 | Coverage evidence |
| Pricing | Canonical target exists; legacy pricing remains | One pricing authority | #23 | Reconciliation |
| Aggregation | Ledger aggregation exists; policy integration incomplete | Canonical aggregation boundary | #23 | Aggregate tests |
| Watchdog | Two overlapping monitors | One policy watchdog | #23 | Shadow/alert tests |
| Hard stop | Durable mechanism exists; coverage incomplete | Verified unified automatic stop | #23 | Canary/readback |
| Billing reconciliation | Not established by this SPEC | Provider reconciliation before enforcement | #23 | G4 |
| Post-TC measurement | Not established by this SPEC | Representative measurement before calibration | #24/#23 | G3 |
| Legacy retirement | Transitional authorities remain | Retire after reachability proof | #23 | Retirement audit |

## 33. Open Questions

NONE at the architectural level. Remaining questions are implementation-level and must be resolved within the relevant slice without changing this contract: exact additive attribution fields, concrete resolver composition, per-provider coverage inventory, deployment/canary mechanics, and threshold policy values.

## SPEC Quality Gate

Self-review: **PASS**.

- Agent-last leaves `FULL_AGENT` as residual behavior.
- Capability identity is separated from ExecutionClass and tool/provider identity.
- Capability authority is separated from ActionContract operation authority.
- Approval is a gate, not execution authority; raw text is not executable truth after capture.
- Verification is separate from execution.
- `usage_events` is raw truth, not policy authority; `core/model_pricing.py` is the target pricing authority.
- One future watchdog owns automatic cost enforcement.
- Current runtime state is not described as migrated.
- `ENFORCE` is explicitly gated.
- Cross-track ownership and non-goals are explicit.
- No vendor, tool, repository, class, field, threshold, or implementation was selected without need.
