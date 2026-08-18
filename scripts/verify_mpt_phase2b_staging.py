#!/usr/bin/env python3
"""MPT Phase 2B — controlled staging verification of the canonical submit path.

Proves external_execution.submit is reachable ONLY through the real,
production-shaped path:

    fresh disposable ActionContract -> canonical approval (ActionGateway)
    -> dispatcher -> ExternalExecutionBoundary -> MoneyPrinterTurboAdapter

Deliberately does NOT:
  - expose external_execution.submit to Telegram/the model: this script
    calls core.action_gateway.action_gateway.propose_action()/approve()
    directly in-process, the same way scripts/verify_tc9_staging.py does —
    it never touches app.py's handlers or the tool-use loop. The tool
    itself is already model_exposed=False in tool_registry.py.
  - add a permanent CLI command: this is a scripts/verify_*_staging.py
    canary, matching the existing convention (verify_tc8/tc9/f15/bug157...),
    not something wired into app.py.
  - call MoneyPrinterTurboAdapter directly: submission happens exclusively
    via get_default_boundary(), the same singleton tools/dispatcher.py and
    scheduler.py use.
  - bypass approval semantics: propose_action(requires_approval=True) then
    a separate approve() call, exactly the two-step ceremony production
    uses (BUG-091 identity/trusted_source handling included).

Staging-safe by construction (same pattern as verify_tc9_staging.py):
  - every identity comes from scripts.staging_identity.unique_identity(),
    so a run can never collide with a contract left behind by a previous
    run or engineer (BUG-122).
  - cleanup removes only this run's disposable ActionContract (scoped by
    tenant_id=run_id). It deliberately does NOT touch the resulting
    ExternalExecutionJob record — that row is the real Phase 2B evidence
    (daily/concurrency counters, provider polling) and must survive.

Completion polling is NOT reimplemented here: scheduler.py's
_job_external_execution_poll() already calls get_default_boundary().poll_due()
every 2 minutes whenever EXTERNAL_EXECUTION_ENABLED is on and the app's
scheduler thread is alive — that is the canonical poller. --wait only
re-reads the job record (read-only, no mutation) to show status as the
real scheduler updates it.

Preconditions this script assumes are already set for the test window
(it does not set them — see the operator checklist that produced this
script):
  MPT_MAX_EXECUTIONS_PER_DAY=3   (checked below against --expect-max-per-day)
  EXTERNAL_EXECUTION_ENABLED=true
  EMERGENCY_STOP_ALL=false only if the canonical run cannot proceed at true
    (external_execution.submit is blocked_by_emergency=True in
    tool_registry.py, so it MUST be false for this run to reach the adapter)

CAUTION: EMERGENCY_STOP_ALL is a durable, Airtable-backed flag with no
per-environment scoping in code (core/emergency_stop.py has no
tenant/service axis). If staging and production share one Airtable base
(this repo has exactly one documented base — see
docs/PHASE_4B_ROLLOUT_AND_CUTOVER.md — and no confirmed separate staging
base), flipping it off here flips it off wherever else reads that same
flag record. Confirm the staging AIRTABLE_BASE_ID is distinct from
production's before changing EMERGENCY_STOP_ALL. This script does not
change it and does not verify that isolation for you.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class VerificationFailure(RuntimeError):
    pass


def _preflight(evidence: dict, expect_max_per_day: int) -> None:
    for var in ("DATABASE_URL", "AIRTABLE_API_KEY", "AIRTABLE_BASE_ID", "TELEGRAM_TOKEN"):
        if not os.getenv(var, "").strip():
            raise VerificationFailure(f"{var} is not configured — this is a staging-only script")
    if os.getenv("MPT_PHASE2B_STAGING_NON_PRODUCTION", "").lower() != "true":
        raise VerificationFailure(
            "set MPT_PHASE2B_STAGING_NON_PRODUCTION=true to confirm this target is "
            "non-production staging — this script creates a real ActionContract "
            "and, if capacity/flags allow, launches a real MPT render process"
        )
    db_url = os.getenv("DATABASE_URL", "")
    if not any(t in db_url.lower() for t in ("staging", "sandbox", "test", "dev")):
        raise VerificationFailure(
            "DATABASE_URL does not look like a non-production database "
            "(expected staging/sandbox/test/dev in the name) — refusing to run"
        )

    from core.mpt_runtime_policy import MPTExecutionPolicy
    policy = MPTExecutionPolicy.from_env()
    print(f"{'Policy — max_concurrent':<40} {policy.max_concurrent}")
    print(f"{'Policy — max_per_day':<40} {policy.max_per_day}")
    print(f"{'Policy — max_runtime_seconds':<40} {policy.max_runtime_seconds}")
    print(f"{'Policy — runtime_profile':<40} {policy.runtime_profile or '(unset)'}")
    if policy.max_per_day != expect_max_per_day:
        raise VerificationFailure(
            f"MPTExecutionPolicy.from_env().max_per_day == {policy.max_per_day}, "
            f"expected {expect_max_per_day} — the test-window env var is not what "
            f"this process actually loaded; fix before submitting"
        )

    from feature_flags import is_enabled
    print(f"{'EXTERNAL_EXECUTION_ENABLED':<40} {is_enabled('EXTERNAL_EXECUTION_ENABLED')}")
    print(f"{'EMERGENCY_STOP_ALL':<40} {is_enabled('EMERGENCY_STOP_ALL')}")
    evidence["Preflight"] = {"status": "PASS", "max_per_day": policy.max_per_day}
    print(f"{'Preflight':<40} PASS")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--script-file", type=Path, help="Path to the approved script text")
    parser.add_argument("--script", type=str, help="Approved script text inline (alternative to --script-file)")
    parser.add_argument("--media", action="append", required=True,
                         help="Path to an approved media file under MPT_APPROVED_MEDIA_ROOT (repeatable, 1-8)")
    parser.add_argument("--aspect-ratio", default="9:16", choices=("9:16", "16:9", "1:1"))
    parser.add_argument("--voice-profile", default="zh-CN-XiaoxiaoNeural-Female")
    parser.add_argument("--expect-max-per-day", type=int, default=3)
    parser.add_argument("--wait-seconds", type=int, default=0,
                         help="If >0, poll (read-only) the job record for this many seconds after submit")
    parser.add_argument("--evidence-path", type=Path)
    args = parser.parse_args()

    if bool(args.script_file) == bool(args.script):
        parser.error("pass exactly one of --script-file or --script")
    script_text = args.script if args.script else args.script_file.read_text(encoding="utf-8")
    if not script_text.strip():
        parser.error("approved script text is empty")

    evidence: dict = {}
    failed = False
    run_id = None
    print("MPT PHASE 2B — CANONICAL STAGING SUBMIT CANARY\n")

    try:
        # A bare `import app` never bootstraps the Emergency Stop manager
        # (app.py's own module docstring: that is deliberately NOT a side
        # effect of importing the module — only app.run_startup_sequence(),
        # invoked by gunicorn or `python3 app.py`'s __main__ block, does).
        # Without it, feature_flags.is_enabled("EMERGENCY_STOP_ALL") fails
        # closed to True (EmergencyStopNotConfigured -> blocked), so both
        # the preflight print below and the dispatcher's later check would
        # silently report/enforce a block regardless of the real durable
        # flag. bootstrap_emergency_stop() alone (not the full
        # run_startup_sequence()) only constructs the store/manager and
        # does one hydration read — no scheduler thread, no webhook
        # re-registration — safe for a one-off verification process.
        from core.emergency_stop_bootstrap import bootstrap_emergency_stop
        boot = bootstrap_emergency_stop()
        print(f"{'EmergencyStop bootstrap':<40} configured={boot.configured} store_status={boot.store_status}")

        _preflight(evidence, args.expect_max_per_day)

        from scripts.staging_identity import cleanup_run_contracts, new_run_namespace, unique_identity
        from identity import Role
        import app  # noqa: E402  (heavy import, real staging config)
        from core.action_gateway import action_gateway as gw
        from core.external_execution_boundary import get_default_boundary

        run_id = new_run_namespace()
        owner = unique_identity(Role.OWNER, run_id=run_id)
        evidence["run_id"] = run_id
        evidence["identity"] = owner.memory_key
        print(f"{'Run namespace':<40} run_id={run_id}")

        media_refs = [str(Path(m).resolve()) for m in args.media]
        tool_inputs = {
            "approved_script": script_text,
            "script_sha256": hashlib.sha256(script_text.encode("utf-8")).hexdigest(),
            "approved_media_refs": media_refs,
            "aspect_ratio": args.aspect_ratio,
            "voice_profile": args.voice_profile,
        }

        propose = gw.propose_action(
            tenant_id=owner.tenant_id, canonical_user_id=owner.memory_key,
            tool_name="external_execution.submit", tool_inputs=tool_inputs,
            origin_channel="telegram", origin_chat_id=owner.user_id,
            requires_approval=True, identity=owner,
            trusted_source="mpt_phase2b_staging_canary",
        )
        if not propose.ok:
            raise VerificationFailure(f"propose_action rejected: {propose.reason}")
        contract_id = propose.contract_id
        evidence["contract_id"] = contract_id
        print(f"{'Proposed':<40} PASS — contract_id={contract_id}")

        mock_bot = MagicMock()
        with patch.object(app, "bot", mock_bot):
            approve_msg = gw.approve(contract_id, approver=owner.memory_key, approver_role=owner.role)
        contract = gw.find_contract(contract_id)
        contract_status = contract.status if contract else None
        evidence["contract_status"] = contract_status
        evidence["approve_message"] = approve_msg
        print(f"{'Approved':<40} contract_status={contract_status!r} message={approve_msg!r}")

        job = get_default_boundary().repository.get(contract_id)
        if job is None:
            evidence["job"] = {"status": "MISSING"}
            print(f"{'ExternalExecutionJob':<40} MISSING — no durable job record was created")
        else:
            evidence["job"] = {
                "status": job.status,
                "provider_job_id": job.provider_job_id,
                "failure_code": job.failure_code,
                "evidence": job.evidence,
            }
            print(f"{'ExternalExecutionJob':<40} status={job.status!r} provider_job_id={job.provider_job_id!r} "
                  f"failure_code={job.failure_code!r} evidence={job.evidence!r}")

            if args.wait_seconds > 0 and job.status == "submitted":
                deadline = time.time() + args.wait_seconds
                print(f"\nWaiting up to {args.wait_seconds}s (read-only re-reads; the real "
                      "scheduler polls every 2 minutes, this script does not poll the provider itself)...")
                last_status = job.status
                while time.time() < deadline:
                    time.sleep(20)
                    current = get_default_boundary().repository.get(contract_id)
                    if current is None:
                        break
                    if current.status != last_status:
                        print(f"{'  status change':<40} {last_status!r} -> {current.status!r}")
                        last_status = current.status
                    if current.status in {"completed", "failed", "outcome_unknown"}:
                        job = current
                        evidence["job"] = {
                            "status": job.status, "provider_job_id": job.provider_job_id,
                            "failure_code": job.failure_code, "evidence": job.evidence,
                        }
                        break

    except Exception as exc:
        failed = True
        evidence["fatal"] = {"status": "FAIL", "detail": f"{type(exc).__name__}: {exc}"}
        print(f"\nFATAL{'':<35} FAIL — {type(exc).__name__}: {exc}")
    finally:
        if run_id:
            try:
                deleted = cleanup_run_contracts(run_id)
                evidence["cleanup"] = {"status": "PASS", "detail": f"deleted={deleted}"}
                print(f"{'Cleanup (ActionContracts only)':<40} PASS — deleted={deleted} record(s)")
            except Exception as exc:
                failed = True
                evidence["cleanup"] = {"status": "FAIL", "detail": f"{type(exc).__name__}: {exc}"}
                print(f"{'Cleanup':<40} FAIL — {type(exc).__name__}: {exc}")

    if args.evidence_path:
        args.evidence_path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nEvidence written to {args.evidence_path}")

    print("\nFINAL:")
    print("MPT PHASE 2B STAGING CANARY: FAIL" if failed else "MPT PHASE 2B STAGING CANARY: DONE")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
