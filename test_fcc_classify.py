"""FCC one-by-one classification of imported expenses — ``GET|POST /api/fcc/classify``, the queue read model, the two new fee categories and the
allow-list change (an import record may have no category yet). The ActionGateway ceremony is replaced by a fake that runs the REAL executor
(``tma_write op=patch``): the owner policy, the field the server chose and the audit are the real code. Synthetic data only."""

from __future__ import annotations

import pytest

import tma_api
from airtable_schema import FinEventFields as EF
from airtable_schema import Tables
from core.financial_control import bank_import as bi
from core.financial_control import card_import as ci
from core.financial_control import cashflow
from core.financial_control import service
from test_fcc_bank_import import row, statement
from test_fcc_import_api import CREATED, DB, ELI, ELIYAHU, H, PARTNER, aa, client, world  # noqa: F401 — `world` is the autouse fixture


def ev(i, label, amount, day="2026-10-05", category=None, source="import:bank", kind="household_expense", owner=ELI):
    f = {EF.KIND: kind, EF.AMOUNT: amount, EF.OCCURRED_AT: day, EF.SOURCE: source, EF.RAW_TEXT: label, EF.FINANCIAL_OWNER: [owner]}
    if category:
        f[EF.EXPENSE_CATEGORY] = category
    return {"id": f"rec{i:014d}", "fields": f}


@pytest.fixture
def patched(monkeypatch):
    calls = []

    def fake_patch(table_, record_id, fields, source="unknown", **kw):
        for r in DB[table_]:
            if r["id"] == record_id:
                r["fields"].update(fields)
                calls.append((table_, record_id, dict(fields)))
                return True
        return False

    def gateway(action, payload, identity, label):
        out = aa.tma_write(op=payload["op"], table=payload["table"], action=action, requested_by="eliyahu", fields=payload.get("fields"), record_id=payload.get("record_id", ""),
                           audit_action=payload.get("audit_action", ""), audit_details=payload.get("audit_details", ""), identity=identity,
                           trusted_source="tma_api", execution_context={"contract_id": "c1", "approved_by": "eliyahu", "claim_execution_id": "x1"})
        return "appr", ({"ok": True, "status": "executed"} if out.get("ok") else {"error": out.get("user_message")}), (200 if out.get("ok") else 500)
    monkeypatch.setattr("tools.airtable_gateway.airtable_patch", fake_patch)
    monkeypatch.setattr(tma_api, "_queue_or_owner_execute", gateway)
    monkeypatch.setattr("tools.airtable_read_adapter.get_record_fields",
                        lambda table_, rid: next((dict(r["fields"]) for r in DB[table_] if r["id"] == rid), {}))
    return calls


def seed():
    DB[Tables.FIN_EVENTS] = [
        ev(1, "חנות לא ידועה", 100.0), ev(2, "חנות לא ידועה", 40.0, "2026-10-07"), ev(3, "מסעדה", 500.0, "2026-10-06", source="import:card"),
        ev(4, "כבר מסווג", 70.0, category="living"), ev(5, "חשבון של אחר", 999.0, owner="recDana"),
        ev(6, "משכורת", 8000.0, kind="one_time"), ev(7, "אירוע ידני", 20.0, source="fcc_free_text")]


# ── the categories ──────────────────────────────────────────────────────────────────────────────────────────────
def test_the_two_fee_categories_exist_and_the_built_in_rules_use_them():
    labels = dict(cashflow.EXPENSE_CATEGORIES)
    assert labels["card_fees"] == "דמי כרטיס" and labels["fees_interest"] == "עמלות וריביות"
    assert cashflow.category_key("דמי כרטיס") == "card_fees" and cashflow.category_key("עמלות וריביות") == "fees_interest"
    assert not cashflow.is_custom("card_fees") and cashflow.label_of("fees_interest") == "עמלות וריביות"
    bank = bi.classify(bi.parse_statement(statement([row("03/10/2026", "דמי כרטיס חודשי", 10.0, "debit", 90.0), row("02/10/2026", "עמלת פעולה", 5.0, "debit", 100.0),
                                                     row("01/10/2026", "x", 105.0, "credit", 105.0)]), "m").rows)
    assert {c.row.description: c.category for c in bank if c.kind == bi.EXPENSE} == {"דמי כרטיס חודשי": "card_fees", "עמלת פעולה": "fees_interest"}
    assert ci.FEE_CATEGORY == "card_fees"


