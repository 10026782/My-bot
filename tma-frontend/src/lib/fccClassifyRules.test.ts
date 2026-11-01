// Plain node + esbuild test (see package.json `npm test`). Wording only: the client does no financial arithmetic.
import type { FccRuleView } from "../types";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { FccClassifyRules } from "../components/FccClassifyRules";
import { ruleConfirmLine, ruleModel } from "./fccClassifyRules";

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

const view = (over: Partial<FccRuleView> = {}): FccRuleView => ({
  total: 3, item: { id: "recAAAAAAAAAAAAAA", match: "משנת יוסף", applies_to: "card", times_seen: 4, amount: 1114.3, last_seen: "2026-10-05" },
  categories: [{ key: "living", label: "מחייה" }, { key: "card_fees", label: "דמי כרטיס" }], ...over,
});

test("the model states the count and the next description as the server sent them", () => {
  const m = ruleModel(view());
  assert.ok(m.header.includes("3 תיאורים")); assert.equal(m.item?.title, "משנת יוסף");
  assert.ok(m.item?.meta.includes("כרטיס אשראי") && m.item?.meta.includes("4 פעמים") && m.item?.meta.includes("₪1,114"));
  assert.equal(m.empty, false);
});

test("a single occurrence reads 'once' and nothing waiting is an empty state", () => {
  assert.ok(ruleModel(view({ item: { ...view().item!, times_seen: 1 } })).item?.meta.includes("פעם אחת"));
  const e = ruleModel(view({ total: 0, item: null }));
  assert.equal(e.empty, true); assert.equal(e.item, null);
});

test("the review line names the description and the category and says it covers later imports too", () => {
  const line = ruleConfirmLine(ruleModel(view()), "מחייה");
  assert.ok(line.includes("משנת יוסף") && line.includes("מחייה") && line.includes("בייבוא הבא"));
});

test("the section renders only when something waits", () => {
  assert.equal(renderToStaticMarkup(createElement(FccClassifyRules, { summary: { total: 0 }, onChanged: () => undefined })), "");
  assert.equal(renderToStaticMarkup(createElement(FccClassifyRules, { summary: null, onChanged: () => undefined })), "");
  const html = renderToStaticMarkup(createElement(FccClassifyRules, { summary: { total: 5 }, onChanged: () => undefined }));
  assert.ok(html.includes("תיאורים לסיווג") && html.includes("5 תיאורים") && html.includes("סווג תיאור אחד-אחד"));
});

if (failures > 0) throw new Error(`${failures} test(s) failed`);
