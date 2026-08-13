# test_marketing_creative_renderer.py — BUG-164 PR1 (Authority Foundation)
# Plain script, run directly: python3 test_marketing_creative_renderer.py

from dataclasses import replace

from marketing_creative_renderer import (
    _MAX_FACT_ORDER_LEN,
    CreativeProposal,
    ProposalRejected,
    authority_filter_and_render,
    parse_creative_proposal,
)
from marketing_fact_authority import (
    FactAuthority,
    FactUsage,
    ProtectedDemandFacts,
    extract_protected_facts,
)

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
    "fact_order": ["goal", "location", "audience"],
}


def _without(facts: ProtectedDemandFacts, key: str) -> ProtectedDemandFacts:
    return ProtectedDemandFacts(demand_id=facts.demand_id, facts={k: v for k, v in facts.facts.items() if k != key})


def _with_replaced(facts: ProtectedDemandFacts, key: str, **changes) -> ProtectedDemandFacts:
    return ProtectedDemandFacts(demand_id=facts.demand_id, facts={**facts.facts, key: replace(facts.facts[key], **changes)})


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
    # it must always cause a rejection, not a truncated-but-accepted proposal.
    # emphasis_fact_keys is included here: it was removed from the live
    # schema (FINAL CORRECTION PASS -- it had no deterministic rendering
    # effect), so it must now be rejected exactly like any other unknown key.
    for extra_key in ("rationale", "copy", "text", "framing_text", "notes", "emphasis_fact_keys"):
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
    assert "disallowed_fact" in result.reason and "constraints" in result.reason
    print("test_constraints_cannot_appear_as_copy OK")


def test_domain_topic_and_demand_type_cannot_appear_as_copy_despite_canonical():
    facts = extract_protected_facts("recDemo1", _DEMAND)
    for routing_key in ("domain", "demand_type", "topic"):
        proposal = parse_creative_proposal({**_VALID_RAW, "fact_order": ["goal", routing_key]})
        result = authority_filter_and_render(proposal, facts)
        assert result.status == "rejected", routing_key
        assert "disallowed_fact" in result.reason and routing_key in result.reason, routing_key
    print("test_domain_topic_and_demand_type_cannot_appear_as_copy_despite_canonical OK")


def test_unknown_fact_key_rejected_when_structurally_allowed_but_missing():
    # "audience" IS an allowed key for this template, but was never
    # extracted for this Demand (simulating an empty field) -- must fail as
    # unknown_fact_key, distinct from disallowed_fact.
    facts = _without(extract_protected_facts("recDemo1", _DEMAND), "audience")
    proposal = parse_creative_proposal({**_VALID_RAW, "fact_order": ["goal", "audience"]})
    result = authority_filter_and_render(proposal, facts)
    assert result.status == "rejected"
    assert result.reason == "unknown_fact_key:audience"
    print("test_unknown_fact_key_rejected_when_structurally_allowed_but_missing OK")


def test_disallowed_fact_key_rejected_for_arbitrary_name():
    facts = extract_protected_facts("recDemo1", _DEMAND)
    proposal = parse_creative_proposal({**_VALID_RAW, "fact_order": ["goal", "not_a_real_key"]})
    result = authority_filter_and_render(proposal, facts)
    assert result.status == "rejected"
    assert "disallowed_fact" in result.reason and "not_a_real_key" in result.reason
    print("test_disallowed_fact_key_rejected_for_arbitrary_name OK")


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


def test_duplicate_fact_order_rejected():
    facts = extract_protected_facts("recDemo1", _DEMAND)
    proposal = parse_creative_proposal({**_VALID_RAW, "fact_order": ["goal", "goal", "location"]})
    result = authority_filter_and_render(proposal, facts)
    assert result.status == "rejected" and result.reason == "duplicate_fact_order"
    print("test_duplicate_fact_order_rejected OK")


def test_oversized_fact_order_rejected():
    facts = extract_protected_facts("recDemo1", _DEMAND)
    proposal = parse_creative_proposal({**_VALID_RAW, "fact_order": [f"k{i}" for i in range(_MAX_FACT_ORDER_LEN + 1)]})
    result = authority_filter_and_render(proposal, facts)
    assert result.status == "rejected" and result.reason == "oversized_fact_order"
    print("test_oversized_fact_order_rejected OK")


def test_missing_required_fact_rejected():
    facts = extract_protected_facts("recDemo1", _DEMAND)
    proposal = parse_creative_proposal({**_VALID_RAW, "fact_order": ["location", "audience"]})  # no "goal"
    result = authority_filter_and_render(proposal, facts)
    assert result.status == "rejected"
    assert "missing_required_fact" in result.reason and "goal" in result.reason
    print("test_missing_required_fact_rejected OK")


