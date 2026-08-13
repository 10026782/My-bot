# marketing_fact_authority.py — F23 BOSS Marketing Bridge / BUG-164 Authority
# Foundation (PR1 of 3 — see BUG_AUDIT_LOG.md BUG-164 for the full design
# history; this file implements the "FINAL AUTHORITY REDESIGN" contract).
#
# Pure, deterministic. No Airtable I/O, no AI call. Defines ProtectedFact —
# the only shape a fact is allowed to take before it can reach
# marketing_creative_renderer.py's authority_filter_and_render(). Every fact
# carries three independent pieces of metadata, on purpose kept separate:
#
#   authority  — who owns this value (CANONICAL/DETERMINISTIC/CANDIDATE).
#                Canonical authority does NOT by itself mean the value may be
#                published — see `usage` below.
#   usage      — whether this fact may ever appear as rendered copy at all.
#                Constraints is canonical business truth but is an
#                INSTRUCTION to the copy, not something to quote verbatim.
#                Domain/Demand Type are canonical but exist for routing only.
#   semantic_type — the business predicate this value's meaning is pinned
#                to. Prevents a deterministically-extracted value from being
#                reattached to a different meaning than its source (BUG-164's
#                actual failure mode: "10" staying "10" while its meaning
#                silently changed from "candidates wanted" to "open roles").
#
# extract_protected_facts() is the single shared entry point building this
# from a canonical Demand record, built on top of
# marketing_brief_composer.protected_demand_fields() — one field-extraction
# definition, two consumers (the AI-facing brief and this grounding layer),
# so they cannot drift apart on what a Demand's fields are.
#
# PR1 scope: this module ships NO derivation rules. Every ProtectedFact here
# is a whole, unmodified canonical field value — never a substring, regex
# match, or other transformation of one. That is what makes it impossible
# for a fact to carry a semantic meaning narrower than its full source value
# (see the module docstring in marketing_creative_renderer.py for why this
# matters). A future DETERMINISTIC-tier derivation rule may be added later,
# but only by explicitly declaring both its extraction function AND the
# semantic_type it is claimed to preserve — a reviewable, visible diff, not
# something this module does implicitly.

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from marketing_brief_composer import protected_demand_fields


class FactAuthority(str, Enum):
    CANONICAL = "canonical"
    DETERMINISTIC = "deterministic"
    CANDIDATE = "candidate"


class FactUsage(str, Enum):
    RENDERABLE = "renderable"        # may be interpolated into persisted copy
    INSTRUCTION_ONLY = "instruction_only"  # governs copy, never quoted as copy
    ROUTING_ONLY = "routing_only"    # selects templates/behavior, never copy


class SemanticType(str, Enum):
    TOPIC_TITLE = "topic_title"
    TARGET_AUDIENCE = "target_audience"
    WORK_LOCATION = "work_location"
    CONSTRAINTS_TEXT = "constraints_text"
    ROUTING_DOMAIN = "routing_domain"
    ROUTING_DEMAND_TYPE = "routing_demand_type"
    RECRUITMENT_GOAL = "recruitment_goal"
    SALES_GOAL = "sales_goal"
    LISTING_GOAL = "listing_goal"
    SERVICE_GOAL = "service_goal"


@dataclass(frozen=True)
class ProtectedFact:
    key: str
    value: str
    source: str
    semantic_type: SemanticType
    authority: FactAuthority
    usage: FactUsage
    confirmed: bool = True


@dataclass(frozen=True)
class ProtectedDemandFacts:
    demand_id: str
    facts: dict[str, ProtectedFact]

    def renderable(self) -> dict[str, ProtectedFact]:
        """Facts eligible to ever appear in persisted copy: usage=RENDERABLE
        and confirmed. Canonical authority alone is not sufficient — this is
        the only place that combines both checks, so callers never have to
        remember to check `usage` separately from `authority`."""
        return {
            k: f for k, f in self.facts.items()
            if f.usage is FactUsage.RENDERABLE and f.confirmed
        }


# Slots whose semantic meaning is fixed regardless of demand_type.
_FIXED_SLOT_SEMANTICS: dict[str, tuple[SemanticType, FactUsage]] = {
    "topic": (SemanticType.TOPIC_TITLE, FactUsage.RENDERABLE),
    "audience": (SemanticType.TARGET_AUDIENCE, FactUsage.RENDERABLE),
    "location": (SemanticType.WORK_LOCATION, FactUsage.RENDERABLE),
    "constraints": (SemanticType.CONSTRAINTS_TEXT, FactUsage.INSTRUCTION_ONLY),
    "domain": (SemanticType.ROUTING_DOMAIN, FactUsage.ROUTING_ONLY),
    "demand_type": (SemanticType.ROUTING_DEMAND_TYPE, FactUsage.ROUTING_ONLY),
}

