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


# 7/8 — dynamic target
def test_7_8_dynamic_target_under_and_over_performance():
    g = goal("g", "t", ELI, 12000)
    base = calc.compute_goal(g, [], TODAY, GF)
    assert base["dynamic_target_per_week"] == round(12000 / 24 * 7, 2)     # 24 calendar days left on 8/10 (31-day month)
    under = calc.compute_goal(g, [calc.Event("one_time", 500, date(2026, 10, 3))], TODAY, GF)
    over = calc.compute_goal(g, [calc.Event("one_time", 9000, date(2026, 10, 3))], TODAY, GF)
    assert under["dynamic_target_per_week"] > over["dynamic_target_per_week"]
    assert under["remaining"] == 11500 and over["remaining"] == 3000


# monthly goal -> weekly pace by real calendar days (not whole weeks)
@pytest.mark.parametrize("today,days", [
    (date(2026, 2, 1), 28), (date(2026, 4, 1), 30), (date(2026, 10, 1), 31),    # month start: 28/30/31
    (date(2026, 10, 16), 16), (date(2026, 10, 25), 7),                          # mid month, exactly one week left
])
def test_monthly_pace_uses_calendar_days(today, days):
    r = calc.compute_goal(goal("g", "t", ELI, 15000), [], today, GF)
    assert r["dynamic_target_per_week"] == round(15000 / days * min(7, days), 2)


def test_monthly_pace_last_days_is_partial_week_and_never_exceeds_remaining():
    r = calc.compute_goal(goal("g", "t", ELI, 15000), [calc.Event("one_time", 12000, date(2026, 10, 5))], date(2026, 10, 29), GF)
    assert r["dynamic_target_per_week"] == round(3000 / 3 * 3, 2) == 3000.0       # 3 days left: the whole remainder
    last = calc.compute_goal(goal("g", "t", ELI, 15000), [], date(2026, 10, 31), GF)
    assert last["dynamic_target_per_week"] == 15000.0                             # last day: all of it


def test_monthly_pace_resets_on_new_month_and_follows_performance():
    g = goal("g", "t", ELI, 15000)
    oct_ev = [calc.Event("one_time", 14000, date(2026, 10, 20))]
    assert calc.compute_goal(g, oct_ev, date(2026, 11, 1), GF)["actual"] == 0      # parent resets on the 1st
    ev9 = [calc.Event("one_time", 9000, date(2026, 10, 3))]
    none = calc.compute_goal(g, [], TODAY, GF)["dynamic_target_per_week"]
    assert calc.compute_goal(g, ev9, TODAY, GF)["dynamic_target_per_week"] < none          # over-performance lowers the pace
    assert calc.compute_goal(g, [], date(2026, 10, 22), GF)["dynamic_target_per_week"] > none   # nothing earned => pace rises


def test_weekly_goal_resets_on_sunday():
    g = goal("g", "t", ELI, 2500, **{GF.PERIOD_TYPE: "weekly"})
    ev = [calc.Event("one_time", 1000, date(2026, 10, 10))]                      # Saturday
    assert calc.compute_goal(g, ev, date(2026, 10, 10), GF)["actual"] == 1000
    assert calc.compute_goal(g, ev, date(2026, 10, 11), GF)["actual"] == 0       # Sunday: new week


# 9 — mid-period target change keeps events
def test_9_target_change_keeps_progress():
    g = goal("g", "t", ELI, 12000)
    evs = [calc.Event("one_time", 2000, date(2026, 10, 2)), calc.Event("target_change", 18000, date(2026, 10, 5))]
    r = calc.compute_goal(g, evs, TODAY, GF)
    assert r["target"] == 18000 and r["actual"] == 2000 and r["remaining"] == 16000
    assert calc.compute_goal(g, evs, date(2026, 10, 4), GF)["target"] == 12000   # history intact


# 14/15 — writer is plan-only, no direct write calls in the feature package
def test_14_15_no_direct_writes_in_feature_code():
    import pathlib
    src = "".join(p.read_text() for p in pathlib.Path("core/financial_control").glob("*.py"))
    for forbidden in ("airtable_create", "airtable_patch", "requests.", "airtable_tools", "import crm", "urlopen"):
        assert forbidden not in src
    assert "Financial Goals" in approval_actions._TMA_WRITE_ALLOWED_TABLES


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
    monkeypatch.setattr(tma_api, "_fcc_enabled", lambda identity=None: flag)
    return app.test_client()


# ═══ Income hierarchy: parent goal + source/sub-goal (explicit "Contributes To" link) ═══
def hierarchy(events):
    DB[Tables.FIN_GOALS] = [
        goal("recP", "הכנסה חודשית כוללת", ELI, 15000, **{GF.CATEGORY: "income"}),
        goal("recT", "הכנסה מנסיעות", ELI, 2500, **{GF.CATEGORY: "income", GF.PERIOD_TYPE: "weekly", GF.PARENT_GOAL: ["recP"]}),
    ]
    DB[Tables.FIN_EVENTS] = events


def rows_of(view):
    return {g["goal_id"]: g for g in view["goals"]}


def test_source_target_does_not_inflate_parent_target():
    hierarchy([])
    view = service.overview(ELIYAHU, TODAY)
    card = view["summary"]["income"]
    assert card["target"] == 15000 and card["goals"] == 1            # not 17,500
    assert rows_of(view)["recT"]["is_source"] and rows_of(view)["recT"]["parent_id"] == "recP"


def test_source_event_rolls_up_into_parent_actual_once():
    both = event("recX", "recT", ELI, 300, day="2026-10-07")
    both["fields"][EF.GOAL] = ["recT", "recP"]                     # same event linked to source AND parent
    hierarchy([event("recA", "recT", ELI, 1000, day="2026-10-06"), event("recB", "recP", ELI, 500, day="2026-10-02"), both])
    view = service.overview(ELIYAHU, TODAY)
    rows = rows_of(view)
    assert rows["recT"]["actual"] == 1300                           # the source keeps its own events
    assert rows["recP"]["actual"] == 1800 == view["summary"]["income"]["actual"]    # 1000 + 500 + 300, no double count


def test_source_target_change_never_moves_parent_target():
    hierarchy([event("recC", "recT", ELI, 4000, kind="target_change", day="2026-10-05")])
    rows = rows_of(service.overview(ELIYAHU, TODAY))
    assert rows["recT"]["target"] == 4000 and rows["recP"]["target"] == 15000


def test_weekly_source_resets_sunday_parent_resets_month():
    hierarchy([event("recA", "recT", ELI, 1000, day="2026-10-03")])     # Saturday of the previous week
    rows = rows_of(service.overview(ELIYAHU, TODAY))                     # Thursday 8/10: new week since Sun 4/10
    assert rows["recT"]["actual"] == 0 and rows["recP"]["actual"] == 1000
    nov = rows_of(service.overview(ELIYAHU, date(2026, 11, 1)))
    assert nov["recP"]["actual"] == 0


def test_weekly_breakdown_travel_minimum_and_other_sources():
    hierarchy([event("recA", "recT", ELI, 1000, day="2026-10-06")])
    row = rows_of(service.overview(ELIYAHU, TODAY))["recP"]
    pace = round(14000 / 24 * 7, 2)                                     # 4083.33
    assert row["dynamic_target_per_week"] == pace
    assert row["weekly_sources_required"] == 1500                        # travel still owes 2500 - 1000 this week
    assert row["other_sources_needed"] == round(pace - 1500, 2)
    card = service.overview(ELIYAHU, TODAY)["summary"]["income"]
    assert card["other_sources_needed"] == row["other_sources_needed"] and card["sources"][0]["goal_id"] == "recT"


def test_other_sources_never_negative_when_travel_exceeds_pace():
    hierarchy([event("recA", "recP", ELI, 14000, day="2026-10-02")])     # parent almost done, pace small
    row = rows_of(service.overview(ELIYAHU, TODAY))["recP"]
    assert row["other_sources_needed"] == 0.0


def test_parent_link_cycle_and_foreign_parent_are_ignored():
    hierarchy([])
    DB[Tables.FIN_GOALS][0]["fields"][GF.PARENT_GOAL] = ["recT"]           # recP -> recT -> recP
    view = service.overview(ELIYAHU, TODAY)
    assert view["summary"]["income"]["goals"] == 2                        # cycle dropped: both stand alone
    DB[Tables.FIN_GOALS][0]["fields"].pop(GF.PARENT_GOAL)
    DB[Tables.FIN_GOALS][1]["fields"][GF.PARENT_GOAL] = ["recGA"]         # not an active goal of this owner
    assert not rows_of(service.overview(ELIYAHU, TODAY))["recT"]["is_source"]


# ═══ Gross -> direct costs -> net (event kind direct_cost; no new table) ═══
def test_direct_cost_keeps_gross_actual_but_net_drives_remaining():
    g = goal("g", "t", ELI, 15000)
    evs = [calc.Event("one_time", 3000, date(2026, 10, 6)), calc.Event("direct_cost", 380, date(2026, 10, 6)),
           calc.Event("direct_cost", 120, date(2026, 10, 7))]
    r = calc.compute_goal(g, evs, TODAY, GF)
    assert (r["actual"], r["direct_costs"], r["net"]) == (3000, 500, 2500)
    assert r["remaining"] == 12500                                   # progress vs target is net


def test_direct_cost_respects_period_and_superseded_and_other_months():
    g = goal("g", "t", ELI, 15000)
    evs = [calc.Event("direct_cost", 100, date(2026, 9, 30)), calc.Event("direct_cost", 50, date(2026, 10, 2), superseded=True),
           calc.Event("direct_cost", 70, date(2026, 10, 2))]
    assert calc.compute_goal(g, evs, TODAY, GF)["direct_costs"] == 70


def test_direct_cost_on_source_rolls_up_into_parent_net_once():
    hierarchy([event("recA", "recT", ELI, 3000, day="2026-10-06"),
               event("recF", "recT", ELI, 380, kind="direct_cost", day="2026-10-06"),
               event("recG", "recT", ELI, 120, kind="direct_cost", day="2026-10-07")])
    view = service.overview(ELIYAHU, TODAY)
    rows = rows_of(view)
    assert (rows["recT"]["actual"], rows["recT"]["direct_costs"], rows["recT"]["net"]) == (3000, 500, 2500)
    assert (rows["recP"]["actual"], rows["recP"]["net"]) == (3000, 2500)
    card = view["summary"]["income"]
    assert (card["actual"], card["direct_costs"], card["net"]) == (3000, 500, 2500)    # source not added twice
    src = next(x for x in card["sources"] if x["goal_id"] == "recT")
    assert (src["direct_costs"], src["net"]) == (500, 2500)                            # weekly breakdown shows costs too


def test_direct_cost_kind_is_accepted_by_draft_and_classifier_validation():
    assert "direct_cost" in fd.EVENT_KINDS and fd.VALUE_LABELS["kind"]["direct_cost"]
    from core.financial_control import writer as w
    assert w.validate_intent({"action": "log_progress", "goal_hint": "נסיעות", "amount": 380, "kind": "direct_cost"})["kind"] == "direct_cost"
    assert w.validate_intent({"action": "log_progress", "goal_hint": "x", "amount": 1, "kind": "bogus"}) is None


def test_project_rows_have_no_cost_fields():
    DB[Tables.FIN_GOALS] = [goal("recPr", "פרויקט", ELI, None, **{GF.CATEGORY: "project"})]
    DB[Tables.FIN_EVENTS] = []
    row = service.overview(ELIYAHU, TODAY)["goals"][0]
    assert row["mode"] == "project" and row["direct_costs"] is None and row["net"] is None


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


# ═══ Slice 2: header summary + FCC tasks (owner-only) ═══
def test_summary_by_category_and_owner_isolation():
    DB[Tables.FIN_GOALS] = [
        goal("recGE", "הכנסה נוספת", ELI, 12000, **{GF.CATEGORY: "income"}),
        goal("recGS", "חיסכון קבוע", ELI, 3000, **{GF.CATEGORY: "savings", GF.CALC_METHOD: "cumulative"}),
        goal("recGA", "של אבי", AVI, 99000, **{GF.CATEGORY: "income"}),
    ]
    DB[Tables.FIN_EVENTS] = [event("e1", "recGE", ELI, 2000), event("e2", "recGA", AVI, 55555)]
    eli = service.overview(ELIYAHU, TODAY)["summary"]
    assert eli["income"]["target"] == 12000 and eli["income"]["actual"] == 2000
    assert eli["savings"]["target"] == 3000 and "debt" not in eli
    assert "99000" not in str(eli) and "55555" not in str(eli)


def test_fcc_tasks_only_owner_open_topic_and_tag():
    mk = lambda tid, owner, status="ממתין", topic="כספים", desc="[FCC:recGE] x": {"id": tid, "fields": {
        TaskFields.NAME: tid, TaskFields.STATUS: status, TaskFields.OWNER: [owner],
        TaskFields.TOPIC: topic, TaskFields.DESCRIPTION: desc}}
    DB[Tables.TASKS] = [mk("mine", ELI), mk("avi", AVI), mk("done", ELI, status="בוצע"),
                        mk("othertopic", ELI, topic="שיווק"), mk("notag", ELI, desc="plain")]
    assert [t["title"] for t in service.overview(ELIYAHU, TODAY)["tasks"]] == ["mine"]
    assert [t["title"] for t in service.overview(AVI_I, TODAY)["tasks"]] == ["avi"]


# ═══ Canary: flag + FCC_CANARY_USER_IDS allowlist (fail closed) ═══
def test_canary_allowlist_fail_closed(monkeypatch):
    import feature_flags
    monkeypatch.setattr(feature_flags, "is_enabled", lambda n, *a, **k: n == "FEATURE_FINANCIAL_CONTROL_CENTER")
    monkeypatch.delenv("FCC_CANARY_USER_IDS", raising=False)
    assert tma_api._fcc_enabled(ELIYAHU) is False                 # flag on, no allowlist -> nobody
    monkeypatch.setenv("FCC_CANARY_USER_IDS", " Eliyahu ")
    assert tma_api._fcc_enabled(ELIYAHU) is True
    assert tma_api._fcc_enabled(AVI_I) is False                   # partner stays out
    assert tma_api._fcc_enabled(None) is False
    monkeypatch.setattr(feature_flags, "is_enabled", lambda *a, **k: False)
    assert tma_api._fcc_enabled(ELIYAHU) is False                 # flag off wins


def test_canary_http_other_user_gets_404(monkeypatch):
    import feature_flags
    monkeypatch.setattr(feature_flags, "is_enabled", lambda n, *a, **k: n == "FEATURE_FINANCIAL_CONTROL_CENTER")
    monkeypatch.setenv("FCC_CANARY_USER_IDS", "eliyahu")
    app = Flask(__name__)
    app.register_blueprint(tma_api.tma_api)
    monkeypatch.setattr(tma_api, "_validate_initdata", lambda _: {"id": "x"})
    for who, code in ((ELIYAHU, 200), (AVI_I, 404)):
        monkeypatch.setattr(tma_api, "resolve_identity", lambda *_, w=who: w)
        assert app.test_client().get("/api/fcc/overview", headers=H).status_code == code



# ═══════════════ FCC Diamond completion: one draft primitive for TMA + chat ═══════════════
import core.business_draft as bd
import session_store as ss_mod
from core.draft_flow import DRAFT_TTL_SECONDS
from core.financial_control import chat as fchat, conversation as conv, draft as fd
from session_store import PersistentSessionStore


@pytest.fixture(autouse=True)
def mem_store(monkeypatch):
    """Real PersistentSessionStore (CAS/TTL/identity binding), RAM only: no Airtable I/O."""
    store = PersistentSessionStore()
    monkeypatch.setattr(PersistentSessionStore, "_sync_to_db", lambda self, sender, session, is_new=False: True)
    monkeypatch.setattr(PersistentSessionStore, "_load_from_db", lambda self, sender, channel="": None)
    monkeypatch.setattr(ss_mod, "lead_sessions", store)
    return store


class Ex:
    """Scripted extractor (stands in for the LLM). Fails loudly if used while ``locked``."""

    def __init__(self, classify=None, fill=None):
        self.c, self.f, self.calls, self.locked = classify or {}, fill or {}, [], False

    def classify(self, text, titles, today):
        assert not self.locked, "classifier called after confirm"
        self.calls.append(("classify", text))
        return self.c.get(text)

    def fill(self, text, awaiting, fields, entity, today):
        assert not self.locked, "extractor called after confirm"
        self.calls.append(("fill", text))
        return self.f.get(text, {})


def run(ex, who, text, **kw):
    return conv.handle_turn(who, text, extractor=ex, today=TODAY, **kw)


EF_GOAL = {"action": "create_goal", "title": "קרן חירום", "category": "emergency_fund"}


def eli_goal_writes(result):
    return result.snapshot["writes"]


# 1 + 2 + 5 + 6 + 12 — multi-turn create, persisted between messages, only missing fields asked
def test_create_goal_multi_turn_persists_state_and_asks_only_missing():
    ex = Ex(classify={"תוסיף יעד קרן חירום": EF_GOAL}, fill={"סוף השנה": {"end_date": "2026-12-31"}})
    r1 = run(ex, ELIYAHU, "תוסיף יעד קרן חירום")
    assert r1.state == "ask" and r1.awaiting == "target_amount" and "סכום היעד" in r1.message
    r2 = run(ex, ELIYAHU, "60000")                                   # known fields are not asked again
    assert r2.state == "ask" and r2.awaiting == "end_date" and "₪60,000" in r2.message
    r3 = run(ex, ELIYAHU, "סוף השנה")
    assert r3.state == "review"
    for expected in ("קרן חירום", "₪60,000", "מצטבר", "31/12/2026", "אשר ורשום / ערוך / בטל"):
        assert expected in r3.message                                # full final business payload
    assert [c for c in ex.calls if c[0] == "classify"] == [("classify", "תוסיף יעד קרן חירום")]   # state persisted
    assert not any(c == ("fill", "60000") for c in ex.calls)         # deterministic answers need no LLM


# 13 + 14 — confirm freezes, writer does not re-infer, exact canonical fields, no field loss
def test_confirm_freezes_snapshot_and_writes_exact_reviewed_fields(mem_store):
    ex = Ex(classify={"x": EF_GOAL}, fill={"סוף השנה": {"end_date": "2026-12-31"}})
    run(ex, ELIYAHU, "x"); run(ex, ELIYAHU, "60000"); run(ex, ELIYAHU, "סוף השנה")
    ex.locked = True                                                  # no classify/extract after confirm
    r = run(ex, ELIYAHU, "אשר")
    assert r.state == "confirmed" and r.snapshot["tool_name"] == "fcc_writes"
    (w,) = r.snapshot["writes"]
    assert w["op"] == "post" and w["table"] == Tables.FIN_GOALS
    assert w["fields"] == {GF.TITLE: "קרן חירום", GF.TARGET_AMOUNT: 60000.0, GF.CATEGORY: "emergency_fund",
                           GF.CALC_METHOD: "cumulative", GF.END_DATE: "2026-12-31", GF.STATUS: "active"}
    stored = mem_store.load_business_draft("boss_hq:eliyahu", fd.FCC_GOAL, tenant_id="boss_hq", actor_user_id="eliyahu",
                                           source_channel="fcc", channel="fcc", contracts=fd.FCC_CONTRACTS)
    assert stored.lifecycle_state is bd.DraftState.CONFIRMED and stored.snapshot is not None
    with pytest.raises(bd.BusinessDraftError):
        stored.set_field("target_amount", 1, adapter=fd.ADAPTER)      # frozen
    conv.complete_execution(ELIYAHU)
    assert conv.pending_view(ELIYAHU) is None


# income: safe inference, no end date needed, straight to review
def test_income_goal_infers_category_period_method_and_skips_end_date():
    ex = Ex(classify={"תוסיף יעד הכנסה חודשית 15000": {
        "action": "create_goal", "title": "הכנסה חודשית", "target": 15000, "category": "income"}})
    r = run(ex, ELIYAHU, "תוסיף יעד הכנסה חודשית 15000")
    assert r.state == "review" and "(הוסק)" in r.message
    w = run(ex, ELIYAHU, "אשר").snapshot["writes"][0]["fields"]
    assert (w[GF.CATEGORY], w[GF.PERIOD_TYPE], w[GF.CALC_METHOD]) == ("income", "monthly", "period_sum")
    assert GF.END_DATE not in w


# cumulative types need an end date; "other" never guesses period/method
def test_required_matrix_cumulative_needs_end_date_and_other_asks_period_and_method():
    for cat in ("emergency_fund", "debt"):
        ex = Ex(classify={"g": {"action": "create_goal", "title": f"t-{cat}", "target": 1000, "category": cat}})
        r = run(ex, ELIYAHU, "g")
        assert r.awaiting == "end_date", cat
        run(ex, ELIYAHU, "בטל")
    ex = Ex(classify={"o": {"action": "create_goal", "title": "השקעות", "target": 5000, "category": "other"}})
    r = run(ex, ELIYAHU, "o")
    assert r.awaiting == "period_type"                                # not guessed
    r = run(ex, ELIYAHU, "חודשי")
    assert r.awaiting == "calc_method"
    r = run(ex, ELIYAHU, "מצטבר")
    assert r.awaiting == "end_date"                                   # conditional on cumulative


# 7 + 8 — required cannot be skipped; optional fields are never asked
def test_required_field_cannot_be_skipped_and_optional_never_asked():
    ex = Ex(classify={"x": EF_GOAL})
    run(ex, ELIYAHU, "x")
    r = run(ex, ELIYAHU, "דלג")
    assert r.awaiting == "target_amount" and "אי אפשר לדלג" in r.message
    run(ex, ELIYAHU, "60000")
    seen = {conv.pending_view(ELIYAHU)["awaiting"]}
    assert seen == {"end_date"} and "start_date" not in seen          # optional start_date is never prompted
    r = run(ex, ELIYAHU, "2026-12-31")                                # ISO accepted deterministically
    assert r.state == "review"
    r = run(ex, ELIYAHU, "דלג")                                       # a skip word is never a confirm
    assert r.state == "unrelated" and conv.pending_view(ELIYAHU)["state"] == "review"


# 9 — edit changes one field only, does not restart the flow
def test_edit_changes_single_field_in_same_draft():
    ex = Ex(classify={"x": EF_GOAL}, fill={"סכום 80000": {"target_amount": 80000}, "סוף יוני": {"end_date": "2027-06-30"}})
    run(ex, ELIYAHU, "x"); run(ex, ELIYAHU, "60000"); run(ex, ELIYAHU, "2026-12-31")
    r = run(ex, ELIYAHU, "ערוך")
    assert r.state == "ask" and "מה לערוך" in r.message
    r = run(ex, ELIYAHU, "סכום 80000")
    assert r.state == "review" and "₪80,000" in r.message and "31/12/2026" in r.message
    r = run(ex, ELIYAHU, "סוף יוני")                                  # direct edit from review
    assert "30/06/2027" in r.message and "₪80,000" in r.message and "קרן חירום" in r.message
    assert [c for c in ex.calls if c[0] == "classify"] == [("classify", "x")]


# 10 — cancel closes the draft
def test_cancel_closes_draft():
    ex = Ex(classify={"x": EF_GOAL})
    run(ex, ELIYAHU, "x")
    assert run(ex, ELIYAHU, "בטל").state == "cancelled"
    assert conv.pending_view(ELIYAHU) is None
    assert run(ex, ELIYAHU, "אשר").state == "info"                    # nothing to confirm


# 11 — TTL is the existing Diamond contract (1800s), expiry handled lazily
def test_ttl_uses_existing_diamond_contract_and_expires(monkeypatch):
    assert DRAFT_TTL_SECONDS == bd.DRAFT_TTL_SECONDS == 1800
    ex = Ex(classify={"x": EF_GOAL})
    run(ex, ELIYAHU, "x")
    real = bd.time.time
    monkeypatch.setattr(bd.time, "time", lambda: real() + 1801)
    r = run(ex, ELIYAHU, "60000")
    assert r.state == "clarify"                                       # expired draft is NOT resumed
    assert conv.pending_view(ELIYAHU) is None
    assert run(ex, ELIYAHU, "אשר").state == "info"                    # and nothing is left to confirm


# 3 + 18 + 19 — concurrent users hold separate drafts; owner isolation
def test_concurrent_users_have_isolated_drafts():
    ex = Ex(classify={"e": EF_GOAL, "a": {"action": "create_goal", "title": "יעד אבי", "category": "income", "target": 7000}})
    run(ex, ELIYAHU, "e")
    run(ex, AVI_I, "a")
    run(ex, ELIYAHU, "60000")
    eli, avi = conv.pending_view(ELIYAHU), conv.pending_view(AVI_I)
    assert eli["awaiting"] == "end_date" and eli["fields"]["יעד"] == "קרן חירום"
    assert avi["state"] == "review" and avi["fields"]["יעד"] == "יעד אבי" and "קרן חירום" not in str(avi)
    assert run(ex, AVI_I, "בטל").state == "cancelled"
    assert conv.pending_view(ELIYAHU)["awaiting"] == "end_date"       # Eliyahu's draft untouched
    assert conv.handle_turn(ident("nobody", Role.MANAGER), "x", extractor=ex).state == "denied"


# 4 — missing amount asks the amount (no Task); ambiguity asks which goal (own goals only)
def test_missing_amount_is_asked_not_turned_into_task_and_goal_is_chosen_not_guessed():
    DB[Tables.FIN_GOALS] += [goal("recG2", "חיסכון קבוע", ELI), goal("recG3", "חיסכון לילדים", ELI)]
    ex = Ex(classify={"העברתי לחיסכון": {"action": "log_progress", "goal_hint": "חיסכון"}})
    r = run(ex, ELIYAHU, "העברתי לחיסכון")
    assert r.state == "needs_goal" and {c["goal_id"] for c in r.candidates} == {"recG2", "recG3"}
    assert "recGA" not in str(r.candidates)                           # never another owner's goal
    r = run(ex, ELIYAHU, "הכנסה של אבי")
    assert r.state == "needs_goal"                                    # foreign/unknown title does not resolve
    r = run(ex, ELIYAHU, "חיסכון קבוע")
    assert r.state == "ask" and r.awaiting == "amount" and "חיסכון קבוע" in r.message
    assert DB[Tables.TASKS] == [] and r.snapshot is None              # no Task, no write
    r = run(ex, ELIYAHU, "5,000")
    assert r.state == "review" and "₪5,000" in r.message
    w = run(ex, ELIYAHU, "אשר").snapshot["writes"][0]["fields"]
    assert w[EF.GOAL] == ["recG2"] and w[EF.AMOUNT] == 5000.0 and w[EF.KIND] == "one_time"
    assert w[EF.IDEMPOTENCY_KEY].startswith("fcc-") and w[EF.RAW_TEXT] == "העברתי לחיסכון"


def test_explicit_goal_id_of_other_owner_denied():
    ex = Ex(classify={"רשום": {"action": "log_progress", "goal_hint": "", "amount": 10}})
    assert run(ex, ELIYAHU, "רשום", goal_id="recGA").state == "denied"


# missing field != follow-up Task; a real external action is a Task
def test_real_followup_task_inherits_owner_and_missing_field_is_not_a_task():
    ex = Ex(classify={"דיברתי עם הבנק": {"action": "follow_up", "goal_hint": "הכנסה נוספת", "task_title": "להשיג יתרות"}})
    r = run(ex, ELIYAHU, "דיברתי עם הבנק")
    assert r.state == "review" and "משימת המשך" in r.message
    (w,) = run(ex, ELIYAHU, "אשר").snapshot["writes"]
    f = w["fields"]
    assert w["table"] == Tables.TASKS and f[TaskFields.OWNER] == [ELI] and f[TaskFields.TOPIC] == "כספים"
    assert f[TaskFields.DESCRIPTION].startswith("[FCC:recGE]") and f[TaskFields.STATUS] == "ממתין"


# 15 — update_goal: overlay on the base snapshot, only changed fields are written
def test_update_goal_overlay_preserves_unchanged_fields_and_target_is_an_event():
    DB[Tables.FIN_GOALS] = [goal("recGE", "הכנסה נוספת", ELI, 12000, **{GF.CATEGORY: "income"}), DB[Tables.FIN_GOALS][1]]
    ex = Ex(classify={"שנה": {"action": "update_goal", "goal_hint": "הכנסה נוספת", "target": 80000, "end_date": "2026-12-31"}})
    r = run(ex, ELIYAHU, "שנה")
    assert r.state == "review" and "₪80,000" in r.message and "הכנסה" in r.message and "שינויים" in r.message
    writes = run(ex, ELIYAHU, "אשר").snapshot["writes"]
    patch = next(w for w in writes if w["op"] == "patch")
    assert patch["record_id"] == "recGE" and set(patch["fields"]) == {GF.END_DATE}     # nothing else touched
    event = next(w for w in writes if w["op"] == "post")
    assert event["table"] == Tables.FIN_EVENTS and event["fields"][EF.KIND] == "target_change"
    assert event["fields"][EF.AMOUNT] == 80000.0 and event["fields"][EF.GOAL] == ["recGE"]
    # nothing to change -> clarify, not an empty write
    conv.complete_execution(ELIYAHU)
    ex2 = Ex(classify={"כלום": {"action": "update_goal", "goal_hint": "הכנסה נוספת"}})
    assert run(ex2, ELIYAHU, "כלום").state == "clarify"


def test_rename_via_update_patches_title_only():
    ex = Ex(classify={"שם": {"action": "rename_goal", "goal_hint": "הכנסה נוספת", "new_title": "הכנסה שוטפת"}})
    run(ex, ELIYAHU, "שם")
    (w,) = run(ex, ELIYAHU, "אשר").snapshot["writes"]
    assert w["op"] == "patch" and w["fields"] == {GF.TITLE: "הכנסה שוטפת"} and w["record_id"] == "recGE"


# 20 — duplicate title blocked; duplicate event not written twice
def test_duplicate_goal_title_and_duplicate_event_blocked():
    ex = Ex(classify={"d": {"action": "create_goal", "title": " הכנסה  נוספת "}})
    assert run(ex, ELIYAHU, "d").state == "duplicate"
    ev = {"action": "log_progress", "goal_hint": "הכנסה נוספת", "amount": 5000}
    ex = Ex(classify={"העברתי 5000": ev})
    run(ex, ELIYAHU, "העברתי 5000")
    key = run(ex, ELIYAHU, "אשר").snapshot["writes"][0]["fields"][EF.IDEMPOTENCY_KEY]
    DB[Tables.FIN_EVENTS].append(event("recNew", "recGE", ELI, 5000, key=key, day="2026-10-08"))
    conv.complete_execution(ELIYAHU)
    assert run(ex, ELIYAHU, "העברתי 5000").state == "duplicate"


# 16 — TMA: same flow; the client only renders server state and executes the FROZEN writes
def test_tma_flow_resumes_after_refresh_and_executes_frozen_writes(monkeypatch):
    ex = Ex(classify={"תוסיף יעד קרן חירום": EF_GOAL}, fill={"סוף השנה": {"end_date": "2026-12-31"}})
    monkeypatch.setattr(conv, "DeterministicExtractor", lambda: ex)
    sent = []
    monkeypatch.setattr(tma_api, "_queue_or_owner_execute",
                        lambda action, payload, identity, label: (sent.append((action, payload)) or ("a1", {"ok": True}, 200)))
    c = http(monkeypatch, ELIYAHU)
    post = lambda t, **kw: c.post("/api/fcc/write", json={"text": t, **kw}, headers=H).get_json()
    assert post("תוסיף יעד קרן חירום")["awaiting"] == "target_amount"
    ov = c.get("/api/fcc/overview", headers=H).get_json()             # refresh: the open question comes back
    assert ov["draft"]["awaiting"] == "target_amount"
    assert post("60000")["awaiting"] == "end_date"
    assert post("סוף השנה")["state"] == "review" and sent == []       # nothing written before confirm
    done = post("אשר")
    assert done["state"] == "executed" and [a for a, _ in sent] == ["tma_fcc_write"]
    assert sent[0][1]["fields"][GF.CATEGORY] == "emergency_fund" and sent[0][1]["table"] == Tables.FIN_GOALS
    assert c.get("/api/fcc/overview", headers=H).get_json()["draft"] is None


def test_tma_failed_execution_keeps_confirmed_draft_for_retry(monkeypatch):
    ex = Ex(classify={"x": {"action": "create_goal", "title": "יעד", "target": 100, "category": "income"}})
    monkeypatch.setattr(conv, "DeterministicExtractor", lambda: ex)
    calls = {"n": 0}

    def flaky(action, payload, identity, label):
        calls["n"] += 1
        return ("a", {"error": "boom"}, 500) if calls["n"] == 1 else ("a", {"ok": True}, 200)
    monkeypatch.setattr(tma_api, "_queue_or_owner_execute", flaky)
    c = http(monkeypatch, ELIYAHU)
    post = lambda t: c.post("/api/fcc/write", json={"text": t}, headers=H)
    post("x")
    first = post("אשר")
    assert first.status_code == 500 and first.get_json()["state"] == "partial_failure"
    assert post("אשר").get_json()["state"] == "executed"             # retry executes the same frozen writes


# 17 — chat: same draft as the TMA; continuation claimed before the agent; writes via the canonical queue
def test_chat_and_tma_share_one_draft_and_chat_executes_via_canonical_queue(monkeypatch):
    import feature_flags
    monkeypatch.setattr(feature_flags, "is_enabled", lambda n, *a, **k: n == "FEATURE_FINANCIAL_CONTROL_CENTER")
    monkeypatch.setenv("FCC_CANARY_USER_IDS", "eliyahu")
    ex = Ex(classify={"תוסיף יעד קרן חירום": EF_GOAL}, fill={"סוף השנה": {"end_date": "2026-12-31"}})
    monkeypatch.setattr(conv, "DeterministicExtractor", lambda: ex)
    queued = []
    q = lambda tool, inputs: (queued.append((tool, inputs)) or {"ok": True, "contract_id": "c1", "created_this_turn": True})
    assert fchat.maybe_handle(ELIYAHU, "שלום", queue=q) == (None, None)       # no draft -> not an FCC turn
    assert "סכום היעד" in fchat.start_turn(ELIYAHU, "תוסיף יעד קרן חירום")   # started by the agent tool
    c = http(monkeypatch, ELIYAHU)
    assert c.get("/api/fcc/overview", headers=H).get_json()["draft"]["awaiting"] == "target_amount"   # same draft in TMA
    text, out = fchat.maybe_handle(ELIYAHU, "60000", queue=q)
    assert text is not None and "עד מתי" in text and out is None
    text, out = fchat.maybe_handle(ELIYAHU, "סוף השנה", queue=q)
    assert "31/12/2026" in text and queued == []
    text, out = fchat.maybe_handle(ELIYAHU, "אשר", queue=q)
    assert text is None and out["contract_id"] == "c1"
    (tool, inputs), = queued
    assert tool == "airtable_add" and inputs["table"] == Tables.FIN_GOALS
    assert inputs["fields"][GF.CATEGORY] == "emergency_fund" and inputs["fields"][GF.END_DATE] == "2026-12-31"
    assert conv.pending_view(ELIYAHU) is None
    # a different user (not on the canary list) is never claimed by FCC
    assert fchat.maybe_handle(AVI_I, "אשר", queue=q) == (None, None)


def test_chat_queue_failure_keeps_confirmed_draft_for_retry(monkeypatch):
    import feature_flags
    monkeypatch.setattr(feature_flags, "is_enabled", lambda n, *a, **k: n == "FEATURE_FINANCIAL_CONTROL_CENTER")
    monkeypatch.setenv("FCC_CANARY_USER_IDS", "eliyahu")
    ex = Ex(classify={"x": {"action": "create_goal", "title": "יעד", "target": 100, "category": "income"}})
    monkeypatch.setattr(conv, "DeterministicExtractor", lambda: ex)
    fchat.start_turn(ELIYAHU, "x")
    text, out = fchat.maybe_handle(ELIYAHU, "אשר", queue=lambda t, i: {"ok": False})
    assert "לא הצלחתי" in text and out is None and conv.pending_view(ELIYAHU) is not None
    text, out = fchat.maybe_handle(ELIYAHU, "אשר", queue=lambda t, i: {"ok": True, "contract_id": "c"})
    assert text is None and out is not None and conv.pending_view(ELIYAHU) is None


# 21 — ActionGateway stays the single write path: FCC code only emits frozen writes
def test_no_direct_airtable_write_in_fcc_package_and_only_canonical_tools_emitted():
    import pathlib
    src = "".join(p.read_text() for p in pathlib.Path("core/financial_control").glob("*.py"))
    for forbidden in ("airtable_create", "airtable_patch", "requests.", "urlopen", "airtable_tools", "import crm"):
        assert forbidden not in src
    assert fchat.to_canonical_call({"op": "post", "table": "T", "fields": {"a": 1}})[0] == "airtable_add"
    assert fchat.to_canonical_call({"op": "patch", "table": "T", "record_id": "r", "fields": {"a": 1}})[0] == "airtable_update"


# extractor plumbing (LLM boundary mocked): malformed output never becomes data
def test_fill_reply_and_classify_parse_llm_json_and_reject_garbage(monkeypatch):
    import llm_fallback
    from core.financial_control import classifier
    outs = iter([
        'noise {"fields": {"end_date": "2026-12-31"}, "evidence": {"end_date": "סוף השנה"}} tail',
        "no json at all",
        '{"action": "create_goal", "title": "t"}',
        '{"fields": {"target_amount": 5}, "evidence": {"target_amount": "5 לידים"}}',      # quote not in the text
        '{"fields": {"target_amount": 5}}',                                                  # no evidence at all
        '{"fields": {"target_amount": 60000}, "evidence": {"target_amount": "60 אלף"}}',
    ])
    monkeypatch.setattr(llm_fallback, "call_anthropic_text", lambda **kw: next(outs))
    assert classifier.fill_reply("סוף השנה", "end_date", {}, fd.FCC_GOAL, today=TODAY) == {"end_date": "2026-12-31"}
    assert classifier.fill_reply("???", "end_date", {}, fd.FCC_GOAL, today=TODAY) == {}
    assert classifier.classify("x", [], today=TODAY)["action"] == "create_goal"
    assert classifier.fill_reply("מה מצב הלידים שלי?", "target_amount", {}, fd.FCC_GOAL, today=TODAY) == {}
    assert classifier.fill_reply("מה מצב הלידים שלי?", "target_amount", {}, fd.FCC_GOAL, today=TODAY) == {}
    assert classifier.fill_reply("60 אלף", "target_amount", {}, fd.FCC_GOAL, today=TODAY) == {"target_amount": 60000}


