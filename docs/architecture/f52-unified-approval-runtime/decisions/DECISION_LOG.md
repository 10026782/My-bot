# F52 — Decision Log

This log records planning decisions for the F52 program. It is not runtime implementation authority until the planning gate is explicitly approved.

## D-001 — Establish F52 as the canonical program name

- Date: 14/07/2026
- Status: Closed
- Decision: Rename the program to **F52 — Unified Approval Runtime Migration and Implementation Program**. Phase 4C remains a historical research identifier only.
- Rationale: The verified scope spans channels, tools, claims, identity, projections, media and background work; it is not a point bug fix.
- Affected documents: `README.md`, all Phase 4C research documents, this log.

## D-002 — All 11 `requires_approval` tools remain in the claim cohort

- Date: 14/07/2026
- Status: Closed
- Decision: Every currently marked `requires_approval` tool requires verified live PostgreSQL execution ownership before provider execution, including `gmail_draft`, `send_followup` and `send_recovery`.
- Rationale: Reclassification is a separate business-policy decision; exceptions would recreate an execution-boundary bypass during migration.
- Affected documents: `research/OPEN_QUESTIONS.md`, `spec/F52_UNIFIED_APPROVAL_RUNTIME_SPEC.md`, `rollout/MIGRATION_PLAN.md`.

## D-003 — Future policy reclassification is outside F52 migration

- Date: 14/07/2026
- Status: Closed
- Decision: Changing approval requirements for drafts, notifications or low-risk actions is excluded from the F52 migration.
- Rationale: F52 migrates existing policy safely; it does not silently broaden business-policy scope.
- Affected documents: `research/OPEN_QUESTIONS.md`, `spec/F52_UNIFIED_APPROVAL_RUNTIME_SPEC.md`.

## D-004 — Signed references are opaque, signed, versioned and expiring

- Date: 14/07/2026
- Status: Closed
- Decision: Channel references are transport tokens with action/recipient binding, TTL, version and key-rotation readiness.
- Rationale: UI data must resolve one existing contract and must not reconstruct executable payload.
- Affected documents: `spec/F52_UNIFIED_APPROVAL_RUNTIME_SPEC.md`, `rollout/MIGRATION_PLAN.md`.

## D-005 — Presentation state uses a separate projection store

- Date: 14/07/2026
- Status: Closed
- Decision: Presentation state is stored outside ActionContract and linked by `contract_id`.
- Rationale: A contract is canonical authority; adapter/provider/message state is replaceable display state.
- Affected documents: `spec/F52_UNIFIED_APPROVAL_RUNTIME_SPEC.md`, `rollout/MIGRATION_PLAN.md`.

## D-006 — Legacy EventBus compatibility is lookup-only

- Date: 14/07/2026
- Status: Closed
- Decision: A legacy EventBus ID can resolve only an existing unambiguous canonical contract; it can never create, infer, repair or persist one.
- Rationale: Legacy payload is not trustworthy execution authority.
- Affected documents: `spec/F52_UNIFIED_APPROVAL_RUNTIME_SPEC.md`, `rollout/CUTOVER_PLAN.md`.

## D-007 — AP-36 is a separate narrow hotfix

- Date: 14/07/2026
- Status: Closed — follow-up required
- Decision: AP-36 will move the Meta media enablement/readiness guard before media processing as a separate hotfix.
- Rationale: The hotfix must prevent Drive/Airtable writes while the relevant Meta media path is disabled, without changing approval policy or adding the final typed media handler. It requires a regression test; full media migration remains in the later F52 media workstream.
- Affected documents: `audits/phase-4c/CURRENT_STATE_MAP.md`, `research/MIGRATION_OPTIONS.md`, this log.

## D-008 — Implementation components deploy dark before cutover

- Date: 14/07/2026
- Status: Closed
- Decision: F52 components are deployed dark and pass readiness checks before activation/cutover.
- Rationale: Authority changes require observable staged verification and a rollback boundary.
- Affected documents: `rollout/MIGRATION_PLAN.md`, `rollout/CUTOVER_PLAN.md`, `rollout/ROLLBACK_PLAN.md`.

