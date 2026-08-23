"""Focused PR4 coverage for Telegram Decision business writes."""

import ast
from types import SimpleNamespace
from unittest.mock import Mock, patch

import cmd_decision
from airtable_schema import DecisionFields, Tables


def test_decision_writes_use_existing_storage_port():
    identity = SimpleNamespace(tenant_id="tenant", user_id="user")
    storage = Mock()
    storage.add.side_effect = ["recDecision", "recStakeholder", "recEvent"]

    with patch.object(cmd_decision, "_decision_storage", return_value=storage), \
            patch("tools.contact_resolver.resolve") as resolve:
        resolve.return_value.status = "not_found"
        decision = cmd_decision._create_decision(
            identity, "Decision", "general", 10, ["Stakeholder"]
        )
        event_id = cmd_decision._create_decision_event(
            identity, "recDecision", {"raw_content": "update"}
        )

    assert decision["id"] == "recDecision"
    assert event_id == "recEvent"
    assert [call.args[0] for call in storage.add.call_args_list] == [
        Tables.DECISIONS, Tables.DECISION_STAKEHOLDERS, Tables.DECISION_EVENTS,
    ]
    assert decision["fields"][DecisionFields.STATUS]


def test_cmd_decision_has_no_direct_airtable_business_writer():
    tree = ast.parse(open("cmd_decision.py", encoding="utf-8").read())
    direct_calls = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"airtable_create", "airtable_patch", "airtable_update"}
    }
    assert not direct_calls

