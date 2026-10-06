// Plain node + esbuild test (see package.json `npm test`); same conventions as commandCenterPresentation.test.ts.
import type { FccGoalRow } from "../types";
import { CATEGORY_LABEL, dmy, goalCardModel, headerCards } from "./fccPresentation";

const assert = {
  equal(actual: unknown, expected: unknown, message?: string) {
    if (actual !== expected) throw new Error(message ?? `expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
  },
  deepEqual(actual: unknown, expected: unknown, message?: string) {
    const a = JSON.stringify(actual), b = JSON.stringify(expected);
    if (a !== b) throw new Error(message ?? `expected ${b}, got ${a}`);
  },
};
let failures = 0;
function test(name: string, fn: () => void) {
  try { fn(); console.log(`ok - ${name}`); } catch (error) { failures += 1; console.error(`FAIL - ${name}`); console.error(error); }
}

const base: FccGoalRow = {
  goal_id: "g", title: "t", category: "income", priority: null, method: "period_sum", mode: "recurring", end_date: null,
  period_start: "2026-10-01", period_end: "2026-10-31", target: 10000, actual: 2000, remaining: 8000,
  remaining_periods: 4, dynamic_target_per_week: 2000, status: "in_progress", next_action: null,
};

test("recurring goal shows target/actual/remaining and the weekly pace", () => {
  const m = goalCardModel(base);
  assert.equal(m.kind, "numeric");
  assert.deepEqual(m.metrics.map((x) => x.label), ["יעד", "בפועל", "נשאר", "יעד דינמי לשבוע"]);
  assert.equal(m.progressPct, 20);
});

test("cumulative goal shows totals and % — weekly pace only with an explicit end date", () => {
  const cum = { ...base, mode: "cumulative" as const, method: "cumulative", target: 700000, actual: 0, remaining: 700000, dynamic_target_per_week: null };
  const noEnd = goalCardModel(cum);
  assert.deepEqual(noEnd.metrics.map((x) => x.label), ["יעד כולל", "בפועל", "נשאר", "הושלם"]);
  const withEnd = goalCardModel({ ...cum, end_date: "2026-12-31", dynamic_target_per_week: 15000 });
  assert.equal(withEnd.metrics[4].label, "קצב לשבוע עד 31/12/2026");
});

test("monthly-level goal never shows a weekly pace", () => {
  const m = goalCardModel({ ...base, mode: "monthly_level", method: "recurring_level", target: 7000, actual: 0, remaining: 7000, dynamic_target_per_week: null });
  assert.deepEqual(m.metrics.map((x) => x.label), ["יעד הפחתה לחודש", "הושג", "נשאר ליעד"]);
});

test("project goal renders no amounts at all, only status + next action + date", () => {
  const p: FccGoalRow = { ...base, category: "project", mode: "project", status: "project", target: null, actual: null, remaining: null,
    remaining_periods: null, dynamic_target_per_week: null, next_action: { title: "לקבל הערכת שווי", due_date: "2026-10-20" } };
  const m = goalCardModel(p);
  assert.equal(m.kind, "project");
  assert.deepEqual(m.metrics, []);
  assert.equal(m.progressPct, null);
  assert.deepEqual(m.nextAction, { title: "לקבל הערכת שווי", due: "20/10/2026" });
  assert.equal(goalCardModel({ ...p, next_action: null }).nextAction, null, "explicitly missing next action");
});

test("numeric goal without a target asks for one instead of showing ₪0", () => {
  const m = goalCardModel({ ...base, mode: "cumulative", status: "missing_target", target: null, actual: 0, remaining: null });
  assert.equal(m.kind, "needs_target");
  assert.deepEqual(m.metrics, []);
});

test("header cards: families are separate and the weekly card is income-only", () => {
  const cards = headerCards({ monthly_cash_improvement: 0, summary: {
    income: { target: 11500, actual: 0, remaining: 11500, dynamic_target_per_week: 4000, goals: 2 },
    debt_repaid: { target: 700000, actual: 0, remaining: 700000, dynamic_target_per_week: 0, goals: 1 },
    payment_reduction: { target: 7000, actual: 0, remaining: 7000, dynamic_target_per_week: 1750, goals: 1 } } });
  const by = Object.fromEntries(cards.map((c) => [c.key, c]));
  assert.equal(by.income_week.label, "יעד הכנסה לשבוע");
  assert.equal(by.debt.value, "₪0 / ₪700,000");
  assert.equal(by.reduction.value, "₪0 / ₪7,000");
  assert.equal(by.savings.value, "—");
  assert.equal(by.savings.hint, "לא הוגדר יעד");
});

test("labels and dates", () => {
  assert.equal(CATEGORY_LABEL.business_project, "פרויקט עסקי");
  assert.equal(dmy("2026-12-31"), "31/12/2026");
  assert.equal(dmy(null), "");
});

if (failures > 0) throw new Error(`${failures} test(s) failed`);
console.log("all fccPresentation tests passed");
