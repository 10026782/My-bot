// Plain node + esbuild test (see package.json `npm test`). Wording only: the client does no financial arithmetic.
declare function require(id: string): { readFileSync(path: string, enc: string): string };
import type { FccNetWorth } from "../types";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { NetWorthCard } from "../components/FccNetWorth";
import { MISSING, NET_WORTH_TITLE, NO_DATE, RECEIVABLES_NOTE, netWorthModel } from "./fccNetWorth";

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

const base: FccNetWorth = {
  as_of: "2026-10-19", net: 1060000, partial: false, gaps: { accounts_without_balance: 0, assets_left_out: 0, debts_without_balance: 0 },
  accounts: { total: 100000, items: [{ id: "a", name: "חשבון", value: 100000, as_of: "2026-10-01", verification: "self_reported" }], missing: [], oldest_as_of: "2026-10-01" },
  assets: { total: 1000000, items: [{ id: "h", name: "דירה", asset_type: null, as_of: null, gross_value: 1000000, ownership_pct: 100, value: 1000000, debt_source: "linked_loans",
    debt: 40000, debt_gross: 40000, unknown_debt_loans: 0, ignored_mortgage_balance: 40000, counted: true, missing: [] }], sold_excluded: 1, oldest_as_of: null, as_of_known: false },
  liabilities: { total: 40000, on_assets: 40000, standalone: null, standalone_items: [], oldest_as_of: null, as_of_known: false },
  receivables: { in_net: false, label: "expected_uncertain", count: 1, total: 25000, coverage: 1, items: [{ id: "r", name: "חבר", balance: 25000 }] },
};

test("breakdown rows show the server's numbers and the source dates", () => {
  const m = netWorthModel(base);
  assert.equal(m.net.value, "₪1,060,000");
  assert.equal(m.rows.map((r) => r.key).join(","), "accounts,assets,liabilities");
  assert.ok(m.rows[0].hint.includes("2026-10-01"), "accounts date");
  assert.ok(m.rows[1].hint.includes(NO_DATE) && m.rows[2].hint.includes(NO_DATE), "assets/liabilities have no stored date: said so");
});

test("receivables are a separate, labelled expected/uncertain card — not a row of the net", () => {
  const m = netWorthModel(base);
  assert.ok(m.receivables && m.receivables.value === "₪25,000" && m.receivables.hint === RECEIVABLES_NOTE);
  assert.ok(!m.rows.some((r) => r.key === "receivables"));
});

test("a missing total is 'חסר', never 0; partial says so and every gap is noted", () => {
  const m = netWorthModel({ ...base, net: null, partial: true, gaps: { accounts_without_balance: 2, assets_left_out: 1, debts_without_balance: 3 },
    accounts: { ...base.accounts, total: null }, liabilities: { ...base.liabilities, total: null } });
  assert.equal(m.net.value, MISSING);
  assert.equal(m.rows[0].value, MISSING);
  assert.equal(m.rows[2].value, MISSING);
  assert.ok(m.net.hint.startsWith("חלקי"));
  assert.ok(m.notes.some((n) => n.includes("2 חשבונות")) && m.notes.some((n) => n.includes("1 נכסים")) && m.notes.some((n) => n.includes("3 הלוואות")));
});

test("a sold asset and an overlapping mortgage are explained; no receivables card when there are none", () => {
  const m = netWorthModel({ ...base, receivables: { ...base.receivables, count: 0, total: null, items: [] } });
  assert.equal(m.receivables, null);
  assert.ok(m.notes.some((n) => n.includes("נמכרו")) && m.notes.some((n) => n.includes("פעם אחת")));
});

test("card: renders the breakdown; 404/403 render nothing; other errors offer a retry", () => {
  const html = renderToStaticMarkup(createElement(NetWorthCard, { state: { status: "ok", data: base }, onRetry: () => undefined }));
  assert.ok(html.includes(NET_WORTH_TITLE) && html.includes("₪1,060,000") && html.includes("חייבים לי"));
  assert.equal(renderToStaticMarkup(createElement(NetWorthCard, { state: { status: "error", code: 404 }, onRetry: () => undefined })), "");
  assert.equal(renderToStaticMarkup(createElement(NetWorthCard, { state: { status: "error", code: 403 }, onRetry: () => undefined })), "");
  assert.ok(renderToStaticMarkup(createElement(NetWorthCard, { state: { status: "error", code: 500 }, onRetry: () => undefined })).includes("נסו שוב"));
});

test("the client does no arithmetic and never fetches by itself", () => {
  const fs = require("fs");
  const src = fs.readFileSync("src/lib/fccNetWorth.ts", "utf8") + fs.readFileSync("src/components/FccNetWorth.tsx", "utf8");
  assert.ok(!/fetch\(|localStorage|reduce\(/.test(src), "no fetch / storage / sums in the presentation files");
});

if (failures > 0) { console.error(`${failures} failing`); throw new Error("failing"); }
