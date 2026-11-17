import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { CommuteView } from "../components/FccCommute";
import {
  ANSWERS, EMPTY_FORM, EMPTY_OWN_FORM, answerBody, answerOf, dayLabel, economicsHint, economicsRows, emptyTripForm, formFromSettings, profitModel, quotaRows, routeBody, settingsBody, summaryModel,
  tripBody, tripRows, weekRows,
} from "./fccCommute";
import type { FccCommute, FccCommuteDay, FccCommuteProfit, FccCommuteRoute, FccCommuteStats } from "../types";

let failures = 0;
const assert = {
  equal: (a: unknown, b: unknown) => { if (a !== b) throw new Error(`expected ${JSON.stringify(b)}, got ${JSON.stringify(a)}`); },
  ok: (v: unknown) => { if (!v) throw new Error("not ok"); },
};
function test(name: string, fn: () => void) { try { fn(); console.log(`ok - ${name}`); } catch (e) { failures++; console.error(`not ok - ${name}: ${(e as Error).message}`); } }

const day = (date: string, o: Partial<FccCommuteDay> = {}): FccCommuteDay => ({ date, weekday: "רביעי", is_tomorrow: false, is_today: false, rest_day: false, outcome: null, stops: null, trip_id: null, ...o });
const route: FccCommuteRoute = {
  id: "recR", name: "נסיעה", kind: "paid", weekdays: [], price: 130, km_one_way: 22, minutes_one_way: 35, cost_per_km: null, planned_days: 6, active: true, notes: null, vehicle_class: null, return_status: "empty", waiting_minutes: 0,
  economics: { price: 130, km_per_day: 44, minutes_per_day: 70, hours_per_day: 1.17, gross_per_hour: 111.43, gross_per_km: 2.95, vehicle_cost_per_day: null, net_per_day: null, net_per_hour: null, net_per_km: null, monthly_potential: 3380, return_status: "empty", vehicle_class: null },
  days: [day("2026-11-18", { is_tomorrow: true, outcome: "yes", stops: 3 }), day("2026-11-16")],
  this_month: { month: "2026-11", yes_days: 5, no_days: 1, income: 650, stops: { "2": 3, "3": 2 }, stops_recorded: 5, three_share: 0.4, weeks: [{ week_start: "2026-11-08", yes_days: 5, income: 650 }] },
  history: [], stops_note: null,
};
const stats = (o: Partial<FccCommuteStats> = {}): FccCommuteStats => ({ rides: 2, avg_price: 185, measured_rides: 2, gross_per_hour: 120, gross_per_km: 2.5, net_per_hour: 90, net_per_km: 1.7, empty_return_share: 0.5, continuation_share: 0, waited_share: 0.5, on_the_way_share: 0, ...o });
const profitability: FccCommuteProfit = {
  cost_per_km: 0.8, overall: stats(),
  by_destination: [{ destination: "קיסריה", ...stats({ rides: 1, gross_per_km: 24, on_the_way_share: 1, empty_return_share: 0 }), classes: [], kinds: ["ride"], vs_average_per_km: 21.5 },
    { destination: "נתב״ג", ...stats(), classes: ["large"], kinds: ["delivery"], vs_average_per_km: -0.3 }],
  by_class: [{ class: "large", label: "גדול", ...stats() }], by_kind: [{ kind: "delivery", label: "משלוח", ...stats() }], by_way: [{ on_the_way: true, label: "על הדרך", ...stats() }],
};
const view: FccCommute = {
  month: "2026-11", today: "2026-11-17", routes: [route], own_trips: [{ id: "o1", name: "עבודה", weekdays: ["ראשון", "שלישי"], km_one_way: 30, minutes_one_way: 25 }], income_this_month: 970, default_cost_per_km: 0.8,
  one_off: { month: "2026-11", trips: 2, income: 320 }, unanswered_past: 4, profitability, settings: { free_km: 1000, free_fuel: 300, fuel_cost_per_km: 0.5, cost_per_km: 0.8, other_km_used: 400, other_km_month: "2026-11" },
  quota: { month: "2026-11", allowed_km: 600, free_km: 1000, fuel_km: 600, other_km: 400, other_km_stale: false, rides_km: 100, rides_without_km: 1, used_km: 500, remaining_km: 100, over_km: 0, days_left: 14, km_per_day_left: 7.1, avg_per_km: 2.2, worth_of_remaining: 220, fuel_note: null },
  trips: [
    { id: "t1", date: "2026-11-12", weekday: "חמישי", route: "נסיעה", one_off: false, kind: "ride", outcome: "yes", stops: 3, amount: 130, vehicle_class: null, return_status: "empty", on_the_way_of: null, km: 44, minutes: 70, gross_per_hour: 111.43, gross_per_km: 2.95, net_per_hour: null },
    { id: "t2", date: "2026-11-13", weekday: "שישי", route: "נסיעה", one_off: false, kind: "ride", outcome: "no", stops: null, amount: 0, vehicle_class: null, return_status: null, on_the_way_of: null, km: null, minutes: null, gross_per_hour: null, gross_per_km: null, net_per_hour: null },
    { id: "t3", date: "2026-11-09", weekday: "שני", route: "קיסריה", one_off: true, kind: "delivery", outcome: "yes", stops: null, amount: 120, vehicle_class: "large", return_status: "empty", on_the_way_of: "עבודה", km: 5, minutes: 12, gross_per_hour: 600, gross_per_km: 24, net_per_hour: 580 },
  ],
};
const noop = () => undefined;
const render = (data: FccCommute, error: string | null = null) => renderToStaticMarkup(createElement(CommuteView, { data, busy: false, error, onAnswer: noop, onSaveRoute: noop, onSaveTrip: noop, onSaveSettings: noop }));