def test_an_import_record_without_a_category_is_accepted_but_a_bad_one_is_not():
    rec = {"Kind": "household_expense", "Amount": 10.0, "Occurred At": "2026-10-01", "Recorded By": "eliyahu", "Source": "import:bank",
           "Source Ref": "bank:" + "a" * 20, "Idempotency Key": "bank:" + "a" * 20, "Raw Text": "x", "Verification": "statement"}
    assert aa.validate_batch_record(Tables.FIN_EVENTS, rec) is None
    assert aa.validate_batch_record(Tables.FIN_EVENTS, {**rec, "Expense Category": "x" * 41}) == "bad category"
    assert aa.validate_batch_record(Tables.FIN_EVENTS, {**rec, "Kind": "one_time", "Expense Category": "living"}) == "bad category"


# ── the queue ───────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_queue_has_only_the_owners_uncategorized_expenses_imported_or_manual_largest_first(monkeypatch):
    seed()
    waiting = service.classify_waiting(ELIYAHU)
    assert sorted(w["id"] for w in waiting) == [f"rec{i:014d}" for i in (1, 2, 3, 7)]                 # not: another owner's, classified, income
    manual = next(w for w in waiting if w["id"] == f"rec{7:014d}")
    assert manual["source"] == "manual" and manual["label"] == "הוצאה שנרשמה ידנית" and manual["group"] == ""
    view = service.classify_view(waiting)
    assert view["total"] == 4 and view["total_amount"] == 660.0
    assert view["item"]["label"] == "מסעדה" and view["item"]["source"] == "card" and view["item"]["same_count"] == 0
    nxt = service.classify_view(waiting, frozenset({f"rec{3:014d}"}))["item"]
    assert nxt["label"] == "חנות לא ידועה" and nxt["amount"] == 100.0 and nxt["same_count"] == 1
    assert service.classify_view([])["item"] is None


def test_the_cashflow_view_tells_how_many_wait(monkeypatch):
    seed()
    view = service.cashflow_view(ELIYAHU)
    assert view["to_classify"] == {"total": 4, "total_amount": 660.0}


# ── the endpoints ───────────────────────────────────────────────────────────────────────────────────────────────
def test_get_is_owner_only_and_returns_the_next_one_with_the_category_list(monkeypatch):
    seed()
    assert client(monkeypatch, flag=False).get("/api/fcc/classify", headers=H).status_code == 404
    assert client(monkeypatch, who=PARTNER).get("/api/fcc/classify", headers=H).status_code == 404
    body = client(monkeypatch).get("/api/fcc/classify", headers=H).get_json()
    assert body["item"]["label"] == "מסעדה" and body["total"] == 4
    assert {"card_fees", "fees_interest"} <= {c["key"] for c in body["categories"]}
    skipped = client(monkeypatch).get(f"/api/fcc/classify?skip=rec{3:014d}", headers=H).get_json()
    assert skipped["item"]["label"] == "חנות לא ידועה"


def test_post_patches_one_field_of_one_record_through_the_executor(monkeypatch, patched):
    seed()
    r = client(monkeypatch).post("/api/fcc/classify", json={"event_id": f"rec{3:014d}", "category": "fees_interest"}, headers=H)
    body = r.get_json()
    assert r.status_code == 200 and body["state"] == "done" and body["done"] == 1 and body["total"] == 3
    assert patched == [(Tables.FIN_EVENTS, f"rec{3:014d}", {EF.EXPENSE_CATEGORY: "fees_interest"})]            # one record, one field, the server's choice
    assert body["item"]["label"] == "חנות לא ידועה"


def test_apply_same_covers_the_other_rows_with_the_same_description_only(monkeypatch, patched):
    seed()
    body = client(monkeypatch).post("/api/fcc/classify", json={"event_id": f"rec{1:014d}", "category": "קייטרינג חדש", "apply_same": True}, headers=H).get_json()
    assert body["done"] == 2 and body["total"] == 2 and body["same_left"] == 0
    assert sorted(c[1] for c in patched) == [f"rec{1:014d}", f"rec{2:014d}"] and all(c[2] == {EF.EXPENSE_CATEGORY: "קייטרינג חדש"} for c in patched)
    assert [r for r in DB[Tables.FIN_EVENTS] if r["id"] == f"rec{3:014d}"][0]["fields"].get(EF.EXPENSE_CATEGORY) is None      # a different description: untouched


