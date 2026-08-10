"""Pure ActionFact to MessageContract adapter (D-012 PR C).

Translates the existing internal ``ActionFact`` execution fact into the
canonical ``MessageContract`` envelope. This module performs no I/O and holds
no state. It is called at the ActionGateway status-reply boundary; the adapter
does not own lifecycle, evidence, or reply-ownership decisions.

State resolution is delegated entirely to
``core.message_contract.build_message_contract()``'s existing
``lifecycle_state``/``_state_from_lifecycle()`` precedence chain —
``ActionFact.outcome`` is validated against the supported execution vocabulary
(``executed``/``failed``/``pending``/``rejected``/``outcome_unknown``), so this
adapter defines no competing state table.
"""

from __future__ import annotations

from typing import Protocol

from core.message_contract import (
    MessageContract,
    MessageContractValidationError,
    TurnContextSource,
    build_message_contract,
)

ADAPTER_SOURCE_MODULE = "core.action_fact_message_adapter"

_REPLY_OWNER = "gateway"
_VALID_OUTCOMES = frozenset({"executed", "failed", "pending", "rejected", "outcome_unknown"})
_REJECTED_REASON_CODE = "ACTION_REJECTED"


class ActionFactLike(Protocol):
    tool_name: str
    contract_id: str
    outcome: str
    record_id: str | None
    error_code: str | None
    raw_tool_response: dict


def _reason_code_for(outcome: str, error_code: object) -> str | None:
    if outcome == "failed":
        if error_code is not None and not isinstance(error_code, str):
            raise MessageContractValidationError("ActionFact.error_code must be a string or None")
        return error_code
    if outcome == "rejected":
        return _REJECTED_REASON_CODE
    return None


def from_action_fact(
    fact: ActionFactLike,
    *,
    description: str | None = None,
    entity_type: str | None = None,
    evidence_status: str | None = None,
    evidence_ref: str | None = None,
    execution_verified: bool | None = None,
    occurred_at: str | None = None,
    turn_id: str | None = None,
) -> MessageContract:
    outcome = fact.outcome
    if not isinstance(outcome, str) or outcome not in _VALID_OUTCOMES:
        raise MessageContractValidationError("unsupported ActionFact.outcome")
    if description is not None and not isinstance(description, str):
        raise MessageContractValidationError("description must be a string or None")
    if entity_type is not None and not isinstance(entity_type, str):
        raise MessageContractValidationError("entity_type must be a string or None")

    evidence_status = evidence_status if evidence_status is not None else getattr(fact, "evidence_status", None)
    evidence_ref = evidence_ref if evidence_ref is not None else getattr(fact, "evidence_ref", None)
    execution_verified = (
        execution_verified if execution_verified is not None
        else getattr(fact, "execution_verified", None)
    )
    occurred_at = occurred_at if occurred_at is not None else getattr(fact, "occurred_at", None)
    turn_id = turn_id if turn_id is not None else getattr(fact, "turn_id", None)

    reason_code = _reason_code_for(outcome, fact.error_code)
    entity_name = description if (description and description.strip()) else None

    return build_message_contract(
        lifecycle_state=outcome,
        multiple_pending=False,
        display_payload={
            "entity_name": entity_name,
            "entity_type": entity_type,
            "reason_code": reason_code,
            "execution_verified": execution_verified,
            "occurred_at": occurred_at,
        },
        reply_owner=_REPLY_OWNER,
        turn_context_source=TurnContextSource.LEGACY_INGRESS,
        source_module=ADAPTER_SOURCE_MODULE,
        turn_id=turn_id,
        evidence_status=evidence_status,
        evidence_ref=evidence_ref,
        reason_code=reason_code,
        execution_verified=execution_verified,
        occurred_at=occurred_at,
    )
