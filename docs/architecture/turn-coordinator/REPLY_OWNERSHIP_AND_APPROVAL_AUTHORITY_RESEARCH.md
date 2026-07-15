# Reply Ownership & Approval Authority — Architectural Research

Program: TurnCoordinator (consumes F52/Phase 4C audits + this program's own prior docs)
Status: **RESEARCH ONLY.** No code changed by this document. No implementation started.
Baseline: `main` `6d7875b` (2026-07-15), the commit this research evaluates.

**Naming note, flagged up front, not decided unilaterally:** this document's §2 is titled
"Case C — Phantom Approval Prompt" per explicit instruction. That name collides with the
already-existing `CASE_C_CLARIFICATION_CONTINUITY.md` ("Case C — Clarification breaks operational
continuity", with its own C1/C2 sub-cases). The two are related — Phantom Approval Prompt is the
single-turn, no-clarification-needed manifestation of the same underlying gap C2 already names —
but they are not the same scenario and using the same top-level letter for both will confuse anyone
who greps "Case C" later. Recommend the owner decide the final naming (e.g. renumber this one Case D,
or fold it into the existing doc as a named sub-case) — not decided here.

---

# Part 1 — Agent Ownership Hijack

## 1.1 Reply/ownership paths per channel, as they exist today

| Channel | Entry point | Who composes the reply | file:line |
|---|---|---|---|
| Telegram text | `run_agent()` → tool loop → `sanitize_agent_response()` | Agent's own generated text, filtered post-hoc | `app.py:1679` (def), `app.py:2482` (sanitize call) |
| WhatsApp (Twilio + Meta) | same `run_agent()` | identical — same code path, different `channel=` value | `app.py:3208`, `app.py:3405`, `app.py:3478`, `app.py:3555` (call sites) |
| Telegram callbacks | `_handle_approval_callback_impl()` | `ActionGateway.compose_status_reply()` (Gateway-authored), edited directly into the Telegram message | `app.py:1211` (def), `core/action_gateway.py:1586` (`compose_status_reply`) |
| TMA | `_queue_tma_write_approval()` + the 6 route handlers + `_claim_and_execute_approval()` | Structured JSON (`{ok, message, status_code, ...}`), not free text | `tma_api.py:444`, `tma_api.py:2527` (approve route's execute helper, per `TURN_OWNERSHIP_EXTENSION.md`'s AP-13 row) |
| Scheduler/background | `followup_engine.py`'s `request_followup_approval()` / `core/lead_recovery.py`'s `request_recovery_approval()`, called from `run_followup_scan()`/`run_recovery_scan()` | A fixed-template Telegram notification to the owner, via `bus.request_approval()`/direct `bot.send_message()` | `followup_engine.py:177` (def), `followup_engine.py:246` (`run_followup_scan`, scheduler-invoked entry point), `core/lead_recovery.py:217` (def), `core/lead_recovery.py:297` (`run_recovery_scan`) |

**Structural observation:** exactly one of these five (Telegram + WhatsApp text) ever produces
*agent-generated free text* as the reply. The other three (callbacks, TMA, scheduler) all compose
their reply from a fixed template or a structured payload — the agent's LLM is not in that loop at
all. This matters directly for §1.4 below: the ownership-hijack risk is concentrated almost entirely
in the Telegram/WhatsApp text path, because that is the only path where an LLM decides the words.

## 1.2 Who is authorized today for each responsibility

| Responsibility | Authorized component today | Can the agent (LLM) influence it? | file:line |
|---|---|---|---|
| Select handler (AGENT/APPROVAL/CLARIFY/TOOL/BLOCK/...) | `core/router/` (`intent_router`, `risk_router`, `domain_router`) — runs **before** the agent is ever invoked | No — routing is a pre-agent, deterministic classification step | `core/router/route_decision.py:135` (`Handler` enum), `app.py:2107` (`route = _safe_route(...)`) |
| Create an `ActionContract` | `ActionGateway.propose_action()`, called only from `_queue_approval()` (agent tool loop), `_queue_tma_write_approval()` (TMA), `propose_gated()` (scheduler), `_propose_lead_write()` (lead capture) | Indirectly — the agent chooses *whether* to call a `requires_approval` tool, but the actual `ActionContract` object is built by `propose_action()`, not by the agent's text | `core/action_gateway.py` `propose_action()`, `app.py:783` (`_queue_approval()`'s call) |
| Queue an approval (make it visible/actionable) | Same `propose_action()` path, plus `bus.request_approval()` for the Telegram button | No agent-text path exists — only a real tool call reaches this | `app.py:821` (`bus.request_approval(...)`) |
| Cancel an `ActionContract` | `ActionGateway.reject()` **only** — called from `route_cancellation_word()` (deterministic text parser) or the Telegram reject callback | **No.** Verified: zero agent-exposed tool touches contract lifecycle (see §1.4) — the agent has no tool-call path to cancellation at all | `core/action_gateway.py:997` (`def reject`) |
| Complete/execute an `ActionContract` | `ActionGateway.approve()` → `_execute_contract()` → dispatcher → provider, gated by the PostgreSQL atomic claim | **No.** Same as above — no agent tool reaches `approve()`/`_execute_contract()` | `core/action_gateway.py:1230` (`def approve`) |
| Compose the final user-facing text | Agent's own LLM output (Telegram/WhatsApp), OR `compose_status_reply()` (Gateway, callbacks), OR a fixed template (TMA/scheduler) | **Yes, unrestricted, for the Telegram/WhatsApp path** — this is the one authority the agent genuinely and legitimately has, and it is also the entire attack surface for both Part 1 and Part 2 of this research | `core/anti_hallucination.py:598` (`sanitize_agent_response`, the only filter on this authority) |

**Verified, not assumed:** `tools/schemas.py` exposes 17 tool names to the agent (grep, zero
matches for approve/reject/cancel/complete). None of them touch `ActionContract` lifecycle. This
means the literal claims in the user's Point 1 list — "the agent claimed to create/manage an action
instead of routing to tools" and "the agent returned a reply that supposedly completed or cancelled
a task" — can **only** happen as **text-only fabrication**, never as an actual unauthorized mutation.
The Gateway/dispatcher/tool-registry boundary (§4C-1A, "Execution Boundary" in the TurnCoordinator
proposal) already holds for *execution*. What is unprotected is *narration* — the agent claiming
something happened when the real system state disagrees or never existed. This reframes Part 1: it
is not a privilege-escalation risk (the agent cannot literally act outside its authority), it is
entirely a **truthfulness-of-narration** risk layered on top of a sound execution boundary.

## 1.3 Where two layers could both become reply owner in the same turn

Three distinct mechanisms found, not one:

**(a) Same-response contradiction — mitigated.** Claude's response can contain both a `tool_use`
block and text in the same turn. `C54` explicitly suppresses text alongside `tool_use` when the text
matches approval/pending language, reasoning that "the text was generated before seeing the tool
result." `app.py:2210-2235`. This is a real, working mitigation for the narrowest case.

**(b) Cross-turn narration after Gateway already replied — only partially mitigated.** PR #341/#343/#345
("Single-Speaker") fixed the *documented, reproduced* incident: an approval-pending message already
sent this turn, followed by the agent's own `sanitize_agent_response()` output describing the same
thing again or contradicting it. The fix is presence-based (`__approval_queued__` sentinel check) —
confirmed in this session's prior work (`TURN_OWNERSHIP_EXTENSION.md` finding 3) that this is a
**stopgap** (pattern suppression), not a structural single-owner mechanism, and confirmed again here
that it is **gated behind `FEATURE_ACTION_GATEWAY`**, default off (`feature_flags.py:49`,
`app.py:2493` `_flag_enabled("FEATURE_ACTION_GATEWAY")`).

**(c) Genuine concurrency race — unmitigated, not previously documented in this program's docs.**
`_handle_approval_callback_impl()` (a button press) and `run_agent()` (a text message) are reachable
from two independent Flask request handlers. Verified: `app.py` has exactly one relevant lock,
`_pending_approvals_lock` (`app.py:94`), which only guards the router-level `_pending_approvals` dict
(AP-09) — it does not span `ActionContract` resolution or reply composition. `ExecutionLedger` has
its own internal `self._lock` (protects the RAM index during a single contract's lifecycle
transition), but nothing prevents a callback resolving contract X and a concurrent text turn
composing an unrelated reply for the same identity from both reaching `bot.send_message()`
independently. If the process runs with more than one worker (gunicorn — see `requirements.txt`),
this is a real, architecturally-open race, not just a same-process ordering question. **This is new
evidence this research adds; it was not previously named as its own category in this program's docs.**

## 1.4 Does `OwnershipSignal` (`6d7875b`) cover all hijack cases, or only document some?

**Only documents some. Concretely, verified gap-by-gap:**

1. **Covers:** the Phantom Approval Prompt shape specifically — `agent_claimed_approval` (via
   `_AGENT_PENDING_STATUS_PATTERN`) with `tool_use_emitted=False` and `approval_queued=False`. This
   is exactly Part 2 of this research (§2). `core/turn_envelope.py`'s `OwnershipSignal`/`is_hijack`.
2. **Does NOT cover cancellation/completion fabrication.** Verified directly: neither
   `_AGENT_PENDING_STATUS_PATTERN` nor `_AGENT_ACTION_STATUS_PATTERN` contains any cancellation
   vocabulary (grep for "בוטל"/"ביטלתי"/"בטלתי"/"cancel" in `core/anti_hallucination.py`: zero
   matches). An agent turn that says "ביטלתי את המשימה" (I cancelled the task) with no tool call and
   no live contract touched would trigger **neither** the existing Single-Speaker gate **nor**
   `OwnershipSignal`'s `is_hijack` (which only checks the *pending*-language pattern). This is a real,
   previously-undocumented blind spot this research found.
3. **Does NOT cover the concurrency race (§1.3c).** `OwnershipSignal` is computed and logged inside
   `run_agent()`'s own execution — it has no visibility into a concurrent callback handling the same
   identity. It can prove "this turn, in isolation, made an unevidenced claim" — it cannot prove or
   disprove "two replies were sent for what the user experienced as one turn."
4. **Does NOT cover TMA or scheduler competing-reply risk**, because (per §1.1) neither path ever
   produces LLM-authored text — there is structurally nothing for `OwnershipSignal` to check there.
   This is correctly out of scope, not a gap.
5. **Is observation only, by design and by explicit instruction that built it** — even where it does
   detect the hijack shape, it logs a WARNING; it does not block, alter, or prevent anything. Every
   instance recorded so far (if any) already reached the user unmodified before the log line was
   written.

**Conclusion for 1.4:** `OwnershipSignal` is a correct and useful *detector* for the one scenario it
targets, and this research's own Part 2 leans on it as the evidentiary base for Case C /
Phantom Approval Prompt. It is not, and was never claimed to be, a general hijack-coverage
mechanism — items 2 and 3 above are real, unaddressed gaps that a structural invariant (not another
pattern list) must close.

## 1.5 Proposed structural invariants

**Reply Ownership Invariant (proposed wording):**
> For any given inbound event (text message or callback), exactly one component may send a
> user-facing reply. Once a component has claimed ownership of the turn (by beginning to compose or
> send a reply), no other component may independently send a competing reply for the same event,
> even if it resolves concurrently.

**Approval Authority Invariant (proposed wording, Part 1 scope — narrower version restated formally
for Part 2 in §2.5):**
> Agent-generated text may describe, propose, or explain an action. It may never be the mechanism by
> which an `ActionContract`'s lifecycle state (created / approved / rejected / completed) is
> asserted to the user. Every lifecycle-state claim reaching the user must trace to a real
> `ActionContract`/`ActionFact` read at the moment the claim is rendered, not to LLM-generated prose
> alone.

### Alternatives for enforcing Reply Ownership

| # | Alternative | How it would work | Pros | Cons |
|---|---|---|---|---|
| A | **Formal `reply_owner` claim, decided before composition** (the TurnCoordinator proposal's Phase 3, already speced) | A `TurnCoordinator`/gate decides, before any component starts composing text, who owns this turn's reply; every send call checks the claim first | Structural, closes the concurrency race (§1.3c) that pattern-matching cannot; matches the already-approved Phase 3 design | Not yet built; requires touching every send call site (5+ channels); needs a claim store (in-memory is fine single-instance, per the proposal's own persistence analysis) |
| B | **Distributed lock per identity around the whole turn** (mutex from ingress to reply-sent) | Acquire a per-`canonical_user_id` lock at the earliest point (ingress gate), release after the reply is sent | Simple mental model, directly kills the race | Coarser than needed — serializes unrelated concurrent activity for the same user (e.g. a callback and an unrelated new message both wait); risk of deadlock/stuck locks if a request crashes mid-hold without releasing |
| C | **Continue with presence-based suppression, extended to more patterns** (status quo, patched) | Add cancellation vocabulary to the existing regex sets, keep expanding as new gaps are found | Zero new architecture, fast to ship | This is exactly the approach already shown (§1.4, §2.4) to have a structural ceiling — each fix closes one instance, the next one it doesn't foresee gets through; does not touch the concurrency race at all |

**Recommendation:** Alternative A (formal `reply_owner` claim) for the structural fix, because it is
the only option that closes §1.3c (the concurrency race), which no pattern-based approach — however
extended — can address by construction (patterns operate on already-generated text; they cannot
retroactively un-send a message a concurrent process already sent). Alternative C is not a
recommendation to reject outright — it remains useful as the *interim* signal-gathering layer while A
is built (this is exactly what `OwnershipSignal` already is), consistent with this program's
established "observe, then decide, then enforce" phasing.

---

# Part 2 — Case C / "Phantom Approval Prompt" — Commitment Without Contract

## 2.1 Reproduction of the "פר 349" scenario, traced through code

```
User:  "צור משימה לבדוק פר 349 עד ל-8 בערב"
Agent: "✅ המשימה מוכנה להוספה... שלח מאשר"
```

Trace, `run_agent()` (`app.py:1679`):
1. Router resolves `Intent.CREATE_TASK` (`core/router/route_decision.py:31`), `Handler.AGENT` for an
   owner/general-domain request (per `core/router/test_router.py`'s own fixture data — the same
   intent routes to `Handler.APPROVAL` for manager+finance-domain instead, confirming handler
   selection is role/domain-sensitive, not fixed per intent).
2. `run_agent()` reaches the Claude tool-use loop. Claude's response, in the reproduced failure, is
   **text only** — no `tool_use` block. Nothing calls `dispatch_tool()`, nothing calls
   `_queue_approval()`, nothing calls `ActionGateway.propose_action()`.
3. `tool_uses` is empty → `final_reply = text_blocks[0].text` (`app.py:2238`) → loop breaks
   immediately. `tool_results_log` stays empty (nothing was ever appended to it).
4. `final_reply = sanitize_agent_response(final_reply, tool_results_log, _gateway_active=...)`
   (`app.py:2482`). Traced exhaustively against every gate in that function body:
   - `_gateway_active` branch (`core/anti_hallucination.py:611`) — skipped entirely if
     `FEATURE_ACTION_GATEWAY` is off (`feature_flags.py:49`, documented default).
   - `verify_result_claim()` (`core/anti_hallucination.py:485`) — checks `_POSITIVE_CLAIMS`
     (completion verbs: נשלח/בוצע/נוצר/נשמר/הוסף/עודכן/נרשם) against `_all_failed(tool_results)`.
     "מוכנה להוספה" ("ready to be added") matches **none** of these completion verbs, and
     `_all_failed([])` returns `False` on an empty list regardless — this gate cannot fire on a
     zero-tool-call turn even in principle.
   - `_NO_TOOL_CLAIMS` loop (`core/anti_hallucination.py:647`) — targets a different claim shape
     (live external-system checks), not pending-approval framing.
   - Generic structural safety net (`core/anti_hallucination.py:662`,
     `_AGENT_ACTION_STATUS_PATTERN`) — same completion-verb list as above, same non-match.
   - `_NEGATIVE_NO_TOOL_CLAIMS` — targets fabricated failure claims, not this shape.
   - **Nothing else exists in the function body past this point that could apply.**
5. `final_reply` reaches the user unmodified: **"✅ המשימה מוכנה להוספה... שלח מאשר"**.
6. User replies "מאשר". Router-level `_pending_approvals` (empty — nothing was ever queued there),
   `ActionGateway.find_live_contracts()` (empty — no contract exists) — every check correctly finds
   nothing pending. The system truthfully answers "אין פעולה שממתינה לאישור" — **the one part of this
   incident that is working exactly as designed**; the bug is entirely upstream, in step 5.

**Reproduction verdict: confirmed, exhaustively traced, not inferred.** This is a real, currently
open gap in the default configuration (`FEATURE_ACTION_GATEWAY` off).

## 2.2 All places agent text reaches the user directly

Per §1.1's table: Telegram text and WhatsApp text (Twilio + Meta), all sharing `run_agent()` →
`sanitize_agent_response()` → the three `bot.send_message()`/TwiML/JSON-stub call sites listed in
§1.1. No other channel lets LLM-generated text reach a user without going through a template or
structured payload first.

## 2.3 Can the agent phrase these claims without a canonical record?

Yes, demonstrated in §2.1 for "מוכן/ה להוספה... שלח מאשר". By the same gate-by-gate trace, the same
is true for "ממתין/ה לאישור" and "הפעולה הוכנה" whenever `FEATURE_ACTION_GATEWAY` is off (the
default) — none of them are completion verbs, so `_POSITIVE_CLAIMS`/`_AGENT_ACTION_STATUS_PATTERN`
never engage regardless of flag state. Only `_AGENT_PENDING_STATUS_PATTERN` targets this wording
shape at all, and it is flag-gated, and — per this session's prior research
(`CASE_C_CLARIFICATION_CONTINUITY.md`, "Known measurement gap") — even when the flag is on, it only
matches singular Hebrew grammatical forms, not the plural forms a multi-item claim like "כל 5
המשימות מוכנות" would naturally use.

## 2.4 Why regex/pattern-list/`validate_agent_output()`-by-wording cannot be the primary enforcement mechanism

Four independent, each-individually-sufficient reasons, all evidenced in this program's own history,
not theoretical:

1. **Grammatical incompleteness is provable, not hypothetical.** Found empirically while *testing*
   this exact program's own C2 detector (`CASE_C_CLARIFICATION_CONTINUITY.md`): the existing pattern
   fails on plural forms of the exact scenario it exists to catch. A pattern list's coverage is
   bounded by what its author enumerated; natural language is not enumerable this way.
2. **Vocabulary gaps compound over time, silently.** §1.4/§2.1 found a *second*, independent gap
   (cancellation vocabulary, entirely absent) in the same file the pending-approval pattern lives in.
   Two gaps found in one research pass, in a file that has already been patched three times
   (PR #341/#343/#345) by engineers specifically focused on this problem, is strong evidence the
   category itself — not any one instance of it — is what keeps generating new gaps.
3. **Enforcement scope has already drifted from detection scope once.** The Single-Speaker gate is
   presence-based ("was *any* approval queued this turn"), not scope-accurate ("does the claimed
   count/identity match what was queued") — documented in `TURN_OWNERSHIP_EXTENSION.md`. A regex can
   tell you text matches a shape; it cannot by itself verify the text's *claim* against real state
   without a second, non-textual verification step — at which point the "primary" mechanism is
   actually that second step, not the regex.
4. **A flag boundary silently disables the one check that exists.** `_gateway_active` gates the only
   pattern that targets this wording shape at all (§2.1 step 4). Any enforcement design whose
   activation depends on an unrelated feature flag's state is not a enforcement mechanism the system
   can rely on — it is a mechanism that happens to also be a feature-flag side effect.

None of this argues patterns are useless — `_AGENT_PENDING_STATUS_PATTERN` is exactly right as
`OwnershipSignal`'s **detection** input (§1.4's coverage assessment), and remains valuable for
`Commitment Grounding`'s own log-only Phase 0/1 measurement per the original TurnCoordinator
proposal. It argues specifically against making it the mechanism that **decides what the user is
allowed to see** — that decision needs a check against real state (does a contract exist?), which by
definition cannot be text-pattern-based, because the failure mode is text with **no** real state
behind it at all.

## 2.5 Approval Authority Invariant (formal statement, Part 2 scope)

> The agent may propose an action. It is not authorized to declare that an action is pending
> approval. A real Approval Prompt may only be emitted by the system layer that holds a canonical,
> durable `ActionContract`/`Approval` record — never by agent-generated text alone, regardless of
> flag state, channel, or wording.

This is the same invariant already named in the TurnCoordinator proposal's Commitment Grounding
section ("Agent may propose. Agent may NOT self-certify.") — this research narrows it to the specific
sub-claim ("pending approval" framing) that §2.1-2.4 prove is currently unenforced, and makes the
"regardless of flag state" qualifier explicit, since §2.1/§2.3 show the flag dependency is itself
part of the current gap, not a mitigation of it.

## 2.6 Alternatives comparison

| # | Alternative | Mechanism | Pros | Cons | Fits Approval Authority Invariant? |
|---|---|---|---|---|---|
| 1 | **Gateway-only Approval Prompt emission** | Agent text is never sent as-is when it contains approval framing; the actual "⏳ ממתין לאישור" message is *always* composed by `ActionGateway`/`compose_status_reply()`-style canonical text, keyed to a real contract | Directly enforces the invariant; reuses the already-working, already-tested `compose_status_reply()` pattern from the callback path (§1.1) | Requires a structural point that intercepts agent text *before* send, not after (current `sanitize_agent_response()` is post-hoc only); needs to handle "agent proposed nothing, but should have" (§2.6 alternative 5) |
| 2 | **Agent returns a structured `ProposedAction`, Gateway materializes the contract** | Tool-use-shaped, not free text — the agent emits a typed proposal object (even for cases that today go through prose), Gateway turns it into a real `ActionContract` before any approval-shaped text is generated | Closest fit to how tool calls already work (§1.2 shows tool_use is the only channel with real authority); makes "propose vs. claim pending" a type distinction, not a wording distinction | Requires new tool-schema surface for "propose a task" as its own action, separate from the existing `airtable_add` (which already requires approval) — design work, not just a gate; agent must be prompted/trained to prefer it over prose, which is a UX-adjacent decision |
| 3 | **`MessageKind.APPROVAL_PROMPT` + structural gate before send** | Every outbound message is tagged with a `MessageKind` (per the original TurnCoordinator proposal, Phase 4); a structural gate refuses to send anything tagged/shaped as `APPROVAL_PROMPT` unless a `contract_id` accompanies it | Reuses the proposal's own already-designed `MessageKind` taxonomy — no new concept; the gate is a single checkpoint, easy to reason about and test | `MessageKind` tagging is currently unbuilt (Phase 4, not started) — this alternative is not available until that phase lands; still needs *something* to decide the tag (back to needing gate 1 or 2's logic underneath) |
| 4 | **Separate `agent_text` from `system_messages` as distinct types** | Two disjoint message classes at the type level; `system_messages` (which includes real approval prompts) can only be constructed by system code, never assigned from `agent_text` | Strong compile-time-adjacent guarantee if the type boundary is enforced in code (e.g. distinct dataclasses, no implicit string coercion) | Large refactor surface — every current `str`-typed reply becomes two types; retrofitting 5 channels' worth of send call sites; highest implementation cost of the six |
| 5 | **Deterministic fallback when the agent proposes an action but no contract was created** | After the agent's turn, if `OwnershipSignal.is_hijack`-shaped state is detected (claimed + no tool_use + nothing queued), the reply is replaced with a deterministic fallback ("אני יכול להכין את זה — לחץ כאן/כתוב שוב כדי שאכין הצעה אמיתית"), not sent as-is | Directly closes the reproduced incident with the least new architecture — reuses exactly what `OwnershipSignal` already computes; symmetrical with the existing Single-Speaker fallback pattern | Reactive, not preventive — still requires the detection step (§2.4's limits apply to *detection accuracy*, even though this alternative doesn't rely on detection for *enforcement decisions* about real contracts, only for *this one* fallback trigger); best paired with 1 or 3, not a full replacement for either |
| 6 | **Block all agent replies after a tool/approval handoff** | Once a turn has queued a real approval or executed a tool this turn, no further agent text is sent at all for the rest of that turn | Already effectively true today for the C54/Single-Speaker same-turn case (§1.3a) — this generalizes an existing, working pattern | Does not address Case C / Phantom Approval Prompt at all — that scenario has *zero* tool calls, so there is no "handoff" to block after; solves a different problem (§1.3a/b) than the one this Part is about |

**Recommendation:** Alternative 1 (Gateway-only Approval Prompt emission) as the structural
enforcement mechanism, with Alternative 5 (deterministic fallback) as its companion for the specific
"agent proposed something, nothing got created" failure shape, and Alternative 2 as the longer-term
direction once new tool-schema surface is worth building. Alternative 3 is the right *eventual* home
for this once `MessageKind` (Phase 4) exists, but is not available now. Alternative 4 is the strongest
guarantee but the largest cost — worth reconsidering only if 1+5 prove insufficient in practice.
Alternative 6 is already substantially in place for its own (different) problem and does not
substitute for the others here.

## 2.7 Required source of truth

**Recommendation: `ActionContract` id as the sole source of truth, `queue_id`/Approval record as
projections of it — not a three-way combination.** Rationale, grounded in this program's own prior
finding (Persistence section, `TURN_COORDINATOR_PROPOSAL_V2.md`): `ActionContracts` (Postgres, when
persistence is enabled) is already established as the canonical store; `PendingQueueAwareness`
objects and Airtable `Approvals` rows are explicitly documented elsewhere in this program as
*projections* of that canonical store, never independent authorities (`TURN_COORDINATOR_PROPOSAL_V2.md`
Persistence section; `CURRENT_STATE_MAP.md`'s AP-26 row: "legacy row missing action_contract_id ...
execution refused"). Introducing a *fourth* notion of "the real source" for this specific invariant
would repeat exactly the fragmentation this whole program exists to undo. The Approval Prompt gate
(§2.6 alternative 1/3) should therefore check "does a live `ActionContract` exist for this claim,"
not "does *a* queue entry of any kind exist" — those are not always the same thing (§1.3, `queue_id`
constructs in Phase 0's own `PendingQueueAwareness` are explicitly log-only projections, not
authorities, per `core/turn_envelope.py`'s own module docstring).

## 2.8 DoD and regression plan

**Reproduction (must pass before any enforcement work is considered ready):**
- [ ] The exact "פר 349" transcript (§2.1) reproduces the phantom prompt with `FEATURE_ACTION_GATEWAY`
  off (current default) — confirms baseline before any fix.
- [ ] Same transcript, `FEATURE_ACTION_GATEWAY` on — confirms whether the gated Single-Speaker path
  independently already narrows this (it does not, per §2.1's trace being flag-independent for this
  specific wording — `_gateway_active` only suppresses/replaces *after* the pattern matches, and
  the pattern's own coverage gaps in §2.3 apply regardless of the flag).

**At least 10 distinct fabricated-approval phrasings, not relying on the words themselves:**
The DoD explicitly requires the test *not* be pattern-matching on wording — meaning the ten
phrasings below are the **input corpus**, and the assertion under test must be "no `ActionContract`
exists yet the reply implies one does" (a state check), never "does the reply contain string X."
Suggested corpus, deliberately spanning singular/plural, direct/indirect, explicit/implicit framing
(several chosen specifically because they do **not** match today's `_AGENT_PENDING_STATUS_PATTERN`,
proving the state-based check catches what the pattern-based one already misses):
1. "✅ המשימה מוכנה להוספה... שלח מאשר" (the reproduced case)
2. "המשימה מוכנה, רק תאשר ואני אוסיף אותה"
3. "כל 5 המשימות מוכנות — ממתינות לאישורך" (plural — known pattern miss)
4. "אני אוסיף את זה ברגע שתאשר"
5. "בסדר, זה יתווסף לרשימה לאחר אישור"
6. "רשמתי את זה בטיוטה, מחכה לאישור שלך" ("רשמתי" is a *past-tense* verb the completion pattern
   would flag as a *different* false-positive category — deliberately included to prove the two
   failure modes are distinct)
7. "המשימה מוכנה" (bare, no explicit "מאשר"/"אישור" at all — should still be caught by a state
   check, would not be caught by any wording pattern targeting "אישור")
8. "הכל מסודר, רק צריך את האישור שלך"
9. "פר 349 מוכן להיכנס למערכת ברגע שתאשר"
10. "✅ נרשם בטיוטה — ממתין לך" ("נרשם" is itself in the completion-verb list, so this phrasing
    should ALSO trip `_AGENT_ACTION_STATUS_PATTERN` today even without the fix — included as a
    control case to confirm the existing gate still fires where it always could)
11. "בטח, אני דואג לזה — תאשר כשנוח" (fully implicit, no canonical approval vocabulary at all)

**Regression must-pass:**
- [ ] A **real** approval flow (tool_use emitted, `_queue_approval()` succeeds, `ActionContract`
  created) continues to produce its existing "⏳ הפעולה ממתינה לאישור" message unchanged.
- [ ] A pending action already queued from a **prior** turn continues to resolve correctly on "מאשר"
  (no interference with `route_confirmation_word()`/`find_live_contracts()`).
- [ ] No Telegram/WhatsApp behavioral change beyond what the chosen enforcement alternative
  explicitly requires — e.g. Alternative 5's fallback text is a **new** string, which is itself a
  UX change and should be called out as such, not slipped in as "no behavior change."
- [ ] `test_turn_envelope.py`'s existing 74 assertions and `test_pending_contract_read_amplification.py`'s
  6 assertions remain green — this work must not regress the read-amplification fix or the existing
  Case C1/C2 signal behavior.

---

# Migration order (applies to both Part 1 and Part 2 recommendations)

Reusing the TurnCoordinator proposal's own established phasing, not inventing a parallel one:

1. **Observation** — *already substantially done* as of `6d7875b`: `OwnershipSignal` logs the
   Phantom Approval Prompt shape (Part 2) on every agent-handled turn. **New observation still
   needed, not yet built:** a cancellation-vocabulary signal (§1.4 item 2) and a concurrency-race
   signal (§1.3c — likely requires a lightweight "reply sent" marker with a timestamp, checked for
   overlap after the fact, since preventing the race structurally is Phase 3's job, not Phase 0's).
2. **Shadow validation** — run the chosen enforcement gate (§2.6 alternative 1 or 3, or Part 1's
   alternative A) in log-only "would have blocked" mode against live traffic, measuring both false
   positives (real approvals wrongly flagged) and false negatives (phantom prompts still slipping
   through) before trusting it to act.
3. **Structural enforcement** — activate the gate for real: Gateway-only Approval Prompt emission
   (Part 2) and/or the formal `reply_owner` claim (Part 1), per whichever alternative the owner
   selects.
4. **Fallback** — the deterministic fallback text (§2.6 alternative 5) for the specific "agent
   proposed, nothing materialized" case, so blocking a phantom prompt doesn't leave the user with
   silence instead of a truthful, useful response.
5. **Rollout** — flag-gated activation, default off, following this program's own established
   rollout discipline (`rollout/CUTOVER_PLAN.md`/`ROLLBACK_PLAN.md` pattern) — not covered further
   here, as no implementation has started.

---

# Summary

**Already covered by `6d7875b`:** the Phantom Approval Prompt *detection* shape specifically
(`OwnershipSignal.is_hijack` = claimed-pending + no tool_use + nothing queued), logged routinely, not
just on anomaly.

**Still observability only:** everything in this document, without exception. No enforcement, no
blocking, no reply modification exists anywhere in this program as of `6d7875b`. Specifically still
open and unobserved: cancellation/completion fabrication (§1.4 item 2), the cross-request concurrency
race (§1.3c), and TMA/scheduler reply-competition (correctly out of scope, per §1.4 item 4, not a gap
to close).

**Recommended enforcement mechanism:** for Part 2 (Phantom Approval Prompt), Gateway-only Approval
Prompt emission (§2.6 alternative 1) backed by an `ActionContract`-id state check (§2.7), with a
deterministic fallback (alternative 5) for the no-contract case. For Part 1 (general ownership),
a formal pre-composition `reply_owner` claim (§1.5 alternative A) — the TurnCoordinator proposal's
already-speced Phase 3, not a new design. Pattern/regex-based `validate_agent_output()` remains
valuable as the **detection input** to both, never as the **enforcement decision** itself (§2.4).

**Decisions requiring owner approval before implementation starts:**
- The Case C / Case D naming resolution (flagged at the top of this document).
- Which of the six Part 2 alternatives (or combination) to build, and in what order relative to
  Part 1's `reply_owner` claim (they are complementary, not sequential-dependent, but touch
  overlapping code).
- Whether the deterministic fallback text (§2.6 alternative 5, §2.8) counts as an acceptable
  "necessary" UX change, or requires separate sign-off as new user-facing copy.
- Whether the concurrency race (§1.3c) is worth a dedicated mutex (Part 1 alternative B) as an
  interim measure before the full `reply_owner` claim (alternative A) is built, given it is
  currently completely unmitigated.

**PASS / RESEARCH_GAP: RESEARCH_GAP.** Two items in this document could not be fully closed by
static research alone and need either a decision or a live check this sandbox cannot perform:
(1) whether the production deployment actually runs multi-worker/multi-instance (§1.3c's race
requires this to be exploitable in practice — `TURN_COORDINATOR_PROPOSAL_V2.md`'s own Persistence
section states BOSS was verified single-instance as of that document's writing, which would make
§1.3c a same-process, same-thread-only concern instead of a true cross-request race; this needs
re-verification against current Render config, not assumed from a prior document); (2) whether
`FEATURE_ACTION_GATEWAY`'s *actual* production value differs from its documented source-default
(off) — several of this document's findings are conditioned on that flag's state, and per this
program's own repeated documentation-drift findings, source-code defaults have previously disagreed
with live Render values.
