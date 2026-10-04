"""Private Financial Control Center: isolation, dynamic target, event semantics,
free-text writer (plan only — execution goes through ActionGateway/tma_write).
In-memory Airtable fakes; no network."""

from __future__ import annotations

import os

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-fcc-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:FCC_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patFccTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appFccTest")
os.environ.setdefault("ELIYAHU_CHAT_ID", "1")

from datetime import date

import pytest

import identity as identity_module
from airtable_schema import FinEventFields as EF, FinGoalFields as GF, TaskFields, Tables
from core import data_access_policy as policy
from core import owner_resolution
from core.financial_control import calc, service, writer
from identity import Domain, Identity, Role
from tools import approval_actions
from tools import dispatcher as dispatcher_module
from tools.airtable_security import TenantScopeViolation, enforce_tenant_scope

ELI, AVI = "recEli", "recAvi"
PROFILES = [{"id": ELI, "fields": {"name": "Eliyahu"}}, {"id": AVI, "fields": {"name": "Avi"}}]


def ident(uid, role):
    return Identity(user_id=uid, role=role, display_name=uid, tenant_id="boss_hq", domain_id=Domain.GENERAL,
                    allowed_domains=[], channel="telegram", external_id=f"tg-{uid}")


ELIYAHU, AVI_I = ident("eliyahu", Role.OWNER), ident("avi", Role.PARTNER)
TODAY = date(2026, 10, 8)    # Thursday; Oct has 31 days


def goal(gid, title, owner, target=12000, **extra):
    f = {GF.TITLE: title, GF.STATUS: "active", GF.PERIOD_TYPE: "monthly", GF.TARGET_AMOUNT: target,
         GF.CALC_METHOD: "period_sum", GF.FINANCIAL_OWNER: [owner]}
    f.update(extra)
    return {"id": gid, "fields": f}


def event(eid, gid, owner, amount, kind="one_time", day="2026-10-02", key=None, **extra):
    f = {EF.GOAL: [gid], EF.AMOUNT: amount, EF.KIND: kind, EF.OCCURRED_AT: day, EF.FINANCIAL_OWNER: [owner]}
    if key:
        f[EF.IDEMPOTENCY_KEY] = key
    f.update(extra)
    return {"id": eid, "fields": f}


DB: dict = {}


