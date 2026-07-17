# F52 — Agent Message Output Map

Status: Verified repository audit; documentation only
Audit date: 17/07/2026
Evidence baseline: `origin/main` `96cf6430ec8d6018742fdf8042f0146873071cfd`
Scope: approval runtime, Action Gateway, lead capture and their live Telegram /
WhatsApp projections

## Method and boundaries

The audit traced message builders to their live channel sinks and searched for
`compose_status_reply`, `GatewayReply`, `_describe_tool_call`, approval callback
text, pending-list text, direct `bot.send_message` / `edit_message_text`, Twilio
reply construction, raw exceptions and technical identifiers.

This map describes `main`, not branch intent or production deployment state. It
does not change code and makes no claim that any proposed formatter is active.

Legend:

- Evidence: `yes` means state is derived from a durable/verified runtime fact;
  `partial` means some evidence exists but the message may overstate or expose a
  weaker fact; `no` means the builder does not establish execution evidence.
- Model wording: whether free-form model/user text can supply the displayed
  wording.
- Target: the future semantic state routed through the single formatter.

## Output inventory

| Current builder | Current state and data source | Evidence | Model wording | Technical leak risk | Live destination | Target |
|---|---|---:|---:|---|---|---|
| `app.py:_pending_clarification_message` (`679`) | Multiple legacy approvals; raw stored user request | no | yes (raw user text) | Markdown/backticks; request may contain internal-looking text | `run_agent` reply -> Telegram/Twilio | `approval_batch` from display payloads |
| `app.py:approval_response` (`700`) | Legacy single approval preview from `original_text` | no | yes | Bold Markdown; raw request presented as action | `run_agent` reply -> Telegram/Twilio | `approval_single` after a real frozen contract exists |
| `app.py:_describe_tool_call` (`761`) | Tool-specific preview from executable inputs | no | no | Tool name, table name, field keys, draft ID, record ID and raw input fallback | Owner approval message, callback edits, tests | Replace with display-payload formatter; never use as safe fallback |
| `app.py:_queue_approval_detailed_impl` duplicate branches (`965`, `982`) | Recently executed / already pending from cache and EventBus | partial | no | `tool_name`, origin channel; success-like duplicate wording relies on cache state | Model tool-result path -> sanitized agent reply | `failure`/`approval_single` with stable reason code |
| `app.py:_queue_approval_detailed_impl` owner notification (`994`, `1172`) | Approval request from EventBus label and action ID | partial | no | Tool/table/field data plus EventBus ID exposed directly | Telegram owner via `bot.send_message` | `approval_single` + opaque callback reference in renderer |
| `core.action_gateway.ActionGateway.propose_action` (`680` onward) | Persistence, dedup and proposal outcomes | yes for proposal state; not execution | no | Markdown marker and internal reason vocabulary can pass through callers | Lead Capture and raw tool loop | `approval_single` or `failure` from structured `GatewayResult` |
| `core.action_gateway:_describe_contract_for_reconfirmation` (`604`) | Frozen ActionContract payload | yes for proposal identity | no | Non-Lead fallback exposes `tool_name` and table | Reconfirmation and success label | Produce `display_payload`; safe generic fallback when absent |
| `ActionGateway.route_confirmation_word` (`996`) | Single reconfirmation or multi-contract choice | yes for live contract state | no | Multi list exposes tool name and contract ID prefix | Direct `run_agent` return -> channel | `approval_single`, `approval_batch` or `failure` |
| `ActionGateway.route_disambiguation` / `route_combined_word` (`1187`, `1237`) | Selected live contract and sibling closure | yes | no | Cancellation can expose `tool_name`; free-form status strings bypass common formatter | Direct `run_agent` return -> channel | `approval_batch` result through formatter |
| `ActionGateway.reject` / `route_cancellation_word` (`1051`, `1125`) | Durable rejection outcome | yes when transition succeeds | no | Internal lifecycle status can be shown by `reject`; inconsistent state markers | Direct `run_agent` return -> channel | `failure` with `ACTION_REJECTED` / persistence reason code |
| `ActionGateway.approve` / `_execute_contract` (`1337` onward) | Approval, atomic executor, provider result and lifecycle | mixed by branch | no | Raw exception interpolation at `1551`, `1578`, `1598`; internal runtime terms | Callback/free-text callers | Structured verified success, verified failure or unverified outcome |
| `ActionGateway.compose_status_reply` (`1690`) | `ActionFact` and optional frozen contract | partial | no | `tool_name`, record ID, error code, Markdown backticks | Gateway execution, callback wrapper, status query | Extend as the one public formatter API |
| `ActionGateway.query_execution_status` (`1717`) | Ledger latest status / live contracts | yes for ledger state | no | Pending fallback exposes `tool_name`; inherits composer leaks | Direct `run_agent` return -> channel | `success`, `failure`, `approval_single` or `idle` |
| `app.py:_notify_stale_or_resolved_callback` (`1582`) | Terminal/stale callback lookup plus legacy label | yes for no-new-dispatch; label is unsafe | no | Legacy label; Markdown; action details may be tool-derived | Telegram persistent message + edited approval message | `failure` with expired/resolved reason code |
| `app.py:_handle_approval_callback_impl` failure branches (`1823`–`1954`) | Gateway/legacy verification and lifecycle sync | mixed | no | Raw verifier reason, raw label, internal `ActionContract`, Markdown/backticks | Telegram requester and owner approval message | `failure` from stable error registry |
| `app.py:_handle_approval_callback_impl` success branch (`1956`–`2003`) | Wrapped `ActionFact` when flag on; raw tool user message when off | partial | provider/tool text may contribute when flag off | Record/tool data via composer or raw provider message; duplicate wording paths | Telegram requester + owner edit + callback popup | `success` only after verified evidence |
| `app.py:_handle_approval_callback_impl` reject branch (`2009`) | EventBus pop and legacy label | partial | no | Tool-derived label; Markdown | Telegram requester + owner edit + callback popup | `failure` / cancelled state from contract facts |
| `core.lead_candidate_handler:handle_lead_candidate` (`1020` onward) | Parsed lead plus Gateway proposal or direct write | mixed | user-derived lead text supplies fields | Bold Markdown; phone displayed; direct success outside composer | `run_agent` reply -> Telegram/Twilio | `clarification`, `approval_single`, or evidence-aware `success` |
| `core.lead_candidate_handler:_handle_mixed_batch` (`1140` onward) | Per-lead direct write/proposal facts | mixed | user-derived entity data | Multiple state markers; raw Gateway message nesting; independent success wording | `run_agent` reply -> Telegram/Twilio | `approval_batch` or batch `success` contract |
| `core.lead_candidate_handler:_handle_batch` (`1283`) | Direct provider writes and returned record IDs | partial | user-derived entity data | Explicit `record_id` in every success line; many emojis; success outside formatter | `run_agent` reply -> Telegram/Twilio | Batch `success` with human items only |
| `core.output_gateway.send_outbound` (`93`) | Output policy and single-speaker guard over already-built body | no semantic evidence of its own | yes, body is supplied by caller | Strict fallback can expose contract ref prefix; detects only selected Hebrew verbs | Twilio/other customer-capable adapters | Channel renderer/policy sink after semantic formatter |
| `app.py:_webhook_telegram_impl` (`3830`–`3855`) | Sends final `run_agent` string directly | inherited | yes | No semantic contract or renderer boundary; plain send currently avoids parse mode | Telegram | Telegram renderer |
| `app.py:_webhook_whatsapp_impl` (`4065`–`4089`) | Sends final agent/gateway string through output policy | inherited | yes | Same mixed body contract as Telegram; TwiML is transport-only | Twilio WhatsApp | WhatsApp renderer |
| `app.py:_webhook_whatsapp_meta_impl` (`4180`–`4196`) | Computes reply only when enabled; current outbound remains a stub | inherited | yes | Reply logged (truncated); not actually delivered | Log only, no customer delivery | Future WhatsApp renderer after real delivery evidence |

