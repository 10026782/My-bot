# Message Contract Envelope Foundation — PR A SPEC

**Gate:** `docs/architecture/CROSS_LAYER_AUTHORITY_CONTRACT_V1.md` — mandatory.

**Status:** `PLANNING GATE — PROCEED FOR FOUNDATION ONLY`

**Authority:** D-012 in `docs/architecture/f52-unified-approval-runtime/decisions/DECISION_LOG.md`, the frozen `spec/MESSAGE_CONTRACT_ENVELOPE_CONTRACT_V1.md`, and owner-approved Stage 3A in `docs/architecture/multilayer/BOSS_MULTILAYER_ALIGNMENT_PLAN.md`.

This SPEC authorizes only a pure, disconnected foundation. It does not authorize runtime wiring, adapters, output changes, routing, lifecycle, ownership decisions, queue policy, RP5 integration, or feature flags.

## 1. Current-state audit

Audit baseline: `origin/main` at `55312ab2096786f2892853d8b2f6d477b6e1cf12`.

1. There is no runtime `MessageContract` class and no runtime `MessageState` enum on `main`.
2. D-012 and Message Contract V1 already define the canonical future public presentation contract. A separate Response State Contract would duplicate an approved responsibility.
3. `core/agent_message_formatter.py` already exposes a string-based `CANONICAL_STATES` renderer registry with ten values and accepts the existing `display_payload` dict shape. It is a formatter capability registry, not a typed business envelope.
4. Its vocabulary overlaps V1 but is not identical. `clarification_needed` and `idle` are legacy formatter inputs; V1 uses `needs_input` and `neutral`, and adds `approved_processing`, `cancelled`, `already_completed`, `already_cancelled`, and `no_pending_action`.
5. `ActionContract`, `ActionFact`, `GatewayReply`, and `ApprovalLifecycleResult` already exist and remain internal lifecycle/fact/result contracts. PR A does not adapt, import, mutate, or replace them.
6. `TurnEvidenceSummary.classification()` owns evidence verdicts. PR A copies a supplied verdict and applies the frozen D-012 precedence table; it does not inspect tool output or invent evidence.
7. `TurnEnvelope.reply_owner` is observational and the formal TurnCoordinator is not implemented. `turn_id` therefore remains nullable and ownership fields are caller-supplied data only.

### Classification

**MERGE/ADAPT.** Implement the approved D-012 contract and preserve the existing formatter registry as a backward-compatibility boundary. Do not create another state contract. The typed V1 registry is the sole semantic `MessageState`; old formatter-only names remain formatter compatibility inputs, not extra V1 states.

## 2. Canonical existing types

| Type or contract | Current role | PR A treatment |
|---|---|---|
| `ActionContract` | approval lifecycle source of truth | unchanged; no import |
| `ActionFact` | internal structural action fact | unchanged; PR C consumer |
| `GatewayReply` | internal rendered action result | unchanged; PR C consumer |
| `ApprovalLifecycleResult` | internal approval-lifecycle result | unchanged; PR B consumer |
| `TurnEvidenceSummary` | evidence classification | unchanged; supplied verdict copied as a string |
| formatter `CANONICAL_STATES` | legacy renderer capability registry | retained for exact compatibility; not a second semantic contract |
| `display_payload` dict | existing safe formatter payload | represented by typed `DisplayPayload` with identical serialized keys |

## 3. Gaps only

Main lacks a closed typed V1 `MessageState`, immutable `MessageContract`, typed serializable `DisplayPayload`, strict safe/audit separation, pure D-012 precedence builder, schema round-trip, payload-free observability projection, disconnected formatter wrapper, and focused purity/compatibility/no-wiring tests. No additional lifecycle, evidence, owner, queue, delivery, or routing source of truth is needed.

## 4. Proposed schema

Schema version: `1.0`.

```python
class MessageState(str, Enum):
    NEEDS_INPUT = "needs_input"
    APPROVAL_PENDING = "approval_pending"
    APPROVAL_PENDING_BATCH = "approval_pending_batch"
    APPROVED_PROCESSING = "approved_processing"
    SUCCESS = "success"
    FAILURE = "failure"
    OUTCOME_UNKNOWN = "outcome_unknown"
    UNVERIFIED_EFFECT = "unverified_effect"
    MIXED = "mixed"
    MIXED_WITH_UNKNOWN = "mixed_with_unknown"
    CANCELLED = "cancelled"
    ALREADY_COMPLETED = "already_completed"
    ALREADY_CANCELLED = "already_cancelled"
    NO_PENDING_ACTION = "no_pending_action"
    NEUTRAL = "neutral"

@dataclass(frozen=True)
class DisplayPayload:
    action: str | None
    entity_type: str | None
    entity_name: str | None
    key_fields: tuple[DisplayField, ...]
    count: int | None
    items: tuple[DisplayItem, ...]
    reason_code: str | None
    execution_verified: bool | None
    occurred_at: str | None

@dataclass(frozen=True)
class MessageContract:
    version: str
    state: MessageState
    display_payload: DisplayPayload
    reply_owner: str
    turn_context_source: TurnContextSource
    source_module: str
    turn_id: str | None
    evidence_status: str | None
    evidence_ref: str | None
    reason_code: str | None
    execution_verified: bool | None
    occurred_at: str | None
```

