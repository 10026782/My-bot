# test_marketing_fact_authority.py — BUG-164 PR1 (Authority Foundation)
# Plain script, run directly: python3 test_marketing_fact_authority.py

from marketing_fact_authority import (
    FactAuthority,
    FactUsage,
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


def test_canonical_facts_extracted_with_correct_usage_and_authority():
    pdf = extract_protected_facts("recDemo1", _DEMAND)
    for key in ("topic", "audience", "location", "goal", "constraints", "domain", "demand_type"):
        assert key in pdf.facts, f"missing fact: {key}"
        assert pdf.facts[key].authority is FactAuthority.CANONICAL

    assert pdf.facts["goal"].usage is FactUsage.RENDERABLE
    assert pdf.facts["audience"].usage is FactUsage.RENDERABLE
    assert pdf.facts["location"].usage is FactUsage.RENDERABLE
    assert pdf.facts["topic"].usage is FactUsage.RENDERABLE
    assert pdf.facts["constraints"].usage is FactUsage.INSTRUCTION_ONLY
    assert pdf.facts["domain"].usage is FactUsage.ROUTING_ONLY
    assert pdf.facts["demand_type"].usage is FactUsage.ROUTING_ONLY
    print("test_canonical_facts_extracted_with_correct_usage_and_authority OK")


def test_renderable_filters_to_usage_renderable_and_confirmed_only():
    pdf = extract_protected_facts("recDemo1", _DEMAND)
    renderable = pdf.renderable()
    assert set(renderable.keys()) == {"topic", "audience", "location", "goal"}
    print("test_renderable_filters_to_usage_renderable_and_confirmed_only OK")


def test_goal_semantic_type_resolved_per_demand_type():
    cases = {
        "recruitment": SemanticType.RECRUITMENT_GOAL,
        "furniture_import": SemanticType.SALES_GOAL,
        "fiber_equipment": SemanticType.SALES_GOAL,
        "real_estate_listing": SemanticType.LISTING_GOAL,
        "service": SemanticType.SERVICE_GOAL,
    }
    for demand_type, expected in cases.items():
        demand = dict(_DEMAND, **{"Demand Type": demand_type})
        pdf = extract_protected_facts("recDemo1", demand)
        assert pdf.facts["goal"].semantic_type == expected, demand_type
    print("test_goal_semantic_type_resolved_per_demand_type OK")


def test_unrecognized_demand_type_produces_no_goal_fact():
    demand = dict(_DEMAND, **{"Demand Type": "not_a_real_type"})
    pdf = extract_protected_facts("recDemo1", demand)
    assert "goal" not in pdf.facts
    # the other, demand-type-invariant slots are unaffected
    assert "location" in pdf.facts and "audience" in pdf.facts
    print("test_unrecognized_demand_type_produces_no_goal_fact OK")


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


if __name__ == "__main__":
    test_canonical_facts_extracted_with_correct_usage_and_authority()
    test_renderable_filters_to_usage_renderable_and_confirmed_only()
    test_goal_semantic_type_resolved_per_demand_type()
    test_unrecognized_demand_type_produces_no_goal_fact()
    test_goal_value_stays_atomic_no_derived_substring_fact()
    test_shared_field_extraction_matches_brief_composer()
    print("test_marketing_fact_authority.py: ALL TESTS PASSED")
