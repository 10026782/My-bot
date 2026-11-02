// Statement import — presentation only. No fetching, no storage, no financial arithmetic: every number is the server's. The review states exactly what
// would be written and what would not, and why; the only thing the client sends back is the digest it was shown.
import type { FccImportPreview, FccImportRun } from "../types";
import { money } from "./fccPresentation";
import { monthLabel } from "./fccCashflow";

export const KIND_LABEL = { bank: "דוח בנק (PDF)", card: "דוח כרטיס אשראי (Excel / PDF)" } as const;
export const SKIP_LABEL: Record<string, string> = {
  already_imported: "כבר יובאו קודם",
  card_settlement: "חיוב כרטיס אשראי בבנק — יפורט בדוח הכרטיס",
  cash_withdrawal: "משיכת מזומן",
  credit_service: "אשראי מתגלגל",
  adjustment: "הטבה / זיכוי מועדון",
  transfer: "העברה בין חשבונותיך",
  reversal: "חיוב שהוחזר (שני הצדדים)",
  ignore: "סומן להתעלמות",
  needs_review: "העברה / ביט — לבדיקה אחת-אחת",
  needs_classification: "ממתין לסיווג שלך",
  no_category: "חסרה קטגוריה בכלל",
  no_source: "חסר שם מקור להכנסה",
  loan: "הלוואה — לא נקראת ולא נשמרת (הסכומים המדויקים בלשונית ״הלוואות וחוב״)",
};
export const IMPORT_NOTE = "כל שורה נבנית בשרת מהקובץ ששלחת; הוצאה שלא ידועה נכתבת ״לא מסווג״ ואתה מסווג אותה אחת-אחת במסך; הכנסה, החזר והעברה לא נכתבים בלי החלטה שלך (הם נוספים כשורת ״ממתין״ בטבלת Cashflow Rules). ייבוא חוזר של אותו דוח לא כותב דבר פעמיים.";

export interface ImportReview {
  blocked: string[];                  // why nothing can be imported (the statement does not add up ...)
  headline: string;
  months: { month: string; label: string; expenses: string; income: string; events: number }[];
  skipped: { key: string; label: string; count: number; total: string }[];
  pending: string[];
  pendingNote: string | null;
  uncategorizedNote: string | null;
  canImport: boolean;
  confirmLabel: string;
}

export function reviewOf(p: FccImportPreview): ImportReview {
  const pl = p.plan;
  const blocked = p.parse.ok ? [] : ["הדוח אינו מתיישב — לא נכתב דבר.", ...p.parse.problems];
  const months = Object.entries(pl.months).map(([month, m]) => ({ month, label: monthLabel(month), expenses: money(m.expenses), income: money(m.income), events: m.events }));
  const skipped = Object.entries(pl.skipped).filter(([, s]) => s.count > 0).map(([key, s]) => ({ key, label: SKIP_LABEL[key] ?? key, count: s.count, total: money(s.total) }));
  const pending = pl.pending_examples.map((e) => `${e.match} — ${e.direction === "credit" ? "זכות" : "חובה"} ${money(e.example_amount)}${e.times_seen > 1 ? ` · ${e.times_seen} פעמים` : ""}${e.row ? " (שורה בודדת)" : ""}`);
  const more = pl.pending_rules - pl.pending_examples.length;
  return {
    blocked,
    headline: pl.remaining === 0 ? (pl.backfill ? `${pl.backfill} רישומים שכבר יובאו יקבלו תאריך חיוב.` : pl.events > 0 ? "כל השורות שהוחלטו כבר יובאו." : "אין שורות שהוחלטו לייבוא בדוח הזה.")
      : `ייכתבו ${pl.remaining} רישומים${pl.already_imported ? ` (${pl.already_imported} כבר יובאו)` : ""}${pl.backfill ? ` · ${pl.backfill} קיימים יקבלו תאריך חיוב` : ""}.`,
    months, skipped, pending: more > 0 ? [...pending, `ועוד ${more}`] : pending,
    uncategorizedNote: pl.uncategorized && pl.uncategorized.count > 0 ? `${pl.uncategorized.count} מהרישומים (${money(pl.uncategorized.total)}) ייכתבו בלי קטגוריה — תסווג אותם אחת-אחת במסך ״הוצאות לסיווג״.` : null,
    pendingNote: pl.pending_rules > 0 ? `${pl.pending_rules} תיאורים יתווספו לטבלת Cashflow Rules כ״ממתין״${pl.pending_row_rules ? ` (מהם ${pl.pending_row_rules} העברות לבדיקה בודדת)` : ""}.` : null,
    canImport: p.can_import && blocked.length === 0,
    confirmLabel: pl.remaining > 0 ? `אשר ייבוא של ${pl.remaining} רישומים` : pl.backfill ? `אשר עדכון תאריך חיוב ל-${pl.backfill} רישומים` : "הוסף את התיאורים לסיווג",
  };
}

