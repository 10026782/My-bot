"""EpisodicEntry — the Episodic Memory data contract (Phase 1, contract only).

Represents one event in ``interaction -> action -> tool/result -> outcome``.
Not every field is populated on every event; only ``tenant_id``,
``canonical_user_id``, ``event_type``, ``source``, and ``occurred_at`` are
required. Everything else is an optional reference into an existing source
of truth (ActionContract id, tool execution id, evidence id, ...) — this
contract does not duplicate Business Memory fields and carries no free-text
memory blob; ``payload`` is a bounded, structured JSON object only.

See docs/research/BOSS_MEMORY_RETRIEVAL_ARCHITECTURE_2026-08.md, Phase 1.
This module defines the contract only — no persistence, no wiring.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

_MAX_PAYLOAD_BYTES = 8192


class EpisodicEntryValidationError(ValueError):
    """Raised when EpisodicEntry data violates the closed contract."""


class EpisodicEventType(str, Enum):
    """A small, closed vocabulary. Extend deliberately, not per caller."""

    INTERACTION = "interaction"
    ACTION_PROPOSED = "action_proposed"
    ACTION_EXECUTED = "action_executed"
    TOOL_RESULT = "tool_result"
    OUTCOME = "outcome"
    CORRECTION = "correction"


_EVENT_TYPES = frozenset(t.value for t in EpisodicEventType)


def _required_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EpisodicEntryValidationError(f"{field_name} is required")
    return value


def _optional_string(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise EpisodicEntryValidationError(f"{field_name} must be a non-empty string or None")
    return value


def _validate_payload(payload: Mapping[str, Any] | None) -> None:
    if payload is None:
        return
    if not isinstance(payload, Mapping):
        raise EpisodicEntryValidationError("payload must be a JSON object (mapping) or None")
    try:
        encoded = json.dumps(payload)
    except (TypeError, ValueError) as exc:
        raise EpisodicEntryValidationError("payload must be JSON-serializable") from exc
    if len(encoded.encode("utf-8")) > _MAX_PAYLOAD_BYTES:
        raise EpisodicEntryValidationError(
            f"payload exceeds the {_MAX_PAYLOAD_BYTES}-byte bound"
        )


@dataclass(frozen=True)
class EpisodicEntry:
    tenant_id: str
    canonical_user_id: str
    event_type: str
    source: str
    occurred_at: float

    id: str | None = None
    session_id: str | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    domain_id: str | None = None
    action_ref: str | None = None
    outcome_ref: str | None = None
    provenance_ref: str | None = None
    payload: Mapping[str, Any] | None = None
    created_at: float | None = None

    def __post_init__(self) -> None:
        _required_string(self.tenant_id, "tenant_id")
        _required_string(self.canonical_user_id, "canonical_user_id")
        _required_string(self.source, "source")
        if self.event_type not in _EVENT_TYPES:
            raise EpisodicEntryValidationError(
                f"event_type must be one of {sorted(_EVENT_TYPES)}"
            )
        if isinstance(self.occurred_at, bool) or not isinstance(self.occurred_at, (int, float)):
            raise EpisodicEntryValidationError("occurred_at must be a unix timestamp")
        for field_name, value in (
            ("session_id", self.session_id),
            ("entity_type", self.entity_type),
            ("entity_id", self.entity_id),
            ("domain_id", self.domain_id),
            ("action_ref", self.action_ref),
            ("outcome_ref", self.outcome_ref),
            ("provenance_ref", self.provenance_ref),
        ):
            _optional_string(value, field_name)
        _validate_payload(self.payload)
