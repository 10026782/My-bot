# F52 Contract Coverage Map

> Status: Historical baseline audit
> Canonical program: F52 — Unified Approval Runtime Migration and Implementation
> Superseded for current-state conclusions by: ../phase-4c/CURRENT_STATE_MAP.md
> Do not use this document as current implementation instruction.

Updated: 25/06/2026

Scope: audit-only contract coverage map for current BOSS tools and tool-like actions. This document does not change production behavior, code, `app.py`, or Airtable schema.

Source context:

- `docs/architecture/f52-unified-approval-runtime/audits/original/F52_CURRENT_TOOL_MAP.md`
- `tools/schemas.py`
- `tool_registry.py`
- `action_validator.py`
- `tools/dispatcher.py`
- `guards/rate_limiter.py`
- `core/anti_hallucination.py`
- `event_bus.py`
- current test files

Legend:

- 🟢 covered
- 🟡 partial
- 🔴 missing
- ⚫ not applicable

Column abbreviations:

- Schema: exposed in `tools/schemas.py`
- Registry: present in `tool_registry.py`
- Input: covered by `action_validator.py`
- Dispatch: route in `tools/dispatcher.py`
- OutVal: passes through `validate_tool_output`
- Struct: returns structured `{ok, tool, external_id, evidence, user_message}`
- Proof: `verify_execution` / A32 success evidence checks
- Approval: consistent approval policy across app / registry / event bus
- Durable: persisted last tool result or durable proof record
- Tests: regression coverage

## 1. Summary Table

| Area | Schema | Registry | Input | Dispatch | OutVal | Struct | Proof | Approval | Durable | Tests | Summary |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Agent tool spine | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟡 | 🟡 | 🟡 | 🔴 | 🟡 | Core path exists, but result/proof/durable evidence are incomplete. |
| External write/send tools | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟡 | 🔴 | 🟢 | Best-covered group, but approval policy is split and no durable last result exists. |
| External read/search tools | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🔴 | 🟡 | ⚫ | 🔴 | 🟡 | Mostly string-returning tools with weaker proof. |
| CRM agent tool | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🔴 | 🟡 | 🟡 | 🔴 | 🔴 | Registered only for payment paid; provider writes still direct in `crm.py`. |
| Hidden validator-only CRM tools | 🔴 | 🔴 | 🟢 | 🔴 | ⚫ | 🔴 | 🔴 | 🟡 | 🔴 | 🟡 | `action_validator.py` knows them, but they are not exposed or dispatched. |
| TMA write actions | 🔴 | 🔴 | 🟡 | 🔴 | 🔴 | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 | Approval receipts exist for some writes, but outside agent contract. |
| Telegram command actions | 🔴 | 🔴 | 🟡 | 🔴 | 🔴 | 🔴 | 🟡 | 🟡 | 🟡 | 🔴 | Owner/role checks exist in places, but no formal tool contract. |
| Media upload actions | 🔴 | 🔴 | 🟡 | 🔴 | 🔴 | 🟡 | 🟡 | 🟡 | 🟡 | 🟢 | Good local result dataclasses and tests; outside agent tool contract. |
| Lead/session persistence actions | 🔴 | 🔴 | 🟡 | 🔴 | 🔴 | 🔴 | 🔴 | ⚫ | 🟡 | 🟡 | Persist business state, but parse display strings as proof. |
| Scheduler/background jobs | 🔴 | 🔴 | ⚫ | 🔴 | 🔴 | 🔴 | 🔴 | ⚫ | 🟡 | 🟡 | Operational jobs are not covered by the tool contract. |
| Direct provider adapters/shims | 🔴 | 🔴 | 🟡 | 🔴 | 🔴 | 🟡 | 🟡 | ⚫ | 🔴 | 🟡 | Provider details leak through multiple modules. |

## 2. Per-Tool Coverage Matrix

### Agent Tools

