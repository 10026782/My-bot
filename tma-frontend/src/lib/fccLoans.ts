// Pure presentation of the FCC loans & debt area. Unknown stays unknown: a missing number renders
// "לא הוגדר" (never ₪0 / 0%), a derived cost is marked approximate while it rests on incomplete data,
// and nothing here recommends which loan to close — it only orders and lays out the facts.
import type { FccAssetAction, FccLoan, FccLoans } from "../types";
import { dmy, money } from "./fccPresentation";

export interface ActionRow {
  id: string;
  title: string;
  statusLabel: string;              // "ממתין" | "בתהליך"
  inProgress: boolean;              // true -> no "start" button
  meta: string;                     // "אחראי: אורי · עד 20/10/2026"
  history: string[];                // lines already recorded (started / …)
}

const ymd = (iso: string | null) => (iso && iso.length >= 10 ? `${iso.slice(8, 10)}/${iso.slice(5, 7)}/${iso.slice(0, 4)}` : "");

export function actionRows(i: { actions?: FccAssetAction[] }): ActionRow[] {
  return (i.actions ?? []).map((a) => ({
    id: a.id,
    title: a.title || UNKNOWN,
    statusLabel: a.status === "בביצוע" ? "בתהליך" : "ממתין",
    inProgress: a.status === "בביצוע",
    meta: [a.owner && a.owner !== "—" ? `אחראי: ${a.owner}` : "", a.due_date ? `עד ${ymd(a.due_date)}` : ""].filter(Boolean).join(" · "),
    history: a.history ? a.history.split("\n").filter(Boolean) : [],
  }));
}

export const UNKNOWN = "לא הוגדר";
export const UNCLASSIFIED = "לא סווג";
export const STATUS_UNKNOWN = "סטטוס לא הוגדר";

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
    { key: "rate", label: "ריבית ממוצעת", value: pct(s.weighted_average_interest_rate),
      hint: s.weighted_average_interest_rate == null ? undefined : ["משוקללת לפי יתרת סילוק", coverageHint(s.coverage.interest_rate, n)].filter(Boolean).join(" · ") },
    { key: "freed", label: "תזרים חודשי שיכול להשתחרר", value: val(s.total_monthly_cash_freed_if_all_closed), hint: coverageHint(s.coverage.monthly_payment, n) ?? "אם כל ההלוואות ייסגרו" },
  ];
}

export const owedToMe = (l: { direction?: string }): boolean => l.direction === "owed_to_me";

export function filterLoans(items: FccLoan[], filter: LoanFilter): FccLoan[] {
  const active = items.filter((i) => i.active && !owedToMe(i));       // a debt owed TO the owner is never listed among his loans
  const type = FILTERS.find((f) => f.key === filter)?.type;
  return filter === "all" ? active : active.filter((i) => i.loan_type === type);   // unclassified loans appear under "הכל" only
}

export function sortLoans(items: FccLoan[], loans: FccLoans, mode: RankMode): FccLoan[] {
  const order = loans.rankings[mode];
  const pos = (id: string) => { const i = order.indexOf(id); return i < 0 ? order.length : i; };
  return [...items].sort((a, b) => pos(a.id) - pos(b.id));
}

export interface LoanRow { label: string; value: string }
export interface LoanTag { text: string; tone: "plain" | "muted" }
export interface LoanCardModel {
  title: string;
  lender: string | null;
  typeLabel: string;
  tags: LoanTag[];                     // small, low-contrast chips: type (only if unclassified) / status / partial data
  assetLine: string | null;            // null = no linked asset -> no row at all
  keyRows: LoanRow[];                  // the three headline figures: closure balance, monthly payment, rate
  metaRows: LoanRow[];                 // payments remaining, end date
  rows: LoanRow[];                     // keyRows + metaRows
  freedLine: string;
  freedKnown: boolean;                 // true -> emphasised line; false -> plain "unknown" line
  incomplete: boolean;
  statusUnknown: boolean;
}

/** "Partial data" only when a headline figure is really missing (months remaining alone is not enough). */
export function isPartial(l: FccLoan): boolean {
  return l.missing.some((m) => m !== "months_remaining");
}

export function loanCardModel(l: FccLoan): LoanCardModel {
  const keyRows: LoanRow[] = [
    { label: "יתרת סילוק", value: val(l.early_closure_balance) },
    { label: "החזר חודשי", value: val(l.monthly_payment) },
    { label: "ריבית", value: pct(l.interest_rate) },
  ];
  const metaRows: LoanRow[] = [
    { label: "תשלומים שנותרו", value: months(l.payments_remaining) },
    { label: "תאריך סיום", value: dmy(l.end_date) || UNKNOWN },
  ];
  const typeLabel = l.loan_type ?? UNCLASSIFIED;
  const tags: LoanTag[] = [{ text: typeLabel, tone: l.loan_type ? "plain" : "muted" }];
  if (l.status_unknown) tags.push({ text: STATUS_UNKNOWN, tone: "muted" });
  if (isPartial(l)) tags.push({ text: "נתונים חלקיים", tone: "muted" });
  const freed = l.monthly_cash_freed_if_closed;
  return {
    title: l.name || UNKNOWN,
    lender: l.lender && l.lender !== l.name ? l.lender : null,
    typeLabel,
    tags,
    assetLine: l.related_asset ? `נכס: ${l.related_asset_name || "נכס מקושר"}` : null,
    keyRows, metaRows, rows: [...keyRows, ...metaRows],
    freedLine: freed == null ? `החזר חודשי: ${UNKNOWN}` : `בסגירה משתחררים ${money(freed)} לחודש`,
    freedKnown: freed != null,
    incomplete: isPartial(l),
    statusUnknown: l.status_unknown,
  };
}

