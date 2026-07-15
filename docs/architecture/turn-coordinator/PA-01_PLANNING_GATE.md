# PA-01 Planning Gate — Phantom Approval Prompt Structural Enforcement

Program: TurnCoordinator
Status: **PLANNING ONLY.** No code written, no branch opened, no implementation started.
Baseline: `main` `f2f7093` (2026-07-15).
Scope: **PA-01 only**, per explicit instruction. OH-01 (Reply Ownership claim), OS-01 (false
cancellation/completion), RC-01 (concurrency protection) remain research-only — see
`REPLY_OWNERSHIP_AND_APPROVAL_AUTHORITY_RESEARCH.md` — and are not planned further here. Naming
per owner decision: see that document's top-of-file note and `CASE_C_CLARIFICATION_CONTINUITY.md`'s
matching update.

**Revision note (this pass):** the original §4 used `_ownership_signal.is_hijack` as the primary
enforcement trigger. Correctly rejected: `is_hijack` is derived from `agent_claimed_approval`, a
text-pattern match (`_agent_text_claims_pending()`) — using it as the *decision* mechanism is still
wording-based enforcement, just one layer removed from the obvious version, and would still miss a
new phrasing the pattern doesn't cover. §4 below is rewritten around a **state-only structural
predicate** that never inspects `final_reply`'s text at all. `is_hijack`/`detect_case_c2_signal()`
are retained, demoted to observability/shadow-metrics/defense-in-depth/regression-signal roles only
(§4.1), never the authority that decides whether a reply is replaced.

---

## 1. Production facts — verification status

Two facts were required to be verified before any code is written. Neither can be fully closed from
this sandbox (no Render dashboard/live environment access — the same limitation already disclosed in
the prior research's PASS/RESEARCH_GAP verdict). What follows is the best available evidence for
each, clearly separated from what still needs a live check, plus — critically — why **PA-01
specifically does not need either fact resolved to proceed**, which is what makes it the correct
first item in the approved implementation order.

### 1a. Render instance/worker count

- **Static evidence, current:** `docs/operations/DEPLOYMENT.md:85` — Start Command is `gunicorn app:app`
  with no `--workers`/`-w` flag and no `WEB_CONCURRENCY` reference anywhere in the repo (grepped:
  zero matches). Gunicorn's own documented default is 1 worker when unspecified.
- **Prior live evidence, dated:** `TURN_COORDINATOR_PROPOSAL_V2.md:679` — "נבדק בפועל מול Render
  dashboard — Manual Scaling = 1, Total Instances שטוח על 1 לאורך 48 שעות" (checked directly against
  the Render dashboard at the time that document was written; single-instance confirmed for a 48-hour
  window, not a point-in-time snapshot).
- **Not re-verified now.** Both signals point the same direction (single-instance, single-worker) and
  neither has been contradicted anywhere in this repo's history, but "not contradicted" is not the
  same as "confirmed today." **This still requires a live Render dashboard check before RC-01 planning
  begins** — not before PA-01, see below.

### 1b. `FEATURE_ACTION_GATEWAY` actual production value

Genuinely contested in this repo's own audit trail, not just undocumented — both directions have
direct historical evidence:

- **Documented source default: off.** `feature_flags.py:49`'s own docstring, and
  `docs/operations/DEPLOYMENT.md`'s "מה פועל בפרודקשן" list (updated 16/06/2026) does not include
  `FEATURE_ACTION_GATEWAY` among the flags on by default.
- **Live-observed as active, at least once:** `BUG_AUDIT_LOG.md:1114` — a user directly tested the
  two-step disambiguation protocol live in Telegram production and it worked, which is only possible
  if `FEATURE_ACTION_GATEWAY` was active at that time ("ב-סביבה שנבדקה, `FEATURE_ACTION_GATEWAY`
  בפועל **פעיל**... לא מאומת דרך קוד סטטי... אלא רק דרך תצפית חיה", dated in that log entry's context
  as 05/07/2026).
- **Explicitly marked unverified elsewhere:** `BUG_AUDIT_LOG.md:2179` — a different feature's rollout
  entry states "Verified בפרודקשן: לא — FEATURE_ACTION_GATEWAY כבוי כברירת מחדל", from a different
  point in this program's history.
- **Conclusion:** the flag's value has likely changed over time (consistent with a flag being turned
  on for testing, or varying by rollout stage) and there is no single "the current value is X"
  fact to cite. **This requires a live check of the actual Render environment variables** — not
  resolvable from source, and not attempted to be resolved by assumption here.