| Tool | Schema | Registry | Input | Dispatch | OutVal | Struct | Proof | Approval | Durable | Tests | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `search_drive` | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🔴 | 🟡 | ⚫ | 🔴 | 🟡 | Returns string from Google Drive REST. A32 has no-tool-evidence claim gate, but no structured file ids. |
| `read_drive_file` | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🔴 | 🟡 | ⚫ | 🔴 | 🔴 | Returns string content; no durable proof of file id/read source. |
| `calendar_get_events` | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🔴 | 🟡 | ⚫ | 🔴 | 🟡 | String read result; A32 can ground claims by tool identity but not durable event evidence. |
| `calendar_create_event` | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟡 | 🔴 | 🟢 | Structured result requires `event_id` and `htmlLink`. Approval mismatch: `app.py` and `event_bus.py` treat it as approval-worthy, `tool_registry.py` does not mark `requires_approval`. |
| `gmail_draft` | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | ⚫ | 🔴 | 🟢 | Structured draft result with `draft_id`; no durable Last Tool Result. |
| `gmail_send_draft` | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🔴 | 🟢 | Best-covered send tool: structured message id, registry approval, app approval, event bus approval. |
| `gmail_read` | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🔴 | 🟡 | ⚫ | 🔴 | 🔴 | String snippets; no message ids in normalized result contract. |
| `sheets_append` | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🔴 | 🟡 | 🟢 | 🔴 | 🔴 | Write action returns string success/failure, so proof is weak despite approval metadata. |
| `airtable_get` | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🔴 | 🟡 | ⚫ | 🔴 | 🟡 | String table dump; tenant scope exists, but no structured records/proof. |
| `airtable_add` | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟡 | 🔴 | 🟢 | Structured record id through gateway. Approval mismatch: `app.py` queues approval, registry does not mark `requires_approval`, event bus labels it but does not list it in `ACTIONS_REQUIRING_APPROVAL`. |
| `airtable_update` | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🟡 | 🔴 | 🟢 | Structured record id through gateway. Same approval mismatch as `airtable_add`. |
| `airtable_get_schema` | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🔴 | 🟡 | ⚫ | 🔴 | 🟡 | Reads live schema and returns formatted string. |
| `resolve_contact` | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🔴 | 🟡 | ⚫ | 🔴 | 🔴 | Search/resolution output is display text, not typed contact result. |
| `search_lead` | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🔴 | 🟡 | ⚫ | 🔴 | 🟡 | Uses `airtable_get("Leads", SEARCH(...))`, returns string. |
| `get_daily_report` | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🔴 | 🟡 | ⚫ | 🔴 | 🟡 | Report string from `daily_digest`; direct Airtable reads bypass agent tool result contract. |
| `search_business_memory` | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🔴 | 🟡 | ⚫ | 🔴 | 🔴 | Read/search tool outside structured result contract. |
| `crm_mark_payment_paid` | 🟢 | 🟢 | 🟢 | 🟢 | 🟢 | 🔴 | 🟡 | 🟡 | 🔴 | 🔴 | Registry marks approval/high risk, but `crm.py` returns strings and still uses direct Airtable `_patch`. |

### Validator-Only / Hidden Tool Names

