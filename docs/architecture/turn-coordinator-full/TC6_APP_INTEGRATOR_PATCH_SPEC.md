# TC6 — `app.py` Integrator Patch Spec

**Status:** spec only, not applied. `app.py` is Integrator-only per
`PARALLEL_IMPLEMENTATION_WORKSTREAMS.md`'s file ownership map — the TC6 WS2
branch (`claude/tc6-explicit-reply-ownership`) does not edit this file
directly. This document is the isolated patch spec the integrator applies
against `app.py`, once WS2's `core/action_gateway.py` change
(`reply_ownership_for_contract()`) has landed.

**Base:** `origin/main` `38d9226` (same base as the WS2 branch).

**Design correction this spec implements** (owner-approved, supersedes the
TC6 preflight's original §E, which proposed `ActionGateway.approval_status()`
as the enforcement source): `approval_status()` is user-scoped — it answers
"what is this identity's latest/live contract," which can silently point at
a different contract than the one this turn actually touched. TC6 must
preserve **exact turn-to-contract correlation**. The canonical rule:

- `__approval_queued__` / the current-turn structured result = **correlation
  evidence only** (proves *a* contract touch happened this turn).
- The exact `contract_id` on that entry = the identity of the lifecycle
  action this turn actually touched.
- `ActionLifecycleResult` projected from that **exact** contract (via the new
  `ActionGateway.reply_ownership_for_contract(contract_id)`, WS2,
  `core/action_gateway.py`) = the canonical reply-ownership authority.
- `ActionLifecycleResult` must **only** ever be produced from a real
  `ActionContract` through that canonical projection — never fabricated
  inline by a caller as a fallback.
- **Review round 2 correction:** a read failure or unexpected `None` from
  the canonical projection is not just "return some existing failure dict
  from the producer" — that alone does not stop the Agent from being
  invoked again, because `run_agent()`'s tool loop only early-returns when
  its `_gateway_owned` derivation matches, and a generic failure dict
  (no `action_lifecycle_result`, no `reply_owner`) does not match it. TC6
  must therefore distinguish, structurally, at the tool-loop level:
  - **Branch A — canonical Gateway ownership**: a correlated current-turn
    approval entry with a real `ActionLifecycleResult` for its exact
    `contract_id` and `reply_owner == "gateway"` → the existing
    Gateway-owned early return (unchanged shape, see §2).
  - **Branch B — correlated approval turn, ownership unverifiable**: a
    correlated current-turn approval entry exists (a real contract was
    touched), but the canonical ownership projection for that exact
    contract could not be confirmed. This is a **safety stop, not a second
    reply-ownership authority** — it fabricates no `ActionLifecycleResult`,
    claims no `reply_owner="gateway"`, and never silently defaults to Agent
    ownership. It fails closed with its own early return, structurally
    identical in *shape* to Branch A's, before the Agent can be invoked
    again — see §1d/§2.

---

## 1. `_queue_approval_detailed_impl()` — stop hardcoding `reply_owner` per branch

Every return branch that already holds a **verified canonical contract_id**
this turn (i.e. every branch that already builds `_pending_lifecycle` /
`_generic_lifecycle` / `_lifecycle_result` via the legacy
`build_approval_lifecycle_result()` path today) must also derive a typed
`action_lifecycle_result` from that **exact** contract_id, and the scalar
`"reply_owner"` key must be *read from* that typed result, never
independently hardcoded.

### 1a. `existing_pending_blocks_agent` (enforce branch, current `app.py:1504-1520`, and shadow branch `app.py:1609-1625`)

```python
# BEFORE (both branches, unchanged shape today):
_pending_lifecycle = build_approval_lifecycle_result(
    _gw.find_contract(_gw_result.contract_id),
    canonical_state="pending_conflict",
)
return {
    "message": _pending_lifecycle.safe_user_message,
    "contract_id": _gw_result.contract_id,
    "ok": False,
    "terminal_outcome": "APPROVAL_QUEUE_ERROR",
    "action_tool": tool_name,
    "created_this_turn": False,
    "owner_notified": False,
    "reply_owner": "gateway",              # <- independently hardcoded
    "lifecycle_result": _pending_lifecycle,
    "final_response_count": 1,
}
```

