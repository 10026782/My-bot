# Phase 4C — Migration Options

Baseline: `origin/main` `4d3787e6e6fcbc93bd5a30f62f0834136b706f06`. Final sequencing must be reconfirmed after Phase 4B rollout/cutover verification. The recommendation reuses ActionGateway, PostgreSQL claims and the dispatcher; it does not create a second runtime.

## Option comparison

| Dimension | A — big-bang replacement | B — channel-by-channel | C — tool/policy-class incremental |
|---|---|---|---|
| Core idea | Replace EB, callbacks, direct handlers and flags in one cutover | Finish Telegram, then WhatsApp, TMA, background/media | Close execution boundary and migrate coherent action classes behind narrow flags |
| Risk | Critical: too many coupled UX/provider paths | High: a tool remains bypassable through another channel/caller | Medium: shared boundary first, then bounded cohorts |
| Code churn | XL in one review | L per channel; duplicates adapter work | S/M focused PRs, cumulative L/XL |
| Observability | Weak during a single large switch | Good by channel, weak across shared tools | Best: compare old/new path per policy class |
| Rollback | All-or-nothing and likely restores fallback | Channel rollback can still expose shared direct dispatcher | Per cohort; rollback presentation without reopening dispatcher bypass |
| Compatibility | Highest regression surface | Preserves untouched channels | Preserves unrelated channels/tools while invariant boundary is strengthened |
| Duplicate risk | High during dual-runtime cutover | Same tool may have old/new authorities concurrently | One execution proof rule, then one cohort at a time |
| Duration | Short calendar, long stabilization | Medium/long | Medium, with useful safe milestones |
| Testing | Massive end-to-end matrix before first value | Repeats provider cases per channel | Shared boundary suite plus adapter-specific suites |
| Telegram impact | Large simultaneous rewrite | Direct and concentrated | First cohort targets its proven P0 paths |
| WhatsApp readiness | Delayed until whole rewrite | Native adapter arrives after Telegram | Runtime becomes channel-neutral before WhatsApp UX |
| EventBus | Temptation to delete globally | Can remain per channel | Downgrade individual uses to projection/notification |

## Recommendation: Option C, boundary-first tool/policy cohorts

Repository evidence favors Option C. ActionGateway already supplies durable proposal/recovery, policy authorization, frozen requester identity, lifecycle persistence, atomic execution and evidence classification. TMA demonstrates the desired adapter boundary. The missing global property is that ten approval-required dispatcher tools still accept ordinary authorized calls, and Telegram buttons reference EB IDs with a direct fallback.

“Tool-by-tool” should not mean eleven bespoke runtimes. Phase 4C-1 should migrate the shared **agent-exposed approval class** as one cohort because all seven agent-facing approval tools enter through the same `run_agent()`/callback code. The dispatcher proof boundary should cover all approval-required tools at once, with an explicit trusted gateway execution token/context. Internal tool presenters can then migrate without reopening a direct path.

Recommended order differs slightly from the candidate sequence: move the Telegram approval adapter into 4C-1 rather than leaving unsafe buttons until 4C-2. Free-text/numbered/reconfirmation cleanup can remain 4C-2.

## Proposed phases

### Phase 4C-0 — governance, invariant tests and observability

- Scope: freeze new approval mechanisms; publish one generated inventory of Tool Registry approval metadata and TMA policy exceptions; add non-payload diagnostics for attempted direct dispatch; define supported flag combinations and migration metrics.
- Likely files: governance docs/tests, `tool_registry.py`, dispatcher diagnostics only, feature-flag documentation. Do not alter provider behavior.
- Prerequisite: Phase 4B rollout/cutover verified and exact deployed flags recorded.
- Out of scope: channel behavior, provider adapters, EventBus deletion.
- Compatibility/flag: passive diagnostics under a default-off diagnostics flag if volume/sensitivity requires it.
- Rollback: remove diagnostics; no authority change.
- Tests: registry/schema parity, policy inventory snapshot, no personal payload logging.
- DoD: every approval-required tool and direct caller has an owner/migration phase; invariants executable.
- Effort/risk: **S / Low**.

### Phase 4C-1 — Telegram agent tools and immutable callback contract IDs

