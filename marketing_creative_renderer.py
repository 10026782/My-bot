# marketing_creative_renderer.py — F23 BOSS Marketing Bridge / BUG-164
# Authority Foundation (PR1 of 3).
#
# CreativeProposal is the AI's ENTIRE output contract for creative_ideas: a
# closed set of structural choices (which template combination, which known
# facts, in what order) — never free text. There is no field on this
# dataclass an arbitrary AI-authored string could occupy.
#
# authority_filter_and_render() is the single deterministic boundary between
# a CreativeProposal and persisted copy. It validates the proposal's
# angle_id/opening_style/cta_style against
# marketing_creative_templates.TEMPLATE_REGISTRY (unknown combination -> fail
# closed) and every fact key it references against ProtectedDemandFacts
# (unknown key, or a key whose usage isn't RENDERABLE, or an unconfirmed fact
# -> fail closed) before calling the registered pure render function.
# Canonical authority alone does not grant render permission — usage is
# checked independently of authority, so a canonical-but-INSTRUCTION_ONLY
# fact like Constraints can never be interpolated into copy just because it
# is "true" and "known".
#
# No AI-authored string ever reaches the returned rendered text: the only
# strings involved are (a) the Hebrew skeleton fragments hand-written in
# marketing_creative_templates.py, and (b) whole ProtectedFact.value strings
# looked up by key — the same values, without modification, that
# marketing_fact_authority.extract_protected_facts() pinned to a
# semantic_type and to an unconfirmed/confirmed authority tier.
#
# PR1 scope: not yet wired into cmd_marketing.py or the creative_ideas
# prompt — that live cutover is BUG-164 PR2. This module ships here as a
# pure, independently tested contract only. No CandidateFact
# solicitation/confirmation flow exists in this PR (or in PR2) — see
# BUG_AUDIT_LOG.md BUG-164 for why that's explicitly out of scope for now.

from __future__ import annotations

from dataclasses import dataclass

from marketing_creative_templates import AngleId, CtaStyle, OpeningStyle, TEMPLATE_REGISTRY
from marketing_fact_authority import FactUsage, ProtectedDemandFacts

_ALLOWED_PROPOSAL_FIELDS = frozenset({
    "angle_id", "opening_style", "cta_style", "emphasis_fact_keys", "fact_order",
})


@dataclass(frozen=True)
class CreativeProposal:
    angle_id: AngleId
    opening_style: OpeningStyle
    cta_style: CtaStyle
    emphasis_fact_keys: tuple[str, ...] = ()
    fact_order: tuple[str, ...] = ()


class ProposalRejected(ValueError):
    """Raised by parse_creative_proposal on any malformed/unrecognized AI output."""


def parse_creative_proposal(raw: dict) -> CreativeProposal:
    """
    raw: one already-JSON-decoded object from the AI's response. Unknown
    top-level keys are a hard reject, never silently discarded -- an AI
    response that tries to smuggle in e.g. a "framing_text"/"copy" key fails
    here, before any of its content can be inspected further.
    """
    if not isinstance(raw, dict):
        raise ProposalRejected("proposal_not_an_object")

    unknown = set(raw.keys()) - _ALLOWED_PROPOSAL_FIELDS
    if unknown:
        raise ProposalRejected(f"unknown_fields:{sorted(unknown)}")

    try:
        angle_id = AngleId(raw["angle_id"])
        opening_style = OpeningStyle(raw["opening_style"])
        cta_style = CtaStyle(raw["cta_style"])
    except KeyError as e:
        raise ProposalRejected(f"missing_field:{e}") from e
    except ValueError as e:
        raise ProposalRejected(f"invalid_enum_value:{e}") from e

    emphasis = raw.get("emphasis_fact_keys", ())
    order = raw.get("fact_order", ())
    if not isinstance(emphasis, (list, tuple)) or not all(isinstance(k, str) for k in emphasis):
        raise ProposalRejected("invalid_emphasis_fact_keys")
    if not isinstance(order, (list, tuple)) or not all(isinstance(k, str) for k in order):
        raise ProposalRejected("invalid_fact_order")

    return CreativeProposal(
        angle_id=angle_id, opening_style=opening_style, cta_style=cta_style,
        emphasis_fact_keys=tuple(emphasis), fact_order=tuple(order),
    )


