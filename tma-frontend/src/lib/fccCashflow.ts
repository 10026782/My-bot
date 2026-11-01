// Monthly cashflow — presentation only. No fetching, no storage, no financial arithmetic: every number is the server's
// (/api/fcc/cashflow); this only words them. A missing value is "חסר" (never 0). The only computation is a bar width (share of the month's total).
import type { FccCashflow, FccCashflowMonth, FccCashflowRec } from "../types";
import { money } from "./fccPresentation";

export const MISSING = "חסר";
export const RANGES = [3, 6, 12] as const;
export const DEFAULT_RANGE = 6;
export const CASHFLOW_NOTES = [
  "הוצאה = מה שנרשם בפועל. התחייבויות קבועות לא נוספות לסכום (החיוב עצמו כבר נרשם כהוצאה) והן משמשות להמלצות בלבד.",
  "הלוואות הן הוצאה: חיוב שנרשם גובר; כשאין חיוב רשום, ההחזר החודשי המתוכנן נכנס לחודש הנוכחי בלבד (מסומן כהערכה).",
  "חודש בלי הכנסות או בלי הוצאות רשומות מוצג כ״חסר״ ולא נכנס להשוואות.",
];
const HEB_MONTHS = ["ינואר", "פברואר", "מרץ", "אפריל", "מאי", "יוני", "יולי", "אוגוסט", "ספטמבר", "אוקטובר", "נובמבר", "דצמבר"];

export function monthLabel(key: string): string {
  const [y, m] = key.split("-");
  const name = HEB_MONTHS[Number(m) - 1];
  return name ? `${name} ${y}` : key;
}
const val = (n: number | null | undefined): string => (n == null ? MISSING : money(n));
const signed = (n: number): string => (n > 0 ? `+${money(n)}` : n < 0 ? `-${money(Math.abs(n))}` : money(0));

export interface CashflowRow { month: string; label: string; income: string; expenses: string; balance: string; tone: "ok" | "bad" | "missing"; tag: string | null }
export interface CashflowDetail {
  month: string; label: string; partialNote: string | null;
  kpis: { key: string; label: string; value: string; hint?: string }[];
  sources: { key: string; name: string; value: string; hint: string }[];
  categories: { key: string; label: string; value: string; pct: number; custom: boolean; estimate: boolean }[];
  missingNote: string | null;
}
export interface CashflowModel { rows: CashflowRow[]; selected: string; detail: CashflowDetail | null; insights: string[]; notes: string[] }

export function rowOf(m: FccCashflowMonth): CashflowRow {
  return {
    month: m.month, label: monthLabel(m.month), income: val(m.income.net), expenses: val(m.expenses.total), balance: val(m.balance),
    tone: m.balance == null ? "missing" : m.balance < 0 ? "bad" : "ok",
    tag: m.partial ? `עד ה-${m.day} בחודש` : null,
  };
}

/** The month shown in detail by default: the latest month with a known balance, else the latest month. */
export function defaultMonth(v: Pick<FccCashflow, "months">): string {
  const done = [...v.months].reverse().find((m) => m.balance != null && !m.partial);
  return (done ?? v.months[v.months.length - 1])?.month ?? "";
}

export function detailOf(m: FccCashflowMonth): CashflowDetail {
  const total = m.expenses.total ?? 0;
  const gap = m.balance != null && m.balance < 0;
  return {
    month: m.month, label: monthLabel(m.month),
    partialNote: m.partial ? `החודש עדיין לא הסתיים — הנתונים עד ה-${m.day} בחודש (מתוך ${m.days_in_month}).` : null,
    kpis: [
      { key: "income", label: "הכנסות נטו", value: val(m.income.net), hint: m.income.known && m.income.direct_costs ? `ברוטו ${money(m.income.gross)} · עלויות ישירות ${money(m.income.direct_costs)}` : undefined },
      { key: "expenses", label: "הוצאות", value: val(m.expenses.total) },
      { key: "balance", label: gap ? "חסר" : "יתרה", value: m.balance == null ? MISSING : money(gap ? (m.shortfall ?? 0) : (m.surplus ?? 0)),
        hint: m.balance == null ? `חסר: ${m.missing.map((x) => (x === "income" ? "הכנסות" : "הוצאות")).join(", ")}` : gap ? "הוצאות גבוהות מההכנסות" : "הכנסות גבוהות מההוצאות" },
    ],
    sources: m.income.sources.map((s) => ({
      key: s.name, name: s.name, value: money(s.net),
      hint: [s.basis === "standing" ? "סכום קבוע" : null, s.direct_costs ? `ברוטו ${money(s.gross)} · עלויות ישירות ${money(s.direct_costs)}` : null].filter(Boolean).join(" · "),
    })),
    categories: m.expenses.categories.map((c) => ({
      key: c.key, label: c.label, value: money(c.amount), custom: !!c.custom, estimate: c.basis === "scheduled",
      pct: total > 0 && c.amount > 0 ? Math.min(100, Math.round((c.amount / total) * 100)) : 0,
    })),
    missingNote: m.missing.length ? `ל${monthLabel(m.month)} חסרות ${m.missing.map((x) => (x === "income" ? "הכנסות" : "הוצאות")).join(" ו")} — אין יתרה.` : null,
  };
}

