# core/action_gateway_atomic_executor.py — Phase 4B0.1C ActionGateway atomic wiring
#
# Wraps ActionGateway execution through atomic claims repository.
# When FEATURE_ATOMIC_CLAIMS=true, every contract execution is gated by claim ownership.
# When flag=false, execution path is unchanged (backward compatible).
#
# Staging only: flag is OFF in production, so execution remains non-atomic until
# 48+ hours of staging verification confirms readiness for prod rollout.

from __future__ import annotations

import logging
import time
from typing import Optional, Any

logger = logging.getLogger(__name__)


def execute_with_atomic_claim(
    contract_id: str,
    canonical_user_id: str,
    tool_name: str,
    tool_inputs: dict,
    identity,
    executor_fn,
) -> tuple[bool, Any, Optional[str]]:
    """
    Execute a tool with atomic claim coordination.

    Args:
        contract_id: ActionContract.contract_id
        canonical_user_id: Approver's canonical_user_id
        tool_name: Name of tool to execute
        tool_inputs: Tool input payload
        identity: Identity object for dispatch
        executor_fn: Callable that calls dispatch_tool()

    Returns:
        (success: bool, result: any, error: optional str)

    Behavior:
        - FEATURE_ATOMIC_CLAIMS=false: calls executor_fn directly (backward compatible)
        - FEATURE_ATOMIC_CLAIMS=true, claim acquired: calls executor_fn with claim ownership
        - FEATURE_ATOMIC_CLAIMS=true, claim already held: returns failure (not acquired)
        - FEATURE_ATOMIC_CLAIMS=true, PostgreSQL unavailable: returns failure (fail-closed)
    """
    from feature_flags import is_enabled

    # If flag is OFF, execute normally (backward compatible)
    if not is_enabled("FEATURE_ATOMIC_CLAIMS"):
        logger.debug(f"FEATURE_ATOMIC_CLAIMS disabled — executing without claim: {contract_id}")
        try:
            result = executor_fn(tool_name, tool_inputs, identity)
            return (True, result, None)
        except Exception as e:
            return (False, None, str(e))

    # Flag is ON: require atomic claim
    from core.atomic_claim_repository import claim_contract_execution, update_claim_status

    # Attempt to claim
    result = claim_contract_execution(
        contract_id=contract_id,
        claimant_id=canonical_user_id,
        idempotency_key=None,  # Let repo generate unique execution_id
    )

    if result.is_disabled():
        # Flag OFF but we checked above — shouldn't happen
        logger.warning(f"Unexpected: flag check mismatch for {contract_id}")
        try:
            result_obj = executor_fn(tool_name, tool_inputs, identity)
            return (True, result_obj, None)
        except Exception as e:
            return (False, None, str(e))

    if result.is_unavailable():
        # PostgreSQL down or not configured — fail-closed
        logger.error(
            f"Atomic claim execution BLOCKED (PostgreSQL unavailable): contract={contract_id}, "
            f"canonical_user_id={canonical_user_id}. Never fall back to legacy execution path."
        )
        return (False, None, "PostgreSQL unavailable (atomic claims required but not available)")

    if result.is_error():
        # Unexpected error during claim attempt
        logger.error(
            f"Atomic claim acquisition failed with error: contract={contract_id}, error={result.error}"
        )
        return (False, None, f"Claim acquisition error: {result.error}")

    if result.is_already_claimed():
        # Another caller already owns this contract
        logger.info(
            f"Claim rejected (contract already being executed): contract={contract_id}, "
            f"attempted_by={canonical_user_id}"
        )
        return (
            False,
            None,
            "Contract is already being executed by another approver. Please wait or try again."
        )

    if result.is_contract_identity_conflict():
        # Same contract already being executed with different idempotency_key (concurrent execution)
        logger.error(
            f"Contract identity conflict (fail-closed): same contract already being executed "
            f"with different idempotency_key (concurrent execution attempt). "
            f"contract={contract_id}, canonical_user_id={canonical_user_id}, error={result.error}"
        )
        return (
            False,
            None,
            f"Contract is already being executed (fail-closed): {result.error}"
        )

    if result.is_idempotency_conflict():
        # Idempotency key already used for a different contract (identity/session mismatch)
        logger.error(
            f"Idempotency conflict (fail-closed): same idempotency_key used for different contract. "
            f"contract={contract_id}, canonical_user_id={canonical_user_id}, error={result.error}"
        )
        return (
            False,
            None,
            f"Identity/idempotency conflict detected (fail-closed): {result.error}"
        )

    if not result.is_acquired():
        # Shouldn't happen if all cases above handled
        logger.error(f"Unexpected claim result: {result.result}")
        return (False, None, "Unexpected claim result")

    # ✅ ACQUIRED: this caller owns the claim, may execute
    claim = result.claim
    logger.info(
        f"Claim acquired (execution ownership confirmed): contract={contract_id}, "
        f"execution_id={claim.execution_id}, canonical_user_id={canonical_user_id}"
    )

    # Execute the tool
    execution_error = None
    execution_result = None
    try:
        execution_result = executor_fn(tool_name, tool_inputs, identity)
        logger.info(
            f"Execution succeeded: contract={contract_id}, execution_id={claim.execution_id}, "
            f"tool={tool_name}"
        )
        # Update claim status: completed
        update_claim_status(contract_id, "completed")
        return (True, execution_result, None)

    except Exception as e:
        execution_error = str(e)
        logger.error(
            f"Execution failed: contract={contract_id}, execution_id={claim.execution_id}, "
            f"tool={tool_name}, error={e}"
        )
        # Update claim status: failed
        update_claim_status(contract_id, "failed", error=execution_error)
        return (False, None, execution_error)


