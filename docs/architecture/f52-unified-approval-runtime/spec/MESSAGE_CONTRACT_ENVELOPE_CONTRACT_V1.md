# Unified Message Contract Envelope — Behavior Contract V1

**Gate:** `docs/architecture/CROSS_LAYER_AUTHORITY_CONTRACT_V1.md` — MANDATORY. This is
a Planning Gate document touching tools/actions, approvals, and execution
presentation (Layer 3/F52 and the RP5 guard). Per that document's §7 standing
rule it opens with this reference and does not proceed past a completed
Cross-Layer Impact Matrix — the full matrix (all 4 layers × 9 required fields,
plus proof-of-non-impact and RP5-applicability) is recorded in-repo in §0.1
immediately below, not only summarized.

**Status:** `PLANNING COMPLETE — OWNER DECISIONS RECORDED. IMPLEMENTATION NOT
AUTHORIZED.` Owner decisions recorded 28/07/2026 (see
`decisions/DECISION_LOG.md` D-012). No runtime code exists yet; this document
is the frozen target for PR A/B/C in
`rollout/MESSAGE_CONTRACT_ENVELOPE_MIGRATION_PLAN.md`.

**Naming note:** this document is deliberately **not** titled "Message Contract
Foundation" — that title is taken by
`docs/architecture/f52-unified-approval-runtime/PR1_MESSAGE_CONTRACT_FOUNDATION.md`
(implementing `core/agent_message_formatter.py`). This contract is the envelope
*around* PR1's existing `(state, display_payload)` pair, not a competing
formatter — see §1 and §8.

**Prerequisite reading:** `spec/UNIFIED_MESSAGE_UX_STANDARD.md` (UX source of
truth, D-010/D-011), `PR1_MESSAGE_CONTRACT_FOUNDATION.md`
(`core/agent_message_formatter.py`), `core/action_gateway.py`
(`ActionContract`, `ActionFact`, `GatewayReply`, `ApprovalLifecycleResult`),
`core/turn_evidence.py` (RP4), `docs/architecture/turn-coordinator/
TURN_COORDINATOR_BEHAVIOR_CONTRACT_V1.md` (frozen, unimplemented).

---

## 0.1 Cross-Layer Impact Matrix (mandatory, `CROSS_LAYER_AUTHORITY_CONTRACT_V1.md` §2)

Recorded in-repo per that document's §5 "Proof of Non-Impact" requirement — a
summary or a pointer to an external conversation is not sufficient; grep
evidence, unchanged-tests evidence, and no-new-coupling evidence are stated
explicitly below for every layer marked "not touched."

### Layer 1 — Core Reasoning / BUG-104
- **touched:** not touched
- **input impact:** none
- **output impact:** none
- **authority impact:** none — `MessageContract` never computes business
  phase/confidence/next-step; those enter only via a pre-computed
  `semantic_payload` input, per the field-ownership matrix (§5 below:
  "Layer 1, only where required").
- **shared identifiers:** none — no identifier from this contract
  (`MessageContract`, `DisplayPayload`, `MessageState`,
  `build_message_contract`) appears in `core/leads_reasoning_projection.py`,
  `core/adapters/leads_adapter.py`, or any `docs/architecture/bug-104/` doc.
- **invariants:** unaffected — Layer 1 stays read-only, flag-gated,
  execution-authority-free, exactly as before.
- **failure semantics:** n/a — no coupling exists to fail.
- **observability:** no new Layer 1 logging.
- **cross-layer tests:** none apply; no Layer 1 test file imports anything
  from this spec's scope.
- **proof of non-impact:**
  1. *grep evidence:* `git grep -n "MessageContract\|DisplayPayload\|build_message_contract" -- 'core/leads_reasoning_projection.py' 'core/adapters/leads_adapter.py'` → no matches (spec-only at this stage; no code exists to grep yet, so this is re-verified against the Layer 1 file set directly).
  2. *unchanged-tests evidence:* no code changed in this PR (documentation only), so `test_bug104_*` suites are untouched by construction.
  3. *no-new-coupling evidence:* no import statement was added anywhere — this PR contains zero `.py` changes.

