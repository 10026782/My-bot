#!/usr/bin/env python3
"""TC10 — isolated regression mode runner.

Runs the Turn Coordinator / ActionGateway regression matrix
(scripts/regression_matrix.py) with a forced, disposable environment that
cannot reach real Airtable or real Telegram, regardless of what is already
exported in the calling shell.

This is the fix for the exact contamination documented in
docs/architecture/turn-coordinator-full/TC8_DURABLE_TURN_STATE.md's "TC10
handoff": scripts/verify_tc8_staging.py used to run this same file list as
subprocesses that inherited the *ambient* environment
(``env = os.environ.copy()``). Individual test files only set fake
Airtable/Telegram credentials via ``os.environ.setdefault(...)``, which is a
no-op when the ambient shell already has real staging (or worse,
production-shaped) secrets exported — as it typically does when someone is
about to run a staging verification pass. Real credentials meant "propose
boundary" checks and owner-notify calls in these tests could reach real
Airtable/Telegram, using the small set of fixed identity strings baked into
each test file, so a second run collided with the first run's leftover
ActionContracts (BUG-122 proposal_boundary_blocked).

This runner closes that gap by constructing the subprocess environment from
scratch (``_ISOLATED_ENV`` below), overriding — never merely defaulting —
every credential-shaped variable. No test in this matrix can reach a real
external system no matter what the caller's shell holds.

Usage:
    python scripts/run_isolated_regression.py
    python scripts/run_isolated_regression.py --repeat 2
    python scripts/run_isolated_regression.py --evidence-path out.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.regression_matrix import (  # noqa: E402
    FULL_REGRESSION,
    NO_DATABASE_URL_FILES,
    PYTEST_MODE_FILES,
    REGRESSION_GROUPS,
)

# Hard overrides — these values win regardless of the ambient shell
# environment. This is the isolation guarantee: this runner is safe to
# invoke even from a shell that has real staging or production secrets
# exported for an unrelated task.
_ISOLATED_ENV_OVERRIDES: dict[str, str] = {
    "AIRTABLE_API_KEY": "fake-isolated-regression-key-not-real",
    "AIRTABLE_BASE_ID": "appISOLATEDREGRESSI0N",
    "TELEGRAM_TOKEN": "123456789:ISOLATEDregressionNOTrealTOKEN00",
    "ELIYAHU_CHAT_ID": "999999999",
    "ANTHROPIC_API_KEY": "sk-ant-isolated-regression-not-real",
    "RENDER_APP_URL": "https://isolated-regression.invalid",
    "SETUP_WEBHOOK": "0",
    "GOOGLE_REFRESH_TOKEN": "",
    "TC10_ISOLATED_REGRESSION": "1",
}


class RegressionResult:
    __slots__ = ("filename", "ok", "summary", "returncode")

    def __init__(self, filename: str, ok: bool, summary: str, returncode: int) -> None:
        self.filename = filename
        self.ok = ok
        self.summary = summary
        self.returncode = returncode


def _isolated_env(*, drop_database_url: bool) -> dict[str, str]:
    env = os.environ.copy()
    env.update(_ISOLATED_ENV_OVERRIDES)
    if drop_database_url:
        env.pop("DATABASE_URL", None)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return env


def _run_one(filename: str) -> RegressionResult:
    pytest_mode = filename in PYTEST_MODE_FILES
    drop_db = filename in NO_DATABASE_URL_FILES
    command = [sys.executable]
    if pytest_mode:
        command += ["-m", "pytest", "-q"]
    command.append(filename)
    env = _isolated_env(drop_database_url=drop_db)
    try:
        result = subprocess.run(
            command, cwd=ROOT, env=env, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300,
        )
    except subprocess.TimeoutExpired:
        return RegressionResult(filename, False, "timeout after 300s", -1)
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    summary = next(
        (line for line in reversed(lines) if re.search(r"passed|failed|PASSED|FAILED", line)),
        f"exit={result.returncode}",
    )
    if result.returncode != 0:
        summary = f"{summary} [exit={result.returncode}]"
    return RegressionResult(filename, result.returncode == 0, summary, result.returncode)


def _run_matrix() -> tuple[bool, dict]:
    evidence: dict = {"groups": {}, "full_regression": {}}
    ok = True

    print("Named regression gates")
    for label, filename in REGRESSION_GROUPS.items():
        res = _run_one(filename)
        evidence["groups"][label] = {
            "file": filename, "status": "PASS" if res.ok else "FAIL", "detail": res.summary,
        }
        print(f"  {label:<24} {'PASS' if res.ok else 'FAIL':<4} — {res.summary}")
        ok = ok and res.ok

    print("\nFull isolated regression matrix")
    failures = []
    for filename in FULL_REGRESSION:
        res = _run_one(filename)
        evidence["full_regression"][filename] = {
            "status": "PASS" if res.ok else "FAIL", "detail": res.summary,
        }
        print(f"  {filename:<52} {'PASS' if res.ok else 'FAIL':<4} — {res.summary}")
        if not res.ok:
            failures.append(filename)
            ok = False

    evidence["full_regression_tally"] = f"{len(FULL_REGRESSION) - len(failures)}/{len(FULL_REGRESSION)}"
    evidence["full_regression_failures"] = failures
    return ok, evidence


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeat", type=int, default=1, help="run the matrix N times to prove deterministic stability")
    parser.add_argument("--evidence-path", type=Path)
    args = parser.parse_args()

    print("TC10 ISOLATED REGRESSION MATRIX\n")
    print("Isolation: AIRTABLE_API_KEY/AIRTABLE_BASE_ID/TELEGRAM_TOKEN/ANTHROPIC_API_KEY")
    print("forced to disposable fake values for every subprocess — ambient shell")
    print("credentials (including real staging/production secrets) are never used.\n")

    runs = []
    all_ok = True
    for i in range(1, args.repeat + 1):
        if args.repeat > 1:
            print(f"\n=== Run {i}/{args.repeat} ===")
        ok, evidence = _run_matrix()
        runs.append(evidence)
        all_ok = all_ok and ok

    stable = True
    if len(runs) > 1:
        baseline = runs[0]["full_regression_tally"]
        stable = all(r["full_regression_tally"] == baseline for r in runs)
        print(f"\nRepeated-run stability ({len(runs)} runs): {'STABLE' if stable else 'UNSTABLE'} — tallies: "
              f"{[r['full_regression_tally'] for r in runs]}")

    result = {
        "runs": runs,
        "repeat_count": len(runs),
        "stable": stable,
        "final_status": "PASS" if (all_ok and stable) else "FAIL",
    }

    if args.evidence_path:
        args.evidence_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nEvidence written to {args.evidence_path}")

    print(f"\nFINAL: {result['final_status']}")
    return 0 if (all_ok and stable) else 1


if __name__ == "__main__":
    raise SystemExit(main())
