// Pure presentation of the FCC early-payoff engine. All numbers come from the server (scores, metrics, scenarios);
// this file only orders, labels and explains them. It never recommends: it shows the data and why a loan sits where it does.
import type { FccLoans, FccPayoffRow, FccScenarioResult, FccScenarios, PayoffStrategy } from "../types";
import { UNKNOWN, pct, val } from "./fccLoans";
import { money } from "./fccPresentation";

export const STRATEGY_TABS: { key: PayoffStrategy; label: string; basis: string }[] = [
  { key: "balanced", label: "מאוזן", basis: "ציון מאוזן (ריבית 30% · פינוי תזרים 30% · סכום לסילוק 25% · זמן שנותר 15%)" },
  { key: "interest", label: "ריבית", basis: "ריבית גבוהה קודם" },
  { key: "cash", label: "פינוי תזרים", basis: "החזר חודשי שמתפנה, גבוה קודם" },
  { key: "efficiency", label: "יעילות סילוק", basis: "יעילות פינוי תזרים שנתית (החזר חודשי × 12 ÷ יתרת סילוק), גבוהה קודם" },
];

export const FACTOR_LABEL: Record<string, string> = { interest: "ריבית", cash: "החזר חודשי", closure: "יתרת סילוק", time: "זמן שנותר" };

/** Ratio -> "54%" / "4.5%". Not a return on investment — it is cash released per shekel of closure amount. */
export function ratioPct(r: number | null | undefined): string {
  if (r == null) return UNKNOWN;
  const v = r * 100;
  return `${v >= 10 ? Math.round(v) : Number(v.toFixed(1))}%`;
}

export function orderedRows(loans: FccLoans, strategy: PayoffStrategy): FccPayoffRow[] {
  const payoff = loans.payoff;
  if (!payoff) return [];
  const pos = (id: string) => { const i = payoff.rankings[strategy].indexOf(id); return i < 0 ? 1e9 : i; };
  return [...payoff.items].sort((a, b) => pos(a.id) - pos(b.id));
}

const tier = (score: number | null): string => (score == null ? "" : score >= 67 ? "גבוהה" : score <= 33 ? "נמוכה" : "בינונית");

function futureCost(r: FccPayoffRow): string {
  if (r.estimated_future_cost == null) return UNKNOWN;
  return r.future_cost_exact ? money(r.estimated_future_cost) : `משוער ${money(r.estimated_future_cost)}`;
}

export interface PayoffCardModel {
  id: string;
  title: string;
  rank: number;
  figures: { label: string; value: string }[];
  scoreLabel: string;               // "62 · כיסוי נתונים 3/4"
  partial: boolean;
  missingLabel: string | null;      // "חסר: ריבית"
  why: string;                      // explanation, strategy-led; facts only
}

export function payoffCardModel(r: FccPayoffRow, strategy: PayoffStrategy, rank: number): PayoffCardModel {
  const lead: Record<PayoffStrategy, string | null> = {
    balanced: r.balanced_score == null ? null : `ציון מאוזן ${Math.round(r.balanced_score)}`,
    interest: r.interest_rate == null ? null : `ריבית ${tier(r.scores.interest)} (${pct(r.interest_rate)})`,
    cash: r.monthly_cash_freed == null ? null : `פינוי תזרים ${tier(r.scores.cash)}`,
    efficiency: r.annualized_cash_release == null ? null : `יעילות פינוי תזרים ${ratioPct(r.annualized_cash_release)} בשנה`,
  };
  const facts = [
    lead[strategy],
    r.monthly_cash_freed == null ? null : `מפנה ${money(r.monthly_cash_freed)} לחודש`,
    r.amount_to_close == null ? null : `דורשת ${money(r.amount_to_close)} לסגירה`,
    r.months_remaining == null ? null : `${r.months_remaining} תשלומים נותרו`,
  ].filter((x): x is string => !!x);
  const missing = r.missing_factors.map((f) => FACTOR_LABEL[f]);
  return {
    id: r.id,
    title: r.name || UNKNOWN,
    rank,
    figures: [
      { label: "יתרת סילוק", value: val(r.amount_to_close) },
      { label: "ריבית", value: pct(r.interest_rate) },
      { label: "החזר חודשי שמתפנה", value: val(r.monthly_cash_freed) },
      { label: "חודשים שנותרו", value: r.months_remaining == null ? UNKNOWN : String(r.months_remaining) },
      { label: "יעילות פינוי תזרים שנתית", value: ratioPct(r.annualized_cash_release) },
      { label: "עלות עתידית משוערת", value: futureCost(r) },
    ],
    scoreLabel: r.balanced_score == null ? `ציון משוקלל: ${UNKNOWN}` : `ציון משוקלל ${Math.round(r.balanced_score)} · כיסוי נתונים ${r.score_coverage_label}`,
    partial: r.partial,
    missingLabel: missing.length ? `חסר: ${missing.join(", ")}` : null,
    why: facts.length ? facts.join(" · ") : "אין מספיק נתונים לדירוג",
  };
}