def test_post_refuses_other_peoples_classified_non_import_or_income_rows_and_bad_input(monkeypatch, patched):
    seed()
    c = client(monkeypatch)
    for rid in (5, 4, 6, 99):                         # another owner's, already classified, income, missing: all answered alike
        assert c.post("/api/fcc/classify", json={"event_id": f"rec{rid:014d}", "category": "living"}, headers=H).status_code == 404
    assert c.post("/api/fcc/classify", json={"event_id": f"rec{1:014d}", "category": ""}, headers=H).status_code == 400
    assert c.post("/api/fcc/classify", json={"event_id": f"rec{1:014d}", "category": "uncategorized"}, headers=H).status_code == 400
    assert c.post("/api/fcc/classify", json={"event_id": "nope", "category": "living"}, headers=H).status_code == 400
    assert client(monkeypatch, who=PARTNER).post("/api/fcc/classify", json={"event_id": f"rec{1:014d}", "category": "living"}, headers=H).status_code == 404
    assert patched == []


def test_a_failing_write_is_reported_and_nothing_is_marked_done(monkeypatch, patched):
    seed()
    monkeypatch.setattr(tma_api, "_queue_or_owner_execute", lambda *a, **k: ("a", {"error": "x"}, 500))
    r = client(monkeypatch).post("/api/fcc/classify", json={"event_id": f"rec{1:014d}", "category": "living", "apply_same": True}, headers=H)
    assert r.status_code == 500 and r.get_json()["state"] == "partial_failure" and r.get_json()["done"] == 0


def test_a_manually_recorded_expense_without_a_category_can_be_classified_and_is_never_grouped(monkeypatch, patched):
    seed()
    DB[Tables.FIN_EVENTS].append(ev(8, "intent:monthly.household_expense#ab12", 30.0, source="fcc_free_text"))
    body = client(monkeypatch).post("/api/fcc/classify", json={"event_id": f"rec{7:014d}", "category": "home", "apply_same": True}, headers=H).get_json()
    assert body["done"] == 1                                                                           # the other manual row has no description: not "the same"
    assert patched == [(Tables.FIN_EVENTS, f"rec{7:014d}", {EF.EXPENSE_CATEGORY: "home"})]


def test_the_first_import_s_singular_label_is_the_built_in_fees_category():
    assert cashflow.category_key("עמלות וריבית") == "fees_interest" and not cashflow.is_custom(cashflow.category_key("עמלות וריבית"))


# ── the answer outlives the statement: classifying an imported expense leaves a RULE behind ─────────────────────────
from airtable_schema import CashflowRuleFields as CR  # noqa: E402
from test_fcc_import_api import CREATED as CREATED_ROWS  # noqa: E402


def rules_created():
    return [r["fields"] for t, r in CREATED_ROWS if t == Tables.CASHFLOW_RULES]


def test_classifying_creates_a_decided_rule_and_the_next_statement_is_classified_by_it(monkeypatch, patched):
    DB[Tables.FIN_EVENTS] = [ev(1, "יש חסד אלעד", 100.0, source="import:card"), ev(2, "יש חסד אלעד", 40.0, "2026-10-07", source="import:card")]
    body = client(monkeypatch).post("/api/fcc/classify", json={"event_id": f"rec{1:014d}", "category": "living", "apply_same": True}, headers=H).get_json()
    assert body["done"] == 2 and body["rule_saved"] is True
    made = rules_created()
    assert len(made) == 1 and made[0][CR.MATCH] == "יש חסד אלעד" and made[0][CR.APPLIES_TO] == "card" and made[0][CR.DIRECTION] == "debit"
    assert (made[0][CR.KIND], made[0][CR.CATEGORY], made[0][CR.STATUS]) == ("expense", "living", "active") and made[0][CR.FINANCIAL_OWNER] == [ELI]
    # the NEXT month's statement: the same merchant is decided by the rule, never asked again
    rules = bi.owner_rules_from(service.cashflow_rule_items(service.my_cashflow_rules(ELIYAHU), "card"))
    charge = ci.CardCharge(__import__("datetime").date(2026, 11, 3), "יש חסד אלעד", 77.0, 77.0, "7716", __import__("datetime").date(2026, 11, 15), 1, ci.REGULAR, "", "")
    c = ci.classify_charge(charge, rules)
    assert c.kind == ci.EXPENSE and c.category == "living" and ci.importable(c)


