"""FCC assets & equity — pure, read-only read model over the existing ``Assets`` table (no I/O, no writes).

Values are shown exactly as stored (``Equity`` / ``My Equity`` are Airtable formulas; nothing is re-derived here).
Debt appears in two clearly separate places that are NEVER added together, because they can describe the same
loan: the asset's own ``Mortgage Balance`` field, and the active ``Loans`` linked to the asset (via Related Asset).
A missing value is ``None`` (never 0); totals skip unknown values and report how many assets they cover.
"""

from __future__ import annotations

from airtable_schema import AssetFields as AF


def _num(value) -> float | None:
    if value is None or isinstance(value, bool) or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _sel(value):
    return value.get("name") if isinstance(value, dict) else value


def _sum(values) -> tuple[float | None, int]:
    known = [v for v in values if v is not None]
    return (round(sum(known), 2) if known else None), len(known)


def asset_item(record: dict, loans_by_asset: dict[str, list[dict]]) -> dict:
    f = record.get("fields") or {}
    linked = loans_by_asset.get(record.get("id"), [])
    debt, debt_known = _sum(l["early_closure_balance"] for l in linked)
    pay, _ = _sum(l["monthly_payment"] for l in linked)
    return {
        "id": record.get("id"),
        "name": f.get(AF.NAME) or None,
        "asset_type": _sel(f.get(AF.TYPE)),
        "status": _sel(f.get(AF.STATUS)),
        "current_value": _num(f.get(AF.VALUE)),
        "monthly_income": _num(f.get(AF.MONTHLY_INCOME)),
        "mortgage_balance": _num(f.get(AF.MORTGAGE)),
        "ownership_pct": _num(f.get(AF.OWNERSHIP_PCT)),
        "next_step": (f.get(AF.NEXT_STEP) or "").strip() or None,
        "next_step_owner": _sel(f.get(AF.NEXT_STEP_OWNER)) or None,
        "equity": _num(f.get(AF.EQUITY)),
        "my_equity": _num(f.get(AF.MY_EQUITY)),
        "linked_loans": [{k: l[k] for k in ("id", "name", "loan_type", "early_closure_balance", "monthly_payment", "interest_rate")}
                         for l in linked],
        "linked_debt": debt,                       # None when no linked loan has a closure balance
        "linked_debt_known": debt_known,
        "linked_monthly_payments": pay,
    }


def summarize(items: list[dict], loan_items: list[dict]) -> dict:
    value, value_n = _sum(i["current_value"] for i in items)
    mort, mort_n = _sum(i["mortgage_balance"] for i in items)
    eq, eq_n = _sum(i["equity"] for i in items)
    my_eq, my_eq_n = _sum(i["my_equity"] for i in items)
    income, income_n = _sum(i["monthly_income"] for i in items)
    linked_ids = {l["id"] for i in items for l in i["linked_loans"]}
    active = [l for l in loan_items if l.get("active")]
    unlinked = [l for l in active if l["id"] not in linked_ids]
    linked_debt, _ = _sum(l["early_closure_balance"] for l in active if l["id"] in linked_ids)
    unlinked_debt, _ = _sum(l["early_closure_balance"] for l in unlinked)
    return {
        "count": len(items),
        "total_value": value, "total_mortgage": mort, "total_equity": eq, "total_my_equity": my_eq, "total_monthly_income": income,
        "coverage": {"value": value_n, "mortgage": mort_n, "equity": eq_n, "my_equity": my_eq_n, "monthly_income": income_n},
        "linked_loans_count": len(linked_ids), "linked_loans_debt": linked_debt,
        "unlinked_loans_count": len(unlinked), "unlinked_loans_debt": unlinked_debt,       # debt that belongs to no asset
    }


SOLD = "נמכר"          # live Assets.Status choice


