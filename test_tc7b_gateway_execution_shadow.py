#!/usr/bin/env python3
"""
test_tc7b_gateway_execution_shadow.py — TC7-B RP4/RP5 execution-shadow wiring.

Covers the new seam only: TC7-A's EvidenceResult stays execution-evidence
authority (see test_tc7a_exact_contract_evidence.py, untouched); this file
covers core/turn_evidence.py::project_evidence_result() and its wiring into
core/action_gateway.py's ActionGateway._execute_contract()/
_persist_execution_status() (evidence capture, log-level independence,
fail-closed projection failure) and ActionGateway.approve_with_lifecycle_
result() (the actual seam that observes shadow evidence against the REAL
user-visible reply text -- both the Telegram callback-button path and the
text confirm-word path funnel through this one method; NOT against
_execute_contract()'s own internal return string, which neither caller
actually shows to the user).

Does NOT test: RP5 enforcement (not implemented), final_reply mutation (RP4
invariant explicitly forbids it and is asserted here to still hold), the
sheets_append/Tasks canonicalization bug (separate follow-up, untouched).

Run: python3 test_tc7b_gateway_execution_shadow.py
Pass condition: exit code 0, all assertions green.
"""

from __future__ import annotations

import contextlib
import logging
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
from core.dispatcher_outcome import DispatcherOutcome
from core.router.ownership_contracts import EvidenceResult
from core.turn_evidence import TurnEvidenceSummary, project_evidence_result

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
# Helpers
# ═════════════════════════════════════════════════════════════════

_VALID_RECORD_ID = "rec" + "A1B2C3D4E5F6G7"  # matches ^rec[A-Za-z0-9]{14}$


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


def _raising_executor(tool_name=None, tool_inputs=None, contract_id=None, identity=None):
    raise RuntimeError("simulated dispatch failure")


def _outcome_unknown_executor(tool_name=None, tool_inputs=None, contract_id=None, identity=None):
    return DispatcherOutcome(result="outcome_unknown", user_message="", error="timeout")


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


def _spy_observe_shadow_finalizer():
    """Patch core.action_gateway's imported observe_shadow_finalizer name
    (module-global lookup at call time, same monkeypatch pattern used by
    test_tc7a_exact_contract_evidence.py's _spy_evidence_for_contract) so
    every real call from approve_with_lifecycle_result()'s closure is
    recorded, while still exercising the real function (and its real log
    line) underneath."""
    calls = []
    original = ag_module.observe_shadow_finalizer

    def _spy(final_text, evidence, *, state, approval_prompt_sent=False):
        result = original(final_text, evidence, state=state, approval_prompt_sent=approval_prompt_sent)
        calls.append({
            "final_text": final_text,
            "evidence": evidence,
            "state": state,
            "approval_prompt_sent": approval_prompt_sent,
            "comparison": result[1],
        })
        return result

    ag_module.observe_shadow_finalizer = _spy
    return calls, original


class _CaptureHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


# ═════════════════════════════════════════════════════════════════
# 0: core/turn_evidence.py::project_evidence_result() — pure mapping
# ═════════════════════════════════════════════════════════════════

r = project_evidence_result(EvidenceResult(result="success", verified=True, evidence_ref=_VALID_RECORD_ID))
check("(0a) success+verified -> verified_writes=1", r.verified_writes == 1)
check("(0a) success+verified -> classification=verified_write_success", r.classification() == "verified_write_success")
check("(0a) single-component summary (fresh, nothing else set)", r.failed_calls == 0 and r.outcome_unknown == 0 and r.unverified_effects == 0)

r = project_evidence_result(EvidenceResult(result="failed", error="boom"))
check("(0b) failed -> failed_calls=1", r.failed_calls == 1)
check("(0b) failed -> classification=failure", r.classification() == "failure")

r = project_evidence_result(EvidenceResult(result="outcome_unknown", outcome_unknown=True))
check("(0c) outcome_unknown -> outcome_unknown=1", r.outcome_unknown == 1)
check("(0c) outcome_unknown -> classification=outcome_unknown", r.classification() == "outcome_unknown")

# Never convert an unverified success-shaped object into verified success --
# TC7-A itself never constructs this combination, but the projection must
# still fail closed if it somehow saw one.
r = project_evidence_result(EvidenceResult(result="success", verified=False))
check("(0d) success without verified=True -> NOT verified_writes", r.verified_writes == 0)
check("(0d) success without verified=True -> falls closed to unverified_effect", r.classification() == "unverified_effect")

