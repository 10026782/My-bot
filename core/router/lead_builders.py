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

CANONICAL_BUILDERS_PLAN.md's CreateLeadBuilder row requires more than a name:
"identity scope + lead fields" (required), "capture policy; write evidence"
(approval/evidence), and "invalid/duplicate identity" (clarification/
failure). ``build_create_lead_proposal`` therefore requires three explicit,
caller-supplied preconditions -- ``scope``, ``capture_policy``, and
``identity_precondition`` -- none of them defaulted, so a caller cannot
silently obtain a valid, approved-by-default proposal the way an earlier
version of this module allowed. This module performs no lookup and reads no
flag itself: every precondition is asserted by the caller, not computed
here.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

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


class CapturePolicy:
    """The explicit, already-resolved capture-policy outcomes TC4 consumes
    for a lead-create proposal. This is TC4's own outcome vocabulary, not a
    verbatim mirror of ``feature_flags.py``'s ``FEATURE_AUTO_CAPTURE`` flag
    -- this module never reads that flag or reproduces its tiering logic; a
    caller resolves the real-world policy elsewhere and declares the result
    here. Only ``AUTO_WRITE`` and ``PREVIEW_REQUIRED`` can ever produce a
    ``CanonicalActionProposal``; ``NEEDS_REVIEW`` is a decision this builder
    is not authorized to turn into a write proposal at all -- it fails
    closed instead of ever being interpreted as an approval requirement.
    """

    AUTO_WRITE = "auto_write"              # deterministic write, no approval gate
    PREVIEW_REQUIRED = "preview_required"  # write proposal requires approval
    NEEDS_REVIEW = "needs_review"          # not TC4's to decide -- no proposal at all

    ALL = frozenset({AUTO_WRITE, PREVIEW_REQUIRED, NEEDS_REVIEW})


_CAPTURE_POLICY_APPROVAL_REQUIRED = {
    CapturePolicy.AUTO_WRITE: False,
    CapturePolicy.PREVIEW_REQUIRED: True,
}


@dataclass(frozen=True)
class LeadIdentityPrecondition:
    """An already-decided identity validity/duplicate check for lead
    creation, injected by the caller -- this module performs no lookup
    itself (no Airtable/resolver call). ``valid`` and ``is_duplicate`` both
    have no default: a caller must explicitly assert both, so an unasserted
    precondition cannot silently pass. ``valid=False`` or
    ``is_duplicate=True`` fails closed before any proposal is built.

    A future integration step may populate this from TC5's ``resolve_lead``
    (``core/router/entity_resolvers.py``) against phone/name -- that wiring
    is outside TC4's scope; this contract only consumes the result.
    """

    valid: bool = field(kw_only=True)
    is_duplicate: bool = field(kw_only=True)

    def __post_init__(self) -> None:
        if not isinstance(self.valid, bool):
            raise TypeError("valid must be an explicit bool")
        if not isinstance(self.is_duplicate, bool):
            raise TypeError("is_duplicate must be an explicit bool")


def _require_text(value: str, field_name: str) -> str:
    value = str(value or "").strip()
    if not value:
        raise ValueError(f"{field_name} is required")
    return value


def _proposal(
    intent: str, tool: str, fields: Mapping[str, object], *, approval_required: bool,
) -> CanonicalActionProposal:
    return CanonicalActionProposal(
        intent=intent,
        canonical_tool=tool,
        resource=Tables.LEADS,
        fields=dict(fields),
        risk=Risk.NEEDS_APPROVAL if approval_required else Risk.NORMAL,
        approval_required=approval_required,
        evidence_requirement="lead_write",
        reply_policy="gateway",
    )


def build_create_lead_proposal(
    name: str,
    *,
    scope: str,
    capture_policy: str,
    identity_precondition: LeadIdentityPrecondition,
    **fields: object,
) -> CanonicalActionProposal:
    """Build a complete named lead-create proposal from deterministic input.

    Fails closed, before any proposal is built, when: ``scope`` is missing
    (identity scope is required, CANONICAL_BUILDERS_PLAN.md);
    ``capture_policy`` is missing, not one of ``CapturePolicy.ALL``, or is
    ``CapturePolicy.NEEDS_REVIEW`` (that outcome is never turned into a
    write proposal by this builder -- approval must be explicit, never
    silently defaulted or inferred); or ``identity_precondition`` says the
    identity is invalid or a known duplicate.
    """
    if not scope or not str(scope).strip():
        raise ValueError("scope is required")
    if capture_policy not in CapturePolicy.ALL:
        raise ValueError(
            f"capture_policy must be one of {sorted(CapturePolicy.ALL)}, got {capture_policy!r}"
        )
    if capture_policy == CapturePolicy.NEEDS_REVIEW:
        raise ValueError(
            "capture_policy=needs_review cannot produce a canonical lead-create "
            "proposal -- this outcome requires review outside TC4's scope"
        )
    if not identity_precondition.valid:
        raise ValueError("lead creation requires a valid identity")
    if identity_precondition.is_duplicate:
        raise ValueError("lead creation rejected: identity is a known duplicate")

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
        approval_required=_CAPTURE_POLICY_APPROVAL_REQUIRED[capture_policy],
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
        approval_required=True,
    )
