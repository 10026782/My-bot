"""B2 step 2 — access policy for the (still EMPTY) ``Goal Allocations`` table, registered before any row exists.

Security: business roles / other owners / unresolved identities get nothing; an allocation cannot link a goal or an
account that belongs to someone else (create and update) or more than one record in either link.
Backward compatibility: nothing writes the table from code; existing FCC/accounts policies are unchanged.
Pure unit tests: Airtable is replaced by in-memory fakes; no network.
"""

from __future__ import annotations

import os

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-alloc-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:ALLOC_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patAllocTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appAllocTest")
os.environ.setdefault("ELIYAHU_CHAT_ID", "1")

import json

import pytest

import identity as identity_module
from airtable_schema import GoalAllocationFields as GA
from airtable_schema import Tables
from core import data_access_policy as policy
from core import owner_resolution
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

ALLOCATIONS = [
    {"id": "recAlE", "fields": {GA.NAME: "eli-alloc", GA.FINANCIAL_OWNER: [ELI]}},
    {"id": "recAlD", "fields": {GA.NAME: "dana-alloc", GA.FINANCIAL_OWNER: [DANA]}},
    {"id": "recAlN", "fields": {GA.NAME: "ownerless-alloc"}},
]


@pytest.fixture(autouse=True)
def fakes(monkeypatch):
    def fake_list_records(table, query, **kwargs):
        _f, value, _s, _ci = query.arguments
        return [p for p in PROFILES if p["fields"]["name"].casefold() == str(value).casefold()][: kwargs.get("max_records") or 99]

    monkeypatch.setattr(owner_resolution, "list_records", fake_list_records)
    monkeypatch.setattr(identity_module, "_REGISTRY", {"telegram:1": {"tenant": "boss_hq", "user": "eliyahu", "role": "owner"}})
    monkeypatch.setattr(dispatcher_module._ff, "is_enabled", lambda *a, **k: False)
    monkeypatch.setattr(airtable_tools, "_audit", lambda *a, **k: None)
    monkeypatch.setattr(airtable_tools, "airtable_get_records", lambda table, f="", max_records=None: list(ALLOCATIONS))
    owners = {"recGoalE": [ELI], "recGoalD": [DANA], "recAccE": [ELI], "recAccD": [DANA], "recAlE": [ELI], "recAlD": [DANA]}

    def get_fields(table, rid, **k):
        if rid not in owners:                      # an ownerless record
            return {}
        return {"Financial Owner": owners[rid]}

    monkeypatch.setattr("tools.airtable_read_adapter.get_record_fields", get_fields)


def agent_get(who, table="Goal Allocations"):
    return dispatcher_module.dispatch_tool("airtable_get", {"table": table}, who)


def test_field_names_match_the_live_schema_and_the_cache():
    names = [GA.NAME, GA.GOAL, GA.ACCOUNT, GA.FINANCIAL_OWNER, GA.MODE, GA.PERCENT, GA.AMOUNT, GA.STATUS,
             GA.EFFECTIVE_FROM, GA.NOTES, GA.CREATED_AT]
    assert names == ["Name", "Goal", "Account", "Financial Owner", "Mode", "Percent", "Amount", "Status",
                     "Effective From", "Notes", "Created At"]
    assert Tables.GOAL_ALLOCATIONS == "Goal Allocations"
    assert json.load(open("schema_cache.json"))["tables"]["Goal Allocations"] == names


def test_table_is_registered_owner_scoped_before_any_row_exists():
    p = policy.policy_for(Tables.GOAL_ALLOCATIONS)
    assert p is not None and p.mode == policy.OWNER_SCOPED and p.owner_field == GA.FINANCIAL_OWNER
    assert policy.is_owner_scoped("goal allocations") and policy.needs_record_filter("Goal Allocations ")


def test_business_roles_and_other_owners_never_see_allocations():
    for who in (MANAGER, EMPLOYEE):
        out = agent_get(who)
        for hidden in ("eli-alloc", "dana-alloc", "ownerless-alloc"):
            assert hidden not in out, (who.role, hidden)
    assert "dana-alloc" not in agent_get(ELIYAHU) and "ownerless-alloc" not in agent_get(ELIYAHU)
    assert "eli-alloc" in agent_get(ELIYAHU)
    assert "eli-alloc" not in agent_get(DANA_OWNER)


def test_unresolved_identity_and_raw_table_id_fail_closed():
    for who in (STRANGER, None):
        with pytest.raises(policy.PersonalDataAccessDenied):
            policy.filter_records(Tables.GOAL_ALLOCATIONS, ALLOCATIONS, who)
    assert "גישה נחסמה" in agent_get(ELIYAHU, "tblZgqHiBbSeyRTCA")
    assert "גישה נחסמה" in airtable_tools.airtable_get(Tables.GOAL_ALLOCATIONS, "")


