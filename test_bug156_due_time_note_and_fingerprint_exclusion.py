#!/usr/bin/env python3
"""
test_bug156_due_time_note_and_fingerprint_exclusion.py — BUG-156
(due_time participated in the create_task business fingerprint but was
never persisted to Airtable — Option B, owner-approved 04/08/2026).

Problem (staging, 03/08/2026): the Tasks table's due-date field is Airtable
type "date", not "dateTime" — no live field ever persisted a time value.
DeterministicTaskParse.business_identity() nonetheless included due_time,
so two otherwise-identical create_task requests differing only in time
produced DIFFERENT fingerprints/contracts/approvals, even though both would
write byte-identical Airtable rows once approved.

Fix (Option B — code-only, no live Airtable schema change):
  1. business_identity() no longer includes due_time — two requests
     differing only in time now correctly collapse to the SAME fingerprint.
     due_time itself is still parsed/validated (a malformed time still
     fail-closes to clarification) — only excluded from the identity.
  2. app._queue_deterministic_create_task() builds an explicit note when
     due_time is present ("the time won't be saved") and threads it through
     _queue_approval_detailed()/_queue_approval_detailed_impl()'s new
     extra_note parameter, appended to both the owner-facing pending prompt
     and the message returned to a non-owner requester.

See docs/architecture/action-gateway/
BUG-156_DUE_TIME_FINGERPRINT_VS_PERSISTENCE_FIX_20260804.md for the full
design and Cross-Layer Impact Matrix.
"""

from __future__ import annotations

import os

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-bug156-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:BUG156_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patBug156Test")
os.environ.setdefault("AIRTABLE_BASE_ID", "appBug156Test")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")
# CodeRabbit follow-up: assignment (not setdefault) so an inherited/ambient
# value can never leave this test writing through to a real Airtable base —
# core/action_gateway.py's module-level singleton reads this flag once, at
# import time, to decide whether to wire a real ActionContractRepository.
os.environ["FEATURE_ACTION_CONTRACT_PERSISTENCE"] = "false"

from unittest.mock import MagicMock, patch

import app  # noqa: E402
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


# ══════════════════════════════════════════════════════════════════
print("── 1. business_identity() excludes due_time, keeps it parsed/validated ──")
r1 = parse_deterministic_create_task("צור משימה X עד 5/8/26 בשעה 19:00")
r2 = parse_deterministic_create_task("צור משימה X עד 5/8/26 בשעה 20:00")

chk("due_time is still parsed on the dataclass (r1)", r1.due_time == "19:00")
chk("due_time is still parsed on the dataclass (r2)", r2.due_time == "20:00")
chk("business_identity() has no due_time key", "due_time" not in r1.business_identity()["fields"])
chk(
    "two requests differing ONLY in time now produce the SAME identity "
    "(the fix — they used to differ)",
    r1.business_identity() == r2.business_identity(),
)
chk(
    "malformed time still fail-closes to uncertain (unaffected by the "
    "identity exclusion)",
    parse_deterministic_create_task("צור משימה X עד 5/8/26 בשעה 29:00").uncertain,
)


# ══════════════════════════════════════════════════════════════════
print("\n── 2. _queue_deterministic_create_task() surfaces an explicit due-time note ──")

identity = Identity(
    user_id="owner-bug156", role=Role.OWNER, display_name="owner-bug156",
    tenant_id="boss_hq", domain_id="general", channel="telegram",
    external_id="owner-bug156",
)
task_parse = parse_deterministic_create_task("צור משימה בדיקת שעה עד 5/8/26 בשעה 10:30")
assert task_parse.certain

captured_notes = []


def _fake_queue_approval_detailed(tool, payload, chat_id, channel, user_text,
                                   fingerprint_payload=None, trusted_source="agent",
                                   extra_note=None):
    captured_notes.append(extra_note)
    return {
        "message": "יש משימה שממתינה לאישור",
        "owner_notified": True,
        "created_this_turn": True,
        "contract_id": "contract-bug156",
        "reply_owner": "gateway",
        "action_tool": "airtable_add",
    }


with patch.object(app, "_queue_approval_detailed", side_effect=_fake_queue_approval_detailed), \
     patch.dict(os.environ, {"OWNER_TELEGRAM_ID": identity.user_id}, clear=False):
    app._queue_deterministic_create_task(
        task_parse.title, identity.user_id, "telegram",
        "צור משימה בדיקת שעה עד 5/8/26 בשעה 10:30", identity,
        task_parse=task_parse,
    )

