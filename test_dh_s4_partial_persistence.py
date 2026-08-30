"""DH-S4: Decision Hub side-effect persistence must be explicit and truthful."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

import cmd_decision
from airtable_schema import Tables


def _identity():
    return SimpleNamespace(tenant_id="tenant-a", user_id="user-a", is_owner=True, role="owner")


def test_stakeholder_write_success_is_structured():
    storage = Mock()
    storage.add.return_value = "stakeholder-1"
    with patch.object(cmd_decision, "_decision_storage", return_value=storage), patch(
        "tools.contact_resolver.resolve", return_value=SimpleNamespace(status="not_found")
    ):
        result = cmd_decision._create_stakeholder(_identity(), "decision-1", "Dana")

    assert result.status == "SUCCESS"
    assert result.record_id == "stakeholder-1"
    assert storage.add.call_args.args[0] == Tables.DECISION_STAKEHOLDERS


def test_stakeholder_write_failure_is_not_discarded():
    storage = Mock()
    storage.add.return_value = None
    with patch.object(cmd_decision, "_decision_storage", return_value=storage), patch(
        "tools.contact_resolver.resolve", return_value=SimpleNamespace(status="not_found")
    ):
        result = cmd_decision._create_stakeholder(_identity(), "decision-1", "Dana")

    assert result.status == "FAILED"
    assert result.failed_steps == ("stakeholder",)


def test_primary_decision_plus_stakeholder_failure_is_partial_not_success():
    storage = Mock()
    storage.add.side_effect = ["decision-1", None]
    with patch.object(cmd_decision, "_decision_storage", return_value=storage), patch(
        "tools.contact_resolver.resolve", return_value=SimpleNamespace(status="not_found")
    ):
        result = cmd_decision._create_decision(_identity(), "Decision", "general", 10, ["Dana"])

    assert result.status == "PARTIAL"
    assert result.record_id == "decision-1"
    assert result.failed_steps == ("stakeholder",)
    assert "חלקית" in cmd_decision._decision_new_receipt(result, "Decision")


def test_event_write_success_is_structured():
    storage = Mock()
    storage.add.return_value = "event-1"
    with patch.object(cmd_decision, "_decision_storage", return_value=storage):
        result = cmd_decision._create_decision_event(
            _identity(), "decision-1", {"raw_content": "update"}
        )

    assert result.status == "SUCCESS"
    assert result.record_id == "event-1"
    assert storage.add.call_args.args[0] == Tables.DECISION_EVENTS


def test_event_write_failure_is_not_discarded():
    storage = Mock()
    storage.add.return_value = None
    with patch.object(cmd_decision, "_decision_storage", return_value=storage):
        result = cmd_decision._create_decision_event(
            _identity(), "decision-1", {"raw_content": "update"}
        )

    assert result.status == "FAILED"
    assert result.failed_steps == ("event",)


def test_update_event_failure_cannot_render_full_success():
    bot = Mock()
    msg = SimpleNamespace(text="update", photo=None, document=None, chat=SimpleNamespace(id="c1"), from_user=SimpleNamespace(id="u1"))
    state = {"decision": {"id": "decision-1", "fields": {"Title": "Decision"}}}
    failed = cmd_decision.DecisionPersistenceResult(status="FAILED", failed_steps=("event",))
    with patch("decision_pipeline.run_pipeline", return_value={
        "halted_at": None,
        "result": SimpleNamespace(user_flag="", reason=""),
    }), patch.object(cmd_decision, "_create_decision_event", return_value=failed):
        cmd_decision._handle_update_step(bot, msg, state, lambda *_: _identity())

    reply = bot.send_message.call_args.args[1]
    assert "חלקית" not in reply
    assert "לא הושלם" in reply
    assert "אין זו הצלחה מלאה" not in reply
