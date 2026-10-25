// E1d: "מבחן לחץ נזילות" — presentation only. No fetching, no storage, no financial arithmetic: every number shown comes from the
// server (portfolio_lab.liquidity_stress); this only parses the form into the request and words/lays out the answer.
import type { StressMode, StressParams, StressView } from "../types";
import { ils } from "./familyWealth";

export interface StressForm {
  fundValue: string; phase: "withdrawal" | "accumulation"; deposit: string; support: string; otherExpenses: string; otherIncome: string;
  returnPct: string; feePct: string; inflationPct: string; horizonMonths: string;
  crisisOn: boolean; crisisDecline: string; crisisStart: string; crisisRecoveryYears: string;
  pledged: string; earmarked: string; protectedAmount: string;
  loanOn: boolean; loanAmount: string; loanRate: string; loanMaxLtv: string; loanInterestOnly: boolean; loanTerm: string; loanVerified: boolean;
  collateral: "risky_and_pledged" | "risky_only"; cureFirst: "cushion" | "risky_sale";
  proceeds: "none" | "asset_income"; proceedsIncome: string; proceedsValue: string;
}

// The research example (docs/portfolio_lab/E1_LIQUIDITY_STRESS_TEST_SPEC.md). The max LTV is deliberately EMPTY: it is the user's own
// number (the lender's term) — no bank default exists.
export const DEFAULT_STRESS_FORM: StressForm = {
  fundValue: "3000000", phase: "withdrawal", deposit: "8000", support: "10000", otherExpenses: "0", otherIncome: "0",
  returnPct: "8", feePct: "0.15", inflationPct: "2", horizonMonths: "120",
  crisisOn: true, crisisDecline: "40", crisisStart: "1", crisisRecoveryYears: "2",
  pledged: "0", earmarked: "0", protectedAmount: "0",
  loanOn: false, loanAmount: "900000", loanRate: "7", loanMaxLtv: "", loanInterestOnly: true, loanTerm: "", loanVerified: false,
  collateral: "risky_and_pledged", cureFirst: "cushion", proceeds: "none", proceedsIncome: "0", proceedsValue: "0",
};

export const STRESS_TITLE = "מבחן לחץ נזילות";
export const STRESS_NOTE = "תרחיש לפי ההנחות שהזנת — לא תחזית ולא המלצה, ואין כאן הערכת סיכוי. סף ה-LTV והריבית הם נתונים שלך ולא אומתו מול בנק. שום דבר כאן לא נשמר.";
export const STRESS_PROTECTED_NOTE = "הון הילדים מופרד: אינו בטוחה ואינו מממן הפסדים של הקרן המרכזית.";
export const STRESS_STALE_NOTE = "התוצאה למטה חושבה לפי הנחות קודמות — הקלטים השתנו. הרץ שוב כדי לעדכן.";

/** The request key of a run, and whether the form no longer matches it (an invalid form also counts: the old answer is not for these inputs). */
export function stressKey(form: StressForm): string | null {
  const parsed = stressParams(form);
  return parsed.ok ? JSON.stringify(parsed.params) : null;
}
export const isStale = (form: StressForm, ranKey: string | null): boolean => ranKey !== null && stressKey(form) !== ranKey;

export const CASHFLOW_LABEL = "תזרים", CALL_LABEL = "דרישת בטוחות";

type Parsed<T> = { ok: true; value: T } | { ok: false; error: string };

function num(raw: string, label: string, min: number, max: number, integer = false): Parsed<number> {
  const text = raw.trim();
  const n = Number(text);
  if (text === "" || !Number.isFinite(n)) return { ok: false, error: `${label}: יש להזין מספר` };
  if (integer && !Number.isInteger(n)) return { ok: false, error: `${label}: יש להזין מספר שלם` };
  if (n < min || n > max) return { ok: false, error: `${label}: בין ${min} ל-${max}` };
  return { ok: true, value: n };
}

