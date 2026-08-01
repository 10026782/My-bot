# Reconfirmation tool_name Leak Fix — Scope V1

**Gate:** `docs/architecture/CROSS_LAYER_AUTHORITY_CONTRACT_V1.md` — MANDATORY
(Layer 4/ActionGateway, RP5 guard). Full Cross-Layer Impact Matrix in §5.

**Status:** `SCOPE ONLY — NO CODE, NO PR, NO FLAG CHANGE.` Split out of
`APPROVAL_PENDING_BATCH_MIGRATION_SCOPE_V1.md`'s OQ4 (D-017): unlike that
migration, this fix is **not** flag-gated — it changes text that is already
live in production, unconditionally, today.

---

## 1. Purpose

Fix `_describe_contract_for_reconfirmation()` (`core/action_gateway.py:847-880`)
so it never falls back to a raw `tool_name` for any of the 11
`requires_approval=True` tools (`tool_registry.py`) — mirroring the coverage
`_safe_contract_business_description()` (`core/action_gateway.py:982-1018`)
already has.

## 2. Root cause

Two separate business-description helpers exist, with different coverage:

| tool | `_safe_contract_business_description()` (used by D-014/015/016) | `_describe_contract_for_reconfirmation()` (used by lists/reconfirmation) |
|---|---|---|
| `airtable_add`/`update` | generic "הוספת/עדכון רשומה" | Lead-specific / Task-specific / generic (richer — **keep**) |
| `calendar_create_event` | "קביעת אירוע: ..." | ❌ leaks `tool_name` |
| `gmail_draft` | "הפעולה המבוקשת" (generic fallback) | ❌ leaks `tool_name` |
| `gmail_send_draft` | "שליחת הודעת דוא״ל" | ❌ leaks `tool_name` |
| `sheets_append` | "כתיבה לגיליון: ..." | ❌ leaks `tool_name` |
| `crm_mark_payment_paid` | "הפעולה המבוקשת" (generic fallback) | ❌ leaks `tool_name` |
| `media_save_to_memory` | "הפעולה המבוקשת" (generic fallback) | ❌ leaks `tool_name` |
| `send_followup`/`send_recovery` | "שליחת הודעת המשך" | ❌ leaks `tool_name` |
| `tma_write` | "הפעולה המבוקשת" (generic fallback) | ❌ leaks `tool_name` |

`_describe_contract_for_reconfirmation()`'s final line —
`return f"{contract.tool_name} / {table}" if table else contract.tool_name`
— is the only branch reached for 9 of the 11 approval-requiring tools.

## 3. Blast radius (grep-confirmed callers, none flag-gated)

- `describe_pending_queue()`'s numbered-list items (via
  `_describe_contract_for_disambiguation()`) — **live today, unconditional**.
- `describe_superseded_reason()` (Hotfix E) — **live today, unconditional**.
- `_resolve_single_contract()`'s reconfirmation prompt (`route_confirmation_word`,
  BUG-PENDING-APPROVAL-B context-poisoning safety) — **live today,
  unconditional**, directly user-facing (`"יש פעולה קודמת שממתינה לאישור: {desc}..."`).
- `_render_pending_batch_reply()` (D-017) — shadow/on only.
- `ActionResolutionEvent.action_summary` (`_emit_resolution()`) — internal
  event/audit payload; needs a one-line check whether anything downstream
  surfaces it to a user before assuming it's low-risk.

## 4. Fix

Surgical, not a rewrite: keep the Lead/Task/generic-Airtable branches in
`_describe_contract_for_reconfirmation()` exactly as they are (richer than
`_safe_contract_business_description()`'s generic version — no reason to
lose that). Replace only the final fallback line with a delegated call:

```python
# before
table = payload.get("table") or payload.get("spreadsheet_name") or ""
return f"{contract.tool_name} / {table}" if table else contract.tool_name

# after
return _safe_contract_business_description(contract)
```

Single source of truth for "what does this tool mean in business terms"
going forward — no duplicated verb-mapping table to drift out of sync.
Alternative considered and rejected: copy `_safe_contract_business_description()`'s
per-tool branches into this function too — rejected as needless duplication
of an already-tested, already-safe mapping.

## 5. Cross-Layer Impact Matrix

**Layer 1/2:** not touched — no identifiers, no code path overlap.
**Layer 3 (F52):** touched indirectly — `_render_pending_batch_reply()`
(D-017) is one of five callers; this fix makes its per-item text safe for
tools it wasn't safe for before. No `MessageState`/schema change.
**Layer 4 (ActionGateway):** touched directly — this is entirely a Layer-4
description-helper fix; no `ActionContract.status`/lifecycle/authority
change, read-only description rendering only.
**RP5 guard:** applies — action-status text shown to the user changes for
non-Airtable pending/superseded contracts; shadow/off-on precedent doesn't
apply here (this isn't flag-gated) — the change ships as soon as it merges,
so review/tests must treat it as a direct production text change, not a
shadow candidate.

## 6. Non-goals

- Not flag-gated — unlike D-014→D-017, `off`/`shadow`/`on` machinery does
  not apply; this is a direct fix to always-live text.
- Not a change to `_safe_contract_business_description()` itself.
- Not a change to Lead/Task-specific branches.
- Not a change to approval logic, ownership, queue, evidence authority, or
  routing.

## 7. Tests (planned)

- Unit: `_describe_contract_for_reconfirmation()` for each of the 9
  previously-leaking tools — no raw `tool_name` in output, matches
  `_safe_contract_business_description()`'s wording.
- Regression: Lead/Task-specific branches unchanged (existing tests should
  stay green without modification).
- Integration: `describe_pending_queue()`'s list, `describe_superseded_reason()`,
  and `_resolve_single_contract()`'s reconfirmation prompt each produce
  leak-free text for a non-Airtable pending contract.
