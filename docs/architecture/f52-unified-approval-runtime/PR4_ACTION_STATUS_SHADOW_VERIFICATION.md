# F52 PR 4 — Action Status Live Surface: Shadow Verification (implementation note)

Program: F52 — Unified Approval Runtime Migration and Implementation
UX source of truth: `docs/architecture/f52-unified-approval-runtime/spec/UNIFIED_MESSAGE_UX_STANDARD.md`
Status: **verification only — no runtime behavior change, no flag turned on.**

## What this PR does

This is the **first real live-surface candidate** for the F52 formatter cutover:
`ActionGateway.compose_status_reply()`, specifically the `approval_pending`
("ממתין לאישור") reply and the other status outcomes it renders
(`executed`/`completed`, `failed`, `rejected`, unrecognized).

It does two things, both scoped to that one path:

1. **Strengthens `shadow`-mode observability.** When
   `FEATURE_UNIFIED_STATUS_FORMATTER=shadow`, the legacy text is still what's
   sent to the user, but the comparison log written next to it
   (`[UnifiedStatusFormatterShadow]`) now carries only safe, structured
   fields — never the raw legacy/unified text, never a raw record id, tool
   name, contract id, or payload. See "Shadow log fields" below.
2. **Adds focused correctness tests** for `approval_pending` and for the
   outcome → state mapping (`executed`/`completed` → `success`,
   `failed`/`rejected` → `failure`-family, anything else →
   `outcome_unknown`, never `success`) — see `test_f52_status_reply_reconciliation.py`.

## What this PR does NOT do

- It does **not** set `FEATURE_UNIFIED_STATUS_FORMATTER=on` or change its
  default (`off`) anywhere. `off` remains byte-identical legacy output.
- It does **not** change `FEATURE_EVIDENCE_FINALIZER` or anything in the RP5
  evidence-classification pipeline. RP5 is not implemented here — this PR
  only prepares the WORDING path for a future evidence-derived state, exactly
  as PR1–PR3 already did.
- It does **not** change approval execution policy, `ActionGateway` execution
  behavior, the scheduler, the tool registry, or permissions.
- It does **not** touch `app.py`'s broad reply generation or the TMA/frontend.

## Why `approval_pending` specifically

`compose_status_reply()` is reached on every pending-approval reply — the
highest-traffic, highest-blast-radius status text in the bot (a user sees it
every time an action needs their confirmation). It is also the state where a
wording mistake is most dangerous: an `approval_pending` reply must never
read like the action already happened. Verifying this path first, in
`shadow` only, lets an operator collect real production comparison data
before any user-visible text changes.

## Shadow log fields

Log line: `[UnifiedStatusFormatterShadow] outcome=... mapped_state=... text_differs=... record_id_leak=... tool_name_leak=... contract_id_leak=... redaction_count=... fallback_used=... formatter_version=... legacy_len=... unified_len=...`

| Field | Meaning | Why it's safe |
|---|---|---|
| `outcome` | `fact.outcome` (`executed`/`completed`/`failed`/`pending`/`rejected`/other) | A fixed small vocabulary, not business data. |
| `mapped_state` | The canonical formatter state (`success`/`failure`/`approval_pending`/`outcome_unknown`) | Same — a fixed vocabulary name, never raw text. |
| `text_differs` | `bool` — legacy text != unified text | Boolean only; the texts themselves are never logged. |
| `record_id_leak` / `tool_name_leak` / `contract_id_leak` | `bool` — defense-in-depth re-check that the unified text (the text that would be sent if the flag were `on`) does not contain `fact.record_id` / `fact.tool_name` / `fact.contract_id` verbatim | Booleans only; the identifiers themselves are never logged, only whether they appear. |
| `redaction_count` | `int` from the formatter's own observability record (`format_agent_message_with_meta`) | A count, not the redacted content. |
| `fallback_used` | `bool` — the formatter fell back to its "unrecognized state" text | Boolean. |
| `formatter_version` | `int` | Static metadata. |
| `legacy_len` / `unified_len` | `int` — text length in characters | A count, not the text. |

If any leak flag is `True`, a second `logger.warning` line is emitted
(same safe fields only) so it's visible without raw-grepping info logs.

Nothing else is logged. In particular: no raw legacy/unified text (which may
contain lead names, phone numbers, or other business data), no
`normalized_payload`, no credentials, no internal queue/session ids.

## Recommended next operator action

**Shadow only.** Do not set `FEATURE_UNIFIED_STATUS_FORMATTER=on` as a result
of this PR. The next step is collecting real `shadow` comparison samples in
production (see checklist below), not flipping to `on`.

