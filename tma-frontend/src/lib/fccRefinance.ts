// Pure presentation of the refinance simulator. Unknown stays unknown; both comparisons (same term / the offer's term) are always shown, because a longer term
// lowers the payment and usually raises the total interest — a lower payment alone is never presented as a saving.
import type { FccRefinance, FccRefinanceBody, FccRefinanceRow, FccRefinanceTotals } from "../types";
import { money } from "./fccPresentation";
import { UNKNOWN } from "./fccLoans";

export const REFINANCE_TITLE = "סימולטור מחזור למשכנתא";
export const REFINANCE_HELP = "הזן הצעה אחת: ריבית, תקופה ועלויות. המערכת תראה אילו הלוואות כדאי לכלול, כמה יורד ההחזר החודשי, מה קורה לריבית הכוללת ותוך כמה חודשים העלויות חוזרות. לא נשמר דבר.";

export interface OfferInput { rate: string; years: string; fees: string; insurance: string }

const num = (s: string): number | null => {
  const v = Number(String(s).replace(/,/g, "").trim());
  return String(s).trim() !== "" && Number.isFinite(v) ? v : null;
};

/** -> the request body, or the message to show. Costs may be blank (0); rate and term are required. */
export function offerBody(i: OfferInput, loanIds: string[] | null, feeOverrides: Record<string, string>): { body: FccRefinanceBody } | { error: string } {
  const rate = num(i.rate), years = num(i.years);
  if (rate == null || rate < 0 || rate > 30) return { error: "ריבית בין 0 ל-30 אחוז" };
  if (years == null || years < 1 || years > 35) return { error: "תקופה בין שנה ל-35 שנים" };
  const fees = i.fees.trim() === "" ? 0 : num(i.fees), insurance = i.insurance.trim() === "" ? 0 : num(i.insurance);
  if (fees == null || fees < 0 || insurance == null || insurance < 0) return { error: "עלויות חייבות להיות מספר חיובי או ריק" };
  const overrides: Record<string, number> = {};
  for (const [id, v] of Object.entries(feeOverrides)) { const n = num(v); if (n != null && n >= 0) overrides[id] = n; }
  const body: FccRefinanceBody = { rate, term_months: Math.round(years * 12), fees, insurance_monthly: insurance, fee_overrides: overrides };
  if (loanIds) body.loan_ids = loanIds;
  return { body };
}

export const VERDICT_LABEL: Record<FccRefinanceRow["verdict"], string> = {
  worth: "כדאי לכלול", not_worth: "לא כדאי", unknown_fee: "עמלה לא ידועה", missing: "חסרים נתונים",
};

export interface RefinanceLine { label: string; value: string; tone?: "good" | "bad" }
const signed = (n: number): RefinanceLine["tone"] => (n > 0 ? "good" : n < 0 ? "bad" : undefined);
const saving = (n: number) => (n >= 0 ? `חוסך ${money(n)}` : `מייקר ב-${money(-n)}`);

export function totalsLines(t: FccRefinanceTotals): RefinanceLine[] {
  return [
    { label: "החזר חודשי היום", value: money(t.current_payment) },
    { label: "החזר חודשי לפי ההצעה", value: money(t.offer_payment) },
    { label: "הפרש בהחזר החודשי", value: t.monthly_saving >= 0 ? `יורד ב-${money(t.monthly_saving)}` : `עולה ב-${money(-t.monthly_saving)}`, tone: signed(t.monthly_saving) },
    { label: "ריבית שנותרה היום", value: money(t.current_interest_left) },
    { label: "ריבית לפי ההצעה (כל התקופה)", value: money(t.offer_interest) },
    { label: "סה״כ בתקופת ההצעה", value: saving(t.total_saving_offer_term), tone: signed(t.total_saving_offer_term) },
    { label: `סה״כ באותו טווח (${t.same_term_months} חודשים)`, value: saving(t.total_saving_same_term), tone: signed(t.total_saving_same_term) },
    { label: "עלויות חד-פעמיות", value: money(t.one_time_costs) },
    { label: "החזר העלויות", value: t.payback_months == null ? UNKNOWN : t.payback_months === 0 ? "מיידי" : `${t.payback_months} חודשים` },
  ];
}

export interface RefinanceRowModel { id: string; title: string; verdict: string; tone: "good" | "bad" | "muted"; lines: string[]; needsFee: boolean }

export function rowModel(r: FccRefinanceRow): RefinanceRowModel {
  const lines = [
    r.balance != null ? `יתרה ${money(r.balance)}${r.rate != null ? ` · ריבית ${r.rate}%` : ""}${r.payment != null ? ` · החזר ${money(r.payment)}` : ""}` : "",
    r.interest_left != null ? `ריבית שנותרה ${money(r.interest_left)}${r.exact ? "" : " (הערכה)"}${r.months != null ? ` ב-${r.months} חודשים` : ""}` : "",
    r.interest_share != null ? `${Math.round(r.interest_share * 100)}% מהתשלומים שנותרו הם ריבית (השאר קרן)` : "",
    r.net_saving != null ? `באותו קצב פירעון, אחרי עמלה: ${saving(r.net_saving)}` : "",
    r.full_term_net != null ? `אם תישאר לכל תקופת המשכנתא: ${saving(r.full_term_net)}` : "",
    r.reason ?? "",
  ].filter(Boolean);
  return { id: r.id, title: r.name ?? UNKNOWN, verdict: VERDICT_LABEL[r.verdict], tone: r.verdict === "worth" ? "good" : r.verdict === "not_worth" ? "bad" : "muted", lines, needsFee: r.verdict === "unknown_fee" };
}

export interface RefinanceModel {
  recommended: RefinanceLine[] | null; recommendedPays: boolean; recommendedNames: string[];
  selected: RefinanceLine[] | null; rows: RefinanceRowModel[]; notes: string[];
}

export function refinanceModel(r: FccRefinance): RefinanceModel {
  const names = r.rows.filter((x) => r.recommended_ids.includes(x.id)).map((x) => x.name ?? UNKNOWN);
  return {
    recommended: r.recommended ? totalsLines(r.recommended) : null, recommendedPays: r.recommended_pays, recommendedNames: names,
    selected: r.selected ? totalsLines(r.selected) : null, rows: r.rows.map(rowModel), notes: r.notes,
  };
}