### Why PA-01 does not need either fact resolved

PA-01's recommended mechanism (§4) requires **no concurrency primitive** — it is a single-process,
single-request, in-memory decision made once per turn, using state already computed within that same
`run_agent()` call. Instance/worker count only matters for RC-01 (the concurrency race), which the
approved order places explicitly last, gated on this exact verification (constraint 4). PA-01's
design is also explicitly **independent of `FEATURE_ACTION_GATEWAY`** (§4.2) — governed by its own
new flag — specifically *because* §1.3b of the research found that flag's gating to be part of the
existing gap, not a fix for it. Building PA-01 on top of `FEATURE_ACTION_GATEWAY`'s state would
inherit exactly the uncertainty documented above; a dedicated flag sidesteps needing to know 1b at
all for this specific patch.

---

## 2. Exact shared reply-composition point

Single funnel for both Telegram and WhatsApp (Twilio + Meta) text turns — `run_agent()`, `app.py`:

- `app.py:2506-2509` — `final_reply = sanitize_agent_response(final_reply, tool_results_log,
  _gateway_active=_flag_enabled("FEATURE_ACTION_GATEWAY"))`. This is the last point `final_reply`'s
  *content* is decided.
- `app.py:2510-2571` — the existing Phase 0 telemetry (Case C2 detection, `OwnershipSignal`
  construction/logging) already sits immediately after this, and already computes everything PA-01's
  enforcement needs (§4.1).
- `app.py:2574` — `memory.add(ctx.memory_key, "assistant", final_reply)` — **critical ordering
  constraint**: any enforcement replacement of `final_reply` must happen *before* this line, or the
  phantom claim gets written into the agent's own conversation memory and the agent will "remember"
  having said it on a later turn, compounding the problem rather than fixing it. Verified: nothing
  reassigns `final_reply` between line 2506 and `return final_reply` at line 2602 today — confirmed
  by grep, zero other assignments in that span.
- `app.py:2602` — `return final_reply`.

No other assembly point exists — confirmed in the prior research (§1.1) that Telegram, WhatsApp
Twilio, and WhatsApp Meta all call this same `run_agent()` and only differ in how they transmit the
returned string afterward (`bot.send_message()` / TwiML / JSON stub), not in how it's composed.

---

## 3. Where the Gateway creates a real ActionContract + real Approval Prompt

- `core/action_gateway.py:626` — `ActionGateway.propose_action()`, the sole constructor of a real
  `ActionContract`.
- `app.py:730` (def) → `app.py:783`/`app.py:805` (the two `propose_action()` call sites, gateway-flag
  on/shadow branches) → `app.py:821` (`bus.request_approval(...)`, makes it visible/actionable) →
  `app.py:863` — **the real, canonical Approval Prompt text**: `f"⏳ הפעולה ממתינה לאישור: {label}\nשלח
  *מאשר* כדי לאשר (בכל ערוץ)."`, returned by `_queue_approval()` only after a real contract exists.

This confirms the exact shape of the problem PA-01 closes: two structurally different code paths can
each produce approval-prompt-shaped text — one (`app.py:863`) always backed by a real contract, the
other (agent free text reaching `app.py:2506`) never verified against one. PA-01 does not touch or
duplicate the first path at all.

**Where the canonical `ActionContract` id itself lives, precisely:** `GatewayResult.contract_id: str
| None = None` (`core/action_gateway.py:214`), populated by `propose_action()` and already assigned to
the local `_gw_result` inside `_queue_approval()` (`app.py:783`/`805`). **Gap found this pass:**
`_queue_approval()` currently appends only a bare sentinel to `tool_results_log` —
`{"tool": "__approval_queued__", "content": result, "ok": True}` (`app.py:2439-2443`) — the real `contract_id` is computed but never
carried into that record. §4.2 below closes this: the sentinel gains a `contract_id` field, so the
structural predicate can check for an actual id, not just a flag that something happened.

