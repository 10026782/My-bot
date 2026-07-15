# Phase 4C — Turn-Ownership Extension to the Current-State Map

Program: F52 — Unified Approval Runtime Migration and Implementation
Consumed by: `docs/architecture/turn-coordinator/TURN_COORDINATOR_PROPOSAL_V2.md`, Phase 0
Document role: Extends `CURRENT_STATE_MAP.md`'s AP-01..AP-50 inventory with turn-ownership
and agent-dependency dimensions. It does not re-derive entry points, does not repeat their
file:line evidence, and is not a new full-system audit — per the proposal's own instruction:
*"Phase 0 does not start a new full-system audit. It consumes and refreshes the existing
F52 / Phase 4C audit maps, adding only the missing turn-level dimensions."*

Status: Research input to Phase 0. Not implementation. No code changed by this document.

**Revision note (this pass):** refreshed against `main` `ac8355b` (2026-07-15, through PR #345)
per explicit instruction, narrow scope: revalidate cited line numbers, re-assess Case A against
`BUG-BATCH-DISCARD`, keep the callback context-interrupted finding open, make an explicit call on
`_pending_voice_edits`' temporary classification, and soften the AP-25 reuse suggestion into an
explicit separate-decision requirement. No other section was re-audited in this pass.

## Baseline staleness this extension corrects for

`CURRENT_STATE_MAP.md`'s baseline is `4d3787e6e6fcbc93bd5a30f62f0834136b706f06` (2026-07-14).
Current `main` at the time of this revision is `ac8355b` (2026-07-15, through PR #345),
27 commits later. Five of those 27 are not documentation or rollout tooling — they are
behavioral changes to exactly the rows this extension depends on (AP-01, AP-02, AP-04, AP-09,
AP-10, AP-12):

- `e26df5a` **Fix Single-Speaker contradictory fallback and duplicated success text** — added a
  suppression sentinel (`__approval_queued__`) to `sanitize_agent_response()` so the agent's
  fallback text no longer overwrites an already-sent pending-approval message, and made
  `ActionGateway._execute_contract()` return only `compose_status_reply()`'s text instead of
  appending the executor's own message a second time.
- `5a06596` **Fix multi-turn Single-Speaker pending-approval narration** (PR #341 follow-up) —
  extended the same suppression gate to catch "ready and waiting for approval" narration, not
  only completion-verb narration.
- `d541175` / `bb8312a` **canonical tool resolution wired into `propose_action()` and
  `_queue_approval()`** — a tool-name hint from free text (for example a task-like request that
  could resolve to `sheets_append`) is now canonicalized before a contract/button is built, so
  the durable contract and the legacy `event_bus` button no longer disagree on which tool will
  run.
- `15b8567` **Fix BUG-BATCH-DISCARD: restore multi-task batch preservation** (PR #345) — replaced
  the hard per-turn `_mutating_approvals_this_turn >= 1` discard with `event_bus.BatchQueueStore`
  (`event_bus.py:200-235`): every mutating tool call in a turn is now durably preserved (in-memory,
  same volatility class as `PendingActionsStore`), the first still queues immediately, the rest
  are held per `canonical_user_id` and promoted one at a time — via `app._promote_next_batch_item()`
  (`app.py:866`) — only once no contract is currently live for that identity. Promotion is wired
  as a side effect through a new `_gateway_reply_with_promotion()` wrapper (`app.py:905`) at every
  ActionGateway resolution call site: override word, combined word, disambiguation, cancellation,
  and the Telegram callback (`app.py:1393`, `1423`). See findings 1a/1b below — this fixes
  a *sibling* mechanism to the one the original Case A dialogue describes, not Case A's own path.

None of these five commits are reflected in `CURRENT_STATE_MAP.md`'s prose for
AP-01/02/04/09/10/12, and `AI_CONTEXT.md` (checked separately) was three commits stale relative
to `main` as of the prior pass and has not been re-checked in this one. Per `AGENTS.md`'s
post-merge verification protocol, this extension treats `main` as authoritative and flags the gap
rather than silently working around it.

**Direct consequence for TurnCoordinator:** the "documented incident" the proposal cites as
urgency for Phase 3 Reply Ownership (*"approval prompt מול fallback סותר, הודעת הצלחה כפולה"*)
is the same incident `e26df5a`/`5a06596` already patched — but patched with a **text-pattern
suppression gate keyed off regex matching + a sentinel string**, not a structural single
`reply_owner` that decides *before* text is generated. The proposal's Phase 3 is not redundant
with this fix; it is the generalization of it. Gate C's DoD item *"Reply Ownership (Phase 3) is
documented with reference to the real incident... not a theoretical protection"* should name
`e26df5a`/`5a06596`/`test_single_speaker_fallback_and_duplication.py` explicitly as the
regression baseline Phase 3 must not weaken, since that suite currently encodes the *stopgap*
behavior (pattern-based suppression) that a real `reply_owner` gate should eventually make
unnecessary — not just coexist with.

The `bb8312a` commit message itself documented three items explicitly deferred as "out of scope."
Two of those three are now resolved by `15b8567`/PR #345: only one mutating approval queued per
agent turn with the rest silently discarded, and no durable queue behind the agent's promise to
continue a batch — both fixed by `BatchQueueStore` (see findings 1a/1b below). The third
remains fully open and was independently re-verified for this revision, not just re-cited:
`_apply_ingress_context_gate()` (`app.py:2742`) marks `context_interrupted` on every inbound
**callback** event including the approve/reject button press itself, because the exemption
(`event.kind == "text"` at `app.py:2755`) never covers `kind == "callback"`. `15b8567` did not
touch this. Re-reading the callback call site directly (`app.py:2813-2819`) confirms this is not
an oversight but an explicit, documented design choice as of today: *"Every callback (including
approve:/reject:, which belongs to app.py's own separate `_pending_approvals` mechanism, not
ActionGateway) is 'not an ActionGateway resolution' — always interrupts."* That comment is honest
about the tradeoff but does not resolve it — a button press on one pending contract still marks a
different, unrelated still-pending contract as context-interrupted (see AP-02/AP-08, and finding 2
below).

## Dimensions added (per the proposal's `TurnEnvelope`/`CapabilityAction`/`MessageKind`)

| Dimension | Definition | Source concept in the proposal |
|---|---|---|
| `reply_owner_today` | Which component's text actually reaches the user for this entry point **today**, before any `reply_owner` field exists | `TurnEnvelope.reply_owner` (Phase 3) |
| `outbound_sender` | The mechanical send call/adapter (Telegram send, callback edit, TwiML, TMA JSON) | distinguishes transport from authorship |
| `message_kind_today` | Best-fit `MessageKind` value for what this entry point sends, or "untyped" if no such distinction exists in code today | `MessageKind` enum |
| `expects_next_user_reply` | Y/N — does this outbound message put the conversation into a state where the next inbound message must be interpreted against it | `PendingQueueAwareness` existence |
| `pending_queue_source` | Which store actually holds the wait state: `AC` (ActionContract), `PG` (Postgres claim), `EB` (EventBus RAM), session/preview RAM, or a bespoke RAM dict | `PendingQueueAwareness.source` |
| `agent_interpreted` | Y/N — does resolving *this specific step* require live free-text LLM interpretation (`ExecutionKind.AGENT_INTERPRETED`), as opposed to a deterministic parser/handler | `ExecutionKind` |
| `deterministic_without_agent` | Y/N — would this step still work correctly if `AgentAvailability == AGENTLESS` today (not "could it in principle," but "does the current wiring allow it") | `available_in_agentless_mode` |

Legend: `Y`/`N` = verified from source read for this extension or directly implied by
`CURRENT_STATE_MAP.md`'s own text; `Y*`/`N*` = inferred by domain reasoning, not independently
re-verified against source for this pass — treat as a Phase 0 call-site item to confirm, not a
closed fact. `—` = not applicable (no conversational turn exists at this entry point).

## Extended matrix

| ID | reply_owner_today | outbound_sender | message_kind_today | expects_next_user_reply | pending_queue_source | agent_interpreted | deterministic_without_agent |
|---|---|---|---|---|---|---|---|
| AP-01 | Agent pipeline (`sanitize_agent_response`) | Telegram/Twilio send in `run_agent()` caller | untyped (APPROVAL_PROMPT shape) | Y | EB (+AC if persistence on) | Y | N |
| AP-02 | **Gateway** (`compose_status_reply`), not agent — see staleness note above | Telegram callback message edit, bypasses `sanitize_agent_response` | untyped (no ACTION_RESULT kind exists) | N | EB→AC/PG | N | Y |
| AP-03 | callback handler directly | Telegram callback edit | untyped | N | EB popped; AC left stale (P1-1) | N | Y |
| AP-04 | mixed: ActionGateway parser resolves, but reply still flows through agent's `sanitize_agent_response` pipeline in the same turn | `run_agent()` caller send | untyped, hybrid approval/completion | N normally, Y if reconfirmation fires | AC | N* for the parse itself | Y in principle, **N in current wiring** — only reachable inside `run_agent()`, not before it (see §Routing-order gap) |
| AP-05 | ActionGateway parser via agent pipeline | same as AP-04 | untyped | N usually | AC | N | Y in principle / N in wiring |
| AP-06 | ActionGateway parser via agent pipeline | same as AP-04 | untyped (this *is* the "מספר N" resolver Case A needs unified) | Y (awaits the numbered pick) | AC + RAM disambiguation ordering | N | Y in principle / N in wiring |
| AP-07 | ActionGateway parser via agent pipeline | same as AP-04 | untyped | N | AC | N | Y in principle / N in wiring |
| AP-08 | ActionGateway context-integrity logic via agent pipeline | same as AP-04 | untyped, conceptually CLARIFICATION_REQUEST | Y | AC + RAM reconfirm state | N | Y in principle / N in wiring; **also hit by the callback-context-interrupted gap** (see staleness note) |
| AP-09 | router / `run_agent()` re-run of original text | `run_agent()` caller send | untyped; doc's own mismatch #4 notes this conflates "plan confirmation" with "tool authorization" | Y | RAM `_pending_approvals` dict, 10m | Y (original free text needed agent interpretation) | N |
| AP-10 | agent pipeline or Gateway depending on branch | `run_agent()` caller send | untyped (APPROVAL_PROMPT shape) | Y | AC | Y (agent proposed it) | N* (confirmation step may be deterministic once AC exists; proposal step is not) |
| AP-11 | — (no conversational turn; internal auto-write) | none directly (feeds AP-12 preview later) | — | N | AC created but ignored by write step (P0-3) | N | Y — and that is *why* the bypass is dangerous: nothing is asking first |
| AP-12 | session/preview handler, `resolve_pending_lead_preview()` (`core/lead_candidate_handler.py:1228`) | `run_agent()` caller send (batch summary) | untyped (APPROVAL_PROMPT shape for the batch; **no kind at all for "שמור 3"**) | Y | `session_store.lead_sessions` preview RAM — a queue source not covered by AC/EB/AP, and **not touched by `BatchQueueStore`** (Tier 2, separate from Tier 1's tool-loop batch mechanism — see findings 1a/1b) | Y today (this is Case A's literal failure) | N today; **should become Y once Phase 2 ships** `resolve_numbered_reference()` |
| AP-13..AP-15, AP-17, AP-19, AP-21 (TMA approval routes) | TMA endpoint (HTTP JSON) | HTTP response | untyped (APPROVAL_PROMPT/completion shape) | N — TMA is request/response, not a standing conversational turn; `TurnEnvelope`/`MessageKind` apply weakly here except where the same action also produces a Telegram/EB notification | AC + AP projection | N (typed REST call, no LLM) | Y |
| AP-16, AP-18, AP-20 (TMA owner-direct branches) | TMA endpoint | HTTP response | — (no pending message at all) | N | none | N | Y |
| AP-22 (read-only approvals list) | TMA endpoint | HTTP response | — | N | reads AP, creates none | N | Y |
| AP-23, AP-24 (TMA approve/reject route) | TMA endpoint | HTTP response | untyped | N | AC + AP | N | Y |
| AP-25 (TMA bulk approvals) | TMA endpoint, aggregates per-item outcomes | HTTP response (typed per-item result list) | untyped | N | AC + AP | N | Y — **a reusable reference pattern for typed per-item batch outcomes (see finding 5); not to be adopted into the agent/Telegram flow without a separate decision** |
| AP-26 (legacy Approvals row) | TMA endpoint | HTTP response | conceptually CAPABILITY_BOUNDARY ("this can no longer execute") | N | AP only, no AC | N | Y |
| AP-27 (`followup_engine.scan_and_propose`) | scheduler job → Telegram EB buttons | Telegram send (proactive, not a reply to any inbound turn) | conceptually SYSTEM_NOTIFICATION carrying an embedded APPROVAL_PROMPT — today untagged, so a user scrolling back cannot tell this from an ordinary agent reply | Y | AC + EB | N for the proposal; **Y for whatever reply the owner sends back**, since free text not matching a button goes through `run_agent()` | Y for the proposal itself |
| AP-28 (`lead_recovery.scan_and_propose`) | same pattern as AP-27 | Telegram send | same as AP-27 | Y | AC + EB | same split as AP-27 | Y for the proposal |
| AP-29 (voice approval request) | Telegram callback (same shape as AP-02) | Telegram callback edit | untyped notification+prompt hybrid | Y | AC + EB | N | Y |
| AP-30 (`voice_edit:` then next text) | media handler callback, then **a separate ad-hoc "next raw text" capture that is not `run_agent()` and not a registered pending source** | Telegram send from media handler | untyped | Y — waits for the edited transcript text | `_pending_voice_edits` RAM dict (`media_handler.py:202`) — **temporarily classified under `source="file_flow"` for Phase 0 purposes, see finding 4** | N (raw text goes straight to save, bypassing the agent entirely — if the user says something unrelated instead of the edit, there is no `TurnEnvelope`-style awareness to catch that) | Y |
| AP-31, AP-32 (file upload) | channel handler / TMA endpoint | channel response / HTTP response | untyped completion/error | N | idempotency store only, not conversational | N | Y |
| AP-33 (WhatsApp Twilio text → `run_agent()`) | same as AP-01/04 | **TwiML response — a distinct `outbound_sender` from Telegram even though the reply logic is shared** | same as AP-01 | Y | same as AP-01 | Y | N |
| AP-34 (WhatsApp media) | same pattern as AP-29/31 | Telegram owner buttons / TwiML | same | Y | AC+EB / idem | N | Y |
| AP-35 (Meta WhatsApp text, stub outbound) | — (agent may run, but "no reply delivery" per original doc) | none — JSON stub only | — | N (cannot expect a reply through a channel with no outbound) | n/a | Y if flag on | N — but **AGENTLESS is moot here regardless**, since outbound doesn't exist independent of agent availability |
| AP-36 (Meta WhatsApp media pre-flag) | media handler | log/JSON only | — | N | idem only | N | Y |
| AP-37, AP-38 (email/bounce — dead adapters) | — (nothing ever consumes the EB item) | Telegram approval-like UI is presented, but never resolved by any subscriber | untyped, but **should arguably be SYSTEM_ERROR-in-waiting**: an APPROVAL_PROMPT-shaped message exists with no `reply_owner` ever able to close it | Y superficially (invites a reply), N functionally (nothing consumes it) — **this mismatch is itself a finding** | EB, orphaned | N | Y (feature-flagged off) |
| AP-39 (abandoned-lead task creation) | — (background write) | none conversational | — | N | none | N | Y |
| AP-40 (interaction log persistence) | — (background write); later surfaces via Telegram summary | Telegram send (delayed, separate turn) | that later summary is conceptually SYSTEM_NOTIFICATION, untyped today | N | none for the write itself | N | Y |
| AP-41 (`create_tasks_from_analysis`) | — (background); surfaces via same Telegram summary as AP-40 | Telegram send (delayed) | — for the write; SYSTEM_NOTIFICATION for the later summary | N | none | **Y** — this is a background LLM call, not the live conversational agent, but is still `ExecutionKind.AGENT_INTERPRETED` in the proposal's sense; the proposal does not currently distinguish "live per-turn agent" from "background batch LLM call" as two different `AGENT_INTERPRETED` sub-cases, and probably should before Phase 1 | N |
| AP-42 (lead-memory flush) | — (silent persistence, log only) | none | — | N | none | N | Y |
| AP-43 (weekly quest reset) | — for the write; scheduler for the notification | Telegram send (delayed) | resulting notification is conceptually SYSTEM_NOTIFICATION, untyped today | N | none | N | Y |
| AP-44..AP-47 (TMA asset/venture/game routes) | TMA endpoint | HTTP response | — | N | none | N | Y |
| AP-48 (`/done` lead conversion) | command handler | Telegram send | untyped completion notice | N | none | N (slash command, no LLM) | Y |
| AP-49 (`/update`, `cmd_decision`) | command handler | Telegram send | untyped completion notice | N | none | N for the trigger; content may later be read by the live agent as injected context | Y |
| AP-50 (ingress/attribution/session/funnel capture) | **varies by sub-flow — this row is itself a merge of several distinct call sites and does not reduce to one answer** | varies | varies | varies | varies (session/idempotency, feature-specific) | **mixed**: `furniture_lead_funnel.py` is an explicit deterministic FSM (N); general `lead_qualifier.py` scoring/qualification questions use the LLM (Y) | mixed accordingly — **flag as a place Phase 0's call-site granularity must go finer than AP-50's** |

## New findings this pass surfaces (feed into Phase 0's exact call-site list)

1a. **RESOLVED by PR #345 — Tier 1 (agent tool-loop) batch discard.** The former
   `_mutating_approvals_this_turn >= 1` hard block (silent discard, generic warning only in the
   *tool_result* channel) is now `BatchQueueStore`: every mutating tool call this turn is durably
   preserved and promoted one at a time as the previous one resolves. Verified directly against
   `app.py:2145-2197` and `event_bus.py:200-235` for this revision, plus
   `test_bug_batch_approval_preserved.py` (33 assertions, cited in `15b8567`). This closes the
   *data-loss* half of the original finding 1. It does **not** implement `PendingQueueAwareness` or
   `resolve_numbered_reference()` — items are still promoted and approved sequentially, one live
   contract at a time, never presented as a numbered list the user can address by index. Phase 1/2
   remain necessary for that; they are no longer blocked by silent loss underneath them.
1b. **STILL OPEN — Tier 2 (lead batch preview) is a separate mechanism, untouched by PR #345, and
   is what the proposal's Case A dialogue literally describes.** "5 מועמדים ממתינים... שמור 3" is
   `resolve_pending_lead_preview()` (AP-12, `core/lead_candidate_handler.py:1228`), not the
   tool-loop path finding 1a fixes — its own docstring says so explicitly
   (`core/lead_candidate_handler.py:1240-1241`: *"לא נוגע ב-`_pending_approvals` או ActionGateway
   contracts — Tier 1 (`_propose_lead_write`) ממשיך לעבוד בדיוק כפי שהוא, ללא שינוי"*). More
   precisely than the prior pass stated: this is not merely *unresolved by the agent's own
   reasoning* — the handler's docstring states outright, by design, **"אין תמיכה ב-selection חלקי
   ('כן 1') — רק אישור/ביטול מלא לכל ה-batch"** (`core/lead_candidate_handler.py:1242`, "no partial
   selection support — only full confirm/cancel for the entire batch"). Case A's failure is not a
   bug in this function; it is the function's documented scope boundary. `PendingQueueAwareness`
   (Phase 0/1) and `resolve_numbered_reference()` (Phase 2) remain both necessary and, for this
   entry point specifically, not yet started by any merged work.
2. **The callback-context-interrupted gap is real, unaddressed by PR #345, and now explicitly
   confirmed as a known-but-open design choice, not a silent oversight.** `_apply_ingress_context_gate()`
   (`app.py:2742`, exemption check at `app.py:2755`) only exempts `event.kind == "text"` via
   `is_own_resolution_event()`; a `kind == "callback"` event (an approve/reject button press)
   always calls `mark_context_interrupted()` — the callback call site's own comment
   (`app.py:2813-2819`) says this is intentional for now. A button press on one pending contract
   can therefore mark a *different*, unrelated still-pending contract as context-interrupted,
   forcing spurious reconfirmation. This belongs in Gate B's "two queues active simultaneously"
   regression requirement, and in `active_queue_id`'s priority-order test, not only in Case A's fix.
3. **AP-02's reply is Gateway-authored, not agent-authored, and today's fix is a suppression
   patch, not a `reply_owner` field.** The single-speaker regression suite
   (`test_single_speaker_fallback_and_duplication.py`) should be named explicitly in Gate C's DoD
   as the pre-existing behavior Phase 3 generalizes — see the staleness note above.
4. **DECISION for this pass — `_pending_voice_edits` is temporarily classified under
   `source="file_flow"`, not left as an open question.** It is not `AC`, not `EB`, not lead-preview
   session state, and the proposal's `PendingQueueAwareness.source` Literal
   (`action_gateway | lead_capture | file_flow | task_flow | system`) has no exact slot for it.
   Rationale for `file_flow` over a new `voice_edit_flow` value or `system`: it is handled by the
   same `media_handler.py` module as file/media uploads (AP-31/32, already under `file_flow` in
   spirit), and a new Literal value should not be added unilaterally to an externally-authored
   proposal document without the proposal owner's sign-off. This is explicitly a **temporary
   placeholder for Phase 0's call-site inventory**, not a recommendation to leave it unfixed in the
   v3 schema — whoever finalizes the Phase 1 `PendingQueueAwareness` schema should treat this as an
   open item to confirm, not inherit silently.
5. **AP-25 (TMA bulk approvals) is a reusable reference pattern for typed per-item batch outcomes —
   adopting its shape into the agent/Telegram flow is a separate decision, not implied by this
   audit.** It already solves, for its own channel, a version of the problem AP-12 has (an explicit
   typed per-item outcome list instead of a silent drop) and PR #345 also solved differently for
   Tier 1 (sequential promotion rather than a single batch response). Recording it here as prior art
   only; Phase 2's actual batch/queue design should evaluate it against `BatchQueueStore`'s
   sequential-promotion approach on its own merits, not default to either.
6. **Background LLM calls (AP-41, and `lead_qualifier.py` within AP-50) are `AGENT_INTERPRETED` in
   the proposal's `ExecutionKind` sense but are not the live per-turn conversational agent.** The
   proposal's Phase 0 mapping instruction ("map which `CapabilityAction` are `AGENT_INTERPRETED`
   vs `DETERMINISTIC`/`CONVERSATIONAL`") should decide explicitly whether `AgentAvailability ==
   AGENTLESS` is meant to also suspend these background jobs, or only the live conversational
   turn — the proposal's text currently only discusses the live turn.
7. **AP-13..AP-25 (TMA) show that "reply_owner" and "turn" are conversational-channel concepts that
   apply weakly to a stateless REST adapter.** `TurnEnvelope`/`MessageKind` should be scoped
   explicitly to the conversational channels (Telegram, WhatsApp) plus the *notifications* TMA
   actions produce on those channels — not retrofitted onto every TMA HTTP response, which already
   has clean single-response semantics by construction.

## Routing-order gap (§Phase 1 dependency)

The proposal's routing order requires deterministic reply-owner resolution (confirm word,
disambiguation, cancellation, reconfirmation) to happen **before** the agent is invoked at all,
so these paths work under `AGENTLESS`. Today, AP-04 through AP-08's ActionGateway parsers are
only reachable *from inside* `run_agent()` — there is no pre-agent call site that runs them first.
This is not a flaw in the parsers (they are already deterministic, per `deterministic_without_agent`
above); it is a wiring gap that Phase 1 must close as a prerequisite, not something Phase 0 can
just log and defer, since without it "AGENTLESS routes still work for approve/reject/disambiguation"
(Gate B) is not actually achievable — those routes still go through `run_agent()`'s entry point
even though they don't need the LLM once inside it.

**Unchanged by this revision, but now carries an added side effect to preserve:** PR #345 wrapped
every one of these call sites' return value in `_gateway_reply_with_promotion()` (override word,
combined word, disambiguation, cancellation — `app.py`, within the same `run_agent()` conditional
blocks as before) so that resolving one contract also promotes the next `BatchQueueStore` item for
that identity. Whatever Phase 1 wiring moves these parsers to run before the agent must carry this
promotion side effect with them — it is not separable from the parser call itself today.

## Case C read-amplification fix (Phase 0 self-regression, found and fixed)

A production baseline comparison (2026-07-14 vs 2026-07-15) found a plain greeting turn's pending-
ActionContract reads went from 1 to 3: the pre-existing ingress-gate check
(`_apply_ingress_context_gate()` → `ActionGateway.is_own_resolution_event()` →
`find_live_contracts()`) plus Phase 0's own two additions (`_build_and_log_turn_envelope()` at
"1.7" and the Case C2 signal check after `sanitize_agent_response()`) — three independent queries
for one identity's state within a single request, none of them reusing another's result.

Fixed by establishing one per-turn snapshot and threading it through every consumer instead of
re-querying:

- `core/action_gateway.py`'s `is_own_resolution_event()` gained an optional `live` parameter
  (`None` default — fully backward compatible for the direct-call tests in
  `test_pr0_gates_structural.py`).
- `app.py`'s `_apply_ingress_context_gate()` gained an optional `live_contracts` parameter, threaded
  to `is_own_resolution_event()`.
- The three `kind="text"` webhook handlers (Telegram, WhatsApp Twilio, WhatsApp Meta) each fetch
  `find_live_contracts()` exactly once, pass it into `_apply_ingress_context_gate()`, and thread the
  same value into `run_agent()` via a new `_live_contracts_snapshot` parameter.
- `run_agent()` establishes this as the turn's single source at a new "1.65" step (reusing the
  threaded-in value, or fetching once itself as a fallback for callers that don't thread it — e.g.
  recursive `run_agent()` calls) and passes it to `_build_and_log_turn_envelope()`.
- The Case C2 check's post-turn re-read was removed entirely, not just deduplicated: the code path
  that reaches it (past the tool loop, past `sanitize_agent_response()`) is only reachable when
  every confirm/disambiguation/cancellation/override route returned early instead — none of which
  is on this path — so the only way contract/batch-queue state could differ from the turn-start
  snapshot on this path is a `_queue_approval()` call succeeding this same turn, which is exactly
  what `tool_results_log`'s `__approval_queued__` sentinel (already used for `approval_queued_this_turn`)
  detects. The turn-start snapshot is therefore provably still accurate whenever that flag is False,
  making a second query unnecessary rather than merely redundant.
- One exception, deliberately left unfixed: the "2.55" confirm-word section's own
  `find_live_contracts()` check was **not** consolidated — `test_c89_preview_confirmation.py`'s
  `test_app_py_confirm_word_checks_gateway_before_flag_branch` statically asserts this exact call
  appears there, ahead of the `FEATURE_ACTION_GATEWAY` flag branch, as an intentional structural
  invariant. This branch never executes on a greeting turn (the reported regression's scenario) —
  reverted after breaking that test, to keep the fix's blast radius to what the regression actually
  required.

Verified empirically (not just reasoned about): a direct `run_agent()`-level count (mirroring
`test_session_snapshot.py`'s LL-11 pattern) showed 2 internal `find_live_contracts()` calls for a
greeting turn before this fix, 1 when called without a threaded snapshot (fallback) after, and 0
when called with one (the webhook-handler path) — see `test_pending_contract_read_amplification.py`.
Combined with the webhook handler's own single explicit fetch, a full production request goes from
3 reads to 1. `multi_contract_conflict`/Case C1 and Case C2 detection logic and output are
unchanged — same signal, same conditions, only the data source changed from a fresh query to an
already-fetched snapshot proven equivalent for this code path.

## What this extension deliberately does not do

- It does not re-verify AP-13..AP-50's original file:line evidence — that remains
  `CURRENT_STATE_MAP.md`'s responsibility.
- It does not propose code changes. Findings 1a/1b/2-7 and the routing-order gap are Phase 0 inputs.
- Finding 4's `file_flow` classification for `_pending_voice_edits` is a working placeholder for
  Phase 0's inventory, not a closed decision on the proposal's v3 schema — whoever finalizes the
  Phase 1 `PendingQueueAwareness` schema should still confirm or override it explicitly.
