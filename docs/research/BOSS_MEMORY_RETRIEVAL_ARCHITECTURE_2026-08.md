# BOSS Memory & Retrieval Architecture — Audit + Design

> This is a design/audit reference, not a runtime source of truth and not an implementation approval.

Date: 2026-08-18
Base commit audited: `d2f9481` (`origin/main`)
Worktree: `/home/elichazan/My-bot-worktrees/memory-retrieval-design`, branch `audit/memory-retrieval-design`
Scope: Internal Architecture / Hermes Learnings track only. No Money Printer external tools, no Metabase, no MCP, no Ollama, no Supabase, no n8n, no Dify, no external SaaS evaluation. No migration, no schema implementation, no production code in this document.

Prior finding this builds on: Render Postgres is sufficient as the existing storage layer. The gap is not a new database — it is a **Memory Architecture + Retrieval** layer on top of what already exists.

---

## A. Current State Map

Verified directly against `origin/main` code (not against older docs). File:line citations below are load-bearing — re-grep before trusting them if this document is read after further drift.

| State / Memory | Current Store | Durable? | Owner | Source of Truth? | Retrieval Today | Context Use |
|---|---|---|---|---|---|---|
| Sessions (lead-capture FSM step) | `session_store.py` `PersistentSessionStore` — RAM LRU cache backed by Airtable `Tables.SESSIONS` | Airtable (RAM is a cache) | `lead_capture.py`/`app.py` via `lead_sessions` | Yes, for session/FSM state | `get()`/`get_or_create()` | Not injected into LLM prompt; drives deterministic FSM |
| Turn coordination (TC8) | `core/turn_state_repository.py` → Postgres `durable_turn_state` | Postgres | `TurnStateRepository` | Yes, for turn ownership only — `active_contract_id` is a reference, not lifecycle authority | Conditional SELECT | Not fed to LLM |
| Turn envelope (routing/observability) | `core/turn_envelope.py`, rebuilt every turn | **RAM only, never stored** (explicit in module docstring) | `app.py` `_build_and_log_turn_envelope` | No | Log-only | Never injected into prompt |
| Conversation memory (short-term) | `memory_store.py` `MemoryStore`, module-level singleton | **RAM only** — docstring: "NON-DURABLE, PROCESS-LOCAL... a restart or redeploy loses it all"; 12h TTL, 50-msg cap | `app.py` after every turn | No — explicitly never the lifecycle/business source of truth | `get_for_claude(uid)` | **Yes** — becomes the `messages[]` array sent to Claude every turn. A parallel channel `context_events` (BUG-149) is injected into the system prompt separately |
| Lead memory (score/tier/summary) | `lead_memory.py`, RAM buffer, debounced write to Airtable `Tables.LEADS` | Airtable (write-behind; ≤2 unflushed msgs at risk on crash, mitigated by a 10-min flush job) | `LeadMemory.update()`, gated by `LEAD_MEMORY` flag (default off) | Yes, for score/tier/summary fields | RAM-only `.get()`/`.all_active()` — no read-back from Airtable | Feeds `followup_engine`, not the LLM prompt directly |
| Lead events (structured log) | Airtable `Tables.LEAD_EVENTS` ("Lead Events") — must be created manually before use | Airtable, if the table exists in the live base (unconfirmed) | `lead_capture.capture_lead_event()`, `core/lead_event_writer.py` | Yes, for lead-event history | Not read back anywhere found in current code | No |
| `core/lead_events.py` (learning-engine read adapter) | Reads Airtable table "Business Memory" directly via raw `httpx`, bypassing `tools/airtable_gateway.py` | Reads Airtable | N/A (read-only) | No — a read adapter over a different table than "Lead Events" above | `core/learning_engine.py._load_events` | No — feeds a Telegram display string only |
| Business facts (`/update` command) | `cmd_update.py` → Airtable `Tables.BUSINESS_MEMORY`, gated by `FEATURE_BUSINESS_UPDATE` (default off) | Airtable | `cmd_update._save_to_business_memory()` | Yes — canonical manual business-memory entries | `get_recent_business_context(domain, limit=5)`, truncated to 600 chars | **Yes** — `context.py` ("C20: Business Memory injection") appends this into the system prompt on every `build_context()` call |
| User Profile Layer (`profile.py`) | Designed for Airtable table "Profile", field `ProfileData` | **Dead code** — field never created live; zero non-test callers anywhere in the repo | N/A | No | N/A | N/A |
| ActionContracts (approval/decision lifecycle) | `core/action_contract_repository.py` → **Airtable** `Tables.ACTION_CONTRACTS` (despite living under `core/` next to Postgres repos) | Airtable | `ActionContractRepository.save()`/`.transition()` — no compare-and-swap, read-check-PATCH-verify only | Yes — explicit single state owner. The TMA "Approvals" Airtable table is a non-authoritative display projection | `.get()`, `.find_pending_by_canonical_user()`, `.find_by_business_fingerprint()` | Feeds approval prompts as rendered text, not raw contract fields |
| Execution claim (atomic ownership) | `core/atomic_claim_repository.py` → Postgres `action_execution_claims` | Postgres | `claim_contract_execution()` (`INSERT...ON CONFLICT DO NOTHING RETURNING`) | Yes, for execution ownership only — separate authority from contract status | Health-checked at startup | No |
| Lifecycle/evidence projections | `core/lifecycle_projection.py`, `core/evidence_projection.py`, `core/action_resolution_projection.py` | RAM-only / pure functions over an in-hand contract | `core/action_gateway.py` resolution sink | No — derived/shadow. `action_resolution_projection.py` writes into `memory_store` (see above) and its own docstring states this "is never the lifecycle source of truth" | In-request, or same-process `memory_store` TTL window | Resolution events *are* fed to the LLM via `context_events` |
| MessageContracts | `core/message_contract.py` — "performs no I/O, reads no runtime state" | Not persisted | Same-request callers | No — presentation object only | N/A | Shapes what's said, not fed back into the LLM |
| Last tool result shadow | `core/last_tool_result_shadow.py`, module-level dict | RAM only, 200-entry cap, 15-min TTL, gated by `FEATURE_LAST_TOOL_RESULT_SHADOW` (default off) | `record()` | No — explicit shadow/observation | `recent()` (diagnostics) | Never |
| Session-level "last tool result" (C60) | `session_store.py` `set_last_tool_result`/`get_last_tool_result` | Airtable (same Sessions sync) | `lead_sessions` | Yes, for cross-round tool awareness | `get_last_tool_result()` | Feeds agent tool-context awareness between rounds |
| Execution evidence (`turn_evidence.py`, `anti_hallucination.py`, `evidence_projection.py`, `claim_authorization.py`) | Pure computation over in-request data; none persist | RAM-only, per-request, no cross-turn persistence | Computed fresh each turn by `app.py`'s tool loop | No — derived from ActionContract status + in-call tool results | N/A | Drives what the assistant may claim this turn — not stored as memory |
| Learning events / "what worked" | `core/learning_engine.py` — explicitly read-only, writes nothing new | Reads Business Memory via `core/lead_events.py` | N/A | N/A | `get_domain_insights()` → Telegram display string; gated by `LEARNING_ENGINE` flag (default off) | **No** — module's own comment marks context-injection as a future phase, not wired today |
| Marketing — ad attribution (UTM) | `ad_attribution.py` writes UTM fields onto `Tables.LEADS` records directly (no dedicated table) | Airtable | `ad_attribution.py` | Yes, for UTM fields on the lead record | `airtable_get(Tables.LEADS, formula)` for reporting | No |
| Marketing — audience intelligence | `audience_intelligence.py` — read-only via `crm.py`/`Tables.LEADS` | Reads Airtable, writes nothing | N/A | No — computed segments only | Computed on demand (weekly report) | No |
| Follow-up state | `followup_engine.py` reads `lead_memory.all_active()`; writes `followup_count` back onto `Tables.LEADS` | Airtable (piggybacked on Leads) | `followup_engine.run_followup_scan()` | Yes, for `followup_count`/tier fields only | Recomputed each scheduler run | No |
| Abandoned-lead worker | `abandoned_lead_worker.py` reads Airtable Sessions, writes `Tables.TASKS` | Airtable | `run_abandoned_scan()` | N/A — derived scan each run | Recomputed each run | No |
| `usage_events` | `core/migrations/002_usage_events.sql` → Postgres | Postgres | `core/usage_telemetry.record_usage()`, called from every LLM/STT call site | Yes, but **shadow only** — migration docstring says nothing reads it to drive `AI_Usage_Daily`/`EMERGENCY_STOP_AI` yet | Read functions exist (`get_usage_window`, `get_daily_usage`, `get_trailing_hour_usage`) but have **zero callers outside their own test file** — confirmed by grep | No |
| Preferences / tenant context | No durable store beyond the dead `profile.py` and static per-role prompt selection in `context.py` | N/A | N/A | N/A | N/A | Role-based prompt selection is static code, not stored preference data |
| Legacy RAM approval queues | `app.py:_pending_approvals` (router-level, BUG-070/LL-13) and `event_bus.PendingActionsStore` | RAM only | `app.py`, `event_bus.py` | No — ActionContracts (Airtable) is canonical for the newer flow | In-process only | Drives ✅/❌ reply UX |
| `event_bus.BatchQueueStore` | RAM dict, explicitly quarantined/legacy — "never persisted to Airtable" | RAM only | N/A | No | N/A | N/A |
| `event_bus.ExecutedActionCache` | RAM dict, 600s TTL | RAM only | Dedup for executed-action fingerprints | No | Fingerprint lookups | No |