**Where "structured clarification" comes from, precisely:** `Handler.CLARIFY` is assigned entirely
inside `core/router/` (confidence-threshold/ambiguous-phrase classification,
`core/router/intent_router.py:128` `detect_intent()` plus the ambiguous-phrase branch noted at
`core/router/intent_router.py:40`) — **before** `run_agent()`'s tool loop is ever reached. Consumed at
`app.py:2177-2178`: `if route.handler == Handler.CLARIFY: return clarify_response(route)` — an early
return, `clarify_response()` (`app.py:546-548`) is a static template/`route.response_override`, no
`ActionContract`, no agent text at all. **Structural consequence, load-bearing for §4's predicate:**
by the time any turn reaches `app.py:2506` (PA-01's enforcement point), `route.handler` can never be
`CLARIFY` — it already returned. This is not something PA-01 needs to newly check; it is already
guaranteed by existing, unmodified code, and §4 states this explicitly rather than re-implementing it.

**A related, pre-existing mechanism found this pass, explicitly out of PA-01's scope:**
`Handler.APPROVAL` → `approval_response()` (`app.py:626-635`, early return at `app.py:2180-2184`) is
the legacy `_pending_approvals` "plan confirmation" path (AP-09 in `TURN_OWNERSHIP_EXTENSION.md`) —
it also produces approval-prompt-shaped text ("⏳ ... כן/לא") **without** an `ActionContract` exising
at the moment it's shown (it stores the original request text and re-runs it later). By the letter of
constraint 2, this is architecturally the same class of gap PA-01 closes for the agent path. It is
**not** touched here: it is a separate, already-documented, pre-existing issue (P2 in the original
audit, "rename/classify as plan confirmation or retire") and folding its fix into PA-01 would be scope
creep beyond what was approved. Flagged for a future, separate planning gate — not silently ignored,
not silently expanded into.

---

## 4. Minimal patch design — state-only structural predicate

### 4.0 The structural predicate, exact

```
action_intent      := route.intent in _NORMAL_INTENTS      # core/router/risk_router.py:33-41, reused not duplicated
structural_clarify := route.handler == Handler.CLARIFY      # always False at this point — see §3, already
                                                              # guaranteed by the app.py:2177-2178 early return
contract_created   := any(
                          r.get("tool") == "__approval_queued__" and r.get("contract_id")
                          for r in tool_results_log
                       )                                     # turn-scoped, real id required (§4.1)

BLOCK  :=  action_intent  and  not structural_clarify  and  not contract_created
```

`final_reply`'s own **text is never read** by this predicate. `structural_clarify` is included for
documentation completeness/defense-in-depth (a future refactor could theoretically change the early-return
order) even though it is always `False` when this code runs today — it costs one boolean check to keep
the invariant self-documenting rather than relying on a comment alone.

### 4.1 `is_hijack`/`detect_case_c2_signal()` — demoted, not removed

Per decision 1, both stay exactly as shipped in `6d7875b`, doing exactly what they already do
(`app.py:2510-2571`, unmodified) — logged on every turn, unconditionally, regardless of `BLOCK`'s
value. Their role going forward:
- **Observability** — routine per-turn signal, unchanged.
- **Shadow metrics** — cross-tabulated against `BLOCK` during the shadow phase (§6) specifically to
  measure how often the text-pattern signal and the state-only predicate agree/disagree — a
  disagreement where `is_hijack=True` but `BLOCK=False` (or vice versa) is itself useful data about
  either signal's accuracy, not an error.
- **Defense-in-depth** — if `BLOCK` is ever computed incorrectly by a future bug, `is_hijack`'s
  independent, differently-derived signal remains available as a secondary detector logged
  side-by-side, not wired to any enforcement action itself.
- **Regression signal** — the 11-phrasing corpus (§5) still exercises `is_hijack`'s own correctness,
  because it remains a real, shipped, tested component — just no longer load-bearing for the
  send/replace decision.

`is_hijack`'s previously-identified advantage over `detect_case_c2_signal()` (turn-scoped vs
identity-wide `queue_count`, `PA-01_PLANNING_GATE.md`'s prior revision) remains true and relevant to
*which* of the two remains the better **shadow-metric** to watch — it does not change §4.0, since
neither is part of `BLOCK` at all now.

### 4.2 Two required code changes — both minimal, both reuse existing mechanisms

**(a) Carry a real `contract_id`, not just a sentinel flag.** `_queue_approval()`
(`app.py:2439-2443`) already computes `_gw_result.contract_id` from `propose_action()`'s return
(`core/action_gateway.py:214`) — it is simply not threaded into the log record yet:

```python
# app.py:2439-2443, one new key added to the dict already being constructed
tool_results_log.append({
    "tool": "__approval_queued__",
    "content": result,
    "ok": True,
    "contract_id": _gw_result.contract_id if _gw_result else None,  # NEW
})
```

`_gw_result` is already in scope at this exact point (it is what `_queue_approval()` just computed to
decide `result`) — no new query, no new read, a value that already exists is simply not discarded.

**(b) A dedicated, independent 3-state flag.** Reuses this repo's own established off/shadow/enforce
convention exactly (`get_runtime_schema_provider_state()`/`get_select_value_validation_state()`,
`feature_flags.py:231-250`):

```python
# feature_flags.py — new accessor, same pattern as the two existing *_STATE accessors
_PA01_STATES = frozenset({"off", "shadow", "enforce"})

def get_pa01_enforcement_state() -> str:
    """
    Three-state accessor for FEATURE_PA01_ENFORCEMENT_STATE. Independent of
    FEATURE_ACTION_GATEWAY by design — see PA-01_PLANNING_GATE.md §1 for why.
    Returns "off" for any unset/unrecognized value — fail closed to old (log-only) behavior.
    """
    value = os.environ.get("FEATURE_PA01_ENFORCEMENT_STATE", "off").strip().lower()
    return value if value in _PA01_STATES else "off"
```

`"off"` = today's `6d7875b` behavior, unchanged (`is_hijack`/`detect_case_c2_signal()` log only, §4.0's
predicate is never even evaluated). `"shadow"` = evaluate `BLOCK`, log a distinct "would_block" line,
never touch `final_reply`. `"enforce"` = evaluate `BLOCK`, replace `final_reply` when `True`. Default
`"off"` — no behavior change on merge.