| Tool-like name | Schema | Registry | Input | Dispatch | OutVal | Struct | Proof | Approval | Durable | Tests | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `crm_add_contact` | 🔴 | 🔴 | 🟢 | 🔴 | ⚫ | 🔴 | 🔴 | 🟡 | 🔴 | 🟡 | Present in `action_validator.py`; not exposed to agent or dispatcher. Direct CRM implementation exists and returns strings. |
| `crm_find_contact` | 🔴 | 🔴 | 🟢 | 🔴 | ⚫ | 🔴 | 🔴 | ⚫ | 🔴 | 🟡 | Validator-only name; CRM function exists outside contract. |
| `crm_list_contacts` | 🔴 | 🔴 | 🟢 | 🔴 | ⚫ | 🔴 | 🔴 | ⚫ | 🔴 | 🟡 | Validator-only name; CRM function exists outside contract. |
| `crm_update_last_contact` | 🔴 | 🔴 | 🟢 | 🔴 | ⚫ | 🔴 | 🔴 | 🟡 | 🔴 | 🟡 | Validator-only name; direct Airtable patch in CRM helper. |
| `crm_add_deal` | 🔴 | 🔴 | 🟢 | 🔴 | ⚫ | 🔴 | 🔴 | 🟡 | 🔴 | 🟡 | Validator includes funding-cost check, but no agent schema/registry/dispatch. |
| `crm_update_deal_status` | 🔴 | 🔴 | 🟢 | 🔴 | ⚫ | 🔴 | 🔴 | 🟡 | 🔴 | 🟡 | Validator-only name; direct CRM implementation returns strings. |
| `crm_list_deals` | 🔴 | 🔴 | 🟢 | 🔴 | ⚫ | 🔴 | 🔴 | ⚫ | 🔴 | 🟡 | Validator-only name. |
| `crm_add_payment` | 🔴 | 🔴 | 🟢 | 🔴 | ⚫ | 🔴 | 🔴 | 🟡 | 🔴 | 🟡 | Validator-only name; direct CRM write exists. |
| `crm_upcoming_payments` | 🔴 | 🔴 | 🟢 | 🔴 | ⚫ | 🔴 | 🔴 | ⚫ | 🔴 | 🟡 | Validator-only name. |
| `crm_overdue_payments` | 🔴 | 🔴 | 🟢 | 🔴 | ⚫ | 🔴 | 🔴 | 🟡 | 🔴 | 🟡 | Validator-only name; implementation can patch overdue statuses inside read flow. |
| `add_knowledge` | 🔴 | 🔴 | 🟢 | 🔴 | ⚫ | 🔴 | 🔴 | ⚫ | 🔴 | 🟡 | Validator-only; no visible schema/registry/dispatcher route in current tool spine. |

### Tool-Like Actions Outside `dispatch_tool`