# agent tool: registered owner-only, schema'd, gated by the same canary, never writes
def test_fcc_update_tool_is_owner_only_gated_and_draft_only(monkeypatch):
    import feature_flags
    import tool_registry
    import tools.schemas as schemas
    meta = tool_registry._REGISTRY.get("fcc_update")
    assert meta is not None and meta.roles_allowed == {"owner"} and not meta.requires_approval
    assert any(t["name"] == "fcc_update" for t in schemas.TOOL_SCHEMAS)
    ex = Ex(classify={"תוסיף יעד קרן חירום": EF_GOAL})
    monkeypatch.setattr(conv, "DeterministicExtractor", lambda: ex)
    monkeypatch.setattr(feature_flags, "is_enabled", lambda *a, **k: False)
    assert "לא פעיל" in dispatcher_module.dispatch_tool("fcc_update", {"text": "תוסיף יעד קרן חירום"}, ELIYAHU)
    monkeypatch.setattr(feature_flags, "is_enabled", lambda n, *a, **k: n == "FEATURE_FINANCIAL_CONTROL_CENTER")
    monkeypatch.setenv("FCC_CANARY_USER_IDS", "eliyahu")
    out = dispatcher_module.dispatch_tool("fcc_update", {"text": "תוסיף יעד קרן חירום"}, ELIYAHU)
    assert "סכום היעד" in out and conv.pending_view(ELIYAHU)["awaiting"] == "target_amount"
    assert DB[Tables.FIN_GOALS][0]["id"] == "recGE" and len(DB[Tables.FIN_GOALS]) == 2     # nothing written


# ═══════════════ Sessions privacy gate (PR: FCC Diamond completion) ═══════════════
import identity as identity_module_  # noqa: E402
from tools import airtable_tools  # noqa: E402

SESSIONS_RAW_ID = "tblHLfE24lTkVUhz0"
MANAGER = ident("manny", Role.MANAGER)
EMPLOYEE = ident("eve", Role.EMPLOYEE)


def _start_goal_draft(who, title="קרן חירום"):
    ex = Ex(classify={"s": {"action": "create_goal", "title": title, "category": "emergency_fund"}})
    run(ex, who, "s")
    return ex


# 1 — A cannot read B's FCC draft (neither through the conversation nor through the store binding)
def test_a_cannot_read_b_fcc_draft(mem_store):
    _start_goal_draft(AVI_I, "יעד סודי של אבי")
    assert conv.pending_view(ELIYAHU) is None
    assert "סודי" not in str(conv.pending_view(ELIYAHU))
    # even a caller that guesses B's slot key is stopped by the stored identity binding
    with pytest.raises(bd.DraftIdentityMismatchError):
        mem_store.load_business_draft("boss_hq:avi", fd.FCC_GOAL, tenant_id="boss_hq", actor_user_id="eliyahu",
                                      source_channel="fcc", channel="fcc", contracts=fd.FCC_CONTRACTS)
    # a wrong tenant does not resolve either
    with pytest.raises(bd.DraftIdentityMismatchError):
        mem_store.load_business_draft("boss_hq:avi", fd.FCC_GOAL, tenant_id="other_tenant", actor_user_id="avi",
                                      source_channel="fcc", channel="fcc", contracts=fd.FCC_CONTRACTS)


# 2 — A cannot mutate B's draft: A's answers only ever touch A's slot; a forged save is refused
def test_a_cannot_mutate_b_fcc_draft(mem_store):
    ex = _start_goal_draft(AVI_I, "יעד אבי")
    before = conv.pending_view(AVI_I)
    run(ex, ELIYAHU, "60000")                                         # A answers: no draft of A's => not an answer
    run(ex, ELIYAHU, "בטל")
    assert conv.pending_view(AVI_I) == before
    avi_draft = mem_store.load_business_draft("boss_hq:avi", fd.FCC_GOAL, tenant_id="boss_hq", actor_user_id="avi",
                                              source_channel="fcc", channel="fcc", contracts=fd.FCC_CONTRACTS)
    forged = bd.create_draft(entity_type=fd.FCC_GOAL, operation=bd.DraftOperation.CREATE, tenant_id="boss_hq",
                             actor_role="owner", actor_user_id="eliyahu", source_channel="fcc", sender="boss_hq:avi",
                             contracts=fd.FCC_CONTRACTS)
    with pytest.raises(bd.DraftIdentityMismatchError):
        mem_store.save_business_draft("boss_hq:avi", forged, expected_version=avi_draft.idempotency_key,
                                      channel="fcc", contracts=fd.FCC_CONTRACTS)


# 3 — generic Airtable tools (every internal role) can neither read nor write Sessions
def test_generic_tools_cannot_read_or_write_sessions(monkeypatch):
    rows = [{"id": "recS1", "fields": {"Sender ID": "boss_hq:avi", "State JSON": '{"business_drafts": "SECRET-DRAFT"}'}}]
    monkeypatch.setattr(airtable_tools, "airtable_get_records", lambda t, f="", max_records=None: list(rows))
    monkeypatch.setattr(airtable_tools, "_audit", lambda *a, **k: None)
    monkeypatch.setattr(dispatcher_module._ff, "is_enabled", lambda *a, **k: False)
    for who in (ELIYAHU, AVI_I, MANAGER, EMPLOYEE):
        for variant in ("Sessions", "sessions", " Sessions "):
            out = dispatcher_module.dispatch_tool("airtable_get", {"table": variant}, who)
            assert "SECRET-DRAFT" not in out and "recS1" not in out, (who.user_id, variant)
        for tool, params in (("airtable_get", {"table": "Sessions"}),
                             ("airtable_add", {"table": "Sessions", "fields": {"Sender ID": "x"}}),
                             ("airtable_update", {"table": "Sessions", "record_id": "recS1", "fields": {"Sender ID": "x"}})):
            with pytest.raises(TenantScopeViolation):
                enforce_tenant_scope(tool, who, params)
    assert policy.filter_records("Sessions", rows, ELIYAHU) == []
    with pytest.raises(policy.PersonalDataAccessDenied):
        policy.authorize_record("Sessions", rows[0]["fields"], ELIYAHU)
    assert airtable_tools.airtable_get("Sessions") == policy.SYSTEM_STATE_MESSAGE        # render path refuses too


# 4 — a raw Sessions table id cannot bypass the policy; TMA write allowlist excludes Sessions
def test_raw_sessions_table_id_and_tma_write_cannot_bypass_policy():
    assert policy.is_raw_table_id(SESSIONS_RAW_ID)
    for who in (ELIYAHU, MANAGER):
        for tool in ("airtable_get", "airtable_add", "airtable_update"):
            with pytest.raises(TenantScopeViolation):
                enforce_tenant_scope(tool, who, {"table": SESSIONS_RAW_ID, "record_id": "recS1", "fields": {}})
    assert "Sessions" not in approval_actions._TMA_WRITE_ALLOWED_TABLES


# 5 — unrelated text in the middle of the amount question is NOT stored as a value
def test_unrelated_text_is_not_saved_as_amount_and_draft_is_untouched(mem_store):
    ex = Ex(classify={"x": EF_GOAL})                       # fill() returns {} for any other text
    run(ex, ELIYAHU, "x")
    before = conv.pending_view(ELIYAHU)
    r = run(ex, ELIYAHU, "מה מצב הלידים שלי?")
    assert r.state == "unrelated" and r.awaiting == "target_amount" and "סכום היעד" in r.message
    assert conv.pending_view(ELIYAHU) == before
    stored = mem_store.load_business_draft("boss_hq:eliyahu", fd.FCC_GOAL, tenant_id="boss_hq", actor_user_id="eliyahu",
                                           source_channel="fcc", channel="fcc", contracts=fd.FCC_CONTRACTS)
    assert "target_amount" not in stored.fields and set(stored.fields) == {"title", "category", "calc_method"}
    # an extractor that hallucinates a number WITHOUT evidence cannot sneak one in either (classifier-level filter)
    ex2 = Ex(fill={"מה מצב הלידים שלי?": {"title": "מה מצב הלידים שלי?"}})
    assert run(ex2, ELIYAHU, "מה מצב הלידים שלי?").awaiting == "target_amount"


# 6 + 7 — an invalid date keeps the draft on the same field; the next valid reply continues the same draft
def test_invalid_date_reasks_same_field_then_valid_reply_continues(mem_store):
    ex = Ex(classify={"x": EF_GOAL}, fill={"31/02/2026": {"end_date": "31/02/2026"}})
    run(ex, ELIYAHU, "x"); run(ex, ELIYAHU, "60000")
    r = run(ex, ELIYAHU, "31/02/2026")
    assert r.state == "ask" and r.awaiting == "end_date" and "ערך לא תקין" in r.message
    stored = mem_store.load_business_draft("boss_hq:eliyahu", fd.FCC_GOAL, tenant_id="boss_hq", actor_user_id="eliyahu",
                                           source_channel="fcc", channel="fcc", contracts=fd.FCC_CONTRACTS)
    assert "end_date" not in stored.fields and stored.fields["target_amount"] == 60000
    r = run(ex, ELIYAHU, "31/12/2026")
    assert r.state == "review" and "31/12/2026" in r.message         # same draft, nothing re-asked
    assert [c for c in ex.calls if c[0] == "classify"] == [("classify", "x")]
    r = run(ex, ELIYAHU, "-5")                                         # invalid amount on an edit is also rejected
    assert r.state in ("unrelated", "ask") and "₪60,000" in conv.pending_view(ELIYAHU)["message"]


# 8 — cancel clears only the current user's draft
def test_cancel_clears_only_current_users_draft():
    ex = Ex(classify={"e": EF_GOAL, "a": {"action": "create_goal", "title": "יעד אבי", "target": 5, "category": "income"}})
    run(ex, ELIYAHU, "e"); run(ex, AVI_I, "a")
    assert run(ex, ELIYAHU, "בטל").state == "cancelled"
    assert conv.pending_view(ELIYAHU) is None and conv.pending_view(AVI_I)["state"] == "review"


# 9 — simultaneous A/B drafts stay isolated through their whole lifecycle incl. confirm
def test_simultaneous_drafts_isolated_through_confirm():
    ex = Ex(classify={"e": EF_GOAL, "a": {"action": "create_goal", "title": "יעד אבי", "target": 7000, "category": "income"}},
            fill={"סוף השנה": {"end_date": "2026-12-31"}})
    run(ex, ELIYAHU, "e"); run(ex, AVI_I, "a"); run(ex, ELIYAHU, "60000")
    avi = run(ex, AVI_I, "אשר").snapshot["writes"][0]["fields"]
    eli = run(ex, ELIYAHU, "סוף השנה")
    assert avi[GF.TITLE] == "יעד אבי" and "קרן חירום" not in str(avi)
    assert eli.state == "review" and "יעד אבי" not in eli.message


# identity fail-closed: no tenant / unresolved => nothing is read or written
def test_unresolved_or_tenantless_identity_fails_closed():
    tenantless = Identity(user_id="eliyahu", role=Role.OWNER, display_name="eliyahu", tenant_id="",
                          domain_id=Domain.GENERAL, allowed_domains=[], channel="telegram", external_id="tg-x")
    ex = Ex(classify={"x": EF_GOAL})
    assert conv.handle_turn(tenantless, "x", extractor=ex, today=TODAY).state == "denied"
    assert conv.pending_view(tenantless) is None and ex.calls == []


# chat releases unrelated messages to the normal flow while the draft stays open
def test_chat_releases_unrelated_message_and_keeps_draft(monkeypatch):
    import feature_flags
    monkeypatch.setattr(feature_flags, "is_enabled", lambda n, *a, **k: n == "FEATURE_FINANCIAL_CONTROL_CENTER")
    monkeypatch.setenv("FCC_CANARY_USER_IDS", "eliyahu")
    ex = Ex(classify={"x": EF_GOAL})
    monkeypatch.setattr(conv, "DeterministicExtractor", lambda: ex)
    fchat.start_turn(ELIYAHU, "x")
    q = lambda t, i: pytest.fail("must not queue")
    assert fchat.maybe_handle(ELIYAHU, "מה מצב הלידים שלי?", queue=q) == (None, None)
    assert conv.pending_view(ELIYAHU)["awaiting"] == "target_amount"



# ═══════════════ Goal families: recurring / monthly_level / cumulative / project ═══════════════
def _family_db():
    DB[Tables.FIN_GOALS] = [
        goal("g1", "הכנסה חודשית קבועה", ELI, 10000, **{GF.CATEGORY: "income"}),
        goal("g2", "הכנסה מנסיעות", ELI, 1500, **{GF.CATEGORY: "income"}),
        goal("g3", "סגירת הלוואות", ELI, 700000, **{GF.CATEGORY: "debt", GF.CALC_METHOD: "cumulative"}),
        goal("g4", "הפחתת החזרים חודשיים", ELI, 7000, **{GF.CATEGORY: "debt"}),
        goal("g5", "הפחתת ריבית קבועה", ELI, 3000, **{GF.CATEGORY: "debt", GF.CALC_METHOD: "recurring_level"}),
        goal("g6", "קרן חירום זמינה", ELI, 60000, **{GF.CATEGORY: "emergency_fund", GF.CALC_METHOD: "cumulative",
                                                     GF.END_DATE: "2026-12-31"}),
        goal("g7", "תוספת חיסכון מהפרטי", ELI, None, **{GF.CATEGORY: "savings"}),         # numeric, target not set yet
        goal("p1", "מכירת יבנאל", ELI, None, **{GF.CATEGORY: "project"}),
        goal("p2", "ייבוא סיבים", ELI, None, **{GF.CATEGORY: "business_project"}),
        goal("p3", "חסכונות ושוק ההון", ELI, None, **{GF.CATEGORY: "investment"}),
        goal("zA", "של אבי", AVI, 99000, **{GF.CATEGORY: "debt", GF.CALC_METHOD: "cumulative"}),
    ]
    for g in DB[Tables.FIN_GOALS]:
        if g["fields"].get(GF.TARGET_AMOUNT) is None:
            g["fields"].pop(GF.TARGET_AMOUNT, None)
    DB[Tables.FIN_EVENTS] = []


def test_goal_families_are_classified_from_existing_data_without_schema_change():
    _family_db()
    rows = {r["goal_id"]: r for r in service.overview(ELIYAHU, TODAY)["goals"]}
    assert {k: rows[k]["mode"] for k in ("g1", "g2", "g3", "g4", "g5", "g6", "p1", "p2", "p3")} == {
        "g1": "recurring", "g2": "recurring", "g3": "cumulative", "g4": "recurring", "g5": "monthly_level",
        "g6": "cumulative", "p1": "project", "p2": "project", "p3": "project"}
    assert rows["g7"]["status"] == "missing_target" and rows["g7"]["mode"] != "project"   # a numeric goal lacking an amount


def test_project_goal_carries_no_amounts_and_shows_next_action():
    _family_db()
    DB[Tables.TASKS] = [{"id": "t1", "fields": {
        TaskFields.NAME: "לקבל הערכת שווי", TaskFields.STATUS: "ממתין", TaskFields.OWNER: [ELI],
        TaskFields.TOPIC: "כספים", TaskFields.DESCRIPTION: "[FCC:p1] x", TaskFields.DUE_DATE: "2026-10-20"}}]
    rows = {r["goal_id"]: r for r in service.overview(ELIYAHU, TODAY)["goals"]}
    p1, p2 = rows["p1"], rows["p2"]
    for key in ("actual", "remaining", "dynamic_target_per_week", "remaining_periods", "target"):
        assert p1[key] is None and p2[key] is None                    # no ₪0, no dead "—" cells to render
    assert p1["status"] == "project" and p1["next_action"] == {"title": "לקבל הערכת שווי", "due_date": "2026-10-20"}
    assert p2["next_action"] is None                                  # explicit: no next action yet


def test_pace_rules_per_family():
    _family_db()
    rows = {r["goal_id"]: r for r in service.overview(ELIYAHU, TODAY)["goals"]}
    assert rows["g1"]["dynamic_target_per_week"] is not None          # recurring: weekly pace
    assert rows["g5"]["dynamic_target_per_week"] is None              # monthly level: never a weekly pace
    assert rows["g3"]["dynamic_target_per_week"] is None              # cumulative without an end date: no pace
    assert rows["g6"]["dynamic_target_per_week"] and rows["g6"]["end_date"] == "2026-12-31"   # explicit end date opts in


def test_summary_never_mixes_families_or_includes_projects_or_other_owners():
    _family_db()
    summary = service.overview(ELIYAHU, TODAY)["summary"]
    assert summary["income"]["target"] == 11500 and summary["income"]["goals"] == 2
    assert summary["debt_repaid"]["target"] == 700000 and summary["debt_repaid"]["goals"] == 1   # not 707,000
    assert summary["payment_reduction"]["target"] == 10000 and summary["payment_reduction"]["goals"] == 2
    assert summary["emergency_fund"]["target"] == 60000
    assert "savings" not in summary                                    # only a target-less savings goal exists
    assert "99000" not in str(summary)                                 # another owner's goal never aggregates


def test_direct_costs_reduce_remaining_and_raise_pace():
    hierarchy([event("recA", "recT", ELI, 100, day="2026-10-06"),
               event("recF", "recT", ELI, 30, kind="direct_cost", day="2026-10-06")])
    rows = rows_of(service.overview(ELIYAHU, TODAY))
    p = rows["recP"]
    assert (p["actual"], p["net"]) == (100, 70)
    assert p["remaining"] == p["target"] - 70                # profit is 70, not 100


def test_household_spend_is_separate_from_income_and_net():
    hierarchy([event("recA", "recT", ELI, 1000, day="2026-10-06"),
               event("recH", "recP", ELI, 400, kind="household_expense", day="2026-10-05"),
               event("recH2", "recP", ELI, 250, kind="household_expense", day="2026-09-28"),     # other month
               event("recH3", "recP", ELI, 90, kind="household_expense", day="2026-10-04", **{EF.SUPERSEDED_BY: ["recX"]})])
    view = service.overview(ELIYAHU, TODAY)
    assert view["household"]["month_total"] == 400
    card = view["summary"]["income"]
    assert (card["actual"], card["direct_costs"], card["net"]) == (1000, 0, 1000)           # never part of income / net


def test_household_kind_is_accepted_by_draft_and_classifier_validation():
    assert "household_expense" in fd.EVENT_KINDS and fd.VALUE_LABELS["kind"]["household_expense"]
    from core.financial_control import writer as w
    assert w.validate_intent({"action": "log_progress", "goal_hint": "הוצאות בית", "amount": 300,
                              "kind": "household_expense"})["kind"] == "household_expense"


def _expense(eid, owner, amount, required=True, status=None):
    f = {"name": eid, "amount": amount, "owner": [owner], "Receipt Required": required}
    if status:
        f["Receipt Status"] = status
    return {"id": eid, "fields": f}


def test_receipts_counter_counts_only_my_missing_business_receipts():
    DB[Tables.EXPENSES] = [
        _expense("e1", ELI, 100, status="missing"), _expense("e2", ELI, 50),            # missing / unset -> counted
        _expense("e3", ELI, 70, status="received"), _expense("e4", ELI, 30, required=False),
        _expense("e5", "recOTHER", 999, status="missing")]                              # someone else's row
    assert service.receipts_overview(ELIYAHU) == {"missing_count": 2, "missing_amount": 150.0}


def test_receipts_counter_fails_closed_for_unresolved_identity():
    DB[Tables.EXPENSES] = [_expense("e1", ELI, 100, status="missing")]
    assert service.receipts_overview(None) == {"missing_count": 0, "missing_amount": 0.0}


# ═══════════════ Recurring Obligations: private commitments, not an expense ledger ═══════════════
def _ob(oid, owner, name, amount, freq="monthly", active=True, review=None, saving=None):
    f = {"Name": name, "Amount": amount, "Frequency": freq, "Active": active, "Financial Owner": [owner]}
    if review:
        f["Review Status"] = review
    if saving is not None:
        f["Potential Monthly Saving"] = saving
    return {"id": oid, "fields": f}


def test_obligation_table_is_owner_scoped_never_manager_or_employee():
    from core import data_access_policy as pol
    assert pol.is_owner_scoped(Tables.REC_OBLIGATIONS)
    rows = [_ob("o1", ELI, "נטפליקס", 70), _ob("o2", "recOTHER", "סודי", 999)]
    assert [r["id"] for r in pol.filter_records(Tables.REC_OBLIGATIONS, rows, ELIYAHU)] == ["o1"]
    with pytest.raises(pol.PersonalDataAccessDenied):                    # a manager/employee has no owner-of-record access
        pol.filter_records(Tables.REC_OBLIGATIONS, rows, ident("nobody", Role.MANAGER))


def test_obligation_monthly_equivalent_by_frequency():
    assert calc.monthly_equivalent(120, "monthly") == 120
    assert calc.monthly_equivalent(300, "quarterly") == 100
    assert calc.monthly_equivalent(1200, "yearly") == 100
    assert calc.monthly_equivalent(500, "custom") is None           # no honest conversion -> not counted
    assert calc.monthly_equivalent(None, "monthly") is None


def test_obligations_summary_three_numbers_inactive_and_foreign_excluded():
    DB[Tables.REC_OBLIGATIONS] = [
        _ob("o1", ELI, "נטפליקס", 70, review="cancel"),
        _ob("o2", ELI, "ביטוח", 1200, freq="yearly", review="negotiate", saving=30),
        _ob("o3", ELI, "חשמל", 400, freq="quarterly"),
        _ob("o4", ELI, "ישן", 999, active=False, review="cancel"),
        _ob("o5", "recOTHER", "של מישהו אחר", 5000, review="cancel")]
    s = service.obligations_overview(ELIYAHU)
    assert s["total_monthly"] == round(70 + 100 + 400 / 3, 2)
    assert (s["flagged_count"], s["flagged_monthly"]) == (2, 170)
    assert s["potential_saving"] == 70 + 30            # cancel -> full monthly cost; stated saving wins


def test_obligation_is_in_overview_and_never_touches_income_or_household():
    DB[Tables.REC_OBLIGATIONS] = [_ob("o1", ELI, "נטפליקס", 70)]
    hierarchy([event("recA", "recT", ELI, 1000, day="2026-10-06")])
    view = service.overview(ELIYAHU, TODAY)
    assert view["obligations"]["total_monthly"] == 70
    assert view["summary"]["income"]["net"] == 1000 and view["household"]["month_total"] == 0


OB_NETFLIX = {"action": "upsert_obligation", "goal_hint": "", "title": "נטפליקס", "amount": 70,
              "frequency": "monthly", "review_status": "cancel"}


def test_netflix_cancel_creates_obligation_not_a_progress_event():
    DB[Tables.REC_OBLIGATIONS] = []
    ex = Ex(classify={"נטפליקס 70 לחודש לבטל": OB_NETFLIX})
    r = run(ex, ELIYAHU, "נטפליקס 70 לחודש לבטל")
    assert r.state == "ask" and r.entity == fd.FCC_OBLIGATION and r.awaiting == "scope"
    r = run(ex, ELIYAHU, "ביתי")
    assert r.state == "review" and "(הוסק)" in r.message and "₪70" in r.message       # saving inferred = monthly cost
    r = run(ex, ELIYAHU, "אשר")
    assert r.state == "confirmed"
    (write,) = r.snapshot["writes"]
    assert write["op"] == "post" and write["table"] == Tables.REC_OBLIGATIONS            # NOT Financial Progress Events
    f = write["fields"]
    assert (f["Name"], f["Amount"], f["Frequency"], f["Scope"], f["Review Status"]) == ("נטפליקס", 70, "monthly", "household", "cancel")
    assert f["Potential Monthly Saving"] == 70 and f["Active"] is True


def test_existing_obligation_is_updated_not_duplicated():
    DB[Tables.REC_OBLIGATIONS] = [_ob("recOB1", ELI, "נטפליקס", 50, review=None)]
    ex = Ex(classify={"נטפליקס עכשיו 70 לבטל": OB_NETFLIX})
    r = run(ex, ELIYAHU, "נטפליקס עכשיו 70 לבטל")
    assert r.state == "review"
    r = run(ex, ELIYAHU, "אשר")
    (write,) = r.snapshot["writes"]
    assert write["op"] == "patch" and write["table"] == Tables.REC_OBLIGATIONS and write["record_id"] == "recOB1"
    assert write["fields"]["Amount"] == 70 and write["fields"]["Review Status"] == "cancel"
    assert "Name" not in write["fields"] and "Scope" not in write["fields"]            # unmentioned fields untouched


def test_obligation_intent_validation_and_foreign_obligation_never_matched():
    from core.financial_control import writer as w
    assert w.validate_intent({"action": "upsert_obligation", "title": "x", "amount": 5, "frequency": "weekly"}) is None
    ok = w.validate_intent(OB_NETFLIX)
    assert ok["review_status"] == "cancel" and ok["frequency"] == "monthly"
    DB[Tables.REC_OBLIGATIONS] = [_ob("recX", "recOTHER", "נטפליקס", 50)]            # someone else's -> not mine
    ex = Ex(classify={"נטפליקס 70": {**OB_NETFLIX, "review_status": None}})
    r = run(ex, ELIYAHU, "נטפליקס 70")
    assert r.state == "ask" and r.awaiting == "scope"                                   # CREATE, not UPDATE of a foreign row


def test_cancel_of_untracked_commitment_says_so_in_review():
    DB[Tables.REC_OBLIGATIONS] = []
    ex = Ex(classify={"נטפליקס 70 לבטל": OB_NETFLIX})
    run(ex, ELIYAHU, "נטפליקס 70 לבטל")
    r = run(ex, ELIYAHU, "ביתי")
    assert r.state == "review" and "לא מצאתי התחייבות בשם נטפליקס" in r.message and "לבטל" in r.message


def test_summary_counts_cancel_pending_separately():
    DB[Tables.REC_OBLIGATIONS] = [_ob("o1", ELI, "א", 70, review="cancel"), _ob("o2", ELI, "ב", 100, review="reduce")]
    s = service.obligations_overview(ELIYAHU)
    assert (s["flagged_count"], s["cancel_pending"]) == (2, 1)


OB_DONE = {"action": "deactivate_obligation", "goal_hint": "", "title": "נטפליקס"}


def test_actually_cancelled_marks_inactive_and_leaves_the_monthly_total():
    DB[Tables.REC_OBLIGATIONS] = [_ob("recOB1", ELI, "נטפליקס", 70, review="cancel")]
    ex = Ex(classify={"ביטלתי את נטפליקס": OB_DONE})
    r = run(ex, ELIYAHU, "ביטלתי את נטפליקס")
    assert r.state == "review" and "תצא מהסכום החודשי" in r.message
    r = run(ex, ELIYAHU, "אשר")
    (write,) = r.snapshot["writes"]
    assert write["op"] == "patch" and write["record_id"] == "recOB1" and write["fields"] == {"Active": False}
    DB[Tables.REC_OBLIGATIONS][0]["fields"]["Active"] = False                      # as stored after the write
    assert service.obligations_overview(ELIYAHU)["total_monthly"] == 0


def test_deactivate_without_a_tracked_commitment_is_clarified_not_created():
    DB[Tables.REC_OBLIGATIONS] = [_ob("recX", "recOTHER", "נטפליקס", 70)]
    ex = Ex(classify={"ביטלתי את נטפליקס": OB_DONE})
    r = run(ex, ELIYAHU, "ביטלתי את נטפליקס")
    assert r.state == "clarify" and "לא מצאתי" in r.message


def test_cancelled_commitment_can_be_added_again():
    DB[Tables.REC_OBLIGATIONS] = [_ob("recOB1", ELI, "נטפליקס", 70, active=False)]
    ex = Ex(classify={"נטפליקס 70": {**OB_NETFLIX, "review_status": None}})
    run(ex, ELIYAHU, "נטפליקס 70")
    run(ex, ELIYAHU, "ביתי")
    r = run(ex, ELIYAHU, "אשר")
    assert r.state == "confirmed" and r.snapshot["writes"][0]["op"] == "post"       # inactive one does not block a new row


# ═══════════════ Savings = a standing monthly allocation vs target (never resets); emergency fund = one-time pot ═══════════════
def test_new_savings_goal_is_a_standing_monthly_level_not_cumulative_nor_period_sum():
    ex = Ex(classify={"s": {"action": "create_goal", "title": "הפרשה לשוק ההון", "target": 5000, "category": "savings"}})
    r = run(ex, ELIYAHU, "s")
    assert r.state == "review" and "(הוסק)" in r.message                       # period + method inferred, no end date asked
    w = run(ex, ELIYAHU, "אשר").snapshot["writes"][0]["fields"]
    assert (w[GF.CATEGORY], w[GF.PERIOD_TYPE], w[GF.CALC_METHOD]) == ("savings", "monthly", "recurring_level")
    assert GF.END_DATE not in w


def _savings_goal(gid="recS", target=5000):
    return goal(gid, "הפרשה לשוק ההון", ELI, target,
                **{GF.CATEGORY: "savings", GF.PERIOD_TYPE: "monthly", GF.CALC_METHOD: "recurring_level"})


def test_savings_level_accumulates_across_months_and_never_resets():
    DB[Tables.FIN_GOALS] = [_savings_goal()]
    DB[Tables.FIN_EVENTS] = [event("e1", "recS", ELI, 2000, kind="monthly_recurring", day="2026-08-15"),    # started two months ago
                             event("e2", "recS", ELI, 1000, kind="monthly_recurring", day="2026-10-03"),   # raised this month
                             event("e3", "recS", ELI, -300, kind="monthly_recurring", day="2026-10-05")]   # cut back a little
    view = service.overview(ELIYAHU, TODAY)
    card = view["summary"]["savings"]
    assert (card["actual"], card["target"], card["remaining"], card["mode"]) == (2700, 5000, 2300, "monthly_level")
    assert view["goals"][0]["dynamic_target_per_week"] is None                      # a level has no weekly pace


def test_savings_one_time_deposits_do_not_count_as_the_standing_level():
    DB[Tables.FIN_GOALS] = [_savings_goal()]
    DB[Tables.FIN_EVENTS] = [event("e1", "recS", ELI, 9000, kind="one_time", day="2026-10-03")]
    assert service.overview(ELIYAHU, TODAY)["summary"]["savings"]["actual"] == 0


def test_legacy_cumulative_savings_shows_only_until_a_monthly_one_exists_and_never_sums():
    legacy = goal("gL", "חיסכון ישן", ELI, 10000, **{GF.CATEGORY: "savings", GF.CALC_METHOD: "cumulative"})
    DB[Tables.FIN_EVENTS] = []
    DB[Tables.FIN_GOALS] = [legacy]
    assert service.overview(ELIYAHU, TODAY)["summary"]["savings"]["mode"] == "cumulative"
    DB[Tables.FIN_GOALS] = [legacy, _savings_goal(target=5000)]
    card = service.overview(ELIYAHU, TODAY)["summary"]["savings"]
    assert (card["target"], card["mode"]) == (5000, "monthly_level")                   # 15,000 would mean mixing families


# ═══════════════ "I now allocate X per month" = a NEW total level; the system computes the delta ═══════════════
def _level_world(*levels):
    DB[Tables.FIN_GOALS] = [_savings_goal()]
    DB[Tables.FIN_EVENTS] = [event(f"e{i}", "recS", ELI, v, kind="monthly_recurring", day="2026-09-01") for i, v in enumerate(levels)]


LEVEL = {"action": "log_progress", "goal_hint": "הפרשה", "kind": "monthly_recurring", "level": 3500}


def test_set_level_computes_the_delta_from_the_current_level():
    _level_world(2000, 1000)                                    # current level 3,000
    ex = Ex(classify={"אני מפריש עכשיו 3500": LEVEL})
    r = run(ex, ELIYAHU, "אני מפריש עכשיו 3500")
    assert r.state == "review" and "₪500" in r.message and "קביעת רמה" in r.message
    (w,) = run(ex, ELIYAHU, "אשר").snapshot["writes"]
    assert w["fields"]["Amount"] == 500 and w["fields"]["Kind"] == "monthly_recurring"


def test_set_level_downwards_is_a_negative_delta_and_same_level_is_a_noop():
    _level_world(4000)
    ex = Ex(classify={"עכשיו 3500": LEVEL, "עכשיו 4000": {**LEVEL, "level": 4000}})
    r = run(ex, ELIYAHU, "עכשיו 3500")
    assert "-₪500" in r.message
    run(ex, ELIYAHU, "בטל")
    assert run(ex, ELIYAHU, "עכשיו 4000").state == "clarify"


def test_set_level_validation_rejects_garbage():
    from core.financial_control import writer as w
    assert w.validate_intent({**LEVEL, "level": -5}) is None
    assert w.validate_intent({**LEVEL, "level": "הרבה"}) is None


# ═══════════════ the agent passes a structured intent -> no second classification call ═══════════════
def test_structured_intent_skips_the_classifier_call(monkeypatch):
    from core.financial_control import classifier
    monkeypatch.setattr(classifier, "classify", lambda *a, **k: (_ for _ in ()).throw(AssertionError("Haiku must not be called")))
    _level_world(3000)
    monkeypatch.setattr(fchat.gate, "enabled_for", lambda identity: True)
    out = fchat.start_turn(ELIYAHU, "אני מפריש עכשיו 3500", intent=LEVEL)
    assert "₪500" in out and "אשר" in out


def test_invalid_structured_intent_is_not_understood_and_no_model_is_called(monkeypatch):
    import llm_fallback
    monkeypatch.setattr(llm_fallback, "call_anthropic_text", _boom)
    monkeypatch.setattr(fchat.gate, "enabled_for", lambda identity: True)
    _level_world(3000)
    out = fchat.start_turn(ELIYAHU, "x", intent={"action": "bogus"})
    assert "כפתורים" in out and not conv.has_pending(ELIYAHU)


# ═══════════════ standing-order savings: plan (level) vs actual deposits; a missed month = a visible gap ═══════════════
def test_deposits_vs_level_gap_this_month_and_last_month():
    DB[Tables.FIN_GOALS] = [_savings_goal()]
    DB[Tables.FIN_EVENTS] = [
        event("l1", "recS", ELI, 3000, kind="monthly_recurring", day="2026-08-01"),      # level 3,000 from August
        event("l2", "recS", ELI, 2000, kind="monthly_recurring", day="2026-10-02"),      # raised to 5,000 this month
        event("d1", "recS", ELI, 3000, kind="one_time", day="2026-09-10"),               # September fully deposited? no: 3,000 of 3,000
        event("d2", "recS", ELI, 1200, kind="one_time", day="2026-10-04")]               # this month so far
    row = rows_of(service.overview(ELIYAHU, TODAY))["recS"]
    assert (row["deposited_month"], row["gap_month"]) == (1200, 3800)                    # 5,000 plan - 1,200 deposited
    assert (row["gap_last_month"]) == 0                                                  # September met its 3,000
    card = service.overview(ELIYAHU, TODAY)["summary"]["savings"]
    assert (card["deposited_month"], card["gap_month"]) == (1200, 3800)


def test_missed_month_is_a_gap_and_does_not_inflate_this_months_level():
    DB[Tables.FIN_GOALS] = [_savings_goal()]
    DB[Tables.FIN_EVENTS] = [event("l1", "recS", ELI, 5000, kind="monthly_recurring", day="2026-08-01"),
                             event("d1", "recS", ELI, 1000, kind="one_time", day="2026-09-12")]      # September short by 4,000
    row = rows_of(service.overview(ELIYAHU, TODAY))["recS"]
    assert row["gap_last_month"] == 4000
    assert row["actual"] == 5000 and row["target"] == 5000                               # level untouched: no automatic catch-up


def test_make_up_deposit_counts_in_the_month_it_is_made_not_backwards():
    DB[Tables.FIN_GOALS] = [_savings_goal()]
    DB[Tables.FIN_EVENTS] = [event("l1", "recS", ELI, 5000, kind="monthly_recurring", day="2026-08-01"),
                             event("d1", "recS", ELI, 9000, kind="one_time", day="2026-10-03")]      # 5,000 + 4,000 make-up
    row = rows_of(service.overview(ELIYAHU, TODAY))["recS"]
    assert row["deposited_month"] == 9000 and row["gap_month"] == 0 and row["gap_last_month"] == 5000


def test_deposit_is_logged_as_one_time_on_the_savings_goal():
    DB[Tables.FIN_GOALS] = [_savings_goal()]
    DB[Tables.FIN_EVENTS] = []
    dep = {"action": "log_progress", "goal_hint": "הפרשה", "kind": "one_time", "amount": 5000}
    ex = Ex(classify={"הפקדתי החודש 5000": dep})
    r = run(ex, ELIYAHU, "הפקדתי החודש 5000")
    assert r.state == "review"
    (w,) = run(ex, ELIYAHU, "אשר").snapshot["writes"]
    assert w["fields"]["Kind"] == "one_time" and w["fields"]["Amount"] == 5000


# ───────── Loans & debt (read-only, owner-scoped) ─────────
from airtable_schema import LoanFields as LF
from core.financial_control import loans as fcc_loans


def loan(lid, owner=ELI, **f):
    return {"id": lid, "fields": {LF.NAME: lid, "Owner": [owner], **f}}


def seed_loans():
    DB[Tables.LOANS] = [
        loan("recL1", **{LF.LOAN_TYPE: "פרטית", LF.EARLY_CLOSURE: 100000, LF.INTEREST_RATE: 6.0, LF.MONTHLY_PAYMENT: 2000,
                         LF.PAYMENTS_LEFT: 60, LF.AMOUNT: 150000, LF.EARLY_FEE: "אין", LF.RELATED_ASSET: ["recA1"]}),
        loan("recL2", **{LF.LOAN_TYPE: "עסקית", LF.EARLY_CLOSURE: 50000, LF.INTEREST_RATE: 12.0, LF.MONTHLY_PAYMENT: 1000,
                         LF.PAYMENTS_LEFT: 60, LF.AMOUNT: 60000}),
        loan("recL3"),                                                                  # partial: mortgage with no details
        loan("recL4", **{LF.EARLY_CLOSURE: 7000, LF.STATUS: "Paid Off", LF.MONTHLY_PAYMENT: 500}),
        loan("recLX", owner=AVI, **{LF.EARLY_CLOSURE: 999999, LF.MONTHLY_PAYMENT: 77777}),
    ]
    DB["Assets"] = [{"id": "recA1", "fields": {"Name": "דירה", "Owner": [ELI]}},
                    {"id": "recA2", "fields": {"Name": "נכס של אבי", "Owner": [AVI]}}]


def loans_for(who=ELIYAHU):
    return service.overview(who, TODAY)["loans"]


