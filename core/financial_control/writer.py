"""FCC free-text writer: Classify -> Resolve -> Validate -> Preview -> Action Contract.

* Classification is the injected ``classifier`` (LLM in production); this module
  contains NO phrase parsers. It only validates the structured intent and resolves
  it against the caller's OWN goals.
* It never writes. ``plan()`` returns proposals (``tma_write`` payloads) that the
  caller sends through ``_queue_or_owner_execute`` -> ActionGateway -> dispatcher.
* Ambiguity / missing data are returned as such, never guessed.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date

from airtable_schema import FinEventFields, FinGoalFields, TaskFields, Tables
from core import data_access_policy as policy
from core.financial_control import calc, service

ACTIONS = ("log_progress", "set_target", "create_goal", "update_goal", "rename_goal", "follow_up", "note")
PERIOD_TYPES = ("monthly", "weekly", "custom")
CALC_METHODS = (calc.PERIOD_SUM, calc.CUMULATIVE, calc.RECURRING_LEVEL)
SOURCE = "fcc_free_text"
FCC_TASK_TOPIC = "כספים"   # existing Tasks.Topic choice; with the [FCC:<goal>] tag marks FCC-origin tasks


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().casefold())


def idempotency_key(owner_ref: str, action: str, goal_id: str, amount, day: str, text: str) -> str:
    raw = json.dumps([owner_ref, action, goal_id, amount, day, _norm(text)], ensure_ascii=False)
    return "fcc-" + hashlib.sha256(raw.encode()).hexdigest()[:24]


def validate_intent(intent: object) -> dict | None:
    """Strict shape check of the classifier output. Unknown/garbled -> None (clarify)."""
    if not isinstance(intent, dict) or intent.get("action") not in ACTIONS:
        return None
    out = {"action": intent["action"], "goal_hint": str(intent.get("goal_hint") or "").strip()}
    for key in ("amount", "target"):
        val = intent.get(key)
        if val is not None:
            if isinstance(val, bool) or not isinstance(val, (int, float)):
                return None
            out[key] = float(val)
    kind = intent.get("kind")
    if kind is not None:
        if kind not in (calc.ONE_TIME, calc.MONTHLY_RECURRING):
            return None
        out["kind"] = kind
    for key in ("title", "new_title", "task_title", "note", "category"):
        if intent.get(key):
            out[key] = str(intent[key]).strip()
    for key, allowed in (("period_type", PERIOD_TYPES), ("calc_method", CALC_METHODS)):
        val = intent.get(key)
        if val is not None:
            if val not in allowed:
                return None
            out[key] = val
    for key in ("start_date", "end_date"):
        val = intent.get(key)
        if val is not None:
            parsed = calc._d(val) if isinstance(val, str) else None
            if parsed is None:
                return None
            out[key] = parsed.isoformat()
    return out


_GOAL_ATTRS = (
    ("category", FinGoalFields.CATEGORY, "קטגוריה"),
    ("period_type", FinGoalFields.PERIOD_TYPE, "תקופה"),
    ("calc_method", FinGoalFields.CALC_METHOD, "שיטת חישוב"),
    ("start_date", FinGoalFields.START_DATE, "התחלה"),
    ("end_date", FinGoalFields.END_DATE, "סיום"),
)


def _goal_attr_fields(clean: dict) -> dict:
    return {field: clean[key] for key, field, _ in _GOAL_ATTRS if key in clean}


def _goal_attr_summary(clean: dict) -> str:
    return ", ".join(f"{label}: {clean[key]}" for key, _, label in _GOAL_ATTRS if key in clean)


def resolve_goal(hint: str, goals: list[dict]) -> tuple[str, list[dict]]:
    """('one'|'none'|'many', matches) among the caller's own goals only."""
    active = [g for g in goals if str((g.get("fields") or {}).get(FinGoalFields.STATUS) or "active").lower()
              in ("active", "פעיל")]
    if not active:
        return "none", []
    h = _norm(hint)
    if h:
        exact = [g for g in active if _norm((g["fields"]).get(FinGoalFields.TITLE, "")) == h]
        if len(exact) == 1:
            return "one", exact
        part = [g for g in active if h in _norm(g["fields"].get(FinGoalFields.TITLE, ""))
                or _norm(g["fields"].get(FinGoalFields.TITLE, "")) in h]
        if len(part) == 1:
            return "one", part
        if part:
            return "many", part
        return "none", []
    return ("one", active) if len(active) == 1 else ("many", active)


