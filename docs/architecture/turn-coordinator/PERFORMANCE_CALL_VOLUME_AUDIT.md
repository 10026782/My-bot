# Performance & Call-Volume Audit — Telegram Create-Task → Approve → Execute

Program: TurnCoordinator (consumes F52/Phase 4C + prior TurnCoordinator-program docs as
background; does not re-derive them).
Status: **AUDIT / RESEARCH ONLY. No runtime code changed by this document. Not a Planning Gate.**
This document does not authorize any implementation. It reports read-only findings about
external-call volume (Anthropic/Airtable/Telegram) in the current `main` runtime and proposes
optimizations for a future implementation phase to pick up. Any implementation PR that acts on
these findings must independently satisfy `CROSS_LAYER_AUTHORITY_CONTRACT_V1.md`'s full
Cross-Layer Impact Matrix (§2 there) before code is written — this document does not substitute
for that gate, exactly as `REPLY_OWNERSHIP_AND_APPROVAL_AUTHORITY_RESEARCH.md` (research-only)
does not substitute for `PA-01_PLANNING_GATE.md` (the approved implementation plan for its topic).
Baseline: `main` `f918e105969ec5042423d5cc166e6383e8413048` (2026-07-24).
Cross-Layer gate: `docs/architecture/CROSS_LAYER_AUTHORITY_CONTRACT_V1.md` applies per its §7
standing rule (this document touches TurnCoordinator/routing, F52/tool-contract, and Durable
Atomic Approval material) — referenced here per that rule, not re-litigated.

## Why this is filed under `turn-coordinator/`

The single largest finding below (§ "Flow 4 — 'מאשר'") is a direct TurnCoordinator-relevant gap:
today, a plain-text "מאשר" approval can be resolved by either of two structurally different code
paths — the legacy `_pending_approvals` dict (which **recursively re-invokes the entire Agent
pipeline**, costing 2 extra Anthropic calls) or the `ActionGateway`/`route_combined_word` path
(which replays the already-captured tool call with **0** Anthropic calls) — and which one fires is
determined by which store originally queued the action, not by turn-level policy. This is the same
class of "multiple non-unified pending-state stores" problem `PHASE_2_SHADOW_PLANNING_GATE.md`
§1.5 already documents structurally (four coexisting pending-state stores: `_pending_approvals`,
`event_bus.PendingActionsStore`, `ActionGateway`'s `ExecutionLedger`/`ActionContract`,
`event_bus.BatchQueueStore`). This audit adds a **cost** dimension to that existing structural
finding: the store that resolves a given turn doesn't just affect correctness/ownership, it
determines whether that turn costs 0 or up to 4 Anthropic calls.

---

## Method

Five parallel read-only research passes over `app.py`, `core/router/`, `context.py`, `tools/`,
`core/action_gateway.py`, `core/action_contract_repository.py`, `event_bus.py`, `session_store.py`,
and `core/runtime_schema_provider.py`. All findings below are cited `file:line` against the
baseline commit above. No code was changed, no branch was opened for the audit itself, no PR was
filed for the audit work beyond attaching this document.

---

## 1. Per-turn call maps

**Legend:** `ANT`=Anthropic call · `AT`=Airtable HTTP call · `TG`=Telegram API call ·
`LOCAL`=in-process, not external

### Flow 1 — Create task, no approvals pending

