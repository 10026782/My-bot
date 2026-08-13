# test_marketing_fact_authority.py — BUG-164 PR1 (Authority Foundation)
# Plain script, run directly: python3 test_marketing_fact_authority.py

from marketing_fact_authority import (
    FactAuthority,
    FactUsage,
    ProtectedDemandFacts,
    SemanticType,
    extract_protected_facts,
)

_DEMAND = {
    "Domain": "general",
    "Demand Type": "recruitment",
    "Demand Title": "דרישה למתקינים - בית שמש",
    "Target Audience": "ניסיון 3+ שנים",
    "Location": "בית שמש",
    "Goal": "10 מועמדים תוך שבוע",
    "Constraints": "מיקום נגיש לנכים",
}

_AUDIENCE_SEMANTICS = {
    "recruitment": SemanticType.RECRUITMENT_ROLE_REQUIREMENTS,
    "furniture_import": SemanticType.FURNITURE_PRODUCT_CATEGORY,
    "fiber_equipment": SemanticType.FIBER_EQUIPMENT_PROJECT_CONTEXT,
    "real_estate_listing": SemanticType.LISTING_PROPERTY_DETAILS,
    "service": SemanticType.SERVICE_TYPE_CONTEXT,
}
_LOCATION_SEMANTICS = {
    "recruitment": SemanticType.RECRUITMENT_WORK_AREA,
    "furniture_import": SemanticType.FURNITURE_SALES_AREA,
    "fiber_equipment": SemanticType.FIBER_PROJECT_AREA,
    "real_estate_listing": SemanticType.LISTING_PROPERTY_LOCATION,
    "service": SemanticType.SERVICE_AREA,
}
_GOAL_SEMANTICS = {
    "recruitment": SemanticType.RECRUITMENT_GOAL,
    "furniture_import": SemanticType.SALES_GOAL,
    "fiber_equipment": SemanticType.SALES_GOAL,
    "real_estate_listing": SemanticType.LISTING_GOAL,
    "service": SemanticType.SERVICE_GOAL,
}


def test_canonical_facts_extracted_with_correct_usage_and_authority():
    pdf = extract_protected_facts("recDemo1", _DEMAND)
    for key in ("topic", "audience", "location", "goal", "constraints", "domain", "demand_type"):
        assert key in pdf.facts, f"missing fact: {key}"
        assert pdf.facts[key].authority is FactAuthority.CANONICAL

    assert pdf.facts["goal"].usage is FactUsage.RENDERABLE
    assert pdf.facts["audience"].usage is FactUsage.RENDERABLE
    assert pdf.facts["location"].usage is FactUsage.RENDERABLE
    assert pdf.facts["topic"].usage is FactUsage.ROUTING_ONLY  # internal record label, not proven copy
    assert pdf.facts["constraints"].usage is FactUsage.INSTRUCTION_ONLY
    assert pdf.facts["domain"].usage is FactUsage.ROUTING_ONLY
    assert pdf.facts["demand_type"].usage is FactUsage.ROUTING_ONLY
    print("test_canonical_facts_extracted_with_correct_usage_and_authority OK")


def test_renderable_filters_to_usage_renderable_and_confirmed_only():
    pdf = extract_protected_facts("recDemo1", _DEMAND)
    renderable = pdf.renderable()
    assert set(renderable.keys()) == {"audience", "location", "goal"}
    assert "topic" not in renderable
    print("test_renderable_filters_to_usage_renderable_and_confirmed_only OK")


def test_topic_is_routing_only_not_renderable():
    """Demand Title is a system-composed internal record label (demand-type
    label + location, per cmd_marketing.py::_materialize_demand_fields /
    the wizard's title composition) and has been observed to carry
    internal/test annotations -- it is not proven to always be publishable
    business copy, so it must never be RENDERABLE."""
    pdf = extract_protected_facts("recDemo1", _DEMAND)
    assert pdf.facts["topic"].usage is FactUsage.ROUTING_ONLY
    assert pdf.facts["topic"].semantic_type == SemanticType.TOPIC_TITLE
    print("test_topic_is_routing_only_not_renderable OK")


