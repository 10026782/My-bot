"""מודול הלוואות (PATH_ENGINE_ARCHITECTURE_SPEC §4.2): `take_loan` (נטילת הלוואה כדי לממן סכום) ו-`prepay_loan` (פירעון מוקדם מלא).

הלוואה אינה אירוע מס (הנחיית הבעלים): הנכסים נשארים ובעלי מס סמוי זהה לבסיס, ולכן לפני/אחרי מס סמוי זהים בהלוואה. התשלום החודשי מ-`loans.pmt`
(נוסחה אחת, בלי עותק); הצמיחה מהמנוע הקיים. **אסור לייבא** `balanced_score`/`rankings`/`optimal` של `payoff.py`. הצמדה: `none` בלבד בגרסה ראשונה;
ריבית משתנה וניכוי ריבית לא מודלו ולא מונחים. חסר = `None` + `missing_inputs`."""

from __future__ import annotations

import calendar
from datetime import date

from core.financial_control.loans import pmt

from . import core

MODULE, VERSION = "loans", "loans-1"
TYPES = ("take_loan", "prepay_loan")
_COMMON = {"id", "label", "type"}
_ALLOWED = {
    "take_loan": _COMMON | {"amount", "annual_rate_pct", "term_months", "fees", "starts_on", "linkage", "approved", "terms_verified", "retained_capital",
                            "retained_return_pct", "retained_fee_pct"},
    "prepay_loan": _COMMON | {"balance", "annual_rate_pct", "remaining_months", "early_fee", "source_return_pct", "source_fee_pct"},
}


def describe_inputs(type_: str) -> dict:
    """מה נדרש / אופציונלי / קיים במערכת — לממשק "מה חסר" בלבד, לא לחישוב."""
    if type_ == "take_loan":
        return {"required": ["amount", "annual_rate_pct", "term_months"], "optional": ["fees", "starts_on", "approved", "terms_verified", "retained_capital",
                                                                                    "retained_return_pct", "retained_fee_pct"],
                "missing_means_null": ["fees"], "not_supported": ["linkage other than none", "variable rate", "interest deductibility"]}
    if type_ == "prepay_loan":
        return {"required": ["balance", "annual_rate_pct", "remaining_months"], "optional": ["early_fee", "source_return_pct", "source_fee_pct"],
                "missing_means_null": ["early_fee", "source_return_pct"], "existing_in_system": ["Loans: early closure balance, rate, payments left"],
                "not_supported": ["partial prepayment"]}
    raise ValueError("unknown loan path type")


def _add_months(day: date, months: int) -> date:
    index = day.year * 12 + day.month - 1 + months
    year, month = divmod(index, 12)
    return date(year, month + 1, min(day.day, calendar.monthrange(year, month + 1)[1]))


def schedule_through(principal: float, annual_rate_pct: float, term: int, first_payment_after: date, compare_at: date) -> dict:
    """לוח סילוקין חודשי דטרמיניסטי עם `loans.pmt`; רק תשלומים עד `compare_at` נספרים. מחזיר תשלום, ריבית כוללת, ריבית עד ההשוואה, תשלומים ויתרה."""
    payment = pmt(principal, annual_rate_pct, term)
    i = annual_rate_pct / 1200.0
    balance, interest_through, paid, rows, balance_at_compare = principal, 0.0, 0, [], principal
    for k in range(1, term + 1):
        interest = balance * i
        balance -= payment - interest
        when = _add_months(first_payment_after, k)
        if when <= compare_at:
            interest_through += interest
            paid += 1
            balance_at_compare = max(balance, 0.0)
            if len(rows) < core.MAX_MONTHS:
                rows.append({"date": when.isoformat(), "amount": -payment, "kind": "payment"})
    return {"payment": payment, "interest_total": payment * term - principal, "interest_through": interest_through, "payments_through": paid,
            "balance_at_compare": 0.0 if paid >= term else balance_at_compare, "rows": rows}


def evaluate(frame: dict, spec: dict) -> dict:
    core.check_frame(frame)
    if not isinstance(spec, dict) or spec.get("type") not in TYPES:
        raise ValueError(f"loan path type must be one of: {', '.join(TYPES)}")
    extra = set(spec) - _ALLOWED[spec["type"]]
    if extra:
        raise ValueError(f"unknown fields for {spec['type']}: {', '.join(sorted(extra))}")
    if not isinstance(spec.get("id"), str) or not spec["id"].strip() or not isinstance(spec.get("label"), str) or not spec["label"].strip():
        raise ValueError("a path needs an id and a label")
    return _take_loan(frame, spec) if spec["type"] == "take_loan" else _prepay_loan(frame, spec)


