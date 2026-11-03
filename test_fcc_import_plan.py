"""FCC statement import plan, stage 5b — ``core.financial_control.import_plan`` (pure). Synthetic statements only.

Covers: only decided rows are written, a bank settlement / cash / transfers / reversals / rows for review are never written, a refund is a negative
expense, income carries its source and no goal, dates (a loan instalment counts on the billing date), idempotency (a second import writes nothing), what the
owner is asked (once per description, a row rule per transfer), merging bank and card, and the event / rule row fields.
"""

from __future__ import annotations

from datetime import date

from airtable_schema import CashflowRuleFields as CR
from airtable_schema import FinEventFields as EF
from airtable_schema import Tables
from core.financial_control import bank_import as bi
from core.financial_control import card_import as ci
from core.financial_control import import_plan as ip
from test_fcc_bank_import import row, statement
from test_fcc_card_import import F, iso_header, iso_total, iso_txn, card_header, table, DT

RULES = bi.owner_rules_from([{"match": "מלם מערכות", "kind": "income", "category": "עבודת אשתי", "direction": "credit"}])
NEWEST_FIRST = [
    row("09/10/2026", "הפק מזומן-בנקט", 200.0, "credit", 15600.0),
    row("08/10/2026", "חנות לא ידועה", 100.0, "debit", 15400.0),
    row("07/10/2026", "העברה-נייד", 700.0, "credit", 15500.0),
    row("06/10/2026", 'מכס ומע"מ', 300.0, "credit", 14800.0),
    row("05/10/2026", "עיריית מודיעין", 500.0, "debit", 14500.0),
    row("04/10/2026", "החזר חיוב-טכני", 1200.0, "credit", 15000.0),
    row("03/10/2026", "מרכז התורה", 1200.0, "debit", 13800.0),
    row("02/10/2026", 'ישראכרט בע"מ', 3000.0, "debit", 15000.0),
    row("01/10/2026", 'מלם מערכות בע"', 8000.0, "credit", 18000.0),
]


def bank_items(rules=RULES):
    return bi.classify(bi.parse_statement(statement(NEWEST_FIRST), "main").rows, rules)


def test_decided_rows_become_events_with_the_right_sign_category_and_source_and_an_unknown_debit_has_no_category():
    plan = ip.plan_bank(bank_items())
    got = [(e.date.day, e.kind, e.amount, e.category, e.source_name, e.origin) for e in plan.events]
    assert got == [(1, "one_time", 8000.0, None, "עבודת אשתי", "import:bank"), (5, "household_expense", 500.0, "taxes", None, "import:bank"),
                   (6, "household_expense", -300.0, "taxes", None, "import:bank"),
                   (8, "household_expense", 100.0, None, None, "import:bank")]            # the income, the tax, the VAT refund as a negative expense, and an UNKNOWN debit with no category yet
    assert all(e.key.startswith("bank:") and e.month == "2026-10" for e in plan.events)


def test_what_is_skipped_and_why_nothing_is_written_twice():
    plan = ip.plan_bank(bank_items())
    assert plan.skipped == {"card_settlement": {"count": 1, "total": 3000.0}, "reversal": {"count": 2, "total": 2400.0},
                            "needs_review": {"count": 1, "total": 700.0}, "needs_classification": {"count": 1, "total": 200.0}}
    written = {e.key for e in plan.events}
    for c in bank_items():
        if c.kind in (bi.CARD_SETTLEMENT, bi.REVERSAL, bi.NEEDS_REVIEW, bi.INCOME):
            assert c.row.key not in written                                               # a settlement, a returned charge, a transfer, a credit candidate: never


def test_the_owner_is_asked_once_per_description_and_per_transfer_row():
    plan = ip.plan_bank(bank_items())
    by = {(r.match, bool(r.row_key)): r for r in plan.pending_rules}
    assert set(by) == {("הפק מזומן-בנקט", False), ("", True)}      # a cash deposit (a credit: never income unasked), ONE row rule for the transfer — the unknown debit is classified on screen
    row_rule = by[("", True)]
    assert (row_rule.applies_to, row_rule.direction, row_rule.example_amount, row_rule.row_key.startswith("bank:")) == ("bank", "credit", 700.0, True)
    again = ip.plan_bank(bank_items(), known_rule_keys=ip.known_rule_keys([
        {"fields": {CR.MATCH: "הפק מזומן-בנקט"}}, {"fields": {CR.MATCH: "", CR.ROW_KEY: row_rule.row_key}}]))
    assert again.pending_rules == []                                                                      # already waiting in the table: not added again


