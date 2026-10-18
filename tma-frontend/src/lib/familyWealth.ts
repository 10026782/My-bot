// "תכנון חיסכון לטווח ארוך" (family wealth) — presentation only. No fetching, no storage, no financial arithmetic:
// every number shown comes from the server (FCC overview / portfolio_lab view); this only words and lays them out.
import type { FccAccount, FccAccountsForecast, FccAccountsView, FccForecastParams, FccOverview, PortfolioLabParams, PortfolioLabView } from "../types";
import { money } from "./fccPresentation";

export const SCREEN_TITLE = "תכנון חיסכון לטווח ארוך";   // owner's choice (14/10/2026); one constant so the name can change in one place

// Every place that names the screen derives from SCREEN_TITLE: entry card, screen title, open button, tab-strip label.
export const OPEN_LABEL = `פתח: ${SCREEN_TITLE}`;
export const TABS_ARIA_LABEL = `אזורי ${SCREEN_TITLE}`;

export type FamilyTabKey = "savings" | "accounts" | "lab";
export const FAMILY_TABS: { key: FamilyTabKey; label: string }[] = [
  { key: "savings", label: "החיסכון שלי" },
  { key: "accounts", label: "החשבונות" },
  { key: "lab", label: "מעבדת העתיד" },
];
export const FAMILY_TAB_PREFIX = "fw";

/** Every deposit figure is something the owner recorded (review -> "אשר"); nothing is matched against a bank or a fund. */
export const SELF_REPORTED = "דיווח עצמי — לא מאומת מול בנק או קרן";
export const BALANCE_PLACEHOLDER = "יתרת התיק תוצג כהערכה לפי הפקדות, עם עדכון ידני מדי כמה חודשים — בשלב הבא.";

export interface SavingsRow { key: string; label: string; value: string; hint?: string }
export interface SavingsTabModel { rows: SavingsRow[]; notes: string[]; hasData: boolean }

/** The savings tab from data the FCC overview already carries. Plan = the standing level of the savings goal(s); actual =
 *  this month's recorded deposits on the long-term goal; "צפוי להתפנות" is derived from income and is NOT a plan. */
export function savingsTabModel(data: Pick<FccOverview, "summary" | "savings_release" | "savings_history">): SavingsTabModel {
  const plan = data.summary.savings;
  const release = data.savings_release ?? null;
  const rows: SavingsRow[] = [];
  rows.push(plan && plan.mode === "monthly_level"
    ? { key: "plan", label: "הפקדה חודשית מתוכננת", value: money(plan.actual), hint: `יעד: ${money(plan.target)}` }
    : { key: "plan", label: "הפקדה חודשית מתוכננת", value: "לא הוגדרה", hint: "אין יעד חיסכון חודשי פעיל" });
  rows.push(release
    ? { key: "deposited", label: "הופקד החודש", value: money(release.deposited), hint: SELF_REPORTED }
    : { key: "deposited", label: "הופקד החודש", value: "לא זמין", hint: "אי אפשר לגזור — חסר יעד הכנסה או הכנסה קבועה" });
  if (release) {
    rows.push({ key: "expected", label: "צפוי להתפנות", value: money(release.expected),
                hint: "נגזר מההכנסה החודשית — אינו הפקדה מתוכננת" });
  }
  const h = data.savings_history ?? null;
  if (h) {
    rows.push({ key: "ytd", label: "הופקד מתחילת השנה", value: money(h.ytd), hint: `${h.deposit_count} הפקדות · ${SELF_REPORTED}` });
    rows.push({ key: "average", label: "ממוצע חודשי", value: money(h.monthly_average), hint: `על פני ${h.months_elapsed} חודשים מתחילת השנה` });
    rows.push({ key: "streak", label: "רצף חודשים עם הפקדה", value: String(h.streak), hint: h.last_deposit ? `הפקדה אחרונה: ${h.last_deposit}` : "עוד לא נרשמה הפקדה" });
    rows.push({ key: "ytd_gap", label: "פער מול התכנון מתחילת השנה", value: money(h.ytd_gap),
                hint: `תכנון מצטבר ${money(h.ytd_plan)} · פער נרשם ואינו מתמלא אוטומטית` });
  }
  rows.push({ key: "balance", label: "יתרת תיק", value: "לא זמינה", hint: BALANCE_PLACEHOLDER });
  return {
    rows,
    notes: ["אין כאן הבטחת תשואה — המספרים הם דיווח והנחות בלבד."],
    hasData: Boolean(plan || release || h),
  };
}

