#!/usr/bin/env python3
"""
test_memory_shadow_command.py — owner-gate + wiring regression test for
/memory_shadow (Phase 2B), plus format_shadow_comparison()/build_shadow_request()
unit coverage.

/memory_shadow is a thin owner-only wrapper, same shape as /boss_doctor:
authorize -> build_shadow_request() -> compare_with_live_paths() ->
format_shadow_comparison() -> reply. No mutation path, no secret exposure,
no prompt/context change.
"""

from __future__ import annotations

import os
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:TEST")
os.environ.setdefault("ELIYAHU_CHAT_ID", "1")
os.environ.setdefault("AIRTABLE_API_KEY", "patTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import logging
logging.disable(logging.CRITICAL)

from unittest.mock import patch

import telebot
import app
import core.memory_retrieval_shadow as shadow_module
from core.memory_retrieval_contract import (
    BusinessMemoryItem,
    MemoryRetrievalRequest,
    MemorySnapshot,
    SnapshotMetadata,
)
from core.memory_retrieval_shadow import ShadowComparison, build_shadow_request, format_shadow_comparison

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


class _FakeUser:
    id = 1


class _FakeChat:
    id = 12345


class _FakeMsg:
    from_user = _FakeUser()
    chat = _FakeChat()


def _identity(role: str, tenant_id: str = "boss_hq", user_id: str = "1", domain_id: str = "general"):
    return type("I", (), {
        "role": role,
        "tenant_id": tenant_id,
        "user_id": user_id,
        "domain_id": domain_id,
        "memory_key": f"{tenant_id}:{user_id}",
    })()


def _snapshot(*, business=(), episodic=(), bm_available=True, bm_error=None,
              ep_available=True, ep_error=None, bm_budget=5, ep_budget=20):
    meta = SnapshotMetadata(
        generated_at=0.0, tenant_id="boss_hq", canonical_user_id="1",
        session_id=None, entity_type=None, entity_id=None, domain_id="general",
        business_memory_available=bm_available, business_memory_error=bm_error,
        business_memory_returned=len(business), business_memory_budget=bm_budget,
        episodic_memory_available=ep_available, episodic_memory_error=ep_error,
        episodic_memory_returned=len(episodic), episodic_memory_budget=ep_budget,
    )
    return MemorySnapshot(business_facts=tuple(business), episodic_entries=tuple(episodic), metadata=meta)


def _comparison(**kw):
    snapshot = _snapshot(**kw)
    request = MemoryRetrievalRequest(tenant_id="boss_hq", canonical_user_id="1")
    return ShadowComparison(
        request=request,
        live_conversation_message_count=3,
        live_business_memory_char_count=120,
        new_snapshot=snapshot,
    )


# ══════════════════════════════════════════════════
# 1. Owner allowed
# ══════════════════════════════════════════════════

print("\n── owner can run /memory_shadow ─")

sentinel_comparison = _comparison(business=[BusinessMemoryItem(
    record_id="rec1", title="t", description="d", event_type=None, domain=None, occurred_at=None,
)])

calls = []
with patch("app.resolve_identity") as mock_identity, \
     patch.object(app.bot, "send_message", side_effect=lambda cid, text, **kw: calls.append((cid, text))), \
     patch.object(shadow_module, "compare_with_live_paths", return_value=sentinel_comparison) as mock_compare:
    mock_identity.return_value = _identity("owner")
    app.cmd_memory_shadow(_FakeMsg())

chk("owner gets exactly one reply", len(calls) == 1)
chk("reply goes to the requesting chat", calls and calls[0][0] == 12345)
chk("reply contains the Memory Shadow header", calls and "Memory Shadow" in calls[0][1])
chk("compare_with_live_paths() called exactly once", mock_compare.call_count == 1)


# ══════════════════════════════════════════════════
# 2. Non-owner denied
# ══════════════════════════════════════════════════

print("\n── non-owner roles are rejected ─")

for role in ("partner", "manager", "employee", "lead", "guest", "readonly"):
    calls = []
    with patch("app.resolve_identity") as mock_identity, \
         patch.object(app.bot, "send_message", side_effect=lambda cid, text, **kw: calls.append((cid, text))), \
         patch.object(shadow_module, "compare_with_live_paths") as mock_compare:
        mock_identity.return_value = _identity(role)
        app.cmd_memory_shadow(_FakeMsg())
    chk(f"role={role}: compare_with_live_paths() never called", mock_compare.call_count == 0)
    chk(f"role={role}: gets the owner-only denial", len(calls) == 1 and "בעלים" in calls[0][1])

print("── identity=None is rejected ─")
calls = []
with patch("app.resolve_identity") as mock_identity, \
     patch.object(app.bot, "send_message", side_effect=lambda cid, text, **kw: calls.append((cid, text))), \
     patch.object(shadow_module, "compare_with_live_paths") as mock_compare:
    mock_identity.return_value = None
    app.cmd_memory_shadow(_FakeMsg())
chk("identity=None: compare_with_live_paths() never called", mock_compare.call_count == 0)
chk("identity=None: gets the owner-only denial", len(calls) == 1 and "בעלים" in calls[0][1])


# ══════════════════════════════════════════════════
# 3. compare_with_live_paths() wiring — called exactly once, with a request
#    built strictly from proven identity fields
# ══════════════════════════════════════════════════

print("\n── compare_with_live_paths() wiring ─")

calls = []
with patch("app.resolve_identity") as mock_identity, \
     patch.object(app.bot, "send_message", side_effect=lambda cid, text, **kw: calls.append((cid, text))), \
     patch.object(shadow_module, "compare_with_live_paths", return_value=sentinel_comparison) as mock_compare:
    mock_identity.return_value = _identity("owner", tenant_id="boss_hq", user_id="42")
    app.cmd_memory_shadow(_FakeMsg())

chk("compare_with_live_paths() called exactly once", mock_compare.call_count == 1)
called_request = mock_compare.call_args[0][0]
chk("request built from identity's tenant_id", called_request.tenant_id == "boss_hq")
chk("request built from identity's canonical_user_id", called_request.canonical_user_id == "42")
chk("request session_id left unset (no provable source)", called_request.session_id is None)
chk("request entity_type/entity_id left unset (no provable source)",
    called_request.entity_type is None and called_request.entity_id is None)
chk("memory_key passed through from identity", mock_compare.call_args.kwargs.get("memory_key") == "boss_hq:42")


# ══════════════════════════════════════════════════
# 4 & 5. No writes, no prompt/context mutation
# ══════════════════════════════════════════════════

print("\n── /memory_shadow never mutates anything ─")


def _boom(*a, **k):
    raise AssertionError("cmd_memory_shadow must never call a mutating function")


import feature_flags
import tools.dispatcher as dispatcher
from core.episodic_memory_repository import EpisodicMemoryRepository

calls = []
with patch("app.resolve_identity") as mock_identity, \
     patch.object(app.bot, "send_message", side_effect=lambda cid, text, **kw: calls.append((cid, text))), \
     patch.object(feature_flags, "set_flag", _boom, create=True), \
     patch.object(feature_flags, "set_emergency_stop", _boom, create=True), \
     patch.object(dispatcher, "dispatch_tool", _boom, create=True), \
     patch.object(EpisodicMemoryRepository, "insert", _boom), \
     patch("tools.airtable_gateway.airtable_create", _boom):
    mock_identity.return_value = _identity("owner")
    app.cmd_memory_shadow(_FakeMsg())

chk("real run through poisoned mutation paths still succeeds (none were called)", len(calls) == 1)

import memory_store as memory_store_module
before = memory_store_module.memory.get_for_claude("boss_hq:1")
calls = []
with patch("app.resolve_identity") as mock_identity, \
     patch.object(app.bot, "send_message", side_effect=lambda cid, text, **kw: calls.append((cid, text))):
    mock_identity.return_value = _identity("owner")
    app.cmd_memory_shadow(_FakeMsg())
after = memory_store_module.memory.get_for_claude("boss_hq:1")
chk("memory_store conversation state unchanged by the command", before == after)


# ══════════════════════════════════════════════════
# 6-8. Category failures/emptiness surfaced in output, never raise
# ══════════════════════════════════════════════════

print("\n── category failures/emptiness surfaced in output, never raise ─")

text = format_shadow_comparison(_comparison(episodic=(), ep_available=True))
chk("empty episodic result handled: 'episodic: 0 items' in output", "episodic: 0 items" in text)

text = format_shadow_comparison(_comparison(bm_available=False, bm_error="airtable down"))
chk("Airtable/business-memory failure surfaced: available=False in output",
    "available=False" in text and "airtable down" in text)

text = format_shadow_comparison(_comparison(ep_available=False, ep_error="postgres down"))
chk("Postgres/episodic failure surfaced: available=False in output",
    "available=False" in text and "postgres down" in text)


# ══════════════════════════════════════════════════
# 9 & 10. Budget differences + ordering differences surfaced
# ══════════════════════════════════════════════════

print("\n── budget truncation and ordering differences surfaced ─")

full_budget_items = tuple(
    BusinessMemoryItem(record_id=f"r{i}", title="t", description="d", event_type=None, domain=None, occurred_at=None)
    for i in range(5)
)
text = format_shadow_comparison(_comparison(business=full_budget_items, bm_budget=5))
chk("budget truncation surfaced when returned == budget", "truncated=possibly" in text)

text = format_shadow_comparison(_comparison(business=full_budget_items[:2], bm_budget=5))
chk("no truncation flagged when returned < budget", "truncated=no" in text)

text = format_shadow_comparison(_comparison())
chk("ordering difference note present", "Ordering:" in text and "deterministic-recency" in text)


# ══════════════════════════════════════════════════
# 11. No secrets in output
# ══════════════════════════════════════════════════

print("\n── no secret leakage through the command reply ─")

secret = "SECRET_MARKER_MEMORY_SHADOW"
calls = []
with patch("app.resolve_identity") as mock_identity, \
     patch.object(app.bot, "send_message", side_effect=lambda cid, text, **kw: calls.append((cid, text))), \
     patch.object(shadow_module, "compare_with_live_paths", return_value=sentinel_comparison), \
     patch.dict(os.environ, {"AIRTABLE_API_KEY": secret}):
    mock_identity.return_value = _identity("owner")
    app.cmd_memory_shadow(_FakeMsg())
chk("secret env value never appears in the reply", calls and secret not in calls[0][1])

text = format_shadow_comparison(_comparison(business=(BusinessMemoryItem(
    record_id="rec1", title="SENSITIVE_TITLE", description="SENSITIVE_DESC",
    event_type=None, domain=None, occurred_at=None,
),)))
chk("business memory item text (title/description) never appears in formatted output",
    "SENSITIVE_TITLE" not in text and "SENSITIVE_DESC" not in text)


# ══════════════════════════════════════════════════
# 12. Insufficient context fails safely
# ══════════════════════════════════════════════════

print("\n── insufficient context fails safely (NOT_ENOUGH_CONTEXT) ─")

chk("build_shadow_request() returns None for blank tenant_id",
    build_shadow_request(_identity("owner", tenant_id="", user_id="1")) is None)
chk("build_shadow_request() returns None for blank canonical_user_id",
    build_shadow_request(_identity("owner", tenant_id="boss_hq", user_id="")) is None)

calls = []
with patch("app.resolve_identity") as mock_identity, \
     patch.object(app.bot, "send_message", side_effect=lambda cid, text, **kw: calls.append((cid, text))), \
     patch.object(shadow_module, "compare_with_live_paths") as mock_compare:
    mock_identity.return_value = _identity("owner", tenant_id="", user_id="1")
    app.cmd_memory_shadow(_FakeMsg())
chk("NOT_ENOUGH_CONTEXT: compare_with_live_paths() never called", mock_compare.call_count == 0)
chk("NOT_ENOUGH_CONTEXT: reply says so, doesn't crash", len(calls) == 1 and "NOT_ENOUGH_CONTEXT" in calls[0][1])


# ══════════════════════════════════════════════════
# 13. Existing /boss_doctor and /status routing unchanged
# ══════════════════════════════════════════════════

print("\n── regression: /boss_doctor and /status routing unaffected ─")

calls = []
with patch("app.resolve_identity") as mock_identity, \
     patch.object(app.bot, "send_message", side_effect=lambda cid, text, **kw: calls.append((cid, text))):
    mock_identity.return_value = _identity("owner")
    app.cmd_boss_doctor(_FakeMsg())
chk("/boss_doctor still replies for an owner", len(calls) == 1 and "BOSS Doctor" in calls[0][1])

calls = []
with patch("app.resolve_identity") as mock_identity, \
     patch.object(app.bot, "send_message", side_effect=lambda cid, text, **kw: calls.append((cid, text, kw.get("parse_mode")))):
    mock_identity.return_value = _identity("owner")
    app.cmd_status(_FakeMsg())
chk("/status still replies for an owner", len(calls) >= 1)

calls = []
with patch("app.resolve_identity") as mock_identity, \
     patch.object(app.bot, "send_message", side_effect=lambda cid, text, **kw: calls.append((cid, text))), \
     patch.object(shadow_module, "compare_with_live_paths", return_value=sentinel_comparison):
    mock_identity.return_value = _identity("owner")

    update = telebot.types.Update.de_json({
        "update_id": 1,
        "message": {
            "message_id": 1,
            "date": 0,
            "chat": {"id": 12345, "type": "private"},
            "from": {"id": 1, "is_bot": False, "first_name": "t"},
            "text": "/memory_shadow",
        },
    })
    try:
        app.bot.process_new_updates([update])
        dispatch_raised = False
    except Exception:
        dispatch_raised = True

chk("real /memory_shadow dispatch via bot.process_new_updates() does not raise", dispatch_raised is False)
chk("real dispatch delivered a report", len(calls) == 1 and "Memory Shadow" in calls[0][1])


print(f"\n{'='*40}")
print(f"memory_shadow command tests: {passed} passed, {failed} failed")

if __name__ == "__main__":
    import sys
    sys.exit(0 if failed == 0 else 1)
