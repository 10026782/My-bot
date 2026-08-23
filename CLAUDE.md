# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

"The Boss Bot" — a Hebrew-language Telegram/WhatsApp business assistant chatbot powered by Anthropic Claude (`app.py` is the Flask entrypoint, formerly `bot.py` per older docs — the live entrypoint is `app.py`). It serves multiple roles (owner, partner, manager, employee, lead, guest) across multiple business domains (real_estate, import, media, saas, finance, general), backed by Airtable as the CRM/data store, with optional Google Workspace, Twilio/WhatsApp, and a Telegram Mini App (TMA) frontend (`tma-frontend/`, React + Vite + TS).

Most comments, log messages, and docstrings in this codebase are in **Hebrew** — match that convention when editing existing files.

**Before doing task work**, read and follow the canonical Context Librarian bootstrap in `AGENTS.md` when its trigger scope applies. Do not duplicate or reinterpret that contract here. Read `AI_CONTEXT.md` only when the selected bundle cites it, the selected profile requires it, or an operational-state claim cannot be resolved from other current evidence. If `AI_CONTEXT.md` is stale (>7 days per its own header), do not trust it as production proof.

**Before opening a new branch**, run `bash pre_session_gate.sh "<task description>"` (see `AGENTS.md`). It blocks (`exit 1`) if there are unmerged `claude/*` branches against `origin/main`, to stop work from fragmenting across abandoned branches. Only pass `--force` if the user has explicitly approved opening a new branch anyway.

## Running locally

```bash
# Minimal — just the bot
ANTHROPIC_API_KEY=<key> TELEGRAM_TOKEN=<token> python3 app.py

# Full local dev with ngrok tunnel + webhook setup (requires .env from .env.example)
./run_local.sh
```

- Flask listens on `0.0.0.0:10000` by default (override with `PORT`).
- `TELEGRAM_TOKEN` must be in `<bot_id>:<secret>` format or `telebot.TeleBot()` raises `ValueError` at import time, preventing the server from starting.
- `startup_validator.validate_startup()` runs at import time in `app.py` and will hard-fail on missing critical env vars (see `.env.example` for the required set: `TELEGRAM_TOKEN`, `ANTHROPIC_API_KEY`, `ELIYAHU_CHAT_ID`, `AIRTABLE_API_KEY`, `AIRTABLE_BASE_ID`).
- `/status` and `/schema` Telegram commands are owner/admin-only diagnostics; `format_startup_message()` from `startup_validator` reports env var state.
- Always use `python3`, not `python` (may not be on PATH).

## Tests

There is no pytest/unittest harness wired up — tests are plain scripts with their own runners:

```bash
python3 smoke_tests.py        # static AST-based checks: imports resolve, required tools registered, no old table names, etc.
python3 test_integration.py   # Identity → Router → Decision flow, mocked, no Flask/Anthropic/DB
python3 -m py_compile app.py  # quick syntax check (no linter config exists in the repo)
```

`core/router/test_router.py` similarly exercises the router in isolation — run it directly with `python3 core/router/test_router.py`.

Other standalone test scripts, run the same way (`python3 <file>.py`):
- `test_airtable_gateway.py` — field normalization, validation, audit logging in `tools/airtable_gateway.py`.
- `test_approval_concurrency.py` — 3-state approval flow (pending → processing → approved/rejected) and double-approve race conditions.
- `test_furniture_lead_funnel.py` — the deterministic state machine in `furniture_lead_funnel.py`.
- `test_identity_smoke.py` — basic identity resolution sanity check.
- `test_a32_enforcement.py` — end-to-end `run_agent()` (Identity/Router/Context/Anthropic mocked) verifying the NO-TOOL-EVIDENCE gate blocks unverified "success" claims.
- `test_c53a.py` — the structured tool-result contract (`{ok, tool, external_id, evidence, user_message}`) introduced for the Screen Filter Gateway/Finance Pulse work.
- `test_inbound_handler.py` — dedup/update/create logic in `inbound_handler.py` (F06).

