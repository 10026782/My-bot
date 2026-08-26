#!/usr/bin/env python3
"""
test_tc7_b_rp5_gateway_sink_enforcement.py — RP5 enforcement at ActionGateway's
two execution-shadow sink sites.

Gap this closes: PR #1036 wired RP5 enforcement into app.py's canonical
general Agent-loop response path only (see test_rp5_evidence_enforcement.py).
core/action_gateway.py's own two observation sinks --
ActionGateway._execute_contract()'s _finish() (the universal boundary: direct
approve() callers, e.g. tma_api.py / route_override_word()) and
ActionGateway.approve_with_lifecycle_result()'s _finish() (the deferred
handoff seam for the Telegram callback-button and text confirm-word paths) --
called observe_claim_authorization_shadow() and discarded the decision same
as app.py's three sites did before TC7-B3/RP5. This file proves both sinks
now apply the identical accept/reject predicate app.py's RP5 block uses
(legacy_response_claim == "success" and not authorized, gated on
FEATURE_EVIDENCE_FINALIZER == "enforce"), and adds "mixed" evidence-status
coverage (core.claim_authorization.ClaimCategory.MIXED can never authorize a
"success" claim) that was previously untested anywhere in the RP5 suite.

Uses the real ActionGateway/ExecutionLedger, plus the same _contract/_rp5_state
fixture shapes test_tc7_rp5_gateway_execution_shadow.py uses (inlined here,
not imported -- that file executes its own suite and sys.exit()s at import
time). observe_claim_authorization_shadow itself is monkeypatched to a forced
return value (same spy-by-reassignment pattern that file already uses for
observe_shadow_finalizer) so each scenario
is deterministic regardless of the real regex/evidence classification of the
Gateway's own rendered text -- this file tests RP5's *enforcement wiring* at
the two sinks, not TC7-B1/B2's decision logic (already covered by
test_tc7_b3_claim_authorization_wiring.py / test_rp5_evidence_enforcement.py).

Run: python3 test_tc7_b_rp5_gateway_sink_enforcement.py
Pass condition: exit code 0, all assertions green.
"""

from __future__ import annotations

import contextlib
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
from core.anti_hallucination import _NO_TOOL_EVIDENCE_FALLBACK
from core.claim_authorization_shadow import ClaimAuthorizationShadowComparison

_passed = 0
_failed = 0

_VALID_RECORD_ID = "rec" + "A1B2C3D4E5F6G7"  # matches ^rec[A-Za-z0-9]{14}$


# Inlined rather than imported from test_tc7_rp5_gateway_execution_shadow.py --
# that file executes its own suite and sys.exit()s at import time, which
# would kill this process before this file's own checks ever ran.
def _contract(
    *, contract_id: str, canonical_user_id: str = "user-a",
    tool_name: str = "airtable_add", context_interrupted: bool = False,
) -> ActionContract:
    return ActionContract(
        contract_id=contract_id,
        tenant_id="tenant-a",
        canonical_user_id=canonical_user_id,
        tool_name=tool_name,
        normalized_payload={"table": "Leads", "fields": {"name": "Alice"}},
        business_action_fingerprint=f"fp-{contract_id}",
        origin_channel="telegram",
        origin_chat_id="chat-a",
        requires_approval=True,
        status="pending",
        created_at=time.time(),
        context_interrupted=context_interrupted,
    )


def _ok_executor(tool_name=None, tool_inputs=None, contract_id=None, identity=None):
    return {"ok": True, "tool": "airtable_add", "external_id": _VALID_RECORD_ID, "evidence": {}, "user_message": "נוסף"}


@contextlib.contextmanager
def _rp5_state(value: str | None):
    """Set/restore FEATURE_EVIDENCE_FINALIZER for the duration of a block."""
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


def check(desc: str, condition: bool) -> None:
    global _passed, _failed
    if condition:
        print(f"✅ {desc}")
        _passed += 1
    else:
        print(f"❌ {desc}")
        _failed += 1


def _forced_comparison(
    *, legacy_response_claim: str, authorized: bool,
    canonical_claim: str = "neutral", evidence_status: str = "failure",
) -> ClaimAuthorizationShadowComparison:
    return ClaimAuthorizationShadowComparison(
        evidence_status=evidence_status,
        lifecycle_state=None,
        canonical_claim=canonical_claim,
        authorization_reason=None if authorized else "forced_test_reason",
        legacy_response_claim=legacy_response_claim,
        legacy_rp4_mismatch=not authorized,
        divergent=not authorized,
        divergence_code="match" if authorized else "claim_category_mismatch",
    )


