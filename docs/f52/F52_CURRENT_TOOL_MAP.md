# F52 Current Tool Map

Updated: 25/06/2026

Scope: audit-only map of the current BOSS tool architecture before F52. No production behavior changes are included in this document.

## Current Architecture Map

### Agent tool path

The main Claude tool path starts in `app.py`.

1. `app.py` imports `dispatch_tool` from `tools`, `validate_tool_output` from `guards`, and `verify_execution` / `sanitize_agent_response` from `core.anti_hallucination`.
2. Claude receives `ctx.allowed_tools` in the model call.
3. Tool use blocks are processed in the agent loop.
4. For each tool call, `app.py` may queue approval, or executes:
   - `dispatch_tool(tu.name, tu.input, identity)`
   - `validate_tool_output(tu.name, raw)`
   - `verify_execution(tu.name, result)`
   - append a per-turn item to `tool_results_log`
5. Final text is passed through `sanitize_agent_response(final_reply, tool_results_log)`.

Primary references:

- `app.py:52-56` imports the tool dispatcher, output validator, and anti-hallucination gates.
- `app.py:927` creates `tool_results_log` as a per-turn in-memory list.
- `app.py:993-1008` handles approval / dispatch / validate / verify.
- `app.py:1028-1033` records only `{tool, content, ok}` for final claim checking.
- `app.py:1047` sanitizes the final agent response.

### Tool definition and policy layers

Current tool metadata is split across several files:

- `tools/schemas.py`: Claude native tool schemas exposed to the model.
- `tool_registry.py`: roles, tenant-scope flags, approval flags, risk flags.
- `action_validator.py`: required inputs and structure checks before dispatch.
- `tools/dispatcher.py`: match/case execution router.
- `guards/rate_limiter.py`: `validate_tool_output`, currently length-limits and preserves dict results.
- `core/anti_hallucination.py`: A32 proof/claim gate.

Notable mismatch:

- `action_validator.py` includes CRM tools and `add_knowledge`.
- `tools/schemas.py` hides CRM schemas.
- `tools/dispatcher.py` only dispatches `crm_mark_payment_paid` among CRM actions.
- `tool_registry.py` only registers the currently allowed subset.

### Registered / exposed agent tools

From `tools/schemas.py`, the current Claude-facing tool set is:

- Drive: `search_drive`, `read_drive_file`
- Calendar: `calendar_get_events`, `calendar_create_event`
- Gmail: `gmail_draft`, `gmail_send_draft`, `gmail_read`
- Sheets: `sheets_append`
- Airtable: `airtable_get`, `airtable_add`, `airtable_update`, `airtable_get_schema`
- Contacts / lead lookup: `resolve_contact`, `search_lead`
- Reports / memory: `get_daily_report`, `search_business_memory`
- CRM: `crm_mark_payment_paid`

### Dispatcher execution map

`tools/dispatcher.py` is the single agent dispatcher, but not the only code path that calls providers.

Dispatcher routes:

- Drive routes to `tools.drive_tools`, which re-exports `tools.google_tools`.
- Calendar routes to `tools.calendar_tools`, which re-exports `tools.google_tools`.
- Gmail routes to `tools.gmail_tools`, which re-exports `tools.google_tools`.
- Sheets routes to `tools.sheets_tools`, which re-exports `tools.google_tools`.
- Airtable routes to `tools.airtable_tools`.
- Contact resolver routes to `tools.contact_resolver`.
- Daily report imports `daily_digest.build_digest`.
- Business memory imports `interaction_engine.search_business_memory`.
- CRM payment action imports `crm.crm_mark_payment_paid`.

### Airtable write paths

There is a declared single write gateway:

- `tools/airtable_gateway.py`: `airtable_create`, `airtable_patch`.
- It normalizes fields via `FIELD_ALIASES`, validates against `schema_cache.json`, strips read-only/forbidden fields, audits, and uses Airtable HTTP POST/PATCH.

Observed write callers using the gateway:

- `tools/airtable_tools.py` for `airtable_add` / `airtable_update`.
- `media_gateway.py` for Media Files metadata.
- `media_handler.py` for Business Memory transcript save after approval.
- `furniture_lead_funnel.py` for lead create/update.
- `tma_api.py` via `_gw_patch` / `_gw_create` wrappers in several routes.
- `lead_capture.py` uses gateway for scoring patch, but create path goes through `airtable_tools.airtable_add`.

Observed direct Airtable provider calls outside the write gateway:

- `crm.py` defines `_get`, `_post`, `_patch` using `httpx` directly against Airtable.
- `tma_api.py` reads Airtable directly in `_at_list` / `_at_get_record`.
- `daily_digest.py` reads Airtable directly.
- `providers/airtable_shim.py` reads Airtable directly.
- `tools/airtable_tools.py` reads Airtable directly for `airtable_get`, schema meta, linked-record lookup.
- `tools/dispatcher.py` performs direct Airtable GET for duplicate checks.

### Non-agent direct actions

These paths are tool-like but are not registered in the agent tool registry:

- Telegram command handlers in `app.py` for game actions such as `/done`, `/quests`, `/coins`.
- Media upload flow in `media_handler.py` called from Telegram and TMA routes.
- TMA API actions in `tma_api.py`, including lead updates, project hub actions, approvals, game actions, and upload handling.
- Lead qualification/session flow in `lead_qualifier.py` and `session_store.py`.
- Lead capture and lead memory flows in `lead_capture.py` and `lead_memory.py`.
- Scheduler jobs in `scheduler.py`, including game/week summary flows.

### Provider adapters / shims

Current provider-specific modules:

- Google REST: `tools/google_tools.py`
- Google Drive upload: `drive_adapter.py`
- Airtable gateway: `tools/airtable_gateway.py`
- Airtable tools: `tools/airtable_tools.py`
- Airtable shim: `providers/airtable_shim.py`
- Anthropic shim: `providers/anthropic_shim.py`
- Twilio shim: `providers/twilio_shim.py`
- Telegram send adapter: `tools/telegram_adapter.py`
- WhatsApp adapter: `tools/whatsapp_adapter.py`
- Voice/STT adapter: `voice_stt_adapter.py`
- Media orchestration: `media_handler.py`
- Media Airtable gateway wrapper: `media_gateway.py`

## Risk Findings

### R1. Tool result normalization is partial

Structured C53-A style dict results exist for:

- `airtable_add`
- `airtable_update`
- `gmail_draft`
- `gmail_send_draft`
- `calendar_create_event`

String results still exist for:

- `airtable_get`
- `airtable_get_schema`
- `search_lead`
- `gmail_read`
- `calendar_get_events`
- `search_drive`
- `read_drive_file`
- `sheets_append`
- `crm_mark_payment_paid`
- `get_daily_report`
- `search_business_memory`
- most direct/non-agent flows

Risk: `verify_execution` has stronger evidence checks only for selected structured write/send tools. Other tools can still look successful or failed based on text prefixes and heuristics.

### R2. Success proof is not persisted as a first-class Last Tool Result

Current proof is mostly turn-local:

- `tool_results_log` is created inside `app.py` during one agent turn.
- `memory_store.py` persists user/assistant conversation text in RAM with TTL, not structured tool evidence.
- `event_bus.py` stores pending approval payloads in RAM only.
- `lead_memory.py` and `session_store.py` persist lead/session state, not generic tool evidence.

Risk: after the reply is sent, the system lacks a durable, queryable "last tool result" record with tool name, inputs, provider evidence, external id, status, and timestamp.

### R3. Provider-specific code leaks into core/orchestration modules

Examples:

- `app.py` directly uses Telegram `bot.send_message`, webhook setup, and Telegram file APIs.
- `app.py` imports Airtable schema classes inside command handlers and calls `_at_list`, `_at_patch`, `_at_create` style helpers.
- `tools/dispatcher.py` directly imports `httpx` and calls Airtable for duplicate checks.
- `crm.py` directly constructs Airtable URLs and uses `httpx.get/post/patch`.
- `tma_api.py` directly reads Airtable and uses Airtable table names across route logic.
- `daily_digest.py` reads Airtable directly.
- `drive_adapter.py` and `tools/google_tools.py` use Google REST directly without a shared result contract.

Risk: F52 cannot assume provider isolation already exists. Some provider calls bypass registry, dispatcher, approval policy, output normalization, and proof capture.

### R4. Airtable schema governance is fragmented

Current governance sources include:

- `airtable_schema.py`
- `schema_cache.json`
- `schema_validator.py`
- `tools/airtable_gateway.py`
- `tools/airtable_tools.py`
- `tools/dispatcher.py`
- `tma_api.py`
- direct formula/table literals in feature modules

Hardcoded table / field names outside central schema governance include:

- `tools/dispatcher.py`: `_DEDUP_FIELDS`, `_ALIAS_MAP`, tenant-aware table set, `"Leads"`.
- `tools/airtable_tools.py`: `_TABLE_FIELDS`, `_LINKED_RECORD_FIELDS`, `"Leads"`, `"Projects"`, `"Units"`, `"Loans"`, game tables, and `search_lead` formula fields.
- `tools/airtable_gateway.py`: `READ_ONLY_FIELDS`, `LINKED_RECORD_FIELDS`, `"Leads"`, `"Media Files"`, and field literals.
- `session_store.py`: `"LeadSessions"` and session field literals.
- `tma_api.py`: many `"Leads"`, `"ProjectsHub"`, `"משימות (Tasks)"`, `"עסקאות (Deals)"`, `"תשלומים (Payments)"`, game table names, and formula field names.
- `daily_digest.py`: table literals for Leads, Contacts, Roadmap_Tasks, Deals, Tasks.
- `lead_capture.py`: audit payload literal `{"table": "Leads"}`.

Risk: schema changes can silently pass one layer but fail another. The gateway may validate with `schema_cache`, while other direct readers/writers can still rely on stale literals.

