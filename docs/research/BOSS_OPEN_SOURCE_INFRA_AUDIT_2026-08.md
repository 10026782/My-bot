# BOSS Open-Source / Memory / Infrastructure Audit — 2026-08

> This is a research/procurement catalog, not a BOSS source of truth for implementation or runtime status.

Audit base: `origin/main` at `2369b4cee29db40dce00d03db9fb0e50cb2e4290` (fetched 2026-08-18).
Evidence labels: `MERGED` means present in that tree; `WIRED` means a current call site exists; `DEPLOYED` and `RUNTIME VERIFIED` are not inferred from code or historical prose.

## A. Executive Summary

1. BOSS already has governed execution through ActionContract → authorization/approval → ActionGateway → dispatcher/provider → result/evidence.
2. MCP has no clean ready-made slot today; an adapter would be safe only behind ActionGateway and identity/tenant policy.
3. Render Postgres is already used for atomic execution claims, durable turn state, polling leases, and usage events.
4. ActionContracts, business/session records, and external job state remain Airtable-owned by current code.
5. Conversation memory and action-resolution context are explicitly process-local and restart-unsafe.
6. Some approval/queue fallbacks are also RAM-only, even though ActionContracts is the lifecycle authority.
7. Therefore the main memory gap is architecture/retrieval, not the absence of a database engine.
8. At the supplied $14/month total, no evidence justifies moving Render Postgres to Supabase.
9. Supabase adds Auth/RLS/Realtime/Storage/vector tooling, but those are not current requirements shown by main.
10. The existing LLM provider protocol is useful but not wired into the main Anthropic/OpenAI call paths.
11. Ollama is therefore a future provider-port exercise, not a drop-in cost switch.
12. Hermes runtime integration is rejected; substrate patterns may be learned selectively.
13. n8n and Dify are reference-only because a second orchestration authority would duplicate BOSS governance.
14. The catalogs below are indexes, not approval to adopt any product.

## B. Current Architecture Constraints

An external capability must preserve:

```text
User/Agent → intent/proposal → ActionContract → authorization/approval
→ ActionGateway → dispatcher/provider → ToolResult/ActionResult → evidence
```

Current evidence: `app.py`, `core/action_gateway.py`, `core/action_contract_repository.py`, `tools/dispatcher.py`, `tools/schemas.py`, `core/anti_hallucination.py`, and the focused ActionGateway/contract tests. ActionContracts remain lifecycle authority; PostgreSQL claims own execution ownership where enabled; Airtable stores the canonical ActionContract record. Any MCP, workflow, model, or SaaS adapter must not create a parallel authority, bypass identity/tenant scope, or turn provider output into success without normalized result/evidence.

## C. Candidate Matrix

| Candidate | Value | Existing overlap | Cost effect | Integration risk | Verdict |
|---|---|---|---|---|---|
| Hermes | substrate patterns for memory, skills, discovery | partial: sessions, tool registry, provider protocol | none | high: runtime trust boundary/tool authority | LEARN only |
| MCP | standardized provider/tool transport | dispatcher/tool registry, but no MCP client boundary | unknown | high: injection, identity, credentials, schema drift | ARCHITECTURE GAP FIRST |
| Ollama | local model endpoint | LLMProvider protocol only; direct SDK callers remain | potentially lower API spend, adds ops/GPU cost | high: quality, tools, structured output, timeout | FUTURE SPIKE |
| Supabase | hosted Postgres plus Auth/RLS/Realtime/Storage/vector tools | current Postgres + Airtable already cover shown needs | no proven saving below $14/month | migration and vendor surface | KEEP RENDER |
| Render Postgres | durable coordination and telemetry substrate | already used by main | known owner cost $14/month total | low for current scope | KEEP / EXTEND LATER |
| n8n | internal notifications/data movement/ETL | scheduler and provider integrations exist | unknown; self-hosting cost | authority duplication; Sustainable Use License | REFERENCE ONLY |
| Dify | prompt/workflow/RAG/LLMOps lessons | prompts, routing, provider calls exist | unknown | second orchestration runtime; modified license | REFERENCE ONLY |
| awesome-llm-apps | code-pattern index | partial patterns in current modules | none | copied code/dependency/supply-chain risk | LEARN |
| awesome-selfhosted | alternative discovery | no direct overlap | procurement research only | each project requires separate review | CATALOG |
| public-apis | API discovery | provider/tool registry exists | procurement research only | API security/reliability/licensing varies | CATALOG |
| free-for-dev | free-tier discovery | no direct runtime overlap | may reduce procurement cost | terms/limits/change risk | CATALOG |

