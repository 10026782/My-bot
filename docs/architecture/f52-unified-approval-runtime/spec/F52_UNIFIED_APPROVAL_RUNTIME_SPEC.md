# F52 — Unified Approval Runtime Migration and Implementation Specification

Historical research identifier: Phase 4C
Status: Planning-gate candidate
Implementation authority: Effective only after explicit planning-gate approval

Evidence baseline: `origin/main` `4d3787e6e6fcbc93bd5a30f62f0834136b706f06`. Final sequencing and policy require review after Phase 4B rollout verification.

## Objective

One durable runtime must own every approval-required mutation:

```text
proposal
  -> frozen ActionContract
  -> authorization / approval policy
  -> PostgreSQL execution claim
  -> dispatcher or typed deterministic handler
  -> provider evidence
  -> canonical ActionContract lifecycle
  -> channel projection / user response
```

Telegram, TMA and WhatsApp may present and parse differently. They may not differ in authorization, execution ownership, provider-success standards, or lifecycle semantics.

## Authority model

1. Airtable ActionContracts is the durable contract and lifecycle audit store.
2. PostgreSQL `action_execution_claims` is the sole execution-ownership primitive.
3. Tool Registry owns coarse tool policy (`requires_approval`, role, risk, read-only); a single typed policy evaluator may refine it from immutable proposal facts and returns `approval`, `self_confirm`, or an explicitly named future policy.
4. `ActionGateway` owns proposal dedup, authorization, lifecycle and entry into atomic execution.
5. Dispatcher/typed handler accepts approval-required execution only with gateway-created context that is verified against the live PostgreSQL claim.
6. Channel state, EventBus, Airtable Approvals, buttons, callback text and `CONTEXT_DATA` are projections. None is authority.
7. Requester and approver are distinct identities. Current role/permission is checked at action time; provider scoping uses the frozen requester.

## Interaction classifications

