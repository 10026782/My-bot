"""D1 step 6: ``deposit`` account events join the deposit roll-ups (one_time ∪ deposit) and nothing else.
Regression: with no ``deposit`` events every number is exactly what #1315 produced. Pure, no network."""

from __future__ import annotations

import os

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-fcc-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:FCC_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patFccTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appFccTest")
os.environ.setdefault("ELIYAHU_CHAT_ID", "1")

from datetime import date

from airtable_schema import FinEventFields as EF, FinGoalFields as GF
from core.financial_control import accounts as acc, calc, service

E = calc.Event
TODAY = date(2026, 10, 14)
PLAN = [E(calc.MONTHLY_RECURRING, 1000, date(2026, 1, 1))]


def rec(eid, kind, amount, day, goal="recG", **extra):
    f = {EF.KIND: kind, EF.AMOUNT: amount, EF.OCCURRED_AT: day}
    if goal:
        f[EF.GOAL] = [goal]
    f.update(extra)
    return {"id": eid, "fields": f}


def test_only_deposit_joined_event_kinds():
    assert calc.DEPOSIT in calc.EVENT_KINDS and calc.DEPOSIT_KINDS == (calc.ONE_TIME, calc.DEPOSIT)
    for k in ("withdrawal", "fee", "transfer", "balance_snapshot"):
        assert k not in calc.EVENT_KINDS


def test_parse_events_reads_deposit_but_still_skips_other_account_kinds():
    rows = [rec(f"r{k}", k, 100, "2026-10-01") for k in ("deposit", "withdrawal", "fee", "transfer", "balance_snapshot")]
    assert [e.kind for e in calc.parse_events(rows, EF)] == ["deposit"]


def test_history_without_deposit_events_is_identical_to_before():
    one = [E(calc.ONE_TIME, 1000, date(2026, 8, 3), ref="a"), E(calc.ONE_TIME, 500, date(2026, 9, 2), ref="b"),
           E(calc.ONE_TIME, 700, date(2026, 10, 1), ref="c"), E(calc.ONE_TIME, 999, date(2026, 10, 2), True, "d")]
    h = calc.deposit_history(one, PLAN, TODAY)
    assert (h["deposit_count"], h["streak"], h["last_deposit"]) == (3, 3, "2026-10-01")
    assert h["ytd"] == 2200.0 and h["monthly_average"] == 220.0
    assert calc.deposit_history(one + [E(calc.NOTE, 0, TODAY)], PLAN, TODAY) == h          # other kinds change nothing


def test_deposit_counts_in_history_status_and_month_with_one_time():
    ev = [E(calc.ONE_TIME, 400, date(2026, 10, 2), ref="a"), E(calc.DEPOSIT, 600, date(2026, 10, 5), ref="b"),
          E(calc.DEPOSIT, 250, date(2026, 9, 5), ref="c"), E(calc.DEPOSIT, 9, date(2026, 10, 6), True, "x"),
          E(calc.DEPOSIT, 77, date(2026, 12, 1), ref="future")]
    assert calc.deposits_in_month(ev, TODAY) == 1000.0
    st = calc.deposit_status(ev + PLAN, TODAY)
    assert (st["deposited_month"], st["deposited_last_month"], st["gap_month"]) == (1000.0, 250.0, 0.0)
    h = calc.deposit_history(ev, PLAN, TODAY)
    assert h["deposit_count"] == 3 and h["ytd"] == 1250.0 and h["streak"] == 2 and h["last_deposit"] == "2026-10-05"


def test_same_event_is_never_counted_twice():
    dup = [E(calc.DEPOSIT, 600, date(2026, 10, 5), ref="b"), E(calc.DEPOSIT, 600, date(2026, 10, 5), ref="b")]
    assert calc.deposits_in_month(dup, TODAY) == 600.0
    assert calc.deposit_history(dup, PLAN, TODAY)["deposit_count"] == 1
    assert calc.deposit_status(dup + PLAN, TODAY)["deposited_month"] == 600.0
    two = [E(calc.DEPOSIT, 600, date(2026, 10, 5), ref="b"), E(calc.DEPOSIT, 600, date(2026, 10, 5), ref="c")]   # distinct records
    assert calc.deposits_in_month(two, TODAY) == 1200.0


def test_deposit_is_not_goal_progress_or_income():
    goal = {"id": "recG", "fields": {GF.TITLE: "t", GF.STATUS: "active", GF.PERIOD_TYPE: "monthly",
                                     GF.TARGET_AMOUNT: 5000, GF.CALC_METHOD: "period_sum"}}
    base = [E(calc.ONE_TIME, 300, date(2026, 10, 2), ref="a")]
    with_dep = base + [E(calc.DEPOSIT, 4000, date(2026, 10, 3), ref="b")]
    assert calc.compute_goal(goal, with_dep, TODAY, GF) == calc.compute_goal(goal, base, TODAY, GF)


def test_recent_events_show_a_goal_linked_deposit_but_hide_an_unlinked_one():
    rows = [rec("rOne", "one_time", 50, "2026-10-01"), rec("rDep", "deposit", 700, "2026-10-05"),
            rec("rLoose", "deposit", 800, "2026-10-06", goal=None), rec("rSnap", "balance_snapshot", 500000, "2026-10-07"),
            rec("rWd", "withdrawal", 100, "2026-10-08"), rec("rTr", "transfer", 100, "2026-10-09"), rec("rFee", "fee", 5, "2026-10-10")]
    out = service.recent_progress_events(rows)
    assert [e[EF.KIND] for e in out] == ["deposit", "one_time"] and out[0]["goal_ids"] == ["recG"]


def test_deposit_does_not_change_the_consolidated_value():
    ACC = {"id": "recA", "fields": {"Name": "קרן", "Account Type": "study_fund", "Status": "active", "Financial Owner": ["recEli"]}}
    snap = {"id": "s", "fields": {EF.KIND: "balance_snapshot", EF.AMOUNT: 100000, EF.OCCURRED_AT: "2026-10-01",
                                  EF.ACCOUNT: ["recA"], EF.FINANCIAL_OWNER: ["recEli"]}}
    dep = {"id": "d", "fields": {EF.KIND: "deposit", EF.AMOUNT: 5000, EF.OCCURRED_AT: "2026-10-05", EF.GOAL: ["recG"],
                                 EF.ACCOUNT: ["recA"], EF.FINANCIAL_OWNER: ["recEli"]}}
    before = acc.accounts_overview([ACC], [snap], TODAY)["totals"]["consolidated_value"]
    after = acc.accounts_overview([ACC], [snap, dep], TODAY)
    assert after["totals"]["consolidated_value"] == before == 100000.0          # a deposit is a movement, never a second asset
    assert after["totals"]["estimated_value"] == 105000.0                       # only the labelled estimate moves
