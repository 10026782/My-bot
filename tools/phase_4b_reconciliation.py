#!/usr/bin/env python3
# tools/phase_4b_reconciliation.py — Phase 4B reconciliation diagnostic.
#
# Read-only. This tool has NO --apply/mutation mode at all — it only ever
# reads ActionContracts, Approvals, and PostgreSQL action_execution_claims
# and reports anomalies. Repairs (if any are ever needed) live in
# tools/phase_4b_repair_projections.py, gated separately.
#
# Run manually:
#   python3 tools/phase_4b_reconciliation.py --tenant-id boss_hq
#   python3 tools/phase_4b_reconciliation.py --tenant-id boss_hq --json
#
# Produces reports/runtime/phase_4b_reconciliation.json (gitignored — see
# reports/samples/phase_4b_reconciliation.sample.json for a fixture example).
#
# --tenant-id is required: R10 verifies every contract-linked Approvals row
# points to a contract belonging to that ONE rollout tenant (the real check —
# ApprovalsFields itself has no tenant_id field of its own, so the canonical
# tenant always comes from the linked ActionContract). Omitting --tenant-id
# is never silently treated as "nothing to check" — run_reconciliation()
# reports it as its own blocking finding so an operator can't accidentally
# get a false rollout_target_met=true by forgetting the flag.
#
# R16 is a separate, independent anomaly: two ActionContracts sharing a
# business_action_fingerprint but disagreeing with EACH OTHER on tenant_id
# (a structural fingerprint-collision signal, unrelated to which tenant this
# particular rollout is scoped to).

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from airtable_schema import ApprovalsFields  # noqa: E402
from tools.phase_4b_rollout_common import (  # noqa: E402
    REPO_ROOT, dump_json_report, fetch_all_action_contracts, fetch_all_approvals,
    fetch_all_claims, git_state, is_canonical_tma_contract, utc_now_iso,
)

REPORT_PATH = REPO_ROOT / "reports" / "runtime" / "phase_4b_reconciliation.json"

# A claim sitting in "executing" longer than this is flagged for manual
# attention alongside genuine outcome_unknown claims — a fresh in-flight
# claim (well under this age) is normal and not reported.
_STUCK_EXECUTING_SECONDS = 3600


def _finding(check_id: str, description: str, severity: str, items: list) -> dict:
    assert severity in ("blocking", "warning", "informational")
    items = sorted(set(items))
    return {
        "check_id": check_id,
        "description": description,
        "severity": severity,
        "count": len(items),
        "items": items,
    }


