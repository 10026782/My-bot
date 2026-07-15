# PA-01 Planning Gate — Phantom Approval Prompt Structural Enforcement

Program: TurnCoordinator
Status: **PLANNING ONLY.** No code written, no branch opened, no implementation started.
Baseline: `main` `f2f7093` (2026-07-15).
Scope: **PA-01 only**, per explicit instruction. OH-01 (Reply Ownership claim), OS-01 (false
cancellation/completion), RC-01 (concurrency protection) remain research-only — see
`REPLY_OWNERSHIP_AND_APPROVAL_AUTHORITY_RESEARCH.md` — and are not planned further here. Naming
per owner decision: see that document's top-of-file note and `CASE_C_CLARIFICATION_CONTINUITY.md`'s
matching update.

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

---

## 4. Minimal patch design

### 4.1 Reuses existing state — no new detection logic

`_ownership_signal` (already built at `app.py:2562-2568`, shipped in `6d7875b`) already computes
`is_hijack` = `agent_claimed_approval and not tool_use_emitted and not approval_queued`
(`core/turn_envelope.py:435-441`). **This research pass found `is_hijack` is the more correct trigger
for PA-01 than the sibling `detect_case_c2_signal()` check that sits just above it** — worth stating
explicitly since both exist in the same function and look similar:

`detect_case_c2_signal()`'s `queue_count` (`app.py:2535`) is **identity-wide**: it counts *any*
pending queue for this identity, including one from a completely unrelated prior action. Concretely:
if the user already has an unrelated pending Gmail-draft approval, and in the *same* turn asks for an
unrelated task and the agent fabricates "מוכן לאישור, שלח מאשר" for the *task*, `detect_case_c2_signal()`
returns `False` (because `queue_count > 0` from the unrelated Gmail item) — a **false negative** for
exactly the scenario PA-01 must catch. `OwnershipSignal.is_hijack`'s `tool_use_emitted`/`approval_queued`
are **turn-scoped** (computed from *this turn's* `tool_calls_made`/`tool_results_log` only), so it is
unaffected by unrelated pending state and correctly still flags the fabrication. **No new signal needs
to be built — `_ownership_signal` already exists at the exact point needed; PA-01 only needs to act on
it.**

### 4.2 New: a dedicated, independent 3-state flag

Reuses this repo's own established off/shadow/enforce convention exactly (`get_runtime_schema_provider_state()`/
`get_select_value_validation_state()`, `feature_flags.py:231-250`) rather than inventing a new flag
shape:

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

`"off"` = exactly today's `6d7875b` behavior (log only, per `log_ownership_signal`'s existing WARNING
line). `"shadow"` = compute and log a *distinct* "would have blocked" line, never touch `final_reply`.
`"enforce"` = actually replace `final_reply`. Default `"off"` — no behavior change on merge.

### 4.3 New: the deterministic fallback constant