CI פעיל: `.github/workflows/ci.yml` runs on every PR and push to `main` — `backend-ci` (compileall syntax check, `smoke_tests.py`, core import check, every `test_*.py` script, schema governance as warning-only) and `frontend-ci` (builds `tma-frontend/` if present). No `Makefile`/`Procfile`.

When verifying behavioral changes to the webhook flow, start the server and POST simulated Telegram/WhatsApp webhook payloads with `curl` — there's no automated end-to-end suite.

## Architecture: Identity → Router → Context → Agent

Every inbound message in `app.py` flows through this fixed pipeline (see the comment block at the top of `app.py`):

```
resolve_identity → route_request → build_context → run_agent
```

1. **Identity** (`identity.py`): `resolve_identity(channel, external_id)` returns an `Identity` with a `role` (owner > partner > manager > employee > lead > guest > readonly, ranked via `Role.rank`), `tenant_id`, and `domain_id`. **"There is no action without identity."** Hard rule: `identity is None` must hard-fail, never silently fall back.
2. **Router** (`core/router/`): `route_request()` composes several sub-routers — `channel_router`, `domain_router`, `intent_router`, `risk_router` — into a single `RouteDecision` (`core/router/route_decision.py`) carrying `Intent`, `RouterDomain`, `Risk`, and a `Handler` (e.g. `AGENT`, `APPROVAL`, blocked/clarify flows). `app.py._safe_route()` wraps `route_request` with a fallback `RouteDecision`.
3. **Context** (`context.py`): `build_context()` assembles the system prompt / conversation context for the model, pulling in `domain_prompts.py` (per-domain prompt variants) and short-term memory from `memory_store.py`.
4. **Agent** (`run_agent` in `app.py`): drives the Claude tool-use loop (`MAX_TOOL_TURNS = 3`, `AGENT_TIMEOUT = 25`s), calling tools via the dispatcher and verifying outputs with `core.anti_hallucination` (`verify_execution`, `sanitize_agent_response`).

## Tool execution: Registry decides, Dispatcher executes

This is the security-critical core — **"Iron rule: no Tool without a permission check."**

- `tool_registry.py`: declarative metadata per tool (`ToolMeta`): `roles_allowed`, `tenant_scoped`, `requires_approval`, `high_risk`, `read_only`. `enforce(tool, identity)` from this module is the gate — it raises `ToolDenied` if the role isn't permitted.
- `tools/dispatcher.py`: the **single entry point** for all tool execution — `dispatch_tool(name, inputs, identity)`. Before routing to a concrete implementation it calls `action_validator.validate_action(tool, inputs)` (unknown-tool block → required-param presence check → structure/"9% rule" check) as a defense-in-depth gate independent of `tool_registry.enforce()`. It also performs dedup checks (`_DEDUP_FIELDS`), table-name aliasing (`_ALIAS_MAP`), and routes to the concrete tool implementations in `tools/` (drive, calendar, gmail, sheets, airtable, contact_resolver).
- `action_validator.py`: the param-shape gate described above — separate from, and in addition to, the role-based `tool_registry.enforce()` check.
- `tools/airtable_security.py`: `enforce_tenant_scope()` must be called before any raw Airtable read/write to prevent cross-tenant data leaks; `audit_log_airtable()` logs all access.
- `_MEMORABLE_TOOLS` in `app.py` lists tools whose results get persisted to memory across agent turns (e.g. `airtable_add`, `calendar_create_event`).
- **Never** import tool functions (e.g. from `crm` or `airtable_tools`) directly outside of the dispatcher/digest/scheduler/collector modules — this bypasses identity and tenant enforcement (see the grep check in `docs/governance/SECURITY_CHECKLIST.md`).

### Approval flow

High-risk/irreversible actions (`requires_approval=True` in the registry, e.g. `gmail_send_draft`, `crm_mark_payment_paid`) don't execute immediately. They route through `Handler.APPROVAL`:
- `app.py._queue_approval()` stores a pending action keyed by `chat_id` in `_pending_approvals` / `event_bus.pending` (`PendingActionsStore`/`EventBus` in `event_bus.py`).
- The user confirms/cancels with natural-language words from `_CONFIRM_WORDS` / `_CANCEL_WORDS` (Hebrew + English + emoji), handled in `_handle_approval_callback`, which **re-runs `enforce()` for the original requester** immediately before dispatching — never trust a stored decision blindly.

