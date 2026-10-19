"""C2 — unified net worth: ``core.financial_control.net_worth`` (pure) + ``service.net_worth_view`` + GET /api/fcc/net-worth.

Covers: the breakdown, no double counting of asset-linked debt, receivables apart from the net, sold assets leave, missing is never 0,
no leak between owners, owner-only gate (404 for everyone else), read-only, and a read failure never degrading into a wrong number.
In-memory Airtable fakes; no network.
"""

from __future__ import annotations

import os

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-nw-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:NW_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patNwTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appNwTest")
os.environ.setdefault("ELIYAHU_CHAT_ID", "1")

from datetime import date

import pytest
from flask import Flask

import identity as identity_module
import tma_api
from airtable_schema import AssetFields as AS
from airtable_schema import FinAccountFields as ACF
from airtable_schema import FinEventFields as EF
from airtable_schema import LoanFields as LF
from airtable_schema import Tables
from core import data_access_policy as policy
from core import owner_resolution
from core.financial_control import loans as fcc_loans
from core.financial_control import net_worth as nw
from core.financial_control import service
from identity import Domain, Identity, Role

TODAY = date(2026, 10, 19)
ELI, AVI = "recEli", "recAvi"
PROFILES = [{"id": ELI, "fields": {"name": "Eliyahu"}}, {"id": AVI, "fields": {"name": "Avi"}}]


def ident(uid, role):
    return Identity(user_id=uid, role=role, display_name=uid, tenant_id="boss_hq", domain_id=Domain.GENERAL,
                    allowed_domains=[], channel="telegram", external_id=f"tg-{uid}")


ELIYAHU, AVI_I = ident("eliyahu", Role.OWNER), ident("avi", Role.PARTNER)
H = {"X-Telegram-Init-Data": "valid"}


def acct(aid, name, owner=ELI, **f):
    return {"id": aid, "fields": {ACF.NAME: name, ACF.ACCOUNT_TYPE: "liquid", ACF.STATUS: "active", ACF.FINANCIAL_OWNER: [owner], **f}}


def snap(eid, account, amount, day="2026-10-01", owner=ELI):
    return {"id": eid, "fields": {EF.KIND: "balance_snapshot", EF.AMOUNT: amount, EF.OCCURRED_AT: day, EF.ACCOUNT: [account],
                                  EF.FINANCIAL_OWNER: [owner]}}


def asset(rid, name, value=None, pct=100, mortgage=None, status=None, owner=ELI):
    f = {AS.NAME: name, "Owner": [owner]}
    for key, v in ((AS.VALUE, value), (AS.OWNERSHIP_PCT, pct), (AS.MORTGAGE, mortgage), (AS.STATUS, status)):
        if v is not None:
            f[key] = v
    return {"id": rid, "fields": f}


def loan(rid, name, balance=None, asset_id=None, owed_to_me=False, status=None, owner=ELI):
    f = {LF.NAME: name, "Owner": [owner], LF.ACTIVE: True}
    if balance is not None:
        f[LF.EARLY_CLOSURE] = balance
    if asset_id:
        f[LF.RELATED_ASSET] = [asset_id]
    if owed_to_me:
        f[LF.DIRECTION] = fcc_loans.DIRECTION_TO_ME_STORED
    if status:
        f[LF.STATUS] = status
    return {"id": rid, "fields": f}


def view(accounts, events, assets, loans, today=TODAY):
    """The pure model over already-scoped rows (what the service hands it)."""
    from core.financial_control import accounts as fcc_accounts
    return nw.net_worth(fcc_accounts.accounts_overview(accounts, events, today), assets,
                        [fcc_loans.loan_item(r, today) for r in loans], today)


# ── pure model ────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_breakdown_accounts_plus_assets_minus_liabilities_with_dates():
    v = view([acct("recA1", "עו״ש")], [snap("recS", "recA1", 50000, "2026-10-10")],
             [asset("recH", "דירה", 2_000_000)], [loan("recL", "הלוואה פרטית", 30000)])
    assert v["accounts"]["total"] == 50000 and v["assets"]["total"] == 2_000_000 and v["liabilities"]["total"] == 30000
    assert v["net"] == 2_020_000 and v["partial"] is False
    assert v["accounts"]["items"][0]["as_of"] == "2026-10-10" and v["accounts"]["oldest_as_of"] == "2026-10-10"
    assert v["assets"]["as_of_known"] is False and v["assets"]["items"][0]["as_of"] is None          # no stored date: unknown, not invented


