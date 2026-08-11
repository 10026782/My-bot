# marketing_gateway.py — F23 BOSS Marketing Bridge (M1)
#
# Thin wrapper over tools/airtable_gateway.py for the 3 new Marketing tables
# plus Marketing Rules (stored in the existing Business Memory table). Mirrors
# media_gateway.py's shape exactly: dataclass -> fields dict -> single gateway
# call. All writes go through tools/airtable_gateway.py — never call httpx
# directly here. Called by cmd_marketing.py (a direct command handler, not an
# agent-invoked dispatcher tool — see the M1 spec's Canonical Reuse Gate).

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from airtable_schema import (
    BusinessMemoryFields as BMF,
    MarketingCreativesFields as MCF,
    MarketingDemandFields as MDF,
    MarketingDemandStage,
    MarketingPublicationFields as MPF,
    Tables,
)
from tools.airtable_gateway import airtable_create, airtable_patch, at_list_by_formula, _safe_formula_param

logger = logging.getLogger(__name__)

_MARKETING_RULE_PREFIX = "[Marketing Rule]"


# ══════════════════════════════════════════════════
# Marketing Demand
# ══════════════════════════════════════════════════

@dataclass
class DemandRecord:
    title: str
    domain: str            # one of identity.Domain's canonical values (see domain_utils.py)
    demand_type: str        # one of marketing_domain_profiles.PROFILES keys
    target_audience: str = ""
    location: str = ""
    goal: str = ""
    constraints: str = ""
    next_action: str = ""
    status: str = "Active"


def create_demand(demand: DemandRecord) -> str | None:
    fields = {
        MDF.NAME: demand.title,
        MDF.DOMAIN: demand.domain,
        MDF.DEMAND_TYPE: demand.demand_type,
        MDF.CURRENT_STAGE: MarketingDemandStage.INTAKE,
        MDF.STATUS: demand.status,
    }
    if demand.target_audience:
        fields[MDF.TARGET_AUDIENCE] = demand.target_audience
    if demand.location:
        fields[MDF.LOCATION] = demand.location
    if demand.goal:
        fields[MDF.GOAL] = demand.goal
    if demand.constraints:
        fields[MDF.CONSTRAINTS] = demand.constraints
    if demand.next_action:
        fields[MDF.NEXT_ACTION] = demand.next_action

    record = airtable_create(Tables.MARKETING_DEMAND, fields, source="marketing_gateway")
    if not record:
        logger.warning("[marketing_gateway] create_demand failed for title=%s", demand.title)
        return None
    return record.get("id")


def update_demand_stage(demand_id: str, stage: str, next_action: str = "") -> bool:
    fields: dict = {MDF.CURRENT_STAGE: stage}
    if next_action:
        fields[MDF.NEXT_ACTION] = next_action
    return airtable_patch(Tables.MARKETING_DEMAND, demand_id, fields, source="marketing_gateway")


def _get_by_id(table: str, record_id: str) -> dict | None:
    """
    Read-only. tools/airtable_gateway.py has no generic GET-by-record-id
    helper (only at_get_by_field/at_list_by_formula), so this uses Airtable's
    RECORD_ID() formula function through the existing at_list_by_formula
    read path rather than adding a new HTTP call outside the gateway.
    """
    try:
        records = at_list_by_formula(
            table, f"RECORD_ID()='{_safe_formula_param(record_id)}'", max_records=1,
        )
    except Exception as e:
        logger.warning("[marketing_gateway] _get_by_id(%s, %s) failed: %s", table, record_id, e)
        return None
    return records[0] if records else None


def get_demand(demand_id: str) -> dict | None:
    """Returns the Demand record's `fields` dict, or None if not found/error."""
    record = _get_by_id(Tables.MARKETING_DEMAND, demand_id)
    return record.get("fields") if record else None


def get_creative(creative_id: str) -> dict | None:
    """Returns the Creative record's `fields` dict, or None if not found/error."""
    record = _get_by_id(Tables.MARKETING_CREATIVES, creative_id)
    return record.get("fields") if record else None


