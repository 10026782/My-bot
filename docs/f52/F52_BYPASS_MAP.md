# F52 Bypass Map

Updated: 03/07/2026 — added `cmd_decision.py:700` (`route_file_to_decision_inbox`), a Drive-upload bypass in the same Route/Controller family as `_handle_telegram_media`/`tma_upload`/`media_handler.py`, missed in the original scan (see C89/F52 scope-verification thread).

Scope: audit-only map of current places where code bypasses one or more F52 contract layers. This document does not change production behavior, refactor code, modify `app.py`, or change Airtable schema.

Source context:

- `docs/f52/F52_CURRENT_TOOL_MAP.md`
- `docs/f52/F52_CONTRACT_COVERAGE_MAP.md`
- Static scans of `app.py`, `tma_api.py`, `crm.py`, `tools/`, media, lead/session, scheduler, and provider adapter modules

Contract layers audited:

- Tool Registry
- Action Validator
- Dispatcher
- Tool Gateway
- Output Validation
- A32 / proof gate
- Approval policy
- Durable Last Tool Result

Risk legend:

- 🟢 low: intentional/internal read or audit-only flow with low production consequence
- 🟡 medium: bypass exists, but mostly read-only or locally constrained
- 🟠 high: write/send/state mutation bypass with partial checks or weak proof
- 🔴 critical: direct provider write/send/delete path with weak or split approval/proof controls

## 1. Executive Summary

The BOSS codebase has a real agent tool spine: Claude-facing schemas, registry metadata, input validation, `dispatch_tool`, output validation, A32 proof checks, and per-turn claim sanitization. That spine is strongest for a small set of agent-visible write/send tools such as `gmail_draft`, `gmail_send_draft`, `calendar_create_event`, `airtable_add`, and `airtable_update`.

The bypass surface is still broad. The largest bypass families are:

- TMA routes in `tma_api.py`, which perform read/write/game/approval/media actions outside `dispatch_tool`.
- Direct Airtable REST calls in `crm.py`, `tma_api.py`, `daily_digest.py`, `tools/dispatcher.py`, `tools/airtable_tools.py`, and provider shims.
- Telegram command handlers in `app.py`, which are operational commands but not modeled as tools.
- Media flows in `app.py` and `media_handler.py`, which use local result dataclasses but not the generic `ToolResult` contract.
- Lead/session persistence flows that infer success from strings, `✅`, and `rec\w+` regex parsing.
- Scheduler/background jobs that send messages, scan state, update game/lead flows, or invoke agents outside the tool contract.

The most important F52 gap is not only missing dispatch. It is missing durable evidence. Current success proof is mostly per-turn and in-memory (`tool_results_log`) or embedded in provider response strings. There is no consistent durable Last Tool Result record that later code can use as proof.

## 2. Bypass Categories

### Direct Provider Bypass

Code calls provider APIs directly instead of using a governed gateway or adapter. This is most visible for Airtable REST calls using `httpx.get`, `httpx.post`, and `httpx.patch` outside `tools/airtable_gateway.py`.

### Route / Controller Bypass

HTTP routes and Telegram handlers perform tool-like operations directly. These paths can mutate Airtable records, send messages, create tasks, update game state, and process approvals without going through the agent tool registry, action validator, or dispatcher.

### Local Result Shape Bypass

Several modules return strings or local dataclasses instead of the generic structured tool result expected by A32-style proof gates. This makes it harder to distinguish successful external side effects from formatted user messages.

### String Proof Bypass

Some persistence code treats `"✅"` or a `rec\w+` regex match as success proof. This is fragile because display strings become an implicit API.

### Approval Policy Bypass / Mismatch

Approval rules are split across `tool_registry.py`, `event_bus.py`, and `app.py`. Some non-agent flows implement their own approval or owner checks, while other flows mutate state without the same centralized policy.

### Background Job Bypass

Scheduler and worker jobs perform read/send/write/background operations outside the tool contract. Some of these jobs are safe reports, while others touch lead recovery, payment reminders, game state, or external messaging.

### Durable Evidence Bypass

