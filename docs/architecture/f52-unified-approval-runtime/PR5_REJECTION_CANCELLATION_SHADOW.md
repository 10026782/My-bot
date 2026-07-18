# F52 PR 5 — Rejection/Cancellation Shadow Verification (implementation note)

Program: F52 — Unified Approval Runtime Migration and Implementation
UX source of truth: `docs/architecture/f52-unified-approval-runtime/spec/UNIFIED_MESSAGE_UX_STANDARD.md`
Status: **verification only — no runtime behavior change, no flag turned on.**

## Why this PR exists

A real production log surfaced a gap PR4 didn't cover:

```
ActionContract lifecycle PATCH succeeded with status/version update
[ActionGateway] rejected: contract=... tool=airtable_update by=boss_hq:eliyahu
route_cancellation_word() returned: 🚫 הפעולה בוטלה.
```

No `[UnifiedStatusFormatterShadow]` line was ever emitted. PR4
(`PR4_ACTION_STATUS_SHADOW_VERIFICATION.md`) wired
`ActionGateway.compose_status_reply()`'s shadow logging into the
**executed**/status-query path (`_execute_contract()` /
`query_execution_status()`), but `reject()` /
`route_cancellation_word()` / `route_combined_word()`'s cancel branch
never called `compose_status_reply()` at all — every cancellation reply
was, and until this PR remained, a hardcoded legacy string with zero
`FEATURE_UNIFIED_STATUS_FORMATTER` involvement. `FEATURE_UNIFIED_STATUS_
FORMATTER=shadow` therefore had no visibility into how the unified
formatter would render this surface.

## What this PR does

Adds a new `ActionGateway._render_rejection_reply(contract, legacy_text)`
that applies the **exact same** off/shadow/on machinery PR4 already built:

- `off` (default): returns `legacy_text` unchanged, byte-identical.
- `shadow`: computes the unified text via the same
  `_compose_status_reply_unified()` / `_action_fact_to_message()` PR4 uses
  (an `ActionFact(outcome="rejected", ...)`), logs the **same**
  `[UnifiedStatusFormatterShadow]` safe-comparison record via the
  **same**, unmodified `_log_shadow_comparison()`/`_shadow_leak_flags()`,
  and still returns `legacy_text`.
- `on`: returns the unified text instead.

