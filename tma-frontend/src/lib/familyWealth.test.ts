// Plain node + esbuild test (see package.json `npm test`).
declare function require(id: string): { readFileSync(path: string, enc: string): string; readdirSync(path: string): string[] };
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { FamilyWealth, FamilyWealthCard } from "../components/FamilyWealth";
import { FccTabBar } from "../components/FccTabBar";
import { LineChart, StackBar } from "../components/PortfolioLabCharts";
import type { FccAccountsForecast, FccAccountsView, FccOverview, PortfolioLabView, PaceView } from "../types";
import { AccountsPanel, ForecastResult, FundingResult, FundingSection, FundingSourcesList, SavedPlanChanges } from "../components/FamilyWealth";
import { ContextualComposer } from "../components/FccTabBar";
import { ACCOUNTS_COMPOSER, COMPOSER, FUNDING_COMPOSER } from "./fccTabs";
import { FCC_TABS, panelId, tabForKey, tabId } from "./fccTabs";
import {
  BALANCE_PLACEHOLDER, DEFAULT_LAB_FORM, FAMILY_TABS, OPEN_LABEL, SCREEN_TITLE, TABS_ARIA_LABEL, SELF_REPORTED, barChartModel, breakdownParts, familyCardModel,
  DEFAULT_FORECAST_FORM, DEFAULT_FUNDING_FORM, FUNDING_FIELDS, FUNDING_FOLLOWUP_LABELS, FUNDING_TYPE_LABELS, fundingModel, fundingRequest, newFundingOption, sourcesModel, savedChangesModel, SAVED_TITLE, SAVED_NOTE, isCurrentGoal, sourcesCacheKey, sourcesErrorText, SOURCES_DEBOUNCE_MS, SOURCES_EXPECTED_LABEL, type FundingForm, accountsTabModel, intraYearLines, timingRows, MISSING_LABEL, paceAccountRows, paceAssumptions, paceCorrectionRows, paceForecastLines, paceReturnText, paceSummaryRows, forecastModel, forecastParams, scenarioLines, scenarioRows, crisisTableRows, labKpiCards, labParams, labTableRows, lineChartModel, savingsTabModel,
  serverNote,
} from "./familyWealth";

