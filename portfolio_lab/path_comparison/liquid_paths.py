"""מודול כספים נזילים (PATH_ENGINE_ARCHITECTURE_SPEC §4.3): `use_liquid_cash` (שימוש בכסף שכבר נזיל) ו-`wait` (מסלול הייחוס הטבעי: לא לעשות דבר עכשיו).

שימוש בכסף נזיל אינו אירוע מס בעצמו; מה שאבד הוא הצמיחה העתידית של הסכום (מהמנוע הקיים), והמס הראשוני עליה (הרשומה היחידה) מופחת מעלות ההזדמנות
בשורת "אחרי מס סמוי". כסף נעול אינו מסלול מימון (ValueError); מותנה = ודאות נמוכה. `available_on` עתידי עדיין לא נתמך בגרסה ראשונה.
חסר = `None` + `missing_inputs`; אין המלצה, ציון או דירוג."""

from __future__ import annotations

from datetime import date

from . import core

MODULE, VERSION = "liquid", "liquid-1"
TYPES = ("use_liquid_cash", "wait")
_COMMON = {"id", "label", "type"}
_ALLOWED = {
    "use_liquid_cash": _COMMON | {"amount", "balance", "expected_return_pct", "fee_pct", "withdraw_fee", "liquidity_state", "available_on"},
    "wait": _COMMON | {"amount", "until", "price_change_pct"},
}


def describe_inputs(type_: str) -> dict:
    if type_ == "use_liquid_cash":
        return {"required": ["amount", "expected_return_pct"], "optional": ["balance", "fee_pct", "withdraw_fee", "liquidity_state"],
                "missing_means_null": ["expected_return_pct", "withdraw_fee"], "existing_in_system": ["Financial Accounts: balance, expected return, fee, liquidity"],
                "not_supported": ["available_on after today", "locked money"]}
    if type_ == "wait":
        return {"required": ["amount", "until"], "optional": ["price_change_pct"], "missing_means_null": ["price_change_pct"], "not_supported": []}
    raise ValueError("unknown liquid path type")


def evaluate(frame: dict, spec: dict) -> dict:
    core.check_frame(frame)
    if not isinstance(spec, dict) or spec.get("type") not in TYPES:
        raise ValueError(f"liquid path type must be one of: {', '.join(TYPES)}")
    extra = set(spec) - _ALLOWED[spec["type"]]
    if extra:
        raise ValueError(f"unknown fields for {spec['type']}: {', '.join(sorted(extra))}")
    if not isinstance(spec.get("id"), str) or not spec["id"].strip() or not isinstance(spec.get("label"), str) or not spec["label"].strip():
        raise ValueError("a path needs an id and a label")
    return _use_cash(frame, spec) if spec["type"] == "use_liquid_cash" else _wait(frame, spec)