Nothing in `core/agent_message_formatter.py` changed. `"rejected"` continues
to map to the `"failure"` canonical state — a decision already locked in
PR1–PR3 (`_action_fact_to_message()`'s own comment: "Rejection/expiry are
failure-family variants (spec)"). This PR does not introduce a new
canonical state; it only wires an existing, already-correct mapping into a
surface that had never called it.

Wired into the two call sites where a rejection/cancellation reply is
actually returned to the user:

- `ActionGateway.route_cancellation_word()` — free-text "לא"/"בטל"/etc.
  against one or more live pending contracts.
- `ActionGateway.route_combined_word()` — "לא 1"/"בטל 2" targeted
  cancellation of one specific contract.

### Why not inside `reject()` itself

`reject()`'s return value is an internal control-flow signal three
different callers (`route_cancellation_word`'s loop, `route_disambiguation`'s
and `route_combined_word`'s sibling-closing) branch on via
`result.startswith("🚫")` to distinguish "successfully rejected" from "a
real error occurred" (contract not found, not pending, or a durable-write
failure). If `reject()` itself returned the unified text once an operator
sets the flag to `on`, that prefix check would silently break — the unified
wording never starts with `"🚫"` — a latent multi-contract correctness bug
that would only surface later, well after this PR. Rendering happens
instead at the two callers' own final, actually-user-visible return
points, exactly mirroring where `compose_status_reply()` itself is called
for the executed path (at the final reply boundary, never woven into an
internal helper). `reject()`'s own return contract is completely
untouched by this PR.

## What this PR does NOT do

- Does not touch BUG-111 lead parsing (`core/ingress_classifier.py`,
  `core/lead_candidate_handler.py`).
- Does not touch RP5 / the Evidence Finalizer in any way.
- Does not change `FEATURE_UNIFIED_STATUS_FORMATTER`'s default (`off`) or
  set it to `shadow`/`on` anywhere.
- Does not change approval execution/authority semantics, `ActionGateway`
  execution, or the tool registry.
- Does not add a new canonical formatter state.

## Paths covered

- `ActionGateway.reject()` — return contract unchanged; contributes the
  `ActionFact` the two callers below render from.
- `ActionGateway.route_cancellation_word()` — free-text single/multi cancel.
- `ActionGateway.route_combined_word()` — "לא N" targeted cancel.

## Paths explicitly NOT covered (documented, not silently missed)

- `ActionGateway.route_disambiguation()`'s **sibling**-contract rejections
  (closing other pending contracts when the user picks one by ordinal).
  These are never shown to the user on their own — only the *chosen*
  contract's `approve()` reply is returned — so there is no independent
  user-facing text to route through the formatter here.
- `app.py`'s Telegram inline-button **reject** path
  (`_handle_approval_callback_impl`'s `"reject"` branch). This is a
  separate, pre-existing legacy path that builds its own cancellation text
  directly (`f"🚫 הפעולה בוטלה: {item['label']}"`) and never calls
  `ActionGateway.reject()` / `compose_status_reply()` at all — the same gap
  the existing `BUG-BATCH-DISCARD` comment already documents for
  ActionContract sync on that path. Wiring it in would first require
  deciding whether/how this legacy button path should sync-cancel the
  matching contract at all (a bigger decision than a shadow-observability
  addition), so it is left as an explicitly documented, separate gap — see
  the in-line "F52 PR5 note" comment at that branch in `app.py`.

## Known, pre-existing wording/leak issue NOT fixed here

`route_combined_word()`'s legacy multi-pending cancel text already embeds
`contract.tool_name` directly:
`f"🚫 פעולה מספר {idx} ({contract.tool_name}) בוטלה. נשארו {remaining} פעולות ממתינות."`
This predates this PR and is intentionally **not** changed — legacy output
must stay byte-identical while the flag is `off`/default. Only the new
unified/shadow text this PR renders is guaranteed tool-name-free (verified
in tests — see below). Fixing the legacy leak itself is a separate,
future decision (part of the eventual `on` cutover, not a shadow PR).

## Shadow log fields

Same shape PR4 already established — see
`PR4_ACTION_STATUS_SHADOW_VERIFICATION.md`'s own field table. For a
rejection, a representative line looks like:

```
[UnifiedStatusFormatterShadow] outcome=rejected mapped_state=failure text_differs=True record_id_leak=False tool_name_leak=False contract_id_leak=False redaction_count=0 fallback_used=False formatter_version=1 legacy_len=15 unified_len=41
```

No raw record id, tool name, contract id, or free-form user text is ever
logged — only the same booleans/counts/state-names PR4's fields already
guarantee.

## Example unified text (illustrative, `on` mode only — never sent by default)

`format_agent_message_with_meta("failure", {"reason_code": "ACTION_REJECTED", "reason": "הפעולה נדחתה."})`
currently renders as:

> לא הצלחתי להשלים את הפעולה. הפעולה נדחתה.

This uses the **existing**, unmodified `_render_failure()` fallback path
(no new `_REASON_TEXT` entry was added) — the failure-family framing
("לא הצלחתי להשלים...") is not a perfect semantic match for a
user-*requested* cancellation (arguably reads as if the system failed,
rather than "you asked to stop and I did"), but changing that prefix is
shared code affecting every failure-family message, not scoped to this
follow-up. Recorded here as a follow-up wording refinement candidate for
whenever `on` is actually being considered for this surface — not a
blocker for shadow-mode observability, which is this PR's whole goal.

## Recommended next operator action

Same as PR4: **shadow only**. Do not set `FEATURE_UNIFIED_STATUS_FORMATTER=on`
as a result of this PR. Once shadow is enabled for the approval-pending
surface (per PR4's own checklist), the same `shadow` setting now also
produces comparison samples for cancellations — no separate flag exists
for this surface; it shares `FEATURE_UNIFIED_STATUS_FORMATTER` with PR4.

## Tests

`test_f52_pr5_rejection_shadow.py` (35 checks):

- `off` (default) — legacy text byte-identical, zero
  `[UnifiedStatusFormatterShadow]` lines, for both `route_cancellation_word()`
  and `route_combined_word()`.
- `shadow` — free-text "לא" against one pending contract emits exactly one
  safe comparison line (`outcome=rejected`, `mapped_state=failure`, all
  leak flags `False`, no raw record id/tool name/contract id in the log
  line itself); legacy text is still what's returned.
- `shadow` — "לא 1" combined cancel emits the same kind of comparison.
- `on` — cancellation text never contains a success marker (`✓`/`✅`), for
  both call sites.
- `on` — unified text contains no raw record id, tool name, or contract
  id, for both call sites (explicitly contrasted against
  `route_combined_word()`'s known legacy tool-name leak, proving the
  *unified* text specifically avoids it).
- The Telegram callback reject path is directly introspected (source-level,
  comments stripped) to confirm it calls neither `ActionGateway.reject()`
  nor `compose_status_reply()`/`_render_rejection_reply()` — i.e. it is
  genuinely separate, not silently un-covered — and that the gap is
  documented in-line in `app.py`.
- Regression: `FEATURE_UNIFIED_STATUS_FORMATTER` still defaults to `off`;
  `FEATURE_EVIDENCE_FINALIZER` (RP4/RP5) untouched, still defaults to
  `off`; `core.ingress_classifier` (BUG-111's live path) unchanged.
