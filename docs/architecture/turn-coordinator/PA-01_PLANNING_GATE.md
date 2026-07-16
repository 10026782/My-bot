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

**Revision note (pass 2):** pass 1's predicate still had a **structural false positive**:
its `action_intent` term was `route.intent in _NORMAL_INTENTS` — but `_NORMAL_INTENTS`
(`core/router/risk_router.py:33-41`) is a *routing* bucket (which intents reach `Handler.AGENT` under
which role/domain combos), not a *contract-expectation* bucket. It contains `DRAFT_EMAIL`,
`DRAFT_MESSAGE`, `QUALIFY_LEAD`, and `STORE_MEMORY` — four intents whose legitimate, common fulfillment
shape does **not** require an `ActionContract` at all (§3.5 below has the full analysis and table).
Under pass 1's predicate, a correct, honest "here's your draft" reply to a `DRAFT_EMAIL` request with
zero `tool_use` would have been wrongly replaced by the fallback — a real false positive, not a
hypothetical one, and structural (baked into the predicate itself, not a shadow-phase measurement
question). §3.5 fixed this: `action_intent` was replaced by `approval_contract_expected`, sourced from
a new, narrower, explicit policy set — `_CONTRACT_REQUIRED_INTENTS` — not from `_NORMAL_INTENTS`, and
not duplicated as a second list inside `app.py`.

