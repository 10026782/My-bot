"""C83 regression tests for registry-derived policy views."""

from __future__ import annotations

from tool_registry import (
    TOOLS_BLOCKED_BY_EMERGENCY,
    TOOLS_REQUIRING_APPROVAL,
    ToolMeta,
    _REGISTRY,
    is_blocked_by_emergency,
    needs_approval,
)


EXPECTED_APPROVAL_TOOLS = frozenset({
    "airtable_add",
    "airtable_update",
    "calendar_create_event",
    "crm_mark_payment_paid",
    "gmail_draft",
    "gmail_send_draft",
    "sheets_append",
    # PR-0C — ActionGateway adapters (former event_bus custom actions)
    "media_save_to_memory",
    "send_followup",
    "send_recovery",
    # Phase 4B-2 wiring — TMA write-through-approval adapter
    "tma_write",
    "external_execution.submit",
})


def test_approval_policy_is_derived_from_registry_without_regression():
    derived = frozenset(
        name for name, meta in _REGISTRY.items() if meta.requires_approval
    )

    assert TOOLS_REQUIRING_APPROVAL == derived == EXPECTED_APPROVAL_TOOLS
    assert all(needs_approval(name) for name in EXPECTED_APPROVAL_TOOLS)


def test_emergency_policy_is_derived_separately_from_registry():
    derived = frozenset(
        name for name, meta in _REGISTRY.items() if meta.blocked_by_emergency
    )

    assert TOOLS_BLOCKED_BY_EMERGENCY == derived == EXPECTED_APPROVAL_TOOLS
    assert all(is_blocked_by_emergency(name) for name in EXPECTED_APPROVAL_TOOLS)


def test_approval_and_emergency_flags_are_independent_dimensions():
    approval_only = ToolMeta(
        name="approval_only",
        roles_allowed={"owner"},
        requires_approval=True,
        blocked_by_emergency=False,
    )
    emergency_only = ToolMeta(
        name="emergency_only",
        roles_allowed={"owner"},
        requires_approval=False,
        blocked_by_emergency=True,
    )

    assert approval_only.requires_approval and not approval_only.blocked_by_emergency
    assert emergency_only.blocked_by_emergency and not emergency_only.requires_approval


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))
