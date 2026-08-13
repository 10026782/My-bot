# test_marketing_creative_templates.py — BUG-164 PR1 (Authority Foundation)
# Plain script, run directly: python3 test_marketing_creative_templates.py

from marketing_creative_templates import (
    TEMPLATE_REGISTRY,
    AngleId,
    ClaimType,
    CtaStyle,
    OpeningStyle,
    _ANGLE_LEAD_IN,
    _ANGLE_LEAD_IN_CLAIM_TYPE,
    _CTA_TEXT,
    _CTA_TEXT_CLAIM_TYPE,
    allowed_combinations,
)
from marketing_fact_authority import FactAuthority, FactUsage, ProtectedFact, SemanticType

_ALL_DEMAND_TYPES = ("recruitment", "furniture_import", "fiber_equipment", "real_estate_listing", "service")


def test_every_demand_type_has_registered_combinations():
    for dt in _ALL_DEMAND_TYPES:
        combos = allowed_combinations(dt)
        assert combos, f"{dt} has no supported combinations"
        for combo in combos:
            assert (dt, *combo) in TEMPLATE_REGISTRY
    print("test_every_demand_type_has_registered_combinations OK")


def test_unknown_demand_type_returns_no_combinations():
    assert allowed_combinations("not_a_real_type") == ()
    print("test_unknown_demand_type_returns_no_combinations OK")


def test_registry_is_only_source_of_valid_combinations():
    # every registry key's demand_type must be one this module actually
    # supports -- proves there's no second, out-of-band list of combos
    for (demand_type, angle, opening, cta), template in TEMPLATE_REGISTRY.items():
        assert demand_type in _ALL_DEMAND_TYPES
        assert (angle, opening, cta) in allowed_combinations(demand_type)
        assert template.demand_type == demand_type
        assert template.angle_id == angle
    print("test_registry_is_only_source_of_valid_combinations OK")


def test_every_template_declares_semantic_contract():
    # Template Semantic Contract (FINAL CORRECTION PASS): every registered
    # Template must declare required/allowed fact keys and an expected
    # semantic_type for every allowed key. "goal" is always required; topic
    # is never allowed (ROUTING_ONLY, not proven-publishable copy).
    for key, template in TEMPLATE_REGISTRY.items():
        assert "goal" in template.required_fact_keys, key
        assert template.required_fact_keys <= template.allowed_fact_keys, key
        assert "topic" not in template.allowed_fact_keys, key
        assert set(template.fact_semantic_types) == template.allowed_fact_keys, key
    print("test_every_template_declares_semantic_contract OK")


def test_semantic_contract_matches_fact_authority_resolution():
    # cross-check: the semantic_type each Template expects for goal/location/
    # audience matches what marketing_fact_authority.extract_protected_facts
    # actually resolves for that demand_type -- the two files must agree.
    from marketing_fact_authority import extract_protected_facts

    demand = {
        "Domain": "general", "Target Audience": "x", "Location": "y", "Goal": "z",
    }
    for dt in _ALL_DEMAND_TYPES:
        pdf = extract_protected_facts("recDemo", dict(demand, **{"Demand Type": dt, "Demand Title": "t"}))
        for combo in allowed_combinations(dt):
            template = TEMPLATE_REGISTRY[(dt, *combo)]
            for key in ("goal", "location", "audience"):
                assert template.fact_semantic_types[key] == pdf.facts[key].semantic_type, (dt, key)
    print("test_semantic_contract_matches_fact_authority_resolution OK")


def test_bug164_goal_value_renders_atomically():
    goal_fact = ProtectedFact(
        key="goal", value="10 מועמדים תוך שבוע", source="Demand.goal",
        semantic_type=SemanticType.RECRUITMENT_GOAL, authority=FactAuthority.CANONICAL,
        usage=FactUsage.RENDERABLE,
    )
    template = TEMPLATE_REGISTRY[("recruitment", AngleId.BENEFIT_FIRST, OpeningStyle.STATEMENT, CtaStyle.APPLY_NOW)]
    rendered = template.render({"goal": goal_fact}, ("goal",))
    assert "10 מועמדים תוך שבוע" in rendered, rendered
    assert "משרות" not in rendered, rendered
    print("test_bug164_goal_value_renders_atomically OK")


def test_render_uses_only_facts_present_in_order():
    goal_fact = ProtectedFact(
        key="goal", value="G", source="s", semantic_type=SemanticType.SALES_GOAL,
        authority=FactAuthority.CANONICAL, usage=FactUsage.RENDERABLE,
    )
    template = TEMPLATE_REGISTRY[("furniture_import", AngleId.BENEFIT_FIRST, OpeningStyle.STATEMENT, CtaStyle.CONTACT_NOW)]
    rendered = template.render({"goal": goal_fact}, ("goal",))
    assert "G" in rendered
    print("test_render_uses_only_facts_present_in_order OK")


def test_all_static_fragments_classified_creative_device():
    """Marketing Claim Policy: no BOUNDED_CLAIM/BUSINESS_FACT static template
    text may ship without a validity-window/canonical-authority governance
    layer, which doesn't exist yet (future Marketing Claim Registry)."""
    assert set(_ANGLE_LEAD_IN_CLAIM_TYPE) == set(_ANGLE_LEAD_IN)
    assert set(_CTA_TEXT_CLAIM_TYPE) == set(_CTA_TEXT)
    assert all(v is ClaimType.CREATIVE_DEVICE for v in _ANGLE_LEAD_IN_CLAIM_TYPE.values())
    assert all(v is ClaimType.CREATIVE_DEVICE for v in _CTA_TEXT_CLAIM_TYPE.values())
    print("test_all_static_fragments_classified_creative_device OK")


def test_static_fragments_contain_no_bounded_time_or_quantity_claim():
    for text in (*_ANGLE_LEAD_IN.values(), *_CTA_TEXT.values()):
        assert "השבוע" not in text, text  # e.g. "רק השבוע" -- BOUNDED_CLAIM example
        assert not any(digit in text for digit in "0123456789"), text
    print("test_static_fragments_contain_no_bounded_time_or_quantity_claim OK")


def test_urgency_and_social_proof_lead_ins_make_no_concrete_claim():
    # Regression for the Marketing Claim Policy correction: URGENCY/SOCIAL_PROOF
    # previously used "רק השבוע!" (BOUNDED_CLAIM) and "כבר עשרות לקוחות בחרו בנו"
    # (BUSINESS_FACT: customer count) with no governance backing either.
    urgency_text = _ANGLE_LEAD_IN[AngleId.URGENCY]
    social_proof_text = _ANGLE_LEAD_IN[AngleId.SOCIAL_PROOF]
    assert "רק השבוע" not in urgency_text
    assert "עשרות" not in social_proof_text and "לקוחות בחרו" not in social_proof_text
    print("test_urgency_and_social_proof_lead_ins_make_no_concrete_claim OK")


if __name__ == "__main__":
    test_every_demand_type_has_registered_combinations()
    test_unknown_demand_type_returns_no_combinations()
    test_registry_is_only_source_of_valid_combinations()
    test_every_template_declares_semantic_contract()
    test_semantic_contract_matches_fact_authority_resolution()
    test_bug164_goal_value_renders_atomically()
    test_render_uses_only_facts_present_in_order()
    test_all_static_fragments_classified_creative_device()
    test_static_fragments_contain_no_bounded_time_or_quantity_claim()
    test_urgency_and_social_proof_lead_ins_make_no_concrete_claim()
    print("test_marketing_creative_templates.py: ALL TESTS PASSED")