### Layer 2 — TurnCoordinator
- **touched:** indirectly (forward-reference only, not a live coupling)
- **input impact:** the builder's `turn_decision` parameter is typed against
  `TurnCoordinator`'s frozen (unapproved, unimplemented) `TurnDecision` —
  specifically `.turn_id`/`.reply_owner`. Since `TurnCoordinator` has no
  implementation (`grep -rl "class TurnCoordinator"` → zero files), this
  spec's schema makes `turn_id` **nullable** and adds `turn_context_source`
  (§3) precisely so the contract does not assume a producer that doesn't
  exist yet (decision D-012 #2).
- **output impact:** none — this spec produces no `TurnDecision`/
  `TurnActionReference` fields.
- **authority impact:** none — `MessageContract.reply_owner` is a verbatim
  copy of whatever reply-owner value the (current de-facto or future formal)
  Layer 2 owner already decided; it is never recomputed here.
- **shared identifiers:** `turn_id`, `reply_owner` — referenced, not
  redefined (satisfies the identifier-squatting prohibition, §4 #9 of the
  authority contract).
- **invariants:** the Reply-Owner Invariant (`TURN_COORDINATOR_BEHAVIOR_CONTRACT_V1.md`
  §4a — singular per `turn_id`, decided before the handler runs) is preserved
  by copy-only semantics.
- **failure semantics:** when no real `TurnDecision` exists (today, always),
  `turn_id=None` and `turn_context_source` records `legacy_ingress` or
  `unavailable` — an explicit degraded state, never a fabricated value (§3).
- **observability:** `turn_context_source` is itself a new observability
  field recording this exact gap (§10).
- **cross-layer tests:** none exist yet; deferred to when a real
  `TurnDecision` producer exists (`spec` §12 OQ list).

### Layer 3 — F52 / Phase 4C Action & Tool Contract
- **touched:** directly
- **input impact:** consumes `action_contract` (read-only field access only)
  and the C53a `{ok, tool, external_id, evidence, user_message}` result
  contract.
- **output impact:** `MessageContract` is designed to become the sole input
  to `format_agent_message()` (`core/agent_message_formatter.py`), extending
  PR1 rather than replacing it — this is the direct D-010/D-011
  reconciliation target (see D-012, `decisions/DECISION_LOG.md`).
  `tool_registry.py`, `tools/dispatcher.py`, `action_validator.py` are
  untouched.
- **authority impact:** none — this contract never decides approval policy,
  tool permission, or dispatch routing; it is a read-only downstream
  projection (field-ownership matrix, §5).
- **shared identifiers:** `reason_code`, `occurred_at`, `execution_verified`,
  `display_payload` — all already live on `core/agent_message_formatter.py`'s
  existing contract; this spec aligns with, not redefines, their meaning
  (§2 schema note).
- **invariants:** `UNIFIED_MESSAGE_UX_STANDARD.md`'s locked principles all
  still hold, in particular principle 2 (success only with
  `execution_verified=true`) and principle 6 (missing/unsafe data → neutral
  fallback).
- **failure semantics:** unknown/malformed state still fails closed to a
  neutral message (`core/agent_message_formatter.py:508-512`) — §8/§11
  preserve this guarantee unchanged.
- **observability:** extends, not duplicates, the existing
  `format_agent_message_with_meta()` record (§10).
- **cross-layer tests:** `test_agent_message_formatter.py` (28 checks) and
  `test_agent_message_formatter_display_payload.py` must stay green
  unmodified — this PR contains zero changes to
  `core/agent_message_formatter.py`.
- **proof of non-impact:** n/a — this layer is marked "touched directly," so
  proof-of-non-impact does not apply here; the constraint instead is proof of
  *bounded* impact, satisfied by the unchanged-tests requirement above.

### Layer 4 — Durable Atomic Approval (ActionContract)
- **touched:** indirectly
- **input impact:** `action_contract` parameter reads `ActionContract.status`
  read-only.
- **output impact:** none — no write path to `ActionContract`,
  `ActionContractRepository`, or `execute_with_atomic_claim()` exists in this
  contract.
- **authority impact:** none — canonical approval-lifecycle status remains
  exclusively owned by Layer 4 (§5 field-ownership matrix states this
  explicitly).
- **shared identifiers:** none of this schema's field names collide with
  `ActionContract`'s fields; `contract_id`/Airtable record IDs are explicitly
  forbidden from ever reaching `DisplayPayload` (§2).
- **invariants:** "no two components may independently decide success"
  (authority contract §4 #1) is the organizing constraint of the whole
  builder design (§9).
- **failure semantics:** unchanged — Layer 4's atomic-claim/fail-closed
  behavior is untouched.
- **observability:** no new Layer 4 logging.
- **cross-layer tests:** Layer 4 regression suites
  (`test_approval_concurrency.py`, `test_cxx_action_integrity.py`) are
  unaffected — zero Layer 4 code changes in this PR.
- **proof of non-impact:**
  1. *grep evidence:* zero `.py` files changed in this documentation-only PR — `git diff --stat` against `core/action_gateway.py`, `core/action_contract_repository.py`, `core/action_gateway_atomic_executor.py` shows no changes.
  2. *unchanged-tests evidence:* `test_approval_concurrency.py`/`test_cxx_action_integrity.py` untouched by construction (no code changed).
  3. *no-new-coupling evidence:* no new import added anywhere in this PR.

### Cross-Cutting Guard — RP5 Evidence Finalization (§1.5 of the authority contract)
- **applies:** yes
- **how:** `execution_verified` and the `outcome_unknown`/`unverified_effect`
  mappings (§6) are populated **exclusively** from
  `core/turn_evidence.py::TurnEvidenceSummary.classification()` and/or
  `core/anti_hallucination.py::verify_execution()`. No independent grounding
  check is introduced — this satisfies the standing warning in the authority
  contract §1.5 against a second `validate_agent_output()`-style mechanism.
  RP4 remains shadow-only (`FEATURE_EVIDENCE_FINALIZER` off); RP5 enforcement
  remains blocked per `RP5_PREFLIGHT_BLOCKER.md`. This spec changes neither
  flag.

---

## 0. Decision D-012 summary (see DECISION_LOG.md for full text)

1. **`MessageContract` is the sole canonical input to the final UX formatter.**
   This does not delete or immediately replace `ApprovalLifecycleResult`,
   `GatewayReply`, or `ActionFact` — those remain valid *internal* fact/result
   contracts. They must reach the formatter only through adapters that produce
   `MessageContract`. Architecture is **reconciliation, not supersession.**
   D-011 is closed conceptually by this rule: multiple internal contracts are
   allowed; exactly one public presentation contract is allowed; the UX
   formatter consumes `MessageContract` only.
2. **v1 does not block on `TurnCoordinator`.** `turn_id` is nullable;
   `reply_owner` remains required where currently known; a new
   `turn_context_source` field records provenance. No fake canonical `turn_id`
   is ever synthesized from `chat_id`/session ID/`contract_id`/channel message
   ID.
3. **Registry keeps `approval_pending_batch`, `mixed`, `mixed_with_unknown`**
   as full v1 states, not a lesser "extension" tier — never collapsed into
   `neutral`/`outcome_unknown`.
4. **Three separate PRs** (A: envelope + wrapper, B: `ApprovalLifecycleResult`
   adapter, C: `ActionFact`/`GatewayReply` adapter) — B and C are never
   combined.
5. **`evidence_ref` is supplied only by the evidence/execution authority** —
   the builder copies it, never derives/hashes/invents it.
6. **Explicit precedence table** (§6) governs lifecycle-vs-evidence conflicts,
   resolved conservatively — completed-without-verified-evidence never becomes
   `success`; the formatter never changes state.

---

## 1. Relationship to existing contracts (D-011 resolution)

```
Internal fact/result contracts (unchanged, still valid):
  ActionFact / GatewayReply         (core/action_gateway.py, compose_status_reply())
  ApprovalLifecycleResult           (core/action_gateway.py, build_approval_lifecycle_result())
  C53a {ok,tool,external_id,evidence,user_message}
  TurnEvidenceSummary.classification()   (RP4/RP5)

                    │  adapters (PR B, PR C — §9)
                    ▼
         MessageContract   ◀── the ONE public presentation contract
                    │
                    ▼
       format_agent_message(state, display_payload)   (UX Formatter, PR1, unchanged)
```

`MessageContract.state` + `MessageContract.display_payload` **are** PR1's
existing `(state, payload)` inputs — not a new pair. No wording changes to
`core/agent_message_formatter.py` are made or required by this contract.

---

## 2. `MessageContract` schema (final, v1)

```python
@dataclass(frozen=True)
class MessageContract:
    version: str                     # schema version, e.g. "1.0" — §11
    turn_id: str | None              # NULLABLE (decision 2). None when no
                                      # authoritative turn id exists — never
                                      # synthesized from chat_id/session_id/
                                      # contract_id/channel message id.
    reply_owner: str                 # required where currently known (today:
                                      # ApprovalLifecycleResult.reply_owner
                                      # literal "gateway", or the de-facto
                                      # router/handler owner). Not nullable —
                                      # unlike turn_id, some component always
                                      # knows who owns the reply.
    turn_context_source: str         # closed set: "turn_coordinator" |
                                      # "legacy_ingress" | "unavailable" — §3
    state: MessageState              # closed registry, §4
    display_payload: DisplayPayload  # unchanged from PR1 — §5
    reason_code: str | None
    execution_verified: bool | None
    source_module: str
    evidence_status: str | None      # optional copy of the canonical evidence
                                      # classification — §2.1
    evidence_ref: str | None         # copied only from the evidence/execution
                                      # authority — never derived — §7
    occurred_at: str | None
```

`DisplayPayload` is unchanged from the prior spec turn — verbatim PR1's
existing contract (`action`, `entity_type`, `entity_name`, `key_fields`,
`count`, `items`, `reason_code`, `execution_verified`, `occurred_at`); same
forbidden-field list (no raw tool names, table names, provider responses,
internal exception text, contract UUIDs, Airtable record IDs,
implementation-specific identifiers).

### 2.1 V1 addendum — `evidence_status` metadata

`evidence_status` is optional metadata copied from the canonical evidence
classification. It does not determine or upgrade `MessageState`, is not a new
source of truth, and has no runtime ownership or enforcement authority.
Unknown or absent values must fail closed or remain `None`, according to the
existing schema rules. This addendum ratifies schema metadata only and does not
change runtime behavior.

---

## 3. `turn_context_source` (new field, decision 2)

| Value | Meaning |
|---|---|
| `turn_coordinator` | `turn_id`/`reply_owner` came from a real `TurnDecision` (only possible once `TurnCoordinator` ships — currently never) |
| `legacy_ingress` | `reply_owner` was resolved by today's de-facto owners (`core/router/router.py::route_request()`, `core/lead_candidate_handler.py`, or `ApprovalLifecycleResult.reply_owner`); `turn_id` is `None` |
| `unavailable` | Neither `turn_id` nor a confident `reply_owner` provenance could be established; `reply_owner` still carries the best-known value, but callers must not treat it as durable/turn-scoped |

**Explicitly forbidden as a `turn_id` source, in any `turn_context_source`
value:** `chat_id`, session ID, `contract_id`, channel message ID. None of
these identify a *turn* — using one would silently fabricate the exact kind of
parallel/competing identifier `CROSS_LAYER_AUTHORITY_CONTRACT_V1.md` §4
prohibition #9 (identifier squatting) and §4 prohibition #8 (turn_id +
matching execution evidence, not a substitute) forbid. When no real
`TurnDecision` exists, `turn_id=None` and `turn_context_source="legacy_ingress"`
(or `"unavailable"`) is the only correct representation.

A future schema version (`version >= "2.0"`) may make `turn_id` mandatory once
`TurnCoordinator` is live in production — see §11.

---

## 4. `MessageState` registry (closed, v1 — final)

| State | Meaning |
|---|---|
| `needs_input` | User input required before a safe decision |
| `approval_pending` | One frozen action awaits approval |
| `approval_pending_batch` | Several frozen actions await selection/approval — **kept distinct, never collapsed** (decision 3) |
| `approved_processing` | Approved, execution not yet final |
| `success` | Verified completed business action |
| `failure` | Stable, non-retryable failure |
| `outcome_unknown` | No usable evidence either way |
| `unverified_effect` | Partial evidence of a possible side effect; manual review required |
| `mixed` | Some actions in the turn succeeded, some didn't — **kept distinct** (decision 3) |
| `mixed_with_unknown` | Mixed outcome plus an unverifiable component — **kept distinct** (decision 3) |
| `cancelled` | Public name for internal lifecycle `rejected` |
| `already_completed` | Replay of an already-finished action |
| `already_cancelled` | Replay of an already-cancelled action |
| `no_pending_action` | No live contract exists for this reference |
| `neutral` | Nothing to report; safe generic fallback; also the closed-registry fail-safe for an unrecognized future state (§11) |

15 states total. Implemented as a closed `Enum`/`frozenset`, matching
`CANONICAL_STATES` in `core/agent_message_formatter.py:54-59` — invalid state
is a construction-time error.

---

## 5. Field ownership matrix (unchanged from the prior spec turn)

| Field(s) | Owner | Current authoritative source |
|---|---|---|
| `turn_id`, `reply_owner`, `turn_context_source` | TurnCoordinator (target); legacy ingress (today) | `TurnDecision.turn_id`/`.reply_owner` (frozen, unimplemented) / `core/router/router.py::route_request()` / `ApprovalLifecycleResult.reply_owner` |
| `action`, `entity_type`, `entity_name`, approval policy, normalized `reason_code` | F52 / Action & Tool Contract layer | `tool_registry.ToolMeta`, `tools/schemas.py`, C53a result contract |
| Approval lifecycle state, atomic execution outcome | Layer 4 / ActionContracts | `ActionContract.status`, `ActionContractRepository`, `execute_with_atomic_claim()` |
| `execution_verified`, evidence classification | RP5 (guard) | `core/turn_evidence.py::TurnEvidenceSummary.classification()`, `core/anti_hallucination.py::verify_execution()` |
| Business phase / next step | Layer 1 (Core Reasoning), only where required | `core/leads_reasoning_projection.py` — not a required field; enters only via a pre-computed input, never computed by the builder |
| `evidence_ref` | Evidence/execution authority (RP5 / C53a / `TurnActionReference`) | §7 — the builder only copies it |
| `state` (public `MessageState`) | Message Contract Builder | §6 precedence table |
| Final wording | UX Formatter | `core/agent_message_formatter.py::format_agent_message()` |

**No two components may independently decide success** —
`CROSS_LAYER_AUTHORITY_CONTRACT_V1.md` §4 prohibition #1, restated.

---

## 6. Evidence and lifecycle precedence table (final, decision 6)

Evaluated top-to-bottom; **first match wins** — this is the explicit,
conservative conflict-resolution order:

| # | Condition | → `state` | Notes |
|---|---|---|---|
| 1 | `ActionContract.status == "pending"` | `approval_pending` (or `approval_pending_batch` if multiple contracts) | Evidence is irrelevant here — nothing has executed yet. |
| 2 | `ActionContract.status == "rejected"`, first occurrence | `cancelled` | |
| 2b | `ActionContract.status == "rejected"`, `repeated=True` | `already_cancelled` | Synthesized from `canonical_state="rejected"` + `repeated`, mirroring `build_approval_lifecycle_result()`'s existing `repeated` parameter. |
| 3 | `ActionContract.status == "failed"` | `failure` | Terminal; evidence cannot soften a stable failure. |
| 4 | `ActionContract.status in ("approved", "executing")` (not yet completed) | `approved_processing` | **Never** `success`, regardless of any evidence present — execution isn't final (decision 6, rule "approved but execution not final → approved_processing"). |
| 5 | `ActionContract.status in ("completed", "executed")` **and** `evidence_verdict` is `verified_write_success` (or `verified_read_only` for a read action), for the **same** contract | `success` | The only path to `success`. |
| 6 | `ActionContract.status in ("completed", "executed")` **and** `evidence_verdict` is `outcome_unknown` | `outcome_unknown` | Completed lifecycle status alone never implies success (decision 6, explicit rule). |
| 7 | `ActionContract.status in ("completed", "executed")` **and** `evidence_verdict` is `unverified_effect` | `unverified_effect` | Same rule, distinct evidence shape. |
| 8 | `ActionContract.status in ("completed", "executed")` **and** `evidence_verdict` is `failure`/`failed` | `failure` | Evidence contradicting an optimistic lifecycle status is trusted over the status, conservatively. |
| 9 | `ActionContract.status in ("completed", "executed")` **and no `evidence_verdict` supplied at all** | `outcome_unknown` | Conservative default — completion without any evidence is never assumed success. |
| 10 | `ActionContract.status == "outcome_unknown"` | `outcome_unknown` | Layer 4 already flagged uncertainty; a *new* `MessageContract` built later with fresh, matching evidence may move this — see §8 no-upgrade rules; the same builder call never does. |
| 11 | `ActionContract.status == "draft"` or no matching contract | `no_pending_action` | |
| Any row | Missing/unsafe display data | Same `state` as matched above, neutral safe `DisplayPayload` | Never a different (weaker or stronger) state, never a raw fallback. |

**Stale/unrelated evidence:** `evidence_verdict` must correspond to the same
`ActionContract`/turn as `action_contract`. The builder is a pure function of
its five inputs (§7 of the prior spec turn) and does not itself perform
evidence-to-contract matching — that correlation is the caller's
responsibility, upstream of the builder. If a caller cannot prove the
`evidence_verdict` it holds corresponds to the `action_contract` it holds, the
conservative rule is: **omit `evidence_verdict`** (pass `None`) rather than
pass unrelated evidence — row 9's "no evidence supplied" branch is the
designed-safe fallback for exactly this situation, not row 5's `success`
branch.

**Formatter never changes state:** `format_agent_message()` already enforces
this (`core/agent_message_formatter.py:17`, "it never derives, upgrades, or
infers truth") — this precedence table is evaluated once, entirely inside
`build_message_contract()`; the UX Formatter downstream has no state-mutation
authority at all.

---

## 7. `evidence_ref` authority (decision 5)

`evidence_ref` is supplied **only** by the evidence/execution authority (RP5 /
`core/turn_evidence.py`'s `TurnActionReference.execution_evidence_ref` once
implemented, or the C53a `evidence` dict via `core/anti_hallucination.py`).
The builder's role is **copy only**:

**Forbidden**, unconditionally:
- deriving it from `contract_id`;
- hashing an internal identifier;
- storing an Airtable record ID;
- embedding raw provider evidence;
- inventing a local evidence token.

**When no canonical evidence reference exists:** `evidence_ref = None`. This
is not an error condition — most `MessageContract`s (e.g. `approval_pending`,
`needs_input`) legitimately have no evidence reference yet.

---

## 8. No-state-upgrade policy (unchanged, restated)

Forbidden without new authoritative execution evidence: `outcome_unknown →
success`, `unverified_effect → success`, `approval_pending → success`,
`approved_processing → success`. Because `build_message_contract()` is pure
and stateless, "upgrade" can only happen via a fresh call with a genuinely new
`evidence_verdict` — never a mutation of an existing `MessageContract`, and
never performed by the UX Formatter.

---

## 9. Builder and adapters

```python
def build_message_contract(
    turn_decision: "TurnDecision | None",         # Layer 2 — nullable per §3
    action_contract: "ActionContract | None",      # Layer 4
    execution_result: "DispatcherOutcome | dict | None",
    evidence_verdict: "TurnEvidenceSummary | VerifyResult | None",
    semantic_payload: dict,
) -> MessageContract: ...

def from_approval_lifecycle_result(
    result: "ApprovalLifecycleResult",
    turn_decision: "TurnDecision | None" = None,
) -> MessageContract: ...          # PR B

def from_action_fact(
    fact: "ActionFact",
    turn_decision: "TurnDecision | None" = None,
) -> MessageContract: ...          # PR C
```

Both adapters apply the same §6 precedence table and §8 no-upgrade rule; they
differ only in which internal contract they read from. Neither adapter writes
back to `ActionContract`, `ActionContractRepository`, or any Layer 4 storage.

---

## 10. Observability (unchanged from the prior spec turn)

```
version, turn_id, reply_owner, turn_context_source, state, source_module,
reason_code, execution_verified, evidence_ref, payload_completeness, fallback_used
```

Never logged: raw `DisplayPayload` content, `contract_id`, record IDs.

---

## 11. Versioning

- `MessageContract.version` is tracked separately from
  `core/agent_message_formatter.py`'s `FORMATTER_VERSION` and from
  `TurnDecision.contract_version`/`.policy_snapshot_version` — three distinct
  objects, not a naming collision.
- New states may be added in future registry versions; existing names are
  never repurposed (identifier-squatting prohibition).
- Unknown future states fail safely to `neutral` and are never treated as
  success — inherited unchanged from `core/agent_message_formatter.py:508-512`.
- **v2 candidate change (not authorized, tracked here only):** once
  `TurnCoordinator` is live in production, a future schema version may make
  `turn_id` mandatory and retire `turn_context_source="legacy_ingress"` as a
  live value (kept only for historical log records).

---

## 12. Remaining non-blocking open questions

See `decisions/DECISION_LOG.md` D-012 for the full list. None of these block
PR A (§ of `rollout/MESSAGE_CONTRACT_ENVELOPE_MIGRATION_PLAN.md`):

- **OQ-4:** exact interim value/format for `reply_owner` when
  `turn_context_source="unavailable"` (best-effort string vs. a reserved
  sentinel) — resolve during PR A implementation, not blocking the spec.
- **OQ-5 (resolved by decision 5 for the *builder*; still open for the
  *adapters*):** for PR B/PR C, which existing field (if any) on
  `ApprovalLifecycleResult`/`ActionFact` legitimately qualifies as an
  "evidence/execution authority" source for `evidence_ref`, versus simply has
  none today (→ `None`) — resolve per-adapter during PR B/PR C, not blocking
  PR A.
- **OQ-6:** exact enum/type for `turn_context_source` (str literal vs. formal
  `Enum`) — implementation detail, not a planning blocker.
