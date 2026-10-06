// Pure presentation of Financial Control Center goals. The server decides each goal's family
// (`mode`) from existing data; this file only maps a family to the fields worth showing, so a
// project never renders ₪0 / "—" and a cumulative or monthly-level goal never shows a weekly pace
// it does not have. No fetching, no state.
import type { FccGoalRow, FccOverview } from "../types";

const nf = new Intl.NumberFormat("he-IL", { maximumFractionDigits: 0 });
export const money = (n: number | null | undefined): string => (n == null ? "—" : `₪${nf.format(n)}`);

export function dmy(iso: string | null | undefined): string {
  if (!iso || iso.length < 10) return "";
  const [y, m, d] = iso.slice(0, 10).split("-");
  return `${d}/${m}/${y}`;
}

export const CATEGORY_LABEL: Record<string, string> = {
  income: "הכנסה", savings: "חיסכון", debt: "חוב", debt_repaid: "חוב", emergency_fund: "קרן חירום",
  project: "פרויקט", business_project: "פרויקט עסקי", investment: "השקעות", other: "אחר",
};

export interface GoalMetric { label: string; value: string }

export interface GoalCardModel {
  kind: "numeric" | "project" | "needs_target";
  metrics: GoalMetric[];
  progressPct: number | null;      // null = no progress bar
  note?: string;                   // single explanatory line (needs_target)
  nextAction?: { title: string; due: string } | null;   // project only; null = explicitly missing
  targetDate?: string;             // project only
}

export function goalCardModel(g: FccGoalRow): GoalCardModel {
  if (g.mode === "project" || g.status === "project") {
    const na = g.next_action;
    return {
      kind: "project", metrics: [], progressPct: null,
      nextAction: na?.title ? { title: na.title, due: dmy(na.due_date) } : null,
      targetDate: dmy(g.end_date) || undefined,
    };
  }
  if (g.status === "missing_target" || g.target == null) {
    return { kind: "needs_target", metrics: [], progressPct: null, note: "הגדר סכום יעד כדי להתחיל לעקוב" };
  }
  const pct = g.target > 0 ? Math.min(100, Math.round(((g.actual ?? 0) / g.target) * 100)) : 0;
  if (g.mode === "monthly_level") {
    return { kind: "numeric", progressPct: pct, metrics: [
      { label: "יעד הפחתה לחודש", value: money(g.target) },
      { label: "הושג", value: money(g.actual) },
      { label: "נשאר ליעד", value: money(g.remaining) },
    ] };
  }
  if (g.mode === "cumulative") {
    const metrics: GoalMetric[] = [
      { label: "יעד כולל", value: money(g.target) },
      { label: "בפועל", value: money(g.actual) },
      { label: "נשאר", value: money(g.remaining) },
      { label: "הושלם", value: `${pct}%` },
    ];
    if (g.dynamic_target_per_week != null && g.end_date) {
      metrics.push({ label: `קצב לשבוע עד ${dmy(g.end_date)}`, value: money(g.dynamic_target_per_week) });
    }
    return { kind: "numeric", progressPct: pct, metrics };
  }
  return { kind: "numeric", progressPct: pct, metrics: [
    { label: "יעד", value: money(g.target) },
    { label: "בפועל", value: money(g.actual) },
    { label: "נשאר", value: money(g.remaining) },
    { label: "יעד דינמי לשבוע", value: money(g.dynamic_target_per_week) },
  ] };
}

export interface HeaderCardModel { key: string; label: string; value: string; hint?: string }

export function headerCards(data: Pick<FccOverview, "summary" | "monthly_cash_improvement">): HeaderCardModel[] {
  const s = data.summary;
  const ratio = (card: { actual: number; target: number } | undefined, hint = "לא הוגדר יעד") =>
    card ? { value: `${money(card.actual)} / ${money(card.target)}`, hint: undefined as string | undefined }
         : { value: "—", hint };
  const income = ratio(s.income);
  const savings = ratio(s.savings);
  const emergency = ratio(s.emergency_fund);
  const debt = ratio(s.debt_repaid);
  const reduction = ratio(s.payment_reduction);
  return [
    { key: "income", label: "הכנסה מול יעד", ...income },
    { key: "income_week", label: "יעד הכנסה לשבוע",
      value: s.income ? money(s.income.dynamic_target_per_week) : "—", hint: s.income ? undefined : "לא הוגדר יעד" },
    { key: "savings", label: "חיסכון", ...savings },
    { key: "emergency", label: "קרן חירום", ...emergency,
      hint: s.emergency_fund ? "כיסוי חודשים: אין נתוני הוצאה" : emergency.hint },
    { key: "debt", label: "חוב שנפרע", ...debt },
    { key: "reduction", label: "הפחתה בהחזרים (לחודש)", ...reduction },
    { key: "cash", label: "שיפור תזרים חודשי", value: money(data.monthly_cash_improvement) },
  ];
}
