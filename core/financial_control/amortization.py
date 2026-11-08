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

import base64
import io
import json
import re
import zlib
from dataclasses import dataclass, field
from datetime import date, datetime

_TOL = 0.06                      # rounding tolerance per row (₪)
_SUM_TOL = 1.0                   # tolerance of the whole-schedule principal sum (₪)
MAX_ROWS = 600
_CAL_TOL = 25.0                  # the most a printed principal may differ from the fall of the balance at a rate change (₪)
_CAL_NOTE = "בכמה תשלומים (בשינוי ריבית) הקרן והריבית שבמכתב שונות בשקלים בודדים מירידת היתרה — הפירוק חושב מירידת היתרה ומסכום התשלום"


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


# ── Cal (כאל) loan letter: a PDF with the FULL dated schedule ─────────────────────────────────────────────────────────
_DMY = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")
_NUM = re.compile(r"^-?\d+(?:\.\d+)?$")


def _cal_rows(fragments) -> list[tuple]:
    """(balance, interest, principal, total, date, no) per table row: the fragments of one printed line share a y; read left to right."""
    lines: dict[tuple, list] = {}
    for f in fragments:
        if f.page >= 2:
            lines.setdefault((f.page, round(f.y / 3)), []).append(f)
    rows = []
    for key in sorted(lines):
        cells = [c.text.strip() for c in sorted(lines[key], key=lambda c: c.x)]
        if len(cells) != 6 or not _DMY.match(cells[4]) or not all(_NUM.match(c) for c in (cells[0], cells[1], cells[2], cells[3], cells[5])):
            continue
        d, m, y = (int(x) for x in _DMY.match(cells[4]).groups())
        try:
            rows.append((float(cells[0]), float(cells[1]), float(cells[2]), float(cells[3]), date(y, m, d), int(cells[5])))
        except ValueError:
            continue
    return rows


def parse_cal_fragments(fragments, today: date | None = None) -> Schedule:
    today = today or date.today()
    out = Schedule()
    loan_amount = None
    for f in fragments:                                  # the amount sits on the same printed line as its label (same y)
        if f.page == 1 and f.text.startswith('ש"ח'):
            label = [g for g in fragments if g.page == 1 and abs(g.y - f.y) < 3 and "סכום ההלוואה" in g.text]
            if label:
                loan_amount = _num(f.text.replace('ש"ח', ""))
    n_stated = None
    for f in fragments:
        if f.page == 1 and re.fullmatch(r"\d{1,3}", f.text.strip()):
            if [g for g in fragments if g.page == 1 and abs(g.y - f.y) < 3 and "מס' תשלומים" in g.text]:
                n_stated = int(f.text)
    rows = _cal_rows(fragments)
    if not rows or loan_amount is None:
        out.problems.append("לא זוהה לוח סילוקין של כאל (סכום ההלוואה או טבלת התשלומים חסרים)")
        return out
    if len(rows) > MAX_ROWS or (n_stated is not None and n_stated != len(rows)):
        out.problems.append("מספר התשלומים בטבלה אינו מתאים למספר שבמכתב")
        return out
    prev = loan_amount
    for balance, interest, principal, total, d, no in rows:
        # the balance column is the chain that ends at 0 and the total is what is charged; at a rate change the printed principal / interest columns can
        # differ from them by a few shekels, so the split follows the balance (principal = the fall of the balance, interest = the rest of the payment)
        eff_principal = round(prev - balance, 2)
        eff_interest = round(total - eff_principal, 2)
        if eff_principal < -_TOL or eff_interest < -_TOL or abs(eff_principal - principal) > _CAL_TOL:
            out.problems.append(f"תשלום {no} אינו מתיישב")
            return out
        if abs(eff_principal - principal) > _TOL and _CAL_NOTE not in out.notes:
            out.notes.append(_CAL_NOTE)
        out.rows.append([d.isoformat(), eff_principal, max(eff_interest, 0.0), round(total, 2), round(balance, 2), 1 if d <= today else 0, 1])
        prev = balance
    if abs(prev) > _TOL:
        out.problems.append("היתרה בסוף הלוח אינה אפס")
        return out
    done = [r for r in out.rows if r[5]]
    out.original = round(loan_amount, 2)
    out.payment_now = (done[-1][3] if done else out.rows[0][3])
    out.ok = True
    return out


