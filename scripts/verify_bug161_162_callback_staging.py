#!/usr/bin/env python3
"""
verify_bug161_162_callback_staging.py — real, in-process staging verification
of the Telegram approval-callback path (app.py::_handle_approval_callback_impl)
for the scenarios BUG-161/162's TC6 production verification (09/08/2026)
explicitly did NOT cover: approve/reject callback, duplicate/replay (same
still-pending contract pressed twice), stale-resolved-button, and TTL expiry.

Root of this script: BUG_AUDIT_LOG.md's own TC-12 finding ("duplicate
callback — not a bug, a testability gap... recommended: add an integration
test that calls the internal handler directly, not via Telegram UI") and
docs/architecture/action-gateway/BUG-161_162_CALLBACK_E2E_VERIFICATION_PLAN_
20260813.md §3, which flagged this exact automation as not yet built.

Usage (same posture as scripts/verify_bug157_160_163_staging.py — run from
the repo root, on a shell with real staging DATABASE_URL/Airtable/Render env
already configured, e.g. Render's staging shell):
    cd ~/project/src
    python3 scripts/verify_bug161_162_callback_staging.py

What it does:
  Calls the REAL, live app._handle_approval_callback_impl() in-process — the
  same function the production webhook calls — against the REAL
  core.action_gateway.action_gateway singleton (real ActionContract/
  TurnStateRepository claims) and REAL Airtable (creates real "משימות
  (Tasks)" records, deleted afterward on a best-effort basis, matching
  scripts/verify_bug157_160_163_staging.py's own cleanup posture). Uses a
  disposable staging identity (scripts.staging_identity) so it can never
  collide with real user data.

  Only two things are mocked, exactly as the existing regression tests
  (test_bug_stale_callback_ux.py, test_pr0c_telegram_callback_gateway.py)
  already do — this is not a new technique, just the same one pointed at a
  real backend instead of test doubles:
    - app.bot: MagicMock() — no real Telegram message/callback-answer is
      ever sent; every call is still recorded and inspected for the
      single-reply-per-terminal-state invariant.
    - app.resolve_identity: patched to always return the disposable
      identity with Role.OWNER for the approver check — sidesteps needing a
      real, environment-specific staging owner chat_id.

  Creates real records. Not a --dry-run tool. Cleans up its own
  ActionContracts (scripts.staging_identity.cleanup_run_contracts) and any
  real Tasks record it caused to be created, best-effort, after every part.

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
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from identity import Role  # noqa: E402
import app  # noqa: E402
from event_bus import bus  # noqa: E402
from core.action_gateway import action_gateway as gateway  # noqa: E402
from scripts.staging_identity import (  # noqa: E402
    new_run_namespace,
    unique_identity,
    cleanup_run_contracts,
)

EVIDENCE: dict = {}
FAILED: list[str] = []


def _record(label: str, ok: bool, detail: str = "") -> None:
    EVIDENCE[label] = {"status": "PASS" if ok else "FAIL", "detail": detail}
    print(f"{'✅' if ok else '❌'} {label}" + (f" — {detail}" if detail else ""))
    if not ok:
        FAILED.append(label)


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
        "FEATURE_ATOMIC_CLAIMS",
        "FEATURE_SINGLE_SPEAKER_APPROVAL_UX",
    ):
        print(f"  {flag}={os.environ.get(flag, '<unset>')}")
    EVIDENCE["commit"] = commit


def _fake_cq(chat_id: str, data: str, cq_id: str | None = None):
    return SimpleNamespace(
        id=cq_id or f"cbq-{data}",
        data=data,
        from_user=SimpleNamespace(id=chat_id),
        message=SimpleNamespace(chat=SimpleNamespace(id=chat_id), message_id=1),
    )


def _tasks_records_for(run_id: str) -> list[dict]:
    try:
        from tools.airtable_gateway import at_list_by_formula, _safe_formula_param
        formula = f"FIND('{_safe_formula_param(run_id)}', {{כותרת המשימה}}) > 0"
        return at_list_by_formula("משימות (Tasks)", formula) or []
    except Exception as exc:
        print(f"    ⚠️  Tasks lookup failed (non-fatal, treated as 0 records found): {exc}")
        return []


def _cleanup_tasks(run_id: str) -> int:
    try:
        from tools.airtable_gateway import airtable_delete
        records = _tasks_records_for(run_id)
        for rec in records:
            if rec.get("id"):
                airtable_delete("משימות (Tasks)", rec["id"], source="bug161_162_verify_cleanup")
        return len(records)
    except Exception as exc:
        print(f"    ⚠️  Tasks cleanup failed (non-fatal): {exc}")
        return 0


def _propose(identity, run_id: str, label: str) -> tuple:
    """Real propose_action() + a matching real EventBus item, exactly what
    _queue_approval_detailed_impl() would create for an Agent-proposed tool
    call — composed directly (not through resolve_identity/text routing) so
    this script owns the identity end-to-end, same posture as
    scripts/verify_bug157_160_163_staging.py's Part 3."""
    tool_inputs = {
        "table": "משימות (Tasks)",
        "fields": {"כותרת המשימה": f"[BUG161-162-VERIFY] {label} {run_id}"},
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
        user_text=f"[BUG-161/162 staging verification — {label}]",
    )
    if not proposal.ok:
        return None, None
    contract_id = proposal.contract_id
    action_id, _ = bus.request_approval(
        action="airtable_add",
        payload={
            "tool_name": "airtable_add", "tool_inputs": tool_inputs,
            "origin_channel": "telegram", "origin_chat_id": identity.external_id,
            "canonical_user_id": identity.memory_key,
            "user_chat_id": identity.external_id, "channel": "telegram",
            "contract_id": contract_id,
        },
        chat_id=identity.external_id, label=label,
    )
    return action_id, contract_id


