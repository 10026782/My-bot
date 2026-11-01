"""FCC card import, stage 5c — ``core.financial_control.card_import`` (pure) + the offline script's helpers. Synthetic fragments only.

Covers: row grouping (an icon / date a hair off the text), merchant / type / remark columns, sections that must add up to the statement's own
total, loan instalments (the instalment, not the loan), ATM withdrawals, benefit lines, unreadable rows, keys, classification (owner rules win),
matching a section to the bank's settlement (amount, window, each bank line once) and what the card statement does not cover.
"""

from __future__ import annotations

from datetime import date

from core.financial_control import bank_import as bi
from core.financial_control import card_import as ci
from core.financial_control.card_import import Fragment as F

TYPE_X = 373.0


def header(page=1, y=0.0):
    return [F(page, 507, y, "תאריך"), F(page, TYPE_X, y, "סוג"), F(page, 194, y, "הערות")]


def card_header(last4, page=1, y=0.0):
    return [F(page, 456, y, "לכרטיס"), F(page, 423, y, "שמסתיים"), F(page, 413, y, "-ב"), F(page, 396, y, last4)]


def txn(y, day, words, charge, amount=None, kind_words=("רגילה",), remark=(), page=1, date_dy=0.0):
    """One transaction row. Words are given in logical order and placed right to left (x descending), like the statement."""
    out = [F(page, 497, y + date_dy, day)]
    x = 480.0
    for w in words:
        out.append(F(page, x, y, w))
        x -= 20
    kx = 371.0 if len(kind_words) > 1 else 367.0
    for w in kind_words:
        out.append(F(page, kx, y, w))
        kx -= 18
    if amount is not None:
        out.append(F(page, 290, y, f"{amount:,.2f}"))
    out.append(F(page, 243, y, f"{charge:,.2f}"))
    rx = 193.0
    for w in remark:
        out.append(F(page, rx, y, w))
        rx -= 12
    return out


def total(y, day, amount, page=1):
    return [F(page, 509, y, 'סה"כ'), F(page, 489, y, "חיובים"), F(page, 465, y, "בתאריך"), F(page, 434, y, day), F(page, 238, y, f"{amount:,.2f}"), F(page, 232, y, "₪")]


def statement():
    frags = header() + card_header("7716", y=-20.0)
    frags += txn(20, "14/09/26", ["שופרסל", "יש", "חסד"], 54.80)
    frags += txn(30, "15/09/26", ["קרן", "עולם", "התורה"], 20.00, date_dy=2.0)           # the date sits 2 points off the text
    frags += txn(40, "15/09/26", ["קרן", "עולם", "התורה"], 20.00)                        # an identical charge the same day
    frags += txn(50, "04/10/26", [], -1.34, remark=("הנחת", "מועדון"))                    # a benefit line: one amount, negative
    frags += total(60, "15/10/26", 54.80 + 20 + 20 - 1.34)
    # a second card: an ATM withdrawal charged immediately, then a bill with a loan instalment
    frags += card_header("6428", y=70.0)
    frags += txn(80, "25/09/26", ["כספומט", "המזרחי", "מודיעין"], 1000.0, 1000.0, kind_words=("חיוב", "עסקות", "מיידי"))
    frags += total(90, "28/09/26", 1000.0)
    frags += txn(100, "10/10/21", ["מקס"], 717.02, 32000.0, kind_words=("הלוואה", "מתחשבת", "2"), remark=("תשלום", "57", "מתוך", "60"))
    frags += txn(110, "24/09/26", ["דן", "חברה", "לתחבורה", "ציבורית"], 30.00)
    frags += total(120, "15/10/26", 747.02)
    # noise that must be ignored: an interest table (dates, percentages), a VAT box (three amounts, no date), a summary line without a date
    frags += [F(2, 518, 5, "החל"), F(2, 434, 5, "03/09/26"), F(2, 441, 15, "11.00%"), F(2, 351, 15, "10.25%")]
    frags += [F(2, 290, 30, "17.90"), F(2, 250, 30, "2.73"), F(2, 210, 30, "15.17")]
    return frags