# Two calls never share state (fresh instance every time).
r1 = project_evidence_result(EvidenceResult(result="success", verified=True))
r2 = project_evidence_result(EvidenceResult(result="failed"))
check("(0e) project_evidence_result always returns a fresh TurnEvidenceSummary", r1 is not r2)


# ═════════════════════════════════════════════════════════════════
# 1: Gateway execution success -> verified_write_success, claim-compatible
# ═════════════════════════════════════════════════════════════════

with _rp5_state("shadow"):
    gw = ActionGateway(ledger=ExecutionLedger())
    contract = _contract(contract_id="succ-1")
    gw._ledger.save(contract)
    gw._tool_executor = _ok_executor
    calls, original = _spy_observe_shadow_finalizer()
    try:
        result = gw.approve_with_lifecycle_result(
            "succ-1", approver="user-a", approver_role="owner",
        )
        check("(1) execution succeeded (contract completed/executed)",
              gw._ledger.find_by_id("succ-1").status in ("completed", "executed"))
        check("(1) exactly one shadow observation fired", len(calls) == 1)
        if calls:
            cmp = calls[0]["comparison"]
            check("(1) evidence_status=verified_write_success", cmp.evidence_status == "verified_write_success")
            check("(1) observed final_text is the REAL returned message, not _execute_contract()'s own string",
                  calls[0]["final_text"] == result.safe_user_message)
            check("(1) claim is compatible with the evidence (no mismatch)", cmp.mismatch is False)
            check("(1) approval_prompt_sent=False for execution-resolution turns", calls[0]["approval_prompt_sent"] is False)
    finally:
        ag_module.observe_shadow_finalizer = original


# ═════════════════════════════════════════════════════════════════
# 2 & 3: both live entry paths reach the identical seam
# ═════════════════════════════════════════════════════════════════

with _rp5_state("shadow"):
    # Scenario 3 — callback-button path: app.py's _handle_approval_callback_impl
    # calls approve_with_lifecycle_result() directly (app.py:2842).
    gw = ActionGateway(ledger=ExecutionLedger())
    contract = _contract(contract_id="button-1")
    gw._ledger.save(contract)
    gw._tool_executor = _ok_executor
    calls, original = _spy_observe_shadow_finalizer()
    try:
        gw.approve_with_lifecycle_result("button-1", approver="user-a", approver_role="owner")
        check("(3) callback-button path reaches the seam", len(calls) == 1)
        if calls:
            check("(3) callback-button path -> verified_write_success", calls[0]["comparison"].evidence_status == "verified_write_success")
    finally:
        ag_module.observe_shadow_finalizer = original

    # Scenario 2 — text confirm-word path: route_confirmation_word() ->
    # _resolve_single_contract() -> approve_with_lifecycle_result() (same seam).
    gw = ActionGateway(ledger=ExecutionLedger())
    contract = _contract(contract_id="confirm-1", canonical_user_id="user-b")
    gw._ledger.save(contract)
    gw._tool_executor = _ok_executor
    calls, original = _spy_observe_shadow_finalizer()
    try:
        gw.route_confirmation_word(
            "user-b", approver_role="owner",
            live_contracts=[contract], use_session_bookmark=False,
        )
        check("(2) text confirm-word path reaches the identical seam", len(calls) == 1)
        if calls:
            check("(2) confirm-word path -> verified_write_success", calls[0]["comparison"].evidence_status == "verified_write_success")
    finally:
        ag_module.observe_shadow_finalizer = original


# ═════════════════════════════════════════════════════════════════
# 4: Failed execution -> failure
# ═════════════════════════════════════════════════════════════════

with _rp5_state("shadow"):
    gw = ActionGateway(ledger=ExecutionLedger())
    contract = _contract(contract_id="fail-1")
    gw._ledger.save(contract)
    gw._tool_executor = _raising_executor
    calls, original = _spy_observe_shadow_finalizer()
    try:
        gw.approve_with_lifecycle_result("fail-1", approver="user-a", approver_role="owner")
        check("(4) failed execution -> exactly one observation", len(calls) == 1)
        if calls:
            check("(4) evidence_status=failure", calls[0]["comparison"].evidence_status == "failure")
    finally:
        ag_module.observe_shadow_finalizer = original