/** Form → request body. Validation here only saves a round trip; the server validates everything again. */
export function stressParams(f: StressForm): { ok: true; params: StressParams } | { ok: false; error: string } {
  const fields: [keyof StressParams | string, Parsed<number>][] = [];
  const get = (raw: string, label: string, min: number, max: number, integer = false) => {
    const r = num(raw, label, min, max, integer);
    fields.push([label, r]);
    return r;
  };
  const fund = get(f.fundValue, "שווי הקרן", 1, 1e12), dep = get(f.deposit, "הפקדה חודשית", 0, 1e9), sup = get(f.support, "תמיכה חודשית", 0, 1e9);
  const oex = get(f.otherExpenses, "הוצאות נוספות", 0, 1e9), oin = get(f.otherIncome, "הכנסות נוספות", 0, 1e9);
  const ret = get(f.returnPct, "תשואה שנתית", -50, 100), fee = get(f.feePct, "דמי ניהול", 0, 10), inf = get(f.inflationPct, "אינפלציה", -10, 100);
  const hor = get(f.horizonMonths, "אופק (חודשים)", 1, 360, true);
  const pledged = get(f.pledged, "מזומן משועבד", 0, 1e12), ear = get(f.earmarked, "מזומן להתחייבויות משפחתיות", 0, 1e12), prot = get(f.protectedAmount, "הון ילדים", 0, 1e12);
  const bad = fields.find(([, r]) => !r.ok);
  if (bad && !bad[1].ok) return { ok: false, error: bad[1].error };
  const v = (r: Parsed<number>) => (r as { ok: true; value: number }).value;
  const params: StressParams = {
    fund_value: v(fund), phase: f.phase, monthly_deposit: v(dep), monthly_support: v(sup), other_monthly_expenses: v(oex), other_monthly_income: v(oin),
    annual_return_pct: v(ret), annual_fee_pct: v(fee), inflation_pct: v(inf), horizon_months: v(hor), cushion_modes: [0, 12, 24],
    cash_buckets: { pledged: v(pledged), family_earmarked: v(ear) }, protected_capital: { amount: v(prot) },
  };
  if (f.crisisOn) {
    const d = num(f.crisisDecline, "ירידה (%)", 1, 90), s = num(f.crisisStart, "חודש תחילת המשבר", 1, 360, true), r = num(f.crisisRecoveryYears, "שנות התאוששות", 1, 10, true);
    for (const x of [d, s, r]) if (!x.ok) return { ok: false, error: x.error };
    params.crisis = { decline_pct: v(d), start_month: v(s), recovery_years: v(r) };
  }
  if (f.loanOn) {
    const amount = num(f.loanAmount, "סכום ההלוואה", 1, 1e12), rate = num(f.loanRate, "ריבית שנתית (%)", 0, 100);
    if (f.loanMaxLtv.trim() === "") return { ok: false, error: "סף LTV: יש להזין את הסף שהמלווה קבע (אין ברירת מחדל)" };
    const ltv = num(f.loanMaxLtv, "סף LTV (%)", 5, 95);
    for (const x of [amount, rate, ltv]) if (!x.ok) return { ok: false, error: x.error };
    const loan: NonNullable<StressParams["loan"]> = {
      amount: v(amount), annual_rate_pct: v(rate), max_ltv_pct: v(ltv), interest_only: f.loanInterestOnly, terms_verified: f.loanVerified,
      collateral: f.collateral, cure_order: f.cureFirst === "cushion" ? ["cushion", "risky_sale"] : ["risky_sale", "cushion"], use_proceeds: { kind: "none" },
    };
    if (!f.loanInterestOnly) {
      const term = num(f.loanTerm, "תקופת ההלוואה (חודשים)", 1, 600, true);
      if (!term.ok) return { ok: false, error: term.error };
      loan.term_months = term.value;
    }
    if (f.proceeds === "asset_income") {
      const inc = num(f.proceedsIncome, "הכנסה חודשית מהנכס", 0, 1e9), val = num(f.proceedsValue, "שווי הנכס", 0, 1e12);
      for (const x of [inc, val]) if (!x.ok) return { ok: false, error: x.error };
      loan.use_proceeds = { kind: "asset_income", monthly_income: v(inc), asset_value: v(val) };
    }
    params.loan = loan;
  }
  return { ok: true, params };
}

export const missing = (v: number | null | undefined, fmt: (n: number) => string): string => (v === null || v === undefined ? "—" : fmt(v));
const monthText = (m: number | null): string => (m === null ? "—" : `חודש ${m}`);
const yesNo = (ok: boolean | null | undefined): string => (ok === null || ok === undefined ? "לא רלוונטי" : ok ? "כן" : "לא");

function eventCell(b: StressMode["events"]["forced_sale"], withAmount: boolean): string {
  if (b.status === "not_applicable_no_loan") return "לא רלוונטי (אין הלוואה)";
  if (!b.count) return "לא אירע";
  const base = `${b.count === 1 ? "חודש אחד" : `${b.count} חודשים`} · ראשון: ${monthText(b.first_month)}`;
  return withAmount ? `${base} · ${ils(b.total_amount)}` : base;
}

export interface StressRow { key: string; label: string; cells: string[] }
export const stressHead = (view: StressView): string[] => ["מדד", ...view.modes.map((m) => m.label)];

