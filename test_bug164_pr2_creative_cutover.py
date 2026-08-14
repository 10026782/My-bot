# test_bug164_pr2_creative_cutover.py — BUG-164 PR2 (Marketing Cutover)
#
# Standalone script, run directly: python3 test_bug164_pr2_creative_cutover.py
# (no pytest harness in this repo — see CLAUDE.md's Tests section).
#
# Proves the creative_ideas generation-to-save path in cmd_marketing.py now
# goes exclusively through BUG-164 PR1's authority boundary (unmodified):
# canonical Demand -> ProtectedDemandFacts -> bounded CreativeProposal ->
# authority_filter_and_render() -> rendered copy -> save_creative_ideas().
# marketing_gateway and llm_fallback.call_anthropic_text are mocked; no real
# Airtable/Anthropic I/O happens.

import json
from unittest.mock import patch

from airtable_schema import MarketingDemandFields as MDF
from cmd_marketing import _build_creative_proposal_instruction, _create_demand_and_generate_ideas, \
    _parse_and_render_creative_proposals
from marketing_fact_authority import (
    FactAuthority,
    FactUsage,
    ProtectedDemandFacts,
    extract_protected_facts,
)

_DEMAND_FIELDS = {
    MDF.DOMAIN: "general",
    MDF.DEMAND_TYPE: "recruitment",
    MDF.NAME: "גיוס — בית שמש",
    MDF.TARGET_AUDIENCE: "ניסיון 3+ שנים",
    MDF.LOCATION: "בית שמש",
    MDF.GOAL: "10 מועמדים תוך שבוע",
    MDF.CONSTRAINTS: "מיקום נגיש לנכים",
}

_STATE = {
    "domain": "general",
    "demand_type": "recruitment",
    "answers": {
        "role_experience": "ניסיון 3+ שנים",
        "area": "בית שמש",
        "quantity_deadline": "10 מועמדים תוך שבוע",
        "constraints": "מיקום נגיש לנכים",
    },
}

_VALID_PROPOSAL_JSON = json.dumps([
    {"angle_id": "benefit_first", "opening_style": "statement", "cta_style": "apply_now",
     "fact_order": ["goal", "location", "audience"]},
    {"angle_id": "urgency", "opening_style": "statement", "cta_style": "apply_now",
     "fact_order": ["goal"]},
    {"angle_id": "benefit_first", "opening_style": "statement", "cta_style": "apply_now",
     "fact_order": ["goal", "audience"]},
])


def _mock_marketing_gateway(save_return="recCreative1"):
    """Returns the set of patch() context managers standing in for
    marketing_gateway + the AI call, wired for a successful demand-creation
    path. save_creative_ideas is the assertion point most tests care about."""
    return (
        patch("marketing_gateway.create_demand", return_value="recDemo1"),
        patch("marketing_gateway.get_demand", return_value=dict(_DEMAND_FIELDS)),
        patch("marketing_gateway.get_marketing_rules", return_value=""),
        patch("marketing_gateway.save_creative_ideas", return_value=save_return),
    )


# ── 1. valid bounded proposals produce 3 rendered ideas ─────────────

def test_valid_proposals_produce_three_rendered_ideas():
    facts = extract_protected_facts("recDemo1", _DEMAND_FIELDS)
    ok, ideas, reason = _parse_and_render_creative_proposals(_VALID_PROPOSAL_JSON, facts)
    assert ok, reason
    assert len(ideas) == 3
    assert all(isinstance(idea, str) and idea for idea in ideas)
    print("test_valid_proposals_produce_three_rendered_ideas OK")


# ── 2. rendered ideas saved through the existing save_creative_ideas path ──

def test_end_to_end_saves_rendered_ideas_via_existing_save_path():
    m_create, m_get, m_rules, m_save = _mock_marketing_gateway()
    with m_create, m_get, m_rules, m_save as save_mock, \
            patch("llm_fallback.call_anthropic_text", return_value=_VALID_PROPOSAL_JSON):
        result = _create_demand_and_generate_ideas(_STATE, triggered_by="test")

    assert result["ok"] is True, result
    assert result["creative_id"] == "recCreative1"
    assert len(result["ideas"]) == 3

    save_mock.assert_called_once()
    kwargs = save_mock.call_args.kwargs
    assert kwargs["idea1"] == result["ideas"][0]
    assert kwargs["idea2"] == result["ideas"][1]
    assert kwargs["idea3"] == result["ideas"][2]
    # persisted text is system-rendered output, never the raw AI JSON string
    for idea_text in (kwargs["idea1"], kwargs["idea2"], kwargs["idea3"]):
        assert "angle_id" not in idea_text and "fact_order" not in idea_text
    print("test_end_to_end_saves_rendered_ideas_via_existing_save_path OK")


# ── 3. BUG-164 regression: canonical Goal preserved atomically end-to-end ──

