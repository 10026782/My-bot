# Approval Pending Batch Migration — Scope V1

**Gate:** `docs/architecture/CROSS_LAYER_AUTHORITY_CONTRACT_V1.md` — MANDATORY.
This is a Planning Gate document touching tools/actions, approvals, and
execution presentation (Layer 3/F52 and the RP5 guard, same territory as
`MESSAGE_CONTRACT_ENVELOPE_CONTRACT_V1.md` and the F52 Decision Log D-014/
D-015/D-016). Per that document's §7 standing rule it opens with this
reference and does not proceed past a completed Cross-Layer Impact Matrix —
recorded in §7 below.

**Status:** `SCOPE ONLY — NO CODE, NO PR, NO FLAG CHANGE.` This document
defines what the next follow-up covers and what it must decide before
implementation; it authorizes no runtime change by itself. Requested
02/08/2026, same day as D-016, as the explicit next work item.

**Prerequisite reading:** `UNIFIED_MESSAGE_UX_STANDARD.md` (canonical
patterns, now including the D-015 NEW-prompt/STATUS-QUERY split),
`core/agent_message_formatter.py` (`STATE_APPROVAL_PENDING_BATCH`/
`_render_approval_pending_batch()` — already code-complete since PR1, zero
live callers today), `core/action_gateway.py`'s `describe_pending_queue()`,
`query_execution_status()`, `_render_pending_query_reply()` (D-016 — the
off/shadow/on pattern this migration reuses), `DECISION_LOG.md` D-014/D-015/
D-016.

---

## 1. Purpose

Unify every "list of pending approvals" surface under
`STATE_APPROVAL_PENDING_BATCH`/`_render_approval_pending_batch()`, and in the
same vertical slice remove internal-term leaks from the user-facing text
those surfaces render today.

---

## 2. Trigger

1. D-016 explicitly deferred `describe_pending_queue()` and
   `query_execution_status()`'s multi-contract branch as "batch-shaped, not
   `approval_pending_query`-shaped" — this is that deferred follow-up.
2. Mid-session production transcript (this same day) surfaced the live
   symptom directly:
   ```text
   Eli: האם הפעולה ממתינה לאישור?
   BOSS: במערכת ActionContracts מצאתי 1 בקשות ממתינות:
   • 1. יצירת משימה: בדיקת PR E pending verification
   ```
   Two concrete defects in one reply: the internal module/table name
   "ActionContracts" is exposed to the user, and "1 בקשות ממתינות" is a
   grammar error specific to the count=1 case.

---

## 3. In scope

- `ActionGateway.describe_pending_queue()` — full migration (both the
  "no pending" branch and the numbered-list branch), including the
  `len(live) == 1` case.
- `ActionGateway.query_execution_status()`'s multi-contract branch
  (`len(live) > 1`) — currently `build_approval_lifecycle_result(contracts=live)
  .safe_user_message`, the exact same call `describe_pending_queue()` does
  not use today (they render differently — see §5) but should converge on
  the same target text once migrated.
- Numbered-list rendering behavior specifically for `count == 1` — must be
  decided, not assumed (see OQ1, §6).
- `off` / `shadow` / `on` wiring via the same `FEATURE_UNIFIED_STATUS_FORMATTER`
  three-state pattern D-016's `_render_pending_query_reply()` already
  established (reuse the pattern, not necessarily the same function — a list
  payload needs `items`, not `entity_name`).
- Observability: the same `_log_shadow_comparison()`/`_shadow_leak_flags()`
  safe-comparison logging, reused unmodified (per the Explicit Prohibitions
  in the Cross-Layer Authority Contract — no parallel logging mechanism).
- Output wording: target text owned by the existing, already-shipped
  `_render_approval_pending_batch()` (`core/agent_message_formatter.py:438`)
  — reviewed for correctness as part of this scope (see §5, the same
  count=1 grammar bug already exists there, unexercised until now).
- Internal-term cleanup, scoped to what actually leaks today (§5 has the
  full grep-sourced inventory): the literal string `"ActionContracts"`, the
  phrase `"תורי אישור legacy"`, and — flagged as a decision point, not
  assumed in scope — the raw `tool_name` fallback in
  `_describe_contract_for_reconfirmation()` (`core/action_gateway.py:880`)
  for non-Airtable, non-table tools.

---

## 4. Explicitly out of scope

- Approval logic, ownership, queue, evidence authority, routing —
  unchanged, same standing constraint as D-014/D-015/D-016.
