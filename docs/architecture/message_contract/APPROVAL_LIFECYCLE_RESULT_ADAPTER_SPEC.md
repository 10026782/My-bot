# ApprovalLifecycleResult to MessageContract Adapter — PR B SPEC

**Status:** `PLANNING GATE — PROCEED FOR PURE, UNWIRED ADAPTER ONLY`

**Baseline:** `origin/main` at `fd1d559acb419f651cec870d5c305ee08a534795`.

**Authority:** D-012 and D-013 in `docs/architecture/f52-unified-approval-runtime/decisions/DECISION_LOG.md`, Message Contract V1, its migration plan, and the merged PR A foundation in `core/message_contract.py`.

This SPEC authorizes one pure adapter from the existing internal `ApprovalLifecycleResult` projection to the existing canonical `MessageContract`. It does not authorize a second builder, runtime wiring, formatting, delivery, lifecycle mutation, ownership enforcement, queue policy, RP5 integration, flags, routing, or output changes.

## 1. Current-state audit

1. `core/message_contract.py` already owns the only canonical `MessageState`, `MessageContract`, `DisplayPayload`, validation, serialization, observability projection, and `build_message_contract()`.
2. `core/action_gateway.py` already owns the internal frozen `ApprovalLifecycleResult`. Its fields are `canonical_state`, `reply_owner`, `safe_business_description`, `safe_user_message`, `contract_id`, and four delivery/single-speaker fields.
3. `build_approval_lifecycle_result(..., repeated=False)` receives `repeated` explicitly but does not store it in `ApprovalLifecycleResult`. It changes wording only. Therefore repeated status cannot be reconstructed from the result object without parsing prose.
4. Existing call sites pass `repeated=True` from structured lifecycle/replay context. PR B must preserve that distinction as an explicit adapter argument and must never inspect `safe_user_message` to infer it.
5. `ApprovalLifecycleResult` contains no evidence verdict or evidence-authority reference. Its `contract_id` is transport correlation, not evidence. D-012 therefore requires `evidence_ref=None`, and a first-occurrence `completed` result maps conservatively to `outcome_unknown`, not `success`.
6. `safe_business_description` is already the gateway's user-safe structured description. It may be copied into `DisplayPayload.entity_name`. `safe_user_message` is final wording owned by the existing approval renderer and is not copied or parsed by the adapter.
7. No production module imports the proposed adapter because it does not exist. The implementation must preserve this zero-caller boundary.

### Classification

**ADAPT.** Keep both existing contracts and add only the D-012 reconciliation adapter. Do not merge their responsibilities and do not create another state registry or builder.

## 2. Contract chain — Planning Gate Rule 00

1. **Entry point:** focused tests or a future, separately authorized caller; no production entry point in PR B.
2. **Public API:** `from_approval_lifecycle_result(result, *, repeated=False)`.
3. **Data contract:** an `ApprovalLifecycleResult`-shaped immutable value plus an explicit boolean repeated context returns the canonical immutable `MessageContract`.
4. **Execution point:** none; the adapter performs no write, send, update, lookup, formatting, or lifecycle transition.
5. **Verification point:** mapping-table, round-trip, purity, no-prose-inference, no-ID-leak, import-boundary, no-caller, and unchanged regression tests.

## 3. Adapter contract

The adapter lives in a separate dependency-light module and calls the existing `build_message_contract()` exactly once. It uses a structural typed protocol so importing the adapter does not import `core.action_gateway` and trigger a new runtime dependency edge.

```python
def from_approval_lifecycle_result(
    result: ApprovalLifecycleResultLike,
    *,
    repeated: bool = False,
) -> MessageContract: ...
```

The adapter validates `repeated` as a real boolean and rejects unknown `canonical_state` values. It does not mutate `result` and holds no state.

## 4. Exact state mapping