def test_parses_sections_cards_merchants_and_columns():
    p = ci.parse_card_statement(statement(), "max")
    assert p.ok and p.problems == [] and len(p.sections) == 3
    s1, s2, s3 = p.sections
    assert (s1.card, s1.billing_date, s1.total, s1.computed, s1.ok, s1.rows) == ("7716", date(2026, 10, 15), 93.46, 93.46, True, 4)
    assert (s2.card, s2.billing_date, s2.immediate, s2.rows) == ("6428", date(2026, 9, 28), True, 1)
    assert (s3.card, s3.total, s3.ok) == ("6428", 747.02, True)
    by = {(c.date, c.merchant): c for c in p.charges}
    assert by[(date(2026, 9, 14), "שופרסל יש חסד")].charge == 54.8 and by[(date(2026, 9, 14), "שופרסל יש חסד")].card == "7716"
    assert len([c for c in p.charges if c.merchant == "קרן עולם התורה"]) == 2                     # the off-by-2 date still joins its row


def test_loan_instalment_is_the_instalment_not_the_loan_and_atm_is_cash():
    p = ci.parse_card_statement(statement(), "max")
    loan = next(c for c in p.charges if c.kind == ci.LOAN)
    assert (loan.charge, loan.amount, loan.remark) == (717.02, 32000.0, "תשלום 57 מתוך 60") and loan.date == date(2021, 10, 10)
    items = {c.charge.merchant: c for c in ci.classify_all(p.charges)}
    assert items["מקס"].kind == ci.EXPENSE and items["מקס"].category == "loans" and items["מקס"].charge.charge == 717.02
    atm = items["כספומט המזרחי מודיעין"]
    assert atm.kind == ci.CASH and atm.category is None and atm.charge.kind == ci.IMMEDIATE


def test_only_decided_card_lines_are_importable():
    items = ci.classify_all(ci.parse_card_statement(statement(), "max").charges)
    ok = [c.charge.merchant for c in items if ci.importable(c)]
    assert set(ok) == {"מקס", "דן חברה לתחבורה ציבורית"}                                  # the loan instalment and a built-in category; cash / unknown / benefit wait


def test_benefit_line_is_an_adjustment_with_its_remark():
    p = ci.parse_card_statement(statement(), "max")
    benefit = next(c for c in p.charges if c.kind == ci.BENEFIT)
    assert benefit.charge == -1.34 and benefit.amount is None and benefit.merchant == "הנחת מועדון"
    assert ci.classify_charge(benefit).kind == ci.ADJUSTMENT


def test_a_section_that_does_not_add_up_or_leftover_rows_make_the_statement_not_ok():
    frags = header() + card_header("7716", y=-20.0) + txn(20, "14/09/26", ["א"], 50.0) + total(30, "15/10/26", 49.0)
    p = ci.parse_card_statement(frags)
    assert not p.ok and p.sections[0].ok is False and "50.00" in p.problems[0] and "49.00" in p.problems[0]
    left = ci.parse_card_statement(header() + card_header("7716", y=-20.0) + txn(20, "14/09/26", ["א"], 50.0))
    assert not left.ok and "after the last section total" in left.problems[0] and left.charges == []
    assert not ci.parse_card_statement([]).ok                                                 # nothing parsed is not "ok"


def test_a_row_with_too_many_amounts_is_reported_not_guessed():
    bad = header() + card_header("7716", y=-20.0) + [F(1, 497, 20, "14/09/26"), F(1, 290, 20, "1.00"), F(1, 260, 20, "2.00"), F(1, 243, 20, "3.00")]
    p = ci.parse_card_statement(bad + total(30, "15/10/26", 0.0))
    assert not p.ok and any("unreadable row" in x for x in p.problems)


def test_keys_are_stable_distinct_for_identical_same_day_charges_and_per_card_ref():
    a = ci.parse_card_statement(statement(), "max").charges
    b = ci.parse_card_statement(statement(), "max").charges
    c = ci.parse_card_statement(statement(), "other").charges
    assert [x.key for x in a] == [x.key for x in b] and len({x.key for x in a}) == len(a) and not {x.key for x in a} & {x.key for x in c}
    assert all(x.key.startswith("card:") for x in a)


