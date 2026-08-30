# SINGLE-SPEAKER APPROVAL UX

## Program Identity

This is the refreshed continuation of the original Single-Speaker Approval UX
program established by PR #471. It unifies the original approval-turn
ownership invariant with the later deterministic-turn and MessageContract
work. It does not replace the F52, Turn Coordinator, RP5, or ActionGateway
authorities.

Relationship to the program registry: F52 / Single-Speaker Approval UX is the
implementation program/slice of `UX-01 — Unified BOSS Experience`. It preserves
`UX-01` as the canonical identity and does not replace or rename it.

Current-state rule: current status and phase are read only from `origin/main` at
the recorded Truth Reset SHA. Open PRs, branches, local commits and drafts are
proposed/not-current evidence only. F52 is `IMPLEMENTATION_OF: UX-01`; it does
not replace UX-01, UX-01 does not replace F52, and resolved U1 is not an active
blocker. Other relationships require an explicit marker; do not infer them from
names, shared files, architecture area or chronology.

Evidence level: **DOCUMENTED / UX LANGUAGE APPROVED**. This document is a plan,
not code, deployment, or runtime verification.

## Core Invariant

```text
ONE SYSTEM → ONE CANONICAL STATE → ONE REPLY OWNER
→ ONE FINAL USER-FACING RESPONSE → ONE SEMANTIC UX CONTRACT
→ CHANNEL-SPECIFIC RENDERER ONLY
```

## Historical Foundation

### PR #471 — Single-Speaker Approval UX

PR #471 introduced the approval-lifecycle user-safe projection, Gateway-owned
final delivery when enabled, exact callback correlation, canonical rejection,
replay/stale handling, cross-chat delivery, and unconditional redaction of
internal identifiers and tool names. Telegram and WhatsApp were required to
express the same lifecycle meaning. Merge: `c64da20`.

### PR #473 — Documentation follow-up

PR #473 recorded the PR #471 merge and rollout boundary. It did not make the
feature production-verified or authorize later deterministic work.

### PR #492 — Original PR2

PR2 was titled “Deterministic Approval Cost Cuts”, but that title describes the
rollout vehicle, not the complete architectural intent. Its preflight and
implementation establish a deterministic approval-turn boundary: take one
canonical ActionContracts snapshot; resolve recognized lifecycle requests
before Session, Router, Business Memory, and Agent work; mutate only through
ActionGateway; avoid mutation when contracts are ambiguous; stop after
`approval_queued`; and record request-local observability. Merge: `db51afc`,
with preflight PR #491 (`12e2a45`). MessageContract implementation was
explicitly outside PR2.

## What Was Superseded

| Concern | Current owner | Status |
| --- | --- | --- |
| Reply ownership | TC6 / Turn Coordinator | Merged runtime path; callback/replay coverage remains separately scoped. |
| Lifecycle truth and mutation | ActionContracts / ActionGateway | Canonical and preserved. |
| Evidence-authorized success | TC7 / RP5 | Static paths exist; enforcement/runtime status remains evidence-scoped. |
| Deterministic pre-Agent lifecycle resolution | PR2 | Implemented for recognized deterministic paths; legacy paths remain non-universal. |
| Public presentation | MessageContract family | Canonical by D-012; adapter and formatter consolidation remains incomplete. |

“Superseded” means a later owner exists; it does not erase PR2 invariants.

## Current Architecture

- **ActionContracts** — lifecycle truth and contract identity.
- **ActionGateway** — lifecycle mutation and execution, including idempotency
  and replay-safe behavior.
- **Turn Coordinator / TC6** — reply ownership and terminal-turn closure.
- **TC7 / RP5** — evidence-backed claim authorization, not lifecycle or wording.
- **MessageContract** — public presentation contract only; not lifecycle,
  authorization, or business-state authority.
- **DraftFlow / TurnResult** — deterministic workflow/result primitives, not
  global lifecycle stores or replacement authorities.

No new state store or competing source of truth is permitted.

## Unified UX Target

The channel-neutral semantic layer represents: Confirm / Cancel, Single Choice,
Multi Choice, Free Text, Review, Edit, Pending, Success, Failure, Validation
Error, Expired, Replay, No Pending, and Multiple Pending. Provider adapters may
choose controls and transport, but may not change meaning, authority, or final
reply ownership.

