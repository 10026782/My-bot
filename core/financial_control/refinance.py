"""FCC refinance simulator — pure, read-only. No I/O, no writes, no network, no model.

Question: "what if I roll my loans into one mortgage at THIS offer?" — per loan and for the selected set: the monthly payment, the interest still to be paid, the
one-time costs, the months until the saving pays them back, and which loans are worth including at all (a loan whose rate is already below the offer's is not).

Iron rules:
* **Only what is known.** Each loan's remaining interest comes from the lender's schedule when it is stored (exact), else from payment × payments left − balance
  (marked an estimate); a loan without balance, payment and payments left is NOT priced — it is listed as missing, never guessed. An early-repayment fee that is
  not a number ("2%", blank) is unknown: the loan's verdict says so, and the owner can type the fee in.
* **Two honest comparisons.** "Same term" (the offer's rate over the loan's own remaining months) shows what the RATE alone is worth; "offer term" (what the offer
  really sets) shows the monthly relief — a longer term lowers the payment and usually raises the total interest, so both are always shown.
* **Not a recommendation to sign.** Prime-linked loans and the offer move with the prime; every figure assumes today's rates stay. Index-linking, track mix,
  insurance and bank-specific terms are only what the owner types in.
"""

from __future__ import annotations

from datetime import date

from core.financial_control import amortization, loans as fcc_loans

MIN_GAIN_RATIO = 0.01     # a loan is worth rolling only if it saves at least 1% of its balance net of fees: a loan whose interest is mostly paid already saves pennies
MAX_RATE = 30.0
MIN_TERM, MAX_TERM = 12, 420
MAX_MONEY = 50_000_000.0


class RefinanceInputError(ValueError):
    """A parameter outside what a real offer can be; the message is safe to show."""


def parse_offer(params: dict) -> dict:
    def num(key, lo, hi, required=True):
        raw = params.get(key)
        if raw in (None, ""):
            if required:
                raise RefinanceInputError(f"חסר: {key}")
            return 0.0
        try:
            v = float(raw)
        except (TypeError, ValueError):
            raise RefinanceInputError(f"ערך לא תקין: {key}") from None
        if v != v or not lo <= v <= hi:                          # NaN or out of range
            raise RefinanceInputError(f"ערך מחוץ לטווח: {key}")
        return v
    offer = {"rate": num("rate", 0.0, MAX_RATE), "term_months": int(num("term_months", MIN_TERM, MAX_TERM)),
             "fees": num("fees", 0.0, MAX_MONEY, False), "insurance_monthly": num("insurance_monthly", 0.0, MAX_MONEY, False)}
    overrides = params.get("fee_overrides") or {}
    if not isinstance(overrides, dict):
        raise RefinanceInputError("ערך לא תקין: fee_overrides")
    offer["fee_overrides"] = {str(k): _money(v) for k, v in list(overrides.items())[:50]}
    ids = params.get("loan_ids")
    offer["loan_ids"] = list(dict.fromkeys(str(i) for i in ids))[:100] if isinstance(ids, list) else None       # each loan once, whatever the caller sent
    offer["detail"] = bool(params.get("detail"))                                                                    # month-by-month rows for the selected loans
    return offer


def _money(v) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        raise RefinanceInputError("ערך לא תקין: עמלה") from None
    if f != f or not 0.0 <= f <= MAX_MONEY:
        raise RefinanceInputError("ערך מחוץ לטווח: עמלה")
    return f


def _remaining(item: dict, rows: list[list] | None, today: date) -> dict | None:
    """What is still ahead on a loan, as the payments themselves: the lender's schedule rows when stored (exact), else a labelled ESTIMATE built from the loan's own
    balance, payment and payments left. ``principal`` is the principal those payments repay — the basis of every comparison, so the two sides repay the same money."""
    ahead = amortization.ahead(rows, today) if rows else []
    if ahead:
        return {"rows": ahead, "months": len(ahead), "interest": round(sum(r[2] for r in ahead), 2), "principal": round(sum(r[1] for r in ahead), 2), "exact": True}
    bal, pay = item.get("early_closure_balance"), item.get("monthly_payment")
    left = item.get("payments_remaining") if item.get("payments_remaining") is not None else item.get("months_remaining")
    if bal is None or pay is None or not left or left < 1:
        return None
    first = date.fromisoformat(item["first_payment_date"]) if item.get("first_payment_date") else today
    est = _estimate_rows(bal, item.get("interest_rate"), pay, int(left), first)
    return {"rows": est, "months": int(left), "interest": max(round(pay * left - bal, 2), 0.0), "principal": round(bal, 2), "exact": False}


