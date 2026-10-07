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


def build(records: list[dict], loan_items: list[dict]) -> dict:
    """Owner-scoped asset ``records`` + the owner's loan items (``loans.loan_item`` rows) -> screen payload."""
    loans_by_asset: dict[str, list[dict]] = {}
    for loan in loan_items:
        if loan.get("active") and loan.get("related_asset"):
            loans_by_asset.setdefault(loan["related_asset"], []).append(loan)
    items = [asset_item(r, loans_by_asset) for r in records]
    items.sort(key=lambda i: (-(i["current_value"] or 0), i["name"] or ""))
    return {"items": items, "summary": summarize(items, loan_items)}
