# BOSS Agent Reliability and Permission Hardening Spec

Status: planning/specification only. No code is implemented by this document.

## 1. Objective

Strengthen the existing BOSS agent runtime so that it exposes only usable tools, fails on registry ambiguity, reports side effects from evidence rather than model prose, stops unproductive tool loops, makes scheduler automation explicit and recoverable, and preserves one hardened approval boundary.

This is an additive hardening plan, not an architecture rewrite. The current Sources of Authority remain:

- `tool_registry.py` owns tool permission/risk metadata (`tool_registry.py:1-5`, `tool_registry.py:19-28`).
- `context.py` owns role-based model/tool exposure (`context.py:40-79`, `context.py:253-267`).
- `core/anti_hallucination.py` owns execution-evidence and claim validation (`core/anti_hallucination.py:1-7`, `core/anti_hallucination.py:381-430`).
- `core/action_gateway.py` owns business action contracts and approval execution (`core/action_gateway.py:574-590`, `core/action_gateway.py:626-780`).
- `scheduler.py` owns fixed scheduled job registration and emergency gating (`scheduler.py:770-862`).

That ownership follows the repository’s one-Source-of-Authority and tool/gate separation rules (`docs/governance/MODULE_RULES.md:9-19`, `docs/governance/MODULE_RULES.md:59-71`).

## 2. Non-goals

- No Hermes code, package, runtime, registry, scheduler, or skill system is integrated.
- No new general agent runtime, dynamic tool plugin system, user-created cron feature, provider marketplace, or channel is introduced.
- No BOSS business flow, CRM schema, Decision Hub scope, or product positioning is broadened.
- No approval bypass is created, and no existing production flag is enabled by this work.
- No “big bang” F52 or Phase 4B activation is part of this spec; those paths remain dormant pending their own rollout decision (`AI_CONTEXT.md:16-19`, `AI_CONTEXT.md:31-39`).

## 3. Design invariants

1. **Permission and availability are separate.** A role may be authorized for a tool that is not operationally available; the model must receive the tool only when both are true. Current `ToolMeta` covers permission/risk but has no availability contract (`tool_registry.py:19-28`), while `context._filter_tools()` filters only by role/name (`context.py:44-79`).
2. **Unknown or duplicate tool identity fails closed.** Current enforcement denies missing registry entries (`tool_registry.py:258-277`); registration ambiguity must be rejected with the same posture.
3. **Provider/user text is never execution truth.** `DispatcherOutcome` already requires structured `completed`, `failed`, or `outcome_unknown` and forbids inferring truth from `user_message` (`core/dispatcher_outcome.py:12-30`).
4. **No mutation success without evidence.** Existing validators already require tool-specific evidence and fail closed for write actions (`core/anti_hallucination.py:153-180`, `core/anti_hallucination.py:381-430`).
5. **Scheduler remains fixed and business-owned.** Existing jobs are statically registered in one function (`scheduler.py:792-862`); this spec adds metadata and safety, not arbitrary scheduling.
6. **Approval remains a gateway, not a tool implementation.** The repository explicitly separates gates from tools (`docs/governance/MODULE_RULES.md:59-71`).

## 4. Proposed changes

### R1 — Tool availability contract (`check_fn` equivalent)

**Exact current evidence**

- `ToolMeta` currently declares role, tenant scope, approval, emergency, risk, read-only, and description, but no runtime readiness callback/status (`tool_registry.py:19-28`).
- `context._filter_tools()` selects schemas solely by role/name (`context.py:44-79`).
- The flag registry already demonstrates a narrow structural-readiness pattern by refusing `EMAIL_INBOUND` and `ABANDONED_LEADS` when their required adapters are absent (`feature_flags.py:191-223`).

**Why it matters**

An authorized tool can still be unusable because credentials, provider configuration, feature readiness, schema, or a required adapter is missing. Exposing it invites avoidable model calls and misleading retries.

**Risk if skipped**

The model can select tools that are guaranteed to fail, creating poor UX, repeated attempts, false approval requests, and confusion between permission denial and provider unavailability.

**Minimal implementation later**

