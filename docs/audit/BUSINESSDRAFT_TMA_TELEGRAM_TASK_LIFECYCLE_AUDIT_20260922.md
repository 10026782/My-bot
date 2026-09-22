# TMA / Telegram / WhatsApp Draft UX + Task Lifecycle Audit

**Date:** 22/09/2026
**Classification:** `STATIC_VERIFIED` — read-only research, no code change.
**Truth Reset SHA:** `origin/main` = `7afe3db6516ab4a1da70121df1a3ab8f6d6c03e1`
**Scope:** `app.py` Telegram UX, `tma_api.py`, Task write paths, and DraftFlow consumers (`cmd_decision.py`/`cmd_marketing.py`/`cmd_update.py`) — how draft/preview/approval state is currently surfaced across channels, plus Task's write-path fragmentation, read as supporting evidence for [`BUSINESSDRAFT_UX_CONTRACT_FREEZE_20260922.md`](../architecture/BUSINESSDRAFT_UX_CONTRACT_FREEZE_20260922.md).

All reads via `git show origin/main:<path>` — working tree WIP ignored.

---

## 1. Telegram UX (`app.py`, 8907 lines)

**Lead-draft button flow** — `_handle_lead_draft_callback()` (`app.py:3014-3086`), keyboard built by `_lead_draft_keyboard()` (`app.py:3090-3103`). Callback data format: `"lead_draft_approve:{token}"`, `"lead_draft_edit:{token}"`, `"lead_draft_cancel:{token}"` (colon-split, token = `draft["callback_token"]` from `session_store.lead_sessions.get_lead_draft(chat_id)`).
- **cancel**: clears draft (`lead_sessions.clear_lead_draft`), edits message via `render_lead_draft_message(draft, state="cancelled")` (`core/lead_service.py`).
- **edit**: sets `draft["mode"]="edit_choice"`, prompts "איזה שדה לערוך? שם / טלפון / תחום / מקור / הערה." (`app.py:3049`) — no field-picker keyboard, next free-text reply is interpreted as the field choice.
- **approve** (default branch, `app.py:3057-3086`): calls `core.lead_candidate_handler._propose_lead_write()` → `core.action_gateway.action_gateway.approve_with_lifecycle_result(contract_id, approver=..., approver_role=...)`. Draft cleared only if `lifecycle.canonical_state in {executed, completed, failed, rejected}`.
- Registered at `app.py:8100-8101`: `data.startswith(("lead_draft_approve:", "lead_draft_cancel:"))` (note: `lead_draft_edit:` is NOT in this startswith tuple at 8100 — worth flagging, though the handler itself branches on `action=="lead_draft_edit"` at 3047, so it's presumably matched by a broader prefix elsewhere; not independently re-verified here).

**Free-text confirm/cancel** (`app.py:187-190`): `_CONFIRM_WORDS = frozenset({"כן","אשר","מאשר","מאשרת","✅","yes","y","ok","אוקי","בצע","קדימה"})`, `_CANCEL_WORDS = frozenset({"לא","בטל","דוחה","❌","no","n","ביטול","עצור","cancel"})`. Exact-word (not substring) match against lowered/stripped text, checked at multiple points in the main text-handling function (`app.py:5972, 6139, 5799-5801` for `_pending_approvals` bucket, `4947-4948, 5430, 5622`). Comment at `app.py:194-200` notes this exact-word grammar deliberately does NOT catch natural-language "what's pending" queries — a separate narrow intent-matcher was added for that.

**`_handle_approval_callback_impl()` re-enforcement** (`app.py:4113`): identity is re-resolved fresh from the *originally stored requester* (`user_chat_id = payload.get("user_chat_id", item.get("chat_id",""))`, `app.py:4233`; `identity = resolve_identity(channel, user_chat_id)`, `app.py:4296`), then **`app.py:4313`: `enforce(tool_name, identity)`** — wrapped in `try/except ToolDenied` that aborts with "⛔ הפעולה כבר אינה מורשית" (`app.py:4310-4318`). This matches CLAUDE.md's claim exactly — the stored contract is never trusted for authorization, only for content; the approver-clicking identity (`approver_chat_id`, `app.py:4127-4128`) is checked separately at intake (`actions.approve` capability) but the tool-level `enforce()` re-check uses the original requester's identity, not the approver's.

## 2. TMA UX (`tma_api.py`, 4743 lines)

**Generic write path**: no route literally named `tma_write` — the canonical internal function is `_queue_tma_write_approval()` (`tma_api.py:523-591`) wrapped by `_queue_or_owner_execute()` (`tma_api.py:732-763`). Both fail **closed** (HTTP 503) unless `FEATURE_ACTION_CONTRACT_PERSISTENCE` AND `FEATURE_ATOMIC_CLAIMS` are both live (`tma_api.py:582-597`) — no RAM-only/direct-execution fallback exists. It always calls `action_gateway.propose_action(tool_name="tma_write", ...)` (`tma_api.py:637-646`), i.e. unconditionally through ActionGateway — confirmed. `_queue_or_owner_execute` then auto-drives Owner's fresh pending contract through `_claim_and_execute_approval` (same path `/api/approvals/<id>` uses); Manager's request stays `pending_approval` (202) for manual approval. Payload shape into `_queue_tma_write_approval`: `{op: "post"|"patch", table, action, requested_by, ...caller fields}`; table must be in `tools.approval_actions._TMA_WRITE_ALLOWED_TABLES` (`tma_api.py:600-602`).

**Lead endpoints** — all direct-write (no client-visible draft/preview step), gated only by role + server-side ActionGateway approval policy:
- `/api/leads` GET only (`tma_api.py:1602`) — no POST /api/leads; lead *creation* happens outside TMA (`inbound_handler.py`/`lead_capture.py`).
- `/api/leads/<id>/status` PATCH (`tma_api.py:2037`) → `tma_update_lead_status`, editable: `status` only, validated against `LeadStatus.ALL`.
- `/api/leads/<id>` PATCH (`tma_api.py:2133`) → `tma_patch_lead`; editable fields = `_LEAD_EDITABLE` (STATUS, SCORE, OUTCOME, Next Followup, OWNER, NEXT_STEP; `tma_api.py:2075-2079`); Score is owner-only (`tma_api.py:2151-2153`).
- `/api/leads/<id>/outcome` POST (`tma_api.py:2195`) → `tma_set_lead_outcome`; maps outcome key to `{Outcome, Status}` pair via `_OUTCOME_STATUS_MAP`.
- `/api/leads/<id>/task` POST (`tma_api.py:2235`) → `tma_create_lead_task`; **create-only**, `op:"post"` on `Tables.TASKS`.
All five route through `_queue_or_owner_execute`/`_queue_tma_write_approval`. Frontend (`LeadDetail.tsx:209-281`) confirms direct-edit UX: `patchLead()` calls fire straight on save (score/status/outcome/followup fields), no separate review/confirm screen client-side — the approval gate is entirely server-side and role-conditioned (Owner auto-executes, Manager queues).

**Approvals contract**:
- `GET /api/approvals` (`tma_api.py:3246`) and `POST /api/approvals/bulk` (`tma_api.py:3257`, low-risk only, never medium/high) return/consume the `_fmt_approval()` shape (`tma_api.py:2674-2690`): `{id, action, requested_by, requested_at, risk_level, context_type, context_id, status, action_contract_id, legacy_read_only, projected_lifecycle_status, actionable}`.
- `POST /api/approvals/<id>` (`tma_api.py:3673`) body `{action: "approve"|"reject", note}`; both branches load the canonical `ActionContract` and drive `ActionGateway.approve()/reject()` via shared `_claim_and_execute_approval`/`_claim_and_reject_approval` helpers — never patches `Approvals.STATUS` directly.
- Frontend `Approvals.tsx` (233 lines) renders flat cards from exactly this shape; buttons only render when `approval.actionable === true` (`tma_api.py`-computed, `tma-frontend/src/components/Approvals.tsx:50`). No field-level diff/preview card — it's an action-summary list, not a draft editor.

**Frontend draft/review components**: `git ls-tree` on `tma-frontend/src` found only `Approvals.tsx`, `LeadCard.tsx`, `LeadDetail.tsx`, `LeadPipeline.tsx` — **no dedicated Draft/Review component exists on the TMA side**; the Telegram "lead draft" review-card concept (`render_lead_draft_message` with review/edit/cancel states) has no TMA equivalent today.

## 3. Task table writers (grep `Tasks` across `origin/main` *.py, non-test)

No single canonical Task writer exists — confirmed directly by a dispatcher comment: **`tools/dispatcher.py:1036-1038`**: "*(`_TASK_ALLOWED_UPDATE_FIELDS`) plus Domain-field canonicalization... No role re-check here: **there is no dedicated create-tool narrower than airtable_add/airtable_update for Tasks to under-cut**." Distinct write paths found:

1. **Generic agent/dispatcher path** — `airtable_add`/`airtable_update` with `table="Tasks"` (or `Tables.TASKS`), gated only by a field allowlist `_TASK_ALLOWED_UPDATE_FIELDS` (`tools/dispatcher.py:276`) checked for updates (`tools/dispatcher.py:1033-1046`). Supports both create and update (it's the generic Airtable writer). No Task-specific registry tool.
2. **NL deterministic short-circuit** — `core/turn_coordinator_runtime.py`: `gateway_call()` (line 223-234) maps canonical_tool `"task_create"` → `("airtable_add", {table, fields})` and `"task_update"/"task_complete"` → `("airtable_update", {table, record_id, fields})`; exposed via `queue_task_request()` (line 268-296), called from `app.py:1289` and `app.py:1520`. **Supports create and update/complete.**
3. **TMA `/api/leads/<id>/task` POST** (`tma_api.py:2235-2299`) → `tma_create_lead_task` → `airtable_add` on `Tables.TASKS`, copies domain/owner/lead-link from the parent lead. **Create-only, no update.**
4. **TMA `/api/tasks/<id>` PATCH** (`tma_api.py:3194-3238`) → `tma_update_task_status` → `airtable_update`, Owner-only, ownership-checked against `TaskFields.OWNER` links, field-restricted to `status`. **Update-only, no create.**
5. **Scheduler-created** — `abandoned_lead_worker.py::create_human_pipeline_task()` (lines 240-290) → `action_gateway.propose_action(tool_name="airtable_add", tool_inputs={table: Tables.TASKS, fields})` with a synthetic Manager-role `Identity`, `requires_approval=True`. **Create-only.**

**Conclusion for the design doc**: Task has no canonical `task_create`/`task_update` *tool-registry* entry — every path above bottoms out in the generic `airtable_add`/`airtable_update` primitives, differentiated only by caller-side field construction and (for path 1) a `canonical_tool` label that never reaches `tool_registry.py`. This is a real gap to resolve in the BusinessDraft migration-order decision.

## 4. DraftFlow consumers (`cmd_decision.py`, `cmd_marketing.py`, `cmd_update.py`)

- All three import `DraftSpec`, `resolve_draft_reply` from **`core/draft_flow.py`** (`cmd_decision.py:27`, `cmd_marketing.py:48`, `cmd_update.py:12`) — **not** `structured_command.py`. `core/structured_command.py` exists but is a separate primitive used only by the lead-draft path (`core/lead_candidate_handler.py`, `core/lead_service.py`) — i.e. there are **two parallel draft/structured-input primitive modules** today, not one shared module across all consumers as CLAUDE.md's "R6.2-R6.6 shared primitives" phrasing might suggest. Worth flagging explicitly in the design-freeze doc.
- State persistence is **consistent across all three**: module-level in-memory dict `_pending: dict[str, dict] = {}` (`cmd_decision.py:51`, `cmd_marketing.py:81`, `cmd_update.py:44`), each with `_STATE_TTL_SECONDS = 30*60` (30 min). None are session_store/DB-backed — a process restart silently drops any in-flight draft in all three commands equally (no divergence found between them on this axis). `cmd_decision.py` additionally uses `session_store.lead_sessions` but only for file-upload tracking (`FileUploadResult`, lines 1049-1095), not for the core draft state dict.

## File/line index

- `app.py`: 182-200 (word sets), 1726-1951 (`_queue_approval`/`_queue_approval_detailed`), 3004-3103 (lead-draft callback + keyboard), 4113-4340 (`_handle_approval_callback_impl`, `enforce()` at 4313)
- `tma_api.py`: 523-763 (`_queue_tma_write_approval`/`_queue_or_owner_execute`), 2037-2299 (lead endpoints), 3194-3238 (`/api/tasks/<id>`), 3246-3339 (`/api/approvals`, bulk), 3673-3742 (`/api/approvals/<id>`), 2674-2690 (`_fmt_approval`)
- `tools/dispatcher.py`: 276 (`_TASK_ALLOWED_UPDATE_FIELDS`), 1033-1046 (Tasks update-field gate + "no dedicated create-tool" comment)
- `core/turn_coordinator_runtime.py`: 223-296 (`gateway_call`, `prepare_task_gateway_call`, `queue_task_request`)
- `abandoned_lead_worker.py`: 240-290 (`create_human_pipeline_task`)
- `core/draft_flow.py`, `core/structured_command.py` (two separate primitive modules)
- `tma-frontend/src/components/`: `Approvals.tsx`, `LeadDetail.tsx`, `LeadCard.tsx`, `LeadPipeline.tsx` (no Draft component)
