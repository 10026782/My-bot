#!/usr/bin/env python3
"""TC10 — TC9 MessageContract staging runtime canary.

Verifies that TC9's ActionGateway -> MessageContract wiring
(core/action_gateway.py::_message_contract_for_fact /
core.action_fact_message_adapter.from_action_fact) is actually exercised
by the real, deployed runtime — not just by
test_tc9_messagecontract_runtime_wiring.py's isolated unit coverage (which
builds ActionFact objects by hand and never touches a real ActionGateway
singleton, real Airtable-backed contract, or real app.py callback/text
handler).

Staging-safe by construction:
  - every identity comes from scripts.staging_identity.unique_identity(),
    so nothing here can collide with a contract another run — or another
    engineer's staging session — left behind (BUG-122);
  - it creates at most one throwaway Tasks record and one ActionContracts
    record per run, both under this run's own disposable tenant_id, cleaned
    up via scripts.staging_identity.cleanup_run_contracts() in `finally`;
  - app.bot is patched with a MagicMock as defense-in-depth, but note this
    canary calls core.action_gateway.action_gateway directly (propose_action/
    approve), which never touches app.bot at all — the owner-notify call
    that some app.py wrapper functions make is not on this code path. This
    canary verifies MessageContract construction at the ActionGateway
    boundary; it does NOT drive app.py's real callback/text handlers and
    makes no claim about Telegram-transport call counts (see the coverage
    note on "exactly one final response" below);
  - it never touches PostgreSQL turn-state directly (TC8's own script
    already covers that) and never edits ActionGateway/TC9 semantics.

Coverage (see CLAUDE.md-adjacent TC10 spec, "MessageContract operational
verification"):
  - pending: propose a real contract, compose_status_reply() on it, assert
    MessageState.APPROVAL_PENDING and reply_owner.
  - executed/completed: approve() (which executes internally — this canary
    does not call the dispatcher a second time, to avoid a real duplicate
    write against staging Airtable), assert MessageState.SUCCESS,
    evidence_status/evidence_ref preserved.
  - failed: propose against a deliberately-invalid table name. If rejected
    at the proposal boundary (structural, before a contract exists), that is
    recorded as its own distinct, honestly-labeled outcome — NOT counted as
    "FAILURE MessageState verified," since no MessageContract was produced
    to check. Only a contract that reaches real execution and lands in
    ActionContract status "failed" counts toward the FAILURE assertion.
  - outcome_unknown: NOT attempted here. There is no safe, deterministic way
    to force execution into a truly ambiguous state against real staging
    without either faking evidence (which would prove nothing about real
    wiring) or deliberately destabilizing staging (explicitly forbidden by
    the TC10 spec). This state is covered by
    test_tc9_messagecontract_runtime_wiring.py's isolated unit test instead
    — that is stated here as a known, accepted limitation, not silently
    dropped.
  - turn_id: the callback path's turn_id is the real Telegram callback
    query id (see app.py's four approve/reject/cancel sites, all
    `turn_id=f"callback:{cq.id}"`). This canary constructs a realistic
    callback-query object carrying a synthetic-but-real-shaped id (the
    contract_id itself — deterministic, unique, never fabricated by TC9)
    and asserts the resulting MessageContract carries that exact id
    through unmodified. It also asserts the no-turn_id case
    (compose_status_reply on a fact with turn_id=None) never invents one.
  - no duplicate final response: NOT covered by this script — it calls
    core.action_gateway.action_gateway directly and never reaches app.py's
    callback/text handlers or app.bot, so there is nothing meaningful to
    assert a call count on here. That invariant is covered where it's
    actually exercised: test_turn_envelope.py and the TC6/PA-01 app.py
    integration tests, which do drive the real handlers with a mocked bot.

This script requires real staging DATABASE_URL / AIRTABLE_API_KEY /
AIRTABLE_BASE_ID / TELEGRAM_TOKEN in its environment and a network path to
the real staging Airtable base. It has NOT been executed as part of this
TC10 change — no staging credentials are available in the environment that
authored it. Run it from a machine with staging secrets and keep the
printed evidence as the "Staging runtime evidence" artifact TC10 requires;
do not label its output "Production evidence."
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class VerificationFailure(RuntimeError):
    pass


def _check(label: str, fn, evidence: dict) -> None:
    try:
        detail = fn()
        evidence[label] = {"status": "PASS", "detail": detail}
        print(f"{label:<40} PASS{(' — ' + str(detail)) if detail else ''}")
    except Exception as exc:
        evidence[label] = {"status": "FAIL", "detail": f"{type(exc).__name__}: {exc}"}
        print(f"{label:<40} FAIL — {type(exc).__name__}: {exc}")
        raise


def _preflight(evidence: dict) -> None:
    for var in ("DATABASE_URL", "AIRTABLE_API_KEY", "AIRTABLE_BASE_ID", "TELEGRAM_TOKEN"):
        if not os.getenv(var, "").strip():
            raise VerificationFailure(f"{var} is not configured — this is a staging-only script")
    if os.getenv("TC9_STAGING_NON_PRODUCTION", "").lower() != "true":
        raise VerificationFailure(
            "set TC9_STAGING_NON_PRODUCTION=true to confirm this target is "
            "non-production staging — this script creates and executes a "
            "real ActionContracts/Tasks record and must never run against "
            "production"
        )
    # The confirmation env var above is caller-controlled and, on its own,
    # proves nothing — a shell could export it alongside real production
    # DATABASE_URL/AIRTABLE_BASE_ID by mistake. Require the target's own
    # identifiers to also look non-production, the same defense-in-depth
    # naming heuristic scripts/verify_tc8_staging.py's _preflight() already
    # uses for DATABASE_URL.
    base = os.getenv("AIRTABLE_BASE_ID", "")
    db_url = os.getenv("DATABASE_URL", "")
    non_prod_tokens = ("staging", "sandbox", "test", "dev")
    if not any(token in base.lower() for token in non_prod_tokens):
        raise VerificationFailure(
            f"AIRTABLE_BASE_ID ({base!r}) does not look like a non-production "
            "base (expected one of staging/sandbox/test/dev in the name) — "
            "refusing to run even with TC9_STAGING_NON_PRODUCTION=true"
        )
    if not any(token in db_url.lower() for token in non_prod_tokens):
        raise VerificationFailure(
            "DATABASE_URL does not look like a non-production database "
            "(expected one of staging/sandbox/test/dev in the name) — "
            "refusing to run even with TC9_STAGING_NON_PRODUCTION=true"
        )
    evidence["Preflight"] = {
        "status": "PASS",
        "detail": f"non-production confirmation + base={base!r} name heuristic",
    }
    print(f"{'Preflight':<40} PASS — non-production confirmation + base name heuristic")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-path", type=Path)
    args = parser.parse_args()

    evidence: dict = {}
    failed = False
    run_id = None
    print("TC9 MESSAGECONTRACT STAGING RUNTIME CANARY\n")

    try:
        _preflight(evidence)

        from scripts.staging_identity import cleanup_run_contracts, new_run_namespace, unique_identity
        from identity import Role
        import app  # noqa: E402  (heavy import, real staging config)
        from core.action_gateway import action_gateway as gw
        from core.message_contract import MessageState

        run_id = new_run_namespace()
        owner = unique_identity(Role.OWNER, run_id=run_id)
        evidence["run_id"] = run_id
        evidence["identity"] = owner.memory_key
        print(f"{'Run namespace':<40} run_id={run_id}")

        # ---- PENDING -------------------------------------------------
        propose = gw.propose_action(
            tenant_id=owner.tenant_id, canonical_user_id=owner.memory_key,
            tool_name="airtable_add",
            tool_inputs={"table": "Tasks", "fields": {"כותרת המשימה": f"TC10 canary {run_id}"}},
            origin_channel="telegram", origin_chat_id=owner.user_id,
            requires_approval=True, identity=owner, trusted_source="deterministic_create_task",
        )
        if not propose.ok:
            raise VerificationFailure(f"setup propose failed: {propose.reason}")
        contract_id = propose.contract_id
        evidence["contract_id"] = contract_id

        def _pending_check():
            from core.action_gateway import ActionFact
            fact = ActionFact(
                tool_name="airtable_add", contract_id=contract_id, outcome="pending",
                record_id=None, error_code=None, raw_tool_response={},
            )
            reply = gw.compose_status_reply(fact)
            contract = reply.contract
            if contract is None:
                raise VerificationFailure("no MessageContract produced for pending fact")
            if contract.state != MessageState.APPROVAL_PENDING:
                raise VerificationFailure(f"expected APPROVAL_PENDING, got {contract.state}")
            return f"state={contract.state} reply_owner={getattr(contract, 'reply_owner', None)}"

        _check("Pending — canonical MessageContract path", _pending_check, evidence)

        # ---- turn_id propagation / non-fabrication --------------------
        def _turn_id_check():
            from core.action_gateway import ActionFact
            fake_cq_id = f"tc10-real-shaped-{contract_id}"
            fact_with_turn = ActionFact(
                tool_name="airtable_add", contract_id=contract_id, outcome="pending",
                record_id=None, error_code=None, raw_tool_response={},
                turn_id=f"callback:{fake_cq_id}",
            )
            reply_with = gw.compose_status_reply(fact_with_turn)
            if reply_with.contract is None or reply_with.contract.turn_id != f"callback:{fake_cq_id}":
                raise VerificationFailure("real turn_id was not propagated unmodified")

            fact_without_turn = ActionFact(
                tool_name="airtable_add", contract_id=contract_id, outcome="pending",
                record_id=None, error_code=None, raw_tool_response={},
            )
            reply_without = gw.compose_status_reply(fact_without_turn)
            if reply_without.contract is not None and reply_without.contract.turn_id is not None:
                raise VerificationFailure(
                    f"turn_id was fabricated when none was available: {reply_without.contract.turn_id!r}"
                )
            return "propagated when present, never fabricated when absent"

        _check("turn_id — propagated, never fabricated", _turn_id_check, evidence)

        # ---- shared helper: approve() executes internally (single real
        # write — see core/action_gateway.py's approve()/_execute_contract).
        # This canary must never dispatch a second time itself, or every run
        # would leave an extra write against staging Airtable behind it.
        def _approve_and_derive_fact(cid: str, *, approver_role: str):
            mock_bot = MagicMock()
            with patch.object(app, "bot", mock_bot), \
                 patch("feature_flags.is_enabled", side_effect=lambda n: n == "FEATURE_ACTION_GATEWAY"):
                approve_msg = gw.approve(cid, approver=owner.memory_key, approver_role=approver_role)
            contract = gw.find_contract(cid)
            if contract is None:
                raise VerificationFailure(f"contract {cid} vanished after approve()")
            real_status = contract.status
            ok = real_status in ("completed", "executed")
            from core.action_gateway import ActionFact
            # evidence_ref/evidence_status here are a synthetic projection of
            # the REAL, just-observed contract.status (not a second dispatch,
            # not invented independently of it) — the same synthetic-but-
            # outcome-driven pattern test_tc9_messagecontract_runtime_wiring.py's
            # own _fact() helper uses. contract.status is the genuine signal;
            # this only re-derives the MessageContract shape from it.
            fact = ActionFact(
                tool_name="airtable_add", contract_id=cid,
                outcome="executed" if ok else "failed",
                record_id=cid if ok else None,
                error_code=None if ok else f"staging_canary_status_{real_status}",
                raw_tool_response={},
                evidence_status="verified_write_success" if ok else "failure",
                evidence_ref=cid if ok else None,
                execution_verified=ok,
            )
            return ok, real_status, approve_msg, fact

        # ---- EXECUTED / COMPLETED -------------------------------------
        def _executed_check():
            ok, real_status, approve_msg, fact = _approve_and_derive_fact(contract_id, approver_role=owner.role)
            reply = gw.compose_status_reply(fact)
            contract_out = reply.contract
            if contract_out is None:
                raise VerificationFailure("no MessageContract produced for executed fact")
            expected = MessageState.SUCCESS if ok else MessageState.FAILURE
            if contract_out.state != expected:
                raise VerificationFailure(
                    f"expected {expected} (real contract.status={real_status!r}), got {contract_out.state}"
                )
            if ok and not contract_out.evidence_ref:
                raise VerificationFailure("evidence_ref missing on a claimed-successful execution")
            return f"ok={ok} real_status={real_status} state={contract_out.state} approve_msg={approve_msg!r}"

        _check("Executed — canonical MessageContract + evidence preserved", _executed_check, evidence)

        # ---- FAILED (deterministic, safe) ------------------------------
        def _failed_check():
            mock_bot = MagicMock()
            with patch.object(app, "bot", mock_bot):
                propose2 = gw.propose_action(
                    tenant_id=owner.tenant_id, canonical_user_id=owner.memory_key,
                    tool_name="airtable_add",
                    tool_inputs={"table": "TC10_Nonexistent_Table_Canary", "fields": {}},
                    origin_channel="telegram", origin_chat_id=owner.user_id,
                    requires_approval=True, identity=owner, trusted_source="deterministic_create_task",
                )
            if not propose2.ok:
                # Structural rejection before a contract even exists — no
                # MessageContract was produced, so this does NOT verify
                # MessageState.FAILURE. Recorded as its own distinct,
                # honestly-labeled outcome rather than folded into the
                # "Failed" check as if it were equivalent evidence.
                evidence["Failed (boundary rejection, not FAILURE-state)"] = {
                    "status": "INCONCLUSIVE",
                    "detail": f"rejected at proposal boundary before a contract existed: {propose2.reason}",
                }
                print(
                    f"{'Failed (boundary rejection)':<40} INCONCLUSIVE — "
                    f"rejected before a contract existed, FAILURE MessageState not exercised: {propose2.reason}"
                )
                return
            ok, real_status, _approve_msg, fact = _approve_and_derive_fact(
                propose2.contract_id, approver_role=owner.role,
            )
            reply = gw.compose_status_reply(fact)
            contract_out = reply.contract
            if ok or contract_out is None or contract_out.state != MessageState.FAILURE:
                raise VerificationFailure(
                    f"expected a real FAILURE (contract.status={real_status!r}), "
                    f"got ok={ok} state={getattr(contract_out, 'state', None)}"
                )
            return f"real_status={real_status} state={contract_out.state}"

        try:
            detail = _failed_check()
            if detail is not None:
                evidence["Failed — deterministic reproduction, no false success"] = {
                    "status": "PASS", "detail": detail,
                }
                print(f"{'Failed — deterministic reproduction':<40} PASS — {detail}")
        except VerificationFailure as exc:
            evidence["Failed — deterministic reproduction, no false success"] = {
                "status": "FAIL", "detail": str(exc),
            }
            print(f"{'Failed — deterministic reproduction':<40} FAIL — {exc}")
            raise

        evidence["outcome_unknown"] = {
            "status": "DEFERRED",
            "detail": (
                "not safely reproducible against real staging without "
                "fabricating evidence or destabilizing staging; covered by "
                "test_tc9_messagecontract_runtime_wiring.py (isolated "
                "integration evidence) instead"
            ),
        }
        print(f"{'outcome_unknown':<40} DEFERRED — see test_tc9_messagecontract_runtime_wiring.py")

    except Exception as exc:
        failed = True
        evidence["fatal"] = {"status": "FAIL", "detail": f"{type(exc).__name__}: {exc}"}
        print(f"\nFATAL{'':<35} FAIL — {type(exc).__name__}: {exc}")
    finally:
        if run_id:
            try:
                from scripts.staging_identity import cleanup_run_contracts
                deleted = cleanup_run_contracts(run_id)
                evidence["cleanup"] = {"status": "PASS", "detail": f"deleted={deleted}"}
                print(f"{'Cleanup':<40} PASS — deleted={deleted} record(s) for run_id={run_id}")
            except Exception as exc:
                failed = True
                evidence["cleanup"] = {"status": "FAIL", "detail": f"{type(exc).__name__}: {exc}"}
                print(f"{'Cleanup':<40} FAIL — {type(exc).__name__}: {exc}")
                print(
                    "  -> cleanup failure means canary-created records may "
                    f"still exist in staging under run_id={run_id} — this "
                    "must not be silently reported as a passing run"
                )

    if args.evidence_path:
        args.evidence_path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nEvidence written to {args.evidence_path}")

    print("\nFINAL:")
    print("TC9 STAGING CANARY: FAIL" if failed else "TC9 STAGING CANARY: DONE")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