| `ApprovalLifecycleResult.canonical_state` | `repeated` | `MessageState` | Reason |
|---|---:|---|---|
| `pending` | either | `approval_pending` | one live approval |
| `pending_conflict` | either | `approval_pending` | the existing action remains pending; no queue policy is introduced |
| `authorization_denied` | either | `approval_pending` | denial does not change the underlying pending lifecycle |
| `multiple_pending` | either | `approval_pending_batch` | distinct frozen V1 state |
| `approved_processing` | either | `approved_processing` | execution is not final |
| `completed` | `False` | `outcome_unknown` | no evidence exists in this source; completion alone is not success |
| `completed` | `True` | `already_completed` | explicit replay context; no new execution claim |
| `rejected` | `False` | `cancelled` | public V1 name for rejected lifecycle |
| `rejected` | `True` | `already_cancelled` | explicit replay context |
| `failed` | either | `failure` | stable failure |
| `outcome_unknown` | either | `outcome_unknown` | uncertainty is never upgraded |
| `no_contract` | either | `no_pending_action` | no live matching action |

`repeated` affects only `completed` and `rejected`. It is never derived from text and never changes pending, failure, uncertainty, or no-contract semantics.

## 5. Field mapping and ownership

| Target field | Source/value | Rule |
|---|---|---|
| `state` | table in §4 | semantic adapter mapping only |
| `display_payload.entity_name` | non-empty `safe_business_description` | copy user-safe structured detail; otherwise empty payload |
| `reply_owner` | `result.reply_owner` | data-only candidate; no owner decision or enforcement |
| `turn_context_source` | `legacy_ingress` | provenance of today's approval result |
| `source_module` | fixed adapter source label | observability only |
| `turn_id` | `None` | never synthesize from chat/session/contract/channel IDs |
| `evidence_status` | `None` | this source carries no evidence verdict |
| `evidence_ref` | `None` | never promote `contract_id` |
| `reason_code`, `execution_verified`, `occurred_at` | `None` | unavailable from this source |

User-safe fields are only `state` and `display_payload`; audit-only metadata remains governed by `MessageContract`. `safe_user_message`, `contract_id`, delivery flags, callback data, raw tool names, record IDs, and provider data never enter `DisplayPayload`.

The adapter reads only `canonical_state`, `reply_owner`, and `safe_business_description`. The four single-speaker/delivery fields remain untouched on the original object; this disconnected PR neither consumes nor changes their behavior.

## 6. Compatibility strategy

- `ApprovalLifecycleResult`, its builder, call sites, wording, callback behavior, and delivery fields remain byte-for-byte unchanged.
- `MessageContract`, `MessageState`, `DisplayPayload`, and `build_message_contract()` remain the sole canonical envelope foundation; no duplicate builder or registry is added.
- The adapter output round-trips through `MessageContract.to_dict()` / `from_dict()`.
- Unknown lifecycle states fail closed instead of falling back by prose.
- Existing formatter, single-speaker, callback, queue, lifecycle, routing, and Message Contract tests pass unchanged.
- There is no import or call from `app.py`, `core/action_gateway.py`, channel adapters, flags, router, queue code, or formatter code.

## 7. Non-goals

No runtime callers or production wiring; no formatting or output changes; no modification of `ApprovalLifecycleResult`; no TurnCoordinator; no `final_reply_owner` or Single Speaker enforcement; no queue, repeat-request, already-resolved, TTL, retention, or legacy migration policy; no RP5/evidence lookup; no `ActionFact`/`GatewayReply` adapter; no ActionContract lifecycle changes; no Agent Surface Reduction; no feature flags; no routing, adapters, channels, or execution-path changes.

## 8. Test plan

- complete parameterized mapping table, including explicit repeated synthesis;
- completed without evidence is `outcome_unknown`, never `success`;
- changing only `safe_user_message` cannot change adapter output;
- invalid/unknown canonical state and non-boolean repeated input are rejected;
- safe description is copied and empty description yields an empty payload;
- `contract_id` and wording do not appear in serialized, user-safe, audit, or payload output;
- owner/provenance/correlation/evidence fields are mapped exactly;
- JSON serialization/deserialization round-trip;
- input object is unchanged and repeated calls are deterministic;
- AST/import guard proves no DB, Airtable, network, Agent, gateway, router, lifecycle, evidence, formatter, or channel dependency;
- repository search proves zero production callers;
- existing `test_message_contract.py`, formatter suites, and single-speaker suite remain unchanged and pass;
- `git diff --check`.

