# Task Golden Writer — canonical Task write core

**Status:** `CODE_DONE + STATIC_VERIFIED` on branch `claude/blank-task-cards-audit-4rsy4t` (24/09/2026, revision 2 after owner review). Not merged, deployed, or runtime-verified.
**Owner module:** `core/task_writer.py`
**Trigger:** blank task cards in the Mini App's "My Work" screen (audit, 24/09/2026).

## 1. Why

A read-only audit of the live Tasks table (`משימות (Tasks)`, 135 rows) found **99 rows with an empty `כותרת המשימה`**. 97 of them had no other field set. The TMA projection and the card only pass values through, so the title was already empty in the **creation payload**:

- `core/action_gateway._sheets_payload_to_airtable()` mapped `row_data[0]` to the title with no value check. `row_data=[""]` produced `{כותרת המשימה: ""}` and nothing else. This is the primary root cause.
- `action_validator` checks key presence and `airtable_gateway.validate_airtable_fields()` checks field names, not text values. So the generic `airtable_add` path was equally open.
- `interaction_engine` wrote the title and due date straight from the LLM's JSON.

The 99 historical rows are **not** changed by this work.

## 2. Four separated concerns

| Concern | Where | What it does |
|---|---|---|
| **Golden Writer validation** | `core/task_writer.py` §1 (pure) | The one invariant: Title is required and non-empty after safe normalization (NFKC, zero-width removal, whitespace normalization). A non-text value has no title (the field is `singleLineText`). UPDATE is checked only when it touches Title. It adds **no** policy for Status, Due Date, Owner or unknown fields; existing schema contracts and `airtable_gateway` still own those. |
| **Resolver / verification** | `core/task_writer.py` §2 (pure, I/O injected) + `core/action_gateway._fetch_task_link_record` / `_task_link_name_resolver` | A model-supplied link is never passed through directly. A `rec…` ID that exists in its linked table (`get_record_fields`) is kept. A Contact or Deal name is resolved through the existing canonical exact-label, tenant-scoped resolver `commercial_crm.lookup_human_reference`, and only an exactly-one match yields the canonical ID. Anything not found, ambiguous or without a resolver (Lead or Owner by name) is **omitted**, because every link field is optional. Links from trusted internal sources keep the existing behavior. |
| **Diamond completion** | `core/task_writer.py` §3 (pure) + `complete_task_proposal` | Before asking, derive a missing Title from trusted context: (1) the user's own text through the router's existing deterministic create-task parser (`parse_deterministic_create_task`, certain results only; its due date is reused if the payload has none); (2) a **verified** linked Lead whose `Next Action` is actionable, plus the Lead's name, giving `"<action label> — <name>"` (for example `להתקשר בחזרה — דני כהן`). The labels match `tma_api._LEAD_NEXT_ACTION_OPTIONS`, enforced by a test. A name alone, a non-actionable Next Action (Waiting Response or Closed …), or an unverified record yields nothing, so nothing is invented. |
| **Caller UX** | callers | **Agent / bot:** only when no title can be derived, `TaskCanonicalizationError` → `_queue_approval_detailed`'s existing CanonicalizationError handler → `APPROVAL_QUEUE_NEVER_ATTEMPTED` + `"מה כותרת המשימה?"` (asks for the title only). **Workers:** derive, else skip and log. **Router:** unchanged (it already asks). **Mini App:** unchanged. |

## 3. Canonical flow

```
router / Agent airtable_add / Agent sheets_append / interaction_engine / abandoned_lead_worker
   → resolve_canonical_call()                                   (unchanged)
   → GATE 1  core.action_gateway.complete_task_proposal()       (before approval)
        verification (agent source) → Diamond completion → Title validation
        · called by app._queue_approval_detailed_impl() and ActionGateway.propose_action()
        · returns the SAME dict when nothing changed, so the caller's fingerprint_payload is kept
        · a changed payload drops the caller's fingerprint_payload (BUG-CRM-BYPASS-FINGERPRINT-PARITY
          precedent), so the stored fingerprint is computed from exactly what will be dispatched
   → approval (ActionContract lifecycle, dedup and audit unchanged)
   → GATE 2  tools/dispatcher.py airtable_add / airtable_update on Tasks   (persistence boundary)
        after _validate_execution_proof; Title invariant only; writes the normalized Title,
        every other field untouched
```

## 4. The six known Task creation paths

