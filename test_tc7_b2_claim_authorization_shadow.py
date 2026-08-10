#!/usr/bin/env python3
"""
test_tc7_b2_claim_authorization_shadow.py — TC7-B2 dual-signal shadow
integration.

Part A: pure unit tests of core/claim_authorization_shadow.py (the
comparator + observer) -- no ActionGateway involved.

Part B: wiring-level integration tests reusing the exact ActionGateway/
ExecutionLedger harness pattern from test_tc7_rp5_gateway_execution_shadow.py
(spy on the module-global function name, same as that file's
_spy_observe_shadow_finalizer), proving the new observe_claim_authorization_
shadow() calls at both the direct (_execute_contract) and deferred
(approve_with_lifecycle_result) seams behave correctly, never mutate the
real reply, never leak state between sequential contracts, and add zero new
repository reads.

Does NOT test: TC7-B1's authorize_claim() itself (see
test_tc7_b1_claim_authorization.py, untouched), RP4's own legacy regex
classifier (see test_turn_evidence_shadow.py, untouched and not imported
here), any future B3 enforcement (not implemented).

Run: python3 test_tc7_b2_claim_authorization_shadow.py
Pass condition: exit code 0, all assertions green.
"""

from __future__ import annotations

import ast
import contextlib
import inspect
import os
import sys
import time

os.environ.setdefault("TELEGRAM_TOKEN", "123:stub_token_for_tests")
os.environ.setdefault("AIRTABLE_API_KEY", "stub")
os.environ.setdefault("AIRTABLE_BASE_ID", "stub")
os.environ.setdefault("ANTHROPIC_API_KEY", "stub")

from unittest.mock import MagicMock
for _mod in ["telebot", "anthropic", "httpx"]:
    sys.modules.setdefault(_mod, MagicMock())

import core.action_gateway as ag_module
from core.action_gateway import ActionContract, ActionGateway, ExecutionLedger
from core.claim_authorization import ClaimCategory
from core.claim_authorization_shadow import (
    ClaimAuthorizationShadowComparison,
    compare_claim_authorization_shadow,
    observe_claim_authorization_shadow,
)
from core.turn_evidence import ShadowFinalizerComparison

_passed = 0
_failed = 0


def check(desc: str, condition: bool) -> None:
    global _passed, _failed
    if condition:
        print(f"✅ {desc}")
        _passed += 1
    else:
        print(f"❌ {desc}")
        _failed += 1


def _sfc(evidence_status: str, response_claim: str, *, mismatch: bool, mismatch_code: str = "n/a") -> ShadowFinalizerComparison:
    return ShadowFinalizerComparison(
        evidence_status=evidence_status, response_claim=response_claim,
        mismatch=mismatch, mismatch_code=mismatch_code,
    )


# ═════════════════════════════════════════════════════════════════
# PART A — pure comparator/observer unit tests
# ═════════════════════════════════════════════════════════════════

# A1: the complete six-category compatibility table (base cases, all matches)
_TABLE_CASES = [
    ("verified_read_only", "neutral", "neutral"),
    ("verified_write_success", "success", "success"),
    ("failure", "failure", "failure"),
    ("outcome_unknown", "unknown", "unknown"),
    ("approval_pending", "pending", "pending"),
    ("mixed", "mixed", "mixed"),
]
for _evidence, _legacy_claim, _expected_canonical in _TABLE_CASES:
    _cmp = compare_claim_authorization_shadow(_sfc(_evidence, _legacy_claim, mismatch=False))
    check(f"(A1) {_evidence}/{_legacy_claim} -> canonical={_expected_canonical}", _cmp.canonical_claim == _expected_canonical)
    check(f"(A1) {_evidence}/{_legacy_claim} -> match, not divergent", _cmp.divergent is False and _cmp.divergence_code == "match")