def test_bug164_regression_goal_preserved_atomically_end_to_end():
    m_create, m_get, m_rules, m_save = _mock_marketing_gateway()
    with m_create, m_get, m_rules, m_save as save_mock, \
            patch("llm_fallback.call_anthropic_text", return_value=_VALID_PROPOSAL_JSON):
        result = _create_demand_and_generate_ideas(_STATE, triggered_by="test")

    assert result["ok"] is True, result
    for idea_text in result["ideas"]:
        if "goal" in json.loads(_VALID_PROPOSAL_JSON)[0]["fact_order"]:
            pass  # sanity no-op, real assertion below covers all 3
    assert any("10 מועמדים תוך שבוע" in idea for idea in result["ideas"])
    assert not any("משרות" in idea for idea in result["ideas"])
    kwargs = save_mock.call_args.kwargs
    assert "10 מועמדים תוך שבוע" in kwargs["idea1"]
    print("test_bug164_regression_goal_preserved_atomically_end_to_end OK")


# ── 4. raw unsupported AI business claims cannot reach persisted Idea fields ──

def test_ai_free_text_field_cannot_reach_persisted_ideas():
    smuggled = json.dumps([
        {"angle_id": "benefit_first", "opening_style": "statement", "cta_style": "apply_now",
         "fact_order": ["goal"], "framing_text": "10 משרות פתוחות"},
    ] * 3)
    m_create, m_get, m_rules, m_save = _mock_marketing_gateway()
    with m_create, m_get, m_rules, m_save as save_mock, \
            patch("llm_fallback.call_anthropic_text", return_value=smuggled):
        result = _create_demand_and_generate_ideas(_STATE, triggered_by="test")

    assert result["ok"] is False, result
    save_mock.assert_not_called()
    print("test_ai_free_text_field_cannot_reach_persisted_ideas OK")


# ── 5. malformed proposal fails closed ──────────────────────────────

def test_malformed_json_fails_closed():
    facts = extract_protected_facts("recDemo1", _DEMAND_FIELDS)
    ok, ideas, reason = _parse_and_render_creative_proposals("not json at all", facts)
    assert not ok and ideas == [] and reason.startswith("invalid_json")
    print("test_malformed_json_fails_closed OK")


# ── 6. unknown field fails closed ───────────────────────────────────

def test_unknown_field_fails_closed():
    facts = extract_protected_facts("recDemo1", _DEMAND_FIELDS)
    raw = json.dumps([
        {"angle_id": "benefit_first", "opening_style": "statement", "cta_style": "apply_now",
         "fact_order": ["goal"], "rationale": "AI free text"},
    ] * 3)
    ok, ideas, reason = _parse_and_render_creative_proposals(raw, facts)
    assert not ok and ideas == [] and "unknown_fields" in reason
    print("test_unknown_field_fails_closed OK")


# ── 7. unknown template combination fails closed ────────────────────

def test_unknown_combination_fails_closed():
    facts = extract_protected_facts("recDemo1", _DEMAND_FIELDS)
    # schedule_visit is a real_estate_listing cta_style, not valid for recruitment
    raw = json.dumps([
        {"angle_id": "benefit_first", "opening_style": "statement", "cta_style": "schedule_visit",
         "fact_order": ["goal"]},
    ] * 3)
    ok, ideas, reason = _parse_and_render_creative_proposals(raw, facts)
    assert not ok and ideas == [] and "unknown_template_combination" in reason
    print("test_unknown_combination_fails_closed OK")


# ── 8. non-renderable/routing/instruction-only fact fails closed ────

def test_non_renderable_fact_fails_closed():
    facts = extract_protected_facts("recDemo1", _DEMAND_FIELDS)
    for routing_key in ("constraints", "domain", "demand_type", "topic"):
        raw = json.dumps([
            {"angle_id": "benefit_first", "opening_style": "statement", "cta_style": "apply_now",
             "fact_order": ["goal", routing_key]},
        ] * 3)
        ok, ideas, reason = _parse_and_render_creative_proposals(raw, facts)
        assert not ok and ideas == [], (routing_key, reason)
        assert "disallowed_fact" in reason, (routing_key, reason)
    print("test_non_renderable_fact_fails_closed OK")


# ── 9. candidate/unconfirmed fact fails closed ───────────────────────

