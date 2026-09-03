"""S2C deterministic completion routing contract tests."""

from airtable_schema import CommercialStatus, Currency, DealType, Direction, RelationshipType
from commercial_completion_routing import (
    CommercialCompletionRouter,
    deserialize_completion_session, serialize_completion_session,
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


def test_completion_state_round_trips_and_preserves_all_deal_fields():
    router = CommercialCompletionRouter(queue=lambda *_: None)
    first = router.start("deal", current_values=_deal())
    restored = router.restore(serialize_completion_session(first.session))
    assert restored.field_name == first.field_name
    payload = restored.session.active.complete_payload()
    assert set(payload) >= {
        "Counterparty Contact", "Deal Type Code", "Relationship Type",
        "Currency", "Commercial Status", "סכום",
    }
    # The production adapter must hand every approved persisted contract field
    # to crm_create_deal, with links represented as primitive IDs.
    assert set(router._inspect(restored.session).tool_inputs) >= {
        "counterparty_contact_id", "deal_type_code", "relationship_type",
        "currency", "commercial_status", "amount",
    }


def test_app_resumes_persisted_state_through_answer_without_agent_fallback():
    import ast
    from pathlib import Path
    app = Path(__file__).parents[1] / "app.py"
    source = app.read_text(encoding="utf-8")
    tree = ast.parse(source)
    run_agent = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "run_agent")
    assert "commercial_completion" in source
    assert any(isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "answer" for n in ast.walk(run_agent))
    assert "_completion_router.answer" in source


def test_direct_and_lead_deal_paths_use_the_same_completion_entity():
    from pathlib import Path
    source = (Path(__file__).parents[1] / "app.py").read_text(encoding="utf-8")
    assert '"create_deal": "deal"' in source
    assert 'router.start(\n            "deal"' in source


def test_app_adapter_names_every_approved_deal_v2_field():
    from pathlib import Path
    source = (Path(__file__).parents[1] / "commercial_completion_routing.py").read_text(encoding="utf-8")
    for field in (
        "counterparty_contact_id", "counterparty_organization_id", "deal_type_code",
        "relationship_type", "currency", "commercial_status", "start_date",
    ):
        assert field in source
