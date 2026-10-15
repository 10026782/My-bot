"""D1 step 3a — access policy for the (still EMPTY) ``Financial Accounts`` table, registered before any row exists.

Security: business roles / other owners / unresolved identities get nothing; an event cannot link to another person's
account (create and update, ``Account`` and ``Counter Account``) or to more than one account.
Backward compatibility: the new Kind values stay outside ``calc.EVENT_KINDS`` and nothing writes accounts yet.
Pure unit tests: Airtable is replaced by in-memory fakes; no network.
"""

from __future__ import annotations

import os

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-accounts-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:ACCOUNTS_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patAccountsTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appAccountsTest")
os.environ.setdefault("ELIYAHU_CHAT_ID", "1")

import pytest

import identity as identity_module
from airtable_schema import FinAccountFields as AF
from airtable_schema import FinEventFields as EF
from airtable_schema import Tables
from core import data_access_policy as policy
from core import owner_resolution
from core.financial_control import calc
from identity import Domain, Identity, Role
from tools import airtable_tools, approval_actions
from tools import dispatcher as dispatcher_module
from tools.airtable_security import TenantScopeViolation, enforce_tenant_scope

ELI, DANA = "recEli", "recDana"
PROFILES = [{"id": ELI, "fields": {"name": "Eliyahu"}}, {"id": DANA, "fields": {"name": "Dana"}},
            {"id": "recMgr", "fields": {"name": "Manny"}}, {"id": "recEmp", "fields": {"name": "Eve"}}]


def ident(user_id, role):
    return Identity(user_id=user_id, role=role, display_name=user_id, tenant_id="boss_hq", domain_id=Domain.GENERAL,
                    allowed_domains=[], channel="telegram", external_id=f"tg-{user_id}")


ELIYAHU, DANA_OWNER = ident("eliyahu", Role.OWNER), ident("dana", Role.OWNER)
MANAGER, EMPLOYEE, STRANGER = ident("manny", Role.MANAGER), ident("eve", Role.EMPLOYEE), ident("nobody", Role.MANAGER)

ACCOUNTS = [
    {"id": "recAccE", "fields": {AF.NAME: "eli-pension", AF.HOLDER_NAMES: "Eli", AF.FINANCIAL_OWNER: [ELI]}},
    {"id": "recAccD", "fields": {AF.NAME: "dana-fund", AF.HOLDER_NAMES: "Dana", AF.FINANCIAL_OWNER: [DANA]}},
    {"id": "recAccN", "fields": {AF.NAME: "ownerless-account", AF.HOLDER_NAMES: "Nobody"}},
]


@pytest.fixture(autouse=True)
def fakes(monkeypatch):
    def fake_list_records(table, query, **kwargs):
        assert table == Tables.PROFILE
        _f, value, _s, _ci = query.arguments
        return [p for p in PROFILES if p["fields"]["name"].casefold() == str(value).casefold()][: kwargs.get("max_records") or 99]

    monkeypatch.setattr(owner_resolution, "list_records", fake_list_records)
    monkeypatch.setattr(identity_module, "_REGISTRY", {"telegram:1": {"tenant": "boss_hq", "user": "eliyahu", "role": "owner"}})
    monkeypatch.setattr(dispatcher_module._ff, "is_enabled", lambda *a, **k: False)
    monkeypatch.setattr(airtable_tools, "_audit", lambda *a, **k: None)
    monkeypatch.setattr(airtable_tools, "airtable_get_records", lambda table, f="", max_records=None: list(ACCOUNTS))
    goals = {"recGoalE": {"Financial Owner": [ELI]}, "recGoalD": {"Financial Owner": [DANA]}}

    def get_fields(table, rid, **k):
        if table == Tables.FIN_ACCOUNTS:
            return dict(next(r for r in ACCOUNTS if r["id"] == rid)["fields"])
        if table == Tables.FIN_GOALS:
            return dict(goals[rid])
        if table == Tables.FIN_EVENTS:
            return {EF.FINANCIAL_OWNER: [ELI]}            # "recEv": the caller's own existing event
        raise KeyError(table)

    monkeypatch.setattr("tools.airtable_read_adapter.get_record_fields", get_fields)


