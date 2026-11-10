"""P3 stage 1 — the loans module (take_loan / prepay_loan), checked against an independent amortization written in the test."""

from __future__ import annotations

from datetime import date

import pytest

from portfolio_lab.path_comparison import core, loan_paths

TODAY = date(2026, 10, 25)


def frame(compare_at="2029-10-25", **over):
    raw = {"today": "2026-10-25", "compare_at": compare_at, "inflation_pct": [2.5, 2.5, 2.5, 2.5, 2.5], "owner_inputs_label": "הנחות בעלים"}
    raw.update(over)
    return core.make_frame(raw)


def loan(**over):
    spec = {"id": "loan", "label": "הלוואה", "type": "take_loan", "amount": 120000, "annual_rate_pct": 6, "term_months": 24, "fees": 0}
    spec.update(over)
    return spec


def oracle(principal, rate_pct, n, paid):
    """Independent level-payment amortization: (payment, interest paid in the first `paid` payments, balance after them)."""
    i = rate_pct / 1200
    pay = principal / n if i == 0 else principal * i / (1 - (1 + i) ** -n)
    bal, interest = principal, 0.0
    for _ in range(paid):
        step = bal * i
        interest += step
        bal -= pay - step
    return pay, interest, bal


# ═══ take_loan ═══

def test_the_loan_amounts_match_an_independent_amortization_over_the_whole_term():
    r = loan_paths.evaluate(frame("2029-10-25"), loan())
    pay, interest, _ = oracle(120000, 6, 24, 24)
    assert r["result"]["monthly_cash_effect"] == pytest.approx(-pay, abs=0.01)
    assert r["cost"]["interest_total"] == pytest.approx(pay * 24 - 120000, abs=0.01) == pytest.approx(interest, abs=0.01)
    assert r["measures"]["economic_cost"]["net_cost"] == pytest.approx(interest, abs=0.01)
    assert r["provenance"]["payments_through_compare"] == 24 and r["provenance"]["liability_at_compare"] == 0.0
    assert r["result"]["cash_at_compare_date"] == pytest.approx(120000 - pay * 24, abs=0.01)


def test_when_the_compare_date_is_before_the_end_only_the_interest_so_far_counts_and_the_liability_remains():
    r = loan_paths.evaluate(frame("2027-10-25"), loan(term_months=60))
    pay, interest, bal = oracle(120000, 6, 60, 12)
    assert r["provenance"]["payments_through_compare"] == 12
    assert r["measures"]["economic_cost"]["net_cost"] == pytest.approx(interest, abs=0.01) and r["provenance"]["liability_at_compare"] == pytest.approx(bal, abs=0.01)
    assert r["cost"]["interest_total"] == pytest.approx(pay * 60 - 120000, abs=0.01)
    assert r["cost"]["interest_total"] > r["measures"]["economic_cost"]["net_cost"]


def test_a_loan_is_not_a_tax_event_and_the_two_latent_tax_rows_coincide():
    r = loan_paths.evaluate(frame(), loan())
    assert r["tax"]["event"] == "none" and r["tax"]["status"] == "not_assessed"
    nw = r["measures"]["net_worth"]
    assert nw["before_latent_tax"] == nw["after_latent_tax"] and nw["after_latent_tax"]["nominal"] == -r["measures"]["economic_cost"]["net_cost"]
    assert r["movement_kind"] == "liability" and r["purpose"] == "fund_amount" and r["funds_amount"] == 120000.0 and r["result"]["balance_effect"] == "adds_liability"