```python
# AFTER:
_pending_lifecycle = build_approval_lifecycle_result(
    _gw.find_contract(_gw_result.contract_id),
    canonical_state="pending_conflict",
)
_action_lifecycle_result = _ownership_for_contract_or_none(_gw, _gw_result.contract_id)
if _action_lifecycle_result is None:
    # TC6 review fix round 2 (Branch B): the ownership authority itself
    # could not be confirmed for a contract_id this call already believes
    # is real. Do NOT use _orphan_cleanup_failure_response() here — its
    # wording ("an error occurred while trying to CANCEL an approval
    # request") is semantically false for this case (nothing was ever
    # cancelled). Instead return the SAME already-computed, already-safe
    # legacy text (_pending_lifecycle.safe_user_message, independent of
    # whether the NEW canonical check succeeded) paired with a distinct,
    # internal-only terminal_outcome marker so the tool loop (§2) can
    # recognize this as "correlated approval turn, ownership unverifiable"
    # and fail closed BEFORE another Agent round — never a fabricated
    # ActionLifecycleResult, never an invented reply_owner="gateway", never
    # a silent fall-through to Agent ownership.
    return {
        "message": _pending_lifecycle.safe_user_message,
        "contract_id": _gw_result.contract_id,
        "ok": False,
        "terminal_outcome": "APPROVAL_OWNERSHIP_VERIFICATION_FAILED",
        "action_tool": tool_name,
        "created_this_turn": False,
        "owner_notified": False,
        "final_response_count": 1,
        # deliberately NO "reply_owner" / "action_lifecycle_result" keys —
        # see §1d/§2 for how the tool loop reacts to this marker.
    }
return {
    "message": _pending_lifecycle.safe_user_message,
    "contract_id": _gw_result.contract_id,
    "ok": False,
    "terminal_outcome": "APPROVAL_QUEUE_ERROR",
    "action_tool": tool_name,
    "created_this_turn": False,
    "owner_notified": False,
    "reply_owner": _action_lifecycle_result.reply_owner,   # derived, not hardcoded
    "lifecycle_result": _pending_lifecycle,                 # UNCHANGED — legacy text source
    "action_lifecycle_result": _action_lifecycle_result,    # NEW — TC6 canonical ownership
    "final_response_count": 1,
}
```

### 1b. Generic `ok=False` (BUG-162 branch, current `app.py:1521-1575`)

```python
# BEFORE (relevant excerpt):
_generic_lifecycle = (
    build_approval_lifecycle_result(_generic_found_contract, repeated=True)
    if _generic_found_contract else None
)
return {
    "message": (...),
    "contract_id": _generic_contract_id,
    "ok": False, "terminal_outcome": "APPROVAL_QUEUE_ERROR",
    "action_tool": tool_name, "created_this_turn": False,
    **({
        "owner_notified": False,
        "reply_owner": "gateway",             # <- independently hardcoded
        "lifecycle_result": _generic_lifecycle,
        "final_response_count": 1,
    } if _generic_lifecycle else {}),
}
```

```python
# AFTER:
_generic_lifecycle = (
    build_approval_lifecycle_result(_generic_found_contract, repeated=True)
    if _generic_found_contract else None
)
if _generic_lifecycle:
    _generic_action_lifecycle_result = _ownership_for_contract_or_none(
        _gw, _generic_contract_id,
    )
    if _generic_action_lifecycle_result is None:
        # Same Branch B fail-closed rule as §1a: a verified contract exists
        # (_generic_found_contract), but the ownership authority itself
        # could not be confirmed — never fabricate, never default to Agent,
        # never _orphan_cleanup_failure_response() (wrong wording for this
        # case — see §1a's comment). Reuses the same already-computed,
        # already-safe _generic_lifecycle.safe_user_message.
        return {
            "message": _generic_lifecycle.safe_user_message,
            "contract_id": _generic_contract_id,
            "ok": False,
            "terminal_outcome": "APPROVAL_OWNERSHIP_VERIFICATION_FAILED",
            "action_tool": tool_name,
            "created_this_turn": False,
            "owner_notified": False,
            "final_response_count": 1,
        }
return {
    "message": (...),
    "contract_id": _generic_contract_id,
    "ok": False, "terminal_outcome": "APPROVAL_QUEUE_ERROR",
    "action_tool": tool_name, "created_this_turn": False,
    **({
        "owner_notified": False,
        "reply_owner": _generic_action_lifecycle_result.reply_owner,
        "lifecycle_result": _generic_lifecycle,
        "action_lifecycle_result": _generic_action_lifecycle_result,
        "final_response_count": 1,
    } if _generic_lifecycle else {}),
}
```

