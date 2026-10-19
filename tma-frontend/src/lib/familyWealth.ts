// "תכנון חיסכון לטווח ארוך" (family wealth) — presentation only. No fetching, no storage, no financial arithmetic:
// every number shown comes from the server (FCC overview / portfolio_lab view); this only words and lays them out.
import type { FccAccount, FccAccountsForecast, FccAccountsView, FccForecastAccount, FccForecastParams, FccOverview, FundingCertainty, FundingOptionResult, FundingOptionType, FundingLiquidityState, FundingPlan, FundingRequestBody, FundingSourceCategory, FundingSourceItem, FundingSources, FundingWindow, FundingWindowEnd, FundingWindowOption, PaceAccountRow, PaceParams, PaceView, PlKpis, PortfolioLabParams, PortfolioLabView } from "../types";
import { money } from "./fccPresentation";

export const SCREEN_TITLE = "תכנון חיסכון לטווח ארוך";   // owner's choice (14/10/2026); one constant so the name can change in one place

// Every place that names the screen derives from SCREEN_TITLE: entry card, screen title, open button, tab-strip label.
export const OPEN_LABEL = `פתח: ${SCREEN_TITLE}`;
export const TABS_ARIA_LABEL = `אזורי ${SCREEN_TITLE}`;

export type FamilyTabKey = "savings" | "accounts" | "funding" | "lab";
export const FAMILY_TABS: { key: FamilyTabKey; label: string }[] = [
  { key: "savings", label: "החיסכון שלי" },
  { key: "accounts", label: "החשבונות" },
  { key: "funding", label: "מימון יעד" },
  { key: "lab", label: "מעבדת העתיד" },
];
export const FAMILY_TAB_PREFIX = "fw";

/** Every deposit figure is something the owner recorded (review -> "אשר"); nothing is matched against a bank or a fund. */
export const SELF_REPORTED = "דיווח עצמי — לא מאומת מול בנק או קרן";
export const BALANCE_PLACEHOLDER = "יתרת התיק תוצג כהערכה לפי הפקדות, עם עדכון ידני מדי כמה חודשים — בשלב הבא.";

export interface SavingsRow { key: string; label: string; value: string; hint?: string }
export interface SavingsTabModel { rows: SavingsRow[]; notes: string[]; hasData: boolean }

/** The savings tab from data the FCC overview already carries. Plan = the standing level of the savings goal(s); actual =
 *  this month's recorded deposits on the long-term goal; "צפוי להתפנות" is derived from income and is NOT a plan. */
export function savingsTabModel(data: Pick<FccOverview, "summary" | "savings_release" | "savings_history">): SavingsTabModel {
  const plan = data.summary.savings;
  const release = data.savings_release ?? null;
  const rows: SavingsRow[] = [];
  rows.push(plan && plan.mode === "monthly_level"
    ? { key: "plan", label: "הפקדה חודשית מתוכננת", value: money(plan.actual), hint: `יעד: ${money(plan.target)}` }
    : { key: "plan", label: "הפקדה חודשית מתוכננת", value: "לא הוגדרה", hint: "אין יעד חיסכון חודשי פעיל" });
  rows.push(release
    ? { key: "deposited", label: "הופקד החודש", value: money(release.deposited), hint: SELF_REPORTED }
    : { key: "deposited", label: "הופקד החודש", value: "לא זמין", hint: "אי אפשר לגזור — חסר יעד הכנסה או הכנסה קבועה" });
  if (release) {
    rows.push({ key: "expected", label: "צפוי להתפנות", value: money(release.expected),
                hint: "נגזר מההכנסה החודשית — אינו הפקדה מתוכננת" });
  }
  const h = data.savings_history ?? null;
  if (h) {
    rows.push({ key: "ytd", label: "הופקד מתחילת השנה", value: money(h.ytd), hint: `${h.deposit_count} הפקדות · ${SELF_REPORTED}` });
    rows.push({ key: "average", label: "ממוצע חודשי", value: money(h.monthly_average), hint: `על פני ${h.months_elapsed} חודשים מתחילת השנה` });
    rows.push({ key: "streak", label: "רצף חודשים עם הפקדה", value: String(h.streak), hint: h.last_deposit ? `הפקדה אחרונה: ${h.last_deposit}` : "עוד לא נרשמה הפקדה" });
    rows.push({ key: "ytd_gap", label: "פער מול התכנון מתחילת השנה", value: money(h.ytd_gap),
                hint: `תכנון מצטבר ${money(h.ytd_plan)} · פער נרשם ואינו מתמלא אוטומטית` });
  }
  rows.push({ key: "balance", label: "יתרת תיק", value: "לא זמינה", hint: BALANCE_PLACEHOLDER });
  return {
    rows,
    notes: ["אין כאן הבטחת תשואה — המספרים הם דיווח והנחות בלבד."],
    hasData: Boolean(plan || release || h),
  };
}

/** Entry card on the monthly FCC tab: one short line, only from what the overview already has. */
export function familyCardModel(data: Pick<FccOverview, "summary" | "savings_release" | "savings_history">): { title: string; value: string; hint: string } {
  const release = data.savings_release ?? null;
  return {
    title: SCREEN_TITLE,
    value: release ? `הופקד החודש ${money(release.deposited)}` : "אין עדיין נתון לחודש",
    hint: release ? SELF_REPORTED : "פתחו את המסך לתכנון ולמעבדת העתיד",
  };
}

// ── Accounts tab (D1 step 7 / B1): wording + layout of what the server derived. No sums, no estimates computed here. ──
export const ACCOUNT_TYPE_LABELS: Record<string, string> = {
  pension: "קרן פנסיה", study_fund: "קרן השתלמות", provident_investment: "קופת גמל להשקעה", managers_insurance: "ביטוח מנהלים",
  brokerage: "חשבון השקעות", liquid: "נזיל", other: "אחר",
};
export const LIQUIDITY_LABELS: Record<string, string> = {
  immediate: "נזיל מיד", locked_until_date: "נעול עד תאריך", age_based: "לפי גיל", unknown: "לא ידוע",
};
export const BALANCE_FACT_NOTE = "השווי הוא היתרה האחרונה שדווחה — עובדה. ההערכה מתווספת בנפרד ואינה נכללת בסכום המאוחד.";
export const NO_SNAPSHOT = "אין יתרה שדווחה";
export const NO_ACCOUNTS_TITLE = "עוד אין חשבונות";
export const NO_ACCOUNTS_MESSAGE = "חשבונות פנסיה, השתלמות והשקעות יוצגו כאן אחרי שיוזנו. אפשר יהיה להוסיף יתרה בשלב הבא.";

const verificationNote = (v: string | null | undefined): string =>
  v === "self_reported" ? SELF_REPORTED : v === "statement" ? "לפי דוח" : v === "bank_or_fund_confirmed" ? "מאומת מול בנק או קרן" : "";

export interface AccountRow { id: string; title: string; subtitle: string; value: string; hint: string; estimate?: string; closed: boolean }
export interface AccountsTabModel { hasAccounts: boolean; total: SavingsRow; extras: SavingsRow[]; rows: AccountRow[]; notes: string[] }

export function accountRow(a: FccAccount): AccountRow {
  const kind = a.account_type ? ACCOUNT_TYPE_LABELS[a.account_type] ?? a.account_type : "";
  const subtitle = [kind, a.institution, a.holder_names].filter(Boolean).join(" · ");
  const liquidity = a.liquidity ? (LIQUIDITY_LABELS[a.liquidity] ?? a.liquidity) : "";
  const b = a.balance;
  return {
    id: a.id, title: a.name || "חשבון ללא שם", subtitle, closed: a.status === "closed",
    value: b ? money(b.value) : NO_SNAPSHOT,
    hint: b ? [`נכון ל-${b.as_of}`, verificationNote(b.verification), liquidity].filter(Boolean).join(" · ") : [liquidity, "הוסיפו יתרה כדי לראות שווי"].filter(Boolean).join(" · "),
    estimate: b && b.estimate.movement_count > 0 ? `הערכה בעקבות ${b.estimate.movement_count} תנועות מאז: ${money(b.estimate.value)}` : undefined,
  };
}

/** The accounts tab from the server view: the consolidated value is the server's sum of snapshots; closed accounts are listed, not counted. */
export function accountsTabModel(view: FccAccountsView): AccountsTabModel {
  const t = view.totals;
  const total: SavingsRow = t.consolidated_value == null
    ? { key: "total", label: "שווי מאוחד", value: "לא זמין", hint: "עוד אין יתרה שדווחה באף חשבון פעיל" }
    : { key: "total", label: "שווי מאוחד", value: money(t.consolidated_value),
        hint: `${t.accounts_with_value} חשבונות עם יתרה${t.oldest_snapshot ? ` · העדכון הישן ביותר: ${t.oldest_snapshot}` : ""}${t.all_self_reported ? ` · ${SELF_REPORTED}` : ""}` };
  const extras: SavingsRow[] = [];
  if (t.estimated_value != null && t.estimated_value !== t.consolidated_value) {
    extras.push({ key: "estimate", label: "הערכה לפי תנועות מאז", value: money(t.estimated_value), hint: "הערכה בלבד — אינה חלק מהשווי המאוחד" });
  }
  if (t.accounts_without_snapshot > 0) extras.push({ key: "missing", label: "חשבונות בלי יתרה", value: String(t.accounts_without_snapshot), hint: "אינם נספרים בשווי המאוחד" });
  if (t.closed_accounts > 0) extras.push({ key: "closed", label: "חשבונות סגורים", value: String(t.closed_accounts), hint: "מוצגים ברשימה, לא נכללים בסכום" });
  return {
    hasAccounts: view.accounts.length > 0, total, extras, rows: view.accounts.map(accountRow),
    notes: [BALANCE_FACT_NOTE, "אין כאן הבטחת תשואה — המספרים הם דיווח בלבד."],
  };
}

// ── Accounts forecast (D1 step 7 / A1): the form is strings while typing; every number shown comes from the server's engine run. ──
export interface ForecastForm { years: string; returnPct: string; feePct: string; inflationPct: string; deposits: Record<string, string> }
export const DEFAULT_FORECAST_FORM: ForecastForm = { years: "20", returnPct: "6", feePct: "0.15", inflationPct: "2", deposits: {} };
export const FORECAST_TITLE = "תחזית לפי הנחות";
export const FORECAST_NOTE = "תחזית מבוססת הנחות בלבד — לא הבטחת תשואה ולא המלצה. נקודת המוצא היא היתרה האחרונה שדווחה בכל חשבון; ההפקדה החודשית היא הנחה שלך (ברירת מחדל 0).";
export const FORECAST_ACCOUNT_HEAD = ["חשבון", "יתרת פתיחה", "הפקדה חודשית", "דמי ניהול", "שווי סופי", "שווי ריאלי"];

