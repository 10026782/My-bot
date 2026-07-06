# C95A — Archive Carry-Forward Gap Report

Audit date: 06/07/2026
Type: audit / gap discovery only. No code, Airtable, or ROADMAP changes were made as part of this task.

## 0. Source note — archive input

The task named a source document `MASTER_PLAN_v2` and reference files `C95A_relevant_files.txt` / `C95A_content_hits.txt` / `C95A_candidate_files.txt`. None of these exact filenames exist in the repository (searched full tree). What does exist, and what this report treats as the archive evidence base instead:

- `archive/BOSS_MASTER_PLAN_2026_v2.md` — short, mostly a "completed" list already marked ARCHIVED (superseded 14/06/2026), doesn't describe most of the 13 capability areas below.
- `archive/BOSS_MASTER_PLAN_One_Road.md` — "One Road, Many Exits" architecture doc (Core/Ports/5 Gates/domain-agnostic), ARCHIVE-flagged, closest match for capabilities #1–3 (deterministic core, thin app.py, router separation).
- `archive/BOSS_MASTER_PLAN_GAP_ANALYSIS.md` — a prior (2026-06-07) reality-check audit; useful as a historical baseline, itself superseded.
- `docs/governance/BOSS_UNIFIED_MASTER_PLAN_v2.md` — dated 30/06/2026, the most architecturally complete "v2" doc in the repo (layer map, horizons, gates); closest single match for the literal filename `MASTER_PLAN_v2`.

None of these four documents individually contains all 13 capability areas listed in the task (e.g. "Contacts Brain," "draft mode," "morning cockpit," and the specific debrief→pattern-mining→adaptive-rule pipeline are not named verbatim in any of them). Per this task's own instruction ("do not claim missing until searched"), this report treats **current code and current docs (ROADMAP.md, AI_CONTEXT.md, BUG_AUDIT_LOG.md, CHANGE_CONTROL_LOG.md) as the primary evidence**, and the four archive docs above as supporting evidence of original intent where they speak to a given capability. Every capability below states explicitly which archive document (if any) supports it, and flags `NEEDS_VERIFICATION` where no archive text was found matching the task's framing.

---

## 1. Executive summary

**Still represented clearly (doc + code aligned):**
- Router/orchestrator separation (`core/router/*`) — clean, documented, tested.
- Multi-channel lead intake (Telegram, WhatsApp, Email, Voice/IVR, File upload) — all five channels have live ingress adapters and are documented in ROADMAP/AI_CONTEXT with granular, dated status per channel.
- Action IDs / pending-action audit surface — `core/action_gateway.py` is real, wired into `app.py`, and its own limitations (shadow mode, dual mechanisms) are honestly documented in `SPEC_LL13_Pending_Approval_Unification.md`.

**Partially implemented:**
- Schema discovery/governance — five real modules exist and are wired (one into CI, one into the write path), but every enforcement layer is explicitly non-blocking (`|| true` in CI, "warns not blocks" in the validator).
- Contacts Brain — a real resolver with ranking + disambiguation exists but is flag-gated off by default, with no alias table and no preferred-channel logic.
- Morning cockpit / daily digest — real and scheduled, but known-buggy (BUG-066..069) and missing a learning/debrief section.