# "Goal" is one generic Airtable field (MarketingDemandFields.GOAL) reused
# across all 5 demand types with a different business meaning each time —
# so unlike the fixed slots above, its semantic_type must be resolved per
# demand_type, not globally. Keys must match marketing_domain_profiles.PROFILES.
_GOAL_SEMANTICS_BY_DEMAND_TYPE: dict[str, SemanticType] = {
    "recruitment": SemanticType.RECRUITMENT_GOAL,
    "furniture_import": SemanticType.SALES_GOAL,
    "fiber_equipment": SemanticType.SALES_GOAL,
    "real_estate_listing": SemanticType.LISTING_GOAL,
    "service": SemanticType.SERVICE_GOAL,
}


def extract_protected_facts(demand_id: str, demand: dict) -> ProtectedDemandFacts:
    """
    Pure. Builds the canonical-tier ProtectedFact set for one Demand record.
    """
    raw = protected_demand_fields(demand)
    facts: dict[str, ProtectedFact] = {}

    for key, (semantic_type, usage) in _FIXED_SLOT_SEMANTICS.items():
        if raw.get(key):
            facts[key] = ProtectedFact(
                key=key, value=raw[key], source=f"Demand.{key}",
                semantic_type=semantic_type, authority=FactAuthority.CANONICAL,
                usage=usage, confirmed=True,
            )

    if raw.get("goal"):
        semantic_type = _GOAL_SEMANTICS_BY_DEMAND_TYPE.get(raw.get("demand_type", ""))
        if semantic_type is not None:
            facts["goal"] = ProtectedFact(
                key="goal", value=raw["goal"], source="Demand.goal",
                semantic_type=semantic_type, authority=FactAuthority.CANONICAL,
                usage=FactUsage.RENDERABLE, confirmed=True,
            )
        # else: demand_type isn't in the known table, so we cannot state what
        # business predicate "Goal" represents for it — fail closed at the
        # source by not creating the fact at all, rather than guessing. Any
        # template referencing {{goal}} for this Demand will be rejected
        # downstream as an unknown_fact_key, same as any other missing slot.

    return ProtectedDemandFacts(demand_id=demand_id, facts=facts)


if __name__ == "__main__":
    demand = {
        "Domain": "general",
        "Demand Type": "recruitment",
        "Demand Title": "דרישה למתקינים",
        "Target Audience": "ניסיון 3+ שנים",
        "Location": "בית שמש",
        "Goal": "10 מועמדים תוך שבוע",
        "Constraints": "מיקום נגיש לנכים",
    }

    pdf = extract_protected_facts("recDemo1", demand)
    assert pdf.facts["goal"].value == "10 מועמדים תוך שבוע"
    assert pdf.facts["goal"].semantic_type == SemanticType.RECRUITMENT_GOAL
    assert pdf.facts["goal"].usage is FactUsage.RENDERABLE
    assert pdf.facts["constraints"].usage is FactUsage.INSTRUCTION_ONLY
    assert pdf.facts["domain"].usage is FactUsage.ROUTING_ONLY
    assert pdf.facts["demand_type"].usage is FactUsage.ROUTING_ONLY
    assert all(f.authority is FactAuthority.CANONICAL for f in pdf.facts.values())

    renderable = pdf.renderable()
    assert "goal" in renderable and "location" in renderable and "audience" in renderable
    assert "constraints" not in renderable
    assert "domain" not in renderable and "demand_type" not in renderable

    # unrecognized demand_type -> no goal fact at all (fail closed at source)
    bad = dict(demand, **{"Demand Type": "not_a_real_type"})
    pdf_bad = extract_protected_facts("recDemo2", bad)
    assert "goal" not in pdf_bad.facts

    # semantic_type varies by demand_type for the same generic Goal field
    furniture = dict(demand, **{"Demand Type": "furniture_import", "Goal": "מכירת 20 יחידות"})
    pdf_furniture = extract_protected_facts("recDemo3", furniture)
    assert pdf_furniture.facts["goal"].semantic_type == SemanticType.SALES_GOAL

    print("marketing_fact_authority.py self-test OK")
