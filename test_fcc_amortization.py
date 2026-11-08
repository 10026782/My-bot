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
    assert [r[5] for r in s.rows] == [1, 1, 0, 0] and A.remaining(s.rows) == {"payments": 2, "interest": 9.0, "principal": 600.0, "total": 609.0}
    broken = [UPCOMING[0], (3, 600.0, 300.0, 6.0, 306.0, 300.0), (4, 300.0, 100.0, 3.0, 103.0, 200.0)]   # the principals do not add up to the opening balance
    assert not A.parse_sheets([CHARGED, broken]).ok
    assert not A.parse_sheets([[("x",)]]).ok


def test_stored_form_roundtrip_and_garbage_is_ignored():
    s = _parsed()
    rows = A.loads(A.dumps(s))
    assert rows == s.rows
    from datetime import date as D
    assert A.asof(A.dumps(s, D(2026, 11, 8))) == D(2026, 11, 8) and A.asof("") is None and A.asof(A.dumps(s)) == D.today()
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


def _frag(page, x, y, text):
    from core.financial_control.card_import import Fragment
    return Fragment(page, x, y, text, x + 10)


def _cal(rows, amount="3000", count="3"):
    fr = [_frag(1, 200, 288.4, f'ש"ח {amount}'), _frag(1, 466, 288.4, "סכום ההלוואה"), _frag(1, 236, 308.1, count), _frag(1, 470, 308.1, "מס' תשלומים")]
    for k, (bal, intr, princ, tot, d, no) in enumerate(rows):
        y = 226.0 + 20 * k
        fr += [_frag(2, 75, y, str(bal)), _frag(2, 150, y, str(intr)), _frag(2, 237, y, str(princ)), _frag(2, 300, y, str(tot)), _frag(2, 383, y, d), _frag(2, 460, y, str(no))]
    return fr


def test_cal_letter_follows_the_balance_when_the_printed_split_is_off():
    rows = [(2010.0, 30.0, 990.0, 1020.0, "02/10/2026", 1), (1006.0, 20.0, 1004.0, 1024.0, "02/11/2026", 2), (0, 10.0, 1006.0, 1016.0, "02/12/2026", 3)]
    s = A.parse_cal_fragments(_cal(rows), date(2026, 11, 8))
    assert s.ok, s.problems
    assert [r[5] for r in s.rows] == [1, 1, 0] and s.original == 3000.0 and s.payment_now == 1024.0
    assert s.rows[1][1] == 1004.0 and s.rows[1][2] == 20.0                 # principal = the fall of the balance, interest = the rest of the payment
    off = [rows[0], (1000.0, 20.0, 1004.0, 1024.0, "02/11/2026", 2), rows[2]]      # printed principal 1004 vs the balance's fall 1010: within the tolerance, noted
    s2 = A.parse_cal_fragments(_cal(off), date(2026, 11, 8))
    assert s2.ok and s2.rows[1][1] == 1010.0 and s2.notes
    bad = [rows[0], (1500.0, 20.0, 1004.0, 1024.0, "02/11/2026", 2), rows[2]]          # a balance far from the printed principal: refused
    assert not A.parse_cal_fragments(_cal(bad), date(2026, 11, 8)).ok
    assert not A.parse_cal_fragments(_cal(rows, count="4"), date(2026, 11, 8)).ok             # the letter says 4 payments, the table has 3
    assert not A.parse_cal_fragments(_cal(rows[:2]), date(2026, 11, 8)).ok                     # the balance does not reach 0