def _estimate_rows(balance: float, rate_pct, pay: float, n: int, first: date) -> list[list]:
    """An ESTIMATED schedule for a loan without the lender's table: the payment stays what it is today for the payments left, the interest follows the declining balance
    and is scaled so that the total interest is payment × payments left − balance (the same figure the loan card shows). Never shown as the bank's schedule."""
    target = max(pay * n - balance, 0.0)
    raw, bal = [], balance
    for _ in range(n):
        i = bal * (rate_pct or 0.0) / 1200.0
        raw.append(i)
        bal -= max(pay - i, 0.0)
    scale = target / sum(raw) if sum(raw) > 0 else 0.0
    rows, bal = [], round(balance, 2)
    for k in range(n):
        interest = round(raw[k] * scale if scale else target / n, 2)
        if k == n - 1:
            principal, total = round(bal, 2), round(bal + interest, 2)
        else:
            principal, total = round(pay - interest, 2), round(pay, 2)
        bal = round(max(bal - principal, 0.0), 2)
        rows.append([amortization._plus_months(first, k).isoformat(), principal, interest, total, bal, 0, 0])
    return rows


def _row(item: dict, offer: dict, rem: dict | None) -> dict:
    fee_known = item["early_fee_amount"] is not None
    fee = offer["fee_overrides"].get(item["id"], item["early_fee_amount"])
    row = {"id": item["id"], "name": item["name"], "balance": item["early_closure_balance"], "rate": item["interest_rate"],
           "payment": item["monthly_payment"], "months": rem["months"] if rem else None, "interest_left": rem["interest"] if rem else None,
           "exact": rem["exact"] if rem else None, "prepay_fee": fee, "fee_known": fee_known or item["id"] in offer["fee_overrides"],
           "payoff_now": round(item["early_closure_balance"] + fee, 2) if item["early_closure_balance"] is not None and fee is not None else None,
           "same_term_payment": None, "same_term_interest": None, "net_saving": None, "interest_share": None,
           "full_term_interest": None, "full_term_net": None, "offer_payment": None, "monthly_relief": None, "relief_cost": None, "relief_cost_per_100": None, "verdict": "missing", "reason": None}
    if rem is None or item["early_closure_balance"] is None or item["monthly_payment"] is None:
        row["reason"] = "חסרים נתונים בהלוואה (יתרה, החזר חודשי או כמה תשלומים נשארו), ולכן לא חישבתי אותה"
        return row
    n, bal = rem["months"], rem["principal"]                  # the principal the remaining payments repay: the same money on both sides of every comparison
    pay = fcc_loans._pmt(bal, offer["rate"], n)
    row["same_term_payment"] = round(pay, 2)
    row["same_term_interest"] = round(pay * n - bal, 2)
    row["net_saving"] = round(rem["interest"] - row["same_term_interest"] - (fee or 0.0), 2)
    row["interest_share"] = round(rem["interest"] / (bal + rem["interest"]), 3) if bal + rem["interest"] > 0 else None       # how much of the payments still ahead is interest (information only, not a rate)
    full = fcc_loans._pmt(bal, offer["rate"], offer["term_months"]) * offer["term_months"] - bal        # the same principal left in the mortgage for its whole term
    row["full_term_interest"] = round(full, 2)
    row["full_term_net"] = round(rem["interest"] - full - (fee or 0.0), 2)
    # the monthly aspect: this loan alone inside the mortgage at the offer's term. A loan can fail on interest and still be worth it for the cash it frees every month.
    pay_in = fcc_loans._pmt(bal, offer["rate"], offer["term_months"])
    row["offer_payment"] = round(pay_in, 2)
    row["monthly_relief"] = round(item["monthly_payment"] - pay_in, 2)
    row["relief_cost"] = round(full + (fee or 0.0) - rem["interest"], 2)                  # the extra interest and fee paid in total for that relief (negative = it also saves interest)
    if row["monthly_relief"] > 0:
        row["relief_cost_per_100"] = round(row["relief_cost"] / row["monthly_relief"] * 100.0, 2)     # total extra cost for every ₪100 of monthly relief
    if not row["fee_known"]:
        row["verdict"] = "unknown_fee"
        row["reason"] = "לא ידועה עמלת הפירעון של ההלוואה. הזן אותה כדי שאדע אם כדאי"
    elif row["net_saving"] >= MIN_GAIN_RATIO * bal and row["net_saving"] > 0:
        row["verdict"] = "worth"
        if row["full_term_net"] < 0:
            row["reason"] = "כדאי רק אם תמשיך לשלם אותה בקצב של היום. אם תפרוס אותה לכל תקופת המשכנתא היא תתייקר"
    else:
        row["verdict"] = "not_worth"
        if (item["interest_rate"] or 0) <= offer["rate"]:
            row["reason"] = "הריבית שלה כבר נמוכה מהריבית בהצעה או שווה לה"
        elif row["net_saving"] > 0:
            row["reason"] = f"כמעט נגמרה: נשארו רק {n} תשלומים וכמעט כל מה שנשאר בה הוא קרן, אז אין ריבית שמשתלם לחסוך"
        else:
            row["reason"] = "עמלת הפירעון גדולה מהריבית שאפשר לחסוך"
    return row


