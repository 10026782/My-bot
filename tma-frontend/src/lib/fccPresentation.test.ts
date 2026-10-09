// Plain node + esbuild test (see package.json `npm test`); same conventions as commandCenterPresentation.test.ts.
import type { FccGoalRow, FccSavingsRelease } from "../types";
import { CATEGORY_LABEL, dmy, goalCardModel, headerCards, savingsFollowUp, savingsReleaseModel } from "./fccPresentation";

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

test("savings card is a standing monthly allocation vs target (legacy cumulative keeps the plain label)", () => {
  const monthly = headerCards({ monthly_cash_improvement: 0, summary: { savings: { target: 5000, actual: 3000, remaining: 2000, dynamic_target_per_week: 0, goals: 1, mode: "monthly_level" } } });
  const m = monthly.find((c) => c.key === "savings");
  assert.equal(m?.label, "הפרשה חודשית לחיסכון");
  assert.equal(m?.value, "₪3,000 / ₪5,000");
  assert.equal((m?.hint ?? "").includes("לא מתאפס"), true);
  const card = goalCardModel({ ...base, mode: "monthly_level", category: "savings", target: 5000, actual: 3000, remaining: 2000 });
  assert.deepEqual(card.metrics.map((x) => x.label), ["יעד הפרשה חודשית", "מופרש כרגע לחודש", "חסר ליעד"]);
  const withDeposits = goalCardModel({ ...base, mode: "monthly_level", category: "savings", target: 5000, actual: 3000, remaining: 2000,
    deposited_month: 1000, gap_month: 2000, gap_last_month: 3000 });
  assert.deepEqual(withDeposits.metrics.slice(3).map((x) => x.label), ["הופקד בפועל החודש", "פער החודש", "פער בחודש שעבר"]);
  const hinted = headerCards({ monthly_cash_improvement: 0, summary: { savings: { target: 5000, actual: 3000, remaining: 2000, dynamic_target_per_week: 0, goals: 1,
    mode: "monthly_level", deposited_month: 1000, gap_month: 2000, gap_last_month: 3000 } } }).find((c) => c.key === "savings");
  assert.equal((hinted?.hint ?? "").includes("הופקד החודש ₪1,000 · פער ₪2,000"), true);
  assert.equal((hinted?.hint ?? "").includes("פער בחודש שעבר ₪3,000"), true);
  const legacy = headerCards({ monthly_cash_improvement: 0, summary: { savings: { target: 10000, actual: 0, remaining: 10000, dynamic_target_per_week: 0, goals: 1, mode: "cumulative" } } });
  assert.equal(legacy.find((c) => c.key === "savings")?.label, "חיסכון");
});

test("labels and dates", () => {
  assert.equal(CATEGORY_LABEL.business_project, "פרויקט עסקי");
  assert.equal(dmy("2026-12-31"), "31/12/2026");
  assert.equal(dmy(null), "");
});

const rel = (o: Partial<FccSavingsRelease> = {}): FccSavingsRelease => ({ income_net: 10000, income_target: 15000, fixed_level: 8000, shortfall: 5000, from_fixed: 3000, extra: 0,
  available: 3000, deposited: 0, remaining: 3000, expected: 8000, gap: 8000, month: "2026-10", closing: false,
  destination: { id: "recP", title: "תכנון פנסיוני" }, ...o });

test("savings release: a shortfall comes out of the fixed income (10,000 of 15,000 -> 3,000 of 8,000 stay)", () => {
  const m = savingsReleaseModel(rel());
  assert.equal(m.headline, "₪3,000");
  assert.equal(m.lines[1].includes("חסרים ₪5,000") && m.lines[1].includes("₪3,000 מתוך ₪8,000"), true);
  assert.equal(m.lines[2].includes("נשארו להפקדה ₪3,000"), true);
  assert.equal(m.depositLabel, "הפקד ₪3,000");
  assert.equal(m.closing, null); assert.equal(m.canExplainGap, false);
});

test("savings release: goal met + extra, nothing left to deposit offers a plain 'record a deposit'", () => {
  const m = savingsReleaseModel(rel({ income_net: 17000, shortfall: 0, from_fixed: 8000, extra: 2000, available: 10000, deposited: 10000, remaining: 0, expected: 10000, gap: 0 }));
  assert.equal(m.lines[1].includes("יעד ההכנסה הושג") && m.lines[1].includes("ועוד ₪2,000"), true);
  assert.equal(m.depositLabel, "רשום הפקדה");
});

test("savings release: month end asks the total and offers to document the gap only when there is one", () => {
  const closing = savingsReleaseModel(rel({ closing: true, deposited: 3000, remaining: 0, gap: 5000 }));
  assert.equal(closing.closing?.includes("סך הפקדות החודש: ₪3,000"), true); assert.equal(closing.gapLine?.includes("₪5,000"), true); assert.equal(closing.canExplainGap, true);
  assert.equal(savingsReleaseModel(rel({ closing: true, gap: 0 })).canExplainGap, false);
  assert.equal(savingsReleaseModel(rel({ destination: null })).destination, "יעד ההפקדה ייבחר בעת ההפקדה");
});

test("savings follow-up: asked only while something is still free", () => {
  assert.equal(savingsFollowUp(rel())?.confirm, "הפקד ₪3,000");
  assert.equal(savingsFollowUp(rel({ remaining: 0 })), null);
  assert.equal(savingsFollowUp(null), null);
});

if (failures > 0) throw new Error(`${failures} test(s) failed`);
console.log("all fccPresentation tests passed");
