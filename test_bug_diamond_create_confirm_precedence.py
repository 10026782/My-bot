# test_bug_diamond_create_confirm_precedence.py —
# BUG-DIAMOND-CREATE-CONFIRM-PRECEDENCE regression
#
# Production report (05/09/2026, live Telegram transcript + Render logs,
# owner):
#
#   Eli:  פתח עסקה בשם ניהול משרד בתחום גיוס
#   BOSS: עם מי העסקה? אפשרויות: איש קשר / ארגון
#         מה שם איש הקשר?
#   Eli:  אבי חזן
#   BOSS: לא מצאתי את אבי חזן. ליצור איש קשר חדש?
#   Eli:  (taps [כן] / types "כן")
#   BOSS: אין פעולה שממתינה לאישור
#
# Root cause (confirmed against the production Render log, which shows
# `deterministic=True` on the exact turn that answered "אין פעולה שממתינה
# לאישור" — a marker only ever set by app.py's
# _resolve_pr2_deterministic_approval()): that resolver is PR2's own
# earlier, unconditional bare-"כן"/"לא" interception, gated ONLY on
# `should_prefer_lead_draft()` (a check with zero knowledge of DIAMOND
# PATH's commercial_completion CREATE_CONFIRM state). It runs BEFORE the
# S2C block ever restores the persisted commercial_completion session, so
# with no live ActionGateway contract to route to it answers the generic
# "no pending approval" reply and the pending nested-create offer is
# silently swallowed — for BOTH a typed "כן"/"לא" AND the inline button
# (webhook_telegram()'s "commercial_completion:" callback branch calls
# run_agent() with the button's own choice text, so it hits the exact same
# gate). Existing regression coverage
# (test_bug_s2c_stale_session_fresh_command_escape.py's test_4) never
# caught this because FEATURE_ACTION_GATEWAY/
# FEATURE_DETERMINISTIC_APPROVAL_COST_CUTS both default off in the test
# environment — _resolve_pr2_deterministic_approval() itself no-ops
# whenever either flag is off, so that test exercises only the (already
# correct) S2C-block-level "לא" precedence fix, never this earlier gate.
# Production has both flags on (proven by the log's own deterministic=True).
#
# Fix: _has_pending_nested_create_confirm() (app.py) — the same
# self-fetching-Sessions-read pattern should_prefer_lead_draft() already
# uses — now also makes the PR2 fast path stand down while a nested-create
# CREATE_CONFIRM is genuinely pending, so control falls through to the S2C
# block's own (already correct) handling instead.
#
# This file reproduces the exact production scenario with both flags
# enabled (the only way to reach the buggy code path at all), and confirms
# the fix does not disturb the CREATE_CONFIRM precedence invariants already
# covered (fresh command still supersedes, decline never cancels the parent
# Deal, a chat with NO pending nested-create still gets normal PR2 handling).