export function insightLines(v: FccCashflow): string[] {
  const out: string[] = [];
  const ch = v.insights.changes;
  if (ch) {
    out.push(`שינוי ${monthLabel(ch.from)} ← ${monthLabel(ch.to)}: סך הוצאות ${signed(ch.total_delta)} (${money(ch.total_before)} ← ${money(ch.total_after)})`);
    for (const i of ch.items.slice(0, 5)) out.push(`${i.label}: ${signed(i.delta)}${i.pct != null ? ` (${i.pct > 0 ? "+" : ""}${Math.round(i.pct)}%)` : ""}`);
  }
  for (const s of v.insights.spikes) out.push(`חריגה ב${s.label} (${monthLabel(s.month)}${s.partial ? ", עד היום" : ""}): ${money(s.amount)} מול רגיל ${money(s.baseline)} (+${money(s.excess)})`);
  for (const l of v.insights.large_items) out.push(`סעיף גבוה: ${l.label || l.category} — ${money(l.amount)} (${l.category}, ${l.date})`);
  return out;
}

export function cashflowModel(v: FccCashflow, selected?: string): CashflowModel {
  const sel = selected && v.months.some((m) => m.month === selected) ? selected : defaultMonth(v);
  const month = v.months.find((m) => m.month === sel);
  const notes = [...CASHFLOW_NOTES];
  if (!v.loans_payments_known) notes.push("לא נמצא החזר הלוואות מתוכנן — הלוואות נספרות רק לפי חיוב שנרשם.");
  return { rows: [...v.months].reverse().map(rowOf), selected: sel, detail: month ? detailOf(month) : null, insights: insightLines(v), notes };
}

// ── recommendations ("הזדמנויות") — the server decides and words the facts; this only shows them ────────────────────────────────────────
export const RECS_NOTE = "אלה נקודות לבדיקה מתוך מה שנרשם, לא החלטה. ״עד ₪X״ הוא גבול עליון ולא חיסכון מובטח; רק חיסכון שציינת (או החלטת ביטול) נספר בסיכום. ההתחייבויות לא נוספו להוצאות.";
export interface RecCard { id: string; title: string; amount: string | null; tone: "saving" | "estimate" | "bound" | "plain"; facts: string[]; hint: string | null }
export interface RecsModel { summary: string[]; cards: RecCard[]; more: string | null; empty: boolean; note: string }

export function recCard(r: FccCashflowRec): RecCard {
  const amount = r.amount == null ? null
    : r.basis === "stated" ? `חיסכון ${money(r.amount)} בחודש`
    : r.basis === "inferred" ? `≈ ${money(r.amount)} בחודש (מוסק מהעלות)`
    : `עד ${money(r.amount)}`;
  return { id: r.id, title: r.title, amount, facts: r.facts, hint: r.hint,
           tone: r.amount == null ? "plain" : r.basis === "stated" ? "saving" : r.basis === "inferred" ? "estimate" : "bound" };
}

export function recsModel(v: FccCashflow): RecsModel {
  const r = v.recommendations, sm = r.summary, lines: string[] = [];
  if (sm.monthly_gap != null && sm.monthly_gap > 0) lines.push(`חסר בממוצע ${money(sm.monthly_gap)} בחודש (עד 3 החודשים האחרונים שהושלמו).`);
  else if (sm.monthly_gap === 0) lines.push("בחודשים האחרונים שהושלמו לא היה חוסר.");
  if (sm.stated_saving > 0) lines.push(`חיסכון שציינת בהתחייבויות: ${money(sm.stated_saving)} בחודש.`);
  if (sm.inferred_saving > 0) lines.push(`החלטות ביטול בלי חיסכון שצוין: ≈ ${money(sm.inferred_saving)} בחודש (מוסק מהעלות החודשית, רק אחרי ביטול בפועל).`);
  if (sm.covers_gap_pct != null) lines.push(`זה מכסה כ-${sm.covers_gap_pct}% מהחוסר.`);
  if (!r.commitments_known) lines.push("לא הצלחנו לקרוא את ההתחייבויות — ההמלצות מבוססות על ההוצאות בלבד.");
  const hidden = r.total - r.items.length;
  return { summary: lines, cards: r.items.map(recCard), more: hidden > 0 ? `ועוד ${hidden} נקודות לבדיקה` : null, empty: r.items.length === 0, note: RECS_NOTE };
}

