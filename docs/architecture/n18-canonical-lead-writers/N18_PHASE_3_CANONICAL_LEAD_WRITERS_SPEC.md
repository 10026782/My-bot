# N18 Phase 3 — Canonical Lead Writers Spec

**Status:** Documentation gate output, 30/08/2026. **Documentation only — no
runtime code, Airtable schema, feature flag, or deployment config was changed
to produce this document.**

**Canonical Source relationship:** `IMPLEMENTATION_OF: N18` (Canonical Write
Infrastructure, `ROADMAP.md` / `BOSS_UNIFIED_MASTER_PLAN.md` §3.5). This
document is the detailed writer-by-writer spec that row summarizes; it does
not replace or compete with it.

## 0. Truth-reset correction (read this before the rest of the document)

This spec was requested against an assumed state — Phase 3 Slice 1 still
open, five writers still legacy/direct, Owner Resolution for non-interactive
sources an unsolved architectural prerequisite. A read-only Truth Reset
against `origin/main` (git ancestry of the cited commits, plus actually
running the cited test files — not just reading doc claims) found that
assumption **stale**. The corrected state:

| Claim in the original request | Verified state on `origin/main` |
|---|---|
| Phase 3 Slice 1 (Telegram Preview) — code complete, runtime not established | **CLOSED** — PR #1043 (`3de2dcf`), 27/08/2026. `test_n18_slice1_lead_preview.py` 6/6. |
| (not mentioned) | **Phase 4 (Telegram approve/cancel buttons) — also CLOSED** — PR #1065 (`2484f3c`), 28/08/2026. `test_n18_phase4_telegram_buttons.py` 4/4, `test_n18_draft_dispatch_unification.py` 8/8. |
| WhatsApp inbound — remaining legacy/direct writer | **Already canonical.** `lead_capture.py:247` calls `create_lead()` directly; the flag-gated `core/whatsapp_lead_cutover.py` path (`WHATSAPP_CANONICAL_LEAD_WRITE`) is a *second*, newer canonical route, not a legacy fallback. |
| Email inbound — remaining legacy/direct writer | **Already canonical.** `inbound_handler.py:84` calls `create_lead()` directly (F06 gate, used by `email_inbound.py`); `core/noninteractive_lead_cutovers.create_email_inbound_lead()` also exists as an alternate canonical entry. |
| Furniture funnel — remaining legacy/direct writer | **Already canonical.** `furniture_lead_funnel.py` calls `core/noninteractive_lead_cutovers.create_furniture_inbound_lead()`, which calls `create_lead()`. |
| Voice IVR — remaining legacy/direct writer | **Partially true — the one real gap.** `voice_adapter.py`'s canonical path (`create_voice_inbound_lead()`) exists, but a live `airtable_add()` fallback still executes whenever `VOICE_CANONICAL_LEAD_WRITE` is off (its current default). |
| LeadMemory fallback — remaining legacy/direct **creation** writer | **Miscategorized.** `lead_memory.py`'s own docstring: "לעולם אינו יוצר Lead" (never creates a Lead). It only updates an existing record via `core.lead_service.update_lead_fields()` — a sibling canonical function, not a creation bypass. |
| Owner Resolution for non-interactive sources — unsolved prerequisite, `PLANNED` | **Already implemented.** `core/source_owner_mapping.py`'s `resolve_owner_user_id()` / `resolve_furniture_owner_user_id()` is consumed by all three `core/noninteractive_lead_cutovers.py` wrappers (email/furniture/voice) before they call `create_lead()`. |

This correction is itself the primary content of the "architectural blocker"
section the request asked for: **there is no blocker.** The one concrete,
verified remaining gap is narrower — see §9.

## 1. Problem Statement

BOSS has multiple inbound channels that can create a Lead (Telegram, WhatsApp,
Email, Furniture funnel, Voice IVR) plus internal flows (structured command,
batch import, Lead Draft confirmation, post-write enrichment). Before N18,
each channel wrote to the `Leads` table through its own path, with its own
dedup, validation, and Owner-assignment logic duplicated per adapter. N18
generalizes the Draft → Approval → Write → Evidence framework and gives Lead
creation one authority: `core.lead_service.create_lead()`. Phase 3's job is
migrating every channel onto that authority without silently changing Owner
semantics, dedup behavior, or approval requirements per channel.

## 2. Current Writer Map (verified 30/08/2026)

