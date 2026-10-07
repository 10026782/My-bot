"""FCC early-payoff engine — pure, read-only (no I/O, no writes, no recommendation).

Works on the owner-scoped, active loan items produced by ``loans.loan_item``. It only *computes, ranks and explains*:

  * per-loan facts (closure amount, rate, monthly cash freed, months left) and two computed estimates:
    estimated continuation cost and an annual interest burden. No percentage "efficiency" metric exists on purpose:
    it mixed principal and interest and looked like a return.
  * cost saving = what closing now could avoid (continuation cost − known early-repayment fee), with two data-quality
    levels: hard inconsistency (no arithmetic sense) and suspicious (far from a rough rate/time estimate)
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
STRATEGIES = ("balanced", "interest", "cash", "savings")
# Rough sanity band for the continuation cost vs. an amortising-loan estimate (closure × rate × months ÷ 24).
# A heuristic only: it never overrides a hard inconsistency, and a suspicious loan is flagged, not "corrected".
SUSPICIOUS_LOW, SUSPICIOUS_HIGH = 0.4, 2.5
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


def _cost_block(item: dict) -> dict:
    """Continuation cost / cost saving with the two data-quality levels. Nothing is computed from inconsistent data."""
    closure, total = item.get("early_closure_balance"), item.get("estimated_total_remaining_payments")
    fee = item.get("early_fee_amount")                       # None = unknown / non-numeric; 0.0 = known "none"
    rate, months = item.get("interest_rate"), item.get("months_remaining")
    out = {"estimated_future_cost": None, "future_cost_exact": False, "cost_saving": None, "cost_saving_exact": False,
           "no_saving": False, "data_inconsistent": False, "data_suspicious": False, "data_issue": None}
    if closure is None or total is None:
        return out
    if total < closure - _EPS:                                # hard: the remaining payments cannot even repay the closure amount
        # (a known fee larger than the continuation cost is NOT an inconsistency: it is a legitimate "no saving" case below)
        out.update(data_inconsistent=True, data_issue="inconsistent")
        return out
    gross = round(total - closure, 2)
    if rate is not None and months:
        expected = closure * rate / 100.0 * months / 24.0
        if expected > 0 and not (SUSPICIOUS_LOW * expected <= gross <= SUSPICIOUS_HIGH * expected):
            out.update(data_suspicious=True, data_issue="suspicious")      # soft: show the facts, drop the cost + ranking
            return out
    out.update(estimated_future_cost=gross, future_cost_exact=fee is not None)
    net = round(gross - (fee or 0.0), 2)
    if net <= 0:
        out.update(no_saving=True, cost_saving=0.0, cost_saving_exact=fee is not None)     # never a positive "saving" after the fee
    else:
        out.update(cost_saving=net, cost_saving_exact=fee is not None)
    return out


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
        cost = _cost_block(item)
        rows.append({
            "id": iid, "name": item.get("name"), "lender": item.get("lender"), "loan_type": item.get("loan_type"),
            "amount_to_close": closure,
            "interest_rate": item.get("interest_rate"),
            "monthly_cash_freed": monthly,
            "months_remaining": item.get("months_remaining"),
            "estimated_remaining_payments": item.get("estimated_total_remaining_payments"),
            **cost,
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
        "savings": _order(rows, lambda r: r["cost_saving"]),
    }


def _sum_known(rows: list[dict], key: str) -> float | None:
    """0 for an empty selection (nothing closed = nothing released); None when loans were closed but none has the value."""
    if not rows:
        return 0.0
    known = [r[key] for r in rows if r[key] is not None]
    return round(sum(known), 2) if known else None


def _result(selected: list[dict], budget: float, skipped_over: list[str], unknown: list[str], no_data: list[str] | None = None) -> dict:
    used = round(sum(r["amount_to_close"] for r in selected), 2)
    return {
        "budget": budget,
        "used": used,
        "remaining_budget": round(budget - used, 2),
        "closed_count": len(selected),
        "closed": [{k: r[k] for k in ("id", "name", "amount_to_close", "monthly_cash_freed", "cost_saving", "cost_saving_exact")}
                   for r in selected],
        "debt_removed": used,
        "monthly_cash_released": _sum_known(selected, "monthly_cash_freed"),
        "future_cost_saved": _sum_known(selected, "cost_saving"),
        "future_cost_saved_exact": bool(selected) and all(r["cost_saving_exact"] for r in selected),
        "partial": any(r["monthly_cash_freed"] is None or r["cost_saving"] is None for r in selected),
        "skipped_over_budget": skipped_over,
        "excluded_unknown_amount": unknown,
        "excluded_no_data": no_data or [],          # loans the strategy's own metric is unknown for (never used as filler)
    }


def simulate(rows: list[dict], order: list[str], budget: float, need: str | None = None) -> dict:
    """Walk the strategy order and close every loan whose full closure amount still fits (<= remaining budget).
    A loan that does not fit is skipped whole — there is no partial payoff — and the walk continues."""
    by_id = {r["id"]: r for r in rows}
    left, selected, skipped, unknown, no_data = float(budget), [], [], [], []
    for iid in order:
        row = by_id[iid]
        amount = row["amount_to_close"]
        if amount is None:
            unknown.append(iid)
        elif need and row[need] is None:
            no_data.append(iid)                                   # e.g. the savings strategy never closes a loan whose saving is unknown
        elif amount <= left + _EPS:
            selected.append(row)
            left -= amount
        else:
            skipped.append(iid)
    return _result(selected, float(budget), skipped, unknown, no_data)


def optimal(rows: list[dict], budget: float, objective: str) -> dict | None:
    """Best whole-loan combination within the budget by ``objective`` ('cash' = monthly cash released,
    'saved' = estimated future cost saved). Exact (exhaustive) for up to MAX_OPTIMAL_LOANS eligible loans,
    otherwise None. Loans with an unknown value contribute 0 to the objective (never a guess)."""
    need = "monthly_cash_freed" if objective == "cash" else "cost_saving"
    eligible = [r for r in rows if r["amount_to_close"] is not None and r[need] is not None]
    unknown = [r["id"] for r in rows if r["amount_to_close"] is None]
    no_data = [r["id"] for r in rows if r["amount_to_close"] is not None and r[need] is None]
    if len(eligible) > MAX_OPTIMAL_LOANS:
        return None
    key = (lambda r: r["monthly_cash_freed"] or 0.0) if objective == "cash" else (lambda r: r["cost_saving"] or 0.0)
    other = (lambda r: r["cost_saving"] or 0.0) if objective == "cash" else (lambda r: r["monthly_cash_freed"] or 0.0)
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
    return _result(sorted(best, key=lambda r: r["id"]), float(budget), skipped, unknown, no_data)


def scenarios(rows: list[dict], budget: float) -> dict:
    ranks = rankings(rows)
    return {
        "budget": float(budget),
        "strategies": {s: simulate(rows, ranks[s], budget, "cost_saving" if s == "savings" else None) for s in STRATEGIES},
        "optimal": {"cash": optimal(rows, budget, "cash"), "saved": optimal(rows, budget, "saved")},
    }


def build(items: list[dict]) -> dict:
    """Payload block for the loans overview (active loans only)."""
    rows = metrics(items)
    return {"weights": dict(WEIGHTS), "items": rows, "rankings": rankings(rows)}