### 4.3 The approved fallback constant

```python
_PA01_PHANTOM_APPROVAL_FALLBACK = (
    "לא הצלחתי להכין את הפעולה לאישור, ולכן לא נוצרה כרגע פעולה שממתינה. "
    "אפשר לשלוח שוב את הבקשה."
)
```

Exact wording per decision 4 — no longer open for revision at this planning stage.

### 4.4 The patch, sketched (not to be written yet)

Inserted immediately after the existing `OwnershipSignal` block (`app.py:2560-2571`), **before**
`memory.add()` (`app.py:2574` in the pre-patch baseline — see §4.5):

```python
# PA-01 — Phantom Approval Prompt structural enforcement (see
# docs/architecture/turn-coordinator/PA-01_PLANNING_GATE.md §4.0). State-only:
# never inspects final_reply's text. is_hijack/detect_case_c2_signal() above
# are observability/shadow-metrics/defense-in-depth only, not read here.
try:
    _pa01_action_intent = getattr(route, "intent", None) in _NORMAL_INTENTS
except Exception:
    # Cannot classify -> treat as non-action, per decision 5 ("do not fail
    # normal turns that are not action intent"). This is itself a PA-01
    # coverage gap if it ever fires (a true action-intent turn could slip
    # through unenforced) — accepted per the fail-safe-degraded policy's own
    # asymmetry: non-action-turn availability outranks this rare case.
    _pa01_action_intent = False

if _pa01_action_intent:
    from feature_flags import get_pa01_enforcement_state
    _pa01_state = get_pa01_enforcement_state()
    if _pa01_state in ("shadow", "enforce"):
        try:
            _pa01_structural_clarify = getattr(route, "handler", None) == Handler.CLARIFY
            _pa01_contract_created = any(
                r.get("tool") == "__approval_queued__" and r.get("contract_id")
                for r in tool_results_log
            )
            _pa01_block = not _pa01_structural_clarify and not _pa01_contract_created
        except Exception as exc:
            # Fail-safe degraded (decision 5): cannot verify state -> block,
            # never let an unverified reply through. Distinct log marker.
            logger.error(
                "[PA-01] PA01_ENFORCEMENT_ERROR error_type=%s user=%s",
                type(exc).__name__, _sanitize_id(identity.memory_key),
            )
            _pa01_block = True

        if _pa01_block:
            logger.warning(
                "[PA-01] phantom_approval_prompt state=%s user=%s intent=%s action=%s",
                _pa01_state, _sanitize_id(identity.memory_key),
                getattr(route, "intent", "unknown"),
                "blocked" if _pa01_state == "enforce" else "would_block",
            )
            if _pa01_state == "enforce":
                final_reply = _PA01_PHANTOM_APPROVAL_FALLBACK
```

