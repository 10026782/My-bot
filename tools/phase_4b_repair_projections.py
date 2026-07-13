#!/usr/bin/env python3
# tools/phase_4b_repair_projections.py — Phase 4B safe projection display repairs.
#
# Default mode is --report-only (also the default with no flags — you must
# pass BOTH --apply AND --confirm APPLY_PROJECTION_REPAIRS to write
# anything). This tool is deliberately narrower than
# tools/phase_4b_reconciliation.py: it never repairs anything reconciliation
# doesn't already flag, and it never performs anything but the 5 allowed
# repair types below. It is NOT a substitute for reconciliation and must
# never be run without first reviewing a reconciliation report.
#
# Allowed repairs ONLY:
#   1. Create a missing Approvals projection for a valid PENDING canonical
#      tma_write contract (mirrors tma_api._ensure_approval_projection's
#      create path, reusing tma_api.ACTION_RISK/_RISK_LEVEL_AIRTABLE so the
#      re-created row matches what the live path would have written).
#   2. Correct action_contract_id on an already-identified orphaned
#      projection, ONLY when exactly one unclaimed pending canonical
#      contract matches it 1:1 by CONTEXT_ID == contract's tool_inputs
#      "action" value — never a fuzzy/heuristic match, never more than one
#      candidate on either side.
#   3. Set legacy_read_only=false for a projection that has a valid
#      action_contract_id (contradictory legacy flag on a genuinely
#      contract-linked row).
#   4. Set projected_lifecycle_status from the canonical contract — EXCEPT
#      when the canonical status is outcome_unknown (never auto-repaired;
#      requires manual reconciliation, matching the canary spec).
#   5. Blank CONTEXT_DATA, ONLY for a row that already has a valid
#      action_contract_id (a genuine Phase-4B-2-shaped, contract-linked
#      projection) — never touches CONTEXT_DATA on a legacy (no
#      action_contract_id) row.
#
# This tool NEVER: approves or rejects a contract, calls
# ActionGateway.approve()/reject(), calls dispatch_tool(), creates a
# PostgreSQL execution claim, retries a provider write, changes an
# ActionContract's lifecycle/status, or auto-repairs outcome_unknown.
#
# Run manually:
#   python3 tools/phase_4b_repair_projections.py --report-only
#   python3 tools/phase_4b_repair_projections.py --apply --confirm APPLY_PROJECTION_REPAIRS
#
# Produces reports/phase_4b_repair_projections.json.

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from airtable_schema import ApprovalsFields, ApprovalStatus  # noqa: E402
from tools.phase_4b_rollout_common import (  # noqa: E402
    REPO_ROOT, dump_json_report, fetch_all_action_contracts, fetch_all_approvals,
    git_state, is_canonical_tma_contract, utc_now_iso,
)

REPORT_PATH = REPO_ROOT / "reports" / "runtime" / "phase_4b_repair_projections.json"
_CONFIRM_TOKEN = "APPLY_PROJECTION_REPAIRS"