def sold_item(record: dict, loans_by_asset: dict[str, list[dict]]) -> dict:
    """A sold asset, shown apart from the active ones: sale date / full price / MY share (price × Ownership %).
    An unknown ownership % leaves the share unknown — 100% is never assumed. Linked loans stay what they are (open)."""
    f = record.get("fields") or {}
    amount, pct = _num(f.get(AF.SALE_AMOUNT)), _num(f.get(AF.OWNERSHIP_PCT))
    linked = loans_by_asset.get(record.get("id"), [])
    return {
        "id": record.get("id"),
        "name": f.get(AF.NAME) or None,
        "sale_date": f.get(AF.SALE_DATE) or None,
        "sale_amount": amount,
        "ownership_pct": pct,
        "my_share": round(amount * pct / 100.0, 2) if amount is not None and pct is not None else None,
        "linked_loans": [{k: l[k] for k in ("id", "name", "early_closure_balance")} for l in linked],
    }


def my_equity(item: dict) -> float | None:
    """The owner's share of the asset's equity: the stored ``My Equity`` when Airtable has it, else (value − the asset's own mortgage)
    × ownership %. Any missing input leaves it unknown (a missing mortgage is not 0 and an unknown ownership is not 100%)."""
    if item["my_equity"] is not None:
        return item["my_equity"]
    v, m, p = item["current_value"], item["mortgage_balance"], item["ownership_pct"]
    return round((v - m) * p / 100.0, 2) if None not in (v, m, p) else None


def personal_equity(items: list[dict], balance: dict | None) -> dict:
    """Personal equity = the owner's share of his active assets + the NET debt position (receivables − own debts not already in an
    asset): a positive net is shown as a financial asset, a negative one is not an asset but still reduces the total."""
    shares = [my_equity(i) for i in items]
    assets_total, known = _sum(shares)
    net = balance.get("net") if balance else None
    total = None if assets_total is None and net is None else round((assets_total or 0.0) + (net or 0.0), 2)
    missing = (balance.get("missing_receivables", 0) + balance.get("missing_liabilities", 0)) if balance else 0
    return {"assets_my_equity": assets_total, "assets_known": known, "assets_count": len(items),
            "financial_asset": balance.get("financial_asset") if balance else None, "net_debt": balance.get("net_debt") if balance else None,
            "net": net, "total": total, "partial": known < len(items) or missing > 0}


def build(records: list[dict], loan_items: list[dict], tasks: list[dict] | None = None, balance: dict | None = None) -> dict:
    """Owner-scoped asset ``records`` + the owner's loan items (``loans.loan_item`` rows) -> screen payload. ``balance`` is the
    receivables-vs-own-debts position (``loans.debt_balance``); it feeds the personal equity only."""
    loans_by_asset: dict[str, list[dict]] = {}
    for loan in loan_items:
        if loan.get("active") and loan.get("related_asset"):
            loans_by_asset.setdefault(loan["related_asset"], []).append(loan)
    sold_records = [r for r in records if _sel((r.get("fields") or {}).get(AF.STATUS)) == SOLD]
    sold = [sold_item(r, loans_by_asset) for r in sold_records]
    sold.sort(key=lambda i: (i["sale_date"] or "", i["name"] or ""), reverse=True)
    # Active assets only feed the totals. A sold asset is NOT deleted from the owner's wealth — it became proceeds that
    # this screen does not track — so the totals are "active assets", never a total net worth (the UI says so).
    items = [asset_item(r, loans_by_asset) for r in records if r not in sold_records]
    items.sort(key=lambda i: (-(i["current_value"] or 0), i["name"] or ""))
    for item in items:                                       # the OPEN next actions of this asset (several allowed), soonest first
        item["actions"] = [{k: t[k] for k in ("id", "title", "status", "due_date", "owner", "history")}
                           for t in (tasks or []) if t.get("asset_id") == item["id"]]
    summary = summarize(items, loan_items)
    summary["personal_equity"] = personal_equity(items, balance)
    return {"items": items, "summary": summary, "sold": {"count": len(sold), "items": sold}}