/** Typed text -> request body. Blank / non-numeric input is an error shown on the form, never silently 0. A blank deposit means "no deposit". */
export function forecastParams(form: ForecastForm): { ok: true; params: FccForecastParams } | { ok: false; error: string } {
  const num = (text: string, name: string): number | string => {
    const v = text.trim() === "" ? NaN : Number(text);
    return Number.isFinite(v) ? v : `${name}: יש להזין מספר`;
  };
  const f = { years: num(form.years, "מספר שנים"), ret: num(form.returnPct, "תשואה"), fee: num(form.feePct, "דמי ניהול"), infl: num(form.inflationPct, "אינפלציה") };
  for (const v of Object.values(f)) if (typeof v === "string") return { ok: false, error: v };
  const n = f as Record<keyof typeof f, number>;
  if (!Number.isInteger(n.years)) return { ok: false, error: "מספר שנים: יש להזין מספר שלם" };
  const deposits: Record<string, number> = {};
  for (const [id, text] of Object.entries(form.deposits)) {
    if (text.trim() === "") continue;
    const v = Number(text);
    if (!Number.isFinite(v) || v < 0) return { ok: false, error: "הפקדה חודשית: יש להזין מספר שאינו שלילי" };
    if (v > 0) deposits[id] = v;
  }
  return { ok: true, params: { years: n.years, annual_return_pct: n.ret, annual_fee_pct: n.fee, inflation_pct: n.infl, monthly_contributions: deposits } };
}

export interface ForecastModel {
  total: SavingsRow[]; head: string[]; rows: { id: string; cells: string[]; feeHint: string; liquidity: string }[]; chart: ReturnType<typeof lineChartModel> | null; notes: string[];
  goalHead: string[]; goals: { id: string; cells: string[]; verdict: string }[];
  allocations: AllocationModel | null;
}
/** What the server reports as missing per account, in the owner's words (a missing input is shown, never filled in). */
const MISSING_LABELS: Record<string, string> = {
  management_fee: "דמי ניהול מהצבירה", deposit_fee: "דמי ניהול מההפקדה", expected_return: "תשואה צפויה", monthly_deposit: "הפקדה חודשית מתוכננת",
  investment_track: "מסלול השקעה", linkage: "הצמדה", insurance_cost: "עלות ביטוח חודשית", insurance_cost_date: "תאריך עלות הביטוח",
  liquidity: "סוג נזילות", liquid_from: "תאריך שחרור",
};
const MAX_INCOMPARABLE_SHOWN = 4;
export const GOAL_HEAD = ["מטרה", "יעד", "חודש יעד", "נגיש מאומת", "תוצאה"];
const GOAL_REASONS: Record<string, string> = {
  missing_target: "חסר סכום יעד", missing_date: "חסר תאריך יעד", past_date: "תאריך היעד עבר", beyond_horizon: "מעבר לאופק התחזית",
  no_verified_accessible_account: "אין חשבון נגיש מאומת",
  over_allocated: "חשבון מזין בהקצאת יתר — לא מחושב",
  allocated_not_accessible: "הוקצה, אך לא נגיש (מותנה או נעול)",
  allocation_not_yet_effective: "ההקצאה טרם נכנסה לתוקף בחודש הקריאה",
  allocation_effective_after_due: "ההקצאה נכנסת לתוקף אחרי תאריך היעד",
};
const LIQUIDITY_STATE_LABELS: Record<string, string> = { accessible: "נגיש", conditional: "מותנה", locked: "נעול" };
const SKIPPED_LABELS: Record<string, string> = {
  inactive: "הקצאות שאינן פעילות", status_missing: "הקצאות בלי סטטוס", invalid_link: "הקצאות עם קישור לא תקין", unknown_link: "הקצאות שאינן שלך או שאינן מוכרות",
  invalid_value: "הקצאות עם ערך לא תקין", account_closed: "הקצאות לחשבון סגור", no_snapshot: "הקצאות לחשבון בלי יתרה", not_yet_effective: "הקצאות שטרם נכנסו לתוקף",
};
export const ALLOCATION_TITLE = "הקצאות מטרות";
export const ALLOCATION_NOTE = "הקצאה היא תווית על כסף שכבר קיים: היא אינה העברה, אינה הפקדה או משיכה, ואינה הופכת כסף לנזיל. הסכומים מחושבים בשרת מהשורות שהזנת ב-Airtable; המסך לא משנה אותן.";
export const NO_ALLOCATIONS_MESSAGE = "לא הוזנו הקצאות. כיסוי המטרות מחושב כפוטנציאל לפי כל הכסף הנגיש (כפי שהוצג).";

export interface AllocationModel {
  kpis: SavingsRow[];
  accountHead: string[]; accounts: { id: string; cells: string[]; over: boolean }[];
  goalHead: string[]; goals: { id: string; cells: string[]; warn: string }[];
  notes: string[];
}
const ALLOCATION_ACCOUNT_HEAD = ["חשבון", "שווי", "הוקצה", "לא מוקצה", "נזילות היום"];
const ALLOCATION_GOAL_HEAD = ["מטרה", "הוקצה", "נגיש", "מותנה", "נעול"];
/** The server's allocation overview as rows. Nothing is derived here beyond text: over-allocation is shown, never clipped to zero. */
export function allocationsModel(view: FccAccountsForecast): AllocationModel | null {
  const a = view.allocations;
  if (!a || !a.has_allocations) return null;
  const notes: string[] = [];
  if (a.over_allocated_accounts > 0) notes.push(`${a.over_allocated_accounts} חשבונות בהקצאת יתר — מוצגים בנפרד ואינם נכללים בסכומי "הוקצה" ו"לא מוקצה"; מטרות שמוזנות מהם אינן מחושבות.`);
  if (a.duplicate_goal_account_pairs > 0) notes.push(`${a.duplicate_goal_account_pairs} זוגות מטרה+חשבון עם יותר משורת הקצאה אחת — הסכומים נסכמו; כדאי לאחד.`);
  const skipped = Object.entries(a.skipped ?? {}).filter(([, n]) => n > 0).map(([k, n]) => `${n} ${SKIPPED_LABELS[k] ?? k}`);
  if (skipped.length) notes.push(`לא נספרו: ${skipped.join(", ")}.`);
  return {
    kpis: [
      { key: "value", label: "שווי החשבונות עם יתרה", value: money(a.totals.accounts_value), hint: `נכון ל-${a.as_of} · היתרות האחרונות שדווחו` },
      { key: "allocated", label: "הוקצה למטרות", value: money(a.totals.allocated), hint: `${a.count} הקצאות בתוקף` },
      { key: "unallocated", label: "לא מוקצה", value: money(a.totals.unallocated), hint: "בחשבונות שאינם בהקצאת יתר" },
      { key: "over", label: "הקצאת יתר", value: money(a.totals.over_allocated), hint: a.totals.over_allocated > 0 ? "מוצגת במפורש, אינה מקוזזת" : "אין" },
    ],
    accountHead: ALLOCATION_ACCOUNT_HEAD,
    accounts: a.accounts.filter((x) => x.allocations.length > 0 || x.over_allocated).map((x) => ({
      id: x.id, over: x.over_allocated,
      cells: [x.name || "חשבון ללא שם", money(x.value), x.over_allocated ? `${money(x.allocated)} (יתר ${money(x.over_by)})` : money(x.allocated),
              x.over_allocated ? "הקצאת יתר" : money(x.unallocated), LIQUIDITY_STATE_LABELS[x.liquidity_state] ?? x.liquidity_state],
    })),
    goalHead: ALLOCATION_GOAL_HEAD,
    goals: a.goals.map((g) => ({
      id: g.id, cells: [g.title || "מטרה ללא שם", money(g.allocated), money(g.accessible), money(g.conditional), money(g.locked)],
      warn: g.blocked_by_over_allocation > 0 ? `${money(g.blocked_by_over_allocation)} מוזנים מחשבון בהקצאת יתר` : "",
    })),
    notes,
  };
}
/** How an account's liquidity was classified, in words that never promise a right to withdraw. */
export function liquidityLabel(a: FccForecastAccount): string {
  const l = a.liquidity;
  if (!l) return "";
  const date = l.liquid_from ? l.liquid_from.split("-").reverse().join("/") : "";
  switch (l.basis) {
    case "immediate": return "נגיש מיד (כפי שסומן)";
    case "retirement_immediate": return "מוצר פרישה — מותנה, לא נגיש";
    case "dated": return `תאריך שחרור ${date} — מותנה, זכאות למשיכה לא אומתה`;
    case "undated": return "נעול — חסר תאריך שחרור";
    default: return "נזילות לא אומתה — מותנה";
  }
}
/** Wording + layout of the server's forecast: totals are the server's consolidated numbers; the chart only scales them. */
export function forecastModel(view: FccAccountsForecast): ForecastModel {
  const c = view.consolidated;
  const total: SavingsRow[] = c.final_nominal == null ? [] : [
    { key: "start", label: "שווי פתיחה מאוחד", value: money(c.start_value), hint: `${c.accounts} חשבונות · היתרות האחרונות שדווחו${view.all_self_reported ? ` · ${SELF_REPORTED}` : ""}` },
    { key: "final", label: `שווי מאוחד בעוד ${view.years} שנים`, value: money(c.final_nominal), hint: "נומינלי, אחרי דמי ניהול · הנחות בלבד" },
    { key: "real", label: "שווי מאוחד ריאלי", value: money(c.final_real), hint: `אחרי אינפלציה של ${view.assumptions.inflation_pct}% בשנה` },
    { key: "invested", label: "סך שהושקע", value: money(c.invested), hint: "כולל את יתרת הפתיחה וההפקדות שהוזנו" },
  ];
  const notes = [...view.warnings];
  if (view.excluded.without_snapshot > 0) notes.push(`${view.excluded.without_snapshot} חשבונות בלי יתרה שדווחה אינם בתחזית.`);
  if (view.excluded.closed > 0) notes.push(`${view.excluded.closed} חשבונות סגורים אינם בתחזית.`);
  for (const g of view.data_gaps ?? []) {
    notes.push(`חסר לדיוק — ${g.name || "חשבון ללא שם"}: ${g.missing.map((k) => MISSING_LABELS[k] ?? k).join(", ")}.`);
  }
  // Only goals that can actually be compared get a table row; the rest stay visible as ONE compact "missing for accuracy" line (capped), never a wall of empty rows.
  const incomparable = (view.goals ?? []).filter((g) => g.verdict === "not_comparable");
  if (incomparable.length > 0) {
    const shown = incomparable.slice(0, MAX_INCOMPARABLE_SHOWN).map((g) => `${g.title || "מטרה ללא שם"} (${GOAL_REASONS[g.reason ?? ""] ?? "לא ניתן להשוואה"}${g.basis === "allocation" && g.allocated_value ? ` · הוקצה ${money(g.allocated_value)}` : ""})`);
    const more = incomparable.length - shown.length;
    notes.push(`חסר לדיוק — ${incomparable.length} מטרות בלי השוואה: ${shown.join(", ")}${more > 0 ? ` ועוד ${more}` : ""}.`);
  }
  const comparable = (view.goals ?? []).filter((g) => g.verdict !== "not_comparable");
  const anyAllocation = comparable.some((g) => g.basis === "allocation");
  const goals = comparable.map((g, i) => {
    const byAllocation = g.basis === "allocation";
    // Planned (what the owner entered) and effective (what the account can carry) are shown separately; the entered amount is never reduced.
    const allocated = !byAllocation ? "—" : (g.allocation_gap ?? 0) > 0.005 ? `בפועל ${money(g.allocated_value ?? 0)} מתוך מתוכנן ${money(g.planned_allocated_value ?? 0)}` : money(g.allocated_value ?? 0);
    let result = g.verdict === "covered" ? (byAllocation ? "מכוסה לפי ההקצאה" : "מכוסה (פוטנציאלית)") : `חסר ${money(g.gap ?? 0)}${byAllocation ? " לפי ההקצאה" : ""}`;
    if (!byAllocation && g.potential_caveat === "allocated_elsewhere") {
      result += ` · ${money(g.allocated_elsewhere_accessible ?? 0)} מהכסף הנגיש כבר מוקצה למטרות אחרות; פנוי בפועל ${money(g.unallocated_accessible_value ?? 0)}`;
    }
    const cells = [g.title || "מטרה ללא שם", g.target_amount == null ? "—" : money(g.target_amount), g.due_month ? g.due_month.split("-").reverse().join("/") : "—",
                   ...(anyAllocation ? [allocated] : []), g.accessible_value == null ? "—" : money(g.accessible_value), result];
    return { id: g.id ?? `goal-${i}`, verdict: g.verdict, cells };
  });
  const hasLiquidity = c.series.length > 0 && c.series[0].accessible !== undefined;
  return {
    total, head: FORECAST_ACCOUNT_HEAD, notes, goalHead: anyAllocation ? [...GOAL_HEAD.slice(0, 3), "הוקצה", ...GOAL_HEAD.slice(3)] : GOAL_HEAD, goals,
    allocations: allocationsModel(view),
    rows: view.accounts.map((a) => ({
      id: a.id, feeHint: a.fee_source === "account" ? "דמי הניהול של החשבון" : "ברירת המחדל מהקלט", liquidity: liquidityLabel(a),
      cells: [a.name || "חשבון ללא שם", money(a.start_value), a.monthly_contribution ? money(a.monthly_contribution) : "—",
              `${a.fee_pct}%${a.fee_source === "default" ? " (ברירת מחדל)" : ""}`, money(a.final_nominal), money(a.final_real)],
    })),
    chart: view.accounts.length ? lineChartModel([
      { name: "מאוחד (נומינלי)", pts: c.series.map((r): [number, number] => [r.year, r.nominal]) },
      { name: "מאוחד (ריאלי)", pts: c.series.map((r): [number, number] => [r.year, r.real]), color: CHART_COLORS[2] },
      { name: "סך שהושקע", pts: c.series.map((r): [number, number] => [r.year, r.invested]), color: "#8892a0", dash: "4 3" },
      ...(hasLiquidity ? [
        { name: "נגיש מאומת", pts: c.series.map((r): [number, number] => [r.year, r.accessible ?? 0]), color: CHART_COLORS[3] },
        { name: "מותנה", pts: c.series.map((r): [number, number] => [r.year, r.conditional ?? 0]), color: CHART_COLORS[1], dash: "2 3" },
      ] : []),
    ]) : null,
  };
}

