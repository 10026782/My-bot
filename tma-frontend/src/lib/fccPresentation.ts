// Pure presentation of Financial Control Center goals. The server decides each goal's family
// (`mode`) from existing data; this file only maps a family to the fields worth showing, so a
// project never renders ₪0 / "—" and a cumulative or monthly-level goal never shows a weekly pace
// it does not have. No fetching, no state.
import type { FccGoalRow, FccOverview, FccSavingsRelease, FccSummaryCard } from "../types";

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

/** Plan vs actual for the standing-order savings card; a missed month is a visible gap, not an automatic catch-up. */
function savingsHint(card: { deposited_month?: number; gap_month?: number; gap_last_month?: number }): string {
  const parts = ["הוראת קבע מול יעד · לא מתאפס"];
  if (card.deposited_month != null) parts.push(`הופקד החודש ${money(card.deposited_month)}${card.gap_month ? ` · פער ${money(card.gap_month)}` : ""}`);
  if (card.gap_last_month) parts.push(`פער בחודש שעבר ${money(card.gap_last_month)} — אפשר לכתוב ״משימת המשך לפער בחיסכון״`);
  return parts.join(" · ");
}

function isSavings(category: unknown): boolean {
  const c = String(typeof category === "object" && category ? (category as { name?: string }).name : category ?? "").trim().toLowerCase();
  return c === "savings" || c === "חיסכון";
}

export interface GoalMetric { label: string; value: string }

export interface GoalCardModel {
  kind: "numeric" | "project" | "needs_target";
  metrics: GoalMetric[];
  progressPct: number | null;      // null = no progress bar
  note?: string;                   // single explanatory line (needs_target)
  sourceNote?: string;             // source/sub-goal: its target is part of the parent, not on top of it
  nextAction?: { title: string; due: string } | null;   // project only; null = explicitly missing
  targetDate?: string;             // project only
}

/** Label in the "which goal?" picker: the title plus its current target, so two similar goals are told apart. */
export function goalPickLabel(g: Pick<FccGoalRow, "title" | "target">): string {
  const title = g.title ?? "";
  return g.target != null ? `${title} · ${money(g.target)}` : title;
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
  const pct = g.target > 0 ? Math.min(100, Math.round((((g.direct_costs ? g.net : g.actual) ?? 0) / g.target) * 100)) : 0;
  if (g.mode === "monthly_level" && isSavings(g.category)) {      // standing monthly allocation: a level vs target, never resets
    return { kind: "numeric", progressPct: pct, note: "הוראת קבע חודשית — לא מתאפסת בסוף החודש", metrics: [
      { label: "יעד הפרשה חודשית", value: money(g.target) },
      { label: "מופרש כרגע לחודש", value: money(g.actual) },
      { label: "חסר ליעד", value: money(g.remaining) },
      ...(g.deposited_month != null ? [{ label: "הופקד בפועל החודש", value: money(g.deposited_month) }] : []),
      ...(g.gap_month ? [{ label: "פער החודש", value: money(g.gap_month) }] : []),
      ...(g.gap_last_month ? [{ label: "פער בחודש שעבר", value: money(g.gap_last_month) }] : []),
    ] };
  }
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
  const sourceNote = g.is_source ? "מקור שתורם ליעד הכולל — לא מתווסף אליו" : undefined;
  return { kind: "numeric", progressPct: pct, sourceNote, metrics: [
    { label: "יעד", value: money(g.target) },
    { label: "בפועל", value: money(g.actual) },
    { label: "נשאר", value: money(g.remaining) },
    ...(g.is_source && g.period_type === "weekly" ? [] : [{ label: "יעד דינמי לשבוע", value: money(g.dynamic_target_per_week) }]),
    ...costMetrics(g),
  ] };
}

/** Gross -> direct costs -> net, only when the goal actually has direct costs. */
function costMetrics(g: { actual?: number | null; direct_costs?: number | null; net?: number | null }): GoalMetric[] {
  if (!g.direct_costs) return [];
  return [
    { label: "ברוטו", value: money(g.actual) },
    { label: "הוצאות ישירות", value: `-${money(g.direct_costs)}` },
    { label: "נטו", value: money(g.net) },
  ];
}

export function netBreakdown(card: FccSummaryCard | undefined): string | undefined {
  if (!card?.direct_costs) return undefined;
  return `ברוטו ${money(card.actual)} · הוצאות ישירות -${money(card.direct_costs)} · נטו ${money(card.net)}`;
}

/** The weekly card's headline is the PACE still needed from now to reach the monthly goal. A weekly source (e.g. travel)
 *  is a part INSIDE that pace, never on top of it:
 *   - a source that still owes shows what is left, and "other sources" is the rest, so the parts add up to the headline;
 *   - once every weekly source has reached its minimum there is nothing to add up: each is shown as achieved and
 *     "other sources" is left out (it would just repeat the headline and read like 2,500 + 2,681). */
export function weeklyBreakdown(card: FccSummaryCard | undefined): string | undefined {
  if (!card?.sources?.length || card.other_sources_needed == null) return undefined;
  const weekly = card.sources.filter((s) => s.period_type === "weekly");
  const met = (s: (typeof weekly)[number]) => s.remaining != null && s.remaining <= 0;
  const line = (s: (typeof weekly)[number]) => met(s)
    ? `${s.title ?? "מקור"} השבוע: היעד ${money(s.target)} הושג ✅`
    : `${s.title ?? "מקור"}: נשאר ${money(s.remaining)} מתוך ${money(s.target)} השבוע`
      + (s.direct_costs ? ` (הוצאות ישירות -${money(s.direct_costs)} · נטו ${money(s.net)})` : "");
  const parts = weekly.map(line);
  if (weekly.some((s) => !met(s))) {
    parts.push(`ממקורות אחרים: ${money(card.other_sources_needed)}`);
    return `מזה: ${parts.join(" · ")}`;
  }
  return parts.length ? parts.join(" · ") : undefined;
}