def create_atomic_aware_executor(ledger, base_executor_fn):
    """
    Factory: creates an executor that wraps base_executor_fn with atomic claims.

    Args:
        ledger: ExecutionLedger instance (to look up contracts)
        base_executor_fn: Original executor that calls dispatch_tool

    Returns:
        New executor function that gates dispatch through atomic claims
    """

    def atomic_executor(tool_name: str, tool_inputs: dict, contract_id: str):
        """Atomic-aware executor for use in _execute_contract."""
        from identity import Identity, resolve_identity

        # Reconstruct identity from contract (same as original)
        identity = None
        contract = ledger.find_by_id(contract_id)
        if contract:
            if contract.actor_role and contract.actor_external_id:
                identity = Identity(
                    user_id=contract.actor_user_id or contract.canonical_user_id,
                    role=contract.actor_role,
                    display_name=contract.actor_display_name,
                    tenant_id=contract.tenant_id,
                    domain_id=contract.actor_domain_id or "general",
                    allowed_domains=list(contract.actor_allowed_domains or []),
                    channel=contract.origin_channel,
                    external_id=contract.actor_external_id,
                )
                logger.info(
                    "[ActionGateway] approved by=%s/%s@%s | atomic execution (claim gated)",
                    contract.tenant_id, identity.user_id, contract.actor_role,
                )
            else:
                try:
                    identity = resolve_identity(contract.origin_channel, contract.origin_chat_id)
                except Exception as exc:
                    logger.warning("[ActionGateway] identity resolve failed: %s", exc)

        # Execute with atomic claim coordination
        success, tool_result, error = execute_with_atomic_claim(
            contract_id=contract_id,
            canonical_user_id=contract.canonical_user_id if contract else "unknown",
            tool_name=tool_name,
            tool_inputs=tool_inputs,
            identity=identity,
            executor_fn=base_executor_fn,
        )

        if success:
            return tool_result
        else:
            # Execution failed or claim was not acquired
            raise RuntimeError(f"Execution failed: {error or 'unknown error'}")

    return atomic_executor
