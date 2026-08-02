# Lane A — MessageContract / Approval Runtime gap closure

**Date:** 02/08/2026  
**Branch:** `codex/lane-a-messagecontract-gap-closure`  
**Status:** Implemented but not yet verified in production; stop before merge.  
**Flag constraint:** `FEATURE_UNIFIED_STATUS_FORMATTER` remains unchanged and off by default.

## Planning Gate and verification ledger

The Context Librarian `cross_layer_architecture` bundle was rebuilt at
`9048ccaae3a580d7d53f03228235d09237c33568`. The gate was `WARNING`, with
100% mandatory authority coverage and only `layer.approvals` / `layer.ux_f52`
stale. Direct verification covered `docs/context_librarian/PLANNING_GATE.md`,
`tools/context_librarian/librarian.py`, `test_context_librarian.py`, this
Decision Log, the MessageContract/adapters/formatter, ActionGateway, app routing,
feature flags, and their focused tests. Staleness alone did not block planning;
no authority conflict remains after the owner assigned D-018/D-019.

Budget ledger: estimate 10,811 approximate tokens / 12,000 profile budget,
no overflow. The earlier `approval_ux` estimate was 8,147 / 8,000 and was
rejected without truncation; the complete cross-layer profile was selected.
No catalog refresh was performed.

## Outcome and live-caller inventory

| Outcome / state | Source of truth | Live caller / owner | Current renderer | Target / canonical renderer | Agent fallback | Evidence sufficient | Migration safety |
|---|---|---|---|---|---|---|---|
| pending, single | ActionContract `pending`; bounded live snapshot | `describe_pending_queue()` and `query_execution_status()`; Approval Runtime | off: lifecycle/legacy copy; shadow/on: D-016 singular helper | D-014–D-017 surface wording; D-019 is baseline only | No after D-018 intent match | Lifecycle evidence is sufficient for pending, never success | Safe; no authority/write change |
| pending, none | absence in the same bounded snapshot | pending/status deterministic route | D-017 idle or safe status absence | D-017 surface response | No | Absence is not execution evidence | Safe |
| pending, batch | ActionContract live snapshot | both status functions | D-017 shared batch helper | D-017 numbered list | No | Per-contract pending lifecycle | Safe; selection state unchanged |
| failed | terminal ActionContract/ActionFact | `_execute_contract()` and status query | `compose_status_reply()`; failed already crosses MessageContract in shadow/on | MessageContract failure; D-019 baseline when context-free | No for D-018 status intent | Durable failure or verified failure classification | Safe; no success upgrade |
| cancelled / rejected | terminal ActionContract rejection | reject/cancel callback/text callers | ApprovalLifecycleResult and rejection helper | cancelled MessageState; D-019 baseline where context-free | No for recognized lifecycle intent | Canonical rejected transition | Safe; existing adapter retained |
| completed / executed | terminal ActionContract plus execution fact | executor and status query | contextual `compose_status_reply()` | success only with verified evidence; D-019 baseline where context-free | No for D-018 status intent | Required; formatter cannot infer it | Safe only with explicit verification |
| outcome_unknown | ActionContract / dispatcher classification | executor/status query | fail-closed outcome-unknown formatter | remain outcome_unknown | No for D-018 status intent | Sufficient only to deny success | Do not migrate to completed |
| expired | TTL-filtered pending lookup; legacy lock TTL | live lookup / per-turn legacy cleanup | no-pending/expired safe response | surface-specific safe response | No for recognized intent | TTL is sufficient to deny execution | Safe cleanup; no new lifecycle state |
| unavailable | repository/read failure | ingress snapshot guard | deterministic `לא ניתן לבדוק כרגע את מצב הפעולה.` | same fail-closed response | No | Insufficient to claim absence or success | Safe; never reports absence and never calls Agent |

### Existing adapters and ownership

- `ApprovalLifecycleResult -> MessageContract` and `ActionFact -> MessageContract`
  already exist and are reused; no adapter was rebuilt.
- ActionContracts remains lifecycle authority. MessageContract owns presentation,
  not approval, queue, execution, or evidence decisions.
- `format_agent_message*()` is the unified formatter. D-019 adds a narrow
  context-free summary API; it does not silently replace D-014–D-017 surfaces.
- Legacy renderers remain only for flag-off rollback compatibility. Shadow
  computes/logs without changing output; on changes only the already-wired
  surface output. This change does not alter the flag state.

### Routing and bounded-read result

D-018 adds an anchored generic status grammar (including `מה מצב הפעולה?`) after
approval-resolution precedence and before Agent execution. Pending intent keeps
higher precedence and uses `describe_pending_queue()`. Both reuse the one
request snapshot. Terminal status reads use `ExecutionLedger`'s canonical-user
index, so 109 unrelated cached contracts are not scanned. Safe absence is
`לא מצאתי מידע עדכני על הפעולה.` and cannot fall through to the Agent.

