#!/usr/bin/env python3
# tools/phase_4b_canary_verify.py — Phase 4B observational canary verifier.
#
# Purely observational. Given the IDs an operator noted down while manually
# running one of the canary scenarios in
# docs/PHASE_4B_ROLLOUT_AND_CUTOVER.md §9, this tool cross-checks that the
# contract, projection, claim, and (optionally) the provider record actually
# agree with each other. It NEVER:
#   - proposes an action (never calls ActionGateway.propose_action())
#   - approves or rejects anything (never calls .approve()/.reject())
#   - dispatches a tool (never calls dispatch_tool())
#   - creates or updates a PostgreSQL claim (never calls
#     claim_contract_execution()/update_claim_status() — only the
#     documented read-only core.atomic_claim_repository.get_claim())
#   - retries anything
#   - writes to Airtable or PostgreSQL in any way
#
# --expected-outcome is required (completed|rejected|outcome_unknown) — a
# pending/approved/executing contract can never match any of the three and
# therefore can never be reported VERIFIED. 'completed' additionally
# requires a completed PostgreSQL claim AND supplied, existing provider
# evidence (--provider-table/--provider-record-id are not optional in that
# case). 'outcome_unknown', once confirmed, returns verdict=MANUAL_REVIEW —
# a distinct third state, never VERIFIED and never bluntly FAILED, matching
# the "never auto-retry outcome_unknown — investigate manually" rule
# elsewhere in this codebase.
#
# Run manually, after a canary step, with whatever IDs you have:
#   python3 tools/phase_4b_canary_verify.py --contract-id <id> --expected-outcome completed \
#       --provider-table Leads --provider-record-id <id>
#   python3 tools/phase_4b_canary_verify.py --contract-id <id> --expected-outcome rejected
#   python3 tools/phase_4b_canary_verify.py --contract-id <id> --expected-outcome outcome_unknown --json
#
# Exit codes: 0 = VERIFIED, 1 = FAILED, 2 = tool error, 3 = MANUAL_REVIEW.
#
# Produces reports/runtime/phase_4b_canary_verify.json (gitignored — see
# reports/samples/phase_4b_canary_evidence.sample.json for a fixture shape).

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from airtable_schema import ApprovalsFields  # noqa: E402
from tools.phase_4b_rollout_common import (  # noqa: E402
    REPO_ROOT, dump_json_report, fetch_all_records, fetch_record_by_id,
    git_state, is_canonical_tma_contract, utc_now_iso,
)

REPORT_PATH = REPO_ROOT / "reports" / "runtime" / "phase_4b_canary_verify.json"

_TERMINAL_SUCCESS_STATUSES = ("completed", "executed")
_VALID_EXPECTED_OUTCOMES = ("completed", "rejected", "outcome_unknown")


def _outcome_matches(contract_status: str, claim, expected_outcome: str) -> bool:
    """Whether the contract's (and, for outcome_unknown, the claim's) actual
    state matches what the operator expected this canary to have reached.
    A pending/approved/executing contract can never match any of the three
    expected outcomes — that's exactly what keeps a not-yet-terminal canary
    from ever being reported VERIFIED."""
    if expected_outcome == "completed":
        return contract_status in _TERMINAL_SUCCESS_STATUSES
    if expected_outcome == "rejected":
        return contract_status == "rejected"
    if expected_outcome == "outcome_unknown":
        return contract_status == "outcome_unknown" or (claim is not None and claim.status == "outcome_unknown")
    raise ValueError(f"unknown expected_outcome: {expected_outcome!r}")


def _finding(id_: str, description: str, mandatory: bool, status: str, detail: str = "") -> dict:
    assert status in ("PASS", "FAIL", "WARN", "SKIP")
    return {"id": id_, "description": description, "mandatory": mandatory,
            "status": status, "detail": detail}


