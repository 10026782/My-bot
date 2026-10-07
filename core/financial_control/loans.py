"""FCC loans & debt — pure read model over the existing ``Loans`` table (no I/O here).

Unknown stays unknown: a missing number is ``None`` (never 0), a derived value is ``None`` when any input is
missing, and a derived cost is flagged ``future_cost_exact=False`` while the early-repayment fee is blank or
non-numeric. Sums/averages skip unknown values and report how many loans they cover, so a partial record
(e.g. a mortgage with no details) can never drag a total or an average toward zero.
"""

from __future__ import annotations

import re
from datetime import date

from airtable_schema import LoanFields as LF

UNCLASSIFIED = "לא סווג"
LOAN_TYPES = ("פרטית", "עסקית", "משכנתא")
_PAID_OFF = "paid off"
_NO_FEE = {"אין", "ללא", "0", "none", "no", "-"}
_NUM_FEE = re.compile(r"^[₪\s]*([0-9][0-9,]*(?:\.[0-9]+)?)\s*(?:₪|ש\"ח|שח)?\s*$")


def _num(value) -> float | None:
    if value is None or isinstance(value, bool) or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _sel(value):
    return value.get("name") if isinstance(value, dict) else value


def _first_link(value) -> str | None:
    if isinstance(value, list) and value:
        head = value[0]
        return head.get("id") if isinstance(head, dict) else head if isinstance(head, str) else None
    return None


def parse_fee(text) -> tuple[float | None, bool]:
    """-> (amount, known). "אין" = known zero; a plain number = known amount; blank or free text ("2%") = unknown."""
    raw = str(text or "").strip()
    if not raw:
        return None, False
    if raw.casefold() in _NO_FEE:
        return 0.0, True
    m = _NUM_FEE.match(raw)
    if m:
        return float(m.group(1).replace(",", "")), True
    return None, False


def _months_between(start: date, end: date) -> int | None:
    months = (end.year - start.year) * 12 + (end.month - start.month)
    return months if months >= 0 else None


def _iso_date(value) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10]) if value else None
    except ValueError:
        return None


def is_active(fields: dict) -> bool:
    """Active unless the loan is marked Paid Off. Airtable does not distinguish an unchecked ``Active Loan``
    box from a never-filled one, so the checkbox alone cannot close a loan; use Payment Status = Paid Off."""
    return str(_sel(fields.get(LF.STATUS)) or "").strip().casefold() != _PAID_OFF


def status_unknown(fields: dict) -> bool:
    """Active Loan unchecked (or never filled — Airtable cannot tell) AND not Paid Off: the loan is kept visible and
    counted, but flagged so the owner can confirm it."""
    return not fields.get(LF.ACTIVE) and is_active(fields)


def loan_item(record: dict, today: date, asset_names: dict[str, str] | None = None) -> dict:
    f = record.get("fields") or {}
    loan_type = _sel(f.get(LF.LOAN_TYPE))
    loan_type = loan_type if loan_type in LOAN_TYPES else None
    asset_id = _first_link(f.get(LF.RELATED_ASSET))
    closure = _num(f.get(LF.EARLY_CLOSURE))
    balance = _num(f.get(LF.OUTSTANDING))
    monthly = _num(f.get(LF.MONTHLY_PAYMENT))
    rate = _num(f.get(LF.INTEREST_RATE))
    left = _num(f.get(LF.PAYMENTS_LEFT))
    end = _iso_date(f.get(LF.END_DATE))
    fee_amount, fee_known = parse_fee(f.get(LF.EARLY_FEE))

    months = int(left) if left is not None else (_months_between(today, end) if end else None)
    total_remaining = round(monthly * left, 2) if monthly is not None and left is not None else None
    future_cost = round(total_remaining - closure, 2) if total_remaining is not None and closure is not None else None
    if future_cost is not None and future_cost < 0:
        future_cost = None                      # inconsistent inputs: show unknown rather than a negative "cost"
    basis = closure if closure is not None else balance
    annual_interest = round(basis * rate / 100.0, 2) if basis is not None and rate is not None else None

    missing = [name for name, v in (("early_closure_balance", closure), ("interest_rate", rate),
                                    ("monthly_payment", monthly), ("months_remaining", months)) if v is None]
    return {
        "id": record.get("id"),
        "name": f.get(LF.NAME) or None,
        "lender": f.get(LF.LENDER) or None,
        "loan_type": loan_type,
        "related_asset": asset_id,
        "related_asset_name": (asset_names or {}).get(asset_id) if asset_id else None,
        "original_amount": _num(f.get(LF.AMOUNT)),
        "current_balance": balance,
        "early_closure_balance": closure,
        "interest_rate": rate,
        "monthly_payment": monthly,
        "payments_remaining": int(left) if left is not None else None,
        "end_date": end.isoformat() if end else None,
        "early_repayment_fee": str(f.get(LF.EARLY_FEE)).strip() if f.get(LF.EARLY_FEE) else None,
        "early_fee_amount": fee_amount,
        "active": is_active(f),
        "status_unknown": status_unknown(f),
        # derived
        "months_remaining": months,
        "estimated_total_remaining_payments": total_remaining,
        "estimated_future_cost": future_cost,
        "future_cost_exact": future_cost is not None and fee_known,
        "monthly_cash_freed_if_closed": monthly,
        "annual_interest_cost": annual_interest,       # simple burden metric: balance × rate (₪/year)
        "missing": missing,
    }


