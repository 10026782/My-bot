"""FCC loans timeline — pure, read-only (no I/O, no writes, no model).

The owner's question: "when does my monthly payment drop, and when does the interest become less than a quarter / 15% / … of it?" — answered from the payments
themselves, month by month, summed over the active loans the owner owes:

* each loan's payments ahead are the lender's stored schedule when there is one (exact), else the existing labelled ESTIMATE (``refinance._remaining``) — the same
  facts the refinance simulator uses; there is no second formula. A loan without balance / payment / payments left is not priced and is counted in ``of`` vs ``loans``.
* two scopes: without the mortgages (``no_mortgage``) and with them (``all``).
* every figure assumes today's rates (a prime-linked schedule is re-cut when the prime changes); estimated loans are summed apart so the exact part stays visible.
"""

from __future__ import annotations

from datetime import date

from core.financial_control import refinance

LIMITS = (0.30, 0.25, 0.20, 0.15, 0.10, 0.05)
MIN_DROP = 100.0          # a month-on-month fall of at least this much is "the payment dropped" (smaller moves are prime / rounding noise)
MORTGAGE = "משכנתא"


def _label(item: dict) -> str:
    """Loans share names ("כאל", "מקס"), so the label carries the rate and the instalment that tell them apart."""
    parts = [item["name"] or "הלוואה"]
    if item.get("interest_rate") is not None:
        parts.append(f"{item['interest_rate']:g}%")
    if item.get("monthly_payment") is not None:
        parts.append(f"₪{item['monthly_payment']:,.0f}")
    return " · ".join(parts)


def _scope(items: list[dict], schedules: dict, today: date) -> dict | None:
    months: dict[str, list[float]] = {}          # month -> [payment, interest]
    ends: dict[str, tuple[str, str]] = {}        # loan id -> (display label, last payment month)
    priced = exact = 0
    balance = interest_exact = interest_est = 0.0
    for item in items:
        rem = refinance._remaining(item, schedules.get(item["id"]), today)
        if rem is None:
            continue
        priced += 1
        exact += 1 if rem["exact"] else 0
        balance += rem["principal"]
        if rem["exact"]:
            interest_exact += rem["interest"]
        else:
            interest_est += rem["interest"]
        this_month = today.isoformat()[:7]
        # the payments of THIS calendar month count in full: a stored-schedule row dated on / before today is already "charged", yet it is part of this month's payment
        stored = [r for r in (schedules.get(item["id"]) or []) if r[0][:7] == this_month and r[0] <= today.isoformat()]
        for r in stored + list(rem["rows"]):
            m = r[0][:7]
            cell = months.setdefault(m, [0.0, 0.0])
            cell[0] += r[3]
            cell[1] += r[2]
        ends[item["id"]] = (_label(item), rem["rows"][-1][0][:7])
    if not months:
        return None
    keys = sorted(months)
    pay = {m: round(months[m][0], 2) for m in keys}
    inte = {m: round(months[m][1], 2) for m in keys}
    share = {m: (inte[m] / pay[m] if pay[m] > 0 else 0.0) for m in keys}

    drops: list[dict] = []
    for prev, cur in zip(keys, keys[1:]):
        if pay[prev] - pay[cur] < MIN_DROP:
            continue
        ended = sorted(n for n, last in ends.values() if last == prev)
        if drops and drops[-1]["_last"] == prev:             # consecutive months of one fall (a final small payment): one event
            d = drops[-1]
            d.update(to=pay[cur], drop=round(d["from"] - pay[cur], 2), interest=inte[cur], _last=cur, ended=d["ended"] + ended)
        else:
            drops.append({"month": cur, "from": pay[prev], "to": pay[cur], "drop": round(pay[prev] - pay[cur], 2), "interest": inte[cur], "ended": ended, "_last": cur})
    for d in drops:
        d.pop("_last")

    thresholds = []
    for limit in LIMITS:
        first = next((m for m in keys if share[m] < limit), None)
        if first is None:
            continue
        i = keys.index(first)
        sustained = next((m for m in keys[i:] if all(share[x] < limit for x in keys[keys.index(m):])), None)
        thresholds.append({"limit": limit, "first": first, "sustained": sustained,
                           "payment": pay[sustained] if sustained else None, "interest": inte[sustained] if sustained else None})

    yearly = [{"month": m, "payment": pay[m], "interest": inte[m], "share": round(share[m], 4)} for m in keys if m == keys[0] or m.endswith("-01")]
    if yearly[-1]["month"] != keys[-1]:
        yearly.append({"month": keys[-1], "payment": pay[keys[-1]], "interest": inte[keys[-1]], "share": round(share[keys[-1]], 4)})
    return {"loans": priced, "of": len(items), "exact": exact, "balance": round(balance, 2),
            "payment_now": pay[keys[0]], "interest_now": inte[keys[0]], "share_now": round(share[keys[0]], 4), "first_month": keys[0], "last_month": keys[-1],
            "interest_remaining": round(interest_exact + interest_est, 2), "interest_remaining_exact": round(interest_exact, 2),
            "interest_remaining_estimated": round(interest_est, 2), "drops": drops, "thresholds": thresholds, "yearly": yearly}


def build(items: list[dict], schedules: dict | None, today: date) -> dict:
    """``items``: ``loans.loan_item`` rows; ``schedules``: loan id -> parsed lender schedule. Only active loans the owner owes count."""
    mine = [i for i in items if i["active"] and i["direction"] == "owed_by_me"]
    sched = schedules or {}
    return {"no_mortgage": _scope([i for i in mine if i["loan_type"] != MORTGAGE], sched, today),
            "all": _scope(mine, sched, today),
            "assumption": "מניח שהריבית של היום נשארת; שינוי בפריים משנה את הסכומים. הלוואה בלי לוח סילוקין מחושבת כהערכה."}
