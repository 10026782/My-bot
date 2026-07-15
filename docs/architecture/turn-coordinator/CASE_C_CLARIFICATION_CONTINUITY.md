# Case C — Clarification breaks operational continuity

Program: TurnCoordinator (consumes F52/Phase 4C audits — see
`../f52-unified-approval-runtime/audits/phase-4c/TURN_OWNERSHIP_EXTENSION.md`)
Status: Verified against `main` `5aa6467` (2026-07-15). Findings below are
code-verified with file:line citations, not inferred from the abstract
description alone — same standard as Cases A/B in the proposal and the
turn-ownership extension.

## The scenario

A multi-item request requires clarification for one item. After the user
answers, the system renders the completed list and claims the actions are
pending approval, but no live approval target exists for (some or all of)
what's claimed.

Two distinct failure modes, and this codebase currently exhibits **both**,
via two independent mechanisms — not the same bug wearing two names:

- **C1** — an existing durable queue loses ownership across clarification.
- **C2** — no durable queue was ever created, but the agent claims one exists.

## C1 — verified: `_queue_approval()` has no live-contract guard across turns

`event_bus.BatchQueueStore` (added in PR #345, `event_bus.py:200-235`) exists
specifically to guarantee **at most one live `ActionContract` per identity at
a time** for a multi-item request — its own module comment is explicit:
*"This deliberately avoids letting >1 contract be simultaneously 'pending'
for the same identity... batch items must never reach 'pending' status more
than one at a time."* That guarantee is enforced by `_mutating_approvals_this_turn`
(`app.py:2176`, reset to `0` at the top of every `run_agent()` call) — a
**per-turn, in-process counter**, not a check against `find_live_contracts()`.

`_queue_approval()` (`app.py:730`) — the only function that actually creates
a live `ActionContract` — checks two things before proposing: recent-execution
dedup (`executed_action_cache`) and same-tool-same-inputs pending dedup
(`bus.find_pending_by_business_fingerprint()`). It does **not** call
`find_live_contracts(identity.memory_key)` or check `BatchQueueStore` before
proposing. Verified directly against `app.py:730-820` for this finding — no
such check exists in the function body.

**Concrete failure sequence:**
1. Turn 1: user asks for 5 items; item 3 is missing required info. Claude's
   response includes `tool_use` for items 1/2/4/5 and clarifying text about
   item 3 in the same response (C54, `app.py:2210-2235`, does not suppress
   this — it only suppresses text that also matches approval-status
   language, and a genuine clarification question does not). Item 1 becomes
   a live `ActionContract`; items 2/4/5 are deferred into `BatchQueueStore`
   per PR #345's design.
2. Turn 2: user answers the clarification for item 3. `_mutating_approvals_this_turn`
   resets to `0` for this fresh `run_agent()` call — it has no memory of
   turn 1's counter. If Claude now calls the tool for item 3,
   `_queue_approval()` proposes it directly, with **no check that item 1's
   contract from turn 1 might still be live**.
3. Result: two independently-live `ActionContract`s for the same identity
   (item 1 from turn 1, item 3 from turn 2), which is exactly the state
   `BatchQueueStore` was built to prevent. Per the PR #345 commit message's
   own documented (and empirically tested-and-rejected) finding: once >1
   contract is simultaneously live for an identity,
   `route_confirmation_word()` stops directly executing a plain "מאשר" and
   falls into the `len(live)>1` disambiguation branch instead, and
   `route_disambiguation()`/`route_combined_word()` reject every sibling
   contract the moment one is selected by number. Items 2/4/5, still sitting
   untouched in `BatchQueueStore`, are not part of that disambiguation at
   all — the user has no way to know they still exist, and nothing in the
   current disambiguation prompt mentions them.

This is not a hypothetical composition of two features — it is the same
multi-contract hazard PR #345 explicitly designed against, reachable through
a code path (a fresh `run_agent()` turn) that its per-turn counter cannot see
across.

## C2 — verified: no gate exists for an unevidenced "pending approval" claim when `FEATURE_ACTION_GATEWAY` is off

`core/anti_hallucination.py` has two separate regexes for two separate claim
shapes:
- `_AGENT_ACTION_STATUS_PATTERN` (`core/anti_hallucination.py:521`) — past-tense
  completion verbs only (נוסף/בוצע/נשלח/etc). Checked **unconditionally**
  ("always on, not gated by `_gateway_active`" per its own comment,
  `core/anti_hallucination.py:655-668`) against `_has_write_tool_evidence()`.
- `_AGENT_PENDING_STATUS_PATTERN` (`core/anti_hallucination.py:537`) —
  "ready/pending approval" language (e.g. "ממתינה לאישור"). Checked **only**
  inside `if _gateway_active and (...)` (`core/anti_hallucination.py:611-629`).

`_gateway_active` is passed into `sanitize_agent_response()` as
`_flag_enabled("FEATURE_ACTION_GATEWAY")` at its one call site
(`app.py:2422-2425`). `feature_flags.py:49` documents this flag's default as
**OFF**. There is no other call site and no fallback check for pending-
approval language when the flag is off — verified by reading
`sanitize_agent_response()`'s full body (`core/anti_hallucination.py:598-680+`):
every other gate in that function targets *completion* claims or *no-tool*
diagnostic claims, none of them match `_AGENT_PENDING_STATUS_PATTERN`'s
wording independently of the gated block.

**Concrete failure sequence:** with `FEATURE_ACTION_GATEWAY` off (the
documented default), an agent turn that emits *only* text — no `tool_use` at
all, e.g. because it believes (correctly or not) that a prior turn already
queued everything and it just needs to summarize — and that text says
something shaped like "5 הפריטים ממתינים לאישור הבעלים" passes
`sanitize_agent_response()` with **zero checks against it**. `verify_result_claim()`
and the `_NO_TOOL_CLAIMS` gates target different claim shapes (live
check/action claims, not future/pending framing) — confirmed by inspecting
their claim-pattern lists, none of which overlap with
`_AGENT_PENDING_STATUS_PATTERN`'s wording.

**Compounding note:** even when `FEATURE_ACTION_GATEWAY` **is** on, the check
at `core/anti_hallucination.py:622` (`any(r.get("tool") == "__approval_queued__" for r in tool_results)`)
is presence-based, not scope-accurate — it asks "was *any* approval queued
this turn," not "does the claimed count/identity match what was actually
queued." A turn that queues 1 of 5 claimed items still passes this check and
the agent's overstated "all 5 pending" text is suppressed as if it were a
harmless redundant echo (the Single-Speaker branch's intended case), not
flagged as a scope mismatch. This is a milder, gateway-on variant of the same
underlying problem C2 describes at its worst (gateway off).

## Required invariants (as specified, unchanged)

1. A clarification must retain a stable owner reference: `draft_id` or
   `queue_id` plus `item_id`.
2. Resolving a clarification must update the same owned object.
3. A conversational draft must be materialized into a durable approval queue
   before an approval prompt is emitted.
4. The system must never emit a present-state claim such as "pending
   approval" unless a live pending approval target exists.
5. Phase 0 must log enough state to distinguish C1 from C2.

## Scope split — what's Phase 0 vs. what isn't

Invariants 1-4 are **behavioral** requirements — they change what the system
does (block a premature approval-prompt, tie a clarification reply to a
specific owned object). That is Phase 1+ work (materialization) and Phase 5
work (Commitment Grounding, already scoped in the proposal as log-only
first), not Phase 0. Building them now would violate Gate A's "no behavior
change" constraint this session has held to throughout Phase 0.

Invariant 5 **is** Phase 0 scope — pure observation, no behavior change — and
is implemented below.

## Phase 0 addition: C1/C2 distinguishing signal

Two independent, narrow, log-only checks, both reusing state
`_build_and_log_turn_envelope()` and `sanitize_agent_response()` already
compute — no new reads, no new stores:

- **C1 signal** — `len(live_contracts) > 1` for one identity at turn start.
  This is a direct, unambiguous symptom check: BatchQueueStore's own design
  invariant is "at most 1 live contract per identity," so seeing more than
  one *is* the ownership-conflict signature, independent of whether
  clarification caused it.
- **C2 signal** — the turn's final reply matches `_AGENT_PENDING_STATUS_PATTERN`
  while this turn's envelope shows zero pending queues (`queue_count == 0`)
  and no `__approval_queued__` evidence was produced this turn. This does not
  block or alter the reply (Phase 0 never does) — it only logs that the
  claim-vs-state mismatch occurred, for the same reason Phase 5's Commitment
  Grounding is speced as log-only first: measure real frequency before
  deciding what to enforce.

See implementation in `core/turn_envelope.py` (`detect_case_c2_signal()` /
`log_case_c_signal()`) and its two call sites in `app.py` — one at turn
start (C1, reuses `_build_and_log_turn_envelope()`'s already-fetched
`live_contracts`), one right after `sanitize_agent_response()` computes
`final_reply` (C2, reuses `tool_results_log` already assembled for that
call). Both log through the same PII boundary `log_turn_envelope()` already
enforces (fingerprinted identifiers, no payload/text content beyond a
boolean pattern-match result).

### Known measurement gap in the C2 detector, found while testing it

`detect_case_c2_signal()` deliberately reuses `_AGENT_PENDING_STATUS_PATTERN`
(single source of truth, not a duplicated regex) rather than writing a new
one. That regex's forms
(`ממתינ[הת]\s?(ל)?אישור`, `מוכנ[הת]?\s.{0,25}(לאישור|ממתינ)`) only match
singular ("ממתינה"/"ממתינת"/"מוכנה"/"מוכן") grammatical forms — a plural
claim about a list ("5 הפריטים **ממתינים** לאישור"), which is exactly the
natural Hebrew phrasing for Case C's own multi-item scenario, does not
match. Confirmed empirically while writing `test_turn_envelope.py`: the
literal string "5 הפריטים ממתינים לאישור הבעלים" does not trigger the
pattern; "הפעולה ממתינה לאישור" (singular, matching one of the regex's
literal branches) does.

**Consequence:** the C2 log-only signal will undercount true positives for
list-shaped claims specifically — the exact shape Case C is about — until
`_AGENT_PENDING_STATUS_PATTERN` itself gains plural forms. This is not fixed
here: it is a shared regex also used by `sanitize_agent_response()`'s
gateway-on branch, so widening it is a decision for whoever owns
`core/anti_hallucination.py`'s pattern set, not a silent one-line patch
bundled into Phase 0 log-only work. Recorded here so the eventual Phase 0
measurement data ("how often does C2 actually fire") is read with this known
undercount in mind, not treated as a precise rate.