def _use_cash(frame: dict, spec: dict) -> dict:
    today = date.fromisoformat(frame["today"])
    amount = core.num(spec.get("amount"), "amount", positive=True, hi=1e10)
    balance = core.num(spec.get("balance"), "balance", lo=0, hi=1e11, required=False)
    if balance is not None and amount > balance + 0.005:
        raise ValueError("amount exceeds the balance")
    ret = core.num(spec.get("expected_return_pct"), "expected_return_pct", lo=-50, hi=50, required=False)
    fee_pct = core.num(spec.get("fee_pct"), "fee_pct", lo=0, hi=10, required=False)
    withdraw_fee = core.num(spec.get("withdraw_fee"), "withdraw_fee", lo=0, hi=1e10, required=False)
    state = spec.get("liquidity_state", "accessible")
    if state == "locked":
        raise ValueError("locked money cannot fund the amount")
    if state not in ("accessible", "conditional"):
        raise ValueError("liquidity_state must be accessible or conditional")
    if spec.get("available_on") is not None and not (today.replace(day=1) <= core.to_date(spec["available_on"], "available_on") < _next_month(today)):
        raise ValueError("available_on must be within the current month in this version")
    growth_before = growth_after = tax = None
    if ret is not None:
        grown = core.lump_value(frame, amount, ret, fee_pct or 0.0)
        growth_before = grown["nominal"] - amount
        tax = core.tax_on_growth(frame, amount, growth_before)
        growth_after = growth_before - tax
    cost_before = core.total_or_none([growth_before, withdraw_fee])
    cost_after = core.total_or_none([growth_after, withdraw_fee])
    r = core.blank_result(frame, path_id=spec["id"], module=MODULE, module_version=VERSION, type_="use_liquid_cash", label=spec["label"].strip(),
                          movement_kind="equity_conversion", purpose="fund_amount", funds_amount=amount)
    r["cash_flows"] = [{"date": today.isoformat(), "amount": amount, "kind": "withdrawal"}] + ([{"date": today.isoformat(), "amount": -withdraw_fee, "kind": "fee"}] if withdraw_fee else [])
    r["cost"].update(fees_total=withdraw_fee, opportunity_cost=growth_before)
    r["measures"]["liquidity"] = {"cash_available": None if withdraw_fee is None else amount - withdraw_fee, "available_on": today.isoformat(), "state": state}
    r["measures"]["economic_cost"] = {"net_cost": cost_after, "components": ["forgone_growth_after_tax", "withdraw_fee"]}
    r["measures"]["net_worth"] = core.net_worth_block(frame, None if cost_before is None else -cost_before, None if cost_after is None else -cost_after)
    r["result"].update(cash_at_compare_date=None if withdraw_fee is None else amount - withdraw_fee, monthly_cash_effect=None, balance_effect="uses_existing_balance")
    r["result"]["net_worth_change_at_compare_date"] = dict(r["measures"]["net_worth"]["after_latent_tax"])
    r["after_action"]["capital_remaining"] = None if balance is None else balance - amount
    r["after_action"]["assets_remaining"] = [] if balance is None else [{"name": "account_balance_after", "value": balance - amount}]
    r["after_action"]["given_up"]["assets"] = [{"name": "liquid_funds_used", "value": amount}]
    r["after_action"]["given_up"]["lost_future_value"] = growth_before
    r["index_used"] = {"name": "account_return_as_entered", "source": "owner_entered", "kind": "simulation_assumption", "verified": False}
    r["assumptions"] = [{"id": "forgone_growth", "text": "הצמיחה העתידית של הסכום שנמשך אבדה (מנוע הצמיחה הקיים)", "source": "assumed"},
                        {"id": "growth_taxed_preliminary", "text": "המס הראשוני על הצמיחה שאבדה מופחת בשורת אחרי מס סמוי", "source": "assumed"}]
    if ret is not None and fee_pct is None:
        r["assumptions"].append({"id": "fee_zero", "text": "דמי ניהול של החשבון לא הוזנו — 0 בחישוב", "source": "default"})
    r["missing_inputs"] = [n for n, v in (("expected_return_pct", ret), ("withdraw_fee", withdraw_fee)) if v is None]
    r["risks"] = ["depends_on_assumed_return"] + (["release_not_verified"] if state == "conditional" else [])
    r["not_applicable"] = ["cost.interest_total", "cost.holding_costs", "cost.lost_income", "cost.forced_sale_discount_amount", "tax.deferral_benefit", "tax.deferral_lost"]
    if tax is not None:
        r["tax"].update(status="preliminary_estimate", paid=0.0, reason="no tax event in using liquid cash; the tax on the forgone growth is netted in the after-latent-tax row")
    r["certainty"] = "unknown" if r["missing_inputs"] else ("expected" if state == "accessible" else "uncertain")
    r["provenance"] = {"tax_on_forgone_growth": tax}
    return core.finalize(r)


def _wait(frame: dict, spec: dict) -> dict:
    today, compare_at = date.fromisoformat(frame["today"]), date.fromisoformat(frame["compare_at"])
    amount = core.num(spec.get("amount"), "amount", positive=True, hi=1e10)
    until = core.to_date(spec.get("until"), "until")
    if not today < until <= compare_at:
        raise ValueError("until must fall after today and no later than compare_at")
    price = core.num(spec.get("price_change_pct"), "price_change_pct", lo=-90, hi=1000, required=False)
    extra = None if price is None else amount * price / 100.0
    r = core.blank_result(frame, path_id=spec["id"], module=MODULE, module_version=VERSION, type_="wait", label=spec["label"].strip(),
                          movement_kind="no_movement", purpose="fund_amount", funds_amount=amount)
    r["measures"]["liquidity"] = {"cash_available": 0.0, "available_on": None, "state": None}
    r["measures"]["economic_cost"] = {"net_cost": extra, "components": ["price_change_while_waiting"]}
    r["measures"]["net_worth"] = core.net_worth_block(frame, None if extra is None else -extra, None if extra is None else -extra)
    r["result"].update(cash_at_compare_date=0.0, monthly_cash_effect=0.0, balance_effect="no_change_until_later")
    r["result"]["net_worth_change_at_compare_date"] = dict(r["measures"]["net_worth"]["after_latent_tax"])
    r["index_used"] = {"name": "price_change_as_entered" if price is not None else None, "source": "owner_entered" if price is not None else None,
                       "kind": "simulation_assumption" if price is not None else None, "verified": False}
    r["assumptions"] = [{"id": "no_action_now", "text": "לא נעשה דבר עד התאריך; היעד לא ממומן בזמן", "source": "assumed"}]
    r["missing_inputs"] = [] if price is not None else ["price_change_pct"]
    r["risks"] = ["goal_not_funded_on_time"]
    r["not_applicable"] = ["cost.interest_total", "cost.fees_total", "cost.holding_costs", "cost.lost_income", "cost.opportunity_cost", "cost.forced_sale_discount_amount",
                           "tax.deferral_benefit", "tax.deferral_lost"]
    r["certainty"] = "expected" if price is not None else "unknown"
    r["provenance"] = {"funds_on_time": False, "until": until.isoformat()}
    return core.finalize(r)


def _next_month(day: date) -> date:
    return date(day.year + (day.month == 12), day.month % 12 + 1, 1)
