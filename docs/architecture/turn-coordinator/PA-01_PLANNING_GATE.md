# PA-01 Planning Gate — Phantom Approval Prompt Structural Enforcement

Program: TurnCoordinator
Status: **PLANNING ONLY.** No code written, no branch opened, no implementation started.
Baseline: `main` `f2f7093` (2026-07-15).
Scope: **PA-01 only**, per explicit instruction. OH-01 (Reply Ownership claim), OS-01 (false
cancellation/completion), RC-01 (concurrency protection) remain research-only — see
`REPLY_OWNERSHIP_AND_APPROVAL_AUTHORITY_RESEARCH.md` — and are not planned further here. Naming
per owner decision: see that document's top-of-file note and `CASE_C_CLARIFICATION_CONTINUITY.md`'s
matching update.

**Revision note (pass 1):** the original §4 used `_ownership_signal.is_hijack` as the primary
enforcement trigger. Correctly rejected: `is_hijack` is derived from `agent_claimed_approval`, a
text-pattern match (`_agent_text_claims_pending()`) — using it as the *decision* mechanism is still
wording-based enforcement, just one layer removed from the obvious version, and would still miss a
new phrasing the pattern doesn't cover. §4 was rewritten around a **state-only structural
predicate** that never inspects `final_reply`'s text at all. `is_hijack`/`detect_case_c2_signal()`
are retained, demoted to observability/shadow-metrics/defense-in-depth/regression-signal roles only
(§4.1), never the authority that decides whether a reply is replaced.

**Revision note (pass 2, this pass):** pass 1's predicate still had a **structural false positive**:
its `action_intent` term was `route.intent in _NORMAL_INTENTS` — but `_NORMAL_INTENTS`
(`core/router/risk_router.py:33-41`) is a *routing* bucket (which intents reach `Handler.AGENT` under
which role/domain combos), not a *contract-expectation* bucket. It contains `DRAFT_EMAIL`,
`DRAFT_MESSAGE`, `QUALIFY_LEAD`, and `STORE_MEMORY` — four intents whose legitimate, common fulfillment
shape does **not** require an `ActionContract` at all (§3.5 below has the full analysis and table).
Under pass 1's predicate, a correct, honest "here's your draft" reply to a `DRAFT_EMAIL` request with
zero `tool_use` would have been wrongly replaced by the fallback — a real false positive, not a
hypothetical one, and structural (baked into the predicate itself, not a shadow-phase measurement
question). §3.5 (new) and §4.0 (revised) below fix this: `action_intent` is replaced by
`approval_contract_expected`, sourced from a new, narrower, explicit policy set —
`_CONTRACT_REQUIRED_INTENTS` — not from `_NORMAL_INTENTS`, and not duplicated as a second list inside
`app.py`.

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

## 3.5 Canonical intent → contract-expectation policy (new this pass)

### Why `_NORMAL_INTENTS` cannot be reused for this

`_NORMAL_INTENTS` (`core/router/risk_router.py:33-41`) answers "does this intent reach `Handler.AGENT`
(vs. read-only/high-risk/unknown handling)" — a routing question. `requires_approval` on a *tool*
(`tool_registry.py`'s `ToolMeta.requires_approval`, e.g. `airtable_add`, `calendar_create_event`,
`gmail_draft`) answers "does calling *this specific tool* need an `ActionContract`" — an execution
question, and it is **role/domain-invariant**: `tool_registry.needs_approval(tool_name)` reads only the
static `ToolMeta.requires_approval` field, never `identity.role`/`domain` (verified by reading
`tool_registry.py:280-282` — no role/domain parameter exists on that function at all). PA-01's question
is a third, different one — "does a *well-formed, legitimate* turn classified with this *intent* always
involve calling one of those approval-gated tools this turn, such that a zero-`tool_use` reply is
inherently suspicious" — and no existing set in the codebase answers it. Building it requires walking
every `_NORMAL_INTENTS` member against the concrete tool(s) that would fulfill it, using
`tools/dispatcher.py`'s 21-case `case "..."` switch (which is exhaustive — every dispatchable tool,
cross-checked 1:1 against `tool_registry.py`'s 21 `_REGISTRY` entries) as the ground truth for "which
tools exist at all," since several `_NORMAL_INTENTS` values have **no dispatcher case that fulfills
them whatsoever** (found this pass, see table).

### Full table — every `_NORMAL_INTENTS` member

