#!/usr/bin/env python3
"""Focused F52-G2 regression tests for edited voice saves."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import os

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-f52-g2-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:F52_G2_TEST")
os.environ.setdefault("AIRTABLE_API_KEY", "patF52G2Test")
os.environ.setdefault("AIRTABLE_BASE_ID", "appF52G2Test")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import media_handler as mh


def _item(contract_id, transcript):
    return {"payload": {
        "tool_name": "media_save_to_memory",
        "tool_inputs": {"transcript": transcript, "domain": "general", "source": "voice"},
        "canonical_user_id": "owner",
        "tenant_id": "boss_hq",
        "contract_id": contract_id,
    }}


def _gateway(old):
    gw = MagicMock()
    gw.find_contract.return_value = old
    gw._ledger.find_by_fingerprint.return_value = old
    return gw


def test_old_contract_is_superseded_before_edit_staging():
    old = SimpleNamespace(contract_id="A", status="pending")
    with patch("core.action_gateway.action_gateway", _gateway(old)) as gw:
        assert mh._supersede_voice_contract(_item("A", "payload A"))
        gw.supersede_if_pending.assert_called_once_with("A")


def test_replacement_request_contains_exactly_edited_payload():
    payloads = []
    callbacks, messages = [], []
    bot = MagicMock()
    bot.callback_query_handler.side_effect = lambda **kwargs: lambda fn: callbacks.append(fn) or fn
    bot.message_handler.side_effect = lambda **kwargs: lambda fn: messages.append(fn) or fn
    old = SimpleNamespace(contract_id="A", status="pending")
    new = SimpleNamespace(contract_id="B", status="pending")
    gateway = _gateway(old)
    gateway._ledger.find_by_fingerprint.side_effect = [old, new]
    gateway.find_contract.side_effect = [old]
    gateway.propose_gated.return_value = None

    def request_approval(**kwargs):
        payloads.append(kwargs["payload"])
        return "bus-B", "label"

    with patch("core.action_gateway.action_gateway", gateway), \
         patch("event_bus.bus.request_approval", side_effect=request_approval), \
         patch("identity.resolve_identity", return_value=SimpleNamespace(
             memory_key="owner", tenant_id="boss_hq")), \
         patch("telebot.types.InlineKeyboardMarkup"), \
         patch("telebot.types.InlineKeyboardButton"), \
        patch("app.bot", bot, create=True):
        mh._voice_callbacks_registered = False
        mh._register_voice_callbacks(bot)
        bus = MagicMock()
        bus.pop.return_value = _item("A", "payload A")
        with patch("event_bus.bus", bus):
            callbacks[0](SimpleNamespace(
                data="voice_edit:bus-A", id="cb", from_user=SimpleNamespace(id="owner"),
                message=SimpleNamespace(chat=SimpleNamespace(id="owner"), message_id=1),
            ))
        with patch.object(mh, "_send_voice_approval_request", return_value="📨 queued") as replacement:
            messages[0](SimpleNamespace(
                text="payload B", from_user=SimpleNamespace(id="owner"),
                chat=SimpleNamespace(id="owner"),
            ))
            replacement.assert_called_once_with(
                "payload B", "general", "voice", "owner", reason="עריכת תמלול",
            )
        gateway._ledger.find_by_fingerprint.return_value = new
        gateway._ledger.find_by_fingerprint.side_effect = None
        mh._send_voice_approval_request(
            "payload B", "general", "voice", "owner", reason="עריכת תמלול",
        )

    assert payloads[-1]["tool_inputs"] == {
        "transcript": "payload B", "domain": "general", "source": "voice",
    }
    assert payloads[-1]["contract_id"] == "B"


def test_edit_never_calls_direct_memory_writer():
    old = SimpleNamespace(contract_id="A", status="pending")
    with patch("core.action_gateway.action_gateway", _gateway(old)), \
         patch.object(mh, "_save_transcript_to_memory") as direct_save:
        assert mh._supersede_voice_contract(_item("A", "payload A"))
        direct_save.assert_not_called()


def test_multiple_edits_only_latest_contract_can_execute():
    a = SimpleNamespace(contract_id="A", status="pending")
    b = SimpleNamespace(contract_id="B", status="pending")
    gateway = _gateway(a)
    with patch("core.action_gateway.action_gateway", gateway):
        assert mh._supersede_voice_contract(_item("A", "A"))
        gateway.find_contract.return_value = b
        assert mh._supersede_voice_contract(_item("B", "B"))
    assert [c.args[0] for c in gateway.supersede_if_pending.call_args_list] == ["A", "B"]


def test_cancelled_replacement_does_not_persist():
    replacement = SimpleNamespace(contract_id="B", status="rejected")
    gateway = _gateway(replacement)
    with patch("core.action_gateway.action_gateway", gateway), \
         patch.object(mh, "_save_transcript_to_memory") as direct_save:
        assert mh._supersede_voice_contract(_item("B", "edited"))
        direct_save.assert_not_called()


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