def parse_file(data: bytes, today: date | None = None) -> Schedule:
    """The lender's schedule from an Excel (Max) or a PDF letter (Cal). Anything else is refused."""
    if data[:5] == b"%PDF-":
        from core.financial_control import statement_reader as sr
        try:
            return parse_cal_fragments(sr.pdf_fragments(data, visual_hebrew=True), today)
        except sr.StatementError as exc:
            return Schedule(problems=[str(exc)])
    if data[:4] == b"PK\x03\x04":
        return parse_workbook(data)
    return Schedule(problems=["הקובץ אינו PDF או Excel (xlsx)"])


# ── stored form ───────────────────────────────────────────────────────────────────────────────────────────────────
def dumps(s: Schedule, asof: date | None = None) -> str:
    """The stored form. ``asof`` = the day the lender's schedule was issued / imported: the FUTURE rows assume the prime rate of that day (every
    prime-linked payment is recalculated when the prime moves), so the date is kept to tell the owner how fresh the projection is."""
    return json.dumps({"v": 1, "asof": (asof or date.today()).isoformat(), "rows": s.rows}, separators=(",", ":"))


def asof(text) -> date | None:
    try:
        obj = json.loads(text) if isinstance(text, str) and text else None
        return _date(obj.get("asof")) if isinstance(obj, dict) else None
    except ValueError:
        return None


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
    return {"payments": len(up), "interest": round(sum(r[2] for r in up), 2), "principal": round(sum(r[1] for r in up), 2), "total": round(sum(r[3] for r in up), 2)}


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


# ── a prime change: the not-yet-charged part is projected again ───────────────────────────────────────────────────────
def _pmt(balance: float, rate: float, n: int) -> float:
    i = rate / 1200.0
    return balance / n if i == 0 else balance * i / (1 - (1 + i) ** -n)


def pack(text: str) -> str:
    """The stored schedule, compressed for a draft's snapshot (a prime-change draft carries every loan's schedule until the owner confirms)."""
    return base64.b64encode(zlib.compress(text.encode("utf-8"), 9)).decode("ascii")


def unpack(blob) -> str | None:
    try:
        return zlib.decompress(base64.b64decode(blob)).decode("utf-8") if blob else None
    except Exception:                                    # noqa: BLE001 — a damaged blob means "no schedule", never a half-read one
        return None


def reproject(rows: list[list], delta: float, today: date) -> list[list] | None:
    """The schedule after the prime moves by ``delta`` points: payments already charged (dated up to today) stay exactly as they were; the rest is
    recomputed from the balance after the last charged payment at the new rate over the SAME remaining payments (the end date stays), with the
    payment scaled the way the bank does it (the same payment times the instalment ratio at the new vs the old rate — the bank's own baseline is
    kept). The old rate is read from the schedule itself (next payment's interest / its opening balance), not from a typed field. None when there is
    nothing ahead, the rate cannot be read, or the new rate would be negative — the old schedule is then left as it is."""
    kept = [r for r in rows if _date(r[0]) and _date(r[0]) <= today]
    future = [r for r in rows if _date(r[0]) and _date(r[0]) > today]
    if not future:
        return None
    opening = round(sum(r[1] for r in future), 2)
    if opening <= 0 or future[0][2] <= 0:
        return None
    old_rate = future[0][2] / opening * 1200.0
    new_rate = old_rate + delta
    n = len(future)
    if new_rate < 0:
        return None
    base, moved = _pmt(opening, old_rate, n), _pmt(opening, new_rate, n)
    if base <= 0:
        return None
    pay = round(future[0][3] * moved / base, 2)
    out = [list(r) for r in kept]
    bal = opening
    for k, r in enumerate(future):
        interest = round(bal * new_rate / 1200.0, 2)
        if k == n - 1:
            principal, total = round(bal, 2), round(bal + interest, 2)
        else:
            principal, total = round(pay - interest, 2), pay
        bal = round(max(bal - principal, 0.0), 2)
        out.append([r[0], principal, interest, total, bal, 0, 1])
    return out
