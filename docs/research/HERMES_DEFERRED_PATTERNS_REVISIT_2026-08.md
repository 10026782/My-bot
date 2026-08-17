# BOSS — Hermes Deferred Patterns Revisit Audit — 2026-08

> This document is a design/audit reference. It is not a BOSS implementation or runtime source of truth.

Audit base: `origin/main` at `84249b119c1901a44f1f96ad931fb2aaeeb506df`, fetched 2026-08-18.

Scope is audit-only. Hermes remains a reference architecture. No Hermes runtime, MCP, Ollama, migration, schema, dependency, or production-behavior change is proposed here.

## Evidence boundary

`HERMES_AGENT_AUDIT.md` is not present in `origin/main`; it is therefore not used as current BOSS evidence. The four approved research documents were read from the base tree. Current conclusions below come from direct inspection of `origin/main` code and focused repository tests. Code defaults, shadow flags, and historical documents do not prove deployment or runtime activation.

Primary evidence inspected:

- `app.py`, `tma_api.py`, `core/ingress_envelope.py`, `core/telegram_ingress_adapter.py`, `core/whatsapp_ingress_adapter.py`, `core/output_gateway.py`, `providers/interfaces.py`, `providers/anthropic_shim.py`
- `tool_registry.py`, `context.py`, `tools/dispatcher.py`, `feature_flags.py`
- `memory_store.py`, `session_store.py`, `core/action_gateway.py`, `core/turn_state_repository.py`
- `scheduler.py`, `core/atomic_claims_health.py`, `tma_api.py` health endpoints
- `docs/research/BOSS_OPEN_SOURCE_INFRA_AUDIT_2026-08.md` and the three approved indexes

Focused checks used: `test_tool_registry_invariants.py`, `test_tool_availability_shadow.py`, ingress/envelope tests, ActionGateway/authority tests, provider-interface inspection, scheduler/health source inspection, and a repository search for arbitrary shell/code execution and direct mutation paths.

## Nine-pattern matrix

| Hermes Pattern | Current BOSS State | Evidence | Gap | Adopt Now? | Priority |
| --- | --- | --- | --- | --- | --- |
| Channel Adapter | Partial ingress and outbound boundaries | `IngressEnvelope`; Telegram/WhatsApp adapters; `OutputGateway`; TMA routes | No complete canonical `ChannelEvent → DeliveryRequest/Result` contract or adapter conformance suite; channel handling remains partly in `app.py` | DESIGN ONLY | P1 |
| Tool Availability | Authorization and read-only availability checks exist | `ToolMeta`, `ToolAvailability`, `get_availability()`, role filtering, env checks | Availability is not the full enabled/configured/authorized/healthy/tenant-ready model; model exposure is primarily registry/schema based, so an authorized-but-unavailable tool can remain visible | DESIGN ONLY | P1 |
| boss doctor | Read-only health/status surfaces already exist | `/api/health`, `/api/owner/health`, capability-map/control-center, atomic-claims health and predeploy checks | No one redacted aggregator covering all requested providers, Postgres, Airtable schema, approvals, scheduler, webhook, delivery, ActionGateway, and workers | YES — SMALL SLICE | P2 |
| Provider Port | Protocol/shim exist but active path is coupled | `LLMProvider` and `AnthropicLLMProvider`; direct SDK paths in `app.py`/`llm_fallback.py` | Missing provider-neutral tool, structured-output, timeout/retry/error, streaming, capability, and cost conformance contract | DESIGN ONLY | P1 |
| Compact Memory | Storage and bounded process context are split | `MemoryStore`; `PersistentSessionStore`; Airtable business memory; Postgres operational repositories | Missing retrieval/context-selection policy with tenant/entity scope, provenance, conflict/correction handling, retention, and context budget | DESIGN ONLY | P1 |
| Scheduler Safety | Fixed jobs, automation guard, and some durable leases exist | `scheduler.py`; `EMERGENCY_STOP_AUTOMATION`; external poll leases; atomic claims | No universal provider pinning, fresh-context rule, deterministic retry/idempotency contract, or unified visible failure state | DESIGN ONLY | P2 |
| Skills/Playbooks | No canonical runtime skill loader | Existing prompts, routing, templates, and workflow code | A human-authored, versioned, read-only, tenant-scoped, auditable playbook format could guide reasoning without authority | DESIGN ONLY | P3 |
| Sandbox | No general arbitrary shell/Python/code tool exposed to BOSS | Registry/schema and dispatcher inventory; repository search found no general model-facing execution surface | No current sandbox requirement; isolated converter/provider subprocesses are bounded implementation details, not a general BOSS capability | NO | — |
| Approval/Authority | ActionContracts → authorization/approval → ActionGateway remains canonical | `core/action_gateway.py`, `tool_registry.py`, dispatcher, evidence/result paths, ingress gates | Multiple legacy approval projections/fallback stores remain operationally complex, but no new direct model/tool/provider mutation bypass was found | ALREADY COVERED | P0 governance |