def test_loans_owner_isolation():
    seed_loans()
    body = loans_for()
    assert {i["id"] for i in body["items"]} == {"recL1", "recL2", "recL3", "recL4"}
    assert "999999" not in str(body) and "77777" not in str(body)
    assert {i["id"] for i in loans_for(AVI_I)["items"]} == {"recLX"}


def test_loans_summary_active_only_and_totals():
    seed_loans()
    s = loans_for()["summary"]
    assert s["total_active_loans"] == 3                      # Paid Off excluded
    assert s["total_early_closure_balance"] == 150000        # 7000 of the closed loan not included
    assert s["total_monthly_payments"] == 3000 == s["total_monthly_cash_freed_if_all_closed"]
    assert s["total_original_amount"] == 210000
    assert s["incomplete_count"] == 1                        # only the empty mortgage lacks data


def test_loans_weighted_interest_ignores_missing():
    seed_loans()
    s = loans_for()["summary"]
    assert s["weighted_average_interest_rate"] == round((6 * 100000 + 12 * 50000) / 150000, 2) == 8.0
    assert s["coverage"]["interest_rate"] == 2               # the empty mortgage is not averaged in as 0


def test_loans_missing_values_stay_none_not_zero():
    seed_loans()
    l3 = next(i for i in loans_for()["items"] if i["id"] == "recL3")
    for k in ("early_closure_balance", "interest_rate", "monthly_payment", "months_remaining",
              "estimated_total_remaining_payments", "estimated_future_cost", "monthly_cash_freed_if_closed", "annual_interest_cost"):
        assert l3[k] is None
    assert l3["loan_type"] is None and l3["related_asset"] is None
    assert fcc_loans.summarize([fcc_loans.loan_item(loan("recE"), TODAY)])["total_early_closure_balance"] is None


def test_loans_future_cost_and_exactness():
    seed_loans()
    items = {i["id"]: i for i in loans_for()["items"]}
    l1, l2 = items["recL1"], items["recL2"]
    assert l1["estimated_total_remaining_payments"] == 120000 and l1["estimated_future_cost"] == 20000
    assert l1["future_cost_exact"] is True                   # fee "אין" is a known zero
    assert l2["estimated_future_cost"] == 10000 and l2["future_cost_exact"] is False   # fee blank -> not exact
    assert fcc_loans.parse_fee("2%") == (None, False) and fcc_loans.parse_fee("500 ₪") == (500.0, True)


def test_loans_types_and_uncategorized_breakdown():
    seed_loans()
    s = loans_for()["summary"]
    assert set(s["by_type"]) == {"פרטית", "עסקית", fcc_loans.UNCLASSIFIED}
    assert s["by_type"]["פרטית"]["early_closure_balance"] == 100000
    assert s["by_type"][fcc_loans.UNCLASSIFIED]["early_closure_balance"] is None


def test_loans_related_asset_name_only_from_own_assets():
    seed_loans()
    body = loans_for()
    l1 = next(i for i in body["items"] if i["id"] == "recL1")
    assert l1["related_asset"] == "recA1" and l1["related_asset_name"] == "דירה"
    assert body["summary"]["by_asset"][0]["asset_name"] == "דירה" and len(body["summary"]["by_asset"]) == 1
    assert "נכס של אבי" not in str(body)


def test_loans_rankings_are_orderings_unknown_last():
    seed_loans()
    r = loans_for()["rankings"]
    assert r["high_interest"] == ["recL2", "recL1", "recL3"]
    assert r["cash_freed"] == ["recL1", "recL2", "recL3"]
    assert r["small_balance"] == ["recL2", "recL1", "recL3"]


def test_loans_goal_passthrough_does_not_touch_ssot():
    seed_loans()
    DB[Tables.FIN_GOALS].append(goal("recDebt", "סגירת הלוואות", ELI, 700000, **{GF.CALC_METHOD: "cumulative", GF.CATEGORY: "debt"}))
    DB[Tables.FIN_EVENTS].append(event("recDE", "recDebt", ELI, 100000))
    g = loans_for()["goal"]
    assert g["target"] == 700000 and g["closed"] == 100000 and g["remaining"] == 600000 and g["active_closure_balance"] == 150000


def test_loans_http_payload_isolated(monkeypatch):
    seed_loans()
    body = http(monkeypatch, AVI_I).get("/api/fcc/overview", headers=H).get_json()
    assert [i["id"] for i in body["loans"]["items"]] == ["recLX"] and "100000" not in str(body["loans"])


def test_loans_status_unknown_kept_visible_and_counted():
    DB[Tables.LOANS] = [
        loan("recK", **{LF.ACTIVE: True, LF.EARLY_CLOSURE: 1000, LF.MONTHLY_PAYMENT: 100}),              # confirmed active
        loan("recU1", **{LF.EARLY_CLOSURE: 2000, LF.MONTHLY_PAYMENT: 200}),                              # unchecked, no status
        loan("recU2", **{LF.STATUS: "Current", LF.EARLY_CLOSURE: 3000}),                                 # unchecked, not Paid Off
        loan("recP", **{LF.STATUS: "Paid Off", LF.EARLY_CLOSURE: 9000}),                                 # closed: not unknown, not shown active
    ]
    body = loans_for()
    flags = {i["id"]: i["status_unknown"] for i in body["items"]}
    assert flags == {"recK": False, "recU1": True, "recU2": True, "recP": False}
    s = body["summary"]
    assert s["unknown_status_count"] == 2
    assert s["total_active_loans"] == 3 and s["total_early_closure_balance"] == 6000   # unknown-status loans are included
    assert s["total_monthly_payments"] == 300


# ───────── Early-payoff engine (read-only) ─────────
from core.financial_control import payoff as fcc_payoff


def pl(lid, closure=None, rate=None, monthly=None, left=None, owner=ELI, **extra):
    f = {}
    if closure is not None: f[LF.EARLY_CLOSURE] = closure
    if rate is not None: f[LF.INTEREST_RATE] = rate
    if monthly is not None: f[LF.MONTHLY_PAYMENT] = monthly
    if left is not None: f[LF.PAYMENTS_LEFT] = left
    f.update(extra)
    return loan(lid, owner, **f)


def seed_payoff():
    DB[Tables.LOANS] = [
        pl("recP1", 100000, 6.0, 2000, 60, **{LF.EARLY_FEE: "אין"}),     # big, low rate, high payment, long
        pl("recP2", 50000, 12.0, 1800, 36, **{LF.EARLY_FEE: "אין"}),     # mid
        pl("recP3", 10000, 9.0, 375, 30, **{LF.EARLY_FEE: "אין"}),       # small, short
        pl("recPX", 5000, 20.0, 9999, 99, owner=AVI),                     # someone else's
    ]


def payoff_rows(who=ELIYAHU):
    return {r["id"]: r for r in loans_for(who)["payoff"]["items"]}


def test_payoff_scores_are_min_max_normalised_and_closure_is_inverse():
    seed_payoff()
    r = payoff_rows()
    assert r["recP2"]["scores"]["interest"] == 100.0 and r["recP1"]["scores"]["interest"] == 0.0     # 12 high, 6 low
    assert r["recP1"]["scores"]["cash"] == 100.0 and r["recP3"]["scores"]["cash"] == 0.0
    assert r["recP3"]["scores"]["closure"] == 100.0 and r["recP1"]["scores"]["closure"] == 0.0       # smaller amount = higher
    assert r["recP1"]["scores"]["time"] == 100.0 and r["recP3"]["scores"]["time"] == 0.0             # longer remaining = higher
    assert r["recP2"]["scores"]["interest"] == 100.0 and r["recP3"]["scores"]["interest"] == 50.0    # (9-6)/(12-6)


def test_payoff_balanced_score_uses_the_documented_weights():
    seed_payoff()
    r = payoff_rows()["recP3"]
    s = r["scores"]
    expected = 0.30 * s["interest"] + 0.30 * s["cash"] + 0.25 * s["closure"] + 0.15 * s["time"]
    assert r["balanced_score"] == round(expected, 2)
    assert fcc_payoff.WEIGHTS == {"interest": 0.30, "cash": 0.30, "closure": 0.25, "time": 0.15}
    assert r["score_coverage"] == 1.0 and r["score_coverage_label"] == "4/4" and r["missing_factors"] == [] and r["partial"] is False


def test_payoff_missing_factor_is_renormalised_not_zero_and_reports_coverage():
    seed_payoff()
    DB[Tables.LOANS].append(pl("recP4", 20000, None, 500, 20))            # no interest rate
    r = payoff_rows()["recP4"]
    assert r["scores"]["interest"] is None and r["missing_factors"] == ["interest"] and r["partial"] is True
    assert r["score_coverage"] == 0.75 and r["score_coverage_label"] == "3/4"
    s = r["scores"]
    expected = (0.30 * s["cash"] + 0.25 * s["closure"] + 0.15 * s["time"]) / (0.30 + 0.25 + 0.15)    # weights renormalised over known
    assert r["balanced_score"] == round(expected, 2)
    assert payoff_rows()["recP1"]["scores"]["interest"] == 0.0           # the missing rate did not distort the others


def test_payoff_partial_data_loan_is_listed_but_not_fabricated():
    seed_payoff()
    DB[Tables.LOANS].append(loan("recEmpty"))                             # the empty mortgage
    r = payoff_rows()["recEmpty"]
    assert r["balanced_score"] is None and r["score_coverage"] == 0.0 and r["score_coverage_label"] == "0/4"
    assert set(r["missing_factors"]) == {"interest", "cash", "closure", "time"}
    assert r["cost_saving"] is None and r["estimated_future_cost"] is None and r["data_issue"] is None
    ranks = loans_for()["payoff"]["rankings"]
    assert all(ranks[k][-1] == "recEmpty" for k in ranks)                 # unknown always last


def test_misleading_percentage_metrics_are_gone_from_the_contract():
    seed_payoff()
    body = loans_for()["payoff"]
    text = str(body)
    for gone in ("annualized_cash_release", "monthly_cash_efficiency", "cash_release_efficiency", "efficiency"):
        assert gone not in text
    assert set(body["rankings"]) == {"balanced", "interest", "cash", "savings"}
    assert fcc_payoff.STRATEGIES == ("balanced", "interest", "cash", "savings")


def test_payoff_cost_formulas_gross_net_and_interest_burden():
    seed_payoff()
    r = payoff_rows()
    assert r["recP1"]["estimated_remaining_payments"] == 2000 * 60
    assert r["recP1"]["estimated_future_cost"] == 120000 - 100000          # monthly × remaining − closure
    assert r["recP1"]["cost_saving"] == 20000 and r["recP1"]["cost_saving_exact"] is True      # fee "אין" is a known zero
    assert r["recP1"]["annual_interest_burden"] == 100000 * 6.0 / 100       # closure × rate
    assert r["recP2"]["estimated_future_cost"] == 1800 * 36 - 50000 == 14800


def test_cost_saving_is_net_of_a_known_fee_and_estimated_when_the_fee_is_unknown():
    DB[Tables.LOANS] = [pl("recF", 100000, 6.0, 2000, 60, **{LF.EARLY_FEE: "3000"}),     # known numeric fee
                        pl("recU", 100000, 6.0, 2000, 60),                                  # fee unknown
                        pl("recT", 100000, 6.0, 2000, 60, **{LF.EARLY_FEE: "2%"}),         # non-numeric fee = unknown
                        pl("recZ", 100000, 6.0, 2000, 60, **{LF.EARLY_FEE: "25000"})]      # fee larger than the gross cost
    r = payoff_rows()
    assert r["recF"]["estimated_future_cost"] == 20000 and r["recF"]["cost_saving"] == 17000 and r["recF"]["cost_saving_exact"] is True
    for k in ("recU", "recT"):
        assert r[k]["cost_saving"] == 20000 and r[k]["cost_saving_exact"] is False       # shown as an estimate, never claimed as net
    assert r["recZ"]["no_saving"] is True and r["recZ"]["cost_saving"] == 0.0           # never a positive "saving" after the fee


def test_hard_inconsistency_blocks_cost_and_the_savings_ranking():
    DB[Tables.LOANS] = [pl("recI", 90000, 5.0, 1000, 60),                                  # 60×1000 < 90000
                        pl("recK", 1000, 5.0, 50, 12, **{LF.EARLY_FEE: "500"}),           # 600 ≥ 1000? no: 600 < 1000+500
                        pl("recOk", 50000, 6.0, 1000, 60)]
    r = payoff_rows()
    for k in ("recI", "recK"):
        assert r[k]["data_inconsistent"] is True and r[k]["data_issue"] == "inconsistent"
        assert r[k]["estimated_future_cost"] is None and r[k]["cost_saving"] is None and r[k]["data_suspicious"] is False
        assert r[k]["amount_to_close"] is not None and r[k]["monthly_cash_freed"] is not None    # the four facts stay visible
    ranks = loans_for()["payoff"]["rankings"]
    assert ranks["savings"][0] == "recOk" and set(ranks["savings"][1:]) == {"recI", "recK"}     # excluded = after every loan with a saving
    assert r["recOk"]["data_issue"] is None


def test_a_known_fee_above_the_continuation_cost_is_no_saving_not_bad_data():
    DB[Tables.LOANS] = [pl("recE", 1000, 5.0, 105, 10, **{LF.EARLY_FEE: "300"}),          # cost 50, fee 300 -> closing loses money
                        pl("recN", 1000, 5.0, 105, 10, **{LF.EARLY_FEE: "אין"})]          # cost 50, no fee -> saves 50
    r = payoff_rows()
    assert r["recE"]["data_inconsistent"] is False and r["recE"]["estimated_future_cost"] == 50.0
    assert r["recE"]["no_saving"] is True and r["recE"]["cost_saving"] == 0.0 and r["recE"]["cost_saving_exact"] is True
    assert r["recN"]["no_saving"] is False and r["recN"]["cost_saving"] == 50.0
    assert loans_for()["payoff"]["rankings"]["savings"] == ["recN", "recE"]               # a zero saving ranks below a real one


def test_suspicious_loans_keep_their_facts_but_leave_the_cost_and_savings_ranking():
    DB[Tables.LOANS] = [pl("recLow", 100000, 6.0, 2300, 46, **{LF.EARLY_FEE: "אין"}),     # cost 5,800 vs rough 11,500 -> 0.50 ok
                        pl("recTooLow", 118400, 6.0, 2600, 46, **{LF.EARLY_FEE: "אין"}),   # cost 1,200 vs rough ~13,600 -> suspicious
                        pl("recTooHigh", 10000, 6.0, 1000, 30, **{LF.EARLY_FEE: "אין"}),  # cost 20,000 vs rough 75 -> suspicious
                        pl("recFine", 55342, 12.05, 1189, 63, **{LF.EARLY_FEE: "אין"})]   # ~ the rough estimate
    r = payoff_rows()
    assert r["recLow"]["data_suspicious"] is False and r["recFine"]["data_suspicious"] is False
    for k in ("recTooLow", "recTooHigh"):
        assert r[k]["data_suspicious"] is True and r[k]["data_issue"] == "suspicious" and r[k]["data_inconsistent"] is False
        assert r[k]["estimated_future_cost"] is None and r[k]["cost_saving"] is None
        assert r[k]["amount_to_close"] is not None and r[k]["interest_rate"] == 6.0 and r[k]["monthly_cash_freed"] is not None
        assert r[k]["months_remaining"] is not None                                          # the four facts stay
    sav = loans_for()["payoff"]["rankings"]["savings"]
    assert set(sav[:2]) == {"recLow", "recFine"} and set(sav[2:]) == {"recTooLow", "recTooHigh"}


def test_corrected_hapoalim_is_consistent_and_not_flagged():
    DB[Tables.LOANS] = [pl("recHap", 118400, 6.0, 2816.16, 45, **{LF.EARLY_FEE: "אין"})]
    r = payoff_rows()["recHap"]
    assert r["data_issue"] is None and round(r["estimated_future_cost"], 2) == round(2816.16 * 45 - 118400, 2)
    old = pl("recHapOld", 118400, 6.25, 2600, 45, **{LF.EARLY_FEE: "אין"})                  # the pre-correction data
    DB[Tables.LOANS] = [old]
    assert payoff_rows()["recHapOld"]["data_inconsistent"] is True


def test_payoff_rankings_by_each_strategy():
    seed_payoff()
    rk = loans_for()["payoff"]["rankings"]
    assert rk["interest"] == ["recP2", "recP3", "recP1"]
    assert rk["cash"] == ["recP1", "recP2", "recP3"]
    assert rk["savings"] == ["recP1", "recP2", "recP3"]                                 # 20,000 > 14,800 > 1,250
    bal = {i: r["balanced_score"] for i, r in payoff_rows().items()}
    assert rk["balanced"] == sorted(bal, key=lambda i: -bal[i])


def scen(budget, who=ELIYAHU):
    return service.loan_scenarios(who, budget, TODAY)


def test_budget_scenario_closes_whole_loans_in_strategy_order():
    seed_payoff()
    out = scen(60000)["strategies"]
    s = out["interest"]                       # interest order P2(50000) -> P3(10000) -> P1(100000 does not fit)
    assert [c["id"] for c in s["closed"]] == ["recP2", "recP3"] and s["closed_count"] == 2
    assert s["used"] == 60000 and s["remaining_budget"] == 0 and s["debt_removed"] == 60000
    assert s["monthly_cash_released"] == 2175 and s["skipped_over_budget"] == ["recP1"]
    assert s["future_cost_saved"] == 14800 + 1250 and s["future_cost_saved_exact"] is True
    assert [c["id"] for c in out["cash"]["closed"]] == ["recP2", "recP3"]          # P1 (100000) skipped whole, never partial


def test_budget_exact_boundary_is_included():
    seed_payoff()
    assert scen(10000)["strategies"]["cash"]["closed"][0]["id"] == "recP3"
    assert scen(10000)["strategies"]["cash"]["remaining_budget"] == 0
    assert scen(9999.99)["strategies"]["cash"]["closed_count"] == 0


def test_budget_insufficient_closes_nothing_and_never_partial():
    seed_payoff()
    r = scen(5000)["strategies"]["balanced"]
    assert r["closed_count"] == 0 and r["used"] == 0 and r["remaining_budget"] == 5000
    assert r["monthly_cash_released"] == 0 and r["debt_removed"] == 0
    assert set(r["skipped_over_budget"]) == {"recP1", "recP2", "recP3"}


def test_budget_with_partial_data_loan_excludes_unknown_amount_and_flags_partial():
    seed_payoff()
    DB[Tables.LOANS].append(loan("recEmpty"))
    DB[Tables.LOANS].append(pl("recNoPay", 1000, 7.0))                    # closable but no monthly payment / months
    r = scen(200000)["strategies"]["interest"]
    assert "recEmpty" in r["excluded_unknown_amount"]
    assert any(c["id"] == "recNoPay" for c in r["closed"]) and r["partial"] is True
    assert r["monthly_cash_released"] == 4175                              # the unknown payment is not guessed


def test_savings_strategy_and_optimal_modes_never_close_a_loan_whose_metric_is_unknown():
    DB[Tables.LOANS] = [pl("recOk", 50000, 6.0, 1000, 60), pl("recBad", 20000, 6.0, 100, 10),         # recBad: inconsistent -> no saving
                        pl("recNoPay", 1000, 7.0)]                                                     # no monthly payment, no saving
    out = scen(500000)
    sv = out["strategies"]["savings"]
    assert [c["id"] for c in sv["closed"]] == ["recOk"] and set(sv["excluded_no_data"]) == {"recBad", "recNoPay"}
    assert {c["id"] for c in out["optimal"]["saved"]["closed"]} == {"recOk"}
    assert {c["id"] for c in out["optimal"]["cash"]["closed"]} == {"recOk", "recBad"}                 # cash needs a monthly payment: both have one
    assert "recNoPay" in out["optimal"]["cash"]["excluded_no_data"] and "recNoPay" not in {c["id"] for c in out["optimal"]["cash"]["closed"]}
    interest = out["strategies"]["interest"]                                                          # other strategies still use them as plain fills
    assert {"recOk", "recBad", "recNoPay"} == {c["id"] for c in interest["closed"]}


def test_budget_optimal_combination_matches_or_beats_every_greedy_strategy():
    seed_payoff()
    out = scen(150000)
    best_cash, best_saved = out["optimal"]["cash"], out["optimal"]["saved"]
    assert best_cash["used"] <= 150000 and best_saved["used"] <= 150000
    assert best_cash["monthly_cash_released"] == 3800 and {c["id"] for c in best_cash["closed"]} == {"recP1", "recP2"}
    assert best_cash["monthly_cash_released"] >= max(s["monthly_cash_released"] for s in out["strategies"].values())
    assert best_saved["future_cost_saved"] == 20000 + 14800
    assert best_saved["future_cost_saved"] >= max(s["future_cost_saved"] or 0 for s in out["strategies"].values())
    assert out["strategies"]["interest"]["monthly_cash_released"] == 2175       # greedy by rate is strictly worse here


def test_budget_700k_preset_closes_everything_and_leaves_the_rest():
    seed_payoff()
    r = scen(700000)["strategies"]["balanced"]
    assert r["closed_count"] == 3 and r["debt_removed"] == 160000 and r["remaining_budget"] == 540000
    assert r["monthly_cash_released"] == 4175


def test_budget_scenario_owner_isolation_and_http(monkeypatch):
    seed_payoff()
    avi = scen(10 ** 7, AVI_I)["strategies"]["balanced"]
    assert [c["id"] for c in avi["closed"]] == ["recPX"] and avi["used"] == 5000
    mine = http(monkeypatch, ELIYAHU)
    ok = mine.get("/api/fcc/loans/scenario?budget=60000", headers=H)
    assert ok.status_code == 200 and "recPX" not in str(ok.get_json()) and "9999" not in str(ok.get_json())
    assert mine.get("/api/fcc/loans/scenario?budget=abc", headers=H).status_code == 400
    assert mine.get("/api/fcc/loans/scenario?budget=-5", headers=H).status_code == 400
    assert http(monkeypatch, ELIYAHU, flag=False).get("/api/fcc/loans/scenario?budget=1", headers=H).status_code == 404


def test_payoff_overview_payload_owner_isolation():
    seed_payoff()
    body = loans_for()
    assert {r["id"] for r in body["payoff"]["items"]} == {"recP1", "recP2", "recP3"}
    assert "recPX" not in str(body["payoff"])


# ───────── Payoff engine — numeric truth checks & budget invariants ─────────
import random


def _rows(specs):
    """specs: [(id, closure, rate, monthly, left)] -> engine metric rows via the real loan_item path."""
    recs = [pl(i, c, r, m, n) for i, c, r, m, n in specs]
    return fcc_payoff.metrics([fcc_loans.loan_item(r, TODAY) for r in recs])


def test_huge_balance_small_payment_has_a_tiny_saving_share_and_no_percentage_metric():
    rows = {r["id"]: r for r in _rows([("recHuge", 1234567, 12.05, 1189, 63), ("recSmall", 3060, 12.85, 784, 4)])}
    huge = rows["recHuge"]
    assert "annualized_cash_release" not in huge and "monthly_cash_efficiency" not in huge        # no 307% / 1.16% style metric anywhere
    assert huge["monthly_cash_freed"] == 1189 and huge["amount_to_close"] == 1234567              # only the plain facts
    assert huge["data_inconsistent"] is True                                                       # 63×1,189 = 74,907 < 1,234,567


def _check_invariants(result, rows, budget, order=None):
    by_id = {r["id"]: r for r in rows}
    closed_sum = round(sum(c["amount_to_close"] for c in result["closed"]), 2)
    assert result["used"] == closed_sum == result["debt_removed"]
    assert result["used"] <= budget + 1e-9                                         # never over budget
    assert round(result["used"] + result["remaining_budget"], 2) == round(budget, 2)   # used + remaining == budget
    assert result["remaining_budget"] >= -1e-9
    assert all(c["amount_to_close"] <= budget + 1e-9 for c in result["closed"])    # no loan bigger than the budget is ever closed
    assert len({c["id"] for c in result["closed"]}) == result["closed_count"]
    if order is not None:                                                          # replay the greedy walk: each pick fit what was left
        left = float(budget)
        picked = {c["id"] for c in result["closed"]}
        for iid in order:
            amt = by_id[iid]["amount_to_close"]
            if amt is None:
                assert iid in result["excluded_unknown_amount"]
            elif iid in result["excluded_no_data"]:
                assert iid not in picked                                           # strategy metric unknown: never a filler pick
            elif iid in picked:
                assert amt <= left + 1e-9
                left -= amt
            else:
                assert amt > left + 1e-9 and iid in result["skipped_over_budget"]  # skipped only because it did not fit what remained


def test_no_scenario_may_exceed_budget_700k_with_a_loan_larger_than_the_budget():
    rows = _rows([("recBig", 1234567, 12.05, 1189, 63), ("recHap", 118400, 6.25, 2600, 45), ("recMax", 94549, 6.96, 1389, 86),
                  ("recSmall", 3060, 12.85, 784, 4), ("recKal", 55342, 12.05, 1189, 63)])
    ranks = fcc_payoff.rankings(rows)
    out = fcc_payoff.scenarios(rows, 700000)
    for strat, result in out["strategies"].items():
        _check_invariants(result, rows, 700000, ranks[strat])
        assert "recBig" not in {c["id"] for c in result["closed"]}
        assert "recBig" in result["skipped_over_budget"] or "recBig" in result["excluded_no_data"]       # too big, or no saving data
        expected = 94549 + 3060 + 55342 + (0 if strat == "savings" else 118400)        # recHap has no saving data (45×2,600 < closure): never a savings pick
        assert result["used"] == expected and result["remaining_budget"] == 700000 - result["used"]
    for kind, result in out["optimal"].items():
        _check_invariants(result, rows, 700000)
        assert "recBig" not in {c["id"] for c in result["closed"]}


def test_budget_invariants_hold_for_random_portfolios_in_every_mode():
    rnd = random.Random(20261007)
    for _ in range(60):
        specs = [(f"rec{n}", rnd.choice([None, rnd.randint(500, 400000)]), rnd.choice([None, round(rnd.uniform(2, 20), 2)]),
                  rnd.choice([None, rnd.randint(50, 5000)]), rnd.choice([None, rnd.randint(1, 120)])) for n in range(rnd.randint(1, 9))]
        rows = _rows([(i, c, r, m, n) for i, c, r, m, n in specs if c is not None] or [("recOnly", 1000, 5, 100, 12)])
        ranks = fcc_payoff.rankings(rows)
        for budget in (1, 999.5, 25000, 123456.78, 700000):
            out = fcc_payoff.scenarios(rows, budget)
            for strat, result in out["strategies"].items():
                _check_invariants(result, rows, budget, ranks[strat])
            for result in out["optimal"].values():
                if result is not None:
                    _check_invariants(result, rows, budget)


def test_optimal_combination_never_exceeds_budget_even_when_it_is_tight():
    rows = _rows([("recX", 60000, 5, 900, 100), ("recY", 40000, 6, 700, 80), ("recZ", 35000, 7, 800, 60)])
    for budget in (74999, 75000, 75001, 100000, 134999):
        for result in fcc_payoff.scenarios(rows, budget)["optimal"].values():
            _check_invariants(result, rows, budget)
    assert fcc_payoff.optimal(rows, 75000, "cash")["used"] == 75000          # exact fit is allowed
    assert fcc_payoff.optimal(rows, 74999, "cash")["used"] <= 74999


def test_budget_used_plus_remaining_equals_budget_through_the_service_and_http(monkeypatch):
    seed_payoff()
    for budget in (5000, 10000, 60000, 150000, 700000):
        for result in list(scen(budget)["strategies"].values()) + [v for v in scen(budget)["optimal"].values() if v]:
            assert round(result["used"] + result["remaining_budget"], 2) == budget and result["used"] <= budget
    body = http(monkeypatch, ELIYAHU).get("/api/fcc/loans/scenario?budget=700000", headers=H).get_json()
    assert all(round(s["used"] + s["remaining_budget"], 2) == 700000 for s in body["strategies"].values())


# ───────── Assets & equity tab (read-only) ─────────
from airtable_schema import AssetFields as AF


def asset(aid, name, owner=ELI, **f):
    return {"id": aid, "fields": {AF.NAME: name, "Owner": [owner], **f}}


def seed_assets():
    DB["Assets"] = [
        asset("recAH", "בית", **{AF.TYPE: {"name": "Residential"}, AF.STATUS: {"name": "פעיל"}, AF.VALUE: 5000000, AF.MORTGAGE: 1200000,
                                 AF.EQUITY: 3800000, AF.MY_EQUITY: 3800000, AF.OWNERSHIP_PCT: 100, AF.MONTHLY_INCOME: 0}),
        asset("recAL", "קרקע", **{AF.TYPE: {"name": "Land"}, AF.VALUE: 1200000, AF.MORTGAGE: 0, AF.EQUITY: 1200000, AF.MY_EQUITY: 1200000}),
        asset("recAE", "נכס ריק"),                                                   # nothing filled in
        asset("recAX", "נכס של אבי", owner=AVI, **{AF.VALUE: 99999999}),
    ]
    DB[Tables.LOANS] = [
        loan("recL1", **{LF.EARLY_CLOSURE: 100000, LF.MONTHLY_PAYMENT: 2000, LF.RELATED_ASSET: ["recAH"]}),
        loan("recL2", **{LF.EARLY_CLOSURE: 50000, LF.MONTHLY_PAYMENT: 1000}),                       # not linked to any asset
        loan("recL3", **{LF.STATUS: "Paid Off", LF.EARLY_CLOSURE: 7000, LF.RELATED_ASSET: ["recAH"]}),   # closed: not counted
    ]


def assets_for(who=ELIYAHU):
    return service.overview(who, TODAY)["assets"]


def test_assets_owner_isolation():
    seed_assets()
    body = assets_for()
    assert {i["id"] for i in body["items"]} == {"recAH", "recAL", "recAE"}
    assert "99999999" not in str(body) and "נכס של אבי" not in str(body)
    assert {i["id"] for i in assets_for(AVI_I)["items"]} == {"recAX"}


def test_assets_values_are_shown_as_stored_and_unknown_stays_none():
    seed_assets()
    items = {i["id"]: i for i in assets_for()["items"]}
    h = items["recAH"]
    assert (h["current_value"], h["mortgage_balance"], h["equity"], h["my_equity"], h["ownership_pct"]) == (5000000, 1200000, 3800000, 3800000, 100)
    e = items["recAE"]
    assert all(e[k] is None for k in ("current_value", "mortgage_balance", "equity", "my_equity", "monthly_income", "ownership_pct", "asset_type"))
    assert e["linked_loans"] == [] and e["linked_debt"] is None


def test_assets_linked_loans_are_active_only_and_separate_from_the_recorded_mortgage():
    seed_assets()
    h = {i["id"]: i for i in assets_for()["items"]}["recAH"]
    assert [l["id"] for l in h["linked_loans"]] == ["recL1"]                       # the Paid Off loan is not linked debt
    assert h["linked_debt"] == 100000 and h["linked_monthly_payments"] == 2000
    assert h["mortgage_balance"] == 1200000                                        # kept apart: never summed with linked debt


def test_assets_summary_totals_skip_unknown_and_report_coverage():
    seed_assets()
    s = assets_for()["summary"]
    assert s["count"] == 3 and s["total_value"] == 6200000 and s["total_equity"] == 5000000 and s["total_my_equity"] == 5000000
    assert s["total_mortgage"] == 1200000 and s["coverage"]["value"] == 2 and s["coverage"]["mortgage"] == 2
    assert s["linked_loans_count"] == 1 and s["linked_loans_debt"] == 100000
    assert s["unlinked_loans_count"] == 1 and s["unlinked_loans_debt"] == 50000      # debt that belongs to no asset
    DB["Assets"] = [asset("recAE", "נכס ריק")]
    e = assets_for()["summary"]
    assert e["total_value"] is None and e["total_equity"] is None and e["total_monthly_income"] is None


def test_assets_http_payload_isolated(monkeypatch):
    seed_assets()
    body = http(monkeypatch, AVI_I).get("/api/fcc/overview", headers=H).get_json()
    assert [i["id"] for i in body["assets"]["items"]] == ["recAX"] and "5000000" not in str(body["assets"])


# ═══════════════ Phase 2 — closing a loan (one confirmation: Payment Status = Paid Off + one debt-goal event) ═══════════════
def seed_close():
    DB[Tables.FIN_GOALS] = [goal("recGD", "סגירת חובות", ELI, 700000, **{GF.CATEGORY: "debt", GF.CALC_METHOD: "cumulative"}),
                            goal("recGAV", "חוב של אבי", AVI, 5000, **{GF.CATEGORY: "debt"})]
    DB[Tables.FIN_EVENTS] = []
    DB[Tables.LOANS] = [
        loan("recC1", **{LF.NAME: "פועלים", LF.EARLY_CLOSURE: 118400, LF.MONTHLY_PAYMENT: 2816.16, LF.PAYMENTS_LEFT: 45}),
        loan("recC2", **{LF.NAME: "בלי יתרה", LF.MONTHLY_PAYMENT: 500}),
        loan("recC3", **{LF.NAME: "סגורה", LF.STATUS: "Paid Off", LF.EARLY_CLOSURE: 1000}),
        loan("recCX", owner=AVI, **{LF.NAME: "של אבי", LF.EARLY_CLOSURE: 77777}),
    ]


def start_close(loan_id="recC1", who=ELIYAHU):
    return conv.start_loan_close(who, loan_id, today=TODAY)


def test_close_review_shows_everything_that_will_change_and_writes_nothing(monkeypatch):
    seed_close()
    r = start_close()
    assert r.state == "review" and r.entity == "fcc_loan_close"
    for part in ("סגירת הלוואה", "פועלים", "₪118,400", "(הוסק)", "Paid Off", "סגירת חובות"):
        assert part in r.message
    assert r.snapshot is None                                            # nothing frozen or written yet


def test_close_confirm_freezes_exactly_two_writes_status_and_one_event():
    seed_close()
    start_close()
    r = conv.handle_turn(ELIYAHU, "אשר", extractor=Ex(), today=TODAY)
    assert r.state == "confirmed"
    status, ev = r.snapshot["writes"]
    assert status["op"] == "patch" and status["table"] == Tables.LOANS and status["record_id"] == "recC1"
    assert status["fields"] == {LF.STATUS: "Paid Off"}                  # only the status: no balance / payment rewritten
    assert ev["op"] == "post" and ev["table"] == Tables.FIN_EVENTS
    assert ev["fields"][EF.GOAL] == ["recGD"] and ev["fields"][EF.AMOUNT] == 118400 and ev["fields"][EF.KIND] == "one_time"
    assert ev["fields"][EF.OCCURRED_AT] == "2026-10-08" and "פועלים" in ev["fields"][EF.NOTE]


def test_close_amount_can_be_edited_to_what_was_actually_paid():
    seed_close()
    start_close()
    ex = Ex(fill={"סכום 118248.80": {"amount": 118248.8}})
    assert conv.handle_turn(ELIYAHU, "ערוך", extractor=ex, today=TODAY).state == "ask"
    assert "118,248.80" in conv.handle_turn(ELIYAHU, "סכום 118248.80", extractor=ex, today=TODAY).message
    r = conv.handle_turn(ELIYAHU, "אשר", extractor=ex, today=TODAY)
    assert r.snapshot["writes"][1]["fields"][EF.AMOUNT] == 118248.8


def test_close_edit_cannot_change_which_loan_is_closed():
    seed_close()
    start_close()
    conv.handle_turn(ELIYAHU, "ערוך", extractor=Ex(), today=TODAY)
    ex = Ex(fill={"x": {"loan": "recCX", "record_id": "recCX", "goal": "recGAV", "amount": 100000}})   # one valid edit rides along
    assert conv.handle_turn(ELIYAHU, "x", extractor=ex, today=TODAY).state == "review"
    r = conv.handle_turn(ELIYAHU, "אשר", extractor=Ex(), today=TODAY)
    status, ev = r.snapshot["writes"]
    assert status["record_id"] == "recC1" and ev["fields"][EF.GOAL] == ["recGD"]


def test_close_unknown_balance_asks_for_the_amount_paid_and_does_not_guess():
    seed_close()
    r = start_close("recC2")
    assert r.state == "ask" and r.awaiting == "amount" and "בלי יתרה" in r.message
    r = conv.handle_turn(ELIYAHU, "5000", extractor=Ex(), today=TODAY)
    assert r.state == "review"


def test_close_is_owner_scoped_foreign_and_unknown_loans_are_denied_identically():
    seed_close()
    foreign, unknown = start_close("recCX"), start_close("recNOPE")
    assert foreign.state == unknown.state == "denied" and foreign.message == unknown.message
    assert conv.start_loan_close(AVI_I, "recC1", today=TODAY).state == "denied"      # Avi cannot close Eli's loan
    assert not [d for d in conv.pending_view(ELIYAHU) or []]                          # no draft was opened for Eli


def test_close_already_paid_off_loan_is_info_not_a_second_closing():
    seed_close()
    r = start_close("recC3")
    assert r.state == "info" and "כבר" in r.message and conv.pending_view(ELIYAHU) is None


def test_close_blocks_a_second_open_draft():
    seed_close()
    start_close()
    assert start_close("recC1").state == "info" and start_close("recC2").state == "info"


def test_close_without_a_unique_debt_goal_updates_only_the_status_and_says_so():
    seed_close()
    DB[Tables.FIN_GOALS] = [goal("recGAV", "חוב של אבי", AVI, 5000, **{GF.CATEGORY: "debt"})]       # Eli has none
    r = start_close()
    assert "בלי אירוע התקדמות" in r.message
    (status,) = conv.handle_turn(ELIYAHU, "אשר", extractor=Ex(), today=TODAY).snapshot["writes"]
    assert status["fields"] == {LF.STATUS: "Paid Off"}
    seed_close()
    DB[Tables.FIN_GOALS].append(goal("recGD2", "חוב נוסף", ELI, 10000, **{GF.CATEGORY: "debt"}))       # two -> never guess
    conv.handle_turn(ELIYAHU, "בטל", extractor=Ex(), today=TODAY)
    r = start_close()
    assert "בלי אירוע התקדמות" in r.message


def test_close_retry_after_a_partial_failure_never_logs_the_closing_twice():
    seed_close()
    start_close()
    first = conv.handle_turn(ELIYAHU, "אשר", extractor=Ex(), today=TODAY)
    status, ev = first.snapshot["writes"]
    DB[Tables.LOANS][0]["fields"][LF.STATUS] = "Paid Off"                  # the status write landed, the event did not
    retry = conv.handle_turn(ELIYAHU, "אשר", extractor=Ex(), today=TODAY)
    assert retry.state == "confirmed" and [w["table"] for w in retry.snapshot["writes"]] == [Tables.FIN_EVENTS]
    DB[Tables.FIN_EVENTS].append({"id": "recEv", "fields": {**ev["fields"], EF.FINANCIAL_OWNER: [ELI]}})   # now the event landed too
    again = conv.handle_turn(ELIYAHU, "אשר", extractor=Ex(), today=TODAY)
    assert again.state == "duplicate"