- Extend `ToolMeta` with a side-effect-free availability reference, preferably a named callable returning a small `ToolAvailability(available, code, reason)` result.
- Keep checks local/read-only: environment presence, feature readiness, required adapter registration, and optional schema/provider readiness. No network calls during context construction.
- Define default availability as `available=True` for existing tools so the first PR is behavior-preserving.
- Keep permission evaluation in `tool_registry.py`; provider-specific probes may be injected through a port, consistent with the port rule (`docs/governance/MODULE_RULES.md:44-57`).

**Tests required**

- Existing tools without a check remain available.
- Missing credential/config returns unavailable with a stable machine code.
- Availability checks never override role denial.
- A check exception fails closed for schema exposure and is logged without secrets.
- Checks are side-effect-free and do not invoke providers.

**Rollout flag**

`FEATURE_TOOL_AVAILABILITY_FILTER`, default off for schema filtering. The metadata and diagnostics may land first with no behavior change; enable shadow logging before enforcement.

### R2 — Hide unavailable tools from model schema exposure

**Exact current evidence**

- `build_context()` obtains the model-visible schemas from `_filter_tools(identity.role)` (`context.py:253-267`).
- `_filter_tools()` only intersects `TOOL_SCHEMAS` with the static role map (`context.py:44-79`).
- Enforcement still occurs at dispatch and denies unknown/unauthorized tools (`tool_registry.py:258-277`), so schema filtering is defense-in-depth rather than a replacement for permission enforcement.

**Why it matters**

The best time to prevent a guaranteed failure is before the model sees the tool. Dispatch enforcement must remain because model/schema exposure is not an authorization boundary.

**Risk if skipped**

Unavailable tools remain callable in model planning, increasing failed calls, approval noise, cost, and hallucinated recovery paths.

**Minimal implementation later**

- After role filtering, ask `tool_registry` for availability and omit unavailable tools only when `FEATURE_TOOL_AVAILABILITY_FILTER` is enabled.
- In shadow mode, expose the current schema unchanged but log `role`, tool name, availability code, and count; never log credentials.
- Add unavailable-tool summaries to a future read-only diagnostics command, not to user prompts.

**Tests required**

- Role-allowed + available appears.
- Role-allowed + unavailable is hidden only under enforce mode.
- Role-denied stays hidden in every mode.
- Shadow mode produces identical schema lists to current behavior.
- Dispatch still rejects an unavailable/unauthorized direct call even if a stale model schema contains it.

**Rollout flag**

Use the same `FEATURE_TOOL_AVAILABILITY_FILTER` with `off` / `shadow` / `enforce` semantics if practical; do not add a second overlapping flag.

### R3 — Collision-fail for duplicate tool names and registry/schema drift

**Exact current evidence**

- BOSS currently uses a dictionary literal as `_REGISTRY` (`tool_registry.py:49-233`), and schemas are maintained separately in `TOOL_SCHEMAS`, filtered by name (`context.py:77-79`).
- Missing registry tools are denied at enforcement (`tool_registry.py:258-277`).
- Derived approval/emergency sets already come from `_REGISTRY`, demonstrating the desired single-policy-source direction (`tool_registry.py:236-243`).

**Why it matters**

Python dictionary literals cannot surface a duplicate key after construction; a later duplicate silently replaces the earlier entry. Separate schema and registry inventories can also drift, leaving a schema without policy or policy without a callable schema.

**Risk if skipped**

A duplicate or drifted tool identity can silently change permission, risk, approval, or handler expectations and evade review.

**Minimal implementation later**

- Introduce a startup validation function, not a new runtime registry: parse/construct the existing entries through a duplicate-detecting helper or validate source declarations before building the final immutable mapping.
- Validate uniqueness across registry names and schema names.
- Fail application startup for duplicate names, schema-without-policy, or mutating policy-without-evidence-validator; allow explicit internal-only tools through a declared `model_exposed=False` field.
- Do not let “last registration wins.”

**Tests required**

- Duplicate registry declaration fails with both source labels.
- Duplicate schema name fails.
- model-exposed schema without policy fails.
- internal-only `tma_write`, `send_followup`, `send_recovery`, and `media_save_to_memory` remain valid when explicitly marked; their current internal-only intent is documented at `tool_registry.py:188-232`.
- Every approval/high-risk tool has an evidence validator or an explicit non-success-producing classification (`core/anti_hallucination.py:153-180`).

