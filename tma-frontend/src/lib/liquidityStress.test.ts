// Plain node + esbuild test (see package.json `npm test`). E1d: liquidity stress presentation.
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { LiquidityStressPanel, StressResult } from "../components/LiquidityStressPanel";
import type { StressView } from "../types";
import { DEFAULT_STRESS_FORM, burnRows, stressHead, stressParams, stressRows } from "./liquidityStress";

const assert = {
  equal(actual: unknown, expected: unknown, message?: string) {
    if (actual !== expected) throw new Error(message ?? `expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
  },
  ok(v: unknown, message?: string) { if (!v) throw new Error(message ?? "expected truthy"); },
};
let failures = 0;
function test(name: string, fn: () => void) {
  try { fn(); console.log(`ok - ${name}`); } catch (e) { failures += 1; console.error(`FAIL - ${name}: ${(e as Error).message}`); }
}

// Real server output (portfolio_lab.liquidity_stress.build_stress_view, 6 months, 900K loan @7%, max LTV 45%, 40% crisis in month 1).
const FIXTURE = {"schema_version": "1.0", "result_type": "stress_scenario_under_stated_assumptions", "engine_version": "1.0.0", "inputs_echo": {"fund_value": 3000000.0, "phase": "withdrawal", "deposit": 8000.0, "support": 10000.0, "other_expenses": 0.0, "other_income": 0.0, "annual_return": 0.08, "annual_fee": 0.0015, "inflation": 0.02, "cash_return": 0.0, "horizon": 6, "crisis": {"decline": 0.4, "start_month": 1, "recovery_years": 2}, "cushion_months": [0, 12, 24], "reserved": {"pledged": 0.0, "family_earmarked": 0.0}}, "loan": {"principal": 900000.0, "annual_rate_pct": 7.0, "interest_only": true, "term_months": null, "first_month_interest": 5250.0, "first_month_principal_repayment": 0.0, "max_ltv_pct": 45.0, "max_ltv_source": "owner_entered", "terms_verified": false, "collateral": "risky_and_pledged", "cure_order": ["cushion", "risky_sale"], "proceeds": {"kind": "none", "monthly_income": 0.0, "asset_value": 0.0, "note": "תמורת ההלוואה הוצאה ללא תשואה: מוסיפה חוב בלי נכס."}}, "net_burn": {"components": {"support": 10000.0, "other_expenses": 0.0, "loan_interest": 5250.0, "loan_repayments": 0.0, "less_other_income": -0.0, "less_asset_income": -0.0, "less_deposits": -8000.0}, "net_burn_per_month": 7250.0, "basis": "net_burn"}, "protected_capital": {"amount": 0.0, "separation": "hard", "note": "הון הילדים מופרד: אינו חלק מהקרן, אינו בטוחה ואינו מממן הפסדים; לא נכלל בחישוב."}, "modes": [{"cushion_months": 0, "label": "ללא כרית", "free_cushion": 0.0, "months_of_support_covered": 0.0, "events": {"collateral_call": {"count": 1, "first_month": 1, "total_amount": 169752.4, "events": [{"month": 1, "amount": 169752.4, "debt": 900000.0, "collateral": 1792524.85, "cured_from_free_cash": 0.0, "cured_from_risky_sale": 169752.4, "unresolved": 0.0, "ltv": 0.5021}], "events_truncated": false, "status": "evaluated", "unresolved_count": 0}, "forced_sale": {"count": 7, "first_month": 1, "total_amount": 208301.29, "events": [{"month": 1, "amount": 7250.0, "units": 12084.84, "price_index": 0.6, "cause": "cashflow"}, {"month": 1, "amount": 169752.4, "units": 282956.06, "price_index": 0.6, "cause": "collateral_call"}, {"month": 2, "amount": 6259.78, "units": 10147.78, "price_index": 0.62, "cause": "cashflow"}, {"month": 3, "amount": 6259.78, "units": 9869.17, "price_index": 0.63, "cause": "cashflow"}, {"month": 4, "amount": 6259.78, "units": 9598.2, "price_index": 0.65, "cause": "cashflow"}, {"month": 5, "amount": 6259.78, "units": 9334.67, "price_index": 0.67, "cause": "cashflow"}, {"month": 6, "amount": 6259.78, "units": 9078.38, "price_index": 0.69, "cause": "cashflow"}], "events_truncated": false}, "cash_shortfall": {"count": 0, "first_month": null, "total_amount": 0, "events": [], "events_truncated": false}}, "forced_sale_by_cause": {"cashflow": 38548.89, "collateral_call": 169752.4}, "initial_collateral": 3000000.0, "initial_ltv": 0.3, "trigger_decline_pct": 33.33, "cushion_exhausted_month": null, "window_24m": {"months": 24, "from_month": 1, "to_month": 6, "forced_sale_free": false, "shortfall_free": true, "collateral_call_free": false}, "final_net_value": 1832022.79, "final_real_value": 1813972.86, "final_debt": 730247.6, "final_net_worth": 1101775.19, "final_net_worth_real": 1090919.99, "max_ltv": 0.5021, "delta_vs_no_crisis": -1069385.31, "series": [{"month": 1, "risky": 1622772.45, "free_cash": 0.0, "reserved_cash": 0.0, "total": 1622772.45, "debt": 730247.6, "ltv": 0.5021, "net_worth": 892524.85}, {"month": 2, "risky": 1662325.33, "free_cash": 0.0, "reserved_cash": 0.0, "total": 1662325.33, "debt": 730247.6, "ltv": 0.4393, "net_worth": 932077.73}, {"month": 3, "risky": 1702994.83, "free_cash": 0.0, "reserved_cash": 0.0, "total": 1702994.83, "debt": 730247.6, "ltv": 0.4288, "net_worth": 972747.23}, {"month": 4, "risky": 1744812.48, "free_cash": 0.0, "reserved_cash": 0.0, "total": 1744812.48, "debt": 730247.6, "ltv": 0.4185, "net_worth": 1014564.88}, {"month": 5, "risky": 1787810.69, "free_cash": 0.0, "reserved_cash": 0.0, "total": 1787810.69, "debt": 730247.6, "ltv": 0.4085, "net_worth": 1057563.09}, {"month": 6, "risky": 1832022.79, "free_cash": 0.0, "reserved_cash": 0.0, "total": 1832022.79, "debt": 730247.6, "ltv": 0.3986, "net_worth": 1101775.19}]}, {"cushion_months": 12, "label": "12 חודשי תזרים נטו", "free_cushion": 87000.0, "months_of_support_covered": 8.7, "events": {"collateral_call": {"count": 1, "first_month": 1, "total_amount": 141274.33, "events": [{"month": 1, "amount": 141274.33, "debt": 900000.0, "collateral": 1747581.37, "cured_from_free_cash": 79750.0, "cured_from_risky_sale": 61524.33, "unresolved": 0.0, "ltv": 0.515}], "events_truncated": false, "status": "evaluated", "unresolved_count": 0}, "forced_sale": {"count": 6, "first_month": 1, "total_amount": 93653.83, "events": [{"month": 1, "amount": 61524.33, "units": 102553.38, "price_index": 0.6, "cause": "collateral_call"}, {"month": 2, "amount": 6425.9, "units": 10417.09, "price_index": 0.62, "cause": "cashflow"}, {"month": 3, "amount": 6425.9, "units": 10131.08, "price_index": 0.63, "cause": "cashflow"}, {"month": 4, "amount": 6425.9, "units": 9852.92, "price_index": 0.65, "cause": "cashflow"}, {"month": 5, "amount": 6425.9, "units": 9582.4, "price_index": 0.67, "cause": "cashflow"}, {"month": 6, "amount": 6425.9, "units": 9319.3, "price_index": 0.69, "cause": "cashflow"}], "events_truncated": false}, "cash_shortfall": {"count": 0, "first_month": null, "total_amount": 0, "events": [], "events_truncated": false}}, "forced_sale_by_cause": {"cashflow": 32129.5, "collateral_call": 61524.33}, "initial_collateral": 2913000.0, "initial_ltv": 0.309, "trigger_decline_pct": 31.34, "cushion_exhausted_month": 2, "window_24m": {"months": 24, "from_month": 1, "to_month": 6, "forced_sale_free": false, "shortfall_free": true, "collateral_call_free": false}, "final_net_value": 1903880.32, "final_real_value": 1885122.42, "final_debt": 758725.67, "final_net_worth": 1145154.65, "final_net_worth_real": 1133872.07, "max_ltv": 0.515, "delta_vs_no_crisis": -1023352.44, "series": [{"month": 1, "risky": 1686057.04, "free_cash": 0.0, "reserved_cash": 0.0, "total": 1686057.04, "debt": 758725.67, "ltv": 0.515, "net_worth": 927331.37}, {"month": 2, "risky": 1727230.4, "free_cash": 0.0, "reserved_cash": 0.0, "total": 1727230.4, "debt": 758725.67, "ltv": 0.4393, "net_worth": 968504.73}, {"month": 3, "risky": 1769566.13, "free_cash": 0.0, "reserved_cash": 0.0, "total": 1769566.13, "debt": 758725.67, "ltv": 0.4288, "net_worth": 1010840.45}, {"month": 4, "risky": 1813097.03, "free_cash": 0.0, "reserved_cash": 0.0, "total": 1813097.03, "debt": 758725.67, "ltv": 0.4185, "net_worth": 1054371.36}, {"month": 5, "risky": 1857856.87, "free_cash": 0.0, "reserved_cash": 0.0, "total": 1857856.87, "debt": 758725.67, "ltv": 0.4084, "net_worth": 1099131.2}, {"month": 6, "risky": 1903880.32, "free_cash": 0.0, "reserved_cash": 0.0, "total": 1903880.32, "debt": 758725.67, "ltv": 0.3985, "net_worth": 1145154.65}]}, {"cushion_months": 24, "label": "24 חודשי תזרים נטו", "free_cushion": 174000.0, "months_of_support_covered": 17.4, "events": {"collateral_call": {"count": 1, "first_month": 1, "total_amount": 137075.44, "events": [{"month": 1, "amount": 137075.44, "debt": 900000.0, "collateral": 1695387.9, "cured_from_free_cash": 137075.44, "cured_from_risky_sale": 0.0, "unresolved": 0.0, "ltv": 0.5309}], "events_truncated": false, "status": "evaluated", "unresolved_count": 0}, "forced_sale": {"count": 1, "first_month": 6, "total_amount": 2577.41, "events": [{"month": 6, "amount": 2577.41, "units": 3737.94, "price_index": 0.69, "cause": "cashflow"}], "events_truncated": false}, "cash_shortfall": {"count": 0, "first_month": null, "total_amount": 0, "events": [], "events_truncated": false}}, "forced_sale_by_cause": {"cashflow": 2577.41, "collateral_call": 0}, "initial_collateral": 2826000.0, "initial_ltv": 0.3185, "trigger_decline_pct": 29.23, "cushion_exhausted_month": 6, "window_24m": {"months": 24, "from_month": 1, "to_month": 6, "forced_sale_free": false, "shortfall_free": true, "collateral_call_free": false}, "final_net_value": 1946022.91, "final_real_value": 1926849.81, "final_debt": 762924.56, "final_net_worth": 1183098.36, "final_net_worth_real": 1171441.93, "max_ltv": 0.5309, "delta_vs_no_crisis": -982063.52, "series": [{"month": 1, "risky": 1695387.9, "free_cash": 29674.56, "reserved_cash": 0.0, "total": 1725062.46, "debt": 762924.56, "ltv": 0.5309, "net_worth": 962137.9}, {"month": 2, "risky": 1743250.58, "free_cash": 23224.16, "reserved_cash": 0.0, "total": 1766474.74, "debt": 762924.56, "ltv": 0.4376, "net_worth": 1003550.19}, {"month": 3, "risky": 1792464.47, "free_cash": 16773.77, "reserved_cash": 0.0, "total": 1809238.24, "debt": 762924.56, "ltv": 0.4256, "net_worth": 1046313.69}, {"month": 4, "risky": 1843067.73, "free_cash": 10323.38, "reserved_cash": 0.0, "total": 1853391.1, "debt": 762924.56, "ltv": 0.4139, "net_worth": 1090466.55}, {"month": 5, "risky": 1895099.57, "free_cash": 3872.98, "reserved_cash": 0.0, "total": 1898972.55, "debt": 762924.56, "ltv": 0.4026, "net_worth": 1136047.99}, {"month": 6, "risky": 1946022.91, "free_cash": 0.0, "reserved_cash": 0.0, "total": 1946022.91, "debt": 762924.56, "ltv": 0.392, "net_worth": 1183098.36}]}], "notes": ["תרחיש לפי הנחות שהוזנו; אין כאן הערכת סיכוי, המלצה או תנאי בנק מאומתים.", "מכירה כפויה: מכירת נכס סיכון לצורך תזרים או לתיקון דרישת בטוחות (שדה cause). מחסור במזומן: אין מזומן חופשי ואין נכס סיכון שמכסה את התזרים. דרישת בטוחות: LTV חרג מהסף שהוזן. שלושתם אירועים נפרדים.", "כרית נמדדת לפי תזרים נטו (כולל ריבית ופירעונות בחודש הראשון). מזומן חופשי מכסה תזרים ותיקון בטוחות אך אינו נספר כבטוחה; מזומן משועבד נספר כבטוחה ואינו מממן; מזומן מיועד להתחייבויות משפחתיות אינו מממן דבר.", "ללא מס, ללא אינפלציה בתזרים (סכומים נומינליים קבועים).", "תנאי ההלוואה (סף LTV, ריבית) הוזנו ידנית ולא אומתו מול בנק.", "הלוואה בריבית בלבד: הקרן אינה נפרעת באופק והיתרה מנוכה בשווי הנקי."], "replay_digest": "e8c69f1b24496bbea48df3141778671492f33b34ad0383a5709be31a09175bdc"} as unknown as StressView;

test("the default form builds the research request: cushions 0/12/24, crisis on, no loan", () => {
  const r = stressParams(DEFAULT_STRESS_FORM);
  assert.ok(r.ok);
  if (!r.ok) return;
  assert.equal(JSON.stringify(r.params.cushion_modes), "[0,12,24]");
  assert.equal(r.params.crisis?.decline_pct, 40);
  assert.ok(!("loan" in r.params));
  assert.equal(r.params.protected_capital.amount, 0);
});

test("the max LTV has no default: a loan without it is refused before any request", () => {
  const r = stressParams({ ...DEFAULT_STRESS_FORM, loanOn: true });
  assert.ok(!r.ok && r.error.includes("אין ברירת מחדל"));
});

test("a loan request carries the owner's own terms; an amortizing loan needs a term; cure order follows the choice", () => {
  const base = { ...DEFAULT_STRESS_FORM, loanOn: true, loanMaxLtv: "45" };
  const a = stressParams(base);
  assert.ok(a.ok && a.params.loan?.max_ltv_pct === 45 && a.params.loan?.terms_verified === false && a.params.loan?.interest_only === true);
  assert.ok(a.ok && a.params.loan?.cure_order[0] === "cushion");
  assert.ok(!stressParams({ ...base, loanInterestOnly: false }).ok);
  const amort = stressParams({ ...base, loanInterestOnly: false, loanTerm: "120", cureFirst: "risky_sale", proceeds: "asset_income", proceedsIncome: "3000", proceedsValue: "900000" });
  assert.ok(amort.ok && amort.params.loan?.term_months === 120 && amort.params.loan?.cure_order[0] === "risky_sale");
  assert.ok(amort.ok && JSON.stringify(amort.params.loan?.use_proceeds) === JSON.stringify({ kind: "asset_income", monthly_income: 3000, asset_value: 900000 }));
});

test("crisis off sends no crisis; bad numbers are refused with a Hebrew message", () => {
  const off = stressParams({ ...DEFAULT_STRESS_FORM, crisisOn: false });
  assert.ok(off.ok && !("crisis" in off.params));
  for (const bad of [{ fundValue: "" }, { fundValue: "abc" }, { horizonMonths: "1.5" }, { horizonMonths: "999" }, { crisisDecline: "95" }, { deposit: "-1" }]) {
    const r = stressParams({ ...DEFAULT_STRESS_FORM, ...bad });
    assert.ok(!r.ok && /[֐-׿]/.test(r.error), JSON.stringify(bad));
  }
});

test("the three events are three separate rows and are never merged", () => {
  const rows = stressRows(FIXTURE);
  const labels = rows.map((r) => r.label);
  assert.ok(labels.includes("אירוע: דרישת בטוחות") && labels.includes("אירוע: מכירה כפויה") && labels.includes("אירוע: מחסור במזומן"));
  assert.equal(rows.find((r) => r.key === "call")!.cells.length, 3);
  assert.equal(stressHead(FIXTURE).length, 4);
  assert.ok(labels.includes("ירידה שמפעילה דרישת בטוחות (%)"), "loan rows appear when there is a loan");
});

test("without a loan the collateral call reads as not applicable and the loan rows are absent", () => {
  const noLoan = { ...FIXTURE, loan: null, modes: FIXTURE.modes.map((m) => ({ ...m, events: { ...m.events, collateral_call: { status: "not_applicable_no_loan", count: 0, first_month: null, total_amount: 0, events: [], events_truncated: false } } })) } as StressView;
  const rows = stressRows(noLoan);
  assert.ok(rows.find((r) => r.key === "call")!.cells[0].includes("אין הלוואה"));
  assert.ok(!rows.some((r) => r.key === "trigger"));
});

test("the result renders in Hebrew with no raw server codes, no forbidden wording and the child-capital separation", () => {
  const html = renderToStaticMarkup(createElement(StressResult, { view: FIXTURE }));
  assert.ok(html.includes("הון הילדים מופרד"));
  assert.ok(html.includes("תזרים נטו נדרש בחודש"));
  const visible = html.replace(/digest[^<]*/, "").replace(/סוג תוצאה: [^·<]*/, "");
  assert.ok(!/not_applicable|stress_scenario|risky_|collateral_call|cash_shortfall|forced_sale/.test(visible), "raw codes leaked");
  assert.ok(!/probabilit|success.?rate|chance|recommend|סיכוי להצליח|הסתברות/i.test(html));
  assert.ok(burnRows(FIXTURE).some((r) => r.key === "loan_interest"));
});

test("the panel renders the form, the not-a-forecast note and the child-capital rule", () => {
  const html = renderToStaticMarkup(createElement(LiquidityStressPanel));
  assert.ok(html.includes("מבחן לחץ נזילות") && html.includes("לא תחזית ולא המלצה") && html.includes("הון הילדים מופרד"));
  assert.ok(!html.includes("סף LTV"), "loan fields stay hidden until the loan is chosen");
  assert.ok(html.includes("הרץ מבחן לחץ"));
});

if (failures > 0) throw new Error(`${failures} liquidityStress test(s) failed`);
console.log("all liquidityStress tests passed");
