"""FCC cashflow — ``service.cashflow_inputs`` / ``service.cashflow_view`` + GET /api/fcc/cashflow.

Owner scoping (nothing of another person reaches a number), income sources (child goal / "מקור: X" note / "כללי" / standing fixed income),
expenses by category (custom + uncategorized, superseded ignored), loans as a scheduled expense for the current month, the HTTP gate and the
read-only guarantee. In-memory Airtable fakes; no network.
"""

from __future__ import annotations

import os

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-cf-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:CF_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patCfTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appCfTest")
os.environ.setdefault("ELIYAHU_CHAT_ID", "1")

from datetime import date

import pytest
from flask import Flask

import identity as identity_module
import tma_api
from airtable_schema import FinEventFields as EF
from airtable_schema import FinGoalFields as GF
from airtable_schema import LoanFields as LF
from airtable_schema import RecObFields as RF
from airtable_schema import Tables
from core import data_access_policy as policy
from core import owner_resolution
from core.financial_control import service
from identity import Domain, Identity, Role

TODAY = date(2026, 10, 20)
ELI, AVI = "recEli", "recAvi"
PROFILES = [{"id": ELI, "fields": {"name": "Eliyahu"}}, {"id": AVI, "fields": {"name": "Avi"}}]
H = {"X-Telegram-Init-Data": "valid"}


def ident(uid, role):
    return Identity(user_id=uid, role=role, display_name=uid, tenant_id="boss_hq", domain_id=Domain.GENERAL,
                    allowed_domains=[], channel="telegram", external_id=f"tg-{uid}")


ELIYAHU, AVI_I = ident("eliyahu", Role.OWNER), ident("avi", Role.PARTNER)


def goal(gid, title, category, owner=ELI, parent=None, target=None, start=None):
    f = {GF.TITLE: title, GF.CATEGORY: category, GF.STATUS: "active", GF.FINANCIAL_OWNER: [owner]}
    if parent:
        f[GF.PARENT_GOAL] = [parent]
    if target is not None:
        f[GF.TARGET_AMOUNT] = target
    if start:
        f[GF.START_DATE] = start
    return {"id": gid, "fields": f}


def ev(eid, goal_id, kind, amount, day, note=None, category=None, owner=ELI, superseded=False):
    f = {EF.KIND: kind, EF.AMOUNT: amount, EF.OCCURRED_AT: day, EF.GOAL: [goal_id], EF.FINANCIAL_OWNER: [owner]}
    if note:
        f[EF.NOTE] = note
    if category:
        f[EF.EXPENSE_CATEGORY] = category
    if superseded:
        f[EF.SUPERSEDED_BY] = ["recNew"]
    return {"id": eid, "fields": f}


def loan(rid, name, payment, owner=ELI):
    return {"id": rid, "fields": {LF.NAME: name, "Owner": [owner], LF.ACTIVE: True, LF.MONTHLY_PAYMENT: payment}}


DB: dict = {}


@pytest.fixture(autouse=True)
def fakes(monkeypatch):
    DB.clear()
    DB.update({
        Tables.FIN_GOALS: [
            goal("recTotal", "הכנסה חודשית", "income"),
            goal("recTrips", "נסיעות", "income", parent="recTotal"),
            goal("recFixed", "נוף הגליל", "fixed_income", target=8000, start="2026-09-01"),
            goal("recHome", "הוצאות בית", "household"),
            goal("recGAvi", "הכנסה של אבי", "income", owner=AVI),
        ],
        Tables.FIN_EVENTS: [
            ev("e1", "recTrips", "one_time", 3000, "2026-10-05"),
            ev("e2", "recTrips", "direct_cost", 400, "2026-10-06"),
            ev("e3", "recTotal", "one_time", 700, "2026-10-09", note="מקור: תיווך"),
            ev("e4", "recTotal", "one_time", 300, "2026-10-10"),
            ev("e5", "recHome", "household_expense", 1200, "2026-10-03", category="living"),
            ev("e6", "recHome", "household_expense", 300, "2026-10-04", category="חיות מחמד"),
            ev("e7", "recHome", "household_expense", 90, "2026-10-05"),
            ev("e8", "recHome", "household_expense", 5000, "2026-10-06", category="living", superseded=True),
            ev("x1", "recGAvi", "one_time", 99999, "2026-10-02", owner=AVI),
            ev("x2", "recGAvi", "household_expense", 88888, "2026-10-02", category="living", owner=AVI),
        ],
        Tables.LOANS: [loan("recL1", "הלוואה שלי", 2500), loan("recLA", "של אבי", 77777, owner=AVI)],
    })

    def fake_profile(table, query, **kw):
        _f, value, _s, _ci = query.arguments
        return [p for p in PROFILES if p["fields"]["name"].casefold() == str(value).casefold()]
    monkeypatch.setattr(owner_resolution, "list_records", fake_profile)
    monkeypatch.setattr(identity_module, "_REGISTRY", {
        "telegram:1": {"tenant": "boss_hq", "user": "eliyahu", "role": "owner"},
        "telegram:2": {"tenant": "boss_hq", "user": "avi", "role": "partner"},
    })
    monkeypatch.setattr(service, "_read", lambda table, formula="": list(DB.get(table, [])))