### R5. Approval policy is split

Approval/risk metadata appears in:

- `tool_registry.py`: `requires_approval`, `high_risk`.
- `event_bus.py`: `ACTIONS_REQUIRING_APPROVAL`.
- `app.py`: approval queue and callback execution path.
- `action_validator.py`: `_SENSITIVE_TOOLS`.
- `tools/dispatcher.py`: emergency-stop risky tools.

Risk: a tool may be sensitive in one layer but not approval-gated in another. Example: `calendar_create_event` is in `event_bus.ACTIONS_REQUIRING_APPROVAL`, while `tool_registry.py` does not mark it `requires_approval`.

### R6. Gateway rule is aspirational, not enforced globally

`tools/airtable_gateway.py` states that all Airtable writes must go through it. However:

- `crm.py` still has direct `_post` and `_patch` helpers.
- `tma_api.py` routes generally wrap writes through `_gw_patch/_gw_create`, but has direct provider reads and a large amount of provider-specific table logic.
- Legacy helper modules still parse record ids out of string tool results.

Risk: some write paths may bypass normalization, field stripping, audit shape, and structured evidence.

### R7. Result parsing depends on display text in several flows

Examples:

- `session_store.py` treats `"✅"` in result strings as success and regexes `rec\w+`.
- `lead_memory.py` treats `"✅"` in result strings as success and regexes `rec\w+`.
- `lead_capture.py` regexes `rec\w+` from `airtable_add` result.

Risk: once F52 changes result shape or localization, these flows can break unless they are normalized first.

### R8. Direct command/game flows are outside agent tool guarantees

Telegram commands and TMA game endpoints update Airtable/game state through local helper paths rather than the agent dispatcher. Some use schema constants, but they are not protected by `tool_registry`, `action_validator`, or the A32 tool evidence path.

Risk: "tool architecture" refactors that only cover `dispatch_tool` will leave visible production behaviors outside the new contract.

## Safe No-Brainer Refactors To Document For F52

These are low-risk candidates, but should still be implemented in a separate F52 implementation branch, not in this audit branch.

1. Add a read-only inventory test that compares tool names across `tools/schemas.py`, `tool_registry.py`, `action_validator.py`, and `tools/dispatcher.py`.
2. Introduce a shared `ToolResult` data shape in documentation/tests first, then migrate one read-only tool at a time.
3. Normalize `validate_tool_output` naming/location; it is currently in `guards/rate_limiter.py` even though it is not a rate limiter concern.
4. Add a passive `Last Tool Result` recorder that records existing normalized fields without changing execution decisions.
5. Move duplicate static Airtable alias maps from `tools/dispatcher.py` into a single schema-governed location.
6. Add a static audit check that flags `httpx.post/patch` to Airtable outside `tools/airtable_gateway.py`.
7. Add a static audit check that flags `"✅" in result` and `rec\w+` parsing in persistence flows.
8. Document which direct/non-agent actions are intentionally outside the agent tool dispatcher.

## Risky Changes Requiring Design Review

1. Replacing string outputs for all tools at once. This affects agent replies, approval callback display, lead/session persistence, and tests.
2. Moving CRM writes from `crm.py` direct Airtable calls to `tools/airtable_gateway.py`; field validation and linked-record behavior may change.
3. Centralizing all TMA Airtable table literals. TMA routes have route-specific filtering and UI expectations that may rely on current literals.
4. Making `calendar_create_event` approval policy consistent across registry/event bus. This can change user-visible scheduling behavior.
5. Enforcing gateway-only Airtable access for reads as well as writes. Existing read helpers return formatted Hebrew strings, not records.
6. Persisting all tool evidence to Airtable. This creates schema, privacy, retention, and cost questions.
7. Moving Telegram/WhatsApp send behavior behind one output gateway. Existing direct sends include typing indicators, callbacks, owner alerts, media notices, and command responses.
8. Treating direct command handlers as formal tools. This may require new permission semantics for commands currently protected by owner checks or route-level logic.

## F52 Design Questions

1. Should F52 normalize only agent tools, or all tool-like actions including TMA, scheduler, media, and command handlers?
2. Should Last Tool Result be stored in RAM, Airtable, logs, or a new durable store?
3. What is the minimum proof contract per provider?
   - Airtable: record id, table, operation, field keys, HTTP status?
   - Gmail: draft/message id, thread id, recipient, subject hash?
   - Calendar: event id, htmlLink, start/end?
   - Drive: file id, webViewLink, mime type?
4. Should tool outputs be bilingual display strings plus machine fields, or machine fields with display formatting at the edge?
5. Which schema source wins when `airtable_schema.py`, `schema_cache.json`, and module-local constants disagree?

## Audit Conclusion

The current system has a real agent tool spine: schemas, registry, validator, dispatcher, output validation, and A32 response gating. It also has many production-critical side paths that are tool-like but not governed by that spine.

The main F52 risk is not adding a new abstraction. The main risk is assuming the current abstraction already covers all writes, reads, success claims, and state persistence. It does not.