def test_account_value_is_the_reported_balance_never_the_estimate():
    dep = {"id": "recD", "fields": {EF.KIND: "deposit", EF.AMOUNT: 9999, EF.OCCURRED_AT: "2026-10-12", EF.ACCOUNT: ["recA1"],
                                    EF.FINANCIAL_OWNER: [ELI]}}
    v = view([acct("recA1", "עו״ש")], [snap("recS", "recA1", 1000), dep], [], [])
    assert v["net"] == 1000 and v["accounts"]["total"] == 1000


def test_asset_debt_linked_loan_and_asset_mortgage_are_deducted_once():
    # the same 400k mortgage appears twice: as the asset's own field and as a Loan linked to the asset
    v = view([], [], [asset("recH", "דירה", 1_000_000, mortgage=400_000)], [loan("recM", "משכנתא", 400_000, asset_id="recH")])
    assert v["liabilities"]["total"] == 400_000 and v["net"] == 600_000
    row = v["assets"]["items"][0]
    assert row["debt_source"] == "linked_loans" and row["ignored_mortgage_balance"] == 400_000


def test_linked_loan_without_balance_stays_missing_even_when_the_asset_has_a_mortgage_balance():
    v = view([], [], [asset("recH", "דירה", 1_000_000, mortgage=300_000)], [loan("recM", "משכנתא ללא יתרה", None, asset_id="recH")])
    row = v["assets"]["items"][0]
    assert v["liabilities"]["total"] is None and row["debt"] is None and row["debt_source"] == "linked_loans"      # no silent fall back to the asset's field
    assert row["ignored_mortgage_balance"] == 300_000 and v["net"] == 1_000_000
    assert v["gaps"]["debts_without_balance"] == 1 and v["partial"] is True


def test_asset_mortgage_without_a_loan_is_a_separate_debt_deducted_in_full_and_unverified():
    v = view([], [], [asset("recH", "דירה", 1_000_000, pct=50, mortgage=200_000)], [])
    row = v["assets"]["items"][0]
    assert v["assets"]["total"] == 500_000 and v["liabilities"]["total"] == 200_000 and v["net"] == 300_000       # NOT 400_000: no split by ownership
    assert row["debt_source"] == "asset_mortgage" and row["debt_responsibility_known"] is False
    assert v["gaps"]["asset_debts_unverified"] == 1 and v["partial"] is True


def test_two_linked_loans_sum_and_unlinked_loan_stands_alone():
    v = view([], [], [asset("recH", "דירה", 1_000_000)],
             [loan("recM1", "מסלול א", 200_000, asset_id="recH"), loan("recM2", "מסלול ב", 100_000, asset_id="recH"), loan("recP", "פרטית", 50_000)])
    assert v["liabilities"]["on_assets"] == 300_000 and v["liabilities"]["standalone"] == 50_000
    assert v["liabilities"]["total"] == 350_000 and v["net"] == 650_000


def test_partial_ownership_scales_the_value_but_a_recorded_loan_is_deducted_in_full():
    # owner example: asset 2,000,000 at 50% + a 600,000 loan in his name => 400,000 (not 700,000)
    v = view([], [], [asset("recH", "דירה", 2_000_000, pct=50)], [loan("recM", "משכנתא", 600_000, asset_id="recH")])
    assert v["assets"]["total"] == 1_000_000 and v["liabilities"]["total"] == 600_000 and v["net"] == 400_000
    assert v["partial"] is False and v["assets"]["items"][0]["debt_responsibility_known"] is True


def test_sold_asset_leaves_but_its_open_loan_stays_a_liability():
    v = view([], [], [asset("recS", "נמכר", 900_000, status="נמכר"), asset("recH", "דירה", 100_000)],
             [loan("recL", "הלוואה על נכס שנמכר", 70_000, asset_id="recS")])
    assert v["assets"]["total"] == 100_000 and v["assets"]["sold_excluded"] == 1 and [a["id"] for a in v["assets"]["items"]] == ["recH"]
    assert v["liabilities"]["total"] == 70_000 and v["liabilities"]["standalone_items"][0]["note"] == "linked_to_sold_asset"
    assert v["net"] == 30_000