## Adding a new tool — checklist

(from `docs/governance/SECURITY_CHECKLIST.md`, required before merging)
1. Implement it in the relevant `tools/*.py` module.
2. Add its JSON schema to `tools/schemas.py`.
3. Register it in `tool_registry.py` with correct `roles_allowed` (and `requires_approval`/`high_risk`/`tenant_scoped` as needed).
4. Wire it into `tools/dispatcher.py`'s dispatch switch.
5. Run the grep checks in `docs/governance/SECURITY_CHECKLIST.md` (e.g. confirm every `case "..."` in the dispatcher has a matching registry entry).

## Other key modules

- `event_bus.py`: pending-action store + audit/event log used by the approval flow and lead-recovery features.
- `feature_flags.py`: runtime + env-based flags; the 5 canonical `EMERGENCY_STOP_*` flags are durably backed by Airtable via `EmergencyStopManager` (PATCH 3B) and survive restarts for real — `is_enabled()`/`set_flag()` are intercepted for exactly these names (`is_enabled()` delegates to `evaluate_emergency_stop()`, `set_flag()` raises `EmergencyStopLegacyWriteBlocked`); use `set_emergency_stop()`/`clear_emergency_stop()` to write them. The old `/tmp/emergency_flags.json` in-memory persistence mechanism this replaced no longer exists.
- `core/anti_hallucination.py`: post-hoc verification that the agent's claimed actions actually happened (`verify_execution`) and response sanitization (`sanitize_agent_response`).
- `core/lead_recovery.py`, `lead_qualifier.py`, `lead_memory.py`, `core/lead_events.py`: the lead lifecycle — qualification state machine, long-term memory, audit log, and recovery/follow-up logic.
- `crm.py`, `airtable_schema.py`, `airtable_tools.py`: the Airtable-backed CRM repository and table/field name constants — prefer the Hebrew table aliases defined here over hardcoded English names (see `_ALIAS_MAP` / `OLD_TABLE_NAMES` checks in `smoke_tests.py`).
- `scheduler.py`: background jobs (daily digest, overdue payments, cleanup, security reminders) registered via the `schedule` library and run on a background thread started from `app.py` (`start_scheduler`).
- `tma_api.py`: Flask blueprint registered onto the main app, serving the Telegram Mini App's REST API (projects, leads, approvals, game/quests, finance pulse). Auth is via `require_tma_auth` decorator validating Telegram `initData`.
- `config.py`: WhatsApp number → business domain mapping (`CHANNEL_DOMAINS`) — add new channel mappings only here.
- `guards/`: `idempotency`, `rate_limiter`, `circuit_breaker` — cross-cutting reliability wrappers re-exported from `guards/__init__.py`.
- `core_knowledge.py`: the system prompt's static manifest + dynamic per-call context (`STATIC_MANIFEST`, `dynamic_context`), consumed by `context.py`.
- `llm_fallback.py`: `call_anthropic_text()` wraps direct (non-tool-loop) Anthropic text calls used by `daily_collector.py`, `creative_generator.py`, `lead_qualifier.py`, `tma_api.py`; optional OpenAI fallback behind the `LLM_FALLBACK` flag (off by default).
- `session_store.py`: `PersistentSessionStore`/`lead_sessions` — DB-backed (Airtable) lead qualifier session state, replacing an in-memory LRU store; always-on infra, not flag-gated. Consumed by `lead_qualifier.py`, `furniture_lead_funnel.py`, `interaction_engine.py`.
- `score_display.py`: lead temperature scoring → 5-tier display (COLD → BOILING); `format_lead_report`/`format_score_inline` consumed by `lead_qualifier.py` and `audience_intelligence.py`.
- `shabbat_guard.py`: always-on (no flag) Shabbat/holiday quiet-hours guard — `should_send_now`/`next_allowed_time`/`shabbat_safe` consumed by `scheduler.py`, `voice_adapter.py`, `daily_digest.py`, `abandoned_lead_worker.py` to suppress outbound sends.
- `cmd_update.py`: `/update`/`/עדכון` Telegram command (`FEATURE_BUSINESS_UPDATE` flag, registered in `feature_flags.py`'s registry docstring) for manually logging business context to Airtable; read back by `context.py` as injected per-domain context.
- `inbound_handler.py`: F06 inbound-lead gate in front of `lead_capture.py` — dedups by `external_id`, updates existing leads by `sender_id`, else creates a new lead; used by `email_inbound.py`. See `test_inbound_handler.py`.
- `daily_collector.py` / `daily_digest.py` / `payment_reminder.py`: scheduled jobs invoked (via lazy import) from `scheduler.py` — end-of-day business-data collector w/ Telegram approval buttons, the 08:00 morning digest, and the `PAYMENT_REMINDERS`-gated due-soon payment scanner, respectively.
- `contact_merge.py`: standalone offline CLI (not a dispatcher tool — no identity/tenant context, never touches Airtable directly) merging Google Contacts CSV exports and `.vcf` files from multiple sources into one Airtable-`Contacts`-ready CSV, deduping by normalized Israeli phone number. Run manually before a CSV import.
- `scripts/classify_contacts_for_airtable.py`: standalone offline CSV/VCF contact classifier (own parser, no shared code with `contact_merge.py`) — assigns `Role Category`/`Specialty` via Hebrew keyword rules with confidence scoring and review-required flagging (multi-role conflicts, ambiguous tokens, unnormalizable phones, supplier-like contacts), dedups by normalized phone, and writes import-ready/review-required/supplier-review CSVs + an `.xlsx` + a markdown summary to `--outdir`. `--owner`/`--referred-by` are required, written into every row as output-only columns (not live Airtable `Contacts` fields yet). See `test_classify_contacts_for_airtable.py`.
- A few modules are code-complete but **not currently imported by anything in the live pipeline** (verify with grep before assuming they're wired in): `profile.py` (Airtable-backed long-term user profile), `project_timeline.py` (Airtable timeline table generator, has its own CLI), `tenant_provisioner.py` (F08 `MULTITENANT` provisioning), `creative_generator.py` (`CREATIVE_GENERATOR` flag), `knowledge_engine.py`/root-level `router.py` (Supabase-backed dynamic context, `KNOWLEDGE_ENGINE` flag), `core/tenant_config.py` + `providers/` (F13 — `TenantConfig` + `StorageProvider`/`LLMProvider`/`ChannelAdapter` shims, code-complete per ROADMAP.md F13 but zero imports from any live module; overlaps undecided with F12's own planned `providers/` proposal — don't wire either in without resolving that first).

### `tools/` — concrete tool implementations behind the dispatcher

`tools/dispatcher.py` is the entry point (see above); the actual integrations it calls into live alongside it: `airtable_tools.py`/`airtable_gateway.py`/`airtable_security.py` (Airtable reads/writes + tenant enforcement + audit logging), `contact_resolver.py` (lead/contact dedup matching), `google_tools.py` (shared OAuth flow) with per-service files `gmail_tools.py`, `calendar_tools.py`, `drive_tools.py`, `sheets_tools.py`, and the outbound channel adapters `telegram_adapter.py` / `whatsapp_adapter.py`. `tools/schemas.py` holds the JSON tool schemas required by step 2 of the "Adding a new tool" checklist.

### `core/` — cross-cutting gates beyond the router

- `core/cost_watchdog.py`: tracks hourly/daily Claude token spend (persisted to JSONL + Airtable) and auto-triggers `EMERGENCY_STOP_AI` if a cost threshold is exceeded; `cost_monitor.py` at the repo root logs the per-call token counts it consumes and drives the live trigger — both unchanged and still authoritative. `core/usage_telemetry.py` (PostgreSQL `usage_events`, see `core/migrations/002_usage_events.sql`) is a **shadow-only**, provider/service/model-generic recording point added alongside these — every Anthropic/OpenAI text call and OpenAI Whisper STT call additionally records through it via `core/model_pricing.py`'s canonical pricing table, but nothing reads from it yet; it exists to accumulate real data before a later cutover of `AI_Usage_Daily`/the trigger onto it.
- `core/emergency_window.py`, `core/otp.py`, `core/financial_gate.py`: the (currently flag-gated, `EMERGENCY_WINDOW`) Approval Policy stack — a temporary override window for high-risk approvals, an OTP request/verify flow, and an escalate-not-block gate for detected financial commitments. `Approval_Policy_Spec.md` is referenced from `AI_CONTEXT.md`/`BUG_AUDIT_LOG.md` but doesn't currently exist in the repo; check `AI_CONTEXT.md` for current activation status before assuming this is live. `APPROVAL_SYSTEM_AUDIT_AND_C53_SPEC.md` (different doc — a post-hoc architecture audit of all 4 approval mechanisms + planned C53 test harness, not the original build spec) does exist, but is dated 17/06/2026 and its file:line claims aren't re-verified against current code.
- `core/learning_engine.py`: read-only pattern extraction from `lead_events` (F02) — intentionally inert until ~2-3 months of lead-event data accumulates.
- `core/output_gateway.py`: second-layer outbound guard distinguishing INTERNAL vs CUSTOMER-facing audiences before a message is sent.
- `health_monitor.py`: checks Airtable connectivity, scheduler thread liveness, and emergency-flag state; backs the `/status` endpoint.
- `boss_doctor.py`: Phase 1 read-only diagnostic aggregator ("boss doctor") — `run_doctor()` composes existing signals only (`tool_registry.get_availability()`, `feature_flags` accessors, `health_monitor.get_health_status()`, `core/atomic_claims_health.py`, `schedule.jobs`) into a `DoctorReport` of `DiagnosticCheck(name, status, code, detail, source)` rows with a fixed `OK`/`DEGRADED`/`UNAVAILABLE`/`UNKNOWN` status vocabulary; `format_report()` renders a short operator summary. Distinguishes `configured` (env presence) from `runtime-observed` (live probe, Airtable only) from `production-verified` (not attempted — always reported as "not checked"); never repairs, mutates, changes a flag, or calls the dispatcher/ActionGateway. No command is wired to it yet (no owner-only entrypoint) — see `test_boss_doctor.py` and `docs/research/HERMES_DEFERRED_PATTERNS_REVISIT_2026-08.md` ("boss doctor" pattern) for the design rationale.

### Schema validation & governance pipeline

Airtable field/table drift is a recurring failure mode in this repo, so there's a dedicated pipeline: `airtable_schema.py` is the canonical source of table/field names in code; `schema_audit.py` diffs that against the live Airtable schema and refreshes `schema_cache.json`; `schema_validator.py` and `schema_intelligence.py` use that cache to validate fields before writes; `audit_truth_gate.py` (GOV-02) is the higher-level gate comparing main's commit hash, the canonical schema, and the live Airtable base, blocking or downgrading to read-only if any of those are unverifiable. `system_registry.yaml` + `system_registry_audit.py` audit overall service status into `reports/` (auto-generated — don't hand-edit). `daily_git_audit.py` and `branch_cemetery_cleanup.py` report/clean up stale unmerged `claude/*` branches (the same condition `pre_session_gate.sh` checks at session start).

`core/runtime_schema_provider.py` (PR3B, `RuntimeSchemaProvider`): the live schema read path — resolves fresh Meta API → last-good in-memory → latest snapshot archive record → `schema_cache.json` seed, in that priority order; captures field type + select choices, not just names. Three-state flag `FEATURE_AIRTABLE_RUNTIME_SCHEMA_PROVIDER_STATE` (`off`/`shadow`/`enforce`, read via `get_runtime_schema_provider_state()`, not `is_enabled()`). `tools/schema_snapshot.py` (PR3A): flag-gated (`FEATURE_AIRTABLE_SCHEMA_SNAPSHOT`) scheduler job that archives the live Meta API schema (with table/field IDs) as JSON+XLSX to an Airtable snapshot table, feeding the provider's fallback chain. `tools/check_airtable_schema_runtime.py` (PR3C): manual on-demand diagnostic CLI (no scheduler job, no flag) — `python3 tools/check_airtable_schema_runtime.py`. See `docs/governance/AIRTABLE_SCHEMA_GOVERNANCE.md` for how these four layers compose, what each one's `Closes:` scope actually covers, and why they don't supersede the sentinel/structural checks listed above.

### Lead lifecycle & growth features (mostly feature-flag gated)

Several modules are code-complete but disabled by default via `feature_flags.py` — check `AI_CONTEXT.md`'s "Known gaps" table for current on/off state before assuming any of these are active in production. `feature_flags.py`'s own module docstring is meant to be the single registry of every flag checked in code ("every flag must appear here") — treat it as the first place to check for a flag's default/purpose, but verify against an actual `is_enabled("X")` grep, since it has drifted before (e.g. `FEATURE_BUSINESS_UPDATE`, used by `cmd_update.py`, was missing from the docstring list until it was registered).

- `lead_capture.py` (`LEAD_CAPTURE`/`LEAD_SCORING`): inbound WhatsApp/Telegram lead creation with optional live scoring.
- `lead_conversion.py` (`LEAD_AUTO_CONVERT`): owner-only `/convert` command promoting qualified leads to contacts.
- `abandoned_lead_worker.py` (`ABANDONED_LEADS`): detects leads stuck mid-qualification and auto-bounces or escalates them.
- `followup_engine.py` (`FOLLOWUP_AUTOMATION`): identifies "ripe" leads, drafts follow-ups, and routes them through approval.
- `furniture_lead_funnel.py`: a separate, deterministic WhatsApp funnel for a specific product line (not the general agent flow) — see `test_furniture_lead_funnel.py`.
- `voice_adapter.py` (`FEATURE_VOICE_IVR`/F07): Twilio Voice IVR state machine for lead qualification.
- `email_inbound.py` (`EMAIL_INBOUND`/F06): polls Gmail and routes inbound mail through identity → approval → reply.
- `interaction_engine.py` (`INTERACTION_INTELLIGENCE`/D06.1): unified interaction log across calendar/email/WhatsApp.
- `audience_intelligence.py` (`AUDIENCE_INTELLIGENCE`/D04): segmentation, high-value/churn detection, lookalike matching.
- `ad_attribution.py` (D05): UTM/campaign source tracking, consumed at lead-intake time via `app.py`'s `_inject_utm`.
- `data_engines.py`: stubs for F02/F03/F04 (learning, attribution, KPI) intentionally blocked pending more historical data.

### Background workers

- `worker.py`: the proactive background worker hit by Render's Cron trigger (`POST /worker/trigger`, scheduled ~08:00/18:00) for routine async tasks.
- This is distinct from `scheduler.py`'s in-process `schedule`-library jobs (digest, overdue payments, cleanup) started from `app.py`.

## Frontend (`tma-frontend/`)

React + TypeScript + Vite + Tailwind Telegram Mini App.

```bash
cd tma-frontend
npm run dev       # vite dev server
npm run build     # tsc && vite build
npm run preview
```

## Planning & docs conventions

- `docs/governance/BOSS_BUSINESS_INTENT.md` is the owner-authored, single source of truth for business *intent* (what BOSS is for, the golden-rule test before any feature, the agent's allowed/forbidden scope, the Librarian's role) — not for implementation status. Changing it requires an explicit owner decision (see its own "Change policy"). `ROADMAP.md` and `docs/governance/BOSS_UNIFIED_MASTER_PLAN.md` govern *what's being built and when*; this document governs *why and for whom*.
- `ROADMAP.md` is **the single source of truth** for planned work — "every batch starts by reading the ROADMAP, not from memory." Other planning docs (`BOSS_MASTER_PLAN_*.md` in `archive/`, `BOSS_CURRENT_STATE.md`, `boss_bot_summary.md`) are archives/snapshots, not authoritative. A `ROADMAP.md` change isn't done until the `עודכן:` date at the top of the file is also bumped (see `AGENTS.md`).
- `AI_CONTEXT.md` is the live production-state doc (see top of this file) — read it before trusting any "is X live/active" assumption.
- `docs/governance/SECURITY_CHECKLIST.md` defines when a security review is required (new file touching `dispatcher`/`crm`/`identity`/`auth`, new tool, new role, new endpoint) and the manual checklist + grep patterns to run before merging to main — consult it whenever touching identity, tenancy, registry, or endpoint auth.
- `docs/governance/CROSS_LAYER_GOVERNANCE_REVISED_PLANNING_GATE.md` is the mandatory Cross-Layer Planning Gate: every implementation records a lightweight assessment; `NONE` is for proven local changes, `SINGLE-LAYER` for an owned single-layer contract change, `FULL` for authority/contract/lifecycle/evidence/persistence/routing/runtime-wiring/fallback/multi-layer triggers, and `UNCERTAIN` fails closed to the FULL path or architecture review. `docs/architecture/CROSS_LAYER_AUTHORITY_CONTRACT_V1.md` remains authoritative for ownership boundaries and prohibitions, but no longer imposes a blanket full-matrix rule.

- `docs/governance/MODULE_RULES.md` and `docs/governance/ARCHITECTURE_DRIFT_MAP.md`: module-interaction rules and known drift between code intent and the live Airtable schema.
- `docs/governance/MIGRATION_AIRTABLE_ENGLISH_SCHEMA.md`: background on the Hebrew→English Airtable field/table migration referenced by the `_ALIAS_MAP` aliasing layer.
- `docs/operations/DEPLOYMENT.md` and `docs/operations/RUNBOOK.md`: Render deploy/rollback process and the production runbook (health checks, emergency stop, scaling) — consult before claiming a change is "deployed."
- `AGENTS.md` covers the pre-session branch gate and the ROADMAP "definition of done"; treat its older "Cursor Cloud specific instructions" section (single-file app, no tests, no `/` route) as stale/historical — the rest of this file describes the current state. It also defines the **post-merge verification protocol** (sync `main`, grep every changed symbol, "merged" must be proven by grep on `main`, not by `git log`/PR status) and **Rule 15** (no "fixed"/"deployed"/"completed" claim without merge+deploy+production verification).
- `GOVERNANCE_RULES.md` (Rules 13-18, referenced from `AGENTS.md`): audits must be based on `main`/production state, audits can't modify code, no claim without verification, root-cause-before-fix, one authoritative status source, and fix-the-process-not-just-the-incident for repeat incidents.
- `CHANGE_CONTROL_LOG.md` and `BUG_AUDIT_LOG.md`: append-only, auto/manually-updated logs of merged changes and bugs from report through production verification — don't hand-edit history, append new entries.
- `RELEASE_CHECKLIST.md` and `CHANGELOG.md`: the pre-merge PR checklist (ROADMAP ID, single main file per feature, flag default-off, writes go through `airtable_gateway.py`) and the running unreleased-changes log.
- `.claude/skills/CLAUDE_SKILLS.md` describes a Developer/Operator Claude Skills architecture with `dev/` and `operator/` subdirectories under `.claude/skills/` — as of this writing those subdirectories **don't exist on disk**, only the index file does; treat the skills system as aspirational/documented-but-not-built rather than live.

## כלל ברזל — "סיימתי" = מאומת, לא מוצהר

לפני שמדווחים "✅ הושלם" / מסמנים ✅ בכל מסמך, חובה להריץ ולהציג בפלט:

1. `git log -1 --oneline` — commit קיים מקומית
2. `git push` בוצע בפועל (לא רק `git commit`) — הצג את הפלט
3. אם הפיצ'ר תלוי ב-Render deploy: commit hash ב-Render dashboard מול origin/main
4. אם רלוונטי — ציין מצב flag נוכחי ב-Render env (LEAD_SCORING, LEAD_MEMORY וכו')

עדכון מסמך ל-✅ מותר **רק אחרי** ש-1-2 עברו ומוצגים. **חוסר אימות = ✅ FALSE.**

תבנית חובה לסוף כל task:
```
STATUS: [✅ VERIFIED IN PROD | 🟡 CODE DONE, NOT VERIFIED | ❌ FAILED]
EVIDENCE: <commit hash, push output>
```
