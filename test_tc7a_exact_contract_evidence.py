#!/usr/bin/env python3
"""
test_tc7a_exact_contract_evidence.py — TC7-A exact-contract evidence authority.

Covers:
  - core/evidence_projection.py::build_evidence_result_from_outcome()
    (pure construction: contract snapshot + same-turn DispatcherOutcome -> EvidenceResult)
  - core/action_gateway.py::ActionGateway.evidence_for_contract()
    (exact-contract-correlated projection, analogous in spirit to
    reply_ownership_for_contract() — never "latest contract for this user")
  - core/action_gateway.py::ActionGateway._execute_contract()'s wiring of the
    above into the real single choke point (_persist_execution_status())

Does NOT test: claim authorization / user-visible response replacement (not
built in TC7-A), FEATURE_EVIDENCE_FINALIZER enforcement (not flipped in
TC7-A), TurnEvidenceSummary/RP4/RP5 internals (untouched by this PR — see the
"regression, not new tests" note in the deliverable report).

Run: python3 test_tc7a_exact_contract_evidence.py
Pass condition: exit code 0, all assertions green.
"""

from __future__ import annotations

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

# core.action_gateway's TC7-A seam is gated behind
# logger.isEnabledFor(logging.INFO) (CodeRabbit round) -- production runs at
# INFO (every [ActionGateway]/[Approval] log line observed in the real
# deployment evidence for TC6 was INFO-level), but this script's default
# ambient level (no explicit config) would otherwise suppress it, silently
# skipping the seam entirely rather than testing it. Set explicitly so the
# tests below exercise the real runtime condition, not an artifact of this
# script's own default logging level.
logging.getLogger("core.action_gateway").setLevel(logging.INFO)

from core.action_gateway import ActionContract, ActionGateway, ExecutionLedger
from core.dispatcher_outcome import DispatcherOutcome
from core.evidence_projection import build_evidence_result, build_evidence_result_from_outcome
from core.router.ownership_contracts import EvidenceResult

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


def _contract(
    status: str, *, contract_id: str = "c1", canonical_user_id: str = "user-a",
    created_at: float | None = None, tool_name: str = "airtable_add",
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
        status=status,
        created_at=time.time() if created_at is None else created_at,
    )


# Real Airtable record ids must match ^rec[A-Za-z0-9]{14}$ — these are used
# everywhere a "real" Airtable evidence_ref is needed so tests exercise the
# actual canonical validator shape, not a placeholder that would only have
# passed under the old (too-narrow) top-level-external_id-only logic.
_REC_A = "rec" + "A1B2C3D4E5F6G7"
_REC_B = "rec" + "B2C3D4E5F6G7H8"


# ═════════════════════════════════════════════════════════════════
# 1-4, 6-8, 11: build_evidence_result_from_outcome() — pure construction
# ═════════════════════════════════════════════════════════════════

# Test 1: exact completed contract + verified provider evidence -> success
r = build_evidence_result_from_outcome(
    _contract("completed"),
    DispatcherOutcome(result="completed", user_message="ok", external_id=_REC_A),
)
check("(1) completed contract + real external_id -> result=success", r.result == "success")
check("(1) completed contract + real external_id -> verified=True", r.verified is True)
check("(1) evidence_ref carries the external_id", r.evidence_ref == _REC_A)
check("(1) outcome_unknown is False on real success", r.outcome_unknown is False)

# Test 2: completed contract WITHOUT provider evidence -> outcome_unknown, never success
r = build_evidence_result_from_outcome(
    _contract("completed"),
    DispatcherOutcome(result="completed", user_message="ok", external_id=""),
)
check("(2) completed contract, empty external_id -> never success", r.result != "success")
check("(2) completed contract, empty external_id -> outcome_unknown", r.result == "outcome_unknown")
check("(2) verified=False without a real evidence_ref", r.verified is False)

