# marketing_creative_templates.py — F23 BOSS Marketing Bridge / BUG-164
# Authority Foundation (PR1 of 3).
#
# Closed, deterministic template registry. The AI never authors persisted
# copy — it only selects angle_id/opening_style/cta_style (see
# CreativeProposal in marketing_creative_renderer.py). Each registered
# (demand_type, angle_id, opening_style, cta_style) combination maps to one
# render function built from fixed, developer-authored Hebrew phrase
# fragments — it interpolates whole ProtectedFact.value strings (never a
# substring) into those fragments.
#
# TEMPLATE_REGISTRY / allowed_combinations() are the single source of truth
# for which combinations are valid for a given demand_type. Both the
# AI-facing prompt (BUG-164 PR2 — which combinations to offer the model) and
# marketing_creative_renderer.py (which combinations to accept back) must
# derive their allowed-value lists from here — never maintain a second,
# independent list that could drift out of sync with this one.
#
# PR1 scope: this registry is not yet wired into cmd_marketing.py or the
# creative_ideas prompt (BUG-164 PR2). It ships here as a pure, independently
# tested contract.
#
# Marketing Claim Policy (three classes every piece of generated text falls
# into — see BUG_AUDIT_LOG.md BUG-164 "MARKETING CLAIM POLICY" correction):
#   CREATIVE_DEVICE — non-factual persuasive language (hooks, tone, CTA
#     style, generic urgency/scarcity framing with no concrete claim). No
#     canonical source required. This is ALL a static template fragment in
#     this file is allowed to be — enforced by the self-test below.
#   BOUNDED_CLAIM — a promotional claim whose truth depends on time/state
#     ("רק השבוע", "עד יום חמישי", limited-availability language). Requires
#     system-owned valid_from/valid_until/claim_type/state metadata and must
#     stop rendering once expired. No such governance exists yet (that's a
#     future Marketing Claim Registry / weekly audit layer, explicitly out of
#     scope for BUG-164 PR1/PR2) — so no BOUNDED_CLAIM content may appear as
#     static template text today.
#   BUSINESS_FACT — concrete/verifiable business information (price,
#     quantity, customer count, location, experience requirement, etc.).
#     Requires canonical authority. In this registry, BUSINESS_FACT content
#     enters *only* via ProtectedFact.value interpolation in _PHRASE_BUILDERS
#     (governed by marketing_fact_authority.py's authority/usage checks) —
#     never as static lead-in/CTA text. A static fragment must never assert a
#     fact (a count, a date, an unsourced promise) on its own.
# "Creative" does not mean "anything the AI wants" (angle/opening/CTA
# selection is still bounded by TEMPLATE_REGISTRY). "Canonical" does not mean
# "all marketing must be dry" (CREATIVE_DEVICE framing is fully allowed and
# does not need to trace back to the Demand).

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable

from marketing_fact_authority import ProtectedFact


class ClaimType(str, Enum):
    CREATIVE_DEVICE = "creative_device"
    BOUNDED_CLAIM = "bounded_claim"
    BUSINESS_FACT = "business_fact"

RenderFn = Callable[[dict[str, ProtectedFact], tuple[str, ...]], str]


class AngleId(str, Enum):
    BENEFIT_FIRST = "benefit_first"   # lead with value to the reader
    URGENCY = "urgency"                 # lead with time constraint / scarcity
    SOCIAL_PROOF = "social_proof"       # lead with credibility/experience framing
    DIRECT_OFFER = "direct_offer"       # lead with the offer itself, no framing


class OpeningStyle(str, Enum):
    QUESTION = "question"
    STATEMENT = "statement"
    EXCLAMATION = "exclamation"


class CtaStyle(str, Enum):
    CONTACT_NOW = "contact_now"
    LEARN_MORE = "learn_more"
    APPLY_NOW = "apply_now"            # recruitment
    SCHEDULE_VISIT = "schedule_visit"  # real_estate_listing


@dataclass(frozen=True)
class Template:
    demand_type: str
    angle_id: AngleId
    opening_style: OpeningStyle
    cta_style: CtaStyle
    render: RenderFn