def agent_get(who, table="Financial Accounts"):
    return dispatcher_module.dispatch_tool("airtable_get", {"table": table}, who)


# ═══════════════ security: who can read the accounts table ═══════════════

def test_table_is_registered_owner_scoped_before_any_row_exists():
    p = policy.policy_for(Tables.FIN_ACCOUNTS)
    assert p is not None and p.mode == policy.OWNER_SCOPED and p.owner_field == AF.FINANCIAL_OWNER
    assert policy.is_owner_scoped("financial accounts") and policy.needs_record_filter("Financial Accounts ")


def test_business_roles_and_other_owners_never_see_accounts():
    for who in (MANAGER, EMPLOYEE):
        out = agent_get(who)
        for hidden in ("eli-pension", "dana-fund", "ownerless-account", "Holder", "Eli", "Dana"):
            assert hidden not in out, (who.role, hidden)
    assert "dana-fund" not in agent_get(ELIYAHU) and "ownerless-account" not in agent_get(ELIYAHU)
    assert "eli-pension" not in agent_get(DANA_OWNER)


def test_owner_reads_only_own_accounts_and_name_variants_resolve_to_the_same_policy():
    for variant in ("Financial Accounts", "financial accounts", " FINANCIAL ACCOUNTS "):
        out = agent_get(ELIYAHU, variant)
        assert "eli-pension" in out and "Eli" in out
        assert "dana-fund" not in out and "ownerless-account" not in out


def test_unresolved_identity_and_raw_table_id_fail_closed():
    for who in (STRANGER, None):
        with pytest.raises(policy.PersonalDataAccessDenied):
            policy.filter_records(Tables.FIN_ACCOUNTS, ACCOUNTS, who)
        with pytest.raises(policy.PersonalDataAccessDenied):
            policy.enforce_table_access("airtable_get", who, {"table": Tables.FIN_ACCOUNTS})
    assert "גישה נחסמה" in agent_get(ELIYAHU, "tblhV9f86iXMIwKx1")          # raw table id would dodge name-based policy
    assert "גישה נחסמה" in airtable_tools.airtable_get(Tables.FIN_ACCOUNTS, "")   # caller that skips the dispatcher


def test_account_writes_are_owner_stamped_and_refuse_someone_elses_owner():
    assert policy.scope_new_record_fields(Tables.FIN_ACCOUNTS, {AF.NAME: "x"}, ELIYAHU)[AF.FINANCIAL_OWNER] == [ELI]
    with pytest.raises(policy.PersonalDataAccessDenied):
        policy.scope_new_record_fields(Tables.FIN_ACCOUNTS, {AF.NAME: "x", AF.FINANCIAL_OWNER: [DANA]}, ELIYAHU)
    enforce_tenant_scope("airtable_update", ELIYAHU, {"table": Tables.FIN_ACCOUNTS, "record_id": "recAccE"})
    for rid in ("recAccD", "recAccN"):
        with pytest.raises(TenantScopeViolation):
            enforce_tenant_scope("airtable_update", ELIYAHU, {"table": Tables.FIN_ACCOUNTS, "record_id": rid})


# ═══════════════ security: events cannot hang under someone else's account ═══════════════

@pytest.mark.parametrize("link", [EF.ACCOUNT, EF.COUNTER_ACCOUNT])
def test_event_cannot_link_to_another_persons_or_ownerless_account(link):
    base = {EF.KIND: "balance_snapshot", EF.AMOUNT: 1}
    for rid in ("recAccD", "recAccN"):
        with pytest.raises(policy.PersonalDataAccessDenied):
            policy.scope_new_record_fields(Tables.FIN_EVENTS, {**base, link: [rid]}, ELIYAHU)         # create
        with pytest.raises(TenantScopeViolation):
            enforce_tenant_scope("airtable_add", ELIYAHU, {"table": Tables.FIN_EVENTS, "fields": {**base, link: [rid]}})
        with pytest.raises(TenantScopeViolation):                                                       # update
            enforce_tenant_scope("airtable_update", ELIYAHU, {"table": Tables.FIN_EVENTS, "record_id": "recEv",
                                                              "fields": {link: [rid]}})
    # the same update is accepted when the account is the caller's own (so the denials above are the link guard)
    enforce_tenant_scope("airtable_update", ELIYAHU, {"table": Tables.FIN_EVENTS, "record_id": "recEv",
                                                      "fields": {link: ["recAccE"]}})
    ok = policy.scope_new_record_fields(Tables.FIN_EVENTS, {**base, link: ["recAccE"]}, ELIYAHU)
    assert ok[link] == ["recAccE"] and ok[EF.FINANCIAL_OWNER] == [ELI]


