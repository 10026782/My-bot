// Pure presentation of the refinance simulator, in plain words. Unknown stays unknown. Two comparisons are always shown together: "if you keep paying like today"
// (what the lower rate alone is worth) and "if you spread it over the whole mortgage" (a lower payment, but usually more interest in total).
import type { FccRefinance, FccRefinanceBody, FccRefinanceRow, FccRefinanceTotals } from "../types";
import { money } from "./fccPresentation";
import { UNKNOWN } from "./fccLoans";

export const REFINANCE_TITLE = "סימולטור מחזור למשכנתא";
export const REFINANCE_HELP = "הזן הצעה אחת: ריבית, כמה שנים ועלויות. תראה אילו הלוואות כדאי לכלול, כמה יורד ההחזר החודשי וכמה ריבית תשלם בסך הכל עד הסוף, לפני ואחרי. לא נשמר דבר.";
export const SCENARIO_KEEP = "אם תמשיך לשלם כמו היום";
export const SCENARIO_STRETCH = "אם תפרוס לכל התקופה";
export const REFINANCE_HOW = [
  "ריבית שנשארה = כמה ריבית עוד תשלם עד סוף ההלוואה. בהלוואה עם לוח סילוקין מהבנק זה המספר האמיתי; בלי לוח זה חישוב בקירוב (ההחזר כפול מספר התשלומים פחות היתרה).",
  `״${SCENARIO_KEEP}״: את היתרה של ההלוואה אתה פורע באותם חודשים שנשארו לה, אבל בריבית של ההצעה. כך רואים מה שווה ההפרש בריבית לבד.`,
  `״${SCENARIO_STRETCH}״: היתרה נפרסת על כל שנות המשכנתא. ההחזר החודשי יורד, אבל מכיוון שמשלמים ריבית על יותר זמן, בדרך כלל משלמים יותר ריבית בסך הכל.`,
  "ה״כדאי״ של כל הלוואה: אחרי ריבית ההצעה ואחרי עמלת הפירעון, האם נשאר חיסכון ממשי (לפחות 1% מהיתרה). הלוואה שכמעט נגמרה לא תצא כדאית, כי כמעט אין בה ריבית לחסוך.",
  "הסיכום כולל גם את העלויות החד-פעמיות של ההצעה (פתיחת תיק, שמאי וכו׳), ומראה אחרי כמה חודשים הן חוזרות בזכות הירידה בהחזר החודשי.",
  "הכול מניח שהריביות נשארות כמו היום. בריבית משתנה (פריים) או בהצמדה למדד התוצאה היא הערכה.",
];

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
  worth: "כדאי למחזר", not_worth: "לא כדאי", unknown_fee: "חסרה עמלת פירעון", missing: "חסרים נתונים",
};

export interface RefinanceLine { label: string; value: string; tone?: "good" | "bad" }
const signed = (n: number): RefinanceLine["tone"] => (n > 0 ? "good" : n < 0 ? "bad" : undefined);
const gain = (n: number) => (n >= 0 ? `תחסוך ${money(n)}` : `תשלם ${money(-n)} יותר`);
const delta = (n: number) => (n === 0 ? "ללא שינוי" : n > 0 ? `+${money(n)}` : `-${money(-n)}`);

/** The summary of a set of loans, in plain words. */
export function totalsLines(t: FccRefinanceTotals): RefinanceLine[] {
  return [
    { label: "היום אתה משלם בחודש", value: money(t.current_payment) },
    { label: "אחרי המחזור תשלם בחודש", value: money(t.offer_payment) },
    { label: "ההחזר החודשי", value: t.monthly_saving >= 0 ? `יורד ב-${money(t.monthly_saving)}` : `עולה ב-${money(-t.monthly_saving)}`, tone: signed(t.monthly_saving) },
    { label: "ריבית שנשארה לשלם היום", value: money(t.current_interest_left) },
    { label: "ריבית שתשלם אחרי המחזור (לכל התקופה)", value: money(t.offer_interest) },
    { label: `${SCENARIO_KEEP} (${t.same_term_months} חודשים)`, value: gain(t.total_saving_same_term), tone: signed(t.total_saving_same_term) },
    { label: SCENARIO_STRETCH, value: gain(t.total_saving_offer_term), tone: signed(t.total_saving_offer_term) },
    { label: "עלויות חד-פעמיות", value: money(t.one_time_costs) },
    { label: "העלויות חוזרות אחרי", value: t.payback_months == null ? UNKNOWN : t.payback_months === 0 ? "מיד" : `${t.payback_months} חודשים` },
  ];
}

export interface TableRow { label: string; today: string; after: string; diff: string; tone?: "good" | "bad" }
export interface ScenarioTable { title: string; rows: TableRow[] }

