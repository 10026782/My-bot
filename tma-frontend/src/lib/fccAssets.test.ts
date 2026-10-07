// Plain node + esbuild test (see package.json `npm test`).
import type { FccAssetItem, FccAssets } from "../types";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { AssetsSection } from "../components/FccAssets";
import { UNKNOWN } from "./fccLoans";
import { UNTYPED, assetCardModel, assetsHeaderCards, debtLines } from "./fccAssets";

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

const mk = (o: Partial<FccAssetItem>): FccAssetItem => ({ id: "x", name: "x", asset_type: null, status: null, current_value: null, monthly_income: null,
  mortgage_balance: null, ownership_pct: null, equity: null, my_equity: null, linked_loans: [], linked_debt: null, linked_debt_known: 0, linked_monthly_payments: null, ...o });

const house = mk({ id: "h", name: "בית", asset_type: "Residential", status: "פעיל", current_value: 5000000, mortgage_balance: 1200000, equity: 3800000, my_equity: 3800000,
  ownership_pct: 100, monthly_income: 0, linked_loans: [{ id: "l1", name: "בנק", loan_type: "משכנתא", early_closure_balance: 100000, monthly_payment: 2000, interest_rate: 6 }],
  linked_debt: 100000, linked_debt_known: 1, linked_monthly_payments: 2000 });
const empty = mk({ id: "e", name: "נכס ריק" });
const assets: FccAssets = { items: [house, empty], summary: { count: 2, total_value: 5000000, total_mortgage: 1200000, total_equity: 3800000, total_my_equity: 3800000, total_monthly_income: 0,
  coverage: { value: 1, mortgage: 1, equity: 1, my_equity: 1, monthly_income: 1 }, linked_loans_count: 1, linked_loans_debt: 100000, unlinked_loans_count: 1, unlinked_loans_debt: 50000 } };

test("header cards: value / equity / my equity / income, with partial coverage said out loud", () => {
  const c = assetsHeaderCards(assets);
  assert.equal(c.map((x) => x.value).join(" | "), "₪5,000,000 | ₪3,800,000 | ₪3,800,000 | ₪0");
  assert.equal(c[0].hint, "מבוסס על 1 מתוך 2 נכסים");
});

test("no fake zeroes: unknown totals and fields render לא הוגדר", () => {
  const none: FccAssets = { items: [empty], summary: { ...assets.summary, count: 1, total_value: null, total_mortgage: null, total_equity: null, total_my_equity: null,
    total_monthly_income: null, coverage: { value: 0, mortgage: 0, equity: 0, my_equity: 0, monthly_income: 0 }, linked_loans_debt: null, unlinked_loans_debt: null } };
  assert.ok(assetsHeaderCards(none).every((c) => c.value === UNKNOWN));
  const m = assetCardModel(empty);
  assert.ok(m.rows.every((r) => r.value === UNKNOWN), JSON.stringify(m.rows));
  assert.equal(m.typeLabel, UNTYPED);
  assert.ok(m.partial);
});

test("recorded mortgage and linked loans are separate lines, never summed", () => {
  const lines = debtLines(assets);
  assert.equal(lines.map((l) => l.value).join(" | "), "₪1,200,000 | ₪100,000 | ₪50,000");
  assert.ok(lines[1].label.includes("(1)") && lines[2].label.includes("(1)"));
  assert.ok(!lines.some((l) => l.value === "₪1,300,000"));
});

test("asset card: type label, status, linked loans only when linked", () => {
  const m = assetCardModel(house);
  assert.equal(m.typeLabel, "מגורים");
  assert.equal(m.status, "פעיל");
  assert.equal(m.linkedLoans.length, 1);
  assert.ok(m.linkedLoans[0].text.includes("יתרת סילוק ₪100,000") && m.linkedLoans[0].text.includes("6%"));
  assert.equal(m.linkedDebtLine, "חוב מקושר: ₪100,000");
  assert.equal(assetCardModel(empty).linkedLoans.length, 0);
  assert.equal(assetCardModel(empty).linkedDebtLine, null);
});

test("render smoke: read-only tab (no buttons/inputs), cards, debt block", () => {
  const html = renderToStaticMarkup(createElement(AssetsSection, { assets }));
  assert.equal((html.match(/class="fcc-loan fcc-asset"/g) ?? []).length, 2);
  assert.ok(html.includes("חוב ביחס לנכסים") && html.includes("לא מחושב") === false);
  assert.ok(!html.includes("<button") && !html.includes("<input"), "the assets tab is read-only in this phase");
  assert.ok(html.includes("נתונים חלקיים"));
});

test("empty state when there are no assets", () => {
  const html = renderToStaticMarkup(createElement(AssetsSection, { assets: { ...assets, items: [] } }));
  assert.ok(html.includes("אין נכסים"));
});

if (failures > 0) throw new Error(`${failures} test(s) failed`);
console.log("all fccAssets tests passed");