| # | Call | Type | file:line | Classification |
|---|------|------|-----------|-----------------|
| 1 | `resolve_identity()` — webhook gate | LOCAL* | `app.py:4359` | duplicate read (see #2) |
| 2 | `resolve_identity()` — inside `run_agent()`, same channel/id | LOCAL* | `app.py:2582` | **duplicate read** — identical call to #1, result discarded |
| 3 | Session snapshot `_ls.get(chat_id)` | AT (0 if RAM-warm) | `app.py:2621` | premature — a create-task turn doesn't need funnel session state |
| 4 | Business Memory full-table GET (unbounded, `limit=5` is dead code) | AT | `context.py:272` → `cmd_update.py:539-574` → `tools/airtable_tools.py:254-299` | **premature context loading** |
| 5 | (conditional) `resolve_business_memory_domain()` → Meta API schema fetch if TTL(300s) expired | AT | `cmd_update.py:403` → `core/runtime_schema_provider.py:69-75,127` | cacheable metadata |
| 6 | Anthropic call #1 — propose `tool_use` (e.g. `airtable_add`) | ANT | `app.py:3174` | required business operation |
| 7 | `tool_registry.enforce()` + `action_validator.validate_action()` | LOCAL | `app.py:3276`, `action_validator.py` | required safety |
| 8 | `requires_approval=True` → queue (legacy `bus.request_approval`, RAM-only) | LOCAL | `app.py:3292`→`app.py:1101,1138` | required business operation |
| 9 | `cost_watchdog.log_usage()` (JSONL+Airtable) for call #1 | AT | `app.py:3190-3196` | observability only |
| 10 | Anthropic call #2 — final text ("נשלח לאישור…") | ANT | `app.py:3174` (loop iteration 2) | **target for elimination** — see §2 |
| 11 | `cost_watchdog.log_usage()` for call #2 | AT | `app.py:3190-3196` | observability only |
| 12 | C54 suppression + A32 `verify_execution`/`sanitize_agent_response` | LOCAL | `app.py:3217-3241`, `3464`, `3506-3509` | required safety |
| 13 | Telegram `sendMessage` with approve/reject inline keyboard | TG | `app.py:1344-1349` | required business operation |

Confirmed external calls: 2 ANT + 2-4 AT + 1 TG ≈ 5-7. (*Identity resolution's own internal
cost — whether it hits Airtable for tenant lookup — was not directly instrumented by this pass;
flagged for follow-up, see §7.)

### Flow 2 — Create task while approvals already pending

Same as Flow 1, plus a Pending-Approval Gate check (`app.py:2665-2745`, required safety) and a
`find_live_contracts()` call for this user (RAM-cached, `core/action_gateway.py:462-500`,
cacheable metadata). No extra Anthropic calls.

### Flow 3 — "מה ממתין לאישור?"

Fully deterministic: `_PENDING_QUERY_RE` short-circuits before router/`build_context`
(`app.py:194-198`, checked `2813`) → `find_live_contracts()`/`describe_pending_queue()`
(RAM-cached, `core/action_gateway.py:2291-2331`) → Telegram `sendMessage`.
**0 Anthropic, 0-1 Airtable, 1 Telegram.** The universal session snapshot at `app.py:2621` still
fires unconditionally before this intent is even known — premature/unnecessary for this flow.

### Flow 4 — "מאשר" (single pending action, plain text)

Two structurally different code paths exist for this exact input, and **which one fires depends
on where the action was originally queued** — see the "Why this is filed under `turn-coordinator/`"
note above.

**Path A — legacy `_pending_approvals`/`bus` dict** (currently live default, since
`FEATURE_ACTION_GATEWAY` defaults off and `_queue_approval_detailed()` falls through to
`bus.request_approval()`, `app.py:1101,1138`):
- Matched at the **2.5 Pending-Approval Gate**, `app.py:2665-2745`, which runs *before* the 2.55
  confirm-word/ActionGateway intercept.
- Pops the entry, then **recursively calls `run_agent(pending_entry["text"], ..., _skip_approval=True)`**
  (`app.py:2736-2741`).
- This recursion re-enters the entire Agent tool loop from scratch: an Anthropic call re-proposing
  the same `tool_use`, dispatch, then a second Anthropic call for final text.
- **Cost: 2 additional Anthropic calls + 1-2 Airtable writes (dispatch) + 1 Telegram send** — on
  top of the 2 Anthropic calls already spent creating the task in Flow 1. **4 Anthropic calls
  total for create+approve.**

**Path B — ActionGateway/`route_combined_word`** (only reached if the legacy dict has no match,
or once `FEATURE_ACTION_GATEWAY`/persistence flags are on):
- `action_gateway.approve()` (`core/action_gateway.py:1751`) replays the already-captured
  `tool_name`/`tool_inputs` from proposal time — no re-invocation of the model.
- Cost: **0 Anthropic calls**, ~3 Airtable writes (status→approved, tool dispatch,
  status→completed via `ExecutionLedger.update_status`/`transition()`,
  `core/action_gateway.py:1820,2062`; each `transition()` = GET→PATCH→GET = 3 AT calls per status
  change, see §6), 1 Telegram send.

### Flow 5 — "מאשר 1" (approve by number, multiple pending)

Intercepted by `route_combined_word()` (`core/action_gateway.py:1636`), matched **before** the
legacy 2.5 gate's ambiguity logic ever engages (`app.py:2771-2782`) — multi-pending disambiguation
already always goes through the gateway path, not the recursive dict path. **0 Anthropic calls**,
N Airtable writes (1 per rejected sibling + 3 for the approved one), 1-2 Telegram calls.

### Flow 6 — Telegram approval callback (button tap)

Dedicated handler, `_handle_approval_callback_impl()` (`app.py:1991`), invoked directly from the
webhook dispatcher (`app.py:4319`) — never touches `route_request()`, `build_context()`, or the
Agent loop. **0 Anthropic, ~2-3 Airtable, 3 distinct Telegram calls** (`answerCallbackQuery`,
`sendMessage`, `editMessageText`).

### Flow 7 — Reconfirmation: "מאשר" → "כן"

Both legs independently hit the confirm-word short-circuits (2.55 block /
`route_confirmation_word` FSM) — neither leg reaches the Agent. **0 Anthropic calls across both
messages.** Distinct from Flow 4 Path A — this FSM does not recurse through `run_agent()`.

### Flow 8 — Action execution after approval

Bundled into whichever approve path fired (Flow 4/5/6): `dispatch_tool()` write (AT, required
business operation), `audit_log_airtable()` (currently `logger.info`, same level as raw httpx
logs — needs verification whether it's log-only or itself an Airtable write, see §9), A32
`verify_execution()` (LOCAL), contract status → "executed" via `transition()` (AT x3 in the
gateway path), Telegram confirmation `sendMessage` (TG).

---

## 2. Anthropic tool-loop cost

`MAX_TOOL_TURNS = 3` (`app.py:77`), single `client.messages.create()` call site (`app.py:3174`),
inside `while True:` (`app.py:3173`). A normal single-action turn costs **2** Anthropic calls by
design: propose `tool_use`, then finalize into natural-language text once the tool result is
known. `BatchQueue`/deferred tools do **not** cost an extra Anthropic call in the same turn —
deferred entries are promoted later by replaying the captured `tool_name`/`tool_inputs` verbatim
(`app.py:1430-1466`), again with 0 Anthropic calls. C54 suppression and A32
`verify_execution`/`sanitize_agent_response` are pure post-processing of the already-received
response — zero network calls (confirmed: no `anthropic`/`messages.create` references anywhere in
`core/anti_hallucination.py`).

**Proposal to cap a normal single-action turn at 1 model call:** template the confirmation text
locally for the common "single mutating tool, no further tool_use needed" case (e.g.
`format_confirmation(tool_name, tool_result)` with a static Hebrew phrase table), mirroring the
exact "replay captured tool_call, no re-invocation" pattern already proven safe by BatchQueue
promotion and the `ActionGateway.approve()` path. Reserve the second Anthropic call for cases that
need genuine natural-language synthesis. This does not weaken approval enforcement:
`tool_registry.enforce()`/`action_validator` already run before any dispatch regardless of how the
confirmation text is produced.

---

## 3. Lazy context loading

Business Memory (`context.py:267-276` → `cmd_update.py:539-574`, unbounded/paginated,
`limit=5` is dead code) and the session snapshot (`app.py:2621`) both load unconditionally,
**before** it's known whether the turn will reach the Agent at all. ToolAvailability
(`context.py:82-104`) is already correctly flag-gated (`FEATURE_TOOL_AVAILABILITY_FILTER`,
default off) and not currently firing. **Proposal:** move Business Memory load and the session
snapshot behind the router's handler decision — only load them once `route.handler == Handler.AGENT`
(or equivalent) is confirmed, not before. Gateway-owned approval turns (Flows 3-7) already mostly
avoid loading Agent context today (`build_context()` itself is never called on those paths) — the
one exception is the session snapshot at `app.py:2621`, which fires on every turn regardless.

---

## 4. Deterministic approval routing

Confirmed: none of the six approval-reply intents (pending-query, approve, reject,
approve/reject-by-number, yes/no reconfirmation, Telegram callback) exist in the router's `Intent`
enum (`core/router/route_decision.py:17-102`) — all six are matched by regex/frozenset directly in
`app.py`, and `RouteDecision.llm_classified` is hard-coded `False` (`router.py:175`). Deterministic
routing already occurs before Agent context construction for 5 of 6 — the one exception is Flow 4
Path A's recursive re-entry into `run_agent()`, which is the single highest-leverage fix identified
in this audit (§1, §2).

---

## 5. Airtable schema caching

A normal `airtable_add` (Flow 1's create-task write) does **not** hit the live Meta API today —
`validate_airtable_fields()` (`tools/airtable_gateway.py:384`) uses only the in-memory
`schema_cache.json`-seeded cache, since `FEATURE_AIRTABLE_RUNTIME_SCHEMA_PROVIDER_STATE` defaults
to `"off"` (`tools/airtable_gateway.py:141-142`). Two call sites are unconditional/uncached
regardless of that flag: `tools/airtable_gateway.py:588,620` (`resolve_table_and_field_ids()`,
`get_table_schema()`). **Proposal:** wrap both in the same TTL-cache pattern
`core/runtime_schema_provider.py` already implements (300s TTL, stale-serve fallback), with
invalidation triggered by an `UNKNOWN_FIELD_NAME`/`422` response.

---

## 6. ActionContract repository round trips

`core/action_contract_repository.py`'s `transition()` (`:199-281`) is GET → PATCH → GET: a
pre-write read (compare-and-swap emulation, genuinely required for concurrency safety — Airtable
has no native compare-and-swap, `:11-17,174-183`), the PATCH, and a **read-back to verify the
write landed** (`:275-280`). **Proposal:** if the PATCH response body already carries the written
status/version fields, use it directly instead of the trailing GET — cutting each `transition()`
from 3 round trips to 2 without weakening the conflict check. This subsystem is currently dormant
(`FEATURE_ACTION_CONTRACT_PERSISTENCE`/`FEATURE_ACTION_GATEWAY` both default off) — the live
Telegram approval path uses `event_bus.py`'s in-memory `PendingActionsStore` instead, which has
zero Airtable round trips of its own.

---

## 7. Session operations

`PersistentSessionStore` reads are RAM-first (cache-warm = 0 Airtable calls); every write is
unconditionally 1-2 Airtable HTTP calls (`session_store.py:459-541`). A confirm-word ("מאשר") turn
triple-fetches the same `chat_id`-keyed lead-preview record within one turn
(`core/lead_candidate_handler.py:1433` then a redundant re-fetch at `:1475`) — a genuine, safely
removable duplicate. Pending-queue queries and Telegram callbacks correctly do not touch
`session_store` for unrelated business context today, beyond the universal snapshot noted in §3.

---

## 8. BatchQueue

Pure in-RAM (`event_bus.py:200-235`), zero Anthropic-call cost of its own (promotion replays
captured tool calls verbatim). Its real cost is lifecycle risk, not raw call volume: approval
ambiguity (multi-pending disambiguation overhead) and rejected-action resurrection (a deferred
item can surface as an unexpected new confirmation prompt after the user's attention has moved
on). **Recommended default for this phase: "one user message → at most one proposed write."** This
would not reduce LLM calls (already ~0 marginal cost) but would reduce contract creation, session
writes, and eliminate approval ambiguity/resurrection risk for the common case, at the cost of
requiring multi-action requests to be split across turns. `tool_registry.enforce()`/
`action_validator` are unaffected either way.

---

## 9. Logging noise

`resolve_identity()` fires twice per plain-text turn with identical arguments
(`app.py:4359` and `app.py:2582`, the second discarding the first's result), producing 3
"Identity Resolved"-family log lines per turn. `audit_log_airtable()`
(`tools/airtable_security.py:149-174`) is currently at the same `logger.info` level as raw httpx
success logs — fully duplicative today, not already a quieter dedicated channel. No
`logging.getLogger("httpx")` level override exists anywhere in the repo. Lifecycle/claim/write/
failure logs (`event_bus.py`, `action_validator.py`, `core/action_gateway.py`,
`core/claim_gate.py`) are correctly low-cardinality and should not be touched by any noise
reduction.

---

## Requirement for the next implementation phase

Per the phase order in `TURN_COORDINATOR_BEHAVIOR_CONTRACT_V1.md` ("סדר היישום"), Phase 2 Shadow
planning is complete but its runtime (`core/turn_coordinator_shadow.py`) is **not yet
implemented** (`PHASE_2_SHADOW_PLANNING_GATE.md` line 4, §11), and Phase 3 (narrow BUG-130
enforcement) is blocked behind Phase 2's Shadow Exit Criteria (§8 of the frozen contract). This
audit adds the following as an explicit, owner-reviewable requirement for **whichever phase is
implemented next** (Phase 2 Shadow runtime completion, or Phase 3, per owner decision on
sequencing):

1. **Close the Flow 4 Path A recursion gap** (§1, §2 above) as part of that phase's scope — a
   turn resolved by the legacy `_pending_approvals` dict must not re-invoke `run_agent()`
   recursively; it must replay the already-captured tool call the same way
   `ActionGateway.approve()` and BatchQueue promotion already do. This is not a new mechanism —
   it is extending an existing, already-proven pattern to the one path that still lacks it, and it
   directly reduces `TurnEnvelope`/Shadow-decision noise from an inflated Anthropic-call count on
   what should be a 0-Anthropic-call turn class.
2. **Any Shadow-decision or Coordinator-selected-handler computation for approval-reply turns**
   (pending-query, approve, reject, approve/reject-by-number, yes/no reconfirmation, Telegram
   callback) must record which of the two Flow-4 paths (legacy dict vs. `ActionGateway`) actually
   resolved the turn, and its Anthropic-call count for that turn, as an observability field —
   consistent with `PHASE_2_SHADOW_PLANNING_GATE.md` §5's `ShadowDecisionRecord` schema
   philosophy (comparison metadata, not inference).
3. **Lazy-load Business Memory and the turn-start session snapshot behind the handler decision**
   (§3 above) as part of the same phase that formalizes handler selection — since the Coordinator
   (or its Shadow) is exactly the component that will know, structurally, whether a given turn
   needs Agent context before any context-loading code runs.
4. Items in §5-§9 above (schema-call caching, `ActionContract.transition()` round-trip reduction,
   session duplicate-fetch removal, BatchQueue default, logging noise) are independent of
   TurnCoordinator phase sequencing and may be picked up opportunistically, but should not be
   used to justify deferring items 1-3, which are the ones with direct TurnCoordinator-phase
   relevance.

Any PR implementing items 1-3 must produce its own Cross-Layer Impact Matrix per
`CROSS_LAYER_AUTHORITY_CONTRACT_V1.md` §2 before code is written — this requirement note does not
pre-approve implementation, it only ensures the optimization is not lost or silently deferred once
phase-implementation work begins.