r = build_evidence_result_from_outcome(_contract("completed"), outcome=None)
check("(2b) completed contract, outcome=None -> falls back, never success", r.result != "success")
check("(2b) matches plain build_evidence_result(contract) fallback", r == build_evidence_result(_contract("completed")))

# Test 3: failed DispatcherOutcome -> failed evidence
r = build_evidence_result_from_outcome(
    _contract("failed"),
    DispatcherOutcome(result="failed", user_message="", error="boom"),
)
check("(3) failed outcome -> result=failed", r.result == "failed")
check("(3) failed outcome -> verified=False", r.verified is False)
check("(3) failed outcome -> error preserved", r.error == "boom")

# Test 4: outcome_unknown DispatcherOutcome -> outcome_unknown evidence
r = build_evidence_result_from_outcome(
    _contract("outcome_unknown"),
    DispatcherOutcome(result="outcome_unknown", user_message="", error="timeout"),
)
check("(4) ambiguous outcome -> result=outcome_unknown", r.result == "outcome_unknown")
check("(4) ambiguous outcome -> outcome_unknown flag True", r.outcome_unknown is True)
check("(4) ambiguous outcome -> never verified", r.verified is False)
check("(4) ambiguous outcome -> error preserved", r.error == "timeout")

# Test 6: pending contract -> never success
r = build_evidence_result_from_outcome(_contract("pending"), outcome=None)
check("(6) pending contract -> never success", r.result != "success")
check("(6) pending contract -> outcome_unknown", r.result == "outcome_unknown")

# Test 7: approved but not executed -> never success
r = build_evidence_result_from_outcome(_contract("approved"), outcome=None)
check("(7) approved-not-executed -> never success", r.result != "success")

# Test 8: rejected contract -> never success
r = build_evidence_result_from_outcome(_contract("rejected"), outcome=None)
check("(8) rejected contract -> never success", r.result != "success")

# Test 11: provider user_message with success wording cannot manufacture verified evidence
r = build_evidence_result_from_outcome(
    _contract("failed"),
    DispatcherOutcome(
        result="failed", user_message="✅ הצלחה מלאה! הפעולה בוצעה בהצלחה",
        error="actually failed", external_id="",
    ),
)
check("(11a) success-sounding user_message on a failed outcome -> still failed", r.result == "failed")
check("(11a) success-sounding user_message -> verified stays False", r.verified is False)

r = build_evidence_result_from_outcome(
    _contract("outcome_unknown"),
    DispatcherOutcome(
        result="outcome_unknown", user_message="✅ בוצע בהצלחה!", error="ambiguous",
    ),
)
check("(11b) success-sounding user_message on an unknown outcome -> still outcome_unknown", r.result == "outcome_unknown")

# Same check, but proving evidence_ref itself is never derived from user_message
# even when result IS completed — only outcome.external_id (a structured field)
# may ever populate it.
r = build_evidence_result_from_outcome(
    _contract("completed"),
    DispatcherOutcome(
        result="completed", user_message="נוצרה רשומה rec_should_not_be_used", external_id="",
    ),
)
check("(11c) completed + success-wording user_message but NO external_id -> never success", r.result != "success")
check("(11c) evidence_ref is empty, not scraped from user_message text", r.evidence_ref == "")


# ═════════════════════════════════════════════════════════════════
# 5, 9, 10, 12: ActionGateway.evidence_for_contract() — exact-contract API
# ═════════════════════════════════════════════════════════════════

# Fail-closed API contract, mirroring reply_ownership_for_contract()
gw = ActionGateway()
for blank_id in [None, "", "   ", "\t\n"]:
    check(
        f"evidence_for_contract(blank={blank_id!r}) -> None",
        gw.evidence_for_contract(blank_id) is None,
    )

gw = ActionGateway()
gw._ledger.save(_contract("completed", contract_id="known-1"))
check(
    "evidence_for_contract(unknown id) -> None (not outcome_unknown-with-content)",
    gw.evidence_for_contract("does-not-exist") is None,
)