`DisplayPayload` is the user-safe detail area. The fixed metadata is audit-only. Separate `user_safe_record()` and `observability_record()` projections prevent raw payload values from entering audit logs and internal correlation fields from entering user-facing data.

`evidence_ref` remains singular because D-012 froze it; it is a copied reference, never evidence itself. `evidence_status` is the sole gap added to the frozen schema: it records the already-supplied verdict for observability and round-trip audit and does not classify evidence.

### Correlation and ownership

- `turn_id` is nullable and never synthesized from chat/session/contract/channel IDs.
- `evidence_ref` is optional and authority-supplied.
- `reply_owner` is required data-only candidate/current-known-owner metadata; no policy validation or single-speaker enforcement occurs.
- `turn_context_source` is `turn_coordinator`, `legacy_ingress`, or `unavailable`; provenance only.
- `source_module` identifies the constructing component, not execution or ownership authority.

## 5. State definitions and precedence

The 15 definitions are unchanged from V1 §4. When lifecycle input is supplied, V1 §6 applies top-to-bottom:

1. `pending` → `approval_pending` or `approval_pending_batch`.
2. `rejected` → `cancelled`; repeated synthesis is deferred to PR B.
3. `failed` → `failure`.
4. `approved`/`executing` → `approved_processing`.
5. `completed`/`executed` plus matching verified-success evidence → `success`.
6. completed plus unknown/unverified/failure/no evidence → the corresponding conservative non-success state.
7. lifecycle `outcome_unknown` → `outcome_unknown`.
8. `draft` or explicit no-contract input → `no_pending_action`.

For non-lifecycle messages callers may supply a V1 state directly. Direct `success` is rejected unless `execution_verified is True` and `evidence_status` is verified success. Invalid or conflicting inputs are rejected; the builder never silently upgrades state. The formatter never executes precedence or changes state.

## 6. Field ownership and separation

| Field | Owner/source | Foundation behavior |
|---|---|---|
| lifecycle input | ActionContracts | mapped only; no repository read |
| `state` | Message Contract builder | deterministic frozen precedence |
| evidence fields | evidence/execution authority | copied; never derived |
| `display_payload` | structured producer/F52 | validated/copied; no raw provider data |
| correlation/ownership | current ingress/future TurnCoordinator | copied; no decision |
| final wording | existing formatter | wrapper delegates; no wording logic |
| delivery | channel adapter/output gateway | out of scope |

Only `state` and serialized `display_payload` appear in `user_safe_record()`. `DisplayPayload` rejects unknown keys such as tool, contract, callback, record, provider, exception, token, URL, and raw-response fields.

Audit-only fields are `version`, `turn_id`, `reply_owner`, `turn_context_source`, `source_module`, `evidence_status`, `evidence_ref`, `reason_code`, `execution_verified`, and `occurred_at`. `observability_record()` excludes display-payload values.

## 7. Pure APIs

```python
build_message_contract(...structured keyword inputs...) -> MessageContract
MessageContract.to_dict() -> dict
MessageContract.from_dict(data) -> MessageContract
format_message_contract(contract) -> str
format_message_contract_with_meta(contract) -> tuple[str, dict]
```

No API imports or accepts DB, Airtable, network, Telegram, WhatsApp, Agent, repository, dispatcher, ActionGateway, or TurnCoordinator objects. The wrapper delegates only to the existing pure formatter and has zero production callers.

## 8. Backward compatibility

- Existing formatter functions, constants, text, aliases, and dict behavior remain unchanged.
- Existing formatter tests pass byte-for-byte without modification.
- `DisplayPayload.to_dict()` uses the existing nine canonical keys.
- Deserialization accepts frozen D-012 names `source_module` and singular `evidence_ref`.
- Legacy formatter inputs `clarification_needed` and `idle` remain supported by the formatter but are not V1 enum members; new code uses `needs_input` and `neutral`.
- No existing internal result adapter is included, so no runtime producer changes representation.

## 9. Contract Chain — Planning Gate Rule 00

1. **Entry point:** tests/importing callers only; no production call site.
2. **Public API:** builder and formatter wrapper above.
3. **Data contract:** structured keyword inputs return immutable, JSON-serializable data.
4. **Execution point:** none; no send/write/update.
5. **Verification:** schema, precedence, round-trip, purity, compatibility, import-boundary, and no-caller evidence.

## 10. Planning Gate answers