### Direct answers

Pattern 1 verdict: `PARTIAL — GAP FIRST`. A small future contract should contain canonical inbound identity/tenant, event id, channel/provider, text/media references, reply/thread context, capabilities, and an outbound delivery result with provider message id, status, error class, and evidence reference. It must not own routing or approval.

Pattern 2 verdict: `ARCHITECTURE GAP FIRST`. BOSS distinguishes role authorization from local availability for some tools, but not from provider health, tenant readiness, or feature state as one contract. Yes: the model can currently see a tool that is authorized by role but unavailable, because schema exposure and availability evaluation are not the same boundary.

Pattern 3 verdict: `READY FOR IMPLEMENTATION`. Phase 1 should be a read-only owner/operator command or internal diagnostic function that aggregates redacted feature/config presence, registry availability, existing health checks, scheduler liveness, ActionGateway readiness, and known degraded flags. It must not repair, mutate, print secret values, or claim production state.

Pattern 4 verdict: `CONFORMANCE TESTS FIRST`. A second provider cannot be added safely by implementing the current protocol alone. The contract must normalize structured output, tool-call request, tool-result continuation, timeout, provider failure, malformed response, retry semantics, streaming behavior, model identity, token/cost accounting, capability requirements, evidence metadata, and latency telemetry.

Pattern 5 verdict: `READY FOR MEMORY DESIGN`. Render Postgres is sufficient as a storage substrate; the missing layer is retrieval/context selection. Business memory, episodic/session memory, and compact prompt context should remain separate projections with explicit provenance and tenant boundaries.

Pattern 6 verdict: `READY FOR HARDENING`. Existing fixed jobs and guards are useful, but safety semantics are not uniform enough to adopt Hermes scheduling patterns wholesale.

Pattern 7 verdict: `READ-ONLY PLAYBOOKS MAY HELP`. Playbooks may supply human-authored reasoning guidance only; they must never become executable skills or gain execution authority.

Pattern 8 verdict: `OUT OF CURRENT SCOPE`. No general shell, terminal, arbitrary Python, or arbitrary code execution capability is exposed by the current BOSS tool surface.

Pattern 9 verdict: `ALREADY COVERED`. The authority chain remains the governing architecture. Any future adapter must enter through identity/tenant/risk policy, ActionContract, approval where required, ActionGateway, execution, and evidence.

## Top three justified learnings

### 1. Memory retrieval/context architecture — design only

Why now: Postgres and durable business/session stores already exist, while prompt context and process-local conversation memory remain incomplete and restart-unsafe.

Minimal slice: define the retrieval policy and a bounded prompt projection; do not add schema or migrate Airtable in this audit.

Prerequisites: tenant/entity scope, provenance/evidence model, retention policy, conflict/correction rules, and a hard context budget.

Likely files: a future design document plus the existing memory/session/context and Postgres repository boundaries.

Tests required: tenant isolation, deterministic ranking, stale/conflicting fact handling, correction precedence, retention, and context-budget bounds.

Governance risk: retrieval can leak cross-tenant or low-confidence facts and can be mistaken for business-memory authority.

Non-goals: Supabase, vector search by default, raw prompt-history replay, business-schema migration, or replacing Airtable-owned business memory.

### 2. ToolAvailability / capability registry — design and shadow contract

Why now: registry authorization and basic env checks exist, but model exposure can precede actual readiness.

Minimal slice: specify a redacted read-only availability projection with `enabled`, `configured`, `authorized`, `healthy`, `tenant_ready`, and stable `reason`; keep registry policy and ActionGateway authority unchanged.