**Rollout flag**

No production behavior flag. Land first as a CI/startup validation in warning mode only if current drift is discovered; move to fail-fast in the same PR only when the repository is clean.

### R4 — Final response evidence footer and evidence-derived completion status

**Exact current evidence**

- The tool loop verifies each result immediately after dispatch (`app.py:2495-2519`).
- `sanitize_agent_response()` blocks action-completion language without successful write evidence (`core/anti_hallucination.py:677-700`).
- A remaining empty-text fallback says `✅ פעולה הושלמה.` even when no tool use exists in that response (`app.py:2370-2372`).
- `DispatcherOutcome` already provides structured terminal states and prohibits deriving truth from display text (`core/dispatcher_outcome.py:12-30`).

**Why it matters**

Regex sanitization is a guard, not a complete status renderer. The final user-visible response should be structurally derived from the verified outcomes accumulated during the turn, including `outcome_unknown`, rather than relying on model wording or a generic success fallback.

**Risk if skipped**

An empty or malformed final model response can still generate a success claim without evidence; mixed-result turns can hide partial failure or unknown outcomes.

**Minimal implementation later**

- Add a small `TurnEvidenceSummary` owned by the agent loop: counts of verified reads, verified writes, failed calls, unknown outcomes, queued approvals, and unverified effects.
- Finalization appends a deterministic footer only when tools/approvals occurred or when the model response is empty.
- Replace the generic empty success fallback with a neutral message such as “No final response was produced”; if verified outcomes exist, render those outcomes explicitly.
- Never expose raw record IDs, credentials, payloads, or internal tool names in customer-facing text; use business descriptions already present in approval/result composition.
- Keep `sanitize_agent_response()` as defense-in-depth.

**Tests required**

- Empty response + no tool evidence never says done/completed.
- Verified write produces a success summary.
- Failed write produces failure only.
- `outcome_unknown` is distinct and says not to retry automatically.
- Mixed success/failure reports both and never collapses to success.
- Approval queued is not reported as executed.
- Read-only evidence never supports a mutation claim.
- Footer contains no internal IDs/tool names.

**Rollout flag**

`FEATURE_EVIDENCE_FINALIZER`, default off; shadow mode compares proposed status with current final response and logs mismatches. Enforce after production samples show no regressions.

### R5 — Universal “no done claim without verified evidence” invariant

**Exact current evidence**

- The anti-hallucination principle is already “if the tool didn't confirm it, the agent didn't do it” (`core/anti_hallucination.py:1-7`).
- Write validators are explicit and fail closed when missing (`core/anti_hallucination.py:153-180`, `core/anti_hallucination.py:381-430`).
- Action Gateway explicitly says success claims require real tool evidence (`core/action_gateway.py:1331-1340`).
- Current roadmap records structured results and evidence verification as merged, but the current context also warns that newer work is not production-verified (`ROADMAP.md:265-270`; `AI_CONTEXT.md:8-10`).

**Why it matters**

The rule must cover agent text, approval callbacks, scheduler completions, recovery counters, TMA responses, and internal status transitions—not only one conversational sanitizer.

**Risk if skipped**

Different surfaces can report success from different standards. The open recovery issue already documents a counter advancing when the customer did not receive the message (`ROADMAP.md:283-287`).

**Minimal implementation later**

- Define one typed `EvidenceStatus`: `verified_success`, `verified_failure`, `outcome_unknown`, `not_executed`, `approval_pending`.
- Require every surface that emits a completion claim or terminal status to consume this typed result, not free text.
- Add a static audit test listing all calls that write `completed`/`executed` or render success, with an allowlist tied to evidence-producing functions.
- Do not change business semantics in this PR; first make inconsistent paths visible.

**Tests required**

- Static coverage test for all terminal-status writers and success renderers.
- Scheduler recovery does not increment completion state from draft/attempt evidence.
- Approval callback cannot mark complete after failed verification.
- TMA and Telegram render the same evidence status consistently.
- Unknown provider outcome remains non-retryable and non-successful.

**Rollout flag**

Reuse `FEATURE_EVIDENCE_FINALIZER` for user rendering. Canonical lifecycle enforcement in the dormant Phase 4B path remains governed by `FEATURE_ACTION_CONTRACT_PERSISTENCE` and `FEATURE_ATOMIC_CLAIMS`; do not add another action-lifecycle flag.