def _cand(goals: list[dict]) -> list[dict]:
    return [{"goal_id": g["id"], "title": g["fields"].get(FinGoalFields.TITLE)} for g in goals]


def _event_post(owner_label: str, goal_id: str, kind: str, amount, day: str, key: str, text: str, note: str = "") -> dict:
    fields = {
        FinEventFields.GOAL: [goal_id], FinEventFields.KIND: kind, FinEventFields.AMOUNT: amount,
        FinEventFields.OCCURRED_AT: day, FinEventFields.RECORDED_BY: owner_label,
        FinEventFields.SOURCE: SOURCE, FinEventFields.RAW_TEXT: text[:2000],
        FinEventFields.IDEMPOTENCY_KEY: key,
    }
    if note:
        fields[FinEventFields.NOTE] = note
    return {"op": "post", "table": Tables.FIN_EVENTS, "fields": fields,
            "audit_action": "fcc_event", "audit_details": key}


def plan(raw_text: str, intent: object, identity, today: date | None = None, goal_id: str | None = None) -> dict:
    """Return {status, ...}. status ∈ denied|clarify|needs_goal|duplicate|preview.

    ``goal_id`` is an explicit user choice after a ``needs_goal`` answer; it is
    still verified as the caller's own goal (never trusted).
    """
    today = today or date.today()
    day = today.isoformat()
    actor = policy.resolve_actor(identity)
    if not actor.resolved:
        return {"status": "denied", "message": policy.UNRESOLVED_MESSAGE}
    clean = validate_intent(intent)
    if clean is None:
        return {"status": "clarify", "message": "לא הבנתי את הבקשה — אפשר לנסח שוב?"}
    action = clean["action"]
    owner_label = getattr(identity, "user_id", "")
    proposals: list[dict] = []

    if action == "create_goal":
        title = clean.get("title") or clean.get("goal_hint")
        if not title:
            return {"status": "clarify", "message": "איך לקרוא ליעד החדש?"}
        fields = {FinGoalFields.TITLE: title, FinGoalFields.STATUS: "active"}
        if "target" in clean:
            fields[FinGoalFields.TARGET_AMOUNT] = clean["target"]
        fields.update(_goal_attr_fields(clean))
        if any(_norm(g["fields"].get(FinGoalFields.TITLE, "")) == _norm(title) for g in service.my_goals(identity)):
            return {"status": "duplicate", "message": "כבר קיים יעד בשם הזה."}
        extra = _goal_attr_summary(clean)
        return {"status": "preview", "summary": f"יעד חדש: {title}" + (f" ({extra})" if extra else ""),
                "proposals": [{"op": "post", "table": Tables.FIN_GOALS, "fields": fields,
                               "audit_action": "fcc_goal_create", "audit_details": title[:80]}],
                "idempotency_key": idempotency_key(actor.profile_id, action, "", clean.get("target"), day, raw_text)}

    goals = service.my_goals(identity)               # caller's own goals only
    state, matches = resolve_goal(clean["goal_hint"], goals)
    if goal_id:
        chosen = [g for g in goals if g["id"] == goal_id]
        if not chosen:
            return {"status": "denied", "message": policy.DENIED_MESSAGE}
        state, matches = "one", chosen
    if state == "none":
        return {"status": "needs_goal", "candidates": _cand(goals),
                "message": "לא נמצא יעד מתאים — בחר יעד או צור חדש."}
    if state == "many":
        return {"status": "needs_goal", "candidates": _cand(matches),
                "message": "יש כמה יעדים מתאימים — איזה מהם?"}
    goal = matches[0]
    gid = goal["id"]
    title = goal["fields"].get(FinGoalFields.TITLE, "")

    if action == "update_goal":
        attrs = _goal_attr_fields(clean)
        if not attrs:
            return {"status": "clarify", "message": "מה לעדכן ביעד (קטגוריה, תקופה, שיטת חישוב, תאריכים)?"}
        proposals.append({"op": "patch", "table": Tables.FIN_GOALS, "record_id": gid, "fields": attrs,
                          "audit_action": "fcc_goal_update", "audit_details": gid})
        return {"status": "preview", "summary": f"עדכון יעד {title}: {_goal_attr_summary(clean)}",
                "goal_id": gid, "proposals": proposals,
                "idempotency_key": idempotency_key(actor.profile_id, action, gid, None, day, raw_text)}

    if action == "rename_goal":
        if not clean.get("new_title"):
            return {"status": "clarify", "message": "מה השם החדש?"}
        proposals.append({"op": "patch", "table": Tables.FIN_GOALS, "record_id": gid,
                          "fields": {FinGoalFields.TITLE: clean["new_title"]},
                          "audit_action": "fcc_goal_rename", "audit_details": gid})
        summary = f"שינוי שם יעד: {title} → {clean['new_title']}"
        amount = None
    elif action in ("log_progress", "set_target"):
        amount = clean.get("amount") if action == "log_progress" else clean.get("target")
        if amount is None:
            # missing data -> follow-up task instead of an invented number
            missing = _followup(identity, actor, gid, f"להשלים סכום עבור: {title}", raw_text)
            return {"status": "preview", "summary": "חסר סכום — תיווצר משימת המשך",
                    "proposals": missing, "idempotency_key": ""}
        kind = calc.TARGET_CHANGE if action == "set_target" else clean.get("kind", calc.ONE_TIME)
        key = idempotency_key(actor.profile_id, action, gid, amount, day, raw_text)
        if any((e.get("fields") or {}).get(FinEventFields.IDEMPOTENCY_KEY) == key for e in service.my_events(identity)):
            return {"status": "duplicate", "message": "האירוע כבר נרשם.", "idempotency_key": key}
        proposals.append(_event_post(owner_label, gid, kind, amount, day, key, raw_text, clean.get("note", "")))
        summary = f"{'שינוי יעד' if action == 'set_target' else 'התקדמות'} ({kind}) {amount:g} ביעד: {title}"
    elif action == "note":
        key = idempotency_key(actor.profile_id, action, gid, None, day, raw_text)
        proposals.append(_event_post(owner_label, gid, calc.NOTE, 0, day, key, raw_text, clean.get("note", raw_text)))
        summary = f"הערה ביעד: {title}"
        amount = None
    else:  # follow_up
        summary = f"משימת המשך ליעד: {title}"
        amount = None

    if clean.get("task_title") or action == "follow_up":
        proposals += _followup(identity, actor, gid, clean.get("task_title") or title, raw_text)
    return {"status": "preview", "summary": summary, "goal_id": gid, "proposals": proposals,
            "idempotency_key": idempotency_key(actor.profile_id, action, gid, amount, day, raw_text)}


def _followup(identity, actor, goal_id: str, title: str, raw_text: str) -> list[dict]:
    """Task proposal (reuse Tasks, Owner=actor). [] if an identical open one exists."""
    tag = f"[FCC:{goal_id}]"
    for rec in service.open_followups(identity, goal_id):
        if _norm(rec["fields"].get(TaskFields.NAME, "")) == _norm(title):
            return []
    return [{"op": "post", "table": Tables.TASKS,
             "fields": {TaskFields.NAME: title, TaskFields.STATUS: "ממתין",
                        TaskFields.DESCRIPTION: f"{tag} {raw_text[:300]}".strip(),
                        TaskFields.OWNER: [actor.profile_id], TaskFields.TOPIC: FCC_TASK_TOPIC},
             "audit_action": "fcc_followup", "audit_details": goal_id}]
