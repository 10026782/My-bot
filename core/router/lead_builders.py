"""Deterministic lead proposal builders for WS1/TC4.

Mirrors ``core/router/task_builders.py``'s TC2 pattern exactly: builders
validate and name a proposed action, they never execute it. Only
``CreateLeadBuilder``/``UpdateLeadBuilder`` exist, matching
``docs/architecture/turn-coordinator-full/CANONICAL_BUILDERS_PLAN.md`` --
leads have no "complete" concept analogous to tasks (status/outcome
transitions are just an update).

This module is pure and unwired: it is not called from ``app.py`` or
``core/turn_coordinator_runtime.py``. It does not touch
``core/lead_candidate_handler.py``'s live Tier-1/2/3 capture path or
``FEATURE_AUTO_CAPTURE`` -- wiring these builders into a real intent-ownership
registry and a bounded Airtable lookup (mirroring
``core/turn_coordinator_runtime.py::airtable_task_lookup``) is a later,
separate integration seam, not part of TC4.
"""

from __future__ import annotations

from collections.abc import Mapping

from airtable_schema import LeadFields, Tables
from core.router.ownership_contracts import CanonicalActionProposal
from core.router.route_decision import Intent, Risk

_LEAD_WRITE_FIELDS = frozenset({
    LeadFields.NAME,
    LeadFields.PHONE,
    LeadFields.STATUS,
    LeadFields.SCORE,
    LeadFields.TIER,
    LeadFields.SUMMARY,
    LeadFields.SOURCE,
    LeadFields.CHANNEL,
    LeadFields.DOMAIN,
    LeadFields.OUTCOME,
    LeadFields.NEXT_FOLLOWUP,
    LeadFields.OWNER,
    LeadFields.NEXT_STEP,
})


def _require_text(value: str, field_name: str) -> str:
    value = str(value or "").strip()
    if not value:
        raise ValueError(f"{field_name} is required")
    return value


def _proposal(intent: str, tool: str, fields: Mapping[str, object]) -> CanonicalActionProposal:
    return CanonicalActionProposal(
        intent=intent,
        canonical_tool=tool,
        resource=Tables.LEADS,
        fields=dict(fields),
        risk=Risk.NEEDS_APPROVAL,
        approval_required=True,
        evidence_requirement="lead_write",
        reply_policy="gateway",
    )


def build_create_lead_proposal(name: str, **fields: object) -> CanonicalActionProposal:
    """Build a complete named lead-create proposal from deterministic input.

    ``approval_required`` is always ``True`` here -- the actual capture-tier
    policy (``FEATURE_AUTO_CAPTURE``, Tier 1/2 auto-write) lives in
    ``core/lead_candidate_handler.py`` and is not reproduced or overridden by
    this unwired builder; a safe, conservative default is used instead of
    inferring capture policy this module has no access to.
    """
    normalized_name = _require_text(name, "name")
    if LeadFields.NAME in fields:
        raise ValueError("name must be supplied as the named name argument")
    unknown = set(fields) - _LEAD_WRITE_FIELDS
    if unknown:
        raise ValueError(f"unsupported lead fields: {sorted(unknown)}")
    return _proposal(
        Intent.CREATE_LEAD,
        "lead_create",
        {LeadFields.NAME: normalized_name, **fields},
    )


def build_update_lead_proposal(record_id: str, **fields: object) -> CanonicalActionProposal:
    """Build an update proposal for one already-resolved lead record."""
    record_id = _require_text(record_id, "record_id")
    if not fields:
        raise ValueError("at least one lead field is required")
    unknown = set(fields) - _LEAD_WRITE_FIELDS
    if unknown:
        raise ValueError(f"unsupported lead fields: {sorted(unknown)}")
    return _proposal(
        Intent.UPDATE_LEAD,
        "lead_update",
        {"record_id": record_id, **fields},
    )
