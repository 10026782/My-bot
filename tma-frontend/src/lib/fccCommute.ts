// Pure presentation of the commute tab (rides answered day by day, one-off trips and deliveries, the leased car's free allowance). All numbers come from the server;
// this file only words them and turns typed text into a request body. Unknown stays unknown: a missing km / minutes / cost is shown as "—", never as zero.
import type {
  CommuteClass, CommuteKind, CommuteReturn, FccCommute, FccCommuteDay, FccCommuteProfit, FccCommuteQuota, FccCommuteRoute, FccCommuteRouteBody, FccCommuteSettingsBody, FccCommuteStats,
  FccCommuteTripBody,
} from "../types";
import { money } from "./fccPresentation";

export const UNKNOWN = "—";
export const COMMUTE_TITLE = "נסיעות";
export type AnswerKey = "no" | "2" | "3";
export const ANSWERS: { key: AnswerKey; label: string }[] = [
  { key: "no", label: "אין נסיעה" },
  { key: "2", label: "2 תחנות" },
  { key: "3", label: "3 תחנות" },
];
export const CLASS_OPTIONS: { value: CommuteClass | ""; label: string }[] = [{ value: "", label: "לא צוין" }, { value: "regular", label: "רגיל" }, { value: "large", label: "גדול (6 נוסעים)" }];
export const RETURN_OPTIONS: { value: CommuteReturn; label: string; hint: string }[] = [
  { value: "empty", label: "חוזר ריק — המחיר כולל חזור", hint: "הלוך ושוב, החזרה בלי נוסע" },
  { value: "waited", label: "מחכה שעות — המחיר כולל חזור והמתנה", hint: "הלוך ושוב + דקות המתנה" },
  { value: "continuation", label: "יש נסיעת המשך/חזור בתשלום", hint: "המחיר הזה הוא לכיוון אחד בלבד" },
];
export const KIND_OPTIONS: { value: CommuteKind; label: string }[] = [{ value: "ride", label: "נסיעה" }, { value: "delivery", label: "משלוח" }];
export const WEEKDAYS = ["ראשון", "שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת"];

export const dmy = (iso: string): string => `${iso.slice(8, 10)}/${iso.slice(5, 7)}`;
export const dayLabel = (d: FccCommuteDay): string => `${d.is_tomorrow ? "מחר · " : d.is_today ? "היום · " : ""}יום ${d.weekday} ${dmy(d.date)}`;

/** The pressed button of a day: "no", "2", "3", or null while it is not answered. */
export function answerOf(d: FccCommuteDay): AnswerKey | null {
  if (d.outcome === "no") return "no";
  if (d.outcome === "yes") return d.stops === 3 ? "3" : d.stops === 2 ? "2" : null;
  return null;
}

export function answerBody(routeId: string, date: string, key: AnswerKey): { route_id: string; date: string; outcome: "yes" | "no"; stops?: number } {
  return key === "no" ? { route_id: routeId, date, outcome: "no" } : { route_id: routeId, date, outcome: "yes", stops: Number(key) };
}

const num = (n: number | null | undefined, unit = ""): string => (n == null ? UNKNOWN : `${new Intl.NumberFormat("he-IL", { maximumFractionDigits: 2 }).format(n)}${unit}`);
const m = (n: number | null | undefined): string => (n == null ? UNKNOWN : money(n));
const pct = (x: number | null | undefined): string => (x == null ? UNKNOWN : `${Math.round(x * 100)}%`);

export interface CommuteSummary { cards: { key: string; label: string; value: string; hint?: string }[] }

/** The month at a glance: what to collect at the end of the month, how many ride days / trips, and the days still without an answer. */
export function summaryModel(v: FccCommute): CommuteSummary {
  const days = v.routes.reduce((a, r) => a + r.this_month.yes_days, 0);
  const no = v.routes.reduce((a, r) => a + r.this_month.no_days, 0);
  const extra = v.one_off.trips;
  return {
    cards: [
      { key: "collect", label: "לגבות בסוף החודש", value: money(v.income_this_month),
        hint: `${days} ימי נסיעה קבועה${extra ? ` · ${extra} נסיעות/משלוחים נוספים (${money(v.one_off.income)})` : ""}${no ? ` · ${no} ימים בלי נסיעה` : ""}` },
      { key: "days", label: "ימי נסיעה קבועה החודש", value: String(days) },
      { key: "missing", label: "ימים שלא עודכנו", value: String(v.unanswered_past), hint: v.unanswered_past ? "ימים שעברו בלי תשובה לא נספרים בהכנסה" : undefined },
    ],
  };
}

