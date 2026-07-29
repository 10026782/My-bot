#!/usr/bin/env python3
"""Focused PR2 fast-path checks (no network, Agent, Session, or Router)."""

from __future__ import annotations

import os
import sys
import time
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))
# Force (not setdefault) — app.py has import-time TeleBot/webhook side
# effects; an ambient real TELEGRAM_TOKEN/SETUP_WEBHOOK in the shell or CI
# environment must never leak into this "no network" script.
os.environ["ANTHROPIC_API_KEY"] = "sk-pr2-test"
os.environ["TELEGRAM_TOKEN"] = "123456789:PR2_TEST_TOKEN"
os.environ["AIRTABLE_API_KEY"] = "patPr2Test"
os.environ["AIRTABLE_BASE_ID"] = "appPr2Test"
os.environ["SETUP_WEBHOOK"] = "0"

import app  # noqa: E402
import feature_flags  # noqa: E402
from core.action_gateway import ActionContract, ActionGateway, ExecutionLedger  # noqa: E402
import core.action_gateway as action_gateway_module  # noqa: E402
from identity import Identity, Role  # noqa: E402


def contract(contract_id: str, user: str) -> ActionContract:
    return ActionContract(
        contract_id=contract_id, tenant_id="boss_hq", canonical_user_id=user,
        tool_name="airtable_add", normalized_payload={"table": "Tasks", "fields": {}},
        business_action_fingerprint=f"fp-{contract_id}", origin_channel="telegram",
        origin_chat_id="pr2", requires_approval=True, status="pending", created_at=time.time(),
    )


def resolve(text: str, live: list, identity: Identity):
    return app._resolve_pr2_deterministic_approval(
        user_text=text, identity=identity, live_contracts=live, out_meta={},
    )


def terminal_contract(contract_id: str, user: str, *, status: str, age_seconds: float) -> ActionContract:
    c = contract(contract_id, user)
    c.status = status
    c.created_at = time.time() - age_seconds
    return c


