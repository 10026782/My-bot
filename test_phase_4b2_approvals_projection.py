# test_phase_4b2_approvals_projection.py — Phase 4B-2 (schema-prep stage)
#
# Scope: schema/contract tests ONLY, per the Phase 4B-2 audit. This does NOT
# test routing, canonical reads, stale-projection rejection, reconciliation,
# or execution — those are deferred to the later wiring stage (tma_api.py is
# unchanged in this stage; _queue_tma_write_approval()/
# _claim_and_execute_approval() still write/read Approvals directly with no
# action_contract_id and no PostgreSQL claim).
#
# Tests:
#   1. ApprovalsFields carries exactly the 3 new Phase 4B-2 projection
#      constants, with the documented literal field names, and no new
#      payload field was introduced.
#   2. ProjectedLifecycleStatus exposes exactly the 9 documented display
#      buckets.
#   3. Every ActionContractStatus value maps to exactly one
#      ProjectedLifecycleStatus bucket via project_lifecycle_status()
#      (table-driven, per the audit's §D mapping).
#   4. outcome_unknown maps distinctly from failed (no collapse).
#   5. Terminal-status set matches ALLOWED_CONTRACT_TRANSITIONS having no
#      outgoing transition (core/action_contract_repository.py).
#   6. superseded is terminal but audit-hidden by default; all other
#      terminal statuses remain audit-visible.
#   7. draft is excluded from the owner-approval pending list even though it
#      shares a display bucket with pending.
#   8. is_actionable() only returns True for APPROVAL_POLICY_APPROVAL +
#      status=="pending" — self_confirm (including any draft) is never
#      actionable through this projection.
#   9. is_legacy_row() treats empty/None action_contract_id as legacy.
#  10. An unrecognized canonical status raises ValueError (loud schema
#      failure) rather than silently mis-projecting.

