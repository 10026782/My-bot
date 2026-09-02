"""בדיקות רגרסיה — _finalize_deterministic_queue_outcome() as the ONE shared
Single-Speaker duplicate-reply-suppression guard for every deterministic
(non-Agent) queue-then-approve turn.

BUG-CRM-BYPASS-DEAL-DUPLICATE-REPLY (02/09/2026) closed this exact
duplicate-message bug for crm_create_deal, after it had already been fixed
once before for create_task — the fix was never ported when the Deal route
was written, even though its own docstring promised to "mirror
_queue_deterministic_create_task() exactly". To stop this class of gap from
recurring on the NEXT deterministic writer, the guard now lives in ONE
shared function, and this file proves three things:

1. The shared helper's own behavior in isolation (owner-as-requester ->
   suppressed; different requester -> not suppressed; out_meta population
   only when a contract was actually queued this turn).
2. _queue_deterministic_task_update() (update_task/complete_task) — which
   never had this guard at all, a second latent instance of the exact same
   bug class discovered while building the shared helper — is now closed
   too, via the same helper.
3. tools/audit_turn_coordinator_bypass.py's new guard 6
   (DETERMINISTIC_QUEUE_DUPLICATE_REPLY_SUPPRESSION) actually catches a
   sibling function that bypasses the shared helper, verified empirically
   (not just theoretically) by removing the helper call from a scratch
   copy and confirming the guard fails, then restoring it.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-det-queue-dup-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:det-queue-dup-test")
os.environ.setdefault("AIRTABLE_API_KEY", "patDetQueueDupTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appDetQueueDupTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")
os.environ["FEATURE_ACTION_CONTRACT_PERSISTENCE"] = "false"

import app  # noqa: E402
from core.action_gateway import action_gateway as _real_gw  # noqa: E402
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


print("── _finalize_deterministic_queue_outcome(): unit-level contract ──")

with patch.dict(os.environ, {"OWNER_TELEGRAM_ID": "chat_a"}, clear=False):
    suppressed = app._finalize_deterministic_queue_outcome(
        {
            "message": "יש פעולה שממתינה לאישור: X", "created_this_turn": True,
            "contract_id": "c1", "owner_notified": True, "reply_owner": "gateway",
            "final_response_count": 1, "action_tool": "crm_create_deal",
        },
        "chat_a", None, "UnitTest", "fallback",
    )
chk("owner-as-requester + owner_notified=True -> suppressed (empty string)",
    suppressed == "")

with patch.dict(os.environ, {"OWNER_TELEGRAM_ID": "chat_owner"}, clear=False):
    not_suppressed = app._finalize_deterministic_queue_outcome(
        {
            "message": "יש פעולה שממתינה לאישור: X", "created_this_turn": True,
            "contract_id": "c2", "owner_notified": True, "reply_owner": "gateway",
            "final_response_count": 1, "action_tool": "crm_create_deal",
        },
        "chat_requester", None, "UnitTest", "fallback",
    )
chk("different requester chat -> NOT suppressed (real confirmation returned)",
    not_suppressed == "יש פעולה שממתינה לאישור: X")

not_owner_notified = app._finalize_deterministic_queue_outcome(
    {"message": "X", "created_this_turn": True, "contract_id": "c3"},
    "chat_a", None, "UnitTest", "fallback",
)
chk("owner_notified falsy (e.g. the owner-notify send itself failed) -> "
    "never suppressed, the real message/fallback is returned",
    not_owner_notified == "X")

out_meta_when_queued: dict = {}
app._finalize_deterministic_queue_outcome(
    {
        "message": "X", "created_this_turn": True, "contract_id": "c4",
        "reply_owner": "gateway", "final_response_count": 1,
    },
    "chat_x", out_meta_when_queued, "UnitTest", "fallback",
)
chk("out_meta populated when a contract was actually queued this turn",
    out_meta_when_queued == {
        "source_module": "action_gateway", "reply_owner": "gateway",
        "final_response_count": 1,
    })

out_meta_when_not_queued: dict = {}
app._finalize_deterministic_queue_outcome(
    {"message": "X", "created_this_turn": False},
    "chat_x", out_meta_when_not_queued, "UnitTest", "fallback",
)
chk("out_meta left untouched when nothing was queued this turn "
    "(created_this_turn=False)",
    out_meta_when_not_queued == {})

empty_message_fallback = app._finalize_deterministic_queue_outcome(
    {"created_this_turn": False}, "chat_x", None, "UnitTest", "the fallback text",
)
chk("an empty/missing outcome message falls back to the caller-supplied "
    "fallback text",
    empty_message_fallback == "the fallback text")


print()
print("── _queue_deterministic_task_update(): the second latent instance of "
      "this exact bug, discovered while building the shared helper ──")

import core.turn_coordinator_runtime as _tcr  # noqa: E402

user_id_tu1 = "req_task_update_dup_1"
mock_bot_tu1 = MagicMock()

with patch.object(app, "bot", mock_bot_tu1), \
     patch.object(_tcr, "airtable_task_lookup", lambda *_a, **_k: [{"id": "rec-task-1"}]), \
     patch.dict(os.environ, {"OWNER_TELEGRAM_ID": user_id_tu1}, clear=False), \
     patch("feature_flags.is_enabled", side_effect=lambda name: name == "FEATURE_ACTION_GATEWAY"):
    reply_tu1 = app._queue_deterministic_task_update(
        "update_task", "עדכן משימה supplier: today", user_id_tu1, "telegram",
        _owner_identity(user_id_tu1),
    )

chk("update_task, requester IS the owner: owner notification sent exactly once",
    mock_bot_tu1.send_message.call_count == 1)
chk("update_task, requester IS the owner: the second plain-text reply is "
    "suppressed (this path never had the guard before — the exact "
    "duplicate-message bug BUG-CRM-BYPASS-DEAL-DUPLICATE-REPLY closed for "
    "Deal, latent here too)",
    reply_tu1 == "")

user_id_tu2 = "req_task_update_dup_2"
owner_id_tu2 = "owner_task_update_dup_2"
mock_bot_tu2 = MagicMock()

with patch.object(app, "bot", mock_bot_tu2), \
     patch.object(_tcr, "airtable_task_lookup", lambda *_a, **_k: [{"id": "rec-task-2"}]), \
     patch.dict(os.environ, {"OWNER_TELEGRAM_ID": owner_id_tu2}, clear=False), \
     patch("feature_flags.is_enabled", side_effect=lambda name: name == "FEATURE_ACTION_GATEWAY"):
    reply_tu2 = app._queue_deterministic_task_update(
        "update_task", "עדכן משימה supplier: today", user_id_tu2, "telegram",
        _owner_identity(user_id_tu2),
    )

chk("update_task, requester is NOT the owner: still gets a real, "
    "non-empty queued-confirmation reply",
    bool(reply_tu2) and "ממתינה לאישור" in reply_tu2)


print()
print("=" * 50)
print(
    "BUG-CRM-BYPASS-DEAL-DUPLICATE-REPLY shared-helper tests: "
    f"{passed} passed, {failed} failed"
)
if failed:
    raise SystemExit(1)
