"""FCC loan amortization schedules (לוח סילוקין) — pure parser + reader. No I/O, no writes, no network, no model.

Input: the Excel export of a card-company / bank loan schedule: a sheet of CHARGED payments (paid on, opening principal, principal paid, interest paid,
prime, total, balance) and a sheet of NOT-YET-CHARGED payments (payment number, opening, principal, interest, total, balance). Output: one row per payment
with its exact interest / principal split, stored compactly on the loan (``Loans."Amortization Schedule"``) so the loans tab shows the REAL split instead of
the balance × rate estimate (a schedule front-loads the interest; a prime-linked loan changes monthly).

Iron rules: a schedule is trusted only if it adds up (the not-yet-charged principals sum to the first opening balance and the last balance is 0, each row's
balance follows from its opening and principal); otherwise it is rejected whole, never repaired. Not-yet-charged rows carry no date in the export — theirs are
DERIVED month by month after the last charged payment (flagged), never typed. No account / card number is read or stored.
"""

from __future__ import annotations

import io
import json
from dataclasses import dataclass, field
from datetime import date, datetime

_TOL = 0.06                      # rounding tolerance per row (₪)
_SUM_TOL = 1.0                   # tolerance of the whole-schedule principal sum (₪)
MAX_ROWS = 600


@dataclass
class Schedule:
    ok: bool = False
    problems: list[str] = field(default_factory=list)
    rows: list[list] = field(default_factory=list)       # [iso date, principal, interest, total, balance after, charged(1)/upcoming(0), dated(1)/derived(0)]
    original: float | None = None                         # the opening balance of the first charged payment (= the loan amount)
    payment_now: float | None = None                      # the last charged payment's total
    notes: list[str] = field(default_factory=list)


def _num(v) -> float | None:
    if v is None or isinstance(v, bool):
        return None
    try:
        return float(str(v).replace(",", "").strip())
    except ValueError:
        return None


def _date(v) -> date | None:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v)[:10]) if v else None
    except ValueError:
        return None


def _plus_months(d: date, k: int) -> date:
    idx = d.year * 12 + d.month - 1 + k
    year, month = idx // 12, idx % 12 + 1
    import calendar
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def parse_workbook(data: bytes) -> Schedule:
    try:
        import openpyxl
    except ImportError:
        return Schedule(problems=["קריאת Excel אינה זמינה בשרת הזה"])
    try:
        wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True, read_only=True)
        sheets = [[tuple(r) for r in ws.iter_rows(values_only=True)] for ws in wb.worksheets]
    except Exception:                                    # noqa: BLE001 — a corrupt file is a refusal, not a crash
        return Schedule(problems=["הקובץ אינו קובץ Excel תקין"])
    return parse_sheets(sheets)


def _is_header(row: tuple, word: str) -> bool:
    return bool(row) and isinstance(row[0], str) and word in row[0]


