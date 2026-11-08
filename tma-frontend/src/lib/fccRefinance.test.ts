// Plain node + esbuild test (see package.json `npm test`).
import type { FccRefinance, FccRefinanceRow } from "../types";
import { offerBody, refinanceModel, rowModel, totalsLines } from "./fccRefinance";

const assert = {
  equal(actual: unknown, expected: unknown, message?: string) { if (actual !== expected) throw new Error(message ?? `expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`); },
  ok(v: unknown, message?: string) { if (!v) throw new Error(message ?? "expected truthy"); },
};
let failures = 0;
function test(name: string, fn: () => void) { try { fn(); console.log(`ok - ${name}`); } catch (error) { failures += 1; console.error(`FAIL - ${name}`); console.error(error); } }

const row = (o: Partial<FccRefinanceRow>): FccRefinanceRow => ({ id: "a", name: "מקס", balance: 40000, rate: 12, payment: 1000, months: 48, interest_left: 8000, exact: false, prepay_fee: 0, fee_known: true,
  same_term_payment: 939, same_term_interest: 5091, net_saving: 2909, interest_share: 0.167, full_term_interest: 13000, full_term_net: -5000,
  offer_payment: 450, monthly_relief: 550, relief_cost: 5000, relief_cost_per_100: 909, verdict: "worth", reason: null, ...o });
const totals = { loans: 1, balance: 40000, current_payment: 1000, current_interest_left: 8000, one_time_costs: 3000, offer_payment: 450, offer_interest: 14000, monthly_saving: 550,
  total_saving_offer_term: -9000, same_term_months: 48, same_term_payment: 939, same_term_interest: 5091, total_saving_same_term: -91, payback_months: 6, any_unknown_fee: false, uses_estimates: true };

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

test("totals: a lower payment is not shown as a saving when the total costs more; both comparisons are present", () => {
  const lines = totalsLines(totals);
  const get = (l: string) => lines.find((x) => x.label.startsWith(l))!;
  assert.ok(get("הפרש בהחזר").value.startsWith("יורד") && get("הפרש בהחזר").tone === "good");
  assert.ok(get("סה״כ בתקופת ההצעה").value.startsWith("מייקר") && get("סה״כ בתקופת ההצעה").tone === "bad");
  assert.ok(get("סה״כ באותו טווח").value.startsWith("מייקר"));
  assert.equal(get("החזר העלויות").value, "6 חודשים");
  assert.equal(totalsLines({ ...totals, payback_months: null }).find((x) => x.label === "החזר העלויות")!.value, "לא הוגדר");
});

test("row: verdicts, estimate marker, and the fee input appears only when the fee is unknown", () => {
  const w = rowModel(row({}));
  assert.equal(w.verdict, "כדאי לכלול"); assert.equal(w.tone, "good"); assert.ok(w.lines.some((l) => l.includes("(הערכה)"))); assert.equal(w.needsFee, false);
  assert.ok(w.lines.some((l) => l.includes("17% מהתשלומים שנותרו הם ריבית")) && w.lines.some((l) => l.includes("לכל תקופת המשכנתא: מייקר")));
  assert.ok(w.lines.some((l) => l.includes("הקלה בהחזר החודשי") && l.includes("מחיר ההקלה")));
  assert.ok(rowModel(row({ monthly_relief: -20, relief_cost_per_100: null })).lines.includes("אין הקלה בהחזר החודשי"));
  const near = rowModel(row({ verdict: "not_worth", net_saving: 22, interest_share: 0.018, reason: "רוב הריבית כבר שולמה" }));
  assert.ok(near.lines.some((l) => l.startsWith("2% מהתשלומים")) && near.lines.includes("רוב הריבית כבר שולמה") && near.tone === "bad");
  const u = rowModel(row({ verdict: "unknown_fee", reason: "עמלת הפירעון לא ידועה" }));
  assert.ok(u.needsFee && u.tone === "muted");
  const m = rowModel(row({ verdict: "missing", balance: null, interest_left: null, net_saving: null, interest_share: null, full_term_net: null, monthly_relief: null, reason: "חסרים יתרה" }));
  assert.equal(m.lines.length, 1);
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
if (failures > 0) throw new Error(`${failures} test(s) failed`);
console.log("all fccRefinance tests passed");
