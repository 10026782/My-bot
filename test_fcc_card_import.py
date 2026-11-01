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