/** Compare selection: at most two loans; a third pick replaces the oldest. */
export function togglePick(picked: string[], id: string): string[] {
  if (picked.includes(id)) return picked.filter((x) => x !== id);
  return picked.length >= 2 ? [picked[1], id] : [...picked, id];
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

export interface LoanGoalModel { lines: LoanRow[]; pct: number | null; pctLabel: string }

export function loanGoalModel(loans: FccLoans): LoanGoalModel | null {
  const g = loans.goal;
  if (!g) return null;
  const pct = g.closed != null && g.target > 0 ? Math.max(0, Math.min(100, Math.round((g.closed / g.target) * 100))) : null;
  return {
    pct,
    pctLabel: pct == null ? UNKNOWN : `${pct}%`,
    lines: [
      { label: "יעד", value: money(g.target) },
      { label: "נסגר עד כה", value: val(g.closed) },
      { label: "נשאר", value: val(g.remaining) },
      { label: "יתרות סילוק פעילות", value: val(g.active_closure_balance) },
    ],
  };
}

// ── "Close a loan" flow ───────────────────────────────────────────────────────────────────────────────────────
// The SERVER owns the draft (shared FCC slot) and the only write path; the client renders each turn and sends the
// owner's next word (אשר / ערוך / בטל / an answer).

export const CLOSE_BUTTON = "סגרתי את ההלוואה";
export const PARTIAL_BUTTON = "פרעון חלקי";
export const ARRANGEMENT_BUTTON = "הסדר פירעון";
export const NEXT_ACTION_BUTTON = "פעולה הבאה";
export const RECEIVED_BUTTON = "נפרע במלואו";

/** Debts owed TO the owner: active ones, largest first (unknown balance last). */
export function receivableItems(loans: FccLoans): FccLoan[] {
  return loans.items.filter((i) => i.active && owedToMe(i))
    .sort((a, b) => (b.early_closure_balance ?? -1) - (a.early_closure_balance ?? -1) || (a.name ?? "").localeCompare(b.name ?? ""));
}

export const NO_ARRANGEMENT = "לא הוגדר הסדר פירעון";

export interface BalanceCardModel {
  lines: LoanRow[];
  verdict: string;                     // what the net is: a financial asset, or NOT an asset
  positive: boolean;
  notes: string[];                     // what was left out / unknown — never hidden
}

/** "Owed to me" vs "I owe": shown only when something is owed to the owner. A negative net is not an asset (but it still counts in the personal equity). */
export function balanceCardModel(loans: FccLoans): BalanceCardModel | null {
  const b = loans.balance;
  if (!b || b.receivables_count === 0) return null;
  const net = b.net;
  const notes: string[] = [];
  if (b.linked_excluded_count > 0) notes.push(`${b.linked_excluded_count} הלוואות מקושרות לנכס (${money(b.linked_excluded_total)}) לא נכללות — החוב שלהן כבר בהון הנכס.`);
  if (b.missing_liabilities > 0 || b.missing_receivables > 0) notes.push(`${b.missing_liabilities + b.missing_receivables} חובות בלי יתרה לא נכללים בחישוב.`);
  return {
    lines: [
      { label: "חייבים לי", value: money(b.receivables_total) },
      { label: "החובות שלי (בלי מקושרות לנכס)", value: money(b.liabilities_total) },
      { label: "יתרה נטו", value: net == null ? UNKNOWN : money(net) },
    ],
    verdict: net == null ? UNKNOWN : net > 0 ? `נכס פיננסי נטו: ${money(net)} — נרשם בנכסים` : net < 0 ? `היתרה שלילית (${money(net)}) — אינה נכס, אך נכנסת להון האישי` : "המאזן מתאזן — אין נכס נטו",
    positive: net != null && net > 0,
    notes,
  };
}

export interface ReceivableCardModel { id: string; title: string; balance: string; arrangement: string; arrangementKnown: boolean; actions: ActionRow[] }

export function receivableCardModel(l: FccLoan): ReceivableCardModel {
  const arrangement = l.arrangement === "monthly" ? `פירעון חודשי ${val(l.monthly_payment)}${l.end_date ? ` · עד ${dmy(l.end_date)}` : ""}`
    : l.arrangement === "deadline" ? `מועד פירעון ${dmy(l.end_date) || UNKNOWN}` : NO_ARRANGEMENT;
  return { id: l.id, title: l.name || UNKNOWN, balance: val(l.early_closure_balance), arrangement, arrangementKnown: !!l.arrangement,
           actions: actionRows(l) };
}

export function receivablesSummary(loans: FccLoans): string | null {
  const r = loans.receivables;
  if (!r || r.count === 0) return null;
  const missing = r.no_arrangement > 0 ? ` · ${r.no_arrangement} בלי הסדר פירעון` : "";
  return `חייבים לי: ${val(r.total_balance)} (${r.count} חובות)${missing}`;
}
export const BALANCE_BUTTON = "עדכון יתרה";
export const PAYMENT_BUTTON = "שינוי החזר";

/** Only an active loan can be closed; the flows themselves (``loan.close`` / ``loan.update_balance`` / ``loan.update_payment``) run in the shared contextual writer. */
export const canClose = (loan: { active: boolean }): boolean => loan.active;
