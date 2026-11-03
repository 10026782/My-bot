"""FCC statement import — the batch executor (``tma_write op=post_many``), the allow-list, and ``POST /api/fcc/import/{preview,run}``.

The PDF / Excel reading is replaced by the pure parsers over synthetic statements; the ActionGateway ceremony is replaced by a fake that runs the REAL
executor (so validation, the owner policy, idempotency and the chunk behaviour are the real code). No network, no real statements.
"""

from __future__ import annotations

import os

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-imp-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:IMP_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patImpTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appImpTest")
os.environ.setdefault("ELIYAHU_CHAT_ID", "1")

import io

import pytest
from flask import Flask

import identity as identity_module
import tma_api
from airtable_schema import CashflowRuleFields as CR
from airtable_schema import FinEventFields as EF
from airtable_schema import Tables
from core import data_access_policy as policy
from core import owner_resolution
from core.financial_control import bank_import as bi
from core.financial_control import card_import as ci
from core.financial_control import import_plan as ip
from core.financial_control import service
from core.financial_control import statement_reader as sr
from identity import Domain, Identity, Role
from test_fcc_bank_import import row, statement
from test_fcc_card_import import table
from tools import approval_actions as aa

ELI, DANA = "recEli", "recDana"
PROFILES = [{"id": ELI, "fields": {"name": "Eliyahu"}}, {"id": DANA, "fields": {"name": "Dana"}}]
H = {"X-Telegram-Init-Data": "valid"}


def ident(uid, role):
    return Identity(user_id=uid, role=role, display_name=uid, tenant_id="boss_hq", domain_id=Domain.GENERAL,
                    allowed_domains=[], channel="telegram", external_id=f"tg-{uid}")


ELIYAHU, PARTNER = ident("eliyahu", Role.OWNER), ident("avi", Role.PARTNER)
NEWEST_FIRST = [
    row("09/10/2026", "הפק מזומן-בנקט", 200.0, "credit", 15600.0),
    row("08/10/2026", "חנות לא ידועה", 100.0, "debit", 15400.0),
    row("07/10/2026", "העברה-נייד", 700.0, "credit", 15500.0),
    row("06/10/2026", 'מכס ומע"מ', 300.0, "credit", 14800.0),
    row("05/10/2026", "עיריית מודיעין", 500.0, "debit", 14500.0),
    row("04/10/2026", "החזר חיוב-טכני", 1200.0, "credit", 15000.0),
    row("03/10/2026", "מרכז התורה", 1200.0, "debit", 13800.0),
    row("02/10/2026", 'ישראכרט בע"מ', 3000.0, "debit", 15000.0),
    row("01/10/2026", 'מלם מערכות בע"', 8000.0, "credit", 18000.0),
]
DB: dict = {}
CREATED: list = []


@pytest.fixture(autouse=True)
def world(monkeypatch):
    DB.clear()
    CREATED.clear()
    DB[Tables.FIN_EVENTS] = []
    DB[Tables.CASHFLOW_RULES] = [{"id": "recR1", "fields": {CR.MATCH: "מלם מערכות", CR.KIND: "income", CR.CATEGORY: "עבודת אשתי", CR.DIRECTION: "credit",
                                                           CR.APPLIES_TO: "bank", CR.STATUS: "active", CR.FINANCIAL_OWNER: [ELI]}}]

    def fake_profile(table_, query, **kw):
        _f, value, _s, _ci = query.arguments
        return [p for p in PROFILES if p["fields"]["name"].casefold() == str(value).casefold()]
    monkeypatch.setattr(owner_resolution, "list_records", fake_profile)
    monkeypatch.setattr(identity_module, "_REGISTRY", {"telegram:1": {"tenant": "boss_hq", "user": "eliyahu", "role": "owner"}})
    monkeypatch.setattr(service, "_read", lambda table_, formula="": list(DB.get(table_, [])))

    # the real batch executor with a fake provider (Airtable) and a fake claim check
    def fake_create(table_, fields, source="unknown", **kw):
        if table_ in (Tables.FIN_EVENTS, Tables.CASHFLOW_RULES):
            rec = {"id": f"rec{len(CREATED):014d}", "fields": dict(fields)}
            DB[table_].append(rec)
            CREATED.append((table_, rec))
            return rec
        return {"id": "recLog"}
    monkeypatch.setattr("tools.airtable_gateway.airtable_create", fake_create)
    monkeypatch.setattr(aa, "_verify_active_execution_claim", lambda *a, **k: True)
    monkeypatch.setattr("tools.airtable_read_adapter.list_records", lambda table_, formula="", **kw: list(DB.get(table_, [])))

    executed = []

    def fake_gateway(action, payload, identity, label):
        executed.append(payload)
        out = aa.tma_write(op=payload["op"], table=payload["table"], action=action, requested_by="eliyahu", records=payload.get("records"),
                           audit_action=payload.get("audit_action", ""), audit_details=payload.get("audit_details", ""), identity=identity,
                           trusted_source="tma_api", execution_context={"contract_id": "c1", "approved_by": "eliyahu", "claim_execution_id": "x1"})
        return "appr", ({"ok": True, "status": "executed"} if out.get("ok") else {"error": out.get("user_message")}), (200 if out.get("ok") else 500)
    monkeypatch.setattr(tma_api, "_queue_or_owner_execute", fake_gateway)
    monkeypatch.setattr(tma_api, "_FCC_IMPORT_CHUNK", 2)
    world.executed = executed