Exact wording is a UX decision requiring owner sign-off (flagged, not decided here — matching the
prior research's own §2.6/Summary note that this counts as new user-facing copy). Proposed starting
point, designed to satisfy constraint 2 exactly ("אין לשלוח מוכן לאישור... אינו טוען שהפעולה נוצרה"):

```python
_PA01_PHANTOM_APPROVAL_FALLBACK = (
    "אני יכול להכין הצעה לפעולה הזו, אבל עדיין לא פתחתי אותה בפועל — "
    "נסח את הבקשה שוב כדי שאכין הצעה אמיתית לאישור."
)
```

This deliberately does not say "נכשלתי" (failed) — nothing failed, nothing was attempted — matching
the same principle already established for `_SINGLE_SPEAKER_FALLBACK`'s sibling case
(`core/anti_hallucination.py:544-547`'s own comment: a fabricated continuation claim is a different
failure class from an actual failure, and should not be worded as one).

### 4.4 The patch, sketched (not to be written yet)

Inserted immediately after the existing `OwnershipSignal` block, `app.py:2560-2571`:

```python
# PA-01 — Phantom Approval Prompt structural enforcement (see
# docs/architecture/turn-coordinator/PA-01_PLANNING_GATE.md). Reuses
# _ownership_signal computed above — no new detection, no new query, no
# ActionContract/approval-runtime code duplicated here. Governed by its own
# flag, independent of FEATURE_ACTION_GATEWAY (see PA-01_PLANNING_GATE.md §1).
_pa01_ownership_signal = locals().get("_ownership_signal")  # defensive: may be
                                                              # unset if the block above raised
                                                              # before assignment
if _pa01_ownership_signal is not None and _pa01_ownership_signal.is_hijack:
    from feature_flags import get_pa01_enforcement_state
    _pa01_state = get_pa01_enforcement_state()
    if _pa01_state in ("shadow", "enforce"):
        logger.warning(
            "[PA-01] phantom_approval_prompt state=%s user=%s intent=%s handler=%s action=%s",
            _pa01_state, _sanitize_id(identity.memory_key),
            _pa01_ownership_signal.recognized_intent, _pa01_ownership_signal.selected_handler,
            "blocked" if _pa01_state == "enforce" else "would_block",
        )
        if _pa01_state == "enforce":
            final_reply = _PA01_PHANTOM_APPROVAL_FALLBACK
```

**Design decision requiring owner input, not resolved here:** if this block itself raises (e.g. an
unforeseen bug in `is_hijack`'s computation), should it fail-open (let the possibly-phantom
`final_reply` through unmodified — consistent with every other Phase 0 telemetry block's convention)
or fail-closed (replace with the fallback anyway, since the one thing being protected against is
exactly "an unverified claim reaching the user")? The sketch above fails open, matching this
program's established convention throughout — flagged explicitly because PA-01 is the first block in
this program whose failure mode has a *direct* correctness consequence (not just a missing log line),
so the convention deserves an explicit re-confirmation, not a silent carry-over.

**Why this does not duplicate the approval runtime:** zero new reads (`_ownership_signal` already
computed), zero new writes, zero new persistence, zero interaction with `ActionContract`/`ActionGateway`
at all — it only decides what string `run_agent()` returns, using a boolean that already exists.

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
special-case per phrasing**, proving the mechanism is `is_hijack`-driven (state), not per-string
matching. Includes phrasing #7 ("bare, no explicit אישור word at all") and #11 ("fully implicit") from
the research doc specifically because they stress-test that the trigger isn't keyed to specific
approval vocabulary.

**Regression, must-pass:**
- [ ] A **real** approval flow (`tool_use` emitted, `_queue_approval()` succeeds,
  `__approval_queued__` sentinel present) → `is_hijack` is `False` → `final_reply` unchanged,
  `=enforce` mode included in this assertion.
- [ ] The **false-negative fix** from §4.1: identity has an unrelated pre-existing pending contract
  (e.g. a Gmail draft) *and* this turn fabricates an unrelated phantom claim with zero `tool_use` →
  `=enforce` still replaces `final_reply` (proving `is_hijack`'s turn-scoping catches what
  `detect_case_c2_signal()`'s identity-wide `queue_count` would have missed — this is a **new**
  regression case this planning pass found, not present in existing tests).
- [ ] A genuine clarifying question for a mutating intent with zero `tool_use` (e.g. "איזה פר, 349
  או 350?") does **not** trigger `is_hijack` (because `_agent_text_claims_pending()` — reused
  unchanged from `core/turn_envelope.py:344` — does not match clarifying-question phrasing) →
  `final_reply` unchanged even in `=enforce` mode. **This is the test that proves PA-01 is not a
  blanket "block every zero-tool-use agent reply" gate** — required per constraint 2's own framing
  ("agent may propose an action" remains legal).
- [ ] A pending action from a **prior** turn continues to resolve correctly on "מאשר" — unaffected,
  since PA-01 only touches the tool-loop-fallthrough path, never the confirm-word early-return path
  (§1.3 of the research: those routes return before `app.py:2506` is ever reached).
- [ ] `test_turn_envelope.py` (74 assertions) and `test_pending_contract_read_amplification.py`
  (6 assertions) remain green unmodified — PA-01 must not alter `OwnershipSignal`/`detect_case_c2_signal`
  themselves, only add a new consumer of `_ownership_signal`.
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
3. **Structural enforcement** — flip the Render env var to `"enforce"` once shadow data is reviewed
   and the false-positive rate is judged acceptable (threshold is an owner decision, not set here).
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

- **False positives blocking a legitimate agent reply.** Mitigated by the shadow phase (step 2) and
  by §4.1's `is_hijack` already being narrower/more accurate than the alternative signal it could have
  used — but not eliminated; this is exactly what shadow data is for.
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

This document is the complete Planning Gate deliverable for PA-01. No code has been written, no
branch opened. Implementation may begin once the owner confirms: the fallback wording (§4.3), the
fail-open/fail-closed decision on the enforcement block's own errors (§4.4), and the false-positive
threshold for flipping shadow→enforce (§6 step 3). OH-01/OS-01/RC-01 remain out of scope until their
own planning gates, per the approved order.
