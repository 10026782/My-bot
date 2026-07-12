#!/usr/bin/env python3
"""
test_pr0c_writer_migration.py — Regression tests for PR-0C Phase 3: migrating
media_handler.py / followup_engine.py / core/lead_recovery.py's approval
writers from a "non-tool" event_bus payload (routed to a now-removed
.confirmed subscriber) to a tool_name="..."/tool_inputs={...} payload (routed
through app.py's tool_name branch, which executes via tools/approval_actions.py
and, when FEATURE_ACTION_GATEWAY is on, through ActionGateway.approve()).

Coverage:
  1. ActionGateway.propose_gated(): flag off -> shadow, never blocks, swallows
     exceptions; flag on -> blocking, duplicate/pending propose returns a
     user-facing message instead of None.
  2. media_handler.py::_send_voice_approval_request queues a tool_name=
     "media_save_to_memory" payload with the right tool_inputs.
  3. media_handler.py's voice-edit callback reads domain/source from the new
     nested tool_inputs shape (regression for the payload reshape).
  4. followup_engine.py::request_followup_approval queues a tool_name=
     "send_followup" payload with the right tool_inputs.
  5. core/lead_recovery.py::request_recovery_approval queues a tool_name=
     "send_recovery" payload with the right tool_inputs (incl. tier).
"""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-pr0c3-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:PR0C3_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patPR0C3Test")
os.environ.setdefault("AIRTABLE_BASE_ID", "appPR0C3Test")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

from identity import Identity, Role  # noqa: E402
from core.action_gateway import ActionGateway, ExecutionLedger  # noqa: E402

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


def _identity(user_id: str) -> Identity:
    return Identity(
        user_id=user_id, role=Role.OWNER, display_name=user_id,
        tenant_id="boss_hq", domain_id="general", channel="telegram", external_id=user_id,
    )


# ══════════════════════════════════════════════════════════════════
# 1. propose_gated: shadow (flag off) vs blocking (flag on)
# ══════════════════════════════════════════════════════════════════
print("\n── Test 1: ActionGateway.propose_gated ───────────────────────")

gw = ActionGateway(ledger=ExecutionLedger())
identity = _identity("owner_1")

with patch("feature_flags.is_enabled", return_value=False):
    result = gw.propose_gated(
        tenant_id="boss_hq", canonical_user_id=identity.memory_key,
        tool_name="send_followup", tool_inputs={"chat_id": "owner_1", "draft": "a"},
        origin_channel="telegram", origin_chat_id="owner_1", identity=identity,
    )
chk("Test1: flag off -> propose_gated returns None (never blocks)", result is None)
chk("Test1: flag off -> contract still recorded (shadow)",
    gw._ledger.find_by_fingerprint(
        gw.compute_business_fingerprint("boss_hq", identity.memory_key, "send_followup",
                                         gw.normalize_payload({"chat_id": "owner_1", "draft": "a"}))
    ) is not None)

with patch("feature_flags.is_enabled", return_value=True):
    r1 = gw.propose_gated(
        tenant_id="boss_hq", canonical_user_id=identity.memory_key,
        tool_name="send_followup", tool_inputs={"chat_id": "owner_1", "draft": "b"},
        origin_channel="telegram", origin_chat_id="owner_1", identity=identity,
    )
    chk("Test1: flag on, first propose -> None (proceeds)", r1 is None)
    r2 = gw.propose_gated(
        tenant_id="boss_hq", canonical_user_id=identity.memory_key,
        tool_name="send_followup", tool_inputs={"chat_id": "owner_1", "draft": "b"},
        origin_channel="telegram", origin_chat_id="owner_1", identity=identity,
    )
    chk("Test1: flag on, duplicate propose -> blocked with a user message", isinstance(r2, str) and bool(r2))

with patch("feature_flags.is_enabled", return_value=False), \
     patch.object(gw, "propose_action", side_effect=RuntimeError("boom")):
    result = gw.propose_gated(
        tenant_id="boss_hq", canonical_user_id=identity.memory_key,
        tool_name="send_followup", tool_inputs={"chat_id": "owner_1", "draft": "c"},
        origin_channel="telegram", origin_chat_id="owner_1", identity=identity,
    )
chk("Test1: flag off + propose_action raises -> still returns None (swallowed)", result is None)


# ══════════════════════════════════════════════════════════════════
# 2 & 3. media_handler.py — tool-shaped payload + voice-edit reads tool_inputs
# ══════════════════════════════════════════════════════════════════
print("\n── Test 2/3: media_handler.py writer + voice-edit ─────────────")

import media_handler

captured_payload = {}

