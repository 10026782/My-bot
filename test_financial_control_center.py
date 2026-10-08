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
    monkeypatch.setattr(conv, "LlmExtractor", lambda: ex)
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
    monkeypatch.setattr(conv, "LlmExtractor", lambda: ex)
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
    monkeypatch.setattr(conv, "LlmExtractor", lambda: ex)
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
    monkeypatch.setattr(conv, "LlmExtractor", lambda: ex)
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
    monkeypatch.setattr(conv, "LlmExtractor", lambda: ex)
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
    monkeypatch.setattr(conv, "LlmExtractor", lambda: ex)
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


def test_invalid_structured_intent_falls_back_to_the_classifier(monkeypatch):
    from core.financial_control import classifier
    calls = []
    monkeypatch.setattr(classifier, "classify", lambda text, titles, today=None: calls.append(text) or None)
    monkeypatch.setattr(fchat.gate, "enabled_for", lambda identity: True)
    _level_world(3000)
    fchat.start_turn(ELIYAHU, "x", intent={"action": "bogus"})
    assert calls == ["x"]


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
    intent("monthly.income", "recGI")
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
    assert conv.handle_turn(ELIYAHU, "שילמתי 500", extractor=ex, today=TODAY, scope="monthly").state != "info"


def test_scope_does_not_block_answering_an_open_draft():
    seed_intents()
    intent("monthly.income", "recGI")
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
    monkeypatch.setattr(conv.LlmExtractor, "fill", lambda self, text, awaiting, fields, entity, today:
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
