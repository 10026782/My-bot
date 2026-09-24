#!/usr/bin/env python3
"""Task Golden Writer — canonical Task write core + every known bypass.

Standalone assert-based script (repo convention:
`python3 test_task_golden_writer.py`).

Blank-Task audit (24/09/2026): 97 live Tasks rows had an empty
`כותרת המשימה` because no layer validated the title *value* — only the
presence of the `fields`/`row_data` keys. Root cause: core/action_gateway.py's
sheets_append → Tasks positional converter (`row_data[0]` unchecked), with the
generic airtable_add path equally unguarded.

Covers:
  A. core/task_writer.py — pure validation/normalization rules
  B. gate 1 — resolve_canonical_call() fails closed before any approval
  C. app._queue_approval_detailed — the Agent gets a Diamond "ask for title"
     message and no ActionContract is attempted
  D. gate 2 — dispatcher airtable_add/airtable_update on Tasks
  E. interaction_engine — LLM tasks without a real title are never proposed
  F. abandoned_lead_worker — no identifiable sender → no task
"""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-task-golden-writer-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:TASK_GOLDEN_WRITER_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patTaskGoldenWriterTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appTaskGoldenWriterTest")
os.environ.setdefault("RENDER_APP_URL", "https://example.com")
os.environ.setdefault("SETUP_WEBHOOK", "0")
os.environ["FEATURE_ACTION_CONTRACT_PERSISTENCE"] = "false"

import app  # noqa: E402
import tools.dispatcher as dispatcher_module  # noqa: E402
from airtable_schema import Tables, TaskFields, TaskStatus  # noqa: E402
from core import task_writer  # noqa: E402
from core.action_gateway import (  # noqa: E402
    CanonicalizationError, TaskCanonicalizationError, action_gateway, enforce_task_write_contract,
    resolve_canonical_call,
)
from core.task_writer import (  # noqa: E402
    ASK_TITLE_MESSAGE, TaskWriteRejected, prepare_task_create, prepare_task_update,
)
from identity import Identity, Role  # noqa: E402

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


def rejected(fn, *args, **kwargs) -> TaskWriteRejected | None:
    try:
        fn(*args, **kwargs)
    except TaskWriteRejected as exc:
        return exc
    return None


def canon_error(tool, inputs, user_text="", trusted_source="agent"):
    try:
        enforce_task_write_contract(*resolve_canonical_call(tool, inputs, user_text), trusted_source)
    except CanonicalizationError as exc:
        return exc
    return None


REC_A = "recAAAAAAAAAAAAAA"
REC_B = "recBBBBBBBBBBBBBB"

# ══════════════════════════════════════════════════
print("\n[A] Golden Writer — title is the only required business field")
# ══════════════════════════════════════════════════

_BLANK_TITLES = {
    "empty": "", "spaces": "   ", "tabs/newlines": "\t\n ", "nbsp": "  ",
    "zero-width": "​‏", "None": None, "punctuation": "...", "emoji-only": "📞",
    "dash": "—",
}
for label, value in _BLANK_TITLES.items():
    exc = rejected(prepare_task_create, {TaskFields.NAME: value})
    chk(f"title {label!r} is rejected and asks only for the title",
        exc is not None and exc.missing == (TaskFields.NAME,) and exc.user_message == ASK_TITLE_MESSAGE)

exc = rejected(prepare_task_create, {TaskFields.STATUS: TaskStatus.PENDING, TaskFields.DESCRIPTION: "x"})
chk("missing title key (only other fields) is rejected — the exact live blank-row shape",
    exc is not None and exc.code == "title_missing")
chk("empty fields dict is rejected", rejected(prepare_task_create, {}) is not None)
chk("non-dict fields is rejected", rejected(prepare_task_create, ["x"]) is not None)
for bad in (123, ["לקרוא לדני"], {"he": "x"}):
    chk(f"non-text title {bad!r} is rejected",
        getattr(rejected(prepare_task_create, {TaskFields.NAME: bad}), "code", "") == "title_invalid_type")

for placeholder in ("משימה", "משימה חדשה", "Task", "NEW TASK", "null", "None", "N/A", "undefined", "TBD", "משימה.",
                    "[משימה]", "> משימה", '"Task"', "to-do"):
    chk(f"placeholder title {placeholder!r} (hallucination-prone LLM echo) is rejected",
        getattr(rejected(prepare_task_create, {TaskFields.NAME: placeholder}), "code", "") == "title_placeholder")

