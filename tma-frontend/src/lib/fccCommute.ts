// Pure presentation of the commute tab (rides answered day by day, one-off trips and deliveries, the leased car's free allowance). All numbers come from the server;
// this file only words them and turns typed text into a request body. Unknown stays unknown: a missing km / minutes / cost is shown as "—", never as zero.
import type {
  CommuteClass, CommuteKind, CommuteLoad, CommuteReturn, FccCommute, FccCommuteDay, FccCommuteProfit, FccCommuteQuota, FccCommuteRoute, FccCommuteRouteBody, FccCommuteSettingsBody, FccCommuteStats,
  FccCommuteEvaluation, FccCommuteOfferBody, FccCommutePending, FccCommuteReturnStats, FccCommuteScenario, FccCommuteTripBody,
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
/** On a one-off trip the way back is usually not known yet: it is recorded after the ride (the trip waits in "ממתינות לעדכון"). */
export const TRIP_RETURN_OPTIONS: { value: CommuteReturn | ""; label: string }[] = [{ value: "", label: "עוד לא ידוע — אעדכן אחרי הנסיעה" }, ...RETURN_OPTIONS];
export const LOAD_OPTIONS: { value: CommuteLoad | ""; label: string }[] = [{ value: "", label: "לא צוין" }, { value: "full", label: "מלא (עם נוסעים)" }, { value: "empty", label: "ריק" }];
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

/** How a past day was timed: the outbound leg (the hour it left, the minutes) and the return leg, or null. */
export const dayTiming = (d: FccCommuteDay): string | null => {
  const out = [d.start_time ? `יציאה ${d.start_time}` : null, d.minutes_one_way ? `${d.minutes_one_way} דק׳` : null].filter(Boolean).join(" ");
  const ret = [d.return_start_time ? `יציאה ${d.return_start_time}` : null, d.return_minutes ? `${d.return_minutes} דק׳` : null].filter(Boolean).join(" ");
  const bits = [out ? `הלוך: ${out}` : null, ret ? `חזור: ${ret}` : null].filter(Boolean);
  return bits.length ? bits.join(" · ") : null;
};

export interface DayTimingBody { route_id: string; date: string; outcome: "yes"; stops: number; start_time?: string; minutes_one_way?: number; return_start_time?: string; return_minutes?: number }
export interface DayTimingText { start: string; minutes: string; retStart: string; retMinutes: string }
const parseMinutes = (text: string): number | null | "bad" => {
  if (!text.trim()) return null;
  const v = Number(text.replace(/[,\s]/g, ""));
  return Number.isFinite(v) && v > 0 && v <= 1440 ? v : "bad";
};

/** The same answer of the day (a ride with 2 / 3 stops) with each leg's hour and minutes that day — only for a day that had a ride. */
export function dayTimingBody(routeId: string, day: FccCommuteDay, t: DayTimingText): { body: DayTimingBody } | { error: string } {
  const key = answerOf(day);
  if (key == null || key === "no") return { error: "קודם סמנו שהייתה נסיעה ובכמה תחנות" };
  const body: DayTimingBody = { route_id: routeId, date: day.date, outcome: "yes", stops: Number(key) };
  for (const [text, label] of [[t.start, "שעת יציאה (הלוך)"], [t.retStart, "שעת יציאה (חזור)"]] as const) if (text && !TIME_RE.test(text)) return { error: `${label}: HH:MM` };
  if (t.start) body.start_time = t.start;
  if (t.retStart) body.return_start_time = t.retStart;
  const out = parseMinutes(t.minutes);
  const ret = parseMinutes(t.retMinutes);
  if (out === "bad" || ret === "bad") return { error: "דקות: מספר חיובי" };
  if (out != null) body.minutes_one_way = out;
  if (ret != null) body.return_minutes = ret;
  if (Object.keys(body).length === 4) return { error: "הזינו שעה או דקות" };
  return { body };
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

/** The route's month in one line about the minutes the owner timed: how many days and the average of each leg. */
export const timedLine = (r: FccCommuteRoute): string | null => {
  const a = (n: number | null): string => (n == null ? UNKNOWN : new Intl.NumberFormat("he-IL", { maximumFractionDigits: 1 }).format(n));
  if (!r.this_month.timed_days && !r.this_month.timed_return_days) return null;
  return `זמן בפועל החודש: הלוך ${a(r.this_month.avg_minutes_one_way)} דק׳ (${r.this_month.timed_days} ימים) · חזור ${a(r.this_month.avg_return_minutes)} דק׳ (${r.this_month.timed_return_days} ימים)`;
};

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
    { label: 'ק"מ ליום (שני הצדדים + בלי תשלום)', value: num(e.km_per_day) },
    { label: "זמן ליום (בלי ההמתנה החופשית בין הצדדים)", value: e.minutes_per_day == null ? UNKNOWN : `${num(e.minutes_per_day)} דק׳` },
    { label: 'ק"מ בלי תשלום ליום', value: e.unpaid_km ? num(e.unpaid_km) : UNKNOWN },
    { label: 'ק"מ ריקים ליום', value: e.empty_km == null ? UNKNOWN : `${num(e.empty_km)}${e.empty_share == null ? "" : ` (${pct(e.empty_share)})`}` },
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

const LOAD_LABEL = { full: "מלא", empty: "ריק" } as const;
export interface LegRow { key: string; label: string; start: string; km: string; minutes: string; load: string; unpaid: string }
/** The two legs of a usual day, side by side: when it leaves, km, minutes, full / empty and the unpaid driving around it. */
export function legRows(r: FccCommuteRoute): LegRow[] {
  return r.economics.legs.map((l) => ({
    key: l.key, label: l.label, start: l.start ?? UNKNOWN, km: num(l.km), minutes: l.minutes == null ? UNKNOWN : `${num(l.minutes)} דק׳`, load: l.load ? LOAD_LABEL[l.load] : UNKNOWN,
    unpaid: l.unpaid_km || l.unpaid_minutes ? `${num(l.unpaid_km)} ק"מ · ${num(l.unpaid_minutes)} דק׳` : UNKNOWN,
  }));
}

export interface DecisionModel { lines: MetricRow[]; legs: { key: string; label: string; avg: string; total: string; days: string; slow: boolean }[]; note: string | null }
/** The month's decision "do I keep this route": the income against BOTH legs and the unpaid driving, and each leg's average minutes so the slow one shows. Numbers only — the owner decides. */
export function decisionModel(r: FccCommuteRoute): DecisionModel | null {
  const d = r.this_month.decision;
  if (!d.days && !d.unknown_days) return null;
  const slow = d.slowest ? d.legs.find((l) => l.key === d.slowest) : null;
  return {
    lines: [
      { label: "ימי נסיעה שחושבו", value: String(d.days) },
      { label: "הכנסה", value: money(d.income) },
      { label: 'ק"מ בסך הכול (שני הצדדים + בלי תשלום)', value: num(d.km) },
      { label: "שעות בסך הכול", value: d.minutes ? `${num(d.minutes / 60)} (בלי ההמתנה החופשית בין הצדדים)` : UNKNOWN },
      { label: "הכנסה לשעה", value: m(d.gross_per_hour) },
      { label: 'הכנסה לק"מ', value: m(d.gross_per_km) },
      { label: "נטו אחרי עלות הרכב", value: m(d.net) },
      { label: "נטו לשעה", value: m(d.net_per_hour) },
      { label: 'ק"מ ריקים', value: d.empty_km == null ? UNKNOWN : `${num(d.empty_km)}${d.empty_share == null ? "" : ` (${pct(d.empty_share)})`}` },
    ],
    legs: d.legs.map((l) => ({ key: l.key, label: l.label, avg: `${num(l.avg_minutes)} דק׳`, total: `${num(l.avg_total_minutes)} דק׳ עם הנסיעה בלי תשלום`, days: `${l.timed_days} ימים נמדדו`, slow: l.key === d.slowest })),
    note: slow ? `הצד האיטי יותר: ${slow.label}` : null,
  };
}

const RETURN_LABEL: Record<CommuteReturn, string> = { empty: "חזרה ריקה", waited: "המתנה", continuation: "יש נסיעת המשך" };
const CLASS_LABEL: Record<CommuteClass, string> = { regular: "רגיל", large: "גדול" };
const KIND_LABEL: Record<CommuteKind, string> = { ride: "נסיעה", delivery: "משלוח" };

export interface TripRow { key: string; date: string; route: string; result: string; detail: string; amount: string; perKm: string }
export function tripRows(v: FccCommute): TripRow[] {
  return v.trips.map((t) => {
    const bits = [t.city ? (t.area ? `${t.city} · ${t.area}` : t.city) : null, t.added_stops ? `${t.added_stops} תחנות (+${money(t.stops_price)})` : null, t.start_time ? `יציאה ${t.start_time}` : null, t.vehicle_class ? CLASS_LABEL[t.vehicle_class] : null, t.return_status ? RETURN_LABEL[t.return_status] : null, t.on_the_way_of ? `על הדרך של ${t.on_the_way_of}` : null,
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
export interface PlaceRow { key: string; label: string; rides: string; avgPrice: string; perKm: string; perHour: string; vsAverage: string }
const placeRow = (r: FccCommuteProfit["by_city"][number]): PlaceRow => ({
  key: `${r.city}|${r.area ?? ""}`, label: r.area ? `${r.city} · ${r.area}` : r.city, rides: String(r.rides), avgPrice: m(r.avg_price), perKm: m(r.gross_per_km), perHour: m(r.gross_per_hour),
  vsAverage: r.vs_average_per_km == null ? UNKNOWN : `${r.vs_average_per_km >= 0 ? "+" : "−"}${money(Math.abs(r.vs_average_per_km))}`,
});

/** Where: a city's profitability is not another's, and inside a city the entrance is not a remote neighbourhood — cities, then areas, each against his average per km. */
export function placeModel(p: FccCommuteProfit): { cities: PlaceRow[]; areas: PlaceRow[]; note: string | null } {
  return { cities: p.by_city.map(placeRow), areas: p.by_area.map(placeRow), note: p.without_place ? `${p.without_place} נסיעות בלי עיר לא נכנסו להשוואת המקומות — הוסיפו עיר ואזור` : null };
}

export interface StopsModel { lines: MetricRow[]; bands: { key: string; label: string; rides: string; minutes: string; perHour: string }[]; note: string | null }
/** The extra stops: what they earned on their own (the surcharge against the km and minutes THEY added), what they did to the whole ride, and by hour — a stop on the way is not a stop across the city in the rush hour. */
export function stopsModel(p: FccCommuteProfit): StopsModel | null {
  const s = p.stops;
  if (!s) return null;
  return {
    lines: [
      { label: "נסיעות עם תחנות", value: `${s.rides} (${s.stops} תחנות)` },
      { label: "תוספת ממוצעת לנסיעה", value: m(s.avg_price) },
      { label: "דקות לתחנה (ממוצע)", value: s.avg_minutes_per_stop == null ? UNKNOWN : `${num(s.avg_minutes_per_stop)} דק׳` },
      { label: 'ק"מ לתחנה (ממוצע)', value: s.avg_km_per_stop == null ? UNKNOWN : num(s.avg_km_per_stop) },
      { label: "התחנות לבדן — לשעה", value: m(s.per_hour) },
      { label: 'התחנות לבדן — לק"מ', value: m(s.per_km) },
      { label: "כל הנסיעה לשעה: עם התחנות", value: m(s.ride_per_hour_with) },
      { label: "כל הנסיעה לשעה: בלי התחנות", value: m(s.ride_per_hour_without) },
    ],
    bands: s.by_band.map((b) => ({ key: b.band, label: b.label, rides: String(b.rides), minutes: b.avg_minutes_per_stop == null ? UNKNOWN : `${num(b.avg_minutes_per_stop)} דק׳`, perHour: m(b.per_hour) })),
    note: s.note,
  };
}

export interface TimeRow { key: string; label: string; rides: string; avgMinutes: string; perHour: string; perKm: string }
export interface TimeInsight { key: string; title: string; detail: string }

/** What traffic does to a ride's length: the day in bands, and — per destination with a real sample in two bands — the minutes and the ₪ per hour of each band. Facts, no verdict. */
export function timeModel(p: FccCommuteProfit): { rows: TimeRow[]; insights: TimeInsight[]; note: string | null } {
  const label = (key: string): string => p.by_time.find((b) => b.band === key)?.label ?? key;
  const insights = p.time_insights.map((i) => ({
    key: i.destination,
    title: `${i.destination}: ${label(i.slowest)} לוקחת ${num(i.extra_minutes)} דק׳ יותר מ${label(i.fastest)}`,
    detail: i.bands.map((b) => `${b.label}: ${num(b.avg_minutes)} דק׳ · ${m(b.gross_per_hour)} לשעה (${b.rides} נסיעות)`).join(" | "),
  }));
  return {
    rows: p.by_time.map((b) => ({ key: b.band, label: b.label, rides: String(b.rides), avgMinutes: b.avg_minutes == null ? UNKNOWN : `${num(b.avg_minutes)} דק׳`, perHour: m(b.gross_per_hour), perKm: m(b.gross_per_km) })),
    insights,
    note: p.without_time ? `${p.without_time} נסיעות בלי שעת יציאה לא נכנסו להשוואת השעות — הוסיפו שעה כדי לראות איך הפקקים משפיעים` : null,
  };
}

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
export const TIME_RE = /^([01]\d|2[0-3]):[0-5]\d$/;
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

export interface RouteForm {
  name: string; price: string; km: string; minutes: string; cost: string; days: string; cls: CommuteClass | ""; ret: CommuteReturn; waiting: string; own: boolean; weekdays: string[]; start: string;
  retStart: string; retKm: string; retMinutes: string; outLoad: CommuteLoad | ""; retLoad: CommuteLoad | ""; outUnpaidKm: string; outUnpaidMin: string; retUnpaidKm: string; retUnpaidMin: string;
}
export const EMPTY_FORM: RouteForm = { name: "", price: "", km: "", minutes: "", cost: "", days: "6", cls: "", ret: "empty", waiting: "", own: false, weekdays: [], start: "", retStart: "", retKm: "", retMinutes: "", outLoad: "", retLoad: "", outUnpaidKm: "", outUnpaidMin: "", retUnpaidKm: "", retUnpaidMin: "" };
export const EMPTY_OWN_FORM: RouteForm = { ...EMPTY_FORM, days: "", own: true };
export const formFromRoute = (r: FccCommuteRoute): RouteForm => ({
  name: r.name, price: r.price == null ? "" : String(r.price), km: r.km_one_way == null ? "" : String(r.km_one_way), minutes: r.minutes_one_way == null ? "" : String(r.minutes_one_way),
  cost: r.cost_per_km == null ? "" : String(r.cost_per_km), days: r.planned_days == null ? "" : String(r.planned_days), cls: r.vehicle_class ?? "", ret: r.return_status,
  waiting: r.waiting_minutes ? String(r.waiting_minutes) : "", own: r.kind === "own", weekdays: r.weekdays, start: r.start_time ?? "",
  retStart: r.return_start_time ?? "", retKm: r.return_km == null ? "" : String(r.return_km), retMinutes: r.return_minutes == null ? "" : String(r.return_minutes), outLoad: r.outbound_load ?? "", retLoad: r.return_load ?? "",
  outUnpaidKm: r.out_unpaid_km ? String(r.out_unpaid_km) : "", outUnpaidMin: r.out_unpaid_minutes ? String(r.out_unpaid_minutes) : "", retUnpaidKm: r.ret_unpaid_km ? String(r.ret_unpaid_km) : "",
  retUnpaidMin: r.ret_unpaid_minutes ? String(r.ret_unpaid_minutes) : "",
});

/** A new paid route needs a name and a price; an own weekly drive needs only a name (and the weekdays are for the list). */
export function routeBody(form: RouteForm, routeId?: string): { body: FccCommuteRouteBody } | { error: string } {
  const body: FccCommuteRouteBody = routeId ? { route_id: routeId } : {};
  if (form.name.trim()) body.name = form.name.trim();
  const err = fill(body, [["price", form.own ? "" : form.price, "מחיר"], ["km_one_way", form.km, 'ק"מ'], ["minutes_one_way", form.minutes, "דקות"], ["cost_per_km", form.cost, 'עלות לק"מ'],
    ["planned_days", form.days, "ימים בשבוע"], ["waiting_minutes", form.waiting, "דקות המתנה"], ["return_km", form.own ? "" : form.retKm, 'ק"מ חזור'], ["return_minutes", form.own ? "" : form.retMinutes, "דקות חזור"],
    ["out_unpaid_km", form.own ? "" : form.outUnpaidKm, 'ק"מ בלי תשלום (הלוך)'], ["out_unpaid_minutes", form.own ? "" : form.outUnpaidMin, "דקות בלי תשלום (הלוך)"],
    ["ret_unpaid_km", form.own ? "" : form.retUnpaidKm, 'ק"מ בלי תשלום (חזור)'], ["ret_unpaid_minutes", form.own ? "" : form.retUnpaidMin, "דקות בלי תשלום (חזור)"]]);
  if (err) return { error: err };
  if (form.start) { if (!TIME_RE.test(form.start)) return { error: "שעת יציאה: HH:MM" }; body.start_time = form.start; }
  if (!form.own && form.retStart) { if (!TIME_RE.test(form.retStart)) return { error: "שעת יציאה (חזור): HH:MM" }; body.return_start_time = form.retStart; }
  if (!form.own) { if (form.outLoad) body.outbound_load = form.outLoad; if (form.retLoad) body.return_load = form.retLoad; }
  if (!form.own) { if (form.cls) body.vehicle_class = form.cls; body.return_status = form.ret; } else { body.route_kind = "own"; if (form.weekdays.length) body.weekdays = form.weekdays; }
  if (!routeId && !body.name) return { error: "צריך שם" };
  if (!routeId && !form.own && body.price == null) return { error: "מסלול חדש צריך שם ומחיר ליום נסיעה" };
  if (body.planned_days != null && (body.planned_days < 1 || body.planned_days > 7)) return { error: "ימים בשבוע: בין 1 ל-7" };
  return { body };
}

export interface TripForm { city: string; area: string; stops: string; stopsPrice: string; stopsKm: string; stopsMinutes: string; start: string; destination: string; date: string; price: string; cls: CommuteClass | ""; kind: CommuteKind; km: string; minutes: string; ret: CommuteReturn | ""; waiting: string; onWay: string; extraKm: string; extraMinutes: string }
export const emptyTripForm = (today: string): TripForm => ({ city: "", area: "", stops: "", stopsPrice: "", stopsKm: "", stopsMinutes: "", start: "", destination: "", date: today, price: "", cls: "", kind: "ride", km: "", minutes: "", ret: "", waiting: "", onWay: "", extraKm: "", extraMinutes: "" });

/** One typed trip: the price is typed every time (there is no price list). "On the way" = the km / minutes it ADDED replace the one-way based ones. */
export function tripBody(form: TripForm): { body: FccCommuteTripBody } | { error: string } {
  if (!form.destination.trim()) return { error: "צריך יעד" };
  const body: FccCommuteTripBody = { destination: form.destination.trim(), kind: form.kind };
  if (/^\d{4}-\d{2}-\d{2}$/.test(form.date)) body.date = form.date;
  const err = fill(body, [["price", form.price, "מחיר"], ["km_one_way", form.km, 'ק"מ'], ["minutes_one_way", form.minutes, "דקות"], ["waiting_minutes", form.ret === "waited" ? form.waiting : "", "דקות המתנה"],
    ["extra_km", form.extraKm, 'ק"מ עיקוף'], ["extra_minutes", form.extraMinutes, "דקות עיקוף"], ["added_stops", form.stops, "מספר תחנות"], ["stops_price", form.stopsPrice, "תוספת התחנות"],
    ["stops_km", form.stopsKm, 'ק"מ התחנות'], ["stops_minutes", form.stopsMinutes, "דקות התחנות"]]);
  if (err) return { error: err };
  if (body.price == null) return { error: "צריך מחיר" };
  if (body.stops_price != null && body.stops_price > body.price) return { error: "תוספת התחנות לא יכולה להיות יותר מהמחיר" };
  if (form.city.trim()) body.city = form.city.trim();
  if (form.area.trim()) body.area = form.area.trim();
  if (form.cls) body.vehicle_class = form.cls;
  if (form.start) { if (!TIME_RE.test(form.start)) return { error: "שעת יציאה: HH:MM" }; body.start_time = form.start; }
  if (form.ret) body.return_status = form.ret;
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

// ── an offer, priced before it is taken ──
/** The same typed fields as a trip: price (required), km / minutes of one way, start time, and — on the way of an own drive — only the detour. Nothing here is saved. */
export function evaluateBody(form: TripForm): { body: FccCommuteOfferBody } | { error: string } {
  const body = {} as FccCommuteOfferBody;
  const err = fill(body, [["price", form.price, "מחיר"], ["km_one_way", form.onWay ? "" : form.km, 'ק"מ'], ["minutes_one_way", form.onWay ? "" : form.minutes, "דקות"],
    ["waiting_minutes", !form.onWay && form.ret !== "empty" && form.ret !== "continuation" ? form.waiting : "", "דקות המתנה"], ["extra_km", form.onWay ? form.extraKm : "", 'ק"מ עיקוף'], ["extra_minutes", form.onWay ? form.extraMinutes : "", "דקות עיקוף"],
    ["added_stops", form.stops, "מספר תחנות"], ["stops_price", form.stopsPrice, "תוספת התחנות"], ["stops_km", form.stopsKm, 'ק"מ התחנות'], ["stops_minutes", form.stopsMinutes, "דקות התחנות"]]);
  if (err) return { error: err };
  if (body.price == null || body.price <= 0) return { error: "צריך מחיר" };
  if (body.stops_price != null && body.stops_price > body.price) return { error: "תוספת התחנות לא יכולה להיות יותר מהמחיר" };
  if (form.city.trim()) body.city = form.city.trim();
  if (form.area.trim()) body.area = form.area.trim();
  if (form.destination.trim()) body.destination = form.destination.trim();
  if (form.start) { if (!TIME_RE.test(form.start)) return { error: "שעת יציאה: HH:MM" }; body.start_time = form.start; }
  if (form.onWay && body.extra_km == null) return { error: 'הזינו ק"מ עיקוף' };
  return { body };
}

export interface ScenarioRow { key: string; label: string; km: string; minutes: string; perKm: string; perHour: string; netPerHour: string; allowance: string }
export interface EvaluationModel { headline: string | null; rows: ScenarioRow[]; expected: ScenarioRow | null; basis: string | null; vsAverage: string | null; typical: string | null; allowance: string | null; place: string | null; stops: string | null; notes: string[] }

const scenarioRow = (s: FccCommuteScenario): ScenarioRow => ({
  key: s.key, label: s.label, km: s.km == null ? UNKNOWN : num(s.km, ' ק"מ'), minutes: s.minutes == null ? UNKNOWN : `${num(s.minutes)} דק׳`, perKm: m(s.gross_per_km), perHour: m(s.gross_per_hour), netPerHour: m(s.net_per_hour),
  allowance: s.beyond_km == null ? UNKNOWN : s.beyond_km > 0 ? `חורג ב-${num(s.beyond_km)} ק"מ${s.cost_beyond == null ? "" : ` (עלות ${money(s.cost_beyond)})`}` : "בתוך המכסה",
});

/** The answer to "is this offer worth it": the three ways back side by side, the expected figure when the history allows it (with its sample), the allowance and the comparison with his average. */
export function evaluationModel(ev: FccCommuteEvaluation): EvaluationModel {
  const rows = ev.scenarios.map(scenarioRow);
  const hours = ev.scenarios.map((s) => s.gross_per_hour).filter((x): x is number => x != null);
  const sign = (n: number | null | undefined): string => (n == null ? UNKNOWN : `${n >= 0 ? "+" : "−"}${money(Math.abs(n))}`);
  const w = ev.basis.weights;
  const split = `חוזר ריק ${pct(w?.empty)}, יש המשך ${pct(w?.continuation)}, המתנה ${pct(w?.waited)}`;
  const level = { area: "אזור", city: "עיר", destination: "יעד" } as const;
  const basis = ev.basis.used && ev.basis.used !== "overall" ? `לפי ${ev.basis.sample} נסיעות קודמות ל${level[ev.basis.used]} הזה: ${split}`
    : ev.basis.used === "overall" ? `לאזור/ליעד הזה אין מספיק היסטוריה — לפי ${ev.basis.overall_sample} נסיעות שלך בסך הכול: ${split}` : null;
  return {
    headline: ev.expected ? `צפוי: ${m(ev.expected.gross_per_hour)} לשעה · ${m(ev.expected.gross_per_km)} לק"מ` : hours.length > 1 ? `בין ${money(Math.min(...hours))} ל-${money(Math.max(...hours))} לשעה, לפי הדרך חזרה` : hours.length === 1 ? `${money(hours[0])} לשעה` : null,
    rows: ev.expected ? rows.filter((r) => r.key !== "expected") : rows, expected: ev.expected ? scenarioRow(ev.expected) : null, basis,
    vsAverage: ev.vs_average && (ev.vs_average.per_km != null || ev.vs_average.per_hour != null) ? `לעומת הממוצע שלך (${ev.average?.rides ?? 0} נסיעות): ${sign(ev.vs_average.per_km)} לק"מ · ${sign(ev.vs_average.per_hour)} לשעה` : null,
    typical: ev.typical_at_this_hour ? `ליעד הזה בשעות ${ev.typical_at_this_hour.band} נסעת בממוצע ${num(ev.typical_at_this_hour.avg_minutes_one_way)} דק׳ לכיוון (${ev.typical_at_this_hour.rides} נסיעות)` : null,
    allowance: ev.allowance_remaining_km == null ? null : `נותרו במכסה ${num(ev.allowance_remaining_km)} ק"מ החודש`, notes: ev.notes,
    place: ev.place ? `${ev.place.level === "area" ? "באזור" : "בעיר"} ${ev.place.label} (${ev.place.rides} נסיעות שלך): ממוצע ${m(ev.place.avg_price)} · ${m(ev.place.gross_per_km)} לק"מ · ${m(ev.place.gross_per_hour)} לשעה` : null,
    stops: ev.stops ? [`${ev.stops.added ? `${ev.stops.added} תחנות` : "תחנות"}: תוספת ${m(ev.stops.price)} על ${num(ev.stops.km)} ק"מ ו-${num(ev.stops.minutes)} דק׳${ev.stops.band ? ` (${ev.stops.band})` : ""}`,
      `התחנות לבדן: ${m(ev.stops.per_hour)} לשעה · ${m(ev.stops.per_km)} לק"מ${ev.stops.owner_per_hour == null ? "" : ` (בנסיעות קודמות שלך: ${m(ev.stops.owner_per_hour)} לשעה)`}`,
      `כל הנסיעה: ${m(ev.stops.total_gross_per_hour)} לשעה עם התחנות מול ${m(ev.stops.base_gross_per_hour)} בלעדיהן`].join(" · ") : null,
  };
}

// ── trips that wait for the way back, and what the history says ──
export interface PendingRow { id: string; title: string; detail: string }
export const pendingRows = (pending: FccCommutePending[]): PendingRow[] => pending.map((p) => ({
  id: p.id, title: `${p.weekday} ${dmy(p.date)} · ${p.destination ?? UNKNOWN}${p.kind === "delivery" ? " (משלוח)" : ""}`,
  detail: [p.price == null ? null : money(p.price), p.km_one_way == null ? null : `${num(p.km_one_way)} ק"מ`, p.start_time ? `יציאה ${p.start_time}` : null].filter(Boolean).join(" · "),
}));

/** The way back of a trip that was taken: empty / a paid continuation / waited N minutes. */
export function returnBody(tripId: string, status: CommuteReturn, waitingText = ""): { body: FccCommuteTripBody } | { error: string } {
  const body: FccCommuteTripBody = { trip_id: tripId, return_status: status };
  if (status === "waited") {
    const v = parseNum(waitingText);
    if (v === "bad" || v == null) return { error: "כמה דקות חיכית?" };
    body.waiting_minutes = v;
  }
  return { body };
}

export interface ReturnRow { key: string; label: string; known: string; empty: string; continuation: string; waited: string }
export function returnModel(r: FccCommuteReturnStats): { rows: ReturnRow[]; note: string } {
  const row = (key: string, label: string, b: FccCommuteReturnStats["overall"]): ReturnRow => {
    const share = (n: number): string => (b.known ? pct(n / b.known) : UNKNOWN);
    return { key, label, known: String(b.known), empty: share(b.empty), continuation: share(b.continuation), waited: `${share(b.waited)}${b.avg_wait_minutes ? ` (${num(b.avg_wait_minutes)} דק׳)` : ""}` };
  };
  return {
    rows: [row("all", "הכול", r.overall), ...r.by_area.map((a) => row(`a-${a.city}-${a.area}`, `${a.city} · ${a.area}`, a)), ...r.by_city.map((c) => row(`c-${c.city}`, `${c.city} (כל העיר)`, c)),
      ...r.by_destination.map((d) => row(`d-${d.destination}`, d.destination, d))],
    note: `זה מה שקרה בנסיעות שתיעדת — אקראי ועם תחרות, לא הבטחה. הממוצע המשוקלל בבדיקת הצעה מופיע אחרי ${r.min_destination} נסיעות מתועדות לאזור (אחרת לעיר, אחרת ליעד) או ${r.min_overall} בסך הכול.`,
  };
}