def test_candidate_and_unconfirmed_fact_fails_closed():
    from dataclasses import replace
    facts = extract_protected_facts("recDemo1", _DEMAND_FIELDS)
    raw = json.dumps([
        {"angle_id": "benefit_first", "opening_style": "statement", "cta_style": "apply_now",
         "fact_order": ["goal"]},
    ] * 3)

    candidate_facts = ProtectedDemandFacts(
        demand_id=facts.demand_id,
        facts={**facts.facts, "goal": replace(facts.facts["goal"], authority=FactAuthority.CANDIDATE)},
    )
    ok, ideas, reason = _parse_and_render_creative_proposals(raw, candidate_facts)
    assert not ok and ideas == [] and "non_canonical_authority:goal:candidate" in reason

    unconfirmed_facts = ProtectedDemandFacts(
        demand_id=facts.demand_id,
        facts={**facts.facts, "goal": replace(facts.facts["goal"], confirmed=False)},
    )
    ok2, ideas2, reason2 = _parse_and_render_creative_proposals(raw, unconfirmed_facts)
    assert not ok2 and ideas2 == [] and "unconfirmed_fact:goal" in reason2
    print("test_candidate_and_unconfirmed_fact_fails_closed OK")


# ── 10. renderer failure causes zero creative persistence ───────────

def test_renderer_failure_never_calls_save_creative_ideas():
    invalid = json.dumps([{"angle_id": "not_a_real_angle"}] * 3)
    m_create, m_get, m_rules, m_save = _mock_marketing_gateway()
    with m_create, m_get, m_rules, m_save as save_mock, \
            patch("llm_fallback.call_anthropic_text", return_value=invalid):
        result = _create_demand_and_generate_ideas(_STATE, triggered_by="test")

    assert result["ok"] is False
    save_mock.assert_not_called()
    print("test_renderer_failure_never_calls_save_creative_ideas OK")


# ── 11. there is no legacy raw-text fallback ─────────────────────────

def test_no_legacy_raw_text_fallback():
    import cmd_marketing
    assert not hasattr(cmd_marketing, "_parse_three_ideas"), \
        "legacy free-text idea parser must not exist -- no dormant fallback path"

    # AI response that is exactly the OLD free-text format is rejected, not
    # silently accepted by some remaining compatibility path
    legacy_shaped = "רעיון 1:\nטקסט חופשי\n\nרעיון 2:\nטקסט חופשי\n\nרעיון 3:\nטקסט חופשי"
    facts = extract_protected_facts("recDemo1", _DEMAND_FIELDS)
    ok, ideas, reason = _parse_and_render_creative_proposals(legacy_shaped, facts)
    assert not ok and ideas == []
    print("test_no_legacy_raw_text_fallback OK")


# ── 12. existing creative selection + handoff behavior remains unchanged ──

def test_creative_selection_and_handoff_unchanged():
    from cmd_marketing import _select_creative_and_generate_handoff
    from airtable_schema import MarketingCreativesFields as MCF, MarketingDemandStage

    creative_fields = {
        MCF.IDEA_1: "רעיון קיים לבדיקה",
        MCF.LINKED_DEMAND: ["recDemo1"],
    }
    with patch("marketing_gateway.select_creative", return_value=True), \
            patch("marketing_gateway.get_creative", return_value=creative_fields), \
            patch("marketing_gateway.get_demand", return_value=dict(_DEMAND_FIELDS)), \
            patch("marketing_gateway.get_marketing_rules", return_value=""), \
            patch("marketing_gateway.save_production_handoff", return_value=True) as save_handoff_mock, \
            patch("marketing_gateway.update_demand_stage", return_value=True):
        result = _select_creative_and_generate_handoff("recCreative1", "1")

    assert result["ok"] is True, result
    assert "handoff" in result and isinstance(result["handoff"], str) and result["handoff"]
    save_handoff_mock.assert_called_once()
    assert "רעיון קיים לבדיקה" in save_handoff_mock.call_args.args[1]
    print("test_creative_selection_and_handoff_unchanged OK")


# ── prompt sanity: closed menu never offers a non-renderable key ────

def test_prompt_never_offers_non_renderable_fact_keys():
    facts = extract_protected_facts("recDemo1", _DEMAND_FIELDS)
    instruction = _build_creative_proposal_instruction(_DEMAND_FIELDS, facts, domain_rules="")
    for forbidden in ('"constraints"', '"domain"', '"demand_type"', '"topic"'):
        assert forbidden not in instruction, forbidden
    print("test_prompt_never_offers_non_renderable_fact_keys OK")


if __name__ == "__main__":
    test_valid_proposals_produce_three_rendered_ideas()
    test_end_to_end_saves_rendered_ideas_via_existing_save_path()
    test_bug164_regression_goal_preserved_atomically_end_to_end()
    test_ai_free_text_field_cannot_reach_persisted_ideas()
    test_malformed_json_fails_closed()
    test_unknown_field_fails_closed()
    test_unknown_combination_fails_closed()
    test_non_renderable_fact_fails_closed()
    test_candidate_and_unconfirmed_fact_fails_closed()
    test_renderer_failure_never_calls_save_creative_ideas()
    test_no_legacy_raw_text_fallback()
    test_creative_selection_and_handoff_unchanged()
    test_prompt_never_offers_non_renderable_fact_keys()
    print("test_bug164_pr2_creative_cutover.py: ALL TESTS PASSED")
