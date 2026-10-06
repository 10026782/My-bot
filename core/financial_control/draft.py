"""FCC draft schema on top of the canonical BusinessDraft engine (core/business_draft.py).

No new session engine: drafts are ``BusinessDraft`` objects over FCC-specific
``EntityContract``s (the same ``commercial_completion`` field-contract vocabulary:
required / conditional-required / defaults / validation), persisted by
``session_store.lead_sessions`` (CAS, TTL, identity binding), and frozen by
``BusinessDraft.confirm()`` into an immutable ``ConfirmedSnapshot``.

The snapshot's ``tool_inputs`` is ``{"writes": [{op, table, fields[, record_id]}]}`` — the exact
canonical Airtable writes (owner stamping and cross-owner link checks are applied later by
``core.data_access_policy`` at execution). Nothing downstream re-classifies or re-defaults.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

from airtable_schema import FinEventFields as EF
from airtable_schema import FinGoalFields as GF
from airtable_schema import TaskFields, Tables
from commercial_completion import (
    Condition, EntityContract, InputType, RequiredMode, _f,
)
from core.business_draft import CommercialEntityAdapter, UnsupportedOperationError, register_entity_adapter

FCC_GOAL = "fcc_goal"
FCC_EVENT = "fcc_event"
FCC_FOLLOWUP = "fcc_followup"
FCC_ENTITIES = (FCC_GOAL, FCC_EVENT, FCC_FOLLOWUP)

SNAPSHOT_TOOL = "fcc_writes"        # snapshot envelope name; executors translate to canonical tools
FCC_CHANNEL = "fcc"                 # one draft slot per person, shared by TMA and chat
SOURCE = "fcc_free_text"
FCC_TASK_TOPIC = "כספים"            # existing Tasks.Topic choice (FCC-origin marker with [FCC:<goal>])

CATEGORIES = ("income", "savings", "emergency_fund", "debt", "other")
PERIOD_TYPES = ("monthly", "weekly", "custom")
CALC_METHODS = ("period_sum", "cumulative", "recurring_level")
EVENT_KINDS = ("one_time", "monthly_recurring", "target_change", "direct_cost", "household_expense", "note")

# Safe inference by goal type (user-approved matrix). "other" is never guessed.
INFERENCE: dict[str, dict[str, str]] = {
    "income": {"period_type": "monthly", "calc_method": "period_sum"},
    "savings": {"calc_method": "cumulative"},
    "emergency_fund": {"calc_method": "cumulative"},
    "debt": {"calc_method": "cumulative"},
}

_CUM = (Condition("calc_method", ("cumulative",)),)
_OTHER = (Condition("category", ("other",)),)

FCC_CONTRACTS: dict[str, EntityContract] = {
    FCC_GOAL: EntityContract(FCC_GOAL, (
        _f("title", GF.TITLE, InputType.TEXT, required=RequiredMode.ALWAYS, example="קרן חירום"),
        _f("target_amount", GF.TARGET_AMOUNT, InputType.CURRENCY, required=RequiredMode.ALWAYS,
           validation="positive", example="60000"),
        _f("category", GF.CATEGORY, InputType.SELECT, required=RequiredMode.ALWAYS, choices=CATEGORIES),
        _f("period_type", GF.PERIOD_TYPE, InputType.SELECT, required=RequiredMode.CONDITIONAL,
           when=_OTHER, choices=PERIOD_TYPES),
        _f("calc_method", GF.CALC_METHOD, InputType.SELECT, required=RequiredMode.CONDITIONAL,
           when=_OTHER, choices=CALC_METHODS),
        _f("end_date", GF.END_DATE, InputType.DATE, required=RequiredMode.CONDITIONAL, when=_CUM,
           example="2026-12-31"),
        _f("start_date", GF.START_DATE, InputType.DATE),
    )),
    FCC_EVENT: EntityContract(FCC_EVENT, (
        _f("goal", EF.GOAL, InputType.LINK, required=RequiredMode.ALWAYS),
        _f("kind", EF.KIND, InputType.SELECT, required=RequiredMode.ALWAYS, choices=EVENT_KINDS,
           default="one_time"),
        _f("amount", EF.AMOUNT, InputType.CURRENCY, required=RequiredMode.ALWAYS),
        _f("occurred_at", EF.OCCURRED_AT, InputType.DATE, required=RequiredMode.ALWAYS),
        _f("note", EF.NOTE, InputType.TEXT),
    )),
    FCC_FOLLOWUP: EntityContract(FCC_FOLLOWUP, (
        _f("title", TaskFields.NAME, InputType.TEXT, required=RequiredMode.ALWAYS),
        _f("goal", EF.GOAL, InputType.LINK),
        _f("due_date", TaskFields.DUE_DATE, InputType.DATE),
    )),
}

# ── Presentation (Hebrew): labels, display values, select-answer vocabulary ────────────────────
LABELS = {
    "title": "יעד", "target_amount": "סכום", "category": "קטגוריה", "period_type": "תקופה",
    "calc_method": "שיטת חישוב", "end_date": "תאריך יעד", "start_date": "תאריך התחלה",
    "goal": "יעד", "kind": "סוג", "amount": "סכום", "occurred_at": "תאריך", "note": "הערה", "due_date": "לתאריך",
}
VALUE_LABELS = {
    "category": {"income": "הכנסה", "savings": "חיסכון", "emergency_fund": "קרן חירום", "debt": "חוב", "other": "אחר"},
    "period_type": {"monthly": "חודשי", "weekly": "שבועי", "custom": "מותאם"},
    "calc_method": {"period_sum": "סכום בתקופה", "cumulative": "מצטבר", "recurring_level": "שינוי קבוע בחודש"},
    "kind": {"one_time": "חד-פעמי", "monthly_recurring": "חודשי קבוע", "target_change": "שינוי יעד", "direct_cost": "הוצאה ישירה", "household_expense": "הוצאה ביתית", "note": "הערה"},
}
# Closed answer vocabulary of the options we present (equivalent to buttons) — not NL parsing.
ANSWER_VOCAB = {f: {label: key for key, label in labels.items()} for f, labels in VALUE_LABELS.items()}
ANSWER_VOCAB["category"]["קרן חירום זמינה"] = "emergency_fund"


def display_value(field: str, value: Any) -> str:
    if field in VALUE_LABELS:
        return VALUE_LABELS[field].get(value, str(value))
    if field in ("target_amount", "amount") and isinstance(value, (int, float)):
        return f"₪{value:,.0f}"
    if field in ("end_date", "start_date", "occurred_at", "due_date") and isinstance(value, str) and len(value) >= 10:
        y, m, d = value[:10].split("-")
        return f"{d}/{m}/{y}"
    return str(value)


def prompt_for(entity: str, field: str, fields: Mapping[str, Any], goal_title: str = "") -> str:
    title = fields.get("title") or goal_title
    if field == "title":
        return "איך לקרוא ליעד?"
    if field == "target_amount":
        return f"מה סכום היעד{' ל' + title if title else ''}?"
    if field == "category":
        return "איזה סוג יעד זה? הכנסה / חיסכון / קרן חירום / חוב / אחר"
    if field == "period_type":
        return "באיזו תקופה נמדד היעד? חודשי / שבועי / מותאם"
    if field == "calc_method":
        return "איך למדוד התקדמות? סכום בתקופה / מצטבר מול יעד / שינוי קבוע בחודש"
    if field == "end_date":
        target = fields.get("target_amount")
        goal = f" ל-{display_value('target_amount', target)}" if target else ""
        return f"עד מתי אתה רוצה להגיע{goal}?"
    if field == "amount":
        return f"כמה לרשום{' ביעד ' + goal_title if goal_title else ''}?"
    if field == "goal":
        return "לאיזה יעד?"
    return f"מה {LABELS.get(field, field)}?"


def render_review(entity: str, fields: Mapping[str, Any], *, goal_title: str = "", operation: str = "CREATE",
                  changed: Mapping[str, Any] | None = None, inferred: tuple[str, ...] = ()) -> str:
    """Full final business payload, shown before confirmation."""
    order = [f.field_name for f in FCC_CONTRACTS[entity].fields]
    lines: list[str] = []
    head = {FCC_GOAL: "יעד חדש" if operation == "CREATE" else "עדכון יעד",
            FCC_EVENT: "רישום התקדמות", FCC_FOLLOWUP: "משימת המשך"}[entity]
    lines.append(f"📋 {head}")
    if entity == FCC_EVENT and goal_title:
        lines.append(f"• יעד: {goal_title}")
    for name in order:
        if name == "goal" and entity == FCC_EVENT:
            continue
        value = fields.get(name)
        if value in (None, ""):
            continue
        mark = " (הוסק)" if name in inferred else ""
        lines.append(f"• {LABELS.get(name, name)}: {display_value(name, value)}{mark}")
    if operation == "UPDATE" and changed:
        lines.append("שינויים: " + ", ".join(LABELS.get(k, k) for k in changed))
    lines.append("")
    lines.append("אשר ורשום / ערוך / בטל")
    return "\n".join(lines)


# ── Canonical writes (the Golden Writer's input) ───────────────────────────────────────────────
def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().casefold())


def event_idempotency_key(profile_id: str, goal_id: str, kind: str, amount, day: str, raw_text: str) -> str:
    raw = json.dumps([profile_id, goal_id, kind, amount, day, _norm(raw_text)], ensure_ascii=False)
    return "fcc-" + hashlib.sha256(raw.encode()).hexdigest()[:24]


def _event_write(values: Mapping[str, Any], ctx: Mapping[str, Any], raw_text: str) -> dict:
    key = event_idempotency_key(ctx.get("profile_id", ""), values["goal"], values["kind"],
                                values["amount"], values["occurred_at"], raw_text)
    fields = {
        EF.GOAL: [values["goal"]], EF.KIND: values["kind"], EF.AMOUNT: values["amount"],
        EF.OCCURRED_AT: values["occurred_at"], EF.RECORDED_BY: ctx.get("user_id", ""),
        EF.SOURCE: SOURCE, EF.RAW_TEXT: (raw_text or "")[:2000], EF.IDEMPOTENCY_KEY: key,
    }
    if values.get("note"):
        fields[EF.NOTE] = values["note"]
    return {"op": "post", "table": Tables.FIN_EVENTS, "fields": fields,
            "audit_action": "fcc_event", "audit_details": key}


class FccEntityAdapter(CommercialEntityAdapter):
    """Entity adapter for the FCC contracts. Canonical 'tool' = the frozen ``fcc_writes`` envelope."""

    def __init__(self) -> None:
        super().__init__(FCC_CONTRACTS)

    def get_update_editable_fields(self, entity_type: str) -> frozenset[str]:
        if entity_type != FCC_GOAL:
            return frozenset()
        return frozenset(f.field_name for f in FCC_CONTRACTS[FCC_GOAL].fields)

    def get_canonical_create_tool(self, entity_type: str) -> str | None:
        return SNAPSHOT_TOOL if entity_type in FCC_CONTRACTS else None

    def get_canonical_update_tool(self, entity_type: str) -> str | None:
        return SNAPSHOT_TOOL if entity_type == FCC_GOAL else None

    def build_create_payload(self, writer) -> dict[str, Any]:
        values = writer.resolved_values()
        ctx = dict(writer.identity)
        raw = str(writer.source_context.get("raw_text") or "")
        entity = writer.target_entity
        if entity == FCC_GOAL:
            fields = {GF.STATUS: "active"}
            for name, spec in (("title", GF.TITLE), ("target_amount", GF.TARGET_AMOUNT),
                               ("category", GF.CATEGORY), ("period_type", GF.PERIOD_TYPE),
                               ("calc_method", GF.CALC_METHOD), ("end_date", GF.END_DATE),
                               ("start_date", GF.START_DATE)):
                if values.get(name) not in (None, ""):
                    fields[spec] = values[name]
            write = {"op": "post", "table": Tables.FIN_GOALS, "fields": fields,
                     "audit_action": "fcc_goal_create", "audit_details": str(values.get("title", ""))[:80]}
            return {"writes": [write]}
        if entity == FCC_EVENT:
            return {"writes": [_event_write(values, ctx, raw)]}
        if entity == FCC_FOLLOWUP:
            tag = f"[FCC:{values.get('goal') or 'none'}]"
            fields = {TaskFields.NAME: values["title"], TaskFields.STATUS: "ממתין",
                      TaskFields.DESCRIPTION: f"{tag} {raw[:300]}".strip(),
                      TaskFields.OWNER: [ctx["profile_id"]], TaskFields.TOPIC: FCC_TASK_TOPIC}
            if values.get("due_date"):
                fields[TaskFields.DUE_DATE] = values["due_date"]
            return {"writes": [{"op": "post", "table": Tables.TASKS, "fields": fields,
                                "audit_action": "fcc_followup", "audit_details": tag}]}
        raise UnsupportedOperationError(f"unknown FCC entity {entity!r}")

    def build_update_payload(self, writer, original_fields) -> dict[str, Any]:
        """Partial update: ONLY changed fields. A target change is an append-only event
        (history is never rewritten); everything else patches the goal. Unmentioned
        fields are never touched."""
        if writer.target_entity != FCC_GOAL:
            raise UnsupportedOperationError(f"{writer.target_entity} has no UPDATE")
        values = dict(writer.current_values)
        changed = {k: v for k, v in values.items() if v != original_fields.get(k)}
        if not changed:
            return {}
        ctx = dict(writer.identity)
        raw = str(writer.source_context.get("raw_text") or "")
        record_id = str(writer.source_context.get("record_id") or "")
        writes: list[dict] = []
        patch = {}
        for name, spec in (("title", GF.TITLE), ("category", GF.CATEGORY), ("period_type", GF.PERIOD_TYPE),
                           ("calc_method", GF.CALC_METHOD), ("end_date", GF.END_DATE),
                           ("start_date", GF.START_DATE)):
            if name in changed:
                patch[spec] = changed[name]
        if patch:
            writes.append({"op": "patch", "table": Tables.FIN_GOALS, "record_id": record_id, "fields": patch,
                           "audit_action": "fcc_goal_update", "audit_details": record_id})
        if "target_amount" in changed:
            writes.append(_event_write({"goal": record_id, "kind": "target_change",
                                        "amount": changed["target_amount"],
                                        "occurred_at": str(writer.source_context.get("today") or "")},
                                       ctx, raw))
        return {"writes": writes}


ADAPTER = FccEntityAdapter()
for _entity in FCC_ENTITIES:
    register_entity_adapter(_entity, ADAPTER)
