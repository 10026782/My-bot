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
from airtable_schema import AssetFields as AF
from airtable_schema import LoanFields as LF
from airtable_schema import FinGoalFields as GF
from airtable_schema import RecObFields as RF
from airtable_schema import TaskFields, Tables
from commercial_completion import (
    Condition, EntityContract, InputType, RequiredMode, _f,
)
from core.business_draft import CommercialEntityAdapter, UnsupportedOperationError, register_entity_adapter

FCC_GOAL = "fcc_goal"
FCC_EVENT = "fcc_event"
FCC_FOLLOWUP = "fcc_followup"
FCC_OBLIGATION = "fcc_obligation"   # Recurring Obligations: a COMMITMENT (never an actual-expense ledger row)
FCC_LOAN_CLOSE = "fcc_loan_close"   # closing a loan: Loans.Payment Status = Paid Off + one progress event on the debt goal
FCC_LOAN_BALANCE = "fcc_loan_balance"   # one field of an existing loan: Outstanding Principal for Early Closure (the "יתרה" the screen shows)
FCC_LOAN_PAYMENT = "fcc_loan_payment"   # one field of an existing loan: Current Monthly Payment
FCC_LOAN_NEW = "fcc_loan_new"           # a new loan (owner-scoped create)
FCC_ASSET_VALUE = "fcc_asset_value"        # one field of an existing asset: Current Value
FCC_ASSET_MORTGAGE = "fcc_asset_mortgage"  # one field of an existing asset: Mortgage Balance (on the asset itself)
FCC_ASSET_STEP = "fcc_asset_step"          # Next Step (free text) + optional Next Step Owner (live select)
FCC_ASSET_SOLD = "fcc_asset_sold"          # TRANSITION: Status=נמכר + Sale Date + Sale Amount in ONE atomic patch (review + approval)
ASSET_SOLD_STATUS = "נמכר"                 # live Assets.Status choice
FCC_ENTITIES = (FCC_GOAL, FCC_EVENT, FCC_FOLLOWUP, FCC_OBLIGATION, FCC_LOAN_CLOSE, FCC_LOAN_BALANCE, FCC_LOAN_PAYMENT, FCC_LOAN_NEW,
                FCC_ASSET_VALUE, FCC_ASSET_MORTGAGE, FCC_ASSET_STEP, FCC_ASSET_SOLD)
STEP_OWNERS = ("אליהו", "אהרן", "אורי", "משפטי", "—")   # the LIVE Assets."Next Step Owner" choices (read 08/10/2026) — never invented
LOAN_TYPES = ("private", "business", "mortgage")
LOAN_TYPE_STORED = {"private": "פרטית", "business": "עסקית", "mortgage": "משכנתא"}   # the live Loans."Loan Type" choices
LOAN_PAID_OFF = "Paid Off"          # existing Loans.Payment Status choice

# Intent registry (SSOT for the contextual composer chips / card actions). A chip only names an intent (+ optionally the
# record it is about); it pre-fills `kind` and nothing else, and the SAME BusinessDraft completion flow asks what is missing.
# target: the kind of record the intent is about ("goal" | "loan" | None). target_required: it cannot start without one.
INTENTS: dict[str, dict] = {
    "monthly.income":            {"tab": "monthly", "entity": "fcc_event", "kind": "one_time", "target": "goal", "goal_filter": "income"},
    "monthly.household_expense": {"tab": "monthly", "entity": "fcc_event", "kind": "household_expense", "target": "goal", "goal_hint": "הוצאות בית"},
    "monthly.direct_cost":       {"tab": "monthly", "entity": "fcc_event", "kind": "direct_cost", "target": "goal", "goal_filter": "income"},
    "monthly.goal_update":       {"tab": "monthly", "entity": "fcc_goal", "target": "goal", "target_required": True},
    "monthly.obligation":        {"tab": "monthly", "entity": "fcc_obligation"},
    "loan.close":                {"tab": "loans", "entity": "fcc_loan_close", "target": "loan", "target_required": True, "transition": True},
    "loan.update_balance":       {"tab": "loans", "entity": "fcc_loan_balance", "target": "loan", "target_required": True},
    "loan.update_payment":       {"tab": "loans", "entity": "fcc_loan_payment", "target": "loan", "target_required": True},
    "loan.create":               {"tab": "loans", "entity": "fcc_loan_new"},
    "asset.update_value":        {"tab": "assets", "entity": "fcc_asset_value", "target": "asset", "target_required": True},
    "asset.update_mortgage":     {"tab": "assets", "entity": "fcc_asset_mortgage", "target": "asset", "target_required": True},
    "asset.next_step":           {"tab": "assets", "entity": "fcc_asset_step", "target": "asset", "target_required": True},
    "asset.mark_sold":           {"tab": "assets", "entity": "fcc_asset_sold", "target": "asset", "target_required": True, "transition": True},
}

