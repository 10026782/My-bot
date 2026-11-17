import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { CommuteView } from "../components/FccCommute";
import {
  ANSWERS, EMPTY_FORM, EMPTY_OWN_FORM, evaluateBody, evaluationModel, pendingRows, returnBody, returnModel, timeModel, answerBody, answerOf, dayLabel, economicsHint, economicsRows, emptyTripForm, formFromSettings, profitModel, quotaRows, routeBody, settingsBody, summaryModel,
  tripBody, tripRows, weekRows,
} from "./fccCommute";
import type { FccCommute, FccCommuteDay, FccCommuteEvaluation, FccCommuteProfit, FccCommuteRoute, FccCommuteStats } from "../types";

let failures = 0;
const assert = {
  equal: (a: unknown, b: unknown) => { if (a !== b) throw new Error(`expected ${JSON.stringify(b)}, got ${JSON.stringify(a)}`); },
  ok: (v: unknown) => { if (!v) throw new Error("not ok"); },
};
function test(name: string, fn: () => void) { try { fn(); console.log(`ok - ${name}`); } catch (e) { failures++; console.error(`not ok - ${name}: ${(e as Error).message}`); } }

const day = (date: string, o: Partial<FccCommuteDay> = {}): FccCommuteDay => ({ date, weekday: "רביעי", is_tomorrow: false, is_today: false, rest_day: false, outcome: null, stops: null, trip_id: null, ...o });
const route: FccCommuteRoute = {
  id: "recR", name: "נסיעה", kind: "paid", weekdays: [], price: 130, km_one_way: 22, minutes_one_way: 35, cost_per_km: null, planned_days: 6, active: true, notes: null, vehicle_class: null, return_status: "empty", waiting_minutes: 0, start_time: "06:30",
  economics: { price: 130, km_per_day: 44, minutes_per_day: 70, hours_per_day: 1.17, gross_per_hour: 111.43, gross_per_km: 2.95, vehicle_cost_per_day: null, net_per_day: null, net_per_hour: null, net_per_km: null, monthly_potential: 3380, return_status: "empty", vehicle_class: null },
  days: [day("2026-11-18", { is_tomorrow: true, outcome: "yes", stops: 3 }), day("2026-11-16")],
  this_month: { month: "2026-11", yes_days: 5, no_days: 1, income: 650, stops: { "2": 3, "3": 2 }, stops_recorded: 5, three_share: 0.4, weeks: [{ week_start: "2026-11-08", yes_days: 5, income: 650 }] },
  history: [], stops_note: null,
};
const stats = (o: Partial<FccCommuteStats> = {}): FccCommuteStats => ({ rides: 2, avg_price: 185, measured_rides: 2, gross_per_hour: 120, gross_per_km: 2.5, net_per_hour: 90, net_per_km: 1.7, empty_return_share: 0.5, continuation_share: 0, waited_share: 0.5, on_the_way_share: 0, ...o });
const profitability: FccCommuteProfit = {
  cost_per_km: 0.8, overall: stats(), without_time: 1,
  by_time: [{ band: "morning_rush", label: "בוקר (שעת עומס)", ...stats({ rides: 2 }), avg_minutes: 63 }, { band: "midday", label: "צהריים", ...stats({ rides: 2 }), avg_minutes: 29 }],
  time_insights: [{ destination: "תל אביב", fastest: "midday", slowest: "morning_rush", extra_minutes: 34, bands: [{ band: "midday", label: "צהריים", rides: 2, avg_minutes: 29, gross_per_hour: 310.34, gross_per_km: 5, avg_price: 150 }, { band: "morning_rush", label: "בוקר (שעת עומס)", rides: 2, avg_minutes: 63, gross_per_hour: 142.86, gross_per_km: 5, avg_price: 150 }] }],
  by_destination: [{ destination: "קיסריה", ...stats({ rides: 1, gross_per_km: 24, on_the_way_share: 1, empty_return_share: 0 }), classes: [], kinds: ["ride"], vs_average_per_km: 21.5 },
    { destination: "נתב״ג", ...stats(), classes: ["large"], kinds: ["delivery"], vs_average_per_km: -0.3 }],
  by_class: [{ class: "large", label: "גדול", ...stats() }], by_kind: [{ kind: "delivery", label: "משלוח", ...stats() }], by_way: [{ on_the_way: true, label: "על הדרך", ...stats() }],
};
const view: FccCommute = {
  pending_updates: [{ id: "recP", date: "2026-11-16", weekday: "שני", destination: "נתב״ג", price: 220, km_one_way: 50, minutes_one_way: 40, start_time: "07:30", kind: "ride" }],
  return_stats: { overall: { known: 12, empty: 5, continuation: 4, waited: 3, avg_wait_minutes: 80 }, by_destination: [{ destination: "נתב״ג", known: 8, empty: 3, continuation: 3, waited: 2, avg_wait_minutes: 90 }], min_destination: 5, min_overall: 10 },
  month: "2026-11", today: "2026-11-17", routes: [route], own_trips: [{ id: "o1", name: "עבודה", weekdays: ["ראשון", "שלישי"], km_one_way: 30, minutes_one_way: 25 }], income_this_month: 970, default_cost_per_km: 0.8,
  one_off: { month: "2026-11", trips: 2, income: 320 }, unanswered_past: 4, profitability, settings: { free_km: 1000, free_fuel: 300, fuel_cost_per_km: 0.5, cost_per_km: 0.8, other_km_used: 400, other_km_month: "2026-11" },
  quota: { month: "2026-11", allowed_km: 600, free_km: 1000, fuel_km: 600, other_km: 400, other_km_stale: false, rides_km: 100, rides_without_km: 1, used_km: 500, remaining_km: 100, over_km: 0, days_left: 14, km_per_day_left: 7.1, avg_per_km: 2.2, worth_of_remaining: 220, fuel_note: null },
  trips: [
    { id: "t1", date: "2026-11-12", weekday: "חמישי", route: "נסיעה", one_off: false, kind: "ride", outcome: "yes", stops: 3, amount: 130, vehicle_class: null, return_status: "empty", on_the_way_of: null, start_time: "06:30", band: "morning_rush", km: 44, minutes: 70, gross_per_hour: 111.43, gross_per_km: 2.95, net_per_hour: null },
    { id: "t2", date: "2026-11-13", weekday: "שישי", route: "נסיעה", one_off: false, kind: "ride", outcome: "no", stops: null, amount: 0, vehicle_class: null, return_status: null, on_the_way_of: null, start_time: null, band: null, km: null, minutes: null, gross_per_hour: null, gross_per_km: null, net_per_hour: null },
    { id: "t3", date: "2026-11-09", weekday: "שני", route: "קיסריה", one_off: true, kind: "delivery", outcome: "yes", stops: null, amount: 120, vehicle_class: "large", return_status: "empty", on_the_way_of: "עבודה", start_time: "17:45", band: "evening_rush", km: 5, minutes: 12, gross_per_hour: 600, gross_per_km: 24, net_per_hour: 580 },
  ],
};
const noop = () => undefined;
const evaluation: FccCommuteEvaluation = {
  offer: { destination: "נתב״ג", price: 220, km_one_way: 50, minutes_one_way: 40, start_time: "07:30", on_the_way: false },
  scenarios: [
    { key: "empty", label: "חזרה ריקה", km: 100, minutes: 80, gross_per_hour: 165, gross_per_km: 2.2, net_per_hour: 105, net_per_km: 1.4, net: 140, free_km: 100, beyond_km: 0, cost_beyond: 0, net_after_allowance: 220 },
    { key: "continuation", label: "יש נסיעת המשך (המחיר לכיוון אחד)", km: 50, minutes: 40, gross_per_hour: 330, gross_per_km: 4.4, net_per_hour: 270, net_per_km: 3.6, net: 180, free_km: 50, beyond_km: 0, cost_beyond: 0, net_after_allowance: 220 },
    { key: "waited", label: "המתנה של 120 דק׳", km: 100, minutes: 200, gross_per_hour: 66, gross_per_km: 2.2, net_per_hour: 42, net_per_km: 1.4, net: 140, free_km: 60, beyond_km: 40, cost_beyond: 32, net_after_allowance: 188 },
  ],
  expected: { key: "expected", label: "צפוי (לפי ההיסטוריה שלך)", km: 85, minutes: 110, gross_per_hour: 120, gross_per_km: 2.59, net_per_hour: 80, net_per_km: 1.8, net: 152, free_km: 85, beyond_km: 0, cost_beyond: 0, net_after_allowance: 220 },
  basis: { used: "destination", destination_sample: 8, overall_sample: 12, weights: { empty: 0.5, continuation: 0.3, waited: 0.2 } }, average: { gross_per_km: 2.1, gross_per_hour: 100, rides: 12 }, vs_average: { per_km: 0.49, per_hour: 20 },
  typical_at_this_hour: { band: "בוקר (שעת עומס)", rides: 3, avg_minutes_one_way: 55 }, allowance_remaining_km: 440, cost_per_km: 0.8, notes: ["הערה לדוגמה"],
};
const render = (data: FccCommute, error: string | null = null, ev: FccCommuteEvaluation | null = null) =>
  renderToStaticMarkup(createElement(CommuteView, { data, busy: false, error, evaluation: ev, onAnswer: noop, onSaveRoute: noop, onSaveTrip: noop, onSaveSettings: noop, onEvaluate: noop, onReturn: noop }));

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

