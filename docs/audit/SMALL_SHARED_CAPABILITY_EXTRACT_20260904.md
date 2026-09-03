# Small Shared Draft-Field Capability Audit

**Date:** 04/09/2026  
**Classification:** `SMALL_SHARED_CAPABILITY_EXTRACTED`  
**Evidence level:** `STATIC_VERIFIED` only; not merged, deployed, or runtime verified.

## Extracted capability

The implementation adds one state-only primitive for existing structured draft/session dictionaries:

- `SET_FIELD`
- `CLEAR_FIELD`
- `MOVE_FIELD`
- `SWAP_FIELDS`

`FieldMetadata` carries the user label, prompt, input type, finite choices,
resolver, editability, clearability, and compatible field type. Operations stage
all changes before committing, so validation failures leave the original state
unchanged. Linked fields are rejected by scalar MOVE/SWAP.

## Lead application

The existing `lead_draft` remains the sole state object. Lead field validation
now delegates mutation to the shared `SET_FIELD` primitive. Existing Lead
rendering and DraftFlow remain in place; metadata supplies user-facing labels,
prompts, and domain single-select options.

## Commercial application

No `CommercialCompletionSession` exists in the inspected checkout or git
history. No parallel session or replacement state object was created. The
generic metadata and operation API is ready for the existing session when its
actual module is identified.

## Explicitly out of scope

No BusinessDraft model, persistence store, new state machine, batch architecture,
writer, ActionContract, ActionGateway, approval change, TMA migration, Task
migration, Contact migration, Payment migration, or legacy-store removal.

## Verification

- `test_draft_field_operations.py`: 3 passed
- `test_draft_flow.py`: 16 passed
- `test_n18_draft_dispatch_unification.py`: 8 passed
- `python3 -m py_compile core/draft_fields.py core/lead_service.py`: passed
- `git diff --check`: passed

Focused tests emitted expected local Airtable/network warnings; no production
claim is made.

## Owner decision

No architecture decision is required for this primitive. Commercial wiring
requires identifying or supplying the existing `CommercialCompletionSession`;
it must not be invented as part of this change.