**Already canonical — call `create_lead()` directly or through a
`create_lead()`-calling wrapper:**

- Telegram natural-language Lead creation, structured Lead command, Lead
  Draft confirmation, batch import via `_write_one_lead()` (pre-N18-Phase-3
  baseline, unchanged by this reconciliation).
- Telegram Lead Preview approval (`app.py`, N18 Phase 3 Slice 1) — calls
  `create_lead(..., manage_action_contract=False)` from inside ActionGateway's
  own approved-contract dispatch executor; the generic Leads dispatcher path
  is prevented for this trusted preview source.
- Telegram approve/cancel buttons (N18 Phase 4 buttons slice) — dispatches
  into the same Draft/ActionGateway flow.
- WhatsApp inbound — `lead_capture.py` (unconditional `create_lead()` call)
  and, when `WHATSAPP_CANONICAL_LEAD_WRITE` is on, `core/whatsapp_lead_cutover.
  create_whatsapp_inbound_lead()` (a dedicated identity-resolution path that
  also calls `create_lead()`). Either branch is canonical.
- Email inbound — `inbound_handler.py` (F06 gate) calls `create_lead()`
  directly; `core/noninteractive_lead_cutovers.create_email_inbound_lead()`
  is available as an alternate canonical entry point using the same identity
  + Owner-mapping pattern as Furniture/Voice.
- Furniture funnel — `furniture_lead_funnel.py` →
  `core/noninteractive_lead_cutovers.create_furniture_inbound_lead()` →
  `create_lead()`.

**Update-only path (not a creation writer — correctly out of scope for a
creation-bypass audit):**

- LeadMemory (`lead_memory.py`) — enrichment only, via
  `core.lead_service.update_lead_fields()`. Never creates a Lead; finds an
  existing record by `memory_key` or does nothing.

**Remaining legacy bypass:**

- Voice IVR (`voice_adapter.py::_save_voice_lead()`) — when
  `VOICE_CANONICAL_LEAD_WRITE` is off (current default), falls through to a
  direct `tools.airtable_tools.airtable_add()` call, bypassing `create_lead()`
  entirely (no Owner-invariant enforcement, no ActionGateway dedup
  fingerprint, no ActionContract lifecycle record). When the flag is on, it
  correctly calls `create_voice_inbound_lead()` → `create_lead()`.

## 3. Canonical Target Architecture

```
source adapter → canonical identity/context → create_lead() → canonical Lead write
```

Every Lead-creating channel resolves to this invariant. An adapter's only
job is producing an `Identity` (via `identity.resolve_identity()`) and a
`LeadPayload` — it must not itself decide dedup outcome, Owner assignment,
domain canonicalization, or approval requirement. `core.lead_service.
create_lead()` is the single place those decisions are made.

## 4. `create_lead()` Authority Boundary

`core/lead_service.py::create_lead(identity, payload: LeadPayload, *,
source_module, existing_id=None, write_event=True,
manage_action_contract=True) -> LeadCreateResult` owns, in this order:

1. **Payload validation** (`_validate()`) — name/phone required, referral
   field cross-validation (`REFERRAL_FEE_TYPES`/`REFERRAL_FEE_STATUSES`).
2. **Domain canonicalization** — rejects any `payload.domain` not in
   `CANONICAL_LEAD_DOMAINS`.
3. **Emergency Stop gate** — `EMERGENCY_STOP_ALL` blocks before any write.
4. **Owner resolution** (`resolve_owner()`) — hard-enforced invariant: an
   unresolvable Owner blocks creation outright (`action="invalid"`), exactly
   like a missing name/phone. There is no warn-and-proceed fallback; this
   replaced an earlier, explicitly rejected soft-fallback design.
5. **Dedup** — `existing_id` if the caller already resolved one (backward
   compatibility for callers with their own lookup), else
   `find_existing_lead(name, phone)`.
6. **ActionGateway proposal** (`action_gateway.propose_action()`) — dedup
   fingerprint + audit ledger, skipped only when `manage_action_contract=False`
   (reserved for a caller — currently only the Telegram Preview path — that
   is itself executing an already-approved outer ActionContract, to avoid a
   nested contract for the same write).
7. **Write** — `tools.airtable_gateway.airtable_create()`/`airtable_patch()`
   on the `Leads` table — the single Airtable write path, never a direct
   `httpx` call.
8. **Lifecycle persistence** — the ActionContract's ledger status is updated
   to `completed`/`failed`; a persistence failure here is itself a terminal
   result (`action="lifecycle_persistence_failed"`), not swallowed.
