// Pure presentation of the FCC loans & debt area. Unknown stays unknown: a missing number renders
// "לא הוגדר" (never ₪0 / 0%), a derived cost is marked approximate while it rests on incomplete data,
// and nothing here recommends which loan to close — it only orders and lays out the facts.
import type { FccLoan, FccLoans } from "../types";
import { dmy, money } from "./fccPresentation";

export const UNKNOWN = "לא הוגדר";
export const UNCLASSIFIED = "לא סווג";

export const val = (n: number | null | undefined): string => (n == null ? UNKNOWN : money(n));
export const pct = (n: number | null | undefined): string => (n == null ? UNKNOWN : `${n.toFixed(2).replace(/\.?0+$/, "")}%`);
const months = (n: number | null | undefined): string => (n == null ? UNKNOWN : String(n));

export type LoanFilter = "all" | "private" | "business" | "mortgage";
export const FILTERS: { key: LoanFilter; label: string; type: FccLoan["loan_type"] }[] = [
  { key: "all", label: "הכל", type: null },
  { key: "private", label: "פרטיות", type: "פרטית" },
  { key: "business", label: "עסקיות", type: "עסקית" },
  { key: "mortgage", label: "משכנתאות", type: "משכנתא" },
];

export type RankMode = "high_interest" | "cash_freed" | "small_balance";
export const RANK_MODES: { key: RankMode; label: string }[] = [
  { key: "high_interest", label: "ריבית גבוהה קודם" },
  { key: "cash_freed", label: "פינוי תזרים קודם" },
  { key: "small_balance", label: "יתרה קטנה קודם" },
];

export interface LoanHeaderCard { key: string; label: string; value: string; hint?: string }

function coverageHint(known: number, total: number): string | undefined {
  return total > 0 && known < total ? `מבוסס על ${known} מתוך ${total} הלוואות` : undefined;
}

export function loanHeaderCards(loans: FccLoans): LoanHeaderCard[] {
  const s = loans.summary;
  const n = s.total_active_loans;
  return [
    { key: "balance", label: "יתרת חוב לסילוק", value: val(s.total_early_closure_balance), hint: coverageHint(s.coverage.early_closure_balance, n) },
    { key: "payments", label: "החזר חודשי כולל", value: val(s.total_monthly_payments), hint: coverageHint(s.coverage.monthly_payment, n) },
    { key: "rate", label: "ריבית ממוצעת", value: pct(s.weighted_average_interest_rate), hint: s.weighted_average_interest_rate == null ? undefined : `משוקללת לפי יתרה · ${coverageHint(s.coverage.interest_rate, n) ?? "כל ההלוואות"}` },
    { key: "freed", label: "תזרים חודשי שיכול להשתחרר", value: val(s.total_monthly_cash_freed_if_all_closed), hint: coverageHint(s.coverage.monthly_payment, n) ?? "אם כל ההלוואות ייסגרו" },
  ];
}

export function filterLoans(items: FccLoan[], filter: LoanFilter): FccLoan[] {
  const active = items.filter((i) => i.active);
  const type = FILTERS.find((f) => f.key === filter)?.type;
  return filter === "all" ? active : active.filter((i) => i.loan_type === type);   // unclassified loans appear under "הכל" only
}

export function sortLoans(items: FccLoan[], loans: FccLoans, mode: RankMode): FccLoan[] {
  const order = loans.rankings[mode];
  const pos = (id: string) => { const i = order.indexOf(id); return i < 0 ? order.length : i; };
  return [...items].sort((a, b) => pos(a.id) - pos(b.id));
}

export interface LoanRow { label: string; value: string }
export interface LoanCardModel {
  title: string;
  lender: string | null;
  typeLabel: string;
  assetLine: string | null;            // null = no linked asset -> no row at all
  rows: LoanRow[];
  freedLine: string;
  incomplete: boolean;
}

export function loanCardModel(l: FccLoan): LoanCardModel {
  return {
    title: l.name || UNKNOWN,
    lender: l.lender && l.lender !== l.name ? l.lender : null,
    typeLabel: l.loan_type ?? UNCLASSIFIED,
    assetLine: l.related_asset ? `נכס: ${l.related_asset_name || "נכס מקושר"}` : null,
    rows: [
      { label: "יתרת סילוק", value: val(l.early_closure_balance) },
      { label: "ריבית", value: pct(l.interest_rate) },
      { label: "החזר חודשי", value: val(l.monthly_payment) },
      { label: "תשלומים שנותרו", value: months(l.payments_remaining) },
      { label: "תאריך סיום", value: dmy(l.end_date) || UNKNOWN },
    ],
    freedLine: l.monthly_cash_freed_if_closed == null ? `החזר חודשי: ${UNKNOWN}` : `בסגירה משתחררים ${money(l.monthly_cash_freed_if_closed)} לחודש`,
    incomplete: l.missing.length > 0,
  };
}

/** Future cost is approximate unless every input (incl. a numeric early-repayment fee) is known. */
export function futureCostLabel(l: FccLoan): string {
  if (l.estimated_future_cost == null) return UNKNOWN;
  return l.future_cost_exact ? money(l.estimated_future_cost) : `≈ ${money(l.estimated_future_cost)} (משוער${l.early_repayment_fee ? ", עמלת פירעון לא מספרית" : ", עמלת פירעון לא ידועה"})`;
}

export function compareRows(a: FccLoan, b: FccLoan): { label: string; a: string; b: string }[] {
  return [
    { label: "יתרה", a: val(a.early_closure_balance), b: val(b.early_closure_balance) },
    { label: "ריבית", a: pct(a.interest_rate), b: pct(b.interest_rate) },
    { label: "החזר חודשי", a: val(a.monthly_payment), b: val(b.monthly_payment) },
    { label: "חודשים שנותרו", a: months(a.months_remaining), b: months(b.months_remaining) },
    { label: "תזרים שמתפנה", a: val(a.monthly_cash_freed_if_closed), b: val(b.monthly_cash_freed_if_closed) },
    { label: "עלות עתידית משוערת", a: futureCostLabel(a), b: futureCostLabel(b) },
  ];
}

export interface LoanGoalModel { lines: LoanRow[] }

export function loanGoalModel(loans: FccLoans): LoanGoalModel | null {
  const g = loans.goal;
  if (!g) return null;
  return { lines: [
    { label: "יעד סגירה", value: money(g.target) },
    { label: "נסגר עד כה", value: val(g.closed) },
    { label: "נשאר", value: val(g.remaining) },
    { label: "יתרות סילוק של הלוואות פעילות", value: val(g.active_closure_balance) },
  ] };
}