| Tool-like action family | Schema | Registry | Input | Dispatch | OutVal | Struct | Proof | Approval | Durable | Tests | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Telegram `/status` | 🔴 | 🔴 | 🟡 | 🔴 | 🔴 | 🔴 | 🔴 | 🟡 | 🔴 | 🔴 | Command handler path, direct bot output, not an agent tool. |
| Telegram `/schema` | 🔴 | 🔴 | 🟡 | 🔴 | 🔴 | 🔴 | 🟡 | 🟡 | 🔴 | 🔴 | Owner-only check exists; reads schema/display output directly. |
| Telegram `/done` game action | 🔴 | 🔴 | 🟡 | 🔴 | 🔴 | 🔴 | 🟡 | 🟡 | 🟡 | 🔴 | Updates Quests and Coins_Log through app helpers; outside tool registry and A32 contract. |
| Telegram `/convert` | 🔴 | 🔴 | 🟡 | 🔴 | 🔴 | 🔴 | 🟡 | 🟡 | 🟡 | 🔴 | Owner-only conversion command; not normalized as ToolResult. |
| Telegram `/quest` and `/coins` | 🔴 | 🔴 | 🟡 | 🔴 | 🔴 | 🔴 | 🟡 | ⚫ | 🔴 | 🔴 | Read/display commands outside formal tool contract. |
| Approval callback tool execution | ⚫ | ⚫ | 🟡 | 🟡 | 🟢 | 🟡 | 🟢 | 🟢 | 🔴 | 🟡 | Uses queued payloads and `verify_execution`; pending store is in-memory. |
| `send_followup.confirmed` handler | 🔴 | 🔴 | 🟡 | 🔴 | 🔴 | 🔴 | 🟡 | 🟢 | 🟡 | 🟡 | Event bus action, not agent schema; routes outbound through output gateway. |
| Media voice upload | 🔴 | 🔴 | 🟡 | 🔴 | 🔴 | 🟡 | 🟡 | 🟡 | 🟡 | 🟢 | `MediaResult` dataclass exists; Drive/Airtable evidence is local, not generic ToolResult. |
| Media file/TMA upload | 🔴 | 🔴 | 🟡 | 🔴 | 🔴 | 🟡 | 🟡 | 🟡 | 🟡 | 🟢 | Similar to voice path; not part of agent tool registry. |
| Media Business Memory approval write | 🔴 | 🔴 | 🟡 | 🔴 | 🔴 | 🔴 | 🟡 | 🟢 | 🟡 | 🟡 | Approval exists; final Airtable write returns string and gateway record, not Last Tool Result. |
| TMA create project | 🔴 | 🔴 | 🟡 | 🔴 | 🔴 | 🟡 | 🟡 | 🟢 | 🟡 | 🟡 | Approval receipt path exists; not covered by agent tool schema/registry. |
| TMA lead status update | 🔴 | 🔴 | 🟡 | 🔴 | 🔴 | 🟡 | 🟡 | 🟢 | 🟡 | 🟡 | Approval-gated write path; no generic tool contract. |
| TMA create lead task/followup | 🔴 | 🔴 | 🟡 | 🔴 | 🔴 | 🟡 | 🟡 | 🟢 | 🟡 | 🟡 | Approval-gated route family; no generic ToolResult. |
| TMA finance/assets/ventures routes | 🔴 | 🔴 | 🟡 | 🔴 | 🔴 | 🟡 | 🟡 | 🟡 | 🟡 | 🟡 | Route-level logic and direct Airtable reads/writes; outside dispatcher. |
| TMA game/checkin actions | 🔴 | 🔴 | 🟡 | 🔴 | 🔴 | 🔴 | 🟡 | 🟡 | 🟡 | 🟡 | Updates game tables directly through TMA helpers; not formal tools. |
| Lead capture (`capture_inbound_lead`) | 🔴 | 🔴 | 🟡 | 🔴 | 🔴 | 🟡 | 🟡 | ⚫ | 🟡 | 🟡 | Uses Airtable tools/gateway; parses record ids from display result. |
| Lead qualifier/session store | 🔴 | 🔴 | 🟡 | 🔴 | 🔴 | 🔴 | 🔴 | ⚫ | 🟡 | 🟡 | Persists LeadSessions but uses string success checks and regex record id parsing. |
| Lead memory flush/save | 🔴 | 🔴 | 🟡 | 🔴 | 🔴 | 🔴 | 🔴 | ⚫ | 🟡 | 🟡 | Persists lead state, not tool evidence; parses display strings. |
| Daily digest builder | 🔴 | 🔴 | ⚫ | 🔴 | 🔴 | 🔴 | 🟡 | ⚫ | 🔴 | 🟡 | Direct Airtable reads and report string; available as `get_daily_report` but internals bypass contract. |
| Scheduler jobs | 🔴 | 🔴 | ⚫ | 🔴 | 🔴 | 🔴 | 🔴 | ⚫ | 🟡 | 🟡 | Background jobs are operational actions, not covered by tool schema/registry/proof. |
| `tools/schema_governance.py` | 🔴 | 🔴 | ⚫ | 🔴 | 🔴 | 🟡 | 🟡 | ⚫ | 🟡 | 🟡 | Standalone audit tool, not agent-exposed; produces reports not ToolResult. |
| `crm.py` helper functions | 🔴 | 🔴 | 🟡 | 🔴 | 🔴 | 🔴 | 🔴 | 🟡 | 🔴 | 🟡 | Direct Airtable `_get/_post/_patch`; bypasses gateway contract except where called through `crm_mark_payment_paid`. |
| `drive_adapter.upload_file` | 🔴 | 🔴 | 🟡 | 🔴 | 🔴 | 🟡 | 🟡 | ⚫ | 🟡 | 🟢 | Strong local dataclass evidence, but not generic tool contract. |
| `voice_stt_adapter.transcribe` | 🔴 | 🔴 | 🟡 | 🔴 | 🔴 | 🟡 | 🟡 | ⚫ | 🔴 | 🟢 | Local transcript result, not agent ToolResult/durable evidence. |
| Provider shims in `providers/*` | 🔴 | 🔴 | 🟡 | 🔴 | 🔴 | 🟡 | 🟡 | ⚫ | 🔴 | 🔴 | F13-related shims exist, but are not wired into live tool path. |

