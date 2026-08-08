import inspect

import pytest

from airtable_schema import LeadFields
from core.router.lead_builders import CapturePolicy, LeadIdentityPrecondition
from core.router.lead_integration import prepare_lead_proposal
from core.router.ownership_contracts import IntentOwnershipDecision, IntentOwnershipRegistry
from core.router.route_decision import Intent

_VALID_IDENTITY = LeadIdentityPrecondition(valid=True, is_duplicate=False)


def _registry():
    return IntentOwnershipRegistry({
        Intent.CREATE_LEAD: IntentOwnershipDecision(
            Intent.CREATE_LEAD, "LEAD_BUILDER", "structured create", 1.0,
        ),
        Intent.UPDATE_LEAD: IntentOwnershipDecision(
            Intent.UPDATE_LEAD, "RESOLVER", "entity update", 1.0, True,
        ),
    })


def test_integration_builds_create_without_lookup():
    proposal = prepare_lead_proposal(
        Intent.CREATE_LEAD, _registry(), scope="tenant:u1", name="Dana Cohen",
        capture_policy=CapturePolicy.AUTO_WRITE, identity_precondition=_VALID_IDENTITY,
    )
    assert proposal.intent == Intent.CREATE_LEAD
    assert proposal.fields[LeadFields.NAME] == "Dana Cohen"


def test_integration_create_requires_capture_policy():
    with pytest.raises(ValueError):
        prepare_lead_proposal(
            Intent.CREATE_LEAD, _registry(), scope="tenant:u1", name="Dana Cohen",
            identity_precondition=_VALID_IDENTITY,
        )


def test_integration_create_requires_identity_precondition():
    with pytest.raises(ValueError):
        prepare_lead_proposal(
            Intent.CREATE_LEAD, _registry(), scope="tenant:u1", name="Dana Cohen",
            capture_policy=CapturePolicy.AUTO_WRITE,
        )


def test_integration_create_missing_scope_fails_closed():
    with pytest.raises(ValueError):
        prepare_lead_proposal(
            Intent.CREATE_LEAD, _registry(), scope="", name="Dana Cohen",
            capture_policy=CapturePolicy.AUTO_WRITE, identity_precondition=_VALID_IDENTITY,
        )


def test_integration_create_invalid_identity_fails_closed():
    invalid = LeadIdentityPrecondition(valid=False, is_duplicate=False)
    with pytest.raises(ValueError):
        prepare_lead_proposal(
            Intent.CREATE_LEAD, _registry(), scope="tenant:u1", name="Dana Cohen",
            capture_policy=CapturePolicy.AUTO_WRITE, identity_precondition=invalid,
        )


def test_integration_create_duplicate_identity_fails_closed():
    duplicate = LeadIdentityPrecondition(valid=True, is_duplicate=True)
    with pytest.raises(ValueError):
        prepare_lead_proposal(
            Intent.CREATE_LEAD, _registry(), scope="tenant:u1", name="Dana Cohen",
            capture_policy=CapturePolicy.AUTO_WRITE, identity_precondition=duplicate,
        )


def test_integration_resolves_then_builds_update():
    proposal = prepare_lead_proposal(
        Intent.UPDATE_LEAD, _registry(), scope="tenant:u1", query="Dana Cohen",
        fields={LeadFields.STATUS: "active"},
        lookup=lambda query, scope, limit: [{"id": "rec1"}],
    )
    assert proposal.intent == Intent.UPDATE_LEAD
    assert proposal.fields["record_id"] == "rec1"


def test_integration_returns_resolver_result_for_ambiguous_update():
    result = prepare_lead_proposal(
        Intent.UPDATE_LEAD, _registry(), scope="tenant:u1", query="Cohen",
        lookup=lambda query, scope, limit: [{"id": "rec1"}, {"id": "rec2"}],
    )
    assert result.match_count == 2
    assert result.stable_reference == ""


def test_integration_returns_resolver_result_for_zero_matches():
    result = prepare_lead_proposal(
        Intent.UPDATE_LEAD, _registry(), scope="tenant:u1", query="nobody",
        lookup=lambda query, scope, limit: [],
    )
    assert result.match_count == 0
    assert result.stable_reference == ""


def test_integration_update_requires_lookup():
    with pytest.raises(ValueError):
        prepare_lead_proposal(
            Intent.UPDATE_LEAD, _registry(), scope="tenant:u1", query="Dana Cohen",
        )


def test_integration_rejects_registry_policy_mismatch():
    registry = IntentOwnershipRegistry({
        Intent.CREATE_LEAD: IntentOwnershipDecision(
            Intent.CREATE_LEAD, "LEAD_BUILDER", "bad resolver policy", 1.0, True,
        ),
    })
    try:
        prepare_lead_proposal(Intent.CREATE_LEAD, registry, scope="tenant:u1", name="x")
    except ValueError as error:
        assert "resolver policy mismatch" in str(error)
    else:
        raise AssertionError("policy mismatch was accepted")


def test_integration_rejects_unsupported_intent():
    registry = IntentOwnershipRegistry({
        Intent.FIND_LEAD: IntentOwnershipDecision(
            Intent.FIND_LEAD, "RESOLVER", "read-only search", 1.0, False,
        ),
    })
    try:
        prepare_lead_proposal(Intent.FIND_LEAD, registry, scope="tenant:u1", query="Cohen")
    except ValueError as error:
        assert "unsupported lead integration intent" in str(error)
    else:
        raise AssertionError("unsupported intent was accepted")


def test_lead_integration_never_calls_agent():
    """The integration seam only selects/resolves/builds -- no Agent/LLM call."""
    import core.router.lead_integration as module

    source = inspect.getsource(module)
    for banned in ("agent", "anthropic", "claude", "llm"):
        assert banned not in source.lower()
