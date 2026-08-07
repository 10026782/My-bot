#!/usr/bin/env python3
"""
test_bug159_create_task_noun_form_and_verbs.py — BUG-159 (the deterministic
create_task parser only recognized the noun "משימה" and the verbs
"צור"/"תיצור" — "משימת" (construct form) and "הוסף"/"תוסיף" silently fell
through to the general Agent loop instead of the fast deterministic path).

Problem (owner, staging, 07/08/2026): "צור משימה בדיקת באג 153" (noun
"משימה") matched core/router/router.py's _STRUCTURED_CREATE_TASK_RE and got
routed deterministically (risk=NEEDS_APPROVAL, handler=TOOL,
app._queue_deterministic_create_task(), agent_calls=0). "צור משימת בדיקת
באג 155" (noun "משימת" — the construct/smichut form, equally natural
Hebrew) did NOT match at all: parse_deterministic_create_task() returned
DeterministicTaskParse() (matched=False), which is neither .certain nor
.uncertain, so router.py fell through to detect_risk()'s generic default
(risk=normal, handler=agent) — a real Claude API call, and critically,
BUG-153's trusted_source="deterministic_create_task" reconfirmation-after-
rejection carve-out never applies, since that path is never reached.
Separately, intent_router.py's detect_intent() already recognizes
"הוסף"/"תוסיף" as create_task-triggering verbs at the intent level, but
_STRUCTURED_CREATE_TASK_RE never supported them for the deterministic
parser, so even "הוסף משימה X" (correct noun form!) fell through too.

Fix: _STRUCTURED_CREATE_TASK_RE extended (owner-approved, narrow) from
r"(?:צור|תיצור)\s+משימה" to r"(?:צור|תיצור|הוסף|תוסיף)\s+משימ(?:ה|ת)" —
matches exactly the two legitimate noun forms and exactly the four verbs
already intent-recognized as create_task-triggering, nothing broader.
"""

from __future__ import annotations

import os

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-bug159-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:BUG159_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patBug159Test")
os.environ.setdefault("AIRTABLE_BASE_ID", "appBug159Test")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

from core.router import Handler, Risk, route_request  # noqa: E402
from core.router.router import parse_deterministic_create_task  # noqa: E402
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


def _owner(user_id: str) -> Identity:
    return Identity(
        user_id=user_id, role=Role.OWNER, display_name=user_id,
        tenant_id="boss_hq", domain_id="general", channel="telegram", external_id=user_id,
    )


# The owner's exact required closure-criteria phrasings, each expected to
# resolve to the same normalized title "בדיקה" or "בדיקת באג X".
_VARIANTS = [
    ("צור משימה בדיקת באג 153", "בדיקת באג 153"),
    ("צור משימת בדיקת באג 155", "בדיקת באג 155"),
    ("צור משימת בדיקה", "בדיקה"),
    ("תיצור משימת בדיקה", "בדיקה"),
    ("הוסף משימת בדיקה", "בדיקה"),
    ("תוסיף משימת בדיקה", "בדיקה"),
]


# ══════════════════════════════════════════════════════════════════
print("── 1. parse_deterministic_create_task(): every required variant "
      "parses as certain, with the correct extracted title ──")

for text, expected_title in _VARIANTS:
    parsed = parse_deterministic_create_task(text)
    chk(f"'{text}' → certain=True", parsed.certain)
    chk(f"'{text}' → title == '{expected_title}'", parsed.title == expected_title)


# ══════════════════════════════════════════════════════════════════
print("\n── 2. regression: existing 'משימה' + 'צור'/'תיצור' phrasing is "
      "completely unaffected ──")

r_old1 = parse_deterministic_create_task("צור משימה: לקנות חלב")
chk("'צור משימה: X' still parses exactly as before",
    r_old1.certain and r_old1.title == "לקנות חלב")
r_old2 = parse_deterministic_create_task("תיצור משימה לשלוח מייל ל־5/8/26")
chk("'תיצור משימה ... ל־<date>' (BUG-154 phrasing) still parses correctly",
    r_old2.certain and r_old2.due_date == "2026-08-05")


# ══════════════════════════════════════════════════════════════════
print("\n── 3. business_identity() fingerprint is equivalent across "
      "phrasings for identical content — the noun/verb never leaks into "
      "the fingerprint payload ──")

identities = [parse_deterministic_create_task(t).business_identity() for t, _ in _VARIANTS[2:]]
chk(
    "'צור משימת בדיקה' / 'תיצור משימת בדיקה' / 'הוסף משימת בדיקה' / "
    "'תוסיף משימת בדיקה' all produce the IDENTICAL business_identity() "
    "payload (same fingerprint, same dedup behavior)",
    all(i == identities[0] for i in identities),
)


# ══════════════════════════════════════════════════════════════════
print("\n── 4. route_request(): every required variant reaches the "
      "deterministic TOOL path — intent=create_task, risk=needs_approval, "
      "handler=tool, never the Agent loop ──")

_owner_identity = _owner("owner-bug159-route")
for text, _ in _VARIANTS:
    route = route_request(text, "telegram", _owner_identity)
    chk(f"'{text}' → intent == 'create_task'", route.intent == "create_task")
    chk(f"'{text}' → handler == Handler.TOOL (deterministic, not Agent)",
        route.handler == Handler.TOOL)
    chk(f"'{text}' → risk == Risk.NEEDS_APPROVAL", route.risk == Risk.NEEDS_APPROVAL)
    chk(f"'{text}' → needs_approval is True", route.needs_approval is True)


