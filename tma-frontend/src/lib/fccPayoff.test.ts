// Plain node + esbuild test (see package.json `npm test`).
declare function require(id: string): { readFileSync(path: string, enc: string): string };
import type { FccLoans, FccPayoffRow, FccScenarioResult, FccScenarios } from "../types";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { PayoffEngine, ScenarioView } from "../components/FccPayoff";
import { UNKNOWN } from "./fccLoans";
import { STRATEGY_TABS, orderedRows, parseBudget, payoffCardModel, presetBudget, savingLine, scenarioDetail, scenarioRows } from "./fccPayoff";

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

const row = (o: Partial<FccPayoffRow>): FccPayoffRow => ({
  id: "x", name: "x", lender: null, loan_type: null, amount_to_close: null, interest_rate: null, monthly_cash_freed: null, months_remaining: null,
  estimated_remaining_payments: null, estimated_future_cost: null, future_cost_exact: false, cost_saving: null, cost_saving_exact: false, no_saving: false,
  data_inconsistent: false, data_suspicious: false, data_issue: null, annual_interest_burden: null,
  scores: { interest: null, cash: null, closure: null, time: null }, balanced_score: null,
  score_coverage: 0, score_coverage_label: "0/4", missing_factors: ["interest", "cash", "closure", "time"], partial: true, ...o,
});

// Fixtures follow the engine's formulas: cost = monthly × months − closure; burden = closure × rate; saving = cost − known fee.
const kal = row({ id: "k", name: "כאל", amount_to_close: 55342, interest_rate: 12.05, monthly_cash_freed: 1189, months_remaining: 63,
  estimated_remaining_payments: 74907, estimated_future_cost: 74907 - 55342, future_cost_exact: true, cost_saving: 74907 - 55342, cost_saving_exact: true,
  annual_interest_burden: 6668.71, scores: { interest: 100, cash: 40, closure: 70, time: 80 }, balanced_score: 72.5, score_coverage: 1, score_coverage_label: "4/4", missing_factors: [], partial: false });
const max = row({ id: "m", name: "מקס", amount_to_close: 3060, interest_rate: 12.85, monthly_cash_freed: 784, months_remaining: 4,
  estimated_remaining_payments: 3136, estimated_future_cost: 76, future_cost_exact: false, cost_saving: 76, cost_saving_exact: false,
  annual_interest_burden: 393.21, scores: { interest: 100, cash: 20, closure: 100, time: 0 }, balanced_score: 62.1, score_coverage: 1, score_coverage_label: "4/4", missing_factors: [], partial: false });
const bad = row({ id: "b", name: "הפועלים (נתונים ישנים)", amount_to_close: 118400, interest_rate: 6.25, monthly_cash_freed: 2600, months_remaining: 45,
  estimated_remaining_payments: 117000, data_inconsistent: true, data_issue: "inconsistent", annual_interest_burden: 7400,
  scores: { interest: 0, cash: 100, closure: 0, time: 60 }, balanced_score: 40, score_coverage: 1, score_coverage_label: "4/4", missing_factors: [], partial: false });
const susp = row({ id: "s", name: "חשודה", amount_to_close: 118400, interest_rate: 6, monthly_cash_freed: 2600, months_remaining: 46,
  estimated_remaining_payments: 119600, data_suspicious: true, data_issue: "suspicious", annual_interest_burden: 7104,
  scores: { interest: 0, cash: 100, closure: 0, time: 70 }, balanced_score: 41, score_coverage: 1, score_coverage_label: "4/4", missing_factors: [], partial: false });
const noRate = row({ id: "n", name: "ללא ריבית", amount_to_close: 20000, monthly_cash_freed: 500, months_remaining: 20,
  scores: { interest: null, cash: 10, closure: 60, time: 30 }, balanced_score: 33.3, score_coverage: 0.75, score_coverage_label: "3/4", missing_factors: ["interest"] });
const empty = row({ id: "e", name: "משכנתא" });

const ranks = { balanced: ["k", "m", "s", "b", "n", "e"], interest: ["m", "k", "n", "e", "b", "s"].filter((x) => !["b", "s"].includes(x)).concat(["b", "s"]).slice(0, 6),
  cash: ["b", "s", "k", "m", "n", "e"], savings: ["k", "m", "b", "s", "n", "e"] };
