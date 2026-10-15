"""D1 step 5 — ``core.financial_control.accounts.accounts_overview``: pure read model, facts vs estimates.

Security: other owners' rows are ignored even if passed in; free-text notes never leave the model.
Backward compatibility: not wired anywhere yet; goal-event kinds untouched; nothing is invented (None, never 0).
"""

from __future__ import annotations

import os
import pathlib
from datetime import date

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-overview-test")
os.environ.setdefault("TELEGRAM_TOKEN", "123456789:OVERVIEW_TEST_TOKEN")
os.environ.setdefault("AIRTABLE_API_KEY", "patOverviewTest")
os.environ.setdefault("AIRTABLE_BASE_ID", "appOverviewTest")
os.environ.setdefault("ELIYAHU_CHAT_ID", "1")

import pytest

from airtable_schema import FinAccountFields as AF
from airtable_schema import FinEventFields as EF
from core.financial_control import accounts as acc
from core.financial_control import calc

TODAY = date(2026, 10, 15)
ELI, DANA = "recEli", "recDana"


def account(rid, name="acc", owner=ELI, **f):
    return {"id": rid, "fields": {AF.NAME: name, AF.FINANCIAL_OWNER: [owner], AF.STATUS: "active", **f}}


def ev(rid, kind, amount, day, account_id, counter=None, owner=ELI, **f):
    fields = {EF.KIND: kind, EF.AMOUNT: amount, EF.OCCURRED_AT: day, EF.ACCOUNT: [account_id], EF.FINANCIAL_OWNER: [owner], **f}
    if counter:
        fields[EF.COUNTER_ACCOUNT] = [counter]
    return {"id": rid, "fields": fields}


A, B = account("recA", "pension", **{AF.ACCOUNT_TYPE: "pension", AF.HOLDER_NAMES: "Eli",
                                      AF.NOTES: "private note", AF.TAX_NOTES: "private tax note"}), account("recB", "brokerage")


def row(out, rid):
    return next(r for r in out["accounts"] if r["id"] == rid)


# ═══ facts: only dated snapshots make a balance ═══

def test_consolidated_value_is_the_sum_of_latest_snapshots_and_movements_never_change_it():
    events = [ev("s1", "balance_snapshot", 100000, "2026-06-30", "recA"), ev("s2", "balance_snapshot", 120000, "2026-09-30", "recA"),
              ev("s3", "balance_snapshot", 50000, "2026-09-30", "recB"),
              ev("d1", "deposit", 5000, "2026-10-05", "recA"), ev("w1", "withdrawal", 2000, "2026-10-06", "recB"),
              ev("f1", "fee", 100, "2026-10-07", "recA")]
    out = acc.accounts_overview([A, B], events, TODAY)
    assert row(out, "recA")["balance"]["value"] == 120000 and row(out, "recB")["balance"]["value"] == 50000
    assert out["totals"]["consolidated_value"] == 170000                     # fact: snapshots only
    assert out["totals"]["accounts_with_value"] == 2 and out["totals"]["accounts_without_snapshot"] == 0
    assert out["totals"]["oldest_snapshot"] == "2026-09-30"
    # the same events without any movement give the same fact
    assert acc.accounts_overview([A, B], events[:3], TODAY)["totals"]["consolidated_value"] == 170000


def test_superseded_and_future_snapshots_are_ignored():
    events = [ev("s1", "balance_snapshot", 100, "2026-06-30", "recA"),
              ev("s2", "balance_snapshot", 999, "2026-09-30", "recA", **{EF.SUPERSEDED_BY: "s3"}),
              ev("s4", "balance_snapshot", 777, "2026-12-31", "recA")]                     # future-dated
    bal = row(acc.accounts_overview([A], events, TODAY), "recA")["balance"]
    assert bal["value"] == 100 and bal["as_of"] == "2026-06-30"