def test_classification_builtin_owner_rules_and_unknown():
    mk = lambda m: ci.CardCharge(date(2026, 9, 1), m, 10.0, 10.0, "1", date(2026, 10, 15), 1, ci.REGULAR)
    assert ci.classify_charge(mk("דן חברה לתחבורה ציבורית")).category == "transport"
    assert ci.classify_charge(mk("משנת יוסף")).kind == ci.UNKNOWN
    rules = bi.owner_rules_from([{"match": "משנת יוסף", "kind": "expense", "category": "institutions"}, {"match": "שופרסל", "kind": "expense", "category": "living"}])
    assert ci.classify_charge(mk("משנת יוסף"), rules).category == "institutions" and ci.classify_charge(mk("שופרסל יש חסד"), rules).category == "living"
    s = ci.summarize(ci.classify_all(ci.parse_card_statement(statement(), "max").charges))
    assert s["by_kind"]["cash_withdrawal"]["total"] == 1000.0 and s["by_category"]["loans"] == 717.02
    assert [u["merchant"] for u in s["unmapped"]][0] == "שופרסל יש חסד" and s["unmapped_total"] == 2


# ── the Isracard layout: a "ענף" column, a card-at-the-business column, a different total wording, undated fee lines ─────────────────────────
def iso_header(page=1, y=0.0):
    return [F(page, 502, y, "תאריך"), F(page, 456, y, "כרטיס"), F(page, 429, y, "שם"), F(page, 342, y, "ענף"), F(page, 287, y, "סכום"), F(page, 199, y, "פירוט")]


def iso_txn(y, day, in_business, words, sector, amount, charge, remark=(), page=1):
    out = [F(page, 490, y, day)]
    out += [F(page, 469 - 17 * i, y, w) for i, w in enumerate(in_business)]                  # "לא הוצג" / "ה.קבע": never part of the merchant name
    out += [F(page, 432 - 18 * i, y, w) for i, w in enumerate(words)]
    out += [F(page, 336, y, w) for w in sector[:1]] + [F(page, 318, y, w) for w in sector[1:]]
    if amount is not None:
        out.append(F(page, 285, y, f"{amount:,.2f}"))
    out.append(F(page, 243, y, f"{charge:,.2f}"))
    out += [F(page, 198 - 12 * i, y, w) for i, w in enumerate(remark)]
    return out


def iso_total(y, day, amount, page=1):
    return [F(page, 503, y, 'סה"כ'), F(page, 485, y, "חיוב"), F(page, 455, y, "לתאריך"), F(page, 414, y, day), F(page, 226, y, f"{amount:,.2f}")]


def iso_statement():
    frags = iso_header() + card_header("3818", y=-20.0)
    frags += iso_txn(20, "27/09/26", [], ["משיכת", "מזומנים"], ["שונות"], 2000.0, 2000.0) + iso_total(30, "28/09/26", 2000.0)
    frags += iso_txn(40, "05/07/26", ["לא", "הוצג"], ["לאסט", "פרייס"], ["שונות"], 4405.0, 367.08, remark=("תשלום", "4", "מתוך", "12"))
    frags += iso_txn(50, "10/09/26", ["תש.", "נייד"], ["פז", "אפליקצית", "YELLOW"], ["דלק"], 16.0, 16.0)
    frags += iso_txn(60, "20/09/26", ["ה.", "קבע"], ["מגדל", "בריאות/חיים"], ["ביטוח"], 278.11, 278.11)
    frags += iso_txn(70, "24/09/26", ["לא", "הוצג"], ["קליית", "בראשית"], ["מסעדות/קפה"], 17.52, 17.52)
    # the card's own fee lines (no date): the fee, its VAT and the fee subtotal (which must not be counted again)
    frags += [F(2, 430, 80, "דמי"), F(2, 407, 80, "כרטיס"), F(2, 378, 80, "הנפקה/"), F(2, 206, 80, "15.17"), F(2, 198, 80, "₪")]
    frags += [F(2, 206, 90, "2.73"), F(2, 197, 90, "₪"), F(2, 181, 90, 'מע"מ'), F(2, 159, 90, "18.00%")]
    frags += [F(2, 245, 100, "17.90"), F(2, 203, 100, 'סה"כ'), F(2, 189, 100, "כולל"), F(2, 172, 100, 'מע"מ')]
    frags += iso_total(110, "11/10/26", 367.08 + 16 + 278.11 + 17.52 + 15.17 + 2.73, page=2)
    return frags