def test_close_event_key_is_stable_per_loan_amount_and_day():
    seed_close()
    start_close()
    k1 = conv.handle_turn(ELIYAHU, "אשר", extractor=Ex(), today=TODAY).snapshot["writes"][1]["fields"][EF.IDEMPOTENCY_KEY]
    conv.complete_execution(ELIYAHU)
    start_close()
    k2 = conv.handle_turn(ELIYAHU, "אשר", extractor=Ex(), today=TODAY).snapshot["writes"][1]["fields"][EF.IDEMPOTENCY_KEY]
    assert k1 == k2


def test_close_cancel_leaves_everything_untouched():
    seed_close()
    start_close()
    assert conv.handle_turn(ELIYAHU, "בטל", extractor=Ex(), today=TODAY).state == "cancelled"
    assert conv.pending_view(ELIYAHU) is None and DB[Tables.LOANS][0]["fields"].get(LF.STATUS) is None


def test_close_http_open_then_confirm_executes_the_frozen_writes(monkeypatch):
    seed_close()
    sent = []
    monkeypatch.setattr(tma_api, "_queue_or_owner_execute",
                        lambda action, payload, identity, label: (sent.append((action, payload)) or ("a", {"ok": True}, 200)))
    c = http(monkeypatch, ELIYAHU)
    opened = c.post("/api/fcc/intent/start", json={"intent": "loan.close", "entity_id": "recC1"}, headers=H).get_json()
    assert opened["state"] == "review" and sent == []                              # opening writes nothing
    done = c.post("/api/fcc/write", json={"text": "אשר"}, headers=H).get_json()
    assert done["state"] == "executed" and [p["table"] for _, p in sent] == [Tables.LOANS, Tables.FIN_EVENTS]
    assert sent[0][1]["fields"] == {LF.STATUS: "Paid Off"}


def test_close_http_guards_flag_off_missing_id_foreign_loan(monkeypatch):
    seed_close()
    assert http(monkeypatch, ELIYAHU, flag=False).post("/api/fcc/intent/start", json={"intent": "loan.close", "entity_id": "recC1"}, headers=H).status_code == 404
    c = http(monkeypatch, ELIYAHU)
    assert c.post("/api/fcc/intent/start", json={}, headers=H).status_code == 400
    r = c.post("/api/fcc/intent/start", json={"intent": "loan.close", "entity_id": "recCX"}, headers=H)
    assert r.status_code == 403 and "77777" not in r.get_data(as_text=True)


def test_close_loans_table_is_in_the_write_allowlist_and_owner_recheck_blocks_foreign_record(monkeypatch):
    assert "Loans" in approval_actions._TMA_WRITE_ALLOWED_TABLES
    seed_close()
    _, denied = approval_actions._enforce_personal_data_policy("patch", "Loans", "recCX", {LF.STATUS: "Paid Off"}, ELIYAHU)
    assert denied is not None
    _, ok = approval_actions._enforce_personal_data_policy("patch", "Loans", "recC1", {LF.STATUS: "Paid Off"}, ELIYAHU)
    assert ok is None


def test_close_leaves_the_payoff_engine_and_summary_consistent_after_the_write():
    seed_close()
    before = service.overview(ELIYAHU, TODAY)["loans"]
    assert "recC1" in [i["id"] for i in before["payoff"]["items"]]
    DB[Tables.LOANS][0]["fields"][LF.STATUS] = "Paid Off"                       # as stored after the status write
    after = service.overview(ELIYAHU, TODAY)["loans"]
    assert "recC1" not in [i["id"] for i in after["payoff"]["items"]]
    assert after["summary"]["total_active_loans"] == before["summary"]["total_active_loans"] - 1


# ── Contextual writer P1: intents (chips / card actions) — one engine, one draft slot, no classifier ───────────────
def seed_intents():
    DB[Tables.FIN_GOALS] = [
        goal("recGI", "משכורת", ELI, 20000, **{GF.CATEGORY: "income"}),
        goal("recGI2", "פרילנס", ELI, 5000, **{GF.CATEGORY: "income"}),
        goal("recGH", "הוצאות בית", ELI, 9000, **{GF.CATEGORY: "other"}),
        goal("recGK", "קרן חירום", ELI, 60000, **{GF.CATEGORY: "emergency_fund", GF.CALC_METHOD: "cumulative"}),
        goal("recGAV", "של אבי", AVI, 5000, **{GF.CATEGORY: "income"}),
    ]
    DB[Tables.FIN_EVENTS] = []
    DB[Tables.LOANS] = [loan("recC1", **{LF.NAME: "פועלים", LF.EARLY_CLOSURE: 118400})]


def intent(iid, entity_id=None, who=ELIYAHU):
    return conv.start_intent(who, iid, entity_id, today=TODAY)


def test_intent_registry_covers_the_p1_monthly_chips_and_loan_close():
    for iid in ("monthly.income", "monthly.household_expense", "monthly.direct_cost", "monthly.goal_update",
                "monthly.obligation", "loan.close"):
        assert iid in fd.INTENTS
    assert fd.INTENTS["loan.close"]["transition"] is True
    assert fd.INTENTS["monthly.household_expense"]["kind"] == "household_expense"     # NOT direct_cost
    assert fd.INTENTS["monthly.direct_cost"]["kind"] == "direct_cost"


def test_intent_unknown_is_rejected_and_writes_nothing():
    seed_intents()
    assert intent("monthly.nope").state == "clarify"
    assert intent("").state == "clarify"


def test_intent_income_prefills_kind_and_offers_only_own_income_goals():
    seed_intents()
    r = intent("monthly.income")
    assert r.state == "needs_goal" and r.entity == "fcc_event"
    assert {c["goal_id"] for c in r.candidates} == {"recGI", "recGI2"}            # income goals of the caller only
    assert r.fields.get("סוג") == "חד-פעמי"                                       # kind pre-filled by the intent
    assert r.snapshot is None


def test_intent_income_full_flow_reviews_then_freezes_one_event():
    seed_intents()
    r = intent("monthly.income", "recGI")
    assert r.awaiting == "kind"                                                   # the income type is asked, never silently defaulted
    conv.handle_turn(ELIYAHU, "חד-פעמית", goal_id="one_time", extractor=Ex(), today=TODAY)
    r = conv.handle_turn(ELIYAHU, "5000", extractor=Ex(fill={"5000": {"amount": 5000}}), today=TODAY)
    assert r.state == "review" and "משכורת" in r.message and "₪5,000" in r.message
    c = conv.handle_turn(ELIYAHU, "אשר", extractor=Ex(), today=TODAY)
    assert c.state == "confirmed"
    (w,) = c.snapshot["writes"]
    assert w["table"] == Tables.FIN_EVENTS and w["fields"][EF.GOAL] == ["recGI"] and w["fields"][EF.KIND] == "one_time"


def test_intent_household_expense_is_household_never_direct_cost():
    seed_intents()
    r = intent("monthly.household_expense")                  # a unique "הוצאות בית" goal is selected without asking
    assert r.state == "ask" and r.awaiting == "amount"
    r = conv.handle_turn(ELIYAHU, "300", extractor=Ex(fill={"300": {"amount": 300}}), today=TODAY)
    assert r.state == "review" and "הוצאה ביתית" in r.message
    c = conv.handle_turn(ELIYAHU, "אשר", extractor=Ex(), today=TODAY)
    (w,) = c.snapshot["writes"]
    assert w["fields"][EF.KIND] == "household_expense" and w["fields"][EF.GOAL] == ["recGH"]


def test_intent_direct_cost_prefills_direct_cost_on_an_income_goal():
    seed_intents()
    intent("monthly.direct_cost", "recGI2")
    r = conv.handle_turn(ELIYAHU, "80", extractor=Ex(fill={"80": {"amount": 80}}), today=TODAY)
    assert r.state == "review" and "הוצאה ישירה" in r.message
    (w,) = conv.handle_turn(ELIYAHU, "אשר", extractor=Ex(), today=TODAY).snapshot["writes"]
    assert w["fields"][EF.KIND] == "direct_cost" and w["fields"][EF.GOAL] == ["recGI2"]


def test_intent_goal_update_needs_the_goal_and_then_asks_what_to_change():
    seed_intents()
    assert intent("monthly.goal_update").state == "clarify"                      # no record chosen -> nothing opened
    r = intent("monthly.goal_update", "recGK")
    assert r.state == "ask" and r.entity == "fcc_goal"
    ex = Ex(fill={"סכום 80000": {"target_amount": 80000}})
    assert conv.handle_turn(ELIYAHU, "סכום 80000", extractor=ex, today=TODAY).state == "review"


def test_intent_obligation_opens_an_empty_obligation_draft():
    seed_intents()
    r = intent("monthly.obligation")
    assert r.state == "ask" and r.entity == "fcc_obligation" and r.awaiting == "name"


def test_intent_cannot_target_somebody_elses_goal_or_loan():
    seed_intents()
    assert intent("monthly.income", "recGAV").state == "denied"                  # Avi's goal == not found
    assert intent("monthly.goal_update", "recGAV").state == "denied"
    seed_close()
    assert intent("loan.close", "recCX").state == "denied"


def test_intent_blocks_a_second_open_draft_across_intents():
    seed_intents()
    intent("monthly.income", "recGI")
    r = intent("monthly.household_expense")
    assert r.state == "info" and "יש עדכון פתוח" in r.message


def test_intent_loan_close_is_the_same_flow_as_the_card_button():
    seed_close()
    r = intent("loan.close", "recC1")
    assert r.state == "review" and r.entity == "fcc_loan_close" and r.snapshot is None
    conv.handle_turn(ELIYAHU, "בטל", extractor=Ex(), today=TODAY)
    assert intent("loan.close").state in ("denied", "clarify")                    # needs a loan id


def test_two_legitimate_entries_of_the_same_amount_are_not_deduplicated():
    seed_intents()
    ex = Ex(fill={"300": {"amount": 300}})
    keys = []
    for _ in range(2):
        intent("monthly.household_expense")
        conv.handle_turn(ELIYAHU, "300", extractor=ex, today=TODAY)
        (w,) = conv.handle_turn(ELIYAHU, "אשר", extractor=Ex(), today=TODAY).snapshot["writes"]
        keys.append(w["fields"][EF.IDEMPOTENCY_KEY])
        conv.complete_execution(ELIYAHU, "fcc_event")
    assert keys[0] != keys[1]


def test_free_text_cannot_open_a_new_draft_from_the_loans_or_assets_tabs():
    seed_intents()
    ex = Ex(classify={"שילמתי 500": {"action": "log_progress", "goal_hint": "משכורת", "amount": 500}})
    for tab in ("loans", "assets"):
        r = conv.handle_turn(ELIYAHU, "שילמתי 500", extractor=ex, today=TODAY, scope=tab)
        assert r.state == "info" and "בכפתורים" in r.message
    assert ex.calls == []                                                            # classifier never consulted
    assert conv.handle_turn(ELIYAHU, "שילמתי 500", extractor=ex, today=TODAY, scope="monthly").state == "info"    # the TMA starts from chips only


def test_scope_does_not_block_answering_an_open_draft():
    seed_intents()
    intent("monthly.income", "recGI")
    conv.handle_turn(ELIYAHU, "חד-פעמית", goal_id="one_time", extractor=Ex(), today=TODAY, scope="loans")
    r = conv.handle_turn(ELIYAHU, "700", extractor=Ex(fill={"700": {"amount": 700}}), today=TODAY, scope="loans")
    assert r.state == "review"


def test_intent_start_endpoint_flag_auth_and_validation(monkeypatch):
    seed_intents()
    assert http(monkeypatch, ELIYAHU, flag=False).post("/api/fcc/intent/start", json={"intent": "monthly.obligation"}, headers=H).status_code == 404
    c = http(monkeypatch, ELIYAHU)
    assert c.post("/api/fcc/intent/start", json={}, headers=H).status_code == 400
    r = c.post("/api/fcc/intent/start", json={"intent": "monthly.obligation"}, headers=H)
    assert r.status_code == 200 and r.get_json()["entity"] == "fcc_obligation"
    assert c.post("/api/fcc/intent/start", json={"intent": "monthly.income", "entity_id": "recGAV"}, headers=H).status_code in (403, 200)


# ── Contextual writer P2: loan balance / monthly payment / new loan ────────────────────────────────────────────────
def seed_p2():
    seed_close()
    DB[Tables.LOANS] = [
        loan("recC1", **{LF.NAME: "פועלים", LF.EARLY_CLOSURE: 118400, LF.MONTHLY_PAYMENT: 2816.16, LF.OUTSTANDING: 120000}),
        loan("recC3", **{LF.NAME: "סגורה", LF.STATUS: "Paid Off", LF.EARLY_CLOSURE: 1000}),
        loan("recCX", owner=AVI, **{LF.NAME: "של אבי", LF.EARLY_CLOSURE: 77777}),
    ]


def say(text, **fill):
    return conv.handle_turn(ELIYAHU, text, extractor=Ex(fill={text: fill} if fill else {}), today=TODAY)


def test_p2_intents_are_registered_and_none_is_a_transition():
    for iid, ent in (("loan.update_balance", "fcc_loan_balance"), ("loan.update_payment", "fcc_loan_payment"), ("loan.create", "fcc_loan_new")):
        assert fd.INTENTS[iid]["entity"] == ent and not fd.INTENTS[iid].get("transition")
    assert fd.INTENTS["loan.update_balance"]["target_required"] and fd.INTENTS["loan.update_payment"]["target_required"]
    assert not fd.INTENTS["loan.create"].get("target")


def test_update_balance_shows_today_asks_then_writes_exactly_one_field():
    seed_p2()
    r = intent("loan.update_balance", "recC1")
    assert r.state == "ask" and r.entity == "fcc_loan_balance" and "פועלים" in r.message and "₪118,400" in r.message
    r = say("112000", balance=112000)
    assert r.state == "review" and "עדכון יתרת הלוואה" in r.message and "היום: ₪118,400" in r.message and "₪112,000" in r.message
    assert r.snapshot is None
    (w,) = conv.handle_turn(ELIYAHU, "אשר", extractor=Ex(), today=TODAY).snapshot["writes"]
    assert w["op"] == "patch" and w["table"] == Tables.LOANS and w["record_id"] == "recC1"
    assert w["fields"] == {LF.EARLY_CLOSURE: 112000}                       # ONE field; Outstanding Balance / status untouched


def test_update_payment_writes_only_the_monthly_payment():
    seed_p2()
    intent("loan.update_payment", "recC1")
    say("2500", payment=2500)
    (w,) = conv.handle_turn(ELIYAHU, "אשר", extractor=Ex(), today=TODAY).snapshot["writes"]
    assert w["fields"] == {LF.MONTHLY_PAYMENT: 2500} and w["record_id"] == "recC1"


def test_loan_updates_validate_amounts_and_cannot_retarget_the_loan():
    seed_p2()
    intent("loan.update_payment", "recC1")
    r = say("0", payment=0)
    assert r.state == "ask"                                                 # a zero payment is not accepted
    r = say("2500", payment=2500, record_id="recCX", loan="recCX")           # a smuggled other loan id is ignored
    c = conv.handle_turn(ELIYAHU, "אשר", extractor=Ex(), today=TODAY)
    assert c.snapshot["writes"][0]["record_id"] == "recC1"


def test_loan_updates_are_owner_scoped_and_only_for_active_loans():
    seed_p2()
    assert intent("loan.update_balance", "recCX").state == "denied"          # Avi's loan == not found
    assert intent("loan.update_payment", "recCX").state == "denied"
    r = intent("loan.update_balance", "recC3")
    assert r.state == "info" and "נסגרה" in r.message                        # a closed loan has nothing to update
    assert intent("loan.update_balance").state == "clarify"                  # no loan chosen


def test_loan_update_to_the_value_it_already_has_is_not_written_twice():
    seed_p2()
    intent("loan.update_balance", "recC1")
    say("118400", balance=118400)
    r = conv.handle_turn(ELIYAHU, "אשר", extractor=Ex(), today=TODAY)
    assert r.state == "duplicate"


def test_new_loan_asks_only_what_is_missing_then_reviews_then_one_owner_scoped_post():
    seed_p2()
    r = intent("loan.create")
    assert r.state == "ask" and r.entity == "fcc_loan_new" and r.awaiting == "name"
    assert say("כאל", name="כאל").awaiting == "loan_type"
    assert say("פרטית").awaiting == "balance"                                # closed vocabulary answer, no LLM needed
    assert say("48300", balance=48300).awaiting == "payment"
    assert say("1900", payment=1900).awaiting == "rate"
    r = say("7.5", rate=7.5)
    assert r.state == "review" and "הלוואה חדשה" in r.message and "₪48,300" in r.message and "7.5%" in r.message and "פרטית" in r.message
    assert r.snapshot is None
    c = conv.handle_turn(ELIYAHU, "אשר", extractor=Ex(), today=TODAY)
    (w,) = c.snapshot["writes"]
    assert w["op"] == "post" and w["table"] == Tables.LOANS
    assert w["fields"] == {LF.NAME: "כאל", LF.LOAN_TYPE: "פרטית", LF.EARLY_CLOSURE: 48300, LF.MONTHLY_PAYMENT: 1900,
                           LF.INTEREST_RATE: 7.5, LF.ACTIVE: True}          # Owner is added at execution by the owner-scope policy


def test_new_loan_rejects_bad_numbers_and_an_unknown_type_and_blocks_a_same_named_active_loan():
    seed_p2()
    intent("loan.create")
    say("כאל", name="כאל")
    assert say("מעורבת").awaiting == "loan_type"                             # not one of the three live choices
    say("עסקית"); say("1000", balance=1000)
    assert say("0", payment=0).awaiting == "payment"
    say("500", payment=500)
    assert say("150", rate=150).awaiting == "rate"                           # percent must be 0..100
    say("6", rate=6)
    DB[Tables.LOANS].append(loan("recDup", **{LF.NAME: "כאל", LF.EARLY_CLOSURE: 1}))
    assert conv.handle_turn(ELIYAHU, "אשר", extractor=Ex(), today=TODAY).state == "duplicate"


def test_new_loan_optional_fields_can_be_added_in_edit():
    seed_p2()
    intent("loan.create")
    for t, k in (("כאל", {"name": "כאל"}), ("פרטית", {}), ("48300", {"balance": 48300}), ("1900", {"payment": 1900}), ("7.5", {"rate": 7.5})):
        say(t, **k)
    conv.handle_turn(ELIYAHU, "ערוך", extractor=Ex(), today=TODAY)
    say("מלווה כאל, תשלומים 30", lender="כאל", payments_left=30)
    (w,) = conv.handle_turn(ELIYAHU, "אשר", extractor=Ex(), today=TODAY).snapshot["writes"]
    assert w["fields"][LF.LENDER] == "כאל" and w["fields"][LF.PAYMENTS_LEFT] == 30


def test_loan_intents_share_the_single_draft_slot_with_everything_else():
    seed_p2()
    intent("loan.create")
    assert intent("loan.update_balance", "recC1").state == "info"
    assert intent("monthly.obligation").state == "info"


def test_p2_http_new_loan_and_update_confirm_executes_frozen_writes_and_scopes_the_new_loan(monkeypatch):
    seed_p2()
    sent = []
    monkeypatch.setattr(tma_api, "_queue_or_owner_execute",
                        lambda action, payload, identity, label: (sent.append(payload) or ("a", {"ok": True}, 200)))
    monkeypatch.setattr(conv.DeterministicExtractor, "fill", lambda self, text, awaiting, fields, entity, today:
                        {"balance": 1000} if awaiting == "balance" else {"payment": 100} if awaiting == "payment" else
                        {"rate": 5} if awaiting == "rate" else {"name": text} if awaiting == "name" else {})
    c = http(monkeypatch, ELIYAHU)
    assert c.post("/api/fcc/intent/start", json={"intent": "loan.create"}, headers=H).get_json()["awaiting"] == "name"
    for text in ("הלוואה חדשה", "משכנתא", "1000", "100", "5"):
        turn = c.post("/api/fcc/write", json={"text": text, "scope": "loans"}, headers=H).get_json()
    assert turn["state"] == "review" and sent == []
    assert c.post("/api/fcc/write", json={"text": "אשר", "scope": "loans"}, headers=H).get_json()["state"] == "executed"
    assert sent[0]["op"] == "post" and sent[0]["table"] == Tables.LOANS and sent[0]["fields"][LF.LOAN_TYPE] == "משכנתא"
    # the executor adds the Owner for the caller and re-checks the record owner of a patch
    scoped = policy.scope_new_record_fields(Tables.LOANS, dict(sent[0]["fields"]), ELIYAHU)
    assert scoped.get("Owner")
    _, denied = approval_actions._enforce_personal_data_policy("patch", "Loans", "recCX", {LF.EARLY_CLOSURE: 1}, ELIYAHU)
    assert denied is not None


def test_early_closure_principal_is_the_only_balance_outstanding_balance_is_legacy_and_never_a_fallback():
    DB[Tables.LOANS] = [
        loan("recOnlyLegacy", **{LF.NAME: "ישן", LF.OUTSTANDING: 90000, LF.INTEREST_RATE: 10.0, LF.MONTHLY_PAYMENT: 1000}),
        loan("recNew", **{LF.NAME: "חדש", LF.EARLY_CLOSURE: 50000, LF.OUTSTANDING: 999999, LF.INTEREST_RATE: 6.0, LF.MONTHLY_PAYMENT: 800}),
    ]
    view = service.loans_overview(ELIYAHU, TODAY)
    by = {i["id"]: i for i in view["items"]}
    assert by["recOnlyLegacy"]["early_closure_balance"] is None                  # missing stays "not defined"
    assert by["recNew"]["early_closure_balance"] == 50000
    assert all("current_balance" not in i for i in view["items"])               # the legacy number is not even exposed
    assert view["summary"]["total_early_closure_balance"] == 50000               # the legacy 90,000 / 999,999 never counted
    assert view["summary"]["weighted_average_interest_rate"] == 6.0              # weighted only by the SSOT balance


# ── Contextual writer P3: asset value / mortgage / next step ───────────────────────────────────────────────────────
def seed_p3():
    DB["Assets"] = [
        asset("recAH", "בית שמש", **{AF.STATUS: {"name": "פעיל"}, AF.VALUE: 5000000, AF.MORTGAGE: 1200000,
                                     AF.NEXT_STEP: "לבדוק מחיר", AF.NEXT_STEP_OWNER: {"name": "אהרן"}}),
        asset("recAS", "דירה שנמכרה", **{AF.STATUS: {"name": "נמכר"}, AF.VALUE: 1000000}),
        asset("recAE", "נכס ריק"),
        asset("recAX", "נכס של אבי", owner=AVI, **{AF.VALUE: 99999999}),
    ]
    DB[Tables.LOANS] = [loan("recL1", **{LF.EARLY_CLOSURE: 100000, LF.RELATED_ASSET: ["recAH"]})]


def test_p3_intents_registered_and_none_of_them_is_a_transition():
    for iid, ent in (("asset.update_value", "fcc_asset_value"), ("asset.update_mortgage", "fcc_asset_mortgage"), ("asset.next_step", "fcc_asset_step")):
        assert fd.INTENTS[iid]["entity"] == ent and fd.INTENTS[iid]["target_required"] and not fd.INTENTS[iid].get("transition")


def test_asset_value_shows_today_asks_then_writes_exactly_one_field():
    seed_p3()
    r = intent("asset.update_value", "recAH")
    assert r.state == "ask" and r.entity == "fcc_asset_value" and "בית שמש" in r.message and "₪5,000,000" in r.message
    r = say("5400000", value=5400000)
    assert r.state == "review" and "עדכון שווי נכס" in r.message and "היום: ₪5,000,000" in r.message and "₪5,400,000" in r.message
    assert r.snapshot is None
    (w,) = conv.handle_turn(ELIYAHU, "אשר", extractor=Ex(), today=TODAY).snapshot["writes"]
    assert w["op"] == "patch" and w["table"] == "Assets" and w["record_id"] == "recAH"
    assert w["fields"] == {AF.VALUE: 5400000}                               # Equity / Mortgage / Status untouched


def test_asset_mortgage_writes_only_its_field_and_says_it_is_not_synced_with_loans():
    seed_p3()
    intent("asset.update_mortgage", "recAH")
    r = say("1100000", mortgage=1100000)
    assert "לא מסתנכרנת להלוואות" in r.message
    (w,) = conv.handle_turn(ELIYAHU, "אשר", extractor=Ex(), today=TODAY).snapshot["writes"]
    assert w["fields"] == {AF.MORTGAGE: 1100000}
    conv.complete_execution(ELIYAHU)
    DB["Assets"][0]["fields"][AF.MORTGAGE] = 1100000
    intent("asset.update_mortgage", "recAH")
    say("0", mortgage=0)                                                    # zero is a valid "no mortgage"
    assert conv.handle_turn(ELIYAHU, "אשר", extractor=Ex(), today=TODAY).snapshot["writes"][0]["fields"] == {AF.MORTGAGE: 0}


def test_asset_intents_are_owner_scoped_skip_sold_assets_and_need_a_target():
    seed_p3()
    for iid in ("asset.update_value", "asset.update_mortgage", "asset.next_step"):
        assert intent(iid, "recAX").state == "denied"                       # Avi's asset == not found
        assert intent(iid).state == "clarify"
        r = intent(iid, "recAS")
        assert r.state == "info" and "נמכר" in r.message
    assert intent("asset.update_value", "recLOAN").state == "denied"


def test_asset_update_to_the_value_it_already_has_or_same_text_is_not_written_twice():
    seed_p3()
    intent("asset.update_value", "recAH"); say("5000000", value=5000000)
    assert conv.handle_turn(ELIYAHU, "אשר", extractor=Ex(), today=TODAY).state == "duplicate"
    DB[Tables.TASKS] = [step_task("tOpen", "recAH", "לבדוק מחיר")]
    intent("asset.next_step", "recAH"); say("לבדוק מחיר", step=" לבדוק מחיר ")
    r = conv.handle_turn(ELIYAHU, "אשר", extractor=Ex(), today=TODAY)
    assert r.state == "duplicate"                                           # the same OPEN action already exists on this asset


def test_asset_cannot_be_retargeted_by_an_edit_and_shares_the_single_draft_slot():
    seed_p3()
    intent("asset.update_value", "recAH")
    say("6000000", value=6000000, record_id="recAX", asset="recAX")
    assert conv.handle_turn(ELIYAHU, "אשר", extractor=Ex(), today=TODAY).snapshot["writes"][0]["record_id"] == "recAH"
    seed_p3(); conv.complete_execution(ELIYAHU)
    intent("asset.update_value", "recAH")
    assert intent("asset.next_step", "recAH").state == "info"


def test_asset_read_model_keeps_the_legacy_next_step_as_stored_and_lists_open_actions():
    seed_p3()
    DB[Tables.TASKS] = [step_task("t1", "recAH", "לשלוח הצעה", owner="אורי", due="2026-10-20")]
    items = {i["id"]: i for i in service.overview(ELIYAHU, TODAY)["assets"]["items"]}
    assert items["recAH"]["next_step"] == "לבדוק מחיר" and items["recAH"]["next_step_owner"] == "אהרן"      # legacy text, untouched
    (a,) = items["recAH"]["actions"]
    assert a["id"] == "t1" and a["title"] == "לשלוח הצעה" and a["status"] == "ממתין" and a["owner"] == "אורי" and a["due_date"] == "2026-10-20"
    assert items["recAE"]["next_step"] is None and items["recAE"]["next_step_owner"] is None


# ── Contextual writer P4: mark an asset sold (Sale Date + Sale Amount) ─────────────────────────────────────────────
def seed_p4():
    DB["Assets"] = [
        asset("recAH", "בית שמש", **{AF.STATUS: {"name": "פעיל"}, AF.VALUE: 2300000, AF.MORTGAGE: 900000, AF.OWNERSHIP_PCT: 50,
                                     AF.EQUITY: 1400000, AF.MY_EQUITY: 700000}),
        asset("recAN", "נכס בלי אחוז בעלות", **{AF.STATUS: {"name": "פעיל"}, AF.VALUE: 1000000}),
        asset("recAS", "דירה שנמכרה", **{AF.STATUS: {"name": "נמכר"}, AF.VALUE: 1000000, AF.MORTGAGE: 300000, AF.OWNERSHIP_PCT: 100,
                                         AF.SALE_DATE: "2026-09-01", AF.SALE_AMOUNT: 1100000, AF.EQUITY: 700000, AF.MY_EQUITY: 700000}),
        asset("recAX", "נכס של אבי", owner=AVI, **{AF.VALUE: 99999999}),
    ]
    DB[Tables.LOANS] = [loan("recL1", **{LF.NAME: "כאל", LF.EARLY_CLOSURE: 48300, LF.RELATED_ASSET: ["recAH"]}),
                        loan("recL2", **{LF.NAME: "לא קשורה", LF.EARLY_CLOSURE: 1000})]


def test_p4_mark_sold_is_a_registered_transition_with_both_values_required():
    spec = fd.INTENTS["asset.mark_sold"]
    assert spec["entity"] == "fcc_asset_sold" and spec["transition"] is True and spec["target_required"]
    req = {f.field_name for f in fd.FCC_CONTRACTS["fcc_asset_sold"].fields if f.required.value == "true"}
    assert req == {"sale_date", "sale_amount"}


def test_p4_sale_review_is_loud_and_writes_nothing_before_approval():
    seed_p4()
    r = intent("asset.mark_sold", "recAH")
    assert r.state == "ask" and r.awaiting == "sale_amount" and "100%" in r.message       # the date defaults to today, the price is asked
    r = say("2500000", sale_amount=2500000)
    assert r.state == "review" and r.snapshot is None
    for part in ("סימון נכס כנמכר", "בית שמש", "08/10/2026", "(הוסק)", "₪2,500,000", "החלק שלך (50%): ₪1,250,000",
                 "כאל", "₪48,300", "לא נסגרות אוטומטית", "₪900,000", "לא מתאפסת", "יצא מסיכומי הנכסים הפעילים", "לא נרשמת כנכס/מזומן"):
        assert part in r.message, part
    assert "₪1,000" not in r.message.replace("₪1,000,000", "")                          # an unrelated loan is not listed


def test_p4_confirm_freezes_exactly_one_atomic_patch_and_nothing_else():
    seed_p4()
    intent("asset.mark_sold", "recAH"); say("2500000", sale_amount=2500000)
    c = conv.handle_turn(ELIYAHU, "אשר", extractor=Ex(), today=TODAY)
    assert c.state == "confirmed"
    (w,) = c.snapshot["writes"]                                                         # ONE write: no loan close, no mortgage reset, no proceeds record
    assert w["op"] == "patch" and w["table"] == "Assets" and w["record_id"] == "recAH"
    assert w["fields"] == {AF.STATUS: "נמכר", AF.SALE_DATE: "2026-10-08", AF.SALE_AMOUNT: 2500000}


def test_p4_sale_date_is_editable_before_approval_and_the_amount_is_mandatory():
    seed_p4()
    intent("asset.mark_sold", "recAH")
    assert say("0", sale_amount=0).awaiting == "sale_amount"                            # a sale without a (positive) price is not recorded
    say("2500000", sale_amount=2500000)
    conv.handle_turn(ELIYAHU, "ערוך", extractor=Ex(), today=TODAY)
    r = say("התאריך 2026-09-20", sale_date="2026-09-20")
    assert r.state == "review" and "20/09/2026" in r.message and "(הוסק)" not in r.message.split("תאריך מכירה")[1].split("\n")[0]
    (w,) = conv.handle_turn(ELIYAHU, "אשר", extractor=Ex(), today=TODAY).snapshot["writes"]
    assert w["fields"][AF.SALE_DATE] == "2026-09-20"


def test_p4_unknown_ownership_leaves_my_share_unknown_never_100_percent():
    seed_p4()
    intent("asset.mark_sold", "recAN")
    r = say("1200000", sale_amount=1200000)
    assert "לא ניתן לחשב" in r.message and "₪1,200,000" in r.message


def test_p4_owner_scope_sold_assets_and_missing_target():
    seed_p4()
    assert intent("asset.mark_sold", "recAX").state == "denied"
    assert intent("asset.mark_sold").state == "clarify"
    r = intent("asset.mark_sold", "recAS")
    assert r.state == "info" and "נמכר" in r.message                                    # already sold: nothing to do


def test_p4_second_confirmation_of_the_same_sale_is_a_duplicate_not_a_second_write():
    seed_p4()
    intent("asset.mark_sold", "recAH"); say("2500000", sale_amount=2500000)
    DB["Assets"][0]["fields"][AF.STATUS] = {"name": "נמכר"}                              # applied elsewhere in the meantime
    assert conv.handle_turn(ELIYAHU, "אשר", extractor=Ex(), today=TODAY).state == "duplicate"


def test_p4_sold_assets_leave_the_active_totals_and_are_listed_apart_with_my_share():
    seed_p4()
    view = service.overview(ELIYAHU, TODAY)["assets"]
    assert {i["id"] for i in view["items"]} == {"recAH", "recAN"}                       # the sold one is not an active asset
    assert view["summary"]["count"] == 2 and view["summary"]["total_value"] == 3300000 and view["summary"]["total_mortgage"] == 900000
    assert view["summary"]["total_my_equity"] == 700000                                 # only active assets: recAS' 700,000 is excluded
    (s,) = view["sold"]["items"]
    assert view["sold"]["count"] == 1 and s["id"] == "recAS" and s["sale_date"] == "2026-09-01"
    assert s["sale_amount"] == 1100000 and s["ownership_pct"] == 100 and s["my_share"] == 1100000


def test_p4_sold_share_follows_ownership_and_stays_unknown_without_it():
    seed_p4()
    DB["Assets"][2]["fields"][AF.OWNERSHIP_PCT] = 50
    (s,) = service.overview(ELIYAHU, TODAY)["assets"]["sold"]["items"]
    assert s["my_share"] == 550000
    del DB["Assets"][2]["fields"][AF.OWNERSHIP_PCT]
    (s,) = service.overview(ELIYAHU, TODAY)["assets"]["sold"]["items"]
    assert s["my_share"] is None and s["sale_amount"] == 1100000


def test_p4_loans_linked_to_a_sold_asset_stay_open_and_visible():
    seed_p4()
    DB["Assets"][0]["fields"][AF.STATUS] = {"name": "נמכר"}
    view = service.overview(ELIYAHU, TODAY)
    sold = {s["id"]: s for s in view["assets"]["sold"]["items"]}
    assert [l["name"] for l in sold["recAH"]["linked_loans"]] == ["כאל"]               # still listed against the sold asset
    assert any(i["name"] == "כאל" and i["active"] for i in view["loans"]["items"])      # and still an active loan


def test_p4_http_sale_executes_the_frozen_patch_and_the_executor_rechecks_the_owner(monkeypatch):
    seed_p4()
    sent = []
    monkeypatch.setattr(tma_api, "_queue_or_owner_execute",
                        lambda action, payload, identity, label: (sent.append(payload) or ("a", {"ok": True}, 200)))
    monkeypatch.setattr(conv.DeterministicExtractor, "fill", lambda self, text, awaiting, fields, entity, today: {"sale_amount": 2500000} if awaiting == "sale_amount" else {})
    c = http(monkeypatch, ELIYAHU)
    assert c.post("/api/fcc/intent/start", json={"intent": "asset.mark_sold", "entity_id": "recAH"}, headers=H).get_json()["awaiting"] == "sale_amount"
    assert c.post("/api/fcc/write", json={"text": "2500000", "scope": "assets"}, headers=H).get_json()["state"] == "review"
    assert sent == []
    assert c.post("/api/fcc/write", json={"text": "אשר", "scope": "assets"}, headers=H).get_json()["state"] == "executed"
    assert len(sent) == 1 and sent[0]["fields"][AF.STATUS] == "נמכר" and sent[0]["record_id"] == "recAH"
    _, denied = approval_actions._enforce_personal_data_policy("patch", "Assets", "recAX", {AF.STATUS: "נמכר"}, ELIYAHU)
    assert denied is not None


# ── Income is booked on a SOURCE (not a goal): wording + "מקור אחר" ────────────────────────────────────────────
def seed_sources():
    DB[Tables.FIN_GOALS] = [
        goal("recP", "הכנסה חודשית קבועה", ELI, 15000, **{GF.CATEGORY: "income"}),
        goal("recT", "הכנסה מנסיעות", ELI, 2500, **{GF.CATEGORY: "income", GF.PARENT_GOAL: ["recP"]}),
        goal("recGH", "הוצאות בית", ELI, 9000, **{GF.CATEGORY: "other"}),
    ]
    DB[Tables.FIN_EVENTS] = []


def test_income_chip_speaks_of_a_source_and_offers_other_source():
    seed_sources()
    r = intent("monthly.income")
    assert r.state == "needs_goal" and "מקור" in r.message and "יעד" not in r.message
    assert [c["goal_id"] for c in r.candidates] == ["recP", "recT", conv.OTHER_SOURCE_ID]
    assert r.candidates[-1]["title"] == "מקור אחר"


def test_other_source_books_on_the_total_goal_with_the_named_source_in_the_note():
    seed_sources()
    intent("monthly.income")
    r = conv.handle_turn(ELIYAHU, "מקור אחר", goal_id=conv.OTHER_SOURCE_ID, extractor=Ex(), today=TODAY)
    assert r.state == "ask" and r.awaiting == "source"
    r = conv.handle_turn(ELIYAHU, "אבי", extractor=Ex(), today=TODAY)
    assert r.awaiting == "kind" and [c["goal_id"] for c in r.candidates] == ["one_time", "monthly_recurring"]
    r = conv.handle_turn(ELIYAHU, "חד-פעמית", goal_id="one_time", extractor=Ex(), today=TODAY)
    assert r.state == "ask" and r.awaiting == "amount" and r.message == "כמה לרשום ממקור אבי?"
    r = conv.handle_turn(ELIYAHU, "1200", extractor=Ex(fill={"1200": {"amount": 1200}}), today=TODAY)
    assert r.state == "review" and "• מקור: הכנסה חודשית קבועה" in r.message and "מקור: אבי" in r.message
    c = conv.handle_turn(ELIYAHU, "אשר", extractor=Ex(), today=TODAY)
    (w,) = c.snapshot["writes"]
    assert w["fields"][EF.GOAL] == ["recP"] and w["fields"][EF.NOTE] == "מקור: אבי" and w["fields"][EF.KIND] == "one_time"