class _RaisingRepository:
    def get(self, contract_id: str):
        raise RuntimeError("simulated repository outage")


gw_broken = ActionGateway(ledger=ExecutionLedger(repository=_RaisingRepository()))
try:
    gw_broken.evidence_for_contract("some-id")
    check("repository failure propagates (not swallowed into None)", False)
except RuntimeError:
    check("repository failure propagates (not swallowed into None)", True)

# Test 9: two contracts, same user — exact touched contract B must be used,
# regardless of A's created_at ordering (both "A newer" and "A older" cases).
for a_created, b_created, label in [(1000.0, 2000.0, "A older"), (2000.0, 1000.0, "A newer")]:
    gw = ActionGateway()
    gw._ledger.save(_contract("completed", contract_id="A", canonical_user_id="user-x", created_at=a_created))
    gw._ledger.save(_contract("completed", contract_id="B", canonical_user_id="user-x", created_at=b_created))

    result_b = gw.evidence_for_contract(
        "B", dispatcher_outcome=DispatcherOutcome(result="completed", user_message="", external_id=_REC_B),
    )
    check(f"(9 {label}) exact contract B used, not A -> evidence_ref=REC_B", result_b.evidence_ref == _REC_B)
    check(f"(9 {label}) B result is success (B's own outcome had real evidence)", result_b.result == "success")

    # The user-scoped "latest" projection is a DIFFERENT question and must
    # never be substituted for exact-contract lookup — demonstrate they can
    # disagree by construction (latest-for-user query never receives B's
    # outcome, so it can never itself claim verified success).
    latest = gw.execution_status("user-x")
    check(
        f"(9 {label}) user-scoped execution_status() never reports success "
        "(it never received the exact-contract outcome)",
        latest is None or latest.result != "success",
    )

# Test 10: stale/unrelated contract (A, genuinely completed) cannot satisfy
# evidence for the contract actually touched this turn (C, still pending).
gw = ActionGateway()
gw._ledger.save(_contract("completed", contract_id="A-stale", canonical_user_id="user-y", created_at=1.0))
# Simulate A's own (unrelated) real success being on record.
_ = gw.evidence_for_contract(
    "A-stale", dispatcher_outcome=DispatcherOutcome(result="completed", user_message="", external_id=_REC_A),
)
gw._ledger.save(_contract("pending", contract_id="C-current", canonical_user_id="user-y", created_at=2.0))
result_c = gw.evidence_for_contract("C-current")
check(
    "(10) stale unrelated contract A's success cannot leak into C's evidence",
    result_c.result != "success",
)
check("(10) C's own (pending) state is what's reported", result_c.result == "outcome_unknown")


# ═════════════════════════════════════════════════════════════════
# 5, 12: _execute_contract() integration — exception and malformed result
# never manufacture success, and the seam is actually wired (not just the
# pure helper functions tested in isolation above).
# ═════════════════════════════════════════════════════════════════

def _spy_evidence_for_contract(gateway: ActionGateway):
    """Wrap evidence_for_contract to record every call this test makes,
    proving _execute_contract's single choke point actually calls it — not
    just that the pure functions behave correctly if called."""
    calls = []
    original = ActionGateway.evidence_for_contract

    def _spy(self, contract_id, *, dispatcher_outcome=None):
        result = original(self, contract_id, dispatcher_outcome=dispatcher_outcome)
        calls.append((contract_id, dispatcher_outcome, result))
        return result

    gateway.__class__.evidence_for_contract = _spy
    return calls, original


# Test 5: dispatch exception -> never success, and the seam still fires
# (contract-only fallback, since no structured outcome exists for a raised
# exception).
gw = ActionGateway(ledger=ExecutionLedger())
contract = _contract("approved", contract_id="exc-1")
gw._ledger.save(contract)
calls, _original = _spy_evidence_for_contract(gw)


