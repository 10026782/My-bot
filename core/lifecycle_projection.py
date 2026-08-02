from __future__ import annotations

import time
from typing import Any

from core.router.ownership_contracts import ActionLifecycleResult


def build_action_lifecycle_result(
    contract: Any | None,
    *,
    now: float | None = None,
    reply_owner: str = "gateway",
    error_replay_classification: str = "",
) -> ActionLifecycleResult:
    """Build a deterministic WS2 lifecycle projection from an ActionContract.

    The projection is pure and fail-closed: a missing or unknown contract yields
    a non-success projection rather than inventing an execution state.
    """
    if contract is None:
        return ActionLifecycleResult(
            contract_ref="",
            lifecycle_state="missing",
            approval_state="missing",
            execution_state="missing",
            reply_owner=reply_owner,
            error_replay_classification=error_replay_classification or "missing_snapshot",
        )

    status = str(getattr(contract, "status", "") or "")
    contract_ref = str(getattr(contract, "contract_id", "") or "")
    created_at = getattr(contract, "created_at", None)
    current_time = now if now is not None else time.time()

    if status == "pending":
        if isinstance(created_at, (int, float)) and (current_time - float(created_at)) > 24 * 3600:
            return ActionLifecycleResult(
                contract_ref=contract_ref,
                lifecycle_state="expired",
                approval_state="pending",
                execution_state="not_started",
                reply_owner=reply_owner,
                error_replay_classification=error_replay_classification or "expired",
            )
        return ActionLifecycleResult(
            contract_ref=contract_ref,
            lifecycle_state="pending",
            approval_state="pending",
            execution_state="not_started",
            reply_owner=reply_owner,
            error_replay_classification=error_replay_classification or "",
        )

    if status == "approved":
        return ActionLifecycleResult(
            contract_ref=contract_ref,
            lifecycle_state="approved",
            approval_state="approved",
            execution_state="not_started",
            reply_owner=reply_owner,
            error_replay_classification=error_replay_classification or "",
        )

    if status == "executing":
        return ActionLifecycleResult(
            contract_ref=contract_ref,
            lifecycle_state="executing",
            approval_state="approved",
            execution_state="in_progress",
            reply_owner=reply_owner,
            error_replay_classification=error_replay_classification or "",
        )

    if status in {"completed", "executed"}:
        return ActionLifecycleResult(
            contract_ref=contract_ref,
            lifecycle_state="completed",
            approval_state="approved",
            execution_state="succeeded",
            reply_owner=reply_owner,
            error_replay_classification=error_replay_classification or "",
        )

    if status == "failed":
        return ActionLifecycleResult(
            contract_ref=contract_ref,
            lifecycle_state="failed",
            approval_state="approved",
            execution_state="failed",
            reply_owner=reply_owner,
            error_replay_classification=error_replay_classification or "",
        )

    if status == "outcome_unknown":
        return ActionLifecycleResult(
            contract_ref=contract_ref,
            lifecycle_state="outcome_unknown",
            approval_state="approved",
            execution_state="outcome_unknown",
            reply_owner=reply_owner,
            error_replay_classification=error_replay_classification or "",
        )

    if status == "rejected":
        return ActionLifecycleResult(
            contract_ref=contract_ref,
            lifecycle_state="rejected",
            approval_state="rejected",
            execution_state="not_started",
            reply_owner=reply_owner,
            error_replay_classification=error_replay_classification or "",
        )

    return ActionLifecycleResult(
        contract_ref=contract_ref,
        lifecycle_state="missing",
        approval_state="missing",
        execution_state="missing",
        reply_owner=reply_owner,
        error_replay_classification=error_replay_classification or "missing_snapshot",
    )