def test_missing_fees_are_missing_not_zero_and_no_total_is_shown():
    r = loan_paths.evaluate(frame(), loan(fees=None))
    assert r["missing_inputs"] == ["fees"] and r["cost"]["fees_total"] is None
    assert r["measures"]["economic_cost"]["net_cost"] is None and r["result"]["cash_at_compare_date"] is None
    assert r["measures"]["net_worth"]["after_latent_tax"]["nominal"] is None and r["measures"]["liquidity"]["cash_available"] is None
    assert any(c["caveat_id"] == "missing_is_missing" for c in r["caveats"])
    paid = loan_paths.evaluate(frame(), loan(fees=1500))
    pay, interest, _ = oracle(120000, 6, 24, 24)
    assert paid["measures"]["economic_cost"]["net_cost"] == pytest.approx(interest + 1500, abs=0.01) and paid["measures"]["liquidity"]["cash_available"] == 118500.0
    assert [f["kind"] for f in paid["cash_flows"][:2]] == ["loan_proceeds", "fee"]


def test_certainty_follows_approval_and_unverified_terms_are_a_risk():
    approved = loan_paths.evaluate(frame(), loan(approved=True, terms_verified=True))
    assert approved["certainty"] == "expected" and "terms_unverified" not in approved["risks"] and approved["index_used"]["verified"] is True
    pending = loan_paths.evaluate(frame(), loan())
    assert pending["certainty"] == "uncertain" and {"terms_unverified", "timing_uncertain", "interest_deductibility_not_assumed"} <= set(pending["risks"])
    assert pending["measures"]["liquidity"]["state"] == "conditional" and approved["measures"]["liquidity"]["state"] == "accessible"


def test_a_zero_rate_loan_costs_no_interest_and_the_retained_capital_shows_its_latent_tax():
    zero = loan_paths.evaluate(frame(), loan(annual_rate_pct=0))
    assert zero["cost"]["interest_total"] == pytest.approx(0, abs=1e-6) and zero["result"]["monthly_cash_effect"] == pytest.approx(-5000, abs=0.01)
    kept = loan_paths.evaluate(frame(), loan(retained_capital=250000, retained_return_pct=6, retained_fee_pct=0.5))
    asset = kept["after_action"]["assets_remaining"][0]
    grown = core.lump_value(frame(), 250000, 6, 0.5)
    assert asset["growth_to_compare"] == pytest.approx(grown["nominal"] - 250000, abs=0.01) and asset["latent_tax_on_growth"] > 0
    assert kept["tax"]["status"] == "preliminary_estimate" and kept["tax"]["latent_at_compare"] == pytest.approx(asset["latent_tax_on_growth"], abs=0.01)
    assert any(c["caveat_id"] == "tax_rate_estimate" for c in kept["caveats"])
    assert loan_paths.evaluate(frame(), loan(retained_capital=250000))["tax"]["status"] == "not_assessed"            # no return entered: nothing invented


@pytest.mark.parametrize("over", [
    {"amount": 0}, {"amount": -5}, {"amount": "120000"}, {"amount": True}, {"annual_rate_pct": -1}, {"annual_rate_pct": 150}, {"term_months": 0}, {"term_months": 12.5},
    {"term_months": 1000}, {"linkage": "cpi"}, {"starts_on": "2030-01-01"}, {"starts_on": "2026-01-01"}, {"approved_by": "x"}, {"fees": -1}, {"id": ""}, {"label": None},
])
def test_bad_loan_inputs_are_rejected(over):
    with pytest.raises(ValueError):
        loan_paths.evaluate(frame(), loan(**over))


def test_only_the_declared_loan_types_and_a_valid_frame_are_accepted():
    with pytest.raises(ValueError):
        loan_paths.evaluate(frame(), loan(type="sell_asset"))
    with pytest.raises(ValueError):
        loan_paths.evaluate({"today": "2026-10-25"}, loan())
    assert loan_paths.describe_inputs("take_loan")["required"] == ["amount", "annual_rate_pct", "term_months"]
    with pytest.raises(ValueError):
        loan_paths.describe_inputs("sell_asset")


def test_a_later_start_moves_the_payments_and_is_deterministic():
    a = loan_paths.evaluate(frame(), loan(starts_on="2027-01-25"))
    assert a["cash_flows"][0]["date"] == "2027-01-25" and a["cash_flows"][1]["date"] == "2027-02-25"
    assert a == loan_paths.evaluate(frame(), loan(starts_on="2027-01-25"))


