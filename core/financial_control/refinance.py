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
    offer["loan_ids"] = [str(i) for i in ids][:100] if isinstance(ids, list) else None
    return offer


def _money(v) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        raise RefinanceInputError("ערך לא תקין: עמלה") from None
    if f != f or not 0.0 <= f <= MAX_MONEY:
        raise RefinanceInputError("ערך מחוץ לטווח: עמלה")
    return f


def _remaining(item: dict) -> dict | None:
    """What is still ahead on a loan: months, interest, and whether the figure is exact (the lender's schedule) or an estimate."""
    bal, pay = item.get("early_closure_balance"), item.get("monthly_payment")
    sched = item.get("schedule_remaining")
    if sched and sched.get("payments"):
        return {"months": sched["payments"], "interest": sched["interest"], "exact": True}
    left = item.get("payments_remaining") if item.get("payments_remaining") is not None else item.get("months_remaining")
    if bal is None or pay is None or not left or left < 1:
        return None
    interest = round(pay * left - bal, 2)
    return {"months": int(left), "interest": max(interest, 0.0), "exact": False}


def _row(item: dict, offer: dict) -> dict:
    rem = _remaining(item)
    fee_known = item["early_fee_amount"] is not None
    fee = offer["fee_overrides"].get(item["id"], item["early_fee_amount"])
    row = {"id": item["id"], "name": item["name"], "balance": item["early_closure_balance"], "rate": item["interest_rate"],
           "payment": item["monthly_payment"], "months": rem["months"] if rem else None, "interest_left": rem["interest"] if rem else None,
           "exact": rem["exact"] if rem else None, "prepay_fee": fee, "fee_known": fee_known or item["id"] in offer["fee_overrides"],
           "same_term_payment": None, "same_term_interest": None, "net_saving": None, "interest_share": None,
           "full_term_interest": None, "full_term_net": None, "offer_payment": None, "monthly_relief": None, "relief_cost": None, "relief_cost_per_100": None, "verdict": "missing", "reason": None}
    if rem is None or item["early_closure_balance"] is None or item["monthly_payment"] is None:
        row["reason"] = "חסרים נתונים בהלוואה (יתרה, החזר חודשי או כמה תשלומים נשארו), ולכן לא חישבתי אותה"
        return row
    n, bal = rem["months"], item["early_closure_balance"]
    pay = fcc_loans._pmt(bal, offer["rate"], n)
    row["same_term_payment"] = round(pay, 2)
    row["same_term_interest"] = round(pay * n - bal, 2)
    row["net_saving"] = round(rem["interest"] - row["same_term_interest"] - (fee or 0.0), 2)
    row["interest_share"] = round(rem["interest"] / (bal + rem["interest"]), 3) if bal + rem["interest"] > 0 else None       # how much of the payments still ahead is interest
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


