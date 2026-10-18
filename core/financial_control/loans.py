"""FCC loans & debt — pure read model over the existing ``Loans`` table (no I/O here).

Unknown stays unknown: a missing number is ``None`` (never 0), a derived value is ``None`` when any input is
missing, and a derived cost is flagged ``future_cost_exact=False`` while the early-repayment fee is blank or
non-numeric. Sums/averages skip unknown values and report how many loans they cover, so a partial record
(e.g. a mortgage with no details) can never drag a total or an average toward zero.
"""

from __future__ import annotations

import calendar
import re
from datetime import date

from airtable_schema import LoanFields as LF
from core.financial_control import payoff

OWED_BY_ME, OWED_TO_ME = "owed_by_me", "owed_to_me"       # a debt of the owner / a debt owed TO the owner (Loans.Direction)
DIRECTION_TO_ME_STORED = "חייבים לי"                       # the live Loans.Direction choice for OWED_TO_ME; empty or anything else = OWED_BY_ME
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
    monthly = _num(f.get(LF.MONTHLY_PAYMENT))
    rate = _num(f.get(LF.INTEREST_RATE))
    left = _num(f.get(LF.PAYMENTS_LEFT))
    end = _iso_date(f.get(LF.END_DATE))
    fee_amount, fee_known = parse_fee(f.get(LF.EARLY_FEE))
    next_due = _iso_date(f.get(LF.NEXT_PAYMENT))
    direction = OWED_TO_ME if str(_sel(f.get(LF.DIRECTION)) or "").strip() == DIRECTION_TO_ME_STORED else OWED_BY_ME      # tolerant of a stray space in the choice name

    months = int(left) if left is not None else (_months_between(today, end) if end else None)
    total_remaining = round(monthly * left, 2) if monthly is not None and left is not None else None
    future_cost = round(total_remaining - closure, 2) if total_remaining is not None and closure is not None else None
    if future_cost is not None and future_cost < 0:
        future_cost = None                      # inconsistent inputs: show unknown rather than a negative "cost"
    annual_interest = round(closure * rate / 100.0, 2) if closure is not None and rate is not None else None   # SSOT balance only

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
        "early_closure_balance": closure,
        "interest_rate": rate,
        "monthly_payment": monthly,
        "payments_remaining": int(left) if left is not None else None,
        "end_date": end.isoformat() if end else None,
        "early_repayment_fee": str(f.get(LF.EARLY_FEE)).strip() if f.get(LF.EARLY_FEE) else None,
        "early_fee_amount": fee_amount,
        "active": is_active(f),
        "direction": direction,
        # how the debt is repaid: a standing monthly amount, a deadline, or nothing recorded yet (None = ask the owner)
        "arrangement": "monthly" if monthly else "deadline" if end else None,
        "next_payment_due": next_due.isoformat() if next_due else None,
        "payments_done": left == 0,                   # every instalment paid: the owner confirms the closing (never closed automatically)
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
    # SSOT: the early-closure principal is THE balance; Loans."Outstanding Balance" is legacy and never read here
    weighted = [(i["interest_rate"], i["early_closure_balance"]) for i in active if i["interest_rate"] is not None]
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


# ── Monthly auto-step: the balance follows the loan's own schedule ───────────────────────────────────────────────────
def _due_on(year: int, month: int, day: int) -> date:
    """The due day of a month, clamped to the month's last day (a 31st becomes the 30th / 28th)."""
    return date(year, month, min(day, calendar.monthrange(year, month)[1]))


def _plus_month(d: date, day: int) -> date:
    year, month = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    return _due_on(year, month, day)


def _shekel(x: float) -> str:
    return f"₪{x:,.2f}"


def advance_due(fields: dict, today: date) -> str | None:
    """After the owner corrects the balance ("as of today") while its due date has already passed: the date the monthly job should
    wait for instead — the first due day after today — so the instalment already inside the corrected balance is not applied again.
    None when there is nothing to move (no / future ``Next Payment Due``, or no usable ``Monthly Due Day``)."""
    nd, day = _iso_date(fields.get(LF.NEXT_PAYMENT)), _num(fields.get(LF.DUE_DAY))
    if nd is None or nd > today or day is None or not 1 <= day <= 31:
        return None
    this = _due_on(today.year, today.month, int(day))
    return (this if this > today else _plus_month(this, int(day))).isoformat()


AUTO_MAX_STEPS = 12          # a longer gap (the job was off for a year) is applied in slices, never in one leap


