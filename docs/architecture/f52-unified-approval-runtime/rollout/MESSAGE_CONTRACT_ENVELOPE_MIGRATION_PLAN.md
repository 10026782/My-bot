# Message Contract Envelope — Migration Plan

Program: F52 — Unified Approval Runtime Migration and Implementation
Authority: `spec/MESSAGE_CONTRACT_ENVELOPE_CONTRACT_V1.md` (frozen contract),
`decisions/DECISION_LOG.md` D-012 (owner decisions).
Status: **planning only — no PR in this sequence is authorized to merge by
this document.** Each PR still requires its own review/approval when actually
implemented.

Per D-012 decision 4, PR B and PR C are never combined, and no PR in this
sequence changes final wording (`core/agent_message_formatter.py`'s rendered
text stays byte-identical throughout).

---

## PR A — MessageContract envelope (foundation)

**Scope:**
- `MessageContract` and `DisplayPayload` dataclasses (`spec/
  MESSAGE_CONTRACT_ENVELOPE_CONTRACT_V1.md` §2) — `DisplayPayload` is byte-
  identical to PR1's existing `display_payload` shape, no new fields.
- Closed `MessageState` registry (§4, 15 states, including
  `approval_pending_batch`/`mixed`/`mixed_with_unknown` per decision 3).
- `build_message_contract()` pure builder (§9) implementing the precedence
  table (§6) and no-upgrade policy (§8).
- Schema versioning (`version` field, §11) and observability metadata (§10).
- A thin wrapper that calls `format_agent_message(contract.state,
  contract.display_payload)` — i.e. `MessageContract` becomes constructible
  and log-observable, and can already drive the existing formatter, without
  any adapter for `ApprovalLifecycleResult`/`ActionFact` yet.

**Explicitly out of scope for PR A:**
- No change to `core/agent_message_formatter.py` wording, states, or
  redaction behavior.
- No adapter from `ApprovalLifecycleResult` or `ActionFact` (PR B/PR C).
- No change to `ActionContract`, `ActionContractRepository`, `tool_registry.py`,
  `tools/dispatcher.py`, or any Layer 4 code.
- No flag activation — `MessageContract` is constructible and testable, not
  wired into `app.py`/Telegram/WhatsApp.

**Proof-of-non-impact obligations (per `CROSS_LAYER_AUTHORITY_CONTRACT_V1.md`
§5), to be produced at PR-A time, not assumed here:**
- grep evidence that no PR-A file imports `core/action_gateway.py`,
  `core/action_contract_repository.py`, or `tool_registry.py`.
- `test_agent_message_formatter.py` and
  `test_agent_message_formatter_display_payload.py` pass unmodified,
  before and after.
- No new import from `core/action_gateway.py` into
  `core/agent_message_formatter.py` or vice versa.

**Acceptance:** see `spec/MESSAGE_CONTRACT_ENVELOPE_CONTRACT_V1.md` §12 and the
prior spec turn's proposed test matrix (builder purity, no-upgrade, mapping
table coverage, forbidden-field fuzzing, missing-data policy, unknown-state
fail-safe, `already_completed`/`already_cancelled` synthesis, observability).

---

## PR B — `ApprovalLifecycleResult` → `MessageContract` adapter

**Depends on:** PR A merged.

**Scope:**
- `from_approval_lifecycle_result()` (§9 of the contract doc).
- Maps `ApprovalLifecycleResult.canonical_state` (+ its `repeated` context)
  into the closed `MessageState` registry per §6's precedence table,
  including the `already_completed`/`already_cancelled` synthesis (the
  contract doc's §6 row 2b) since today's `build_approval_lifecycle_result()`
  only carries this distinction via a boolean, not a distinct
  `canonical_state`.
- Preserves `ApprovalLifecycleResult`'s existing single-speaker guarantees
  (`is_final`, `should_remove_keyboard`, `final_response_required`,
  `final_response_count`) and callback-delivery behavior unchanged —
  `approve_with_lifecycle_result()`/`reject_with_lifecycle_result()` and
  `FEATURE_SINGLE_SPEAKER_APPROVAL_UX` are not modified.
- `contract_id` is dropped before reaching `DisplayPayload`; it may only ever
  reach `evidence_ref` if the evidence authority itself supplies it there
  (decision 5) — the adapter does not promote it there on its own.

**Explicitly out of scope for PR B:**
- No `GatewayReply`/`ActionFact` migration (that is PR C).
- No change to `core/action_gateway.py`'s `ActionContract`,
  `build_approval_lifecycle_result()`, or the approval flow itself.

**Acceptance:** adapter round-trip tests proving no `contract_id` leak into
`DisplayPayload`; regression proof that `FEATURE_SINGLE_SPEAKER_APPROVAL_UX`
behavior (single-speaker, keyboard removal, final-response counting) is
byte-identical before/after.

---

## PR C — `ActionFact` / `GatewayReply` → `MessageContract` adapter

**Depends on:** PR A merged. Independent of PR B (may land before or after,
but never in the same PR as B).

**Scope:**
- `from_action_fact()` (§9 of the contract doc), mapping `ActionFact.outcome`
  (`"executed" | "failed" | "pending" | "rejected"`) through the same §6
  precedence table used by the builder and by PR B's adapter.
- Deprecates **direct** formatter access from the `ActionFact`/`GatewayReply`
  surface — i.e. call sites that today go straight from `ActionFact` to
  `compose_status_reply()`'s rendered text are pointed at the new adapter +
  `format_agent_message()` path instead. `compose_status_reply()` itself is
  not deleted in this PR (that is a later, separately-authorized cutover,
  mirroring how `FEATURE_UNIFIED_STATUS_FORMATTER`'s `off`/`shadow`/`on`
  staged rollout was done for the PR1 reconciliation, per
  `PR1_MESSAGE_CONTRACT_FOUNDATION.md`).

**Explicitly out of scope for PR C:**
- No change to `ApprovalLifecycleResult` (PR B's surface).
- No deletion of `compose_status_reply()`/`GatewayReply`/`ActionFact` — they
  remain valid internal contracts per D-012 decision 1.

**Acceptance:** same class of proof-of-non-impact and adapter round-trip
tests as PR B, scoped to the `ActionFact`/`GatewayReply` surface.

---

## Sequencing summary

```
PR A (envelope, no adapters, no wording change)
   │
   ├──▶ PR B (ApprovalLifecycleResult adapter)     ── independent, can be parallel
   │
   └──▶ PR C (ActionFact/GatewayReply adapter)     ── independent, can be parallel
```

Neither PR B nor PR C is a prerequisite for the other. Both require PR A.
Per D-012 decision 4, they are never merged as a single combined PR.
