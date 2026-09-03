"""PR-RP1 regression tests for tool registry/schema declaration invariants."""

from __future__ import annotations

import pytest

from tool_registry import (
    ToolMeta,
    ToolRegistryInvariantError,
    _REGISTRY,
    _build_registry,
    validate_tool_invariants,
)
from tools.schemas import TOOL_SCHEMAS


INTERNAL_ONLY_TOOLS = frozenset({
    "media_save_to_memory",
    "send_followup",
    "send_recovery",
    "tma_write",
    "external_execution.submit",
    "crm_find_or_create_organization",
    "crm_create_charge",
    "crm_create_charge_payment",
})


def _meta(name: str, *, model_exposed: bool = True) -> ToolMeta:
    return ToolMeta(
        name=name,
        roles_allowed={"owner"},
        model_exposed=model_exposed,
    )


def _schema(name: str) -> dict:
    return {
        "name": name,
        "description": "test schema",
        "input_schema": {"type": "object", "properties": {}},
    }


def test_current_registry_and_model_schemas_satisfy_invariants():
    validate_tool_invariants(TOOL_SCHEMAS)

    schema_names = {schema["name"] for schema in TOOL_SCHEMAS}
    assert len(schema_names) == len(TOOL_SCHEMAS)
    assert schema_names == {
        name for name, meta in _REGISTRY.items() if meta.model_exposed
    }


def test_duplicate_registry_name_fails_with_both_declaration_positions():
    with pytest.raises(ToolRegistryInvariantError) as exc_info:
        _build_registry((_meta("duplicate"), _meta("duplicate")))

    message = str(exc_info.value)
    assert "duplicate registry tool name 'duplicate'" in message
    assert "#1" in message
    assert "#2" in message


def test_duplicate_model_schema_name_fails_instead_of_last_wins():
    registry = _build_registry((_meta("duplicate"),))

    with pytest.raises(ToolRegistryInvariantError) as exc_info:
        validate_tool_invariants(
            (_schema("duplicate"), _schema("duplicate")),
            registry=registry,
        )

    message = str(exc_info.value)
    assert "duplicate model schema tool name 'duplicate'" in message
    assert "#1" in message
    assert "#2" in message


def test_model_exposed_schema_without_registry_policy_fails():
    with pytest.raises(
        ToolRegistryInvariantError,
        match="model-exposed schema 'orphan_schema' has no tool_registry policy",
    ):
        validate_tool_invariants((_schema("orphan_schema"),), registry={})


def test_model_exposed_registry_tool_without_schema_fails():
    registry = _build_registry((_meta("missing_schema"),))

    with pytest.raises(
        ToolRegistryInvariantError,
        match="model-exposed registry tools missing schemas: missing_schema",
    ):
        validate_tool_invariants((), registry=registry)


def test_internal_only_registry_tool_is_explicitly_exempt_from_schema_requirement():
    registry = _build_registry((_meta("internal_action", model_exposed=False),))
    validate_tool_invariants((), registry=registry)


def test_internal_only_registry_tool_cannot_be_model_exposed_by_schema():
    registry = _build_registry((_meta("internal_action", model_exposed=False),))

    with pytest.raises(
        ToolRegistryInvariantError,
        match="internal-only registry tool 'internal_action' must not be model-exposed",
    ):
        validate_tool_invariants((_schema("internal_action"),), registry=registry)


def test_existing_internal_action_adapters_are_explicitly_classified():
    actual_internal = {
        name for name, meta in _REGISTRY.items() if not meta.model_exposed
    }
    assert actual_internal == INTERNAL_ONLY_TOOLS

    schema_names = {schema["name"] for schema in TOOL_SCHEMAS}
    assert INTERNAL_ONLY_TOOLS.isdisjoint(schema_names)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
