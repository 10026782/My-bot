# core/approvals_projection.py — Phase 4B-2 (schema-prep stage)
#
# Pure, side-effect-free mapping between the canonical ActionContract
# lifecycle (ActionContractStatus, airtable_schema.py) and the Approvals
# display projection (ProjectedLifecycleStatus, airtable_schema.py). No
# Airtable I/O, no PostgreSQL access, no imports of tma_api.py.
#
# EXISTS_UNWIRED: nothing here is called by any live path yet. tma_api.py's
# _queue_tma_write_approval()/_claim_and_execute_approval() are unchanged in
# this stage — they still write/read Approvals directly, with no
# action_contract_id and no PostgreSQL claim. Wiring those functions to this
# module (and to core.action_gateway/core.atomic_claim_repository) is the
# Phase 4B wiring stage, tracked separately from this schema-prep stage.
#
# Authority split (Phase 4B-2 audit, §A.0):
#   ActionContracts (Airtable) — canonical contract + lifecycle/audit truth.
#   PostgreSQL action_execution_claims — execution ownership/claim, the only
#     primitive that may authorize a single execution.
#   Approvals (Airtable) — non-authoritative TMA projection/read model only.
# Nothing in this module may be used, directly or indirectly, to authorize a
# claim or an execution. It answers exactly two questions: "what should the
# TMA display for this canonical status?" and "is this row eligible for an
# owner-approval action, given its canonical approval_policy?" — the answer
# to the second question is advisory for a future wiring stage, not an
# execution gate in itself.

from __future__ import annotations

from airtable_schema import ProjectedLifecycleStatus
from core.action_gateway import APPROVAL_POLICY_APPROVAL, APPROVAL_POLICY_SELF_CONFIRM

# ActionContractStatus values (airtable_schema.py) -> ProjectedLifecycleStatus
# bucket. "draft" maps into the same display bucket as "pending" — it is
# still shown in history/audit views — but is deliberately excluded from the
# owner-approval pending list (see is_pending_list_visible()) because a draft
# may be a self_confirm proposal, confirmed by the requester through a
# separate free-text flow, not the Approvals TMA screen.
_CONTRACT_STATUS_TO_PROJECTION: dict[str, str] = {
    "draft":           ProjectedLifecycleStatus.PENDING,
    "pending":         ProjectedLifecycleStatus.PENDING,
    "approved":        ProjectedLifecycleStatus.APPROVED,
    "executing":       ProjectedLifecycleStatus.EXECUTING,
    "completed":       ProjectedLifecycleStatus.COMPLETED,
    "failed":          ProjectedLifecycleStatus.FAILED,
    "outcome_unknown": ProjectedLifecycleStatus.OUTCOME_UNKNOWN,
    "rejected":        ProjectedLifecycleStatus.REJECTED,
    "superseded":      ProjectedLifecycleStatus.SUPERSEDED,
    "executed":        ProjectedLifecycleStatus.LEGACY,  # legacy compat value; RAM-only path may still emit it
}

# No outgoing transition in ALLOWED_CONTRACT_TRANSITIONS
# (core/action_contract_repository.py) — terminal for display/audit purposes.
TERMINAL_CONTRACT_STATUSES: frozenset[str] = frozenset({
    "completed", "failed", "outcome_unknown", "rejected", "superseded", "executed",
})

# Terminal but intentionally not surfaced in general audit/history views by
# default (Phase 4B-2 audit §D) — still exists, still queryable.
AUDIT_HIDDEN_STATUSES: frozenset[str] = frozenset({"superseded"})


def project_lifecycle_status(contract_status: str) -> str:
    """
    Pure display-bucket mapping for one canonical ActionContractStatus value.
    Never consulted for claim/execution authority — display only.

    Raises ValueError for any status not in the canonical set, rather than
    silently defaulting, so an unrecognized/new canonical status is a loud
    schema-contract failure, not a quiet mis-projection.
    """
    try:
        return _CONTRACT_STATUS_TO_PROJECTION[contract_status]
    except KeyError:
        raise ValueError(
            f"unknown ActionContract status for projection: {contract_status!r}"
        ) from None


def is_terminal(contract_status: str) -> bool:
    """Whether this canonical status has no further lifecycle transition."""
    return contract_status in TERMINAL_CONTRACT_STATUSES


def is_visible_for_audit(contract_status: str) -> bool:
    """Whether this canonical status should surface in general audit/history views."""
    return contract_status not in AUDIT_HIDDEN_STATUSES


def is_pending_list_visible(contract_status: str) -> bool:
    """
    Owner-approval pending-list membership. Only "pending" qualifies —
    "draft" is excluded even though it maps to the same display bucket, since
    it may represent a self_confirm proposal the requester confirms through a
    separate free-text flow (core.action_gateway.route_confirmation_word),
    not the Approvals owner-approval screen.
    """
    return contract_status == "pending"


def is_actionable(contract_status: str, approval_policy: str) -> bool:
    """
    Whether an owner approve/reject action is meaningful for this contract,
    per the Phase 4B-2 audit's rule that actionability must be read from the
    canonical contract's approval_policy, never inferred from status alone.

    Only APPROVAL_POLICY_APPROVAL contracts in "pending" status are
    actionable here. APPROVAL_POLICY_SELF_CONFIRM contracts (including any
    "draft") are never actionable through this projection — they are
    resolved through a separate self-confirm flow, not owner approval.

    This function does not itself authorize anything: a future wiring stage
    still requires the PostgreSQL execution claim before any dispatch.
    """
    if contract_status != "pending":
        return False
    return approval_policy == APPROVAL_POLICY_APPROVAL


def is_legacy_row(action_contract_id: str | None) -> bool:
    """
    A projection row with no action_contract_id predates Phase 4B-2 and must
    be treated as legacy_read_only: never auto-replayed, never actionable,
    per the Phase 4B-2 audit's legacy/cutover policy (§E).
    """
    return not action_contract_id


__all__ = [
    "APPROVAL_POLICY_APPROVAL",
    "APPROVAL_POLICY_SELF_CONFIRM",
    "TERMINAL_CONTRACT_STATUSES",
    "AUDIT_HIDDEN_STATUSES",
    "project_lifecycle_status",
    "is_terminal",
    "is_visible_for_audit",
    "is_pending_list_visible",
    "is_actionable",
    "is_legacy_row",
]
