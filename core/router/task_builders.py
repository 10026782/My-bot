"""Deterministic task proposal builders for WS1/TC2.

Builders validate and name a proposed action.  They never execute it.
"""

from __future__ import annotations

from collections.abc import Mapping

from airtable_schema import Tables, TaskFields
from core.router.ownership_contracts import CanonicalActionProposal
from core.router.route_decision import Intent, Risk


_TASK_WRITE_FIELDS = frozenset({
    TaskFields.NAME,
    TaskFields.DESCRIPTION,
    TaskFields.DUE_DATE,
    TaskFields.STATUS,
    TaskFields.CONTACTS_LINK,
    TaskFields.DEALS_LINK,
    TaskFields.DOMAIN,
    TaskFields.OWNER,
    TaskFields.LEAD_LINK,
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
        resource=Tables.TASKS,
        fields=dict(fields),
        risk=Risk.NEEDS_APPROVAL,
        approval_required=True,
        evidence_requirement="task_write",
        reply_policy="gateway",
    )


def build_create_task_proposal(
    title: str, identity=None, **fields: object
) -> CanonicalActionProposal:
    """Build a complete named task-create proposal from deterministic input.

    If identity is provided and OWNER is not already set, auto-populate from identity.user_id.
    """
    normalized_title = _require_text(title, "title")
    if TaskFields.NAME in fields:
        raise ValueError("title must be supplied as the named title argument")
    unknown = set(fields) - _TASK_WRITE_FIELDS
    if unknown:
        raise ValueError(f"unsupported task fields: {sorted(unknown)}")

    final_fields = {TaskFields.NAME: normalized_title, **fields}

    # Auto-populate OWNER from identity if not already set
    if identity is not None and TaskFields.OWNER not in final_fields:
        user_id = getattr(identity, "user_id", None)
        if user_id:
            final_fields[TaskFields.OWNER] = user_id

    return _proposal(
        Intent.CREATE_TASK,
        "task_create",
        final_fields,
    )


def build_update_task_proposal(record_id: str, **fields: object) -> CanonicalActionProposal:
    """Build an update proposal for one already-resolved task record."""
    record_id = _require_text(record_id, "record_id")
    if not fields:
        raise ValueError("at least one task field is required")
    unknown = set(fields) - _TASK_WRITE_FIELDS
    if unknown:
        raise ValueError(f"unsupported task fields: {sorted(unknown)}")
    return _proposal(
        Intent.UPDATE_TASK,
        "task_update",
        {"record_id": record_id, **fields},
    )


def build_complete_task_proposal(record_id: str) -> CanonicalActionProposal:
    """Build the canonical completion proposal for one resolved task."""
    record_id = _require_text(record_id, "record_id")
    return _proposal(
        Intent.COMPLETE_TASK,
        "task_complete",
        {"record_id": record_id, TaskFields.STATUS: "בוצע"},
    )