## 3. Missing Contract Pieces

### Global Missing Pieces

1. Durable Last Tool Result is missing for all current tools.
   - Current evidence is per-turn `tool_results_log`, log messages, provider ids in returned dicts, or business records.
   - There is no durable, queryable record with tool name, input summary, status, external id, evidence, timestamp, and caller identity.

2. Output normalization is not universal.
   - Structured results exist for `airtable_add`, `airtable_update`, `gmail_draft`, `gmail_send_draft`, and `calendar_create_event`.
   - Read tools and several write-like tools still return display strings.

3. Approval policy has multiple sources of truth.
   - `app.py` has `_APPROVAL_TOOLS`.
   - `tool_registry.py` has `requires_approval` and `high_risk`.
   - `event_bus.py` has `ACTIONS_REQUIRING_APPROVAL`.
   - `action_validator.py` has `_SENSITIVE_TOOLS`.
   - `tools/dispatcher.py` has emergency-stop risky tools.

4. Direct provider calls bypass contract layers.
   - `crm.py` uses direct Airtable HTTP helpers.
   - `tma_api.py` directly reads Airtable and uses many table/field literals.
   - `daily_digest.py` directly reads Airtable.
   - `tools/google_tools.py` and `drive_adapter.py` call Google REST directly.
   - `tools/dispatcher.py` performs direct Airtable duplicate GET.

5. Regression tests are uneven.
   - C53-A structured-result checks are good for the five structured tools.
   - Smoke tests check dispatcher/registry alignment.
   - Tool-like actions outside `dispatch_tool` have route-specific tests at best, not contract coverage.

### Per-Contract Missing Pieces

| Contract piece | Missing / partial areas |
|---|---|
| Schema exposed to agent | Hidden CRM names, all TMA routes, Telegram commands, media flows, scheduler jobs, provider adapters. |
| Registry entry | Hidden CRM names, direct command/TMA/media/scheduler actions. |
| Input validation | Most agent tools have it; route/direct flows rely on route-specific parsing or ad hoc validation. |
| Dispatcher route | Only agent tools have it; tool-like flows bypass `dispatch_tool`. |
| Output validation | Only agent loop and approval callback call `validate_tool_output`; direct flows do not. |
| Structured ToolResult | Missing for most reads/search/report tools and direct flows. |
| Success proof | Strong only for selected structured write/send tools; weak for string tools and direct flows. |
| Approval policy | Split and inconsistent for `calendar_create_event`, `airtable_add`, `airtable_update`, and CRM/direct actions. |
| Durable evidence | No generic Last Tool Result persistence. Business records/logs are not equivalent. |
| Regression tests | Strongest around C53-A and media; weak for registry/approval mismatch and direct provider bypasses. |

## 4. Tools With Highest Risk

1. `sheets_append`
   - Write action with approval metadata but string result.
   - No structured spreadsheet id/range/update proof.
   - Success claim can be grounded only weakly.

2. `crm_mark_payment_paid`
   - High-risk payment mutation.
   - Registry marks approval/high risk, but implementation returns string and `crm.py` uses direct Airtable patch.
   - No structured payment proof or durable last result.

3. `airtable_add` / `airtable_update`
   - Good structured result and gateway path when called through agent.
   - Approval policy mismatch across `app.py`, registry, and event bus.
   - Several non-agent flows still parse display strings around Airtable results.

4. TMA write actions
   - Some have approval receipts and gateway writes.
   - They are outside schema/registry/dispatcher/output validation.
   - Route-specific behavior makes them easy to miss in tool-contract refactors.

5. Telegram game commands
   - Mutate Airtable/game state outside the tool spine.
   - No structured ToolResult or durable generic proof.
   - Owner checks may exist, but not a common contract.

6. `crm.py` helper family
   - Direct provider calls bypass gateway promises.
   - Hidden validator-only names create false confidence: validation exists but no agent route exists.

