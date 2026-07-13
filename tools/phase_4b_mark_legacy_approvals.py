#!/usr/bin/env python3
# tools/phase_4b_mark_legacy_approvals.py — Phase 4B legacy Approvals marking.
#
# Default mode is --report-only (also the default with no flags at all — you
# must pass BOTH --apply AND --confirm APPLY_LEGACY_READ_ONLY to write
# anything). The only permitted mutation is setting
# ApprovalsFields.LEGACY_READ_ONLY = true on Approvals rows that have no
# action_contract_id. Nothing else is ever touched:
#   - never deletes rows
#   - never creates ActionContracts for old rows
#   - never replays or clears CONTEXT_DATA
#   - never changes STATUS
#   - never changes projected_lifecycle_status
#   - never approves/rejects/actions anything
#
# Idempotent: a row already legacy_read_only=true is left alone (not
# re-patched, not counted as a pending candidate on a second run).
#
# Run manually:
#   python3 tools/phase_4b_mark_legacy_approvals.py --report-only
#   python3 tools/phase_4b_mark_legacy_approvals.py --apply --confirm APPLY_LEGACY_READ_ONLY
#
# Produces reports/phase_4b_legacy_marking.json.

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from airtable_schema import ApprovalsFields  # noqa: E402
from tools.phase_4b_rollout_common import (  # noqa: E402
    REPO_ROOT, dump_json_report, fetch_all_approvals, git_state, utc_now_iso,
)

REPORT_PATH = REPO_ROOT / "reports" / "phase_4b_legacy_marking.json"
_CONFIRM_TOKEN = "APPLY_LEGACY_READ_ONLY"


def _find_candidates(approvals: list[dict]) -> list[dict]:
    """Rows with no action_contract_id and legacy_read_only not already true.
    Idempotent — a row already marked is not a candidate on a later run."""
    return [
        row for row in approvals
        if not row.get("fields", {}).get(ApprovalsFields.ACTION_CONTRACT_ID)
        and row.get("fields", {}).get(ApprovalsFields.LEGACY_READ_ONLY) is not True
    ]


def run(apply: bool, confirm: str | None) -> dict:
    approvals = fetch_all_approvals()
    if approvals is None:
        return {
            "generated_at": utc_now_iso(),
            "git": git_state(),
            "mode": "apply" if apply else "report-only",
            "error": "could not fetch Approvals table — no changes attempted",
            "candidate_record_ids": [],
            "applied_record_ids": [],
            "failed_record_ids": [],
        }

    candidates = _find_candidates(approvals)
    candidate_ids = sorted(row["id"] for row in candidates)

    will_apply = apply and confirm == _CONFIRM_TOKEN

    result = {
        "generated_at": utc_now_iso(),
        "git": git_state(),
        "mode": "apply" if will_apply else "report-only",
        "apply_requested": apply,
        "confirm_token_matched": confirm == _CONFIRM_TOKEN,
        "candidate_count": len(candidate_ids),
        "candidate_record_ids": candidate_ids,
        "applied_record_ids": [],
        "failed_record_ids": [],
    }

    if apply and not will_apply:
        result["refused_reason"] = (
            "--apply was passed without the exact --confirm APPLY_LEGACY_READ_ONLY token "
            "— no write attempted"
        )
        return result

    if not will_apply:
        return result

    from tools.airtable_gateway import airtable_patch

    applied, failed = [], []
    for record_id in candidate_ids:
        ok = airtable_patch(
            "Approvals", record_id,
            {ApprovalsFields.LEGACY_READ_ONLY: True},
            source="phase_4b_mark_legacy_approvals",
        )
        (applied if ok else failed).append(record_id)

    result["applied_record_ids"] = sorted(applied)
    result["failed_record_ids"] = sorted(failed)
    return result


def _print_human(result: dict) -> None:
    print("Phase 4B Legacy Approvals Marking")
    print("=" * 60)
    print(f"generated_at: {result['generated_at']}")
    print(f"mode: {result['mode']}")
    if "error" in result:
        print(f"ERROR: {result['error']}")
        return
    print(f"candidates (no action_contract_id, not already legacy_read_only): "
          f"{result['candidate_count']}")
    for rid in result["candidate_record_ids"]:
        print(f"  - {rid}")
    if result.get("refused_reason"):
        print(f"\nREFUSED: {result['refused_reason']}")
    if result["mode"] == "apply":
        print(f"\napplied: {len(result['applied_record_ids'])}")
        print(f"failed:  {len(result['failed_record_ids'])}")
        for rid in result["failed_record_ids"]:
            print(f"  FAILED: {rid}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Mark pre-4B-2 Approvals rows legacy_read_only=true (report-only by default)"
    )
    parser.add_argument("--report-only", action="store_true",
                         help="Explicit report-only mode (also the default with no flags)")
    parser.add_argument("--apply", action="store_true",
                         help="Attempt the write — requires --confirm APPLY_LEGACY_READ_ONLY too")
    parser.add_argument("--confirm", default=None,
                         help="Must be exactly APPLY_LEGACY_READ_ONLY to allow a write")
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
    if result["mode"] == "apply" and result["failed_record_ids"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
