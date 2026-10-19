"""FCC unified net worth — pure, read-only read model (C2). No I/O, no writes, no estimates.

Net worth = account value (latest REPORTED balance, never the movements-based estimate)
          + asset value (the stored ``Current Value`` × ``Ownership %``; never estimated here)
          − liabilities (the owner's own active debts).

Iron rules against double counting / invention:
* a debt that sits on an asset is deducted ONCE: the active ``Loans`` linked to the asset (Related Asset) are the owner's own liability and
  are deducted at their FULL recorded balance — the ownership % applies to the asset's VALUE only, never to a recorded loan (liability
  share != ownership share). When a linked loan exists the asset's own ``Mortgage Balance`` is never used, not even as a fallback for a
  linked loan with no balance (that loan stays "missing"). With no linked loan, a ``Mortgage Balance`` on the asset is the conservative
  case: deducted in full as a SEPARATE debt whose liability share is unknown, and the result is flagged partial / unverified;
* a missing asset value or ownership % takes the ASSET out of the assets total (no 100% assumed, no valuation) but never its known debt —
  the debt stays deducted and the net is flagged partial / unverified, so a missing asset field can only lower the net, never inflate it;
* a sold asset leaves the net worth (its value is not counted);
* "owed TO me" (receivables) is neither income nor existing money: shown apart as expected / uncertain, never in the net;
* a missing input is ``None`` / "missing" (never 0, never 100% ownership); an asset with an unknown value or ownership is left out of
  the totals as a whole (value and its debt) and reported, so the result is ``partial`` instead of silently wrong;
* assets and loans carry no "updated at" field in Airtable: their ``as_of`` is None (unknown), never invented. Account balances carry the
  date of the last snapshot and are classed current / stale (older than ``STALE_AFTER_DAYS``, exposed in the payload) / missing. No tax.
"""

from __future__ import annotations

from datetime import date

from core.financial_control import assets as fcc_assets
from core.financial_control import loans as fcc_loans


STALE_AFTER_DAYS = 90          # an account balance older than this is "stale" (server-side, exposed to the screen)


def _sum(values) -> float | None:
    known = [v for v in values if v is not None]
    return round(sum(known), 2) if known else None


def _share(amount: float | None, pct: float | None) -> float | None:
    return round(amount * pct / 100.0, 2) if amount is not None and pct is not None else None


def _age_days(as_of: str, today: date) -> int | None:
    try:
        return (today - date.fromisoformat(as_of)).days
    except ValueError:
        return None


def _accounts_part(view: dict, today: date) -> dict:
    rows = []
    for a in (view or {}).get("accounts", []):
        if a.get("status") == "closed" or not a.get("balance"):
            continue
        age = _age_days(a["balance"]["as_of"], today)
        rows.append({"id": a["id"], "name": a.get("name"), "value": a["balance"]["value"], "as_of": a["balance"]["as_of"],
                     "verification": a["balance"]["verification"], "age_days": age,
                     "freshness": "stale" if age is None or age > STALE_AFTER_DAYS else "current"})
    missing = [{"id": a["id"], "name": a.get("name")} for a in (view or {}).get("accounts", [])
               if a.get("status") != "closed" and not a.get("balance")]
    return {"total": _sum(r["value"] for r in rows), "items": rows, "missing": missing,
            "oldest_as_of": min((r["as_of"] for r in rows), default=None), "stale_after_days": STALE_AFTER_DAYS,
            "freshness": {"current": sum(1 for r in rows if r["freshness"] == "current"),
                          "stale": sum(1 for r in rows if r["freshness"] == "stale"), "missing": len(missing)}}


def _asset_row(item: dict, mine_loans: list[dict]) -> dict:
    """One active asset: its share of the VALUE (by ownership %) and the single debt that sits on it (recorded loans in full)."""
    linked = [l for l in mine_loans if l["related_asset"] == item["id"]]
    known = [l for l in linked if l["early_closure_balance"] is not None]
    if linked:                                   # the owner's own loans: full recorded balance; a loan without one stays missing
        source, debt, unknown_debts, responsibility = "linked_loans", _sum(l["early_closure_balance"] for l in known), len(linked) - len(known), True
    elif item["mortgage_balance"] is not None:   # no loan record: deducted in full, liability share unknown (conservative)
        source, debt, unknown_debts, responsibility = "asset_mortgage", item["mortgage_balance"], 0, False
    else:
        source, debt, unknown_debts, responsibility = None, None, 0, True
    pct, value = item["ownership_pct"], item["current_value"]
    reasons = [r for r, v in (("missing_value", value), ("missing_ownership", pct)) if v is None]
    return {
        "id": item["id"], "name": item["name"], "asset_type": item["asset_type"], "as_of": None,
        "gross_value": value, "ownership_pct": pct,
        "value": _share(value, pct),
        "debt_source": source, "debt": debt, "debt_responsibility_known": responsibility, "unknown_debt_loans": unknown_debts,
        "ignored_mortgage_balance": item["mortgage_balance"] if source == "linked_loans" else None,   # same debt, shown, NOT deducted
        "counted": not reasons, "missing": reasons,
    }


