"""FCC early-payoff engine — pure, read-only (no I/O, no writes, no recommendation).

Works on the owner-scoped, active loan items produced by ``loans.loan_item``. It only *computes, ranks and explains*:

  * per-loan metrics: cash-release efficiency, annualised cash release, estimated future cost
  * four normalised 0-100 factor scores (relative to the owner's own active loans — no arbitrary cut-offs)
  * a weighted balanced score that renormalises over the factors that are actually known
  * four ranking strategies (never an automatic "winner")
  * a budget simulator (whole-loan payoffs only; no partial payoff) per strategy, plus the best combination by
    monthly cash released / future cost saved

Unknown stays unknown: a missing factor is never scored as 0, it is dropped from the weighting and reported in
``missing_factors`` / ``score_coverage``.
"""

from __future__ import annotations

from itertools import combinations

# Balanced-score weights (sum = 1). Change here only; the engine renormalises when a factor is unknown.
WEIGHTS = {"interest": 0.30, "cash": 0.30, "closure": 0.25, "time": 0.15}
FACTORS = tuple(WEIGHTS)
STRATEGIES = ("balanced", "interest", "cash", "efficiency")
MAX_OPTIMAL_LOANS = 16        # exhaustive subset search is exact up to 2**16 combinations
_EPS = 1e-9


def _factor_values(item: dict) -> dict[str, float | None]:
    return {
        "interest": item.get("interest_rate"),
        "cash": item.get("monthly_cash_freed_if_closed"),
        "closure": item.get("early_closure_balance"),
        "time": item.get("months_remaining"),
    }


def _normalise(values: dict[str, float], invert: bool = False) -> dict[str, float]:
    """Min-max to 0-100 over the loans that have the factor. No spread (one loan / all equal) -> neutral 50."""
    if not values:
        return {}
    lo, hi = min(values.values()), max(values.values())
    if hi - lo < _EPS:
        return {k: 50.0 for k in values}
    return {k: round(100.0 * ((hi - v) if invert else (v - lo)) / (hi - lo), 2) for k, v in values.items()}


def _balanced(scores: dict[str, float | None]) -> tuple[float | None, int]:
    known = {f: s for f, s in scores.items() if s is not None}
    if not known:
        return None, 0
    total = sum(WEIGHTS[f] for f in known)
    return round(sum(WEIGHTS[f] * s for f, s in known.items()) / total, 2), len(known)


def _ratio(numer: float | None, denom: float | None) -> float | None:
    return numer / denom if numer is not None and denom is not None and denom > 0 else None


def metrics(items: list[dict]) -> list[dict]:
    """One row per active loan with derived metrics, factor scores, balanced score and data coverage."""
    values = {i["id"]: _factor_values(i) for i in items}
    scored: dict[str, dict[str, float]] = {}
    for factor in FACTORS:
        known = {k: v[factor] for k, v in values.items() if v[factor] is not None}
        scored[factor] = _normalise(known, invert=(factor == "closure"))     # smaller closure amount = higher score

    rows = []
    for item in items:
        iid = item["id"]
        scores = {f: scored[f].get(iid) for f in FACTORS}
        balanced, n_known = _balanced(scores)
        missing = [f for f in FACTORS if scores[f] is None]
        closure, monthly = item.get("early_closure_balance"), item.get("monthly_cash_freed_if_closed")
        monthly_eff = _ratio(monthly, closure)
        rows.append({
            "id": iid, "name": item.get("name"), "lender": item.get("lender"), "loan_type": item.get("loan_type"),
            "amount_to_close": closure,
            "interest_rate": item.get("interest_rate"),
            "monthly_cash_freed": monthly,
            "months_remaining": item.get("months_remaining"),
            "estimated_remaining_payments": item.get("estimated_total_remaining_payments"),
            "estimated_future_cost": item.get("estimated_future_cost"),
            "future_cost_exact": item.get("future_cost_exact", False),
            "monthly_cash_efficiency": monthly_eff,                                   # NOT a return / ROI
            "annualized_cash_release": monthly_eff * 12 if monthly_eff is not None else None,
            "annual_interest_burden": item.get("annual_interest_cost"),
            "scores": scores,
            "balanced_score": balanced,
            "score_coverage": round(n_known / len(FACTORS), 4),
            "score_coverage_label": f"{n_known}/{len(FACTORS)}",
            "missing_factors": missing,
            "partial": bool(missing),
        })
    return rows


def _order(rows: list[dict], key) -> list[str]:
    known = sorted((r for r in rows if key(r) is not None), key=lambda r: (-key(r), r["name"] or "", r["id"]))
    unknown = sorted((r for r in rows if key(r) is None), key=lambda r: (r["name"] or "", r["id"]))
    return [r["id"] for r in known + unknown]