def _totals(rows: list[dict], offer: dict) -> dict | None:
    """The selected loans rolled into ONE mortgage: payment and interest over the loans' own remaining months and over the offer's term."""
    priced = [r for r in rows if r["verdict"] != "missing"]
    if not priced:
        return None
    bal = round(sum(r["balance"] for r in priced), 2)
    cur_pay = round(sum(r["payment"] for r in priced), 2)
    cur_interest = round(sum(r["interest_left"] for r in priced), 2)
    fees_prepay = round(sum((r["prepay_fee"] or 0.0) for r in priced), 2)
    one_time = round(offer["fees"] + fees_prepay, 2)
    longest = max(r["months"] for r in priced)
    term = offer["term_months"]
    pay_offer = fcc_loans._pmt(bal, offer["rate"], term) + offer["insurance_monthly"]
    interest_offer = pay_offer * term - bal                              # includes the insurance over the term
    pay_same = fcc_loans._pmt(bal, offer["rate"], longest) + offer["insurance_monthly"]
    interest_same = pay_same * longest - bal
    monthly_saving = round(cur_pay - pay_offer, 2)
    out = {
        "loans": len(priced), "balance": bal, "current_payment": cur_pay, "current_interest_left": cur_interest, "one_time_costs": one_time,
        "offer_payment": round(pay_offer, 2), "offer_interest": round(interest_offer, 2), "monthly_saving": monthly_saving,
        "total_saving_offer_term": round(cur_interest - interest_offer - one_time, 2),
        "same_term_months": longest, "same_term_payment": round(pay_same, 2), "same_term_interest": round(interest_same, 2),
        "total_saving_same_term": round(cur_interest - interest_same - one_time, 2),
        "payback_months": (int(-(-one_time // monthly_saving)) if monthly_saving > 0 and one_time > 0 else (0 if one_time <= 0 and monthly_saving > 0 else None)),
        "any_unknown_fee": any(r["verdict"] == "unknown_fee" for r in priced),
        "uses_estimates": any(r["exact"] is False for r in priced),
    }
    return out


def simulate(items: list[dict], offer: dict) -> dict:
    """``items`` = ``loans.loan_item`` dicts (the owner's own, owed BY him, active). Returns per-loan rows, the totals for the selected loans, and the set
    of loans worth including (their own net saving > 0 with a known fee) with its totals."""
    mine = [i for i in items if i["active"] and i["direction"] == fcc_loans.OWED_BY_ME]
    rows = [_row(i, offer) for i in mine]
    chosen = set(offer["loan_ids"]) if offer["loan_ids"] is not None else {r["id"] for r in rows}
    selected = [r for r in rows if r["id"] in chosen]
    worth = [r for r in rows if r["verdict"] == "worth"]
    notes = ["החישוב מניח שהריביות נשארות כמו שהן היום. בריבית משתנה או בהצמדה למדד התוצאה היא הערכה בלבד.",
             "הריבית משולמת בעיקר בתחילת ההלוואה. ככל שהיא מתקדמת, מה שנשאר בה הוא בעיקר קרן, ולכן מחזור הלוואה שמתקדמת חוסך מעט.",
             "גם הלוואה שלא חוסכת ריבית יכולה להיות שווה בשביל להקל על ההחזר החודשי. בכל הלוואה כתוב בכמה ההחזר יורד וכמה ריבית נוספת תשלם בסך הכל.",
             "״אם תמשיך לשלם כמו היום״ מראה כמה שווה ההפרש בריבית לבדו. ״אם תפרוס לכל התקופה״ מראה את הקלת ההחזר החודשי, אבל פריסה ארוכה מייקרת בדרך כלל את הריבית."]
    if any(r["exact"] is False for r in rows if r["verdict"] != "missing"):
        notes.append("בהלוואות בלי לוח סילוקין מהבנק הריבית שנשארה מחושבת בקירוב (ההחזר כפול מספר התשלומים פחות היתרה).")
    if any(r["verdict"] == "unknown_fee" for r in rows):
        notes.append("בהלוואות שעמלת הפירעון שלהן לא ידועה אין המלצה עד שתזין עמלה.")
    if any(r["verdict"] == "missing" for r in rows):
        notes.append("הלוואות שחסרים בהן נתונים לא נכנסו לחישוב.")
    # the monthly-relief view: every priced loan that frees cash in the mortgage, the cheapest relief (extra cost per ₪100 a month) first
    relief_rows = sorted((r for r in rows if r["verdict"] != "missing" and (r["monthly_relief"] or 0) > 0),
                         key=lambda r: (r["relief_cost_per_100"] if r["relief_cost_per_100"] is not None else 0.0))
    recommended = _totals(worth, offer)
    # a loan's own verdict is BEFORE the offer's fixed costs (opening fee, appraiser...): the set as a whole has to cover them too
    pays = bool(recommended and recommended["total_saving_same_term"] > 0)
    if worth and not pays:
        notes.append("גם ההלוואות שחוסכות ריבית כל אחת לבד לא מכסות יחד את העלויות הקבועות של ההצעה, ולכן במצב הזה המחזור לא משתלם.")
    elif offer["fees"] > 0:
        notes.append("ה״כדאי״ של כל הלוואה נבדק לפני העלויות הקבועות של ההצעה (פתיחת תיק, שמאי וכו׳). הסיכום למטה כולל אותן.")
    return {"offer": {k: offer[k] for k in ("rate", "term_months", "fees", "insurance_monthly")},
            "rows": rows, "selected_ids": [r["id"] for r in selected],
            "selected": _totals(selected, offer), "recommended_ids": [r["id"] for r in worth], "recommended": recommended, "recommended_pays": pays,
            "relief_ids": [r["id"] for r in relief_rows], "relief": _totals(relief_rows, offer), "notes": notes}
