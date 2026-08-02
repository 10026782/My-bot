"""בדיקות למסלול הסטטוס הדטרמיניסטי של פעולה שבוטלה."""

from __future__ import annotations

import logging
import os
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-cancelled-status-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:cancelled-status-test")
os.environ.setdefault("AIRTABLE_API_KEY", "patCancelledStatusTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appCancelledStatusTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import app  # noqa: E402
from airtable_schema import Tables, TaskFields  # noqa: E402
from core.action_gateway import action_gateway  # noqa: E402
from identity import Identity, Role  # noqa: E402


def _cancelled_identity() -> Identity:
    """יוצר זהות קנונית מבודדת למסלול הסטטוס."""
    return Identity(
        user_id="owner-cancelled-status-route",
        role=Role.OWNER,
        display_name="owner-cancelled-status-route",
        tenant_id="boss_hq",
        domain_id="general",
        channel="telegram",
        external_id="owner-cancelled-status-route",
    )


def _seed_cancelled_contract(identity: Identity) -> None:
    """מכניס חוזה משימה לתור ואז דוחה אותו ללא ביצוע כלי."""
    proposal = action_gateway.propose_action(
        tenant_id=identity.tenant_id,
        canonical_user_id=identity.memory_key,
        tool_name="airtable_add",
        tool_inputs={
            "table": Tables.TASKS,
            "fields": {TaskFields.NAME: "do not surface this task"},
        },
        origin_channel="telegram",
        origin_chat_id=identity.user_id,
        requires_approval=True,
        identity=identity,
        trusted_source="agent",
        user_text="צור משימה: do not surface this task",
    )
    assert proposal.ok is True
    assert action_gateway.reject(proposal.contract_id, rejected_by=identity.memory_key).startswith("🚫")


def test_cancelled_status_variants_are_gateway_owned(caplog):
    """מוודא שכל וריאציית ביטול משתמשת רק בחוזה הקנוני וללא Agent."""
    identity = _cancelled_identity()
    _seed_cancelled_contract(identity)
    variants = (
        ("הפעולה בוטלה?", "כן, הפעולה בוטלה."),
        ("הפעולה כבר בוטלה", "נכון, הפעולה כבר בוטלה."),
        ("האם הפעולה בוטלה?", "כן, הפעולה בוטלה."),
        ("זה כבר בוטל?", "כן, הפעולה בוטלה."),
    )
    caplog.set_level(logging.INFO)
    with patch.object(app, "resolve_identity", return_value=identity), \
         patch.object(app.rate_limiter, "is_allowed", return_value=True), \
         patch.object(app, "dispatch_tool", side_effect=AssertionError("no tool execution")) as dispatch, \
         patch.object(
             app.client.messages,
             "create",
             side_effect=AssertionError("cancelled status must not call Agent"),
         ) as agent_call:
        for text, expected in variants:
            metadata = {}
            assert app.run_agent(text, identity.user_id, "telegram", _out_meta=metadata) == expected
            assert metadata["source_module"] == "action_gateway"
            assert metadata["status_route_owner"] == "approval_runtime"

    assert dispatch.call_count == 0
    assert agent_call.call_count == 0
    assert caplog.text.count("status_route_owner=approval_runtime") >= len(variants)
    assert caplog.text.count("terminal_rejection_status=cancelled") >= len(variants)
    assert caplog.text.count("agent_calls=0") >= len(variants)
    assert caplog.text.count("fallback_used=False") >= len(variants)
    assert "handler=agent" not in caplog.text
    assert "POST /v1/messages" not in caplog.text
    assert "airtable_get table=Tasks" not in caplog.text
    assert "status_claim_mismatch" not in caplog.text


def test_cancelled_status_without_proof_is_deterministic_and_does_not_guess():
    """מוודא שאין טענה על ביטול ללא חוזה קנוני דחוי."""
    identity = Identity(
        user_id="owner-cancelled-status-no-proof",
        role=Role.OWNER,
        display_name="owner-cancelled-status-no-proof",
        tenant_id="boss_hq",
        domain_id="general",
        channel="telegram",
        external_id="owner-cancelled-status-no-proof",
    )
    metadata = {}
    with patch.object(app, "resolve_identity", return_value=identity), \
         patch.object(app.rate_limiter, "is_allowed", return_value=True), \
         patch.object(app.client.messages, "create", side_effect=AssertionError("no Agent")) as agent_call:
        reply = app.run_agent("הפעולה בוטלה?", identity.user_id, "telegram", _out_meta=metadata)

    assert reply == "לא מצאתי פעולה אחרונה שבוטלה."
    assert metadata["status_route_owner"] == "approval_runtime"
    assert agent_call.call_count == 0
