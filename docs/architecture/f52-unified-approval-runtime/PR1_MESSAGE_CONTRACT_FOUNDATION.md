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
   This PR instead creates an isolated module and leaves `compose_status_reply()`
   untouched, because the PR-1 scope explicitly forbids changing `ActionGateway`
   behavior and requires zero runtime change. `compose_status_reply()` today
   exposes exactly what the standard forbids (raw `record_id`, `tool_name`,
   backtick markup, passive "בוצע"). A follow-up PR should route it through
   `format_agent_message()` so exactly one formatter survives.

2. **`human_summary` as a primary payload input.** The spec deprecates
   free-form `human_summary` to an untrusted compatibility hint in favor of a
   structured `display_payload`. This foundation accepts `human_summary` (plus
   `entity_name`/`business_identifier`/`fields`/`items`/`reason`/`user_options`)
   as described in the PR brief, but treats it as **sanitized descriptive text
   only** — it is never execution evidence and never enables a success state
   (the caller-supplied state is the only truth). Converging the payload shape
   onto the spec's `display_payload` is a follow-up task.

## Tests

`test_agent_message_formatter.py` — 28 checks (content + security), including:
first-person success wording, no raw-ID / no tool-name / no bold-markdown / no
raw-provider-payload leakage, approval single & batch by business summary,
clarification capped at three choices, idle short & capability-list-free,
`outcome_unknown` no-auto-retry, `unverified_effect` manual-review, and
`mixed`/`mixed_with_unknown` never collapsing into success.
