# marketing_fact_authority.py — F23 BOSS Marketing Bridge / BUG-164 Authority
# Foundation (PR1 of 3 — see BUG_AUDIT_LOG.md BUG-164 for the full design
# history; this file implements the "FINAL AUTHORITY REDESIGN" contract plus
# the "FINAL CORRECTION PASS" structural review).
#
# Pure, deterministic. No Airtable I/O, no AI call. Defines ProtectedFact —
# the only shape a fact is allowed to take before it can reach
# marketing_creative_renderer.py's authority_filter_and_render(). Every fact
# carries three independent pieces of metadata, on purpose kept separate:
#
#   authority  — who owns this value (CANONICAL/DETERMINISTIC/CANDIDATE).
#                Canonical authority does NOT by itself mean the value may be
#                published — see `usage` below. PR1/PR2 render authority is
#                further restricted to CANONICAL only (see
#                marketing_creative_renderer.py) — DETERMINISTIC/CANDIDATE
#                remain governance concepts this enum supports for future
#                work, but nothing here produces them yet and nothing
#                downstream accepts them as renderable yet.
#   usage      — whether this fact may ever appear as rendered copy at all.
#                Constraints is canonical business truth but is an
#                INSTRUCTION to the copy, not something to quote verbatim.
#                Domain/Demand Type are canonical but exist for routing only.
#                Topic (Demand Title) is a system-composed internal record
#                label (see _materialize_demand_fields/cmd_marketing.py — it's
#                built from the demand-type label + location, and in practice
#                can carry internal/test annotations) — not proven to always
#                be publishable business copy, so it is ROUTING_ONLY, not
#                RENDERABLE, until a creation path guarantees otherwise.
#   semantic_type — the business predicate this value's meaning is pinned
#                to. Prevents a deterministically-extracted value from being
#                reattached to a different meaning than its source (BUG-164's
#                actual failure mode: "10" staying "10" while its meaning
#                silently changed from "candidates wanted" to "open roles").
#                Audience and Location are NOT one global predicate: per the
#                live intake mapping in cmd_marketing.py::_materialize_
#                demand_fields(), the same "Target Audience"/"Location"
#                Airtable fields carry a different real-world meaning per
#                demand_type (e.g. recruitment's "audience" is role/
#                experience requirements; real_estate_listing's "audience" is
#                literally labeled "פרטי הנכס:" — property details). Their
#                semantic_type is therefore resolved per demand_type, exactly
#                like Goal already was.
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

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType

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
    TOPIC_TITLE = "topic_title"                # Demand Title -- internal record label, not copy
    CONSTRAINTS_TEXT = "constraints_text"
    ROUTING_DOMAIN = "routing_domain"
    ROUTING_DEMAND_TYPE = "routing_demand_type"

    # Goal -- one generic Airtable field, meaning resolved per demand_type.
    RECRUITMENT_GOAL = "recruitment_goal"
    SALES_GOAL = "sales_goal"
    LISTING_GOAL = "listing_goal"
    SERVICE_GOAL = "service_goal"

    # Target Audience -- one generic Airtable field, meaning resolved per
    # demand_type per the live cmd_marketing.py::_materialize_demand_fields()
    # intake mapping (not invented from this file):
    #   recruitment          -> role_experience   (role/requirements sought)
    #   furniture_import     -> product_category  (product/category context)
    #   fiber_equipment      -> equipment_project  (equipment/project context)
    #   real_estate_listing  -> "פרטי הנכס: {property_type_rooms}" (property details)
    #   service              -> service_type       (service type/context)
    RECRUITMENT_ROLE_REQUIREMENTS = "recruitment_role_requirements"
    FURNITURE_PRODUCT_CATEGORY = "furniture_product_category"
    FIBER_EQUIPMENT_PROJECT_CONTEXT = "fiber_equipment_project_context"
    LISTING_PROPERTY_DETAILS = "listing_property_details"
    SERVICE_TYPE_CONTEXT = "service_type_context"

    # Location -- one generic Airtable field, meaning resolved per
    # demand_type per the same live intake mapping:
    #   recruitment          -> area              (work area)
    #   furniture_import     -> sales_area         (sales/delivery area)
    #   fiber_equipment      -> project_area        (project area)
    #   real_estate_listing  -> property_location   (property location)
    #   service              -> service_area        (service area)
    RECRUITMENT_WORK_AREA = "recruitment_work_area"
    FURNITURE_SALES_AREA = "furniture_sales_area"
    FIBER_PROJECT_AREA = "fiber_project_area"
    LISTING_PROPERTY_LOCATION = "listing_property_location"
    SERVICE_AREA = "service_area"


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
    facts: dict[str, ProtectedFact] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Immutable after construction: facts is exposed only as a read-only
        # mapping view, so no caller can mutate a Demand's protected fact set
        # in place once extract_protected_facts() has built it.
        object.__setattr__(self, "facts", MappingProxyType(dict(self.facts)))

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
    "topic": (SemanticType.TOPIC_TITLE, FactUsage.ROUTING_ONLY),
    "constraints": (SemanticType.CONSTRAINTS_TEXT, FactUsage.INSTRUCTION_ONLY),
    "domain": (SemanticType.ROUTING_DOMAIN, FactUsage.ROUTING_ONLY),
    "demand_type": (SemanticType.ROUTING_DEMAND_TYPE, FactUsage.ROUTING_ONLY),
}