def test_other_source_requires_a_name_and_confirm_words_are_not_a_name():
    seed_sources()
    intent("monthly.income")
    conv.handle_turn(ELIYAHU, "x", goal_id=conv.OTHER_SOURCE_ID, extractor=Ex(), today=TODAY)
    for bad in ("אשר", "דלג"):                               # empty text never reaches the draft (answered "מה לעדכן?")
        r = conv.handle_turn(ELIYAHU, bad, extractor=Ex(), today=TODAY)
        assert r.awaiting == "source" and "שם" in r.message


def test_other_source_not_offered_without_a_single_total_income_goal():
    seed_intents()                                           # two top-level income goals: ambiguous, so no synthetic choice
    r = intent("monthly.income")
    assert conv.OTHER_SOURCE_ID not in {c["goal_id"] for c in r.candidates}
    r = conv.handle_turn(ELIYAHU, "x", goal_id=conv.OTHER_SOURCE_ID, extractor=Ex(), today=TODAY)
    assert r.state == "denied" or r.state == "needs_goal"    # never silently picks some goal


def test_household_expense_wording_is_an_item_not_a_goal():
    seed_sources()
    r = intent("monthly.household_expense")
    assert r.state == "ask" and "סעיף" in r.message and "יעד" not in r.message


def test_income_kind_is_asked_and_recurring_on_a_period_goal_is_flagged_in_review():
    seed_sources()
    intent("monthly.income", "recT")                                              # a period_sum source (default calc method)
    r = conv.handle_turn(ELIYAHU, "x", extractor=Ex(), today=TODAY)               # not a kind: asked again, nothing stored
    assert r.awaiting == "kind" and "בחרו" in r.message
    r = conv.handle_turn(ELIYAHU, "חודשית קבועה", extractor=Ex(), today=TODAY)   # typed label works like the button
    assert r.awaiting == "amount"
    r = conv.handle_turn(ELIYAHU, "800", extractor=Ex(fill={"800": {"amount": 800}}), today=TODAY)
    assert r.state == "review" and "חודשי קבוע" in r.message and "לא תיכלל" in r.message
    c = conv.handle_turn(ELIYAHU, "אשר", extractor=Ex(), today=TODAY)
    (w,) = c.snapshot["writes"]
    assert w["fields"][EF.KIND] == "monthly_recurring"


def test_income_one_time_review_has_no_recurring_warning():
    seed_sources()
    intent("monthly.income", "recT")
    conv.handle_turn(ELIYAHU, "חד פעמית", extractor=Ex(), today=TODAY)
    r = conv.handle_turn(ELIYAHU, "300", extractor=Ex(fill={"300": {"amount": 300}}), today=TODAY)
    assert r.state == "review" and "לא תיכלל" not in r.message and "חד-פעמי" in r.message


# ── Savings release: the fixed income frees up once the income goal is met from the other sources ─────────────────
def seed_release(income_events, deposits=()):
    DB[Tables.FIN_GOALS] = [
        goal("recInc", "הכנסה חודשית", ELI, 15000, **{GF.CATEGORY: "income"}),
        goal("recFix", "הכנסות נוף הגליל", ELI, 8000, **{GF.CATEGORY: "fixed_income", GF.CALC_METHOD: "recurring_level"}),
        goal("recPen", "תכנון פנסיוני", ELI, None, **{GF.CATEGORY: "long_term"}),
    ]
    DB[Tables.FIN_GOALS][2]["fields"].pop(GF.TARGET_AMOUNT)
    DB[Tables.FIN_EVENTS] = [event(f"recI{i}", "recInc", ELI, a) for i, a in enumerate(income_events)] + \
                            [event(f"recD{i}", "recPen", ELI, a, day="2026-10-05") for i, a in enumerate(deposits)]


def release(**kw):
    return service.overview(ELIYAHU, TODAY)["savings_release"]


def test_recent_events_show_every_existing_kind_exactly_as_before():
    kinds = ("one_time", "monthly_recurring", "target_change", "note", "direct_cost", "household_expense")
    seed_release([], deposits=[])
    DB[Tables.FIN_EVENTS] = [event(f"recK{i}", "recPen", ELI, 100 + i, kind=k, day=f"2026-10-0{i + 1}") for i, k in enumerate(kinds)]
    out = service.overview(ELIYAHU, TODAY)["recent_events"]
    assert [e[EF.KIND] for e in out] == list(reversed(kinds))                       # all six, newest first
    assert set(out[0]) == {"goal_ids", EF.AMOUNT, EF.KIND, EF.OCCURRED_AT, EF.NOTE} and out[0]["goal_ids"] == ["recPen"]
    DB[Tables.FIN_EVENTS][0]["fields"][EF.KIND] = {"name": "one_time"}              # Airtable select object form
    assert len(service.overview(ELIYAHU, TODAY)["recent_events"]) == 6


def test_recent_events_never_show_balance_snapshots_transfers_or_fees_as_progress():
    seed_release([], deposits=[])
    real = [event(f"recR{i}", "recPen", ELI, 50 + i, day=f"2026-09-{10 + i:02d}") for i in range(10)]     # 10 real events, older
    hidden = [event(f"recH{i}", "recPen", ELI, 500000, kind=k, day=f"2026-10-1{i}")                        # newer, would take the slots
              for i, k in enumerate(("balance_snapshot", "withdrawal", "fee", "transfer"))]
    DB[Tables.FIN_EVENTS] = real + hidden + [event("recN", "recPen", ELI, 1, kind=None, day="2026-10-13")]
    out = service.overview(ELIYAHU, TODAY)["recent_events"]
    assert len(out) == 10 and all(e[EF.KIND] == "one_time" for e in out)            # filtered BEFORE the cut: real events keep their slots
    assert all(e[EF.AMOUNT] < 500000 for e in out)
    assert out[0][EF.OCCURRED_AT] == "2026-09-19"

def test_savings_history_is_derived_from_existing_events_and_marks_gaps():
    from datetime import date
    from core.financial_control import calc
    E = calc.Event
    dep = [E(calc.ONE_TIME, 1000, date(2026, 8, 3)), E(calc.ONE_TIME, 500, date(2026, 9, 2)),
           E(calc.ONE_TIME, 700, date(2026, 10, 1)), E(calc.ONE_TIME, 999, date(2026, 10, 2), superseded=True),
           E(calc.ONE_TIME, 400, date(2026, 12, 1))]                       # future-dated: ignored
    plan = [E(calc.MONTHLY_RECURRING, 1000, date(2026, 1, 1))]
    h = calc.deposit_history(dep, plan, date(2026, 10, 14))
    assert (h["ytd"], h["months_elapsed"], h["monthly_average"]) == (2200, 10, 220)
    assert (h["ytd_plan"], h["ytd_gap"], h["streak"], h["deposit_count"]) == (10000, 7800, 3, 3)
    assert h["last_deposit"] == "2026-10-01" and len(h["recent"]) == 12 and h["recent"][-1] == {"month": "2026-10", "deposited": 700, "plan": 1000}
    # no deposit yet this month: the streak still counts through last month; a missed month breaks it
    assert calc.deposit_history(dep[:2], plan, date(2026, 10, 14))["streak"] == 2
    assert calc.deposit_history([E(calc.ONE_TIME, 1, date(2026, 8, 1))], plan, date(2026, 10, 14))["streak"] == 0
    # nothing recorded
    z = calc.deposit_history([], [], date(2026, 1, 5))
    assert (z["ytd"], z["monthly_average"], z["streak"], z["last_deposit"]) == (0, 0, 0, None)


def test_savings_history_in_overview_needs_one_unambiguous_destination():
    seed_release([17000], deposits=[4000])
    h = service.overview(ELIYAHU, TODAY)["savings_history"]
    assert h["ytd"] == 4000 and h["deposit_count"] == 1 and h["streak"] == 1
    DB[Tables.FIN_GOALS].append(goal("recPen2", "קרן נוספת", ELI, None, **{GF.CATEGORY: "long_term"}))
    assert service.overview(ELIYAHU, TODAY)["savings_history"] is None


def test_release_formula_shortfall_comes_out_of_the_fixed_income_and_excess_is_extra():
    for net, avail in ((0, 0), (7000, 0), (10000, 3000), (15000, 8000), (17000, 10000)):
        seed_release([net] if net else [])
        r = release()
        assert r["available"] == avail, (net, r)
    seed_release([10000])
    r = release()
    assert (r["shortfall"], r["from_fixed"], r["extra"], r["fixed_level"], r["income_target"]) == (5000, 3000, 0, 8000, 15000)
    assert r["destination"]["id"] == "recPen" and r["remaining"] == 3000 and r["month"] == "2026-10"


def test_release_counts_deposits_this_month_and_reports_the_gap_against_a_full_month():
    seed_release([17000], deposits=[4000])
    r = release()
    assert r["available"] == 10000 and r["deposited"] == 4000 and r["remaining"] == 6000
    assert r["expected"] == 10000 and r["gap"] == 6000
    seed_release([10000], deposits=[3000])
    r = release()
    assert r["remaining"] == 0 and r["expected"] == 8000 and r["gap"] == 5000        # 15,000 not reached: the missing part is the gap


def test_release_is_none_without_a_fixed_income_and_never_reads_titles():
    seed_release([10000])
    DB[Tables.FIN_GOALS][1]["fields"][GF.CATEGORY] = "other"
    assert release() is None


def test_deposit_intent_prefills_the_freed_amount_on_the_pension_goal_and_writes_one_event():
    seed_release([10000])
    r = intent("savings.deposit")
    assert r.state == "review" and "₪3,000" in r.message and "• יעד: תכנון פנסיוני" in r.message
    c = conv.handle_turn(ELIYAHU, "אשר", extractor=Ex(), today=TODAY)
    (w,) = c.snapshot["writes"]
    f = w["fields"]
    assert w["table"] == Tables.FIN_EVENTS and f[EF.GOAL] == ["recPen"] and f[EF.AMOUNT] == 3000 and f[EF.KIND] == "one_time"


def test_deposit_amount_is_editable_and_nothing_freed_asks_for_an_amount():
    seed_release([10000])
    intent("savings.deposit")
    r = conv.handle_turn(ELIYAHU, "ערוך", extractor=Ex(), today=TODAY)
    assert r.state == "ask"
    conv.handle_turn(ELIYAHU, "בטל", extractor=Ex(), today=TODAY)
    seed_release([5000])
    r = intent("savings.deposit")
    assert r.state == "ask" and r.awaiting == "amount"


def test_gap_reason_is_documented_as_a_note_event_with_the_chosen_reason():
    seed_release([10000])                                   # 15,000 not reached, nothing deposited: gap 8,000
    r = intent("savings.gap_reason")
    assert r.state == "ask" and r.awaiting == "reason"
    assert [c["goal_id"] for c in r.candidates] == ["extra_fixed", "extra_home", "income_hard"]
    r = conv.handle_turn(ELIYAHU, "x", goal_id="extra_fixed", extractor=Ex(), today=TODAY)
    assert r.state == "review" and "פער הפקדה 2026-10: הוצאה חריגה בנוף הגליל" in r.message
    c = conv.handle_turn(ELIYAHU, "אשר", extractor=Ex(), today=TODAY)
    (w,) = c.snapshot["writes"]
    assert w["fields"][EF.KIND] == "note" and w["fields"][EF.GOAL] == ["recPen"] and w["fields"][EF.AMOUNT] == 8000


def test_gap_reason_accepts_free_text_and_rejects_command_words_and_no_gap_is_info():
    seed_release([10000])
    intent("savings.gap_reason")
    assert conv.handle_turn(ELIYAHU, "אשר", extractor=Ex(), today=TODAY).awaiting == "reason"
    r = conv.handle_turn(ELIYAHU, "הלוואה דחופה לקרוב", extractor=Ex(), today=TODAY)
    assert r.state == "review" and "הלוואה דחופה לקרוב" in r.message
    conv.handle_turn(ELIYAHU, "בטל", extractor=Ex(), today=TODAY)
    seed_release([15000], deposits=[8000])
    assert intent("savings.gap_reason").state == "info"


def test_savings_intents_are_owner_scoped_and_income_followup_flags_only_income_events():
    seed_release([10000])
    assert intent("savings.deposit", who=AVI_I).state in ("clarify", "denied", "needs_goal", "ask", "review", "info")
    snap = {"writes": [{"table": Tables.FIN_EVENTS, "fields": {EF.KIND: "one_time", EF.GOAL: ["recInc"]}}]}
    assert conv.income_followup(ELIYAHU, snap) is True
    assert conv.income_followup(ELIYAHU, {"writes": [{"table": Tables.FIN_EVENTS, "fields": {EF.KIND: "one_time", EF.GOAL: ["recPen"]}}]}) is False
    assert conv.income_followup(ELIYAHU, {"writes": [{"table": Tables.FIN_EVENTS, "fields": {EF.KIND: "household_expense", EF.GOAL: ["recInc"]}}]}) is False


# ── Next step: a free-text answer is taken verbatim; the model is not on this path ───────────────────────────────
def _boom(**kw):
    raise RuntimeError("the model must not be called for a free-text next step")


def test_next_step_command_words_and_blank_are_not_a_step(monkeypatch):
    import llm_fallback
    monkeypatch.setattr(llm_fallback, "call_anthropic_text", _boom)
    seed_p3()
    intent("asset.next_step", "recAH")
    for word in ("דלג", "אשר"):
        r = conv.handle_turn(ELIYAHU, word, extractor=conv.DeterministicExtractor(), today=TODAY, scope="assets")
        assert r.awaiting == "step" or r.state == "info", (word, r.state)


def test_a_model_failure_is_not_understood_never_a_crashed_turn(monkeypatch):
    import llm_fallback
    monkeypatch.setattr(llm_fallback, "call_anthropic_text", _boom)
    seed_intents()
    intent("monthly.income", "recGI")
    conv.handle_turn(ELIYAHU, "חד-פעמית", goal_id="one_time", extractor=Ex(), today=TODAY)
    r = conv.handle_turn(ELIYAHU, "כמה מאה ועשרים", extractor=conv.DeterministicExtractor(), today=TODAY)       # free-form amount needs the model
    assert r.state in ("ask", "unrelated") and r.awaiting == "amount"


# ── The TMA writer is deterministic: no model anywhere on the path (credits exhausted / model down must not matter) ──
def _say(text, goal_id=None, scope="monthly"):
    return conv.handle_turn(ELIYAHU, text, goal_id=goal_id, extractor=conv.DeterministicExtractor(), today=TODAY, scope=scope)


@pytest.fixture
def no_model(monkeypatch):
    import llm_fallback
    monkeypatch.setattr(llm_fallback, "call_anthropic_text", _boom)


def test_new_goal_is_built_from_a_chip_with_buttons_and_typed_values_without_a_model(no_model):
    seed_intents()
    r = intent("monthly.goal_new")
    assert r.state == "ask" and r.awaiting == "title"
    r = _say("קרן לימודים")
    assert r.awaiting == "target_amount"
    r = _say("120000")
    assert r.awaiting == "category" and {c["title"] for c in r.candidates} >= {"חיסכון חודשי", "קרן חירום", "חוב"}
    r = _say("קרן חירום", goal_id="emergency_fund")                      # a button click == typing the label
    assert r.awaiting == "end_date"
    r = _say("2027-06-30")
    assert r.state == "review" and "קרן לימודים" in r.message and "₪120,000" in r.message
    (w,) = _say("אשר").snapshot["writes"]
    assert w["table"] == Tables.FIN_GOALS and w["fields"][GF.TITLE] == "קרן לימודים" and w["fields"][GF.TARGET_AMOUNT] == 120000


def test_review_edit_grammar_is_label_then_value_and_unknown_text_is_not_understood(no_model):
    seed_intents()
    intent("monthly.goal_new")
    _say("שכר דירה")
    _say("5000")
    r = _say("הכנסה", goal_id="income")                                  # income: period / method / end date are inferred
    assert r.state == "review" and "₪5,000" in r.message
    assert _say("ערוך").state == "ask"
    r = _say("סכום 8000")
    assert r.state == "review" and "₪8,000" in r.message
    _say("ערוך")
    r = _say("משהו שלא מובן")                                             # no label: nothing is changed, nothing is guessed
    assert r.state in ("ask", "unrelated")
    assert conv.pending_view(ELIYAHU) is not None


def test_obligation_chip_asks_choices_as_buttons_and_stores_the_typed_name_verbatim(no_model):
    seed_intents()
    r = intent("monthly.obligation")
    assert r.awaiting == "name"
    r = _say("נטפליקס")
    assert r.awaiting == "amount"
    r = _say("70")
    assert r.awaiting == "scope" and {c["goal_id"] for c in r.candidates} == {"household", "business", "personal"}
    r = _say("ביתי", goal_id="household")                                   # frequency defaults to monthly: straight to review
    assert r.state == "review" and "נטפליקס" in r.message and "ביתי" in r.message


def test_a_new_loan_is_collected_without_a_model(no_model):
    seed_intents()
    r = intent("loan.create")
    for expect, answer, gid in (("name", "בנק מזרחי", None), ("loan_type", "פרטית", "private"), ("balance", "50000", None),
                                ("payment", "1500", None), ("rate", "5.5", None)):
        assert r.awaiting == expect, (expect, r.awaiting)
        r = _say(answer, goal_id=gid, scope="loans")
    assert r.state == "review" and "בנק מזרחי" in r.message


def test_goal_update_edit_is_label_then_value_without_a_model(no_model):
    seed_intents()
    r = intent("monthly.goal_update", "recGK")
    assert r.state == "ask"
    r = _say("סכום 75000")
    assert r.state == "review" and "₪75,000" in r.message
    (w,) = _say("אשר").snapshot["writes"]
    assert w["table"] == Tables.FIN_EVENTS and w["fields"][EF.AMOUNT] == 75000 and w["fields"][EF.KIND] == "target_change"


# ── Asset next actions are TASKS: several open, a life cycle (בתהליך / בוצע / בוטלה), edit; the legacy text stays ───────
def step_task(tid, asset, title, owner=None, status="ממתין", due=None, owner_profile=ELI, extra=""):
    desc = f"[FCC-ASSET:{asset}]" + (f"\nאחראי: {owner}" if owner else "") + (f"\n{extra}" if extra else "")
    f = {TaskFields.NAME: title, TaskFields.STATUS: status, TaskFields.DESCRIPTION: desc, TaskFields.TOPIC: "כספים",
         TaskFields.OWNER: [owner_profile]}
    if due:
        f[TaskFields.DUE_DATE] = due
    return {"id": tid, "fields": f}


def _confirm_one():
    return conv.handle_turn(ELIYAHU, "אשר", extractor=conv.DeterministicExtractor(), today=TODAY).snapshot["writes"]


def test_a_new_next_action_is_a_new_task_and_the_open_ones_stay(no_model):
    seed_p3()
    DB[Tables.TASKS] = [step_task("t1", "recAH", "לשלוח הצעה")]
    r = intent("asset.next_step", "recAH")
    assert r.awaiting == "step" and "1" in r.message                           # "open actions in the asset right now: 1"
    r = _say("לבדוק תכנית בנייה", scope="assets")
    assert r.state == "review" and "משימת מעקב חדשה" in r.message and "נשארות" in r.message
    _say("ערוך", scope="assets"); _say("אחראי אורי", scope="assets")
    _say("ערוך", scope="assets"); r = _say("תאריך יעד 2026-11-01", scope="assets")
    assert "2026-11-01" in r.message or "01/11/2026" in r.message
    (w,) = _confirm_one()
    f = w["fields"]
    assert w["op"] == "post" and w["table"] == Tables.TASKS
    assert f[TaskFields.NAME] == "לבדוק תכנית בנייה" and f[TaskFields.STATUS] == "ממתין" and f[TaskFields.TOPIC] == "כספים"
    assert f[TaskFields.OWNER] == [ELI] and f[TaskFields.DUE_DATE] == "2026-11-01"
    assert f[TaskFields.DESCRIPTION] == "[FCC-ASSET:recAH]\nאחראי: אורי"        # tag first, then who is responsible
    assert AF.NEXT_STEP not in f                                                # the legacy asset field is no longer written


def test_start_done_and_cancel_are_status_moves_with_a_history_line_and_a_review(no_model):
    seed_p3()
    DB[Tables.TASKS] = [step_task("t1", "recAH", "לשלוח הצעה", owner="אורי")]
    r = intent("asset.step_start", "t1")
    assert r.state == "review" and "לשלוח הצעה" in r.message and "בתהליך" in r.message and r.snapshot is None   # nothing written before אשר
    (w,) = _confirm_one()
    assert w["op"] == "patch" and w["record_id"] == "t1" and w["fields"][TaskFields.STATUS] == "בביצוע"
    assert w["fields"][TaskFields.DESCRIPTION].startswith("[FCC-ASSET:recAH]\nאחראי: אורי\nהתחילה ב־2026-10-08")
    conv.complete_execution(ELIYAHU)
    DB[Tables.TASKS][0]["fields"][TaskFields.STATUS] = "בביצוע"
    assert intent("asset.step_start", "t1").state == "info"                     # already in progress
    intent("asset.step_done", "t1")
    (w,) = _confirm_one()
    assert w["fields"][TaskFields.STATUS] == "בוצע" and "הושלמה ב־2026-10-08" in w["fields"][TaskFields.DESCRIPTION]
    conv.complete_execution(ELIYAHU)
    intent("asset.step_cancel", "t1")
    (w,) = _confirm_one()
    assert w["fields"][TaskFields.STATUS] == "בוצע" and "בוטלה ב־2026-10-08" in w["fields"][TaskFields.DESCRIPTION]   # no new Status choice


def test_edit_one_action_changes_only_that_task_and_keeps_its_history(no_model):
    seed_p3()
    DB[Tables.TASKS] = [step_task("t1", "recAH", "לשלוח הצעה", owner="אורי", due="2026-10-20", extra="התחילה ב־2026-10-05"),
                        step_task("t2", "recAH", "לבדוק מחיר")]
    r = intent("asset.step_edit", "t1")
    assert r.state == "ask" and "לשלוח הצעה" in r.message or r.state == "ask"
    r = _say("שלוח הצעה מעודכנת — רק חלק מהתכנית התחיל", scope="assets")
    assert r.state == "review" and "רק חלק מהתכנית התחיל" in r.message
    (w,) = _confirm_one()
    assert w["op"] == "patch" and w["record_id"] == "t1" and w["fields"][TaskFields.NAME] == "שלוח הצעה מעודכנת — רק חלק מהתכנית התחיל"
    assert w["fields"][TaskFields.DUE_DATE] == "2026-10-20"
    assert w["fields"][TaskFields.DESCRIPTION] == "[FCC-ASSET:recAH]\nאחראי: אורי\nהתחילה ב־2026-10-05"   # owner + history preserved
    assert "t2" not in str(w)


def test_task_actions_are_owner_scoped_and_a_closed_or_foreign_task_is_not_found(no_model):
    seed_p3()
    DB[Tables.TASKS] = [step_task("tAvi", "recAX", "של אבי", owner_profile=AVI), step_task("tDone", "recAH", "סגורה", status="בוצע"),
                        step_task("tMine", "recAH", "שלי")]
    for tid in ("tAvi", "tDone", "tNope"):
        for iid in ("asset.step_edit", "asset.step_start", "asset.step_done", "asset.step_cancel"):
            assert intent(iid, tid).state == "denied", (iid, tid)
    assert intent("asset.step_done").state == "clarify"
    assert intent("asset.step_done", "tMine", who=AVI_I).state == "denied"      # Avi cannot move Eliyahu's task


def test_a_task_patch_is_idempotent_and_a_closed_task_is_not_written_again(no_model):
    seed_p3()
    DB[Tables.TASKS] = [step_task("t1", "recAH", "לשלוח הצעה")]
    intent("asset.step_done", "t1")
    DB[Tables.TASKS][0]["fields"][TaskFields.STATUS] = "בוצע"                    # closed meanwhile (another device)
    assert conv.handle_turn(ELIYAHU, "אשר", extractor=conv.DeterministicExtractor(), today=TODAY).state == "duplicate"


def test_finishing_an_action_offers_the_next_one_for_that_asset_only():
    done = {"writes": [{"op": "patch", "table": Tables.TASKS, "record_id": "t1",
                        "fields": {TaskFields.STATUS: "בוצע", TaskFields.DESCRIPTION: "[FCC-ASSET:recAH]\nהושלמה ב־2026-10-08"}}]}
    assert conv.next_step_followup(done) == "recAH"
    started = {"writes": [{"op": "patch", "table": Tables.TASKS, "record_id": "t1",
                           "fields": {TaskFields.STATUS: "בביצוע", TaskFields.DESCRIPTION: "[FCC-ASSET:recAH]"}}]}
    assert conv.next_step_followup(started) is None and conv.next_step_followup(None) is None
    goal_task = {"writes": [{"op": "patch", "table": Tables.TASKS, "fields": {TaskFields.STATUS: "בוצע", TaskFields.DESCRIPTION: "[FCC:recG]"}}]}
    assert conv.next_step_followup(goal_task) is None


def test_goal_follow_up_list_ignores_asset_actions_and_vice_versa(no_model):
    seed_p3()
    DB[Tables.TASKS] = [step_task("t1", "recAH", "פעולת נכס"),
                        {"id": "g1", "fields": {TaskFields.NAME: "משימת יעד", TaskFields.STATUS: "ממתין", TaskFields.TOPIC: "כספים",
                                                TaskFields.DESCRIPTION: "[FCC:recG1] x", TaskFields.OWNER: [ELI]}}]
    assert [t["id"] for t in service.asset_tasks(ELIYAHU)] == ["t1"]
    assert [t["id"] for t in service.fcc_tasks(ELIYAHU)] == ["g1"]


def test_p3_http_next_action_creates_a_task_and_the_executor_rechecks_the_owner(monkeypatch, no_model):
    seed_p3()
    sent = []
    monkeypatch.setattr(tma_api, "_queue_or_owner_execute",
                        lambda action, payload, identity, label: (sent.append(payload) or ("a", {"ok": True}, 200)))
    c = http(monkeypatch, ELIYAHU)
    assert c.post("/api/fcc/intent/start", json={"intent": "asset.next_step", "entity_id": "recAH"}, headers=H).get_json()["awaiting"] == "step"
    assert c.post("/api/fcc/write", json={"text": "לדבר עם המתווך", "scope": "assets"}, headers=H).get_json()["state"] == "review"
    assert sent == []
    done = c.post("/api/fcc/write", json={"text": "אשר", "scope": "assets"}, headers=H).get_json()
    assert done["state"] == "executed" and done["follow_up_asset"] is None
    assert sent[0]["table"] == Tables.TASKS and sent[0]["op"] == "post" and sent[0]["fields"][TaskFields.NAME] == "לדבר עם המתווך"
    assert Tables.TASKS in approval_actions._TMA_WRITE_ALLOWED_TABLES
    DB[Tables.TASKS] = [step_task("t1", "recAH", "x")]
    c.post("/api/fcc/intent/start", json={"intent": "asset.step_done", "entity_id": "t1"}, headers=H)
    done = c.post("/api/fcc/write", json={"text": "אשר", "scope": "assets"}, headers=H).get_json()
    assert done["state"] == "executed" and done["follow_up_asset"] == "recAH"       # the screen then asks for the next action


# ── Free text for a next action: what is stored, what is a rule, what is rejected ───────────────────────────────────
def _edit_say(text):
    return _say(text, scope="assets")


def test_next_action_text_is_stored_whole_even_when_it_starts_with_a_label_word(no_model):
    seed_p3()
    intent("asset.next_step", "recAH")
    r = _edit_say("הפעולה הבאה: לשלוח הצעה, ואחראי אורי יבדוק")                 # contains label words, still just text
    assert r.state == "review" and "הפעולה הבאה: לשלוח הצעה, ואחראי אורי יבדוק" in r.message
    _edit_say("ערוך")
    r = _edit_say("הפעולה מעודכנת לגמרי")                                       # in edit too: no label is needed for the action text
    assert r.state == "review" and "הפעולה מעודכנת לגמרי" in r.message
    (w,) = _confirm_one()
    assert w["fields"][TaskFields.NAME] == "הפעולה מעודכנת לגמרי"


def test_action_text_is_one_line_and_capped_and_command_words_are_not_an_action(no_model):
    seed_p3()
    intent("asset.next_step", "recAH")
    r = _edit_say("שורה ראשונה\n\n   שורה   שנייה\t")
    assert "שורה ראשונה שורה שנייה" in r.message
    _edit_say("ערוך")
    r = _edit_say("א" * 800)
    (w,) = _confirm_one()
    assert len(w["fields"][TaskFields.NAME]) == 500 and "\n" not in w["fields"][TaskFields.NAME]
    conv.complete_execution(ELIYAHU)
    intent("asset.next_step", "recAH")
    for word in ("אשר", "דלג", "ערוך"):
        assert _edit_say(word).awaiting == "step", word                          # a command word is never taken as the action


def test_owner_and_due_date_rules_reject_what_they_cannot_parse_instead_of_storing_it_as_text(no_model):
    seed_p3()
    intent("asset.next_step", "recAH")
    _edit_say("לשלוח הצעה")
    _edit_say("ערוך")
    for bad in ("אחראי דוד", "אחראי", "תאריך יעד מתישהו"):
        r = _edit_say(bad)
        assert r.state == "unrelated", bad                                       # not understood; nothing changed
        _edit_say("ערוך") if r.state != "review" else None
    r = _edit_say("אחראי אהרן")
    assert r.state == "review" and "אהרן" in r.message and "לשלוח הצעה" in r.message
    _edit_say("ערוך")
    r = _edit_say("תאריך יעד 2026-12-01")
    (w,) = _confirm_one()
    assert w["fields"][TaskFields.NAME] == "לשלוח הצעה" and w["fields"][TaskFields.DUE_DATE] == "2026-12-01"
    assert w["fields"][TaskFields.DESCRIPTION] == "[FCC-ASSET:recAH]\nאחראי: אהרן"


# ═══ Debts owed TO the owner, partial repayment, repayment arrangement, loan next actions ═══
DEBT_GOAL = lambda: goal("recGD", "סגירת הלוואות", ELI, 700000, **{GF.CATEGORY: "debt", GF.CALC_METHOD: "cumulative"})


def seed_debts(with_goal=True):
    DB[Tables.FIN_GOALS] = [DEBT_GOAL()] if with_goal else []
    DB[Tables.FIN_EVENTS] = []
    DB[Tables.LOANS] = [
        loan("recM", **{LF.NAME: "כאל", LF.EARLY_CLOSURE: 55000, LF.MONTHLY_PAYMENT: 1182.65, LF.INTEREST_RATE: 6, LF.PAYMENTS_LEFT: 40,
                        LF.NOTES: "לכל מטרה"}),
        loan("recR", **{LF.NAME: "דני", LF.EARLY_CLOSURE: 20000, LF.DIRECTION: "חייבים לי"}),
        loan("recN", **{LF.NAME: "בלי יתרה"}),
        loan("recX", owner=AVI, **{LF.NAME: "של אבי", LF.EARLY_CLOSURE: 777}),
    ]
    DB["Assets"] = [asset("recAH", "בית שמש", **{AF.STATUS: {"name": "פעיל"}}), asset("recAS", "נמכר", **{AF.STATUS: {"name": "נמכר"}}),
                    asset("recAX", "נכס של אבי", owner=AVI)]


def _loans_view():
    return service.loans_overview(ELIYAHU, TODAY)


def test_a_debt_owed_to_the_owner_is_listed_apart_and_never_counted_as_his_liability():
    seed_debts()
    v = _loans_view()
    by_id = {i["id"]: i for i in v["items"]}
    assert by_id["recR"]["direction"] == "owed_to_me" and by_id["recM"]["direction"] == "owed_by_me" and by_id["recN"]["direction"] == "owed_by_me"
    assert v["summary"]["total_early_closure_balance"] == 55000                 # 20,000 owed to him is not in the liabilities
    assert v["summary"]["total_active_loans"] == 2
    assert "recR" not in v["rankings"]["small_balance"] and "recR" not in str(v["payoff"])
    assert v["receivables"] == {"count": 1, "total_balance": 20000.0, "coverage": 1, "no_arrangement": 1}
    assert fcc_loans.loan_item(DB[Tables.LOANS][1], TODAY)["arrangement"] is None
    assert "777" not in str(v)                                                  # another owner's row never reaches the payload


def test_receivables_are_excluded_from_asset_debt_and_from_the_budget_simulator():
    seed_debts()
    DB[Tables.LOANS][1]["fields"][LF.RELATED_ASSET] = ["recAH"]
    a = service.assets_overview(ELIYAHU, _loans_view()["items"])
    assert a["summary"]["linked_loans_count"] == 0 and a["summary"]["unlinked_loans_debt"] == 55000
    sc = service.loan_scenarios(ELIYAHU, 1_000_000, TODAY)
    assert "דני" not in str(sc)


def test_partial_payment_asks_amount_then_where_the_money_came_from_then_reviews_old_to_new(no_model):
    seed_debts()
    r = intent("loan.partial_payment", "recM")
    assert r.state == "ask" and r.awaiting == "amount" and "כמה שילמת" in r.message
    r = _say("5,000", scope="loans")
    assert r.state == "ask" and r.awaiting == "destination" and "מאיפה שולם" in r.message
    assert [c["goal_id"] for c in r.candidates] == ["savings", "current", "asset:recAH"]      # own, held assets only (sold / foreign are not offered)
    r = _say("שוטף", goal_id="current", scope="loans")
    assert r.state == "review"
    assert "₪55,000 ← ₪50,000" in r.message and "מקור התשלום: שוטף" in r.message and "סגירת הלוואות" in r.message
    patch, event = _confirm_one()
    assert patch["op"] == "patch" and patch["record_id"] == "recM" and patch["fields"][LF.EARLY_CLOSURE] == 50000.0
    assert patch["fields"][LF.NOTES].startswith("לכל מטרה\nפרעון חלקי ₪5,000 ב־08/10/2026 — מקור התשלום: שוטף")   # the old note is kept
    assert LF.MONTHLY_PAYMENT not in patch["fields"] and LF.STATUS not in patch["fields"]
    assert event["table"] == Tables.FIN_EVENTS and event["fields"][EF.AMOUNT] == 5000 and event["fields"][EF.GOAL] == ["recGD"]
    assert "פרעון חלקי: כאל" in event["fields"][EF.NOTE]


def test_partial_payment_destination_is_one_of_the_presented_places_only(no_model):
    seed_debts()
    intent("loan.partial_payment", "recM")
    _say("1000", scope="loans")
    for bad in ("איפשהו", "asset:recAS", "asset:recAX", "אשר"):
        r = _say(bad, scope="loans")
        assert r.state == "ask" and r.awaiting == "destination", bad
    r = _say("נכס: בית שמש", scope="loans")                                       # typing the button label also works
    assert r.state == "review" and "נכס: בית שמש" in r.message


def test_partial_payment_cannot_exceed_the_balance_and_points_to_closing(no_model):
    seed_debts()
    intent("loan.partial_payment", "recM")
    r = _say("60000", scope="loans")
    assert r.awaiting == "amount" and "סגירת הלוואה" in r.message
    r = _say("55000", scope="loans")                                              # exactly the balance is still allowed: balance 0, not closed
    assert r.awaiting == "destination"


def test_partial_payment_on_a_debt_owed_to_the_owner_is_not_income_and_has_no_goal_event(no_model):
    seed_debts()
    r = intent("loan.partial_payment", "recR")
    assert "החזיר" in r.message
    r = _say("5000", scope="loans")
    assert "מה נעשה עם הכסף" in r.message
    r = _say("חיסכון", goal_id="savings", scope="loans")
    assert "אינו הכנסה" in r.message and "יעד הכסף: חיסכון" in r.message and "אירוע התקדמות" not in r.message
    (patch,) = _confirm_one()
    assert patch["fields"][LF.EARLY_CLOSURE] == 15000.0 and "הכסף הועבר לחיסכון" in patch["fields"][LF.NOTES]
    assert DB[Tables.FIN_EVENTS] == []                                            # nothing was booked on any goal


def test_partial_payment_with_unknown_balance_only_logs_history_and_without_debt_goal_books_no_event(no_model):
    seed_debts(with_goal=False)
    intent("loan.partial_payment", "recN")
    _say("300", scope="loans")
    r = _say("שוטף", goal_id="current", scope="loans")
    assert "לא הוגדרה" in r.message and "בלי אירוע התקדמות" in r.message
    (patch,) = _confirm_one()
    assert set(patch["fields"]) == {LF.NOTES}                                     # no balance is invented


def test_partial_payment_is_idempotent_and_owner_scoped(no_model):
    seed_debts()
    intent("loan.partial_payment", "recM")
    _say("5000", scope="loans"); _say("שוטף", goal_id="current", scope="loans")
    writes = _confirm_one()
    DB[Tables.LOANS][0]["fields"].update(writes[0]["fields"])                     # the patch landed
    DB[Tables.FIN_EVENTS].append({"id": "e1", "fields": {**writes[1]["fields"], EF.FINANCIAL_OWNER: [ELI]}})
    assert not [w for w in writes if not conv._already_applied(ELIYAHU, w)]       # a retry writes nothing twice
    conv.complete_execution(ELIYAHU)
    assert intent("loan.partial_payment", "recX").state == "denied"               # Avi's loan is "not found"
    assert intent("loan.partial_payment").state == "clarify"


def _arrangement_flow(text_after_loan):
    seed_debts()
    r = intent("loan.arrangement", "recR")
    assert r.awaiting == "arrangement" and "לא הוגדר הסדר פירעון" in r.message
    assert [c["title"] for c in r.candidates] == ["פירעון חודשי קבוע", "מועד פירעון", "אין הסדר"]
    return r


def test_arrangement_monthly_asks_for_the_amount_and_stores_schedule_amount_and_a_note_line(no_model):
    _arrangement_flow(None)
    r = _say("פירעון חודשי קבוע", scope="loans")
    assert r.awaiting == "payment"
    r = _say("1500", scope="loans")
    assert r.state == "review" and "פירעון חודשי: ₪1,500" in r.message
    (w,) = _confirm_one()
    assert w["record_id"] == "recR" and w["fields"][LF.PAYMENT_SCHED] == "Monthly" and w["fields"][LF.MONTHLY_PAYMENT] == 1500
    assert "הסדר פירעון (2026-10-08): פירעון חודשי ₪1,500" in w["fields"][LF.NOTES] and LF.EARLY_CLOSURE not in w["fields"]