**Fail-safe-degraded policy, resolved (supersedes the prior revision's open fail-open/fail-closed
question):** two different failure surfaces, two different answers, both per decision 5 — (i) failure
to determine `_pa01_action_intent` itself → treat as non-action, never touches `final_reply`, never
raises into the caller ("do not fail normal turns that are not action intent"); (ii) failure *after*
`_pa01_action_intent` is confirmed `True` (i.e. we know this is an action-intent turn but can't verify
contract/clarify state) → fail-closed, block, log `PA01_ENFORCEMENT_ERROR` distinctly from the normal
`would_block`/`blocked` log line. This is an intentional asymmetry, not an inconsistency: the two
branches protect different things (availability for ordinary turns vs. correctness for action-intent
turns).

### 4.5 `memory.add()` ordering — exact location

`app.py:2574` (pre-patch baseline) — `memory.add(ctx.memory_key, "assistant", final_reply)`. §4.4's
block is inserted strictly before this line (immediately after the existing `OwnershipSignal` try/except
at `app.py:2560-2571`), so if `BLOCK` fires in `"enforce"` mode, `memory.add()` receives
`_PA01_PHANTOM_APPROVAL_FALLBACK`, never the original agent text — the agent's own conversation memory
never contains a claim it didn't actually get to make to the user. Verified in the pre-patch baseline
(previous revision of this document) that nothing else reassigns `final_reply` between the
`sanitize_agent_response()` call (`app.py:2506`) and `return final_reply` (`app.py:2602`) — the new
block is the only additional writer, and it runs before the one read that matters (`memory.add()`).

**Why this does not duplicate the approval runtime:** the only new read is `route.intent`/`route.handler`
(already computed this turn) and `tool_results_log` (already accumulated this turn, now carrying one
extra key per 4.2a). Zero new queries, zero new writes beyond replacing a local string variable, zero
interaction with `ActionContract`/`ActionGateway`/`propose_action()` — `BLOCK` only reads what
`_queue_approval()` already recorded; it never calls into the Gateway itself.

---

## 5. Tests

New file, `test_pa01_phantom_approval_enforcement.py`, following the established pattern (mirrors
`test_pending_contract_read_amplification.py`/`test_turn_envelope.py`'s direct-`run_agent()`-call
style with Identity/Router/Anthropic mocked).

**Reproduction:**
- [ ] The exact "פר 349" transcript, `FEATURE_PA01_ENFORCEMENT_STATE=off` → today's behavior
  unchanged (phantom text reaches `final_reply` as-is) — pins current baseline so a future change
  can't silently alter it without the test noticing.
- [ ] Same transcript, `=shadow` → `final_reply` still equals the phantom text (unmodified), but the
  `would_block` WARNING line fires — proves shadow mode observes without acting.
- [ ] Same transcript, `=enforce` → `final_reply` equals `_PA01_PHANTOM_APPROVAL_FALLBACK` exactly.

**11-phrasing corpus (from `REPLY_OWNERSHIP_AND_APPROVAL_AUTHORITY_RESEARCH.md` §2.8), state-based
assertion only:** each phrasing run with `=enforce`, zero `tool_use`, zero contract created; assert
`final_reply == _PA01_PHANTOM_APPROVAL_FALLBACK` for all 11 — **the assertion must not branch or
special-case per phrasing**, proving `BLOCK` fires identically regardless of what `is_hijack` computes
for that phrasing (§4.1 — `is_hijack` is logged alongside as a shadow metric in this test, asserted
non-authoritative, never asserted as the reason `BLOCK` is `True`). Includes phrasing #7 ("bare, no
explicit אישור word at all") and #11 ("fully implicit") from the research doc specifically because they
stress-test that `_agent_text_claims_pending()` itself is weak on edge phrasing — which is exactly why
decision 1 demoted it.