def _sum(values) -> tuple[float | None, int]:
    known = [v for v in values if v is not None]
    return (round(sum(known), 2) if known else None), len(known)


def _bucket(items: list[dict]) -> dict:
    bal, _ = _sum(i["early_closure_balance"] for i in items)
    pay, _ = _sum(i["monthly_payment"] for i in items)
    return {"count": len(items), "early_closure_balance": bal, "monthly_payments": pay}


def _order(items: list[dict], key, reverse: bool) -> list[str]:
    known = [i for i in items if key(i) is not None]
    unknown = [i for i in items if key(i) is None]
    known.sort(key=lambda i: (key(i), i["name"] or ""), reverse=reverse)
    unknown.sort(key=lambda i: i["name"] or i["id"] or "")
    return [i["id"] for i in known + unknown]


def rankings(items: list[dict]) -> dict[str, list[str]]:
    """Three views for the owner to choose from — never an automatic "close this one" decision."""
    return {
        "high_interest": _order(items, lambda i: i["interest_rate"], True),
        "cash_freed": _order(items, lambda i: i["monthly_cash_freed_if_closed"], True),
        "small_balance": _order(items, lambda i: i["early_closure_balance"], False),
    }


def summarize(items: list[dict]) -> dict:
    active = [i for i in items if i["active"]]
    orig, orig_n = _sum(i["original_amount"] for i in active)
    bal, bal_n = _sum(i["early_closure_balance"] for i in active)
    pay, pay_n = _sum(i["monthly_payment"] for i in active)
    cost, cost_n = _sum(i["estimated_future_cost"] for i in active)
    weighted = [(i["interest_rate"], i["early_closure_balance"] if i["early_closure_balance"] is not None else i["current_balance"])
                for i in active if i["interest_rate"] is not None]
    weighted = [(r, b) for r, b in weighted if b]
    total_b = sum(b for _, b in weighted)
    avg_rate = round(sum(r * b for r, b in weighted) / total_b, 2) if total_b else None

    by_type: dict[str, list[dict]] = {}
    by_asset: dict[str, list[dict]] = {}
    for i in active:
        by_type.setdefault(i["loan_type"] or UNCLASSIFIED, []).append(i)
        if i["related_asset"]:
            by_asset.setdefault(i["related_asset"], []).append(i)
    return {
        "total_active_loans": len(active),
        "total_original_amount": orig,
        "total_early_closure_balance": bal,
        "total_monthly_payments": pay,
        "weighted_average_interest_rate": avg_rate,
        "total_estimated_future_cost": cost,
        "total_monthly_cash_freed_if_all_closed": pay,
        # how many loans each figure is actually based on (a total over 4 of 9 loans must not look complete)
        "coverage": {"original_amount": orig_n, "early_closure_balance": bal_n, "monthly_payment": pay_n,
                     "future_cost": cost_n, "interest_rate": len(weighted)},
        "unknown_status_count": sum(1 for i in active if i["status_unknown"]),
        "incomplete_count": sum(1 for i in active if i["missing"]),
        "future_cost_exact": bool(cost_n) and all(i["future_cost_exact"] for i in active if i["estimated_future_cost"] is not None),
        "by_type": {k: _bucket(v) for k, v in by_type.items()},
        "by_asset": [{"asset_id": aid, "asset_name": v[0]["related_asset_name"], **_bucket(v)} for aid, v in by_asset.items()],
    }


def build(records: list[dict], today: date, asset_names: dict[str, str] | None = None,
          debt_goal: dict | None = None) -> dict:
    """Owner-scoped ``records`` (already policy-filtered) -> screen payload. ``debt_goal`` is the existing
    Financial Goals debt card (the SSOT of the closing target) and is only passed through."""
    items = [loan_item(r, today, asset_names) for r in records]
    active_items = [i for i in items if i["active"]]
    summary = summarize(items)
    goal = None
    if debt_goal and debt_goal.get("target") is not None:
        goal = {"target": debt_goal["target"], "closed": debt_goal.get("actual"), "remaining": debt_goal.get("remaining"),
                "active_closure_balance": summary["total_early_closure_balance"]}
    return {"items": items, "summary": summary, "rankings": rankings(active_items), "goal": goal}
