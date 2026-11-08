// Pure presentation of the loan-schedule import (the lender's exact amortization table). Nothing is guessed: no candidate -> the file is not saved.
import type { FccLoanSchedulePreview } from "../types";
import { dmy, money } from "./fccPresentation";

export const SCHEDULE_TITLE = "לוח סילוקין מדויק";
export const SCHEDULE_HELP = "אפשר לצרף קובץ Excel של לוח הסילוקין מהבנק / חברת האשראי (ה״תשלומים שחויבו״ וה״תשלומים שטרם חויבו״). הפירוק לקרן וריבית של ההלוואה יהיה מדויק במקום הערכה. נשמרת רק טבלת התשלומים — לא הקובץ.";
export const NO_MATCH = "לא נמצאה הלוואה פעילה עם אותו סכום מקורי — לא נשמר דבר.";

export interface SchedulePreviewModel {
  lines: string[];
  candidates: { id: string; label: string }[];
  canSave: boolean;
  needsChoice: boolean;
  problems: string[];
}

export function schedulePreviewModel(p: FccLoanSchedulePreview): SchedulePreviewModel {
  if (p.state === "rejected") return { lines: [], candidates: [], canSave: false, needsChoice: false, problems: p.problems?.length ? p.problems : ["הקובץ לא נקרא"] };
  const cands = (p.candidates ?? []).map((c) => ({ id: c.id, label: `${c.name}${c.lender && c.lender !== c.name ? ` · ${c.lender}` : ""}${c.has_schedule ? " (יוחלף לוח קיים)" : ""}` }));
  const m = p.this_month;
  const lines = [
    p.original != null ? `סכום מקורי ${money(p.original)}${p.payment_now != null ? ` · תשלום אחרון ${money(p.payment_now)}` : ""}` : "",
    p.payments_left != null ? `נותרו ${p.payments_left} תשלומים${p.ends ? ` עד ≈ ${dmy(p.ends)}` : ""}${p.interest_left != null ? ` · ריבית עתידית ${money(p.interest_left)}` : ""}` : "",
    m ? `החודש: ריבית ${money(m.interest)} · קרן ${money(m.principal)} · יתרה בסוף החודש ${money(m.balance_after)}` : "",
    ...(p.notes ?? []),
  ].filter(Boolean);
  return { lines, candidates: cands, canSave: cands.length > 0, needsChoice: cands.length > 1, problems: cands.length === 0 ? [NO_MATCH] : [] };
}