test("time of day: bands, the traffic fact per destination (minutes and ₪ per hour of each band), the trips without a time, the start time in the forms", () => {
  const t = timeModel(profitability);
  assert.equal(t.rows.length, 2);
  assert.equal(t.rows[0].avgMinutes.includes("63"), true);
  assert.ok(t.insights[0].title.includes("תל אביב") && t.insights[0].title.includes("34") && t.insights[0].detail.includes("29 דק׳"));
  assert.ok(t.note!.includes("1 נסיעות בלי שעת יציאה"));
  assert.equal(timeModel({ ...profitability, without_time: 0, by_time: [], time_insights: [] }).note, null);
  assert.ok(tripRows(view)[0].detail.includes("יציאה 06:30"));
  const f = emptyTripForm("2026-11-17");
  const ok = tripBody({ ...f, destination: "תל אביב", price: "150", start: "07:45", km: "30", minutes: "60" });
  assert.ok("body" in ok && ok.body.start_time === "07:45");
  assert.ok("error" in tripBody({ ...f, destination: "x", price: "5", start: "7pm" }) && "error" in routeBody({ ...EMPTY_FORM, name: "x", price: "5", start: "25:00" }));
  const r = routeBody({ ...EMPTY_FORM, name: "x", price: "5", start: "06:30" });
  assert.ok("body" in r && r.body.start_time === "06:30");
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

test("an offer: the price is required, only the detour counts on the way, the expected figure comes with its sample, the three ways back side by side", () => {
  const f = emptyTripForm("2026-11-17");
  assert.ok("error" in evaluateBody(f) && "error" in evaluateBody({ ...f, price: "0" }) && "error" in evaluateBody({ ...f, price: "5a" }));
  const ok = evaluateBody({ ...f, price: "220", destination: " נתב״ג ", km: "50", minutes: "40", start: "07:30", ret: "waited", waiting: "120" });
  assert.ok("body" in ok && ok.body.price === 220 && ok.body.km_one_way === 50 && ok.body.minutes_one_way === 40 && ok.body.start_time === "07:30" && ok.body.waiting_minutes === 120 && ok.body.destination === "נתב״ג");
  const sure = evaluateBody({ ...f, price: "220", km: "50", ret: "empty", waiting: "99" });
  assert.ok("body" in sure && sure.body.waiting_minutes === undefined);
  const way = evaluateBody({ ...f, price: "120", onWay: "עבודה", km: "30", extraKm: "5", extraMinutes: "12" });
  assert.ok("body" in way && way.body.extra_km === 5 && way.body.km_one_way === undefined && way.body.extra_minutes === 12);
  assert.ok("error" in evaluateBody({ ...f, price: "120", onWay: "עבודה" }) && "error" in evaluateBody({ ...f, price: "5", start: "7pm" }));
  const e = evaluationModel(evaluation);
  assert.ok(e.headline!.startsWith("צפוי") && e.rows.length === 3 && e.expected!.key === "expected" && e.basis!.includes("8 נסיעות קודמות ליעד") && e.basis!.includes("50%"));
  assert.ok(e.vsAverage!.includes("+") && e.typical!.includes("55 דק׳") && e.allowance!.includes("440") && e.notes[0] === "הערה לדוגמה");
  assert.ok(e.rows[2].allowance.includes("חורג ב-40") && e.rows[0].allowance === "בתוך המכסה");
  const thin = evaluationModel({ ...evaluation, expected: null, basis: { used: null, destination_sample: 1, overall_sample: 2, weights: null } });
  assert.ok(thin.headline!.startsWith("בין") && thin.expected === null && thin.basis === null);
  const overall = evaluationModel({ ...evaluation, basis: { ...evaluation.basis, used: "overall" } });
  assert.ok(overall.basis!.includes("אין מספיק היסטוריה"));
  const html = render(view, null, evaluation);
  assert.ok(html.includes("תרחישי חזרה") && html.includes("צפוי (לפי ההיסטוריה שלך)") && html.includes("בתוך המכסה"));
});

test("the way back is learned over time: trips wait for the update, the body, the history table and its caveat", () => {
  const p = pendingRows(view.pending_updates);
  assert.ok(p[0].title.includes("נתב״ג") && p[0].title.includes("16/11") && p[0].detail.includes("50 ק\"מ") && p[0].detail.includes("יציאה 07:30"));
  const empty = returnBody("recP", "empty");
  assert.ok("body" in empty && empty.body.trip_id === "recP" && empty.body.return_status === "empty" && empty.body.waiting_minutes === undefined);
  const waited = returnBody("recP", "waited", "90");
  assert.ok("body" in waited && waited.body.waiting_minutes === 90 && "error" in returnBody("recP", "waited", "") && "error" in returnBody("recP", "waited", "x"));
  const r = returnModel(view.return_stats);
  assert.equal(r.rows[0].label, "הכול");
  assert.ok(r.rows[0].empty === "42%" && r.rows[0].waited.includes("25%") && r.rows[0].waited.includes("80") && r.rows[1].known === "8");
  assert.ok(r.note.includes("אקראי ועם תחרות") && r.note.includes("5 נסיעות") && r.note.includes("10 בסך הכול"));
  const html = render(view);
  assert.ok(html.includes("חזרתי ריק") && html.includes("היה המשך") && html.includes("ישבתי בצד"));
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
  assert.ok(html.includes("פקקים: איך שעת היציאה משנה") && html.includes("מכסת הרכב") && html.includes("יש נסיעה?") && html.includes('aria-pressed="true"') && html.includes("אילו נסיעות השתלמו") && html.includes("טבלת נסיעות"));
  assert.ok(html.includes("הצעה לנסיעה — כדאי?") && html.includes("ממתינות לעדכון") && html.includes("מה קורה בדרך חזרה") && html.includes("קיבלתי — שמירה כנסיעה") && html.includes("הנסיעות הקבועות שלי") && html.includes("הגדרות הרכב") && html.includes("הוספת מסלול קבוע בתשלום") && html.includes("על הדרך של עבודה"));
  const empty = render({ ...view, routes: [], trips: [], own_trips: [], quota: null, settings: null, one_off: { month: "2026-11", trips: 0, income: 0 }, profitability: { ...profitability, by_destination: [], by_class: [], by_kind: [], by_way: [], overall: null } }, "אופס");
  assert.ok(empty.includes("אין נסיעה קבועה עדיין") && empty.includes("אופס") && empty.includes("עוד לא הוגדרה מכסה") && empty.includes("עוד אין נסיעות שנרשמו להשוואה"));
});

if (failures) throw new Error(`${failures} fccCommute test(s) failed`);
console.log("all fccCommute tests passed");