chk("over-long title is rejected, not truncated",
    getattr(rejected(prepare_task_create, {TaskFields.NAME: "א" * 251}), "code", "") == "title_too_long")

out = prepare_task_create({TaskFields.NAME: "  ​לקרוא   לדני  "})
chk("valid title is normalized (NFKC, zero-width removed, whitespace collapsed)",
    out[TaskFields.NAME] == "לקרוא לדני")
chk("Status is deterministically defaulted to ממתין", out[TaskFields.STATUS] == TaskStatus.PENDING)
chk("nothing else is invented (no Owner/Due/Description/links)", set(out) == {TaskFields.NAME, TaskFields.STATUS})
chk("a short real title such as 'CRM' is accepted", prepare_task_create({TaskFields.NAME: "CRM"})[TaskFields.NAME] == "CRM")
chk("a title that merely contains the word משימה is accepted",
    prepare_task_create({TaskFields.NAME: "משימה לדני — הצעת מחיר"})[TaskFields.NAME] == "משימה לדני — הצעת מחיר")

print("\n[A] Golden Writer — optional fields")
chk("Status alias 'done' → בוצע",
    prepare_task_create({TaskFields.NAME: "x1", TaskFields.STATUS: "done"})[TaskFields.STATUS] == TaskStatus.DONE)
chk("Status בביצוע kept", prepare_task_create({TaskFields.NAME: "x1", TaskFields.STATUS: "בביצוע"})[TaskFields.STATUS] == TaskStatus.IN_PROGRESS)
chk("unknown Status is rejected, not guessed",
    getattr(rejected(prepare_task_create, {TaskFields.NAME: "x1", TaskFields.STATUS: "urgent"}), "code", "") == "status_invalid")
chk("valid due date kept",
    prepare_task_create({TaskFields.NAME: "x1", TaskFields.DUE_DATE: "2026-10-01"})[TaskFields.DUE_DATE] == "2026-10-01")
for bad_due in ("tomorrow", "מחר", "2026-02-31", "01/10/2026", "2026-10-01T10:00", 20261001):
    chk(f"due date {bad_due!r} is rejected, never guessed",
        getattr(rejected(prepare_task_create, {TaskFields.NAME: "x1", TaskFields.DUE_DATE: bad_due}), "code", "") == "due_date_invalid")
out = prepare_task_create({TaskFields.NAME: "x1", TaskFields.DUE_DATE: "", TaskFields.DESCRIPTION: "  ", "tenant_id": "boss_hq"})
chk("empty optional fields are dropped; tenant_id is ignored", set(out) == {TaskFields.NAME, TaskFields.STATUS})
chk("unknown field is rejected (fail closed)",
    getattr(rejected(prepare_task_create, {TaskFields.NAME: "x1", "Priority": "high"}), "code", "") == "field_unknown")
out = prepare_task_create({"title": "לקרוא לדני", "due_date": "2026-10-01"})
chk("English aliases title/due_date map deterministically to the Hebrew fields",
    out[TaskFields.NAME] == "לקרוא לדני" and out[TaskFields.DUE_DATE] == "2026-10-01")
chk("the same field under two names is rejected as ambiguous",
    getattr(rejected(prepare_task_create, {"title": "a1", TaskFields.NAME: "b1"}), "code", "") == "field_ambiguous")

print("\n[A] Golden Writer — record ids are never trusted from the Agent")
for field in (TaskFields.OWNER, TaskFields.CONTACTS_LINK, TaskFields.DEALS_LINK, TaskFields.LEAD_LINK):
    chk(f"Agent-supplied {field} is rejected",
        getattr(rejected(prepare_task_create, {TaskFields.NAME: "x1", field: [REC_A]}, source="agent"), "code", "") == "link_untrusted")
chk("unspecified source defaults to untrusted",
    rejected(prepare_task_create, {TaskFields.NAME: "x1", TaskFields.OWNER: [REC_A]}) is not None)
