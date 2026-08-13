# test_marketing_creative_renderer.py — BUG-164 PR1 (Authority Foundation)
# Plain script, run directly: python3 test_marketing_creative_renderer.py

from marketing_creative_renderer import (
    CreativeProposal,
    ProposalRejected,
    authority_filter_and_render,
    parse_creative_proposal,
)
from marketing_fact_authority import extract_protected_facts

_DEMAND = {
    "Domain": "general",
    "Demand Type": "recruitment",
    "Demand Title": "דרישה למתקינים - בית שמש (בדיקת M1 חיה)",
    "Target Audience": "ניסיון 3+ שנים",
    "Location": "בית שמש",
    "Goal": "10 מועמדים תוך שבוע",
    "Constraints": "מיקום נגיש לנכים",
}

_VALID_RAW = {
    "angle_id": "benefit_first", "opening_style": "statement", "cta_style": "apply_now",
    "emphasis_fact_keys": ["goal"], "fact_order": ["goal", "location", "audience"],
}


def test_valid_proposal_parses():
    p = parse_creative_proposal(_VALID_RAW)
    assert p.angle_id.value == "benefit_first"
    assert p.fact_order == ("goal", "location", "audience")
    print("test_valid_proposal_parses OK")


def test_unknown_top_level_field_is_hard_rejected():
    try:
        parse_creative_proposal({**_VALID_RAW, "framing_text": "10 משרות פתוחות"})
        raise AssertionError("expected ProposalRejected")
    except ProposalRejected as e:
        assert "unknown_fields" in str(e)
    print("test_unknown_top_level_field_is_hard_rejected OK")


def test_unknown_top_level_field_never_silently_discarded():
    # a second, independent proof that an extra field never just vanishes --
    # it must always cause a rejection, not a truncated-but-accepted proposal
    for extra_key in ("rationale", "copy", "text", "framing_text", "notes"):
        try:
            parse_creative_proposal({**_VALID_RAW, extra_key: "anything"})
            raise AssertionError(f"expected ProposalRejected for extra key {extra_key!r}")
        except ProposalRejected:
            pass
    print("test_unknown_top_level_field_never_silently_discarded OK")


def test_invalid_enum_value_rejected():
    try:
        parse_creative_proposal({**_VALID_RAW, "angle_id": "not_a_real_angle"})
        raise AssertionError("expected ProposalRejected")
    except ProposalRejected:
        pass
    print("test_invalid_enum_value_rejected OK")


def test_malformed_fact_order_type_rejected():
    try:
        parse_creative_proposal({**_VALID_RAW, "fact_order": "goal,location"})  # string, not list
        raise AssertionError("expected ProposalRejected")
    except ProposalRejected:
        pass
    print("test_malformed_fact_order_type_rejected OK")


def test_valid_pipeline_renders_ok():
    facts = extract_protected_facts("recDemo1", _DEMAND)
    proposal = parse_creative_proposal(_VALID_RAW)
    result = authority_filter_and_render(proposal, facts)
    assert result.status == "ok", result.reason
    assert "10 מועמדים תוך שבוע" in result.rendered
    print("test_valid_pipeline_renders_ok OK")


def test_constraints_cannot_appear_as_copy():
    facts = extract_protected_facts("recDemo1", _DEMAND)
    proposal = parse_creative_proposal({**_VALID_RAW, "fact_order": ["goal", "constraints"]})
    result = authority_filter_and_render(proposal, facts)
    assert result.status == "rejected"
    assert "non_renderable_usage:constraints" in result.reason
    print("test_constraints_cannot_appear_as_copy OK")


def test_domain_and_demand_type_cannot_appear_as_copy_despite_canonical():
    facts = extract_protected_facts("recDemo1", _DEMAND)
    for routing_key in ("domain", "demand_type"):
        proposal = parse_creative_proposal({**_VALID_RAW, "fact_order": ["goal", routing_key]})
        result = authority_filter_and_render(proposal, facts)
        assert result.status == "rejected", routing_key
        assert f"non_renderable_usage:{routing_key}" in result.reason, routing_key
    print("test_domain_and_demand_type_cannot_appear_as_copy_despite_canonical OK")


def test_unknown_fact_key_rejected():
    facts = extract_protected_facts("recDemo1", _DEMAND)
    proposal = parse_creative_proposal({**_VALID_RAW, "fact_order": ["goal", "not_a_real_key"]})
    result = authority_filter_and_render(proposal, facts)
    assert result.status == "rejected"
    assert "unknown_fact_key:not_a_real_key" in result.reason
    print("test_unknown_fact_key_rejected OK")


def test_unregistered_combination_fails_closed():
    facts = extract_protected_facts("recDemo1", _DEMAND)
    # schedule_visit is a real_estate_listing cta_style, not valid for recruitment
    proposal = parse_creative_proposal({**_VALID_RAW, "cta_style": "schedule_visit"})
    result = authority_filter_and_render(proposal, facts)
    assert result.status == "rejected"
    assert result.reason == "unknown_template_combination"
    print("test_unregistered_combination_fails_closed OK")


def test_empty_fact_order_fails_closed():
    facts = extract_protected_facts("recDemo1", _DEMAND)
    proposal = parse_creative_proposal({**_VALID_RAW, "fact_order": []})
    result = authority_filter_and_render(proposal, facts)
    assert result.status == "rejected" and result.reason == "empty_fact_order"
    print("test_empty_fact_order_fails_closed OK")


def test_bug164_regression_goal_cannot_become_another_business_concept():
    """
    The original BUG-164 production failure: AI rewrote
    Goal="10 מועמדים תוך שבוע" into idea text containing "10 משרות פתוחות".
    Proves: across every valid (angle_id, opening_style, cta_style) combo
    registered for recruitment, the rendered text always contains the full,
    untouched goal phrase and never contains the fabricated "משרות" wording.
    """
    from marketing_creative_templates import allowed_combinations

    facts = extract_protected_facts("recDemo1", _DEMAND)
    for angle, opening, cta in allowed_combinations("recruitment"):
        proposal = CreativeProposal(
            angle_id=angle, opening_style=opening, cta_style=cta,
            fact_order=("goal", "location", "audience"),
        )
        result = authority_filter_and_render(proposal, facts)
        assert result.status == "ok", (angle, opening, cta, result.reason)
        assert "10 מועמדים תוך שבוע" in result.rendered, result.rendered
        assert "משרות" not in result.rendered, result.rendered
    print("test_bug164_regression_goal_cannot_become_another_business_concept OK")


if __name__ == "__main__":
    test_valid_proposal_parses()
    test_unknown_top_level_field_is_hard_rejected()
    test_unknown_top_level_field_never_silently_discarded()
    test_invalid_enum_value_rejected()
    test_malformed_fact_order_type_rejected()
    test_valid_pipeline_renders_ok()
    test_constraints_cannot_appear_as_copy()
    test_domain_and_demand_type_cannot_appear_as_copy_despite_canonical()
    test_unknown_fact_key_rejected()
    test_unregistered_combination_fails_closed()
    test_empty_fact_order_fails_closed()
    test_bug164_regression_goal_cannot_become_another_business_concept()
    print("test_marketing_creative_renderer.py: ALL TESTS PASSED")