# ═══ prepay_loan ═══

def prepay(**over):
    spec = {"id": "prepay", "label": "פירעון מוקדם", "type": "prepay_loan", "balance": 100000, "annual_rate_pct": 6, "remaining_months": 60, "early_fee": 500,
            "source_return_pct": 4, "source_fee_pct": 0.5}
    spec.update(over)
    return spec


def test_prepayment_benefit_is_the_interest_avoided_minus_the_fee_and_the_forgone_growth_checked_independently():
    f = frame("2027-10-25")
    r = loan_paths.evaluate(f, prepay())
    pay, interest, _ = oracle(100000, 6, 60, 12)
    grown = core.lump_value(f, 100000, 4, 0.5)
    growth = grown["nominal"] - 100000
    tax = core.tax_on_growth(f, 100000, growth)
    assert r["provenance"]["interest_avoided_through_compare"] == pytest.approx(interest, abs=0.01)
    assert r["measures"]["net_worth"]["before_latent_tax"]["nominal"] == pytest.approx(interest - 500 - growth, abs=0.01)
    assert r["measures"]["net_worth"]["after_latent_tax"]["nominal"] == pytest.approx(interest - 500 - (growth - tax), abs=0.01)
    assert r["measures"]["economic_cost"]["net_cost"] == pytest.approx((500 + (growth - tax)) - interest, abs=0.01)                # cost minus benefit
    assert r["movement_kind"] == "equity_conversion" and r["purpose"] == "reduce_debt" and r["funds_amount"] is None
    assert r["result"]["monthly_cash_effect"] == pytest.approx(pay, abs=0.01) and r["cost"]["fees_total"] == 500.0 and r["cost"]["opportunity_cost"] == pytest.approx(growth, abs=0.01)


def test_prepayment_with_a_missing_fee_or_return_is_missing_not_zero():
    r = loan_paths.evaluate(frame("2027-10-25"), prepay(early_fee=None, source_return_pct=None))
    assert set(r["missing_inputs"]) == {"early_fee", "source_return_pct"} and r["certainty"] == "unknown"
    assert r["measures"]["net_worth"]["after_latent_tax"]["nominal"] is None and r["measures"]["economic_cost"]["net_cost"] is None
    only_fee = loan_paths.evaluate(frame("2027-10-25"), prepay(early_fee=None))
    assert only_fee["missing_inputs"] == ["early_fee"] and only_fee["measures"]["net_worth"]["before_latent_tax"]["nominal"] is None


def test_a_higher_source_return_makes_prepayment_cost_more_and_the_numbers_move_monotonically():
    f = frame("2027-10-25")
    costs = [loan_paths.evaluate(f, prepay(source_return_pct=x))["measures"]["net_worth"]["after_latent_tax"]["nominal"] for x in (0, 3, 6, 9)]
    assert costs == sorted(costs, reverse=True)


@pytest.mark.parametrize("over", [{"balance": 0}, {"remaining_months": 0}, {"remaining_months": 7.5}, {"early_fee": -1}, {"amount": 5}, {"source_return_pct": 90}, {"monthly_payment": 1000}])
def test_bad_prepayment_inputs_are_rejected_and_partial_prepayment_is_not_supported(over):
    with pytest.raises(ValueError):
        loan_paths.evaluate(frame("2027-10-25"), prepay(**over))


def test_the_ranking_helpers_of_payoff_are_never_used():
    import ast
    from pathlib import Path
    tree = ast.parse(Path("portfolio_lab/path_comparison/loan_paths.py").read_text(encoding="utf-8"))
    imported = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert "core.financial_control.loans" in imported and not any("payoff" in m for m in imported)


