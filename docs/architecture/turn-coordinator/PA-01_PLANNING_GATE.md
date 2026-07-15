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
or any agent-authored text:

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

### 4.0 The decision matrix and the Phantom-only predicate, exact (revised, pass 3)

Pass 3 splits pass 2's single `approval_contract_expected` boolean into the four independent signals
§3.5/§3.6 established, and states the **full decision matrix** (not just the Phantom-block case) so it
is unambiguous which of the four possible responses a contract-required turn gets:

```
intent_requires_contract_for_success := intent_requires_contract_for_success(route.intent)   # §3.5, policy-only
contract_capable_this_turn            := contract_capable_this_turn(route, identity, ctx)      # §3.6, runtime-dependent
contract_created                      := any(r.get("tool") == "__approval_queued__" and r.get("contract_id")
                                              for r in tool_results_log)                        # turn-scoped, real id required
structured_terminal_outcome           := first r.get("terminal_outcome") in tool_results_log, else None   # §3.6's six-outcome table
```

**Decision matrix (§4.4 implements this directly):**

| `intent_requires_contract_for_success` | `contract_capable_this_turn` | `contract_created` | `structured_terminal_outcome` | Response |
|---|---|---|---|---|
| False | — | — | — | ordinary agent reply, PA-01 never touches it |
| True | — | True | — | `_queue_approval()`'s own Gateway Approval Prompt (`app.py:863`), unchanged |
| True | True | False | set | that outcome's own deterministic response (§4.4) |
| True | True | False | None | **Phantom fallback** (§4.3) — this is the only cell that was ever the actual target |
| True | False | False | — | **Capability/permission deterministic response** (§4.3b, new this pass) — never the Phantom fallback, never a raw agent reply |

(Row 2 — `contract_created=True` — takes priority regardless of `contract_capable_this_turn`/
`structured_terminal_outcome`: if a contract genuinely exists this turn, capability was self-evidently
sufficient and no further check is needed.)

**The Phantom-only predicate, exact — this is what actually replaces `final_reply` with §4.3's fallback
text specifically:**

```
BLOCK_PHANTOM  :=  intent_requires_contract_for_success
                    and contract_capable_this_turn
                    and not contract_created
                    and not structured_terminal_outcome
```

`final_reply`'s own **text is never read** by any of these four signals — unchanged from pass 1.
`intent_requires_contract_for_success` is pass 2's `approval_contract_expected`, renamed to match this
pass's terminology (same function, same set, no behavior change to this term). `contract_capable_this_turn`
and `structured_terminal_outcome` are both new this pass (§3.6) — together they fix the structural false
positive described in the pass-3 revision note above: a `guest`/`employee`/`lead`/`readonly` identity
attempting a contract-required intent now resolves to the capability row, not the Phantom row; a
mid-turn `ToolDenied`/`LeadsDirectWriteBlocked`/queueing failure now resolves to its own outcome row, not
the Phantom row.

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
# app.py:2439-2443, two new keys added to the dict already being constructed
tool_results_log.append({
    "tool": "__approval_queued__",
    "content": result,
    "ok": bool(_gw_result and _gw_result.contract_id),                                # CHANGED (was hardcoded True)
    "contract_id": _gw_result.contract_id if _gw_result else None,                    # NEW (pass 2)
    "terminal_outcome": None if (_gw_result and _gw_result.contract_id) else "APPROVAL_QUEUE_ERROR",  # NEW (pass 3, §3.6)
})
```

`_gw_result` is already in scope at this exact point. **Revised this pass:** pass 2 only added
`contract_id`; pass 3 also fixes `"ok"` (previously hardcoded `True` even for duplicate/rejected/
notify-failed returns — itself a pre-existing minor inaccuracy in the A32 log, unrelated to PA-01 but
worth fixing alongside since the same line is being touched) and adds `"terminal_outcome"` so
§3.6's `APPROVAL_QUEUE_ERROR` case is structurally detectable without inspecting `result`'s text.

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
keyed by a structured `terminal_outcome` field is state, not inference.

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

**(f) Structured terminal-outcome lookup, one small helper.** Reads only `tool_results_log` (already
fully constructed by (a)/(b) above by the time PA-01's block runs):

```python
def _pa01_structured_terminal_outcome(tool_results_log: list[dict]) -> tuple[str, str] | None:
    for r in tool_results_log:
        outcome = r.get("terminal_outcome")
        if outcome:
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

