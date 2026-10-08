// Plain node + esbuild test (see package.json `npm test`).
declare function require(id: string): { readFileSync(path: string, enc: string): string };
import type { FccLoan, FccLoans, FccTurn } from "../types";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { LoanClosePanel, LoansSection } from "../components/FccLoans";
import { CLOSE_BUTTON, CLOSE_WORDS, FILTERS, UNKNOWN, applyTurn, canClose, closeView, type CloseFlow, compareRows, filterLoans, futureCostLabel, loanCardModel, loanGoalModel, loanHeaderCards, pct, sortLoans, togglePick, val } from "./fccLoans";

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

test("debt goal block passes the SSOT numbers through (unknown closed stays unknown)", () => {
  const g = loanGoalModel(loans);
  assert.equal(g?.lines[0].value, "₪700,000");
  assert.equal(g?.lines[1].value, UNKNOWN);
  assert.equal(g?.pct, null);
  assert.equal(g?.pctLabel, UNKNOWN);
  assert.equal(loanGoalModel({ ...loans, goal: null }), null);
});

test("progress bar: 0 closed is a clean 0%, partial closed is a rounded %, never above 100", () => {
  const withClosed = (closed: number) => loanGoalModel({ ...loans, goal: { target: 700000, closed, remaining: 700000 - closed, active_closure_balance: 150000 } });
  assert.equal(withClosed(0)?.pct, 0);
  assert.equal(withClosed(0)?.pctLabel, "0%");
  assert.equal(withClosed(0)?.lines[1].value, "₪0");
  assert.equal(withClosed(100000)?.pctLabel, "14%");
  assert.equal(withClosed(900000)?.pct, 100);
  assert.equal(withClosed(100000)?.lines.map((l) => l.label).join(), "יעד,נסגר עד כה,נשאר,יתרות סילוק פעילות");
});

test("compact loan card: three headline figures first, meta line, emphasised freed-cash line", () => {
  const m = loanCardModel(full);
  assert.equal(m.keyRows.map((r) => r.label).join(), "יתרת סילוק,החזר חודשי,ריבית");
  assert.equal(m.metaRows.map((r) => r.label).join(), "תשלומים שנותרו,תאריך סיום");
  assert.equal(m.keyRows[0].value, "₪100,000");
  assert.ok(m.freedKnown);
  assert.equal(loanCardModel(empty).freedKnown, false);
});

test("badges: partial only when a headline figure is missing; unclassified/unknown-status are muted", () => {
  assert.equal(loanCardModel(mk({ missing: ["months_remaining"] })).incomplete, false);
  assert.equal(loanCardModel(mk({ missing: ["interest_rate"] })).incomplete, true);
  const tags = loanCardModel(mk({ status_unknown: true, missing: ["monthly_payment"] })).tags;
  assert.equal(tags.map((t) => t.text).join(), "לא סווג,סטטוס לא הוגדר,נתונים חלקיים");
  assert.ok(tags.every((t) => t.tone === "muted"));
  assert.equal(loanCardModel(full).tags.length, 1);
});

test("compare selection holds at most two; a third replaces the oldest; toggling off works", () => {
  assert.equal(togglePick([], "a").join(), "a");
  assert.equal(togglePick(["a"], "b").join(), "a,b");
  assert.equal(togglePick(["a", "b"], "c").join(), "b,c");
  assert.equal(togglePick(["a", "b"], "a").join(), "b");
});

test("rate card says it is weighted by closure balance, plus coverage only when partial", () => {
  assert.equal(loanHeaderCards(loans)[2].hint, "משוקללת לפי יתרת סילוק · מבוסס על 2 מתוך 3 הלוואות");
  const all = loanHeaderCards({ ...loans, summary: { ...loans.summary, coverage: { ...loans.summary.coverage, interest_rate: 3 } } });
  assert.equal(all[2].hint, "משוקללת לפי יתרת סילוק");
});

const html = renderToStaticMarkup(createElement(LoansSection, { loans: { ...loans, goal: { target: 700000, closed: 0, remaining: 700000, active_closure_balance: 150000 } } }));

test("390px smoke (render): one compact card per active loan, small checkbox control, no full-width compare button", () => {
  assert.equal((html.match(/class="fcc-loan"/g) ?? []).length, 3);
  assert.equal((html.match(/type="checkbox"/g) ?? []).length, 3);
  assert.ok(!html.includes(">השווה<"));
  assert.ok(html.includes('aria-valuenow="0"') && html.includes(">0%<"));
  assert.ok(html.includes("fcc-loan__freed"));
  assert.ok(html.includes('class="fcc-unknown"'), "unknown values get the muted style");
  assert.ok(html.includes("fcc-tag--muted"));
  assert.ok(html.includes("משוקללת לפי יתרת סילוק"));
  assert.ok(!/₪0[^,0-9]/.test(html.replace("נסגר עד כה</dt><dd>₪0", "")), "no fake zero for unknown values");
});