chk("extra_note was passed through to _queue_approval_detailed()", len(captured_notes) == 1)
chk(
    "the note explicitly names the parsed time and says it won't be saved",
    bool(captured_notes) and captured_notes[0] is not None
    and "10:30" in captured_notes[0] and "לא תישמר" in captured_notes[0],
)


# ══════════════════════════════════════════════════════════════════
print("\n── 3. no due_time -> no note ──")
captured_notes.clear()
task_parse_no_time = parse_deterministic_create_task("צור משימה בדיקה עד 5/8/26")
assert task_parse_no_time.certain and not task_parse_no_time.due_time

with patch.object(app, "_queue_approval_detailed", side_effect=_fake_queue_approval_detailed), \
     patch.dict(os.environ, {"OWNER_TELEGRAM_ID": identity.user_id}, clear=False):
    app._queue_deterministic_create_task(
        task_parse_no_time.title, identity.user_id, "telegram",
        "צור משימה בדיקה עד 5/8/26", identity,
        task_parse=task_parse_no_time,
    )

chk("no due_time -> extra_note is None", captured_notes == [None])


# ══════════════════════════════════════════════════════════════════
# CodeRabbit follow-up: sections 2-3 above fake out _queue_approval_detailed()
# entirely, so they only prove extra_note is FORWARDED as a parameter — not
# that the real rendering code (app.py's two "_pending_text = f'{...}\n\n
# {extra_note}'" / "_final_message = f'{...}\n\n{extra_note}'" appends)
# actually puts it in front of a human. If either append broke, this file
# would stay green. This section drives the REAL (unfaked)
# _queue_approval_detailed_impl() and inspects both surfaces directly:
# the owner-facing bot.send_message() text, and the requester-facing
# returned message for a non-owner requester (whose reply isn't suppressed).
# ══════════════════════════════════════════════════════════════════
print("\n── 4. end-to-end: the due-time note actually reaches both rendered surfaces ──")

owner_identity = Identity(
    user_id="owner-bug156-e2e", role=Role.OWNER, display_name="owner-bug156-e2e",
    tenant_id="boss_hq", domain_id="general", channel="telegram",
    external_id="owner-bug156-e2e",
)
requester_identity = Identity(
    user_id="employee-bug156-e2e", role=Role.EMPLOYEE, display_name="employee-bug156-e2e",
    tenant_id="boss_hq", domain_id="general", channel="telegram",
    external_id="employee-bug156-e2e",
)
task_parse_e2e = parse_deterministic_create_task("צור משימה בדיקת רינדור עד 5/8/26 בשעה 14:45")
assert task_parse_e2e.certain and task_parse_e2e.due_time == "14:45"

mock_bot_e2e = MagicMock()


def _resolve_identity_e2e(channel, ext_id):
    return owner_identity if ext_id == owner_identity.user_id else requester_identity


with patch.object(app, "bot", mock_bot_e2e), \
     patch.object(app, "resolve_identity", side_effect=_resolve_identity_e2e), \
     patch.dict(os.environ, {"OWNER_TELEGRAM_ID": owner_identity.user_id}, clear=False), \
     patch("feature_flags.is_enabled", side_effect=lambda name: name == "FEATURE_ACTION_GATEWAY"):
    requester_message = app._queue_deterministic_create_task(
        task_parse_e2e.title, requester_identity.user_id, "telegram",
        "צור משימה בדיקת רינדור עד 5/8/26 בשעה 14:45", requester_identity,
        task_parse=task_parse_e2e,
    )

chk("end-to-end: bot.send_message() was actually called (owner prompt sent)",
    mock_bot_e2e.send_message.call_count == 1)
_owner_sent_text = mock_bot_e2e.send_message.call_args.args[1]
chk(
    "end-to-end: the REAL owner-facing pending prompt (not a fake) contains "
    "the parsed time and the 'not saved' wording",
    "14:45" in _owner_sent_text and "לא תישמר" in _owner_sent_text,
)
chk(
    "end-to-end: the REAL requester-facing returned message (non-owner "
    "requester, not suppressed) also contains the note",
    bool(requester_message) and "14:45" in requester_message and "לא תישמר" in requester_message,
)


print()
print("=" * 50)
print(f"BUG-156 (due_time fingerprint exclusion + note) tests: {passed} passed, {failed} failed")
if failed:
    raise SystemExit(1)