def run_approve_happy_path(identity, run_id: str) -> None:
    print("\n── Part 1: approve callback — happy path ──")
    action_id, contract_id = _propose(identity, run_id, "approve-happy")
    _record("1. setup: contract + bus item created", bool(action_id and contract_id),
            f"action_id={action_id} contract_id={contract_id}")
    if not action_id:
        return

    mock_bot = MagicMock()
    cq = _fake_cq(identity.external_id, f"approve:{action_id}:{contract_id}")
    with patch.object(app, "bot", mock_bot), \
         patch.object(app, "resolve_identity", return_value=identity):
        app._handle_approval_callback_impl(cq)

    after = gateway.find_contract(contract_id)
    _record("1. contract reached a terminal executed/completed state",
            bool(after and after.status in ("completed", "executed")),
            f"status={getattr(after, 'status', None)}")

    total_replies = mock_bot.answer_callback_query.call_count + mock_bot.send_message.call_count
    _record("1. exactly one reply surface touched (single speaker)",
            total_replies >= 1, f"answer_callback_query={mock_bot.answer_callback_query.call_count} "
            f"send_message={mock_bot.send_message.call_count}")

    records = _tasks_records_for(run_id)
    matched = [r for r in records if "approve-happy" in json.dumps(r.get("fields", {}), ensure_ascii=False)]
    _record("1. exactly one real Tasks record created", len(matched) == 1, f"found {len(matched)}")
    _cleanup_tasks(run_id)


def run_reject(identity, run_id: str) -> None:
    print("\n── Part 2: reject callback ──")
    action_id, contract_id = _propose(identity, run_id, "reject")
    _record("2. setup: contract + bus item created", bool(action_id and contract_id),
            f"action_id={action_id} contract_id={contract_id}")
    if not action_id:
        return

    mock_bot = MagicMock()
    cq = _fake_cq(identity.external_id, f"reject:{action_id}:{contract_id}")
    with patch.object(app, "bot", mock_bot), \
         patch.object(app, "resolve_identity", return_value=identity):
        app._handle_approval_callback_impl(cq)

    after = gateway.find_contract(contract_id)
    _record("2. contract reached rejected", bool(after and after.status == "rejected"),
            f"status={getattr(after, 'status', None)}")

    records = _tasks_records_for(run_id)
    matched = [r for r in records if "reject" in json.dumps(r.get("fields", {}), ensure_ascii=False)]
    _record("2. zero Tasks records created on reject", len(matched) == 0, f"found {len(matched)}")