def test_arrangement_deadline_asks_for_a_date_and_none_writes_only_a_note(no_model):
    _arrangement_flow(None)
    _say("מועד פירעון", scope="loans")
    assert _say("מתישהו", scope="loans").awaiting == "end_date"                     # not a date -> asked again
    r = _say("2027-03-01", scope="loans")
    assert r.state == "review"
    (w,) = _confirm_one()
    assert w["fields"][LF.PAYMENT_SCHED] == "Custom" and w["fields"][LF.END_DATE] == "2027-03-01" and LF.MONTHLY_PAYMENT not in w["fields"]
    conv.complete_execution(ELIYAHU)
    intent("loan.arrangement", "recR")
    r = _say("אין הסדר", scope="loans")
    assert r.state == "review"
    (w,) = _confirm_one()
    assert set(w["fields"]) == {LF.NOTES} and "אין הסדר פירעון" in w["fields"][LF.NOTES]


def test_an_arrangement_shows_on_the_card_after_it_is_stored():
    seed_debts()
    DB[Tables.LOANS][1]["fields"].update({LF.MONTHLY_PAYMENT: 1500})
    assert {i["id"]: i for i in _loans_view()["items"]}["recR"]["arrangement"] == "monthly"
    assert _loans_view()["receivables"]["no_arrangement"] == 0
    DB[Tables.LOANS][1]["fields"].update({LF.MONTHLY_PAYMENT: None, LF.END_DATE: "2027-01-01"})
    assert {i["id"]: i for i in _loans_view()["items"]}["recR"]["arrangement"] == "deadline"


def test_a_new_debt_owed_to_the_owner_is_created_with_its_repayment_mechanism(no_model):
    seed_debts()
    r = intent("loan.receivable_new")
    assert r.awaiting == "name" and "מי חייב לך" in r.message
    assert _say("דני כהן", scope="loans").awaiting == "balance"
    assert _say("12000", scope="loans").awaiting == "arrangement"
    assert _say("פירעון חודשי קבוע", scope="loans").awaiting == "payment"
    r = _say("1000", scope="loans")
    assert r.state == "review" and "חוב שחייבים לך" in r.message
    (w,) = _confirm_one()
    f = w["fields"]
    assert w["op"] == "post" and w["table"] == Tables.LOANS
    assert f[LF.NAME] == "דני כהן" and f[LF.LENDER] == "דני כהן" and f[LF.EARLY_CLOSURE] == 12000 and f[LF.ACTIVE] is True
    assert f[LF.DIRECTION] == "חייבים לי" and f[LF.PAYMENT_SCHED] == "Monthly" and f[LF.MONTHLY_PAYMENT] == 1000
    assert LF.LOAN_TYPE not in f and LF.INTEREST_RATE not in f
    conv.complete_execution(ELIYAHU)
    DB[Tables.LOANS].append({"id": "recNew", "fields": {**f, "Owner": [ELI]}})
    intent("loan.receivable_new"); _say("דני כהן", scope="loans"); _say("5", scope="loans"); _say("אין הסדר", scope="loans")
    assert conv.handle_turn(ELIYAHU, "אשר", extractor=conv.DeterministicExtractor(), today=TODAY).state == "duplicate"


def test_closing_a_debt_owed_to_the_owner_marks_it_paid_without_a_goal_event(no_model):
    seed_debts()
    r = conv.start_loan_close(ELIYAHU, "recR", today=TODAY)
    assert "חוב שחייבים לך" in r.message
    writes = _confirm_one()
    assert len(writes) == 1 and writes[0]["fields"] == {LF.STATUS: "Paid Off"}


def loan_step_task(tid, loan_id, title, **kw):
    t = step_task(tid, loan_id, title, **kw)
    t["fields"][TaskFields.DESCRIPTION] = t["fields"][TaskFields.DESCRIPTION].replace("[FCC-ASSET:", "[FCC-LOAN:")
    return t


def test_a_loan_next_action_is_a_task_tagged_with_the_loan_and_never_mixes_with_assets(no_model):
    seed_debts()
    DB[Tables.TASKS] = [loan_step_task("tl1", "recR", "להתקשר לדני", due="2026-10-20"), step_task("ta1", "recAH", "פעולת נכס")]
    assert [t["id"] for t in service.loan_tasks(ELIYAHU)] == ["tl1"] and [t["id"] for t in service.asset_tasks(ELIYAHU)] == ["ta1"]
    assert {i["id"]: i for i in _loans_view()["items"]}["recR"]["actions"][0]["title"] == "להתקשר לדני"
    assert service.assets_overview(ELIYAHU, _loans_view()["items"])["items"][0]["actions"][0]["title"] == "פעולת נכס"
    r = intent("loan.next_step", "recR")
    assert r.awaiting == "step" and "דני" in r.message and "1" in r.message
    r = _say("לדרוש שיק", scope="loans")
    assert r.state == "review" and "פעולה הבאה בהלוואה" in r.message and "משימת מעקב חדשה" in r.message
    (w,) = _confirm_one()
    assert w["op"] == "post" and w["table"] == Tables.TASKS and w["fields"][TaskFields.NAME] == "לדרוש שיק"
    assert w["fields"][TaskFields.DESCRIPTION] == "[FCC-LOAN:recR]" and w["fields"][TaskFields.TOPIC] == "כספים"
    conv.complete_execution(ELIYAHU)
    assert intent("loan.next_step", "recX").state == "denied"


def test_loan_next_action_life_cycle_edit_start_done_cancel_keep_the_loan_tag(no_model):
    seed_debts()
    DB[Tables.TASKS] = [loan_step_task("tl1", "recR", "להתקשר לדני", owner="אורי")]
    intent("asset.step_start", "tl1")
    (w,) = _confirm_one()
    assert w["record_id"] == "tl1" and w["fields"][TaskFields.STATUS] == "בביצוע" and w["fields"][TaskFields.DESCRIPTION].startswith("[FCC-LOAN:recR]")
    conv.complete_execution(ELIYAHU)
    intent("asset.step_edit", "tl1")
    r = _say("להתקשר לדני ולשלוח הודעה", scope="loans")
    assert r.state == "review" and "עריכת פעולה בהלוואה" in r.message
    (w,) = _confirm_one()
    assert w["fields"][TaskFields.DESCRIPTION] == "[FCC-LOAN:recR]\nאחראי: אורי"          # tag + owner survive an edit
    conv.complete_execution(ELIYAHU)
    DB[Tables.TASKS].append(loan_step_task("tl2", "recX", "של אבי", owner_profile=AVI))
    assert intent("asset.step_done", "tl2").state == "denied"                            # not the owner's -> not found
    intent("asset.step_done", "tl1")
    (w,) = _confirm_one()
    assert w["fields"][TaskFields.STATUS] == "בוצע" and "[FCC-LOAN:recR]" in w["fields"][TaskFields.DESCRIPTION]
    assert conv.next_step_followup({"writes": [w]}) is None                              # the "next action?" prompt is for assets only


def test_loan_task_post_is_not_written_twice(no_model):
    seed_debts()
    DB[Tables.TASKS] = [loan_step_task("tl1", "recR", "להתקשר לדני")]
    intent("loan.next_step", "recR")
    _say("להתקשר לדני", scope="loans")
    assert conv.handle_turn(ELIYAHU, "אשר", extractor=conv.DeterministicExtractor(), today=TODAY).state == "duplicate"


def test_new_loan_intents_are_registered_and_none_is_a_transition():
    for iid, ent in (("loan.partial_payment", "fcc_loan_partial"), ("loan.arrangement", "fcc_loan_arrangement"),
                     ("loan.receivable_new", "fcc_receivable_new"), ("loan.next_step", "fcc_asset_step")):
        assert fd.INTENTS[iid]["entity"] == ent and fd.INTENTS[iid]["tab"] == "loans" and not fd.INTENTS[iid].get("transition")
    assert fd.INTENTS["loan.partial_payment"]["target_required"] and fd.INTENTS["loan.arrangement"]["target_required"]
    assert "target_required" not in fd.INTENTS["loan.receivable_new"]


def test_http_partial_payment_runs_the_same_review_then_executes_the_frozen_writes(monkeypatch, no_model):
    seed_debts()
    sent = []
    monkeypatch.setattr(tma_api, "_queue_or_owner_execute",
                        lambda action, payload, identity, label: (sent.append(payload) or ("a", {"ok": True}, 200)))
    c = http(monkeypatch, ELIYAHU)
    assert c.post("/api/fcc/intent/start", json={"intent": "loan.partial_payment", "entity_id": "recM"}, headers=H).get_json()["awaiting"] == "amount"
    assert c.post("/api/fcc/write", json={"text": "2000", "scope": "loans"}, headers=H).get_json()["awaiting"] == "destination"
    assert c.post("/api/fcc/write", json={"text": "חיסכון", "goal_id": "savings", "scope": "loans"}, headers=H).get_json()["state"] == "review"
    assert sent == []
    done = c.post("/api/fcc/write", json={"text": "אשר", "scope": "loans"}, headers=H).get_json()
    assert done["state"] == "executed" and [w["table"] for w in sent] == [Tables.LOANS, Tables.FIN_EVENTS]
    assert Tables.LOANS in approval_actions._TMA_WRITE_ALLOWED_TABLES


def test_the_direction_field_name_is_the_one_the_live_table_will_have():
    assert LF.DIRECTION == "Direction" and fd.DIRECTION_TO_ME == "חייבים לי" == fcc_loans.DIRECTION_TO_ME_STORED


# ═══ Goal update: which field (buttons), then its value — the user typed free text and got "לא הבנתי את העריכה" ═══
def test_goal_update_asks_which_field_by_buttons_then_the_value_then_reviews(no_model):
    seed_intents()
    r = intent("monthly.goal_update", "recGK")
    assert r.state == "ask" and r.awaiting == "field" and "קרן חירום" in r.message
    assert [c["goal_id"] for c in r.candidates][:2] == ["target_amount", "title"]
    r = _say("סכום יעד", goal_id="target_amount")
    assert r.state == "ask" and r.awaiting == "target_amount" and "₪60,000" in r.message            # today's value is shown
    r = _say("90,000")
    assert r.state == "review" and "₪90,000" in r.message
    writes = _confirm_one()
    assert [w["fields"].get("Kind") for w in writes] == ["target_change"] and writes[0]["fields"]["Amount"] == 90000


def test_goal_update_value_step_rejects_a_non_value_and_asks_the_same_field_again(no_model):
    seed_intents()
    intent("monthly.goal_update", "recGK")
    _say("סכום יעד", goal_id="target_amount")
    r = _say("הרבה יותר")
    assert r.state == "ask" and r.awaiting == "target_amount" and "❌" in r.message
    r = _say("-5")
    assert r.awaiting == "target_amount"
    assert _say("70000").state == "review"


def test_goal_update_accepts_what_the_owner_naturally_types_without_the_field_question(no_model):
    for typed in ("סכום יעד 80000", "סכום 80000", "80000", "80,000"):
        DB.clear(); seed_intents()
        conv.complete_execution(ELIYAHU)
        r = intent("monthly.goal_update", "recGK")
        r = _say(typed)
        assert r.state == "review" and "₪80,000" in r.message, typed
        _say("בטל")


def test_goal_update_edit_after_review_offers_the_fields_again_and_other_fields_work_by_buttons(no_model):
    seed_intents()
    intent("monthly.goal_update", "recGK")
    _say("80000")
    r = _say("ערוך")
    assert r.awaiting == "field" and r.candidates
    r = _say("קטגוריה", goal_id="category")
    assert r.awaiting == "category" and [c["title"] for c in r.candidates]                      # a closed list is answered by buttons
    r = _say("חוב")
    assert r.state == "review" and "₪80,000" in r.message and "חוב" in r.message
    assert _say("בחרו משהו", goal_id="nope").state == "unrelated"                             # in review, text that is not an edit changes nothing


def test_goal_update_field_step_ignores_command_words_and_unknown_buttons(no_model):
    seed_intents()
    intent("monthly.goal_update", "recGK")
    for word in ("אשר", "ערוך", "לא יודע"):
        r = _say(word)
        assert r.state == "ask" and r.awaiting == "field" and "בחרו מה לעדכן" in r.message, word
    assert _say("בטל").state == "cancelled"


# ═══ Debts balance (owed to me vs owed by me) and the personal equity ═══
def seed_balance(receivable=1_000_000, mine=700_000, linked=400_000):
    DB[Tables.FIN_GOALS], DB[Tables.FIN_EVENTS] = [], []
    DB[Tables.LOANS] = [
        loan("recR", **{LF.NAME: "חייב א", LF.EARLY_CLOSURE: receivable, LF.DIRECTION: "חייבים לי "}),     # the live choice name carries a trailing space
        loan("recM", **{LF.NAME: "שלי", LF.EARLY_CLOSURE: mine}),
        loan("recK", **{LF.NAME: "מקושרת", LF.EARLY_CLOSURE: linked, LF.RELATED_ASSET: ["recAH"]}),
        loan("recU", **{LF.NAME: "בלי יתרה"}),
        loan("recC", **{LF.NAME: "נסגרה", LF.EARLY_CLOSURE: 5000, LF.STATUS: "Paid Off"}),
        loan("recX", owner=AVI, **{LF.NAME: "של אבי", LF.EARLY_CLOSURE: 123456789}),
    ]
    DB["Assets"] = [asset("recAH", "בית שמש", **{AF.STATUS: {"name": "פעיל"}, AF.VALUE: 2_000_000, AF.MORTGAGE: 500_000, AF.OWNERSHIP_PCT: 50}),
                    asset("recAL", "קרקע", **{AF.STATUS: {"name": "פעיל"}, AF.VALUE: 1_000_000, AF.MORTGAGE: 0, AF.OWNERSHIP_PCT: 100, AF.MY_EQUITY: 900_000}),
                    asset("recAU", "בלי נתונים", **{AF.STATUS: {"name": "פעיל"}}),
                    asset("recAX", "של אבי", owner=AVI, **{AF.VALUE: 99_999_999})]


def test_positive_net_is_a_financial_asset_negative_net_is_not_and_linked_loans_are_not_counted_twice():
    seed_balance()
    b = _loans_view()["balance"]
    assert b["receivables_total"] == 1_000_000 and b["liabilities_total"] == 700_000      # the asset-linked 400,000 and the closed 5,000 are left out
    assert b["net"] == 300_000 and b["financial_asset"] == 300_000 and b["net_debt"] == 0
    assert b["linked_excluded_count"] == 1 and b["linked_excluded_total"] == 400_000
    assert b["missing_liabilities"] == 1 and b["missing_receivables"] == 0                # "בלי יתרה" is reported, never turned into 0
    assert "123456789" not in str(_loans_view())
    seed_balance(receivable=200_000)
    b = _loans_view()["balance"]
    assert b["net"] == -500_000 and b["financial_asset"] == 0 and b["net_debt"] == -500_000


def test_balance_is_unknown_without_any_known_balance_and_receivables_alone_make_an_asset():
    DB[Tables.LOANS] = [loan("recU", **{LF.NAME: "בלי יתרה"})]
    b = _loans_view()["balance"]
    assert b["net"] is None and b["financial_asset"] is None and b["missing_liabilities"] == 1
    DB[Tables.LOANS] = [loan("recR", **{LF.EARLY_CLOSURE: 40_000, LF.DIRECTION: "חייבים לי"})]
    assert _loans_view()["balance"]["financial_asset"] == 40_000


def test_personal_equity_adds_the_owners_share_of_assets_and_the_net_debt_position():
    seed_balance()
    pe = service.assets_overview(ELIYAHU, _loans_view()["items"])["summary"]["personal_equity"]
    # (2,000,000 − 500,000) × 50% = 750,000 (computed: Airtable's formula is empty) + 900,000 (stored) ; + net 300,000
    assert pe["assets_my_equity"] == 1_650_000 and pe["assets_known"] == 2 and pe["assets_count"] == 3
    assert pe["financial_asset"] == 300_000 and pe["net_debt"] == 0 and pe["total"] == 1_950_000 and pe["partial"] is True
    seed_balance(receivable=200_000)
    pe = service.assets_overview(ELIYAHU, _loans_view()["items"])["summary"]["personal_equity"]
    assert pe["financial_asset"] == 0 and pe["net_debt"] == -500_000 and pe["total"] == 1_150_000      # not an asset, still reduces the equity
    assert "99999999" not in str(pe)


def test_personal_equity_never_invents_an_ownership_or_a_mortgage_and_asset_linked_debt_stays_separate():
    seed_balance()
    DB["Assets"] = [asset("recAH", "בית", **{AF.STATUS: {"name": "פעיל"}, AF.VALUE: 2_000_000, AF.MORTGAGE: 500_000}),         # no ownership %
                    asset("recAL", "קרקע", **{AF.STATUS: {"name": "פעיל"}, AF.VALUE: 1_000_000, AF.OWNERSHIP_PCT: 100})]         # no mortgage
    a = service.assets_overview(ELIYAHU, _loans_view()["items"])
    assert a["summary"]["personal_equity"]["assets_my_equity"] is None and a["summary"]["personal_equity"]["total"] == 300_000
    assert a["summary"]["personal_equity"]["partial"] is True
    assert a["summary"]["linked_loans_count"] == 1 and a["summary"]["linked_loans_debt"] == 400_000     # the asset-linked debt view is unchanged


# ═══ A new income SOURCE inside the total income goal ("מקורות הכנסה קבועים": אבי, תיווכים…) ═══
def test_new_income_source_is_built_from_a_chip_and_linked_under_the_total_goal(no_model):
    hierarchy([])
    r = intent("monthly.source_new")
    assert r.state == "ask" and r.awaiting == "title" and "אבי, תיווכים" in r.message
    r = _say("אבי")
    assert r.awaiting == "target_amount" and "אבי" in r.message
    r = _say("2,000")
    assert r.awaiting == "period_type" and [c["title"] for c in r.candidates] == ["חודשי", "שבועי"]
    r = _say("חודשי")
    assert r.state == "review" and "מקור הכנסה חדש" in r.message and "הכנסה חודשית כוללת" in r.message and "₪2,000" in r.message
    (w,) = _confirm_one()
    f = w["fields"]
    assert w["op"] == "post" and w["table"] == Tables.FIN_GOALS
    assert f[GF.TITLE] == "אבי" and f[GF.TARGET_AMOUNT] == 2000 and f[GF.CATEGORY] == "income" and f[GF.PERIOD_TYPE] == "monthly"
    assert f[GF.CALC_METHOD] == "period_sum" and f[GF.STATUS] == "active" and f[GF.PARENT_GOAL] == ["recP"]


def test_a_new_source_is_counted_inside_the_parent_never_on_top_of_it(no_model):
    hierarchy([])
    DB[Tables.FIN_GOALS].append(goal("recAvi", "אבי", ELI, 2000, **{GF.CATEGORY: "income", GF.PARENT_GOAL: ["recP"]}))
    DB[Tables.FIN_EVENTS] = [event("recE", "recAvi", ELI, 700, day="2026-10-05")]
    view = service.overview(ELIYAHU, TODAY)
    assert view["summary"]["income"]["target"] == 15000 and rows_of(view)["recP"]["actual"] == 700       # rolled up once, target not inflated


def test_a_source_needs_exactly_one_total_income_goal_and_never_duplicates_a_name(no_model):
    DB[Tables.FIN_GOALS] = [goal("recA", "הכנסה א", ELI, 100, **{GF.CATEGORY: "income"}), goal("recB", "הכנסה ב", ELI, 200, **{GF.CATEGORY: "income"})]
    assert intent("monthly.source_new").state == "clarify"                                   # two roots: ambiguous, nothing is guessed
    DB[Tables.FIN_GOALS] = []
    assert intent("monthly.source_new").state == "clarify"
    hierarchy([])
    intent("monthly.source_new"); _say("הכנסה מנסיעות"); _say("100"); _say("שבועי")
    assert conv.handle_turn(ELIYAHU, "אשר", extractor=conv.DeterministicExtractor(), today=TODAY).state == "duplicate"


def test_a_source_cannot_hang_under_another_persons_goal():
    hierarchy([])
    DB[Tables.FIN_GOALS].append(goal("recAv", "של אבי", AVI, 1000, **{GF.CATEGORY: "income"}))
    own = {GF.TITLE: "x", GF.PARENT_GOAL: ["recP"]}
    assert policy.scope_new_record_fields(Tables.FIN_GOALS, own, ELIYAHU)[GF.FINANCIAL_OWNER] == [ELI]
    with pytest.raises(policy.PersonalDataAccessDenied):
        policy.scope_new_record_fields(Tables.FIN_GOALS, {GF.TITLE: "x", GF.PARENT_GOAL: ["recAv"]}, ELIYAHU)
    _f, denied = approval_actions._enforce_personal_data_policy("post", Tables.FIN_GOALS, "", {GF.TITLE: "x", GF.PARENT_GOAL: ["recAv"]}, ELIYAHU)
    assert denied is not None and denied["ok"] is False


def test_source_intent_is_registered_and_is_not_a_transition():
    assert fd.INTENTS["monthly.source_new"]["entity"] == "fcc_source_new" and "target_required" not in fd.INTENTS["monthly.source_new"]


# ═══ Monthly auto-step: the loan balance follows its own schedule; the owner only corrects now and then ═══
def _auto_loan(**f):
    base = {LF.NAME: "מקס", LF.EARLY_CLOSURE: 3060.71, LF.INTEREST_RATE: 12.85, LF.MONTHLY_PAYMENT: 784.24, LF.PAYMENTS_LEFT: 4,
            LF.DUE_DAY: 15, LF.NEXT_PAYMENT: "2026-10-15"}
    base.update(f)
    return loan("recAuto", **{k: v for k, v in base.items() if v is not None})


def test_nothing_happens_before_the_due_date_and_one_instalment_is_applied_on_it():
    assert fcc_loans.auto_step(_auto_loan(), date(2026, 10, 14)) is None
    s = fcc_loans.auto_step(_auto_loan(), date(2026, 10, 16))
    assert s["action"] == "step" and s["steps"] == 1
    f = s["fields"]
    assert f[LF.EARLY_CLOSURE] == 2309.25            # 3060.71 × (1 + 12.85%/12) − 784.24
    assert f[LF.PAYMENTS_LEFT] == 3 and f[LF.NEXT_PAYMENT] == "2026-11-15"
    assert "עדכון אוטומטי (2026-10-16): 1 תשלומים — יתרה ₪3,060.71 ← ₪2,309.25" in f[LF.NOTES]


def test_a_missed_stretch_is_caught_up_instalment_by_instalment_and_the_old_notes_are_kept():
    s = fcc_loans.auto_step(_auto_loan(**{LF.NEXT_PAYMENT: "2026-08-15", LF.NOTES: "לכל מטרה"}), date(2026, 10, 16))
    assert s["steps"] == 3 and s["fields"][LF.NEXT_PAYMENT] == "2026-11-15" and s["fields"][LF.PAYMENTS_LEFT] == 1
    assert s["fields"][LF.NOTES].startswith("לכל מטרה\nעדכון אוטומטי")


def test_the_last_instalment_zeroes_the_balance_never_closes_the_loan_and_then_the_loan_is_left_alone():
    rec = _auto_loan(**{LF.PAYMENTS_LEFT: 1, LF.EARLY_CLOSURE: 780})
    s = fcc_loans.auto_step(rec, date(2026, 10, 16))
    assert s["fields"][LF.EARLY_CLOSURE] == 0 and s["fields"][LF.PAYMENTS_LEFT] == 0 and LF.STATUS not in s["fields"]
    rec["fields"].update(s["fields"])
    assert fcc_loans.auto_step(rec, date(2026, 12, 1)) is None                  # finished: nothing more is written
    assert fcc_loans.loan_item(rec, date(2026, 12, 1))["payments_done"] is True


def test_the_first_run_only_learns_the_next_due_date_and_a_second_run_the_same_day_writes_nothing():
    rec = _auto_loan(**{LF.NEXT_PAYMENT: None, LF.DUE_DAY: 27})
    s = fcc_loans.auto_step(rec, date(2026, 10, 8))
    assert s["action"] == "init" and s["fields"] == {LF.NEXT_PAYMENT: "2026-10-27"}      # the stored balance is as of today: no instalment now
    assert fcc_loans.auto_step(_auto_loan(**{LF.NEXT_PAYMENT: None, LF.DUE_DAY: 5}), date(2026, 10, 8))["fields"] == {LF.NEXT_PAYMENT: "2026-11-05"}
    assert fcc_loans.auto_step(_auto_loan(**{LF.NEXT_PAYMENT: None, LF.DUE_DAY: 8}), date(2026, 10, 8))["fields"] == {LF.NEXT_PAYMENT: "2026-10-08"}
    rec["fields"].update(s["fields"])
    assert fcc_loans.auto_step(rec, date(2026, 10, 8)) is None


def test_inputs_that_would_make_a_wrong_number_are_skipped_with_a_reason_and_other_loans_are_not_stepped():
    day = date(2026, 10, 16)
    assert fcc_loans.auto_step(_auto_loan(**{LF.INTEREST_RATE: None}), day)["reason"] == "missing_input"
    assert fcc_loans.auto_step(_auto_loan(**{LF.MONTHLY_PAYMENT: 10}), day)["reason"] == "payment_below_interest"   # would grow the balance
    assert fcc_loans.auto_step(_auto_loan(**{LF.NEXT_PAYMENT: None, LF.DUE_DAY: None}), day)["reason"] == "no_due_day"
    assert fcc_loans.auto_step(_auto_loan(**{LF.DIRECTION: "חייבים לי"}), day) is None                                # a debt owed TO the owner
    assert fcc_loans.auto_step(_auto_loan(**{LF.STATUS: "Paid Off"}), day) is None


def test_a_31st_due_day_clamps_to_the_month_end_and_the_schedule_reproduces_a_real_loan():
    s = fcc_loans.auto_step(_auto_loan(**{LF.NEXT_PAYMENT: "2027-01-31", LF.DUE_DAY: 31}), date(2027, 2, 1))
    assert s["fields"][LF.NEXT_PAYMENT] == "2027-02-28"
    rate, pay, n = 12.05, 1182.65, 63                                   # a live loan: its balance equals the present value of its payments
    i = rate / 100 / 12
    pv = round(pay * (1 - (1 + i) ** -n) / i, 2)
    assert abs(pv - 55342.78) < 400                                     # the stored balance matches the formula's own schedule (±0.7%)
    rec = _auto_loan(**{LF.EARLY_CLOSURE: pv, LF.INTEREST_RATE: rate, LF.MONTHLY_PAYMENT: pay, LF.PAYMENTS_LEFT: n, LF.NEXT_PAYMENT: "2026-11-10", LF.DUE_DAY: 10})
    day = date(2026, 11, 10)
    for _ in range(n):
        s = fcc_loans.auto_step(rec, day)
        rec["fields"].update(s["fields"])
        day = date.fromisoformat(s["fields"][LF.NEXT_PAYMENT])
    assert rec["fields"][LF.EARLY_CLOSURE] == 0 and rec["fields"][LF.PAYMENTS_LEFT] == 0


def test_the_job_patches_only_the_owners_loans_through_the_gateway_and_is_idempotent(monkeypatch):
    import scheduler
    seed_debts(with_goal=False)
    DB[Tables.LOANS] = [_auto_loan(**{LF.NEXT_PAYMENT: "2026-10-01"}), loan("recX", owner=AVI, **{LF.NAME: "של אבי", LF.EARLY_CLOSURE: 777, LF.INTEREST_RATE: 5,
                        LF.MONTHLY_PAYMENT: 50, LF.NEXT_PAYMENT: "2026-09-01", LF.DUE_DAY: 1}),
                        loan("recNoRate", **{LF.NAME: "חסר", LF.EARLY_CLOSURE: 1000, LF.NEXT_PAYMENT: "2026-10-01", LF.MONTHLY_PAYMENT: 100})]
    calls = []

    def fake_patch(table, record_id, fields, source="unknown", **kw):
        calls.append((table, record_id, source))
        next(r for r in DB[table] if r["id"] == record_id)["fields"].update(fields)
        return True
    import tools.airtable_gateway as gw
    monkeypatch.setattr(gw, "airtable_patch", fake_patch)
    dry = scheduler.fcc_loan_auto_step_for(ELIYAHU, TODAY, dry_run=True)
    assert calls == [] and [s["id"] for s in dry["stepped"]] == ["recAuto"] and dry["skipped"][0]["reason"] == "missing_input"
    r = scheduler.fcc_loan_auto_step_for(ELIYAHU, TODAY)
    assert calls == [(Tables.LOANS, "recAuto", "fcc_loan_auto")]                 # Avi's overdue loan is never touched
    assert r["stepped"][0]["after"] < r["stepped"][0]["before"] and DB[Tables.LOANS][1]["fields"][LF.EARLY_CLOSURE] == 777
    assert scheduler.fcc_loan_auto_step_for(ELIYAHU, TODAY)["stepped"] == [] and len(calls) == 1      # same day again: nothing due, nothing written


def test_a_failed_write_is_reported_and_retried_on_the_next_run(monkeypatch):
    import scheduler
    seed_debts(with_goal=False)
    DB[Tables.LOANS] = [_auto_loan(**{LF.NEXT_PAYMENT: "2026-10-01"})]
    import tools.airtable_gateway as gw
    monkeypatch.setattr(gw, "airtable_patch", lambda *a, **k: False)
    r = scheduler.fcc_loan_auto_step_for(ELIYAHU, TODAY)
    assert r["stepped"] == [] and r["failed"][0]["id"] == "recAuto"
    assert scheduler.fcc_loan_auto_step_for(ELIYAHU, TODAY)["failed"][0]["id"] == "recAuto"           # nothing moved, so it is due again


def test_the_scheduler_job_is_off_by_default_and_acts_only_for_fcc_owners(monkeypatch):
    import scheduler
    ran = []
    monkeypatch.setattr(scheduler, "fcc_loan_auto_step_for", lambda who, *a, **k: (ran.append(who.user_id) or
                        {"stepped": [], "initialized": [], "skipped": [], "failed": []}))
    monkeypatch.delenv(service.LOAN_AUTO_STEP_FLAG, raising=False)
    assert service.loan_auto_step_enabled() is False
    scheduler._job_fcc_loan_auto_step()
    assert ran == []
    monkeypatch.setenv(service.LOAN_AUTO_STEP_FLAG, "true")
    from core.financial_control import gate
    monkeypatch.setattr(gate, "enabled_for", lambda who: who.user_id == "eliyahu")
    scheduler._job_fcc_loan_auto_step()
    assert ran == ["eliyahu"]                                                       # the partner (avi) is in the registry but not an FCC owner


def test_the_loans_payload_says_whether_balances_follow_their_schedule_and_shows_the_next_due_date(monkeypatch):
    seed_debts()
    DB[Tables.LOANS][0]["fields"].update({LF.NEXT_PAYMENT: "2026-10-10", LF.PAYMENTS_LEFT: 0})
    monkeypatch.delenv(service.LOAN_AUTO_STEP_FLAG, raising=False)
    v = _loans_view()
    assert v["auto_step"] is False
    item = {i["id"]: i for i in v["items"]}["recM"]
    assert item["next_payment_due"] == "2026-10-10" and item["payments_done"] is True
    monkeypatch.setenv(service.LOAN_AUTO_STEP_FLAG, "true")
    assert _loans_view()["auto_step"] is True


def test_correcting_a_balance_after_its_due_date_moves_the_next_due_date_so_the_job_does_not_apply_it_again(no_model):
    seed_debts(with_goal=False)
    DB[Tables.LOANS] = [_auto_loan(**{LF.NEXT_PAYMENT: "2026-10-05", LF.DUE_DAY: 5})]      # due 5/10, today is 8/10
    r = intent("loan.update_balance", "recAuto")
    assert "תאריך החיוב הבא יעודכן" in r.message and "05/11/2026" in r.message
    _say("2500", scope="loans")
    (w,) = _confirm_one()
    assert w["fields"] == {LF.EARLY_CLOSURE: 2500, LF.NEXT_PAYMENT: "2026-11-05"}
    DB[Tables.LOANS][0]["fields"].update(w["fields"])
    assert fcc_loans.auto_step(DB[Tables.LOANS][0], TODAY) is None                         # not due again until 5/11
    conv.complete_execution(ELIYAHU)
    DB[Tables.LOANS] = [_auto_loan()]                                                      # a FUTURE due date: only the balance is written
    intent("loan.update_balance", "recAuto")
    _say("2500", scope="loans")
    (w,) = _confirm_one()
    assert w["fields"] == {LF.EARLY_CLOSURE: 2500}


# ═══ Prime-rate change: one number moves every loan's rate and payment together ═══
def seed_prime():
    DB[Tables.FIN_GOALS], DB[Tables.FIN_EVENTS] = [], []
    DB[Tables.LOANS] = [
        loan("recA", **{LF.NAME: "כאל 60,700", LF.EARLY_CLOSURE: 55000, LF.INTEREST_RATE: 12.05, LF.MONTHLY_PAYMENT: 1182.65, LF.PAYMENTS_LEFT: 63, LF.NOTES: "לכל מטרה"}),
        loan("recB", **{LF.NAME: "מקס", LF.EARLY_CLOSURE: 94549.56, LF.INTEREST_RATE: 6.96, LF.MONTHLY_PAYMENT: 1378.22, LF.PAYMENTS_LEFT: 86}),
        loan("recC", **{LF.NAME: "ללא החזר", LF.EARLY_CLOSURE: 1000, LF.INTEREST_RATE: 8}),                       # rate only: payment cannot be derived
        loan("recD", **{LF.NAME: "ללא ריבית", LF.EARLY_CLOSURE: 1000, LF.MONTHLY_PAYMENT: 100, LF.PAYMENTS_LEFT: 10}),   # no rate: not touched
        loan("recR", **{LF.NAME: "חייב לי", LF.EARLY_CLOSURE: 5000, LF.INTEREST_RATE: 5, LF.DIRECTION: "חייבים לי"}),
        loan("recP", **{LF.NAME: "נפרעה", LF.EARLY_CLOSURE: 0, LF.INTEREST_RATE: 5, LF.STATUS: "Paid Off"}),
        loan("recX", owner=AVI, **{LF.NAME: "של אבי", LF.EARLY_CLOSURE: 777, LF.INTEREST_RATE: 5, LF.MONTHLY_PAYMENT: 50, LF.PAYMENTS_LEFT: 20}),
    ]


def test_prime_plan_scales_the_banks_own_payment_over_the_remaining_term():
    seed_prime()
    rows = fcc_loans.prime_rows(service.my_loans(ELIYAHU), TODAY)             # the owner's own rows only (another owner's never arrive)
    assert [r["id"] for r in rows] == ["recA", "recB", "recC"]            # not: no rate, owed TO the owner, closed
    up = {p["id"]: p for p in fcc_loans.prime_plan(rows, 0.25)}
    down = {p["id"]: p for p in fcc_loans.prime_plan(rows, -0.5)}
    assert up["recA"]["new_rate"] == 12.3 and up["recA"]["new_payment"] > 1182.65 and down["recA"]["new_payment"] < 1182.65
    assert abs(up["recA"]["new_payment"] - 1182.65) < 12                  # a quarter point over 63 months moves the payment by a few shekels
    assert up["recC"]["new_payment"] is None and up["recC"]["new_rate"] == 8.25      # no payment on file: only the rate follows
    assert fcc_loans.prime_plan(rows, -9)[2]["skip"] == "negative_rate"
    assert fcc_loans.prime_plan(rows, 0.0)[0]["new_payment"] == 1182.65            # no change keeps the bank's number exactly


def test_prime_change_flow_asks_one_number_reviews_every_loan_and_patches_each(no_model):
    seed_prime()
    r = intent("loan.prime_change")
    assert r.state == "ask" and r.awaiting == "delta" and "3 הלוואות" in r.message and "פריים" in r.message
    r = _say("+0.25", scope="loans")
    assert r.state == "review" and "שינוי ריבית: +0.25%" in r.message
    assert "כאל 60,700: ריבית 12.05% ← 12.3%" in r.message and "מקס: ריבית 6.96% ← 7.21%" in r.message and "ההחזר לא מחושב" in r.message
    assert "ללא ריבית" not in r.message and "חייב לי" not in r.message and "אבי" not in r.message
    writes = _confirm_one()
    assert [w["record_id"] for w in writes] == ["recA", "recB", "recC"] and all(w["op"] == "patch" and w["table"] == Tables.LOANS for w in writes)
    a = writes[0]["fields"]
    assert a[LF.INTEREST_RATE] == 12.3 and a[LF.MONTHLY_PAYMENT] > 1182.65 and a[LF.NOTES].startswith("לכל מטרה\nשינוי פריים (2026-10-08) +0.25%: ריבית 12.05% ← 12.3%")
    assert set(writes[2]["fields"]) == {LF.INTEREST_RATE, LF.NOTES}               # the loan without a payment: rate + history only
    assert LF.EARLY_CLOSURE not in a and LF.STATUS not in a and LF.NEXT_PAYMENT not in a


def test_prime_change_accepts_signs_and_decimals_rejects_zero_typos_and_words(no_model):
    seed_prime()
    intent("loan.prime_change")
    for bad in ("0", "7", "-6", "הרבה", ""):
        r = _say(bad, scope="loans") if bad else None
        if r is not None:
            assert r.awaiting == "delta" and r.state in ("ask", "unrelated"), bad
    assert _say("-0.5", scope="loans").state == "review"
    conv.handle_turn(ELIYAHU, "בטל", extractor=conv.DeterministicExtractor(), today=TODAY)
    intent("loan.prime_change")
    assert _say("−0.25", scope="loans").state == "review"                         # a typographic minus works as a minus


def test_prime_change_is_idempotent_owner_scoped_and_needs_loans_with_a_rate(no_model):
    seed_prime()
    intent("loan.prime_change"); _say("0.25", scope="loans")
    writes = _confirm_one()
    for w in writes:
        next(r for r in DB[Tables.LOANS] if r["id"] == w["record_id"])["fields"].update(w["fields"])
    assert all(conv._already_applied(ELIYAHU, w) for w in writes)                   # a retry after success writes nothing
    assert all(w["record_id"] != "recX" for w in writes)
    conv.complete_execution(ELIYAHU)
    DB[Tables.LOANS] = [loan("recD", **{LF.NAME: "ללא ריבית", LF.EARLY_CLOSURE: 1000})]
    assert intent("loan.prime_change").state == "clarify"