test("answers: the pressed button, the request body and the day label", () => {
  assert.equal(ANSWERS.map((a) => a.label).join("|"), "אין נסיעה|2 תחנות|3 תחנות");
  assert.equal(answerOf(route.days[0]), "3");
  assert.equal(answerOf(route.days[1]), null);
  assert.equal(answerOf(day("2026-11-10", { outcome: "no" })), "no");
  assert.equal(JSON.stringify(answerBody("recR", "2026-11-18", "3")), JSON.stringify({ route_id: "recR", date: "2026-11-18", outcome: "yes", stops: 3 }));
  assert.equal(JSON.stringify(answerBody("recR", "2026-11-18", "no")), JSON.stringify({ route_id: "recR", date: "2026-11-18", outcome: "no" }));
  assert.ok(dayLabel(route.days[0]).startsWith("מחר · יום רביעי 18/11"));
});

test("summary: what to collect (routes + one-off), ride days and the days without an answer", () => {
  const s = summaryModel(view);
  assert.equal(s.cards[0].label, "לגבות בסוף החודש");
  assert.ok(s.cards[0].value.includes("970") && s.cards[0].hint!.includes("5 ימי נסיעה קבועה") && s.cards[0].hint!.includes("2 נסיעות/משלוחים נוספים") && s.cards[0].hint!.includes("1 ימים בלי נסיעה"));
  assert.equal(s.cards[2].value, "4");
});

test("economics: inside the allowance (gross) and beyond it (net); unknown stays unknown, never zero", () => {
  const rows = Object.fromEntries(economicsRows(route).map((r) => [r.label, r.value]));
  assert.equal(rows["נטו ליום (מעל המכסה)"], "—");
  assert.ok(rows["בתוך המכסה — לשעה"].includes("111"));
  assert.equal(economicsHint(route), null);
  assert.equal(weekRows(route)[0].days, "5");
  const t = tripRows(view);
  assert.equal(t[0].result, "3 תחנות");
  assert.equal(t[1].amount, "—");
  assert.ok(t[2].result === "משלוח" && t[2].detail.includes("על הדרך של עבודה") && t[2].detail.includes("גדול") && t[2].perKm.includes("24"));
});

test("allowance: what is left, the stale warning and an unset allowance", () => {
  const q = quotaRows(view.quota)!;
  const rows = Object.fromEntries(q.rows.map((r) => [r.label, r.value]));
  assert.ok(rows["נותר מהמכסה"].includes("100") && rows["מכסה חינם החודש (ק\"מ)"].includes("600"));
  assert.ok(q.notes.some((n) => n.includes("1 נסיעות בלי ק\"מ")));
  const over = quotaRows({ ...view.quota!, over_km: 12, remaining_km: 0, other_km_stale: true })!;
  assert.ok(over.rows.some((r) => r.value.includes("חריגה של 12")) && over.notes.some((n) => n.includes("מחודש קודם")));
  assert.equal(quotaRows(null), null);
});

test("profitability: ranked rows with a number against the average (never a verdict), groups, the cost note", () => {
  const p = profitModel(profitability);
  assert.equal(p.destinations[0].label, "קיסריה");
  assert.ok(p.destinations[0].extra.includes("+") && p.destinations[0].extra.includes("100% על הדרך"));
  assert.ok(p.destinations[1].label.includes("(משלוח)") && p.destinations[1].extra.includes("−"));
  assert.equal(p.groups.length, 3);
  assert.ok(p.note.includes("נטו"));
  assert.ok(profitModel({ ...profitability, cost_per_km: null }).note.includes("הזינו עלות"));
});

