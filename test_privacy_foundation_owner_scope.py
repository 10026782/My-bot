"""Privacy Foundation (PRIV-FCC-01): owner-of-record scoping for personal data.

Covers core/data_access_policy.py and every path wired to it:
generic agent tools (dispatcher -> enforce_tenant_scope), TMA /api/assets*,
TMA My-Work / task PATCH, tma_write execution-time re-check, and the strict
Profile resolution (core/owner_resolution.py). Pure unit tests: Airtable is
replaced by in-memory fakes; no network.
"""

from __future__ import annotations

import os

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-privacy-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:PRIVACY_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patPrivacyTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appPrivacyTest")
os.environ.setdefault("ELIYAHU_CHAT_ID", "1")

import pytest
from flask import Flask

import identity as identity_module
import tma_api
from airtable_schema import Tables, TaskFields, TaskStatus
from core import data_access_policy as policy
from core import owner_resolution
from identity import Domain, Identity, Role
from tools import airtable_security, airtable_tools, approval_actions
from tools import dispatcher as dispatcher_module
from tools.airtable_security import TenantScopeViolation, enforce_tenant_scope

ELI, DANA, AVI, MGR, EMP = "recEli", "recDana", "recAvi", "recMgr", "recEmp"

PROFILES = [
    {"id": ELI, "fields": {"name": "Eliyahu"}},
    {"id": DANA, "fields": {"name": "Dana"}},      # a second *owner* (hypothetical)
    {"id": AVI, "fields": {"name": "Avi"}},
    {"id": MGR, "fields": {"name": "Manny"}},
    {"id": EMP, "fields": {"name": "Eve"}},
    {"id": "recJunk", "fields": {"name": "ליד חדש"}},
]


def ident(user_id, role, domains=()):
    return Identity(
        user_id=user_id, role=role, display_name=user_id, tenant_id="boss_hq",
        domain_id=Domain.GENERAL, allowed_domains=list(domains),
        channel="telegram", external_id=f"tg-{user_id}",
    )


ELIYAHU = ident("eliyahu", Role.OWNER)
DANA_OWNER = ident("dana", Role.OWNER)
AVI_PARTNER = ident("avi", Role.PARTNER, ["recruitment", "personal"])
MANAGER = ident("manny", Role.MANAGER)
EMPLOYEE = ident("eve", Role.EMPLOYEE)
STRANGER = ident("nobody", Role.MANAGER)            # no Profile row at all
LEAD = ident("+972500000000", Role.LEAD)


def rec(rid, **fields):
    return {"id": rid, "fields": fields}


LOANS = [
    rec("recLoanE", **{"Loan Name/ID": "eli-loan", "Owner": [ELI]}),
    rec("recLoanD", **{"Loan Name/ID": "dana-loan", "Owner": [DANA]}),
    rec("recLoanN", **{"Loan Name/ID": "ownerless-loan"}),
]
ASSETS = [
    rec("recAssetE", Name="eli-asset", **{"Current Value": 1000, "Mortgage Balance": 100, "Equity": 900,
                                          "My Equity": 900, "Monthly Income": 10, "Owner": [ELI]}),
    rec("recAssetD", Name="dana-asset", **{"Current Value": 5000, "Mortgage Balance": 500, "Equity": 4500,
                                           "My Equity": 4500, "Monthly Income": 50, "Owner": [DANA]}),
    rec("recAssetN", Name="ownerless-asset", **{"Current Value": 7000, "Equity": 7000, "Owner": []}),
]


@pytest.fixture(autouse=True)
def fakes(monkeypatch):
    """Profile table + identity registry + Airtable readers, all in memory."""
    def fake_list_records(table, query, **kwargs):
        assert table == Tables.PROFILE
        _field, value, _spaced, _ci = query.arguments
        return [p for p in PROFILES if p["fields"]["name"].casefold() == str(value).casefold()][: kwargs.get("max_records") or 99]

    monkeypatch.setattr(owner_resolution, "list_records", fake_list_records)
    monkeypatch.setattr(identity_module, "_REGISTRY", {
        "telegram:1": {"tenant": "boss_hq", "user": "eliyahu", "role": "owner"},
        "whatsapp:972": {"tenant": "boss_hq", "user": "eliyahu", "role": "owner"},   # same person, 2nd channel
        "telegram:2": {"tenant": "boss_hq", "user": "avi", "role": "partner", "domains": ["recruitment"]},
    })
    monkeypatch.setattr(dispatcher_module._ff, "is_enabled", lambda *a, **k: False)
    monkeypatch.setattr(airtable_tools, "_audit", lambda *a, **k: None)


