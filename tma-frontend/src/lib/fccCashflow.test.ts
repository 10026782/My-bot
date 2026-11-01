// Plain node + esbuild test (see package.json `npm test`). Wording only: the client does no financial arithmetic.
import type { FccCashflow, FccCashflowMonth } from "../types";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { CashflowView } from "../components/FccCashflow";
import { MISSING, cashflowModel, defaultMonth, insightLines, monthLabel } from "./fccCashflow";

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

const month = (key: string, over: Partial<FccCashflowMonth> = {}): FccCashflowMonth => ({
  month: key, is_current: false, partial: false, day: null, days_in_month: 30,
  income: { known: true, sources: [{ name: "נסיעות", kind: "variable", gross: 3000, direct_costs: 400, net: 2600, basis: "recorded" },
                                    { name: "נוף הגליל", kind: "fixed", gross: 8000, direct_costs: 0, net: 8000, basis: "standing" }], gross: 11000, direct_costs: 400, net: 10600 },
  expenses: { known: true, count: 3, categories: [{ key: "living", label: "מחייה", amount: 3000 }, { key: "חיות מחמד", label: "חיות מחמד", amount: 1000, custom: true },
                                                  { key: "loans", label: "הלוואות", amount: 2500, basis: "scheduled" }], total: 6500 },
  balance: 4100, shortfall: 0, surplus: 4100, missing: [], ...over,
});
const data: FccCashflow = {
  months: [month("2026-08", { balance: -500, shortfall: 500, surplus: 0 }), month("2026-09"),
           month("2026-10", { is_current: true, partial: true, day: 20, days_in_month: 31 }),
           month("2026-07", { income: { known: false, sources: [], gross: null, direct_costs: null, net: null }, balance: null, shortfall: null, surplus: null, missing: ["income"] })],
  categories: [], thresholds: {}, loans_payments_known: true, as_of: "2026-10-20",
  insights: {
    changes: { from: "2026-08", to: "2026-09", total_before: 6000, total_after: 6500, total_delta: 500, items: [{ key: "living", label: "מחייה", before: 2500, after: 3000, delta: 500, pct: 20 }] },
    spikes: [{ month: "2026-10", key: "leisure", label: "פנאי ובילויים", amount: 1500, baseline: 500, excess: 1000, partial: true }],
    large_items: [{ ref: "r", label: "מקרר", amount: 2500, date: "2026-09-09", key: "home", category: "הוצאות בית" }],
  },
};

test("month labels are Hebrew", () => {
  assert.equal(monthLabel("2026-10"), "אוקטובר 2026");
  assert.equal(monthLabel("bad"), "bad");
});

test("default month = the latest COMPLETE month with a known balance (never the partial current one)", () => {
  assert.equal(defaultMonth(data), "2026-09");
});

test("a month with no income shows חסר, never 0, and has no balance tone", () => {
  const m = cashflowModel(data, "2026-07");
  const row = m.rows.find((r) => r.month === "2026-07")!;
  assert.equal(row.income, MISSING); assert.equal(row.balance, MISSING); assert.equal(row.tone, "missing");
  assert.ok(m.detail!.missingNote!.includes("הכנסות"));
  assert.equal(m.detail!.kpis.find((k) => k.key === "balance")!.value, MISSING);
});

test("a shortfall month is labelled חסר with the amount, a surplus month יתרה", () => {
  const bad = cashflowModel(data, "2026-08").detail!.kpis.find((k) => k.key === "balance")!;
  assert.equal(bad.label, "חסר"); assert.ok(bad.value.includes("500"));
  const ok = cashflowModel(data, "2026-09").detail!.kpis.find((k) => k.key === "balance")!;
  assert.equal(ok.label, "יתרה"); assert.ok(ok.value.includes("4,100"));
  assert.equal(cashflowModel(data).rows.find((r) => r.month === "2026-08")!.tone, "bad");
});

test("partial current month is flagged; scheduled loans are marked as an estimate; custom categories are marked", () => {
  const m = cashflowModel(data, "2026-10");
  assert.ok(m.detail!.partialNote!.includes("20"));
  assert.equal(m.rows.find((r) => r.month === "2026-10")!.tag, "עד ה-20 בחודש");
  assert.equal(m.detail!.categories.find((c) => c.key === "loans")!.estimate, true);
  assert.equal(m.detail!.categories.find((c) => c.key === "חיות מחמד")!.custom, true);
  assert.equal(m.detail!.categories.find((c) => c.key === "living")!.pct, 46);      // share of the month total, for the bar only
});

test("income sources keep the server's net and explain standing / direct costs", () => {
  const s = cashflowModel(data, "2026-09").detail!.sources;
  assert.equal(s.find((x) => x.name === "נוף הגליל")!.hint, "סכום קבוע");
  assert.ok(s.find((x) => x.name === "נסיעות")!.hint.includes("עלויות ישירות"));
});

test("insights: change, spike (partial marked) and large item all worded from server numbers", () => {
  const lines = insightLines(data);
  assert.ok(lines[0].includes("אוגוסט 2026") && lines[0].includes("+₪500"));
  assert.ok(lines.some((l) => l.includes("חריגה בפנאי ובילויים") && l.includes("עד היום")));
  assert.ok(lines.some((l) => l.includes("מקרר") && l.includes("₪2,500")));
});

test("notes state that obligations are not added and that missing months are excluded; missing loans info is stated", () => {
  const n = cashflowModel(data).notes.join(" ");
  assert.ok(n.includes("התחייבויות קבועות לא נוספות") && n.includes("חסר"));
  assert.ok(cashflowModel({ ...data, loans_payments_known: false }).notes.some((x) => x.includes("לא נמצא החזר הלוואות")));
});

test("markup: range buttons, month rows (newest first), bars, insights; no input fields (read-only)", () => {
  const html = renderToStaticMarkup(createElement(CashflowView, { data, selected: "2026-09", onSelect: () => undefined, range: 6, onRange: () => undefined }));
  assert.equal((html.match(/aria-label="טווח חודשים"/g) ?? []).length, 1);
  assert.equal((html.match(/fcc-cf-row /g) ?? []).length, 4);
  const list = html.slice(html.indexOf("חודש אחר חודש"));                                    // the detail heading above also names the selected month
  assert.ok(list.indexOf("אוקטובר 2026") < list.indexOf("ספטמבר 2026") && list.indexOf("ספטמבר 2026") < list.indexOf("אוגוסט 2026"));
  assert.ok(html.includes('role="progressbar"') && html.includes("שינויים וחריגות") && html.includes("חיות מחמד ✦"));
  assert.ok(!html.includes("<textarea") && !html.includes("<input"));
  assert.equal((html.match(/aria-pressed="true"/g) ?? []).length, 2);                // the selected range + the selected month
});

if (failures > 0) throw new Error(`${failures} test(s) failed`);