def test_isracard_layout_sections_fees_and_the_card_at_the_business_column():
    p = ci.parse_card_statement(iso_statement(), "isracard")
    assert p.ok and p.problems == [] and [(s.card, s.billing_date.day, s.total, s.ok) for s in p.sections] == [("3818", 28, 2000.0, True), ("3818", 11, 696.61, True)]
    by = {c.merchant: c for c in p.charges}
    assert {"משיכת מזומנים", "לאסט פרייס", "פז אפליקצית YELLOW", "מגדל בריאות/חיים", "קליית בראשית"} <= set(by)
    assert by["לאסט פרייס"].charge == 367.08 and by["לאסט פרייס"].amount == 4405.0 and by["לאסט פרייס"].remark == "תשלום 4 מתוך 12" and by["לאסט פרייס"].kind == ci.REGULAR
    assert by["לאסט פרייס"].merchant.split() == ["לאסט", "פרייס"] and by["פז אפליקצית YELLOW"].sector == "דלק" and by["מגדל בריאות/חיים"].sector == "ביטוח"
    fees = [c for c in p.charges if c.kind == ci.FEE]
    assert [c.charge for c in fees] == [15.17, 2.73] and all(c.date == date(2026, 10, 11) for c in fees)      # the 17.90 subtotal is not a third fee


def test_isracard_classification_cash_fees_and_unambiguous_sectors_only():
    items = {c.charge.merchant: c for c in ci.classify_all(ci.parse_card_statement(iso_statement(), "isracard").charges)}
    assert items["משיכת מזומנים"].kind == ci.CASH and not ci.importable(items["משיכת מזומנים"])
    assert items["פז אפליקצית YELLOW"].category == "transport" and items["מגדל בריאות/חיים"].category == "insurance"        # the issuer's own sector
    assert items["לאסט פרייס"].kind == ci.UNKNOWN and items["קליית בראשית"].kind == ci.UNKNOWN                              # a restaurant sector is not guessed into a category
    fee = [c for c in items.values() if c.charge.kind == ci.FEE]
    assert len(fee) == 2 and all(c.kind == ci.EXPENSE and c.category == "עמלות וריבית" and ci.importable(c) for c in fee)


def test_isracard_sections_match_the_bank_settlements():
    p = ci.parse_card_statement(iso_statement(), "isracard")
    b = bank([(date(2026, 9, 28), 2000.0, 'ישראכרט בע"מ'), (date(2026, 10, 11), 696.61, 'ישראכרט בע"מ'), (date(2026, 10, 11), 1114.44, 'ישראכרט בע"מ')])
    m = ci.match_settlements(p.sections, b)
    assert [x.bank_key for x in m] == ["b0", "b1"] and ci.reconcile(b, m)["uncovered_bank_settlements"] == {"count": 1, "total": 1114.44}


# ── an Excel export (header-driven; the preferred input) ─────────────────────────────────────────────────────────
from datetime import datetime as DT

HEAD = ("תאריך\nעסקה", "שם בית עסק", "סכום\nעסקה", "סכום\nחיוב", "סוג\nעסקה", "ענף", "הערות")