Even when a path has structured output or local receipt records, there is no uniform persisted Last Tool Result contract. Evidence is partial, flow-specific, or only present in Airtable business tables.

## 3. Full Bypass Table

| File path | Function / route / handler | Provider involved | Bypassed layer(s) | Mode | Risk | Why it matters | Suggested future handling |
|---|---|---|---|---|---|---|---|
| `app.py` | module startup webhook setup | Telegram | Tool Registry, Action Validator, Dispatcher, Output Validation, A32, Durable Last Tool Result | send | 🟡 | Startup sends a Telegram webhook request outside any contract; expected operational side effect at import/startup. | document only |
| `app.py` | `@bot.message_handler(commands=["status"])` | Telegram / app state | Tool Registry, Action Validator, Dispatcher, Output Validation, A32, Durable Last Tool Result | read | 🟡 | Operational command exposes status outside tool schema and no normalized result. | wrap |
| `app.py` | `@bot.message_handler(commands=["schema"])` | Airtable schema / Telegram | Tool Registry, Action Validator, Dispatcher, Output Validation, A32, Durable Last Tool Result | read/send | 🟡 | Schema introspection is command-only and bypasses current tool contract. | adapter |
| `app.py` | `@bot.message_handler(commands=["done"])` | Game / Airtable / Telegram | Tool Registry, Action Validator, Dispatcher, Output Validation, A32, Durable Last Tool Result | write/send | 🟠 | User-visible state mutation is command-driven, not governed by registry or proof contract. | design review |
| `app.py` | `@bot.message_handler(commands=["convert"])` | Telegram / conversion helpers | Tool Registry, Action Validator, Dispatcher, Output Validation, A32, Durable Last Tool Result | write/send | 🟡 | Conversion command is tool-like and sends results without normalized tool evidence. | wrap |
| `app.py` | `@bot.message_handler(commands=["quest"])` | Game / Airtable / Telegram | Tool Registry, Action Validator, Dispatcher, Output Validation, A32, Durable Last Tool Result | read/write/send | 🟠 | Game operations can affect persistent state outside the tool contract. | design review |
| `app.py` | `@bot.message_handler(commands=["coins"])` | Game / Airtable / Telegram | Tool Registry, Action Validator, Dispatcher, Output Validation, A32, Durable Last Tool Result | read/send | 🟡 | Reads and reports persistent game state without normalized result/evidence. | wrap |
| `app.py` | `_handle_approval_callback_impl` | Event bus / tools / Telegram | Registry and Dispatcher for non-tool approvals, Output Validation, A32, Durable Last Tool Result | write/send | 🟠 | Tool approvals use the dispatch spine, but other approval actions can route through event bus semantics outside the tool contract. | design review |
| `app.py` | `_handle_telegram_media` | Telegram / Drive / Airtable / STT | Tool Registry, Action Validator, Dispatcher, generic ToolResult, A32, Durable Last Tool Result | write/send | 🟠 | Media ingestion has side effects and proof, but not via the generic F52 result contract. | adapter |
| `app.py` | `/telegram` webhook route | Telegram / agent loop | Route itself bypasses Tool Registry; tool calls inside agent loop use dispatcher | background/send | 🟡 | Webhook routing, slash-command delegation, and direct message handling mix tool and non-tool flows. | document only |
| `app.py` | `/whatsapp` route | Twilio / WhatsApp / lead flows | Tool Registry, Action Validator, Dispatcher, Output Validation, A32, Durable Last Tool Result | read/write/send | 🟠 | Inbound messaging can trigger lead/session capture outside agent tool contracts. | design review |
| `app.py` | `/webhooks/meta/whatsapp` route | Meta WhatsApp / lead flows | Tool Registry, Action Validator, Dispatcher, Output Validation, A32, Durable Last Tool Result | read/write/send | 🟠 | Meta webhook path can trigger message and lead handling without tool normalization. | design review |
| `app.py` | `/worker/trigger` route | Worker / scheduler | Tool Registry, Action Validator, Dispatcher, Output Validation, A32, Durable Last Tool Result | background | 🟠 | Background trigger can run proactive work outside centralized contracts. | design review |
| `app.py` | `/voice/incoming`, `/voice/step` routes | Twilio Voice | Tool Registry, Action Validator, Dispatcher, Output Validation, A32, Durable Last Tool Result | send/background | 🟡 | Voice routes perform external provider interactions without tool result persistence. | adapter |
| `tma_api.py` | `_at_list` | Airtable | Tool Gateway, Dispatcher, Output Validation, A32, Durable Last Tool Result | read | 🟠 | Direct Airtable reads duplicate gateway/provider logic and return raw record shapes. | gateway |
| `tma_api.py` | `_at_get_record` | Airtable | Tool Gateway, Dispatcher, Output Validation, A32, Durable Last Tool Result | read | 🟠 | Direct record reads bypass output normalization and durable evidence. | gateway |
| `tma_api.py` | `_at_patch` | Airtable | Tool Registry, Action Validator, Dispatcher, Output Validation, A32, Durable Last Tool Result | write | 🟠 | Writes use the Airtable gateway internally, but route-level policy/proof remain outside agent contract. | wrap |
| `tma_api.py` | `_gw_patch` / `_gw_create` style route helpers | Airtable gateway | Tool Registry, Action Validator, Dispatcher, Output Validation, A32, Durable Last Tool Result | write | 🟠 | Gateway helps provider safety, but no registry, generic output validation, or durable Last Tool Result. | adapter |
| `tma_api.py` | `create_project` route | Airtable | Tool Registry, Action Validator, Dispatcher, Output Validation, A32, Durable Last Tool Result | write | 🟠 | Project creation is a tool-like state mutation outside agent contracts. | wrap |
| `tma_api.py` | `update_lead_status`, `patch_lead`, `set_lead_outcome` routes | Airtable | Tool Registry, Action Validator, Dispatcher, Output Validation, A32, Durable Last Tool Result | write | 🔴 | Lead state mutation is high-impact business state and bypasses centralized proof/approval. | design review |
| `tma_api.py` | `create_lead_task`, `create_followup` routes | Airtable | Tool Registry, Action Validator, Dispatcher, Output Validation, A32, Durable Last Tool Result | write | 🟠 | Follow-up/task creation can later drive outbound behavior without normalized proof. | wrap |
| `tma_api.py` | `ask_ai` route | Anthropic / app context | Tool Registry, Action Validator, Dispatcher, Output Validation, A32, Durable Last Tool Result | read/background | 🟡 | AI route is outside the agent tool spine and may form claims without the same A32 evidence flow. | design review |
| `tma_api.py` | `finance_pulse`, `owner_health`, `owner_control_center`, `activity_feed` routes | Airtable / reports | Tool Gateway for reads, Dispatcher, Output Validation, A32, Durable Last Tool Result | read | 🟡 | Owner dashboards read operational data through route-specific logic, not normalized tool results. | document only |
| `tma_api.py` | `bulk_approve`, `act_on_approval` routes | Event bus / Airtable / TMA | Tool Registry, Action Validator, Dispatcher for non-tool actions, Output Validation, A32, Durable Last Tool Result | write/send | 🟠 | Approval execution path is parallel to agent tool approval and can drift from central policy. | design review |
| `tma_api.py` | `update_asset` route | Airtable | Tool Registry, Action Validator, Dispatcher, Output Validation, A32, Durable Last Tool Result | write | 🟠 | Asset mutation affects persistent media/business records without F52 result. | wrap |
| `tma_api.py` | `create_venture`, `update_venture` routes | Airtable | Tool Registry, Action Validator, Dispatcher, Output Validation, A32, Durable Last Tool Result | write | 🟠 | Venture records are core business state and route writes are outside centralized contract. | wrap |
| `tma_api.py` | `system_health` route | Airtable Meta / system | Tool Gateway, Dispatcher, Output Validation, A32, Durable Last Tool Result | read | 🟡 | Direct health checks call Airtable APIs outside provider gateway; low mutation risk. | document only |
| `tma_api.py` | `emergency_stop` route | App / persistent control | Tool Registry, Action Validator, Dispatcher, Output Validation, A32, Durable Last Tool Result | write/background | 🔴 | Safety-critical control plane action should have explicit contract, approval, and durable proof semantics. | design review |
| `tma_api.py` | `update_quest`, `complete_daily_task`, `update_checkin_task_status`, `game_checkin_put` routes | Airtable / game state | Tool Registry, Action Validator, Dispatcher, Output Validation, A32, Durable Last Tool Result | write | 🟠 | Persistent gamification writes bypass the same proof and approval model as tools. | design review |
| `tma_api.py` | `tma_upload` route | TMA / Drive / Airtable / media | Tool Registry, Action Validator, Dispatcher, generic ToolResult, A32, Durable Last Tool Result | write | 🟠 | Upload flow uses media result types, but not generic tool output or durable Last Tool Result. | adapter |
| `crm.py` | `_get` | Airtable | Tool Gateway, Dispatcher, Output Validation, A32, Durable Last Tool Result | read | 🟠 | CRM reads use direct Airtable REST instead of the existing gateway. | gateway |
| `crm.py` | `_post` | Airtable | Tool Gateway, Tool Registry, Action Validator, Dispatcher, Output Validation, A32, Approval policy, Durable Last Tool Result | write | 🔴 | Direct Airtable create bypasses the explicit "write gateway only" rule in `tools/airtable_gateway.py`. | gateway |
| `crm.py` | `_patch` | Airtable | Tool Gateway, Tool Registry, Action Validator, Dispatcher, Output Validation, A32, Approval policy, Durable Last Tool Result | write | 🔴 | Direct Airtable patch is high-risk because CRM payment/customer state can change without structured proof. | gateway |
| `crm.py` | `crm_mark_payment_paid` | Airtable | Tool Gateway, structured ToolResult, durable proof; approval partly covered | write | 🔴 | Exposed agent tool is registered, but implementation returns strings and uses direct `_patch`. | gateway |
| `daily_digest.py` | `_at_list`, `build_digest` | Airtable / Telegram via callers | Tool Gateway, Dispatcher for internal reads, structured ToolResult, A32, Durable Last Tool Result | read/send | 🟡 | Report data is assembled from direct Airtable reads and sent by jobs without normalized evidence. | adapter |
| `tools/dispatcher.py` | `_check_duplicate` | Airtable | Tool Gateway, Output Validation, A32, Durable Last Tool Result | read | 🟠 | Dispatcher itself performs a direct Airtable duplicate lookup before gateway writes. | gateway |
| `tools/airtable_tools.py` | `_lookup_record_id` | Airtable | Tool Gateway for read lookup, structured output, durable proof | read | 🟡 | Linked-record lookup calls Airtable directly and can affect write input transformation. | adapter |
| `tools/airtable_tools.py` | `airtable_get` | Airtable | structured ToolResult, durable proof | read | 🟡 | Agent tool uses dispatcher but returns a formatted string instead of typed record evidence. | adapter |
| `tools/airtable_tools.py` | `airtable_get_schema` | Airtable Meta API | Tool Gateway, structured ToolResult, durable proof | read | 🟡 | Live schema reads are formatted strings, not governed schema evidence. | adapter |
| `tools/schema_governance.py` | `fetch_live_schema`, `run_governance` | Airtable Meta API | Tool Registry, Dispatcher, Output Validation, A32, Durable Last Tool Result | read/background | 🟢 | Audit/governance script is not a production user action, but still direct provider code. | document only |
| `providers/airtable_shim.py` | Airtable shim helpers | Airtable | Tool Registry, Action Validator, Dispatcher, Output Validation, A32, Durable Last Tool Result | read | 🟡 | Provider-specific shim exists outside the primary gateway and can become a parallel path. | design review |
| `tools/google_tools.py` | `calendar_create_event` internals | Google Calendar | Provider adapter layer; approval split between app/event bus/registry | write | 🟡 | Agent path is covered, but provider REST logic lives directly in the tool implementation. | adapter |
| `tools/google_tools.py` | `gmail_draft`, `gmail_send_draft` internals | Gmail | Provider adapter layer; Durable Last Tool Result | send | 🟡 | Structured agent results exist, but no durable evidence store. | adapter |
| `tools/google_tools.py` | `sheets_append` | Google Sheets | structured ToolResult, stronger proof, Durable Last Tool Result | write | 🟠 | Write/send-like action returns display strings, so A32 success proof is weaker. | wrap |
| `tools/google_tools.py` | `search_drive`, `read_drive_file`, `gmail_read`, `calendar_get_events` | Google APIs | structured ToolResult, durable proof | read | 🟡 | Reads are agent-dispatched but return strings instead of typed evidence. | adapter |
| `drive_adapter.py` | Drive upload helpers | Google Drive | Tool Registry, Action Validator, Dispatcher, generic ToolResult, A32, Durable Last Tool Result | write | 🟡 | Used by media flows as a local adapter, not as a governed tool result. | adapter |
| `voice_stt_adapter.py` | transcription helpers | STT provider | Tool Registry, Dispatcher, generic ToolResult, A32, Durable Last Tool Result | read/background | 🟡 | Transcription output is part of media proof but not represented as a generic tool result. | adapter |
| `tools/telegram_adapter.py` | Telegram send helper | Telegram | Tool Registry, Action Validator, Dispatcher, Output Validation, A32, Durable Last Tool Result | send | 🟡 | Direct send helper wraps provider call but no generic send-result evidence. | adapter |
| `media_handler.py` | `handle_voice_note` | Telegram / Drive / STT / Airtable | Tool Registry, Action Validator, Dispatcher, generic ToolResult, A32, Durable Last Tool Result | write/send | 🟠 | Multi-provider media write path uses local `MediaResult`, not F52 ToolResult. | adapter |
| `media_handler.py` | `handle_file_upload` | Telegram / Drive / Airtable | Tool Registry, Action Validator, Dispatcher, generic ToolResult, A32, Durable Last Tool Result | write/send | 🟠 | File upload has useful tests and local statuses, but not generic proof persistence. | adapter |
| `media_handler.py` | `handle_tma_upload` | TMA / Drive / Airtable | Tool Registry, Action Validator, Dispatcher, generic ToolResult, A32, Durable Last Tool Result | write | 🟠 | TMA upload is route-driven and not normalized as a tool result. | adapter |
| `media_handler.py` | `_handle_memory_confirmed` | Airtable / memory | Tool Registry, Action Validator, Dispatcher, Output Validation, A32, Durable Last Tool Result | write | 🟠 | Memory save success is reported with display text and not durable generic proof. | wrap |
| `cmd_decision.py` | `route_file_to_decision_inbox` | Telegram / Google Drive / Airtable | Tool Registry, Action Validator, Dispatcher, generic ToolResult, A32, Durable Last Tool Result | write | 🟡 | Calls `drive_adapter.upload_file()` directly (line 700) before creating the Decision Inbox record — same Route/Controller Bypass family as `_handle_telegram_media`/`tma_upload`/`media_handler.py`. Dormant: `FEATURE_DECISION_HUB=off` by default, not reachable in production. | adapter |
| `lead_capture.py` | `capture_inbound_lead` | Airtable | Tool Registry, Action Validator, Dispatcher, Output Validation, A32, Durable Last Tool Result | write | 🟠 | Captures business leads outside tool contract and parses record ids from strings. | wrap |
| `lead_qualifier.py` | `handle_lead_message` | Lead/session/Airtable via helpers | Tool Registry, Action Validator, Dispatcher, Output Validation, A32, Durable Last Tool Result | write/send | 🟠 | Lead qualification can trigger persistence and responses outside tool contract. | design review |
| `furniture_lead_funnel.py` | `handle_furniture_lead_message` / `_save_lead` | Airtable | Tool Registry, Action Validator, Dispatcher, Output Validation, A32, Durable Last Tool Result | write | 🟠 | Funnel persistence uses gateway in places but still infers record ids from formatted responses. | wrap |
| `session_store.py` | `_sync_to_db` | Airtable via `tools.airtable_tools` | structured ToolResult, A32, Durable Last Tool Result | write | 🟠 | Session persistence treats `"✅"` and `rec\w+` in strings as database proof. | wrap |
| `session_store.py` | `_load_from_db` | Airtable via `tools.airtable_tools` | structured ToolResult, A32, Durable Last Tool Result | read | 🟡 | Loads parse formatted Airtable strings rather than structured records. | adapter |
| `session_store.py` | `_delete_from_db` | Airtable via update/delete-like behavior | structured ToolResult, A32, Durable Last Tool Result | write/delete | 🟠 | Session cleanup lacks normalized deletion or tombstone proof. | wrap |
| `lead_memory.py` | lead memory `_write` / flush paths | Airtable via `tools.airtable_tools` | structured ToolResult, A32, Durable Last Tool Result | write | 🟠 | Memory sync parses `✅` and `rec\w+`, making display text an implicit success contract. | wrap |
| `worker.py` | `run_proactive_check` | Airtable / Anthropic / Telegram | Tool Registry, Action Validator, Dispatcher, Output Validation, A32, Approval policy, Durable Last Tool Result | background/send | 🟠 | Proactive agent-like work sends messages and reads Airtable outside tool contracts. | design review |
| `scheduler.py` | `_job_daily_digest`, `_job_weekly_summary`, `_job_daily_usage_report` | Airtable / Telegram | Tool Registry, Dispatcher, Output Validation, A32, Durable Last Tool Result | background/send | 🟡 | Scheduled reports send external messages without generic send proof. | adapter |
| `scheduler.py` | `_job_overdue_payments`, `_job_payment_reminders` | CRM / Airtable / Telegram | Tool Registry, Action Validator, Dispatcher, Approval policy, A32, Durable Last Tool Result | background/send | 🟠 | Payment flows are high-sensitivity and may send reminders outside central approval/proof. | design review |
| `scheduler.py` | `_job_followup_scan`, `_job_lead_recovery`, `_job_abandoned_scan`, `_job_interaction_scan` | Airtable / lead flows / Telegram | Tool Registry, Action Validator, Dispatcher, Output Validation, A32, Durable Last Tool Result | background/write/send | 🟠 | Lead recovery and follow-up automation can affect customer communications without F52 evidence. | design review |
| `scheduler.py` | `_job_daily_collector`, `_job_learning_cycle`, `_job_email_inbound`, `_job_attribution_report`, `_job_audience_report` | Airtable / Gmail / analytics / Telegram | Tool Registry, Action Validator, Dispatcher, Output Validation, A32, Durable Last Tool Result | background/read/send | 🟡 | Operational jobs are outside the contract and have mixed read/send behavior. | adapter |
| `scheduler.py` | `_job_daily_game_digest`, `_job_weekly_quest_reset`, `_job_boss_battle_check` | Airtable / game / Telegram | Tool Registry, Action Validator, Dispatcher, Output Validation, A32, Durable Last Tool Result | background/write/send | 🟠 | Game reset/check jobs mutate persistent game state and send claims without normalized proof. | design review |
| `scheduler.py` | `_job_cost_watchdog`, `_job_security_reminder`, `_job_daily_git_audit` | system / Telegram | Tool Registry, Dispatcher, Output Validation, A32, Durable Last Tool Result | background/send | 🟡 | System notifications are useful but still bypass generic send proof and durable result. | adapter |