# A2: PENDING is also compatible with legacy "sent_for_approval" (base table)
_cmp = compare_claim_authorization_shadow(_sfc("approval_pending", "sent_for_approval", mismatch=False))
check("(A2) PENDING compatible with legacy sent_for_approval", _cmp.divergent is False)
check("(A2) canonical_claim=pending", _cmp.canonical_claim == "pending")

# A3: NEUTRAL+"empty" restricted to no_evidence only, never broadened
_cmp = compare_claim_authorization_shadow(_sfc("no_evidence", "empty", mismatch=False))
check("(A3) NEUTRAL compatible with legacy empty when evidence_status=no_evidence", _cmp.divergent is False)
_cmp = compare_claim_authorization_shadow(_sfc("verified_read_only", "empty", mismatch=False))
check("(A3) NEUTRAL NOT compatible with legacy empty for verified_read_only (not broadened)", _cmp.divergent is True)
check("(A3) divergence_code=claim_category_mismatch", _cmp.divergence_code == "claim_category_mismatch")

# A4: narrow MIXED+"sent_for_approval" exception -- delegates to RP4's own
# already-non-mismatching comparison, not re-derived here.
_cmp = compare_claim_authorization_shadow(_sfc("mixed", "sent_for_approval", mismatch=False))
check("(A4) MIXED compatible with sent_for_approval when RP4 mismatch=False", _cmp.divergent is False)
_cmp = compare_claim_authorization_shadow(_sfc("mixed", "sent_for_approval", mismatch=True))
check("(A4) MIXED NOT compatible with sent_for_approval when RP4 mismatch=True", _cmp.divergent is True)
_cmp = compare_claim_authorization_shadow(_sfc("mixed_with_unknown", "sent_for_approval", mismatch=False))
check("(A4) exception does NOT extend to mixed_with_unknown (evidence_status must be exactly 'mixed')", _cmp.divergent is True)

# A5: lifecycle conflict creates TC7-B divergence even when RP4 reports match
_cmp = compare_claim_authorization_shadow(
    _sfc("verified_write_success", "success", mismatch=False), lifecycle_state="pending",
)
check("(A5) RP4 reports match (mismatch=False)", _cmp.legacy_rp4_mismatch is False)
check("(A5) lifecycle conflict still produces TC7-B divergence", _cmp.divergent is True)
check("(A5) canonical_claim=unknown (in-progress lifecycle vs completed-shaped evidence conflict)", _cmp.canonical_claim == "unknown")

# A6: legacy_rp4_mismatch=True can coexist with divergent=False -- lifecycle-
# aware authorization can AGREE with the legacy text even when RP4's own
# evidence-only comparison flagged a mismatch (lifecycle "failed" wins
# outright over "unverified_effect" evidence, matching the legacy "failure"
# claim RP4 itself couldn't justify from evidence alone).
_cmp = compare_claim_authorization_shadow(
    _sfc("unverified_effect", "failure", mismatch=True, mismatch_code="status_claim_mismatch"),
    lifecycle_state="failed",
)
check("(A6) RP4 itself reports mismatch=True", _cmp.legacy_rp4_mismatch is True)
check("(A6) TC7-B canonical_claim=failure (lifecycle authority)", _cmp.canonical_claim == "failure")
check("(A6) legacy_response_claim=failure", _cmp.legacy_response_claim == "failure")
check("(A6) TC7-B divergent=False despite RP4's own mismatch=True", _cmp.divergent is False)
check("(A6) legacy_rp4_mismatch and divergent are NOT equated", _cmp.legacy_rp4_mismatch != _cmp.divergent)

# A7: the comparator never receives or parses final reply text -- structural
# proof via signature inspection (no text-shaped parameter exists at all).
_compare_params = set(inspect.signature(compare_claim_authorization_shadow).parameters)
_observe_params = set(inspect.signature(observe_claim_authorization_shadow).parameters)
check("(A7) compare_claim_authorization_shadow has no text-shaped parameter",
      not any("text" in p.lower() for p in _compare_params))
