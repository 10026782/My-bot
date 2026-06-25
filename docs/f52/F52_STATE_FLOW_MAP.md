# F52 State Flow Map

Updated: 25/06/2026

Scope: audit-only map of how state currently flows through BOSS before F52 implementation. This document does not change production behavior, refactor code, modify `app.py`, or change Airtable schema.

Source context:

- `docs/f52/F52_CURRENT_TOOL_MAP.md`
- `docs/f52/F52_CONTRACT_COVERAGE_MAP.md`
- `docs/f52/F52_BYPASS_MAP.md`
- Static audit of `app.py`, `memory_store.py`, `event_bus.py`, `session_store.py`, `lead_memory.py`, `lead_capture.py`, `media_handler.py`, `tma_api.py`, `scheduler.py`, `worker.py`, and `airtable_schema.py`

## 1. Executive Summary

BOSS now has three overlapping state systems:

1. Agent turn state: `app.py` builds a Claude message list from `memory_store.py`, tool calls, tool results, `tool_results_log`, and final reply sanitization.
2. Durable session state: `session_store.py` persists Universal Sessions to Airtable `Sessions` using `State JSON`, including `last_uploaded_file` and C60 `last_tool_result`.
3. Side-path state: approvals, media, lead memory, TMA writes, scheduler jobs, and proactive worker flows use their own RAM stores, Airtable business tables, or route-specific receipts.

The main improvement since the previous F52 maps is C60: after real agent tool dispatch, `_capture_last_tool_result()` writes a compact `last_tool_result` to `lead_sessions.set_last_tool_result()`, which syncs into `Sessions.State JSON`. This is useful, but it is not yet a general Last Tool Result contract. It does not cover approval-executed tools, TMA writes, scheduler jobs, media flows, route commands, or most background sends.

The highest-risk state gaps are:

- `tool_results_log` is per-turn RAM only and is not persisted.
- `memory_store.py` is process RAM only with a 12-hour TTL.
- `event_bus.PendingActionsStore` is process RAM only; approval payloads disappear on restart or expiry.
- TMA approvals persist pending payloads in Airtable `Approvals`, but this is a parallel approval state model, not the agent tool model.
- Lead/session code still reads some proof from strings or formatted Airtable output.
- Background jobs can read, write, or send without writing a normalized durable Last Tool Result.

## 2. Current State Stores

| Store | File / owner | Backing | Contents | Lifetime | Current risk |
|---|---|---|---|---|---|
| Conversation memory | `memory_store.py` singleton `memory` | RAM | Claude history messages by `memory_key`, role/content, channel metadata, last active time | Process lifetime, TTL 12 hours, trimmed by count/token estimate | Lost on restart; not durable proof; not shared across workers. |
| Per-turn tool proof log | `app.py` `tool_results_log` | RAM local variable | `{tool, content, ok}` for current agent turn | Single `run_agent()` call | Used by A32 final sanitization only; lost after reply. |
| Claude tool result messages | `app.py` `tool_results` | RAM local variable, sent back to Claude | Anthropic `tool_result` blocks keyed by `tool_use_id` | Single tool loop | Drives next model step but not durable evidence. |
| Universal sessions | `session_store.py` `lead_sessions` | RAM LRU plus Airtable `Sessions` | domain, channel, step, answers, done, score, tier, `last_uploaded_file`, `last_tool_result` inside `State JSON` | Durable if Airtable sync succeeds | Most durable state store, but stored as JSON text parsed back from formatted `airtable_get()` output. |
| Last uploaded file | `session_store.py` `last_uploaded_file` | `Sessions.State JSON`; optional linked Media File | `FileUploadResult` dict: type, url, file_id, original filename, timestamp, conversation id | Durable through session sync | Covers media context, not generic tool proof. |
| Last tool result | `session_store.py` `last_tool_result` | `Sessions.State JSON` | `{tool, status, summary, record_id, url, input, timestamp}` from agent tool dispatch | Durable through session sync if sync succeeds | Only one result, compact/truncated, not all flows, not all evidence. |
| Router pending approval | `app.py` `_pending_approvals` | RAM dict | original text, channel, domain, created_at | 10 minutes or restart | User text confirmation flow; no durable audit. |
| Event bus pending actions | `event_bus.py` `PendingActionsStore` | RAM dict | action, payload, chat_id, label, created, expires | 30 minutes or restart | Tool/non-tool approval payloads vanish on restart. |
| TMA approvals | `tma_api.py` / Airtable `Approvals` | Airtable | action label, requested by/at, risk, context type/id/data, status | Durable | Parallel to event bus; stores payload and status, but not generic ToolResult. |
| TMA receipts | `tma_api.py` `_persist_receipt()` | Airtable `Interaction Log` | JSON receipt in summary plus key insight | Durable if write succeeds | Flow-specific proof; failure is warning only and does not roll back write. |
| Lead memory debounce | `lead_memory.py` singleton | RAM plus Airtable `Leads` on flush/save | `LeadState`: contact fields, score/tier, counters, record id, dirty flag | RAM until flush; durable in Leads if save succeeds | Some proof fallback still parses strings/record ids. |
| Inbound lead capture | `lead_capture.py` | Airtable `Leads`; optional `lead_memory` | creates/updates lead and syncs score/tier/memory | Durable in Leads if write succeeds | Parses record ids and success text in places. |
| Media flow result | `media_handler.py` `MediaResult` | RAM return value; Drive/Airtable side effects | ok, transcript, drive url/id, media record id, message, error | Function call only; side effects durable elsewhere | Local dataclass is not generic Last Tool Result. |
| Business Memory | `airtable_schema.py` `Tables.BUSINESS_MEMORY` | Airtable | strategic/manual events, voice memory saves | Durable if write succeeds | Used as business memory, not generic proof store. |
| Scheduler state | `scheduler.py` | Mixed: RAM schedule loop, Airtable, files, logs | job runtime, reports, reminders, lead recovery, game state, usage reports | Depends on job/provider | No shared durable proof contract per job. |
| Worker state | `worker.py` | Provider calls and response string | proactive check result | Function call / external side effects | Agent-like background flow outside tool result contract. |

