// Plain node + esbuild test (see package.json `npm test`).
declare function require(id: string): { readFileSync(path: string, enc: string): string; readdirSync(path: string): string[] };
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { FamilyWealth, FamilyWealthCard } from "../components/FamilyWealth";
import { FccTabBar } from "../components/FccTabBar";
import { LineChart, StackBar } from "../components/PortfolioLabCharts";
import type { FccAccountsForecast, FccAccountsView, FccOverview, PortfolioLabView } from "../types";
import { AccountsPanel, ForecastResult } from "../components/FamilyWealth";
import { ContextualComposer } from "../components/FccTabBar";
import { ACCOUNTS_COMPOSER, COMPOSER } from "./fccTabs";
import { FCC_TABS, panelId, tabForKey, tabId } from "./fccTabs";
import {
  BALANCE_PLACEHOLDER, DEFAULT_LAB_FORM, FAMILY_TABS, OPEN_LABEL, SCREEN_TITLE, TABS_ARIA_LABEL, SELF_REPORTED, barChartModel, breakdownParts, familyCardModel,
  DEFAULT_FORECAST_FORM, accountsTabModel, forecastModel, forecastParams, labKpiCards, labParams, labTableRows, lineChartModel, savingsTabModel,
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

test("screen name and the three tabs are the agreed ones", () => {
  assert.equal(SCREEN_TITLE, "תכנון חיסכון לטווח ארוך");
  assert.equal(FAMILY_TABS.map((t) => t.label).join(" | "), "החיסכון שלי | החשבונות | מעבדת העתיד");
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
  assert.equal(tabForKey("accounts" as const, "ArrowLeft", true, FAMILY_TABS), "lab");
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