def auto_step(record: dict, today: date) -> dict | None:
    """What the monthly job does for ONE of the owner's loans, or None when nothing is due.

    On each due date the instalment is applied in the standard way: ``balance × (1 + annual rate / 12) − payment``, the number of
    payments remaining drops by one and ``Next Payment Due`` moves a month on (the last payment brings the balance to 0). The loan is
    NOT closed here — a finished schedule only shows "payments done". ``Next Payment Due`` is also the idempotency key: a loan is
    touched only when it is due, so a second run the same day writes nothing. The first time (no ``Next Payment Due``) the job only
    sets it from ``Monthly Due Day``, because the stored balance is already as of today.
    Returns ``{"action": "init" | "step" | "skip", "fields": {...}, ...}``. A loan with a missing input, or a payment that does not even
    cover the interest, is skipped with a reason — a balance is never invented."""
    f = record.get("fields") or {}
    owed_to_me = str(_sel(f.get(LF.DIRECTION)) or "").strip() == DIRECTION_TO_ME_STORED
    if not is_active(f) or owed_to_me:
        return None                                               # closed loans and debts owed TO the owner are not stepped
    balance, rate, pay = _num(f.get(LF.EARLY_CLOSURE)), _num(f.get(LF.INTEREST_RATE)), _num(f.get(LF.MONTHLY_PAYMENT))
    left, due_day, next_due = _num(f.get(LF.PAYMENTS_LEFT)), _num(f.get(LF.DUE_DAY)), _iso_date(f.get(LF.NEXT_PAYMENT))
    name = f.get(LF.NAME) or record.get("id")
    base = {"id": record.get("id"), "name": name}

    def skip(reason: str) -> dict:
        return {**base, "action": "skip", "reason": reason, "fields": {}}

    day = int(due_day) if due_day is not None and 1 <= due_day <= 31 else None
    if next_due is None:                                           # first run: only learn the next due date
        if day is None:
            return skip("no_due_day")
        this = _due_on(today.year, today.month, day)
        nxt = this if this >= today else _plus_month(this, day)
        return {**base, "action": "init", "fields": {LF.NEXT_PAYMENT: nxt.isoformat()}, "next_due": nxt.isoformat()}
    if next_due > today:
        return None                                                # not due yet
    if left is not None and left <= 0 or balance is not None and balance <= 0:
        return None                                                # schedule finished: shown as "payments done"
    if balance is None or rate is None or pay is None or pay <= 0:
        return skip("missing_input")
    monthly = rate / 100.0 / 12.0
    if pay <= balance * monthly:
        return skip("payment_below_interest")                      # would grow the balance: the data needs a look, not a step
    bal, lp, nd, steps = balance, left, next_due, 0
    while nd <= today and steps < AUTO_MAX_STEPS and bal > 0 and (lp is None or lp > 0):
        bal = 0.0 if lp == 1 else round(max(bal * (1 + monthly) - pay, 0.0), 2)
        lp = lp - 1 if lp is not None else None
        nd = _plus_month(nd, day or nd.day)
        steps += 1
    line = f"עדכון אוטומטי ({today.isoformat()}): {steps} תשלומים — יתרה {_shekel(balance)} ← {_shekel(bal)}"
    notes = "\n".join(x for x in (str(f.get(LF.NOTES) or "").strip(), line) if x)
    fields = {LF.EARLY_CLOSURE: bal, LF.NEXT_PAYMENT: nd.isoformat(), LF.NOTES: notes}
    if lp is not None:
        fields[LF.PAYMENTS_LEFT] = int(lp)
    return {**base, "action": "step", "fields": fields, "steps": steps, "before": balance, "after": bal, "payments_left": lp,
            "next_due": nd.isoformat(), "behind": nd <= today}


# ── Prime-rate change: every prime-linked loan of the owner moves together ───────────────────────────────────────────
PRIME_MAX_STEP = 5.0         # a single change larger than this (in percentage points) is a typo, not a decision


def _pmt(balance: float, rate: float, n: int) -> float:
    """Instalment that repays ``balance`` in ``n`` months at an annual ``rate`` (%)."""
    i = rate / 1200.0
    return balance / n if i == 0 else balance * i / (1 - (1 + i) ** -n)


pmt = _pmt                          # public name for other read models (the funding planner); one formula, no copy


def prime_rows(records: list[dict], today: date) -> list[dict]:
    """The owner's loans a prime change touches: active, his own debts (not owed TO him), with a known rate. Captured when the
    draft opens, so the review and the writes use the same numbers. All the owner's loans are prime-linked (owner decision)."""
    rows = []
    for rec in records:
        item = loan_item(rec, today)
        if not item["active"] or item["direction"] != OWED_BY_ME or item["interest_rate"] is None:
            continue
        rows.append({"id": item["id"], "name": item["name"], "rate": item["interest_rate"], "payment": item["monthly_payment"],
                     "balance": item["early_closure_balance"], "left": item["payments_remaining"],
                     "notes": str((rec.get("fields") or {}).get(LF.NOTES) or "")})
    return rows


