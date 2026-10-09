// Plain node + esbuild test (see package.json `npm test`).
declare function require(id: string): { readFileSync(path: string, enc: string): string };
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { ContextualComposer, FccTabBar, type ComposerTargets } from "../components/FccTabBar";
import { SavingsFollowUp, SavingsReleaseCard } from "../components/FccKpiCard";
import type { FccTurn } from "../types";
import {
  COMPOSER, DEFAULT_TAB, FCC_TABS, WRITER_WORDS, chipsEnabled, initialTab, inputVisible, isTab, nextWriterState, panelId,
  rememberTab, resetTabMemory, tabForKey, tabId, writerView, type FccTabKey,
} from "./fccTabs";

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

test("keyboard: arrows follow the visual order (mirrored in RTL), wrap, Home/End jump, other keys ignored", () => {
  assert.equal(tabForKey("monthly", "ArrowLeft", true), "loans");        // RTL: next tab is on the left
  assert.equal(tabForKey("monthly", "ArrowRight", true), "assets");      // wraps to the last
  assert.equal(tabForKey("assets", "ArrowLeft", true), "monthly");
  assert.equal(tabForKey("monthly", "ArrowRight", false), "loans");      // LTR is the mirror image
  assert.equal(tabForKey("loans", "Home", true), "monthly");
  assert.equal(tabForKey("loans", "End", true), "assets");
  assert.equal(tabForKey("loans", "Enter", true), null);
  assert.equal(tabForKey("loans", "ArrowDown", true), null);
});

test("only the selected tab is in the Tab order; every tab points at an existing panel id", () => {
  const html = renderToStaticMarkup(createElement(FccTabBar, { active: "loans", onChange: () => undefined }));
  assert.equal((html.match(/tabindex="0"/g) || []).length, 1);
  assert.equal((html.match(/tabindex="-1"/g) || []).length, 2);
  for (const t of FCC_TABS) assert.ok(html.includes(`aria-controls="${panelId(t.key)}"`) && html.includes(`id="${tabId(t.key)}"`));
});

// ── Contextual composer ──────────────────────────────────────────────────────────────────────────────────────────────
const turn = (state: FccTurn["state"], message = "m", extra: Partial<FccTurn> = {}): FccTurn => ({ state, message, ...extra });
const targets: ComposerTargets = { goals: [{ id: "g1", title: "משכורת" }], loans: [{ id: "recL1", title: "פועלים" }], assets: [{ id: "recA1", title: "בית שמש" }] };
const noop = () => undefined;
const composer = (tab: FccTabKey, t: FccTurn | null = null, receipt: string | null = null, busy = false) =>
  renderToStaticMarkup(createElement(ContextualComposer, { tab, turn: t, receipt, error: null, busy, targets, onStart: noop, onSend: noop, onDismiss: noop }));

test("each tab has its own title; the monthly chips are income / household expense / direct cost / obligation / goal update", () => {
  assert.equal(COMPOSER.monthly.title, "עדכון כספי"); assert.equal(COMPOSER.loans.title, "עדכון הלוואה"); assert.equal(COMPOSER.assets.title, "עדכון נכס");
  assert.equal(COMPOSER.monthly.chips.map((c) => c.intent).join(),
    "monthly.income,monthly.household_expense,monthly.direct_cost,monthly.obligation,monthly.goal_update,savings.deposit");
  assert.equal(COMPOSER.monthly.chips.find((c) => c.intent === "monthly.household_expense")?.label, "+ הוצאה ביתית");
  assert.equal(COMPOSER.monthly.chips.find((c) => c.intent === "monthly.direct_cost")?.label, "+ עלות ישירה");
});

test("chips are intents only: no chip carries a write, a field name or a kind; targets are chosen, never typed", () => {
  for (const tab of FCC_TABS) for (const c of COMPOSER[tab.key].chips) {
    assert.ok(/^(monthly|loan|asset|savings)\.[a-z_]+$/.test(c.intent), c.intent);
    assert.ok(Object.keys(c).every((k) => ["intent", "label", "pick"].includes(k)));
  }
  assert.equal(COMPOSER.loans.chips.map((c) => c.intent).join(), "loan.update_balance,loan.update_payment,loan.create,loan.close");
  for (const c of COMPOSER.loans.chips) assert.equal(c.pick, c.intent === "loan.create" ? undefined : "loan", c.intent);
  assert.equal(COMPOSER.monthly.chips.find((c) => c.intent === "monthly.goal_update")?.pick, "goal");
});

