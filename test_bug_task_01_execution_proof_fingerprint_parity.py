#!/usr/bin/env python3
"""
test_bug_task_01_execution_proof_fingerprint_parity.py — BUG-TASK-01
(deterministic create_task's business_identity() fingerprint payload
diverged in TABLE ALIAS and FIELD KEY NAMES from the real dispatched
Airtable payload, so tools/dispatcher.py's execution-proof fingerprint
recompute could never match the contract's stored
business_action_fingerprint — every approved deterministic create_task
ActionContract was denied at dispatch with "approval-sensitive execution
proof does not match the action payload", regardless of the task's
content. Live evidence: R10 bug report, 01/09/2026, BUG-TASK-01.)

Root cause (confirmed empirically before this fix, not by inspection
alone): DeterministicTaskParse.business_identity() (core/router/router.py)
built its identity payload as {"table": "Tasks", "fields": {"title": ...}}.
The REAL write payload the deterministic path actually dispatches
(core/router/task_builders.py::build_create_task_proposal() ->
core/turn_coordinator_runtime.py::gateway_call()) is
{"table": Tables.TASKS, "fields": {TaskFields.NAME: ...}} — a DIFFERENT
table alias string ("Tasks" vs "משימות (Tasks)") and a DIFFERENT field key
("title" vs "כותרת המשימה"). core/action_gateway.py's propose_action()
hashes business_action_fingerprint from fingerprint_payload
(business_identity()) whenever one is supplied, but
tools/dispatcher.py::_validate_execution_proof() independently RECOMPUTES
the expected fingerprint from the real dispatched payload
(contract.normalized_payload) at execution time — the two fingerprints
could never be equal, so Dispatcher denied every approved deterministic
create_task contract, fail-closed, unconditionally.

This was NOT caught by test_bug155/test_bug156 because those only prove
business_identity()'s *internal* self-consistency (due_time excluded,
phrasing-invariant) — neither compares it against the real dispatched
tool_inputs shape, and neither exercises
tools/dispatcher.py::_validate_execution_proof() at all. The originally
suspected root cause (dispatcher failing to re-apply
core.action_gateway._canonical_task_payload() before recomputing) was
checked and disproven first: contract.normalized_payload is already
canonical at propose time (propose_action() applies
_canonical_task_payload() to it before storage), so dispatcher's plain
normalize_payload() on an already-canonical payload is a no-op and was
never the actual mismatch source — see the investigating session's static
repro before this file existed.

Fix: business_identity() now uses the same Tables.TASKS / TaskFields.NAME /
TaskFields.DUE_DATE constants the real write payload uses, so both payloads
canonicalize (core/action_gateway.py::_canonical_task_payload()) to the
identical shape and hash to the identical fingerprint. due_time stays
excluded from the identity (BUG-156, unchanged).

This file exercises the REAL propose_action() and the REAL
_validate_execution_proof() — the exact two functions that disagreed live
— never a reimplementation of their logic.
"""

from __future__ import annotations

import os

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-bugtask01-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:BUGTASK01_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patBugTask01Test")
os.environ.setdefault("AIRTABLE_BASE_ID", "appBugTask01Test")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")
# Keep the ActionContract ledger in-memory only — no real persistence/Airtable
# writes must ever happen from this test.
os.environ["FEATURE_ACTION_CONTRACT_PERSISTENCE"] = "false"

import app  # noqa: E402  (import side effects: startup validation, etc.)
from airtable_schema import Tables, TaskFields  # noqa: E402
from core.action_gateway import action_gateway as _gw  # noqa: E402
from core.router.router import DeterministicTaskParse  # noqa: E402
from identity import Identity, Role  # noqa: E402
from tools.dispatcher import _validate_execution_proof  # noqa: E402

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


def _identity(user_id: str) -> Identity:
    return Identity(
        user_id=user_id, role=Role.OWNER, display_name=user_id,
        tenant_id="boss_hq", domain_id="general", channel="telegram", external_id=user_id,
    )


def _execution_context_for(contract) -> dict:
    """Mirrors exactly what core/action_gateway.py::_make_dispatch_executor()
    builds from a live, approved contract before calling dispatch_tool()."""
    return {
        "contract_id": contract.contract_id,
        "approved_by": contract.canonical_user_id,
        "tool_name": contract.tool_name,
        "tenant_id": contract.tenant_id,
        "canonical_user_id": contract.canonical_user_id,
        "business_action_fingerprint": contract.business_action_fingerprint,
        "status": "approved",
    }