# ═════════════════════════════════════════════════════════════════
# 5: Ambiguous execution -> outcome_unknown
# ═════════════════════════════════════════════════════════════════

with _rp5_state("shadow"):
    gw = ActionGateway(ledger=ExecutionLedger())
    contract = _contract(contract_id="unk-1")
    gw._ledger.save(contract)
    gw._tool_executor = _outcome_unknown_executor
    calls, original = _spy_observe_shadow_finalizer()
    try:
        gw.approve_with_lifecycle_result("unk-1", approver="user-a", approver_role="owner")
        check("(5) ambiguous execution -> exactly one observation", len(calls) == 1)
        if calls:
            check("(5) evidence_status=outcome_unknown", calls[0]["comparison"].evidence_status == "outcome_unknown")
        check("(5) mixed_with_unknown never appears from a single-contract resolution",
              not calls or calls[0]["comparison"].evidence_status != "mixed_with_unknown")
    finally:
        ag_module.observe_shadow_finalizer = original


# ═════════════════════════════════════════════════════════════════
# 6: Reconfirmation-required branch, no execution -> no observation
# ═════════════════════════════════════════════════════════════════

with _rp5_state("shadow"):
    gw = ActionGateway(ledger=ExecutionLedger())
    contract = _contract(contract_id="reconf-1", canonical_user_id="user-c", context_interrupted=True)
    gw._ledger.save(contract)
    gw._tool_executor = _ok_executor
    calls, original = _spy_observe_shadow_finalizer()
    try:
        msg = gw.route_confirmation_word(
            "user-c", approver_role="owner",
            live_contracts=[contract], use_session_bookmark=False,
        )
        check("(6) reconfirmation requested, not executed", "לאשר אותה" in msg)
        check("(6) contract still pending (never executed)", gw._ledger.find_by_id("reconf-1").status == "pending")
        check("(6) no shadow observation for a non-executed turn", len(calls) == 0)
    finally:
        ag_module.observe_shadow_finalizer = original


# ═════════════════════════════════════════════════════════════════
# 7: Multi-contract disambiguation branch, no execution -> no observation
# ═════════════════════════════════════════════════════════════════

with _rp5_state("shadow"):
    gw = ActionGateway(ledger=ExecutionLedger())
    c1 = _contract(contract_id="amb-1", canonical_user_id="user-d")
    c2 = _contract(contract_id="amb-2", canonical_user_id="user-d")
    gw._ledger.save(c1)
    gw._ledger.save(c2)
    gw._tool_executor = _ok_executor
    calls, original = _spy_observe_shadow_finalizer()
    try:
        gw.route_confirmation_word(
            "user-d", approver_role="owner",
            live_contracts=[c1, c2], use_session_bookmark=False,
        )
        check("(7) neither contract executed", gw._ledger.find_by_id("amb-1").status == "pending"
              and gw._ledger.find_by_id("amb-2").status == "pending")
        check("(7) no shadow observation for a disambiguation-only turn", len(calls) == 0)
    finally:
        ag_module.observe_shadow_finalizer = original


# ═════════════════════════════════════════════════════════════════
# 8: Two sequential contracts, same user -> two independent observations,
# never combined/stale-correlated (also proves the thread-local handoff
# clears itself between calls rather than leaking a prior contract's
# evidence into a later, unrelated call on the same object/thread).
# ═════════════════════════════════════════════════════════════════

with _rp5_state("shadow"):
    gw = ActionGateway(ledger=ExecutionLedger())
    ca = _contract(contract_id="seq-a", canonical_user_id="user-e")
    cb = _contract(contract_id="seq-b", canonical_user_id="user-e")
    gw._ledger.save(ca)
    gw._ledger.save(cb)
    calls, original = _spy_observe_shadow_finalizer()
    try:
        gw._tool_executor = _ok_executor
        gw.approve_with_lifecycle_result("seq-a", approver="user-e", approver_role="owner")
        gw._tool_executor = _raising_executor
        gw.approve_with_lifecycle_result("seq-b", approver="user-e", approver_role="owner")
        check("(8) two independent observations, not merged into one", len(calls) == 2)
        if len(calls) == 2:
            check("(8) each call gets its own fresh TurnEvidenceSummary instance",
                  calls[0]["evidence"] is not calls[1]["evidence"])
            check("(8) contract A -> success", calls[0]["comparison"].evidence_status == "verified_write_success")
            check("(8) contract B -> failure (not contaminated by A's success)", calls[1]["comparison"].evidence_status == "failure")
    finally:
        ag_module.observe_shadow_finalizer = original

    # A THIRD, unrelated call that never executes anything must not pick up
    # any stale leftover from A/B above.
    calls2, original2 = _spy_observe_shadow_finalizer()
    try:
        c_noop = _contract(contract_id="seq-c-noop", canonical_user_id="user-e", context_interrupted=True)
        gw._ledger.save(c_noop)
        gw.route_confirmation_word(
            "user-e", approver_role="owner",
            live_contracts=[c_noop], use_session_bookmark=False,
        )
        check("(8b) a later non-executing call never inherits a prior call's evidence", len(calls2) == 0)
    finally:
        ag_module.observe_shadow_finalizer = original2


