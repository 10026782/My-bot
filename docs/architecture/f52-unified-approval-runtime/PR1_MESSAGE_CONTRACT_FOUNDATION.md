# F52 PR 1 — Message Contract Foundation (implementation note)

Program: F52 — Unified Approval Runtime Migration and Implementation
UX source of truth: `docs/architecture/f52-unified-approval-runtime/spec/UNIFIED_MESSAGE_UX_STANDARD.md`
Status: **foundation only — no runtime behavior change.**

## What this PR does

Adds the standalone semantic formatter `core/agent_message_formatter.py`, exposing:

```python
format_agent_message(state, payload) -> str
```

It converts a canonical message **state** plus a structured business **payload**
into final, plain-text, user-facing wording. It is the "Semantic Formatter"
stage of the F52 flow (`Internal Result -> Message Contract -> Semantic
Formatter -> Channel Renderer`).

## What this PR does NOT do

- It does **not** change any Telegram/WhatsApp final reply.
- It is **not** imported or wired into `app.py`, `ActionGateway`, approval logic,
  the scheduler, the tool registry, or permissions.
- It does **not** implement RP5 enforcement, and does **not** change
  `FEATURE_EVIDENCE_FINALIZER` behavior.
- It activates **no** feature flags.

Future PRs will route specific surfaces through `format_agent_message(state,
payload)` incrementally. RP5 will later provide the evidence-derived **state**;
this formatter renders that state. The two layers stay separate: **RP5 / the
Evidence Contract owns classification/state; the formatter owns wording.** The
formatter never upgrades a non-success state into success.

## Layer boundary (locked)

- Internal state and verified evidence are the source of truth; model prose is
  never execution evidence.
- The formatter renders the state it is told. It never derives, infers, or
  upgrades truth (`approval_pending`/`outcome_unknown`/`unverified_effect`/
  `mixed*` are never rendered as success).
- Technical identifiers never reach user text: record IDs, UUIDs, hex/contract
  IDs, tool names, URLs, tokens, and raw provider payload blocks are redacted
  defensively; Hebrew, phone numbers, emails, and human dates are preserved;
  ISO timestamps are rendered as `dd/mm/YYYY`.
- Output is plain text — no Markdown, at most one leading status marker, no
  per-row markers.

## States implemented

Canonical set (10), a superset of the UX standard's version-1 seven states:

`success`, `failure`, `approval_pending`, `approval_pending_batch`,
`clarification_needed`, `idle`, `outcome_unknown`, `unverified_effect`,
`mixed`, `mixed_with_unknown`.

The UX standard's names are accepted as **aliases** (`approval_single` →
`approval_pending`, `approval_batch` → `approval_pending_batch`, `clarification`
→ `clarification_needed`; `success`/`failure`/`idle`/`unverified_effect` match
directly). The three extra states (`outcome_unknown`, `mixed`,
`mixed_with_unknown`) carry the RP4/RP5 `TurnEvidenceSummary.classification()`
vocabulary so the future evidence-derived state renders without a second
translation layer. An unrecognized state falls back to a neutral, non-committal
message and is never rendered as success.

## Deliberate deviations from the spec, deferred to a follow-up PR

Two points where this foundation PR intentionally differs from the UX standard,
recorded here so a later PR reconciles them rather than leaving silent drift:

1. **Standalone module vs. adapting `ActionGateway.compose_status_reply()`.**
   The spec says PR 1 should "extract or adapt `compose_status_reply()` into a
   channel-neutral formatter … it must not introduce a competing formatter."
   PR 1 created an isolated module and left `compose_status_reply()` untouched,
   because the PR-1 scope forbade changing `ActionGateway` behavior.

   **RESOLVED (follow-up):** `compose_status_reply()` now delegates its wording
   to `format_agent_message()` behind the three-state
   `FEATURE_UNIFIED_STATUS_FORMATTER` flag (`off`/`shadow`/`on`, default `off`).
   With the flag `off` the legacy text is byte-identical to before F52;
   `shadow` computes and logs the unified text beside the legacy one but still
   sends legacy; `on` sends the unified text (dropping `record_id`/`tool_name`,
   mapping error codes to human text, first-person success). The legacy renderer
   is retained only as `_compose_status_reply_legacy()`, the flag-`off`
   fallback, and is slated for removal after the cutover. See
   `test_f52_status_reply_reconciliation.py`. There is now one canonical
   formatter; the legacy path is a bounded, flag-gated fallback, not a competing
   live formatter.

2. **`human_summary` as a primary payload input.** The spec deprecates
   free-form `human_summary` to an untrusted compatibility hint in favor of a
   structured `display_payload`. PR 1 accepted `human_summary` as sanitized
   descriptive text only (never execution evidence, never enables success).

   **RESOLVED (follow-up):** the formatter now accepts the spec's canonical
   `display_payload` field names (`action`, `entity_type`, `entity_name`,
   `key_fields`, `count`, `items`, `reason_code`, `execution_verified`,
   `occurred_at`) through a single `_normalize_payload()` mapping; the legacy
   loose names (`fields`/`reason`/`business_identifier`/`human_summary`/
   `user_options`) are accepted as a compatibility layer, canonical names
   winning. `human_summary` is now enforced as a **hint only** per the spec's
   "human_summary migration decision": it is ignored when a structured
   display_payload is present (any of `entity_name`/`key_fields`/`items`/
   `action`), and never enables success. `execution_verified=False` is never
   rendered as success (spec locked principle 2); `occurred_at` renders as a
   human `dd/mm/YYYY` date, never raw ISO. See
   `test_agent_message_formatter_display_payload.py`.

## Tests

`test_agent_message_formatter.py` — 28 checks (content + security), including:
first-person success wording, no raw-ID / no tool-name / no bold-markdown / no
raw-provider-payload leakage, approval single & batch by business summary,
clarification capped at three choices, idle short & capability-list-free,
`outcome_unknown` no-auto-retry, `unverified_effect` manual-review, and
`mixed`/`mixed_with_unknown` never collapsing into success.
