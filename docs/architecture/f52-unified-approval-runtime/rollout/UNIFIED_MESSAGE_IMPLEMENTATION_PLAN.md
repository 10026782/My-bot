# F52 — Unified Message Standard Implementation Plan

Status: Documentation-only implementation plan
Date: 17/07/2026
Depends on: `spec/UNIFIED_MESSAGE_UX_STANDARD.md` and
`audits/phase-4c/AGENT_MESSAGE_OUTPUT_MAP.md`

## Goal and non-goals

The goal is to migrate user-facing action messages to one structured,
evidence-aware composition boundary, beginning with Approval Runtime.

Approval policy, authority, fingerprinting, deduplication, fail-closed behavior,
executor ownership, TMA and business capture policy are explicitly out of
scope. This plan does not authorize production code on the research branch.

## PR sequence

### PR 0 — Documentation and output audit

- Add the UX standard.
- Add the verified output map.
- Lock the `display_payload` versus `human_summary` decision.
- Add this implementation and rollout plan.
- Make no production-code change.

Exit gate: reviewers agree on the single formatter seam, display contract,
fallback behavior and first vertical slice.

### PR 1 — Message Contract Foundation

- Add typed message state and `display_payload` structures.
- Extend/refactor `compose_status_reply()` as the one public composition API.
- Add sanitizer, date renderer and basic stable error registry.
- Keep the component disconnected from production paths.
- Add unit tests for the six states and the security matrix.

Exit gate: no bold Markdown, no tool/record/UUID leakage, no raw exception, and
no success without `execution_verified=true`.

### PR 2 — Approval Message Vertical Slice

- Persist/read `display_payload` with the frozen ActionContract facts while
  keeping presentation delivery state in the separate projection store.
- Migrate single approval, batch selection, pending list, successful approval,
  cancellation, rejection, expiry and post-approval execution failure.
- Preserve old-contract reads through the safe generic fallback.
- Add `FEATURE_UNIFIED_APPROVAL_MESSAGES=false`.
- Add authority, concurrency, cross-channel, fingerprint and dedup regression
  tests.

Exit gate: approval messages contain business entities only; callbacks use the
same ActionContract; no success precedes verified execution.

### PR 3 — Execution results and errors

- Map adapter exceptions to stable error codes.
- Route verified success, verified failure and unknown/unverified results
  through the formatter.
- Remove raw technical errors from migrated approval paths.
- Keep full exception details in protected logs/audit evidence.

### PR 4 — Gateway and Lead Capture adoption

- Route `GatewayReply` facts through the same contract.
- Migrate Tier 1/2/3 lead previews, single success and batch/mixed summaries.
- Remove duplicate same-turn success wording.
- Do not change capture decisions or write policy.

### Later incremental adoption

When a module is otherwise changed: inventory its user text, replace that text
with a message contract, route through the formatter, add regression coverage
and update the output map. Untouched modules retain their current behavior until
their own small PR.

## Feature rollout

Initial flag:

```text
FEATURE_UNIFIED_APPROVAL_MESSAGES=false
```

Activation order:

1. Unit tests.
2. Shadow rendering: compute and log metadata/diff, never send the new text.
3. Owner-only messages.
4. Telegram approval flow.
5. WhatsApp textual approval flow.
6. General approval activation.
7. Remove legacy fallback only after a defined stability window and clean
   coverage audit.

The flag controls only the approval-message vertical slice. It is not a global
switch for every system message.

## Static audit

The first enforcement version is warning-only and reports:

- `tool_name`, record IDs or UUIDs in user-message builders;
- `**` / parse-mode-dependent bold text;
- repeated state emojis;
- `str(exception)` or exception interpolation in user responses;
- success wording outside the formatter;
- raw tool/provider output sent directly to a channel.

After a migrated file reaches a clean baseline, enforcement becomes blocking
for that file only. Non-migrated files remain warnings so rollout is incremental.

## Observability

Each shadow or live composition records `message_state`, `formatter_version`,
`source_module`, log-only `contract_id`, `fallback_used`, `redaction_count`,
`error_code` and `execution_verified`.

Shadow comparison must never log secrets, full raw payloads or user-visible
technical identifiers. Metrics distinguish formatter fallback from delivery
failure.

## Required test matrix

### Content

- single and batch success;
- single and batch approval;
- mapped and unknown failure;
- clarification with at most three choices;
- idle/no-pending.

### Security and resilience

- Markdown in entity name;
- tool name or UUID in a field;
- injected execution claim in a field;
- missing and partial display payload;
- success without evidence;
- token/internal URL in exception;
- missing and oversized batch item/list;
- Hebrew, phone numbers and dates.

### Behavior preservation

- approval policy and authority unchanged;
- fingerprint and duplicate suppression unchanged;
- executor and atomic-claim behavior unchanged;
- old ActionContract remains readable;
- Telegram/WhatsApp semantic equivalence;
- no provider call from formatter or renderer.

## Rollback

Rollback disables the new presentation and returns to the existing safe legacy
display where available. It must not restore direct execution, weaken evidence
requirements or reinterpret display data as executable input. New contracts
remain readable by old code; migrated contracts without sufficient safe display
data use the generic fallback.

## Branch order

PR 0 remains on the existing F52/Phase 4C research branch and is documentation
only. After it merges, all code PRs start from updated `main` on a separate
`codex/` implementation branch. No system-wide refactor begins before PR 2 has
passed its vertical-slice gates.
