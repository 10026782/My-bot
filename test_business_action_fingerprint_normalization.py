"""Regression coverage for canonical task identity and rejected dedupe."""

from __future__ import annotations

import pytest

from core.action_gateway import ActionGateway, ExecutionLedger, _canonical_business_text


def test_business_text_normalization_repeats_after_wrapper_and_punctuation_removal():
    assert _canonical_business_text('(\"task\").') == "task"


def _gateway() -> ActionGateway:
    return ActionGateway(ledger=ExecutionLedger())


def _propose(gateway: ActionGateway, title: str):
    return gateway.propose_action(
        tenant_id="boss_hq",
        canonical_user_id="boss_hq:fingerprint-test",
        tool_name="airtable_add",
        tool_inputs={"table": "Tasks", "fields": {"name": title}},
        origin_channel="telegram",
        origin_chat_id="fingerprint-test",
        requires_approval=True,
        user_text=f"צור משימה {title}",
    )


@pytest.mark.parametrize(
    "equivalent_title",
    [
        "פרסם מודעה עד לתאריך 6/8/26 בשעה 10:00",
        "פרסם\u00a0מודעה עד לתאריך 6/8/26 בשעה 10:00",
        "פרסם  מודעה עד לתאריך 6/8/26 בשעה 10:00",
        '"פרסם מודעה עד לתאריך 6/8/26 בשעה 10:00."',
        "> [פרסם מודעה עד לתאריך 6/8/26 בשעה 10:00]",
    ],
)
def test_equivalent_task_formatting_reuses_rejected_contract(equivalent_title):
    gateway = _gateway()
    first = _propose(gateway, "פרסם מודעה עד לתאריך 6/8/26 בשעה 10:00")
    assert first.ok is True
    assert gateway.reject(first.contract_id, rejected_by="boss_hq:fingerprint-test")

    replay = _propose(gateway, equivalent_title)

    assert replay.ok is False
    assert replay.contract_id == first.contract_id
    assert "כבר בוטלה" in (replay.user_message or "")
    assert len(gateway._ledger.contracts_for_user("boss_hq:fingerprint-test")) == 1


def test_materially_changed_task_time_gets_new_fingerprint():
    gateway = _gateway()
    first = _propose(gateway, "פרסם מודעה עד לתאריך 6/8/26 בשעה 10:00")
    assert first.ok is True
    assert gateway.reject(first.contract_id, rejected_by="boss_hq:fingerprint-test")

    changed = _propose(gateway, "פרסם מודעה עד לתאריך 6/8/26 בשעה 11:00")

    assert changed.ok is True
    assert changed.contract_id != first.contract_id
    assert len(gateway._ledger.contracts_for_user("boss_hq:fingerprint-test")) == 2