## Acceptance matrix

| State | Approved baseline | Evidence requirement | Route owner | Fallback | Leak prevention | off / shadow / on | Rollback | Tests | Production requirement |
|---|---|---|---|---|---|---|---|---|---|
| pending | `הפעולה ממתינה לאישור.` | canonical pending lifecycle | Approval Runtime | safe no-pending/absence; never Agent | formatter redaction; no internal nouns | D-014–D-017 remain surface authority; baseline API is mode-independent | keep flag off | baseline, precedence, zero-Agent, bounded snapshot | grouped pending probes, counts 0/1/2 |
| failed | `הפעולה לא הושלמה.` | terminal failure/evidence classification | Approval Runtime / Gateway | fail closed | no raw reason/tool/id | existing off/shadow/on wiring | flag off | MessageContract + status suite | grouped verified failure probe |
| cancelled | `הפעולה בוטלה.` | canonical rejected transition | Approval Runtime / Gateway | no-contract safe response | lifecycle adapter and redaction | existing rejection surface policy | flag off | adapter/rejection/concurrency suites | callback and text cancellation probes |
| completed | `הפעולה הושלמה.` | explicit verified execution evidence | Gateway/evidence owner | unverified message, never success | no provider/tool/id detail | contextual D-014–D-017 unaffected; baseline helper gates success | flag off | explicit verified/unverified tests | verified execution probe only |

For every state, output must exclude ActionContracts, legacy terminology, queue
names, raw tool names, IDs, internal states, and implementation details.

## Pending-lock lifecycle

The router-level legacy pending lock already used one critical section for
selection plus pop, preventing two text confirmations from winning. Lane A adds:

- acquire telemetry with reason and zero initial age;
- terminal release reasons for confirmation, cancellation, expiry, and cleanup;
- per-turn stale lock recovery, rather than waiting for an expired confirmation;
- stuck-lock age telemetry;
- tests proving expiry cleanup, idempotent duplicate cleanup, and a single
  winner under concurrent terminal release.

The ActionContract callback/text path continues to rely on its existing guarded
transition and atomic execution claim. No queue or authority was redesigned.

## Observability

Added or retained fields:

- formatter shadow: `contract_path`, `contract_version`, `source_component`,
  `outcome`, `mapped_state`, `fallback_used`, and identifier leak flags;
- D-018 route: `status_route_owner=approval_runtime`, identity-scoped
  `records_scanned`, candidate count, and fallback use;
- lock lifecycle: `lock_acquire_reason`, `lock_release_reason`, and
  `stuck_lock_age_seconds`.

Logs contain no user text, rendered reply, IDs, tool names, or payloads.

## Flag readiness and rollout

**Verdict: NOT READY; keep `FEATURE_UNIFIED_STATUS_FORMATTER` off.** This branch
prepares code/tests only. Required sequence remains implementation -> targeted
tests -> shadow verification -> grouped production probe -> canary decision ->
canary -> rollback verification -> full rollout decision. Canary and rollout are
out of scope here.

### BLOCKER

- Production verification has not run; therefore no production completion or
  readiness claim is permitted.

### BEFORE_FLAG_ON

- Run grouped off/shadow/on acceptance with real deployment identity.
- Verify pending 0/1/2, failure, cancellation, and evidence-backed completion.
- Confirm stable shadow telemetry, zero leak flags, bounded record counts, one
  final-message owner, and documented rollback to off.
- Exercise repository-unavailable status queries; an outage must not be
  reported as absence.

### FOLLOW_UP

- Consider moving the older PR2 flag-gated narrow status grammar onto the same
  D-018 intent classifier after production evidence; this slice does not change
  that flag or its rollout semantics.
- Evaluate a durable-store terminal-status lookup for cold-cache status queries.
  Current D-018 behavior is bounded to the identity-indexed cache plus the
  existing durable pending lookup and safely reports no current information.

## Production verification plan

1. Deploy the exact merge SHA with the formatter flag still off.
2. Confirm deployment identity and all relevant feature-flag values.
3. Run read-only status probes for no contract, one pending, two pending,
   failed, cancelled, outcome-unknown, and evidence-backed completed.
4. Assert zero Agent/model calls and identity-scoped records-scanned telemetry.
5. Run callback/text duplicate and terminal-lock cleanup probes without causing
   duplicate provider execution.
6. Enable shadow only in a separately approved operation, collect leak/fallback
   telemetry, then return to off and verify rollback. No canary/full rollout is
   authorized by this branch.