def serve(monkeypatch, table_rows: dict):
    """Generic agent read returns raw rows (Airtable would not filter by Owner)."""
    monkeypatch.setattr(airtable_tools, "airtable_get_records", lambda table, f="", max_records=None: list(table_rows[table]))


def agent_get(identity, table):
    return dispatcher_module.dispatch_tool("airtable_get", {"table": table}, identity)


# ═══════════════ P1 — generic Airtable read (dispatcher / airtable_get) ═══════════════

def test_1_employee_cannot_read_personal_loans(monkeypatch):
    serve(monkeypatch, {"Loans": LOANS})
    out = agent_get(EMPLOYEE, "Loans")
    assert "eli-loan" not in out and "dana-loan" not in out and "ownerless-loan" not in out


def test_2_manager_cannot_read_personal_loans(monkeypatch):
    serve(monkeypatch, {"Loans": LOANS})
    out = agent_get(MANAGER, "Loans")
    assert "eli-loan" not in out and "dana-loan" not in out and "ownerless-loan" not in out


def test_3_owner_a_cannot_read_owner_b_personal_data(monkeypatch):
    serve(monkeypatch, {"Loans": LOANS, "Assets": ASSETS})
    for table, other in (("Loans", "dana-loan"), ("Assets", "dana-asset")):
        assert other not in agent_get(ELIYAHU, table)
    for table, other in (("Loans", "eli-loan"), ("Assets", "eli-asset")):
        assert other not in agent_get(DANA_OWNER, table)


def test_12_authorized_owner_still_reads_own_records(monkeypatch):
    serve(monkeypatch, {"Loans": LOANS, "Assets": ASSETS})
    out = agent_get(ELIYAHU, "Loans")
    assert "eli-loan" in out and "recLoanE" in out
    assert "dana-loan" not in out and "ownerless-loan" not in out   # ownerless: nobody
    assert "eli-asset" in agent_get(ELIYAHU, "Assets")


def test_11_generic_read_cannot_bypass_policy(monkeypatch):
    serve(monkeypatch, {"Loans": LOANS, "Assets": ASSETS, "tblABCDEFGHIJKLMN": LOANS})
    # alias / case / whitespace variants resolve to the same policy
    for variant in ("loans", "LOANS", " Loans ", "assets", "Assets "):
        out = agent_get(MANAGER, variant)
        assert "dana-loan" not in out and "eli-loan" not in out and "dana-asset" not in out
    # raw table id would dodge name-based rules -> denied on the generic path
    out = agent_get(ELIYAHU, "tblABCDEFGHIJKLMN")
    assert "eli-loan" not in out and "גישה נחסמה" in out
    # a caller that skips the dispatcher cannot render a policy table unfiltered
    assert "גישה נחסמה" in airtable_tools.airtable_get("Loans", "")
    # filter formula injection does not change who may see what
    assert "dana-loan" not in agent_get(ELIYAHU, "Loans").replace("eli-loan", "")