def parse_sheets(sheets: list[list[tuple]]) -> Schedule:
    charged_rows: list[tuple] = []
    upcoming_rows: list[tuple] = []
    for rows in sheets:
        if not rows:
            continue
        head = rows[0]
        if _is_header(head, "שולם"):
            charged_rows = [r for r in rows[1:] if r and _date(r[0])]
        elif _is_header(head, "תשלום"):
            upcoming_rows = [r for r in rows[1:] if r and _num(r[0]) is not None]
    out = Schedule()
    if not charged_rows and not upcoming_rows:
        out.problems.append("לא נמצא לוח תשלומים (גיליון ״תשלומים שחויבו״ / ״תשלומים שטרם חויבו״)")
        return out
    if len(charged_rows) + len(upcoming_rows) > MAX_ROWS:
        out.problems.append("הלוח ארוך מדי")
        return out
    last_date: date | None = None
    for r in charged_rows:
        d, opening, princ, intr, total, bal = _date(r[0]), _num(r[1]), _num(r[2]), _num(r[3]), _num(r[5]), _num(r[6])
        if None in (d, opening, princ, intr, total, bal):
            out.problems.append("שורה ששולמה אינה קריאה")
            return out
        if abs(princ + intr - total) > _TOL:
            out.problems.append(f"שורה ששולמה ב-{d.isoformat()} אינה מתיישבת")
            return out
        if abs(opening - princ - bal) > _TOL:             # a payment that also cleared accrued interest: the balance is the truth, the split follows from it
            princ = round(opening - bal, 2)
            intr = round(total - princ, 2)
            note = "בשורות ששולמו שבהן היתרה לא ירדה בגובה ה״קרן״ שבקובץ (למשל תשלום משלים) הקרן חושבה מירידת היתרה"
            if note not in out.notes:
                out.notes.append(note)
        out.rows.append([d.isoformat(), round(princ, 2), round(intr, 2), round(total, 2), round(bal, 2), 1, 1])
        last_date = d
    if charged_rows:
        out.original = _num(charged_rows[0][1])
        out.payment_now = round(_num(charged_rows[-1][5]) or 0, 2) or None
    if upcoming_rows:
        if last_date is None:
            out.problems.append("אין תשלום ששולם — אי אפשר לתארך את התשלומים הבאים")
            return out
        first_opening = _num(upcoming_rows[0][1])
        princ_sum = 0.0
        for k, r in enumerate(upcoming_rows, start=1):
            opening, princ, intr, total, bal = _num(r[1]), _num(r[2]), _num(r[3]), _num(r[4]), _num(r[5])
            if None in (opening, princ, intr, total, bal):
                out.problems.append("שורה עתידית אינה קריאה")
                return out
            if abs(opening - princ - bal) > _TOL or abs(princ + intr - total) > _TOL:
                out.problems.append(f"תשלום {int(_num(r[0]))} אינו מתיישב")
                return out
            princ_sum += princ
            out.rows.append([_plus_months(last_date, k).isoformat(), round(princ, 2), round(intr, 2), round(total, 2), round(bal, 2), 0, 0])
        if first_opening is None or abs(princ_sum - first_opening) > _SUM_TOL:
            out.problems.append("סכום הקרן העתידי אינו שווה ליתרה הפותחת")
            return out
        if abs(out.rows[-1][4]) > _TOL:
            out.problems.append("היתרה בסוף הלוח אינה אפס")
            return out
        out.notes.append("תאריכי התשלומים העתידיים נגזרים מחודש לחודש אחרי התשלום האחרון ששולם")
    out.ok = True
    return out


# ── stored form ───────────────────────────────────────────────────────────────────────────────────────────────────
def dumps(s: Schedule) -> str:
    return json.dumps({"v": 1, "rows": s.rows}, separators=(",", ":"))


def loads(text) -> list[list] | None:
    """The stored rows, or None when the field is empty / not ours / malformed (a broken schedule is ignored, never half-used)."""
    if not text or not isinstance(text, str):
        return None
    try:
        obj = json.loads(text)
        rows = obj["rows"] if isinstance(obj, dict) and obj.get("v") == 1 else None
        if not rows or not all(isinstance(r, list) and len(r) == 7 and _date(r[0]) for r in rows):
            return None
        return rows
    except (ValueError, KeyError, TypeError):
        return None


def month_split(rows: list[list], year: int, month: int) -> dict | None:
    """Interest / principal / total of ONE month (all payments dated in it) and the balance after the month's last payment; None = no payment that month."""
    hit = [r for r in rows if (d := _date(r[0])) and d.year == year and d.month == month]
    if not hit:
        return None
    return {"principal": round(sum(r[1] for r in hit), 2), "interest": round(sum(r[2] for r in hit), 2),
            "total": round(sum(r[3] for r in hit), 2), "balance_after": hit[-1][4], "charged": all(r[5] for r in hit)}


def last_date(rows: list[list]) -> date | None:
    return _date(rows[-1][0]) if rows else None


def remaining(rows: list[list]) -> dict:
    """What the not-yet-charged part of the schedule still costs: payments left, interest, principal."""
    up = [r for r in rows if not r[5]]
    return {"payments": len(up), "interest": round(sum(r[2] for r in up), 2), "principal": round(sum(r[1] for r in up), 2)}


def match_loan(s: Schedule, loans: list[dict]) -> list[dict]:
    """The owner's loans this schedule can belong to: same original amount (the first opening balance) AND same current payment; if no loan agrees on both,
    those that agree on the amount alone. Several candidates = the owner chooses (never a silent pick)."""
    def f(rec):
        return rec.get("fields") or {}
    amt, pay = s.original, s.payment_now
    if amt is None:
        return []
    by_amount = [r for r in loans if (a := _num(f(r).get("Loan Amount"))) is not None and abs(a - amt) < 1]
    both = [r for r in by_amount if pay is not None and (p := _num(f(r).get("Current Monthly Payment"))) is not None and abs(p - pay) < 1]
    return both or by_amount
