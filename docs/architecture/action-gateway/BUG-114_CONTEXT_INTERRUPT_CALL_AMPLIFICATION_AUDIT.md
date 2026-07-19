# BUG-114 — ActionContracts context-interrupt call amplification (audit only)

**Status:** 🔴 Audit complete, registered, **not fixed** — narrow fix proposed below, awaiting owner decision to implement.
**Scope of this document:** investigation only. No code was changed to produce this document. Explicitly out of scope: BUG-111, BUG-112, BUG-113, PR #393/#399/#400 — this is a separate, unrelated finding surfaced in the same production log excerpt.

## 1. Production evidence

Render log, 2026-07-19 11:36:20–11:36:23, a single inbound Telegram message (`list_tasks` intent) from a user (`boss_hq:eliyahu`) with 6 live pending `ActionContracts`:

```
GET ActionContracts?filterByFormula=AND({canonical_user_id}='boss_hq:eliyahu',{status}='pending')&maxRecords=100
GET ActionContracts?filterByFormula={contract_id}='78876ce1-...'&maxRecords=1
PATCH ActionContracts/rec1HMpA3BtxaKUAH                    [AUDIT:gateway] keys=['status','version','context_interrupted']
GET ActionContracts?filterByFormula={contract_id}='78876ce1-...'&maxRecords=1
GET ActionContracts?filterByFormula={contract_id}='598f3595-...'&maxRecords=1
PATCH ActionContracts/rec6hScIAe4G1iLyl                    [AUDIT:gateway] keys=['status','version','context_interrupted']
GET ActionContracts?filterByFormula={contract_id}='598f3595-...'&maxRecords=1
... (same GET/PATCH/GET triplet repeats for 4 more contract_ids)
```

`core.turn_envelope` in the same turn: `case_c_signal kind=C1 detail=live_contracts=6`, `multi_contract_conflict=true`.

Net cost of this **one** inbound message, before the agent even starts processing it: **1 + 6×3 = 19 Airtable HTTP round-trips**, purely for context-interrupt bookkeeping on contracts the message has nothing to do with.

## 2. Answers to the audit questions

### Q1 — Which function marks `context_interrupted` for all live contracts?

`core/action_gateway.py::ExecutionLedger.mark_context_interrupted()` (line 558), wrapped by `ActionGateway.mark_context_interrupted()` (line 2030), called from `app.py:3920` inside `_apply_ingress_context_gate()` (or equivalent ingress-gate helper) — **on every inbound `text`/`media` event that is not itself a resolution event** (`is_own_resolution_event()` returns False) **and is not an `approve:`/`reject:` callback press** (`app.py:3907–3920`). In practice: any unrelated message the user sends while they have live pending contracts triggers this call.

### Q2 — Does it re-patch contracts already `context_interrupted=True`?

**Yes.** The selection filter in `mark_context_interrupted()` is:

```python
for c in self._store.values()
if c.canonical_user_id == canonical_user_id and c.status == "pending"
```

— it does not check `c.context_interrupted` at all. Every pending contract for the user is included in `changes` and re-run through `update_status()` with `{"context_interrupted": True}`, **even when that field is already `True`**. `ExecutionLedger.update_status()` → `ActionContractRepository.transition()` does have an idempotent shortcut (`if current.status == new_status and not updates: return current`, `action_contract_repository.py:239`), but it only fires when the `updates` dict is **empty** — a `{"context_interrupted": True}` update is non-empty even when the value doesn't actually change, so the shortcut never applies here. A contract that is already `context_interrupted=True` and stays "pending" gets the full GET→PATCH→GET treatment on **every subsequent unrelated message**, for as long as it remains pending (which, per Q6, can be indefinite).

### Q3 — Can the initial pending query filter to `context_interrupted != true`?

