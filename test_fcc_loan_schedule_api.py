"""POST /api/fcc/loans/schedule — preview names the loan(s) a schedule fits (writes nothing); confirm writes ONE patch on the chosen loan. Owner only."""
from __future__ import annotations

import io
import os

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-ls-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:LS_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patLsTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appLsTest")
os.environ.setdefault("ELIYAHU_CHAT_ID", "1")

import pytest
from flask import Flask

import tma_api
from core.financial_control import amortization as am, service
from identity import Domain, Identity, Role
from test_fcc_amortization import CHARGED, UPCOMING

H = {"X-Telegram-Init-Data": "valid"}


def ident(uid, role):
    return Identity(user_id=uid, role=role, display_name=uid, tenant_id="boss_hq", domain_id=Domain.GENERAL, allowed_domains=[], channel="telegram", external_id=f"tg-{uid}")


LOANS = [{"id": "recA", "fields": {"Loan Name/ID": "מקס", "Loan Amount": 1000, "Current Monthly Payment": 410, "Active Loan": True}},
         {"id": "recB", "fields": {"Loan Name/ID": "אחרת", "Loan Amount": 9000, "Current Monthly Payment": 50, "Active Loan": True}}]
WRITES: list = []


@pytest.fixture
def api(monkeypatch):
    WRITES.clear()
    app = Flask(__name__)
    app.register_blueprint(tma_api.tma_api)
    who = ident("eliyahu", Role.OWNER)
    monkeypatch.setattr(tma_api, "_validate_initdata", lambda _: {"id": who.user_id})
    monkeypatch.setattr(tma_api, "resolve_identity", lambda *_: who)
    monkeypatch.setattr(tma_api, "_fcc_enabled", lambda identity=None: True)
    monkeypatch.setattr(service, "my_loans", lambda identity: LOANS)
    monkeypatch.setattr(am, "parse_file", lambda data: am.parse_sheets([CHARGED, UPCOMING]))
    monkeypatch.setattr(tma_api, "_queue_or_owner_execute", lambda action, payload, identity, label: (WRITES.append(payload) or ("a", {"ok": True}, 200)))
    return app, who


def send(app, **form):
    return app.test_client().post("/api/fcc/loans/schedule", data={"file": (io.BytesIO(b"x"), "s.xlsx"), **form}, headers=H, content_type="multipart/form-data")


def test_preview_names_the_matching_loan_and_writes_nothing(api):
    r = send(api[0]).get_json()
    assert r["state"] == "preview" and [c["id"] for c in r["candidates"]] == ["recA"] and r["payments_left"] == 2 and not WRITES


def test_confirm_writes_one_patch_on_the_chosen_loan_only(api):
    digest = send(api[0]).get_json()["digest"]
    assert send(api[0], confirm="1", loan_id="recB", digest=digest).status_code == 400          # not a loan this schedule fits
    assert send(api[0], confirm="1", loan_id="recA", digest="bad").status_code == 409
    out = send(api[0], confirm="1", loan_id="recA", digest=digest).get_json()
    assert out["state"] == "saved" and len(WRITES) == 1
    w = WRITES[0]
    assert w["op"] == "patch" and w["table"] == "Loans" and w["record_id"] == "recA" and list(w["fields"]) == ["Amortization Schedule"]
    assert am.loads(w["fields"]["Amortization Schedule"]) is not None


def test_a_bad_file_is_rejected_and_non_owner_gets_404(api, monkeypatch):
    monkeypatch.setattr(am, "parse_file", lambda data: am.parse_sheets([[("x",)]]))
    assert send(api[0]).get_json()["state"] == "rejected" and not WRITES
    monkeypatch.setattr(tma_api, "resolve_identity", lambda *_: ident("avi", Role.PARTNER))
    assert send(api[0]).status_code == 404


def test_the_same_schedule_sent_twice_is_not_written_again(api, monkeypatch):
    saved = am.dumps(am.parse_sheets([CHARGED, UPCOMING]))
    monkeypatch.setattr(service, "my_loans", lambda identity: [{**LOANS[0], "fields": {**LOANS[0]["fields"], "Amortization Schedule": saved}}, LOANS[1]])
    pre = send(api[0]).get_json()
    assert pre["candidates"][0]["identical"] is True
    out = send(api[0], confirm="1", loan_id="recA", digest=pre["digest"]).get_json()
    assert out["state"] == "saved" and out["already"] is True and not WRITES
