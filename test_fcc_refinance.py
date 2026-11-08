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
    assert by["near"]["net_saving"] > 0 and by["near"]["verdict"] == "not_worth" and "רוב הריבית כבר שולמה" in by["near"]["reason"]    # a few shekels of saving is not a reason
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
    row = R.simulate([item], OFFER)["rows"][0]
    assert row["exact"] is True and row["interest_left"] == 75.0 and row["months"] == 2


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
