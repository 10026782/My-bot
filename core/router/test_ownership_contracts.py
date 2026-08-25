import pytest

from core.router.ownership_contracts import (
    ActionLifecycleResult,
    CapabilityResolutionError,
    CanonicalActionProposal,
    ExecutionClass,
    EvidenceResult,
    IntentOwnershipDecision,
    IntentOwnershipRegistry,
    ResolvedCapability,
    ResolverResult,
    lookup_resolved_capability,
    resolve_capability,
)
from core.router.route_decision import Handler
from core.turn_envelope import ExecutionKind


def test_contracts_are_frozen_and_registry_is_immutable():
    decision = IntentOwnershipDecision("update_task", "RESOLVER", "entity lookup", 1.0, True)
    registry = IntentOwnershipRegistry().with_decision(decision)

    assert registry.require("update_task") == decision
    assert registry.for_intent("missing") is None
    assert registry.decisions["update_task"].resolver_required is True

    with pytest.raises(TypeError):
        registry.decisions["create_task"] = decision


def test_action_proposal_copies_fields_and_resolver_requires_unique_reference():
    fields = {"title": "Call supplier"}
    proposal = CanonicalActionProposal(
        "create_task", "task_create", "tasks", fields, approval_required=True,
    )
    fields["title"] = "mutated"

    assert proposal.fields["title"] == "Call supplier"
    with pytest.raises(ValueError):
        ResolverResult("task", "tenant:u1", 2, stable_reference="rec1")


@pytest.mark.parametrize(
    "factory",
    [
        lambda: IntentOwnershipDecision("", "owner", "reason", 1.0),
        lambda: IntentOwnershipDecision("x", "owner", "reason", 1.1),
        lambda: CanonicalActionProposal("x", "", "tasks"),
        lambda: ResolverResult("task", "tenant:u1", -1),
    ],
)
def test_contracts_reject_invalid_required_values(factory):
    with pytest.raises(ValueError):
        factory()


def test_ws2_lifecycle_and_evidence_contracts_are_frozen_and_validated():
    lifecycle = ActionLifecycleResult(
        contract_ref="contract-123",
        lifecycle_state="pending",
        approval_state="awaiting_approval",
        execution_state="not_started",
        reply_owner="gateway",
    )
    evidence = EvidenceResult(
        result="completed",
        evidence_ref="evidence-456",
        provider_result="ok",
        verified=True,
    )

    assert lifecycle.contract_ref == "contract-123"
    assert evidence.verified is True
    assert evidence.outcome_unknown is False

    with pytest.raises(ValueError):
        ActionLifecycleResult("", "pending", "awaiting_approval", "not_started", "gateway")

    with pytest.raises(ValueError):
        EvidenceResult("", "", "", False)


def test_execution_class_is_closed_and_resolved_capability_is_immutable():
    assert {item.value for item in ExecutionClass} == {
        "DETERMINISTIC", "NARROW_MODEL", "FULL_AGENT",
    }
    capability = ResolvedCapability(
        capability_id="general.reasoning",
        capability_version="v1",
        execution_class=ExecutionClass.FULL_AGENT,
        executor_ref="agent.loop",
        validator_ref="agent.output",
        verification_ref="turn.evidence",
        approval_risk_ref="route.policy",
        fallback_ref="none",
    )
    assert lookup_resolved_capability(
        capability.capability_id, {capability.capability_id: capability}
    ) is capability
    with pytest.raises((AttributeError, TypeError)):
        capability.capability_id = "task.create"
    with pytest.raises(TypeError):
        ResolvedCapability("bad", "FULL_AGENT")


def test_resolution_uses_existing_ownership_and_fails_closed():
    ownership = IntentOwnershipDecision("create_task", "task_builder", "task intent", 1.0)
    capability = ResolvedCapability(
        "task.create", ExecutionClass.DETERMINISTIC, executor_ref="task_gateway"
    )
    candidates = {ownership.intent: (capability,)}

    assert resolve_capability(ownership, candidates) is capability
    with pytest.raises(CapabilityResolutionError):
        resolve_capability(
            IntentOwnershipDecision("missing", "task_builder", "task intent", 1.0),
            candidates,
        )


def test_resolution_rejects_ambiguous_candidates_without_fallback():
    ownership = IntentOwnershipDecision("create_task", "task_builder", "task intent", 1.0)
    candidates = {
        ownership.intent: (
            ResolvedCapability("task.create", ExecutionClass.DETERMINISTIC, executor_ref="task_gateway"),
            ResolvedCapability("general.reasoning", ExecutionClass.FULL_AGENT, executor_ref="agent.loop"),
        ),
    }

    with pytest.raises(CapabilityResolutionError):
        resolve_capability(ownership, candidates)


def test_resolved_capability_requires_executor_identity():
    with pytest.raises(ValueError):
        ResolvedCapability("task.create", ExecutionClass.DETERMINISTIC)


def test_capability_identity_is_independent_from_tool_identity():
    capability = ResolvedCapability(
        "lead.create", ExecutionClass.NARROW_MODEL, executor_ref="airtable_add"
    )
    replacement = ResolvedCapability(
        "lead.create", ExecutionClass.NARROW_MODEL, executor_ref="lead_gateway_v2"
    )
    assert capability.capability_id == replacement.capability_id
    assert capability.executor_ref != replacement.executor_ref


def test_legacy_handler_and_execution_kind_values_remain_unchanged():
    assert Handler.AGENT == "agent"
    assert Handler.TOOL == "tool"
    assert ExecutionKind.DETERMINISTIC.value == "deterministic"
    assert ExecutionKind.AGENT_INTERPRETED.value == "agent_interpreted"