export interface WeekRow { key: string; label: string; days: string; income: string }
export function weekRows(r: FccCommuteRoute): WeekRow[] {
  return r.this_month.weeks.map((w) => ({ key: w.week_start, label: `שבוע מ-${dmy(w.week_start)}`, days: String(w.yes_days), income: money(w.income) }));
}

export interface MetricRow { label: string; value: string }
/** One trip day (there and back): the numbers that say whether the ride is worth it. Gross = while the km are free (inside the allowance); net = beyond it (the owner's cost per km). */
export function economicsRows(r: FccCommuteRoute): MetricRow[] {
  const e = r.economics;
  return [
    { label: "מחיר ליום נסיעה", value: m(e.price) },
    { label: 'ק"מ ליום', value: num(e.km_per_day) },
    { label: "זמן ליום", value: e.minutes_per_day == null ? UNKNOWN : `${num(e.minutes_per_day)} דק׳` },
    { label: 'בתוך המכסה — לשעה', value: m(e.gross_per_hour) },
    { label: 'בתוך המכסה — לק"מ', value: m(e.gross_per_km) },
    { label: "עלות רכב ליום (מעל המכסה)", value: m(e.vehicle_cost_per_day) },
    { label: "נטו ליום (מעל המכסה)", value: m(e.net_per_day) },
    { label: "נטו לשעה (מעל המכסה)", value: m(e.net_per_hour) },
    { label: 'נטו לק"מ (מעל המכסה)', value: m(e.net_per_km) },
    { label: "פוטנציאל חודשי (לפי הימים בשבוע)", value: e.monthly_potential == null ? UNKNOWN : `≈ ${money(e.monthly_potential)}` },
  ];
}

export function economicsHint(r: FccCommuteRoute): string | null {
  const missing = [r.km_one_way == null ? 'ק"מ' : null, r.minutes_one_way == null ? "זמן" : null].filter(Boolean);
  return missing.length ? `חסר: ${missing.join(", ")}` : null;
}

const RETURN_LABEL: Record<CommuteReturn, string> = { empty: "חזרה ריקה", waited: "המתנה", continuation: "יש נסיעת המשך" };
const CLASS_LABEL: Record<CommuteClass, string> = { regular: "רגיל", large: "גדול" };
const KIND_LABEL: Record<CommuteKind, string> = { ride: "נסיעה", delivery: "משלוח" };

export interface TripRow { key: string; date: string; route: string; result: string; detail: string; amount: string; perKm: string }
export function tripRows(v: FccCommute): TripRow[] {
  return v.trips.map((t) => {
    const bits = [t.vehicle_class ? CLASS_LABEL[t.vehicle_class] : null, t.return_status ? RETURN_LABEL[t.return_status] : null, t.on_the_way_of ? `על הדרך של ${t.on_the_way_of}` : null,
      t.km != null ? `${num(t.km)} ק"מ` : null].filter((x): x is string => !!x);
    return {
      key: t.id, date: `${t.weekday} ${dmy(t.date)}`, route: t.route ?? UNKNOWN,
      result: t.outcome === "no" ? "אין נסיעה" : t.one_off ? KIND_LABEL[t.kind] : t.stops ? `${t.stops} תחנות` : "נסיעה",
      detail: bits.join(" · "), amount: t.outcome === "yes" ? money(t.amount) : UNKNOWN, perKm: t.outcome === "yes" ? m(t.gross_per_km) : UNKNOWN,
    };
  });
}

/** The leased car's free allowance this month. */
export function quotaRows(q: FccCommuteQuota | null): { rows: MetricRow[]; notes: string[] } | null {
  if (!q) return null;
  const notes = [q.fuel_note, q.other_km_stale ? 'ה"ק"מ אחרים" שהוזנו הם מחודש קודם — לא נספרו; עדכנו אותם' : null,
    q.rides_without_km ? `${q.rides_without_km} נסיעות בלי ק"מ לא נספרו במכסה` : null].filter((x): x is string => !!x);
  return {
    rows: [
      { label: 'מכסה חינם החודש (ק"מ)', value: num(q.allowed_km) },
      { label: 'ק"מ אחרים שהוזנו', value: num(q.other_km) },
      { label: 'ק"מ מנסיעות ומשלוחים', value: num(q.rides_km) },
      { label: "נותר מהמכסה", value: q.over_km ? `חריגה של ${num(q.over_km)} ק"מ` : num(q.remaining_km, ' ק"מ') },
      { label: 'נותר ליום (ק"מ)', value: num(q.km_per_day_left) },
      { label: 'ממוצע ₪ לק"מ החודש', value: m(q.avg_per_km) },
      { label: "שווי המכסה שנותרה במחיר הממוצע (הערכה)", value: q.worth_of_remaining == null ? UNKNOWN : `≈ ${money(q.worth_of_remaining)}` },
    ],
    notes,
  };
}

