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

test("income hierarchy: weekly card shows the source minimum and the rest from other sources", () => {
  const cards = headerCards({ monthly_cash_improvement: 0, summary: {
    income: { target: 15000, actual: 1000, remaining: 14000, dynamic_target_per_week: 4083.33, goals: 1,
      weekly_sources_required: 1500, other_sources_needed: 2583.33,
      sources: [{ goal_id: "t", title: "הכנסה מנסיעות", period_type: "weekly", target: 2500, actual: 1000, remaining: 1500 }] } } });
  const by = Object.fromEntries(cards.map((c) => [c.key, c]));
  assert.equal(by.income.value, "₪1,000 / ₪15,000");
  assert.equal((by.income_week.hint ?? "").includes("הכנסה מנסיעות: נשאר ₪1,500 מתוך ₪2,500 השבוע"), true);
  assert.equal((by.income_week.hint ?? "").includes("ממקורות אחרים: ₪2,583"), true);
});

test("weekly card source line shows its direct costs and net", () => {
  const cards = headerCards({ monthly_cash_improvement: 0, summary: {
    income: { target: 15000, actual: 1340, remaining: 13660, dynamic_target_per_week: 3678, goals: 1,
      weekly_sources_required: 2350, other_sources_needed: 1328,
      sources: [{ goal_id: "t", title: "נסיעות", period_type: "weekly", target: 2500, actual: 150, remaining: 2350,
        direct_costs: 100, net: 50 }] } } });
  const hint = cards.find((c) => c.key === "income_week")?.hint ?? "";
  assert.equal(hint.includes("נסיעות: נשאר ₪2,350 מתוך ₪2,500 השבוע (הוצאות ישירות -₪100 · נטו ₪50)"), true);
});

test("a source goal card says it is inside the parent and has no weekly pace of its own", () => {
  const m = goalCardModel({ ...base, mode: "recurring", is_source: true, period_type: "weekly", target: 2500, actual: 0, remaining: 2500 });
  assert.equal((m.sourceNote ?? "").includes("לא מתווסף"), true);
  assert.equal(m.metrics.some((x) => x.label === "יעד דינמי לשבוע"), false);
});

test("gross -> direct costs -> net shows only when there are direct costs", () => {
  const withCost = headerCards({ monthly_cash_improvement: 0, summary: {
    income: { target: 15000, actual: 3000, remaining: 12000, direct_costs: 500, net: 2500, dynamic_target_per_week: 3500, goals: 1 } } });
  const hint = withCost.find((c) => c.key === "income")?.hint ?? "";
  assert.equal(hint, "ברוטו ₪3,000 · הוצאות ישירות -₪500 · נטו ₪2,500");
  assert.equal(withCost.find((c) => c.key === "income")?.value, "₪2,500 / ₪15,000");   // progress is net
  const without = headerCards({ monthly_cash_improvement: 0, summary: {
    income: { target: 15000, actual: 3000, remaining: 12000, direct_costs: 0, net: 3000, dynamic_target_per_week: 3500, goals: 1 } } });
  assert.equal(without.find((c) => c.key === "income")?.hint, undefined);
  const m = goalCardModel({ ...base, mode: "recurring", target: 15000, actual: 3000, remaining: 12000, direct_costs: 500, net: 2500 });
  assert.deepEqual(m.metrics.slice(-3).map((x) => x.label), ["ברוטו", "הוצאות ישירות", "נטו"]);
});

test("household spend and missing receipts are separate cards that appear only when relevant", () => {
  const none = headerCards({ monthly_cash_improvement: 0, summary: {} });
  assert.equal(none.some((c) => c.key === "household" || c.key === "receipts"), false);
  const cards = headerCards({ monthly_cash_improvement: 0, summary: {},
    household: { month_total: 2400 }, receipts: { missing_count: 3, missing_amount: 410 } });
  assert.equal(cards.find((c) => c.key === "household")?.value, "₪2,400");
  const r = cards.find((c) => c.key === "receipts");
  assert.equal(r?.value, "3");
  assert.equal((r?.hint ?? "").includes("₪410"), true);
});

test("recurring obligations show three separate numbers only when there are active obligations", () => {
  assert.equal(headerCards({ monthly_cash_improvement: 0, summary: {} }).some((c) => c.key.startsWith("obligations")), false);
  const cards = headerCards({ monthly_cash_improvement: 0, summary: {},
    obligations: { total_monthly: 303.33, flagged_count: 2, flagged_monthly: 170, cancel_pending: 1, potential_saving: 100, count: 4 } });
  const by = Object.fromEntries(cards.map((c) => [c.key, c]));
  assert.equal(by.obligations.value, "₪303");
  assert.equal(by.obligations_flagged.value, "2");
  assert.equal(by.obligations_saving.value, "₪100");
  assert.equal((by.obligations_flagged.hint ?? "").includes("1 ממתינות לביטול בפועל"), true);
});

test("savings card says monthly only for a monthly allocation (legacy cumulative keeps the plain label)", () => {
  const monthly = headerCards({ monthly_cash_improvement: 0, summary: { savings: { target: 10000, actual: 2000, remaining: 8000, dynamic_target_per_week: 0, goals: 1, mode: "recurring" } } });
  const m = monthly.find((c) => c.key === "savings");
  assert.equal(m?.label, "חיסכון חודשי");
  assert.equal(m?.value, "₪2,000 / ₪10,000");
  const legacy = headerCards({ monthly_cash_improvement: 0, summary: { savings: { target: 10000, actual: 0, remaining: 10000, dynamic_target_per_week: 0, goals: 1, mode: "cumulative" } } });
  assert.equal(legacy.find((c) => c.key === "savings")?.label, "חיסכון");
});

test("labels and dates", () => {
  assert.equal(CATEGORY_LABEL.business_project, "פרויקט עסקי");
  assert.equal(dmy("2026-12-31"), "31/12/2026");
  assert.equal(dmy(null), "");
});

if (failures > 0) throw new Error(`${failures} test(s) failed`);
console.log("all fccPresentation tests passed");