/** Entry card on the monthly FCC tab: one short line, only from what the overview already has. */
export function familyCardModel(data: Pick<FccOverview, "summary" | "savings_release" | "savings_history">): { title: string; value: string; hint: string } {
  const release = data.savings_release ?? null;
  return {
    title: SCREEN_TITLE,
    value: release ? `הופקד החודש ${money(release.deposited)}` : "אין עדיין נתון לחודש",
    hint: release ? SELF_REPORTED : "פתחו את המסך לתכנון ולמעבדת העתיד",
  };
}

// ── Accounts tab (D1 step 7 / B1): wording + layout of what the server derived. No sums, no estimates computed here. ──
export const ACCOUNT_TYPE_LABELS: Record<string, string> = {
  pension: "קרן פנסיה", study_fund: "קרן השתלמות", provident_investment: "קופת גמל להשקעה", managers_insurance: "ביטוח מנהלים",
  brokerage: "חשבון השקעות", liquid: "נזיל", other: "אחר",
};
export const LIQUIDITY_LABELS: Record<string, string> = {
  immediate: "נזיל מיד", locked_until_date: "נעול עד תאריך", age_based: "לפי גיל", unknown: "לא ידוע",
};
export const BALANCE_FACT_NOTE = "השווי הוא היתרה האחרונה שדווחה — עובדה. ההערכה מתווספת בנפרד ואינה נכללת בסכום המאוחד.";
export const NO_SNAPSHOT = "אין יתרה שדווחה";
export const NO_ACCOUNTS_TITLE = "עוד אין חשבונות";
export const NO_ACCOUNTS_MESSAGE = "חשבונות פנסיה, השתלמות והשקעות יוצגו כאן אחרי שיוזנו. אפשר יהיה להוסיף יתרה בשלב הבא.";

const verificationNote = (v: string | null | undefined): string =>
  v === "self_reported" ? SELF_REPORTED : v === "statement" ? "לפי דוח" : v === "bank_or_fund_confirmed" ? "מאומת מול בנק או קרן" : "";

export interface AccountRow { id: string; title: string; subtitle: string; value: string; hint: string; estimate?: string; closed: boolean }
export interface AccountsTabModel { hasAccounts: boolean; total: SavingsRow; extras: SavingsRow[]; rows: AccountRow[]; notes: string[] }

export function accountRow(a: FccAccount): AccountRow {
  const kind = a.account_type ? ACCOUNT_TYPE_LABELS[a.account_type] ?? a.account_type : "";
  const subtitle = [kind, a.institution, a.holder_names].filter(Boolean).join(" · ");
  const liquidity = a.liquidity ? (LIQUIDITY_LABELS[a.liquidity] ?? a.liquidity) : "";
  const b = a.balance;
  return {
    id: a.id, title: a.name || "חשבון ללא שם", subtitle, closed: a.status === "closed",
    value: b ? money(b.value) : NO_SNAPSHOT,
    hint: b ? [`נכון ל-${b.as_of}`, verificationNote(b.verification), liquidity].filter(Boolean).join(" · ") : [liquidity, "הוסיפו יתרה כדי לראות שווי"].filter(Boolean).join(" · "),
    estimate: b && b.estimate.movement_count > 0 ? `הערכה בעקבות ${b.estimate.movement_count} תנועות מאז: ${money(b.estimate.value)}` : undefined,
  };
}