def test_receivables_are_apart_and_not_in_the_net():
    v = view([], [], [], [loan("recR", "חייב לי חבר", 25_000, owed_to_me=True), loan("recL", "שלי", 10_000)])
    assert v["net"] == -10_000
    assert v["receivables"]["in_net"] is False and v["receivables"]["total"] == 25_000 and v["receivables"]["label"] == "expected_uncertain"
    assert v["liabilities"]["total"] == 10_000 and "חייב לי חבר" not in str(v["liabilities"])


def test_paid_off_loan_is_not_a_liability():
    v = view([], [], [], [loan("recL", "נסגרה", 10_000, status="Paid Off")])
    assert v["liabilities"]["total"] is None and v["net"] is None


def test_missing_data_is_missing_not_zero():
    v = view([acct("recA1", "עו״ש"), acct("recA2", "בלי יתרה")], [snap("recS", "recA1", 1000)],
             [asset("recX", "בלי שווי", None), asset("recY", "בלי בעלות", 500_000, pct=None, mortgage=100_000)], [])
    assert v["accounts"]["total"] == 1000 and v["accounts"]["missing"] == [{"id": "recA2", "name": "בלי יתרה"}]
    assert v["assets"]["total"] is None                                               # nothing counted: None, not 0
    assert v["liabilities"]["total"] == 100_000                                       # the known debt is NOT dropped with its asset
    assert v["gaps"] == {"accounts_without_balance": 1, "assets_left_out": 2, "debts_without_balance": 0, "asset_debts_unverified": 1} and v["partial"] is True
    assert {a["id"]: a["missing"] for a in v["assets"]["items"]} == {"recX": ["missing_value"], "recY": ["missing_ownership"]}
    assert v["net"] == 1000 - 100_000


def test_asset_without_value_keeps_its_linked_debt_so_the_net_is_never_inflated():
    v = view([acct("recA1", "עו״ש")], [snap("recS", "recA1", 50_000)], [asset("recH", "מגרש", None)], [loan("recM", "משכנתא", 300_000, asset_id="recH")])
    row = v["assets"]["items"][0]
    assert row["counted"] is False and row["missing"] == ["missing_value"] and row["value"] is None and row["debt"] == 300_000
    assert v["assets"]["total"] is None and v["liabilities"]["total"] == 300_000 and v["net"] == -250_000
    assert v["partial"] is True and v["gaps"]["assets_left_out"] == 1


def test_asset_without_ownership_keeps_its_linked_debt_too():
    v = view([], [], [asset("recH", "דירה", 1_000_000, pct=None)], [loan("recM", "משכנתא", 400_000, asset_id="recH")])
    assert v["assets"]["total"] is None and v["liabilities"]["total"] == 400_000 and v["net"] == -400_000 and v["partial"] is True


def test_account_freshness_current_stale_missing_with_an_exposed_threshold():
    v = view([acct("recA1", "טרי"), acct("recA2", "ישן"), acct("recA3", "בלי יתרה")],
             [snap("recS1", "recA1", 10, "2026-10-10"), snap("recS2", "recA2", 20, "2026-01-01")], [], [])
    acc = v["accounts"]
    assert acc["stale_after_days"] == nw.STALE_AFTER_DAYS == 90
    assert {i["id"]: i["freshness"] for i in acc["items"]} == {"recA1": "current", "recA2": "stale"}
    assert acc["freshness"] == {"current": 1, "stale": 1, "missing": 1}
    assert v["assets"]["as_of_known"] is False and v["liabilities"]["as_of_known"] is False


def test_nothing_known_gives_no_net():
    v = view([], [], [], [])
    assert v["net"] is None and v["accounts"]["total"] is None and v["partial"] is False


# ── service: owner scoping, read failures ─────────────────────────────────────────────────────────────────────────────
DB: dict = {}