**Implemented but not documented as such (i.e., you'd only find it by reading code):**
- The `ActionGateway`/`event_bus.py` duplication — two independent pending-action mechanisms both live simultaneously, which is the exact anti-pattern `SPEC_LL13` was written to eliminate; the spec itself is still "Draft — not yet implemented."
- `TrafficSourcesFields`/`TRAFFIC_SOURCES` Airtable table exists live but zero code reads/writes it.

**Documented but not implemented:**
- `LeadEventFields` (Lead Events table) is fully spec'd in `airtable_schema.py` but `core/lead_events.py` actually targets a completely different table (`"Business Memory"`) — a spec/code mismatch, not just an unbuilt feature.
- Learning Loop / pattern mining / adaptive rules — explicitly deferred in both the archive (`BOSS_UNIFIED_MASTER_PLAN_v2.md` Horizon 7: "not now") and current code (`core/learning_engine.py` intentionally inert per CLAUDE.md) — this is a *documented* deferral, not a silent drop.

**Dropped during doc consolidation without an explicit decision:**
- "Draft mode" as a resumable, contact/channel-tied pending-action concept never existed beyond the Gmail draft tool; the closest attempt (`pending_lead_preview`) was found to be dead code (BUG-056/057) and no doc records a decision to drop the general concept.
- Data-model canonicalization (Leads vs Contacts vs Deals each having their own status/stage vocabulary) — nowhere is there a decision doc saying which is canonical; `ARCHITECTURE_DRIFT_MAP.md` only warns against adding new status values, it doesn't resolve the three-way split.

**Superseded by newer architecture:**
- The "One Road" Ports/5-Gates decision-hub vision is being carried forward through `core/action_gateway.py` + `core/reasoning_engines.py` + Decision Hub Stage 0-6, under different names, and is actively tracked in ROADMAP (unlike most of the rest of the archive).

See §2 for the full capability matrix and §3 for area-by-area evidence.

---

## 2. Capability matrix

| # | Original capability | Archive evidence | Current doc evidence | Current code evidence | Status | Gap | Recommended action |
|---|---|---|---|---|---|---|---|
| 1 | Deterministic business system + AI reasoning layer | `archive/BOSS_MASTER_PLAN_One_Road.md`: "5 Gates: Delta→Entity→Trust→Readiness→Risk", `GateResult` contract | `ROADMAP.md` §0.5, §Reasoning Layer notes (30/06, 28/06/2026 entries) | `core/reasoning_engines.py`, `core/reasoning_entity.py`, `core/reasoning_ports.py`, `core/adapters/decision_adapter.py` — merged, 59/59 tests pass, but `run()`/`append_reasoning_block()` have "אפס קריאה חיה" except one fallback call from `cmd_decision.py._format_decision_card()` when `FEATURE_DECISION_HUB` is off | PARTIAL | Reasoning layer exists and is tested but is not driving real decisions in the live path | Keep — decide explicit activation criteria before wiring further |
| 2 | Thin `app.py` | `docs/governance/MODULE_RULES.md` rule 2 ("רזון app.py", referenced but not directly quotable — see rule list header) | Not tracked as a metric anywhere in ROADMAP/AI_CONTEXT | `app.py` is 2,860 lines / 139KB — the single largest file in the repo, containing routing, approval queue, digest triggers, and the agent loop | DROPPED_WITHOUT_DECISION | The "thin app.py" module rule is aspirational text with no enforcement or tracked metric; app.py has grown continuously and no doc acknowledges the drift | NEEDS_DECISION — either add a line-count/complexity gate to CI or formally retire the rule |
| 3 | Router / orchestrator separation | `archive/BOSS_MASTER_PLAN_One_Road.md`: "הכביש (CORE): Input → Memory → Understanding → 5 Gates → Decision/Action" | `CLAUDE.md` Architecture section; `ROADMAP.md` router entries throughout | `core/router/{channel_router,domain_router,intent_router,risk_router,route_decision,capture_router}.py`, `core/router/test_router.py` | IMPLEMENTED | None significant | Keep |
| 4 | Contacts Brain (resolver, aliases, ranking, preferred channel) | `archive/BOSS_MASTER_PLAN_2026_v2.md` §4 "Contact Resolver" (immediate priority) | Not documented as "Contacts Brain" anywhere; `CLAUDE.md:74,120` calls it "lead/contact dedup matching" | `tools/contact_resolver.py` — ranking (`_score_match`, home-grown fuzzy scorer) + disambiguation (`ResolveStatus.AMBIGUOUS`, max 5 candidates) implemented; flag `CONTACT_RESOLVER` off by default, and when off resolution is disabled (not degraded); no alias/nickname table; no `preferred_channel` logic anywhere in repo (zero grep hits) | PARTIAL | No aliases, no preferred-channel selection, disabled by default, brittle regex-parsing of a display string instead of a structured data source | Keep — add alias table + turn flag on behind owner verification before calling this "done" |
| 5 | Draft mode / pending message actions (save→resume→approve/cancel) | `archive/BOSS_MASTER_PLAN_2026_v2.md` doesn't name this; task's own framing is the only source found | No ROADMAP/AI_CONTEXT entry for "draft mode" | Only a real, same-session Gmail draft (`gmail_draft`/`gmail_send_draft`, `requires_approval=True`) exists. `pending_lead_preview` (closest analog to a resumable draft) is confirmed dead code — written but never read back (BUG-056/BUG-057). `_pending_approvals` (app.py) is in-memory, 10-minute TTL, not resumable across sessions | MISSING | No general resumable "draft tied to contact+channel+action_id" concept exists; the one attempt at it is dead code | NEEDS_C95 (see C96 below) — either build it deliberately or explicitly decide not to |
| 6 | Schema discovery / Airtable contract validation | Not named in any archive doc found; `CLAUDE.md`'s own description of the pipeline is the most complete source | `CLAUDE.md` §Schema validation & governance pipeline (accurate); `ROADMAP.md:1059` documents a live Assets-schema drift bug | `schema_audit.py` (standalone, consumed by `tools/schema_governance.py`), `schema_validator.py` (live in `tools/airtable_gateway.py:127`, non-blocking), `schema_intelligence.py` (live, owner-only `/schema` command), `tools/schema_governance.py` (wired into CI `|| true`, non-blocking), `audit_truth_gate.py` (GOV-02, called only from `daily_git_audit.py`, not per-request) | PARTIAL | Real, wired pipeline exists but every enforcement layer is explicitly non-blocking/best-effort; no pre-write hard gate | Keep, but consider making at least one layer hard-block for production tenant writes (see C97) |
| 7 | Knowledge Engine / Business Memory (adaptive rules, dynamic context, token budget) | `archive/BOSS_MASTER_PLAN_One_Road.md` §"Memory" row: "session + business memory + lead memory — קיים, חלקי" | `CLAUDE.md:116` explicitly lists `knowledge_engine.py` as code-complete but unimported; `ROADMAP.md:241` documents the actually-shipped alternative (C54 `/update` command) | `knowledge_engine.py` (Supabase-backed, token-budget logic, `adaptive_rules` table read) has **zero live callers** anywhere in the repo. The real live path is `core_knowledge.py` (`STATIC_MANIFEST` + `dynamic_context`, consumed by `context.py:87`) plus a separate Airtable-backed business-memory injection via `cmd_update.get_recent_business_context()` (`context.py:242-251`, capped at 600 chars, no token-budget math) | SUPERSEDED | The original Supabase Knowledge Engine design was replaced by a simpler Airtable `/update`-driven memory, but no doc records this as a deliberate architectural decision — it reads as an abandoned parallel build | DOC_SYNC_ONLY — record the supersession in ROADMAP/AI_CONTEXT so `knowledge_engine.py` isn't mistaken for live code again |
| 8 | Learning Loop / pattern mining / adaptive rules (debrief→pattern→proposed rule→approved rule→context improves) | `archive/BOSS_MASTER_PLAN_2026_v2.md` §7 "Month 3: Learning Engine"; `docs/governance/BOSS_UNIFIED_MASTER_PLAN_v2.md` Horizon 7 explicitly lists Learning Engine as "not now" | `CLAUDE.md:126,148`, `ROADMAP.md:939-944` (F02/F03/F04, explicitly gated on N04 + months of data) | `core/learning_engine.py` (real pattern extraction, `run_learning_cycle()`, but output is a display string only — no proposed-rule object, no write path); `data_engines.py` (explicit `TODO: from learning_engine import run_learning_cycle` — not even wired to the real module); `workers/survey_worker.py` (`send_won_survey`/`send_lost_survey` have **zero callers** anywhere); no `proposed_rule`/`adaptive_rule` concept with human approval exists anywhere in the codebase | DOC_ONLY / DROPPED_WITHOUT_DECISION (survey_worker specifically) | The deferral of learning-engine *activation* is documented and deliberate; but `survey_worker.py` being fully unwired (not even behind a flag check that fires) is undocumented dead code, and `data_engines.py` not even importing the real `learning_engine.py` is a separate, undocumented gap | Keep the deferral decision; separately flag survey_worker.py as orphaned (HIGH doc-sync gap) |
| 9 | Action IDs / pending actions / immutable audit trail | `archive/BOSS_MASTER_PLAN_One_Road.md` §"Approval Gate — קיים ✓" | `SPEC_LL13_Pending_Approval_Unification.md` (explicitly "Draft Spec — טרם ממומש", documents 4 independent mechanisms and mandates unification) | `core/action_gateway.py` (real `ActionContract`, `contract_id`, status enum, `business_action_fingerprint` dedup, wired into `app.py` 10+ call sites, but flag `FEATURE_ACTION_GATEWAY` off by default / shadow mode) coexists with `event_bus.py`'s older `PendingActionsStore` — **both live simultaneously**, contradicting SPEC_LL13's explicit prohibition on a "fifth mechanism." Audit trail also duplicated: `tools/airtable_security.py:audit_log_airtable()` vs `ActionGateway`'s own `ExecutionLedger._airtable_writer` (RAM-only until an `ActionContracts` Airtable table exists) | PARTIAL / DROPPED_WITHOUT_DECISION (on unification) | SPEC_LL13's unification mandate is not executed — the exact anti-pattern it names is currently live in production code | HIGH priority — see C95B/C96 |
| 10 | Queue / async workers (email/survey/learning workers, Redis/RQ-class queue) | `archive/BOSS_MASTER_PLAN_2026_v2.md` §7 "90 Day Roadmap" implies background automation; no explicit "Redis/RQ" text found in any archive doc — task's framing is the primary source here | No ROADMAP/AI_CONTEXT section discusses queue technology at all | `worker.py` — synchronous, Render-cron-triggered HTTP endpoint, no broker; `scheduler.py` — single-threaded blocking `schedule` library loop (all jobs share one thread, explicitly flagged as a stall risk in `daily_collector.py:15-18`); zero Redis/RQ/Celery/SQS anywhere in `requirements.txt` or imports | MISSING | No real async queue exists; if any scheduled job hangs, it stalls every other job behind it in the same thread | NEEDS_C95 (C95F) — decide if a real queue is warranted at current scale, or document that single-thread `schedule` is the deliberate choice |
| 11 | Morning cockpit report (finance, followups, stuck leads, pipeline, tasks, learning/debrief queue, insight) | `archive/BOSS_MASTER_PLAN_2026_v2.md` §4 "Daily Digest v2" as a near-term priority | `docs/governance/BOSS_UNIFIED_MASTER_PLAN_v2.md` H1.5 defines the desired digest content (hot leads, followups needing approval, today's tasks, anomalies/failures) | `daily_digest.py` produces 6 real sections (hot leads, today's followups, today's roadmap tasks, open deals, upcoming payments, yesterday's changes) — confirmed no stuck/old-lead section, no anomaly section, no learning/debrief section. `daily_collector.py` is a separate LLM-based end-of-day capture-verification scan, not a digest section. `weekly_summary.py` is a separate, unconnected weekly report | PARTIAL | Missing: stuck/aging leads, anomaly detection, and any learning/debrief queue visibility in the daily digest specifically | MEDIUM — see C95F |
| 12 | Lead/CRM data model (Contacts/Deals/Tasks/Expenses/Payments/Learnings, Contacts.Stage) | `archive/BOSS_MASTER_PLAN_GAP_ANALYSIS.md` — original master plan's data program list | No document found reconciling the current 3-way status split | Leads and Contacts are correctly non-duplicative (Leads=funnel, Contacts=relationship, linked via `Origin Lead`), but status/stage vocabulary has drifted into **three independent enums**: `LeadFields.STATUS`/`LeadStatus` (10 values), `ContactFields.STATUS` (4 Hebrew values), `DealFields.STAGE` (4 Hebrew values) — no single canonical "Stage" as the archive envisioned. Separately, `LeadEventFields` is fully spec'd in `airtable_schema.py` but `core/lead_events.py` actually writes to a `"Business Memory"` table instead — a spec/code mismatch | CODE_ONLY_NOT_DOCUMENTED / DROPPED_WITHOUT_DECISION | Three status vocabularies with no reconciliation doc; Lead Events schema vs. implementation mismatch | HIGH — see C95C |
| 13 | Marketing / attribution intelligence (source/campaign tracking, CPL, conversion) | `archive/BOSS_MASTER_PLAN_2026_v2.md` §4 "Finance Pulse with real data" (adjacent); `docs/governance/BOSS_UNIFIED_MASTER_PLAN_v2.md` H1.2/H2.1 define Source/Revenue Attribution explicitly | `docs/governance/BOSS_UNIFIED_MASTER_PLAN_v2.md:700` status table marks TRAFFIC_SOURCES as not-yet-done, dated 30/06/2026 | `ad_attribution.py` — real, code-complete UTM/CPL/ROI pipeline, wired into `app.py:2614` on WhatsApp inbound (flag `AD_ATTRIBUTION`, off by default; BUG-057 fix confirmed flag-gated). `lead_capture.py` writes a hardcoded `SOURCE` literal per channel, with real UTM fields written separately via `ad_attribution.record_lead_source()`. `TrafficSourcesFields`/`Tables.TRAFFIC_SOURCES` exists live in Airtable (confirmed via MCP 24/06/2026) but has **zero code wiring** — comment in `airtable_schema.py` says so explicitly. `audience_intelligence.py`'s "mock leads" claim from the old gap-analysis is no longer true in the live path (mock is test-scoped only now) | PARTIAL | Attribution pipeline is real but flag-gated off; the TRAFFIC_SOURCES table is a live orphan with a documented "not yet done" status that matches code reality (rare case of doc/code alignment on an unbuilt feature) | MEDIUM — see C95E; low urgency since doc and code agree here |

---

## 3. Detailed evidence by area

### A. Schema Discovery / Airtable Contract Validation — PARTIAL

- `airtable_schema.py` is the canonical, hardcoded schema source (`class Tables`, `*Fields` classes) — this is static, not dynamic discovery.
- `schema_audit.py` — standalone script ("סקריפט עצמאי — מריץ פעם אחת"), diffs live cache vs. `airtable_schema.py`; consumed by `tools/schema_governance.py:36`, not called from the runtime write path.
- `schema_validator.py` — **live in the write path**: `tools/airtable_gateway.py:17,127` (`_sv.validate_fields`), but explicitly non-blocking ("לא חוסם כשה-cache חסר — רק מלוגג אזהרה").
- `schema_intelligence.py` — live, but only as the owner-only `/schema` Telegram command (`app.py:386`), not an automatic gate.
- `tools/schema_governance.py` (N07) — wired into CI (`.github/workflows/ci.yml:46-47`), but `|| true` means it can never fail the build; also has a documented silent-skip gap for unregistered `*Fields` classes.
- `audit_truth_gate.py` (GOV-02) — real MAIN>CANONICAL>LIVE>DOCS verification, but only invoked from `daily_git_audit.py`'s cron path, not per-request.
- No dedicated test files beyond `test_airtable_gateway.py`'s coverage of the validator.
- `ROADMAP.md:1059` documents a live, unresolved Assets-schema drift bug — proof the underlying problem this pipeline exists to prevent is still occurring in practice.

**Verdict**: the original "discover, compare, report drift" intent is real and wired in five places, but is layered entirely in soft/warn-only enforcement. No hard pre-write gate exists.

### B. Contacts Brain — PARTIAL, flag off by default

- `tools/contact_resolver.py` (395 lines): `resolve()` checks `CONTACT_RESOLVER` flag; **when off, resolution is disabled** (not degraded) — returns `NOT_FOUND` telling the user to type an exact email.
- Ranking: real home-grown fuzzy scorer (`_score_match`, exact/startswith/substring/word-overlap/Jaccard fallback), thresholds `_SCORE_MIN=0.50`/`_SCORE_CONFIDENT=0.80`.
- Disambiguation: real — `ResolveStatus.AMBIGUOUS`, up to 5 numbered candidates.
- Aliases/nicknames: **not implemented** — only Hebrew niqqud-stripping normalization, no alias table.
- Preferred channel: **zero hits** for `preferred_channel` anywhere in the repo.
- Data source is brittle: regex-parses `crm.crm_list_contacts`'s emoji-formatted display string rather than a structured API, with a hardcoded `_mock_contacts()` fallback if the `crm` import fails.
- `contact_merge.py` confirmed standalone/offline, not dispatcher-wired (matches CLAUDE.md).
- Not mentioned as "Contacts Brain" or "contact resolver" in ROADMAP.md/AI_CONTEXT.md/BOSS_CURRENT_STATE.md at all.

### C. Draft Mode / Pending Message Actions — MISSING as a general concept

- Gmail draft (`gmail_send`→`gmail_draft`, then `gmail_send_draft`) is real and `requires_approval=True`, but it's a same-conversation, tool-specific mechanism — not a general "save as draft, resume days later" flow.
- `event_bus.PendingActionsStore` is generic but typeless — payload is opaque, no first-class contact/channel fields.
- `app.py`'s `_pending_approvals` is explicitly in-memory, 10-minute TTL, does not survive a restart (confirmed by `SPEC_LL13_Pending_Approval_Unification.md §0`).
- `session_store.PersistentSessionStore` has no `set_draft`/`get_draft` method — it's lead-qualifier-session-specific.
- The one real attempt at something like this, `pending_lead_preview`, is confirmed dead code — written but never read back (BUG-056/057), and the misleading "reply כן" CTA was removed rather than the resolver being built.
- No ROADMAP/AI_CONTEXT entry for "draft mode" as a named capability.

### D. Knowledge Engine / Business Memory — SUPERSEDED

- `knowledge_engine.py` (Supabase-backed, `MAX_TOKENS=12000` budget, `adaptive_rules`/`business_memory`/`deal_intelligence` reads) has **zero live callers** anywhere in the repo — confirmed dead/orphaned, and CLAUDE.md already documents this honestly.
- The actual live static+dynamic context layer is `core_knowledge.py` (`STATIC_MANIFEST` + `dynamic_context`, consumed by `context.py:87`) — no token-budget math here, just string concatenation plus a local `data.json` cache.
- A second, independent business-memory injection exists via `cmd_update.get_recent_business_context()` (Airtable-backed, 600-char cap, `context.py:242-251`) — this is the actually-shipped replacement (ROADMAP C54, merged PR #85), but no doc frames it as "the new Knowledge Engine" or explains why the Supabase design was abandoned.
- `core/request_context.py` is a per-request caching object, unrelated to knowledge/context building despite the naming proximity.
- `KNOWLEDGE_ENGINE` feature flag exists in the flag glossary but isn't in `_DEFAULTS` and has no live caller checking it besides the dead module itself.

### E. Learning Loop / Pattern Mining / Adaptive Rules — deferral is documented; some pieces are undocumented dead code

- `core/learning_engine.py` — real, statistics-only pattern mining (objection/success keyword frequency from `lead_events`) with self-tests, but output is a Telegram display string only. Comment explicitly marks "Phase 2 (future): wire into domain_prompts" as not built. No proposed-rule object, no write path, no approval flow anywhere.
- `data_engines.py` — confirmed stub exactly as CLAUDE.md describes; critically, it doesn't even call the real `core/learning_engine.py` — has an explicit `# TODO: from learning_engine import run_learning_cycle` left unresolved.
- `workers/survey_worker.py` — `send_won_survey`/`send_lost_survey` have **zero callers anywhere in the codebase**. This is undocumented dead code, distinct from the documented F02 deferral.
- `weekly_summary.py` and `daily_collector.py` are both real but serve different purposes (reporting and save-verification respectively) — neither performs "outcome collection for learning."
- No `proposed_rule`/`adaptive_rule` type with human-approval gating exists anywhere; the only `adaptive_rules` reference is the dead Supabase table lookup inside the orphaned `knowledge_engine.py`.
- The deferral itself (F02/F03/F04 blocked pending ~2-3 months of lead-event data) **is** documented consistently across CLAUDE.md and ROADMAP.md — this part is a deliberate, tracked decision, not a silent drop.

### F. Action IDs / Pending Actions / Audit Trail — PARTIAL, unification mandate unmet

- `core/action_gateway.py` (1,108 lines) is real: `ActionContract` with `contract_id`, status enum, `business_action_fingerprint` sha1 dedup; public API includes `propose_action`, `approve`, `route_confirmation_word`, `route_cancellation_word`, `route_disambiguation`, `route_combined_word`, `route_override_word`. Wired into `app.py` at 10+ call sites, but running in shadow mode (`FEATURE_ACTION_GATEWAY` off by default — "registers contracts but doesn't block").
- `SPEC_LL13_Pending_Approval_Unification.md` explicitly documents **four independent approval mechanisms** (`_pending_approvals`, `event_bus.PendingActionsStore`, TMA `Approvals` table, and a fourth) and mandates unifying into one durable Airtable-backed store, explicitly forbidding a "fifth mechanism." Its own header says "Draft Spec — not yet implemented."
- In practice, `action_gateway.py` was added *on top of* the existing mechanisms rather than replacing them — `event_bus.PendingActionsStore` is still live and referenced. This is precisely the "fifth mechanism" anti-pattern the spec warns against, now live in production code without anyone flagging the contradiction.
- Audit trail is similarly duplicated: `tools/airtable_security.py:audit_log_airtable()` vs. `ActionGateway`'s own `ExecutionLedger`, which is RAM-only until an `ActionContracts` Airtable table exists. No code reconciles which is authoritative.

### G. Queue / Workers — MISSING (no real queue technology)

- `worker.py` is a synchronous, Render-cron-triggered (`POST /worker/trigger`) HTTP handler — no broker, no persistence, no retry semantics beyond re-running the whole scan on the next 3-hour tick.
- `scheduler.py` uses the blocking, single-threaded `schedule` library — all jobs run sequentially in one daemon thread; a hang in one job stalls every other due job (explicitly acknowledged as a risk in `daily_collector.py`'s own comments).
- `workers/survey_worker.py` functions have zero callers anywhere.
- No Redis/RQ/Celery/SQS in `requirements.txt` or anywhere in the codebase.
- No ROADMAP/AI_CONTEXT section discusses queue technology as planned, decided-against, or dropped — it's simply never mentioned.

### H. Morning Cockpit Report — PARTIAL

- `daily_digest.py` generates 6 real sections: hot leads (Score≥50), today's followups, today's roadmap tasks, open deals, upcoming payments (7-day window), yesterday's changes summary.
- Missing relative to the original intent: no stuck/old-lead section, no anomaly/insight section, no learning/debrief-queue visibility.
- `daily_collector.py` (23:00) is a separate LLM-based "did we forget to save this" scan — not a cockpit section.
- `weekly_summary.py` is a separate, unconnected weekly report (feature-flagged off by default) — not merged into the daily digest.
- Scheduled at 07:30 (`DIGEST_TIME` env, default), collector at 23:00; both are now wrapped in `shabbat_safe(...)` in current `scheduler.py` — meaning the BUG-067 Shabbat-send issue documented in ROADMAP's 05/07/2026 entry appears to already be fixed in code, and the ROADMAP text describing it as open is stale on that specific point (the report-length and completed-task-detail issues from the same bug cluster were not confirmed fixed).

### I. Lead / CRM Data Model Drift — CODE_ONLY_NOT_DOCUMENTED

- Leads and Contacts are correctly distinct, non-duplicative tables (Leads = inbound funnel; Contacts = relationship rolodex; linked via `Origin Lead`).
- However, three independent status/stage vocabularies now exist where the archive envisioned one: `LeadFields.STATUS`/`LeadStatus` (10 English-keyword values), `ContactFields.STATUS` (4 Hebrew values), `DealFields.STAGE` (4 Hebrew values, this is actually where the closest analog to the old lead/contacted/proposal/negotiation/won/lost pipeline concept now lives). No document reconciles these three.
- `LeadEventFields` is fully specified in `airtable_schema.py` (dedicated "Lead Events" table, linked to Leads) but `core/lead_events.py`'s `LeadEventStore` actually reads/writes a completely different table, `"Business Memory"` — a genuine spec-vs-code mismatch, not just an unbuilt feature.
- Follow-up state lives in `lead_memory.py`, not in a dedicated Tasks/Roadmap_Tasks table; `Roadmap_Tasks` is a separate, unrelated internal dev/ops task table.
- Score/tier live in `LeadFields.SCORE`/`TIER`, but `score_display.py`'s parallel English 5-tier display scale is fully decoupled from those schema constants (no import of `airtable_schema` in that file) — a second silent vocabulary for the same concept, for display purposes only.
- No document (`ROADMAP.md`, `AI_CONTEXT.md`, `BOSS_CURRENT_STATE.md`, `docs/governance/ARCHITECTURE_DRIFT_MAP.md`) states which table/vocabulary is canonical.

### J. Marketing / Attribution Intelligence — PARTIAL, but doc/code agree on what's missing

- `ad_attribution.py` is a real, code-complete UTM/CPL/ROI pipeline (`parse_utm`, `build_attribution_report`, `cpl` property, quality scoring), gated by `AD_ATTRIBUTION` (off by default). Wired into `app.py:2614` on WhatsApp inbound, confirmed flag-checked after the BUG-057 fix.
- `lead_capture.py` writes a hardcoded `SOURCE` literal per channel (e.g. `"whatsapp_inbound"`); real per-campaign UTM data is written separately via `ad_attribution.record_lead_source()` — a two-write split, not a single coherent source field.
- `audience_intelligence.py`'s mock-data path is now test-scoped only (`_run_tests()`), not in the live `run_audience_scan` path — the older gap-analysis claim that it "can report mock leads" in production no longer matches current code.
- `Tables.TRAFFIC_SOURCES`/`TrafficSourcesFields` exists live in Airtable (confirmed via MCP 24/06/2026) with an explicit code comment "not yet referenced by any code module" — this is a rare case where code, schema comments, and the 30/06/2026 `BOSS_UNIFIED_MASTER_PLAN_v2.md` status table all agree it's simply not built yet. Low-urgency because doc and code are already in sync here.

---

## 4. Gap severity

| Gap | Severity | Why |
|---|---|---|
| ActionGateway/event_bus dual mechanisms (contradicts SPEC_LL13) | **BLOCKER** | Two independent approval-tracking systems live simultaneously creates a real risk of an action being approved in one system's view and not the other's — directly threatens "broken approvals" / false success claims that SPEC_LL13 was written to prevent |
| LeadEventFields spec vs. `core/lead_events.py` code mismatch (targets wrong table) | HIGH | Anyone reading `airtable_schema.py` to understand where lead events live will look in the wrong table; risks duplicate/conflicting event-logging code being written later |
| Three uncoordinated status/stage vocabularies (Leads/Contacts/Deals) | HIGH | Major schema drift risk — matches the CLAUDE.md-flagged "recurring failure mode"; a well-intentioned future feature could easily read the wrong status field |
| `survey_worker.py` fully unwired (zero callers) | MEDIUM | Dead code that looks live (has real Supabase persistence logic) — risk of someone assuming it's active and building on top of it |
| Schema governance pipeline is entirely non-blocking | MEDIUM | Defense-in-depth exists but nothing actually stops a bad write; matches the still-open Assets-schema-drift bug in ROADMAP |
| Draft mode / resumable pending actions missing | MEDIUM | Not a current production risk (nothing depends on it), but it's a named original capability with zero real implementation and no decision recorded |
| Contacts Brain: no aliases, no preferred-channel, flag off by default | MEDIUM | Feature works when explicitly enabled and tested; the gap is completeness, not safety |
| No real async queue (single-thread `schedule`) | MEDIUM | A hang in one scheduled job can stall the daily digest, followup scan, etc. behind it — an operational risk, not a data-integrity one |
| Daily digest missing stuck-lead/anomaly/learning sections | LOW | Digest is functional; this is a completeness gap, not a correctness one |
| Knowledge Engine (Supabase) orphaned without a documented supersession decision | DOC_SYNC_ONLY | Already correctly labeled dead in CLAUDE.md; just needs the "why" recorded once, low risk of confusion beyond that |
| TRAFFIC_SOURCES table exists but unwired | LOW | Doc and code already agree this is simply not-yet-built; no drift to fix |

---

## 5. Recommended carry-forward decisions

| Original capability | Decision |
|---|---|
| Deterministic core + reasoning layer | **Keep** — already tracked in ROADMAP; needs an explicit activation gate before it's wired into more live paths |
| Thin `app.py` | **NEEDS_DECISION** — either enforce it (CI line-count/complexity check) or formally retire the module rule so it stops reading as an unmet promise |
| Router/orchestrator separation | **Keep** — working as designed |
| Contacts Brain | **Keep** — code exists and is reasonable; needs aliases + preferred-channel before calling it done, and an owner decision on turning `CONTACT_RESOLVER` on |
| Draft mode | **Defer** — no safety-critical dependency exists yet; needs a deliberate design pass (precedence, storage, expiry) before building, not an ad hoc addition |
| Schema discovery/governance | **Keep** — but consider promoting `schema_governance.py`'s CI check from `|| true` to blocking for at least new-table/new-field additions |
| Knowledge Engine (Supabase design) | **Drop, formally** — record in ROADMAP that `core_knowledge.py` + `cmd_update.py`'s Airtable business memory is the shipped replacement; delete or archive `knowledge_engine.py` and its flag once that's recorded |
| Learning Loop / pattern mining | **Defer** (already the deliberate decision) — but separately: **Drop or wire** `workers/survey_worker.py` explicitly, don't leave it silently orphaned |
| Action IDs / ActionGateway | **Keep, but unify** — execute SPEC_LL13's mandate: pick one pending-action mechanism (most likely `action_gateway.py`, since it's the newer/richer one) and retire `event_bus.PendingActionsStore` or explicitly document why both must coexist |
| Queue/workers | **Defer with documentation** — record explicitly that single-threaded `schedule` is the deliberate current-scale choice, or size the risk of a real queue migration |
| Morning cockpit | **Keep, extend** — add stuck-lead and anomaly sections; low effort relative to value |
| Lead/CRM data model | **NEEDS_DECISION** — pick one canonical status vocabulary (or explicitly ratify that Leads/Contacts/Deals status fields are allowed to differ, and document the mapping between them) |
| Marketing/attribution | **Keep** — code and docs already agree; just needs `AD_ATTRIBUTION` flag activation and the TRAFFIC_SOURCES table wiring once revenue-loop priorities from the Unified Master Plan reach that horizon |

---

## 6. Recommended next SPECs

- **C95B — Lead Policy Engine**: resolve which status/stage vocabulary governs lead lifecycle decisions and how Leads/Contacts/Deals statuses map to each other.
- **C95C — Lead Data Model Reconciliation**: fix the `LeadEventFields` vs. `core/lead_events.py` table mismatch; decide whether "Lead Events" or "Business Memory" is canonical for event logging.
- **C95D — Followup & Tasks Layer**: clarify the relationship between `lead_memory.py`-based followup state and the `Roadmap_Tasks` table; decide if they should be unified.
- **C95E — Multi-channel Intake finalization**: wire `TRAFFIC_SOURCES` into `ad_attribution.py`, decide on `AD_ATTRIBUTION`/`CONTACT_RESOLVER` flag activation criteria.
- **C95F — Reports & Queues**: extend `daily_digest.py` with stuck-lead/anomaly sections; decide on `worker.py`/`scheduler.py`'s single-thread model vs. a real queue; resolve or remove `workers/survey_worker.py`.
- **C96 — Contacts Brain + Draft Mode**: add alias/nickname resolution and preferred-channel logic to `contact_resolver.py`; design (don't ad hoc) a real resumable draft-action concept if the business need still exists.
- **C97 — Schema Discovery / Schema Governance**: decide which layer(s) of the existing 5-module pipeline should become hard-blocking rather than warn-only, starting with new-table/new-field CI checks.
- **C98 — Knowledge + Learning Loop Carry-forward**: formally retire `knowledge_engine.py` (Supabase design) in favor of the shipped `core_knowledge.py`/`cmd_update.py` path; decide the fate of `workers/survey_worker.py`; keep the F02/F03/F04 data-driven deferral as-is.

---

## 7. Constraints honored

No code, Airtable schema, or ROADMAP.md changes were made while producing this report. All findings above are grounded in direct file reads/greps performed during this audit (see file:line citations throughout §3); items without direct evidence are marked NEEDS_VERIFICATION or explicitly noted as absent rather than assumed missing.