def _raising_executor(tool_name=None, tool_inputs=None, contract_id=None, identity=None):
    raise RuntimeError("simulated dispatch failure")


gw._tool_executor = _raising_executor
try:
    reply_text = gw._execute_contract(contract)
    check("(5) dispatch exception -> reply is a failure message, not a success claim", "❌" in reply_text)
    persisted = gw._ledger.find_by_id("exc-1")
    check("(5) dispatch exception -> contract status persisted as failed", persisted is not None and persisted.status == "failed")
    check("(5) TC7-A seam fired at least once during exception path", len(calls) >= 1)
    check(
        "(5) resulting evidence for this exact contract is never success",
        gw.evidence_for_contract("exc-1") is None
        or gw.evidence_for_contract("exc-1").result != "success",
    )
finally:
    ActionGateway.evidence_for_contract = _original


# Test 12: malformed (plain-string) raw result cannot manufacture success —
# verify_execution() must reject it before the success branch is ever reached.
gw = ActionGateway(ledger=ExecutionLedger())
contract = _contract("approved", contract_id="malformed-1")
gw._ledger.save(contract)
calls, _original = _spy_evidence_for_contract(gw)


def _malformed_executor(tool_name=None, tool_inputs=None, contract_id=None, identity=None):
    return "לא מובנה, סתם טקסט"  # plain string, not the C53-A dict shape


gw._tool_executor = _malformed_executor
try:
    reply_text = gw._execute_contract(contract)
    persisted = gw._ledger.find_by_id("malformed-1")
    check(
        "(12) malformed raw result -> contract never persisted as completed/executed",
        persisted is not None and persisted.status not in ("completed", "executed"),
    )
    final_evidence = gw.evidence_for_contract("malformed-1")
    check(
        "(12) malformed raw result -> evidence never reports success",
        final_evidence is None or final_evidence.result != "success",
    )
finally:
    ActionGateway.evidence_for_contract = _original


# Positive integration control: a genuinely successful, well-formed
# execution DOES reach the seam with a completed+external_id outcome, and
# evidence_for_contract (queried with that same outcome) reports success —
# proving the wiring is a real seam, not merely fail-closed by omission.
gw = ActionGateway(ledger=ExecutionLedger())
contract = _contract("approved", contract_id="ok-1")
gw._ledger.save(contract)
calls, _original = _spy_evidence_for_contract(gw)


_VALID_RECORD_ID = "rec" + "A1B2C3D4E5F6G7"  # matches ^rec[A-Za-z0-9]{14}$


def _ok_executor(tool_name=None, tool_inputs=None, contract_id=None, identity=None):
    return {"ok": True, "tool": "airtable_add", "external_id": _VALID_RECORD_ID, "evidence": {}, "user_message": "נוסף"}


gw._tool_executor = _ok_executor
try:
    reply_text = gw._execute_contract(contract)
    persisted = gw._ledger.find_by_id("ok-1")
    check("(positive control) successful execution persists completed/executed", persisted is not None and persisted.status in ("completed", "executed"))
    success_calls = [c for c in calls if c[2] is not None and c[2].result == "success"]
    check("(positive control) TC7-A seam recorded a real success EvidenceResult", len(success_calls) == 1)
    if success_calls:
        check("(positive control) evidence_ref is the real external_id", success_calls[0][2].evidence_ref == _VALID_RECORD_ID)
finally:
    ActionGateway.evidence_for_contract = _original


# ═════════════════════════════════════════════════════════════════
# BLOCKER-2 FIX — canonical evidence_ref must not be top-level-external_id
# only. Representative write tools where real evidence lives ONLY in
# nested evidence.* fields (no top-level external_id at all) must still
# reach "success", and must still fail closed when that nested evidence is
# missing/invalid — routed through the exact same
# core.anti_hallucination.extract_canonical_evidence_ref() /
# _EVIDENCE_VALIDATORS verify_execution() itself uses, so the two can never
# independently disagree on what counts as evidence.
# ═════════════════════════════════════════════════════════════════