def test_non_canonical_authority_rejected():
    # allowed key, RENDERABLE usage, confirmed -- but authority isn't
    # CANONICAL. DETERMINISTIC/CANDIDATE are not renderable in this live
    # design yet, regardless of usage/confirmed state.
    facts = _with_replaced(extract_protected_facts("recDemo1", _DEMAND), "goal", authority=FactAuthority.DETERMINISTIC)
    proposal = parse_creative_proposal(_VALID_RAW)
    result = authority_filter_and_render(proposal, facts)
    assert result.status == "rejected"
    assert result.reason == "non_canonical_authority:goal:deterministic"
    print("test_non_canonical_authority_rejected OK")


def test_candidate_authority_rejected():
    facts = _with_replaced(extract_protected_facts("recDemo1", _DEMAND), "goal", authority=FactAuthority.CANDIDATE)
    proposal = parse_creative_proposal(_VALID_RAW)
    result = authority_filter_and_render(proposal, facts)
    assert result.status == "rejected"
    assert result.reason == "non_canonical_authority:goal:candidate"
    print("test_candidate_authority_rejected OK")


def test_unconfirmed_fact_rejected():
    facts = _with_replaced(extract_protected_facts("recDemo1", _DEMAND), "goal", confirmed=False)
    proposal = parse_creative_proposal(_VALID_RAW)
    result = authority_filter_and_render(proposal, facts)
    assert result.status == "rejected"
    assert result.reason == "unconfirmed_fact:goal"
    print("test_unconfirmed_fact_rejected OK")


def test_instruction_only_usage_rejected_at_render_authority_gate():
    # a key that IS in the template's allowed set (location) but whose usage
    # was (hypothetically) INSTRUCTION_ONLY rather than RENDERABLE -- proves
    # the usage gate itself, independent of the disallowed_fact structural
    # gate that catches constraints/domain/topic before this point.
    facts = _with_replaced(extract_protected_facts("recDemo1", _DEMAND), "location", usage=FactUsage.INSTRUCTION_ONLY)
    proposal = parse_creative_proposal(_VALID_RAW)
    result = authority_filter_and_render(proposal, facts)
    assert result.status == "rejected"
    assert result.reason == "non_renderable_usage:location:instruction_only"
    print("test_instruction_only_usage_rejected_at_render_authority_gate OK")


def test_routing_only_usage_rejected_at_render_authority_gate():
    facts = _with_replaced(extract_protected_facts("recDemo1", _DEMAND), "location", usage=FactUsage.ROUTING_ONLY)
    proposal = parse_creative_proposal(_VALID_RAW)
    result = authority_filter_and_render(proposal, facts)
    assert result.status == "rejected"
    assert result.reason == "non_renderable_usage:location:routing_only"
    print("test_routing_only_usage_rejected_at_render_authority_gate OK")


def test_semantic_mismatch_rejected_despite_matching_key_name():
    # A matching key NAME is not enough: "audience" carrying location's
    # semantic_type (wrong predicate, same key name) must fail closed.
    facts = extract_protected_facts("recDemo1", _DEMAND)
    mismatched = _with_replaced(facts, "audience", semantic_type=facts.facts["location"].semantic_type)
    proposal = parse_creative_proposal({**_VALID_RAW, "fact_order": ["goal", "audience"]})
    result = authority_filter_and_render(proposal, mismatched)
    assert result.status == "rejected"
    assert result.reason.startswith("semantic_mismatch:audience:")
    print("test_semantic_mismatch_rejected_despite_matching_key_name OK")


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
    test_domain_topic_and_demand_type_cannot_appear_as_copy_despite_canonical()
    test_unknown_fact_key_rejected_when_structurally_allowed_but_missing()
    test_disallowed_fact_key_rejected_for_arbitrary_name()
    test_unregistered_combination_fails_closed()
    test_empty_fact_order_fails_closed()
    test_duplicate_fact_order_rejected()
    test_oversized_fact_order_rejected()
    test_missing_required_fact_rejected()
    test_non_canonical_authority_rejected()
    test_candidate_authority_rejected()
    test_unconfirmed_fact_rejected()
    test_instruction_only_usage_rejected_at_render_authority_gate()
    test_routing_only_usage_rejected_at_render_authority_gate()
    test_semantic_mismatch_rejected_despite_matching_key_name()
    test_bug164_regression_goal_cannot_become_another_business_concept()
    print("test_marketing_creative_renderer.py: ALL TESTS PASSED")
