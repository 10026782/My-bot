"""TRACK 3 — real staging verification for BUG-157 / BUG-160 / BUG-163.

Run this from a Render Shell on the ``my-bot-approval-staging`` service
(NOT from a local/CI machine — it needs the real staging env vars: Airtable
credentials, DATABASE_URL if FEATURE_ACTION_CONTRACT_PERSISTENCE is on,
etc., which only exist inside that container). It cannot be run against
production per the task's own rule ("אין לבצע race test ראשון בפרודקשן").

    cd ~/project/src   # or wherever Render's shell drops you — repo root
    python3 scripts/verify_bug157_160_163_staging.py
    python3 scripts/verify_bug157_160_163_staging.py --include-approval-race

What it does, by part:

  Part 1 (BUG-160) and Part 2 (BUG-163) call the real, live
  ``core.router.router.route_request()`` directly, in-process, with the
  exact input strings from the BUG_AUDIT_LOG.md reports. ``route_request()``
  is pure classification (no DB/Airtable access), so these two parts have
  ZERO side effects and always run.

  Part 3 (BUG-157) exercises the real ``core.action_gateway.action_gateway``
  singleton — the same object the live webhook uses — under genuine
  concurrent threads, using a disposable identity (scripts.staging_identity)
  so it can never collide with real user data. By default it only proposes
  contracts (writes to the ActionContracts table) and cleans them up
  afterward via ``cleanup_run_contracts()`` — it never approves/executes,
  so it never touches a real business table (Tasks). Pass
  ``--include-approval-race`` to additionally run the approval-race /
  execution-claim-race check (invariants C/D/E), which DOES execute one
  real Airtable Tasks write — the script deletes that record afterward on a
  best-effort basis, but you are creating real staging data if you pass
  this flag.

Prints PASS/FAIL per check and a final JSON evidence blob. Exits 1 if any
check failed.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from identity import Role  # noqa: E402
from core.router.router import route_request  # noqa: E402
from core.action_gateway import action_gateway as gateway  # noqa: E402
from scripts.staging_identity import (  # noqa: E402
    new_run_namespace,
    unique_identity,
    cleanup_run_contracts,
)

EVIDENCE: dict = {"routing": {}, "bug157": {}}
FAILED: list[str] = []


def _record(section: str, label: str, ok: bool, detail: str = "") -> None:
    EVIDENCE[section][label] = {"status": "PASS" if ok else "FAIL", "detail": detail}
    print(f"{'✅' if ok else '❌'} [{section}] {label}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAILED.append(f"{section}:{label}")


def _commit_and_flags() -> None:
    commit = os.environ.get("RENDER_GIT_COMMIT", "").strip()
    if not commit:
        try:
            commit = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, timeout=5
            ).strip()
        except Exception:
            commit = "unknown"
    print(f"running commit: {commit}")
    for flag in (
        "FEATURE_ACTION_GATEWAY",
        "FEATURE_ACTION_CONTRACT_PERSISTENCE",
        "FEATURE_ATOMIC_CLAIMS",
        "FEATURE_SINGLE_SPEAKER_APPROVAL_UX",
        "FEATURE_DETERMINISTIC_APPROVAL_COST_CUTS",
    ):
        print(f"  {flag}={os.environ.get(flag, '<unset>')}")
    EVIDENCE["commit"] = commit


# ══════════════════════════════════════════════════
# Part 1 — BUG-160: unbalanced quote must not bypass the deterministic route
# ══════════════════════════════════════════════════

def run_bug160(identity) -> None:
    print("\n── BUG-160: unbalanced quote / create_task routing ──")

    # Exact reported input (BUG_AUDIT_LOG.md, opening quote, no closing quote).
    decision = route_request(
        '"צור משימה בדיקת PR546 עד תאריך 12-08-26 בשעה 14:54',
        "telegram", identity,
    )
    _record(
        "routing", "BUG-160 unbalanced-quote create_task -> deterministic tool",
        decision.intent == "create_task" and decision.handler == "tool",
        f"intent={decision.intent} handler={decision.handler} risk={decision.risk}",
    )

    # Regression: balanced quotes must still work exactly as before.
    decision = route_request('"צור משימה בדיקה"', "telegram", identity)
    _record(
        "routing", "BUG-160 regression: balanced quotes still deterministic",
        decision.intent == "create_task" and decision.handler == "tool",
        f"intent={decision.intent} handler={decision.handler}",
    )


# ══════════════════════════════════════════════════
# Part 2 — BUG-163: complete_task/update_task natural-language coverage
# ══════════════════════════════════════════════════

def run_bug163(identity) -> None:
    print("\n── BUG-163: complete_task/update_task intent coverage ──")

    cases = [
        ('השלם את המשימה בדיקת Complete לא קיימת', "complete_task"),
        ('סמן משימת מעקב כבוצעה', "complete_task"),
        # Precedence: "עדכן" must still win UPDATE_TASK, not get swallowed
        # by the new COMPLETE_TASK "...כבוצע" pattern.
        ('עדכן משימת מעקב לסטטוס בוצע', "update_task"),
        # Must not false-positive against LIST_TASKS.
        ('תראה לי אילו משימות כבר בוצעו', "list_tasks"),
    ]
    for text, expected_intent in cases:
        decision = route_request(text, "telegram", identity)
        _record(
            "routing", f"BUG-163 '{text}' -> intent={expected_intent}",
            decision.intent == expected_intent,
            f"got intent={decision.intent} handler={decision.handler}",
        )


# ══════════════════════════════════════════════════
# Part 3 — BUG-157: real concurrency against the live ActionGateway
# ══════════════════════════════════════════════════

def run_bug157_creation_race(identity, run_id: str, race_count: int) -> str | None:
    print(f"\n── BUG-157A/B: real {race_count}-way propose_action() race (ActionContracts only) ──")

    tool_inputs = {
        "table": "משימות (Tasks)",
        "fields": {"כותרת המשימה": f"[TC3-VERIFY] BUG-157 creation race {run_id}"},
    }
    results: list = [None] * race_count
    barrier = threading.Barrier(race_count)

    def worker(i: int) -> None:
        barrier.wait(timeout=5)
        results[i] = gateway.propose_action(
            tenant_id=identity.tenant_id,
            canonical_user_id=identity.memory_key,
            tool_name="airtable_add",
            tool_inputs=tool_inputs,
            origin_channel="telegram",
            origin_chat_id=identity.external_id,
            requires_approval=True,
            identity=identity,
            trusted_source="deterministic_create_task",
            user_text="[TC3 staging verification — safe to ignore/reject]",
        )

    threads = [threading.Thread(target=worker, args=(i,), daemon=True) for i in range(race_count)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=15)

    returned = [r for r in results if r is not None]
    _record("bug157", "A. all concurrent calls returned (no hang)", len(returned) == race_count,
            f"{len(returned)}/{race_count} returned")

    winners = [r for r in returned if r.ok]
    _record("bug157", "A. exactly one live contract created", len(winners) == 1,
            f"{len(winners)} winners, contract_ids={[w.contract_id for w in winners]}")

    winner_id = winners[0].contract_id if winners else None
    losers = [r for r in returned if not r.ok]
    dedup_ok = winner_id is not None and all(
        (l.contract_id == winner_id) for l in losers if l.contract_id
    )
    _record("bug157", "A. every loser dedups against the winner's contract_id",
            dedup_ok, f"{len(losers)} losers")

    if winner_id:
        again = gateway.propose_action(
            tenant_id=identity.tenant_id,
            canonical_user_id=identity.memory_key,
            tool_name="airtable_add",
            tool_inputs=tool_inputs,
            origin_channel="telegram",
            origin_chat_id=identity.external_id,
            requires_approval=True,
            identity=identity,
            trusted_source="deterministic_create_task",
            user_text="[TC3 staging verification — duplicate pending suppression]",
        )
        _record("bug157", "B. post-race duplicate pending suppression",
                (not again.ok) and again.contract_id == winner_id,
                f"ok={again.ok} contract_id={again.contract_id}")

    return winner_id


def run_bug157_approval_race(identity, run_id: str) -> None:
    print("\n── BUG-157 C/D/E: approval race / execution-claim race (REAL Tasks write) ──")
    print("    ⚠️  this creates one real record in the staging Tasks table")

    tool_inputs = {
        "table": "משימות (Tasks)",
        "fields": {"כותרת המשימה": f"[TC3-VERIFY] BUG-157 approval race {run_id} — safe to delete"},
    }
    proposal = gateway.propose_action(
        tenant_id=identity.tenant_id,
        canonical_user_id=identity.memory_key,
        tool_name="airtable_add",
        tool_inputs=tool_inputs,
        origin_channel="telegram",
        origin_chat_id=identity.external_id,
        requires_approval=True,
        identity=identity,
        trusted_source="deterministic_create_task",
        user_text="[TC3 staging verification — approval race]",
    )
    if not proposal.ok:
        _record("bug157", "C. setup: fresh contract proposed", False, str(proposal.reason))
        return
    contract_id = proposal.contract_id
    _record("bug157", "C. setup: fresh contract proposed", True, f"contract_id={contract_id}")

    race_n = 3
    results: list = [None] * race_n
    barrier = threading.Barrier(race_n)

    def approver(i: int) -> None:
        barrier.wait(timeout=5)
        results[i] = gateway.approve_with_lifecycle_result(
            contract_id, approver=identity.external_id, approver_role="owner",
        )

    threads = [threading.Thread(target=approver, args=(i,), daemon=True) for i in range(race_n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=20)

    returned = [r for r in results if r is not None]
    _record("bug157", "C. all concurrent approve calls returned (no hang)", len(returned) == race_n,
            f"{len(returned)}/{race_n} returned")
    for i, r in enumerate(returned):
        print(f"    caller {i}: canonical_state={r.canonical_state} is_final={r.is_final}")

    # EMERGENCY_STOP_ALL blocks every write tool (tools/dispatcher.py:156)
    # independently of BUG-157's claim/execution logic. If it's on, the one
    # execution attempt that *does* win the claim will fail for that
    # unrelated reason — expected here, not a BUG-157 regression. Surfaced
    # explicitly so a 0-Tasks-record result below isn't misread as evidence
    # of anything concurrency-related.
    try:
        import feature_flags as _ff
        emergency_stop_active = _ff.is_enabled("EMERGENCY_STOP_ALL")
    except Exception:
        emergency_stop_active = None
    print(f"    EMERGENCY_STOP_ALL active: {emergency_stop_active}")

    # C/D — single execution owner: exactly one non-"repeated" claimant
    # should exist (the caller whose own approve() call actually flipped
    # status away from "pending"); every other concurrent caller must have
    # observed an already-non-pending contract, never executed a second
    # time. canonical_state alone doesn't distinguish "I executed" from "I
    # merely observed the winner's result" when both land on the same
    # terminal state, so this counts distinct execution *attempts* via the
    # real business-side effect instead (below), and here only checks that
    # no caller was left in a non-terminal state.
    non_final = [r for r in returned if not r.is_final]
    _record("bug157", "C. every returned result is final (no caller left hanging mid-execution)",
            len(non_final) == 0, f"{len(non_final)} non-final result(s)")

    settled_before_replay = gateway.find_contract(contract_id)
    status_before_replay = settled_before_replay.status if settled_before_replay else None

    # Replay after the race has fully resolved — must stay idempotent: it
    # must not change contract status again (i.e. must not trigger a
    # second execution attempt), regardless of whether the original
    # execution attempt itself succeeded or failed for an unrelated reason
    # (e.g. EMERGENCY_STOP_ALL).
    time.sleep(0.5)
    replay = gateway.approve_with_lifecycle_result(
        contract_id, approver=identity.external_id, approver_role="owner",
    )
    settled_after_replay = gateway.find_contract(contract_id)
    status_after_replay = settled_after_replay.status if settled_after_replay else None
    _record("bug157", "E. replay-after-claim stays idempotent (no second execution)",
            status_after_replay == status_before_replay,
            f"status before replay={status_before_replay!r} after replay={status_after_replay!r} "
            f"replay canonical_state={replay.canonical_state}")

    # Best-effort cleanup + the real double-execution smoking gun: however
    # many Tasks records exist for this run's unique title, there must
    # never be more than one — 0 is a legitimate outcome (e.g. the one
    # allowed execution attempt failed, whether due to EMERGENCY_STOP_ALL
    # or anything else unrelated to the race itself), but 2+ would mean two
    # concurrent callers both actually wrote, which is exactly the defect
    # BUG-157's atomic claim exists to prevent.
    try:
        from tools.airtable_gateway import at_list_by_formula, airtable_delete, _safe_formula_param
        formula = f"FIND('{_safe_formula_param(run_id)}', {{כותרת המשימה}}) > 0"
        records = at_list_by_formula("משימות (Tasks)", formula)
        matched = [rec for rec in records if rec.get("id")]
        _record("bug157", "D. at most one Tasks record created by the race (no double execution)",
                len(matched) <= 1,
                f"found {len(matched)} record(s); final contract status={status_after_replay!r}; "
                f"emergency_stop_active={emergency_stop_active}")
        for rec in matched:
            airtable_delete("משימות (Tasks)", rec["id"], source="tc3_verify_cleanup")
        print(f"    cleaned up {len(matched)} Tasks record(s)")
    except Exception as exc:
        print(f"    ⚠️  Tasks cleanup/verification failed (not fatal to the check above): {exc}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--include-approval-race", action="store_true",
                         help="also run BUG-157 C/D/E (real Tasks-table write)")
    parser.add_argument("--race-count", type=int, default=5,
                         help="concurrent propose_action() callers for BUG-157 A/B (default 5)")
    args = parser.parse_args()

    _commit_and_flags()

    run_id = new_run_namespace()
    identity = unique_identity(Role.OWNER, run_id=run_id, label="tc3verify")
    print(f"\nrun_id={run_id}")

    run_bug160(identity)
    run_bug163(identity)

    winner_id = None
    try:
        winner_id = run_bug157_creation_race(identity, run_id, args.race_count)
    finally:
        if winner_id:
            try:
                gateway.reject_with_lifecycle_result(winner_id, rejected_by=f"tc3verify:{run_id}")
            except Exception as exc:
                print(f"    ⚠️  could not reject {winner_id} during cleanup: {exc}")

    if args.include_approval_race:
        run_bug157_approval_race(identity, run_id)
    else:
        print("\n(skipping BUG-157 C/D/E approval-race check — pass --include-approval-race to run it)")

    deleted = cleanup_run_contracts(run_id)
    print(f"\ncleanup_run_contracts: deleted={deleted} ActionContract record(s) for run_id={run_id}")

    print("\n" + "=" * 60)
    print(json.dumps(EVIDENCE, ensure_ascii=False, indent=2))
    print("=" * 60)
    if FAILED:
        print(f"\n❌ {len(FAILED)} check(s) FAILED: {FAILED}")
        return 1
    print("\n✅ all checks PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