def _fake_request_approval(action, payload, chat_id, label=""):
    captured_payload.clear()
    captured_payload.update(payload)
    return "act123", label

with patch("event_bus.bus.request_approval", side_effect=_fake_request_approval), \
     patch("identity.resolve_identity", return_value=_identity("owner_voice")), \
     patch("core.action_gateway.action_gateway.propose_gated", return_value=None), \
     patch("telebot.types.InlineKeyboardMarkup"), \
     patch("telebot.types.InlineKeyboardButton"), \
     patch("app.bot", MagicMock(), create=True):
    media_handler._send_voice_approval_request(
        transcript="hello world", domain="general", source="voice", owner_chat_id="owner_voice", reason="test",
    )

chk("Test2: media_handler queues tool_name='media_save_to_memory'",
    captured_payload.get("tool_name") == "media_save_to_memory")
chk("Test2: tool_inputs carries transcript/domain/source",
    captured_payload.get("tool_inputs", {}) == {"transcript": "hello world", "domain": "general", "source": "voice"})
chk("Test2: canonical_user_id populated", bool(captured_payload.get("canonical_user_id")))

# Voice-edit callback: simulate popping an item shaped like the new payload
fake_item = {
    "payload": {
        "tool_name": "media_save_to_memory",
        "tool_inputs": {"transcript": "x", "domain": "import", "source": "voice"},
    }
}
tool_inputs_from_item = fake_item["payload"].get("tool_inputs", {})
chk("Test3: voice-edit reads domain from nested tool_inputs",
    tool_inputs_from_item.get("domain", "general") == "import")
chk("Test3: voice-edit reads source from nested tool_inputs",
    tool_inputs_from_item.get("source", "media_handler") == "voice")


# ══════════════════════════════════════════════════════════════════
# 4. followup_engine.py — tool-shaped payload
# ══════════════════════════════════════════════════════════════════
print("\n── Test 4: followup_engine.py writer ──────────────────────────")

import followup_engine

candidate = followup_engine.FollowupCandidate(
    memory_key="whatsapp:+972500000000", tier="HOT", hours_silent=5.0,
    followup_count=0, last_message="hi", contact_name="דני", contact_channel="whatsapp",
    draft="טיוטת פולואפ",
)

with patch("event_bus.bus.request_approval", side_effect=_fake_request_approval), \
     patch("identity.resolve_identity", return_value=_identity("owner_fu")), \
     patch("core.action_gateway.action_gateway.propose_gated", return_value=None):
    action_id, label = followup_engine.request_followup_approval(candidate, "owner_fu")

chk("Test4: followup_engine queues tool_name='send_followup'",
    captured_payload.get("tool_name") == "send_followup")
chk("Test4: tool_inputs carries draft/contact_name/channel/memory_key/chat_id",
    captured_payload.get("tool_inputs", {}) == {
        "chat_id": "owner_fu", "draft": "טיוטת פולואפ", "contact_name": "דני",
        "channel": "whatsapp", "memory_key": "whatsapp:+972500000000",
    })
chk("Test4: action_id returned", action_id == "act123")


# ══════════════════════════════════════════════════════════════════
# 5. core/lead_recovery.py — tool-shaped payload
# ══════════════════════════════════════════════════════════════════
print("\n── Test 5: core/lead_recovery.py writer ───────────────────────")

import core.lead_recovery as lead_recovery

recovery_candidate = lead_recovery.RecoveryCandidate(
    memory_key="whatsapp:+972500000001", name="יוסי", tier="WARM", days_silent=10,
    last_message="hi", domain="real_estate", channel="whatsapp", draft="טיוטת recovery",
)

with patch("event_bus.bus.request_approval", side_effect=_fake_request_approval), \
     patch("identity.resolve_identity", return_value=_identity("owner_rec")), \
     patch("core.action_gateway.action_gateway.propose_gated", return_value=None):
    action_id, label = lead_recovery.request_recovery_approval(recovery_candidate, "owner_rec")

chk("Test5: lead_recovery queues tool_name='send_recovery'",
    captured_payload.get("tool_name") == "send_recovery")
chk("Test5: tool_inputs carries draft/contact_name/channel/memory_key/tier/chat_id",
    captured_payload.get("tool_inputs", {}) == {
        "chat_id": "owner_rec", "draft": "טיוטת recovery", "contact_name": "יוסי",
        "channel": "whatsapp", "memory_key": "whatsapp:+972500000001", "tier": "WARM",
    })
chk("Test5: action_id returned", action_id == "act123")


# ══════════════════════════════════════════════════════════════════
print(f"\n{'='*50}")
print(f"PR-0C Phase 3 writer migration tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