def run_reconciliation(tenant_id: str | None = None) -> dict:
    fetch_errors: dict[str, str] = {}

    contracts_raw = fetch_all_action_contracts()
    if contracts_raw is None:
        fetch_errors["action_contracts"] = "fetch failed — see logs; treating as unavailable"
        contracts_raw = []
    approvals = fetch_all_approvals()
    if approvals is None:
        fetch_errors["approvals"] = "fetch failed — see logs; treating as unavailable"
        approvals = []
    claims = fetch_all_claims()
    claims_unavailable = claims is None
    if claims_unavailable:
        fetch_errors["claims"] = "PostgreSQL unavailable — claim-based checks skipped"
        claims = []

    contracts_by_id = {c.contract_id: c for c, _rec_id in contracts_raw}
    approvals_by_contract: dict[str, list[dict]] = defaultdict(list)
    for row in approvals:
        cid = row.get("fields", {}).get(ApprovalsFields.ACTION_CONTRACT_ID, "")
        if cid:
            approvals_by_contract[cid].append(row)
    claims_by_contract = {c["contract_id"]: c for c in claims}

    from core.approvals_projection import project_lifecycle_status, is_terminal

    findings: list[dict] = []

    # 1. ActionContracts (canonical TMA shape) with no Approvals projection.
    missing_projection = [
        c.contract_id for c, _rec_id in contracts_raw
        if is_canonical_tma_contract(c) and not approvals_by_contract.get(c.contract_id)
    ]
    findings.append(_finding(
        "R1_contract_missing_projection",
        "ActionContracts (tma_write/tma_api/tma canonical shape) with no Approvals projection",
        "blocking", missing_projection,
    ))

    # 2. Approvals rows whose action_contract_id has no ActionContract.
    orphaned_projections = [
        row["id"] for row in approvals
        if row.get("fields", {}).get(ApprovalsFields.ACTION_CONTRACT_ID)
        and row["fields"][ApprovalsFields.ACTION_CONTRACT_ID] not in contracts_by_id
    ]
    findings.append(_finding(
        "R2_orphaned_projection",
        "Approvals rows whose action_contract_id has no matching ActionContract",
        "blocking", orphaned_projections,
    ))

    # 3. More than one Approvals row for the same action_contract_id.
    duplicate_projection_contracts = [
        cid for cid, rows in approvals_by_contract.items() if len(rows) > 1
    ]
    findings.append(_finding(
        "R3_duplicate_projection",
        "action_contract_id values with more than one Approvals projection row",
        "blocking", duplicate_projection_contracts,
    ))

    # 4. Projection lifecycle status differs from the canonical contract.
    status_mismatch = []
    for cid, rows in approvals_by_contract.items():
        contract = contracts_by_id.get(cid)
        if contract is None:
            continue
        try:
            expected = project_lifecycle_status(contract.status)
        except ValueError:
            continue
        for row in rows:
            actual = row.get("fields", {}).get(ApprovalsFields.PROJECTED_LIFECYCLE_STATUS)
            if actual != expected:
                status_mismatch.append(row["id"])
    findings.append(_finding(
        "R4_status_mismatch",
        "Approvals projected_lifecycle_status differs from the canonical contract's status",
        "blocking", status_mismatch,
    ))

    # 5. New contract-linked Approvals rows with non-empty CONTEXT_DATA.
    nonempty_context_data = [
        row["id"] for row in approvals
        if row.get("fields", {}).get(ApprovalsFields.ACTION_CONTRACT_ID)
        and row.get("fields", {}).get(ApprovalsFields.CONTEXT_DATA)
    ]
    findings.append(_finding(
        "R5_nonempty_context_data",
        "Contract-linked Approvals rows with non-empty CONTEXT_DATA (must always be blank)",
        "blocking", nonempty_context_data,
    ))

    # 6. Rows with action_contract_id but legacy_read_only=true.
    contract_linked_but_legacy = [
        row["id"] for row in approvals
        if row.get("fields", {}).get(ApprovalsFields.ACTION_CONTRACT_ID)
        and row.get("fields", {}).get(ApprovalsFields.LEGACY_READ_ONLY) is True
    ]
    findings.append(_finding(
        "R6_contract_linked_marked_legacy",
        "Approvals rows with a contract link but legacy_read_only=true (contradictory state)",
        "blocking", contract_linked_but_legacy,
    ))

    # 7. Rows without action_contract_id that are NOT treated as legacy/read-only.
    unmarked_legacy = [
        row["id"] for row in approvals
        if not row.get("fields", {}).get(ApprovalsFields.ACTION_CONTRACT_ID)
        and row.get("fields", {}).get(ApprovalsFields.LEGACY_READ_ONLY) is not True
    ]
    findings.append(_finding(
        "R7_unmarked_legacy_row",
        "Approvals rows with no action_contract_id that are not marked legacy_read_only=true",
        "blocking", unmarked_legacy,
    ))

    # 8. Contract-linked rows missing projected_lifecycle_status.
    missing_projected_status = [
        row["id"] for row in approvals
        if row.get("fields", {}).get(ApprovalsFields.ACTION_CONTRACT_ID)
        and not row.get("fields", {}).get(ApprovalsFields.PROJECTED_LIFECYCLE_STATUS)
    ]
    findings.append(_finding(
        "R8_missing_projected_status",
        "Contract-linked Approvals rows missing projected_lifecycle_status",
        "blocking", missing_projected_status,
    ))

    # 9. Approvals rows pointing to a non-TMA contract.
    non_tma_contract_rows = []
    for cid, rows in approvals_by_contract.items():
        contract = contracts_by_id.get(cid)
        if contract is not None and not is_canonical_tma_contract(contract):
            non_tma_contract_rows.extend(row["id"] for row in rows)
    findings.append(_finding(
        "R9_non_tma_contract_exposed",
        "Approvals rows whose linked contract is not a canonical tma_write/tma_api contract",
        "blocking", non_tma_contract_rows,
    ))

    # 10. Real tenant-scope check: every contract-linked Approvals row must
    # point to a contract belonging to the ONE tenant this rollout is scoped
    # to (--tenant-id). Absent tenant_id is NEVER treated as "nothing to
    # check" — it is its own guaranteed blocking finding under the same
    # stable check_id, so a forgotten --tenant-id can never silently produce
    # rollout_target_met=true.
    if tenant_id is None:
        findings.append(_finding(
            "R10_tenant_scope_mismatch",
            "Tenant scope could not be verified — --tenant-id was not provided. This is a "
            "blocking gap, never a silent pass.",
            "blocking", ["__tenant_id_not_provided__"],
        ))
    else:
        tenant_scope_mismatch = []
        for cid, rows in approvals_by_contract.items():
            contract = contracts_by_id.get(cid)
            if contract is None:
                continue
            if contract.tenant_id != tenant_id:
                tenant_scope_mismatch.extend(row["id"] for row in rows)
        findings.append(_finding(
            "R10_tenant_scope_mismatch",
            f"Contract-linked Approvals rows whose canonical contract's tenant_id does not "
            f"match the expected rollout tenant ({tenant_id!r})",
            "blocking", tenant_scope_mismatch,
        ))

    # 16. Fingerprint-level cross-tenant duplication — a separate, independent
    # anomaly from R10 above. R10 checks each row against the ONE rollout
    # tenant; this checks whether two ActionContracts share a
    # business_action_fingerprint (hash(tenant+user+tool+payload),
    # core/action_gateway.py) while disagreeing with EACH OTHER on
    # tenant_id — a structural fingerprint-collision signal independent of
    # which tenant any particular rollout is scoped to.
    fingerprint_tenants: dict[str, set[str]] = defaultdict(set)
    fingerprint_contracts: dict[str, list[str]] = defaultdict(list)
    for c, _rec_id in contracts_raw:
        if c.business_action_fingerprint:
            fingerprint_tenants[c.business_action_fingerprint].add(c.tenant_id)
            fingerprint_contracts[c.business_action_fingerprint].append(c.contract_id)
    fingerprint_cross_tenant = []
    for fp, tenants in fingerprint_tenants.items():
        if len(tenants) > 1:
            fingerprint_cross_tenant.extend(fingerprint_contracts[fp])
    findings.append(_finding(
        "R16_fingerprint_cross_tenant_duplication",
        "ActionContracts sharing a business_action_fingerprint but disagreeing with each "
        "other on tenant_id (independent of R10's single-rollout-tenant check)",
        "blocking", fingerprint_cross_tenant,
    ))

    # 11. Pending projections whose canonical contract is already terminal.
    stale_pending_projection = []
    for cid, rows in approvals_by_contract.items():
        contract = contracts_by_id.get(cid)
        if contract is None:
            continue
        try:
            terminal = is_terminal(contract.status)
        except ValueError:
            continue
        if not terminal:
            continue
        for row in rows:
            if row.get("fields", {}).get(ApprovalsFields.PROJECTED_LIFECYCLE_STATUS) == "pending":
                stale_pending_projection.append(row["id"])
    findings.append(_finding(
        "R11_stale_pending_projection",
        "Approvals rows still showing projected_lifecycle_status=pending while the canonical "
        "contract has already reached a terminal status",
        "blocking", stale_pending_projection,
    ))

    # 12. Executing/outcome_unknown claims requiring manual attention.
    now = time.time()
    needs_manual_attention = []
    for c in claims:
        if c["status"] == "outcome_unknown":
            needs_manual_attention.append(c["contract_id"])
        elif c["status"] == "executing" and (now - (c["claimed_at"] or now)) > _STUCK_EXECUTING_SECONDS:
            needs_manual_attention.append(c["contract_id"])
    findings.append(_finding(
        "R12_claims_needing_manual_attention",
        f"Claims with status=outcome_unknown, or status=executing for over "
        f"{_STUCK_EXECUTING_SECONDS}s (never auto-retry — investigate manually)",
        "blocking" if not claims_unavailable else "warning",
        needs_manual_attention,
    ))

    # 13. Claims whose canonical ActionContract cannot be found.
    orphaned_claims = [
        c["contract_id"] for c in claims if c["contract_id"] not in contracts_by_id
    ]
    findings.append(_finding(
        "R13_orphaned_claim",
        "PostgreSQL claims whose canonical ActionContract cannot be found",
        "blocking", orphaned_claims,
    ))

    # 14. Completed/executed contracts whose EXISTING claim status disagrees.
    completed_contract_claim_mismatch = []
    for c, _rec_id in contracts_raw:
        if c.status not in ("completed", "executed"):
            continue
        claim = claims_by_contract.get(c.contract_id)
        if claim is not None and claim["status"] != "completed":
            completed_contract_claim_mismatch.append(c.contract_id)
    findings.append(_finding(
        "R14_completed_contract_claim_mismatch",
        "ActionContracts with status=completed/executed whose PostgreSQL claim exists but "
        "disagrees (claim status != completed)",
        "blocking", completed_contract_claim_mismatch,
    ))

    # 17. A completed/executed CANONICAL tma_write contract must have a
    # PostgreSQL claim at all — Phase 4B-2 makes PostgreSQL claims the sole
    # execution-ownership primitive for tma_write, so a canonical contract
    # that reached completed/executed with no claim row at all is a real gap,
    # not tolerable history. Historical tolerance (missing claim silently OK)
    # is preserved ONLY for non-canonical contracts — other tools may have
    # completed via the legacy pre-atomic-claims path for their entire
    # lifetime and never created a claim at all; that remains untouched.
    canonical_completed_missing_claim = []
    for c, _rec_id in contracts_raw:
        if c.status not in ("completed", "executed"):
            continue
        if not is_canonical_tma_contract(c):
            continue
        if claims_by_contract.get(c.contract_id) is None:
            canonical_completed_missing_claim.append(c.contract_id)
    findings.append(_finding(
        "R17_canonical_completed_missing_claim",
        "Completed/executed canonical tma_write ActionContracts with no PostgreSQL claim at "
        "all (blocking — historical tolerance for a missing claim is preserved only for "
        "non-TMA contracts)",
        "blocking" if not claims_unavailable else "warning",
        canonical_completed_missing_claim,
    ))

    # 15. Duplicate active execution ownership anomaly.
    #
    # action_execution_claims.contract_id is a database PRIMARY KEY, so two
    # claim rows can never share one contract_id — that specific duplication
    # is structurally impossible and not what this checks. Instead: two
    # different contracts sharing a business_action_fingerprint (the same
    # logical business action) each holding an active ("executing") claim
    # would mean the same action is being executed twice concurrently under
    # two different contract_ids — a real ownership-duplication anomaly this
    # tool can detect.
    executing_contract_ids = {c["contract_id"] for c in claims if c["status"] == "executing"}
    duplicate_active_ownership = []
    for fp, cids in fingerprint_contracts.items():
        active = [cid for cid in cids if cid in executing_contract_ids]
        if len(active) > 1:
            duplicate_active_ownership.extend(active)
    findings.append(_finding(
        "R15_duplicate_active_ownership",
        "Multiple contracts sharing a business_action_fingerprint each holding an active "
        "(executing) PostgreSQL claim at the same time",
        "blocking", duplicate_active_ownership,
    ))

    blocking_findings = [f for f in findings if f["severity"] == "blocking" and f["count"] > 0]
    warnings = [f for f in findings if f["severity"] == "warning" and f["count"] > 0]
    informational = [f for f in findings if f["severity"] == "informational" and f["count"] > 0]

    rollout_target_met = not blocking_findings and not fetch_errors

    return {
        "generated_at": utc_now_iso(),
        "git": git_state(),
        "counts": {
            "action_contracts": len(contracts_raw),
            "approvals": len(approvals),
            "claims": (None if claims_unavailable else len(claims)),
        },
        "fetch_errors": fetch_errors,
        "findings": findings,
        "blocking_findings": blocking_findings,
        "warnings": warnings,
        "informational": informational,
        "rollout_target_met": rollout_target_met,
    }