9. **Post-write enrichment** (`_run_post_write_enrichment`) — fires only on
   success.

`update_lead_fields()` is the sibling, narrower authority for updating an
*existing* Lead (used by LeadMemory and others) — it requires a
pre-resolved `record_id` and an explicit field set, and has no
direct-writer fallback on gateway proposal failure.

## 5. Adapter Responsibilities

An adapter (WhatsApp/Email/Furniture/Voice/Telegram):

- Resolves its own channel-specific identity (`identity.resolve_identity()`,
  or a purpose-built resolver like `resolve_owner_user_id()` for a
  non-interactive destination-account mapping).
- Builds a `LeadPayload` with the fields it actually knows.
- Calls `create_lead()` (or a thin per-channel wrapper in
  `core/noninteractive_lead_cutovers.py`/`core/whatsapp_lead_cutover.py` that
  does the same) and returns/logs the `LeadCreateResult` it gets back.

An adapter must **not**: invent Owner business rules, substitute an
arbitrary default Owner, decide dedup on its own, or call
`tools.airtable_tools.airtable_add()`/`airtable_gateway.airtable_create()`
against the `Leads` table directly.

## 6. Owner Resolution (already implemented — not a design task in this pass)

`core/source_owner_mapping.py` provides the canonical, already-built policy
for non-interactive sources:

- `resolve_owner_user_id(source: OwnerMappingSource, identifier, *, mappings=None)`
  looks up a configured `owner_user_id` for a WhatsApp destination number,
  email recipient, or voice destination — from `config.OWNER_USER_ID_MAPPINGS`
  by default. Returns `None` (never a guessed default) when unmapped.
- `resolve_furniture_owner_user_id()` is the Furniture-specific WhatsApp
  destination-account wrapper.
- `carried_owner_user_id()` validates an explicit LeadMemory owner context
  without inventing one.
- The module's own docstring is explicit about the boundary this spec must
  preserve: *"Profile record resolution belongs exclusively to
  `core.lead_service.create_lead()`."* — these functions resolve a
  **user_id string**, never a Profile **record id**; `create_lead()`'s own
  `resolve_owner()` does the user_id → Profile-record-id resolution
  (`tma_api._resolve_profile_record_id()`) and hard-enforces the invariant.

Explicitly prohibited (and not present in current code — verified by
reading all three `noninteractive_lead_cutovers.py` wrappers and
`lead_capture.py`): first-Profile fallback, first-admin fallback, an
arbitrary configured user without documented authority, or a silent
null-to-owner substitution inside an adapter. Every mapping miss returns
`LeadCreateResult(ok=False, action="blocked", reason="... owner mapping
missing")` — creation is refused, never defaulted.

**No further Owner Resolution design work is required by this spec.** The
open item is narrower: Voice IVR's *legacy fallback branch* does not go
through this resolution at all (see §9) — that is a cutover-completion gap,
not a missing policy.

## 7. Validation / Dedup / Owner / Attribution Authority

All four live inside `create_lead()` (§4, steps 1/5/4/9) — never
duplicated in an adapter. `LeadPayload`'s campaign/referral fields are
validated by the same `_validate()` call even though (per its own comment)
no live Airtable column exists yet for campaign attribution — the model is
locked in ahead of the schema, not the other way around.

## 8. ActionGateway Interaction

`create_lead()` calls `action_gateway.propose_action(...)` for dedup
fingerprinting and an audit/lifecycle ledger entry, with
`requires_approval=False` (Lead creation itself is not an approval-gated
tool) — this is a bookkeeping/idempotency proposal, not the approval flow
used for `requires_approval=True` tools elsewhere. `manage_action_contract=
False` is the one documented exception, reserved for a caller that is itself
running inside an already-approved outer ActionContract (currently only the
Telegram Preview path, per its own docstring note referencing N18 Phase 3
Slice 1) — never a general opt-out.

## 9. No-Legacy-Fallback Rule After Cutover

**Invariant: no supported Lead creation path may bypass `create_lead()`.**
Today this invariant holds for every writer except one:

- **Voice IVR** (`voice_adapter.py::_save_voice_lead()`): when
  `VOICE_CANONICAL_LEAD_WRITE` is off (default), a direct
  `airtable_add()` call executes instead of `create_voice_inbound_lead()`.
  This is the single concrete violation of the invariant that exists in
  running code today.

