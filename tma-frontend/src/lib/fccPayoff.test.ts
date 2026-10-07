// Plain node + esbuild test (see package.json `npm test`).
declare function require(id: string): { readFileSync(path: string, enc: string): string };
import type { FccLoans, FccPayoffRow, FccScenarioResult, FccScenarios } from "../types";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { PayoffEngine, ScenarioView } from "../components/FccPayoff";
import { UNKNOWN } from "./fccLoans";
import { STRATEGY_TABS, orderedRows, parseBudget, payoffCardModel, presetBudget, ratioPct, scenarioDetail, scenarioRows } from "./fccPayoff";

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
  estimated_remaining_payments: null, estimated_future_cost: null, future_cost_exact: false, monthly_cash_efficiency: null, annualized_cash_release: null,
  annual_interest_burden: null, scores: { interest: null, cash: null, closure: null, time: null }, balanced_score: null,
  score_coverage: 0, score_coverage_label: "0/4", missing_factors: ["interest", "cash", "closure", "time"], partial: true, ...o,
});

const kal = row({ id: "k", name: "כאל", amount_to_close: 55342, interest_rate: 12.05, monthly_cash_freed: 1189, months_remaining: 63,
  estimated_future_cost: 19565, future_cost_exact: true, monthly_cash_efficiency: 0.0215, annualized_cash_release: 0.2578,
  scores: { interest: 100, cash: 40, closure: 70, time: 80 }, balanced_score: 72.5, score_coverage: 1, score_coverage_label: "4/4", missing_factors: [], partial: false });
const max = row({ id: "m", name: "מקס", amount_to_close: 3060, interest_rate: 12.85, monthly_cash_freed: 784, months_remaining: 4,
  monthly_cash_efficiency: 0.256, annualized_cash_release: 3.07, scores: { interest: 100, cash: 20, closure: 100, time: 0 }, balanced_score: 62.1,
  estimated_future_cost: 76, future_cost_exact: false, score_coverage: 1, score_coverage_label: "4/4", missing_factors: [], partial: false });
const noRate = row({ id: "n", name: "ללא ריבית", amount_to_close: 20000, monthly_cash_freed: 500, months_remaining: 20,
  scores: { interest: null, cash: 10, closure: 60, time: 30 }, balanced_score: 33.3, score_coverage: 0.75, score_coverage_label: "3/4", missing_factors: ["interest"] });
const empty = row({ id: "e", name: "משכנתא" });

const ranks = { balanced: ["k", "m", "n", "e"], interest: ["m", "k", "n", "e"], cash: ["m", "k", "n", "e"].reverse().filter((x) => x !== "e").concat("e"), efficiency: ["m", "k", "n", "e"] };
const loans = { items: [], summary: {}, rankings: {}, goal: { target: 700000, closed: 0, remaining: 700000, active_closure_balance: 78402 },
  payoff: { weights: { interest: 0.3, cash: 0.3, closure: 0.25, time: 0.15 }, items: [empty, noRate, max, kal], rankings: ranks } } as unknown as FccLoans;

// Scenario fixtures are COMPUTED from the loan rows (never hand-typed), so they obey the engine's own invariants.
const mkRes = (budget: number, picked: FccPayoffRow[], o: Partial<FccScenarioResult> = {}): FccScenarioResult => {
  const used = picked.reduce((a, r) => a + (r.amount_to_close ?? 0), 0);
  const known = picked.filter((r) => r.monthly_cash_freed != null);
  const costs = picked.filter((r) => r.estimated_future_cost != null);
  return { budget, used, remaining_budget: budget - used, closed_count: picked.length,
    closed: picked.map((r) => ({ id: r.id, name: r.name, amount_to_close: r.amount_to_close ?? 0, monthly_cash_freed: r.monthly_cash_freed, estimated_future_cost: r.estimated_future_cost, future_cost_exact: r.future_cost_exact })),
    debt_removed: used,
    monthly_cash_released: picked.length === 0 ? 0 : known.length ? known.reduce((a, r) => a + (r.monthly_cash_freed ?? 0), 0) : null,
    future_cost_saved: picked.length === 0 ? 0 : costs.length ? costs.reduce((a, r) => a + (r.estimated_future_cost ?? 0), 0) : null,
    future_cost_saved_exact: picked.length > 0 && picked.every((r) => r.future_cost_exact),
    partial: picked.some((r) => r.monthly_cash_freed == null || r.estimated_future_cost == null),
    skipped_over_budget: [], excluded_unknown_amount: [], ...o };
};
const res = (o: Partial<FccScenarioResult>) => mkRes(100000, [kal, max], o);
const scenarios: FccScenarios = { budget: 100000,
  strategies: { balanced: res({}), interest: mkRes(100000, [kal], { skipped_over_budget: ["a"], excluded_unknown_amount: ["e"], partial: true, monthly_cash_released: null }),
    cash: res({}), efficiency: mkRes(100000, []) },
  optimal: { cash: res({}), saved: null } };