test("390px smoke (css): loan blocks can shrink — grids use minmax(0,1fr), long text wraps, no fixed widths", () => {
  const css = require("node:fs").readFileSync("src/index.css", "utf8");
  const block = css.slice(css.indexOf("FCC loans & debt"));
  assert.ok(block.length > 500);
  assert.ok(block.includes("repeat(3, minmax(0, 1fr))"));
  assert.ok(block.includes("min-inline-size: 0"));
  assert.ok(block.includes("overflow-wrap: anywhere"));
  assert.ok(!/(^|[^-])width:\s*\d+px/m.test(block), "no fixed pixel width");
  assert.ok(!/min-(inline-size|width):\s*[1-9]\d{2,}px/.test(block), "no wide min-width");
});

const turn = (state: FccTurn["state"], message = "m"): FccTurn => ({ state, message });
const flow = (t: FccTurn | null, receipt: string | null = null): CloseFlow => ({ loanId: "recL1", turn: t, receipt });

test("review offers confirm + edit + cancel (cancel reaches the server)", () => {
  const v = closeView(flow(turn("review")));
  assert.equal(v.confirm, "אשר ורשום"); assert.ok(v.canEdit && v.cancelsDraft && !v.showInput && !v.dismissOnly);
});

test("ask / unrelated show the answer input and can cancel the draft", () => {
  for (const s of ["ask", "unrelated"] as const) {
    const v = closeView(flow(turn(s)));
    assert.ok(v.showInput && v.cancelsDraft && v.confirm === null && !v.canEdit);
  }
});

test("a partial failure offers a retry (the confirmed draft stays on the server) and can still be cancelled", () => {
  const v = closeView(flow(turn("partial_failure")));
  assert.equal(v.confirm, "נסה שוב"); assert.ok(v.cancelsDraft);
});

test("terminal info states only offer to close the panel", () => {
  for (const s of ["info", "denied", "duplicate", "clarify"] as const) {
    const v = closeView(flow(turn(s)));
    assert.ok(v.dismissOnly && v.confirm === null && !v.showInput && !v.cancelsDraft, s);
  }
});

test("executed -> receipt + overview refresh; cancelled -> panel closes without refresh; other turns keep the panel", () => {
  const done = applyTurn(flow(turn("review")), { state: "executed", message: "נרשם ✓" });
  assert.equal(done.refresh, true); assert.equal(done.flow?.receipt, "נרשם ✓"); assert.equal(done.flow?.turn, null);
  assert.ok(closeView(done.flow!).dismissOnly);
  const cancelled = applyTurn(flow(turn("review")), turn("cancelled"));
  assert.equal(cancelled.flow, null); assert.equal(cancelled.refresh, false);
  const next = applyTurn(flow(turn("review")), turn("ask"));
  assert.equal(next.flow?.turn?.state, "ask"); assert.equal(next.refresh, false);
});

test("the words sent to the server are the shared FCC ones", () => {
  assert.equal(CLOSE_WORDS.confirm, "אשר"); assert.equal(CLOSE_WORDS.edit, "ערוך"); assert.equal(CLOSE_WORDS.cancel, "בטל");
});

test("only an active loan can be closed", () => {
  assert.ok(canClose({ active: true })); assert.ok(!canClose({ active: false }));
});

const noop = () => undefined;
const panel = (f: CloseFlow, busy = false) => renderToStaticMarkup(createElement(LoanClosePanel, {
  flow: f, busy, error: null, onSend: noop, onDismiss: noop }));

test("review panel renders the server's review text and the three actions, nothing else", () => {
  const html = panel(flow(turn("review", "📋 סגירת הלוואה\n• הלוואה: פועלים")));
  assert.ok(html.includes("סגירת הלוואה") && html.includes("פועלים"));
  assert.ok(html.includes("אשר ורשום") && html.includes("ערוך") && html.includes("בטל"));
  assert.ok(!html.includes("<textarea") && !html.includes("<input"));
});

test("ask panel renders one input; busy disables the buttons (no double confirm)", () => {
  assert.equal((panel(flow(turn("ask", "כמה שילמת?"))).match(/<textarea/g) || []).length, 1);
  const busy = panel(flow(turn("review")), true);
  assert.ok(!busy.includes("<button type=\"button\" class=\"boss-button boss-button--primary boss-bubble--action\">"));
  assert.equal((busy.match(/disabled=""/g) || []).length >= 3, true);
});

test("the receipt panel has no confirm button, so a done closing cannot be confirmed twice", () => {
  const html = panel(flow(null, "נרשם ✓"));
  assert.ok(html.includes("נרשם ✓") && !html.includes("אשר ורשום") && html.includes("סגור"));
  assert.ok(CLOSE_BUTTON.length > 0);
});

if (failures > 0) throw new Error(`${failures} test(s) failed`);
console.log("all fccLoans tests passed");