## 3. Agent-Turn State Flow

Current `run_agent()` state flow:

1. Input arrives from Telegram, WhatsApp, Meta WhatsApp, `/worker/trigger`, or another caller.
2. `resolve_identity(channel, chat_id)` maps the sender to identity/role/memory key.
3. If identity is `Role.LEAD`, `lead_capture.capture_inbound_lead(identity, user_text)` may persist a lead before normal agent handling.
4. Rate limiter checks `identity.memory_key`.
5. `_pending_approvals` may intercept the user message as a yes/no response for router-level approval.
6. `resolve_context_pronouns(user_text, chat_id)` reads `lead_sessions.get_last_tool_result()` and `lead_sessions.get_last_file()` before router intent detection.
7. Router chooses handler/domain/intent and whether tools are allowed.
8. `build_context()` creates system prompt, allowed tools, model, memory key, and budget.
9. `_build_tool_context(chat_id)` appends recent `last_tool_result` and `last_uploaded_file` context to the system prompt if fresh enough.
10. `memory.get_for_claude(ctx.memory_key)` returns RAM-only chat history, trimmed if too large.
11. Claude receives system prompt, allowed tool schemas, and messages.
12. If Claude returns tool use:
    - `enforce(tu.name, identity)` checks registry authorization.
    - If `meta.requires_approval`, `_queue_approval()` stores the payload in `event_bus.PendingActionsStore` and sends owner buttons.
    - Otherwise `dispatch_tool()`, `validate_tool_output()`, and `verify_execution()` run.
13. Tool result state splits:
    - `tool_results` goes back to Claude as `tool_result` content.
    - `tool_results_log` stores `{tool, content, ok}` for final A32 claim filtering.
    - `_capture_last_tool_result()` persists compact result context into `Sessions.State JSON`.
    - Some memorable tool strings are appended into `memory_store.py`.
14. Final text is passed through `sanitize_agent_response(final_reply, tool_results_log)`.
15. Final user/assistant messages are appended to `memory_store.py`.

Important gap: the strongest per-turn proof is `tool_results_log`, but that proof is not the durable `last_tool_result`. The durable `last_tool_result` is a compact summary of the last executed tool only.

## 4. Approval State Flow

There are three approval state flows.

### Router-Level Text Confirmation

`approval_response()` writes `_pending_approvals[chat_id] = {text, channel, domain, created_at}`. The next user message is interpreted as confirm/cancel if it matches `_CONFIRM_WORDS` or `_CANCEL_WORDS`.

State properties:

- RAM only.
- 10-minute TTL.
- Original user text is replayed into `run_agent(..., _skip_approval=True)`.
- No durable approval id, no persisted payload, no generic proof result.

### Agent Tool Approval Through Event Bus

When a registry tool requires approval, `_queue_approval()` calls `event_bus.bus.request_approval()` with payload:

- `tool_name`
- `tool_inputs`
- `user_chat_id`
- `channel`

