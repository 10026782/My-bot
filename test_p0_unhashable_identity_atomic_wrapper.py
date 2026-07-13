#!/usr/bin/env python3
"""
test_p0_unhashable_identity_atomic_wrapper.py — P0 regression: unhashable Identity
in the atomic-claims execution wrapper.

Root cause: execute_with_atomic_claim() called executor_fn(tool_name, tool_inputs,
identity) POSITIONALLY. The real production executor
(core.action_gateway._make_dispatch_executor) has the signature
(tool_name, tool_inputs, contract_id, identity=None) — the 3rd positional slot is
contract_id, not identity. The reconstructed Identity object silently bound to
contract_id, and was then passed to ExecutionLedger.find_by_id() ->
self._store.get(contract_id) -> TypeError: unhashable type: 'Identity' (Identity
is a mutable, unfrozen dataclass — deliberately NOT made hashable by this fix).

Traceback captured against the pre-fix code (contract_id positionally shadowed
by an Identity object):
    File "core/action_gateway.py", line 1487, in _executor
        contract = ledger.find_by_id(contract_id)
    File "core/action_gateway.py", line 379, in find_by_id
        cached = self._store.get(contract_id)
    TypeError: unhashable type: 'Identity'

Fix: execute_with_atomic_claim now calls executor_fn(tool_name, tool_inputs,
contract_id=contract_id, identity=identity) — by keyword, preserving the real
contract_id AND correctly routing identity to the parameter dispatch_tool
actually expects. _make_dispatch_executor's _executor accepts an explicit
identity= keyword: when supplied (atomic path) it is used as-is (already
fail-closed validated in _execute_contract from the frozen contract's
tenant_id/actor_user_id/actor_role/actor_external_id); when omitted (legacy
flag-OFF path) behavior is unchanged — identity is derived from contract_id.

This test drives the REAL, production _make_dispatch_executor (not a hand-rolled
mock with a convenient signature) through _execute_contract -> execute_with_atomic_claim
-> dispatch_tool -> airtable_update, mocking only the lowest-level HTTP call
(airtable_gateway.airtable_patch). Before the fix, every one of these scenarios
raised "unhashable type: 'Identity'" inside ExecutionLedger.find_by_id() before
ever reaching dispatch_tool.
"""

from __future__ import annotations