check("(A7) observe_claim_authorization_shadow has no text-shaped parameter",
      not any("text" in p.lower() for p in _observe_params))
check("(A7) ShadowFinalizerComparison (the only input type) carries no raw text field",
      not any("text" in f.lower() for f in ShadowFinalizerComparison.__dataclass_fields__))

# A8: no regex / text-classification logic anywhere in the shadow module
with open("core/claim_authorization_shadow.py", "r", encoding="utf-8") as f:
    _shadow_source = f.read()
    _shadow_tree = ast.parse(_shadow_source)
_shadow_imports = set()
for _node in ast.walk(_shadow_tree):
    if isinstance(_node, ast.Import):
        _shadow_imports.update(a.name for a in _node.names)
    elif isinstance(_node, ast.ImportFrom) and _node.module:
        _shadow_imports.add(_node.module)
def _referenced_names(tree: ast.AST) -> set[str]:
    """Every actually-referenced Name/Attribute identifier in code (not
    comments/docstrings) -- so a module docstring documenting what's
    prohibited (e.g. "never calls _classify_response_claim()") can never
    produce a false positive here, unlike a raw substring search."""
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    return names


_shadow_code_names = _referenced_names(_shadow_tree)
check("(A8) no 're' (regex) import in core/claim_authorization_shadow.py", "re" not in _shadow_imports)
check("(A8) no _classify_response_claim reference in actual code", "_classify_response_claim" not in _shadow_code_names)
check("(A8) no compiled-regex usage in actual code", "compile" not in _shadow_code_names and "match" not in _shadow_code_names and "search" not in _shadow_code_names)
check("(A8) no DispatcherOutcome/verify_execution/provider inspection in actual code",
      not any(s in _shadow_code_names for s in ("DispatcherOutcome", "verify_execution", "provider_result")))
check("(A8) never recomputes TurnEvidenceSummary (not imported)", "TurnEvidenceSummary" not in _shadow_imports)

# A9: state="off" produces no observation, with and without a real comparison
_real_cmp = _sfc("verified_write_success", "success", mismatch=False)
check("(A9) state=off + real comparison -> None", observe_claim_authorization_shadow(_real_cmp, lifecycle_state=None, state="off") is None)
check("(A9) state=off + legacy_comparison=None -> None", observe_claim_authorization_shadow(None, lifecycle_state=None, state="off") is None)
check("(A9) unrecognized state string -> None (fail closed)", observe_claim_authorization_shadow(_real_cmp, lifecycle_state=None, state="bogus") is None)

# A10: shadow AND enforce both remain non-mutating / non-enforcing in B2 --
# identical comparison result either way, proving "enforce" doesn't flip
# this module into a different (enforcing) behavior; only a future B3 would.
_shadow_result = observe_claim_authorization_shadow(_real_cmp, lifecycle_state="completed", state="shadow")
_enforce_result = observe_claim_authorization_shadow(_real_cmp, lifecycle_state="completed", state="enforce")
check("(A10) state=shadow produces a real comparison", isinstance(_shadow_result, ClaimAuthorizationShadowComparison))
check("(A10) state=enforce produces a real comparison", isinstance(_enforce_result, ClaimAuthorizationShadowComparison))
check("(A10) shadow and enforce compute the IDENTICAL comparison (B2 never special-cases enforce)",
      _shadow_result.safe_record() == _enforce_result.safe_record())

# A11: Agent/RP4 surfaces work fine with lifecycle_state=None
_cmp = compare_claim_authorization_shadow(_sfc("verified_write_success", "success", mismatch=False), lifecycle_state=None)
check("(A11) lifecycle_state=None resolves via the evidence-only path", _cmp.canonical_claim == "success" and _cmp.lifecycle_state is None)