test("assets chips: value / mortgage / next step / mark-sold — all choose an asset; nothing offers a loan close or a write directly", () => {
  assert.equal(COMPOSER.assets.chips.map((c) => c.intent).join(), "asset.update_value,asset.update_mortgage,asset.next_step,asset.mark_sold");
  for (const c of COMPOSER.assets.chips) assert.equal(c.pick, "asset");
  assert.equal(COMPOSER.assets.chips.find((c) => c.intent === "asset.mark_sold")?.label, "נכס נמכר");
});

test("free text may open a NEW draft only on the monthly tab", () => {
  assert.ok(COMPOSER.monthly.freeText && !COMPOSER.loans.freeText && !COMPOSER.assets.freeText);
  const idle = writerView(null, null);
  assert.ok(inputVisible(COMPOSER.monthly, idle, false));
  assert.ok(!inputVisible(COMPOSER.loans, idle, false) && !inputVisible(COMPOSER.assets, idle, false));
  assert.ok(inputVisible(COMPOSER.loans, writerView(turn("ask"), null), false), "an open question is answerable in any tab");
  assert.ok(!inputVisible(COMPOSER.monthly, idle, true), "no input while choosing a target");
});

test("writerView: review -> confirm/edit/cancel; ask -> input; needs_goal -> own-goal choices; partial failure -> retry", () => {
  const r = writerView(turn("review"), null);
  assert.equal(r.confirm, "אשר ורשום"); assert.ok(r.canEdit && r.cancelsDraft && !r.showInput && !r.dismissOnly);
  const a = writerView(turn("ask"), null); assert.ok(a.showInput && a.cancelsDraft && a.confirm === null);
  const g = writerView(turn("needs_goal", "איזה יעד?", { candidates: [{ goal_id: "g1", title: "משכורת" }] }), null);
  assert.equal(g.choices.length, 1); assert.equal(g.choices[0].goal_id, "g1"); assert.ok(g.cancelsDraft);
  const p = writerView(turn("partial_failure"), null); assert.equal(p.confirm, "נסה שוב"); assert.ok(p.cancelsDraft);
  for (const s of ["info", "denied", "duplicate", "clarify"] as const) {
    const v = writerView(turn(s), null); assert.ok(v.dismissOnly && v.confirm === null && !v.cancelsDraft && !v.showInput, s);
  }
});

test("a receipt cannot be confirmed twice; chips are disabled while ANY draft is open or the server is busy", () => {
  const done = writerView(null, "נרשם ✓");
  assert.ok(done.dismissOnly && done.confirm === null && done.message === "נרשם ✓");
  assert.ok(chipsEnabled(done, false) && !chipsEnabled(done, true));
  assert.ok(!chipsEnabled(writerView(turn("review"), null), false), "one shared draft slot");
  assert.ok(!chipsEnabled(writerView(turn("ask"), null), false));
});

test("nextWriterState: executed -> receipt + refresh; cancelled -> clears; anything else keeps the turn", () => {
  const ex = nextWriterState(turn("executed", "נרשם ✓"));
  assert.ok(ex.refresh && ex.turn === null && ex.receipt === "נרשם ✓");
  const c = nextWriterState(turn("cancelled", "בוטל. לא נרשם דבר."));
  assert.ok(!c.refresh && c.turn === null);
  const k = nextWriterState(turn("review")); assert.ok(!k.refresh && k.turn?.state === "review" && k.receipt === null);
  assert.equal(WRITER_WORDS.confirm, "אשר"); assert.equal(WRITER_WORDS.edit, "ערוך"); assert.equal(WRITER_WORDS.cancel, "בטל");
});