/** The accounts tab from the server view: the consolidated value is the server's sum of snapshots; closed accounts are listed, not counted. */
export function accountsTabModel(view: FccAccountsView): AccountsTabModel {
  const t = view.totals;
  const total: SavingsRow = t.consolidated_value == null
    ? { key: "total", label: "שווי מאוחד", value: "לא זמין", hint: "עוד אין יתרה שדווחה באף חשבון פעיל" }
    : { key: "total", label: "שווי מאוחד", value: money(t.consolidated_value),
        hint: `${t.accounts_with_value} חשבונות עם יתרה${t.oldest_snapshot ? ` · העדכון הישן ביותר: ${t.oldest_snapshot}` : ""}${t.all_self_reported ? ` · ${SELF_REPORTED}` : ""}` };
  const extras: SavingsRow[] = [];
  if (t.estimated_value != null && t.estimated_value !== t.consolidated_value) {
    extras.push({ key: "estimate", label: "הערכה לפי תנועות מאז", value: money(t.estimated_value), hint: "הערכה בלבד — אינה חלק מהשווי המאוחד" });
  }
  if (t.accounts_without_snapshot > 0) extras.push({ key: "missing", label: "חשבונות בלי יתרה", value: String(t.accounts_without_snapshot), hint: "אינם נספרים בשווי המאוחד" });
  if (t.closed_accounts > 0) extras.push({ key: "closed", label: "חשבונות סגורים", value: String(t.closed_accounts), hint: "מוצגים ברשימה, לא נכללים בסכום" });
  return {
    hasAccounts: view.accounts.length > 0, total, extras, rows: view.accounts.map(accountRow),
    notes: [BALANCE_FACT_NOTE, "אין כאן הבטחת תשואה — המספרים הם דיווח בלבד."],
  };
}

// ── Accounts forecast (D1 step 7 / A1): the form is strings while typing; every number shown comes from the server's engine run. ──
export interface ForecastForm { years: string; returnPct: string; feePct: string; inflationPct: string; deposits: Record<string, string> }
export const DEFAULT_FORECAST_FORM: ForecastForm = { years: "20", returnPct: "6", feePct: "0.15", inflationPct: "2", deposits: {} };
export const FORECAST_TITLE = "תחזית לפי הנחות";
export const FORECAST_NOTE = "תחזית מבוססת הנחות בלבד — לא הבטחת תשואה ולא המלצה. נקודת המוצא היא היתרה האחרונה שדווחה בכל חשבון; ההפקדה החודשית היא הנחה שלך (ברירת מחדל 0).";
export const FORECAST_ACCOUNT_HEAD = ["חשבון", "יתרת פתיחה", "הפקדה חודשית", "דמי ניהול", "שווי סופי", "שווי ריאלי"];

/** Typed text -> request body. Blank / non-numeric input is an error shown on the form, never silently 0. A blank deposit means "no deposit". */
export function forecastParams(form: ForecastForm): { ok: true; params: FccForecastParams } | { ok: false; error: string } {
  const num = (text: string, name: string): number | string => {
    const v = text.trim() === "" ? NaN : Number(text);
    return Number.isFinite(v) ? v : `${name}: יש להזין מספר`;
  };
  const f = { years: num(form.years, "מספר שנים"), ret: num(form.returnPct, "תשואה"), fee: num(form.feePct, "דמי ניהול"), infl: num(form.inflationPct, "אינפלציה") };
  for (const v of Object.values(f)) if (typeof v === "string") return { ok: false, error: v };
  const n = f as Record<keyof typeof f, number>;
  if (!Number.isInteger(n.years)) return { ok: false, error: "מספר שנים: יש להזין מספר שלם" };
  const deposits: Record<string, number> = {};
  for (const [id, text] of Object.entries(form.deposits)) {
    if (text.trim() === "") continue;
    const v = Number(text);
    if (!Number.isFinite(v) || v < 0) return { ok: false, error: "הפקדה חודשית: יש להזין מספר שאינו שלילי" };
    if (v > 0) deposits[id] = v;
  }
  return { ok: true, params: { years: n.years, annual_return_pct: n.ret, annual_fee_pct: n.fee, inflation_pct: n.infl, monthly_contributions: deposits } };
}

