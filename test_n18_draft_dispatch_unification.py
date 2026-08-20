# test_n18_draft_dispatch_unification.py — N18 Phase 2: Confirm/Cancel
# Dispatch Unification.
#
# Drives app.run_agent() end-to-end (not the unit-level lch.* calls already
# covered by test_lead_service_phase1.py section 9) against a review-mode
# Lead Draft Card, proving two things the app.py refactor must preserve:
#   1. Behavior is unchanged: "כן"/"לא" against a review-mode draft still
#      resolves through the early dispatch (write/cancel), never falling
#      through to ActionGateway's "אין פעולה שממתינה לאישור".
#   2. should_prefer_lead_draft() is now called exactly ONCE per turn —
#      previously it was called independently at the PR2 fast-path site AND
#      again at the ── 2.55 ── confirm/cancel branch (up to 2-3 self-
#      fetching Sessions reads for one turn). This is the "single decision
#      point" the confirm/cancel dispatch unification slice is about.

import os, sys
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:TEST")
os.environ.setdefault("AIRTABLE_API_KEY", "patTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")
os.environ.setdefault("ELIYAHU_CHAT_ID", "123456")

from unittest.mock import patch

import app
import core.lead_candidate_handler as lch
from identity import Identity, Role
from core.router.route_decision import RouteDecision
from context import AgentContext
from session_store import lead_sessions
from core.action_gateway import action_gateway

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


def _seed_review_draft(chat_id: str) -> None:
    lead_sessions.set_lead_draft(chat_id, {
        "name": "דנה כהן", "phone": "0501112222", "domain": "recruitment",
        "source": "", "note": "", "channel": "telegram",
        "mode": "review", "awaiting_field": None,
    })


def _run_agent_counting_prefer_draft(chat_id: str, user_text: str):
    """Drives app.run_agent() end-to-end (Identity/Router/Anthropic mocked,
    same pattern as test_session_snapshot.py) while counting real calls to
    core.lead_candidate_handler.should_prefer_lead_draft()."""
    identity = Identity(user_id=chat_id, role=Role.OWNER)
    fake_ctx = AgentContext(
        system_prompt="test", allowed_tools=[], memory_key=f"n18test:{chat_id}",
        max_tokens=500, model="claude-haiku-test", identity_label="owner",
    )
    calls = []
    real_should_prefer = lch.should_prefer_lead_draft

    def _counting(*a, **kw):
        calls.append(a)
        return real_should_prefer(*a, **kw)

    # Only the two flags that gate the PR2 fast path are on — a blanket
    # is_enabled()->True mock would also flip EMERGENCY_STOP_ALL on and
    # have create_lead() hard-block the write (the exact bug077 mocking
    # mistake this repo already hit once).
    _flags_on = {"FEATURE_DETERMINISTIC_APPROVAL_COST_CUTS", "FEATURE_ACTION_GATEWAY"}
    with patch.object(app, "resolve_identity", return_value=identity), \
         patch.object(app, "_safe_route", return_value=RouteDecision()), \
         patch.object(app, "build_context", return_value=fake_ctx), \
         patch.object(lch, "should_prefer_lead_draft", side_effect=_counting), \
         patch.object(action_gateway, "find_live_contracts", return_value=[]), \
         patch("feature_flags.is_enabled", side_effect=lambda flag: flag in _flags_on), \
         patch("tma_api._resolve_profile_record_id", return_value="recOWNER123"), \
         patch("core.lead_service.find_existing_lead", return_value=None), \
         patch("tools.airtable_gateway.airtable_create", return_value={"id": "recDANA001"}):
        reply = app.run_agent(user_text, chat_id, channel="telegram", _live_contracts_snapshot=[])

    return calls, reply


# ══════════════════════════════════════════════════
# Confirm ("כן") against a review-mode draft
# ══════════════════════════════════════════════════
chat_confirm = "n18_dispatch_confirm"
_seed_review_draft(chat_confirm)
calls_confirm, reply_confirm = _run_agent_counting_prefer_draft(chat_confirm, "כן")

chk("confirm: should_prefer_lead_draft called exactly once per turn "
    "(single decision point, not PR2 + §2.55 duplicated)",
    len(calls_confirm) == 1)
chk("confirm: 'כן' against the review-mode draft resolves to the write "
    "outcome, not ActionGateway's 'אין פעולה שממתינה לאישור'",
    isinstance(reply_confirm, str) and reply_confirm.startswith("✅"))
chk("confirm: draft cleared from the session after confirm",
    lead_sessions.get_lead_draft(chat_confirm) is None)

# ══════════════════════════════════════════════════
# Cancel ("לא") against a review-mode draft
# ══════════════════════════════════════════════════
chat_cancel = "n18_dispatch_cancel"
_seed_review_draft(chat_cancel)
calls_cancel, reply_cancel = _run_agent_counting_prefer_draft(chat_cancel, "לא")

chk("cancel: should_prefer_lead_draft called exactly once per turn",
    len(calls_cancel) == 1)
chk("cancel: 'לא' against the review-mode draft resolves to the cancel "
    "message",
    reply_cancel == "ביטלתי את יצירת הליד.")
chk("cancel: draft cleared from the session after cancel",
    lead_sessions.get_lead_draft(chat_cancel) is None)

# ══════════════════════════════════════════════════
# No draft pending — should_prefer_lead_draft still checked once (confirm
# word probe), but resolves False and normal ActionGateway handling runs.
# ══════════════════════════════════════════════════
calls_none, reply_none = _run_agent_counting_prefer_draft("n18_dispatch_no_draft", "כן")
chk("no draft pending: should_prefer_lead_draft still called exactly once "
    "(the probe itself doesn't skip the check, only its outcome differs)",
    len(calls_none) == 1)
chk("no draft pending: 'כן' falls through to ActionGateway's no-pending reply",
    reply_none == "אין פעולה שממתינה לאישור")


print("\n" + "=" * 50)
print(f"N18 draft dispatch unification tests: {passed} passed, {failed} failed")
if failed:
    sys.exit(1)
