# PR2 — Deterministic Approval Cost Cuts: Preflight Audit

Status: AUDIT COMPLETE — IMPLEMENTATION NOT YET AUTHORIZED
Base commit: 7ee5c5bbacd063fabfbe13d9be882e4d2b2a18d8
Scope: PR2 — Deterministic Approval Cost Cuts

## Purpose and boundary

This document records the approved read-only preflight for the next approval
lifecycle stabilization scope. It is not an implementation plan authorization
and does not create implementation tasks. Runtime code, feature flags,
deployment configuration, and lifecycle state are out of scope for this PR.

The audit was performed against `origin/main` at the base commit above.

## Repository state

- PR #471, `feat(approval): enforce single-speaker lifecycle UX`, is merged.
  Its merge commit is `c64da20d776fab063396345ab293cb3aaaa8f5da`.
  `FEATURE_SINGLE_SPEAKER_APPROVAL_UX` remains default-off in
  `feature_flags.py` and `.env.example`; approval identifier redaction is
  unconditional.
- PR #479, `fix(approval-ux): business-facing wording, hide Airtable table
  names`, is merged. Its merge commit is
  `e663818ac0548bd568732b4925c35edf56af6812`.
- PR #480, `docs(f52): record D-012 owner decisions, freeze Message Contract
  Envelope V1`, is merged. Its merge commit is
  `11e58df48a2a89cc5cfccc6c419e1260ea817868`.
- The Message Contract documents are present as planning/documentation
  authority. There is no MessageContract runtime implementation in scope for
  PR2.

## Authority and owner decisions

1. PR2 requires PR1 Single-Speaker UX to be enabled. The deterministic
   rollout must not independently change final-reply ownership.
2. Terminal-contract replay requires safe correlation or a narrow, documented
   recency rule. A process-local cache alone is not a sufficient durable
   source for terminal lifecycle wording.
3. Deterministic grammar must be explicit and anchored. Do not route broad
   natural-language approximations into lifecycle mutation.
4. Metrics must cover both callback ingress and text ingress.
5. ActionContracts remains the sole lifecycle source of truth. No Session,
   EventBus, Business Memory, or metrics state may become approval lifecycle
   authority.
6. MessageContract implementation is explicitly outside PR2.

## Current call chain

The relevant text-ingress sequence on `app.py::run_agent` is currently:

```text
resolve_identity
  -> WhatsApp Lead Capture (Role.LEAD only)
  -> Session snapshot
  -> live ActionContracts lookup
  -> TurnEnvelope
  -> deterministic approval checks
  -> Router
  -> lead candidate handling
  -> Business Memory
  -> Agent
  -> ActionContract proposal
  -> approval_queued
  -> second Agent call when the PR1 flag is off
```

The desired PR2 boundary, when explicitly enabled with PR1, is:

```text
resolve_identity
  -> one canonical ActionContracts snapshot
  -> deterministic approval resolver
       -> Gateway lifecycle result and one final response
       -> otherwise, existing non-approval path
```

Telegram callback ingress already follows a separate direct path:

```text
callback -> exact ActionContract correlation -> Gateway approve/reject
         -> direct execution or durable rejection -> one terminal delivery