@pytest.fixture(autouse=True)
def fakes(monkeypatch):
    DB.clear()
    DB.update({
        Tables.FIN_ACCOUNTS: [acct("recAE", "החשבון שלי"), acct("recAA", "החשבון של אבי", AVI)],
        Tables.FIN_EVENTS: [snap("recS1", "recAE", 100_000), snap("recS2", "recAA", 777_777, owner=AVI)],
        "Assets": [asset("recHE", "הדירה שלי", 1_000_000), asset("recHA", "הדירה של אבי", 5_555_555, owner=AVI)],
        Tables.LOANS: [loan("recLE", "הלוואה שלי", 40_000), loan("recLA", "ההלוואה של אבי", 666_666, owner=AVI),
                       loan("recRA", "חייב לאבי", 12_345, owed_to_me=True, owner=AVI)],
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


def test_no_leak_between_owners():
    mine = service.net_worth_view(ELIYAHU, TODAY)
    assert mine["net"] == 100_000 + 1_000_000 - 40_000
    text = str(mine)
    for foreign in ("777777", "5555555", "666666", "12345", "אבי"):
        assert foreign not in text
    assert mine["receivables"]["count"] == 0
    theirs = service.net_worth_view(AVI_I, TODAY)
    assert theirs["net"] == 777_777 + 5_555_555 - 666_666 and theirs["receivables"]["total"] == 12_345
    assert "1000000" not in str(theirs) and "הדירה שלי" not in str(theirs)


def test_unresolved_identity_is_denied():
    with pytest.raises(policy.PersonalDataAccessDenied):
        service.net_worth_view(ident("nobody", Role.MANAGER), TODAY)


def test_a_failed_read_is_not_turned_into_a_wrong_number(monkeypatch):
    def broken(table, formula=""):
        if table == Tables.LOANS:
            raise RuntimeError("airtable down")
        return list(DB.get(table, []))
    monkeypatch.setattr(service, "_read", broken)
    with pytest.raises(RuntimeError):
        service.net_worth_view(ELIYAHU, TODAY)                        # not an empty loans list that would inflate the net worth
    r = http(monkeypatch, ELIYAHU).get("/api/fcc/net-worth", headers=H)
    assert r.status_code == 500 and r.get_json() == {"error": "internal error"}


# ── HTTP gate ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_http_flag_off_and_non_owner_get_404(monkeypatch):
    assert http(monkeypatch, ELIYAHU, flag=False).get("/api/fcc/net-worth", headers=H).status_code == 404
    assert http(monkeypatch, AVI_I).get("/api/fcc/net-worth", headers=H).status_code == 404         # partner: not the owner role
    assert http(monkeypatch, ident("lead1", Role.LEAD)).get("/api/fcc/net-worth", headers=H).status_code == 404


def test_http_owner_gets_own_view_only_and_it_is_read_only(monkeypatch):
    c = http(monkeypatch, ELIYAHU)
    r = c.get("/api/fcc/net-worth", headers=H)
    body = r.get_json()
    assert r.status_code == 200 and body["net"] == 1_060_000
    assert "777777" not in str(body) and "הדירה של אבי" not in str(body)
    for method in ("post", "put", "patch", "delete"):
        assert getattr(c, method)("/api/fcc/net-worth", headers=H, json={}).status_code == 405
    assert len(DB[Tables.LOANS]) == 3 and len(DB["Assets"]) == 2


def test_http_unresolved_identity_403(monkeypatch):
    assert http(monkeypatch, ident("nobody", Role.OWNER)).get("/api/fcc/net-worth", headers=H).status_code == 403


def test_http_partial_data_is_stable_and_exposes_the_stale_threshold(monkeypatch):
    # an asset without a value + a linked loan without a balance (+ the asset's own mortgage) + an account without a balance + a stale one
    DB[Tables.FIN_ACCOUNTS] = [acct("recOld", "ישן"), acct("recNone", "בלי יתרה")]
    DB[Tables.FIN_EVENTS] = [snap("recS", "recOld", 5_000, "2026-01-01")]
    DB["Assets"] = [asset("recH", "מגרש", None, mortgage=90_000)]
    DB[Tables.LOANS] = [loan("recL", "הלוואה בלי יתרה", None, asset_id="recH")]
    r = http(monkeypatch, ELIYAHU).get("/api/fcc/net-worth", headers=H)
    body = r.get_json()
    assert r.status_code == 200 and body["partial"] is True
    assert body["accounts"]["stale_after_days"] == 90 and body["accounts"]["freshness"] == {"current": 0, "stale": 1, "missing": 1}
    assert body["net"] == 5_000 and body["assets"]["total"] is None and body["liabilities"]["total"] is None       # unknown stays unknown, not 0
    assert body["gaps"]["debts_without_balance"] == 1 and body["assets"]["items"][0]["ignored_mortgage_balance"] == 90_000
    assert body["assets"]["items"][0]["missing"] == ["missing_value"]
