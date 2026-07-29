# PR Hotfix A — Cross-Layer Impact Matrix

Status: implementation evidence for `claude/pr2-staging-acceptance-audit-7n9f2p` (GitHub PR #494).
Base: `origin/main` at `fa5482c` (PR #493 merged).
Per `docs/architecture/CROSS_LAYER_AUTHORITY_CONTRACT_V1.md` — mandatory gate for any change
touching the Durable Atomic Approval layer.

## Scope of this PR

Three fixes, all rooted in one production staging incident (29/07/2026):

1. `core/action_gateway.py::_sheets_payload_to_airtable()` — accepts a 2-element positional
   `row_data` (title, due date) for the Tasks table, not just 1.
2. `app.py::_queue_approval_detailed()` — catches `CanonicalizationError` distinctly
   (`terminal_outcome=APPROVAL_QUEUE_NEVER_ATTEMPTED`, with the canonical `action_tool`
   recomputed the same way the generic exception handler already does), and the tool loop no
   longer counts this provably contract-less failure against BUG-122's one-mutation-per-turn
   budget.
3. `app.py::_resolve_pr2_deterministic_approval()` — a bare "כן"/"אשר"/"לא"/"דוחה"/"מבטל" with
   no live `ActionContract` never calls `find_recent_terminal_by_user()` at any recency window;
   it always returns the canonical no-pending response. `is_created_query` ("יצרת?") is
   unaffected — it keeps the 24h `_LIVE_CONTRACT_STALE_SECONDS` window.

## Layer 1 — Core Reasoning / BUG-104

touched: not touched.

input impact: none — no signal this PR changes is read by Layer 1.

output impact: none.

authority impact: none — Layer 1 remains read-only, no dispatcher/tool use; unaffected by this PR.

shared identifiers: none.

invariants: Core Reasoning remains read-only and has no dispatcher use — unchanged by this PR.

failure semantics: not applicable.

observability: none added.

cross-layer tests: no BUG-104 suite exercises this PR's diff.

## Layer 2 — TurnCoordinator

touched: indirectly.

input impact: none — `_resolve_pr2_deterministic_approval()` continues to run before Router/Agent
exactly as PR2 established; this PR only changes what happens *inside* that resolver once it has
already decided to intercept a turn (confirm/cancel-word replay logic, and the tool loop's
mutation accounting). No new signal reaches `core/turn_envelope.py`/the de-facto router/capture
owners (`core/router/router.py`, `core/lead_candidate_handler.py`).

output impact: none — no new route decision, `Handler`, or `reply_owner` signal. The
`__approval_queued__`/`__approval_blocked_pending__` sentinels in `tool_results_log` keep the same
shape and keys; only the *value* of `terminal_outcome` gains one new member
(`APPROVAL_QUEUE_NEVER_ATTEMPTED`) alongside the existing `APPROVAL_QUEUE_ERROR`/
`APPROVAL_QUEUE_ORPHANED`.

authority impact: none — TurnCoordinator's de-facto owners (Router/`lead_candidate_handler`) are
never reached differently because of this PR; business create/update/delete decisions are still
made only where they already were.

shared identifiers: none — no `core/turn_envelope.py` identifier (`turn_id`, `OwnershipSignal`
fields, etc.) is read, written, or redefined by this PR.

invariants: business create/update/delete decisions are never made by capture — unaffected;
this PR does not touch `core/lead_candidate_handler.py`.

failure semantics: non-matching/no-live-contract input is fail-safe fall-through to the canonical
no-pending response — never auto-approved, never silently retried. This is a strengthening of the
existing invariant (see §"Root cause" — the incident was exactly a fail-*unsafe* case: a stale,
unrelated contract's terminal state leaking into an unrelated reply), not a new one.

observability: no new `TurnCoordinator`-layer log line. `[Approval] _queue_approval_detailed
canonicalization failed` (new, same logger as the existing generic handler) is Layer 4, not Layer 2.

cross-layer tests: `test_bug141_pending_query_dispatch_order.py` (dispatch-order regression, PR2's
own cross-layer test) remains green — see full suite results below.

## Layer 3 — F52 / Phase 4C Action & Tool Contract

touched: not touched directly.

input impact: none.

output impact: none.

authority impact: no policy or tool mapping change — `tool_registry.py`'s `ToolMeta` entries
(`roles_allowed`/`requires_approval`/`high_risk`/etc.) are unmodified.

shared identifiers: none.

invariants: no dispatcher/tool-registry/schema import was added or changed.

failure semantics: not applicable.

observability: none.

cross-layer tests: no C53a suite is changed. `git diff origin/main...HEAD --name-only` (see
"Proof of non-impact" below) confirms `tool_registry.py`, `tools/dispatcher.py`, and
`tools/schemas.py` are absent from the diff.

## Layer 4 — Durable Atomic Approval

touched: directly.

input impact: `_sheets_payload_to_airtable()` now accepts one additional positional-payload shape
(2-element `row_data` for the Tasks table) that previously raised unconditionally. This is a
widening of accepted input, not a narrowing — every payload shape previously accepted is still
accepted identically (see regression tests). `_queue_approval_detailed()` no longer treats every
non-`CanonicalizationError` exception the same way it treats a `CanonicalizationError` — the two
were previously indistinguishable at the wrapper's `except Exception` boundary.

output impact: one new `terminal_outcome` literal, `APPROVAL_QUEUE_NEVER_ATTEMPTED`, alongside the
existing `APPROVAL_QUEUE_ERROR`/`APPROVAL_QUEUE_ORPHANED`. Consumed by exactly one new call site
(app.py's tool loop, the `_mutating_approvals_this_turn` increment guard) and read nowhere else in
the diff. `_resolve_pr2_deterministic_approval()`'s reply for a bare confirm/cancel word with no
live contract is now always the canonical `build_approval_lifecycle_result(canonical_state=
"no_contract")`/no-pending-cancellation text, never a replayed terminal contract's own wording —
existing consumers of `ApprovalLifecycleResult` (Telegram/WhatsApp adapters) are unaffected since
the shape is unchanged, only which `canonical_state` gets selected.

authority impact: unchanged — `ActionContracts` remains the sole lifecycle authority; the new
`terminal_outcome` value is a request-local classification of *this call's own outcome*, never a
new source of truth about contract status, and is not persisted to any `ActionContract` field.

shared identifiers: new `terminal_outcome` literal `APPROVAL_QUEUE_NEVER_ATTEMPTED` (string, not a
new class/schema field) — verified via grep (below) that no other module pattern-matches on the
closed set of `terminal_outcome` values in a way that would silently misclassify the new one as
something else. No `ActionContract` status literal is added (`draft|pending|approved|rejected|
completed|failed|outcome_unknown` is unchanged).

invariants: no Session bookmark is read on the confirm/cancel replay-guard path (unchanged from
PR2's own invariant — this PR removes a replay path, it does not add a Session read to replace
it). "ActionContracts is the sole lifecycle source of truth" holds — the fix removes an *incorrect
inference* from stale ActionContracts state, it does not introduce a second source.

failure semantics: a `CanonicalizationError` is fail-closed exactly as before (no contract is ever
created), but is now reported to the caller as a *provably clean* failure
(`APPROVAL_QUEUE_NEVER_ATTEMPTED`) rather than the merely *unverified* `APPROVAL_QUEUE_ORPHANED` —
this is a narrowing of uncertainty (fewer failures reported as "unknown"), not a new failure mode.

observability: new log line `[Approval] _queue_approval_detailed canonicalization failed:
tool=%s reason=%s` (distinct from the existing generic `[Approval] _queue_approval_detailed
unexpected error`), content-free of payload/message text.

cross-layer tests: `test_bug_canonical_tool_wiring.py` (positional canonicalization + mutation-
accounting outcome shape), `test_pr2_deterministic_approval_cost_cuts.py` (confirm/cancel replay
guard, full incident reproduction, `יצרת?` unaffected), `test_pa01_phantom_approval_enforcement.py`
(P1-2/P2-4 — action_tool canonical name and terminal_outcome precision on this exact exception
path) — all green after the action_tool recompute fix (see "CI correction" below).

## Proof of non-impact (Layers 1 and 3)

`git diff origin/main...HEAD --name-only` produces exactly:
```
app.py
core/action_gateway.py
test_bug_canonical_tool_wiring.py
test_pa01_phantom_approval_enforcement.py
test_pr2_deterministic_approval_cost_cuts.py
```
No entries for `core/leads_reasoning_projection.py`, `core/adapters/leads_adapter.py`,
`core/router/router.py`, `core/lead_candidate_handler.py`, `tool_registry.py`,
`tools/dispatcher.py`, or `tools/schemas.py` — grep for new imports of any of those modules inside
the two changed source files (`app.py`, `core/action_gateway.py`) also returns nothing beyond
pre-existing, unrelated imports. No-new-coupling: the only new intra-repo import added is
`from core.action_gateway import resolve_canonical_tool as _resolve_for_canon_error` inside
`app.py`'s new `except CanonicalizationError` branch — the same function the pre-existing generic
handler already imports for the identical purpose two branches below it, not a new dependency
direction.

## Cross-Cutting Guard — RP5 Evidence Finalization

applies: yes. This PR changes `terminal_outcome` values returned by `_queue_approval_detailed()`,
which feed `core/turn_evidence.py`'s shadow classification at the tool-loop call site (app.py
`~3921-3923`):

```python
if _approval_outcome["created_this_turn"]:
    turn_evidence.record_approval_pending()
elif _approval_outcome["terminal_outcome"] == "APPROVAL_QUEUE_ORPHANED":
    turn_evidence.record_unverified_effect()
else:
    turn_evidence.record_verification("failed", read_only=meta.read_only)
```

Concrete effect: a `CanonicalizationError` failure, previously classified `APPROVAL_QUEUE_ORPHANED`
→ `record_unverified_effect()` ("we don't know if this happened"), is now classified
`APPROVAL_QUEUE_NEVER_ATTEMPTED` → falls to the `else` branch → `record_verification("failed",
...)` ("this is a verified failure"). This is **more accurate**, not a behavior regression: a
`CanonicalizationError` is raised before any persistence attempt, so "verified failed" is the
correct classification, not "unverified." Verified directly: `grep -n "terminal_outcome"
core/turn_evidence.py` returns zero matches — `core/turn_evidence.py` does not itself
pattern-match on `terminal_outcome` string values, so this PR does not require any change there;
the classification shift happens entirely at the existing app.py call site shown above, not inside
RP4/RP5's own module. This PR does not introduce a grounding/evidence mechanism, does not call
`core/turn_evidence.py` directly, and does not bypass `core/anti_hallucination.py` — the existing
Single-Speaker suppression and `verify_execution()` paths are untouched.

## CI correction (documented for the record, not a separate PR)

The first push of this hotfix (commit `f87ad4f`) failed `backend-ci` —
`test_pa01_phantom_approval_enforcement.py`: 106/108 passed. Root cause: the new
`except CanonicalizationError` branch returned `"action_tool": tool_name` (the wrapper's raw,
pre-canonicalization parameter) instead of recomputing the canonical name the way the pre-existing
generic `except Exception` handler already does — losing that handler's own established fix for
"the canonicalized local variable is lost when the frame unwinds on exception." Confirmed as a
genuine regression (not a pre-existing failure) by running the identical test file against
`origin/main` in an isolated worktree: 108/108 passed there. Fixed by recomputing
`resolve_canonical_tool(tool_name, tool_inputs, user_text)` in the new branch, mirroring the
existing pattern exactly. One test assertion (P1-2, tied to P2-4's scenario) was updated to expect
the new, more precise `APPROVAL_QUEUE_NEVER_ATTEMPTED` value instead of the old
`APPROVAL_QUEUE_ORPHANED` for this specific `CanonicalizationError`-driven scenario — the test's
own inline comment now documents why. No other test in the file was touched; the remaining 106
were unaffected by the regression and remain unchanged.