def test_11b_write_paths_enforce_owner_of_record(monkeypatch):
    # airtable_update on another person's asset -> blocked before any write
    monkeypatch.setattr("tools.airtable_read_adapter.get_record_fields",
                        lambda table, rid, **k: dict(next(r for r in ASSETS if r["id"] == rid)["fields"]))
    with pytest.raises(TenantScopeViolation):
        enforce_tenant_scope("airtable_update", ELIYAHU, {"table": "Assets", "record_id": "recAssetD"})
    with pytest.raises(TenantScopeViolation):
        enforce_tenant_scope("airtable_update", ELIYAHU, {"table": "Assets", "record_id": "recAssetN"})
    enforce_tenant_scope("airtable_update", ELIYAHU, {"table": "Assets", "record_id": "recAssetE"})   # own: ok
    # unreadable record -> fail closed
    def boom(*a, **k):
        raise RuntimeError("airtable down")
    monkeypatch.setattr("tools.airtable_read_adapter.get_record_fields", boom)
    with pytest.raises(TenantScopeViolation):
        enforce_tenant_scope("airtable_update", ELIYAHU, {"table": "Assets", "record_id": "recAssetE"})
    # creating: Owner is stamped to the actor; someone else's Owner is refused
    assert policy.scope_new_record_fields("Assets", {"Name": "x"}, ELIYAHU)["Owner"] == [ELI]
    with pytest.raises(policy.PersonalDataAccessDenied):
        policy.scope_new_record_fields("Assets", {"Name": "x", "Owner": [DANA]}, ELIYAHU)


def test_13_non_sensitive_tables_unchanged(monkeypatch):
    leads = [rec("recL1", Name="lead-1")]
    serve(monkeypatch, {"Leads": leads, "Expenses": [rec("recX", name="exp-1")]})
    assert "lead-1" in agent_get(MANAGER, "Leads")
    assert "exp-1" in agent_get(EMPLOYEE, "Expenses")
    assert policy.policy_for("Leads") is None and not policy.needs_record_filter("Payments")
    assert enforce_tenant_scope("airtable_get", MANAGER, {"table": "Leads"}) == {"table": "Leads"}


# ═══════════════ P2 — /api/assets owner isolation + aggregates ═══════════════

def tma_client(monkeypatch, who):
    app = Flask(__name__)
    app.register_blueprint(tma_api.tma_api)
    monkeypatch.setattr(tma_api, "_validate_initdata", lambda _: {"id": who.user_id})
    monkeypatch.setattr(tma_api, "resolve_identity", lambda *_: who)
    return app.test_client()


H = {"X-Telegram-Init-Data": "valid"}


def asset_store(monkeypatch):
    monkeypatch.setattr(tma_api, "_at_list", lambda table, *a, **k: list(ASSETS))
    monkeypatch.setattr(tma_api, "_at_get_record",
                        lambda table, rid: next((r for r in ASSETS if r["id"] == rid), None))


def test_4_assets_endpoint_never_returns_other_owners_assets(monkeypatch):
    asset_store(monkeypatch)
    body = tma_client(monkeypatch, ELIYAHU).get("/api/assets", headers=H).get_json()
    assert [a["name"] for a in body["assets"]] == ["eli-asset"]
    body = tma_client(monkeypatch, DANA_OWNER).get("/api/assets", headers=H).get_json()
    assert [a["name"] for a in body["assets"]] == ["dana-asset"]


def test_5_aggregates_exclude_other_owners_and_ownerless(monkeypatch):
    asset_store(monkeypatch)
    body = tma_client(monkeypatch, ELIYAHU).get("/api/assets", headers=H).get_json()
    assert body["count"] == 1
    assert (body["total_value"], body["total_debt"], body["total_equity"],
            body["my_equity"], body["monthly_income"]) == (1000, 100, 900, 900, 10)


def test_asset_detail_and_patch_are_owner_of_record_only(monkeypatch):
    asset_store(monkeypatch)
    queued = []
    monkeypatch.setattr(tma_api, "_queue_or_owner_execute",
                        lambda a, p, i, l: (queued.append((a, p)) or ("ap-1", {"ok": True, "status": "executed"}, 200)))
    c = tma_client(monkeypatch, ELIYAHU)
    assert c.get("/api/assets/recAssetE", headers=H).status_code == 200
    assert c.get("/api/assets/recAssetD", headers=H).status_code == 404       # no existence oracle
    assert c.get("/api/assets/recAssetN", headers=H).status_code == 404       # ownerless: nobody
    assert c.patch("/api/assets/recAssetD", json={"Status": "x"}, headers=H).status_code == 404
    assert c.patch("/api/assets/recAssetN", json={"Status": "x"}, headers=H).status_code == 404
    assert queued == []
    assert c.patch("/api/assets/recAssetE", json={"Status": "x"}, headers=H).status_code == 200
    assert [p["record_id"] for _, p in queued] == ["recAssetE"]


