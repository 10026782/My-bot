# BUG-115 — "כן" confirmation hijacked by unrelated stale ActionContracts

**Status:** ✅ Fix implemented, tests green (22 new + full regression sweep clean), **not yet production-verified**.
**Scope of this document:** §1–§5 below are the original audit, unchanged as written; the narrow fix from §5 has since been implemented — see §7. Explicitly out of scope: BUG-114 (call amplification, ✅ verified in prod, PR #402) — different symptom, different fix target, though both are consequences of the same underlying "pending ActionContracts never expire" gap (BUG-114 §2 Q6). Not conflated: BUG-114's fix (a filter condition in `mark_context_interrupted()`) is unrelated code and was not touched by this fix.

## 1. Production evidence

```
Eli: צור ליד חדש לענף גיוס 0548442163 ללא שם כרגע

BOSS: 📋 זיהיתי ליד: *לענף גיוס* (0548442163)
      לשמור? ענה *כן* לאישור או *לא* לביטול.

Eli: כן

BOSS: יש כמה פעולות הממתינות לאישור — איזו?
      • 1. airtable_add (id: 78876ce1)
      • 2. airtable_add (id: 598f3595)
      • 3. airtable_update (id: d55acb52)
      • 4. airtable_add (id: 8c9a0adb)
      • 5. airtable_update (id: 1da79b0b)
      • 6. airtable_update (id: 50b61a45)
      • 7. airtable_add (id: 181cf6f6)
      • 8. airtable_add (id: f3834e7c)
      שלח את המספר (1, 2, ...) כדי לאשר פעולה ספציפית.
```

**Expected:** the "כן" confirms the lead preview just shown.
**Actual:** it fell into ActionGateway's generic multi-contract disambiguation, listing 8 unrelated pending contracts by raw tool name and internal id — none of which the user was actually responding to.

Cross-reference: 6 of these 8 contract ids (`78876ce1`, `598f3595`, `d55acb52`, `8c9a0adb`, `50b61a45`, `181cf6f6`) are the exact same ids from the BUG-114 production sample (`live_contracts=6`); `1da79b0b` is the contract from an unrelated earlier session exchange (the PR #393 verification sample, a task-status-check-then-update turn) that was also never explicitly resolved. **These are stale, long-since-abandoned contracts accumulating with no expiry — BUG-114 §2 Q6 already documented that no TTL/cleanup exists for pending `ActionContracts`.** `f3834e7c` — the 8th, newest entry, matching insertion order — is almost certainly the contract this exact lead preview itself created (see §2).

## 2. How the lead preview creates a real ActionContract (by design, not a bug)

`core/lead_candidate_handler.py:1191-1221` (`handle_lead_candidate()`'s Tier-1 single-lead branch): when a lead can't auto-write (no `FEATURE_AUTO_CAPTURE`, or an existing lead needing `airtable_update`), it calls `_propose_lead_write()` (`core/lead_candidate_handler.py:583`), which proposes a **real** `ActionContract` via `ActionGateway.propose_action()` and returns the exact "📋 זיהיתי ליד..." / "לשמור? ענה כן..." preview text seen in the log. The comment at `lead_candidate_handler.py:1192-1195` is explicit and deliberate (from BUG-056): *"preview mode now proposes a REAL pending ActionContract (instead of the dead-end session['pending_lead_preview']) so 'כן' can actually resolve it — see app.py's confirm-word handling (checks ActionGateway live contracts first)."*

So this is not a Tier-1-vs-Tier-2 mixup (the earlier hypothesis in the investigation request) — **the lead preview genuinely is a Tier-1 ActionGateway contract**, exactly as BUG-056 intended. The routing precedence check in `app.py` (`_gw_cw.find_live_contracts(identity.memory_key)`, `app.py:2636`) correctly finds a live contract and correctly routes to `ActionGateway.route_confirmation_word()`. **The bug is entirely inside `route_confirmation_word()` itself** (`core/action_gateway.py:1010`): BUG-056's design implicitly assumed "usually there's exactly one live contract — the one just proposed," so `len(live)==1` auto-approves directly. It never accounted for old, abandoned contracts still being "live" by the time a new one is proposed, so `len(live)==8`, and the generic multi-item disambiguation branch (`action_gateway.py:1054-1061`) fires instead — a branch that has **no concept of "which contract was just shown to the user"** at all, only a raw count.

## 3. Answers to the investigation questions

### Q1 — How is "כן" routed when both a lead preview confirmation and ActionGateway approval_pending exist?

There is no separate "lead preview confirmation" routing path competing with ActionGateway here — per §2, the lead preview **is** an ActionGateway contract. The only routing question that matters is inside `route_confirmation_word()`: `len(live)==1` → auto-approve; `len(live)>1` → generic disambiguation, unconditionally, regardless of recency or relevance (`action_gateway.py:1018-1061`).

### Q2 — Should the last visible prompt / `message_kind` take priority over the generic approval queue?

In principle yes, and that's exactly the shape of the proposed fix in §4 — but `TurnEnvelope.message_kind` (the field named in the investigation request) is **not a real mechanism today**: `core/turn_envelope.py:200` documents it as "always None in Phase 0 — not computed until Phase 4." There is no live "last visible prompt" tracker anywhere in the current codebase to prioritize with. One needs to be added (§4 proposes reusing an existing, proven pattern rather than building Phase 4 wholesale).

### Q3 — Does `TurnEnvelope.active_queue_id` incorrectly prefer `action_gateway` over `lead_capture`?

**Partially confirmed, but not the actual cause of the production bug.** `app.py:1404` and `app.py:1443` assign `action_gateway_queue.priority=3` and `lead_capture_queue.priority=5`; `build_turn_envelope()`'s `active_queue_id = sorted(queues, key=lambda q: q.priority)[0].queue_id` (`turn_envelope.py:272-273`) — lower number sorts first, so **`action_gateway` (3) is indeed picked over `lead_capture` (5)** whenever both are present. However: `TurnEnvelope` is explicitly Phase-0 **observation-only** (see the module's own header docstring, `turn_envelope.py:1-27`: "no I/O... never injects into the agent's prompt/context"). It is built at a separate call site (`app.py`'s "1.7" section, ~line 1380-1465) purely for logging, and the actual "כן" routing decision at `app.py`'s "2.55" section (~line 2542+) never reads `active_queue_id` at all — it makes its own, independent decision via `_gw_cw.find_live_contracts()`. **The two mechanisms happen to agree (both currently favor ActionGateway over lead-capture-shaped state) but are not the same code path** — fixing `active_queue_id`'s priority ordering would change nothing about the reported bug, since nothing reads it for routing today. Worth noting as consistent design intent, not worth "fixing" on its own.

### Q4 — Is the `lead_candidate_handler`/`resolve_pending_lead_preview` confirm path bypassed when `multi_contract_conflict=true`?

**No — because that Tier-2 path was never in play for this scenario at all** (§2). `resolve_pending_lead_preview()` (`app.py:2652`, only reached when `find_live_contracts()` returns empty) is unrelated to what happened here; it exists for a *different* legacy preview mechanism (`session["pending_lead_preview"]`, batch clarification flows) that this specific single-lead Tier-1 flow does not use. The investigation's framing of "is Tier-2 bypassed" was a reasonable hypothesis but turned out not to match the actual code path — worth recording so a future investigation doesn't re-tread this exact question.

### Q5 — Should user-facing ActionGateway disambiguation expose tool names / raw ids?

No — confirmed as a real, independent finding regardless of the routing question. `action_gateway.py:1059`: `f"• {i}. {c.tool_name} (id: {c.contract_id[:8]})"` — literally `airtable_add`/`airtable_update` and an 8-char slice of the internal contract UUID, shown verbatim to the end user. This file already has exactly the right tool for this: `_describe_contract_for_reconfirmation()` (`action_gateway.py:604-621`) produces a human business-readable description (e.g. `"יצירת ליד: יוסי כהן, 0501234567, גיוס"`) and is already used one branch above, at `action_gateway.py:1047`, for the single-contract reconfirmation case. It is simply never reused for the multi-contract list.

## 4. Root cause (one sentence)

`route_confirmation_word()`'s multi-contract branch has no way to recognize "the contract this specific 'כן' is actually replying to" — it only counts, and once old abandoned contracts accumulate (BUG-114 §2 Q6), a routine "כן" after a fresh single-item preview degrades into a generic, privacy-leaking disambiguation menu instead of confirming what was just shown.

## 5. Proposed narrow fix (not yet implemented)

Two independent, additive pieces — neither touches `ActionContractRepository.transition()`, BUG-114's filter, F52, or `EvidenceFinalizer`:

### 5a. "Last prompted contract" bookmark (fixes the misrouting)

Reuse the exact pattern `session_store.py` already has for `pending_lead_preview` (`set_pending_lead_preview`/`get_pending_lead_preview`/`clear_pending_lead_preview`, `session_store.py:349-386`) — a short-TTL, per-chat bookmark, not a new storage mechanism:

- When `_propose_lead_write()` (or any other Tier-1 preview call site) successfully proposes a contract and is about to return its "לשמור? ענה כן" preview text, record `contract_id` in a new, similarly-shaped bookmark (e.g. `set_last_prompted_contract(chat_id, contract_id, ttl=...)`), matching the ~10-minute advertised window the approval prompt itself already implies elsewhere in this codebase (BUG-112's `_PENDING_APPROVAL_TTL`).
- In `app.py`'s confirm-word branch (`app.py:2619`, before the existing `find_live_contracts()` check at `app.py:2636`), check this bookmark first: if it names a `contract_id` that is *still* live (`status=="pending"`), resolve the "כן" against exactly that one contract (call the equivalent of `approve(contract_id=...)` / a new single-contract variant of `route_confirmation_word()`), bypassing the "how many total live contracts exist" question entirely.
- Only fall through to the existing `find_live_contracts()`/count-based logic when there is no live bookmark (e.g. the user typed "כן" out of the blue with nothing just shown, or the bookmark expired) — this preserves every existing behavior for that case, including the genuine multi-contract disambiguation UI when it's truly warranted.

This directly satisfies acceptance criteria 1–3: the visible prompt wins when it's what's live; old unrelated contracts can't hijack it; disambiguation is reserved for when the user isn't responding to a specific just-shown prompt.

### 5b. Human-readable disambiguation labels (fixes the leak, independent of 5a)

In `route_confirmation_word()`'s multi-contract branch (`action_gateway.py:1058-1059`), replace:
```python
lines.append(f"• {i}. {c.tool_name} (id: {c.contract_id[:8]})")
```
with a call to the existing `_describe_contract_for_reconfirmation(c)` helper, already proven correct one branch above for the same purpose. Worth doing even if 5a is deferred — it's a strict improvement on its own and satisfies acceptance criterion 4 independently.

### Why this is safe

- Does not change `ActionGateway` approval/execution semantics — `approve()` itself, dispatch, and lifecycle transitions are untouched; only which contract a bare "כן" resolves against, and how a list is displayed to the user.
- Does not touch BUG-114's fix (`mark_context_interrupted()`'s filter) — this bug is entirely in `route_confirmation_word()` and the preview call sites, a disjoint code path.
- Fail-closed preserved: the bookmark is advisory only — if it's stale/missing/expired, behavior falls back to exactly today's logic (count-based auto-approve or disambiguation), never silently approving something the bookmark merely *claims* without the underlying contract still genuinely being live and pending.
- 5b alone is a pure display-layer change with an existing, already-tested formatting helper — near-zero risk.

### Suggested test coverage (not yet written)

1. Single fresh lead-preview contract, no other live contracts → "כן" auto-approves it (existing `len(live)==1` behavior, regression guard).
2. Fresh lead-preview contract + N unrelated old live contracts, all with a *stale* (not-yet-abandoned-by-the-user) bookmark pointing at the fresh one → "כן" resolves the fresh one directly, not the disambiguation list.
3. No bookmark (or an expired one) + multiple live contracts → existing disambiguation behavior preserved exactly (regression guard for the genuinely-ambiguous case).
4. Bookmark points at a contract_id that is no longer "pending" (already approved/rejected/superseded by the time "כן" arrives) → falls through to existing count-based logic, does not error.
5. Disambiguation list (5b) renders `_describe_contract_for_reconfirmation()`-shaped text for each item, never `tool_name`/raw contract_id substrings.

## 6. What this document did NOT do, as originally written (superseded by §7)

At audit time: no code was modified, 5a/5b were not implemented, nothing outside this document itself was touched. **§7 below is the implementation follow-up** — read it for what's actually true now.

- Did not address BUG-114 §2 Q6 (no TTL/expiry for stale pending contracts) directly — that remains its own separate, deferred, owner-level policy decision; implementing it would also reduce how often this bug's disambiguation branch is even reached, but was not required for the fix in §7 to work correctly, and was not implemented here.

## 7. Implementation (follow-up to §5, same day)

Both parts from §5 were implemented as designed, with one placement change and one scope extension found necessary while writing tests — neither changes the safety argument in §5, both are documented here for an honest record.

**5a — bookmark, implemented as designed, with the check placed inside `route_confirmation_word()` itself** (the fix request explicitly asked for this placement; §5's own sketch had suggested `app.py`'s confirm-word branch as an alternative location — both are safe, `route_confirmation_word()` was chosen since it's the single call site both the "one live contract" and "bookmark hit" cases now share):

- `session_store.py`: three new methods on `PersistentSessionStore` — `set_last_prompted_contract()`/`get_last_prompted_contract()`/`clear_last_prompted_contract()` — same shape as the existing `pending_lead_preview` trio, including round-trip persistence through `_sync_to_db()`/`_load_from_db()` (the existing trio's exact fields list, extended). TTL is 600s (not the 1800s other bookmarks in this file use) — matches `_PENDING_APPROVAL_TTL`'s own advertised "פג תוקף בעוד 10 דקות" window, not a new number invented for this fix.
- `core/lead_candidate_handler.py`: the lead-preview call site (`_handle_single_candidate()`, right after `_propose_lead_write()` succeeds, covering both the new-lead and existing-lead-update preview variants) sets the bookmark.
- `app.py`: `_queue_approval_detailed_impl()`'s owner-notification block sets the bookmark right after `_owner_notified = True` — i.e. only once the prompt is *proven* sent, not merely attempted, mirroring the existing `owner_notified` proof pattern from F52 PR6.
- `core/action_gateway.py`: `route_confirmation_word()` checks the bookmark first. A new `_resolve_single_contract()` helper factors out the existing reconfirmation/context-poisoning safety logic (BUG-PENDING-APPROVAL-B) so it is shared, byte-identical, between the "exactly one live contract" path and the "bookmark hit" path — a bookmark can never bypass that safety check. It returns `(message, terminal)`; the bookmark is cleared only when `terminal=True` (an actual approve, or a durable-write failure) — **not** when the outcome is "please reconfirm" (context was interrupted since the prompt was shown), since the bookmark must survive to let the *next* confirm word still resolve the same contract directly. This distinction was not spelled out as precisely in §5's original sketch and was worked out while writing Test 6 (the interrupted-bookmark scenario) below.
- Explicit proactive bookmark-clearing was scoped to the two outcomes reachable from inside `route_confirmation_word()` itself (approve, durable-failure) plus the "bookmark stale/not-live/wrong-user" fallback path. Deliberately **not** added to `reject()`, `route_cancellation_word()`, `mark_context_interrupted()`'s supersede branch, or the Telegram button-reject handler — touching those would be real scope creep for a narrow fix. This is safe, not just convenient: `get_last_prompted_contract()`'s consumer always re-validates `status == "pending"` before trusting the bookmark, so an un-cleared bookmark pointing at an already-terminal contract (rejected via any of those other paths) is already fully inert — it simply won't match, and gets lazily cleared on the next read attempt (Test 4 covers this directly). The only cost of not clearing eagerly everywhere is the bookmark lingering in session state a little longer than strictly necessary, never a correctness or safety risk.

**5b — human-readable disambiguation labels, via a new dedicated helper, not a generalization of the shared one.** §5's literal proposal — reuse `_describe_contract_for_reconfirmation()` as-is — turned out to be insufficient on its own: its existing fallback for anything other than the Leads table is `f"{contract.tool_name} / {table}"`, which still leaks the raw tool name, and every contract in the actual production disambiguation sample (`airtable_add`/`airtable_update` against `Tasks`) hits exactly that fallback, not the Leads-specific branch.

First attempt: generalized that fallback directly inside `_describe_contract_for_reconfirmation()`. **This broke an existing, unrelated, already-passing test** — `test_stage_b_full_suite.py`'s DoD20 asserts that `compose_status_reply()`'s "✅ בוצע: {label}" executed-completion text (built via `_compose_status_reply_legacy()`, which also calls this same shared helper for a completely different purpose — describing what was actually written after a real execution) contains the raw tool name. That call site was never part of BUG-115's scope; generalizing the shared function changed its behavior there too, invisibly, until the full regression sweep caught it.

Corrected: `_describe_contract_for_reconfirmation()` is left **completely unchanged** from before this fix. A new, separate `_describe_contract_for_disambiguation()` was added instead — reuses the same Leads-specific branch verbatim (delegates to the original function for that case, identical output), but has its *own* generalized fallback for `airtable_add`/`airtable_update` against any table — `"הוספה ב-{table}"` / `"עדכון ב-{table}"`, optionally followed by a short preview of the first non-empty, non-record-id-shaped field value (`_first_field_preview()`, capped at 40 chars, skips anything matching Airtable's own record-id shape). Only the disambiguation-list loop calls this new function; every other existing call site of the original helper is untouched, byte-for-byte. Other tool types (`gmail_send_draft`, `calendar_create_event`, etc.) fall back to the original helper's own unchanged behavior — production reports never exercise them here, and `app.py`'s `_describe_tool_call()` already owns richer per-tool copy for the initial approval prompt itself.

**Tests:** new `test_bug115_confirmation_routing_bookmark.py`, 22 checks — covers the core production scenario (old unrelated contracts + a fresh bookmarked one), the no-bookmark regression (existing disambiguation behavior + human-readable labels), an expired bookmark, a bookmark pointing at an already-resolved contract, a bookmark under a different user, the interrupted-bookmark reconfirmation-required case (bookmark kept, not cleared, until the second confirm), bookmark clearing after a terminal approve, and an integration check that the real lead-preview call site actually sets the bookmark. Full existing regression suite touching these functions (30 files spanning `route_confirmation_word`/`route_disambiguation`/lead preview/reconfirmation FSM/BUG-070/BUG-074/BUG-076/BUG-111/Stage B/PR-0/F52 PR5/etc.) re-run and confirmed unaffected. `test_bug114_context_interrupt_amplification.py` (12 checks) and `test_bug_reconfirmation_oneshot_fsm.py` (27 checks) re-run green as explicit proof neither BUG-114's fix nor the underlying reconfirmation FSM regressed. Full `test_*.py` sweep, `smoke_tests.py`, `compileall`, `git diff --check` all clean.

**Scope, confirmed unchanged from §5's design:** `ActionGateway.approve()`/dispatch/lifecycle-transition semantics untouched. `route_disambiguation()` (the numbered "1"/"2"/... follow-up) untouched — it already delegates to `approve()` for its own reply text, no raw-label leak there. `TurnEnvelope.active_queue_id`, `message_kind`, and BUG-114's `mark_context_interrupted()` filter — all untouched, as required.

**Not yet done:** production verification. This fix has not yet been observed correctly resolving a real "כן"/"מאשר" against a fresh prompt while older unrelated contracts are live in production traffic.
