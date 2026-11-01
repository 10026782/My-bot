"""FCC bank import, stage 5a — ``core.financial_control.bank_import`` (pure). Synthetic statements only (no real account data in the repo).

Covers: parsing the Hapoalim-style text layout (bidi marks, row-number artifact lines, a page break with a repeated header), the balance-chain
check, the column cross-check, conflicts / broken chains / unparsed lines (never silently fixed), idempotency keys, rule matching (token
boundaries, owner rules first), returned-charge pairing, card settlements apart from spending, and the report.
"""

from __future__ import annotations

from datetime import date

from core.financial_control import bank_import as bi

RLM = "‏"
HEADER_COLS = (45, 62)       # end offsets of the "זכות" / "חובה" header words


def header() -> str:
    line = [" "] * 130
    for word, end in (('יתרה בש"ח', 31), ("זכות", HEADER_COLS[0]), ("חובה", HEADER_COLS[1]), ("פעולה", 104), ("תאריך", 125)):
        for i, ch in enumerate(word):
            line[end - len(word) + i] = ch
    return "".join(line).rstrip()


def row(day: str, desc: str, amount: float, side: str, balance: float, marks: bool = False) -> str:
    line = [" "] * 130
    def put(text: str, end: int):
        for i, ch in enumerate(text):
            line[end - len(text) + i] = ch
    put("##", 2)
    bal = f"₪{balance:,.2f}"
    put(bal, 32)
    put(f"{amount:,.2f}", 44 if side == "credit" else 60)
    put(desc, 104)
    put(f"{RLM}{day}{RLM}" if marks else day, 125)
    return "".join(line).rstrip()


