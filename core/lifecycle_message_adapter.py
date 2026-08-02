"""Pure WS2 lifecycle/evidence projections into the public MessageContract.

This module consumes structural views of the frozen WS2 contracts.  It never
imports runtime ownership, approval, queue, provider, or delivery code.
"""

from __future__ import annotations

from typing import Protocol

from core.message_contract import (
    MessageContract,
    MessageContractValidationError,
    TurnContextSource,
    build_message_contract,
)


ADAPTER_SOURCE_MODULE = "core.lifecycle_message_adapter"
_REPLY_OWNER = "gateway"


class ActionLifecycleResultLike(Protocol):
    contract_ref: str
    lifecycle_state: str
    approval_state: str
    execution_state: str
    reply_owner: str
    error_replay_classification: str


class EvidenceResultLike(Protocol):
    result: str
    evidence_ref: str
    provider_result: str
    verified: bool
    outcome_unknown: bool
    error: str


_LIFECYCLE_ALIASES = frozenset({
    "pending", "approved", "executing", "completed", "completed_verified",
    "failed", "cancelled", "rejected", "expired", "outcome_unknown",
    "duplicate", "stale", "not_found", "unavailable",
})
def _validate_evidence(evidence: EvidenceResultLike | None) -> None:
    if evidence is None:
        return
    if not isinstance(evidence.result, str) or not evidence.result.strip():
        raise MessageContractValidationError("EvidenceResult.result is required")
    for name in ("evidence_ref", "provider_result", "error"):
        if not isinstance(getattr(evidence, name), str):
            raise MessageContractValidationError(f"EvidenceResult.{name} must be a string")
    if not isinstance(evidence.verified, bool) or not isinstance(evidence.outcome_unknown, bool):
        raise MessageContractValidationError("EvidenceResult verification fields must be bool")


def _evidence_status(evidence: EvidenceResultLike | None) -> tuple[str | None, bool | None, str | None]:
    if evidence is None:
        return None, None, None
    _validate_evidence(evidence)
    if evidence.outcome_unknown:
        return "outcome_unknown", False, "OUTCOME_UNKNOWN"
    if evidence.error or evidence.result.strip().lower() in {"failed", "failure", "error"}:
        return "failure", False, "EVIDENCE_FAILURE"
    if evidence.verified:
        return "verified_write_success", True, None
    return "no_evidence", False, "EXECUTION_NOT_VERIFIED"


def _lifecycle_projection(state: str) -> tuple[str, str | None]:
    normalized = state.strip().lower() if isinstance(state, str) else ""
    if normalized not in _LIFECYCLE_ALIASES:
        raise MessageContractValidationError("unsupported ActionLifecycleResult.lifecycle_state")
    if normalized == "pending":
        return "pending", None
    if normalized in {"approved", "executing"}:
        return "approved", None
    if normalized in {"completed", "completed_verified"}:
        return "completed", None
    if normalized in {"failed", "expired", "unavailable"}:
        return "failed", {
            "expired": "ACTION_EXPIRED",
            "unavailable": "PROVIDER_UNAVAILABLE",
        }.get(normalized, "ACTION_FAILED")
    if normalized in {"cancelled", "rejected"}:
        return "rejected", "ACTION_CANCELLED"
    if normalized == "not_found":
        return "no_contract", "ACTION_NOT_FOUND"
    if normalized == "duplicate":
        return "outcome_unknown", "DUPLICATE_ACTION"
    return "outcome_unknown", "STALE_ACTION"


def from_action_lifecycle_result(
    result: ActionLifecycleResultLike,
    *,
    evidence: EvidenceResultLike | None = None,
    description: str | None = None,
) -> MessageContract:
    """Project frozen lifecycle data, optionally reconciled with evidence."""
    if not isinstance(result.lifecycle_state, str):
        raise MessageContractValidationError("ActionLifecycleResult.lifecycle_state must be a string")
    lifecycle_state, lifecycle_reason = _lifecycle_projection(result.lifecycle_state)
    evidence_status, execution_verified, evidence_reason = _evidence_status(evidence)

    # Terminal lifecycle authority wins over stale/pending prose. Evidence
    # failures and uncertainty are allowed to downgrade optimistic lifecycle
    # projections, including an approval/pending projection.
    if lifecycle_state == "rejected":
        evidence_status = None
        execution_verified = None
    elif evidence_status in {"failure", "failed"}:
        lifecycle_state = "failed"
    elif evidence_status in {"outcome_unknown", "unverified_effect", "mixed", "mixed_with_unknown"}:
        lifecycle_state = "completed"
    reason_code = lifecycle_reason or evidence_reason
    payload = {"entity_name": description if isinstance(description, str) and description.strip() else None}
    return build_message_contract(
        lifecycle_state=lifecycle_state,
        display_payload=payload,
        reply_owner=result.reply_owner or _REPLY_OWNER,
        turn_context_source=TurnContextSource.TURN_COORDINATOR,
        source_module=ADAPTER_SOURCE_MODULE,
        turn_id=None,
        evidence_status=evidence_status,
        evidence_ref=(evidence.evidence_ref or None) if evidence is not None else None,
        reason_code=reason_code,
        execution_verified=execution_verified,
        occurred_at=None,
    )