/** Typed budget -> number (accepts ₪, commas, spaces, Hebrew-locale separators); null when not a positive amount. */
export function parseBudget(text: string): number | null {
  const cleaned = text.replace(/[₪,\s‎‏]/g, "");
  if (!/^\d+(\.\d+)?$/.test(cleaned)) return null;
  const n = Number(cleaned);
  return n > 0 && n <= 1_000_000_000 ? n : null;
}

export function presetBudget(loans: FccLoans): { label: string; amount: number } | null {
  const g = loans.goal;
  return g && g.target > 0 ? { label: `תקציב יעד סגירת חובות: ${money(g.target)}`, amount: g.target } : null;
}

export interface ScenarioRow { key: string; label: string; closed: string; released: string; left: string }

const sRow = (key: string, label: string, r: FccScenarioResult | null): ScenarioRow =>
  ({ key, label, closed: r ? String(r.closed_count) : UNKNOWN, released: r ? val(r.monthly_cash_released) : UNKNOWN, left: r ? money(r.remaining_budget) : UNKNOWN });

/** Comparison of every strategy for one budget, plus the best whole-loan combinations (by cash released / future cost saved). */
export function scenarioRows(s: FccScenarios): ScenarioRow[] {
  return [
    ...STRATEGY_TABS.map((t) => sRow(t.key, t.label, s.strategies[t.key])),
    sRow("optimal-cash", "שילוב: מקסימום תזרים", s.optimal.cash),
    sRow("optimal-saved", "שילוב: מקסימום עלות שנחסכת", s.optimal.saved),
  ];
}

export function scenarioDetail(r: FccScenarioResult): { lines: { label: string; value: string }[]; notes: string[] } {
  const saved = r.future_cost_saved == null ? UNKNOWN : r.future_cost_saved_exact ? money(r.future_cost_saved) : `משוער ${money(r.future_cost_saved)}`;
  const notes: string[] = [];
  if (r.skipped_over_budget.length) notes.push(`${r.skipped_over_budget.length} הלוואות לא נכנסו בתקציב — אין פרעון חלקי`);
  if (r.excluded_unknown_amount.length) notes.push(`${r.excluded_unknown_amount.length} הלוואות בלי יתרת סילוק לא נכללו בסימולציה`);
  if (r.partial) notes.push("נתונים חלקיים: חלק מהסכומים כוללים רק הלוואות עם נתון ידוע");
  return {
    lines: [
      { label: "הלוואות שנסגרות", value: String(r.closed_count) },
      { label: "ניצול תקציב", value: money(r.used) },
      { label: "נשאר מהתקציב", value: money(r.remaining_budget) },
      { label: "החזר חודשי שמתפנה", value: val(r.monthly_cash_released) },
      { label: "חוב שנעלם", value: money(r.debt_removed) },
      { label: "עלות עתידית שנחסכת", value: saved },
    ],
    notes,
  };
}
