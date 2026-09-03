"""S2C deterministic completion routing contract tests."""

from airtable_schema import CommercialStatus, Currency, DealType, Direction, RelationshipType
from commercial_completion_routing import (
    CommercialCompletionRouter,
    MUTATION_TOOLS,
    SUPPORTED_COMPLETION_ENTITIES,
)


def _deal():
    return {
        "name": "Deal", "domain": "import", "owner": "recOwner1",
        "counterparty_contact": "recContact1", "deal_type": DealType.SERVICE,
        "relationship_type": RelationshipType.ONE_OFF, "currency": Currency.ILS,
        "commercial_status": CommercialStatus.PROSPECT, "expected_value": 100,
    }


def test_supported_entities_have_one_canonical_primitive_each():
    assert SUPPORTED_COMPLETION_ENTITIES == set(MUTATION_TOOLS)
    assert set(MUTATION_TOOLS.values()) == {
        "crm_create_deal", "crm_create_payment_term",
        "crm_find_or_create_organization", "crm_create_charge",
        "crm_create_charge_payment",
    }


def test_router_clarifies_only_next_missing_field_then_queues_complete_deal():
    queued = []
    router = CommercialCompletionRouter(queue=lambda tool, payload: queued.append((tool, payload)))
    values = _deal()
    values.pop("relationship_type")
    values.pop("currency")
    values.pop("commercial_status")
    first = router.start("deal", current_values=values, source_context={})
    assert first.outcome == "CLARIFY"
    assert first.field_name == "relationship_type"  # field order is contract-owned

    session = first.session
    for field, value in (
        ("relationship_type", RelationshipType.ONE_OFF),
        ("currency", Currency.ILS),
        ("commercial_status", CommercialStatus.PROSPECT),
    ):
        result = router.answer(session, field, value)
        session = result.session
    assert result.outcome == "TOOL"
    assert result.tool_name == "crm_create_deal"
    assert queued == [("crm_create_deal", result.tool_inputs)]


def test_payment_is_charge_required_and_never_agent_fallback():
    router = CommercialCompletionRouter(queue=lambda *_: None)
    result = router.start(
        "payment",
        current_values={"amount": 10, "paid_at": "2026-09-03", "direction": Direction.RECEIVABLE, "currency": Currency.ILS},
    )
    assert result.outcome == "CLARIFY"
    assert result.field_name == "charge"


def test_allocation_and_economics_are_blocked_in_s2c():
    router = CommercialCompletionRouter(queue=lambda *_: None)
    assert router.start("allocation_rule").outcome == "BLOCK"
    assert router.start("deal_economics").outcome == "BLOCK"


def test_queue_receives_the_same_mapping_that_route_reports():
    calls = []
    router = CommercialCompletionRouter(queue=lambda tool, payload: calls.append((tool, dict(payload))))
    result = router.start("organization", current_values={"organization_name": "Acme"})
    assert result.outcome == "TOOL"
    assert calls == [(result.tool_name, dict(result.tool_inputs))]
