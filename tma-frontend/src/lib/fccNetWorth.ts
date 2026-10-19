// Unified net worth card — presentation only. No fetching, no storage, no financial arithmetic: every number is the server's
// (/api/fcc/net-worth); this only words them. A missing value is "חסר" (never 0); receivables are shown apart and never in the net.
import type { FccNetWorth } from "../types";
import { money } from "./fccPresentation";

export const NET_WORTH_TITLE = "שווי נקי מאוחד";
export const MISSING = "חסר";
export const NET_WORTH_NOTE = "חשבונות (היתרה האחרונה שדווחה) + נכסים (השווי שהוזן × אחוז הבעלות) − התחייבויות. אין כאן אמידת שווי נכסים ואין חישוב מס. התחייבות על נכס מנוכה פעם אחת בלבד.";
export const RECEIVABLES_NOTE = "צפוי / לא ודאי — כסף שחייבים לך. אינו הכנסה, אינו כסף קיים ואינו נכלל בשווי הנקי.";
export const NO_DATE = "תאריך עדכון לא נשמר";

export interface NetWorthRow { key: string; label: string; value: string; hint: string }
export interface NetWorthModel { net: NetWorthRow; rows: NetWorthRow[]; receivables: NetWorthRow | null; notes: string[]; partial: boolean }

const val = (n: number | null | undefined): string => (n == null ? MISSING : money(n));

export function netWorthModel(v: FccNetWorth): NetWorthModel {
  const g = v.gaps;
  const notes: string[] = [NET_WORTH_NOTE];
  if (g.accounts_without_balance > 0) notes.push(`${g.accounts_without_balance} חשבונות בלי יתרה שדווחה — אינם נספרים בשווי הנקי.`);
  if (g.assets_left_out > 0) notes.push(`${g.assets_left_out} נכסים בלי שווי או אחוז בעלות — הוצאו מהחישוב (ולא הוערכו).`);
  if (g.debts_without_balance > 0) notes.push(`${g.debts_without_balance} הלוואות בלי יתרה — אינן מנוכות.`);
  for (const a of v.assets.items) {                       // each left-out asset by name, with what the owner has to enter (the system never guesses a value)
    const name = a.name || "נכס ללא שם";
    if (a.missing.includes("missing_value")) notes.push(`${name} — חסר שווי — יש להזין`);
    if (a.missing.includes("missing_ownership")) notes.push(`${name} — חסר אחוז בעלות — יש להזין`);
  }
  if (v.assets.sold_excluded > 0) notes.push(`${v.assets.sold_excluded} נכסים שנמכרו אינם נכללים.`);
  const kept = v.assets.items.filter((a) => a.ignored_mortgage_balance != null).length;
  if (kept > 0) notes.push(`ב-${kept} נכסים יתרת המשכנתא שבנכס זהה להלוואה המקושרת — נוכתה פעם אחת.`);
  const accountsHint = v.accounts.oldest_as_of ? `עדכון ישן ביותר: ${v.accounts.oldest_as_of}` : NO_DATE;
  const rows: NetWorthRow[] = [
    { key: "accounts", label: "חשבונות", value: val(v.accounts.total), hint: `${v.accounts.items.length} חשבונות · ${accountsHint}` },
    { key: "assets", label: "נכסים", value: val(v.assets.total), hint: [`${v.assets.items.filter((a) => a.counted).length} נכסים`, v.assets.as_of_known ? "" : NO_DATE].filter(Boolean).join(" · ") },
    { key: "liabilities", label: "התחייבויות", value: val(v.liabilities.total), hint: v.liabilities.as_of_known ? "" : NO_DATE },
  ];
  const recv = v.receivables.count === 0 ? null
    : { key: "receivables", label: "חייבים לי (צפוי / לא ודאי)", value: val(v.receivables.total), hint: RECEIVABLES_NOTE };
  return {
    net: { key: "net", label: NET_WORTH_TITLE, value: val(v.net), hint: v.partial ? "חלקי — חסרים נתונים (ראו הערות)" : `נכון ל-${v.as_of}` },
    rows, receivables: recv, notes, partial: v.partial,
  };
}