def _annuity(balance, rate, n, start=date(2026, 9, 15), charged=2):
    """A clean annuity schedule: `charged` payments dated up to Oct 2026, the rest after."""
    pay = round(A._pmt(balance, rate, n), 2)
    rows, bal = [], balance
    for k in range(n):
        idx = start.year * 12 + start.month - 1 + k
        d = date(idx // 12, idx % 12 + 1, 15)
        i = round(bal * rate / 1200, 2)
        pr = round(bal, 2) if k == n - 1 else round(pay - i, 2)
        tot = round(pr + i, 2)
        bal = round(bal - pr, 2)
        rows.append([d.isoformat(), pr, i, tot, bal, 1 if k < charged else 0, 1])
    return rows


def test_reproject_keeps_charged_months_and_follows_the_new_prime():
    rows = _annuity(12000, 6.0, 12)
    today = date(2026, 11, 8)
    same = A.reproject(rows, 0.0, today)
    assert same[:2] == rows[:2]                                             # charged months untouched
    assert all(abs(a[3] - b[3]) < 0.1 and abs(a[4] - b[4]) < 0.5 for a, b in zip(same, rows))      # no change in prime: the same schedule
    down = A.reproject(rows, -0.5, today)
    assert [r[0] for r in down] == [r[0] for r in rows] and down[-1][4] == 0.0       # same dates, same end, balance reaches 0
    assert down[2][3] < rows[2][3] and down[2][2] < rows[2][2] and down[2][1] > rows[2][1]     # lower prime: smaller payment, less interest, MORE principal
    up = A.reproject(rows, 1.0, today)
    assert up[2][3] > rows[2][3] and up[2][2] > rows[2][2]
    assert A.reproject(rows, -9.0, today) is None and A.reproject(rows[:2], 0.5, today) is None
    assert A.unpack(A.pack("x" * 500)) == "x" * 500 and A.unpack("not base64!") is None


def test_prime_change_writes_project_the_stored_schedule_again():
    from core.financial_control import draft as D, loans as L
    rows = _annuity(12000, 6.0, 12)
    s = A.Schedule(ok=True, rows=rows)
    rec = {"id": "recS", "fields": {"Loan Name/ID": "מקס", "Active Loan": True, "Outstanding Principal for Early Closure": 10000, "Interest Rate (%)": 6, "Current Monthly Payment": rows[3][3],
                                    "Payments Remaining": 10, "Amortization Schedule": A.dumps(s, date(2026, 10, 1))}}
    plain = {"id": "recT", "fields": {"Loan Name/ID": "בלי לוח", "Active Loan": True, "Outstanding Principal for Early Closure": 10000, "Interest Rate (%)": 6, "Current Monthly Payment": 900, "Payments Remaining": 12}}
    prime = L.prime_rows([rec, plain], date(2026, 11, 8))
    assert prime[0]["schedule"] and prime[1]["schedule"] is None
    writes = D.prime_change_writes({"delta": -0.5}, {"prime_rows": prime, "today": "2026-11-08"})
    with_schedule = next(w for w in writes if w["record_id"] == "recS")["fields"]
    without = next(w for w in writes if w["record_id"] == "recT")["fields"]
    assert "Amortization Schedule" not in without
    new_rows = A.loads(with_schedule["Amortization Schedule"])
    assert new_rows[:2] == rows[:2] and A.asof(with_schedule["Amortization Schedule"]) == date(2026, 11, 8)
    assert with_schedule["Current Monthly Payment"] == new_rows[2][3] < rows[2][3] and "לוח הסילוקין חושב מחדש" in with_schedule["Notes"]


def test_annuity_rows_is_one_correct_formula():
    rows = A.annuity_rows(12000.0, 6.0, 12, date(2026, 12, 10))
    assert len(rows) == 12 and rows[0][0] == "2026-12-10" and rows[-1][0] == "2027-11-10" and rows[-1][4] == 0.0
    assert rows[0][3] == 1032.8 and rows[0][2] == 60.0 and rows[0][1] == 972.8                          # 12000 at 6% over 12 months: 1,032.80, 60.00 of it interest
    assert abs(sum(r[2] for r in rows) - 393.6) < 0.2 and abs(sum(r[1] for r in rows) - 12000.0) < 0.01
    assert A.annuity_rows(0, 6.0, 12, date(2026, 12, 10)) == [] and A.annuity_rows(1000, 6.0, 0, date(2026, 12, 10)) == []
    zero = A.annuity_rows(1200.0, 0.0, 12, date(2026, 12, 10))
    assert all(r[3] == 100.0 and r[2] == 0.0 for r in zero)


if __name__ == "__main__":
    test_parse_dates_future_rows_and_checks(); test_stored_form_roundtrip_and_garbage_is_ignored()
    test_match_loan_by_amount_and_payment(); test_cal_letter_follows_the_balance_when_the_printed_split_is_off(); test_reproject_keeps_charged_months_and_follows_the_new_prime(); test_prime_change_writes_project_the_stored_schedule_again(); test_loan_item_uses_the_schedule_and_cashflow_uses_its_months(); print("ok amortization")
