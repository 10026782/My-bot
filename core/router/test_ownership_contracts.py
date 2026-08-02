import pytest

from core.router.ownership_contracts import (
    CanonicalActionProposal,
    IntentOwnershipDecision,
    IntentOwnershipRegistry,
    ResolverResult,
)


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
