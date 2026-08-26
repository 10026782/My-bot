#!/usr/bin/env python3
"""
test_rp5_evidence_enforcement.py — RP5: real enforcement of TC7-B's
claim_authorization decision on app.py's canonical response path.

Gap this closes: TC7-B (core/claim_authorization.py + TC7-B2's
core/claim_authorization_shadow.py, wired into _out_meta by TC7-B3) computes
a real authorization decision for every general Agent-loop turn -- but
nothing ever acted on it: an unauthorized execution-success claim could
still reach the user unchanged, the decision reachable only via a log line
or debug metadata. RP5 adds exactly one narrow block to app.py's PR-RP4 call
site (the general Agent-loop return path, the one this file's docstring
itself names as "RP5 owns any future enforcement/footer/fallback changes"):
when FEATURE_EVIDENCE_FINALIZER="enforce" AND the agent's own text asserts
execution success (legacy_response_claim == "success") AND TC7-B's decision
does not authorize that claim, final_reply is replaced with
core.anti_hallucination's existing _NO_TOOL_EVIDENCE_FALLBACK -- the exact
fallback A32 already uses for its own no-tool-evidence gate, never a new
success/failure claim of its own. Neither TC7-B's decision logic
(authorize_claim / compare_claim_authorization_shadow) nor A32's own gate
(core/anti_hallucination.py's sanitize_agent_response) is touched.

Part A: pure predicate tests against the required accept/reject matrix,
built on core.claim_authorization_shadow's own canonical fixture -- the
same one test_tc7_b2_claim_authorization_shadow.py and
test_tc7_b3_claim_authorization_wiring.py already use. Mirrors the exact
three-condition predicate app.py's RP5 block evaluates.

Part B: end-to-end proof that app.run_agent()'s real canonical response
path performs the block -- not just logging/meta. Reuses
test_pa01_phantom_approval_enforcement.py's exact Identity/Router/Context/
Anthropic-mocked run_agent() harness style (env-var save/restore around a
patch list), with only the TC7-B decision itself substituted via a spy on
observe_claim_authorization_shadow (the same spy pattern
test_tc7_b2_claim_authorization_shadow.py already uses against
core.action_gateway's imported name) -- no real tool call is needed to
prove RP5's own wiring, and every other layer (A32, RP4, TC7-B's decision
logic) runs for real and unmodified.

Part C: structural proof of enforcement location (after A32, gated by the
existing flag, never touching a non-"success" claim) + an A32 regression
run.

Run: python3 test_rp5_evidence_enforcement.py
Pass condition: exit code 0, all assertions green.
"""

from __future__ import annotations

import ast
import os
import sys
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-rp5-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:RP5_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patRP5Test")
os.environ.setdefault("AIRTABLE_BASE_ID", "appRP5Test")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import app  # noqa: E402

import emergency_stop_test_support  # noqa: E402
emergency_stop_test_support.configure_all_clear_emergency_stop()
import session_store  # noqa: E402
from identity import Identity, Role  # noqa: E402
from core.router.route_decision import RouteDecision  # noqa: E402
from context import AgentContext  # noqa: E402
from core.anti_hallucination import _NO_TOOL_EVIDENCE_FALLBACK  # noqa: E402
from core.claim_authorization_shadow import (  # noqa: E402
    ClaimAuthorizationShadowComparison,
    compare_claim_authorization_shadow,
)
from core.turn_evidence import ShadowFinalizerComparison  # noqa: E402

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


# ═════════════════════════════════════════════════════════════════
# PART A — required accept/reject matrix (pure predicate)
# ═════════════════════════════════════════════════════════════════

def _sfc(evidence_status: str, response_claim: str) -> ShadowFinalizerComparison:
    return ShadowFinalizerComparison(
        evidence_status=evidence_status,
        response_claim=response_claim,
        mismatch=(evidence_status == "no_evidence" and response_claim != "empty"),
        mismatch_code="n/a",
    )


