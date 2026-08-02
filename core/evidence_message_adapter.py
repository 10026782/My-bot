"""Pure WS2 EvidenceResult projection into MessageContract."""

from __future__ import annotations

from core.lifecycle_message_adapter import (
    EvidenceResultLike,
    _evidence_status,
)
from core.message_contract import MessageContract, TurnContextSource, build_message_contract

ADAPTER_SOURCE_MODULE = "core.evidence_message_adapter"


def from_evidence_result(
    result: EvidenceResultLike,
    *,
    description: str | None = None,
    reply_owner: str = "gateway",
) -> MessageContract:
    """Project evidence without exposing provider text or raw exceptions."""
    evidence_status, execution_verified, reason_code = _evidence_status(result)
    lifecycle_state = "completed" if evidence_status not in {"failure", "outcome_unknown", "no_evidence"} else (
        "failed" if evidence_status == "failure" else "outcome_unknown"
    )
    return build_message_contract(
        lifecycle_state=lifecycle_state,
        display_payload={
            "entity_name": description if isinstance(description, str) and description.strip() else None,
            "execution_verified": execution_verified,
        },
        reply_owner=reply_owner,
        turn_context_source=TurnContextSource.TURN_COORDINATOR,
        source_module=ADAPTER_SOURCE_MODULE,
        turn_id=None,
        evidence_status=evidence_status,
        evidence_ref=result.evidence_ref or None,
        reason_code=reason_code,
        execution_verified=execution_verified,
        occurred_at=None,
    )