# ══════════════════════════════════════════════════════════════════
print("\n── 5. route_request(): a truly UNRELATED noun form ('משימות', "
      "plural) is correctly NOT matched — the fix is narrow, not \\w+ ──")

route_plural = route_request("צור משימות בדיקה", "telegram", _owner_identity)
chk(
    "'צור משימות בדיקה' (plural, not a supported form) does NOT reach the "
    "deterministic TOOL path — proves משימ(?:ה|ת) is narrow, not a broad "
    "\\w+/prefix match",
    route_plural.handler != Handler.TOOL,
)


# ══════════════════════════════════════════════════════════════════
print("\n── 6. end-to-end: app._queue_deterministic_create_task() is the "
      "actual caller reached for the NEW phrasings (not just proven at the "
      "router level) — same trusted_source, same code path as 'משימה' ──")

import unittest.mock as _mock  # noqa: E402

os.environ["FEATURE_ACTION_CONTRACT_PERSISTENCE"] = "false"
import app  # noqa: E402
from core.action_gateway import action_gateway as _real_gw  # noqa: E402

for text, _expected_title in [_VARIANTS[1], _VARIANTS[4]]:  # "משימת" and "הוסף משימת"
    requester = _owner(f"owner-bug159-e2e-{abs(hash(text))}")
    parsed = parse_deterministic_create_task(text)
    with _mock.patch.object(app, "bot", _mock.MagicMock()):
        app._queue_deterministic_create_task(
            parsed.title, requester.user_id, "telegram", text, requester,
            None, task_parse=parsed,
        )
    live = _real_gw.find_live_contracts(requester.memory_key)
    chk(f"'{text}': a real ActionContract was created via the "
        "deterministic path", len(live) == 1)
    if live:
        chk(f"'{text}': trusted_source is 'deterministic_create_task' — "
            "the same BUG-153 carve-out 'משימה'-phrased requests get",
            live[0].trusted_source == "deterministic_create_task")


# ══════════════════════════════════════════════════════════════════
# CodeRabbit (07/08/2026): section 6 למעלה מוכיח ש-parse_deterministic_
# create_task() + route_request() + _queue_deterministic_create_task()
# מתחברים נכון זה לזה, ע"י קריאה ישירה ל-_queue_deterministic_
# create_task() עם ארגומנטים מפורסרים מראש — הוא לא מוכיח שנקודת
# הכניסה האמיתית של הודעה נכנסת בפרודקשן (app.run_agent(), הפונקציה
# האמיתית שה-webhook handlers של טלגרם/וואטסאפ קוראים לה עם טקסט גולמי)
# מגיעה למסלול הזה עבור הניסוחים החדשים, וגם לא שאין קריאות Claude API
# בדרך. הסקשן הזה מפעיל את app.run_agent() עצמו — נקודת הכניסה האמיתית,
# נקראת עם טקסט גולמי בדיוק כמו webhook — עם ה-call site של Anthropic
# client מוחלף כך שייכשל בקול רם אם ייקרא בכלל, מוכיח את שתי הטענות
# באמת ולא רק ע"י הרכבה (composition).
print("\n── 7. true end-to-end: app.run_agent() (the real inbound-message "
      "entry point) reaches the deterministic path for the NEW phrasings "
      "— zero Anthropic calls, exactly one ActionContract created ──")

for text, expected_title in [_VARIANTS[1], _VARIANTS[4]]:  # "משימת" and "הוסף משימת"
    requester = _owner(f"owner-bug159-run-agent-{abs(hash(text))}")
    mock_bot7 = _mock.MagicMock()
    mock_anthropic_create = _mock.MagicMock(
        side_effect=AssertionError(
            "Anthropic client was called — the deterministic create_task "
            "path was bypassed for a 'certain' parse."
        )
    )
    with _mock.patch.object(app, "bot", mock_bot7), \
         _mock.patch.object(app, "resolve_identity", return_value=requester), \
         _mock.patch.object(app.client.messages, "create", mock_anthropic_create):
        app.run_agent(text, requester.user_id, channel="telegram")

    chk(f"'{text}': app.run_agent() never called the Anthropic client "
        "(agent_calls=0, proven not just logged)",
        mock_anthropic_create.call_count == 0)
    live7 = _real_gw.find_live_contracts(requester.memory_key)
    chk(f"'{text}': app.run_agent() created exactly one live ActionContract",
        len(live7) == 1)
    if live7:
        chk(f"'{text}': trusted_source is 'deterministic_create_task' via "
            "the real inbound-message entry point",
            live7[0].trusted_source == "deterministic_create_task")
        chk(f"'{text}': title parsed correctly through the full "
            "run_agent() → route_request() → _queue_deterministic_"
            "create_task() chain",
            expected_title in live7[0].normalized_payload.get("fields", {}).values())


print()
print("=" * 50)
print(f"BUG-159 (create_task noun-form + verb parser gap) tests: {passed} passed, {failed} failed")
if failed:
    raise SystemExit(1)
