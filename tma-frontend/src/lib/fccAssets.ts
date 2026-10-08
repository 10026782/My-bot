// Pure presentation of the FCC "נכסים והון" tab (read-only). Values are shown as stored; an unknown value is
// "לא הוגדר" (never ₪0), and the recorded mortgage vs. the linked loans are shown apart — never added together.
import type { FccAssetItem, FccAssets, FccSoldAsset } from "../types";
import { UNKNOWN, pct, val } from "./fccLoans";
import { dmy, money } from "./fccPresentation";

export const ASSET_TYPE_LABEL: Record<string, string> = {
  Residential: "מגורים", "Residential Investment": "השקעה למגורים", "Income Property": "נכס מניב",
  Land: "קרקע", Commercial: "מסחרי", Other: "אחר",
};
export const UNTYPED = "לא סווג";

export interface AssetsHeaderCard { key: string; label: string; value: string; hint?: string }

function coverage(known: number, total: number): string | undefined {
  return total > 0 && known < total ? `מבוסס על ${known} מתוך ${total} נכסים` : undefined;
}

export function assetsHeaderCards(a: FccAssets): AssetsHeaderCard[] {
  const s = a.summary;
  return [
    { key: "value", label: "שווי נכסים פעילים", value: val(s.total_value), hint: coverage(s.coverage.value, s.count) },
    { key: "equity", label: "הון בנכסים פעילים (Equity)", value: val(s.total_equity), hint: coverage(s.coverage.equity, s.count) ?? "שווי פחות משכנתא רשומה" },
    { key: "my_equity", label: "ההון שלי בנכסים פעילים (לפי בעלות)", value: val(s.total_my_equity), hint: coverage(s.coverage.my_equity, s.count) },
    { key: "income", label: "הכנסה חודשית מנכסים פעילים", value: val(s.total_monthly_income), hint: coverage(s.coverage.monthly_income, s.count) },
  ];
}

export interface DebtLine { label: string; value: string }

/** Debt overview kept in two separate lines because the recorded mortgage and linked loans can describe the same loan. */
export function debtLines(a: FccAssets): DebtLine[] {
  const s = a.summary;
  return [
    { label: "משכנתא רשומה בנכסים", value: val(s.total_mortgage) },
    { label: `הלוואות מקושרות לנכס פעיל (${s.linked_loans_count})`, value: val(s.linked_loans_debt) },
    { label: `הלוואות שלא מקושרות לנכס פעיל (${s.unlinked_loans_count})`, value: val(s.unlinked_loans_debt) },
  ];
}

export interface AssetCardModel {
  id: string;
  title: string;
  typeLabel: string;
  status: string | null;
  rows: { label: string; value: string }[];
  linkedLoans: { id: string; text: string }[];       // empty -> no linked-loans block at all
  linkedDebtLine: string | null;
  partial: boolean;
  nextStep: string | null;          // "<text> · אחראי: <owner>" as stored; null -> no line
  actionable: boolean;              // false for a sold / inactive asset: no write actions on its card
}

/** Live Assets.Status choices meaning the asset is no longer held: the writer has nothing to update there. */
export const ASSET_GONE = ["נמכר", "לא פעיל"];

export function assetCardModel(i: FccAssetItem): AssetCardModel {
  const rows = [
    { label: "שווי נוכחי", value: val(i.current_value) },
    { label: "משכנתא רשומה", value: val(i.mortgage_balance) },
    { label: "הון (Equity)", value: val(i.equity) },
    { label: "ההון שלי", value: val(i.my_equity) },
    { label: "אחוז בעלות", value: i.ownership_pct == null ? UNKNOWN : `${i.ownership_pct}%` },
    { label: "הכנסה חודשית", value: val(i.monthly_income) },
  ];
  return {
    id: i.id,
    title: i.name || UNKNOWN,
    typeLabel: i.asset_type ? ASSET_TYPE_LABEL[i.asset_type] ?? i.asset_type : UNTYPED,
    status: i.status,
    rows,
    linkedLoans: i.linked_loans.map((l) => ({
      id: l.id,
      text: `${l.name || UNKNOWN} · יתרת סילוק ${val(l.early_closure_balance)} · החזר ${val(l.monthly_payment)}${l.interest_rate == null ? "" : ` · ${pct(l.interest_rate)}`}`,
    })),
    linkedDebtLine: i.linked_loans.length ? `חוב מקושר: ${val(i.linked_debt)}${i.linked_debt_known < i.linked_loans.length ? " (חלקי)" : ""}` : null,
    partial: i.current_value == null || i.equity == null,
    nextStep: i.next_step ? `${i.next_step}${i.next_step_owner && i.next_step_owner !== "—" ? ` · אחראי: ${i.next_step_owner}` : ""}` : null,
    actionable: !ASSET_GONE.includes(i.status ?? ""),
  };
}

export { money };

/** The totals above are ACTIVE assets only. A sale turns an asset into proceeds this screen does not track, so once any asset
 *  is sold the screen says so — it never presents the active total as the owner's total net worth. */
export function soldNote(a: FccAssets): string | null {
  const n = a.sold?.count ?? 0;
  return n > 0 ? `הסיכומים כוללים נכסים פעילים בלבד (לא כולל ${n} שנמכרו). תמורת המכירה אינה נרשמת כאן כנכס או כמזומן — זה אינו "הון כולל".` : null;
}

export interface SoldCardModel {
  id: string;
  title: string;
  rows: { label: string; value: string }[];
  openLoans: string[];              // loans still linked to the sold asset (they stay open)
}

export function soldCardModel(i: FccSoldAsset): SoldCardModel {
  return {
    id: i.id,
    title: i.name || UNKNOWN,
    rows: [
      { label: "תאריך מכירה", value: i.sale_date ? dmy(i.sale_date) : UNKNOWN },
      { label: "מחיר מכירה (100%)", value: val(i.sale_amount) },
      { label: i.ownership_pct == null ? "החלק שלי" : `החלק שלי (${i.ownership_pct}%)`, value: val(i.my_share) },
    ],
    openLoans: i.linked_loans.map((l) => `${l.name || UNKNOWN} · יתרת סילוק ${val(l.early_closure_balance)}`),
  };
}
