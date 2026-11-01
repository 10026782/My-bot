// Classification of DESCRIPTIONS (the owner's pending rules) — presentation only. No fetching and no arithmetic: every number is the server's.
// The owner picks a category, sees one review line and confirms; only then is anything sent. One answer decides every row with that description,
// in the next import and in every later one.
import type { FccRuleView } from "../types";
import { money } from "./fccPresentation";

export const SOURCE_LABEL: Record<string, string> = { bank: "בנק", card: "כרטיס אשראי", any: "בנק / כרטיס" };

export interface RuleModel {
  empty: boolean;
  header: string;
  item: { id: string; title: string; meta: string } | null;
  categories: { key: string; label: string }[];
}

export function ruleModel(v: FccRuleView): RuleModel {
  const it = v.item;
  return {
    empty: v.total === 0,
    header: v.total === 0 ? "אין תיאורים שממתינים לסיווג" : `${v.total} תיאורים ממתינים לסיווג`,
    item: it ? { id: it.id, title: it.match, meta: `${SOURCE_LABEL[it.applies_to] ?? it.applies_to} · ${it.times_seen > 1 ? `${it.times_seen} פעמים` : "פעם אחת"} · עד ${money(it.amount)}` } : null,
    categories: v.categories,
  };
}

export function ruleConfirmLine(m: RuleModel, categoryLabel: string): string {
  return m.item ? `לסווג כל ״${m.item.title}״ כ״${categoryLabel}״? (בייבוא הבא ובכל ייבוא אחריו)` : "";
}
