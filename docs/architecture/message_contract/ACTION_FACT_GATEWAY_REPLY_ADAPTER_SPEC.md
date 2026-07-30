# ActionFact/GatewayReply to MessageContract Adapter — PR C SPEC

**Mandatory gate reference (required by `docs/architecture/CROSS_LAYER_AUTHORITY_CONTRACT_V1.md` §7):** this document touches Layer 4 (Durable Atomic Approval — `ActionFact`/`GatewayReply` live in `core/action_gateway.py`, explicitly reserved to Layer 4 per that contract's §1/§3/§4) and the F52/Message Contract surface. It opens with this reference per the contract's standing rule and includes the full Cross-Layer Impact Matrix at §11. `APPROVAL_LIFECYCLE_RESULT_ADAPTER_SPEC.md` (PR B) omitted this reference; this SPEC does not repeat that gap.

**Status:** `PLANNING GATE — PROCEED FOR PURE, UNWIRED ADAPTER ONLY`

**Baseline:** `origin/main` at `ef1ad65a588a8a9eab1ae17b3799e641be0db9b4`.

**Authority:** `docs/architecture/CROSS_LAYER_AUTHORITY_CONTRACT_V1.md`;
D-012 and D-013 in
`docs/architecture/f52-unified-approval-runtime/decisions/DECISION_LOG.md`;
`spec/MESSAGE_CONTRACT_ENVELOPE_CONTRACT_V1.md` §6/§9 (evidence/lifecycle
precedence table, `from_action_fact()` signature); the merged PR A foundation
in `core/message_contract.py`; PR B's own precedent in
`APPROVAL_LIFECYCLE_RESULT_ADAPTER_SPEC.md` and
`core/approval_lifecycle_message_adapter.py`.

This SPEC authorizes one pure adapter from the existing internal `ActionFact`
projection to the existing canonical `MessageContract`. It does not authorize
a second builder, runtime wiring, formatting, delivery, lifecycle mutation,
ownership enforcement, queue policy, RP5 integration, flags, routing, or
output changes. It does not touch `GatewayReply` or `compose_status_reply()`
at all — see §1.4.

## 1. Current-state audit

1. `core/message_contract.py` already owns the only canonical `MessageState`,
   `MessageContract`, `DisplayPayload`, validation, serialization,
   observability projection, `build_message_contract()`, and the reusable
   `_state_from_lifecycle()` precedence-table helper.
2. `core/action_gateway.py` already owns the internal frozen `ActionFact`
   (`tool_name`, `contract_id`, `outcome`, `record_id`, `error_code`,
   `raw_tool_response`) and `GatewayReply` (`text`, `fact`). `ActionFact`'s own
   docstring states it is "מבני בלבד. אין בו משפט בשפה טבעית" (structural
   only, no natural-language sentence) — it carries no business description,
   no evidence verdict, and no reply-owner field.
3. `ActionFact.outcome` is a closed, documented vocabulary of exactly four
   values: `"executed" | "failed" | "pending" | "rejected"` (the class
   docstring's own comment, confirmed unchanged against `core/action_gateway.py`
   at this baseline). This is a **strict subset** of the values
   `core/message_contract.py::_state_from_lifecycle()` already accepts
   (`pending`, `rejected`, `failed`, `approved`, `executing`, `completed`,
   `executed`, `outcome_unknown`, `draft`, `no_contract`) — `_state_from_lifecycle()`
   already implements the exact §6 precedence table for every value `ActionFact`
   can carry. The adapter therefore delegates state resolution to
   `build_message_contract(lifecycle_state=fact.outcome, evidence_status=...)`
   directly, rather than building a second, parallel state-mapping table. This
   is a stronger "no competing builder" guarantee than PR B's own adapter
   (which needed its own `_message_state()` table because
   `ApprovalLifecycleResult.canonical_state`'s 10-value vocabulary is not a
   subset of `_state_from_lifecycle()`'s).
4. `ActionFact` carries no evidence verdict, no `evidence_ref`, and no
   `execution_verified` flag. The one already-wired existing consumer,
   `ActionGateway._action_fact_to_message()` (`core/action_gateway.py:2804-2825`,
   used only by `_compose_status_reply_unified()` under
   `FEATURE_UNIFIED_STATUS_FORMATTER`), maps `outcome in ("completed",
   "executed")` straight to `"success"` **unconditionally** — it does not
   require or check any evidence verdict. This SPEC's adapter is deliberately
   **more conservative** than that existing wired path: because
   `_state_from_lifecycle()` treats an `executed` outcome without a matching
   `evidence_status` as `outcome_unknown`, not `success` (§6 row 9, "conservative
   default — completion without any evidence is never assumed success"), the
   new adapter can never produce `success` unless the caller explicitly
   supplies matching verified evidence (`evidence_status` **and**
   `execution_verified=True` together — `MessageContract.__post_init__` itself
   independently enforces this pairing and raises otherwise). This is the
   direct implementation of the "no success without evidence" requirement.
5. `ActionFact.error_code` is a stable, structured, machine-readable code
   (never raw exception text — confirmed by `core/agent_message_formatter.py`'s
   `_REASON_TEXT` dict, which already looks failure reason codes up by this
   same vocabulary). It is safe to forward as `MessageContract.reason_code`
   for a `failed` outcome without any text inference. For a `rejected`
   outcome, the existing wired `_action_fact_to_message()` already assigns the
   fixed structured constant `"ACTION_REJECTED"` (never derived from text) —
   the adapter reuses the identical constant for consistency, not a new
   invention.
6. `ActionFact` carries no business description field at all (unlike
   `ApprovalLifecycleResult.safe_business_description`). The one existing
   wired consumer derives a description by looking up the `ActionContract`
   through `self._ledger.find_by_id(fact.contract_id)` and calling
   `_safe_contract_business_description(contract)` — this requires I/O and
   gateway/ledger state, which a pure, stateless adapter must not perform
   (`core/message_contract.py`'s own module docstring: "This module ... performs
   no I/O, reads no runtime state"). The adapter therefore accepts an explicit,
   already-safe `description: str | None` parameter, mirroring PR B's
   `safe_business_description` copy-only pattern, generalized because
   `ActionFact` does not carry the field natively. The adapter never derives
   `description` from `fact.tool_name`, `fact.record_id`, or
   `fact.raw_tool_response`.
7. `fact.record_id`, `fact.tool_name`, `fact.contract_id`, and
   `fact.raw_tool_response` are never read by the adapter for any purpose
   other than closed-vocabulary/type validation of the structural `Protocol`.
   None of the four ever reaches `DisplayPayload` or `evidence_ref` — the same
   rule D-012 decision 5 states for `contract_id` (never derive `evidence_ref`
   from it) is extended here, explicitly, to `record_id` (a raw provider/Airtable
   identifier) and `tool_name` (an internal tool name), per
   `decision.ux_no_internal_ids`.
8. No production module imports the proposed adapter because it does not
   exist. The implementation must preserve this zero-caller boundary — same
   as PR B.

### 1.4 Why `GatewayReply`/`compose_status_reply()` are out of scope for this PR

The migration plan's PR C description also mentions "deprecates direct
formatter access from the `ActionFact`/`GatewayReply` surface" (pointing
existing `compose_status_reply()`-adjacent call sites at the new adapter).
**That wiring step is explicitly not authorized by this SPEC or performed by
this PR** — the task instructions for this PR require a pure, unwired adapter
only, with no runtime wiring and no output change, matching PR B's own
precedent exactly. `compose_status_reply()`, `_compose_status_reply_legacy()`,
`_compose_status_reply_unified()`, `_action_fact_to_message()`, and
`GatewayReply` itself remain byte-for-byte unchanged by this PR. A future,
separately authorized wiring PR would be required to point any call site at
`from_action_fact()` — not authorized here, exactly as PR B's own §13 reserved
PR C for a "later, separately specified and reviewed wiring PR."

### Classification

**ADAPT.** Keep both existing contracts and add only the D-012 reconciliation
adapter. Do not merge their responsibilities and do not create another state
registry or builder.

## 2. Contract chain — Planning Gate Rule 00

1. **Entry point:** focused tests only; no production entry point in this PR.
2. **Public API:** `from_action_fact(fact, *, description=None, evidence_status=None, execution_verified=None, occurred_at=None)`.
3. **Data contract:** an `ActionFact`-shaped immutable value plus explicit,
   structured caller-supplied evidence/description context returns the
   canonical immutable `MessageContract`.
4. **Execution point:** none; the adapter performs no write, send, update,
   lookup, formatting, or lifecycle transition.
5. **Verification point:** mapping-table (via delegation to
   `_state_from_lifecycle()`), round-trip, purity, no-prose-inference,
   no-ID-leak, no-evidence-without-success, import-boundary, no-caller, and
   unchanged regression tests.

## 3. Adapter contract

The adapter lives in a separate dependency-light module and calls the
existing `build_message_contract()` exactly once. It uses a structural typed
protocol so importing the adapter does not import `core.action_gateway` and
trigger a new runtime dependency edge — identical strategy to PR B.

```python
def from_action_fact(
    fact: ActionFactLike,
    *,
    description: str | None = None,
    evidence_status: str | None = None,
    execution_verified: bool | None = None,
    occurred_at: str | None = None,
) -> MessageContract: ...
```

The adapter validates `fact.outcome` against the closed four-value vocabulary
and rejects anything else (fail closed, mirrors PR B's unknown-`canonical_state`
rejection). It does not mutate `fact` and holds no state.

## 4. Exact state mapping

The adapter does not define its own state table. It forwards
`lifecycle_state=fact.outcome` directly into the existing, already-tested
`build_message_contract()`/`_state_from_lifecycle()` precedence chain. For
documentation purposes, the resulting mapping for `ActionFact`'s exact
four-value vocabulary is:

| `ActionFact.outcome` | Evidence supplied | `MessageState` | Reason |
|---|---|---|---|
| `pending` | irrelevant | `approval_pending` | §6 row 1; evidence is irrelevant, nothing executed yet |
| `rejected` | irrelevant | `cancelled` | §6 row 2; `ActionFact` carries no `repeated` context, so `already_cancelled` synthesis (PR B-only, see its §4) does not apply here |
| `failed` | irrelevant | `failure` | §6 row 3; terminal, evidence cannot soften a stable failure |
| `executed` | `evidence_status` in `{verified_write_success, verified_read_only}` **and** `execution_verified=True` | `success` | §6 row 5; the only path to `success` — both fields required together, or `MessageContract.__post_init__` raises |
| `executed` | `evidence_status="outcome_unknown"` | `outcome_unknown` | §6 row 6 |
| `executed` | `evidence_status="unverified_effect"` | `unverified_effect` | §6 row 7 |
| `executed` | `evidence_status in {failure, failed}` | `failure` | §6 row 8; evidence contradicting an optimistic outcome is trusted over it |
| `executed` | `evidence_status="mixed"` | `mixed` | §6 (implemented by `_state_from_lifecycle()`) |
| `executed` | `evidence_status="mixed_with_unknown"` | `mixed_with_unknown` | §6 (implemented by `_state_from_lifecycle()`) |
| `executed` | none supplied, or `"no_evidence"` | `outcome_unknown` | §6 row 9; conservative default |

Any value outside `{"executed", "failed", "pending", "rejected"}` is rejected
by the adapter before reaching `build_message_contract()` — `ActionFact`'s own
type contract never produces such a value, so this is a defensive, fail-closed
guard against a malformed or spoofed input, not a expected runtime path.

`multiple_pending` is never set — `ActionFact` and `compose_status_reply()`
represent exactly one execution fact (confirmed by
`test_f52_status_reply_reconciliation.py::test_compose_status_reply_represents_exactly_one_action_fact`,
unchanged and re-verified at this baseline); batch approval facts are the
`ApprovalLifecycleResult`/PR B surface, not this one.

## 5. Field mapping and ownership

| Target field | Source/value | Rule |
|---|---|---|
| `state` | delegated to `_state_from_lifecycle(fact.outcome, evidence_status, multiple_pending=False)` | no separate mapping table; single source of precedence logic |
| `display_payload.entity_name` | non-empty caller-supplied `description` | copy caller-supplied, already-safe structured detail; otherwise empty payload |
| `reply_owner` | fixed constant `"gateway"` | `GatewayReply`/`compose_status_reply()` is documented (`core/action_gateway.py` §15.1-15.3) as gateway-owned action-status text; no per-call ownership decision exists on `ActionFact` itself, so this is a fixed, explicit, documented constant — never inferred |
| `turn_context_source` | `TurnContextSource.LEGACY_INGRESS` | provenance of today's `ActionFact` path; no `TurnCoordinator` exists (identical to PR B) |
| `source_module` | fixed adapter source label (`core.action_fact_message_adapter`) | observability only |
| `turn_id` | `None` | never synthesize from `chat_id`/session/`contract_id`/channel IDs |
| `evidence_status` | caller-supplied, forwarded verbatim | this source (`ActionFact`) carries no evidence verdict of its own; the caller must supply it structurally |
| `evidence_ref` | `None`, always | never promote `contract_id` or `record_id` — extends D-012 decision 5 explicitly to `record_id` |
| `reason_code` | `fact.error_code` when `outcome == "failed"`; fixed constant `"ACTION_REJECTED"` when `outcome == "rejected"`; `None` otherwise | stable, structured codes only, never raw text; mirrors the existing wired `_action_fact_to_message()`'s own choices exactly |
| `execution_verified` | caller-supplied, forwarded verbatim | never derived from `raw_tool_response` |
| `occurred_at` | caller-supplied, forwarded verbatim | never derived from `raw_tool_response` |

User-safe fields are only `state` and `display_payload`; audit-only metadata
remains governed by `MessageContract`. `fact.raw_tool_response`,
`fact.record_id`, `fact.tool_name`, `fact.contract_id`, callback data, and
provider data never enter `DisplayPayload` or `evidence_ref`.

The adapter reads only `fact.outcome` and `fact.error_code` from the input
object at runtime (the remaining `Protocol` fields exist for structural
type-matching only, identical in spirit to PR B's adapter reading a subset of
`ApprovalLifecycleResultLike`'s declared fields).

## 6. Compatibility strategy

- `ActionFact`, `GatewayReply`, `compose_status_reply()`,
  `_compose_status_reply_legacy()`, `_compose_status_reply_unified()`, and
  `_action_fact_to_message()` remain byte-for-byte unchanged (see §1.4).
- `MessageContract`, `MessageState`, `DisplayPayload`, `build_message_contract()`,
  and `_state_from_lifecycle()` remain the sole canonical envelope foundation;
  no duplicate builder or registry is added.
- The adapter output round-trips through `MessageContract.to_dict()` /
  `from_dict()`.
- Unknown/out-of-vocabulary outcomes fail closed instead of falling back by
  prose.
- Existing formatter, single-speaker, callback, queue, lifecycle, routing,
  and Message Contract tests pass unchanged.
- There is no import or call from `app.py`, `core/action_gateway.py`, channel
  adapters, flags, router, queue code, or formatter code.

## 7. Non-goals

No runtime callers or production wiring; no formatting or output changes; no
modification of `ActionFact` or `GatewayReply`; no `compose_status_reply()`
rewiring (see §1.4); no TurnCoordinator; no `final_reply_owner` or Single
Speaker enforcement change; no queue, repeat-request, TTL, retention, or
legacy migration policy; no RP5/evidence lookup or classification (the caller
supplies evidence structurally; the adapter performs none); no
`ApprovalLifecycleResult` changes (PR B's surface, already merged and
untouched here); no `ActionContract` lifecycle changes; no Agent Surface
Reduction; no feature flags; no routing, adapters, channels, or execution-path
changes.

## 8. Test plan

- complete mapping coverage for all four `ActionFact.outcome` values, including
  every `executed` + evidence-status branch in §4's table;
- `executed` without matching evidence (`evidence_status`/`execution_verified`
  omitted, or only one of the pair supplied) never produces `success` — either
  `outcome_unknown` (no evidence at all) or a hard
  `MessageContractValidationError` (mismatched pairing), never a silent
  downgrade that could be mistaken for success;
- unknown/out-of-vocabulary `outcome` values are rejected;
- `description` is copied into `display_payload.entity_name` only, and an
  empty/`None` description yields an empty payload;
- `fact.tool_name`, `fact.record_id`, `fact.contract_id`, and
  `fact.raw_tool_response` never appear in serialized, user-safe, audit, or
  payload output, regardless of what they contain;
- `reason_code` mapping for `failed` (from `error_code`) and `rejected`
  (fixed `"ACTION_REJECTED"`) is exact and structured;
- JSON serialization/deserialization round-trip via `MessageContract.to_dict()`/`from_dict()`;
- input object is unchanged and repeated calls are deterministic;
- AST/import guard proves no DB, Airtable, network, Agent, gateway, router,
  lifecycle, evidence, formatter, or channel dependency;
- repository search proves zero production callers;
- existing `test_message_contract.py`,
  `test_approval_lifecycle_message_adapter.py`, formatter suites, and
  single-speaker/status-reconciliation suites remain unchanged and pass;
- `git diff --check`.

The exact unchanged regression proofs (existing `ActionFact`/`GatewayReply`
behavior must not move) are:

- `test_f52_status_reply_reconciliation.py` — every
  `compose_status_reply()`/`_action_fact_to_message()` assertion, including
  `test_single_status_text_entry_point` and
  `test_compose_status_reply_represents_exactly_one_action_fact`;
- `test_single_speaker_fallback_and_duplication.py` — the `ActionFact`/
  `compose_status_reply()` audit-trail assertions (Finding B);
- `test_f52_pr5_rejection_shadow.py` / `test_f52_pr6_pending_shadow.py` — the
  rejection/pending rendering paths that also construct `ActionFact` values;
- `test_message_contract.py` — the full PR A foundation suite, including
  `_state_from_lifecycle()`'s own coverage, which this adapter reuses without
  modification.

## 9. Rollback boundary and exact file scope

Rollback deletes the standalone adapter, its focused tests, and this SPEC. No
runtime call site, state, output, flag, queue, lifecycle, formatter, or
persisted data needs reversal.

Exact file scope:

- `docs/architecture/message_contract/ACTION_FACT_GATEWAY_REPLY_ADAPTER_SPEC.md` (new)
- `core/action_fact_message_adapter.py` (new)
- `test_action_fact_message_adapter.py` (new)

Any need to modify `core/action_gateway.py`, `core/message_contract.py`,
`app.py`, formatter code, routing, flags, or channels is a planning-gate stop
and requires a new decision.

## 10. Planning Gate answers

1. **Real problem:** yes; D-012 and the migration plan explicitly defer this
   missing adapter to PR C, independent of PR B.
2. **Already solved elsewhere:** the envelope, builder, and precedence-table
   helper (`_state_from_lifecycle()`) all exist and are reused verbatim; only
   the `ActionFact`-shaped adapter function is missing.
3. **Smallest change:** one standalone pure adapter, one test file, and this
   SPEC — no new state-mapping table, since `_state_from_lifecycle()` already
   covers `ActionFact.outcome`'s full vocabulary.
4. **Dual mechanism:** no; the adapter delegates to the sole canonical builder
   and precedence helper, and adds no state registry of its own.
5. **Bypass:** none; no runtime or execution path exists in scope.
6. **Evidence:** the source (`ActionFact`) has none of its own; the adapter
   requires the caller to supply it explicitly and structurally, and
   `MessageContract.__post_init__` independently enforces the evidence/success
   pairing regardless of what the adapter does.
7. **Business impact:** one common road for `ActionFact`-based execution
   status, preventing a second, competing presentation-mapping table from
   emerging alongside PR B's.
8. **Forward enforcement:** closed vocabulary validation, strict evidence
   pairing (enforced by the existing `MessageContract` dataclass, not
   reimplemented here), no-prose/no-ID/import/no-caller tests, and unchanged
   regressions.

Architectural gates: no infrastructure import; no tool/gate mixing; no
input-handler or precedence change; no raw input; domain-agnostic; no
write/send/state mutation.

**Planning Gate result: `PROCEED` for the exact three-file scope above.**

## 11. Cross-Layer Impact Matrix

### Layer 1 — Core Reasoning / BUG-104

- touched: not touched
- input impact: none
- output impact: none
- authority impact: none
- shared identifiers: none
- invariants: unchanged
- failure semantics: unchanged
- observability: none added
- cross-layer tests: none reference this layer
- proof: no Core Reasoning identifier (`core/leads_reasoning_projection.py`,
  `FEATURE_CORE_REASONING_LEADS_STATE`, `core/adapters/leads_adapter.py`)
  appears anywhere in the new files; `grep -rl "leads_reasoning_projection\|FEATURE_CORE_REASONING_LEADS_STATE" core/action_fact_message_adapter.py test_action_fact_message_adapter.py` returns no matches (verified before merge).

### Layer 2 — TurnCoordinator

- touched: not touched; only the existing nullable/provenance schema
  (`turn_id`, `turn_context_source`) already defined by PR A is populated
- input impact: no `TurnDecision` is read or referenced; `turn_id=None`,
  `turn_context_source=legacy_ingress` — identical posture to PR B
- output impact: none; no ownership decision or enforcement
- authority impact: none
- shared identifiers: existing `turn_id`/`reply_owner` fields only, already
  defined by PR A, not new
- invariants: no fabricated turn ID
- failure semantics: unchanged
- observability: none added beyond `MessageContract.observability_record()`,
  already defined by PR A
- cross-layer tests: none — no `TurnCoordinator` class exists (`grep -rl "class TurnCoordinator"` returns zero files, confirmed at this baseline, same finding `CROSS_LAYER_AUTHORITY_CONTRACT_V1.md` §1 layer 2 already documents)
- proof: no coordinator import, call, flag, or file diff

### Layer 3 — F52 / Message Contract

- touched: directly, through the pure adapter — this is the layer the adapter
  belongs to
- input impact: structured `ActionFact` fields (`outcome`, `error_code`) plus
  explicit caller-supplied evidence/description context → canonical envelope
- output impact: a new `MessageContract` value with zero callers; no existing
  output changes (`compose_status_reply()`'s actual text output is unchanged,
  see §1.4)
- authority impact: state mapping only, delegated entirely to the existing
  `_state_from_lifecycle()`; wording remains with the formatter, unreached by
  this PR
- shared identifiers: existing V1 state names and schema fields only; no new
  `MessageState` value is added
- invariants: `_state_from_lifecycle()`'s existing conservative-default and
  no-upgrade invariants apply unmodified; `MessageContract.__post_init__`'s
  "success requires matching verified evidence" invariant applies unmodified
- failure semantics: unknown outcome fails closed (raises
  `MessageContractValidationError`) before reaching the builder
- observability: `MessageContract.observability_record()`, already defined by
  PR A, reused unmodified
- cross-layer tests: mapping/purity/no-leak/no-competing-builder tests in
  `test_action_fact_message_adapter.py`; existing `test_message_contract.py`
  run unchanged to prove `_state_from_lifecycle()` itself is untouched

### Layer 4 — Durable Atomic Approval

- touched: indirectly, by reference only — the adapter reads `ActionFact`
  structurally (`outcome`, `error_code` only) via a `Protocol`, never imports
  `core.action_gateway`, and performs no `ActionContract`/repository read or
  lifecycle write
- input impact: none to Layer 4 itself; the adapter is a pure consumer of an
  already-constructed `ActionFact` value passed in by a future caller (not
  this PR)
- output impact: none; `ActionFact`, `GatewayReply`, `compose_status_reply()`,
  and every `ActionGateway` method remain byte-for-byte unchanged (see §1.4)
- authority impact: none; `ActionFact` remains exclusively defined and owned
  by `core/action_gateway.py` per `CROSS_LAYER_AUTHORITY_CONTRACT_V1.md` §1/§4
  ("`class ActionFact` ... שמור בלעדית לשכבה 4") — this adapter does not
  redefine it, only structurally type-matches it via `ActionFactLike`,
  identical in spirit to how PR B's `ApprovalLifecycleResultLike` referenced
  Layer 4's `ApprovalLifecycleResult` without redefining it
- shared identifiers: `contract_id`, `record_id`, `tool_name` are explicitly
  never promoted into `DisplayPayload`/`evidence_ref` (§1.7/§5)
- invariants: execution ownership and lifecycle remain unchanged; the
  "no success without evidence" invariant is stricter here than the existing
  wired `_action_fact_to_message()` path (§1.4), never weaker
- failure semantics: unchanged; the adapter has no execution path to fail
- observability: none added to Layer 4 itself
- cross-layer tests: none needed — no Layer 4 code changes
- proof: `grep -n "^from core.action_gateway\|^import core.action_gateway" core/action_fact_message_adapter.py` returns no matches (the adapter uses `typing.Protocol` only); no diff in `core/action_gateway.py`, `core/action_contract_repository.py`, or `core/action_gateway_atomic_executor.py`

### Cross-Cutting Guard — RP5 Evidence Finalization

- applies: yes, by reference only, same posture as PR B
- reasoning: this adapter's `evidence_status`/`execution_verified` parameters
  are the exact vocabulary RP4's `TurnEvidenceSummary.classification()`
  already produces (`verified_write_success`, `verified_read_only`, `failure`,
  `outcome_unknown`, `unverified_effect`, `mixed`, `mixed_with_unknown`,
  `no_evidence`) — the adapter performs no evidence lookup or classification
  itself; it only accepts an already-classified value from whatever future
  caller holds it (RP4/RP5, or none at all, in which case the conservative
  `outcome_unknown` default applies per §6 row 9). No claim/state upgrade or
  text mutation occurs. RP5 enforcement itself
  (`FEATURE_EVIDENCE_FINALIZER`) remains off/shadow-only and is not touched.

## 12. Proof of no runtime change

- all changed Python modules are new and have zero production callers;
- no diff in `app.py`, `core/action_gateway.py`, formatter, router, channels,
  queues, lifecycle, RP5, or flags;
- adapter import performs no I/O and importing it does not import
  `core.action_gateway`;
- existing output regression suites (§8) run unchanged;
- this PR makes no production-state claim.

## 13. Relationship to PR B

Independent of PR B — this PR does not modify
`core/approval_lifecycle_message_adapter.py`,
`test_approval_lifecycle_message_adapter.py`, or
`APPROVAL_LIFECYCLE_RESULT_ADAPTER_SPEC.md`. Per D-012 decision 4, PR B and PR
C are never combined into one PR; they are not combined here either. Runtime
consumption of either adapter (including the `compose_status_reply()`
rewiring described in the migration plan's PR C scope, §1.4 above) requires a
later, separately specified and reviewed wiring PR with explicit
output-compatibility and ownership evidence. Neither is authorized here.