## Existing architectural assets

`GatewayReply` is already documented as the only type permitted to carry
action-status text, and `compose_status_reply()` is already called by Gateway
execution, callback wrapping and ledger status queries. It is therefore the
correct migration seam.

`core.output_gateway` is an outbound policy/delivery boundary, not a semantic
formatter. It must remain downstream of message composition. Its
single-speaker regex is a safety belt, not proof that a message is evidence-safe.

`_describe_tool_call()` and `_describe_contract_for_reconfirmation()` are not
safe formatter substitutes. Both fall back to technical names, and the former
reads executable inputs directly.

## Highest-priority gaps

1. Verified success can still disclose record IDs through
   `compose_status_reply()`.
2. Failure branches can interpolate raw executor/verifier exceptions.
3. Single and batch approval lists expose tool names, table names, EventBus IDs
   or contract ID prefixes.
4. Lead Capture constructs success and batch summaries independently and can
   expose record IDs.
5. Legacy approval previews display raw user/model text as if it described the
   frozen action.
6. Telegram and WhatsApp share strings but do not yet share a semantic contract
   plus explicit channel renderers.

## Migration routing decision

The target is not a new parallel message path. PR 1 extends the existing
`compose_status_reply`/`GatewayReply` boundary to accept a structured message
contract. PR 2 migrates the approval rows above first. Lead Capture and general
Gateway adoption remain later, independently reversible work.