# ══════════════════════════════════════════════════
# Marketing Creatives
# ══════════════════════════════════════════════════

def save_creative_ideas(
    demand_id: str,
    title: str,
    idea1: str,
    idea2: str,
    idea3: str,
    brief_used: str = "",
) -> str | None:
    fields = {
        MCF.NAME: title,
        MCF.LINKED_DEMAND: [demand_id],
        MCF.IDEA_1: idea1,
        MCF.IDEA_2: idea2,
        MCF.IDEA_3: idea3,
        MCF.SELECTION_STATUS: "Pending Review",
    }
    if brief_used:
        fields[MCF.BRIEF_USED] = brief_used

    record = airtable_create(Tables.MARKETING_CREATIVES, fields, source="marketing_gateway")
    if not record:
        logger.warning("[marketing_gateway] save_creative_ideas failed for demand_id=%s", demand_id)
        return None
    creative_id = record.get("id")
    if not update_demand_stage(demand_id, MarketingDemandStage.IDEAS_GENERATED):
        logger.warning(
            "[marketing_gateway] creative_id=%s saved but demand_id=%s stage update to "
            "IDEAS_GENERATED failed — Current Stage is now stale, fix manually in Airtable",
            creative_id, demand_id,
        )
    return creative_id


def select_creative(creative_id: str, selected_idea: str, reviewer_notes: str = "") -> bool:
    """selected_idea: one of 'Idea 1' | 'Idea 2' | 'Idea 3' | 'None'."""
    fields = {
        MCF.SELECTED_IDEA: selected_idea,
        MCF.SELECTION_STATUS: "Rejected All" if selected_idea == "None" else "Selected",
    }
    if reviewer_notes:
        fields[MCF.REVIEWER_NOTES] = reviewer_notes
    return airtable_patch(Tables.MARKETING_CREATIVES, creative_id, fields, source="marketing_gateway")


def save_production_handoff(creative_id: str, handoff_text: str) -> bool:
    return airtable_patch(
        Tables.MARKETING_CREATIVES, creative_id,
        {MCF.PRODUCTION_HANDOFF: handoff_text}, source="marketing_gateway",
    )


# ══════════════════════════════════════════════════
# Marketing Publications
# ══════════════════════════════════════════════════

@dataclass
class PublicationRecord:
    title: str
    demand_id: str
    source_code: str
    asset_id: str = ""
    channel_id: str = ""
    published_at: str = ""     # ISO date
    responses: int = 0
    qualified_responses: int = 0
    passed_forward: int = 0
    spend: float = 0
    notes: str = ""


def record_publication(pub: PublicationRecord) -> str | None:
    fields: dict = {
        MPF.NAME: pub.title,
        MPF.DEMAND: [pub.demand_id],
        MPF.SOURCE_CODE: pub.source_code,
    }
    if pub.asset_id:
        fields[MPF.ASSET] = [pub.asset_id]
    if pub.channel_id:
        fields[MPF.CHANNEL] = [pub.channel_id]
    if pub.published_at:
        fields[MPF.PUBLISHED_AT] = pub.published_at
    if pub.responses:
        fields[MPF.RESPONSES] = pub.responses
    if pub.qualified_responses:
        fields[MPF.QUALIFIED_RESPONSES] = pub.qualified_responses
    if pub.passed_forward:
        fields[MPF.PASSED_FORWARD] = pub.passed_forward
    if pub.spend:
        fields[MPF.SPEND] = pub.spend
    if pub.notes:
        fields[MPF.NOTES] = pub.notes

    record = airtable_create(Tables.MARKETING_PUBLICATIONS, fields, source="marketing_gateway")
    if not record:
        logger.warning("[marketing_gateway] record_publication failed for demand_id=%s", pub.demand_id)
        return None
    publication_id = record.get("id")
    if not update_demand_stage(pub.demand_id, MarketingDemandStage.PUBLISHED):
        logger.warning(
            "[marketing_gateway] publication_id=%s saved but demand_id=%s stage update to "
            "PUBLISHED failed — Current Stage is now stale, fix manually in Airtable",
            publication_id, pub.demand_id,
        )
    return publication_id