### 1c. Success branch (current `app.py:1841-1867`)

```python
# BEFORE:
_lifecycle_result = _approval_gateway.lifecycle_result(_contract_id)
_final_message = _lifecycle_result.safe_user_message
...
return {
    ...,
    "reply_owner": _lifecycle_result.reply_owner,   # from the LEGACY ApprovalLifecycleResult
    "lifecycle_result": _lifecycle_result,
    "final_response_count": 1,
}
```

```python
# AFTER:
_lifecycle_result = _approval_gateway.lifecycle_result(_contract_id)
_final_message = _lifecycle_result.safe_user_message
_action_lifecycle_result = _ownership_for_contract_or_none(_approval_gateway, _contract_id)
if _action_lifecycle_result is None:
    # Same Branch B fail-closed rule as §1a/§1b: a real contract was just
    # created (_contract_id is known-real here — this is the success
    # path), but the ownership authority itself could not be confirmed.
    # Never fabricate, never default to Agent, never
    # _orphan_cleanup_failure_response() (wrong wording — nothing was
    # cancelled). Reuses the same already-computed _final_message.
    return {
        "message": _final_message,
        "contract_id": _contract_id,
        "ok": False,
        "terminal_outcome": "APPROVAL_OWNERSHIP_VERIFICATION_FAILED",
        "action_tool": tool_name,
        "created_this_turn": False,
        "owner_notified": _owner_notified,
        "final_response_count": 1,
    }
...
return {
    ...,
    "reply_owner": _action_lifecycle_result.reply_owner,   # from the NEW canonical projection
    "lifecycle_result": _lifecycle_result,                  # UNCHANGED — legacy text source
    "action_lifecycle_result": _action_lifecycle_result,    # NEW
    "final_response_count": 1,
}
```

### 1d. New local helper and marker (add once near the top of `_queue_approval_detailed_impl()`, or as module-level `app.py` additions)

**Review correction (round 1):** the original version of this spec had this
helper fabricate a synthetic `ActionLifecycleResult` (`lifecycle_state=
"unknown"`, `reply_owner="gateway"`) whenever the exact-contract read
failed or returned an unexpected `None`. This was rejected on review —
`ActionLifecycleResult` must only ever be produced from a real
`ActionContract` through the canonical WS2 projection
(`build_action_lifecycle_result()`), never synthesized inline by a caller.

**Review correction (round 2):** the first fix made the helper return
`None` on failure, with each call site (§1a/§1b/§1c) falling back to
`_orphan_cleanup_failure_response()`. This was *itself* insufficient for
two independent reasons, both fixed here: (a) `_orphan_cleanup_failure_
response()`'s wording ("an error occurred trying to *cancel* an approval
request") is semantically false for an ownership-*read* failure — nothing
was ever cancelled; (b) more importantly, returning any producer-level
dict alone does not stop the Agent from being invoked again — the tool
loop's early return only fires when its `_gateway_owned` derivation
matches (§2), and a generic failure dict matches nothing. The corrected
design below fixes both: the helper still returns `None` — nothing else —
on any read failure, but each call site (§1a/§1b/§1c) now returns the
already-computed, already-safe legacy text tagged with a new, distinct,
internal-only marker (`APPROVAL_OWNERSHIP_VERIFICATION_FAILED`) that §2's
tool-loop logic recognizes as **Branch B** and fails closed on, structurally,
before another Agent round can run — not merely a caller-local failure
response.

