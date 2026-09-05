# test_bug_crm_bypass_deal_optional_name_marker.py —
# BUG-CRM-BYPASS-DEAL-OPTIONAL-NAME-MARKER regression
#
# Production report (05/09/2026, owner):
#
#   "צור עסקה ניהול משרד גיוס בבורסה תחום גיוס"
#   "פתח עסקה ניהול משרד בתחום גיוס"
#
# Router already returns intent=create_deal, domain=recruitment,
# confidence=0.95 for both — but the structured parser
# (parse_deterministic_create_deal) required the literal marker "בשם"
# before the Deal name, in either field order. Neither production message
# uses "בשם" at all, so the parser's own regex never matched
# (matched=False) and the whole message CLARIFIED with a generic "not sure
# about the name or the domain" message, even though the domain was never
# in question.
#
# FIX THE EXTRACTION CONTRACT, NOT ONE REGEX VARIANT (owner directive):
# "בשם" is now optional. Once the command prefix is recognized and a
# domain clause is found anywhere in the text, the domain word is
# resolved, the prefix + optional "בשם" marker + domain clause + optional
# trailing self-ownership suffix are all stripped, and whatever text
# remains is the Deal Name — never a second per-phrasing regex. If
# nothing remains after stripping, this is a real, distinct state (domain
# confidently resolved, Deal Name genuinely missing) that must reach
# Handler.TOOL and the Commercial Completion writer's own per-field
# CLARIFY for the name specifically — never a router-level generic
# message, never Handler.AGENT, and never a repeated domain question.
#
# This file covers the exact production strings, the four "בשם"-optional
# shapes named in the fix request, the missing-name end-to-end CLARIFY,
# and confirms every existing extraction invariant
# (test_bug_crm_bypass_create_deal_deterministic_route.py) is unaffected.