`event_bus.PendingActionsStore` stores action id, action, payload, chat id, label, created, and expires. Telegram owner buttons carry `approve:{action_id}` or `reject:{action_id}`.

On approve:

1. `app.py` pops the pending action from RAM.
2. If payload has `tool_name`, it re-runs `enforce()`.
3. It executes `dispatch_tool()`, `validate_tool_output()`, and `verify_execution()`.
4. It sends a user notification and edits the owner message.

State gaps:

- Pending payload is RAM only and lost on restart.
- The approved execution path does not currently call `_capture_last_tool_result()`.
- No durable approval execution record is written in the generic ToolResult shape.

### TMA Approval Through Airtable

TMA write routes call `_queue_tma_write_approval()`. This writes an Airtable `Approvals` record with `Context Data` containing a JSON payload:

- `type: "tma_write"`
- action
- requested_by
- table/op/fields/record_id
- audit metadata

On `/api/approvals/<approval_id>` approve:

1. TMA reads the durable `Approvals` record.
2. It claims status by patching to `PROCESSING`.
3. It decodes `Context Data`.
4. `_execute_tma_write()` creates or patches Airtable records.
5. It persists a receipt to `Interaction Log`.
6. It patches approval status to approved or failed.

State properties:

- More durable than event bus approvals.
- Has per-approval locking in process.
- Approval payload and status are persisted.
- Receipt is flow-specific, not a generic Last Tool Result.

Design risk: event bus approvals and TMA approvals are both legitimate, but they are separate state machines with different durability and proof semantics.

## 5. Lead/Session State Flow

Lead/session flow has two overlapping meanings of "session":

- Conversation/session context in `session_store.py` `Sessions`.
- Lead business state in Airtable `Leads` and `lead_memory.py`.

### Universal Sessions

`PersistentSessionStore` keeps RAM LRU state and syncs to Airtable `Tables.SESSIONS`:

- `Sender ID`
- `Context Type`
- `Channel`
- `Created At`
- `Updated At`
- `State JSON`
- optional linked lead/decision/media/business memory fields

`State JSON` includes:

- domain
- step
- answers
- done
- drop_off_step
- score
- tier
- last_uploaded_file
- last_tool_result

Load path:

1. `get(sender)` checks RAM.
2. If missing, `_load_from_db(sender)` calls `airtable_get(Tables.SESSIONS, formula)`.
3. It parses formatted Airtable output for record id, context, channel, and balanced JSON from `State JSON`.
4. It restores RAM state.

Risk: the persisted session state is real, but loading depends on parsing formatted strings returned by `airtable_get()`, not structured records.

### Lead Capture

`lead_capture.capture_inbound_lead()` can run at the start of `run_agent()` for lead identities. It writes/updates Airtable `Leads`, syncs contact basics, and can update `lead_memory`.

Risk: it is outside the tool contract and still has proof paths based on record id regex and success strings.

### Lead Memory

`lead_memory.py` keeps `LeadState` in RAM and writes to Airtable on save/flush. `scheduler.py` calls `job_flush_lead_memory()` every 10 minutes.

Risk: until flushed, updates are RAM-only. Save proof has newer dict support, but still includes fallback paths for `"success text"` and `rec\w+`.

## 6. Media State Flow

Telegram media flow in `app.py` calls `media_handler.py`.

### Voice

1. Telegram voice metadata is checked for oversize before download.
2. `handle_voice_note()` uploads/saves/transcribes depending on flags and size.
3. It returns `MediaResult`.
4. Depending on transcript intent:
   - no action: display transcript and log for review.
   - hard action/no risk: save to Voice Inbox / Media Files pending.
   - risk or explicit memory save: queue approval through `event_bus`.
   - confirmed memory save: write Business Memory.

### Photo / Document

1. `handle_file_upload()` classifies size.
2. It resolves Drive folder, uploads to Drive, saves Airtable media metadata.
3. `app.py` can persist `FileUploadResult` with `lead_sessions.set_last_file()`.

State properties:

- `MediaResult` is structured locally.
- `last_uploaded_file` can be durable in `Sessions.State JSON`.
- Drive and Airtable provider ids may be durable in their provider tables.

State gaps:

- MediaResult is not normalized to generic `ToolResult`.
- Voice approvals use event_bus RAM pending state.
- Business Memory save proof is string/local status, not Last Tool Result.
- Last uploaded file is context state, not proof of all media side effects.

## 7. TMA State Flow

TMA routes are controller-driven, not agent-dispatch-driven.