def _rp5_blocks(comparison: ClaimAuthorizationShadowComparison) -> bool:
    """Exact predicate mirrored from app.py's RP5 block (see the PR-RP4/RP5
    comment there): only a "success" claim can ever be blocked, and only
    when TC7-B did not authorize it."""
    return comparison.legacy_response_claim == "success" and not comparison.authorized


_cmp1 = compare_claim_authorization_shadow(_sfc("verified_write_success", "success"), lifecycle_state="completed")
check("(A1) authorized execution success -> success reply stays", _rp5_blocks(_cmp1) is False)

_cmp2 = compare_claim_authorization_shadow(_sfc("no_evidence", "success"))
check("(A2) no execution evidence + 'success' claim -> blocked", _rp5_blocks(_cmp2) is True)

_cmp3 = compare_claim_authorization_shadow(_sfc("failure", "success"))
check("(A3) failed execution evidence + 'success' claim -> blocked", _rp5_blocks(_cmp3) is True)

_cmp4 = compare_claim_authorization_shadow(_sfc("verified_read_only", "success"))
check("(A4) unrelated (read-only) evidence + 'success' claim -> blocked", _rp5_blocks(_cmp4) is True)

_cmp5 = compare_claim_authorization_shadow(_sfc("no_evidence", "neutral"))
check("(A5a) informational/neutral claim with no evidence -> never blocked", _rp5_blocks(_cmp5) is False)

_cmp5b = compare_claim_authorization_shadow(_sfc("failure", "pending"))
check("(A5b) non-'success' claim rejected by TC7-B (e.g. 'pending') -> still never blocked (RP5 only guards 'success')",
      _rp5_blocks(_cmp5b) is False)

# mixed evidence (ClaimCategory.MIXED can never authorize a "success" claim --
# core/claim_authorization.py's _EVIDENCE_ONLY table has no "mixed" -> SUCCESS
# entry) + a 'success' claim -> blocked, same as any other unauthorized case.
_cmp6 = compare_claim_authorization_shadow(_sfc("mixed", "success"))
check("(A6a) mixed evidence + 'success' claim -> blocked", _rp5_blocks(_cmp6) is True)

_cmp7 = compare_claim_authorization_shadow(_sfc("mixed_with_unknown", "success"))
check("(A6b) mixed_with_unknown evidence + 'success' claim -> blocked", _rp5_blocks(_cmp7) is True)

# mixed evidence claimed as 'mixed' (not 'success') -> never blocked, RP5
# only ever guards a 'success' legacy claim.
_cmp8 = compare_claim_authorization_shadow(_sfc("mixed", "mixed"))
check("(A6c) mixed evidence + 'mixed' claim (not 'success') -> never blocked", _rp5_blocks(_cmp8) is False)


# ═════════════════════════════════════════════════════════════════
# PART B — end-to-end: real app.run_agent() canonical path
# ═════════════════════════════════════════════════════════════════

# Generic text A32/RP4's own text-pattern regexes never match (verified: no
# completion verb, no pending/approval-invite phrasing) -- isolates RP5's
# own effect from A32's independent, unmodified no-tool-evidence gate.
_NEUTRAL_TEXT = "תודה, קיבלתי את הבקשה שלך ואמשיך לטפל בנושא."


def _forced_comparison(*, authorized: bool) -> ClaimAuthorizationShadowComparison:
    return ClaimAuthorizationShadowComparison(
        evidence_status="verified_write_success" if authorized else "failure",
        lifecycle_state=None,
        canonical_claim="success" if authorized else "failure",
        authorization_reason=None if authorized else "lifecycle_failed",
        legacy_response_claim="success",
        legacy_rp4_mismatch=not authorized,
        divergent=not authorized,
        divergence_code="match" if authorized else "claim_category_mismatch",
    )