## Canonical UX Language Contract (R2.0)

UX Direction 1 is the canonical language for approval and review interactions:

```text
Title
→ Business details
→ Actions
```

Use minimal icons and clean business language. Do not expose record IDs,
contract IDs, tool names, table names, or transport identifiers. The canonical
actions are:

```text
✅ אשר    ✏️ ערוך    ↩️ בטל
```

Do not use X-style cancel iconography. Canonical status wording is:

| Semantic status | User-facing wording |
| --- | --- |
| Pending | `⏳ ממתין לאישור` |
| Success | `✅ <entity/action> נשמר / הושלם` |
| Failure | `⚠️ לא הושלם` |
| Expired | `⌛ פג תוקף` |
| Cancellation | `↩️ בוטל` |

Use entity-specific wording where it is clearer. A final success response is
concise but includes the exact meaningful business data persisted, for example:

```text
✅ הליד נשמר

שם: ישראל ישראלי
תחום: גיוס
אחראי: אליהו
סטטוס: חדש
```

Do not force every entity to display every stored field. Prefer fields created
or changed by the operation, plus important business context; omit low-value
metadata.

The canonical review card is:

```text
👤 ליד חדש

שם: ...
טלפון: ...
תחום: ...
מקור: ...
אחראי: ...
סטטוס: ...

[ ✅ אשר ] [ ✏️ ערוך ] [ ↩️ בטל ]
```

Tasks use the same semantic structure with task-specific business fields, and
approval prompts use the same structure with action, entity, change, and new
value. Choices use a clear prompt and provider-supported controls, with `↩️
חזרה` for return.

Telegram and WhatsApp must use the same status wording, field labels, final
meaning, reply ownership, success/failure semantics, and cancellation semantics.
Only controls, layout, provider limits, callback/reply identifiers, and
edit/send transport behavior may differ. Provider differences affect controls,
not business meaning.

## Telegram Boundary

Telegram-specific concerns are inline keyboards, `callback_data`,
transport-only callback acknowledgment, and edit/send behavior. Callback
encoding is adapter-only and user-facing content must not expose internal IDs.

## WhatsApp Boundary

WhatsApp-specific concerns are interactive reply IDs, supported buttons/lists,
provider limits, and text fallback. Current repository behavior is primarily
Twilio synchronous text/TwiML; Meta outbound is disabled/stubbed by default.
These are transport facts, not business semantics.

### R7.3 Deterministic WhatsApp text fallback grammar

R7.3 formalizes the plain-text layer over the R7.2 semantic normalizer. Before
classification, the adapter trims leading/trailing whitespace, collapses all
internal whitespace (including newlines) to single spaces, and applies
case-insensitive matching to Latin text via `casefold()`. Punctuation is not
removed or rewritten. Classification then uses exact whole-input matching
against the bounded reserved tokens for `confirm`, `edit`, and `cancel`; no
fuzzy or Agent/LLM intent inference is allowed. Any other non-empty text is
returned as semantic `text`, while missing or empty text remains `unknown`.
Provider identifiers stay inside the adapter and no lifecycle authority is
added. This is `CODE_DONE / STATIC_VERIFIED` for the implementation PR only;
it makes no runtime or deployment claim.

### R8.2 `approval_pending_query` MessageContract extension and migration

R8.2 records `approval_pending_query` as a distinct MessageContract
presentation semantic. It is not a new lifecycle state, approval event,
execution state, or synthetic ActionFact. The existing ActionContract remains
authoritative with lifecycle `pending`; its safe business description and task
metadata are the only inputs to this presentation projection. The status-query
wording therefore remains distinct from the `approval_pending` new-prompt
wording while using the canonical MessageContract renderer. Only
`ActionGateway._render_pending_query_reply()` is migrated; idle, pending-batch,
and generic legacy fallback paths remain unchanged.

Evidence level: **MERGED / STATIC VERIFIED** (`PR #1118`, merge `b31f11d`,
verified on `origin/main` `c65085b`). No deployment or runtime claim is made
here.

### R8.3 Pending-batch MessageContract migration

