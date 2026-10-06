"""FCC intent helpers: validate the classifier's structured output and resolve goals.

* Classification is the injected extractor (LLM in production); this module contains NO phrase
  parsers. It only validates the structured intent and resolves a goal hint against the caller's
  OWN goals. Ambiguity is returned as such, never guessed.
* It never writes and holds no state: the multi-turn draft/completion flow lives in
  ``conversation`` (BusinessDraft-based), and execution goes through the ActionGateway.
"""

from __future__ import annotations

import re

from airtable_schema import FinGoalFields
from core.financial_control import calc

ACTIONS = ("log_progress", "set_target", "create_goal", "update_goal", "rename_goal", "follow_up", "note",
           "upsert_obligation", "deactivate_obligation")
PERIOD_TYPES = ("monthly", "weekly", "custom")
CALC_METHODS = (calc.PERIOD_SUM, calc.CUMULATIVE, calc.RECURRING_LEVEL)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().casefold())


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
        if kind not in (calc.ONE_TIME, calc.MONTHLY_RECURRING, calc.DIRECT_COST, calc.HOUSEHOLD_EXPENSE):
            return None
        out["kind"] = kind
    from core.financial_control import draft as fd        # obligation vocab lives with the draft contract
    for key, allowed in (("frequency", fd.OB_FREQUENCIES), ("scope", fd.OB_SCOPES), ("review_status", fd.OB_REVIEW),
                         ("obligation_type", fd.OB_TYPES), ("essentiality", fd.OB_ESSENTIALITY)):
        val = intent.get(key)
        if val is not None:
            if val not in allowed:
                return None
            out[key] = val
    val = intent.get("saving")
    if val is not None:
        if isinstance(val, bool) or not isinstance(val, (int, float)) or val < 0:
            return None
        out["saving"] = float(val)
    for key in ("title", "new_title", "task_title", "note", "category", "vendor"):
        if intent.get(key):
            out[key] = str(intent[key]).strip()
    for key, allowed in (("period_type", PERIOD_TYPES), ("calc_method", CALC_METHODS)):
        val = intent.get(key)
        if val is not None:
            if val not in allowed:
                return None
            out[key] = val
    for key in ("start_date", "end_date", "next_charge_date"):
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
