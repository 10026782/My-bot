# Task Golden Writer — canonical Task write core

**Status:** `CODE_DONE + STATIC_VERIFIED` on branch `claude/blank-task-cards-audit-4rsy4t` (24/09/2026). Not merged, deployed, or runtime-verified.
**Owner module:** `core/task_writer.py`
**Trigger:** blank task cards in the Mini App's "My Work" screen (audit, 24/09/2026).

## 1. Why

A read-only audit of the live Tasks table (`משימות (Tasks)`, 135 rows) found **99 rows with an empty `כותרת המשימה`**. 97 of them had *no* other field set. The TMA projection (`tma_api._process_owner_tasks`) and the card (`MyWork.tsx`) only pass values through, so the title was already empty in the **creation payload**:

- `core/action_gateway._sheets_payload_to_airtable()` mapped `row_data[0]` to the title with no value check. `row_data=[""]` produced `{כותרת המשימה: ""}` and nothing else, which matches the live blank-row shape. This is the primary root cause.
- `action_validator._check_presence()` only checks that `fields`/`row_data` keys are present. `tools/airtable_gateway.validate_airtable_fields()` checks field *names*, not text *values*. So the generic `airtable_add` path was equally open.
- `interaction_engine` wrote the title straight from the LLM's JSON (`task.get("title", "")`), plus an unvalidated LLM due date.

## 2. Canonical flow

The write core is shared. Each caller keeps its own interaction layer (UX).

```
router (task_builders) ─┐
Agent airtable_add ─────┤
Agent sheets_append ────┤ resolve_canonical_call()  → canonical airtable_add / airtable_update
interaction_engine ─────┤
abandoned_lead_worker ──┘
        │
        ▼  GATE 1: proposal boundary. Validate only; the payload is never rewritten (BUG-TASK-01 fingerprint parity)
   core.action_gateway.enforce_task_write_contract(tool, payload, trusted_source)
     └─ called by ActionGateway.propose_action() and app._queue_approval_detailed_impl()
     └─ fails closed with TaskCanonicalizationError(user_message, code, missing) before any fingerprint/ActionContract
        │  (app: CanonicalizationError handler → APPROVAL_QUEUE_NEVER_ATTEMPTED + "מה כותרת המשימה?")
        ▼
   approval (ActionContract lifecycle unchanged)
        │
        ▼  GATE 2: execution boundary (after _validate_execution_proof)
   tools/dispatcher.py  airtable_add  → task_writer.prepare_task_create()  → dedup → airtable_add()
                        airtable_update → task_writer.prepare_task_update() → allowlist/Domain → airtable_update()
```

`core/task_writer.py` is pure: no I/O, idempotent, `prepare(prepare(x)) == prepare(x)`.

## 3. Rules (Golden Writer + Diamond completion)

| Field | Rule |
|---|---|
| **Title** (`כותרת המשימה`) | **Required.** Must be text. Normalized with NFKC; zero-width characters and NBSP removed; whitespace collapsed. Must contain a letter or digit. Must not be a placeholder (`משימה`, `משימה חדשה`, `task`, `null`, `none`, `n/a`, `tbd`, …). At most 250 characters (rejected, never truncated). Rejection carries `missing=("כותרת המשימה",)` and asks only for the title. |
| Status | Auto-defaults to `ממתין` (deterministic). Accepts `ממתין/בביצוע/בוצע` and the fixed aliases `pending/todo/in progress/done/completed`. Anything else is rejected, never guessed. |
| Due date | Optional. Strict `YYYY-MM-DD` and a real calendar date. `מחר`, `tomorrow`, `2026-02-31` and datetimes are rejected. |
| Description, Domain | Optional text. Empty values are dropped. Domain on update keeps the existing live-select canonicalization. |
| Owner / Contacts / Deals / Leads links | **Rejected when the source is the Agent** (`trusted_source` missing or `"agent"`). Trusted internal sources must supply well-formed `rec…` IDs. Owner is **not** auto-resolved in this migration. A Task with no Owner is already shown to the sole owner by the My Work projection. |
| Unknown fields | Rejected (fail closed). The aliases `title/description/due_date/status` map deterministically. The same field sent under two names is rejected as ambiguous. `tenant_id` is ignored. |

Automatic (system) Tasks must derive a meaningful title from their source. If they cannot, **no Task is created**. Bot-created Tasks ask only for the missing title.

## 4. Migration matrix (the six known creation paths)

