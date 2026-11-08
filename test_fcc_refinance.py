"""FCC refinance simulator: pure model (per-loan verdicts, totals, the two comparisons, unknowns) and POST /api/fcc/loans/refinance (owner only, read-only)."""
from __future__ import annotations

import os

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-rf-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:RF_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patRfTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appRfTest")
os.environ.setdefault("ELIYAHU_CHAT_ID", "1")

from datetime import date

import pytest
from flask import Flask

import tma_api
from core.financial_control import loans as L, refinance as R, service
from identity import Domain, Identity, Role

TODAY = date(2026, 11, 8)
H = {"X-Telegram-Init-Data": "valid"}


def rec(i, bal, rate, pay, left, fee=None, **extra):
    f = {"Loan Name/ID": i, "Active Loan": True, "Outstanding Principal for Early Closure": bal, "Interest Rate (%)": rate, "Current Monthly Payment": pay, "Payments Remaining": left}
    if fee is not None:
        f["Early Repayment Fee/Penalty"] = fee
    f.update(extra)
    return {"id": i, "fields": f}


RECS = [rec("hi", 40000, 12.0, 1000, 48, fee="אין"),            # 12% -> worth refinancing at 6%
        rec("lo", 100000, 3.0, 1800, 60, fee="אין"),            # 3% -> already below the offer: not worth
        rec("feeunk", 20000, 11.0, 700, 36),                    # fee not known
        rec("nodata", None, None, None, None, fee="אין"),        # missing everything
        rec("tome", 5000, 5.0, 100, 50, fee="אין", **{"Direction": "חייבים לי"})]
ITEMS = [L.loan_item(r, TODAY) for r in RECS]
OFFER = R.parse_offer({"rate": 6.0, "term_months": 120, "fees": 3000})


def test_per_loan_verdicts_and_unknowns_are_never_guessed():
    out = R.simulate(ITEMS, OFFER)
    by = {r["id"]: r for r in out["rows"]}
    assert set(by) == {"hi", "lo", "feeunk", "nodata"}                       # a debt owed TO the owner is not a loan to refinance
    assert by["hi"]["verdict"] == "worth" and by["hi"]["net_saving"] > 0
    assert by["lo"]["verdict"] == "not_worth" and by["lo"]["net_saving"] < 0
    assert by["feeunk"]["verdict"] == "unknown_fee" and by["feeunk"]["reason"]
    assert by["nodata"]["verdict"] == "missing" and by["nodata"]["interest_left"] is None
    assert out["recommended_ids"] == ["hi"]
    assert any("עמלת הפירעון" in n for n in out["notes"]) and any("חסרים" in n for n in out["notes"])


def test_a_loan_whose_interest_is_mostly_paid_is_not_worth_rolling_even_at_a_lower_rate():
    near = L.loan_item(rec("near", 2309.25, 12.85, 784.24, 3, fee="אין"), TODAY)          # 3 payments left, almost only principal
    big = L.loan_item(rec("big", 93719.73, 6.96, 1378.22, 85, fee="אין"), TODAY)
    out = R.simulate([near, big], R.parse_offer({"rate": 5.5, "term_months": 240}))
    by = {r["id"]: r for r in out["rows"]}
    assert by["near"]["net_saving"] > 0 and by["near"]["verdict"] == "not_worth" and "כמעט נגמרה" in by["near"]["reason"]    # a few shekels of saving is not a reason
    assert by["near"]["interest_share"] < 0.05 < by["big"]["interest_share"]
    assert by["near"]["full_term_net"] < 0                                                  # left in a 20-year mortgage it would cost far more than it has left
    assert by["big"]["verdict"] == "worth" and by["big"]["full_term_net"] < 0 and "לכל תקופת המשכנתא" in by["big"]["reason"]
    assert out["recommended_ids"] == ["big"]


