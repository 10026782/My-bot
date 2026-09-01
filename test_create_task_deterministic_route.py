"""בדיקות רגרסיה לבעלות ה-Coordinator על תור יצירת משימה מובנה."""

from __future__ import annotations

import os
import logging
import pytest
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-create-task-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:create-task-test")
os.environ.setdefault("AIRTABLE_API_KEY", "patCreateTaskTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appCreateTaskTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import app  # noqa: E402
from airtable_schema import Tables, TaskFields  # noqa: E402
from core.action_gateway import action_gateway  # noqa: E402
from core.router import Handler, Intent, route_request  # noqa: E402
from core.router.router import (  # noqa: E402
    deterministic_create_task_title,
    parse_deterministic_create_task,
)
from identity import Identity, Role  # noqa: E402


def _owner(user_id: str = "owner-deterministic-create-task") -> Identity:
    """יוצר זהות owner מבודדת לבדיקות המסלול הדטרמיניסטי."""
    return Identity(
        user_id=user_id,
        role=Role.OWNER,
        display_name="owner-deterministic-create-task",
        tenant_id="boss_hq",
        domain_id="general",
        channel="telegram",
        external_id="owner-deterministic-create-task",
    )


def test_structured_create_task_rejects_whitespace_only_title():
    assert deterministic_create_task_title("צור משימה ") is None


@pytest.mark.parametrize(
    "text",
    [
        "> Eli: צור משימה: X",
        '"צור משימה X"',
        "> [צור משימה X]",
        "> Eli: > Eli: צור משימה X",
    ],
)
def test_create_task_prefix_and_reply_wrappers_are_normalized(text):
    assert deterministic_create_task_title(text) == "X"


def test_create_task_parser_builds_structured_business_identity():
    parsed = parse_deterministic_create_task(
        "צור משימה פרסום מודעות עד לחמישי הקרוב 6/8/26 בשעה19:00"
    )
    assert parsed.certain is True
    assert parsed.title == "פרסום מודעות"
    assert parsed.due_date == "2026-08-06"
    # due_time is still parsed/validated even though it's excluded from the
    # identity below (BUG-156) — a malformed time must still fail-closed.
    assert parsed.due_time == "19:00"
    # BUG-156: due_time is deliberately excluded from business_identity() —
    # the Tasks table's due-date field is Airtable type "date", not
    # "dateTime", so no write ever persists a time value. Including it in
    # the identity/fingerprint would distinguish two requests whose actual
    # Airtable write ends up byte-identical. See
    # docs/architecture/action-gateway/
    # BUG-156_DUE_TIME_FINGERPRINT_VS_PERSISTENCE_FIX_20260804.md.
    #
    # BUG-TASK-01: table/field keys must be the SAME Tables.TASKS/TaskFields
    # constants the real write payload uses (core/router/task_builders.py::
    # build_create_task_proposal() / core/turn_coordinator_runtime.py::
    # gateway_call()) — this identity payload is what ActionGateway hashes
    # into business_action_fingerprint, and tools/dispatcher.py independently
    # recomputes that same fingerprint from the real dispatched payload at
    # execution time. An ad-hoc "Tasks"/"title" shape here (superficially
    # equivalent, structurally different) made every approved deterministic
    # create_task contract fail Dispatcher's execution-proof check.
    assert parsed.business_identity() == {
        "table": Tables.TASKS,
        "fields": {
            TaskFields.NAME: "פרסום מודעות",
            TaskFields.DUE_DATE: "2026-08-06",
        },
    }


def test_malformed_date_clarifies_before_agent_or_contract():
    identity = _owner(user_id="owner-deterministic-create-task-uncertain")
    route = route_request("צור משימה X עד 31/02/26", "telegram", identity)
    assert route.handler == Handler.CLARIFY
    assert route.tool_allowed is False
    assert route.needs_approval is False


def test_malformed_time_clarifies_before_agent_or_contract():
    identity = _owner(user_id="owner-deterministic-create-task-uncertain-time")
    route = route_request("צור משימה X עד 31/08/26 בשעה 19:0", "telegram", identity)
    assert route.handler == Handler.CLARIFY
    assert route.tool_allowed is False
    assert route.needs_approval is False


def test_deterministic_pending_reply_is_suppressed_when_owner_was_notified():
    identity = _owner(user_id="owner-deterministic-create-task-single-speaker")
    with patch.dict(os.environ, {"OWNER_TELEGRAM_ID": identity.user_id}, clear=False), \
         patch.object(
             app,
             "_queue_approval_detailed",
             return_value={
                 "message": "יש משימה שממתינה לאישור",
                 "owner_notified": True,
                 "created_this_turn": True,
                 "contract_id": "contract-1",
                 "reply_owner": "gateway",
                 "action_tool": "airtable_add",
             },
         ):
        assert app._queue_deterministic_create_task(
            "X", identity.user_id, "telegram", "צור משימה X", identity,
        ) == ""


@pytest.mark.parametrize(
    ("case_id", "text", "expected_title"),
    [
        ("colon", "צור משימה: X", "X"),
        ("no-colon", "צור משימה X", "X"),
        ("date-time", "צור משימה X עד לתאריך Y בשעה Z", "X עד לתאריך Y בשעה Z"),
    ],
)
def test_structured_create_task_is_gateway_owned_without_agent_call(case_id, text, expected_title):
    """מוודא שבקשה מובנית יוצרת contract ממתין בלי קריאת Agent."""
    identity = _owner(user_id=f"owner-deterministic-create-task-{case_id}")
    route = route_request(text, "telegram", identity)
    assert route.intent == Intent.CREATE_TASK
    assert route.handler == Handler.TOOL
    assert route.needs_approval is True

    metadata = {}
    with patch.object(app, "resolve_identity", return_value=identity), \
         patch.object(app.rate_limiter, "is_allowed", return_value=True), \
         patch.object(
             app.client.messages,
             "create",
             side_effect=AssertionError("structured create-task must not call Agent"),
         ), \
         patch(
             "feature_flags.is_enabled",
             side_effect=lambda name: name == "FEATURE_ACTION_GATEWAY",
         ):
        reply = app.run_agent(text, identity.user_id, "telegram", _out_meta=metadata)

    assert reply
    assert metadata["source_module"] == "action_gateway"
    assert metadata["reply_owner"] == "gateway"

    contract = action_gateway.find_live_contracts(identity.memory_key)
    task_contracts = [
        item for item in contract
        if item.tool_name == "airtable_add"
        and item.normalized_payload.get("table") == Tables.TASKS
        and item.normalized_payload.get("fields", {}).get(TaskFields.NAME) == expected_title
    ]
    assert len(task_contracts) == 1
    assert task_contracts[0].status == "pending"
    assert all(item.tool_name != "sheets_append" for item in task_contracts)


def test_unsupported_three_value_tasks_row_fails_closed_with_diagnostic(caplog):
    """מוודא ש-row לא נתמך נכשל בסגירה ומפיק diagnostic מבני."""
    identity = _owner()
    caplog.set_level(logging.WARNING, logger="core.action_gateway")
    with patch.object(app, "resolve_identity", return_value=identity), \
         patch.object(app, "dispatch_tool", side_effect=AssertionError("must not execute")), \
         patch(
             "feature_flags.is_enabled",
             side_effect=lambda name: name == "FEATURE_ACTION_GATEWAY",
         ):
        outcome = app._queue_approval_detailed(
            "sheets_append",
            {"table": "Tasks", "row_data": ["Task text", "", "General"]},
            identity.user_id,
            "telegram",
            user_text="צור משימה: legacy payload",
        )

    assert outcome["ok"] is False
    assert outcome["contract_id"] is None
    assert outcome["created_this_turn"] is False
    assert outcome["terminal_outcome"] == "APPROVAL_QUEUE_NEVER_ATTEMPTED"
    assert "נוצרה" not in outcome["message"]
    assert "[CanonicalizationDiagnostic]" in caplog.text
    assert "values_length=3" in caplog.text
    assert "row_count=1" in caplog.text
    assert "column_count=3" in caplog.text
    assert "converter_reason=unsupported_tasks_positional_shape" in caplog.text
