"""Pure ApprovalLifecycleResult to MessageContract adapter (D-012 PR B).

The module deliberately uses a structural protocol instead of importing
``core.action_gateway``.  Importing or calling this adapter therefore adds no
gateway/runtime dependency edge and performs no lifecycle or evidence lookup.
"""

from __future__ import annotations

from typing import Protocol

from core.message_contract import (
    MessageContract,
    MessageContractValidationError,
    MessageState,
    TurnContextSource,
    build_message_contract,
)


ADAPTER_SOURCE_MODULE = "core.approval_lifecycle_message_adapter"


class ApprovalLifecycleResultLike(Protocol):
    """Structural view of the existing internal approval result contract."""

    canonical_state: str
    reply_owner: str
    safe_business_description: str
    safe_user_message: str
    contract_id: str | None
    is_final: bool
    should_remove_keyboard: bool
    final_response_required: bool
    final_response_count: int


_CANONICAL_STATE_MAP = {
    "pending": MessageState.APPROVAL_PENDING,
    "pending_conflict": MessageState.APPROVAL_PENDING,
    "authorization_denied": MessageState.APPROVAL_PENDING,
    "multiple_pending": MessageState.APPROVAL_PENDING_BATCH,
    "approved_processing": MessageState.APPROVED_PROCESSING,
    "completed": MessageState.OUTCOME_UNKNOWN,
    "rejected": MessageState.CANCELLED,
    "failed": MessageState.FAILURE,
    "outcome_unknown": MessageState.OUTCOME_UNKNOWN,
    "no_contract": MessageState.NO_PENDING_ACTION,
}


def _message_state(canonical_state: str, *, repeated: bool) -> MessageState:
    if not isinstance(canonical_state, str) or not canonical_state.strip():
        raise MessageContractValidationError(
            "ApprovalLifecycleResult.canonical_state must be a non-empty string"
        )
    if canonical_state == "completed" and repeated:
        return MessageState.ALREADY_COMPLETED
    if canonical_state == "rejected" and repeated:
        return MessageState.ALREADY_CANCELLED
    try:
        return _CANONICAL_STATE_MAP[canonical_state]
    except KeyError as exc:
        raise MessageContractValidationError(
            "unsupported ApprovalLifecycleResult.canonical_state"
        ) from exc


def from_approval_lifecycle_result(
    result: ApprovalLifecycleResultLike,
    *,
    repeated: bool = False,
) -> MessageContract:
    """Adapt structured approval semantics into the canonical envelope.

    ``repeated`` is explicit because the existing result does not retain that
    input.  The adapter never parses ``safe_user_message`` and never promotes
    ``contract_id`` to either display data or evidence metadata.
    """
    if not isinstance(repeated, bool):
        raise MessageContractValidationError("repeated must be bool")

    description = result.safe_business_description
    if not isinstance(description, str):
        raise MessageContractValidationError(
            "ApprovalLifecycleResult.safe_business_description must be a string"
        )

    return build_message_contract(
        state=_message_state(result.canonical_state, repeated=repeated),
        display_payload={"entity_name": description if description.strip() else None},
        reply_owner=result.reply_owner,
        turn_context_source=TurnContextSource.LEGACY_INGRESS,
        source_module=ADAPTER_SOURCE_MODULE,
        turn_id=None,
        evidence_status=None,
        evidence_ref=None,
        reason_code=None,
        execution_verified=None,
        occurred_at=None,
    )