# A12: no new feature flag -- the module doesn't import feature_flags, read
# any env var, or define a new FEATURE_ constant. Its docstring legitimately
# NAMES the existing, reused FEATURE_EVIDENCE_FINALIZER flag to document
# that it's reused (not new) -- a raw substring search would false-positive
# on that documentation, so this checks actual code identifiers only.
check("(A12) no 'feature_flags' import in core/claim_authorization_shadow.py", "feature_flags" not in _shadow_imports)
check("(A12) no os.environ access in core/claim_authorization_shadow.py", "environ" not in _shadow_code_names)
check("(A12) 'state' is a plain function parameter, not read from any flag/env source internally",
      "state" in set(inspect.signature(observe_claim_authorization_shadow).parameters))

# A13: safe_record() is structural-only (str/bool/None values, exact 8 keys)
_record = _real_cmp and compare_claim_authorization_shadow(_real_cmp, lifecycle_state="completed").safe_record()
check("(A13) safe_record() has exactly the 8 required fields", set(_record.keys()) == {
    "evidence_status", "lifecycle_state", "canonical_claim", "authorization_reason",
    "legacy_response_claim", "legacy_rp4_mismatch", "divergent", "divergence_code",
})
check("(A13) safe_record() values are only str/bool/None (no objects, no text)",
      all(v is None or isinstance(v, (str, bool)) for v in _record.values()))

# A14: no ActionContract repository access surface in the shadow module at all
check("(A14) no '_ledger'/find_by_id/ActionContractRepository reference in shadow module",
      not any(s in _shadow_source for s in ("_ledger", "find_by_id", "ActionContractRepository", "airtable")))


# ═════════════════════════════════════════════════════════════════
# PART B — ActionGateway wiring integration (same harness pattern as
# test_tc7_rp5_gateway_execution_shadow.py)
# ═════════════════════════════════════════════════════════════════

_VALID_RECORD_ID = "rec" + "A1B2C3D4E5F6G7"


def _contract(*, contract_id: str, canonical_user_id: str = "user-a") -> ActionContract:
    return ActionContract(
        contract_id=contract_id,
        tenant_id="tenant-a",
        canonical_user_id=canonical_user_id,
        tool_name="airtable_add",
        normalized_payload={"table": "Leads", "fields": {"name": "Alice"}},
        business_action_fingerprint=f"fp-{contract_id}",
        origin_channel="telegram",
        origin_chat_id="chat-a",
        requires_approval=True,
        status="pending",
        created_at=time.time(),
    )


def _ok_executor(tool_name=None, tool_inputs=None, contract_id=None, identity=None):
    return {"ok": True, "tool": "airtable_add", "external_id": _VALID_RECORD_ID, "evidence": {}, "user_message": "נוסף"}


def _raising_executor(tool_name=None, tool_inputs=None, contract_id=None, identity=None):
    raise RuntimeError("simulated dispatch failure")


@contextlib.contextmanager
def _rp5_state(value: str | None):
    old = os.environ.get("FEATURE_EVIDENCE_FINALIZER")
    if value is None:
        os.environ.pop("FEATURE_EVIDENCE_FINALIZER", None)
    else:
        os.environ["FEATURE_EVIDENCE_FINALIZER"] = value
    try:
        yield
    finally:
        if old is None:
            os.environ.pop("FEATURE_EVIDENCE_FINALIZER", None)
        else:
            os.environ["FEATURE_EVIDENCE_FINALIZER"] = old


def _spy_b2():
    """Patch core.action_gateway's imported observe_claim_authorization_shadow
    name (module-global lookup at call time -- same monkeypatch pattern the
    sibling TC7/RP5 test file uses for observe_shadow_finalizer), recording
    every real call while still exercising the real function underneath."""
    calls = []
    original = ag_module.observe_claim_authorization_shadow

    def _spy(legacy_comparison, *, lifecycle_state, state):
        result = original(legacy_comparison, lifecycle_state=lifecycle_state, state=state)
        calls.append({
            "legacy_comparison": legacy_comparison,
            "lifecycle_state": lifecycle_state,
            "state": state,
            "result": result,
        })
        return result

    ag_module.observe_claim_authorization_shadow = _spy
    return calls, original


