"""FCC loan amortization schedules: parser, stored form, exact monthly split, match to a loan, cashflow months. Plain script."""
from datetime import date

from core.financial_control import amortization as A, loans as L

CHARGED = [("שולם בתאריך", "קרן", 'ע"ח קרן', 'ע"ח ריבית', "פריים", 'סה"כ לתשלום', "יתרה"),
           ("2026-09-15T00:00:00", 1000.0, 0, 10.0, 6, 10.0, 1000.0),
           ("2026-10-15T00:00:00", 1000.0, 400.0, 10.0, 6, 410.0, 600.0)]
UPCOMING = [("תשלום", "קרן", 'ע"ח הקרן', 'ע"ח ריבית', "סה״כ", "יתרה"),
            (3, 600.0, 300.0, 6.0, 306.0, 300.0), (4, 300.0, 300.0, 3.0, 303.0, 0.0)]


def _parsed():
    return A.parse_sheets([CHARGED, UPCOMING])


def test_parse_dates_future_rows_and_checks():
    s = _parsed()
    assert s.ok, s.problems
    assert s.original == 1000.0 and s.payment_now == 410.0
    assert [r[0] for r in s.rows] == ["2026-09-15", "2026-10-15", "2026-11-15", "2026-12-15"]
    assert [r[5] for r in s.rows] == [1, 1, 0, 0] and A.remaining(s.rows) == {"payments": 2, "interest": 9.0, "principal": 600.0}
    broken = [UPCOMING[0], (3, 600.0, 300.0, 6.0, 306.0, 300.0), (4, 300.0, 100.0, 3.0, 103.0, 200.0)]   # the principals do not add up to the opening balance
    assert not A.parse_sheets([CHARGED, broken]).ok
    assert not A.parse_sheets([[("x",)]]).ok


def test_stored_form_roundtrip_and_garbage_is_ignored():
    s = _parsed()
    rows = A.loads(A.dumps(s))
    assert rows == s.rows
    assert A.loads("") is None and A.loads("not json") is None and A.loads('{"v":2,"rows":[]}') is None
    assert A.month_split(rows, 2026, 11) == {"principal": 300.0, "interest": 6.0, "total": 306.0, "balance_after": 300.0, "charged": False}
    assert A.month_split(rows, 2027, 6) is None


def test_match_loan_by_amount_and_payment():
    s = _parsed()
    loans = [{"id": "a", "fields": {"Loan Amount": 1000, "Current Monthly Payment": 410}},
             {"id": "b", "fields": {"Loan Amount": 1000, "Current Monthly Payment": 99}},
             {"id": "c", "fields": {"Loan Amount": 5000, "Current Monthly Payment": 410}}]
    assert [r["id"] for r in A.match_loan(s, loans)] == ["a"]
    assert [r["id"] for r in A.match_loan(s, loans[1:2] + loans[2:])] == ["b"]      # nobody agrees on both: the amount alone, the owner chooses


def test_loan_item_uses_the_schedule_and_cashflow_uses_its_months():
    s = _parsed()
    rec = {"id": "x", "fields": {"Loan Name/ID": "x", "Active Loan": True, "Outstanding Principal for Early Closure": 600, "Interest Rate (%)": 6,
                                 "Current Monthly Payment": 410, "Amortization Schedule": A.dumps(s)}}
    item = L.loan_item(rec, date(2026, 11, 8))
    assert item["split_exact"] is True and item["interest_this_month"] == 6.0 and item["principal_this_month"] == 300.0 and item["balance_after_this_month"] == 300.0
    assert item["end_date"] == "2026-12-15" and item["end_date_inferred"] is True and item["schedule_remaining"]["payments"] == 2
    plain = L.loan_item({"id": "y", "fields": {k: v for k, v in rec["fields"].items() if k != "Amortization Schedule"}}, date(2026, 11, 8))
    assert plain["split_exact"] is False
    wins = [("2026-10", date(2026, 10, 1), date(2026, 10, 31)), ("2026-11", date(2026, 11, 1), date(2026, 11, 30)), ("2026-12", date(2026, 12, 1), date(2026, 12, 31)), ("2027-01", date(2027, 1, 1), date(2027, 1, 31))]
    totals, _u, _c = L.monthly_schedule([rec], wins, date(2026, 11, 8))
    assert totals == {"2026-10": 410.0, "2026-11": 306.0, "2026-12": 303.0, "2027-01": 0.0}, totals


if __name__ == "__main__":
    test_parse_dates_future_rows_and_checks(); test_stored_form_roundtrip_and_garbage_is_ignored()
    test_match_loan_by_amount_and_payment(); test_loan_item_uses_the_schedule_and_cashflow_uses_its_months(); print("ok amortization")
