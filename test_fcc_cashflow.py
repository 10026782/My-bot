"""FCC cashflow — ``core.financial_control.cashflow`` (pure, read-only). No Airtable, no Flask, no network.

Covers: month windows, income per source (standing / recorded / general), unknown != 0, expenses by category (uncategorized apart,
refunds), loans as an expense (recorded beats scheduled, scheduled only for the current month, never both), obligations never added,
month-over-month change, category spikes, large items, and that the module has no I/O.
"""

from __future__ import annotations

import ast
from datetime import date
from pathlib import Path

from core.financial_control import cashflow as cf
from core.financial_control.cashflow import GENERAL_SOURCE, IncomeSource, Txn

TODAY = date(2026, 10, 20)


def T(amount, y, m, d, cat=None, label="", ref=None):
    return Txn(amount, date(y, m, d), cat, ref, label)


def row(view, key):
    return next(r for r in view["months"] if r["month"] == key)


def test_month_windows_cross_year_and_clamp():
    w = cf.month_windows(date(2026, 2, 10), 4)
    assert [k for k, _, _ in w] == ["2025-11", "2025-12", "2026-01", "2026-02"]
    assert w[-1][2] == date(2026, 2, 28)
    assert len(cf.month_windows(TODAY, 0)) == 1 and len(cf.month_windows(TODAY, 999)) == 36


def test_category_list_has_owner_categories_and_keys_resolve():
    labels = [l for _, l in cf.EXPENSE_CATEGORIES]
    for want in ("מחייה", "תקשורת", "הלוואות", "עסק", "הוצאות בית", "מוסדות", "תחבורה", "תרומות", "ביגוד והנעלה", "ביטוחים"):
        assert want in labels
    assert cf.category_key("מחייה") == "living" and cf.category_key("living") == "living"
    assert cf.category_key({"name": "transport"}) == "transport"
    assert cf.category_key("???") == cf.UNCATEGORIZED and cf.category_key(None) == cf.UNCATEGORIZED


def test_income_by_source_standing_recorded_and_general():
    work = IncomeSource("נוף הגליל", cf.FIXED, fixed_monthly=8000.0, fixed_since=date(2026, 9, 1))
    trips = IncomeSource("נסיעות", cf.VARIABLE,
                         gross=(T(3000, 2026, 10, 5), T(1500, 2026, 10, 12)), direct_costs=(T(400, 2026, 10, 6),))
    other = IncomeSource(GENERAL_SOURCE, cf.GENERAL, gross=(T(700, 2026, 10, 9),))
    v = cf.build([work, trips, other], [], TODAY, months=3)
    oct_ = row(v, "2026-10")["income"]
    assert [s["name"] for s in oct_["sources"]] == ["נוף הגליל", "נסיעות", "כללי"]
    assert (oct_["gross"], oct_["direct_costs"], oct_["net"]) == (13200.0, 400.0, 12800.0)
    assert row(v, "2026-09")["income"]["gross"] == 8000.0          # standing only
    assert row(v, "2026-08")["income"]["known"] is False and row(v, "2026-08")["income"]["net"] is None   # before fixed_since: unknown, not 0


def test_recorded_entry_replaces_standing_never_adds():
    work = IncomeSource("נוף הגליל", cf.FIXED, gross=(T(8200, 2026, 10, 1),), fixed_monthly=8000.0)
    assert row(cf.build([work], [], TODAY, 1), "2026-10")["income"]["gross"] == 8200.0


def test_unknown_is_not_zero_balance_needs_both_sides():
    inc = IncomeSource("נסיעות", gross=(T(5000, 2026, 9, 3),))
    v = cf.build([inc], [T(2000, 2026, 8, 2, "living")], TODAY, months=3)
    sep, aug = row(v, "2026-09"), row(v, "2026-08")
    assert sep["balance"] is None and sep["missing"] == ["expenses"]
    assert aug["balance"] is None and aug["missing"] == ["income"]
    assert row(v, "2026-10")["missing"] == ["income", "expenses"]


def test_expenses_by_category_uncategorized_apart_and_refund_reduces():
    ex = [T(1000, 2026, 9, 3, "living"), T(300, 2026, 9, 4, "מחייה"), T(-100, 2026, 9, 5, "living"),
          T(250, 2026, 9, 6, "transport"), T(90, 2026, 9, 7, None), T(40, 2026, 9, 8, "bogus")]
    inc = IncomeSource("x", gross=(T(9000, 2026, 9, 1),))
    sep = row(cf.build([inc], ex, TODAY, 2), "2026-09")
    cats = {c["key"]: c["amount"] for c in sep["expenses"]["categories"]}
    assert cats == {"living": 1200.0, "transport": 250.0, "uncategorized": 130.0}
    assert sep["expenses"]["total"] == 1580.0 and sep["balance"] == 7420.0 and sep["surplus"] == 7420.0 and sep["shortfall"] == 0.0
    assert [c["key"] for c in sep["expenses"]["categories"]] == ["living", "transport", "uncategorized"]   # fixed display order