def _safe_str(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"


def _find_projection_for_contract(contract_id: str) -> tuple[dict | None, str]:
    """Auto-discover the Approvals projection row for a contract_id when the
    operator didn't supply --approval-record-id. Read-only formula search,
    same idempotent-lookup shape as tma_api._find_approval_projection_by_contract.
    Returns (row_or_None, detail_message)."""
    from tools.airtable_gateway import _safe_formula_param, at_list_by_formula, AirtableLookupError

    formula = f"{{{ApprovalsFields.ACTION_CONTRACT_ID}}}='{_safe_formula_param(contract_id)}'"
    try:
        records = at_list_by_formula("Approvals", formula, max_records=2)
    except AirtableLookupError as exc:
        return None, f"projection lookup failed: {exc}"
    if not records:
        return None, "no Approvals projection found for this contract_id"
    if len(records) > 1:
        return None, f"ambiguous: {len(records)} Approvals rows reference this contract_id"
    return records[0], ""


def verify_canary(contract_id: str, expected_outcome: str, approval_record_id: str | None = None,
                   provider_table: str | None = None, provider_record_id: str | None = None) -> dict:
    if expected_outcome not in _VALID_EXPECTED_OUTCOMES:
        raise ValueError(
            f"expected_outcome must be one of {_VALID_EXPECTED_OUTCOMES}, got {expected_outcome!r}"
        )

    findings: list[dict] = []

    from core.action_contract_repository import ActionContractRepository, ActionContractLookupError

    contract = None
    try:
        contract = ActionContractRepository().get(contract_id)
    except ActionContractLookupError as exc:
        findings.append(_finding("contract_lookup", "ActionContract is reachable and found",
                                  True, "FAIL", f"lookup error: {exc}"))
    if contract is None and not findings:
        findings.append(_finding("contract_lookup", "ActionContract is reachable and found",
                                  True, "FAIL", "contract not found (or expired pending)"))
    elif contract is not None:
        findings.append(_finding("contract_lookup", "ActionContract is reachable and found",
                                  True, "PASS", f"status={contract.status}"))

    if contract is None:
        # Nothing else can be meaningfully checked without the contract.
        for check_id, desc in [
            ("expected_outcome_match", "contract's actual lifecycle status matches --expected-outcome"),
            ("contract_canonical_shape", "contract has the canonical tma_write/tma_api/tma shape"),
            ("requester_approver_separation", "requester and approver stable IDs are distinct"),
            ("projection_lookup", "an Approvals projection exists for this contract"),
            ("projection_contract_link", "projection's action_contract_id matches the contract"),
            ("projection_lifecycle_match", "projection's projected_lifecycle_status matches the contract"),
            ("projection_not_legacy", "projection is not marked legacy_read_only"),
            ("projection_context_data_empty", "projection CONTEXT_DATA is empty"),
            ("claim_expectation", "PostgreSQL claim presence/status matches the contract's lifecycle"),
            ("duplicate_execution_evidence", "no other claim shares this claim's idempotency_key"),
            ("provider_record_exists", "the supplied provider record actually exists"),
        ]:
            findings.append(_finding(check_id, desc, False, "SKIP", "skipped: contract not found"))
        return _package(findings, contract_id, expected_outcome)

    # Fetched once, up front — needed both for expected_outcome_match
    # (the outcome_unknown case looks at the claim, not just the contract)
    # and for claim_expectation/duplicate_execution_evidence below.
    from core.atomic_claim_repository import get_claim
    claim = get_claim(contract_id)

    outcome_matches = _outcome_matches(contract.status, claim, expected_outcome)
    findings.append(_finding(
        "expected_outcome_match", "contract's actual lifecycle status matches --expected-outcome",
        True, "PASS" if outcome_matches else "FAIL",
        f"expected_outcome={expected_outcome!r} actual_contract_status={contract.status!r}"
        + ("" if claim is None else f" claim_status={claim.status!r}"),
    ))

    canonical = is_canonical_tma_contract(contract)
    findings.append(_finding(
        "contract_canonical_shape", "contract has the canonical tma_write/tma_api/tma shape",
        True, "PASS" if canonical else "FAIL",
        "" if canonical else
        f"tool_name={contract.tool_name!r} trusted_source={getattr(contract,'trusted_source','')!r} "
        f"origin_channel={contract.origin_channel!r} approval_policy={getattr(contract,'approval_policy','')!r}",
    ))

    # Stable-ID comparison — actor_user_id/canonical_user_id (the frozen
    # proposal-time identity) versus approved_by. actor_display_name is
    # never the primary comparison: it's free-text, not a stable identity,
    # and is only ever included in the detail message for human context.
    requester_id = contract.actor_user_id or contract.canonical_user_id
    approver_id = contract.approved_by or ""
    if contract.status in ("approved", "executing") or contract.status in _TERMINAL_SUCCESS_STATUSES \
            or contract.status == "rejected":
        separated = bool(approver_id) and approver_id != requester_id
        findings.append(_finding(
            "requester_approver_separation", "requester and approver stable IDs are distinct",
            True, "PASS" if separated else "FAIL",
            f"requester_id={requester_id!r} approver_id={approver_id!r} "
            f"(actor_display_name={contract.actor_display_name!r}, shown for reference only)",
        ))
    else:
        findings.append(_finding(
            "requester_approver_separation", "requester and approver stable IDs are distinct",
            False, "SKIP", f"contract status={contract.status!r} — not yet approved",
        ))

    # Projection lookup — explicit record id if supplied, else auto-discover.
    row = None
    if approval_record_id:
        row = fetch_record_by_id("Approvals", approval_record_id)
        lookup_detail = "" if row else f"record '{approval_record_id}' not found"
    else:
        row, lookup_detail = _find_projection_for_contract(contract_id)
    findings.append(_finding(
        "projection_lookup", "an Approvals projection exists for this contract",
        True, "PASS" if row else "FAIL", lookup_detail,
    ))

    if row is None:
        for check_id, desc in [
            ("projection_contract_link", "projection's action_contract_id matches the contract"),
            ("projection_lifecycle_match", "projection's projected_lifecycle_status matches the contract"),
            ("projection_not_legacy", "projection is not marked legacy_read_only"),
            ("projection_context_data_empty", "projection CONTEXT_DATA is empty"),
        ]:
            findings.append(_finding(check_id, desc, False, "SKIP", "skipped: projection not found"))
    else:
        fields = row.get("fields", {})
        linked_id = fields.get(ApprovalsFields.ACTION_CONTRACT_ID, "")
        findings.append(_finding(
            "projection_contract_link", "projection's action_contract_id matches the contract",
            True, "PASS" if linked_id == contract_id else "FAIL",
            f"projection.action_contract_id={linked_id!r} expected={contract_id!r}",
        ))

        from core.approvals_projection import project_lifecycle_status
        try:
            expected_status = project_lifecycle_status(contract.status)
            actual_status = fields.get(ApprovalsFields.PROJECTED_LIFECYCLE_STATUS)
            findings.append(_finding(
                "projection_lifecycle_match", "projection's projected_lifecycle_status matches the contract",
                True, "PASS" if actual_status == expected_status else "FAIL",
                f"projection={actual_status!r} expected={expected_status!r}",
            ))
        except ValueError as exc:
            findings.append(_finding(
                "projection_lifecycle_match", "projection's projected_lifecycle_status matches the contract",
                True, "FAIL", _safe_str(exc),
            ))

        legacy = fields.get(ApprovalsFields.LEGACY_READ_ONLY)
        findings.append(_finding(
            "projection_not_legacy", "projection is not marked legacy_read_only",
            True, "PASS" if legacy is not True else "FAIL", f"legacy_read_only={legacy!r}",
        ))

        context_data = fields.get(ApprovalsFields.CONTEXT_DATA)
        findings.append(_finding(
            "projection_context_data_empty", "projection CONTEXT_DATA is empty",
            True, "PASS" if not context_data else "FAIL",
            "" if not context_data else "CONTEXT_DATA is non-empty",
        ))

    # Claim expectation depends on the contract's own lifecycle — a
    # rejected contract MUST NEVER have a claim; a completed/executed
    # canonical contract MUST have one, and it must be completed. `claim`
    # was already fetched above for expected_outcome_match.
    if contract.status == "rejected":
        findings.append(_finding(
            "claim_expectation", "PostgreSQL claim presence/status matches the contract's lifecycle",
            True, "PASS" if claim is None else "FAIL",
            "no claim, as expected for a rejected contract" if claim is None
            else f"unexpected claim found (status={claim.status!r}) for a rejected contract",
        ))
    elif contract.status in _TERMINAL_SUCCESS_STATUSES and canonical:
        if claim is None:
            findings.append(_finding(
                "claim_expectation", "PostgreSQL claim presence/status matches the contract's lifecycle",
                True, "FAIL", "no claim found for a completed/executed canonical contract",
            ))
        else:
            findings.append(_finding(
                "claim_expectation", "PostgreSQL claim presence/status matches the contract's lifecycle",
                True, "PASS" if claim.status == "completed" else "FAIL",
                f"claim.status={claim.status!r}",
            ))
    else:
        findings.append(_finding(
            "claim_expectation", "PostgreSQL claim presence/status matches the contract's lifecycle",
            False, "SKIP" if claim is None else "WARN",
            f"contract status={contract.status!r} — informational only "
            f"({'no claim' if claim is None else f'claim.status={claim.status!r}'})",
        ))

    if claim is not None:
        dup_detail = ""
        dup_status = "PASS"
        dup_mandatory = True
        try:
            from core.database import get_conn, release_conn
            conn = get_conn()
            if conn is None:
                # PostgreSQL being unreachable here is an environment gap,
                # not a real cross-check failure — never let it force an
                # overall FAILED verdict on its own.
                dup_status, dup_detail = "SKIP", "PostgreSQL unavailable for duplicate-idempotency-key check"
                dup_mandatory = False
            else:
                try:
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT contract_id FROM action_execution_claims "
                            "WHERE idempotency_key = %s AND contract_id != %s;",
                            (claim.idempotency_key, contract_id),
                        )
                        others = [r[0] for r in cur.fetchall()]
                    if others:
                        dup_status = "FAIL"
                        dup_detail = f"idempotency_key also claimed by: {sorted(others)}"
                finally:
                    release_conn(conn)
        except Exception as exc:
            dup_status, dup_detail = "FAIL", _safe_str(exc)
        findings.append(_finding(
            "duplicate_execution_evidence", "no other claim shares this claim's idempotency_key",
            dup_mandatory, dup_status, dup_detail,
        ))
    else:
        findings.append(_finding(
            "duplicate_execution_evidence", "no other claim shares this claim's idempotency_key",
            False, "SKIP", "skipped: no claim to check",
        ))

    # A "completed" canary MUST have supplied, existing provider evidence —
    # this is mandatory=True unconditionally for expected_outcome=="completed",
    # so omitting --provider-table/--provider-record-id is itself a FAIL, not
    # a SKIP. For "rejected"/"outcome_unknown" canaries, provider evidence is
    # optional context (SKIP when omitted, as before).
    provider_required = (expected_outcome == "completed")
    if provider_table and provider_record_id:
        rec = fetch_record_by_id(provider_table, provider_record_id)
        findings.append(_finding(
            "provider_record_exists", "the supplied provider record actually exists",
            True, "PASS" if rec else "FAIL",
            "" if rec else f"'{provider_record_id}' not found in table '{provider_table}'",
        ))
    elif provider_required:
        findings.append(_finding(
            "provider_record_exists", "the supplied provider record actually exists",
            True, "FAIL",
            "--expected-outcome completed requires --provider-table and --provider-record-id evidence",
        ))
    else:
        findings.append(_finding(
            "provider_record_exists", "the supplied provider record actually exists",
            False, "SKIP", "skipped: --provider-table/--provider-record-id not supplied",
        ))

    return _package(findings, contract_id, expected_outcome, claim=claim, contract_status=contract.status)


