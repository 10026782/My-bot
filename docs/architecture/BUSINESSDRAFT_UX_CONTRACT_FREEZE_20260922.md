# Final UX + BusinessDraft Contract Freeze

**Mode:** READ ONLY / DESIGN AUTHORITY. No code, schema, or runtime change was made while producing this document.

**Owner decision freeze (PR #1248, 2026-09-22):** the 5 items originally raised in §30 as open owner decisions were resolved by explicit owner instruction and are applied throughout this document (draft cardinality approved as one-per-entity-kind-per-sender; Deal-first phase ordering approved, superseding this document's original Contact-first recommendation; a canonical Payment update/correction boundary is now required, not optional; Decision/Marketing/BusinessUpdate migration is deferred but not architecturally excluded; `FEATURE_ATOMIC_CLAIMS` production-verification is now an explicit rollout gate from Phase 2 onward). Final Verdict is now `CONTRACT_FROZEN_READY_FOR_IMPLEMENTATION`. See §30 for the full resolution record and §27 for the reordered migration plan.

**Truth Reset SHA:** `origin/main` = `7afe3db6516ab4a1da70121df1a3ab8f6d6c03e1` (2026-09-22, tip at time of writing — merge of `codex/recruitment-worker-model-phase2`).

**Deviation from the literal truth-reset procedure, and why:** this session's local checkout (`0f80122`, 264 commits behind `origin/main`) has extensive **uncommitted working-tree changes from a concurrent session** touching exactly this area (`core/draft_fields.py`, `commercial_crm.py`, `airtable_schema.py`, `tool_registry.py`, `tools/dispatcher.py`, `tools/airtable_security.py`, a new `docs/governance/COMMERCIAL_SCHEMA_V2_ADD_ONLY_STATUS_20260903.md`, `tools/commercial_model_simulation.py`, `tests/`). Per `AGENTS.md`'s SHARED CHECKOUT protocol, this document does **not** run `git switch`/`git pull` on the shared working tree — every file below was read with `git show origin/main:<path>`, never from the dirty working tree. `git status --short` was recorded for the record and is reproduced at the end of this section; none of it was touched.

```
 M BUG_AUDIT_LOG.md
 M CHANGE_CONTROL_LOG.md
 M ROADMAP.md
 M action_validator.py
 M airtable_schema.py
 M commercial_crm.py
 M core/lead_service.py
 M crm.py
 M daily_digest.py
 M docs/CRM_BUSINESS_LANGUAGE.md
 M docs/architecture/f52-unified-approval-runtime/rollout/GATEWAY_CUTOVER_READINESS_20260820.md
 M docs/architecture/turn-coordinator/README.md
 M docs/governance/BOSS_UNIFIED_MASTER_PLAN.md
 M docs/governance/HORIZON.md
 M schema_cache.json
 M tool_registry.py
 M tools/airtable_security.py
 M tools/airtable_tools.py
 M tools/dispatcher.py
 M tools/schemas.py
?? core/draft_fields.py
?? docs/governance/COMMERCIAL_SCHEMA_V2_ADD_ONLY_STATUS_20260903.md
?? test_draft_field_operations.py
?? tests/
?? tools/commercial_model_simulation.py
```

One important correction made mid-research: `core/draft_fields.py` **is already merged to `origin/main`** (confirmed with `git cat-file -e origin/main:core/draft_fields.py`) and is already live inside `core/lead_service.py` (`LEAD_FIELD_METADATA`, `origin/main` lines 1015–1033). The `??` above is an artifact of this local checkout being 264 commits stale, not evidence the file is unmerged. The `docs/audit/SMALL_SHARED_CAPABILITY_EXTRACT_20260904.md` audit (also on `origin/main`) documents its own merge review for exactly this primitive.

**Supporting audits produced alongside this document** (full research transcripts, not summarized further here — this document is the synthesis, those are the evidence):
- [`docs/audit/BUSINESSDRAFT_LEAD_DRAFT_SESSION_MECHANISM_AUDIT_20260922.md`](../audit/BUSINESSDRAFT_LEAD_DRAFT_SESSION_MECHANISM_AUDIT_20260922.md) — `core/lead_service.py`, `core/lead_candidate_handler.py`, `session_store.py`
- [`docs/audit/BUSINESSDRAFT_ACTIONGATEWAY_DISPATCHER_AUDIT_20260922.md`](../audit/BUSINESSDRAFT_ACTIONGATEWAY_DISPATCHER_AUDIT_20260922.md) — `core/action_gateway.py`, `tools/dispatcher.py`, `event_bus.py`, `tools/approval_actions.py`, `tool_registry.py`
- [`docs/audit/BUSINESSDRAFT_COMMERCIAL_CRM_GOLDEN_WRITER_DIAMOND_PATH_AUDIT_20260922.md`](../audit/BUSINESSDRAFT_COMMERCIAL_CRM_GOLDEN_WRITER_DIAMOND_PATH_AUDIT_20260922.md) — `commercial_crm.py`, `crm.py`, `airtable_schema.py` entity fields, DIAMOND PATH mechanics
- [`docs/audit/BUSINESSDRAFT_TMA_TELEGRAM_TASK_LIFECYCLE_AUDIT_20260922.md`](../audit/BUSINESSDRAFT_TMA_TELEGRAM_TASK_LIFECYCLE_AUDIT_20260922.md) — `app.py` Telegram UX, `tma_api.py`, Task write paths, DraftFlow consumers

---

## Approved Architectural Baseline

Decisions A–N from the task brief were checked against current `origin/main` code, not reopened. None are contradicted. Two are sharpened by evidence:

- **K (Sessions for durable draft persistence):** already true in practice, not just permitted. `session_store.py`'s per-sender session dict already carries `lead_draft`, `pending_lead_preview`, `active_lead_candidate`, `last_prompted_contract`, `last_lead_candidate_batch`, `commercial_completion`, `deal_enrichment_offer`, and `lead_deal_link` as sibling top-level keys today. See §4 for the exact shape and its limits.
- **N (Task migration gated on canonical writer/lifecycle authority):** confirmed still unresolved. `ROADMAP.md`'s `TASKS_DEADLINES_ROADMAP_TASKS` row is `IN_PROGRESS`, not closed, and no `task_create`/`task_update` tool-registry entry exists (§16). Task is correctly out of this freeze's implementation order until that closes.

---

## Current Mechanisms

The repo already contains most of what this document would otherwise have to invent. The table below is the actual inventory; narrative follows for the pieces worth explaining.

| Module | Storage | Entity coverage | Lifecycle | Edit | Confirm | Approval | Idempotency | Final writer | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| `core/draft_flow.py` (`DraftSpec`, `resolve_draft_reply`) | caller-owned (session dict or in-memory) | Lead, Decision, Marketing, BusinessUpdate | `filling → (edit_choice ↔ filling) → review → confirm/cancel/abandon` | yes, generic | yes (`CONFIRM_WORDS`) | caller-dependent | none (caller's job) | entity-owned | **KEEP_CORE** — reuse as-is |
| `core/structured_command.py` | n/a (pure parser) | Lead only | n/a | n/a | n/a | n/a | n/a | n/a | **KEEP_ADAPTER**, opt-in shorthand, not core |
| `core/draft_fields.py` (`SET_FIELD`/`CLEAR_FIELD`/`MOVE_FIELD`/`SWAP_FIELDS`, `FieldMetadata`) | n/a (pure, operates on caller's dict) | Lead (operations); Commercial (metadata type only, via `commercial_completion_ux.FieldPresentation = FieldMetadata`) | n/a | **is** the edit contract | n/a | n/a | n/a | n/a | **KEEP_CORE** — this is §7 |
| `commercial_completion.py` (`EntityContract`/`FieldContract`/`CommercialCompletionWriter`/`CompletionSession`/`ContinuationRef`) | pure, no I/O | lead(context only), contact, organization, deal, payment_term, charge, charge_from_term, payment, allocation_rule, allocation_snapshot(system-only), deal_economics | implicit CLARIFY-loop → `complete_payload()` | none built in (no explicit review/back-edit) | implicit at `complete_payload()` | via caller's `queue()` → ActionGateway | nonce-based, nested-only | `commercial_crm.py` primitives | **KEEP_CORE** — closest existing artifact to "BusinessDraft" itself |
| `commercial_completion_routing.py` (`CommercialCompletionRouter`) | none | same 6 top-level-supported entities | orchestrates the above | n/a | queues via injected `queue()` | ActionGateway | inherited from ActionGateway | `MUTATION_TOOLS` map | **KEEP_CORE** — reference channel-neutral API (§25) |
| `commercial_completion_ux.py` | none | same | n/a | n/a | n/a | n/a | n/a | n/a | **KEEP_ADAPTER** — reference renderer (§26) |
| `session_store.py` / `lead_sessions` | Airtable `Sessions` (JSON blob) + RAM LRU | all of the above, one slot per kind | n/a (storage layer) | n/a | n/a | n/a | none beyond create-lock | n/a | **KEEP_CORE** with caveats — see §4 |
| `core/lead_candidate_handler.py` Tier-1 (`_propose_lead_write`) | `last_prompted_contract` in session | Lead | single-item propose→approve | none | via ActionGateway | ActionGateway | fingerprint | `create_lead` | **MIGRATE** (§18) |
| Tier-2 batch (`pending_lead_preview`) | session | Lead batch | confirm-all-or-cancel only, no per-item | none | all-or-nothing | ActionGateway per write | fingerprint per write | `create_lead` | **MIGRATE → BusinessDraftBatch** (§18–19) |
| `last_lead_candidate_batch` | session | Lead batch (post-write only) | n/a — write-after cache, not pending state | n/a | n/a | n/a | n/a | n/a | **MIGRATE**, lowest blast radius (no `app.py` surface at all) |
| `event_bus.py` (`PendingActionsStore`/`EventBus`) | RAM dict, 30 min TTL | followup/abandoned/recovery/media/email/otp/scheduler/tma (legacy callers) | flat pending→confirmed/rejected | none | free-text | none built in | none | caller-specific | **DEPRECATE**, already shrinking (see `tools/approval_actions.py`) |
| `app.py::_pending_approvals` | RAM dict, shorter TTL | general-agent tool-use | flat | none | `_CONFIRM_WORDS` | re-`enforce()`s at dispatch | none | dispatcher | **DEPRECATE**, same track as above |
| `core/action_gateway.py` (`ActionContract`/`ActionGateway`/`ExecutionLedger`) | RAM + optional Postgres (`FEATURE_ACTION_CONTRACT_PERSISTENCE`) | universal | `draft→pending→approved→executing→{completed\|failed\|outcome_unknown\|rejected\|superseded}` | n/a (not a draft) | `approve()`/`reject()` | is the approval authority | fingerprint + optimistic `version` + (staging-only) atomic Postgres claim | is the writer boundary | **KEEP_CORE**, never duplicated |
| TMA (`tma_api.py`) | none client-side | Lead only (status/fields/outcome/task-create) | direct PATCH, no draft/review step | server-gated only | implicit (server decides auto-execute vs queue by role) | ActionGateway, unconditionally | ActionGateway's | Lead writers | **gap**, not a mechanism to retire — see §12 |
| Task (5 independent paths) | n/a | Task | n/a | n/a | ad hoc per path | 4 of 5 via ActionGateway, 1 (turn-coordinator short-circuit) via raw `airtable_add`/`update` labels | none unifying | none canonical | **BLOCKED**, see §16/§18 |

### Why this changes the shape of the task

`commercial_completion.py` + `commercial_completion_routing.py` + `commercial_completion_ux.py` (the "DIAMOND PATH" nested-entity approval-continuation work, built 04–17/09/2026, with a live V2 Payment production canary on 17/09/2026) is not a parallel or competing mechanism to design around — it is, in substance, an unnamed, commercial-scoped first draft of exactly this task's target: a `FieldContract`/`EntityContract` domain model with required/optional/conditional/derived classification, a mutable pre-confirm writer object, an immutable nested-entity frame stack with a typed continuation pointer back into `ActionContract`, and a channel-neutral router returning a structured `CompletionRoute`. Two governance decisions already on record (`canonical_boundaries.json`: `decision.commercial_completion_foundation`, `decision.commercial_completion_routing`) explicitly reserve broadening this into a general production-mutation/routing authority for a **separate owner-classification decision** — this document *is* that decision's design input, not a bypass of it.

---

## Final BusinessDraft Object

The envelope below **wraps** `CommercialCompletionWriter`'s existing shape (`target_entity`, `current_values`, `source_context`, `identity`, `contracts`) rather than replacing it. Classification follows the task's own instruction: nothing is added because it "might be useful."

**IDENTITY**
| Field | Class | Basis |
|---|---|---|
| `draft_id` | REQUIRED (new) | Scoped as `f"{tenant_id}:{channel}:{sender}:{entity_type}"` — deterministic, not a random UUID, because Sessions has no secondary index and every real lookup today already goes through `(tenant, channel, sender)`. See §4 for why arbitrary-cardinality IDs are explicitly **not** frozen. |
| `entity_type` | REQUIRED | = `CommercialCompletionWriter.target_entity`, unchanged. |
| `operation` (CREATE\|UPDATE) | REQUIRED (new) | Neither Lead's draft nor Commercial completion carries this today — both are CREATE-only in their draft UX (Lead's `update_lead_fields()` exists but has no draft around it). Must be added explicitly; see §16. |
| `tenant_id` | REQUIRED | Already present in `source_context`/`identity`; `ActionContract` already freezes it. |
| `actor_user_id`, `actor_role` | REQUIRED | Mirror `ActionContract`'s frozen actor snapshot fields verbatim (`actor_role`, `actor_user_id`, `actor_display_name`, `actor_domain_id`, `actor_external_id`) so confirm-time never re-derives identity. |
| `domain` | OPTIONAL | Already an inherited per-entity field (e.g. Deal/Lead `domain`); not duplicated at envelope level beyond what `source_context` already carries. |

**SOURCE**
| Field | Class | Basis |
|---|---|---|
| `source_channel` | REQUIRED | Matches `ContinuationRef.channel` precedent exactly. |
| `raw_input` | OPTIONAL | Lead's `build_draft_from_text` keeps it; Commercial completion doesn't once fields are captured. Not needed once `fields` is populated. |
| `source_context` | REQUIRED | Already exists verbatim on `CommercialCompletionWriter`. |
| `originating_record_id` | NOT_NEEDED | Already modeled as an ordinary business LINK field per entity (e.g. `origin_lead`) — an envelope-level duplicate would be a second source of truth for the same fact. |

**STATE**
| Field | Class | Basis |
|---|---|---|
| `lifecycle_state` | REQUIRED (new) | See §5. |
| `created_at`/`updated_at` | REQUIRED | Matches existing `set_at`/`updated_at` patterns in `session_store.py`. |
| `expires_at` | REQUIRED | Matches `DRAFT_TTL_SECONDS = 1800` already used by `lead_draft`/`pending_lead_preview`. |
| `idempotency_key` | REQUIRED, narrow scope | This is a **draft-object concurrency counter** (mirrors `ActionContract.version`'s optimistic-concurrency field), *not* a business dedup key — that job stays with `ActionContract.business_action_fingerprint`, computed once at confirm time. Two parallel idempotency concepts is correct here, not redundant: one guards concurrent edits to the still-mutable draft, the other guards duplicate business writes. |

**DATA**
| Field | Class | Basis |
|---|---|---|
| `fields` | REQUIRED | = `current_values`, unchanged. |
| `original_fields` | OPTIONAL, UPDATE-only | Meaningless for CREATE; needed only once `operation=UPDATE` exists (§16). |
| `linked_fields` (separate representation) | NOT_NEEDED | Already modeled inline: `FieldContract.input_type == LINK`, validated as a canonical `rec...` id. A parallel representation would fork validation. |
| `validation_state`, `missing_required_fields` | DERIVED | = `missing_fields()`/`is_complete()`, computed on demand today, never cached — keep it that way. |
| `warnings` | OPTIONAL (new) | No soft-warning tier exists today (binary valid/invalid only). Small, real gap — see §22 — but not required to exist as a first-class list; a `BLOCK`-adjacent reason string already covers most cases. |

**EDIT**
| Field | Class | Basis |
|---|---|---|
| `edit_history`, `last_edit_at`, `last_edit_by` | OPTIONAL (new), deferred | Nothing tracks this today for either Lead or Commercial drafts, and nothing in the evidence shows it's been missed in an incident. Defer past Phase 2; `updated_at`/`actor_user_id` already cover the minimal need. |

**CONTROL**
| Field | Class | Basis |
|---|---|---|
| `adapter_version`, `schema_version` | NOT_NEEDED | `ENTITY_CONTRACTS` is one live dict; schema evolution already has its own mechanism (`core/runtime_schema_provider.py`). Inventing a second, BusinessDraft-local version number duplicates that. |
| `metadata` (free-form bag) | NOT_NEEDED | A junk-drawer field contradicts the task's own "don't add fields solely because they may be useful" instruction; anything genuinely needed later gets a named field via a real decision. |

---

## Final Persistence Contract

**SESSIONS_SAFE_AS_INITIAL_DRAFT_STORE** — with concrete caveats, all evidence-based (`session_store.py`, 1374 lines, `origin/main`):

- Durable across restart: yes, via `_sync_to_db()` → Airtable `Sessions.STATE_JSON`.
- Query/retrieval: **only** by `(tenant_id, channel, sender)` → `_canonical_session_key()`. There is **no lookup by draft_id** — a draft is a nested key inside the one session row for that triple. `draft_id = f"{tenant}:{channel}:{sender}:{entity_type}"` (frozen above) is therefore not an independent index; it's a label for "which nested key inside that one row."
- Concurrency: `self._create_lock` guards only first-creation (double-checked locking). Individual field setters (`set_lead_draft`, `set_pending_lead_preview`, etc.) are **not** lock-protected — a race between two concurrent turns for the same sender+channel can clobber each other's last-write-wins state. No optimistic version field on the session dict itself today.
- Multiple simultaneous drafts per user: **no**, not in the arbitrary-cardinality sense. The existing pattern is "one slot per draft *kind*" (`lead_draft`, `deal_enrichment_offer`, `lead_deal_link`, `commercial_completion` are each a single top-level key) — not "N slots for N drafts of any kind." A second Lead draft for the same sender+channel silently overwrites the first; there is no queue/stack for same-kind drafts.
- Batch references: already proven (`pending_lead_preview`'s `candidates` list).
- Payload size: `STATE_JSON` is one Airtable long-text field holding the *entire* session dict (16+ keys today and growing) — no per-draft size accounting exists. A pathological case (many large drafts accumulating in one session) is not guarded against.
- Versioning: none — every sync is a full overwrite of the whole `STATE_JSON`. No revision counter, no conflict detection between two writers touching different sub-keys concurrently.
- Duplicate-record handling: `_select_canonical_session_record()` picks the most-recently-updated row when a lookup returns more than one Airtable row for the same sender; logged (`SESSION_DUPLICATE_DETECTED`) but never auto-merged.
- Cleanup: LRU eviction from RAM only; the Airtable row is marked (`done=True, deleted=True` inside the JSON), never actually deleted.

**Decision, per the task's own instruction not to invent a new table for cleanliness:** reuse Sessions exactly as scoped above. `draft_id` is a computed label, not a new index; BusinessDraft explicitly **does not** promise arbitrary-cardinality concurrent drafts per user per entity kind — that would require a real schema change (an indexed sub-structure) this document does not authorize.

**Owner Decision #1 — RESOLVED (PR #1248 freeze, 2026-09-22): APPROVED.** One draft per entity-kind per sender is the frozen v1 cardinality. Arbitrary concurrent same-entity drafts (e.g. two Deals in flight for the same user at once) are explicitly deferred, not designed for, in this program.

---

## Final Lifecycle

Evidence-merged from `core/draft_flow.py`'s `filling/edit_choice/review` states and `commercial_completion_routing.py`'s implicit `CLARIFY`-loop-then-queue shape:

| State | Meaning | In ⟶ | ⟶ Out | Mutable? | User-visible? | Retryable? | Expires? | ActionContract may exist? |
|---|---|---|---|---|---|---|---|---|
| `CAPTURED` | First field(s) being asked (`filling`/first `CLARIFY`) | draft creation | `NEEDS_CLARIFICATION`, `READY_FOR_REVIEW` | yes | yes | n/a | yes (TTL) | no |
| `NEEDS_CLARIFICATION` | A field's answer was ambiguous (`CLARIFY` with choices — e.g. multiple Contact matches) | `CAPTURED`, `EDITING` | `CAPTURED`, `READY_FOR_REVIEW` | yes | yes | yes | yes | no |
| `READY_FOR_REVIEW` | All required fields present, nothing blocking (`is_complete()`) | `CAPTURED`, `NEEDS_CLARIFICATION`, `EDITING` | `EDITING`, `CONFIRMED`, `CANCELLED` | yes | yes | n/a | yes | no |
| `EDITING` | User chose to change a field (`edit_choice`) | `READY_FOR_REVIEW` | `READY_FOR_REVIEW` | yes | yes | n/a | yes | no |
| `CONFIRMED` | `complete_payload()` produced the frozen, canonical snapshot | `READY_FOR_REVIEW` | `ACTION_CONTRACT_CREATED`, `FAILED` | **no** | yes | no (one-shot) | no | not yet |
| `ACTION_CONTRACT_CREATED` / `WRITE_PENDING` / `WRITTEN` | Thin **read-through** labels mirroring `ActionContract.status` (`pending`/`approved`+`executing`/`completed`) — never independently tracked | `CONFIRMED` | terminal | no | yes | via ActionGateway's own retry rules | no | yes |
| `CANCELLED` (terminal) | User or system cancel/abandon | any non-terminal | — | no | yes | no | — | no |
| `EXPIRED` (terminal) | TTL lapsed (mirrors existing 1800s precedent) | any non-terminal | — | no | on next access only | no | — | no |
| `FAILED` (terminal) | `ActionContract` reached `failed`/`outcome_unknown`, or `complete_payload()`/queue raised | `CONFIRMED`, `ACTION_CONTRACT_CREATED` | — | no | yes | draft may be recreated fresh, not resumed | — | maybe |

Hard rule honored: `ACTION_CONTRACT_CREATED`/`WRITE_PENDING`/`WRITTEN` are display labels computed from `ActionContract.status` at render time — BusinessDraft does not store a second copy of that state machine, matching `decision.no_new_source_of_truth`.

---

## Final Confirmation Boundary

This mechanism **already exists** and should be reused verbatim, not redesigned:

- **Snapshot structure:** `CommercialCompletionWriter.complete_payload()` — validates `missing_fields()` is empty, then returns `{airtable_field: value}` for every persisted, non-computed, present field. Structural immutability already comes from the frozen dataclass + `dataclasses.replace()` pattern.
- **Canonical payload:** the entity-specific `_primitive_inputs()` translation (one function per entity in `commercial_completion_routing.py`) — already exists for all 6 top-level entities.
- **Snapshot → ActionContract:** `self._queue(tool, inputs)` → `action_gateway.propose_action()`. The exact `inputs` dict is, per the code's own comment, "never changed after this point, preserving Gateway fingerprint parity" — this **is** the fingerprint/hash relationship the task asks to specify.
- **Confirm twice:** already blocked structurally — `propose_action()`'s BUG-122 one-live-mutation-per-user policy refuses a second proposal from `trusted_source="agent"` while one is still pending for that user/tool/fingerprint.
- **Draft changes after a confirm attempt:** for the same reason, a second edit-then-confirm is blocked while the first contract is pending; the user must first cancel/reject the pending contract (mirrors `CompletionSession.abandon_nested()`'s pattern for nested flows) before a new one can be proposed.
- **ActionContract creation fails:** `KeyError`/`ValueError`/`CompletionBlockedError` from `complete_payload()`/`queue()` is caught and replaced with one fixed, business-safe Hebrew message (`BUG-COMPLETION-STALE-BLOCK-LEAK`'s fix) — never the raw exception text. Freeze this pattern as universal, not entity-specific.
- **Can the draft return to `READY_FOR_REVIEW`?** Only before `CONFIRMED`. After `CONFIRMED`, the frozen snapshot is what was fingerprinted; there is no path back without starting a fresh draft.
- **Permanent immutability:** once the mirrored `ActionContract.status` reaches a terminal state (`completed`/`failed`/`outcome_unknown`/`rejected`), the draft transitions to `WRITTEN`/`FAILED`/`CANCELLED` and is cleared from Sessions — matching `lead_draft`'s existing clear-on-terminal behavior.

Hard rule preserved: `ActionContract` payload is never edited after creation — nothing in the existing code paths does this, and nothing here proposes changing that.

---

## Final Edit Contract

`core/draft_fields.py` already defines, and already runs in production for Lead, exactly four of the required operations:

| Operation | Status today | Freeze |
|---|---|---|
| `SET_FIELD` | live (Lead) | canonical, as-is |
| `CLEAR_FIELD` | live (Lead) | canonical, as-is |
| `MOVE_FIELD` | live (Lead), gated by `compatible_field_type` equality, rejects `LINK`-typed fields | canonical, as-is |
| `SWAP_FIELDS` | live (Lead), same gate | canonical, as-is |
| `SET_LINK` / `CLEAR_LINK` | **not implemented anywhere as named operations** | new — must resolve through `commercial_completion_ux.resolve_human_link()`'s bounded resolver seam exactly (never accept a raw record id from free text) |
| `BACK_TO_REVIEW` | behaviorally implemented (`draft_flow.py`'s `edit_choice → review` transition) | freeze the name, no new logic |
| `CANCEL` | live | canonical, as-is |

**One real, scoped gap:** `draft_fields.py`'s four operations currently only work on a **plain mutable dict** (Lead's shape). `CommercialCompletionWriter` is an **immutable dataclass** using `apply_answer()`/`replace()`. These are two different mechanical shapes over the same semantics. Freeze: `CommercialCompletionWriter` gets its **own** thin implementation of the same four operations (using `dataclasses.replace()`, reusing `FieldContract`'s `compatible_field_type`/`manual_entry_allowed`/`clearable`-equivalent rules, not `draft_fields.py`'s dict-mutation function bodies verbatim). This is exactly the next step the 04/09 extraction's own closing note anticipated ("ready for the existing session when its actual module is identified") — that module is now identified.

Type compatibility (text↔text, number↔number, date↔date) is already enforced by `FieldMetadata.compatible_field_type` equality; no new rule needed.

---

## Final Review Card UX

Freeze the conceptual order given in the task template (header → primary fields → business fields → ownership → validation → actions), with one correction: **do not build a second, parallel rendering path.** `deal_field_business_summary()` (`commercial_completion_ux.py`) already builds "one shared per-field label-aware summary... called from BOTH the pending-approval prompt and the completion message" for Deal specifically. Generalize that pattern (reusing `field_presentation()`'s label registry) across all entities rather than inventing a second summary function that could drift from what the `ActionContract` preview itself shows.

Per-entity field display order is not assumed to equal declaration order in code, per the task's own instruction — but in practice, `DealFields`' declared order in `commercial_completion.py`'s `ENTITY_CONTRACTS["deal"]` already roughly matches the desired card order (name → domain → owner → counterparty → business fields → stage/dates → notes → computed rollups), so no reordering work is actually required for Deal. Verify per-entity before assuming this holds elsewhere.

---

## Clickable Field Model

`FieldContract`'s own metadata already almost directly determines UI state — this is nearly a pure rendering function, not new business logic:

| UI state | Basis |
|---|---|
| `NORMAL` | present, valid, `manual_entry_allowed=True` |
| `MISSING_REQUIRED` | `is_required(values)==True` and absent — `missing_fields()` already computes this |
| `INVALID` | present but fails `validate_value()` |
| `WARNING` | new, small — see §22 |
| `READ_ONLY` | `is_computed` or `manual_entry_allowed=False` |
| `LINKED` | `input_type == LINK` |

Empty fields are clickable only if editable (not `READ_ONLY`/computed). TMA: inline edit for scalar SELECT/TEXT/NUMBER/DATE, modal/related-record picker for LINK fields — the picker reuses `resolve_human_link()`'s resolved/clarify/create three-way exactly, rendered as a searchable list instead of a chat reply.

---

## Telegram UX

Freeze the existing pattern, generalized beyond Lead:

- **Review:** compact card + `Confirm`/`Edit`/`Cancel` inline buttons (`_lead_draft_keyboard()` precedent), callback data `"{entity}_draft_approve:{token}"` / `"_edit:"` / `"_cancel:"`, generalizing Lead's exact format.
- **Edit today:** free-text field-name prompt only ("איזה שדה לערוך? שם / טלפון / ..."), no button picker. **Concrete UX simplification recommended in §29:** replace with an inline per-field button list — Telegram already supports this, it directly serves the task's own principle J (discoverable, not command-memory-dependent), and it is a small, scoped change on top of an existing keyboard-building function, not new architecture.
- **Linked fields:** reuse `resolve_human_link()`'s resolved/clarify(with choices+tokens)/create three-way exactly as DIAMOND PATH already does today — this is production-hardened (multiple named bugs fixed: `BUG-5-CALLBACK-TOKEN`, `BUG-DIAMOND-CONTACT-APPROVAL-AND-SEARCH`), not something to redesign.
- **Missing fields → direct clarification:** already the `CLARIFY` route's job; no change needed.
- **Re-enforcement:** `_handle_approval_callback_impl()` re-resolves the *original requester's* identity and calls `enforce(tool_name, identity)` fresh before dispatch (`app.py:4313`) — confirms CLAUDE.md's description exactly; BusinessDraft's confirm path must keep routing through this, never trust a stored decision.

---

## TMA UX

**No draft/review component exists on the TMA side today for any entity** — confirmed by `git ls-tree` on `tma-frontend/src`: only `Approvals.tsx`, `LeadCard.tsx`, `LeadDetail.tsx`, `LeadPipeline.tsx` exist. `LeadDetail.tsx` fires `patchLead()` directly on save with no preview. This is the single largest gap in the current UX (see §29) — it is real greenfield work, not a mechanism to migrate.

Freeze:
- Clickable field rows per §10's state model, grouped per §9's card IA.
- Inline edit for scalar SELECT/TEXT/NUMBER/DATE fields (small footprint — matches the existing direct-PATCH-on-save interaction, just insert a review step before the PATCH fires instead of firing immediately).
- Modal/picker for LINK fields, built directly on `resolve_human_link()`'s three-way result (more screen real estate needed for a candidate list than a chat reply allows).
- Save-per-field-operation (each edit immediately calls the channel-neutral `set_field`/`set_link`), not a separate client-local "unsaved draft" buffer — the BusinessDraft object itself, Sessions-backed, already *is* the persisted pre-confirm state. Adding a third state layer (browser-local + BusinessDraft + ActionContract) would be new complexity with no evidenced need.
- Confirm/cancel footer + current lifecycle-state badge (§5) + post-confirm approval state, reusing `_fmt_approval()`'s existing shape rather than inventing a parallel one.

---

## Text-Only Channel UX

Freeze: numbered field list + `edit <field>` + confirm/cancel, using **exactly** `draft_flow.py`'s existing `CONFIRM_WORDS`/`CANCEL_WORDS`/`EDIT_WORDS` vocabulary — this is already channel-neutral and already serves WhatsApp for Lead today. No separate lifecycle; the WhatsApp renderer consumes the same `CompletionRoute`/lifecycle state as Telegram, formatted as plain numbered text. The channel adapter invents no state of its own, per the task's hard rule.

---

## Entity Adapter Contract

Freeze mapped directly onto `EntityContract`/`FieldContract`'s existing shape — most of these already exist under a different name:

| Required method | Existing basis |
|---|---|
| `get_entity_type()` | `EntityContract.entity` |
| `get_field_definitions()` | `EntityContract.fields` |
| `get_required_fields()` | `FieldContract.is_required(values)` — dynamic/conditional-aware, better than a static tuple |
| `get_editable_fields()` | fields where `manual_entry_allowed` |
| `validate_field()` | `validate_value()` |
| `validate_draft()` | `missing_fields()` + `_assert_supported()` |
| `normalize_field()` | `_coerce_value()` |
| `format_field()` | `field_presentation()` + `render_prompt()` |
| `get_preview_order()` | new, but cheap — declaration order already suffices for Deal (§9); confirm per entity, don't assume a reorder is needed by default |
| `get_link_rules()` | `one_of_required` + `input_type == LINK` fields + the entity-resolver map already in `commercial_completion_routing.answer_human()` |
| `build_create_payload()` | `complete_payload()` + `_primitive_inputs()` |
| `build_update_payload()` | **new** — does not exist for any commercial entity today (§16) |
| `get_canonical_create_tool()` | `MUTATION_TOOLS[entity]` |
| `get_canonical_update_tool()` | **new/missing** for every entity except Contact |

Separation already holds: `commercial_completion.py` owns semantics (no rendering), `commercial_completion_ux.py` owns presentation (no semantics, no I/O, no persistence) — freeze this split as the permanent rule, per the task's own instruction.

---

## Entity UX Matrix

Field sets below are the live `ENTITY_CONTRACTS`/`airtable_schema.py` definitions — nothing added beyond the approved schema.

**Deal** — required: `name`, `domain`, `owner`, one-of(`counterparty_contact`, `counterparty_organization`). Optional (post-creation enrichment, never blocks create): `business_deal_type`, `relationship_role`, `engagement_duration`, `currency`, `commercial_status`, `estimated_value_basis`/`range`/`notes`, `start_date`, `notes`. Read-only/computed: `total_charged`, `total_collected`, `outstanding`. Linked: `origin_lead`, `counterparty_contact`, `counterparty_organization`. Create: `crm_create_deal`. Update: **missing** (§16).

**Payment Term** — required: `deal`, `direction`, `calculation_type`, plus conditional fields keyed off `calculation_type`/`cadence`/`trigger_type`/`due_rule` (fixed_amount, rate_pct, calculation_basis, tier_configuration, custom_calculation_rule, unit_rate, installment_count, trigger_date/delay/event, specific_due_date, schedule_anchor_date, net_days), required `currency`. Optional: minimum/maximum amount, grace_period_days, vat_rule, start/end date, notes. Computed: `next_due_date`. Create: `crm_create_payment_term`. Update: **missing**.

**Payment** — required: `charge`, `amount`, `paid_at`, `direction`, `currency`, `deal` (made `ALWAYS` after `BUG-COMPLETION-PAYMENT-DEAL-CRASH`, 17/09/2026). Optional: `payment_term`, `counterparty_contact`/`organization`, `reference`, `method`, document requirement/status, notes. Create: `crm_create_charge_payment` (V2, preferred) or legacy `create_payment` (quarantined). Update: **missing — required** (Owner Decision #3, RESOLVED: a canonical update/correction boundary is required; see §16/§17). Do not ship Payment CREATE-only.

**Contact** — required: `name`, `phone`. Optional: `email`, `company`, `role_category`. Create: `find_or_create_contact`. Update: `crm.update_contact` — **the one fully symmetric entity today.**

**Lead** — required: `name`, `phone`, `domain` (inherited). Optional: `owner`, `source`, `channel`. Create: `create_lead`. Update: `update_lead_fields` — symmetric at the writer level, but has **no draft/review UX around it at all** (used only by post-write enrichment, e.g. `lead_memory`).

**Task** — no `EntityContract` exists in `commercial_completion.py` today at all. `airtable_schema.TaskFields`: `NAME`(="כותרת המשימה"), `DESCRIPTION`, `DUE_DATE`, `STATUS`, `CONTACTS_LINK`, `DEALS_LINK`, `DOMAIN`, `OWNER` (link to Profile), `LEAD_LINK`. This is the basis for a future `EntityContract("task", ...)`, gated on §16/§18's Task-writer prerequisite — not built as part of this freeze.

---

## Create/Update Authority Matrix

| Entity | Create | Update | Note |
|---|---|---|---|
| Deal | SUPPORTED | **MISSING** | generic `airtable_update` is the only path today — explicitly not acceptable as final authority per the task's hard rule |
| Payment Term | SUPPORTED | **MISSING** | same |
| Charge | SUPPORTED | **MISSING** | `docs/evidence/COMMERCIAL_S2B_MUTATION_PRIMITIVES_20260903.md` states explicitly: "generic updates to Charges... fail closed because no update primitive was approved" — already fail-closed by design, good starting posture |
| Organization | SUPPORTED (find-or-create absorbs the common reuse case) | **MISSING** (no rename/field update) | one-field schema today; low urgency |
| Payment | SUPPORTED | **MISSING — REQUIRED** (Owner Decision #3, RESOLVED: APPROVED) | a canonical Payment update/correction boundary is required; Payment CREATE must not remain canonical while UPDATE/correction stays generic |
| Contact | SUPPORTED | SUPPORTED | fully symmetric |
| Lead | SUPPORTED | SUPPORTED | symmetric at writer level, no draft UX on update |
| Task | SUPPORTED (5 redundant paths) | SUPPORTED (redundant paths) | **NOT_CANONICAL** — no single writer owns either; blocks BusinessDraft participation per the task's own hard rule and governing decision N |

**Exact update writers still required before adapter implementation:** `update_deal()`, `update_payment_term()`, and a canonical update/correction boundary for Payment (Owner Decision #3, RESOLVED — required, not deferrable). `update_organization()` is optional/deferrable. Contact and Lead need nothing further. Task needs one canonical `create_task()`/`update_task()` pair, replacing the 5 fragmented paths — but that decision belongs to the still-open `TASKS_DEADLINES_ROADMAP_TASKS` track, not to this document.

---

## Commercial CRM First Contract

| Entity | Adapter | Confirmed snapshot | Canonical tool | Canonical writer | Evidence |
|---|---|---|---|---|---|
| Deal | `EntityContract["deal"]` | `complete_payload()` → `_primitive_inputs("deal", ...)` | `crm_create_deal` | `commercial_crm.create_deal()` | `UNIFIED_APPROVAL_ACTIONGATEWAY` canary, 02/09/2026 (`crm_create_deal` contract `09e1fd02...`, execution `01cc8515...`) |
| Payment Term | `EntityContract["payment_term"]` | same pattern | `crm_create_payment_term` | `commercial_crm.create_payment_term()` | same canary program |
| Payment | `EntityContract["payment"]` / `["charge_from_term"]` | same | `crm_create_charge_payment` / `crm_create_charge_from_term` | `commercial_crm.create_charge_payment()` / `create_charge_from_term()` | live production canary, 17/09/2026 (5 bugs found and fixed same day) |
| Contact | `EntityContract["contact"]` | same | `crm_find_or_create_contact` | `commercial_crm.find_or_create_contact()` → `crm.create_contact_from_fields()` | DIAMOND PATH nested-create canary (production transcripts in `test_diamond_path_approval_continuation.py`, `test_bug_diamond_contact_approval_and_search.py`) |

**Update writer gaps to close first:** `update_deal()`, `update_payment_term()`, and a canonical Payment update/correction boundary (Owner Decision #3, RESOLVED — required) — all three block `UPDATE_SUPPORTED` classification and must land before their adapters can honestly claim update capability. No Lead migration precedes this path's proof, matching governing decision M — and the proof (Deal/Payment canaries above) already exists, ahead of this document.

---

## Lead Migration Contract

Converge onto `BusinessDraft[Lead]` only after the Commercial CRM core is proven (already true — see above). Retirement targets, with exact blast radius from direct code inspection:

- `lead_draft`: production callers besides `lead_service.py`/`lead_candidate_handler.py`/`session_store.py` are entirely inside `app.py` — `_handle_lead_draft_callback()` (:3014-3105), `_lead_draft_keyboard()` (:3091), the early confirm/cancel-word dispatch block (~:5424-6220), plus 7 named test files.
- `pending_lead_preview`: `app.py` (~:2658-2722, 6005-6211) + 7 named test files.
- `last_lead_candidate_batch`: **zero** `app.py` surface — lowest-blast-radius retirement of the three.

Explicit plan: retire only after behavior parity + runtime evidence, per the task's own instruction — do not delete on a schedule.

---

## Task Migration Contract

**Blocked**, correctly, pending `TASKS_DEADLINES_ROADMAP_TASKS`'s own closure (owned outside this document). Current state for the record: 5 independent write paths (generic `airtable_add`/`update` with a field allowlist; `core/turn_coordinator_runtime.py`'s NL short-circuit, which maps to the same generic primitives under a label that never reaches `tool_registry.py`; TMA's create-only `/api/leads/<id>/task`; TMA's update-only `/api/tasks/<id>`; `abandoned_lead_worker.py`'s scheduler-created task) — none symmetric, none canonical, and Task is absent from `tools/dispatcher.py`'s `_TENANT_AWARE` set entirely (writes never get `tenant_id` injected). This document freezes the *target* shape (§15's Task row) but does not authorize starting Task's BusinessDraft adapter before that prerequisite closes, per governing decision N.

---

## Batch Contract

`BusinessDraftBatch` per the task's template. Current state to build from: Tier-2 preview already has confirm-all + cancel but explicitly **no** partial selection ("אין תמיכה ב-selection חלקי", code comment) — real gap. Tier-3 "high"-confidence items already get individual per-item `ActionContract`s as a side effect of mixed-confidence handling, which is close to but not the same as a deliberate per-item batch API.

- `EDIT_ITEM`/`REMOVE_ITEM`/`CONFIRM_ITEM`: new capability, modeled directly on the single-item edit/confirm contract (§7/§6) applied per batch entry.
- `CONFIRM_ALL_VALID`: mostly exists (Tier-2's confirm-all) — **freeze it to skip individually-invalid items and report per-item outcome**, replacing today's literal all-or-nothing behavior. This is a concrete, scoped fix, not new architecture.
- Duplicate prevention / per-item evidence: inherit directly from `ActionGateway`'s existing per-write fingerprinting — no new mechanism.
- Batch summary UX: reuse §9's review-card pattern per item, rolled up into a count summary (N ready / N needs review / N invalid), addressing §29's batch-usability finding.

---

## Linked Record Contract

Freeze `resolve_human_link()` exactly as it exists — resolved / clarify(choices + tokens) / create, generalized beyond Deal/Contact/Organization to any `LINK` field on any entity. This is production-hardened (named bugs already fixed on this exact path). Hard rule already enforced in code and carried forward unchanged: `canonical_value`/`candidate_ids` are internal-only, never rendered — only display labels reach the user.

---

## Validation Contract

The four layers the task asks to keep separate are **already architecturally distinct** in current code — freeze, don't collapse:

1. **Capture confidence** — Router/`intent_router`'s Tier classification (upstream of any completion flow entirely).
2. **Field validity** — `validate_value()`/`FieldContract`.
3. **Draft validity** — `missing_fields()`/`is_complete()`.
4. **Authority/approval** — `tool_registry.enforce()` + `ActionGateway`'s `approval_policy`.

No code path today collapses these into one score; this document requires that property be preserved, not introduced.

---

## Error UX Contract

| Category | Message style | Retryable | Return-to-edit | Draft intact? |
|---|---|---|---|---|
| `FIELD_INVALID` | fixed, business-safe, per-field (`_validation_failure_message()` pattern) | yes | yes (same field) | yes |
| `MISSING_REQUIRED` | the field's own `render_prompt()` | yes | n/a (still filling) | yes |
| `LINK_NOT_FOUND` | `resolve_human_link()`'s "create?" or "try another name" text | yes | yes | yes |
| `PERMISSION_DENIED` | `"⛔ הפעולה כבר אינה מורשית"` pattern (existing, `_handle_approval_callback_impl`) | no | no | draft cleared (or left for the requester, entity-dependent) |
| `DRAFT_EXPIRED` | **new, small gap** — no dedicated message exists today; freeze it to follow the same business-safe-text discipline | no | no (start fresh) | no |
| `DRAFT_CONFLICT` | **new, small gap**, same discipline | depends | possibly | depends |
| `CONFIRMATION_FAILED` | `BUG-COMPLETION-STALE-BLOCK-LEAK`'s fixed generic message — never raw exception text | yes | yes | yes, draft survives |
| `ACTION_PROPOSAL_FAILED` | same discipline | yes | yes | yes |
| `WRITE_FAILED` | ActionGateway's own `failed`/`outcome_unknown` handling | per ActionGateway policy | no (fresh draft) | no |
| `OUTCOME_UNKNOWN` | ActionGateway's existing terminal state, surfaced honestly, never silently retried | no auto-retry | no | no |

No raw enum/internal exception leakage anywhere in this table — this is already the enforced pattern for the two categories that exist today (`FIELD_INVALID`, `CONFIRMATION_FAILED`); extend it uniformly.

---

## Idempotency / Concurrency Contract

- **Draft-level:** `session_store.py`'s create-lock only — no per-field-mutation lock exists. Acceptable at today's evidenced traffic; flagged as a real (not hypothetical) gap for concurrent TMA + Telegram editing of the same draft.
- **Confirm-level:** `propose_action()`'s fingerprint dedup + BUG-122's one-live-mutation-per-user policy — reuse verbatim, do not reinvent.
- **Double-click confirm / Telegram duplicate callback:** `approve()`'s striped per-`contract_id` lock already makes two concurrent `approve()` calls for the same contract serialize correctly.
- **TMA double submit:** `_queue_or_owner_execute()`'s fail-closed-to-503-unless-both-flags-live posture already prevents a silent double-write; no RAM-only fallback exists.
- **Batch double confirm:** new — apply the same one-live-mutation policy per batch-id (or per item, per §19's design).
- **Writer-level dedup:** `commercial_crm.py`'s own deterministic `Reference`-formula matching (e.g. `create_charge_from_term`) — reuse, don't duplicate.
- **Deepest layer — important operational note:** `core/action_gateway_atomic_executor.py`'s PostgreSQL atomic-claim mechanism, the strongest concurrency guarantee in the stack, has its own file-header statement: **"Staging only... flag is OFF in production."** BusinessDraft's confirm-time concurrency guarantee is therefore currently *weaker in production than in staging*, independent of anything this document proposes.

**Owner Decision #5 — RESOLVED (PR #1248 freeze, 2026-09-22).** Phase 0/1 static implementation (closing update-writer gaps, extracting/wrapping the core modules) may proceed independently of `FEATURE_ATOMIC_CLAIMS`'s production state — neither depends on the strongest concurrency guarantee being live. But **production BusinessDraft write canary / rollout (Phase 2 onward, any real confirm-time writes) is gated on `FEATURE_ATOMIC_CLAIMS` being enabled and runtime-verified in production**, not merely staging-verified. This gate must be checked before any Phase 2+ production canary, not assumed satisfied.

`ActionGateway`'s atomic-claim behavior is preserved unmodified; BusinessDraft introduces no competing execution-ownership mechanism, per the task's hard rule.

---

## Permission Contract

- **Creator/tenant scope:** already structural, not policy — a draft lives inside the tenant-scoped `(tenant, channel, sender)` session row; there is no globally-addressable draft store to leak across tenants from.
- **Role restrictions:** enforced by `tool_registry.enforce()` at **confirm** time, not at draft-edit time. Editing a still-mutable, unconfirmed draft has no side effect, so this asymmetry is intentional and matches the governing philosophy (`BusinessDraft is mutable before confirmation`) — not a gap.
- **Guessing another user's draft ID:** structurally prevented today by construction (no addressable draft ID exists pre-BusinessDraft at all) and remains prevented post-BusinessDraft, because `draft_id = tenant:channel:sender:entity_type` is only reachable by someone who already has channel-level access to that identity — the same trust boundary the rest of the pipeline already relies on (Identity → Router → Context → Agent's own "no action without identity" rule).
- **Admin/owner override:** none observed in current code for drafts specifically (Owner already auto-executes via `_queue_or_owner_execute`'s existing role branch — that's an execution-time behavior, not a draft-access override).

---

## Channel-Neutral API

Freeze method list mapped onto what already exists, generalized:

| Method | Existing basis |
|---|---|
| `create_draft`, `get_draft`, `list_user_drafts` | new thin wrapper over Sessions' existing per-kind slot pattern (§4) |
| `set_field`, `clear_field`, `move_field`, `swap_fields` | `core/draft_fields.py`, live |
| `set_link`, `clear_link` | new, built on `resolve_human_link()` |
| `validate` | `missing_fields()`/`is_complete()` |
| `confirm` | `complete_payload()` → `queue()` → `propose_action()` |
| `cancel`, `expire` | `draft_flow.py`'s existing cancel/TTL handling |

Structured result type: generalize `CompletionRoute`'s existing shape (`outcome`, `entity`, `session`, `field_name`, `field_type`, `tool_name`, `tool_inputs`, `reason`, `user_label`, `prompt`, `choices`, `choice_tokens`) — already proven channel-neutral (both Telegram and WhatsApp already consume the same shape today for Commercial completion). No user-facing strings originate from the core — already true (`commercial_completion.py` raises typed exceptions only; all Hebrew text lives in `commercial_completion_ux.py`) — freeze this separation as permanent.

---

## Renderer Contract

`TelegramReviewView`/`TMAReviewView`/`WhatsAppReviewView` each consume the same `CompletionRoute` + `field_presentation()` output. Today: Telegram- and WhatsApp-shaped renderers exist (same underlying text, different framing); **TMA renderer does not exist and must be built** (§12). Renderers format labels/buttons only — confirmed true of `commercial_completion_ux.py` today (no state mutation, no validation bypass, no writer calls, no entity-specific authority) — freeze this boundary unchanged.

---

## Migration Plan

**Owner Decision #2 — RESOLVED (PR #1248 freeze, 2026-09-22): APPROVED, Deal first.** This document's earlier Contact-first recommendation (cheapest-pilot reasoning) is superseded by explicit owner instruction. Commercial CRM / Golden Writer remains the implementation anchor; Contact is **not** reordered ahead of Deal. The frozen first implementation sequence is:

- **PHASE 0** — Close canonical commercial UPDATE authority gaps: `update_deal()`, `update_payment_term()`, and a canonical Payment update/correction boundary (Owner Decision #3, RESOLVED — required, see §16/§17). All three must land before their adapters can honestly claim update capability.
- **PHASE 1** — Generalize/wrap the existing proven primitives: `commercial_completion.py`, `commercial_completion_routing.py`, `commercial_completion_ux.py`, `core/draft_flow.py`, `core/draft_fields.py` — a new thin envelope module (e.g. `core/business_draft.py`) composes these rather than replacing any of them, preserving their existing production canaries.
- **PHASE 2** — Sessions-backed BusinessDraft persistence, v1 cardinality: one draft per entity-kind per sender (Owner Decision #1, RESOLVED — see §4). Arbitrary concurrent same-entity drafts remain deferred, not built.
- **PHASE 3** — Deal adapter + review/edit UX: add the missing `READY_FOR_REVIEW` step (§8/§29's largest single UX gap), generalize `deal_field_business_summary()` into the shared review card, consume the `update_deal()` writer closed in Phase 0.
- **PHASE 4** — PaymentTerm + Payment adapters, consuming the `update_payment_term()` and Payment update/correction writers closed in Phase 0.
- **PHASE 5** — Contact adapter. Full CREATE+UPDATE symmetry already exists at the writer level; this phase is adapter/UX wrapping only, now sequenced after Deal/Payment per Owner Decision #2 rather than as the first pilot.
- **PHASE 6** — Lead migration (§18), only after Phases 3–5 prove the core, per governing decision M.
- **PHASE 7** — Task canonical writer + adapter, after canonical Task authority closes — **hard external dependency** on `TASKS_DEADLINES_ROADMAP_TASKS` closing; not schedulable by this program alone.

Continuing beyond the frozen first sequence (unchanged in substance from the prior draft, renumbered):

- **PHASE 8** — TMA draft/review UI build-out. Corrected framing: this is **not** a "generic write retirement" (TMA already routes every write through `ActionGateway` correctly) — it is building the missing review screen in front of an already-correct write path.
- **PHASE 9** — Batch unification (§19), after Lead migration (Phase 6) since Lead is the only entity with real batch precedent today.
- **PHASE 10** — Remove legacy pending stores (`event_bus.PendingActionsStore`'s remaining callers, `app.py::_pending_approvals`, `lead_draft`/`pending_lead_preview`/`last_lead_candidate_batch`) only after runtime proof, using the exact blast-radius lists in §18.

**Production rollout gate (Owner Decision #5, RESOLVED, §23):** Phase 0/1 static implementation may proceed independently of `FEATURE_ATOMIC_CLAIMS`. Any production BusinessDraft write canary from Phase 2 onward is gated on `FEATURE_ATOMIC_CLAIMS` being enabled and runtime-verified in production, not merely staging-verified.

---

## Retirement Matrix

| Mechanism | Verdict | Note |
|---|---|---|
| `core/draft_flow.py` | KEEP_CORE | generalizes into BusinessDraft's lifecycle engine |
| lead draft state (`lead_draft`) | MIGRATE | Phase 6 |
| Tier-1 preview (`last_prompted_contract`) | MIGRATE | folds into single-item confirm path |
| Tier-2/3 pending (`pending_lead_preview`) | MIGRATE → BusinessDraftBatch | Phase 9 |
| `event_bus.PendingActionsStore` | DEPRECATE | already shrinking — media/followup/recovery/`tma_write` already migrated to real dispatcher tools per `tools/approval_actions.py`'s own stated purpose |
| `app.py::_pending_approvals` | DEPRECATE | same track |
| TMA `tma_write` / `_queue_tma_write_approval` | KEEP_CORE | already correctly ActionGateway-native; only the missing review UI needs building, not this path |
| TMA Approvals projection (`/api/approvals`) | KEEP_ADAPTER | stays the post-proposal approval list; BusinessDraft adds a separate *pre-confirm* review screen, does not replace this |
| commercial legacy update paths | N/A | none exist yet to retire — when Phase 0 creates them, they start as `KEEP_CORE` |
| Voice fallback (`voice_adapter.py::_save_voice_lead`) | HISTORICAL_ONLY / out of scope | never asked the user anything — not a draft/review mechanism; already tracked separately under N18/TR-22 |
| `cmd_update.py`/`cmd_decision.py`/`cmd_marketing.py` `_pending` state | **DEFERRED_FROM_INITIAL_MIGRATION** (Owner Decision #4, RESOLVED) | already `draft_flow.py`-based and structurally compatible; Decision/Marketing/BusinessUpdate are separately-owned entities per `WRITER_AUTHORITY_REGISTRY.md` and are not scheduled in this program's phases — but they are **not architecturally excluded**. BusinessDraft core (§27 Phases 1–2) must remain compatible with a later migration of these domains; nothing in this freeze may close that door. |

---

## UX Simplifications

Ranked by evidenced impact, not speculation:

1. **Add a review step to Commercial completion flows.** Today: zero consolidated review before queuing — strictly sequential Q&A. This is the single largest gap against the task's own UX principles A and F. (Phase 4 in §27.)
2. **Replace Telegram's free-text "which field?" edit prompt with inline buttons.** Removes command-memory burden; Telegram already supports this, no new architecture required.
3. **Batch: per-item confirm/remove**, replacing today's literal all-or-nothing confirm. Directly serves batch usability (§19).
4. **Build the missing TMA review card.** Today a Manager clicks "save" on `LeadDetail.tsx` with zero preview of what gets proposed — the single largest Telegram/TMA inconsistency found. (§12/§26.)
5. **Extend the business-safe-error-text discipline to `DRAFT_EXPIRED`/`DRAFT_CONFLICT`** specifically — small, concrete, already-proven pattern (§22).
6. **Reuse `BUG-5-CALLBACK-TOKEN`'s token-based candidate selection in the TMA picker too**, avoiding a second free-text round-trip there.

---

## Remaining Owner Decisions

All 5 items below were resolved by explicit owner instruction on 2026-09-22 (PR #1248 freeze). Original questions are preserved for record; resolutions are authoritative and supersede this document's earlier recommendations where they differed.

1. **Draft cardinality — RESOLVED: APPROVED.** "One draft per entity-kind per sender" (§4) is the frozen v1 limit. Arbitrary-cardinality concurrent drafts (e.g. two Deals in flight for the same user at once) are explicitly deferred, not built in this program.
2. **Phase ordering — RESOLVED: APPROVED, Deal first.** This document's original Contact-first recommendation (cheapest-pilot reasoning, §27) is superseded. Commercial CRM / Golden Writer remains the implementation anchor; Contact is not reordered ahead of Deal. See the revised §27 sequence.
3. **Payment UPDATE writer — RESOLVED: APPROVED, required.** A canonical Payment update/correction boundary must be built. Payment CREATE must not remain canonical while UPDATE/correction stays generic — this closes what was previously an open bookkeeping-policy question. See §16/§17/§27 Phase 0.
4. **Decision/Marketing/BusinessUpdate scope — RESOLVED: DEFERRED FROM INITIAL MIGRATION, NOT ARCHITECTURALLY EXCLUDED.** These remain out of this program's scheduled phases, but BusinessDraft core (§27 Phases 1–2) must remain compatible with a later migration of these domains — nothing in Phase 1's envelope design may close that door. See §28.
5. **`FEATURE_ATOMIC_CLAIMS` production gate — RESOLVED.** Phase 0/1 static implementation may proceed independently of the flag's production state. Production BusinessDraft write canary / rollout (Phase 2 onward) is gated on `FEATURE_ATOMIC_CLAIMS` being enabled and runtime-verified in production, not staging-verified. See §23.

---

## Final Verdict

**CONTRACT_FROZEN_READY_FOR_IMPLEMENTATION**

All 5 owner decisions above are resolved as of 2026-09-22 (PR #1248). Phase 0 (closing `update_deal()`/`update_payment_term()`/Payment update-boundary gaps) and Phase 1 (extracting/wrapping the already-proven core modules) may begin immediately. Phase 2's draft-cardinality scope and Phase 3's Deal-first ordering are no longer open questions — both are frozen per Owner Decisions #1 and #2. Any production write canary from Phase 2 onward remains gated on `FEATURE_ATOMIC_CLAIMS` being enabled and runtime-verified in production (Owner Decision #5).