// ── Future lab form (strings while typing; converted once on submit) ──
export interface LabForm {
  initial: string; monthly: string; years: string; returnPct: string; feePct: string; inflationPct: string;
  timing: "begin" | "end"; indexed: boolean; baseline: string; strategies: string[];
  crisisOn: boolean; crisisDecline: string; crisisYear: string; crisisRecovery: "fast" | "prolonged";
  crisisMonth: string; // "" = annual crisis (the whole-year path); "1".."12" = a one-month drop inside the year
  compareOn: boolean; cmpMonthly: string; cmpReturnPct: string; cmpFeePct: string; cmpInflationPct: string; // set B: blank = same as set A
}
export const STRATEGY_OPTIONS: { key: string; label: string }[] = [
  { key: "global", label: "100% קרן עולמית" }, { key: "world_em", label: "World + EM" },
  { key: "three_funds", label: "השילוש" }, { key: "experimental_90_10", label: "90/10" },
];
export const CRISIS_DECLINES = [10, 20, 30, 40, 50];
export const DEFAULT_LAB_FORM: LabForm = {
  initial: "0", monthly: "8000", years: "30", returnPct: "8", feePct: "0.15", inflationPct: "2",
  timing: "end", indexed: false, baseline: "global", strategies: STRATEGY_OPTIONS.map((s) => s.key),
  crisisOn: false, crisisDecline: "30", crisisYear: "5", crisisRecovery: "fast", crisisMonth: "",
  compareOn: false, cmpMonthly: "", cmpReturnPct: "", cmpFeePct: "", cmpInflationPct: "",
};

/** Typed text -> request body. Blank / non-numeric input is an error shown on the form, never silently 0. */
export function labParams(form: LabForm): { ok: true; params: PortfolioLabParams } | { ok: false; error: string } {
  const num = (text: string, name: string): number | string => {
    const v = text.trim() === "" ? NaN : Number(text);
    return Number.isFinite(v) ? v : `${name}: יש להזין מספר`;
  };
  const fields = {
    initial: num(form.initial, "סכום התחלתי"), monthly: num(form.monthly, "הפקדה חודשית"), years: num(form.years, "מספר שנים"),
    ret: num(form.returnPct, "תשואה"), fee: num(form.feePct, "דמי ניהול"), infl: num(form.inflationPct, "אינפלציה"),
  };
  for (const v of Object.values(fields)) if (typeof v === "string") return { ok: false, error: v };
  const f = fields as Record<keyof typeof fields, number>;
  if (!Number.isInteger(f.years)) return { ok: false, error: "מספר שנים: יש להזין מספר שלם" };
  const strategies = form.strategies.length ? form.strategies : [form.baseline];
  const params: PortfolioLabParams = {
    initial: f.initial, monthly_contribution: f.monthly, years: f.years, annual_return_pct: f.ret, annual_fee_pct: f.fee,
    inflation_pct: f.infl, deposit_timing: form.timing, index_contributions: form.indexed, baseline: form.baseline, strategies,
  };
  if (form.crisisOn) {
    const year = num(form.crisisYear, "שנת המשבר");
    if (typeof year === "string") return { ok: false, error: year };
    params.crisis = { decline_pct: Number(form.crisisDecline), year, recovery: form.crisisRecovery };
    if (form.crisisMonth !== "") params.crisis.month = Number(form.crisisMonth);
  }
  if (form.compareOn) {
    const override: NonNullable<PortfolioLabParams["compare_to"]> = {};
    const entries: [string, keyof typeof override, string][] = [
      [form.cmpMonthly, "monthly_contribution", "הפקדה חודשית (סט ב׳)"], [form.cmpReturnPct, "annual_return_pct", "תשואה (סט ב׳)"],
      [form.cmpFeePct, "annual_fee_pct", "דמי ניהול (סט ב׳)"], [form.cmpInflationPct, "inflation_pct", "אינפלציה (סט ב׳)"],
    ];
    for (const [text, key, name] of entries) {
      if (text.trim() === "") continue;
      const v = num(text, name);
      if (typeof v === "string") return { ok: false, error: v };
      override[key] = v;
    }
    if (Object.keys(override).length === 0) return { ok: false, error: "השוואת תרחישים: יש למלא לפחות הנחה אחת בסט ב׳" };
    params.compare_to = override;
  }
  return { ok: true, params };
}

// ── KPI cards / table cells (labels + formatting only) ──
export const pct = (fraction: number | null | undefined, digits = 2): string =>
  fraction == null || !Number.isFinite(fraction) ? "—" : `${(fraction * 100).toFixed(digits)}%`;
export const ils = (value: number | null | undefined): string => (value == null || !Number.isFinite(value) ? "—" : money(value));

export function labKpiCards(view: PortfolioLabView): { key: string; label: string; value: string; hint?: string }[] {
  const k = view.kpis;
  return [
    { key: "final_nominal", label: "שווי סופי נומינלי", value: ils(k.final_nominal) },
    { key: "final_real", label: "שווי סופי ריאלי", value: ils(k.final_real) },
    { key: "contributions", label: "סך הפקדות", value: ils(k.contributions) },
    { key: "nominal_profit", label: "רווח נומינלי", value: ils(k.nominal_profit) },
    { key: "real_profit", label: "רווח ריאלי", value: ils(k.real_profit) },
    { key: "fees", label: "דמי ניהול ששולמו", value: ils(k.management_fees_paid) },
    { key: "cost_impact", label: "השפעה כוללת של העלויות", value: ils(k.total_cost_impact) },
    { key: "net_return", label: "תשואה שנתית אפקטיבית נטו", value: pct(k.net_effective_annual_return) },
    { key: "after_tax", label: "שווי אחרי מס", value: k.after_tax.display ?? ils(k.after_tax.value), hint: k.after_tax.note },
  ];
}