def http(monkeypatch, who, flag=True):
    app = Flask(__name__)
    app.register_blueprint(tma_api.tma_api)
    monkeypatch.setattr(tma_api, "_validate_initdata", lambda _: {"id": who.user_id})
    monkeypatch.setattr(tma_api, "resolve_identity", lambda *_: who)
    monkeypatch.setattr(tma_api, "_fcc_enabled", lambda identity=None: flag)
    return app.test_client()


def month(view, key):
    return next(r for r in view["months"] if r["month"] == key)


def test_income_sources_child_note_general_and_standing_fixed():
    oct_ = month(service.cashflow_view(ELIYAHU, TODAY, 3), "2026-10")["income"]
    by = {s["name"]: s for s in oct_["sources"]}
    assert set(by) == {"נוף הגליל", "נסיעות", "תיווך", "כללי"}
    assert (by["נסיעות"]["gross"], by["נסיעות"]["direct_costs"], by["נסיעות"]["net"]) == (3000.0, 400.0, 2600.0)
    assert by["תיווך"]["gross"] == 700.0 and by["כללי"]["gross"] == 300.0 and by["כללי"]["kind"] == "general"
    assert by["נוף הגליל"]["gross"] == 8000.0 and by["נוף הגליל"]["basis"] == "standing"
    assert oct_["net"] == 8000 + 2600 + 700 + 300
    assert month(service.cashflow_view(ELIYAHU, TODAY, 3), "2026-08")["income"]["known"] is False      # before the standing income started


def test_expenses_custom_uncategorized_superseded_and_scheduled_loans():
    exp = month(service.cashflow_view(ELIYAHU, TODAY, 2), "2026-10")["expenses"]
    cats = {c["key"]: c for c in exp["categories"]}
    assert cats["living"]["amount"] == 1200.0                        # the superseded 5,000 is ignored
    assert cats["חיות מחמד"]["amount"] == 300.0 and cats["חיות מחמד"]["custom"] is True
    assert cats["uncategorized"]["amount"] == 90.0
    assert cats["loans"]["amount"] == 2500.0 and cats["loans"]["basis"] == "scheduled"
    assert exp["total"] == 1200 + 300 + 90 + 2500
    assert service.cashflow_view(ELIYAHU, TODAY, 2)["loans_payments_known"] is True


def test_recorded_loan_charge_beats_the_scheduled_payment():
    DB[Tables.FIN_EVENTS].append(ev("e9", "recHome", "household_expense", 2400, "2026-10-02", category="loans"))
    loans = next(c for c in month(service.cashflow_view(ELIYAHU, TODAY, 2), "2026-10")["expenses"]["categories"] if c["key"] == "loans")
    assert loans["amount"] == 2400.0 and loans["basis"] == "recorded"


def test_no_leak_between_owners():
    text = str(service.cashflow_view(ELIYAHU, TODAY, 3))
    for foreign in ("99999", "88888", "77777", "הכנסה של אבי"):
        assert foreign not in text
    theirs = service.cashflow_view(AVI_I, TODAY, 3)
    assert month(theirs, "2026-10")["income"]["gross"] == 99999.0 and "נסיעות" not in str(theirs)


def test_unresolved_identity_is_denied():
    with pytest.raises(policy.PersonalDataAccessDenied):
        service.cashflow_view(ident("nobody", Role.MANAGER), TODAY, 3)


def test_a_failed_loans_read_means_no_scheduled_payment_not_a_guess(monkeypatch):
    def broken(table, formula=""):
        if table == Tables.LOANS:
            raise RuntimeError("airtable down")
        return list(DB.get(table, []))
    monkeypatch.setattr(service, "_read", broken)
    view = service.cashflow_view(ELIYAHU, TODAY, 2)
    assert view["loans_payments_known"] is False
    assert "loans" not in {c["key"] for c in month(view, "2026-10")["expenses"]["categories"]}


def test_http_gate_validation_and_read_only(monkeypatch):
    assert http(monkeypatch, ELIYAHU, flag=False).get("/api/fcc/cashflow", headers=H).status_code == 404
    assert http(monkeypatch, AVI_I).get("/api/fcc/cashflow", headers=H).status_code == 404
    assert http(monkeypatch, ident("nobody", Role.OWNER)).get("/api/fcc/cashflow", headers=H).status_code == 403
    c = http(monkeypatch, ELIYAHU)
    assert c.get("/api/fcc/cashflow?months=abc", headers=H).status_code == 400
    assert c.get("/api/fcc/cashflow?months=0", headers=H).status_code == 400
    assert c.get("/api/fcc/cashflow?months=99", headers=H).status_code == 400
    r = c.get("/api/fcc/cashflow?months=3", headers=H)
    body = r.get_json()
    assert r.status_code == 200 and len(body["months"]) == 3 and "99999" not in str(body)
    for method in ("post", "put", "patch", "delete"):
        assert getattr(c, method)("/api/fcc/cashflow", headers=H, json={}).status_code == 405
    assert len(DB[Tables.FIN_EVENTS]) == 10 and len(DB[Tables.LOANS]) == 2


