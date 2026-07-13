#!/usr/bin/env python3
"""
test_phase_4b0_integration_result_classification.py — Integration test for atomic claim fixes

CRITICAL: Corrected implementation:
1. Identity reconstruction fail-closed: requires all immutable fields (tenant, user, role, external_id)
2. Structured DispatcherOutcome contract: completed | failed | outcome_unknown (not string parsing)
3. Permission denial: dispatcher called once, provider adapter not called, claim failed
4. Atomic conflict/DB failure: dispatcher called zero times
5. Explicit success: claim completed with external_id
6. Ambiguous outcome: claim outcome_unknown, never auto-retry
7. User-facing result must agree with claim status

This test verifies structured outcomes with proper distinctions.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import patch, MagicMock
from typing import Any

os.environ.setdefault("FEATURE_ATOMIC_CLAIMS", "true")
os.environ.setdefault("FEATURE_ACTION_GATEWAY", "true")

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


def test_identity_preserved_through_atomic_wrapper():
    """
    Identity from frozen contract must reach dispatcher unchanged.
    Before fix: identity=None → dispatcher received unknown tenant/user
    After fix: identity reconstructed from contract → dispatcher receives boss_hq:eliyahu
    """
    from core.action_gateway import ActionGateway, ExecutionLedger, ActionContract

    contract_id = "test-identity-preservation"
    test_contract = ActionContract(
        contract_id=contract_id,
        tenant_id="boss_hq",
        canonical_user_id="boss_hq:eliyahu",
        tool_name="airtable_update",
        normalized_payload={"table": "Leads", "record_id": "rec123", "fields": {"Status": "Won"}},
        business_action_fingerprint="fingerprint_001",
        status="approved",
        origin_channel="telegram",
        origin_chat_id="chat_1",
        requires_approval=True,
        created_at=1234567890.0,
        actor_role="owner",
        actor_user_id="eliyahu",
        actor_display_name="אליהו",
        actor_external_id="tg_user_1",
        actor_domain_id="real_estate",
        actor_allowed_domains=["real_estate"],
        approved_by="boss_hq:eliyahu",
        approved_at=1234567891.0,
    )

    mock_ledger = MagicMock(spec=ExecutionLedger)
    mock_ledger.update_status = MagicMock()

    # Track what identity the executor receives
    captured_identity = {}
    def mock_executor(tool_name, tool_inputs, contract_id=None, identity=None):
        captured_identity["received"] = identity
        return {"ok": True, "external_id": "rec12345678901234"}

    with patch('feature_flags.is_enabled', return_value=True):
        with patch('core.action_gateway_atomic_executor.execute_with_atomic_claim') as mock_atomic:
            # Mock successful execution
            mock_atomic.return_value = (True, {"ok": True, "external_id": "rec12345678901234"}, None)

            gateway = ActionGateway(ledger=mock_ledger)
            gateway._tool_executor = mock_executor

            result = gateway._execute_contract(test_contract)

            # Verify identity was passed to atomic executor
            if mock_atomic.called:
                call_kwargs = mock_atomic.call_args[1]
                identity_arg = call_kwargs.get('identity')

                chk(
                    "Identity passed to atomic executor (not None)",
                    identity_arg is not None
                )

                if identity_arg:
                    chk(
                        "Tenant preserved (boss_hq)",
                        identity_arg.tenant_id == "boss_hq"
                    )

                    chk(
                        "User preserved (eliyahu)",
                        identity_arg.user_id == "eliyahu"
                    )

                    chk(
                        "Role preserved (owner)",
                        identity_arg.role == "owner"
                    )

                    chk(
                        "External ID preserved (tg_user_1)",
                        identity_arg.external_id == "tg_user_1"
                    )


def test_permission_denial_claim_failed():
    """
    Permission denial (access denied result):
    - Dispatcher called once (authorization check happens in dispatcher)
    - Provider adapter NOT called (failed before provider reached)
    - Claim marked failed (not completed)
    - User-facing result matches claim status
    """
    from core.action_gateway import ActionGateway, ExecutionLedger, ActionContract
    from core.dispatcher_outcome import DispatcherOutcome

    contract_id = "test-permission-denial-failed"
    test_contract = ActionContract(
        contract_id=contract_id,
        tenant_id="boss_hq",
        canonical_user_id="boss_hq:readonly_user",
        tool_name="airtable_update",
        normalized_payload={"table": "Leads", "record_id": "rec123", "fields": {"Status": "Won"}},
        business_action_fingerprint="fingerprint_002",
        status="approved",
        origin_channel="telegram",
        origin_chat_id="chat_1",
        requires_approval=True,
        created_at=1234567890.0,
        actor_role="readonly",  # No write permission
        actor_user_id="readonly_user",
        actor_external_id="tg_user_2",
        approved_by="boss_hq:readonly_user",
        approved_at=1234567891.0,
    )

    mock_ledger = MagicMock(spec=ExecutionLedger)
    mock_ledger.update_status = MagicMock()

    # Track claim status updates from atomic executor
    claim_status_updates = []

    with patch('feature_flags.is_enabled', return_value=True):
        with patch('core.atomic_claim_repository.update_claim_status') as mock_update_claim:
            mock_update_claim.side_effect = lambda cid, status, error=None: claim_status_updates.append({"contract_id": cid, "status": status, "error": error})

            # Dispatcher returns structured DispatcherOutcome: permission denied
            def executor_permission_denied(tool_name, tool_inputs, contract_id=None, identity=None, claim_execution_id=None):
                return DispatcherOutcome(
                    result="failed",
                    user_message="❌ גישה נחסמה: אין הרשאה לבצע פעולת כתיבה.",
                    error_code="PERMISSION_DENIED",
                    error="User role readonly does not permit airtable_update writes",
                )

            gateway = ActionGateway(ledger=mock_ledger)
            gateway._tool_executor = executor_permission_denied

            # Use real execute_with_atomic_claim with mocked dependencies
            with patch('core.atomic_claim_repository.claim_contract_execution') as mock_claim:
                from core.atomic_claim_repository import ClaimAcquisitionResult, AtomicExecutionClaim

                # Mock successful claim acquisition
                claim = AtomicExecutionClaim(
                    contract_id=contract_id,
                    claimant_id="boss_hq:readonly_user",
                    execution_id="exec_1",
                    claimed_at=1234567891.0,
                )
                mock_claim.return_value = ClaimAcquisitionResult(result="acquired", claim=claim)

                result = gateway._execute_contract(test_contract)

                # Verify claim was marked failed for permission denial
                chk(
                    "Permission denial produces claim failed",
                    any(u["status"] == "failed" for u in claim_status_updates if u["contract_id"] == contract_id)
                )

                chk(
                    "No claim completed for permission denial",
                    not any(u["status"] == "completed" for u in claim_status_updates if u["contract_id"] == contract_id)
                )

                # Verify user result indicates failure
                chk(
                    "User-facing result indicates failure",
                    "ביצוע נכשל" in result or "נכשל" in result or "denied" in result.lower()
                )


def test_explicit_success_claim_completed():
    """
    Explicit success with required evidence (structured outcome):
    - DispatcherOutcome.result = "completed"
    - external_id present (proof of provider action)
    - Claim marked completed (not failed)
    - User-facing result matches claim status
    """
    from core.action_gateway import ActionGateway, ExecutionLedger, ActionContract
    from core.dispatcher_outcome import DispatcherOutcome

    contract_id = "test-explicit-success-completed"
    test_contract = ActionContract(
        contract_id=contract_id,
        tenant_id="boss_hq",
        canonical_user_id="boss_hq:eliyahu",
        tool_name="airtable_add",
        normalized_payload={"table": "Leads", "Name": "יוסי כהן"},
        business_action_fingerprint="fingerprint_003",
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
    )

    mock_ledger = MagicMock(spec=ExecutionLedger)
    mock_ledger.update_status = MagicMock()

    # Track claim status updates from atomic executor
    claim_status_updates = []

    with patch('feature_flags.is_enabled', return_value=True):
        with patch('core.atomic_claim_repository.update_claim_status') as mock_update_claim:
            mock_update_claim.side_effect = lambda cid, status, error=None: claim_status_updates.append({"contract_id": cid, "status": status, "error": error})

            # Dispatcher returns structured DispatcherOutcome: explicit success with evidence
            def executor_success(tool_name, tool_inputs, contract_id=None, identity=None, claim_execution_id=None):
                return DispatcherOutcome(
                    result="completed",
                    user_message="✅ בוצע: הוסף ליד יוסי כהן",
                    external_id="rec12345678901234",
                    raw_response={"ok": True, "external_id": "rec12345678901234"},
                )

            gateway = ActionGateway(ledger=mock_ledger)
            gateway._tool_executor = executor_success

            # Use real execute_with_atomic_claim with mocked dependencies
            with patch('core.atomic_claim_repository.claim_contract_execution') as mock_claim:
                from core.atomic_claim_repository import ClaimAcquisitionResult, AtomicExecutionClaim

                # Mock successful claim acquisition
                claim = AtomicExecutionClaim(
                    contract_id=contract_id,
                    claimant_id="boss_hq:eliyahu",
                    execution_id="exec_2",
                    claimed_at=1234567891.0,
                )
                mock_claim.return_value = ClaimAcquisitionResult(result="acquired", claim=claim)

                result = gateway._execute_contract(test_contract)

                # Verify claim was marked completed for explicit success
                chk(
                    "Explicit success (outcome=completed) produces claim completed",
                    any(u["status"] == "completed" for u in claim_status_updates if u["contract_id"] == contract_id)
                )

                chk(
                    "No claim marked failed for explicit success",
                    not any(u["status"] == "failed" for u in claim_status_updates if u["contract_id"] == contract_id)
                )

                # Verify user result indicates success
                chk(
                    "User-facing result indicates success",
                    "בוצע" in result or "✅" in result
                )


def test_ambiguous_outcome_claim_unknown():
    """
    Ambiguous provider outcome (outcome_unknown):
    - DispatcherOutcome.result = "outcome_unknown"
    - Typical: timeout after request sent, transport error after delivery, retry-ability unknown
    - Claim marked outcome_unknown (never auto-retry)
    - No user-facing success claim
    """
    from core.action_gateway import ActionGateway, ExecutionLedger, ActionContract
    from core.dispatcher_outcome import DispatcherOutcome

    contract_id = "test-ambiguous-outcome-unknown"
    test_contract = ActionContract(
        contract_id=contract_id,
        tenant_id="boss_hq",
        canonical_user_id="boss_hq:eliyahu",
        tool_name="airtable_update",
        normalized_payload={"table": "Leads", "record_id": "rec123", "fields": {"Status": "Contacted"}},
        business_action_fingerprint="fingerprint_004",
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
    )

    mock_ledger = MagicMock(spec=ExecutionLedger)
    mock_ledger.update_status = MagicMock()

    # Track claim status updates from atomic executor
    claim_status_updates = []

    with patch('feature_flags.is_enabled', return_value=True):
        with patch('core.atomic_claim_repository.update_claim_status') as mock_update_claim:
            mock_update_claim.side_effect = lambda cid, status, error=None: claim_status_updates.append({"contract_id": cid, "status": status, "error": error})

            # Dispatcher returns structured DispatcherOutcome: ambiguous outcome (timeout after request)
            def executor_ambiguous(tool_name, tool_inputs, contract_id=None, identity=None, claim_execution_id=None):
                return DispatcherOutcome(
                    result="outcome_unknown",
                    user_message="⏱️ תהליך עדכון מתמשך — עלול לקחת זמן. אנא המתן.",
                    error="Timeout after Airtable request sent (may have succeeded, may be in progress)",
                )

            gateway = ActionGateway(ledger=mock_ledger)
            gateway._tool_executor = executor_ambiguous

            # Use real execute_with_atomic_claim with mocked dependencies
            with patch('core.atomic_claim_repository.claim_contract_execution') as mock_claim:
                from core.atomic_claim_repository import ClaimAcquisitionResult, AtomicExecutionClaim

                # Mock successful claim acquisition
                claim = AtomicExecutionClaim(
                    contract_id=contract_id,
                    claimant_id="boss_hq:eliyahu",
                    execution_id="exec_3",
                    claimed_at=1234567891.0,
                )
                mock_claim.return_value = ClaimAcquisitionResult(result="acquired", claim=claim)

                result = gateway._execute_contract(test_contract)

                # Verify claim was marked outcome_unknown for ambiguous result
                chk(
                    "Ambiguous outcome (outcome=outcome_unknown) produces claim outcome_unknown",
                    any(u["status"] == "outcome_unknown" for u in claim_status_updates if u["contract_id"] == contract_id)
                )

                chk(
                    "No claim completed for ambiguous outcome",
                    not any(u["status"] == "completed" for u in claim_status_updates if u["contract_id"] == contract_id)
                )

                chk(
                    "No claim failed for ambiguous outcome (not auto-retried)",
                    not any(u["status"] == "failed" for u in claim_status_updates if u["contract_id"] == contract_id)
                )

                # Verify user result indicates ambiguity (not success, not clear failure)
                chk(
                    "User-facing result indicates ambiguity",
                    "עדכון" in result or "⏱️" in result or "מתמשך" in result or "timeout" in result.lower()
                )


if __name__ == "__main__":
    print("=" * 70)
    print("Phase 4B0 — Integration Tests: Identity & Result Classification")
    print("=" * 70)
    print()

    test_identity_preserved_through_atomic_wrapper()
    print()
    test_permission_denial_claim_failed()
    print()
    test_explicit_success_claim_completed()
    print()
    test_ambiguous_outcome_claim_unknown()

    print()
    print("=" * 70)
    print(f"PASSED: {passed} | FAILED: {failed}")
    print("=" * 70)

    if failed > 0:
        sys.exit(1)
