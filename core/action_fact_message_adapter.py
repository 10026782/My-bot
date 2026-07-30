"""Pure ActionFact to MessageContract adapter (D-012 PR C).

Translates the existing internal ``ActionFact`` execution fact into the
canonical ``MessageContract`` envelope. This module performs no I/O, holds no
state, and has zero production callers — see
``docs/architecture/message_contract/ACTION_FACT_GATEWAY_REPLY_ADAPTER_SPEC.md``
for the full Planning Gate. It does not modify, wire, or call
``core/action_gateway.py``'s ``ActionFact``, ``GatewayReply``, or
``compose_status_reply()`` in any way.

State resolution is delegated entirely to
``core.message_contract.build_message_contract()``'s existing
``lifecycle_state``/``_state_from_lifecycle()`` precedence chain —
``ActionFact.outcome``'s closed four-value vocabulary
(``executed``/``failed``/``pending``/``rejected``) is a strict subset of what
that helper already accepts, so this adapter defines no competing state
table.
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
_VALID_OUTCOMES = frozenset({"executed", "failed", "pending", "rejected"})
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
    evidence_status: str | None = None,
    execution_verified: bool | None = None,
    occurred_at: str | None = None,
) -> MessageContract:
    outcome = fact.outcome
    if not isinstance(outcome, str) or outcome not in _VALID_OUTCOMES:
        raise MessageContractValidationError("unsupported ActionFact.outcome")
    if description is not None and not isinstance(description, str):
        raise MessageContractValidationError("description must be a string or None")

    reason_code = _reason_code_for(outcome, fact.error_code)
    entity_name = description if (description and description.strip()) else None

    return build_message_contract(
        lifecycle_state=outcome,
        multiple_pending=False,
        display_payload={"entity_name": entity_name},
        reply_owner=_REPLY_OWNER,
        turn_context_source=TurnContextSource.LEGACY_INGRESS,
        source_module=ADAPTER_SOURCE_MODULE,
        turn_id=None,
        evidence_status=evidence_status,
        evidence_ref=None,
        reason_code=reason_code,
        execution_verified=execution_verified,
        occurred_at=occurred_at,
    )
