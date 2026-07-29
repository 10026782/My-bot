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