## 4. Highest-Risk Bypasses

1. `crm.py` direct Airtable `_post` / `_patch`

   These are direct provider writes outside `tools/airtable_gateway.py`. They can change customer, deal, and payment state, while exposed CRM actions still return strings rather than structured tool evidence.

2. TMA lead/status write routes in `tma_api.py`

   `update_lead_status`, `patch_lead`, and `set_lead_outcome` mutate core business records through a route/controller path, not the agent tool contract. Some route-level checks exist, but proof, approval policy, and durable Last Tool Result are not centralized.

3. Emergency stop route in `tma_api.py`

   This is control-plane behavior. Even if intentionally separate from agent tools, F52 should treat it as a first-class contracted action with explicit proof and audit semantics.

4. Lead/session proof parsing

   `session_store.py`, `lead_memory.py`, `lead_capture.py`, and `furniture_lead_funnel.py` parse `"✅"` or `rec\w+` from display strings. This makes user-facing text part of the persistence API and can create false-positive success claims.

5. Scheduler payment/lead jobs

   `_job_overdue_payments`, `_job_payment_reminders`, `_job_followup_scan`, `_job_lead_recovery`, and related jobs can send or schedule customer-facing actions outside the registry/approval/proof layers.

6. Approval policy split

   Approval concepts live in `tool_registry.py`, `event_bus.py`, and `app.py`. Current coverage is enough to run, but not enough for a single auditable source of truth.