# ── the shared time axis: every path of a set of loans, month by month ──────────────────────────────────────────────────
def _ym(iso: str) -> int:
    d = date.fromisoformat(iso[:10])
    return d.year * 12 + d.month - 1


def _month_arrays(paths: list[list[list]], base: int, length: int, start_balances: list[float]) -> dict:
    """Sum several loans' payment rows on ONE axis (month index from ``base``): a loan contributes only in the months it is paid, so a loan that ended stops adding
    and a longer path keeps going. Also the debt left after each month (a finished loan carries 0, a not-yet-started one its opening principal)."""
    pay, interest, principal, debt = [0.0] * length, [0.0] * length, [0.0] * length, [0.0] * length
    for rows, opening in zip(paths, start_balances):
        by_month = {}
        for r in rows:
            m = _ym(r[0]) - base
            cur = by_month.setdefault(m, [0.0, 0.0, 0.0, 0.0])
            cur[0] += r[3]; cur[1] += r[2]; cur[2] += r[1]; cur[3] = r[4]
        carry = opening
        for m in range(length):
            if m in by_month:
                pay[m] += by_month[m][0]; interest[m] += by_month[m][1]; principal[m] += by_month[m][2]
                carry = by_month[m][3]
            debt[m] += carry
    r2 = lambda xs: [round(x, 2) for x in xs]
    return {"pay": r2(pay), "interest": r2(interest), "principal": r2(principal), "debt": r2(debt)}