test("strategy switch re-orders the same loans; unknown-score loans stay last", () => {
  assert.equal(orderedRows(loans, "balanced").map((r) => r.id).join(), "k,m,n,e");
  assert.equal(orderedRows(loans, "interest").map((r) => r.id).join(), "m,k,n,e");
  assert.equal(STRATEGY_TABS.map((t) => t.label).join(), "מאוזן,ריבית,פינוי תזרים,יעילות סילוק");
  assert.equal(orderedRows({ ...loans, payoff: undefined } as FccLoans, "balanced").length, 0);
});

test("explanation text states the facts (strategy-led), not a verdict", () => {
  const m = payoffCardModel(kal, "interest", 1);
  assert.equal(m.why, "ריבית גבוהה (12.05%) · מפנה ₪1,189 לחודש · דורשת ₪55,342 לסגירה · 63 תשלומים נותרו");
  assert.ok(payoffCardModel(kal, "efficiency", 1).why.startsWith("יעילות פינוי תזרים 26% בשנה"));
  assert.ok(payoffCardModel(kal, "balanced", 1).why.startsWith("ציון מאוזן 73"));
});

test("score coverage and missing factors are shown; partial data does not fake confidence", () => {
  const m = payoffCardModel(noRate, "balanced", 3);
  assert.ok(m.scoreLabel.includes("כיסוי נתונים 3/4"), m.scoreLabel);
  assert.equal(m.missingLabel, "חסר: ריבית");
  assert.ok(m.partial);
  assert.equal(payoffCardModel(kal, "balanced", 1).missingLabel, null);
});

test("fully partial loan: no fake zeroes, unknown everywhere, no score", () => {
  const m = payoffCardModel(empty, "balanced", 4);
  assert.ok(m.figures.every((f) => f.value === UNKNOWN), JSON.stringify(m.figures));
  assert.equal(m.scoreLabel, `ציון משוקלל: ${UNKNOWN}`);
  assert.equal(m.why, "אין מספיק נתונים לדירוג");
  assert.equal(ratioPct(null), UNKNOWN);
});

test("numeric truth: annualised cash release = monthly × 12 ÷ closure (huge balance + small payment ≈ 1.16%, not 26%)", () => {
  const huge = row({ amount_to_close: 1234567, monthly_cash_freed: 1189, annualized_cash_release: (1189 * 12) / 1234567, months_remaining: 63 });
  assert.equal(ratioPct(huge.annualized_cash_release), "1.16%");
  const f = Object.fromEntries(payoffCardModel(huge, "efficiency", 1).figures.map((x) => [x.label, x.value]));
  assert.equal(f["יעילות פינוי תזרים שנתית"], "1.16%");
  assert.equal(f["יתרת סילוק"], "₪1,234,567");
  assert.equal(f["החזר חודשי שמתפנה"], "₪1,189");
  for (const r of [kal, max]) {            // fixtures themselves must obey the formula
    assert.equal(ratioPct(r.annualized_cash_release), ratioPct(((r.monthly_cash_freed as number) * 12) / (r.amount_to_close as number)));
  }
  assert.equal(ratioPct(kal.annualized_cash_release), "26%");
});

test("figures: closure, rate, monthly released, months, annual efficiency %, future cost (marked משוער when not exact)", () => {
  const f = Object.fromEntries(payoffCardModel(max, "balanced", 2).figures.map((x) => [x.label, x.value]));
  assert.equal(f["יתרת סילוק"], "₪3,060");
  assert.equal(f["יעילות פינוי תזרים שנתית"], "307%");
  assert.equal(f["עלות עתידית משוערת"], "משוער ₪76");
  assert.equal(payoffCardModel(kal, "balanced", 1).figures[5].value, "₪19,565");
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
  assert.equal(scenarioRows(scenarios)[5].closed, UNKNOWN);                   // combination not computed
  const d = scenarioDetail(scenarios.strategies.interest);
  assert.ok(d.notes.some((n) => n.includes("אין פרעון חלקי")));
  assert.ok(d.notes.some((n) => n.includes("בלי יתרת סילוק")));
  assert.ok(d.notes.some((n) => n.includes("נתונים חלקיים")));
  assert.equal(scenarioDetail(scenarios.strategies.balanced).lines[5].value, "משוער ₪19,641");
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
    const d = scenarioDetail(r);
    assert.equal(d.lines[1].value, `₪${new Intl.NumberFormat("he-IL").format(r.used)}`);
  }
});

const forbidden = ["מומלץ", "מומלצת", "מומלצים", "כדאי", "עדיף", "הכי טוב", "תסגור", "recommended", "winner"];

test("render smoke: engine shows cards, explanation, budget box, preset — and no recommendation language", () => {
  const html = renderToStaticMarkup(createElement(PayoffEngine, { loans }));
  assert.equal((html.match(/fcc-pay__card/g) ?? []).length, 4);
  assert.ok(html.includes("למה כאן"));
  assert.ok(html.includes("מנוע פרעון מוקדם"));
  assert.ok(html.includes("תקציב יעד סגירת חובות: ₪700,000"));
  assert.ok(html.includes("לא סכום שקיים כרגע במזומן"));
  assert.ok(html.includes("כיסוי נתונים 3/4"));
  assert.ok(html.includes("נתונים חלקיים"));
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
