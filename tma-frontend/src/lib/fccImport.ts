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
};
export const IMPORT_NOTE = "כל שורה נבנית בשרת מהקובץ ששלחת; נכתבות רק שורות שהוחלטו (עם קטגוריה / מקור מאושר). מה שלא ידוע לא נכתב — הוא נוסף כשורת ״ממתין״ בטבלת Cashflow Rules, ושם אתה מסווג. ייבוא חוזר של אותו דוח לא כותב דבר פעמיים.";

export interface ImportReview {
  blocked: string[];                  // why nothing can be imported (the statement does not add up ...)
  headline: string;
  months: { month: string; label: string; expenses: string; income: string; events: number }[];
  skipped: { key: string; label: string; count: number; total: string }[];
  pending: string[];
  pendingNote: string | null;
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
    headline: pl.remaining === 0 ? (pl.events > 0 ? "כל השורות שהוחלטו כבר יובאו." : "אין שורות שהוחלטו לייבוא בדוח הזה.")
      : `ייכתבו ${pl.remaining} רישומים${pl.already_imported ? ` (${pl.already_imported} כבר יובאו)` : ""}.`,
    months, skipped, pending: more > 0 ? [...pending, `ועוד ${more}`] : pending,
    pendingNote: pl.pending_rules > 0 ? `${pl.pending_rules} תיאורים יתווספו לטבלת Cashflow Rules כ״ממתין״${pl.pending_row_rules ? ` (מהם ${pl.pending_row_rules} העברות לבדיקה בודדת)` : ""}.` : null,
    canImport: p.can_import && blocked.length === 0,
    confirmLabel: pl.remaining > 0 ? `אשר ייבוא של ${pl.remaining} רישומים` : "הוסף את התיאורים לסיווג",
  };
}

export interface Progress { written: number; rules: number; step: "events" | "rules" | "done"; remaining: number; done: boolean; blocked: string | null }

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
  return p.step === "events" ? `נכתבו ${p.written} · נותרו ${p.remaining}…` : `מוסיף תיאורים לסיווג (${p.rules})…`;
}