export interface ForecastModel {
  total: SavingsRow[]; head: string[]; rows: { id: string; cells: string[]; feeHint: string }[]; chart: ReturnType<typeof lineChartModel> | null; notes: string[];
}
/** What the server reports as missing per account, in the owner's words (a missing input is shown, never filled in). */
const MISSING_LABELS: Record<string, string> = {
  management_fee: "דמי ניהול מהצבירה", deposit_fee: "דמי ניהול מההפקדה", expected_return: "תשואה צפויה", monthly_deposit: "הפקדה חודשית מתוכננת",
  investment_track: "מסלול השקעה", linkage: "הצמדה", insurance_cost: "עלות ביטוח חודשית", insurance_cost_date: "תאריך עלות הביטוח",
};
/** Wording + layout of the server's forecast: totals are the server's consolidated numbers; the chart only scales them. */
export function forecastModel(view: FccAccountsForecast): ForecastModel {
  const c = view.consolidated;
  const total: SavingsRow[] = c.final_nominal == null ? [] : [
    { key: "start", label: "שווי פתיחה מאוחד", value: money(c.start_value), hint: `${c.accounts} חשבונות · היתרות האחרונות שדווחו${view.all_self_reported ? ` · ${SELF_REPORTED}` : ""}` },
    { key: "final", label: `שווי מאוחד בעוד ${view.years} שנים`, value: money(c.final_nominal), hint: "נומינלי, אחרי דמי ניהול · הנחות בלבד" },
    { key: "real", label: "שווי מאוחד ריאלי", value: money(c.final_real), hint: `אחרי אינפלציה של ${view.assumptions.inflation_pct}% בשנה` },
    { key: "invested", label: "סך שהושקע", value: money(c.invested), hint: "כולל את יתרת הפתיחה וההפקדות שהוזנו" },
  ];
  const notes = [...view.warnings];
  if (view.excluded.without_snapshot > 0) notes.push(`${view.excluded.without_snapshot} חשבונות בלי יתרה שדווחה אינם בתחזית.`);
  if (view.excluded.closed > 0) notes.push(`${view.excluded.closed} חשבונות סגורים אינם בתחזית.`);
  for (const g of view.data_gaps ?? []) {
    notes.push(`חסר לדיוק — ${g.name || "חשבון ללא שם"}: ${g.missing.map((k) => MISSING_LABELS[k] ?? k).join(", ")}.`);
  }
  return {
    total, head: FORECAST_ACCOUNT_HEAD, notes,
    rows: view.accounts.map((a) => ({
      id: a.id, feeHint: a.fee_source === "account" ? "דמי הניהול של החשבון" : "ברירת המחדל מהקלט",
      cells: [a.name || "חשבון ללא שם", money(a.start_value), a.monthly_contribution ? money(a.monthly_contribution) : "—",
              `${a.fee_pct}%${a.fee_source === "default" ? " (ברירת מחדל)" : ""}`, money(a.final_nominal), money(a.final_real)],
    })),
    chart: view.accounts.length ? lineChartModel([
      { name: "מאוחד (נומינלי)", pts: c.series.map((r): [number, number] => [r.year, r.nominal]) },
      { name: "מאוחד (ריאלי)", pts: c.series.map((r): [number, number] => [r.year, r.real]), color: CHART_COLORS[2] },
      { name: "סך שהושקע", pts: c.series.map((r): [number, number] => [r.year, r.invested]), color: "#8892a0", dash: "4 3" },
    ]) : null,
  };
}

// ── Future lab form (strings while typing; converted once on submit) ──
export interface LabForm {
  initial: string; monthly: string; years: string; returnPct: string; feePct: string; inflationPct: string;
  timing: "begin" | "end"; indexed: boolean; baseline: string; strategies: string[];
  crisisOn: boolean; crisisDecline: string; crisisYear: string; crisisRecovery: "fast" | "prolonged";
}
export const STRATEGY_OPTIONS: { key: string; label: string }[] = [
  { key: "global", label: "100% קרן עולמית" }, { key: "world_em", label: "World + EM" },
  { key: "three_funds", label: "השילוש" }, { key: "experimental_90_10", label: "90/10" },
];
export const CRISIS_DECLINES = [10, 20, 30, 40, 50];
export const DEFAULT_LAB_FORM: LabForm = {
  initial: "0", monthly: "8000", years: "30", returnPct: "8", feePct: "0.15", inflationPct: "2",
  timing: "end", indexed: false, baseline: "global", strategies: STRATEGY_OPTIONS.map((s) => s.key),
  crisisOn: false, crisisDecline: "30", crisisYear: "5", crisisRecovery: "fast",
};