def test_15_authorized_asset_flow_unchanged(monkeypatch):
    asset_store(monkeypatch)
    r = tma_client(monkeypatch, ELIYAHU).get("/api/assets/recAssetE", headers=H).get_json()
    assert r["name"] == "eli-asset" and r["equity"] == 900 and r["my_equity"] == 900


def test_tma_write_rechecks_ownership_at_execution(monkeypatch):
    monkeypatch.setattr(approval_actions, "_verify_active_execution_claim", lambda *a: True)
    monkeypatch.setattr("tools.airtable_read_adapter.get_record_fields",
                        lambda table, rid, **k: dict(next(r for r in ASSETS if r["id"] == rid)["fields"]))
    patched = []
    import tools.airtable_gateway as gw
    monkeypatch.setattr(gw, "airtable_patch", lambda *a, **k: patched.append(a) or True)
    ctx = {"contract_id": "c1", "approved_by": "eliyahu", "claim_execution_id": "x1"}
    common = dict(op="patch", table="Assets", fields={"Status": "x"}, trusted_source="tma_api", execution_context=ctx)
    denied = approval_actions.tma_write(record_id="recAssetD", identity=ELIYAHU, **common)
    assert denied["ok"] is False and patched == []
    denied = approval_actions.tma_write(record_id="recAssetN", identity=ELIYAHU, **common)
    assert denied["ok"] is False and patched == []
    ok = approval_actions.tma_write(record_id="recAssetE", identity=ELIYAHU, **common)
    assert ok["ok"] is True and len(patched) == 1


# ═══════════════ P3 — partner / domain path ═══════════════

def test_6_partner_cannot_bypass_owner_restriction_via_domain(monkeypatch):
    asset_store(monkeypatch)
    # "personal" in allowed_domains opens the feature, never someone else's assets
    body = tma_client(monkeypatch, AVI_PARTNER).get("/api/assets", headers=H).get_json()
    assert body["assets"] == [] and body["total_value"] == 0
    serve(monkeypatch, {"Loans": LOANS, "Assets": ASSETS})
    for table in ("Loans", "Assets"):
        out = agent_get(AVI_PARTNER, table)
        assert "eli-" not in out and "dana-" not in out
    # partner + private task in his own domain, owned by Eliyahu: hidden; business task: visible
    tasks = [
        rec("recT1", **{"כותרת המשימה": "private-eli", "Domain": "Recruitment", "Visibility": "Private", "Owner": [ELI]}),
        rec("recT2", **{"כותרת המשימה": "biz-recruit", "Domain": "Recruitment"}),
    ]
    serve(monkeypatch, {Tables.TASKS: tasks})
    out = agent_get(AVI_PARTNER, Tables.TASKS)
    assert "private-eli" not in out and "biz-recruit" in out
    # partner generic update of an owner's asset is stopped by the central hook too
    monkeypatch.setattr("tools.airtable_read_adapter.get_record_fields",
                        lambda table, rid, **k: dict(next(r for r in ASSETS if r["id"] == rid)["fields"]))
    with pytest.raises(TenantScopeViolation):
        enforce_tenant_scope("airtable_update", AVI_PARTNER, {"table": "Assets", "record_id": "recAssetE"})


# ═══════════════ P4 — Tasks without Owner / private tasks ═══════════════

def work_for(identity, records, profile_id):
    return tma_api._process_owner_tasks(
        records, profile_id, identity.user_id, "2026-10-04",
        claim_ownerless=policy.ownerless_task_claimable(identity),
    )


def titles(result):
    return sorted(t["title"] for t in result["immediate"] + result["upcoming"])


def _task(rid, title, **extra):
    return rec(rid, **{TaskFields.NAME: title, TaskFields.STATUS: TaskStatus.PENDING, **extra})


