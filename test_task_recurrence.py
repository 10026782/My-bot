#!/usr/bin/env python3
"""Task recurrence — existing Tasks.Cadence field on top of the Task Golden Writer.

Standalone assert-based script (repo convention: `python3 test_task_recurrence.py`).

Owner decisions (24/09/2026):
  - reuse the existing `Cadence` singleSelect (Daily/Weekly/Monthly/One-time);
    empty and legacy "One Time" read as One-time; no backfill, no option cleanup.
  - recurring completion advances the SAME record: Due Date = next occurrence,
    Status = ממתין (TaskStatus.PENDING). No occurrence rows are created.
  - Gate 1 performs the transformation before approval; Gate 2 is validation-only;
    approved == fingerprinted == executed payload.
  - recurring Tasks need a schedule anchor: Daily without a date → local today;
    Weekly/Monthly without a date → ask ONLY for the date.
  - conservative parsing: "כל יום / כל שבוע / כל חודש" only.

Sections:
  R1 parser table            R2 router deterministic create     R3 normalization/validation
  R4 next-occurrence math    R5 recurring_completion (pure)     R6 Gate 1 create (Agent)
  R7 Gate 1 update/completion (router + Agent entry)            R8 caller UX (app path)
  R9 parity: proposed == approved == fingerprinted == executed   R10 duplicate completion
  R11 Gate 2 validation-only R12 Mini App completion (PATCH /api/tasks/<id>)
"""

from __future__ import annotations

import os
import sys
import time
from datetime import date
from unittest.mock import patch

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-task-recurrence-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:TASK_RECURRENCE_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patTaskRecurrenceTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appTaskRecurrenceTs")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")
os.environ["FEATURE_ACTION_CONTRACT_PERSISTENCE"] = "false"

import app  # noqa: E402
import core.action_gateway as gateway_module  # noqa: E402
import tma_api  # noqa: E402
import tools.dispatcher as dispatcher_module  # noqa: E402
from airtable_schema import ProfileFields, Tables, TaskFields, TaskRecurrence, TaskStatus  # noqa: E402
from core import task_writer  # noqa: E402
from core.action_gateway import CanonicalizationError, action_gateway, complete_task_proposal  # noqa: E402
from core.router.router import parse_deterministic_create_task, route_request  # noqa: E402
from core.router.task_builders import build_complete_task_proposal  # noqa: E402
from core.task_writer import (  # noqa: E402
    ASK_RECURRENCE_MESSAGE, ASK_START_DATE_MESSAGE, TaskWriteRejected, next_occurrence,
    normalize_recurrence, prepare_task_create, prepare_task_update, recurrence_from_text,
    recurring_completion,
)
from core.turn_coordinator_runtime import gateway_call  # noqa: E402
from identity import Identity, Role  # noqa: E402
import inspect  # noqa: E402
import session_store  # noqa: E402
from session_store import lead_sessions  # noqa: E402

# Session store runs RAM-only here (no Airtable I/O). Sources captured first so
# R13 can check the persistence whitelists of the real methods.
_SYNC_SRC = inspect.getsource(session_store.PersistentSessionStore._sync_to_db)
_LOAD_SRC = inspect.getsource(session_store.PersistentSessionStore._load_from_db)
for _p in (patch.object(session_store.PersistentSessionStore, "_sync_to_db", lambda self, *a, **k: True),
           patch.object(session_store.PersistentSessionStore, "_load_from_db", lambda self, *a, **k: None),
           patch.object(session_store.PersistentSessionStore, "_delete_from_db", lambda self, *a, **k: None)):
    _p.start()

passed = 0
failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        passed += 1
        print(f"✅ {desc}")
    else:
        failed += 1
        print(f"❌ {desc}")