def net_worth(accounts_view: dict, asset_records: list[dict], loan_items: list[dict], today: date) -> dict:
    """Owner-scoped inputs (already policy-filtered): ``accounts_view`` = ``accounts.accounts_overview`` output, ``asset_records`` = raw
    Assets rows, ``loan_items`` = ``loans.loan_item`` rows. Returns the broken-down net worth."""
    active_loans = [l for l in loan_items if l["active"]]
    mine_loans = [l for l in active_loans if l["direction"] == fcc_loans.OWED_BY_ME]
    receivable_loans = [l for l in active_loans if l["direction"] == fcc_loans.OWED_TO_ME]

    sold_ids = {r.get("id") for r in asset_records if fcc_assets._sel((r.get("fields") or {}).get(fcc_assets.AF.STATUS)) == fcc_assets.SOLD}
    live = [r for r in asset_records if r.get("id") not in sold_ids]
    loans_by_asset: dict[str, list[dict]] = {}
    for l in mine_loans:
        if l["related_asset"]:
            loans_by_asset.setdefault(l["related_asset"], []).append(l)
    asset_rows = [_asset_row(fcc_assets.asset_item(r, loans_by_asset), mine_loans) for r in live]
    asset_rows.sort(key=lambda a: (-(a["value"] or 0), a["name"] or ""))
    live_ids = {a["id"] for a in asset_rows}

    # a loan on an active asset is handled in that asset's row; every other active own debt stands alone and is deducted in full
    standalone = [{"id": l["id"], "name": l["name"], "loan_type": l["loan_type"], "balance": l["early_closure_balance"], "as_of": None,
                   "note": "linked_to_sold_asset" if l["related_asset"] and l["related_asset"] in sold_ids
                           else "asset_not_found" if l["related_asset"] else None}
                  for l in mine_loans if l["related_asset"] not in live_ids]

    accounts = _accounts_part(accounts_view, today)
    counted = [a for a in asset_rows if a["counted"]]
    assets_total = _sum(a["value"] for a in counted)
    asset_debt = _sum(a["debt"] for a in asset_rows)          # a known debt stays even when the asset's own value/ownership is missing
    standalone_debt = _sum(s["balance"] for s in standalone)
    liabilities_total = _sum([asset_debt, standalone_debt])

    unknown_balance = sum(1 for s in standalone if s["balance"] is None) + sum(a["unknown_debt_loans"] for a in asset_rows)
    parts = [accounts["total"], assets_total, liabilities_total]
    net = None if all(p is None for p in parts) else round((accounts["total"] or 0.0) + (assets_total or 0.0) - (liabilities_total or 0.0), 2)
    gaps = {"accounts_without_balance": len(accounts["missing"]), "assets_left_out": len(asset_rows) - len(counted),
            "debts_without_balance": unknown_balance,
            "asset_debts_unverified": sum(1 for a in asset_rows if a["debt_source"] == "asset_mortgage")}

    recv = fcc_loans.receivables(loan_items)
    return {
        "as_of": today.isoformat(),
        "net": net,
        "partial": any(gaps.values()),
        "gaps": gaps,
        "accounts": accounts,
        "assets": {"total": assets_total, "items": asset_rows, "sold_excluded": len(sold_ids), "oldest_as_of": None, "as_of_known": False},
        "liabilities": {"total": liabilities_total, "on_assets": asset_debt, "standalone": standalone_debt, "standalone_items": standalone,
                        "oldest_as_of": None, "as_of_known": False},
        # NOT part of the net: money someone owes the owner is not income and not money he has
        "receivables": {"in_net": False, "label": "expected_uncertain", "count": recv["count"], "total": recv["total_balance"],
                        "coverage": recv["coverage"], "items": [{"id": l["id"], "name": l["name"], "balance": l["early_closure_balance"]}
                                                                for l in receivable_loans]},
    }