**Revision note (pass 3, this pass):** pass 2's `approval_contract_expected` still had a second,
independent structural false positive: it assumed that whenever an intent is contract-required, an
`ActionContract` *can* be created this turn, for this identity — ignoring that (a) `ctx.allowed_tools`
is role-filtered (`context.py:44-79`) and several roles (`employee`, `lead`, `guest`, `readonly`) are
never even offered the write tool a contract-required intent needs; (b) `tool_registry.check_allowed()`
is a second, independently-maintained role-tool policy layer that can diverge from (a); (c)
`enforce()`/`enforce_leads_write_gate()` can still deny/preflight-block a tool call *after* it is
attempted, inside the tool loop; (d) `action_validator.validate_action()` is a further, independent
defense-in-depth gate. None of these are phantom claims — they are legitimate, structurally-detectable
reasons no contract exists, and conflating them with a phantom claim means telling a `guest` who
structurally cannot ever get a task approved to "just send the request again" (§4.3's fallback wording),
which is actively misleading. §3.6 (new) and §4.0 (revised again) below fix this: the single
`approval_contract_expected` boolean is split into `intent_requires_contract_for_success` (policy-only,
role/domain-invariant, what pass 2 already had, renamed) and `contract_capable_this_turn`
(runtime-dependent — can *this* identity's *this* turn actually reach a contract at all), plus a new
`structured_terminal_outcome` signal read from `tool_results_log` for the mid-turn denial/preflight/
validation cases. The Phantom-fallback predicate now requires all of: contract required, capable,
no contract created, no other structured terminal outcome.

**Revision note (pass 4, this pass):** pass 3's `contract_created`/`structured_terminal_outcome` still
had a third structural false positive: **neither term was scoped to the intent's own expected tool.**
`contract_created` matched *any* `__approval_queued__` sentinel carrying *any* `contract_id` — so an
agent that misfires and calls `calendar_create_event` while the user actually asked for `CREATE_TASK`
(expected tool `airtable_add`) would produce a real `ActionContract` for the *event*, and pass 3's
predicate would read that as "the task's contract exists," routing to matrix row 2 (Gateway prompt)
for a task that was never actually queued for approval — the opposite failure from Phantom (a false
*negative* on the block, not a false positive on it, but equally a misreport of what actually
happened). The same gap applied to `structured_terminal_outcome`: `_pa01_structured_terminal_outcome()`
returned the *first* `terminal_outcome` found in `tool_results_log` regardless of which tool it
belonged to, so an unrelated `PERMISSION_DENIED` earlier in the same turn could suppress a genuine
Phantom block for the intent actually being evaluated. §4.2(a) now tags the sentinel with the real
`action_tool` the contract was created for; both `contract_created_for_expected_tool` and the
terminal-outcome lookup (§4.2f) are scoped against `expected_tool_for_intent(route.intent)` before
being read at all (§4.0, revised again).

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

## 3.5 Canonical intent → contract-expectation policy (pass 2; policy-source revised to a dict in pass 3)

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
`intent_requires_contract_for_success` to the 10 intents where it is unambiguous, rather than keeping it
broad and wrong. Widening coverage for these four (without reintroducing the false positive) is future
work, not blocking this pass — see §7's updated risk list.

### The canonical policy source — one definition, no duplication in `app.py`

Added to `core/router/risk_router.py` — the same module that already owns `_NORMAL_INTENTS`/
`_HIGH_RISK_INTENTS`, so intent policy has exactly one home, not two. **Revised in pass 3:** a plain
`_CONTRACT_REQUIRED_INTENTS` set (pass 2) is not enough — §3.6 needs to know *which tool* each
contract-required intent expects, to check that specific tool's capability, not just "some write tool
exists." Replaced by a dict, `intent → expected tool name`, matching §3.5's table 1:1:

```python
# core/router/risk_router.py — new, alongside the existing intent buckets

# Every _NORMAL_INTENTS member that always routes through a requires_approval=True
# dispatcher tool with no legitimate zero-tool_use shape, mapped to that tool's
# exact name. See PA-01_PLANNING_GATE.md §3.5 for the per-intent table and the
# reasoning for what is deliberately excluded (draft/conversational intents, and
# intents with no backing tool at all).
_CONTRACT_REQUIRED_INTENT_TO_TOOL: dict[str, str] = {
    Intent.CREATE_TASK:       "airtable_add",
    Intent.UPDATE_TASK:       "airtable_update",
    Intent.COMPLETE_TASK:     "airtable_update",
    Intent.CREATE_EVENT:      "calendar_create_event",
    Intent.SCHEDULE_MEETING:  "calendar_create_event",
    Intent.CREATE_CONTACT:    "airtable_add",
    Intent.UPDATE_CONTACT:    "airtable_update",
    Intent.CREATE_LEAD:       "airtable_add",
    Intent.UPDATE_LEAD:       "airtable_update",
    Intent.UPDATE_DEAL_STAGE: "airtable_update",
}
assert set(_CONTRACT_REQUIRED_INTENT_TO_TOOL) <= _NORMAL_INTENTS  # sanity: never a superset

# Documentation/test-only view — not consumed by the predicate itself, kept
# so a reader (and test_pa01_*.py) can see the excluded set by name rather
# than by subtraction.
_NON_CONTRACT_NORMAL_INTENTS = _NORMAL_INTENTS - set(_CONTRACT_REQUIRED_INTENT_TO_TOOL)


def intent_requires_contract_for_success(intent: str) -> bool:
    """
    PA-01's single source of truth for "does a well-formed turn with this
    intent require a real ActionContract before an approval-shaped reply is
    legitimate." Policy-only, role/domain-invariant by design — see
    PA-01_PLANNING_GATE.md §3.5 (tool_registry.py's requires_approval is
    itself role/domain-invariant) and §3.6 for the separate, runtime/identity
    -dependent question of whether a contract can actually be created THIS
    turn, for THIS identity (that is contract_capable_this_turn, §3.6 — not
    this function).
    """
    return intent in _CONTRACT_REQUIRED_INTENT_TO_TOOL


def expected_tool_for_intent(intent: str) -> str | None:
    """The single dispatcher tool a contract-required intent's fulfillment
    expects — None for anything not in _CONTRACT_REQUIRED_INTENT_TO_TOOL.
    Consumed by §3.6's contract_capable_this_turn, not by
    intent_requires_contract_for_success itself."""
    return _CONTRACT_REQUIRED_INTENT_TO_TOOL.get(intent)
```

`app.py` imports and calls `intent_requires_contract_for_success(route.intent)` and
`expected_tool_for_intent(route.intent)` (§4.4) — it does not define, copy, or maintain any intent list
or intent→tool mapping of its own. This satisfies the "no duplicate list in `app.py`" requirement
directly: there is exactly one `_CONTRACT_REQUIRED_INTENT_TO_TOOL` definition in the whole codebase.

---

## 3.6 Runtime capability layer (new this pass) — why "contract-required" ≠ "contract-capable"

### The gap pass 2 missed

§3.5 answers a **policy** question: for this *intent*, does a well-formed fulfillment need a contract.
It says nothing about *this identity, this turn* — whether the expected tool is even reachable. Four
independent, already-existing gates sit between "intent is contract-required" and "a contract actually
gets created," none of which pass 2 accounted for:

1. **Role-based tool offering.** `ctx.allowed_tools` (`context.py:30-79`, `AgentContext.allowed_tools`,
   built once per turn by `_filter_tools(identity.role)` from `_ROLE_TOOLS`, `context.py:44-74`) is the
   list of tools actually passed to the Claude API call (`app.py:2272`, `tools=ctx.allowed_tools`) — a
   tool not in this list **cannot be called by the agent at all this turn**, structurally, not by
   policy. Verified directly: `Role.EMPLOYEE`'s entry (`context.py:65-68`) is `{"calendar_get_events",
   "airtable_get"}` — both read-only; `Role.LEAD`'s entry (`context.py:69-71`) is `{"airtable_get"}`
   only; `Role.GUEST`/`Role.READONLY` (`context.py:72-73`) are both `set()`. None of these four roles
   are ever offered `airtable_add`/`airtable_update`/`calendar_create_event` — i.e. **none of the 10
   `_CONTRACT_REQUIRED_INTENT_TO_TOOL` tools are reachable by these four roles at all**, for any
   contract-required intent.
2. **A second, independently-maintained role-tool policy layer.** `tool_registry.py`'s
   `ToolMeta.roles_allowed` (e.g. `airtable_add`'s `_INTERNAL` = owner/partner/manager/employee,
   `tool_registry.py:120-122`) is a *different* set, maintained in a *different file*, from
   `context.py`'s `_ROLE_TOOLS`. Both currently agree in direction (employee is excluded from
   `context.py`'s offered-tools set for `airtable_add`, even though `tool_registry.py`'s
   `roles_allowed` would technically permit it) — but nothing enforces they stay in sync; they are two
   independently-edited files. `tool_registry.check_allowed(tool_name, identity)` (`tool_registry.py:
   258-262`) reads the second layer and must be checked too, precisely because it does not always agree
   with the first — a tool offered per `context.py` but denied per `tool_registry.py` (or vice versa)
   is a real, checkable drift condition, not a hypothetical one.
3. **`route.tool_allowed`** (`core/router/route_decision.py:166`, computed in `core/router/router.py:
   109-136`) — a third, independent gate: `False` for `Handler.RESTRICTED` (non-senior role attempting
   a `_HIGH_RISK_INTENTS` member — converted to `Handler.AGENT` with `tool_allowed=False`,
   `router.py:111-116`) or `Handler.BLOCK` (`router.py:118-120`). Checked today at `app.py:2337` (silent
   tool block inside the loop) and `app.py:2208` (an *upstream, pre-Claude-call* short-circuit,
   `check_deterministic_denial()`, discussed below). Structurally, `_CONTRACT_REQUIRED_INTENT_TO_TOOL`'s
   10 intents are all `_NORMAL_INTENTS` members, and `detect_risk()` (`core/router/risk_router.py:99
   -117`) never routes a `_NORMAL_INTENTS` member through `Handler.RESTRICTED` (that branch is
   exclusively for `_HIGH_RISK_INTENTS`) — so `route.tool_allowed` is provably always `True` for a
   contract-required turn that reaches PA-01's gate *today*. Included in `contract_capable_this_turn`
   anyway, same defensive-completeness reasoning as pass 2's (dropped) `structural_clarify` term — cheap
   to check, protects against a future router change silently invalidating the assumption.
4. **Mid-turn denial/preflight/validation gates**, which cannot be predicted upfront at all (a role can
   pass all three checks above and *still* be denied once the agent actually attempts the call) —
   covered by `structured_terminal_outcome`, not `contract_capable_this_turn`. See below.

### A closely-related, pre-existing mechanism found this pass — not the same thing, not reused as-is

`core/router/deterministic_denial.py`'s `check_deterministic_denial()` (called at `app.py:2208-2216`,
**before** the Claude API call) already does something adjacent: for a small, deliberately conservative
set of `(intent, tool)` hints (`INTENT_TOOL_HINTS`, `deterministic_denial.py:41-44` — currently only
`Intent.UPDATE_LEAD`/`Intent.CREATE_LEAD` → `airtable_update`/`airtable_add`), it calls
`tool_registry.check_allowed()` and `enforce_leads_write_gate()` and, if the outcome is **already
certain**, returns a `DeterministicDenial` that skips the Claude round-trip entirely, with `run_agent()`
returning `denial.message` directly (`app.py:2210-2216`) — a return **before** PA-01's own gate
(`app.py:2506`) is ever reached, same class of "upstream, structural, never seen by PA-01" as
`Handler.CLARIFY`.

This is **not** reused as `contract_capable_this_turn`'s implementation, for a documented, deliberate
reason stated in the module's own comment (`deterministic_denial.py:7-9`): *"מודול הזה אף פעם לא מחליט
'מותר' — רק 'אסור' או 'לא יודע'"* ("this module never decides 'allowed' — only 'denied' or 'unknown'").
It is an asymmetric, conservative, denial-only optimizer — returning `None` means "don't know, let the
agent try," never "confirmed capable." `contract_capable_this_turn` needs the opposite shape: a genuine
positive capability assertion PA-01 can rely on to choose between the Phantom-fallback branch and the
Capability-unavailable branch. Reusing `check_deterministic_denial()` as-is would be wrong twice over:
it would silently inherit its narrow, 2-intent-only scope (8 of the 10 contract-required intents have no
`INTENT_TOOL_HINTS` entry at all today), and its `None` return does not mean what
`contract_capable_this_turn=True` needs to mean.

**Relationship, stated precisely so the two are never confused:** for the 2 intents
`check_deterministic_denial()` already covers, a `role_not_allowed`/`leads_write_gate` denial is
resolved *upstream* of PA-01 (same as `Handler.CLARIFY`) — PA-01's own `contract_capable_this_turn`/
`structured_terminal_outcome` checks are pure defense-in-depth for those 2 cases specifically. For the
other 8 contract-required intents, PA-01's own checks are the **only** structural coverage that exists
— not defense-in-depth, load-bearing.

### `contract_capable_this_turn`, exact

```python
def contract_capable_this_turn(route, identity, ctx) -> bool:
    expected_tool = expected_tool_for_intent(route.intent)   # risk_router.py, §3.5
    if expected_tool is None:
        return False   # not contract-required at all — caller must check
                        # intent_requires_contract_for_success first (§4.0)
    return (
        any(t["name"] == expected_tool for t in ctx.allowed_tools)   # context.py:30-79
        and tool_registry.check_allowed(expected_tool, identity)      # tool_registry.py:258-262
        and route.tool_allowed                                        # route_decision.py:166
    )
```

All three reads are of state already computed earlier this same turn (`ctx` at `build_context()`,
`route` at `route_request()`) — no new query, no new I/O. **Table-granularity limitation, disclosed
honestly:** `airtable_add`/`airtable_update` back 6 of the 10 contract-required intents
(`CREATE_TASK`/`CREATE_CONTACT`/`CREATE_LEAD` all → `airtable_add`; `UPDATE_TASK`/`UPDATE_CONTACT`/
`UPDATE_LEAD`/`UPDATE_DEAL_STAGE`/`COMPLETE_TASK` all → `airtable_update`) — `contract_capable_this_turn`
can only check *tool-level* reachability, not *table-level* (e.g. it cannot know upfront whether this
identity may write to the Leads table specifically vs. the Tasks table). That finer-grained denial is
exactly what `enforce_leads_write_gate()`'s preflight (`PREFLIGHT_BLOCKED`, below) exists to catch — the
two layers are complementary by necessity, not redundant.

### Structured terminal outcomes — six, all state-sourced, zero text inspection

A `StructuredTerminalOutcome` is looked up from `tool_results_log` entries carrying a new
`"terminal_outcome"` key (added at three existing catch/return sites, §4.2) — never from `final_reply`
or any agent-authored text. **Scoped by tool, since pass 4:** the lookup only considers an entry whose
own tool identity matches `expected_tool_for_intent(route.intent)` — `r["tool"] == expected_tool` for
the `ToolDenied`/`LeadsDirectWriteBlocked` entries (§4.2b, already tagged with the real `tu.name`), or
`r["action_tool"] == expected_tool` for the `__approval_queued__` sentinel (§4.2a, new `action_tool`
key). An outcome belonging to a different tool the agent happened to call this turn is not a terminal
outcome *for this intent* and must not suppress its Phantom check — see the pass-4 revision note above
for the concrete misfire this closes.

| Outcome | Source (file:line) | Reachable at PA-01's gate today? |
|---|---|---|
| `CAPABILITY_UNAVAILABLE` | Not read from `tool_results_log` — it *is* the deterministic response §4.4 uses when `contract_capable_this_turn` is `False`, computed upfront (§3.6 above). | **Yes** — the primary new case this pass fixes (`guest`/`employee`/`lead`/`readonly` attempting a contract-required intent). |
| `PERMISSION_DENIED` | `ToolDenied` caught at `app.py:2352-2358` (existing code). **Gap found this pass:** currently appends only to `tool_results` (the Claude-facing list), never to `tool_results_log` — §4.2 adds a `"terminal_outcome": "PERMISSION_DENIED"` entry there. | Rare given `contract_capable_this_turn` already checks `tool_registry.check_allowed()` upfront — fires only if `enforce()`'s live check disagrees with that upfront check (e.g. the two role-tool layers noted in §3.6 point 2 drift, or `identity` state changes mid-turn). Real defense-in-depth, not decorative. |
| `PREFLIGHT_BLOCKED` | `LeadsDirectWriteBlocked` caught at `app.py:2369-2378` (existing BUG-091 code, `enforce_leads_write_gate()`). **Same gap:** currently appends only to `tool_results` — §4.2 adds the same new key there. | **Yes, load-bearing** — this is exactly the table-granularity case §3.6 flagged: a role can be `airtable_add`-capable in general and still be preflight-blocked on the Leads table specifically. |
| `VALIDATION_FAILED` | `action_validator.validate_action()` returning `ActionBlocked` inside `tools/dispatcher.py:156-162`. | **Not reachable within a PA-01-relevant turn today**, disclosed honestly: `_queue_approval()` (`app.py:730+`) never calls `dispatch_tool()`/`validate_action()` — it calls `propose_action()` directly (`app.py:783`/`805`), so a contract-required tool's inputs are never run through `action_validator` in the *same* turn PA-01 evaluates. `validate_action()` only runs later, when an *already-approved* action is actually dispatched — a different turn, outside PA-01's scope. Defined in the enum for completeness and for non-contract-required tool dispatches (where it *is* reachable, just irrelevant to `BLOCK_PHANTOM` since those turns never reach this predicate). |
| `STRUCTURED_CLARIFICATION` | `route.handler == Handler.CLARIFY` — same fact §4.0 (pass 2) already established. | **No** — structurally unreachable at PA-01's gate, `Handler.CLARIFY` always returns at `app.py:2177-2178`, before `app.py:2506`. Listed here for matrix completeness (§4.0's decision table), not as a live check. |
| `APPROVAL_QUEUE_ERROR` | `_queue_approval()`'s own early-return branches that are *not* a successful contract creation: duplicate-fingerprint block (`app.py:753-757`), cross-channel duplicate suppression (`app.py:766-772`), `GatewayResult.ok=False`/persistence failure (`app.py:794-799`, `816-817`), owner-notify failure (`app.py:856-860`). **Gap found this pass:** the `__approval_queued__` sentinel (`app.py:2439-2443`) is appended unconditionally with `"ok": True` regardless of which of these branches produced `result` — §4.2 enriches it to distinguish a real success from a structured non-creation. | **Yes, load-bearing** — without this, every one of these already-accurate, gate-authored messages (e.g. "⚠️ פעולה זו כבר בוצעה לאחרונה") would be *replaced* by the generic Phantom fallback under pass 2's predicate, which is a real regression in message accuracy, not just a missed optimization. |

---

## 4. Minimal patch design — state-only structural predicate

### 4.0 The decision matrix and the Phantom-only predicate, exact (revised, pass 4)

Pass 3 split pass 2's single `approval_contract_expected` boolean into four independent signals
(§3.5/§3.6) and stated the **full decision matrix** (not just the Phantom-block case). Pass 4 keeps the
same four-signal shape but scopes two of the four terms to the intent's own expected tool — otherwise a
contract or terminal outcome belonging to a *different* tool the agent happened to touch this turn could
be misread as covering the intent actually being evaluated (pass-4 revision note above):

```
expected_tool                         := expected_tool_for_intent(route.intent)                # §3.5, policy-only
intent_requires_contract_for_success  := intent_requires_contract_for_success(route.intent)    # §3.5, policy-only
contract_capable_this_turn            := contract_capable_this_turn(route, identity, ctx)      # §3.6, runtime-dependent

contract_created_for_expected_tool    := any(
    r.get("tool") == "__approval_queued__"
    and r.get("contract_id")
    and r.get("action_tool") == expected_tool
    for r in tool_results_log
)                                                                                                # turn-scoped AND tool-scoped (pass 4)

structured_terminal_outcome           := first entry in tool_results_log where either
                                              (r.get("tool") == expected_tool and r.get("terminal_outcome"))
                                           or (r.get("tool") == "__approval_queued__"
                                               and r.get("action_tool") == expected_tool
                                               and r.get("terminal_outcome")),
                                          else None                                              # §3.6's outcome table, now tool-scoped (pass 4)
```

`contract_created_for_expected_tool` replaces pass 3's `contract_created` (renamed, not just
re-scoped — the name itself now states the invariant it enforces). A contract or terminal outcome for
any tool other than `expected_tool` is invisible to this predicate entirely; it may still be logged
elsewhere (A32 telemetry, `is_hijack` shadow metrics) but never satisfies rows 2 or 3 below for *this*
intent.

**Decision matrix (§4.4 implements this directly):**

| `intent_requires_contract_for_success` | `contract_capable_this_turn` | `contract_created_for_expected_tool` | `structured_terminal_outcome` | Response |
|---|---|---|---|---|
| False | — | — | — | ordinary agent reply, PA-01 never touches it |
| True | — | True | — | `_queue_approval()`'s own Gateway Approval Prompt (`app.py:863`), unchanged |
| True | True | False | set | that outcome's own deterministic response (§4.4) |
| True | True | False | None | **Phantom fallback** (§4.3) — this is the only cell that was ever the actual target |
| True | False | False | — | **Capability/permission deterministic response** (§4.3b) — never the Phantom fallback, never a raw agent reply |

(Row 2 — `contract_created_for_expected_tool=True` — takes priority regardless of
`contract_capable_this_turn`/`structured_terminal_outcome`: if a contract genuinely exists **for this
intent's own expected tool** this turn, capability was self-evidently sufficient and no further check is
needed. Pass 4 correction: a contract created for a *different* tool — e.g. the agent called
`calendar_create_event` while the intent was `CREATE_TASK` — no longer satisfies this row at all; it
falls through to whichever of rows 3-5 the real state resolves to, exactly as if no contract had been
created, because for `CREATE_TASK`'s purposes none was.)

**The Phantom-only predicate, exact — this is what actually replaces `final_reply` with §4.3's fallback
text specifically:**

```
BLOCK_PHANTOM  :=  intent_requires_contract_for_success
                    and contract_capable_this_turn
                    and not contract_created_for_expected_tool
                    and not structured_terminal_outcome
```

`final_reply`'s own **text is never read** by any of these signals — unchanged from pass 1.
`intent_requires_contract_for_success` is pass 2's `approval_contract_expected`, renamed to match this
pass's terminology (same function, same set, no behavior change to this term). `contract_capable_this_turn`
and `structured_terminal_outcome` were both new in pass 3 (§3.6) — together they fix the structural false
positive described in the pass-3 revision note above: a `guest`/`employee`/`lead`/`readonly` identity
attempting a contract-required intent now resolves to the capability row, not the Phantom row; a
mid-turn `ToolDenied`/`LeadsDirectWriteBlocked`/queueing failure now resolves to its own outcome row, not
the Phantom row. Pass 4 adds the `_for_expected_tool` scoping to `contract_created` and tool-scopes
`structured_terminal_outcome` (§4.0 above) — without it, a contract or denial belonging to a tool other
than the intent's own `expected_tool` could wrongly satisfy row 2 or row 3, hiding a genuine Phantom case
behind unrelated turn activity.

**`structural_clarify` remains dropped from the live predicate** (pass 2's finding, unchanged): `Handler.
CLARIFY` is decided entirely upstream, inside `core/router/` (`intent_router.py:128`/`:40`), consumed by
the early return at `app.py:2177-2178` — before the tool loop, before `app.py:2506` where PA-01's block
runs. `STRUCTURED_CLARIFICATION` is listed in §3.6's outcome table purely for decision-matrix
completeness (so a reader sees why it's not a live check), not as a term any code evaluates at this gate.

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

### 4.2 Six required code changes — all minimal, all reuse existing mechanisms

**(a) Carry a real `contract_id`, not just a sentinel flag.** `_queue_approval()`
(`app.py:2439-2443`) already computes `_gw_result.contract_id` from `propose_action()`'s return
(`core/action_gateway.py:214`) — it is simply not threaded into the log record yet:

```python
# app.py:2439-2443, three new keys added to the dict already being constructed
tool_results_log.append({
    "tool": "__approval_queued__",
    "content": result,
    "ok": bool(_gw_result and _gw_result.contract_id),                                # CHANGED (was hardcoded True)
    "contract_id": _gw_result.contract_id if _gw_result else None,                    # NEW (pass 2)
    "terminal_outcome": None if (_gw_result and _gw_result.contract_id) else "APPROVAL_QUEUE_ERROR",  # NEW (pass 3, §3.6)
    "action_tool": tu.name,                                                            # NEW (pass 4, §4.0) — the real tool call that triggered this contract
})
```

`_gw_result` is already in scope at this exact point, and so is `tu` (the `tool_use` block whose
`requires_approval=True` tool routed here — the same object `tu.name` is read from at the `enforce()`
call a few lines earlier in the same loop iteration). **Revised this pass:** pass 2 only added
`contract_id`; pass 3 also fixed `"ok"` (previously hardcoded `True` even for duplicate/rejected/
notify-failed returns — itself a pre-existing minor inaccuracy in the A32 log, unrelated to PA-01 but
worth fixing alongside since the same line was being touched) and added `"terminal_outcome"` so
§3.6's `APPROVAL_QUEUE_ERROR` case is structurally detectable without inspecting `result`'s text; pass 4
adds `"action_tool"` — **from the real tool call, never guessed from `route.intent`** — so §4.0's
`contract_created_for_expected_tool` can verify the contract was actually created for the tool the
intent expected, not merely that *some* contract exists this turn.

**(b) Tag the two existing mid-turn denial branches with a `terminal_outcome`.** Both already exist and
already produce an accurate, gate-authored message — they currently just don't reach `tool_results_log`
at all (§3.6's finding):

```python
# app.py:2352-2358 (existing ToolDenied catch) — one new tool_results_log append
try:
    meta = enforce(tu.name, identity)
except ToolDenied as e:
    logger.warning(f"[Tool] Denied: {tu.name} for {identity.role}")
    tool_results.append({
        "type": "tool_result", "tool_use_id": tu.id, "content": str(e)
    })
    tool_results_log.append({                                    # NEW
        "tool": tu.name, "content": str(e), "ok": False,          # NEW
        "terminal_outcome": "PERMISSION_DENIED",                  # NEW
    })                                                             # NEW
    continue
```

```python
# app.py:2369-2378 (existing LeadsDirectWriteBlocked catch) — same pattern
except LeadsDirectWriteBlocked as e:
    logger.warning(f"[Approval] preflight blocked Leads write before queueing: {tu.name}")
    tool_results.append({
        "type": "tool_result", "tool_use_id": tu.id, "content": str(e)
    })
    tool_results_log.append({                                    # NEW
        "tool": tu.name, "content": str(e), "ok": False,          # NEW
        "terminal_outcome": "PREFLIGHT_BLOCKED",                  # NEW
    })                                                             # NEW
    continue
```

Both reuse `str(e)` — text the *gate itself* already authored (`ToolDenied`'s/`LeadsDirectWriteBlocked`'s
own exception message), not agent-generated text. Reading it back later (§4.4) is not the text-detection
this document's decision 8/pass-1's "no wording as primary mechanism" rule forbids — that rule is about
never inferring intent from the *agent's* free-form output; a fixed, gate-authored, non-agent string
keyed by a structured `terminal_outcome` field is state, not inference. Both entries already carry
`"tool": tu.name` — the real tool the denial/preflight-block happened on — so no separate `action_tool`
key is needed here for pass 4's scoping (§4.0): `r.get("tool") == expected_tool` is sufficient for these
two, and only the `__approval_queued__` sentinel needed a dedicated `action_tool` key since its own
`"tool"` field is the fixed literal `"__approval_queued__"`, not a real tool name.

**(c) A dedicated, independent 3-state flag.** Reuses this repo's own established off/shadow/enforce
convention exactly (`get_runtime_schema_provider_state()`/`get_select_value_validation_state()`,
`feature_flags.py:231-250`) — unchanged from pass 2:

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

`"off"` = today's `6d7875b` behavior, unchanged. `"shadow"` = evaluate the full matrix (§4.0), log a
distinct line per row, never touch `final_reply`. `"enforce"` = evaluate the matrix, replace
`final_reply` per the matrix's response column. Default `"off"` — no behavior change on merge.

**(d) The canonical policy source itself (§3.5, revised this pass to a dict).**
`_CONTRACT_REQUIRED_INTENT_TO_TOOL`, `_NON_CONTRACT_NORMAL_INTENTS`,
`intent_requires_contract_for_success()`, and `expected_tool_for_intent()` added to
`core/router/risk_router.py`, alongside the existing `_NORMAL_INTENTS`/`_HIGH_RISK_INTENTS` buckets —
full definition in §3.5. `app.py` imports and calls these two functions only; no intent list or
intent→tool mapping is defined or copied inside `app.py` itself.

**(e) `contract_capable_this_turn()` (§3.6, new this pass).** A small, pure function — reads
`ctx.allowed_tools`, calls `tool_registry.check_allowed()`, reads `route.tool_allowed` — placed either
alongside `expected_tool_for_intent()` in `core/router/risk_router.py` (keeps all PA-01 policy in one
module) or as a local helper in `app.py` immediately before its one call site (§4.4) — either is
acceptable; the planning-stage recommendation is `risk_router.py`, for the same "one home for intent
policy" reasoning as (d), since it also needs `expected_tool_for_intent()` internally.

**(f) Structured terminal-outcome lookup, one small helper — scoped to `expected_tool` (revised pass 4).**
Reads only `tool_results_log` (already fully constructed by (a)/(b) above by the time PA-01's block
runs). Pass 3's version returned the *first* `terminal_outcome` in the log regardless of which tool it
belonged to; pass 4 requires the entry's own tool identity to match `expected_tool` first — an entry for
a different tool is not a terminal outcome for *this* intent and is skipped, not returned:

```python
def _pa01_structured_terminal_outcome(
    tool_results_log: list[dict], expected_tool: str | None,
) -> tuple[str, str] | None:
    if expected_tool is None:
        return None
    for r in tool_results_log:
        outcome = r.get("terminal_outcome")
        if not outcome:
            continue
        # the __approval_queued__ sentinel's real tool lives in "action_tool" (§4.2a);
        # every other tagged entry (ToolDenied/LeadsDirectWriteBlocked, §4.2b) already
        # carries the real tool name directly in "tool".
        entry_tool = r.get("action_tool") if r.get("tool") == "__approval_queued__" else r.get("tool")
        if entry_tool == expected_tool:
            return outcome, r.get("content", "")
    return None
```

### 4.3 Approved fallback constants — two, not one

```python
# (a) Phantom claim, no evidence at all of any attempt to create a contract.
# Exact wording per decision 4 (prior pass) — no longer open for revision.
_PA01_PHANTOM_APPROVAL_FALLBACK = (
    "לא הצלחתי להכין את הפעולה לאישור, ולכן לא נוצרה כרגע פעולה שממתינה. "
    "אפשר לשלוח שוב את הבקשה."
)

# (b) Capability/permission gap. Deliberately does NOT say "try sending the
# request again": resending changes nothing when the real blocker is a
# role/capability gap, and telling the user otherwise is actively misleading
# (the exact failure mode §3.6 was written to prevent).
# Wording approved by decision 7, pass 4 — supersedes pass 3's draft text.
_PA01_CAPABILITY_UNAVAILABLE_FALLBACK = (
    "לא ניתן לבצע את הפעולה הזו דרך החשבון הנוכחי. "
    "לביצוע, יש לפנות למנהל מורשה."
)
```

`_PA01_CAPABILITY_UNAVAILABLE_FALLBACK`'s wording is now **approved** (decision 7, pass 4) — pass 3's
draft ("הפעולה הזו אינה זמינה עבור התפקיד שלך... פנה לבעלים או למנהל") is superseded and should not be
used. For the four mid-turn `structured_terminal_outcome` cases (`PERMISSION_DENIED`/`PREFLIGHT_BLOCKED`/
`APPROVAL_QUEUE_ERROR`/`VALIDATION_FAILED`), **no new constant is introduced** — §4.4 reuses the
gate-authored `content` string §4.2(b)/(a) already captured, since it is already accurate and
outcome-specific (e.g. `enforce_leads_write_gate()`'s own message names the exact table/reason), and
inventing a fourth generic string would be strictly less informative than what the gate already said.

### 4.4 The patch, sketched (not to be written yet)

Inserted immediately after the existing `OwnershipSignal` block (`app.py:2560-2571`), **before**
`memory.add()` (`app.py:2574` in the pre-patch baseline — see §4.5). Implements the full §4.0 matrix,
not just the Phantom row — every branch below corresponds to exactly one matrix row:

```python
# PA-01 — Phantom Approval Prompt structural enforcement (see
# docs/architecture/turn-coordinator/PA-01_PLANNING_GATE.md §4.0/§3.6). State-only:
# never inspects final_reply's text at any point. is_hijack/detect_case_c2_signal()
# above are observability/shadow-metrics/defense-in-depth only, not read here.
try:
    from core.router.risk_router import intent_requires_contract_for_success
    _pa01_contract_required = intent_requires_contract_for_success(getattr(route, "intent", None))
except Exception:
    # Cannot classify -> treat as non-contract-required (matrix row 1), per
    # decision 5 ("do not fail normal turns that are not action intent").
    # A PA-01 coverage gap if it ever fires — accepted per fail-safe-degraded
    # policy's own asymmetry: ordinary-turn availability outranks this rare case.
    _pa01_contract_required = False

if _pa01_contract_required:
    from feature_flags import get_pa01_enforcement_state
    from core.router.risk_router import expected_tool_for_intent
    _pa01_state = get_pa01_enforcement_state()
    if _pa01_state in ("shadow", "enforce"):
        try:
            _pa01_expected_tool = expected_tool_for_intent(getattr(route, "intent", None))
            _pa01_contract_created = any(
                r.get("tool") == "__approval_queued__"
                and r.get("contract_id")
                and r.get("action_tool") == _pa01_expected_tool          # NEW (pass 4, §4.0)
                for r in tool_results_log
            )
            _pa01_outcome = None if _pa01_contract_created else _pa01_structured_terminal_outcome(
                tool_results_log, _pa01_expected_tool,                    # NEW arg (pass 4, §4.2f)
            )
            _pa01_capable = (
                _pa01_contract_created  # row 2 short-circuits capability entirely — see §4.0's matrix note
                or contract_capable_this_turn(route, identity, ctx)
            )
        except Exception as exc:
            # Fail-safe degraded (decision 5): cannot verify state -> block,
            # never let an unverified reply through. Distinct log marker.
            logger.error(
                "[PA-01] PA01_ENFORCEMENT_ERROR error_type=%s user=%s",
                type(exc).__name__, _sanitize_id(identity.memory_key),
            )
            _pa01_contract_created, _pa01_outcome, _pa01_capable = False, None, True  # forces the Phantom row, not silently ignored

        # Matrix row 2 — a contract for THIS intent's own expected tool genuinely
        # exists: nothing to do, Gateway's own message already stands. A contract
        # for a different tool the agent happened to call this turn does not
        # satisfy this row (pass 4) — it falls through exactly like no contract.
        if not _pa01_contract_created:
            _pa01_response = None
            if not _pa01_capable:
                # Matrix row 5 — capability/permission gap.
                _pa01_response = _PA01_CAPABILITY_UNAVAILABLE_FALLBACK
                _pa01_row = "capability_unavailable"
            elif _pa01_outcome is not None:
                # Matrix row 3 — a real, gate-authored terminal outcome exists.
                _outcome_kind, _outcome_message = _pa01_outcome
                _pa01_response = _outcome_message  # the gate's own text, not agent text (§4.2b)
                _pa01_row = _outcome_kind.lower()
            else:
                # Matrix row 4 — the actual Phantom Approval Prompt case.
                _pa01_response = _PA01_PHANTOM_APPROVAL_FALLBACK
                _pa01_row = "phantom_approval_prompt"

            if _pa01_response is not None:
                logger.warning(
                    "[PA-01] %s state=%s user=%s intent=%s action=%s",
                    _pa01_row, _pa01_state, _sanitize_id(identity.memory_key),
                    getattr(route, "intent", "unknown"),
                    "blocked" if _pa01_state == "enforce" else "would_block",
                )
                if _pa01_state == "enforce":
                    final_reply = _pa01_response
```

**Fail-safe-degraded policy, resolved (extends the prior pass's answer to cover the new signals):** two
different failure surfaces, two different answers, both per decision 5 — (i) failure to determine
`_pa01_contract_required` itself (e.g. `intent_requires_contract_for_success()` raises) → treat as
not-contract-required (matrix row 1), never touches `final_reply`, never raises into the caller; (ii)
failure *after* `_pa01_contract_required` is confirmed `True` (cannot verify capability/contract/outcome
state) → fail-closed to the **Phantom row specifically** (`_pa01_capable` forced `True`,
`_pa01_contract_created`/`_pa01_outcome` forced to the values that select row 4), not the capability row
— deliberate: an enforcement-machinery failure should not be misreported as "your role can't do this"
(a false, specific, and worse claim) when the honest state is "the check itself broke." Logged as
`PA01_ENFORCEMENT_ERROR`, distinct from the normal per-row log lines. This is an intentional asymmetry,
not an inconsistency: the two branches protect different things (availability for
non-contract-required turns vs. a safe, non-misleading failure mode for contract-required turns whose
own state couldn't be verified).

### 4.5 `memory.add()` ordering — exact location

`app.py:2574` (pre-patch baseline) — `memory.add(ctx.memory_key, "assistant", final_reply)`. §4.4's
block is inserted strictly before this line (immediately after the existing `OwnershipSignal` try/except
at `app.py:2560-2571`), so whichever matrix row (§4.0) fires in `"enforce"` mode, `memory.add()` receives
that row's response — `_PA01_PHANTOM_APPROVAL_FALLBACK`, `_PA01_CAPABILITY_UNAVAILABLE_FALLBACK`, or a
gate-authored `terminal_outcome` message — never the original agent text for any of them. The agent's
own conversation memory never contains a claim it didn't actually get to make to the user, regardless of
*which* row replaced it. Verified in the pre-patch baseline that nothing else reassigns `final_reply`
between the `sanitize_agent_response()` call (`app.py:2506`) and `return final_reply` (`app.py:2602`) —
the new block is the only additional writer, and it runs before the one read that matters
(`memory.add()`).

**Why this does not duplicate the approval runtime:** the only new reads are `route.intent`/
`route.handler` (via `intent_requires_contract_for_success()`/`contract_capable_this_turn()`, §3.5/§3.6
— imported functions, not duplicated policy), `ctx.allowed_tools` (already built once per turn by
`build_context()`), `identity` (already resolved this turn), and `tool_results_log` (already accumulated
this turn, now carrying two extra keys per §4.2a/b). Zero new queries, zero new writes beyond replacing
a local string variable, zero interaction with `ActionContract`/`ActionGateway`/`propose_action()` — the
matrix only reads what other gates already computed or recorded this same turn; it never calls into the
Gateway itself, and never calls `enforce()`/`enforce_leads_write_gate()` a second time (it reads their
*already-recorded outcomes* from `tool_results_log`, per §4.2b, not their live behavior again).

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
  recognizes at all, so `is_hijack` is `False` too), intent is `Intent.CREATE_TASK` for an `owner`
  identity (contract-required *and* capable, §3.5/§3.6), zero `tool_use` emitted, no
  `__approval_queued__` sentinel with a `contract_id` present, no `structured_terminal_outcome` →
  assert `BLOCK_PHANTOM is True` and, in `=enforce` mode, `final_reply ==
  _PA01_PHANTOM_APPROVAL_FALLBACK`, **while asserting `is_hijack is False` on the same turn** (both
  assertions in the same test, so a future edit that accidentally reintroduces an `is_hijack`/text
  dependency into `BLOCK_PHANTOM`'s computation fails this test immediately).

**§3.5 policy regression (pass 2's false positive — draft/conversational intents):**
- [ ] **`DRAFT_EMAIL` with zero `tool_use`** ("here's a draft: ...") →
  `intent_requires_contract_for_success` is `False` (§3.5 — excluded from
  `_CONTRACT_REQUIRED_INTENT_TO_TOOL`) → the matrix never leaves row 1 → `final_reply` passes through
  unchanged in `=enforce` mode.
- [ ] **`DRAFT_MESSAGE` with zero `tool_use`** — same shape and assertion as `DRAFT_EMAIL`.
- [ ] **An intent not in `_CONTRACT_REQUIRED_INTENT_TO_TOOL` (e.g. `QUALIFY_LEAD`) where a tool call
  *does* succeed this turn** → `intent_requires_contract_for_success` is `False`, matrix stays at row 1
  regardless of `tool_results_log` contents → `final_reply` unaffected either way.
- [ ] **`Intent.UNKNOWN` and any `_READ_ONLY_INTENTS` member** (e.g. `Intent.ASK_QUESTION`) → neither is
  in `_NORMAL_INTENTS` at all, so `intent_requires_contract_for_success()` returns `False` trivially →
  unaffected, `=enforce` mode included.

**§3.6 capability regression — the correction this pass exists to make (the user's 7 required cases,
verbatim):**
- [ ] **`owner` + `CREATE_TASK` + `airtable_add` available (`owner`'s `_ROLE_TOOLS` includes it,
  `tool_registry.check_allowed("airtable_add", owner)` is `True`) + zero `tool_use`** → matrix row 4 →
  `=enforce` replaces `final_reply` with `_PA01_PHANTOM_APPROVAL_FALLBACK`. (Same case as the
  decision-7 test above, restated here as the first of the user's 7 literal cases for direct
  traceability.)
- [ ] **`owner` + `CREATE_TASK` + a real `ActionContract`** (`tool_use` emitted, `__approval_queued__`
  sentinel with a non-`None` `contract_id`) → matrix row 2 → `final_reply` is `_queue_approval()`'s own
  Gateway prompt (`app.py:863`), untouched, `=enforce` mode included.
- [ ] **`guest` + `CREATE_TASK` + `airtable_add` NOT in `guest`'s `ctx.allowed_tools`**
  (`context.py:72` — `Role.GUEST: set()`) + zero `tool_use` → `contract_capable_this_turn` is `False` →
  matrix row 5 → `=enforce` replaces `final_reply` with `_PA01_CAPABILITY_UNAVAILABLE_FALLBACK`, **not**
  `_PA01_PHANTOM_APPROVAL_FALLBACK`. Precondition to state in the test: `guest`+`CREATE_TASK` reaches
  `Handler.AGENT` at all (`risk_router.detect_risk()`'s external-role branch, `risk_router.py:103-104`),
  so the turn genuinely reaches PA-01's gate rather than being blocked earlier.
- [ ] **`employee` + `UPDATE_TASK` + `airtable_update` NOT in `employee`'s `ctx.allowed_tools`**
  (`context.py:65-68` — only `calendar_get_events`/`airtable_get`, both read-only) + zero `tool_use`,
  domain = `general`/`crm` (so the turn reaches `Handler.AGENT`, not `Handler.APPROVAL`, per
  `risk_router.py`'s domain-gating for `employee`) → same assertion as the `guest` case:
  `_PA01_CAPABILITY_UNAVAILABLE_FALLBACK`, not the Phantom fallback.
- [ ] **A tool call rejected via `ToolDenied`** (`app.py:2352-2358` — force this by having
  `contract_capable_this_turn` be `True` upfront but `enforce()` deny anyway, simulating the §3.6
  point-2 drift between `context.py`'s `_ROLE_TOOLS` and `tool_registry.py`'s `roles_allowed`) →
  `tool_results_log` carries a `"terminal_outcome": "PERMISSION_DENIED"` entry (§4.2b) → matrix row 3 →
  `=enforce` replaces `final_reply` with that entry's own `content` (the real `ToolDenied` message),
  **not** the Phantom fallback.
- [ ] **A preflight block** (`LeadsDirectWriteBlocked` from `enforce_leads_write_gate()`,
  `app.py:2369-2378` — e.g. an `airtable_add` call targeting the Leads table that the preflight gate
  rejects) → `tool_results_log` carries a `"terminal_outcome": "PREFLIGHT_BLOCKED"` entry (§4.2b) →
  matrix row 3 → `=enforce` replaces `final_reply` with that entry's own `content`, **not** the Phantom
  fallback.
- [ ] **A non-contract intent** (any of the five in §3.5's non-contract-required set, or any
  `_READ_ONLY_INTENTS`/`UNKNOWN`) → unaffected regardless of role/capability/tool outcome — restates the
  §3.5 policy-regression bullets above as the user's 7th literal case.

**§4.0 tool-scoping regression (new this pass, the user's 5 required cases, verbatim):**
- [ ] **`owner` + `CREATE_TASK` + a real contract of `airtable_add`** (`tool_use` emitted for
  `airtable_add`, `__approval_queued__` sentinel with `contract_id` set and `action_tool="airtable_add"`)
  → `expected_tool_for_intent(CREATE_TASK) == "airtable_add"` matches → `contract_created_for_expected_tool`
  is `True` → matrix row 2 → `final_reply` is `_queue_approval()`'s own Gateway prompt, untouched,
  `=enforce` mode included.
- [ ] **`owner` + `CREATE_TASK` + a real contract of `calendar_create_event`** (agent misfires and calls
  the wrong tool; sentinel has `contract_id` set but `action_tool="calendar_create_event"`) → does
  **not** satisfy `contract_created_for_expected_tool` for `CREATE_TASK` (`"calendar_create_event" !=
  "airtable_add"`) → matrix does not reach row 2 for this intent — falls through to row 3/4/5 exactly as
  if no contract existed. With no other `tool_results_log` entry for `airtable_add` and a capable
  identity, this resolves to row 4 (Phantom fallback) — asserting that a contract for the wrong tool is
  worth nothing to this intent's own check.
- [ ] **`owner` + `CREATE_TASK` + `PERMISSION_DENIED` tagged against an unrelated tool** (e.g. a
  `ToolDenied` entry with `"tool": "gmail_send_draft"`, unrelated to this turn's `CREATE_TASK` request) →
  `_pa01_structured_terminal_outcome(tool_results_log, "airtable_add")` skips it (`entry_tool !=
  expected_tool`) → `structured_terminal_outcome` is `None` for this intent → does not suppress the
  Phantom check — if capable, no `contract_created_for_expected_tool`, and no matching outcome, matrix
  resolves to row 4 (Phantom fallback), not row 3.
- [ ] **`owner` + `CREATE_TASK` + `PREFLIGHT_BLOCKED` tagged against `airtable_add`** (a real
  `LeadsDirectWriteBlocked` entry with `"tool": "airtable_add"`, matching `expected_tool`) → the lookup
  matches → matrix row 3 → `=enforce` replaces `final_reply` with that entry's own `content` — a valid,
  in-scope terminal outcome, contrasted directly with the unrelated-tool case above.
- [ ] **Multiple `tool_results_log` entries in one turn** (e.g. an unrelated `gmail_draft` denial *and* a
  genuine `airtable_add` contract, both present) → only the entry whose tool identity (`"tool"` directly,
  or `"action_tool"` for the sentinel) equals `expected_tool_for_intent(route.intent)` is ever selected
  by either `contract_created_for_expected_tool` or `_pa01_structured_terminal_outcome` — the unrelated
  entry is present in the log (for A32/telemetry purposes) but structurally invisible to this intent's
  matrix evaluation.

**Additional regression, must-pass:**
- [ ] The **false-negative fix** from §4.1 (still valid, restated for the new predicate): identity has
  an unrelated pre-existing pending contract (e.g. a Gmail draft) *and* this turn fabricates an
  unrelated phantom claim for a contract-required intent with zero `tool_use` and no `contract_id` for
  **this turn's** intent → `=enforce` still replaces `final_reply` with the Phantom fallback, because
  `contract_created_for_expected_tool` is computed from `tool_results_log` (turn-scoped **and**
  tool-scoped, pass 4) and finds nothing matching `expected_tool` — not fooled by an unrelated live
  contract belonging to a different request or a different tool.
- [ ] **`APPROVAL_QUEUE_ERROR` regression (new this pass, §3.6):** `_queue_approval()` returns a
  duplicate-fingerprint-blocked or cross-channel-duplicate-suppressed string (`app.py:753-757`/
  `766-772`) → the `__approval_queued__` sentinel now carries `"terminal_outcome": "APPROVAL_QUEUE_ERROR"`
  and `"ok": False` (§4.2a) → matrix row 3 → `=enforce` replaces `final_reply` with that sentinel's own
  `content` (the accurate "⚠️ פעולה זו כבר בוצעה לאחרונה..." text) — **not** the generic Phantom
  fallback, which would be a strictly less accurate message for this case.
- [ ] **Known, accepted limitation — a genuine free-text clarifying question for a contract-required
  intent with zero `tool_use`**, for a *capable* identity (e.g. "איזה משימה, X או Y?" for `owner` +
  `CREATE_TASK`, where the router did *not* classify `Handler.CLARIFY`) → `contract_capable_this_turn`
  is `True`, no `structured_terminal_outcome`, no contract → matrix row 4 → `final_reply` **is
  replaced** by the Phantom fallback, even though the agent's text was a legitimate question. Assert
  this explicitly. Unchanged from pass 2 — this trade-off is about matrix row 4 specifically and is
  orthogonal to this pass's capability fix (which only ever redirects *incapable* turns to row 5,
  never removes row 4 for capable ones).
- [ ] A pending action from a **prior** turn continues to resolve correctly on "מאשר" — unaffected,
  since PA-01 only touches the tool-loop-fallthrough path, never the confirm-word early-return path.
- [ ] `test_turn_envelope.py` (74 assertions) and `test_pending_contract_read_amplification.py`
  (6 assertions) remain green unmodified — PA-01 must not alter `OwnershipSignal`/`detect_case_c2_signal`
  themselves, only add a new consumer of `tool_results_log`/`route`/`ctx`/`identity` that does not touch
  either.
- [ ] `set(_CONTRACT_REQUIRED_INTENT_TO_TOOL) <= _NORMAL_INTENTS` (§3.5's own sanity assertion) is
  itself asserted in the test file.
- [ ] For all 10 `_CONTRACT_REQUIRED_INTENT_TO_TOOL` entries, the mapped tool name is itself a real key
  in `tool_registry.py`'s `_REGISTRY` with `requires_approval=True` — a parametrized test over the dict,
  catching drift if either file changes independently.
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
   8's graduation criteria are met, verbatim, extended this pass with two new capability-layer criteria:
   - [ ] At least **7 days** of continuous `"shadow"` operation.
   - [ ] At least **50 contract-required-intent turns or replays** (i.e. `route.intent` in
     `_CONTRACT_REQUIRED_INTENT_TO_TOOL`, §3.5 — not the broader former `_NORMAL_INTENTS`) observed in
     the shadow log during that window (a sample too small to trust a false-positive rate from).
   - [ ] **Zero** blocks of a real approval (matrix row 2 — `contract_created_for_expected_tool` would
     have been `True`) logged as if it were row 4/5. Any such event found is a bug in §4.0's matrix and
     must be fixed before graduating, not accepted as noise.
   - [ ] **Zero** cases where a contract or terminal outcome for a *different* tool than
     `expected_tool_for_intent(route.intent)` was observed to affect the row selected for a
     contract-required intent (pass 4's tool-scoping fix, §4.0/§4.2f) — any such event is a bug in the
     scoping logic itself.
   - [ ] **Zero** blocks of a `DRAFT_EMAIL`/`DRAFT_MESSAGE`/`QUALIFY_LEAD`/`UPDATE_EVENT`/`STORE_MEMORY`
     turn (§3.5's non-contract-required set). Structurally unreachable by construction
     (`intent_requires_contract_for_success` is `False` for all five, matrix row 1) — recorded as an
     explicit graduation gate anyway, to catch a future edit that accidentally moves one of these five
     into `_CONTRACT_REQUIRED_INTENT_TO_TOOL` without re-verifying §3.5's reasoning first.
   - [ ] **NEW — a sample of matrix row 5 (`capability_unavailable`) events, manually reviewed, confirm
     the identity genuinely lacked the tool** (cross-checked against `context.py`'s `_ROLE_TOOLS` and
     `tool_registry.py`'s `roles_allowed` directly, not just trusted from the log) — catches a bug in
     `contract_capable_this_turn()`'s own three-part check before it ships broadly to every `employee`/
     `lead`/`guest`/`readonly` identity.
   - [ ] **NEW — zero unexplained `PERMISSION_DENIED`/`PREFLIGHT_BLOCKED` volume spikes** relative to
     each gate's own pre-PA-01 baseline rate (both gates already existed and already fired before this
     patch — §3.6 only makes their outcomes visible to `tool_results_log`, it does not change how often
     `enforce()`/`enforce_leads_write_gate()` themselves deny). A spike would indicate `contract_capable_
     this_turn()`'s upfront check is systematically wrong in the "looks capable but isn't" direction.
   - [ ] **Manual review** of every `would_block`-shaped shadow event (rows 3/4/5 combined) from the
     window — not just the aggregate rate — specifically to catch the §5 "known limitation" case
     (legitimate free-text clarifying questions on a *capable* contract-required intent, §7) at real
     observed volume, since that case is accepted as a trade-off in the abstract but its actual
     frequency is unmeasured until shadow data exists.
   - [ ] All §5 regression tests passing, including the decision-7 test, the 7 capability-layer tests,
     and the "known, accepted limitation" test, on the commit being graduated.
   Graduation requires all eight, not a subset.
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

- **Structural false positive #1 (pass 2), closed — recorded so its reasoning is not lost.** Pass 1's
  predicate used `route.intent in _NORMAL_INTENTS`, which included `DRAFT_EMAIL`, `DRAFT_MESSAGE`,
  `QUALIFY_LEAD`, and `STORE_MEMORY` — intents with a legitimate, common, zero-`tool_use` fulfillment
  shape (§3.5). Fixed by `intent_requires_contract_for_success()`, sourced from the narrower
  `_CONTRACT_REQUIRED_INTENT_TO_TOOL` (10 of the 15 former `_NORMAL_INTENTS` members).
- **Structural false positive #2 (pass 3, this pass), closed.** Pass 2's `approval_contract_expected`
  still assumed a contract-required intent could always reach a contract for *any* identity — ignoring
  that `employee`/`lead`/`guest`/`readonly` are never even offered the relevant write tool
  (`context.py`'s `_ROLE_TOOLS`, §3.6), and that `enforce()`/`enforce_leads_write_gate()`/queueing itself
  can still deny or decline mid-turn for legitimate, structural reasons unrelated to a phantom claim.
  Fixed by splitting the single boolean into `contract_capable_this_turn` (§3.6) and
  `structured_terminal_outcome` (§3.6), and the 5-row decision matrix (§4.0) that routes each case to
  its own, accurate response instead of the generic Phantom fallback. Recorded here, not as a residual
  risk, but as the reason the matrix has 5 rows instead of 2.
- **Structural false positive #3 (pass 4, this pass), closed.** Pass 3's `contract_created`/
  `structured_terminal_outcome` matched *any* tool's contract or terminal outcome present in
  `tool_results_log` this turn, not specifically the one the intent's own `expected_tool_for_intent()`
  names — so a contract or denial belonging to an unrelated tool the agent also touched this turn could
  wrongly satisfy matrix row 2 or row 3 for a *different* intent. Fixed by scoping both signals to
  `expected_tool`: the sentinel now carries `"action_tool"` (§4.2a) and `_pa01_structured_terminal_
  outcome()` takes `expected_tool` as a required argument (§4.2f), renamed to
  `contract_created_for_expected_tool` to state the invariant in the name itself.
- **Narrowed, still-real risk — legitimate free-text agent clarifying questions on *capable*
  contract-required turns will be blocked/replaced (matrix row 4), not just phantom claims.** §4.0's
  matrix is deliberately strict per decision 2: for a contract-required, *capable* turn, only a
  router-classified `Handler.CLARIFY` may return a clarifying question — any other clarifying text the
  agent generates itself (e.g. "איזה משימה, X או Y?" for `owner` + `CREATE_TASK`, zero `tool_use`) has
  `contract_created_for_expected_tool=False` and no `structured_terminal_outcome`, landing on row 4
  exactly like an actual phantom claim. This risk is unchanged by this pass's capability fix — it is orthogonal: the capability
  fix only ever redirects *incapable* turns away from row 4 to row 5; it does nothing for capable turns
  where the agent is genuinely asking a legitimate question. Not measured yet — this is exactly what
  §6's manual-review graduation criterion exists to quantify before `"enforce"` ships. If shadow data
  shows this fires often, the resolution is a router fix (widen `intent_router.py`'s ambiguous-phrase
  detection so more clarifying-question shapes flow through `Handler.CLARIFY` structurally), not a
  regression back to a text-pattern carve-out inside PA-01's own predicate.
- **False positives blocking a legitimate agent reply (phantom-claim-shaped, matrix row 4 specifically),
  within the 10 contract-required intents, for capable identities.** Mitigated by the shadow phase
  (step 2) — the matrix has no text-based escape hatch by design, so this is measured empirically via
  shadow data.
- **Two structured-terminal-outcome branches (§3.6) reuse gate-authored text (`str(ToolDenied(...))`,
  `str(LeadsDirectWriteBlocked(...))`, `_queue_approval()`'s own dedup/error strings) as the row-3
  response, instead of a fixed PA-01 constant.** This is a deliberate accuracy-over-consistency choice
  (§4.3) — these messages are already specific and correct (e.g. name the exact table/reason) where a
  generic constant would be strictly worse — but it means row-3 responses are not fully predictable from
  this document alone; a wording change to `ToolDenied`/`LeadsDirectWriteBlocked`/`_queue_approval()`'s
  own messages automatically changes what PA-01 shows, without touching PA-01's own code. Worth a doc
  comment cross-reference at each site when implementation happens, so a future editor of those messages
  knows PA-01 now also surfaces them directly to the user, not just to logs.
- **`_CONTRACT_REQUIRED_INTENT_TO_TOOL`/`_NON_CONTRACT_NORMAL_INTENTS` (§3.5) is a new policy surface
  that must be kept in sync with `_NORMAL_INTENTS` and with the dispatcher's actual tool set.** A future
  new intent added to `_NORMAL_INTENTS` without also classifying it in §3.5's table is a silent gap — it
  defaults to "not contract-required" (the `in` check on a dict that doesn't contain it), i.e. **the
  fail-safe direction for an unclassified new intent is "not contract-required," not
  "contract-required."** Same fail-safe-degraded asymmetry as decision 5's turn-level policy, one level
  up at the intent-catalog level.
- **Three of the five non-contract-required intents (`UPDATE_EVENT`, `DRAFT_MESSAGE`, `STORE_MEMORY`)
  have no backing tool at all** — a separate, pre-existing gap (§3.5) this pass found but does not fix:
  the agent has no way to actually fulfill these requests through any registered tool, regardless of
  PA-01. Worth its own backlog item; out of PA-01's scope.
- **Two pieces of new user-facing copy, both now approved wording, not a "no UX change" patch.**
  `_PA01_PHANTOM_APPROVAL_FALLBACK` (§4.3a, decision 4, pass 1) and `_PA01_CAPABILITY_UNAVAILABLE_
  FALLBACK` (§4.3b, decision 7, pass 4) are both new strings with owner-approved exact wording — neither
  is open for further revision at the planning stage; still worth flagging here since two new strings
  reaching production users is a real UX surface, even with wording already settled.
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

This document is the complete Planning Gate deliverable for PA-01 through four corrections: pass 1
replaced the rejected `is_hijack`-as-trigger design with a state-only structural mechanism; pass 2 fixed
a structural false positive treating draft/conversational intents as contract-required; pass 3 fixed a
second structural false positive — treating every contract-required intent as if a contract could be
created by *any* identity, ignoring role-based tool availability and mid-turn denial/preflight gates;
pass 4 (this edit) fixes a third structural false positive — `contract_created`/`structured_terminal_outcome`
matching *any* tool's contract or outcome in `tool_results_log`, not specifically the intent's own
expected tool, which could hide a genuine Phantom case behind an unrelated tool call in the same turn.
No code has been written, no branch opened — **אין לממש עדיין** remains in force. Direct answers to the
required return items:

**Sentinel structure, final (§4.2a):** the `__approval_queued__` entry now carries five keys —
`"tool": "__approval_queued__"` (fixed literal, unchanged), `"content"` (the Gateway's own message,
unchanged), `"ok"` (pass 3: real success/failure, no longer hardcoded `True`), `"contract_id"` (pass 2:
the real id from `_gw_result.contract_id`), `"terminal_outcome"` (pass 3: `None` on success, else
`"APPROVAL_QUEUE_ERROR"`), and `"action_tool"` (**new, pass 4**: `tu.name` — the real tool call that
produced this contract, read from the same `tu` object `enforce()` was already called with a few lines
earlier, never guessed from `route.intent`). The two other tagged sites (`ToolDenied`,
`LeadsDirectWriteBlocked`, §4.2b) needed no new key — their existing `"tool": tu.name` already names the
real tool directly.

**Predicate, scoped by `expected_tool` (§4.0):**
```
expected_tool                         := expected_tool_for_intent(route.intent)                # §3.5
intent_requires_contract_for_success  := intent_requires_contract_for_success(route.intent)    # §3.5
contract_capable_this_turn            := contract_capable_this_turn(route, identity, ctx)      # §3.6

contract_created_for_expected_tool    := any(
    r.get("tool") == "__approval_queued__"
    and r.get("contract_id")
    and r.get("action_tool") == expected_tool
    for r in tool_results_log
)

structured_terminal_outcome           := _pa01_structured_terminal_outcome(tool_results_log, expected_tool)
                                          # scoped: r["tool"]==expected_tool for direct entries,
                                          # r["action_tool"]==expected_tool for the sentinel

BLOCK_PHANTOM := intent_requires_contract_for_success and contract_capable_this_turn
                 and not contract_created_for_expected_tool and not structured_terminal_outcome
```
`contract_created` is renamed to `contract_created_for_expected_tool` — not a cosmetic rename, the name
now states the invariant it enforces: a contract for a *different* tool than the intent's own
`expected_tool` (e.g. `calendar_create_event` when the intent was `CREATE_TASK`, expecting
`airtable_add`) no longer satisfies matrix row 2 at all; it is treated exactly as if no contract existed
for this intent, and the matrix falls through to whichever of rows 3-5 the real state resolves to. The
full 5-row response table (§4.0) is otherwise unchanged in shape from pass 3.

**Terminal-outcome lookup, scoped (§4.2f):** `_pa01_structured_terminal_outcome()` now takes
`expected_tool` as a required second argument and skips any entry whose own tool identity doesn't match
it — computed as `r.get("action_tool")` when `r["tool"] == "__approval_queued__"` (the sentinel), else
`r.get("tool")` directly (the two other tagged sites already carry the real name). Pass 3's version
returned the *first* `terminal_outcome` in the log unconditionally; pass 4 requires a match first, so an
unrelated `PERMISSION_DENIED` earlier in the same turn (e.g. from a different tool the agent also
touched) can no longer suppress a genuine Phantom block for the intent actually being evaluated.

**Capability wording, approved (decision 7):** `_PA01_CAPABILITY_UNAVAILABLE_FALLBACK` is updated to
`"לא ניתן לבצע את הפעולה הזו דרך החשבון הנוכחי. לביצוע, יש לפנות למנהל מורשה."` — this supersedes pass
3's draft text and is no longer flagged as pending owner sign-off for wording (§4.3).

**Verdict: PASS.** This pass's correction is state-only and duplication-free, same as the prior three: no
new signal source is introduced — `action_tool` is read from the same `tu` object already in scope at the
sentinel's existing append site, and the scoping comparison reuses `expected_tool_for_intent()` (§3.5,
already canonical, no second definition). The result closes a real cross-tool misattribution (a contract
or denial for tool A no longer covers an intent whose canonical tool is B) without touching
`intent_requires_contract_for_success`, `contract_capable_this_turn`, or any of pass 1-3's already-closed
findings. §5 carries all 5 of the user's required tool-scoping regression cases (matching contract passes,
mismatched contract falls through, unrelated denial ignored, matching preflight block honored, multiple
log entries resolve to only the matching one) plus a restated false-negative test now asserting
tool-scoping specifically. §6/§7 need no further change this pass — the rollout gating and risk register
already covered "wrong contract/outcome attribution" only implicitly via the general accuracy criteria;
no new graduation criterion or open risk is introduced, since this is a closed correctness fix to an
already-planned mechanism, not a new capability. No further correction is required before implementation
may begin. OH-01/OS-01/RC-01 remain out of scope until their own planning gates, per the approved order.

---

## 8. Implementation notes (post-approval, commit 81676ad → implementation)

Per this document's own minimal-update rule: recorded here only because real line numbers/implementation
details differ from what §4 sketched — no planning decision changed, no new signal, no new policy source.

**§4.2(a)'s `_gw_result`-in-scope assumption was wrong.** The plan's sketch read `_gw_result` directly at
the tool-loop's `__approval_queued__` append site, assuming it was already in scope there. In the real
code, `_gw_result` is local to `_queue_approval()` (`app.py`, pre-implementation ~line 767) — the tool
loop only ever received `_queue_approval()`'s plain `str` return, never the Gateway result object.
Fix: `_queue_approval()`'s body was renamed to `_queue_approval_detailed()`, returning a dict
(`{"message", "contract_id", "ok", "terminal_outcome"}`) instead of a bare string; `_queue_approval()`
itself became a one-line wrapper (`return _queue_approval_detailed(...)["message"]`) preserving the
exact string-returning contract two existing tests already depend on directly
(`test_bug_canonical_tool_wiring.py`, `test_bug_batch_approval_preserved.py`) and that
`_promote_next_batch_item()` (`app.py`, discards the return value) already relies on implicitly. The
tool loop's approval-gate branch now calls `_queue_approval_detailed()` and builds the sentinel from its
four fields directly, plus `"action_tool": tu.name` (from the real `tool_use` block, exactly per
decision 4/requirement 4 — never from the dict).

**§4.2(a)'s `"ok"`/`"terminal_outcome"` formula (`bool(contract_id)`) does not hold on every branch.**
Applying it uniformly would have mis-classified the owner-notify-failure branch: `propose_action()` can
already have created a real `contract_id` by that point (enforce-mode `FEATURE_ACTION_GATEWAY`), yet the
user was never actually notified — a practically-broken, orphaned contract, not a usable one. Fix: each
of `_queue_approval_detailed()`'s five early-return branches (duplicate fingerprint, cross-channel
duplicate, Gateway rejection, persistence failure, owner-notify failure) explicitly sets
`"ok": False, "terminal_outcome": "APPROVAL_QUEUE_ERROR", "contract_id": None` — matching §3.6's own
branch-by-branch classification (which already listed owner-notify failure under `APPROVAL_QUEUE_ERROR`)
rather than re-deriving it from `contract_id` truthiness. Only the genuine success return (end of the
function) uses the `bool(contract_id)`-based formula, where it is valid.

**Undefined-variable guard added.** `_gw_result = None` is now initialized before the
`FEATURE_ACTION_GATEWAY` if/else in `_queue_approval_detailed()` — the shadow-mode branch's
`except Exception` can leave `_gw_result` unassigned before the function reaches its success return,
which would otherwise raise `NameError` instead of completing the (correct, existing) shadow-mode
non-blocking behavior.

**Real line numbers** (post-implementation, this branch): `_PA01_PHANTOM_APPROVAL_FALLBACK`/
`_PA01_CAPABILITY_UNAVAILABLE_FALLBACK`/`_pa01_structured_terminal_outcome()` — `app.py` module scope,
immediately after `AGENT_TIMEOUT`. `_queue_approval()`/`_queue_approval_detailed()` — `app.py`, where
`_queue_approval()` previously stood. `ToolDenied`/`LeadsDirectWriteBlocked` catches and the
`__approval_queued__` sentinel — `app.py`'s tool loop, unchanged relative position. The PA-01 matrix
block itself — `app.py`, immediately after the `OwnershipSignal` try/except, immediately before
`memory.add()`, exactly as §4.4/§4.5 specified. `_CONTRACT_REQUIRED_INTENT_TO_TOOL`,
`intent_requires_contract_for_success()`, `expected_tool_for_intent()`, `contract_capable_this_turn()` —
`core/router/risk_router.py`, between `_NORMAL_INTENTS` and `_HIGH_RISK_INTENTS`, exactly as §4.2(d)/(e)
specified. `get_pa01_enforcement_state()` — `feature_flags.py`, alongside the two existing three-state
accessors, exactly as §4.2(c) specified.

**Main Integration Pass finding (merge commit 8fb0d0c → canonical-tool-wiring fix, commit follows this
edit): `action_tool` must be the CANONICAL tool, not `tu.name`.** `_queue_approval_detailed()` calls
`resolve_canonical_tool(tool_name, tool_inputs, user_text)` (`app.py`, BUG-CANONICAL-TOOL-WIRING, existing
since before PA-01) *before* computing the fingerprint, the label, the EventBus payload, and the
`ActionGateway` contract itself — so the `tool_name` local variable inside that function, from that point
on, is the resolved canonical tool (e.g. `airtable_add`), which can differ from the raw `tool_use` block's
own name the model called (e.g. `sheets_append`). The first implementation pass had the tool loop's
sentinel read `"action_tool": tu.name` — the pre-canonicalization name — at the call site, not the
canonical one `_queue_approval_detailed()` actually used to create the contract. Concretely:
`route.intent = CREATE_TASK` (`expected_tool = airtable_add`), `tu.name = sheets_append`,
`resolve_canonical_tool(...)` rewrites it to `airtable_add`, the real `ActionContract.tool_name` is
`airtable_add` — but the sentinel recorded `action_tool = sheets_append`, so
`contract_created_for_expected_tool` (§4.0) would incorrectly evaluate `False` for a turn that in fact
had a real, correctly-scoped contract, risking PA-01 overwriting a genuine Gateway Approval Prompt with
the Phantom fallback. **Fixed:** `_queue_approval_detailed()`'s return dict gained a fifth key,
`"action_tool"`, set to the post-canonicalization `tool_name` on every return branch (including all five
early-return/non-success branches, since canonicalization happens once, at the top of the function, before
any of them) — never inferred from `contract_id`, never recomputed at the call site. The tool loop's
sentinel now reads `"action_tool": _approval_outcome["action_tool"]`, not `tu.name`. `tu.name` itself is
not surfaced anywhere in the sentinel — no `requested_tool` telemetry field was added, per instruction 3.
This is, like the other Main Integration Pass corrections, a plumbing-level fix: it does not touch
`intent_requires_contract_for_success`, `contract_capable_this_turn`, the matrix, the sentinel's other four
keys, or any approved wording — it only corrects which tool identity the fifth key (`action_tool`, added in
this same implementation) actually carries, so that it means what §4.0's scoping was always meant to check
against: *the tool the contract was actually created for*, not *the tool name the model happened to type*.

**Historical note on the pre-Main-Integration-Pass state:** before this correction, `tu.name` and the
canonical tool coincided in every test case exercised prior to the Main Integration Pass (none of them
triggered `resolve_canonical_tool()`'s rewrite branch), which is why the gap was not caught until the
integration pass's own review deliberately traced `_queue_approval_detailed()`'s internal canonicalization
step against the sentinel's construction site. Restated per instruction 4: the source of truth for
`action_tool` was never, and is not now, an inference from `route.intent` — it is the exact tool name that
was actually used to create the `ActionContract`, read directly from `_queue_approval_detailed()`'s own
return value.

**Follow-up finding: `contract_id` presence ≠ creation this turn.** The Main Integration Pass's own
review found a second, related gap in the same area: `ActionGateway.propose_action()` returns a real,
non-`None` `contract_id` not only on genuine creation (`GatewayResult(ok=True, ...)`, always immediately
after saving a brand-new `ActionContract`) but also on several *rejection/dedup* paths — an existing
`"pending"` contract for the same fingerprint, an existing `"approved"`/`"executing"`/`"outcome_unknown"`
one — all returned as `GatewayResult(ok=False, contract_id=existing.contract_id, ...)`. Row 2's original
condition (`contract_id` truthy + `action_tool` match) did not check `ok`/`terminal_outcome` at all, so a
rejected/duplicate lookup's `contract_id` could satisfy row 2 exactly like a genuine creation — silently
leaving whatever the agent said unreplaced instead of correctly firing row 3 with the accurate rejection
message. **Fix:** `_queue_approval_detailed()`'s return dict gained a sixth key, `"created_this_turn"`,
set per-branch (`True` only on the final success return, and there specifically from
`bool(_gw_result and _gw_result.ok)` — never from `contract_id` truthiness, since shadow mode's own
success-shaped return can also carry a pre-existing `contract_id` when the underlying proposal was itself
a dedup that shadow mode doesn't block on). Row 2's predicate is now: `tool == "__approval_queued__" and
ok is True and terminal_outcome is None and created_this_turn is True and contract_id and
action_tool == expected_tool` — all five required, extracted into its own function,
`_pa01_contract_created_for_expected_tool()`, mirroring `_pa01_structured_terminal_outcome()`'s existing
pattern (both now full-log scans, never first-entry-only, verified explicitly against a batch turn where
the expected tool's sentinel is the second `tool_results_log` entry). Every other branch (duplicate
fingerprint, cross-channel duplicate, Gateway rejection/dedup, persistence failure, owner-notify failure)
already set `ok=False`/`terminal_outcome="APPROVAL_QUEUE_ERROR"`, so `created_this_turn=False` on those
branches is consistent with, not a change to, their existing classification — only the previously-missing
row-2 gate condition was added. **Exception normalization, added at the same time:** `_queue_approval_
detailed()` is now a thin wrapper around a renamed `_queue_approval_detailed_impl()`, catching any
exception from EventBus/dedup/Gateway/owner-notification operations and returning the same uniform
6-key, fail-closed shape (`ok=False`, `contract_id=None`, `terminal_outcome="APPROVAL_QUEUE_ERROR"`,
`created_this_turn=False`) — no branch, expected or exceptional, can leave the tool loop to guess a shape
from a raw exception.

**No deviation from any of decisions 1-13** (the approved implementation instructions), nor from either
the Main Integration Pass instructions or this follow-up correction's own instructions — every deviation
recorded in this §8 is a plumbing-level correction to how the sketch/earlier passes accessed or
propagated already-correct state, not a change to the predicate's *shape* (still the same 5-row matrix),
the policy source, the sentinel's required *keys* (this round adds one — `created_this_turn` — but does
not remove or repurpose any existing one), the matrix's rows, or the approved wording.

**Codex re-audit of commit `b7eb2bb` (verdict: `FIX_REQUIRED`) — return state must match canonical
state.** A third review found that `_queue_approval_detailed()`'s return value could still disagree with
the *actual* durable/EventBus/batch-queue state in three concrete ways, none of them covered by the
`created_this_turn` fix above (which only handles `propose_action()`'s own *structured*
`GatewayResult(ok=False, ...)` returns, not exceptions, not batch-deferred calls, and not failures that
happen *after* a contract is already saved).

- **P1-A — a real exception from `propose_action()`, not a structured `GatewayResult` failure.** The
  shadow-mode branch (`FEATURE_ACTION_GATEWAY` off) wrapped its `propose_action()` call in a bare
  `try/except Exception` that logged at `DEBUG` and fell straight through to `bus.request_approval()`,
  treating an unhandled bug/exception identically to "nothing happened, proceed with the legacy path."
  This produced a real legacy `EventBus` pending item with **no** canonical `ActionContract` behind it,
  and — because `_gw_result` stayed `None` — a message that still read `"⏳ הפעולה ממתינה לאישור"` even
  though no Gateway evidence existed for it at all. **Fix:** the shadow branch's `except Exception` now
  returns the same uniform fail-closed shape used everywhere else (`ok=False`, `contract_id=None`,
  `terminal_outcome="APPROVAL_QUEUE_ERROR"`, `created_this_turn=False`) immediately, and never reaches
  `bus.request_approval()`. Enforce mode (`FEATURE_ACTION_GATEWAY` on) needed no code change: an exception
  there already propagated out of `_queue_approval_detailed_impl()` entirely — skipping
  `bus.request_approval()`, which sits unconditionally *after* the whole `if/else` Gateway block — and was
  already caught only by `_queue_approval_detailed()`'s own outer exception-normalizing wrapper; both
  branches are now covered by regression tests (R2-real) to prove this explicitly rather than by
  inspection alone. This fix is independent of `FEATURE_PA01_ENFORCEMENT_STATE` — it runs inside
  `_queue_approval_detailed_impl()` on every call regardless of PA-01's own state, matching the review's
  explicit requirement that "off" must not excuse a false pending state.

- **P1-B — a batch-deferred expected-tool call was structurally invisible to PA-01.** When a turn's
  *second* mutating tool call hits the pre-existing `BUG-BATCH-DISCARD` deferral
  (`_mutating_approvals_this_turn >= 1` → `event_bus.batch_queue.enqueue(...)`), no `tool_results_log`
  entry was ever appended for it. If that deferred call happened to be the intent's own expected tool
  (e.g. a first `calendar_create_event` call creates a real, live, but *unrelated* contract, and a second
  `airtable_add` call — the `CREATE_TASK` expected tool — is deferred to `batch_queue`), PA-01 saw "no
  contract, no terminal outcome" for `airtable_add` and fell through to the Phantom fallback — a false
  claim, since the action genuinely *is* queued, just not yet promoted into its own live contract. **Fix:**
  the deferral branch now also appends a `tool_results_log` entry:
  `{"tool": "__approval_deferred_batch__", "action_tool": <canonical>, "ok": False, "contract_id": None,
  "terminal_outcome": "APPROVAL_DEFERRED_BATCH", "content": <the same deterministic "נשמר בתור..."
  message already shown to the model>, "created_this_turn": False}`. The canonical tool name is resolved
  via the same `resolve_canonical_tool()` call `_queue_approval_detailed_impl()` will use once this item is
  promoted (see `_promote_next_batch_item()`), so PA-01's expected-tool scoping matches correctly even
  across a Sheets/Drive rewrite. `_pa01_structured_terminal_outcome()`'s `entry_tool` extraction was
  extended to also read `action_tool` for this new sentinel type (previously only `__approval_queued__`),
  so this entry is found by the existing scoped, full-log-scan lookup with no change to the lookup's own
  shape or semantics. `_pa01_contract_created_for_expected_tool()` needed no change — a deferred entry's
  `tool` is never `__approval_queued__`, so it correctly never satisfies row 2. Net effect: a mixed batch
  where the expected tool is deferred now resolves to row 3 (the deferred-batch message), never row 2 and
  never row 4 (Phantom). This does **not** change `batch_queue`'s own mechanics in any way — no tool is
  force-run, no existing contract is cancelled, only a truthful state record is added for PA-01 to read.

- **P1-C — a contract persisted, then a later step (EventBus publish / owner notification) failed,
  leaving an orphan.** Two spots in `_queue_approval_detailed_impl()` run *after* `propose_action()` may
  themselves fail: `bus.request_approval()` (previously not wrapped in `try/except` at all — an exception
  there propagated out uncaught, past a possibly-already-saved contract, with `_gw_result` never read
  again to clean it up) and the owner-Telegram-notification `try/except`, whose failure branch already
  explicitly returned `contract_id=None` "deliberately" (§8, canonical-tool-wiring note above) but never
  actually did anything about the real, live `ActionContract` (and, by that point, the real live `EventBus`
  pending item too) it was denying the existence of. Both are now closed with the same strategy — **revoke
  the contract, using the durable lifecycle transition the user's own cancellation already uses**
  (`action_gateway.reject(contract_id, rejected_by="system:<reason>")`, via a new helper
  `_revoke_orphaned_gateway_contract()`), so `find_live_contracts()` stops returning it and it can never be
  approved by a stale Telegram button: a `contract_id=None` return is now truthful, not just asserted.
  `bus.request_approval()` is now wrapped in `try/except`; on failure the (possibly just-saved) contract is
  revoked and the uniform failure shape is returned. The owner-notification failure branch additionally
  cancels the `EventBus` pending item itself (`event_bus.pending.cancel(action_id)`) before revoking the
  contract, since by that point both exist. Revocation is best-effort and never raises — a failure to
  revoke is logged and the caller's own structured-failure return proceeds regardless, since the user is
  never told the action is pending either way. No new field was added to the return contract for this —
  "persisted" vs. "usable/notified" was resolved by making revocation synchronous and best-effort at the
  point of failure, so by the time `_queue_approval_detailed_impl()` returns, "not live" is once again true
  whenever the return says `contract_id=None`, without needing a distinct signal to reconcile a
  transient-but-real disagreement between the two.

**Final return contract (all three findings applied, no field renamed or removed from the
`created_this_turn` round above):**

```python
{
    "message": str,
    "contract_id": str | None,          # None means: no LIVE contract exists for this call, full stop —
                                         # true on every branch, including post-persistence revocation
    "ok": bool,
    "terminal_outcome": str | None,     # None only when created_this_turn is True
    "action_tool": str,                 # canonical (post-resolve_canonical_tool) on every branch
    "created_this_turn": bool,          # True only immediately after a fresh contract save that
                                         # stayed live through EventBus publish + owner notification
}
```

`tool_results_log` gained one new sentinel `tool` value, `"__approval_deferred_batch__"`, alongside the
existing `"__approval_queued__"` — both carry the canonical tool identity in `action_tool`, not `tool`.

**Regression tests added (all in `test_pa01_phantom_approval_enforcement.py`, section "P1"):** R2-real
(propose_action() raising a real exception, shadow and enforce Gateway modes, PA-01 off and enforce
states — 8 assertions), R3-real (mixed batch: real contract for an unrelated tool first, expected tool
genuinely deferred second — 6 assertions, unit + end-to-end `run_agent()` integration), R4a/R4b
(contract persisted then `bus.request_approval()` raises / owner notification fails — 7 assertions,
including direct `find_live_contracts()`/`event_bus.pending.list_for_chat()`/`batch_queue.count_pending()`
repository-state checks, not just the return dict). All three were confirmed red against commit `b7eb2bb`
(8 failures, one per finding-specific assertion) before the fix, and green after
(`test_pa01_phantom_approval_enforcement.py`: 70/70).

**No deviation** from this re-audit's own instructions: no PA-01 predicate/policy/matrix/wording change,
no extension beyond `_queue_approval_detailed_impl()`'s own plumbing and the two `_pa01_*` scoped-lookup
helpers, `BUG-104` untouched, no new branch/PR opened.

**Codex re-audit of commit `8e05d67` (verdict: `FIX_REQUIRED`) — the P1 cleanup itself was not
verified.** The three reproductions above passed on their own SUCCESS paths, but the cleanup helper
(`_revoke_orphaned_gateway_contract()`) had two structural gaps, plus one unrelated `action_tool` gap in
the outer wrapper:

1. **`_gw_result` is not always available to key cleanup off of.** `propose_action()` can raise AFTER
   `ExecutionLedger.save()` has already durably persisted a contract but BEFORE returning a
   `GatewayResult` — in that exact case, `_gw_result` stays at its outer-scope `None` initialization, so
   a cleanup keyed on `_gw_result.contract_id` has nothing to revoke, even though a real orphan exists.
2. **"Best-effort" swallowed durable failures without checking them.** `ActionGateway.reject()` returns a
   human-facing message *string*, not a boolean — a durable-transition failure inside it is caught
   internally and returned as a failure string, **not raised**. The old helper's `try/except` therefore
   saw a normal (non-exceptional) return and logged `"revoked orphaned contract"` even when the contract
   was still `"pending"` — the exact false-safety the original P1-C fix was meant to eliminate, just moved
   one layer deeper.
3. **Same gap for the EventBus pending-item cancel.** `PendingActionsStore.cancel()` raising was caught
   and logged at `DEBUG`, then execution continued as if cleared.
4. **`action_tool` in the outer wrapper's catch-all still read the raw, pre-canonicalization parameter.**
   `_impl`'s own canonicalized local `tool_name` is lost when its stack frame unwinds on an exception —
   the outer wrapper only ever saw its own untouched parameter.

**Fix — verification, not attempts, and a distinct "unverifiable" outcome:**

> **Correction (Codex re-audit of `818c8a6`, superseding the two paragraphs below):** the claim that "any
> live contract found this way can only be the one this same call just created" is **wrong** and was
> retracted in that next round. A business-action fingerprint proves the two calls describe the *same
> business action*; it does not, and cannot, prove *this call* created or owns the specific `ActionContract`
> row found under it — a fingerprint match can equally be a genuinely pre-existing contract from an
> earlier, unrelated turn, or a concurrently-created one from a different turn entirely (a real, accepted
> race this system already tolerates elsewhere). `_find_live_contract_by_fingerprint()` and every
> fingerprint-keyed revoke/cleanup call site described below were **removed** in the `818c8a6 → `next round.
> See "Codex re-audit of commit `818c8a6`" further below for the corrected ownership rule and the return
> semantics that replaced this one. The two paragraphs immediately below are kept for historical record of
> what commit `8e05d67` actually shipped — do not implement against them.

- ~~`_find_live_contract_by_fingerprint(tenant_id, canonical_user_id, tool_name, tool_inputs)`: recomputes
  the exact business fingerprint `propose_action()` would have used and searches `find_live_contracts()`
  for a match — used whenever no `GatewayResult` is available at all (finding 1). Sound because
  `propose_action()` itself always checks `find_by_fingerprint()` first and returns *early*, without
  saving, whenever a contract for that exact fingerprint already exists — so any live contract found this
  way can only be the one this same call just created.~~ (retracted — see correction note above)
- `_revoke_and_verify_contract(canonical_user_id, contract_id, reason)` / `_cancel_and_verify_pending
  (action_id, reason)`: each performs the revoke/cancel, then **re-queries** (`find_live_contracts()` /
  `pending.get()`) to confirm the item is actually gone, returning `True` only when independently
  confirmed — never merely because the call didn't raise (findings 2 and 3).
- `_orphan_cleanup_failure_response(tool_name, contract_id)`: the distinct terminal state for when
  verification fails — `terminal_outcome="APPROVAL_QUEUE_ORPHANED"` (new, alongside the existing
  `"APPROVAL_QUEUE_ERROR"`), and `contract_id` is the **real**, possibly-still-live id, deliberately never
  `None`. This is the field-semantics fix at the heart of the re-audit: `contract_id=None` now means "no
  live contract, verified," in every branch, without exception — a branch that cannot verify this returns
  the real id instead of a false `None`, rather than reusing the "confirmed clean" shape for an unverified
  state. `created_this_turn` stays `False` regardless, since an unconfirmed/still-live contract was never
  properly notified to the owner either way and must not be read as usable evidence for row 2.
  `_pa01_contract_created_for_expected_tool()`'s existing 5-condition check (requiring `ok is True` and
  `terminal_outcome is None`) already excludes `APPROVAL_QUEUE_ORPHANED` from row 2 without any change —
  it surfaces via the existing scoped terminal-outcome lookup (row 3) like any other outcome, needing no
  new PA-01-side logic.
- ~~**Central fingerprint-based cleanup moved to the outer wrapper.** `_queue_approval_detailed()`'s
  `except Exception` handler now: (a) recomputes `action_tool` via `resolve_canonical_tool()` itself
  (idempotent/pure, so safe to call again — falling back to the raw name only if canonicalization itself
  is what raised, the one case where "canonical" is genuinely unknowable), and (b) runs the fingerprint-
  based orphan lookup+revoke+verify as a backstop for any exception path that doesn't already know a
  `contract_id`/`action_id` directly.~~ (the fingerprint-based backstop in (b) is retracted — see correction
  note above; (a)'s `action_tool` recomputation remains correct and unchanged by the next round.) The two
  Gateway-`propose_action()` call sites (shadow AND — newly, in this round — enforce, neither of which has
  a `_gw_result` yet when `propose_action()` itself raises) re-raise instead of duplicating cleanup logic
  locally; the `bus.request_approval()` and owner-notification failure sites, which DO already know
  `_gw_result`/`action_id` precisely, call the verified helpers directly rather than re-raising.

**Regression tests added (`test_pa01_phantom_approval_enforcement.py`, section "P2"):** P2-1 (propose_
action() raising after a real `ExecutionLedger.save()`, shadow AND Gateway-enforce modes — 8 assertions),
P2-2 (`reject()`'s own durable transition failing without raising — 2 assertions, asserting the contract
is honestly reported still-live with its real id and `APPROVAL_QUEUE_ORPHANED`), P2-3 (`pending.cancel()`
raising after the contract itself was successfully revoked — 2 assertions), P2-4/P2-4b (`action_tool`
stays canonical across an exception that predates `propose_action()` entirely, with a fallback-to-raw
proof for the one case where canonicalization itself fails — 3 assertions). All 5 finding-specific
assertions confirmed red against commit `8e05d67` before this fix, green after
(`test_pa01_phantom_approval_enforcement.py`: 81/81; full sweep 117/117 `test_*.py` files, `smoke_tests.py`
PASS, `compileall` clean).

**No deviation:** no PA-01 predicate/policy/matrix/wording change. `terminal_outcome="APPROVAL_QUEUE_
ORPHANED"` is a new *value*, not a new field or a change to any existing field's meaning — the return
contract's shape (the same 6 keys) is unchanged from the `created_this_turn` round. `BUG-104` untouched,
no new branch/PR opened.

**Codex re-audit of commit `818c8a6` (verdict: `FIX_REQUIRED`) — architectural ruling: fingerprint is not
ownership proof.** The `8e05d67` fix above was itself unsound at its foundation: it treated a business-
action *fingerprint match* as sufficient grounds to mutate (`reject()`) whatever `ActionContract` was found
under it. A fingerprint proves two calls describe the identical business action — it proves nothing about
*which call created or owns* the specific contract row found that way. A fingerprint match found during
cleanup could be:

- a genuinely **pre-existing** contract, created by an earlier, unrelated turn for the same business action
  (e.g. the user already asked for this once before, unrelated to the call that's now failing);
- a **concurrently-created** one, from a different call/turn racing at the same moment (an accepted race
  this system already tolerates elsewhere — e.g. `ActionGateway`'s own `len(live)>1` sibling-closing logic).

Mutating either on the theory that "our failing call probably created it" silently interferes with a
request this call has no authority over — the exact structural risk the re-audit flagged.

**Ownership rule (binding, final):** destructive cleanup (`reject()`/`update_status()`, or any other
mutation) of an `ActionContract` is permitted **only** when the current call holds a `contract_id` it
received **directly** from its own `propose_action()` invocation — concretely, a `GatewayResult` with
`ok=True` and a `contract_id`, produced by *this* call. Every other case — `propose_action()` raising
without ever returning a result, a `failure_code` whose acknowledgment is uncertain
(`persistence_failed`), a failed `resolve_canonical_tool()`, a failed repository lookup, or simply "only a
fingerprint is known" — is **ownership NOT proven**, and no lookup by fingerprint, no mutation, and no
attempt to "find the likely contract" is permitted. `_find_live_contract_by_fingerprint()` and its one
caller (the outer wrapper's fingerprint-based backstop) were **deleted outright** (not demoted to a
read-only diagnostic — nothing else in this module needs a fingerprint→contract lookup). The outer
`_queue_approval_detailed()` exception handler now does exactly two things on any exception: recompute
`action_tool` canonically (best-effort, unchanged from the previous round) for telemetry, and return the
conservative `APPROVAL_QUEUE_ORPHANED` state with `contract_id=None` — no lookup, no mutation, ever.

**Persistence uncertainty reclassified.** `propose_action()`'s two structured `failure_code`s are not
equivalent:

- `"persistence_lookup_failed"` fails on the *first* operation of `propose_action()`, before any candidate
  `ActionContract` object is even constructed — structurally, provably clean. This alone still returns
  `APPROVAL_QUEUE_ERROR`, `contract_id=None`, verified.
- `"persistence_failed"` means `ExecutionLedger.save()` raised — but a raised exception from a durable
  write does not prove the write never landed (a lost acknowledgment after a real write is a classic
  distributed-systems failure mode, and `ActionGateway` provides no attempt-ID or other explicit
  "definitely not written" signal to rule it out). This failure_code now returns `APPROVAL_QUEUE_ORPHANED`,
  `contract_id=None` (no id is available to attribute, ownership is not established either way), in both
  the shadow and Gateway-enforce branches — previously both `failure_code`s were treated identically as
  verified-clean.

**Verification by exact status, not `find_live_contracts()` membership.** `_revoke_and_verify_contract()`
now confirms cleanup via `action_gateway.find_contract(contract_id)` — an authoritative lookup of that one
contract by ID — checking its own `status` field directly, rather than checking whether the id is merely
absent from `find_live_contracts()`. The distinction matters: `find_live_contracts()` only proves "not
`pending`" — a contract a *concurrent* lifecycle event moved to `"approved"`/`"executing"`/`"executed"` etc.
also disappears from that list, without our `reject()` having caused it or the contract being in any sense
safely cancelled. Success now requires `status` to land in `_SAFE_CANCELLED_CONTRACT_STATUSES`, currently
`{"rejected"}` — the only status `ActionGateway.reject()` itself ever sets in this codebase's actual
lifecycle (there is no separate `"cancelled"`/`"revoked"` status). `"approved"`, `"executing"`, `"executed"`,
`"completed"`, `"outcome_unknown"`, still-`"pending"`, and a missing contract (lookup returns `None`, with
no proof our own action caused the disappearance) are all **not** cleanup success — every one of them
returns `APPROVAL_QUEUE_ORPHANED` with the real (known-owned) `contract_id`, never a false "verified clean."

**`APPROVAL_QUEUE_ORPHANED` + `contract_id=None` semantics, precisely (both are legal, documented
combinations, and mean different things depending on which produced them):**

- `contract_id` is a **real, proven-owned id** when this call held a genuine `GatewayResult.ok=True`
  `contract_id` from its own `propose_action()`, but a later verified revoke/cancel attempt on it could not
  be confirmed.
- `contract_id=None` means **no id is known or attributable to this call at all** — never backfilled via a
  fingerprint lookup (removed entirely, per the ownership rule above). This is explicitly **not** the same
  `None` as `APPROVAL_QUEUE_ERROR`'s "confirmed no contract exists" — it means *unknown/unattributable*, not
  *confirmed absent*. `created_this_turn` is `False` in every `APPROVAL_QUEUE_ORPHANED` case regardless of
  which `contract_id` value applies.

**PA-01 matrix — unchanged, verified.** `APPROVAL_QUEUE_ORPHANED` is picked up by the existing scoped
terminal-outcome lookup (`_pa01_structured_terminal_outcome()`) exactly like any other outcome string —
no PA-01-side code change was needed. `_pa01_contract_created_for_expected_tool()`'s existing 5-condition
check (`ok is True`, `terminal_outcome is None`, ...) already excludes it from row 2 without modification.
An `ORPHANED` outcome for an *unrelated* tool does not suppress the expected tool's own row 3/row 4
evaluation, by the same full-log-scan, scoped-by-`action_tool` logic already in place for every other
outcome kind.

**Follow-up, explicitly out of scope for this fix:** a proposal-attempt ID (assigned before `propose_
action()` attempts to save, independent of whether the save itself succeeds) would let a future round
positively attribute an orphan even when `propose_action()` never returns — closing the residual "genuinely
unknowable" cases this round still reports as `contract_id=None`/`ORPHANED` rather than a specific owned
id. This is **not** implemented here — no new schema/migration/attempt-ID field was added; the ownership
rule above is enforced entirely with the return-value shape and lifecycle already in the codebase.

**Regression tests (`test_pa01_phantom_approval_enforcement.py`, section "P3", plus in-place corrections to
sections "K2" and "P2"):** the 8 reproductions required by the re-audit — pre-existing same-fingerprint
contract untouched (P3-1), concurrent same-fingerprint contract untouched (P3-2), failure before `propose_
action()` doesn't touch a pre-existing contract (P3-3), canonicalization failure doesn't touch a
pre-existing raw-tool-named contract (P3-4), structured `persistence_failed` does not return verified-clean
(the existing R2 unit test, updated in place to expect `APPROVAL_QUEUE_ORPHANED`), a `pending→approved`
lifecycle race is not reported as revoke success (P3-6, calling `_revoke_and_verify_contract()` directly),
an exact owned contract ID with a genuine `reject()`→`"rejected"` transition IS reported as success (P3-7,
verified via `find_contract()`'s exact status — not just `find_live_contracts()` absence), and an exact
owned contract ID with a durable `reject()` failure stays `ORPHANED` (the existing P2-2 test, already
correct, unchanged). Three existing test blocks that encoded the now-removed fingerprint-based-revoke
behavior were corrected in place rather than left passing against a description of code that no longer
exists: R2 (unit, `persistence_failed` → `APPROVAL_QUEUE_ERROR` was wrong, now expects `APPROVAL_QUEUE_
ORPHANED`), P1-A/R2-real (three assertions, same correction, all three Gateway-mode/PA-01-state
combinations), and P2-1 (shadow + Gateway-enforce, both variants flipped from "contract revoked, no live
contract remains" to "contract left completely untouched, still `pending`" — the literal opposite of what
the previous round shipped, per the re-audit's explicit instruction). All 18 assertions targeting this
round's findings confirmed red against commit `818c8a6` before the fix (the exact count: R2 ×1, P1-A/R2-real
×3, P2-1 ×4, P2-4/P1-2 ×2, P3-1 ×2, P3-2 ×1, P3-3 ×2, P3-4 ×2, P3-6 ×1), green after
(`test_pa01_phantom_approval_enforcement.py`: 95/95; full sweep 117/117 `test_*.py` files including
`core/router/test_router.py`, `smoke_tests.py` PASS, `compileall` clean).

**No deviation:** no PA-01 predicate/policy/matrix/wording change. `BUG-104` untouched. No proposal-attempt
ID, migration, or schema change was introduced — explicitly deferred as a future follow-up, not part of
this fix. No new branch/PR opened.

**Codex re-audit of commit `0d658c1` (verdict: `FIX_REQUIRED`) — a TOCTOU race in the ownership-proven
cleanup path.** The `818c8a6 → 0d658c1` round correctly removed fingerprint-based cleanup and required an
owned `contract_id`, but the cleanup it did perform on that owned id was still not atomic. The dangerous
window is *inside* `ActionGateway.reject()`: it reads the contract, checks `status == "pending"`, and only
*then*, as a **separate** step, calls `ExecutionLedger.update_status(contract_id, "rejected")`. On the
default `FEATURE_ACTION_CONTRACT_PERSISTENCE`-off path, that RAM write is **unconditional** (no CAS, no
re-check of the status). So a concurrent turn moving the contract `pending → approved` in the window
between the check and the write is silently overwritten to `rejected`, and `_revoke_and_verify_contract()`
— reading the status back afterward — sees `rejected`, concludes its own cancellation succeeded, and
reports `True`, having clobbered a live approval. A deterministic reproduction against `0d658c1` (concurrent
approval injected at the write) printed `cleanup_ok=True`, `final_status=rejected` — exactly the
false-success the previous round's exact-status verification was meant to prevent, but couldn't, because
the clobber happened *before* the verification read.

**Fix — atomic conditional transition.**

- `ExecutionLedger.update_status()` gained a keyword-only `require_status` parameter. When provided, the
  transition is applied only if the contract is still in exactly that status at the moment of the write,
  returning `False` (no mutation) otherwise. The RAM path does the guard **and** the set inside a **single
  `self._lock` acquisition** — a concurrent `update_status()` for the same contract also takes that lock,
  so the two are serialized and neither can slip a change between the other's check and set. The durable
  path enforces `require_status` via the repository's existing CAS on `expected_status` (a mismatch returns
  `False` instead of raising). When `require_status` is `None` (every existing caller) the behavior is
  byte-for-byte the legacy unconditional overwrite — no existing call path changes.
- `ActionGateway.reject_if_pending(contract_id, rejected_by) -> bool`: a new, additive, purpose-built API
  that calls `update_status(..., require_status="pending")` and returns whether it itself performed the
  `pending → rejected` transition. `reject()` (which returns a user-facing string and is used by
  `route_cancellation_word` and the Telegram approval callback) is left **entirely unchanged** — this
  method is only for the PA-01 orphan-cleanup path, which needs a verified boolean, not a message.
- `_revoke_and_verify_contract()` now uses `reject_if_pending()` and requires BOTH conditions for success,
  defense in depth: (1) `reject_if_pending()` reports it performed the atomic transition (a contract a
  concurrent event already moved past `pending` yields `False` here with no mutation), AND (2) the existing
  exact-status re-read via `find_contract()` still shows a safe-cancelled status (catching the reverse
  ordering — we transition to `rejected`, then a concurrent writer overwrites it back before we verify).

**Scope note:** this round necessarily touches `core/action_gateway.py` (an additive `update_status`
parameter and a new `reject_if_pending()` method) — the re-audit explicitly required "transition אטומי
מותנה pending → rejected גם ב־RAM ledger, או API ייעודי כמו reject_if_pending()". Both changes are purely
additive and default-inert: no existing caller passes `require_status`, no existing caller of `reject()` is
affected, and `BUG-104` remains untouched.

**Regression tests (`test_pa01_phantom_approval_enforcement.py`, section "P4"):** the deterministic race
reproduction (concurrent approval injected at the exact write window via a shared `update_status` wrapper
that exercises both the old racy `reject()` and the new atomic `reject_if_pending()` — 2 assertions:
approval not clobbered, cleanup not reported as success), plus two unit pins on `reject_if_pending()`
itself (returns `False`/no mutation on an already-approved contract; returns `True`/transitions a genuinely
pending one). The 2 race assertions confirmed red against commit `0d658c1` before the fix
(`cleanup_ok=True`, `final_status=rejected`), green after (`cleanup_ok=False`, `final_status=approved`).
Full suite green: `test_pa01_phantom_approval_enforcement.py` 99/99, full sweep 117/117 `test_*.py` files
(including `core/router/test_router.py`, `test_action_gateway.py`, `test_approval_concurrency.py`,
`test_phase_4b0_1c_concurrent_approvals.py`, and the durable-lifecycle suites that exercise `update_status`
most heavily), `smoke_tests.py` PASS, `compileall` clean.

**No deviation:** no PA-01 predicate/policy/matrix/wording change. The `core/action_gateway.py` changes are
additive and default-inert. `BUG-104` untouched; no proposal-attempt-ID/migration/schema change (still
deferred). No new branch/PR opened.

**Codex re-audit of commit `ce990a0` (verdict: `FIX_REQUIRED`) — the atomic guard was only atomic for the
RAM-only ledger.** The `ce990a0` round made the RAM ledger's `pending → rejected` a single-lock guarded
set — correct for the persistence-off default. But it also reached that atomicity in the *durable* path by
passing `require_status` through to `ActionContractRepository.transition()` as though that were a CAS. It
is not: the Airtable-backed repository has no conditional-PATCH primitive, and `transition()` is
**read → check → PATCH** (three separate operations). A concurrent writer can change the durable state
between the check-read and the unconditional PATCH, so routing a destructive conditional cleanup
(PA-01's `pending → rejected`) through it can still clobber a live approval — a TOCTOU the version check
cannot close, because the check and the write are not one operation. Two distinct bugs:

1. **Durable conditional cleanup was not fail-closed.** `ExecutionLedger.update_status(require_status=...)`
   called `repository.transition()` even though Airtable offers no atomic conditional transition.
2. **`transition()`'s idempotent shortcut ran before the expected-state check.** `if current.status ==
   new_status and not updates: return current` sat *above* the `expected_status`/`expected_version` check,
   so a call with `expected_status="pending"` against an actual `rejected/v2` record hit the shortcut
   (actual `== new_status "rejected"`, no updates) and returned **success** — silently accepting a stale
   expectation as though this call had performed the transition. A deterministic reproduction against
   `ce990a0` had the idempotent shortcut return success where a conflict was required.

**Architectural ruling (binding):** a fingerprint proves same-action, not ownership (established the
previous round); and now — a durable store without a *real* atomic conditional primitive must never
perform a destructive conditional cleanup. The safe matrix is: **RAM-only ledger** — atomic
`pending → rejected` under a single lock is allowed; **durable Airtable repository** — no conditional
destructive cleanup at all; `reject_if_pending()` returns `False` *without any PATCH*, and the caller maps
that to `APPROVAL_QUEUE_ORPHANED`. A read-back showing `rejected` is never, on its own, sufficient to
return `True`.

**Fix — scoped to `core/action_gateway.py` and `core/action_contract_repository.py` only (no app.py logic
change):**

- **Fix 1 — durable conditional cleanup fails closed, decided at the ledger/repository boundary.**
  `ActionContractRepository` now declares a capability, `supports_atomic_conditional_transition = False`.
  `ExecutionLedger.update_status()`: when `require_status is not None` and the repository does not declare
  that capability as exactly `True` (`getattr(..., False) is not True`, so a test double whose attribute
  auto-creates to a truthy Mock is also treated as no-CAS — fail closed by default), it returns `False`
  **without calling `transition()` at all** — no PATCH, no durable mutation. This is not a feature-flag
  check in `app.py`; the decision lives on the ledger/repository boundary, and a future Postgres-backed
  repository with a real atomic `UPDATE ... WHERE status = :expected` can flip the capability to `True`.
  `require_status=None` (every existing caller — approve, reject, execution lifecycle) is entirely
  unchanged: still routes through `transition()` exactly as before.

- **Fix 2 — strict expected-state ordering in `transition()`.** The `expected_status`/`expected_version`
  check now runs *before* the idempotent shortcut. A stale expectation (`expected=pending` vs actual
  `rejected/v2`) raises `ActionContractTransitionConflictError` and never PATCHes. The idempotent shortcut
  is preserved for genuine, correctly-expected same-status replays (which now only reach it after the
  expectation is confirmed to match).

`reject_if_pending()` is unchanged in signature; its docstring now records that `True` requires a *real*
atomic primitive to have performed the transition — the RAM single-lock set, never a non-atomic durable
write. `_revoke_and_verify_contract()` in `app.py` needed **no logic change**: it already maps
`reject_if_pending() → False` to `APPROVAL_QUEUE_ORPHANED`, so a durable non-CAS repository now naturally
yields the conservative orphan outcome. (Only comments/docstrings were touched in `app.py`-adjacent code;
no recovery logic was added there — within the re-audit's explicit scope guard.)

**Regression tests (`test_pa01_phantom_approval_enforcement.py`, section "P5"), the 5 required
reproductions:** D1 (durable TOCTOU — non-CAS repository → `reject_if_pending()` fails closed,
`transitioned=False`, **zero** `transition()`/PATCH calls, the concurrent approval untouched), D2
(already-rejected shortcut — real `ActionContractRepository.transition()` with `expected=pending` against
`rejected/v2` → conflict, no PATCH), D3 (RAM atomic success — `pending → rejected`, `transitioned=True`),
D4 (RAM concurrent approval wins first — `transitioned=False`, status stays `approved`), D5 (PA-01 durable
cleanup outcome — owner-notify failure under a durable non-CAS repository → `APPROVAL_QUEUE_ORPHANED`, real
owned `contract_id` surfaced, no durable overwrite (still `pending`), message makes no cancellation claim,
row 2 not satisfied). The 4 discriminating assertions (D1 no-PATCH, D2 conflict, D5 outcome + no-overwrite)
confirmed red against commit `ce990a0` before the fix, green after (D3/D4 are RAM-only and pass on both, as
expected). Full suite green: `test_pa01_phantom_approval_enforcement.py` 110/110, full plain-script sweep
117/117, all pytest-style repository/lifecycle/concurrency suites (`test_phase_4b_1b_durable_lifecycle.py`
17/17, `test_pr0c_action_contract_repository.py` 14/14, `test_pr0c_action_contracts_persistence.py` 16/16,
`test_action_gateway.py` 43/43, `test_approval_concurrency.py` 20/20,
`test_phase_4b0_1c_concurrent_approvals.py` 12/12, `test_stage_b_full_suite.py` 128/128), `smoke_tests.py`
PASS, `compileall` clean, `git diff --check` clean. (A stale brittle source-grep in
`test_phase_4b_1a_lookup_correctness.py`, left by the `818c8a6` round's split of the two persistence
failure codes and only surfacing under `pytest`, was updated to match the current code — test-only, no
app.py change.)

**No deviation:** no PA-01 predicate/policy/matrix/wording change. Changes are confined to
`core/action_gateway.py`, `core/action_contract_repository.py`, tests, and docs — no new recovery logic in
`app.py`. `BUG-104` untouched; no migration, no Postgres wiring, no attempt at full Airtable CAS (the
durable path fails closed instead); proposal-attempt-ID still deferred. No new branch/PR opened.
