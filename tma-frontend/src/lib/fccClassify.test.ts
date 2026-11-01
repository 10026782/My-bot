// Plain node + esbuild test (see package.json `npm test`). Wording only: the client does no financial arithmetic.
import type { FccClassifyView } from "../types";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { FccClassify } from "../components/FccClassify";
import { CUSTOM_MAX, classifyModel, confirmLine, customCategory, refreshAction, resultNote } from "./fccClassify";

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

const view = (over: Partial<FccClassifyView> = {}): FccClassifyView => ({
  total: 3, total_amount: 1500, categories: [{ key: "living", label: "מחייה" }, { key: "card_fees", label: "דמי כרטיס" }, { key: "fees_interest", label: "עמלות וריביות" }],
  item: { id: "recAAAAAAAAAAAAAA", date: "2026-10-05", amount: 1000, label: "חנות לא ידועה", source: "card", same_count: 2 }, ...over,
});

test("the model states the count, the sum and the next expense as the server sent them", () => {
  const m = classifyModel(view());
  assert.ok(m.header.includes("3 הוצאות") && m.header.includes("₪1,500"));
  assert.equal(m.item?.title, "חנות לא ידועה"); assert.equal(m.item?.amount, "₪1,000"); assert.ok(m.item?.meta.includes("05/10/2026") && m.item?.meta.includes("כרטיס אשראי"));
  assert.ok(m.sameLabel?.includes("2 הוצאות נוספות")); assert.equal(m.empty, false);
});

test("a manually recorded expense is labelled as such", () => {
  const m = classifyModel(view({ item: { id: "recBBBBBBBBBBBBBB", date: "2026-10-11", amount: 420, label: "הוצאה שנרשמה ידנית", source: "manual", same_count: 0 } }));
  assert.ok(m.item?.meta.includes("רישום ידני") && m.sameLabel === null);
});

test("the two new fee categories are offered", () => {
  const labels = classifyModel(view()).categories.map((c) => c.label);
  assert.ok(labels.includes("דמי כרטיס") && labels.includes("עמלות וריביות"));
});

test("nothing waiting is an empty state, not a zero", () => {
  const m = classifyModel(view({ total: 0, total_amount: 0, item: null }));
  assert.equal(m.empty, true); assert.equal(m.item, null); assert.ok(m.header.includes("אין"));
});

test("no 'same description' line when it is the only one", () => {
  assert.equal(classifyModel(view({ item: { ...view().item!, same_count: 0 } })).sameLabel, null);
});

test("the review line names the row, the amount and the category before anything is sent", () => {
  const m = classifyModel(view());
  const line = confirmLine(m, "דמי כרטיס", true);
  assert.ok(line.includes("חנות לא ידועה") && line.includes("₪1,000") && line.includes("דמי כרטיס") && line.includes("2 נוספות"));
  assert.ok(!confirmLine(m, "דמי כרטיס", false).includes("נוספות"));
});

test("a new category is trimmed, collapsed, never empty and never over the server's limit", () => {
  assert.equal(customCategory("  קייטרינג   אירועים "), "קייטרינג אירועים");
  assert.equal(customCategory("   "), null); assert.equal(customCategory("x".repeat(CUSTOM_MAX + 1)), null);
});

test("the result note counts what was classified and what is left of the same description", () => {
  assert.equal(resultNote(view()), null);
  assert.equal(resultNote(view({ state: "done", done: 10, same_left: 4 })), "סווגו 10 · נותרו עוד 4 עם אותו שם");
  assert.ok(resultNote(view({ state: "done", done: 1, rule_saved: true }))?.includes("בדוחות הבאים"));
});

test("after a new import an open panel reloads; a closed one and an unchanged counter do nothing", () => {
  assert.equal(refreshAction("open", 0, 1), "reload"); assert.equal(refreshAction("saving", 1, 2), "reload"); assert.equal(refreshAction("error", 0, 1), "reload");
  assert.equal(refreshAction("closed", 0, 1), "none"); assert.equal(refreshAction("open", 3, 3), "none");
});

test("the section renders only when something waits", () => {
  assert.equal(renderToStaticMarkup(createElement(FccClassify, { summary: { total: 0, total_amount: 0 }, onChanged: () => undefined })), "");
  assert.equal(renderToStaticMarkup(createElement(FccClassify, { summary: null, onChanged: () => undefined })), "");
  const html = renderToStaticMarkup(createElement(FccClassify, { summary: { total: 4, total_amount: 800 }, onChanged: () => undefined }));
  assert.ok(html.includes("הוצאות לסיווג") && html.includes("4 הוצאות") && html.includes("סווג הוצאה אחת-אחת"));
});

if (failures > 0) throw new Error(`${failures} test(s) failed`);
