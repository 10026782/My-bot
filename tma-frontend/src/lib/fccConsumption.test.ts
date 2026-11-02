// Plain node + esbuild test (see package.json `npm test`). Wording only: the client does no financial arithmetic.
import type { FccConsumption, FccConsumptionMonth } from "../types";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { ConsumptionView } from "../components/FccConsumption";
import { consumptionModel, defaultConsumptionMonth } from "./fccConsumption";

const assert = {
  equal(actual: unknown, expected: unknown, message?: string) {
    if (actual !== expected) throw new Error(message ?? `expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
  },
  ok(v: unknown, message?: string) { if (!v) throw new Error(message ?? "expected truthy"); },
};
let failures = 0;
function test(name: string, fn: () => void) {
  try { fn(); console.log(`ok - ${name}`); } catch (error) { failures += 1; console.error(`FAIL - ${name}`); console.error(error); }
}

const month = (key: string, over: Partial<FccConsumptionMonth> = {}): FccConsumptionMonth => ({
  month: key, is_current: false, partial: false, installments: 0,
  expenses: { known: true, count: 3, categories: [{ key: "living", label: "מחייה", amount: 3000 }, { key: "leisure", label: "פנאי ובילויים", amount: 1000 }], total: 4000 }, ...over,
});
const data: FccConsumption = {
  months: [month("2026-07", { expenses: { known: false, count: 0, categories: [], total: null } }), month("2026-08"), month("2026-09", { installments: 450 }),
           month("2026-10", { is_current: true, partial: true })],
  categories: [], as_of: "2026-10-20",
  insights: { changes: null, spikes: [{ month: "2026-09", key: "leisure", label: "פנאי ובילויים", amount: 1000, baseline: 400, excess: 600, partial: false }], large_items: [] },
};

test("default month: the latest complete month with expenses; newest first in the list", () => {
  assert.equal(defaultConsumptionMonth(data), "2026-09");
  assert.equal(consumptionModel(data).rows[0].month, "2026-10");
});

test("the detail words the totals, the bar share and the instalments line; a missing month is חסר", () => {
  const m = consumptionModel(data, "2026-09");
  assert.equal(m.detail?.total, "₪4,000"); assert.equal(m.detail?.categories[0].pct, 75);
  assert.equal(m.detail?.installments, "מתוכם תשלומים: ₪450");
  assert.equal(consumptionModel(data, "2026-08").detail?.installments, null);
  assert.equal(consumptionModel(data, "2026-07").detail?.total, "חסר");
  assert.ok(consumptionModel(data, "2026-10").detail?.partialNote);
});

test("month navigation: older / newer neighbours and the ends", () => {
  const m = consumptionModel(data, "2026-09");
  assert.equal(m.older?.month, "2026-08"); assert.equal(m.newer?.month, "2026-10");
  assert.equal(consumptionModel(data, "2026-10").newer, null); assert.equal(consumptionModel(data, "2026-07").older, null);
});

test("markup: no loans / income wording; categories, instalments, insights and the notes are shown", () => {
  const html = renderToStaticMarkup(createElement(ConsumptionView, { data, selected: "2026-09", onSelect: () => undefined, range: 6, onRange: () => undefined }));
  assert.ok(html.includes("צריכה לפי קטגוריה") && html.includes("מחייה") && html.includes("מתוכם תשלומים") && html.includes("חריגה בפנאי ובילויים"));
  assert.ok(html.includes("הלוואות לא נספרות כאן") && html.includes("מעבר בין חודשים"));
  assert.ok(!html.includes("הכנסות") && !html.includes("יתרה"));
});

if (failures > 0) throw new Error(`${failures} test(s) failed`);