def _plan_repairs(contracts_raw: list, approvals: list[dict]) -> dict:
    from core.approvals_projection import project_lifecycle_status

    contracts_by_id = {c.contract_id: c for c, _rec_id in contracts_raw}
    approvals_by_contract: dict[str, list[dict]] = {}
    for row in approvals:
        cid = row.get("fields", {}).get(ApprovalsFields.ACTION_CONTRACT_ID, "")
        if cid:
            approvals_by_contract.setdefault(cid, []).append(row)

    plan = {
        "create_projection": [],       # [{contract_id, fields}]
        "correct_action_contract_id": [],  # [{record_id, contract_id}]
        "clear_legacy_flag": [],       # [record_id]
        "set_projected_status": [],    # [{record_id, new_status}]
        "blank_context_data": [],      # [record_id]
        "skipped_outcome_unknown": [],
        "skipped_ambiguous": [],
    }

    # Candidate pool for both Repair 1 and Repair 2: every valid pending
    # canonical contract with no existing projection row at all.
    missing_contracts = [
        c for c, _rec_id in contracts_raw
        if is_canonical_tma_contract(c) and c.status == "pending"
        and not approvals_by_contract.get(c.contract_id)
    ]
    missing_by_action: dict[str, list] = {}
    for c in missing_contracts:
        action_key = str((c.normalized_payload or {}).get("action", c.tool_name))
        missing_by_action.setdefault(action_key, []).append(c)

    # Repair 2 runs FIRST: correct action_contract_id on an orphaned
    # projection (a row whose action_contract_id points at nothing), only
    # for an unambiguous 1:1 match — exactly one orphaned row AND exactly
    # one missing contract sharing the same CONTEXT_ID/action key. A key
    # matching more than one row or more than one contract is refused
    # entirely (every row sharing that key goes to skipped_ambiguous, no
    # guessing). A matched contract is consumed here and must never also
    # get a brand-new projection from Repair 1 below.
    orphaned_rows = [
        row for row in approvals
        if row.get("fields", {}).get(ApprovalsFields.ACTION_CONTRACT_ID)
        and row["fields"][ApprovalsFields.ACTION_CONTRACT_ID] not in contracts_by_id
    ]
    rows_by_context_id: dict[str, list] = {}
    for row in orphaned_rows:
        key = row.get("fields", {}).get(ApprovalsFields.CONTEXT_ID, "")
        rows_by_context_id.setdefault(key, []).append(row)

    matched_contract_ids: set[str] = set()
    for key, candidate_rows in rows_by_context_id.items():
        candidate_contracts = missing_by_action.get(key, []) if key else []
        if key and len(candidate_rows) == 1 and len(candidate_contracts) == 1:
            row = candidate_rows[0]
            contract = candidate_contracts[0]
            plan["correct_action_contract_id"].append({
                "record_id": row["id"], "contract_id": contract.contract_id,
            })
            matched_contract_ids.add(contract.contract_id)
        else:
            plan["skipped_ambiguous"].extend(row["id"] for row in candidate_rows)

    # Repair 1 runs SECOND, only for missing contracts NOT consumed above —
    # a contract matched to an orphaned row gets that row corrected, never
    # also a brand-new duplicate projection.
    for c in missing_contracts:
        if c.contract_id in matched_contract_ids:
            continue
        action = (c.normalized_payload or {}).get("action", c.tool_name)
        plan["create_projection"].append({
            "contract_id": c.contract_id,
            "fields": {
                ApprovalsFields.ACTION: str(action),
                ApprovalsFields.REQUESTED_BY: c.actor_display_name or c.actor_user_id or c.canonical_user_id,
                ApprovalsFields.REQUESTED_AT: datetime.fromtimestamp(
                    c.created_at, tz=timezone.utc).isoformat() if c.created_at else
                    datetime.now(timezone.utc).isoformat(),
                ApprovalsFields.CONTEXT_TYPE: "tma_write",
                ApprovalsFields.CONTEXT_ID: str(action),
                ApprovalsFields.CONTEXT_DATA: "",
                ApprovalsFields.STATUS: ApprovalStatus.PENDING,
                ApprovalsFields.ACTION_CONTRACT_ID: c.contract_id,
                ApprovalsFields.LEGACY_READ_ONLY: False,
                ApprovalsFields.PROJECTED_LIFECYCLE_STATUS: project_lifecycle_status("pending"),
                # RISK_LEVEL intentionally omitted here — tma_api.ACTION_RISK/
                # _RISK_LEVEL_AIRTABLE mapping is applied by the caller (see
                # run()), which imports tma_api lazily to avoid a hard
                # dependency for report-only mode.
            },
        })

    # Repair 3 — clear a contradictory legacy_read_only=true on a genuinely
    # contract-linked row.
    for cid, rows in approvals_by_contract.items():
        if cid not in contracts_by_id:
            continue
        for row in rows:
            if row.get("fields", {}).get(ApprovalsFields.LEGACY_READ_ONLY) is True:
                plan["clear_legacy_flag"].append(row["id"])

    # Repair 4 — set projected_lifecycle_status from the canonical contract,
    # never for outcome_unknown.
    for cid, rows in approvals_by_contract.items():
        contract = contracts_by_id.get(cid)
        if contract is None:
            continue
        if contract.status == "outcome_unknown":
            plan["skipped_outcome_unknown"].extend(row["id"] for row in rows)
            continue
        try:
            expected = project_lifecycle_status(contract.status)
        except ValueError:
            continue
        for row in rows:
            actual = row.get("fields", {}).get(ApprovalsFields.PROJECTED_LIFECYCLE_STATUS)
            if actual != expected:
                plan["set_projected_status"].append({"record_id": row["id"], "new_status": expected})

    # Repair 5 — blank CONTEXT_DATA, only for contract-linked rows.
    for cid, rows in approvals_by_contract.items():
        if cid not in contracts_by_id:
            continue
        for row in rows:
            if row.get("fields", {}).get(ApprovalsFields.CONTEXT_DATA):
                plan["blank_context_data"].append(row["id"])

    return plan