const loans = { items: [], summary: {}, rankings: {}, goal: { target: 700000, closed: 0, remaining: 700000, active_closure_balance: 78402 },
  payoff: { weights: { interest: 0.3, cash: 0.3, closure: 0.25, time: 0.15 }, items: [empty, noRate, susp, bad, max, kal], rankings: ranks } } as unknown as FccLoans;

// Scenario fixtures are COMPUTED from the loan rows (never hand-typed), so they obey the engine's own invariants.
const mkRes = (budget: number, picked: FccPayoffRow[], o: Partial<FccScenarioResult> = {}): FccScenarioResult => {
  const used = picked.reduce((a, r) => a + (r.amount_to_close ?? 0), 0);
  const known = picked.filter((r) => r.monthly_cash_freed != null);
  const costs = picked.filter((r) => r.cost_saving != null);
  return { budget, used, remaining_budget: budget - used, closed_count: picked.length,
    closed: picked.map((r) => ({ id: r.id, name: r.name, amount_to_close: r.amount_to_close ?? 0, monthly_cash_freed: r.monthly_cash_freed, cost_saving: r.cost_saving, cost_saving_exact: r.cost_saving_exact })),
    debt_removed: used,
    monthly_cash_released: picked.length === 0 ? 0 : known.length ? known.reduce((a, r) => a + (r.monthly_cash_freed ?? 0), 0) : null,
    future_cost_saved: picked.length === 0 ? 0 : costs.length ? costs.reduce((a, r) => a + (r.cost_saving ?? 0), 0) : null,
    future_cost_saved_exact: picked.length > 0 && picked.every((r) => r.cost_saving_exact),
    partial: picked.some((r) => r.monthly_cash_freed == null || r.cost_saving == null),
    skipped_over_budget: [], excluded_unknown_amount: [], excluded_no_data: [], ...o };
};
const res = (o: Partial<FccScenarioResult>) => mkRes(100000, [kal, max], o);
const scenarios: FccScenarios = { budget: 100000,
  strategies: { balanced: res({}), interest: mkRes(100000, [kal], { skipped_over_budget: ["a"], excluded_unknown_amount: ["e"], partial: true, monthly_cash_released: null }),
    cash: res({}), savings: mkRes(100000, []) },
  optimal: { cash: res({}), saved: null } };

test("four strategies; switching re-orders the same loans; unknown/excluded loans stay last", () => {
  assert.equal(STRATEGY_TABS.map((t) => t.label).join(), "מאוזן,ריבית,פינוי תזרים,חיסכון בעלות");
  assert.equal(orderedRows(loans, "savings").map((r) => r.id).join(), "k,m,b,s,n,e");
  assert.equal(orderedRows(loans, "cash")[0].id, "b");
  assert.equal(orderedRows({ ...loans, payoff: undefined } as FccLoans, "balanced").length, 0);
});

test("no percentage 'efficiency' metric exists in the card, the tabs or the types", () => {
  const m = payoffCardModel(kal, "savings", 1);
  assert.ok(!m.figures.some((f) => f.label.includes("יעילות")));
  assert.ok(!STRATEGY_TABS.some((t) => t.label.includes("יעילות") || t.basis.includes("יעילות")));
  assert.ok(!JSON.stringify(m).includes("307%") && !JSON.stringify(m).includes("annualized"));
});

test("card figures: the four facts, then continuation cost and annual interest burden (both marked as estimates)", () => {
  const f = Object.fromEntries(payoffCardModel(kal, "balanced", 1).figures.map((x) => [x.label, x.value]));
  assert.equal(f["יתרת סילוק"], "₪55,342");
  assert.equal(f["ריבית"], "12.05%");
  assert.equal(f["החזר חודשי שמתפנה"], "₪1,189");
  assert.equal(f["חודשים שנותרו"], "63");
  assert.equal(f["עלות המשך משוערת"], "₪19,565");
  assert.equal(f["עומס ריבית שנתי משוער"], "משוער ₪6,669");
  const g = Object.fromEntries(payoffCardModel(max, "balanced", 2).figures.map((x) => [x.label, x.value]));
  assert.equal(g["עלות המשך משוערת"], "משוער ₪76");        // fee unknown -> an estimate, not exact
});