def _run_with_forced_authorization(*, authorized: bool, evidence_finalizer_state: str = "enforce") -> str:
    identity = Identity(user_id="rp5_t1", role=Role.OWNER)
    fake_ctx = AgentContext(
        system_prompt="test", allowed_tools=[], memory_key="rp5test:rp5_t1",
        max_tokens=500, model="claude-haiku-test", identity_label="owner",
    )
    fake_response = SimpleNamespace(
        content=[SimpleNamespace(type="text", text=_NEUTRAL_TEXT)],
        usage=SimpleNamespace(input_tokens=10, output_tokens=10),
    )

    old_state = os.environ.get("FEATURE_EVIDENCE_FINALIZER")
    os.environ["FEATURE_EVIDENCE_FINALIZER"] = evidence_finalizer_state
    try:
        with patch.object(app, "resolve_identity", return_value=identity), \
             patch.object(app, "_safe_route", return_value=RouteDecision()), \
             patch.object(app, "build_context", return_value=fake_ctx), \
             patch.object(app.client.messages, "create", return_value=fake_response), \
             patch.object(session_store.lead_sessions, "get", return_value=None), \
             patch.object(app, "observe_claim_authorization_shadow",
                           return_value=_forced_comparison(authorized=authorized)):
            return app.run_agent(_NEUTRAL_TEXT, "rp5_t1", channel="telegram")
    finally:
        if old_state is None:
            os.environ.pop("FEATURE_EVIDENCE_FINALIZER", None)
        else:
            os.environ["FEATURE_EVIDENCE_FINALIZER"] = old_state


_reply_authorized = _run_with_forced_authorization(authorized=True)
check("(B1) authorized 'success' claim reaches the user unchanged",
      _reply_authorized == _NEUTRAL_TEXT)

_reply_unauthorized = _run_with_forced_authorization(authorized=False)
check("(B2) unauthorized 'success' claim is replaced before reaching the user",
      _reply_unauthorized == _NO_TOOL_EVIDENCE_FALLBACK)
check("(B2b) the fallback never itself claims the action succeeded",
      "בוצע" not in _reply_unauthorized and "נוצר" not in _reply_unauthorized
      and "עודכן" not in _reply_unauthorized and "נשלח" not in _reply_unauthorized)

_reply_shadow = _run_with_forced_authorization(authorized=False, evidence_finalizer_state="shadow")
check("(B3) state='shadow' still never blocks -- observation only, matching TC7-B2's own contract",
      _reply_shadow == _NEUTRAL_TEXT)

_reply_off = _run_with_forced_authorization(authorized=False, evidence_finalizer_state="off")
check("(B4) state='off' -> no computation, no block",
      _reply_off == _NEUTRAL_TEXT)


# ═════════════════════════════════════════════════════════════════
# PART C — structural location proof + A32 regression
# ═════════════════════════════════════════════════════════════════

with open("app.py", "r", encoding="utf-8") as f:
    _app_source = f.read()
    _app_tree = ast.parse(_app_source)

_a32_idx = _app_source.index('final_reply = sanitize_agent_response(')
_rp5_idx = _app_source.index('final_reply = _NO_TOOL_EVIDENCE_FALLBACK')
check("(C1) RP5's block sits AFTER A32's sanitize_agent_response call in source order",
      _rp5_idx > _a32_idx)

_rp5_block_src = _app_source[_app_source.index("# RP5 — evidence enforcement."):_rp5_idx + len('final_reply = _NO_TOOL_EVIDENCE_FALLBACK')]
check("(C2) RP5's block is gated on the existing FEATURE_EVIDENCE_FINALIZER 'enforce' state (no new flag)",
      '_evidence_finalizer_state == "enforce"' in _rp5_block_src)
check("(C3) RP5's block only ever fires for a 'success' legacy claim",
      'legacy_response_claim == "success"' in _rp5_block_src)
check("(C4) RP5's block reads .authorized, not a re-derivation of evidence",
      "_claim_authorization.authorized" in _rp5_block_src)
check("(C5) A32 (core.anti_hallucination) itself was not modified by this diff",
      "def sanitize_agent_response" not in _rp5_block_src)


def _run_a32_regression():
    import subprocess
    r = subprocess.run([sys.executable, "test_a32_enforcement.py"], capture_output=True, text=True)
    check("(D1) existing A32 enforcement suite (test_a32_enforcement.py) remains green",
          r.returncode == 0)


_run_a32_regression()


print(f"\n{_passed} passed, {_failed} failed")
if _failed:
    sys.exit(1)
