# test_c89_preview_confirmation.py — BUG-056: C89 Tier 1 preview confirmation
#
# Covers the fix for the dead-end preview flow: LCH used to store
# session["pending_lead_preview"] and nothing ever read it back, so "כן"
# always fell through to "אין פעולה שממתינה לאישור". Now _propose_lead_write()
# registers a real ActionContract via ActionGateway, and app.py's confirm/
# cancel-word handling checks Gateway live contracts first (regardless of
# FEATURE_ACTION_GATEWAY, which defaults off).

import os, sys
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:TEST")
os.environ.setdefault("AIRTABLE_API_KEY", "patTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

from dataclasses import dataclass, field
from unittest.mock import patch

from core.action_gateway import ActionGateway, ExecutionLedger
import core.lead_candidate_handler as lch

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


VALID_REC_ID = "recXOW7FBZQZcNdw1"
LEAD_TEXT = "משה כהן 0501234567"


def _ok_executor(tool_name, tool_inputs, contract_id):
    return {
        "ok": True,
        "tool": tool_name,
        "external_id": VALID_REC_ID,
        "evidence": {"record_id": VALID_REC_ID},
        "user_message": f"✅ רשומה נוספה | ID: {VALID_REC_ID}",
    }


def _new_gw(executor=None):
    return ActionGateway(ledger=ExecutionLedger(), tool_executor=executor)


def test_tier1_auto_capture_off_shows_preview():
    """Tier 1 lead with FEATURE_AUTO_CAPTURE=false -> preview message, no write."""
    identity = MockIdentity()
    gw = _new_gw(executor=_ok_executor)
    with patch.object(lch, "_at_find_lead", return_value=None), \
         patch("core.action_gateway.action_gateway", gw), \
         patch("feature_flags.is_enabled", return_value=False):
        reply = lch.handle_lead_candidate(identity, LEAD_TEXT, "chat_p1", "telegram")
    assert reply is not None, "Tier 1 preview must reply, not fall through to Agent"
    assert "לשמור" in reply and "כן" in reply, f"reply={reply!r}"
    assert "משה כהן" in reply, f"reply={reply!r}"
    live = gw.find_live_contracts(identity.memory_key)
    assert len(live) == 1, f"expected exactly 1 live (pending) contract, got {len(live)}"
    assert live[0].tool_name == "airtable_add", f"tool_name={live[0].tool_name}"
    return "OK"


def test_confirm_yes_resolves_via_gateway_and_writes():
    """Reply 'כן' -> pending preview found and lead write goes through Gateway."""
    identity = MockIdentity()
    gw = _new_gw(executor=_ok_executor)
    with patch.object(lch, "_at_find_lead", return_value=None), \
         patch("core.action_gateway.action_gateway", gw), \
         patch("feature_flags.is_enabled", return_value=False):
        preview_reply = lch.handle_lead_candidate(identity, LEAD_TEXT, "chat_p2", "telegram")
        assert preview_reply is not None

        # Simulate app.py's confirm-word handling: ActionGateway live
        # contracts checked first, regardless of FEATURE_ACTION_GATEWAY.
        live_before = gw.find_live_contracts(identity.memory_key)
        assert len(live_before) == 1, "must find the real pending contract from the preview"

        confirm_reply = gw.route_confirmation_word(identity.memory_key)

    assert confirm_reply is not None
    assert "בוצע" in confirm_reply or VALID_REC_ID in confirm_reply, f"confirm_reply={confirm_reply!r}"
    live_after = gw.find_live_contracts(identity.memory_key)
    assert len(live_after) == 0, "contract must no longer be pending after execution"
    contract = gw.find_contract(live_before[0].contract_id)
    assert contract.status == "executed", f"status={contract.status}"
    assert contract.normalized_payload.get("_source") == "lead_capture", \
        "write must go through dispatch_tool with _source=lead_capture (Leads write gate), not a raw call"
    return "OK"


def test_cancel_no_clears_pending_no_write():
    """Reply 'לא' -> pending preview cleared, no write."""
    identity = MockIdentity()
    gw = _new_gw(executor=_ok_executor)
    with patch.object(lch, "_at_find_lead", return_value=None), \
         patch("core.action_gateway.action_gateway", gw), \
         patch("feature_flags.is_enabled", return_value=False):
        preview_reply = lch.handle_lead_candidate(identity, LEAD_TEXT, "chat_p3", "telegram")
        assert preview_reply is not None
        live_before = gw.find_live_contracts(identity.memory_key)
        assert len(live_before) == 1

        cancel_reply = gw.route_cancellation_word(identity.memory_key)

    assert cancel_reply is not None
    assert "בוטל" in cancel_reply, f"cancel_reply={cancel_reply!r}"
    live_after = gw.find_live_contracts(identity.memory_key)
    assert len(live_after) == 0, "no contract should remain pending after cancel"
    contract = gw.find_contract(live_before[0].contract_id)
    assert contract.status == "rejected", f"status={contract.status}"
    # Confirming afterward must find nothing pending (no accidental write).
    with patch("core.action_gateway.action_gateway", gw):
        confirm_after_cancel = gw.route_confirmation_word(identity.memory_key)
    assert confirm_after_cancel == "אין פעולה שממתינה לאישור.", f"got={confirm_after_cancel!r}"
    return "OK"


def test_repeated_tier1_input_no_duplicate_lead():
    """Repeated Tier 1 input (same text, before confirmation) -> no duplicate pending contract."""
    identity = MockIdentity()
    gw = _new_gw(executor=_ok_executor)
    with patch.object(lch, "_at_find_lead", return_value=None), \
         patch("core.action_gateway.action_gateway", gw), \
         patch("feature_flags.is_enabled", return_value=False):
        reply1 = lch.handle_lead_candidate(identity, LEAD_TEXT, "chat_p4", "telegram")
        reply2 = lch.handle_lead_candidate(identity, LEAD_TEXT, "chat_p4", "telegram")

    assert reply1 is not None and reply2 is not None
    live = gw.find_live_contracts(identity.memory_key)
    assert len(live) == 1, f"repeated identical Tier 1 input must not create a second pending contract, got {len(live)}"
    assert "כבר יש בקשת אישור" in reply2 or "כבר קיימת" in reply2, f"reply2={reply2!r}"
    return "OK"


def test_repeated_tier1_after_execution_needs_override():
    """Repeated Tier 1 input AFTER the first was confirmed/executed -> duplicate-executed override flow, no silent re-write."""
    identity = MockIdentity()
    gw = _new_gw(executor=_ok_executor)
    with patch.object(lch, "_at_find_lead", return_value=None), \
         patch("core.action_gateway.action_gateway", gw), \
         patch("feature_flags.is_enabled", return_value=False):
        lch.handle_lead_candidate(identity, LEAD_TEXT, "chat_p5", "telegram")
        gw.route_confirmation_word(identity.memory_key)  # executes it

        reply_again = lch.handle_lead_candidate(identity, LEAD_TEXT, "chat_p5", "telegram")

    assert reply_again is not None
    assert "בצע שוב" in reply_again or "כבר בוצעה" in reply_again, f"reply_again={reply_again!r}"
    executed = [c for c in gw._ledger._store.values() if c.status == "executed"]
    assert len(executed) == 1, f"must still be exactly 1 executed contract, got {len(executed)}"
    return "OK"


def test_existing_lead_preview_says_update_not_generic_save():
    """C89 UX: when the candidate matches an existing lead (airtable_update),
    the preview must ask 'לעדכן אותו?' — not the generic new-lead 'לשמור?'."""
    identity = MockIdentity()
    gw = _new_gw(executor=_ok_executor)
    with patch.object(lch, "_at_find_lead", return_value="recEXISTING0000001"), \
         patch("core.action_gateway.action_gateway", gw), \
         patch("feature_flags.is_enabled", return_value=False):
        reply = lch.handle_lead_candidate(identity, LEAD_TEXT, "chat_p6", "telegram")
    assert reply is not None
    assert "מצאתי ליד קיים" in reply and "לעדכן אותו" in reply, f"reply={reply!r}"
    assert "לשמור? ענה" not in reply, f"reply must not use the generic new-lead wording: {reply!r}"
    live = gw.find_live_contracts(identity.memory_key)
    assert len(live) == 1 and live[0].tool_name == "airtable_update", \
        f"expected 1 pending airtable_update contract, got {live}"
    return "OK"


def test_existing_lead_update_requires_approval_even_with_auto_capture():
    """C89 UX: updates to an existing lead always require approval, even when
    FEATURE_AUTO_CAPTURE=true — only brand-new leads may auto-write."""
    identity = MockIdentity()
    gw = _new_gw(executor=_ok_executor)
    with patch.object(lch, "_at_find_lead", return_value="recEXISTING0000002"), \
         patch("core.action_gateway.action_gateway", gw), \
         patch("feature_flags.is_enabled", return_value=True):
        reply = lch.handle_lead_candidate(identity, LEAD_TEXT, "chat_p7", "telegram")
    assert reply is not None
    assert "מצאתי ליד קיים" in reply and "לעדכן אותו" in reply, \
        f"auto_capture=true must still preview an update, not silently write: {reply!r}"
    live = gw.find_live_contracts(identity.memory_key)
    assert len(live) == 1 and live[0].tool_name == "airtable_update" and live[0].status == "pending", \
        f"update must stay pending (never auto-executed), got {live}"
    return "OK"


def test_new_lead_still_auto_writes_with_auto_capture():
    """Control: a brand-new lead (no existing match) still auto-writes
    immediately when FEATURE_AUTO_CAPTURE=true — only updates are gated."""
    identity = MockIdentity()
    gw = _new_gw(executor=_ok_executor)
    with patch.object(lch, "_at_find_lead", return_value=None), \
         patch("core.action_gateway.action_gateway", gw), \
         patch("feature_flags.is_enabled", return_value=True), \
         patch("tools.airtable_gateway.airtable_create", return_value={"id": "recNEWLEAD00000001"}):
        reply = lch.handle_lead_candidate(identity, LEAD_TEXT, "chat_p8", "telegram")
    assert reply is not None
    assert "לעדכן אותו" not in reply, f"new lead must not use update wording: {reply!r}"
    live = gw.find_live_contracts(identity.memory_key)
    assert len(live) == 0, f"new lead with auto_capture=true must not leave a pending contract: {live}"
    return "OK"


def test_app_py_confirm_word_checks_gateway_before_flag_branch():
    """Static check: app.py's confirm-word block checks ActionGateway live
    contracts BEFORE the FEATURE_ACTION_GATEWAY-gated branch, so LCH's
    always-on-Gateway preview contracts resolve regardless of the flag."""
    src = open(os.path.join(os.path.dirname(__file__), "app.py"), encoding="utf-8").read()
    marker = 'elif _lower in _CONFIRM_WORDS:'
    idx = src.index(marker)
    block = src[idx: idx + 1200]
    gw_check_idx = block.index("find_live_contracts")
    flag_check_idx = block.index('_flag_cw("FEATURE_ACTION_GATEWAY")')
    assert gw_check_idx < flag_check_idx, \
        "find_live_contracts() check must come before the FEATURE_ACTION_GATEWAY flag branch"
    assert "_CANCEL_WORDS" in src[idx: idx + 3000], "cancel-word branch must exist alongside confirm-word"
    return "OK"


TESTS = [
    test_tier1_auto_capture_off_shows_preview,
    test_confirm_yes_resolves_via_gateway_and_writes,
    test_cancel_no_clears_pending_no_write,
    test_repeated_tier1_input_no_duplicate_lead,
    test_repeated_tier1_after_execution_needs_override,
    test_existing_lead_preview_says_update_not_generic_save,
    test_existing_lead_update_requires_approval_even_with_auto_capture,
    test_new_lead_still_auto_writes_with_auto_capture,
    test_app_py_confirm_word_checks_gateway_before_flag_branch,
]


def run():
    p = f = 0
    for t in TESTS:
        try:
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
