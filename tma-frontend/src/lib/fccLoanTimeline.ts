// Pure presentation of the loans timeline (computed on the server from the lender schedules / labelled estimates): when the payment drops and when the
// interest share of it falls below 25% / 20% / 15% … — nothing is computed here.
import type { FccLoanTimeline, FccTimelineScope } from "../types";
import { money } from "./fccPresentation";

export type TimelineScope = "no_mortgage" | "all";
export const TIMELINE_SCOPES: { key: TimelineScope; label: string }[] = [
  { key: "no_mortgage", label: "ללא משכנתא" },
  { key: "all", label: "כולל משכנתא" },
];
export const TIMELINE_TITLE = "ציר זמן: ההחזר החודשי והריבית";

/** "2028-05" -> "05/2028" */
export const monthLabel = (m: string): string => `${m.slice(5, 7)}/${m.slice(0, 4)}`;
const pct = (x: number): string => `${Math.round(x * 100)}%`;

export interface TimelineModel {
  summary: { label: string; value: string }[];
  drops: { key: string; title: string; detail: string }[];
  thresholds: { key: string; title: string; detail: string }[];
  yearly: { key: string; month: string; payment: string; interest: string; share: string }[];
  hint: string | null;
  note: string;
}

export function timelineModel(t: FccLoanTimeline | undefined, scope: TimelineScope): TimelineModel | null {
  const s: FccTimelineScope | null | undefined = t?.[scope];
  if (!t || !s) return null;
  const est = s.interest_remaining_estimated;
  return {
    summary: [
      { label: "יתרת חוב", value: money(s.balance) },
      { label: "החזר חודשי כולל", value: money(s.payment_now) },
      { label: "ריבית החודש", value: `${money(s.interest_now)} (${pct(s.share_now)} מההחזר)` },
      { label: "ריבית שנותרה עד הסיום", value: est > 0 ? `≈ ${money(s.interest_remaining)} (מלוחות ${money(s.interest_remaining_exact)} · הערכה ${money(est)})` : money(s.interest_remaining) },
      { label: "התשלום האחרון", value: monthLabel(s.last_month) },
    ],
    drops: s.drops.map((d) => ({
      key: d.month,
      title: `${monthLabel(d.month)}: ההחזר יורד ב-${money(d.drop)}`,
      detail: `מ-${money(d.from)} ל-${money(d.to)} · ריבית ${money(d.interest)}${d.ended.length ? ` · מסתיימות: ${d.ended.join(", ")}` : ""}`,
    })),
    thresholds: s.thresholds.map((th) => ({
      key: String(th.limit),
      title: `ריבית פחות מ-${pct(th.limit)} מההחזר`,
      detail: th.sustained
        ? `מ-${monthLabel(th.sustained)} ואילך (החזר ${money(th.payment)}, ריבית ${money(th.interest)})${th.first !== th.sustained ? ` · כבר ב-${monthLabel(th.first)} לזמן קצר` : ""}`
        : `ב-${monthLabel(th.first)} לזמן קצר בלבד`,
    })),
    yearly: s.yearly.map((y) => ({ key: y.month, month: monthLabel(y.month), payment: money(y.payment), interest: money(y.interest), share: pct(y.share) })),
    hint: s.loans < s.of ? `מבוסס על ${s.loans} מתוך ${s.of} הלוואות (בשאר חסר יתרה, החזר או מספר תשלומים)` : s.exact < s.loans ? `${s.loans - s.exact} מתוך ${s.loans} הלוואות מחושבות כהערכה, בלי לוח סילוקין` : null,
    note: t.assumption,
  };
}