- `MessageContract`/`MessageState` schema — `STATE_APPROVAL_PENDING_BATCH`
  already exists in `agent_message_formatter.py` only (same non-schema
  pattern D-015's `STATE_APPROVAL_PENDING_QUERY` used); no new state,
  no `core/message_contract.py` edit anticipated.
- `_render_pending_prompt()` (new-prompt, D-015) and
  `_render_pending_query_reply()` (single-contract status query, D-016) —
  unaffected; this migration is additive, a third rendering surface for the
  *multi*-contract case.
- Any single-contract branch already covered by D-016 — not touched again
  here.
- `FEATURE_UNIFIED_STATUS_FORMATTER`'s default (`off`) — unchanged by this
  scope document or its eventual implementation, same as every prior PR in
  this program.

---

## 5. Current state — inventory (grep-sourced, not assumed)

### 5.1 `describe_pending_queue()` (`core/action_gateway.py:3055-3069`)

```python
if not live:
    no_pending = self.describe_no_pending_reason(canonical_user_id)
    base = no_pending or "לא מצאתי בקשות ממתינות במערכת ActionContracts."
    return base + "\n\n(הבדיקה מכסה את מערכת ActionContracts בלבד — לא תורי אישור legacy נוספים.)"
...
lines = [f"במערכת ActionContracts מצאתי {len(live)} בקשות ממתינות:"]
for i, c in enumerate(live, 1):
    lines.append(f"• {i}. {_describe_contract_for_disambiguation(c)}{_format_pending_age_suffix(c)}")
lines.append("\nשלח את המספר (1, 2, ...) כדי לאשר פעולה ספציפית, או \"בטל <מספר>\" כדי לדחות אחת.")
lines.append("\n(הבדיקה אינה כוללת כרגע תורי אישור legacy נוספים.)")
```

- Renders a numbered list **unconditionally**, even for exactly one pending
  contract — the "send a number to select" affordance stays structurally
  identical regardless of count. This is the reason D-016 did not fold this
  surface into the singular `approval_pending_query` state.
- Leaks (4 lines, exact source):
  - `"לא מצאתי בקשות ממתינות במערכת ActionContracts."` (no-pending branch)
  - `"(הבדיקה מכסה את מערכת ActionContracts בלבד — לא תורי אישור legacy נוספים.)"`
  - `f"במערכת ActionContracts מצאתי {len(live)} בקשות ממתינות:"`
  - `"(הבדיקה אינה כוללת כרגע תורי אישור legacy נוספים.)"`
- Always sets `self._disambiguation[canonical_user_id] = list(live)` —
  **unchanged by this migration**; the reply-text surface and the
  disambiguation-state surface are independent (§4).
- Live call sites: `app.py:2901`, `app.py:3244` — both unconditional, no
  flag, current production behavior.

### 5.2 `query_execution_status()`'s multi-contract branch (`core/action_gateway.py:2975-3053`, two identical occurrences)

```python
if len(live) > 1:
    return build_approval_lifecycle_result(contracts=live).safe_user_message
```

`build_approval_lifecycle_result(contracts=live)` (`core/action_gateway.py:1084-1092`,
`canonical_state == "multiple_pending"`) renders:

```python
lines = ["יש כמה פעולות שממתינות לאישור:"]
for index, pending in enumerate(multiple, 1):
    lines.append(f"{index}. {_safe_contract_business_description(pending)}{_format_pending_age_suffix(pending)}")
lines.append("שלח מספר כדי לבחור פעולה אחת.")
```

- No `"ActionContracts"` leak here — this is a **different legacy renderer**
  from `describe_pending_queue()`'s (which builds its own lines with
  `_describe_contract_for_disambiguation()`, not
  `_safe_contract_business_description()`). The two multi-contract surfaces
  do not share wording today even though both answer "what's pending" —
  itself a parity gap worth closing as part of unifying onto one target
  (see OQ5).
- Live call site: `app.py:3271` — unconditional, no flag.

### 5.3 Known, already-documented leak in the per-item description (`core/action_gateway.py:847-880`)

