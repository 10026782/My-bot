# BOSS — Unified User-Message UX Standard

Program: F52 — Unified Approval Runtime Migration and Implementation
Historical identifier: Phase 4C
Status: Planning-gate input; documentation only
Evidence baseline: `origin/main` `96cf6430ec8d6018742fdf8042f0146873071cfd` (17/07/2026)

**Erratum (27/07/2026, PR #471, `c64da20`, added by a Context Librarian metadata audit):** the "Public message API" section below anticipates PR 1 extending/adapting `ActionGateway.compose_status_reply()`/`GatewayReply` into the one channel-neutral formatter. What actually landed in PR #471 is a second, narrower canonical renderer, `ApprovalLifecycleResult` (`core/action_gateway.py`), produced by `build_approval_lifecycle_result()` and consumed by `approve_with_lifecycle_result()`/`reject_with_lifecycle_result()` — specifically for approval-lifecycle turns (queued/approved/rejected/completed/failed/multiple-pending), gated by `FEATURE_SINGLE_SPEAKER_APPROVAL_UX` (default off). It sits alongside `GatewayReply`/`compose_status_reply()` rather than replacing or being built from it; `display_payload` (`core/agent_message_formatter.py`) remains a separate, third contract for non-approval-lifecycle status turns. This document's "one public message-composition API" principle is not yet met as of `a885561d` — there are now two canonical approval-facing renderers, not one. Identifier/tool-name redaction in the new path is unconditional (BUG-118) and holds regardless of the flag.

## Scope

This standard governs only the conversion of verified internal state into text
shown to a user. It does not change approval policy, approver identity,
fingerprints, duplicate suppression, fail-closed behavior, execution, TMA, or
channel topology.

The required flow is:

```text
Internal Result -> Message Contract -> Semantic Formatter -> Channel Renderer
```

Modules must not independently turn free-form text or raw provider/tool output
into Telegram or WhatsApp action-status messages.

## Locked principles

1. Internal state and verified evidence are the source of truth. Model prose is
   never execution evidence.
2. A success message is permitted only when `execution_verified=true`.
3. Technical identifiers remain in logs and audit evidence, never in user text.
4. The same semantic message must have the same meaning on every channel.
5. Plain text is the default. Bold Markdown, raw backticks and parse-mode
   dependence are not part of the semantic contract.
6. Missing or unsafe display data produces a neutral fallback and an observable
   gap; it never causes a technical fallback such as a tool name.
7. One message contains at most one state marker.

## Public message API

F52 will expose one public message-composition API. The existing
`ActionGateway.compose_status_reply()` is the preferred extension point because
`GatewayReply` already establishes a single-speaker boundary. PR 1 must first
extract or adapt this function into a channel-neutral formatter; it must not
introduce a competing formatter.

Internal state-specific handlers or a formatter registry are allowed behind the
single public API.

## Message states

The first formatter version supports exactly seven states:

| State | Meaning | Required evidence |
|---|---|---|
| `success` | The requested business action completed | `execution_verified=true` |
| `failure` | Execution or proposal failed | Stable `reason_code`; no raw exception |
| `approval_single` | One frozen business action awaits approval | Durable contract plus safe display payload |
| `approval_batch` | Several frozen business actions await selection/approval | Durable contracts plus safe item payloads |
| `clarification` | User input is required before a safe decision | Prompt plus at most three safe choices |
| `idle` | No action is pending or being claimed | Verified absence/neutral state |
| `unverified_effect` | There is an indication that a process or side effect may have occurred, but there is not enough verified evidence to report success, normal failure, or valid approval_pending | Partial evidence plus stable `reason_code`; no success evidence |

Cancellation, rejection, expiry and unverified outcomes are failure-family
variants with distinct stable reason codes; they do not create additional public
states in formatter version 1. `unverified_effect` is the exception: RP5 needs a
distinct public state for cases where a side effect may have happened but the
system cannot truthfully classify it as success, normal failure, or valid
approval pending.

## `unverified_effect` UX rules

The formatter must treat `unverified_effect` as a manual-review state:

- never render it as success;
- never render it as normal pending approval;
- require manual review or an explicit state check before continuing;
- never suggest or trigger automatic retry;
- never expose internal IDs, tool names, payloads, credentials, raw provider
  data, raw exceptions, or model-generated success text.

This state is used when the system has enough indication to avoid pretending
"nothing happened", but not enough verified evidence to claim a completed
business result, a clean failure, or a safe approval waiting state.

## Relationship to RP5 Evidence Contract

RP5 owns evidence-derived classification and state. It decides, from backend
evidence, whether the state is `success`, `failure`, `approval_single`,
`approval_batch`, `clarification`, `idle`, `unverified_effect`, or another
internal state mapped into the public formatter contract.

The UX formatter owns final user-facing wording. RP5 example strings are backend
meaning examples, not final production copy. `format_agent_message(state,
payload)` may soften wording for clarity, channel fit, and user tone, but it may
not change truth.

The formatter must never upgrade a state:

- `approval_pending` must not become `executed`;
- `outcome_unknown` must not become `success`;
- `verified_read_only` must not become mutation success;
- `unverified_effect` must not become success or regular pending.

## Display payload

`display_payload` is the canonical structured display contract:

```json
{
  "action": "create",
  "entity_type": "lead",
  "entity_name": "דני כהן",
  "key_fields": [
    {"label": "טלפון", "value": "0501234567"}
  ],
  "count": 1,
  "items": [],
  "reason_code": null,
  "execution_verified": true,
  "occurred_at": "2026-07-17T09:30:00+03:00"
}
```

Field rules:

- `action`: `create`, `update`, `delete` or `send`.
- `entity_type`: business entity such as `lead`, `task`, `email`, `meeting`
  or `payment`.
- `entity_name`: human name when safely available.
- `key_fields`: at most two central business fields, each with a human label.
- `count`: batch count.
- `items`: human business items for a batch; never record or contract IDs.
- `reason_code`: stable registry code for non-success outcomes.
- `execution_verified`: structural evidence gate, not a text inference.
- `occurred_at`: machine timestamp rendered into a human date by the formatter.

The following are forbidden display inputs: `tool_name`, contract ID, callback
ID, record ID, UUID, Airtable table name, provider URL, token, raw exception,
and raw model success text.

## `human_summary` migration decision

`display_payload` replaces free-form `human_summary` as the canonical write
contract. During migration, legacy `human_summary` may be read only as an
untrusted compatibility hint. It:

- is never execution evidence;
- cannot enable a success state;
- is sanitized and may only contribute non-technical descriptive text;
- is ignored when a valid `display_payload` exists;
- must not be newly persisted after a producer migrates;
- is removed only after the compatibility window and coverage audit pass.

Semantic `display_payload` belongs with the frozen action facts. Channel delivery
state (message ID, callback reference, projection status and expiry) remains in
the separate presentation projection defined by F52 D-005. These are different
concerns and must not be merged.

## Sanitization and rendering

Before formatting, every display string is normalized and bounded. The
sanitizer must:

- neutralize Markdown/control characters rather than enabling parse mode;
- redact UUIDs, Airtable-style record IDs, tool names and internal URLs/tokens;
- reject or replace injected execution claims such as "הפעולה בוצעה" inside a
  field value;
- preserve Hebrew, phone numbers and human dates;
- bound field, item and total message lengths;
- tolerate missing batch items without exposing raw objects.

Channel renderers may change line wrapping and length limits only. They may not
change state, evidence requirements or business meaning.

## Canonical patterns

Examples are illustrative; the formatter owns final wording.

```text
✓ שמרתי את דני כהן (0501234567)

יש פעולה שממתינה לאישור:
יצירת ליד עבור דני כהן (0501234567)
לאשר? כן / לא

יש 3 פעולות שממתינות לאישור:
1. יצירת ליד עבור דני כהן
2. עדכון משימה: חזרה לספק
3. שליחת מייל לרונית
שלח מספר כדי לבחור.
```

Safe missing-contract fallback:

```text
יש פעולה שממתינה לאישור. חסר לי מידע כדי להציג אותה בצורה בטוחה.
```

Unverified execution fallback:

```text
לא ניתן לאמת כרגע אם הפעולה בוצעה. אין לנסות שוב עד לבדיקת המצב.
```

## Error registry baseline

Formatter decisions use stable codes rather than matching exception text:

- `GOOGLE_AUTH_REQUIRED`
- `STRUCTURED_RESULT_INVALID`
- `PERMISSION_DENIED`
- `ACTION_EXPIRED`
- `EXECUTION_NOT_VERIFIED`
- `PROVIDER_UNAVAILABLE`
- `VALIDATION_FAILED`
- `UNKNOWN_ERROR`

Adapters own exception-to-code mapping. Full exceptions remain in protected logs
and audit evidence.

## Observability

Every formatter invocation records, without adding these values to user text:

- `message_state`
- `formatter_version`
- `source_module`
- `contract_id`
- `fallback_used`
- `redaction_count`
- `error_code`
- `execution_verified`

## Acceptance gates

Content tests cover single/batch success, single/batch approval, mapped and
unknown failure, clarification with no more than three choices, and idle.
Security tests cover Markdown injection, tool/UUID injection, injected success
claims, missing/partial payloads, success without evidence, secret-bearing
exceptions, missing/large batch items, Hebrew, phone numbers and dates.

Regression tests must prove approval policy, authority, fingerprinting,
duplicate suppression, executor behavior and legacy ActionContract reads are
unchanged.
