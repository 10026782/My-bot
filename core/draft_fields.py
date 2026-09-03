"""Small, state-only field editing primitives for existing draft/session dicts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

Resolver = Callable[[Any], Any]


@dataclass(frozen=True)
class FieldMetadata:
    field_key: str
    user_label: str
    prompt: str = ""
    input_type: str = "text"
    choices: tuple[str, ...] = ()
    resolver: Resolver | None = None
    editable: bool = True
    compatible_field_type: str = "text"
    clearable: bool = True

    def choice_options(self) -> tuple[dict[str, str], ...]:
        """Provider-neutral options; channel adapters decide how to render."""
        return tuple({"value": choice, "label": choice} for choice in self.choices)


class FieldOperationError(ValueError):
    pass


def _metadata(metadata: Mapping[str, FieldMetadata], key: str) -> FieldMetadata:
    try:
        field = metadata[key]
    except KeyError as exc:
        raise FieldOperationError(f"unknown field: {key}") from exc
    if field.field_key != key:
        raise FieldOperationError(f"metadata key mismatch: {key}")
    return field


def _resolve(field: FieldMetadata, value: Any) -> Any:
    try:
        resolved = field.resolver(value) if field.resolver else value
    except (TypeError, ValueError) as exc:
        raise FieldOperationError(str(exc) or f"invalid value for {field.user_label}") from exc
    if resolved is None:
        raise FieldOperationError(f"invalid value for {field.user_label}")
    if field.choices and resolved not in field.choices:
        raise FieldOperationError(f"invalid choice for {field.user_label}")
    return resolved


def _editable(field: FieldMetadata) -> None:
    if not field.editable:
        raise FieldOperationError(f"field is not editable: {field.user_label}")


def _commit(state: dict, staged: dict) -> dict:
    state.clear()
    state.update(staged)
    return state


def set_field(state: dict, field_key: str, value: Any, metadata: Mapping[str, FieldMetadata]) -> dict:
    field = _metadata(metadata, field_key)
    _editable(field)
    staged = dict(state)
    staged[field_key] = _resolve(field, value)
    return _commit(state, staged)


def clear_field(state: dict, field_key: str, metadata: Mapping[str, FieldMetadata]) -> dict:
    field = _metadata(metadata, field_key)
    _editable(field)
    if not field.clearable:
        raise FieldOperationError(f"field cannot be cleared: {field.user_label}")
    staged = dict(state)
    staged[field_key] = ""
    return _commit(state, staged)


def _scalar_transfer(source: FieldMetadata, target: FieldMetadata) -> None:
    if source.compatible_field_type != target.compatible_field_type:
        raise FieldOperationError("incompatible field types")
    if source.compatible_field_type.startswith("link"):
        raise FieldOperationError("linked fields require explicit link operations")
    _editable(source)
    _editable(target)


def move_field(state: dict, source_key: str, target_key: str, metadata: Mapping[str, FieldMetadata]) -> dict:
    source = _metadata(metadata, source_key)
    target = _metadata(metadata, target_key)
    _scalar_transfer(source, target)
    value = state.get(source_key, "")
    staged = dict(state)
    staged[target_key] = _resolve(target, value)
    staged[source_key] = ""
    return _commit(state, staged)


def swap_fields(state: dict, first_key: str, second_key: str, metadata: Mapping[str, FieldMetadata]) -> dict:
    first = _metadata(metadata, first_key)
    second = _metadata(metadata, second_key)
    _scalar_transfer(first, second)
    first_value = _resolve(second, state.get(first_key, ""))
    second_value = _resolve(first, state.get(second_key, ""))
    staged = dict(state)
    staged[first_key] = second_value
    staged[second_key] = first_value
    return _commit(state, staged)


def apply_field_operation(state: dict, operation: str, metadata: Mapping[str, FieldMetadata], **kwargs: Any) -> dict:
    operations = {"SET_FIELD": set_field, "CLEAR_FIELD": clear_field, "MOVE_FIELD": move_field, "SWAP_FIELDS": swap_fields}
    try:
        handler = operations[operation]
    except KeyError as exc:
        raise FieldOperationError(f"unsupported operation: {operation}") from exc
    return handler(state, metadata=metadata, **kwargs)
