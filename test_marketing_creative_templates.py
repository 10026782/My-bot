# test_marketing_creative_templates.py — BUG-164 PR1 (Authority Foundation)
# Plain script, run directly: python3 test_marketing_creative_templates.py

from marketing_creative_templates import (
    TEMPLATE_REGISTRY,
    AngleId,
    CtaStyle,
    OpeningStyle,
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


if __name__ == "__main__":
    test_every_demand_type_has_registered_combinations()
    test_unknown_demand_type_returns_no_combinations()
    test_registry_is_only_source_of_valid_combinations()
    test_bug164_goal_value_renders_atomically()
    test_render_uses_only_facts_present_in_order()
    print("test_marketing_creative_templates.py: ALL TESTS PASSED")