@dataclass(frozen=True)
class RenderResult:
    status: str          # "ok" | "rejected"
    rendered: str | None = None
    reason: str = ""


def authority_filter_and_render(proposal: CreativeProposal, facts: ProtectedDemandFacts) -> RenderResult:
    demand_type_fact = facts.facts.get("demand_type")
    if demand_type_fact is None:
        return RenderResult(status="rejected", reason="missing_demand_type")

    template = TEMPLATE_REGISTRY.get(
        (demand_type_fact.value, proposal.angle_id, proposal.opening_style, proposal.cta_style)
    )
    if template is None:
        return RenderResult(status="rejected", reason="unknown_template_combination")

    if not proposal.fact_order:
        return RenderResult(status="rejected", reason="empty_fact_order")

    for key in (*proposal.fact_order, *proposal.emphasis_fact_keys):
        fact = facts.facts.get(key)
        if fact is None:
            return RenderResult(status="rejected", reason=f"unknown_fact_key:{key}")
        if fact.usage is not FactUsage.RENDERABLE:
            return RenderResult(status="rejected", reason=f"non_renderable_usage:{key}:{fact.usage.value}")
        if not fact.confirmed:
            return RenderResult(status="rejected", reason=f"unconfirmed_fact:{key}")

    rendered_text = template.render(facts.renderable(), proposal.fact_order)
    return RenderResult(status="ok", rendered=rendered_text)


if __name__ == "__main__":
    from marketing_fact_authority import extract_protected_facts

    demand = {
        "Domain": "general",
        "Demand Type": "recruitment",
        "Demand Title": "דרישה למתקינים",
        "Target Audience": "ניסיון 3+ שנים",
        "Location": "בית שמש",
        "Goal": "10 מועמדים תוך שבוע",
        "Constraints": "מיקום נגיש לנכים",
    }
    facts = extract_protected_facts("recDemo1", demand)

    valid_raw = {
        "angle_id": "benefit_first", "opening_style": "statement", "cta_style": "apply_now",
        "emphasis_fact_keys": ["goal"], "fact_order": ["goal", "location", "audience"],
    }
    proposal = parse_creative_proposal(valid_raw)
    result = authority_filter_and_render(proposal, facts)
    assert result.status == "ok", result.reason
    assert "10 מועמדים תוך שבוע" in result.rendered
    assert "משרות" not in result.rendered

    # unknown top-level field (e.g. an AI trying to smuggle prose) -> hard reject
    try:
        parse_creative_proposal({**valid_raw, "framing_text": "10 משרות פתוחות"})
        raise AssertionError("expected ProposalRejected")
    except ProposalRejected as e:
        assert "unknown_fields" in str(e)

    # invalid enum value -> hard reject
    try:
        parse_creative_proposal({**valid_raw, "angle_id": "not_a_real_angle"})
        raise AssertionError("expected ProposalRejected")
    except ProposalRejected:
        pass

    # referencing constraints (INSTRUCTION_ONLY) as copy -> fail closed
    p2 = parse_creative_proposal({**valid_raw, "fact_order": ["goal", "constraints"]})
    r2 = authority_filter_and_render(p2, facts)
    assert r2.status == "rejected" and "non_renderable_usage:constraints" in r2.reason

    # referencing domain (ROUTING_ONLY, canonical) as copy -> fail closed
    # (canonical authority alone does not grant render permission)
    p3 = parse_creative_proposal({**valid_raw, "fact_order": ["goal", "domain"]})
    r3 = authority_filter_and_render(p3, facts)
    assert r3.status == "rejected" and "non_renderable_usage:domain" in r3.reason

    # unknown fact key -> fail closed
    p4 = parse_creative_proposal({**valid_raw, "fact_order": ["goal", "not_a_real_key"]})
    r4 = authority_filter_and_render(p4, facts)
    assert r4.status == "rejected" and "unknown_fact_key:not_a_real_key" in r4.reason

    # unregistered combination for this demand_type -> fail closed
    p5 = parse_creative_proposal({**valid_raw, "cta_style": "schedule_visit"})
    r5 = authority_filter_and_render(p5, facts)
    assert r5.status == "rejected" and r5.reason == "unknown_template_combination"

    print("marketing_creative_renderer.py self-test OK")