def test_http_prime_change_executes_one_frozen_patch_per_loan(monkeypatch, no_model):
    seed_prime()
    sent = []
    monkeypatch.setattr(tma_api, "_queue_or_owner_execute",
                        lambda action, payload, identity, label: (sent.append(payload) or ("a", {"ok": True}, 200)))
    c = http(monkeypatch, ELIYAHU)
    assert c.post("/api/fcc/intent/start", json={"intent": "loan.prime_change"}, headers=H).get_json()["awaiting"] == "delta"
    assert c.post("/api/fcc/write", json={"text": "+0.25", "scope": "loans"}, headers=H).get_json()["state"] == "review"
    assert sent == []
    done = c.post("/api/fcc/write", json={"text": "אשר", "scope": "loans"}, headers=H).get_json()
    assert done["state"] == "executed" and [w["record_id"] for w in sent] == ["recA", "recB", "recC"]


def test_prime_intent_is_registered_and_is_not_a_transition():
    assert fd.INTENTS["loan.prime_change"]["entity"] == "fcc_prime_change" and "target_required" not in fd.INTENTS["loan.prime_change"]
    assert not fd.INTENTS["loan.prime_change"].get("transition")


# ── Action goals (no amount) move by actions / status; the old single "Next Step" becomes a real open action ───────
def seed_action_goals():
    DB[Tables.FIN_GOALS], DB[Tables.FIN_EVENTS], DB[Tables.TASKS] = [
        goal("recY", "מכירת יבנאל", ELI, None, **{GF.CATEGORY: "other"}),
        goal("recM", "הכנסה חודשית", ELI, 15000, **{GF.CATEGORY: "income"}),
        goal("recYX", "יעד של אבי", AVI, None, **{GF.CATEGORY: "other"}),
    ], [], []


def test_action_goal_amount_update_is_refused_and_numeric_goal_still_updates(no_model):
    seed_action_goals()
    r = intent("monthly.goal_update", "recY")
    assert r.state == "clarify" and "יעד של פעולה" in r.message
    assert intent("monthly.goal_update", "recM").state == "ask"


def test_action_goal_done_and_pause_are_a_status_patch_only(no_model):
    seed_action_goals()
    r = intent("monthly.goal_done", "recY")
    assert r.state == "review" and "הושלם" in r.message and "מכירת יבנאל" in r.message
    (w,) = _confirm_one()
    assert w["op"] == "patch" and w["table"] == Tables.FIN_GOALS and w["record_id"] == "recY" and w["fields"] == {GF.STATUS: "done"}
    conv.complete_execution(ELIYAHU)
    intent("monthly.goal_pause", "recY")
    (w,) = _confirm_one()
    assert w["fields"] == {GF.STATUS: "paused"}


def test_action_goal_next_action_creates_a_goal_tagged_followup_task(no_model):
    seed_action_goals()
    r = intent("monthly.goal_followup", "recY")
    assert r.state == "ask" and r.awaiting == "title" and "מכירת יבנאל" in r.message
    assert _say("לתאם עורך דין", scope="monthly").state == "review"
    (w,) = _confirm_one()
    assert w["op"] == "post" and w["table"] == Tables.TASKS and w["fields"][TaskFields.NAME] == "לתאם עורך דין"
    assert "[FCC:recY]" in w["fields"][TaskFields.DESCRIPTION]


def test_action_goal_intents_are_owner_scoped(no_model):
    seed_action_goals()
    for iid in ("monthly.goal_done", "monthly.goal_pause", "monthly.goal_followup"):
        assert intent(iid, "recYX").state == "denied"
        assert intent(iid).state == "clarify"


def seed_legacy_step():
    DB["Assets"] = [asset("recAH", "קרית ספר", **{AF.STATUS: {"name": "פעיל"}, AF.VALUE: 1000000, AF.NEXT_STEP: "לבדוק מימוש", AF.NEXT_STEP_OWNER: {"name": "אהרן"}}),
                    asset("recAN", "ללא פעולה ישנה", **{AF.STATUS: {"name": "פעיל"}, AF.VALUE: 5})]
    DB[Tables.TASKS], DB[Tables.LOANS] = [], []


def test_legacy_next_step_is_adopted_as_an_open_action_and_the_old_field_is_emptied(no_model):
    seed_legacy_step()
    r = intent("asset.adopt_step", "recAH")
    assert r.state == "review" and "לבדוק מימוש" in r.message and "אהרן" in r.message
    post, clear = _confirm_one()
    assert post["op"] == "post" and post["table"] == Tables.TASKS and post["fields"][TaskFields.NAME] == "לבדוק מימוש"
    assert "[FCC-ASSET:recAH]" in post["fields"][TaskFields.DESCRIPTION] and "אחראי: אהרן" in post["fields"][TaskFields.DESCRIPTION]
    assert clear["op"] == "patch" and clear["table"] == "Assets" and clear["record_id"] == "recAH" and clear["fields"] == {AF.NEXT_STEP: ""}
    DB["Assets"][0]["fields"][AF.NEXT_STEP] = ""                                     # applied: a retry writes nothing
    assert conv._already_applied(ELIYAHU, clear)


def test_adopting_needs_a_legacy_step_and_an_owned_asset(no_model):
    seed_legacy_step()
    assert intent("asset.adopt_step", "recAN").state == "info"
    assert intent("asset.adopt_step", "recZZ").state == "denied"
    assert intent("asset.adopt_step").state == "clarify"


# ── The fixed weekly quota: target / days-in-month × 7, per-day month rates; a shortfall carries, a surplus is HELD for the month end ──
def _live(*pairs):
    return [calc.Event(k, a, date.fromisoformat(d), False, None) for d, a, k in pairs]


def test_weekly_quota_uses_each_days_own_month_rate_and_a_shortfall_carries_forward():
    w = calc.weekly_quota(15000, [], date(2026, 10, 14))
    assert w["week_start"] == "2026-10-11" and w["week_end"] == "2026-10-17" and w["quota"] == round(15000 / 31 * 7, 2)    # 3,387.10
    assert [h["week_start"] for h in w["history"]] == ["2026-10-04"]                      # Oct 1-3 belong to September's last week
    assert w["carry_in"] == round(15000 / 31 * 7, 2) and w["required"] == round(2 * 15000 / 31 * 7, 2)    # last week's shortfall is still owed
    assert w["remaining"] == w["required"] and w["surplus"] == 0.0 and w["held_total"] == 0.0
    w = calc.weekly_quota(14000, [], date(2026, 10, 28))                                  # 25/10 - 31/10 stays in October
    assert w["quota"] == round(14000 / 31 * 7, 2)
    w = calc.weekly_quota(15000, [], date(2026, 11, 29))                                  # 29/11 - 5/12: 2 days of November (30d) + 5 days of December (31d)
    assert w["week_start"] == "2026-11-29" and w["quota"] == round(15000 / 30 * 2 + 15000 / 31 * 5, 2)


def test_weekly_quota_a_surplus_is_held_not_netted_against_the_next_week():
    live = _live(("2026-10-05", 3000, "one_time"), ("2026-10-06", 1000, "one_time"))
    w = calc.weekly_quota(18000, live, date(2026, 10, 12))
    short = round(18000 / 31 * 7 - 4000, 2)
    assert w["carry_in"] == short and abs(w["required"] - (18000 / 31 * 7 + short)) < 0.02   # 4,000 < the quota: the shortfall is still owed
    assert w["history"][0]["surplus"] == 0.0 and w["held_total"] == 0.0                   # ... and there is nothing to hold
    rich = _live(("2026-10-05", 9000, "one_time"))
    w = calc.weekly_quota(18000, rich, date(2026, 10, 12))
    assert w["history"][0]["surplus"] == w["history"][0]["held"] == round(9000 - 18000 / 31 * 7, 2) and w["held_total"] == w["history"][0]["held"]
    assert w["carry_in"] == 0.0 and w["required"] == round(18000 / 31 * 7, 2)             # next week still needs its full quota
    cur = calc.weekly_quota(18000, rich + _live(("2026-10-12", 6000, "one_time"), ("2026-10-13", 500, "direct_cost")), date(2026, 10, 14))
    assert cur["actual"] == 5500 and cur["surplus"] == round(5500 - 18000 / 31 * 7, 2) and cur["held_total"] == round(w["held_total"] + cur["surplus"], 2)
    assert calc.weekly_quota(None, [], date(2026, 10, 14)) is None and calc.weekly_quota(0, [], date(2026, 10, 14)) is None


def test_weekly_quota_decisions_move_use_or_save_a_surplus_and_hold_changes_nothing():
    quota = 18000 / 31 * 7
    base = _live(("2026-10-05", 9000, "one_time"))
    note = lambda decision, amount, week="2026-10-04": calc.Event("note", amount, date(2026, 10, 9), False, None, calc.week_surplus_note(week, decision))
    surplus = round(9000 - quota, 2)
    assert calc.weekly_quota(18000, base + [note("hold", surplus)], date(2026, 10, 12))["held_total"] == surplus
    carried = calc.weekly_quota(18000, base + [note("carry", 1000)], date(2026, 10, 12))
    assert carried["carry_in"] == -1000 and carried["required"] == round(quota - 1000, 2) and carried["held_total"] == round(surplus - 1000, 2)
    assert calc.weekly_quota(18000, base + [note("carry", 0)], date(2026, 10, 12))["carry_in"] == -surplus        # an old marker: the whole surplus moved
    for word in ("use", "save"):
        w = calc.weekly_quota(18000, base + [note(word, 2000)], date(2026, 10, 12))
        assert w["carry_in"] == 0.0 and w["held_total"] == round(surplus - 2000, 2)
    assert calc.weekly_quota(18000, base + [note("use", 99999)], date(2026, 10, 12))["held_total"] == 0.0           # never more than the surplus


# ── The last income entries, so nothing is booked twice ───────────────────────────────────────────────────────────
def test_recent_incomes_lists_own_income_entries_newest_first_with_source_and_flags_duplicates():
    DB[Tables.FIN_GOALS] = [goal("recInc", "הכנסה חודשית", ELI, 18000, **{GF.CATEGORY: "income"}),
                            goal("recSrc", "נסיעות", ELI, 2500, **{GF.CATEGORY: "income", GF.PERIOD_TYPE: "weekly"}),
                            goal("recPen", "תכנון פנסיוני", ELI, None, **{GF.CATEGORY: "long_term"}),
                            goal("recAvi", "הכנסה של אבי", AVI, 9000, **{GF.CATEGORY: "income"})]
    DB[Tables.FIN_EVENTS] = [
        event("e1", "recInc", ELI, 1500, day="2026-10-05"),
        event("e2", "recSrc", ELI, 700, day="2026-10-07", **{EF.NOTE: "אבי"}),
        event("e3", "recSrc", ELI, 700, day="2026-10-07", **{EF.NOTE: "אבי"}),
        event("e4", "recInc", ELI, 80, kind="direct_cost", day="2026-10-06"),
        event("e5", "recPen", ELI, 900, day="2026-10-06"),                      # a savings deposit: not an income entry
        event("e6", "recInc", ELI, 5, kind="note", day="2026-10-06"),            # a marker note: not an income entry
        event("e7", "recAvi", AVI, 4000, day="2026-10-06"),                      # another owner's
        event("e8", "recInc", ELI, 300, day="2026-10-04", **{EF.SUPERSEDED_BY: ["e1"]}),
    ]
    rows = service.overview(ELIYAHU, TODAY)["recent_incomes"]
    assert [r["id"] for r in rows] == ["e3", "e2", "e4", "e1"]
    assert rows[0]["source"] == "נסיעות" and rows[0]["note"] == "אבי" and rows[0]["amount"] == 700
    assert rows[0]["possible_duplicate"] and rows[1]["possible_duplicate"] and not rows[2]["possible_duplicate"] and rows[2]["kind"] == "direct_cost"
    assert "הכנסה של אבי" not in str(rows) and all(r["id"] != "e7" for r in rows)
    assert len(service.recent_incomes(DB[Tables.FIN_GOALS], DB[Tables.FIN_EVENTS] * 5, limit=3)) == 3


# ── The weekly-surplus question: hold for the month end (default) / carry / use / save, and the month-end decision ──
FRI = date(2026, 10, 16)
SAT_LAST = date(2026, 10, 31)


def seed_week_surplus(with_savings=True):
    DB[Tables.FIN_GOALS] = [goal("recInc", "הכנסה חודשית", ELI, 18000, **{GF.CATEGORY: "income"})]
    if with_savings:
        DB[Tables.FIN_GOALS].append(goal("recPen", "תכנון פנסיוני", ELI, None, **{GF.CATEGORY: "long_term"}))
        DB[Tables.FIN_GOALS][1]["fields"].pop(GF.TARGET_AMOUNT)
    DB[Tables.FIN_EVENTS] = [event("recE1", "recInc", ELI, 9000, day="2026-10-05"), event("recE2", "recInc", ELI, 6000, day="2026-10-12")]
    DB[Tables.TASKS] = []


def _wk(today):
    return service.overview(ELIYAHU, today)["summary"]["income"]["weekly"]


def _yes(today=FRI):
    return conv.handle_turn(ELIYAHU, "אשר", extractor=conv.DeterministicExtractor(), today=today).snapshot["writes"]


def _book(writes):
    for i, w in enumerate(writes):
        DB[Tables.FIN_EVENTS].append({"id": f"recMk{len(DB[Tables.FIN_EVENTS])}{i}", "fields": {**w["fields"], EF.FINANCIAL_OWNER: [ELI]}})


def test_weekly_surplus_is_asked_when_the_week_closes_and_for_the_last_closed_week_until_answered():
    seed_week_surplus()
    quota = round(18000 / 31 * 7, 2)
    fri = _wk(FRI)
    assert fri["closing"]["kind"] == "week" and fri["closing"]["week_start"] == "2026-10-11" and fri["closing"]["goal_id"] == "recInc"
    assert fri["closing"]["amount"] == fri["surplus"] == round(6000 - quota, 2)
    assert fri["held_total"] == round(9000 - quota + 6000 - quota, 2) and fri["carry_in"] == 0.0                 # the picture mid-month; no netting
    wed = _wk(date(2026, 10, 14))                                                                              # mid-week: the PREVIOUS week is the open question
    assert wed["closing"]["week_start"] == "2026-10-04" and wed["closing"]["amount"] == round(9000 - quota, 2)
    DB[Tables.FIN_EVENTS] = [DB[Tables.FIN_EVENTS][1]]                                                          # no surplus in the closed week -> no question
    assert _wk(date(2026, 10, 14))["closing"] is None


def test_weekly_surplus_hold_is_the_default_and_the_marker_only_stops_the_question(no_model):
    seed_week_surplus()
    quota = round(18000 / 31 * 7, 2)
    before = _wk(FRI)
    r = conv.start_intent(ELIYAHU, "weekly.surplus_hold", None, today=FRI)
    assert r.state == "review" and "נשמרים להחלטה בסוף החודש" in r.message and "לא מקטינים" in r.message
    (w,) = _yes()
    f = w["fields"]
    assert w["table"] == Tables.FIN_EVENTS and f[EF.KIND] == "note" and f[EF.NOTE] == "עודף שבועי 2026-10-11: נשמר" and f[EF.GOAL] == ["recInc"]
    _book([w])
    after = _wk(FRI)
    assert after["closing"] is None and after["held_total"] == before["held_total"] and after["carry_in"] == before["carry_in"]
    assert _wk(date(2026, 10, 18))["required"] == quota                                                          # the next week still needs its full quota


def test_weekly_surplus_carry_lowers_the_next_week_and_use_or_save_leave_the_pot(no_model):
    seed_week_surplus()
    quota = round(18000 / 31 * 7, 2)
    surplus = round(6000 - quota, 2)
    conv.start_intent(ELIYAHU, "weekly.surplus_carry", None, today=FRI)
    (w,) = _yes()
    assert w["fields"][EF.NOTE] == "עודף שבועי 2026-10-11: הועבר" and w["fields"][EF.AMOUNT] == surplus
    _book([w])
    nxt = _wk(date(2026, 10, 18))
    assert nxt["carry_in"] == -surplus and nxt["required"] == round(quota - surplus, 2)
    conv.complete_execution(ELIYAHU)
    seed_week_surplus()
    held_before = _wk(FRI)["held_total"]
    conv.start_intent(ELIYAHU, "weekly.surplus_use", None, today=FRI)
    (w,) = _yes()
    assert w["fields"][EF.NOTE] == "עודף שבועי 2026-10-11: נוצל" and w["fields"][EF.AMOUNT] == surplus
    _book([w])
    assert _wk(FRI)["held_total"] == round(held_before - surplus, 2) and _wk(date(2026, 10, 18))["carry_in"] == 0.0
    conv.complete_execution(ELIYAHU)
    seed_week_surplus()
    r = conv.start_intent(ELIYAHU, "weekly.surplus_save", None, today=FRI)
    assert r.state == "review" and "הפקדה לחיסכון" in r.message
    marker, dep = _yes()
    assert marker["fields"][EF.NOTE] == "עודף שבועי 2026-10-11: נחסך" and marker["fields"][EF.AMOUNT] == surplus
    assert dep["fields"][EF.GOAL] == ["recPen"] and dep["fields"][EF.KIND] == "one_time" and dep["fields"][EF.AMOUNT] == surplus
    assert dep["fields"][EF.NOTE].startswith(fd.SAVINGS_DEPOSIT_NOTE)


def test_month_end_asks_about_the_whole_held_amount_and_only_use_or_save_are_offered(no_model):
    seed_week_surplus()
    quota = round(18000 / 31 * 7, 2)
    held = round(9000 - quota + 6000 - quota, 2)
    closing = _wk(SAT_LAST)["closing"]
    assert closing["kind"] == "month" and closing["month"] == "2026-10" and closing["amount"] == held
    assert _wk(date(2026, 11, 2))["closing"]["kind"] == "month"                                                  # still asked in the first days of the next month
    assert _wk(date(2026, 11, 10))["closing"] is None
    assert conv.start_intent(ELIYAHU, "weekly.surplus_use", None, today=SAT_LAST).state == "info"               # a weekly answer to a month question
    r = conv.start_intent(ELIYAHU, "weekly.month_use", None, today=SAT_LAST)
    assert r.state == "review" and "עודף החודש" in r.message
    (w,) = _yes(SAT_LAST)
    assert w["fields"][EF.NOTE] == "סיכום חודש 2026-10: נוצל" and w["fields"][EF.AMOUNT] == held
    _book([w])
    assert _wk(SAT_LAST)["closing"] is None and _wk(SAT_LAST)["held_total"] == 0.0
    conv.complete_execution(ELIYAHU)
    seed_week_surplus()
    marker, dep = (conv.start_intent(ELIYAHU, "weekly.month_save", None, today=SAT_LAST), _yes(SAT_LAST))[1]
    assert marker["fields"][EF.NOTE] == "סיכום חודש 2026-10: נחסך" and dep["fields"][EF.GOAL] == ["recPen"] and dep["fields"][EF.AMOUNT] == held
    assert conv.start_intent(ELIYAHU, "weekly.month_use", None, today=FRI).state == "info"                      # a month answer to a weekly question


def test_weekly_surplus_amount_can_be_lowered_but_not_raised_and_save_needs_a_savings_goal(no_model):
    seed_week_surplus()
    conv.start_intent(ELIYAHU, "weekly.surplus_use", None, today=FRI)
    r = conv.handle_turn(ELIYAHU, "ערוך", extractor=conv.DeterministicExtractor(), today=FRI, scope="monthly")
    r = conv.handle_turn(ELIYAHU, "סכום 5000", extractor=conv.DeterministicExtractor(), today=FRI, scope="monthly")
    assert "גדול מהעודף" in r.message
    r = conv.handle_turn(ELIYAHU, "סכום 500", extractor=conv.DeterministicExtractor(), today=FRI, scope="monthly")
    assert r.state == "review" and "₪500" in r.message
    (w,) = _yes()
    assert w["fields"][EF.AMOUNT] == 500
    conv.complete_execution(ELIYAHU)
    seed_week_surplus(with_savings=False)
    assert conv.start_intent(ELIYAHU, "weekly.surplus_save", None, today=FRI).state == "clarify"


def test_weekly_surplus_with_nothing_open_and_other_owners_data(no_model):
    seed_week_surplus()
    DB[Tables.FIN_EVENTS] = []
    assert conv.start_intent(ELIYAHU, "weekly.surplus_hold", None, today=FRI).state == "info"
    assert conv.start_intent(AVI_I, "weekly.surplus_use", None, today=FRI).state == "info"                      # nothing of ELIYAHU's leaks to another owner


# ── A loan's interest rate / remaining payments can be corrected on their own ────────────────────────────────────
def seed_rate_loan():
    DB[Tables.FIN_GOALS], DB[Tables.FIN_EVENTS] = [], []
    DB[Tables.LOANS] = [loan("recR", **{LF.NAME: "אקספרס", LF.EARLY_CLOSURE: 2630.72, LF.MONTHLY_PAYMENT: 52.84, LF.AMOUNT: 2800}),
                        loan("recRx", owner=AVI, **{LF.NAME: "של אבי", LF.INTEREST_RATE: 5})]


def test_loan_rate_and_remaining_payments_are_one_field_updates_with_review(no_model):
    seed_rate_loan()
    r = intent("loan.update_rate", "recR")
    assert r.state == "ask" and r.awaiting == "rate" and "אקספרס" in r.message and "לא הוגדר" in r.message          # no rate stored yet
    r = _say("10.65", scope="loans")
    assert r.state == "review" and "10.65%" in r.message and "עדכון ריבית הלוואה" in r.message
    (w,) = _confirm_one()
    assert w["op"] == "patch" and w["table"] == Tables.LOANS and w["record_id"] == "recR" and w["fields"] == {LF.INTEREST_RATE: 10.65}
    DB[Tables.LOANS][0]["fields"].update(w["fields"])
    assert conv._already_applied(ELIYAHU, w)                                                              # a retry writes nothing
    conv.complete_execution(ELIYAHU)
    r = intent("loan.update_rate", "recR")
    assert "היום: 10.65%" in r.message
    conv.handle_turn(ELIYAHU, "בטל", extractor=conv.DeterministicExtractor(), today=TODAY)
    r = intent("loan.update_term", "recR")
    assert r.awaiting == "payments_left" and "כמה תשלומים נותרו" in r.message
    assert _say("66", scope="loans").state == "review"
    (w,) = _confirm_one()
    assert w["fields"] == {LF.PAYMENTS_LEFT: 66}


def test_loan_rate_is_owner_scoped_and_rejects_a_negative_value(no_model):
    seed_rate_loan()
    assert intent("loan.update_rate", "recRx").state == "denied" and intent("loan.update_rate").state == "clarify"
    intent("loan.update_rate", "recR")
    assert _say("-3", scope="loans").awaiting == "rate"


def test_loan_original_amount_is_a_one_field_update_that_must_be_positive(no_model):
    seed_rate_loan()
    r = intent("loan.update_original", "recR")
    assert r.state == "ask" and r.awaiting == "original" and "היום: ₪2,800" in r.message
    assert _say("0", scope="loans").awaiting == "original"
    r = _say("3000", scope="loans")
    assert r.state == "review" and "עדכון סכום מקורי" in r.message
    (w,) = _confirm_one()
    assert w["table"] == Tables.LOANS and w["record_id"] == "recR" and w["fields"] == {LF.AMOUNT: 3000}
    conv.complete_execution(ELIYAHU)
    assert intent("loan.update_original", "recRx").state == "denied"


# ═══ D1 step 7 / B1: read-only accounts tab (/api/fcc/accounts) ═══
from airtable_schema import FinAccountFields as ACF   # noqa: E402


def seed_accounts():
    def acct(aid, owner, name, **extra):
        f = {ACF.NAME: name, ACF.ACCOUNT_TYPE: "study_fund", ACF.STATUS: "active", ACF.FINANCIAL_OWNER: [owner],
             ACF.NOTES: f"הערה פרטית {aid}", ACF.TAX_NOTES: f"מס {aid}"}
        f.update(extra)
        return {"id": aid, "fields": f}

    def mv(eid, kind, amount, day, account, owner=ELI):
        return {"id": eid, "fields": {EF.KIND: kind, EF.AMOUNT: amount, EF.OCCURRED_AT: day, EF.ACCOUNT: [account],
                                      EF.FINANCIAL_OWNER: [owner]}}
    DB[Tables.FIN_ACCOUNTS] = [acct("recAE", ELI, "קרן השתלמות"), acct("recAA", AVI, "החשבון של אבי")]
    DB[Tables.FIN_EVENTS] = DB[Tables.FIN_EVENTS] + [
        mv("recS1", "balance_snapshot", 100000, "2026-10-01", "recAE"), mv("recD1", "deposit", 5000, "2026-10-05", "recAE"),
        mv("recS2", "balance_snapshot", 777777, "2026-10-01", "recAA", AVI)]


def test_accounts_view_returns_only_own_accounts_and_never_free_text():
    seed_accounts()
    view = service.accounts_view(ELIYAHU, TODAY)
    assert [a["id"] for a in view["accounts"]] == ["recAE"]
    assert view["totals"]["consolidated_value"] == 100000.0 and view["totals"]["estimated_value"] == 105000.0
    text = str(view)
    assert "777777" not in text and "החשבון של אבי" not in text and "הערה פרטית" not in text and "מס rec" not in text
    assert [a["id"] for a in service.accounts_view(AVI_I, TODAY)["accounts"]] == ["recAA"]


def test_accounts_view_unresolved_identity_is_denied():
    seed_accounts()
    with pytest.raises(policy.PersonalDataAccessDenied):
        service.accounts_view(ident("nobody", Role.MANAGER), TODAY)


def test_http_accounts_flag_off_and_non_owner_get_404(monkeypatch):
    seed_accounts()
    assert http(monkeypatch, ELIYAHU, flag=False).get("/api/fcc/accounts", headers=H).status_code == 404
    assert http(monkeypatch, AVI_I).get("/api/fcc/accounts", headers=H).status_code == 404          # partner: not the owner role


def test_http_accounts_owner_gets_own_view_only(monkeypatch):
    seed_accounts()
    r = http(monkeypatch, ELIYAHU).get("/api/fcc/accounts", headers=H)
    body = r.get_json()
    assert r.status_code == 200 and [a["id"] for a in body["accounts"]] == ["recAE"]
    assert "777777" not in str(body) and "הערה פרטית" not in str(body)


def test_http_accounts_unresolved_identity_403_and_read_only(monkeypatch):
    seed_accounts()
    who = ident("nobody", Role.OWNER)
    assert http(monkeypatch, who).get("/api/fcc/accounts", headers=H).status_code == 403
    c = http(monkeypatch, ELIYAHU)
    for method in ("post", "put", "patch", "delete"):
        assert getattr(c, method)("/api/fcc/accounts", headers=H, json={}).status_code == 405        # no write path
    assert len(DB[Tables.FIN_ACCOUNTS]) == 2


# ═══ D1 step 7 / A1: POST /api/fcc/accounts/forecast ═══
def forecast(c, body=None, raw=None):
    import json as _json
    data = raw if raw is not None else _json.dumps(body if body is not None else {"years": 10})
    return c.post("/api/fcc/accounts/forecast", data=data, headers={**H, "Content-Type": "application/json"})


def test_http_forecast_flag_off_and_non_owner_get_404(monkeypatch):
    seed_accounts()
    assert forecast(http(monkeypatch, ELIYAHU, flag=False)).status_code == 404
    assert forecast(http(monkeypatch, AVI_I)).status_code == 404


def test_http_forecast_uses_only_the_callers_own_accounts_and_snapshots(monkeypatch):
    seed_accounts()
    r = forecast(http(monkeypatch, ELIYAHU), {"years": 10, "monthly_contributions": {"recAE": 500}})
    body = r.get_json()
    assert r.status_code == 200 and [a["id"] for a in body["accounts"]] == ["recAE"]
    assert body["accounts"][0]["start_value"] == 100000 and body["consolidated"]["start_value"] == 100000
    assert "777777" not in str(body) and "החשבון של אבי" not in str(body) and "הערה פרטית" not in str(body)
    # another owner's account id cannot be forecast
    bad = forecast(http(monkeypatch, ELIYAHU), {"monthly_contributions": {"recAA": 500}})
    assert bad.status_code == 400 and "777777" not in str(bad.get_json())


def test_http_forecast_validation_and_transport_errors(monkeypatch):
    seed_accounts()
    c = http(monkeypatch, ELIYAHU)
    assert forecast(c, {"years": 5}).status_code == 400
    assert forecast(c, raw="not json").status_code == 400
    assert c.post("/api/fcc/accounts/forecast", data="{}", headers={**H, "Content-Type": "text/plain"}).status_code == 415
    assert c.post("/api/fcc/accounts/forecast", data="x" * (70 * 1024), headers={**H, "Content-Type": "application/json"}).status_code == 413
    assert c.get("/api/fcc/accounts/forecast", headers=H).status_code == 405


def test_http_forecast_unresolved_identity_403_and_nothing_is_written(monkeypatch):
    seed_accounts()
    assert forecast(http(monkeypatch, ident("nobody", Role.OWNER))).status_code == 403
    before = (len(DB[Tables.FIN_ACCOUNTS]), len(DB[Tables.FIN_EVENTS]))
    assert forecast(http(monkeypatch, ELIYAHU)).status_code == 200
    assert (len(DB[Tables.FIN_ACCOUNTS]), len(DB[Tables.FIN_EVENTS])) == before


def test_http_forecast_accounts_without_the_new_fields_still_work_and_list_what_is_missing(monkeypatch):
    seed_accounts()
    body = forecast(http(monkeypatch, ELIYAHU), {"years": 10}).get_json()
    a = body["accounts"][0]
    assert a["start_value"] == 100000 and a["monthly_contribution"] == 0.0 and a["monthly_contribution_source"] == "default"      # the 5000 deposit after the snapshot is not a plan
    assert a["return_source"] == "default" and a["insurance_cost_known"] is False
    assert body["data_gaps"] and body["data_gaps"][0]["id"] == "recAE" and "monthly_deposit" in body["data_gaps"][0]["missing"]


def test_http_forecast_reads_the_new_account_fields_but_a_scenario_cannot_write_them_back(monkeypatch):
    seed_accounts()
    DB[Tables.FIN_ACCOUNTS][0]["fields"].update({ACF.PLANNED_MONTHLY_DEPOSIT: 1500, ACF.EXPECTED_RETURN: 4.0, ACF.LINKAGE: {"name": "cpi"},
                                                 ACF.INSURANCE_COST_MONTHLY: 120, ACF.INSURANCE_COST_AS_OF: "2026-09-30"})
    import copy as _copy
    before = _copy.deepcopy(DB[Tables.FIN_ACCOUNTS])
    c = http(monkeypatch, ELIYAHU)
    a = forecast(c, {"years": 10}).get_json()["accounts"][0]
    assert (a["monthly_contribution"], a["monthly_contribution_source"], a["return_kind"], a["insurance_cost_monthly"]) == (1500.0, "account", "real_to_nominal", 120.0)
    typed = forecast(c, {"years": 10, "monthly_contributions": {"recAE": 300}}).get_json()["accounts"][0]
    assert (typed["monthly_contribution"], typed["monthly_contribution_source"]) == (300.0, "typed")
    for field in ("planned_monthly_deposit", "expected_return_pct", "insurance_cost_monthly", "linkage"):
        assert forecast(c, {"years": 10, field: 1}).status_code == 400                      # only assumptions are accepted, never account fields
    assert DB[Tables.FIN_ACCOUNTS] == before                                                  # a scenario never changes the stored account


def test_http_forecast_returns_goal_coverage_for_the_callers_own_goals_only(monkeypatch):
    tma_api._PL_LIMITER = None                                # the 12/min limiter is process-wide; this test starts from a clean window
    seed_accounts()
    DB[Tables.FIN_ACCOUNTS][0]["fields"][ACF.LIQUIDITY] = "immediate"
    DB[Tables.FIN_ACCOUNTS][1]["fields"][ACF.LIQUIDITY] = "immediate"
    DB[Tables.FIN_GOALS] = DB[Tables.FIN_GOALS] + [
        goal("recGA", "מטרה שלי", ELI, 90000, **{GF.CATEGORY: "long_term", GF.END_DATE: "2027-12-31"}),
        goal("recGB", "מטרה של אבי", AVI, 5, **{GF.CATEGORY: "long_term", GF.END_DATE: "2027-12-31"}),
        goal("recGC", "הכנסה", ELI, 5, **{GF.CATEGORY: "income", GF.END_DATE: "2027-12-31"})]
    import copy as _copy
    before = _copy.deepcopy((DB[Tables.FIN_GOALS], DB[Tables.FIN_ACCOUNTS], DB[Tables.FIN_EVENTS]))
    body = forecast(http(monkeypatch, ELIYAHU), {"years": 10, "annual_return_pct": 0, "annual_fee_pct": 0, "inflation_pct": 0}).get_json()
    mine = [g for g in body["goals"] if g["id"] == "recGA"][0]
    assert [g["id"] for g in body["goals"]] == ["recGA"] and body["goals_skipped"]["other_category"] >= 1       # Avi's goal never shows; income is not a coverage goal
    assert mine["verdict"] == "covered" and mine["accessible_value"] == 100000.0 and mine["due_month"] == "2027-12"
    assert "מטרה של אבי" not in str(body) and "777777" not in str(body)
    assert (DB[Tables.FIN_GOALS], DB[Tables.FIN_ACCOUNTS], DB[Tables.FIN_EVENTS]) == before                   # nothing was written


def test_http_forecast_rejects_goals_or_liquidity_in_the_request_body(monkeypatch):
    tma_api._PL_LIMITER = None
    seed_accounts()
    c = http(monkeypatch, ELIYAHU)
    for field in ("goals", "liquidity", "liquid_from", "accessible"):
        assert forecast(c, {"years": 10, field: [{"id": "x"}]}).status_code == 400


def test_http_locked_until_date_account_is_locked_until_release_then_only_conditional(monkeypatch):
    tma_api._PL_LIMITER = None
    seed_accounts()
    DB[Tables.FIN_ACCOUNTS][0]["fields"].update({ACF.LIQUIDITY: "locked_until_date", ACF.LIQUID_FROM: "2027-11-28"})
    DB[Tables.FIN_GOALS] = DB[Tables.FIN_GOALS] + [
        goal("recGo", "לפני השחרור", ELI, 1, **{GF.CATEGORY: "savings", GF.END_DATE: "2027-10-31"}),
        goal("recGm", "באמצע חודש השחרור", ELI, 1, **{GF.CATEGORY: "savings", GF.END_DATE: "2027-11-15"}),
        goal("recGn", "בסוף חודש השחרור", ELI, 1, **{GF.CATEGORY: "savings", GF.END_DATE: "2027-11-30"})]
    body = forecast(http(monkeypatch, ELIYAHU), {"years": 10, "annual_return_pct": 0, "annual_fee_pct": 0, "inflation_pct": 0}).get_json()
    acc = body["accounts"][0]
    assert acc["liquidity"] == {"basis": "dated", "liquid_from": "2027-11-28", "state_now": "locked", "state_at_horizon": "conditional"}
    goals = {g["id"]: g for g in body["goals"]}
    before, mid, after = goals["recGo"], goals["recGm"], goals["recGn"]
    assert (before["locked_value"], before["conditional_value"]) == (100000.0, 0.0)               # still locked on the last day before the release month
    assert (mid["locked_value"], mid["conditional_value"], mid["value_as_of"]) == (100000.0, 0.0, "2027-10-31")      # due 15/11 < release 28/11
    assert (after["locked_value"], after["conditional_value"]) == (0.0, 100000.0)                 # month end after the release: conditional - never accessible
    for g in (before, mid, after):
        assert g["accessible_value"] is None and g["verdict"] == "not_comparable" and g["reason"] == "no_verified_accessible_account"
    series = body["consolidated"]["series"]
    assert series[0]["locked"] == 100000.0 and series[0]["accessible"] == 0 and series[-1]["conditional"] == 100000.0 and series[-1]["locked"] == 0
    assert all(p["accessible"] == 0 for p in series)


# ═══ D1 step 8: account writes (balance snapshot / deposit) through the shared draft -> review -> אשר flow ═══
def seed_account_writes():
    seed_accounts()
    DB[Tables.FIN_GOALS] = DB[Tables.FIN_GOALS] + [goal("recPenD", "תכנון פנסיוני", ELI, None, **{GF.CATEGORY: "long_term"})]
    DB[Tables.FIN_ACCOUNTS].append({"id": "recAC", "fields": {ACF.NAME: "חשבון סגור", ACF.STATUS: "closed", ACF.FINANCIAL_OWNER: [ELI]}})


def test_account_intents_are_registered_need_a_target_and_are_not_transitions():
    for iid, ent in (("account.update_balance", "fcc_account_balance"), ("account.deposit", "fcc_account_deposit")):
        assert fd.INTENTS[iid]["entity"] == ent and fd.INTENTS[iid]["target_required"] and fd.INTENTS[iid]["target"] == "account"
        assert not fd.INTENTS[iid].get("transition")
    assert set(fd.FCC_CONTRACTS["fcc_account_balance"].fields[i].field_name for i in range(3)) == {"balance", "occurred_at", "verification"}
    for c in (fd.FCC_CONTRACTS["fcc_account_balance"], fd.FCC_CONTRACTS["fcc_account_deposit"]):
        assert not any(f.field_name in ("note", "title", "name") for f in c.fields)          # no free text can reach an account write


def test_balance_snapshot_flow_writes_exactly_one_event_with_the_account_and_no_goal():
    seed_account_writes()
    r = intent("account.update_balance", "recAE")
    assert r.state == "ask" and r.awaiting == "balance" and "קרן השתלמות" in r.message and "100,000" in r.message
    r = say("120000", balance=120000)
    assert r.state == "review" and "עדכון יתרת חשבון" in r.message and "₪120,000" in r.message and "קרן השתלמות" in r.message
    assert "לא נבדקת מול בנק או קרן" in r.message and r.snapshot is None
    (w,) = conv.handle_turn(ELIYAHU, "אשר", extractor=Ex(), today=TODAY).snapshot["writes"]
    f = w["fields"]
    assert w["op"] == "post" and w["table"] == Tables.FIN_EVENTS
    assert f[EF.KIND] == "balance_snapshot" and f[EF.AMOUNT] == 120000 and f[EF.ACCOUNT] == ["recAE"] and f[EF.VERIFICATION] == "self_reported"
    assert f[EF.OCCURRED_AT] == TODAY.isoformat() and EF.GOAL not in f and f[EF.IDEMPOTENCY_KEY].startswith("fcc-")
    assert f[EF.RAW_TEXT].startswith("intent:account.update_balance#") and not policy.contains_long_number(f[EF.RAW_TEXT])


