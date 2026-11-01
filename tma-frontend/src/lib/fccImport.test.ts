// Plain node + esbuild test (see package.json `npm test`). Wording only: the client does no financial arithmetic.
import type { FccImportPreview } from "../types";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { FccImport } from "../components/FccImport";
import { IMPORT_NOTE, SKIP_LABEL, START, advance, progressText, reviewOf } from "./fccImport";

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

const preview = (over: Partial<FccImportPreview> = {}): FccImportPreview => ({
  kind: "bank", label: "main", parse: { ok: true, rows: 191, verified: 190, problems: [] }, digest: "abc", can_import: true, chunk: 20,
  plan: {
    events: 3, remaining: 3, already_imported: 0,
    months: { "2026-10": { expenses: 200, income: 8000, events: 3, by_category: { taxes: 200 }, by_source: { "עבודת אשתי": 8000 } } },
    skipped: { card_settlement: { count: 1, total: 3000 }, needs_review: { count: 2, total: 700 }, reversal: { count: 0, total: 0 } },
    pending_rules: 14, pending_row_rules: 2,
    pending_examples: [{ match: "חנות לא ידועה", direction: "debit", times_seen: 2, example_amount: 100, row: false }, { match: "לבדיקה: העברה-נייד", direction: "credit", times_seen: 1, example_amount: 700, row: true }],
  },
  ...over,
});

test("the review says what will be written, month by month, and what will NOT be and why", () => {
  const r = reviewOf(preview());
  assert.equal(r.headline, "ייכתבו 3 רישומים."); assert.equal(r.canImport, true); assert.equal(r.confirmLabel, "אשר ייבוא של 3 רישומים");
  assert.equal(r.months[0].label, "אוקטובר 2026"); assert.equal(r.months[0].expenses, "₪200"); assert.equal(r.months[0].income, "₪8,000");
  assert.equal(r.skipped.length, 2);                                                         // a reason with count 0 is not listed
  assert.ok(r.skipped[0].label.includes("יפורט בדוח הכרטיס") && r.skipped[1].label.includes("אחת-אחת"));
});

test("pending descriptions are announced as additions to the owner's table, with the single-row ones named, and the rest counted", () => {
  const r = reviewOf(preview());
  assert.ok(r.pendingNote!.includes("14 תיאורים") && r.pendingNote!.includes("Cashflow Rules") && r.pendingNote!.includes("2 העברות"));
  assert.ok(r.pending[0].includes("חנות לא ידועה") && r.pending[0].includes("2 פעמים") && r.pending[1].includes("שורה בודדת") && r.pending[2] === "ועוד 12");
});

test("a statement that does not add up blocks the import and says so", () => {
  const r = reviewOf(preview({ parse: { ok: false, rows: 10, verified: 5, problems: ["2 breaks in the balance chain"] }, digest: null, can_import: false }));
  assert.equal(r.canImport, false); assert.ok(r.blocked[0].includes("לא נכתב דבר") && r.blocked[1].includes("breaks"));
});

test("nothing new to write: the headline says so and the button only offers the pending descriptions", () => {
  const done = reviewOf(preview({ plan: { ...preview().plan, remaining: 0, already_imported: 3 } }));
  assert.equal(done.headline, "כל השורות שהוחלטו כבר יובאו."); assert.equal(done.confirmLabel, "הוסף את התיאורים לסיווג"); assert.equal(done.canImport, true);
  const none = reviewOf(preview({ can_import: false, plan: { ...preview().plan, events: 0, remaining: 0, pending_rules: 0, pending_row_rules: 0, pending_examples: [] } }));
  assert.equal(none.headline, "אין שורות שהוחלטו לייבוא בדוח הזה."); assert.equal(none.canImport, false); assert.equal(none.pendingNote, null);
});

test("progress accumulates events and rules, finishes on done and keeps a failure retryable", () => {
  let p = advance(START, { state: "progress", step: "events", written: 20, remaining: 5, rules_to_add: 3 });
  assert.equal(progressText(p), "נכתבו 20 · נותרו 5…");
  p = advance(p, { state: "progress", step: "events", written: 5, remaining: 0, rules_to_add: 3 });
  p = advance(p, { state: "progress", step: "rules", written: 3, remaining: 0 });
  p = advance(p, { state: "done", step: "done", written: 0, remaining: 0 });
  assert.equal(p.done, true); assert.equal(progressText(p), "הושלם: 25 רישומים נכתבו · 3 תיאורים נוספו לסיווג.");
  const blocked = advance({ ...START, written: 20 }, { state: "blocked", step: "events", message: "הכתיבה לא הושלמה" });
  assert.equal(blocked.written, 20); assert.equal(progressText(blocked), "הכתיבה לא הושלמה"); assert.equal(blocked.done, false);
});

test("every reason the server can give for skipping has a Hebrew label", () => {
  for (const k of ["already_imported", "card_settlement", "cash_withdrawal", "credit_service", "adjustment", "transfer", "reversal", "ignore", "needs_review", "needs_classification", "no_category", "no_source"]) {
    assert.ok(SKIP_LABEL[k] && /[֐-׿]/.test(SKIP_LABEL[k]), k);
  }
  assert.ok(IMPORT_NOTE.includes("בונה בשרת") || IMPORT_NOTE.includes("נבנית בשרת")); assert.ok(IMPORT_NOTE.includes("פעמיים") && IMPORT_NOTE.includes("Cashflow Rules"));
});

test("markup: the import card is closed by default (one button, no file input until opened)", () => {
  const html = renderToStaticMarkup(createElement(FccImport, { onImported: () => undefined }));
  assert.ok(html.includes("ייבוא דוח") && html.includes('aria-expanded="false"') && !html.includes('type="file"'));
});

if (failures > 0) throw new Error(`${failures} test(s) failed`);