Read routes:

- Use `_at_list()` / `_at_get_record()` direct Airtable reads.
- Build route JSON responses for dashboard, owner control, finance pulse, leads, assets, ventures, game state, and approvals.
- Do not write generic read result evidence.

Write routes:

- Owner writes can execute directly or through gateway helpers.
- Manager/high-risk writes often queue TMA approval records in Airtable.
- Approval execution writes receipts to `Interaction Log` where possible.

TMA state stores:

- Airtable business tables: Leads, Tasks, ProjectsHub, Contacts, Assets, Ventures, Game tables, etc.
- Airtable `Approvals` table for TMA pending approvals.
- Airtable `Interaction Log` for TMA receipts/audit.
- In-process `_APPROVAL_LOCKS` for same-process double-claim protection.

State gaps:

- TMA writes do not update `Sessions.last_tool_result`.
- TMA receipts are not the same shape as agent ToolResult.
- Some route writes still bypass dispatcher/validator/output validation.
- `_APPROVAL_LOCKS` is process-local only.

## 8. Scheduler/Background State Flow

`scheduler.py` starts recurring jobs that run outside the agent tool loop. It includes jobs for:

- pending cleanup
- daily digest
- git audit
- overdue payments
- daily collector
- follow-up scan
- payment reminders
- lead recovery
- learning cycle
- security reminder
- weekly summary
- email inbound
- attribution/audience/interaction reports
- game digest/reset/boss battle
- cost watchdog and usage report
- `job_flush_lead_memory()`

`worker.py` has `run_proactive_check()` that performs proactive provider reads and posts.

State properties:

- Scheduler state is mostly implicit in job timing and provider side effects.
- Some jobs write Airtable business state.
- Some jobs send Telegram/customer-facing messages.
- Some jobs only log success.

State gaps:

- No per-job Last Tool Result.
- No generic durable proof record for send/write outcomes.
- No shared approval/proof policy for background sends.
- Some job success is represented only by logs or message text.

## 9. Where State Is Lost Or Only In RAM

| State | Where | Loss condition | Impact |
|---|---|---|---|
| Claude conversation history | `memory_store.py` | Process restart, TTL expiry, trimming | Agent loses recent conversation context. |
| `tool_results_log` | `app.py` local variable | End of `run_agent()` | A32 final proof cannot be audited later. |
| Anthropic tool result blocks | `app.py` local variable | End of tool loop | Model got result, but no durable full transcript of tool evidence. |
| Router pending approval | `app.py` `_pending_approvals` | Restart, 10-minute TTL, unrelated message | Original requested action disappears. |
| Event bus pending actions | `event_bus.py` `pending` | Restart, 30-minute TTL, pop on confirm/reject | Owner approval buttons can point to missing payload. |
| Voice edit state | `media_handler.py` `_pending_voice_edits` | Restart or owner flow interruption | Owner edit flow loses pending transcript. |
| Lead memory dirty state | `lead_memory.py` | Restart before save/flush | Recent lead score/contact state can be lost before Airtable sync. |
| TMA approval locks | `tma_api.py` `_APPROVAL_LOCKS` | Restart/multiple workers | Only protects one process from duplicate approval execution. |
| Scheduler job runtime state | `scheduler.py` | Restart | In-flight job state and proof are not retained. |

## 10. Where Success Proof Is Stored Today

| Flow | Proof location today | Proof strength | Notes |
|---|---|---|---|
| Agent structured write tools | Tool result dict, `tool_results_log`, compact `Sessions.last_tool_result` | Medium/high | Strong during turn; durable only as compact last result. |
| Agent read tools returning strings | `tool_results_log` content, final reply evidence gate | Medium/low | No structured durable source ids for many reads. |
| Approved agent tools | Owner Telegram message, execution result text, logs | Medium/low | Does not appear to persist compact Last Tool Result after approved execution. |
| TMA approved writes | Airtable `Approvals` status and `Interaction Log` receipt | Medium/high | Durable but parallel contract. |
| TMA direct owner writes | Route JSON response, audit logs, business table mutation | Medium | Not generic ToolResult. |
| Airtable gateway writes | Provider response id and gateway audit log | Medium | Logs plus returned result; not necessarily durable result record. |
| Lead capture | Airtable `Leads` record, optional `lead_memory` state | Medium | Some proof is parsed from strings/record ids. |
| Session persistence | Airtable `Sessions.State JSON` | Medium | Durable session state, not immutable proof ledger. |
| Media upload | Drive file, Airtable Media Files, `MediaResult`, `last_uploaded_file` | Medium | Good local shape but not generic ToolResult. |
| Voice Business Memory save | Airtable `Business Memory`, event bus result string | Medium/low | Approval pending is RAM, final proof not normalized. |
| Scheduler sends | Logs, provider side effects, occasional Airtable records | Low/medium | No unified proof per job. |
| Worker proactive check | Return string/log/provider effects | Low | Outside tool proof contract. |