/** The three events are separate rows by design: a collateral call, a forced sale and a cash shortfall are never merged into one figure. */
export function stressRows(view: StressView): StressRow[] {
  const row = (key: string, label: string, pick: (m: StressMode) => string): StressRow => ({ key, label, cells: view.modes.map(pick) });
  const hasLoan = view.loan !== null;
  const rows: StressRow[] = [
    row("cushion", "כרית חופשית", (m) => ils(m.free_cushion)),
    row("support", "חודשי תמיכה שהכרית מכסה", (m) => missing(m.months_of_support_covered, (n) => n.toFixed(1))),
    row("call", "אירוע: דרישת בטוחות", (m) => eventCell(m.events.collateral_call, false)),
    row("forced", "אירוע: מכירה כפויה", (m) => eventCell(m.events.forced_sale, true)),
    row("forced_cause", "  מתוכה בגלל תזרים / בגלל דרישת בטוחות", (m) => `${ils(m.forced_sale_by_cause.cashflow)} / ${ils(m.forced_sale_by_cause.collateral_call)}`),
    row("shortfall", "אירוע: מחסור במזומן", (m) => eventCell(m.events.cash_shortfall, true)),
    row("exhausted", "הכרית אזלה", (m) => (m.cushion_exhausted_month === null ? "לא" : monthText(m.cushion_exhausted_month))),
  ];
  if (hasLoan) {
    rows.push(
      row("trigger", "ירידה שמפעילה דרישת בטוחות (%)", (m) => missing(m.trigger_decline_pct, (n) => `${n}%`)),
      row("ltv0", "LTV התחלתי", (m) => missing(m.initial_ltv, (n) => `${(n * 100).toFixed(1)}%`)),
      row("ltv_max", "LTV מקסימלי", (m) => missing(m.max_ltv, (n) => `${(n * 100).toFixed(1)}%`)),
      row("debt", "יתרת חוב בסוף האופק", (m) => ils(m.final_debt)),
    );
  }
  rows.push(row("final", "שווי נקי בסוף האופק", (m) => ils(m.final_net_worth)), row("delta", "הפרש מול תרחיש ללא משבר", (m) => ils(m.delta_vs_no_crisis)));
  if (view.modes.some((m) => m.window_24m)) {
    rows.push(
      row("w_sale", "חלון 24 חודשים: ללא מכירה כפויה", (m) => yesNo(m.window_24m?.forced_sale_free)),
      row("w_short", "חלון 24 חודשים: ללא מחסור במזומן", (m) => yesNo(m.window_24m?.shortfall_free)),
      row("w_call", "חלון 24 חודשים: ללא דרישת בטוחות", (m) => yesNo(m.window_24m?.collateral_call_free)),
    );
  }
  return rows;
}

export function burnRows(view: StressView): { key: string; label: string; value: string }[] {
  const labels: Record<string, string> = {
    support: "תמיכה משפחתית", other_expenses: "הוצאות נוספות", loan_interest: "ריבית הלוואה (חודש ראשון)", loan_repayments: "פירעון קרן (חודש ראשון)",
    less_other_income: "פחות: הכנסות נוספות", less_asset_income: "פחות: הכנסה מנכס", less_deposits: "פחות: הפקדות",
  };
  return Object.entries(view.net_burn.components).filter(([, n]) => n !== 0).map(([key, n]) => ({ key, label: labels[key] ?? key, value: ils(n) }));
}

export const netWorthLines = (view: StressView) =>
  view.modes.map((m) => ({ name: m.label, pts: m.series.filter((_, i) => i % 3 === 2 || i === 0).map((r): [number, number] => [r.month, r.net_worth]) }));

// E1e: hand-off from a loan option typed in the funding planner. Strings are passed through untouched (no arithmetic). What the plan does not
// hold is NOT guessed: the max LTV (the lender's own term) and the collateral stay for the user to type.
export interface StressSeed { id: number; amount: string; rate: string; term: string; verified: boolean }
export const LOAN_TO_STRESS_LABEL = "בדוק במבחן לחץ נזילות";
export const STRESS_SEEDED_NOTE = "הערכים הועברו מאפשרות ההלוואה בתוכנית המימון (סכום, ריבית ותקופה). סף ה-LTV והבטוחה לא קיימים בתוכנית ולא נוחשו — יש להזין אותם. התוכנית עצמה לא השתנתה.";

export function seedFromLoan(values: Record<string, string>, id: number): StressSeed | null {
  const amount = (values.amount ?? "").trim(), rate = (values.annual_rate_pct ?? "").trim(), term = (values.term_months ?? "").trim();
  if (amount === "" || rate === "" || term === "") return null;
  return { id, amount, rate, term, verified: values.terms_verified === "true" };
}

export function applySeed(form: StressForm, seed: StressSeed): StressForm {
  return { ...form, loanOn: true, loanAmount: seed.amount, loanRate: seed.rate, loanInterestOnly: false, loanTerm: seed.term, loanVerified: seed.verified };
}