out = prepare_task_create({TaskFields.NAME: "x1", TaskFields.LEAD_LINK: REC_A}, source="interaction_engine_scheduler")
chk("trusted internal source may link a well-formed record id (normalized to a list)", out[TaskFields.LEAD_LINK] == [REC_A])
chk("trusted source with a malformed record id is still rejected",
    getattr(rejected(prepare_task_create, {TaskFields.NAME: "x1", TaskFields.OWNER: ["Eli"]}, source="tma_api"), "code", "") == "link_invalid")

print("\n[A] Golden Writer — idempotence + update")
once = prepare_task_create({TaskFields.NAME: " לקרוא לדני ", TaskFields.STATUS: "pending", TaskFields.DUE_DATE: "2026-10-01"})
chk("prepare(prepare(x)) == prepare(x)", prepare_task_create(once) == once)
chk("update blanking the title is rejected", rejected(prepare_task_update, {TaskFields.NAME: "  "}) is not None)
chk("update without a title key is allowed (status only)",
    prepare_task_update({TaskFields.STATUS: "done"}) == {TaskFields.STATUS: TaskStatus.DONE})
chk("update with an invalid due date is rejected", rejected(prepare_task_update, {TaskFields.DUE_DATE: "tomorrow"}) is not None)

# ══════════════════════════════════════════════════
print("\n[B] Gate 1 — proposal boundary (resolve_canonical_call + enforce_task_write_contract)")
# ══════════════════════════════════════════════════

for row in ([""], ["   "], ["​"], ["משימה"], ["", "2026-10-01"]):
    exc = canon_error("sheets_append", {"sheet_name": "Tasks", "row_data": row})
    chk(f"ROOT CAUSE sheets_append row_data={row!r} → TaskCanonicalizationError asking for the title",
        isinstance(exc, TaskCanonicalizationError) and exc.missing == (TaskFields.NAME,)
        and exc.user_message == ASK_TITLE_MESSAGE)

tool, payload = resolve_canonical_call("sheets_append", {"sheet_name": "Tasks", "row_data": ["לקרוא לדני", "2026-10-01"]})
chk("valid sheets_append row still canonicalizes to airtable_add, payload NOT rewritten (fingerprint parity)",
    tool == "airtable_add"
    and payload == {"table": Tables.TASKS, "fields": {TaskFields.NAME: "לקרוא לדני", TaskFields.DUE_DATE: "2026-10-01"}})

for fields in ({TaskFields.NAME: ""}, {TaskFields.NAME: "   "}, {}, {TaskFields.STATUS: TaskStatus.PENDING}):
    for table in ("Tasks", Tables.TASKS):
        exc = canon_error("airtable_add", {"table": table, "fields": fields})
        chk(f"generic airtable_add {table!r} fields={fields!r} → rejected before approval",
            isinstance(exc, TaskCanonicalizationError))

chk("Agent airtable_add with a hallucinated Owner id → rejected",
    isinstance(canon_error("airtable_add", {"table": "Tasks", "fields": {TaskFields.NAME: "x1", TaskFields.OWNER: [REC_A]}}),
               TaskCanonicalizationError))
chk("same Owner from a trusted internal source is accepted at the proposal boundary",
    canon_error("airtable_add", {"table": "Tasks", "fields": {TaskFields.NAME: "x1", TaskFields.OWNER: [REC_A]}},
                trusted_source="interaction_engine_scheduler") is None)
chk("airtable_update blanking a Task title → rejected",
    isinstance(canon_error("airtable_update", {"table": "Tasks", "record_id": REC_B, "fields": {TaskFields.NAME: ""}}),
               TaskCanonicalizationError))
chk("airtable_update status-only on Tasks is unaffected",
    canon_error("airtable_update", {"table": "Tasks", "record_id": REC_B, "fields": {TaskFields.STATUS: "done"}}) is None)
chk("non-Task tables are untouched by the Task writer",
    canon_error("airtable_add", {"table": "Interaction Log", "fields": {"Summary": ""}}) is None)

with patch.object(action_gateway, "find_live_contracts", side_effect=AssertionError("must not be reached")):
    try:
        action_gateway.propose_action(
            tenant_id="boss_hq", canonical_user_id="u1", tool_name="airtable_add",
            tool_inputs={"table": Tables.TASKS, "fields": {TaskFields.NAME: " "}},
            origin_channel="scheduler", origin_chat_id="u1", requires_approval=True,
        )
        raised = False
    except TaskCanonicalizationError:
        raised = True
