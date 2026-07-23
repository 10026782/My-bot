# Staging session findings (23/07/2026) — TTL enforcement, sibling auto-reject, pending-approval query routing

**Status:** 3 of the original 6 findings fixed + tested (below), and further confirmed against a real `ActionContracts` table export the owner supplied mid-review (§1.1). 2 findings (plus a 3rd, Finding #7, discovered mid-review from the executed record's own data) documented as requiring an owner/architecture decision — explicitly deferred to the TurnCoordinator contract's own approval, not implemented ad hoc. 1 finding is a manual data-review item, not a code fix.

**Prioritization rule applied (owner direction, mid-review):** everything here surfaced while probing the frozen TurnCoordinator plan. Only fix now what would otherwise corrupt reliable sample-gathering during that probing (stale/misleading pending-contract state, silent mass-rejection, wrong-table query answers — Findings #1/#3/#4). Anything that doesn't block reliable samples — even a confirmed, real bug — waits for the next stage (TurnCoordinator's own approval) rather than being patched ad hoc and risking a parallel mechanism (Findings #2, #6's destructive-intent flow, #7).

### 1.1 Real evidence used (owner-supplied `ActionContracts` export)

The owner exported the live records for the 7-contract batch referenced in the original findings report. This turned three "most likely explanation" hypotheses below into confirmed facts — see Findings #1/#5/#6:

| contract_id | content | created_at (Israel time) | age at 2026-07-23 13:16:03* | final status |
|---|---|---|---|---|
| `ac30218d` | "זיהיתי", 0501112222 | 2026-07-21 23:24:42 | **37.9h** | rejected |
| `f7b451f4` | ביבי נתניהו (phone update) | 2026-07-22 02:28:15 | 34.8h | rejected |
| `02ad21bc` | "תמחק איש קשר", 0536272637 | 2026-07-22 09:51:36 | **27.4h** | rejected |
| `7fed5be6` | איש קשר דני לוי, 0501234567 | 2026-07-22 22:37:02 | 14.65h | **approved → executed** |
| `f39d932b` | תמחק ליד ביבי נתניהו | 2026-07-22 23:24:16 | 13.9h | rejected |
| `ffc9c672` | airtable_update (בדיקה) | 2026-07-22 23:32:24 | 13.7h | rejected |

\* derived from `7fed5be6`'s own `approved_at=1784801763.111`, which falls inside the original report's stated 13:15:35–13:16:58 window — used as the disambiguation moment for all six age calculations.

Cross-referenced against fix commit `9285106` (BUG-129/BUG-135, `_NAME_STOP` additions), which landed 2026-07-22 07:09:28 UTC = 10:09:28 Israel time: both fake-name contracts (`ac30218d`, `02ad21bc`) were created *before* that commit existed (10.75h and 0.30h before, respectively) — see Findings #5/#6.

**Mandatory gate:** per `docs/architecture/CROSS_LAYER_AUTHORITY_CONTRACT_V1.md`, this document touches the Durable Atomic Approval layer (`ActionContract`/`ExecutionLedger`/`ActionGateway`) directly. §2 below is the full Cross-Layer Impact Matrix required before any of the runtime changes in this doc were made.

**Source:** `FINDINGS SUMMARY — TurnCoordinator Staging Session, 2026-07-23`, manual tests on `my-bot-approval-staging`, channel Telegram, user `boss_hq:eliyahu@owner`, 13:15:35–13:16:58. All 6 findings occurred under `policy_snapshot_version: phase0-static-v1` — i.e. entirely on the existing `route_disambiguation()`/`route_confirmation_word()` code path, independent of any TurnCoordinator decision (TurnCoordinator has zero runtime implementation — `grep -rl "class TurnCoordinator"` returns nothing).

---

## 1. Findings, verified against actual code (not the report alone)

### Finding #1 (P0) — TTL not enforced in practice on pending ActionContracts — ✅ fixed

**Report claim:** an item from >12h earlier was still shown as a live candidate and got executed on selection.

**Verified root cause (narrower and more specific than the report's framing):** `CONTRACT_PENDING_TTL_SECONDS = 24 * 3600` (`core/action_contract_repository.py:84`) is an already-decided policy — not an open "30min or 1h?" question as the report suggested. It **is** enforced by `ActionContractRepository.get()` and `find_pending_by_canonical_user()` (both call `_is_expired()`). The actual bug: `ExecutionLedger.find_live_by_user()` (`core/action_gateway.py`, the method every free-text approval route calls through `find_live_contracts()`) only consults the repository — and therefore only ever applies `_is_expired()` — on a **cold cache** (`has_cached_user_contract == False`). Once any contract for that user is cached in RAM, the method returned straight from `self._store` with no expiry check at all, for the lifetime of the process. A contract that ages past 24h without anyone re-visiting it (nothing proactively revisits "pending" contracts) stayed "live" forever on a warm cache.

Note: the specific 12h-old item in the report was **still inside** the 24h TTL, so this particular fix (making both code paths agree) would not by itself have hidden that exact item — see the interim mitigation below for the practical harm reduction.

**Fix:** `find_live_by_user()` now applies `_is_expired()` uniformly on both the cold-cache and warm-cache path (`core/action_gateway.py`, imports `CONTRACT_PENDING_TTL_SECONDS`/`_is_expired` from `core.action_contract_repository`).

**Interim mitigation (also implemented, addresses the report's own §2 immediate recommendation):** every multi-contract listing (`route_confirmation_word()`'s disambiguation branch, and the new `describe_pending_queue()` — Finding #4) now appends an inline age warning (`⚠️ (ממתין מ-N שעות/דקות)`) to any item older than 1 hour, independent of the 24h TTL. This is a display-only change — it does not affect what `approve()`/`reject()` will act on.

### Finding #2 (P0) — sibling auto-reject on unrelated batch — **documented, not implemented**

**Verified:** real, current behavior. `route_disambiguation()`/`route_combined_word()`'s confirm branch (`core/action_gateway.py`, marked "§21, commit 6752ec0") unconditionally rejects every other pending contract for the identity when one is picked by ordinal. Confirmed this is a **deliberate, documented design** — `event_bus.py:192`, `test_bug_batch_approval_preserved.py`'s docstring, `CHANGELOG.md`'s BUG-BATCH-DISCARD entry (PR #345) all describe it as built for disambiguating **alternative interpretations of one request** (e.g. the same lead captured twice), not for a numbered list of independent, unrelated actions.

**Why this session's scenario differs from the already-fixed BUG-BATCH-DISCARD case:** PR #345 already solved this for the single-turn "create 5 tasks in one message" case — only one contract is ever made live at a time via `event_bus.BatchQueueStore`/`app._promote_next_batch_item()`, so §21's sibling-reject never fires for a real same-turn batch. The staging report's 7 live contracts are a **different** shape: independent contracts accumulated across *separate* turns/messages over hours (Finding #1's TTL gap is exactly why they were all still "live" at once) — never funneled through the batch queue, so §21 fires on picking any one of them.

**Why not fixed here:** distinguishing "these N pending items are genuinely competing interpretations of the same request" from "these N pending items are coincidentally both still pending" requires a real classification signal that does not exist today (e.g. a `conflict_group_id`/shared-resource comparison on `ActionContract`) — the report's own recommended fix ("`single_choice` only when items provably compete for the same resource/entity") requires designing that signal. This is a genuine ActionContract lifecycle/semantics change (Durable Atomic Approval layer, §1 layer 4) with no narrow, low-risk fix available (unlike Findings #1/#3/#4) — same category CLAUDE.md's iron rule and `CROSS_LAYER_AUTHORITY_CONTRACT_V1.md` require an explicit decision for, not a unilateral implementation. **Recommendation:** owner decision needed on the classification approach before any implementation; candidate next step is a Planning Gate doc under `docs/architecture/action-gateway/` scoped exactly to this, referencing this audit.

### Finding #3 (P1) — no disclosure on mass sibling-rejection — ✅ fixed

**Verified:** confirmed — `route_disambiguation()`/`route_combined_word()`'s confirm branch returned only `approve()`'s own reply, with no mention that other contracts were closed.

**Fix:** both methods now count successfully-rejected siblings and append `"\n\nℹ️ שים לב: N פעולות נוספות שהיו ברשימה נדחו אוטומטית (בחירה לפי מספר מבטלת את שאר האפשרויות שהוצגו יחד)."` to the reply when N>0. Display-only — does not change §21's underlying reject decision (Finding #2, above, is the place that decision itself would change).

### Finding #4 (P1) — "what's pending approval?" query hits the wrong table — ✅ fixed

**Verified:** confirmed. There is no `Intent`/router entry for "list pending approvals" — `Intent.NEEDS_APPROVAL`/`Handler.APPROVAL` route an action that itself requires approval, not a query about the queue. `_CONFIRM_WORDS`/`_CANCEL_WORDS` in `app.py` are exact-word matches (`"מאשר"`, `"כן"`, …), so a longer natural-language question like `"לאשר את הפעולות שממתינות לאישור"` never matches them and fell straight through every deterministic Gateway route to the general agent — which has no ActionContracts tool and picked an ordinary business table (`airtable_get(table="Tasks")`) instead.

**Fix:** new `ActionGateway.describe_pending_queue(canonical_user_id)` (`core/action_gateway.py`) — read-only, never approves/rejects, reuses the same listing format (+ age warning) as `route_confirmation_word()`'s multi-item branch, and sets the same disambiguation state so a follow-up bare ordinal still resolves correctly. Wired into `app.py` via a new, deliberately narrow `_PENDING_QUERY_RE` (requires a "pending" word near an "approval" word, or an interrogative near a "pending" word) checked after the existing confirm/cancel/override/combined/status-query branches and before falling through to the agent. Worst-case false positive is harmless (shows an accurate list instead of routing to the agent).

### Finding #5 (P1) — "זיהיתי, 0501112222" residue from BUG-129 — ✅ **confirmed pre-fix artifact, not a live gap** (`ActionContracts` export, see below)

**Verified:** `"זיהיתי"` was added to `_NAME_STOP` in `core/ingress_classifier.py` by commit `9285106` ("fix(BUG-135): stop command verbs / bot self-quote from hijacking lead-name extraction"), confirmed an ancestor of `origin/main` (`git merge-base --is-ancestor 9285106 origin/main` → true). `test_bug135_command_verb_name_stop.py` T1/T2 explicitly cover this exact self-quote pattern (`"📋 זיהיתי ליד: *משה חביב* (0501112222)"` → recovers the real name, not `"זיהיתי"`) and pass on current code.

**Note (documentation drift, unrelated to runtime correctness):** `CHANGELOG.md`'s entry for this fix still says `"Branch claude/zihuiti-name-extraction-22qitu, not yet merged"` even though the commit is on `main` — a stale line, not a code gap. Not corrected here (out of scope for this audit; flagged for the next docs-sync pass).

**Confirmed with real data (owner supplied the `ActionContracts` export after the initial draft of this doc — this is not a hypothesis anymore):**

Fix commit `9285106` landed 2026-07-22 07:09:28 UTC (10:09:28 Israel time). Contract `ac30218d-e335-45ea-b831-1e70e4195b5c` (`"Name": "זיהיתי"`, `phone: 0501112222`) has `created_at=1784665482.571` → **2026-07-21 23:24:42 Israel time — 10.75 hours before the fix commit existed at all.** This contract was created by the pre-fix classifier by construction; there is nothing left to fix in current `_NAME_STOP`.

**Why it kept resurfacing:** exactly Finding #1's bug. This contract sat as `status="pending"` in `ExecutionLedger._store` and was never re-filtered by `_is_expired()` on the warm-cache path. At the moment of the reported disambiguation (2026-07-23 13:16:03, derived from sibling `7fed5be6`'s `approved_at` in the same export — falls inside the report's stated 13:15:35–13:16:58 window), this contract was **37.9 hours old** — well past the 24h TTL — and was rejected as sibling #? in the disambiguation. With this session's Finding #1 fix, it would never have appeared in the list at all.

### Finding #6 (P0) — destructive-intent inversion — ✅ **fake-name part confirmed pre-fix; no double-damage; "garbage record" framing corrected**

**Verified — the fake-name bug itself, confirmed pre-fix with real data:** contract `02ad21bc-f19b-4076-a3f6-2217c13f68df` (`"Name": "תמחק איש קשר"`, `phone: 0536272637`, `summary: "תמחק איש קשר 0536272637"`) has `created_at=1784703096.866` → **2026-07-22 09:51:36 Israel time — 18 minutes before fix commit `9285106` landed.** Same conclusion as Finding #5: pre-fix artifact, not a live gap. `classify_ingress("תמחק איש קשר 0536272637", ...)` degrades to tier 5 (no candidate at all) on current code — verified by the existing test suite, re-run clean in this session.

**Verified — no double-damage:** the `02ad21bc` contract's `status` in the export is **`rejected`**, not executed — it was correctly one of the auto-rejected siblings (Finding #2's §21 mechanism) when `7fed5be6` was picked, and never wrote anything to Airtable. At disambiguation time it was **27.4 hours old** (also past the 24h TTL — Finding #1's fix would have hidden it too).

**Verified — no separate "delete-intent" handling exists:** `core/router/intent_router.py`'s only delete-shaped intent is `Intent.DELETE_TASK` (tasks only) — there is no equivalent for contacts/leads. A real "the user asked to delete X" flow (distinct from "don't let a delete command masquerade as a fake create") is designed as `HandlerId.DESTRUCTIVE_ENTITY_CLARIFICATION`/`DecisionReason.DESTRUCTIVE_REQUIRES_CLARIFICATION` in `docs/architecture/turn-coordinator/TURN_COORDINATOR_BEHAVIOR_CONTRACT_V1.md` §3.2 — entirely inside the **frozen, not-yet-approved** TurnCoordinator contract (TurnCoordinator layer, §1 layer 2 — zero runtime implementation today). Building any ad hoc version of this outside that frozen contract would itself violate `CROSS_LAYER_AUTHORITY_CONTRACT_V1.md` §4 prohibition #1 (parallel sources of truth) — **not implemented here**, consistent with the mandatory gate.

**"Garbage record" framing corrected — real evidence changes the picture:** the record that actually got written (via contract `7fed5be6-cc4f-4e3a-aa16-dcf9a2289419`, `"Name": "איש קשר דני לוי"`, `phone: 0501234567`, `summary: "תוסיף איש קשר דני לוי 0501234567"`) is **not** a malformed/nonsense name — it reads as a legitimate contact-add request. Its `created_at=1784749022.270` (2026-07-22 22:37:02) vs. `approved_at=1784801763.111` (2026-07-23 13:16:03) means it sat pending for **14.65 hours** before being approved — still inside the 24h TTL, so Finding #1's TTL fix alone would **not** have hidden it (this is exactly why the age-warning display, not just the TTL fix, was implemented — see Finding #1 above). The actual harm here isn't "junk data written" — it's that a **14.65-hour-old, forgotten intent silently executed** when the user picked "3" believing they were resolving something from the current conversation.

### Finding #7 (new, discovered mid-review from the executed record's own data) — "add a contact" always creates a Lead, never a Contact — **documented only, explicitly deferred to the TurnCoordinator contract**

**Discovered from:** the owner's own Airtable export of the executed record (`recK8RdYkdDmTGdob`) — `Leads` table, `Name: "איש קשר דני לוי"` (the role-noun "contact person" literally embedded in the name field), full lead-funnel metadata attached (`טמפרטורה: ❄️ קר / Cold`, `Score: 0`, `Suggested Followup: 📝 השאר במעקב / Keep Nurturing`) — for a message that said "תוסיף איש קשר דני לוי" (add **contact** Dani Levi), not a sales lead.

**Root cause, verified:** two independent classifiers exist and don't communicate:
- `core/router/intent_router.py:67` — `(r"(הוסף|צור|פתח).*(איש קשר|contact|לקוח|ספק)", Intent.CREATE_CONTACT, 0.90)` — **correctly** classifies this message as `Intent.CREATE_CONTACT`, and `risk_router.py` maps it to `airtable_add` against `Tables.CONTACTS` (`אנשי קשר (Contacts)`, a real, separate table — confirmed live and reachable via the generic dispatcher in `lead_conversion.py`/`crm.py`).
- `core/lead_candidate_handler.py` — the module that actually wins ownership of this message per BUG-056's Tier-1 precedence — never references `Intent.CREATE_CONTACT` or `Tables.CONTACTS` at all (`grep` confirms zero occurrences). It is hardcoded to always propose `airtable_add table=Leads`, regardless of what the Router's own intent classification says.

**Why not fixed here:** this is not a new problem to design a solution for — it is **scenario 7, verbatim, in the frozen `docs/architecture/turn-coordinator/TURN_COORDINATOR_BEHAVIOR_CONTRACT_V1.md`** (line ~543): the contract's own worked example is literally `"תוסיף איש קשר בדיקה טלפון 0500000000"` → `intent_signal` EXPLICIT `CREATE_CONTACT` should win ownership over the capture flow, which should only supply payload, not decide create-vs-update/which-table. This production incident is real-world confirmation that the exact bug scenario 7 was designed to fix does happen, not just a hypothetical — but the fix is TurnCoordinator's own ownership-arbitration mechanism (layer 2, §1), currently zero-runtime-implementation and blocked on approval + a full Cross-Layer Impact Matrix for the contract itself. Patching `lead_candidate_handler.py` to special-case `Intent.CREATE_CONTACT` right now would build a parallel arbitration mechanism competing with the planned one — exactly `CROSS_LAYER_AUTHORITY_CONTRACT_V1.md` §4 prohibition #1. **Not implemented, per explicit owner direction** (this finding doesn't block reliable sample-gathering the way Findings #1/#3/#4 did — it's a correctness gap TurnCoordinator itself is meant to close, not one that corrupts staging test results in the meantime).

---

## 2. Cross-Layer Impact Matrix (`CROSS_LAYER_AUTHORITY_CONTRACT_V1.md` §2)

### שכבה 1 — Core Reasoning / BUG-104
touched: not touched
input impact: none
output impact: none
authority impact: none
shared identifiers: none — no `core/leads_reasoning_projection.py`/`core/adapters/leads_adapter.py` identifier referenced or changed
invariants: n/a
failure semantics: n/a
observability: n/a
cross-layer tests: n/a
**Proof of non-impact:** `git diff --stat` for this change touches only `core/action_gateway.py`, `app.py`, `test_staging_23jul_findings.py`; `grep -n "leads_reasoning_projection\|BUG-104\|FEATURE_CORE_REASONING_LEADS_STATE"` on the diff returns nothing. `test_bug104_*.py` not run as part of this change (none of BUG-104's own modules were touched) — no regression possible by construction (no shared import added).

### שכבה 2 — TurnCoordinator
touched: not touched (deliberately — Finding #2's classification design, Finding #6's DESTRUCTIVE_ENTITY_CLARIFICATION work, and Finding #7's CREATE_CONTACT ownership-arbitration gap — TurnCoordinator contract §3.2 and scenario 7 respectively — are all explicitly deferred, not implemented, for exactly this reason)
input impact: none
output impact: none
authority impact: none
shared identifiers: none — no `HandlerId`/`ReplyOwnerKind`/`DecisionReason`/`TurnCoordinator`/`TurnEnvelope` symbol referenced or defined
invariants: n/a
failure semantics: n/a
observability: n/a
cross-layer tests: n/a
**Proof of non-impact:** `grep -rn "TurnCoordinator\|TurnEnvelope\|HandlerId\|ReplyOwnerKind" core/action_gateway.py app.py` shows no new occurrences introduced by this diff (existing `core/turn_envelope.py` observation hooks in `app.py` are untouched — this change's new code is inserted in the "2.55" confirm/cancel/disambiguation block, entirely before/independent of the "1.7"/TurnEnvelope construction site and the later "2.6" pronoun-resolution section).

### שכבה 3 — F52 / Phase 4C Action & Tool Contract
touched: indirectly
input impact: none — no `ToolMeta`/`tools/schemas.py`/`tools/dispatcher.py` change
output impact: `describe_pending_queue()`'s reply text and the two disclosure-suffix additions are new outbound strings, but neither goes through `compose_status_reply()`/`ActionFact`/`FEATURE_UNIFIED_STATUS_FORMATTER` — they are plain legacy-style text appended directly, matching the existing (pre-change) pattern of `route_disambiguation()`'s/`route_confirmation_word()`'s own replies, which also bypass the unified formatter today. No new formatter surface created or bypassed differently than before.
authority impact: none — `tool_registry.enforce()`/`action_validator.validate_action()` untouched; `describe_pending_queue()` never calls `dispatch_tool()`/`propose_action()`/`approve()`/`reject()`.
shared identifiers: none new — reuses existing `ActionContract`/`_describe_contract_for_disambiguation` (already scoped to layer 4, unchanged in meaning).
invariants: unaffected — C53a `{ok, tool, external_id, evidence, user_message}` result contract not touched (no dispatcher/tool call added).
failure semantics: `describe_pending_queue()`/`_PENDING_QUERY_RE` fail open to "no match → falls through to the agent" (same as before this change) — a regex miss or an exception in the age-formatting helper cannot block or corrupt an approval; worst case is the pre-existing agent-guesses-a-table behavior, not a new failure mode.
observability: new `logger.info("[ActionGateway] describe_pending_queue: ...")` log line, matching the existing logging convention for every other Gateway route in `app.py`.
cross-layer tests: `test_staging_23jul_findings.py` asserts `describe_pending_queue()` never calls the tool executor (`executions7 == []`) and never changes contract status — the boundary this layer cares about (no execution without a real approval decision).

### שכבה 4 — Durable Atomic Approval
touched: directly
input impact: `find_live_by_user()` now filters on `_is_expired()`/`CONTRACT_PENDING_TTL_SECONDS` on the warm-cache path — same input contract as the existing cold-cache/repository path, now consistent. `route_disambiguation()`/`route_combined_word()` also now count (but do not otherwise change) sibling rejections.
output impact: `find_live_contracts()` can now return fewer items than before for a user with a long-cached, TTL-expired "pending" contract (was previously an unbounded-duration inconsistency bug, not an intended behavior any caller depended on positively — verified via the full existing test sweep, see §7). `approve()`'s return value (consumed by `route_disambiguation()`/`route_combined_word()`) is unchanged; only the wrapping text in those two callers changed.
authority impact: none — `approve()`'s own authorization boundary (`_has_approval_authority`/`APPROVAL_POLICY_SELF_CONFIRM`) untouched, not called by any new code path.
shared identifiers: `CONTRACT_PENDING_TTL_SECONDS`/`_is_expired` imported from `core.action_contract_repository` into `core.action_gateway` — a **reference**, not a redefinition (no new TTL constant invented; `CROSS_LAYER_AUTHORITY_CONTRACT_V1.md` §4 prohibition #9 explicitly permits this pattern, same as `ActionFact`'s precedent in §3 of that doc).
invariants: BUG-114's `mark_context_interrupted()` filter (`(c.reconfirmation_required or not c.context_interrupted)`) is untouched and still applied downstream of `find_live_by_user()` — TTL filtering happens strictly before that check runs, no interaction. BUG-115's bookmark short-circuit (`route_confirmation_word()`'s `_bookmark` check) is untouched and still runs before any call to `find_live_contracts()`.
failure semantics: identical to before — `find_live_by_user()` still fails open to "no repository configured → in-RAM only," `describe_pending_queue()`/age-formatting cannot raise into a failed approval (pure string formatting on already-validated `ActionContract` fields).
observability: none removed; existing `[ActionGateway] disambiguation:`/`combined_word confirm:` log lines extended with a new `rejected_siblings=%d` field, additive only.
cross-layer tests: `test_staging_23jul_findings.py` (16 new assertions) + full existing `test_action_gateway.py`/`test_bug_batch_approval_preserved.py`/`test_bug115_confirmation_routing_bookmark.py`/`test_bug117_batch_preview_precedence.py`/`test_bug070_combined_wording.py`/`test_bug070_pending_approval_multi.py`/`test_pr0c_action_contract_repository.py`/`test_pr0c_action_contracts_persistence.py`/`test_stage_b_full_suite.py`/`test_c89_preview_confirmation.py`/`test_bug114_context_interrupt_amplification.py` re-run clean (see §7) — this is exactly the cross-layer regression surface for layer 4 changes in this repo's own convention (every prior BUG-11x fix here re-ran the same set).

### Cross-Cutting Guard — RP5 Evidence Finalization (§1.5)
applies: yes — `route_disambiguation()`/`route_combined_word()`'s replies are user-facing action-status text, and `describe_pending_queue()` answers a "what's pending" question.
Impact: none of the changes here invent a new success/failure/pending claim — `describe_pending_queue()` never asserts an outcome (it lists `ActionContract.status == "pending"` items verbatim, the same canonical field RP4/`core/turn_evidence.py` already reads); the disclosure suffix states a fact already true before this change (siblings were already being rejected — only the *telling the user* part is new) and does not change `approve()`'s own `ActionFact`/status. No new grounding-check or evidence-classification mechanism was created — this reuses `ActionContract.status`/`find_live_contracts()` exactly as every existing Gateway route already does, not a parallel mechanism.

---

## 3. Manual action items (not performed by this session)

1. **Review (not necessarily delete) `recK8RdYkdDmTGdob`** (Leads, `my-bot-approval-staging` base, from contract `7fed5be6`, "איש קשר דני לוי", 0501234567) — confirmed **not** garbage data (§1 Finding #6): a legitimate-looking contact-add request that sat pending 14.65h before silently executing on an unrelated disambiguation pick. The `"תמחק איש קשר"` sibling (`02ad21bc`) was confirmed rejected, not executed — no second record to check there. Needs the owner to confirm whether `"דני לוי"` is a contact they actually want kept.
2. ~~Confirm the `my-bot-approval-staging` deploy's commit hash~~ — **resolved for Findings #5/#6** by the `ActionContracts` export (§1.1): both fake-name contracts were *created* before fix commit `9285106` existed in git at all, independent of deploy timing. Still generally good practice to confirm current deploy freshness for unrelated reasons, but no longer blocks this doc's conclusions.
3. **`CHANGELOG.md`'s BUG-129/BUG-135 entry** still says "not yet merged" though the commit is on `main` — a docs-sync fix, out of scope here.
4. **Finding #2's classification design** — owner decision needed on how to detect "genuinely competing" vs. "coincidentally co-pending" contracts before any `single_choice`-vs-`per_item` semantics change is implemented.

---

## 4. Explicit non-goals of this fix

- Does **not** shorten `CONTRACT_PENDING_TTL_SECONDS` (24h) — that's a policy call with the same TMA-approval-latency tradeoff already documented at its definition; not revisited here.
- Does **not** change `route_disambiguation()`/`route_combined_word()`'s underlying reject-all-siblings *decision* (Finding #2) — only adds visibility (age, disclosure) around an unchanged decision.
- Does **not** implement `DESTRUCTIVE_ENTITY_CLARIFICATION`/any delete-intent flow for contacts/leads (Finding #6) — blocked on the frozen TurnCoordinator contract's own approval + a full Cross-Layer Impact Matrix for that specific change, per §1 layer 2 above.
- Does **not** touch `ExecutionLedger.mark_context_interrupted()`/BUG-114's filter, `route_confirmation_word()`'s BUG-115 bookmark, or `should_prefer_batch_preview()`/BUG-117's Tier-2 precedence — all read as correct and unrelated to these findings.

---

## 5. Files changed

- `core/action_gateway.py` — `find_live_by_user()` TTL fix; `_format_pending_age_suffix()` + age display in `route_confirmation_word()`'s listing; `describe_pending_queue()`; disclosure text in `route_disambiguation()`/`route_combined_word()`.
- `app.py` — `_PENDING_QUERY_RE` + new deterministic routing branch calling `describe_pending_queue()`.
- `test_staging_23jul_findings.py` (new) — 24 assertions covering Findings #1/#3/#4.

## 6. Tests

New: `test_staging_23jul_findings.py`, 24/24 passing.

Full regression (existing suites most likely to interact with this change, all re-run clean after the fix): `test_action_gateway.py` (43), `test_bug_batch_approval_preserved.py` (33), `test_bug115_confirmation_routing_bookmark.py` (22), `test_bug117_batch_preview_precedence.py` (11), `test_bug070_combined_wording.py` (27), `test_bug070_pending_approval_multi.py` (9), `test_pr0c_action_contract_repository.py` (14), `test_pr0c_action_contracts_persistence.py` (16), `test_stage_b_full_suite.py` (128/128), `test_c89_preview_confirmation.py` (9/9), `test_bug114_context_interrupt_amplification.py` (12), `test_bug135_command_verb_name_stop.py` (10). Plus `smoke_tests.py`, `test_integration.py`, `python3 -m compileall -q .`, and the full `test_*.py` sweep (168 files) — see commit for the sweep's exact pass/fail accounting.

**Fix not yet production-verified** — the underlying bug (Finding #1's warm-cache TTL gap) is confirmed against real `ActionContracts` data (§1.1: 3 of 6 siblings were 27-38h old, past the 24h TTL, and still shown/rejected as live), and the "stale intent silently executed" root cause of Finding #6's actual harm is confirmed the same way (14.65h-old contract executed unnoticed). But the **fix itself** — this session's code changes — has not yet been observed running against live/staging traffic. Per this repo's own rule, do not upgrade this doc's status past "code done, root cause confirmed" until a real post-deploy sample shows the age warning/TTL filtering/disclosure text firing in practice.