- Scope: all seven agent-exposed approval-required tools create/reuse durable ACs; Telegram presentation carries immutable AC ID (or a signed opaque presentation reference resolving only to it); approve/reject re-read that AC and call gateway; missing/unavailable AC fails closed; remove callback direct-dispatch/manual lifecycle path; enforce gateway execution proof at dispatcher for every approval-required tool.
- Likely files: `app.py`, `tools/dispatcher.py`, `tool_registry.py`, `core/action_gateway.py` (execution proof interface only), callback/registry/atomic tests. EventBus may still deliver UI but cannot own pending/authority.
- Prerequisites: persistence and atomic claims enabled/healthy for the cohort; Phase 4B lifecycle verified; maximum Telegram callback length/design settled.
- Out of scope: free-text UX redesign, WhatsApp, media edit/files, scheduler, TMA route behavior, lifecycle redesign.
- Compatibility/flag: a cohort flag default-off; shadow can create/compare presentation references but must never create a second executable authority. Enabling requires persistence+claims; mismatches fail closed.
- Rollback: revert UI to read-only/manual retry; **must not** restore direct dispatch. Keep contracts pending.
- Tests: full required matrix in risk report, all seven tools, reject, unrelated callbacks, real PostgreSQL opt-in.
- DoD: no agent approval callback or internal direct call can execute a registry approval tool without AC authorization and acquired PG claim; one provider write under duplicate/concurrent clicks.
- Effort/risk: **L / High**.

### Phase 4C-2 — Telegram text/selection adapters and EB authority removal

- Scope: free-text yes/no, combined ordinal, numbered selection, cancellation, reconfirmation and multiple pending all resolve durable ACs; make candidate ordering durable or reconstructible; retire `_pending_approvals` as “approval” authority; reject always persists canonical rejection. Downgrade EB uses individually to projection/notification.
- Likely files: `app.py`, `core/action_gateway.py`, `event_bus.py`, presentation adapter module, Telegram regression tests.
- Prerequisite: 4C-1 immutable references and fail-closed dispatcher.
- Out of scope: WhatsApp UX and non-tool mutations.
- Compatibility/flag: parser adapter flag; old buttons can be rendered stale/read-only, not executed through fallback.
- Rollback: return explicit “re-open action” instructions; retain canonical contracts.
- Tests: restart with multiple contracts, stale ordinals, one-shot reconfirmation, forged text/callback, unrelated callback families.
- DoD: all Telegram approval language is presentation over AC; EB restart cannot lose authority or enable execution.
- Effort/risk: **M / Medium**.

### Phase 4C-3 — WhatsApp presentation/reply adapter

- Scope: use the same AC runtime for Twilio and later Meta; create channel-specific prompt/reply parser; map signed sender and destination number to canonical identity/tenant/domain; store presentation references needed for restart and stale-reply validation.
- Likely files: `app.py` or extracted WhatsApp adapters, `identity.py`, tenant/domain configuration, presentation repository, webhook tests.
- Prerequisite: decisions on number→tenant/domain mapping and reply correlation; 4C-1/2 adapter interface stable.
- Out of scope: Meta provider send unless separately production-ready; media/file actions.
- Compatibility/flag: provider-specific default-off flags. Text mutation disabled when no outbound/reply adapter exists.
- Rollback: read-only WhatsApp or explicit unsupported response; pending AC remains manageable in another authorized channel only if policy allows cross-channel presentation.
- Tests: signatures, replay IDs, forged sender, cross-number/domain, restart, duplicate reply, channel crossover, outbound delivery failure.
- DoD: WhatsApp changes UX only; authorization, claim, dispatcher and lifecycle match Telegram/TMA.
- Effort/risk: **L / High**.

### Phase 4C-4 — non-tool and media mutations