def test_a_second_import_of_the_same_statement_writes_nothing():
    first = ip.plan_bank(bank_items())
    second = ip.plan_bank(bank_items(), existing_keys={e.key for e in first.events})
    assert second.events == [] and second.skipped["already_imported"] == {"count": 4, "total": 8900.0}


def test_the_same_description_is_grouped_not_repeated():
    rows = [row("03/10/2026", "מקור לא ידוע", 30.0, "credit", 250.0), row("02/10/2026", "מקור לא ידוע", 50.0, "credit", 220.0), row("01/10/2026", "x", 170.0, "credit", 170.0)]
    plan = ip.plan_bank(bi.classify(bi.parse_statement(statement(rows), "m").rows))
    src = [r for r in plan.pending_rules if r.match == "מקור לא ידוע"]
    assert len(src) == 1 and (src[0].times_seen, src[0].example_amount, src[0].last_seen) == (2, 50.0, date(2026, 10, 3))


def test_an_unknown_debit_and_an_unknown_card_purchase_are_written_without_a_category_and_a_card_refund_waits():
    rows = [row("02/10/2026", "חנות לא ידועה", 30.0, "debit", 70.0), row("01/10/2026", "x", 100.0, "credit", 100.0)]
    bank = ip.plan_bank(bi.classify(bi.parse_statement(statement(rows), "m").rows))
    assert [(e.label, e.category, e.amount) for e in bank.events] == [("חנות לא ידועה", None, 30.0)]
    f = ip.event_fields(bank.events[0])
    assert f[EF.KIND] == "household_expense" and EF.EXPENSE_CATEGORY not in f and f[EF.RAW_TEXT] == "חנות לא ידועה"
    assert ip.summarize(bank)["uncategorized"] == {"count": 1, "total": 30.0}
    card = ip.plan_card(card_items())
    assert [e.label for e in card.events if e.category is None] == ["תוכנה בע\"מ"] and card.pending_rules == []


# ── card ────────────────────────────────────────────────────────────────────────────────────────────────────────
def card_items(rules=None):
    return ci.classify_all(ci.parse_card_table(table(), "cal").charges, rules)


def test_card_lines_loans_and_fees_count_on_the_billing_date_and_cash_and_rolling_credit_are_never_written():
    plan = ip.plan_card(card_items())
    got = {e.label: e for e in plan.events}
    assert set(got) == {"כביש חוצה צפון", "ביטוח ישיר חיים", "תוכנה בע\"מ"}                                                                     # the two loan lines are recognised but NOT imported
    assert plan.skipped["loan"]["count"] == 2 and plan.skipped["loan"]["total"] > 52 and not any(e.category == "loans" for e in plan.events)
    assert got["כביש חוצה צפון"].date == date(2026, 9, 27) and got["כביש חוצה צפון"].category == "transport"                                        # a purchase: its own date
    assert plan.skipped["cash_withdrawal"] == {"count": 1, "total": 400.0} and plan.skipped["credit_service"] == {"count": 2, "total": 3761.86}
    assert got["תוכנה בע\"מ"].category is None and plan.pending_rules == []                                  # a purchase nobody classified: written "לא מסווג"


def test_an_owner_rule_turns_an_unknown_merchant_into_an_event_and_installment_purchases_use_the_billing_date():
    rules = bi.owner_rules_from([{"match": "תוכנה", "kind": "expense", "category": "communication"}])
    plan = ip.plan_card(card_items(rules))
    assert {e.label for e in plan.events} >= {"תוכנה בע\"מ"} and plan.pending_rules == []
    inst = ci.CardCharge(date(2026, 7, 5), "לאסט פרייס", 367.08, 4405.0, "3818", date(2026, 10, 11), 1, ci.REGULAR, "תשלום 4 מתוך 12")
    e = ip.plan_card([ci.ClassifiedCharge(inst, ci.EXPENSE, "clothing", "owner:0")], set()).events[0]
    assert e.date == date(2026, 10, 11) and e.month == "2026-10"


