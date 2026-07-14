# F52 Approval Flow Map

> Status: Historical baseline audit
> Canonical program: F52 — Unified Approval Runtime Migration and Implementation
> Superseded for current-state conclusions by: ../phase-4c/CURRENT_STATE_MAP.md
> Do not use this document as current implementation instruction.

Updated: 26/06/2026

Scope: audit-only map of current approval flows in BOSS before F52 implementation. This document does not change production behavior, refactor code, modify `app.py`, or change Airtable schema.

Source context:

- `docs/architecture/f52-unified-approval-runtime/audits/original/F52_CURRENT_TOOL_MAP.md`
- `docs/architecture/f52-unified-approval-runtime/audits/original/F52_CONTRACT_COVERAGE_MAP.md`
- `docs/architecture/f52-unified-approval-runtime/audits/original/F52_BYPASS_MAP.md`
- `docs/architecture/f52-unified-approval-runtime/audits/original/F52_STATE_FLOW_MAP.md`
- Static audit of `tool_registry.py`, `event_bus.py`, `app.py`, `action_validator.py`, `tools/dispatcher.py`, `tma_api.py`, `scheduler.py`, `worker.py`, `core/router/risk_router.py`, `core/financial_gate.py`, `core/output_gateway.py`

## 1. Executive Summary

BOSS has several approval mechanisms that are useful but not yet governed by one approval contract:

- Router text confirmation in `app.py` (`_pending_approvals`) for high-risk intents before re-running the original request.
- Agent tool approval in `app.py` driven by `tool_registry.py` `requires_approval`.
- Event bus pending action approval in `event_bus.py` for tool and non-tool callbacks.
- TMA persisted approval records in Airtable `Approvals`, plus route-level risk classification and optional Emergency Window / OTP.
- Output/financial gates that require proof metadata for customer-facing financial overrides.
- Background jobs and scheduler sends, which mostly operate without a central approval policy.

The main approval risk is split source of truth. `tool_registry.py`, `event_bus.py`, `action_validator.py`, `core/router/risk_router.py`, and `tma_api.py` each classify risk or approval needs differently. Some of these lists are enforcement points; others are labels, validators, or route-local policies. The current runtime can be safe in specific paths, but F52 cannot assume "approval-required" means one consistent thing across the app.

Most important findings:

- `tool_registry.py` is the runtime source for agent tool approval in `run_agent()`.
- `event_bus.py` has its own `ACTIONS_REQUIRING_APPROVAL`, but agent runtime approval does not use that list directly.
- `action_validator.py` marks several tools sensitive, including `airtable_add` and `airtable_update`, but it is not the runtime approval source.
- `calendar_create_event` is in `event_bus.ACTIONS_REQUIRING_APPROVAL` but is not `requires_approval=True` in `tool_registry.py`, so normal agent execution does not queue approval from registry.
- `airtable_add` and `airtable_update` are sensitive in `action_validator.py` and labeled in event bus defaults, but are not `requires_approval=True` in `tool_registry.py` and are not in `event_bus.ACTIONS_REQUIRING_APPROVAL`.
- Approved agent tool execution revalidates registry permission and verifies execution, but does not update `Sessions.last_tool_result` or write a durable approval proof record.
- TMA approvals are more durable than event bus approvals because payload/status live in Airtable `Approvals`, but they are a parallel contract with route-specific receipts.

## 2. Current Approval Mechanisms

