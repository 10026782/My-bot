from action_validator import ActionAllowed, ActionBlocked, validate_action
from identity import Identity, Role
from tool_registry import needs_approval, is_blocked_by_emergency, enforce


def test_external_submit_is_validated_without_provider_fields():
    assert isinstance(validate_action("external_execution.submit", {}), ActionAllowed)
    assert isinstance(validate_action("external_execution.submit.unknown", {}), ActionBlocked)


def test_external_submit_keeps_registry_policy():
    assert needs_approval("external_execution.submit") is True
    assert is_blocked_by_emergency("external_execution.submit") is True
    assert enforce("external_execution.submit", Identity("u", Role.OWNER)).model_exposed is False


def test_external_submit_feature_gate_blocks_before_boundary(monkeypatch):
    import tools.dispatcher as dispatcher

    monkeypatch.setattr(dispatcher._ff, "is_enabled", lambda name: False)
    result = dispatcher.dispatch_tool(
        "external_execution.submit",
        {},
        identity=Identity("u", Role.OWNER),
        execution_context={"contract_id": "test-contract"},
    )
    assert result.error_code == "external_execution_disabled"


def test_external_submit_emergency_stop_blocks_before_boundary(monkeypatch):
    import tools.dispatcher as dispatcher

    monkeypatch.setattr(dispatcher._ff, "is_enabled", lambda name: name == "EMERGENCY_STOP_ALL")
    result = dispatcher.dispatch_tool(
        "external_execution.submit",
        {"adapter_name": "arbitrary-provider"},
        identity=Identity("u", Role.OWNER),
        execution_context={"contract_id": "test-contract"},
    )
    assert "מצב חירום" in result
