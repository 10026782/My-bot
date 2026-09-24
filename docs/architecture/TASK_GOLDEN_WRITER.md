# Task Golden Writer — canonical Task write core

**Status:** Golden Writer core merged to `main` (PR #1266, merge `df623f89`). Not deployed or runtime-verified. §8 Recurrence: `CODE_DONE + STATIC_VERIFIED` on branch `claude/blank-task-cards-audit-4rsy4t` (24/09/2026). Not merged, deployed, or runtime-verified.
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

### Diamond scope (intentional, this PR)

Task Diamond completion is **deliberately limited** to the two trusted sources implemented here:

1. the user's original create-task text, parsed by the router's existing deterministic parser (certain results only); and
2. a **verified** linked Lead whose `Next Action` is actionable, combined with that Lead's name.

It does **not** complete a Title from Contact or Deal context. Contact and Deal names are used only by **verification**, to turn a model-supplied link into a canonical ID or to omit it. They never produce a Title, because neither table carries an action to derive one from. Extending completion to other sources is out of scope for this PR.

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

**Ordering (verified in code and tests):**

- **Agent path.** In `app._queue_approval_detailed_impl`, Gate 1 runs right after `resolve_canonical_call` and `resolve_identity`. It runs before the executed-action dedup fingerprint (`executed_action_cache.compute`), the EventBus business-fingerprint lookup, the approval label (`_describe_tool_call`) and `propose_action`. All of them receive the completed `tool_inputs`.
- **Proposal.** Inside `propose_action`, Gate 1 runs before `normalize_payload`, the choice of fingerprint basis and `compute_business_fingerprint`.
- **Result.** The completed payload is exactly what is approved, fingerprinted, stored on the ActionContract and passed to the dispatcher. Tests: `test_task_golden_writer.py` §P (P1–P4), which includes the real `_validate_execution_proof` check and a real `dispatch_tool` write.

**Gate 2 is validation and normalization only.** It never runs Diamond completion or link resolution. Completion happens only before approval, so persistence cannot change a Task's business meaning after it was approved (§N). The only change Gate 2 makes is whitespace/NFKC normalization of the Title, which is idempotent on the stored payload: `propose_action` already canonicalizes Task text through `_canonical_task_payload`.

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
- Title completion from Contact or Deal context, or from any source other than the two listed under "Diamond scope".

## 8. Recurrence (Tasks.`Cadence`)

Owner decisions (24/09/2026): reuse the existing `Cadence` single-select (`fldcQk3DisdkzhPMX`); no new field, no rename, no backfill, no option cleanup. Recurrence is separate from Status: Status is the state of the current occurrence, `Cadence` is how often it repeats.

| Topic | Rule |
|---|---|
| Values | `Daily` / `Weekly` / `Monthly` / `One-time` (`airtable_schema.TaskRecurrence`, `TaskFields.RECURRENCE = "Cadence"`). Empty and the legacy live option `One Time` read as One-time. Nothing writes a default: One-time = no value. Any other value is rejected (it would otherwise become a new select option). |
| Parsing | `task_writer.recurrence_from_text`, deterministic and conservative: `כל יום` / `כל שבוע` / `כל חודש` (also with ו-/ב-). `כל היום/השבוע/החודש` ("the whole day…") is not a frequency. Ambiguous or unsupported → never guessed: a weekday after `כל יום` (`כל יום שני` = every Monday), negation, two different frequencies, `כל יומיים/שבועיים/חודשיים/שנה`, `כל N …`. The Title keeps the user's wording. |
| Where it is derived | Router deterministic create: `parse_deterministic_create_task` → `DeterministicTaskParse.recurrence` (also in `business_identity()`, so the fingerprint basis matches the write payload; BUG-TASK-01). Ambiguous → the router's existing clarification, asking only about frequency. Agent path (Gate 1): the user's own text fills a missing value and wins over a conflicting recurring value; ambiguous text asks only about frequency; when the text is silent (e.g. the user's answer to the date question), the model's canonical value is kept. It is shown in the approval label before anything is written. |
| Schedule anchor | Due Date = the next occurrence. A recurring Task needs one. **Daily** without a date → local today (Asia/Jerusalem). **Weekly/Monthly** without a date → `TaskCanonicalizationError` asking only for the start date; no weekday or month-day is invented. One-time: Due Date stays optional. |
| Completion | Marking a recurring Task `בוצע` becomes an update of the **same record**: `Due Date` = next occurrence, `Status` = `ממתין` (`TaskStatus.PENDING`, the existing pending option). No occurrence rows are created. One-time/empty/`One Time` → normal Done. A Task already `בוצע` is never advanced again. Completion history = the ActionContract/approval and audit records. |
| Next occurrence | `anchor + k·interval` for the smallest k ≥ 1 that is after today. Anchor = the current Due Date, or today for an undated Daily. An overdue Task jumps to the next future occurrence; Weekly keeps its weekday; Monthly = calendar month, day capped at month end (31/1 → 28/2 → 28/3: a known one-time drift). |
| Where it runs | **Gate 1 only**, before approval: `complete_task_proposal` → `_complete_task_update` (router `COMPLETE_TASK` and Agent `airtable_update`) and `tma_api.update_task_status` (Mini App "mark done", computed from the record the handler already loads). The record read (`_fetch_task_record`) fails **closed** on a read error (404 = no record → unchanged). The rewritten payload drops any stale `fingerprint_payload`, so approved == fingerprinted == executed. |
| Gate 2 | Validation only: Cadence must be a known option; a recurring create must carry a Due Date. It never reads the record, advances a date or fills an anchor. |
| Duplicates | Two completions from the same record state produce the same payload and fingerprint, so the second is caught as a duplicate. The next occurrence's completion has a later Due Date, so it is a different action. |
| Mini App | UX unchanged. Create stays One-time (it never writes `Cadence`). Completion correctly advances an already-recurring Task (backend only; response shape unchanged; an undated Weekly/Monthly returns 409 with the date question). My Work needs no change: it already reloads after "mark done" and buckets by Due Date. |

Tests: `test_task_recurrence.py` (R1–R12: parser, router create, normalization, math, pure completion, Gate 1 create/update, caller UX, parity with the real `_validate_execution_proof` + `dispatch_tool`, duplicate completion, Gate 2 validation-only, Mini App completion).

Cross-Layer Impact: FULL (same four layers as §6). Layer 2 (TurnCoordinator): the deterministic parse carries `recurrence`; ambiguous → existing CLARIFY. Layer 3 (Action & Tool Contract): the Tasks update allowlist and the router builder field set accept `Cadence`; Gate 2 validates it. Layer 4 (Durable Atomic Approval): the transformation happens before `propose_action` fingerprints anything; the ActionContract stores the advanced payload; `_validate_execution_proof` is unchanged. Layer 1 (Core Reasoning): one schema line in `core_knowledge.py`. New read: one `get_record_fields` per Task completion (and per update that makes an undated Task recurring), fail-closed.

Not in this change: RRULE / every N / weekday schedules; a recurrence badge in the Mini App; Mini App recurrence on create; the live `One Time`/`Open` option cleanup; the My Work 100-record read cap (separate HIGH bug, `BUG_AUDIT_LOG.md` → MY-WORK-TASK-READ-CAP).