### Every distinct Postgres table today

| Table | Migration | Purpose |
|---|---|---|
| `action_execution_claims` | `001_action_execution_claims.sql` | Atomic execution-ownership claim per ActionContract. Gated by `FEATURE_ATOMIC_CLAIMS`. |
| `durable_turn_state` | `002_durable_turn_state.sql` | TC8 turn-ownership coordination row per (tenant, user). Not lifecycle authority. |
| `external_poll_leases` | `002_external_poll_leases.sql` | Short-lived polling-ownership leases; explicitly not an execution ledger. |
| `tools` / `capabilities` / `tool_capabilities` | `002_tool_catalog.sql` | Editorial tool-catalog snapshot; runtime never calls it live. Out of scope for memory. |
| `usage_events` | `002_usage_events.sql` | Durable per-call cost/usage log. Write-only in practice today. |

`core/action_contract_repository.py` and `core/external_execution_repository.py` are **Airtable-backed** despite the `*_repository.py` naming convention shared with the Postgres repositories — a real naming trap, worth fixing independently of this design.

### Airtable tables carrying business/memory-relevant state

Leads, Contacts, Deals, Sessions, Business Memory, Lead Events (manual-create, unconfirmed live), Profile (field not created — dead), ActionContracts, External Execution Jobs, Tasks, Interaction Log, Learnings & Insights, AI_Usage_Daily, Emergency_Window, Decisions/Decision Events/Decision Stakeholders/Decision Inbox, TRAFFIC_SOURCES (live, wired into no code module), plus the string-literal "Approvals" table (a non-authoritative TMA projection, not a `Tables.` constant).