## D. Memory Findings

| State | Current owner | Store | Durable? | Restart safe? | Multi-worker safe? | TTL | Source of truth | Class |
|---|---|---|---|---|---|---|---|---|
| Conversation history | `MemoryStore` | process-local dict | No | No | No | 12h | MemoryStore for prompt only | RAM ONLY |
| Action-resolution context | `MemoryStore` | process-local dict | No | No | No | 12h/10 events | best-effort prompt context | RAM ONLY |
| Lead sessions | `PersistentSessionStore` | Airtable Sessions + RAM cache | Yes in Airtable | Yes, if Airtable reachable | Partial; cache is per process | no generic TTL | Sessions table | DURABLE/PARTIAL |
| Last tool result / uploaded file | session store | Airtable State JSON + RAM cache | Yes in session record | Yes, if restored | Partial; cache is per process | session lifecycle | Sessions table | DURABLE/PARTIAL |
| Pending lead preview | session store | Airtable State JSON + RAM cache | Yes in session record | Yes, if restored | Partial | documented preview TTL | session record | DURABLE/PARTIAL |
| ActionContract lifecycle | ActionGateway/Repository | Airtable ActionContracts + RAM cache | Yes when repository configured | Yes | Airtable update is not CAS | contract TTL | ActionContracts | DURABLE/PARTIAL |
| Execution ownership/idempotency | AtomicClaimRepository | PostgreSQL | Yes | Yes | Yes, DB constraints/CAS | lifecycle | `action_execution_claims` | DURABLE |
| Turn ownership | TurnStateRepository | PostgreSQL | Yes | Yes | Yes, versioned CAS | terminal/recovery semantics | `durable_turn_state` | DURABLE |
| External poll ownership | ExternalPollLeaseRepository | PostgreSQL | Yes | Yes | Yes, lease constraint | lease expiry | `external_poll_leases` | DURABLE |
| External job/business state | ExternalExecutionRepository | Airtable | Yes | Yes | API-dependent | provider/job lifecycle | Airtable job record | DURABLE |
| Evidence/result projection | ActionContract/ToolResult plus turn evidence | Airtable contract/result fields + process-local turn object | Partial | Partial | Partial | turn/lifecycle dependent | ActionContract/result | PARTIAL |
| MessageContract state | builders/adapters | per-turn object/result | No dedicated durable store | No | No | turn lifetime | current message/result | DERIVED |
| Usage/cost events | `usage_telemetry` | PostgreSQL `usage_events` | Yes | Yes | Yes | query window | usage_events, shadow-only | DURABLE |
| Business memory | domain adapters | Airtable business tables | Yes | Yes | API-dependent | domain-defined | domain table | DURABLE |
| Learning data | no dedicated owner found | no canonical event store | Unknown | Unknown | Unknown | Unknown | none identified | UNKNOWN |
| Marketing/creative state | marketing adapters | Airtable demand/creative records | Yes | Yes | API-dependent | workflow-defined | marketing tables | DURABLE |
| Approval fallbacks | EventBus/app/TMA paths | RAM dicts plus Airtable projections | Partial | No for RAM paths | No/partial | 10m/30m/24h by path | ActionContracts only for canonical lifecycle | PARTIAL |

The important distinction is operational state versus business memory, episodic history, learning data, and prompt context. Main has pieces of all four, but not one coherent retrieval architecture for them.

## E. Render Postgres Findings

Render Postgres is already a suitable system-memory substrate for operational state: `core/database.py` provides the pool; migrations define atomic claims, durable turn state, external poll leases, and `usage_events`; repositories and tests consume them. It can also host future machine-oriented event/history tables without requiring a new database product.

It is not yet the canonical store for all BOSS memory. ActionContracts, Sessions, external job state, and domain/business records are Airtable-owned. Moving those would be a schema/migration project and is out of scope.

