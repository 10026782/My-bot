"""בדיקות רגרסיה — BUG-CRM-BYPASS-DEAL-DUPLICATE-REPLY.

Live production canary (02/09/2026, "בדיקת-קנרית 11"): the owner sent a
structured create_deal request and got TWO messages for the SAME pending
action — an interactive "⏳ בקשת אישור..." prompt with the approve/reject
keyboard, AND a separate plain-text "יש פעולה שממתינה לאישור: ..." reply.
Only the first is tracked by the approve/reject callback for editing-in-
place, so after approval the second is left behind forever, still reading
"ממתין לאישור" even though the action already completed.

This exact duplicate-message UX bug was already fixed once for Tasks
(app._queue_deterministic_create_task()'s "duplicate_reply_suppressed"
guard — see test_first_pending_notification_failure_suppression.py) but
the guard was never ported to app._queue_deterministic_create_deal() when
it was written to "mirror _queue_deterministic_create_task() exactly" —
this is a regression in that mirroring, not a new bug class. This test
proves the identical guard now exists on the Deal path too.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-deal-dup-reply-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:deal-dup-reply-test")
os.environ.setdefault("AIRTABLE_API_KEY", "patDealDupReplyTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appDealDupReplyTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")
os.environ["FEATURE_ACTION_CONTRACT_PERSISTENCE"] = "false"

import app  # noqa: E402
from core.action_gateway import action_gateway as _real_gw  # noqa: E402
from core.router.router import parse_deterministic_create_deal  # noqa: E402
from identity import Identity, Role  # noqa: E402

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


def _owner_identity(user_id: str) -> Identity:
    return Identity(
        user_id=user_id, role=Role.OWNER, display_name=user_id,
        tenant_id="boss_hq", domain_id="general", channel="telegram",
        external_id=user_id,
    )


print("── requester IS the owner: the second (plain-text) reply is suppressed ──")

user_id1 = "req_deal_dup_1"
mock_bot1 = MagicMock()  # no side_effect -- owner notification "send" succeeds

with patch.object(app, "bot", mock_bot1), \
     patch.dict(os.environ, {"OWNER_TELEGRAM_ID": user_id1}, clear=False), \
     patch("feature_flags.is_enabled", side_effect=lambda name: name == "FEATURE_ACTION_GATEWAY"):
    out_meta1: dict = {}
    reply1 = app._queue_deterministic_create_deal(
        "בדיקת-קנרית 11", "import", user_id1, "telegram",
        "צור עסקה בשם בדיקת-קנרית 11 בתחום Import",
        _owner_identity(user_id1), out_meta1,
    )

chk("the interactive owner-notification send was attempted exactly once",
    mock_bot1.send_message.call_count == 1)
chk("the second, plain-text reply is suppressed (empty string, never a "
    "duplicate 'ממתין לאישור' message)",
    reply1 == "")
chk("out_meta still records source_module=action_gateway even when the "
    "duplicate text reply is suppressed",
    out_meta1.get("source_module") == "action_gateway")

live1 = _real_gw.find_live_contracts(f"boss_hq:{user_id1}")
chk("exactly one pending crm_create_deal contract exists (the suppression "
    "only affects the reply text, never the underlying contract)",
    len(live1) == 1 and live1[0].status == "pending"
    and live1[0].tool_name == "crm_create_deal")


print()
print("── requester is NOT the owner: the queued-confirmation reply is NOT "
      "suppressed (a different person still needs to know it was queued) ──")

user_id2 = "req_deal_dup_2"
owner_id2 = "owner_deal_dup_2"
mock_bot2 = MagicMock()

with patch.object(app, "bot", mock_bot2), \
     patch.dict(os.environ, {"OWNER_TELEGRAM_ID": owner_id2}, clear=False), \
     patch("feature_flags.is_enabled", side_effect=lambda name: name == "FEATURE_ACTION_GATEWAY"):
    reply2 = app._queue_deterministic_create_deal(
        "בדיקת-קנרית 12", "import", user_id2, "telegram",
        "צור עסקה בשם בדיקת-קנרית 12 בתחום Import",
        _owner_identity(user_id2),
    )

chk("owner notification was still sent to the (different) owner chat",
    mock_bot2.send_message.call_count == 1)
chk("the requester (a different chat than the owner) still gets a real, "
    "non-empty queued-confirmation reply — never silently suppressed",
    bool(reply2) and "ממתינה לאישור" in reply2)


print()
print("── driven through the real parser -> deterministic route, matching "
      "the exact production canary text ──")

user_id3 = "req_deal_dup_3"
mock_bot3 = MagicMock()
_deal_parse3 = parse_deterministic_create_deal(
    "צור עסקה בשם בדיקת-קנרית 11 בתחום Import"
)
assert _deal_parse3.certain

with patch.object(app, "bot", mock_bot3), \
     patch.dict(os.environ, {"OWNER_TELEGRAM_ID": user_id3}, clear=False), \
     patch("feature_flags.is_enabled", side_effect=lambda name: name == "FEATURE_ACTION_GATEWAY"):
    reply3 = app._queue_deterministic_create_deal(
        _deal_parse3.name, _deal_parse3.domain, user_id3, "telegram",
        "צור עסקה בשם בדיקת-קנרית 11 בתחום Import",
        _owner_identity(user_id3),
    )

chk("real canary text, real parser output, owner-as-requester -> the "
    "duplicate plain-text reply is suppressed (reproduces the exact "
    "production incident being fixed)",
    reply3 == "")
chk("exactly one message reached Telegram for this turn (the interactive "
    "approval prompt), never two",
    mock_bot3.send_message.call_count == 1)


print()
print("=" * 50)
print(f"BUG-CRM-BYPASS-DEAL-DUPLICATE-REPLY tests: {passed} passed, {failed} failed")
if failed:
    raise SystemExit(1)