def test_monthly_relief_is_a_separate_aspect_with_its_price():
    near = L.loan_item(rec("near", 2309.25, 12.85, 784.24, 3, fee="אין"), TODAY)
    big = L.loan_item(rec("big", 93719.73, 6.96, 1378.22, 85, fee="אין"), TODAY)
    out = R.simulate([near, big], R.parse_offer({"rate": 5.5, "term_months": 240}))
    by = {r["id"]: r for r in out["rows"]}
    assert by["near"]["verdict"] == "not_worth" and by["near"]["monthly_relief"] > 700           # useless for interest, but it would free most of its payment...
    assert 0 < by["near"]["relief_cost_per_100"] < by["big"]["relief_cost_per_100"]             # ...and cheaply: little principal is stretched, the big loan costs far more per shekel of relief
    assert out["relief_ids"] == ["near", "big"]                                                  # cheapest relief first and out["relief"]["monthly_saving"] > 0 and out["relief"]["loans"] == 2
    cheap = R.simulate([big], R.parse_offer({"rate": 5.5, "term_months": 240}))
    assert cheap["relief_ids"] == ["big"]


def test_totals_show_both_comparisons_and_payback():
    out = R.simulate(ITEMS, OFFER)
    t = out["selected"]
    assert t["loans"] == 3 and t["balance"] == 160000 and t["current_payment"] == 3500          # the loan with no data is not priced
    assert t["offer_payment"] < t["current_payment"] and t["monthly_saving"] > 0                  # the long term lowers the payment...
    assert t["total_saving_offer_term"] < t["total_saving_same_term"]                             # ...and costs interest versus the same term
    assert t["payback_months"] == -(-t["one_time_costs"] // t["monthly_saving"]) and t["any_unknown_fee"] is True
    only = out["recommended"]
    assert only["loans"] == 1 and only["balance"] == 40000
    assert out["recommended_pays"] is False and only["total_saving_same_term"] < 0 and any("העלויות הקבועות" in n for n in out["notes"])      # the loan saves interest alone, but not enough for the offer's own fees
    free = R.simulate(ITEMS, R.parse_offer({"rate": 6.0, "term_months": 120}))
    assert free["recommended_pays"] is True and free["recommended"]["total_saving_same_term"] > 0


def test_selection_and_fee_override():
    sel = R.simulate(ITEMS, R.parse_offer({"rate": 6, "term_months": 120, "loan_ids": ["hi"]}))
    assert sel["selected_ids"] == ["hi"] and sel["selected"]["loans"] == 1
    ov = R.simulate(ITEMS, R.parse_offer({"rate": 6, "term_months": 120, "fee_overrides": {"feeunk": 500}}))
    row = next(r for r in ov["rows"] if r["id"] == "feeunk")
    assert row["fee_known"] and row["verdict"] == "worth" and row["prepay_fee"] == 500.0


def test_a_stored_schedule_makes_the_remaining_interest_exact():
    from core.financial_control import amortization as A
    rows = [[f"2026-{m:02d}-10", 100.0, 10.0, 110.0, 400.0 - 100.0 * (m - 11), 1 if m < 11 else 0, 1] for m in range(11, 12)]
    sched = A.Schedule(ok=True, rows=[["2026-11-10", 500.0, 50.0, 550.0, 500.0, 0, 1], ["2026-12-10", 500.0, 25.0, 525.0, 0.0, 0, 1]])
    item = L.loan_item(rec("s", 1000, 6, 550, 2, fee="אין", **{"Amortization Schedule": A.dumps(sched)}), TODAY)
    row = R.simulate([item], OFFER, {"s": A.loads(A.dumps(sched))}, TODAY)["rows"][0]
    assert row["exact"] is True and row["interest_left"] == 75.0 and row["months"] == 2
    assert R.simulate([item], OFFER, None, TODAY)["rows"][0]["exact"] is False                  # no stored schedule given: an estimate, and labelled as one


@pytest.mark.parametrize("bad", [{}, {"rate": "x", "term_months": 120}, {"rate": 99, "term_months": 120}, {"rate": 5, "term_months": 3}, {"rate": 5, "term_months": 120, "fees": -1},
                                 {"rate": float("nan"), "term_months": 120}, {"rate": 5, "term_months": 120, "fee_overrides": {"a": "z"}}])
def test_offer_validation(bad):
    with pytest.raises(R.RefinanceInputError):
        R.parse_offer(bad)


def ident(uid, role):
    return Identity(user_id=uid, role=role, display_name=uid, tenant_id="boss_hq", domain_id=Domain.GENERAL, allowed_domains=[], channel="telegram", external_id=f"tg-{uid}")


def client(monkeypatch, who):
    app = Flask(__name__)
    app.register_blueprint(tma_api.tma_api)
    monkeypatch.setattr(tma_api, "_validate_initdata", lambda _: {"id": who.user_id})
    monkeypatch.setattr(tma_api, "resolve_identity", lambda *_: who)
    monkeypatch.setattr(tma_api, "_fcc_enabled", lambda identity=None: True)
    monkeypatch.setattr(service, "my_loans", lambda identity: RECS)
    return app.test_client()


def test_endpoint_is_owner_only_read_only_and_validates(monkeypatch):
    c = client(monkeypatch, ident("eliyahu", Role.OWNER))
    ok = c.post("/api/fcc/loans/refinance", json={"rate": 6, "term_months": 120, "fees": 3000}, headers=H)
    assert ok.status_code == 200 and ok.get_json()["recommended_ids"] == ["hi"]
    assert c.post("/api/fcc/loans/refinance", json={"rate": 99, "term_months": 120}, headers=H).status_code == 400
    assert c.post("/api/fcc/loans/refinance", data="not json", content_type="application/json", headers=H).status_code == 400
    assert c.post("/api/fcc/loans/refinance", data="x", content_type="text/plain", headers=H).status_code == 415
    other = client(monkeypatch, ident("avi", Role.PARTNER))
    assert other.post("/api/fcc/loans/refinance", json={"rate": 6, "term_months": 120}, headers=H).status_code == 404


# ── phase 1 accuracy: mathematical checks, written independently of the engine's own helpers ────────────────────────────────────────
def annuity_pay(bal, rate_pct, n):
    i = rate_pct / 1200.0
    return bal / n if i == 0 else bal * i / (1 - (1 + i) ** -n)


def annuity_interest(bal, rate_pct, n):
    return annuity_pay(bal, rate_pct, n) * n - bal


# three loans of very different lengths, each with a payment that is consistent with its own balance, rate and months
SHORT, MID, LONG = (10000.0, 9.0, 12), (30000.0, 8.0, 36), (60000.0, 7.0, 120)
MIXED = [L.loan_item(rec(name, b, r, round(annuity_pay(b, r, n), 2), n, fee="אין"), TODAY) for name, (b, r, n) in (("short", SHORT), ("mid", MID), ("long", LONG))]


def test_like_today_is_each_loan_over_its_own_months_never_the_longest_for_all():
    offer = R.parse_offer({"rate": 5.0, "term_months": 120, "fees": 2000})
    t = R.simulate(MIXED, offer)["selected"]
    expect_same = sum(annuity_interest(b, 5.0, n) for b, _r, n in (SHORT, MID, LONG))
    expect_keep = sum(annuity_interest(b, r, n) for b, r, n in (SHORT, MID, LONG))
    assert abs(t["same_term_interest"] - expect_same) < 1.5 and abs(t["current_interest_left"] - expect_keep) < 1.5
    assert abs(t["total_saving_same_term"] - (expect_keep - expect_same - 2000)) < 3.0
    wrong = annuity_interest(100000.0, 5.0, 120)                      # the old method: ONE annuity over the longest term for the whole balance
    assert abs(t["same_term_interest"] - wrong) > 1000                 # clearly not that
    assert t["same_term_months"] == 120


def test_group_saving_is_the_sum_of_the_loans_savings_minus_the_one_time_costs_once():
    offer = R.parse_offer({"rate": 5.0, "term_months": 120, "fees": 1500, "insurance_monthly": 20, "fee_overrides": {"short": 100, "mid": 200}})
    out = R.simulate(MIXED, offer)
    t = out["selected"]
    per_loan = sum(r["net_saving"] for r in out["rows"])               # each loan's saving already net of ITS OWN early-repayment fee
    assert t["one_time_costs"] == 1500 + 100 + 200                     # the offer's fees once + each loan's fee once
    assert abs(t["total_saving_same_term"] - (per_loan - 1500 - 20 * t["same_term_months"])) < 3.0
    again = R.simulate(MIXED + MIXED, R.parse_offer({"rate": 5.0, "term_months": 120, "fees": 1500, "insurance_monthly": 20, "fee_overrides": {"short": 100, "mid": 200},
                                                      "loan_ids": ["short", "short", "mid", "long", "long"]}))["selected"]
    assert again["loans"] == 3 and again["one_time_costs"] == t["one_time_costs"] and again["total_saving_same_term"] == t["total_saving_same_term"]   # no loan counted twice


def test_zero_saving_only_when_balance_rate_months_method_and_dates_are_identical():
    from core.financial_control import amortization as A
    from datetime import date as D
    rows = A.annuity_rows(24000.0, 8.0, 24, D(2026, 12, 10))          # a lender schedule built with the SAME method as the alternative
    item = L.loan_item(rec("same", 24000, 8.0, rows[0][3], 24, fee="אין", **{"Amortization Schedule": A.dumps(A.Schedule(ok=True, rows=rows))}), TODAY)
    same = R.simulate([item], R.parse_offer({"rate": 8.0, "term_months": 24}), {"same": rows}, TODAY)
    assert abs(same["rows"][0]["net_saving"]) < 1.0 and abs(same["selected"]["total_saving_same_term"]) < 1.0       # nothing to gain: same rate, same months, same method
    assert abs(same["selected"]["total_saving_offer_term"]) < 1.0 and same["selected"]["monthly_saving"] == 0
    other = R.simulate([item], R.parse_offer({"rate": 7.0, "term_months": 24}), {"same": rows}, TODAY)
    assert other["selected"]["total_saving_same_term"] > 100                                                            # a lower rate does save
    longer = R.simulate([item], R.parse_offer({"rate": 8.0, "term_months": 60}), {"same": rows}, TODAY)
    assert longer["selected"]["total_saving_offer_term"] < -100 and longer["selected"]["monthly_saving"] > 0           # same rate, longer term: relief, but it costs interest


def test_every_alternative_is_on_one_time_axis_including_the_months_after_the_loans_would_have_ended():
    out = R.simulate(MIXED, R.parse_offer({"rate": 5.0, "term_months": 240, "fees": 2000}))["selected"]
    years = out["timeline"]["years"]
    assert out["timeline"]["months"] == 240 and len(years) == 20
    assert years[0]["keep"]["payment"] > years[0]["stretch"]["payment"] > 0
    ended = next(y for y in years if y["keep"]["payment"] == 0)                       # the original loans are over...
    assert ended["year"] == 11 and ended["stretch"]["payment"] > 0 and ended["diff_stretch"] < 0     # ...the stretched mortgage still collects, shown as a negative difference
    for path in ("keep", "same_pace", "stretch"):
        assert years[-1][path]["debt_end"] == 0                                         # every path is fully repaid by the end of the axis
        debts = [y[path]["debt_end"] for y in years]
        assert all(a >= b for a, b in zip(debts, debts[1:]))                            # the debt only goes down
    # cumulative differences close exactly on the interest, insurance and fee identities
    assert abs(years[-1]["cum_diff_stretch"] - (out["current_interest_left"] - out["offer_interest"])) < 2.0
    assert abs(years[-1]["cum_diff_same_pace"] - (out["current_interest_left"] - out["same_term_interest"])) < 2.0
    assert abs(out["total_saving_offer_term"] - (years[-1]["cum_diff_stretch"] - out["one_time_costs"])) < 2.0


def test_saving_relief_and_future_debt_are_three_separate_readings():
    out = R.simulate(MIXED, R.parse_offer({"rate": 5.0, "term_months": 240, "fees": 2000}))["selected"]
    assert out["monthly_saving"] > 0 and out["total_saving_offer_term"] < 0                  # lower payment AND a worse total: relief is not a saving
    assert {"keep", "same_pace", "stretch", "years"} <= set(out["debt_ahead"][0])
    keep3 = next(d for d in out["debt_ahead"] if d["years"] == 3)
    assert keep3["keep"] < sum(b for b, _r, _n in (SHORT, MID, LONG)) and keep3["stretch"] > keep3["keep"]       # the stretched mortgage owes more after 3 years
    assert "monthly" not in out and "monthly" in R.simulate(MIXED, R.parse_offer({"rate": 5.0, "term_months": 240, "detail": True}))["selected"]


def test_estimated_schedule_is_consistent_and_labelled_an_estimate():
    item = L.loan_item(rec("est", 20000, 10.0, 700, 36), TODAY)
    out = R.simulate([item], R.parse_offer({"rate": 5.0, "term_months": 36}))
    assert out["rows"][0]["exact"] is False and out["selected"]["uses_estimates"] is True and out["selected"]["estimated_loans"] == ["est"]
    rows = R._estimate_rows(20000.0, 10.0, 700.0, 36, TODAY)
    assert abs(sum(r[2] for r in rows) - (700 * 36 - 20000)) < 1.0 and abs(sum(r[1] for r in rows) - 20000) < 1.0 and rows[-1][4] == 0
    assert any("בקירוב" in n for n in out["notes"])


def test_single_loan_results_equal_the_closed_form_and_the_group_of_one():
    out = R.simulate([MIXED[2]], R.parse_offer({"rate": 5.0, "term_months": 120}))
    row, t = out["rows"][0], out["selected"]
    b, r, n = LONG
    assert abs(row["same_term_interest"] - annuity_interest(b, 5.0, n)) < 1.0 and abs(row["interest_left"] - annuity_interest(b, r, n)) < 1.0
    assert abs(t["same_term_interest"] - row["same_term_interest"]) < 1.5 and abs(t["total_saving_same_term"] - row["net_saving"]) < 1.5       # a group of one is the loan itself


def test_a_schedule_stored_earlier_is_read_by_date_not_by_its_stale_charged_flag():
    from core.financial_control import amortization as A
    from datetime import date as D
    rows = A.annuity_rows(1200.0, 6.0, 12, D(2026, 6, 10))              # imported in June: every row flagged "not charged yet"
    assert A.remaining(rows)["payments"] == 12                           # by the stored flags nothing is behind us
    later = A.remaining(rows, D(2026, 11, 8))                           # by November, five of them (Jun..Oct) are behind us
    assert later["payments"] == 7 and later["interest"] < A.remaining(rows)["interest"]
    item = L.loan_item(rec("old", 700, 6, rows[0][3], 7, **{"Amortization Schedule": A.dumps(A.Schedule(ok=True, rows=rows), D(2026, 6, 1))}), TODAY)
    assert item["schedule_remaining"]["payments"] == 7 and item["interest_remaining"] == later["interest"]


def test_endpoint_reads_the_stored_schedule_and_returns_month_rows_only_on_request(monkeypatch):
    from core.financial_control import amortization as A
    rows = A.annuity_rows(12000.0, 9.0, 12, date.today().replace(day=28))
    rec_s = rec("sched", 12000, 9.0, rows[0][3], 12, fee="אין", **{"Amortization Schedule": A.dumps(A.Schedule(ok=True, rows=rows))})
    c = client(monkeypatch, ident("eliyahu", Role.OWNER))
    monkeypatch.setattr(service, "my_loans", lambda identity: [rec_s])
    out = c.post("/api/fcc/loans/refinance", json={"rate": 6, "term_months": 24}, headers=H).get_json()
    assert out["rows"][0]["exact"] is True and out["selected"]["uses_estimates"] is False and "monthly" not in out["selected"]
    full = c.post("/api/fcc/loans/refinance", json={"rate": 6, "term_months": 24, "detail": True}, headers=H).get_json()
    assert len(full["selected"]["monthly"]) == full["selected"]["timeline"]["months"] and len(full["selected"]["monthly"][0]["keep"]) == 3
