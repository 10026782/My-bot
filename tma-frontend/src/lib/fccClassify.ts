// One-by-one classification of imported expenses — presentation only. No fetching and no arithmetic: every number is the server's.
// The owner picks a category, sees one review line ("לסווג … כ…?") and confirms; only then is anything sent.
import type { FccClassifyView } from "../types";
import { money } from "./fccPresentation";

export const CUSTOM_MAX = 40;
export const SOURCE_LABEL = { bank: "בנק", card: "כרטיס אשראי", manual: "רישום ידני" } as const;

export interface ClassifyModel {
  empty: boolean;
  header: string;
  item: { id: string; title: string; meta: string; amount: string; sameCount: number } | null;
  sameLabel: string | null;
  categories: { key: string; label: string }[];
}

const dayLabel = (iso: string): string => { const [y, m, d] = iso.split("-"); return d && m && y ? `${d}/${m}/${y}` : iso; };

export function classifyModel(v: FccClassifyView): ClassifyModel {
  const item = v.item;
  return {
    empty: v.total === 0,
    header: v.total === 0 ? "אין הוצאות שממתינות לסיווג" : `${v.total} הוצאות ממתינות לסיווג · ${money(v.total_amount)}`,
    item: item ? { id: item.id, title: item.label, meta: `${dayLabel(item.date)} · ${SOURCE_LABEL[item.source] ?? item.source}`, amount: money(item.amount), sameCount: item.same_count } : null,
    sameLabel: item && item.same_count > 0 ? `החל גם על ${item.same_count} הוצאות נוספות עם אותו שם` : null,
    categories: v.categories,
  };
}

/** A new category's name as the owner typed it: trimmed, whitespace collapsed, never empty and never longer than the server accepts. */
export function customCategory(text: string): string | null {
  const t = text.replace(/\s+/g, " ").trim();
  return t && t.length <= CUSTOM_MAX ? t : null;
}

export function confirmLine(m: ClassifyModel, categoryLabel: string, applySame: boolean): string {
  if (!m.item) return "";
  const extra = applySame && m.item.sameCount > 0 ? ` (וגם ${m.item.sameCount} נוספות עם אותו שם)` : "";
  return `לסווג ״${m.item.title}״ · ${m.item.amount} כ״${categoryLabel}״${extra}?`;
}

export function resultNote(v: FccClassifyView): string | null {
  if (v.state !== "done") return null;
  const more = v.same_left ? ` · נותרו עוד ${v.same_left} עם אותו שם` : "";
  return `סווגו ${v.done ?? 1}${more}`;
}