For Money Printer, the database is conceptually suitable for interactions, turns, decisions, outcomes, attribution, learning events, provider usage, costs, confidence, and corrections. The missing work is an explicit event model, retention/tenant policy, retrieval queries, and a deliberate prompt-context projection. Do not mix that with operational locks or raw prompt history.

## F. Supabase Decision

**Verdict: `KEEP RENDER`.**

Owner-supplied cost is Render production $7/month plus staging $7/month = $14/month. Repository evidence does not expose current DB size, connection saturation, backup/restore metrics, latency, egress, or a required Supabase-only capability. Supabase's open-source platform provides hosted Postgres, Auth/authorization, APIs, Realtime, Storage, and vector tooling, but capability availability is not a migration justification by itself. No cost reduction is proven at $14/month.

Reopen only when one of these is evidenced: Render connection/latency/backups/restore limits block a requirement; BOSS needs Supabase Auth/RLS/Realtime/Storage/vector operations that Render plus current code cannot provide; or a total-cost comparison including migration, operations, egress, and recovery shows a durable saving.

## G. MCP Decision

**Verdict: `ARCHITECTURE GAP FIRST`.**

MCP can fit only as `BOSS → governed action → provider adapter → MCP client → MCP server → provider`. The current provider protocol covers storage/LLM/channel, not a generic governed external execution adapter; direct tool dispatch and ActionGateway remain the existing path. Before an MCP spike, define a contract for capability discovery, tenant identity, server-side credentials, approval classification, timeout/retry/idempotency, revocation, unavailable-server behavior, schema/version pinning, untrusted-server handling, prompt/tool-injection defenses, and normalized external evidence. Never use `LLM → MCP server → mutation`.

## H. Model Provider Decision

**Verdict: `ARCHITECTURE GAP FIRST`; Ollama is `FUTURE SPIKE`.**

`providers/interfaces.py` contains an `LLMProvider.generate()` protocol and `providers/anthropic_shim.py` implements a normalized response shape, but current main call sites still use direct Anthropic/OpenAI SDK paths in `app.py`, `llm_fallback.py`, and related modules. Tool calls are Anthropic-shaped; structured-output, streaming, retry/error normalization, capability requirements, and token accounting are not unified behind the protocol. Usage telemetry is provider-generic and durable, but explicitly shadow-only.

Required before provider two: one provider-neutral request/result/error contract, explicit tool/schema capability negotiation, timeout/retry/fallback policy, token/cost reporting, and conformance tests for text, tool call, malformed output, timeout, rate limit, unavailable provider, and tenant-safe telemetry.

Future low-risk workloads: classification, structured extraction, summarization, document preprocessing, and background tagging. Embeddings and analytics can be considered after a real retrieval requirement. High-risk reasoning and governed tool selection should remain on a frontier provider until conformance and quality evidence exist.

## I. Code Mining Findings

| Pattern/source | What it solves | BOSS overlap | Reuse value | Risk | Recommendation |
|---|---|---|---|---|---|
| Hermes memory + searchable history | persistent facts and episodic retrieval | sessions durable; conversation memory RAM-only | high for data model ideas | privacy/retrieval leakage | LEARN |
| Hermes skills/procedures | repeatable task playbooks | no canonical procedural-skill registry found | medium | hidden authority/tool use | ADAPT only behind contracts |
| Hermes capability discovery | tool availability visibility | tool registry exists; availability filter is not a full provider registry | medium | discovery can imply authority | ADAPT as read-only metadata |
| awesome-llm-apps structured extraction | extraction pipelines | direct provider calls and domain parsers exist | medium | copied code/dependencies | LEARN |
| awesome-llm-apps evaluator patterns | quality checks around LLM output | tests and anti-hallucination checks exist | medium | evaluator becomes authority | ADAPT as evidence only |
| awesome-llm-apps RAG/context management | retrieve small context subset | prompt context helpers exist; no general retrieval layer | high | tenant/privacy leakage | FUTURE SPIKE |
| awesome-selfhosted catalog | alternative discovery | none | high as procurement index | per-project license/security | CATALOG |
| public-apis catalog | API discovery | provider/tool registry exists | medium | untrusted third-party APIs | CATALOG |
| free-for-dev catalog | pricing discovery | none | medium | unstable terms/limits | CATALOG |

## J. Licensing / Commercial Risks

