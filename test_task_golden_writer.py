#!/usr/bin/env python3
"""Task Golden Writer — canonical Task write core + every known bypass.

Standalone assert-based script (repo convention:
`python3 test_task_golden_writer.py`).

Blank-Task audit (24/09/2026): 97 live Tasks rows had an empty
`כותרת המשימה` because no layer validated the title *value* — only the
presence of the `fields`/`row_data` keys. Root cause: core/action_gateway.py's
sheets_append → Tasks positional converter (`row_data[0]` unchecked), with the
generic airtable_add path equally unguarded.

Sections map 1:1 onto the four separated concerns:
  A. Golden Writer validation   (core/task_writer.py §1 — Title non-empty only)
  B. resolver / verification    (core/task_writer.py §2 — model-supplied links)
  C. Diamond completion         (core/task_writer.py §3 — derive Title first)
  D. Gate 1 — complete_task_proposal / propose_action (verification → Diamond → validation)
  E. caller UX — Agent path asks for the title only; no contract attempted
  F. Gate 2 — dispatcher persistence boundary (CREATE + UPDATE)
  G. interaction_engine / H. abandoned_lead_worker — automatic callers
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
import core.action_gateway as gateway_module  # noqa: E402
import tools.dispatcher as dispatcher_module  # noqa: E402
from airtable_schema import LeadFields, Tables, TaskFields, TaskStatus  # noqa: E402
from core import task_writer  # noqa: E402
from core.action_gateway import (  # noqa: E402
    ActionGateway, CanonicalizationError, ExecutionLedger, TaskCanonicalizationError,
    action_gateway, complete_task_proposal, resolve_canonical_call,
)
from core.task_writer import ASK_TITLE_MESSAGE, TaskWriteRejected, prepare_task_create, prepare_task_update  # noqa: E402
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


def rejected(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except TaskWriteRejected as exc:
        return exc
    return None


REC_LEAD = "recLEADAAAAAAAAAA"
REC_CONTACT = "recCONTACTAAAAAAA"
REC_MISSING = "recMISSINGAAAAAAA"
LEAD_FIELDS = {LeadFields.NAME: "דני כהן", LeadFields.NEXT_STEP: "Call Back"}

owner = Identity(
    user_id="owner-golden-writer", role=Role.OWNER, display_name="owner-golden-writer",
    tenant_id="boss_hq", domain_id="general", channel="telegram", external_id="owner-golden-writer",
)


def fake_fetch(records: dict):
    calls = []

    def _fetch(table, record_id):
        calls.append((table, record_id))
        return records.get((table, record_id))
    _fetch.calls = calls
    return _fetch


def gate1(tool, inputs, *, user_text="", trusted_source="agent", records=None, names=None, identity=owner):
    """resolve_canonical_call + complete_task_proposal with I/O faked."""
    fetch = fake_fetch(records or {})
    resolver = (lambda entity, name: (names or {}).get((entity, name), []))
    with patch.object(gateway_module, "_fetch_task_link_record", fetch), \
         patch.object(gateway_module, "_task_link_name_resolver", lambda ident: resolver if ident else None):
        tool, payload = resolve_canonical_call(tool, inputs, user_text)
        try:
            out = complete_task_proposal(tool, payload, trusted_source=trusted_source,
                                         identity=identity, user_text=user_text)
        except CanonicalizationError as exc:
            return exc, payload, fetch
    return out, payload, fetch


# ══════════════════════════════════════════════════
print("\n[A] Golden Writer validation — Title non-empty after normalization, nothing else")
# ══════════════════════════════════════════════════

for label, value in {"empty": "", "spaces": "   ", "tabs/newlines": "\t\n ", "nbsp": "  ",
                     "zero-width": "​‏﻿", "None": None, "number": 123, "list": ["x"]}.items():
    exc = rejected(prepare_task_create, {TaskFields.NAME: value})
    chk(f"title {label!r} → rejected, asks only for the title",
        exc is not None and exc.missing == (TaskFields.NAME,) and exc.user_message == ASK_TITLE_MESSAGE)
chk("missing title key → rejected (the live blank-row shape)",
    rejected(prepare_task_create, {TaskFields.STATUS: TaskStatus.PENDING}) is not None)
chk("empty / non-dict fields → rejected",
    rejected(prepare_task_create, {}) is not None and rejected(prepare_task_create, None) is not None)

for value in ("...", "📞", "—", "משימה", "Task", "null", "N/A", "א" * 300):
    chk(f"no new semantic restriction: {value[:12]!r} is a valid title",
        prepare_task_create({TaskFields.NAME: value})[TaskFields.NAME] == value)

out = prepare_task_create({TaskFields.NAME: "  ​לקרוא   לדני  "})
chk("safe normalization only (NFKC, zero-width removed, whitespace collapsed)", out[TaskFields.NAME] == "לקרוא לדני")
chk("no Status default is invented", TaskFields.STATUS not in out)
raw = {TaskFields.NAME: "x", TaskFields.STATUS: "urgent", TaskFields.DUE_DATE: "tomorrow", "Priority": "high",
       TaskFields.OWNER: ["recOWNERAAAAAAAAA"], "tenant_id": "boss_hq"}
chk("optional/unknown fields pass through untouched (existing contracts own them)",
    prepare_task_create(raw) == raw)
chk("prepare(prepare(x)) == prepare(x)", prepare_task_create(prepare_task_create(raw)) == prepare_task_create(raw))

print("\n[A] UPDATE")
chk("update not touching Title → valid, unchanged", prepare_task_update({TaskFields.STATUS: "done"}) == {TaskFields.STATUS: "done"})
chk("update with empty fields → valid", prepare_task_update({}) == {})
chk("update making Title empty → rejected", rejected(prepare_task_update, {TaskFields.NAME: "   "}) is not None)
chk("update making Title zero-width only → rejected", rejected(prepare_task_update, {TaskFields.NAME: "​"}) is not None)
chk("update with a real Title → normalized", prepare_task_update({TaskFields.NAME: " חדש "}) == {TaskFields.NAME: "חדש"})

# ══════════════════════════════════════════════════
print("\n[B] resolver / verification — model-supplied references")
# ══════════════════════════════════════════════════

fetch = fake_fetch({(Tables.LEADS, REC_LEAD): LEAD_FIELDS})
fields, verified, omitted = task_writer.verify_task_links(
    {TaskFields.NAME: "x", TaskFields.LEAD_LINK: [REC_LEAD]}, fetch_record=fetch)
chk("existing rec id → kept as canonical id, record fields captured",
    fields[TaskFields.LEAD_LINK] == [REC_LEAD] and verified[REC_LEAD] == LEAD_FIELDS and not omitted)
fields, _, omitted = task_writer.verify_task_links(
    {TaskFields.NAME: "x", TaskFields.LEAD_LINK: [REC_MISSING]}, fetch_record=fake_fetch({}))
chk("non-existent (hallucinated) rec id → omitted, field removed, never passed through",
    TaskFields.LEAD_LINK not in fields and omitted == [TaskFields.LEAD_LINK])
fields, _, _ = task_writer.verify_task_links(
    {TaskFields.LEAD_LINK: [REC_LEAD, REC_MISSING]}, fetch_record=fetch)
chk("mixed list → only verified ids kept", fields[TaskFields.LEAD_LINK] == [REC_LEAD])
chk("rec id looked up in the correct linked table", fetch.calls[0] == (Tables.LEADS, REC_LEAD))

names = {("contact", "דני"): [REC_CONTACT], ("contact", "יוסי"): ["recA0000000000001", "recA0000000000002"]}
resolver = lambda entity, name: names.get((entity, name), [])  # noqa: E731
fields, _, omitted = task_writer.verify_task_links(
    {TaskFields.CONTACTS_LINK: "דני"}, fetch_record=fake_fetch({}), resolve_name=resolver)
chk("contact name with exactly one canonical match → canonical id", fields[TaskFields.CONTACTS_LINK] == [REC_CONTACT])
fields, _, omitted = task_writer.verify_task_links(
    {TaskFields.CONTACTS_LINK: "יוסי"}, fetch_record=fake_fetch({}), resolve_name=resolver)
chk("ambiguous contact name → omitted (optional), never a guess",
    TaskFields.CONTACTS_LINK not in fields and omitted == [TaskFields.CONTACTS_LINK])
fields, _, _ = task_writer.verify_task_links(
    {TaskFields.DEALS_LINK: "עסקה שלא קיימת"}, fetch_record=fake_fetch({}), resolve_name=resolver)
chk("unknown deal name → omitted", TaskFields.DEALS_LINK not in fields)
fields, _, _ = task_writer.verify_task_links(
    {TaskFields.OWNER: "Eliyahu", TaskFields.LEAD_LINK: "דני"}, fetch_record=fake_fetch({}), resolve_name=resolver)
chk("Owner / Lead by name (no canonical name resolver) → omitted",
    TaskFields.OWNER not in fields and TaskFields.LEAD_LINK not in fields)
fields, _, _ = task_writer.verify_task_links({TaskFields.CONTACTS_LINK: "דני"}, fetch_record=fake_fetch({}))
chk("no resolver available (no identity) → name omitted", TaskFields.CONTACTS_LINK not in fields)

# ══════════════════════════════════════════════════
print("\n[C] Diamond completion — derive from trusted context, never invent")
# ══════════════════════════════════════════════════

chk("user's own text via the router's deterministic parser → title",
    task_writer.title_from_user_text("צור משימה לקנות חלב") == ("לקנות חלב", None))
title, due = task_writer.title_from_user_text("צור משימה לשלוח הצעת מחיר עד לתאריך 6/10/26")
chk("…and the parser's due date is reused", title == "לשלוח הצעת מחיר" and due == "2026-10-06")
chk("non-create text → nothing derived", task_writer.title_from_user_text("מה קורה עם דני?") == ("", None))
chk("bare 'צור משימה' → nothing derived", task_writer.title_from_user_text("צור משימה") == ("", None))
chk("Lead + actionable Next Action + known name → derived title",
    task_writer.title_from_lead(LEAD_FIELDS) == "להתקשר בחזרה — דני כהן")
chk("non-actionable Next Action (Waiting Response) → nothing derived",
    task_writer.title_from_lead({LeadFields.NAME: "דני", LeadFields.NEXT_STEP: "Waiting Response"}) == "")
chk("Next Action without a lead name → nothing derived",
    task_writer.title_from_lead({LeadFields.NEXT_STEP: "Call Back"}) == "")
chk("name without an action → nothing derived (a name is not a task)", task_writer.compose_title("", "דני") == "")
import tma_api  # noqa: E402
chk("actionable Next Action labels match the canonical TMA display labels",
    all(tma_api._LEAD_NEXT_ACTION_OPTIONS[k][1] == v for k, v in task_writer.ACTIONABLE_LEAD_NEXT_ACTIONS.items()))

# ══════════════════════════════════════════════════
print("\n[D] Gate 1 — proposal boundary")
# ══════════════════════════════════════════════════

for row in ([""], ["   "], ["​"], ["", "2026-10-01"]):
    exc, _, _ = gate1("sheets_append", {"sheet_name": "Tasks", "row_data": row})
    chk(f"ROOT CAUSE sheets_append row_data={row!r}, no context → TaskCanonicalizationError asking for the title",
        isinstance(exc, TaskCanonicalizationError) and exc.missing == (TaskFields.NAME,)
        and exc.user_message == ASK_TITLE_MESSAGE)

out, _, _ = gate1("sheets_append", {"sheet_name": "Tasks", "row_data": [""]}, user_text="צור משימה לקנות חלב")
chk("Diamond: blank sheets_append + user's own create-task text → title derived instead of asking",
    isinstance(out, dict) and out["fields"][TaskFields.NAME] == "לקנות חלב")

out, _, fetch = gate1("airtable_add", {"table": "Tasks", "fields": {TaskFields.NAME: "", TaskFields.LEAD_LINK: [REC_LEAD]}},
                      records={(Tables.LEADS, REC_LEAD): LEAD_FIELDS})
chk("Diamond: blank title + verified Lead (Call Back, דני כהן) → 'להתקשר בחזרה — דני כהן', link kept",
    isinstance(out, dict) and out["fields"][TaskFields.NAME] == "להתקשר בחזרה — דני כהן"
    and out["fields"][TaskFields.LEAD_LINK] == [REC_LEAD])

exc, _, _ = gate1("airtable_add", {"table": "Tasks", "fields": {TaskFields.NAME: "", TaskFields.LEAD_LINK: [REC_MISSING]}})
chk("blank title + hallucinated Lead id → not trusted, nothing derived → ask for title",
    isinstance(exc, TaskCanonicalizationError))
exc, _, _ = gate1("airtable_add", {"table": "Tasks", "fields": {TaskFields.NAME: "", TaskFields.LEAD_LINK: [REC_LEAD]}},
                  records={(Tables.LEADS, REC_LEAD): {LeadFields.NAME: "דני", LeadFields.NEXT_STEP: "Closed Won"}})
chk("blank title + verified Lead with a non-actionable Next Action → ask (no invented action)",
    isinstance(exc, TaskCanonicalizationError))
exc, _, _ = gate1("airtable_add", {"table": "Tasks", "fields": {TaskFields.NAME: "", TaskFields.CONTACTS_LINK: "דני"}},
                  names={("contact", "דני"): [REC_CONTACT]})
chk("blank title + verified Contact name only → ask (a name alone is not a task)",
    isinstance(exc, TaskCanonicalizationError))

payload = {"table": "Tasks", "fields": {TaskFields.NAME: "לקרוא לדני", TaskFields.LEAD_LINK: [REC_MISSING]}}
out, _, _ = gate1("airtable_add", payload)
chk("valid title + hallucinated optional link → Task kept, link omitted (not failed)",
    isinstance(out, dict) and out["fields"] == {TaskFields.NAME: "לקרוא לדני"})

payload = {"table": "Tasks", "fields": {TaskFields.NAME: "לקרוא לדני", TaskFields.STATUS: "urgent", "Due": "היום"}}
out, canonical, fetch = gate1("airtable_add", payload)
chk("valid payload without links → the SAME object is returned (fingerprint untouched), no I/O",
    out is canonical and fetch.calls == [])

out, canonical, fetch = gate1("airtable_add", {"table": "Tasks", "fields": {TaskFields.NAME: "x", TaskFields.LEAD_LINK: [REC_LEAD]}},
                              trusted_source="abandoned_lead_scheduler")
chk("trusted internal source → its links are not re-resolved (existing behavior)", out is canonical and fetch.calls == [])

exc, _, _ = gate1("airtable_update", {"table": "Tasks", "record_id": REC_LEAD, "fields": {TaskFields.NAME: " "}})
chk("UPDATE blanking a Title → rejected before approval", isinstance(exc, TaskCanonicalizationError))
out, canonical, _ = gate1("airtable_update", {"table": "Tasks", "record_id": REC_LEAD, "fields": {TaskFields.STATUS: "done"}})
chk("UPDATE not touching Title → unchanged", out is canonical)
out, canonical, _ = gate1("airtable_add", {"table": "Interaction Log", "fields": {"Summary": ""}})
chk("non-Task tables untouched", out is canonical)

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
chk("propose_action: underivable blank Title raises before any ledger/live-contract access", raised)

gw = ActionGateway(ledger=ExecutionLedger())
result = gw.propose_action(
    tenant_id="boss_hq", canonical_user_id="boss_hq:golden", tool_name="airtable_add",
    tool_inputs={"table": "Tasks", "fields": {TaskFields.NAME: ""}},
    origin_channel="telegram", origin_chat_id="golden", requires_approval=True,
    trusted_source="test_harness", user_text="צור משימה לקנות חלב",
    fingerprint_payload={"table": "Tasks", "fields": {TaskFields.NAME: ""}},
)
stored = gw.find_contract(result.contract_id) if result.ok else None
chk("propose_action: Diamond-completed title is what the contract stores (the owner approves what is written)",
    stored is not None and stored.normalized_payload["fields"][TaskFields.NAME] == "לקנות חלב")

# ══════════════════════════════════════════════════
print("\n[E] caller UX — Agent path")
# ══════════════════════════════════════════════════

with patch.object(action_gateway, "propose_action", side_effect=AssertionError("must not propose")) as spy:
    result = app._queue_approval_detailed(
        "sheets_append", {"sheet_name": "Tasks", "row_data": [""]}, "chat-golden-1", "telegram", "תעשה משהו",
    )
chk("underivable blank Task → never queued (NEVER_ATTEMPTED), Agent asked for the title only",
    result.get("ok") is False and result.get("terminal_outcome") == "APPROVAL_QUEUE_NEVER_ATTEMPTED"
    and result.get("contract_id") is None and spy.call_count == 0 and result.get("message") == ASK_TITLE_MESSAGE)

with patch.object(action_gateway, "propose_action", side_effect=RuntimeError("captured")) as spy:
    app._queue_approval_detailed(
        "sheets_append", {"sheet_name": "Tasks", "row_data": [""]}, "chat-golden-2", "telegram", "צור משימה לקנות חלב",
        fingerprint_payload={"table": "Tasks", "fields": {TaskFields.NAME: ""}},
    )
kwargs = spy.call_args.kwargs if spy.call_args else {}
chk("Diamond-completed Task reaches propose_action with the derived title (no question asked)",
    kwargs.get("tool_inputs", {}).get("fields", {}).get(TaskFields.NAME) == "לקנות חלב")
chk("…and the stale caller fingerprint_payload is dropped (fingerprint = what is dispatched)",
    kwargs.get("fingerprint_payload") is None)

# ══════════════════════════════════════════════════
print("\n[F] Gate 2 — dispatcher persistence boundary")
# ══════════════════════════════════════════════════


def _dispatch(name, inputs, trusted_source="agent"):
    with patch.object(dispatcher_module, "_validate_execution_proof", return_value=None), \
         patch.object(dispatcher_module._ff, "is_enabled", return_value=False):
        return dispatcher_module.dispatch_tool(
            name, inputs, identity=owner, trusted_source=trusted_source,
            execution_context={"contract_id": "c-golden"},
        )


_ok = {"ok": True, "tool": "airtable_add", "external_id": "recCCCCCCCCCCCCCC",
       "evidence": {"record_id": "recCCCCCCCCCCCCCC"}, "user_message": "ok"}

for fields in ({TaskFields.NAME: ""}, {TaskFields.NAME: "   "}, {TaskFields.STATUS: TaskStatus.DONE}):
    with patch.object(dispatcher_module, "airtable_add", return_value=_ok) as write, \
         patch.object(dispatcher_module, "_check_duplicate", return_value=None):
        result = _dispatch("airtable_add", {"table": "Tasks", "fields": fields})
    chk(f"stored/legacy contract fields={fields!r} never reaches Airtable",
        write.call_count == 0 and isinstance(result, dict) and result.get("ok") is False
        and result.get("user_message") == ASK_TITLE_MESSAGE)

with patch.object(dispatcher_module, "airtable_add", return_value=_ok) as write, \
     patch.object(dispatcher_module, "_check_duplicate", return_value=None) as dedup:
    result = _dispatch("airtable_add", {"table": "Tasks", "fields": {TaskFields.NAME: "  לקרוא לדני ", TaskFields.DUE_DATE: "2026-10-01"}})
chk("valid Task written once", write.call_count == 1 and result.get("ok") is True)
chk("written fields: normalized title, every other field untouched (no Status invented)",
    write.call_args.args[1] == {TaskFields.NAME: "לקרוא לדני", TaskFields.DUE_DATE: "2026-10-01"})
chk("dedup still runs, on the normalized title", dedup.call_args.args[2] == "לקרוא לדני")

with patch.object(dispatcher_module, "airtable_update", return_value=_ok) as upd:
    result = _dispatch("airtable_update", {"table": "Tasks", "record_id": REC_LEAD, "fields": {TaskFields.NAME: " "}})
chk("UPDATE cannot blank an existing Task title", upd.call_count == 0 and result.get("ok") is False)
with patch.object(dispatcher_module, "airtable_update", return_value=_ok) as upd:
    _dispatch("airtable_update", {"table": "Tasks", "record_id": REC_LEAD, "fields": {TaskFields.STATUS: TaskStatus.DONE}})
chk("UPDATE not touching Title written unchanged",
    upd.call_count == 1 and upd.call_args.args[2] == {TaskFields.STATUS: TaskStatus.DONE})

# ══════════════════════════════════════════════════
print("\n[G] interaction_engine")
# ══════════════════════════════════════════════════

import interaction_engine  # noqa: E402

analysis = interaction_engine.InteractionAnalysis(tasks=[
    {"title": ""}, {"title": "  ​"}, {"owner": "דני"}, "not-a-dict", None,
    {"title": "משימה"},
    {"title": "לשלוח הצעת מחיר לדני", "due": "tomorrow"},
    {"title": "לתאם פגישה", "due": "2026-10-05"},
])
interaction = interaction_engine.InteractionSchema(source_channel="email", raw_id="r1", title="שיחה עם דני")
with patch.object(action_gateway, "propose_action", return_value=MagicMock(ok=False, contract_id="", reason="spy")) as spy:
    interaction_engine.create_tasks_from_analysis(analysis, interaction)
calls = [c.kwargs["tool_inputs"]["fields"] for c in spy.call_args_list]
chk("items with a non-empty title are proposed (no placeholder blacklist); blank/untitled items are not",
    [f[TaskFields.NAME] for f in calls] == ["משימה", "לשלוח הצעת מחיר לדני", "לתאם פגישה"])
chk("invalid model-derived due date is omitted, the Task still created", TaskFields.DUE_DATE not in calls[1])
chk("valid due date kept", calls[2].get(TaskFields.DUE_DATE) == "2026-10-05")
chk("worker's existing Status default is preserved", all(f[TaskFields.STATUS] == TaskStatus.PENDING for f in calls))

# ══════════════════════════════════════════════════
print("\n[H] abandoned_lead_worker")
# ══════════════════════════════════════════════════

import abandoned_lead_worker as alw  # noqa: E402


def _lead(sender, answers=None):
    return alw.AbandonedLead(sender=sender, channel="voice", domain="general", step=2, total_steps=4,
                             minutes_silent=30, answers=answers or {})


def _title_for(lead):
    with patch.object(action_gateway, "propose_action", return_value=MagicMock(ok=False, contract_id="", reason="spy")) as spy:
        ok = alw.create_human_pipeline_task(lead, owner_chat_id="1")
    return ok, (spy.call_args.kwargs["tool_inputs"]["fields"][TaskFields.NAME] if spy.call_args else None)


chk("sender present → existing template unchanged", _title_for(_lead("0501234567"))[1] == "📞 ליד נטוש — 0501234567")
chk("no sender but the lead's own name in its answers → derived from it (not skipped)",
    _title_for(_lead("", {"name": "דני"}))[1] == "📞 ליד נטוש — דני")
ok, title = _title_for(_lead("  ", {"budget": "2M"}))
chk("no sender and no lead name → skipped (nothing identifies the lead)", ok is False and title is None)


# ══════════════════════════════════════════════════
print("\n[U] UPDATE regression — Title is protected, never required")
# ══════════════════════════════════════════════════

_UPDATE_NO_TITLE = {TaskFields.STATUS: TaskStatus.DONE, TaskFields.DUE_DATE: "2026-10-01"}
_UPDATE_VALID_TITLE = {TaskFields.NAME: "לתאם פגישה עם דני"}
_UPDATE_BLANK_TITLES = {"empty": "", "whitespace": "   ", "nbsp/zero-width": "\u00a0\u200b"}

# writer level
chk("U1 writer: update WITHOUT Title → allowed, unchanged", prepare_task_update(_UPDATE_NO_TITLE) == _UPDATE_NO_TITLE)
chk("U2 writer: update with a valid Title → allowed", prepare_task_update(_UPDATE_VALID_TITLE) == _UPDATE_VALID_TITLE)
for label, blank in _UPDATE_BLANK_TITLES.items():
    chk(f"U3 writer: update to {label} Title → rejected", rejected(prepare_task_update, {TaskFields.NAME: blank}) is not None)

# Gate 1 (before approval)
out, canonical, _ = gate1("airtable_update", {"table": "Tasks", "record_id": REC_LEAD, "fields": dict(_UPDATE_NO_TITLE)})
chk("U1 Gate 1: update WITHOUT Title → allowed, payload untouched", out is canonical)
out, canonical, _ = gate1("airtable_update", {"table": "Tasks", "record_id": REC_LEAD, "fields": dict(_UPDATE_VALID_TITLE)})
chk("U2 Gate 1: update with a valid Title → allowed, payload untouched", out is canonical)
for label, blank in _UPDATE_BLANK_TITLES.items():
    exc, _, _ = gate1("airtable_update", {"table": "Tasks", "record_id": REC_LEAD, "fields": {TaskFields.NAME: blank}})
    chk(f"U3 Gate 1: update to {label} Title → rejected before approval", isinstance(exc, TaskCanonicalizationError))

# Gate 2 (persistence)
with patch.object(dispatcher_module, "airtable_update", return_value=_ok) as upd:
    _dispatch("airtable_update", {"table": "Tasks", "record_id": REC_LEAD, "fields": dict(_UPDATE_NO_TITLE)})
chk("U1 Gate 2: update WITHOUT Title → written exactly as approved",
    upd.call_count == 1 and upd.call_args.args[2] == _UPDATE_NO_TITLE)
with patch.object(dispatcher_module, "airtable_update", return_value=_ok) as upd:
    _dispatch("airtable_update", {"table": "Tasks", "record_id": REC_LEAD, "fields": dict(_UPDATE_VALID_TITLE)})
chk("U2 Gate 2: update with a valid Title → written",
    upd.call_count == 1 and upd.call_args.args[2] == _UPDATE_VALID_TITLE)
for label, blank in _UPDATE_BLANK_TITLES.items():
    with patch.object(dispatcher_module, "airtable_update", return_value=_ok) as upd:
        result = _dispatch("airtable_update", {"table": "Tasks", "record_id": REC_LEAD, "fields": {TaskFields.NAME: blank}})
    chk(f"U3 Gate 2: update to {label} Title → rejected, never written",
        upd.call_count == 0 and result.get("ok") is False)

# ══════════════════════════════════════════════════
print("\n[P] proposed == approved == fingerprinted == executed")
# ══════════════════════════════════════════════════

from tools.dispatcher import _validate_execution_proof  # noqa: E402


def _execution_context_for(contract) -> dict:
    """Same fields core/action_gateway.py::_make_dispatch_executor() builds."""
    return {
        "contract_id": contract.contract_id, "approved_by": contract.canonical_user_id,
        "tool_name": contract.tool_name, "tenant_id": contract.tenant_id,
        "canonical_user_id": contract.canonical_user_id,
        "business_action_fingerprint": contract.business_action_fingerprint, "status": "approved",
    }


def _propose_completed(user_id, fields, *, user_text="", records=None):
    ident = Identity(user_id=user_id, role=Role.OWNER, display_name=user_id, tenant_id="boss_hq",
                     domain_id="general", channel="telegram", external_id=user_id)
    with patch.object(gateway_module, "_fetch_task_link_record", fake_fetch(records or {})):
        result = action_gateway.propose_action(
            tenant_id="boss_hq", canonical_user_id=ident.memory_key, tool_name="airtable_add",
            tool_inputs={"table": Tables.TASKS, "fields": fields}, origin_channel="telegram",
            origin_chat_id=user_id, requires_approval=True, identity=ident, trusted_source="agent",
            user_text=user_text,
            # a stale caller fingerprint_payload (the blank proposal) must not survive completion
            fingerprint_payload={"table": Tables.TASKS, "fields": dict(fields)},
        )
    return ident, (action_gateway.find_contract(result.contract_id) if result.ok else None)


for label, kwargs, expected_title in (
    ("user text", {"fields": {TaskFields.NAME: ""}, "user_text": "צור משימה לקנות חלב"}, "לקנות חלב"),
    ("verified Lead", {"fields": {TaskFields.NAME: " ", TaskFields.LEAD_LINK: [REC_LEAD]},
                       "records": {(Tables.LEADS, REC_LEAD): LEAD_FIELDS}}, "להתקשר בחזרה — דני כהן"),
):
    ident, contract = _propose_completed(f"u-parity-{label}", **kwargs)
    stored = contract.normalized_payload if contract else {}
    chk(f"P1 [{label}] contract stores the Diamond-completed Title (what the owner approves)",
        stored.get("fields", {}).get(TaskFields.NAME) == expected_title)
    chk(f"P2 [{label}] stored fingerprint == fingerprint the dispatcher recomputes from the stored payload",
        contract is not None and _validate_execution_proof(
            "airtable_add", stored, ident, _execution_context_for(contract), "agent") is None)
    with patch.object(dispatcher_module, "airtable_add", return_value=_ok) as write, \
         patch.object(dispatcher_module, "_check_duplicate", return_value=None), \
         patch.object(dispatcher_module._ff, "is_enabled", return_value=False):
        result = dispatcher_module.dispatch_tool(
            "airtable_add", stored, identity=ident, trusted_source="agent",
            execution_context=_execution_context_for(contract),
        )
    chk(f"P3 [{label}] real execution proof passes and Airtable receives exactly the approved fields",
        result.get("ok") is True and write.call_count == 1 and write.call_args.args[1] == stored["fields"])

captured = {}


def _capture_compute(user_chat_id, tool_name, tool_inputs):
    captured["dedup"] = tool_inputs
    raise RuntimeError("captured")


import event_bus  # noqa: E402
with patch.object(event_bus.executed_action_cache, "compute", side_effect=_capture_compute):
    app._queue_approval_detailed(
        "sheets_append", {"sheet_name": "Tasks", "row_data": [""]}, "chat-golden-3", "telegram", "צור משימה לקנות חלב",
    )
chk("P4 Agent path: the dedup fingerprint is computed from the COMPLETED payload (Gate 1 runs first)",
    captured.get("dedup", {}).get("fields", {}).get(TaskFields.NAME) == "לקנות חלב")

# ══════════════════════════════════════════════════
print("\n[N] Gate 2 is validation/normalization only — no Diamond after approval")
# ══════════════════════════════════════════════════

_forbidden = AssertionError("Gate 2 must not run Diamond completion or link resolution")
with patch.object(task_writer, "title_from_user_text", side_effect=_forbidden), \
     patch.object(task_writer, "title_from_lead", side_effect=_forbidden), \
     patch.object(task_writer, "verify_task_links", side_effect=_forbidden), \
     patch.object(gateway_module, "_fetch_task_link_record", side_effect=_forbidden), \
     patch.object(dispatcher_module, "airtable_add", return_value=_ok) as write, \
     patch.object(dispatcher_module, "_check_duplicate", return_value=None):
    blocked = _dispatch("airtable_add", {"table": "Tasks", "fields": {TaskFields.NAME: "", TaskFields.LEAD_LINK: [REC_LEAD]}})
    written = _dispatch("airtable_add", {"table": "Tasks", "fields": {TaskFields.NAME: "לקנות חלב", TaskFields.LEAD_LINK: [REC_LEAD]}})
chk("N1 blank Title at Gate 2 (even with a Lead link) → rejected, nothing derived, nothing written",
    blocked.get("ok") is False and blocked.get("user_message") == ASK_TITLE_MESSAGE)
chk("N2 valid Task at Gate 2 → written with the same fields (links not re-resolved or dropped)",
    written.get("ok") is True and write.call_count == 1
    and write.call_args.args[1] == {TaskFields.NAME: "לקנות חלב", TaskFields.LEAD_LINK: [REC_LEAD]})

print(f"\n{'=' * 60}")
print(f"Task Golden Writer tests: {passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