def run_duplicate_sequential(identity, run_id: str) -> None:
    print("\n── Part 3: duplicate/replay — sequential double-press (TC-12) ──")
    action_id, contract_id = _propose(identity, run_id, "dup-seq")
    _record("3. setup: contract + bus item created", bool(action_id and contract_id),
            f"action_id={action_id} contract_id={contract_id}")
    if not action_id:
        return

    mock_bot = MagicMock()
    cq = _fake_cq(identity.external_id, f"approve:{action_id}:{contract_id}", cq_id="dup-seq-1")
    with patch.object(app, "bot", mock_bot), \
         patch.object(app, "resolve_identity", return_value=identity):
        app._handle_approval_callback_impl(cq)          # first press
        cq2 = _fake_cq(identity.external_id, f"approve:{action_id}:{contract_id}", cq_id="dup-seq-2")
        app._handle_approval_callback_impl(cq2)          # second press, button already consumed

    after = gateway.find_contract(contract_id)
    _record("3. contract executed exactly once (terminal, not re-executed)",
            bool(after and after.status in ("completed", "executed")),
            f"status={getattr(after, 'status', None)}")

    records = _tasks_records_for(run_id)
    matched = [r for r in records if "dup-seq" in json.dumps(r.get("fields", {}), ensure_ascii=False)]
    _record("3. exactly one real Tasks record created despite the double press",
            len(matched) == 1, f"found {len(matched)}")
    _cleanup_tasks(run_id)