def _take_loan(frame: dict, spec: dict) -> dict:
    today, compare_at = date.fromisoformat(frame["today"]), date.fromisoformat(frame["compare_at"])
    amount = core.num(spec.get("amount"), "amount", positive=True, hi=1e10)
    rate = core.num(spec.get("annual_rate_pct"), "annual_rate_pct", lo=0, hi=100)
    term = core.num(spec.get("term_months"), "term_months", positive=True, hi=480)
    if term != int(term):
        raise ValueError("term_months must be a whole number")
    term = int(term)
    fees = core.num(spec.get("fees"), "fees", lo=0, hi=1e10, required=False)
    starts_on = core.to_date(spec["starts_on"], "starts_on") if spec.get("starts_on") else today
    if not today <= starts_on < compare_at:
        raise ValueError("starts_on must fall between today and compare_at")
    if spec.get("linkage") not in (None, "none"):
        raise ValueError("only an unlinked loan is supported in this version")
    approved, verified = bool(spec.get("approved", False)), bool(spec.get("terms_verified", False))
    sched = schedule_through(amount, rate, term, starts_on, compare_at)
    net_cost = core.total_or_none([sched["interest_through"], fees])
    r = core.blank_result(frame, path_id=spec["id"], module=MODULE, module_version=VERSION, type_="take_loan", label=spec["label"].strip(),
                          movement_kind="liability", purpose="fund_amount", funds_amount=amount)
    flows = [{"date": starts_on.isoformat(), "amount": amount, "kind": "loan_proceeds"}]
    if fees:
        flows.append({"date": starts_on.isoformat(), "amount": -fees, "kind": "fee"})
    r["cash_flows"] = flows + sched["rows"]
    r["cost"].update(interest_total=sched["interest_total"], fees_total=fees)
    r["measures"]["liquidity"] = {"cash_available": None if fees is None else amount - fees, "available_on": starts_on.isoformat(),
                                  "state": "accessible" if approved else "conditional"}
    r["measures"]["economic_cost"] = {"net_cost": net_cost, "components": ["interest_through_compare", "fees"]}
    # the assets stay where they are: latent tax is the same as if nothing happened, so the two rows coincide; what the loan costs is the interest
    nw = None if net_cost is None else -net_cost
    r["measures"]["net_worth"] = core.net_worth_block(frame, nw, nw)
    r["result"].update(cash_at_compare_date=None if fees is None else amount - fees - sched["payment"] * sched["payments_through"],
                       monthly_cash_effect=-sched["payment"], balance_effect="adds_liability")
    r["result"]["net_worth_change_at_compare_date"] = dict(r["measures"]["net_worth"]["after_latent_tax"])
    r["index_used"] = {"name": "loan_rate_as_entered", "source": "owner_entered", "kind": "simulation_assumption", "verified": verified}
    r["assumptions"] = [{"id": "level_payment", "text": "החזר חודשי קבוע (loans.pmt), ריבית קבועה, ללא הצמדה", "source": "assumed"},
                        {"id": "interest_through_compare", "text": "הריבית נספרת רק עד תאריך ההשוואה", "source": "assumed"},
                        {"id": "assets_stay", "text": "הנכסים נשארים; המס הסמוי עליהם זהה למצב בלי פעולה", "source": "assumed"}]
    r["risks"] = ["interest_deductibility_not_assumed", "fixed_rate_assumed"] + ([] if verified else ["terms_unverified"]) + ([] if approved else ["timing_uncertain"])
    r["not_applicable"] = ["cost.holding_costs", "cost.lost_income", "cost.opportunity_cost", "cost.forced_sale_discount_amount"]
    if fees is None:
        r["missing_inputs"].append("fees")
    rc, rr = spec.get("retained_capital"), spec.get("retained_return_pct")
    if rc is not None and rr is not None:                    # optional context: the capital the loan lets the owner keep invested
        rc = core.num(rc, "retained_capital", positive=True, hi=1e10)
        fee_pct = core.num(spec.get("retained_fee_pct"), "retained_fee_pct", lo=0, hi=10, required=False)
        grown = core.lump_value(frame, rc, core.num(rr, "retained_return_pct", lo=-50, hi=50), fee_pct or 0.0)
        growth = grown["nominal"] - rc
        latent = core.tax_on_growth(frame, rc, growth)
        r["after_action"]["capital_remaining"] = rc
        r["after_action"]["assets_remaining"] = [{"name": "retained_capital", "value": rc, "growth_to_compare": growth, "latent_tax_on_growth": latent}]
        r["tax"].update(latent_at_compare=latent, status="preliminary_estimate", reason="latent tax on the retained capital's growth (same with or without the loan)")
        if fee_pct is None:
            r["assumptions"].append({"id": "retained_fee_zero", "text": "דמי ניהול של ההון שנשאר לא הוזנו — 0 בחישוב", "source": "default"})
    r["not_applicable"] += ["tax.deferral_benefit", "tax.deferral_lost"]       # needs the sale counterfactual (the real-estate module, a later stage)
    r["certainty"] = "expected" if approved else "uncertain"
    r["provenance"] = {"payment": sched["payment"], "payments_through_compare": sched["payments_through"], "liability_at_compare": sched["balance_at_compare"]}
    return core.finalize(r)