def table(extra=()):
    rows = [("פירוט עסקאות לחשבון בנק 111-2222 לכרטיס אשראי משולב המסתיים ב-1234", None, None, None, None, None, None), (None,) * 7,
            ("עסקאות לחיוב ב-10/10/2026: 1,300.60 ₪*", None, None, None, None, None, None), HEAD,
            (DT(2026, 9, 30), "החזר מועדון", -6.16, None, "צבירה למועדון", None, None),                           # no charge: not part of this bill
            (DT(2026, 9, 28), "תוכנה בע\"מ", 60.0, 60.0, "רגילה", "תקשורת ומחשבים", None),
            (DT(2026, 9, 27), "כביש חוצה צפון", 4.94, 4.94, "הוראת קבע", "רכב ותחבורה", None),
            (DT(2026, 9, 27), "דמי כרטיס", 17.9, None, "שרותים", "ציוד ומשרד", None),                              # a waived fee: no charge
            (DT(2026, 9, 27), "הבנק", 400.0, 400.0, "משיכת מזומן", None, None),
            (DT(2026, 9, 23), "ביטוח ישיר חיים", 168.59, 168.59, "הוראת קבע", "ביטוח ופיננסים", None),
            (DT(2026, 8, 31), "שירות אשראי מתגלגל", -2121.57, -2121.57, "זיכוי", "ציוד ומשרד", None),
            (DT(2026, 8, 31), "שירות אשראי מתגלגל", 1617.84, 1640.29, "רכישה בקרדיט", "ציוד ומשרד", "תשלום 1 מתוך 1"),
            (DT(2026, 3, 11), "הלוואת אקספרס", 2800.0, 52.84, "רכישה בקרדיט", "ציוד ומשרד", "תשלום 6 מתוך 72"),
            (DT(2026, 3, 11), "הלוואה מחוץ למסגרת", 18400.0, 614.23, "רכישה בקרדיט", "ציוד ומשרד", "תשלום 6 מתוך 72"),
            *extra, (None,) * 7, ("כרטיסך מחויב בהתאם...", None, None, None, None, None, None)]
    return rows


def test_excel_table_columns_are_found_by_header_name_and_uncharged_rows_are_skipped():
    p = ci.parse_card_table(table(), "cal")
    assert p.ok and p.problems == [] and len(p.sections) == 1
    s = p.sections[0]
    assert (s.card, s.billing_date, s.total, s.computed, s.ok) == ("1234", date(2026, 10, 10), 1300.6, 1300.6, True)
    assert sorted(c.merchant for c in p.charges) == sorted(["תוכנה בע\"מ", "כביש חוצה צפון", "הבנק", "ביטוח ישיר חיים", "שירות אשראי מתגלגל", "שירות אשראי מתגלגל", "הלוואת אקספרס", "הלוואה מחוץ למסגרת"])
    assert not [c for c in p.charges if c.merchant in ("החזר מועדון", "דמי כרטיס")]                      # no charge amount: not in this bill


def test_excel_rolling_credit_is_outside_the_statement_total_but_inside_what_the_bank_pays():
    p = ci.parse_card_table(table(), "cal")
    s = p.sections[0]
    assert s.payment == round(1300.6 - 2121.57 + 1640.29, 2) == 819.32                                    # the bank is debited the sum of ALL charge cells
    b = bank([(date(2026, 10, 11), 819.32, "כרטיסי אשראי ל"), (date(2026, 10, 11), 1300.6, "כרטיסי אשראי ל")])
    m = ci.match_settlements(p.sections, b)
    assert m[0].bank_key == "b0" and ci.reconcile(b, m)["matched_total"] == 819.32                         # matched on the payment, not on the header total
    items = {c.charge.merchant: c for c in ci.classify_all(p.charges) if c.charge.kind != ci.ROLLING}
    roll = [c for c in ci.classify_all(p.charges) if c.charge.kind == ci.ROLLING]
    assert [c.kind for c in roll] == [ci.CREDIT_SERVICE, ci.CREDIT_SERVICE] and not any(ci.importable(c) for c in roll)


def test_excel_loans_cash_and_sectors():
    items = {c.charge.merchant: c for c in ci.classify_all(ci.parse_card_table(table(), "cal").charges) if c.charge.kind != ci.ROLLING}
    assert items["הלוואת אקספרס"].category == "loans" and items["הלוואת אקספרס"].charge.charge == 52.84 and items["הלוואת אקספרס"].charge.amount == 2800.0
    assert items["הלוואה מחוץ למסגרת"].category == "loans" and items["הבנק"].kind == ci.CASH
    assert items["כביש חוצה צפון"].category == "transport" and items["ביטוח ישיר חיים"].rule_id == "builtin:ביטוח"          # by the merchant name; the broad sector "ביטוח ופיננסים" alone is never used
    assert items["תוכנה בע\"מ"].kind == ci.UNKNOWN