# Fixed, developer-authored connector phrasing per RENDERABLE fact key, per
# demand_type. Deliberately references only topic/audience/location/goal —
# never constraints/domain/demand_type (those are INSTRUCTION_ONLY/
# ROUTING_ONLY, enforced independently by the renderer regardless of what's
# defined here). Wraps the fact's full value verbatim — never a substring.
_PHRASE_BUILDERS: dict[str, dict[str, Callable[[str], str]]] = {
    "recruitment": {
        "goal": lambda v: f"מחפשים {v}",
        "location": lambda v: f"ב{v}",
        "audience": lambda v: f"({v})",
        "topic": lambda v: v,
    },
    "furniture_import": {
        "goal": lambda v: v,
        "location": lambda v: f"זמין ב{v}",
        "audience": lambda v: f"מיועד ל{v}",
        "topic": lambda v: v,
    },
    "fiber_equipment": {
        "goal": lambda v: v,
        "location": lambda v: f"פעילים באזור {v}",
        "audience": lambda v: f"עבור {v}",
        "topic": lambda v: v,
    },
    "real_estate_listing": {
        "goal": lambda v: v,
        "location": lambda v: f"ב{v}",
        "audience": lambda v: f"מתאים ל{v}",
        "topic": lambda v: v,
    },
    "service": {
        "goal": lambda v: v,
        "location": lambda v: f"באזור {v}",
        "audience": lambda v: f"עבור {v}",
        "topic": lambda v: v,
    },
}

# NOTE: URGENCY/SOCIAL_PROOF deliberately avoid any concrete time/date or
# quantity claim ("רק השבוע" / "כבר עשרות לקוחות" would be a BOUNDED_CLAIM and
# a BUSINESS_FACT respectively — see the Marketing Claim Policy note above).
# The *angle itself* (urgency/social-proof as a persuasion strategy) is a
# legitimate CREATIVE_DEVICE; only an ungoverned concrete claim is not.
_ANGLE_LEAD_IN: dict[AngleId, str] = {
    AngleId.BENEFIT_FIRST: "",
    AngleId.URGENCY: "אל תפספסו! ",
    AngleId.SOCIAL_PROOF: "הצטרפו למי שכבר בחרו בנו. ",
    AngleId.DIRECT_OFFER: "",
}

_CTA_TEXT: dict[CtaStyle, str] = {
    CtaStyle.CONTACT_NOW: "צרו קשר עכשיו!",
    CtaStyle.LEARN_MORE: "לפרטים נוספים לחצו כאן.",
    CtaStyle.APPLY_NOW: "הצטרפו אלינו עכשיו!",
    CtaStyle.SCHEDULE_VISIT: "קבעו ביקור עוד היום!",
}

# Every static fragment above is CREATIVE_DEVICE by construction. Kept as an
# explicit, per-entry map (not a blanket assumption) so a future contributor
# adding a BOUNDED_CLAIM/BUSINESS_FACT fragment must consciously override it
# here, and the self-test below fails loudly instead of silently allowing it.
_ANGLE_LEAD_IN_CLAIM_TYPE: dict[AngleId, ClaimType] = {
    angle: ClaimType.CREATIVE_DEVICE for angle in _ANGLE_LEAD_IN
}
_CTA_TEXT_CLAIM_TYPE: dict[CtaStyle, ClaimType] = {
    cta: ClaimType.CREATIVE_DEVICE for cta in _CTA_TEXT
}

# The single closed list of (angle_id, opening_style, cta_style) combos
# supported per demand_type. allowed_combinations() is the only accessor —
# nothing else may hardcode a second list of valid combinations.
_SUPPORTED_COMBOS: dict[str, tuple[tuple[AngleId, OpeningStyle, CtaStyle], ...]] = {
    "recruitment": (
        (AngleId.BENEFIT_FIRST, OpeningStyle.STATEMENT, CtaStyle.APPLY_NOW),
        (AngleId.URGENCY, OpeningStyle.STATEMENT, CtaStyle.APPLY_NOW),
    ),
    "furniture_import": (
        (AngleId.BENEFIT_FIRST, OpeningStyle.STATEMENT, CtaStyle.CONTACT_NOW),
        (AngleId.URGENCY, OpeningStyle.STATEMENT, CtaStyle.CONTACT_NOW),
    ),
    "fiber_equipment": (
        (AngleId.BENEFIT_FIRST, OpeningStyle.STATEMENT, CtaStyle.LEARN_MORE),
        (AngleId.DIRECT_OFFER, OpeningStyle.STATEMENT, CtaStyle.CONTACT_NOW),
    ),
    "real_estate_listing": (
        (AngleId.BENEFIT_FIRST, OpeningStyle.STATEMENT, CtaStyle.SCHEDULE_VISIT),
        (AngleId.SOCIAL_PROOF, OpeningStyle.STATEMENT, CtaStyle.SCHEDULE_VISIT),
    ),
    "service": (
        (AngleId.BENEFIT_FIRST, OpeningStyle.STATEMENT, CtaStyle.CONTACT_NOW),
        (AngleId.SOCIAL_PROOF, OpeningStyle.QUESTION, CtaStyle.LEARN_MORE),
    ),
}