# ═════════════════════════════════════════════════════════════════
# 9: evidence_for_contract() raises while RP5 shadow active -> unverified_effect,
# original reply still returned, no exception escapes.
# ═════════════════════════════════════════════════════════════════

with _rp5_state("shadow"):
    gw = ActionGateway(ledger=ExecutionLedger())
    contract = _contract(contract_id="raise-1")
    gw._ledger.save(contract)
    gw._tool_executor = _ok_executor

    def _raising_evidence_for_contract(contract_id, *, dispatcher_outcome=None):
        raise RuntimeError("simulated projection failure")

    gw.evidence_for_contract = _raising_evidence_for_contract
    calls, original = _spy_observe_shadow_finalizer()
    try:
        result = gw.approve_with_lifecycle_result("raise-1", approver="user-a", approver_role="owner")
        check("(9) no exception escaped approve_with_lifecycle_result()", True)  # reaching here proves it
        check("(9) execution still succeeded despite projection failure",
              gw._ledger.find_by_id("raise-1").status in ("completed", "executed"))
        check("(9) original Gateway reply still returned (not blanked/replaced)",
              bool(result.safe_user_message) and "הושלמ" in result.safe_user_message)
        check("(9) exactly one shadow observation still fired (fail-closed, not silently dropped)", len(calls) == 1)
        if calls:
            check("(9) evidence_status=unverified_effect", calls[0]["comparison"].evidence_status == "unverified_effect")
    finally:
        ag_module.observe_shadow_finalizer = original


# ═════════════════════════════════════════════════════════════════
# 10: evidence_for_contract() returns None while RP5 shadow active ->
# same fail-closed unverified_effect.
# ═════════════════════════════════════════════════════════════════

with _rp5_state("shadow"):
    gw = ActionGateway(ledger=ExecutionLedger())
    contract = _contract(contract_id="none-1")
    gw._ledger.save(contract)
    gw._tool_executor = _ok_executor

    def _none_evidence_for_contract(contract_id, *, dispatcher_outcome=None):
        return None

    gw.evidence_for_contract = _none_evidence_for_contract
    calls, original = _spy_observe_shadow_finalizer()
    try:
        result = gw.approve_with_lifecycle_result("none-1", approver="user-a", approver_role="owner")
        check("(10) execution still succeeded despite projection returning None",
              gw._ledger.find_by_id("none-1").status in ("completed", "executed"))
        check("(10) exactly one shadow observation still fired", len(calls) == 1)
        if calls:
            check("(10) evidence_status=unverified_effect (never manufactured success)", calls[0]["comparison"].evidence_status == "unverified_effect")
    finally:
        ag_module.observe_shadow_finalizer = original


# ═════════════════════════════════════════════════════════════════
# 11: Logger independence — INFO vs WARNING must yield identical shadow
# classification; only the informational [TC7A][ExecutionEvidence] log may
# disappear at WARNING.
# ═════════════════════════════════════════════════════════════════

_ag_logger = logging.getLogger("core.action_gateway")
_original_level = _ag_logger.level