def client(monkeypatch, who=ELIYAHU, flag=True, bank=None, card=None):
    app = Flask(__name__)
    app.register_blueprint(tma_api.tma_api)
    monkeypatch.setattr(tma_api, "_validate_initdata", lambda _: {"id": who.user_id})
    monkeypatch.setattr(tma_api, "resolve_identity", lambda *_: who)
    monkeypatch.setattr(tma_api, "_fcc_enabled", lambda identity=None: flag)
    monkeypatch.setattr(sr, "read_bank", lambda data, ref: bank or bi.parse_statement(statement(NEWEST_FIRST), ref))
    monkeypatch.setattr(sr, "read_card", lambda data, ref: card or ci.parse_card_table(table(), ref))
    return app.test_client()


def post(c, path, kind="bank", digest=None, label="main"):
    data = {"kind": kind, "label": label, "file": (io.BytesIO(b"%PDF-fake"), "s.pdf")}
    if digest is not None:
        data["digest"] = digest
    return c.post(path, data=data, headers=H, content_type="multipart/form-data")


def run_all(c, kind, digest, limit=20):
    calls = []
    for _ in range(limit):
        r = post(c, "/api/fcc/import/run", kind, digest)
        assert r.status_code == 200, r.get_json()
        body = r.get_json()
        calls.append(body)
        if body["state"] == "done":
            return calls
    raise AssertionError("did not converge")


# ── the preview ─────────────────────────────────────────────────────────────────────────────────────────────────
def test_preview_shows_the_plan_and_writes_nothing(monkeypatch):
    r = post(client(monkeypatch), "/api/fcc/import/preview")
    body = r.get_json()
    assert r.status_code == 200 and body["parse"]["ok"] and body["can_import"] and body["digest"]
    plan = body["plan"]
    assert plan["events"] == 4 and plan["remaining"] == 4 and plan["already_imported"] == 0                       # the income, the tax, the VAT refund, an unknown debit
    assert plan["months"]["2026-10"] == {"expenses": 300.0, "income": 8000.0, "events": 4, "by_category": {"taxes": 200.0, "uncategorized": 100.0}, "by_source": {"עבודת אשתי": 8000.0}}
    assert plan["uncategorized"] == {"count": 1, "total": 100.0}
    assert plan["skipped"]["card_settlement"]["count"] == 1 and plan["pending_rules"] == 2 and plan["pending_row_rules"] == 1
    assert {e["match"] for e in plan["pending_examples"]} >= {"הפק מזומן-בנקט"}
    assert CREATED == [] and world.executed == []


def test_gate_validation_and_a_statement_that_does_not_add_up(monkeypatch):
    assert post(client(monkeypatch, flag=False), "/api/fcc/import/preview").status_code == 404
    assert post(client(monkeypatch, who=PARTNER), "/api/fcc/import/preview").status_code == 404
    assert post(client(monkeypatch), "/api/fcc/import/preview", kind="loan").status_code == 400
    assert client(monkeypatch).post("/api/fcc/import/preview", data={"kind": "bank"}, headers=H, content_type="multipart/form-data").status_code == 400
    broken = bi.parse_statement(statement([NEWEST_FIRST[0], NEWEST_FIRST[2]]), "main")
    c = client(monkeypatch, bank=broken)
    body = post(c, "/api/fcc/import/preview").get_json()
    assert body["parse"]["ok"] is False and body["digest"] is None and body["can_import"] is False and body["parse"]["problems"]
    assert post(c, "/api/fcc/import/run", digest="anything").status_code == 409 and CREATED == []