| Mechanism | Trigger | Stored where | Who can approve | TTL / expiry | Executes after approval | Revalidated? | Result verified? | Last Tool Result updated? | Durable proof? | Restart/timeout failure mode |
|---|---|---|---|---|---|---|---|---|---|---|
| Router text confirmation | `core/router/risk_router.py` returns `Handler.APPROVAL`; `app.py` calls `approval_response()` | `app.py` `_pending_approvals` RAM dict | Same user confirms by text (`כן`, `אשר`, `yes`, etc.) | 600 seconds via `_PENDING_APPROVAL_TTL` | Replays original text into `run_agent(..., _skip_approval=True)` | Router approval is bypassed by `_skip_approval`; later tool registry may still enforce tools | Only whatever downstream path verifies | Only if downstream direct agent tool executes | No | Restart loses pending text; timeout clears pending; unrelated message clears pending |
| Agent tool approval | Claude tool call with `ToolMeta.requires_approval=True` | `event_bus.PendingActionsStore` RAM dict | Telegram user with `is_owner` or `can("actions.approve")` in callback | 30 minutes in event bus pending store | `dispatch_tool()`, `validate_tool_output()`, `verify_execution()` | Yes: `enforce(tool_name, identity)` before execution | Yes: `verify_execution()` | No current call to `_capture_last_tool_result()` in approval callback | No generic durable proof; only messages/logs | Restart loses payload; timeout makes button action missing/expired |
| Event bus non-tool approval | Code calls `bus.request_approval()` for action without `tool_name`, e.g. media memory save / followup | `event_bus.PendingActionsStore` RAM dict | Same callback approval gate in `app.py` | 30 minutes | Emits `{action}.confirmed` handler | Handler-specific, not central | Handler-specific; usually string/local result | No | No generic durable proof | Restart/timeout loses payload; missing handler returns warning |
| TMA approval | TMA route calls `_queue_tma_write_approval()` | Airtable `Approvals` table, `Context Data` JSON | TMA-authenticated approver route; route checks identity/role around endpoint | Durable until status changes; no simple RAM TTL | `_execute_tma_write()` creates/patches Airtable and writes receipt | Partly: checks pending status, process lock, table allowlist, op type, route identity | Partly: returns `ok` dict and can set `FAILED`; no generic A32 | No | Yes: `Approvals` status + optional `Interaction Log` receipt | Restart preserves `Approvals`; in-process lock lost; processing records need operational recovery |
| TMA Emergency Window / OTP | `_queue_tma_write_approval()` when `EMERGENCY_WINDOW` flag enabled and action risk/platform requires it | OTP state in `core/otp.py`; emergency window state in core module/storage | Owner receives OTP; requester resubmits code | OTP/window-specific | Continues to TMA approval queue or rejects | Yes within route helper | Not generic tool verification | No | Partial; emergency action recording exists for window actions | Missing OTP/window rejects; restart behavior depends on underlying emergency/OTP storage |
| TMA emergency stop | `/api/health/emergency` route | In-process feature flag via `feature_flags.set_flag()` plus `_audit()` | Owner only | No approval; flag resets on Render dyno restart per code comment | Sets emergency runtime flag and notifies owner | Owner check and valid action check | No generic execution verification | No | Audit log only; runtime flag is process state | Restart clears stop flag unless external env/token disabled |
| Output gateway financial override | `core/output_gateway.py` / `core/financial_gate.py` customer-facing financial text | Audit id / envelope metadata | Requires `approved_by`, `approval_id`, `approved_at` for override metadata | Not an approval queue | Allows or blocks outbound send | Yes, financial gate checks metadata | GatewayResult | No | Gateway/audit-specific | Missing metadata rejects override |
| Scheduler/background sends | `_job_*`, `worker.py`, core job helpers | Mixed: logs, Airtable, provider side effects | Usually no explicit approval at job boundary | Schedule timing only | Sends/reports/writes directly or via job helper | Job-specific | Job-specific, mostly no A32 | No | Mixed, generally no generic proof | Restart may skip/incomplete jobs; no pending approval recovery |

## 3. Approval Sources Of Truth