def test_synthetic_token_never_holds_a_long_number_so_the_account_guard_cannot_reject_our_own_write():
    seeds = {conv._intent_token() for _ in range(2000)}
    assert all(len(t) == 8 and not any(ch.isdigit() for ch in t) for t in seeds)
    seed_account_writes()
    for _ in range(40):
        conv.complete_execution(ELIYAHU)
        intent("account.update_balance", "recAE"); say("1", balance=1)
        w = conv.handle_turn(ELIYAHU, "אשר", extractor=Ex(), today=TODAY).snapshot["writes"][0]
        scoped = policy.scope_new_record_fields(Tables.FIN_EVENTS, dict(w["fields"]), ELIYAHU)
        assert scoped[EF.FINANCIAL_OWNER] == [ELI]                                        # accepted by the real access policy


def test_balance_verification_can_be_edited_to_a_presented_choice_and_a_future_date_is_refused():
    seed_account_writes()
    real = conv.DeterministicExtractor()                                     # the real rule-based edit grammar ("<label> <value>")
    intent("account.update_balance", "recAE"); say("5", balance=5)
    conv.handle_turn(ELIYAHU, "ערוך", extractor=real, today=TODAY)
    r = conv.handle_turn(ELIYAHU, "מקור הנתון לפי דוח", extractor=real, today=TODAY)
    assert r.state == "review" and "לפי דוח" in r.message
    conv.handle_turn(ELIYAHU, "ערוך", extractor=real, today=TODAY)
    r = conv.handle_turn(ELIYAHU, "נכון לתאריך 2026-12-31", extractor=real, today=TODAY)
    assert "עתידי" in r.message
    r = conv.handle_turn(ELIYAHU, "נכון לתאריך 2026-09-30", extractor=real, today=TODAY)
    assert r.state == "review" and "30/09/2026" in r.message
    (w,) = conv.handle_turn(ELIYAHU, "אשר", extractor=real, today=TODAY).snapshot["writes"]
    assert w["fields"][EF.VERIFICATION] == "statement" and w["fields"][EF.OCCURRED_AT] == "2026-09-30"


def test_deposit_without_a_goal_choice_writes_a_deposit_event_on_the_account_only():
    seed_account_writes()
    r = intent("account.deposit", "recAE")
    assert r.state == "ask" and r.awaiting == "count" and "תכנון פנסיוני" in r.message
    assert [c["goal_id"] for c in r.candidates] == ["count", "skip"]
    r = conv.handle_turn(ELIYAHU, "לא, רק בחשבון", goal_id="skip", extractor=Ex(), today=TODAY)
    assert r.awaiting == "amount"
    r = say("3000", amount=3000)
    assert r.state == "review" and "לא תיספר" in r.message and "לא משנה את היתרה המדווחת" in r.message
    (w,) = conv.handle_turn(ELIYAHU, "אשר", extractor=Ex(), today=TODAY).snapshot["writes"]
    f = w["fields"]
    assert f[EF.KIND] == "deposit" and f[EF.AMOUNT] == 3000 and f[EF.ACCOUNT] == ["recAE"] and EF.GOAL not in f


def test_deposit_counted_in_the_goal_is_ONE_deposit_event_never_also_one_time():
    seed_account_writes()
    intent("account.deposit", "recAE")
    r = conv.handle_turn(ELIYAHU, "כן, לספור", goal_id="count", extractor=Ex(), today=TODAY)
    say("3000", amount=3000)
    snap = conv.handle_turn(ELIYAHU, "אשר", extractor=Ex(), today=TODAY).snapshot
    (w,) = snap["writes"]                                                              # exactly one write: the double-count guard
    assert w["fields"][EF.KIND] == "deposit" and w["fields"][EF.GOAL] == ["recPenD"] and w["fields"][EF.ACCOUNT] == ["recAE"]
    # the roll-ups count it once, with the existing one_time history untouched
    events = calc.parse_events([{"id": "d1", "fields": {**w["fields"], EF.KIND: "deposit"}}], EF)
    assert len(events) == 1 and calc.deposits_in_month(events, TODAY) == 3000


def test_deposit_goal_question_is_skipped_when_there_is_no_unique_destination_goal():
    seed_account_writes()
    DB[Tables.FIN_GOALS] = [g for g in DB[Tables.FIN_GOALS] if g["id"] != "recPenD"]
    r = intent("account.deposit", "recAE")
    assert r.awaiting == "amount"


def test_account_intents_are_owner_only_own_accounts_only_and_closed_accounts_have_nothing_to_update():
    seed_account_writes()
    assert intent("account.update_balance", "recAA").state == "denied"                  # Avi's account == not found
    assert intent("account.deposit", "recAA").state == "denied"
    assert intent("account.update_balance").state == "clarify"
    assert intent("account.update_balance", "recAC").state == "info"
    assert intent("account.update_balance", "recGE").state == "denied"                  # a goal id is not an account
    assert intent("account.update_balance", "recAA", who=AVI_I).state == "denied"      # the partner never reaches the owner's accounts
    assert intent("account.update_balance", "recAE", who=AVI_I).state == "denied"


def test_same_balance_text_is_not_written_twice_and_a_conflicting_same_day_snapshot_is_refused():
    seed_account_writes()
    # an existing snapshot of the same account on the same day: same amount = duplicate, a different amount = ambiguous -> refused
    DB[Tables.FIN_EVENTS].append({"id": "recSx", "fields": {EF.KIND: "balance_snapshot", EF.AMOUNT: 100000, EF.OCCURRED_AT: TODAY.isoformat(),
                                                           EF.ACCOUNT: ["recAE"], EF.FINANCIAL_OWNER: [ELI]}})
    intent("account.update_balance", "recAE"); say("111", balance=111)
    r = conv.handle_turn(ELIYAHU, "אשר", extractor=Ex(), today=TODAY)
    assert r.state == "clarify" and "כבר קיימת יתרה מדווחת" in r.message and "100,000" in r.message
    conv.handle_turn(ELIYAHU, "בטל", extractor=Ex(), today=TODAY)
    intent("account.update_balance", "recAE"); say("100000", balance=100000)
    assert conv.handle_turn(ELIYAHU, "אשר", extractor=Ex(), today=TODAY).state == "duplicate"   # same account + day + amount already stands


def test_account_cannot_be_retargeted_by_an_edit():
    seed_account_writes()
    intent("account.update_balance", "recAE")
    say("7", balance=7, record_id="recAA", account_id="recAA")
    assert conv.handle_turn(ELIYAHU, "אשר", extractor=Ex(), today=TODAY).snapshot["writes"][0]["fields"][EF.ACCOUNT] == ["recAE"]


def test_http_confirm_executes_the_frozen_write_through_the_gateway(monkeypatch):
    seed_account_writes()
    sent = []
    monkeypatch.setattr(tma_api, "_queue_or_owner_execute", lambda tool, write, ident, label: (None, {"ok": True}, 200) if sent.append(write) is None else None)
    c = http(monkeypatch, ELIYAHU)
    assert c.post("/api/fcc/intent/start", json={"intent": "account.update_balance", "entity_id": "recAE"}, headers=H).get_json()["state"] == "ask"
    r = c.post("/api/fcc/write", json={"text": "250000"}, headers=H).get_json()
    assert r["state"] == "review"
    done = c.post("/api/fcc/write", json={"text": "אשר"}, headers=H).get_json()
    assert done["state"] == "executed" and len(sent) == 1
    assert sent[0]["fields"][EF.AMOUNT] == 250000 and sent[0]["fields"][EF.ACCOUNT] == ["recAE"]
    # the real executor's access policy accepts it for the owner and rejects another person's account
    scoped = policy.scope_new_record_fields(Tables.FIN_EVENTS, dict(sent[0]["fields"]), ELIYAHU)
    assert scoped[EF.FINANCIAL_OWNER] == [ELI]
    with pytest.raises(policy.PersonalDataAccessDenied):
        policy.scope_new_record_fields(Tables.FIN_EVENTS, {**sent[0]["fields"], EF.ACCOUNT: ["recAA"]}, ELIYAHU)


# ── D1 step 8 review follow-ups: one_time overlap warning, concurrent confirm, audit hand-off ──
def test_deposit_review_warns_when_the_same_goal_amount_and_day_already_stand_as_a_one_time():
    seed_account_writes()
    DB[Tables.FIN_EVENTS].append(event("recOT", "recPenD", ELI, 3000, kind="one_time", day=TODAY.isoformat()))      # booked by hand as a savings deposit
    intent("account.deposit", "recAE")
    conv.handle_turn(ELIYAHU, "כן, לספור", goal_id="count", extractor=Ex(), today=TODAY)
    r = say("3000", amount=3000)
    assert r.state == "review" and "כבר רשומה בהיסטוריית היעד הפקדה חד-פעמית" in r.message and "אם זו אותה הפקדה — בטלו" in r.message
    assert "לא תיספר" not in r.message and "תיספר בהיסטוריית ההפקדות" in r.message
    # not the same money -> no warning, but the standing "do not register twice" line stays on every deposit review
    conv.handle_turn(ELIYAHU, "בטל", extractor=Ex(), today=TODAY)
    intent("account.deposit", "recAE")
    conv.handle_turn(ELIYAHU, "כן, לספור", goal_id="count", extractor=Ex(), today=TODAY)
    r = say("3500", amount=3500)
    assert "כבר רשומה" not in r.message and "אל תרשמו אותה שוב" in r.message
    # an edit that makes it match raises the warning, and one that moves it away removes it again
    conv.handle_turn(ELIYAHU, "ערוך", extractor=Ex(), today=TODAY)
    r = conv.handle_turn(ELIYAHU, "סכום ההפקדה 3000", extractor=conv.DeterministicExtractor(), today=TODAY)
    assert "כבר רשומה" in r.message
    conv.handle_turn(ELIYAHU, "ערוך", extractor=Ex(), today=TODAY)
    r = conv.handle_turn(ELIYAHU, "סכום ההפקדה 3100", extractor=conv.DeterministicExtractor(), today=TODAY)
    assert "כבר רשומה" not in r.message
    # a deposit that is not counted in a goal can never overlap a goal one_time
    conv.handle_turn(ELIYAHU, "בטל", extractor=Ex(), today=TODAY)
    intent("account.deposit", "recAE")
    conv.handle_turn(ELIYAHU, "לא, רק בחשבון", goal_id="skip", extractor=Ex(), today=TODAY)
    assert "כבר רשומה" not in say("3000", amount=3000).message


def test_concurrent_confirms_never_yield_two_different_writes(mem_store):
    """Several "אשר" racing on ONE draft: the draft store's compare-and-swap lets exactly one READY -> CONFIRMED transition win; every result that
    still carries a snapshot carries the SAME frozen write (same Idempotency Key), so the ActionGateway's request fingerprint collapses them."""
    import threading
    seed_account_writes()
    intent("account.update_balance", "recAE"); say("99", balance=99)
    barrier, results, errors = threading.Barrier(6), [], []

    def confirm():
        try:
            barrier.wait()
            results.append(conv.handle_turn(ELIYAHU, "אשר", extractor=Ex(), today=TODAY))
        except Exception as exc:                                   # a lost CAS may surface as an exception: also "no second write"
            errors.append(exc)
    threads = [threading.Thread(target=confirm) for _ in range(6)]
    [t.start() for t in threads]; [t.join() for t in threads]
    snaps = [r.snapshot for r in results if r.snapshot]
    assert snaps, "one of the racers must win"
    assert len({str(s["writes"]) for s in snaps}) == 1                  # byte-identical frozen payload: one Idempotency Key
    assert len({s["writes"][0]["fields"][EF.IDEMPOTENCY_KEY] for s in snaps}) == 1
    assert all(len(s["writes"]) == 1 for s in snaps)
    assert all(r.state in ("confirmed", "clarify", "info", "duplicate", "unrelated", "ask", "review") for r in results)


def test_the_hand_off_to_the_gateway_carries_our_audit_action_into_the_audit_trail(monkeypatch):
    """Not an Airtable round trip (that needs a live base): it proves WHAT we hand to the executor and that the executor audits it by that label."""
    seed_account_writes()
    intent("account.update_balance", "recAE"); say("88", balance=88)
    (w,) = conv.handle_turn(ELIYAHU, "אשר", extractor=Ex(), today=TODAY).snapshot["writes"]
    assert w["audit_action"] == "fcc_account_balance" and w["audit_details"] == w["fields"][EF.IDEMPOTENCY_KEY]
    audited = []
    monkeypatch.setattr(tma_api, "_queue_tma_write_approval", lambda action, payload, identity, label: ("recApproval", {"contract_id": "c1"}, 202))
    monkeypatch.setattr(tma_api, "_claim_and_execute_approval", lambda approval_id, identity: {"ok": True, "execution_result": {"executed": 1}})
    monkeypatch.setattr(tma_api, "_audit", lambda action, identity, details="": audited.append((action, details)))
    approval_id, result, status = tma_api._queue_or_owner_execute("tma_fcc_write", w, ELIYAHU, f"FCC: {w.get('audit_action', 'write')}")
    assert status == 200 and result["status"] == "executed" and result["approval_id"] == "recApproval"
    assert audited == [("tma_fcc_write_owner_autoapprove", "FCC: fcc_account_balance")]            # who/what is in the trail
    dep_audit = {"account.deposit": "fcc_account_deposit"}
    conv.complete_execution(ELIYAHU)
    intent("account.deposit", "recAE"); conv.handle_turn(ELIYAHU, "לא, רק בחשבון", goal_id="skip", extractor=Ex(), today=TODAY); say("5", amount=5)
    (d,) = conv.handle_turn(ELIYAHU, "אשר", extractor=Ex(), today=TODAY).snapshot["writes"]
    assert d["audit_action"] == dep_audit["account.deposit"]


def test_the_same_frozen_write_proposed_many_times_reaches_the_real_gateway_as_one_contract():
    """The other half of the concurrency answer: the draft layer may hand the SAME frozen write to several racers, and the REAL ActionGateway
    (in-memory ledger) collapses identical requests into one contract — one pending approval, so at most one execution."""
    import threading
    from core.action_gateway import ActionGateway, ExecutionLedger
    seed_account_writes()
    intent("account.deposit", "recAE"); conv.handle_turn(ELIYAHU, "לא, רק בחשבון", goal_id="skip", extractor=Ex(), today=TODAY); say("42", amount=42)
    (w,) = conv.handle_turn(ELIYAHU, "אשר", extractor=Ex(), today=TODAY).snapshot["writes"]
    tool_inputs = {**{k: v for k, v in w.items() if k not in ("op", "table", "action", "requested_by")},        # exactly as _queue_tma_write_approval builds it
                   "op": w["op"], "table": w["table"], "action": "tma_fcc_write", "requested_by": "tg:1"}
    gw = ActionGateway(ledger=ExecutionLedger())
    barrier, results = threading.Barrier(6), []

    def propose():
        barrier.wait()
        results.append(gw.propose_action(tenant_id="boss_hq", canonical_user_id="boss_hq:eliyahu", tool_name="tma_write", tool_inputs=dict(tool_inputs),
                                         origin_channel="tma", origin_chat_id="1", requires_approval=True))
    threads = [threading.Thread(target=propose) for _ in range(6)]
    [t.start() for t in threads]; [t.join() for t in threads]
    assert sum(1 for r in results if r.ok) == 1                                       # exactly one new contract
    assert len({r.contract_id for r in results if r.contract_id}) == 1                # everyone else got that same contract back


# ═══ B2 step 3: Goal Allocations in the forecast — owner scope, read-only ═══
from airtable_schema import GoalAllocationFields as GAF   # noqa: E402


def alloc_row(rid, owner, goal_id, account_id, mode="percent", value=30, status="active"):
    f = {GAF.NAME: f"x-{rid}", GAF.GOAL: [goal_id], GAF.ACCOUNT: [account_id], GAF.FINANCIAL_OWNER: [owner], GAF.MODE: mode, GAF.STATUS: status}
    f[GAF.PERCENT if mode == "percent" else GAF.AMOUNT] = value
    return {"id": rid, "fields": f}


FLAT_PARAMS = {"years": 10, "annual_return_pct": 0, "annual_fee_pct": 0, "inflation_pct": 0}


def test_http_forecast_with_an_empty_allocations_table_is_unchanged_and_shows_zero(monkeypatch):
    tma_api._PL_LIMITER = None
    seed_accounts()
    DB[Tables.GOAL_ALLOCATIONS] = []
    body = forecast(http(monkeypatch, ELIYAHU), FLAT_PARAMS).get_json()
    assert body["allocations"]["has_allocations"] is False and body["allocations"]["totals"]["allocated"] == 0.0
    assert body["allocations"]["totals"]["unallocated"] == 100000.0 and body["allocations"]["goals"] == []
    DB.pop(Tables.GOAL_ALLOCATIONS)                           # a base where the table has no rows at all behaves the same
    assert forecast(http(monkeypatch, ELIYAHU), FLAT_PARAMS).get_json()["allocations"]["count"] == 0


def test_http_forecast_uses_only_the_callers_allocations_and_ignores_links_to_other_peoples_records(monkeypatch):
    tma_api._PL_LIMITER = None
    seed_accounts()
    DB[Tables.FIN_ACCOUNTS][0]["fields"][ACF.LIQUIDITY] = "immediate"
    DB[Tables.FIN_GOALS] = DB[Tables.FIN_GOALS] + [
        goal("recGM", "מטרה שלי", ELI, 40000, **{GF.CATEGORY: "long_term", GF.END_DATE: "2027-12-31"}),
        goal("recGV", "מטרה של אבי", AVI, 5, **{GF.CATEGORY: "long_term", GF.END_DATE: "2027-12-31"})]
    DB[Tables.GOAL_ALLOCATIONS] = [
        alloc_row("recAL1", ELI, "recGM", "recAE", "percent", 50),                 # mine
        alloc_row("recAL2", AVI, "recGV", "recAA", "percent", 80),                 # Avi's own row: never read
        alloc_row("recAL3", ELI, "recGM", "recAA", "fixed_amount", 123456),        # my row, but it links Avi's account
        alloc_row("recAL4", ELI, "recGV", "recAE", "fixed_amount", 654321)]        # my row, but it links Avi's goal
    import copy as _copy
    before = _copy.deepcopy(DB)
    body = forecast(http(monkeypatch, ELIYAHU), FLAT_PARAMS).get_json()
    a = body["allocations"]
    assert a["count"] == 1 and a["skipped"]["unknown_link"] == 2
    assert a["totals"]["allocated"] == 50000.0 and a["totals"]["unallocated"] == 50000.0
    assert [x["id"] for x in a["goals"]] == ["recGM"] and a["goals"][0]["accessible"] == 50000.0
    mine = [g for g in body["goals"] if g["id"] == "recGM"][0]
    assert (mine["basis"], mine["allocated_value"], mine["verdict"], mine["gap"]) == ("allocation", 50000.0, "covered", None)
    text = str(body)
    for hidden in ("מטרה של אבי", "החשבון של אבי", "123456", "654321", "777777", "recAA", "recGV"):
        assert hidden not in text, hidden
    assert DB == before                                                                     # nothing was written, anywhere


def test_http_allocation_reader_is_owner_scoped_and_read_only(monkeypatch):
    seed_accounts()
    DB[Tables.GOAL_ALLOCATIONS] = [alloc_row("recAL1", ELI, "recGE", "recAE"), alloc_row("recAL2", AVI, "recGA", "recAA")]
    rows = service.allocations_for_forecast(ELIYAHU)
    assert [r["id"] for r in rows] == ["recAL1"] and rows[0]["goal_id"] == "recGE" and rows[0]["account_id"] == "recAE"
    assert set(rows[0]) == {"id", "goal_id", "account_id", "mode", "percent", "amount", "status", "effective_from"}      # no names, no free text
    with pytest.raises(policy.PersonalDataAccessDenied):
        service.allocations_for_forecast(None)
    multi = {"id": "recAL9", "fields": {GAF.GOAL: ["recGE", "recGA"], GAF.ACCOUNT: ["recAE"], GAF.FINANCIAL_OWNER: [ELI], GAF.MODE: "percent", GAF.PERCENT: 5}}
    DB[Tables.GOAL_ALLOCATIONS].append(multi)
    assert [r for r in service.allocations_for_forecast(ELIYAHU) if r["id"] == "recAL9"][0]["goal_id"] is None       # several links are never guessed at


def test_http_over_allocation_is_reported_through_the_endpoint(monkeypatch):
    tma_api._PL_LIMITER = None
    seed_accounts()
    DB[Tables.FIN_GOALS] = DB[Tables.FIN_GOALS] + [goal("recGM", "מטרה שלי", ELI, 40000, **{GF.CATEGORY: "long_term", GF.END_DATE: "2027-12-31"})]
    DB[Tables.GOAL_ALLOCATIONS] = [alloc_row("recAL1", ELI, "recGM", "recAE", "fixed_amount", 70000), alloc_row("recAL2", ELI, "recGM", "recAE", "fixed_amount", 50000)]
    body = forecast(http(monkeypatch, ELIYAHU), FLAT_PARAMS).get_json()
    acct_row = body["allocations"]["accounts"][0]
    assert acct_row["over_allocated"] is True and acct_row["over_by"] == 20000.0 and acct_row["unallocated"] == 0.0
    assert [g["reason"] for g in body["goals"]] == ["over_allocated"]


def test_http_other_peoples_allocation_rows_never_change_the_callers_totals_or_leak_through_aggregates(monkeypatch):
    tma_api._PL_LIMITER = None
    seed_accounts()
    DB[Tables.FIN_ACCOUNTS][0]["fields"][ACF.LIQUIDITY] = "immediate"
    DB[Tables.FIN_GOALS] = DB[Tables.FIN_GOALS] + [
        goal("recGM", "מטרה שלי", ELI, 40000, **{GF.CATEGORY: "long_term", GF.END_DATE: "2027-12-31"}),
        goal("recGV", "מטרה של אבי", AVI, 5, **{GF.CATEGORY: "long_term", GF.END_DATE: "2027-12-31"})]
    mine = [alloc_row("recAL1", ELI, "recGM", "recAE", "percent", 25)]
    DB[Tables.GOAL_ALLOCATIONS] = list(mine)
    c = http(monkeypatch, ELIYAHU)
    baseline = forecast(c, FLAT_PARAMS).get_json()
    # Avi's rows: one on Avi's own goal/account, and rows that try to claim MY goal / MY account (so they would move my totals if they were read)
    DB[Tables.GOAL_ALLOCATIONS] = mine + [
        alloc_row("recAL2", AVI, "recGV", "recAA", "fixed_amount", 777000),
        alloc_row("recAL3", AVI, "recGV", "recAE", "percent", 60),                    # Avi claims 60% of MY account for his goal
        alloc_row("recAL4", AVI, "recGM", "recAE", "fixed_amount", 90000)]            # Avi claims 90,000 of MY account for MY goal
    tma_api._PL_LIMITER = None
    out = forecast(c, FLAT_PARAMS).get_json()
    assert out["allocations"] == baseline["allocations"] and out["goals"] == baseline["goals"]
    assert out["allocations"]["totals"] == {"accounts_value": 100000.0, "allocated": 25000.0, "unallocated": 75000.0, "over_allocated": 0.0}
    for hidden in ("777000", "777777", "recAA", "recGV", "מטרה של אבי", "החשבון של אבי"):
        assert hidden not in str(out), hidden


def test_a_co_owned_row_never_exposes_the_other_owners_account_or_goal_to_the_second_owner(monkeypatch):
    from portfolio_lab.accounts_forecast import build_accounts_forecast
    seed_accounts()
    DB[Tables.FIN_ACCOUNTS][0]["fields"][ACF.LIQUIDITY] = "immediate"
    DB[Tables.FIN_GOALS] = DB[Tables.FIN_GOALS] + [goal("recGM", "מטרה שלי", ELI, 40000, **{GF.CATEGORY: "long_term", GF.END_DATE: "2027-12-31"})]
    row = alloc_row("recALX", ELI, "recGM", "recAE", "percent", 25)
    row["fields"][GAF.FINANCIAL_OWNER] = [ELI, AVI]                                   # a row listing both people as owners
    DB[Tables.GOAL_ALLOCATIONS] = [row]
    rows_for_avi = service.allocations_for_forecast(AVI_I)
    assert [r["id"] for r in rows_for_avi] == ["recALX"]                              # the policy lets a listed owner read the row...
    out = build_accounts_forecast(service.accounts_view(AVI_I), FLAT_PARAMS, goals=service.goals_for_forecast(AVI_I), allocations=rows_for_avi)
    assert out["allocations"]["count"] == 0 and out["allocations"]["skipped"]["unknown_link"] == 1      # ...but its links are not Avi's, so nothing contributes
    assert out["allocations"]["totals"]["allocated"] == 0.0
    for hidden in ("קרן השתלמות", "מטרה שלי", "100000", "recAE", "recGM"):
        assert hidden not in str(out), hidden


# ═══ Goal Funding Planner, step 1: POST /api/fcc/funding/plan — owner scope, read-only ═══
def planner(c, body=None, raw=None):
    import json as _json
    data = raw if raw is not None else _json.dumps(body if body is not None else {})
    return c.post("/api/fcc/funding/plan", data=data, headers={**H, "Content-Type": "application/json"})


def seed_planner():
    seed_accounts()
    seed_loans()
    DB[Tables.FIN_GOALS] = DB[Tables.FIN_GOALS] + [
        goal("recGW", "חתונה", ELI, 200000, **{GF.CATEGORY: "savings", GF.END_DATE: "2040-12-31", GF.CALC_METHOD: "cumulative"}),
        goal("recGX", "חתונה של אבי", AVI, 888888, **{GF.CATEGORY: "savings", GF.END_DATE: "2040-12-31", GF.CALC_METHOD: "cumulative"})]


DEPOSIT = {"id": "dep", "type": "new_deposits", "hypothetical": {"immediate": True, "expected_return_pct": 4}}


def test_http_planner_flag_off_and_non_owner_get_404(monkeypatch):
    seed_planner()
    assert planner(http(monkeypatch, ELIYAHU, flag=False), {"goal_id": "recGW"}).status_code == 404
    assert planner(http(monkeypatch, AVI_I), {"goal_id": "recGW"}).status_code == 404
    assert http(monkeypatch, ELIYAHU).options("/api/fcc/funding/plan").status_code == 204


def test_http_planner_compares_options_for_the_callers_own_goal_only(monkeypatch):
    seed_planner()
    r = planner(http(monkeypatch, ELIYAHU), {"goal_id": "recGW", "options": [DEPOSIT]})
    body = r.get_json()
    assert r.status_code == 200 and body["goals"][0]["need"]["target"] == 200000 and body["goals"][0]["need"]["gap"] == 200000
    assert {o["type"] for o in body["goals"][0]["options"]} == {"existing_balance", "new_deposits"}
    dep = next(o for o in body["goals"][0]["options"] if o["type"] == "new_deposits")
    assert dep["feasible"] is True and dep["certainty"] == "expected" and dep["monthly_cash_effect"] < 0
    text = str(body)
    for hidden in ("888888", "חתונה של אבי", "777777", "החשבון של אבי", "הערה פרטית", "999999", "77777"):
        assert hidden not in text, hidden


def test_http_planner_rejects_another_owners_goal_loan_asset_and_account_without_leaking(monkeypatch):
    seed_planner()
    c = http(monkeypatch, ELIYAHU)
    for body in ({"goal_id": "recGX"},
                 {"goal_id": "recGW", "options": [{"type": "receivable_collection", "loan_id": "recLX", "expected_net": 5, "expected_date": "2030-01-01"}]},
                 {"goal_id": "recGW", "options": [{"type": "asset_sale", "asset_id": "recA2", "net_proceeds": 5, "expected_date": "2030-01-01"}]},
                 {"goal_id": "recGW", "options": [{"type": "new_deposits", "account_id": "recAA"}]}):
        r = planner(c, body)
        assert r.status_code == 400, body
        text = str(r.get_json())
        assert "888888" not in text and "999999" not in text and "777777" not in text and "נכס של אבי" not in text


def test_http_planner_validation_and_transport_errors_do_not_echo_amounts(monkeypatch):
    seed_planner()
    c = http(monkeypatch, ELIYAHU)
    assert planner(c, raw="not json").status_code == 400
    assert planner(c, {"goal_id": "recGW", "options": [{"type": "custom", "label": "x", "amount": -424242}]}).status_code == 400
    r = planner(c, {"goal_id": "recGW", "options": [{"type": "custom", "label": "x", "amount": -424242}]})
    assert "424242" not in str(r.get_json())
    assert planner(c, {}).status_code == 400
    assert c.post("/api/fcc/funding/plan", data="{}", headers={**H, "Content-Type": "text/plain"}).status_code == 415


def test_http_planner_unresolved_identity_403_and_nothing_is_written(monkeypatch):
    import copy as _copy
    seed_planner()
    assert planner(http(monkeypatch, ident("nobody", Role.OWNER)), {"goal_id": "recGW"}).status_code == 403
    before = _copy.deepcopy(DB)
    assert planner(http(monkeypatch, ELIYAHU), {"goal_id": "recGW", "options": [DEPOSIT]}).status_code == 200
    assert DB == before
    c = http(monkeypatch, ELIYAHU)
    for method in ("get", "put", "patch", "delete"):
        assert getattr(c, method)("/api/fcc/funding/plan", headers=H).status_code == 405          # no write path


def test_http_planner_reads_a_debt_owed_to_me_but_does_not_count_it_as_money(monkeypatch):
    seed_planner()
    DB[Tables.LOANS] = DB[Tables.LOANS] + [loan("recOW", **{LF.EARLY_CLOSURE: 100000, LF.DIRECTION: "חייבים לי"})]
    body = planner(http(monkeypatch, ELIYAHU), {"goal_id": "recGW", "options": [
        {"id": "owed", "type": "receivable_collection", "loan_id": "recOW", "expected_net": 100000, "expected_date": "2030-01-01"}],
        "allocation_plan": [{"goal_id": "recGW", "option_id": "owed", "amount": 100000}]}).get_json()
    plan_ = body["goals"][0]["plan"]
    assert plan_["covered"]["uncertain"] == 100000 and plan_["covered"]["confirmed"] == 0 and plan_["remaining_after_confirmed"] == 200000
    assert body["goals"][0]["need"]["confirmed_existing"] == 0


# ═══ Funding planner, step 2: saving the chosen plan — draft -> review -> אשר, one owner-scoped Funding Plans row ═══
from airtable_schema import FundingPlanFields as FPF   # noqa: E402


def seed_saved_plans():
    seed_planner()
    DB[Tables.FUNDING_PLANS] = [
        {"id": "recFPold", "fields": {FPF.NAME: "ישנה", FPF.GOAL: ["recGW"], FPF.STATUS: "chosen", FPF.FINANCIAL_OWNER: [ELI]}},
        {"id": "recFPdone", "fields": {FPF.NAME: "מוחלפת", FPF.GOAL: ["recGW"], FPF.STATUS: "superseded", FPF.FINANCIAL_OWNER: [ELI]}},
        {"id": "recFPavi", "fields": {FPF.NAME: "של אבי", FPF.GOAL: ["recGX"], FPF.STATUS: "chosen", FPF.FINANCIAL_OWNER: [AVI]}},
    ]


def funding_plan_for(req):
    from portfolio_lab.funding_plan import build_funding_plan, normalize_request
    request_ = normalize_request(req)
    return request_, build_funding_plan(service.funding_inputs(ELIYAHU), request_)


def start_save(selected=("dep",), req=None):
    request_, plan_ = funding_plan_for(req or {"goal_id": "recGW", "options": [DEPOSIT]})
    return conv.start_funding_plan_save(ELIYAHU, request_, plan_, list(selected), today=TODAY)


def test_funding_save_opens_a_review_and_writes_nothing():
    import copy as _copy
    seed_saved_plans()
    before = _copy.deepcopy(DB)
    r = start_save()
    assert r.state == "review" and "שמירת תוכנית מימון" in r.message and "חתונה" in r.message
    assert "לא מזיזה כסף" in r.message and "מוחלפת (1)" in r.message
    assert DB == before                                                                               # a draft is not a write


def test_funding_save_confirm_freezes_one_snapshot_and_supersedes_only_the_goals_chosen_plan():
    import json as _json
    seed_saved_plans()
    start_save()
    for text in ("ערוך", "הערת החלטה בחרנו להפקיד", "ערוך", "לבדוק שוב עד 2027-01-31"):
        assert conv.handle_turn(ELIYAHU, text, extractor=conv.DeterministicExtractor(), today=TODAY).state in ("ask", "review")
    writes = conv.handle_turn(ELIYAHU, "אשר", extractor=conv.DeterministicExtractor(), today=TODAY).snapshot["writes"]
    assert [w["op"] for w in writes] == ["patch", "post"]                                          # patches first: a retry never duplicates the row
    patch_, post_ = writes
    assert patch_["record_id"] == "recFPold" and patch_["fields"] == {FPF.STATUS: "superseded"} and patch_["table"] == Tables.FUNDING_PLANS
    f = post_["fields"]
    assert post_["table"] == Tables.FUNDING_PLANS and f[FPF.GOAL] == ["recGW"] and f[FPF.STATUS] == "chosen" and f[FPF.TARGET_AMOUNT] == 200000
    assert f[FPF.NAME] == "תוכנית מימון — חתונה" and f[FPF.AS_OF] == date.today().isoformat()
    assert f[FPF.DECISION_NOTE] == "בחרנו להפקיד" and f[FPF.REVIEW_BY] == "2027-01-31"
    chosen = _json.loads(f[FPF.SELECTED_OPTIONS])
    assert chosen == [{"id": "dep", "type": "new_deposits", "use_amount": None}]
    assert _json.loads(f[FPF.REQUEST_SNAPSHOT])["goal_ids"] == ["recGW"]
    result_ = _json.loads(f[FPF.RESULT_SNAPSHOT])
    assert result_["need"]["target"] == 200000 and {o["type"] for o in result_["options"]} == {"existing_balance", "new_deposits"}
    assert all("details" not in o for o in result_["options"])
    text = str(writes)
    for hidden in ("888888", "חתונה של אבי", "recFPavi", "recGX"):
        assert hidden not in text, hidden
    assert not any(k in text for k in ("score", "recommended", "rank"))                          # a record of a decision, not advice


def test_funding_save_rejects_unknown_infeasible_or_empty_selection_and_foreign_goals():
    seed_saved_plans()
    for selected in ([], ["nope"], ["dep", "dep"], [7]):
        assert start_save(selected).state == "clarify", selected
    request_, plan_ = funding_plan_for({"goal_id": "recGW", "options": [DEPOSIT]})
    next(o for o in plan_["goals"][0]["options"] if o["id"] == "dep")["feasible"] = False
    assert conv.start_funding_plan_save(ELIYAHU, request_, plan_, ["dep"], today=TODAY).state == "clarify"
    request_, plan_ = funding_plan_for({"goal_id": "recGW", "options": [DEPOSIT]})
    plan_["goals"][0]["need"]["goal_id"] = "recGX"                                                # a goal that is not the caller's own
    assert conv.start_funding_plan_save(ELIYAHU, request_, plan_, ["dep"], today=TODAY).state == "denied"


def test_funding_save_needs_exactly_one_computable_goal():
    seed_saved_plans()
    DB[Tables.FIN_GOALS] = DB[Tables.FIN_GOALS] + [goal("recGN", "בלי תאריך", ELI, 5000, **{GF.CATEGORY: "savings"})]
    request_, plan_ = funding_plan_for({"goal_ids": ["recGW", "recGN"]})
    assert conv.start_funding_plan_save(ELIYAHU, request_, plan_, ["existing"], today=TODAY).state == "clarify"
    request_, plan_ = funding_plan_for({"goal_id": "recGN"})
    assert conv.start_funding_plan_save(ELIYAHU, request_, plan_, ["existing"], today=TODAY).state == "clarify"


def test_funding_plans_table_policy_is_owner_scoped_and_the_write_is_allowlisted():
    seed_saved_plans()
    own = {FPF.GOAL: ["recGW"], FPF.NAME: "x", FPF.STATUS: "chosen"}
    stamped = policy.scope_new_record_fields(Tables.FUNDING_PLANS, dict(own), ELIYAHU)
    assert stamped[FPF.FINANCIAL_OWNER] == [ELI]
    with pytest.raises(policy.PersonalDataAccessDenied):
        policy.scope_new_record_fields(Tables.FUNDING_PLANS, {**own, FPF.GOAL: ["recGX"]}, ELIYAHU)
    with pytest.raises(policy.PersonalDataAccessDenied):
        policy.scope_new_record_fields(Tables.FUNDING_PLANS, {**own, FPF.GOAL: ["recGW", "recGE"]}, ELIYAHU)     # a single goal only
    assert [r["id"] for r in service.my_funding_plans(ELIYAHU)] == ["recFPold", "recFPdone"]
    assert [r["id"] for r in service.my_funding_plans(AVI_I)] == ["recFPavi"]
    assert "Funding Plans" in approval_actions._TMA_WRITE_ALLOWED_TABLES


def test_http_funding_save_gate_validation_and_review(monkeypatch):
    import copy as _copy
    monkeypatch.setattr(tma_api, "_PL_LIMITER", None)                                                 # this test makes more calls than one minute allows
    seed_saved_plans()

    def save(c, body=None, raw=None):
        import json as _json
        return c.post("/api/fcc/funding/plan/save", data=raw if raw is not None else _json.dumps(body if body is not None else {}),
                      headers={**H, "Content-Type": "application/json"})
    assert save(http(monkeypatch, ELIYAHU, flag=False), {"goal_id": "recGW", "selected": ["dep"]}).status_code == 404
    assert save(http(monkeypatch, AVI_I), {"goal_id": "recGW", "selected": ["dep"]}).status_code == 404
    assert http(monkeypatch, ELIYAHU).options("/api/fcc/funding/plan/save").status_code == 204
    c = http(monkeypatch, ELIYAHU)
    assert save(c, raw="not json").status_code == 400
    assert save(c, {"goal_id": "recGW", "options": [DEPOSIT]}).status_code == 400                    # selected required
    r = save(c, {"goal_id": "recGX", "selected": ["existing"]})
    assert r.status_code == 400 and "888888" not in str(r.get_json())                              # another owner's goal
    before = _copy.deepcopy(DB)
    r = save(c, {"goal_id": "recGW", "options": [DEPOSIT], "selected": ["dep"]})
    body = r.get_json()
    assert r.status_code == 200 and body["state"] == "review" and "שמירת תוכנית מימון" in body["message"]
    assert DB == before
    for method in ("get", "put", "patch", "delete"):
        assert getattr(c, method)("/api/fcc/funding/plan/save", headers=H).status_code == 405
