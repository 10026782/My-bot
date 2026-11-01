"""FCC cashflow rules table (``Cashflow Rules``) — registration, owner scoping and the conversion to import rules. In-memory fakes; no network."""

from __future__ import annotations

import os

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-cr-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:CR_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patCrTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appCrTest")
os.environ.setdefault("ELIYAHU_CHAT_ID", "1")

import json
from datetime import date

import pytest

import identity as identity_module
from airtable_schema import CashflowRuleFields as CR
from airtable_schema import Tables
from core import data_access_policy as policy
from core import owner_resolution
from core.financial_control import bank_import as bi
from core.financial_control import card_import as ci
from core.financial_control import service
from identity import Domain, Identity, Role

ELI, DANA = "recEli", "recDana"
PROFILES = [{"id": ELI, "fields": {"name": "Eliyahu"}}, {"id": DANA, "fields": {"name": "Dana"}}]


def ident(uid, role):
    return Identity(user_id=uid, role=role, display_name=uid, tenant_id="boss_hq", domain_id=Domain.GENERAL,
                    allowed_domains=[], channel="telegram", external_id=f"tg-{uid}")


ELIYAHU, DANA_OWNER, MANAGER, STRANGER = ident("eliyahu", Role.OWNER), ident("dana", Role.OWNER), ident("manny", Role.MANAGER), ident("nobody", Role.MANAGER)


def rule(rid, match="", owner=ELI, **f):
    return {"id": rid, "fields": {CR.MATCH: match, CR.FINANCIAL_OWNER: [owner], **f}}


RULES = [
    rule("r1", "מרכז התורה", **{CR.KIND: "expense", CR.CATEGORY: "institutions", CR.DIRECTION: "debit", CR.STATUS: "active", CR.APPLIES_TO: "bank"}),
    rule("r2", "שופרסל", **{CR.KIND: "expense", CR.CATEGORY: "living", CR.APPLIES_TO: "card"}),                       # no status: decided
    rule("r3", 'מלם מערכות', **{CR.KIND: "income", CR.CATEGORY: "עבודת אשתי", CR.DIRECTION: "credit"}),                # no scope: "any"
    rule("r4", "יגדיל תורה", **{CR.STATUS: "pending"}),                                                               # waiting for the owner
    rule("r5", "גמח", **{CR.KIND: "expense", CR.CATEGORY: "donations", CR.STATUS: "disabled"}),
    rule("r6", "", **{CR.KIND: "income", CR.CATEGORY: "הכנסה", CR.ROW_KEY: "bank:abc123"}),                            # one row
    rule("r7", "", **{CR.KIND: "expense"}),                                                                           # neither a match nor a row key
    rule("rD", "של דנה", owner=DANA, **{CR.KIND: "expense", CR.CATEGORY: "living"}),
]
DB: dict = {}


@pytest.fixture(autouse=True)
def fakes(monkeypatch):
    DB.clear()
    DB[Tables.CASHFLOW_RULES] = list(RULES)

    def fake_profile(table, query, **kw):
        _f, value, _s, _ci = query.arguments
        return [p for p in PROFILES if p["fields"]["name"].casefold() == str(value).casefold()]
    monkeypatch.setattr(owner_resolution, "list_records", fake_profile)
    monkeypatch.setattr(identity_module, "_REGISTRY", {"telegram:1": {"tenant": "boss_hq", "user": "eliyahu", "role": "owner"}})
    monkeypatch.setattr(service, "_read", lambda table, formula="": list(DB.get(table, [])))


def test_table_is_registered_owner_scoped_and_matches_the_cache():
    names = [CR.MATCH, CR.APPLIES_TO, CR.DIRECTION, CR.KIND, CR.CATEGORY, CR.ROW_KEY, CR.STATUS, CR.TIMES_SEEN, CR.LAST_SEEN, CR.EXAMPLE_AMOUNT,
             CR.NOTES, CR.FINANCIAL_OWNER, CR.CREATED_AT]
    assert json.load(open("schema_cache.json"))["tables"]["Cashflow Rules"] == names and Tables.CASHFLOW_RULES == "Cashflow Rules"
    p = policy.policy_for(Tables.CASHFLOW_RULES)
    assert p is not None and p.mode == policy.OWNER_SCOPED and p.owner_field == CR.FINANCIAL_OWNER and policy.is_owner_scoped("cashflow rules")


def test_a_person_only_ever_reads_their_own_rules():
    mine = {r["id"] for r in service.my_cashflow_rules(ELIYAHU)}
    assert "rD" not in mine and {"r1", "r2", "r3"} <= mine
    assert {r["id"] for r in service.my_cashflow_rules(DANA_OWNER)} == {"rD"}
    for who in (STRANGER, None):
        with pytest.raises(policy.PersonalDataAccessDenied):
            service.my_cashflow_rules(who)


def test_only_decided_active_rules_become_import_rules():
    items = service.cashflow_rule_items(service.my_cashflow_rules(ELIYAHU))
    assert [i.get("match") or i.get("key") for i in items] == ["מרכז התורה", "שופרסל", "מלם מערכות", "bank:abc123"]       # pending / disabled / empty skipped
    assert items[0] == {"kind": "expense", "category": "institutions", "direction": "debit", "match": "מרכז התורה"}
    assert items[2]["direction"] == "credit" and items[3] == {"kind": "income", "category": "הכנסה", "direction": None, "key": "bank:abc123"}


def test_rules_are_filtered_by_what_they_apply_to():
    rows = service.my_cashflow_rules(ELIYAHU)
    bank = [i.get("match") or i.get("key") for i in service.cashflow_rule_items(rows, "bank")]
    card = [i.get("match") or i.get("key") for i in service.cashflow_rule_items(rows, "card")]
    assert bank == ["מרכז התורה", "מלם מערכות", "bank:abc123"] and card == ["שופרסל", "מלם מערכות", "bank:abc123"]


def test_the_owners_rules_decide_real_descriptions_for_bank_and_card():
    rules = service.cashflow_rules(ELIYAHU, "bank")
    mk = lambda d, side, key="": bi.BankRow(date(2026, 10, 1), d, 100.0, side, 0.0, True, key=key)
    got = bi.classify_row(mk("מרכז התורה רחו", "debit"), rules)
    assert (got.kind, got.category, bi.importable(got)) == (bi.EXPENSE, "institutions", True)
    inc = bi.classify_row(mk('מלם מערכות בע"', "credit"), rules)
    assert (inc.kind, inc.category, bi.importable(inc)) == (bi.INCOME_APPROVED, "עבודת אשתי", True)
    assert bi.classify_row(mk("העברה", "credit", "bank:abc123"), rules).kind == bi.INCOME_APPROVED            # the single-row rule
    assert bi.classify_row(mk("העברה", "credit", "bank:other"), rules).kind == bi.NEEDS_REVIEW                  # its neighbours still wait
    assert bi.classify_row(mk("יגדיל תורה", "credit"), rules).kind == bi.INCOME                                  # pending: still only a candidate
    card = service.cashflow_rules(ELIYAHU, "card")
    charge = ci.CardCharge(date(2026, 9, 1), "שופרסל יש חסד", 10.0, 10.0, "1", date(2026, 10, 10), 1, ci.REGULAR)
    assert ci.classify_charge(charge, card).category == "living"


def test_a_failed_read_is_an_error_not_an_empty_rule_list(monkeypatch):
    def broken(table, formula=""):
        raise RuntimeError("airtable down")
    monkeypatch.setattr(service, "_read", broken)
    with pytest.raises(RuntimeError):
        service.cashflow_rules(ELIYAHU)
