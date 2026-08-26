#!/usr/bin/env python3
"""
test_tc7_b3_claim_authorization_wiring.py — TC7-B3: wire TC7-B1's
authorize_claim() decision onto the turn's own recorded output.

Gap this closes: TC7-B1 (core/claim_authorization.py) computes a real
ClaimCategory decision; TC7-B2 (core/claim_authorization_shadow.py) compares
it against the legacy regex-derived claim -- but every existing call site
(app.py x3, core/action_gateway.py x2) discarded that comparison's return
value, so the decision was reachable only via a log line, never via the
turn's own output. TC7-B3 adds nothing to the decision logic itself (B1/B2
untouched except for one additive `.authorized` property) and does NOT
implement RP5 (no final_reply/footer/fallback mutation) -- it only makes the
already-computed decision land somewhere a caller or test can read it back:
_out_meta["claim_authorization"] at app.py's three canonical response-path
call sites.

Part A: unit tests of the required accept/reject matrix, built directly on
core.claim_authorization_shadow's own canonical fixture (ShadowFinalizerComparison
+ compare_claim_authorization_shadow), not a parallel framework -- the same
fixture test_tc7_b2_claim_authorization_shadow.py already uses.

Part B: structural regression proof that app.py's canonical response path
actually captures the decision instead of discarding it.

Run: python3 test_tc7_b3_claim_authorization_wiring.py
Pass condition: exit code 0, all assertions green.
"""

from __future__ import annotations

import ast
import sys

from core.claim_authorization_shadow import compare_claim_authorization_shadow
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


def _sfc(evidence_status: str, response_claim: str) -> ShadowFinalizerComparison:
    return ShadowFinalizerComparison(
        evidence_status=evidence_status,
        response_claim=response_claim,
        mismatch=(evidence_status == "no_evidence" and response_claim != "empty"),
        mismatch_code="n/a",
    )


# ═════════════════════════════════════════════════════════════════
# PART A — required accept/reject matrix
# ═════════════════════════════════════════════════════════════════

# 1. execution succeeded + matching evidence -> claim authorized.
_cmp1 = compare_claim_authorization_shadow(
    _sfc("verified_write_success", "success"), lifecycle_state="completed",
)
check("(A1) verified write + matching 'success' claim + completed lifecycle -> authorized",
      _cmp1.authorized is True and _cmp1.canonical_claim == "success")

# 2. no execution evidence -> success claim rejected.
_cmp2 = compare_claim_authorization_shadow(_sfc("no_evidence", "success"))
check("(A2) no evidence + 'success' claim -> rejected",
      _cmp2.authorized is False and _cmp2.canonical_claim == "neutral")

# 3. unrelated evidence -> claim rejected.
_cmp3 = compare_claim_authorization_shadow(_sfc("verified_read_only", "success"))
check("(A3) verified read (unrelated to a mutation claim) + 'success' claim -> rejected",
      _cmp3.authorized is False and _cmp3.canonical_claim == "neutral")

# 4. failed execution evidence -> success claim rejected.
_cmp4 = compare_claim_authorization_shadow(_sfc("failure", "success"))
check("(A4) failed execution evidence + 'success' claim -> rejected",
      _cmp4.authorized is False and _cmp4.canonical_claim == "failure")

# 5. non-execution informational claim that doesn't require evidence -> not broken.
_cmp5 = compare_claim_authorization_shadow(_sfc("no_evidence", "neutral"))
check("(A5) no evidence + neutral/informational claim -> still authorized",
      _cmp5.authorized is True)

# `authorized` is exactly the inverse of `divergent` for every case above --
# an additive property, not a second source of truth.
check("(A6) .authorized is always the exact inverse of .divergent",
      all((c.authorized is not c.divergent) for c in (_cmp1, _cmp2, _cmp3, _cmp4, _cmp5)))


# ═════════════════════════════════════════════════════════════════
# PART B — canonical response path actually captures the decision
# ═════════════════════════════════════════════════════════════════

with open("app.py", "r", encoding="utf-8") as f:
    _app_source = f.read()
    _app_tree = ast.parse(_app_source)


def _count_assigned_calls(tree: ast.AST, func_name: str) -> int:
    """Count call sites of func_name whose return value is assigned to a
    Name, not discarded as a bare expression statement."""
    count = 0
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == func_name
        ):
            count += 1
    return count


_assigned_calls = _count_assigned_calls(_app_tree, "observe_claim_authorization_shadow")
_total_calls = sum(
    1 for node in ast.walk(_app_tree)
    if isinstance(node, ast.Call)
    and isinstance(node.func, ast.Name)
    and node.func.id == "observe_claim_authorization_shadow"
)
check("(B1) app.py: all 3 observe_claim_authorization_shadow( call sites assign their return value",
      _total_calls == 3 and _assigned_calls == 3)

_capture_sites = _app_source.count(
    '_out_meta["claim_authorization"] = _claim_authorization.safe_record()'
)
check("(B2) app.py: all 3 call sites record the decision into _out_meta[\"claim_authorization\"]",
      _capture_sites == 3)

def _uses_claim_authorization_var(node: ast.AST) -> bool:
    return any(
        isinstance(n, ast.Name) and n.id == "_claim_authorization"
        for n in ast.walk(node)
    )


_reply_targets = {"final_reply", "safe_user_message"}
_reply_assignments_touching_claim_auth = [
    node for node in ast.walk(_app_tree)
    if isinstance(node, ast.Assign)
    and any(
        isinstance(t, ast.Name) and t.id in _reply_targets for t in node.targets
    )
    and _uses_claim_authorization_var(node.value)
]
check("(B3) TC7-B3 wiring never feeds _claim_authorization into final_reply/safe_user_message (not RP5)",
      _reply_assignments_touching_claim_auth == [])


def _run_module_selfcheck():
    import subprocess
    r = subprocess.run(
        [sys.executable, "-m", "core.claim_authorization_shadow"],
        capture_output=True, text=True,
    )
    check("(C1) core/claim_authorization_shadow.py __main__ self-check still passes",
          r.returncode == 0 and "OK" in r.stdout)


_run_module_selfcheck()


print(f"\n{_passed} passed, {_failed} failed")
if _failed:
    sys.exit(1)