def run(apply: bool, confirm: str | None) -> dict:
    contracts_raw = fetch_all_action_contracts()
    approvals = fetch_all_approvals()
    if contracts_raw is None or approvals is None:
        return {
            "generated_at": utc_now_iso(),
            "git": git_state(),
            "mode": "apply" if apply else "report-only",
            "error": "could not fetch ActionContracts/Approvals — no repairs attempted",
            "plan": {},
            "applied": {},
        }

    plan = _plan_repairs(contracts_raw, approvals)
    will_apply = apply and confirm == _CONFIRM_TOKEN

    result = {
        "generated_at": utc_now_iso(),
        "git": git_state(),
        "mode": "apply" if will_apply else "report-only",
        "apply_requested": apply,
        "confirm_token_matched": confirm == _CONFIRM_TOKEN,
        "plan": plan,
        "applied": {},
    }

    if apply and not will_apply:
        result["refused_reason"] = (
            "--apply was passed without the exact --confirm APPLY_PROJECTION_REPAIRS token "
            "— no write attempted"
        )
        return result
    if not will_apply:
        return result

    from tools.airtable_gateway import airtable_create, airtable_patch

    applied = {
        "created": [], "create_failed": [],
        "action_contract_id_corrected": [], "correction_failed": [],
        "legacy_flag_cleared": [], "legacy_clear_failed": [],
        "projected_status_set": [], "projected_status_failed": [],
        "context_data_blanked": [], "context_data_blank_failed": [],
    }

    try:
        from tma_api import ACTION_RISK, _RISK_LEVEL_AIRTABLE, _DEFAULT_RISK
    except Exception:
        ACTION_RISK, _RISK_LEVEL_AIRTABLE, _DEFAULT_RISK = {}, {}, "High"

    for item in plan["create_projection"]:
        fields = dict(item["fields"])
        action = fields.get(ApprovalsFields.CONTEXT_ID, "")
        risk = ACTION_RISK.get(action, _DEFAULT_RISK)
        fields[ApprovalsFields.RISK_LEVEL] = _RISK_LEVEL_AIRTABLE.get(risk, "high")
        rec = airtable_create("Approvals", fields, source="phase_4b_repair_projections")
        (applied["created"] if rec else applied["create_failed"]).append(item["contract_id"])

    for item in plan["correct_action_contract_id"]:
        ok = airtable_patch(
            "Approvals", item["record_id"],
            {ApprovalsFields.ACTION_CONTRACT_ID: item["contract_id"], ApprovalsFields.LEGACY_READ_ONLY: False},
            source="phase_4b_repair_projections",
        )
        (applied["action_contract_id_corrected"] if ok else applied["correction_failed"]).append(item["record_id"])

    for record_id in plan["clear_legacy_flag"]:
        ok = airtable_patch(
            "Approvals", record_id, {ApprovalsFields.LEGACY_READ_ONLY: False},
            source="phase_4b_repair_projections",
        )
        (applied["legacy_flag_cleared"] if ok else applied["legacy_clear_failed"]).append(record_id)

    for item in plan["set_projected_status"]:
        ok = airtable_patch(
            "Approvals", item["record_id"],
            {ApprovalsFields.PROJECTED_LIFECYCLE_STATUS: item["new_status"]},
            source="phase_4b_repair_projections",
        )
        (applied["projected_status_set"] if ok else applied["projected_status_failed"]).append(item["record_id"])

    for record_id in plan["blank_context_data"]:
        ok = airtable_patch(
            "Approvals", record_id, {ApprovalsFields.CONTEXT_DATA: ""},
            source="phase_4b_repair_projections",
        )
        (applied["context_data_blanked"] if ok else applied["context_data_blank_failed"]).append(record_id)

    result["applied"] = applied
    return result


def _print_human(result: dict) -> None:
    print("Phase 4B Projection Repair")
    print("=" * 60)
    print(f"generated_at: {result['generated_at']}")
    print(f"mode: {result['mode']}")
    if "error" in result:
        print(f"ERROR: {result['error']}")
        return
    plan = result["plan"]
    print(f"create_projection:              {len(plan.get('create_projection', []))}")
    print(f"correct_action_contract_id:      {len(plan.get('correct_action_contract_id', []))}")
    print(f"clear_legacy_flag:               {len(plan.get('clear_legacy_flag', []))}")
    print(f"set_projected_status:            {len(plan.get('set_projected_status', []))}")
    print(f"blank_context_data:              {len(plan.get('blank_context_data', []))}")
    print(f"skipped_outcome_unknown:         {len(plan.get('skipped_outcome_unknown', []))}")
    print(f"skipped_ambiguous:               {len(plan.get('skipped_ambiguous', []))}")
    if result.get("refused_reason"):
        print(f"\nREFUSED: {result['refused_reason']}")
    if result["mode"] == "apply":
        print("\napplied:")
        for k, v in result["applied"].items():
            print(f"  {k}: {len(v)}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Safe Approvals projection display repairs (report-only by default)"
    )
    parser.add_argument("--report-only", action="store_true",
                         help="Explicit report-only mode (also the default with no flags)")
    parser.add_argument("--apply", action="store_true",
                         help="Attempt the repairs — requires --confirm APPLY_PROJECTION_REPAIRS too")
    parser.add_argument("--confirm", default=None,
                         help="Must be exactly APPLY_PROJECTION_REPAIRS to allow a write")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON instead of text")
    args = parser.parse_args()

    try:
        result = run(apply=args.apply, confirm=args.confirm)
    except Exception as exc:
        err = {"error": f"{type(exc).__name__}: {exc}"}
        print(json.dumps(err, indent=2), file=sys.stderr)
        dump_json_report(REPORT_PATH, err)
        return 2

    dump_json_report(REPORT_PATH, result)

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        _print_human(result)

    if "error" in result:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