def test_an_unreadable_file_is_a_clean_400(monkeypatch):
    c = client(monkeypatch)

    def boom(data, ref):
        raise sr.StatementError("ה-PDF אינו מכיל טקסט (סרוק?)")
    monkeypatch.setattr(sr, "read_bank", boom)
    r = post(c, "/api/fcc/import/preview")
    assert r.status_code == 400 and "סרוק" in r.get_json()["error"]


# ── the run ─────────────────────────────────────────────────────────────────────────────────────────────────────
def test_run_needs_the_digest_the_owner_reviewed(monkeypatch):
    c = client(monkeypatch)
    assert post(c, "/api/fcc/import/run").status_code == 409
    assert post(c, "/api/fcc/import/run", digest="not-the-digest").status_code == 409
    assert CREATED == []


def test_the_whole_plan_is_written_in_chunks_then_the_pending_rules_and_nothing_twice(monkeypatch):
    c = client(monkeypatch)
    digest = post(c, "/api/fcc/import/preview").get_json()["digest"]
    calls = run_all(c, "bank", digest)
    assert [(x["step"], x["written"]) for x in calls] == [("events", 2), ("events", 2), ("rules", 2), ("done", 0)]
    events = [r for t, r in CREATED if t == Tables.FIN_EVENTS]
    rules = [r for t, r in CREATED if t == Tables.CASHFLOW_RULES]
    assert len(events) == 4 and len(rules) == 2
    by = {e["fields"][EF.AMOUNT]: e["fields"] for e in events}
    assert set(by) == {8000.0, 500.0, -300.0, 100.0} and EF.EXPENSE_CATEGORY not in by[100.0] and EF.GOAL not in by[8000.0] and by[8000.0][EF.NOTE] == "מקור: עבודת אשתי" and by[-300.0][EF.EXPENSE_CATEGORY] == "taxes"
    assert all(e["fields"][EF.SOURCE] == "import:bank" and e["fields"][EF.FINANCIAL_OWNER] == [ELI] for e in events)        # the owner is stamped by the policy
    assert all(r["fields"][CR.STATUS] == "pending" and CR.KIND not in r["fields"] and r["fields"][CR.FINANCIAL_OWNER] == [ELI] for r in rules)
    # a second import of the same statement: nothing to write, the digest is unchanged, no pending rule is asked twice
    again = post(c, "/api/fcc/import/preview").get_json()
    assert again["plan"]["remaining"] == 0 and again["plan"]["already_imported"] == 4 and again["plan"]["pending_rules"] == 0 and again["digest"] == digest
    assert post(c, "/api/fcc/import/run", digest=digest).get_json()["state"] == "done" and len(CREATED) == 6


def test_the_run_stops_when_the_rules_or_the_file_change_after_the_review(monkeypatch):
    c = client(monkeypatch)
    digest = post(c, "/api/fcc/import/preview").get_json()["digest"]
    assert post(c, "/api/fcc/import/run", digest=digest).status_code == 200
    DB[Tables.CASHFLOW_RULES].append({"id": "recR2", "fields": {CR.MATCH: "הפק מזומן-בנקט", CR.KIND: "income", CR.CATEGORY: "הכנסה אחרת", CR.DIRECTION: "credit", CR.STATUS: "active", CR.FINANCIAL_OWNER: [ELI]}})
    stale = post(c, "/api/fcc/import/run", digest=digest)
    assert stale.status_code == 409 and "review again" in stale.get_json()["error"]


def test_a_failing_chunk_is_reported_and_the_retry_continues_without_duplicates(monkeypatch):
    c = client(monkeypatch)
    digest = post(c, "/api/fcc/import/preview").get_json()["digest"]
    real = tma_api._queue_or_owner_execute
    state = {"fail": True}

    def flaky(action, payload, identity, label):
        if state["fail"] and payload["table"] == Tables.FIN_EVENTS:
            state["fail"] = False
            monkeypatch.setattr("tools.airtable_gateway.airtable_create", _fail_after_one())
        return real(action, payload, identity, label)
    monkeypatch.setattr(tma_api, "_queue_or_owner_execute", flaky)
    r = post(c, "/api/fcc/import/run", digest=digest)
    assert r.status_code == 500 and r.get_json()["state"] == "blocked"
    monkeypatch.setattr("tools.airtable_gateway.airtable_create", _restore_create())
    calls = run_all(c, "bank", digest)
    assert calls[-1]["state"] == "done"
    keys = [e["fields"][EF.IDEMPOTENCY_KEY] for t, e in CREATED if t == Tables.FIN_EVENTS]
    assert len(keys) == 4 and len(set(keys)) == 4                                                                    # one row per statement row, whatever failed