def _totals(rows: list[dict], offer: dict, rems: dict[str, dict], detail: bool = False) -> dict | None:
    """The selected loans on one time axis, in three separate readings the owner asked to keep apart: the NOMINAL SAVING (interest, fees and insurance — the only thing that is
    a saving), the MONTHLY RELIEF (a cash-flow effect, never called a saving) and the FUTURE DEBT (what is still owed after N years). Two alternatives are built from scratch next to the
    loans' own remaining payments: "like today" (each loan repaid over its own remaining months at the offer's rate, which is what a mortgage with one track per loan would cost)
    and "stretched" (ONE mortgage over the offer's term for the sum of the principals). One-time costs (the offer's fees + each loan's early-repayment fee) are counted once."""
    priced = [r for r in rows if r["verdict"] != "missing"]
    if not priced:
        return None
    keep_paths = [rems[r["id"]]["rows"] for r in priced]
    openings = [rems[r["id"]]["principal"] for r in priced]
    firsts = [_ym(p[0][0]) for p in keep_paths]
    base = min(firsts)
    principal = round(sum(openings), 2)
    term, rate = offer["term_months"], offer["rate"]
    first_date = date(base // 12, base % 12 + 1, 1)
    same_paths = [amortization.annuity_rows(o, rate, len(p), first_date, dates=[amortization._plus_months(date.fromisoformat(p[0][0][:10]), k).isoformat() for k in range(len(p))])
                  for p, o in zip(keep_paths, openings)]
    stretch_path = amortization.annuity_rows(principal, rate, term, first_date)
    length = max(max(_ym(p[-1][0]) - base + 1 for p in keep_paths), max(_ym(p[-1][0]) - base + 1 for p in same_paths), term)
    keep = _month_arrays(keep_paths, base, length, openings)
    same = _month_arrays(same_paths, base, length, openings)
    stretch = _month_arrays([stretch_path], base, length, [principal])
    ins = offer["insurance_monthly"]
    same_len = max(_ym(p[-1][0]) - base + 1 for p in same_paths)
    for m in range(length):                                                           # insurance runs while the mortgage does, and is a cost like interest
        if m < same_len:
            same["pay"][m] = round(same["pay"][m] + ins, 2)
        if m < term:
            stretch["pay"][m] = round(stretch["pay"][m] + ins, 2)
    fees_prepay = round(sum((r["prepay_fee"] or 0.0) for r in priced), 2)
    one_time = round(offer["fees"] + fees_prepay, 2)
    keep_interest = round(sum(keep["interest"]), 2)
    same_interest, stretch_interest = round(sum(same["interest"]), 2), round(sum(stretch["interest"]), 2)
    same_ins, stretch_ins = round(ins * same_len, 2), round(ins * term, 2)
    relief = round(keep["pay"][0] - stretch["pay"][0], 2)
    # when the monthly saving of the stretched mortgage has paid the one-time costs back (cumulative, on the shared axis)
    payback, cum = None, 0.0
    for m in range(length):
        cum += keep["pay"][m] - stretch["pay"][m]
        if cum >= one_time and (one_time > 0 or relief > 0):
            payback = m + 1 if one_time > 0 else 0
            break
    years = []
    cum_same = cum_stretch = 0.0
    for y in range((length + 11) // 12):
        sl = slice(12 * y, 12 * y + 12)
        last = min(12 * y + 12, length) - 1
        cell = lambda a: {"payment": round(sum(a["pay"][sl]), 2), "interest": round(sum(a["interest"][sl]), 2), "principal": round(sum(a["principal"][sl]), 2), "debt_end": a["debt"][last]}
        k, sa, st = cell(keep), cell(same), cell(stretch)
        cum_same += k["payment"] - sa["payment"]; cum_stretch += k["payment"] - st["payment"]
        years.append({"year": y + 1, "keep": k, "same_pace": sa, "stretch": st, "diff_same_pace": round(k["payment"] - sa["payment"], 2), "diff_stretch": round(k["payment"] - st["payment"], 2),
                      "cum_diff_same_pace": round(cum_same, 2), "cum_diff_stretch": round(cum_stretch, 2)})
    out = {
        "loans": len(priced), "balance": principal, "one_time_costs": one_time,
        # (1) nominal saving: interest + insurance + one-time costs, the same principal repaid on both sides
        "current_interest_left": keep_interest,
        "same_term_months": same_len, "same_term_interest": round(same_interest + same_ins, 2), "total_saving_same_term": round(keep_interest - same_interest - same_ins - one_time, 2),
        "offer_interest": round(stretch_interest + stretch_ins, 2), "total_saving_offer_term": round(keep_interest - stretch_interest - stretch_ins - one_time, 2),
        # (2) monthly relief: the first month's payments, today vs after
        "current_payment": keep["pay"][0], "same_term_payment": same["pay"][0], "offer_payment": stretch["pay"][0], "monthly_saving": relief,
        "payback_months": payback,
        # (3) future debt, after 1, 3, 5, 10, 15, 20 years on the shared axis (0 = fully repaid)
        "debt_ahead": [{"years": y, "keep": keep["debt"][min(12 * y, length) - 1], "same_pace": same["debt"][min(12 * y, length) - 1], "stretch": stretch["debt"][min(12 * y, length) - 1]}
                       for y in (1, 3, 5, 10, 15, 20) if 12 * y <= length + 11],
        "timeline": {"months": length, "years": years},
        "any_unknown_fee": any(r["verdict"] == "unknown_fee" for r in priced),
        "uses_estimates": any(r["exact"] is False for r in priced),
        "estimated_loans": [r["name"] or r["id"] for r in priced if r["exact"] is False],
    }
    if detail:
        out["monthly"] = [{"month": m + 1, "keep": [keep["pay"][m], keep["interest"][m], keep["principal"][m]], "same_pace": [same["pay"][m], same["interest"][m], same["principal"][m]],
                           "stretch": [stretch["pay"][m], stretch["interest"][m], stretch["principal"][m]]} for m in range(length)]
    return out


def simulate(items: list[dict], offer: dict, schedules: dict[str, list[list]] | None = None, today: date | None = None) -> dict:
    """``items`` = ``loans.loan_item`` dicts (the owner's own, owed BY him, active); ``schedules`` = the stored lender schedules by loan id (rows), when any. Returns per-loan rows, the
    totals for the selected loans, and the set of loans worth including (their own net saving > 0 with a known fee) with its totals."""
    day = today or date.today()
    schedules = schedules or {}
    unique = {}
    for i in items:
        if i["active"] and i["direction"] == fcc_loans.OWED_BY_ME:
            unique.setdefault(i["id"], i)                                              # a loan is one loan, however many times it arrives
    mine = list(unique.values())
    rems = {i["id"]: _remaining(i, schedules.get(i["id"]), day) for i in mine}
    rows = [_row(i, offer, rems[i["id"]]) for i in mine]
    chosen = set(offer["loan_ids"]) if offer["loan_ids"] is not None else {r["id"] for r in rows}
    selected = [r for r in rows if r["id"] in chosen]
    worth = [r for r in rows if r["verdict"] == "worth"]
    notes = ["החישוב מניח שהריביות נשארות כמו שהן היום. בריבית משתנה או בהצמדה למדד התוצאה היא הערכה בלבד.",
             "הריבית משולמת בעיקר בתחילת ההלוואה. ככל שהיא מתקדמת, מה שנשאר בה הוא בעיקר קרן, ולכן מחזור הלוואה שמתקדמת חוסך מעט.",
             "גם הלוואה שלא חוסכת ריבית יכולה להיות שווה בשביל להקל על ההחזר החודשי. בכל הלוואה כתוב בכמה ההחזר יורד וכמה ריבית נוספת תשלם בסך הכל.",
             "״אם תמשיך לשלם כמו היום״ מראה כמה שווה ההפרש בריבית לבדו. ״אם תפרוס לכל התקופה״ מראה את הקלת ההחזר החודשי, אבל פריסה ארוכה מייקרת בדרך כלל את הריבית.",
             "חיסכון בריבית, הקלה בהחזר החודשי ויתרת החוב העתידית מוצגים בנפרד: הקלה בהחזר החודשי היא לא חיסכון."]
    if any(r["exact"] is False for r in rows if r["verdict"] != "missing"):
        notes.append("הלוואות בלי לוח סילוקין מהבנק מחושבות בקירוב (מסומנות בהערכה), ולא כנתון בנקאי מאומת.")
    if any(r["verdict"] == "unknown_fee" for r in rows):
        notes.append("בהלוואות שעמלת הפירעון שלהן לא ידועה אין המלצה עד שתזין עמלה.")
    if any(r["verdict"] == "missing" for r in rows):
        notes.append("הלוואות שחסרים בהן נתונים לא נכנסו לחישוב.")
    # the monthly-relief view: every priced loan that frees cash in the mortgage, the cheapest relief (extra cost per ₪100 a month) first
    relief_rows = sorted((r for r in rows if r["verdict"] != "missing" and (r["monthly_relief"] or 0) > 0),
                         key=lambda r: (r["relief_cost_per_100"] if r["relief_cost_per_100"] is not None else 0.0))
    recommended = _totals(worth, offer, rems)
    # a loan's own verdict is BEFORE the offer's fixed costs (opening fee, appraiser...): the set as a whole has to cover them too
    pays = bool(recommended and recommended["total_saving_same_term"] > 0)
    if worth and not pays:
        notes.append("גם ההלוואות שחוסכות ריבית כל אחת לבד לא מכסות יחד את העלויות הקבועות של ההצעה, ולכן במצב הזה המחזור לא משתלם.")
    elif offer["fees"] > 0:
        notes.append("ה״כדאי״ של כל הלוואה נבדק לפני העלויות הקבועות של ההצעה (פתיחת תיק, שמאי וכו׳). הסיכום למטה כולל אותן, פעם אחת.")
    return {"offer": {k: offer[k] for k in ("rate", "term_months", "fees", "insurance_monthly")},
            "rows": rows, "selected_ids": [r["id"] for r in selected],
            "selected": _totals(selected, offer, rems, offer.get("detail", False)), "recommended_ids": [r["id"] for r in worth], "recommended": recommended, "recommended_pays": pays,
            "relief_ids": [r["id"] for r in relief_rows], "relief": _totals(relief_rows, offer, rems), "notes": notes}