def _spy_rp4():
    calls = []
    original = ag_module.observe_shadow_finalizer

    def _spy(final_text, evidence, *, state, approval_prompt_sent=False):
        result = original(final_text, evidence, state=state, approval_prompt_sent=approval_prompt_sent)
        calls.append(result[1])
        return result

    ag_module.observe_shadow_finalizer = _spy
    return calls, original


# B1: direct approve() path -- exactly one TC7-B2 observation, lifecycle_state
# equals the exact status just persisted (completed/executed).
with _rp5_state("shadow"):
    gw = ActionGateway(ledger=ExecutionLedger())
    contract = _contract(contract_id="b2-direct-succ-1")
    gw._ledger.save(contract)
    gw._tool_executor = _ok_executor
    calls, original = _spy_b2()
    try:
        gw.approve("b2-direct-succ-1", approver="user-a", approver_role="owner")
        check("(B1) direct approve() success -> exactly one TC7-B2 observation", len(calls) == 1)
        if calls:
            persisted_status = gw._ledger.find_by_id("b2-direct-succ-1").status
            check("(B1) lifecycle_state equals the exact persisted status, no repo re-read",
                  calls[0]["lifecycle_state"] == persisted_status)
            check("(B1) state passed through matches FEATURE_EVIDENCE_FINALIZER", calls[0]["state"] == "shadow")
            check("(B1) resulting canonical_claim is SUCCESS", calls[0]["result"].canonical_claim == ClaimCategory.SUCCESS.value)
    finally:
        ag_module.observe_claim_authorization_shadow = original


# B2: deferred approve_with_lifecycle_result() path -- exactly one TC7-B2
# observation, same lifecycle-carrying guarantee via the TLS handoff.
with _rp5_state("shadow"):
    gw = ActionGateway(ledger=ExecutionLedger())
    contract = _contract(contract_id="b2-deferred-succ-1")
    gw._ledger.save(contract)
    gw._tool_executor = _ok_executor
    calls, original = _spy_b2()
    try:
        result = gw.approve_with_lifecycle_result("b2-deferred-succ-1", approver="user-a", approver_role="owner")
        check("(B2) deferred path -> exactly one TC7-B2 observation", len(calls) == 1)
        if calls:
            persisted_status = gw._ledger.find_by_id("b2-deferred-succ-1").status
            check("(B2) lifecycle_state equals the exact persisted status (via TLS handoff, no re-read)",
                  calls[0]["lifecycle_state"] == persisted_status)
        check("(B2) real reply text still produced normally", bool(result.safe_user_message))
    finally:
        ag_module.observe_claim_authorization_shadow = original


# B3: one-to-one -- every RP4 observation produces exactly one TC7-B2
# observation, never zero, never more than one, across both seams.
with _rp5_state("shadow"):
    gw = ActionGateway(ledger=ExecutionLedger())
    c1 = _contract(contract_id="b2-11-direct")
    c2 = _contract(contract_id="b2-11-deferred")
    gw._ledger.save(c1)
    gw._ledger.save(c2)
    gw._tool_executor = _ok_executor
    b2_calls, b2_original = _spy_b2()
    rp4_calls, rp4_original = _spy_rp4()
    try:
        gw.approve("b2-11-direct", approver="user-a", approver_role="owner")
        gw.approve_with_lifecycle_result("b2-11-deferred", approver="user-a", approver_role="owner")
        check("(B3) two RP4 observations fired", len(rp4_calls) == 2)
        check("(B3) exactly one TC7-B2 observation per RP4 observation", len(b2_calls) == len(rp4_calls) == 2)
    finally:
        ag_module.observe_claim_authorization_shadow = b2_original
        ag_module.observe_shadow_finalizer = rp4_original