function tableRows(today: { pay: number; interest: number; total: number }, after: { pay: number; interest: number; total: number }): TableRow[] {
  const d = (a: number, b: number): TableRow["tone"] => (b < a ? "good" : b > a ? "bad" : undefined);
  return [
    { label: "החזר חודשי", today: money(today.pay), after: money(after.pay), diff: delta(after.pay - today.pay), tone: d(today.pay, after.pay) },
    { label: "ריבית עד הסוף", today: money(today.interest), after: money(after.interest), diff: delta(after.interest - today.interest), tone: d(today.interest, after.interest) },
    { label: "סה״כ לתשלום", today: money(today.total), after: money(after.total), diff: delta(after.total - today.total), tone: d(today.total, after.total) },
  ];
}

export interface RefinanceRowModel {
  id: string; title: string; verdict: string; tone: "good" | "bad" | "muted";
  facts: string[];            // balance / rate / payment, and the interest still ahead in shekels
  reason: string | null;      // one plain sentence: why this verdict
  tables: ScenarioTable[];    // today vs after, per scenario (empty when the loan is not priced)
  reliefLine: string | null;  // the monthly aspect, in two shekel figures
  needsFee: boolean;
}

export function rowModel(r: FccRefinanceRow): RefinanceRowModel {
  const facts = [
    r.balance != null ? `יתרה ${money(r.balance)}${r.rate != null ? ` · ריבית ${r.rate}%` : ""}${r.payment != null ? ` · החזר חודשי ${money(r.payment)}` : ""}` : "",
    r.interest_left != null ? `עד סוף ההלוואה תשלם עוד ${money(r.interest_left)} ריבית${r.months != null ? ` (${r.months} חודשים)` : ""}${r.exact ? "" : ", בקירוב"}` : "",
  ].filter(Boolean);
  const priced = r.balance != null && r.payment != null && r.interest_left != null && r.same_term_payment != null && r.same_term_interest != null && r.offer_payment != null && r.full_term_interest != null;
  const fee = r.prepay_fee ?? 0;
  const tables: ScenarioTable[] = [];
  if (priced) {
    const bal = r.balance as number, pay = r.payment as number, left = r.interest_left as number;
    const today = { pay, interest: left, total: bal + left };
    tables.push({ title: SCENARIO_KEEP, rows: tableRows(today, { pay: r.same_term_payment as number, interest: r.same_term_interest as number, total: bal + (r.same_term_interest as number) + fee }) });
    tables.push({ title: SCENARIO_STRETCH, rows: tableRows(today, { pay: r.offer_payment as number, interest: r.full_term_interest as number, total: bal + (r.full_term_interest as number) + fee }) });
  }
  const relief = r.monthly_relief;
  const reliefLine = relief != null && relief > 0 && r.relief_cost != null
    ? `אם המטרה היא להקל על החודש: ההחזר יורד ב-${money(relief)}, ${r.relief_cost >= 0 ? `אבל בסך הכל תשלם ${money(r.relief_cost)} יותר ריבית ועמלות` : `ובנוסף תחסוך ${money(-r.relief_cost)}`}.`
    : relief != null && relief <= 0 ? "במשכנתא ההחזר החודשי על ההלוואה הזו לא יורד." : null;
  return { id: r.id, title: r.name ?? UNKNOWN, verdict: VERDICT_LABEL[r.verdict], tone: r.verdict === "worth" ? "good" : r.verdict === "not_worth" ? "bad" : "muted",
    facts, reason: r.reason ?? null, tables, reliefLine, needsFee: r.verdict === "unknown_fee" };
}

export interface RefinanceModel {
  relief: RefinanceLine[] | null; reliefNames: string[];
  recommended: RefinanceLine[] | null; recommendedPays: boolean; recommendedNames: string[];
  selected: RefinanceLine[] | null; rows: RefinanceRowModel[]; notes: string[];
}

export function refinanceModel(r: FccRefinance): RefinanceModel {
  const names = r.rows.filter((x) => r.recommended_ids.includes(x.id)).map((x) => x.name ?? UNKNOWN);
  const reliefIds = r.relief_ids ?? [];
  const reliefNames = reliefIds.map((id) => r.rows.find((x) => x.id === id)?.name ?? UNKNOWN);
  return {
    relief: r.relief ? totalsLines(r.relief) : null, reliefNames,
    recommended: r.recommended ? totalsLines(r.recommended) : null, recommendedPays: r.recommended_pays, recommendedNames: names,
    selected: r.selected ? totalsLines(r.selected) : null, rows: r.rows.map(rowModel), notes: r.notes,
  };
}