from core.anti_hallucination import extract_canonical_evidence_ref, verify_execution

# Each entry: (tool_name, valid_raw_response, expected_ref, invalid_raw_response)
# valid_raw_response has NO top-level external_id — evidence lives only in
# the nested evidence.* fields, exactly the shape Blocker 2 flagged as
# incorrectly downgraded to outcome_unknown by the old external_id-only logic.
_ALT_EVIDENCE_CASES = [
    (
        "airtable_add",
        {"ok": True, "external_id": "", "evidence": {"record_id": _REC_A}},
        _REC_A,
        {"ok": True, "external_id": "", "evidence": {}},
    ),
    (
        "calendar_create_event",
        {"ok": True, "external_id": "", "evidence": {"event_id": "evt_123", "htmlLink": "https://calendar.google.com/x"}},
        "evt_123",
        {"ok": True, "external_id": "", "evidence": {"event_id": "evt_123"}},  # missing htmlLink
    ),
    (
        "gmail_draft",
        {"ok": True, "external_id": "", "evidence": {"draft_id": "draft_abc123"}},
        "draft_abc123",
        {"ok": True, "external_id": "", "evidence": {}},
    ),
    (
        "gmail_send_draft",
        {"ok": True, "external_id": "", "evidence": {"message_id": "msg_xyz789"}},
        "msg_xyz789",
        {"ok": True, "external_id": "", "evidence": {}},
    ),
    (
        "drive_upload",
        {"ok": True, "external_id": "", "evidence": {"file_id": "file_001"}},
        "file_001",
        {"ok": True, "external_id": "", "evidence": {}},
    ),
    (
        "send_followup",
        {"ok": True, "external_id": "", "evidence": {"audit_id": "audit_777"}},
        "audit_777",
        {"ok": True, "external_id": "", "evidence": {}},
    ),
]

for tool_name, valid_raw, expected_ref, invalid_raw in _ALT_EVIDENCE_CASES:
    contract = _contract("completed", contract_id=f"alt-{tool_name}", tool_name=tool_name)

    # Positive: nested evidence only, empty top-level external_id -> success
    outcome = DispatcherOutcome(result="completed", user_message="", external_id="", raw_response=valid_raw)
    r = build_evidence_result_from_outcome(contract, outcome)
    check(f"(alt-evidence {tool_name}) nested evidence + empty external_id -> success", r.result == "success")
    check(f"(alt-evidence {tool_name}) evidence_ref is the canonical nested ref", r.evidence_ref == expected_ref)
    check(f"(alt-evidence {tool_name}) verified=True", r.verified is True)

    # Negative: same shape but missing/invalid nested evidence -> never success
    bad_outcome = DispatcherOutcome(result="completed", user_message="", external_id="", raw_response=invalid_raw)
    r_bad = build_evidence_result_from_outcome(contract, bad_outcome)
    check(f"(alt-evidence {tool_name}) missing/invalid nested evidence -> never success", r_bad.result != "success")
    check(f"(alt-evidence {tool_name}) missing/invalid nested evidence -> outcome_unknown", r_bad.result == "outcome_unknown")