export interface HeaderCardModel { key: string; label: string; value: string; hint?: string }

export function headerCards(data: Pick<FccOverview, "summary" | "monthly_cash_improvement"> & Partial<Pick<FccOverview, "household" | "receipts" | "obligations">>): HeaderCardModel[] {
  const s = data.summary;
  const ratio = (card: { actual: number; target: number } | undefined, hint = "לא הוגדר יעד") =>
    card ? { value: `${money(card.actual)} / ${money(card.target)}`, hint: undefined as string | undefined }
         : { value: "—", hint };
  // progress is NET when there are direct costs (profit, not turnover); gross/costs are in the hint
  const income = s.income?.direct_costs ? ratio({ actual: s.income.net ?? 0, target: s.income.target }) : ratio(s.income);
  const savings = ratio(s.savings);
  const emergency = ratio(s.emergency_fund);
  const debt = ratio(s.debt_repaid);
  const reduction = ratio(s.payment_reduction);
  return [
    { key: "income", label: "הכנסה מול יעד", ...income, hint: netBreakdown(s.income) },
    { key: "income_week", label: "קצב נדרש לשבוע (מעכשיו)",
      value: s.income ? money(s.income.dynamic_target_per_week) : "—",
      hint: s.income ? weeklyBreakdown(s.income) : "לא הוגדר יעד" },
    { key: "savings", label: s.savings?.mode === "monthly_level" ? "הפרשה חודשית לחיסכון" : "חיסכון", ...savings,
      ...(s.savings?.mode === "monthly_level" ? { hint: savingsHint(s.savings) } : {}) },
    { key: "emergency", label: "קרן חירום", ...emergency,
      hint: s.emergency_fund ? "כיסוי חודשים: אין נתוני הוצאה" : emergency.hint },
    { key: "debt", label: "חוב שנפרע", ...debt },
    { key: "reduction", label: "הפחתה בהחזרים (לחודש)", ...reduction },
    { key: "cash", label: "שיפור תזרים חודשי", value: money(data.monthly_cash_improvement) },
    // separate from income/net: private household spend this month, and business receipts still missing
    ...(data.household?.month_total ? [{ key: "household", label: "הוצאות בית החודש", value: money(data.household.month_total) }] : []),
    // recurring commitments (not actual spend): total per month, how many are marked reduce/cancel/negotiate, potential saving
    ...(data.obligations?.count ? [
      { key: "obligations", label: "התחייבויות חודשיות", value: money(data.obligations.total_monthly),
        hint: `${data.obligations.count} התחייבויות פעילות` },
      { key: "obligations_flagged", label: "לצמצום / ביטול", value: String(data.obligations.flagged_count),
        hint: data.obligations.flagged_count
          ? `${money(data.obligations.flagged_monthly)} בחודש${data.obligations.cancel_pending ? ` · ${data.obligations.cancel_pending} ממתינות לביטול בפועל` : ""}`
          : undefined },
      { key: "obligations_saving", label: "חיסכון חודשי פוטנציאלי", value: money(data.obligations.potential_saving),
        hint: "רק אחרי ביטול בפועל" },
    ] : []),
    ...(data.receipts?.missing_count ? [{ key: "receipts", label: "אסמכתאות חסרות", value: String(data.receipts.missing_count),
      hint: `סה״כ ${money(data.receipts.missing_amount)} בהוצאות עסק` }] : []),
  ];
}


// ── Savings release: "מתפנה לחיסכון" (all numbers come from the server; this only words them) ──
export interface SavingsReleaseModel {
  headline: string;
  lines: string[];
  depositLabel: string;
  closing: string | null;        // month-end question text (last days of the month)
  gapLine: string | null;
  canExplainGap: boolean;
  destination: string;
}

export function savingsReleaseModel(r: FccSavingsRelease): SavingsReleaseModel {
  const lines = [`הכנסה נטו ${money(r.income_net)} מתוך ${money(r.income_target)}`];
  lines.push(r.shortfall > 0
    ? `חסרים ${money(r.shortfall)} ליעד — מהכנסות נוף הגליל נשארים ${money(r.from_fixed)} מתוך ${money(r.fixed_level)}`
    : `יעד ההכנסה הושג — מתפנים ${money(r.fixed_level)} מנוף הגליל${r.extra > 0 ? ` ועוד ${money(r.extra)} מעל היעד` : ""}`);
  lines.push(`הופקדו החודש ${money(r.deposited)} · נשארו להפקדה ${money(r.remaining)}`);
  return {
    headline: money(r.available),
    lines,
    depositLabel: r.remaining > 0 ? `הפקד ${money(r.remaining)}` : "רשום הפקדה",
    closing: r.closing ? `סוף החודש — סך הפקדות החודש: ${money(r.deposited)}. נכון?` : null,
    gapLine: r.closing && r.gap > 0 ? `פער ${money(r.gap)} מול חודש מלא` : null,
    canExplainGap: r.closing && r.gap > 0,
    destination: r.destination?.title ? `יעד ההפקדה: ${r.destination.title}` : "יעד ההפקדה ייבחר בעת ההפקדה",
  };
}

/** The question asked right after an income was booked. Null = nothing is free (no question). */
export function savingsFollowUp(r: FccSavingsRelease | null | undefined): { message: string; confirm: string } | null {
  if (!r || r.remaining <= 0) return null;
  return { message: `מתפנים לחיסכון ${money(r.remaining)} החודש. להפקיד?`, confirm: `הפקד ${money(r.remaining)}` };
}