## 11. Recommended Minimum Last Tool Result Contract

F52 should define a minimum contract that can be produced by agent tools, approvals, TMA route actions, media flows, and background jobs without requiring all of them to become Claude tools.

Recommended minimum fields:

| Field | Required | Purpose |
|---|---|---|
| `id` | yes | Unique local result id for correlation. |
| `source` | yes | `agent_tool`, `approval`, `tma_route`, `media`, `scheduler`, `worker`, `command`. |
| `tool_or_action` | yes | Stable name such as `airtable_add`, `update_lead_status`, `_job_payment_reminders`. |
| `mode` | yes | `read`, `write`, `send`, `delete`, `background`, or `mixed`. |
| `status` | yes | `success`, `failed`, `pending_approval`, `rejected`, `partial`, `blocked`. |
| `provider` | recommended | Airtable, Gmail, Calendar, Drive, Telegram, Twilio, Anthropic, local. |
| `external_id` | recommended for writes | Provider record/message/event id. |
| `external_url` | optional | Provider link when available. |
| `evidence` | yes | Bounded dict with provider response ids, table, fields changed, status code, receipt id, or read source ids. |
| `approval` | required if applicable | approval id, approver, approval source, requested_at, approved_at/rejected_at. |
| `input_summary` | yes | Redacted compact input summary. |
| `output_summary` | yes | User-facing summary or result summary. |
| `error` | required on failure | Stable code plus safe message. |
| `actor` | yes | identity user id/role/channel where known. |
| `correlation` | yes | chat id/session id/tool_use_id/request id/job id where available. |
| `timestamp` | yes | UTC ISO timestamp. |
| `schema_version` | yes | Enables migration. |

Recommended storage model:

- Keep the current compact `Sessions.State JSON.last_tool_result` for context/pronoun resolution.
- Add or designate a durable append-only proof location for full results, because one mutable last-result field is not enough for audit.
- Store only redacted/bounded payloads; never store secrets, full email bodies, or full private transcripts by default.

## 12. Safe No-Brainer Fixes

These are documentation/testing candidates only for this audit; implement separately.

- Add a static audit test that every `dispatch_tool()` success path either records Last Tool Result or explicitly documents why it is not persisted.
- Add a static audit test that approved tool execution calls the same Last Tool Result recorder as direct agent tool execution, or is explicitly documented as an exception.
- Add a static audit test listing all RAM-only stores: `_pending_approvals`, `event_bus.pending`, `memory_store.memory`, `_pending_voice_edits`, `_APPROVAL_LOCKS`, and `lead_memory`.
- Add a static audit test that each `_job_*` has a declared state mode and proof target.
- Add a static audit test for `rec\w+`, `"success emoji"`, and formatted `airtable_get()` parsing in state persistence code.
- Document `Sessions.State JSON` as current context store, not as an append-only proof ledger.
- Document TMA `Approvals` + `Interaction Log` as a parallel durable approval/receipt path until F52 decides whether to unify it.
- Add a small state-flow fixture document for one happy path: user asks to create Airtable record, tool runs, A32 verifies, `last_tool_result` persists, final reply is sanitized.

## 13. Items Requiring Design Review

- Decide whether "Last Tool Result" means only the latest context hint or a durable audit ledger. Current code uses it as latest context.
- Decide where full durable proof lives: existing `Sessions.State JSON`, `Interaction Log`, a new table, files, or another storage layer.
- Decide whether event bus approvals should be persisted like TMA approvals or remain RAM-only.
- Decide whether approved agent tool execution must update `Sessions.last_tool_result`.
- Decide whether TMA route actions should emit F52 result records without becoming Claude tools.
- Decide how background jobs should express proof for read/write/send outcomes.
- Decide redaction and retention policy for stored tool inputs, transcripts, email bodies, Drive file names, and lead/customer data.
- Decide whether `memory_store.py` remains ephemeral conversation memory or should be backed by durable conversation/session storage.
- Decide whether `session_store.py` should load structured Airtable records instead of parsing formatted `airtable_get()` strings.
- Decide whether media `MediaResult` should become a generic F52 result, or be adapted into one at route boundaries.