def statement(rows: list[str], pages: int = 1) -> str:
    """rows are given newest first, as the bank prints them; each is followed by the row-number artifact line."""
    chunks = []
    per = max(1, -(-len(rows) // pages))
    for p in range(pages):
        part = rows[p * per:(p + 1) * per]
        chunks.append("\n".join([RLM + "19/10/2026   bankhapoalim.co.il", "", header()] + [x + "\n1" for x in part]))
    return "\f".join(chunks)


# newest first. balances: start 10,000 (before 01/10) ->
# 01/10 credit salary 8,000 => 18,000 ; 02/10 debit card 3,000 => 15,000 ; 03/10 debit 1,200 charge => 13,800 ; 04/10 credit return 1,200 => 15,000 ; 05/10 debit 500 => 14,500
ROWS = [
    row("05/10/2026", "עיריית מודיעין", 500.00, "debit", 14500.00),
    row("04/10/2026", "החזר חיוב-טכני", 1200.00, "credit", 15000.00),
    row("03/10/2026", "מרכז התורה", 1200.00, "debit", 13800.00),
    row("02/10/2026", 'ישראכרט בע"מ', 3000.00, "debit", 15000.00),
    row("01/10/2026", "מלם מערכות בע\"", 8000.00, "credit", 18000.00),
]


def test_parses_rows_oldest_first_with_verified_direction_and_artifacts_ignored():
    res = bi.parse_statement(statement(ROWS), "main")
    assert res.ok and res.period == (date(2026, 10, 1), date(2026, 10, 5))
    assert [(r.date.day, r.direction, r.amount) for r in res.rows] == [(1, "credit", 8000.0), (2, "debit", 3000.0), (3, "debit", 1200.0), (4, "credit", 1200.0), (5, "debit", 500.0)]
    assert [r.balance for r in res.rows][-1] == 14500.0
    assert res.rows[1].verified and res.rows[1].description == 'ישראכרט בע"מ'
    assert res.summary["rows"] == 5 and res.summary["chain_breaks"] == 0 and res.summary["conflicts"] == 0


def test_oldest_row_has_no_older_neighbour_so_it_relies_on_the_column_and_says_so():
    res = bi.parse_statement(statement(ROWS))
    first = res.rows[0]
    assert first.direction == "credit" and not first.verified and set(first.flags) == {"no_neighbour", "column_only"}
    assert res.ok and res.summary["unchecked"] == 1 and res.summary["verified"] == 4


def test_bidi_marks_a_page_break_and_a_repeated_header_do_not_change_the_result():
    one = bi.parse_statement(statement(ROWS, pages=1))
    two = bi.parse_statement(statement([r.replace("05/10/2026", RLM + "05/10/2026" + RLM) for r in ROWS], pages=3))
    assert [(r.date, r.amount, r.direction) for r in one.rows] == [(r.date, r.amount, r.direction) for r in two.rows]


def test_a_missing_row_breaks_the_chain_and_the_statement_is_not_ok():
    rows = [ROWS[0], ROWS[1], ROWS[3], ROWS[4]]                   # the 03/10 debit is missing between two rows
    res = bi.parse_statement(statement(rows))
    assert not res.ok and res.summary["chain_breaks"] >= 1
    assert any("chain_break" in r.flags for r in res.rows)


def test_a_column_that_disagrees_with_the_balance_is_a_conflict_never_guessed():
    wrong = row("02/10/2026", 'ישראכרט בע"מ', 3000.00, "credit", 15000.00)      # printed in the credit column but the balance fell
    res = bi.parse_statement(statement([ROWS[0], ROWS[1], ROWS[2], wrong, ROWS[4]]))
    r = next(x for x in res.rows if x.date.day == 2)
    assert "conflict" in r.flags and not r.verified and r.direction == "debit"        # arithmetic wins, the conflict is reported
    assert not res.ok and res.summary["conflicts"] == 1


def test_a_line_without_exactly_one_amount_is_reported_not_dropped():
    bad = statement(ROWS) + "\n" + "##   ₪100.00   1.00   2.00      תנועה מוזרה      06/10/2026"
    res = bi.parse_statement(bad)
    assert len(res.unparsed) == 1 and not res.ok and len(res.rows) == 5


def test_positive_and_negative_balances_and_empty_input():
    res = bi.parse_statement(statement([row("02/10/2026", "x", 100.0, "debit", -50.0), row("01/10/2026", "y", 150.0, "credit", 50.0)]))
    assert [r.balance for r in res.rows] == [50.0, -50.0] and res.rows[1].verified
    empty = bi.parse_statement("nothing here")
    assert empty.rows == [] and not empty.ok


def test_keys_are_stable_distinct_per_account_and_per_balance():
    a = bi.parse_statement(statement(ROWS), "main").rows
    b = bi.parse_statement(statement(ROWS), "main").rows
    c = bi.parse_statement(statement(ROWS), "other").rows
    assert [r.key for r in a] == [r.key for r in b] and not set(r.key for r in a) & set(r.key for r in c)
    twin = bi.parse_statement(statement([row("02/10/2026", "קפה", 20.0, "debit", 80.0), row("02/10/2026", "קפה", 20.0, "debit", 100.0), row("01/10/2026", "x", 120.0, "credit", 120.0)])).rows
    assert len({r.key for r in twin}) == 3                       # two identical same-day debits stay distinct (the balance differs)


def test_classification_builtin_rules_use_token_boundaries_and_direction():
    rows = bi.parse_statement(statement(ROWS), "m").rows
    kinds = {r.description: bi.classify_row(r) for r in rows}
    assert kinds['ישראכרט בע"מ'].kind == bi.CARD_SETTLEMENT
    assert kinds["עיריית מודיעין"].kind == bi.EXPENSE and kinds["עיריית מודיעין"].category == "taxes"
    assert kinds["מרכז התורה"].kind == bi.UNKNOWN and kinds["מרכז התורה"].rule_id is None                  # an institution: never guessed
    assert kinds["מלם מערכות בע\""].kind == bi.INCOME and kinds["מלם מערכות בע\""].category is None        # a credit: income only once a source is assigned
    mk = lambda d, side: bi.BankRow(date(2026, 10, 1), d, 10.0, side, 0.0, True)
    assert bi.classify_row(mk("מע\"מ", "debit")).category == "taxes" and bi.classify_row(mk("מכס ומע\"מ", "credit")).kind == bi.REFUND
    assert bi.classify_row(mk("מעמדות", "debit")).kind == bi.UNKNOWN                                          # a rule never matches inside a longer word
    assert bi.classify_row(mk('הו"ק הלוואה', "debit")).category == "loans" and bi.classify_row(mk('הו"ק הלואה קרן', "debit")).category == "loans"   # both spellings
    assert bi.classify_row(mk("ביטוח לאומי", "credit")).category == "קצבאות" and bi.classify_row(mk("ביטוח לאומי", "debit")).category == "taxes"
    # owner decision: every transfer, in or out, is marked for a one-by-one check — never assumed to be the owner's own account
    assert bi.classify_row(mk("העברה-נייד", "credit")).kind == bi.NEEDS_REVIEW == bi.classify_row(mk("העברה-נייד", "debit")).kind


def test_income_needs_the_owners_explicit_approval_and_a_transfer_is_neutral_only_by_an_owner_rule():
    mk = lambda d, side, amount=10.0: bi.BankRow(date(2026, 10, 1), d, amount, side, 0.0, True)
    for desc in ("הפק מזומן-בנקט", "bitהעברת כסף", "העברה-נייד", "זיכוי מלאומי", "קצבת ילדים", "מלם מערכות"):
        assert bi.classify_row(mk(desc, "credit")).kind in (bi.INCOME, bi.NEEDS_REVIEW) and not bi.importable(bi.classify_row(mk(desc, "credit")))      # never income by itself
    rules = bi.owner_rules_from([{"match": "מלם מערכות", "kind": "income", "category": "משכורת", "direction": "credit"},
                                 {"match": "זיכוי מלאומי", "kind": "transfer", "direction": "credit"}])
    got = bi.classify_row(mk("מלם מערכות בע\"", "credit"), rules)
    assert got.kind == bi.INCOME_APPROVED and got.category == "משכורת" and bi.importable(got)
    assert bi.classify_row(mk("זיכוי מלאומי", "credit"), rules).kind == bi.TRANSFER
    assert not bi.importable(bi.classify_row(mk("מלם מערכות", "credit"), bi.owner_rules_from([{"match": "מלם מערכות", "kind": "income"}])))   # approved but no source: not written


def test_every_transfer_and_bit_is_marked_for_a_one_by_one_check_in_both_directions():
    mk = lambda d, side: bi.BankRow(date(2026, 10, 1), d, 10.0, side, 0.0, True, key="k:" + d + side)
    for desc in ("העברה", "העברה-נייד", "העברה מיידית", "העב' לאחר-נייד", "bitהעברת כסף", "bit", "ביט", "פייבוקס", "העברת כסף"):
        for side in ("credit", "debit"):
            c = bi.classify_row(mk(desc, side))
            assert c.kind == bi.NEEDS_REVIEW and c.category is None and not bi.importable(c), (desc, side)
    for desc in ("זיכוי מלאומי", "זיכוי מדיסקונט"):                                       # a credit from another bank
        assert bi.classify_row(mk(desc, "credit")).kind == bi.NEEDS_REVIEW
    assert bi.classify_row(mk("העברה/הפקדה-טל", "credit")).kind == bi.INCOME            # a cash deposit is not a transfer
    assert bi.classify_row(mk("הפק מזומן-בנקט", "credit")).kind == bi.INCOME


def test_a_single_row_can_be_settled_by_its_key_without_touching_its_neighbours():
    rows = [bi.BankRow(date(2026, 10, d), "העברה-נייד", 100.0 * d, "credit", 0.0, True, key=f"bank:{d}") for d in (1, 2, 3)]
    rules = bi.owner_rules_from([{"key": "bank:2", "kind": "income", "category": "הכנסה מבן משפחה"}, {"key": "bank:3", "kind": "transfer"},
                                 {"key": "", "kind": "income"}, {"match": "", "kind": "income"}])
    assert len(rules) == 2
    got = [bi.classify_row(r, rules) for r in rows]
    assert [c.kind for c in got] == [bi.NEEDS_REVIEW, bi.INCOME_APPROVED, bi.TRANSFER] and got[1].category == "הכנסה מבן משפחה" and got[1].rule_id.startswith("owner:")
    assert [bi.importable(c) for c in got] == [False, True, False]
    both = bi.owner_rules_from([{"match": "העברה נייד", "kind": "transfer"}, {"key": "bank:1", "kind": "income", "category": "x"}])
    assert bi.classify_row(rows[0], both).kind == bi.INCOME_APPROVED                       # a rule for one row beats a rule for the description


def test_a_tax_refund_gives_back_the_category_and_is_never_income():
    mk = lambda d, side: bi.BankRow(date(2026, 7, 24), d, 1249.0, side, 0.0, True)
    for desc in ('מכס ומע"מ', 'מע"מ', "מס הכנסה"):
        c = bi.classify_row(mk(desc, "credit"))
        assert c.kind == bi.REFUND and c.category == "taxes" and bi.importable(c), desc
    assert bi.classify_row(mk('מע"מ', "debit")).kind == bi.EXPENSE                        # paying VAT is still an expense
    s = bi.summarize([bi.classify_row(mk('מכס ומע"מ', "credit")), bi.classify_row(mk("העברה", "credit")), bi.classify_row(mk("bit", "debit"))])
    assert s["review"] == {"count": 2, "credit": 1249.0, "debit": 1249.0}


def test_only_decided_rows_are_importable():
    mk = lambda d, side: bi.BankRow(date(2026, 10, 1), d, 10.0, side, 0.0, True)
    assert bi.importable(bi.classify_row(mk("עיריית מודיעין", "debit")))                 # an expense with a category
    for desc in ("מרכז התורה", 'ישראכרט בע"מ'):                                          # unknown debit / card settlement
        assert not bi.importable(bi.classify_row(mk(desc, "debit")))
    rules = bi.owner_rules_from([{"match": "מרכז התורה", "kind": "expense", "category": "institutions"}, {"match": "גמח", "kind": "expense"}])
    assert bi.importable(bi.classify_row(mk("מרכז התורה רחו", "debit"), rules)) and not bi.importable(bi.classify_row(mk("גמח", "debit"), rules))   # no category: not importable


def test_card_payments_stay_out_of_spending_and_are_reported_as_pending_itemization():
    s = bi.summarize(bi.classify(bi.parse_statement(statement(ROWS), "m").rows))
    assert s["pending_card_total"] == 3000.0 and s["months"]["2026-10"]["spending_candidates"] == 500.0 and s["importable"] == 1


def test_owner_rules_win_and_invalid_ones_are_skipped():
    rules = bi.owner_rules_from([
        {"match": "מרכז התורה", "kind": "expense", "category": "institutions"},
        {"match": "מלם מערכות", "kind": "income_candidate", "category": "משכורת", "direction": "credit"},
        {"match": "ישראכרט", "kind": "expense", "category": "living"},            # overrides the built-in card rule
        {"match": "", "kind": "expense"}, {"match": "x", "kind": "nonsense"}, {"match": "y", "kind": "unknown"}, {"match": "z", "kind": "expense", "direction": "up"},
    ])
    assert len(rules) == 3
    rows = bi.parse_statement(statement(ROWS), "m").rows
    got = {r.description: bi.classify_row(r, rules) for r in rows}
    assert got["מרכז התורה"].kind == bi.EXPENSE and got["מרכז התורה"].category == "institutions" and got["מרכז התורה"].rule_id == "owner:0"
    assert got['ישראכרט בע"מ'].kind == bi.EXPENSE and got["מלם מערכות בע\""].category == "משכורת"


def test_returned_charge_cancels_both_halves_and_an_unpaired_one_stays_income():
    items = bi.classify(bi.parse_statement(statement(ROWS), "m").rows)
    rev = [c for c in items if c.kind == bi.REVERSAL]
    assert sorted(c.row.description for c in rev) == ["החזר חיוב-טכני", "מרכז התורה"] and rev[0].paired_key == rev[1].row.key
    lone = bi.classify(bi.parse_statement(statement([row("04/10/2026", "החזר חיוב-טכני", 1200.0, "credit", 1300.0),
                                                     row("01/10/2026", "x", 700.0, "debit", 100.0)]), "m").rows)
    assert [c.kind for c in lone if c.row.description == "החזר חיוב-טכני"] == [bi.INCOME]       # no debit to cancel: not silently dropped


def test_reversal_needs_the_same_amount_inside_the_window_and_pairs_each_debit_once():
    rows = [bi.BankRow(date(2026, 10, d), desc, 100.0, side, 0.0, True, key=f"k{i}") for i, (d, desc, side) in enumerate(
        [(1, "ספק", "debit"), (2, "ספק", "debit"), (3, "החזר חיוב", "credit"), (28, "החזר חיוב", "credit")])]
    out = bi.classify(rows)
    assert [c.kind for c in out] == [bi.UNKNOWN, bi.REVERSAL, bi.REVERSAL, bi.INCOME]          # closest debit wins; the 28th is outside the window


def test_summary_separates_spending_card_settlements_and_income_and_lists_what_to_map():
    res = bi.parse_statement(statement(ROWS), "m")
    s = bi.summarize(bi.classify(res.rows))
    oct_ = s["months"]["2026-10"]
    assert oct_["card_settlements"] == 3000.0 and oct_["income_candidates"] == 8000.0 and oct_["spending_candidates"] == 500.0 and oct_["other"] == 2400.0
    assert s["by_kind"]["reversal"]["debit"] == 1200.0 == s["by_kind"]["reversal"]["credit"]
    assert [u["description"] for u in s["unmapped"]] == ['מלם מערכות בע"']                          # the unknown credit; the reversal pair is not "unmapped"


def test_pure_module_has_no_io_imports():
    import ast
    from pathlib import Path
    tree = ast.parse(Path(bi.__file__).read_text(encoding="utf-8"))
    imported = {n.names[0].name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import)}
    imported |= {(n.module or "").split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert imported <= {"__future__", "hashlib", "re", "dataclasses", "datetime"}, imported


# ── the offline report script ──────────────────────────────────────────────────────────────────────────────────
def _script():
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location("fcc_bank_report", Path(__file__).parent / "scripts" / "fcc_bank_statement_report.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_report_pack_is_written_outside_the_repo_and_lists_what_to_map(tmp_path):
    mod = _script()
    txt = tmp_path / "s.txt"
    txt.write_text(statement(ROWS), encoding="utf-8")
    out = tmp_path / "pack"
    assert mod.main(["--text", str(txt), "--account-ref", "t", "--outdir", str(out)]) == 0
    csv_text = (out / "classified.csv").read_text(encoding="utf-8-sig")
    assert "card_settlement" in csv_text and "reversal" in csv_text and len(csv_text.strip().splitlines()) == 6
    summary = (out / "summary.md").read_text(encoding="utf-8")
    assert "הדוח שלם ומתיישב" in summary and "מלם מערכות" in summary
    import json
    tpl = json.loads((out / "rules_template.json").read_text(encoding="utf-8"))
    assert [t["match"] for t in tpl] == ['מלם מערכות בע"'] and tpl[0]["kind"] == ""
    rules = tmp_path / "rules.json"
    rules.write_text(json.dumps([{"match": "מלם מערכות", "kind": "income_candidate", "category": "משכורת", "direction": "credit"}]), encoding="utf-8")
    out2 = tmp_path / "pack2"
    assert mod.main(["--text", str(txt), "--account-ref", "t", "--outdir", str(out2), "--rules", str(rules)]) == 0
    assert json.loads((out2 / "rules_template.json").read_text(encoding="utf-8")) == []


def test_report_pack_marks_every_transfer_for_a_one_by_one_check(tmp_path):
    mod = _script()
    rows = [row("03/10/2026", "העברה-נייד", 700.0, "credit", 10700.0), row("02/10/2026", "bitהעברת כסף", 300.0, "debit", 10000.0),
            row("01/10/2026", "הפק מזומן-בנקט", 10300.0, "credit", 10300.0)]
    txt = tmp_path / "s.txt"
    txt.write_text(statement(rows), encoding="utf-8")
    out = tmp_path / "pack"
    assert mod.main(["--text", str(txt), "--account-ref", "t", "--outdir", str(out)]) == 0
    review = (out / "review_one_by_one.csv").read_text(encoding="utf-8-sig").strip().splitlines()
    assert len(review) == 3 and "העברה-נייד" in review[1] + review[2] and "bit" in review[1] + review[2] and "הפק מזומן" not in "".join(review)    # a cash deposit is not a transfer
    assert "לבדיקה אחת-אחת: העברות וביט (2)" in (out / "summary.md").read_text(encoding="utf-8")


def test_report_refuses_an_outdir_inside_the_repo_and_flags_an_incomplete_statement(tmp_path):
    from pathlib import Path
    mod = _script()
    txt = tmp_path / "s.txt"
    txt.write_text(statement(ROWS), encoding="utf-8")
    assert mod.main(["--text", str(txt), "--account-ref", "t", "--outdir", str(Path(__file__).parent / "_nope")]) == 2
    broken = tmp_path / "b.txt"
    broken.write_text(statement([ROWS[0], ROWS[1], ROWS[3], ROWS[4]]), encoding="utf-8")
    assert mod.main(["--text", str(broken), "--account-ref", "t", "--outdir", str(tmp_path / "p3")]) == 1
    assert "אינו שלם" in (tmp_path / "p3" / "summary.md").read_text(encoding="utf-8")