The **first** GET in the log (`find_pending_by_canonical_user`, called from `ExecutionLedger.find_live_by_user()`, `action_gateway.py:428–443`) is a **cache-miss recovery hydration** — it only runs when there is no cached contract for this user yet in RAM (`has_cached_user_contract` check), and it needs to fetch full contract objects (including `context_interrupted`) to populate the cache correctly, so narrowing *that* query would be counter-productive. It is not itself the amplification source and was not the point of Q3 once traced.

The actually-useful equivalent of "filter early" applies to `mark_context_interrupted()`'s own **in-memory** selection (the list comprehension quoted under Q2) — `context_interrupted` is already a field on the cached `ActionContract` object (`action_gateway.py:184`), so this filter is a **zero-I/O, in-RAM check**, not a second Airtable query. Adding `and not c.context_interrupted` there is both correct and free.

### Q4 — Is the per-contract GET-before-PATCH necessary?

**Yes, for any contract that genuinely needs a transition** — and should not be removed for those. `ActionContractRepository.transition()`'s pre-PATCH `_get_for_transition()` (`action_contract_repository.py:222`) exists because Airtable has no compare-and-swap primitive; the read is how `transition()` rejects a stale `expected_status`/`expected_version` before writing, so a concurrent lifecycle change (e.g. the user approving the same contract from another device/tab in the same window) is never silently clobbered by an unconditional PATCH. This is deliberate, well-documented (see the file's own header comment and the "Codex re-audit" comments at `action_gateway.py:485–509`), and should not be weakened. It only becomes wasted work when it fires for a contract that didn't need any write at all — which is exactly the Q2/Q3 gap, not a flaw in the read-before-write pattern itself.

### Q5 — Is the per-contract GET-after-PATCH mandatory, or can it be reduced/batched safely?

Under the **current** interface, it is effectively necessary: `tools/airtable_gateway.py::airtable_patch()` (line 297) returns only a `bool` — it discards the PATCH response body (`r.json()` is never read; only `r.status_code == 200` is kept). Airtable's REST API's PATCH response already includes the record's post-write `fields` in the same round-trip, but nothing in this codebase captures it. `transition()`'s separate read-back GET (`action_contract_repository.py:275`) is the only way it currently has to verify `status`/`version` actually landed as expected.

A real reduction is possible without weakening validation — have `airtable_patch()` (or a new sibling) return the patched fields from the PATCH response itself, and have `transition()` verify against that instead of firing a second GET — but that changes a shared, low-level gateway function likely used by many other callers, so it is a broader change than "narrow." **Recommended as a separate, deferred efficiency item, not part of the BUG-114 narrow fix below.**

### Q6 — Why are 6 pending contracts live for the same user, and should older ones be expired/superseded?

There is **no TTL-based or scheduled expiry for pending `ActionContracts`** — grepped `scheduler.py` and `core/approval_queue_recovery.py`: no cleanup job exists. (This is a different mechanism from BUG-112's Telegram-button TTL, which lives entirely in `event_bus.py`'s `PendingActionsStore` and only governs the inline-button press path, not the `ActionGateway`/`ExecutionLedger` durable contract itself.)

The only thing that ever moves a pending contract out of limbo is the interrupt/reconfirm FSM: a first interruption sets `context_interrupted=True` (still "pending"); only a **second** interruption of a contract that has already gone through a reconfirmation display (`reconfirmation_required=True`, set at `action_gateway.py:1021`) supersedes it. If the user keeps sending unrelated messages without ever specifically confirming or cancelling a given proposal — and keeps asking the agent for new things that each queue their own new pending contract — nothing ever forces resolution. That is consistent with 6 simultaneous live contracts for one user: each represents a distinct earlier proposal nobody explicitly closed out.

**This is a real design gap, but a policy question, not a mechanical bug** — whether/how to cap concurrent live contracts per user or add a scheduled supersede sweep is an owner decision (analogous to what BUG-112 did for the Telegram button, but for the durable contract layer itself). **Recommended as a separate follow-up item, explicitly not bundled into the BUG-114 narrow fix.**

