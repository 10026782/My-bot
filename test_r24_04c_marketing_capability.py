from types import SimpleNamespace

import cmd_marketing
from core import ExecutionContext
from core.router import ExecutionClass, Intent
from core.turn_coordinator_runtime import resolve_marketing_creative_drafting_capability
from core.usage_telemetry import usage_attribution_from_context


def test_marketing_intent_and_capability_are_canonical():
    capability = resolve_marketing_creative_drafting_capability()

    assert Intent.DRAFT_MARKETING_CREATIVES in Intent.ALL
    assert capability.capability_id == "marketing.creative_idea_drafting"
    assert capability.execution_class is ExecutionClass.NARROW_MODEL
    assert capability.executor_ref
    assert Intent.DRAFT_MARKETING_CREATIVES not in {
        Intent.ASK_QUESTION, Intent.DRAFT_MESSAGE, Intent.GENERATE_REPORT,
    }


def test_marketing_request_creates_one_operation_and_context():
    context = cmd_marketing._create_marketing_execution_context()

    assert isinstance(context, ExecutionContext)
    assert context.operation.capability_id == "marketing.creative_idea_drafting"
    assert context.operation.execution_class is ExecutionClass.NARROW_MODEL
    assert context.resolved_capability is not None


def test_marketing_context_translates_to_canonical_p23_m3_attribution():
    context = cmd_marketing._create_marketing_execution_context()

    assert usage_attribution_from_context(context) == {
        "capability_id": "marketing.creative_idea_drafting",
        "execution_class": "NARROW_MODEL",
        "operation_id": context.operation.operation_id,
    }


def test_paid_marketing_helper_passes_same_context_to_paid_call(monkeypatch):
    context = cmd_marketing._create_marketing_execution_context()
    seen = []

    monkeypatch.setattr(cmd_marketing, "_parse_and_render_creative_proposals",
                        lambda raw, facts: (True, ["a", "b", "c"], ""))
    monkeypatch.setattr(cmd_marketing, "_materialize_demand_fields",
                        lambda demand_type, answers: {
                            "target_audience": "audience", "location": "place", "goal": "goal",
                        })
    monkeypatch.setattr(cmd_marketing, "_build_creative_proposal_instruction",
                        lambda demand, facts, domain_rules: "instruction")

    fake_gateway = SimpleNamespace(
        DemandRecord=lambda **kwargs: kwargs,
        create_demand=lambda record: "demand-1",
        get_demand=lambda demand_id: {"Name": "Demand"},
        get_marketing_rules=lambda domain: {},
        save_creative_ideas=lambda **kwargs: "creative-1",
    )
    monkeypatch.setitem(__import__("sys").modules, "marketing_gateway", fake_gateway)
    monkeypatch.setitem(__import__("sys").modules, "marketing_fact_authority",
                        SimpleNamespace(extract_protected_facts=lambda demand_id, demand: {}))

    def fake_paid_call(**kwargs):
        seen.append(kwargs["execution_context"])
        return "[]"

    monkeypatch.setattr("llm_fallback.call_anthropic_text", fake_paid_call)

    result = cmd_marketing._create_demand_and_generate_ideas(
        {"domain": "general", "demand_type": "service", "answers": {}},
        execution_context=context,
    )

    assert result["ok"] is True
    assert seen == [context]
    assert seen[0].operation.operation_id == context.operation.operation_id