## When it is safe to consider `FEATURE_UNIFIED_STATUS_FORMATTER=on`

Only after all of the following:

1. `shadow` has run in production long enough to observe at least one sample
   of each outcome this path produces (`executed`/`completed`, `failed`,
   `pending`, `rejected`, and ideally one `outcome_unknown`/unrecognized case).
2. No `record_id_leak=True` / `tool_name_leak=True` / `contract_id_leak=True`
   warning has been observed in any sample.
3. `text_differs=True` samples have been spot-checked manually (compare the
   `approval_pending` unified wording against the legacy wording for a few
   real contracts) to confirm the new wording reads correctly in Hebrew and
   does not regress UX.
4. The owner has explicitly decided to proceed — this is a product/UX
   decision, not something this PR or a shadow sample count decides on its
   own.

## Rollback

Set `FEATURE_UNIFIED_STATUS_FORMATTER=off` (or unset it — `off` is the
default and the fail-closed value for any unrecognized value). This reverts
`compose_status_reply()` to byte-identical legacy text immediately; no code
change or redeploy is required.

## Operator checklist (after merge)

1. Set `FEATURE_UNIFIED_STATUS_FORMATTER=shadow` in the Render environment.
2. Create an action that requires approval (any `requires_approval=True`
   tool, e.g. a lead update outside the `self_confirm` allowlist) and leave
   it pending.
3. Verify the user still sees the legacy `⏳ ממתין לאישור: ...` text — no
   visible change.
4. In the logs, confirm a `[UnifiedStatusFormatterShadow]` line exists for
   that turn.
5. Confirm that line has `outcome=pending` and `mapped_state=approval_pending`.
6. Confirm the unified text (not logged, but verifiable by temporarily
   inspecting `ActionGateway._compose_status_reply_unified()` in a
   non-production shell if needed) would not claim success — this is also
   covered by `test_approval_pending_unified_output_never_claims_completion`.
7. Approve/execute that action.
8. Confirm the resulting `[UnifiedStatusFormatterShadow]` line has
   `outcome=executed` (or `completed`) and `mapped_state=success` — i.e.
   `executed`/`completed` maps to success only after an actual execution
   fact, never before.
9. Check that no shadow log line for any of the above contains a raw
   Airtable record id, a raw tool name, a raw contract id, or business text
   (names/phones) — only the safe fields listed above.

## Batch / multi-status scope note

`compose_status_reply(fact: ActionFact)` takes exactly one `ActionFact` and
has never represented more than one action at a time — there is no
`items`/list parameter on this path today. `approval_pending_batch`,
`mixed`, and `mixed_with_unknown` are canonical states already implemented in
`core/agent_message_formatter.py` (PR1), but nothing on the
`compose_status_reply()` path currently produces them, and this PR does not
invent batch support here. `test_compose_status_reply_represents_exactly_one_action_fact`
guards this as a structural regression check. Wiring an actual batch-status
surface through the formatter (if one exists elsewhere, e.g. disambiguation
lists) is out of scope for PR4 and left to a future PR.

## Tests

`test_f52_status_reply_reconciliation.py` (21 checks) — extends the PR2/PR3
reconciliation suite with:

- `off` remains byte-identical legacy text (unchanged from PR2/PR3).
- `shadow` still sends legacy text, including specifically for
  `approval_pending`.
- The shadow log record contains only the safe fields above, and never the
  raw legacy/unified text, business data (lead name/phone), record id, or
  tool name — for both a `success`-mapping fact and a `pending` fact.
- `pending` maps to the `approval_pending` state (via `_action_fact_to_message`).
- `approval_pending` unified output never contains a completion/success
  marker or verb (`✓`, `✅`, `הושלמ*`, `בוצע*`).
- `approval_pending` unified output never exposes `tool_name`, `record_id`,
  or `contract_id`, even when the underlying `ActionFact` carries them.
- `executed` and `completed` both map to the `success` state; `failed` maps
  to `failure`; `rejected` maps to a `failure`-family state
  (`reason_code=ACTION_REJECTED`); any other/unrecognized outcome maps to
  `outcome_unknown` and never `success` — checked outcome-by-outcome, plus a
  sweep asserting no non-`executed`/`completed` outcome ever produces
  `success`.
- A formatter exception still falls back to legacy (unchanged behavior from
  PR2, retargeted at the new `format_agent_message_with_meta` call site).
- `compose_status_reply()` remains the single status-text entry point and
  takes exactly one `ActionFact` (structural batch-scope guard).
- `FEATURE_UNIFIED_STATUS_FORMATTER` defaults to `off`.