def test_excel_a_total_that_does_not_add_up_or_an_unknown_layout_is_not_ok():
    bad = table()
    bad[2] = ("עסקאות לחיוב ב-10/10/2026: 1,299.00 ₪*", None, None, None, None, None, None)
    p = ci.parse_card_table(bad)
    assert not p.ok and p.sections[0].ok is False and "1299.00" in p.problems[0] and "1300.60" in p.problems[0]
    nope = ci.parse_card_table([("a", "b"), (1, 2)])
    assert not nope.ok and nope.charges == [] and "not a recognised card table" in nope.problems[0]
    no_total = table()
    no_total[2] = ("משהו אחר", None, None, None, None, None, None)
    assert not ci.parse_card_table(no_total).ok


def test_excel_keys_are_stable_and_distinct():
    extra = [(DT(2026, 9, 1), "קפה", 10.0, 10.0, "רגילה", "מסעדות", None)] * 2
    rows = table(extra)
    rows[2] = ("עסקאות לחיוב ב-10/10/2026: 1,320.60 ₪*", None, None, None, None, None, None)
    a, b = ci.parse_card_table(rows, "cal"), ci.parse_card_table(rows, "cal")
    assert a.ok and [c.key for c in a.charges] == [c.key for c in b.charges] and len({c.key for c in a.charges}) == len(a.charges)


def test_report_script_reads_an_excel_table(tmp_path):
    mod = _script()
    parsed, items, summ, recon = mod.build(table(), "cal", None, None)
    assert parsed.ok and summ["by_kind"]["credit_service"]["count"] == 2 and summ["by_category"]["loans"] == 667.07 and recon is None


# ── matching to the bank ────────────────────────────────────────────────────────────────────────────────────────
def bank(items):
    out = []
    for i, (d, amount, desc) in enumerate(items):
        row = bi.BankRow(d, desc, amount, bi.DEBIT, 0.0, True, key=f"b{i}")
        out.append(bi.classify_row(row))
    return out


def test_a_section_is_matched_to_the_bank_settlement_of_the_same_amount_on_the_billing_date():
    p = ci.parse_card_statement(statement(), "max")
    b = bank([(date(2026, 9, 28), 1000.0, "מקס איט פיננסי"), (date(2026, 10, 15), 93.46, "מקס איט פיננסי"), (date(2026, 10, 15), 747.02, 'ישראכרט בע"מ'),
              (date(2026, 10, 15), 500.0, "מקס איט פיננסי")])
    m = ci.match_settlements(p.sections, b)
    assert [x.bank_key for x in m] == ["b0", "b1", "b2"]
    r = ci.reconcile(b, m)
    assert r["matched_total"] == 1840.48 and r["sections_without_bank_line"] == [] and r["uncovered_bank_settlements"] == {"count": 1, "total": 500.0}


def test_matching_uses_each_bank_line_once_within_a_three_day_window_and_never_forces_a_match():
    sec = lambda i, d, t: ci.Section(i, "1", d, t, t, True, 1, False)
    twins = [sec(1, date(2026, 10, 1), 100.0), sec(2, date(2026, 10, 1), 100.0)]
    one = ci.match_settlements(twins, bank([(date(2026, 10, 2), 100.0, "מקס איט")]))
    assert [m.bank_key for m in one] == ["b0", None]                                       # one bank line pays one section
    late = ci.match_settlements([sec(1, date(2026, 10, 1), 100.0)], bank([(date(2026, 10, 5), 100.0, "מקס איט")]))
    early = ci.match_settlements([sec(1, date(2026, 10, 10), 100.0)], bank([(date(2026, 10, 9), 100.0, "מקס איט")]))
    assert late[0].bank_key is None and early[0].bank_key is None                          # outside the window / before the billing date
    wrong = ci.match_settlements([sec(1, date(2026, 10, 1), 100.0)], bank([(date(2026, 10, 1), 100.01, "מקס איט")]))
    assert wrong[0].bank_key is None
    closest = ci.match_settlements([sec(1, date(2026, 10, 1), 100.0)], bank([(date(2026, 10, 3), 100.0, "מקס איט"), (date(2026, 10, 1), 100.0, "מקס איט")]))
    assert closest[0].bank_key == "b1"