**Decision-7 regression — the test that actually proves primary enforcement is state-based, not
text-based:**
- [ ] Construct a turn where `agent_claimed_approval=False` (`_agent_text_claims_pending()` returns
  `False` — e.g. a wording no pattern in `_AGENT_PENDING_STATUS_PATTERN`/`_agent_text_claims_pending()`
  recognizes at all, so `is_hijack` is `False` too), `action_intent` is `True` (mutating intent
  detected by `risk_router.py`), zero `tool_use` emitted, no `__approval_queued__` sentinel with a
  `contract_id` present → assert `_pa01_block is True` and, in `=enforce` mode,
  `final_reply == _PA01_PHANTOM_APPROVAL_FALLBACK`, **while asserting `is_hijack is False` on the same
  turn** (both assertions in the same test, so a future edit that accidentally reintroduces an
  `is_hijack`/text dependency into `_pa01_block`'s computation fails this test immediately). This is
  the direct regression test for the correction this planning pass exists to make — decision 7,
  verbatim.

**Regression, must-pass:**
- [ ] A **real** approval flow (`tool_use` emitted, `_queue_approval()` succeeds, `__approval_queued__`
  sentinel present **with a non-`None` `contract_id`**) → `_pa01_contract_created` is `True` →
  `_pa01_block` is `False` → `final_reply` unchanged, `=enforce` mode included in this assertion. Not
  gated on `is_hijack` at all.
- [ ] The **false-negative fix** from §4.1 (still valid as a shadow-metric-quality finding, restated
  for the new predicate): identity has an unrelated pre-existing pending contract (e.g. a Gmail draft)
  *and* this turn fabricates an unrelated phantom claim with zero `tool_use` and no `contract_id` for
  **this turn's** intent → `=enforce` still replaces `final_reply`, because `_pa01_contract_created` is
  computed from `tool_results_log` (turn-scoped) and finds nothing — proving the state predicate,
  unlike `detect_case_c2_signal()`'s identity-wide `queue_count`, is not fooled by an unrelated live
  contract belonging to a different request.
- [ ] **Known, accepted limitation — a genuine free-text clarifying question for a mutating intent with
  zero `tool_use`** (e.g. "איזה פר, 349 או 350?", where the router did *not* classify `Handler.CLARIFY`
  for this turn) → under §4.0's predicate, `structural_clarify` is `False` (router already committed to
  `Handler.AGENT`) and `contract_created` is `False` → `_pa01_block` is `True` → in `=enforce` mode
  `final_reply` **is replaced** by the fallback, even though the agent's original text was a legitimate
  question, not a phantom claim. Assert this explicitly (do not assert "unaffected" — that would
  describe the old, rejected `is_hijack`-gated design, not this one). This is the trade-off recorded in
  §7 as an accepted cost of decision 2's strictness — the test exists to keep the trade-off visible and
  regression-checked, not to hide it.
- [ ] A pending action from a **prior** turn continues to resolve correctly on "מאשר" — unaffected,
  since PA-01 only touches the tool-loop-fallthrough path, never the confirm-word early-return path
  (§1.3 of the research: those routes return before `app.py:2506` is ever reached).
- [ ] `test_turn_envelope.py` (74 assertions) and `test_pending_contract_read_amplification.py`
  (6 assertions) remain green unmodified — PA-01 must not alter `OwnershipSignal`/`detect_case_c2_signal`
  themselves, only add a new consumer of `tool_results_log`/`route` that does not touch either.
- [ ] Full existing suite (112+ `test_*.py` files, `smoke_tests.py`, `core/router/test_router.py`,
  `compileall`) stays green — same bar every change in this program has been held to.

---

## 6. Rollout plan

Reuses the 5-phase order already approved, mapped concretely to PA-01:

1. **Observation** — done, `6d7875b`. `OwnershipSignal`/`is_hijack` already logs on every
   agent-handled turn.
2. **Shadow validation** — merge §4's patch with `FEATURE_PA01_ENFORCEMENT_STATE` defaulting `"off"`
   in code; set to `"shadow"` in the Render environment (not code) after merge. Monitor the new
   `would_block` WARNING line for (a) false-positive rate — real proposals incorrectly flagged, (b)
   confirmed true positives against manual review of a sample. No user-visible change during this
   phase by construction (`"shadow"` never touches `final_reply`).
3. **Structural enforcement** — flip the Render env var to `"enforce"` only once **all** of decision
   8's graduation criteria are met, verbatim:
   - [ ] At least **7 days** of continuous `"shadow"` operation.
   - [ ] At least **50 action-intent turns or replays** observed in the `would_block` log during that
     window (a sample too small to trust a false-positive rate from).
   - [ ] **Zero** blocks of a real approval (`_pa01_contract_created` would have been `True` — i.e. a
     genuine `propose_action()` call happened — but `would_block` fired anyway). Any such event found
     is a bug in §4.0's predicate and must be fixed before graduating, not accepted as noise.
   - [ ] **Zero** blocks of a legitimate structured clarification (`structural_clarify` would have been
     `True` but `would_block` fired anyway). Per §3's finding this branch is structurally unreachable
     today (`Handler.CLARIFY` always returns before `app.py:2506`), so this criterion is expected to be
     trivially satisfied — recorded as an explicit graduation gate anyway in case a future router change
     alters that guarantee.
   - [ ] **Manual review** of every `would_block=True` shadow event from the window — not just the
     aggregate rate — specifically to catch the §5 "known limitation" case (legitimate free-text
     clarifying questions on action-intent turns, §7) at real observed volume, since that case is
     accepted as a trade-off in the abstract but its actual frequency is unmeasured until shadow data
     exists.
   - [ ] All §5 regression tests passing, including the decision-7 test and the "known, accepted
     limitation" test, on the commit being graduated.
   Graduation requires all six, not a subset — this is intentionally stricter than "false-positive rate
   judged acceptable," which was the prior, vaguer wording this replaces.