def _package(findings: list[dict], contract_id: str, expected_outcome: str,
             claim=None, contract_status: str | None = None) -> dict:
    blocking = [f for f in findings if f["mandatory"] and f["status"] in ("FAIL", "SKIP")]

    manual_review = (
        contract_status is not None
        and expected_outcome == "outcome_unknown"
        and _outcome_matches(contract_status, claim, expected_outcome)
    )

    if manual_review:
        verdict = "MANUAL_REVIEW"
    elif blocking:
        verdict = "FAILED"
    else:
        verdict = "VERIFIED"

    return {
        "generated_at": utc_now_iso(),
        "git": git_state(),
        "contract_id": contract_id,
        "expected_outcome": expected_outcome,
        "verdict": verdict,
        "findings": findings,
        "blocking_findings": blocking,
    }


def _print_human(result: dict) -> None:
    print("Phase 4B Canary Verification")
    print("=" * 60)
    print(f"generated_at: {result['generated_at']}")
    print(f"contract_id: {result['contract_id']}")
    print(f"expected_outcome: {result.get('expected_outcome')}")
    print()
    for f in result["findings"]:
        tag = "mandatory" if f["mandatory"] else "info"
        print(f"  [{f['status']:4s}] ({tag:9s}) {f['id']}: {f['description']}")
        if f["detail"]:
            print(f"           {f['detail']}")
    print()
    print("=" * 60)
    print(f"VERDICT: {result['verdict']}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Phase 4B observational canary verifier (read-only — never mutates anything)"
    )
    parser.add_argument("--contract-id", required=True, help="ActionContract.contract_id to verify")
    parser.add_argument(
        "--expected-outcome", required=True, choices=list(_VALID_EXPECTED_OUTCOMES),
        help=(
            "What this canary was expected to reach. A pending/approved/executing contract "
            "never matches any of these and can never be reported VERIFIED. 'completed' also "
            "requires a completed claim and supplied, existing provider evidence. "
            "'outcome_unknown' returns verdict=MANUAL_REVIEW when confirmed, never VERIFIED/FAILED."
        ),
    )
    parser.add_argument("--approval-record-id", default=None,
                         help="Approvals record id (auto-discovered by contract_id if omitted)")
    parser.add_argument("--provider-table", default=None,
                         help="Airtable table the provider write landed in (required with "
                              "--expected-outcome completed)")
    parser.add_argument("--provider-record-id", default=None,
                         help="Airtable record id the provider write produced (required with "
                              "--expected-outcome completed)")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON instead of text")
    args = parser.parse_args()

    try:
        result = verify_canary(
            contract_id=args.contract_id,
            expected_outcome=args.expected_outcome,
            approval_record_id=args.approval_record_id,
            provider_table=args.provider_table,
            provider_record_id=args.provider_record_id,
        )
    except Exception as exc:
        err = {"error": f"{type(exc).__name__}: {exc}", "verdict": "FAILED"}
        print(json.dumps(err, indent=2), file=sys.stderr)
        dump_json_report(REPORT_PATH, err)
        return 2

    dump_json_report(REPORT_PATH, result)

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    else:
        _print_human(result)

    # 0 = VERIFIED, 1 = FAILED, 3 = MANUAL_REVIEW (neither a clean pass nor
    # a hard failure — a human must look at an outcome_unknown result).
    if result["verdict"] == "VERIFIED":
        return 0
    if result["verdict"] == "MANUAL_REVIEW":
        return 3
    return 1


if __name__ == "__main__":
    sys.exit(main())