## D-009 — Rollback never restores direct execution

- Date: 14/07/2026
- Status: Closed
- Decision: Rollback may disable presentation or new proposals, but never restores a direct-execution fallback.
- Rationale: A rollback must not reintroduce the P0 bypass the migration removes.
- Affected documents: `spec/F52_UNIFIED_APPROVAL_RUNTIME_SPEC.md`, `rollout/ROLLBACK_PLAN.md`.

## D-010 — `display_payload` is the canonical user-message contract

- Date: 17/07/2026
- Status: Closed for planning; implementation not started
- Decision: New and migrated action producers use structured `display_payload`.
  Free-form `human_summary` is a read-only, untrusted compatibility hint during
  migration and is never execution evidence. The existing
  `compose_status_reply()` / `GatewayReply` boundary is extended rather than
  creating a parallel formatter.
- Rationale: The current output audit found that tool names, table/record IDs,
  raw errors and unverified text reach user-message builders. Structured display
  facts allow sanitization and evidence gating without changing approval or
  execution policy.
- Boundary with D-005: semantic display facts may be frozen with the action;
  channel delivery/message/callback state remains in the separate presentation
  projection store.
- Affected documents: `spec/UNIFIED_MESSAGE_UX_STANDARD.md`,
  `audits/phase-4c/AGENT_MESSAGE_OUTPUT_MAP.md`,
  `rollout/UNIFIED_MESSAGE_IMPLEMENTATION_PLAN.md`.

## D-011 — Erratum: PR #471 added a parallel approval-lifecycle formatter, not an extension of D-010's boundary

