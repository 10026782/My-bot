#!/usr/bin/env python3
"""
test_bug_canonical_tool_wiring.py — regression tests for a live-incident
canonical tool-selection failure: a "create task" request created a durable
ActionContract with tool=sheets_append, provider=sheets — the user never
asked for Sheets. Approval correctly executed *that exact contract* through
Atomic Claims, so the resulting "missing Google OAuth" failure was the
expected outcome of dispatching the wrong tool, not a callback-routing or
legacy-fallback bug (both already covered by
test_bug_post_completion_callback_fallthrough.py).

Root cause: resolve_canonical_tool() (core/action_gateway.py) was written,
documented, and unit-tested in isolation (test_stage_b_full_suite.py's
DoD19 block) but was never actually called from propose_action() or from
app.py's _queue_approval() — the raw Agent tool_use loop's tool_name went
straight into the durable ActionContract unfiltered.

Fixed by wiring resolve_canonical_tool() into two places, both required:
  1. ActionGateway.propose_action() itself (core/action_gateway.py) — the
     single contract-creation entry point, protecting every current and
     future caller uniformly.
  2. app.py's _queue_approval(), at the very top, before its own dedup
     fingerprint, button label, and legacy event_bus payload are built —
     resolving only inside propose_action() would leave the legacy bus item
     and button label pointing at the original (sheets_append) hint while
     the durable contract stores the resolved one (airtable_add), which
     would reintroduce the exact fingerprint-mismatch class of bug already
     fixed for the post-completion callback fallthrough (the button falling
     through to a legacy dispatch of the wrong tool).

Does not touch ActionGateway.approve(), Atomic Claims, or callback
execution — resolution happens strictly at proposal time, before any
contract exists.
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-canon-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:CANON_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patCanonTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appCanonTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")

from unittest.mock import patch  # noqa: E402

import app  # noqa: E402
from identity import Identity, Role  # noqa: E402
from core.action_gateway import (  # noqa: E402
    ActionGateway,
    CanonicalizationError,
    ExecutionLedger,
    resolve_canonical_call,
    resolve_canonical_tool,
)
from airtable_schema import Tables, TaskFields  # noqa: E402
from event_bus import bus as _real_bus  # noqa: E402

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        print(f"✅ {desc}")
        passed += 1
    else:
        print(f"❌ {desc}")
        failed += 1


def _identity(user_id: str, role: str) -> Identity:
    return Identity(
        user_id=user_id, role=role, display_name=user_id,
        tenant_id="boss_hq", domain_id="general", channel="telegram", external_id=user_id,
    )


def _dummy_executor(*args, **kwargs):
    return {"ok": True, "tool": "airtable_add", "external_id": "recTest",
            "evidence": {"record_id": "recTest"}, "user_message": "✅ נוסף"}


# ══════════════════════════════════════════════════
# 1. resolve_canonical_tool() wired into propose_action() itself
# ══════════════════════════════════════════════════
print("── propose_action() applies resolve_canonical_tool() ──────────")

gw = ActionGateway(ledger=ExecutionLedger(), tool_executor=_dummy_executor)
identity1 = _identity("owner-canon-1", Role.OWNER)

_no_sheets_text = "לבדוק מה קורה עם אבי עד לשעה 17:00"
propose1 = gw.propose_action(
    tenant_id="boss_hq", canonical_user_id=identity1.memory_key,
    tool_name="sheets_append",
    tool_inputs={"table": "Tasks", "fields": {TaskFields.NAME: "לבדוק מה קורה עם אבי"}},
    origin_channel="telegram", origin_chat_id=identity1.user_id,
    requires_approval=True, identity=identity1, trusted_source="agent",
    user_text=_no_sheets_text,
)
contract1 = gw.find_contract(propose1.contract_id)
chk("no explicit Sheets wording: contract.tool_name overridden to airtable_add",
    contract1 is not None and contract1.tool_name == "airtable_add")
chk("no explicit Sheets wording: contract is NOT sheets_append",
    contract1 is not None and contract1.tool_name != "sheets_append")

identity2 = _identity("owner-canon-2", Role.OWNER)
_explicit_sheets_text = "תוסיף את זה לגיליון ב-Google Sheets"
propose2 = gw.propose_action(
    tenant_id="boss_hq", canonical_user_id=identity2.memory_key,
    tool_name="sheets_append",
    tool_inputs={"spreadsheet_name": "Tasks", "row_data": ["לבדוק מה קורה עם אבי"]},
    origin_channel="telegram", origin_chat_id=identity2.user_id,
    requires_approval=True, identity=identity2, trusted_source="agent",
    user_text=_explicit_sheets_text,
)
contract2 = gw.find_contract(propose2.contract_id)
chk("explicit Sheets request: contract.tool_name stays sheets_append",
    contract2 is not None and contract2.tool_name == "sheets_append")

identity3 = _identity("owner-canon-3", Role.OWNER)
propose3 = gw.propose_action(
    tenant_id="boss_hq", canonical_user_id=identity3.memory_key,
    tool_name="airtable_add",
    tool_inputs={"table": "Tasks", "fields": {"Task": "x"}},
    origin_channel="telegram", origin_chat_id=identity3.user_id,
    requires_approval=True, identity=identity3, trusted_source="agent",
    user_text="",
)
contract3 = gw.find_contract(propose3.contract_id)
chk("airtable_add hint (already canonical): passes through unchanged",
    contract3 is not None and contract3.tool_name == "airtable_add")

resolved_name, resolved_payload = resolve_canonical_call(
    "sheets_append",
    {"sheet_name": "Tasks", "row_data": ["לבדוק מה קורה עם אבי"]},
    "צור משימה לבדוק מה קורה עם אבי",
)
chk("Sheets-shaped task call: tool converts to airtable_add",
    resolved_name == "airtable_add")
chk("Sheets-shaped task call: payload converts with the tool",
    resolved_payload == {
        "table": Tables.TASKS,
        "fields": {"כותרת המשימה": "לבדוק מה קורה עם אבי"},
    })

print("\n── Fail-closed canonical payload conversion ───────────────────")

for _case_name, _tool, _payload in (
    (
        "Drive payload without explicit Drive wording",
        "drive_upload",
        {"filename": "unsafe.txt", "content": "x"},
    ),
    (
        "Sheets payload with unknown Airtable table",
        "sheets_append",
        {"spreadsheet_name": "UnknownTarget", "row_data": ["x"]},
    ),
):
    _case_gw = ActionGateway(ledger=ExecutionLedger(), tool_executor=_dummy_executor)
    _case_identity = _identity(f"owner-canon-{_tool}", Role.OWNER)
    try:
        _case_gw.propose_action(
            tenant_id="boss_hq",
            canonical_user_id=_case_identity.memory_key,
            tool_name=_tool,
            tool_inputs=_payload,
            origin_channel="telegram",
            origin_chat_id=_case_identity.user_id,
            requires_approval=True,
            identity=_case_identity,
            trusted_source="agent",
            user_text="צור משימה בלי בקשת Google מפורשת",
        )
        _case_error = None
    except CanonicalizationError as exc:
        _case_error = exc
    chk(f"{_case_name}: canonicalization fails closed",
        _case_error is not None)
    chk(f"{_case_name}: no ActionContract is created",
        len(_case_gw._ledger._store) == 0)


# ══════════════════════════════════════════════════
# 1b. Positional Tasks canonicalization — PR2 staging acceptance incident,
# 29/07/2026: a sheets_append call with a 2-element row_data (title + due
# date) hit "no explicit positional converter for Airtable table 'Tasks'"
# and killed the whole turn, twice, with no ActionContract ever created.
# ══════════════════════════════════════════════════
print("\n── Positional Tasks canonicalization (title, and title+due date) ──")

_name_only_tool, _name_only_payload = resolve_canonical_call(
    "sheets_append",
    {"table": "Tasks", "row_data": ["לבדוק מה קורה עם אבי"]},
    "צור משימה לבדוק מה קורה עם אבי",
)
chk("1-element row_data (title only) still resolves to airtable_add",
    _name_only_tool == "airtable_add")
chk("1-element row_data (title only) maps to NAME field alone",
    _name_only_payload == {
        "table": Tables.TASKS,
        "fields": {TaskFields.NAME: "לבדוק מה קורה עם אבי"},
    })

_with_due_tool, _with_due_payload = resolve_canonical_call(
    "sheets_append",
    {"table": "Tasks", "row_data": ["לחזור לכל הלידים בענף גיוס", "2026-07-29"]},
    "תייצר משימה באיירטאבל להיום לחזור לכל הלידים בענף גיוס",
)
chk("2-element row_data (title + due date) resolves to airtable_add "
    "(regression: previously raised CanonicalizationError)",
    _with_due_tool == "airtable_add")
chk("2-element row_data maps title to NAME and second value to DUE_DATE",
    _with_due_payload == {
        "table": Tables.TASKS,
        "fields": {
            TaskFields.NAME: "לחזור לכל הלידים בענף גיוס",
            TaskFields.DUE_DATE: "2026-07-29",
        },
    })

try:
    resolve_canonical_call(
        "sheets_append", {"table": "Tasks", "row_data": ["a", "b", "c"]}, "",
    )
    _three_elem_error = None
except CanonicalizationError as exc:
    _three_elem_error = exc
chk("3-element row_data still fails closed (no converter beyond 1 or 2)",
    _three_elem_error is not None)

# PR Hotfix B (CodeRabbit finding on PR #494): due date must be a real
# calendar date, not merely YYYY-MM-DD shaped — date.fromisoformat() catches
# what the format regex alone cannot (e.g. February 31st).
_valid_due_tool, _valid_due_payload = resolve_canonical_call(
    "sheets_append", {"table": "Tasks", "row_data": ["x", "2026-07-29"]}, "",
)
chk("valid YYYY-MM-DD due date resolves to airtable_add",
    _valid_due_tool == "airtable_add")
chk("valid due date is stored as its normalized ISO string",
    _valid_due_payload["fields"][TaskFields.DUE_DATE] == "2026-07-29")

for _bad_date in ("2026-02-31", "29/07/2026", "2026-13-01", "not-a-date"):
    try:
        resolve_canonical_call(
            "sheets_append", {"table": "Tasks", "row_data": ["x", _bad_date]}, "",
        )
        _bad_date_error = None
    except CanonicalizationError as exc:
        _bad_date_error = exc
    chk(f"invalid due date {_bad_date!r} fails closed", _bad_date_error is not None)


# ══════════════════════════════════════════════════
# 1c. Direct runtime regression — simple create-task request must queue through
# the canonical ActionGateway path without a Leads lookup or positional
# canonicalization failure.
# ══════════════════════════════════════════════════
print("\n── Direct runtime regression: צור משימה: X ────────────────")

_simple_task_identity = _identity("owner-canon-simple-task", Role.OWNER)
_simple_task_inputs = {"table": "Tasks", "row_data": ["X"]}

with patch.object(app, "resolve_identity", return_value=_simple_task_identity), \
     patch("feature_flags.is_enabled", side_effect=lambda name: name == "FEATURE_ACTION_GATEWAY"):
    _simple_task_outcome = app._queue_approval_detailed(
        "sheets_append",
        _simple_task_inputs,
        _simple_task_identity.user_id,
        "telegram",
        user_text="צור משימה: X",
    )

chk("simple create-task request queues successfully",
    _simple_task_outcome["ok"] is True)
chk("simple create-task request resolves to airtable_add",
    _simple_task_outcome["action_tool"] == "airtable_add")
chk("simple create-task request creates a contract this turn",
    _simple_task_outcome["created_this_turn"] is True
    and _simple_task_outcome["contract_id"] is not None)
chk("simple create-task approval reply belongs to the Gateway",
    _simple_task_outcome["reply_owner"] == "gateway")
_simple_task_contract = _real_gw.find_contract(_simple_task_outcome["contract_id"])
chk("simple create-task contract is pending and canonical",
    _simple_task_contract is not None
    and _simple_task_contract.status == "pending"
    and _simple_task_contract.tool_name == "airtable_add")
_simple_task_bus_item = _real_bus.find_pending_by_business_fingerprint(
    canonical_user_id=_simple_task_identity.memory_key,
    tool_name="airtable_add",
    normalized_inputs={
        "table": Tables.TASKS,
        "fields": {TaskFields.NAME: "X"},
    },
)
chk("simple create-task EventBus item matches the Gateway contract",
    _simple_task_bus_item is not None
    and _simple_task_bus_item.get("payload", {}).get("tool_name") == "airtable_add")


# ══════════════════════════════════════════════════
# 1c. Mutation-accounting fix — a provably contract-less canonicalization
# failure must be reported with terminal_outcome=APPROVAL_QUEUE_NEVER_
# ATTEMPTED, never counted as a "real" queue attempt, so the tool loop's
# BUG-122 same-turn-mutation guard doesn't block a legitimate differently-
# shaped retry (e.g. the model falling back to airtable_add directly) for a
# slot nothing ever actually occupied.
# ══════════════════════════════════════════════════
print("\n── Mutation accounting: canonicalization failure never queued ─────")

_never_attempted_identity = _identity("owner-canon-never-attempted", Role.OWNER)
with patch.object(app, "resolve_identity", return_value=_never_attempted_identity), \
     patch("feature_flags.is_enabled", side_effect=lambda name: name == "FEATURE_ACTION_GATEWAY"):
    _never_attempted_outcome = app._queue_approval_detailed(
        "sheets_append",
        {"table": "Tasks", "row_data": ["a", "b", "c"]},
        _never_attempted_identity.user_id, "telegram",
        user_text="צור משימה עם שלושה ערכים",
    )
chk("canonicalization failure returns ok=False",
    _never_attempted_outcome["ok"] is False)
chk("canonicalization failure returns terminal_outcome=APPROVAL_QUEUE_NEVER_ATTEMPTED",
    _never_attempted_outcome["terminal_outcome"] == "APPROVAL_QUEUE_NEVER_ATTEMPTED")
chk("canonicalization failure returns created_this_turn=False",
    _never_attempted_outcome["created_this_turn"] is False)
chk("canonicalization failure returns contract_id=None (nothing was ever attempted)",
    _never_attempted_outcome["contract_id"] is None)
chk("canonicalization failure message describes conversion, not a stuck/cleanup failure",
    "להמיר" in _never_attempted_outcome["message"])


# ══════════════════════════════════════════════════
# 2. End-to-end via app.py's _queue_approval() — the actual live incident's
# entry point (the raw Agent tool_use loop) — and consistency between the
# durable contract and the legacy event_bus item/button label.
# ══════════════════════════════════════════════════
print("\n── _queue_approval() end-to-end + bus/contract consistency ────")

from core.action_gateway import action_gateway as _real_gw  # noqa: E402

requester = _identity("owner-canon-e2e", Role.OWNER)
tool_inputs_e2e = {
    "table": Tables.TASKS,
    "fields": {TaskFields.NAME: "לבדוק מה קורה עם אבי עד 17:00"},
}

with patch.object(app, "resolve_identity", return_value=requester), \
     patch("feature_flags.is_enabled", side_effect=lambda name: name == "FEATURE_ACTION_GATEWAY"):
    reply = app._queue_approval(
        "sheets_append", tool_inputs_e2e, requester.user_id, "telegram",
        user_text="לבדוק מה קורה עם אבי עד לשעה 17:00",
    )

chk("_queue_approval reply does not reference Sheets/Google",
    "שיטס" not in reply and "Sheets" not in reply and "גיליון" not in reply)
chk("_queue_approval reply references creating a task without exposing a "
    "tool name or a raw table name",
    "משימה" in reply and "airtable_add" not in reply
    and "Tasks" not in reply and "משימות (Tasks)" not in reply)

_normalized_e2e = _real_gw.normalize_payload(tool_inputs_e2e)
_fp_airtable = _real_gw.compute_business_fingerprint(
    "boss_hq", requester.memory_key, "airtable_add", _normalized_e2e,
)
_fp_sheets = _real_gw.compute_business_fingerprint(
    "boss_hq", requester.memory_key, "sheets_append", _normalized_e2e,
)
_contract_e2e = _real_gw._ledger.find_by_fingerprint(_fp_airtable)
chk("durable contract was created under the RESOLVED tool's fingerprint (airtable_add)",
    _contract_e2e is not None)
chk("durable contract's tool_name is airtable_add, never sheets_append",
    _contract_e2e is not None and _contract_e2e.tool_name == "airtable_add")
chk("no contract exists under the ORIGINAL sheets_append fingerprint",
    _real_gw._ledger.find_by_fingerprint(_fp_sheets) is None)

_bus_item = _real_bus.find_pending_by_business_fingerprint(
    canonical_user_id=requester.memory_key,
    tool_name="airtable_add",
    normalized_inputs=tool_inputs_e2e,
)
chk("legacy event_bus item is findable under the RESOLVED tool_name (airtable_add) — "
    "same fingerprint basis the button callback will later use to locate the contract",
    _bus_item is not None)
chk("legacy event_bus item's stored payload tool_name matches the durable contract's "
    "(no bus/contract divergence -> no fingerprint-mismatch fallthrough on button press)",
    _bus_item is not None and _bus_item.get("payload", {}).get("tool_name") == "airtable_add")


# ══════════════════════════════════════════════════
# 3. Fail-closed regression: task/create-task intent without explicit Sheets
# wording may never create a sheets_append ActionContract — swept across a
# representative set of task-like phrasings with no Sheets/Drive mention.
# ══════════════════════════════════════════════════
print("\n── Fail-closed sweep: task intents never yield sheets_append ──")

_task_like_texts = [
    "צור לי משימה לסגור עם אהרן",
    "תוסיף משימה לבדוק מה קורה עם אבי עד שעה 17:00",
    "לפנות למתווך על הדירה עד לשעה 13:00",
    "",  # no text available at all (worst case — must still fail closed)
]
for _text in _task_like_texts:
    _resolved = resolve_canonical_tool("sheets_append", {"table": "Tasks"}, _text)
    chk(f"fail-closed: sheets_append hint + {_text!r} -> never sheets_append",
        _resolved != "sheets_append")
    chk(f"fail-closed: sheets_append hint + {_text!r} -> resolves to airtable_add",
        _resolved == "airtable_add")


# ══════════════════════════════════════════════════
# 4. Explicit Sheets/Drive requests keep working (must not be over-corrected)
# ══════════════════════════════════════════════════
print("\n── Explicit Sheets/Drive requests still honored ────────────────")

_explicit_sheets_texts = [
    "תוסיף את זה לשיטס", "add this to google sheets", "כתוב את זה לגיליון",
]
for _text in _explicit_sheets_texts:
    _resolved = resolve_canonical_tool("sheets_append", {"table": "Tasks"}, _text)
    chk(f"explicit request {_text!r} -> sheets_append preserved", _resolved == "sheets_append")

_explicit_drive_texts = ["העלה לדרייב", "upload to google drive"]
for _text in _explicit_drive_texts:
    _resolved = resolve_canonical_tool("drive_upload", {}, _text)
    chk(f"explicit request {_text!r} -> drive_upload preserved", _resolved == "drive_upload")


# ══════════════════════════════════════════════════
print(f"\n{'='*50}")
print(f"canonical tool wiring tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