def test_payment_split_interest_principal():
    from core.financial_control import loans as L
    s = L.payment_split(116175.84, 6, 2816.16, 62)
    assert s == {"interest": 580.88, "principal": 2235.28, "balance_after": 113940.56}, s
    assert L.payment_split(None, 6, 100) is None and L.payment_split(1000, None, 100) is None
    assert L.payment_split(100000, 12, 500) is None                       # payment below the interest: no invented split
    assert L.payment_split(700, 6, 784, 1)["balance_after"] == 0.0         # last payment clears the balance


def test_summary_interest_principal_totals():
    from datetime import date
    from core.financial_control import loans as L
    def rec(i, bal, rate, pay, direction=None):
        f = {"Loan Name/ID": i, "Outstanding Principal for Early Closure": bal, "Interest Rate (%)": rate, "Current Monthly Payment": pay, "Active Loan": True}
        if direction: f["Direction"] = direction
        return {"id": i, "fields": f}
    items = [L.loan_item(r, date(2026, 11, 8)) for r in (rec("a", 120000, 6, 2000), rec("b", 1200, 12, 300), rec("c", 5000, None, 100), rec("d", 9999, None, None, "חייבים לי"))]
    s = L.summarize(items)
    assert s["interest_this_month"] == 612.0 and s["principal_this_month"] == 1688.0 and s["balance_after_this_month"] == 119512.0, s
    assert s["split_coverage"] == {"known": 2, "of": 3, "exact": 0}, s["split_coverage"]


def test_summary_split_without_mortgage():
    from datetime import date
    from core.financial_control import loans as L
    from airtable_schema import LoanFields as LF
    def rec(i, bal, rate, pay, typ=None):
        f = {"Loan Name/ID": i, "Outstanding Principal for Early Closure": bal, "Interest Rate (%)": rate, "Current Monthly Payment": pay, "Active Loan": True}
        if typ: f[LF.LOAN_TYPE] = typ
        return {"id": i, "fields": f}
    items = [L.loan_item(r, date(2026, 11, 8)) for r in (rec("a", 120000, 6, 2000, "פרטית"), rec("m", 300000, 6, 2500, "משכנתא"))]
    s = L.summarize(items)
    nm = s["split_no_mortgage"]
    assert nm["of"] == 1 and nm["known"] == 1 and nm["interest_this_month"] == 600.0 and nm["principal_this_month"] == 1400.0, nm
    assert s["interest_this_month"] == 600.0 + 1500.0, s["interest_this_month"]


def test_end_date_inferred_from_payments_remaining():
    from datetime import date
    from core.financial_control import loans as L
    t = date(2026, 11, 8)
    f = {"Payments Remaining": 3, "Monthly Due Day": 10}
    assert L.inferred_end(f, t) == date(2027, 1, 10)
    assert L.inferred_end({**f, "Monthly Due Day": 5}, t) == date(2027, 2, 5)
    assert L.inferred_end({**f, "Next Payment Due": "2026-12-02"}, t) == date(2027, 2, 2)
    assert L.inferred_end({"Payments Remaining": 0}, t) is None and L.inferred_end({}, t) is None
    rec = {"id": "x", "fields": {"Loan Name/ID": "x", "Active Loan": True, "Current Monthly Payment": 100, **f}}
    item = L.loan_item(rec, t)
    assert item["end_date"] == "2027-01-10" and item["end_date_inferred"] is True
    typed = L.loan_item({"id": "y", "fields": {**rec["fields"], "End Date": "2030-01-01"}}, t)
    assert typed["end_date"] == "2030-01-01" and typed["end_date_inferred"] is False
    # schedule: no start date but remaining payments -> current month through the inferred end, not beyond
    from datetime import date as D
    wins = [("2026-11", D(2026, 11, 1), D(2026, 11, 30)), ("2027-01", D(2027, 1, 1), D(2027, 1, 31)), ("2027-02", D(2027, 2, 1), D(2027, 2, 28)), ("2026-10", D(2026, 10, 1), D(2026, 10, 31))]
    totals, undated, _ = L.monthly_schedule([rec], wins, t)
    assert totals == {"2026-11": 100.0, "2027-01": 100.0, "2027-02": 0.0, "2026-10": 0.0}, totals
    assert undated == ["x"]