def _build_render_fn(demand_type: str, angle_id: AngleId, opening_style: OpeningStyle, cta_style: CtaStyle) -> RenderFn:
    phrase_builders = _PHRASE_BUILDERS[demand_type]
    lead_in = _ANGLE_LEAD_IN[angle_id]
    cta_text = _CTA_TEXT[cta_style]

    def _render(facts: dict[str, ProtectedFact], order: tuple[str, ...]) -> str:
        segments = [
            phrase_builders[key](facts[key].value)
            for key in order
            if key in phrase_builders and key in facts
        ]
        body = " ".join(segments)
        if opening_style is OpeningStyle.QUESTION:
            body = f"{body}?"
        elif opening_style is OpeningStyle.EXCLAMATION:
            body = f"{body}!"
        return f"{lead_in}{body} {cta_text}".strip()

    return _render


TEMPLATE_REGISTRY: dict[tuple[str, AngleId, OpeningStyle, CtaStyle], Template] = {}
for _demand_type, _combos in _SUPPORTED_COMBOS.items():
    for _angle, _opening, _cta in _combos:
        TEMPLATE_REGISTRY[(_demand_type, _angle, _opening, _cta)] = Template(
            demand_type=_demand_type, angle_id=_angle, opening_style=_opening, cta_style=_cta,
            render=_build_render_fn(_demand_type, _angle, _opening, _cta),
        )


def allowed_combinations(demand_type: str) -> tuple[tuple[AngleId, OpeningStyle, CtaStyle], ...]:
    """Single source of valid (angle_id, opening_style, cta_style) combos for
    a demand_type. Returns () for an unrecognized demand_type — callers must
    treat that as "nothing valid to offer/accept", not raise."""
    return _SUPPORTED_COMBOS.get(demand_type, ())


if __name__ == "__main__":
    for dt in ("recruitment", "furniture_import", "fiber_equipment", "real_estate_listing", "service"):
        combos = allowed_combinations(dt)
        assert combos, f"{dt} has no supported combinations"
        for combo in combos:
            assert (dt, *combo) in TEMPLATE_REGISTRY

    assert allowed_combinations("not_a_real_type") == ()

    # Marketing Claim Policy: every static template fragment shipped in PR1
    # must be CREATIVE_DEVICE -- no BOUNDED_CLAIM/BUSINESS_FACT content until
    # a validity-window/claim-registry layer exists to govern it.
    assert all(v is ClaimType.CREATIVE_DEVICE for v in _ANGLE_LEAD_IN_CLAIM_TYPE.values())
    assert all(v is ClaimType.CREATIVE_DEVICE for v in _CTA_TEXT_CLAIM_TYPE.values())
    assert set(_ANGLE_LEAD_IN_CLAIM_TYPE) == set(_ANGLE_LEAD_IN)
    assert set(_CTA_TEXT_CLAIM_TYPE) == set(_CTA_TEXT)
    # no leftover concrete time-bound/quantity claims in the static fragments.
    # ("קבעו ביקור עוד היום!" 's "היום" is a CTA action verb -- "come today" --
    # not a validity-window promise like "עד היום"/"רק היום"; still checked
    # for a literal digit or "השבוע", neither of which it contains.)
    for _text in (*_ANGLE_LEAD_IN.values(), *_CTA_TEXT.values()):
        assert "השבוע" not in _text, _text
        assert not any(digit in _text for digit in "0123456789"), _text

    # BUG-164 proof: the full canonical goal value is interpolated atomically
    # -- "10" can never appear detached from "מועמדים תוך שבוע".
    from marketing_fact_authority import FactAuthority, FactUsage, SemanticType

    goal_fact = ProtectedFact(
        key="goal", value="10 מועמדים תוך שבוע", source="Demand.goal",
        semantic_type=SemanticType.RECRUITMENT_GOAL, authority=FactAuthority.CANONICAL,
        usage=FactUsage.RENDERABLE,
    )
    template = TEMPLATE_REGISTRY[("recruitment", AngleId.BENEFIT_FIRST, OpeningStyle.STATEMENT, CtaStyle.APPLY_NOW)]
    rendered = template.render({"goal": goal_fact}, ("goal",))
    assert "10 מועמדים תוך שבוע" in rendered
    assert "משרות" not in rendered

    print("marketing_creative_templates.py self-test OK")