Prerequisites: explicit ownership of feature state, provider readiness, tenant readiness, and fail-closed unavailable behavior.

Likely files: `tool_registry.py`, `context.py`, `tools/schemas.py`, dispatcher boundary, and focused registry tests.

Tests required: authorized/unavailable visibility, unauthorized behavior, missing credentials, unhealthy provider, tenant mismatch, redaction, and schema/registry invariants.

Governance risk: availability must never imply authorization or execution permission.

Non-goals: MCP discovery, provider mutation, credential probing that leaks secrets, or changing current tool policy in this audit.

### 3. Read-only `boss doctor` slice — implementation candidate

Why now: several safe checks already exist, but operators must consult multiple surfaces.

Minimal slice: aggregate existing redacted checks for flags/config presence, registry readiness, Airtable/Telegram checks, scheduler liveness, and ActionGateway/claim readiness; return explicit `ok/degraded/unknown` states.

Prerequisites: the ToolAvailability contract above and a clear distinction between repository capability and live production evidence.

Likely files: a small diagnostic module/CLI and focused tests; reuse existing health/readiness helpers.

Tests required: no secret output, no mutation, provider timeout/degraded states, missing env, unknown checks, and deterministic exit/status mapping.

Governance risk: a doctor result must not be labeled deployed, runtime-verified, or healthy without environment-specific evidence.

Non-goals: auto-repair, migrations, webhook changes, scheduler writes, or deployment orchestration.

## Sequencing

1. Define ToolAvailability/capability semantics.
2. Define Memory Architecture/Retrieval independently, using existing Render Postgres as storage and preserving Airtable ownership.
3. Build the smallest read-only `boss doctor` slice after the availability semantics are stable.
4. Define provider conformance tests; do not switch the active provider.
5. Harden scheduler safety where a concrete failure mode is evidenced.
6. Define a small Channel Adapter contract after ingress/delivery field ownership is agreed.
7. Revisit MCP only after capability discovery, tenant credentials, approval classification, timeout/retry/idempotency, revocation, schema pinning, injection defenses, and normalized evidence are defined.

This is not a mandate to build every item. The only single next implementation slice justified by this audit is: **a read-only ToolAvailability contract plus focused tests, without changing model exposure or execution policy**. `boss doctor` follows as the next small slice only after that contract is accepted.

## MCP prerequisite conclusion

ToolAvailability is one prerequisite, not the whole MCP prerequisite. Before an MCP spike, BOSS needs at most these five gates:

1. governed adapter boundary behind ActionGateway;
2. tenant identity, credential ownership, revocation, and server trust policy;
3. capability/schema/version contract with unavailable-server behavior;
4. approval, timeout, retry, idempotency, and emergency-stop classification;
5. normalized result/evidence and prompt/tool-injection defenses.

No MCP client or server should be built before those gates are explicit.

## Money Printer / Hermes memory conclusion

Hermes can inform bounded episodic retrieval, relevance/recency ranking, provenance, correction handling, and compact context projection. Do not copy an undifferentiated transcript/vector memory or let retrieved text become authority. BOSS-specific requirements are tenant isolation, business-domain ownership, ActionContract/evidence linkage, retention, user corrections, and a strict prompt budget. Render Postgres remains the selected storage substrate; this audit does not propose Supabase or a schema.

## Provider conclusion

The provider port is not ready for a second provider. The existing `LLMProvider`/Anthropic shim is a useful seam, but active callers and tool schemas remain provider-shaped. The correct next step is conformance tests and a normalized request/result/error contract, with no Ollama integration and no business-policy change.

## boss doctor conclusion

Feasible as a small, read-only implementation because health endpoints, capability data, feature flags, registry availability, scheduler state, and claim/readiness checks already exist. It should aggregate and redact; it must not repair or make deployment/runtime claims.

## Still deferred

Hermes runtime integration, MCP, Ollama, Supabase migration, arbitrary executable skills, general sandboxing, free-form user cron, provider switch-over, schema/memory migration, and any production behavior change remain deferred.

## Final status

Files changed: this document only.

No production code, schema, migration, dependency, ROADMAP, or approved index was changed.