| Source | File | What it says | Enforces runtime approval? | Notes |
|---|---|---|---|---|
| Tool registry metadata | `tool_registry.py` | `ToolMeta.requires_approval`, `high_risk`, roles | Yes for agent tool loop in `app.py` | Primary runtime source for Claude tool calls. |
| Event bus action set | `event_bus.py` | `ACTIONS_REQUIRING_APPROVAL` | Only where code calls `bus.needs_approval()` or explicitly uses event bus | Does not drive agent tool approval in current `run_agent()` path. |
| Action validator sensitive set | `action_validator.py` | `_SENSITIVE_TOOLS` | Input/risk validation only if `validate_action()` is used | Not a direct approval queue. Contains names not exposed/dispatched. |
| Router risk | `core/router/risk_router.py` | intent/domain/role -> `Handler.APPROVAL` or `RESTRICTED` | Yes for text requests before agent loop | Approves text intent, not a specific final tool call. |
| TMA action risk | `tma_api.py` `ACTION_RISK` | Low/Medium/High/Critical-like route action classification | Yes for TMA route approval helper | Defaults unmapped TMA actions to High. Separate from tool registry. |
| TMA Airtable approval state | Airtable `Approvals` via `tma_api.py` | pending/processing/approved/rejected/failed | Yes for TMA approval endpoint | Durable path but separate from event bus. |
| Financial/output gate metadata | `core/financial_gate.py`, `core/output_gateway.py` | approved override requires approval metadata | Yes for customer financial claims/sends | Not a general tool approval queue. |
| Emergency stop | `tma_api.py`, `feature_flags.py` | owner can set emergency flags | Yes for guarded code that checks flags | This is a control action, not an approval queue. |

## 4. Agent Tool Approval Flow

Runtime flow:

1. Claude returns a `tool_use`.
2. `app.py` calls `enforce(tu.name, identity)` from `tool_registry.py`.
3. If `meta.requires_approval` is true, `app.py` calls `_queue_approval()`.
4. `_queue_approval()` stores payload in `event_bus.PendingActionsStore` and sends Telegram owner buttons.
5. On callback, `_handle_approval_callback_impl()` checks the approver is owner or has `actions.approve`.
6. It pops the pending payload from event bus RAM.
7. If payload has `tool_name`, it re-runs `enforce()`, executes dispatcher, validates output, and runs `verify_execution()`.
8. It sends result text to the original user and edits the owner approval message.

Path details:

| Item | Current behavior |
|---|---|
| Trigger | `ToolMeta.requires_approval=True` in `tool_registry.py`. |
| Where approval is stored | `event_bus.PendingActionsStore` RAM dict. |
| Who can approve | Telegram identity with `is_owner` or `can("actions.approve")`. |
| TTL / expiry | 30 minutes from event bus `PENDING_TTL_MINUTES`. |
| What executes after approval | `dispatch_tool(tool_name, tool_inputs, identity)`. |
| Whether execution is revalidated | Yes, registry `enforce()` runs again before dispatch. |
| Whether result is verified | Yes, `validate_tool_output()` then `verify_execution()`. |
| Whether Last Tool Result is updated | No current `_capture_last_tool_result()` call in approval callback path. |
| Whether there is durable proof | No generic durable proof; messages/logs only. |
| Failure mode on restart/timeout | RAM payload lost or expired; owner button cannot execute action. |

Tools currently requiring approval by registry:

- `gmail_send_draft`
- `sheets_append`
- `crm_mark_payment_paid`

Important mismatch: `calendar_create_event` is not `requires_approval=True` in `tool_registry.py`, although `event_bus.py` classifies it as approval-worthy. `airtable_add` and `airtable_update` are also not registry approval tools.

## 5. Router Text Confirmation Flow

Router approval is intent-level, not tool-level.

Flow:

1. `core/router/risk_router.py` detects high-risk intent or sensitive domain/role combination.
2. Router returns `Handler.APPROVAL`.
3. `app.py` stores original text in `_pending_approvals[chat_id]`.
4. User replies with a confirm/cancel word.
5. On confirm, `app.py` replays the original text through `run_agent(..., _skip_approval=True)`.

Path details:

| Item | Current behavior |
|---|---|
| Trigger | Router `Handler.APPROVAL`, usually high-risk intent for senior role or sensitive domain for non-senior. |
| Where approval is stored | `app.py` `_pending_approvals` RAM dict. |
| Who can approve | Same chat/user that triggered the pending text. |
| TTL / expiry | 600 seconds via `_PENDING_APPROVAL_TTL`. |
| What executes after approval | The original text is reprocessed by `run_agent()`. |
| Whether execution is revalidated | Router approval is skipped with `_skip_approval=True`; downstream tool registry can still deny/approve tools. |
| Whether result is verified | Only if downstream agent tool path reaches A32. |
| Whether Last Tool Result is updated | Only if downstream direct agent tool executes and calls `_capture_last_tool_result()`. |
| Whether there is durable proof | No. |
| Failure mode on restart/timeout | Pending text lost; user must repeat request. |

