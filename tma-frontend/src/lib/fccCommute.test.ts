import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { CommuteView } from "../components/FccCommute";
import { ANSWERS, answerBody, answerOf, dayLabel, economicsHint, economicsRows, routeBody, summaryModel, tripRows, weekRows, EMPTY_FORM } from "./fccCommute";
import type { FccCommute, FccCommuteRoute } from "../types";

let failures = 0;
const assert = {
  equal: (a: unknown, b: unknown) => { if (a !== b) throw new Error(`expected ${JSON.stringify(b)}, got ${JSON.stringify(a)}`); },
  ok: (v: unknown) => { if (!v) throw new Error("not ok"); },
};
function test(name: string, fn: () => void) { try { fn(); console.log(`ok - ${name}`); } catch (e) { failures++; console.error(`not ok - ${name}: ${(e as Error).message}`); } }

const day = (date: string, o: Partial<FccCommuteRoute["days"][number]> = {}) => ({ date, weekday: "רביעי", is_tomorrow: false, is_today: false, outcome: null, stops: null, trip_id: null, ...o });
const route: FccCommuteRoute = {
  id: "recR", name: "נסיעה", price: 130, km_one_way: 22, minutes_one_way: 35, cost_per_km: null, planned_days: 6, active: true, notes: null,
  economics: { price: 130, km_per_day: 44, minutes_per_day: 70, hours_per_day: 1.17, gross_per_hour: 111.43, gross_per_km: 2.95, vehicle_cost_per_day: null, net_per_day: null, net_per_hour: null, net_per_km: null, monthly_potential: 3380 },
  days: [day("2026-11-18", { is_tomorrow: true, outcome: "yes", stops: 3 }), day("2026-11-16")],
  this_month: { month: "2026-11", yes_days: 5, no_days: 1, income: 650, stops: { "2": 3, "3": 2 }, stops_recorded: 5, three_share: 0.4, weeks: [{ week_start: "2026-11-08", yes_days: 5, income: 650 }] },
  history: [], stops_note: null,
};
const view: FccCommute = {
  month: "2026-11", today: "2026-11-17", routes: [route], income_this_month: 650, unanswered_past: 4,
  trips: [{ id: "t1", date: "2026-11-12", weekday: "חמישי", route: "נסיעה", outcome: "yes", stops: 3, amount: 130 }, { id: "t2", date: "2026-11-13", weekday: "שישי", route: "נסיעה", outcome: "no", stops: null, amount: 0 }],
};

test("answers: the pressed button, the request body and the day label", () => {
  assert.equal(ANSWERS.map((a) => a.label).join("|"), "אין נסיעה|2 תחנות|3 תחנות");
  assert.equal(answerOf(route.days[0]), "3");
  assert.equal(answerOf(route.days[1]), null);
  assert.equal(answerOf(day("2026-11-10", { outcome: "no" })), "no");
  assert.equal(JSON.stringify(answerBody("recR", "2026-11-18", "3")), JSON.stringify({ route_id: "recR", date: "2026-11-18", outcome: "yes", stops: 3 }));
  assert.equal(JSON.stringify(answerBody("recR", "2026-11-18", "no")), JSON.stringify({ route_id: "recR", date: "2026-11-18", outcome: "no" }));
  assert.ok(dayLabel(route.days[0]).startsWith("מחר · יום רביעי 18/11"));
});

test("summary: what to collect, ride days and the days without an answer", () => {
  const s = summaryModel(view);
  assert.equal(s.cards[0].label, "לגבות בסוף החודש");
  assert.ok(s.cards[0].value.includes("650") && s.cards[0].hint!.includes("5 ימי נסיעה") && s.cards[0].hint!.includes("1 ימים בלי נסיעה"));
  assert.equal(s.cards[2].value, "4");
});

test("economics: unknown stays unknown, never zero", () => {
  const rows = Object.fromEntries(economicsRows(route).map((r) => [r.label, r.value]));
  assert.equal(rows["נטו ליום"], "—");
  assert.ok(rows["ברוטו לשעה"].includes("111"));
  assert.equal(economicsHint(route), 'חסר: עלות לק"מ (בלי זה אין נטו)');
  assert.equal(weekRows(route)[0].days, "5");
  assert.equal(tripRows(view)[0].result, "3 תחנות");
  assert.equal(tripRows(view)[1].amount, "—");
});

test("route form: blank is left out, bad is an error, a new route needs a name and a price", () => {
  assert.ok("error" in routeBody(EMPTY_FORM));
  const ok = routeBody({ name: " נסיעה ", price: "130", km: "22", minutes: "35", cost: "", days: "6" });
  assert.ok("body" in ok && ok.body.name === "נסיעה" && ok.body.price === 130 && ok.body.cost_per_km === undefined && ok.body.planned_days === 6);
  assert.ok("error" in routeBody({ ...EMPTY_FORM, name: "x", price: "12a" }));
  assert.ok("error" in routeBody({ ...EMPTY_FORM, name: "x", price: "5", days: "9" }));
  const edit = routeBody({ ...EMPTY_FORM, days: "", cost: "0.8" }, "recR");
  assert.ok("body" in edit && edit.body.route_id === "recR" && edit.body.cost_per_km === 0.8 && edit.body.name === undefined);
});

test("view: tomorrow card with three buttons, the pressed one marked; tables; empty state", () => {
  const html = renderToStaticMarkup(createElement(CommuteView, { data: view, busy: false, error: null, onAnswer: () => undefined, onSaveRoute: () => undefined }));
  assert.ok(html.includes("יש נסיעה?") && html.includes("3 תחנות") && html.includes('aria-pressed="true"'));
  assert.ok(html.includes("טבלת נסיעות") && html.includes("כדאיות ליום נסיעה") && html.includes("לגבות בסוף החודש"));
  const empty = renderToStaticMarkup(createElement(CommuteView, { data: { ...view, routes: [], trips: [] }, busy: false, error: "אופס", onAnswer: () => undefined, onSaveRoute: () => undefined }));
  assert.ok(empty.includes("אין מסלול עדיין") && empty.includes("אופס") && empty.includes("הוספת מסלול"));
});

if (failures) throw new Error(`${failures} fccCommute test(s) failed`);
console.log("all fccCommute tests passed");