| Intent | Backing tool if fulfilled | `requires_approval`? | Contract-required? | Why / expected behavior with zero `tool_use` |
|---|---|---|---|---|
| `CREATE_TASK` | `airtable_add` (Tasks) | True (`tool_registry.py:120-128`) | **Yes** | No natural "just talk about it" shape for filing a task — a zero-`tool_use` reply claiming it's done/pending is exactly PA-01's target. |
| `UPDATE_TASK` | `airtable_update` (Tasks) | True (`:129-137`) | **Yes** | Same reasoning as `CREATE_TASK`. |
| `COMPLETE_TASK` | `airtable_update` (Tasks) | True (`:129-137`) | **Yes** | Same. |
| `CREATE_EVENT` | `calendar_create_event` | True (`:72-78`) | **Yes** | Same. |
| `UPDATE_EVENT` | **none — no dispatcher case exists** | N/A | **No — but flagged separately** | No `calendar_update_event`/`calendar_delete_event` tool exists anywhere in `tools/dispatcher.py`, `tools/schemas.py`, or `tool_registry.py` (grepped: zero matches beyond `calendar_get_events`/`calendar_create_event`). If classified contract-required, `contract_created` could **structurally never become `True`** for this intent — every `UPDATE_EVENT` turn would be permanently replaced by the fallback, and re-sending (the fallback's own instruction) cannot fix it either. Classified **not** contract-required here specifically to avoid that trap. The underlying gap (the agent cannot actually fulfill an "update this calendar event" request through any tool) is real, pre-existing, and out of PA-01's scope — worth its own backlog item, not silently absorbed into this predicate. |
| `SCHEDULE_MEETING` | `calendar_create_event` | True (`:72-78`) | **Yes** | Same as `CREATE_EVENT`. |
| `CREATE_CONTACT` | `airtable_add` (Contacts) | True | **Yes** | Same reasoning as `CREATE_TASK`. |
| `UPDATE_CONTACT` | `airtable_update` (Contacts) | True | **Yes** | Same. |
| `CREATE_LEAD` | `airtable_add` (Leads) | True | **Yes** | Same. (Inbound automatic lead creation goes through `inbound_handler.py`/`lead_capture.py`, not this agent-tool-loop path at all — irrelevant here.) |
| `UPDATE_LEAD` | `airtable_update` (Leads) | True | **Yes** | Same. |
| `QUALIFY_LEAD` | `airtable_update` (Leads, score/stage) *if and when a write happens* | True | **No** | The classifier pattern (`core/router/intent_router.py:62`, "כשיר/qualify...ליד") fires on a request to *assess* a lead — the natural, common shape is a conversational qualifying dialogue (the agent asks questions, reasons about temperature) with no write that same turn; a write only happens once qualification concludes, and when it does, `airtable_update`'s own `requires_approval=True` self-polices via the existing Gateway path regardless of this predicate. Treating every `QUALIFY_LEAD` turn as contract-required would block ordinary qualifying questions. |
| `UPDATE_DEAL_STAGE` | `airtable_update` (Deals) | True | **Yes** | Same reasoning as `CREATE_TASK`. |
| `DRAFT_EMAIL` | `gmail_draft` *if and when the agent actually calls it* | True | **No** | This is the user-flagged false positive. The classifier pattern (`intent_router.py:73`, "כתוב/נסח...מייל") fires on a request to *compose* email text — the common, legitimate shape is the agent writing the draft directly in the chat reply with zero `tool_use`, before (if ever) actually filing it via `gmail_draft`. When the agent *does* call `gmail_draft`, that call is itself `requires_approval=True` and goes through `_queue_approval()` exactly like any other gated tool (`app.py:2361` — `if meta.requires_approval:` is generic, not per-tool-listed) — so real `gmail_draft` calls are unaffected by this classification either way. Classifying `DRAFT_EMAIL` as contract-required would block the ordinary "show me a draft" reply. |
| `DRAFT_MESSAGE` | **none — no dispatcher case exists** | N/A | **No** | No WhatsApp/Telegram draft-save tool is registered anywhere (`tools/dispatcher.py`'s 21 cases contain no such tool) — this intent is fulfilled entirely by the agent writing message text in its reply; there is no tool path at all, so `contract_created` could never become `True` for it, same structural trap as `UPDATE_EVENT` if misclassified. |
| `STORE_MEMORY` | **none — no dispatcher case exists** | N/A | **No** | No memory-write tool is registered either (`search_business_memory` is `read_only=True`) — this intent is fulfilled via `app.py`'s own `memory.add()` conversation-memory pipeline directly, never through `tools/dispatcher.py`. Same structural reasoning as `UPDATE_EVENT`/`DRAFT_MESSAGE`. |

**Summary: 10 of 15 are contract-required** (`CREATE_TASK`, `UPDATE_TASK`, `COMPLETE_TASK`,
`CREATE_EVENT`, `SCHEDULE_MEETING`, `CREATE_CONTACT`, `UPDATE_CONTACT`, `CREATE_LEAD`, `UPDATE_LEAD`,
`UPDATE_DEAL_STAGE`) — each maps deterministically to exactly one dispatcher tool with
`requires_approval=True` and has no legitimate zero-`tool_use` fulfillment shape. **5 are not**
(`UPDATE_EVENT`, `QUALIFY_LEAD`, `DRAFT_EMAIL`, `DRAFT_MESSAGE`, `STORE_MEMORY`) — three for having no
backing tool at all (a pre-existing, separate gap, flagged not fixed), two for having a legitimate,
common, zero-`tool_use` conversational shape whose eventual real tool call (if any) self-polices via
the tool's own `requires_approval` flag independent of this predicate.

**Honest coverage note:** classifying `DRAFT_EMAIL`/`QUALIFY_LEAD`/`STORE_MEMORY`/`DRAFT_MESSAGE` as
not contract-required means a phantom "ready/pending" claim on one of *these* four intents specifically
is **not** structurally blocked by PA-01 — the same coverage gap Case C2/`is_hijack` already describe
and log (§4.1), now explicitly still open for this narrower slice rather than closed by accident. This
is the deliberate, disclosed trade-off of fixing the structural false-positive: narrowing
`approval_contract_expected` to the 10 intents where it is unambiguous, rather than keeping it broad
and wrong. Widening coverage for these four (without reintroducing the false positive) is future work,
not blocking this pass — see §7's updated risk list.

### The canonical policy source — one definition, no duplication in `app.py`

Added to `core/router/risk_router.py` — the same module that already owns `_NORMAL_INTENTS`/
`_HIGH_RISK_INTENTS`, so intent policy has exactly one home, not two:

```python
# core/router/risk_router.py — new, alongside the existing intent buckets

# Subset of _NORMAL_INTENTS whose fulfillment always routes through a
# requires_approval=True dispatcher tool with no legitimate zero-tool_use
# shape. See PA-01_PLANNING_GATE.md §3.5 for the per-intent table and the
# reasoning for what is deliberately excluded (draft/conversational intents,
# and intents with no backing tool at all).
_CONTRACT_REQUIRED_INTENTS = {
    Intent.CREATE_TASK, Intent.UPDATE_TASK, Intent.COMPLETE_TASK,
    Intent.CREATE_EVENT, Intent.SCHEDULE_MEETING,
    Intent.CREATE_CONTACT, Intent.UPDATE_CONTACT,
    Intent.CREATE_LEAD, Intent.UPDATE_LEAD,
    Intent.UPDATE_DEAL_STAGE,
}
assert _CONTRACT_REQUIRED_INTENTS <= _NORMAL_INTENTS  # sanity: never a superset

# Documentation/test-only view — not consumed by the predicate itself, kept
# so a reader (and test_pa01_*.py) can see the excluded set by name rather
# than by subtraction.
_NON_CONTRACT_NORMAL_INTENTS = _NORMAL_INTENTS - _CONTRACT_REQUIRED_INTENTS


def requires_action_contract(intent: str) -> bool:
    """
    PA-01's single source of truth for "does a well-formed turn with this
    intent require a real ActionContract before an approval-shaped reply is
    legitimate." Role/domain-invariant by design — see PA-01_PLANNING_GATE.md
    §3.5 (tool_registry.py's requires_approval is itself role/domain-invariant).
    """
    return intent in _CONTRACT_REQUIRED_INTENTS
```

`app.py` imports and calls `requires_action_contract(route.intent)` (§4.4) — it does not define, copy,
or maintain any intent list of its own. This satisfies the "no duplicate list in `app.py`" requirement
directly: there is exactly one `_CONTRACT_REQUIRED_INTENTS` definition in the whole codebase.

---

## 4. Minimal patch design — state-only structural predicate

### 4.0 The structural predicate, exact (revised, pass 2)

```
approval_contract_expected := requires_action_contract(route.intent)   # core/router/risk_router.py, §3.5 — NOT _NORMAL_INTENTS
contract_created            := any(
                                   r.get("tool") == "__approval_queued__" and r.get("contract_id")
                                   for r in tool_results_log
                                )                                       # turn-scoped, real id required (§4.1)

BLOCK  :=  approval_contract_expected  and  not contract_created
```

`final_reply`'s own **text is never read** by this predicate — unchanged from pass 1.
`approval_contract_expected` replaces pass 1's `action_intent` (`route.intent in _NORMAL_INTENTS`),
which was a structural false positive (§3.5, revision note pass 2): it treated `DRAFT_EMAIL`,
`DRAFT_MESSAGE`, `QUALIFY_LEAD`, and `STORE_MEMORY` — intents with a legitimate, common,
zero-`tool_use` fulfillment shape — as if they always needed a contract.

**`structural_clarify` is dropped from the live predicate, not just renamed.** Pass 1 carried it as a
defensive `and not structural_clarify` term. Per §3 (unchanged this pass): `Handler.CLARIFY` is decided
entirely upstream, inside `core/router/` (`intent_router.py:128`/`:40`), consumed by the early return at
`app.py:2177-2178` — **before** the tool loop, long before `app.py:2506` where PA-01's block runs.
By the time any turn reaches PA-01's enforcement point, `route.handler` has already been proven to not
be `CLARIFY` (the early return would have fired otherwise) — so `structural_clarify` is not a live input
at this gate at all, it is a fact about a different, earlier gate. Keeping a permanently-`False` term in
the live formula added a false impression that clarification-awareness happens *here*; it does not —
clarification protection is upstream and structural, enforced by `app.py:2177-2178` existing at all, not
by anything PA-01 evaluates. This is documented here instead, not encoded as a redundant runtime check.

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

### 4.2 Three required code changes — all minimal, all reuse existing mechanisms

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

**(c) The canonical policy source itself (new this pass, §3.5).** `_CONTRACT_REQUIRED_INTENTS`,
`_NON_CONTRACT_NORMAL_INTENTS`, and `requires_action_contract()` added to
`core/router/risk_router.py`, alongside the existing `_NORMAL_INTENTS`/`_HIGH_RISK_INTENTS` buckets —
full definition in §3.5. `app.py` imports and calls `requires_action_contract(route.intent)` only; no
intent list is defined or copied inside `app.py` itself.

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
# approval_contract_expected comes from risk_router.requires_action_contract()
# — the one canonical policy source (§3.5) — never a locally-defined list.
try:
    from core.router.risk_router import requires_action_contract
    _pa01_contract_expected = requires_action_contract(getattr(route, "intent", None))
except Exception:
    # Cannot classify -> treat as non-contract-required, per decision 5 ("do
    # not fail normal turns that are not action intent"). This is itself a
    # PA-01 coverage gap if it ever fires (a true contract-required turn
    # could slip through unenforced) — accepted per the fail-safe-degraded
    # policy's own asymmetry: ordinary-turn availability outranks this rare case.
    _pa01_contract_expected = False

if _pa01_contract_expected:
    from feature_flags import get_pa01_enforcement_state
    _pa01_state = get_pa01_enforcement_state()
    if _pa01_state in ("shadow", "enforce"):
        try:
            _pa01_contract_created = any(
                r.get("tool") == "__approval_queued__" and r.get("contract_id")
                for r in tool_results_log
            )
            _pa01_block = not _pa01_contract_created
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
to determine `_pa01_contract_expected` itself (e.g. `requires_action_contract()` raises) → treat as
not-contract-required, never touches `final_reply`, never raises into the caller ("do not fail normal
turns that are not action intent"); (ii) failure *after* `_pa01_contract_expected` is confirmed `True`
(i.e. we know this intent requires a contract but can't verify whether one was created) → fail-closed,
block, log `PA01_ENFORCEMENT_ERROR` distinctly from the normal `would_block`/`blocked` log line. This is
an intentional asymmetry, not an inconsistency: the two branches protect different things (availability
for ordinary/non-contract-required turns vs. correctness for contract-required turns).

### 4.5 `memory.add()` ordering — exact location

`app.py:2574` (pre-patch baseline) — `memory.add(ctx.memory_key, "assistant", final_reply)`. §4.4's
block is inserted strictly before this line (immediately after the existing `OwnershipSignal` try/except
at `app.py:2560-2571`), so if `BLOCK` fires in `"enforce"` mode, `memory.add()` receives
`_PA01_PHANTOM_APPROVAL_FALLBACK`, never the original agent text — the agent's own conversation memory
never contains a claim it didn't actually get to make to the user. Verified in the pre-patch baseline
(previous revision of this document) that nothing else reassigns `final_reply` between the
`sanitize_agent_response()` call (`app.py:2506`) and `return final_reply` (`app.py:2602`) — the new
block is the only additional writer, and it runs before the one read that matters (`memory.add()`).

**Why this does not duplicate the approval runtime:** the only new reads are `route.intent` (via
`requires_action_contract()`, §3.5 — imported, not duplicated) and `tool_results_log` (already
accumulated this turn, now carrying one extra key per 4.2a). Zero new queries, zero new writes beyond
replacing a local string variable, zero interaction with `ActionContract`/`ActionGateway`/
`propose_action()` — `BLOCK` only reads what `_queue_approval()` already recorded; it never calls into
the Gateway itself.

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
  recognizes at all, so `is_hijack` is `False` too), intent is `Intent.CREATE_TASK` (a
  `_CONTRACT_REQUIRED_INTENTS` member, §3.5, so `approval_contract_expected` is `True`), zero `tool_use`
  emitted, no `__approval_queued__` sentinel with a `contract_id` present → assert `_pa01_block is True`
  and, in `=enforce` mode, `final_reply == _PA01_PHANTOM_APPROVAL_FALLBACK`, **while asserting
  `is_hijack is False` on the same turn** (both assertions in the same test, so a future edit that
  accidentally reintroduces an `is_hijack`/text dependency into `_pa01_block`'s computation fails this
  test immediately). This is the direct regression test for the correction this planning pass exists to
  make — decision 7, verbatim.

**§3.5 policy regression — the intent-classification correction this pass exists to make (new this
pass, the user's 6 required cases):**
- [ ] **`DRAFT_EMAIL` with zero `tool_use`** ("here's a draft: ...") → `approval_contract_expected` is
  `False` (§3.5 — `DRAFT_EMAIL` is excluded from `_CONTRACT_REQUIRED_INTENTS`) → `_pa01_block` is never
  evaluated at all → `final_reply` passes through unchanged in `=enforce` mode. This is the exact
  false-positive pass 1 would have produced; the test pins that it no longer does.
- [ ] **`DRAFT_MESSAGE` with zero `tool_use`** — same shape and same assertion as `DRAFT_EMAIL`, and
  additionally documents why: no dispatcher tool exists for this intent at all (§3.5), so
  `contract_created` could never become `True` for it if it were misclassified as contract-required.
- [ ] **A `_CONTRACT_REQUIRED_INTENTS` member (e.g. `CREATE_TASK`) with zero `tool_use`** →
  `approval_contract_expected` is `True`, `contract_created` is `False` → `=enforce` mode replaces
  `final_reply` with `_PA01_PHANTOM_APPROVAL_FALLBACK`. This is PA-01's actual target case.
- [ ] **A `_CONTRACT_REQUIRED_INTENTS` member with a real `ActionContract`** (`tool_use` emitted,
  `_queue_approval()` succeeds, `__approval_queued__` sentinel present with a non-`None` `contract_id`)
  → `contract_created` is `True` → `_pa01_block` is `False` → the real Gateway-composed prompt
  (`app.py:863`) reaches the user unmodified, `=enforce` mode included. Not gated on `is_hijack` at all.
- [ ] **An intent not in `_CONTRACT_REQUIRED_INTENTS` (e.g. `QUALIFY_LEAD`) where a tool call *does*
  succeed this turn** (e.g. the agent calls `airtable_update` mid-qualification and it is queued via the
  Gateway normally) → `approval_contract_expected` is `False`, so `BLOCK` is never evaluated regardless
  of what `tool_results_log` contains → `final_reply` unaffected either way. Confirms PA-01 never touches
  a turn outside the 10-intent contract-required set, independent of tool-call outcome.
- [ ] **`Intent.UNKNOWN` and any `_READ_ONLY_INTENTS` member** (e.g. `Intent.ASK_QUESTION`) → neither is
  in `_NORMAL_INTENTS` at all, so `requires_action_contract()` returns `False` trivially → unaffected,
  `=enforce` mode included in the assertion.

**Regression, must-pass:**
- [ ] The **false-negative fix** from §4.1 (still valid as a shadow-metric-quality finding, restated
  for the new predicate): identity has an unrelated pre-existing pending contract (e.g. a Gmail draft)
  *and* this turn fabricates an unrelated phantom claim for a `_CONTRACT_REQUIRED_INTENTS` intent with
  zero `tool_use` and no `contract_id` for **this turn's** intent → `=enforce` still replaces
  `final_reply`, because `_pa01_contract_created` is computed from `tool_results_log` (turn-scoped) and
  finds nothing — proving the state predicate, unlike `detect_case_c2_signal()`'s identity-wide
  `queue_count`, is not fooled by an unrelated live contract belonging to a different request.
- [ ] **Known, accepted limitation — a genuine free-text clarifying question for a
  `_CONTRACT_REQUIRED_INTENTS` intent with zero `tool_use`** (e.g. "איזה משימה, X או Y?" for a
  `CREATE_TASK` turn, where the router did *not* classify `Handler.CLARIFY` for this turn) → under
  §4.0's predicate, `contract_created` is `False` → `_pa01_block` is `True` → in `=enforce` mode
  `final_reply` **is replaced** by the fallback, even though the agent's original text was a legitimate
  question, not a phantom claim. Assert this explicitly (do not assert "unaffected"). This is narrower
  now than pass 1's version of this risk — it only applies to the 10 contract-required intents, not all
  15 former `_NORMAL_INTENTS` members — and remains the trade-off recorded in §7 as an accepted cost of
  decision 2's strictness; the test exists to keep it visible and regression-checked, not to hide it.
- [ ] A pending action from a **prior** turn continues to resolve correctly on "מאשר" — unaffected,
  since PA-01 only touches the tool-loop-fallthrough path, never the confirm-word early-return path
  (§1.3 of the research: those routes return before `app.py:2506` is ever reached).
- [ ] `test_turn_envelope.py` (74 assertions) and `test_pending_contract_read_amplification.py`
  (6 assertions) remain green unmodified — PA-01 must not alter `OwnershipSignal`/`detect_case_c2_signal`
  themselves, only add a new consumer of `tool_results_log`/`route` that does not touch either.
- [ ] `_CONTRACT_REQUIRED_INTENTS <= _NORMAL_INTENTS` (§3.5's own sanity assertion) is itself asserted in
  the test file — catches a future edit that adds a new intent to one set without considering the other.
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
   - [ ] At least **50 contract-required-intent turns or replays** (i.e. `route.intent` in
     `_CONTRACT_REQUIRED_INTENTS`, §3.5 — not the broader former `_NORMAL_INTENTS`) observed in the
     `would_block` log during that window (a sample too small to trust a false-positive rate from).
   - [ ] **Zero** blocks of a real approval (`_pa01_contract_created` would have been `True` — i.e. a
     genuine `propose_action()` call happened — but `would_block` fired anyway). Any such event found
     is a bug in §4.0's predicate and must be fixed before graduating, not accepted as noise.
   - [ ] **Zero** blocks of a `DRAFT_EMAIL`/`DRAFT_MESSAGE`/`QUALIFY_LEAD`/`UPDATE_EVENT`/`STORE_MEMORY`
     turn (§3.5's non-contract-required set). Per §4.0's predicate this branch is structurally
     unreachable by construction (`approval_contract_expected` is `False` for all five, so `BLOCK` is
     never evaluated) — this criterion exists as an explicit graduation gate anyway, specifically to
     catch a future edit that accidentally moves one of these five into `_CONTRACT_REQUIRED_INTENTS`
     without re-verifying §3.5's reasoning first.
   - [ ] **Manual review** of every `would_block=True` shadow event from the window — not just the
     aggregate rate — specifically to catch the §5 "known limitation" case (legitimate free-text
     clarifying questions on a contract-required intent, §7) at real observed volume, since that case is
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

- **Structural false positive found this pass (pass 2), now fixed — recorded so its reasoning is not
  lost.** Pass 1's predicate used `route.intent in _NORMAL_INTENTS`, which included `DRAFT_EMAIL`,
  `DRAFT_MESSAGE`, `QUALIFY_LEAD`, and `STORE_MEMORY` — intents with a legitimate, common,
  zero-`tool_use` fulfillment shape (§3.5). Under that predicate, an honest "here's your draft" reply
  would have been unconditionally replaced by the fallback, on every such turn, not as a rare
  shadow-measured edge case but as a guaranteed outcome of the classification itself. Fixed by
  `approval_contract_expected := requires_action_contract(route.intent)` (§3.5, §4.0), sourced from the
  new, narrower `_CONTRACT_REQUIRED_INTENTS` (10 of the 15 former `_NORMAL_INTENTS` members). This item
  is not a residual risk — it is closed by this pass's correction — recorded here as the reason the
  predicate looks the way it now does.
- **Narrowed, still-real risk — legitimate free-text agent clarifying questions on *contract-required*
  turns will be blocked/replaced, not just phantom claims.** §4.0's predicate is deliberately strict per
  decision 2: for a `_CONTRACT_REQUIRED_INTENTS` turn (§3.5 — now only 10 intents, not all 15 former
  `_NORMAL_INTENTS` members), *only* a router-classified `Handler.CLARIFY` may return a clarifying
  question — any other clarifying text the agent generates itself (e.g. "איזה משימה, X או Y?" emitted as
  ordinary `Handler.AGENT` text, zero `tool_use`, for a `CREATE_TASK` turn) has `contract_created=False`,
  so `BLOCK` is `True` for it exactly as it is for an actual phantom approval claim — §4.0's predicate
  cannot distinguish "the agent is honestly asking a question" from "the agent is fabricating a
  pending-approval claim," because it deliberately never reads `final_reply`'s text at all. This is the
  direct, accepted cost of decision 2's strictness — trading a known false-positive class (legitimate
  clarifications get the same fallback wording as blocked phantom claims) for eliminating the
  text-pattern miss risk that motivated the pass-1 revision. This risk is now **structurally scoped to
  the 10 contract-required intents only** (§3.5) — pass 1's version of this risk, before the
  `approval_contract_expected` fix, additionally misapplied to `DRAFT_EMAIL`/`DRAFT_MESSAGE`/
  `QUALIFY_LEAD`/`STORE_MEMORY`, where it was not a rare edge case but the common case; this pass's fix
  removes that larger, guaranteed-to-fire portion of the risk, leaving only the genuinely rare
  clarifying-question case on the 10 intents where a real write is actually expected. Not measured yet —
  this is exactly what §6's manual-review graduation criterion exists to quantify before `"enforce"`
  ships. If shadow data shows this fires often, the resolution is a router fix (make more
  agent-detectable clarifying-question shapes flow through `Handler.CLARIFY` structurally — e.g.
  widening `intent_router.py`'s ambiguous-phrase detection), not a regression back to a text-pattern
  carve-out inside PA-01's own predicate, which would reintroduce exactly the wording-based fragility
  this correction was made to remove.
- **False positives blocking a legitimate agent reply (phantom-claim-shaped, not clarification-shaped),
  within the 10 contract-required intents.** Mitigated by the shadow phase (step 2) — §4.0's predicate
  has no text-based escape hatch by design, so this is measured empirically via shadow data, not argued
  down from `is_hijack`'s accuracy (which is no longer part of the decision path at all, per decision 1).
- **`_CONTRACT_REQUIRED_INTENTS`/`_NON_CONTRACT_NORMAL_INTENTS` (§3.5) is a new policy surface that must
  be kept in sync with `_NORMAL_INTENTS` and with the dispatcher's actual tool set.** A future new intent
  added to `_NORMAL_INTENTS` without also classifying it in §3.5's table is a silent gap — it defaults to
  "not contract-required" only if explicitly added to `_NON_CONTRACT_NORMAL_INTENTS`, and to nothing
  (undefined membership) otherwise, which `requires_action_contract()` would treat as `False` by
  construction (`in` on a set that doesn't contain it) — i.e. **the fail-safe direction for an
  unclassified new intent is "not contract-required," not "contract-required."** This is the same
  fail-safe-degraded asymmetry as decision 5's turn-level policy, applied one level up at the
  intent-catalog level: a newly-added, not-yet-classified intent silently gets PA-01 coverage skipped
  rather than silently blocking turns for an intent nobody has reasoned about yet. Documented so a future
  maintainer adding an intent knows to update §3.5's table deliberately, not assume it happens
  automatically.
- **Three of the five non-contract-required intents (`UPDATE_EVENT`, `DRAFT_MESSAGE`, `STORE_MEMORY`)
  have no backing tool at all** — a separate, pre-existing gap (§3.5) this pass found but does not fix:
  the agent has no way to actually fulfill these requests through any registered tool, regardless of
  PA-01. Worth its own backlog item; out of PA-01's scope.
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

This document is the complete Planning Gate deliverable for PA-01 through two corrections: pass 1
replaced the rejected `is_hijack`-as-trigger design with a state-only structural mechanism; pass 2 (this
edit) fixes a structural false positive in that mechanism's `action_intent` term, found by the owner.
No code has been written, no branch opened — **אין לממש עדיין** remains in force. Direct answers to the
required return items:

**Full intent mapping (§3.5):** all 15 members of `_NORMAL_INTENTS` classified — 10 contract-required
(`CREATE_TASK`, `UPDATE_TASK`, `COMPLETE_TASK`, `CREATE_EVENT`, `SCHEDULE_MEETING`, `CREATE_CONTACT`,
`UPDATE_CONTACT`, `CREATE_LEAD`, `UPDATE_LEAD`, `UPDATE_DEAL_STAGE` — each maps deterministically to one
`requires_approval=True` dispatcher tool, no legitimate zero-`tool_use` shape), 5 not
(`DRAFT_EMAIL`/`DRAFT_MESSAGE`/`QUALIFY_LEAD` — legitimate common zero-`tool_use` conversational shape,
self-policing via the tool's own `requires_approval` flag if/when a real tool call does happen;
`UPDATE_EVENT`/`STORE_MEMORY`/`DRAFT_MESSAGE` — no backing dispatcher tool exists at all, so
contract-required classification would be a permanent-block trap). Full per-intent table with reasoning
in §3.5.

**Canonical policy source:** `core/router/risk_router.py` — same module that already owns
`_NORMAL_INTENTS`/`_HIGH_RISK_INTENTS`, extended (not duplicated elsewhere) with
`_CONTRACT_REQUIRED_INTENTS` (a 10-member subset of `_NORMAL_INTENTS`, with a sanity assertion that it
never becomes a superset), `_NON_CONTRACT_NORMAL_INTENTS` (the derived, documentation/test-only
complement), and a public function `requires_action_contract(intent: str) -> bool` (§3.5). `app.py`
imports and calls this function only — it defines no intent list of its own, satisfying the "no
duplicate list in `app.py`" requirement directly.

**Corrected predicate** (§4.0):
```
approval_contract_expected := requires_action_contract(route.intent)   # §3.5, NOT _NORMAL_INTENTS
contract_created            := any(r.get("tool") == "__approval_queued__" and r.get("contract_id")
                                    for r in tool_results_log)
BLOCK := approval_contract_expected and not contract_created
```
`final_reply`'s text is never read. `structural_clarify` (pass 1's third term) is **dropped from the
live formula**, not renamed — `Handler.CLARIFY` is decided entirely upstream and always returns before
`app.py:2506` is reached (§3, §4.0), so it was dead weight in the runtime predicate; clarification
protection is documented as an upstream, structural fact instead of a redundant runtime check.
`is_hijack`/`detect_case_c2_signal()` remain non-inputs to `BLOCK`, per pass 1's decision 1 (§4.1).

**Verdict: PASS.** Pass 2's correction is itself now state-only and duplication-free:
`approval_contract_expected` comes from one canonical function in `core/router/risk_router.py`, derived
from a 10-intent set built by walking every `_NORMAL_INTENTS` member against the actual dispatcher tool
set (not asserted from first principles) — `DRAFT_EMAIL`/`DRAFT_MESSAGE`/`QUALIFY_LEAD`/`STORE_MEMORY`
(and `UPDATE_EVENT`, found along the way) are excluded with concrete, cited reasoning (§3.5), not by
guesswork. The predicate itself is simpler than pass 1's (two terms instead of three, since
`structural_clarify` was proven dead weight), while being *more* correct (no structural false positive
on the four intents the owner flagged). §5 now carries the 6 required §3.5 regression cases verbatim,
§6's graduation criteria are restated in terms of the corrected contract-required set, and §7 documents
both the newly-closed risk (pass 1's guaranteed false positive on draft/conversational intents) and the
narrowed-but-still-open one (legitimate free-text clarifying questions on the 10 remaining
contract-required intents, now structurally scoped down from all 15). No further correction is required
before implementation may begin. OH-01/OS-01/RC-01 remain out of scope until their own planning gates,
per the approved order.