export function labTableRows(view: PortfolioLabView): { key: string; cells: string[]; baseline: boolean }[] {
  return view.comparison_table.map((r) => ({
    key: r.strategy, baseline: r.is_baseline,
    cells: [r.is_baseline ? `${r.label} (בסיס)` : r.label, ils(r.final_nominal), ils(r.final_real), ils(r.contributions), ils(r.net_profit), ils(r.costs),
            r.is_baseline ? "—" : `${r.gap_vs_baseline > 0 ? "+" : ""}${ils(r.gap_vs_baseline)}`],
  }));
}
/** Same crisis on every compared strategy: wording of the server's by_strategy rows only (empty when no crisis was applied). */
export const CRISIS_TABLE_HEAD = ["אסטרטגיה", "שווי סופי עם משבר", "שווי סופי ריאלי", "הפרש מול ללא משבר", "פער מול בסיס"];
export function crisisTableRows(view: PortfolioLabView): { key: string; cells: string[] }[] {
  const rows = view.charts.growth.crisis.by_strategy ?? [];
  const signed = (v: number) => `${v > 0 ? "+" : ""}${ils(v)}`;
  return rows.map((r) => ({
    key: r.strategy,
    cells: [r.is_baseline ? `${r.label} (בסיס)` : r.label, ils(r.final_nominal), ils(r.final_real), signed(r.delta_vs_no_crisis), r.is_baseline ? "—" : signed(r.gap_vs_baseline)],
  }));
}
/** C3 scenario comparison: words the server's two result sets and their gap (B minus A). Neutral — no "better", no ranking. */
export const SCENARIO_TABLE_HEAD = ["מדד", "סט א׳", "סט ב׳", "פער (ב׳ פחות א׳)"];
export function scenarioRows(view: PortfolioLabView): { key: string; cells: string[] }[] {
  const c = view.charts.scenario_comparison;
  if (!c || !c.applied || !c.a || !c.b || !c.gaps_b_minus_a) return [];
  const g = c.gaps_b_minus_a;
  const sign = (v: number, f: (x: number) => string) => `${v > 0 ? "+" : ""}${f(v)}`;
  const defs: [string, keyof PlKpis, (x: number | null) => string][] = [
    ["שווי סופי נומינלי", "final_nominal", ils], ["שווי סופי ריאלי", "final_real", ils], ["סך הפקדות", "contributions", ils],
    ["רווח נומינלי", "nominal_profit", ils], ["רווח ריאלי", "real_profit", ils], ["דמי ניהול ששולמו", "management_fees_paid", ils],
    ["השפעה כוללת של העלויות", "total_cost_impact", ils], ["תשואה שנתית אפקטיבית נטו", "net_effective_annual_return", (x) => pct(x)],
  ];
  return defs.map(([label, key, fmt]) => ({
    key, cells: [label, fmt(c.a!.kpis[key] as number), fmt(c.b!.kpis[key] as number), sign(g[key] as number, (x) => fmt(x))],
  }));
}
export function scenarioLines(view: PortfolioLabView) {
  const c = view.charts.scenario_comparison;
  if (!c || !c.applied || !c.a || !c.b) return [];
  return [
    { name: "סט הנחות א׳ (נומינלי)", pts: c.a.series.map((r): [number, number] => [r.year, r.nominal]) },
    { name: "סט הנחות ב׳ (נומינלי)", pts: c.b.series.map((r): [number, number] => [r.year, r.nominal]), color: CHART_COLORS[1] },
  ];
}
/** Intra-year crisis (server's numbers): the same crisis in each month of the year, and the monthly path around it. Empty for an annual crisis. */
export const TIMING_TABLE_HEAD = ["חודש המשבר", "שווי סופי נומינלי", "שווי סופי ריאלי", "הפרש מול ללא משבר"];
export function timingRows(view: PortfolioLabView): { key: number; selected: boolean; cells: string[] }[] {
  const rows = view.charts.growth.crisis.intra_year?.timing_by_month ?? [];
  return rows.map((r) => ({
    key: r.month, selected: r.is_selected,
    cells: [r.is_selected ? `${r.month} (נבחר)` : String(r.month), ils(r.final_nominal), ils(r.final_real), `${r.delta_vs_no_crisis > 0 ? "+" : ""}${ils(r.delta_vs_no_crisis)}`],
  }));
}
export function intraYearLines(view: PortfolioLabView) {
  const path = view.charts.growth.crisis.intra_year?.monthly_path ?? [];
  return [
    { name: "ללא משבר", pts: path.map((r): [number, number] => [r.t_years, r.nominal_no_crisis]) },
    { name: "עם משבר (תרחיש)", pts: path.map((r): [number, number] => [r.t_years, r.nominal_crisis]), color: CHART_COLORS[4] },
  ];
}
// ── C4: actual accumulation pace vs the plan. Wording/formatting of the server's numbers only; a missing value is "חסר", never 0. ──
export const MISSING_LABEL = "חסר";
/** The pace view shares the lab's typed assumptions (return / fee / inflation); null when the form has an invalid number (the pace call then omits them and the server defaults apply). */
export function paceAssumptions(form: LabForm): { annual_return_pct: number; annual_fee_pct: number; inflation_pct: number } | null {
  const parsed = labParams(form);
  return parsed.ok ? { annual_return_pct: parsed.params.annual_return_pct, annual_fee_pct: parsed.params.annual_fee_pct, inflation_pct: parsed.params.inflation_pct } : null;
}
export const PACE_MISSING_REASONS: Record<string, string> = {
  planned_monthly_deposit: "הפקדה חודשית מתוכננת", expected_return: "תשואה צפויה", management_fee: "דמי ניהול", deposit_events: "אירועי הפקדה",
};
export const PACE_STATUS_LABELS: Record<PaceAccountRow["status"], string> = {
  no_snapshot: "אין יתרה מדווחת", single_snapshot: "יתרה אחת בלבד — אין נקודת השוואה", short_period: "פחות מחודש בין היתרות", compared: "מושווה לתוכנית",
};
export const PACE_RETURN_REASONS: Record<string, string> = {
  period_too_short: "התקופה קצרה מ-30 יום — לא ניתן לחשב תשואה", start_balance_not_positive: "יתרת הפתיחה אפס — לא ניתן לחשב תשואה",
  undefined_denominator: "התנועות גדולות מהיתרה — לא ניתן לחשב תשואה", not_computed_consolidated: "אין תשואה מאוחדת מדויקת",
};
export const PACE_CORRECTION_REASONS: Record<string, string> = {
  no_documented_flows: "אין תנועות מתועדות — אי אפשר להסיק קצב בפועל", negative_net_flow_not_modelled: "משיכות נטו — המנוע אינו מדמה משיכות, לא מוצג קו",
  no_actual_pace: "אין קצב בפועל", no_forecast: "אין תחזית",
};
const orMissing = (value: number | null | undefined, f: (x: number) => string = ils) => (value == null ? MISSING_LABEL : f(value));
const signed = (v: number | null | undefined) => (v == null ? MISSING_LABEL : v < 0 ? `-${ils(-v)}` : `${v > 0 ? "+" : ""}${ils(v)}`);

/** The return as shown: an exact number is never shown — only a marked range, or the reason it cannot be computed. */
export function paceReturnText(r: NonNullable<PaceAccountRow["return"]>): string {
  if (r.status !== "approximate_range" || !r.range) return PACE_RETURN_REASONS[r.status] ?? "לא ניתן לחשב תשואה מדויקת";
  const range = `${pct(r.range.low)} עד ${pct(r.range.high)} לתקופה`;
  const annual = r.annualized_range ? ` · שנתי משוער ${pct(r.annualized_range.low)} עד ${pct(r.annualized_range.high)}` : "";
  return `טווח משוער: ${range}${annual} (לא ניתן לחשב תשואה מדויקת; ייתכנו תנועות שלא תועדו)`;
}
export const PACE_SUMMARY_HEAD = ["מדד", "ערך"];
export function paceSummaryRows(view: PaceView): { key: string; cells: string[] }[] {
  const c = view.consolidated;
  if (!c.deviation || c.latest_balance == null) return [];
  const flows = c.flows;
  return [
    { key: "planned", cells: ["הון שהיה אמור להצטבר (בתאריך ההשוואה)", orMissing(c.planned?.value_at_comparison)] },
    { key: "actual", cells: ["הון מדווח בפועל (יתרות אחרונות)", orMissing(c.latest_balance)] },
    { key: "deviation", cells: ["סטייה מהתוכנית", signed(c.deviation.vs_plan)] },
    { key: "deviation_deposits", cells: ["סטייה מהפקדות בלבד (ללא תשואה)", signed(c.deviation.vs_deposits_only)] },
    { key: "planned_deposits", cells: ["הפקדות שתוכננו", orMissing(c.planned?.deposits_total)] },
    { key: "actual_deposits", cells: ["הפקדות שתועדו", flows?.deposits_complete ? orMissing(flows.deposits) : `${MISSING_LABEL} (חשבון ללא אירועי הפקדה)`] },
    { key: "deposits_gap", cells: ["פער הפקדות (תועד פחות תוכנן)", flows?.deposits_complete ? signed(c.deviation.deposits_gap) : MISSING_LABEL] },
    { key: "value_change", cells: ["שינוי שווי בתקופה", signed(c.value_change?.total)] },
    { key: "documented", cells: ["תנועות מתועדות נטו", signed(c.value_change?.documented_flows)] },
    { key: "unexplained", cells: ["שינוי שאינו מוסבר (תשואה + תנועות שלא תועדו)", signed(c.value_change?.unexplained)] },
  ];
}
export const PACE_ACCOUNT_HEAD = ["חשבון", "מצב", "יתרה אחרונה", "מתוכנן", "סטייה", "תשואה"];
export function paceAccountRows(view: PaceView): { key: string; cells: string[]; missing: string }[] {
  return view.accounts.map((a) => ({
    key: a.id,
    cells: [a.name ?? a.id, PACE_STATUS_LABELS[a.status],
            a.latest_balance ? `${ils(a.latest_balance.value)} (${a.latest_balance.as_of})` : MISSING_LABEL,
            a.planned ? ils(a.planned.value_at_comparison) : MISSING_LABEL, a.deviation ? signed(a.deviation.vs_plan) : MISSING_LABEL,
            a.return ? paceReturnText(a.return) : MISSING_LABEL],
    missing: a.missing.map((m) => PACE_MISSING_REASONS[m] ?? m).join(", "),
  }));
}
export function paceForecastLines(view: PaceView) {
  const l = view.forecast.lines;
  if (!view.forecast.applied || !l) return [];
  const out: { name: string; pts: [number, number][]; color?: string; dash?: string }[] = [];
  if (l.planned_pace) out.push({ name: "קצב מתוכנן", pts: l.planned_pace.series.map((r): [number, number] => [r.year, r.nominal]) });
  if (l.actual_pace) out.push({ name: "קצב בפועל (אקסטרפולציה)", pts: l.actual_pace.series.map((r): [number, number] => [r.year, r.nominal]), color: CHART_COLORS[1], dash: "4 3" });
  if (l.goal_history_pace) out.push({ name: "ממוצע הפקדות ביעד (אקסטרפולציה)", pts: l.goal_history_pace.series.map((r): [number, number] => [r.year, r.nominal]), color: CHART_COLORS[3], dash: "2 3" });
  return out;
}
export const PACE_CORRECTION_HEAD = ["שינוי בהפקדה החודשית", "הפקדה חודשית כוללת", "שווי בסוף האופק", "הפרש מהתחזית המעודכנת"];
export function paceCorrectionRows(view: PaceView): { key: number; cells: string[] }[] {
  const c = view.course_correction;
  if (!c.applied || !c.rows) return [];
  return c.rows.map((r) => [r.monthly_change, r] as const).map(([k, r]) => ({
    key: k, cells: [signed(r.monthly_change), ils(r.monthly_deposit), ils(r.final_nominal), signed(r.delta_vs_updated_forecast)],
  }));
}
export const LAB_TABLE_HEAD = ["אסטרטגיה", "שווי סופי", "שווי ריאלי", "סך הפקדות", "רווח נטו", "עלויות", "פער מול בסיס"];