test("cost saving wording: net only when the fee is known; never a positive 'saving' after the fee", () => {
  assert.equal(savingLine(kal), "חיסכון בעלות (נטו אחרי עמלה): ₪19,565");
  assert.equal(savingLine(max), "חיסכון בעלות משוער: ₪76");
  assert.equal(savingLine(row({ no_saving: true, cost_saving: 0, cost_saving_exact: true, estimated_future_cost: 50 })), "אין חיסכון חיובי אחרי עמלת פירעון");
  assert.equal(savingLine(noRate), `חיסכון בעלות: ${UNKNOWN}`);
  assert.equal(savingLine(bad), null);
  assert.equal(savingLine(susp), null);
});

test("explanation text states the facts (strategy-led), not a verdict", () => {
  assert.equal(payoffCardModel(kal, "interest", 1).why, "ריבית גבוהה (12.05%) · מפנה ₪1,189 לחודש · דורשת ₪55,342 לסגירה · 63 תשלומים נותרו");
  assert.ok(payoffCardModel(kal, "savings", 1).why.startsWith("חיסכון בעלות ₪19,565 ·"));
  assert.ok(payoffCardModel(max, "savings", 1).why.startsWith("חיסכון בעלות משוער ₪76 ·"));
  assert.ok(payoffCardModel(kal, "balanced", 1).why.startsWith("ציון מאוזן 73"));
});

test("inconsistent data: flagged for checking, no cost and no saving computed, the four facts stay visible", () => {
  const m = payoffCardModel(bad, "savings", 3);
  assert.equal(m.issueTag, "נתונים לא עקביים");
  assert.ok(m.issueText?.startsWith("נתונים לא עקביים — דורש בדיקה"));
  const f = Object.fromEntries(m.figures.map((x) => [x.label, x.value]));
  assert.equal(f["עלות המשך משוערת"], "לא מחושב");
  assert.equal(m.savingLine, null);
  assert.equal(f["יתרת סילוק"], "₪118,400");
  assert.equal(f["ריבית"], "6.25%");
  assert.equal(f["החזר חודשי שמתפנה"], "₪2,600");
  assert.equal(f["חודשים שנותרו"], "45");
  assert.ok(!m.why.includes("חיסכון בעלות"));
});

test("suspicious data: warned, left out of the savings ranking, the four facts stay visible", () => {
  const m = payoffCardModel(susp, "savings", 4);
  assert.equal(m.issueTag, "נתונים חשודים");
  assert.ok(m.issueText?.includes("יש לבדוק את נתוני ההלוואה"));
  assert.equal(m.savingLine, null);
  assert.equal(m.figures.find((x) => x.label === "יתרת סילוק")?.value, "₪118,400");
  assert.ok(orderedRows(loans, "savings").map((r) => r.id).indexOf("s") > orderedRows(loans, "savings").map((r) => r.id).indexOf("m"));
});

test("score coverage and missing factors are shown; partial data does not fake confidence", () => {
  const m = payoffCardModel(noRate, "balanced", 5);
  assert.ok(m.scoreLabel.includes("כיסוי נתונים 3/4"), m.scoreLabel);
  assert.equal(m.missingLabel, "חסר: ריבית");
  assert.ok(m.partial);
  assert.equal(payoffCardModel(kal, "balanced", 1).missingLabel, null);
});

test("fully partial loan: no fake zeroes, unknown everywhere, no score", () => {
  const m = payoffCardModel(empty, "balanced", 6);
  assert.ok(m.figures.every((f) => f.value === UNKNOWN), JSON.stringify(m.figures));
  assert.equal(m.scoreLabel, `ציון משוקלל: ${UNKNOWN}`);
  assert.equal(m.why, "אין מספיק נתונים לדירוג");
});

test("budget input parsing and the ₪700K preset", () => {
  assert.equal(parseBudget("₪700,000"), 700000);
  assert.equal(parseBudget(" 55342.5 "), 55342.5);
  assert.equal(parseBudget("0"), null);
  assert.equal(parseBudget("-5"), null);
  assert.equal(parseBudget("abc"), null);
  assert.equal(parseBudget(""), null);
  const p = presetBudget(loans);
  assert.equal(p?.amount, 700000);
  assert.equal(p?.label, "תקציב יעד סגירת חובות: ₪700,000");
  assert.equal(presetBudget({ ...loans, goal: null } as FccLoans), null);
});