def _fail_after_one():
    n = {"i": 0}

    def create(table_, fields, source="unknown", **kw):
        if table_ == Tables.FIN_EVENTS:
            n["i"] += 1
            if n["i"] > 1:
                return None
        rec = {"id": f"rec{len(CREATED):014d}", "fields": dict(fields)}
        DB.setdefault(table_, []).append(rec)
        CREATED.append((table_, rec))
        return rec
    return create


def _restore_create():
    def create(table_, fields, source="unknown", **kw):
        if table_ in (Tables.FIN_EVENTS, Tables.CASHFLOW_RULES):
            rec = {"id": f"rec{len(CREATED):014d}", "fields": dict(fields)}
            DB[table_].append(rec)
            CREATED.append((table_, rec))
            return rec
        return {"id": "recLog"}
    return create


def test_a_card_statement_is_imported_with_the_billing_date_and_never_the_cash_or_rolling_credit(monkeypatch):
    c = client(monkeypatch)
    pre = post(c, "/api/fcc/import/preview", kind="card").get_json()
    assert pre["parse"]["ok"] and pre["plan"]["events"] == 3 and pre["plan"]["skipped"]["loan"]["count"] == 2 and pre["plan"]["uncategorized"]["count"] == 1 and pre["plan"]["skipped"]["cash_withdrawal"]["count"] == 1 and pre["plan"]["skipped"]["credit_service"]["count"] == 2
    run_all(c, "card", pre["digest"])
    events = [r["fields"] for t, r in CREATED if t == Tables.FIN_EVENTS]
    assert {f[EF.SOURCE] for f in events} == {"import:card"} and {f[EF.OCCURRED_AT] for f in events} >= {"2026-09-27"}
    assert not any(f.get(EF.EXPENSE_CATEGORY) == "loans" for f in events)                    # loans are never imported (the loans tab is exact)


# ── the executor and its allow-list ─────────────────────────────────────────────────────────────────────────────
def good_event(i=0, **over):
    key = f"bank:{i:020x}"
    f = {"Kind": "household_expense", "Amount": 10.0, "Occurred At": "2026-10-01", "Recorded By": "eliyahu", "Source": "import:bank", "Source Ref": key,
         "Idempotency Key": key, "Raw Text": "x", "Verification": "statement", "Expense Category": "living"}
    f.update(over)
    return f


@pytest.mark.parametrize("over,reason", [
    ({"Goal": ["recG"]}, "field not allowed"), ({"Account": ["recA"]}, "field not allowed"), ({"Kind": "target_change"}, "kind"), ({"Source": "fcc_free_text"}, "kind"),
    ({"Idempotency Key": "x"}, "key"), ({"Source Ref": "bank:" + "0" * 20, "Idempotency Key": "bank:" + "1" * 20}, "key"), ({"Amount": 0}, "amount"),
    ({"Amount": 1e9}, "amount"), ({"Amount": True}, "amount"), ({"Occurred At": "01/10/2026"}, "date"), ({"Verification": "self_reported"}, "verification"),
    ({"Expense Category": ""}, "category"), ({"Note": "מקור: x"}, "note"), ({"Raw Text": "x" * 300}, "Raw Text"),
])
def test_the_executor_refuses_any_event_outside_the_import_shape(over, reason):
    assert reason in (aa.validate_batch_record(Tables.FIN_EVENTS, good_event(**over)) or "")