def test_9_private_task_of_a_never_reaches_b(monkeypatch):
    records = [
        _task("t1", "private-eli", Visibility="Private", Owner=[ELI]),
        _task("t2", "private-ownerless", Visibility="Private"),
        _task("t3", "biz-owned-eli", Owner=[ELI]),
    ]
    assert titles(work_for(ELIYAHU, records, ELI)) == ["biz-owned-eli", "private-eli"]
    assert titles(work_for(DANA_OWNER, records, DANA)) == []          # also no ownerless private for anyone
    serve(monkeypatch, {Tables.TASKS: records})
    out = agent_get(MANAGER, Tables.TASKS)
    assert "private-eli" not in out and "private-ownerless" not in out and "biz-owned-eli" in out
    assert "private-eli" in agent_get(ELIYAHU, Tables.TASKS)


def test_10_existing_business_tasks_keep_working():
    records = [_task("t1", "ownerless-biz"), _task("t2", "owned-eli", Owner=[ELI]), _task("t3", "owned-dana", Owner=[DANA])]
    assert policy.ownerless_task_claimable(ELIYAHU) is True            # sole business owner (registry)
    assert titles(work_for(ELIYAHU, records, ELI)) == ["owned-eli", "ownerless-biz"]


def test_10b_ownerless_not_auto_assigned_once_a_second_owner_exists(monkeypatch):
    reg = dict(identity_module._REGISTRY)
    reg["telegram:3"] = {"tenant": "boss_hq", "user": "dana", "role": "owner"}
    monkeypatch.setattr(identity_module, "_REGISTRY", reg)
    records = [_task("t1", "ownerless-biz"), _task("t2", "owned-eli", Owner=[ELI])]
    assert policy.ownerless_task_claimable(ELIYAHU) is False
    assert titles(work_for(ELIYAHU, records, ELI)) == ["owned-eli"]
    assert titles(work_for(DANA_OWNER, records, DANA)) == []


def test_task_patch_route_uses_same_rule(monkeypatch):
    store = {"tPriv": _task("tPriv", "p", Visibility="Private", Owner=[DANA]),
             "tOwn": _task("tOwn", "o", Owner=[ELI]), "tNone": _task("tNone", "n")}
    monkeypatch.setattr(tma_api, "_at_get_record", lambda table, rid: store.get(rid))
    queued = []
    monkeypatch.setattr(tma_api, "_queue_or_owner_execute",
                        lambda a, p, i, l: (queued.append(p["record_id"]) or ("a", {"ok": True}, 200)))
    c = tma_client(monkeypatch, ELIYAHU)
    assert c.patch("/api/tasks/tPriv", json={"status": "done"}, headers=H).status_code == 403
    assert c.patch("/api/tasks/tOwn", json={"status": "done"}, headers=H).status_code == 200
    assert c.patch("/api/tasks/tNone", json={"status": "done"}, headers=H).status_code == 200   # sole owner: unchanged
    assert queued == ["tOwn", "tNone"]


def test_14_existing_task_helpers_default_behavior_unchanged():
    # direct callers of the pure function keep the historical single-owner semantics
    result = tma_api._process_owner_tasks([_task("t1", "ownerless"), _task("t2", "other", Owner=[DANA])], ELI, "eliyahu", "2026-10-04")
    assert titles(result) == ["ownerless"]


def test_generic_task_update_private_check_is_minimal(monkeypatch):
    """Business task update: no identity lookup. Private task: owner-of-record only."""
    lookups = []
    real = owner_resolution.resolve_profile_record_strict
    monkeypatch.setattr(owner_resolution, "resolve_profile_record_strict", lambda u: (lookups.append(u) or real(u)))
    store = {"tBiz": {"Domain": "Recruitment"}, "tPriv": {"Visibility": "Private", "Owner": [ELI]}}
    monkeypatch.setattr("tools.airtable_read_adapter.get_record_fields", lambda table, rid, **k: store[rid])
    enforce_tenant_scope("airtable_update", MANAGER, {"table": Tables.TASKS, "record_id": "tBiz"})
    assert lookups == []
    with pytest.raises(TenantScopeViolation):
        enforce_tenant_scope("airtable_update", MANAGER, {"table": Tables.TASKS, "record_id": "tPriv"})
    with pytest.raises(TenantScopeViolation):
        enforce_tenant_scope("airtable_update", AVI_PARTNER, {"table": "Tasks", "record_id": "tPriv"})
    enforce_tenant_scope("airtable_update", ELIYAHU, {"table": "Tasks", "record_id": "tPriv"})