## 9. Rollback boundary and exact file scope

Rollback deletes the standalone adapter, its focused tests, and this SPEC. No runtime call site, state, output, flag, queue, lifecycle, formatter, or persisted data needs reversal.

Exact file scope:

- `docs/architecture/message_contract/APPROVAL_LIFECYCLE_RESULT_ADAPTER_SPEC.md` (new)
- `core/approval_lifecycle_message_adapter.py` (new)
- `test_approval_lifecycle_message_adapter.py` (new)

Any need to modify `core/action_gateway.py`, `core/message_contract.py`, `app.py`, formatter code, routing, flags, or channels is a planning-gate stop and requires a new decision.

## 10. Planning Gate answers

1. **Real problem:** yes; D-012 and the migration plan explicitly defer this missing adapter to PR B.
2. **Already solved elsewhere:** the envelope and builder exist; they are reused. Only the adapter gap remains.
3. **Smallest change:** one standalone pure adapter, one test file, and this SPEC.
4. **Dual mechanism:** no; the adapter delegates to the sole canonical builder and adds no state registry.
5. **Bypass:** none; no runtime or execution path exists in scope.
6. **Evidence:** the source has none, so the adapter supplies none and never claims success.
7. **Business impact:** one common road for approval results, preventing later layers from inventing a parallel presentation contract.
8. **Forward enforcement:** closed mapping, strict validation, no-prose/no-ID/import/no-caller tests, and unchanged regressions.

Architectural gates: no infrastructure import; no tool/gate mixing; no input-handler or precedence change; no raw input; domain-agnostic; no write/send/state mutation.

**Planning Gate result: `PROCEED` for the exact three-file scope above.**

## 11. Cross-Layer Impact Matrix

### Layer 1 — Core Reasoning / BUG-104

- touched: no
- input/output/authority/shared identifiers: none
- invariants/failure/observability: unchanged
- proof: no Core Reasoning import, call, or file diff

### Layer 2 — TurnCoordinator

- touched: no; only existing nullable/provenance schema is populated
- input: no `TurnDecision`; `turn_id=None`, `turn_context_source=legacy_ingress`
- output/authority: none; no ownership decision or enforcement
- shared identifiers: existing `turn_id` and `reply_owner` only
- invariant/failure: no fabricated turn ID
- proof: no coordinator import, call, flag, or file diff

### Layer 3 — F52 / Message Contract

- touched: directly through the pure adapter
- input/output: structured internal approval projection → canonical envelope
- authority: state mapping only; wording remains with the formatter
- shared identifiers: existing V1 state names and schema fields
- invariant/failure: completed without evidence stays unknown; unknown state rejects
- observability/tests: fixed source/provenance, payload-free audit, mapping/purity/no-leak tests

### Layer 4 — Durable Atomic Approval

- touched: no; the existing result is read structurally only
- input/output/authority: no contract/repository read or lifecycle write
- shared identifiers: `contract_id` is explicitly dropped
- invariant/failure/observability: execution ownership and lifecycle remain unchanged
- proof: no gateway/repository/atomic executor import, call, or file diff

### Cross-Cutting Guard — RP5

RP5 is not integrated. The adapter receives no evidence input, performs no evidence lookup/classification, and maps completion without evidence to `outcome_unknown`. No claim/state upgrade or text mutation occurs.

## 12. Proof of no runtime change

- all changed Python modules are new and have zero production callers;
- no diff in `app.py`, gateway, formatter, router, channels, queues, lifecycle, RP5, or flags;
- adapter import performs no I/O and importing it does not import `core.action_gateway`;
- existing output regression suites run unchanged;
- this PR makes no production-state claim.

## 13. Next PR boundary

PR C may add the separate `ActionFact`/`GatewayReply` adapter. Runtime consumption of either adapter requires a later, separately specified and reviewed wiring PR with explicit output-compatibility and ownership evidence. Neither is authorized here.
