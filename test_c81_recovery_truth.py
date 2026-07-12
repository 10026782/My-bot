"""C81-FU regression tests for honest recovery completion state."""

from __future__ import annotations

import os

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-c81-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:C81_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patC81Test")
os.environ.setdefault("AIRTABLE_BASE_ID", "appC81Test")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import core.output_gateway as output_gateway
import tools.approval_actions as approval_actions
from core.action_result import ActionResult, ClaimType
from core.output_gateway import GatewayResult
from tools.telegram_adapter import send_telegram


def _telegram_result(*, delivered: bool) -> GatewayResult:
    action_result = ActionResult(
        tool_called=True,
        tool_http_ok=delivered,
        business_success=delivered,
        delivery_attempted=True,
        delivery_success=delivered,
        adapter_mode="live",
        claim_type=ClaimType.SENT,
        source="telegram_adapter",
    )
    return GatewayResult.internal_pass("audit-c81", action_result)


def test_owner_draft_delivery_does_not_complete_customer_recovery(monkeypatch):
    """An owner preview is not proof that the customer received anything."""
    updates = []

    monkeypatch.setattr(
        "core.output_gateway.send_outbound",
        lambda envelope: _telegram_result(delivered=True),
    )
    monkeypatch.setattr(
        "lead_memory.lead_memory.update",
        lambda *args, **kwargs: updates.append((args, kwargs)),
    )

    result = approval_actions.send_recovery(
        chat_id="owner-chat",
        draft="Recovery draft",
        contact_name="Customer",
        channel="whatsapp",
        memory_key="whatsapp:+972500000000",
        tier="WARM",
    )

    assert result["ok"] is True
    assert updates == []


def test_unverified_owner_draft_is_reported_and_does_not_complete_recovery(monkeypatch):
    updates = []

    monkeypatch.setattr(
        "core.output_gateway.send_outbound",
        lambda envelope: _telegram_result(delivered=False),
    )
    monkeypatch.setattr(
        "lead_memory.lead_memory.update",
        lambda *args, **kwargs: updates.append((args, kwargs)),
    )

    result = approval_actions.send_recovery(
        chat_id="owner-chat", draft="Recovery draft", memory_key="lead-2",
    )

    assert result["ok"] is False
    assert result["user_message"].startswith("⚠️")
    assert updates == []


class _TelegramResponse:
    def __init__(self, *, is_success: bool, payload: dict):
        self.is_success = is_success
        self._payload = payload

    def json(self) -> dict:
        return self._payload


def test_telegram_adapter_returns_verified_delivery(monkeypatch):
    monkeypatch.setattr(output_gateway._gateway_context, "approved", True, raising=False)
    monkeypatch.setattr(
        "tools.telegram_adapter.httpx.post",
        lambda *args, **kwargs: _TelegramResponse(
            is_success=True,
            payload={"ok": True, "result": {"message_id": 81}},
        ),
    )

    result = send_telegram("owner-chat", "Recovery draft")

    assert result.delivery_attempted is True
    assert result.delivery_success is True
    assert result.business_success is True


def test_telegram_adapter_rejects_unverified_api_response(monkeypatch):
    monkeypatch.setattr(output_gateway._gateway_context, "approved", True, raising=False)
    monkeypatch.setattr(
        "tools.telegram_adapter.httpx.post",
        lambda *args, **kwargs: _TelegramResponse(
            is_success=True,
            payload={"ok": False, "description": "chat not found"},
        ),
    )

    result = send_telegram("owner-chat", "Recovery draft")

    assert result.delivery_attempted is True
    assert result.delivery_success is False
    assert result.business_success is False
    assert result.error == "chat not found"
