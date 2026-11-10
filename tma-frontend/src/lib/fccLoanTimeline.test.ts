import { timelineModel, monthLabel, TIMELINE_SCOPES } from "./fccLoanTimeline";
import type { FccLoanTimeline, FccTimelineScope } from "../types";

let failures = 0;
const assert = { equal: (a: unknown, b: unknown) => { if (a !== b) throw new Error(`expected ${String(b)}, got ${String(a)}`); }, ok: (v: unknown) => { if (!v) throw new Error("not ok"); } };
function test(name: string, fn: () => void) { try { fn(); console.log(`ok - ${name}`); } catch (e) { failures++; console.error(`not ok - ${name}: ${(e as Error).message}`); } }

const scope: FccTimelineScope = {
  loans: 8, of: 10, exact: 6, balance: 393097, payment_now: 9326, interest_now: 2647, share_now: 0.284, first_month: "2026-11", last_month: "2033-11",
  interest_remaining: 91072, interest_remaining_exact: 76715, interest_remaining_estimated: 14357,
  drops: [{ month: "2027-02", from: 9338, to: 7824, drop: 1514, interest: 2497, ended: ["מקס קטן א", "מקס קטן ב"] }],
  thresholds: [{ limit: 0.25, first: "2028-05", sustained: "2028-05", payment: 7824, interest: 1950 }, { limit: 0.1, first: "2031-05", sustained: "2032-02", payment: 2165, interest: 210 }, { limit: 0.02, first: "2033-11", sustained: null, payment: null, interest: null }],
  yearly: [{ month: "2026-11", payment: 9326, interest: 2647, share: 0.284 }],
};
const t: FccLoanTimeline = { no_mortgage: scope, all: null, assumption: "מניח ריבית של היום" };

test("month label and scopes", () => { assert.equal(monthLabel("2028-05"), "05/2028"); assert.equal(TIMELINE_SCOPES.length, 2); });

test("timeline model: summary, drops, thresholds, yearly, hint — and empty scopes", () => {
  const m = timelineModel(t, "no_mortgage")!;
  assert.equal(m.summary.length, 5);
  assert.ok(m.summary[2].value.includes("28%") && m.summary[3].value.startsWith("≈"));
  assert.ok(m.drops[0].title.startsWith("02/2027") && m.drops[0].detail.includes("מקס קטן א"));
  assert.ok(m.thresholds[0].title.includes("25%") && m.thresholds[0].detail.startsWith("מ-05/2028"));
  assert.ok(m.thresholds[1].detail.includes("כבר ב-05/2031"));
  assert.ok(m.thresholds[2].detail.includes("לזמן קצר בלבד"));
  assert.equal(m.yearly[0].share, "28%");
  assert.ok(m.hint!.includes("8 מתוך 10"));
  assert.equal(timelineModel(t, "all"), null);
  assert.equal(timelineModel(undefined, "all"), null);
});

if (failures) throw new Error(`${failures} fccLoanTimeline test(s) failed`);
console.log("all fccLoanTimeline tests passed");