# Consistency test: for every representative write tool, if the canonical
# structured result is accepted by verify_execution() (status == "ok"), then
# TC7-A's build_evidence_result_from_outcome() must NOT downgrade it to
# outcome_unknown merely because top-level external_id is empty — the two
# must agree, by construction, since both route through the exact same
# _EVIDENCE_VALIDATORS entry.
for tool_name, valid_raw, expected_ref, _invalid_raw in _ALT_EVIDENCE_CASES:
    check_result = verify_execution(tool_name, valid_raw)
    check(
        f"(consistency {tool_name}) verify_execution() accepts the nested-evidence-only result",
        check_result.status == "ok",
    )
    ref = extract_canonical_evidence_ref(tool_name, valid_raw)
    check(
        f"(consistency {tool_name}) extract_canonical_evidence_ref() agrees -> {expected_ref!r}",
        ref == expected_ref,
    )
    contract = _contract("completed", contract_id=f"consistency-{tool_name}", tool_name=tool_name)
    outcome = DispatcherOutcome(result="completed", user_message="", external_id="", raw_response=valid_raw)
    evidence = build_evidence_result_from_outcome(contract, outcome)
    check(
        f"(consistency {tool_name}) verify_execution()==ok never gets downgraded by TC7-A "
        "just because top-level external_id is empty",
        evidence.result == "success",
    )


# ═════════════════════════════════════════════════════════════════
# RE-REVIEW FIX — ok=False gate. extract_canonical_evidence_ref() must
# never yield a ref (and build_evidence_result_from_outcome() must never
# report success) for a raw result whose top-level ok is False, even when
# its nested evidence dict is otherwise well-formed/valid-looking. Without
# this gate the same raw result could be "failed" to verify_execution() and
# "success" to TC7-A — exactly the two-authority inconsistency this whole
# seam exists to prevent. Parametrized across every _ALT_EVIDENCE_CASES
# tool (Airtable, Calendar, Gmail draft/send, Drive, send_followup).
# ═════════════════════════════════════════════════════════════════

for tool_name, valid_raw, expected_ref, _invalid_raw in _ALT_EVIDENCE_CASES:
    # Same evidence dict as the positive alt-evidence case above, but ok=False.
    not_ok_raw = {**valid_raw, "ok": False}

    check_result = verify_execution(tool_name, not_ok_raw)
    check(
        f"(ok-gate {tool_name}) verify_execution() rejects ok=False regardless of evidence shape",
        check_result.status == "failed",
    )

    ref = extract_canonical_evidence_ref(tool_name, not_ok_raw)
    check(
        f"(ok-gate {tool_name}) extract_canonical_evidence_ref() yields no ref when ok=False "
        f"even though the same evidence shape is valid when ok=True (would be {expected_ref!r})",
        ref == "",
    )

    contract = _contract("completed", contract_id=f"okgate-{tool_name}", tool_name=tool_name)
    outcome = DispatcherOutcome(result="completed", user_message="", external_id="", raw_response=not_ok_raw)
    evidence = build_evidence_result_from_outcome(contract, outcome)
    check(
        f"(ok-gate {tool_name}) build_evidence_result_from_outcome() never reports success when ok=False "
        "-- the same raw result cannot be failed to verify_execution() and success to TC7-A",
        evidence.result != "success",
    )
    check(f"(ok-gate {tool_name}) falls closed to outcome_unknown, not a fabricated failure/success", evidence.result == "outcome_unknown")

# Exact reproduction of the reviewer's own example: Airtable, ok=False, a
# genuinely-valid-shaped record_id nested in evidence.
_airtable_ok_false_valid_shape = {
    "ok": False,
    "evidence": {"record_id": _REC_A},
}
check(
    "(ok-gate airtable_add exact repro) verify_execution() -> failed",
    verify_execution("airtable_add", _airtable_ok_false_valid_shape).status == "failed",
)
check(
    "(ok-gate airtable_add exact repro) extract_canonical_evidence_ref() -> ''",
    extract_canonical_evidence_ref("airtable_add", _airtable_ok_false_valid_shape) == "",
)
_repro_contract = _contract("completed", contract_id="okgate-airtable-repro", tool_name="airtable_add")
_repro_outcome = DispatcherOutcome(
    result="completed", user_message="", external_id="", raw_response=_airtable_ok_false_valid_shape,
)
_repro_evidence = build_evidence_result_from_outcome(_repro_contract, _repro_outcome)
check(
    "(ok-gate airtable_add exact repro) build_evidence_result_from_outcome() never success",
    _repro_evidence.result != "success",
)