### Dead / non-live pieces worth flagging explicitly

1. `profile.py` — zero callers, its Airtable field doesn't exist. Any older doc describing it as "the long-term memory layer" is stale.
2. `usage_events` reads — the accessor functions exist but nothing in the live pipeline calls them; the real cost-control trigger is still `cost_monitor.py`'s in-memory accumulator.
3. `core/learning_engine.py` — read-only by design, produces a display string, does not feed context. Its own comment marks context-injection as future work.
4. Two live legacy RAM approval queues coexist with the durable ActionContracts path. They are not memory in the business sense, but they are state that does not survive a restart.

---

## B. Memory Taxonomy

Four layers, deliberately kept separate. Nothing proposed here merges them.

### A. Operational State
Runtime-correctness state, not LLM memory. **Already reasonably well modeled today**: `durable_turn_state`, `action_execution_claims`, `external_poll_leases` (Postgres), plus session FSM state (Airtable Sessions) and the RAM-only approval queues/dedup caches. This layer is out of scope for the retrieval design below — it answers "is this safe to execute," not "what does the model need to know."

### B. Business Memory
Structured, tenant-scoped, auditable business facts: lead/deal facts, decisions, outcomes, UTM/attribution, business events. **Currently fragmented and partially unstructured**: some of this lives correctly as fields on `Tables.LEADS`/`Tables.DEALS` (structured, good); some lives as free-text blobs in `Business Memory` (`cmd_update.py`) with no schema beyond `Title/Description/EventType/Impact/Domain` and no provenance beyond "who ran `/update`"; ActionContracts is the one part of this layer with real provenance (actor, timestamp, version, status transitions).