SNAPSHOT_TOOL = "fcc_writes"        # snapshot envelope name; executors translate to canonical tools
FCC_CHANNEL = "fcc"                 # one draft slot per person, shared by TMA and chat
SOURCE = "fcc_free_text"
FCC_TASK_TOPIC = "כספים"            # existing Tasks.Topic choice (FCC-origin marker with [FCC:<goal>])

CATEGORIES = ("income", "savings", "emergency_fund", "debt", "other")
PERIOD_TYPES = ("monthly", "weekly", "custom")
CALC_METHODS = ("period_sum", "cumulative", "recurring_level")
EVENT_KINDS = ("one_time", "monthly_recurring", "target_change", "direct_cost", "household_expense", "note")

OB_SCOPES = ("household", "business", "personal")
OB_TYPES = ("subscription", "standing_order", "service", "loan_payment", "other")
OB_FREQUENCIES = ("monthly", "quarterly", "yearly", "custom")
OB_ESSENTIALITY = ("essential", "useful", "optional", "review")
OB_REVIEW = ("keep", "reduce", "cancel", "negotiate", "review")
OB_STATUS = ("active", "inactive")      # inactive = actually cancelled/ended: leaves the monthly total

# Safe inference by goal type (user-approved matrix). "other" is never guessed.
INFERENCE: dict[str, dict[str, str]] = {
    "income": {"period_type": "monthly", "calc_method": "period_sum"},
    "savings": {"period_type": "monthly", "calc_method": "recurring_level"},   # a standing monthly allocation (like a standing order) vs a target; never resets. A one-time pot is an emergency fund
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
    FCC_OBLIGATION: EntityContract(FCC_OBLIGATION, (
        _f("name", RF.NAME, InputType.TEXT, required=RequiredMode.ALWAYS, example="נטפליקס"),
        _f("amount", RF.AMOUNT, InputType.CURRENCY, required=RequiredMode.ALWAYS, validation="positive", example="70"),
        _f("scope", RF.SCOPE, InputType.SELECT, required=RequiredMode.ALWAYS, choices=OB_SCOPES),
        _f("frequency", RF.FREQUENCY, InputType.SELECT, required=RequiredMode.ALWAYS, choices=OB_FREQUENCIES,
           default="monthly"),
        _f("review_status", RF.REVIEW_STATUS, InputType.SELECT, choices=OB_REVIEW),
        _f("status", RF.ACTIVE, InputType.SELECT, choices=OB_STATUS),
        _f("saving", RF.POTENTIAL_SAVING, InputType.CURRENCY, validation="non_negative"),
        _f("obligation_type", RF.TYPE, InputType.SELECT, choices=OB_TYPES),
        _f("essentiality", RF.ESSENTIALITY, InputType.SELECT, choices=OB_ESSENTIALITY),
        _f("vendor", RF.VENDOR, InputType.TEXT),
        _f("next_charge_date", RF.NEXT_CHARGE, InputType.DATE, example="2026-11-01"),
    )),
    # The loan itself (record id) and the debt goal live in the draft's source_context, not in editable fields:
    # an edit can change the amount actually paid or the date, never WHICH loan is being closed.
    FCC_LOAN_CLOSE: EntityContract(FCC_LOAN_CLOSE, (
        _f("amount", EF.AMOUNT, InputType.CURRENCY, required=RequiredMode.ALWAYS, validation="positive"),
        _f("occurred_at", EF.OCCURRED_AT, InputType.DATE, required=RequiredMode.ALWAYS),
        _f("note", EF.NOTE, InputType.TEXT),
    )),
    # One field of an EXISTING loan: the loan itself lives in source_context (never editable), so an edit can change the
    # value, never WHICH loan is updated. Exactly one field is written — no other loan number is touched.
    FCC_LOAN_BALANCE: EntityContract(FCC_LOAN_BALANCE, (
        _f("balance", LF.EARLY_CLOSURE, InputType.CURRENCY, required=RequiredMode.ALWAYS, validation="non_negative"),
    )),
    FCC_LOAN_PAYMENT: EntityContract(FCC_LOAN_PAYMENT, (
        _f("payment", LF.MONTHLY_PAYMENT, InputType.CURRENCY, required=RequiredMode.ALWAYS, validation="positive"),
    )),
    FCC_LOAN_NEW: EntityContract(FCC_LOAN_NEW, (
        _f("name", LF.NAME, InputType.TEXT, required=RequiredMode.ALWAYS),
        _f("loan_type", LF.LOAN_TYPE, InputType.SELECT, required=RequiredMode.ALWAYS, choices=LOAN_TYPES),
        _f("balance", LF.EARLY_CLOSURE, InputType.CURRENCY, required=RequiredMode.ALWAYS, validation="non_negative"),
        _f("payment", LF.MONTHLY_PAYMENT, InputType.CURRENCY, required=RequiredMode.ALWAYS, validation="positive"),
        _f("rate", LF.INTEREST_RATE, InputType.PERCENT, required=RequiredMode.ALWAYS),
        _f("lender", LF.LENDER, InputType.TEXT),
        _f("original", LF.AMOUNT, InputType.CURRENCY, validation="positive"),
        _f("payments_left", LF.PAYMENTS_LEFT, InputType.NUMBER, validation="non_negative_integer"),
    )),
    # Assets: the asset itself lives in source_context (never editable). Exactly the named field(s) are written.
    FCC_ASSET_VALUE: EntityContract(FCC_ASSET_VALUE, (
        _f("value", AF.VALUE, InputType.CURRENCY, required=RequiredMode.ALWAYS, validation="non_negative"),
    )),
    FCC_ASSET_MORTGAGE: EntityContract(FCC_ASSET_MORTGAGE, (
        _f("mortgage", AF.MORTGAGE, InputType.CURRENCY, required=RequiredMode.ALWAYS, validation="non_negative"),
    )),
    FCC_ASSET_STEP: EntityContract(FCC_ASSET_STEP, (
        _f("step", AF.NEXT_STEP, InputType.TEXT, required=RequiredMode.ALWAYS),
        _f("step_owner", AF.NEXT_STEP_OWNER, InputType.SELECT, choices=STEP_OWNERS),
    )),
    # Selling an asset: BOTH values are required (no half-recorded sale). The asset lives in source_context, never editable.
    FCC_ASSET_SOLD: EntityContract(FCC_ASSET_SOLD, (
        _f("sale_date", AF.SALE_DATE, InputType.DATE, required=RequiredMode.ALWAYS),
        _f("sale_amount", AF.SALE_AMOUNT, InputType.CURRENCY, required=RequiredMode.ALWAYS, validation="positive"),
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
    "name": "התחייבות", "scope": "שייכות", "frequency": "תדירות", "review_status": "החלטה", "saving": "חיסכון חודשי פוטנציאלי",
    "obligation_type": "סוג", "essentiality": "חשיבות", "vendor": "ספק", "next_charge_date": "חיוב הבא", "status": "מצב",
    "balance": "יתרה לסגירה מוקדמת", "payment": "החזר חודשי", "loan_type": "סוג", "rate": "ריבית שנתית", "lender": "מלווה",
    "original": "סכום מקורי", "payments_left": "תשלומים שנותרו",
    "sale_date": "תאריך מכירה", "sale_amount": "מחיר מכירה (100%)", "value": "שווי נוכחי", "mortgage": "יתרת משכנתא", "step": "פעולה הבאה", "step_owner": "אחראי",
}
LABELS_BY_ENTITY = {FCC_LOAN_NEW: {"name": "שם ההלוואה"}}


def label(entity: str, field: str) -> str:
    return LABELS_BY_ENTITY.get(entity, {}).get(field) or LABELS.get(field, field)
VALUE_LABELS = {
    "category": {"income": "הכנסה", "savings": "חיסכון חודשי", "emergency_fund": "קרן חירום", "debt": "חוב", "other": "אחר"},
    "period_type": {"monthly": "חודשי", "weekly": "שבועי", "custom": "מותאם"},
    "calc_method": {"period_sum": "סכום בתקופה", "cumulative": "מצטבר", "recurring_level": "שינוי קבוע בחודש"},
    "status": {"active": "פעיל", "inactive": "לא פעיל (בוטל בפועל)"},
    "scope": {"household": "ביתי", "business": "עסקי", "personal": "אישי"},
    "loan_type": {"private": "פרטית", "business": "עסקית", "mortgage": "משכנתא"},
    "step_owner": {o: o for o in STEP_OWNERS},
    "frequency": {"monthly": "חודשי", "quarterly": "רבעוני", "yearly": "שנתי", "custom": "מותאם"},
    "review_status": {"keep": "להשאיר", "reduce": "להקטין", "cancel": "לבטל", "negotiate": "לנהל משא ומתן", "review": "לבדוק"},
    "obligation_type": {"subscription": "מנוי", "standing_order": "הוראת קבע", "service": "שירות",
                        "loan_payment": "החזר הלוואה", "other": "אחר"},
    "essentiality": {"essential": "הכרחי", "useful": "שימושי", "optional": "אופציונלי", "review": "לבדיקה"},
    "kind": {"one_time": "חד-פעמי", "monthly_recurring": "חודשי קבוע", "target_change": "שינוי יעד", "direct_cost": "הוצאה ישירה", "household_expense": "הוצאה ביתית", "note": "הערה"},
}
# Closed answer vocabulary of the options we present (equivalent to buttons) — not NL parsing.
ANSWER_VOCAB = {f: {label: key for key, label in labels.items()} for f, labels in VALUE_LABELS.items()}
ANSWER_VOCAB["category"]["קרן חירום זמינה"] = "emergency_fund"
ANSWER_VOCAB["category"]["חיסכון"] = "savings"


def display_value(field: str, value: Any) -> str:
    if field in VALUE_LABELS:
        return VALUE_LABELS[field].get(value, str(value))
    if field == "rate" and isinstance(value, (int, float)):
        return f"{value:g}%"
    if field in ("target_amount", "amount", "saving", "balance", "payment", "original", "value", "mortgage", "sale_amount") and isinstance(value, (int, float)):
        digits = 2 if round(float(value), 2) != round(float(value)) else 0       # agorot are shown when they exist (what is stored = what is reviewed)
        return f"-₪{abs(value):,.{digits}f}" if value < 0 else f"₪{value:,.{digits}f}"
    if field in ("end_date", "start_date", "occurred_at", "due_date", "next_charge_date", "sale_date") \
            and isinstance(value, str) and len(value) >= 10:
        y, m, d = value[:10].split("-")
        return f"{d}/{m}/{y}"
    return str(value)


INCOME_KINDS = ("one_time", "monthly_recurring", "direct_cost")   # events booked against an income SOURCE (not a goal to reach)


def record_noun(entity: str, fields: Mapping[str, Any]) -> str:
    """What the screen calls the record an event is booked on: income events -> a "מקור", household spending -> a "סעיף",
    anything else (progress on a savings / debt goal) stays a "יעד"."""
    if entity != FCC_EVENT:
        return "יעד"
    kind = fields.get("kind")
    return "מקור" if kind in INCOME_KINDS else "סעיף" if kind == "household_expense" else "יעד"


def prompt_for(entity: str, field: str, fields: Mapping[str, Any], goal_title: str = "") -> str:
    title = fields.get("title") or goal_title
    if field == "title":
        return "איך לקרוא ליעד?"
    if field == "target_amount":
        return f"מה סכום היעד{' ל' + title if title else ''}?"
    if field == "category":
        return "איזה סוג יעד זה? הכנסה / חיסכון (הפרשה חודשית) / קרן חירום (סכום חד-פעמי) / חוב / אחר"
    if field == "period_type":
        return "באיזו תקופה נמדד היעד? חודשי / שבועי / מותאם"
    if field == "calc_method":
        return "איך למדוד התקדמות? סכום בתקופה / מצטבר מול יעד / שינוי קבוע בחודש"
    if field == "end_date":
        target = fields.get("target_amount")
        goal = f" ל-{display_value('target_amount', target)}" if target else ""
        return f"עד מתי אתה רוצה להגיע{goal}?"
    if entity == FCC_LOAN_CLOSE and field == "amount":
        return f"כמה שילמת בפועל לסגירת {goal_title or 'ההלוואה'}?"
    if entity == FCC_LOAN_BALANCE:
        return f"מה היתרה לסגירה מוקדמת של {goal_title or 'ההלוואה'}?"
    if entity == FCC_LOAN_PAYMENT:
        return f"מה ההחזר החודשי של {goal_title or 'ההלוואה'}?"
    if entity == FCC_ASSET_VALUE:
        return f"מה השווי הנוכחי של {goal_title or 'הנכס'}?"
    if entity == FCC_ASSET_MORTGAGE:
        return f"מה יתרת המשכנתא של {goal_title or 'הנכס'}? (0 אם אין)"
    if entity == FCC_ASSET_STEP:
        return f"מה הפעולה הבאה עבור {goal_title or 'הנכס'}?"
    if entity == FCC_ASSET_SOLD:
        return (f"באיזה מחיר נמכר {goal_title or 'הנכס'}? (מחיר העסקה המלא של 100% מהנכס, לפני עלויות ומיסים)"
                if field == "sale_amount" else f"מתי נמכר {goal_title or 'הנכס'}?")
    if entity == FCC_LOAN_NEW:
        return {"name": "איך לקרוא להלוואה? (למשל: בנק הפועלים)", "loan_type": "איזה סוג? פרטית / עסקית / משכנתא",
                "balance": "מה היתרה לסגירה מוקדמת?", "payment": "מה ההחזר החודשי?",
                "rate": "מה הריבית השנתית (באחוזים)?"}.get(field, f"מה {label(entity, field)}?")
    if entity == FCC_OBLIGATION:
        if field == "name":
            return "איך לקרוא להתחייבות? (למשל: נטפליקס)"
        if field == "amount":
            return f"כמה החיוב{' של ' + str(fields.get('name')) if fields.get('name') else ''}?"
        if field == "scope":
            return "שייך לבית, לעסק או אישי? ביתי / עסקי / אישי"
        if field == "frequency":
            return "באיזו תדירות? חודשי / רבעוני / שנתי / מותאם"
    noun = record_noun(entity, fields)
    if field == "amount":
        note = str(fields.get("note") or "")
        if noun == "מקור" and note.startswith("מקור: "):         # "מקור אחר": speak of the NAMED source, not the total goal behind it
            return f"כמה לרשום ממקור {note[len('מקור: '):]}?"
        return f"כמה לרשום{' ב' + noun + ' ' + goal_title if goal_title else ''}?"
    if field == "goal":
        return {"מקור": "מאיזה מקור?", "סעיף": "באיזה סעיף?"}.get(noun, "לאיזה יעד?")
    return f"מה {LABELS.get(field, field)}?"


def render_review(entity: str, fields: Mapping[str, Any], *, goal_title: str = "", operation: str = "CREATE",
                  changed: Mapping[str, Any] | None = None, inferred: tuple[str, ...] = (), note: str = "") -> str:
    """Full final business payload, shown before confirmation."""
    order = [f.field_name for f in FCC_CONTRACTS[entity].fields]
    lines: list[str] = []
    head = {FCC_GOAL: "יעד חדש" if operation == "CREATE" else "עדכון יעד",
            FCC_OBLIGATION: "התחייבות חדשה" if operation == "CREATE" else "עדכון התחייבות",
            FCC_EVENT: "רישום התקדמות", FCC_FOLLOWUP: "משימת המשך", FCC_LOAN_CLOSE: "סגירת הלוואה",
            FCC_LOAN_BALANCE: "עדכון יתרת הלוואה", FCC_LOAN_PAYMENT: "עדכון החזר חודשי", FCC_LOAN_NEW: "הלוואה חדשה",
            FCC_ASSET_VALUE: "עדכון שווי נכס", FCC_ASSET_MORTGAGE: "עדכון משכנתא בנכס", FCC_ASSET_STEP: "פעולה הבאה בנכס", FCC_ASSET_SOLD: "סימון נכס כנמכר"}[entity]
    lines.append(f"📋 {head}")
    if note and entity != FCC_ASSET_SOLD:
        lines.append(note)
    if entity == FCC_EVENT and goal_title:
        lines.append(f"• {record_noun(entity, fields)}: {goal_title}")
    if entity in (FCC_LOAN_CLOSE, FCC_LOAN_BALANCE, FCC_LOAN_PAYMENT) and goal_title:
        lines.append(f"• הלוואה: {goal_title}")
    if entity in (FCC_ASSET_VALUE, FCC_ASSET_MORTGAGE, FCC_ASSET_STEP, FCC_ASSET_SOLD) and goal_title:
        lines.append(f"• נכס: {goal_title}")
    for name in order:
        if name == "goal" and entity == FCC_EVENT:
            continue
        value = fields.get(name)
        if value in (None, ""):
            continue
        mark = " (הוסק)" if name in inferred else ""
        lines.append(f"• {label(entity, name)}: {display_value(name, value)}{mark}")
    if entity == FCC_LOAN_CLOSE:
        lines.append(f"ההלוואה תסומן {LOAN_PAID_OFF} ותצא מהחובות הפעילים.")
    if entity in (FCC_LOAN_BALANCE, FCC_LOAN_PAYMENT):
        lines.append("יתעדכן שדה אחד בלבד; שאר נתוני ההלוואה לא ייגעו.")
    if entity == FCC_LOAN_NEW:
        lines.append("תיווצר הלוואה פעילה בבעלותך.")
    if entity in (FCC_ASSET_VALUE, FCC_ASSET_MORTGAGE):
        lines.append("יתעדכן שדה אחד בלבד; שאר נתוני הנכס לא ייגעו.")
    if entity == FCC_ASSET_MORTGAGE:
        lines.append("זו יתרה הרשומה על הנכס עצמו — היא לא מסתנכרנת להלוואות המקושרות ולא נוספת אליהן.")
    if entity == FCC_ASSET_STEP:
        lines.append("הפעולה הבאה הקיימת בנכס תוחלף בטקסט החדש.")
    if entity == FCC_ASSET_SOLD:
        if note:
            lines.append(note)                       # my share + what stays untouched, right under the sale values
        lines.append(f"⚠️ הנכס יסומן \"{ASSET_SOLD_STATUS}\" ויצא מסיכומי הנכסים הפעילים. תמורת המכירה לא נרשמת כנכס/מזומן באף מקום.")
    if entity == FCC_OBLIGATION and fields.get("status") == "inactive":
        lines.append("ההתחייבות תסומן כלא פעילה ותצא מהסכום החודשי.")
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


def _ob_value(name: str, value):
    """``status`` is a select in the draft but a checkbox in storage."""
    return value == "active" if name == "status" else value


def loan_close_writes(values: Mapping[str, Any], ctx: Mapping[str, Any], source: Mapping[str, Any]) -> list[dict]:
    """Closing a loan = ONE confirmation, two canonical writes, nothing else: the loan's Payment Status becomes
    Paid Off (the only thing the loans read model treats as closed) and — when the owner has a debt goal — one
    progress event with the amount actually paid. The event key is derived from the loan, so a retry or a second tap
    can never log the same closing twice. No loan balance/payment field is rewritten."""
    loan_id = str(source.get("record_id") or "")
    if not loan_id:
        raise UnsupportedOperationError("loan close without a loan record")
    writes = [{"op": "patch", "table": Tables.LOANS, "record_id": loan_id, "fields": {LF.STATUS: LOAN_PAID_OFF},
               "audit_action": "fcc_loan_close", "audit_details": loan_id}]
    goal_id = str(source.get("debt_goal_id") or "")
    if goal_id:
        name = str(source.get("loan_name") or "")
        event = _event_write({"goal": goal_id, "kind": "one_time", "amount": values["amount"],
                              "occurred_at": values["occurred_at"],
                              "note": (f"סגירת הלוואה: {name}" + (f" — {values['note']}" if values.get("note") else "")).strip()},
                             ctx, f"close_loan:{loan_id}")
        event["audit_action"] = "fcc_loan_close_event"
        writes.append(event)
    return writes


# entity -> (table, draft field, storage field, audit action): the storage field is fixed by the entity, never by user text
_FIELD_UPDATES = {
    FCC_LOAN_BALANCE: (Tables.LOANS, "balance", LF.EARLY_CLOSURE, "fcc_loan_update"),
    FCC_LOAN_PAYMENT: (Tables.LOANS, "payment", LF.MONTHLY_PAYMENT, "fcc_loan_update"),
    FCC_ASSET_VALUE: ("Assets", "value", AF.VALUE, "fcc_asset_update"),
    FCC_ASSET_MORTGAGE: ("Assets", "mortgage", AF.MORTGAGE, "fcc_asset_update"),
}


def field_update_writes(entity: str, values: Mapping[str, Any], source: Mapping[str, Any]) -> list[dict]:
    """ONE patch, ONE field of the chosen record (loan or asset)."""
    record_id = str(source.get("record_id") or "")
    if not record_id:
        raise UnsupportedOperationError(f"{entity} without a record")
    table, name, field, audit = _FIELD_UPDATES[entity]
    return [{"op": "patch", "table": table, "record_id": record_id, "fields": {field: values[name]},
             "audit_action": audit, "audit_details": f"{record_id}:{name}"}]


def asset_sold_writes(values: Mapping[str, Any], source: Mapping[str, Any]) -> list[dict]:
    """ONE atomic patch: Status + Sale Date + Sale Amount of the chosen asset. Nothing else is written — no loan is closed,
    no mortgage is reset, no proceeds record is created."""
    record_id = str(source.get("record_id") or "")
    if not record_id:
        raise UnsupportedOperationError("asset sale without an asset record")
    return [{"op": "patch", "table": "Assets", "record_id": record_id,
             "fields": {AF.STATUS: ASSET_SOLD_STATUS, AF.SALE_DATE: values["sale_date"], AF.SALE_AMOUNT: values["sale_amount"]},
             "audit_action": "fcc_asset_sold", "audit_details": record_id}]


def asset_step_writes(values: Mapping[str, Any], source: Mapping[str, Any]) -> list[dict]:
    """Next Step (free text) and — only when the owner chose one — Next Step Owner, in ONE patch of the chosen asset."""
    record_id = str(source.get("record_id") or "")
    if not record_id:
        raise UnsupportedOperationError("asset next step without an asset record")
    fields = {AF.NEXT_STEP: str(values["step"]).strip()}
    if values.get("step_owner") not in (None, ""):
        fields[AF.NEXT_STEP_OWNER] = values["step_owner"]
    return [{"op": "patch", "table": "Assets", "record_id": record_id, "fields": fields,
             "audit_action": "fcc_asset_step", "audit_details": record_id}]


def loan_new_write(values: Mapping[str, Any]) -> dict:
    fields: dict[str, Any] = {LF.ACTIVE: True}
    for name, spec in (("name", LF.NAME), ("balance", LF.EARLY_CLOSURE), ("payment", LF.MONTHLY_PAYMENT), ("rate", LF.INTEREST_RATE),
                       ("lender", LF.LENDER), ("original", LF.AMOUNT), ("payments_left", LF.PAYMENTS_LEFT)):
        if values.get(name) not in (None, ""):
            fields[spec] = values[name]
    fields[LF.LOAN_TYPE] = LOAN_TYPE_STORED[values["loan_type"]]
    return {"op": "post", "table": Tables.LOANS, "fields": fields,
            "audit_action": "fcc_loan_create", "audit_details": str(values.get("name", ""))[:80]}


_OB_FIELDS = (("status", RF.ACTIVE), ("name", RF.NAME), ("amount", RF.AMOUNT), ("scope", RF.SCOPE), ("frequency", RF.FREQUENCY),
              ("review_status", RF.REVIEW_STATUS), ("saving", RF.POTENTIAL_SAVING), ("obligation_type", RF.TYPE),
              ("essentiality", RF.ESSENTIALITY), ("vendor", RF.VENDOR), ("next_charge_date", RF.NEXT_CHARGE))


class FccEntityAdapter(CommercialEntityAdapter):
    """Entity adapter for the FCC contracts. Canonical 'tool' = the frozen ``fcc_writes`` envelope."""

    def __init__(self) -> None:
        super().__init__(FCC_CONTRACTS)

    def get_update_editable_fields(self, entity_type: str) -> frozenset[str]:
        if entity_type not in (FCC_GOAL, FCC_OBLIGATION):
            return frozenset()
        return frozenset(f.field_name for f in FCC_CONTRACTS[entity_type].fields)

    def get_canonical_create_tool(self, entity_type: str) -> str | None:
        return SNAPSHOT_TOOL if entity_type in FCC_CONTRACTS else None

    def get_canonical_update_tool(self, entity_type: str) -> str | None:
        return SNAPSHOT_TOOL if entity_type in (FCC_GOAL, FCC_OBLIGATION) else None

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
        if entity == FCC_OBLIGATION:
            fields = {RF.ACTIVE: True}
            for name, spec in _OB_FIELDS:
                if values.get(name) not in (None, ""):
                    fields[spec] = _ob_value(name, values[name])
            return {"writes": [{"op": "post", "table": Tables.REC_OBLIGATIONS, "fields": fields,
                                "audit_action": "fcc_obligation_create", "audit_details": str(values.get("name", ""))[:80]}]}
        if entity == FCC_EVENT:
            return {"writes": [_event_write(values, ctx, raw)]}
        if entity == FCC_LOAN_CLOSE:
            return {"writes": loan_close_writes(values, ctx, writer.source_context)}
        if entity in _FIELD_UPDATES:
            return {"writes": field_update_writes(entity, values, writer.source_context)}
        if entity == FCC_ASSET_STEP:
            return {"writes": asset_step_writes(values, writer.source_context)}
        if entity == FCC_ASSET_SOLD:
            return {"writes": asset_sold_writes(values, writer.source_context)}
        if entity == FCC_LOAN_NEW:
            return {"writes": [loan_new_write(values)]}
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
        if writer.target_entity == FCC_OBLIGATION:
            values = dict(writer.current_values)
            changed = {k: v for k, v in values.items() if v != original_fields.get(k)}
            if not changed:
                return {}
            record_id = str(writer.source_context.get("record_id") or "")
            patch = {spec: _ob_value(name, changed[name]) for name, spec in _OB_FIELDS if name in changed}
            return {"writes": [{"op": "patch", "table": Tables.REC_OBLIGATIONS, "record_id": record_id, "fields": patch,
                                "audit_action": "fcc_obligation_update", "audit_details": record_id}]}
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