import os, sys
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:TEST")
os.environ.setdefault("AIRTABLE_API_KEY", "patTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

from airtable_schema import ApprovalsFields, ProjectedLifecycleStatus, ActionContractStatus
from core.action_contract_repository import ALLOWED_CONTRACT_TRANSITIONS
import core.approvals_projection as proj

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


# ══════════════════════════════════════════════════
# Test 1: ApprovalsFields — exactly 3 new projection constants, literal names
# ══════════════════════════════════════════════════
print("\n── Test 1: ApprovalsFields projection constants ────────────")
chk("ACTION_CONTRACT_ID == 'action_contract_id'",
    ApprovalsFields.ACTION_CONTRACT_ID == "action_contract_id")
chk("LEGACY_READ_ONLY == 'legacy_read_only'",
    ApprovalsFields.LEGACY_READ_ONLY == "legacy_read_only")
chk("PROJECTED_LIFECYCLE_STATUS == 'projected_lifecycle_status'",
    ApprovalsFields.PROJECTED_LIFECYCLE_STATUS == "projected_lifecycle_status")

# CONTEXT_DATA remains an existing legacy field in this stage — 4B-2 does not
# remove it, and this stage introduces no new payload-carrying field.
chk("CONTEXT_DATA still present (existing legacy field, untouched in 4B-2)",
    hasattr(ApprovalsFields, "CONTEXT_DATA"))
_new_4b2_fields = {"ACTION_CONTRACT_ID", "LEGACY_READ_ONLY", "PROJECTED_LIFECYCLE_STATUS"}
_all_field_attrs = {
    k for k, v in vars(ApprovalsFields).items()
    if not k.startswith("_") and isinstance(v, str)
}
_pre_existing_fields = {
    "ACTION", "REQUESTED_BY", "REQUESTED_AT", "RISK_LEVEL", "CONTEXT_TYPE",
    "CONTEXT_ID", "CONTEXT_DATA", "STATUS", "REJECTION_NOTE",
}
chk("exactly 3 new fields added, nothing else changed on ApprovalsFields",
    _all_field_attrs == _pre_existing_fields | _new_4b2_fields)
chk("no new payload/executable field introduced (only id/flag/status added)",
    not any("data" in f.lower() or "payload" in f.lower() for f in _new_4b2_fields))


# ══════════════════════════════════════════════════
# Test 2: ProjectedLifecycleStatus — exactly the 9 documented buckets
# ══════════════════════════════════════════════════
print("\n── Test 2: ProjectedLifecycleStatus buckets ─────────────────")
_expected_buckets = {
    "pending", "approved", "rejected", "executing", "completed",
    "failed", "outcome_unknown", "superseded", "legacy",
}
_actual_buckets = {
    v for k, v in vars(ProjectedLifecycleStatus).items()
    if not k.startswith("_") and isinstance(v, str)
}
chk("ProjectedLifecycleStatus has exactly the 9 documented buckets",
    _actual_buckets == _expected_buckets)


# ══════════════════════════════════════════════════
# Test 3: every canonical status maps to exactly one projection bucket
# (table-driven, per Phase 4B-2 audit §D)
# ══════════════════════════════════════════════════
print("\n── Test 3: canonical status -> projection bucket mapping ───")
_expected_mapping = {
    ActionContractStatus.DRAFT:            ProjectedLifecycleStatus.PENDING,
    ActionContractStatus.PENDING:          ProjectedLifecycleStatus.PENDING,
    ActionContractStatus.APPROVED:         ProjectedLifecycleStatus.APPROVED,
    ActionContractStatus.EXECUTING:        ProjectedLifecycleStatus.EXECUTING,
    ActionContractStatus.COMPLETED:        ProjectedLifecycleStatus.COMPLETED,
    ActionContractStatus.FAILED:           ProjectedLifecycleStatus.FAILED,
    ActionContractStatus.OUTCOME_UNKNOWN:  ProjectedLifecycleStatus.OUTCOME_UNKNOWN,
    ActionContractStatus.REJECTED:         ProjectedLifecycleStatus.REJECTED,
    ActionContractStatus.SUPERSEDED:       ProjectedLifecycleStatus.SUPERSEDED,
    ActionContractStatus.EXECUTED:         ProjectedLifecycleStatus.LEGACY,
}
for status, expected_bucket in _expected_mapping.items():
    chk(f"{status} -> {expected_bucket}",
        proj.project_lifecycle_status(status) == expected_bucket)

# Every value of ActionContractStatus is covered — no canonical status is
# left unmapped.
_all_canonical_statuses = {
    v for k, v in vars(ActionContractStatus).items()
    if not k.startswith("_") and isinstance(v, str)
}
chk("every ActionContractStatus value has a projection mapping",
    _all_canonical_statuses == set(_expected_mapping.keys()))


# ══════════════════════════════════════════════════
# Test 4: outcome_unknown remains distinct from failed
# ══════════════════════════════════════════════════
print("\n── Test 4: outcome_unknown distinct from failed ─────────────")
chk("outcome_unknown bucket != failed bucket",
    proj.project_lifecycle_status(ActionContractStatus.OUTCOME_UNKNOWN)
    != proj.project_lifecycle_status(ActionContractStatus.FAILED))


# ══════════════════════════════════════════════════
# Test 5: terminal-status set matches ALLOWED_CONTRACT_TRANSITIONS
# (no outgoing transition = terminal)
# ══════════════════════════════════════════════════
print("\n── Test 5: terminal status set ──────────────────────────────")
_statuses_with_outgoing = set(ALLOWED_CONTRACT_TRANSITIONS.keys())
_all_statuses = set(_expected_mapping.keys())
_derived_terminal = _all_statuses - _statuses_with_outgoing
chk("proj.TERMINAL_CONTRACT_STATUSES matches repository's implied terminal set",
    proj.TERMINAL_CONTRACT_STATUSES == _derived_terminal)
for s in ("completed", "failed", "outcome_unknown", "rejected", "superseded", "executed"):
    chk(f"{s} is terminal", proj.is_terminal(s))
for s in ("draft", "pending", "approved", "executing"):
    chk(f"{s} is NOT terminal", not proj.is_terminal(s))


# ══════════════════════════════════════════════════
# Test 6: superseded is terminal + audit-hidden; other terminals stay visible
# ══════════════════════════════════════════════════
print("\n── Test 6: audit visibility ──────────────────────────────────")
chk("superseded is hidden from general audit views",
    not proj.is_visible_for_audit("superseded"))
for s in ("completed", "failed", "outcome_unknown", "rejected", "executed", "pending", "draft"):
    chk(f"{s} remains visible for audit", proj.is_visible_for_audit(s))


# ══════════════════════════════════════════════════
# Test 7: draft excluded from owner-approval pending list
# ══════════════════════════════════════════════════
print("\n── Test 7: pending-list visibility ───────────────────────────")
chk("pending IS in the owner-approval pending list",
    proj.is_pending_list_visible("pending"))
chk("draft is NOT in the owner-approval pending list (may be self_confirm)",
    not proj.is_pending_list_visible("draft"))
for s in ("approved", "executing", "completed", "failed", "outcome_unknown", "rejected", "superseded", "executed"):
    chk(f"{s} is NOT in the owner-approval pending list",
        not proj.is_pending_list_visible(s))


# ══════════════════════════════════════════════════
# Test 8: is_actionable() — policy-aware, not status-only
# ══════════════════════════════════════════════════
print("\n── Test 8: is_actionable() reads approval_policy ─────────────")
chk("pending + APPROVAL_POLICY_APPROVAL -> actionable",
    proj.is_actionable("pending", proj.APPROVAL_POLICY_APPROVAL))
chk("pending + APPROVAL_POLICY_SELF_CONFIRM -> NOT actionable",
    not proj.is_actionable("pending", proj.APPROVAL_POLICY_SELF_CONFIRM))
chk("draft + APPROVAL_POLICY_APPROVAL -> NOT actionable (status must be pending)",
    not proj.is_actionable("draft", proj.APPROVAL_POLICY_APPROVAL))
chk("draft + APPROVAL_POLICY_SELF_CONFIRM -> NOT actionable",
    not proj.is_actionable("draft", proj.APPROVAL_POLICY_SELF_CONFIRM))
for s in ("approved", "executing", "completed", "failed", "outcome_unknown", "rejected", "superseded", "executed"):
    chk(f"{s} + APPROVAL_POLICY_APPROVAL -> NOT actionable (not pending)",
        not proj.is_actionable(s, proj.APPROVAL_POLICY_APPROVAL))


# ══════════════════════════════════════════════════
# Test 9: is_legacy_row() — empty/None action_contract_id is legacy
# ══════════════════════════════════════════════════
print("\n── Test 9: legacy-row detection ───────────────────────────────")
chk("None action_contract_id -> legacy", proj.is_legacy_row(None))
chk("empty string action_contract_id -> legacy", proj.is_legacy_row(""))
chk("populated action_contract_id -> NOT legacy", not proj.is_legacy_row("contract-abc-123"))


# ══════════════════════════════════════════════════
# Test 10: unrecognized status is a loud failure, not a silent default
# ══════════════════════════════════════════════════
print("\n── Test 10: unknown status raises ─────────────────────────────")
try:
    proj.project_lifecycle_status("not_a_real_status")
    chk("unknown status raises ValueError", False)
except ValueError:
    chk("unknown status raises ValueError", True)


# ══════════════════════════════════════════════════
print(f"\n{'='*50}")
print(f"Phase 4B-2 projection schema/contract tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
