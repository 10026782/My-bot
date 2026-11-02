"""המשווה (PATH_ENGINE_ARCHITECTURE_SPEC §3.3) — עושה רק את זה: בדיקת בסיס אחד, הפרשים חתומים מול ייחוס שהבעלים בחר, רגישות ונקודת מעבר.

לא ממיין, לא מדרג, לא מסכם ולא ממליץ; סדר הפלט = סדר הקלט; בלי ייחוס — בלי הפרשים. תוצאות על בסיס שונה (חתימת frame, תאריך השוואה, בסיס מס,
בסיס אינפלציה, מטרה, סכום ממומן) נדחות ב-ValueError — אין "ברוטו מול נטו"."""

from __future__ import annotations

from ..models import ENGINE_VERSION
from . import core, liquid_paths, loan_paths

COMPARATOR_VERSION = "comparator-2"
_SCAN_STEPS = 24
_MODULES = {t: loan_paths for t in loan_paths.TYPES} | {t: liquid_paths for t in liquid_paths.TYPES}
GAP_FIELDS = (
    ("cash_at_compare_date", "result.cash_at_compare_date"),
    ("monthly_cash_effect", "result.monthly_cash_effect"),
    ("net_worth_before_latent_tax_nominal", "measures.net_worth.before_latent_tax.nominal"),
    ("net_worth_after_latent_tax_nominal", "measures.net_worth.after_latent_tax.nominal"),
    ("net_worth_after_latent_tax_real", "measures.net_worth.after_latent_tax.real"),
    ("net_cost", "measures.economic_cost.net_cost"),
)


def evaluate_path(frame: dict, spec: dict) -> dict:
    """מפנה מסלול למודול שלו לפי `type`."""
    module = _MODULES.get(spec.get("type")) if isinstance(spec, dict) else None
    if module is None:
        raise ValueError(f"unknown path type; supported: {', '.join(sorted(_MODULES))}")
    return module.evaluate(frame, spec)


def describe_inputs(type_: str) -> dict:
    module = _MODULES.get(type_)
    if module is None:
        raise ValueError(f"unknown path type; supported: {', '.join(sorted(_MODULES))}")
    return module.describe_inputs(type_)


def _basis_check(frame: dict, results: list) -> None:
    if not results:
        raise ValueError("at least one path result is required")
    seen = set()
    for r in results:
        core.validate_path_result(r)
        if r["path_id"] in seen:
            raise ValueError("path ids must be unique")
        seen.add(r["path_id"])
        if r["frame_digest"] != frame["frame_digest"] or r["basis"]["compare_at"] != frame["compare_at"]:
            raise ValueError("every path must be measured on the same frame and compare_at")
        if r["basis"]["tax_basis"] != frame["tax_basis"] or r["basis"]["inflation_basis"] != frame["inflation_basis"]:
            raise ValueError("every path must use the same tax and inflation basis (no gross against net)")
    if len({r["purpose"] for r in results}) != 1:
        raise ValueError("paths with different purposes cannot be compared")
    if len({r["funds_amount"] for r in results}) > 1:                    # None counts as a value: an unknown amount never matches a known one
        raise ValueError("paths must fund the same, known amount")


def compare_paths(frame: dict, results: list, *, reference: str | None = None) -> dict:
    """השוואה ניטרלית של תוצאות מסלולים שכבר חושבו. `reference` = `path_id` של מסלול הייחוס שהבעלים בחר (אופציונלי)."""
    core.check_frame(frame)
    _basis_check(frame, results)
    ref = None
    if reference is not None:
        ref = next((r for r in results if r["path_id"] == reference), None)
        if ref is None:
            raise ValueError("reference must be the id of one of the paths")
    paths = []
    for r in results:
        out = dict(r)
        out["gap_vs_reference"] = None if ref is None else {"reference": reference, "fields": {name: _gap(r, ref, path) for name, path in GAP_FIELDS}}
        paths.append(out)
    warnings = ["השוואה בהנחות שהוזנו בלבד — לא המלצה ולא בחירה עבורך.", "ראשוני — לבדוק בזמן אמת ובייעוץ מס/פיננסי לפני כל פעולה.",
                "ההפרש חתום מול מסלול הייחוס שבחרת: מספר חיובי = ערך גבוה יותר מהייחוס באותו שדה, לא ״טוב יותר״."]
    not_funded = [r["path_id"] for r in results if r["goal_funding"]["funds_on_time"] is False]
    if not_funded:
        warnings.append("מסלולים שאינם מממנים את היעד בזמן מוצגים כחלופה בלבד, לא כשווי ערך: " + ", ".join(not_funded))
    if any(r["certainty"] == "uncertain" and "default_input_used" in r["risks"] for r in results):
        warnings.append("בחלק מהמסלולים נתון שלא הוזן חושב בברירת מחדל — המספר אינו ודאי עד שיוזן.")
    if any(r["missing_inputs"] for r in results):
        warnings.append("נתון חסר מוצג חסר, לא אפס; הפרש שאחד מצדדיו חסר אינו מחושב.")
    return {"schema_version": core.SCHEMA_VERSION, "engine_version": ENGINE_VERSION, "comparator_version": COMPARATOR_VERSION,
            "result_type": "assumption_based_projection", "compare_at": frame["compare_at"], "frame_echo": frame, "purpose": results[0]["purpose"],
            "paths": paths, "reference": reference, "not_funded_on_time": not_funded, "warnings": warnings}