## 5. Safe No-Brainer Audit Tests

These are audit tests only; they should fail loudly when new bypasses are introduced, but they should not change production behavior.

- Add a static test that flags `httpx.post` and `httpx.patch` to Airtable outside `tools/airtable_gateway.py`.
- Add a static test that lists every direct Airtable `httpx.get` outside approved read adapters, then requires an explicit allowlist entry.
- Add a static test for `"✅" in result`, `"✅" in raw`, and `re.search(r"rec\w+")` in persistence code.
- Add a static test that enumerates `@bot.message_handler` commands and requires each command to appear in an F52 bypass/contract map.
- Add a static test that enumerates `@app.route` writes/sends and requires each route to declare whether it is a tool, adapter, gateway, or design-review bypass.
- Add a static test comparing approval-sensitive names across `tool_registry.py`, `event_bus.py`, and `app.py`.
- Add a static test that flags agent-visible write/send tools returning plain strings.
- Add a scheduler audit test that lists every `_job_*` and marks read/write/send/background mode.

## 6. Items Requiring Design Review

- Decide whether TMA route actions should become tools, route-contract actions, or a separate but equivalent F52 contract family.
- Decide whether Telegram command handlers should use the same registry/validator/proof concepts as agent tools, or a parallel command registry.
- Define the durable Last Tool Result store: table/file location, retention, privacy, redaction, and correlation keys.
- Consolidate approval policy into one source of truth, including `tool_registry.py`, `event_bus.py`, route approvals, and app-level approval callbacks.
- Decide how much read evidence is required for read/search tools, especially Google Drive, Gmail, Calendar, Airtable reads, and dashboards.
- Define a migration path for `crm.py` direct provider writes to the Airtable gateway without changing CRM behavior.
- Define whether media flows should emit generic `ToolResult` directly or use an adapter that translates local `MediaResult` into F52 evidence.
- Decide how scheduler/background jobs should record proof and approval for automated sends, reminders, and state mutations.
- Decide whether provider-specific REST code inside agent tool implementations should be acceptable, or whether F52 requires provider adapters below dispatcher routes.

## 7. Recommended Migration Order

1. Add audit-only static tests for direct Airtable writes, `✅` parsing, `rec\w+` parsing, Telegram commands, routes, and scheduler jobs.
2. Document the target F52 result contract in one place, including required fields for external id, evidence, provider, mode, approval, and durable proof.
3. Add a shadow-only durable Last Tool Result recorder for the existing agent dispatch path before changing any behavior.
4. Replace string-proof parsing in session/lead memory with consumption of structured results where the structured result already exists.
5. Consolidate approval policy definitions and add a mismatch test before moving route behavior.
6. Normalize high-risk exposed tools that still return strings, starting with `crm_mark_payment_paid` and `sheets_append`.
7. Move direct CRM Airtable writes behind `tools/airtable_gateway.py` after tests prove behavior parity.
8. Wrap TMA write routes with route-level contract adapters that record proof without forcing them into Claude tool schemas.
9. Add a media adapter that converts local `MediaResult` statuses into generic F52 proof records.
10. Bring scheduler/background jobs under a background-action contract with durable proof, explicit send/write classification, and policy review.