def test_only_card_settlement_debits_can_be_matched():
    sec = ci.Section(1, "1", date(2026, 10, 1), 100.0, 100.0, True, 1, False)
    other = bank([(date(2026, 10, 1), 100.0, "מרכז התורה")])                                # an unknown debit of the same amount is NOT a card payment
    assert ci.match_settlements([sec], other)[0].bank_key is None


def test_pure_module_has_no_io_imports():
    import ast
    from pathlib import Path
    tree = ast.parse(Path(ci.__file__).read_text(encoding="utf-8"))
    imported = {n.names[0].name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import)}
    imported |= {(n.module or "").split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert imported <= {"__future__", "hashlib", "re", "dataclasses", "datetime", "core"}, imported


# ── the offline script ──────────────────────────────────────────────────────────────────────────────────────────
def _script():
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location("fcc_card_report", Path(__file__).parent / "scripts" / "fcc_card_statement_report.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_visual_order_hebrew_is_reversed_per_run_and_digits_latin_stay():
    mod = _script()
    assert mod.logical("ןיעידומ") == "מודיעין" and mod.logical('מ"עב') == 'בע"מ' and mod.logical("MAX Back Total") == "MAX Back Total"
    assert mod.logical("15/10/26") == "15/10/26" and mod.logical("םשה תכרב") == "ברכת השם"


def test_report_pack_with_a_bank_match_and_the_repo_guard(tmp_path):
    from pathlib import Path
    mod = _script()
    from test_fcc_bank_import import row, statement as bank_statement
    bank_text = bank_statement([row("15/10/2026", "מקס איט פיננסי", 93.46, "debit", 906.54), row("14/10/2026", "x", 1000.0, "credit", 1000.0)])
    parsed, items, summ, recon = mod.build(statement(), "max", None, bank_text)
    assert parsed.ok and recon["bank_ok"] and len(recon["matched"]) == 1 and recon["uncovered_bank_settlements"]["count"] == 0
    paths = mod.write_pack(tmp_path / "pack", parsed, items, summ, recon)
    assert [p.name for p in paths] == ["charges.csv", "summary.md", "merchants_rules_template.json"]
    md = (tmp_path / "pack" / "summary.md").read_text(encoding="utf-8")
    assert "הדוח שלם ומתיישב" in md and "התאמה לדוח הבנק" in md and "שופרסל יש חסד" in md
    csv_text = (tmp_path / "pack" / "charges.csv").read_text(encoding="utf-8-sig")
    assert "cash_withdrawal" in csv_text and "loans" in csv_text and len(csv_text.strip().splitlines()) == len(parsed.charges) + 1
    assert mod.main(["--pdf", str(tmp_path / "x.pdf"), "--card-ref", "t", "--outdir", str(Path(__file__).parent / "_nope")]) == 2


def test_max_transaction_details_export_total_line_and_billing_column():
    head = ("תאריך עסקה", "שם בית העסק", "קטגוריה", "4 ספרות אחרונות של כרטיס האשראי", "סוג עסקה", "סכום חיוב", "מטבע חיוב", "סכום עסקה מקורי", "מטבע עסקה מקורי", "תאריך חיוב")
    rows = [("שם בעל כרטיס-123",) + (None,) * 9, ("7716-MAX Back Total",) + (None,) * 9, ("09/2026",) + (None,) * 9, head,
            ("18-08-2026", "משנת יוסף", "מזון וצריכה", "7716", "רגילה", "100.5", "₪", "100.5", "₪", "15-09-2026"),
            ("19-08-2026", "בשר יפת", "מזון וצריכה", "7716", "רגילה", "50", "₪", "50", "₪", "15-09-2026"),
            (None,) * 10, ("סך הכל",) + (None,) * 9, ("150.50₪",) + (None,) * 9]
    r = ci.parse_card_table(rows, "max")
    assert r.ok and len(r.charges) == 2 and r.sections[0].card == "7716" and r.sections[0].billing_date.isoformat() == "2026-09-15"
    assert r.sections[0].total == 150.5
    rows[-1] = ("999.00₪",) + (None,) * 9
    assert not ci.parse_card_table(rows, "max").ok          # a total that the rows do not add up to blocks the file