def test_same_day_snapshots_resolve_deterministically_and_default_verification_is_self_reported():
    out = acc.accounts_overview([A], [ev("s1", "balance_snapshot", 1, "2026-09-30", "recA"),
                                      ev("s2", "balance_snapshot", 2, "2026-09-30", "recA")], TODAY)
    assert row(out, "recA")["balance"]["value"] == 2 and row(out, "recA")["balance"]["verification"] == "self_reported"
    assert out["totals"]["all_self_reported"] is True
    mixed = acc.accounts_overview([A, B], [ev("s1", "balance_snapshot", 1, "2026-09-30", "recA", **{EF.VERIFICATION: "statement"}),
                                           ev("s2", "balance_snapshot", 1, "2026-09-30", "recB")], TODAY)
    assert mixed["totals"]["all_self_reported"] is False and row(mixed, "recA")["balance"]["verification"] == "statement"


def test_nothing_is_invented_without_a_snapshot():
    out = acc.accounts_overview([A, B], [ev("d1", "deposit", 5000, "2026-10-05", "recA")], TODAY)
    assert row(out, "recA")["balance"] is None
    assert out["totals"]["consolidated_value"] is None and out["totals"]["estimated_value"] is None      # None, never 0
    assert out["totals"]["accounts_without_snapshot"] == 2 and out["totals"]["all_self_reported"] is None
    empty = acc.accounts_overview([], [], TODAY)
    assert empty["accounts"] == [] and empty["totals"]["consolidated_value"] is None


def test_closed_accounts_are_listed_but_not_in_the_totals():
    closed = account("recC", "old", **{AF.STATUS: "closed"})
    out = acc.accounts_overview([A, closed], [ev("s1", "balance_snapshot", 100, "2026-09-30", "recA"),
                                              ev("s2", "balance_snapshot", 900, "2026-09-30", "recC")], TODAY)
    assert row(out, "recC")["balance"]["value"] == 900
    assert out["totals"]["consolidated_value"] == 100 and out["totals"]["closed_accounts"] == 1


# ═══ estimates: separate, labelled, never added to the fact ═══

def test_estimate_adds_movements_after_the_snapshot_only_and_is_labelled():
    events = [ev("s1", "balance_snapshot", 1000, "2026-09-30", "recA"),
              ev("d0", "deposit", 7, "2026-09-30", "recA"),          # same day as the snapshot: ambiguous -> excluded
              ev("d1", "deposit", 500, "2026-10-01", "recA"), ev("w1", "withdrawal", 200, "2026-10-02", "recA"),
              ev("f1", "fee", 50, "2026-10-03", "recA"), ev("d2", "deposit", 9, "2026-10-20", "recA")]   # future -> excluded
    bal = row(acc.accounts_overview([A], events, TODAY), "recA")["balance"]
    assert bal["value"] == 1000
    assert bal["estimate"] == {"value": 1250.0, "movements_since": 250.0, "movement_count": 3, "label": "estimate"}


def test_transfer_nets_to_zero_and_is_neither_deposit_nor_withdrawal():
    events = [ev("s1", "balance_snapshot", 1000, "2026-09-30", "recA"), ev("s2", "balance_snapshot", 500, "2026-09-30", "recB"),
              ev("t1", "transfer", 300, "2026-10-02", "recA", counter="recB")]
    out = acc.accounts_overview([A, B], events, TODAY)
    assert row(out, "recA")["balance"]["estimate"]["value"] == 700 and row(out, "recB")["balance"]["estimate"]["value"] == 800
    assert out["totals"]["estimated_value"] == out["totals"]["consolidated_value"] == 1500    # no double counting
    assert row(out, "recA")["balance"]["value"] == 1000                                        # the fact did not move


# ═══ malformed rows are skipped and counted, never guessed ═══