```python
# New sibling to the existing APPROVAL_QUEUE_ERROR / APPROVAL_QUEUE_ORPHANED
# / APPROVAL_QUEUE_NEVER_ATTEMPTED terminal_outcome markers — internal-only,
# never rendered to the user directly (the "message" key carries the real,
# already-existing safe text; this marker is read only by §2's tool-loop
# logic to decide reply ownership, exactly like the existing markers are
# already read by BUG-122's accounting and PA-01's outcome lookup).
_APPROVAL_OWNERSHIP_VERIFICATION_FAILED = "APPROVAL_OWNERSHIP_VERIFICATION_FAILED"


def _ownership_for_contract_or_none(gateway, contract_id: str):
    """TC6: derive the canonical exact-contract ActionLifecycleResult for a
    contract_id THIS call already knows to be real (it was just
    created/found by propose_action() in this same function).

    Returns ``None`` — never a fabricated ``ActionLifecycleResult`` — on
    any read failure. Callers MUST treat ``None`` as "return this call's
    own already-computed safe text, tagged with
    ``_APPROVAL_OWNERSHIP_VERIFICATION_FAILED``" (see §1a/§1b/§1c), never
    as license to invent a synthetic lifecycle/approval/execution state,
    and never as license to silently default reply ownership to the Agent
    (design correction requirements 10-11: no fabrication, no silent Agent
    default, no second ownership authority in app.py).
    """
    try:
        return gateway.reply_ownership_for_contract(contract_id)
    except Exception:
        logger.warning(
            "[ActionGateway] TC6 exact-contract ownership read failed for "
            "contract=%s.", contract_id, exc_info=True,
        )
        return None
```

The branches that have **no contract at all** (duplicate fingerprint,
cross-channel dedup, `persistence_lookup_failed`, `bus.request_approval()`
raising with a successfully-revoked contract) are **unchanged** — they
correctly omit `reply_owner`/`lifecycle_result`/`action_lifecycle_result`
entirely today, and must keep doing so (design correction requirement 11:
no canonical contract exists → do not invent Gateway ownership). They also
never call `_ownership_for_contract_or_none()` at all — only §1a/§1b/§1c,
which already hold a verified contract_id, do. `_orphan_cleanup_failure_
response()` itself is untouched and keeps its existing callers/meaning
(genuine cleanup-uncertain cases, e.g. the `bus.request_approval()`
exception handler) — this spec does not reuse it for the ownership-read-
failure case (see the round-2 correction above for why).

---

## 2. `_gateway_owned` lookup — `run_agent()`, current `app.py:4485-4489`

```python
# BEFORE:
_gateway_owned = next((
    entry for entry in reversed(tool_results_log)
    if entry.get("tool") == "__approval_queued__"
    and entry.get("reply_owner") == "gateway"
), None)
```

```python
# AFTER — derives BOTH Branch A (canonical Gateway ownership) and Branch B
# (correlated turn, ownership unverifiable) from the SAME correlated entry:
_gateway_owned = None
_ownership_verification_failed_entry = None
_correlated_approval_entry = next((
    entry for entry in reversed(tool_results_log)
    if entry.get("tool") == "__approval_queued__"
), None)
if _correlated_approval_entry is not None:
    if _correlated_approval_entry.get("terminal_outcome") == "APPROVAL_OWNERSHIP_VERIFICATION_FAILED":
        # Branch B: a real contract was touched this turn, but its exact-
        # contract ownership projection could not be confirmed (§1a/§1b/§1c).
        _ownership_verification_failed_entry = _correlated_approval_entry
    else:
        _entry_action_lifecycle_result = _correlated_approval_entry.get("action_lifecycle_result")
        if (
            _entry_action_lifecycle_result is not None
            and getattr(_entry_action_lifecycle_result, "reply_owner", None) == "gateway"
        ):
            # Branch A: canonical Gateway ownership, confirmed.
            _gateway_owned = _correlated_approval_entry
```

Everything downstream of the existing `if _gateway_owned is not None and
_flag_enabled("FEATURE_SINGLE_SPEAKER_APPROVAL_UX"):` block (`app.py:4490-
4538` — the `_lifecycle = _gateway_owned.get("lifecycle_result")` read for
`safe_user_message`, the `owner_notified` short-circuit) is **unchanged**
for Branch A. Requirement 9 (keep the boundary, change only its authority)
and requirement 1 (preserve `lifecycle_result`/`safe_user_message`
rendering) are both satisfied by touching only the derivation of
`_gateway_owned` itself, not what it gates.

**New Branch B early return**, added as a sibling check inside the SAME
`FEATURE_SINGLE_SPEAKER_APPROVAL_UX` gate as Branch A (deliberately the
same early, structural, already-established mechanism — **not** PA-01's
separate, later, text-pattern-based mechanism near the end of `run_agent()`,
which this invariant must not depend on):