Closing it is a two-step, already-designed cutover (§13), not new design
work: (1) owner activates `VOICE_CANONICAL_LEAD_WRITE` + runs a live canary,
(2) once verified, the `else` branch's direct `airtable_add()` import and
call in `_save_voice_lead()` is deleted, leaving `create_voice_inbound_lead()`
as the only path.

## 10. Error Semantics

`LeadCreateResult.action` is a closed vocabulary: `"created"`, `"updated"`,
`"duplicate"`, `"blocked"` (Emergency Stop or Owner-mapping-missing),
`"invalid"` (validation/domain/Owner-resolution failure), `"gateway_failed"`
(ActionGateway proposal raised), `"lifecycle_persistence_failed"` (write
succeeded but the ledger update failed — treated as a terminal failure, not
a partial success). No adapter should re-interpret or collapse these —
callers branch on `result.ok` and, for operator-facing messages, `result.
reason`.

## 11. Idempotency Requirements

Idempotency is enforced at two layers, both inside `create_lead()`, never in
an adapter: (1) `find_existing_lead(name, phone)` / caller-supplied
`existing_id` decides created-vs-updated before any write; (2)
`action_gateway.propose_action()`'s dedup fingerprint is the
defense-in-depth layer against a duplicate proposal for the same logical
write (e.g. a retried webhook). An adapter must not add its own idempotency
key or duplicate-suppression logic in front of `create_lead()`.

## 12. Writer-by-Writer Migration Strategy (status, not a new plan)

| Writer | Status | Remaining step |
|---|---|---|
| Telegram (NL / structured / batch) | CLOSED (pre-Phase-3 baseline) | none |
| Telegram Lead Preview | CLOSED (Phase 3 Slice 1, PR #1043) | none |
| Telegram approve/cancel buttons | CLOSED (Phase 4, PR #1065) | none |
| WhatsApp | Code CLOSED (both branches canonical) | owner-gated flag activation + live canary (runtime evidence only) |
| Email | Code CLOSED | runtime evidence only |
| Furniture | Code CLOSED | runtime evidence only |
| Voice IVR | Code CLOSED for the canonical branch; legacy branch still live when flag is off | owner-gated flag activation + live canary, **then delete the legacy branch** |
| LeadMemory | N/A (update-only, out of scope) | none |

No writer requires new design work. What remains for WhatsApp/Voice is
activation + observation, not implementation — see §13.

## 13. Static vs. Runtime Verification Requirements

**Static (met today, this pass):** grep-confirmed `create_lead()` call sites
for every writer in §2; `test_n18_slice1_lead_preview.py` (6/6),
`test_n18_phase4_telegram_buttons.py` (4/4), and
`test_n18_draft_dispatch_unification.py` (8/8) all pass on current
`origin/main`.

**Runtime (not established, not claimed here):** no deployed-SHA canary
evidence exists yet for `WHATSAPP_CANONICAL_LEAD_WRITE` or
`VOICE_CANONICAL_LEAD_WRITE` in production. This document does not claim
otherwise, and this environment cannot itself perform a new deployment —
see `ROADMAP.md`'s `ORACLE_MIGRATION_M0` row for the current deployment
constraint. This is a runtime-verification constraint, not a development
freeze: further static work (e.g. Voice's legacy-branch removal PR) can
still be prepared and merged ahead of the canary.

## 14. Rollback / Cutover Constraints

Both remaining flags (`WHATSAPP_CANONICAL_LEAD_WRITE`,
`VOICE_CANONICAL_LEAD_WRITE`) are independently toggleable and default OFF —
activation is reversible per-flag without a code change. Voice's legacy
branch must not be deleted until its canonical branch has live canary
evidence; deleting it first would leave Voice with no fallback if the
canonical path has an undiscovered runtime defect.

## 15. Closure Criteria

N18 Phase 3 (as scoped to Lead) closes when: both remaining flags are
activated in production, each has a deployed-SHA live-canary record (a real
inbound Lead created through the canonical path, evidenced the way
`verify_a1.py` evidenced SPEC A1), and Voice IVR's legacy `airtable_add()`
branch is deleted. A second entity consumer (Tasks/Payments/Deals/Contacts/
Expenses) is explicitly out of scope for this closure and requires a
separate owner-approved slice (per `BOSS_UNIFIED_MASTER_PLAN.md` §3.5's N18
row) — its absence must not be read as blocking this closure.
