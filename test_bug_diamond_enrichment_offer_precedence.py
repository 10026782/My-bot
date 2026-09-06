# test_bug_diamond_enrichment_offer_precedence.py —
# BUG-DIAMOND-ENRICHMENT-OFFER-PRECEDENCE regression
#
# Production report (06/09/2026, live Telegram transcript, owner — same day
# as the enrichment-offer feature's own PR #1213):
#
#   Eli:  צור עסקה בשם ייבוא סיבים 5 בתחום יבוא
#   BOSS: עם מי העסקה? אפשרויות: איש קשר / ארגון
#         מה שם איש הקשר?
#   Eli:  אבי חזן
#   BOSS: הפעולה הושלמה: פתיחת עסקה: ייבוא סיבים 5
#         העסקה נוצרה בהצלחה. רוצה להשלים פרטים נוספים (...)? השב 'כן' או 'לא'.
#   Eli:  כן
#   BOSS: אין פעולה שממתינה לאישור
#
# Root cause: identical failure mode to BUG-DIAMOND-CREATE-CONFIRM-PRECEDENCE
# (test_bug_diamond_create_confirm_precedence.py), one level up. app.py's
# run_agent() already has a dedicated, correctly-placed check for a parked
# deal_enrichment_offer (right after the Session snapshot fetch, deliberately
# ahead of the S2C block) — but PR2's own earlier, unconditional bare-"כן"/
# "לא" fast path (_resolve_pr2_deterministic_approval, gated only on
# should_prefer_lead_draft()/_has_pending_nested_create_confirm(), neither of
# which knows about deal_enrichment_offer) runs BEFORE that check is ever
# reached. With no live ActionGateway contract to route to (a deal
# enrichment offer is deliberately its own session_store key, never an
# ActionContract), it answers the canonical "no pending approval" reply and
# the offer is silently swallowed — for both the initial כן/לא offer and any
# later cancel word mid-loop.
#
# Existing coverage (test_bug_diamond_optional_enrichment_gates_creation.py)
# never caught this because it calls app._handle_deal_enrichment_reply()
# directly, bypassing run_agent()'s outer routing entirely — that handler
# was always correct; only the routing layer in front of it was broken.
#
# Fix: _has_pending_deal_enrichment_offer() (app.py) — same
# self-fetching-Sessions-read pattern as _has_pending_nested_create_confirm()
# — added to the same _prefer_draft_now OR-chain, so PR2's fast path stands
# down while a deal enrichment offer/loop is genuinely pending and control
# reaches run_agent()'s own (already correct) deal_enrichment_offer check.

import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-diamond-enrichment-precedence-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:DIAMOND_ENRICHMENT_PRECEDENCE_TEST")
os.environ.setdefault("AIRTABLE_API_KEY", "patDiamondEnrichmentPrecedenceTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appDiamondEnrichmentPrecedenceTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import app  # noqa: E402  (env vars above must be set before import)

import emergency_stop_test_support  # noqa: E402
emergency_stop_test_support.configure_all_clear_emergency_stop()
from identity import Identity, Role  # noqa: E402

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


def _parked_offer_state() -> dict:
    return {
        "stage": "offer", "record_id": "recDeal00000001",
        "remaining_fields": list(app._DEAL_ENRICHMENT_FIELDS), "collected": {},
    }


def _parked_collecting_state() -> dict:
    return {
        "stage": "collecting", "record_id": "recDeal00000001",
        "remaining_fields": list(app._DEAL_ENRICHMENT_FIELDS), "collected": {},
    }


def _run(user_text: str, chat_id: str, *, session_payload: dict):
    identity = Identity(
        user_id=chat_id, role=Role.OWNER, display_name=chat_id,
        tenant_id="boss_hq", domain_id="general", channel="telegram",
        external_id=chat_id,
    )
    out_meta: dict = {}
    with patch.object(app, "resolve_identity", return_value=identity), \
         patch.object(app.rate_limiter, "is_allowed", return_value=True), \
         patch("session_store.lead_sessions.get", return_value=session_payload), \
         patch("session_store.lead_sessions.clear_deal_enrichment_offer") as mock_clear, \
         patch("session_store.lead_sessions.set_deal_enrichment_offer") as mock_set, \
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
print("── exact production case: 'כן' against the initial offer must not be swallowed ──")

reply_yes, meta_yes, clear_yes, set_yes, agent_yes = _run(
    "כן", "diamond-enrich-yes",
    session_payload={"deal_enrichment_offer": _parked_offer_state()},
)
check('"כן" against a pending enrichment offer is not the canonical no-pending reply',
      reply_yes != _NO_PENDING)
check('"כן" never falls back to the Agent', not agent_yes.called)
check('"כן" advances the offer into the collecting stage (set_deal_enrichment_offer called)',
      set_yes.called)
if set_yes.called:
    new_state_yes = set_yes.call_args[0][1]
    check('"כן" moves stage to "collecting"', new_state_yes.get("stage") == "collecting")
check('"כן" asks the first enrichment field, not a generic reply',
      bool(reply_yes) and reply_yes != _NO_PENDING)


# ══════════════════════════════════════════════════════════════════
print("\n── exact production case: 'לא' against the initial offer must not be swallowed ──")

reply_no, meta_no, clear_no, set_no, agent_no = _run(
    "לא", "diamond-enrich-no",
    session_payload={"deal_enrichment_offer": _parked_offer_state()},
)
check('"לא" against a pending enrichment offer is not the canonical no-pending reply',
      reply_no != _NO_PENDING)
check('"לא" never falls back to the Agent', not agent_no.called)
check('"לא" declines the offer and clears it (Deal itself untouched)', clear_no.called)


# ══════════════════════════════════════════════════════════════════
print("\n── a cancel word mid-loop (collecting stage) must not be swallowed either ──")

reply_cancel, meta_cancel, clear_cancel, set_cancel, agent_cancel = _run(
    "בטל", "diamond-enrich-cancel-mid-loop",
    session_payload={"deal_enrichment_offer": _parked_collecting_state()},
)
check('"בטל" mid-loop is not the canonical no-pending reply', reply_cancel != _NO_PENDING)
check('"בטל" mid-loop never falls back to the Agent', not agent_cancel.called)
check('"בטל" mid-loop clears the offer (Deal itself untouched)', clear_cancel.called)


# ══════════════════════════════════════════════════════════════════
print("\n── no pending enrichment offer: PR2's generic 'כן'/'לא' handling is untouched ──")

for word, expected in (("כן", _NO_PENDING), ("לא", "לא מצאתי פעולה ממתינה לביטול.")):
    reply_plain, meta_plain, clear_plain, set_plain, agent_plain = _run(
        word, f"diamond-enrich-noop-{word}", session_payload={},
    )
    check(f'"{word}" with no pending offer at all still gets PR2\'s own canonical reply '
          "(unrelated global approval semantics unaffected)",
          reply_plain == expected)
    check(f'"{word}" with no pending offer never touches deal_enrichment_offer session writes',
          not clear_plain.called and not set_plain.called)


print()
print("=" * 60)
print(f"BUG-DIAMOND-ENRICHMENT-OFFER-PRECEDENCE regression: {passed} passed, {failed} failed")
if failed:
    sys.exit(1)