def _propose_task(title: str, identity: Identity, due_date: str | None = None):
    """Mirrors the real deterministic create_task flow
    (app.py::_queue_deterministic_create_task): propose via ActionGateway
    with fingerprint_payload=business_identity(), using the SAME real
    Airtable write payload shape core/router/task_builders.py actually
    dispatches."""
    task_parse = DeterministicTaskParse(title=title, due_date=due_date, matched=True)
    real_tool_inputs = {"table": Tables.TASKS, "fields": {TaskFields.NAME: title}}
    if due_date:
        real_tool_inputs["fields"][TaskFields.DUE_DATE] = due_date

    result = _gw.propose_action(
        tenant_id="boss_hq", canonical_user_id=identity.memory_key,
        tool_name="airtable_add", tool_inputs=real_tool_inputs,
        origin_channel="telegram", origin_chat_id=identity.user_id,
        requires_approval=True, identity=identity,
        trusted_source="deterministic_create_task",
        fingerprint_payload=task_parse.business_identity(),
    )
    assert result.ok, f"propose_action failed unexpectedly: {result.reason}"
    contract = _gw.find_contract(result.contract_id)
    assert contract is not None
    return contract


def _check_execution_proof(contract, identity: Identity) -> str | None:
    """This is EXACTLY the check tools/dispatcher.py::dispatch_tool() runs at
    execution time: recompute the expected fingerprint from the payload
    actually being dispatched (contract.normalized_payload) and compare
    against the stored business_action_fingerprint."""
    return _validate_execution_proof(
        "airtable_add", contract.normalized_payload, identity,
        _execution_context_for(contract), "deterministic_create_task",
    )


# ══════════════════════════════════════════════════════════════════
print("── Live-failure-class regression: proposal fingerprint == execution "
      "proof fingerprint for every semantically equivalent title form ──")

_CASES = {
    "A. plain title":              ("טיפול במשכנתא דחוף", None),
    "B. trailing punctuation":     ("טיפול במשכנתא דחוף.", None),
    "C. repeated whitespace":      ("טיפול   במשכנתא  דחוף", None),
    "D. zero-width character":     ("טיפול​במשכנתא דחוף", None),
    "E. surrounding quotes":       ('"טיפול במשכנתא דחוף"', None),
    "F. leading quote marker '>'": ("> טיפול במשכנתא דחוף", None),
    "G. with due_date":            ("טיפול במשכנתא דחוף", "2026-09-05"),
}

for i, (label, (title, due_date)) in enumerate(_CASES.items()):
    identity = _identity(f"u-case-{i}")
    contract = _propose_task(title, identity, due_date=due_date)
    err = _check_execution_proof(contract, identity)
    chk(f"{label}: execution proof validates (no mismatch)", err is None)


# ══════════════════════════════════════════════════════════════════
print("\n── NEGATIVE: canonicalization parity must not let a materially "
      "changed payload pass — approval integrity must stay intact ──")

_neg_identity = _identity("u-negative")
_neg_contract = _propose_task("טיפול במשכנתא דחוף", _neg_identity)
assert _check_execution_proof(_neg_contract, _neg_identity) is None, (
    "setup: baseline contract must itself validate before mutation tests are meaningful"
)
_neg_ctx = _execution_context_for(_neg_contract)

_MISMATCH = "approval-sensitive execution proof does not match the action payload."

err_title = _validate_execution_proof(
    "airtable_add",
    {"table": Tables.TASKS, "fields": {TaskFields.NAME: "משהו אחר לגמרי"}},
    _neg_identity, _neg_ctx, "deterministic_create_task",
)
chk("different title after approval: execution proof REJECTS (fail closed)", err_title == _MISMATCH)

err_table = _validate_execution_proof(
    "airtable_add",
    {"table": "Deals", "fields": {TaskFields.NAME: "טיפול במשכנתא דחוף"}},
    _neg_identity, _neg_ctx, "deterministic_create_task",
)
chk("different table after approval: execution proof REJECTS (fail closed)", err_table == _MISMATCH)

err_extra_field = _validate_execution_proof(
    "airtable_add",
    {"table": Tables.TASKS, "fields": {
        TaskFields.NAME: "טיפול במשכנתא דחוף", TaskFields.STATUS: "בוצע",
    }},
    _neg_identity, _neg_ctx, "deterministic_create_task",
)
chk("extra changed business field after approval: execution proof REJECTS (fail closed)",
    err_extra_field == _MISMATCH)

err_wrong_tool = _validate_execution_proof(
    "airtable_update", _neg_contract.normalized_payload,
    _neg_identity, _neg_ctx, "deterministic_create_task",
)
chk("redirected to a different tool after approval: execution proof REJECTS (fail closed)",
    err_wrong_tool == "approval-sensitive execution proof targets another tool.")


print()
print("=" * 50)
print(f"BUG-TASK-01 (execution-proof fingerprint parity) tests: {passed} passed, {failed} failed")
if failed:
    raise SystemExit(1)