chk("propose_action (worker entry point) raises before any ledger/live-contract access", raised)

# ══════════════════════════════════════════════════
print("\n[C] Agent path — Diamond ask, no ActionContract attempted")
# ══════════════════════════════════════════════════

with patch.object(action_gateway, "propose_action", side_effect=AssertionError("must not propose")) as spy:
    result = app._queue_approval_detailed(
        "sheets_append", {"sheet_name": "Tasks", "row_data": [""]}, "chat-golden-1", "telegram", "צור משימה",
    )
chk("blank sheets_append from the Agent → ok=False, never queued",
    result.get("ok") is False and result.get("terminal_outcome") == "APPROVAL_QUEUE_NEVER_ATTEMPTED"
    and result.get("contract_id") is None and spy.call_count == 0)
chk("…and the Agent is told to ask only for the missing title", result.get("message") == ASK_TITLE_MESSAGE)

with patch.object(action_gateway, "propose_action", side_effect=AssertionError("must not propose")) as spy:
    result = app._queue_approval_detailed(
        "airtable_add", {"table": "Tasks", "fields": {TaskFields.NAME: " "}}, "chat-golden-2", "telegram", "",
    )
chk("blank generic airtable_add from the Agent → never queued, asks for the title",
    result.get("ok") is False and spy.call_count == 0 and result.get("message") == ASK_TITLE_MESSAGE)

# ══════════════════════════════════════════════════
print("\n[D] Gate 2 — dispatcher execution boundary")
# ══════════════════════════════════════════════════

owner = Identity(
    user_id="owner-golden-writer", role=Role.OWNER, display_name="owner-golden-writer",
    tenant_id="boss_hq", domain_id="general", channel="telegram", external_id="owner-golden-writer",
)


def _dispatch(name, inputs, trusted_source="agent"):
    with patch.object(dispatcher_module, "_validate_execution_proof", return_value=None), \
         patch.object(dispatcher_module._ff, "is_enabled", return_value=False):
        return dispatcher_module.dispatch_tool(
            name, inputs, identity=owner, trusted_source=trusted_source,
            execution_context={"contract_id": "c-golden"},
        )


_ok_write = {"ok": True, "tool": "airtable_add", "external_id": "recCCCCCCCCCCCCCC",
             "evidence": {"record_id": "recCCCCCCCCCCCCCC"}, "user_message": "ok"}

for fields in ({TaskFields.NAME: ""}, {TaskFields.NAME: "   "}, {TaskFields.STATUS: TaskStatus.DONE}, {TaskFields.NAME: "Task"}):
    with patch.object(dispatcher_module, "airtable_add", return_value=_ok_write) as write, \
         patch.object(dispatcher_module, "_check_duplicate", return_value=None):
        result = _dispatch("airtable_add", {"table": "Tasks", "fields": fields})
    chk(f"stored/legacy contract with fields={fields!r} never reaches Airtable",
        write.call_count == 0 and isinstance(result, dict) and result.get("ok") is False
        and result.get("user_message") == ASK_TITLE_MESSAGE)

with patch.object(dispatcher_module, "airtable_add", return_value=_ok_write) as write, \
     patch.object(dispatcher_module, "_check_duplicate", return_value=None) as dedup:
    result = _dispatch("airtable_add", {"table": "Tasks", "fields": {TaskFields.NAME: "  לקרוא לדני ", "due_date": "2026-10-01"}})
chk("valid Task is written once", write.call_count == 1 and result.get("ok") is True)
chk("written fields are the Golden Writer's normalized output (title trimmed, Status defaulted, alias mapped)",
    write.call_args.args[1] == {TaskFields.NAME: "לקרוא לדני", TaskFields.STATUS: TaskStatus.PENDING,
                                TaskFields.DUE_DATE: "2026-10-01"})
chk("dedup still runs, on the normalized title", dedup.call_args.args[2] == "לקרוא לדני")

with patch.object(dispatcher_module, "airtable_add", return_value=_ok_write) as write, \
     patch.object(dispatcher_module, "_check_duplicate", return_value=None):
    result = _dispatch("airtable_add", {"table": "Tasks", "fields": {TaskFields.NAME: "x1", TaskFields.LEAD_LINK: [REC_A]}})
chk("Agent-sourced Lead link is refused at execution time too", write.call_count == 0 and result.get("ok") is False)