def _force(comparison: ClaimAuthorizationShadowComparison):
    """Monkeypatch ag_module's imported name (global lookup at call time,
    same pattern test_tc7_rp5_gateway_execution_shadow.py uses for
    observe_shadow_finalizer) to a fixed return value."""
    original = ag_module.observe_claim_authorization_shadow

    def _fake(legacy_comparison, *, lifecycle_state, state):
        return comparison

    ag_module.observe_claim_authorization_shadow = _fake
    return original


# ═════════════════════════════════════════════════════════════════
# 1 — direct approve() sink (_execute_contract._finish): enforce blocks
# an unauthorized "success" claim.
# ═════════════════════════════════════════════════════════════════

with _rp5_state("enforce"):
    gw = ActionGateway(ledger=ExecutionLedger())
    contract = _contract(contract_id="direct-block-1")
    gw._ledger.save(contract)
    gw._tool_executor = _ok_executor
    original = _force(_forced_comparison(legacy_response_claim="success", authorized=False))
    try:
        reply_text = gw.approve("direct-block-1", approver="user-a", approver_role="owner")
        check("(1) direct approve(): unauthorized 'success' claim replaced with the fallback",
              reply_text == _NO_TOOL_EVIDENCE_FALLBACK)
    finally:
        ag_module.observe_claim_authorization_shadow = original

# authorized -> unchanged.
with _rp5_state("enforce"):
    gw = ActionGateway(ledger=ExecutionLedger())
    contract = _contract(contract_id="direct-ok-1")
    gw._ledger.save(contract)
    gw._tool_executor = _ok_executor
    original = _force(_forced_comparison(legacy_response_claim="success", authorized=True,
                                          canonical_claim="success", evidence_status="verified_write_success"))
    try:
        reply_text = gw.approve("direct-ok-1", approver="user-a", approver_role="owner")
        check("(2) direct approve(): authorized 'success' claim reaches the caller unchanged",
              reply_text != _NO_TOOL_EVIDENCE_FALLBACK and "הושלמ" in reply_text)
    finally:
        ag_module.observe_claim_authorization_shadow = original

# state=shadow -> observation only, never blocks even when unauthorized.
with _rp5_state("shadow"):
    gw = ActionGateway(ledger=ExecutionLedger())
    contract = _contract(contract_id="direct-shadow-1")
    gw._ledger.save(contract)
    gw._tool_executor = _ok_executor
    original = _force(_forced_comparison(legacy_response_claim="success", authorized=False))
    try:
        reply_text = gw.approve("direct-shadow-1", approver="user-a", approver_role="owner")
        check("(3) direct approve(): state='shadow' never blocks (observation only)",
              reply_text != _NO_TOOL_EVIDENCE_FALLBACK)
    finally:
        ag_module.observe_claim_authorization_shadow = original

# non-"success" legacy claim -> never blocked even when unauthorized.
with _rp5_state("enforce"):
    gw = ActionGateway(ledger=ExecutionLedger())
    contract = _contract(contract_id="direct-nonsuccess-1")
    gw._ledger.save(contract)
    gw._tool_executor = _ok_executor
    original = _force(_forced_comparison(legacy_response_claim="pending", authorized=False))
    try:
        reply_text = gw.approve("direct-nonsuccess-1", approver="user-a", approver_role="owner")
        check("(4) direct approve(): non-'success' legacy claim (e.g. 'pending') is never blocked",
              reply_text != _NO_TOOL_EVIDENCE_FALLBACK)
    finally:
        ag_module.observe_claim_authorization_shadow = original

# mixed evidence + 'success' legacy claim -> blocked (MIXED never authorizes success).
with _rp5_state("enforce"):
    gw = ActionGateway(ledger=ExecutionLedger())
    contract = _contract(contract_id="direct-mixed-1")
    gw._ledger.save(contract)
    gw._tool_executor = _ok_executor
    original = _force(_forced_comparison(legacy_response_claim="success", authorized=False,
                                          canonical_claim="mixed", evidence_status="mixed"))
    try:
        reply_text = gw.approve("direct-mixed-1", approver="user-a", approver_role="owner")
        check("(5) direct approve(): mixed evidence + 'success' claim -> blocked",
              reply_text == _NO_TOOL_EVIDENCE_FALLBACK)
    finally:
        ag_module.observe_claim_authorization_shadow = original


# ═════════════════════════════════════════════════════════════════
# 2 — deferred wrapper sink (approve_with_lifecycle_result._finish):
# same predicate, applied against the re-rendered safe_user_message,
# preserving every other ApprovalLifecycleResult field.
# ═════════════════════════════════════════════════════════════════