# Slots whose semantic meaning must be resolved per demand_type (same
# generic Airtable field reused with a different real-world meaning each
# time). Keys must match marketing_domain_profiles.PROFILES. Unrecognized
# demand_type -> no fact created for that slot at all (fail closed at the
# source, same as the rest of this module) rather than guessing.
_GOAL_SEMANTICS_BY_DEMAND_TYPE: dict[str, SemanticType] = {
    "recruitment": SemanticType.RECRUITMENT_GOAL,
    "furniture_import": SemanticType.SALES_GOAL,
    "fiber_equipment": SemanticType.SALES_GOAL,
    "real_estate_listing": SemanticType.LISTING_GOAL,
    "service": SemanticType.SERVICE_GOAL,
}
_AUDIENCE_SEMANTICS_BY_DEMAND_TYPE: dict[str, SemanticType] = {
    "recruitment": SemanticType.RECRUITMENT_ROLE_REQUIREMENTS,
    "furniture_import": SemanticType.FURNITURE_PRODUCT_CATEGORY,
    "fiber_equipment": SemanticType.FIBER_EQUIPMENT_PROJECT_CONTEXT,
    "real_estate_listing": SemanticType.LISTING_PROPERTY_DETAILS,
    "service": SemanticType.SERVICE_TYPE_CONTEXT,
}
_LOCATION_SEMANTICS_BY_DEMAND_TYPE: dict[str, SemanticType] = {
    "recruitment": SemanticType.RECRUITMENT_WORK_AREA,
    "furniture_import": SemanticType.FURNITURE_SALES_AREA,
    "fiber_equipment": SemanticType.FIBER_PROJECT_AREA,
    "real_estate_listing": SemanticType.LISTING_PROPERTY_LOCATION,
    "service": SemanticType.SERVICE_AREA,
}

# key -> (per-demand_type semantic map) for the three demand-type-resolved slots.
_RESOLVED_SLOT_TABLES: dict[str, dict[str, SemanticType]] = {
    "goal": _GOAL_SEMANTICS_BY_DEMAND_TYPE,
    "audience": _AUDIENCE_SEMANTICS_BY_DEMAND_TYPE,
    "location": _LOCATION_SEMANTICS_BY_DEMAND_TYPE,
}


def extract_protected_facts(demand_id: str, demand: dict) -> ProtectedDemandFacts:
    """
    Pure. Builds the canonical-tier ProtectedFact set for one Demand record.
    """
    raw = protected_demand_fields(demand)
    demand_type = raw.get("demand_type", "")
    facts: dict[str, ProtectedFact] = {}

    for key, (semantic_type, usage) in _FIXED_SLOT_SEMANTICS.items():
        if raw.get(key):
            facts[key] = ProtectedFact(
                key=key, value=raw[key], source=f"Demand.{key}",
                semantic_type=semantic_type, authority=FactAuthority.CANONICAL,
                usage=usage, confirmed=True,
            )

    for key, table in _RESOLVED_SLOT_TABLES.items():
        if not raw.get(key):
            continue
        semantic_type = table.get(demand_type)
        if semantic_type is None:
            # demand_type isn't in the known table, so we cannot state what
            # business predicate this slot represents for it -- fail closed
            # at the source by not creating the fact at all, rather than
            # guessing. Any template referencing {{key}} for this Demand is
            # rejected downstream as an unknown_fact_key/disallowed_fact,
            # same as any other missing slot.
            continue
        facts[key] = ProtectedFact(
            key=key, value=raw[key], source=f"Demand.{key}",
            semantic_type=semantic_type, authority=FactAuthority.CANONICAL,
            usage=FactUsage.RENDERABLE, confirmed=True,
        )

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
    assert pdf.facts["audience"].semantic_type == SemanticType.RECRUITMENT_ROLE_REQUIREMENTS
    assert pdf.facts["location"].semantic_type == SemanticType.RECRUITMENT_WORK_AREA
    assert pdf.facts["topic"].usage is FactUsage.ROUTING_ONLY
    assert pdf.facts["constraints"].usage is FactUsage.INSTRUCTION_ONLY
    assert pdf.facts["domain"].usage is FactUsage.ROUTING_ONLY
    assert pdf.facts["demand_type"].usage is FactUsage.ROUTING_ONLY
    assert all(f.authority is FactAuthority.CANONICAL for f in pdf.facts.values())

    renderable = pdf.renderable()
    assert "goal" in renderable and "location" in renderable and "audience" in renderable
    assert "topic" not in renderable  # ROUTING_ONLY, not publishable copy
    assert "constraints" not in renderable
    assert "domain" not in renderable and "demand_type" not in renderable

    # unrecognized demand_type -> no goal/audience/location fact at all
    # (fail closed at the source for every demand-type-resolved slot, not
    # just goal)
    bad = dict(demand, **{"Demand Type": "not_a_real_type"})
    pdf_bad = extract_protected_facts("recDemo2", bad)
    assert "goal" not in pdf_bad.facts
    assert "audience" not in pdf_bad.facts
    assert "location" not in pdf_bad.facts
    assert "topic" in pdf_bad.facts  # demand-type-invariant slot, unaffected

    # semantic_type varies by demand_type for the same generic Goal/Audience/
    # Location fields
    furniture = dict(demand, **{"Demand Type": "furniture_import", "Goal": "מכירת 20 יחידות"})
    pdf_furniture = extract_protected_facts("recDemo3", furniture)
    assert pdf_furniture.facts["goal"].semantic_type == SemanticType.SALES_GOAL
    assert pdf_furniture.facts["audience"].semantic_type == SemanticType.FURNITURE_PRODUCT_CATEGORY
    assert pdf_furniture.facts["location"].semantic_type == SemanticType.FURNITURE_SALES_AREA

    # immutability: facts cannot be mutated after construction
    try:
        pdf.facts["injected"] = pdf.facts["goal"]
        raise AssertionError("expected TypeError on mutation")
    except TypeError:
        pass

    print("marketing_fact_authority.py self-test OK")