def _get(result: dict, path: str):
    node = result
    for part in path.split("."):
        node = node.get(part) if isinstance(node, dict) else None
    return node


def _gap(result: dict, ref: dict, path: str):
    a, b = _get(result, path), _get(ref, path)
    return None if a is None or b is None else round(a - b, 2)


# ── רגישות ונקודת מעבר ────────────────────────────────────────────────────────────────────────────────────────────

def sensitivity(frame: dict, spec: dict, parameter: str, values: list, *, metric: str = "measures.net_worth.after_latent_tax.nominal") -> dict:
    """הרצה חוזרת של אותו מסלול בערכים חלופיים **מפורשים** של פרמטר אחד. מציג שורות נפרדות — בלי ממוצע, חציון או "הערך הסביר"."""
    if not isinstance(values, list) or not 1 <= len(values) <= 20:
        raise ValueError("values must be a list of 1 to 20 explicit alternatives")
    if parameter in ("id", "type", "label"):
        raise ValueError("that parameter cannot be varied")
    rows = []
    for v in values:
        out = evaluate_path(frame, {**spec, parameter: v})
        rows.append({"value": v, "metric": _get(out, metric), "net_cost": out["measures"]["economic_cost"]["net_cost"], "missing_inputs": out["missing_inputs"]})
    return {"path_id": spec.get("id"), "parameter": parameter, "metric_path": metric, "rows": rows,
            "note": "alternative inputs, shown as separate rows; no row is singled out"}


def break_even(frame: dict, spec_a: dict, spec_b: dict, parameter: str, lo: float, hi: float, *, metric: str = "measures.net_worth.after_latent_tax.nominal",
               iterations: int = 60) -> dict:
    """הערך של `parameter` במסלול A שבו A ו-B שווים במדד — **ערך סף, לא מסקנה**. אין שינוי סימן בטווח → `None` ("אין נקודת מעבר בטווח")."""
    lo, hi = core.num(lo, "lo"), core.num(hi, "hi")
    if not lo < hi:
        raise ValueError("lo must be below hi")
    target = _get(evaluate_path(frame, spec_b), metric)

    def diff(x):
        value = _get(evaluate_path(frame, {**spec_a, parameter: x}), metric)
        return None if value is None or target is None else value - target

    out = {"parameter": parameter, "metric_path": metric, "range": [lo, hi], "value": None, "crossings": [], "reason": None,
           "note": "a threshold under the entered assumptions, not a conclusion; found on a %d-step scan, so two crossings closer than one step can be missed" % _SCAN_STEPS}
    xs = [lo + (hi - lo) * i / _SCAN_STEPS for i in range(_SCAN_STEPS + 1)]
    ds = [diff(x) for x in xs]
    if any(d is None for d in ds):
        out["reason"] = "missing_inputs"
        return out
    brackets = []
    for i in range(_SCAN_STEPS):
        if ds[i] == 0:
            brackets.append((xs[i], xs[i], ds[i]))
        elif ds[i] * ds[i + 1] < 0:
            brackets.append((xs[i], xs[i + 1], ds[i]))
    if ds[-1] == 0:
        brackets.append((xs[-1], xs[-1], 0.0))
    crossings = []
    for a, b, fa in brackets:
        for _ in range(iterations if a != b else 0):
            mid = (a + b) / 2
            fm = diff(mid)
            if (fm > 0) == (fa > 0):
                a, fa = mid, fm
            else:
                b = mid
        crossings.append(round((a + b) / 2, 6))
    out["crossings"] = crossings
    if not crossings:
        out["reason"] = "no_crossing_in_range"
    elif len(crossings) == 1:
        out["value"] = crossings[0]
    else:
        out["reason"] = "multiple_crossings"                         # no single threshold exists; all are listed
    return out