test("route form: blank is left out, bad is an error, a new paid route needs a name and a price, an own drive needs no price", () => {
  assert.ok("error" in routeBody(EMPTY_FORM));
  const ok = routeBody({ ...EMPTY_FORM, name: " נסיעה ", price: "130", km: "22", minutes: "35", cls: "large", ret: "waited", waiting: "90" });
  assert.ok("body" in ok && ok.body.name === "נסיעה" && ok.body.price === 130 && ok.body.cost_per_km === undefined && ok.body.planned_days === 6 && ok.body.vehicle_class === "large" && ok.body.return_status === "waited" && ok.body.waiting_minutes === 90);
  assert.ok("error" in routeBody({ ...EMPTY_FORM, name: "x", price: "12a" }));
  assert.ok("error" in routeBody({ ...EMPTY_FORM, name: "x", price: "5", days: "9" }));
  const edit = routeBody({ ...EMPTY_FORM, days: "", cost: "0.8" }, "recR");
  assert.ok("body" in edit && edit.body.route_id === "recR" && edit.body.cost_per_km === 0.8 && edit.body.name === undefined);
  const own = routeBody({ ...EMPTY_OWN_FORM, name: "עבודה", km: "30", weekdays: ["ראשון", "שלישי"] });
  assert.ok("body" in own && own.body.route_kind === "own" && own.body.price === undefined && own.body.weekdays!.length === 2 && own.body.return_status === undefined);
});

test("one-off trip form: the price is typed each time; on the way needs a name and sends the detour; the way back and the wait", () => {
  const f = emptyTripForm("2026-11-17");
  assert.ok("error" in tripBody(f) && "error" in tripBody({ ...f, destination: "נתב״ג" }));
  const ok = tripBody({ ...f, destination: " נתב״ג ", price: "220", cls: "large", km: "50", minutes: "40", ret: "waited", waiting: "120" });
  assert.ok("body" in ok && ok.body.destination === "נתב״ג" && ok.body.price === 220 && ok.body.vehicle_class === "large" && ok.body.return_status === "waited" && ok.body.waiting_minutes === 120 && ok.body.date === "2026-11-17" && ok.body.kind === "ride");
  const way = tripBody({ ...f, destination: "קיסריה", price: "120", kind: "delivery", onWay: "עבודה", extraKm: "5", extraMinutes: "12" });
  assert.ok("body" in way && way.body.on_the_way_of === "עבודה" && way.body.extra_km === 5 && way.body.extra_minutes === 12 && way.body.kind === "delivery");
  assert.ok("error" in tripBody({ ...f, destination: "x", price: "5", extraKm: "5" }) && "error" in tripBody({ ...f, destination: "x", price: "5a" }));
  const notWaited = tripBody({ ...f, destination: "x", price: "5", ret: "empty", waiting: "99" });
  assert.ok("body" in notWaited && notWaited.body.waiting_minutes === undefined);
});

test("settings form: shows what is saved, blank is left out, nothing to save is an error", () => {
  const f = formFromSettings(view.settings);
  assert.equal(f.freeKm, "1000");
  assert.ok("error" in settingsBody({ freeKm: "", freeFuel: "", fuelCost: "", costPerKm: "", otherKm: "" }) && "error" in settingsBody({ ...f, freeKm: "10x" }));
  const ok = settingsBody({ freeKm: "1000", freeFuel: "", fuelCost: "0.5", costPerKm: "", otherKm: "400" });
  assert.ok("body" in ok && ok.body.free_km === 1000 && ok.body.fuel_cost_per_km === 0.5 && ok.body.other_km_used === 400 && ok.body.free_fuel === undefined);
  assert.equal(formFromSettings(null).freeKm, "");
});

test("view: allowance, tomorrow with three buttons (the pressed one marked), profitability, trips, the forms; empty states", () => {
  const html = render(view);
  assert.ok(html.includes("מכסת הרכב") && html.includes("יש נסיעה?") && html.includes('aria-pressed="true"') && html.includes("אילו נסיעות השתלמו") && html.includes("טבלת נסיעות"));
  assert.ok(html.includes("הוספת נסיעה / משלוח") && html.includes("הנסיעות הקבועות שלי") && html.includes("הגדרות הרכב") && html.includes("הוספת מסלול קבוע בתשלום") && html.includes("על הדרך של עבודה"));
  const empty = render({ ...view, routes: [], trips: [], own_trips: [], quota: null, settings: null, one_off: { month: "2026-11", trips: 0, income: 0 }, profitability: { ...profitability, by_destination: [], by_class: [], by_kind: [], by_way: [], overall: null } }, "אופס");
  assert.ok(empty.includes("אין נסיעה קבועה עדיין") && empty.includes("אופס") && empty.includes("עוד לא הוגדרה מכסה") && empty.includes("עוד אין נסיעות שנרשמו להשוואה"));
});

if (failures) throw new Error(`${failures} fccCommute test(s) failed`);
console.log("all fccCommute tests passed");