def test_event_links_are_single_record_even_though_airtable_allows_several():
    with pytest.raises(policy.PersonalDataAccessDenied) as exc:
        policy.scope_new_record_fields(Tables.FIN_EVENTS, {EF.ACCOUNT: ["recAccE", "recAccE"]}, ELIYAHU)
    assert exc.value.args[0] == policy.SINGLE_LINK_MESSAGE
    with pytest.raises(policy.PersonalDataAccessDenied):
        policy.scope_new_record_fields(Tables.FIN_EVENTS, {EF.COUNTER_ACCOUNT: ["recAccE", "recAccD"]}, ELIYAHU)
    # Goal stays multi-record (existing contract)
    out = policy.scope_new_record_fields(Tables.FIN_EVENTS, {EF.GOAL: ["recGoalE", "recGoalE"], EF.AMOUNT: 5}, ELIYAHU)
    assert out[EF.GOAL] == ["recGoalE", "recGoalE"]


# ═══════════════ backward compatibility ═══════════════

def test_existing_goal_link_guard_is_unchanged():
    assert policy.scope_new_record_fields(Tables.FIN_EVENTS, {EF.GOAL: ["recGoalE"], EF.KIND: "one_time"}, ELIYAHU)[EF.FINANCIAL_OWNER] == [ELI]
    with pytest.raises(policy.PersonalDataAccessDenied):
        policy.scope_new_record_fields(Tables.FIN_EVENTS, {EF.GOAL: ["recGoalD"], EF.KIND: "one_time"}, ELIYAHU)
    assert policy.policy_for(Tables.FIN_EVENTS).linked_owner_checks[0] == ("Goal", Tables.FIN_GOALS)


def test_new_event_kinds_stay_outside_every_existing_consumer():
    new = {"deposit", "withdrawal", "fee", "transfer", "balance_snapshot"}
    assert not new & set(calc.EVENT_KINDS)
    records = [{"id": f"rec{k}", "fields": {EF.KIND: k, EF.AMOUNT: 500000, EF.OCCURRED_AT: "2026-10-01"}} for k in sorted(new)]
    assert calc.parse_events(records, EF) == []          # no existing calculation counts them


def test_nothing_writes_accounts_yet():
    assert Tables.FIN_ACCOUNTS not in getattr(approval_actions, "_TMA_WRITE_ALLOWED_TABLES", ())


def test_field_names_match_the_live_schema():
    assert [AF.NAME, AF.ACCOUNT_TYPE, AF.INSTITUTION, AF.FINANCIAL_OWNER, AF.HOLDER_NAMES, AF.STATUS, AF.LIQUIDITY,
            AF.LIQUID_FROM, AF.TAX_TREATMENT, AF.TAX_NOTES, AF.MANAGEMENT_FEE, AF.OPENED_AT, AF.CLOSED_AT, AF.NOTES,
            AF.CREATED_AT] == ["Name", "Account Type", "Institution", "Financial Owner", "Holder Names", "Status",
                               "Liquidity", "Liquid From", "Tax Treatment", "Tax Notes", "Management Fee %", "Opened At",
                               "Closed At", "Notes", "Created At"]
    assert (EF.ACCOUNT, EF.COUNTER_ACCOUNT, EF.VERIFICATION) == ("Account", "Counter Account", "Verification")
    assert Tables.FIN_ACCOUNTS == "Financial Accounts"
