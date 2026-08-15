# test_marketing_brief_composer.py — BUG-164 regression
#
# BUG-164: a creative_ideas AI call (Prompt 1) rewrote Demand.Goal
# "10 מועמדים תוך שבוע" into the unrelated claim "10 משרות פתוחות". Root
# cause: compose_brief() (creative_ideas/creative_review/ad_package/
# publishing_plan) had no equivalent of compose_production_handoff()'s
# _INVENT_CONTRACT telling the model to preserve quantitative facts from
# [פרטי הדרישה] unchanged. These tests prove the fix at the only layer this
# repo controls deterministically — the composed prompt text — since actual
# LLM output isn't unit-testable without a live/mocked API call (out of
# scope for this file, matching every other test_*.py in this repo).

from marketing_brief_composer import compose_brief, compose_production_handoff, TASK_TYPES
from airtable_schema import MarketingDemandFields as MDF

_DEMAND = {
    MDF.DOMAIN: "general",
    MDF.DEMAND_TYPE: "recruitment",
    MDF.NAME: "דרישה למתקינים",
    MDF.TARGET_AUDIENCE: "ניסיון 3+ שנים",
    MDF.LOCATION: "בית שמש",
    MDF.GOAL: "10 מועמדים תוך שבוע",
}


def test_creative_ideas_brief_includes_fidelity_rule():
    brief = compose_brief(demand=_DEMAND, task_type="creative_ideas")
    assert "[כלל מחייב]" in brief
    assert "אין לשנות" in brief and "להמציא" in brief


def test_demand_goal_appears_verbatim_in_creative_ideas_brief():
    brief = compose_brief(demand=_DEMAND, task_type="creative_ideas")
    assert "10 מועמדים תוך שבוע" in brief
    # the exact fabricated phrase observed in production must never be
    # something the composer itself introduces into the prompt.
    assert "10 משרות פתוחות" not in brief


def test_fidelity_rule_present_across_all_compose_brief_task_types():
    for task_type in TASK_TYPES:
        if task_type == "production_handoff":
            continue  # uses compose_production_handoff(), covered separately below
        brief = compose_brief(demand=_DEMAND, task_type=task_type)
        assert "אין לשנות" in brief, f"fidelity rule missing for task_type={task_type!r}"
        assert "10 מועמדים תוך שבוע" in brief, f"Demand.Goal missing verbatim for task_type={task_type!r}"


def test_compose_brief_still_deterministic_with_fidelity_rule():
    b1 = compose_brief(demand=_DEMAND, task_type="creative_ideas", domain_rules="תמיד לציין שכר.")
    b2 = compose_brief(demand=_DEMAND, task_type="creative_ideas", domain_rules="תמיד לציין שכר.")
    assert b1 == b2


def test_production_handoff_invent_contract_unaffected():
    # regression guard: BUG-164's fix must not touch or duplicate the
    # pre-existing, separate grounding contract compose_production_handoff()
    # already had — no parallel source of truth for the same guarantee.
    handoff = compose_production_handoff(demand=_DEMAND, selected_creative="רעיון לדוגמה")
    assert "אין להמציא" in handoff
    assert handoff.count("[כלל מחייב]") == 1


if __name__ == "__main__":
    import sys

    failures = []
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as e:
                failures.append(name)
                print(f"FAIL {name}: {e}")
    if failures:
        print(f"\n{len(failures)} failure(s): {failures}")
        sys.exit(1)
    print(f"\nAll {sum(1 for n in globals() if n.startswith('test_'))} tests passed.")