| # | Path | Bypass risk before | Changed in this work? |
|---|---|---|---|
| 1 | Router deterministic create (`task_builders` → `gateway_call`) | Low: title already required | **No code change.** It passes through both gates; its valid payload comes back as the same object, so its `fingerprint_payload` (BUG-TASK-01) is untouched |
| 2 | Agent raw `airtable_add` → Tasks | **High** | **Yes, via both gates:** verification, Diamond completion, title-only ask |
| 3 | Agent `sheets_append` → Tasks (**root cause**) | **High** | **Yes, via both gates.** Diamond can recover the title from the user's own create-task text |
| 4 | `interaction_engine.create_tasks_from_analysis` | **High** | **Yes (worker code):** an item without a non-empty `title` is skipped, because the interaction offers no trusted action to derive one from. An invalid LLM due date is **omitted**, not invented, and the Task is still created. Non-object items are skipped. The existing Status default is kept |
| 5 | `abandoned_lead_worker.create_human_pipeline_task` | Medium | **Yes (worker code):** existing template `📞 ליד נטוש — <subject>`; subject = sender, else the lead's own `answers["name"]` (same key `voice_adapter` uses); skipped only if neither exists. (`_parse_sessions` already requires a sender, so that skip is defensive) |
| 6 | Mini App `POST /api/leads/<id>/task` → `tma_write` | Low: requires title (HTTP 400) | **No.** Out of scope |
| + | `airtable_update` on Tasks | Medium: could blank a title | **Yes, both gates:** only an update that blanks Title is rejected |

## 5. Existing test fixtures changed

Each change supplies the canonical title field. The pre-existing contract that justifies it: the Task title field is `כותרת המשימה` (`airtable_schema.TaskFields.NAME`, `FIELD_MAP[Tables.TASKS]`, `tools/dispatcher._DEDUP_FIELDS`, and the Agent's own schema in `core_knowledge.py`: "אין שדה Name… שמות השדות בעברית בלבד"). `"Task"`, `"name"` and an empty `fields` are not Task title fields; `airtable_gateway.airtable_create()` drops unknown fields and blocks the write (SPEC A1). These fixtures therefore described a Task write that the pre-existing contract could never persist with a title. Every changed line was then minimized automatically: each was reverted individually and kept only if the test fails without it. All `"Due": "היום"`/`"מחר"` values are restored (the revised writer has no due-date rule). `test_pending_contract_read_amplification.py` is fully restored; it passes unchanged.

See the completion report for the per-file list.

## 6. Cross-Layer Impact: FULL

The change touches canonical Airtable write paths across the approvals and tools layers.

- **Layer 1 — Core Reasoning / BUG-104:** not touched. The Agent only receives the existing CanonicalizationError return shape carrying a title question. Test: `test_pa01_phantom_approval_enforcement.py`.
- **Layer 2 — TurnCoordinator:** touched indirectly. `app._queue_approval_detailed_impl` calls Gate 1 after `resolve_identity`. Output: either a completed payload (fingerprint_payload dropped only when changed) or `APPROVAL_QUEUE_NEVER_ATTEMPTED` + the title question. BUG-122 slot accounting is unchanged. Tests: §E, `test_single_speaker_fallback_and_duplication.py`, `test_bug_canonical_tool_wiring.py`.
- **Layer 3 — F52 / Phase 4C Action & Tool Contract:** touched directly. The dispatcher Tasks branches (Gate 2) and `core/task_writer.py`. There is no new source of truth, and the registry, role, tenant, emergency and proof gates are unchanged and still run first. Dedup runs on the normalized title. Observability: the `[TaskGoldenWriter] create rejected` warning plus `audit_log_airtable(... "blocked: title_blank")`. Tests: §F, `test_c53a.py`, `test_bug_crm_bypass_airtable_update.py`.
- **Layer 4 — Durable Atomic Approval:** touched directly. `propose_action` runs Gate 1 before BUG-122 and before any ledger access. ActionContracts remain the lifecycle authority. Stored payload = dispatched payload, and fingerprint parity holds (§D, `test_bug_task_01_execution_proof_fingerprint_parity.py`, `test_business_action_fingerprint_normalization.py`). New reads (link verification) happen only when the Agent supplied link values. Each failure means "unverified → omit", never a pass-through.

## 7. Not in this change

- The 99 historical blank rows (a data mutation, separate owner decision).
- Owner auto-defaulting (no established write-time contract exists; My Work already shows Owner-less Tasks to the sole owner).
- Mini App `tma_write` (path 6).
- Deriving the Lead-link Title template beyond actionable `Next Action` options.