test("budget simulator view: four strategies + two combinations, detail, notes, unknown stays unknown", () => {
  assert.equal(scenarioRows(scenarios).length, 6);
  assert.equal(scenarioRows(scenarios)[1].released, UNKNOWN);
  assert.equal(scenarioRows(scenarios)[3].released, "₪0");                    // nothing closed = a real zero
  assert.equal(scenarioRows(scenarios)[3].label, "חיסכון בעלות");
  assert.equal(scenarioRows(scenarios)[5].closed, UNKNOWN);                   // combination not computed
  const d = scenarioDetail(scenarios.strategies.interest);
  assert.ok(d.notes.some((n) => n.includes("אין פרעון חלקי")));
  assert.ok(d.notes.some((n) => n.includes("בלי יתרת סילוק")));
  assert.ok(d.notes.some((n) => n.includes("נתונים חלקיים")));
  assert.ok(scenarioDetail(res({ excluded_no_data: ["x", "y"] })).notes.some((n) => n.includes("2 הלוואות ללא נתון לאסטרטגיה הזו")));
  assert.equal(scenarioDetail(scenarios.strategies.balanced).lines[5].value, "משוער ₪19,641");   // 19,565 exact + 76 estimated -> estimate
  const html = renderToStaticMarkup(createElement(ScenarioView, { scenarios, strategy: "interest" }));
  assert.equal((html.match(/<tr/g) ?? []).length, 7);
  assert.ok(html.includes("fcc-pay__row--on"));
});

test("scenario numbers are internally consistent: used ≤ budget, used + remaining = budget, no loan above the budget", () => {
  const all = [...Object.values(scenarios.strategies), scenarios.optimal.cash].filter((x): x is FccScenarioResult => x != null);
  for (const r of all) {
    assert.ok(r.used <= r.budget, "used must not exceed budget");
    assert.equal(r.used + r.remaining_budget, r.budget);
    assert.ok(r.closed.every((c) => c.amount_to_close <= r.budget));
    assert.equal(r.closed.reduce((a, c) => a + c.amount_to_close, 0), r.used);
    assert.equal(scenarioDetail(r).lines[1].value, `₪${new Intl.NumberFormat("he-IL").format(r.used)}`);
  }
});

const forbidden = ["מומלץ", "מומלצת", "מומלצים", "כדאי", "עדיף", "הכי טוב", "תסגור", "recommended", "winner", "יעילות", "307%"];

test("render smoke: cards, explanation, warnings, budget box, preset — no recommendation language, no efficiency metric", () => {
  const html = renderToStaticMarkup(createElement(PayoffEngine, { loans }));
  assert.equal((html.match(/fcc-pay__card/g) ?? []).length, 6);
  assert.ok(html.includes("למה כאן"));
  assert.ok(html.includes("מנוע פרעון מוקדם"));
  assert.ok(html.includes("חיסכון בעלות"));
  assert.ok(html.includes("נתונים לא עקביים — דורש בדיקה"));
  assert.ok(html.includes("נתונים חשודים"));
  assert.ok(html.includes("תקציב יעד סגירת חובות: ₪700,000"));
  assert.ok(html.includes("לא סכום שקיים כרגע במזומן"));
  assert.ok(html.includes("כיסוי נתונים 3/4"));
  assert.ok(!/₪0[^,0-9]/.test(html), "no fake zero for unknown values");
  const all = html + renderToStaticMarkup(createElement(ScenarioView, { scenarios, strategy: "balanced" }));
  for (const w of forbidden) assert.ok(!all.includes(w), `forbidden wording: ${w}`);
});

test("390px smoke (css): payoff blocks can shrink and wrap", () => {
  const css = require("node:fs").readFileSync("src/index.css", "utf8");
  const block = css.slice(css.indexOf("early-payoff engine"));
  assert.ok(block.includes("minmax(0, 1fr)") && block.includes("min-inline-size: 0") && block.includes("overflow-wrap: anywhere"));
  assert.ok(!/(^|[^-])width:\s*\d+px/m.test(block), "no fixed pixel width");
});

if (failures > 0) throw new Error(`${failures} test(s) failed`);
console.log("all fccPayoff tests passed");