def _print_human(result: dict) -> None:
    print("Phase 4B Reconciliation")
    print("=" * 60)
    print(f"generated_at: {result['generated_at']}")
    print(f"git: commit={result['git']['commit_sha']} branch={result['git']['branch']}")
    print(f"counts: {result['counts']}")
    if result["fetch_errors"]:
        print(f"FETCH ERRORS: {result['fetch_errors']}")
    print()
    for f in result["findings"]:
        marker = "OK" if f["count"] == 0 else f["severity"].upper()
        print(f"  [{marker}] {f['check_id']}: {f['description']} — count={f['count']}")
        if f["count"] and f["items"]:
            shown = f["items"][:10]
            print(f"           e.g. {shown}" + (" ..." if f["count"] > 10 else ""))
    print()
    print("=" * 60)
    print(f"rollout_target_met: {result['rollout_target_met']}")
    print(f"blocking_findings: {len(result['blocking_findings'])} | "
          f"warnings: {len(result['warnings'])} | informational: {len(result['informational'])}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 4B reconciliation diagnostic (read-only, no --apply mode)")
    parser.add_argument("--tenant-id", required=True,
                         help="The single tenant this rollout is scoped to (required — see R10)")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON instead of text")
    args = parser.parse_args()

    try:
        result = run_reconciliation(tenant_id=args.tenant_id)
    except Exception as exc:
        err = {"error": f"{type(exc).__name__}: {exc}", "rollout_target_met": False}
        print(json.dumps(err, indent=2), file=sys.stderr)
        dump_json_report(REPORT_PATH, err)
        return 2

    dump_json_report(REPORT_PATH, result)

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        _print_human(result)

    return 0 if result["rollout_target_met"] else 1


if __name__ == "__main__":
    sys.exit(main())