with _rp5_state("enforce"):
    gw = ActionGateway(ledger=ExecutionLedger())
    contract = _contract(contract_id="wrapped-block-1")
    gw._ledger.save(contract)
    gw._tool_executor = _ok_executor
    original = _force(_forced_comparison(legacy_response_claim="success", authorized=False))
    try:
        result = gw.approve_with_lifecycle_result("wrapped-block-1", approver="user-a", approver_role="owner")
        check("(6) wrapped path: unauthorized 'success' claim replaced with the fallback",
              result.safe_user_message == _NO_TOOL_EVIDENCE_FALLBACK)
        check("(6) wrapped path: canonical_state untouched by the replacement",
              result.canonical_state != "" and result.canonical_state is not None)
        check("(6) wrapped path: contract_id untouched", result.contract_id == "wrapped-block-1")
    finally:
        ag_module.observe_claim_authorization_shadow = original

with _rp5_state("enforce"):
    gw = ActionGateway(ledger=ExecutionLedger())
    contract = _contract(contract_id="wrapped-ok-1")
    gw._ledger.save(contract)
    gw._tool_executor = _ok_executor
    original = _force(_forced_comparison(legacy_response_claim="success", authorized=True,
                                          canonical_claim="success", evidence_status="verified_write_success"))
    try:
        result = gw.approve_with_lifecycle_result("wrapped-ok-1", approver="user-a", approver_role="owner")
        check("(7) wrapped path: authorized 'success' claim reaches the caller unchanged",
              result.safe_user_message != _NO_TOOL_EVIDENCE_FALLBACK)
    finally:
        ag_module.observe_claim_authorization_shadow = original

with _rp5_state("shadow"):
    gw = ActionGateway(ledger=ExecutionLedger())
    contract = _contract(contract_id="wrapped-shadow-1")
    gw._ledger.save(contract)
    gw._tool_executor = _ok_executor
    original = _force(_forced_comparison(legacy_response_claim="success", authorized=False))
    try:
        result = gw.approve_with_lifecycle_result("wrapped-shadow-1", approver="user-a", approver_role="owner")
        check("(8) wrapped path: state='shadow' never blocks (observation only)",
              result.safe_user_message != _NO_TOOL_EVIDENCE_FALLBACK)
    finally:
        ag_module.observe_claim_authorization_shadow = original

with _rp5_state("enforce"):
    gw = ActionGateway(ledger=ExecutionLedger())
    contract = _contract(contract_id="wrapped-nonsuccess-1")
    gw._ledger.save(contract)
    gw._tool_executor = _ok_executor
    original = _force(_forced_comparison(legacy_response_claim="failure", authorized=False))
    try:
        result = gw.approve_with_lifecycle_result("wrapped-nonsuccess-1", approver="user-a", approver_role="owner")
        check("(9) wrapped path: non-'success' legacy claim is never blocked",
              result.safe_user_message != _NO_TOOL_EVIDENCE_FALLBACK)
    finally:
        ag_module.observe_claim_authorization_shadow = original

# mixed_with_unknown evidence + 'success' legacy claim -> blocked.
with _rp5_state("enforce"):
    gw = ActionGateway(ledger=ExecutionLedger())
    contract = _contract(contract_id="wrapped-mixed-1")
    gw._ledger.save(contract)
    gw._tool_executor = _ok_executor
    original = _force(_forced_comparison(legacy_response_claim="success", authorized=False,
                                          canonical_claim="mixed", evidence_status="mixed_with_unknown"))
    try:
        result = gw.approve_with_lifecycle_result("wrapped-mixed-1", approver="user-a", approver_role="owner")
        check("(10) wrapped path: mixed_with_unknown evidence + 'success' claim -> blocked",
              result.safe_user_message == _NO_TOOL_EVIDENCE_FALLBACK)
    finally:
        ag_module.observe_claim_authorization_shadow = original


# ═════════════════════════════════════════════════════════════════
# 3 — text confirm-word path (route_confirmation_word -> the same deferred
# sink) reaches the identical enforcement, not just the callback-button
# entry point directly exercised above.
# ═════════════════════════════════════════════════════════════════

with _rp5_state("enforce"):
    gw = ActionGateway(ledger=ExecutionLedger())
    contract = _contract(contract_id="confirmword-block-1", canonical_user_id="user-b")
    gw._ledger.save(contract)
    gw._tool_executor = _ok_executor
    original = _force(_forced_comparison(legacy_response_claim="success", authorized=False))
    try:
        msg = gw.route_confirmation_word(
            "user-b", approver_role="owner",
            live_contracts=[contract], use_session_bookmark=False,
        )
        check("(11) text confirm-word path reaches the same enforcement", msg == _NO_TOOL_EVIDENCE_FALLBACK)
    finally:
        ag_module.observe_claim_authorization_shadow = original


print(f"\n{_passed} passed, {_failed} failed")
if _failed:
    sys.exit(1)
