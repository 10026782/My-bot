// Plain node + esbuild test (see package.json `npm test`).
declare function require(id: string): { readFileSync(path: string, enc: string): string };
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { FccTabBar } from "../components/FccTabBar";
import { DEFAULT_TAB, FCC_TABS, initialTab, isTab, panelId, rememberTab, resetTabMemory, tabId } from "./fccTabs";

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

test("three tabs, in order, with the agreed Hebrew names", () => {
  assert.equal(FCC_TABS.map((t) => t.label).join(" | "), "התנהלות חודשית | הלוואות וחוב | נכסים והון");
  assert.equal(FCC_TABS.map((t) => t.key).join(), "monthly,loans,assets");
});

test("default tab is התנהלות חודשית; a fresh session always starts there", () => {
  resetTabMemory();
  assert.equal(DEFAULT_TAB, "monthly");
  assert.equal(initialTab(), "monthly");
});

test("the tab is remembered during the session and forgotten on a new one", () => {
  resetTabMemory();
  rememberTab("loans");
  assert.equal(initialTab(), "loans");
  rememberTab("assets");
  assert.equal(initialTab(), "assets");
  resetTabMemory();                                   // = reopening the app
  assert.equal(initialTab(), "monthly");
});

test("an unknown tab key is ignored", () => {
  resetTabMemory();
  rememberTab("nope" as never);
  assert.equal(initialTab(), "monthly");
  assert.ok(isTab("assets") && !isTab("x"));
});

test("tab bar: accessible tablist, selected state, ids wired to the panels", () => {
  const html = renderToStaticMarkup(createElement(FccTabBar, { active: "loans", onChange: () => undefined }));
  assert.ok(html.includes('role="tablist"'));
  assert.equal((html.match(/role="tab"/g) ?? []).length, 3);
  assert.ok(html.includes(`id="${tabId("loans")}"`) && html.includes(`aria-controls="${panelId("loans")}"`));
  assert.equal((html.match(/aria-selected="true"/g) ?? []).length, 1);
  assert.ok(/aria-selected="true"[^>]*>הלוואות וחוב|>הלוואות וחוב<\/button>/.test(html));
  for (const t of FCC_TABS) assert.ok(html.includes(t.label));
});

test("390px smoke (css): tabs share the width and can shrink; hidden panels are not displayed", () => {
  const css = require("node:fs").readFileSync("src/index.css", "utf8");
  const block = css.slice(css.indexOf("FCC tabs"));
  assert.ok(block.includes("flex: 1 1 0") && block.includes("min-inline-size: 0"));
  assert.ok(block.includes('[role="tabpanel"][hidden] { display: none; }'));
  assert.ok(!/(^|[^-])width:\s*\d+px/m.test(block));
});

if (failures > 0) throw new Error(`${failures} test(s) failed`);
console.log("all fccTabs tests passed");