def prime_plan(rows: list[dict], delta: float) -> list[dict]:
    """Per loan: the new rate and — when the loan has a balance, a payment and payments remaining — the new monthly payment, i.e. the
    SAME payment scaled by the instalment ratio at the new vs the old rate over the remaining term (the end date stays; the bank's own
    baseline is kept, not a generic formula). Missing inputs leave the payment alone (rate only); a rate that would go negative skips."""
    out = []
    for r in rows:
        new_rate = round(r["rate"] + delta, 2)
        entry = {"id": r["id"], "name": r["name"], "old_rate": r["rate"], "new_rate": new_rate, "old_payment": r["payment"],
                 "new_payment": None, "skip": None}
        if new_rate < 0:
            entry["skip"] = "negative_rate"
        elif r["payment"] and r["balance"] and r["left"] and r["left"] >= 1:
            base, moved = _pmt(r["balance"], r["rate"], int(r["left"])), _pmt(r["balance"], new_rate, int(r["left"]))
            if base > 0:
                entry["new_payment"] = round(r["payment"] * moved / base, 2)
        out.append(entry)
    return out


def debt_balance(items: list[dict]) -> dict:
    """What is owed TO the owner against what the owner owes: ``net`` > 0 is a net financial asset, ``net`` < 0 is not an asset
    (it still reduces the personal equity). The owner's loans that are linked to an asset (``Related Asset``) are left out of the
    net: that debt already sits inside the asset's own equity, and counting it here would count it twice. Unknown balances are
    skipped and reported, never turned into 0; ``net`` is None only when there is no known balance at all."""
    active = [i for i in items if i["active"]]
    recv = [i for i in active if i["direction"] == OWED_TO_ME]
    mine = [i for i in active if i["direction"] == OWED_BY_ME]
    counted = [i for i in mine if not i["related_asset"]]
    linked = [i for i in mine if i["related_asset"]]
    r_total, r_known = _sum(i["early_closure_balance"] for i in recv)
    l_total, l_known = _sum(i["early_closure_balance"] for i in counted)
    linked_total, _ = _sum(i["early_closure_balance"] for i in linked)
    net = round((r_total or 0.0) - (l_total or 0.0), 2) if (r_known or l_known) else None
    return {
        "receivables_total": r_total or 0.0, "liabilities_total": l_total or 0.0, "net": net,
        "financial_asset": max(net, 0.0) if net is not None else None,         # a negative net is NOT an asset
        "net_debt": min(net, 0.0) if net is not None else None,
        "linked_excluded_count": len(linked), "linked_excluded_total": linked_total or 0.0,
        "missing_receivables": len(recv) - r_known, "missing_liabilities": len(counted) - l_known,
        "receivables_count": len(recv),
    }


def receivables(items: list[dict]) -> dict:
    """Debts owed TO the owner: listed and totalled apart. They are never part of the owner's liabilities, the rankings or the
    payoff simulation, and money received on them is not income."""
    active = [i for i in items if i["active"] and i["direction"] == OWED_TO_ME]
    total, known = _sum(i["early_closure_balance"] for i in active)
    return {"count": len(active), "total_balance": total, "coverage": known,
            "no_arrangement": sum(1 for i in active if i["arrangement"] is None)}


def build(records: list[dict], today: date, asset_names: dict[str, str] | None = None,
          debt_goal: dict | None = None, tasks: list[dict] | None = None) -> dict:
    """Owner-scoped ``records`` (already policy-filtered) -> screen payload. ``debt_goal`` is the existing
    Financial Goals debt card (the SSOT of the closing target) and is only passed through. ``tasks`` are the owner's open
    next actions of loans (each item lists its own)."""
    items = [loan_item(r, today, asset_names) for r in records]
    for item in items:                                       # the OPEN next actions of this loan / debt, soonest first
        item["actions"] = [{k: t[k] for k in ("id", "title", "status", "due_date", "owner", "history")}
                           for t in (tasks or []) if t.get("subject_id") == item["id"]]
    mine = [i for i in items if i["direction"] == OWED_BY_ME]
    active_items = [i for i in mine if i["active"]]
    summary = summarize(mine)
    goal = None
    if debt_goal and debt_goal.get("target") is not None:
        goal = {"target": debt_goal["target"], "closed": debt_goal.get("actual"), "remaining": debt_goal.get("remaining"),
                "active_closure_balance": summary["total_early_closure_balance"]}
    return {"items": items, "summary": summary, "rankings": rankings(active_items), "goal": goal,
            "payoff": payoff.build(active_items), "receivables": receivables(items),
            "balance": debt_balance(items)}


def scenarios(records: list[dict], today: date, budget: float) -> dict:
    """Budget simulator over the owner's active loans (read-only; nothing is executed or written)."""
    items = [loan_item(r, today) for r in records]
    return payoff.scenarios(payoff.metrics([i for i in items if i["active"] and i["direction"] == OWED_BY_ME]), budget)