def test_a_pending_rule_for_the_same_description_is_activated_not_duplicated(monkeypatch, patched):
    DB[Tables.FIN_EVENTS] = [ev(1, "פיצה אליה", 36.0, source="import:card")]
    DB[Tables.CASHFLOW_RULES].append({"id": "recP1", "fields": {CR.MATCH: "פיצה אליה", CR.APPLIES_TO: "card", CR.DIRECTION: "debit", CR.STATUS: "pending",
                                                              CR.TIMES_SEEN: 2, CR.EXAMPLE_AMOUNT: 36.0, CR.FINANCIAL_OWNER: [ELI]}})
    client(monkeypatch).post("/api/fcc/classify", json={"event_id": f"rec{1:014d}", "category": "leisure"}, headers=H)
    assert rules_created() == [] and ("Cashflow Rules", "recP1", {CR.KIND: "expense", CR.CATEGORY: "leisure", CR.STATUS: "active"}) in patched


def test_changing_your_mind_updates_the_decided_rule_and_the_same_answer_writes_nothing_more(monkeypatch, patched):
    DB[Tables.FIN_EVENTS] = [ev(1, "בזק", 199.0, source="import:card"), ev(2, "ויקטורי", 90.0, source="import:card")]
    DB[Tables.CASHFLOW_RULES].append({"id": "recD1", "fields": {CR.MATCH: "בזק", CR.APPLIES_TO: "card", CR.DIRECTION: "debit", CR.KIND: "expense", CR.CATEGORY: "home",
                                                              CR.STATUS: "active", CR.FINANCIAL_OWNER: [ELI]}})
    DB[Tables.CASHFLOW_RULES].append({"id": "recD2", "fields": {CR.MATCH: "ויקטורי", CR.APPLIES_TO: "card", CR.DIRECTION: "debit", CR.KIND: "expense", CR.CATEGORY: "living",
                                                              CR.STATUS: "active", CR.FINANCIAL_OWNER: [ELI]}})
    c = client(monkeypatch)
    c.post("/api/fcc/classify", json={"event_id": f"rec{1:014d}", "category": "communication"}, headers=H)       # a different category: the rule follows
    c.post("/api/fcc/classify", json={"event_id": f"rec{2:014d}", "category": "living"}, headers=H)             # the same category: no second write to the rule
    rule_patches = [p for p in patched if p[0] == "Cashflow Rules"]
    assert rule_patches == [("Cashflow Rules", "recD1", {CR.KIND: "expense", CR.CATEGORY: "communication", CR.STATUS: "active"})] and rules_created() == []


def test_a_manual_expense_leaves_no_rule_and_a_failing_rule_write_is_reported(monkeypatch, patched):
    DB[Tables.FIN_EVENTS] = [ev(1, "intent:monthly.household_expense#x", 20.0, source="fcc_free_text"), ev(2, "חנות", 50.0, source="import:bank")]
    c = client(monkeypatch)
    assert c.post("/api/fcc/classify", json={"event_id": f"rec{1:014d}", "category": "home"}, headers=H).status_code == 200 and rules_created() == []
    real = tma_api._queue_or_owner_execute

    def flaky(action, payload, identity, label):
        return ("a", {"error": "x"}, 500) if payload["table"] == "Cashflow Rules" else real(action, payload, identity, label)
    monkeypatch.setattr(tma_api, "_queue_or_owner_execute", flaky)
    r = c.post("/api/fcc/classify", json={"event_id": f"rec{2:014d}", "category": "home"}, headers=H)
    assert r.status_code == 500 and r.get_json()["state"] == "partial_failure" and r.get_json()["done"] == 1


def test_the_new_rule_validator_and_the_gateway_accept_only_that_shape(monkeypatch):
    good = {"Match": "יש חסד", "Applies To": "card", "Direction": "debit", "Kind": "expense", "Category": "living", "Status": "active"}
    assert aa.validate_rule_post(good) is None
    for bad in (None, {}, {**good, "Kind": "income"}, {**good, "Status": "pending"}, {**good, "Direction": "credit"}, {**good, "Applies To": "any"}, {**good, "Match": ""},
                {**good, "Category": ""}, {**good, "Row Key": "bank:" + "a" * 20}, {k: v for k, v in good.items() if k != "Match"}):
        assert aa.validate_rule_post(bad) is not None
    assert aa._rules_write_refused("post", good) is False and aa._rules_write_refused("post", {**good, "Kind": "income"}) is True and aa._rules_write_refused("delete", good) is True