@pytest.fixture(autouse=True)
def fakes(monkeypatch):
    DB.clear()
    DB.update({
        Tables.FIN_GOALS: [goal("recGE", "הכנסה נוספת", ELI), goal("recGA", "הכנסה של אבי", AVI, 99000)],
        Tables.FIN_EVENTS: [event("recEE", "recGE", ELI, 2000), event("recEA", "recGA", AVI, 55555)],
        Tables.TASKS: [],
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
    monkeypatch.setattr(service, "_record_fields", lambda table, rid: next(
        r["fields"] for r in DB[table] if r["id"] == rid))
    import tools.airtable_read_adapter as adapter
    monkeypatch.setattr(adapter, "get_record_fields", lambda table, rid: next(
        r["fields"] for r in DB[table] if r["id"] == rid))


def cls(**kw):
    return {"action": "log_progress", "goal_hint": "הכנסה נוספת", **kw}


# 1/5 — A cannot read B's goals; aggregates exclude B
def test_1_5_read_and_aggregates_exclude_other_owner():
    view = service.overview(ELIYAHU, TODAY)
    assert [g["goal_id"] for g in view["goals"]] == ["recGE"]
    assert "55555" not in str(view) and "99000" not in str(view)
    assert [g["goal_id"] for g in service.overview(AVI_I, TODAY)["goals"]] == ["recGA"]


# 2 — A cannot update B's goal (generic tool + tma_write re-check)
def test_2_update_foreign_goal_denied(monkeypatch):
    with pytest.raises(TenantScopeViolation):
        enforce_tenant_scope("airtable_update", ELIYAHU, {"table": Tables.FIN_GOALS, "record_id": "recGA", "fields": {}})
    _f, denied = approval_actions._enforce_personal_data_policy("patch", Tables.FIN_GOALS, "recGA", {}, ELIYAHU)
    assert denied is not None and denied["ok"] is False


# 3 — A cannot create progress on B's goal
def test_3_progress_on_foreign_goal_denied():
    fields = {EF.GOAL: ["recGA"], EF.AMOUNT: 10, EF.KIND: "one_time"}
    with pytest.raises(policy.PersonalDataAccessDenied):
        policy.scope_new_record_fields(Tables.FIN_EVENTS, fields, ELIYAHU)
    _f, denied = approval_actions._enforce_personal_data_policy("post", Tables.FIN_EVENTS, "", fields, ELIYAHU)
    assert denied is not None
    ok = policy.scope_new_record_fields(Tables.FIN_EVENTS, {**fields, EF.GOAL: ["recGE"]}, ELIYAHU)
    assert ok[EF.FINANCIAL_OWNER] == [ELI]


# 4 — free text / search cannot resolve B's goal
def test_4_free_text_never_resolves_other_owner_goal():
    out = writer.plan("הכנסה של אבי 100", cls(goal_hint="הכנסה של אבי", amount=100), ELIYAHU, TODAY)
    assert out["status"] == "needs_goal" and all(c["goal_id"] != "recGA" for c in out["candidates"])
    forced = writer.plan("x", cls(amount=1), ELIYAHU, TODAY, goal_id="recGA")
    assert forced["status"] == "denied"


# 6 — task from goal inherits owner
def test_6_followup_task_inherits_owner():
    out = writer.plan("דיברתי עם הבנק", {"action": "follow_up", "goal_hint": "הכנסה נוספת", "task_title": "להשיג יתרות"},
                      ELIYAHU, TODAY)
    task = [p for p in out["proposals"] if p["table"] == Tables.TASKS][0]
    assert task["fields"][TaskFields.OWNER] == [ELI] and "[FCC:recGE]" in task["fields"][TaskFields.DESCRIPTION]
    assert task["fields"][TaskFields.TOPIC] == "כספים"          # identifiable as FCC-origin, no new schema


# 7/8 — dynamic target
def test_7_8_dynamic_target_under_and_over_performance():
    g = goal("g", "t", ELI, 12000)
    weeks = calc.weeks_left(TODAY, date(2026, 10, 31))
    base = calc.compute_goal(g, [], TODAY, GF)
    assert base["dynamic_target_per_week"] == round(12000 / weeks, 2)
    under = calc.compute_goal(g, [calc.Event("one_time", 500, date(2026, 10, 3))], TODAY, GF)
    over = calc.compute_goal(g, [calc.Event("one_time", 9000, date(2026, 10, 3))], TODAY, GF)
    assert under["dynamic_target_per_week"] > over["dynamic_target_per_week"]
    assert under["remaining"] == 11500 and over["remaining"] == 3000


# 9 — mid-period target change keeps events
def test_9_target_change_keeps_progress():
    g = goal("g", "t", ELI, 12000)
    evs = [calc.Event("one_time", 2000, date(2026, 10, 2)), calc.Event("target_change", 18000, date(2026, 10, 5))]
    r = calc.compute_goal(g, evs, TODAY, GF)
    assert r["target"] == 18000 and r["actual"] == 2000 and r["remaining"] == 16000
    assert calc.compute_goal(g, evs, date(2026, 10, 4), GF)["target"] == 12000   # history intact


# 10 — rename patches title only; events keep the goal id
def test_10_rename_keeps_links():
    out = writer.plan("שנה שם", {"action": "rename_goal", "goal_hint": "הכנסה נוספת", "new_title": "הכנסה שוטפת"},
                      ELIYAHU, TODAY)
    p = out["proposals"][0]
    assert p["op"] == "patch" and p["record_id"] == "recGE" and list(p["fields"]) == [GF.TITLE]


# 11 — idempotency
def test_11_duplicate_free_text_not_written_twice():
    first = writer.plan("העברתי 5000", cls(amount=5000), ELIYAHU, TODAY)
    assert first["status"] == "preview"
    key = first["proposals"][0]["fields"][EF.IDEMPOTENCY_KEY]
    DB[Tables.FIN_EVENTS].append(event("recNew", "recGE", ELI, 5000, key=key))
    assert writer.plan("העברתי 5000", cls(amount=5000), ELIYAHU, TODAY)["status"] == "duplicate"


# 12 — ambiguity not resolved by invention
def test_12_ambiguity_returns_candidates():
    DB[Tables.FIN_GOALS].append(goal("recG2", "חיסכון קבוע", ELI))
    DB[Tables.FIN_GOALS].append(goal("recG3", "חיסכון לילדים", ELI))
    out = writer.plan("הפקדתי 5000", cls(goal_hint="חיסכון", amount=5000), ELIYAHU, TODAY)
    assert out["status"] == "needs_goal" and {c["goal_id"] for c in out["candidates"]} == {"recG2", "recG3"}
    assert "proposals" not in out


# 13 — missing amount -> follow-up task, no invented number; open duplicate deduped
def test_13_missing_data_becomes_followup_and_dedupes():
    out = writer.plan("שמתי כסף", cls(), ELIYAHU, TODAY)
    assert out["status"] == "preview" and out["proposals"][0]["table"] == Tables.TASKS
    title = out["proposals"][0]["fields"][TaskFields.NAME]
    DB[Tables.TASKS].append({"id": "recT", "fields": {
        TaskFields.NAME: title, TaskFields.STATUS: "ממתין", TaskFields.OWNER: [ELI],
        TaskFields.DESCRIPTION: "[FCC:recGE] x"}})
    assert writer.plan("שמתי כסף", cls(), ELIYAHU, TODAY)["proposals"] == []


# 14/15 — writer is plan-only, no direct write calls in the feature package
def test_14_15_no_direct_writes_in_feature_code():
    import pathlib
    src = "".join(p.read_text() for p in pathlib.Path("core/financial_control").glob("*.py"))
    for forbidden in ("airtable_create", "airtable_patch", "requests.", "airtable_tools", "import crm", "urlopen"):
        assert forbidden not in src
    assert "Financial Goals" in approval_actions._TMA_WRITE_ALLOWED_TABLES


# 16 — unresolved identity fails closed
def test_16_unauthorized_identity_fails_closed():
    stranger = ident("nobody", Role.MANAGER)
    with pytest.raises(policy.PersonalDataAccessDenied):
        service.overview(stranger, TODAY)
    assert writer.plan("x", cls(amount=1), stranger, TODAY)["status"] == "denied"
    assert writer.plan("x", cls(amount=1), None, TODAY)["status"] == "denied"


# 17 — generic agent tools cannot bypass (raw id, other owner's table)
def test_17_generic_tools_blocked_for_foreign_rows(monkeypatch):
    from tools import airtable_tools
    monkeypatch.setattr(airtable_tools, "airtable_get_records", lambda t, f="", max_records=None: list(DB[t]))
    monkeypatch.setattr(dispatcher_module._ff, "is_enabled", lambda *a, **k: False)
    out = dispatcher_module.dispatch_tool("airtable_get", {"table": Tables.FIN_EVENTS}, ELIYAHU)
    assert "55555" not in out and "2000" in out
    with pytest.raises(TenantScopeViolation):
        enforce_tenant_scope("airtable_get", ELIYAHU, {"table": "tblABCDEFGHIJKLMN"})


# monthly_recurring is never blended into one-time totals
def test_recurring_not_blended():
    g = goal("g", "t", ELI, 1000)
    evs = [calc.Event("one_time", 100, date(2026, 10, 3)), calc.Event("monthly_recurring", 750, date(2026, 10, 3))]
    assert calc.compute_goal(g, evs, TODAY, GF)["actual"] == 100
    assert calc.monthly_cash_improvement(evs, TODAY) == 750


# live FCC table ids (created 04/10/2026): the raw id never bypasses the owner policy
def test_raw_live_table_ids_denied_for_every_role():
    for raw in ("tblQPUteMKe13tvlr", "tblqNvcyK34zVjcXP"):
        assert policy.is_raw_table_id(raw)
        for who in (ELIYAHU, AVI_I):
            with pytest.raises(TenantScopeViolation):
                enforce_tenant_scope("airtable_get", who, {"table": raw})
    for name in (Tables.FIN_GOALS, "financial goals", " Financial Progress Events "):
        assert policy.is_owner_scoped(name)


def test_schema_cache_matches_code_constants():
    import json
    from airtable_schema import FinEventFields, FinGoalFields
    cache = json.load(open("schema_cache.json"))["tables"]
    for table, cls_ in ((Tables.FIN_GOALS, FinGoalFields), (Tables.FIN_EVENTS, FinEventFields)):
        names = {v for k, v in vars(cls_).items() if not k.startswith("_")}
        assert names <= set(cache[table])


# ═══ HTTP layer (/api/fcc/*): flag gate, isolation, canonical write path ═══
from flask import Flask
import tma_api
from core.financial_control import classifier

H = {"X-Telegram-Init-Data": "valid"}


def http(monkeypatch, who, flag=True):
    app = Flask(__name__)
    app.register_blueprint(tma_api.tma_api)
    monkeypatch.setattr(tma_api, "_validate_initdata", lambda _: {"id": who.user_id})
    monkeypatch.setattr(tma_api, "resolve_identity", lambda *_: who)
    monkeypatch.setattr(tma_api, "_fcc_enabled", lambda: flag)
    return app.test_client()


def test_http_flag_off_is_404(monkeypatch):
    c = http(monkeypatch, ELIYAHU, flag=False)
    assert c.get("/api/fcc/overview", headers=H).status_code == 404
    assert c.post("/api/fcc/write", json={"text": "x"}, headers=H).status_code == 404


def test_http_overview_isolated_per_owner(monkeypatch):
    body = http(monkeypatch, ELIYAHU).get("/api/fcc/overview", headers=H).get_json()
    assert [g["goal_id"] for g in body["goals"]] == ["recGE"] and "99000" not in str(body)
    body = http(monkeypatch, AVI_I).get("/api/fcc/overview", headers=H).get_json()
    assert [g["goal_id"] for g in body["goals"]] == ["recGA"] and "2000" not in str(body["goals"])


def test_http_unresolved_identity_403(monkeypatch):
    assert http(monkeypatch, ident("nobody", Role.MANAGER)).get("/api/fcc/overview", headers=H).status_code == 403


def test_http_write_preview_then_confirm_uses_canonical_path(monkeypatch):
    calls = []
    monkeypatch.setattr(classifier, "classify", lambda text, titles: {"action": "log_progress", "goal_hint": "הכנסה נוספת", "amount": 500})
    monkeypatch.setattr(tma_api, "_queue_or_owner_execute", lambda action, payload, identity, label: (calls.append((action, payload)) or ("a1", {"ok": True}, 200)))
    c = http(monkeypatch, ELIYAHU)
    prev = c.post("/api/fcc/write", json={"text": "הכנסה 500"}, headers=H).get_json()
    assert prev["status"] == "preview" and calls == []                      # preview never writes
    done = c.post("/api/fcc/write", json={"text": "הכנסה 500", "confirm": True}, headers=H).get_json()
    assert done["status"] == "executed" and [a for a, _ in calls] == ["tma_fcc_write"]
    assert calls[0][1]["table"] == Tables.FIN_EVENTS


def test_http_ambiguous_does_not_write(monkeypatch):
    DB[Tables.FIN_GOALS] += [goal("recG2", "חיסכון קבוע", ELI), goal("recG3", "קרן חירום", ELI)]
    monkeypatch.setattr(classifier, "classify", lambda t, titles: {"action": "log_progress", "goal_hint": "", "amount": 5000})
    monkeypatch.setattr(tma_api, "_queue_or_owner_execute", lambda *a, **k: pytest.fail("must not write"))
    out = http(monkeypatch, ELIYAHU).post("/api/fcc/write", json={"text": "הפקדתי 5000 לחיסכון", "confirm": True}, headers=H).get_json()
    assert out["status"] == "needs_goal" and len(out["candidates"]) >= 2