def _prepay_loan(frame: dict, spec: dict) -> dict:
    today, compare_at = date.fromisoformat(frame["today"]), date.fromisoformat(frame["compare_at"])
    balance = core.num(spec.get("balance"), "balance", positive=True, hi=1e10)
    rate = core.num(spec.get("annual_rate_pct"), "annual_rate_pct", lo=0, hi=100)
    left = core.num(spec.get("remaining_months"), "remaining_months", positive=True, hi=480)
    if left != int(left):
        raise ValueError("remaining_months must be a whole number")
    left = int(left)
    fee = core.num(spec.get("early_fee"), "early_fee", lo=0, hi=1e10, required=False)
    src_ret = core.num(spec.get("source_return_pct"), "source_return_pct", lo=-50, hi=50, required=False)
    src_fee = core.num(spec.get("source_fee_pct"), "source_fee_pct", lo=0, hi=10, required=False)
    sched = schedule_through(balance, rate, left, today, compare_at)
    r = core.blank_result(frame, path_id=spec["id"], module=MODULE, module_version=VERSION, type_="prepay_loan", label=spec["label"].strip(),
                          movement_kind="equity_conversion", purpose="reduce_debt", funds_amount=None)
    growth_before = growth_tax = None
    if src_ret is not None:
        grown = core.lump_value(frame, balance, src_ret, src_fee or 0.0)
        growth_before = grown["nominal"] - balance
        growth_tax = core.tax_on_growth(frame, balance, growth_before)
    avoided = sched["interest_through"]
    cost_before = core.total_or_none([fee, growth_before])
    cost_after = core.total_or_none([fee, None if growth_before is None else growth_before - growth_tax])
    net_before = None if cost_before is None else avoided - cost_before          # benefit minus cost, vs doing nothing
    net_after = None if cost_after is None else avoided - cost_after
    r["cash_flows"] = ([{"date": today.isoformat(), "amount": -balance, "kind": "prepayment"}]
                       + ([{"date": today.isoformat(), "amount": -fee, "kind": "fee"}] if fee else [])
                       + [{"date": row["date"], "amount": -row["amount"], "kind": "payment_avoided"} for row in sched["rows"]])
    r["cost"].update(fees_total=fee, opportunity_cost=growth_before)
    r["measures"]["liquidity"] = {"cash_available": -balance, "available_on": today.isoformat(), "state": "accessible"}
    r["measures"]["economic_cost"] = {"net_cost": None if net_after is None else -net_after, "components": ["early_fee", "forgone_growth", "interest_avoided"]}
    r["measures"]["net_worth"] = core.net_worth_block(frame, net_before, net_after)
    r["result"].update(cash_at_compare_date=None if fee is None else -balance - fee + sched["payment"] * sched["payments_through"],
                       monthly_cash_effect=sched["payment"], balance_effect="reduces_liability_uses_existing_balance")
    r["result"]["net_worth_change_at_compare_date"] = dict(r["measures"]["net_worth"]["after_latent_tax"])
    r["after_action"]["given_up"]["assets"] = [{"name": "liquid_funds_used", "value": balance}]
    r["after_action"]["given_up"]["lost_future_value"] = growth_before
    r["index_used"] = {"name": "source_return_as_entered", "source": "owner_entered", "kind": "simulation_assumption", "verified": False}
    r["assumptions"] = [{"id": "full_prepayment", "text": "פירעון מוקדם מלא של היתרה; החזר חודשי קבוע מחושב מהיתרה, הריבית ומספר החודשים", "source": "assumed"},
                        {"id": "interest_through_compare", "text": "הריבית שנחסכת נספרת רק עד תאריך ההשוואה", "source": "assumed"},
                        {"id": "growth_taxed_preliminary", "text": "הצמיחה שאבדה מחויבת במס ראשוני לפי הרשומה היחידה", "source": "assumed"}]
    if src_ret is not None and src_fee is None:
        r["assumptions"].append({"id": "source_fee_zero", "text": "דמי ניהול של הכסף שנפרע בו לא הוזנו — 0 בחישוב", "source": "default"})
    r["missing_inputs"] = [n for n, v in (("early_fee", fee), ("source_return_pct", src_ret)) if v is None]
    r["risks"] = ["fixed_rate_assumed", "early_fee_as_entered"] if fee is not None else ["fixed_rate_assumed"]
    r["not_applicable"] = ["cost.interest_total", "cost.holding_costs", "cost.lost_income", "cost.forced_sale_discount_amount", "tax.deferral_benefit", "tax.deferral_lost"]
    if growth_tax is not None:
        r["tax"].update(status="preliminary_estimate", paid=0.0, reason="tax on the forgone growth is netted in the after-latent-tax row")
    r["certainty"] = "expected" if not r["missing_inputs"] else "unknown"
    r["provenance"] = {"interest_avoided_through_compare": avoided, "payment_avoided": sched["payment"], "forgone_growth_tax": growth_tax}
    return core.finalize(r)