R8.3 migrates only the `count >= 2` pending-action presentation to the existing
`APPROVAL_PENDING_BATCH` MessageContract semantic. The source remains the
existing authoritative list of pending ActionContracts; no ActionFact is used
as business authority and no lifecycle or execution state changes. The
numbered-list wording and provider-neutral presentation remain unchanged.
The idle, singular pending-query, generic fallback, and other legacy formatter
paths remain outside this slice.

Evidence level: **MERGED / STATIC VERIFIED** (PR #1123, merge `ab38b2a`,
verified on `origin/main`). No deployment or runtime claim is made here.

### R8.4 `NO_PENDING_ACTION` MessageContract renderer and migration

R8.4 makes `NO_PENDING_ACTION` a first-class MessageContract presentation
semantic for the absence of an authoritative live pending ActionContract. It
is not a lifecycle state, execution result, or synthetic ActionFact authority.
The canonical renderer preserves the existing no-pending wording. Only
`ActionGateway._render_pending_empty_reply()` is migrated; pending-query,
pending-batch, generic fallback, and other legacy paths remain unchanged.
Any synthetic ActionFact remains shadow-only observability input.

Evidence level: **MERGED / STATIC VERIFIED** (PR #1130, merge `b9823e0`). No
deployment or runtime claim is made here.

### R8.5 Rejection/cancellation MessageContract migration

R8.5 routes the existing rejection presentation through the existing
`MessageContract` `CANCELLED` semantic. ActionContracts remain lifecycle
authority; `reject()` and all execution boundaries are unchanged. Only
`ActionGateway._render_rejection_reply()` changes presentation routing, while
off/shadow/on behavior and legacy fallback wording remain bounded.

Evidence level: **MERGED / STATIC VERIFIED** (PR #1134, merge `8b04a60`). No
deployment or runtime claim is made here.
### R8.6 Telegram inline rejection MessageContract migration

R8.6 routes the Telegram inline rejection callback's persistent final message
through the existing `CANCELLED` MessageContract presentation via the bounded
R8.5 rejection renderer. The callback acknowledgment is transport-only. The
existing ActionContract lookup, TC8 ownership claim, rejection transition,
replay handling, and final delivery boundary remain unchanged.

Evidence level: **MERGED / STATIC VERIFIED** (PR #1137, merge `a3ffa61`). No
deployment or runtime claim is made here.

### R8.7-A Gateway success-evidence handoff

R8.7-A exposes the same-turn `EvidenceResult` already produced by the
ActionGateway execution boundary through the Gateway-owned
`ApprovalLifecycleResult`. The existing `MessageContract.SUCCESS` semantic is
used only when `execution_verified=True`,
`evidence_status="verified_write_success"`, and an evidence reference is
present. Lifecycle `completed` without matching evidence remains
`OUTCOME_UNKNOWN`. The no-contract/stale callback path remains fail-closed and
separate; no lifecycle, approval, execution, or Telegram transport authority
changes.

Evidence level: **CODE_DONE / STATIC VERIFIED**. No deployment or runtime
claim is made here.

## Single Speaker Rules

1. Exactly one component owns the final user-facing response.
2. Callback acknowledgment is transport-only; the edited or sent message is
   the business response.
3. A deterministic/Gateway terminal result stops Agent continuation.
4. One lifecycle event produces no duplicate business response.
5. Formatter composition must not create a second terminal response.

## Interaction Identity

The provider-neutral model contains `interaction_type`, `action`,
draft/session/contract correlation, `field`, selected value, and a correlation
token. Telegram callback data and WhatsApp reply IDs are adapter encodings, not
new lifecycle identifiers or state stores.

## MessageContract Role

MessageContract is presentation authority only. It is not lifecycle,
authorization, or business-state authority. ActionGateway and RP5/TC7 provide
the state and evidence metadata that presentation may render.

## Original PR2 Status

PR2's deterministic resolver, single supplied live-contract snapshot,
request-local counters, anchored lifecycle grammar, and Agent-loop stop were
implemented and merged. They are not universal because legacy rollback/text
paths coexist: not every ingress is intercepted before all pre-Agent work, not
every legacy path reuses one snapshot, and legacy multiple-pending cancellation
still requires safe closure. These are explicit follow-up scope, not permission
to weaken ActionContracts or Gateway rules.

## PR #1065 Position

PR #1065 is **MERGED / STATIC VERIFIED** on `origin/main` at implementation
commit `2484f3c`. It adds Telegram Lead Draft
approve/cancel buttons while preserving `lead_sessions` as draft state,
canonical lead writing, and ActionGateway lifecycle handling. The R3.2 callback
correction is also merged at `1a42a00` (merge `bca2f33`) and keeps callback
acknowledgment transport-only while the one persistent message carries the
final business result. R4 alignment is merged/static in `3a5242d`; R4.1 optional
Lead Draft note consistency is merged/static in PR #1088 (`16e82c7`). R5's
uniformity gate found no second current uniform consumer, so R6.1 — Decision
New UX Alignment — was the next implementation slice and is now merged/static
in PR #1091 (`40bc446`). R6.2 — Decision New DraftFlow Adoption — is
CODE_DONE / STATIC_VERIFIED. No deployment or
runtime claim is made here.

### Current phase evidence at origin/main `a3ffa61`

- R3.2 — **MERGED / STATIC VERIFIED** (`1a42a00`, merge `bca2f33`).
- R4 — **MERGED / STATIC VERIFIED** (`3a5242d`, including PR #1065 alignment).
- R4.1 — **MERGED / STATIC VERIFIED** (PR #1088, `16e82c7`; optional Lead
  Draft note consistency).
- R5 gate — **GATE_COMPLETE / NO NEW ABSTRACTION JUSTIFIED**: only one current
  uniform consumer was proven before R6.1; the post-R6.1 gate enabled reuse of
  the existing DraftFlow primitive.
- R6.1 — **MERGED / STATIC VERIFIED** (PR #1091, `40bc446`; Decision New UX
  alignment).
- R6.2 — **MERGED / STATIC VERIFIED** (PR #1093, `13a3275`): Decision New
  adopts DraftFlow while retaining Decision-owned state, callbacks, persistence,
  and receipts. The F52/UX-01 program remains `IN_PROGRESS`.
- R6.3 — **MERGED / STATIC VERIFIED**: `/update` independently proves the
  six-stage lifecycle; DraftFlow adoption is intentionally deferred pending
  the post-milestone uniformity gate.
- R6.4 — **MERGED / STATIC VERIFIED**: `/update` adopts the existing
  DraftFlow primitive while preserving its state, writer, callbacks, and receipts.
- R6.5 — **MERGED / STATIC VERIFIED**: `/marketing_new` now keeps its
  Marketing-owned pending state through review/edit and crosses the existing
  demand-and-ideas execution boundary only after explicit confirmation. DraftFlow
  adoption remains out of scope.
- R6.6 — **MERGED / STATIC VERIFIED**: `/marketing_new` adopts the existing
  DraftFlow transition/parser through a Marketing-owned dynamic adapter. State,
  validation, execution, callbacks, review rendering, and receipts remain
  Marketing-owned.
- R8.2 — **MERGED / STATIC VERIFIED** (PR #1118, `b31f11d`):
  `approval_pending_query` is a
  distinct MessageContract presentation semantic; the existing pending
  ActionContract remains lifecycle authority, and only the status-query path
  is migrated. No deployment or runtime claim is made.

- R8.3 — **MERGED / STATIC VERIFIED** (PR #1123, `ab38b2a`): the multi-pending
  batch presentation uses the existing `APPROVAL_PENDING_BATCH`
  MessageContract semantic; other legacy paths remain unchanged. No deployment
  or runtime claim is made here.
- R8.4 — **MERGED / STATIC VERIFIED** (PR #1130, `b9823e0`): the no-pending
  presentation uses the `NO_PENDING_ACTION` MessageContract semantic through
  the canonical renderer; only the empty pending path is migrated. No
  deployment or runtime claim is made here.
- R8.5 — **MERGED / STATIC VERIFIED** (PR #1134, `8b04a60`):
  rejection/cancellation presentation uses the existing `CANCELLED`
  MessageContract semantic through the canonical renderer; lifecycle authority
  and execution remain unchanged. No deployment or runtime claim is made here.
- R8.6 — **MERGED / STATIC VERIFIED** (PR #1137, `a3ffa61`): Telegram inline
  rejection's persistent final message uses the existing `CANCELLED`
  MessageContract semantic, with a transport-only callback acknowledgment. No
  deployment or runtime claim is made here.

## Refreshed Phase Plan

Each phase is one small PR; no phase changes authority or adds a state store.

| Phase | Goal and allowed scope | Invariants | Evidence possible | Deferred |
| --- | --- | --- | --- | --- |
| R0.1 | Canonical refreshed plan and ROADMAP pointer; documentation only. | No runtime, flag, or deployment changes. | DOCUMENTED / PLAN ESTABLISHED | All implementation and runtime claims. |
| R1 | Close single-speaker ownership and callback gaps with smallest corrections. | One owner; no Agent continuation; Gateway authority. | CODE_DONE / STATIC_VERIFIED, then targeted runtime | Broad formatter migration and new controls. |
| R2 | Minimal MessageContract interaction extension and adapters. | Presentation only; no new store; no internal IDs. | CODE_DONE / STATIC_VERIFIED | Provider rendering and activation. |
| R3 | Migrate generic Telegram approvals to the shared semantic contract. | Exact correlation, replay safety, one response. | Static and channel evidence | WhatsApp controls and unrelated flows. |
| R4 | Integrate PR #1065 Lead Draft buttons after callback correction. | Cancel writes nothing; approval writes once; replay safe. | Static/merged and targeted runtime | Generic wizard abstraction. |
| R5 | Gate whether a shared field-choice primitive is justified. | No premature abstraction. | Read-only uniformity gate | Treating hypothetical migrations as current consumers. |
| R6 | Migrate eligible Telegram wizard flows, one slice at a time. | No big-bang rewrite; one response; replay safety. | Focused static/channel evidence | Unsupported provider features. |
| R6.1 | Align the existing Decision New flow with the unified UX. | Preserve canonical state, one reply owner, and existing lifecycle authority. | MERGED / STATIC VERIFIED (`40bc446`, PR #1091) | Runtime/deployment verification and broader eligible wizard slices. |
| R6.3 | Align `/update` independently to collect, edit, validate, review, confirm/cancel, and receipt. | Preserve current update state and write authority; no DraftFlow adoption yet. | MERGED / STATIC VERIFIED (`2c21af2` includes `cd7de90`) | No further R6 consumer; specialized flows remain out of scope. |
| R6.4 | Adopt the existing DraftFlow primitive for `/update`. | Preserve current update state, validation, write authority, callbacks, and receipts. | MERGED / STATIC VERIFIED (`050d8b5` includes `de930c8`) | No new generic abstraction. |
| R6.5 | Align `/marketing_new` to collect, edit, validate, review, confirm/cancel, and receipt. | Preserve Marketing-owned pending state and the existing execution boundary; no DraftFlow adoption. | MERGED / STATIC VERIFIED (`9133e7f` includes `779d430`) | Marketing-specific creative selection remains downstream. |
| R6.6 | Adopt DraftFlow mechanics for `/marketing_new`. | Preserve Marketing state ownership, dynamic field semantics, validation, execution boundary, callbacks, and receipts. | MERGED / STATIC VERIFIED (`3219ba6` includes `5dafd11`) | R6 uniform consumer set closed; no UX redesign or new abstraction. |
| R7 | Add WhatsApp interactive adapter plus text fallback. | Same semantics as Telegram; limits stay in adapter. | Static/provider tests, then runtime | Enabling outbound providers without evidence/approval. |
| R7.1 | Add the Twilio-focused WhatsApp semantic presentation adapter. | MessageContract remains the sole presentation input; controls are optional and text fallback is complete. | MERGED / STATIC VERIFIED (PR #1102, `3c45a87`) | Inbound normalization, Meta outbound, lifecycle and provider activation. |
| R7.2 | Normalize WhatsApp button/reply payloads and text into semantic actions. | Provider IDs stay adapter-local; unknown input fails closed; no lifecycle authority is added. | MERGED / STATIC VERIFIED (PR #1103, `1ff1cee`) | Correlation/replay policy, Meta outbound activation, lifecycle changes. |
| R7.3 | Formalize deterministic WhatsApp plain-text fallback grammar over the existing R7.2 semantic normalizer. | Exact normalized reserved-token matches only; all other non-empty input remains `text`; no fuzzy intent inference or lifecycle authority. | MERGED / STATIC VERIFIED (PR #1111, `85cd048`) | Provider activation, lifecycle changes, and broader F52 formatter work. |
| R8 | Consolidate duplicate formatter paths behind MessageContract. | One public presentation contract and one response. | Regression/static, then canary | Lifecycle or authorization redesign. |
| R8.2 | Add `approval_pending_query` as a distinct MessageContract presentation semantic and migrate the single status-query path. | Lifecycle remains `pending`; ActionContract remains authority; no synthetic ActionFact business input; other legacy paths unchanged. | MERGED / STATIC VERIFIED (PR #1118, `b31f11d`) | Idle, pending-batch, fallback migration and runtime/deployment verification. |
| R8.3 | Migrate the multi-pending batch presentation through the existing `APPROVAL_PENDING_BATCH` MessageContract semantic. | Existing pending ActionContracts remain authority; numbered-list semantics and off/shadow/on behavior remain bounded; other legacy paths unchanged. | MERGED / STATIC VERIFIED (PR #1123, `ab38b2a`) | Idle, singular pending-query, generic fallback, and runtime/deployment verification. |
| R8.4 | Migrate the empty pending presentation through the `NO_PENDING_ACTION` MessageContract semantic. | Absence of a live pending ActionContract remains the authority; wording is preserved; off/shadow/on behavior and all other paths remain unchanged. | MERGED / STATIC VERIFIED (PR #1130, `b9823e0`) | Pending-query, pending-batch, generic fallback, and runtime/deployment verification. |
| R8.5 | Migrate rejection/cancellation presentation through the existing `CANCELLED` MessageContract semantic. | ActionContracts remain lifecycle authority; reject/execute boundaries and off/shadow/on behavior remain unchanged. | MERGED / STATIC VERIFIED (PR #1134, `8b04a60`) | Telegram callback presentation path, generic fallback, and runtime/deployment verification. |
| R8.6 | Migrate the Telegram inline rejection callback's persistent presentation through the existing `CANCELLED` MessageContract semantic. | Callback acknowledgment is transport-only; ActionContract/TC8 authority, rejection, replay, and final delivery remain unchanged. | MERGED / STATIC VERIFIED (PR #1137, `a3ffa61`) | Runtime/deployment verification and unrelated callback paths. |
| R8.7-A | Hand off same-turn Gateway execution evidence to the approval MessageContract adapter. | Existing `SUCCESS` requires verified evidence; `completed` alone remains `OUTCOME_UNKNOWN`; no-contract fallback stays separate. | CODE_DONE / STATIC VERIFIED | Runtime/deployment verification and Telegram transport changes. |
| R9 | Close remaining non-universal PR2 paths. | One snapshot; no ambiguous mutation; no Agent continuation. | Per-path static/runtime evidence | Unrelated performance work. |
| R10 | Runtime rollout, canary, and flag decision. | Governed flags; safe rollback. | DEPLOYED / RUNTIME_VERIFIED with direct evidence | Unresolved evidence or owner decisions. |

## Migration Rules

Preserve authorization, ActionContract authority, ActionGateway execution,
idempotency, replay behavior, and rollback safety. Provider adapters do
presentation only. Do not add a new state store or duplicate lifecycle
authority.

## Runtime / Flag Rules

Keep `FEATURE_SINGLE_SPEAKER_APPROVAL_UX`,
`FEATURE_DETERMINISTIC_APPROVAL_COST_CUTS`, and
`FEATURE_UNIFIED_STATUS_FORMATTER` under the explicit rollout/evidence policy.
Code defaults, merge state, and planning documents do not prove deployment or
runtime activation.

## Completion Criteria

The program closes only when Telegram and WhatsApp share the semantic UX
contract, supported flows have universal single-speaker ownership, adapters do
presentation only, duplicate formatter paths are retired, runtime canary
evidence exists, and flag retirement is an evidence-backed owner decision.