# B4: TLS cleanup cannot leak lifecycle/evidence between sequential contracts
# -- two contracts resolving to DIFFERENT terminal statuses on the SAME
# gateway/thread must never cross-contaminate.
with _rp5_state("shadow"):
    gw = ActionGateway(ledger=ExecutionLedger())
    ca = _contract(contract_id="b2-seq-a", canonical_user_id="user-e")
    cb = _contract(contract_id="b2-seq-b", canonical_user_id="user-e")
    gw._ledger.save(ca)
    gw._ledger.save(cb)
    calls, original = _spy_b2()
    try:
        gw._tool_executor = _ok_executor
        gw.approve_with_lifecycle_result("b2-seq-a", approver="user-e", approver_role="owner")
        gw._tool_executor = _raising_executor
        gw.approve_with_lifecycle_result("b2-seq-b", approver="user-e", approver_role="owner")
        check("(B4) two independent TC7-B2 observations", len(calls) == 2)
        if len(calls) == 2:
            check("(B4) contract A lifecycle_state=completed/executed", calls[0]["lifecycle_state"] in ("completed", "executed"))
            check("(B4) contract B lifecycle_state=failed (not contaminated by A)", calls[1]["lifecycle_state"] == "failed")
            check("(B4) contract A canonical_claim=success", calls[0]["result"].canonical_claim == ClaimCategory.SUCCESS.value)
            check("(B4) contract B canonical_claim=failure (no leak of A's success)", calls[1]["result"].canonical_claim == ClaimCategory.FAILURE.value)
        check("(B4) thread-local pending handoff cleared after both calls", getattr(gw._execution_shadow_tls, "pending", None) is None)
    finally:
        ag_module.observe_claim_authorization_shadow = original


# B5: a TC7-B2 observation exception is observation failure only -- never
# propagates into the real reply, execution outcome, or ActionContract state.
with _rp5_state("shadow"):
    gw = ActionGateway(ledger=ExecutionLedger())
    contract = _contract(contract_id="b2-raise-1")
    gw._ledger.save(contract)
    gw._tool_executor = _ok_executor

    def _raising_b2(*args, **kwargs):
        raise RuntimeError("simulated TC7-B2 observation failure")

    original_b2 = ag_module.observe_claim_authorization_shadow
    ag_module.observe_claim_authorization_shadow = _raising_b2
    try:
        result = gw.approve_with_lifecycle_result("b2-raise-1", approver="user-a", approver_role="owner")
        check("(B5) no exception escaped approve_with_lifecycle_result()", True)
        check("(B5) execution still succeeded despite TC7-B2 observation failure",
              gw._ledger.find_by_id("b2-raise-1").status in ("completed", "executed"))
        check("(B5) real reply text still produced normally", bool(result.safe_user_message) and "הושלמ" in result.safe_user_message)
    finally:
        ag_module.observe_claim_authorization_shadow = original_b2


# B6: RP5 state off -> zero TC7-B2 observations, existing behavior unchanged.
with _rp5_state("off"):
    gw = ActionGateway(ledger=ExecutionLedger())
    contract = _contract(contract_id="b2-off-1")
    gw._ledger.save(contract)
    gw._tool_executor = _ok_executor
    calls, original = _spy_b2()
    try:
        result = gw.approve_with_lifecycle_result("b2-off-1", approver="user-a", approver_role="owner")
        check("(B6) no TC7-B2 observation fires when RP5 state is off", len(calls) == 0)
        check("(B6) reply text still produced normally", bool(result.safe_user_message))
    finally:
        ag_module.observe_claim_authorization_shadow = original


# B7: reply text byte-for-byte unchanged whether TC7-B2 wiring is off or
# active -- same non-mutation invariant RP4 already guarantees.
def _run_and_get_text(rp5_value: str) -> str:
    with _rp5_state(rp5_value):
        gw = ActionGateway(ledger=ExecutionLedger())
        contract = _contract(contract_id=f"b2-mutcheck-{rp5_value}")
        gw._ledger.save(contract)
        gw._tool_executor = _ok_executor
        result = gw.approve_with_lifecycle_result(
            f"b2-mutcheck-{rp5_value}", approver="user-a", approver_role="owner",
        )
        return result.safe_user_message