def test_the_executor_accepts_the_planned_shapes_and_refuses_other_tables_and_shapes():
    assert aa.validate_batch_record(Tables.FIN_EVENTS, good_event()) is None
    income = {k: v for k, v in good_event(Kind="one_time", Note="מקור: עבודה").items() if k != "Expense Category"}
    assert aa.validate_batch_record(Tables.FIN_EVENTS, income) is None and aa.validate_batch_record(Tables.FIN_EVENTS, {**income, "Amount": -5.0}) == "income must be positive"
    assert "not allowed for a batch" in aa.validate_batch_record("Leads", {"x": 1}) and aa.validate_batch_record(Tables.FIN_EVENTS, "x") == "record is not an object"
    rule = {"Match": "חנות", "Applies To": "bank", "Direction": "debit", "Status": "pending", "Times Seen": 2, "Last Seen": "2026-10-01", "Example Amount": 5.0}
    assert aa.validate_batch_record(Tables.CASHFLOW_RULES, rule) is None
    for bad in ({**rule, "Kind": "expense"}, {**rule, "Status": "active"}, {**rule, "Category": "x"}, {**rule, "Match": "", "Row Key": None}, {**rule, "Applies To": "any"}):
        assert aa.validate_batch_record(Tables.CASHFLOW_RULES, bad)


def call_batch(table_, records, identity=ELIYAHU, **kw):
    return aa.tma_write(op="post_many", table=table_, action="tma_fcc_import", requested_by="eliyahu", records=records, identity=identity,
                        trusted_source="tma_api", execution_context=kw.get("ctx", {"contract_id": "c", "approved_by": "eliyahu", "claim_execution_id": "x"}))


def test_a_batch_runs_only_behind_a_live_claim_and_within_its_size_and_validation_limits(monkeypatch):
    monkeypatch.setattr(aa, "_verify_active_execution_claim", lambda *a, **k: False)
    assert call_batch(Tables.FIN_EVENTS, [good_event()])["ok"] is False and CREATED == []
    monkeypatch.setattr(aa, "_verify_active_execution_claim", lambda *a, **k: True)
    assert call_batch(Tables.FIN_EVENTS, [])["ok"] is False
    assert call_batch(Tables.FIN_EVENTS, [good_event(i) for i in range(aa.BATCH_MAX + 1)])["ok"] is False
    assert call_batch(Tables.FIN_EVENTS, [good_event(1), good_event(2, Kind="note")])["ok"] is False and CREATED == []      # ONE bad record: nothing is written


def test_a_batch_skips_what_the_owner_already_has_and_writes_the_rest():
    DB[Tables.FIN_EVENTS].append({"id": "recOld", "fields": {EF.IDEMPOTENCY_KEY: good_event(1)["Idempotency Key"], EF.FINANCIAL_OWNER: [ELI]}})
    out = call_batch(Tables.FIN_EVENTS, [good_event(1), good_event(2)])
    assert out["ok"] and out["evidence"]["created"] == 1 and out["evidence"]["skipped_existing"] == 1 and len(CREATED) == 1
    # someone else's row with the same key does not count as "already imported" for this owner
    DB[Tables.FIN_EVENTS].append({"id": "recDanas", "fields": {EF.IDEMPOTENCY_KEY: good_event(3)["Idempotency Key"], EF.FINANCIAL_OWNER: [DANA]}})
    assert call_batch(Tables.FIN_EVENTS, [good_event(3)])["evidence"]["created"] == 1


def test_a_batch_cannot_be_proposed_by_a_non_owner_or_for_other_tables_or_with_bad_records(monkeypatch):
    import core.database as db
    import feature_flags
    from core.action_gateway import action_gateway as gw
    monkeypatch.setattr(feature_flags, "is_enabled", lambda name, *a, **k: name in ("FEATURE_ACTION_CONTRACT_PERSISTENCE", "FEATURE_ATOMIC_CLAIMS"))
    monkeypatch.setattr(gw, "_ledger", type("L", (), {"_repository": object()})())
    monkeypatch.setattr(db, "get_pool", lambda: object())
    app = Flask(__name__)
    with app.test_request_context("/"):
        for who, table_, recs in ((PARTNER, Tables.FIN_EVENTS, [good_event()]), (ELIYAHU, "Leads", [good_event()]), (ELIYAHU, Tables.FIN_EVENTS, [good_event(Kind="note")]),
                                  (ELIYAHU, Tables.FIN_EVENTS, []), (ELIYAHU, Tables.FIN_EVENTS, [good_event(i) for i in range(aa.BATCH_MAX + 1)])):
            _, resp, status = tma_api._queue_tma_write_approval("tma_fcc_import", {"op": "post_many", "table": table_, "records": recs}, who, "x")
            assert status == 400 and resp["error"] == "batch write refused", (who.role, table_)