import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-deal-name-marker-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:DEAL_NAME_MARKER_TEST")
os.environ.setdefault("AIRTABLE_API_KEY", "patDealNameMarkerTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appDealNameMarkerTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

import app  # noqa: E402  (env vars above must be set before import)

import emergency_stop_test_support  # noqa: E402
emergency_stop_test_support.configure_all_clear_emergency_stop()
from identity import Identity, Role  # noqa: E402
from core.router import Handler, Intent, route_request  # noqa: E402
from core.router.router import parse_deterministic_create_deal  # noqa: E402

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


def _owner(user_id: str) -> Identity:
    return Identity(
        user_id=user_id, role=Role.OWNER, display_name=user_id,
        tenant_id="boss_hq", domain_id="general", channel="telegram",
        external_id=user_id,
    )


# ══════════════════════════════════════════════════════════════════
print("── exact production strings ──")

_prod_1 = parse_deterministic_create_deal("צור עסקה ניהול משרד גיוס בבורסה תחום גיוס")
chk('production string #1 parses certain: name="ניהול משרד גיוס בבורסה", domain=recruitment',
    _prod_1.certain and _prod_1.name == "ניהול משרד גיוס בבורסה" and _prod_1.domain == "recruitment")

_prod_2 = parse_deterministic_create_deal("פתח עסקה ניהול משרד בתחום גיוס")
chk('production string #2 parses certain: name="ניהול משרד", domain=recruitment',
    _prod_2.certain and _prod_2.name == "ניהול משרד" and _prod_2.domain == "recruitment")

owner = _owner("owner-deal-name-marker")
route_1 = route_request("צור עסקה ניהול משרד גיוס בבורסה תחום גיוס", "telegram", owner)
chk("production string #1 reaches Handler.TOOL (not CLARIFY)", route_1.handler == Handler.TOOL)
chk("production string #1 -> Intent.CREATE_DEAL", route_1.intent == Intent.CREATE_DEAL)

route_2 = route_request("פתח עסקה ניהול משרד בתחום גיוס", "telegram", owner)
chk("production string #2 reaches Handler.TOOL (not CLARIFY)", route_2.handler == Handler.TOOL)


# ══════════════════════════════════════════════════════════════════
print("\n── the four 'בשם'-optional shapes named in the fix request ──")

for text, expect_name, expect_domain in (
    ("פתח עסקה בשם X בתחום גיוס", "X", "recruitment"),
    ("פתח עסקה X בתחום גיוס", "X", "recruitment"),
    ("צור עסקה X תחום גיוס", "X", "recruitment"),
    ("צור עסקה X בתחום גיוס", "X", "recruitment"),
):
    parsed = parse_deterministic_create_deal(text)
    chk(f'"{text}" -> name="{expect_name}", domain={expect_domain}',
        parsed.certain and parsed.name == expect_name and parsed.domain == expect_domain)


# ══════════════════════════════════════════════════════════════════
print("\n── genuinely missing name: domain known, name absent ──")

_missing_name = parse_deterministic_create_deal("צור עסקה בתחום יבוא")
chk("no name anywhere in the text -> domain still resolves, name is None",
    _missing_name.matched and not _missing_name.uncertain
    and _missing_name.domain_resolved and not _missing_name.certain
    and _missing_name.domain == "import" and _missing_name.name is None)

route_missing_name = route_request("צור עסקה בתחום יבוא", "telegram", owner)
chk("genuinely-missing-name text still reaches Handler.TOOL (domain is known)",
    route_missing_name.handler == Handler.TOOL)


# ══════════════════════════════════════════════════════════════════
print("\n── end-to-end: production strings never call the Agent, never re-ask domain ──")

for text, expected_name, chat_suffix in (
    ("צור עסקה ניהול משרד גיוס בבורסה תחום גיוס", "ניהול משרד גיוס בבורסה", "prod1"),
    ("פתח עסקה ניהול משרד בתחום גיוס", "ניהול משרד", "prod2"),
):
    chat_id = f"deal-name-marker-{chat_suffix}"
    e2e_owner = _owner(chat_id)
    with patch.object(app, "resolve_identity", return_value=e2e_owner), \
         patch.object(app.rate_limiter, "is_allowed", return_value=True), \
         patch.object(
             app.client.messages, "create",
             side_effect=AssertionError("structured create-deal must not call the Agent"),
         ), \
         patch(
             "feature_flags.is_enabled",
             side_effect=lambda name: name == "FEATURE_ACTION_GATEWAY",
         ):
        reply = app.run_agent(text, chat_id, "telegram")
    chk(f'"{text}" never calls the Agent and gets a real reply', bool(reply))
    chk(f'"{text}" reply never re-asks about the domain (already resolved)',
        "תחום" not in reply)

    from session_store import lead_sessions
    persisted = lead_sessions.get_commercial_completion(chat_id)
    chk(f'"{text}" persists a completion session with the extracted name already filled in',
        bool(persisted)
        and persisted["frames"][-1]["current_values"].get("name") == expected_name
        and persisted["frames"][-1]["current_values"].get("domain") == "recruitment")
    lead_sessions.clear_commercial_completion(chat_id)


# ══════════════════════════════════════════════════════════════════
print("\n── end-to-end: genuinely missing name asks for the name, and ONLY the name ──")

_missing_name_owner = _owner("deal-name-marker-missing")
with patch.object(app, "resolve_identity", return_value=_missing_name_owner), \
     patch.object(app.rate_limiter, "is_allowed", return_value=True), \
     patch.object(
         app.client.messages, "create",
         side_effect=AssertionError("structured create-deal must not call the Agent"),
     ), \
     patch(
         "feature_flags.is_enabled",
         side_effect=lambda name: name == "FEATURE_ACTION_GATEWAY",
     ):
    reply_missing_name = app.run_agent(
        "צור עסקה בתחום יבוא", _missing_name_owner.user_id, "telegram",
    )
chk('a genuinely-missing-name message gets a name-specific CLARIFY ("מה שם העסקה?")',
    reply_missing_name == "מה שם העסקה?")
chk("the missing-name CLARIFY never repeats the domain question",
    "תחום" not in reply_missing_name and "יבוא" not in reply_missing_name)

from session_store import lead_sessions  # noqa: E402
_missing_name_persisted = lead_sessions.get_commercial_completion(_missing_name_owner.user_id)
chk("the parked session already carries the resolved domain (never re-asked)",
    bool(_missing_name_persisted)
    and _missing_name_persisted["frames"][-1]["current_values"].get("domain") == "import"
    and "name" not in _missing_name_persisted["frames"][-1]["current_values"])
lead_sessions.clear_commercial_completion(_missing_name_owner.user_id)


print()
print("=" * 60)
print(f"BUG-CRM-BYPASS-DEAL-OPTIONAL-NAME-MARKER regression: {passed} passed, {failed} failed")
if failed:
    sys.exit(1)