- Date: 27/07/2026 (added by a Context Librarian metadata audit, not a new owner decision)
- Status: Open — flags a drift from D-010, does not resolve it
- Observation: PR #471 (`c64da20`, merged 27/07/2026) introduced `ApprovalLifecycleResult`
  (`core/action_gateway.py`), built by `build_approval_lifecycle_result()` and consumed by
  `approve_with_lifecycle_result()`/`reject_with_lifecycle_result()`, as the canonical
  renderer for approval-lifecycle turns under `FEATURE_SINGLE_SPEAKER_APPROVAL_UX`
  (default off). This is a second formatter alongside `GatewayReply`/
  `compose_status_reply()`, not an extension of that existing boundary as D-010
  requires ("The existing `compose_status_reply()` / `GatewayReply` boundary is
  extended rather than creating a parallel formatter").
- Rationale for recording rather than fixing: this audit is a read-only Context
  Librarian metadata refresh; changing runtime code or resolving the formatter
  duplication is out of its scope and requires an owner decision (reconcile
  `ApprovalLifecycleResult` into `compose_status_reply()`, or formally supersede
  D-010's single-API requirement for the approval-lifecycle subset).
- Affected documents: `spec/UNIFIED_MESSAGE_UX_STANDARD.md`,
  `docs/context_librarian/layers/ux_f52.json`.

## D-012 — `MessageContract` is the sole canonical presentation contract; D-011 closed by reconciliation

- Date: 28/07/2026
- Status: Closed for planning; implementation not authorized
- Decision (owner-approved, resolving D-011):
  1. **Canonical public UX contract.** `MessageContract`
     (`spec/MESSAGE_CONTRACT_ENVELOPE_CONTRACT_V1.md`) is approved as the sole
     canonical input to the final UX formatter
     (`core/agent_message_formatter.py::format_agent_message()`). This does
     not immediately replace `ApprovalLifecycleResult`, `GatewayReply`, or
     `ActionFact` — all three remain valid internal fact/result contracts.
     They must reach the formatter only through adapters that produce
     `MessageContract`. The approved architecture is **reconciliation, not
     immediate deletion or supersession**. D-011 is closed conceptually:
     multiple internal fact/result contracts are allowed; exactly one public
     presentation contract is allowed; the UX formatter consumes
     `MessageContract` only.
  2. **TurnCoordinator sequencing.** `MessageContract` v1 does not block on
     the (unimplemented) `TurnCoordinator`. `turn_id` is nullable;
     `reply_owner` remains required where currently known; a new
     `turn_context_source` field (`turn_coordinator` | `legacy_ingress` |
     `unavailable`) records provenance. No canonical `turn_id` is ever
     synthesized from `chat_id`, session ID, `contract_id`, or channel
     message ID — when no authoritative turn id exists, `turn_id=None`. A
     future schema version may make `turn_id` mandatory once TurnCoordinator
     is live.
  3. **`MessageState` registry** keeps `approval_pending_batch`, `mixed`, and
     `mixed_with_unknown` as full v1 states — never collapsed into `neutral`
     or `outcome_unknown`.
  4. **Adapter sequence** is three separate PRs, never combined: PR A
     (envelope, registry, validation, schema versioning, observability,
     wrapper around the existing `display_payload` formatter path, no wording
     changes), PR B (`ApprovalLifecycleResult` → `MessageContract` adapter,
     preserving single-speaker/callback-delivery behavior, no `GatewayReply`
     migration yet), PR C (`ActionFact`/`GatewayReply` → `MessageContract`
     adapter, deprecating direct formatter access from that surface). See
     `rollout/MESSAGE_CONTRACT_ENVELOPE_MIGRATION_PLAN.md`.
  5. **`evidence_ref` authority.** Must be supplied by the evidence/execution
     authority; the builder may only copy it — never derive it from
     `contract_id`, hash an internal identifier, store an Airtable record ID,
     embed provider evidence, or invent a local token. `evidence_ref=None`
     when no canonical evidence reference exists.
  6. **Evidence/lifecycle precedence** is fixed by an explicit table (see
     `spec/MESSAGE_CONTRACT_ENVELOPE_CONTRACT_V1.md` §6): pending lifecycle →
     `approval_pending`; rejected lifecycle → `cancelled`/`already_cancelled`;
     verified execution success → `success`; a completed lifecycle without
     verified evidence never automatically becomes `success`;
     `outcome_unknown`/`unverified_effect` are never upgraded to `success`;
     stale or unrelated evidence never overrides the current `ActionContract`
     lifecycle; the formatter never changes state.
- Rationale: PR #471 (D-011) left the repo with two canonical approval-facing
  renderers and no owner ruling on which one wins. Rather than deleting either
  (high-risk, touches live approval UX) or leaving the drift open indefinitely,
  the owner chose the reconciliation path: freeze one new public contract that
  every existing internal result type adapts *into*, so the internal contracts
  keep their current, already-tested responsibilities (single-speaker
  enforcement, callback delivery, structural tool-result shape) while the
  formatter boundary itself stops being ambiguous.
- Affected documents: `spec/MESSAGE_CONTRACT_ENVELOPE_CONTRACT_V1.md` (new),
  `rollout/MESSAGE_CONTRACT_ENVELOPE_MIGRATION_PLAN.md` (new),
  `spec/UNIFIED_MESSAGE_UX_STANDARD.md` (forward-reference erratum), root
  `CLAUDE.md` (planning-conventions pointer).
- Remaining non-blocking open questions: exact interim `reply_owner`
  representation when `turn_context_source="unavailable"`; per-adapter
  `evidence_ref` source for PR B/PR C; `turn_context_source` type
  (str literal vs. `Enum`) — none block PR A. See
  `spec/MESSAGE_CONTRACT_ENVELOPE_CONTRACT_V1.md` §12 for the full list.

## D-013 — Ratify `evidence_status` as optional V1 metadata

- Date: 30/07/2026
- Status: Closed for the V1 metadata contract; no runtime behavior change
- Decision: `MessageContract.evidence_status` is optional metadata copied from
  the canonical evidence classification. It does not determine or upgrade
  `MessageState`, is not a new source of truth, and has no runtime ownership or
  enforcement authority. Unknown or absent values must fail closed or remain
  `None`, according to the existing schema rules.
- Rationale: Stage 3A carries the already-supplied evidence classification for
  audit and round-trip observability. Explicit ratification keeps that metadata
  subordinate to the existing evidence authority and the frozen state
  precedence rules.
- Affected document:
  `spec/MESSAGE_CONTRACT_ENVELOPE_CONTRACT_V1.md` §2.1.

## D-014 — Ratify the text-based "לאשר? כן / לא" confirmation as canonical, cross-channel

- Date: 02/08/2026
- Status: Closed for the wording question below; does not itself authorize
  `FEATURE_UNIFIED_STATUS_FORMATTER=on`
- Trigger: a production `[UnifiedStatusFormatterShadow]` sample for
  `outcome=pending` on a Task-creation contract showed `text_differs=True`
  (`legacy_len=56`, `unified_len=83`). Investigation (see PR #522,
  `baabd46`/`ef55cd9`) found two independent contributors: (1) an
  unintentional content bug — the MessageContract adapter used the generic,
  table-agnostic business description instead of the task's own title for
  Task-creation contracts (fixed in PR #522, no product decision needed) —
  and (2) an intentional structural difference — the unified renderer always
  appends `"\nלאשר? כן / לא"` even when the same message ships with inline
  Telegram approve/reject buttons, which the legacy pending prompt never did.
  (2) was left open as a required product decision; this entry closes it.
- Decision: **Option B — keep the text-based `"לאשר? כן / לא"` confirmation
  as the canonical approval_pending wording**, unconditionally, regardless of
  whether inline buttons are also present on a given channel/message.
  `core/agent_message_formatter.py::_render_approval_pending()` already ships
  this (`f"יש פעולה שממתינה לאישור:\n{desc}\nלאשר? כן / לא"`, from PR1 /
  `spec/UNIFIED_MESSAGE_UX_STANDARD.md`'s canonical pattern) — **no code
  change required** for this decision; it only unblocks the open question
  that was withholding shadow→on sign-off on this specific point.
- Rationale (owner): the assistant must produce one clear answer with one
  clear next action independent of channel. Telegram inline buttons are not
  available on WhatsApp or on any other button-less surface the same
  approval flow may reach; a canonical wording that silently depends on a
  channel affordance would fork the UX per channel. A redundant text prompt
  alongside a working inline button is an acceptable, bounded cost against
  that guarantee.
- Open, NOT resolved by this decision: the owner's example wording for a
  Task-creation contract used **"יש משימה שממתינה לאישור"** (task-specific
  noun), not the renderer's actual, always-generic **"יש פעולה שממתינה
  לאישור"**. Whether `_render_approval_pending()` should gain noun-awareness
  (a Task-creation contract renders "משימה", everything else renders
  "פעולה" — mirroring `build_approval_lifecycle_result()`'s existing
  legacy-side distinction) is a **separate, still-open** product question,
  not decided here. `_render_approval_pending()` is shared foundation for
  every `approval_pending` caller (Layer 3/F52), not scoped to
  `ActionGateway`'s pending surface alone, so resolving it is its own
  Cross-Layer-gated change, tracked separately from this entry.
- **Resolved by D-015 below** — the owner's follow-up decision both adds the
  noun-awareness this entry left open AND further splits the wording by
  *when* it renders (new prompt vs. status query), which this entry did not
  anticipate.
- Affected documents: `spec/UNIFIED_MESSAGE_UX_STANDARD.md` (canonical
  pattern already matches this decision, no edit needed), this log.

## D-015 — Split `approval_pending` wording by context: new prompt vs. status query, with task-noun awareness

- Date: 02/08/2026
- Status: Closed for the wording/formatter-copy question below; does not
  itself authorize `FEATURE_UNIFIED_STATUS_FORMATTER=on`; no approval logic,
  ownership, queue, evidence authority, routing, or `MessageContract`
  wiring/schema changed
- Trigger: follow-up to D-014. The owner's recommended canonical wording used
  the task-specific noun ("יש משימה שממתינה לאישור") that
  `_render_approval_pending()` did not actually render (it always said
  "פעולה"). On closer inspection, the owner further distinguished **two
  contexts** that a single "approval_pending" wording cannot correctly cover:
  a **new approval prompt** (rendered right after the user's request is
  queued — nothing was "already" pending from their point of view) vs. a
  **status query** (the user asking about an action that is already
  pending). D-014's ratified wording ("יש פעולה/משימה שממתינה לאישור...")
  is actually the *status-query* framing; the live call site it was tested
  against (`ActionGateway._render_pending_prompt()`) is a *new-prompt* call
  site, not a status query — so D-014 alone would have shipped the wrong
  framing to the one surface that is actually live today.
- Decision: two distinct canonical wordings, chosen by context, both
  task-noun-aware:
  1. **New approval prompt** (generic): `"כדי לבצע את הפעולה הזו נדרש
     אישור:\n<description>\nלאשר? כן / לא"`; (task-creation): `"כדי ליצור את
     המשימה הזו נדרש אישור:\n<task_title>\nלאשר? כן / לא"`.
  2. **Status query** (generic): `"יש פעולה שממתינה לאישור:\n<description>\n
     לאשר? כן / לא"`; (task-creation): `"יש משימה שממתינה לאישור:\n
     <task_title>\nלאשר? כן / לא"`.
  Task-creation contracts use the task's own title in both contexts, never
  the generic table-agnostic business description (already true since
  PR #522; reconfirmed here for both wordings).
- Implementation (content/copy only, per owner-specified scope):
  - `core/agent_message_formatter.py`: `_render_approval_pending()` (the
    renderer wired to `STATE_APPROVAL_PENDING`/`"approval_pending"` — the
    only state reachable through the `MessageContract` crossing) now renders
    the **new-prompt** wording, since `ActionGateway._render_pending_prompt()`
    is its only live caller. A new function `_render_approval_pending_query()`
    renders the **status-query** wording, registered under a new state
    constant `STATE_APPROVAL_PENDING_QUERY = "approval_pending_query"` —
    deliberately **not** added to `core.message_contract.MessageState` (no
    `MessageContract` schema change), so it is reachable only via a direct
    `format_agent_message_with_meta("approval_pending_query", ...)` call,
    never via the `MessageContract` adapter. No live call site uses it yet;
    it exists as the tested, canonical target wording for if/when
    `describe_pending_queue()`/`query_execution_status()` (which still render
    their own legacy text directly and unconditionally, untouched here) are
    migrated onto the shared formatter.
  - `core/action_fact_message_adapter.py::from_action_fact()` gained an
    `entity_type` parameter (already an existing `DisplayPayload` field —
    no schema change), threaded through from
    `core/action_gateway.py::_compose_status_reply_unified()` as
    `entity_type="task"` for a Task-creation contract (same
    `_is_task_creation_contract()` check `build_approval_lifecycle_result()`
    already uses), so the noun choice is data-driven, not hardcoded per call
    site.
- Explicitly out of scope (per owner instruction, unchanged): approval
  logic, ownership, queue, evidence authority, routing, and the shadow
  observability added in prior PRs. `describe_pending_queue()`/
  `query_execution_status()` are not rewired to the unified formatter — they
  keep rendering their own unconditional legacy text.
- Tests: `test_agent_message_formatter.py` gained direct unit coverage
  distinguishing the two states/wordings (generic and task-noun, including
  the missing-data fallback for each) and a schema-boundary check that
  `"approval_pending_query"` is not a `core.message_contract.MessageState`
  member. `test_f52_status_reply_reconciliation.py` gained an integration
  check that `ActionGateway._compose_status_reply_unified()` (the live
  pending path) renders the new-prompt wording, never the status-query
  wording.
- Affected documents: `spec/UNIFIED_MESSAGE_UX_STANDARD.md` (canonical
  patterns split into "NEW prompt" and "STATUS QUERY" sections), this log.