```python
if _flag_enabled("FEATURE_SINGLE_SPEAKER_APPROVAL_UX"):
    if _ownership_verification_failed_entry is not None:
        # Branch B — a safety stop, not a second reply-ownership authority.
        # No ActionLifecycleResult (real or fabricated) backs this branch;
        # no reply_owner="gateway" is claimed; the Agent is never given
        # another round for this turn. Mirrors Branch A's owner_notified/
        # final_response_count shape exactly, so an already-delivered
        # message (§1c's success-path variant) is never duplicated.
        if _out_meta is not None:
            _out_meta.update({
                "reply_owner": "unverified",  # distinct from "gateway"/"agent" — a fact, not an ownership claim
                "final_response_count": 1,
                "canonical_state": "ownership_verification_failed",
            })
        return (
            "" if _ownership_verification_failed_entry.get("owner_notified")
            else _ownership_verification_failed_entry.get("content", "")
        )
    if _gateway_owned is not None:
        # Branch A — existing shape, unchanged (see above).
        ...
```

Both branches are hard `return` statements from `run_agent()` — for either
one, `tool_calls_made += 1` and the next Claude API call (`messages.append(
...)` further down the loop) are never reached, and the later `Ownership
Signal`/PA-01 code (§3, `app.py:4626+`) is never reached either, exactly as
already true for Branch A today. This is what satisfies "the Agent is not
invoked again / cannot become final speaker" and "does not rely on PA-01
being enabled" — the stop happens structurally, before PA-01's own
(separate, later, flag-gated) check would ever run.

---

## 3. `_approval_queued_this_turn` / `OwnershipSignal` — current `app.py:4629-4630` and `4670`

Two **distinct** uses of `_approval_queued_this_turn` exist in this region;
only the second is in TC6's scope:

- **BUG-122 gate** (`app.py:4578-4580`, `4585-4603`) — asks "was anything
  queued this turn at all," a legitimately weaker, presence-only question
  used to avoid a misleading "I failed" fallback. **Not part of TC6, not
  changed.**
- **Case C2 signal** (`app.py:4626-4639`) — also a presence-only detection
  signal (log-only, never blocks). **Not part of TC6, not changed.**
- **OwnershipSignal's `reply_owner`** (`app.py:4653-4672`) — this is the one
  requirement 8 targets: it must derive from the same typed
  `action_lifecycle_result`, not from sentinel presence alone.

```python
# BEFORE (app.py:4670, inside the build_ownership_signal(...) call):
reply_owner="gateway" if _approval_queued_this_turn else "agent",
```

```python
# AFTER — compute once, reuse the same correlation as §2 (if this code path
# runs after an early return in §2 already fired, this recomputation is
# only reached when it did NOT — i.e. FEATURE_SINGLE_SPEAKER_APPROVAL_UX is
# off, or _gateway_owned was None — so it cannot disagree with §2 by
# construction, since both read the same entry the same way):
_signal_correlated_entry = next((
    entry for entry in reversed(tool_results_log)
    if entry.get("tool") == "__approval_queued__"
), None)
_signal_action_lifecycle_result = (
    _signal_correlated_entry.get("action_lifecycle_result")
    if _signal_correlated_entry is not None else None
)
_signal_reply_owner = (
    "gateway"
    if (
        _signal_action_lifecycle_result is not None
        and getattr(_signal_action_lifecycle_result, "reply_owner", None) == "gateway"
    )
    else "agent"
)
...
reply_owner=_signal_reply_owner,   # was: "gateway" if _approval_queued_this_turn else "agent"
```

This closes exactly the duplicate-authority finding from
`BUG-162_SINGLE_SPEAKER_CLOSURE_AUDIT_20260807.md` §2.4: enforcement (§2
above) and observability (this section) now both key off
`action_lifecycle_result.reply_owner`, never off two independently-computed
predicates over the same log.

---

## 4. Confirmation / cancellation / callback paths — reviewed, no change

Per the design correction's explicit instruction not to force these through
`__approval_queued__` or re-architect them for symmetry alone:

- `route_confirmation_word()` / `route_cancellation_word()`
  (`core/action_gateway.py:2052`, `2513`) pre-empt `run_agent()`'s tool loop
  entirely — they are called from `app.py` before the Agent ever gets a
  turn for that message. There is no competing Agent reply to suppress,
  because the Agent is never invoked on this path. No `__approval_queued__`
  entry, no `_gateway_owned` check applies or is needed here.
- The Telegram callback path (`_handle_approval_callback_impl()`) already
  funnels every final message through the single `_deliver_callback_final()`
  chokepoint (`app.py:2515-2574`) — structurally one writer already, by a
  different (older, working) mechanism than the `tool_results_log` sentinel
  scan.

Both were reviewed as part of this spec (TC6 preflight §B) and their
existing regression suites re-run unmodified against current `app.py`
(unaffected by the WS2-only change, since it doesn't touch `app.py`):
`test_pr1_single_speaker_approval_ux.py` (15 tests, all pass) and
`test_single_speaker_fallback_and_duplication.py` (27/27 pass) — both stay
green as the required regression check for this section. No `app.py`
change proposed here.

---

## 5. Proposed integrator-side tests (Section C, E, G — app.py-dependent)

These cannot be added to the WS2 branch (they exercise the new `app.py`
logic in §§1-3 above, which doesn't exist yet on `origin/main`). The
integrator should add a new file, e.g. `test_tc6_app_reply_ownership.py`,
containing tests of this shape once the patch above is applied — mirroring
the existing `monkeypatch.setattr(app, "_queue_approval_detailed", ...)`
pattern already used in `test_turn_coordinator_task_runtime_integration.py`:

```python
"""TC6 — app.py integration: exact-contract reply ownership. Requires the
integrator patch in TC6_APP_INTEGRATOR_PATCH_SPEC.md to be applied first."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import app
from core.router.ownership_contracts import ActionLifecycleResult


def _lifecycle(reply_owner="gateway", state="pending"):
    return ActionLifecycleResult(
        contract_ref="c1", lifecycle_state=state, approval_state=state,
        execution_state="not_started", reply_owner=reply_owner,
    )


# ── C. Single speaker ──────────────────────────────────────────────────

def test_gateway_owned_current_turn_result_suppresses_agent(monkeypatch):
    """A tool_results_log entry correlated to THIS turn's contract, with a
    canonical action_lifecycle_result.reply_owner=='gateway', must suppress
    the Agent's own text — even if the Agent's text says something else."""
    # ... build a minimal run_agent()-shaped scenario (or call the extracted
    # _gateway_owned derivation directly, if factored into a small testable
    # helper) with tool_results_log = [{
    #     "tool": "__approval_queued__", "action_lifecycle_result": _lifecycle(),
    #     "lifecycle_result": SimpleNamespace(safe_user_message="פעולה ממתינה"),
    #     "owner_notified": False,
    # }]
    # assert the returned reply is the Gateway text, never Agent-generated text.


def test_agent_output_cannot_override_gateway_lifecycle_state(monkeypatch):
    """Even if the Agent's own final_reply claims success/failure, a
    gateway-owned current-turn entry must win."""


def test_owner_notified_true_suppresses_duplicate_channel_reply():
    """owner_notified=True → the function returns "" (already delivered via
    bot.send_message to the owner), never a second copy of the text."""


def test_owner_notified_false_returns_one_legacy_safe_user_message():
    """owner_notified=False → exactly one message, sourced from
    lifecycle_result.safe_user_message (unchanged legacy text)."""


def test_final_response_count_remains_one():
    """final_response_count in out_meta stays 1 for a gateway-owned turn."""


# ── E. Shared derivation ───────────────────────────────────────────────

def test_enforcement_and_ownership_signal_agree_on_same_entry(monkeypatch):
    """_gateway_owned (enforcement) and the OwnershipSignal's reply_owner
    (observability) must derive from the SAME tool_results_log entry's
    action_lifecycle_result — never disagree, by construction."""


def test_sentinel_presence_alone_cannot_claim_gateway_ownership():
    """A tool_results_log entry with tool=="__approval_queued__" but NO
    action_lifecycle_result (or one with reply_owner != "gateway") must
    NOT be treated as gateway-owned by either enforcement or the
    observability signal — closing BUG-162 §2.4's duplicate-authority gap
    at its root (a sentinel-only predicate can no longer independently
    claim ownership anywhere)."""


# ── Branch B — ownership read failure, full control-flow proof ─────────
# Demonstrates the actual chain: ownership read failure -> correlated
# fail-closed branch -> early deterministic return -> zero subsequent
# Agent response -> zero synthetic ActionLifecycleResult. Not just "the
# producer dict looks right" (§1's own unit-level shape) -- this proves the
# TOOL LOOP actually reacts to it before another Agent round can run.

def test_ownership_verification_failed_entry_triggers_branch_b_early_return(monkeypatch):
    """A tool_results_log entry correlated to THIS turn, tagged
    terminal_outcome=="APPROVAL_OWNERSHIP_VERIFICATION_FAILED" (Branch B),
    must trigger the SAME early, structural stop as a Branch A
    gateway-owned entry -- before tool_calls_made increments and before
    any further Claude API call/messages.append() is reached."""
    # tool_results_log = [{
    #     "tool": "__approval_queued__",
    #     "terminal_outcome": "APPROVAL_OWNERSHIP_VERIFICATION_FAILED",
    #     "content": "<the same legacy safe_user_message §1a/§1b/§1c already computed>",
    #     "owner_notified": False,
    #     "contract_id": "c1",   # exact-contract correlation still explicit
    #     # deliberately no "action_lifecycle_result" / "reply_owner" keys
    # }]
    # assert the function returns entry["content"] and that no further
    # Claude API call happens (mock the Anthropic client call and assert
    # call_count == 0 after this tool_results_log entry).


def test_ownership_verification_failed_produces_no_synthetic_lifecycle_result(monkeypatch):
    """Across the whole call — producer (_queue_approval_detailed_impl via
    §1) through the tool loop (§2) — no ActionLifecycleResult object (real
    or synthetic) is ever constructed for this turn. Patch
    ActionLifecycleResult.__init__ (or spy on core.lifecycle_projection.
    build_action_lifecycle_result) and assert it is never called on this
    path, proving the failure truly produces nothing fabricated rather
    than a well-hidden one."""


def test_ownership_verification_failed_owner_notified_true_suppresses_duplicate(monkeypatch):
    """Branch B's success-path variant (§1c): if the owner was already
    notified (bot.send_message succeeded) before the ownership check ran,
    the Branch B return must still be "" -- never a duplicate second
    message -- exactly mirroring Branch A's owner_notified short-circuit."""


def test_ownership_verification_failed_final_response_count_remains_one():
    """final_response_count in out_meta stays 1 for a Branch B turn, same
    as Branch A -- this is a safety stop, not a differently-counted
    response."""


def test_ownership_verification_failed_does_not_depend_on_pa01_state(monkeypatch):
    """The Branch B early return must fire identically regardless of
    get_pa01_enforcement_state() -- set it to 'off', 'shadow', and
    'enforce' in turn and assert the same early-return behavior in all
    three, proving this invariant does not rely on PA-01's own, separate,
    later, text-pattern-based mechanism."""


# ── G. Scope guards ──────────────────────────────────────────────────

def test_no_evidence_finalizer_behavior_change():
    """execution_status()/EvidenceResult call sites and behavior are
    byte-identical before/after this patch (diff-based assertion, or a
    direct call comparison against a known fixture)."""


def test_no_new_durable_state_or_lock_introduced():
    """Structural: this patch introduces no new persistence, no new lock,
    no new turn-state table — grep-based or import-based assertion."""
```

Plus the pre-existing regression suites, unmodified, must stay green after
the patch: `test_bug162_gateway_reply_owner_on_generic_block.py` (57/57),
`test_pr1_single_speaker_approval_ux.py`, `test_single_speaker_fallback_and_duplication.py`,
`test_action_gateway.py`, the full root `test_*.py` sweep, `core/router/`
and `core/` pytest suites, `smoke_tests.py`, `python3 -m compileall -q .`.

---

## 6. Scope guards (explicit, matching TC6's own exclusions)

This patch does **not**: touch `EvidenceResult`/`execution_status()`
enforcement (TC7); add durable turn state, locks, or multi-instance
ownership (TC8); touch `core/message_contract.py` or
`core/agent_message_formatter.py` rendering (TC9); touch router/builders/
resolvers (WS1, complete); edit any feature flag; touch `event_bus.py` or
`tma_api.py` (no concrete blocker was found in either — see TC6 preflight §F).