Design note: this flow approves natural-language intent, while agent tool approval approves a specific tool payload. They are not equivalent.

## 6. TMA Approval Flow

TMA approval is route-local and durable in Airtable.

Flow:

1. TMA write route determines direct write versus approval queue.
2. `_queue_tma_write_approval(action, payload, identity, label)` classifies risk via `ACTION_RISK`, defaulting unknown actions to High.
3. If `EMERGENCY_WINDOW` is enabled, mobile/high/critical/medium gates can require Emergency Window, OTP, or explicit confirmation.
4. It writes an `Approvals` record with `Context Data` JSON.
5. `/api/approvals/<approval_id>` reads the approval, checks pending status, claims `PROCESSING`, decodes payload, and executes `_execute_tma_write()`.
6. `_execute_tma_write()` checks table allowlist, writes Airtable, audits, creates route-specific receipt, and attempts to persist receipt in `Interaction Log`.
7. Approval status becomes approved or failed.

Path details:

| Item | Current behavior |
|---|---|
| Trigger | TMA route calls `_queue_tma_write_approval()` for manager or gated write actions. |
| Where approval is stored | Airtable `Approvals` table. |
| Who can approve | TMA authenticated route identity with endpoint permission; implementation checks current status and identity context. |
| TTL / expiry | No simple in-code TTL; durable pending records remain until acted on. |
| What executes after approval | `_execute_tma_write()` post/patch into allowlisted Airtable tables. |
| Whether execution is revalidated | Partly: status re-read, process-local lock, table allowlist, op type, cleaned select values. |
| Whether result is verified | Partly: ok/error dict; no generic `verify_execution()`. |
| Whether Last Tool Result is updated | No. |
| Whether there is durable proof | Yes: `Approvals` status and optional `Interaction Log` receipt. |
| Failure mode on restart/timeout | Pending survives; process lock does not; `PROCESSING`/failed recovery is operationally separate. |

TMA approved write actions currently mapped in `ACTION_RISK`:

- `tma_create_project`: Medium
- `tma_update_lead_status`: Low
- `tma_patch_lead`: Low
- `tma_set_lead_outcome`: Medium
- `tma_create_lead_task`: Low
- `tma_create_followup`: Low
- unmapped future actions: High

## 7. Event Bus Approval Flow

`event_bus.py` provides the shared RAM pending store used by agent tool approval and media/non-tool approvals.

Core behavior:

- `PendingActionsStore.add()` creates an 8-character `action_id`.
- Stored shape: action, payload, chat_id, label, created, expires.
- `get()` and `pop()` enforce expiry.
- `confirm()` emits `{action}.confirmed`, but `app.py` approval callback usually calls `bus.pop()` directly and then executes tool or emits non-tool event.
- `cleanup()` is scheduled by `scheduler.py` `_job_cleanup_pending()`.

Path details:

| Item | Current behavior |
|---|---|
| Trigger | Any code calling `bus.request_approval()`. |
| Where approval is stored | RAM only. |
| Who can approve | Depends on caller; Telegram callback path checks owner or `actions.approve`. |
| TTL / expiry | 30 minutes. |
| What executes after approval | Tool path dispatches; non-tool path emits `{action}.confirmed`. |
| Whether execution is revalidated | Tool path yes; non-tool handler-specific. |
| Whether result is verified | Tool path yes; non-tool handler-specific. |
| Whether Last Tool Result is updated | No. |
| Whether there is durable proof | No generic durable proof. |
| Failure mode on restart/timeout | Pending action disappears or expires. |

Important mismatch: `event_bus.ACTIONS_REQUIRING_APPROVAL` is not the same as `tool_registry.requires_approval`. It includes `calendar_create_event` and `airtable_delete`, but excludes some registry-sensitive or validator-sensitive names.

## 8. Background/Scheduler Approval Gaps

Scheduler/background flows are not currently governed by a unified approval contract.

Examples:

- `_job_daily_digest`, `_job_weekly_summary`, `_job_learning_cycle`, `_job_security_reminder`, game jobs: send Telegram owner messages directly or through helpers.
- `_job_followup_scan`, `_job_lead_recovery`, `_job_abandoned_scan`, `_job_interaction_scan`: can queue follow-up/recovery actions, reminders, or scans; some helper paths use event bus approvals.
- `_job_payment_reminders`, `_job_overdue_payments`: payment-sensitive logic outside the agent approval contract.
- `worker.py run_proactive_check()`: proactive provider reads and Telegram notification outside tool approval.
- `core.cost_watchdog` can send owner alerts.

Current gaps:

- No central "background action requires approval" registry.
- No consistent risk tier for jobs.
- No generic Last Tool Result for background actions.
- No uniform durable proof for sends/writes.
- Job success often means logs, provider side effects, or route/helper-specific records.

## 9. Approval Mismatch Table

| Action/tool | Registry requires approval | Registry high risk | Event bus requires approval | Action validator sensitive | Router may require approval | TMA risk | Current mismatch |
|---|---:|---:|---:|---:|---:|---|---|
| `gmail_send_draft` | Yes | Yes | Yes | Yes | Yes for SEND_EMAIL intent | N/A | Best aligned for agent path. |
| `sheets_append` | Yes | No | Yes | No explicit sensitive set entry beyond required fields | Maybe by intent/domain | N/A | Approval aligned registry/event bus, but result is string and not durable proof. |
| `crm_mark_payment_paid` | Yes | Yes | No | Yes | Maybe finance-sensitive | N/A | Registry approval exists; event bus list omits it; implementation returns string/direct CRM patch. |
| `calendar_create_event` | No | No | Yes | Not in sensitive set | Maybe `CREATE_EVENT` normal or high-risk via router only in some intents | N/A | Event bus says approval, registry does not; normal agent tool can execute without registry approval. |
| `airtable_add` | No | No | No | Yes | Maybe by intent/domain | N/A | Validator sensitive, but registry does not require approval. |
| `airtable_update` | No | No | No | Yes | Maybe by intent/domain | N/A | Validator sensitive, but registry does not require approval. |
| `airtable_delete` | Not registered/exposed | N/A | Yes | N/A | Delete intent high-risk | N/A | Event bus references delete action not present in current agent schemas/dispatcher. |
| `crm_add_payment` | Not registered/exposed | N/A | No | Yes | Finance-sensitive | N/A | Validator-only CRM write; no exposed/dispatch contract. |
| `send_followup.confirmed` | N/A | N/A | Requested ad hoc | N/A | Background/helper-specific | N/A | Non-tool approval with handler-specific proof. |
| `media_save_to_memory` | N/A | N/A | Requested ad hoc | N/A | Media handler-specific | N/A | RAM approval, Business Memory write proof not generic. |
| `tma_update_lead_status` | N/A | N/A | N/A | N/A | N/A | Low | Durable TMA approval path, separate from agent approval. |
| `tma_set_lead_outcome` | N/A | N/A | N/A | N/A | N/A | Medium | Durable TMA approval path, separate from agent approval. |
| `emergency_stop` | N/A | N/A | N/A | N/A | N/A | Not in `ACTION_RISK` | Owner-only direct control action, no approval queue; runtime flag is in-process. |
| scheduler sends | N/A | N/A | Sometimes helper-specific | N/A | N/A | N/A | No central policy. |

## 10. Risk Classification Map

| Layer | Risk model | Values | Enforcement point | Drift risk |
|---|---|---|---|---|
| Router risk | intent/domain/role | read_only, normal, needs_approval, restricted | Before agent loop | Approves natural-language intent, not final provider side effect. |
| Tool registry | per tool metadata | `requires_approval`, `high_risk`, roles | Agent tool loop and approved callback revalidation | Main agent source, but not aligned with event bus/action validator. |
| Action validator | tool input/sensitive sets | sensitive tool list, required fields, structure checks | Only where validator is called | Contains hidden/non-dispatched tools and sensitive names without runtime approval. |
| Event bus | action name set | `ACTIONS_REQUIRING_APPROVAL` | Only if caller uses `bus.needs_approval()` or request helper | List does not govern agent tool runtime. |
| TMA risk | route action risk | Low, Medium, High, Critical-like behavior | `_queue_tma_write_approval()` | Separate route vocabulary; default High for unknown TMA actions. |
| Emergency Window | route/device/OTP policy | mobile/desktop, OTP, emergency window | TMA helper when flag enabled | Gated behind feature flag; not general approval. |
| Financial gate | content/metadata risk | blocked/escalated/approved | Outbound gateway | Requires proof metadata but not a queue. |

