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
    idempotency_key: Optional[str] = None,
) -> tuple[bool, Any, Optional[str]]:
    """
    Execute a tool with atomic claim coordination.

    Args:
        contract_id: ActionContract.contract_id
        canonical_user_id: Approver's canonical_user_id
        tool_name: Name of tool to execute
        tool_inputs: Tool input payload
        identity: Identity object for dispatch
        executor_fn: Callable that calls dispatch_tool() — MUST be invoked by keyword
            (contract_id=..., identity=...), never positionally. The real production
            executor (core.action_gateway._make_dispatch_executor) has the signature
            (tool_name, tool_inputs, contract_id, identity=None) — a positional 3rd
            argument silently binds to contract_id, not identity (BUG: unhashable
            Identity used as a dict key inside ledger.find_by_id()).
        idempotency_key: Optional deterministic key for retry-safety; if None, generated as UUID

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
            result = executor_fn(tool_name, tool_inputs, contract_id=contract_id, identity=identity)
            return (True, result, None)
        except Exception as e:
            return (False, None, str(e))

    # Flag is ON: require atomic claim
    from core.atomic_claim_repository import claim_contract_execution, update_claim_status

    # Attempt to claim
    result = claim_contract_execution(
        contract_id=contract_id,
        claimant_id=canonical_user_id,
        idempotency_key=idempotency_key,
    )

    if result.is_disabled():
        # Flag OFF but we checked above — shouldn't happen
        logger.warning(f"Unexpected: flag check mismatch for {contract_id}")
        try:
            result_obj = executor_fn(tool_name, tool_inputs, contract_id=contract_id, identity=identity)
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

    # Execute the tool — expects structured DispatcherOutcome
    execution_error = None
    execution_result = None
    try:
        raw_outcome = executor_fn(tool_name, tool_inputs, contract_id=contract_id, identity=identity)

        # Phase 4B0: consume an explicit structured outcome, never infer truth from
        # user_message text. The real production executor (_make_dispatch_executor)
        # returns dispatch_tool()'s raw C53-A result (dict/string), not a
        # DispatcherOutcome — classify it via the same evidence-based verifier
        # _execute_contract's legacy path already trusts (verify_execution), so a
        # real successful write actually reaches "completed" instead of always
        # failing closed on a type mismatch. A caller that already returns a
        # DispatcherOutcome directly (e.g. a future ambiguous-outcome-aware
        # dispatcher, or tests) is used as-is.
        from core.dispatcher_outcome import DispatcherOutcome

        if isinstance(raw_outcome, DispatcherOutcome):
            outcome = raw_outcome
        else:
            from core.anti_hallucination import verify_execution
            check = verify_execution(tool_name, raw_outcome)
            _raw_dict = raw_outcome if isinstance(raw_outcome, dict) else None
            _user_message = (
                raw_outcome.get("user_message", "") if isinstance(raw_outcome, dict)
                else (raw_outcome if isinstance(raw_outcome, str) else "")
            )
            _ext_id = raw_outcome.get("external_id", "") if isinstance(raw_outcome, dict) else ""
            if check.status == "ok":
                outcome = DispatcherOutcome(
                    result="completed",
                    user_message=_user_message,
                    external_id=_ext_id,
                    raw_response=_raw_dict,
                )
            else:
                outcome = DispatcherOutcome(
                    result="failed",
                    user_message=_user_message,
                    error=check.reason,
                    raw_response=_raw_dict,
                )

        logger.debug(
            f"Execution returned outcome: contract={contract_id}, execution_id={claim.execution_id}, "
            f"tool={tool_name}, result={outcome.result}, external_id={outcome.external_id}"
        )

        # Classify based on explicit outcome result (not string parsing)
        if outcome.is_completed():
            logger.info(
                f"Execution succeeded (explicit): contract={contract_id}, execution_id={claim.execution_id}, "
                f"tool={tool_name}, external_id={outcome.external_id}"
            )
            # Update claim status: completed
            update_claim_status(contract_id, "completed")
            return (True, outcome, None)

        elif outcome.is_failed():
            logger.error(
                f"Execution failed (explicit): contract={contract_id}, execution_id={claim.execution_id}, "
                f"tool={tool_name}, error_code={outcome.error_code}, error={outcome.error}"
            )
            # Update claim status: failed
            update_claim_status(contract_id, "failed", error=outcome.error)
            return (False, None, outcome.error)

        elif outcome.is_outcome_unknown():
            logger.warning(
                f"Execution outcome unknown (ambiguous): contract={contract_id}, execution_id={claim.execution_id}, "
                f"tool={tool_name}, error={outcome.error} (DO NOT AUTO-RETRY)"
            )
            # Update claim status: outcome_unknown (never auto-retry)
            update_claim_status(contract_id, "outcome_unknown", error=outcome.error)
            return (False, None, f"Outcome unknown (may be in progress): {outcome.error}")

    except Exception as e:
        execution_error = str(e)
        logger.error(
            f"Execution failed (exception): contract={contract_id}, execution_id={claim.execution_id}, "
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
