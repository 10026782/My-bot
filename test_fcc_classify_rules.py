"""FCC description classification — ``GET|POST /api/fcc/classify-rules``: the pending rows of the owner's Cashflow Rules become decided rules one description
at a time (Kind expense, Category, Status active), through the real executor (the fake gateway runs ``tma_write op=patch``). Synthetic data only."""

from __future__ import annotations

import pytest

import tma_api
from airtable_schema import CashflowRuleFields as CR
from airtable_schema import Tables
from core.financial_control import bank_import as bi
from core.financial_control import import_plan as ip
from core.financial_control import service
from test_fcc_classify import patched  # noqa: F401 — fixture (fake patch + the real executor)
from test_fcc_import_api import DB, ELI, ELIYAHU, H, PARTNER, aa, client, world  # noqa: F401 — `world` is the autouse fixture


def rule(i, match, times=1, amount=50.0, direction="debit", status="pending", kind=None, row_key=None, owner=ELI, applies="card"):
    f = {CR.MATCH: match, CR.APPLIES_TO: applies, CR.DIRECTION: direction, CR.STATUS: status, CR.TIMES_SEEN: times, CR.EXAMPLE_AMOUNT: amount,
         CR.LAST_SEEN: "2026-10-05", CR.FINANCIAL_OWNER: [owner]}
    if kind:
        f[CR.KIND] = kind
    if row_key:
        f[CR.ROW_KEY] = row_key
    return {"id": f"rec{i:014d}", "fields": f}


def seed():
    DB[Tables.CASHFLOW_RULES] = [
        rule(1, "משנת יוסף", times=4, amount=1114.3), rule(2, "פיצה אליה", times=2, amount=36.0), rule(3, "חנות בודדת", times=1, amount=500.0),
        rule(4, "משכורת אחרת", direction="credit", times=9), rule(5, "", row_key="bank:" + "a" * 20), rule(6, "כבר הוחלט", status="active", kind="expense"),
        rule(7, "של מישהו אחר", owner="recDana")]


def test_the_queue_has_only_the_owners_pending_expense_descriptions_most_seen_first():
    seed()
    waiting = service.rules_waiting(ELIYAHU)
    assert sorted(w["match"] for w in waiting) == ["חנות בודדת", "משנת יוסף", "פיצה אליה"]            # not: a credit, a row rule, a decided one, another owner's
    view = service.rules_view(waiting)
    assert view["total"] == 3 and view["item"]["match"] == "משנת יוסף" and view["item"]["times_seen"] == 4
    assert service.rules_view(waiting, frozenset({f"rec{1:014d}"}))["item"]["match"] == "פיצה אליה"
    assert service.rules_view([])["item"] is None


def test_the_cashflow_view_tells_how_many_descriptions_wait():
    seed()
    assert service.cashflow_view(ELIYAHU)["rules_to_classify"] == {"total": 3}


def test_get_is_owner_only(monkeypatch):
    seed()
    assert client(monkeypatch, flag=False).get("/api/fcc/classify-rules", headers=H).status_code == 404
    assert client(monkeypatch, who=PARTNER).get("/api/fcc/classify-rules", headers=H).status_code == 404
    body = client(monkeypatch).get("/api/fcc/classify-rules", headers=H).get_json()
    assert body["item"]["match"] == "משנת יוסף" and body["total"] == 3 and {"card_fees", "fees_interest"} <= {c["key"] for c in body["categories"]}
    assert client(monkeypatch).get(f"/api/fcc/classify-rules?skip=rec{1:014d}", headers=H).get_json()["item"]["match"] == "פיצה אליה"