def main() -> None:
    feature_flags.set_flag("FEATURE_ACTION_GATEWAY", True)
    feature_flags.set_flag("FEATURE_SINGLE_SPEAKER_APPROVAL_UX", True)
    feature_flags.set_flag("FEATURE_DETERMINISTIC_APPROVAL_COST_CUTS", True)
    identity = Identity(user_id="pr2-owner", role=Role.OWNER)
    one = contract("pr2-one", identity.memory_key)
    two = contract("pr2-two", identity.memory_key)
    gateway = ActionGateway(ledger=ExecutionLedger())
    gateway._ledger.save(one)
    gateway._ledger.save(two)

    try:
        with patch.object(action_gateway_module, "action_gateway", gateway):
            assert resolve("יצרת קשר עם הליד?", [one], identity) is None
            assert resolve("יש פעולה שממתינה?", [one], identity).startswith("במערכת ActionContracts")
            assert resolve("יצרת?", [one], identity) is not None
            reply = resolve("לא", [one, two], identity)
            assert "2" in reply and one.status == two.status == "pending"
            # Flag-off must leave the new resolver entirely inert, preserving
            # the legacy cancellation route (including its mutate-all behavior).
            feature_flags.set_flag("FEATURE_DETERMINISTIC_APPROVAL_COST_CUTS", False)
            assert resolve("לא", [one, two], identity) is None
            # Prove the legacy route itself still mutates both contracts —
            # not just that the new resolver stays out of the way.
            legacy_reply = gateway.route_cancellation_word(
                identity.memory_key, live_contracts=[one, two],
            )
            assert legacy_reply is not None
            assert one.status == "rejected" and two.status == "rejected"
            feature_flags.set_flag("FEATURE_DETERMINISTIC_APPROVAL_COST_CUTS", True)

            # "must not intercept" grammar corpus (reading-pack §7): anchored
            # exact-match must reject a word appearing inside unrelated
            # business text, not just reject exact non-matches.
            assert resolve("אני מאשר את התקציב לרבעון הבא", [], identity) is None
            assert resolve("יש פעולה שכדאי לבחון מול הלקוח", [], identity) is None

        # 24h terminal-replay boundary (reading-pack §8/§14 finding 2):
        # find_recent_terminal_by_user() must exclude a contract older than
        # _LIVE_CONTRACT_STALE_SECONDS and include one just inside it.
        replay_gateway = ActionGateway(ledger=ExecutionLedger())
        stale = terminal_contract(
            "pr2-stale", identity.memory_key, status="completed",
            age_seconds=app._LIVE_CONTRACT_STALE_SECONDS + 3600,  # 25h old
        )
        fresh = terminal_contract(
            "pr2-fresh", identity.memory_key, status="completed",
            age_seconds=3600,  # 1h old, well inside the 24h window
        )
        with patch.object(action_gateway_module, "action_gateway", replay_gateway):
            replay_gateway._ledger.save(stale)
            assert resolve("יצרת?", [], identity) == "לא מצאתי פעולה אחרונה ב־24 השעות האחרונות."
            replay_gateway._ledger.save(fresh)
            fresh_reply = resolve("יצרת?", [], identity)
            assert fresh_reply != "לא מצאתי פעולה אחרונה ב־24 השעות האחרונות."

        # Confirmation replay guard, corrected (PR2 staging acceptance
        # incident, 29/07/2026): a bare confirm/cancel word with no live
        # contract must NEVER replay find_recent_terminal_by_user() by
        # recency, at ANY age — the first version of this guard used a
        # 10-minute window, which would still have reproduced the incident
        # (the unrelated completed lead contract was only ~20 seconds old).
        # "יצרת?" (explicit status query) keeps the full 24h behavior,
        # proven above and unaffected by this guard.
        _NO_PENDING = "אין פעולה שממתינה לאישור"
        _NO_PENDING_CANCEL = "לא מצאתי פעולה ממתינה לביטול."

        for _word, _expected in (("כן", _NO_PENDING), ("לא", _NO_PENDING_CANCEL)):
            for _age_label, _age_seconds in (
                ("5s", 5), ("20s", 20), ("9min", 9 * 60),
            ):
                aged_gateway = ActionGateway(ledger=ExecutionLedger())
                unrelated = terminal_contract(
                    f"pr2-unrelated-{_word}-{_age_label}", identity.memory_key,
                    status="completed", age_seconds=_age_seconds,
                )
                with patch.object(action_gateway_module, "action_gateway", aged_gateway):
                    aged_gateway._ledger.save(unrelated)
                    reply = resolve(_word, [], identity)
                assert reply == _expected, (_word, _age_label, reply)
                # Not replayed = not mutated.
                assert unrelated.status == "completed", (_word, _age_label)

        # Same unrelated contract still answers the explicit status question
        # regardless of age (within 24h) — the guard is scoped to bare
        # confirm/cancel only, proven separately from the sweep above.
        created_query_gateway = ActionGateway(ledger=ExecutionLedger())
        created_query_contract = terminal_contract(
            "pr2-created-query-unaffected", identity.memory_key,
            status="completed", age_seconds=20,
        )
        with patch.object(action_gateway_module, "action_gateway", created_query_gateway):
            created_query_gateway._ledger.save(created_query_contract)
            created_query_reply = resolve("יצרת?", [], identity)
        assert created_query_reply != "לא מצאתי פעולה אחרונה ב־24 השעות האחרונות.", created_query_reply

        # ── Full incident reproduction (29/07/2026) ─────────────────────
        # 1. unrelated lead contract completed; 2. task canonicalization
        # fails before contract creation; 3. bare "כן" arrives 20s later;
        # 4. no live contract exists; 5. response is no-pending; 6. the
        # completed lead contract is not replayed; 7. no mutation;
        # 8. agent_call_count == 0; 9. final_response_count == 1.
        def lead_contract(contract_id: str, user: str, *, age_seconds: float) -> ActionContract:
            c = ActionContract(
                contract_id=contract_id, tenant_id="boss_hq", canonical_user_id=user,
                tool_name="airtable_add", normalized_payload={"table": "Leads", "fields": {}},
                business_action_fingerprint=f"fp-{contract_id}", origin_channel="telegram",
                origin_chat_id="pr2", requires_approval=True, status="completed",
                created_at=time.time() - age_seconds,
            )
            return c

        incident_identity = Identity(user_id="pr2-incident-owner", role=Role.OWNER)
        incident_gateway = ActionGateway(ledger=ExecutionLedger())

        # 1. unrelated lead contract completed ~20s before the "כן".
        unrelated_lead = lead_contract(
            "pr2-incident-lead", incident_identity.memory_key, age_seconds=20,
        )
        incident_gateway._ledger.save(unrelated_lead)

        # 2. task canonicalization fails before any contract is created —
        # reproducing the real CanonicalizationError, not just asserting the
        # end state.
        from core.action_gateway import (
            CanonicalizationError as _IncidentCanonError,
            resolve_canonical_call as _incident_resolve_canonical_call,
        )
        try:
            _incident_resolve_canonical_call(
                "sheets_append", {"table": "Tasks", "row_data": ["a", "b", "c"]}, "",
            )
            _incident_canon_failed = False
        except _IncidentCanonError:
            _incident_canon_failed = True
        assert _incident_canon_failed
        # 4. no live contract exists (the failed attempt created none; the
        # lead contract is terminal, not live).
        assert incident_gateway.find_live_contracts(incident_identity.memory_key) == []

        # 3. bare "כן" arrives 20 seconds later, with metrics captured.
        import core.approval_turn_metrics as approval_turn_metrics_module
        _captured = {}
        _real_metrics_end = approval_turn_metrics_module.end

        def _capturing_end(token, ingress):
            m = approval_turn_metrics_module.current()
            if m is not None:
                _captured["agent_call_count"] = m.agent_call_count
                _captured["final_response_count"] = m.final_response_count
                _captured["deterministic_path_used"] = m.deterministic_path_used
            _real_metrics_end(token, ingress)

        with patch.object(action_gateway_module, "action_gateway", incident_gateway), \
             patch.object(approval_turn_metrics_module, "end", _capturing_end):
            incident_reply = resolve("כן", [], incident_identity)

        # 5. response is the canonical no-pending response.
        assert incident_reply == _NO_PENDING, incident_reply
        # 6. the completed lead contract is not referenced/replayed.
        assert "הושלמה" not in incident_reply and "נוצרה" not in incident_reply
        # 7. no mutation — the lead contract's status is untouched.
        assert incident_gateway.find_contract("pr2-incident-lead").status == "completed"
        # 8. zero Agent calls. 9. exactly one final response.
        assert _captured["agent_call_count"] == 0, _captured
        assert _captured["final_response_count"] == 1, _captured
        assert _captured["deterministic_path_used"] is True, _captured

        # Exact boundary, with a controlled clock (not wall-clock timing, so
        # "exactly at the limit" can't flake): just-over is excluded,
        # exactly-at and just-under are both included.
        fixed_now = 1_800_000_000.0
        limit = app._LIVE_CONTRACT_STALE_SECONDS
        boundary_gateway = ActionGateway(ledger=ExecutionLedger())
        for suffix, age, expect_found in (
            ("over", limit + 1, False),
            ("at", limit, True),
            ("under", limit - 1, True),
        ):
            c = contract(f"pr2-boundary-{suffix}", identity.memory_key)
            c.status = "completed"
            c.created_at = fixed_now - age
            boundary_gateway._ledger.save(c)
            with patch("core.action_gateway.time.time", return_value=fixed_now):
                found = boundary_gateway.find_recent_terminal_by_user(
                    identity.memory_key, max_age_seconds=limit,
                )
            if expect_found:
                assert found is not None and found.contract_id == f"pr2-boundary-{suffix}", suffix
            else:
                assert found is None, suffix
    finally:
        feature_flags.set_flag("FEATURE_ACTION_GATEWAY", False)
        feature_flags.set_flag("FEATURE_SINGLE_SPEAKER_APPROVAL_UX", False)
        feature_flags.set_flag("FEATURE_DETERMINISTIC_APPROVAL_COST_CUTS", False)

    print("PR2 deterministic approval cost-cuts: OK")


if __name__ == "__main__":
    main()