/** Typed text -> request body. Blank / non-numeric input is an error shown on the form, never silently 0. */
export function labParams(form: LabForm): { ok: true; params: PortfolioLabParams } | { ok: false; error: string } {
  const num = (text: string, name: string): number | string => {
    const v = text.trim() === "" ? NaN : Number(text);
    return Number.isFinite(v) ? v : `${name}: יש להזין מספר`;
  };
  const fields = {
    initial: num(form.initial, "סכום התחלתי"), monthly: num(form.monthly, "הפקדה חודשית"), years: num(form.years, "מספר שנים"),
    ret: num(form.returnPct, "תשואה"), fee: num(form.feePct, "דמי ניהול"), infl: num(form.inflationPct, "אינפלציה"),
  };
  for (const v of Object.values(fields)) if (typeof v === "string") return { ok: false, error: v };
  const f = fields as Record<keyof typeof fields, number>;
  if (!Number.isInteger(f.years)) return { ok: false, error: "מספר שנים: יש להזין מספר שלם" };
  const strategies = form.strategies.length ? form.strategies : [form.baseline];
  const params: PortfolioLabParams = {
    initial: f.initial, monthly_contribution: f.monthly, years: f.years, annual_return_pct: f.ret, annual_fee_pct: f.fee,
    inflation_pct: f.infl, deposit_timing: form.timing, index_contributions: form.indexed, baseline: form.baseline, strategies,
  };
  if (form.crisisOn) {
    const year = num(form.crisisYear, "שנת המשבר");
    if (typeof year === "string") return { ok: false, error: year };
    params.crisis = { decline_pct: Number(form.crisisDecline), year, recovery: form.crisisRecovery };
  }
  return { ok: true, params };
}

// ── KPI cards / table cells (labels + formatting only) ──
export const pct = (fraction: number | null | undefined, digits = 2): string =>
  fraction == null || !Number.isFinite(fraction) ? "—" : `${(fraction * 100).toFixed(digits)}%`;
export const ils = (value: number | null | undefined): string => (value == null || !Number.isFinite(value) ? "—" : money(value));

export function labKpiCards(view: PortfolioLabView): { key: string; label: string; value: string; hint?: string }[] {
  const k = view.kpis;
  return [
    { key: "final_nominal", label: "שווי סופי נומינלי", value: ils(k.final_nominal) },
    { key: "final_real", label: "שווי סופי ריאלי", value: ils(k.final_real) },
    { key: "contributions", label: "סך הפקדות", value: ils(k.contributions) },
    { key: "nominal_profit", label: "רווח נומינלי", value: ils(k.nominal_profit) },
    { key: "real_profit", label: "רווח ריאלי", value: ils(k.real_profit) },
    { key: "fees", label: "דמי ניהול ששולמו", value: ils(k.management_fees_paid) },
    { key: "cost_impact", label: "השפעה כוללת של העלויות", value: ils(k.total_cost_impact) },
    { key: "net_return", label: "תשואה שנתית אפקטיבית נטו", value: pct(k.net_effective_annual_return) },
    { key: "after_tax", label: "שווי אחרי מס", value: k.after_tax.display ?? ils(k.after_tax.value), hint: k.after_tax.note },
  ];
}

export function labTableRows(view: PortfolioLabView): { key: string; cells: string[]; baseline: boolean }[] {
  return view.comparison_table.map((r) => ({
    key: r.strategy, baseline: r.is_baseline,
    cells: [r.is_baseline ? `${r.label} (בסיס)` : r.label, ils(r.final_nominal), ils(r.final_real), ils(r.contributions), ils(r.net_profit), ils(r.costs),
            r.is_baseline ? "—" : `${r.gap_vs_baseline > 0 ? "+" : ""}${ils(r.gap_vs_baseline)}`],
  }));
}
export const LAB_TABLE_HEAD = ["אסטרטגיה", "שווי סופי", "שווי ריאלי", "סך הפקדות", "רווח נטו", "עלויות", "פער מול בסיס"];

// ── Chart geometry: pure scaling of numbers the server already produced (no financial calculation) ──
export const CHART = { w: 520, h: 280, l: 58, r: 12, t: 12, b: 34 } as const;
export const CHART_COLORS = ["#1f5fbf", "#d9822b", "#2a9d8f", "#9b59b6", "#c0392b"];

export const compact = (v: number): string =>
  Math.abs(v) >= 1e6 ? `${(v / 1e6).toFixed(1)}M` : Math.abs(v) >= 1e3 ? `${(v / 1e3).toFixed(0)}K` : String(Math.round(v));

interface Tick { pos: number; label: string }
export interface LineModel { name: string; color: string; dash?: string; points: string; dots: { x: number; y: number }[] }
export interface LineChartModel { yTicks: Tick[]; xTicks: Tick[]; lines: LineModel[] }