export interface ProfitRow { key: string; label: string; rides: string; avgPrice: string; perKm: string; perHour: string; netPerHour: string; extra: string }
const profitRow = (key: string, label: string, s: FccCommuteStats, extra = ""): ProfitRow =>
  ({ key, label, rides: String(s.rides), avgPrice: m(s.avg_price), perKm: m(s.gross_per_km), perHour: m(s.gross_per_hour), netPerHour: m(s.net_per_hour), extra });

/** Which rides were worth it, best ₪ per allowance-km first. "vs average" is a number, never a verdict: the owner decides. */
export function profitModel(p: FccCommuteProfit): { destinations: ProfitRow[]; groups: ProfitRow[]; overall: ProfitRow | null; note: string } {
  const dest = p.by_destination.map((d) => {
    const parts = [d.vs_average_per_km == null ? "" : `${d.vs_average_per_km >= 0 ? "+" : "−"}${money(Math.abs(d.vs_average_per_km))} לק"מ מהממוצע`,
      d.empty_return_share ? `${pct(d.empty_return_share)} חזרה ריקה` : "", d.waited_share ? `${pct(d.waited_share)} המתנה` : "", d.on_the_way_share ? `${pct(d.on_the_way_share)} על הדרך` : ""].filter(Boolean);
    return profitRow(d.destination, `${d.destination}${d.kinds.includes("delivery") ? " (משלוח)" : ""}`, d, parts.join(" · "));
  });
  const groups = [...p.by_class.map((c) => profitRow(`c-${c.class}`, `מחיר ${c.label}`, c)), ...p.by_kind.map((k) => profitRow(`k-${k.kind}`, k.label, k)),
    ...p.by_way.map((w) => profitRow(`w-${w.on_the_way}`, w.label, w))];
  return {
    destinations: dest, groups, overall: p.overall ? profitRow("all", "הכול", p.overall) : null,
    note: p.cost_per_km == null ? 'בתוך המכסה ק"מ עולה אפס, ולכן "בתוך המכסה" הוא הרווח עצמו. להוספת "נטו" מעל המכסה — הזינו עלות לק"מ בהגדרות הרכב.'
      : `בתוך המכסה ק"מ עולה אפס ("בתוך המכסה" הוא הרווח); מעל המכסה כל ק"מ עולה ${money(p.cost_per_km)} ("נטו").`,
  };
}

// ── forms: typed text -> request body (a blank number is left out, never silently 0; an invalid one is an error) ──
const parseNum = (text: string): number | null | "bad" => {
  const t = text.replace(/[₪,\s]/g, "");
  if (t === "") return null;
  if (!/^\d+(\.\d+)?$/.test(t)) return "bad";
  return Number(t);
};
type Spec<B> = [keyof B, string, string][];
function fill<B extends object>(body: B, spec: Spec<B>): string | null {
  for (const [key, text, label] of spec) {
    const v = parseNum(text);
    if (v === "bad") return `ערך לא תקין: ${label}`;
    if (v != null) (body as Record<string, unknown>)[key as string] = v;
  }
  return null;
}

export interface RouteForm { name: string; price: string; km: string; minutes: string; cost: string; days: string; cls: CommuteClass | ""; ret: CommuteReturn; waiting: string; own: boolean; weekdays: string[] }
export const EMPTY_FORM: RouteForm = { name: "", price: "", km: "", minutes: "", cost: "", days: "6", cls: "", ret: "empty", waiting: "", own: false, weekdays: [] };
export const EMPTY_OWN_FORM: RouteForm = { ...EMPTY_FORM, days: "", own: true };
export const formFromRoute = (r: FccCommuteRoute): RouteForm => ({
  name: r.name, price: r.price == null ? "" : String(r.price), km: r.km_one_way == null ? "" : String(r.km_one_way), minutes: r.minutes_one_way == null ? "" : String(r.minutes_one_way),
  cost: r.cost_per_km == null ? "" : String(r.cost_per_km), days: r.planned_days == null ? "" : String(r.planned_days), cls: r.vehicle_class ?? "", ret: r.return_status,
  waiting: r.waiting_minutes ? String(r.waiting_minutes) : "", own: r.kind === "own", weekdays: r.weekdays,
});