import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-diamond-confirm-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:DIAMOND_CONFIRM_TEST")
os.environ.setdefault("AIRTABLE_API_KEY", "patDiamondConfirmTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appDiamondConfirmTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import app  # noqa: E402  (env vars above must be set before import)

import emergency_stop_test_support  # noqa: E402
emergency_stop_test_support.configure_all_clear_emergency_stop()
from identity import Identity, Role  # noqa: E402
from airtable_schema import CommercialStatus, Currency, DealType, RelationshipType  # noqa: E402
from commercial_completion_routing import (  # noqa: E402
    CommercialCompletionRouter, deserialize_completion_session, serialize_completion_session,
)

passed = failed = 0


def check(label: str, condition: bool) -> None:
    global passed, failed
    if condition:
        print(f"✅ {label}")
        passed += 1
    else:
        print(f"❌ {label}")
        failed += 1


_PROD_FLAGS_ON = {"FEATURE_ACTION_GATEWAY", "FEATURE_DETERMINISTIC_APPROVAL_COST_CUTS"}
_NO_PENDING = "אין פעולה שממתינה לאישור"


def _deal_needing_counterparty() -> dict:
    return {
        "name": "ניהול משרד גיוס בבורסה", "domain": "recruitment", "owner": "recOwner00000001",
        "deal_type": DealType.SERVICE, "relationship_type": RelationshipType.ONE_OFF,
        "currency": Currency.ILS, "commercial_status": CommercialStatus.PROSPECT,
        "expected_value": 100,
    }


def _parked_create_confirm_state() -> dict:
    """The exact persisted shape the production transcript produces: a Deal
    parked on counterparty_contact, no match found for "אבי חזן", the
    DIAMOND PATH confirm-to-create offer pending (_ux_pending_nested_create
    marker set, still a single frame)."""
    router = CommercialCompletionRouter(queue=lambda *_: None)
    first = router.start("deal", current_values=_deal_needing_counterparty())
    assert first.outcome == "CLARIFY"
    offer = router.answer_human(
        first.session, "אבי חזן", link_lookup=lambda *_: [], scope="boss_hq:eliyahu",
    )
    assert offer.outcome == "CLARIFY"
    assert offer.choices == ("כן", "לא")
    return serialize_completion_session(offer.session)


def _run(user_text: str, chat_id: str, *, persisted_state: dict | None):
    identity = Identity(
        user_id=chat_id, role=Role.OWNER, display_name=chat_id,
        tenant_id="boss_hq", domain_id="general", channel="telegram",
        external_id=chat_id,
    )
    session_payload = (
        {"commercial_completion": persisted_state} if persisted_state is not None else {}
    )
    out_meta: dict = {}
    with patch.object(app, "resolve_identity", return_value=identity), \
         patch.object(app.rate_limiter, "is_allowed", return_value=True), \
         patch("session_store.lead_sessions.get", return_value=session_payload), \
         patch("session_store.lead_sessions.clear_commercial_completion") as mock_clear, \
         patch("session_store.lead_sessions.set_commercial_completion") as mock_set, \
         patch.object(
             app.client.messages, "create",
             side_effect=AssertionError("must not fall back to the Agent"),
         ) as mock_agent_call, \
         patch(
             "feature_flags.is_enabled",
             side_effect=lambda name: name in _PROD_FLAGS_ON,
         ):
        reply = app.run_agent(user_text, chat_id, "telegram", _out_meta=out_meta)
    return reply, out_meta, mock_clear, mock_set, mock_agent_call


# ══════════════════════════════════════════════════════════════════
print("── exact production case: 'כן' must not be swallowed ──")

reply_yes, meta_yes, clear_yes, set_yes, agent_yes = _run(
    "כן", "diamond-confirm-yes", persisted_state=_parked_create_confirm_state(),
)
check('"כן" against a pending CREATE_CONFIRM is not the canonical no-pending reply',
      reply_yes != _NO_PENDING)
check('"כן" never falls back to the Agent', not agent_yes.called)
check('"כן" re-persists an advanced session (begin_nested was called)', set_yes.called)
if set_yes.called:
    new_state_yes = set_yes.call_args[0][1]
    restored_yes = deserialize_completion_session(new_state_yes)
    check('"כן" begins a nested Contact completion (session gains a frame)',
          len(restored_yes.frames) > 1)
    check('"כן" nested frame is targeting "contact"',
          restored_yes.active.target_entity == "contact")
    check('"כן" nested frame is pre-filled with the candidate name "אבי חזן"',
          restored_yes.active.current_values.get("name") == "אבי חזן")
check('"כן" asks only the next genuinely missing Contact field (phone)',
      bool(reply_yes) and "טלפון" in reply_yes)


# ══════════════════════════════════════════════════════════════════
print("\n── exact production case: 'לא' must not be swallowed either ──")

reply_no, meta_no, clear_no, set_no, agent_no = _run(
    "לא", "diamond-confirm-no", persisted_state=_parked_create_confirm_state(),
)
check('"לא" against a pending CREATE_CONFIRM is not the canonical no-pending reply',
      reply_no != _NO_PENDING)
check('"לא" never falls back to the Agent', not agent_no.called)
check('"לא" declines only the local candidate, keeping the parent Deal alive '
      "(session re-persisted, not cleared)", set_no.called and not clear_no.called)
if set_no.called:
    new_state_no = set_no.call_args[0][1]
    restored_no = deserialize_completion_session(new_state_no)
    check('"לא" does not begin a nested Contact completion (still one frame)',
          len(restored_no.frames) == 1)
    check('"לא" clears the pending marker on the (still single) Deal frame',
          "_ux_pending_nested_create" not in (restored_no.active.current_values or {}))
check('"לא" reply asks again for the counterparty, not the entire Deal cancelled',
      bool(reply_no) and reply_no != "❌ הפעולה בוטלה. אפשר להתחיל מחדש בכל עת.")


# ══════════════════════════════════════════════════════════════════
print("\n── no pending nested-create: PR2's generic 'כן'/'לא' handling is untouched ──")

for word, expected in (("כן", _NO_PENDING), ("לא", "לא מצאתי פעולה ממתינה לביטול.")):
    reply_plain, meta_plain, clear_plain, set_plain, agent_plain = _run(
        word, f"diamond-confirm-noop-{word}", persisted_state=None,
    )
    check(f'"{word}" with no pending completion at all still gets PR2\'s own '
          "canonical reply (unrelated global approval semantics unaffected)",
          reply_plain == expected)
    check(f'"{word}" with no pending completion never touches session_store writes',
          not clear_plain.called and not set_plain.called)


# ══════════════════════════════════════════════════════════════════
print("\n── fresh command still supersedes a pending CREATE_CONFIRM ──")

reply_fresh, meta_fresh, clear_fresh, set_fresh, agent_fresh = _run(
    "צור משימה בדיקת דגימות בתחום יבוא", "diamond-confirm-fresh-command",
    persisted_state=_parked_create_confirm_state(),
)
check("a fresh deterministic command still clears the pending CREATE_CONFIRM",
      clear_fresh.called)
check("a fresh deterministic command's reply never repeats the stale confirm question",
      bool(reply_fresh) and "ליצור איש קשר חדש" not in reply_fresh)


print()
print("=" * 60)
print(f"BUG-DIAMOND-CREATE-CONFIRM-PRECEDENCE regression: {passed} passed, {failed} failed")
if failed:
    sys.exit(1)
