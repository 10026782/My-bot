# TC6 — `app.py` Integrator Patch Spec

**Status:** implemented, **not yet merged to `origin/main`** (CodeRabbit
review round, PR #569 — do not read this as "applied in production"; per
this repo's own Rule 15/GOVERNANCE_RULES.md, that claim requires merge +
deploy + production verification, none of which have happened yet).
`app.py` is Integrator-only per `PARALLEL_IMPLEMENTATION_WORKSTREAMS.md`'s
file ownership map — the TC6 WS2 branch (`claude/tc6-explicit-reply-
ownership`, merged as PR #566) did not edit this file directly. This
document was the isolated patch spec; the integrator cutover implementing
it against `app.py` is Draft PR #569
(`claude/tc6-integrator-app-cutover`), based on `origin/main` `e60d9ce`
(after PR #566/#567), once WS2's `core/action_gateway.py` change
(`reply_ownership_for_contract()`) had already merged. Kept as the design
record — the code blocks below reflect the as-implemented shape on that
open PR (including the round-3 telemetry correction just below and the
round-4 rollback/CodeRabbit fixes), not merely a proposal — but "as-
implemented" here means "in PR #569's branch," not "on `origin/main`."

**Base:** `origin/main` `38d9226` (original spec-authoring base, same as
the WS2 branch). The integrator cutover itself is based on the later
`e60d9ce` tip — see Status above.

**Cross-Layer Authority Contract gate:** this document is subject to
`docs/architecture/CROSS_LAYER_AUTHORITY_CONTRACT_V1.md` — the mandatory
gate for any change touching TurnCoordinator, the F52/Phase 4C Action &
Tool Contract layer, or the Durable Atomic Approval layer
(`ActionContract`/`ActionGateway`), directly or indirectly. See §0 below
for the completed Cross-Layer Impact Matrix (added on PR #569's
CodeRabbit review round, per explicit owner instruction — "write the full
Impact Matrix now" — after the gap was flagged by an automated review;
this gate had not been checked against this specific document on any
earlier TC6 round).

---

## 0. Cross-Layer Impact Matrix (`CROSS_LAYER_AUTHORITY_CONTRACT_V1.md` §2)

Scope of this matrix: the integrator cutover itself — commits `d58f018`
(initial cutover) through the latest CodeRabbit-review commit on PR #569
(`claude/tc6-integrator-app-cutover`). Diff footprint: `app.py`,
`test_tc6_app_reply_ownership.py`, this document. No other file is part of
this PR's diff (verified: `git diff --name-only origin/main...HEAD` on the
PR branch lists exactly these three paths).

### שכבה 1 — Core Reasoning / BUG-104

**touched:** not touched.

- **input impact:** none — this PR reads no BUG-104 output (no
  `leads_reasoning_projection`/`FEATURE_CORE_REASONING_LEADS_STATE`/
  `leads_adapter` symbol appears anywhere in the diff).
- **output impact:** none — this PR produces no signal Layer 1 consumes.
- **authority impact:** none — Layer 1's ownership of business
  state/evidence/phase/confidence is untouched; this PR only ever reads/
  writes approval-lifecycle (`ActionLifecycleResult`) and reply-ownership
  state, a Layer 4/Layer 2 concern, never Layer 1's.
- **shared identifiers:** none found.
- **invariants:** n/a — no Layer 1 invariant is read or relied on by this
  change.
- **failure semantics:** n/a — Layer 1 cannot fail as a result of this
  change; it is never called.
- **observability:** n/a.
- **cross-layer tests:** n/a — no cross-layer coupling to prove.

**Proof of non-impact:**
1. **grep evidence:** `git diff origin/main -- app.py test_tc6_app_reply_ownership.py | grep -iE "leads_reasoning_projection|FEATURE_CORE_REASONING_LEADS_STATE|leads_adapter|core_reasoning|BUG-104|build_reasoning_projection"` → no output.
2. **unchanged-tests evidence:** `core/` pytest suite (includes the BUG-104
   test families — `test_bug104_*.py` live at repo root, not under `core/`,
   but were included unmodified in the full root `test_*.py` sweep both
   before and after this PR's commits) — 189/189 `core/` pytest cases pass
   unchanged; root-sweep result for the `test_bug104_*.py` files:
   unchanged pass/fail status pre- and post-PR (all passing, none of them
   is among the 3 pre-existing/unrelated failures documented in the PR's
   Test Results section).
3. **no-new-coupling evidence:** `app.py`'s diff adds zero new `import`
   statements referencing `core/leads_reasoning_projection.py`,
   `core/adapters/leads_adapter.py`, or any other BUG-104 module.

### שכבה 2 — TurnCoordinator

**touched:** indirectly.

- **input impact:** none directly — this PR does not read from any
  `TurnCoordinator`-owned signal (there is no `class TurnCoordinator` in
  the repo — `grep -rl "class TurnCoordinator"` returns zero files, per
  `CROSS_LAYER_AUTHORITY_CONTRACT_V1.md` §1's own finding, unchanged by
  this PR). The de-facto owners of turn precedence/routing today —
  `core/router/router.py::route_request()` and
  `core/lead_candidate_handler.py::handle_lead_candidate()` — are not
  touched by this diff at all.
- **output impact:** yes, indirectly. This PR changes the **value**
  passed into an *existing, pre-existing* call to
  `core.turn_envelope.build_ownership_signal(..., reply_owner=...)` (the
  call site itself, and the import line, are unchanged by this diff — only
  what feeds its `reply_owner` argument changes, from a sentinel-presence
  boolean to a typed-projection-derived value, see §3). It similarly
  changes the value of the pre-existing `_out_meta["reply_owner"]`/
  `_out_meta["canonical_state"]` telemetry keys that `run_agent()` already
  populated before this PR (Branch A's shape is unchanged; Branch B is new
  — see "shared identifiers" below). Both are read by whatever downstream
  observability/telemetry consumers (`tma_api.py` panels, logs) already
  consumed those exact keys before this PR — no new consumer, no new key
  shape *added by this PR* to `OwnershipSignal` itself.
- **authority impact:** none on the *formal* layer (there is nothing to
  affect — no `TurnCoordinator` class exists). On the **interim,
  de-facto** turn-scoped reply-ownership mechanism this PR modifies (the
  `_gateway_owned`/single-speaker early-return inside `run_agent()`, gated
  by `FEATURE_SINGLE_SPEAKER_APPROVAL_UX`, pre-existing since before TC6):
  authority *narrows*, it does not expand — Branch A can now only claim
  ownership from a real, exact-contract-projected `ActionLifecycleResult`
  (never a bare sentinel-presence heuristic, closing BUG-162 §2.4's
  duplicate-authority gap), and the new Branch B explicitly claims **no**
  authority at all (a safety stop, never `reply_owner="gateway"`). No new
  parallel authority is introduced — this PR's whole design correction
  (§ above) exists specifically to prevent exactly that.
- **shared identifiers:** `_out_meta["canonical_state"]` — pre-existing
  key (Branch A: already existed before this PR, populated from the real
  `ApprovalLifecycleResult.canonical_state` value, a Layer 4 enum: e.g.
  `"pending"`/`"completed"`/`"rejected"`/`"approved_processing"`/
  `"pending_conflict"`/`"no_contract"`/`"multiple_pending"`, see
  `core/action_gateway.py` `build_approval_lifecycle_result()`). Branch B
  (new, this PR) sets the **same `_out_meta` key** to a new, app.py-local
  string value, `"ownership_verification_failed"` — verified via grep
  (`grep -n 'canonical_state' core/action_gateway.py`) to **not** collide
  with any existing Layer-4 `canonical_state` enum member. This is a
  same-name, disjoint-value-space reuse (not a true collision today), but
  it is exactly the kind of ambiguity this gate's "shared identifiers"
  field exists to surface: a future reader could reasonably assume
  `_out_meta["canonical_state"]` is always a Layer-4
  `ApprovalLifecycleResult.canonical_state` echo, and Branch B's value
  breaks that assumption. **Flagged, not renamed** — renaming `_out_meta`'s
  schema is out of this PR's narrow rollback-fix/CodeRabbit-fix scope, but
  should be considered before any future consumer starts pattern-matching
  on this field. No other shared identifier (class name, field name, table
  name, flag name) crosses a layer boundary in this diff.
- **invariants:** the interim mechanism's own invariant — "the Agent never
  becomes final speaker for a Gateway-owned or ownership-unverifiable
  turn" — is preserved and, for the Branch B case, newly established (it
  did not exist before this PR; a projection-read failure previously had
  undefined tool-loop behavior). Verified by `test_tc6_app_reply_
  ownership.py` tests 1-2 (Branch A) and 7-8 (Branch B): exactly one Claude
  API call, hard early return, before `tool_calls_made` increments.
- **failure semantics:** Branch B **is** the newly-defined failure
  semantics for this exact case (ownership-projection read failure) — see
  Layer 4 below for what "failure" means at its source. At this layer, a
  Layer-4 read failure now fails **closed** (safety stop, no Agent
  continuation) rather than previously-undefined behavior.
- **observability:** `logger.warning("[TC6] ownership_verification=failed
  ...")` (new, this PR's CodeRabbit-round fix) plus the pre-existing
  `OwnershipSignal`/`evidence_finalizer_shadow` mechanisms, now also
  invoked on the Branch B path (also new, same round — see the RP5 guard
  section below for why).
- **cross-layer tests:** `test_tc6_app_reply_ownership.py` — the entire
  file is a Layer 2/Layer 4 boundary test: it proves the interim
  reply-ownership mechanism (Layer 2 concern) correctly derives its
  decision from, and only from, a real Layer-4 `ActionLifecycleResult`,
  never inventing one (test 16, structural grep guard) and never
  substituting sentinel presence for it (test 13).

### שכבה 3 — F52 / Phase 4C Action & Tool Contract

**touched:** not touched.

- **input impact:** none — this PR reads `ToolMeta`/`enforce()`/
  `get_tool_meta()` only through pre-existing, unmodified call sites
  (`meta.requires_approval` checks already existed before this PR).
- **output impact:** none — no change to tool definitions, capabilities,
  policy, handler/tool mapping, or the C53a result contract
  (`{ok, tool, external_id, evidence, user_message}`).
- **authority impact:** none — this PR does not touch `tool_registry.py`,
  `tools/schemas.py`, `tools/dispatcher.py`, `compose_status_reply()`, or
  `FEATURE_UNIFIED_STATUS_FORMATTER`.
- **shared identifiers:** none found.
- **invariants:** n/a.
- **failure semantics:** n/a.
- **observability:** n/a.
- **cross-layer tests:** n/a.

**Proof of non-impact:**
1. **grep evidence:** `git diff origin/main -- app.py test_tc6_app_reply_ownership.py | grep -iE "tool_registry\.py|tools/schemas\.py|tools/dispatcher\.py|compose_status_reply|FEATURE_UNIFIED_STATUS_FORMATTER|ToolMeta\("` → no output.
2. **unchanged-tests evidence:** `test_action_gateway.py` (43/43,
   unchanged), `smoke_tests.py`'s "Tool registry / dispatcher sanity"
   check (unchanged pass) — both exercise Layer 3 surface area and stay
   green, byte-identical result before/after this PR's commits.
3. **no-new-coupling evidence:** zero new imports from `tool_registry.py`,
   `tools/schemas.py`, or `tools/dispatcher.py` in this diff.

### שכבה 4 — Durable Atomic Approval

**touched:** indirectly.

- **input impact:** this PR's producer (`_queue_approval_detailed_impl()`)
  now additionally *reads* `ActionGateway.reply_ownership_for_contract
  (contract_id)` — a method that already existed, merged, tested (19/19)
  on PR #566 — gated behind `FEATURE_SINGLE_SPEAKER_APPROVAL_UX` (this
  PR's rollback fix). No new input signal is defined; an existing one is
  newly consumed, conditionally.
- **output impact:** none on Layer 4 itself — `ActionContract.status`,
  the atomic-claim mechanism, and `ActionGateway`'s own return contracts
  are all unchanged (verified: `core/action_gateway.py`,
  `core/action_contract_repository.py`,
  `core/action_gateway_atomic_executor.py`,
  `core/router/ownership_contracts.py` all show zero diff against
  `origin/main` — `git diff --stat origin/main -- <those four files>` is
  empty). Layer 4 CONSUMES nothing new from this PR either.
- **authority impact:** none — `ActionContract`'s lifecycle, the
  single-live-contract invariant, and atomic-claim exclusivity are all
  unchanged. This PR only ever *reads* Layer 4's canonical projection; it
  never writes an `ActionContract`, never mutates `status`, never
  fabricates an `ActionLifecycleResult` in `app.py` (test 16, structural
  grep proof: `"ActionLifecycleResult(" not in <app.py source>`).
- **shared identifiers:** `ActionLifecycleResult`/`ActionContract` names
  are referenced (imported/read) but never redefined — no identifier-
  squatting (prohibition #9). See Layer 2's "shared identifiers" entry
  above for the one same-name/disjoint-value `_out_meta["canonical_state"]`
  note (an app.py-local telemetry key, not a Layer 4 class attribute).
- **invariants:** "`ActionLifecycleResult` only ever comes from a real
  `ActionContract` through the canonical WS2 projection, never fabricated"
  — this PR's own central design rule, verified structurally (test 16)
  and behaviorally (tests 7-8, 14: a read failure/unexpected `None`
  propagates as `None`, never a synthetic result). "Exact-contract
  correlation, never inferred from latest-contract-for-user" — verified
  by test 6 (stale/unrelated contract cannot own the current turn).
- **failure semantics:** a `reply_ownership_for_contract()` read failure
  (exception or unexpected `None`) is Layer 4's own, pre-existing failure
  mode (unchanged by this PR — `ExecutionLedger.find_by_id()`'s "lookup
  failures propagate, clean not-found returns `None`" contract, from
  WS2/PR #566, is not touched here). What's new in **this** PR is purely
  how Layer 2 *reacts* to that pre-existing failure mode (Branch B) — the
  failure semantics of Layer 4 itself are unchanged. Notably (raised by
  this matrix, not previously documented): Branch B does **not**
  revoke/cancel the underlying `ActionContract` it couldn't verify
  ownership for — the contract remains live/`pending` in the ledger,
  untouched. This is intentional (a read/verification failure is not
  evidence the contract itself is invalid — see the in-code comment added
  this round, and `test_tc6_app_reply_ownership.py`'s R1-on assertions,
  which confirm the returned `contract_id` still resolves to a real,
  still-`pending` contract with no cleanup performed).
- **observability:** new, this round: the `logger.warning("[TC6]
  ownership_verification=failed contract=%s ...")` line and the
  RP4 `observe_shadow_finalizer()` call newly added to the Branch B path
  (see RP5 guard below) both surface the `contract_id` this failure
  occurred against — closing the "Branch B is invisible in production"
  gap CodeRabbit flagged.
- **cross-layer tests:** same as Layer 2's entry — `test_tc6_app_reply_
  ownership.py` is the boundary test for this exact Layer 2/Layer 4
  relationship. Additionally, `core/test_tc6_reply_ownership.py` (WS2,
  unchanged by this PR, 19/19 passing) is the boundary test for Layer 4's
  own `reply_ownership_for_contract()` method in isolation.

### Proof of non-impact (Layers 1 and 3)

See each layer's own "Proof of non-impact" block above (Layer 1, Layer 3)
— both provide grep evidence, unchanged-tests evidence, and no-new-
coupling evidence, per §5 of the gate.

### Cross-Cutting Guard — RP5 Evidence Finalization (§1.5)

**applies:** yes. This PR's Branch A/Branch B early returns both produce
user-facing "action-status"-adjacent text (a pending/conflict/rejection/
completion message, or the Branch B safety-stop message) and both are, by
construction, exempt from the normal `sanitize_agent_response()`/RP4
evidence-classification path that runs later in `run_agent()` (the early
`return` happens before that code is ever reached) — squarely the
"reply grounding" and "ניסוח success/failure/pending הפונה למשתמש"
triggers listed in §1.5.

**How this PR interacts with the guard:** it does not invent a new
grounding-check or evidence classifier — it reuses the existing,
shadow-only, non-blocking RP4 mechanism (`core.turn_evidence.
observe_shadow_finalizer()`, already called by Branch A before this PR).
**Finding surfaced while completing this matrix (fixed this round, not
merely documented):** before this fix, Branch B's early return skipped
`observe_shadow_finalizer()` entirely (unlike Branch A) — meaning Branch B
turns were completely invisible to RP4's shadow evidence-classification
population, the exact anomaly-case population RP4/RP5 exist to eventually
measure and (once un-blocked) enforce against. Fixed by adding the
identical `observe_shadow_finalizer(..., approval_prompt_sent=bool(
_ownership_verification_failed_entry.get("owner_notified")))` call to the
Branch B path, writing into the same `_out_meta["evidence_finalizer_
shadow"]` key Branch A already used — no new mechanism, no new
`_out_meta` shape, RP4/RP5 remain shadow-only and non-blocking exactly as
before this PR.

---

**Design correction this spec implements** (owner-approved, supersedes the
TC6 preflight's original §E, which proposed `ActionGateway.approval_status()`
as the enforcement source): `approval_status()` is user-scoped — it answers
"what is this identity's latest/live contract," which can silently point at
a different contract than the one this turn actually touched. TC6 must
preserve **exact turn-to-contract correlation**. The canonical rule:

- `__approval_queued__` / the current-turn structured result = **correlation
  evidence only** (proves *a* contract touch happened this turn).
- The exact `contract_id` on that entry = the identity of the lifecycle
  action this turn actually touched.
- `ActionLifecycleResult` projected from that **exact** contract (via the new
  `ActionGateway.reply_ownership_for_contract(contract_id)`, WS2,
  `core/action_gateway.py`) = the canonical reply-ownership authority.
- `ActionLifecycleResult` must **only** ever be produced from a real
  `ActionContract` through that canonical projection — never fabricated
  inline by a caller as a fallback.
- **Review round 2 correction:** a read failure or unexpected `None` from
  the canonical projection is not just "return some existing failure dict
  from the producer" — that alone does not stop the Agent from being
  invoked again, because `run_agent()`'s tool loop only early-returns when
  its `_gateway_owned` derivation matches, and a generic failure dict
  (no `action_lifecycle_result`, no `reply_owner`) does not match it. TC6
  must therefore distinguish, structurally, at the tool-loop level:
  - **Branch A — canonical Gateway ownership**: a correlated current-turn
    approval entry with a real `ActionLifecycleResult` for its exact
    `contract_id` and `reply_owner == "gateway"` → the existing
    Gateway-owned early return (unchanged shape, see §2).
  - **Branch B — correlated approval turn, ownership unverifiable**: a
    correlated current-turn approval entry exists (a real contract was
    touched), but the canonical ownership projection for that exact
    contract could not be confirmed. This is a **safety stop, not a second
    reply-ownership authority** — it fabricates no `ActionLifecycleResult`,
    claims no `reply_owner="gateway"`, and never silently defaults to Agent
    ownership. It fails closed with its own early return, structurally
    identical in *shape* to Branch A's, before the Agent can be invoked
    again — see §1d/§2.

---

## 1. `_queue_approval_detailed_impl()` — stop hardcoding `reply_owner` per branch

Every return branch that already holds a **verified canonical contract_id**
this turn (i.e. every branch that already builds `_pending_lifecycle` /
`_generic_lifecycle` / `_lifecycle_result` via the legacy
`build_approval_lifecycle_result()` path today) must also derive a typed
`action_lifecycle_result` from that **exact** contract_id, and the scalar
`"reply_owner"` key must be *read from* that typed result, never
independently hardcoded.

### 1a. `existing_pending_blocks_agent` (enforce branch, current `app.py:1504-1520`, and shadow branch `app.py:1609-1625`)

```python
# לפני (שני הענפים, צורה ללא שינוי כיום):
_pending_lifecycle = build_approval_lifecycle_result(
    _gw.find_contract(_gw_result.contract_id),
    canonical_state="pending_conflict",
)
return {
    "message": _pending_lifecycle.safe_user_message,
    "contract_id": _gw_result.contract_id,
    "ok": False,
    "terminal_outcome": "APPROVAL_QUEUE_ERROR",
    "action_tool": tool_name,
    "created_this_turn": False,
    "owner_notified": False,
    "reply_owner": "gateway",              # <- מוצפן-קשיח באופן עצמאי
    "lifecycle_result": _pending_lifecycle,
    "final_response_count": 1,
}
```

```python
# אחרי:
_pending_lifecycle = build_approval_lifecycle_result(
    _gw.find_contract(_gw_result.contract_id),
    canonical_state="pending_conflict",
)
_action_lifecycle_result = _ownership_for_contract_or_none(_gw, _gw_result.contract_id)
if _action_lifecycle_result is None:
    # תיקון-סקירה TC6 סבב 2 (Branch B): סמכות הבעלות עצמה לא ניתנה
    # לאישור עבור contract_id שהקריאה הזו כבר מאמינה שהוא אמיתי. אין
    # להשתמש כאן ב-_orphan_cleanup_failure_response() — הניסוח שלה
    # ("אירעה שגיאה בעת ניסיון לבטל בקשת אישור") שגוי סמנטית למקרה הזה
    # (שום דבר מעולם לא בוטל). במקום זאת, מחזירים את אותו טקסט ישן
    # כבר-מחושב וכבר-בטוח (_pending_lifecycle.safe_user_message, ללא
    # תלות בהצלחת הבדיקה הקנונית החדשה) יחד עם סמן terminal_outcome
    # פנימי-בלבד ומובחן, כדי של-tool loop (§2) יוכל לזהות את זה
    # כ"turn מתואם של אישור, בעלות לא-ניתנת-לאימות" ולהיכשל-בסגירה
    # לפני סבב Agent נוסף — לעולם לא ActionLifecycleResult מומצא,
    # לעולם לא reply_owner="gateway" מומצא, לעולם לא נפילה שקטה
    # לבעלות Agent.
    return {
        "message": _pending_lifecycle.safe_user_message,
        "contract_id": _gw_result.contract_id,
        "ok": False,
        "terminal_outcome": "APPROVAL_OWNERSHIP_VERIFICATION_FAILED",
        "action_tool": tool_name,
        "created_this_turn": False,
        "owner_notified": False,
        "final_response_count": 1,
        # במכוון בלי מפתחות "reply_owner" / "action_lifecycle_result" —
        # ראו §1d/§2 לאיך ה-tool loop מגיב לסמן הזה.
    }
return {
    "message": _pending_lifecycle.safe_user_message,
    "contract_id": _gw_result.contract_id,
    "ok": False,
    "terminal_outcome": "APPROVAL_QUEUE_ERROR",
    "action_tool": tool_name,
    "created_this_turn": False,
    "owner_notified": False,
    "reply_owner": _action_lifecycle_result.reply_owner,   # נגזר, לא מוצפן-קשיח
    "lifecycle_result": _pending_lifecycle,                 # ללא שינוי — מקור הטקסט הישן
    "action_lifecycle_result": _action_lifecycle_result,    # חדש — בעלות קנונית של TC6
    "final_response_count": 1,
}
```

### 1b. Generic `ok=False` (BUG-162 branch, current `app.py:1521-1575`)

```python
# לפני (קטע רלוונטי):
_generic_lifecycle = (
    build_approval_lifecycle_result(_generic_found_contract, repeated=True)
    if _generic_found_contract else None
)
return {
    "message": (...),
    "contract_id": _generic_contract_id,
    "ok": False, "terminal_outcome": "APPROVAL_QUEUE_ERROR",
    "action_tool": tool_name, "created_this_turn": False,
    **({
        "owner_notified": False,
        "reply_owner": "gateway",             # <- מוצפן-קשיח באופן עצמאי
        "lifecycle_result": _generic_lifecycle,
        "final_response_count": 1,
    } if _generic_lifecycle else {}),
}
```

```python
# אחרי:
_generic_lifecycle = (
    build_approval_lifecycle_result(_generic_found_contract, repeated=True)
    if _generic_found_contract else None
)
if _generic_lifecycle:
    _generic_action_lifecycle_result = _ownership_for_contract_or_none(
        _gw, _generic_contract_id,
    )
    if _generic_action_lifecycle_result is None:
        # אותו כלל fail-closed של Branch B כמו §1a: קיים contract מאומת
        # (_generic_found_contract), אך סמכות הבעלות עצמה לא ניתנה
        # לאישור — לעולם לא להמציא, לעולם לא ליפול לבעלות Agent, לעולם
        # לא _orphan_cleanup_failure_response() (ניסוח שגוי למקרה הזה —
        # ראו הערת §1a). משתמשת חוזרת באותו
        # _generic_lifecycle.safe_user_message כבר-מחושב וכבר-בטוח.
        return {
            "message": _generic_lifecycle.safe_user_message,
            "contract_id": _generic_contract_id,
            "ok": False,
            "terminal_outcome": "APPROVAL_OWNERSHIP_VERIFICATION_FAILED",
            "action_tool": tool_name,
            "created_this_turn": False,
            "owner_notified": False,
            "final_response_count": 1,
        }
return {
    "message": (...),
    "contract_id": _generic_contract_id,
    "ok": False, "terminal_outcome": "APPROVAL_QUEUE_ERROR",
    "action_tool": tool_name, "created_this_turn": False,
    **({
        "owner_notified": False,
        "reply_owner": _generic_action_lifecycle_result.reply_owner,
        "lifecycle_result": _generic_lifecycle,
        "action_lifecycle_result": _generic_action_lifecycle_result,
        "final_response_count": 1,
    } if _generic_lifecycle else {}),
}
```

### 1c. Success branch (current `app.py:1841-1867`)

```python
# לפני:
_lifecycle_result = _approval_gateway.lifecycle_result(_contract_id)
_final_message = _lifecycle_result.safe_user_message
...
return {
    ...,
    "reply_owner": _lifecycle_result.reply_owner,   # מה-ApprovalLifecycleResult הישן
    "lifecycle_result": _lifecycle_result,
    "final_response_count": 1,
}
```

```python
# אחרי:
_lifecycle_result = _approval_gateway.lifecycle_result(_contract_id)
_final_message = _lifecycle_result.safe_user_message
_action_lifecycle_result = _ownership_for_contract_or_none(_approval_gateway, _contract_id)
if _action_lifecycle_result is None:
    # אותו כלל fail-closed של Branch B כמו §1a/§1b: contract אמיתי
    # זה עתה נוצר (_contract_id ידוע-כאמיתי כאן — זה מסלול ההצלחה),
    # אך סמכות הבעלות עצמה לא ניתנה לאישור. לעולם לא להמציא, לעולם
    # לא ליפול לבעלות Agent, לעולם לא _orphan_cleanup_failure_response()
    # (ניסוח שגוי — שום דבר לא בוטל). משתמשת חוזרת באותו _final_message
    # כבר-מחושב.
    return {
        "message": _final_message,
        "contract_id": _contract_id,
        "ok": False,
        "terminal_outcome": "APPROVAL_OWNERSHIP_VERIFICATION_FAILED",
        "action_tool": tool_name,
        "created_this_turn": False,
        "owner_notified": _owner_notified,
        "final_response_count": 1,
    }
...
return {
    ...,
    "reply_owner": _action_lifecycle_result.reply_owner,   # מההקרנה הקנונית החדשה
    "lifecycle_result": _lifecycle_result,                  # ללא שינוי — מקור הטקסט הישן
    "action_lifecycle_result": _action_lifecycle_result,    # חדש
    "final_response_count": 1,
}
```

### 1d. New local helper and marker (add once near the top of `_queue_approval_detailed_impl()`, or as module-level `app.py` additions)

**Review correction (round 1):** the original version of this spec had this
helper fabricate a synthetic `ActionLifecycleResult` (`lifecycle_state=
"unknown"`, `reply_owner="gateway"`) whenever the exact-contract read
failed or returned an unexpected `None`. This was rejected on review —
`ActionLifecycleResult` must only ever be produced from a real
`ActionContract` through the canonical WS2 projection
(`build_action_lifecycle_result()`), never synthesized inline by a caller.

**Review correction (round 2):** the first fix made the helper return
`None` on failure, with each call site (§1a/§1b/§1c) falling back to
`_orphan_cleanup_failure_response()`. This was *itself* insufficient for
two independent reasons, both fixed here: (a) `_orphan_cleanup_failure_
response()`'s wording ("an error occurred trying to *cancel* an approval
request") is semantically false for an ownership-*read* failure — nothing
was ever cancelled; (b) more importantly, returning any producer-level
dict alone does not stop the Agent from being invoked again — the tool
loop's early return only fires when its `_gateway_owned` derivation
matches (§2), and a generic failure dict matches nothing. The corrected
design below fixes both: the helper still returns `None` — nothing else —
on any read failure, but each call site (§1a/§1b/§1c) now returns the
already-computed, already-safe legacy text tagged with a new, distinct,
internal-only marker (`APPROVAL_OWNERSHIP_VERIFICATION_FAILED`) that §2's
tool-loop logic recognizes as **Branch B** and fails closed on, structurally,
before another Agent round can run — not merely a caller-local failure
response.

```python
# אח חדש לסמני terminal_outcome הקיימים APPROVAL_QUEUE_ERROR /
# APPROVAL_QUEUE_ORPHANED / APPROVAL_QUEUE_NEVER_ATTEMPTED — פנימי-בלבד,
# לעולם לא מעוצב ישירות למשתמש (המפתח "message" נושא את הטקסט הבטוח
# הקיים בפועל; הסמן הזה נקרא רק על-ידי הלוגיקה של ה-tool-loop ב-§2
# כדי להחליט על בעלות-תשובה, בדיוק כמו שהסמנים הקיימים כבר נקראים
# על-ידי הנהלת-החשבונות של BUG-122 וחיפוש-התוצאה של PA-01).
_APPROVAL_OWNERSHIP_VERIFICATION_FAILED = "APPROVAL_OWNERSHIP_VERIFICATION_FAILED"


def _ownership_for_contract_or_none(gateway, contract_id: str):
    """TC6: נגזרת את ה-ActionLifecycleResult הקנוני לפי contract מדויק
    עבור contract_id שהקריאה הזו כבר יודעת שהוא אמיתי (הוא זה עתה
    נוצר/נמצא ע"י propose_action() באותה הפונקציה).

    מחזירה ``None`` — לעולם לא ``ActionLifecycleResult`` מומצא — בכל
    כשל קריאה. קוראים חייבים להתייחס ל-``None`` כ"החזר את הטקסט הבטוח
    כבר-מחושב של הקריאה הזו עצמה, מתויג עם
    ``_APPROVAL_OWNERSHIP_VERIFICATION_FAILED``" (ראו §1a/§1b/§1c),
    לעולם לא כרישיון להמציא מצב מחזור-חיים/אישור/ביצוע סינתטי, ולעולם
    לא כרישיון ליפול בשקט לבעלות-תשובה של ה-Agent (דרישות 10-11 של
    תיקון-העיצוב: אין המצאה, אין ברירת-מחדל שקטה ל-Agent, אין סמכות
    בעלות שנייה ב-app.py).
    """
    try:
        return gateway.reply_ownership_for_contract(contract_id)
    except Exception:
        logger.warning(
            "[ActionGateway] קריאת בעלות TC6 לפי contract מדויק נכשלה "
            "עבור contract=%s.", contract_id, exc_info=True,
        )
        return None
```

The branches that have **no contract at all** (duplicate fingerprint,
cross-channel dedup, `persistence_lookup_failed`, `bus.request_approval()`
raising with a successfully-revoked contract) are **unchanged** — they
correctly omit `reply_owner`/`lifecycle_result`/`action_lifecycle_result`
entirely today, and must keep doing so (design correction requirement 11:
no canonical contract exists → do not invent Gateway ownership). They also
never call `_ownership_for_contract_or_none()` at all — only §1a/§1b/§1c,
which already hold a verified contract_id, do. `_orphan_cleanup_failure_
response()` itself is untouched and keeps its existing callers/meaning
(genuine cleanup-uncertain cases, e.g. the `bus.request_approval()`
exception handler) — this spec does not reuse it for the ownership-read-
failure case (see the round-2 correction above for why).

---

## 2. `_gateway_owned` lookup — `run_agent()`, current `app.py:4485-4489`

```python
# לפני:
_gateway_owned = next((
    entry for entry in reversed(tool_results_log)
    if entry.get("tool") == "__approval_queued__"
    and entry.get("reply_owner") == "gateway"
), None)
```

```python
# אחרי — נגזרת גם Branch A (בעלות Gateway קנונית) וגם Branch B (turn
# מתואם, בעלות לא-ניתנת-לאימות) מאותה רשומה מתואמת:
_gateway_owned = None
_ownership_verification_failed_entry = None
_correlated_approval_entry = next((
    entry for entry in reversed(tool_results_log)
    if entry.get("tool") == "__approval_queued__"
), None)
if _correlated_approval_entry is not None:
    if _correlated_approval_entry.get("terminal_outcome") == "APPROVAL_OWNERSHIP_VERIFICATION_FAILED":
        # Branch B: contract אמיתי נגע ב-turn הזה, אך הקרנת הבעלות שלו
        # לפי contract מדויק לא ניתנה לאישור (§1a/§1b/§1c).
        _ownership_verification_failed_entry = _correlated_approval_entry
    else:
        _entry_action_lifecycle_result = _correlated_approval_entry.get("action_lifecycle_result")
        if (
            _entry_action_lifecycle_result is not None
            and getattr(_entry_action_lifecycle_result, "reply_owner", None) == "gateway"
        ):
            # Branch A: בעלות Gateway קנונית, מאושרת.
            _gateway_owned = _correlated_approval_entry
```

Everything downstream of the existing `if _gateway_owned is not None and
_flag_enabled("FEATURE_SINGLE_SPEAKER_APPROVAL_UX"):` block (`app.py:4490-
4538` — the `_lifecycle = _gateway_owned.get("lifecycle_result")` read for
`safe_user_message`, the `owner_notified` short-circuit) is **unchanged**
for Branch A. Requirement 9 (keep the boundary, change only its authority)
and requirement 1 (preserve `lifecycle_result`/`safe_user_message`
rendering) are both satisfied by touching only the derivation of
`_gateway_owned` itself, not what it gates.

**New Branch B early return**, added as a sibling check inside the SAME
`FEATURE_SINGLE_SPEAKER_APPROVAL_UX` gate as Branch A (deliberately the
same early, structural, already-established mechanism — **not** PA-01's
separate, later, text-pattern-based mechanism near the end of `run_agent()`,
which this invariant must not depend on):

**Telemetry correction (round 3, applied in the actual implementation):**
the block below originally set `_out_meta["reply_owner"] = "unverified"`.
This was rejected — `"unverified"` is not an owner, and `_out_meta`'s
`reply_owner` key must only ever carry a real, positive ownership claim
(`"gateway"`, as Branch A sets it) or be absent entirely. Branch B omits
`reply_owner` from `_out_meta` altogether and reports the read failure via
a separate, explicitly non-ownership field, `ownership_verification:
"failed"`, instead:

```python
if _flag_enabled("FEATURE_SINGLE_SPEAKER_APPROVAL_UX"):
    if _ownership_verification_failed_entry is not None:
        # Branch B — עצירת-בטיחות, לא סמכות בעלות-תשובה שנייה. שום
        # ActionLifecycleResult (אמיתי או מומצא) לא עומד מאחורי הענף
        # הזה; שום reply_owner="gateway" לא נטען; ה-Agent לעולם לא
        # מקבל סבב נוסף ב-turn הזה. משקף בדיוק את הצורה של
        # owner_notified/final_response_count של Branch A, כדי שהודעה
        # שכבר נמסרה (הגרסה של מסלול-ההצלחה ב-§1c) לעולם לא תוכפל.
        if _out_meta is not None:
            _out_meta.update({
                # במכוון בלי מפתח "reply_owner" — "unverified" אינו בעלים,
                # ו-reply_owner חייב לשאת רק טענת-בעלות חיובית אמיתית
                # ("gateway") או להיעדר לגמרי. ownership_verification="failed"
                # הוא שדה-תצפית נפרד, לא טענת-בעלות.
                "final_response_count": 1,
                "canonical_state": "ownership_verification_failed",
                "ownership_verification": "failed",
            })
        return (
            "" if _ownership_verification_failed_entry.get("owner_notified")
            else _ownership_verification_failed_entry.get("content", "")
        )
    if _gateway_owned is not None:
        # Branch A — צורה קיימת, ללא שינוי (ראו למעלה).
        ...
```

Both branches are hard `return` statements from `run_agent()` — for either
one, `tool_calls_made += 1` and the next Claude API call (`messages.append(
...)` further down the loop) are never reached, and the later `Ownership
Signal`/PA-01 code (§3, `app.py:4626+`) is never reached either, exactly as
already true for Branch A today. This is what satisfies "the Agent is not
invoked again / cannot become final speaker" and "does not rely on PA-01
being enabled" — the stop happens structurally, before PA-01's own
(separate, later, flag-gated) check would ever run.

---

## 3. `_approval_queued_this_turn` / `OwnershipSignal` — current `app.py:4629-4630` and `4670`

Two **distinct** uses of `_approval_queued_this_turn` exist in this region;
only the second is in TC6's scope:

- **BUG-122 gate** (`app.py:4578-4580`, `4585-4603`) — asks "was anything
  queued this turn at all," a legitimately weaker, presence-only question
  used to avoid a misleading "I failed" fallback. **Not part of TC6, not
  changed.**
- **Case C2 signal** (`app.py:4626-4639`) — also a presence-only detection
  signal (log-only, never blocks). **Not part of TC6, not changed.**
- **OwnershipSignal's `reply_owner`** (`app.py:4653-4672`) — this is the one
  requirement 8 targets: it must derive from the same typed
  `action_lifecycle_result`, not from sentinel presence alone.

```python
# לפני (app.py:4670, בתוך הקריאה ל-build_ownership_signal(...)):
reply_owner="gateway" if _approval_queued_this_turn else "agent",
```

```python
# אחרי — מחשבת פעם אחת, משתמשת חוזרת באותה קורלציה כמו §2 (אם הקוד
# הזה רץ אחרי שהחזרה-מוקדמת ב-§2 כבר הופעלה, החישוב-מחדש הזה מגיע רק
# כשהיא לא הופעלה — כלומר FEATURE_SINGLE_SPEAKER_APPROVAL_UX כבוי, או
# _gateway_owned היה None — כך שהוא לא יכול לסתור את §2 מבנית, מכיוון
# ששניהם קוראים את אותה רשומה באותו אופן):
_signal_correlated_entry = next((
    entry for entry in reversed(tool_results_log)
    if entry.get("tool") == "__approval_queued__"
), None)
_signal_action_lifecycle_result = (
    _signal_correlated_entry.get("action_lifecycle_result")
    if _signal_correlated_entry is not None else None
)
_signal_reply_owner = (
    "gateway"
    if (
        _signal_action_lifecycle_result is not None
        and getattr(_signal_action_lifecycle_result, "reply_owner", None) == "gateway"
    )
    else "agent"
)
...
reply_owner=_signal_reply_owner,   # היה: "gateway" if _approval_queued_this_turn else "agent"
```

This closes exactly the duplicate-authority finding from
`BUG-162_SINGLE_SPEAKER_CLOSURE_AUDIT_20260807.md` §2.4: enforcement (§2
above) and observability (this section) now both key off
`action_lifecycle_result.reply_owner`, never off two independently-computed
predicates over the same log.

---

## 4. Confirmation / cancellation / callback paths — reviewed, no change

Per the design correction's explicit instruction not to force these through
`__approval_queued__` or re-architect them for symmetry alone:

- `route_confirmation_word()` / `route_cancellation_word()`
  (`core/action_gateway.py:2052`, `2513`) pre-empt `run_agent()`'s tool loop
  entirely — they are called from `app.py` before the Agent ever gets a
  turn for that message. There is no competing Agent reply to suppress,
  because the Agent is never invoked on this path. No `__approval_queued__`
  entry, no `_gateway_owned` check applies or is needed here.
- The Telegram callback path (`_handle_approval_callback_impl()`) already
  funnels every final message through the single `_deliver_callback_final()`
  chokepoint (`app.py:2515-2574`) — structurally one writer already, by a
  different (older, working) mechanism than the `tool_results_log` sentinel
  scan.

Both were reviewed as part of this spec (TC6 preflight §B) and their
existing regression suites re-run unmodified against current `app.py`
(unaffected by the WS2-only change, since it doesn't touch `app.py`):
`test_pr1_single_speaker_approval_ux.py` (15 tests, all pass) and
`test_single_speaker_fallback_and_duplication.py` (27/27 pass) — both stay
green as the required regression check for this section. No `app.py`
change proposed here.

---

## 5. Proposed integrator-side tests (Section C, E, G — app.py-dependent)

These cannot be added to the WS2 branch (they exercise the new `app.py`
logic in §§1-3 above, which doesn't exist yet on `origin/main`). The
integrator should add a new file, e.g. `test_tc6_app_reply_ownership.py`,
containing tests of this shape once the patch above is applied — mirroring
the existing `monkeypatch.setattr(app, "_queue_approval_detailed", ...)`
pattern already used in `test_turn_coordinator_task_runtime_integration.py`:

```python
"""TC6 — app.py integration: exact-contract reply ownership. Requires the
integrator patch in TC6_APP_INTEGRATOR_PATCH_SPEC.md to be applied first."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import app
from core.router.ownership_contracts import ActionLifecycleResult


def _lifecycle(reply_owner="gateway", state="pending"):
    return ActionLifecycleResult(
        contract_ref="c1", lifecycle_state=state, approval_state=state,
        execution_state="not_started", reply_owner=reply_owner,
    )


# ── C. Single speaker ──────────────────────────────────────────────────

def test_gateway_owned_current_turn_result_suppresses_agent(monkeypatch):
    """A tool_results_log entry correlated to THIS turn's contract, with a
    canonical action_lifecycle_result.reply_owner=='gateway', must suppress
    the Agent's own text — even if the Agent's text says something else."""
    # ... build a minimal run_agent()-shaped scenario (or call the extracted
    # _gateway_owned derivation directly, if factored into a small testable
    # helper) with tool_results_log = [{
    #     "tool": "__approval_queued__", "action_lifecycle_result": _lifecycle(),
    #     "lifecycle_result": SimpleNamespace(safe_user_message="פעולה ממתינה"),
    #     "owner_notified": False,
    # }]
    # assert the returned reply is the Gateway text, never Agent-generated text.


def test_agent_output_cannot_override_gateway_lifecycle_state(monkeypatch):
    """Even if the Agent's own final_reply claims success/failure, a
    gateway-owned current-turn entry must win."""


def test_owner_notified_true_suppresses_duplicate_channel_reply():
    """owner_notified=True → the function returns "" (already delivered via
    bot.send_message to the owner), never a second copy of the text."""


def test_owner_notified_false_returns_one_legacy_safe_user_message():
    """owner_notified=False → exactly one message, sourced from
    lifecycle_result.safe_user_message (unchanged legacy text)."""


def test_final_response_count_remains_one():
    """final_response_count in out_meta stays 1 for a gateway-owned turn."""


# ── E. Shared derivation ───────────────────────────────────────────────

def test_enforcement_and_ownership_signal_agree_on_same_entry(monkeypatch):
    """_gateway_owned (enforcement) and the OwnershipSignal's reply_owner
    (observability) must derive from the SAME tool_results_log entry's
    action_lifecycle_result — never disagree, by construction."""


def test_sentinel_presence_alone_cannot_claim_gateway_ownership():
    """A tool_results_log entry with tool=="__approval_queued__" but NO
    action_lifecycle_result (or one with reply_owner != "gateway") must
    NOT be treated as gateway-owned by either enforcement or the
    observability signal — closing BUG-162 §2.4's duplicate-authority gap
    at its root (a sentinel-only predicate can no longer independently
    claim ownership anywhere)."""


# ── Branch B — ownership read failure, full control-flow proof ─────────
# Demonstrates the actual chain: ownership read failure -> correlated
# fail-closed branch -> early deterministic return -> zero subsequent
# Agent response -> zero synthetic ActionLifecycleResult. Not just "the
# producer dict looks right" (§1's own unit-level shape) -- this proves the
# TOOL LOOP actually reacts to it before another Agent round can run.

def test_ownership_verification_failed_entry_triggers_branch_b_early_return(monkeypatch):
    """A tool_results_log entry correlated to THIS turn, tagged
    terminal_outcome=="APPROVAL_OWNERSHIP_VERIFICATION_FAILED" (Branch B),
    must trigger the SAME early, structural stop as a Branch A
    gateway-owned entry -- before tool_calls_made increments and before
    any further Claude API call/messages.append() is reached."""
    # tool_results_log = [{
    #     "tool": "__approval_queued__",
    #     "terminal_outcome": "APPROVAL_OWNERSHIP_VERIFICATION_FAILED",
    #     "content": "<the same legacy safe_user_message §1a/§1b/§1c already computed>",
    #     "owner_notified": False,
    #     "contract_id": "c1",   # exact-contract correlation still explicit
    #     # deliberately no "action_lifecycle_result" / "reply_owner" keys
    # }]
    # assert the function returns entry["content"] and that no further
    # Claude API call happens (mock the Anthropic client call and assert
    # call_count == 0 after this tool_results_log entry).


def test_ownership_verification_failed_produces_no_synthetic_lifecycle_result(monkeypatch):
    """Across the whole call — producer (_queue_approval_detailed_impl via
    §1) through the tool loop (§2) — no ActionLifecycleResult object (real
    or synthetic) is ever constructed for this turn. Patch
    ActionLifecycleResult.__init__ (or spy on core.lifecycle_projection.
    build_action_lifecycle_result) and assert it is never called on this
    path, proving the failure truly produces nothing fabricated rather
    than a well-hidden one."""


def test_ownership_verification_failed_owner_notified_true_suppresses_duplicate(monkeypatch):
    """Branch B's success-path variant (§1c): if the owner was already
    notified (bot.send_message succeeded) before the ownership check ran,
    the Branch B return must still be "" -- never a duplicate second
    message -- exactly mirroring Branch A's owner_notified short-circuit."""


def test_ownership_verification_failed_final_response_count_remains_one():
    """final_response_count in out_meta stays 1 for a Branch B turn, same
    as Branch A -- this is a safety stop, not a differently-counted
    response."""


def test_ownership_verification_failed_does_not_depend_on_pa01_state(monkeypatch):
    """The Branch B early return must fire identically regardless of
    get_pa01_enforcement_state() -- set it to 'off', 'shadow', and
    'enforce' in turn and assert the same early-return behavior in all
    three, proving this invariant does not rely on PA-01's own, separate,
    later, text-pattern-based mechanism."""


# ── G. Scope guards ──────────────────────────────────────────────────

def test_no_evidence_finalizer_behavior_change():
    """execution_status()/EvidenceResult call sites and behavior are
    byte-identical before/after this patch (diff-based assertion, or a
    direct call comparison against a known fixture)."""


def test_no_new_durable_state_or_lock_introduced():
    """Structural: this patch introduces no new persistence, no new lock,
    no new turn-state table — grep-based or import-based assertion."""
```

Plus the pre-existing regression suites, unmodified, must stay green after
the patch: `test_bug162_gateway_reply_owner_on_generic_block.py` (57/57),
`test_pr1_single_speaker_approval_ux.py`, `test_single_speaker_fallback_and_duplication.py`,
`test_action_gateway.py`, the full root `test_*.py` sweep, `core/router/`
and `core/` pytest suites, `smoke_tests.py`, `python3 -m compileall -q .`.

---

## 6. Scope guards (explicit, matching TC6's own exclusions)

This patch does **not**: touch `EvidenceResult`/`execution_status()`
enforcement (TC7); add durable turn state, locks, or multi-instance
ownership (TC8); touch `core/message_contract.py` or
`core/agent_message_formatter.py` rendering (TC9); touch router/builders/
resolvers (WS1, complete); edit any feature flag; touch `event_bus.py` or
`tma_api.py` (no concrete blocker was found in either — see TC6 preflight §F).