# ── billing date + instalments label (cashflow counts by billing, consumption by purchase) ───────────────────────────────────────────────
def card_event(i=0, **over):
    key = f"card:{i:020x}"
    f = {"Kind": "household_expense", "Amount": 10.0, "Occurred At": "2026-10-01", "Recorded By": "eliyahu", "Source": "import:card", "Source Ref": key,
         "Idempotency Key": key, "Raw Text": "x", "Verification": "statement", "Expense Category": "living", "Billing Date": "2026-10-10"}
    f.update(over)
    return f


@pytest.mark.parametrize("over,ok", [
    ({}, True), ({"Note": "תשלומים"}, True), ({"Note": "אחר"}, False), ({"Billing Date": "10/10/2026"}, False), ({"Billing Date": "2026-13-40"}, False),
    ({"Source": "import:bank", "Source Ref": "bank:" + "0" * 20, "Idempotency Key": "bank:" + "0" * 20}, False),          # a bank row has no billing date
])
def test_the_billing_date_is_for_card_rows_and_the_note_is_only_the_instalments_label(over, ok):
    assert (aa.validate_batch_record(Tables.FIN_EVENTS, card_event(**over)) is None) is ok


def test_a_re_imported_row_fills_the_billing_date_and_the_label_it_lacked_and_never_overwrites(monkeypatch):
    patched = []
    monkeypatch.setattr("tools.airtable_gateway.airtable_create", lambda t, f, source="x", **kw: {"id": "recLog"})
    monkeypatch.setattr("tools.airtable_gateway.airtable_patch", lambda t, rid, f, source="x", **kw: patched.append((rid, dict(f))) or True)
    monkeypatch.setattr(aa, "_verify_active_execution_claim", lambda *a, **k: True)
    monkeypatch.setattr("tools.airtable_read_adapter.list_records", lambda table_, formula="", **kw: list(DB.get(table_, [])))
    old = card_event(1)["Idempotency Key"]
    kept = card_event(2)["Idempotency Key"]
    DB[Tables.FIN_EVENTS].extend([
        {"id": "recOld", "fields": {EF.IDEMPOTENCY_KEY: old, EF.FINANCIAL_OWNER: [ELI]}},                                            # imported before the field existed
        {"id": "recKept", "fields": {EF.IDEMPOTENCY_KEY: kept, EF.FINANCIAL_OWNER: [ELI], EF.BILLING_DATE: "2026-09-10", EF.NOTE: "תשלומים"}},   # already filled
    ])
    out = call_batch(Tables.FIN_EVENTS, [card_event(1, Note="תשלומים"), card_event(2, **{"Billing Date": "2026-10-10"})])
    assert out["ok"] and out["evidence"]["created"] == 0 and out["evidence"]["skipped_existing"] == 2 and out["evidence"]["backfilled"] == 1
    assert patched == [("recOld", {"Billing Date": "2026-10-10", "Note": "תשלומים"})]


def test_an_earlier_card_import_is_filled_with_the_billing_dates_by_importing_the_same_statement_again(monkeypatch):
    c = client(monkeypatch)
    pre = post(c, "/api/fcc/import/preview", kind="card").get_json()
    run_all(c, "card", pre["digest"])
    rows = [r for t, r in CREATED if t == Tables.FIN_EVENTS]
    assert rows and all(EF.BILLING_DATE in r["fields"] for r in rows)
    for r in rows:                                                                  # simulate an import from before the field existed
        r["fields"].pop(EF.BILLING_DATE)
        r["fields"].pop(EF.NOTE, None)
    again = post(c, "/api/fcc/import/preview", kind="card").get_json()
    assert again["plan"]["remaining"] == 0 and again["plan"]["backfill"] == len(rows) and again["can_import"]
    patched = []

    def fake_patch(table_, rid, fields, source="x", **kw):
        patched.append(rid)
        next(r for r in DB[table_] if r["id"] == rid)["fields"].update(fields)
        return True
    monkeypatch.setattr("tools.airtable_gateway.airtable_patch", fake_patch)
    calls = run_all(c, "card", again["digest"])
    assert any(b.get("step") == "billing" for b in calls) and len(patched) == len(rows)
    assert all(EF.BILLING_DATE in r["fields"] for r in rows)
    assert post(c, "/api/fcc/import/preview", kind="card").get_json()["plan"]["backfill"] == 0                # filled once, nothing left
