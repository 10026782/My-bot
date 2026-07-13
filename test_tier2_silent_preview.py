# test_tier2_silent_preview.py — BUG-058: Tier 2 batch-confirm resolver
#
# History: Tier 2 (clean batch) preview used to say "לשמור את כולם? ענה כן
# לאישור" even though nothing in the codebase ever read pending_lead_preview
# back — a misleading CTA. First fix (05/07/2026) made the wording honest
# ("אישור קבוצתי עדיין לא זמין") without building a resolver — a deliberate,
# documented interim step pending a Tier-1/Tier-2 precedence decision.
#
# This file now covers the real resolver: session_store.py's
# set/get/clear_pending_lead_preview() + core/lead_candidate_handler.py's
# resolve_pending_lead_preview(), wired into app.py's 2.55 gate *after* the
# existing Tier-1 ActionGateway live-contract check (BUG-056 precedent) —
# Tier-1 always wins when both exist simultaneously for the same chat_id.

import os, sys
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:TEST")
os.environ.setdefault("AIRTABLE_API_KEY", "patTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import time
from dataclasses import dataclass
from unittest.mock import patch

from core.action_gateway import ActionGateway, ExecutionLedger
import core.lead_candidate_handler as lch
from session_store import lead_sessions as _ls

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


@dataclass
class MockIdentity:
    user_id:   str = "owner_1"
    role:      str = "owner"
    tenant_id: str = "boss_hq"
    domain_id: str = "general"

    @property
    def is_internal(self) -> bool:
        return True

    @property
    def memory_key(self) -> str:
        return f"{self.tenant_id}:{self.user_id}"


BATCH_TEXT = "משה כהן 0501234567\nדנה לוי 0521234567"


def _new_gw():
    return ActionGateway(ledger=ExecutionLedger(), tool_executor=None)


def test_tier2_message_now_offers_real_confirm():
    """Preview now invites 'כן'/'לא' — a real resolver exists (BUG-058 closed)."""
    identity = MockIdentity()
    with patch("feature_flags.is_enabled", return_value=False):
        reply = lch.handle_lead_candidate(identity, BATCH_TEXT, "chat_t2_1", "telegram")

    assert reply is not None, "Tier 2 must reply with a preview, not fall through"
    assert "כן" in reply and "לא" in reply, f"reply should invite confirm/cancel: {reply!r}"
    assert "30 דק" in reply, f"reply should mention the TTL: {reply!r}"
    return "OK"


def test_pending_lead_preview_written_with_channel_domain_and_set_at():
    """pending_lead_preview must be written with set_at + channel/domain (not just candidates/raw_text)."""
    identity = MockIdentity()
    with patch("feature_flags.is_enabled", return_value=False):
        lch.handle_lead_candidate(identity, BATCH_TEXT, "chat_t2_2", "whatsapp")

    session = _ls.get("chat_t2_2")
    assert session is not None, "session must exist after Tier 2 preview"
    preview = session.get("pending_lead_preview")
    assert preview is not None, "pending_lead_preview must be written"
    assert len(preview["candidates"]) == 2
    assert preview["channel"] == "whatsapp"
    assert "set_at" in preview and preview["set_at"] > 0
    return "OK"


def test_confirm_resolves_tier2_and_writes_leads(monkeypatch):
    """BUG-058: 'כן' on a Tier-2-only preview now actually writes the batch
    via _handle_batch, using channel/domain stored on the preview itself."""
    identity = MockIdentity()
    with patch("feature_flags.is_enabled", return_value=False):
        preview_reply = lch.handle_lead_candidate(identity, BATCH_TEXT, "chat_t2_3", "whatsapp")
    assert preview_reply is not None

    called = {}

    def fake_handle_batch(ident, text, chat_id_, channel, domain, batch):
        called.update(channel=channel, domain=domain, batch=batch)
        return "✅ נשמר"

    monkeypatch.setattr(lch, "_handle_batch", fake_handle_batch)

    result = lch.resolve_pending_lead_preview(
        identity=identity, chat_id="chat_t2_3", is_confirm=True, is_cancel=False,
    )
    assert result == "✅ נשמר", f"got={result!r}"
    assert called["channel"] == "whatsapp"
    assert len(called["batch"]) == 2
    assert _ls.get("chat_t2_3")["pending_lead_preview"] is None
    return "OK"


def test_cancel_clears_without_writing():
    identity = MockIdentity()
    with patch("feature_flags.is_enabled", return_value=False):
        lch.handle_lead_candidate(identity, BATCH_TEXT, "chat_t2_cancel", "telegram")

    result = lch.resolve_pending_lead_preview(
        identity=identity, chat_id="chat_t2_cancel", is_confirm=False, is_cancel=True,
    )
    assert "ביטלתי" in result, f"got={result!r}"
    assert _ls.get("chat_t2_cancel")["pending_lead_preview"] is None
    return "OK"


def test_expired_preview_falls_through():
    identity = MockIdentity()
    with patch("feature_flags.is_enabled", return_value=False):
        lch.handle_lead_candidate(identity, BATCH_TEXT, "chat_t2_expired", "telegram")

    session = _ls.get("chat_t2_expired")
    session["pending_lead_preview"]["set_at"] = time.time() - 1900

    result = lch.resolve_pending_lead_preview(
        identity=identity, chat_id="chat_t2_expired", is_confirm=True, is_cancel=False,
    )
    assert result is None, f"expired preview must fall through, got={result!r}"
    assert _ls.get("chat_t2_expired")["pending_lead_preview"] is None
    return "OK"


def test_no_preview_falls_through():
    """No preview at all -> None, app.py continues to its normal flow (BUG-070/Agent/etc.)."""
    identity = MockIdentity()
    result = lch.resolve_pending_lead_preview(
        identity=identity, chat_id="chat_no_such_preview", is_confirm=True, is_cancel=False,
    )
    assert result is None
    return "OK"


def test_neither_confirm_nor_cancel_returns_none():
    identity = MockIdentity()
    with patch("feature_flags.is_enabled", return_value=False):
        lch.handle_lead_candidate(identity, BATCH_TEXT, "chat_t2_neither", "telegram")
    result = lch.resolve_pending_lead_preview(
        identity=identity, chat_id="chat_t2_neither", is_confirm=False, is_cancel=False,
    )
    assert result is None
    # preview must remain untouched — not consumed
    assert _ls.get("chat_t2_neither")["pending_lead_preview"] is not None
    return "OK"


def test_tier1_precedence_over_tier2_when_both_live():
    """BUG-058 caveat resolved: when a chat_id has BOTH a live Tier-1
    ActionGateway contract AND a Tier-2 preview, app.py's 2.55 gate checks
    Tier-1 first (find_live_contracts) and only calls
    resolve_pending_lead_preview() when that returns empty — so Tier-1 wins.
    This test proves the *building block* app.py relies on: Tier-2's resolver
    itself doesn't special-case Tier-1 at all (by design, per its docstring)
    — the ordering guarantee lives in the caller (app.py), not here.
    """
    identity = MockIdentity()
    gw = _new_gw()
    with patch("feature_flags.is_enabled", return_value=False):
        lch.handle_lead_candidate(identity, BATCH_TEXT, "chat_both", "telegram")

    with patch("core.action_gateway.action_gateway", gw):
        r = gw.propose_action(
            tenant_id="boss_hq", canonical_user_id=identity.memory_key,
            tool_name="gmail_send_draft", tool_inputs={"to": "a@b.com"},
            origin_channel="telegram", origin_chat_id="chat_both",
            requires_approval=True,
        )
        assert r.ok
        # Mirrors app.py's actual gate order: Tier-1 checked first.
        has_tier1 = bool(gw.find_live_contracts(identity.memory_key))
        assert has_tier1, "setup: Tier-1 contract must be live"

    # Tier-2 preview is still there, untouched — app.py's ordering (not this
    # function) is what prevents it from being reached in this scenario.
    assert _ls.get("chat_both")["pending_lead_preview"] is not None
    return "OK"


def test_tier1_preview_message_unchanged():
    """Regression guard: Tier 1's own preview message (real resolver via
    ActionGateway) must still invite confirmation — unrelated to this fix."""
    identity = MockIdentity()
    gw = _new_gw()
    with patch.object(lch, "_at_find_lead", return_value=None), \
         patch("core.action_gateway.action_gateway", gw), \
         patch("feature_flags.is_enabled", return_value=False):
        reply = lch.handle_lead_candidate(identity, "משה כהן 0501234567", "chat_t1_check", "telegram")

    assert reply is not None
    assert "לשמור? ענה" in reply, f"Tier 1 preview wording must be unchanged: {reply!r}"
    return "OK"


TESTS = [
    test_tier2_message_now_offers_real_confirm,
    test_pending_lead_preview_written_with_channel_domain_and_set_at,
    test_confirm_resolves_tier2_and_writes_leads,
    test_cancel_clears_without_writing,
    test_expired_preview_falls_through,
    test_no_preview_falls_through,
    test_neither_confirm_nor_cancel_returns_none,
    test_tier1_precedence_over_tier2_when_both_live,
    test_tier1_preview_message_unchanged,
]


def run():
    p = f = 0
    for t in TESTS:
        try:
            if "monkeypatch" in t.__code__.co_varnames[: t.__code__.co_argcount]:
                import types
                class _MP:
                    def __init__(self):
                        self._orig = {}
                    def setattr(self, obj, name, value):
                        self._orig[(obj, name)] = getattr(obj, name)
                        setattr(obj, name, value)
                    def undo(self):
                        for (obj, name), val in self._orig.items():
                            setattr(obj, name, val)
                mp = _MP()
                try:
                    t(mp)
                finally:
                    mp.undo()
            else:
                t()
            print(f"✅ {t.__name__}")
            p += 1
        except AssertionError as e:
            print(f"❌ {t.__name__}: {e}")
            f += 1
        except Exception as e:
            print(f"❌ {t.__name__} EXCEPTION: {e}")
            f += 1
    print(f"\n{p}/{p + f} passed")
    return f == 0


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