// ── Chart geometry: pure scaling of numbers the server already produced (no financial calculation) ──
export const CHART = { w: 520, h: 280, l: 58, r: 12, t: 12, b: 34 } as const;
export const CHART_COLORS = ["#1f5fbf", "#d9822b", "#2a9d8f", "#9b59b6", "#c0392b"];

export const compact = (v: number): string =>
  Math.abs(v) >= 1e6 ? `${(v / 1e6).toFixed(1)}M` : Math.abs(v) >= 1e3 ? `${(v / 1e3).toFixed(0)}K` : String(Math.round(v));

interface Tick { pos: number; label: string }
export interface LineModel { name: string; color: string; dash?: string; points: string; dots: { x: number; y: number }[] }
export interface LineChartModel { yTicks: Tick[]; xTicks: Tick[]; lines: LineModel[] }

export function lineChartModel(lines: { name: string; pts: [number, number][]; color?: string; dash?: string }[]): LineChartModel {
  const iw = CHART.w - CHART.l - CHART.r, ih = CHART.h - CHART.t - CHART.b;
  const xs = lines.flatMap((l) => l.pts.map((p) => p[0])), ys = lines.flatMap((l) => l.pts.map((p) => p[1]));
  const xmin = Math.min(...xs), xmax = Math.max(...xs), ymax = (Math.max(...ys) || 1) * 1.05;
  const x = (v: number) => CHART.l + (iw * (v - xmin)) / (xmax - xmin || 1);
  const y = (v: number) => CHART.t + ih - (ih * v) / ymax;
  return {
    yTicks: [0, 1, 2, 3, 4].map((i) => ({ pos: y((ymax * i) / 4), label: compact((ymax * i) / 4) })),
    xTicks: [0, 1, 2, 3, 4].map((i) => ({ pos: CHART.l + (iw * i) / 4, label: String(Math.round(xmin + ((xmax - xmin) * i) / 4)) })),
    lines: lines.map((l, i) => ({
      name: l.name, color: l.color ?? CHART_COLORS[i % CHART_COLORS.length], dash: l.dash,
      points: l.pts.map((p) => `${x(p[0]).toFixed(1)},${y(p[1]).toFixed(1)}`).join(" "),
      dots: l.pts.length <= 12 ? l.pts.map((p) => ({ x: x(p[0]), y: y(p[1]) })) : [],
    })),
  };
}

export interface BarChartModel { yTicks: Tick[]; groups: { label: string; x: number; bars: { x: number; y: number; w: number; h: number; color: string }[] }[]; legend: { name: string; color: string }[] }
export function barChartModel(labels: string[], series: { name: string; values: number[]; color: string }[]): BarChartModel {
  const iw = CHART.w - CHART.l - CHART.r, ih = CHART.h - CHART.t - CHART.b;
  const ymax = (Math.max(...series.flatMap((s) => s.values)) || 1) * 1.05;
  const gw = iw / labels.length, bw = (gw * 0.7) / series.length;
  return {
    yTicks: [0, 1, 2, 3, 4].map((i) => ({ pos: CHART.t + ih - (ih * i) / 4, label: compact((ymax * i) / 4) })),
    groups: labels.map((label, i) => ({
      label, x: CHART.l + gw * (i + 0.5),
      bars: series.map((s, j) => { const h = (ih * s.values[i]) / ymax; return { x: CHART.l + gw * i + gw * 0.15 + bw * j, y: CHART.t + ih - h, w: bw, h, color: s.color }; }),
    })),
    legend: series.map((s) => ({ name: s.name, color: s.color })),
  };
}

export function breakdownParts(view: PortfolioLabView): { name: string; value: number; share: number; color: string }[] {
  const b = view.charts.breakdown;
  return [
    { name: "הפקדות", value: b.contributions, share: b.shares.contributions, color: CHART_COLORS[0] },
    { name: "רווח נטו", value: b.profit_net, share: b.shares.profit_net, color: CHART_COLORS[2] },
    { name: "עלויות", value: b.costs, share: b.shares.costs, color: CHART_COLORS[4] },
  ];
}

export function growthLines(view: PortfolioLabView) {
  const g = view.charts.growth;
  const lines: { name: string; pts: [number, number][]; color?: string; dash?: string }[] = [
    { name: "נומינלי", pts: g.series.map((r) => [r.year, r.nominal]) },
    { name: "ריאלי", pts: g.series.map((r) => [r.year, r.real]), color: CHART_COLORS[2] },
    { name: "הפקדות מצטברות", pts: g.series.map((r) => [r.year, r.contributions]), color: "#8892a0", dash: "4 3" },
  ];
  if (g.crisis.applied && g.crisis.series) lines.push({ name: "נומינלי עם משבר (תרחיש)", pts: g.crisis.series.map((r) => [r.year, r.nominal]), color: CHART_COLORS[4] });
  return lines;
}
export const comparisonLines = (view: PortfolioLabView) =>
  Object.entries(view.charts.strategy_comparison).map(([id, rows]) => ({ name: view.labels.strategies[id] ?? id, pts: rows.map((r): [number, number] => [r.year, r.nominal]) }));


// ── Goal Funding Planner (step 1b): typed options -> POST /api/fcc/funding/plan -> a neutral comparison. Presentation only: the page converts typed
// text to numbers once on submit; every figure it shows (amounts, dates, certainty, costs) is the server's. No ranking, no "best", no total of "available". ──
/** Step 4: the label of the follow-up task offered per saved option type (display only — the task title itself is fixed on the server). */
export const FUNDING_FOLLOWUP_LABELS: Record<FundingOptionType, string> = {
  existing_balance: "אישור נגישות הכסף הקיים",
  new_deposits: "הגדרת הפקדה חודשית קבועה",
  asset_sale: "בירור שווי נטו ומועד מכירה",
  loan: "בקשת הצעת הלוואה",
  work_income: "הגדרת מקור הכנסה ייעודי",
  receivable_collection: "הסדרת מועד גבייה בכתב",
  obligations_reduction: "בדיקת צמצום התחייבות",
  custom: "ביצוע האפשרות שנבחרה",
};
export const FUNDING_FOLLOWUP_NOTE = "משימת המשך נפתחת כטיוטה בלבד — תוצג סקירה ורק אחרי ״אשר ורשום״ היא נוצרת. לא נוצרת פעולה אחרת.";
export const FUNDING_WINDOW_NOTE = "התאריך הוא הערכה: כל אפשרות מוצגת גם בקצה המוקדם וגם בקצה המאוחר של החלון. אף תאריך לא נבחר עבורך.";
export const FUNDING_SAVE_NOTE = "שמירה היא רישום של החלטה בלבד: היא לא מזיזה כסף, לא פותחת הלוואה או חשבון, לא מוכרת נכס ולא משנה הקצאות. השרת יחשב את התוכנית מחדש ויציג סקירה לפני כל רישום.";
export const FUNDING_TITLE = "מימון יעד";
export const FUNDING_INTRO = "בוחרים יעד, מוסיפים דרכים אפשריות למימון, והמערכת משווה ביניהן. זו השוואה בלבד — לא המלצה ולא בחירה עבורך, וכל המספרים מחושבים בשרת.";
export const FUNDING_PRINCIPLE = "כסף צפוי אינו כסף קיים: חוב שחייבים לך או חיסכון עתידי מוצגים עם רמת ודאות ותנאים, ולא מצטרפים לסכום אחד של \"כסף זמין\".";

export const FUNDING_TYPE_LABELS: Record<FundingOptionType, string> = {
  existing_balance: "כסף קיים (הקצאות)", new_deposits: "הפקדות חדשות", asset_sale: "מכירת נכס", loan: "הלוואה", work_income: "הכנסה מעבודה",
  receivable_collection: "גביית חוב שחייבים לי", obligations_reduction: "צמצום התחייבויות חוזרות", custom: "אפשרות מותאמת",
};
export const FUNDING_CERTAINTY_LABELS: Record<FundingCertainty, string> = { confirmed: "מאושר", expected: "צפוי", uncertain: "לא ודאי", unknown: "לא ידוע" };
const FEASIBLE_LABELS: Record<string, string> = { true: "אפשרי עד התאריך", false: "לא אפשרי", unknown: "לא ידוע" };
const FUNDING_REASONS: Record<string, string> = {
  no_allocation: "אין הקצאה למטרה הזו", over_allocated: "חשבון מזין בהקצאת יתר", not_accessible_by_due: "לא נגיש עד תאריך היעד",
  allocation_not_yet_effective: "ההקצאה טרם נכנסה לתוקף", allocation_effective_after_due: "ההקצאה נכנסת לתוקף אחרי תאריך היעד", no_coverage_basis: "חסר סכום או תאריך יעד",
  release_not_verified: "תאריך השחרור הגיע אך הזכאות לא אומתה", liquidity_unverified: "נזילות לא אומתה", liquidity_unknown: "חסרה נזילות",
  unreachable_under_assumptions: "לא ניתן להשגה לפי ההנחות", available_after_due: "הכסף זמין אחרי תאריך היעד", no_arrangement: "אין הסדר החזר רשום",
  no_flagged_obligations: "אין התחייבויות שסומנו לצמצום", savings_not_confirmed: "החיסכון טרם אושר", income_not_confirmed: "ההכנסה הנוספת טרם אושרה",
  based_on_missing: "חסרה אפשרות הפקדות לחישוב", based_on_not_feasible: "אפשרות ההפקדות אינה אפשרית", available_by_missing: "חסר תאריך זמינות",
};
const NEED_REASONS: Record<string, string> = {
  missing_target: "חסר סכום יעד", missing_date: "חסר תאריך יעד", past_date: "תאריך היעד עבר", beyond_horizon: "מעבר לאופק החישוב",
  due_this_month: "תאריך היעד בחודש הנוכחי, לפני סופו", parent_goal_rollup_not_supported: "מטרת אב עם מטרות־משנה — עדיין לא נתמכת", already_covered: "היעד כבר מכוסה בכסף מאושר",
};
const FUNDING_RISKS: Record<string, string> = {
  not_accessible_by_due: "לא נגיש עד התאריך", timing_uncertain: "מועד לא ודאי", debt_overlap_unresolved: "חוב על הנכס עלול להיספר פעמיים — לא נפתר", lost_income: "הכנסה מהנכס תיעלם",
  collateral_growth_not_modeled: "צמיחת הביטחון לא מחושבת", terms_unverified: "התנאים לא אומתו", unreachable_under_assumptions: "לא ניתן להשגה לפי ההנחות",
  allocated_elsewhere: "הכסף הנגיש כבר מוקצה למטרות אחרות", over_committed_pool: "הקצאת יתר", depends_on_assumed_return: "תלוי בתשואה שהונחה",
  self_reported_balance: "יתרה בדיווח עצמי", event_allocation_overlap: "יש גם הפקדות שדווחו וגם הקצאה — לא נספרו יחד", receivable_no_arrangement: "אין הסדר החזר",
  release_not_verified: "זכאות לשחרור לא אומתה", parent_goal_rollup_not_supported: "מטרת אב לא נתמכת",
};
const FUNDING_CONDITIONS: Record<string, string> = {
  owner_confirms_deposits: "הבעלים מאשר את ההפקדות", liquid_from_reached: "מגיע תאריך השחרור", release_rules_confirmed: "כללי השחרור אושרו", liquidity_verified: "הנזילות אומתה",
  growth_as_assumed: "הצמיחה כפי שהונחה", loan_approved: "ההלוואה אושרה", sale_closes: "המכירה נסגרת", buyer_found: "נמצא קונה", debtor_arrangement: "נקבע הסדר עם החייב",
  debtor_pays_on_schedule: "החייב משלם לפי הלוח", owner_confirms_savings: "הבעלים מאשר את החיסכון", extra_income_available: "קיימת הכנסה נוספת",
};
const MISSING_INPUT_LABELS: Record<string, string> = { liquidity: "נזילות", goal_allocation: "הקצאה למטרה", target_amount: "סכום יעד", end_date: "תאריך יעד", available_by: "תאריך זמינות", based_on: "אפשרות הפקדות", management_fee: "דמי ניהול", expected_return: "תשואה צפויה", deposit_fee: "דמי ניהול מההפקדה" };
/** An unknown code is shown as it is (never hidden), so a new server code can never silently disappear from the page. */
const word = (dict: Record<string, string>, code: string): string => dict[code] ?? code;

