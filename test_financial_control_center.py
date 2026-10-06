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
    for cat in ("savings", "debt"):
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
