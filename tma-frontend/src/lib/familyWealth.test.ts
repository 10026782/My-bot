// Plain node + esbuild test (see package.json `npm test`).
declare function require(id: string): { readFileSync(path: string, enc: string): string; readdirSync(path: string): string[] };
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { FamilyWealth, FamilyWealthCard } from "../components/FamilyWealth";
import { FccTabBar } from "../components/FccTabBar";
import { LineChart, StackBar } from "../components/PortfolioLabCharts";
import type { FccAccountsForecast, FccAccountsView, FccOverview, PortfolioLabView } from "../types";
import { AccountsPanel, ForecastResult, FundingResult, FundingSection } from "../components/FamilyWealth";
import { ContextualComposer } from "../components/FccTabBar";
import { ACCOUNTS_COMPOSER, COMPOSER, FUNDING_COMPOSER } from "./fccTabs";
import { FCC_TABS, panelId, tabForKey, tabId } from "./fccTabs";
import {
  BALANCE_PLACEHOLDER, DEFAULT_LAB_FORM, FAMILY_TABS, OPEN_LABEL, SCREEN_TITLE, TABS_ARIA_LABEL, SELF_REPORTED, barChartModel, breakdownParts, familyCardModel,
  DEFAULT_FORECAST_FORM, DEFAULT_FUNDING_FORM, FUNDING_FIELDS, FUNDING_FOLLOWUP_LABELS, FUNDING_TYPE_LABELS, fundingModel, fundingRequest, newFundingOption, type FundingForm, accountsTabModel, forecastModel, forecastParams, labKpiCards, labParams, labTableRows, lineChartModel, savingsTabModel,
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
  portfolio: { monthly_burden_in_plan: 1154.06, planned_monthly_savings: 1000, shortfall: 154.06, capacity_known: true, plan_chosen: true, over_committed: ["loan"] },
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
  assert.ok(pf["חוסר מול החיסכון המתוכנן"].includes("154") && pf["מקור שהוקצה ליותר מסכומו"] === "loan");
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
  for (const label of ["הלוואה", "מכירת נכס", "הפקדות חדשות", "גביית חוב שחייבים לי"]) assert.ok(html.includes(label), label);
  assert.ok(html.includes("השווה אפשרויות"));
  const loading = renderToStaticMarkup(createElement(FundingSection, { overview: { status: "loading" } }));
  assert.ok(loading.includes("טוען"));
  const result = renderToStaticMarkup(createElement(FundingResult, { model: fundingModel(fundingView, "recG1")! }));
  assert.ok(result.includes("הפקדה חודשית נדרשת") && result.includes("התוכנית שהוזנה") && result.includes("מבט תיק") && result.includes("fw-option"));
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

if (failures > 0) throw new Error(`${failures} test(s) failed`);