```

It does not call the Agent.

## Remaining defects and verified behavior

| Finding | Current state | Relevant source |
| --- | --- | --- |
| Deterministic interception starts after Lead Capture and Session work. | Remaining | `app.py::run_agent` |
| WhatsApp `Role.LEAD` may invoke inbound lead capture before approval resolution. | Remaining | `app.py::run_agent` |
| Textual confirmation reads a Session bookmark. | Remaining | `core.action_gateway.ActionGateway.route_confirmation_word` |
| Pending-status handling obtains a live list and then calls a helper that obtains it again. | Remaining | `app.py::_PENDING_QUERY_RE` branch; `ActionGateway.describe_pending_queue` |
| A queued approval can cause a second Agent call when PR1 is disabled. | Remaining | `app.py::run_agent` approval-queued loop boundary |
| `יש פעולה שממתינה?` is not covered by the current pending-query grammar. | Remaining | `app.py::_PENDING_QUERY_RE` |
| `יצרת?` is not covered by the current status-query grammar. | Remaining | `app.py::_STATUS_QUERY_PATTERNS` |
| No-pending textual rejection can fall through to the Agent. | Remaining | `ActionGateway.route_cancellation_word` |
| Multiple live contracts can be cancelled through the legacy textual reject path. | Remaining; PR2 must list and not mutate | `ActionGateway.route_cancellation_word` |
| Router precedes recognized deterministic approval resolution. | Not present | `app.py::run_agent` places Router after the current deterministic block |
| Business Memory precedes recognized deterministic approval resolution. | Not present | `memory.get_for_claude` is after the current deterministic block |
| Callback approve/reject calls the Agent. | Not present | `app.py::_handle_approval_callback_impl` |
| Textual approve/reject with exactly one live canonical contract calls the Agent. | Not present | `ActionGateway.route_confirmation_word`; `ActionGateway.route_cancellation_word` |

## Minimal implementation patch boundary

When implementation is separately authorized, keep the patch narrow:

1. Add a default-off PR2 rollout flag. It must require the PR1
   Single-Speaker UX path for activation and must not modify existing flags.
2. Add one read-only, canonical ActionContracts snapshot per recognized
   approval lifecycle turn: live contracts plus an eligible terminal result.
   Terminal replay must use exact correlation or a documented narrow recency
   rule.
3. Add an explicit, anchored deterministic grammar for callback actions,
   textual approve/reject, pending list/existence queries, and `יצרת?`.
4. Resolve recognized requests before Lead Capture, Session, Router, Business
   Memory, and the Agent. Unrecognized input continues through the existing
   path.
5. For one live contract, mutate only through the existing ActionGateway
   lifecycle entry points. For multiple live contracts, show a numbered
   disambiguation and do not mutate. Ambiguous identity fails closed.
6. Reuse the snapshot already loaded in the same ingress turn; do not make a
   second ActionContracts lookup merely to render pending status.
7. Under the PR2 rollout flag, stop the Agent loop after
   `approval_queued=true`; do not make a second Agent call.
8. Add request-local counters only: `agent_call_count`,
   `action_contract_read_count`, `final_response_count`, and
   `deterministic_path_used`. Count ActionContract repository reads at their
   repository boundary and emit one safe log without message content,
   payloads, or identifiers.

## Files likely to change when implementation is authorized

- `app.py`
- `core/action_gateway.py`
- `core/action_contract_repository.py`
- `core/approval_turn_metrics.py` (new, request-local only)
- `feature_flags.py`
- `.env.example`
- `test_pr2_deterministic_approval_cost_cuts.py` (new)
- `test_pending_contract_read_amplification.py`
- `test_session_snapshot.py`
- `test_bug141_pending_query_dispatch_order.py`
- `test_bug_approval_callback_hardening.py`
- `test_pr1_single_speaker_approval_ux.py` if needed for flag interaction and
  cross-channel parity

This list is preflight context, not a task list for this documentation PR.

## Test matrix for a separately authorized implementation

| Scenario | Agent calls | ActionContract reads | Final responses | Deterministic |
| --- | ---: | ---: | ---: | --- |
| Approve callback | 0 | bounded | 1 | yes |
| Reject callback | 0 | bounded | 1 | yes |
| Textual approve/reject, one live contract | 0 | 1 snapshot | 1 | yes |
| Pending list or existence query | 0 | 1 snapshot | 1 | yes |
| `יצרת?`: pending, completed, rejected, or none | 0 | 1 snapshot | 1 | yes |
| Repeated terminal approval/rejection | 0 | 1 snapshot | 1 | yes |
| Multiple live contracts | 0 | 1 snapshot | 1 | yes; no mutation |
| Ambiguous identity | 0 | bounded | 1 | fail closed |
| Unrelated create-action request | at most 1 | bounded | 1 | no |
| Post-approval execution | 0 | bounded | 1 | yes |

The implementation test suite must also prove zero Session and Business Memory
reads on deterministic lifecycle paths, callback/text metric coverage,
Telegram/WhatsApp semantic parity, cross-channel canonical resolution, and
one final response per turn.

## Risk and rollback

Risk is moderate. The main risks are changing Session-bookmark precedence,
classifying overly broad text as lifecycle intent, accidental duplicate final
response accounting, and changing the legacy multiple-contract cancellation
behavior.

The implementation must be guarded by a new default-off rollout flag. Turning
that flag off restores the legacy text-ingress route. No schema migration,
new lifecycle store, or data rollback should be required.

## Overlapping branches and integration caution

No open pull request was found that directly implements PR2. The following
unmerged branches overlap the likely implementation surface and must not be
silently incorporated:

- `origin/codex/staging-pm460-review-fixes-clean` (`app.py` and callback
  hardening)
- `origin/codex/pm460-drive-fail-closed`
- `origin/codex/staging-reject-callback-fix`
- `origin/codex/staging-reject-callback-fix-clean`
- `origin/claude/rp5-staging-fault-injection-v4akit` (`app.py`, dispatcher,
  and callback tests; RP5 remains outside PR2)
- local `agent/phase-4b-1b-durable-lifecycle` (ActionContract repository,
  gateway, and executor)
- local `backup/fix-bug-017-raw-state` and
  `backup/main-raw-worktree-state` (app, gateway, EventBus, and Session)

Any implementation branch must start from current `origin/main` and handle
conflicts in `app.py` and `core/action_gateway.py` explicitly.

## References

- PR #471 — Single-Speaker Approval UX
- PR #479 — approval wording and Airtable table-name redaction
- PR #480 — Message Contract foundation documentation
- `docs/architecture/CROSS_LAYER_AUTHORITY_CONTRACT_V1.md`
- `docs/architecture/f52-unified-approval-runtime/spec/MESSAGE_CONTRACT_ENVELOPE_CONTRACT_V1.md`
- `docs/architecture/f52-unified-approval-runtime/decisions/DECISION_LOG.md`
- `docs/architecture/f52-unified-approval-runtime/audits/phase-4c/CURRENT_STATE_MAP.md`