export function lineChartModel(lines: { name: string; pts: [number, number][]; color?: string; dash?: string }[]): LineChartModel {
  const iw = CHART.w - CHART.l - CHART.r, ih = CHART.h - CHART.t - CHART.b;
  const xs = lines.flatMap((l) => l.pts.map((p) => p[0])), ys = lines.flatMap((l) => l.pts.map((p) => p[1]));
  const xmin = Math.min(...xs), xmax = Math.max(...xs), ymax = (Math.max(...ys) || 1) * 1.05;
  const x = (v: number) => CHART.l + (iw * (v - xmin)) / (xmax - xmin || 1);
  const y = (v: number) => CHART.t + ih - (ih * v) / ymax;
  return {
    yTicks: [0, 1, 2, 3, 4].map((i) => ({ pos: y((ymax * i) / 4), label: compact((ymax * i) / 4) })),
    xTicks: [0, 1, 2, 3, 4].map((i) => ({ pos: CHART.l + (iw * i) / 4, label: String(Math.round(xmin + ((xmax - xmin) * i) / 4)) })),
    lines: lines.map((l, i) => ({
      name: l.name, color: l.color ?? CHART_COLORS[i % CHART_COLORS.length], dash: l.dash,
      points: l.pts.map((p) => `${x(p[0]).toFixed(1)},${y(p[1]).toFixed(1)}`).join(" "),
      dots: l.pts.length <= 12 ? l.pts.map((p) => ({ x: x(p[0]), y: y(p[1]) })) : [],
    })),
  };
}

export interface BarChartModel { yTicks: Tick[]; groups: { label: string; x: number; bars: { x: number; y: number; w: number; h: number; color: string }[] }[]; legend: { name: string; color: string }[] }
export function barChartModel(labels: string[], series: { name: string; values: number[]; color: string }[]): BarChartModel {
  const iw = CHART.w - CHART.l - CHART.r, ih = CHART.h - CHART.t - CHART.b;
  const ymax = (Math.max(...series.flatMap((s) => s.values)) || 1) * 1.05;
  const gw = iw / labels.length, bw = (gw * 0.7) / series.length;
  return {
    yTicks: [0, 1, 2, 3, 4].map((i) => ({ pos: CHART.t + ih - (ih * i) / 4, label: compact((ymax * i) / 4) })),
    groups: labels.map((label, i) => ({
      label, x: CHART.l + gw * (i + 0.5),
      bars: series.map((s, j) => { const h = (ih * s.values[i]) / ymax; return { x: CHART.l + gw * i + gw * 0.15 + bw * j, y: CHART.t + ih - h, w: bw, h, color: s.color }; }),
    })),
    legend: series.map((s) => ({ name: s.name, color: s.color })),
  };
}

export function breakdownParts(view: PortfolioLabView): { name: string; value: number; share: number; color: string }[] {
  const b = view.charts.breakdown;
  return [
    { name: "הפקדות", value: b.contributions, share: b.shares.contributions, color: CHART_COLORS[0] },
    { name: "רווח נטו", value: b.profit_net, share: b.shares.profit_net, color: CHART_COLORS[2] },
    { name: "עלויות", value: b.costs, share: b.shares.costs, color: CHART_COLORS[4] },
  ];
}

export function growthLines(view: PortfolioLabView) {
  const g = view.charts.growth;
  const lines: { name: string; pts: [number, number][]; color?: string; dash?: string }[] = [
    { name: "נומינלי", pts: g.series.map((r) => [r.year, r.nominal]) },
    { name: "ריאלי", pts: g.series.map((r) => [r.year, r.real]), color: CHART_COLORS[2] },
    { name: "הפקדות מצטברות", pts: g.series.map((r) => [r.year, r.contributions]), color: "#8892a0", dash: "4 3" },
  ];
  if (g.crisis.applied && g.crisis.series) lines.push({ name: "נומינלי עם משבר (תרחיש)", pts: g.crisis.series.map((r) => [r.year, r.nominal]), color: CHART_COLORS[4] });
  return lines;
}
export const comparisonLines = (view: PortfolioLabView) =>
  Object.entries(view.charts.strategy_comparison).map(([id, rows]) => ({ name: view.labels.strategies[id] ?? id, pts: rows.map((r): [number, number] => [r.year, r.nominal]) }));