7. Read/search tools returning strings
   - `search_drive`, `read_drive_file`, `gmail_read`, `calendar_get_events`, `airtable_get`, `search_lead`, `resolve_contact`, `get_daily_report`, `search_business_memory`.
   - These can support user-visible claims without durable normalized evidence.

8. Lead/session persistence
   - Persists business state but relies on localized display strings and regex record id extraction.
   - F52 result-shape changes can break these flows unless migrated deliberately.

## 5. Safe No-Brainer Fixes

Documented only; do not implement in this audit branch.

1. Add a static contract inventory test comparing:
   - `tools/schemas.py`
   - `tool_registry.py`
   - `action_validator.py`
   - `tools/dispatcher.py`
   - `app.py` approval tool set
   - `event_bus.py` approval action set

2. Add a passive `ToolResult` type definition and examples in docs/tests before changing runtime.

3. Add a read-only audit test that flags:
   - `httpx.post` / `httpx.patch` to Airtable outside `tools/airtable_gateway.py`
   - `"✅" in result`
   - `rec\w+` parsing from display strings
   - tool names present in validator but absent from schema/registry/dispatcher

4. Normalize read-only tools one at a time.
   - Start with `calendar_get_events` and `gmail_read`, because they already produce provider ids internally.
   - Keep `user_message` stable while adding machine fields.

5. Move `validate_tool_output` out of `guards/rate_limiter.py` into a neutral module, after tests lock current behavior.

6. Add a non-invasive Last Tool Result recorder in shadow mode.
   - It should observe existing results and store only bounded metadata.
   - It should not decide success/failure until a later design review.

7. Add documentation comments around direct/non-agent flows marking them "outside agent tool contract" until F52 decides their target state.

8. Create an approval-policy report that lists mismatches without changing behavior.

## 6. Items Requiring Design Review

1. What counts as a "tool" for F52?
   - Agent-visible only?
   - Agent-visible plus TMA/Telegram/media/scheduler actions?
   - Any provider-calling function?

2. Durable evidence storage.
   - RAM is not durable.
   - Airtable adds schema/cost/privacy concerns.
   - Logs are not easy to query as last tool state.
   - A new lightweight store may be needed.

3. Approval source of truth.
   - Decide whether registry, event bus, app, or a new policy table owns approval.
   - Resolve `calendar_create_event`, `airtable_add`, and `airtable_update` mismatch deliberately.

4. Structured result migration strategy.
   - Big-bang migration is risky because display text parsing exists in lead/session flows.
   - Prefer additive structured fields with unchanged `user_message` first.

5. CRM migration to gateway.
   - Moving `crm.py` writes to `tools/airtable_gateway.py` can change validation, field stripping, linked records, and user-visible strings.

6. TMA route contract.
   - TMA endpoints are operationally important but route-shaped, not tool-shaped.
   - Decide whether to wrap them as tools, give them a parallel contract, or leave them separate with explicit audit checks.

7. Read tool evidence granularity.
   - For reads, proof may need query hash, provider ids, record/file/message ids, count, and timestamp.
   - Storing full content may be unnecessary and unsafe.

8. Provider abstraction overlap.
   - F12/F13 provider interfaces exist as planning/code-complete dead code in places.
   - F52 should not accidentally choose a conflicting provider abstraction before that design is resolved.

9. Localization boundary.
   - Current code often uses Hebrew display strings as success indicators.
   - F52 should decide whether machine status is always English/typed and display text is edge-only.

10. Regression test scope.
   - Decide whether F52's contract tests run as pure static audits, unit tests with mocked providers, or integration tests with credentials.

## Audit Conclusion

The current agent tool spine is real and useful, but contract coverage is uneven. The safest F52 direction is additive and evidence-first: document the contract, add static drift tests, add passive durable result capture, then migrate tools one family at a time.

The highest-risk assumption would be treating `dispatch_tool` as the whole system. It is not. TMA actions, Telegram commands, media flows, lead/session persistence, scheduler jobs, and direct provider helpers all perform tool-like work outside the current agent contract.