def test_writes_are_owner_stamped_and_refuse_someone_elses_owner():
    assert policy.scope_new_record_fields(Tables.GOAL_ALLOCATIONS, {GA.NAME: "x"}, ELIYAHU)[GA.FINANCIAL_OWNER] == [ELI]
    with pytest.raises(policy.PersonalDataAccessDenied):
        policy.scope_new_record_fields(Tables.GOAL_ALLOCATIONS, {GA.NAME: "x", GA.FINANCIAL_OWNER: [DANA]}, ELIYAHU)
    enforce_tenant_scope("airtable_update", ELIYAHU, {"table": Tables.GOAL_ALLOCATIONS, "record_id": "recAlE"})
    for rid in ("recAlD", "recAlN"):
        with pytest.raises(TenantScopeViolation):
            enforce_tenant_scope("airtable_update", ELIYAHU, {"table": Tables.GOAL_ALLOCATIONS, "record_id": rid})


@pytest.mark.parametrize("link,own,foreign", [(GA.GOAL, "recGoalE", "recGoalD"), (GA.ACCOUNT, "recAccE", "recAccD")])
def test_allocation_cannot_link_another_persons_goal_or_account(link, own, foreign):
    base = {GA.MODE: "percent", GA.PERCENT: 10}
    for rid in (foreign, "recUnknownOwnerless"):
        with pytest.raises(policy.PersonalDataAccessDenied):
            policy.scope_new_record_fields(Tables.GOAL_ALLOCATIONS, {**base, link: [rid]}, ELIYAHU)
        with pytest.raises(TenantScopeViolation):
            enforce_tenant_scope("airtable_add", ELIYAHU, {"table": Tables.GOAL_ALLOCATIONS, "fields": {**base, link: [rid]}})
        with pytest.raises(TenantScopeViolation):
            enforce_tenant_scope("airtable_update", ELIYAHU, {"table": Tables.GOAL_ALLOCATIONS, "record_id": "recAlE",
                                                              "fields": {link: [rid]}})
    enforce_tenant_scope("airtable_update", ELIYAHU, {"table": Tables.GOAL_ALLOCATIONS, "record_id": "recAlE",
                                                      "fields": {link: [own]}})
    ok = policy.scope_new_record_fields(Tables.GOAL_ALLOCATIONS, {**base, link: [own]}, ELIYAHU)
    assert ok[link] == [own] and ok[GA.FINANCIAL_OWNER] == [ELI]


@pytest.mark.parametrize("link,rid", [(GA.GOAL, "recGoalE"), (GA.ACCOUNT, "recAccE")])
def test_links_are_single_record_even_though_airtable_allows_several(link, rid):
    with pytest.raises(policy.PersonalDataAccessDenied) as exc:
        policy.scope_new_record_fields(Tables.GOAL_ALLOCATIONS, {link: [rid, rid]}, ELIYAHU)
    assert exc.value.args[0] == policy.SINGLE_LINK_MESSAGE


def test_text_fields_reject_long_numbers_and_other_tables_are_untouched():
    for field in (GA.NAME, GA.NOTES):
        with pytest.raises(policy.PersonalDataAccessDenied) as exc:
            policy.scope_new_record_fields(Tables.GOAL_ALLOCATIONS, {GA.NAME: "x", field: "חשבון 123456789"}, ELIYAHU)
        assert exc.value.args[0] == policy.LONG_NUMBER_MESSAGE
        policy.scope_new_record_fields(Tables.GOAL_ALLOCATIONS, {GA.NAME: "x", field: "****1234"}, ELIYAHU)
    policy.scope_new_record_fields(Tables.GOAL_ALLOCATIONS, {GA.NAME: "x", GA.AMOUNT: 12345678.0, GA.EFFECTIVE_FROM: "2026-10-18"}, ELIYAHU)
    assert policy.scope_new_record_fields(Tables.FIN_GOALS, {"Title": "g", "Notes": "ref 123456789012"}, ELIYAHU)["Notes"]


def test_nothing_writes_allocations_from_code():
    assert Tables.GOAL_ALLOCATIONS not in getattr(approval_actions, "_TMA_WRITE_ALLOWED_TABLES", ())


def test_no_module_reads_or_writes_allocations_yet():
    """An allocation is a label on money, not a movement: until the read model (step 3) is approved nothing in the
    runtime may touch the table, so it cannot change a balance, create a deposit/withdrawal or bypass ActionGateway."""
    import pathlib
    import re

    allowed = {"airtable_schema.py", "core/data_access_policy.py"}
    offenders = []
    for path in pathlib.Path(".").rglob("*.py"):
        rel = path.as_posix()
        if rel.startswith(("test_", "tma-frontend", "node_modules", ".git")) or "/test_" in rel or rel in allowed:
            continue
        if re.search(r"GOAL_ALLOCATIONS|GoalAllocationFields|Goal Allocations", path.read_text(encoding="utf-8", errors="ignore")):
            offenders.append(rel)
    assert offenders == []