n8n is source-available under the Sustainable Use License plus Enterprise License, not a permissive OSI license; its own terms limit use around internal business and customer-facing hosted/credential scenarios. Dify uses a modified Apache-2.0-based license with additional restrictions, including a multi-tenant restriction unless authorized and frontend logo/copyright conditions. Treat both as reference-only unless legal review approves a specific internal use.

Catalog licenses checked: Hermes MIT; Ollama MIT; Supabase Apache-2.0; awesome-mcp-servers MIT; awesome-llm-apps Apache-2.0; awesome-selfhosted CC-BY-SA-3.0. Catalog licenses do not license the individual projects listed inside those catalogs. Never adopt based on stars or inclusion alone; check maintainership, security policy, releases, dependencies/CVEs, secret handling, network/process privileges, tenant isolation, telemetry, retention, and supply-chain risk.

## K. Recommended Shortlist

1. Define the provider-neutral LLM conformance contract and tests.
2. Add a small durable event/retrieval design on existing Render Postgres, without migrating Airtable.
3. Keep the four research catalogs current as procurement/discovery indexes.
4. Revisit MCP only after the governed adapter contract exists.
5. Use Hermes/awesome-llm-apps as pattern references, not runtime dependencies.

## L. Explicit Rejections / Not Now

No Hermes runtime integration, no direct MCP mutation path, no Ollama production switch, no Supabase migration, no n8n/Dify orchestration runtime, no Airtable schema migration, no new database, no dependency installation, and no production resource changes.

## M. Next Follow-ups

The one justified next implementation task is: **write and test the provider-neutral LLM conformance contract at the existing provider boundary, without changing the active provider path.**

## Required Decision Table

| Item | NOW | NEXT | LATER | NO | Why |
|---|---|---|---|---|---|
| Durable memory architecture/retrieval on existing Postgres |  | ✓ |  |  | Storage exists; architecture does not |
| LLM provider conformance contract/tests |  | ✓ |  |  | Current protocol is unwired |
| MCP adapter |  |  | ✓ |  | Only after governance contract |
| Ollama |  |  | ✓ |  | Low-risk workloads first, after conformance |
| Keep Render Postgres | ✓ |  |  |  | $14/month; no proven gap |
| Supabase migration |  |  |  | ✓ | No technical/economic trigger |
| Hermes runtime |  |  |  | ✓ | Governance/runtime duplication |
| n8n/Dify runtime |  |  |  | ✓ | Orchestration duplication/licensing |
| Catalog maintenance | ✓ |  |  |  | Avoid repeated discovery work |

## Special Questions

1. **Q1:** Yes. Existing Render Postgres can provide the missing system-memory substrate; it already persists coordination and telemetry.
2. **Q2:** Primarily memory architecture/retrieval and canonical ownership, not raw storage.
3. **Q3:** No evidence shows Supabase lowers the current $14/month cost.
4. **Q4:** Reopen on measured Render limits, a required Supabase-only capability, or a complete lower-TCO comparison.
5. **Q5:** Yes. Keep Airtable as human operational/business layer while Postgres serves machine/system state.
6. **Q6:** Conversation history, action-resolution context, batch/pending approval fallbacks, and some projection/turn evidence are RAM-only or partial; see the table above.
7. **Q7:** No current `HERMES_AGENT_AUDIT.md` exists on `origin/main`, so a literal delta cannot be proven. Current code partially covers channel/provider/tool/session patterns; bounded conversation memory, searchable episodic memory, procedural skills, and a generic doctor/discovery surface remain gaps or unverified.
8. **Q8:** Yes architecturally, but not ready: only behind ActionGateway/provider adapter with identity, approval, timeout, retry, idempotency, revocation, and evidence contracts.
9. **Q9:** No. The protocol exists, but active call paths and conformance tests are not provider-neutral.
10. **Q10:** Check `OPEN_SOURCE_TOOL_INDEX.md`, `EXTERNAL_CAPABILITY_INDEX.md`, and `SAAS_REPLACEMENT_INDEX.md` before building or buying; catalogs remain non-authoritative.

## Verification Boundary

This audit is `MERGED` and `WIRED` evidence from current `origin/main` plus externally checked upstream license pages. It does not claim current deployment state or live database configuration. The repository's dated Render evidence is historical/limited for this audit and does not prove that production equals the current tip.