for level_name, level in (("INFO", logging.INFO), ("WARNING", logging.WARNING)):
    with _rp5_state("shadow"):
        _ag_logger.setLevel(level)
        handler = _CaptureHandler()
        handler.setLevel(logging.DEBUG)
        _ag_logger.addHandler(handler)
        gw = ActionGateway(ledger=ExecutionLedger())
        contract = _contract(contract_id=f"loglevel-{level_name}")
        gw._ledger.save(contract)
        gw._tool_executor = _ok_executor
        calls, original = _spy_observe_shadow_finalizer()
        try:
            gw.approve_with_lifecycle_result(
                f"loglevel-{level_name}", approver="user-a", approver_role="owner",
            )
            check(f"(11 {level_name}) shadow observation still fires regardless of logger level", len(calls) == 1)
            if calls:
                check(
                    f"(11 {level_name}) classification is verified_write_success",
                    calls[0]["comparison"].evidence_status == "verified_write_success",
                )
            tc7a_info_lines = [
                r for r in handler.records
                if r.levelno == logging.INFO and "[TC7A][ExecutionEvidence]" in r.getMessage()
            ]
            if level == logging.INFO:
                check("(11 INFO) [TC7A][ExecutionEvidence] informational log IS present at INFO", len(tc7a_info_lines) >= 1)
            else:
                check("(11 WARNING) [TC7A][ExecutionEvidence] informational log disappears at WARNING (cosmetic-only)", len(tc7a_info_lines) == 0)
        finally:
            ag_module.observe_shadow_finalizer = original
            _ag_logger.removeHandler(handler)

_ag_logger.setLevel(_original_level)

# Direct comparison: same scenario, both levels, identical classification.
_results_by_level = {}
for level_name, level in (("INFO", logging.INFO), ("WARNING", logging.WARNING)):
    with _rp5_state("shadow"):
        _ag_logger.setLevel(level)
        gw = ActionGateway(ledger=ExecutionLedger())
        contract = _contract(contract_id=f"cmp-{level_name}")
        gw._ledger.save(contract)
        gw._tool_executor = _ok_executor
        calls, original = _spy_observe_shadow_finalizer()
        try:
            gw.approve_with_lifecycle_result(f"cmp-{level_name}", approver="user-a", approver_role="owner")
            _results_by_level[level_name] = calls[0]["comparison"].evidence_status if calls else None
        finally:
            ag_module.observe_shadow_finalizer = original
_ag_logger.setLevel(_original_level)
check(
    "(11) INFO and WARNING produce the IDENTICAL EvidenceFinalizerShadow classification",
    _results_by_level.get("INFO") == _results_by_level.get("WARNING") == "verified_write_success",
)


# ═════════════════════════════════════════════════════════════════
# 12: RP5 state OFF — new shadow seam does not activate; existing Gateway
# behavior (execution, persistence, returned text) is unchanged.
# ═════════════════════════════════════════════════════════════════

with _rp5_state("off"):
    gw = ActionGateway(ledger=ExecutionLedger())
    contract = _contract(contract_id="off-1")
    gw._ledger.save(contract)
    gw._tool_executor = _ok_executor
    calls, original = _spy_observe_shadow_finalizer()
    try:
        result = gw.approve_with_lifecycle_result("off-1", approver="user-a", approver_role="owner")
        check("(12) execution still succeeds with RP5 off", gw._ledger.find_by_id("off-1").status in ("completed", "executed"))
        check("(12) no shadow observation fires when RP5 state is off", len(calls) == 0)
        check("(12) reply text still produced normally", bool(result.safe_user_message))
    finally:
        ag_module.observe_shadow_finalizer = original


# ═════════════════════════════════════════════════════════════════
# 13: Original reply text is byte-for-byte unchanged by the shadow observer
# (RP4 non-mutation invariant, preserved at this new seam too).
# ═════════════════════════════════════════════════════════════════

def _run_and_get_text(rp5_value: str) -> str:
    with _rp5_state(rp5_value):
        gw = ActionGateway(ledger=ExecutionLedger())
        contract = _contract(contract_id=f"mutcheck-{rp5_value}")
        gw._ledger.save(contract)
        gw._tool_executor = _ok_executor
        result = gw.approve_with_lifecycle_result(
            f"mutcheck-{rp5_value}", approver="user-a", approver_role="owner",
        )
        return result.safe_user_message


text_off = _run_and_get_text("off")
text_shadow = _run_and_get_text("shadow")
check(
    "(13) reply text is byte-for-byte identical whether RP5 shadow is off or on",
    text_off == text_shadow,
)


# ═════════════════════════════════════════════════════════════════
# Summary
# ═════════════════════════════════════════════════════════════════

print(f"\n{'═'*60}")
print(f"TC7-B execution-shadow wiring: {_passed}/{_passed + _failed} passed")
if _failed:
    print(f"FAILED: {_failed} test(s)")
sys.exit(0 if _failed == 0 else 1)
