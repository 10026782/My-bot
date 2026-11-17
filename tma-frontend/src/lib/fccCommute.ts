// Pure presentation of the commute tab (a recurring paid ride answered day by day). All numbers come from the server; this file only words them and turns
// typed text into a request body. Unknown stays unknown: a missing km / minutes / cost is shown as "—", never as zero.
import type { FccCommute, FccCommuteDay, FccCommuteRoute, FccCommuteRouteBody } from "../types";
import { money } from "./fccPresentation";

export const UNKNOWN = "—";
export const COMMUTE_TITLE = "נסיעות";
export type AnswerKey = "no" | "2" | "3";
export const ANSWERS: { key: AnswerKey; label: string }[] = [
  { key: "no", label: "אין נסיעה" },
  { key: "2", label: "2 תחנות" },
  { key: "3", label: "3 תחנות" },
];

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

export interface CommuteSummary { cards: { key: string; label: string; value: string; hint?: string }[] }

/** The month at a glance: what to collect at the end of the month, how many ride days, and the days still without an answer. */
export function summaryModel(v: FccCommute): CommuteSummary {
  const days = v.routes.reduce((a, r) => a + r.this_month.yes_days, 0);
  const no = v.routes.reduce((a, r) => a + r.this_month.no_days, 0);
  return {
    cards: [
      { key: "collect", label: "לגבות בסוף החודש", value: money(v.income_this_month), hint: `${days} ימי נסיעה${no ? ` · ${no} ימים בלי נסיעה` : ""}` },
      { key: "days", label: "ימי נסיעה החודש", value: String(days) },
      { key: "missing", label: "ימים שלא עודכנו", value: String(v.unanswered_past), hint: v.unanswered_past ? "ימים שעברו בלי תשובה לא נספרים בהכנסה" : undefined },
    ],
  };
}

export interface WeekRow { key: string; label: string; days: string; income: string }
export function weekRows(r: FccCommuteRoute): WeekRow[] {
  return r.this_month.weeks.map((w) => ({ key: w.week_start, label: `שבוע מ-${dmy(w.week_start)}`, days: String(w.yes_days), income: money(w.income) }));
}

export interface MetricRow { label: string; value: string }
/** One trip day (there and back): the numbers that say whether the ride is worth it. Gross uses the price only; net also uses the owner's own cost per km. */
export function economicsRows(r: FccCommuteRoute): MetricRow[] {
  const e = r.economics;
  return [
    { label: "מחיר ליום נסיעה", value: e.price == null ? UNKNOWN : money(e.price) },
    { label: 'ק"מ ליום (הלוך וחזור)', value: num(e.km_per_day) },
    { label: "זמן ליום (הלוך וחזור)", value: e.minutes_per_day == null ? UNKNOWN : `${num(e.minutes_per_day)} דק׳` },
    { label: "ברוטו לשעה", value: e.gross_per_hour == null ? UNKNOWN : money(e.gross_per_hour) },
    { label: 'ברוטו לק"מ', value: e.gross_per_km == null ? UNKNOWN : money(e.gross_per_km) },
    { label: "עלות רכב ליום", value: e.vehicle_cost_per_day == null ? UNKNOWN : money(e.vehicle_cost_per_day) },
    { label: "נטו ליום", value: e.net_per_day == null ? UNKNOWN : money(e.net_per_day) },
    { label: "נטו לשעה", value: e.net_per_hour == null ? UNKNOWN : money(e.net_per_hour) },
    { label: 'נטו לק"מ', value: e.net_per_km == null ? UNKNOWN : money(e.net_per_km) },
    { label: "פוטנציאל חודשי (לפי הימים בשבוע)", value: e.monthly_potential == null ? UNKNOWN : `≈ ${money(e.monthly_potential)}` },
  ];
}

export function economicsHint(r: FccCommuteRoute): string | null {
  const missing = [r.km_one_way == null ? 'ק"מ' : null, r.minutes_one_way == null ? "זמן" : null, r.cost_per_km == null ? 'עלות לק"מ (בלי זה אין נטו)' : null].filter(Boolean);
  return missing.length ? `חסר: ${missing.join(", ")}` : null;
}

export interface TripRow { key: string; date: string; route: string; result: string; amount: string }
export function tripRows(v: FccCommute): TripRow[] {
  return v.trips.map((t) => ({
    key: t.id, date: `${t.weekday} ${dmy(t.date)}`, route: t.route ?? UNKNOWN,
    result: t.outcome === "no" ? "אין נסיעה" : t.stops ? `${t.stops} תחנות` : "נסיעה", amount: t.outcome === "yes" ? money(t.amount) : UNKNOWN,
  }));
}

export interface RouteForm { name: string; price: string; km: string; minutes: string; cost: string; days: string }
export const EMPTY_FORM: RouteForm = { name: "", price: "", km: "", minutes: "", cost: "", days: "6" };
export const formFromRoute = (r: FccCommuteRoute): RouteForm => ({
  name: r.name, price: r.price == null ? "" : String(r.price), km: r.km_one_way == null ? "" : String(r.km_one_way),
  minutes: r.minutes_one_way == null ? "" : String(r.minutes_one_way), cost: r.cost_per_km == null ? "" : String(r.cost_per_km), days: r.planned_days == null ? "" : String(r.planned_days),
});

const parseNum = (text: string): number | null | "bad" => {
  const t = text.replace(/[₪,\s]/g, "");
  if (t === "") return null;
  if (!/^\d+(\.\d+)?$/.test(t)) return "bad";
  return Number(t);
};

/** Typed text -> request body. A blank number is left out (never silently 0); an invalid one is an error. A new route needs a name and a price. */
export function routeBody(form: RouteForm, routeId?: string): { body: FccCommuteRouteBody } | { error: string } {
  const body: FccCommuteRouteBody = routeId ? { route_id: routeId } : {};
  if (form.name.trim()) body.name = form.name.trim();
  const fields: [keyof FccCommuteRouteBody, string, string][] = [["price", form.price, "מחיר"], ["km_one_way", form.km, 'ק"מ'], ["minutes_one_way", form.minutes, "דקות"], ["cost_per_km", form.cost, 'עלות לק"מ'], ["planned_days", form.days, "ימים בשבוע"]];
  for (const [key, text, label] of fields) {
    const v = parseNum(text);
    if (v === "bad") return { error: `ערך לא תקין: ${label}` };
    if (v != null) (body as Record<string, unknown>)[key] = v;
  }
  if (!routeId && (!body.name || body.price == null)) return { error: "מסלול חדש צריך שם ומחיר ליום נסיעה" };
  if (body.planned_days != null && (body.planned_days < 1 || body.planned_days > 7)) return { error: "ימים בשבוע: בין 1 ל-7" };
  return { body };
}