def rejected(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except TaskWriteRejected as exc:
        return exc
    return None


TODAY = date(2026, 9, 24)            # Thursday
REC = "recRECURRINGAAAAA"
DAILY, WEEKLY, MONTHLY, ONE_TIME = (TaskRecurrence.DAILY, TaskRecurrence.WEEKLY,
                                    TaskRecurrence.MONTHLY, TaskRecurrence.ONE_TIME)
DONE, PENDING = TaskStatus.DONE, TaskStatus.PENDING
S, DUE, CAD, NAME = TaskFields.STATUS, TaskFields.DUE_DATE, TaskFields.RECURRENCE, TaskFields.NAME

owner = Identity(
    user_id="owner-recurrence", role=Role.OWNER, display_name="owner-recurrence",
    tenant_id="boss_hq", domain_id="general", channel="telegram", external_id="owner-recurrence",
)


def _today():
    return patch.object(task_writer, "local_today", lambda: TODAY)


def _record(**fields):
    base = {NAME: "לשלוח דוח", S: PENDING}
    base.update(fields)
    return base


def gate1(tool, inputs, *, user_text="", trusted_source="agent", record=None, read_error=None):
    """complete_task_proposal with the Task-record read faked."""
    def _fetch(record_id):
        _fetch.calls.append(record_id)
        if read_error is not None:
            raise task_writer.TaskWriteRejected("task_unverifiable", "x", task_writer.TASK_UNVERIFIABLE_MESSAGE, ())
        return record
    _fetch.calls = []
    with _today(), patch.object(gateway_module, "_fetch_task_record", _fetch), \
         patch.object(gateway_module, "_fetch_task_link_record", lambda t, r: None):
        try:
            return complete_task_proposal(tool, inputs, trusted_source=trusted_source,
                                          identity=owner, user_text=user_text), _fetch
        except CanonicalizationError as exc:
            return exc, _fetch


def complete(fields_record, **kw):
    inputs = {"table": Tables.TASKS, "record_id": REC, "fields": {S: DONE}}
    out, fetch = gate1("airtable_update", inputs, record=fields_record, **kw)
    return out, inputs, fetch


# ══════════════════════════════════════════════════
print("\n[R1] conservative recurrence parser")
# ══════════════════════════════════════════════════

for text, expected in (
    ("כל יום לבדוק מיילים", DAILY), ("לבדוק מיילים כל יום", DAILY),
    ("כל שבוע לשלוח דוח", WEEKLY), ("בכל שבוע לשלוח דוח", WEEKLY), ("ובכל חודש לשלם ארנונה", MONTHLY),
    ("כל חודש לשלם ארנונה", MONTHLY), ("כל יום, שני דוחות", DAILY), ("כל יום כל יום", DAILY),
    ("כל יום שניים דוחות", DAILY),
):
    r = recurrence_from_text(text)
    chk(f"{text!r} → {expected}", r.value == expected and not r.uncertain)

for text in ("כל היום בפגישות", "כל השבוע בחופש", "כל החודש עמוס", "לבדוק מיילים", "שכל יום", "", None):
    r = recurrence_from_text(text)
    chk(f"{text!r} → no recurrence (not a frequency)", r.value is None and not r.uncertain)

for text in ("כל יום שני ישיבת צוות", "כל יום ב' ישיבה", "כל יום שבת", "כל יומיים", "כל שבועיים",
             "כל חודשיים", "כל 3 ימים", "כל שנה", "לא כל יום", "כל יום וכל שבוע", "כל כמה ימים"):
    r = recurrence_from_text(text)
    chk(f"{text!r} → ambiguous/unsupported, never guessed", r.uncertain and r.value is None)

# ══════════════════════════════════════════════════
print("\n[R2] router deterministic create")
# ══════════════════════════════════════════════════

p = parse_deterministic_create_task("צור משימה: כל יום לבדוק מיילים")
chk("Daily parsed; title kept verbatim (no semantic rewrite)",
    p.certain and p.recurrence == DAILY and p.title == "כל יום לבדוק מיילים" and p.due_date is None)
p = parse_deterministic_create_task("צור משימה: כל שבוע לשלוח דוח עד 1/10/26")
chk("Weekly + explicit date → anchor = that date",
    p.certain and p.recurrence == WEEKLY and p.due_date == "2026-10-01" and p.title == "כל שבוע לשלוח דוח")
chk("business_identity (fingerprint basis) carries Cadence, exactly like the write payload",
    p.business_identity() == {"table": Tables.TASKS, "fields": {NAME: "כל שבוע לשלוח דוח", DUE: "2026-10-01", CAD: WEEKLY}})
p = parse_deterministic_create_task("צור משימה: לבדוק מיילים")
chk("no phrase → no Cadence key anywhere (One-time = absence)",
    p.certain and p.recurrence is None and CAD not in p.business_identity()["fields"])
p = parse_deterministic_create_task("צור משימה: כל יום שני ישיבת צוות")
chk("ambiguous phrase → uncertain (never Daily)", p.uncertain and p.recurrence_uncertain and p.recurrence is None)
route = route_request("צור משימה: כל יום שני ישיבת צוות", "telegram", owner)
chk("router clarification asks ONLY about the frequency",
    getattr(route, "response_override", "") == ASK_RECURRENCE_MESSAGE)
route = route_request("צור משימה: כל שבוע לשלוח דוח עד 1/10/26", "telegram", owner)
chk("certain recurring create still routes to the deterministic TOOL path",
    str(getattr(route, "handler", "")).lower().endswith("tool") and route.intent == "create_task")

# ══════════════════════════════════════════════════
print("\n[R3] normalization / validation (Golden Writer)")
# ══════════════════════════════════════════════════

for value, expected in ((None, ONE_TIME), ("", ONE_TIME), ("  ", ONE_TIME), ("One-time", ONE_TIME),
                        ("One Time", ONE_TIME), ("daily", DAILY), ("Weekly", WEEKLY), (" monthly ", MONTHLY),
                        ("Biweekly", None), ("כל יום", None), (3, None)):
    chk(f"normalize_recurrence({value!r}) → {expected!r}", normalize_recurrence(value) == expected)

chk("create without Cadence → untouched (no default written)",
    prepare_task_create({NAME: "x"}) == {NAME: "x"})
chk("legacy 'One Time' normalized to 'One-time'",
    prepare_task_create({NAME: "x", CAD: "One Time"}) == {NAME: "x", CAD: ONE_TIME})
chk("empty Cadence removed (absence = One-time)", prepare_task_create({NAME: "x", CAD: ""}) == {NAME: "x"})
exc = rejected(prepare_task_create, {NAME: "x", CAD: "Biweekly"})
chk("unknown Cadence rejected (never creates a new select option)", exc is not None and exc.code == "recurrence_invalid")
for cadence in (DAILY, WEEKLY, MONTHLY):
    exc = rejected(prepare_task_create, {NAME: "x", CAD: cadence})
    chk(f"{cadence} create without a due date rejected, asking ONLY for the date",
        exc is not None and exc.code == "recurrence_anchor_missing" and exc.missing == (DUE,)
        and exc.user_message == ASK_START_DATE_MESSAGE)
chk("recurring create with a date is valid",
    prepare_task_create({NAME: "x", CAD: WEEKLY, DUE: "2026-10-01"}) == {NAME: "x", CAD: WEEKLY, DUE: "2026-10-01"})
chk("One-time keeps Due Date optional", prepare_task_create({NAME: "x", CAD: ONE_TIME}) == {NAME: "x", CAD: ONE_TIME})
chk("update: Cadence validated/normalized only",
    prepare_task_update({CAD: "weekly"}) == {CAD: WEEKLY}
    and rejected(prepare_task_update, {CAD: "Yearly"}).code == "recurrence_invalid")

# ══════════════════════════════════════════════════
print("\n[R4] next-occurrence math")
# ══════════════════════════════════════════════════

for cadence, anchor, today, expected, label in (
    (DAILY, date(2026, 9, 24), TODAY, date(2026, 9, 25), "daily due today → tomorrow"),
    (DAILY, date(2026, 9, 19), TODAY, date(2026, 9, 25), "daily overdue 5 days → tomorrow (not still overdue)"),
    (DAILY, date(2026, 9, 25), TODAY, date(2026, 9, 26), "daily completed early → the occurrence after"),
    (WEEKLY, date(2026, 9, 24), TODAY, date(2026, 10, 1), "weekly due today → +7"),
    (WEEKLY, date(2026, 7, 30), TODAY, date(2026, 10, 1), "weekly overdue → next same weekday after today"),
    (WEEKLY, date(2026, 10, 1), TODAY, date(2026, 10, 8), "weekly completed early → +7 from anchor"),
    (MONTHLY, date(2026, 9, 24), TODAY, date(2026, 10, 24), "monthly due today → +1 month"),
    (MONTHLY, date(2026, 5, 10), TODAY, date(2026, 10, 10), "monthly overdue → next month-day after today"),
    (MONTHLY, date(2026, 5, 30), TODAY, date(2026, 9, 30), "monthly overdue, day still ahead this month"),
    (MONTHLY, date(2026, 10, 5), TODAY, date(2026, 11, 5), "monthly completed early → +1 month"),
    (MONTHLY, date(2026, 1, 31), date(2026, 1, 31), date(2026, 2, 28), "31st → end of February"),
    (MONTHLY, date(2028, 1, 31), date(2028, 1, 31), date(2028, 2, 29), "31st → leap-year Feb 29"),
    (MONTHLY, date(2026, 12, 15), date(2026, 12, 15), date(2027, 1, 15), "December → January next year"),
):
    got = next_occurrence(cadence, anchor, today)
    chk(f"{label}: {anchor} → {expected}", got == expected and got > today)
try:
    next_occurrence(ONE_TIME, TODAY, TODAY)
    chk("One-time has no next occurrence", False)
except ValueError:
    chk("One-time has no next occurrence", True)

# ══════════════════════════════════════════════════
print("\n[R5] recurring_completion (pure)")
# ══════════════════════════════════════════════════

upd = {S: DONE}
for label, record in (("One-time", _record(**{CAD: ONE_TIME, DUE: "2026-09-24"})),
                      ("empty Cadence", _record(**{DUE: "2026-09-24"})),
                      ("legacy One Time", _record(**{CAD: "One Time", DUE: "2026-09-24"}))):
    chk(f"{label} → normal Done (same object, unchanged)", recurring_completion(upd, record, today=TODAY) is upd)
chk("recurring Task already Done → no second advance",
    recurring_completion(upd, _record(**{CAD: WEEKLY, DUE: "2026-09-24", S: DONE}), today=TODAY) is upd)
chk("non-completion update → untouched",
    recurring_completion({NAME: "y"}, _record(**{CAD: DAILY}), today=TODAY) == {NAME: "y"})
out = recurring_completion(upd, _record(**{CAD: WEEKLY, DUE: "2026-09-24"}), today=TODAY)
chk("Weekly Done → same record, Due advanced, Status back to the existing pending value 'ממתין'",
    out == {S: PENDING, DUE: "2026-10-01"} and PENDING == "ממתין")
chk("Status never takes a recurrence value", out[S] in (PENDING,))
out = recurring_completion(upd, _record(**{CAD: DAILY}), today=TODAY)
chk("Daily without a date → anchored to local today → tomorrow", out == {S: PENDING, DUE: "2026-09-25"})
for cadence in (WEEKLY, MONTHLY):
    exc = rejected(recurring_completion, upd, _record(**{CAD: cadence}), today=TODAY)
    chk(f"{cadence} without a date → asks ONLY for the date (no invented weekday/month-day)",
        exc is not None and exc.code == "recurrence_anchor_missing" and exc.missing == (DUE,))
chk("same update also switching to One-time → plain Done (stop a series)",
    recurring_completion({S: DONE, CAD: ONE_TIME}, _record(**{CAD: WEEKLY, DUE: "2026-09-24"}), today=TODAY)
    == {S: DONE, CAD: ONE_TIME})

# ══════════════════════════════════════════════════
print("\n[R6] Gate 1 create — Agent path")
# ══════════════════════════════════════════════════


def create(fields, text="", source="agent"):
    return gate1("airtable_add", {"table": Tables.TASKS, "fields": fields}, user_text=text, trusted_source=source)[0]


out = create({NAME: "לבדוק מיילים"}, "תזכיר לי כל שבוע לבדוק מיילים, מתחיל ב-1/10")
chk("Weekly derived from the user's own text, but no date → asks ONLY for the start date",
    isinstance(out, CanonicalizationError) and out.user_message == ASK_START_DATE_MESSAGE and out.missing == (DUE,))
out = create({NAME: "לבדוק מיילים", DUE: "2026-10-01"}, "תזכיר לי כל שבוע לבדוק מיילים")
chk("model omitted Cadence, user said 'כל שבוע' → Weekly filled (Diamond)", out["fields"].get(CAD) == WEEKLY)
out = create({NAME: "לבדוק מיילים", CAD: DAILY, DUE: "2026-10-01"}, "תזכיר לי כל שבוע לבדוק מיילים")
chk("model's conflicting recurring value → the user's text wins", out["fields"].get(CAD) == WEEKLY)
out = create({NAME: "לבדוק מיילים"}, "כל יום לבדוק מיילים")
chk("Daily without a date → Due Date = local today (deterministic anchor)",
    out["fields"] == {NAME: "לבדוק מיילים", CAD: DAILY, DUE: "2026-09-24"})
out = create({NAME: "ישיבת צוות"}, "תקבע משימה כל יום שני ישיבת צוות")
chk("ambiguous text → asks ONLY about the frequency, nothing proposed",
    isinstance(out, CanonicalizationError) and out.user_message == ASK_RECURRENCE_MESSAGE and out.missing == (CAD,))
inputs = {"table": Tables.TASKS, "fields": {NAME: "לקנות חלב"}}
out, _ = gate1("airtable_add", inputs, user_text="צור משימה לקנות חלב")
chk("plain one-time create → unchanged (same object; no Cadence, no Due invented)", out is inputs)
out = create({NAME: "x", CAD: "Biweekly", DUE: "2026-10-01"}, "")
chk("unknown model value → rejected, never written as a new option",
    isinstance(out, CanonicalizationError) and out.code == "recurrence_invalid")
out = create({NAME: "x", CAD: "One Time"}, "")
chk("legacy alias normalized at Gate 1 (so Gate 2 is idempotent)", out["fields"] == {NAME: "x", CAD: ONE_TIME})
out = create({NAME: "x"}, "כל יום x", source="interaction_engine_scheduler")
chk("trusted internal sources: no text derivation (payload unchanged)",
    out == {"table": Tables.TASKS, "fields": {NAME: "x"}})

# ══════════════════════════════════════════════════
print("\n[R7] Gate 1 update / completion")
# ══════════════════════════════════════════════════

out, inputs, fetch = complete(_record(**{CAD: WEEKLY, DUE: "2026-09-24"}))
chk("recurring completion transformed at Gate 1 → advance the same record",
    out == {"table": Tables.TASKS, "record_id": REC, "fields": {S: PENDING, DUE: "2026-10-01"}}
    and fetch.calls == [REC] and inputs["fields"] == {S: DONE})
out, inputs, _ = complete(_record(**{CAD: ONE_TIME, DUE: "2026-09-24"}))
chk("One-time completion → same object (fingerprint_payload kept)", out is inputs)
out, inputs, _ = complete(_record(**{DUE: "2026-09-24"}))
chk("empty Cadence completion → same object", out is inputs)
out, inputs, _ = complete(None)
chk("record not found (404) → unchanged; the write fails as before", out is inputs)
out, _, _ = complete(None, read_error=True)
chk("record unreadable → fail CLOSED (never guess: no silent Done, no invented date)",
    isinstance(out, CanonicalizationError) and out.code == "task_unverifiable")
out, _, _ = complete(_record(**{CAD: MONTHLY}))
chk("Monthly without a date → asks ONLY for the date",
    isinstance(out, CanonicalizationError) and out.user_message == ASK_START_DATE_MESSAGE)
inputs = {"table": Tables.TASKS, "record_id": REC, "fields": {NAME: "חדש"}}
out, fetch = gate1("airtable_update", inputs, record=_record())
chk("update that neither completes nor sets recurrence → no read, same object", out is inputs and fetch.calls == [])
out, _ = gate1("airtable_update", {"table": Tables.TASKS, "record_id": REC, "fields": {CAD: WEEKLY}}, record=_record())
chk("making an undated Task Weekly → asks ONLY for the date",
    isinstance(out, CanonicalizationError) and out.missing == (DUE,))
out, _ = gate1("airtable_update", {"table": Tables.TASKS, "record_id": REC, "fields": {CAD: DAILY}}, record=_record())
chk("making an undated Task Daily → anchored to local today", out["fields"] == {CAD: DAILY, DUE: "2026-09-24"})
inputs = {"table": Tables.TASKS, "record_id": REC, "fields": {CAD: WEEKLY}}
out, _ = gate1("airtable_update", inputs, record=_record(**{DUE: "2026-10-01"}))
chk("making a dated Task Weekly → unchanged (its Due Date is the anchor)", out is inputs)
tool, payload = gateway_call(build_complete_task_proposal(REC))
out, _ = gate1(tool, payload, record=_record(**{CAD: DAILY, DUE: "2026-09-24"}),
               trusted_source="deterministic_create_task")
chk("router COMPLETE_TASK payload (build_complete_task_proposal → gateway_call) advances too",
    out["fields"] == {S: PENDING, DUE: "2026-09-25"})

# ══════════════════════════════════════════════════
print("\n[R8] caller UX — app._queue_approval_detailed (router + Agent entry)")
# ══════════════════════════════════════════════════

with _today(), patch.object(gateway_module, "_fetch_task_record", lambda rid: _record(**{CAD: WEEKLY, DUE: "2026-09-24"})), \
     patch.object(action_gateway, "propose_action", side_effect=RuntimeError("captured")) as spy:
    app._queue_approval_detailed(
        "airtable_update", {"table": Tables.TASKS, "record_id": REC, "fields": {S: DONE}},
        "chat-rec-1", "telegram", "סמן את המשימה לשלוח דוח כבוצעה",
        fingerprint_payload={"table": Tables.TASKS, "record_id": REC, "fields": {S: DONE}},
    )
kwargs = spy.call_args.kwargs if spy.call_args else {}
chk("the approval proposal carries the advanced payload",
    kwargs.get("tool_inputs", {}).get("fields") == {S: PENDING, DUE: "2026-10-01"})
chk("…and the stale 'Done' fingerprint_payload is dropped", kwargs.get("fingerprint_payload") is None)
chk("…and the approval label shows exactly what will be written",
    "2026-10-01" in app._describe_tool_call("airtable_update", kwargs.get("tool_inputs", {})))

with _today(), patch.object(gateway_module, "_fetch_task_record", lambda rid: _record(**{CAD: MONTHLY})), \
     patch.object(action_gateway, "propose_action", side_effect=AssertionError("must not propose")) as spy:
    result = app._queue_approval_detailed(
        "airtable_update", {"table": Tables.TASKS, "record_id": REC, "fields": {S: DONE}},
        "chat-rec-2", "telegram", "סמן כבוצע",
    )
chk("undated Monthly completion → NEVER_ATTEMPTED + date question only",
    result.get("ok") is False and result.get("terminal_outcome") == "APPROVAL_QUEUE_NEVER_ATTEMPTED"
    and result.get("message") == ASK_START_DATE_MESSAGE and spy.call_count == 0)

with _today(), patch.object(action_gateway, "propose_action", side_effect=AssertionError("must not propose")) as spy:
    result = app._queue_approval_detailed(
        "airtable_add", {"table": Tables.TASKS, "fields": {NAME: "כל שבוע לשלוח דוח", CAD: WEEKLY}},
        "chat-rec-3", "telegram", "צור משימה: כל שבוע לשלוח דוח",
        fingerprint_payload={"table": Tables.TASKS, "fields": {NAME: "כל שבוע לשלוח דוח", CAD: WEEKLY}},
        trusted_source="deterministic_create_task",
    )
chk("router create 'כל שבוע …' without a date → asks ONLY for the start date",
    result.get("terminal_outcome") == "APPROVAL_QUEUE_NEVER_ATTEMPTED" and result.get("message") == ASK_START_DATE_MESSAGE)

# ══════════════════════════════════════════════════
print("\n[R9] proposed == approved == fingerprinted == executed")
# ══════════════════════════════════════════════════

from tools.dispatcher import _validate_execution_proof  # noqa: E402

_ok = {"ok": True, "tool": "airtable_update", "external_id": REC, "evidence": {"record_id": REC}, "user_message": "ok"}


def _ctx(contract) -> dict:
    return {
        "contract_id": contract.contract_id, "approved_by": contract.canonical_user_id,
        "tool_name": contract.tool_name, "tenant_id": contract.tenant_id,
        "canonical_user_id": contract.canonical_user_id,
        "business_action_fingerprint": contract.business_action_fingerprint, "status": "approved",
    }


def _ident(user_id):
    return Identity(user_id=user_id, role=Role.OWNER, display_name=user_id, tenant_id="boss_hq",
                    domain_id="general", channel="telegram", external_id=user_id)


def _propose(ident, tool, inputs, record=None, user_text=""):
    with _today(), patch.object(gateway_module, "_fetch_task_record", lambda rid: record), \
         patch.object(gateway_module, "_fetch_task_link_record", lambda t, r: None):
        return action_gateway.propose_action(
            tenant_id="boss_hq", canonical_user_id=ident.memory_key, tool_name=tool,
            tool_inputs=inputs, origin_channel="telegram", origin_chat_id=ident.user_id,
            requires_approval=True, identity=ident, trusted_source="agent", user_text=user_text,
            fingerprint_payload=dict(inputs),
        )


def _execute(ident, tool, contract, writer):
    with patch.object(dispatcher_module, writer, return_value={**_ok, "tool": tool}) as write, \
         patch.object(dispatcher_module, "_check_duplicate", return_value=None), \
         patch.object(dispatcher_module._ff, "is_enabled", return_value=False):
        result = dispatcher_module.dispatch_tool(
            tool, contract.normalized_payload, identity=ident, trusted_source="agent", execution_context=_ctx(contract),
        )
    return result, write


ident = _ident("u-rec-parity-complete")
res = _propose(ident, "airtable_update", {"table": Tables.TASKS, "record_id": REC, "fields": {S: DONE}},
               record=_record(**{CAD: WEEKLY, DUE: "2026-09-24"}))
contract = action_gateway.find_contract(res.contract_id) if res.ok else None
stored = contract.normalized_payload if contract else {}
chk("P1 completion: the contract stores the ADVANCED payload (what the owner approves)",
    stored.get("fields") == {S: PENDING, DUE: "2026-10-01"} and stored.get("record_id") == REC)
chk("P2 completion: stored fingerprint == the dispatcher's recomputation from the stored payload",
    contract is not None and _validate_execution_proof("airtable_update", stored, ident, _ctx(contract), "agent") is None)
result, write = _execute(ident, "airtable_update", contract, "airtable_update")
chk("P3 completion: real execution proof passes; Airtable receives exactly the approved fields on the SAME record",
    result.get("ok") is True and write.call_count == 1
    and write.call_args.args[1:] == (REC, {S: PENDING, DUE: "2026-10-01"}))

ident = _ident("u-rec-parity-create")
res = _propose(ident, "airtable_add", {"table": Tables.TASKS, "fields": {NAME: "לבדוק מיילים"}},
               user_text="כל יום לבדוק מיילים")
contract = action_gateway.find_contract(res.contract_id) if res.ok else None
stored = contract.normalized_payload if contract else {}
chk("P4 Daily create: the contract stores Cadence + the derived anchor",
    stored.get("fields") == {NAME: "לבדוק מיילים", CAD: DAILY, DUE: "2026-09-24"})
result, write = _execute(ident, "airtable_add", contract, "airtable_add")
chk("P5 Daily create: proof passes; Airtable receives exactly the approved fields",
    contract is not None and result.get("ok") is True and write.call_count == 1
    and write.call_args.args[1] == stored["fields"])

# ══════════════════════════════════════════════════
print("\n[R10] duplicate completion")
# ══════════════════════════════════════════════════

ident = _ident("u-rec-dup")
state = _record(**{CAD: WEEKLY, DUE: "2026-09-24"})
first = _propose(ident, "airtable_update", {"table": Tables.TASKS, "record_id": REC, "fields": {S: DONE}}, record=state)
second = _propose(ident, "airtable_update", {"table": Tables.TASKS, "record_id": REC, "fields": {S: DONE}}, record=state)
chk("two completions from the same record state → one contract; the second is caught as a duplicate",
    first.ok and not second.ok and second.contract_id == first.contract_id)
advanced = _record(**{CAD: WEEKLY, DUE: "2026-10-01"})
# (separate requester only because the existing one-pending-action guard would
# otherwise block the proposal while the first contract is still pending)
third = _propose(_ident("u-rec-dup-next"), "airtable_update",
                 {"table": Tables.TASKS, "record_id": REC, "fields": {S: DONE}}, record=advanced)
first_contract = action_gateway.find_contract(first.contract_id)
third_contract = action_gateway.find_contract(third.contract_id) if third.ok else None
chk("completing the NEXT occurrence is a different action (Due advances again, different fingerprint)",
    third_contract is not None and third_contract.normalized_payload["fields"] == {S: PENDING, DUE: "2026-10-08"}
    and third_contract.business_action_fingerprint != first_contract.business_action_fingerprint)

# ══════════════════════════════════════════════════
print("\n[R11] Gate 2 is validation-only (no recurrence transformation after approval)")
# ══════════════════════════════════════════════════


def _dispatch(name, inputs):
    with patch.object(dispatcher_module, "_validate_execution_proof", return_value=None), \
         patch.object(dispatcher_module._ff, "is_enabled", return_value=False):
        return dispatcher_module.dispatch_tool(name, inputs, identity=owner, trusted_source="agent",
                                               execution_context={"contract_id": "c-rec"})


_forbidden = AssertionError("Gate 2 must not transform recurrence")
with patch.object(task_writer, "recurring_completion", side_effect=_forbidden), \
     patch.object(task_writer, "fill_recurrence_anchor", side_effect=_forbidden), \
     patch.object(task_writer, "recurrence_from_text", side_effect=_forbidden), \
     patch.object(task_writer, "local_today", side_effect=_forbidden), \
     patch.object(gateway_module, "_fetch_task_record", side_effect=_forbidden), \
     patch.object(dispatcher_module, "airtable_update", return_value=_ok) as upd, \
     patch.object(dispatcher_module, "airtable_add", return_value={**_ok, "tool": "airtable_add"}) as add, \
     patch.object(dispatcher_module, "_check_duplicate", return_value=None):
    done = _dispatch("airtable_update", {"table": Tables.TASKS, "record_id": REC, "fields": {S: DONE}})
    no_anchor = _dispatch("airtable_add", {"table": Tables.TASKS, "fields": {NAME: "x", CAD: DAILY}})
    bad = _dispatch("airtable_add", {"table": Tables.TASKS, "fields": {NAME: "x", CAD: "Yearly", DUE: "2026-10-01"}})
    good = _dispatch("airtable_add", {"table": Tables.TASKS, "fields": {NAME: "x", CAD: WEEKLY, DUE: "2026-10-01"}})
    set_cad = _dispatch("airtable_update", {"table": Tables.TASKS, "record_id": REC, "fields": {CAD: MONTHLY}})
chk("G1 approved 'Done' written exactly as approved (no read, no advance at persistence)",
    done.get("ok") is True and upd.call_args_list[0].args[2] == {S: DONE})
chk("G2 recurring create without a date → rejected (no anchor filled after approval)",
    no_anchor.get("ok") is False and no_anchor.get("user_message") == ASK_START_DATE_MESSAGE)
chk("G3 unknown Cadence → rejected", bad.get("ok") is False)
chk("G4 valid recurring create written with the same fields",
    good.get("ok") is True and add.call_count == 1
    and add.call_args.args[1] == {NAME: "x", CAD: WEEKLY, DUE: "2026-10-01"})
chk("G5 Cadence is an allowed Task update field", set_cad.get("ok") is True and upd.call_args_list[-1].args[2] == {CAD: MONTHLY})

# ══════════════════════════════════════════════════
print("\n[R12] Mini App completion — PATCH /api/tasks/<id> (backend only, UX unchanged)")
# ══════════════════════════════════════════════════

OWNER_RECORD_ID = "recOWNERPROFILE01"


def _tma_patch(task_fields):
    from flask import Flask
    import core.owner_resolution as owner_resolution
    flask_app = Flask(__name__)
    flask_app.register_blueprint(tma_api.tma_api)
    posted = []

    def fake_queue(action, payload, identity, label):
        posted.append((payload, label))
        return "appr-1", {"status": "pending_approval", "approval_id": "appr-1", "contract_id": "c-1"}, 202

    def fake_claim(approval_id, identity):
        return {"ok": True, "status_code": 200, "execution_result": {"contract_status": "executed"}}

    ident = Identity(user_id="eliyahu", role=Role.OWNER, display_name="eliyahu", tenant_id="boss_hq",
                     domain_id="general", channel="telegram", external_id="999999")
    with _today(), patch.object(tma_api, "_validate_initdata", lambda s: {"id": "999999"}), \
         patch.object(tma_api, "resolve_identity", lambda ch, tid: ident), \
         patch.object(tma_api, "_at_get_record", lambda table, rid: {"id": rid, "fields": {**task_fields, TaskFields.OWNER: [OWNER_RECORD_ID]}}), \
         patch.object(owner_resolution, "list_records", lambda table, formula="", max_records=50, paginate=True: [
             {"id": OWNER_RECORD_ID, "fields": {ProfileFields.NAME: "Eliyahu"}}]), \
         patch.object(tma_api, "_queue_tma_write_approval", fake_queue), \
         patch.object(tma_api, "_claim_and_execute_approval", fake_claim):
        r = flask_app.test_client().patch(f"/api/tasks/{REC}", json={"status": "done"},
                                          headers={"X-Telegram-Init-Data": "x"})
    return r, posted


r, posted = _tma_patch(_record(**{CAD: WEEKLY, DUE: "2026-09-24"}))
chk("M1 recurring Task: 200, the proposal (before approval) advances the SAME record",
    r.status_code == 200 and len(posted) == 1
    and posted[0][0]["record_id"] == REC and posted[0][0]["op"] == "patch"
    and posted[0][0]["fields"] == {S: PENDING, DUE: "2026-10-01"})
chk("M1 response shape unchanged (executed)", r.get_json().get("status") == "executed")
r, posted = _tma_patch(_record(**{DUE: "2026-09-24"}))
chk("M2 One-time (empty Cadence): normal Done", r.status_code == 200 and posted[0][0]["fields"] == {S: DONE})
r, posted = _tma_patch(_record(**{CAD: "One Time", DUE: "2026-09-24"}))
chk("M3 legacy 'One Time': normal Done", posted[0][0]["fields"] == {S: DONE})
r, posted = _tma_patch(_record(**{CAD: WEEKLY}))
chk("M4 undated Weekly: 409 asking only for the date, nothing proposed",
    r.status_code == 409 and posted == [] and r.get_json().get("error") == ASK_START_DATE_MESSAGE)
r, posted = _tma_patch(_record(**{CAD: DAILY, DUE: "2026-09-20", S: DONE}))
chk("M5 recurring Task already Done → normal Done (no second advance)", posted[0][0]["fields"] == {S: DONE})
chk("M6 Mini App create path does not write Cadence (stays One-time)",
    "RECURRENCE" not in open("tma_api.py", encoding="utf-8").read().split("def create_lead_task", 1)[1].split("\n@tma_api.route", 1)[0])

# ══════════════════════════════════════════════════
print("\n[R13] date-only follow-up: user-supported recurrence survives, model-only never does")
# ══════════════════════════════════════════════════

SENDER = owner.external_id


def _draft():
    return lead_sessions.get_task_recurrence_draft(SENDER, channel=owner.channel)


def _clear_draft():
    lead_sessions.set_task_recurrence_draft(SENDER, {}, channel=owner.channel)


def _followup(fields, text="1/10/26"):
    return gate1("airtable_add", {"table": Tables.TASKS, "fields": fields}, user_text=text)[0]


FOLLOWUP = {NAME: "לשלוח דוח", CAD: WEEKLY, DUE: "2026-10-01"}

# ── A. user-supported (Agent origin) survives a date-only answer ──
_clear_draft()
out = _followup({NAME: "לשלוח דוח"}, "תזכיר לי כל שבוע לשלוח דוח")
d = _draft() or {}
chk("A1 user said 'כל שבוע', no date → asks ONLY for the date and saves a draft from the USER's request",
    isinstance(out, CanonicalizationError) and out.user_message == ASK_START_DATE_MESSAGE
    and d.get("recurrence") == WEEKLY and d.get("user_id") == owner.user_id
    and d.get("tenant_id") == owner.tenant_id and d.get("claimed_title") is None)
inputs = {"table": Tables.TASKS, "fields": dict(FOLLOWUP)}
out, _ = gate1("airtable_add", inputs, user_text="1/10/26")
chk("A2 date-only answer; model carries Weekly + date → verified against the draft, payload unchanged",
    out is inputs and (_draft() or {}).get("claimed_title") == "לשלוח דוח")
out, _ = gate1("airtable_add", {"table": Tables.TASKS, "fields": dict(FOLLOWUP)}, user_text="1/10/26")
chk("A3 second Gate 1 pass (propose_action re-runs it) → still verified (idempotent claim)",
    isinstance(out, dict) and out["fields"].get(CAD) == WEEKLY)
out = _followup({NAME: "משימה אחרת", CAD: WEEKLY, DUE: "2026-10-02"}, "2/10/26")
chk("A4 the claimed draft cannot lend its recurrence to a DIFFERENT Task",
    isinstance(out, CanonicalizationError) and out.code == "recurrence_unsupported")

# ── B. user-supported (router origin), full proposal: approved == executed ──
_clear_draft()
out, _ = gate1("airtable_add", {"table": Tables.TASKS, "fields": {NAME: "כל שבוע לשלוח דוח", CAD: WEEKLY}},
               trusted_source="deterministic_create_task", user_text="צור משימה: כל שבוע לשלוח דוח")
chk("B1 router create 'צור משימה: כל שבוע …' without a date → asks for the date, draft saved",
    isinstance(out, CanonicalizationError) and (_draft() or {}).get("recurrence") == WEEKLY)
with _today(), patch.object(app, "resolve_identity", lambda *a, **k: owner), \
     patch.object(gateway_module, "_fetch_task_link_record", lambda t, r: None):
    result = app._queue_approval_detailed(
        "airtable_add", {"table": Tables.TASKS, "fields": {NAME: "כל שבוע לשלוח דוח", CAD: WEEKLY, DUE: "2026-10-01"}},
        SENDER, "telegram", "1/10/26",
    )
contract = action_gateway.find_contract(result.get("contract_id")) if result.get("contract_id") else None
stored = contract.normalized_payload if contract else {}
chk("B2 date-only answer through the real app path (both Gate 1 passes) → the contract stores Weekly",
    stored.get("fields") == {NAME: "כל שבוע לשלוח דוח", CAD: WEEKLY, DUE: "2026-10-01"})
chk("B3 …and its fingerprint matches the dispatcher's recomputation (approved == executed)",
    contract is not None and _validate_execution_proof("airtable_add", stored, owner, _ctx(contract), "agent") is None)

# ── C. model-only recurrence never becomes a business fact ──
_clear_draft()
with _today(), patch.object(action_gateway, "propose_action", side_effect=AssertionError("must not propose")) as spy:
    result = app._queue_approval_detailed(
        "airtable_add", {"table": Tables.TASKS, "fields": dict(FOLLOWUP)}, "chat-rec-model-only", "telegram", "1/10/26",
    )
chk("C1 date-only answer, NO user-supported draft, model says Weekly → nothing proposed; asks about the frequency",
    result.get("terminal_outcome") == "APPROVAL_QUEUE_NEVER_ATTEMPTED" and spy.call_count == 0
    and result.get("message") == ASK_RECURRENCE_MESSAGE)
out = _followup(dict(FOLLOWUP), "תזכיר לי לשלוח דוח שבועי")
chk("C2 first turn, text has no recurrence phrase, model infers Weekly → rejected (not written as a fact)",
    isinstance(out, CanonicalizationError) and out.code == "recurrence_unsupported")
out = _followup({NAME: "לשלוח דוח", CAD: WEEKLY}, "תזכיר לי לשלוח דוח")
chk("C3 model-only Weekly without a date → asks about the frequency (not the date) and saves NO draft",
    isinstance(out, CanonicalizationError) and out.code == "recurrence_unsupported" and _draft() is None)

lead_sessions.set_task_recurrence_draft(SENDER, {"recurrence": DAILY, "tenant_id": owner.tenant_id,
                                                 "user_id": owner.user_id, "created_at": time.time(),
                                                 "claimed_title": None}, channel=owner.channel)
chk("C4 draft says Daily, model says Weekly → rejected", _followup(dict(FOLLOWUP)).code == "recurrence_unsupported")
lead_sessions.set_task_recurrence_draft(SENDER, {"recurrence": WEEKLY, "tenant_id": owner.tenant_id,
                                                 "user_id": owner.user_id, "created_at": time.time() - 31 * 60,
                                                 "claimed_title": None}, channel=owner.channel)
chk("C5 expired draft (>30 min) → rejected", _followup(dict(FOLLOWUP)).code == "recurrence_unsupported")
lead_sessions.set_task_recurrence_draft(SENDER, {"recurrence": WEEKLY, "tenant_id": owner.tenant_id,
                                                 "user_id": "someone-else", "created_at": time.time(),
                                                 "claimed_title": None}, channel=owner.channel)
chk("C6 draft bound to another user → rejected", _followup(dict(FOLLOWUP)).code == "recurrence_unsupported")
with patch.object(lead_sessions, "get_task_recurrence_draft", side_effect=RuntimeError("store down")):
    out = _followup(dict(FOLLOWUP))
chk("C7 draft store unreadable → rejected (fail closed)",
    isinstance(out, CanonicalizationError) and out.code == "recurrence_unsupported")
_clear_draft()
inputs = {"table": Tables.TASKS, "fields": {NAME: "לשלוח דוח", CAD: ONE_TIME, DUE: "2026-10-01"}}
out, _ = gate1("airtable_add", inputs, user_text="1/10/26")
chk("C8 model One-time (the default, not a recurrence fact) → unaffected", out is inputs)

chk("P persistence: the draft slot is in the session defaults and both DB whitelists (not RAM-only)",
    "task_recurrence_draft" in session_store._new_session()
    and '"task_recurrence_draft"' in _SYNC_SRC and '"task_recurrence_draft"' in _LOAD_SRC)

print(f"\n{'=' * 60}")
print(f"Task recurrence tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