export type FundingFieldKind = "number" | "date" | "text" | "bool" | "select";
export interface FundingField { key: string; label: string; kind: FundingFieldKind; required?: boolean; hint?: string; options?: { value: string; label: string }[]; optionsFrom?: "accounts" | "assets" | "receivables" | "deposit_options"; when?: (v: Record<string, string>) => boolean }
const T_ASSET_NONE = { value: "", label: "ללא נכס מזוהה" };
export const FUNDING_FIELDS: Record<Exclude<FundingOptionType, "existing_balance">, FundingField[]> = {
  new_deposits: [
    { key: "source", label: "מקור ההנחות", kind: "select", required: true, options: [{ value: "hypothetical", label: "חשבון חדש (הנחות שאזין)" }, { value: "account", label: "חשבון קיים" }] },
    { key: "account_id", label: "חשבון", kind: "select", required: true, optionsFrom: "accounts", when: (v) => v.source === "account" },
    { key: "liquidity", label: "נזילות", kind: "select", required: true, options: [{ value: "immediate", label: "נזיל מיד" }, { value: "date", label: "נפתח בתאריך שחרור" }], when: (v) => v.source !== "account" },
    { key: "liquid_from", label: "תאריך שחרור", kind: "date", required: true, when: (v) => v.source !== "account" && v.liquidity === "date" },
    { key: "expected_return_pct", label: "תשואה שנתית צפויה (%)", kind: "number", when: (v) => v.source !== "account" },
    { key: "fee_pct", label: "דמי ניהול שנתיים (%)", kind: "number", when: (v) => v.source !== "account" },
    { key: "deposit_fee_pct", label: "דמי ניהול מההפקדה (%)", kind: "number", when: (v) => v.source !== "account" },
    { key: "release_confirmed", label: "אני מאשר שכללי השחרור מאפשרים משיכה בתאריך", kind: "bool" },
  ],
  asset_sale: [
    { key: "asset_id", label: "נכס", kind: "select", optionsFrom: "assets" },
    { key: "net_proceeds", label: "תמורה נטו צפויה (₪)", kind: "number", required: true, hint: "אחרי עלויות ומס, כפי שאתה מעריך" },
    { key: "expected_date", label: "תאריך משוער", kind: "date", required: true },
    { key: "confirmed_buyer", label: "יש קונה מאושר", kind: "bool" },
  ],
  loan: [
    { key: "amount", label: "סכום הלוואה (₪)", kind: "number", required: true },
    { key: "annual_rate_pct", label: "ריבית שנתית (%)", kind: "number", required: true },
    { key: "term_months", label: "תקופה (חודשים)", kind: "number", required: true },
    { key: "available_by", label: "תאריך קבלת הכסף", kind: "date", required: true },
    { key: "collateral", label: "ביטחון (טקסט קצר)", kind: "text" },
    { key: "approved", label: "ההלוואה אושרה", kind: "bool" },
    { key: "terms_verified", label: "התנאים אומתו מול הגוף המלווה", kind: "bool" },
  ],
  work_income: [{ key: "based_on", label: "מבוסס על אפשרות הפקדות", kind: "select", required: true, optionsFrom: "deposit_options" }],
  receivable_collection: [
    { key: "loan_id", label: "חוב שחייבים לי", kind: "select", required: true, optionsFrom: "receivables" },
    { key: "expected_net", label: "סכום צפוי להיגבות (₪)", kind: "number", required: true },
    { key: "expected_date", label: "תאריך משוער", kind: "date", required: true },
  ],
  obligations_reduction: [{ key: "monthly_amount", label: "חיסכון חודשי (₪, ריק = לפי התחייבויות שסומנו)", kind: "number" }],
  custom: [
    { key: "label", label: "שם", kind: "text", required: true },
    { key: "amount", label: "סכום (₪)", kind: "number", required: true },
    { key: "available_by", label: "תאריך זמינות", kind: "date" },
    { key: "monthly_cost", label: "עלות חודשית (₪)", kind: "number" },
    { key: "one_time_cost", label: "עלות חד־פעמית (₪)", kind: "number" },
    { key: "certainty", label: "רמת ודאות", kind: "select", options: [{ value: "", label: "ברירת מחדל" }, { value: "expected", label: "צפוי" }, { value: "uncertain", label: "לא ודאי" }] },
  ],
};
export const FUNDING_ADDABLE: Exclude<FundingOptionType, "existing_balance">[] = ["new_deposits", "asset_sale", "loan", "receivable_collection", "obligations_reduction", "work_income", "custom"];

export interface FundingOptionDraft { id: string; type: Exclude<FundingOptionType, "existing_balance">; values: Record<string, string>; use: string }
export interface FundingForm { goalId: string; marginMonths: string; returnPct: string; feePct: string; inflationPct: string; options: FundingOptionDraft[] }
export const DEFAULT_FUNDING_FORM: FundingForm = { goalId: "", marginMonths: "", returnPct: "6", feePct: "0.15", inflationPct: "2", options: [] };

/** A new draft with defaults that never invent money: only selects get a starting choice. */
export function newFundingOption(type: FundingOptionDraft["type"], counter: number): FundingOptionDraft {
  const values: Record<string, string> = {};
  if (type === "new_deposits") { values.source = "hypothetical"; values.liquidity = "immediate"; }
  return { id: `${type}_${counter}`, type, values, use: "" };
}

const isBlank = (t: string | undefined) => t == null || t.trim() === "";
/** Typed text -> request body. A blank required field is an error shown on the form, never silently 0; the server re-validates everything. */
export function fundingRequest(form: FundingForm): { ok: true; body: FundingRequestBody } | { ok: false; error: string } {
  if (isBlank(form.goalId)) return { ok: false, error: "יש לבחור יעד" };
  const num = (text: string, name: string): number | string => { const v = text.trim() === "" ? NaN : Number(text); return Number.isFinite(v) ? v : `${name}: יש להזין מספר`; };
  const a = { ret: num(form.returnPct, "תשואה"), fee: num(form.feePct, "דמי ניהול"), infl: num(form.inflationPct, "אינפלציה") };
  for (const v of Object.values(a)) if (typeof v === "string") return { ok: false, error: v };
  let margin: number | undefined;
  if (!isBlank(form.marginMonths)) {                                 // typed text -> one whole number, once, on submit
    margin = Number(form.marginMonths);
    if (!Number.isInteger(margin) || margin < 0 || margin > 60) return { ok: false, error: "אי־ודאות בתאריך: יש להזין מספר חודשים שלם בין 0 ל־60" };
  }
  const options: Record<string, unknown>[] = [];
  const plan: FundingRequestBody["allocation_plan"] = [];
  for (const draft of form.options) {
    const label = FUNDING_TYPE_LABELS[draft.type];
    const out: Record<string, unknown> = { id: draft.id, type: draft.type };
    const v = draft.values;
    for (const field of FUNDING_FIELDS[draft.type]) {
      if (field.when && !field.when(v)) continue;
      const text = v[field.key];
      if (field.kind === "bool") { if (text === "true") out[field.key] = true; continue; }
      if (isBlank(text)) { if (field.required) return { ok: false, error: `${label}: ${field.label} — שדה חובה` }; continue; }
      if (field.kind === "number") { const n = Number(text); if (!Number.isFinite(n)) return { ok: false, error: `${label}: ${field.label} — יש להזין מספר` }; out[field.key] = n; }
      else out[field.key] = text.trim();
    }
    if (draft.type === "new_deposits") {                              // shape the typed form into the API's two sources
      if (v.source !== "account") {
        const hypo: Record<string, unknown> = {};
        if (v.liquidity === "immediate") hypo.immediate = true; else hypo.liquid_from = out.liquid_from;
        for (const k of ["expected_return_pct", "fee_pct", "deposit_fee_pct"]) if (k in out) hypo[k] = out[k];
        for (const k of ["source", "liquidity", "liquid_from", "expected_return_pct", "fee_pct", "deposit_fee_pct"]) delete out[k];
        out.hypothetical = hypo;
      }
      delete out.source;
    }
    options.push(out);
    if (!isBlank(draft.use)) {
      const amount = Number(draft.use);
      if (!Number.isFinite(amount) || amount <= 0) return { ok: false, error: `${label}: סכום לשימוש — יש להזין מספר חיובי` };
      plan.push({ goal_id: form.goalId, option_id: draft.id, amount });
    }
  }
  return { ok: true, body: { goal_id: form.goalId, assumptions: { annual_return_pct: a.ret as number, annual_fee_pct: a.fee as number, inflation_pct: a.infl as number }, options, allocation_plan: plan, ...(margin !== undefined ? { date_margin_months: margin } : {}) } };
}

export interface FundingOptionCard {
  id: string; type: FundingOptionType; title: string; verdict: string; feasible: boolean | "unknown"; certainty: string; rows: { label: string; value: string }[];
  lists: { label: string; items: string[] }[]; note: string;
  /** Date window: the same option at the earliest / latest date (rows are the server's numbers; empty when the date is firm). */
  windowRows: { label: string; value: string }[];
}
export interface FundingPlanModel {
  needTitle: string; needRows: { label: string; value: string }[]; needReason: string | null; windowNote: string | null; options: FundingOptionCard[];
  plan: { rows: { label: string; value: string }[]; allocations: string[]; note: string } | null;
  portfolio: { rows: { label: string; value: string }[] } | null; warnings: string[];
}
const dmy = (iso: string | null) => (iso ? iso.split("-").reverse().join("/") : "—");
const optMoney = (v: number | null | undefined) => (v == null ? "—" : money(v));