## 11. Durable Proof Map

| Approval path | Durable pending payload | Durable approval decision | Durable execution proof | Last Tool Result | Notes |
|---|---|---|---|---|---|
| Router text confirmation | No | No | No | Only downstream direct agent tool path | RAM only. |
| Agent tool via event bus | No | No | No generic proof | No in callback path | Strong runtime verification, weak durability. |
| Event bus non-tool | No | No | Handler-specific | No | Media/followup paths vary. |
| TMA approval | Yes, Airtable `Approvals.Context Data` | Yes, Airtable status | Partial: `Interaction Log` receipt if write succeeds | No | Most durable approval flow today. |
| Emergency stop | N/A | Owner route/action audit only | `_audit()` and notification | No | Runtime flag resets on restart. |
| Financial override | N/A | Metadata must include approval proof | Gateway audit/result | No | Proof metadata required, but separate from tool approval. |
| Scheduler/background | No central pending proof | No central decision proof | Mixed logs/provider/Airtable | No | Needs explicit F52 design. |

## 12. Safe No-Brainer Fixes

Document only for this audit; implement separately.

- Add a static approval mismatch test comparing `tool_registry.requires_approval`, `event_bus.ACTIONS_REQUIRING_APPROVAL`, and `action_validator._SENSITIVE_TOOLS`.
- Add a static test that lists every `bus.request_approval()` call site and whether it is tool or non-tool.
- Add a static test that approved tool callback execution updates or explicitly skips Last Tool Result.
- Add a static test that every TMA `ACTION_RISK` action appears in the F52 approval map.
- Add a static test that route-level control actions such as `emergency_stop` are listed as direct-control approvals or design-review exceptions.
- Add a scheduler audit table that classifies every `_job_*` as read/write/send/background and whether approval is required.
- Document that `event_bus.ACTIONS_REQUIRING_APPROVAL` is not currently the agent tool approval source of truth.
- Document that `action_validator._SENSITIVE_TOOLS` is not currently an approval queue.

## 13. Items Requiring Design Review

- Choose one approval source of truth for agent tools, or explicitly define precedence among registry, event bus, and validator.
- Decide whether `calendar_create_event` should require approval in registry or be removed from event bus requiring list.
- Decide whether `airtable_add` and `airtable_update` should require approval, and under which roles/tables/domains.
- Decide whether `crm_mark_payment_paid` should be added to event bus approval list or whether event bus list should stop duplicating tool policy.
- Decide whether approved agent tool executions should write `Sessions.last_tool_result` and a durable proof record.
- Decide whether event bus pending actions should persist to Airtable like TMA approvals.
- Decide whether TMA `Approvals` should become the general approval store or remain TMA-only.
- Decide how Emergency Stop should be audited and whether it needs a second confirmation or OTP.
- Decide approval policy for scheduler/background sends and writes.
- Decide retention/redaction rules for approval payloads that include emails, lead data, transcripts, financial content, or Airtable fields.

## 14. Recommended Migration Order

1. Add audit-only drift tests for approval lists and approval call sites.
2. Freeze terminology: distinguish "router text confirmation", "agent tool approval", "event bus approval", "TMA approval", and "financial output proof".
3. Make documentation declare `tool_registry.py` as current agent runtime approval source until replaced.
4. Add passive proof capture for approved agent tool execution without changing approval decisions.
5. Decide and document calendar/Airtable/CRM approval mismatches.
6. Add durable proof shape for event bus approvals, either in `Sessions.last_tool_result` plus append-only ledger or a dedicated approval/result table.
7. Bring non-tool event bus approvals under the same proof shape.
8. Decide whether TMA `Approvals` is the durable approval backend for all flows.
9. Add scheduler/background approval classification before changing job behavior.
10. Only after the maps/tests pass, consolidate policy in a separate F52 implementation branch.
