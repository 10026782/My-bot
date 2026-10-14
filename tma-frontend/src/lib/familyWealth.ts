// "תכנון חיסכון לטווח ארוך" (family wealth) — presentation only. No fetching, no storage, no financial arithmetic:
// every number shown comes from the server (FCC overview / portfolio_lab view); this only words and lays them out.
import type { FccOverview, PortfolioLabParams, PortfolioLabView } from "../types";
import { money } from "./fccPresentation";

export const SCREEN_TITLE = "תכנון חיסכון לטווח ארוך";   // owner's choice (14/10/2026); one constant so the name can change in one place

export type FamilyTabKey = "savings" | "lab";
export const FAMILY_TABS: { key: FamilyTabKey; label: string }[] = [
  { key: "savings", label: "החיסכון שלי" },
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
export function savingsTabModel(data: Pick<FccOverview, "summary" | "savings_release">): SavingsTabModel {
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
  rows.push({ key: "balance", label: "יתרת תיק", value: "לא זמינה", hint: BALANCE_PLACEHOLDER });
  return {
    rows,
    notes: ["סיכומי שנה, ממוצע חודשי ורצף חודשים יתווספו בשלב הבא.", "אין כאן הבטחת תשואה — המספרים הם דיווח והנחות בלבד."],
    hasData: Boolean(plan || release),
  };
}

/** Entry card on the monthly FCC tab: one short line, only from what the overview already has. */
export function familyCardModel(data: Pick<FccOverview, "summary" | "savings_release">): { title: string; value: string; hint: string } {
  const release = data.savings_release ?? null;
  return {
    title: SCREEN_TITLE,
    value: release ? `הופקד החודש ${money(release.deposited)}` : "אין עדיין נתון לחודש",
    hint: release ? SELF_REPORTED : "פתחו את המסך לתכנון ולמעבדת העתיד",
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
