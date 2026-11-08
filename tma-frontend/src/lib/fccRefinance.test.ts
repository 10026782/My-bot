// Plain node + esbuild test (see package.json `npm test`).
import type { FccRefinance, FccRefinanceRow } from "../types";
import { REFINANCE_HOW, monthRows, offerBody, refinanceModel, rowModel, totalsGroups, totalsLines, yearRows } from "./fccRefinance";

const assert = {
  equal(actual: unknown, expected: unknown, message?: string) { if (actual !== expected) throw new Error(message ?? `expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`); },
  ok(v: unknown, message?: string) { if (!v) throw new Error(message ?? "expected truthy"); },
};
let failures = 0;
function test(name: string, fn: () => void) { try { fn(); console.log(`ok - ${name}`); } catch (error) { failures += 1; console.error(`FAIL - ${name}`); console.error(error); } }

const row = (o: Partial<FccRefinanceRow>): FccRefinanceRow => ({ id: "a", name: "מקס", balance: 40000, rate: 12, payment: 1000, months: 48, interest_left: 8000, exact: false, prepay_fee: 0, fee_known: true, payoff_now: 40000,
  same_term_payment: 939, same_term_interest: 5091, net_saving: 2909, interest_share: 0.167, full_term_interest: 13000, full_term_net: -5000,
  offer_payment: 450, monthly_relief: 550, relief_cost: 5000, relief_cost_per_100: 909, verdict: "worth", reason: null, ...o });
const totals = { loans: 1, balance: 40000, current_payment: 1000, current_interest_left: 8000, one_time_costs: 3000, offer_payment: 450, offer_interest: 14000, monthly_saving: 550,
  total_saving_offer_term: -9000, same_term_months: 48, same_term_payment: 939, same_term_interest: 5091, total_saving_same_term: -91, payback_months: 6, any_unknown_fee: false, uses_estimates: true,
  estimated_loans: ["מקס"], debt_ahead: [{ years: 1, keep: 31000, same_pace: 30500, stretch: 39000 }, { years: 5, keep: 0, same_pace: 0, stretch: 33000 }],
  timeline: { months: 24, years: [
    { year: 1, keep: { payment: 12000, interest: 3000, principal: 9000, debt_end: 31000 }, same_pace: { payment: 11268, interest: 2200, principal: 9068, debt_end: 30932 }, stretch: { payment: 5400, interest: 2300, principal: 3100, debt_end: 36900 }, diff_same_pace: 732, diff_stretch: 6600, cum_diff_same_pace: 732, cum_diff_stretch: 6600 },
    { year: 2, keep: { payment: 0, interest: 0, principal: 0, debt_end: 0 }, same_pace: { payment: 0, interest: 0, principal: 0, debt_end: 0 }, stretch: { payment: 5400, interest: 2200, principal: 3200, debt_end: 33700 }, diff_same_pace: 0, diff_stretch: -5400, cum_diff_same_pace: 732, cum_diff_stretch: 1200 }] },
  monthly: [{ month: 1, keep: [1000, 100, 900], same_pace: [939, 80, 859], stretch: [450, 190, 260] }, { month: 49, keep: [0, 0, 0], same_pace: [0, 0, 0], stretch: [450, 150, 300] }] };

test("offer input: required rate and term, blank costs are 0, bad numbers are refused with a message", () => {
  const ok = offerBody({ rate: "5.5", years: "10", fees: "", insurance: "" }, null, {});
  assert.ok("body" in ok && ok.body.term_months === 120 && ok.body.fees === 0 && !("loan_ids" in ok.body));
  assert.ok("error" in offerBody({ rate: "", years: "10", fees: "", insurance: "" }, null, {}));
  assert.ok("error" in offerBody({ rate: "50", years: "10", fees: "", insurance: "" }, null, {}));
  assert.ok("error" in offerBody({ rate: "5", years: "0", fees: "", insurance: "" }, null, {}));
  assert.ok("error" in offerBody({ rate: "5", years: "10", fees: "-3", insurance: "" }, null, {}));
  const sel = offerBody({ rate: "5", years: "10", fees: "100", insurance: "20" }, ["a"], { a: "250", b: "x" });
  assert.ok("body" in sel && sel.body.loan_ids?.[0] === "a" && sel.body.fee_overrides?.a === 250 && !("b" in (sel.body.fee_overrides ?? {})));
});

test("totals in three separate readings: a saving, the monthly relief (never a saving) and the debt left; nothing is a bare percent", () => {
  const groups = totalsGroups(totals);
  assert.equal(groups.map((g) => g.title).join("|"), "חיסכון בריבית ובעלויות|הקלה בהחזר החודשי|כמה חוב יישאר");
  const flat = totalsLines(totals);
  const get = (l: string) => flat.find((x) => x.label.startsWith(l))!;
  assert.ok(get("ההחזר החודשי בפריסה").value.startsWith("יורד ב-") && get("ההחזר החודשי בפריסה").tone === "good");
  assert.ok(get("אם תמשיך לשלם כמו היום").value.includes("יותר") && get("אם תפרוס לכל התקופה").value.includes("יותר") && get("אם תפרוס לכל התקופה").tone === "bad");
  assert.ok(groups[1].hint!.includes("לא חיסכון") && groups[0].lines.every((l) => l.label !== "ההחזר החודשי בפריסה"));      // the relief line is not inside the savings group
  assert.equal(get("העלויות החד-פעמיות חוזרות אחרי").value, "6 חודשים");
  assert.equal(totalsLines({ ...totals, payback_months: null }).find((x) => x.label.startsWith("העלויות החד-פעמיות חוזרות"))!.value, "לא הוגדר");
  assert.ok(groups[2].lines[0].label === "אחרי 1 שנים" && groups[2].lines[0].value.includes("פריסה"));
  assert.ok(!flat.some((l) => l.value.includes("%") || l.label.includes("%")));
});