const assert = {
  equal(actual: unknown, expected: unknown, message?: string) {
    if (actual !== expected) throw new Error(message ?? `expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
  },
  ok(v: unknown, message?: string) { if (!v) throw new Error(message ?? "expected truthy"); },
  deepEqual(actual: unknown, expected: unknown, message?: string) {
    const canon = (v: unknown): unknown => (Array.isArray(v) ? v.map(canon) : v && typeof v === "object" ? Object.fromEntries(Object.entries(v as object).sort(([a], [b]) => a.localeCompare(b)).map(([k, x]) => [k, canon(x)])) : v);
    if (JSON.stringify(canon(actual)) !== JSON.stringify(canon(expected))) throw new Error(message ?? `expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
  },
};
let failures = 0;
function test(name: string, fn: () => void) {
  try { fn(); console.log(`ok - ${name}`); } catch (error) { failures += 1; console.error(`FAIL - ${name}`); console.error(error); }
}

const release = { income_net: 10000, income_target: 15000, fixed_level: 8000, shortfall: 5000, from_fixed: 3000, extra: 0, available: 3000,
  deposited: 2500, remaining: 500, expected: 3000, gap: 500, month: "2026-10", closing: false, destination: { id: "r", title: "תכנון פנסיוני" } };
const plan = { mode: "monthly_level", target: 8000, actual: 5000, remaining: 3000, dynamic_target_per_week: 0, goals: 2 };
const overview = { summary: { savings: plan }, savings_release: release, as_of: "2026-10-14" } as unknown as FccOverview;

test("screen name and the four tabs are the agreed ones", () => {
  assert.equal(SCREEN_TITLE, "תכנון חיסכון לטווח ארוך");
  assert.equal(FAMILY_TABS.map((t) => t.label).join(" | "), "החיסכון שלי | החשבונות | מימון יעד | מעבדת העתיד");
});

test("savings tab: plan = standing level, actual labelled as self-reported, expected is NOT a plan, balance is not invented", () => {
  const m = savingsTabModel(overview);
  const by = Object.fromEntries(m.rows.map((r) => [r.key, r]));
  assert.equal(by.plan.label, "הפקדה חודשית מתוכננת");
  assert.ok(by.plan.value.includes("5,000") && by.plan.hint?.includes("8,000"));
  assert.equal(by.deposited.hint, SELF_REPORTED);
  assert.ok(by.deposited.value.includes("2,500"));
  assert.equal(by.expected.label, "צפוי להתפנות");
  assert.ok(by.expected.hint?.includes("אינו הפקדה מתוכננת"));
  assert.equal(by.balance.value, "לא זמינה");
  assert.equal(by.balance.hint, BALANCE_PLACEHOLDER);
  assert.ok(!m.rows.some((r) => /פער|שנה|רצף/.test(r.label)), "no history rows without server history (nothing is computed here)");
});

test("savings tab: history rows are server numbers only, labelled self-reported, gap stays visible", () => {
  const history = { ytd: 2200, ytd_plan: 10000, ytd_gap: 7800, months_elapsed: 10, monthly_average: 220, streak: 3,
    last_deposit: "2026-10-01", deposit_count: 3, recent: [] };
  const m = savingsTabModel({ ...overview, savings_history: history } as unknown as FccOverview);
  const by = Object.fromEntries(m.rows.map((r) => [r.key, r]));
  assert.ok(by.ytd.value.includes("2,200") && by.ytd.hint?.includes(SELF_REPORTED));
  assert.ok(by.average.value.includes("220") && by.streak.value === "3");
  assert.ok(by.ytd_gap.value.includes("7,800") && by.ytd_gap.hint?.includes("10,000"));
  assert.equal(m.rows.map((r) => r.key).join(","), "plan,deposited,expected,ytd,average,streak,ytd_gap,balance");
});

test("savings tab: missing data stays missing (never 0, never made up)", () => {
  const m = savingsTabModel({ summary: {}, savings_release: null } as unknown as FccOverview);
  const by = Object.fromEntries(m.rows.map((r) => [r.key, r]));
  assert.equal(by.plan.value, "לא הוגדרה");
  assert.equal(by.deposited.value, "לא זמין");
  assert.ok(!by.expected);
  assert.equal(m.hasData, false);
});

test("entry card: short, from the overview only, labelled", () => {
  const c = familyCardModel(overview);
  assert.equal(c.title, SCREEN_TITLE);
  assert.ok(c.value.includes("2,500"));
  assert.equal(c.hint, SELF_REPORTED);
  assert.equal(familyCardModel({ summary: {}, savings_release: null } as unknown as FccOverview).value, "אין עדיין נתון לחודש");
  const html = renderToStaticMarkup(createElement(FamilyWealthCard, { data: overview, onOpen: () => undefined }));
  assert.ok(html.includes("פתח") && html.includes(SCREEN_TITLE));
});

test("family screen renders both tabs, starts on the savings tab and does not mount the lab until opened", () => {
  const html = renderToStaticMarkup(createElement(FamilyWealth, { overview: { status: "ok", data: overview }, onBack: () => undefined, onRetry: () => undefined }));
  assert.ok(html.includes("החיסכון שלי") && html.includes("מעבדת העתיד"));
  assert.ok(html.includes('role="tablist"') && html.includes('id="fw-tab-savings"') && html.includes('id="fw-panel-lab"'));
  assert.ok(!html.includes("נתוני הדגמה"), "the lab (and its simulation call) is not mounted on the savings tab");
  assert.ok(html.includes("הפקדה חודשית מתוכננת") && html.includes("יתרת תיק"));
});

test("the FCC tab strip is reused unchanged for FCC and works for other tab sets", () => {
  const fcc = renderToStaticMarkup(createElement(FccTabBar, { active: "loans", onChange: () => undefined }));
  assert.ok(fcc.includes('id="fcc-tab-loans"') && fcc.includes("אזורי המרכז הכלכלי"));
  assert.equal(tabId("x"), "fcc-tab-x");
  assert.equal(panelId("x", "fw"), "fw-panel-x");
  assert.equal(tabForKey("monthly", "ArrowLeft", true), "loans");
  assert.equal(tabForKey("savings" as const, "ArrowLeft", true, FAMILY_TABS), "accounts");
  assert.equal(tabForKey("accounts" as const, "ArrowLeft", true, FAMILY_TABS), "funding");
  assert.equal(tabForKey("funding" as const, "ArrowLeft", true, FAMILY_TABS), "lab");
  assert.equal(tabForKey("lab" as const, "Home", false, FAMILY_TABS), "savings");
  assert.equal(FCC_TABS.length, 3);
});

test("form -> request: percentages stay as typed, blank/invalid is an error (never silently 0)", () => {
  const ok = labParams(DEFAULT_LAB_FORM);
  assert.ok(ok.ok);
  if (ok.ok) {
    assert.equal(ok.params.annual_return_pct, 8);
    assert.equal(ok.params.annual_fee_pct, 0.15);
    assert.equal(ok.params.years, 30);
    assert.equal(ok.params.crisis, undefined);
  }
  assert.ok(!labParams({ ...DEFAULT_LAB_FORM, monthly: "" }).ok);
  assert.ok(!labParams({ ...DEFAULT_LAB_FORM, years: "abc" }).ok);
  assert.ok(!labParams({ ...DEFAULT_LAB_FORM, years: "10.5" }).ok);
  const c = labParams({ ...DEFAULT_LAB_FORM, crisisOn: true, crisisDecline: "40", crisisYear: "7", crisisRecovery: "prolonged" });
  assert.ok(c.ok && c.params.crisis?.decline_pct === 40 && c.params.crisis?.year === 7 && c.params.crisis?.recovery === "prolonged");
  const none = labParams({ ...DEFAULT_LAB_FORM, strategies: [] });
  assert.ok(none.ok && none.params.strategies.join() === "global", "the baseline is always included");
});

test("one name everywhere: entry card, open button, screen title and tab-strip label all derive from SCREEN_TITLE", () => {
  const card = renderToStaticMarkup(createElement(FamilyWealthCard, { data: overview, onOpen: () => undefined }));
  assert.ok(card.includes(`aria-label="${SCREEN_TITLE}"`), "card aria-label");
  assert.ok(card.includes(`aria-label="${OPEN_LABEL}"`) && OPEN_LABEL.endsWith(SCREEN_TITLE), "open button");
  const screen = renderToStaticMarkup(createElement(FamilyWealth, { overview: { status: "ok", data: overview }, onBack: () => undefined, onRetry: () => undefined }));
  assert.ok(screen.includes(`>${SCREEN_TITLE}</h1>`) || screen.includes(SCREEN_TITLE), "screen title");
  assert.ok(screen.includes(`aria-label="${TABS_ARIA_LABEL}"`) && TABS_ARIA_LABEL.endsWith(SCREEN_TITLE), "tab strip label");
  const fs = require("fs");
  for (const file of ["src/components/FamilyWealth.tsx", "src/components/PortfolioLabPanel.tsx", "src/components/PortfolioLabCharts.tsx", "src/components/FinancialControlCenter.tsx", "src/App.tsx"]) {
    const text = fs.readFileSync(file, "utf8").replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");
    assert.ok(!/תכנון חיסכון|ההון המשפחתי|הון משפחתי/.test(text), `${file} hard-codes a screen name instead of using SCREEN_TITLE`);
  }
});

const view = {
  schema_version: "1.0", source: "portfolio_lab", engine_version: "1.0.0", result_type: "assumption_based_projection", currency: "ILS",
  primary_strategy: { id: "global", label: "100% קרן עולמית" },
  kpis: { final_nominal: 1000, final_real: 500, contributions: 400, nominal_profit: 600, real_profit: 100, management_fees_paid: 10, total_cost_impact: 20,
          net_effective_annual_return: 0.0784, real_effective_annual_return: 0.057, after_tax: { value: null, display: "לא מחושב", note: "לא הוזן מודל מס תקף" } },
  charts: {
    growth: { series: [{ year: 1, nominal: 10, real: 9, contributions: 8 }, { year: 2, nominal: 30, real: 25, contributions: 16 }], crisis: { applied: false } },
    strategy_comparison: { global: [{ year: 1, nominal: 10, real: 9, contributions: 8 }, { year: 2, nominal: 30, real: 25, contributions: 16 }] },
    breakdown: { contributions: 400, profit_net: 580, costs: 20, total_before_costs: 1000, shares: { contributions: 0.4, profit_net: 0.58, costs: 0.02 } },
    sensitivity: { monthly_contribution: [], duration: [] },
  },
  comparison_table: [{ strategy: "global", label: "100% קרן עולמית", is_baseline: true, final_nominal: 1000, final_real: 500, contributions: 400, net_profit: 600, costs: 10, gap_vs_baseline: 0 },
                     { strategy: "world_em", label: "World + EM", is_baseline: false, final_nominal: 900, final_real: 450, contributions: 400, net_profit: 500, costs: 10, gap_vs_baseline: -100 }],
  insights: [], assumptions: [], warnings: [], labels: { strategies: { global: "100% קרן עולמית" }, components: {} }, replay_digest: "abc",
} as unknown as PortfolioLabView;

test("KPI cards show the server's numbers; tax is 'לא מחושב' unless the server gave a value", () => {
  const cards = Object.fromEntries(labKpiCards(view).map((c) => [c.key, c]));
  assert.ok(cards.final_nominal.value.includes("1,000"));
  assert.equal(cards.net_return.value, "7.84%");
  assert.equal(cards.after_tax.value, "לא מחושב");
  assert.equal(cards.after_tax.hint, "לא הוזן מודל מס תקף");
  assert.equal(labKpiCards(view).length, 9);
});

test("comparison table: baseline marked, gap signed, taken from the server", () => {
  const rows = labTableRows(view);
  assert.ok(rows[0].baseline && rows[0].cells[0].includes("(בסיס)") && rows[0].cells[6] === "—");
  assert.ok(rows[1].cells[6].includes("100") && !rows[1].cells[6].startsWith("+"));
});

test("crisis table: the server's by_strategy rows, worded and signed; empty without a crisis", () => {
  assert.equal(crisisTableRows(view).length, 0);
  const withCrisis = { ...view, charts: { ...view.charts, growth: { ...view.charts.growth, crisis: { applied: true, by_strategy: [
    { strategy: "global", label: "100% קרן עולמית", is_baseline: true, final_nominal: 1100, final_real: 550, final_nominal_no_crisis: 1000, delta_vs_no_crisis: 100, gap_vs_baseline: 0 },
    { strategy: "world_em", label: "World + EM", is_baseline: false, final_nominal: 950, final_real: 470, final_nominal_no_crisis: 900, delta_vs_no_crisis: 50, gap_vs_baseline: -150 },
  ] } } } } as unknown as PortfolioLabView;
  const rows = crisisTableRows(withCrisis);
  assert.ok(rows[0].cells[0].includes("(בסיס)") && rows[0].cells[4] === "—" && rows[0].cells[3].startsWith("+"));
  assert.ok(!rows[1].cells[4].startsWith("+") && rows[1].cells[4].includes("150"));
});

test("scenario comparison: only filled set-B fields go into the request; rows are the server's A, B and gap, signed and neutral", () => {
  const off = labParams(DEFAULT_LAB_FORM);
  assert.ok(off.ok && off.params.compare_to === undefined);
  const on = labParams({ ...DEFAULT_LAB_FORM, compareOn: true, cmpReturnPct: "6", cmpMonthly: " " });
  assert.ok(on.ok && JSON.stringify(on.params.compare_to) === JSON.stringify({ annual_return_pct: 6 }));
  assert.ok(!labParams({ ...DEFAULT_LAB_FORM, compareOn: true }).ok);
  assert.ok(!labParams({ ...DEFAULT_LAB_FORM, compareOn: true, cmpFeePct: "abc" }).ok);
  assert.equal(scenarioRows(view).length, 0);
  const kpi = (n: number) => ({ final_nominal: n, final_real: n / 2, contributions: 100, nominal_profit: n - 100, real_profit: 1, management_fees_paid: 5, total_cost_impact: 6, net_effective_annual_return: 0.07, real_effective_annual_return: 0.05 });
  const gap = { final_nominal: -200, final_real: -100, contributions: 0, nominal_profit: -200, real_profit: 0, management_fees_paid: 1, total_cost_impact: 0, net_effective_annual_return: -0.02, real_effective_annual_return: 0, series: [] };
  const cmp = { ...view, charts: { ...view.charts, scenario_comparison: { applied: true,
    a: { label: "א", assumptions: {}, kpis: kpi(1000), series: [{ year: 1, nominal: 10, real: 9, contributions: 1 }] },
    b: { label: "ב", assumptions: {}, kpis: { ...kpi(800), net_effective_annual_return: 0.05 }, series: [{ year: 1, nominal: 8, real: 7, contributions: 1 }] },
    gaps_b_minus_a: gap } } } as unknown as PortfolioLabView;
  const rows = scenarioRows(cmp);
  assert.equal(rows.length, 8);
  assert.ok(rows[0].cells[3].includes("200") && !rows[0].cells[3].startsWith("+") && rows[5].cells[3].startsWith("+"));
  assert.ok(rows[7].cells[3].includes("-2.00%"));
  assert.deepEqual(scenarioLines(cmp)[1].pts, [[1, 8]]);
});

test("intra-year crisis: month goes into the request only when chosen; timing rows and path are the server's numbers", () => {
  const base = { ...DEFAULT_LAB_FORM, crisisOn: true };
  const annual = labParams(base);
  assert.ok(annual.ok && annual.params.crisis && annual.params.crisis.month === undefined);
  const monthly = labParams({ ...base, crisisMonth: "7" });
  assert.ok(monthly.ok && monthly.params.crisis?.month === 7);
  assert.equal(timingRows(view).length, 0);
  const withIntra = { ...view, charts: { ...view.charts, growth: { ...view.charts.growth, crisis: { applied: true, intra_year: {
    timing_by_month: [{ month: 1, is_selected: false, final_nominal: 1000, final_real: 500, delta_vs_no_crisis: 10 },
                      { month: 2, is_selected: true, final_nominal: 990, final_real: 495, delta_vs_no_crisis: -5 }],
    monthly_path: [{ t_years: 0.5, nominal_no_crisis: 10, nominal_crisis: 8 }, { t_years: 1, nominal_no_crisis: 12, nominal_crisis: 11 }],
  } } } } } as unknown as PortfolioLabView;
  const rows = timingRows(withIntra);
  assert.ok(rows[1].selected && rows[1].cells[0].includes("נבחר") && rows[0].cells[3].startsWith("+") && !rows[1].cells[3].startsWith("+"));
  const lines = intraYearLines(withIntra);
  assert.deepEqual(lines[1].pts, [[0.5, 8], [1, 11]]);
});

const paceView = {
  as_of: "2026-10-19", accounts: [
    { id: "recA", name: "קרן", status: "compared", missing: [], latest_balance: { value: 150000, as_of: "2026-09-10" },
      planned: { value_at_comparison: 128000 }, deviation: { vs_plan: 22000, vs_deposits_only: 26000, deposits_gap: 16000 },
      return: { exact: null, status: "approximate_range", days: 243, documented_flow_count: 2, undocumented_flows_possible: true,
                range: { low: 0.0714, high: 0.1 }, annualized_range: { low: 0.109, high: 0.154 } } },
    { id: "recB", name: "פנסיה", status: "single_snapshot", missing: ["planned_monthly_deposit", "deposit_events"], latest_balance: { value: 50000, as_of: "2026-03-01" } },
  ],
  consolidated: { accounts_with_plan: 1, accounts_without_plan: 0, accounts_without_snapshot: 0, accounts_single_snapshot: 1, accounts_short_period: 0, accounts_compared: 1,
    latest_balance: 150000, start_balance: 100000, planned: { value_at_comparison: 128000, deposits_total: 24000, value_deposits_only: 124000 },
    flows: { deposits: 40000, deposits_complete: true, withdrawals: 0, fees: 0, transfers_in: 0, transfers_out: 0, net_documented: 40000 },
    value_change: { total: 50000, documented_flows: 40000, unexplained: 10000 }, deviation: { vs_plan: 22000, vs_deposits_only: 26000, deposits_gap: 16000 } },
  forecast: { applied: true, lines: { planned_pace: { monthly_deposit: 3000, final_nominal: 900, series: [{ year: 1, nominal: 5, real: 4, contributions: 1 }] },
    actual_pace: { monthly_deposit: 5000, final_nominal: 1200, series: [{ year: 1, nominal: 6, real: 5, contributions: 1 }] }, goal_history_pace: null } },
  course_correction: { applied: true, rows: [{ monthly_change: -500, monthly_deposit: 4500, final_nominal: 1100, delta_vs_updated_forecast: -100 },
                                              { monthly_change: 500, monthly_deposit: 5500, final_nominal: 1300, delta_vs_updated_forecast: 100 }] },
} as unknown as PaceView;

test("pace tracker: wording of the server's numbers — signed deviation, no exact return, missing is 'חסר' never 0", () => {
  const rows = paceSummaryRows(paceView);
  const byKey = Object.fromEntries(rows.map((r) => [r.key, r.cells[1]]));
  assert.ok(byKey.deviation.startsWith("+") && byKey.deviation.includes("22,000"));
  assert.ok(byKey.unexplained.startsWith("+") && byKey.actual_deposits.includes("40,000"));
  const accounts = paceAccountRows(paceView);
  assert.ok(accounts[0].cells[5].includes("טווח משוער") && accounts[0].cells[5].includes("לא ניתן לחשב תשואה מדויקת"));
  assert.ok(!/\b10\.00%\b/.test(accounts[0].cells[5].split("עד")[0]));          // the range is shown, not one made-up exact figure
  assert.equal(accounts[1].cells[3], MISSING_LABEL);
  assert.equal(accounts[1].cells[4], MISSING_LABEL);
  assert.ok(accounts[1].missing.includes("הפקדה חודשית מתוכננת") && accounts[1].missing.includes("אירועי הפקדה"));
  const short = paceReturnText({ ...paceView.accounts[0].return!, status: "period_too_short", range: null, annualized_range: null });
  assert.ok(short.includes("30 יום") && !short.includes("%"));
});

test("pace tracker: lines are only those the server produced (no zero line for a missing pace); correction rows are signed and neutral", () => {
  assert.deepEqual(paceForecastLines(paceView).map((l) => l.name), ["קצב מתוכנן", "קצב בפועל (אקסטרפולציה)"]);
  const none = { ...paceView, forecast: { ...paceView.forecast, lines: { planned_pace: null, actual_pace: null, goal_history_pace: null } } } as unknown as PaceView;
  assert.equal(paceForecastLines(none).length, 0);
  const cc = paceCorrectionRows(paceView);
  assert.ok(cc[0].cells[0].startsWith("-") && cc[1].cells[0].startsWith("+") && cc[0].cells[3].startsWith("-") && cc[1].cells[3].startsWith("+"));
  assert.equal(paceCorrectionRows({ ...paceView, course_correction: { applied: false, reason: "no_actual_pace" } } as unknown as PaceView).length, 0);
  assert.equal(paceSummaryRows({ ...paceView, consolidated: { ...paceView.consolidated, deviation: null } } as unknown as PaceView).length, 0);
});

test("pace tracker: assumptions are the lab form's typed numbers; an invalid form yields none", () => {
  assert.deepEqual(paceAssumptions(DEFAULT_LAB_FORM), { annual_return_pct: 8, annual_fee_pct: 0.15, inflation_pct: 2 });
  assert.equal(paceAssumptions({ ...DEFAULT_LAB_FORM, returnPct: "x" }), null);
});

test("breakdown shares come from the server (the client never divides)", () => {
  const parts = breakdownParts(view);
  assert.equal(parts.map((p) => p.share).join(), "0.4,0.58,0.02");
  const html = renderToStaticMarkup(createElement(StackBar, { parts, formatValue: String, formatShare: (s) => `${s}` }));
  assert.ok(html.includes("40.00%") && html.includes("58.00%"));
});

test("chart geometry only scales: points stay inside the plot, the largest value sits at the top", () => {
  const m = lineChartModel([{ name: "a", pts: [[1, 10], [2, 30]] }]);
  const pts = m.lines[0].points.split(" ").map((p) => p.split(",").map(Number));
  assert.ok(pts.every(([x, y]) => x >= 58 && x <= 508 && y >= 12 && y <= 246));
  assert.ok(pts[1][1] < pts[0][1], "a larger value is drawn higher");
  const html = renderToStaticMarkup(createElement(LineChart, { model: m, xLabel: "שנים", title: "t" }));
  assert.ok(html.includes("<polyline") && html.includes('role="img"'));
  const bars = barChartModel(["a", "b"], [{ name: "n", values: [10, 20], color: "#000" }]);
  assert.ok(bars.groups[1].bars[0].h > bars.groups[0].bars[0].h);
});

test("no financial engine in the client: no compounding / annuity / power math in the new sources", () => {
  const fs = require("fs");
  for (const file of ["src/lib/familyWealth.ts", "src/components/FamilyWealth.tsx", "src/components/PortfolioLabPanel.tsx", "src/components/PortfolioLabCharts.tsx"]) {
    const text = fs.readFileSync(file, "utf8").replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");
    for (const bad of ["Math.pow", "**", "Math.exp", "Math.log", "reduce(", "/ 12", "* 12", "annuity", "compound", "1 +"]) {
      assert.ok(!text.includes(bad), `${file} contains "${bad}"`);
    }
  }
});

test("a screen of its own: opened from the hub (owners only) and via the FCC card shortcut — never nested inside the FCC", () => {
  const fs = require("fs");
  const app = fs.readFileSync("src/App.tsx", "utf8");
  assert.ok(app.includes("if (familyOpen)") && app.includes("<FamilyWealthScreen"), "App opens the screen itself");
  assert.ok(/canShowOwnerControl && \(\s*<button[\s\S]{0,120}setFamilyOpen\(true\)/.test(app), "hub entry is owner-only");
  assert.ok(app.includes("aria-label={SCREEN_TITLE}"), "hub button is named by SCREEN_TITLE");
  assert.ok(app.includes("onOpenFamilyWealth="), "the FCC card is a shortcut owned by App");
  const fcc = fs.readFileSync("src/components/FinancialControlCenter.tsx", "utf8");
  assert.ok(!fcc.includes("<FamilyWealth ") && !fcc.includes("familyOpen"), "the FCC no longer renders the screen");
  assert.ok(fcc.includes("onOpenFamilyWealth && <FamilyWealthCard"), "no card without the shortcut");
});

test("the screen loads its own data: loading/error states, and the lab tab does not depend on the overview", () => {
  const states = [
    [{ status: "loading" as const }, "טוען את נתוני החיסכון"],
    [{ status: "error" as const, code: 404 }, "המסך עדיין לא פעיל"],
    [{ status: "error" as const, code: 403 }, "אין הרשאה"],
    [{ status: "error" as const, code: 500 }, "נסו שוב"],
  ] as const;
  for (const [overview, text] of states) {
    const html = renderToStaticMarkup(createElement(FamilyWealth, { overview, onBack: () => undefined, onRetry: () => undefined }));
    assert.ok(html.includes(text), `savings tab shows "${text}"`);
    assert.ok(html.includes(SCREEN_TITLE) && html.includes('id="fw-tab-lab"'), "header and both tabs are always there");
    assert.ok(!html.includes("הפקדה חודשית מתוכננת"), "no savings numbers without data");
  }
});

// ── D1 step 7 / B1: accounts tab ──
const snap = (value: number, estimateValue = value, count = 0) =>
  ({ value, as_of: "2026-10-01", verification: "self_reported", estimate: { value: estimateValue, movements_since: estimateValue - value, movement_count: count, label: "estimate" as const } });
const acct = (id: string, extra: Record<string, unknown> = {}) =>
  ({ id, name: id, account_type: "study_fund", institution: "בנק", holder_names: null, status: "active", liquidity: "immediate", liquid_from: null,
     tax_treatment: null, management_fee_pct: null, balance: null, ...extra });
const accountsView = (accounts: unknown[], totals: Record<string, unknown> = {}) => ({
  accounts, skipped_events: 0, as_of: "2026-10-15",
  totals: { consolidated_value: null, estimated_value: null, accounts_with_value: 0, accounts_without_snapshot: 0, closed_accounts: 0, oldest_snapshot: null, all_self_reported: null, ...totals },
}) as unknown as FccAccountsView;

test("accounts tab: the consolidated value is the server's number, the estimate is separate and labelled, nothing is summed here", () => {
  const v = accountsView([acct("a", { balance: snap(100000, 105000, 1) })], { consolidated_value: 100000, estimated_value: 105000, accounts_with_value: 1, oldest_snapshot: "2026-10-01", all_self_reported: true });
  const m = accountsTabModel(v);
  assert.ok(m.total.value.includes("100,000") && m.total.hint?.includes(SELF_REPORTED));
  assert.ok(m.extras.some((r) => r.key === "estimate" && r.value.includes("105,000") && r.hint?.includes("אינה חלק מהשווי המאוחד")));
  assert.ok(m.rows[0].estimate?.includes("הערכה") && m.rows[0].value.includes("100,000"));
});

test("accounts tab: no snapshot is never shown as 0; closed and missing are counted, not hidden", () => {
  const v = accountsView([acct("a"), acct("b", { status: "closed", balance: snap(5) })], { accounts_without_snapshot: 1, closed_accounts: 1 });
  const m = accountsTabModel(v);
  assert.equal(m.total.value, "לא זמין");
  assert.equal(m.rows[0].value, "אין יתרה שדווחה");
  assert.ok(m.rows[1].closed && m.extras.map((r) => r.key).join() === "missing,closed");
  assert.ok(!m.rows[0].value.includes("₪0"));
});

test("accounts panel: empty / loading / error states, and the rows render", () => {
  const render = (state: Parameters<typeof AccountsPanel>[0]["state"]) => renderToStaticMarkup(createElement(AccountsPanel, { state, onRetry: () => undefined }));
  assert.ok(render({ status: "loading" }).includes("טוען את החשבונות"));
  assert.ok(render({ status: "error", code: 404 }).includes("המסך עדיין לא פעיל"));
  assert.ok(render({ status: "error", code: 403 }).includes("אין הרשאה"));
  assert.ok(render({ status: "error", code: 500 }).includes("נסו שוב"));
  assert.ok(render({ status: "ok", data: accountsView([]) }).includes("עוד אין חשבונות"));
  const html = render({ status: "ok", data: accountsView([acct("קרן א", { balance: snap(100000) })], { consolidated_value: 100000, estimated_value: 100000, accounts_with_value: 1 }) });
  assert.ok(html.includes("קרן א") && html.includes("שווי מאוחד") && html.includes("קרן השתלמות"));
});

test("the accounts tab is not mounted (no fetch) until opened, and the screen has no write control", () => {
  const html = renderToStaticMarkup(createElement(FamilyWealth, { overview: { status: "loading" }, onBack: () => undefined, onRetry: () => undefined }));
  assert.ok(html.includes('id="fw-tab-accounts"') && html.includes('id="fw-panel-accounts"'));
  assert.ok(!html.includes("טוען את החשבונות"), "the accounts call is not made while another tab is open");
  const src = require("fs").readFileSync("src/components/FamilyWealth.tsx", "utf8");
  assert.ok(!/postFccWrite|postFccIntent|method:\s*"(POST|PUT|PATCH|DELETE)"/.test(src), "no write call from the family screen (the forecast POST only carries assumptions)");
});

// ── D1 step 7 / A1: accounts forecast ──
const fPoint = (year: number, nominal: number, real: number, invested: number) => ({ year, nominal, real, invested });
const forecastView = {
  schema_version: "1.0", engine_version: "1.0.0", result_type: "assumption_based_projection", start_date: "2026-10-01", years: 10,
  assumptions: { annual_return_pct: 6, annual_fee_pct_default: 0.15, inflation_pct: 2, deposit_timing: "end" },
  accounts: [
    { id: "recA", name: "קרן א", account_type: "study_fund", start_value: 100000, start_as_of: "2026-10-01", verification: "self_reported", monthly_contribution: 1000,
      fee_pct: 0.5, fee_source: "account", final_nominal: 328448, final_real: 270000, invested: 220000, nominal_profit: 108448, costs_paid: 5000, series: [fPoint(1, 1, 1, 1)] },
    { id: "recB", name: "נזיל", account_type: "liquid", start_value: 50000, start_as_of: "2026-10-02", verification: "self_reported", monthly_contribution: 0,
      fee_pct: 0.15, fee_source: "default", final_nominal: 88208, final_real: 72000, invested: 50000, nominal_profit: 38208, costs_paid: 900, series: [fPoint(1, 1, 1, 1)] },
  ],
  consolidated: { accounts: 2, start_value: 150000, final_nominal: 416656, final_real: 342000, invested: 270000, series: [fPoint(1, 150000, 150000, 150000), fPoint(10, 416656, 342000, 270000)] },
  excluded: { without_snapshot: 1, closed: 1 }, all_self_reported: true, warnings: ["תחזית מבוססת הנחות — לא הבטחת תשואה ולא המלצת השקעה."], as_of: "2026-10-15",
} as unknown as FccAccountsForecast;

test("forecast form: typed text -> request body; blank deposit means none; bad input is an error, never silently 0", () => {
  const ok = forecastParams({ ...DEFAULT_FORECAST_FORM, deposits: { recA: "1,000".replace(",", ""), recB: "  ", recC: "0" } });
  assert.ok(ok.ok && ok.params.years === 20 && ok.params.annual_return_pct === 6 && ok.params.annual_fee_pct === 0.15);
  assert.equal(JSON.stringify(ok.ok ? ok.params.monthly_contributions : null), JSON.stringify({ recA: 1000 }));
  for (const bad of [{ years: "" }, { years: "20.5" }, { returnPct: "abc" }, { feePct: "" }, { deposits: { recA: "-5" } }, { deposits: { recA: "x" } }]) {
    assert.equal(forecastParams({ ...DEFAULT_FORECAST_FORM, ...bad }).ok, false, JSON.stringify(bad));
  }
});

test("forecast model: server totals only, fee source shown, excluded accounts counted, nothing summed here", () => {
  const m = forecastModel(forecastView);
  assert.ok(m.total.find((r) => r.key === "final")?.value.includes("416,656"));
  assert.ok(m.total.find((r) => r.key === "invested")?.hint?.includes("כולל את יתרת הפתיחה"));
  assert.ok(m.rows[1].cells[3].includes("ברירת מחדל") && !m.rows[0].cells[3].includes("ברירת מחדל"));
  assert.ok(m.notes.some((n) => n.includes("1 חשבונות בלי יתרה")) && m.notes.some((n) => n.includes("חשבונות סגורים")));
  assert.ok(m.chart && m.chart.lines.length === 3);
});

test("forecast model: missing account inputs are listed in the owner's words; an older server without data_gaps adds nothing", () => {
  const withGaps = { ...forecastView, data_gaps: [{ id: "recB", name: "נזיל", missing: ["management_fee", "expected_return", "insurance_cost"] }] } as unknown as FccAccountsForecast;
  const note = forecastModel(withGaps).notes.find((n) => n.startsWith("חסר לדיוק"));
  assert.ok(note && note.includes("נזיל") && note.includes("דמי ניהול מהצבירה") && note.includes("תשואה צפויה") && note.includes("עלות ביטוח חודשית"));
  assert.ok(!forecastModel(forecastView).notes.some((n) => n.startsWith("חסר לדיוק")));
});

test("forecast result renders labelled as assumptions, and with no eligible account there is no fake total", () => {
  const html = renderToStaticMarkup(createElement(ForecastResult, { view: forecastView }));
  assert.ok(html.includes("שווי מאוחד בעוד 10 שנים") && html.includes("הבטחת תשואה") && html.includes("קרן א"));
  const none = { ...forecastView, accounts: [], consolidated: { accounts: 0, start_value: 0, final_nominal: null, final_real: null, invested: null, series: [] } } as unknown as FccAccountsForecast;
  const m = forecastModel(none);
  assert.equal(m.total.length, 0);
  assert.equal(m.chart, null);
});

test("forecast is not requested until asked, and only the assumptions are posted (no balances from the client)", () => {
  const src = require("fs").readFileSync("src/components/FamilyWealth.tsx", "utf8");
  assert.ok(src.includes("postFccAccountsForecast(parsed.params)") && !/useEffect\([^)]*run\(/.test(src));
  const api = require("fs").readFileSync("src/api.ts", "utf8");
  assert.ok(api.includes("/api/fcc/accounts/forecast") && api.includes("export async function postFccAccountsForecast(params: FccForecastParams)"));
  const accountsOnly = renderToStaticMarkup(createElement(AccountsPanel, { state: { status: "ok", data: { accounts: [], totals: {}, skipped_events: 0, as_of: "x" } as unknown as FccAccountsView }, onRetry: () => undefined }));
  assert.ok(!accountsOnly.includes("חשב תחזית"), "no forecast form without an account that has a balance");
});

// ── D1 step 8: account writes run in the shared contextual composer ──
test("accounts composer: two chips that only name an intent + an account; no chip creates an account; the FCC tabs are unchanged", () => {
  assert.equal(ACCOUNTS_COMPOSER.chips.map((c) => c.intent).join(), "account.update_balance,account.deposit");
  assert.ok(ACCOUNTS_COMPOSER.chips.every((c) => c.pick === "account") && !ACCOUNTS_COMPOSER.freeText);
  assert.ok(!ACCOUNTS_COMPOSER.chips.some((c) => /create|new/.test(c.intent)));
  assert.equal(Object.keys(COMPOSER).join(), "monthly,loans,assets");
});

test("composer renders with the accounts config (no FCC tab needed) and shows the two account actions", () => {
  const html = renderToStaticMarkup(createElement(ContextualComposer, {
    config: ACCOUNTS_COMPOSER, turn: null, receipt: null, error: null, busy: false,
    targets: { goals: [], loans: [], assets: [], accounts: [{ id: "recA", title: "קרן א" }] }, onStart: () => undefined, onSend: () => undefined, onDismiss: () => undefined,
  }));
  assert.ok(html.includes("עדכון חשבון") && html.includes("עדכון יתרה") && html.includes("הפקדה לחשבון"));
  assert.ok(!html.includes("+ הכנסה"), "the monthly chips do not leak into the accounts composer");
});

test("an open review turn is rendered by the server's words with confirm / edit / cancel (accounts use the same engine)", () => {
  const turn = { state: "review", message: "📋 עדכון יתרת חשבון\n• חשבון: קרן א\n• יתרה: ₪120,000", entity: "fcc_account_balance" } as unknown as import("../types").FccTurn;
  const html = renderToStaticMarkup(createElement(ContextualComposer, {
    config: ACCOUNTS_COMPOSER, turn, receipt: null, error: null, busy: false,
    targets: { goals: [], loans: [], assets: [], accounts: [] }, onStart: () => undefined, onSend: () => undefined, onDismiss: () => undefined,
  }));
  assert.ok(html.includes("עדכון יתרת חשבון") && html.includes("אשר ורשום") && html.includes("ערוך") && html.includes("בטל"));
});

test("the family screen has no write call of its own: writes go only through the shared writer hook (intent/start + write)", () => {
  const screen = require("fs").readFileSync("src/components/FamilyWealth.tsx", "utf8");
  assert.ok(screen.includes("useFccWriter(null, \"accounts\"") && !/postFccIntent|postFccWrite/.test(screen));
  const bar = require("fs").readFileSync("src/components/FccTabBar.tsx", "utf8");
  assert.ok(bar.includes("export function useFccWriter") && bar.includes("postFccIntent") && bar.includes("postFccWrite") && !/\bfetch\(/.test(bar), "the hook only calls the API module");
});

if (failures) throw new Error(`${failures} test(s) failed`);
console.log("all familyWealth tests passed");

// ── D1 step 10 / A2: liquidity states + goal coverage (server numbers only) ──
const a2View = {
  ...forecastView,
  accounts: [
    { ...(forecastView.accounts[0] as object), liquidity: { basis: "immediate", liquid_from: null, state_now: "accessible", state_at_horizon: "accessible" } },
    { ...(forecastView.accounts[1] as object), liquidity: { basis: "dated", liquid_from: "2027-11-28", state_now: "locked", state_at_horizon: "conditional" } },
  ],
  consolidated: { ...forecastView.consolidated, series: [
    { year: 1, nominal: 150000, real: 147000, invested: 150000, accessible: 100000, conditional: 0, locked: 50000 },
    { year: 2, nominal: 160000, real: 150000, invested: 150000, accessible: 100000, conditional: 60000, locked: 0 }] },
  goals: [
    { id: "g1", title: "פנסיה", category: "long_term", target_amount: 90000, due_month: "2027-12", verdict: "covered", reason: null, gap: null, accessible_value: 100000, conditional_value: 0, locked_value: 0 },
    { id: "g2", title: "קרן חירום", category: "emergency_fund", target_amount: 120000, due_month: "2027-12", verdict: "short", reason: null, gap: 20000, accessible_value: 100000, conditional_value: 0, locked_value: 0 },
    { id: "g3", title: "השקעה", category: "investment", target_amount: null, due_month: null, verdict: "not_comparable", reason: "missing_target", gap: null, accessible_value: null, conditional_value: null, locked_value: null },
  ],
} as unknown as FccAccountsForecast;

test("A2 model: coverage wording is potential-only, gaps and reasons come from the server, nothing is recomputed", () => {
  const m = forecastModel(a2View);
  assert.equal(m.goals.length, 2, "only comparable goals get a table row");
  assert.ok(m.goals[0].cells[4].includes("מכוסה (פוטנציאלית)") && m.goals[0].cells[2] === "12/2027");
  assert.ok(m.goals[1].cells[4].includes("חסר") && m.goals[1].cells[4].includes("20,000"));
  const gap = m.notes.find((n) => n.startsWith("חסר לדיוק — 1 מטרות"));
  assert.ok(gap && gap.includes("השקעה") && gap.includes("חסר סכום יעד"), "the incomparable goal stays visible as a missing-data line");
});

test("A2 model: many incomparable goals collapse into one capped line, not a wall of rows", () => {
  const many = Array.from({ length: 9 }, (_, i) => ({ id: `x${i}`, title: `מטרה ${i}`, category: "savings", target_amount: null, due_month: null, verdict: "not_comparable", reason: "missing_target", gap: null, accessible_value: null, conditional_value: null, locked_value: null }));
  const m = forecastModel({ ...a2View, goals: many } as unknown as FccAccountsForecast);
  assert.equal(m.goals.length, 0);
  const lines = m.notes.filter((n) => n.startsWith("חסר לדיוק — 9 מטרות"));
  assert.equal(lines.length, 1);
  assert.ok(lines[0].includes("ועוד 5") && !lines[0].includes("מטרה 8"));
});

test("A2 model: chart gets accessible + conditional lines only when the server sends them; labels never promise a withdrawal right", () => {
  assert.equal(forecastModel(a2View).chart?.lines.length, 5);
  assert.equal(forecastModel(forecastView).chart?.lines.length, 3, "an older response without liquidity renders as before");
  assert.equal(forecastModel(forecastView).goals.length, 0);
  const rows = forecastModel(a2View).rows;
  assert.ok(rows[0].liquidity.includes("נגיש מיד") && rows[1].liquidity.includes("זכאות למשיכה לא אומתה") && rows[1].liquidity.includes("28/11/2027"));
});

// ── B2 step 4: allocations (every number is the server's; nothing is computed in the client) ──
const goalBase = { category: "long_term", target_amount: 1000, due_month: "2030-06", gap: null, accessible_value: null, conditional_value: null, locked_value: null, reason: null };
const allocView = {
  ...a2View,
  goals: [
    { ...goalBase, id: "g1", title: "דירה", verdict: "covered", basis: "allocation", planned_allocated_value: 1200, allocated_value: 800, allocation_gap: 400, accessible_value: 800 },
    { ...goalBase, id: "g2", title: "חירום", verdict: "short", gap: 300, basis: "potential", accessible_value: 700, potential_caveat: "allocated_elsewhere", allocated_elsewhere_accessible: 500, unallocated_accessible_value: 200 },
    { ...goalBase, id: "g3", title: "פנסיה", verdict: "not_comparable", basis: "allocation", reason: "allocated_not_accessible", allocated_value: 5000 },
    { ...goalBase, id: "g4", title: "יתר", verdict: "not_comparable", basis: "allocation", reason: "over_allocated" },
  ],
  allocations: {
    as_of: "2026-10-18", has_allocations: true, count: 3,
    totals: { accounts_value: 10000, allocated: 6000, unallocated: 4000, over_allocated: 1500 },
    accounts: [
      { id: "a1", name: "השקעות", value: 10000, as_of: "2026-10-01", liquidity_state: "accessible", allocated: 6000, allocated_pct: 60, unallocated: 4000, over_allocated: false, over_by: 0, allocations: [{ id: "x" }] },
      { id: "a2", name: "קופה", value: 1000, as_of: "2026-10-01", liquidity_state: "locked", allocated: 2500, allocated_pct: 250, unallocated: 0, over_allocated: true, over_by: 1500, allocations: [{ id: "y" }] },
      { id: "a3", name: "בלי הקצאה", value: 50, as_of: "2026-10-01", liquidity_state: "accessible", allocated: 0, allocated_pct: 0, unallocated: 50, over_allocated: false, over_by: 0, allocations: [] },
    ],
    goals: [
      { id: "g1", title: "דירה", allocated: 6000, accessible: 6000, conditional: 0, locked: 0, blocked_by_over_allocation: 0, status: "ok" },
      { id: "g4", title: "יתר", allocated: 0, accessible: 0, conditional: 0, locked: 0, blocked_by_over_allocation: 2500, status: "blocked_over_allocation" },
    ],
    skipped: { inactive: 2, unknown_link: 1, status_missing: 0 }, over_allocated_accounts: 1, duplicate_goal_account_pairs: 1,
  },
} as unknown as FccAccountsForecast;

test("B2 UI: planned and effective allocation are shown separately, never one clipped number", () => {
  const m = forecastModel(allocView);
  assert.equal(m.goalHead.length, 6);
  assert.ok(m.goalHead.includes("הוקצה"));
  const g1 = m.goals.find((g) => g.id === "g1")!;
  assert.equal(g1.cells.length, 6);
  assert.ok(g1.cells[3].includes("בפועל") && g1.cells[3].includes("800") && g1.cells[3].includes("מתוכנן") && g1.cells[3].includes("1,200"));
  assert.ok(g1.cells[5].includes("לפי ההקצאה"));
});

test("B2 UI: potential coverage carries the allocated-elsewhere caveat and the truly free amount", () => {
  const g2 = forecastModel(allocView).goals.find((g) => g.id === "g2")!;
  assert.equal(g2.cells[3], "—");
  assert.ok(g2.cells[5].includes("כבר מוקצה למטרות אחרות") && g2.cells[5].includes("500") && g2.cells[5].includes("200"));
});

test("B2 UI: allocated-but-not-accessible and over-allocated goals stay visible with their reason", () => {
  const note = forecastModel(allocView).notes.find((n) => n.startsWith("חסר לדיוק — 2 מטרות"))!;
  assert.ok(note.includes("הוקצה, אך לא נגיש") && note.includes("5,000"));
  assert.ok(note.includes("הקצאת יתר"));
});

test("B2 UI: over-allocation is explicit (amount + warning), excluded from healthy sums and not clipped to zero", () => {
  const a = forecastModel(allocView).allocations!;
  assert.equal(a.kpis.find((k) => k.key === "over")!.value.includes("1,500"), true);
  const over = a.accounts.find((r) => r.id === "a2")!;
  assert.equal(over.over, true);
  assert.ok(over.cells[2].includes("2,500") && over.cells[2].includes("1,500") && over.cells[3] === "הקצאת יתר");
  assert.ok(a.notes.some((n) => n.includes("בהקצאת יתר") && n.includes("אינם נכללים")));
  assert.ok(a.goals.find((g) => g.id === "g4")!.warn.includes("2,500"));
  assert.equal(a.accounts.some((r) => r.id === "a3"), false, "accounts without allocation rows are not listed");
});

test("B2 UI: liquidity split per goal and skipped/duplicate notes come from the server", () => {
  const a = forecastModel(allocView).allocations!;
  assert.equal(a.goalHead.join("|"), "מטרה|הוקצה|נגיש|מותנה|נעול");
  assert.equal(a.accounts.find((r) => r.id === "a2")!.cells[4], "נעול");
  assert.ok(a.notes.some((n) => n.includes("2 הקצאות שאינן פעילות") && n.includes("1 הקצאות שאינן שלך") && !n.includes("status")));
  assert.ok(a.notes.some((n) => n.includes("זוגות מטרה+חשבון")));
});

test("B2 UI: empty table or older server — backwards compatible; the screen states what an allocation is and is not", () => {
  assert.equal(forecastModel(a2View).allocations, null);
  assert.equal(forecastModel(a2View).goalHead.length, 5, "no allocation basis -> the A2 table is unchanged");
  const empty = { ...a2View, allocations: { as_of: "2026-10-18", has_allocations: false, count: 0, totals: { accounts_value: 0, allocated: 0, unallocated: 0, over_allocated: 0 }, accounts: [], goals: [], skipped: {}, over_allocated_accounts: 0, duplicate_goal_account_pairs: 0 } } as unknown as FccAccountsForecast;
  assert.equal(forecastModel(empty).allocations, null);
  assert.ok(renderToStaticMarkup(createElement(ForecastResult, { view: empty })).includes("לא הוזנו הקצאות"));
  assert.ok(!renderToStaticMarkup(createElement(ForecastResult, { view: a2View })).includes("לא הוזנו הקצאות"), "older response without the key shows nothing");
  const html = renderToStaticMarkup(createElement(ForecastResult, { view: allocView }));
  assert.ok(html.includes("הקצאות מטרות") && html.includes("אינה העברה") && html.includes("אינה הופכת כסף לנזיל"));
});

test("B2 UI: read-only — no allocation write path or client money math in the frontend", () => {
  const fs = require("node:fs") as unknown as { readFileSync(p: string, e: string): string };
  assert.ok(!/goal.?allocations/i.test(fs.readFileSync("src/api.ts", "utf8")), "no client route to the allocations table");
  const lib = fs.readFileSync("src/lib/familyWealth.ts", "utf8");
  const start = lib.indexOf("export function allocationsModel");
  const model = lib.slice(start, lib.indexOf("// ── Future lab form") > start ? lib.indexOf("// ── Future lab form") : undefined);
  assert.ok(start > 0 && !/\.reduce\(|Math\.(round|min|max)\(|\bfetch/.test(model), "the allocation model only formats the server's numbers");
});


// ── Goal Funding Planner, step 1b: typed options -> request, and a neutral comparison of the server's numbers ──
function fundingForm(patch: Partial<FundingForm> = {}): FundingForm { return { ...DEFAULT_FUNDING_FORM, goalId: "recG1", ...patch }; }
function draft(type: Parameters<typeof newFundingOption>[0], values: Record<string, string>, use = "", n = 1) { return { ...newFundingOption(type, n), values: { ...newFundingOption(type, n).values, ...values }, use }; }

test("funding request: needs a goal; blank required fields are errors, never silently 0", () => {
  const none = fundingRequest(fundingForm({ goalId: "" }));
  assert.ok(!none.ok && none.error.includes("יעד"));
  const loan = fundingRequest(fundingForm({ options: [draft("loan", { amount: "100000", annual_rate_pct: "6", term_months: "60" })] }));
  assert.ok(!loan.ok && loan.error.includes("תאריך קבלת הכסף"), "available_by is required");
  const badNumber = fundingRequest(fundingForm({ options: [draft("loan", { amount: "abc", annual_rate_pct: "6", term_months: "60", available_by: "2029-01-01" })] }));
  assert.ok(!badNumber.ok && badNumber.error.includes("מספר") && !badNumber.error.includes("abc"));
  const badAssumption = fundingRequest(fundingForm({ returnPct: "" }));
  assert.ok(!badAssumption.ok && badAssumption.error.includes("תשואה"));
});

test("funding request: typed text becomes numbers once; optional blanks are omitted; the API's shapes are produced", () => {
  const r = fundingRequest(fundingForm({ options: [
    draft("new_deposits", { source: "hypothetical", liquidity: "immediate", expected_return_pct: "4", fee_pct: "0.3" }, "50000", 1),
    draft("loan", { amount: "100000", annual_rate_pct: "6", term_months: "60", available_by: "2029-01-01", approved: "true" }, "", 2),
    draft("asset_sale", { net_proceeds: "300000", expected_date: "2030-03-01" }, "", 3),
    draft("custom", { label: " מענק ", amount: "40000" }, "", 4),
    draft("new_deposits", { source: "hypothetical", liquidity: "date", liquid_from: "2030-01-01", release_confirmed: "true" }, "", 5),
    draft("new_deposits", { source: "account", account_id: "recA1" }, "", 6),
  ] }));
  assert.ok(r.ok);
  if (!r.ok) return;
  assert.deepEqual(r.body.assumptions, { annual_return_pct: 6, annual_fee_pct: 0.15, inflation_pct: 2 });
  const [dep, loan, sale, custom, dated, account] = r.body.options;
  assert.deepEqual(dep, { id: "new_deposits_1", type: "new_deposits", hypothetical: { immediate: true, expected_return_pct: 4, fee_pct: 0.3 } });
  assert.deepEqual(loan, { id: "loan_2", type: "loan", amount: 100000, annual_rate_pct: 6, term_months: 60, available_by: "2029-01-01", approved: true });
  assert.deepEqual(sale, { id: "asset_sale_3", type: "asset_sale", net_proceeds: 300000, expected_date: "2030-03-01" });
  assert.deepEqual(custom, { id: "custom_4", type: "custom", label: "מענק", amount: 40000 });
  assert.deepEqual(dated, { id: "new_deposits_5", type: "new_deposits", hypothetical: { liquid_from: "2030-01-01" }, release_confirmed: true });
  assert.deepEqual(account, { id: "new_deposits_6", type: "new_deposits", account_id: "recA1" });
  assert.deepEqual(r.body.allocation_plan, [{ goal_id: "recG1", option_id: "new_deposits_1", amount: 50000 }], "only non-blank 'use' amounts enter the plan");
  const badUse = fundingRequest(fundingForm({ options: [draft("custom", { label: "x", amount: "5" }, "-3")] }));
  assert.ok(!badUse.ok && badUse.error.includes("סכום לשימוש"));
});

test("funding request: the form never contains a field that writes, a tax rule or a score", () => {
  const all = JSON.stringify(Object.values(FUNDING_FIELDS).flat().map((f) => [f.key, f.label]));
  assert.ok(!/tax|score|rank|מס\b|ציון|דירוג|המלצ/.test(all));
  assert.equal(Object.keys(FUNDING_FIELDS).length, 7, "existing_balance is automatic (server-derived), not typed");
  assert.equal(FUNDING_TYPE_LABELS.existing_balance, "כסף קיים (הקצאות)");
});

const option = (over: Record<string, unknown>) => ({ id: "x", type: "custom", feasible: true, reason: null, covers_amount: null, available_by: null, monthly_cash_effect: null, one_time_cost: null,
  total_cost: null, new_liabilities: null, time_to_realize_months: null, certainty: "expected", conditions: [], risks: [], assumptions: [], missing_inputs: [], provenance: {}, details: {}, ...over });
const fundingView = {
  schema_version: "1.0", result_type: "funding_plan_comparison", as_of: "2026-10-18", assumptions: { annual_return_pct: 6, annual_fee_pct: 0.15, inflation_pct: 2, horizon_years: 10 },
  goals: [{
    need: { goal_id: "recG1", title: "חתונה", category: "savings", target: 200000, due: "2038-06-30", months_to_due: 140, reason: null, sizing_basis: "target_minus_confirmed",
            confirmed_existing: 20000, expected_existing: 5000, progress_events_actual: null, gap: 180000, gap_after_expected: 175000 },
    options: [
      option({ id: "existing_balance", type: "existing_balance", feasible: true, covers_amount: 25000, certainty: "confirmed" }),
      option({ id: "dep", type: "new_deposits", covers_amount: 180000, monthly_cash_effect: -1154.06, total_cost: 6369.41, available_by: "2038-06-30", time_to_realize_months: 140,
               details: { required_monthly: 1154.06 }, conditions: ["owner_confirms_deposits"], risks: ["depends_on_assumed_return"], assumptions: ["growth_as_assumed"] }),
      option({ id: "loan", type: "loan", covers_amount: 100000, certainty: "uncertain", monthly_cash_effect: -1933.28, total_cost: 15996.81, new_liabilities: { amount: 100000, monthly_payment: 1933.28, term_months: 60 },
               conditions: ["loan_approved"], risks: ["terms_unverified", "brand_new_code"] }),
      option({ id: "owed", type: "receivable_collection", feasible: "unknown", reason: "no_arrangement", covers_amount: 100000, certainty: "uncertain", conditions: ["debtor_arrangement"], risks: ["receivable_no_arrangement"] }),
    ],
    plan: { allocations: [{ option_id: "owed", amount: 100000, certainty: "uncertain", available_by: "2029-01-01", conditions: ["debtor_arrangement"] }],
            covered: { confirmed: 20000, expected: 5000, uncertain: 100000, unknown: 0 }, earliest_available_by: "2029-01-01", remaining_after_confirmed: 180000,
            remaining_after_confirmed_and_expected: 175000, monthly_burden: 0, monthly_release: 0, note: "coverage is split by certainty and is never summed into one 'available' figure" },
  }],
  portfolio: { monthly_burden_in_plan: 1154.06, planned_monthly_savings: 5000, actual_monthly_savings: 1000, shortfall_vs_planned: 0, shortfall_vs_actual: 154.06, planned_known: true, actual_known: true, plan_chosen: true, over_committed: ["loan"] },
  warnings: ["השוואה בין אפשרויות בלבד — לא המלצה ולא בחירה עבורך."],
} as unknown as Parameters<typeof fundingModel>[0];

test("funding model: server numbers only, server order, certainty and conditions shown, nothing ranked or highlighted", () => {
  const m = fundingModel(fundingView, "recG1", { owed: "גביית חוב" })!;
  assert.equal(m.options.map((o) => o.id).join(","), "existing_balance,dep,loan,owed", "the server's order is kept");
  const need = Object.fromEntries(m.needRows.map((r) => [r.label, r.value]));
  assert.ok(need["כסף קיים מאושר למטרה"].includes("20,000") && need["כסף קיים צפוי (לא מאושר)"].includes("5,000") && need["פער לפי הכסף המאושר בלבד"].includes("180,000"));
  const dep = m.options[1], loan = m.options[2], owed = m.options[3];
  assert.ok(dep.rows[0].label === "הפקדה חודשית נדרשת" && dep.rows[0].value.includes("1,154"));
  assert.ok(dep.verdict.startsWith("אפשרי עד התאריך") && dep.certainty === "צפוי" && dep.lists.some((l) => l.label === "תנאים למימוש" && l.items.includes("הבעלים מאשר את ההפקדות")));
  assert.ok(loan.rows.some((r) => r.label === "התחייבות חדשה" && r.value.includes("1,933") && r.value.includes("60 חודשים")));
  assert.ok(loan.lists.find((l) => l.label === "סיכונים")!.items.includes("brand_new_code"), "an unknown server code is shown as it is, never hidden");
  assert.ok(owed.verdict.includes("לא ידוע") && owed.verdict.includes("אין הסדר החזר רשום") && owed.certainty === "לא ודאי" && owed.title === "גביית חוב");
  assert.ok(m.options.every((o) => !/מומלץ|הכי טוב|מנצח|ציון|דירוג/.test(JSON.stringify(o))));
});

test("funding model: the plan is split by certainty — a debt owed to me is not 'available money'", () => {
  const m = fundingModel(fundingView, "recG1")!;
  const plan = Object.fromEntries(m.plan!.rows.map((r) => [r.label, r.value]));
  assert.ok(plan["מאושר"].includes("20,000") && plan["צפוי"].includes("5,000") && plan["לא ודאי"].includes("100,000"));
  assert.ok(plan["נותר אחרי המאושר בלבד"].includes("180,000") && plan["נותר אחרי מאושר וצפוי"].includes("175,000"));
  assert.ok(!m.plan!.rows.some((r) => /זמין|סה"כ/.test(r.label)), "no single 'available' or total figure");
  assert.ok(m.plan!.allocations[0].includes("לא ודאי") && m.plan!.allocations[0].includes("01/01/2029"));
  const pf = Object.fromEntries(m.portfolio!.rows.map((r) => [r.label, r.value]));
  assert.ok(pf["מקור שהוקצה ליותר מסכומו"] === "loan");
  // planned (the standing plan) and actual (how far we got) are two separate lines, each under its own name with its own shortfall
  assert.ok(pf["חיסכון חודשי מתוכנן (התכנית הקבועה)"].includes("5,000") && pf["חיסכון חודשי בפועל (מה שהופרש עד היום)"].includes("1,000"));
  assert.ok(pf["חוסר מול החיסכון המתוכנן"].includes("0") && pf["חוסר מול החיסכון בפועל"].includes("154"));
  const unknownSavings = fundingModel({ ...fundingView, portfolio: { ...fundingView.portfolio, planned_known: false, planned_monthly_savings: null, shortfall_vs_planned: null } } as unknown as Parameters<typeof fundingModel>[0], "recG1")!;
  const pfu = Object.fromEntries(unknownSavings.portfolio!.rows.map((r) => [r.label, r.value]));
  assert.equal(pfu["חיסכון חודשי מתוכנן (התכנית הקבועה)"], "לא ידוע", "a missing plan is 'unknown', never 0 and never the actual");
  assert.equal(pfu["חוסר מול החיסכון המתוכנן"], "לא ידוע");
  assert.equal(fundingModel({ ...fundingView, portfolio: { ...fundingView.portfolio, plan_chosen: false } }, "recG1")!.portfolio, null);
});

test("funding model: a goal that cannot be planned says why; nothing is invented", () => {
  const blocked = { ...fundingView, goals: [{ need: { ...fundingView.goals[0].need, reason: "missing_date", due: null, gap: null }, options: [], plan: null }] } as unknown as Parameters<typeof fundingModel>[0];
  const m = fundingModel(blocked, "recG1")!;
  assert.equal(m.needReason, "חסר תאריך יעד");
  assert.equal(m.options.length, 0);
  assert.ok(m.needRows.some((r) => r.label === "פער לפי הכסף המאושר בלבד" && r.value === "—"));
});

test("funding screen: renders the intro, the principle and the controls; the result block shows the comparison", () => {
  const overview = { status: "ok", data: { summary: {}, as_of: "2026-10-18", goals: [{ goal_id: "recG1", title: "חתונה", target: 200000, end_date: "2038-06-30", mode: "cumulative" },
    { goal_id: "recP", title: "פרויקט", target: null, end_date: null, mode: "project" }], assets: { items: [] }, loans: { items: [] } } } as unknown as Parameters<typeof FundingSection>[0]["overview"];
  const html = renderToStaticMarkup(createElement(FundingSection, { overview }));
  assert.ok(html.includes("מימון יעד") && html.includes("לא המלצה") && html.includes("כסף צפוי אינו כסף קיים"));
  assert.ok(html.includes("חתונה") && !html.includes("פרויקט"), "only goals with an amount and a date can be planned");
  // progressive disclosure: before a goal is chosen only the goal picker is on screen — no option buttons, no simulation assumptions, no submit
  for (const label of ["הלוואה", "מכירת נכס", "הפקדות חדשות", "גביית חוב שחייבים לי", "השווה אפשרויות", "אינפלציה", "דמי ניהול", "אי־ודאות בתאריך"]) assert.ok(!html.includes(label), `${label} must wait for a goal`);
  assert.ok(html.includes("בחרו יעד"));
  const emptyGoals = renderToStaticMarkup(createElement(FundingSection, { overview: { status: "ok", data: { ...(overview as unknown as { data: object }).data, goals: [] } } as unknown as Parameters<typeof FundingSection>[0]["overview"] }));
  assert.ok(emptyGoals.includes("אין יעד עם סכום ותאריך") && !emptyGoals.includes("אינפלציה") && !emptyGoals.includes("הלוואה"), "no goal: the empty message only");
  const loading = renderToStaticMarkup(createElement(FundingSection, { overview: { status: "loading" } }));
  assert.ok(loading.includes("טוען"));
  const result = renderToStaticMarkup(createElement(FundingResult, { model: fundingModel(fundingView, "recG1")! }));
  assert.ok(result.includes("הפקדה חודשית נדרשת") && result.includes("התוכנית שהוזנה") && result.includes("מבט תיק") && result.includes("fw-option"));
});

test("funding screen: the assumptions only exist for the deposits option and the option buttons only after a goal (source gates)", () => {
  const fs = require("node:fs") as unknown as { readFileSync(p: string, e: string): string };
  const comp = fs.readFileSync("src/components/FamilyWealth.tsx", "utf8");
  const section = comp.slice(comp.indexOf("export function FundingSection"), comp.indexOf("/** Own call, own states; mounted only when the tab is opened"));
  assert.ok(section.includes("{hasGoal && hasDeposits && (") && section.includes("<details") && section.includes("{hasGoal && <div className=\"fw-add\""));
  assert.ok(section.includes("{hasGoal && form.options.map"));
});

test("funding: read-only plumbing — one POST route, run only on submit, no client arithmetic", () => {
  const fs = require("node:fs") as unknown as { readFileSync(p: string, e: string): string };
  const api = fs.readFileSync("src/api.ts", "utf8");
  assert.ok(api.includes("/api/fcc/funding/plan") && api.includes("export async function postFccFundingPlan(body: FundingRequestBody)"));
  const comp = fs.readFileSync("src/components/FamilyWealth.tsx", "utf8");
  const section = comp.slice(comp.indexOf("export function FundingSection"), comp.indexOf("/** Own call, own states; mounted only when the tab is opened"));
  assert.ok(section.includes("postFccFundingPlan(parsed.body)") && !/useEffect\([^)]*run\(/.test(section), "the comparison runs only when asked");
  assert.ok(!/\.reduce\(|Math\./.test(section), "no arithmetic in the funding component");
  const lib = fs.readFileSync("src/lib/familyWealth.ts", "utf8");
  const model = lib.slice(lib.indexOf("export function fundingModel"));
  assert.ok(!/\.reduce\(|Math\.|\bfetch\(/.test(model), "the funding model only words and lays out the server's numbers");
});

test("funding save: a checkbox only on options the server did not rule out, and no checkbox without a selection handler", () => {
  const model = fundingModel(fundingView, "recG1")!;
  const withSel = renderToStaticMarkup(createElement(FundingResult, { model, selection: { selected: [model.options[0].id], onToggle: () => undefined } }));
  const boxes = (withSel.match(/type="checkbox"/g) ?? []).length;
  assert.equal(boxes, model.options.filter((o) => o.feasible !== false).length);
  assert.ok(withSel.includes("לשמור באפשרויות התוכנית"));
  const readOnly = renderToStaticMarkup(createElement(FundingResult, { model }));
  assert.ok(!readOnly.includes('type="checkbox"') && !readOnly.includes("לשמור באפשרויות התוכנית"));
});

test("funding save: plumbing — server recomputes, nothing is written before אשר, no client numbers are saved", () => {
  const fs = require("node:fs") as unknown as { readFileSync(p: string, e: string): string };
  const api = fs.readFileSync("src/api.ts", "utf8");
  const save = api.slice(api.indexOf("export async function postFccFundingSave"), api.indexOf("export async function postFccFundingPlan"));
  assert.ok(save.includes("/api/fcc/funding/plan/save") && save.includes("selected") && !save.includes("/api/fcc/write"));
  const comp = fs.readFileSync("src/components/FamilyWealth.tsx", "utf8");
  const section = comp.slice(comp.indexOf("export function FundingSection"), comp.indexOf("/** Own call, own states; mounted only when the tab is opened"));
  assert.ok(section.includes("postFccFundingSave(state.body, selected)") && section.includes("ContextualComposer") && section.includes("FUNDING_COMPOSER"));
  assert.ok(!/\.reduce\(|Math\./.test(section), "no arithmetic in the funding component");
  assert.ok(FUNDING_COMPOSER.chips.length === 0 && !FUNDING_COMPOSER.freeText, "the draft is opened only by the save button; the review and אשר are the shared flow");
});

test("funding follow-up: a label for every option type; only type + goal go up; the draft is the shared flow", () => {
  assert.equal(Object.keys(FUNDING_FOLLOWUP_LABELS).sort().join(), Object.keys(FUNDING_TYPE_LABELS).sort().join());
  const fs = require("node:fs") as unknown as { readFileSync(p: string, e: string): string };
  const api = fs.readFileSync("src/api.ts", "utf8");
  const call = api.slice(api.indexOf("export async function postFccFundingFollowup"), api.indexOf("export async function postFccFundingPlan"));
  assert.ok(call.includes("/api/fcc/funding/plan/followup") && call.includes("goal_id: goalId, option_type: optionType") && !call.includes("title"));
  const comp = fs.readFileSync("src/components/FamilyWealth.tsx", "utf8");
  const section = comp.slice(comp.indexOf("export function FundingSection"), comp.indexOf("/** Own call, own states; mounted only when the tab is opened"));
  assert.ok(section.includes("postFccFundingFollowup(savedFor.goalId, t)") && section.includes("writer.receipt && !writer.turn"));
  assert.ok(!/\.reduce\(|Math\./.test(section), "no arithmetic in the funding component");
});

test("date window: the margin is typed text -> one whole number; the card shows the early and the late end from the server", () => {
  const ok = (m: string) => fundingRequest({ ...DEFAULT_FUNDING_FORM, goalId: "recG1", marginMonths: m });
  const good = ok("24");
  assert.ok(good.ok && good.body.date_margin_months === 24);
  const blank = ok("");
  assert.ok(blank.ok && !("date_margin_months" in blank.body), "blank = the goal's own saved margin, nothing is sent");
  for (const bad of ["2.5", "-1", "61", "abc"]) assert.ok(!ok(bad).ok, bad);
  const end = (due: string, rm: number) => ({ due, reason: null, gap: 200000, months_to_due: 1, options: [{ id: "dep", type: "new_deposits", feasible: true, reason: null, covers_amount: 200000, available_by: null, monthly_cash_effect: -rm, certainty: "expected", time_to_realize_months: 1, required_monthly: rm }] });
  const withWindow = { ...fundingView, goals: [{ ...fundingView.goals[0], need: { ...fundingView.goals[0].need, date_margin_months: 24 },
    window: { margin_months: 24, early: end("2036-06-30", 4100), late: end("2040-06-30", 2200), note: "x" } }] } as unknown as Parameters<typeof fundingModel>[0];
  const m = fundingModel(withWindow, "recG1")!;
  assert.ok(m.windowNote && m.needRows.some((r) => r.label === "תאריך יעד (משוער)" && r.value.includes("± 24 חודשים")));
  const card = m.options.find((o) => o.id === "dep")!;
  assert.equal(card.windowRows.length, 2);
  assert.ok(card.windowRows[0].label.includes("30/06/2036") && card.windowRows[0].value.includes("4,100"));
  assert.ok(card.windowRows[1].label.includes("30/06/2040") && card.windowRows[1].value.includes("2,200"));
  const firm = fundingModel(fundingView, "recG1")!;
  assert.ok(firm.windowNote === null && firm.options.every((o) => o.windowRows.length === 0));
});

if (failures > 0) throw new Error(`${failures} test(s) failed`);


// ── Funding sources (step 2): the five separate categories, "now" beside "at the due date", the expected figure labelled and apart, missing = "חסר" ──
const noState = { now: null, due: null, early: null, late: null };
const srcItem = (patch: Record<string, unknown>) => ({ source_type: "account", source_id: "recA", name: "קרן", amount: 5000, amount_status: "reported", as_of: "2026-10-01", certainty: "uncertain",
  conditions: [], risks: [], missing_inputs: [], balance_effect: "uses_existing_balance", option_template: null, owner_must_enter: [], ...patch });
const sourcesView = {
  schema_version: "1.0", result_type: "goal_funding_sources", as_of: "2026-10-19", category_labels: {}, warnings: ["רשימת מועמדים בלבד"],
  assumptions: { annual_return_pct: 6, annual_fee_pct: 0.15, inflation_pct: 2, note: "n" },
  goals: [{
    goal_id: "recG1", title: "חתונה", target_amount: 250000, due: "2028-06-30", reason: null,
    date_window: { margin_months: 12, early: "2027-06-30", late: "2029-06-30", note: "n" },
    counts: { liquid_now: 1, liquid_by_due_date: 0, conditional_on_action: 3, expected_not_guaranteed: 1, future_deposits: 1 },
    categories: {
      liquid_now: [srcItem({ source_id: "recC", name: "מזומן", certainty: "confirmed", liquidity: { basis: "immediate", liquid_from: null, state_at: { now: "accessible", due: "accessible", early: "accessible", late: "accessible" } },
        expected_at_due: { label: "expected_by_assumptions", guaranteed: false, amount: 5600, early: 5300, late: 5900, includes_planned_deposits: true, monthly_planned_deposit_included: 100, note: "n" },
        allocation: { allocated_to_this_goal: 0, allocated_elsewhere_amount: 400, allocated_elsewhere: true, over_allocated: false, amount_not_allocated_elsewhere: 4600 }, risks: ["allocated_elsewhere"] })],
      liquid_by_due_date: [],
      conditional_on_action: [
        srcItem({ source_id: "recD", name: "קרן עם תאריך", liquidity: { basis: "dated", liquid_from: "2027-01-01", state_at: { now: "locked", due: "conditional", early: "conditional", late: "conditional" } }, expected_at_due: null,
          conditions: ["liquid_from_reached_eligibility_unverified"] }),
        srcItem({ source_type: "account", source_id: "recN", name: "ללא יתרה", amount: null, amount_status: "missing", as_of: null, missing_inputs: ["balance_snapshot", "liquidity"], liquidity: { basis: "unverified", liquid_from: null, state_at: { ...noState, now: "conditional" } }, expected_at_due: null }),
        srcItem({ source_type: "asset", source_id: "recAS1", name: "דירה", amount: null, amount_status: "missing", certainty: "uncertain", conditions: ["owner_decides_to_sell", "sale_closes"], risks: ["debt_overlap_unresolved"],
          missing_inputs: ["net_proceeds", "expected_sale_date"], balance_effect: "converts_asset_to_cash", asset: { asset_type: "Residential", recorded_value: 2000000, ownership_pct: 100, mortgage_balance: null, linked_debt: null, linked_loan_names: [], monthly_income: null },
          option_template: { type: "asset_sale", asset_id: "recAS1" }, owner_must_enter: ["net_proceeds", "expected_date"] }),
      ],
      expected_not_guaranteed: [srcItem({ source_type: "receivable", source_id: "recOW1", name: "חוב", amount: 100000, amount_status: "recorded_balance", conditions: ["debtor_arrangement"], risks: ["timing_uncertain"],
        receivable: { arrangement: null, next_payment_due: null, end_date: null }, option_template: { type: "receivable_collection", loan_id: "recOW1" }, owner_must_enter: ["expected_net", "expected_date"], balance_effect: "converts_receivable_to_cash" })],
      future_deposits: [srcItem({ source_type: "planned_deposit", source_id: "recC", name: "מזומן", amount: 2000, amount_status: "planned_nominal", certainty: "expected", forecast_inclusion: "included_in_forecast",
        deposit: { monthly_planned: 100, months_until_due: 20, deposit_fee_pct: null, state_at: { now: "accessible", due: "accessible", early: "accessible", late: "accessible" } },
        window: { early: { months: 8, amount: 800 }, late: { months: 32, amount: 3200 } }, balance_effect: "adds_future_deposits_to_account", option_template: { type: "new_deposits", account_id: "recC" }, missing_inputs: ["deposit_fee"] })],
    },
    not_available_by_due_date: [srcItem({ source_id: "recK", name: "נעול", liquidity: { basis: "undated", liquid_from: null, state_at: { now: "locked", due: "locked", early: "locked", late: "locked" } } })],
    gaps: { future_deposits: [{ account_id: "recX", name: "חשבון בלי הפקדה", missing: ["planned_monthly_deposit"] }] },
  }],
} as unknown as Parameters<typeof sourcesModel>[0];

test("funding sources model: five separate categories in a fixed order, each with its count, and no total anywhere", () => {
  const m = sourcesModel(sourcesView, "recG1")!;
  assert.deepEqual(m.categories.map((c) => c.key), ["liquid_now", "liquid_by_due_date", "conditional_on_action", "expected_not_guaranteed", "future_deposits"]);
  assert.deepEqual(m.categories.map((c) => c.count), [1, 0, 3, 1, 1]);
  const text = JSON.stringify(m);
  for (const bad of ["סך הכל זמין", "סה״כ זמין", "total_available", "המומלץ", "הטוב ביותר", "ציון", "דירוג"]) assert.ok(!text.includes(bad), `no '${bad}'`);
  assert.ok(m.dueNote?.includes("± 12 חודשים") && m.dueNote.includes("אף תאריך לא נבחר"));
});

test("funding sources model: 'now' beside 'at the due date' (and the window ends); the expected figure is labelled and apart from the reported balance", () => {
  const card = sourcesModel(sourcesView, "recG1")!.categories[0].cards[0];
  const row = (label: string) => card.rows.find((r) => r.label.startsWith(label))?.value;
  assert.equal(row("יתרה מדווחת"), "₪5,000");
  assert.equal(row("נזילות עכשיו"), "נגיש");
  assert.equal(row("נזילות בתאריך היעד"), "נגיש");
  assert.equal(row("אם התאריך מוקדם"), "נגיש");
  assert.equal(row(SOURCES_EXPECTED_LABEL), "₪5,600");
  assert.equal(row("צפוי אם התאריך מוקדם / מאוחר"), "₪5,300 / ₪5,900");
  assert.equal(row("הוקצה ליעדים אחרים"), "₪400");
  assert.ok(card.lists.some((l) => l.items.includes("הכסף הנגיש כבר מוקצה למטרות אחרות")), "allocated elsewhere is flagged");
});

test("funding sources model: category 2 says why it is empty; a release date is conditional, never accessible", () => {
  const m = sourcesModel(sourcesView, "recG1")!;
  assert.ok(m.categories[1].note.includes("תאריך שחרור אינו זכאות") && m.categories[1].cards.length === 0);
  const dated = m.categories[2].cards.find((c) => c.title === "קרן עם תאריך")!;
  assert.equal(dated.rows.find((r) => r.label === "נזילות עכשיו")?.value, "נעול");
  assert.equal(dated.rows.find((r) => r.label === "נזילות בתאריך היעד")?.value, "מותנה");
  assert.ok(dated.lists[0].items.some((i) => i.includes("הזכאות למשיכה לא אומתה")));
});

test("funding sources model: missing is 'חסר' (never 0) and an asset shows no proceeds or sale date of its own", () => {
  const m = sourcesModel(sourcesView, "recG1")!;
  const nobal = m.categories[2].cards.find((c) => c.title === "ללא יתרה")!;
  assert.equal(nobal.rows.find((r) => r.label.startsWith("יתרה מדווחת"))?.value, "חסר");
  assert.equal(nobal.rows.find((r) => r.label === SOURCES_EXPECTED_LABEL)?.value, "חסר");
  assert.equal(nobal.rows.find((r) => r.label === "נזילות בתאריך היעד")?.value, "חסר");
  assert.ok(nobal.lists.some((l) => l.label === "חסר" && l.items.includes("יתרה מדווחת")));
  const asset = m.categories[2].cards.find((c) => c.title === "דירה")!;
  assert.ok(asset.rows.some((r) => r.label === "שווי רשום (ברוטו — לא תמורה)" && r.value === "₪2,000,000"));
  assert.ok(asset.rows.some((r) => r.label === "תמורה נטו" && r.value.startsWith("חסר")) && asset.rows.some((r) => r.label === "מועד מכירה" && r.value.startsWith("חסר")));
  assert.ok(asset.rows.some((r) => r.label === "השפעה על יתרת ההון"));
});

test("funding sources model: planned deposits are apart, marked as in the forecast, and a debt owed to me is expected, not liquid", () => {
  const m = sourcesModel(sourcesView, "recG1")!;
  const dep = m.categories[4].cards[0];
  assert.ok(dep.rows.some((r) => r.label === "ספירה בתחזית" && r.value.includes("אל תוסיפו ליתרה הקיימת")));
  assert.equal(dep.rows.find((r) => r.label.startsWith("אם התאריך מוקדם"))?.value, "₪800 / ₪3,200");
  assert.ok(m.gaps[0].includes("חסר הפקדה חודשית מתוכננת"));
  const owed = m.categories[3].cards[0];
  assert.equal(owed.typeLabel, "חוב שחייבים לי");
  assert.ok(m.categories[0].cards.every((c) => c.typeLabel !== "חוב שחייבים לי"));
  assert.equal(m.unavailable.length, 1);
});

test("funding sources model: 'add as option' only fills an existing option type (asset sale / debt collection / deposits) and lists what the owner must enter", () => {
  const m = sourcesModel(sourcesView, "recG1")!;
  const asset = m.categories[2].cards.find((c) => c.title === "דירה")!.add!;
  assert.deepEqual(asset.prefill, { asset_id: "recAS1" });
  assert.equal(asset.type, "asset_sale");
  assert.deepEqual(asset.mustEnter, ["תמורה נטו", "תאריך משוער"]);
  const owed = m.categories[3].cards[0].add!;
  assert.deepEqual(owed.prefill, { loan_id: "recOW1" });
  assert.equal(owed.type, "receivable_collection");
  const dep = m.categories[4].cards[0].add!;
  assert.deepEqual(dep.prefill, { source: "account", account_id: "recC" });
  assert.equal(m.categories[0].cards[0].add, null, "existing balance is automatic — no add button");
  const draft = newFundingOption(asset.type, 1);
  const filled = fundingRequest({ ...DEFAULT_FUNDING_FORM, goalId: "recG1", options: [{ ...draft, values: { ...draft.values, ...asset.prefill, net_proceeds: "900000", expected_date: "2027-01-01" } }] });
  assert.ok(filled.ok && (filled.body.options[0] as { asset_id?: string }).asset_id === "recAS1", "the prefilled option feeds the existing request unchanged");
});

test("funding sources list: collapsed categories with counts, 'now' states, the add button once, and the loading / error states", () => {
  const model = sourcesModel(sourcesView, "recG1")!;
  const html = renderToStaticMarkup(createElement(FundingSourcesList, { state: { status: "ok", data: sourcesView, goalId: "recG1", saved: null }, model, addedKeys: [], addedNote: null, onAdd: () => undefined }));
  assert.ok(html.includes("מקורות אפשריים ליעד") && html.includes("כסף נזיל עכשיו (1)") && html.includes("כסף שיהפוך לנגיש עד תאריך היעד (0)") && html.includes("הפקדות עתידיות שטרם בוצעו (1)"));
  assert.ok(!html.includes("<details open"), "categories start collapsed — the screen is not flooded");
  assert.equal((html.match(/הוסף כאפשרות/g) ?? []).length, 3);
  const added = renderToStaticMarkup(createElement(FundingSourcesList, { state: { status: "ok", data: sourcesView, goalId: "recG1", saved: null }, model, addedKeys: ["asset_sale:recAS1"], addedNote: "נוספה אפשרות", onAdd: () => undefined }));
  assert.equal((added.match(/הוסף כאפשרות/g) ?? []).length, 2);
  assert.ok(added.includes("נוסף לטופס") && added.includes("נוספה אפשרות"));
  assert.ok(renderToStaticMarkup(createElement(FundingSourcesList, { state: { status: "loading" }, model: null, addedKeys: [], addedNote: null, onAdd: () => undefined })).includes("טוען מקורות"));
  assert.ok(renderToStaticMarkup(createElement(FundingSourcesList, { state: { status: "error", code: 429 }, model: null, addedKeys: [], addedNote: null, onAdd: () => undefined })).includes("יותר מדי חישובים"));
});

test("funding sources: shown only after a goal is chosen, one read-only call per goal, no client arithmetic", () => {
  const fs = require("node:fs") as unknown as { readFileSync(p: string, e: string): string };
  const comp = fs.readFileSync("src/components/FamilyWealth.tsx", "utf8");
  const section = comp.slice(comp.indexOf("export function FundingSection"), comp.indexOf("export function FundingSourcesList"));
  assert.ok(section.includes("{hasGoal && <FundingSourcesList"), "gated on a chosen goal");
  assert.ok(section.includes("[form.goalId]") && section.includes("options: []"), "one call when the goal changes, with no options");
  const list = comp.slice(comp.indexOf("export function FundingSourcesList"), comp.indexOf("function Rows("));
  assert.ok(!/\.reduce\(|Math\.|\bfetch\(/.test(section + list), "no arithmetic and no direct fetch");
  const lib = fs.readFileSync("src/lib/familyWealth.ts", "utf8");
  const model = lib.slice(lib.indexOf("export function sourcesModel") - 3000);
  assert.ok(!/\.reduce\(|Math\.|\bfetch\(/.test(model), "the sources model only words and lays out the server's numbers");
  const before = renderToStaticMarkup(createElement(FundingSection, { overview: { status: "ok", data: { summary: {}, as_of: "2026-10-18", goals: [{ goal_id: "recG1", title: "חתונה", target: 200000, end_date: "2038-06-30", mode: "cumulative" }], assets: { items: [] }, loans: { items: [] } } } as unknown as Parameters<typeof FundingSection>[0]["overview"] }));
  assert.ok(!before.includes("מקורות אפשריים ליעד"), "nothing about sources before a goal is chosen");
});


test("funding sources: a late answer for another goal is dropped, the same request is cached, the call is debounced, every failure has its own message", () => {
  assert.ok(isCurrentGoal("recB", "recB") && !isCurrentGoal("recB", "recA") && !isCurrentGoal("", ""), "A's late answer must not overwrite B's sources");
  const body = { goal_id: "recG1", assumptions: { annual_return_pct: 6, annual_fee_pct: 0.15, inflation_pct: 2 }, options: [], allocation_plan: [] };
  assert.equal(sourcesCacheKey(body), sourcesCacheKey({ ...body }));
  assert.ok(sourcesCacheKey(body) !== sourcesCacheKey({ ...body, goal_id: "recG2" }) && sourcesCacheKey(body) !== sourcesCacheKey({ ...body, date_margin_months: 12 }));
  assert.ok(SOURCES_DEBOUNCE_MS >= 300 && SOURCES_DEBOUNCE_MS <= 600);
  const texts = [404, 429, 503, -1, undefined, 500].map((c) => sourcesErrorText(c));
  assert.equal(new Set(texts).size, 6, "404 / 429 / 503 / older server / network / other each say something different");
  assert.ok(sourcesErrorText(undefined).includes("חיבור") && sourcesErrorText(503).includes("עסוק"));
  const fs = require("node:fs") as unknown as { readFileSync(p: string, e: string): string };
  const comp = fs.readFileSync("src/components/FamilyWealth.tsx", "utf8");
  const section = comp.slice(comp.indexOf("export function FundingSection"), comp.indexOf("export function FundingSourcesList"));
  assert.ok(section.includes("isCurrentGoal(goalRef.current, goalId)"), "both the effect and the compare answer check the goal on screen");
  assert.ok(section.includes("setTimeout(") && section.includes("clearTimeout(timer)") && section.includes("sourcesCache.current"), "debounced, cancellable, cached");
  assert.ok((section.match(/isCurrentGoal\(goalRef\.current, goalId\)/g) ?? []).length >= 3, "effect then + catch and the compare answer");
});

test("funding sources: the expected figure says it is the end of the last completed month, and a missing planned deposit stays missing", () => {
  assert.ok(SOURCES_EXPECTED_LABEL.includes("סוף החודש האחרון שהושלם") && SOURCES_EXPECTED_LABEL.includes("לא מובטח"));
  const noDeposit = JSON.parse(JSON.stringify(sourcesView));
  noDeposit.goals[0].categories.liquid_now[0].expected_at_due = { ...noDeposit.goals[0].categories.liquid_now[0].expected_at_due, includes_planned_deposits: false, monthly_planned_deposit_included: null };
  const card = sourcesModel(noDeposit, "recG1")!.categories[0].cards[0];
  assert.ok(!card.rows.some((r) => r.label === "כולל הפקדה חודשית מתוכננת"), "no planned deposit entered: nothing is claimed as included");
});


// ── Funding sources step 3: "what changed since the saved plan" — saved beside today, comparison only, missing = "חסר", nothing computed in the page ──
const cmpView = {
  schema_version: "1.0", result_type: "saved_plan_comparison", as_of: "2026-10-19", note: "n",
  goals: [
    { goal_id: "recG1", status: "ok", plan_id: "recFP1", saved: { as_of: "2026-09-01", saved_at: "2026-09-02", plans_found: 1 }, today_reason: null, any_change: true,
      need: [{ field: "target", saved: 250000, today: 250000, changed: false }, { field: "due", saved: "2028-06-30", today: "2028-06-30", changed: false },
        { field: "confirmed_existing", saved: 400, today: 1000, changed: true }, { field: "gap", saved: 249600, today: null, changed: true }],
      options: [
        { id: "existing_balance", type: "existing_balance", present_today: true, changed: true, fields: [
          { field: "feasible", saved: true, today: true, changed: false }, { field: "covers_amount", saved: 400, today: 1000, changed: true },
          { field: "certainty", saved: "confirmed", today: "expected", changed: true }, { field: "available_by", saved: null, today: null, changed: false },
          { field: "reason", saved: null, today: null, changed: false }] },
        { id: "sale", type: "asset_sale", present_today: false, changed: true, fields: [{ field: "covers_amount", saved: 90000, today: null, changed: true }] },
      ] },
    { goal_id: "recG2", status: "no_saved_plan" },
    { goal_id: "recG3", status: "unavailable", reason: "saved_request_no_longer_valid" },
  ],
} as unknown as Parameters<typeof savedChangesModel>[0];

test("saved plan changes: saved beside today, the changed rows marked, missing is 'חסר' and a reason that is absent is '—'", () => {
  const m = savedChangesModel(cmpView, "recG1")!;
  assert.equal(m.status, "ok");
  assert.ok(m.headline.startsWith(SAVED_TITLE) && m.headline.includes("יש שינויים"));
  assert.ok(m.savedLine?.includes("02/09/2026"));
  const need = (label: string) => m.need.find((r) => r.label === label)!;
  assert.deepEqual([need("כסף קיים מאושר").saved, need("כסף קיים מאושר").today, need("כסף קיים מאושר").changed], ["₪400", "₪1,000", true]);
  assert.deepEqual([need("סכום יעד").changed, need("תאריך יעד").today], [false, "30/06/2028"]);
  assert.equal(need("פער לפי המאושר בלבד").today, "חסר");
  const ex = m.options[0];
  assert.equal(ex.title, "כסף קיים (הקצאות)");
  assert.equal(ex.rows.find((r) => r.label === "ודאות")?.saved, "מאושר");
  assert.equal(ex.rows.find((r) => r.label === "ודאות")?.today, "צפוי");
  assert.equal(ex.rows.find((r) => r.label === "אפשרות")?.today, "אפשרי עד התאריך");
  assert.equal(ex.rows.find((r) => r.label === "זמין עד")?.today, "חסר");
  assert.equal(ex.rows.find((r) => r.label === "סיבה")?.today, "—");
  const gone = m.options[1];
  assert.ok(!gone.presentToday && gone.rows[0].today === "חסר" && gone.rows[0].saved === "₪90,000");
});

test("saved plan changes: nothing for a goal without a saved plan, a plain sentence when it cannot be compared, no advice words", () => {
  assert.equal(savedChangesModel(cmpView, "recG2"), null);
  assert.equal(savedChangesModel(cmpView, "recZZ"), null);
  assert.equal(savedChangesModel(undefined, "recG1"), null);
  const u = savedChangesModel(cmpView, "recG3")!;
  assert.equal(u.status, "unavailable");
  assert.ok(u.unavailable?.includes("אינו קיים") && u.need.length === 0 && u.options.length === 0);
  const text = JSON.stringify(savedChangesModel(cmpView, "recG1"));
  for (const bad of ["עדיף", "מומלץ", "כדאי", "הטוב ביותר", "ציון", "דירוג", "החלטה חדשה"]) assert.ok(!text.includes(bad), `no '${bad}'`);
  assert.ok(SAVED_NOTE.includes("אינה מתעדכנת") && SAVED_NOTE.includes("השוואה בלבד"));
});

test("saved plan changes: the card is collapsed, marks what changed, and says the saved plan is not updated", () => {
  const html = renderToStaticMarkup(createElement(SavedPlanChanges, { model: savedChangesModel(cmpView, "recG1")! }));
  assert.ok(html.includes("<details") && !html.includes("<details open"));
  assert.ok(html.includes("נשמר: ₪400 · היום: ₪1,000 · השתנה") && html.includes("האפשרות אינה מופיעה בחישוב של היום") && html.includes("אינה מתעדכנת"));
  assert.ok(!html.includes("<button"), "nothing to click: a comparison has no action");
  const un = renderToStaticMarkup(createElement(SavedPlanChanges, { model: savedChangesModel(cmpView, "recG3")! }));
  assert.ok(un.includes("אי אפשר להשוות"));
});

test("saved plan changes: shown only after a goal is chosen, from the same single call; the page computes no difference", () => {
  const fs = require("node:fs") as unknown as { readFileSync(p: string, e: string): string };
  const comp = fs.readFileSync("src/components/FamilyWealth.tsx", "utf8");
  const section = comp.slice(comp.indexOf("export function FundingSection"), comp.indexOf("export function FundingSourcesList"));
  assert.ok(section.includes("{hasGoal && savedModel && <SavedPlanChanges"), "gated on a chosen goal and on a saved plan");
  assert.ok(section.includes("plan.saved_plan_comparison"), "the comparison rides on the sources answer — no extra call");
  assert.equal((section.match(/postFccFundingPlan\(/g) ?? []).length, 2, "still only the sources call and the compare call");
  const lib = fs.readFileSync("src/lib/familyWealth.ts", "utf8");
  const model = lib.slice(lib.indexOf("export function savedChangesModel") - 2500);
  assert.ok(!/\.reduce\(|Math\.|\bfetch\(|\bsaved\s*-\s*|\btoday\s*-\s*/.test(model), "the saved-plan model only words and lays out the server's values");
  const types = fs.readFileSync("src/types.ts", "utf8");
  assert.ok(!/delta|difference|better|worse/.test(types.slice(types.indexOf("export type SavedPlanValue"), types.indexOf("export interface FundingPlan {"))));
});

test("funding model: an allocation above the target is shown as a display-only excess; an exact fit shows no excess row", () => {
  const over = { ...fundingView, goals: [{ ...fundingView.goals[0], plan: { ...fundingView.goals[0].plan, allocated_total: 275000, over_target_by: 25000 } }] } as unknown as Parameters<typeof fundingModel>[0];
  const rows = Object.fromEntries(fundingModel(over, "recG1")!.plan!.rows.map((r) => [r.label, r.value]));
  assert.ok(rows["הוקצה מעבר ליעד (להצגה בלבד — התוכנית לא שונתה)"].includes("25,000"));
  assert.ok(!fundingModel(fundingView, "recG1")!.plan!.rows.some((r) => r.label.startsWith("הוקצה מעבר ליעד")));
});

test("funding model: server notes written in English are shown in Hebrew; an unlisted note is shown as written, never hidden", () => {
  const m = fundingModel(fundingView, "recG1")!;
  assert.equal(m.plan!.note, "הכיסוי מפוצל לפי ודאות ואינו מסוכם ל״כסף זמין״ אחד.");
  assert.equal(serverNote("net proceeds as entered; sale amount on record is gross and is not used"), "תמורה נטו כפי שהוזנה; סכום המכירה שברשומת הנכס הוא ברוטו ואינו בשימוש.");
  assert.equal(serverNote("collected money is not income and is not a liability of yours"), "כסף שנגבה אינו הכנסה ואינו התחייבות שלך.");
  assert.equal(serverNote("some future note"), "some future note");
});

const requiredCard = {
  amount: 9859.84, reason: null, gap: 250000, months: 24, due: "2028-10-19", total_deposits: 236636.16,
  assumptions: { annual_return_pct: 6, fee_pct: 0.15, deposit_fee_pct: 0, inflation_pct: 2, sources: { annual_return_pct: "default", annual_fee_pct: "default", inflation_pct: "owner" } },
  basis: "assumptions",
  sensitivity: [{ label: "low", annual_return_pct: 4, amount: 10200 }, { label: "base", annual_return_pct: 6, amount: 9859.84 }, { label: "high", annual_return_pct: 8, amount: 9500 }],
  scenarios: [{ basis: "after_all_selected", remaining: 15000, amount: 591.59 }],
  planned_monthly_savings: 13000,
  note: "new money only (existing balances are not counted); not split between goals; the planned figure is the family's standing plan, shown beside it and never netted",
};

test("required monthly card: the server's amount, every assumption with its source, the range, and the planned savings beside it (never netted)", () => {
  const withCard = { ...fundingView, goals: [{ ...fundingView.goals[0], required_monthly_card: requiredCard }] } as unknown as Parameters<typeof fundingModel>[0];
  const c = fundingModel(withCard, "recG1")!.requiredCard!;
  assert.equal(c.title, "הפקדה חודשית נדרשת");
  assert.ok(c.headline.includes("9,860") || c.headline.includes("9,859"), c.headline);
  assert.ok(c.subtitle!.includes("250,000") && c.subtitle!.includes("19/10/2028") && c.subtitle!.includes("24 חודשי הפקדה") && c.subtitle!.includes("כסף חדש בלבד"));
  const rows = Object.fromEntries(c.rows.map((r) => [r.label, r.value]));
  assert.ok(rows["תשואה שנתית"].includes("6%") && rows["תשואה שנתית"].includes("ברירת מחדל מערכתית") && rows["אינפלציה"].includes("הנחת בעלים"));
  assert.ok(Object.entries(rows).some(([k, v]) => k.startsWith("חיסכון חודשי מתוכנן") && v.includes("13,000")));
  assert.deepEqual(c.sensitivity.map((s) => s.label), ["תשואה נמוכה (4%)", "תשואה לפי ההנחה (6%)", "תשואה גבוהה (8%)"]);
  assert.ok(c.scenarios[0].label.includes("אחרי כל התוכנית (כולל לא ודאי)") && c.scenarios[0].label.includes("15,000") && c.scenarios[0].value.includes("592"));
  assert.ok(!/[A-Za-z]{4,}/.test(c.note), "the server's English note is shown in Hebrew");
});

test("required monthly card: no amount is said plainly — never an invented figure", () => {
  const view = (card: object) => fundingModel({ ...fundingView, goals: [{ ...fundingView.goals[0], required_monthly_card: card }] } as unknown as Parameters<typeof fundingModel>[0], "recG1")!.requiredCard!;
  const unreachable = view({ amount: null, reason: "unreachable_under_assumptions" });
  assert.equal(unreachable.headline, "אין סכום להצגה");
  assert.ok(unreachable.subtitle!.includes("לא ניתן להשיג") && unreachable.rows.length === 0 && unreachable.sensitivity.length === 0);
  assert.ok(view({ amount: 0, reason: "no_gap" }).headline.length > 0);
  assert.equal(fundingModel(fundingView, "recG1")!.requiredCard, null, "an old server answer without the card shows no card");
});

test("required monthly card is rendered above the options and carries no recommendation wording", () => {
  const withCard = { ...fundingView, goals: [{ ...fundingView.goals[0], required_monthly_card: requiredCard }] } as unknown as Parameters<typeof fundingModel>[0];
  const html = renderToStaticMarkup(createElement(FundingResult, { model: fundingModel(withCard, "recG1")! }));
  assert.ok(html.indexOf("הפקדה חודשית נדרשת") > -1 && html.indexOf("fw-required") < html.indexOf("fw-option"));
  assert.ok(!/מומלץ|כדאי|הטוב ביותר|המלצה/.test(html.replace("לא המלצה", "")));
});