# (b) NEW this pass — capability/permission gap. Deliberately does NOT say
# "try sending the request again": resending changes nothing when the real
# blocker is a role/capability gap, and telling the user otherwise is
# actively misleading (the exact failure mode §3.6 was written to prevent).
_PA01_CAPABILITY_UNAVAILABLE_FALLBACK = (
    "הפעולה הזו אינה זמינה עבור התפקיד שלך במערכת. "
    "לביצוע הפעולה, פנה לבעלים או למנהל."
)
```

`_PA01_CAPABILITY_UNAVAILABLE_FALLBACK` is new user-facing copy requiring the same owner sign-off as
(a) already required (§7) — not yet approved wording, flagged explicitly as open. For the four
mid-turn `structured_terminal_outcome` cases (`PERMISSION_DENIED`/`PREFLIGHT_BLOCKED`/
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
    _pa01_state = get_pa01_enforcement_state()
    if _pa01_state in ("shadow", "enforce"):
        try:
            _pa01_contract_created = any(
                r.get("tool") == "__approval_queued__" and r.get("contract_id")
                for r in tool_results_log
            )
            _pa01_outcome = None if _pa01_contract_created else _pa01_structured_terminal_outcome(tool_results_log)
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

        # Matrix row 2 — contract genuinely exists: nothing to do, Gateway's
        # own message already stands.
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

**Additional regression, must-pass:**
- [ ] The **false-negative fix** from §4.1 (still valid, restated for the new predicate): identity has
  an unrelated pre-existing pending contract (e.g. a Gmail draft) *and* this turn fabricates an
  unrelated phantom claim for a contract-required intent with zero `tool_use` and no `contract_id` for
  **this turn's** intent → `=enforce` still replaces `final_reply` with the Phantom fallback, because
  `contract_created` is computed from `tool_results_log` (turn-scoped) and finds nothing — not fooled by
  an unrelated live contract belonging to a different request.
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
   - [ ] **Zero** blocks of a real approval (matrix row 2 — `contract_created` would have been `True`)
     logged as if it were row 4/5. Any such event found is a bug in §4.0's matrix and must be fixed
     before graduating, not accepted as noise.
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
- **Narrowed, still-real risk — legitimate free-text agent clarifying questions on *capable*
  contract-required turns will be blocked/replaced (matrix row 4), not just phantom claims.** §4.0's
  matrix is deliberately strict per decision 2: for a contract-required, *capable* turn, only a
  router-classified `Handler.CLARIFY` may return a clarifying question — any other clarifying text the
  agent generates itself (e.g. "איזה משימה, X או Y?" for `owner` + `CREATE_TASK`, zero `tool_use`) has
  `contract_created=False` and no `structured_terminal_outcome`, landing on row 4 exactly like an actual
  phantom claim. This risk is unchanged by this pass's capability fix — it is orthogonal: the capability
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
- **Two pieces of new user-facing copy now require owner sign-off, not one.** `_PA01_PHANTOM_APPROVAL_
  FALLBACK` (§4.3a, prior pass) and `_PA01_CAPABILITY_UNAVAILABLE_FALLBACK` (§4.3b, new this pass) are
  both new strings, not a "no UX change" patch — both need explicit sign-off before `"enforce"` ships,
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

This document is the complete Planning Gate deliverable for PA-01 through three corrections: pass 1
replaced the rejected `is_hijack`-as-trigger design with a state-only structural mechanism; pass 2 fixed
a structural false positive treating draft/conversational intents as contract-required; pass 3 (this
edit) fixes a second structural false positive — treating every contract-required intent as if a
contract could be created by *any* identity, ignoring role-based tool availability and mid-turn
denial/preflight gates. No code has been written, no branch opened — **אין לממש עדיין** remains in
force. Direct answers to the required return items:

**Intent → tool mapping (§3.5):** `_CONTRACT_REQUIRED_INTENT_TO_TOOL`, a 10-entry dict in
`core/router/risk_router.py` — `CREATE_TASK`/`CREATE_CONTACT`/`CREATE_LEAD` → `airtable_add`;
`UPDATE_TASK`/`COMPLETE_TASK`/`UPDATE_CONTACT`/`UPDATE_LEAD`/`UPDATE_DEAL_STAGE` → `airtable_update`;
`CREATE_EVENT`/`SCHEDULE_MEETING` → `calendar_create_event`. The remaining 5 `_NORMAL_INTENTS` members
(`DRAFT_EMAIL`/`DRAFT_MESSAGE`/`QUALIFY_LEAD`/`UPDATE_EVENT`/`STORE_MEMORY`) are excluded, with per-intent
reasoning in §3.5's table.

**Capability/permission source (§3.6):** three independent, already-existing state signals, combined by
a new `contract_capable_this_turn(route, identity, ctx)` function — (1) `ctx.allowed_tools`
(`context.py:30-79`, role-filtered tool list actually offered to Claude this turn), (2)
`tool_registry.check_allowed(expected_tool, identity)` (`tool_registry.py:258-262`, a second,
independently-maintained role-tool policy layer), (3) `route.tool_allowed`
(`route_decision.py:166`/`router.py:109-136`). All three already exist; none is duplicated. Mid-turn
denial/preflight/validation is a separate signal, `structured_terminal_outcome`, read from
`tool_results_log` entries newly tagged at three existing sites (§4.2b): `ToolDenied`
(`app.py:2352-2358`) → `PERMISSION_DENIED`; `LeadsDirectWriteBlocked`
(`app.py:2369-2378`) → `PREFLIGHT_BLOCKED`; `_queue_approval()`'s non-success early returns
(`app.py:753-860`) → `APPROVAL_QUEUE_ERROR` (§4.2a).

**Terminal outcomes, six, per §3.6's table:** `CAPABILITY_UNAVAILABLE` (computed upfront by
`contract_capable_this_turn`, not read from the log), `PERMISSION_DENIED`, `PREFLIGHT_BLOCKED`
(load-bearing — catches the table-granularity gap `contract_capable_this_turn` structurally cannot),
`APPROVAL_QUEUE_ERROR` (load-bearing — prevents accurate dedup/error messages from being overwritten by
the generic fallback), `VALIDATION_FAILED` (defined for completeness; **not reachable** within a
PA-01-relevant turn today, since `_queue_approval()` bypasses `dispatch_tool()`/`validate_action()`
entirely), `STRUCTURED_CLARIFICATION` (defined for matrix completeness; **not reachable** at PA-01's
gate, `Handler.CLARIFY` always returns upstream). None of the six is detected from agent-authored text —
five are read from structured `tool_results_log` keys this pass adds, one is computed from
role/tool-registry/router state directly.

**Corrected predicate — now a 5-row decision matrix (§4.0), with the Phantom-only sub-predicate:**
```
intent_requires_contract_for_success := intent_requires_contract_for_success(route.intent)     # §3.5
contract_capable_this_turn            := contract_capable_this_turn(route, identity, ctx)        # §3.6
contract_created                      := any(r["tool"]=="__approval_queued__" and r["contract_id"]
                                              for r in tool_results_log)