- **Approval:** an authorized identity other than (or allowed independently from) the requester authorizes a mutation. `approved_by` is durable.
- **Self-confirmation:** the canonical requester confirms the same frozen action and policy explicitly permits it. Current code permits this only for narrowly allowed Leads fields ([core/action_gateway.py:106](../../../../core/action_gateway.py#L106)).
- **Selection/clarification:** chooses a candidate or completes missing input. It can lead to a proposal but is never execution authorization by itself.
- **Read-only interaction:** bypasses approval runtime and cannot mutate provider/business state.
- **Notification:** outbound delivery only. If it also changes counters/status, that mutation requires its own explicit evidence/policy.

## Proposal contract

Before a channel displays an actionable approval:

1. Resolve canonical requester identity and tenant/domain authorization.
2. Resolve a registered tool or typed deterministic handler.
3. Normalize and freeze provider inputs; no later UI/session payload is executable.
4. Derive policy from the central evaluator and store its version/facts.
5. Compute business fingerprint before generating contract/idempotency IDs.
6. Perform durable duplicate lookup; unavailable persistence fails closed.
7. Persist the AC before returning an actionable presentation reference.
8. Projection creation/delivery failure leaves the AC pending and returns a non-successful presentation outcome; retry repairs presentation without creating another AC.

The existing proposal order already satisfies items 5–7 ([core/action_gateway.py:663](../../../../core/action_gateway.py#L663), [core/action_gateway.py:670](../../../../core/action_gateway.py#L670), [core/action_gateway.py:723](../../../../core/action_gateway.py#L723), [core/action_gateway.py:754](../../../../core/action_gateway.py#L754)).

## Adapter boundary

A channel adapter may:

- format a preview from display-safe contract data;
- store/deliver a presentation reference;
- parse approve/reject/selection/cancel language;
- resolve a signed/opaque reference to one immutable `contract_id`;
- call `ActionGateway.approve()` or `reject()` with the current canonical actor;
- display canonical outcome and projection-lag warnings.

It may not:

- call a provider or `dispatch_tool()` directly;
- recompute an executable payload from display text;
- treat button ownership/chat ID alone as authorization;
- mark terminal status directly;
- deserialize `CONTEXT_DATA` as execution input;
- fall back when contract/repository/claim lookup is unavailable.

TMA `_load_actionable_projection()` and `_claim_and_execute_approval()` are the closest current reference ([tma_api.py:2477](../../../../tma_api.py#L2477), [tma_api.py:2510](../../../../tma_api.py#L2510)). Telegram callback is the counterexample ([app.py:1098](../../../../app.py#L1098), [app.py:1137](../../../../app.py#L1137)).

## Presentation Projection Store

`ActionContract` is the authority and owns the frozen executable payload. Presentation state is not stored inside `ActionContract`. A separate projection store is linked by `contract_id`; it holds only channel-delivery and display state. A signed reference is a transport token only. Projection data, callback data and external message IDs are not authority and contain no executable payload.

Minimum proposed projection shape:

```text
presentation_id
contract_id
adapter
provider
canonical_recipient
external_chat_or_thread_id
external_message_id
reference_version
reference_expires_at
projection_status
created_at
updated_at
```

Canonical flow:

```text
signed reference
→ validate signature/version/TTL/action/recipient
→ load presentation projection
→ resolve canonical contract_id
→ re-read ActionContract
→ ActionGateway approve/reject
```

Forbidden flow:

```text
signed reference
→ reconstruct payload
→ dispatch
```

### Signed reference requirements

The reference logically includes `version`, `presentation_id`, `contract_id`, `action`, recipient binding, `issued_at`, `expires_at`, `key id`, and signature. Validation occurs before any execution-related call and requires action binding between approve/reject, recipient binding, TTL expiry, versioning, and key-rotation readiness. Expiry is explicit. Audit events record expired tokens, modified/invalid tokens and unsupported versions without logging executable payloads.

### Legacy compatibility invariant

The legacy compatibility layer is lookup-only.

It may resolve an existing EventBus identifier only to an already-existing canonical ActionContract.

It must never create, reconstruct, infer, repair, or persist a new contract.

Required cases:

```text
mapped EventBus ID + existing contract
→ resolve existing contract

mapped EventBus ID + missing contract
→ fail closed

unmapped EventBus ID
→ fail closed

ambiguous mapping
→ fail closed

payload appears sufficient for reconstruction
→ still do not create a contract
```

## Contract field assessment

Current AC fields are defined at [core/action_gateway.py:136](../../../../core/action_gateway.py#L136) and round-tripped by [core/action_contract_repository.py:91](../../../../core/action_contract_repository.py#L91).

| Need | Existing representation | Sufficient? |
|---|---|---|
| contract identity/version/time/status | `contract_id`, `version`, `created_at`, `updated_at`, `status` | Yes |
| requester | `tenant_id`, `canonical_user_id`, actor identity fields | Yes for current human channels |
| tenant/domain | tenant plus actor domain/allowed domains and payload metadata | Partly; domain intent is not a first-class immutable field for every handler |
| origin channel | `origin_channel`, `origin_chat_id` | Origin yes; presentation target/provider/message no |
| tool/handler and payload | `tool_name`, `normalized_inputs`, provider/table metadata | Yes for registered dispatcher tools; typed non-tool handler namespace needs definition |
| dedup/idempotency | fingerprint + idempotency key | Yes |
| policy | `requires_approval`, `approval_policy`, `trusted_source`, context flags | Yes for current policies; policy version is not explicit |
| approver | `approved_by`, `approved_at` | Yes |
| rejection | status only; no durable reject actor/time | No for audit requirement |
| provider evidence | `agent_observations` is intentionally RAM-only | No durable receipt/evidence on AC |
| projection reconstruction | origin and contract payload | Not enough to locate/edit an exact channel message after restart |
| background/system initiator | free-form/current identity fields | No uniform system principal/delegation |

### Fields justified by observed use cases

These are candidates; schema work should add only fields accepted in review.

1. **`rejected_by`, `rejected_at`**
   - Missing use case: durable Telegram/TMA rejection audit and restart truth; current reject only persists status.
   - Existing fields cannot distinguish who rejected from requester/approver.
   - Writer: `ActionGateway.reject()`; reader: audit/projection.
   - Lifecycle: set once on pending→rejected.
   - Migration: optional fields; old records remain blank.
   - Authority: canonical audit.

2. **Durable provider outcome/receipt reference** (prefer a bounded structured receipt or immutable receipt-table reference, not arbitrary provider payload)
   - Missing use case: prove which provider write justified `completed`, classify Drive-written/Airtable-failed and reconcile lifecycle persistence failure.
   - `agent_observations` is explicitly non-durable and cannot support restart audit.
   - Writer: atomic executor after evidence verification; readers: status/audit/reconciliation.
   - Lifecycle: append/set once with terminal outcome; redact secrets/personal payload.
   - Migration: additive; no backfill claim for legacy contracts.
   - Authority: canonical evidence, not UI.

3. **Presentation record outside AC, keyed by `contract_id`**
   - Missing use case: multiple channel messages/adapters, delivery state, stale callback validation and restart repair.
   - `origin_chat_id` captures proposal origin, not where an owner approval was delivered; voice/WhatsApp can originate in one channel and present in Telegram.
   - Writer: channel adapter; reader: callback/reply adapter and repair job.
   - Lifecycle: display-only rows can be replaced; canonical contract unchanged.
   - Migration: new projection table/store preferred over multiplying channel fields on AC.
   - Authority: display-only.
   - Minimum fields: `contract_id`, adapter/provider, canonical recipient, external thread/chat/message reference, delivery/update timestamps, projection state, optional signed reference version.

4. **Policy version/facts reference**
   - Missing use case: explain why an old contract was self-confirmable after policy changes and revalidate safely.
   - Existing `approval_policy` stores result but not evaluator version.
   - Writer: proposer/policy evaluator; reader: approval audit/revalidation.
   - Lifecycle: immutable.
   - Migration: additive default for new contracts; legacy uses documented version `legacy` and remains subject to current fail-closed checks.
   - Authority: canonical policy audit.

5. **System initiator/delegation reference** (defer to Phase 4C-5)
   - Missing use case: scheduler-created Tasks and bounded pre-authorized persistence need tenant, scope, policy owner and expiry.
   - A fabricated human `canonical_user_id` would be lossy and unsafe.
   - Writer: scheduler policy adapter; reader: gateway/audit.
   - Lifecycle/migration: new system proposals only; no legacy auto-replay.
   - Authority: canonical authorization input.

Do not add a domain field until the number→tenant/domain and handler-scoping decision is made; current actor domain fields may be enough for some tools. Do not store channel button labels, full personal payload or raw provider responses as authority.

## Authorization and approval

At approval time:

1. Resolve current actor from signed channel input.
2. Re-read AC from durable repository.
3. Require pending and matching tenant/presentation recipient rules.
4. Re-evaluate policy permission: `approval` requires owner or `actions.approve`; `self_confirm` requires exact canonical requester and allowed internal role ([core/action_gateway.py:1240](../../../../core/action_gateway.py#L1240)).
5. Persist approved actor/time with expected transition/version.
6. Attempt PG claim. Database unavailable/conflict never dispatches.
7. Only the acquired claimant executes frozen inputs.

Selection and clarification complete steps before proposal or select which AC enters this sequence. They cannot skip step 4.

## Execution proof and dispatcher

Every `requires_approval=True` dispatcher case must refuse an ordinary call even when role is allowed. The gateway/atomic executor must provide an execution context containing contract ID, claim execution ID and approved actor; dispatcher or a shared guard verifies the live PG claim and that tool, tenant and frozen payload correspond to the AC. A plain caller-constructed dictionary is not proof—the existing `tma_write` verification demonstrates the required distinction ([tools/approval_actions.py:239](../../../../tools/approval_actions.py#L239)).

Read-only tools and explicitly policy-exempt bounded writes should use separate typed entry points; they should not forge approval context.

## Evidence contract

A deterministic execution handler returns:

```text
ok
tool_or_handler
external_id(s)
evidence (bounded and redacted)
user_message
provider outcome classification
```

The gateway verifies tool-specific evidence before reporting success. Outcomes:

- `completed`: explicit provider success and durable canonical terminal persistence.
- `failed`: explicit no-write/failure evidence and durable status.
- `outcome_unknown`: provider effect cannot be proven; durable distinct terminal state; never automatic retry.
- persistence failure after provider success: surface an explicit audit/reconciliation error, never report ordinary success and never invite blind retry.

Multi-provider/file and bulk handlers must return per-step/per-item outcomes. One success cannot erase another unknown/failure.

## Lifecycle

Required transitions:

```text
proposal -> pending
pending -> approved -> completed | failed | outcome_unknown
pending -> rejected
```

`approved` may remain nonterminal when claim is unavailable/conflicted; it must not be shown as completed. Terminal transitions are monotonic. Expected status/version conflicts are visible. Projection updates follow canonical persistence and may lag without changing authority.

Duplicate approval reads canonical terminal status and returns the prior outcome without another provider call. `outcome_unknown` never re-enters pending. Legacy records without immutable contract ID remain read-only, drain or expire; never auto-replay.

## Presentation and compatibility

- TMA continues listing AP rows but rechecks AC actionability.
- Telegram new buttons carry AC-bound references; old EB-only buttons become stale/read-only after cutover.
- Free text searches durable live contracts by canonical user; multiple matches require deterministic presentation.
- WhatsApp uses the same contract/policy calls with its own signed reply parser and message delivery adapter.
- EventBus may publish lifecycle notifications or deliver presentation requests. It cannot store the only pending state or call execution handlers.
- Flag rollback can stop new presentations; it cannot restore direct execution.

## Non-negotiable invariants

1. No approval-required mutation without canonical authorization.
2. PostgreSQL claim is sole execution ownership.
3. Frozen requester scopes provider access; actual approver is separate.
4. Channel adapters never write providers.
5. UI/projection/`CONTEXT_DATA` never authorizes or supplies execution payload.
6. Restart preserves pending contracts and unambiguous resolution.
7. Duplicate/concurrent approval produces at most one provider execution.
8. Provider evidence precedes success; unknown remains distinct and non-retryable.
9. Internal callers cannot bypass Tool Registry approval policy.
10. Read-only/notification/bounded persistence is not forced into human approval without a concrete policy reason.

## Definition of Done for full Phase 4C

- Static caller audit finds no channel callback/provider handler that executes an approval-required mutation directly.
- Every registry approval tool refuses direct dispatcher invocation without verified live claim.
- Every mutation entry point is classified as AC-authorized, bounded pre-authorized, read-only, notification-only or disabled/unsafe; no unknown enabled path remains.
- Telegram, TMA and enabled WhatsApp paths pass authorization, tenant, restart, concurrency, stale/forged input, provider failure, receipt failure and `outcome_unknown` tests.
- All supported flag combinations fail closed; rollback does not restore fallback.
- EB and projections are provably presentation/notification only.
- Legacy records have a documented drain/expiry/read-only policy and are never replayed.
- Production verification proves one AC, one PG winner, one provider write and durable terminal lifecycle for each migrated action class.

## Acceptance matrix

### Authorization

- authorized callback;
- unauthorized callback;
- exact requester match for `self_confirm`;
- current role downgrade;
- separation of requester and approver.

### Identity and tenant

- frozen requester reaches provider;
- approver stored separately;
- cross-tenant refusal;
- cross-domain refusal;
- presentation recipient is not authority.

### Restart

- proposal in instance A;
- approval in instance B;
- same durable contract;
- no dependency on EventBus or RAM state.

### Duplicate and concurrency

- duplicate click;
- concurrent clicks;
- stale callback after terminal state;
- exactly one provider execution.

### Forgery

- unknown contract ID;
- modified signed reference;
- wrong action binding;
- wrong recipient binding;
- expired reference;
- unsupported reference version;
- forged execution context;
- direct dispatch refusal for all approval-required tools.

### Failure handling

- repository unavailable;
- PostgreSQL unavailable;
- claim conflict;
- provider explicit failure;
- receipt verification failure;
- `outcome_unknown`;
- projection delivery failure;
- projection synchronization failure.

### Flags and rollback

- every supported flag combination;
- dark deployment under disabled flag;
- no activation before full readiness;
- rollback never restores direct dispatch;
- pending contracts remain canonical.

### Callback regression

- approve/reject use the new path;
- unrelated callback families remain functional;
- the legacy fallback test is inverted deliberately, not deleted silently.