function windowCell(e: FundingWindowEnd, o: FundingWindowOption | undefined): string {
  if (e.reason) return word(NEED_REASONS, e.reason);
  if (!o) return "—";
  const parts = [`${word(FEASIBLE_LABELS, String(o.feasible))}${o.reason ? ` — ${word(FUNDING_REASONS, o.reason)}` : ""}`];
  if (o.required_monthly != null) parts.push(`הפקדה חודשית נדרשת ${money(o.required_monthly)}`);
  else if (o.covers_amount != null) parts.push(`מכסה ${money(o.covers_amount)}`);
  if (o.monthly_cash_effect != null) parts.push(`תזרים חודשי ${money(o.monthly_cash_effect)}`);
  if (o.available_by) parts.push(`זמין עד ${dmy(o.available_by)}`);
  return parts.join(" · ");
}

function optionCard(o: FundingOptionResult, titles: Record<string, string>, win?: FundingWindow | null): FundingOptionCard {
  const rows: { label: string; value: string }[] = [
    { label: "כמה מכסה", value: optMoney(o.covers_amount) },
    { label: "זמין עד", value: dmy(o.available_by) },
    { label: "השפעה על תזרים חודשי (מינוס = נטל)", value: optMoney(o.monthly_cash_effect) },
    { label: "עלות כוללת", value: optMoney(o.total_cost) },
  ];
  if (o.one_time_cost != null) rows.push({ label: "עלות חד־פעמית", value: money(o.one_time_cost) });
  if (o.new_liabilities) rows.push({ label: "התחייבות חדשה", value: `${money(o.new_liabilities.amount)} · החזר ${money(o.new_liabilities.monthly_payment)} לחודש · ${o.new_liabilities.term_months} חודשים` });
  rows.push({ label: "זמן עד מימוש", value: o.time_to_realize_months == null ? "—" : `${o.time_to_realize_months} חודשים` });
  const detailRequired = o.details && typeof o.details === "object" ? (o.details as Record<string, unknown>).required_monthly : undefined;
  if (typeof detailRequired === "number") rows.unshift({ label: "הפקדה חודשית נדרשת", value: money(detailRequired) });
  const lists = [
    { label: "תנאים למימוש", items: o.conditions.map((c) => word(FUNDING_CONDITIONS, c)) },
    { label: "סיכונים", items: o.risks.map((r) => word(FUNDING_RISKS, r)) },
    { label: "חסר", items: o.missing_inputs.map((m) => word(MISSING_INPUT_LABELS, m)) },
  ].filter((l) => l.items.length > 0);
  const verdict = `${word(FEASIBLE_LABELS, String(o.feasible))}${o.reason ? ` — ${word(FUNDING_REASONS, o.reason)}` : ""}`;
  const windowRows = win ? [
    { label: `אם התאריך מוקדם (${dmy(win.early.due)})`, value: windowCell(win.early, win.early.options.find((x) => x.id === o.id)) },
    { label: `אם התאריך מאוחר (${dmy(win.late.due)})`, value: windowCell(win.late, win.late.options.find((x) => x.id === o.id)) },
  ] : [];
  return { id: o.id, type: o.type, title: titles[o.id] ?? FUNDING_TYPE_LABELS[o.type], verdict, feasible: o.feasible, certainty: word(FUNDING_CERTAINTY_LABELS, o.certainty), rows, lists, note: o.assumptions.join(" · "), windowRows };
}

/** Wording + layout of one goal's comparison. Options keep the server's order (fixed by type); nothing is sorted, scored or highlighted here. */
export function fundingModel(plan: FundingPlan, goalId: string, titles: Record<string, string> = {}): FundingPlanModel | null {
  const g = plan.goals.find((x) => x.need.goal_id === goalId) ?? plan.goals[0];
  if (!g) return null;
  const n = g.need;
  const needRows = [
    { label: "יעד", value: optMoney(n.target) }, { label: n.date_margin_months ? "תאריך יעד (משוער)" : "תאריך יעד", value: n.date_margin_months ? `${dmy(n.due)} ± ${n.date_margin_months} חודשים` : dmy(n.due) },
    { label: "כסף קיים מאושר למטרה", value: money(n.confirmed_existing) },
    { label: "כסף קיים צפוי (לא מאושר)", value: money(n.expected_existing) },
    { label: "פער לפי הכסף המאושר בלבד", value: optMoney(n.gap) },
  ];
  const p = g.plan;
  const planModel = p ? {
    rows: [
      { label: "מאושר", value: money(p.covered.confirmed) }, { label: "צפוי", value: money(p.covered.expected) },
      { label: "לא ודאי", value: money(p.covered.uncertain) }, { label: "לא ידוע", value: money(p.covered.unknown) },
      { label: "נותר אחרי המאושר בלבד", value: money(p.remaining_after_confirmed) },
      { label: "נותר אחרי מאושר וצפוי", value: money(p.remaining_after_confirmed_and_expected) },
      { label: "נטל חודשי בתוכנית", value: money(p.monthly_burden) }, { label: "שחרור חודשי בתוכנית", value: money(p.monthly_release) },
      { label: "הזמינות המוקדמת ביותר", value: dmy(p.earliest_available_by) },
    ],
    allocations: p.allocations.map((a) => `${titles[a.option_id] ?? a.option_id}: ${money(a.amount)} · ${word(FUNDING_CERTAINTY_LABELS, a.certainty)}${a.available_by ? ` · עד ${dmy(a.available_by)}` : ""}`),
    note: p.note,
  } : null;
  const pf = plan.portfolio;
  const portfolio = pf.plan_chosen ? { rows: [
    { label: "נטל חודשי בתוכנית", value: optMoney(pf.monthly_burden_in_plan) },
    { label: "חיסכון חודשי מתוכנן", value: pf.capacity_known ? optMoney(pf.planned_monthly_savings) : "לא ידוע" },
    { label: "חוסר מול החיסכון המתוכנן", value: pf.shortfall == null ? "לא ידוע" : money(pf.shortfall) },
    ...(pf.over_committed.length ? [{ label: "מקור שהוקצה ליותר מסכומו", value: pf.over_committed.map((id) => titles[id] ?? id).join(", ") }] : []),
  ] } : null;
  return {
    needTitle: n.title || "מטרה ללא שם", needRows, needReason: n.reason ? word(NEED_REASONS, n.reason) : null,
    windowNote: g.window ? FUNDING_WINDOW_NOTE : null,
    options: g.options.map((o) => optionCard(o, titles, g.window)), plan: planModel, portfolio, warnings: plan.warnings,
  };
}


// ── Funding sources (step 2): the candidate list the server derives from the owner's own data — FIVE separate categories, never summed. Presentation
// only: every figure is the server's; a missing figure is "חסר" (never 0); nothing is ranked, scored or recommended. ──
export const SOURCES_TITLE = "מקורות אפשריים ליעד";
export const SOURCES_INTRO = "רשימת מועמדים מהנתונים שלך — לא המלצה ולא בחירה עבורך. כל קטגוריה נפרדת ואינה מצטרפת לסכום אחד של ״כסף זמין״.";
export const SOURCES_EXPECTED_LABEL = "צפוי בסוף החודש האחרון שהושלם עד תאריך היעד (לפי הנחות, לא מובטח)";
export const SOURCES_CATEGORY_ORDER: FundingSourceCategory[] = ["liquid_now", "liquid_by_due_date", "conditional_on_action", "expected_not_guaranteed", "future_deposits"];
const SOURCES_CATEGORY_TITLES: Record<FundingSourceCategory, string> = {
  liquid_now: "כסף נזיל עכשיו", liquid_by_due_date: "כסף שיהפוך לנגיש עד תאריך היעד", conditional_on_action: "מותנה בפעולה",
  expected_not_guaranteed: "צפוי ואינו מובטח", future_deposits: "הפקדות עתידיות שטרם בוצעו",
};
const SOURCES_CATEGORY_NOTES: Record<FundingSourceCategory, string> = {
  liquid_now: "חשבונות שסומנו נזילים מיד. היתרה היא הצילום האחרון שדווח.",
  liquid_by_due_date: "תאריך שחרור אינו זכאות למשיכה, ולכן חשבון עם תאריך שחרור מופיע תחת ״מותנה בפעולה״ ולא כאן. הקטגוריה ריקה כל עוד אין חשבון שיהפוך נגיש מבלי שנדרשת פעולה.",
  conditional_on_action: "כסף שנדרשת פעולה כדי להגיע אליו: מכירת נכס (תמורה ומועד מזין הבעלים), או אימות נזילות של חשבון.",
  expected_not_guaranteed: "חוב שחייבים לך. אינו חלק מהיתרה הנזילה, והגבייה אינה מובטחת.",
  future_deposits: "הפקדות מתוכננות שעדיין לא בוצעו — בנפרד מהכסף הקיים. הפקדה שכבר נכללת בתחזית אינה נוספת ליתרה.",
};
const SOURCE_TYPE_LABELS: Record<FundingSourceItem["source_type"], string> = { account: "חשבון", asset: "נכס", receivable: "חוב שחייבים לי", planned_deposit: "הפקדה מתוכננת" };
const LIQUIDITY_BASIS_LABELS: Record<string, string> = { immediate: "נזיל מיד", retirement_immediate: "מוצר פרישה", dated: "נפתח בתאריך שחרור", undated: "נעול ללא תאריך שחרור", unverified: "נזילות לא אומתה" };
const SOURCE_CONDITIONS: Record<string, string> = {
  retirement_product_not_one_time_cash: "מוצר פרישה — לא כסף חד־פעמי", liquid_from_reached_eligibility_unverified: "תאריך השחרור הגיע, אך הזכאות למשיכה לא אומתה",
  liquid_from_missing: "חסר תאריך שחרור", liquidity_unverified: "הנזילות לא אומתה", owner_decides_to_sell: "הבעלים מחליט למכור", sale_closes: "המכירה נסגרת",
  debtor_pays_on_schedule: "החייב משלם לפי הלוח", debtor_arrangement: "נקבע הסדר עם החייב", deposits_actually_made: "ההפקדות מתבצעות בפועל",
};
const SOURCE_RISKS: Record<string, string> = { over_allocated: "החשבון בהקצאת יתר", not_yet_deposited: "טרם הופקד" };
const SOURCE_MISSING: Record<string, string> = {
  balance_snapshot: "יתרה מדווחת", liquid_from: "תאריך שחרור", liquidity: "נזילות", net_proceeds: "תמורה נטו", expected_sale_date: "מועד מכירה", recorded_balance: "יתרה רשומה",
  arrangement: "הסדר החזר", goal_date: "תאריך יעד", planned_monthly_deposit: "הפקדה חודשית מתוכננת", deposit_fee: "דמי ניהול מההפקדה",
};
const BALANCE_EFFECTS: Record<string, string> = {
  uses_existing_balance: "משתמש ביתרה הקיימת של החשבון", converts_asset_to_cash: "הופך נכס למזומן (הנכס יורד מהחזקות)", converts_receivable_to_cash: "הופך חוב שחייבים לך למזומן",
  adds_future_deposits_to_account: "מוסיף הפקדות עתידיות לחשבון (עוד לא בוצעו)",
};
const OWNER_MUST_ENTER: Record<string, string> = { net_proceeds: "תמורה נטו", expected_date: "תאריך משוער", expected_net: "סכום צפוי להיגבות" };
const FORECAST_INCLUSION: Record<string, string> = { included_in_forecast: "כלול כבר בתחזית — אל תוסיפו ליתרה הקיימת", not_included: "לא כלול בתחזית" };
const SOURCE_TEMPLATE_LABELS: Record<NonNullable<FundingSourceItem["option_template"]>["type"], string> = { asset_sale: "מכירת נכס", receivable_collection: "גביית חוב", new_deposits: "הפקדות חדשות" };