- Scope: voice edit replacement contracts; Drive+Media Files typed handler/evidence; TMA assets/ventures/game commands; `/done`, Decision Hub and Business Memory actions. Register as tools where dispatcher semantics fit; otherwise typed deterministic handlers executed by ActionGateway.
- Likely files: `media_handler.py`, `tools/approval_actions.py`, dispatcher/registry, `tma_api.py`, command modules, evidence verifier.
- Prerequisite: typed-handler interface and explicit upload/self-confirm policy.
- Out of scope: broad scheduler delegation.
- Compatibility/flag: one flag per coherent action class, default-off; legacy path can become read-only but not fallback-executable.
- Rollback: stop new proposals; retain/reconcile provider outcomes, never auto-retry `outcome_unknown`.
- Tests: multi-provider partial outcome, replacement/supersession, idempotency, receipt failure, forged handler name/context.
- DoD: each business mutation has deterministic frozen inputs, handler, claim and evidence; selections/edits are not authority.
- Effort/risk: **XL / High**.

### Phase 4C-5 — scheduler/background policy classes

- Scope: classify every registered job; keep read/notification outside runtime; formalize bounded lead-memory/audit/usage persistence; create ACs for interaction/abandoned Tasks and other business mutations; define minimal system principal and delegation.
- Likely files: `scheduler.py`, `interaction_engine.py`, `abandoned_lead_worker.py`, `lead_memory.py`, policy/identity modules, job tests.
- Prerequisite: owner decision on bounded pre-authorization and canonical system identity.
- Out of scope: generic unlimited “automation approval.”
- Compatibility/flag: existing job flags plus policy-version gate. On policy/config uncertainty, skip mutation and alert.
- Rollback: disable affected job; do not replay old pending/system actions automatically.
- Tests: schedule overlap, restart, duplicate job run, tenant scope, expired delegation, provider ambiguity, rate limit.
- DoD: every mutation job is either an explicit AC or documented bounded policy; no “unknown/unsafe” jobs remain enabled.
- Effort/risk: **L / High**.

### Phase 4C-6 — legacy retirement

- Scope: remove proven-unused execution authority, duplicate RAM pending maps and hardcoded risk lists; freeze/drain legacy EB/AP records; correct stale docs. Keep EventBus where it provides notifications/observability.
- Likely files: `event_bus.py`, `app.py`, `tma_api.py`, projection/docs/tests.
- Prerequisite: production metrics show no legacy callers for a full agreed window; migration flags stable.
- Out of scope: deletion based only on static search.
- Compatibility/flag: tombstone/read-only period before deletion.
- Rollback: restore presentation readers only; never legacy execution.
- Tests: caller scan, old callback/record handling, no subscriber remains, rollback does not dispatch.
- DoD: one authorization/runtime authority; no execution payload in projection/UI/CONTEXT_DATA; legacy remains read-only or expired.
- Effort/risk: **M / Medium**.

## Rollback boundaries

1. Rollback may disable proposal presentation or route users to a safe manual process.
2. Rollback may not re-enable callback direct dispatch, flag-off atomic execution for approval-required tools, or UI-payload execution.
3. Existing pending ACs remain authoritative; adapters can be rolled forward to recover them.
4. Provider success with missing receipt/lifecycle is classified and reconciled; it is never blindly retried.
5. `outcome_unknown` is terminal for automatic execution.

## Component disposition

| Component | Destination | Proof required before deletion |
|---|---|---|
| ActionGateway/AC repository/PG claims | Retain and extend | N/A, target core |
| Dispatcher | Retain; enforce approval execution proof | direct-call tests for all approval tools |
| Airtable Approvals | Retain as TMA display projection only | no execution fields/readers |
| EventBus | Adapt/downgrade per event | zero approval/execution-authority callers; notification subscribers inventoried |
| EB pending store | Freeze/deprecate as authority | all buttons/replies resolve durable contract refs |
| `app._pending_approvals` | Reclassify plan confirmation, then deprecate if unused | router behavior tests and no callers |
| callback direct execution/manual lifecycle | Delete in 4C-1 | fail-closed callback tests and unrelated callback regression |
| TMA `ACTION_RISK` | Adapt to canonical policy | bulk behavior parity tests |
| legacy AP `CONTEXT_DATA` | Keep blank/read-only then retire | static/runtime diagnostics show zero readers as execution source |
| channel parsers | Retain as presentation adapters | authorization remains gateway-only |

## Why not channel-first

Telegram is the immediate exposure, but channel-only migration would leave `dispatch_tool()` callable without approval proof and would require repeating that closure for WhatsApp and background callers. Closing the shared boundary while migrating the Telegram agent cohort makes later adapters smaller and prevents a new caller from recreating the bypass.
