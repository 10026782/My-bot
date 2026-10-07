// Plain node + esbuild test (see package.json `npm test`).
import type { FccLoan, FccLoans } from "../types";
import { FILTERS, UNKNOWN, compareRows, filterLoans, futureCostLabel, loanCardModel, loanGoalModel, loanHeaderCards, pct, sortLoans, val } from "./fccLoans";

const assert = {
  equal(actual: unknown, expected: unknown, message?: string) {
    if (actual !== expected) throw new Error(message ?? `expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
  },
  ok(v: unknown, message?: string) { if (!v) throw new Error(message ?? "expected truthy"); },
};
let failures = 0;
function test(name: string, fn: () => void) {
  try { fn(); console.log(`ok - ${name}`); } catch (error) { failures += 1; console.error(`FAIL - ${name}`); console.error(error); }
}

const mk = (o: Partial<FccLoan>): FccLoan => ({
  id: "x", name: "x", lender: null, loan_type: null, related_asset: null, related_asset_name: null, original_amount: null,
  current_balance: null, early_closure_balance: null, interest_rate: null, monthly_payment: null, payments_remaining: null,
  end_date: null, early_repayment_fee: null, active: true, months_remaining: null, estimated_total_remaining_payments: null,
  estimated_future_cost: null, future_cost_exact: false, monthly_cash_freed_if_closed: null, annual_interest_cost: null,
  status_unknown: false, missing: [], ...o,
});

const full = mk({ id: "a", name: "פועלים", lender: "בנק הפועלים", loan_type: "פרטית", related_asset: "r1", related_asset_name: "דירה",
  early_closure_balance: 100000, interest_rate: 6.25, monthly_payment: 2600, payments_remaining: 45, months_remaining: 45,
  end_date: "2030-07-27", monthly_cash_freed_if_closed: 2600, estimated_future_cost: 17000, future_cost_exact: true });
const business = mk({ id: "b", name: "כאל", loan_type: "עסקית", early_closure_balance: 50000, interest_rate: 12, monthly_payment: 900,
  months_remaining: 60, monthly_cash_freed_if_closed: 900, estimated_future_cost: 4000, future_cost_exact: false, missing: ["x"] });
const empty = mk({ id: "c", name: "משכנתא", missing: ["early_closure_balance", "interest_rate", "monthly_payment", "months_remaining"] });
const closed = mk({ id: "d", name: "סגורה", active: false, loan_type: "פרטית" });

const loans: FccLoans = {
  items: [empty, business, full, closed],
  summary: { total_active_loans: 3, total_original_amount: null, total_early_closure_balance: 150000, total_monthly_payments: 3500,
    weighted_average_interest_rate: 8.17, total_estimated_future_cost: null,
    total_monthly_cash_freed_if_all_closed: 3500, incomplete_count: 1, unknown_status_count: 1, future_cost_exact: false, by_type: {}, by_asset: [],
    coverage: { original_amount: 0, early_closure_balance: 2, monthly_payment: 2, future_cost: 2, interest_rate: 2 } },
  rankings: { high_interest: ["b", "a", "c"], cash_freed: ["a", "b", "c"], small_balance: ["b", "a", "c"] },
  goal: { target: 700000, closed: null, remaining: 700000, active_closure_balance: 150000 },
};

test("filters: all excludes closed, types split, unclassified only under all", () => {
  assert.equal(filterLoans(loans.items, "all").length, 3);
  assert.equal(filterLoans(loans.items, "private").map((l) => l.id).join(), "a");
  assert.equal(filterLoans(loans.items, "business").map((l) => l.id).join(), "b");
  assert.equal(filterLoans(loans.items, "mortgage").length, 0);
  assert.equal(FILTERS.length, 4);
});

test("partial loan: no fake zeroes, shows לא הוגדר", () => {
  const m = loanCardModel(empty);
  assert.ok(m.rows.every((r) => r.value === UNKNOWN), JSON.stringify(m.rows));
  assert.equal(m.freedLine, `החזר חודשי: ${UNKNOWN}`);
  assert.ok(m.incomplete);
  assert.equal(val(null), UNKNOWN);
  assert.equal(pct(null), UNKNOWN);
  assert.equal(val(0), "₪0");   // a real zero is still shown as a value
});

test("uncategorized loan is labelled לא סווג", () => {
  assert.equal(loanCardModel(empty).typeLabel, "לא סווג");
  assert.equal(loanCardModel(full).typeLabel, "פרטית");
});

test("linked asset row only when an asset is linked", () => {
  assert.equal(loanCardModel(full).assetLine, "נכס: דירה");
  assert.equal(loanCardModel(business).assetLine, null);
  assert.equal(loanCardModel(mk({ related_asset: "r9" })).assetLine, "נכס: נכס מקושר");
});

test("freed-cash line and lender", () => {
  assert.equal(loanCardModel(full).freedLine, "בסגירה משתחררים ₪2,600 לחודש");
  assert.equal(loanCardModel(full).lender, "בנק הפועלים");
});

test("header cards show coverage and unknown instead of zero", () => {
  const cards = loanHeaderCards(loans);
  assert.equal(cards.length, 4);
  assert.equal(cards[0].value, "₪150,000");
  assert.equal(cards[0].hint, "מבוסס על 2 מתוך 3 הלוואות");
  assert.equal(cards[2].value, "8.17%");
  const none = loanHeaderCards({ ...loans, summary: { ...loans.summary, total_early_closure_balance: null, weighted_average_interest_rate: null, total_monthly_payments: null, total_monthly_cash_freed_if_all_closed: null } });
  assert.ok(none.every((c) => c.value === UNKNOWN));
});

test("ranking modes reorder without choosing for the user", () => {
  const act = filterLoans(loans.items, "all");
  assert.equal(sortLoans(act, loans, "high_interest").map((l) => l.id).join(), "b,a,c");
  assert.equal(sortLoans(act, loans, "cash_freed").map((l) => l.id).join(), "a,b,c");
  assert.equal(sortLoans(act, loans, "small_balance").map((l) => l.id).join(), "b,a,c");
});

test("comparison of two loans: six rows, approximate cost flagged, no recommendation", () => {
  const rows = compareRows(full, business);
  assert.equal(rows.map((r) => r.label).join(), "יתרה,ריבית,החזר חודשי,חודשים שנותרו,תזרים שמתפנה,עלות עתידית משוערת");
  assert.equal(rows[0].a, "₪100,000");
  assert.ok(rows[5].b.startsWith("≈") && rows[5].b.includes("משוער"));
  assert.equal(futureCostLabel(full), "₪17,000");
  assert.equal(futureCostLabel(empty), UNKNOWN);
  assert.equal(compareRows(full, empty)[1].b, UNKNOWN);
});

test("unknown-status loan stays visible with the badge flag; a confirmed one does not", () => {
  const unk = mk({ id: "u", name: "ללא סטטוס", status_unknown: true });
  assert.ok(filterLoans([unk, full], "all").some((l) => l.id === "u"));
  assert.equal(loanCardModel(unk).statusUnknown, true);
  assert.equal(loanCardModel(full).statusUnknown, false);
});

test("debt goal block passes the SSOT numbers through", () => {
  const g = loanGoalModel(loans);
  assert.equal(g?.lines[0].value, "₪700,000");
  assert.equal(g?.lines[1].value, UNKNOWN);   // nothing closed yet is "unknown/none", never invented
  assert.equal(loanGoalModel({ ...loans, goal: null }), null);
});

if (failures > 0) throw new Error(`${failures} test(s) failed`);
console.log("all fccLoans tests passed");