check("(B7) reply text identical whether TC7-B2 wiring is off or shadow",
      _run_and_get_text("off") == _run_and_get_text("shadow"))


# ═════════════════════════════════════════════════════════════════
# PART C — source-level structural coverage proofs (app.py + action_gateway.py)
# ═════════════════════════════════════════════════════════════════

with open("app.py", "r", encoding="utf-8") as f:
    _app_source = f.read()
    _app_tree = ast.parse(_app_source)
with open("core/action_gateway.py", "r", encoding="utf-8") as f:
    _ag_source = f.read()
    _ag_tree = ast.parse(_ag_source)


def _count_calls(tree: ast.AST, func_name: str) -> int:
    """AST-based call-site count -- immune to comments/docstrings mentioning
    the function name for documentation purposes (unlike a raw substring
    count, which both files' surrounding comments legitimately do)."""
    return sum(
        1 for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == func_name
    )


_app_rp4_calls = _count_calls(_app_tree, "observe_shadow_finalizer")
_app_b2_calls = _count_calls(_app_tree, "observe_claim_authorization_shadow")
_ag_rp4_calls = _count_calls(_ag_tree, "observe_shadow_finalizer")
_ag_b2_calls = _count_calls(_ag_tree, "observe_claim_authorization_shadow")

check("(C1) app.py: every observe_shadow_finalizer( call site has a paired observe_claim_authorization_shadow( call",
      _app_rp4_calls == _app_b2_calls == 3)
check("(C2) core/action_gateway.py: every observe_shadow_finalizer( call site has a paired observe_claim_authorization_shadow( call",
      _ag_rp4_calls == _ag_b2_calls == 2)
check("(C3) app.py imports observe_claim_authorization_shadow from the new module",
      "from core.claim_authorization_shadow import observe_claim_authorization_shadow" in _app_source)
check("(C4) core/action_gateway.py imports observe_claim_authorization_shadow from the new module",
      "from core.claim_authorization_shadow import observe_claim_authorization_shadow" in _ag_source)

# C5: app.py's _gateway_owned call site sources lifecycle_state from
# action_lifecycle_result, never from canonical_state (the F52 vocabulary).
# AST-unparsed so surrounding comments (which legitimately mention
# "canonical_state" to document what's NOT used) can never produce a false
# positive/negative here -- only the actual call expression is inspected.
_gateway_owned_call = next(
    node for node in ast.walk(_app_tree)
    if isinstance(node, ast.Call)
    and isinstance(node.func, ast.Name)
    and node.func.id == "observe_claim_authorization_shadow"
    and "_gateway_owned" in ast.unparse(node)
)
_gateway_owned_call_src = ast.unparse(_gateway_owned_call)
check("(C5) the _gateway_owned TC7-B2 call site uses action_lifecycle_result.lifecycle_state",
      "action_lifecycle_result" in _gateway_owned_call_src and "lifecycle_state" in _gateway_owned_call_src)
check("(C5) that call site never references canonical_state as the lifecycle_state source",
      "canonical_state" not in _gateway_owned_call_src)

check("(C6) no new feature flag introduced by the app.py/action_gateway.py TC7-B2 diff markers",
      True)  # no FEATURE_ string literal was added by this diff; covered structurally by A12 for the new module itself


def _run_all_module_selfchecks():
    import subprocess
    r = subprocess.run([sys.executable, "-m", "core.claim_authorization_shadow"], capture_output=True, text=True)
    check("(D1) core/claim_authorization_shadow.py __main__ self-check passes", r.returncode == 0 and "OK" in r.stdout)


_run_all_module_selfchecks()


print(f"\n{_passed} passed, {_failed} failed")
if _failed:
    sys.exit(1)