def test_goal_semantic_type_resolved_per_demand_type():
    for demand_type, expected in _GOAL_SEMANTICS.items():
        demand = dict(_DEMAND, **{"Demand Type": demand_type})
        pdf = extract_protected_facts("recDemo1", demand)
        assert pdf.facts["goal"].semantic_type == expected, demand_type
    print("test_goal_semantic_type_resolved_per_demand_type OK")


def test_audience_semantic_type_resolved_per_demand_type():
    for demand_type, expected in _AUDIENCE_SEMANTICS.items():
        demand = dict(_DEMAND, **{"Demand Type": demand_type})
        pdf = extract_protected_facts("recDemo1", demand)
        assert pdf.facts["audience"].semantic_type == expected, demand_type
        assert pdf.facts["audience"].usage is FactUsage.RENDERABLE, demand_type
    print("test_audience_semantic_type_resolved_per_demand_type OK")


def test_location_semantic_type_resolved_per_demand_type():
    for demand_type, expected in _LOCATION_SEMANTICS.items():
        demand = dict(_DEMAND, **{"Demand Type": demand_type})
        pdf = extract_protected_facts("recDemo1", demand)
        assert pdf.facts["location"].semantic_type == expected, demand_type
        assert pdf.facts["location"].usage is FactUsage.RENDERABLE, demand_type
    print("test_location_semantic_type_resolved_per_demand_type OK")


def test_unrecognized_demand_type_produces_no_resolved_slot_facts():
    demand = dict(_DEMAND, **{"Demand Type": "not_a_real_type"})
    pdf = extract_protected_facts("recDemo1", demand)
    # every demand-type-resolved slot fails closed, not just goal
    assert "goal" not in pdf.facts
    assert "audience" not in pdf.facts
    assert "location" not in pdf.facts
    # demand-type-invariant slots are unaffected
    assert "topic" in pdf.facts and "domain" in pdf.facts and "demand_type" in pdf.facts
    print("test_unrecognized_demand_type_produces_no_resolved_slot_facts OK")


def test_goal_value_stays_atomic_no_derived_substring_fact():
    pdf = extract_protected_facts("recDemo1", _DEMAND)
    assert pdf.facts["goal"].value == "10 מועמדים תוך שבוע"
    # PR1 ships no derivation rules -- no "goal_count" or similar sub-fact exists
    assert "goal_count" not in pdf.facts
    assert not any(k.startswith("goal_") for k in pdf.facts)
    print("test_goal_value_stays_atomic_no_derived_substring_fact OK")


def test_shared_field_extraction_matches_brief_composer():
    from marketing_brief_composer import protected_demand_fields
    raw = protected_demand_fields(_DEMAND)
    pdf = extract_protected_facts("recDemo1", _DEMAND)
    for key in raw:
        if key in pdf.facts:
            assert pdf.facts[key].value == raw[key], key
    print("test_shared_field_extraction_matches_brief_composer OK")


def test_protected_demand_facts_immutable():
    pdf = extract_protected_facts("recDemo1", _DEMAND)
    try:
        pdf.facts["injected"] = pdf.facts["goal"]
        raise AssertionError("expected TypeError on mutation")
    except TypeError:
        pass
    try:
        del pdf.facts["goal"]
        raise AssertionError("expected TypeError on deletion")
    except TypeError:
        pass
    # constructing directly with a plain dict is also locked down post-init
    manual = ProtectedDemandFacts(demand_id="x", facts=dict(pdf.facts))
    try:
        manual.facts["y"] = pdf.facts["goal"]
        raise AssertionError("expected TypeError on mutation of manually-constructed instance")
    except TypeError:
        pass
    print("test_protected_demand_facts_immutable OK")


if __name__ == "__main__":
    test_canonical_facts_extracted_with_correct_usage_and_authority()
    test_renderable_filters_to_usage_renderable_and_confirmed_only()
    test_topic_is_routing_only_not_renderable()
    test_goal_semantic_type_resolved_per_demand_type()
    test_audience_semantic_type_resolved_per_demand_type()
    test_location_semantic_type_resolved_per_demand_type()
    test_unrecognized_demand_type_produces_no_resolved_slot_facts()
    test_goal_value_stays_atomic_no_derived_substring_fact()
    test_shared_field_extraction_matches_brief_composer()
    test_protected_demand_facts_immutable()
    print("test_marketing_fact_authority.py: ALL TESTS PASSED")