### C. Episodic Memory
`interaction → action → tool/result → outcome`. **Currently exists only as ephemeral RAM** (`memory_store.py`'s conversation history, `context_events`, `last_tool_result_shadow`) or as scattered Airtable side-effects (Lead Events table, Interaction Log) with no unified retrieval. There is no durable, queryable episode log today — this is the single largest gap relative to what section 3/4 of the request asks for.

### D. Compact Context / Working Memory
The subset actually sent to the model. Today this is exactly two channels, both ad hoc: `memory_store.get_for_claude()` (last 50 messages, 12h TTL, no ranking, no budget beyond a fixed message cap) and `context.py`'s system-prompt injections (Business Memory last-5, ActionContract pending-approval text, role-based static prompt). There is no retrieval step, no ranking, no relevance scoring, no budget accounting beyond "last N messages." It is a snapshot, not a source of truth — and today it is *assembled by two unrelated code paths* rather than one retrieval pipeline.

---

## C. Source-of-Truth Rules

No new source of truth is introduced by this design (repo-wide rule, `decision.no_new_source_of_truth`). Instead:

| Fact type | Canonical owner today | Rule going forward |
|---|---|---|
| Approval/decision lifecycle | ActionContracts (Airtable) | Stays canonical. Retrieval reads it, never re-derives approval status. |
| Lead/deal structured fields | `Tables.LEADS`/`Tables.DEALS` (Airtable) | Stays canonical. Business Memory retrieval treats these as the ground truth for anything they already cover — no shadow copy of a field that already lives on the lead record. |
| Manually-logged business facts | `Business Memory` table (Airtable) | Stays canonical for free-text/event-shaped facts that don't fit a lead/deal field. Needs provenance fields it doesn't have today (see F). |
| Execution/turn ownership | Postgres (`durable_turn_state`, `action_execution_claims`) | Stays canonical, stays out of the memory/retrieval design entirely — it's operational state, not memory. |
| Conversation turns | Nothing today (RAM only) | **New**: needs a durable, append-only episodic store. This is additive (a new table), not a new *source of truth* for anything that already has one — it only becomes the source of truth for "what was actually said," which nothing else currently records at all. |
| Usage/cost | `usage_events` (Postgres, shadow) already exists | No change needed architecturally; it's a candidate evidence source for episodic ranking once it's read from anywhere. |

---

## D. Retrieval Pipeline (conceptual contract)

```
request/context
      ↓
entity resolution        (tenant_id, canonical_user_id, and — if resolvable — lead/deal/project id)
      ↓
tenant scope filter       (hard boundary, never optional — see J)
      ↓
candidate memories         (Business Memory facts + Episodic entries scoped to the resolved entities)
      ↓
ranking / filtering        (recency, relevance to current intent, confidence, correction/supersession status)
      ↓
context budget allocation  (per-category caps, not just a global token ceiling)
      ↓
LLM context (working memory snapshot — regenerated every turn, never itself persisted)
```

Key property: **retrieval is a read path over existing sources of truth, not a store.** The "candidate memories" step queries Business Memory / Episodic Memory tables directly (or a materialized index over them); it does not maintain its own copy of the facts. This mirrors how `context.py`'s Business Memory injection already works today (it queries Airtable live on every `build_context()` call) — the design generalizes that pattern to cover Episodic Memory too, and adds the ranking/budget steps that don't exist today.

Dimensions to filter/rank on, in the order they should be applied (cheap/hard filters first, expensive/soft ranking last):
1. **tenant** (hard filter, never skippable)
2. **user/person** and **lead/deal/entity** (hard filter once resolvable; falls back to "no entity scope" only for genuinely tenant-wide facts)
3. **domain** (real_estate/import/media/saas/finance/general — hard filter, matches existing per-domain prompt architecture)
4. **recency** (soft rank)
5. **confidence** (soft rank; see F)
6. **correction/supersession status** (hard filter — a superseded fact is excluded, not merely down-ranked)
7. **relevance to current turn's intent** (soft rank — can start as simple keyword/entity overlap; does not require embeddings/vector search, which is explicitly out of scope per the request)
8. **source priority** (soft rank — e.g. an explicit `/update` fact outranks an inferred one at equal recency)

---

## E. Ranking / Scope / Context Budget

Per-category budget, not one global cap — this is the direct Hermes lesson ("don't send it all"):

| Category | Budget shape | Rationale |
|---|---|---|
| Business Memory facts | max N facts (e.g. 5-8), each truncated to a fixed length | Already the pattern `cmd_update.get_recent_business_context()` uses (limit=5, 600 chars) — generalize, don't reinvent |
| Episodic Memory | max M recent turns/episodes + optionally a rolling summary of older ones | `memory_store` already caps at 50 messages/12h; the gap is that nothing summarizes what falls off the window today — it's just dropped |
| Active operational context (pending approval, tool-blindness state) | small, fixed-size, always included when present | Already correctly modeled today via ActionContract injection and `session_store`'s `last_tool_result` |
| Supporting evidence identifiers | IDs/references only, not full payloads | Lets the model ask a tool for detail rather than pre-loading everything — keeps the budget from growing with data volume |

A hard token budget should be the outer bound, with per-category sub-caps enforced before the token count is even checked (cheap to compute, avoids a late truncation step that silently drops whichever category happened to be assembled last — a real risk in the current two-unrelated-code-paths setup).

---

## F. Provenance & Conflict Handling

Every memory item that can influence business reasoning must be able to answer: where did this come from, when was it created/updated, who/what wrote it, what's its confidence, is it corrected/superseded, is there evidence.

**Today**: ActionContracts already carries real provenance (actor, timestamps, version). Business Memory (`cmd_update.py`) does not — it has `Title/Description/EventType/Impact/Domain` and no explicit writer/confidence/supersession fields. Lead-record fields inherit whatever provenance the CRM already has (last-write-wins, no history).

**Conflict rules to design for** (not implement here):
- **Fact changed** (old X, new Y): the newer, non-superseded fact wins in retrieval; the old one is excluded, not blended. Requires a `superseded_by`/`status` concept wherever a fact can change — currently absent from Business Memory.
- **User correction**: gets explicit precedence over both prior facts and system-inferred facts, regardless of recency-of-others — needs its own provenance category ("explicit user correction") distinct from "inferred fact," which today's write policy (section G) doesn't yet distinguish.
- **Conflicting sources**: never silently pick one. Retrieval surfaces both with their provenance if confidence is comparable, and defers to a documented precedence rule (explicit fact > user correction > system observation > inferred fact) only when the caller needs a single answer.
- **Stale information**: freshness should down-rank, not exclude, unless a fact has been explicitly superseded — a fact can be old and still true (e.g. a signed contract).

---

## G. Write Policy

Not every message becomes memory. Classification (design only, no implementation):

| Class | Auto-save? | Requires confidence/evidence? | Notes |
|---|---|---|---|
| Explicit fact (e.g. `/update` entry, a structured lead field write) | Yes | No (author asserted it directly) | Matches current `cmd_update.py` behavior |
| Inferred fact (model-derived from conversation) | No — requires a confidence threshold or explicit confirmation | Yes | Nothing today writes inferred facts durably; keep it that way until confidence scoring exists |
| System-generated observation (e.g. resolution/outcome events) | Yes, to Episodic Memory only, never to Business Memory directly | N/A (observation, not a claim) | Matches how `action_resolution_projection.py` already treats these as ephemeral/shadow |
| Outcome (deal won/lost, follow-up result) | Yes, to Business Memory, since it's usually a structured field change already going through the CRM | No additional evidence beyond the existing write | Already the pattern for `Tables.LEADS`/`Tables.DEALS` writes |
| User correction | Yes, always, tagged as a correction | No | Must never require the same confidence bar as an inferred fact — that would let a wrong inference outrank a human correction |
| Temporary context (mid-conversation working state) | No — stays in Working Memory only | N/A | Never promoted automatically; matches current `memory_store` behavior |
| Noise (chit-chat, non-substantive turns) | No | N/A | Episodic log can still record the turn happened (for conversation continuity), but it carries no Business Memory weight |

---

## H. Airtable vs Postgres Responsibility

Verified current split, and the rule to keep going forward:

```
Airtable → human-operational/business UI: CRM fields the team edits directly
           (Leads, Deals, Contacts, ActionContracts, Business Memory, Sessions)

Postgres → machine/system memory: high-volume history, runtime coordination,
           and learning/event data that no human edits by hand
           (durable_turn_state, action_execution_claims, external_poll_leases,
           usage_events — and, per this design, the new Episodic Memory log)
```

Exceptions already present today, documented rather than fixed here:
- `core/action_contract_repository.py`/`external_execution_repository.py` are named `*_repository.py` (a Postgres-repo naming convention in this codebase) but are Airtable-backed. This is a pre-existing inconsistency, not something this design introduces or needs to resolve.
- `usage_events` is the one Postgres table that is genuinely a memory/learning candidate today (per-call cost data), but it's currently unread — it's evidence waiting for a consumer, not a gap in this design.

No migration is proposed. If Episodic Memory becomes real (see K), it belongs in Postgres by this same rule: it's high-volume, machine-written, and no human edits a conversation turn by hand.

---

## I. Money Printer Compatibility

Not built here, but the retrieval contract in D is shaped to answer these later without rework:

- *What worked before for this lead type?* → Episodic Memory entries scoped to `domain` + lead-type facts from Business Memory, ranked by outcome field (once outcomes are structured, which they partially are via `Tables.DEALS`/`Tables.LEADS` status fields).
- *Which channel produced results?* → `ad_attribution.py`'s UTM fields are already structured Business Memory; retrieval just needs to include them as a queryable category once relevant.
- *What was the last action?* → This is exactly what Episodic Memory's `interaction → action → tool/result → outcome` shape is for; today's `session_store.get_last_tool_result()` is a narrow, single-slot precedent for the same need.
- *What objections already came up?* → Requires Episodic Memory to retain enough of the conversation content (not just message counts) — a real gap today, since `memory_store` drops content after 12h/50 messages with no summarization.
- *What campaign produced a lead?* → Already structured via `ad_attribution.py` writes onto `Tables.LEADS`; no new capability needed, just inclusion in the candidate-memory query.
- *What was the outcome of a similar follow-up?* → Needs `followup_engine`'s scan results to be recorded as Episodic entries rather than recomputed and discarded each run, which is the current behavior.

No Money Printer logic is designed here — this section only confirms the retrieval contract doesn't need to be reshaped later to support it.

---

## J. Security / Tenant Isolation

- Tenant scope is a **hard filter applied first**, before any ranking — mirrors `tools/airtable_security.enforce_tenant_scope()`'s existing "never optional" posture for raw Airtable access. Retrieval must not be a side-channel that bypasses that enforcement; it queries through the same tenant-scoped paths, not a shortcut.
- Episodic Memory (once it exists) must carry `tenant_id`/`canonical_user_id` on every row from day one — retrofitting tenant scoping onto a conversation log after the fact is exactly the kind of governance debt this repo's `docs/governance/` layer exists to prevent.
- No memory item should ever surface across tenants even at low rank — a hard filter, not a scoring penalty, consistent with how `core/action_contract_repository.py` already treats `tenant_id`/`canonical_user_id` binding as identity-fail-closed rather than best-effort.
- Secrets/PII redaction: the existing `tool_registry._redact_operator_detail()` pattern (already reused once, in `boss_doctor.py`) is a precedent for retrieval-layer output too — any memory surface shown to an operator/diagnostic context should redact the same way business-facing content is redacted.

---

## K. Minimal Implementation Plan (max 3 phases)

This section names phases; it does not authorize building them. Each phase should get its own owner decision and its own Context Librarian registration when it's actually started, per this repo's existing gate.

**Phase 1 — Episodic Memory contract + durable log (additive, no cutover).**
Define an `EpisodicEntry` contract (tenant_id, canonical_user_id, entity refs, turn content, action/tool ref, outcome ref, timestamp, provenance) and a Postgres table to hold it, written alongside (not instead of) today's `memory_store.py` RAM path. No retrieval wiring yet — this phase only stops losing episode data on restart. Smallest testable unit: the contract type + repository, following the existing `TurnStateRepository`/`AtomicClaimRepository` pattern.

**Phase 2 — Retrieval contract + context budget for Business Memory + Episodic Memory.**
A single retrieval function that assembles the working-memory snapshot from Business Memory (Airtable, as today) and the new Episodic log (Phase 1), applying the tenant/entity hard filters and per-category budget from sections D/E. Replaces the two ad hoc assembly paths (`memory_store.get_for_claude()` + `context.py`'s Business Memory injection) with one contract, without changing what data sources are canonical.

**Phase 3 — Provenance + conflict handling on Business Memory writes.**
Add the missing provenance fields (writer type, confidence, superseded-by) to Business Memory writes (`cmd_update.py` and any future auto-write path), and enforce the correction-precedence rule from section F at retrieval time. Deferred to last because it requires the write policy in G to have real callers first — no point building conflict resolution for a memory class that has no volume yet.

---

## Recommended Single Next Implementation Slice

**Phase 1's contract only: the `EpisodicEntry` data contract + its repository, with no wiring into the live turn loop yet.**

Why this slice and not a bigger one:
- It's the one piece from the taxonomy in B that has genuinely nothing behind it today (Business Memory, ActionContracts, and operational state all already have *some* durable store; Episodic Memory has none).
- It's testable in complete isolation — a contract type and a repository with `save()`/`get_for_entity()`, following the exact precedent already in the codebase (`core/turn_state_repository.py`, `core/atomic_claim_repository.py`), with no runtime call sites to break.
- It deliberately stops short of retrieval/ranking/budget (Phase 2) and write-policy enforcement (Phase 3) — both need real data flowing first to design against, not assumptions.
- It requires no flag, no cutover, and no change to any existing canonical source of truth — matching the `decision.no_new_source_of_truth` constraint by construction, since it only becomes the source of truth for something (raw episode history) that currently has no source of truth at all.
