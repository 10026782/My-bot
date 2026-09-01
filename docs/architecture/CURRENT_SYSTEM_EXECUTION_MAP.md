# Current System Execution Map

**Truth Reset SHA:** `origin/main` = `b58b27f8771c8ffd4c633a84a28b4009178fbeca` (01/09/2026). This is the merge containing the latest reconciled PRs; all runtime claims below remain static unless explicitly labelled runtime-verified.

**Date:** 31/08/2026. **Type:** read-only architecture audit. No runtime code was modified, no flags changed, nothing deployed.

**Role of this document:** a reusable, file/function-level cross-reference so future work does not repeatedly rediscover execution paths, writer ownership, flag wiring, and gate boundaries. It **reconciles and cites** the existing canonical docs (`ROADMAP.md`, `docs/governance/HORIZON.md`, `docs/governance/BOSS_UNIFIED_MASTER_PLAN.md`, `feature_flags.py`'s own registry docstring, `docs/governance/SECURITY_CHECKLIST.md`) rather than duplicating their content — per this repo's own stated convention ("Reconcile this file rather than duplicating audit content into it," `HORIZON.md`). Where this pass found current code diverging from what those docs say, it is called out explicitly in §10 (Contradictions) rather than silently overwritten.

**Reading rules:** "STATIC VERIFIED" = confirmed by reading/grepping current code. "RUNTIME VERIFIED" = confirmed by an actual production observation (this audit performed none — it is entirely static). A code default or a merged PR is never treated as runtime proof. "Reachable at default flags" means: with every flag at the value `feature_flags.py`'s own docstring/`_DEFAULTS` declares as default, would this code path actually execute today.

---

## 1. Runtime Entry-Point Map

All ingress handlers live in `app.py` (7066 lines) unless noted. Every Telegram/WhatsApp(Twilio)/WhatsApp(Meta) webhook independently calls `resolve_identity()` and `_apply_ingress_context_gate()` (`app.py:6226`) before doing anything else — there is no shared pre-router funnel function, each handler repeats the same 3–4 setup calls.

### 1.1 Telegram inbound
`app.py:6288 @app.route("/telegram")` → `webhook_telegram()` → `_webhook_telegram_impl()` (`app.py:6299`).
- Webhook secret check (`6300-6308`, fail-closed on missing/mismatched `X-Telegram-Bot-Api-Secret-Token`).
- **Callback query branch** (`6311-6338`): `resolve_identity("telegram", ...)` (`6322`) → `_apply_ingress_context_gate()` (`6323`) → `approve:`/`reject:` → `_handle_approval_callback`; `lead_draft_approve:`/`lead_draft_cancel:` → `_handle_lead_draft_callback`; else → pyTeleBot's own handler dispatch.
- **Text branch** (`6340-6498`): dedup on `update_id:message_id` (`6358-6368`) → `resolve_identity` (`6372`) → ActionGateway live-contract prefetch (`6385-6388`) → ingress gate (`6389`) → slash commands short-circuit to their own `@bot.message_handler` (`6396-6403`, never reach `run_agent`) → `/update`/`/marketing_new` pending-capture short-circuits (`6411-6429`) → Decision Hub attachment reference (`6435-6442`, `FEATURE_DECISION_HUB`) → **`run_agent()`** (`6463`) → reply sent via `bot.send_message()` directly (`6495`) — **not** through `tools/telegram_adapter.py`.
- **Media branch** (`6501-6526`): identity + gate → `/update` file-capture claim → else `_handle_telegram_media()`.

### 1.2 WhatsApp via Twilio inbound
`app.py:6531 @app.route("/whatsapp")` → `_webhook_whatsapp_impl()` (`6542`).
`_validate_twilio_signature()` (`6543`) → junk filter (`6552-6554`) → `_channel_domain(to_number)` (`6557`) → dedup on `MessageSid` (`6559-6561`) → `resolve_identity("whatsapp", sender)` (`6574`) → live-contract prefetch + ingress gate (`6576-6580`) → media pipeline (BUG-071, `6588-6675`) → UTM injection (`6677-6693`, `AD_ATTRIBUTION`) → canonical lead write gate (`6695-6728`, `WHATSAPP_CANONICAL_LEAD_WRITE`, domain≠furniture_import) → `core.whatsapp_lead_cutover.create_whatsapp_inbound_lead` → furniture-funnel deterministic pre-agent intercept (`6732-6744`, bypasses agent if it returns a reply) → **`run_agent()`** (`6748`) → `_gateway_whatsapp_reply()` (`6764`, def `~370-388`) routes the reply through `core.output_gateway.send_outbound` (C52 Customer Output Gateway / Financial Gate) before building the Twilio `MessagingResponse` TwiML (`6766-6773`). **`tools/whatsapp_adapter.py` is a documented "honest stub"** (comment at `app.py:383`) — actual delivery on this path is the synchronous TwiML response, never that adapter.

### 1.3 WhatsApp via Meta Cloud API inbound
`app.py:6780 @app.route("/webhooks/meta/whatsapp")`. GET = hub verification (`6782-6790`, fail-closed on token mismatch). POST: `EMERGENCY_STOP_WHATSAPP` check (`6793-6795`) → `_validate_meta_signature()` (`6797`) → `_normalize_meta_payload()` (`6801`) → junk filter → dedup (`6814`) → identity + prefetch + gate (`6825-6837`) → media via Meta Graph API download (`6841-6960`).
`META_OUTBOUND_ENABLED` gate at `app.py:6962`: **if false**, returns `{"status": "received_no_outbound"}` (`6967-6970`) without calling `run_agent` at all. **If true**, `run_agent()` runs (`6972`) but the result is only logged/returned as `{"status": "received"}` (`6979-6988`) — explicit "stub כנה: מחשב תשובה, לא שולח" comment (`6979`). **This channel is inbound-only end-to-end regardless of the flag** — no outbound send path exists anywhere in the repo (confirmed by repo-wide grep for a Graph API `/messages` POST — none found). `META_ACCESS_TOKEN` is declared in `.env.example` but never read by any `.py` file; inbound media download actually uses a different, undocumented var, `META_BUSINESS_TOKEN` (`app.py:6884`).

### 1.4 Email inbound (F06)
`scheduler.py:397 _job_email_inbound()` (registered `scheduler.py:930`, every `EMAIL_POLL_INTERVAL_MIN`=15m) — flag-checked (`EMAIL_INBOUND`) at `scheduler.py:400`. **This flag is structurally forced to `False` regardless of env** (see §3, `_ADAPTER_GATED_FLAGS`), so the job always returns at the check and `run_email_poll` never executes in production today. If it did: `email_inbound.py:331 run_email_poll()` → `poll_inbox()` (`76`) → `should_skip()` (`166`) → `route_email()` (`192`) → `inbound_handler.handle_inbound` (`inbound_handler.py:148`) dedups by external_id/sender → `_update_existing` (`78`) or `_create_email_lead` (`124`, which calls `create_lead()`). This path never calls `run_agent()` — it is a separate deterministic capture/dedup pipeline; reply drafts go through `request_email_approval()` (`email_inbound.py:254`), not the agent tool loop. **Neither this module nor `voice_adapter.py` constructs an `Identity` at intake** — both operate entirely outside the Identity→Router→Context→Agent pipeline that the rest of CLAUDE.md's architecture section describes as universal.

### 1.5 Voice/Twilio IVR inbound (F07)
`app.py:7030 /voice/incoming`, `app.py:7046 /voice/step`. Both validate the Twilio signature and check `is_enabled("VOICE_IVR")` (default off → static "not active" TwiML); when on, both delegate entirely to `voice_adapter.process_voice_step()` (`voice_adapter.py:324`), a self-contained deterministic DTMF state machine (`step_welcome→step_domain→step_interest→step_budget→step_callback`, `:131-232`) keyed by Twilio `CallSid`. `_save_voice_lead()` (`:232`) writes the lead **directly via `airtable_tools.airtable_add()`** — no `resolve_identity()`, no `run_agent()`, no Owner resolution, no ActionGateway dedup, no tenant scoping (see §2, Leads — this is the live legacy bypass).

### 1.6 TMA / REST API ingress
`tma_api.py`, registered `app.py:532-533` (`app.register_blueprint`). `require_tma_auth` (`tma_api.py:913`) validates `X-Telegram-Init-Data` HMAC then calls `resolve_identity("telegram", telegram_id)` (`930`) — no dev bypass. Route inventory (all behind `require_tma_auth` except `/api/tma/auth`): `/api/marketing/demands` (1168), `/api/projects` (1179/1203), `/api/projects/<slug>/dashboard` (1242), `/api/leads` (1526), `/api/leads/<id>` (1725/1892), `/api/leads/<id>/status` (1804), `/api/leads/<id>/outcome` (1937), `/api/leads/<id>/task` (1977), `/api/followup` (2043), `/api/ai/ask` (2092), `/api/finance/pulse` (2179), `/api/owner/health` (2682), `/api/owner/control-center` (2696), `/api/owner/command-center` (2735), `/api/owner/my-work` (2883), `/api/approvals` (2924), `/api/approvals/bulk` (2935), `/api/approvals/<id>` (3351), `/api/activity` (3420), `/api/assets` (3494/3514/3531), `/api/ventures` (3599/3624/3612/3653), `/api/health` (3780) + `/emergency` (3789) + `/emergency/clear` (3859), `/api/game/*` (4010, 4061, 4137, 4196, 4240).
- `/api/ai/ask` (2092) does **not** use `run_agent()` — it builds context via `context.build_context()` (2152) and calls `llm_fallback.call_anthropic_text()` (2156) directly (single-turn, no tool loop), but does route through `core.turn_coordinator_runtime.resolve_tma_contextual_answer_capability()` (2142/2147).
- `/api/approvals/<id>` POST (3351, `act_on_approval()`) drives approve/reject entirely through `core.action_gateway.action_gateway`'s canonical `ActionContract` via `_claim_and_execute_approval`/`_claim_and_reject_approval` (3100+), never patching the `Approvals` projection row directly. It re-checks `FEATURE_ACTION_CONTRACT_PERSISTENCE` and `FEATURE_ATOMIC_CLAIMS` at execution time (3121-3141) — either off/unavailable fails closed with HTTP 503, plus a TTL check (3165-3219) that fails closed on unreadable timestamps.

### 1.7 Scheduler/background jobs as ingress
`worker.py` is confirmed **removed** (no file on disk; commit `6b8573b`; zero `import worker` anywhere). `app.py:6993 POST /worker/trigger`: `Authorization: Bearer $WORKER_SECRET` check (6995-6998) → `owner_chat_id` derived only from server env `ELIYAHU_CHAT_ID`, never the caller (7002-7005, anti-impersonation) → `run_agent(f"[system event]: {event}", owner_chat_id)` (7010) → `bot.send_message` (7013). Confirms CLAUDE.md's description exactly. This route is triggered by something external to this repo (Render cron or similar) — that trigger source is out of repo scope and was not traced. `scheduler.py`'s own in-process `schedule` jobs generally call their own module functions, not `run_agent` — see §6 for the full job table.

### 1.8 Admin/internal/owner-only command entrypoints
All registered via `@bot.message_handler(commands=[...])`, each doing its own `resolve_identity()` + role check, bypassing `route_request()`/`run_agent()` entirely: `/status` (`app.py:545`), `/schema` (`564`, owner-only → `schema_intelligence.handle_schema_command`), `/boss_doctor` (`579`, owner-only → `boss_doctor.run_doctor()`+`format_report()` — **CLAUDE.md's claim that "no command is wired to it yet" is stale; it is wired**, see §10), `/memory_shadow` (595), `/usage` (621), `/done` (637), `/convert` (705, `LEAD_AUTO_CONVERT`-gated), `/quest` (726), `/coins` (769). `/update` (`cmd_update.py:60`, registered `app.py:805`), `/decision` (`cmd_decision.py:119`, registered `app.py:814`), `/marketing_new` (`cmd_marketing.py:229`, registered `app.py:823`) are all registered unconditionally at startup but internally gated by their own flag check (`FEATURE_DECISION_HUB`, `FEATURE_MARKETING_BRIDGE`) — see §3.

### 1.9 Turn Coordinator — confirmed live, not planning-only
`core/turn_coordinator_runtime.py` (294 lines) is actively imported and used, not just a design doc: `resolve_agent_capability` (imported `app.py:65`, called `app.py:4802` inside `run_agent()` to build the per-turn `ResolvedCapability`/`execution_context`). `queue_task_request()` (`core/turn_coordinator_runtime.py:268`) is used by `_queue_deterministic_create_task` (`app.py:1077`) and `_queue_deterministic_task_update` (`app.py:1156`) to route `create_task`/`update_task` intents through the Gateway **without invoking the Claude agent at all** (`agent_calls=0`, logged `app.py:1123-1127`) — a deterministic-router short-circuit for this specific intent class. `tma_api.py:2142/2147` uses the same runtime for `/api/ai/ask`. This is consistent with `ROADMAP.md`'s `TURN_COORDINATOR_PROGRAM` row: `IN_PROGRESS`, `MERGED_STATIC — TC7-B/RP5 paths recorded`, RP5 activation still a separate, pending decision — the static wiring above is live for these specific paths; RP5 evidence-enforcement is not.

### 1.10 `core/action_gateway.py` — confirmed live on every ingress turn, not dormant
`_apply_ingress_context_gate()` (`app.py:6226`) and the `find_live_contracts()` prefetch run on **every** inbound Telegram/WhatsApp(Twilio)/WhatsApp(Meta) message regardless of `FEATURE_ACTION_GATEWAY`. See §4 for the full wiring picture and §10 for why this contradicts the "largely dormant/shadow" framing in `feature_flags.py`'s own comments.

---

## 2. Canonical Writer Map

Background fact needed for every row below: `core/action_gateway.py::propose_action()` (`:1611`) **always** runs its fingerprint/live-contract dedup logic, regardless of `FEATURE_ACTION_GATEWAY` (default OFF, absent from `_DEFAULTS`). The flag only gates `propose_gated()`'s blocking behavior (`:1953`) — ON makes a rejected proposal fail the caller; OFF makes it a best-effort, non-blocking shadow propose (exceptions swallowed). Durable `ActionContract` persistence is a **separate** flag, `FEATURE_ACTION_CONTRACT_PERSISTENCE` (default OFF) — when off, the ledger is RAM-only.

| Entity | Canonical writer | Reachable today at default flags? | Classification | Key evidence |
|---|---|---|---|---|
| **Leads** | `core/lead_service.py::create_lead()` (347-535) — Owner resolution hard-fail, dedup via `find_existing_lead`, `ActionGateway.propose_action()`, write via `airtable_gateway` | Yes (Email/Furniture unconditional; WhatsApp legacy path still routes through `create_lead()`) | **CANONICAL** with a live **LEGACY bypass for Voice** | `voice_adapter.py::_save_voice_lead()` (230-260) calls `airtable_tools.airtable_add()` directly — no Owner resolution, no dedup, no tenant scope — because `VOICE_CANONICAL_LEAD_WRITE` defaults OFF and its canonical wrapper `create_voice_inbound_lead()` is unreachable |
| **Contacts** | `crm.py::create_contact_from_fields()` → `find_or_create_contact()` → `airtable_create()`; update via `crm.py::update_contact()` | Yes | **CANONICAL**, with tracked legacy `/convert` import | `core/reasoning_ports.py::_ProductionContacts.find_or_create()` now delegates to `tools.contact_resolver.resolve()` (PR1153), covered by `test_core_reasoning.py`; the former broken-import finding is code-done, not production-verified. `lead_conversion.py` still imports `crm.crm_add_contact` directly (dispatcher bypass), owner-only `/convert`, `LEAD_AUTO_CONVERT` off; the separate Contacts Notes-field conversion gap remains open. |
| **Deals / Payment Terms / Payments** | `commercial_crm.py::create_deal()`, `create_payment_term()`, `create_payment()`, `calculate_payment()` | **Yes, newly wired** as `crm_create_deal`, `crm_create_payment_term`, `crm_create_payment` in registry/schema/dispatcher (PR1153) | **STATIC WIRED, RUNTIME NOT ESTABLISHED** | `requires_approval`, `tenant_scoped`, and emergency-stop policy are registered and covered by `test_commercial_crm_dispatcher_wiring.py`; no production canary has verified a real record yet. Generic `airtable_add`/`airtable_update` can still bypass the VAT/payment-term contract until ownership is narrowed. `crm_mark_payment_paid` remains the canonical wired mark-paid tool. |
| **Tasks** | Generic `tools/dispatcher.py` `case "airtable_add"`/`"airtable_update"` with table=Tasks; TMA `tma_api.py::create_lead_task()` (1979-2033) via `_queue_or_owner_execute()` | Yes | **CANONICAL**, with a **tenant-scoping gap** | `Tasks`/`משימות (Tasks)` is absent from dispatcher's `_TENANT_AWARE` set (`tools/dispatcher.py:372-377`) — Leads/Contacts/Deals/Payments get automatic `tenant_id` injection, Tasks does not. Dedup: `_DEDUP_FIELDS["Tasks"]="כותרת המשימה"`. `core/action_gateway.py::is_task_table()`/`_canonical_task_payload()` normalize the payload inside `propose_action()` |
| **Decisions / Decision Events** | `cmd_decision.py::_create_decision()` (531-556) → `decision_ports.py::_AirtableStorageAdapter` (65-94) → `airtable_gateway` | **No** — `FEATURE_DECISION_HUB` absent from `_DEFAULTS`, defaults False | **FLAG-GATED**, code wired into `app.py` startup but blocked | `register_decision_command` is called unconditionally (`app.py:814-817`) but internally no-ops when the flag is off (`cmd_decision.py:112-113`). Separately, `lead_capture.py::capture_lead_event()` (107-166) writes `Tables.LEAD_EVENTS` directly, gated by `LEAD_CAPTURE` — this is the Lead-Events writer, distinct from "Decision Events" |
| **Sessions** | `session_store.py::PersistentSessionStore._sync_to_db()` (499-568) → `Tables.SESSIONS` | Yes, always-on | **LEGACY (tracked)** bypass, no tenant scoping | Imports `airtable_add`/`airtable_update` directly from `tools.airtable_tools` (line 503) — listed in `tools/audit_dispatcher_bypass.py:113-116` as a tracked exception (4 call sites). Zero references to `enforce_tenant_scope`/`tenant_id`/`identity` anywhere in the file |
| **Media** | `media_handler.py::_save_transcript_to_memory()` (260-286)/`_save_transcript_to_media_files()` (288-321) → `airtable_gateway` | **No** — `FEATURE_VOICE_NOTES`/`FEATURE_MEDIA_UPLOAD` both default OFF | **CANONICAL** writer, **FLAG-GATED / not reachable today** | Approval routing goes through the shared `ActionGateway.propose_gated()` (`media_handler.py:422`) |
| **Approvals / ActionContracts** | Three coexisting stores, not one system | Dedup: yes always. Blocking enforcement/durable persistence: no | **Mixed CANONICAL/FLAG-GATED** | (1) `app.py::_pending_approvals` (dict, `:180`, own lock `:184`, shorter TTL) — classic Telegram confirm/cancel flow. (2) `event_bus.py::PendingActionsStore`/`EventBus` — used by followup/abandoned/lead-recovery/media/email/otp/scheduler/tma/action_gateway. (3) `core/action_gateway.py::ActionGateway`/`ExecutionLedger` — RAM ledger unless `FEATURE_ACTION_CONTRACT_PERSISTENCE=true` (default off) |
| **Expenses** | **None exists** | Read-only only | **DEAD — no dedicated writer** | `grep "Tables.EXPENSES"` hits only `schema_audit.py` (schema map), `tma_api.py:2286` (read-only Finance Pulse query), `airtable_schema.py` (constants). `Expenses` is in `_ALIAS_MAP` (routable via generic `airtable_add`) but **absent from `_TENANT_AWARE`** — any such write would carry no tenant scoping and has no first-party caller |
| **Projects** | `project_timeline.py::create_timeline_records()` (176) — own CLI, `if __name__=="__main__"` | **No** — zero live importers | **UNWIRED** (confirms CLAUDE.md's existing note) | `grep -rln project_timeline` outside the file itself: nothing live |
| **Marketing entities** | `marketing_gateway.py::create_demand/update_demand_stage/save_creative_ideas/select_creative/save_script_draft/approve_script/record_publication/save_marketing_rule` — all via `airtable_gateway` | **No** — `FEATURE_MARKETING_BRIDGE` default OFF | **CANONICAL** writer, **FLAG-GATED / not reachable today** | `register_marketing_command` called unconditionally (`app.py:823-826`), no-ops internally when the flag is off (`cmd_marketing.py:221-222`) |

**Governance checks that pass clean today:** dispatcher `case` list vs `tool_registry.py` — zero mismatches (the exact grep from `docs/governance/SECURITY_CHECKLIST.md` was re-run). Two dispatcher cases (`tma_write`, `external_execution.submit`) have no `tools/schemas.py` entry, but this is intentional — both are non-LLM-facing, invoked directly by TMA/approval code, never exposed to the Claude tool-use schema.

---

## 3. Feature Flag / Activation Map

`feature_flags.py`'s own module docstring is the canonical registry ("every flag must appear here"), read via `is_enabled(name)` unless noted as a three-state flag with its own accessor. All flags default OFF via `os.environ.get(name, _DEFAULTS.get(name, ""))` → empty → False, **except** the two explicitly listed below.

**Flags defaulting ON:** `FEATURE_INGRESS_ENVELOPE` (default `"true"`, `_DEFAULTS`) — building the IngressEnvelope in `run_agent()`; if unset entirely it must behave as true so a fresh deploy never silently turns off what's already live. All other flags default off, including ones a naive reading might expect ON (`FEATURE_SINGLE_SPEAKER_APPROVAL_UX`, `FEATURE_DETERMINISTIC_APPROVAL_COST_CUTS`, `EXTERNAL_EXECUTION_ENABLED`, `WHATSAPP_CANONICAL_LEAD_WRITE`, `VOICE_CANONICAL_LEAD_WRITE` are all explicit `"false"` entries in `_DEFAULTS`, functionally identical to the fallback but documented there for clarity).

**Boolean flags (`is_enabled()`), grouped by subsystem, all default OFF unless noted:**

| Flag | Behavior when OFF | Behavior when ON | Selects canonical or legacy? | Dependency |
|---|---|---|---|---|
| `LEAD_CAPTURE` | No WhatsApp unknown-number lead creation | `lead_capture.py` creates Lead via `create_lead()` | canonical | — |
| `WHATSAPP_CANONICAL_LEAD_WRITE` | WhatsApp inbound still reaches `create_lead()` via the legacy `lead_capture.py` path | Routes via `core/whatsapp_lead_cutover.py::create_whatsapp_inbound_lead` (explicit Owner mapping) | Both paths already call `create_lead()` underneath — this flag chooses which *wrapper* calls it, not legacy-vs-broken | — |
| `VOICE_CANONICAL_LEAD_WRITE` | **Legacy `airtable_add()` bypass is the only reachable path** (`voice_adapter.py::_save_voice_lead`) | Routes to `create_voice_inbound_lead()` (canonical, has Owner resolution) | **legacy is default-selected today — real gap, see §10** | — |
| `LEAD_SCORING` | No score/tier at lead creation | Score+tier written at creation | — | — |
| `LEAD_MEMORY` | `lead_memory.update()` disconnected | Connected to lead_capture, scheduler flush every 10m (N01) | — | — |
| `FOLLOWUP_AUTOMATION` | Scheduler skips hot-lead scan | Scans HOT leads, queues approval via ActionGateway | — | — |
| `LEAD_RECOVERY` | No fading-lead detection | `core/lead_recovery.py` runs daily 10:00, approves via ActionGateway | — | — |
| `ABANDONED_LEADS` | No-op | **Structurally forced back to False even if set true** — `send_bounce` has no `tool_registry` entry (`_ADAPTER_GATED_FLAGS`) | permanently blocked, not a rollout toggle | Requires building the `send_bounce` adapter first |
| `EMAIL_INBOUND` | No-op | **Structurally forced back to False even if set true** — `send_email_reply` has no `tool_registry` entry | permanently blocked | Requires building the `send_email_reply` adapter first |
| `COST_WATCHDOG_LIVE` | — | Logs usage + enforces daily Sonnet limit | — | — |
| `MULTITENANT` | Single-tenant | F08 multi-tenant mode | — | `tenant_provisioner.py` is DEAD/unwired regardless (§4) |
| `FEATURE_ACTION_GATEWAY` | `propose_gated()` shadow-only (never blocks); **ingress-side context tracking and several direct callers run unconditionally regardless of this flag — see §10** | `propose_gated()` can actually reject the caller | Selects enforcement strength, not presence | — |
| `FEATURE_SINGLE_SPEAKER_APPROVAL_UX` | Legacy delivery routing | Gateway owns the one final response; identifier redaction is unconditional either way | — | Gate for `FEATURE_DETERMINISTIC_APPROVAL_COST_CUTS` |
| `FEATURE_DETERMINISTIC_APPROVAL_COST_CUTS` | Off | Early deterministic approval resolver | Effectively off unless the flag above is also on (`is_enabled()` special-cases this, `feature_flags.py`) | Depends on `FEATURE_SINGLE_SPEAKER_APPROVAL_UX` |
| `FEATURE_ACTION_CONTRACT_PERSISTENCE` | Ledger RAM-only | Durable proposal + recovery lookups | — | — |
| `FEATURE_ATOMIC_CLAIMS` | No PostgreSQL claim row before dispatch | Mandatory claim row via `core/action_gateway_atomic_executor.py`, gate inside `_execute_contract()` (`core/action_gateway.py:3500-3550`) | — | Requires `DATABASE_URL`; `docs/operations/ORACLE_MIGRATION_M0.md` reports this is **already true in live Render env** as of 28/08/2026 |
| `EXTERNAL_EXECUTION_ENABLED` | Poller no-ops | `core/external_execution_boundary.py` polls every 2m | — | — |
| `VOICE_IVR` | Static "not active" TwiML | Full DTMF state machine | — | — |
| `EMAIL_INBOUND` | see above | see above | — | — |
| `AD_ATTRIBUTION` | No UTM injection | UTM→lead attribution | — | — |
| `CONTACT_RESOLVER` | — | Auto contact resolution | — | — |
| `LLM_FALLBACK` | Anthropic failure propagates | Falls back to OpenAI if error is fallback-eligible | — | Requires `OPENAI_API_KEY` |
| `FEATURE_BUSINESS_UPDATE` | `/update` not registered | Registered | — | — |
| `FEATURE_WEEKLY_SUMMARY` | Job not scheduled | Weekly Business Memory digest — **flag checked at registration time, not inside the job**, so a runtime flip doesn't retroactively schedule it | — | — |
| `FEATURE_VOICE_NOTES` / `FEATURE_MEDIA_UPLOAD` | Telegram/TMA media upload gates closed | Voice→STT→Drive+Media Files / photo/doc→Drive+Media Files | — | — |
| `META_OUTBOUND_ENABLED` | Meta inbound never reaches `run_agent()` | Reply is computed but never sent (no send path exists at all) — see §1.3 | Neither state produces observable outbound Meta traffic | — |
| `FEATURE_MARKETING_BRIDGE` | `/marketing_new`/`/marketing_status` not registered | Registered, `marketing_gateway.py` writers reachable | — | — |
| `FEATURE_MEMORY_SHADOW_LOGGING` | No shadow comparison | Daily scheduler job records structured comparison counts, no memory content, no prompt impact | — | — |
| `FEATURE_EPISODIC_CAPTURE` | No capture | One `EpisodicEntry` per turn, fail-soft, capture-only | — | — |
| `EMERGENCY_WINDOW` | — | Temporary High-risk-from-phone override window | — | — |
| `FINANCIAL_COMMITMENT_GATE` | Shadow (log-only) | Escalation (not block) on detected financial commitment | — | — |
| `GAME_SCHEDULER` | Gamification jobs no-op | Daily digest, weekly quest reset, boss battle | — | — |
| `PAYMENT_REMINDERS` | No due-soon scan | `payment_reminder.py` runs daily 09:00 | — | — |
| `FEATURE_AIRTABLE_SCHEMA_SNAPSHOT` / `..._CLEANUP` | No schema archival | Daily 03:30 snapshot job to Airtable + XLSX; cleanup applies retention | — | Needs pre-activation checklist |
| `AUDIENCE_INTELLIGENCE` / `INTERACTION_INTELLIGENCE` / `KPI_ENGINE` / `LEARNING_ENGINE` / `REVENUE_ATTRIBUTION` | Not active | Future/inert — `LEARNING_ENGINE`'s job is intentionally read-only even when on | — | — |

**Three-state flags (own accessor, not `is_enabled()`; all fail-closed to the safe first state on any unrecognized value):**

| Flag | Accessor | States | OFF/first-state behavior | Middle state | Full state |
|---|---|---|---|---|---|
| `FEATURE_TOOL_AVAILABILITY_FILTER` | `get_tool_availability_filter_state()` | off/shadow/enforce | No checks | Local readiness diagnostics only, schemas unchanged | Hide role-allowed tools whose readiness check fails |
| `FEATURE_EVIDENCE_FINALIZER` | `get_evidence_finalizer_state()` | off/shadow/enforce | No comparison | Evidence-derived status + TC7-B claim-authorization compared, logged, `final_reply` untouched | RP5: unauthorized success claim replaced with `core.anti_hallucination._NO_TOOL_EVIDENCE_FALLBACK` |
| `FEATURE_UNIFIED_STATUS_FORMATTER` | `get_unified_status_formatter_state()` | off/shadow/on | Legacy `compose_status_reply()` text, byte-identical | Unified formatter computed+logged next to legacy; legacy still sent | Unified formatter output sent |
| `FEATURE_AIRTABLE_RUNTIME_SCHEMA_PROVIDER_STATE` | `get_runtime_schema_provider_state()` | off/shadow/enforce | Old behavior | Provider runs, compares against `schema_validator`, logs discrepancy, never blocks | Provider result determines which fields are blocked |
| `FEATURE_AIRTABLE_SELECT_VALUE_VALIDATION_STATE` | `get_select_value_validation_state()` | off/shadow/enforce | No value checking | Logs invalid singleSelect/multipleSelects values, never blocks | Invalid-valued field dropped from write entirely (no partial filtering) — active only when the schema provider is in `mode="full"` for that table |
| `FEATURE_PA01_ENFORCEMENT_STATE` | `get_pa01_enforcement_state()` | off/shadow/enforce | Old (log-only) behavior | 5-row matrix computed and logged (`would_block`), `final_reply` untouched | `final_reply` overwritten per the matrix row (`app.py:5652-5653`) |
| `FEATURE_CORE_REASONING_LEADS_STATE` | `get_core_reasoning_leads_state()` | off/shadow/on | No extra Lead Events read, no `reasoning` field, byte-compatible response | Reasoning computed+logged, response unchanged, no persistence | `reasoning` projection returned in `GET /api/leads/<id>`, still no persistence |

**Deployment activation order implied by dependencies** (see §11 for the full runbook): `FEATURE_AIRTABLE_RUNTIME_SCHEMA_PROVIDER_STATE` → `FEATURE_AIRTABLE_SELECT_VALUE_VALIDATION_STATE` (the second only takes effect in a table where the first reports `mode="full"`). `FEATURE_SINGLE_SPEAKER_APPROVAL_UX` → `FEATURE_DETERMINISTIC_APPROVAL_COST_CUTS` (second is inert without the first). `FEATURE_ACTION_CONTRACT_PERSISTENCE` and `FEATURE_ATOMIC_CLAIMS` are independent of each other but both gate `/api/approvals/<id>`'s real execution (§1.6) — both are reportedly already live in production per `ORACLE_MIGRATION_M0.md`. `EMAIL_INBOUND`/`ABANDONED_LEADS` cannot be activated at all until `send_email_reply`/`send_bounce` exist as registered tools — this is a hard prerequisite, not a sequencing preference.

---

## 4. Approval / Action / Reply Ownership Map

**`core/action_gateway.py` is not dormant/shadow-only** — that characterization (from its own docstring at `:1453-1460` and from `feature_flags.py`'s comments) describes only the *general-agent tool-use approval path* (`app.py::_queue_approval`, gated by `is_enabled("FEATURE_ACTION_GATEWAY")` at `app.py:1596`). Multiple other production callers invoke `propose_action()`+`approve()` **unconditionally**, making ActionGateway their sole write path today regardless of the flag:

| Caller | file:line | Flag-gated? |
|---|---|---|
| Weekly quest reset | `scheduler.py:19-51` | No |
| Abandoned-lead human pipeline task | `abandoned_lead_worker.py:247-300` | No |
| TMA generic write endpoint | `tma_api.py:568-650` | No — this endpoint has no other path |
| Interaction Engine task/event writes | `interaction_engine.py:386-453,827-858` | No |
| Lead Tier-1 preview writes | `core/lead_candidate_handler.py:426-470` (comment explicitly: "regardless of FEATURE_ACTION_GATEWAY") | No |
| Lead service | `core/lead_service.py:433-443,557-558` | No |
| General-agent tool-use approvals | `app.py:1596-1614,1953-1980` | **Yes** |

`approve()` (`:3186`) → `_execute_contract()` (`:3297`) has no flag check on dispatch itself — it always calls `tools/dispatcher.py::dispatch_tool()` via `_make_dispatch_executor()` (`:4412`). So `FEATURE_ACTION_GATEWAY=false` only disables *blocking* for the general-agent approval flow; it does not disable the Gateway as an execution mechanism for the callers above.

**Bypass protection**: `tools/dispatcher.py::_validate_execution_proof()` (`:108-135`) requires a fully-populated `execution_context` (contract_id/approved_by/tool_name/tenant_id/canonical_user_id/fingerprint/status, cross-checked against identity+payload) for any approval-sensitive tool — a direct `dispatch_tool()` call omitting it is refused. `tma_write`/`external_execution.submit` specifically require `execution_context["contract_id"]`.

**ActionContract producer**: exactly one production construction site — `core/action_gateway.py:1856` inside `propose_action()`. Every other `ActionContract(` construction in the repo is a test fixture.

**Approval-required tools** (`tool_registry.py`, 12 of 22 registered): `calendar_create_event`, `gmail_draft`, `gmail_send_draft` (also high_risk), `sheets_append`, `airtable_add` (high_risk), `airtable_update` (high_risk), `crm_mark_payment_paid` (high_risk), `media_save_to_memory`, `send_followup`, `send_recovery`, `tma_write`, `external_execution.submit`. **No tool has `high_risk=True` without `requires_approval=True`** — no dispatcher-tool bypass found.

**Reply-ownership sequencing inside `run_agent()`**: PA-01 block (`app.py:5579-5653`, can set `final_reply` only in `enforce`) → RP4 shadow-evidence observer (`5673-5706`, never mutates `final_reply`) → RP5 enforcement (`5722-5736`, only in `enforce`, only overwrites `final_reply` when the agent's own text claims "success" and `claim_authorization.authorized` is False). `FEATURE_UNIFIED_STATUS_FORMATTER` governs only `ActionGateway.compose_status_reply()`'s internal legacy-vs-unified text choice, independent of PA-01/RP5. Three approval-state stores coexist in parallel (see §2, Approvals row) exactly as CLAUDE.md describes; `_handle_approval_callback` re-runs `enforce()` for the original requester before dispatch, as documented.

**PostgreSQL atomic claims**: gate is inside `_execute_contract()` at `core/action_gateway.py:3500-3550` — off (default) skips the claim row entirely; on requires `execute_with_atomic_claim()` from `core/action_gateway_atomic_executor.py` to succeed before any dispatch.

---

## 5. Identity / Permission / Tenant / Domain Map

**Identity construction**: `identity.py::resolve_identity(channel, external_id)` (`:235-284`) looks up `f"{channel}:{external_id}"` in an in-memory `_REGISTRY` built once at import (`_load_registry()`, `:175-229`: `IDENTITY_MAP` env JSON → local `identity_map.json` → `ELIYAHU_CHAT_ID`-derived owner entry + `OWNER_PHONES`/`ELIYAHU_WHATSAPP` WhatsApp-owner alias). **`resolve_identity` never returns `None`** — an unknown key falls back to `Role.LEAD` (WhatsApp) or `Role.READONLY` (everything else), `display_name=""` deliberately (a past bug leaked a placeholder into Airtable's `Name` field). CLAUDE.md's "identity is None must hard-fail" rule is therefore enforced by *never producing* `None`, not by an internal check — the one `identity is None` guard found (`app.py:6243`) is defensive, for a caller-supplied identity elsewhere.

**Role hierarchy**: `Role._RANK` (`identity.py:30-33`): owner=6 > partner=5 > manager=4 > employee=3 > lead=2 > guest=1 > readonly=0.

**Tenant source per channel**:
- Telegram: `_REGISTRY` entry keyed `telegram:{chat_id}` supplies `tenant_id`.
- WhatsApp (Twilio): domain comes from `config.py::get_domain(to_number)` using `CHANNEL_DOMAINS` — **currently an empty dict**, only commented-out examples, plus a `FURNITURE_TWILIO_WHATSAPP_NUMBER` special case. Tenant itself still comes from `_REGISTRY` keyed `whatsapp:{phone}`, or the LEAD fallback.
- WhatsApp Meta / TMA: TMA's `require_tma_auth` calls `resolve_identity("telegram", telegram_id)` — TMA identity is literally the same Telegram registry entry, not a separate tenant model.
- **Email and Voice/IVR construct no `Identity` at all** — zero calls to `resolve_identity()`/`Identity()` in either `email_inbound.py` or `voice_adapter.py`. They are deterministic lead-capture writers entirely outside the Identity→Router→Context→Agent pipeline.

**Owner/profile resolution**: `profile.py` has zero live import sites anywhere (including tests) — fully dormant, matches CLAUDE.md exactly.

**Domain enforcement**: `core/router/domain_router.py::detect_domain()` (`:60-93`) — channel-mapping (1.0) > `identity.domain_id` (0.90) > regex text rules (0.5-x) > `GENERAL` fallback. This is **routing-only classification for prompt-building**, not an access-control gate — it never blocks a request.

**Capability vs. record permission — two genuinely distinct layers**:
- **Capability** (can this role call this tool): `tool_registry.py::enforce()` (`:525-537`) — raises `ToolDenied` if role not in `meta.roles_allowed`; coarse role buckets (`_INTERNAL`, `_MANAGEMENT`, `_SENIOR`, `_OWNER_ONLY`, `_ALL_EXTERNAL`).
- **Record/data** (can this identity touch *this* row): `tools/airtable_security.py::enforce_tenant_scope()` (`:96-142`) — internal roles pass with only a log line; external identities get an `AND(...,{tenant_id}='...')` filter injected; a missing/`"unknown"` tenant_id **hard-fails** with `TenantScopeViolation`, never silently falls back. A third, narrower gate — `enforce_leads_write_gate()` in the same file (`:39-77`) — blocks `airtable_add`/`airtable_update`/`airtable_patch` on `Leads` unless `source` is `lead_capture`/`lead_event`/`lead_scoring`/`crm`, i.e. the Agent itself can never write Leads directly.
- `tool_registry.py::get_availability()` (`:449-522`) is a separate read-only diagnostic view (feeds `boss_doctor.py`) — reports readiness, changes nothing.

---

## 6. Scheduler / Automation Map

Every job is registered once in `start_scheduler()` (`scheduler.py:886-943`), wrapped in `_automation_guard()` (`:864-882`, checks `EMERGENCY_STOP_AUTOMATION` centrally, fails closed to blocked on read error); 8 of them are additionally wrapped in `shabbat_safe()` (`shabbat_guard.py:187-199`).

| Job | Cadence | Entrypoint | Flag (default) | Shabbat-safe | Notes |
|---|---|---|---|---|---|
| daily_digest | daily 07:30 | `_job_daily_digest` (`:83`) | none | yes | |
| schema_snapshot_archive | daily 03:30 | `_job_schema_snapshot_archive` (`:102`) | `FEATURE_AIRTABLE_SCHEMA_SNAPSHOT` (off) | no | |
| daily_collector | daily 23:00 | `_job_daily_collector` (`:131`) | none | yes | Telegram approval-button flow |
| cleanup_pending | every 360m | `_job_cleanup_pending` (`:63`) | none | no | `event_bus.pending.cleanup()` |
| external_execution_poll | every 2m | `_job_external_execution_poll` (`:71`) | `EXTERNAL_EXECUTION_ENABLED` (off) | no | bounded lease-owned poll |
| overdue_payments | daily 00:05 | `_job_overdue_payments` (`:119`) | none | no | |
| flush_lead_memory (N01) | every 10m | `lead_memory.job_flush_lead_memory` | `LEAD_MEMORY` (off) | no | |
| followup_scan (N02) | every 60m | `_job_followup_scan` (`:155`) | `FOLLOWUP_AUTOMATION` (off) | yes | queues via ActionGateway |
| payment_reminders (N04) | daily 09:00 | `_job_payment_reminders` (`:186`) | `PAYMENT_REMINDERS` (off) | yes | |
| lead_recovery (F01) | daily 10:00 | `_job_lead_recovery` (`:222`) | `LEAD_RECOVERY` (off) | yes | approves via ActionGateway |
| learning_cycle (F02) | weekly Sun 06:00 | `_job_learning_cycle` (`:250`) | `LEARNING_ENGINE` (off) | no | read-only, intentionally inert |
| email_inbound | every 15m | `_job_email_inbound` (`:397`) | `EMAIL_INBOUND` — **hard-blocked** (see §3) | no | no-op in production today |
| abandoned_scan (D02) | every 45m | `_job_abandoned_scan` (`:443`) | `ABANDONED_LEADS` — **hard-blocked** | yes | no-op in production today |
| audience_report (D04) | weekly Sun 08:05 | `_job_audience_report` (`:467`) | `AUDIENCE_INTELLIGENCE` (off) | yes | retimed by PR1153; no longer collides with weekly_quest_reset |
| attribution_report (D05) | weekly Sun 08:30 | `_job_attribution_report` (`:425`) | `AD_ATTRIBUTION` (off) | no | |
| interaction_scan (D06) | every 15m | `_job_interaction_scan` (`:487`) | `INTERACTION_INTELLIGENCE` (off) | yes | TODO in-code suggests widening to 30m |
| security_reminder | weekly Sun 09:00 | `_job_security_reminder` (`:348`) | none | no | reads `/tmp/security_review.json` |
| weekly_summary (C22) | weekly Sun 08:30, **conditionally registered** | `_job_weekly_summary` (`:375`) | `FEATURE_WEEKLY_SUMMARY` (off), checked at registration not per-run | no | **duplicate slot with attribution_report (D05)** when both on |
| daily_game_digest | daily 07:00 | `_job_daily_game_digest` (`:525`) | `GAME_SCHEDULER` (off) | no | |
| weekly_quest_reset | weekly Sun 08:00 | `_job_weekly_quest_reset` (`:628`) | `GAME_SCHEDULER` (off) | no | per-quest write unconditionally via ActionGateway; audience_report was retimed to 08:05 by PR1153 |
| boss_battle_check | weekly Fri 18:00 | `_job_boss_battle_check` (`:726`) | `GAME_SCHEDULER` (off) | no | |
| cost_watchdog | every 60m | `_job_cost_watchdog` (`:800`) | none | no | legacy `EMERGENCY_STOP_AI` trigger |
| daily_usage_report | daily 08:15 | `_job_daily_usage_report` (`:841`) | none | no | deliberately offset from the Sunday reporting/game cluster |
| memory_shadow_scan | daily 04:00 | `_job_memory_shadow_scan` (`:809`) | `FEATURE_MEMORY_SHADOW_LOGGING` (off) | no | one owner-scoped sample/day |

**Structural adapter gate** (`feature_flags.py:252-255`, `_ADAPTER_GATED_FLAGS`): `is_enabled()` (`:287-297`) forces `EMAIL_INBOUND`/`ABANDONED_LEADS` to `False` even if the env var is set true, because `tool_registry.get("send_email_reply")`/`get("send_bounce")` both return `None`. Both jobs are entirely no-ops in production today regardless of Render config.

**Finding carried to §10**: the Sunday 08:30 collision (`attribution_report` D05 vs conditionally registered `weekly_summary`) remains static. PR1153 retimed `audience_report` from 08:00 to 08:05; the former 08:00 collision is historical/code-done and still lacks a schedule regression test.

---

## 7. External Dependency Map

| Dependency | Adapter | Required env | Retry | Fail mode | Healthcheck | Notes |
|---|---|---|---|---|---|---|
| Airtable | `tools/airtable_gateway.py`, `tools/airtable_security.py` | `AIRTABLE_API_KEY`, `AIRTABLE_BASE_ID` (CRITICAL) | None, single-shot `httpx`, per-call timeout | Fail-closed | `health_monitor.py::_check_airtable` — real metadata read, 3s timeout, feeds `/health` | `docs/operations/DEPLOYMENT.md` reports prod-verified live 28/08/2026 |
| Telegram Bot API | `telebot` (inbound), `tools/telegram_adapter.py` (C52 send, `adapter_mode="live"`) | `TELEGRAM_TOKEN` (CRITICAL) | None, `timeout=5` | Fail-closed (`ActionResult.failure`) | `health_monitor.py` checks presence only, not a live probe | The only genuinely live outbound C52 adapter of the three checked |
| WhatsApp — Twilio | Inbound in `app.py` webhook; `tools/whatsapp_adapter.py` (C52) | `TWILIO_AUTH_TOKEN` (signature check); SID/number vars are INFO-level, not boot-critical | N/A | Inbound fail-closed on signature. **Outbound is a documented "honest stub"** — `send_whatsapp()` always returns `delivery_success=False, adapter_mode="stub"`; real replies go out via the synchronous TwiML built directly in the webhook handler | None dedicated | |
| WhatsApp — Meta | Inbound webhook + `meta_whatsapp_media_adapter.py` (inbound media only) | `META_VERIFY_TOKEN`/`META_APP_SECRET`/`META_PHONE_NUMBER_ID`/`META_ACCESS_TOKEN` (all optional in `.env.example`); inbound media actually uses undocumented `META_BUSINESS_TOKEN` | N/A | Fail-closed on verify/HMAC | None | **No outbound send implementation exists at all**, confirmed by repo-wide grep — `META_ACCESS_TOKEN` is declared but never read by any `.py` file |
| Gmail | `tools/gmail_tools.py` shim → `tools/google_tools.py` | `GOOGLE_CLIENT_ID`/`SECRET`/`REFRESH_TOKEN` (WARNING-level) | None, `timeout=10-15` | Fail-closed; Gmail only ever drafts, never sends directly | None | Owner-confirmed 31/08 that Workspace was unfrozen; `ORACLE_MIGRATION_M0.md` is the current dated snapshot, but fresh Render values still require live verification |
| Google Drive | `tools/drive_tools.py` shim; separately, `drive_adapter.py` (F16 media storage, used by `media_handler.py`/`cmd_decision.py`) | Same 3 Google vars + `GOOGLE_DRIVE_FOLDER_ID` | None | Fail-closed | None | `ORACLE_MIGRATION_M0.md` flags a malformed, triple-concatenated `GOOGLE_DRIVE_FOLDER_ID` env var live on Render — a dashboard artifact, unresolved |
| Google Sheets | `tools/sheets_tools.py` shim | Same 3 Google vars | None | Fail-closed | None | |
| Google Calendar | `tools/calendar_tools.py` shim | Same 3 Google vars | None | Conflict pre-check is **fail-open** ("בדיקה נכשלה — ממשיך ביצירה"); the create/get calls themselves are fail-closed | None | |
| Render | `gunicorn.conf.py` (`post_worker_init` → `run_startup_sequence()`, pinned `workers=1`, required until a distributed scheduler/leader-election exists) | — | — | — | `/health` exists (`app.py:6187-6190`, `{"status": ...}` only, no `"version"` key despite `DEPLOYMENT.md`'s example) but **is not wired as Render's platform health check** (`healthCheckPath` empty, confirmed live) | `DEPLOYMENT.md` (26/08/2026) documents Auto-Deploy is **off** (manual only) |
| Oracle migration (M0) | infra-only slice | — | — | — | — | `docs/operations/ORACLE_MIGRATION_M0.md`: repo-side readiness only, explicitly no resource provisioned; M1 (provisioning) is a separate, not-yet-started step. PostgreSQL (`DATABASE_URL`) + `FEATURE_ATOMIC_CLAIMS=true` are both reportedly already live |
| STT / transcription | `voice_stt_adapter.py` | `OPENAI_API_KEY`, `OPENAI_STT_MODEL` (default `whisper-1`) | None | Exception propagates, no fallback provider wired | None | `.env.example` describes Groq as primary STT — **stale**; code's actual and only working path is OpenAI Whisper, Groq is fully commented out as unwired Phase-2 work |
| Model providers | `llm_fallback.py::call_anthropic_text()` | `ANTHROPIC_API_KEY` (CRITICAL); `OPENAI_API_KEY`+`LLM_FALLBACK` for fallback | **No app-level retry/backoff anywhere** (no `tenacity`/`backoff` dependency) — relies entirely on SDK defaults | Anthropic failure falls back to OpenAI only if `LLM_FALLBACK=true` and the error is fallback-eligible; otherwise propagates | `core/cost_watchdog.py` auto-triggers `EMERGENCY_STOP_AI` on spend-threshold breach — the live authoritative trigger; `core/usage_telemetry.py` is shadow-only | |

**Not independently re-verifiable from static code**: live values of Render env vars beyond what `ORACLE_MIGRATION_M0.md` (dated 28/08/2026, itself 3 days old relative to this audit) already recorded — no fresh Render API read was performed in this pass.

---

## 8. Dead / Legacy / Unwired Inventory

| Item | Claim source | Verification | Result | Classification |
|---|---|---|---|---|
| `profile.py` | CLAUDE.md | repo-wide grep for any importer | Zero live importers (including tests) | DEAD |
| `project_timeline.py` | CLAUDE.md | same | Only importer is a test file, itself unimported live | DEAD |
| `tenant_provisioner.py` | CLAUDE.md | same | Only importer is a test file, itself unimported live | DEAD (pending F12/F13 decision) |
| `providers/` shims | CLAUDE.md | same | Only importer is a test file, itself unimported live | DEAD/UNKNOWN (blocked pending decision) |
| `worker.py` | CLAUDE.md (removed, `6b8573b`) | `ls` fails; no `import worker` anywhere | Confirmed gone; `workers/survey_worker.py` also deleted the same way | REMOVED — confirmed |
| `POST /worker/trigger` | CLAUDE.md | Read `app.py:6993-7010` | Forwards `[system event]` to `run_agent()`, no worker-module call | KEEP, as documented |
| `_ALIAS_MAP` (`tools/dispatcher.py:56-61`) | — | Read directly | Currently: `Tasks`, `Contacts`, `Deals`, `Expenses` only — `Payments` was deliberately dropped (Track 8C) since the live Hebrew table no longer exists | KEEP, recently pruned, current |
| Dispatcher `case` vs `tool_registry` | SECURITY_CHECKLIST.md's stated grep | Re-ran it | Zero mismatches | KEEP — clean |
| Dispatcher cases vs `tools/schemas.py` | independent check | Diffed 22 vs 20 names | `tma_write`/`external_execution.submit` intentionally absent — non-LLM-facing, invoked directly | KEEP — by design, not drift |
| `_ADAPTER_GATED_FLAGS` (`EMAIL_INBOUND`/`ABANDONED_LEADS`) | CLAUDE.md | Read `feature_flags.py`, grepped `tool_registry.py` | Confirmed structurally hard-blocked, per an explicit 12/07/2026 owner decision (PR-0C) | KEEP-BLOCKED pending the missing adapters — not accidental |
| `tools/whatsapp_adapter.py` | found during dependency trace | Read full file | Entire outbound path is a documented, accurate "honest stub" | KEEP as-is until a real Twilio REST send is built |
| Meta outbound send path | found during dependency trace | repo-wide grep for a Graph API send | No outbound implementation exists at all; the flag only gates whether a reply is computed, never whether it's sent | UNKNOWN — not stated in-code whether this is deliberate Phase-1 scaffolding or stale |
| `core/reasoning_ports.py::_ProductionContacts.find_or_create()` | found while tracing Contacts writers | Read + import-path check | PR1153 delegates to the real `tools.contact_resolver.resolve()` and adds regression coverage; gated callers still need runtime verification | CODE DONE, NOT VERIFIED IN PROD |
| `/health` response shape vs `DEPLOYMENT.md` | found while verifying Render | Read `app.py:6187-6190` | Route returns `{"status": ...}` only; doc's example includes a `"version"` key the route never returns | Doc drift (minor), not a code defect |
| `.env.example`'s Groq-primary STT claim | found while verifying STT | Read `voice_stt_adapter.py:1-4,122-187` | Groq path is fully commented out; OpenAI Whisper is the only working provider | Doc drift, stale relative to code |
| `boss_doctor.py` wiring | CLAUDE.md said "no command wired yet" | Read `app.py:579-583` | `/boss_doctor` **is** registered, owner-only | Doc drift — CLAUDE.md is stale on this specific point |

---

## 9. Runtime Evidence Matrix

Distinguishing STATIC VERIFIED (confirmed by reading this audit's code) / MERGED_STATIC (existing docs' own classification, re-cited not re-derived) / DEPLOYED (claimed live per `ORACLE_MIGRATION_M0.md`'s 28/08/2026 Render snapshot — not re-verified fresh here) / RUNTIME VERIFIED (an actual production observation — none performed in this audit) / RUNTIME NOT ESTABLISHED.

| Capability | Static state | Deployed? | Runtime evidence? | Blocker |
|---|---|---|---|---|
| Telegram inbound → `run_agent` | STATIC VERIFIED (§1.1) | Claimed active per `AI_CONTEXT.md` | Not independently re-verified this pass | None known |
| WhatsApp Twilio inbound → `run_agent` → TwiML reply | STATIC VERIFIED (§1.2) | Claimed active | Not re-verified this pass | None known |
| WhatsApp Meta inbound | STATIC VERIFIED — inbound-only, no send path exists at all (§1.3) | `META_OUTBOUND_ENABLED` reportedly off | RUNTIME NOT ESTABLISHED — and cannot be, until an outbound sender is built | Missing outbound implementation, not just a flag |
| Email inbound (F06) | STATIC VERIFIED — structurally no-op today (§1.4, §6) | N/A | RUNTIME NOT ESTABLISHED — cannot execute regardless of env | Missing `send_email_reply` tool_registry entry |
| Abandoned-lead automation | STATIC VERIFIED — structurally no-op today (§6) | N/A | RUNTIME NOT ESTABLISHED — cannot execute regardless of env | Missing `send_bounce` tool_registry entry |
| Voice IVR (F07) | STATIC VERIFIED, deterministic, outside Identity pipeline (§1.5) | `VOICE_IVR` reportedly off | RUNTIME NOT ESTABLISHED | Flag off |
| N18 canonical Lead writers | STATIC VERIFIED for Email/Furniture/WhatsApp-legacy; Voice's canonical wrapper unreachable (§2) | `WHATSAPP_CANONICAL_LEAD_WRITE`/`VOICE_CANONICAL_LEAD_WRITE` off | RUNTIME NOT ESTABLISHED for the flagged wrappers | Owner-gated activation + canary, per `ROADMAP.md` N18 row |
| Deal/Payment/PaymentTerm canonical writers (`commercial_crm.py`) | MERGED_STATIC and wired by PR1153 | N/A | RUNTIME NOT ESTABLISHED — can now be reached through the new tools, but no real canary has run | Verify owner-approved Deal + Payment Term canary and absence of raw bypass |
| Decision Hub | STATIC COMPLETE per `HORIZON.md`, confirmed wired-but-gated (§2) | `FEATURE_DECISION_HUB` off | RUNTIME NOT ESTABLISHED | Flag off, per `HORIZON.md`'s own next-step |
| Media Layer (F16) | MERGED_STATIC per `ROADMAP.md`/`HORIZON.md`, confirmed the writers exist and are flag-gated (§2) | `FEATURE_VOICE_NOTES`/`FEATURE_MEDIA_UPLOAD` off | RUNTIME NOT ESTABLISHED | M5 owner decision still open per ROADMAP |
| Marketing Bridge (F23) | STATIC VERIFIED, wired but gated (§2) | `FEATURE_MARKETING_BRIDGE` off | RUNTIME NOT ESTABLISHED | Flag off |
| Turn Coordinator (TC7-B/RP5) | STATIC VERIFIED live wiring for deterministic task create/update + TMA `/api/ai/ask` (§1.9) | RP5 off by default per `ROADMAP.md` | RUNTIME NOT ESTABLISHED for RP5 evidence enforcement | Owner approval pending, per `HORIZON.md` |
| ActionGateway (`core/action_gateway.py`) | STATIC VERIFIED as always-active for dedup + several unconditional callers (§4) — **not** dormant as `feature_flags.py`'s comment suggests | `FEATURE_ACTION_GATEWAY` off | RUNTIME NOT ESTABLISHED for the blocking-enforcement branch specifically | See §10 contradiction |
| PostgreSQL atomic claims (`FEATURE_ATOMIC_CLAIMS`) | STATIC VERIFIED gate location (§3, §4) | **Claimed live** per `ORACLE_MIGRATION_M0.md` (28/08/2026) | Not independently re-verified fresh in this pass | Confirm against current Render env before relying on this |
| Emergency Stop (5 flags) | STATIC VERIFIED, durable via `EmergencyStopManager` | Claimed production-verified by the owner directly per `AI_CONTEXT.md` (23/07/2026) | Owner-reported, not independently re-checked here | None known |
| Schema governance pipeline (Track 8/8B/8C) | STATIC VERIFIED + LIVE SCHEMA VERIFIED per `ROADMAP.md`'s `SCHEMA_DATA_CONTRACTS` row (30/08/2026, via a read-only Airtable MCP pass) | N/A (schema state, not a runtime toggle) | LIVE SCHEMA SHAPE VERIFIED; application runtime not established | Deal/Payment tools are statically registered by PR1153; verify canary and TMA ownership |

---

## 10. Contradictions Discovered

1. **Historical finding: ActionGateway characterization.** PR1153 corrected the module comment; current truth is that ingress/prefetch and several callers remain unconditional, while `FEATURE_ACTION_GATEWAY` controls enforcement strength for the general-agent approval path only.
2. **Voice's canonical Lead writer is unreachable by default; only the legacy bypass runs.** `VOICE_CANONICAL_LEAD_WRITE` defaults off, so `voice_adapter.py::_save_voice_lead()`'s direct `airtable_add()` call (no Owner resolution, no dedup, no tenant scope) is the only path that executes today — `create_voice_inbound_lead()` exists but is dead weight until the flag flips. Confirms and sharpens `ROADMAP.md`'s N18 "remaining work" note.
3. **`boss_doctor.py` doc drift**: CLAUDE.md states "no command is wired to it yet" — `/boss_doctor` is in fact registered and owner-gated (`app.py:579-583`). Stale documentation, not a code issue.
4. **`.env.example` STT provider drift**: documents Groq as primary with OpenAI fallback; code's only working provider is OpenAI Whisper, Groq is fully commented out. Stale `.env.example` comment.
5. **`/health` response shape drift**: `docs/operations/DEPLOYMENT.md`'s documented example response includes a `"version"` key the actual route never returns.
6. **Closed/code-done: Contacts adapter import.** PR1153 replaced the nonexistent import with `tools.contact_resolver.resolve()` and added tests; no production activation is claimed.
7. **Owner-confirmed, runtime still unverified: Google Workspace.** The prior “frozen vs live” contradiction was resolved by the 31/08 owner confirmation that Workspace was unfrozen; the current Render values still require live verification.
8. **One Sunday scheduler collision remains:** 08:30 (`attribution_report` vs conditionally registered `weekly_summary`). The 08:00 pair is no longer colliding after `audience_report` moved to 08:05 in PR1153; no schedule assertion exists yet.
9. **Closed/code-done: commercial CRM wiring.** PR1153 registered the three canonical tools with policy/schema/dispatcher coverage; runtime canary and ownership against generic raw writes remain open.
10. **Truth Reset SHA:** this document is now reconciled against `origin/main` at `b58b27f8771c8ffd4c633a84a28b4009178fbeca`; earlier SHA references and pre-PR1153 findings are historical.

---

## 11. Post-Audit Remediation (PR #1153 + 31/08/2026 reconciliation)

Six of §10's ten findings are now resolved. Code fixes are **🟡 CODE DONE, NOT VERIFIED IN PROD** per this repo's own verification rule — no Render deploy/production check has been performed.

- **Finding 1** (`core/action_gateway.py` "dormant/shadow" mischaracterization): fixed — the module header comment now states plainly that `FEATURE_ACTION_GATEWAY` only controls blocking strength for `app.py::_queue_approval`, and that `propose_action()`/`approve()` and their 6+ production callers run unconditionally regardless of the flag.
- **Finding 3** (`boss_doctor.py` doc drift in CLAUDE.md): resolved — CLAUDE.md's `boss_doctor.py` entry now correctly states it is wired to the owner-only `/boss_doctor` command.
- **Finding 4** (`.env.example` STT provider drift): resolved — `.env.example` now documents `GROQ_API_KEY` as reserved/unwired and OpenAI Whisper as the actual live provider.
- **Finding 5** (`/health` response shape drift): resolved — `docs/operations/DEPLOYMENT.md`'s example no longer includes the undocumented `"version"` key.
- **Finding 6** (historical `core/reasoning_ports.py::_ProductionContacts.find_or_create()` broken-import claim): fixed to import `tools.contact_resolver.resolve`/`ResolveStatus`, covered by `test_core_reasoning.py`; runtime activation remains unverified.
- **Finding 8** (Sunday 08:00 `audience_report`/`weekly_quest_reset` collision): `audience_report` moved to 08:05 in `scheduler.py`.
- **Finding 9** (historical `commercial_crm.py` writers-unwired claim): `crm_create_deal`, `crm_create_payment_term`, `crm_create_payment` are registered end-to-end in `tool_registry.py`, `tools/dispatcher.py`, `tools/schemas.py`, `action_validator.py`, and `core/anti_hallucination.py`; runtime canary and TMA/raw-write ownership remain open.
- **Finding 7** (Google Workspace credential contradiction): resolved by owner confirmation (31/08/2026) — Google Workspace was frozen, then unfrozen; `ORACLE_MIGRATION_M0.md` ("live") reflects current reality. `docs/governance/ARCHITECTURE_DRIFT_MAP.md` row 7 and `docs/operations/RUNTIME_VERIFICATION_MASTER_RUNBOOK.md`'s A1 updated accordingly.

Finding 2 (Voice canonical lead writer) remains open — pending a Render deploy the owner is running separately; no flag change made here per owner instruction. Finding 10 is a SHA pointer, not an actionable item.

---

## Related canonical sources (cited, not duplicated)

`ROADMAP.md` (current-state SSOT, 30/08/2026) · `docs/governance/HORIZON.md` (program status map, 30/08/2026) · `docs/governance/BOSS_UNIFIED_MASTER_PLAN.md` (§3.5 Active Work Registry, 30/08/2026) · `feature_flags.py` (flag registry docstring — the authoritative source for §3, reconciled here) · `docs/governance/SECURITY_CHECKLIST.md` (dispatcher/registry grep checks) · `docs/governance/MAINTENANCE_AUDIT_LEDGER.md` (Track 8/8B/8C schema reconciliation) · `docs/operations/ORACLE_MIGRATION_M0.md` (infra readiness, Render env snapshot 28/08/2026) · `docs/architecture/n18-canonical-lead-writers/N18_PHASE_3_CANONICAL_LEAD_WRITERS_SPEC.md` (Lead-writer program detail) · `docs/architecture/turn-coordinator/` and `docs/architecture/f52-unified-approval-runtime/` (Turn Coordinator / F52 program detail, not re-litigated here).