export interface SourceAddOption { type: Exclude<FundingOptionType, "existing_balance">; label: string; prefill: Record<string, string>; mustEnter: string[]; key: string }
export interface SourceCard { key: string; title: string; typeLabel: string; rows: { label: string; value: string }[]; lists: { label: string; items: string[] }[]; add: SourceAddOption | null }
export interface SourceCategoryModel { key: FundingSourceCategory; title: string; note: string; count: number; cards: SourceCard[] }
export interface SourcesModel {
  title: string; reason: string | null; dueNote: string | null; categories: SourceCategoryModel[]; unavailable: SourceCard[]; gaps: string[];
  assumptions: string; warnings: string[];
}

/** The answer of a slower, older request must never overwrite the sources of the goal that is on screen now. */
export const isCurrentGoal = (currentGoalId: string, answerGoalId: string): boolean => currentGoalId !== "" && currentGoalId === answerGoalId;
export const SOURCES_DEBOUNCE_MS = 400;
/** A cached answer is reused only for the very same request (goal + margin + assumptions). */
export const sourcesCacheKey = (body: unknown): string => JSON.stringify(body);
/** One message per failure: 404 (screen off), 429 (rate limit), 503 (busy), -1 (older server, no sources in the answer), no status (network), anything else. */
export function sourcesErrorText(code?: number): string {
  if (code === 404) return "המסך עדיין לא פעיל — המקורות האפשריים אינם זמינים בחשבון הזה.";
  if (code === 429) return "יותר מדי חישובים — אפשר לנסות שוב בעוד דקה.";
  if (code === 503) return "השרת עסוק כרגע — נסו שוב בעוד רגע.";
  if (code === -1) return "השרת עדיין לא תומך ברשימת המקורות האפשריים.";
  if (code == null) return "אין חיבור לשרת — בדקו את הרשת ונסו שוב.";
  return "לא הצלחנו לטעון את המקורות האפשריים.";
}

const stateText = (st: FundingLiquidityState | null | undefined): string => (st ? word(LIQUIDITY_STATE_LABELS, st) : MISSING_LABEL);
const money0 = (n: number | null | undefined): string => (n == null ? MISSING_LABEL : money(n));

function sourceCard(item: FundingSourceItem, window: boolean): SourceCard {
  const rows: { label: string; value: string }[] = [];
  if (item.source_type === "account") {
    rows.push({ label: `יתרה מדווחת${item.as_of ? ` (נכון ל-${dmy(item.as_of)})` : ""}`, value: money0(item.amount) });
    const st = item.liquidity?.state_at;
    rows.push({ label: "נזילות עכשיו", value: stateText(st?.now) }, { label: "נזילות בתאריך היעד", value: stateText(st?.due) });
    if (window && st) rows.push({ label: "אם התאריך מוקדם", value: stateText(st.early) }, { label: "אם התאריך מאוחר", value: stateText(st.late) });
    if (item.liquidity) rows.push({ label: "סוג נזילות", value: word(LIQUIDITY_BASIS_LABELS, item.liquidity.basis) });
    const ex = item.expected_at_due;
    rows.push({ label: SOURCES_EXPECTED_LABEL, value: ex ? money0(ex.amount) : MISSING_LABEL });
    if (ex && window) rows.push({ label: "צפוי אם התאריך מוקדם / מאוחר", value: `${money0(ex.early)} / ${money0(ex.late)}` });
    if (ex?.includes_planned_deposits) rows.push({ label: "כולל הפקדה חודשית מתוכננת", value: money(ex.monthly_planned_deposit_included) });
    const al = item.allocation;
    if (al?.allocated_elsewhere) rows.push({ label: "הוקצה ליעדים אחרים", value: money0(al.allocated_elsewhere_amount) });
    if (al && al.allocated_to_this_goal) rows.push({ label: "הוקצה ליעד הזה", value: money(al.allocated_to_this_goal) });
    if (al?.allocated_elsewhere && al.amount_not_allocated_elsewhere != null) rows.push({ label: "לא מוקצה ליעדים אחרים", value: money(al.amount_not_allocated_elsewhere) });
  } else if (item.source_type === "asset") {
    const a = item.asset;
    rows.push({ label: "שווי רשום (ברוטו — לא תמורה)", value: money0(a?.recorded_value) }, { label: "אחוז בעלות", value: a?.ownership_pct == null ? MISSING_LABEL : `${a.ownership_pct}%` });
    if (a?.mortgage_balance) rows.push({ label: "יתרת משכנתא", value: money(a.mortgage_balance) });
    if (a?.linked_debt) rows.push({ label: "חוב מקושר", value: money(a.linked_debt) });
    rows.push({ label: "תמורה נטו", value: `${MISSING_LABEL} — מזין הבעלים` }, { label: "מועד מכירה", value: `${MISSING_LABEL} — ידני` });
  } else if (item.source_type === "receivable") {
    const r = item.receivable;
    rows.push({ label: "יתרה רשומה (לא סכום צפוי)", value: money0(item.amount) }, { label: "הסדר החזר", value: r?.arrangement === "monthly" ? "תשלום חודשי" : r?.arrangement === "deadline" ? "עד תאריך" : MISSING_LABEL });
    rows.push({ label: "תשלום קרוב", value: r?.next_payment_due ? dmy(r.next_payment_due) : MISSING_LABEL }, { label: "תאריך סיום", value: r?.end_date ? dmy(r.end_date) : MISSING_LABEL });
  } else {
    const d = item.deposit;
    rows.push({ label: "הפקדה חודשית מתוכננת", value: money0(d?.monthly_planned) }, { label: "חודשים עד תאריך היעד", value: d?.months_until_due == null ? MISSING_LABEL : String(d.months_until_due) });
    rows.push({ label: "סך מתוכנן עד התאריך (ללא תשואה)", value: money0(item.amount) });
    if (window && item.window) rows.push({ label: "אם התאריך מוקדם / מאוחר", value: `${money0(item.window.early.amount)} / ${money0(item.window.late.amount)}` });
    rows.push({ label: "נזילות החשבון בתאריך היעד", value: stateText(d?.state_at.due) });
    if (item.forecast_inclusion) rows.push({ label: "ספירה בתחזית", value: word(FORECAST_INCLUSION, item.forecast_inclusion) });
  }
  if (item.balance_effect) rows.push({ label: "השפעה על יתרת ההון", value: word(BALANCE_EFFECTS, item.balance_effect) });
  const lists = [
    { label: "תנאים", items: item.conditions.map((c) => word(SOURCE_CONDITIONS, c)) },
    { label: "סיכונים", items: item.risks.map((r) => word({ ...FUNDING_RISKS, ...SOURCE_RISKS }, r)) },
    { label: "חסר", items: item.missing_inputs.map((m) => word(SOURCE_MISSING, m)) },
  ].filter((l) => l.items.length > 0);
  const t = item.option_template;
  const prefill: Record<string, string> = {};
  if (t?.type === "asset_sale" && t.asset_id) prefill.asset_id = t.asset_id;
  if (t?.type === "receivable_collection" && t.loan_id) prefill.loan_id = t.loan_id;
  if (t?.type === "new_deposits" && t.account_id) { prefill.source = "account"; prefill.account_id = t.account_id; }
  const add = t ? { type: t.type, label: SOURCE_TEMPLATE_LABELS[t.type], prefill, mustEnter: item.owner_must_enter.map((k) => word(OWNER_MUST_ENTER, k)), key: `${t.type}:${t.asset_id ?? t.loan_id ?? t.account_id ?? ""}` } : null;
  return { key: `${item.source_type}:${item.source_id}`, title: item.name || "ללא שם", typeLabel: SOURCE_TYPE_LABELS[item.source_type], rows, lists, add };
}

/** Wording + layout of one goal's candidate sources. Categories keep the fixed order; items keep the server's order (by type, then name). No totals. */
export function sourcesModel(src: FundingSources, goalId: string): SourcesModel | null {
  const g = src.goals.find((x) => x.goal_id === goalId) ?? src.goals[0];
  if (!g) return null;
  const window = g.date_window != null;
  const a = src.assumptions;
  return {
    title: g.title || "מטרה ללא שם",
    reason: g.reason ? word(NEED_REASONS, g.reason) : null,
    dueNote: window ? `תאריך היעד משוער (± ${g.date_window?.margin_months} חודשים): ${dmy(g.date_window?.early ?? null)} – ${dmy(g.date_window?.late ?? null)}. אף תאריך לא נבחר עבורך.` : null,
    categories: SOURCES_CATEGORY_ORDER.map((key) => ({ key, title: SOURCES_CATEGORY_TITLES[key], note: SOURCES_CATEGORY_NOTES[key], count: g.categories[key].length, cards: g.categories[key].map((i) => sourceCard(i, window)) })),
    unavailable: g.not_available_by_due_date.map((i) => sourceCard(i, window)),
    gaps: g.gaps.future_deposits.map((x) => `${x.name || "חשבון ללא שם"}: חסר ${x.missing.map((m) => word(SOURCE_MISSING, m)).join(", ")}`),
    assumptions: `הנחות ל״צפוי״: תשואה ${a.annual_return_pct}% · דמי ניהול ${a.annual_fee_pct}% · אינפלציה ${a.inflation_pct}% — ערכים שהוזנו בחשבון עצמו גוברים עליהן.`,
    warnings: src.warnings,
  };
}
