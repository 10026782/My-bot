"""ליבת השוואת המסלולים (PATH_ENGINE_ARCHITECTURE_SPEC §2–§3): `frame`, שיעור המס מהרשומה היחידה, צמיחה מהמנוע הקיים, מבנה `PathResult` ומאמת.

טהור: ללא I/O, Airtable, LLM, flag או כתיבה. אין כאן `score`/`rank`/`best`/`recommended`; חסר = `None` (+ `missing_inputs`), לא 0; סכום שאחד מרכיביו חסר
אינו מוצג כסכום. המנוע הקיים (`portfolio_lab.engine.simulate`) אינו משתנה — כל צמיחה עוברת דרכו. כל מסלול נמדד מול אותו בסיס: אותו `compare_at`,
אותו בסיס מס (אחרי מס סמוי) ואותו בסיס אינפלציה."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import date

from .. import tax_assumptions
from ..engine import simulate
from ..models import ENGINE_VERSION, Asset, Scenario

SCHEMA_VERSION = "1.0"
CORE_VERSION = "path-core-1"
MAX_MONTHS = 360                              # compare_at at most 30 years ahead
TAX_BASIS = "after_latent_tax"                # the one basis every comparison is made on
MOVEMENT_KINDS = ("new_money", "liability", "equity_conversion", "claim_realization", "no_movement")      # no_movement: the "do nothing / wait" reference path
CERTAINTIES = ("confirmed", "expected", "uncertain", "unknown")
PURPOSES = ("fund_amount", "reduce_debt")
FORBIDDEN_KEYS = ("score", "rank", "ranking", "best", "recommended", "recommendation", "better", "cheapest", "optimal", "total_available")

CAVEATS = (
    {"caveat_id": "preliminary", "version": 1, "text": "ראשוני — לבדוק בזמן אמת ובייעוץ מס/פיננסי לפני כל פעולה", "when": "always"},
    {"caveat_id": "tax_rate_estimate", "version": 1, "text": "שיעור המס הוא הערכה ראשונית לפי הנחיית הבעלים; לא אומת מקצועית", "when": "tax"},
    {"caveat_id": "assumption_based", "version": 1, "text": "ההשוואה בהנחות שהוזנו; אינה תחזית", "when": "always"},
    {"caveat_id": "missing_is_missing", "version": 1, "text": "נתון חסר מוצג חסר, לא אפס", "when": "missing"},
    {"caveat_id": "appreciation_owner_entered", "version": 1,
     "text": "עליית הערך העתידית הוזנה ע\"י הבעלים לפי מדד שנבדק ידנית (שם, תאריך); אינה תחזית", "when": "appreciation"},
)


# ── קלט ───────────────────────────────────────────────────────────────────────────────────────────────────────────

def num(value, name, *, lo=None, hi=None, positive=False, required=True):
    """מספר סופי; `None` מותר רק אם `required=False`. ValueError על כל קלט אחר (בלי להדהד ערכים)."""
    if value is None:
        if required:
            raise ValueError(f"{name} is required")
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    if positive and value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    if lo is not None and value < lo:
        raise ValueError(f"{name} must be at least {lo}")
    if hi is not None and value > hi:
        raise ValueError(f"{name} must be at most {hi}")
    return float(value)


def to_date(value, name) -> date:
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise ValueError(f"{name} must be an ISO date")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an ISO date") from exc


def months_between(start: date, end: date) -> int:
    return (end.year - start.year) * 12 + (end.month - start.month)


def make_frame(raw: dict) -> dict:
    """הבסיס המשותף: תאריך חישוב, תאריך השוואה, אינפלציה (מוזנת, לפי שנה), תשואה חלופית (אופציונלית), רשומת המס היחידה, גרסאות — וחתימה."""
    if not isinstance(raw, dict):
        raise ValueError("frame must be an object")
    unknown = set(raw) - {"today", "compare_at", "inflation_pct", "alternative_return_pct", "owner_inputs_label", "tax_rate_override", "assumptions_version"}
    if unknown:
        raise ValueError(f"unknown frame fields: {', '.join(sorted(unknown))}")
    today, compare_at = to_date(raw.get("today"), "today"), to_date(raw.get("compare_at"), "compare_at")
    months = months_between(today.replace(day=1), compare_at.replace(day=1))
    if not compare_at > today or months < 1:
        raise ValueError("compare_at must fall in a later month than today")
    if months > MAX_MONTHS:
        raise ValueError(f"compare_at must be within {MAX_MONTHS // 12} years")
    raw_infl = raw.get("inflation_pct")
    infl = list(raw_infl) if isinstance(raw_infl, (list, tuple)) else [raw_infl]
    if not 1 <= len(infl) <= 40:
        raise ValueError("inflation_pct must be a number or a yearly list of at most 40")
    infl = [num(i, "inflation_pct", lo=-50, hi=100) for i in infl]      # entered by the owner; never derived from a live index
    alt = num(raw.get("alternative_return_pct"), "alternative_return_pct", lo=-50, hi=50, required=False)
    label = raw.get("owner_inputs_label")
    if not isinstance(label, str) or not label.strip():
        raise ValueError("owner_inputs_label must say where the assumptions come from")
    version = raw.get("assumptions_version", "assumptions-1")
    if not isinstance(version, str) or not 1 <= len(version) <= 40:
        raise ValueError("assumptions_version must be a short text")
    frame = {"today": today.isoformat(), "compare_at": compare_at.isoformat(), "months": months, "inflation_pct": infl, "alternative_return_pct": alt,
             "owner_inputs_label": label.strip()[:120], "tax": tax_assumptions.tax_record(raw.get("tax_rate_override")),
             "tax_basis": TAX_BASIS, "inflation_basis": "yearly_list_entered_by_owner", "assumptions_version": version,
             "calc_versions": {"core": CORE_VERSION, "engine": ENGINE_VERSION, "tax_rate": None}}
    frame["calc_versions"]["tax_rate"] = frame["tax"]["version"]
    frame["frame_digest"] = digest({k: v for k, v in frame.items() if k != "frame_digest"})
    return frame


def digest(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()[:16]


def check_frame(frame) -> dict:
    """מסגרת שנבנתה ב-`make_frame` וחתימתה תקפה; אחרת ValueError (אין השוואה מול מסגרת ששונתה ידנית)."""
    if not isinstance(frame, dict) or "frame_digest" not in frame:
        raise ValueError("frame must come from make_frame")
    if digest({k: v for k, v in frame.items() if k != "frame_digest"}) != frame["frame_digest"]:
        raise ValueError("frame was changed after it was built")
    return frame


# ── צמיחה (המנוע הקיים) ───────────────────────────────────────────────────────────────────────────────────────────

def _scenario(frame: dict, amount: float, annual_return_pct: float, annual_fee_pct: float) -> Scenario:
    years = max(10, -(-frame["months"] // 12))
    start = date.fromisoformat(frame["today"]).replace(day=1).isoformat()
    yearly = list(frame["inflation_pct"])[:years]
    yearly += [yearly[-1]] * (years - len(yearly))                      # the engine wants one value or exactly `years`; the last entered year carries on
    return Scenario(years=years, initial=amount, monthly_contribution=0.0, inflation=tuple(i / 100 for i in yearly),
                    deposit_timing="end", start_date=start,
                    assets=(Asset(name="path", annual_return=annual_return_pct / 100, annual_fee=annual_fee_pct / 100),))


def lump_value(frame: dict, amount: float, annual_return_pct: float, annual_fee_pct: float = 0.0) -> dict:
    """הערך ב-`compare_at` של סכום חד-פעמי `amount` שהושקע היום — מ-`engine.simulate`. `nominal`/`real` (ריאלי לפי אינפלציית ה-frame) ו-`cpi`."""
    row = simulate(_scenario(frame, amount, annual_return_pct, annual_fee_pct), monthly=True)["monthly"][frame["months"] - 1]
    nominal, real = float(row["value_after_costs"]), float(row["real_value"])
    return {"nominal": nominal, "real": real, "cpi": nominal / real if real else cpi_factor(frame)}


def cpi_factor(frame: dict) -> float:
    """אינפלציה מצטברת מ-`today` עד `compare_at` — מאותו מנוע (השקעה ללא תשואה: ערך נומינלי / ריאלי)."""
    row = simulate(_scenario(frame, 1.0, 0.0, 0.0), monthly=True)["monthly"][frame["months"] - 1]
    return float(row["value_after_costs"]) / float(row["real_value"])


def tax_on_growth(frame: dict, amount: float, growth_nominal: float) -> float:
    """מס ראשוני על צמיחה של `amount` עד `compare_at`: הרווח הריאלי = הצמיחה פחות ההצמדה לאינפלציה של הקרן (`amount × (cpi − 1)`); הרשומה היחידה."""
    real_gain = growth_nominal - amount * (cpi_factor(frame) - 1.0)
    return tax_assumptions.tax_on(real_gain, frame["tax"])


# ── PathResult ────────────────────────────────────────────────────────────────────────────────────────────────────

def blank_result(frame: dict, *, path_id: str, module: str, module_version: str, type_: str, label: str, movement_kind: str, purpose: str,
                 funds_amount: float | None) -> dict:
    """השלד האחיד (§3.2). כל שדה שהמודול ימלא; כל מה שלא רלוונטי מסומן ב-`not_applicable` (נבדל מ-`None` של "חסר")."""
    if movement_kind not in MOVEMENT_KINDS or purpose not in PURPOSES:
        raise ValueError("unknown movement kind or purpose")
    return {
        "path_id": path_id, "module": module, "type": type_, "label": label, "purpose": purpose, "funds_amount": funds_amount,
        "frame_digest": frame["frame_digest"], "calc_version": {"core": CORE_VERSION, "module": module_version, "tax_rate": frame["tax"]["version"],
                                                              "assumptions": frame["assumptions_version"]},
        "basis": {"compare_at": frame["compare_at"], "tax_basis": frame["tax_basis"], "inflation_basis": frame["inflation_basis"]},
        "movement_kind": movement_kind,
        "after_action": {"capital_remaining": None, "assets_remaining": [], "future_income_remaining": None,
                         "given_up": {"assets": [], "future_income": None, "lost_future_value": None}},
        "measures": {"liquidity": {"cash_available": None, "available_on": None, "state": None},
                     "net_worth": {"before_latent_tax": {"nominal": None, "real": None}, "after_latent_tax": {"nominal": None, "real": None}},
                     "economic_cost": {"net_cost": None, "components": []}},
        "index_used": {"name": None, "source": None, "kind": None, "verified": False},
        "cash_flows": [],
        "cost": {"interest_total": None, "fees_total": None, "holding_costs": None, "lost_income": None, "opportunity_cost": None,
                 "forced_sale_discount_amount": None},
        "tax": {"event": "none", "event_date": None, "paid": None, "latent_at_compare": None, "deferral_benefit": None, "deferral_lost": None,
                "status": "not_assessed", "reason": None, "rate_version": frame["tax"]["version"], "rate_as_of": frame["tax"]["as_of"],
                "rate_source": frame["tax"]["source"]},
        "lost_future_value": {"rows": [], "missing": False, "asset_in_engine_portfolio": None, "reason": "asset_not_sold"},
        "result": {"cash_at_compare_date": None, "net_worth_change_at_compare_date": {"nominal": None, "real": None},
                   "monthly_cash_effect": None, "balance_effect": None},
        "assumptions": [], "missing_inputs": [], "risks": [], "certainty": "unknown", "provenance": {}, "not_applicable": [],
        "caveats": [],
    }


def total_or_none(parts: list) -> float | None:
    """סכום רק כשכל הרכיבים ידועים; אחרת `None` (לא סכום חלקי מוסתר)."""
    return None if any(p is None for p in parts) else float(sum(parts))


def finalize(result: dict) -> dict:
    """מסמן הסתייגויות קבועות לפי מה שיש בתוצאה, מעגל לאגורה, ומאמת מבנה. מחזיר את אותה תוצאה."""
    caveats = [c for c in CAVEATS if c["when"] == "always"
               or (c["when"] == "tax" and result["tax"]["status"] == "preliminary_estimate")
               or (c["when"] == "missing" and result["missing_inputs"])
               or (c["when"] == "appreciation" and result["lost_future_value"]["rows"])]
    result["caveats"] = [{k: c[k] for k in ("caveat_id", "version", "text")} for c in caveats]
    _round(result)
    validate_path_result(result)
    return result


def _round(node):
    if isinstance(node, dict):
        for k, v in node.items():
            if isinstance(v, float):
                node[k] = round(v, 2)
            else:
                _round(v)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            if isinstance(v, float):
                node[i] = round(v, 2)
            else:
                _round(v)


_REQUIRED_TOP = ("path_id", "module", "type", "label", "purpose", "funds_amount", "frame_digest", "calc_version", "basis", "movement_kind", "after_action",
                 "measures", "index_used", "cash_flows", "cost", "tax", "lost_future_value", "result", "assumptions", "missing_inputs", "risks", "certainty",
                 "provenance", "not_applicable", "caveats")


def validate_path_result(result) -> dict:
    """מאמת מבנה (§7): אין שדה דירוג/המלצה/סכום מאוחד; שלוש המידות נפרדות; הסתייגויות קיימות; בסיס אחד; `not_applicable` מצביע על שדות ריקים."""
    if not isinstance(result, dict):
        raise ValueError("path result must be an object")
    missing = [k for k in _REQUIRED_TOP if k not in result]
    if missing:
        raise ValueError(f"path result is missing: {', '.join(missing)}")
    bad = sorted({k for k in _all_keys(result) if k.lower() in FORBIDDEN_KEYS})
    if bad:
        raise ValueError(f"forbidden fields in a path result: {', '.join(bad)}")
    if result["movement_kind"] not in MOVEMENT_KINDS or result["certainty"] not in CERTAINTIES or result["purpose"] not in PURPOSES:
        raise ValueError("unknown movement_kind / certainty / purpose")
    if set(result["measures"]) != {"liquidity", "net_worth", "economic_cost"}:
        raise ValueError("measures must be exactly liquidity, net_worth and economic_cost (no merged figure)")
    if set(result["measures"]["net_worth"]) != {"before_latent_tax", "after_latent_tax"}:
        raise ValueError("net_worth must show both before and after latent tax")
    if result["basis"].get("tax_basis") != TAX_BASIS:
        raise ValueError("a result must be on the after-latent-tax basis")
    if not any(c["caveat_id"] == "preliminary" for c in result["caveats"]):
        raise ValueError("the standing caveat is missing")
    if result["tax"]["status"] not in ("preliminary_estimate", "not_assessed"):
        raise ValueError("a tax figure is never marked verified here")
    if result["missing_inputs"] and not any(c["caveat_id"] == "missing_is_missing" for c in result["caveats"]):
        raise ValueError("missing inputs need the 'missing is not zero' caveat")
    for path in result["not_applicable"]:
        if _get(result, path, default="__absent__") is not None:
            raise ValueError("not_applicable must point at an empty field")
    for flow in result["cash_flows"]:
        if set(flow) != {"date", "amount", "kind"}:
            raise ValueError("cash_flows entries are {date, amount, kind}")
    return result


def _all_keys(node):
    if isinstance(node, dict):
        for k, v in node.items():
            yield str(k)
            yield from _all_keys(v)
    elif isinstance(node, list):
        for v in node:
            yield from _all_keys(v)


def _get(node, path, default=None):
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def net_worth_block(frame: dict, before_nominal, after_nominal) -> dict:
    """שתי שורות נפרדות (לפני / אחרי מס סמוי), כל אחת נומינלית וריאלית (לפי אינפלציית ה-frame); `None` נשאר `None`."""
    cpi = cpi_factor(frame)
    row = lambda v: {"nominal": v, "real": None if v is None else v / cpi}      # noqa: E731
    return {"before_latent_tax": row(before_nominal), "after_latent_tax": row(after_nominal)}