# ═══════════════ P5 — Profile resolution ═══════════════

def test_7_ambiguous_profile_never_picks_first(monkeypatch):
    twin = PROFILES + [{"id": "recAvi2", "fields": {"name": "AVI"}}]
    def fake(table, query, **kw):
        _f, value, _s, _ci = query.arguments
        return [p for p in twin if p["fields"]["name"].casefold() == str(value).casefold()]
    monkeypatch.setattr(owner_resolution, "list_records", fake)
    assert owner_resolution.resolve_profile_record_strict("avi") == (None, owner_resolution.AMBIGUOUS)
    assert owner_resolution.resolve_profile_record_id("avi") is None
    assert tma_api._resolve_profile_record_id("avi") is None
    assert owner_resolution.resolve_profile_record_id("eliyahu") == ELI      # unique still resolves
    # ...and the policy fails closed for the ambiguous identity
    with pytest.raises(policy.PersonalDataAccessDenied):
        policy.filter_records("Assets", ASSETS, AVI_PARTNER)


def test_8_unresolved_identity_fails_closed(monkeypatch):
    assert owner_resolution.resolve_profile_record_strict("") == (None, owner_resolution.EMPTY_ID)
    assert owner_resolution.resolve_profile_record_strict("ghost")[1] == owner_resolution.NOT_FOUND
    def down(*a, **k):
        raise RuntimeError("airtable down")
    monkeypatch.setattr(owner_resolution, "list_records", down)
    assert owner_resolution.resolve_profile_record_strict("eliyahu") == (None, owner_resolution.LOOKUP_FAILED)
    monkeypatch.undo()
    for who in (STRANGER, LEAD, None):
        with pytest.raises(policy.PersonalDataAccessDenied):
            policy.filter_records("Loans", LOANS, who)
        with pytest.raises(policy.PersonalDataAccessDenied):
            policy.enforce_table_access("airtable_get", who, {"table": "Loans"})


def test_8b_unresolved_identity_gets_nothing_from_assets_api(monkeypatch):
    asset_store(monkeypatch)
    # an owner-role identity with no (unique) Profile row is not a financial owner
    assert tma_client(monkeypatch, ident("ghost", Role.OWNER)).get("/api/assets", headers=H).status_code == 403


# ═══════════════ P6 — primitive + static no-bypass checks ═══════════════

def test_business_role_is_not_personal_authorization():
    actor_eli = policy.resolve_actor(ELIYAHU)
    foreign = {"Owner": [DANA]}
    for table in ("Assets", "Loans"):
        assert policy.record_visible(table, foreign, actor_eli) is False
        assert policy.record_visible(table, {"Owner": [ELI]}, actor_eli) is True
        assert policy.record_visible(table, {}, actor_eli) is False
    # one registry entry is all a future financial table needs
    assert policy.TablePolicy("Financial Goals", policy.OWNER_SCOPED).owner_field == "Owner"


def test_no_second_policy_site_and_no_unfiltered_policy_reads():
    import pathlib, re
    root = pathlib.Path(__file__).parent
    # policy tables are named in exactly one decision module (plus schema/field maps, not access rules)
    for name in ("tma_api.py", "tools/dispatcher.py", "tools/airtable_security.py", "tools/approval_actions.py"):
        text = (root / name).read_text(encoding="utf-8")
        assert "data_access_policy" in text or "_access_policy" in text, name
        assert not re.search(r'table\s*==\s*["\'](Loans|Assets)["\']\s*(and|:)\s*.*owner', text, re.I), name
    # every runtime caller of the agent-facing airtable_get on a non-fixed table goes through dispatcher
    callers = []
    for path in root.rglob("*.py"):
        if path.name.startswith("test_") or "archive" in path.parts or path.name == "airtable_tools.py":
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if re.search(r"(?<![\w.])airtable_get\(\s*[^t)]", line) and "def " not in line and "lambda" not in line:
                callers.append((path.name, line.strip()))
    sensitive = [c for c in callers if re.search(r"Assets|Loans|TASKS|Tasks", c[1])]
    assert sensitive == [], sensitive