1. **Real problem:** yes; D-012 is frozen but unimplemented and a proposed parallel response contract was classified `MERGE`.
2. **Already solved:** partially; formatter/internal result types remain valid but are not the envelope.
3. **Smallest change:** one pure module, this SPEC, and one focused test file.
4. **Dual mechanism:** no; one V1 semantic enum, with legacy formatter names only as compatibility inputs.
5. **Bypass:** none; there is no execution.
6. **Evidence:** success requires supplied verified status and `execution_verified=True`; the builder creates no evidence.
7. **Business impact:** prevents every later layer from inventing a local contract without changing users.
8. **Forward enforcement:** closed enum, strict schema, no-leak projections, purity/import/no-caller tests, unchanged formatter regressions.

Architectural gates: no infrastructure import; builder and formatter remain separate; no input handler or precedence changes; no raw-input persistence; domain-agnostic; no write/send/state mutation.

**Planning Gate result: `PROCEED` for the exact scope below.**

## 11. Cross-Layer Impact Matrix

### Layer 1 — Core Reasoning / BUG-104

- touched: not touched
- input/output/authority/shared identifiers: none
- invariants/failure/observability: unchanged
- proof: no reasoning import or diff; existing tests unchanged

### Layer 2 — TurnCoordinator

- touched: indirectly, schema reference only
- input: optional copied `turn_id`, `reply_owner`, provenance
- output/authority: none; no decision/enforcement
- shared identifiers: existing `turn_id`, `reply_owner`
- invariant/failure: no fabricated ID; nullable ID plus explicit provenance
- observability/tests: copied metadata; nullable/provenance validation

### Layer 3 — F52 / Action and Tool Contract

- touched: directly, pure presentation-contract foundation
- input/output: structured facts/status → immutable envelope/disconnected wrapper
- authority: unchanged; no tool/policy/dispatch decision
- shared identifiers: D-012 names and existing display-payload keys
- invariants/failure: evidence-gated success; invalid construction fails closed
- observability/tests: payload-free record; schema/precedence/purity/no-leak/regression

### Layer 4 — Durable Atomic Approval

- touched: not touched
- input/output/authority: none; generic lifecycle strings only, no ActionContract import
- invariants/failure/observability: unchanged
- proof: imports forbid gateway/repository dependencies; approval code/tests unchanged

### Cross-Cutting Guard — RP5

- applies: yes, as a future consumer/source of supplied evidence status
- PR A does not import RP5, classify claims, read tool results, or mutate text. It copies verdicts and conservatively gates success.

## 12. Test plan

- exactly 15 V1 enum values;
- valid schema plus invalid state/version/owner/source rejection;
- JSON round-trip and D-012 singular evidence reference;
- all lifecycle/evidence precedence rows and no-evidence fail-safe;
- direct success rejection without verified evidence;
- deterministic builder, input non-mutation, immutable result;
- user-safe/audit-only separation and forbidden display-key rejection;
- wrapper equality with existing formatter for supported states and wrapper purity;
- AST/import and repository-search proof of no side-effect dependencies/callers;
- unchanged formatter suites; `git diff --check`.

## 13. Non-goals

No production callers; Telegram/WhatsApp wiring; wording/output changes; TurnCoordinator; final-reply-owner or single-speaker enforcement; queue/already-resolved/repeat policy; TTL/retention; legacy migration; RP5 or ActionContract integration; lifecycle changes; agent-surface work; flags; routing/adapters/execution changes; broad refactor; or new source of truth.

## 14. Rollback boundary

No runtime caller exists. Rollback removes the pure module, tests, and SPEC. It never mutates ActionContracts, evidence, queues, formatter wording, flags, or delivery.

## 15. Exact file scope

- `docs/architecture/message_contract/MESSAGE_CONTRACT_ENVELOPE_FOUNDATION_SPEC.md`
- `core/message_contract.py` (new)
- `test_message_contract.py` (new)

`core/agent_message_formatter.py` may change only for a minimal type/import adaptation needed to avoid a duplicate canonical registry. No renderer, wording, redaction, alias, or call-site change is authorized. If unnecessary, it remains untouched.

## 16. Future consumers and next PR

Future consumers: existing formatter; PR B `ApprovalLifecycleResult` adapter; PR C `ActionFact`/`GatewayReply` adapter; future TurnCoordinator correlation/owner data; RP5 evidence verdict. Channels consume only after separately reviewed wiring.

Recommended next PR: isolated PR B (`ApprovalLifecycleResult -> MessageContract`). It must not include PR C, queue policy, TTL/retention, or runtime owner enforcement.

## 17. Proof of no runtime change

- no diff in `app.py`, channels, router, gateway, repository, dispatcher, lifecycle, queues, RP5, or flags;
- zero production imports/callers of `core.message_contract`;
- existing formatter tests pass unchanged before and after;
- focused tests exercise pure values/functions only;
- no production/runtime status claim is made.