test("the year-by-year table is on one axis: years after the original loans ended show 0 for today and a negative difference", () => {
  const rows = yearRows(totals);
  assert.equal(rows.length, 2);
  assert.equal(rows[0].tone, "good"); assert.ok(rows[0].diff.startsWith("+"));
  assert.equal(rows[1].today, "₪0"); assert.ok(rows[1].diff.startsWith("-"));
  const months = monthRows(totals);
  assert.equal(months[0].today.pay, "₪1,000"); assert.ok(months[0].today.split.includes("ריבית") && months[0].today.split.includes("קרן"));      // two lines: the payment, then its interest and principal
  assert.equal(months[1].today.pay, "—"); assert.equal(months[1].today.split, ""); assert.ok(months[1].stretch.split.includes("קרן"));
  assert.equal(monthRows({ ...totals, monthly: undefined }).length, 0);
});

test("row: the interest ahead is in shekels, two before/after tables, the relief in two shekel figures, the fee box only when the fee is unknown", () => {
  const w = rowModel(row({ same_term_payment: 939, same_term_interest: 5091, offer_payment: 450, full_term_interest: 13000 }));
  assert.equal(w.verdict, "כדאי למחזר"); assert.equal(w.tone, "good"); assert.equal(w.needsFee, false);
  assert.ok(w.facts.some((f) => f.includes("תשלם עוד") && f.includes("ריבית") && f.includes("48 חודשים") && f.includes("הערכה, לא לוח מהבנק")));
  assert.ok(w.facts.some((f) => f.startsWith("לפרוע הכל היום") && f.includes("ללא עמלה")));
  assert.ok(rowModel(row({ payoff_now: 10150, balance: 10000 })).facts.some((f) => f.includes("+ עמלה")));
  assert.ok(rowModel(row({ payoff_now: null })).facts.some((f) => f.endsWith("+ עמלה (לא ידועה)")));
  assert.ok(rowModel(row({ exact: true })).facts.some((f) => f.includes("לפי לוח הבנק")));
  assert.ok(!w.facts.some((f) => f.includes("%  ") || f.includes("מהתשלומים")));
  assert.equal(w.tables.map((t) => t.title).join("|"), "אם תמשיך לשלם כמו היום|אם תפרוס לכל התקופה");
  const keep = w.tables[0].rows, stretch = w.tables[1].rows;
  assert.equal(keep.map((r) => r.label).join(), "החזר חודשי,ריבית עד הסוף,סה״כ לתשלום");
  assert.equal(keep[1].tone, "good"); assert.ok(keep[1].diff.startsWith("-"));            // the same pace saves interest
  assert.equal(stretch[0].tone, "good"); assert.equal(stretch[1].tone, "bad"); assert.ok(stretch[1].diff.startsWith("+"));   // the long term lowers the payment and costs interest
  assert.ok(w.reliefLine!.includes("ההחזר יורד ב-") && w.reliefLine!.includes("יותר ריבית"));
  assert.ok(!w.reliefLine!.includes("₪100"));
  const u = rowModel(row({ verdict: "unknown_fee", reason: "לא ידועה עמלת הפירעון" }));
  assert.ok(u.needsFee && u.tone === "muted" && u.reason === "לא ידועה עמלת הפירעון");
  const m = rowModel(row({ verdict: "missing", balance: null, interest_left: null, net_saving: null, interest_share: null, full_term_net: null, monthly_relief: null, same_term_payment: null, offer_payment: null, reason: "חסרים נתונים" }));
  assert.equal(m.tables.length, 0); assert.equal(m.reliefLine, null);
  assert.equal(rowModel(row({ monthly_relief: -20, relief_cost: 100 })).reliefLine, "במשכנתא ההחזר החודשי על ההלוואה הזו לא יורד.");
});

test("model: names the recommended loans and says when refinancing does not pay", () => {
  const r: FccRefinance = { offer: { rate: 6, term_months: 120, fees: 3000, insurance_monthly: 0 }, rows: [row({}), row({ id: "b", name: "כאל", verdict: "not_worth" })],
    selected_ids: ["a", "b"], selected: totals, recommended_ids: ["a"], recommended: totals, recommended_pays: false, notes: ["n"] };
  const m = refinanceModel(r);
  assert.equal(m.recommendedPays, false); assert.equal(m.recommendedNames.join(","), "מקס"); assert.equal(m.rows.length, 2); assert.equal(m.notes[0], "n");
  const withRelief = refinanceModel({ ...r, relief_ids: ["b", "a"], relief: totals });
  assert.equal(withRelief.reliefNames.join(","), "כאל,מקס"); assert.ok(withRelief.relief !== null);
  assert.equal(refinanceModel({ ...r, recommended: null, recommended_ids: [] }).recommended, null);
});
test("the explanation is plain: no formula symbols, and it names both scenarios", () => {
  assert.ok(REFINANCE_HOW.length >= 5 && REFINANCE_HOW.some((h) => h.includes("אם תמשיך לשלם כמו היום")) && REFINANCE_HOW.some((h) => h.includes("אם תפרוס לכל התקופה")));
  assert.ok(!REFINANCE_HOW.some((h) => /[=×÷]/.test(h.replace("ריבית שנשארה =", ""))));
});
if (failures > 0) throw new Error(`${failures} test(s) failed`);
console.log("all fccRefinance tests passed");