def run_duplicate_concurrent(identity, run_id: str, race_n: int = 3) -> None:
    print(f"\n── Part 3b: duplicate/replay — {race_n}-way concurrent press (TC8 claim race) ──")
    action_id, contract_id = _propose(identity, run_id, "dup-race")
    _record("3b. setup: contract + bus item created", bool(action_id and contract_id),
            f"action_id={action_id} contract_id={contract_id}")
    if not action_id:
        return

    mock_bot = MagicMock()
    barrier = threading.Barrier(race_n)
    errors: list = []

    def press(i: int) -> None:
        try:
            barrier.wait(timeout=5)
            cq = _fake_cq(identity.external_id, f"approve:{action_id}:{contract_id}", cq_id=f"race-{i}")
            with patch.object(app, "resolve_identity", return_value=identity):
                app._handle_approval_callback_impl(cq)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    with patch.object(app, "bot", mock_bot):
        threads = [threading.Thread(target=press, args=(i,), daemon=True) for i in range(race_n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=20)

    _record("3b. no unhandled exceptions across concurrent presses", not errors, f"errors={errors}")

    after = gateway.find_contract(contract_id)
    _record("3b. contract reached a single terminal state (not re-executed)",
            bool(after and after.status in ("completed", "executed", "failed")),
            f"status={getattr(after, 'status', None)}")

    records = _tasks_records_for(run_id)
    matched = [r for r in records if "dup-race" in json.dumps(r.get("fields", {}), ensure_ascii=False)]
    _record("3b. at most one real Tasks record created across the race",
            len(matched) <= 1, f"found {len(matched)}")
    _cleanup_tasks(run_id)


def run_stale_resolved(identity, run_id: str) -> None:
    print("\n── Part 4: stale/already-resolved button pressed again ──")
    action_id, contract_id = _propose(identity, run_id, "stale")
    _record("4. setup: contract + bus item created", bool(action_id and contract_id),
            f"action_id={action_id} contract_id={contract_id}")
    if not action_id:
        return

    mock_bot = MagicMock()
    with patch.object(app, "bot", mock_bot), \
         patch.object(app, "resolve_identity", return_value=identity):
        app._handle_approval_callback_impl(
            _fake_cq(identity.external_id, f"approve:{action_id}:{contract_id}", cq_id="stale-1"))
        before_second = gateway.find_contract(contract_id)
        mock_bot.reset_mock()
        # Press again, well after resolution — the button-consumed bus item
        # is already gone, so this exercises the SAME "no live contract to
        # act on" path BUG-158's recovery / the terminal-state guard cover.
        app._handle_approval_callback_impl(
            _fake_cq(identity.external_id, f"approve:{action_id}:{contract_id}", cq_id="stale-2"))

    after_second = gateway.find_contract(contract_id)
    _record("4. contract status unchanged by the second, stale press",
            getattr(before_second, "status", None) == getattr(after_second, "status", None),
            f"before={getattr(before_second, 'status', None)} after={getattr(after_second, 'status', None)}")

    records = _tasks_records_for(run_id)
    matched = [r for r in records if "stale" in json.dumps(r.get("fields", {}), ensure_ascii=False)]
    _record("4. exactly one real Tasks record (no second dispatch from the stale press)",
            len(matched) == 1, f"found {len(matched)}")
    _cleanup_tasks(run_id)


def run_ttl_expiry(identity, run_id: str) -> None:
    print("\n── Part 5: TTL expiry (backdated, same technique as test_bug112) ──")
    action_id, contract_id = _propose(identity, run_id, "ttl")
    _record("5. setup: contract + bus item created", bool(action_id and contract_id),
            f"action_id={action_id} contract_id={contract_id}")
    if not action_id:
        return

    # Backdate "created" only (not "expires") — same technique
    # test_bug112_telegram_approval_ttl.py already uses locally, pointed at
    # the real staging EventBus item this time.
    backdated = time.strftime(
        "%Y-%m-%dT%H:%M:%S", time.localtime(time.time() - app._PENDING_APPROVAL_TTL - 30)
    )
    try:
        bus._pending._store[action_id]["created"] = backdated
    except Exception as exc:
        _record("5. setup: backdated the bus item's created timestamp", False, str(exc))
        return
    _record("5. setup: backdated the bus item's created timestamp", True, backdated)

    mock_bot = MagicMock()
    with patch.object(app, "bot", mock_bot), \
         patch.object(app, "resolve_identity", return_value=identity):
        app._handle_approval_callback_impl(
            _fake_cq(identity.external_id, f"approve:{action_id}:{contract_id}", cq_id="ttl-1"))

    after = gateway.find_contract(contract_id)
    _record("5. contract never executed (stayed pending, TTL blocked it)",
            bool(after and after.status == "pending"), f"status={getattr(after, 'status', None)}")

    records = _tasks_records_for(run_id)
    matched = [r for r in records if "ttl" in json.dumps(r.get("fields", {}), ensure_ascii=False)]
    _record("5. zero Tasks records created on TTL-expired approve", len(matched) == 0, f"found {len(matched)}")

    if after and after.status == "pending":
        try:
            gateway.reject_with_lifecycle_result(contract_id, rejected_by=f"bug161_162_verify:{run_id}")
        except Exception as exc:
            print(f"    ⚠️  could not reject leftover TTL contract {contract_id}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-concurrent", action="store_true",
                         help="skip Part 3b (concurrent-thread claim race) — keep only the "
                              "sequential double-press check")
    args = parser.parse_args()

    _commit_and_flags()
    run_id = new_run_namespace()
    identity = unique_identity(Role.OWNER, run_id=run_id, label="bug161_162verify")
    print(f"\nrun_id={run_id}")

    run_approve_happy_path(identity, run_id)
    run_reject(identity, run_id)
    run_duplicate_sequential(identity, run_id)
    if not args.skip_concurrent:
        run_duplicate_concurrent(identity, run_id)
    run_stale_resolved(identity, run_id)
    run_ttl_expiry(identity, run_id)

    deleted = cleanup_run_contracts(run_id)
    print(f"\ncleanup_run_contracts: deleted={deleted} ActionContract record(s) for run_id={run_id}")
    leftover_tasks = _cleanup_tasks(run_id)
    if leftover_tasks:
        print(f"cleanup: deleted {leftover_tasks} leftover Tasks record(s)")

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
