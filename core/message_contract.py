"""Pure Message Contract Envelope foundation (D-012 / schema v1).

This module owns semantic message data only.  It performs no I/O, reads no
runtime state, and makes no routing, lifecycle, evidence, or reply-ownership
decision.  Existing authorities supply structured values; the builder validates
and conservatively projects them into the frozen public presentation contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from enum import Enum
from typing import Any, Mapping


MESSAGE_CONTRACT_VERSION = "1.0"


class MessageContractValidationError(ValueError):
    """Raised when contract data violates the closed v1 schema."""


class MessageState(str, Enum):
    NEEDS_INPUT = "needs_input"
    APPROVAL_PENDING = "approval_pending"
    APPROVAL_PENDING_BATCH = "approval_pending_batch"
    APPROVED_PROCESSING = "approved_processing"
    SUCCESS = "success"
    FAILURE = "failure"
    OUTCOME_UNKNOWN = "outcome_unknown"
    UNVERIFIED_EFFECT = "unverified_effect"
    MIXED = "mixed"
    MIXED_WITH_UNKNOWN = "mixed_with_unknown"
    CANCELLED = "cancelled"
    ALREADY_COMPLETED = "already_completed"
    ALREADY_CANCELLED = "already_cancelled"
    NO_PENDING_ACTION = "no_pending_action"
    NEUTRAL = "neutral"


class TurnContextSource(str, Enum):
    TURN_COORDINATOR = "turn_coordinator"
    LEGACY_INGRESS = "legacy_ingress"
    UNAVAILABLE = "unavailable"


class InteractionType(str, Enum):
    CONFIRM_CANCEL = "confirm_cancel"
    SINGLE_CHOICE = "single_choice"
    MULTI_CHOICE = "multi_choice"
    FREE_TEXT = "free_text"
    REVIEW_EDIT = "review_edit"


_INTERACTION_KEYS = frozenset({
    "type", "actions", "options", "field", "selected_values", "editable",
})


def _string_tuple(value: Any, field_name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple)):
        raise MessageContractValidationError(f"{field_name} must be a sequence")
    return tuple(_required_string(item, f"{field_name} item") for item in value)


@dataclass(frozen=True)
class MessageInteraction:
    """Provider-neutral interaction intent for a public message surface."""

    type: InteractionType
    actions: tuple[str, ...] = dataclass_field(default_factory=tuple)
    options: tuple[str, ...] = dataclass_field(default_factory=tuple)
    field: str | None = None
    selected_values: tuple[str, ...] = dataclass_field(default_factory=tuple)
    editable: bool = False

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> "MessageInteraction | None":
        if data is None:
            return None
        if not isinstance(data, Mapping):
            raise MessageContractValidationError("interaction must be a mapping")
        _reject_unknown_keys(data, _INTERACTION_KEYS, "MessageInteraction")
        try:
            interaction_type = InteractionType(data.get("type"))
        except (TypeError, ValueError) as exc:
            raise MessageContractValidationError("invalid interaction type") from exc
        editable = data.get("editable", False)
        if not isinstance(editable, bool):
            raise MessageContractValidationError("interaction.editable must be bool")
        return cls(
            type=interaction_type,
            actions=_string_tuple(data.get("actions"), "interaction.actions"),
            options=_string_tuple(data.get("options"), "interaction.options"),
            field=_optional_string(data.get("field"), "interaction.field"),
            selected_values=_string_tuple(data.get("selected_values"), "interaction.selected_values"),
            editable=editable,
        )

    def __post_init__(self) -> None:
        if not isinstance(self.type, InteractionType):
            raise MessageContractValidationError("interaction.type must be an InteractionType")
        for name in ("actions", "options", "selected_values"):
            values = getattr(self, name)
            if not isinstance(values, tuple) or any(not isinstance(value, str) or not value.strip() for value in values):
                raise MessageContractValidationError(f"interaction.{name} must contain non-empty strings")
        _optional_string(self.field, "interaction.field")
        if not isinstance(self.editable, bool):
            raise MessageContractValidationError("interaction.editable must be bool")
        if self.type is InteractionType.SINGLE_CHOICE and len(self.selected_values) > 1:
            raise MessageContractValidationError("single_choice supports at most one selected value")

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type.value,
            "actions": list(self.actions),
            "options": list(self.options),
            "field": self.field,
            "selected_values": list(self.selected_values),
            "editable": self.editable,
        }


_DISPLAY_PAYLOAD_KEYS = frozenset({
    "action",
    "entity_type",
    "entity_name",
    "key_fields",
    "count",
    "items",
    "reason_code",
    "execution_verified",
    "occurred_at",
})
_DISPLAY_FIELD_KEYS = frozenset({"label", "value", "is_date", "occurred_at"})
_DISPLAY_ITEM_KEYS = frozenset({"human_summary", "entity_name", "label"})
_ACTIONS = frozenset({"create", "update", "delete", "send"})
_VERIFIED_SUCCESS_EVIDENCE = frozenset({
    "verified_write_success",
    "verified_read_only",
})
_COMPLETED_EVIDENCE_STATES = frozenset({
    *_VERIFIED_SUCCESS_EVIDENCE,
    "failure",
    "failed",
    "outcome_unknown",
    "unverified_effect",
    "mixed",
    "mixed_with_unknown",
    "no_evidence",
})
_CANONICAL_EVIDENCE_STATUSES = frozenset({
    *_COMPLETED_EVIDENCE_STATES,
    "approval_pending",
})


def _optional_string(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise MessageContractValidationError(f"{field_name} must be a non-empty string or None")
    return value


def _required_string(value: Any, field_name: str) -> str:
    result = _optional_string(value, field_name)
    if result is None:
        raise MessageContractValidationError(f"{field_name} is required")
    return result


def _reject_unknown_keys(data: Mapping[str, Any], allowed: frozenset[str], name: str) -> None:
    unknown = set(data) - allowed
    if unknown:
        joined = ", ".join(sorted(str(key) for key in unknown))
        raise MessageContractValidationError(f"{name} contains unsupported fields: {joined}")


@dataclass(frozen=True)
class DisplayField:
    label: str | None = None
    value: str | int | float | bool | None = None
    is_date: bool = False
    occurred_at: bool = False

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "DisplayField":
        if not isinstance(data, Mapping):
            raise MessageContractValidationError("each key_fields item must be a mapping")
        _reject_unknown_keys(data, _DISPLAY_FIELD_KEYS, "DisplayField")
        label = _optional_string(data.get("label"), "DisplayField.label")
        value = data.get("value")
        if value is not None and not isinstance(value, (str, int, float, bool)):
            raise MessageContractValidationError("DisplayField.value must be a scalar or None")
        for key in ("is_date", "occurred_at"):
            if key in data and not isinstance(data[key], bool):
                raise MessageContractValidationError(f"DisplayField.{key} must be bool")
        return cls(
            label=label,
            value=value,
            is_date=bool(data.get("is_date", False)),
            occurred_at=bool(data.get("occurred_at", False)),
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"label": self.label, "value": self.value}
        if self.is_date:
            result["is_date"] = True
        if self.occurred_at:
            result["occurred_at"] = True
        return result


@dataclass(frozen=True)
class DisplayItem:
    human_summary: str | None = None
    entity_name: str | None = None
    label: str | None = None

    @classmethod
    def from_value(cls, value: Any) -> "DisplayItem":
        if isinstance(value, str):
            return cls(human_summary=_required_string(value, "DisplayItem.human_summary"))
        if not isinstance(value, Mapping):
            raise MessageContractValidationError("each items entry must be a string or mapping")
        _reject_unknown_keys(value, _DISPLAY_ITEM_KEYS, "DisplayItem")
        item = cls(
            human_summary=_optional_string(value.get("human_summary"), "DisplayItem.human_summary"),
            entity_name=_optional_string(value.get("entity_name"), "DisplayItem.entity_name"),
            label=_optional_string(value.get("label"), "DisplayItem.label"),
        )
        if not any((item.human_summary, item.entity_name, item.label)):
            raise MessageContractValidationError("DisplayItem requires one safe display value")
        return item

    def to_dict(self) -> dict[str, str]:
        return {
            key: value
            for key, value in (
                ("human_summary", self.human_summary),
                ("entity_name", self.entity_name),
                ("label", self.label),
            )
            if value is not None
        }


@dataclass(frozen=True)
class DisplayPayload:
    action: str | None = None
    entity_type: str | None = None
    entity_name: str | None = None
    key_fields: tuple[DisplayField, ...] = dataclass_field(default_factory=tuple)
    count: int | None = None
    items: tuple[DisplayItem, ...] = dataclass_field(default_factory=tuple)
    reason_code: str | None = None
    execution_verified: bool | None = None
    occurred_at: str | None = None

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any] | None) -> "DisplayPayload":
        if data is None:
            return cls()
        if not isinstance(data, Mapping):
            raise MessageContractValidationError("display_payload must be a mapping")
        _reject_unknown_keys(data, _DISPLAY_PAYLOAD_KEYS, "DisplayPayload")

        action = _optional_string(data.get("action"), "DisplayPayload.action")
        if action is not None and action not in _ACTIONS:
            raise MessageContractValidationError("DisplayPayload.action is not in the v1 registry")

        raw_fields = data.get("key_fields", ())
        raw_items = data.get("items", ())
        if raw_fields is None:
            raw_fields = ()
        if raw_items is None:
            raw_items = ()
        if not isinstance(raw_fields, (list, tuple)):
            raise MessageContractValidationError("DisplayPayload.key_fields must be a sequence")
        if not isinstance(raw_items, (list, tuple)):
            raise MessageContractValidationError("DisplayPayload.items must be a sequence")
        if len(raw_fields) > 2:
            raise MessageContractValidationError("DisplayPayload.key_fields supports at most two entries")
        if len(raw_items) > 10:
            raise MessageContractValidationError("DisplayPayload.items supports at most ten entries")

        count = data.get("count")
        if count is not None and (isinstance(count, bool) or not isinstance(count, int) or count < 0):
            raise MessageContractValidationError("DisplayPayload.count must be a non-negative integer or None")
        execution_verified = data.get("execution_verified")
        if execution_verified is not None and not isinstance(execution_verified, bool):
            raise MessageContractValidationError("DisplayPayload.execution_verified must be bool or None")

        return cls(
            action=action,
            entity_type=_optional_string(data.get("entity_type"), "DisplayPayload.entity_type"),
            entity_name=_optional_string(data.get("entity_name"), "DisplayPayload.entity_name"),
            key_fields=tuple(DisplayField.from_mapping(item) for item in raw_fields),
            count=count,
            items=tuple(DisplayItem.from_value(item) for item in raw_items),
            reason_code=_optional_string(data.get("reason_code"), "DisplayPayload.reason_code"),
            execution_verified=execution_verified,
            occurred_at=_optional_string(data.get("occurred_at"), "DisplayPayload.occurred_at"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "entity_type": self.entity_type,
            "entity_name": self.entity_name,
            "key_fields": [item.to_dict() for item in self.key_fields],
            "count": self.count,
            "items": [item.to_dict() for item in self.items],
            "reason_code": self.reason_code,
            "execution_verified": self.execution_verified,
            "occurred_at": self.occurred_at,
        }

    def completeness(self) -> str:
        if any((self.entity_name, self.key_fields, self.items, self.action)):
            return "structured"
        if any((self.entity_type, self.reason_code, self.count is not None, self.occurred_at)):
            return "partial"
        return "empty"


@dataclass(frozen=True)
class MessageContract:
    version: str
    state: MessageState
    display_payload: DisplayPayload
    reply_owner: str
    turn_context_source: TurnContextSource
    source_module: str
    turn_id: str | None = None
    evidence_status: str | None = None
    evidence_ref: str | None = None
    reason_code: str | None = None
    execution_verified: bool | None = None
    occurred_at: str | None = None
    interaction: MessageInteraction | None = None

    def __post_init__(self) -> None:
        if self.version != MESSAGE_CONTRACT_VERSION:
            raise MessageContractValidationError(f"unsupported MessageContract version: {self.version!r}")
        if not isinstance(self.state, MessageState):
            raise MessageContractValidationError("state must be a MessageState")
        if not isinstance(self.display_payload, DisplayPayload):
            raise MessageContractValidationError("display_payload must be a DisplayPayload")
        if self.interaction is not None and not isinstance(self.interaction, MessageInteraction):
            raise MessageContractValidationError("interaction must be a MessageInteraction or None")
        if not isinstance(self.turn_context_source, TurnContextSource):
            raise MessageContractValidationError("turn_context_source must be a TurnContextSource")
        _required_string(self.reply_owner, "reply_owner")
        _required_string(self.source_module, "source_module")
        for field_name in ("turn_id", "evidence_status", "evidence_ref", "reason_code", "occurred_at"):
            _optional_string(getattr(self, field_name), field_name)
        if self.execution_verified is not None and not isinstance(self.execution_verified, bool):
            raise MessageContractValidationError("execution_verified must be bool or None")
        if (
            self.evidence_status is not None
            and self.evidence_status not in _CANONICAL_EVIDENCE_STATUSES
        ):
            raise MessageContractValidationError("unsupported evidence_status")
        if self.state is MessageState.SUCCESS and (
            self.execution_verified is not True
            or self.evidence_status not in _VERIFIED_SUCCESS_EVIDENCE
        ):
            raise MessageContractValidationError("success requires matching verified evidence")
        self._require_payload_metadata_match("reason_code")
        self._require_payload_metadata_match("execution_verified")
        self._require_payload_metadata_match("occurred_at")

    def _require_payload_metadata_match(self, field_name: str) -> None:
        contract_value = getattr(self, field_name)
        payload_value = getattr(self.display_payload, field_name)
        if contract_value is not None and payload_value is not None and contract_value != payload_value:
            raise MessageContractValidationError(f"{field_name} conflicts with display_payload")

    def user_safe_record(self) -> dict[str, Any]:
        result = {
            "state": self.state.value,
            "display_payload": self.display_payload.to_dict(),
        }
        if self.interaction is not None:
            result["interaction"] = self.interaction.to_dict()
        return result

    def observability_record(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "turn_id": self.turn_id,
            "reply_owner_candidate": self.reply_owner,
            "turn_context_source": self.turn_context_source.value,
            "state": self.state.value,
            "source_component": self.source_module,
            "evidence_status": self.evidence_status,
            "evidence_ref": self.evidence_ref,
            "reason_code": self.reason_code,
            "execution_verified": self.execution_verified,
            "occurred_at": self.occurred_at,
            "payload_completeness": self.display_payload.completeness(),
        }

    def to_dict(self) -> dict[str, Any]:
        result = {
            "version": self.version,
            "turn_id": self.turn_id,
            "reply_owner": self.reply_owner,
            "turn_context_source": self.turn_context_source.value,
            "state": self.state.value,
            "display_payload": self.display_payload.to_dict(),
            "reason_code": self.reason_code,
            "execution_verified": self.execution_verified,
            "source_module": self.source_module,
            "evidence_status": self.evidence_status,
            "evidence_ref": self.evidence_ref,
            "occurred_at": self.occurred_at,
        }
        if self.interaction is not None:
            result["interaction"] = self.interaction.to_dict()
        return result

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "MessageContract":
        if not isinstance(data, Mapping):
            raise MessageContractValidationError("MessageContract data must be a mapping")
        allowed = frozenset({
            "version", "turn_id", "reply_owner", "turn_context_source",
            "state", "display_payload", "reason_code", "execution_verified",
            "source_module", "evidence_status", "evidence_ref", "occurred_at",
            "interaction",
        })
        _reject_unknown_keys(data, allowed, "MessageContract")
        if "display_payload" not in data:
            raise MessageContractValidationError("MessageContract.display_payload is required")
        try:
            state = MessageState(data.get("state"))
        except (TypeError, ValueError) as exc:
            raise MessageContractValidationError("invalid MessageState") from exc
        try:
            context_source = TurnContextSource(data.get("turn_context_source"))
        except (TypeError, ValueError) as exc:
            raise MessageContractValidationError("invalid turn_context_source") from exc
        return cls(
            version=data.get("version"),
            state=state,
            display_payload=DisplayPayload.from_mapping(data.get("display_payload")),
            reply_owner=data.get("reply_owner"),
            turn_context_source=context_source,
            source_module=data.get("source_module"),
            turn_id=data.get("turn_id"),
            evidence_status=data.get("evidence_status"),
            evidence_ref=data.get("evidence_ref"),
            reason_code=data.get("reason_code"),
            execution_verified=data.get("execution_verified"),
            occurred_at=data.get("occurred_at"),
            interaction=MessageInteraction.from_mapping(data.get("interaction")),
        )


def _coerce_message_state(value: MessageState | str) -> MessageState:
    if isinstance(value, MessageState):
        return value
    try:
        return MessageState(value)
    except (TypeError, ValueError) as exc:
        raise MessageContractValidationError("invalid MessageState") from exc


def _coerce_context_source(value: TurnContextSource | str) -> TurnContextSource:
    if isinstance(value, TurnContextSource):
        return value
    try:
        return TurnContextSource(value)
    except (TypeError, ValueError) as exc:
        raise MessageContractValidationError("invalid turn_context_source") from exc


def _state_from_lifecycle(
    lifecycle_state: str,
    evidence_status: str | None,
    *,
    multiple_pending: bool,
) -> MessageState:
    lifecycle = _required_string(lifecycle_state, "lifecycle_state").lower()
    if lifecycle == "pending":
        return MessageState.APPROVAL_PENDING_BATCH if multiple_pending else MessageState.APPROVAL_PENDING
    if lifecycle == "rejected":
        return MessageState.CANCELLED
    if lifecycle == "failed":
        return MessageState.FAILURE
    if lifecycle in {"approved", "executing"}:
        return MessageState.APPROVED_PROCESSING
    if lifecycle in {"completed", "executed"}:
        if evidence_status is None or evidence_status == "no_evidence":
            return MessageState.OUTCOME_UNKNOWN
        if evidence_status not in _COMPLETED_EVIDENCE_STATES:
            raise MessageContractValidationError("unsupported evidence_status for completed lifecycle")
        return {
            "verified_write_success": MessageState.SUCCESS,
            "verified_read_only": MessageState.SUCCESS,
            "failure": MessageState.FAILURE,
            "failed": MessageState.FAILURE,
            "outcome_unknown": MessageState.OUTCOME_UNKNOWN,
            "unverified_effect": MessageState.UNVERIFIED_EFFECT,
            "mixed": MessageState.MIXED,
            "mixed_with_unknown": MessageState.MIXED_WITH_UNKNOWN,
        }.get(evidence_status, MessageState.OUTCOME_UNKNOWN)
    if lifecycle == "outcome_unknown":
        return MessageState.OUTCOME_UNKNOWN
    if lifecycle in {"draft", "no_contract"}:
        return MessageState.NO_PENDING_ACTION
    raise MessageContractValidationError("unsupported lifecycle_state")


def _coalesce_payload_metadata(
    explicit_value: Any,
    payload_value: Any,
    field_name: str,
) -> Any:
    if explicit_value is not None and payload_value is not None and explicit_value != payload_value:
        raise MessageContractValidationError(f"{field_name} conflicts with display_payload")
    return explicit_value if explicit_value is not None else payload_value


def build_message_contract(
    *,
    reply_owner: str,
    turn_context_source: TurnContextSource | str,
    source_module: str,
    display_payload: DisplayPayload | Mapping[str, Any] | None = None,
    state: MessageState | str | None = None,
    lifecycle_state: str | None = None,
    multiple_pending: bool = False,
    turn_id: str | None = None,
    evidence_status: str | None = None,
    evidence_ref: str | None = None,
    reason_code: str | None = None,
    execution_verified: bool | None = None,
    occurred_at: str | None = None,
    interaction: MessageInteraction | Mapping[str, Any] | None = None,
    version: str = MESSAGE_CONTRACT_VERSION,
) -> MessageContract:
    """Build one immutable envelope from already-structured authority data."""
    if state is not None and lifecycle_state is not None:
        raise MessageContractValidationError("provide state or lifecycle_state, not both")
    if state is None and lifecycle_state is None:
        raise MessageContractValidationError("state or lifecycle_state is required")
    if not isinstance(multiple_pending, bool):
        raise MessageContractValidationError("multiple_pending must be bool")

    payload = display_payload if isinstance(display_payload, DisplayPayload) else DisplayPayload.from_mapping(display_payload)
    resolved_state = (
        _coerce_message_state(state)
        if state is not None
        else _state_from_lifecycle(lifecycle_state, evidence_status, multiple_pending=multiple_pending)
    )
    resolved_reason = _coalesce_payload_metadata(reason_code, payload.reason_code, "reason_code")
    resolved_verified = _coalesce_payload_metadata(
        execution_verified, payload.execution_verified, "execution_verified"
    )
    resolved_occurred = _coalesce_payload_metadata(occurred_at, payload.occurred_at, "occurred_at")

    return MessageContract(
        version=version,
        state=resolved_state,
        display_payload=payload,
        reply_owner=_required_string(reply_owner, "reply_owner"),
        turn_context_source=_coerce_context_source(turn_context_source),
        source_module=_required_string(source_module, "source_module"),
        turn_id=_optional_string(turn_id, "turn_id"),
        evidence_status=_optional_string(evidence_status, "evidence_status"),
        evidence_ref=_optional_string(evidence_ref, "evidence_ref"),
        reason_code=_optional_string(resolved_reason, "reason_code"),
        execution_verified=resolved_verified,
        occurred_at=_optional_string(resolved_occurred, "occurred_at"),
        interaction=(
            interaction
            if isinstance(interaction, MessageInteraction)
            else MessageInteraction.from_mapping(interaction)
        ),
    )


def format_message_contract(contract: MessageContract) -> str:
    """Pure wrapper over the existing formatter; intentionally unwired."""
    text, _meta = format_message_contract_with_meta(contract)
    return text


def format_message_contract_with_meta(contract: MessageContract) -> tuple[str, dict[str, Any]]:
    if not isinstance(contract, MessageContract):
        raise TypeError("contract must be a MessageContract")
    # Local import keeps the data contract independent from formatter internals
    # and avoids exposing a new runtime import edge until a later wiring PR.
    from core.agent_message_formatter import format_agent_message_with_meta

    text, formatter_meta = format_agent_message_with_meta(
        contract.state.value,
        {
            **contract.display_payload.to_dict(),
            "interaction": contract.interaction.to_dict() if contract.interaction else None,
        },
    )
    meta = contract.observability_record()
    meta.update({
        "formatter_state": formatter_meta["message_state"],
        "formatter_version": formatter_meta["formatter_version"],
        "fallback_used": formatter_meta["fallback_used"],
        "redaction_count": formatter_meta["redaction_count"],
    })
    return text, meta