if __name__ == "__main__":
    test_end_date_inferred_from_payments_remaining(); test_payment_split_interest_principal(); test_summary_interest_principal_totals(); print("ok split")


def test_the_payoff_engine_uses_the_schedule_s_real_remaining_interest():
    from datetime import date
    from core.financial_control import amortization as A, loans as L, payoff
    # payment x months - balance would say 100 x 3 - 280 = 20; the lender's schedule says the interest still ahead is 12.5
    sched = A.Schedule(ok=True, rows=[["2026-11-10", 90.0, 10.0, 100.0, 190.0, 0, 1], ["2026-12-10", 95.0, 5.0, 100.0, 95.0, 0, 1], ["2027-01-10", 95.0, 2.5, 97.5, 0.0, 0, 1]])
    rec = {"id": "s", "fields": {"Loan Name/ID": "s", "Active Loan": True, "Outstanding Principal for Early Closure": 280, "Interest Rate (%)": 12, "Current Monthly Payment": 100,
                                 "Payments Remaining": 3, "Early Repayment Fee/Penalty": "אין", "Amortization Schedule": A.dumps(sched)}}
    item = L.loan_item(rec, date(2026, 11, 8))
    assert item["interest_remaining"] == 17.5 and item["interest_remaining_exact"] is True
    assert item["estimated_future_cost"] == 17.5 and item["estimated_total_remaining_payments"] == 297.5       # the schedule's own remaining payments and interest
    row = payoff.metrics([item])[0]
    assert row["interest_from_schedule"] is True and row["estimated_future_cost"] == 17.5 and row["cost_saving"] == 17.5 and row["future_cost_exact"] is True
    plain = L.loan_item({"id": "p", "fields": {k: v for k, v in rec["fields"].items() if k != "Amortization Schedule"}}, date(2026, 11, 8))
    assert payoff.metrics([plain])[0]["interest_from_schedule"] is False
    assert plain["interest_remaining"] == 20.0 and plain["interest_remaining_exact"] is False            # no schedule: payment x payments left - balance, labelled an estimate


def test_a_loan_shows_what_it_costs_to_close_today_with_a_known_fee_only():
    from datetime import date
    from core.financial_control import loans as L
    def rec(fee):
        f = {"Loan Name/ID": "x", "Active Loan": True, "Outstanding Principal for Early Closure": 10000, "Interest Rate (%)": 6, "Current Monthly Payment": 500, "Payments Remaining": 24, "Monthly Due Day": 10}
        if fee is not None:
            f["Early Repayment Fee/Penalty"] = fee
        return {"id": "x", "fields": f}
    known = L.loan_item(rec("150"), date(2026, 11, 8))
    assert known["payoff_now_total"] == 10150.0 and known["payoff_now_fee_known"] is True
    none = L.loan_item(rec("אין"), date(2026, 11, 8))
    assert none["payoff_now_total"] == 10000.0 and none["payoff_now_fee_known"] is True
    unknown = L.loan_item(rec("2%"), date(2026, 11, 8))
    assert unknown["payoff_now_total"] is None and unknown["payoff_now_fee_known"] is False           # a fee that is not a number is never turned into a total
    assert known["first_payment_date"] == "2026-11-10"
    assert L.loan_item(rec("אין"), date(2026, 11, 20))["first_payment_date"] == "2026-12-10"


