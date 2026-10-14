// Plain node + esbuild test (see package.json `npm test`).
declare function require(id: string): { readFileSync(path: string, enc: string): string; readdirSync(path: string): string[] };
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { FamilyWealth, FamilyWealthCard } from "../components/FamilyWealth";
import { FccTabBar } from "../components/FccTabBar";
import { LineChart, StackBar } from "../components/PortfolioLabCharts";
import type { FccOverview, PortfolioLabView } from "../types";
import { FCC_TABS, panelId, tabForKey, tabId } from "./fccTabs";
import {
  BALANCE_PLACEHOLDER, DEFAULT_LAB_FORM, FAMILY_TABS, OPEN_LABEL, SCREEN_TITLE, TABS_ARIA_LABEL, SELF_REPORTED, barChartModel, breakdownParts, familyCardModel,
  labKpiCards, labParams, labTableRows, lineChartModel, savingsTabModel,
} from "./familyWealth";

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

const release = { income_net: 10000, income_target: 15000, fixed_level: 8000, shortfall: 5000, from_fixed: 3000, extra: 0, available: 3000,
  deposited: 2500, remaining: 500, expected: 3000, gap: 500, month: "2026-10", closing: false, destination: { id: "r", title: "תכנון פנסיוני" } };
const plan = { mode: "monthly_level", target: 8000, actual: 5000, remaining: 3000, dynamic_target_per_week: 0, goals: 2 };
const overview = { summary: { savings: plan }, savings_release: release, as_of: "2026-10-14" } as unknown as FccOverview;

test("screen name and the two tabs are the agreed ones", () => {
  assert.equal(SCREEN_TITLE, "תכנון חיסכון לטווח ארוך");
  assert.equal(FAMILY_TABS.map((t) => t.label).join(" | "), "החיסכון שלי | מעבדת העתיד");
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
  assert.ok(!m.rows.some((r) => /פער/.test(r.label + (r.hint ?? ""))), "no gap is shown in this PR (it would be client arithmetic)");
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
  const html = renderToStaticMarkup(createElement(FamilyWealth, { data: overview, onBack: () => undefined }));
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
  assert.equal(tabForKey("savings" as const, "ArrowLeft", true, FAMILY_TABS), "lab");
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
  const screen = renderToStaticMarkup(createElement(FamilyWealth, { data: overview, onBack: () => undefined }));
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

test("the screen is never reachable without the existing FCC gate: it is only opened from inside FinancialControlCenter", () => {
  const fs = require("fs");
  const app = fs.readFileSync("src/App.tsx", "utf8");
  assert.ok(!app.includes("FamilyWealth") && !app.includes("PortfolioLab"), "App.tsx must not open it directly");
  const fcc = fs.readFileSync("src/components/FinancialControlCenter.tsx", "utf8");
  assert.ok(fcc.includes("familyOpen") && fcc.includes("<FamilyWealthCard"));
});

if (failures) throw new Error(`${failures} test(s) failed`);
console.log("all familyWealth tests passed");