/** A new paid route needs a name and a price; an own weekly drive needs only a name (and the weekdays are for the list). */
export function routeBody(form: RouteForm, routeId?: string): { body: FccCommuteRouteBody } | { error: string } {
  const body: FccCommuteRouteBody = routeId ? { route_id: routeId } : {};
  if (form.name.trim()) body.name = form.name.trim();
  const err = fill(body, [["price", form.own ? "" : form.price, "מחיר"], ["km_one_way", form.km, 'ק"מ'], ["minutes_one_way", form.minutes, "דקות"], ["cost_per_km", form.cost, 'עלות לק"מ'],
    ["planned_days", form.days, "ימים בשבוע"], ["waiting_minutes", form.waiting, "דקות המתנה"]]);
  if (err) return { error: err };
  if (!form.own) { if (form.cls) body.vehicle_class = form.cls; body.return_status = form.ret; } else { body.route_kind = "own"; if (form.weekdays.length) body.weekdays = form.weekdays; }
  if (!routeId && !body.name) return { error: "צריך שם" };
  if (!routeId && !form.own && body.price == null) return { error: "מסלול חדש צריך שם ומחיר ליום נסיעה" };
  if (body.planned_days != null && (body.planned_days < 1 || body.planned_days > 7)) return { error: "ימים בשבוע: בין 1 ל-7" };
  return { body };
}

export interface TripForm { destination: string; date: string; price: string; cls: CommuteClass | ""; kind: CommuteKind; km: string; minutes: string; ret: CommuteReturn; waiting: string; onWay: string; extraKm: string; extraMinutes: string }
export const emptyTripForm = (today: string): TripForm => ({ destination: "", date: today, price: "", cls: "", kind: "ride", km: "", minutes: "", ret: "empty", waiting: "", onWay: "", extraKm: "", extraMinutes: "" });

/** One typed trip: the price is typed every time (there is no price list). "On the way" = the km / minutes it ADDED replace the one-way based ones. */
export function tripBody(form: TripForm): { body: FccCommuteTripBody } | { error: string } {
  if (!form.destination.trim()) return { error: "צריך יעד" };
  const body: FccCommuteTripBody = { destination: form.destination.trim(), kind: form.kind };
  if (/^\d{4}-\d{2}-\d{2}$/.test(form.date)) body.date = form.date;
  const err = fill(body, [["price", form.price, "מחיר"], ["km_one_way", form.km, 'ק"מ'], ["minutes_one_way", form.minutes, "דקות"], ["waiting_minutes", form.ret === "waited" ? form.waiting : "", "דקות המתנה"],
    ["extra_km", form.extraKm, 'ק"מ עיקוף'], ["extra_minutes", form.extraMinutes, "דקות עיקוף"]]);
  if (err) return { error: err };
  if (body.price == null) return { error: "צריך מחיר" };
  if (form.cls) body.vehicle_class = form.cls;
  body.return_status = form.ret;
  if (form.onWay) body.on_the_way_of = form.onWay;
  if (body.extra_km != null && !form.onWay) return { error: "ק״מ עיקוף שייכים לנסיעה על הדרך — בחרו על הדרך של איזו נסיעה" };
  return { body };
}

export interface SettingsForm { freeKm: string; freeFuel: string; fuelCost: string; costPerKm: string; otherKm: string }
export const formFromSettings = (s: FccCommute["settings"]): SettingsForm => ({
  freeKm: s?.free_km == null ? "" : String(s.free_km), freeFuel: s?.free_fuel == null ? "" : String(s.free_fuel), fuelCost: s?.fuel_cost_per_km == null ? "" : String(s.fuel_cost_per_km),
  costPerKm: s?.cost_per_km == null ? "" : String(s.cost_per_km), otherKm: s?.other_km_used == null ? "" : String(s.other_km_used),
});
export function settingsBody(form: SettingsForm): { body: FccCommuteSettingsBody } | { error: string } {
  const body: FccCommuteSettingsBody = {};
  const err = fill(body, [["free_km", form.freeKm, 'מכסת ק"מ'], ["free_fuel", form.freeFuel, "מכסת דלק"], ["fuel_cost_per_km", form.fuelCost, 'עלות דלק לק"מ'], ["cost_per_km", form.costPerKm, 'עלות לק"מ מעל המכסה'],
    ["other_km_used", form.otherKm, 'ק"מ אחרים החודש']]);
  if (err) return { error: err };
  return Object.keys(body).length ? { body } : { error: "אין מה לשמור" };
}