test("markup: idle monthly shows 6 chips + one input; loans shows its 4 chips and NO input; assets shows its 4 chips and NO input", () => {
  const m = composer("monthly");
  assert.equal((m.match(/class="fcc-chip /g) || []).length, 6); assert.equal((m.match(/<textarea/g) || []).length, 1);
  assert.ok(m.includes("עדכון כספי") && m.includes("+ הכנסה") && m.includes("+ הוצאה ביתית") && m.includes("+ עלות ישירה") && m.includes("+ עדכון יעד") && m.includes("+ הפקדה לחיסכון"));
  const l = composer("loans");
  assert.equal((l.match(/class="fcc-chip /g) || []).length, 4); assert.ok(!l.includes("<textarea") && l.includes("עדכון הלוואה") && l.includes("סגירת הלוואה") && l.includes("הלוואה חדשה"));
  const a = composer("assets");
  assert.equal((a.match(/class="fcc-chip /g) || []).length, 4);
  assert.ok(!a.includes("<textarea") && a.includes("עדכון נכס") && a.includes("עדכון שווי") && a.includes("עדכון משכנתא") && a.includes("פעולה הבאה") && a.includes("נכס נמכר"));
});

test("markup: a review shows the server's text with confirm/edit/cancel and no input; chips are disabled", () => {
  const html = composer("loans", turn("review", "📋 סגירת הלוואה\n• הלוואה: פועלים"));
  assert.ok(html.includes("פועלים") && html.includes("אשר ורשום") && html.includes("ערוך") && html.includes("בטל"));
  assert.ok(!html.includes("<textarea"));
  assert.ok(/class="fcc-chip[^"]*"[^>]*disabled=""|disabled=""[^>]*class="fcc-chip/.test(html));
});

test("markup: the SAME open draft renders in every tab (one shared slot, one set of controls per render)", () => {
  const t = turn("ask", "כמה לרשום ביעד משכורת?");
  for (const tab of ["monthly", "loans", "assets"] as FccTabKey[]) {
    const html = composer(tab, t);
    assert.ok(html.includes("כמה לרשום ביעד משכורת?"), tab);
    assert.equal((html.match(/<textarea/g) || []).length, 1, tab);
  }
});

test("markup: busy disables confirm (no double confirm); the receipt state has no confirm button", () => {
  const busy = composer("monthly", turn("review"), null, true);
  assert.ok(!busy.includes('<button type="button" class="boss-button boss-button--primary boss-bubble--action">אשר ורשום'));
  const rec = composer("loans", null, "נרשם ✓");
  assert.ok(rec.includes("נרשם ✓") && !rec.includes("אשר ורשום") && rec.includes("סגור"));
});

test("idle composer is compact (chips + one-row input, no send button, no turn); an active draft expands it", () => {
  const idle = composer("monthly");
  assert.ok(idle.includes("fcc-composer--idle") && !idle.includes("fcc-composer--open"));
  assert.ok(idle.includes('rows="1"') && !idle.includes("שלח עדכון") && !idle.includes("fcc-quick__turn"));
  const open = composer("monthly", turn("ask", "כמה?"));
  assert.ok(open.includes("fcc-composer--open") && open.includes('rows="2"') && open.includes("fcc-quick__turn"));
  assert.ok(composer("loans", null, "נרשם ✓").includes("fcc-composer--open"), "a receipt is an active state");
});

const relFx = { income_net: 10000, income_target: 15000, fixed_level: 8000, shortfall: 5000, from_fixed: 3000, extra: 0, available: 3000, deposited: 0,
  remaining: 3000, expected: 8000, gap: 8000, month: "2026-10", closing: false, destination: { id: "p", title: "תכנון פנסיוני" } };

test("markup: the release card shows the freed amount + deposit button; month end adds the gap-reason button; follow-up asks once", () => {
  const card = renderToStaticMarkup(createElement(SavingsReleaseCard, { release: relFx, onStart: () => undefined, disabled: false }));
  assert.equal(card.includes("מתפנה לחיסכון החודש") && card.includes("₪3,000") && card.includes("הפקד ₪3,000") && !card.includes("תעד סיבה"), true);
  const closing = renderToStaticMarkup(createElement(SavingsReleaseCard, { release: { ...relFx, closing: true }, onStart: () => undefined, disabled: true }));
  assert.equal(closing.includes("תעד סיבה לפער") && closing.includes("סוף החודש") && closing.includes("disabled"), true);
  const fu = renderToStaticMarkup(createElement(SavingsFollowUp, { release: relFx, onStart: () => undefined, onDismiss: () => undefined, disabled: false }));
  assert.equal(fu.includes("להפקיד?") && fu.includes("לא עכשיו"), true);
  assert.equal(renderToStaticMarkup(createElement(SavingsFollowUp, { release: { ...relFx, remaining: 0 }, onStart: () => undefined, onDismiss: () => undefined, disabled: false })), "");
});

if (failures > 0) throw new Error(`${failures} test(s) failed`);
console.log("all fccTabs tests passed");

test("writerView: a closed question (ask + candidates, e.g. income type) is offered as buttons", () => {
  const t = { ...turn("ask", "איזה סוג הכנסה זו?"), candidates: [{ goal_id: "one_time", title: "חד-פעמית" }, { goal_id: "monthly_recurring", title: "חודשית קבועה" }] } as FccTurn;
  const v = writerView(t, null);
  assert.equal(v.choices.map((c) => c.goal_id).join(","), "one_time,monthly_recurring");
  assert.ok(v.showInput && v.cancelsDraft);
  assert.equal(writerView(turn("ask"), null).choices.length, 0);      // a plain question has no buttons
});