def test_merge_keeps_one_copy_of_each_event_and_adds_up_the_skips():
    a, b = ip.plan_bank(bank_items()), ip.plan_card(card_items())
    m = ip.merge(a, b, a)
    assert len(m.events) == len(a.events) + len(b.events) and len(m.pending_rules) == len(a.pending_rules) + len(b.pending_rules)
    assert m.skipped["card_settlement"]["count"] == 2 * a.skipped["card_settlement"]["count"]
    s = ip.summarize(m)
    assert s["months"]["2026-10"]["income"] == 8000.0 and s["months"]["2026-10"]["by_source"] == {"עבודת אשתי": 8000.0}
    assert s["pending_row_rules"] == 1 and s["events"] == len(m.events)


def test_event_rows_have_no_goal_a_negative_refund_the_source_note_and_a_statement_verification():
    plan = ip.plan_bank(bank_items())
    inc, tax, refund, _unknown = (ip.event_write(e, "eliyahu") for e in plan.events)
    assert inc["op"] == "post" and inc["table"] == Tables.FIN_EVENTS and EF.GOAL not in inc["fields"] and refund["fields"][EF.AMOUNT] == -300.0
    f = inc["fields"]
    assert f[EF.KIND] == "one_time" and f[EF.NOTE] == "מקור: עבודת אשתי" and f[EF.SOURCE] == "import:bank" and f[EF.VERIFICATION] == "statement"
    assert f[EF.IDEMPOTENCY_KEY] == f[EF.SOURCE_REF] == plan.events[0].key and EF.EXPENSE_CATEGORY not in f
    assert tax["fields"][EF.EXPENSE_CATEGORY] == "taxes" and EF.NOTE not in tax["fields"] and tax["audit_action"] == "fcc_import_event"


def test_pending_rule_rows_are_undecided_and_carry_context():
    plan = ip.plan_bank(bank_items())
    for r in plan.pending_rules:
        f = ip.pending_rule_fields(r)
        assert f[CR.STATUS] == "pending" and CR.KIND not in f and f[CR.APPLIES_TO] == "bank" and f[CR.LAST_SEEN] and f[CR.EXAMPLE_AMOUNT] > 0
        assert (CR.ROW_KEY in f) == bool(r.row_key) and (f[CR.MATCH] == "") == bool(r.row_key)


def test_a_card_event_carries_the_billing_date_and_the_instalments_label_but_a_loan_and_a_fee_do_not():
    from airtable_schema import FinEventFields as EF
    inst = ci.CardCharge(date(2026, 7, 5), "לאסט פרייס", 367.08, 4405.0, "3818", date(2026, 10, 11), 1, ci.REGULAR, "תשלום 4 מתוך 12")
    plain = ci.CardCharge(date(2026, 10, 5), "פיצה", 50.0, 50.0, "3818", date(2026, 11, 10), 1, ci.REGULAR, "")
    loan = ci.CardCharge(date(2026, 7, 5), "הלוואה", 700.0, 700.0, "3818", date(2026, 10, 11), 1, ci.LOAN, "תשלום 4 מתוך 12")
    ev = {e.label: e for e in ip.plan_card([ci.ClassifiedCharge(x, ci.EXPENSE, "living", "owner:0") for x in (inst, plain, loan)], set()).events}
    assert ev["לאסט פרייס"].installments and ev["לאסט פרייס"].billing == date(2026, 10, 11)
    f = ip.event_fields(ev["לאסט פרייס"], "eliyahu")
    assert f[EF.BILLING_DATE] == "2026-10-11" and f[EF.NOTE] == ip.INSTALMENTS_NOTE and f[EF.OCCURRED_AT] == "2026-10-11"
    g = ip.event_fields(ev["פיצה"], "eliyahu")
    assert g[EF.BILLING_DATE] == "2026-11-10" and g[EF.OCCURRED_AT] == "2026-10-05" and EF.NOTE not in g           # the purchase day, billed next month
    assert not ev["הלוואה"].installments and EF.NOTE not in ip.event_fields(ev["הלוואה"], "eliyahu")