# ═════════════════════════════════════════════════════════════════
# CodeRabbit nitpick fix — a write/action tool registered in
# _WRITE_ACTION_TOOLS but with no entry in _EVIDENCE_VALIDATORS (a future
# tool added to the "Future tools" placeholder before its validator exists)
# must fail closed in extract_canonical_evidence_ref() exactly like
# verify_execution() already does, not fall back to a permissive bare
# external_id read. Today _WRITE_ACTION_TOOLS == frozenset(_EVIDENCE_
# VALIDATORS) exactly (no such tool exists yet), so this is exercised via a
# monkeypatched module-level set, restored immediately after.
# ═════════════════════════════════════════════════════════════════

import core.anti_hallucination as _ah_module

_FUTURE_TOOL = "future_write_tool_no_validator_yet"
_original_write_action_tools = _ah_module._WRITE_ACTION_TOOLS
_ah_module._WRITE_ACTION_TOOLS = _original_write_action_tools | frozenset({_FUTURE_TOOL})
try:
    _future_raw = {"ok": True, "external_id": "some-looking-id-123"}
    _future_check = verify_execution(_FUTURE_TOOL, _future_raw)
    check(
        "(unregistered-write-tool) verify_execution() fails closed (no validator registered)",
        _future_check.status == "failed",
    )
    _future_ref = extract_canonical_evidence_ref(_FUTURE_TOOL, _future_raw)
    check(
        "(unregistered-write-tool) extract_canonical_evidence_ref() also fails closed -> ''",
        _future_ref == "",
    )
    _future_contract = _contract("completed", contract_id="unregistered-write-tool", tool_name=_FUTURE_TOOL)
    _future_outcome = DispatcherOutcome(
        result="completed", user_message="", external_id="", raw_response=_future_raw,
    )
    _future_evidence = build_evidence_result_from_outcome(_future_contract, _future_outcome)
    check(
        "(unregistered-write-tool) build_evidence_result_from_outcome() never success for an "
        "unvalidated write tool, even with a plausible-looking external_id",
        _future_evidence.result != "success",
    )
finally:
    _ah_module._WRITE_ACTION_TOOLS = _original_write_action_tools

# Control: the SAME unregistered-tool name, but genuinely non-write (not in
# _WRITE_ACTION_TOOLS) -- the plain external_id fallback still applies, since
# that path is for read-only/listing tools that verify_execution() itself
# already accepts without a validator.
check(
    "(non-write unregistered tool) extract_canonical_evidence_ref() still falls back to external_id",
    extract_canonical_evidence_ref(_FUTURE_TOOL, {"ok": True, "external_id": "read-only-id"}) == "read-only-id",
)


# ═════════════════════════════════════════════════════════════════
# 13: TurnEvidenceSummary / RP4 untouched — structural non-regression
# ═════════════════════════════════════════════════════════════════

try:
    from core.turn_evidence import TurnEvidenceSummary
    check(
        "(13) TurnEvidenceSummary remains a distinct type from EvidenceResult "
        "(TC7-A introduces no coupling between them)",
        TurnEvidenceSummary is not EvidenceResult and not issubclass(TurnEvidenceSummary, EvidenceResult)
        and not issubclass(EvidenceResult, TurnEvidenceSummary),
    )
except Exception as e:
    check(f"(13) core.turn_evidence still importable unmodified ({e})", False)


# ═════════════════════════════════════════════════════════════════
# Summary
# ═════════════════════════════════════════════════════════════════

print(f"\n{'═'*60}")
print(f"TC7-A exact-contract evidence: {_passed}/{_passed + _failed} passed")
if _failed:
    print(f"FAILED: {_failed} test(s)")
sys.exit(0 if _failed == 0 else 1)