structured_terminal_outcome           := first r["terminal_outcome"] in tool_results_log, else None

BLOCK_PHANTOM := intent_requires_contract_for_success and contract_capable_this_turn
                 and not contract_created and not structured_terminal_outcome
```
Full 5-row response table (not-required → unaffected; contract exists → Gateway prompt; terminal
outcome → that outcome's own message; `BLOCK_PHANTOM` → Phantom fallback; not capable → capability
fallback) in §4.0. No term in either the matrix or `BLOCK_PHANTOM` reads `final_reply`'s text.

**Verdict: PASS.** This pass's correction is state-only and duplication-free, same as the prior two:
`contract_capable_this_turn` reads three signals that already exist in three different files, combined
in one new function, not reimplemented; `structured_terminal_outcome` reads a new key added at three
sites where a real gate already produces an accurate message, reusing that gate's own text rather than
inventing a new one. The result is *more* permissive where it should be (row 5's dedicated capability
message replaces what would otherwise be a misleading "try again" for a `guest`/`employee`/`lead`/
`readonly` identity that structurally cannot ever succeed) and *more* accurate where it should be (row 3
preserves the real dedup/denial/preflight message instead of overwriting it with the generic fallback) —
without reintroducing any text-pattern dependency into the decision itself (decision 8, still holds: the
gate-authored strings reused in row 3 are read by structured key, never pattern-matched). §5 carries all
7 of the user's required capability-layer regression cases plus the `APPROVAL_QUEUE_ERROR` case found
along the way; §6 adds two new graduation criteria (a manually-reviewed row-5 sample, and a
`PERMISSION_DENIED`/`PREFLIGHT_BLOCKED` volume-spike check against each gate's own pre-PA-01 baseline);
§7 records both closed structural false positives (pass 2's and this pass's) and the remaining, narrower
open risk (row 4's clarifying-question trade-off for *capable* identities, unchanged and orthogonal to
this pass's fix). No further correction is required before implementation may begin. OH-01/OS-01/RC-01
remain out of scope until their own planning gates, per the approved order.