def rankings(rows: list[dict]) -> dict[str, list[str]]:
    return {
        "balanced": _order(rows, lambda r: r["balanced_score"]),
        "interest": _order(rows, lambda r: r["interest_rate"]),
        "cash": _order(rows, lambda r: r["monthly_cash_freed"]),
        "efficiency": _order(rows, lambda r: r["annualized_cash_release"]),
    }


def _sum_known(rows: list[dict], key: str) -> float | None:
    """0 for an empty selection (nothing closed = nothing released); None when loans were closed but none has the value."""
    if not rows:
        return 0.0
    known = [r[key] for r in rows if r[key] is not None]
    return round(sum(known), 2) if known else None


def _result(selected: list[dict], budget: float, skipped_over: list[str], unknown: list[str]) -> dict:
    used = round(sum(r["amount_to_close"] for r in selected), 2)
    return {
        "budget": budget,
        "used": used,
        "remaining_budget": round(budget - used, 2),
        "closed_count": len(selected),
        "closed": [{k: r[k] for k in ("id", "name", "amount_to_close", "monthly_cash_freed", "estimated_future_cost", "future_cost_exact")}
                   for r in selected],
        "debt_removed": used,
        "monthly_cash_released": _sum_known(selected, "monthly_cash_freed"),
        "future_cost_saved": _sum_known(selected, "estimated_future_cost"),
        "future_cost_saved_exact": bool(selected) and all(r["future_cost_exact"] for r in selected),
        "partial": any(r["monthly_cash_freed"] is None or r["estimated_future_cost"] is None for r in selected),
        "skipped_over_budget": skipped_over,
        "excluded_unknown_amount": unknown,
    }


def simulate(rows: list[dict], order: list[str], budget: float) -> dict:
    """Walk the strategy order and close every loan whose full closure amount still fits (<= remaining budget).
    A loan that does not fit is skipped whole — there is no partial payoff — and the walk continues."""
    by_id = {r["id"]: r for r in rows}
    left, selected, skipped, unknown = float(budget), [], [], []
    for iid in order:
        row = by_id[iid]
        amount = row["amount_to_close"]
        if amount is None:
            unknown.append(iid)
        elif amount <= left + _EPS:
            selected.append(row)
            left -= amount
        else:
            skipped.append(iid)
    return _result(selected, float(budget), skipped, unknown)


def optimal(rows: list[dict], budget: float, objective: str) -> dict | None:
    """Best whole-loan combination within the budget by ``objective`` ('cash' = monthly cash released,
    'saved' = estimated future cost saved). Exact (exhaustive) for up to MAX_OPTIMAL_LOANS eligible loans,
    otherwise None. Loans with an unknown value contribute 0 to the objective (never a guess)."""
    eligible = [r for r in rows if r["amount_to_close"] is not None]
    unknown = [r["id"] for r in rows if r["amount_to_close"] is None]
    if len(eligible) > MAX_OPTIMAL_LOANS:
        return None
    key = (lambda r: r["monthly_cash_freed"] or 0.0) if objective == "cash" else (lambda r: r["estimated_future_cost"] or 0.0)
    other = (lambda r: r["estimated_future_cost"] or 0.0) if objective == "cash" else (lambda r: r["monthly_cash_freed"] or 0.0)
    best, best_rank = [], (0.0, 0.0, 0.0)
    for size in range(len(eligible) + 1):
        for combo in combinations(eligible, size):
            cost = sum(r["amount_to_close"] for r in combo)
            if cost > budget + _EPS:
                continue
            rank = (sum(key(r) for r in combo), sum(other(r) for r in combo), -cost)       # tie-break: other metric, then spend less
            if rank > best_rank:
                best, best_rank = list(combo), rank
    chosen = {r["id"] for r in best}
    skipped = [r["id"] for r in eligible if r["id"] not in chosen]
    return _result(sorted(best, key=lambda r: r["id"]), float(budget), skipped, unknown)


def scenarios(rows: list[dict], budget: float) -> dict:
    ranks = rankings(rows)
    return {
        "budget": float(budget),
        "strategies": {s: simulate(rows, ranks[s], budget) for s in STRATEGIES},
        "optimal": {"cash": optimal(rows, budget, "cash"), "saved": optimal(rows, budget, "saved")},
    }


def build(items: list[dict]) -> dict:
    """Payload block for the loans overview (active loans only)."""
    rows = metrics(items)
    return {"weights": dict(WEIGHTS), "items": rows, "rankings": rankings(rows)}