### R6 — No-progress guard for repeated failed or identical tool attempts

**Exact current evidence**

- The agent loop caps tool turns at three (`app.py:73`, `app.py:2374-2381`).
- Same-turn read-only calls are deduplicated by `(tool_name, sorted inputs)` and reuse the cached result (`app.py:2495-2511`).
- There is no current per-turn classification of repeated identical failures or identical no-progress results before the global turn cap.

**Why it matters**

A hard iteration cap limits cost but does not explain or prevent repeated identical calls. A deterministic guard can stop retries earlier and give the model a precise recovery instruction.

**Risk if skipped**

The agent wastes turns and provider calls, repeats user-visible failures, and may create multiple approval attempts for semantically identical requests.

**Minimal implementation later**

- Add per-turn signatures for tool name + canonicalized inputs + classified result.
- After one identical failure, allow one retry only if inputs/strategy change; block the next identical attempt with a synthetic tool result stating the prior failure and asking for a different strategy.
- For read-only tools, detect identical successful output already covered by cache; do not re-dispatch.
- Mutating calls must continue through business fingerprint/idempotency controls (`core/action_gateway.py:598-718`), not a separate mutation cache.
- Reset all guard state at turn end.

**Tests required**

- Identical failure is allowed once and then blocked before dispatch.
- Changed arguments are not blocked.
- Read-only duplicate uses the current cache.
- Mutating duplicate still follows Action Gateway fingerprint rules.
- Approval-pending and `outcome_unknown` are never auto-retried.
- Guard cannot leak state between users/turns.

**Rollout flag**

`FEATURE_TOOL_NO_PROGRESS_GUARD`, default off; start with warnings, then enforce after log review.

### R7 — Scheduler provider/model pinning

**Exact current evidence**

- Interactive model selection is hard-coded by role and owner prefix (`context.py:159-171`).
- Scheduler configuration currently reads times/intervals only (`scheduler.py:803-819`) and registers callables without provider/model metadata (`scheduler.py:821-847`).
- Some jobs invoke AI-dependent downstream systems, while current project context identifies cost watchdog and learning/digest automation as runtime concerns (`AI_CONTEXT.md:27-35`).

**Why it matters**

Unattended work should not silently inherit a future provider/model default change, especially where cost, tool capability, or structured output behavior differs.

**Risk if skipped**

A future provider/model refactor can change scheduler cost or behavior without changing scheduler code, and failures may be discovered only after unattended execution.

**Minimal implementation later**

- Add a metadata-only `ScheduledJobPolicy` map adjacent to existing registrations: job name, `uses_ai`, pinned provider/model/profile, expected tool capability, mutation class, and delivery target class.
- Initially validate only that every `uses_ai=True` job declares a pin; do not change how jobs execute.
- In a later PR, pass the pin through existing model/provider call sites. If the configured global provider differs from the recorded pin, skip the AI call and report a deterministic configuration error.
- Do not introduce a new provider runtime; use the existing Anthropic model identifiers until the planned provider port exists (`ROADMAP.md:255-257`).

**Tests required**

- Every registered job appears exactly once in the policy map.
- AI jobs require a pin; non-AI jobs do not.
- Pin mismatch fails closed before an inference call.
- Missing credential produces unavailable, not fallback to another provider.
- Job policy output redacts credentials.

**Rollout flag**

`FEATURE_SCHEDULER_PROVIDER_PIN_ENFORCEMENT`, default off. Metadata validation can run in CI without a flag; runtime enforcement starts in shadow.

### R8 — Non-recursive scheduling and atomic scheduler-owned state writes

**Exact current evidence**

- BOSS currently has no agent-facing cron creation tool; jobs are statically registered in `start_scheduler()` (`scheduler.py:792-862`).
- Duplicate scheduler startup is guarded by existing registered jobs/thread lookup (`scheduler.py:792-801`).
- Scheduler-owned security-review state is written directly with `open(..., "w")` + `json.dump`, so interruption can truncate it (`scheduler.py:240-248`).

**Why it matters**

The current static scheduler already satisfies the product-scope requirement better than a dynamic scheduler. That invariant should be tested. Separately, scheduler-owned state files should not become corrupt during process interruption.