def test_shortfall_when_expenses_exceed_income():
    inc = IncomeSource("x", gross=(T(5000, 2026, 9, 1),))
    sep = row(cf.build([inc], [T(6500, 2026, 9, 2, "home")], TODAY, 2), "2026-09")
    assert sep["balance"] == -1500.0 and sep["shortfall"] == 1500.0 and sep["surplus"] == 0.0


def test_loans_recorded_beats_scheduled_scheduled_only_current_month():
    ex = [T(2300, 2026, 9, 10, "loans")]                              # September loan charge recorded
    v = cf.build([], ex, TODAY, months=3, loans_scheduled_monthly=2500.0)
    sep, octo, aug = row(v, "2026-09"), row(v, "2026-10"), row(v, "2026-08")
    assert sep["expenses"]["categories"][0] == {"key": "loans", "label": "הלוואות", "amount": 2300.0, "basis": "recorded"}
    assert octo["expenses"]["categories"][0]["amount"] == 2500.0 and octo["expenses"]["categories"][0]["basis"] == "scheduled"
    assert aug["expenses"]["known"] is False                          # a past month with nothing recorded stays unknown


def test_loans_scheduled_never_added_on_top_of_a_recorded_charge():
    ex = [T(2400, 2026, 10, 2, "loans")]
    octo = row(cf.build([], ex, TODAY, 1, loans_scheduled_monthly=2500.0), "2026-10")
    assert octo["expenses"]["total"] == 2400.0 and octo["expenses"]["categories"][0]["basis"] == "recorded"


def test_obligations_are_never_part_of_the_expense_total():
    sig = cf.build.__code__.co_varnames[:cf.build.__code__.co_argcount]
    assert "obligations" not in sig


def test_partial_current_month_flag():
    v = cf.build([], [T(10, 2026, 10, 1, "living")], TODAY, 2)
    cur = row(v, "2026-10")
    assert cur["is_current"] and cur["partial"] and cur["day"] == 20 and cur["days_in_month"] == 31
    assert not row(v, "2026-09")["partial"]


def _monthly(cat, amounts):
    ys = [(2026, 6), (2026, 7), (2026, 8), (2026, 9), (2026, 10)]
    return [T(a, y, m, 5, cat) for a, (y, m) in zip(amounts, ys) if a is not None]


def test_category_changes_between_last_two_complete_months():
    ex = _monthly("living", [3000, 3000, 3000, 3000, 500]) + _monthly("transport", [None, None, None, 1000, None])
    ex += [T(900, 2026, 8, 5, "transport")]
    v = cf.build([], ex, TODAY, 5)
    ch = v["insights"]["changes"]
    assert (ch["from"], ch["to"]) == ("2026-08", "2026-09")          # the current month is never compared
    by = {i["key"]: i for i in ch["items"]}
    assert "living" not in by                                        # unchanged -> below MIN_CHANGE, not listed
    assert by["transport"]["before"] == 900.0 and by["transport"]["after"] == 1000.0 and by["transport"]["delta"] == 100.0
    assert ch["total_delta"] == 100.0


def test_changes_need_two_known_complete_months_and_skip_unknown():
    assert cf.build([], [T(100, 2026, 9, 1, "living")], TODAY, 3)["insights"]["changes"] is None
    ex = [T(3000, 2026, 7, 1, "living"), T(5000, 2026, 9, 1, "living")]          # August unknown
    ch = cf.build([], ex, TODAY, 4)["insights"]["changes"]
    assert (ch["from"], ch["to"]) == ("2026-07", "2026-09") and ch["items"][0]["delta"] == 2000.0   # unknown month is skipped, not 0


def test_category_spike_vs_own_baseline_and_no_false_positive():
    ex = _monthly("leisure", [500, 500, 500, 500, 1500]) + _monthly("living", [3000, 3000, 3000, 3000, 3100])
    sp = cf.build([], ex, TODAY, 5)["insights"]["spikes"]
    assert [(s["key"], s["month"], s["excess"]) for s in sp] == [("leisure", "2026-10", 1000.0)]
    assert sp[0]["partial"] is True


def test_spike_needs_baseline_history():
    ex = _monthly("leisure", [None, None, None, 500, 5000])
    assert cf.build([], ex, TODAY, 5)["insights"]["spikes"] == []


def test_large_items_floor_and_median_rule():
    ex = [T(200, 2026, 9, d, "living", f"s{d}") for d in (1, 2, 3, 4)] + [T(2500, 2026, 9, 9, "living", "מקרר", "recBig")]
    ex += [T(1200, 2026, 9, 10, "health", "שיניים", "recDent"), T(300, 2026, 9, 11, "leisure", "x")]
    items = cf.build([], ex, TODAY, 3)["insights"]["large_items"]
    assert [i["ref"] for i in items] == ["recBig", "recDent"] and items[0]["category"] == "מחייה"


def test_pure_module_has_no_io_imports():
    tree = ast.parse(Path(cf.__file__).read_text(encoding="utf-8"))
    imported = {n.names[0].name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import)}
    imported |= {(n.module or "").split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert imported <= {"__future__", "calendar", "dataclasses", "datetime", "statistics"}, imported
