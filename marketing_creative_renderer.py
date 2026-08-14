# marketing_creative_renderer.py — F23 BOSS Marketing Bridge / BUG-164
# Authority Foundation (PR1 of 3).
#
# CreativeProposal is the AI's ENTIRE output contract for creative_ideas: a
# closed set of structural choices (which template combination, in what
# fact order) — never free text. There is no field on this dataclass an
# arbitrary AI-authored string could occupy.
#
# FINAL CORRECTION PASS: emphasis_fact_keys was removed. It was validated
# but never had any deterministic rendering effect (render() only ever
# consumed fact_order) — a field with no effect is dead surface area an AI
# response could exploit for nothing and a reviewer could be misled by for
# nothing, so it's gone rather than kept unused.
#
# authority_filter_and_render() is the single deterministic boundary between
# a CreativeProposal and persisted copy. Every fact_order reference must pass
# ALL of, in order:
#   1. structural bounds -- fact_order not oversized, no duplicates
#   2. marketing_creative_templates.TEMPLATE_REGISTRY combination is known
#      (unknown angle/opening/cta combination -> fail closed)
#   3. Template Semantic Contract -- every referenced key is in the
#      Template's allowed_fact_keys, and every one of its required_fact_keys
#      is present (disallowed/missing-required -> fail closed)
#   4. per-key render authority against ProtectedDemandFacts -- authority ==
#      CANONICAL, confirmed == True, usage == RENDERABLE, and the fact's
#      semantic_type matches what the Template contract declares for that
#      key (a matching key NAME is not enough -- semantic mismatch fails
#      closed too)
# No step here truncates, dedupes, or otherwise repairs a malformed
# proposal — every violation is a hard rejection of the whole proposal.
#
# Canonical authority alone does not grant render permission — usage is
# checked independently of authority, so a canonical-but-INSTRUCTION_ONLY
# fact like Constraints can never be interpolated into copy just because it
# is "true" and "known". Likewise DETERMINISTIC/CANDIDATE authority tiers
# (defined in marketing_fact_authority.py for future governance use) are not
# renderable in this live design yet — PR1/PR2 render authority is CANONICAL
# only.
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
#
# Marketing Claim Policy note: the fact-authority gate above applies only to
# fact_order, i.e. references into ProtectedDemandFacts — it never restricts
# angle_id/opening_style/cta_style selection itself. Persuasive, non-factual
# creative framing (tone, hooks, CTA style, generic urgency/social-proof
# angle choice) is not required to trace back to the Demand and is never
# rejected for that reason — see the ClaimType note at the top of
# marketing_creative_templates.py for the full three-way CREATIVE_DEVICE /
# BOUNDED_CLAIM / BUSINESS_FACT split this registry enforces on its own
# static text.

from __future__ import annotations

from dataclasses import dataclass

from marketing_creative_templates import AngleId, CtaStyle, OpeningStyle, Template, TEMPLATE_REGISTRY
from marketing_fact_authority import FactAuthority, FactUsage, ProtectedDemandFacts

_ALLOWED_PROPOSAL_FIELDS = frozenset({
    "angle_id", "opening_style", "cta_style", "fact_order",
})

# Defensive bound on fact_order length, independent of any single Template's
# allowed_fact_keys size (currently 3). Checked first, before any set math,
# so a pathologically long AI-authored list is rejected cheaply rather than
# processed. Generous headroom above today's max (3) for future demand types
# with more renderable slots, while still bounding worst-case input size.
_MAX_FACT_ORDER_LEN = 10


@dataclass(frozen=True)
class CreativeProposal:
    angle_id: AngleId
    opening_style: OpeningStyle
    cta_style: CtaStyle
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

    order = raw.get("fact_order", ())
    if not isinstance(order, (list, tuple)) or not all(isinstance(k, str) for k in order):
        raise ProposalRejected("invalid_fact_order")

    return CreativeProposal(
        angle_id=angle_id, opening_style=opening_style, cta_style=cta_style,
        fact_order=tuple(order),
    )


@dataclass(frozen=True)
class RenderResult:
    status: str          # "ok" | "rejected"
    rendered: str | None = None
    reason: str = ""