import os
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:TEST")
os.environ.setdefault("AIRTABLE_API_KEY", "patTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import sys
from unittest.mock import patch

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


def _flag_atomic_only(name, *a, **kw):
    """Only FEATURE_ATOMIC_CLAIMS is on — avoids also tripping EMERGENCY_STOP_ALL
    or other flags a blanket return_value=True mock would incorrectly enable."""
    return name == "FEATURE_ATOMIC_CLAIMS"


def _make_contract(contract_id, trusted_source="lead_capture"):
    from core.action_gateway import ActionContract
    return ActionContract(
        contract_id=contract_id,
        tenant_id="boss_hq",
        canonical_user_id="boss_hq:eliyahu",
        tool_name="airtable_update",
        normalized_payload={"table": "Leads", "record_id": "recXOW7FBZQZcNdw1", "fields": {"Status": "Won"}},
        business_action_fingerprint=f"fp_{contract_id}",
        status="approved",
        origin_channel="telegram",
        origin_chat_id="chat_1",
        requires_approval=True,
        created_at=1234567890.0,
        actor_role="owner",
        actor_user_id="eliyahu",
        actor_external_id="tg_user_1",
        approved_by="boss_hq:eliyahu",
        approved_at=1234567891.0,
        trusted_source=trusted_source,
    )


def test_success_through_real_dispatch_executor_no_unhashable_crash():
    """
    The exact P0 regression scenario: real _make_dispatch_executor, real
    dispatch_tool, real airtable_update (HTTP call mocked at the lowest layer).
    Before the fix this raised TypeError: unhashable type: 'Identity' inside
    ExecutionLedger.find_by_id(); the claim was marked failed and the caller
    got a generic "ביצוע נכשל" message instead of ever reaching the provider.
    """
    from core.action_gateway import ActionGateway, ExecutionLedger, _make_dispatch_executor
    from core.atomic_claim_repository import ClaimAcquisitionResult, AtomicExecutionClaim

    contract_id = "test-p0-success"
    contract = _make_contract(contract_id)
    ledger = ExecutionLedger()
    ledger.save(contract)

    # Real production executor — NOT a hand-rolled mock. This is exactly what
    # action_gateway.action_gateway (the live singleton) is wired to.
    gw = ActionGateway(ledger=ledger, tool_executor=_make_dispatch_executor(ledger))

    with patch('feature_flags.is_enabled', side_effect=_flag_atomic_only), \
         patch('tools.airtable_gateway.airtable_patch', return_value=True) as mock_patch, \
         patch('core.atomic_claim_repository.claim_contract_execution') as mock_claim, \
         patch('core.atomic_claim_repository.update_claim_status') as mock_update_status:

        mock_claim.return_value = ClaimAcquisitionResult(
            result="acquired",
            claim=AtomicExecutionClaim(
                contract_id=contract_id, claimant_id="boss_hq:eliyahu",
                execution_id="exec-p0-success", claimed_at=1234567891.0,
            ),
        )

        result = gw._execute_contract(contract)

    chk("no unhashable-Identity crash — a real reply was returned", isinstance(result, str))
    chk("real provider (airtable_patch) called exactly once", mock_patch.call_count == 1)
    chk("success reply reported to user", "בוצע" in result)
    completed_calls = [c for c in mock_update_status.call_args_list if c.args[1] == "completed"]
    chk("claim transitioned to completed", len(completed_calls) == 1)
    failed_calls = [c for c in mock_update_status.call_args_list if c.args[1] == "failed"]
    chk("claim never marked failed on the success path", len(failed_calls) == 0)


def test_permission_denial_dispatcher_called_provider_not_reached():
    """
    A role without write permission: dispatch_tool's own enforce() gate denies
    before reaching the provider. Claim must be failed, not completed — proves
    classification is evidence-based (verify_execution), not "no exception raised".
    Also exercises the exact same real-executor path, so it would have hit the
    same unhashable-Identity crash before the fix (it never even got this far).
    """
    from core.action_gateway import ActionGateway, ExecutionLedger, ActionContract, _make_dispatch_executor
    from core.atomic_claim_repository import ClaimAcquisitionResult, AtomicExecutionClaim

    contract_id = "test-p0-denied"
    contract = ActionContract(
        contract_id=contract_id,
        tenant_id="boss_hq",
        canonical_user_id="boss_hq:readonly_user",
        tool_name="airtable_update",
        normalized_payload={"table": "Leads", "record_id": "recXOW7FBZQZcNdw1", "fields": {"Status": "Won"}},
        business_action_fingerprint="fp_denied",
        status="approved",
        origin_channel="telegram",
        origin_chat_id="chat_1",
        requires_approval=True,
        created_at=1234567890.0,
        actor_role="readonly",       # no write permission (_MANAGEMENT excludes it)
        actor_user_id="readonly_user",
        actor_external_id="tg_user_2",
        approved_by="boss_hq:readonly_user",
        approved_at=1234567891.0,
        trusted_source="lead_capture",
    )
    ledger = ExecutionLedger()
    ledger.save(contract)
    gw = ActionGateway(ledger=ledger, tool_executor=_make_dispatch_executor(ledger))

    with patch('feature_flags.is_enabled', side_effect=_flag_atomic_only), \
         patch('tools.airtable_gateway.airtable_patch') as mock_patch, \
         patch('core.atomic_claim_repository.claim_contract_execution') as mock_claim, \
         patch('core.atomic_claim_repository.update_claim_status') as mock_update_status:

        mock_claim.return_value = ClaimAcquisitionResult(
            result="acquired",
            claim=AtomicExecutionClaim(
                contract_id=contract_id, claimant_id="boss_hq:readonly_user",
                execution_id="exec-p0-denied", claimed_at=1234567891.0,
            ),
        )

        result = gw._execute_contract(contract)

    chk("no unhashable-Identity crash on denial path either", isinstance(result, str))
    chk("provider never reached (denied before dispatch)", mock_patch.call_count == 0)
    chk("failure reported to user", "נכשל" in result)
    failed_calls = [c for c in mock_update_status.call_args_list if c.args[1] == "failed"]
    chk("claim transitioned to failed", len(failed_calls) == 1)
    completed_calls = [c for c in mock_update_status.call_args_list if c.args[1] == "completed"]
    chk("claim never marked completed on denial", len(completed_calls) == 0)


def test_identity_reaches_real_executor_correctly_typed():
    """
    Directly proves the fix's contract: calling the REAL _make_dispatch_executor
    exactly the way execute_with_atomic_claim calls it now (keyword contract_id=
    + identity=) must not raise, and the identity received by dispatch_tool must
    be the Identity object itself (tenant/user/role/channel/external_id all
    preserved) — not misrouted into contract_id, not stringified, not dropped.
    """
    from core.action_gateway import ExecutionLedger, _make_dispatch_executor
    from identity import Identity

    contract_id = "test-p0-identity-shape"
    contract = _make_contract(contract_id)
    ledger = ExecutionLedger()
    ledger.save(contract)
    executor = _make_dispatch_executor(ledger)

    identity = Identity(
        user_id="eliyahu", role="owner", tenant_id="boss_hq",
        domain_id="general", channel="telegram", external_id="tg_user_1",
    )

    captured = {}
    def fake_dispatch_tool(name, inputs, identity=None, trusted_source=None):
        captured["identity"] = identity
        captured["trusted_source"] = trusted_source
        return {"ok": True, "external_id": "recXOW7FBZQZcNdw1", "user_message": "✅ בוצע"}

    with patch("tools.dispatcher.dispatch_tool", side_effect=fake_dispatch_tool):
        # Exactly execute_with_atomic_claim's post-fix call shape.
        result = executor("airtable_update", contract.normalized_payload,
                           contract_id=contract_id, identity=identity)

    chk("dispatch_tool received an Identity, not something else",
        isinstance(captured.get("identity"), Identity))
    chk("tenant_id preserved through to dispatch_tool", captured["identity"].tenant_id == "boss_hq")
    chk("user_id preserved through to dispatch_tool", captured["identity"].user_id == "eliyahu")
    chk("role preserved through to dispatch_tool", captured["identity"].role == "owner")
    chk("channel preserved through to dispatch_tool", captured["identity"].channel == "telegram")
    chk("external_id preserved through to dispatch_tool", captured["identity"].external_id == "tg_user_1")
    chk("trusted_source threaded from contract", captured["trusted_source"] == "lead_capture")
    chk("no crash / correct return", result.get("ok") is True)


TESTS = [
    test_success_through_real_dispatch_executor_no_unhashable_crash,
    test_permission_denial_dispatcher_called_provider_not_reached,
    test_identity_reaches_real_executor_correctly_typed,
]

if __name__ == "__main__":
    print("=" * 70)
    print("P0 — unhashable Identity in atomic-claims execution wrapper")
    print("=" * 70)
    print()
    for t in TESTS:
        t()
        print()
    print("=" * 70)
    print(f"PASSED: {passed} | FAILED: {failed}")
    print("=" * 70)
    if failed > 0:
        sys.exit(1)