def test_loan_timeline_drops_thresholds_and_scopes():
    from datetime import date
    from core.financial_control import loans as L, loan_timeline as T
    today = date(2026, 11, 8)
    def rec(i, bal, rate, pay, left, typ=None):
        f = {"Loan Name/ID": i, "Outstanding Principal for Early Closure": bal, "Interest Rate (%)": rate, "Current Monthly Payment": pay,
             "Payments Remaining": left, "Active Loan": True, "Next Payment Due": "2026-11-15", "Monthly Due Day": 15}
        if typ: f["Loan Type"] = typ
        return {"id": i, "fields": f}
    items = [L.loan_item(r, today) for r in (rec("short", 3000, 12, 1010, 3), rec("long", 60000, 6, 1500, 48), rec("mort", 300000, 5, 2000, 240, "משכנתא"))]
    out = T.build(items, {}, today)
    nm, allv = out["no_mortgage"], out["all"]
    assert nm["loans"] == 2 and allv["loans"] == 3 and nm["of"] == 2 and allv["of"] == 3
    assert nm["payment_now"] > 2400 and allv["payment_now"] > nm["payment_now"] + 1900
    assert [d["ended"] for d in nm["drops"]][0][0].startswith("short") and nm["drops"][0]["drop"] >= 1000    # the short loan ends -> the payment falls by its instalment
    assert nm["interest_remaining"] == round(nm["interest_remaining_exact"] + nm["interest_remaining_estimated"], 2) and nm["interest_remaining_exact"] == 0
    th = {t["limit"]: t for t in nm["thresholds"]}
    assert th[0.25]["sustained"] and th[0.25]["sustained"] <= (th[0.15]["sustained"] or "9999")      # the lower the limit, the later it is reached
    assert nm["yearly"][0]["month"] == nm["first_month"] and nm["yearly"][-1]["month"] == nm["last_month"]
    assert T.build([], {}, today)["no_mortgage"] is None


def test_loan_timeline_this_month_is_full_and_same_named_loans_stay_distinct():
    import json
    from datetime import date
    from core.financial_control import loans as L, loan_timeline as T, amortization as A
    today = date(2026, 11, 10)
    def sched(rows):
        return A.loads(json.dumps({"v": 1, "asof": "2026-11-08", "rows": rows}))
    # same lender name, two loans; the first one's November instalment is dated TODAY (already charged) and must still count in this month
    a_rows = [["2026-10-10", 90.0, 10.0, 100.0, 910.0, 1, 1], ["2026-11-10", 91.0, 9.0, 100.0, 819.0, 1, 1], ["2026-12-10", 92.0, 8.0, 100.0, 727.0, 0, 1]]
    b_rows = [["2026-11-15", 95.0, 5.0, 100.0, 905.0, 0, 1], ["2026-12-15", 96.0, 4.0, 100.0, 809.0, 0, 1]]
    def rec(i, rate):
        return {"id": i, "fields": {"Loan Name/ID": "כאל", "Outstanding Principal for Early Closure": 800, "Interest Rate (%)": rate, "Current Monthly Payment": 100, "Active Loan": True}}
    c_rows = [["2026-11-20", 98.0, 2.0, 100.0, 902.0, 0, 1], ["2026-12-20", 98.0, 2.0, 100.0, 804.0, 0, 1], ["2027-01-20", 98.0, 2.0, 100.0, 706.0, 0, 1]]
    c = {"id": "c", "fields": {"Loan Name/ID": "מקס", "Outstanding Principal for Early Closure": 800, "Interest Rate (%)": 5, "Current Monthly Payment": 100, "Active Loan": True}}
    items = [L.loan_item(rec("a", 10), today), L.loan_item(rec("b", 6), today), L.loan_item(c, today)]
    out = T.build(items, {"a": sched(a_rows), "b": sched(b_rows), "c": sched(c_rows)}, today)["no_mortgage"]
    assert out["first_month"] == "2026-11" and out["payment_now"] == 300.0 and out["interest_now"] == 16.0, out      # all three November instalments, charged (a) or not
    assert out["drops"] and len(set(out["drops"][0]["ended"])) == 2 and all("%" in n for n in out["drops"][0]["ended"]), out["drops"]   # two "כאל" loans, two labels
