#!/usr/bin/env python3
"""TC10 — isolated regression mode runner.

Runs the Turn Coordinator / ActionGateway regression matrix
(scripts/regression_matrix.py) with Airtable credentials forced to a
disposable, non-functional value regardless of what is already exported in
the calling shell.

This is the fix for the exact contamination documented in
docs/architecture/turn-coordinator-full/TC8_DURABLE_TURN_STATE.md's "TC10
handoff": scripts/verify_tc8_staging.py used to run this same file list as
subprocesses that inherited the *ambient* environment
(``env = os.environ.copy()``). Individual test files only set fake Airtable
credentials via ``os.environ.setdefault(...)``, which is a no-op when the
ambient shell already has real staging (or worse, production-shaped)
secrets exported — as it typically does when someone is about to run a
staging verification pass. Real credentials meant "propose boundary" checks
in these tests could reach real Airtable, using the small set of fixed
identity strings baked into each test file, so a second run collided with
the first run's leftover ActionContracts (BUG-122
proposal_boundary_blocked).

This runner closes that gap by hard-overriding — never merely defaulting —
``AIRTABLE_API_KEY``/``AIRTABLE_BASE_ID`` for every subprocess. No test in
this matrix can reach real Airtable no matter what the caller's shell
holds; that credential is the one this repo's own CI convention
(``.github/workflows/ci.yml``) already treats as unsafe to hold real values
in a unit-test job, for the same BUG-122-shaped reason.

TELEGRAM_TOKEN / ELIYAHU_CHAT_ID / ANTHROPIC_API_KEY are deliberately left
untouched — this runner passes through whatever the calling environment
already provides for them, exactly like CI's pre-existing "Run test_*.py
scripts" step does (which sources them from ``secrets.TELEGRAM_TOKEN``/
``secrets.ANTHROPIC_API_KEY``). This was learned the hard way: an earlier
version of this script also force-overrode ``TELEGRAM_TOKEN``/
``ELIYAHU_CHAT_ID`` to fake values as a defense-in-depth measure, on the
theory that no test should be able to reach real Telegram. That broke
test_tc6_app_reply_ownership.py and test_pa01_phantom_approval_enforcement.py
(52/52 -> 44/52 and similar), which have several scenarios that
deliberately exercise the real (unmocked) owner-notify call and assert on
it *succeeding* — confirmed by comparing this PR's own CI run of both the
pre-existing step (52/52, real secrets.TELEGRAM_TOKEN) and this script
(44/52, forced-fake token) on the same commit. Overriding Telegram
credentials here would silently change what these tests exercise, which is
exactly the kind of "weakening a suite to get to green" this harness is
required not to do — so the safer fix is to match the trust boundary this
repository's CI already accepts for Telegram/Anthropic (dedicated,
repo-scoped secrets, not "whatever happens to be in the shell"), and keep
the hard override narrowly scoped to the one credential with a proven
contamination mechanism (Airtable). If you run this locally, do not export
real production Telegram credentials into that shell first — the same
caution that already applies to running any of these test files directly.

Usage:
    python3 scripts/run_isolated_regression.py
    python3 scripts/run_isolated_regression.py --repeat 2
    python3 scripts/run_isolated_regression.py --evidence-path out.json
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

# Hard override — wins regardless of the ambient shell environment. This is
# the isolation guarantee for the one credential with a proven cross-run
# contamination mechanism (BUG-122, see module docstring). TELEGRAM_TOKEN /
# ELIYAHU_CHAT_ID / ANTHROPIC_API_KEY are intentionally NOT here — see the
# module docstring for why forcing those broke real test assertions.
_ISOLATED_ENV_OVERRIDES: dict[str, str] = {
    "AIRTABLE_API_KEY": "fake-isolated-regression-key-not-real",
    "AIRTABLE_BASE_ID": "appISOLATEDREGRESSI0N",
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

    if args.repeat < 1:
        parser.error("--repeat must be >= 1 (0 or negative would run nothing and report a false PASS)")

    print("TC10 ISOLATED REGRESSION MATRIX\n")
    print("Isolation: AIRTABLE_API_KEY/AIRTABLE_BASE_ID forced to disposable fake")
    print("values for every subprocess, regardless of ambient shell credentials —")
    print("this is the proven BUG-122 contamination fix (see module docstring).\n")

    runs = []
    all_ok = True
    for i in range(1, args.repeat + 1):
        if args.repeat > 1:
            print(f"\n=== Run {i}/{args.repeat} ===")
        ok, evidence = _run_matrix()
        runs.append(evidence)
        all_ok = all_ok and ok

    def _outcomes(evidence: dict) -> dict[str, str]:
        outcomes = {label: item["status"] for label, item in evidence["groups"].items()}
        outcomes.update(
            (filename, item["status"]) for filename, item in evidence["full_regression"].items()
        )
        return outcomes

    stable = True
    if len(runs) > 1:
        baseline = _outcomes(runs[0])
        stable = all(_outcomes(r) == baseline for r in runs[1:])
        tallies = [r["full_regression_tally"] for r in runs]
        print(f"\nRepeated-run stability ({len(runs)} runs): {'STABLE' if stable else 'UNSTABLE'} — "
              f"per-file outcomes {'identical' if stable else 'DIFFERED'} across runs, tallies: {tallies}")

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