def test_post_activates_ONE_rule_with_exactly_kind_category_and_status(monkeypatch, patched):
    seed()
    r = client(monkeypatch).post("/api/fcc/classify-rules", json={"rule_id": f"rec{1:014d}", "category": "living"}, headers=H)
    body = r.get_json()
    assert r.status_code == 200 and body["state"] == "done" and body["total"] == 2 and body["item"]["match"] == "פיצה אליה"
    assert patched == [(Tables.CASHFLOW_RULES, f"rec{1:014d}", {CR.KIND: "expense", CR.CATEGORY: "living", CR.STATUS: "active"})]


def test_the_decided_rule_decides_the_next_import(monkeypatch, patched):
    seed()
    client(monkeypatch).post("/api/fcc/classify-rules", json={"rule_id": f"rec{1:014d}", "category": "קייטרינג חדש"}, headers=H)
    rules = bi.owner_rules_from(service.cashflow_rule_items(service.my_cashflow_rules(ELIYAHU), "card"))
    assert ("משנת יוסף", "expense", "קייטרינג חדש") in [(r.match, r.kind, r.category) for r in rules]


def test_post_refuses_what_is_not_a_waiting_expense_description_and_bad_input(monkeypatch, patched):
    seed()
    c = client(monkeypatch)
    for rid in (4, 5, 6, 7, 99):          # a credit, a row rule, already decided, another owner's, missing: all answered alike
        assert c.post("/api/fcc/classify-rules", json={"rule_id": f"rec{rid:014d}", "category": "living"}, headers=H).status_code == 404
    assert c.post("/api/fcc/classify-rules", json={"rule_id": f"rec{1:014d}", "category": ""}, headers=H).status_code == 400
    assert c.post("/api/fcc/classify-rules", json={"rule_id": f"rec{1:014d}", "category": "uncategorized"}, headers=H).status_code == 400
    assert c.post("/api/fcc/classify-rules", json={"rule_id": "x", "category": "living"}, headers=H).status_code == 400
    assert client(monkeypatch, who=PARTNER).post("/api/fcc/classify-rules", json={"rule_id": f"rec{1:014d}", "category": "living"}, headers=H).status_code == 404
    assert patched == []


def test_a_failing_write_is_reported(monkeypatch, patched):
    seed()
    monkeypatch.setattr(tma_api, "_queue_or_owner_execute", lambda *a, **k: ("a", {"error": "x"}, 500))
    r = client(monkeypatch).post("/api/fcc/classify-rules", json={"rule_id": f"rec{1:014d}", "category": "living"}, headers=H)
    assert r.status_code == 500 and r.get_json()["state"] == "partial_failure"


# ── the allow-list: the rules table is writable through tma_write ONLY for this patch ───────────────────────────
GOOD = {"Kind": "expense", "Category": "living", "Status": "active"}


@pytest.mark.parametrize("fields", [None, {}, {**GOOD, "Match": "x"}, {"Kind": "expense", "Category": "living"}, {**GOOD, "Kind": "income"}, {**GOOD, "Status": "pending"},
                                    {**GOOD, "Category": ""}, {**GOOD, "Category": "x" * 41}, {**GOOD, "Category": 5}])
def test_the_rule_patch_validator_refuses_anything_but_the_exact_shape(fields):
    assert aa.validate_rule_patch(fields) is not None
    assert aa.validate_rule_patch(GOOD) is None


def test_the_executor_and_the_gateway_refuse_other_writes_to_the_rules_table(monkeypatch):
    seed()
    ctx = {"contract_id": "c1", "approved_by": "eliyahu", "claim_execution_id": "x1"}
    for op, fields in (("post", GOOD), ("patch", {**GOOD, "Kind": "income"}), ("patch", {"Notes": "x"})):
        out = aa.tma_write(op=op, table=Tables.CASHFLOW_RULES, record_id=f"rec{1:014d}", fields=fields, requested_by="eliyahu", identity=ELIYAHU,
                           trusted_source="tma_api", execution_context=ctx)
        assert out.get("ok") is False
    assert DB[Tables.CASHFLOW_RULES][0]["fields"].get(CR.KIND) is None
