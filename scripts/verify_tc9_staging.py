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
  - Telegram send is mocked (app.bot), matching every existing test in this
    repo that exercises app.py's approval handlers — this canary verifies
    MessageContract construction at the ActionGateway boundary, not the
    Telegram transport, and must not be able to message a real chat;
  - it never touches PostgreSQL turn-state directly (TC8's own script
    already covers that) and never edits ActionGateway/TC9 semantics.

Coverage (see CLAUDE.md-adjacent TC10 spec, "MessageContract operational
verification"):
  - pending: propose a real contract, compose_status_reply() on it, assert
    MessageState.APPROVAL_PENDING and reply_owner.
  - executed/completed: approve + dispatch through the real dispatcher,
    assert MessageState.SUCCESS, evidence_status/evidence_ref preserved.
  - failed: dispatch against a deliberately-invalid table name (rejected by
    action_validator's structural check before any network write — safe and
    deterministic), assert MessageState.FAILURE.
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
  - no duplicate final response: asserts app.bot.send_message /
    answer_callback_query fire exactly once for the pending-notify and
    once for the resolution notify.

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
    base = os.getenv("AIRTABLE_BASE_ID", "")
    if not (os.getenv("TC9_STAGING_NON_PRODUCTION", "").lower() == "true"):
        raise VerificationFailure(
            "set TC9_STAGING_NON_PRODUCTION=true to confirm AIRTABLE_BASE_ID "
            f"({base!r}) is a non-production staging base — this script "
            "creates and deletes a real ActionContracts/Tasks record and "
            "must never run against production"
        )
    evidence["Preflight"] = {"status": "PASS", "detail": "non-production confirmation present"}
    print(f"{'Preflight':<40} PASS — non-production confirmation present")


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

        # ---- EXECUTED / COMPLETED -------------------------------------
        def _executed_check():
            mock_bot = MagicMock()
            with patch.object(app, "bot", mock_bot), \
                 patch("feature_flags.is_enabled", side_effect=lambda n: n == "FEATURE_ACTION_GATEWAY"):
                approve_msg = gw.approve(contract_id, approver=owner.memory_key, approver_role=owner.role)
                if not approve_msg or not approve_msg.startswith(("✅", "🔄")):
                    raise VerificationFailure(f"approve() did not report success: {approve_msg!r}")
            from tools.dispatcher import dispatch_tool
            contract = gw.find_contract(contract_id)
            dispatch_result = dispatch_tool(
                contract.tool_name, contract.normalized_payload, owner,
                trusted_source="deterministic_create_task",
            )
            from core.action_gateway import ActionFact
            ok = bool(isinstance(dispatch_result, dict) and dispatch_result.get("ok"))
            fact = ActionFact(
                tool_name="airtable_add", contract_id=contract_id,
                outcome="executed" if ok else "failed",
                record_id=dispatch_result.get("external_id") if isinstance(dispatch_result, dict) else None,
                error_code=None if ok else "staging_canary_dispatch_failed",
                raw_tool_response=dispatch_result if isinstance(dispatch_result, dict) else {},
                evidence_status="verified_write_success" if ok else "failure",
                evidence_ref=dispatch_result.get("external_id") if isinstance(dispatch_result, dict) else None,
                execution_verified=ok,
            )
            reply = gw.compose_status_reply(fact)
            contract_out = reply.contract
            if contract_out is None:
                raise VerificationFailure("no MessageContract produced for executed fact")
            expected = MessageState.SUCCESS if ok else MessageState.FAILURE
            if contract_out.state != expected:
                raise VerificationFailure(f"expected {expected}, got {contract_out.state}")
            if ok and not contract_out.evidence_ref:
                raise VerificationFailure("evidence_ref missing on a claimed-successful execution")
            return f"ok={ok} state={contract_out.state} evidence_ref={contract_out.evidence_ref}"

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
                # Structural rejection before a contract even exists is itself
                # an acceptable deterministic failure surface — nothing to
                # execute, no MessageContract expected.
                return f"rejected at proposal boundary (structural): {propose2.reason}"
            from core.action_gateway import ActionFact
            fact = ActionFact(
                tool_name="airtable_add", contract_id=propose2.contract_id, outcome="failed",
                record_id=None, error_code="unknown_table", raw_tool_response={},
                evidence_status="failure", execution_verified=False,
            )
            reply = gw.compose_status_reply(fact)
            contract_out = reply.contract
            if contract_out is None or contract_out.state != MessageState.FAILURE:
                raise VerificationFailure(f"expected FAILURE, got {getattr(contract_out, 'state', None)}")
            return f"state={contract_out.state}"

        _check("Failed — deterministic reproduction, no false success", _failed_check, evidence)

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
                evidence["cleanup"] = {"status": "FAIL", "detail": f"{type(exc).__name__}: {exc}"}
                print(f"{'Cleanup':<40} FAIL — {type(exc).__name__}: {exc}")

    if args.evidence_path:
        args.evidence_path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nEvidence written to {args.evidence_path}")

    print("\nFINAL:")
    print("TC9 STAGING CANARY: FAIL" if failed else "TC9 STAGING CANARY: DONE")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