with patch.object(dispatcher_module, "airtable_add", return_value=_ok_write) as write, \
     patch.object(dispatcher_module, "_check_duplicate", return_value=None):
    _dispatch("airtable_add", {"table": "Tasks", "fields": {TaskFields.NAME: "x1", TaskFields.LEAD_LINK: [REC_A]}},
              trusted_source="abandoned_lead_scheduler")
chk("trusted scheduler source may carry a well-formed Lead link", write.call_count == 1)

with patch.object(dispatcher_module, "airtable_update", return_value=_ok_write) as upd:
    result = _dispatch("airtable_update", {"table": "Tasks", "record_id": REC_B, "fields": {TaskFields.NAME: " "}})
chk("airtable_update cannot blank an existing Task title", upd.call_count == 0 and result.get("ok") is False)

with patch.object(dispatcher_module, "airtable_update", return_value=_ok_write) as upd:
    _dispatch("airtable_update", {"table": "Tasks", "record_id": REC_B, "fields": {TaskFields.STATUS: "done"}})
chk("status update still written (alias normalized to בוצע)",
    upd.call_count == 1 and upd.call_args.args[2] == {TaskFields.STATUS: TaskStatus.DONE})

# ══════════════════════════════════════════════════
print("\n[E] interaction_engine — automatic Tasks need a real title")
# ══════════════════════════════════════════════════

import interaction_engine  # noqa: E402

analysis = interaction_engine.InteractionAnalysis(tasks=[
    {"title": ""}, {"title": "   "}, {"title": "משימה"}, {"owner": "דני"}, "not-a-dict", None,
    {"title": "לשלוח הצעת מחיר לדני", "due": "tomorrow"},
    {"title": "לתאם פגישה", "due": "2026-10-05"},
])
interaction = interaction_engine.InteractionSchema(source_channel="email", raw_id="r1", title="שיחה עם דני")
proposal = MagicMock(ok=False, contract_id="", reason="spy")
with patch.object(action_gateway, "propose_action", return_value=proposal) as spy:
    interaction_engine.create_tasks_from_analysis(analysis, interaction)
titles = [c.kwargs["tool_inputs"]["fields"][TaskFields.NAME] for c in spy.call_args_list]
chk("only the two LLM tasks with real titles are proposed", titles == ["לשלוח הצעת מחיר לדני", "לתאם פגישה"])
chk("an invalid LLM due date is dropped (optional), not guessed",
    TaskFields.DUE_DATE not in spy.call_args_list[0].kwargs["tool_inputs"]["fields"])
chk("a valid LLM due date is kept",
    spy.call_args_list[1].kwargs["tool_inputs"]["fields"].get(TaskFields.DUE_DATE) == "2026-10-05")
chk("every proposed payload passes the Golden Writer",
    all(task_writer.prepare_task_create(c.kwargs["tool_inputs"]["fields"], source=c.kwargs["trusted_source"])
        for c in spy.call_args_list))

# ══════════════════════════════════════════════════
print("\n[F] abandoned_lead_worker — title derived from the lead, else no task")
# ══════════════════════════════════════════════════

import abandoned_lead_worker as alw  # noqa: E402


def _lead(sender):
    return alw.AbandonedLead(sender=sender, channel="voice", domain="general", step=2, total_steps=4, minutes_silent=30)


for sender in ("", "   ", None):
    with patch.object(action_gateway, "propose_action", side_effect=AssertionError("must not propose")) as spy:
        ok = alw.create_human_pipeline_task(_lead(sender), owner_chat_id="1")
    chk(f"sender={sender!r} → no task created", ok is False and spy.call_count == 0)

with patch.object(action_gateway, "propose_action", return_value=MagicMock(ok=False, contract_id="", reason="spy")) as spy:
    alw.create_human_pipeline_task(_lead(" 0501234567 "), owner_chat_id="1")
fields = spy.call_args.kwargs["tool_inputs"]["fields"]
chk("identifiable sender → task title derived from it", fields[TaskFields.NAME] == "📞 ליד נטוש — 0501234567")
chk("…and it passes the Golden Writer", bool(task_writer.prepare_task_create(fields, source="abandoned_lead_scheduler")))


print(f"\n{'=' * 60}")
print(f"Task Golden Writer tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