| # | Path | Bypass risk before | Diamond completion needed? | Migration in this change |
|---|---|---|---|---|
| 1 | Router deterministic create (`core/router/task_builders.py` → `turn_coordinator_runtime.gateway_call`) | Low: `_require_text` already required a title | Already asks for the title | None needed. Both gates apply transparently; Status now defaults to `ממתין` at write time |
| 2 | Agent raw `airtable_add` on Tasks | **High**: no value checks | Ask for the title only | Gate 1 + Gate 2 |
| 3 | Agent `sheets_append` → Tasks (`_sheets_payload_to_airtable`) — **root cause** | **High**: `row_data[0]` unchecked | Ask for the title only | Gate 1 + Gate 2 |
| 4 | `interaction_engine.create_tasks_from_analysis` (LLM output) | **High**: blank or placeholder title; unvalidated due date | Automatic: skip a task with no real title; drop an invalid optional due date | Pre-validation in the worker + both gates |
| 5 | `abandoned_lead_worker.create_human_pipeline_task` | Medium: an empty sender gives the generic title `📞 ליד נטוש — ` | Automatic: no identifiable sender → no task | Guard in the worker + both gates |
| 6 | TMA `POST /api/leads/<id>/task` → `tma_write` | Low: strips and requires the title (HTTP 400) | Mini App UX unchanged | **Out of scope** (Mini App). A possible follow-up is to call `prepare_task_create(source="tma_api")` inside `tma_write` for defense in depth |
| + | `airtable_update` on Tasks | Medium: could blank an existing title | n/a | Gate 1 + Gate 2 title/due/status checks |

## 5. Cross-Layer Impact: FULL

The change touches canonical Airtable write paths and two layers (approvals + tools).

### Layer 1 — Core Reasoning / BUG-104
- touched: not touched
- input/output/authority impact: none. Proof: no file under the Core Reasoning layer changed. The Agent only sees a different `message` string in the existing CanonicalizationError return.
- shared identifiers: none new
- invariants: unchanged
- failure semantics: unchanged
- observability: n/a
- cross-layer tests: `test_pa01_phantom_approval_enforcement.py` (passes)

### Layer 2 — TurnCoordinator
- touched: indirectly (`app._queue_approval_detailed_impl` calls the new gate)
- input impact: none
- output impact: a Tasks proposal that fails the Task contract now returns the existing `APPROVAL_QUEUE_NEVER_ATTEMPTED` shape, carrying a title-request `message`
- authority impact: none. The existing CanonicalizationError handler owns the reply
- shared identifiers: `TaskCanonicalizationError` (a subclass of the existing `CanonicalizationError`, same `user_message` attribute as `CommercialCanonicalizationError`)
- invariants: BUG-122 slot accounting is unchanged (NEVER_ATTEMPTED does not consume the slot)
- failure semantics: fail closed; nothing is queued
- observability: `[Approval] _queue_approval_detailed canonicalization failed` log
- cross-layer tests: `test_task_golden_writer.py` §C, `test_single_speaker_fallback_and_duplication.py`, `test_bug_canonical_tool_wiring.py`

### Layer 3 — F52 / Phase 4C Action & Tool Contract
- touched: directly (`tools/dispatcher.py` airtable_add/airtable_update Tasks branches; new `core/task_writer.py`)
- input impact: none
- output impact: an invalid Task write returns C53-A `ok=False` with a user-safe message. A valid write persists normalized fields (trimmed title, Status defaulted)
- authority impact: a new validation authority for the Tasks write *shape*. There is no new source of truth, and the registry/role/tenant/emergency/proof gates are unchanged and still run first
- shared identifiers: `TaskWriteRejected`, `prepare_task_create`, `prepare_task_update`
- invariants: normalization runs after `_validate_execution_proof`, so the fingerprint is still computed on the approved payload. Dedup (`_DEDUP_FIELDS`) now runs on the normalized title
- failure semantics: fail closed before any Airtable call
- observability: `[TaskGoldenWriter] create rejected | code=…` warning and `audit_log_airtable(... "blocked: <code>")`
- cross-layer tests: `test_task_golden_writer.py` §D, `test_bug_crm_bypass_airtable_update.py`, `test_c53a.py`

### Layer 4 — Durable Atomic Approval
- touched: directly (`ActionGateway.propose_action` calls `enforce_task_write_contract` right after `resolve_canonical_call`)
- input impact: none
- output impact: an invalid Tasks proposal raises before any ledger, live-contract or persistence access
- authority impact: none. ActionContracts remain the lifecycle authority. No contract is created, inferred or repaired
- shared identifiers: `enforce_task_write_contract`
- invariants: the stored payload is byte-identical to before (validate-only), so BUG-TASK-01 parity holds
- failure semantics: `TaskCanonicalizationError`, the same class of exception `CommercialCanonicalizationError` already raises from this point
- observability: the exception message and code
- cross-layer tests: `test_task_golden_writer.py` §B, `test_bug_task_01_execution_proof_fingerprint_parity.py`, `test_create_task_deterministic_route.py`, `test_business_action_fingerprint_normalization.py`

## 6. Test fixture changes

About a dozen existing approval-flow tests proposed Tasks using made-up field names (`"Task"`, `"Due": "היום"`, `"name"`, or empty `fields`). Those payloads could never have produced a real Airtable Task: the gateway drops unknown fields and blocks the write. They were switched to the real field names (`כותרת המשימה`, `תאריך יעד`) without changing what each test asserts. One fixture was left unchanged on purpose: `test_pa01` P2-4 relies on an unapproved field name to trigger the CanonicalizationError path.

## 7. Not in this change

- Cleaning up the 99 existing blank rows in Airtable. This is a data mutation and needs a separate owner decision.
- Owner auto-resolution. It needs a Profile lookup (I/O) and an ambiguity policy.
- TMA `tma_write` defense in depth (path 6).
- Editing the `interaction_engine` prompt example (`"title": "משימה"`). Such output is now rejected as a placeholder.