**Risk if skipped**

A future tool could accidentally expose scheduler mutation or allow a job to create jobs recursively. Direct state writes can leave invalid JSON and silently reset operational reminders.

**Minimal implementation later**

- Add a structural test that no model-exposed tool creates/edits/removes scheduler jobs and no scheduled job calls `start_scheduler()` or registration APIs.
- Add a scheduler execution-context marker; if a future scheduler-management function is ever added, it must reject calls from this context by default.
- Replace direct scheduler-owned JSON writes with same-directory temporary file + flush/fsync + atomic replace, preserving current file format and path.
- Scope atomic writes only to existing scheduler state (starting with security-review state); do not create a new mutable job store.

**Tests required**

- No model schema exposes scheduler mutation.
- Job execution cannot register another job.
- Repeated `start_scheduler()` remains idempotent.
- Simulated interruption before replace preserves the old valid file.
- Successful write yields valid JSON and correct permissions.
- Concurrent writes serialize or deterministically choose the last complete write; no partial JSON is observable.

**Rollout flag**

No flag for structural non-recursion or atomic file replacement. These are compatibility-preserving safety properties.

### R9 — Approval boundary hardening

**Exact current evidence**

- Registry policy says whether approval is required (`tool_registry.py:19-28`, `tool_registry.py:236-243`).
- `propose_action()` cross-checks caller-supplied approval policy against the registry and upgrades to approval fail-closed (`core/action_gateway.py:657-733`).
- Proposal identity/payload are normalized, fingerprinted, and durably checked before creation (`core/action_gateway.py:674-780`).
- When atomic claims are enabled, provider dispatch requires a claim and frozen identity; missing identity fails closed (`core/action_gateway.py:1331-1421`).
- The production context still identifies legacy Airtable Approvals as authoritative and Phase 4B/F52 as dormant/planning (`AI_CONTEXT.md:27-34`).

**Why it matters**

The strongest code path is not yet the verified production authority. Hardening must prevent new callers from bypassing registry policy today while preserving the staged migration path.

**Risk if skipped**

Internal callers, channel callbacks, TMA routes, scheduler jobs, or new adapters can mutate providers directly, creating inconsistent authorization, identity, idempotency, and evidence semantics.

**Minimal implementation later**

- Add a static caller audit: every call to a mutating dispatcher/provider must originate from an approved gateway/executor adapter or an explicitly documented owner-direct path.
- Validate at startup/CI that every `requires_approval` tool has: registry policy, schema/internal-only classification, Action Gateway adapter, evidence validator, and a tested execution boundary.
- Add an immutable `trusted_source` allowlist owned by Action Gateway; current code already requires trusted source to be an explicit Python argument rather than tool input (`core/action_gateway.py:643-647`).
- Preserve legacy production behavior while flags are off; do not activate Phase 4B in this PR series.
- Keep requester identity frozen and approver authority checked at action time; no channel payload may become executable authority.

**Tests required**

- Direct dispatch bypass test for every approval-required tool.
- Caller cannot lower `requires_approval`.
- Untrusted tool input cannot set `trusted_source`.
- Requester/approver/tenant mismatch fails closed.
- Stale, duplicate, concurrent, and forged approval inputs cause at most one provider execution.
- Missing evidence cannot persist `completed`.
- Flag-off legacy behavior is unchanged; flag-on dormant path passes existing Phase 4B suites.

**Rollout flag**

No new approval flag. Static/CI hardening is unconditional. Runtime authority changes remain behind existing `FEATURE_ACTION_GATEWAY`, `FEATURE_ACTION_CONTRACT_PERSISTENCE`, and `FEATURE_ATOMIC_CLAIMS` (`feature_flags.py:47-51`).

## 5. Proposed interfaces (illustrative contracts, not code)

These shapes describe responsibilities only and must not be copied from Hermes:

```text
ToolAvailability:
  available: bool
  code: stable machine-readable reason
  detail: redacted operator-facing explanation

TurnEvidenceSummary:
  verified_successes: business descriptions
  verified_failures: business descriptions + stable reason
  outcome_unknown: business descriptions
  approvals_pending: business descriptions
  had_unverified_effect: bool

ScheduledJobPolicy:
  name
  uses_ai
  pinned_provider
  pinned_model
  mutation_class
  delivery_class
```