`_describe_contract_for_reconfirmation()` (used by
`_describe_contract_for_disambiguation()`, which
`describe_pending_queue()`'s list rendering calls per item) has a
**documented, intentional-for-now** fallback:

```python
table = payload.get("table") or payload.get("spreadsheet_name") or ""
return f"{contract.tool_name} / {table}" if table else contract.tool_name
```

This leaks the raw `tool_name` (e.g. `gmail_send_draft`, `calendar_create_event`)
for any tool that isn't `airtable_add`/`airtable_update`. The function's own
docstring already flags this as the one remaining gap ("אין שם חשיפת טבלה
אפשרית שם"). **Not silently included as part of the "ActionContracts"
cleanup** — it is a distinct leak with different root cause (no generic
business-verb mapping exists yet for non-Airtable tools), called out
separately in OQ4 below rather than assumed in scope.

### 5.4 `_render_approval_pending_batch()` already has the same count=1 grammar bug (`core/agent_message_formatter.py:438-444`)

```python
header = f"יש {count} פעולות שממתינות לאישור:"
```

Ungrammatical for `count == 1` ("יש 1 פעולות שממתינות" — same class of bug
`_sibling_auto_cancel_disclosure()` (`core/action_gateway.py:894-905`)
already special-cases for singular/plural agreement, with an explicit
comment flagging exactly this pattern as wrong: `"עבור count=1 הניסוח '1
פעולות' שגוי דקדוקית"`. `_render_approval_pending_batch()` has never been
shadow- or live-tested against a real `count == 1` list because it has zero
live callers today — this migration is what would first exercise that path
for real, so the bug must be fixed as part of it, not discovered after.

### 5.5 Test surface already coupled to the leaking wording

At least 19 `test_*.py` files reference the literal string `"ActionContracts"`.
Most are incidental (class/module name in comments or unrelated fixtures).
One confirmed **routing-fingerprint** dependency that will break by
construction once the wording changes:

```python
# test_bug141_pending_query_dispatch_order.py:160-161, 177-178
chk("(a) reply comes from describe_pending_queue() (ActionContracts-scoped text)",
    "ActionContracts" in reply_a and "1 בקשות ממתינות" in reply_a)
```

This test currently proves "the reply came from `describe_pending_queue()`,
not the general agent" by matching the leaking string itself — i.e. the
leak is doubling as an (accidental, fragile) routing-verification signal.
Implementation must replace this with a real signal (mock/spy call
verification on `describe_pending_queue()` itself, or a distinct safe marker
in the reply) — not preserved by accident, and not left broken. A full
grep-based inventory of all 19 files is implementation-time work, not
completed here.

---

## 6. Open product decisions (must be answered before implementation)

- **OQ1 — does `count == 1` stay a numbered list?** Two real options:
  (a) keep the list shape unconditionally (today's behavior, and the
  scoped reason D-016 gave for not reusing `approval_pending_query` here)
  so the "reply with a number" affordance never changes shape; or
  (b) collapse `count == 1` to the singular `approval_pending_query`
  wording (D-015/D-016), reserving the list shape for `count >= 2`. (b)
  also sidesteps the count=1 grammar bug (§5.4) entirely for the singular
  case, but reintroduces the exact wording-divergence problem D-016 was
  built to close (two different renderers for "one thing pending",
  depending on which function answered). No default recommended here —
  this is the central design question the rest of the migration depends on.
- **OQ2 — what replaces `"ActionContracts"`?** Drop the internal-system
  framing entirely (e.g. `"מצאתי {count} בקשות ממתינות:"`), or keep a
  neutral non-internal qualifier. `_render_approval_pending_batch()`'s
  existing wording (`"יש {count} פעולות שממתינות לאישור:"`) already avoids
  naming any internal system — the default assumption is to converge on
  that existing wording rather than invent a new one, but this is an
  explicit decision point, not assumed.
- **OQ3 — what happens to the "legacy queues" disclaimer?** (`"הבדיקה מכסה
  את מערכת ActionContracts בלבד — לא תורי אישור legacy נוספים"`.) The
  underlying fact it discloses (this check does not cover `app.py`'s
  `_pending_approvals` dict or `event_bus.py`'s `PendingActionsStore` — see
  `core/action_gateway.py:1650`'s own comment) is real and may still be
  worth disclosing to the user, just not by naming internal store/module
  names. Rephrase without internal identifiers, or drop the disclosure
  entirely — decision needed, not a wording-only exercise.
- **OQ4 — is the `tool_name` fallback (§5.3) in scope for this migration?**
  It predates this investigation, is already documented as intentional
  pending a generic business-verb mapping for non-Airtable tools, and fixing
  it requires a different kind of change (a verb-mapping table, not a
  wording swap). Recommend treating as a explicitly separate, later
  follow-up unless the owner wants it folded in now.
- **OQ5 — does `query_execution_status()`'s multi-contract branch converge
  on the exact same target text as `describe_pending_queue()`?** They
  currently use two different legacy renderers with different wording
  (§5.1 vs §5.2) for what is conceptually the same "list of pending
  contracts" answer. Recommend yes (single target `_render_approval_pending_batch()`
  call for both), but confirm — they are reached from different user
  intents ("מה ממתין לאישור" vs "מה מצב הפעולה"), so a deliberate
  distinction is at least conceivable.

---

## 7. Cross-Layer Impact Matrix

### Layer 1 — Core Reasoning / BUG-104
touched: not touched
input impact: none
output impact: none
authority impact: none — no business phase/confidence/evidence computed here
shared identifiers: none
invariants: n/a
failure semantics: n/a
observability: none
cross-layer tests: none
proof of non-impact: grep evidence — no `leads_reasoning_projection`/`adapters/leads_adapter` identifier appears anywhere in the functions listed in §3; no code changed yet (scope-only document, zero `.py` diff).

### Layer 2 — TurnCoordinator
touched: not touched
input impact: none
output impact: none
authority impact: none — `reply_owner` for these surfaces is unaffected; `describe_pending_queue()`/`query_execution_status()` are direct-answer functions, not turn-routing decisions
shared identifiers: none
invariants: n/a
failure semantics: n/a
observability: none
cross-layer tests: none
proof of non-impact: no `TurnDecision`/`turn_context_source` read or written anywhere in the functions this scope touches; no code changed.

### Layer 3 — F52 / Phase 4C Action & Tool Contract
touched: directly (planned)
input impact: the eventual implementation reads `ActionContract.normalized_payload`/`.tool_name` (read-only) for each live contract, same as D-016.
output impact: user-facing text for two existing surfaces changes shape (once `on`); `STATE_APPROVAL_PENDING_BATCH` (existing, additive, non-schema state per D-015's own pattern) becomes reachable from a live caller for the first time.
authority impact: none — no approval policy, tool permission, or dispatch decision is made or changed by rendering.
shared identifiers: `STATE_APPROVAL_PENDING_BATCH`, `_render_approval_pending_batch()` — both already exist (PR1); this migration is their first live wiring, not a redefinition.
invariants: `UNIFIED_MESSAGE_UX_STANDARD.md` principles hold (success only with verified evidence — n/a here, pending states never claim success; missing/unsafe data falls back to a neutral message, already true of `_render_approval_pending_batch()`'s empty-rows branch).
failure semantics: same off/shadow/on fail-safe pattern as D-016 — a formatter exception must fall back to the legacy text, never break the reply.
observability: reuses `_log_shadow_comparison()`/`_shadow_leak_flags()` unmodified, per the Cross-Layer Authority Contract's explicit prohibition on parallel logging mechanisms.
cross-layer tests: `test_agent_message_formatter.py`'s existing `_render_approval_pending_batch()` coverage stays green (no renderer signature change anticipated beyond the count=1 fix in §5.4, which needs its own new test); `test_bug141_pending_query_dispatch_order.py`'s two fingerprint assertions (§5.5) must be redesigned, not merely updated.

### Layer 4 — Durable Atomic Approval (ActionContract)
touched: indirectly
input impact: `ActionContract.status`/`.normalized_payload` read-only, same as every prior rendering-only PR in this program (D-014/D-015/D-016).
output impact: none — no write path to `ActionContract`, `ActionContractRepository`, or `execute_with_atomic_claim()`.
authority impact: none — canonical approval-lifecycle status stays exclusively Layer 4's; `self._disambiguation[canonical_user_id] = list(live)` (the actual selection-state side effect) is explicitly unchanged by this scope (§5.1) — only the *text* describing that state changes.
shared identifiers: none new.
invariants: "no two components may independently decide success" — unaffected; this is a read-only description of existing pending state.
failure semantics: same as Layer 3 above.
observability: none new beyond Layer 3's.
cross-layer tests: existing `describe_pending_queue()`/`query_execution_status()` behavioral tests (`test_staging_23jul_findings.py`, `test_hotfix_e_shared_replay_policy.py`, `test_bug141_pending_query_dispatch_order.py`, others per §5.5) must stay green for `off` (byte-identical legacy), and gain new shadow/on coverage.

### Cross-Cutting Guard — RP5 Evidence Finalization (§1.5 of the authority contract)
applies: yes — this changes action-status/pending wording facing the user, the exact category RP5's applicability list names explicitly.
If yes: shadow-only per this scope (no live text changes while `off`), same as every prior surface in this program; `core/turn_evidence.py`/`TurnEvidenceSummary` classification is not touched or read by this scope — reused, not reimplemented, matching D-016's own boundary.

---

## 8. Non-goals (explicit, restated)

- Not a `MessageContract` schema change.
- Not a change to which flag gates this family (`FEATURE_UNIFIED_STATUS_FORMATTER`,
  still off by default).
- Not a fix to the `tool_name` fallback leak (§5.3) unless OQ4 is answered yes.
- Not a change to `self._disambiguation`/selection-state semantics — text
  only.
- Not a new PR, not a runtime code change — this document is the scope for
  one, pending the OQ1-OQ5 decisions in §6.