# ══════════════════════════════════════════════════
# Marketing Rules — stored in the existing Business Memory table.
# Event Type="Other" (no dedicated enum value exists — do not invent one,
# see the M1 spec's decision on this). Distinguished from other Business
# Memory entries by a "[Marketing Rule]" title prefix, the same ad-hoc
# tagging convention already used elsewhere in this codebase (e.g. the
# "[TMA] venture_create" style entries in Interaction Log) — chosen instead
# of a new Tags choice because the Airtable MCP tooling available here
# cannot add a choice to an existing select field without touching the
# field's other live options.
#
# Domain resolution goes through domain_utils.py (canonical business-domain
# adapter) rather than cmd_update.resolve_business_memory_domain()'s live
# RuntimeSchemaProvider lookup — domain_utils is the deliberately-built
# canonical layer for exactly this cross-table Domain-vocabulary problem.
# ══════════════════════════════════════════════════

def save_marketing_rule(domain: str, rule_text: str, created_by: str = "marketing_gateway") -> str | None:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from domain_utils import UnknownBusinessDomain, business_domain_to_airtable

    try:
        airtable_domain = business_domain_to_airtable(domain, vocabulary="business_memory_legacy")
    except UnknownBusinessDomain as e:
        logger.error("[marketing_gateway] save_marketing_rule: domain resolution failed: %s", e)
        return None

    fields = {
        BMF.TITLE: f"{_MARKETING_RULE_PREFIX} {rule_text[:60]}",
        BMF.DESCRIPTION: rule_text,
        BMF.DATE: datetime.now(ZoneInfo("Asia/Jerusalem")).date().isoformat(),
        BMF.EVENT_TYPE: "Other",
        BMF.IMPACT: "Marketing Rule",
        BMF.DOMAIN: airtable_domain,
    }
    record = airtable_create(Tables.BUSINESS_MEMORY, fields, source=f"marketing_gateway:{created_by}")
    if not record:
        logger.warning("[marketing_gateway] save_marketing_rule failed for domain=%s", domain)
        return None
    return record.get("id")


def get_marketing_rules(domain: str, limit: int = 20) -> str:
    """
    Read-only. Returns the concatenated Description text of every
    "[Marketing Rule]"-prefixed Business Memory record for this domain
    (plus domain-less/General rules), newest first. Empty string on any
    failure or no matches — never raises, matches marketing_brief_composer's
    expectation of a plain (possibly empty) domain_rules string.
    """
    from domain_utils import UnknownBusinessDomain, business_domain_to_airtable

    domain_clause = ""
    try:
        airtable_domain = business_domain_to_airtable(domain, vocabulary="business_memory_legacy")
        v = _safe_formula_param(airtable_domain)
        domain_clause = f"OR({{{BMF.DOMAIN}}}='{v}', {{{BMF.DOMAIN}}}='General'),"
    except UnknownBusinessDomain:
        pass

    formula = f"AND({domain_clause}SEARCH('{_safe_formula_param(_MARKETING_RULE_PREFIX)}', {{{BMF.TITLE}}}))"

    try:
        records = at_list_by_formula(Tables.BUSINESS_MEMORY, formula, max_records=limit)
    except Exception as e:
        logger.warning("[marketing_gateway] get_marketing_rules failed for domain=%s: %s", domain, e)
        return ""

    texts = [r.get("fields", {}).get(BMF.DESCRIPTION, "") for r in records]
    return "\n".join(t for t in texts if t)


if __name__ == "__main__":
    demand = DemandRecord(
        title="test demand", domain="general", demand_type="recruitment",
    )
    assert demand.status == "Active"

    pub = PublicationRecord(title="test pub", demand_id="recABC", source_code="GENERAL-recABC-TELEGRAM-01")
    assert pub.responses == 0

    print("marketing_gateway.py self-test OK")
