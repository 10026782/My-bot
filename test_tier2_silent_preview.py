# test_tier2_silent_preview.py — BUG-058: Tier 2 silent-preview fix
#
# Tier 2 (clean batch) preview used to say "לשמור את כולם? ענה כן לאישור"
# even though nothing in the codebase ever reads pending_lead_preview back —
# "כן" never resolves it (only Tier 1's ActionGateway contract can be
# resolved). This proves: (1) the misleading CTA is gone and replaced with
# observation-only wording, (2) pending_lead_preview is still written (kept
# for audit/future design), (3) a user with ONLY a Tier-2 preview pending who
# says "כן" gets no false confirmation.

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


BATCH_TEXT = "משה כהן 0501234567\nדנה לוי 0521234567"


def _new_gw():
    return ActionGateway(ledger=ExecutionLedger(), tool_executor=None)


def test_tier2_message_is_observation_only():
    """No misleading CTA — no 'reply כן', no 'לאישור', no 'לשמור את כולם'."""
    identity = MockIdentity()
    with patch("feature_flags.is_enabled", return_value=False):
        reply = lch.handle_lead_candidate(identity, BATCH_TEXT, "chat_t2_1", "telegram")

    assert reply is not None, "Tier 2 must reply with a preview, not fall through"
    assert "לשמור את כולם" not in reply, f"old misleading CTA still present: {reply!r}"
    assert "ענה" not in reply, f"reply still instructs the user to answer: {reply!r}"
    assert "לאישור" not in reply, f"reply still implies an approval action: {reply!r}"
    assert "לא שמרתי אותם" in reply, f"reply={reply!r}"
    assert "אישור קבוצתי עדיין לא זמין" in reply, f"reply={reply!r}"
    return "OK"


def test_pending_lead_preview_still_written():
    """pending_lead_preview must still be written — kept for audit/future design, not removed."""
    identity = MockIdentity()
    with patch("feature_flags.is_enabled", return_value=False):
        lch.handle_lead_candidate(identity, BATCH_TEXT, "chat_t2_2", "telegram")

    from session_store import lead_sessions as _ls
    session = _ls.get("chat_t2_2")
    assert session is not None, "session must exist after Tier 2 preview"
    assert session.get("pending_lead_preview") is not None, \
        "pending_lead_preview must still be written (audit/future-design), not deleted"
    assert len(session["pending_lead_preview"]["candidates"]) == 2
    return "OK"


def test_confirm_after_tier2_only_no_false_positive():
    """User with ONLY a Tier-2 preview pending (no Tier-1 contract) says 'כן' -> no false confirmation."""
    identity = MockIdentity()
    gw = _new_gw()
    with patch("feature_flags.is_enabled", return_value=False):
        preview_reply = lch.handle_lead_candidate(identity, BATCH_TEXT, "chat_t2_3", "telegram")
    assert preview_reply is not None

    with patch("core.action_gateway.action_gateway", gw):
        # Simulates app.py's confirm-word handling: ActionGateway has no live
        # contract for this user (Tier 2 never registers one), so the reply
        # must be the honest "nothing pending" message, not a fabricated success.
        confirm_reply = gw.route_confirmation_word(identity.memory_key)

    assert confirm_reply == "אין פעולה שממתינה לאישור.", f"got={confirm_reply!r}"
    return "OK"


def test_tier1_preview_message_unchanged():
    """Regression guard: Tier 1's own preview message (which DOES have a real
    resolver via ActionGateway) must still invite confirmation — this fix is
    scoped to Tier 2 only, must not touch Tier 1's wording."""
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
    test_tier2_message_is_observation_only,
    test_pending_lead_preview_still_written,
    test_confirm_after_tier2_only_no_false_positive,
    test_tier1_preview_message_unchanged,
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