def ob(rid, name, amount, owner=ELI, **f):
    return {"id": rid, "fields": {RF.NAME: name, RF.AMOUNT: amount, RF.FREQUENCY: "monthly", RF.ACTIVE: True, RF.FINANCIAL_OWNER: [owner], **f}}


def test_recommendations_read_the_owners_own_commitments_only_and_never_add_them_to_totals(monkeypatch):
    DB[Tables.REC_OBLIGATIONS] = [
        ob("recO1", "נטפליקס", 70, **{RF.REVIEW_STATUS: "cancel"}),
        ob("recO2", "סלולר", 200, **{RF.REVIEW_STATUS: "negotiate", RF.POTENTIAL_SAVING: 60}),
        ob("recO3", "של אבי", 999, owner=AVI, **{RF.REVIEW_STATUS: "cancel"}),
        ob("recO4", "ישנה", 50, **{RF.REVIEW_STATUS: "cancel", RF.ACTIVE: False}),
    ]
    view = service.cashflow_view(ELIYAHU, TODAY, 2)
    rec = view["recommendations"]
    assert rec["commitments_known"] is True
    assert {i["id"] for i in rec["items"] if i["kind"] == "commitment"} == {"commitment:נטפליקס", "commitment:סלולר"}      # not Avi's, not the cancelled one
    assert (rec["summary"]["stated_saving"], rec["summary"]["inferred_saving"]) == (60.0, 70.0)
    assert "של אבי" not in str(view)
    base = service.cashflow_view(ELIYAHU, TODAY, 2)
    assert month(view, "2026-10")["expenses"]["total"] == month(base, "2026-10")["expenses"]["total"]                     # commitments are not expenses
    DB[Tables.REC_OBLIGATIONS] = []
    assert month(service.cashflow_view(ELIYAHU, TODAY, 2), "2026-10")["expenses"]["total"] == month(view, "2026-10")["expenses"]["total"]


def test_a_failed_commitments_read_is_unknown_not_empty(monkeypatch):
    def broken(table, formula=""):
        if table == Tables.REC_OBLIGATIONS:
            raise RuntimeError("airtable down")
        return list(DB.get(table, []))
    monkeypatch.setattr(service, "_read", broken)
    rec = service.cashflow_view(ELIYAHU, TODAY, 2)["recommendations"]
    assert rec["commitments_known"] is False and not [i for i in rec["items"] if i["kind"] in ("commitment", "optional")]


def imp(eid, kind, amount, day, category=None, note=None, owner=ELI):
    f = {EF.KIND: kind, EF.AMOUNT: amount, EF.OCCURRED_AT: day, EF.SOURCE: "import:bank", EF.FINANCIAL_OWNER: [owner], EF.IDEMPOTENCY_KEY: f"bank:{eid}"}
    if category:
        f[EF.EXPENSE_CATEGORY] = category
    if note:
        f[EF.NOTE] = note
    return {"id": eid, "fields": f}


def test_rows_imported_from_a_statement_have_no_goal_and_still_reach_the_cashflow_the_household_card_and_not_the_progress_list():
    DB[Tables.FIN_EVENTS] += [imp("recI1", "household_expense", 500.0, "2026-10-05", "taxes"), imp("recI2", "household_expense", -300.0, "2026-10-06", "taxes"),
                              imp("recI3", "one_time", 8000.0, "2026-10-01", note="מקור: עבודת אשתי"),
                              imp("recI4", "one_time", 99.0, "2026-10-01", note="בלי שם מקור"),                        # no "מקור:" name: not a source
                              imp("recX9", "household_expense", 77777.0, "2026-10-05", "taxes", owner=AVI)]
    view = service.cashflow_view(ELIYAHU, TODAY, 2)
    octo = month(view, "2026-10")
    taxes = next(c for c in octo["expenses"]["categories"] if c["key"] == "taxes")
    assert taxes["amount"] == 200.0                                                                                # 500 - 300 refund
    assert {s["name"]: s["gross"] for s in octo["income"]["sources"]}["עבודת אשתי"] == 8000.0
    assert "77777" not in str(view) and "99.0" not in str([s for s in octo["income"]["sources"]])
    ov = service.overview(ELIYAHU, TODAY)
    assert ov["household"]["month_total"] == 1200 + 300 + 90 + 200                                                # the existing household rows + the imported net 200
    assert not [e for e in ov["recent_events"] if e.get("Amount") in (500.0, -300.0, 8000.0, 99.0)]               # a statement import is not goal progress