`ToolAvailability` is policy/readiness metadata, not a provider action. `TurnEvidenceSummary` is a projection of existing verified results, not a new source of execution truth. `ScheduledJobPolicy` describes existing fixed jobs and does not create a scheduler runtime.

## 6. Small-PR delivery plan

Each PR must be independently reviewable and behavior-preserving unless its rollout flag is explicitly enabled.

| PR | Scope | Runtime behavior at merge | Required proof |
|---|---|---|---|
| PR-RP0 | Add these two planning documents to the repository and refresh canonical status/date in a dedicated docs branch | None | Link/line audit; no code diff |
| PR-RP1 | Registry/schema invariant validator and duplicate collision failure | CI/startup validation only; no tool filtering | Full registry/schema inventory tests; internal-only exceptions explicit |
| PR-RP2 | `ToolAvailability` metadata + diagnostics in shadow | No schema change while flag off | Availability unit tests; no provider calls; redaction test |
| PR-RP3 | Enforce unavailable-tool hiding behind `FEATURE_TOOL_AVAILABILITY_FILTER` | Current behavior with flag off | Role × availability matrix and direct-dispatch denial tests |
| PR-RP4 | Turn evidence accumulator and shadow finalizer | Logs comparison only | Empty response, mixed outcome, approval-pending, unknown-outcome tests |
| PR-RP5 | Evidence finalizer enforcement; remove generic unsupported success fallback | Flag-off unchanged; controlled canary when enabled | End-to-end Telegram/Twilio response tests and no-ID leakage tests |
| PR-RP6 | No-progress guard behind flag | Warning/shadow first | Identical failure/no-progress, changed strategy, user isolation tests |
| PR-RP7 | Scheduler policy inventory and structural tests for provider pins, emergency wrapper, and non-recursion | No runtime change | Every registered job mapped/wrapped exactly once |
| PR-RP8 | Atomic replacement for existing scheduler-owned security-review state | Compatible file format/path | Crash/interruption/concurrency/permissions tests |
| PR-RP9 | Scheduler provider-pin enforcement behind flag | Off by default; shadow before enforce | No-inference-on-mismatch and credential-unavailable tests |
| PR-RP10 | Approval caller/invariant audit only | No flag activation; legacy production behavior unchanged | Full approval-required tool matrix and bypass tests |

Do not combine PR-RP3, PR-RP5, PR-RP6, PR-RP9, or any Phase 4B activation. Each changes a separate control boundary and needs independent rollback.

## 7. Rollout and acceptance gates

1. **Docs/current-state gate:** production map records observed env values and deployment revision; code defaults are not accepted as production proof (`AI_CONTEXT.md:8-10`).
2. **CI gate:** registry/schema/approval/scheduler structural matrices are complete.
3. **Shadow gate:** availability, finalizer, no-progress, and scheduler pinning run in observation mode with no user-visible changes.
4. **Canary gate:** enable one behavior flag at a time for owner traffic only, with before/after evidence.
5. **Truth gate:** no success status is accepted without the tool-specific verifier or canonical provider outcome.
6. **Rollback gate:** disabling the one feature flag restores the immediately previous behavior without data migration.
7. **Production verification gate:** report “implemented but not yet verified” until deployment revision, live flow, and evidence receipt are confirmed; the current context already applies this distinction to recent merged work (`AI_CONTEXT.md:16-23`, `AI_CONTEXT.md:45-54`).

## 8. Final recommendation

Proceed in this order: registry collision/invariant validation, availability shadowing, evidence-finalizer shadowing, no-progress shadowing, scheduler inventory/atomic state, then approval caller audit. Only after those land should any individual enforcement flag be canaried. Do not activate dormant Phase 4B or Decision Hub as part of this work (`AI_CONTEXT.md:31-39`).

The highest-value first runtime change is removing the unsupported generic completion fallback and replacing it with evidence-derived finalization, but it should land only after the shadow accumulator proves how current turns are classified (`app.py:2370-2372`, `app.py:2495-2519`). The highest-value permission change is registry/schema collision and completeness validation because it can land without changing production behavior (`tool_registry.py:236-277`, `context.py:77-79`).