@pytest.mark.parametrize("bad", [
    ev("x", "deposit", -5, "2026-10-01", "recA"), ev("x", "deposit", 0, "2026-10-01", "recA"),
    ev("x", "balance_snapshot", -1, "2026-10-01", "recA"), ev("x", "deposit", "abc", "2026-10-01", "recA"),
    ev("x", "deposit", 5, "not-a-date", "recA"), ev("x", "transfer", 5, "2026-10-01", "recA"),
    ev("x", "transfer", 5, "2026-10-01", "recA", counter="recA"), ev("x", "transfer", 5, "2026-10-01", "recA", counter="recGhost"),
    ev("x", "deposit", 5, "2026-10-01", "recGhost"),
    {"id": "x", "fields": {EF.KIND: "deposit", EF.AMOUNT: 5, EF.OCCURRED_AT: "2026-10-01", EF.FINANCIAL_OWNER: [ELI],
                            EF.ACCOUNT: ["recA", "recB"]}},                                  # Airtable allows several; the model refuses
    {"id": "x", "fields": {EF.KIND: "deposit", EF.AMOUNT: 5, EF.OCCURRED_AT: "2026-10-01", EF.FINANCIAL_OWNER: [ELI]}},   # no account
])
def test_malformed_events_are_skipped_and_counted(bad):
    out = acc.accounts_overview([A, B], [ev("s1", "balance_snapshot", 100, "2026-09-30", "recA"), bad], TODAY)
    assert out["skipped_events"] == 1 and row(out, "recA")["balance"]["estimate"]["movement_count"] == 0
    assert out["totals"]["consolidated_value"] == 100


def test_goal_events_and_unknown_kinds_are_not_ours():
    goal = {"id": "g", "fields": {EF.KIND: "one_time", EF.AMOUNT: 500, EF.OCCURRED_AT: "2026-10-01", EF.FINANCIAL_OWNER: [ELI]}}
    odd = {"id": "o", "fields": {EF.KIND: "dividend", EF.AMOUNT: 5, EF.OCCURRED_AT: "2026-10-01", EF.ACCOUNT: ["recA"], EF.FINANCIAL_OWNER: [ELI]}}
    out = acc.accounts_overview([A], [goal, odd], TODAY)
    assert out["skipped_events"] == 0 and row(out, "recA")["balance"] is None


# ═══ security ═══

def test_other_owners_rows_are_ignored_even_when_passed_in():
    dana = account("recD", "dana-fund", owner=DANA)
    events = [ev("s1", "balance_snapshot", 100, "2026-09-30", "recA"), ev("s2", "balance_snapshot", 9999, "2026-09-30", "recD", owner=DANA),
              ev("t1", "transfer", 50, "2026-10-02", "recA", counter="recD")]            # event of mine pointing at her account
    out = acc.accounts_overview([A, dana], events, TODAY, owner_id=ELI)
    assert [r["id"] for r in out["accounts"]] == ["recA"] and out["totals"]["consolidated_value"] == 100
    assert out["skipped_events"] == 1                                                  # the transfer to someone else's account
    assert "dana-fund" not in repr(out) and "9999" not in repr(out)


def test_free_text_notes_never_leave_the_model():
    out = acc.accounts_overview([A], [ev("s1", "balance_snapshot", 100, "2026-09-30", "recA", **{EF.NOTE: "פוליסה 1234"})], TODAY)
    text = repr(out)
    assert "private note" not in text and "private tax note" not in text and "פוליסה" not in text
    assert row(out, "recA")["holder_names"] == "Eli" and row(out, "recA")["account_type"] == "pension"


# ═══ backward compatibility ═══

def test_wired_only_into_the_read_only_accounts_view_and_goal_kinds_untouched():
    root = pathlib.Path(__file__).parent
    service_text = (root / "core/financial_control/service.py").read_text(encoding="utf-8")       # D1 step 7 / B1: the one read-only consumer
    assert service_text.count("financial_control import accounts") == 1 and "def accounts_view" in service_text
    for name in ("core/financial_control/conversation.py", "core/financial_control/draft.py",
                 "core/financial_control/chat.py", "tma_api.py", "app.py"):
        text = (root / name).read_text(encoding="utf-8")
        assert "financial_control.accounts" not in text and "import accounts" not in text, name
    assert set(acc.ACCOUNT_KINDS) & set(calc.EVENT_KINDS) == {"deposit"}      # only deposit, deliberately (D1 step 6)
    assert calc.parse_events([ev("s", "balance_snapshot", 5, "2026-10-01", "recA")], EF) == []