4. **Fallback** — already built in step 2/3 (§4.3's constant) — sequenced this way only because the
   user's approved order lists it as its own phase; in this patch's design it ships together with
   structural enforcement, not separately, since the fallback text has no meaning without the gate
   that triggers it.
5. **Rollout** — staged: owner/manager identities first (lowest blast radius, per this program's
   existing rollout convention in `rollout/CUTOVER_PLAN.md`'s pattern for other features), then all
   roles. **Rollback = flip the env var back to `"shadow"` or `"off"`** — no data migration, no schema
   change, no code revert needed; the flag is the entire rollback mechanism.

---

## 7. Migration risks

- **New, load-bearing risk found this pass — legitimate free-text agent clarifying questions on
  action-intent turns will be blocked/replaced, not just phantom claims.** §4.0's predicate is
  deliberately strict per decision 2: for an action-intent turn, *only* a router-classified
  `Handler.CLARIFY` may return a clarifying question — any other clarifying text the agent generates
  itself (e.g. "איזה פר, 349 או 350?" emitted as ordinary `Handler.AGENT` text, zero `tool_use`) has
  `structural_clarify=False` and `contract_created=False`, so `BLOCK` is `True` for it exactly as it is
  for an actual phantom approval claim — §4.0's predicate cannot distinguish "the agent is honestly
  asking a question" from "the agent is fabricating a pending-approval claim," because it deliberately
  never reads `final_reply`'s text at all. This is the direct, accepted cost of decision 2's
  strictness — trading a known false-positive class (legitimate clarifications get the same fallback
  wording as blocked phantom claims) for eliminating the text-pattern miss risk that motivated this
  entire revision. Concretely: today (pre-PA-01) an agent can ask a free-text clarifying question on a
  mutating-intent turn and it reaches the user unmodified; post-PA-01-enforce, that same question is
  replaced by `_PA01_PHANTOM_APPROVAL_FALLBACK` ("אפשר לשלוח שוב את הבקשה"), which is a materially worse
  reply for that specific case — it tells the user to resend rather than answering their disambiguation
  need. Not measured yet — this is exactly what §6's manual-review graduation criterion exists to
  quantify before `"enforce"` ships. If shadow data shows this fires often, the resolution is a router
  fix (make more agent-detectable clarifying-question shapes flow through `Handler.CLARIFY` structurally
  — e.g. widening `intent_router.py`'s ambiguous-phrase detection), not a regression back to a
  text-pattern carve-out inside PA-01's own predicate, which would reintroduce exactly the wording-based
  fragility this correction was made to remove. This risk is why decision 2's phrase "רק מסלול ה-CLARIFY
  המובנה רשאי" was written as a strict "only," not a "preferably" — the strictness is intentional, but
  its cost needed to be written down explicitly rather than discovered later in production.
- **False positives blocking a legitimate agent reply (phantom-claim-shaped, not clarification-shaped).**
  Mitigated by the shadow phase (step 2) — §4.0's predicate has no text-based escape hatch by design, so
  this is measured empirically via shadow data, not argued down from `is_hijack`'s accuracy (which is no
  longer part of the decision path at all, per decision 1).
- **Fallback wording is new user-facing copy**, not a "no UX change" patch — explicitly called out
  per the prior research's own Summary item, requires owner sign-off on the exact string (§4.3),
  separate from approving the mechanism itself.
- **A fourth flag** (`FEATURE_PA01_ENFORCEMENT_STATE`) added to an already flag-heavy codebase —
  justified specifically because §1 found `FEATURE_ACTION_GATEWAY` coupling to be part of the root
  cause, not incidental; reusing that flag would reintroduce the exact uncertainty documented in §1b.
- **`detect_case_c2_signal()` is left unused by this patch** despite already existing — this is
  intentional (§4.1's false-negative finding), but means two similar-looking signals now live in
  `core/turn_envelope.py` for related-but-different purposes. Worth a short doc comment cross-reference
  when implementation happens, so a future reader doesn't assume they're interchangeable.
- **Memory-write ordering** (§2) is a real correctness requirement, not just a nice-to-have — if a
  future refactor moves the enforcement block after `app.py:2574`'s `memory.add()` call, the fallback
  fixes the user-visible symptom while leaving the phantom claim in conversation memory, which the
  agent could then reference in a later turn as if it had said something true. Worth a dedicated test
  asserting `memory.add()` receives the *replaced* value, not just that `return final_reply` does.

---

## Next step

This document is the complete, corrected Planning Gate deliverable for PA-01, updated per the 8-point
correction to replace the rejected `is_hijack`-as-trigger design with a state-only structural
mechanism. No code has been written, no branch opened — **אין לממש עדיין** remains in force. Direct
answers to the six required return items:

1. **The exact structural predicate** (§4.0):
   ```
   action_intent      := route.intent in _NORMAL_INTENTS
   structural_clarify := route.handler == Handler.CLARIFY
   contract_created    := any(r.get("tool") == "__approval_queued__" and r.get("contract_id")
                              for r in tool_results_log)
   BLOCK := action_intent and not structural_clarify and not contract_created
   ```
   `final_reply`'s text is never read. `is_hijack`/`detect_case_c2_signal()` are not inputs to `BLOCK`
   at all (§4.1) — observability/shadow-metric/defense-in-depth/regression-signal only, per decision 1.

2. **Where `action_intent` comes from:** `route.intent`, already computed by the router before
   `run_agent()`'s tool loop starts, tested against `_NORMAL_INTENTS` (`core/router/risk_router.py:33-41`)
   — the existing mutating-intent bucket, reused unchanged, not duplicated (§3, §4.0).

3. **Where `structured clarification` state comes from:** `route.handler == Handler.CLARIFY`, set
   entirely inside `core/router/intent_router.py` (`detect_intent()` at `:128`, ambiguous-phrase branch
   at `:40`) before the tool loop, consumed by the existing early return at `app.py:2177-2178`. Because
   that early return fires before PA-01's enforcement point (`app.py:2506`) is ever reached,
   `structural_clarify` is provably always `False` at the point PA-01 evaluates it today — included for
   documentation/defense-in-depth completeness, not because it currently changes any outcome (§3, §4.0).

4. **Where the `ActionContract` id is obtained:** `GatewayResult.contract_id`
   (`core/action_gateway.py:214`), populated by `propose_action()` and already computed as
   `_gw_result.contract_id` inside `_queue_approval()` — currently discarded, not yet carried into
   `tool_results_log`. §4.2(a) is the one-line fix: add `"contract_id": _gw_result.contract_id if
   _gw_result else None` to the existing sentinel dict at `app.py:2439-2443`. No new query, no new read.

5. **Where reply replacement happens, exactly, before `memory.add()`:** immediately after the existing
   `OwnershipSignal` block (`app.py:2560-2571`, unmodified), strictly before `app.py:2574`'s
   `memory.add(ctx.memory_key, "assistant", final_reply)` — verified by grep that nothing else
   reassigns `final_reply` in that span, so `memory.add()` is guaranteed to receive whatever PA-01's
   block last set `final_reply` to (§2, §4.4, §4.5).

6. **Verdict: PASS.** The corrected design is state-only end to end: `action_intent` from the router's
   own intent classification, `structural_clarify` from the router's own handler classification,
   `contract_created` from the Gateway's own returned id — zero dependence on `final_reply`'s wording,
   zero dependence on `is_hijack`/`_agent_text_claims_pending()` for the enforcement decision itself,
   satisfying the correction's core requirement ("could miss a new phrasing" no longer applies, because
   no phrasing is inspected). The fallback wording (§4.3), the fail-safe-degraded error policy (§4.4),
   the `memory.add()` ordering guarantee (§4.5), the decision-7 regression test proving the mechanism
   survives `agent_claimed_approval=False` + unrecognized phrasing (§5), and the decision-8 graduation
   gate (§6) are all now specified exactly as decided, with one honestly-disclosed, not-yet-implemented
   trade-off newly surfaced by this pass and written into §7 (legitimate free-text agent clarifying
   questions on action-intent turns will also be blocked under `"enforce"`, pending router-level
   mitigation informed by shadow data) — this is a planning-stage finding to carry forward, not a gap in
   the plan itself, since §6's manual-review graduation criterion exists specifically to measure it
   before `"enforce"` ships. No further correction is required before implementation may begin.
   OH-01/OS-01/RC-01 remain out of scope until their own planning gates, per the approved order.