export interface Progress { written: number; rules: number; step: "events" | "billing" | "rules" | "done"; remaining: number; done: boolean; blocked: string | null }

export function advance(prev: Progress, r: FccImportRun): Progress {
  if (r.state === "blocked") return { ...prev, blocked: r.message ?? "הכתיבה לא הושלמה — אפשר לנסות שוב." };
  const events = r.step === "events" ? (r.written ?? 0) : 0;
  const rules = r.step === "rules" ? (r.written ?? 0) : 0;
  return { written: prev.written + events, rules: prev.rules + rules, step: r.step, remaining: r.remaining ?? 0, done: r.state === "done", blocked: null };
}

export const START: Progress = { written: 0, rules: 0, step: "events", remaining: 0, done: false, blocked: null };

export function progressText(p: Progress): string {
  if (p.blocked) return p.blocked;
  if (p.done) return `הושלם: ${p.written} רישומים נכתבו${p.rules ? ` · ${p.rules} תיאורים נוספו לסיווג` : ""}.`;
  if (p.step === "billing") return `מעדכן תאריך חיוב לרישומים קיימים · נותרו ${p.remaining}…`;
  return p.step === "events" ? `נכתבו ${p.written} · נותרו ${p.remaining}…` : `מוסיף תיאורים לסיווג (${p.rules})…`;
}

// ── several statements at once: each file is checked and written on its own (the server is unchanged), ONE confirmation covers the whole batch ──────────────
export type FileStatus = "waiting" | "checking" | "ready" | "nothing" | "error" | "running" | "done" | "blocked";
export interface BatchItem { id: number; name: string; status: FileStatus; preview?: FccImportPreview; error?: string; progress?: Progress }

/** The state of one file after its preview came back: can be written, has nothing to write, or does not add up (never written). */
export function checkedItem(item: BatchItem, preview: FccImportPreview): BatchItem {
  const r = reviewOf(preview);
  if (r.blocked.length > 0) return { ...item, preview, status: "error", error: r.blocked.join(" ") };
  return { ...item, preview, status: r.canImport ? "ready" : "nothing", error: undefined };
}

export interface BatchTotals { files: number; ready: number; nothing: number; errors: number; toWrite: number; backfill: number; pendingRules: number }

export function batchTotals(items: BatchItem[]): BatchTotals {
  const t: BatchTotals = { files: items.length, ready: 0, nothing: 0, errors: 0, toWrite: 0, backfill: 0, pendingRules: 0 };
  for (const i of items) {
    if (i.status === "error") t.errors += 1;
    else if (i.status === "nothing") t.nothing += 1;
    else if (i.status === "ready" || i.status === "blocked" || i.status === "running") {
      t.ready += 1;
      t.toWrite += i.preview?.plan.remaining ?? 0; t.backfill += i.preview?.plan.backfill ?? 0; t.pendingRules += i.preview?.plan.pending_rules ?? 0;
    }
  }
  return t;
}

/** The ONE confirm button of a batch. */
export function batchConfirmLabel(t: BatchTotals): string {
  const parts = [t.toWrite > 0 ? `${t.toWrite} רישומים` : null, t.backfill > 0 ? `תאריך חיוב ל-${t.backfill} קיימים` : null].filter(Boolean).join(" + ");
  return `אשר ייבוא של ${t.ready} ${t.ready === 1 ? "קובץ" : "קבצים"}${parts ? ` (${parts})` : ""}`;
}

export function itemLine(i: BatchItem): string {
  switch (i.status) {
    case "waiting": return "ממתין לבדיקה";
    case "checking": return "קורא ומסווג…";
    case "ready": return reviewOf(i.preview as FccImportPreview).headline;
    case "nothing": return reviewOf(i.preview as FccImportPreview).headline;
    case "error": return i.error ?? "לא ניתן לקרוא את הקובץ — לא נכתב דבר";
    case "running": return progressText(i.progress ?? START);
    case "done": return progressText(i.progress ?? START);
    case "blocked": return i.progress?.blocked ?? "הכתיבה נעצרה — אפשר לנסות שוב (מה שנכתב לא ייכתב פעמיים)";
  }
}

/** Files still to be written, in the order the owner chose them (a retry takes the blocked ones again, never the done ones). */
export const runnable = (items: BatchItem[]): BatchItem[] => items.filter((i) => i.status === "ready" || i.status === "blocked");