## 3. Root cause (one sentence)

`mark_context_interrupted()` re-applies a no-op write to every live pending contract on every unrelated inbound message, instead of skipping contracts that are already in the target state — turning what should be O(new interruptions) into O(all live contracts) per turn.

## 4. Proposed narrow fix (not yet implemented)

Add one filter condition to `ExecutionLedger.mark_context_interrupted()`'s existing list comprehension (`action_gateway.py:565–572`):

```python
with self._lock:
    changes = [
        (c.contract_id, "superseded", {})
        if c.reconfirmation_required
        else (c.contract_id, "pending", {"context_interrupted": True})
        for c in self._store.values()
        if c.canonical_user_id == canonical_user_id
        and c.status == "pending"
        and not c.context_interrupted          # <-- new: skip already-interrupted, no-op contracts
    ]
```

A contract with `reconfirmation_required=True` is **not** skipped by this change — it still needs the real "supersede" transition every time it's hit, since that's a genuine status change with a genuine reason to re-verify against a possible concurrent approval, not a no-op re-write of an unchanged field.

### Why this meets the stated acceptance criteria

- **No behavior change to approval semantics:** the FSM's decision table (pending → pending+interrupted → superseded) is untouched; this only skips contracts whose *outcome* would have been unchanged anyway (`context_interrupted` already `True`, still "pending").
- **No weakening of `ActionGateway` lifecycle validation:** `transition()`'s TOCTOU-safe read-before-write and read-back-verify (Q4/Q5) are completely untouched — they still run in full for every contract that actually needs a write.
- **Reduces Airtable calls for a no-op/already-interrupted pending contract:** from 3 calls (GET+PATCH+GET) to 0 for each such contract, on every subsequent unrelated message while it stays pending. In the observed 6-contract sample, once all 6 have been interrupted once, a later unrelated message would drop from 18 calls to 0 for this step (down from the 1+18=19 total in §1, though the initial `find_live_by_user` recovery GET is cache-miss-only and unaffected).
- **Keeps fail-closed behavior:** `not c.context_interrupted` is a pure in-memory read of already-cached, already-trusted state (the same `_store` the rest of this method already reads without a fresh Airtable round-trip) — it introduces no new trust boundary or new way to silently skip a contract that actually needs marking. A contract that is NOT yet interrupted, or whose cached state is stale/uncertain, is unaffected by this change and still goes through the full write+verify path.

### Suggested test coverage (not yet written)

A new `test_bug114_context_interrupt_amplification.py` (or extending an existing `ExecutionLedger`/`ActionGateway` suite) should cover:
1. Multiple pending contracts for one user, all `context_interrupted=False` → `mark_context_interrupted()` still marks all of them (existing behavior unchanged).
2. A mix — some `context_interrupted=True`, some `False` — → only the `False` ones get `update_status()` called (assert call count / mock the repository's `transition()` and assert it's invoked exactly `len(false_ones)` times, not `len(all_pending)`).
3. A contract with `reconfirmation_required=True` (already-interrupted-once) is still transitioned to `"superseded"` regardless of its `context_interrupted` value — the skip must not accidentally suppress a genuine second-interruption supersede.
4. Regression: a contract belonging to a *different* `canonical_user_id`, or with `status != "pending"`, is still excluded exactly as before (unchanged pre-existing filter behavior).
5. End-to-end (mocked Airtable): assert the total PATCH call count for a `mark_context_interrupted()` call over N contracts where M are already interrupted is exactly `N - M`, not `N`.

## 5. What this document does NOT do

- Does not modify `core/action_gateway.py`, `core/action_contract_repository.py`, `app.py`, or any other runtime file.
- Does not implement the Q5 (PATCH-response-reuse) or Q6 (contract expiry policy) recommendations — both are flagged as separate, deferred items requiring their own scoping/owner decision.
- Does not touch BUG-111, BUG-112, BUG-113, or PR #393/#399/#400.
