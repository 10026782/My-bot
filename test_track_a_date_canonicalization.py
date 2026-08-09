import os
from datetime import date, timedelta

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-track-a-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:TRACK_A_TEST")
os.environ.setdefault("AIRTABLE_API_KEY", "patTrackATest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appTrackATest")
os.environ.setdefault("SETUP_WEBHOOK", "0")

from airtable_schema import Tables, TaskFields
from core.action_gateway import ActionGateway, ExecutionLedger


def test_relative_tomorrow_is_split_before_action_contract_persistence():
    gateway = ActionGateway(ledger=ExecutionLedger())
    result = gateway.propose_action(
        tenant_id="boss_hq",
        canonical_user_id="boss_hq:track-a-date",
        tool_name="airtable_add",
        tool_inputs={
            "table": Tables.TASKS,
            "fields": {TaskFields.NAME: "להתקשר לספק מחר"},
        },
        origin_channel="telegram",
        origin_chat_id="track-a-date",
        requires_approval=True,
        trusted_source="deterministic_create_task",
    )

    contract = gateway.find_contract(result.contract_id)
    assert result.ok and contract is not None
    assert contract.tool_name == "airtable_add"
    assert contract.normalized_payload["table"] == Tables.TASKS
    assert contract.normalized_payload["fields"] == {
        TaskFields.NAME: "להתקשר לספק",
        TaskFields.DUE_DATE: (date.today() + timedelta(days=1)).isoformat(),
    }


def test_deterministic_create_task_runtime_path_reaches_same_canonical_contract():
    import app
    import feature_flags
    from core.action_gateway import action_gateway
    from core.router.router import parse_deterministic_create_task
    from identity import Identity, Role

    identity = Identity(user_id="track-a-runtime-date", role=Role.OWNER)
    parsed = parse_deterministic_create_task("צור משימה להתקשר לספק מחר")
    feature_flags.set_flag("FEATURE_ACTION_GATEWAY", True)
    try:
        app._queue_deterministic_create_task(
            parsed.title, identity.user_id, "telegram",
            "צור משימה להתקשר לספק מחר", identity, task_parse=parsed,
        )
        contracts = action_gateway.find_live_contracts(identity.memory_key)
        assert len(contracts) == 1
        fields = contracts[0].normalized_payload["fields"]
        assert contracts[0].tool_name == "airtable_add"
        assert contracts[0].normalized_payload["table"] == Tables.TASKS
        assert fields[TaskFields.NAME] == "להתקשר לספק"
        assert fields[TaskFields.DUE_DATE] == (date.today() + timedelta(days=1)).isoformat()
    finally:
        feature_flags.set_flag("FEATURE_ACTION_GATEWAY", False)
