// Consumption by month — presentation only (no fetching, no storage, no financial arithmetic: every number is the server's, /api/fcc/consumption).
// The only computation is a bar width. The tab answers one question: in which month was the money actually consumed (the day of the purchase)?
import type { FccConsumption, FccConsumptionMonth } from "../types";
import { MISSING, insightLines, monthLabel } from "./fccCashflow";
import { money } from "./fccPresentation";

export const CONSUMPTION_NOTES = [
  "החודש הוא יום הקנייה בפועל. הלוואות לא נספרות כאן (הן בלשונית ״תזרים״).",
  "רכישה בתשלומים נספרת בחודש החיוב של כל תשלום ומסומנת ״תשלומים״ — לא בחודש הקנייה המקורי.",
  "חודש אחרון עשוי להיות חלקי: רכישות שעוד לא חויבו לא מופיעות עד שייובא הדוח הבא.",
];

export interface ConsumptionRow { month: string; label: string; total: string; tag: string | null; tone: "ok" | "missing" }
export interface ConsumptionDetail {
  month: string; label: string; total: string; partialNote: string | null; installments: string | null;
  categories: { key: string; label: string; value: string; pct: number; custom: boolean }[];
}
export interface ConsumptionModel { rows: ConsumptionRow[]; selected: string; detail: ConsumptionDetail | null; older: { month: string; label: string } | null; newer: { month: string; label: string } | null; insights: string[]; notes: string[] }

const rowOf = (m: FccConsumptionMonth): ConsumptionRow => ({
  month: m.month, label: monthLabel(m.month), total: m.expenses.total == null ? MISSING : money(m.expenses.total), tone: m.expenses.known ? "ok" : "missing",
  tag: m.partial ? "החודש עדיין לא הסתיים" : null,
});

/** The month shown by default: the latest complete month with expenses, else the latest month. */
export function defaultConsumptionMonth(v: Pick<FccConsumption, "months">): string {
  const done = [...v.months].reverse().find((m) => m.expenses.known && !m.partial);
  return (done ?? v.months[v.months.length - 1])?.month ?? "";
}

export function consumptionModel(v: FccConsumption, selected?: string): ConsumptionModel {
  const sel = selected && v.months.some((m) => m.month === selected) ? selected : defaultConsumptionMonth(v);
  const rows = [...v.months].reverse().map(rowOf);                                   // newest first
  const i = rows.findIndex((r) => r.month === sel);
  const month = v.months.find((m) => m.month === sel);
  const total = month?.expenses.total ?? 0;
  const detail: ConsumptionDetail | null = month ? {
    month: month.month, label: monthLabel(month.month), total: month.expenses.total == null ? MISSING : money(month.expenses.total),
    partialNote: month.partial ? "החודש עדיין לא הסתיים — רק מה שכבר מופיע בדוחות שיובאו." : null,
    installments: month.installments > 0 ? `מתוכם תשלומים: ${money(month.installments)}` : null,
    categories: month.expenses.categories.map((c) => ({
      key: c.key, label: c.label, value: money(c.amount), custom: !!c.custom,
      pct: total > 0 && c.amount > 0 ? Math.min(100, Math.round((c.amount / total) * 100)) : 0,
    })),
  } : null;
  return { rows, selected: sel, detail, newer: i > 0 ? rows[i - 1] : null, older: i >= 0 && i < rows.length - 1 ? rows[i + 1] : null, insights: insightLines(v), notes: CONSUMPTION_NOTES };
}