def _check_fact_order_bounds(fact_order: tuple[str, ...], template: Template) -> str | None:
    """Structural checks against the Template Semantic Contract only --
    duplicates / oversized / disallowed / missing-required. Returns a reason
    string on rejection, None if the shape is acceptable. Never
    truncates/dedupes/repairs -- every violation is reported, none fixed."""
    if len(fact_order) > _MAX_FACT_ORDER_LEN:
        return "oversized_fact_order"

    if len(fact_order) != len(set(fact_order)):
        return "duplicate_fact_order"

    order_set = set(fact_order)
    disallowed = order_set - template.allowed_fact_keys
    if disallowed:
        return f"disallowed_fact:{sorted(disallowed)}"

    missing_required = template.required_fact_keys - order_set
    if missing_required:
        return f"missing_required_fact:{sorted(missing_required)}"

    return None


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

    bounds_violation = _check_fact_order_bounds(proposal.fact_order, template)
    if bounds_violation is not None:
        return RenderResult(status="rejected", reason=bounds_violation)

    for key in proposal.fact_order:
        fact = facts.facts.get(key)
        if fact is None:
            return RenderResult(status="rejected", reason=f"unknown_fact_key:{key}")
        if fact.authority is not FactAuthority.CANONICAL:
            return RenderResult(status="rejected", reason=f"non_canonical_authority:{key}:{fact.authority.value}")
        if not fact.confirmed:
            return RenderResult(status="rejected", reason=f"unconfirmed_fact:{key}")
        if fact.usage is not FactUsage.RENDERABLE:
            return RenderResult(status="rejected", reason=f"non_renderable_usage:{key}:{fact.usage.value}")
        expected_semantic = template.fact_semantic_types.get(key)
        if expected_semantic is not None and fact.semantic_type is not expected_semantic:
            return RenderResult(
                status="rejected",
                reason=f"semantic_mismatch:{key}:{fact.semantic_type.value}!={expected_semantic.value}",
            )

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
        "fact_order": ["goal", "location", "audience"],
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

    # removed field (emphasis_fact_keys) -> now also an unknown field
    try:
        parse_creative_proposal({**valid_raw, "emphasis_fact_keys": ["goal"]})
        raise AssertionError("expected ProposalRejected")
    except ProposalRejected as e:
        assert "unknown_fields" in str(e)

    # invalid enum value -> hard reject
    try:
        parse_creative_proposal({**valid_raw, "angle_id": "not_a_real_angle"})
        raise AssertionError("expected ProposalRejected")
    except ProposalRejected:
        pass

    # referencing constraints (not an allowed key for this template) -> fail closed
    p2 = parse_creative_proposal({**valid_raw, "fact_order": ["goal", "constraints"]})
    r2 = authority_filter_and_render(p2, facts)
    assert r2.status == "rejected" and "disallowed_fact" in r2.reason and "constraints" in r2.reason

    # referencing domain (ROUTING_ONLY, canonical, also not an allowed key) -> fail closed
    # (canonical authority alone does not grant render permission)
    p3 = parse_creative_proposal({**valid_raw, "fact_order": ["goal", "domain"]})
    r3 = authority_filter_and_render(p3, facts)
    assert r3.status == "rejected" and "disallowed_fact" in r3.reason and "domain" in r3.reason

    # referencing topic (ROUTING_ONLY, not an allowed key for any template) -> fail closed
    p3b = parse_creative_proposal({**valid_raw, "fact_order": ["goal", "topic"]})
    r3b = authority_filter_and_render(p3b, facts)
    assert r3b.status == "rejected" and "disallowed_fact" in r3b.reason and "topic" in r3b.reason

    # a key outside any template's allowed set entirely -> disallowed_fact
    p4 = parse_creative_proposal({**valid_raw, "fact_order": ["goal", "not_a_real_key"]})
    r4 = authority_filter_and_render(p4, facts)
    assert r4.status == "rejected" and "disallowed_fact" in r4.reason

    # a key that IS structurally allowed by the template but was never
    # extracted for this Demand (e.g. the field was empty) -> unknown_fact_key
    facts_missing_audience = ProtectedDemandFacts(
        demand_id=facts.demand_id,
        facts={k: v for k, v in facts.facts.items() if k != "audience"},
    )
    p4b = parse_creative_proposal({**valid_raw, "fact_order": ["goal", "audience"]})
    r4b = authority_filter_and_render(p4b, facts_missing_audience)
    assert r4b.status == "rejected" and r4b.reason == "unknown_fact_key:audience"

    # unregistered combination for this demand_type -> fail closed
    p5 = parse_creative_proposal({**valid_raw, "cta_style": "schedule_visit"})
    r5 = authority_filter_and_render(p5, facts)
    assert r5.status == "rejected" and r5.reason == "unknown_template_combination"

    # duplicate fact_order -> fail closed
    p6 = parse_creative_proposal({**valid_raw, "fact_order": ["goal", "goal", "location"]})
    r6 = authority_filter_and_render(p6, facts)
    assert r6.status == "rejected" and r6.reason == "duplicate_fact_order"

    # missing required fact ("goal" required, omitted) -> fail closed
    p7 = parse_creative_proposal({**valid_raw, "fact_order": ["location", "audience"]})
    r7 = authority_filter_and_render(p7, facts)
    assert r7.status == "rejected" and "missing_required_fact" in r7.reason and "goal" in r7.reason

    # oversized fact_order -> fail closed, before any set-membership check
    p8 = parse_creative_proposal({**valid_raw, "fact_order": [f"k{i}" for i in range(_MAX_FACT_ORDER_LEN + 1)]})
    r8 = authority_filter_and_render(p8, facts)
    assert r8.status == "rejected" and r8.reason == "oversized_fact_order"

    # semantic mismatch: a fact with the right key/authority/usage/confirmed
    # but the WRONG semantic_type for this template must still fail closed --
    # a matching key name is not enough.
    from dataclasses import replace as _replace
    mismatched_facts = ProtectedDemandFacts(
        demand_id=facts.demand_id,
        facts={**facts.facts, "audience": _replace(facts.facts["audience"], semantic_type=facts.facts["location"].semantic_type)},
    )
    p9 = parse_creative_proposal({**valid_raw, "fact_order": ["goal", "audience"]})
    r9 = authority_filter_and_render(p9, mismatched_facts)
    assert r9.status == "rejected" and "semantic_mismatch:audience" in r9.reason

    # non-CANONICAL authority (allowed key, right usage/confirmed, but not
    # CANONICAL) -> fail closed; DETERMINISTIC/CANDIDATE are not renderable
    # in this live design yet.
    from marketing_fact_authority import FactAuthority as _FA
    non_canonical_facts = ProtectedDemandFacts(
        demand_id=facts.demand_id,
        facts={**facts.facts, "goal": _replace(facts.facts["goal"], authority=_FA.DETERMINISTIC)},
    )
    p10 = parse_creative_proposal(valid_raw)
    r10 = authority_filter_and_render(p10, non_canonical_facts)
    assert r10.status == "rejected" and "non_canonical_authority:goal" in r10.reason

    print("marketing_creative_renderer.py self-test OK")
