// Plain node + esbuild test (see package.json `npm test`).
import { schedulePreviewModel, NO_MATCH } from "./fccLoanSchedule";

const assert = {
  equal(actual: unknown, expected: unknown, message?: string) { if (actual !== expected) throw new Error(message ?? `expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`); },
  ok(v: unknown, message?: string) { if (!v) throw new Error(message ?? "expected truthy"); },
};
let failures = 0;
function test(name: string, fn: () => void) { try { fn(); console.log(`ok - ${name}`); } catch (error) { failures += 1; console.error(`FAIL - ${name}`); console.error(error); } }

const base = { state: "preview" as const, original: 30000, payment_now: 393.78, payments_left: 85, interest_left: 6679.28, ends: "2033-11-15", digest: "d",
  this_month: { principal: 247.86, interest: 144.45, total: 392.31, balance_after: 26419.06, charged: false } };

test("one matching loan -> can save, no choice, the month's exact split is shown", () => {
  const m = schedulePreviewModel({ ...base, candidates: [{ id: "a", name: "מקס", lender: "מקס", has_schedule: false }] });
  assert.ok(m.canSave && !m.needsChoice && m.problems.length === 0);
  assert.ok(m.lines.some((l) => l.includes("ריבית") && l.includes("קרן")) && m.lines.some((l) => l.includes("85 תשלומים")));
});
test("several candidates -> the owner chooses; an existing schedule is flagged as replaced", () => {
  const m = schedulePreviewModel({ ...base, candidates: [{ id: "a", name: "א", lender: null, has_schedule: true }, { id: "b", name: "ב", lender: null, has_schedule: false }] });
  assert.ok(m.needsChoice && m.candidates[0].label.includes("יוחלף"));
});
test("no candidate -> nothing to save and the reason is stated; a rejected file shows its problems", () => {
  const none = schedulePreviewModel({ ...base, candidates: [] });
  assert.equal(none.canSave, false);
  assert.equal(none.problems[0], NO_MATCH);
  const bad = schedulePreviewModel({ state: "rejected", problems: ["היתרה בסוף הלוח אינה אפס"] });
  assert.equal(bad.canSave, false);
  assert.equal(bad.problems[0], "היתרה בסוף הלוח אינה אפס");
});
if (failures > 0) throw new Error(`${failures} test(s) failed`);
console.log("all fccLoanSchedule tests passed");
