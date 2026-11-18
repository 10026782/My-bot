import { useCallback, useEffect, useState } from "react";
import { fetchFccCommute, postFccCommuteDay, postFccCommuteEvaluate, postFccCommuteRoute, postFccCommuteSettings, postFccCommuteTrip } from "../api";
import type { CommuteKind, CommuteLoad, CommuteReturn, FccCommute, FccCommuteEvaluation, FccCommuteRoute } from "../types";
import {
  ANSWERS, CLASS_OPTIONS, EMPTY_FORM, EMPTY_OWN_FORM, KIND_OPTIONS, RETURN_OPTIONS, WEEKDAYS, answerBody, answerOf, dayLabel, economicsHint, economicsRows, emptyTripForm, formFromRoute,
  placeModel, stopsModel, dayTiming, dayTimingBody, decisionModel, legRows, LOAD_OPTIONS, timedLine, type DayTimingBody, TRIP_RETURN_OPTIONS, evaluateBody, evaluationModel, formFromSettings, pendingRows, profitModel, quotaRows, returnBody, returnModel, timeModel, routeBody, settingsBody, summaryModel, tripBody, tripRows, weekRows, type AnswerKey, type ProfitRow, type RouteForm, type SettingsForm, type TripForm,
} from "../lib/fccCommute";
import { KpiCard } from "./FccKpiCard";
import { ScreenState } from "./ui/ScreenState";
import { Surface } from "./ui/Surface";

type State = { status: "loading" } | { status: "ok"; data: FccCommute } | { status: "error"; code?: number };

function AnswerButtons({ route, day, busy, onAnswer }: { route: FccCommuteRoute; day: FccCommuteRoute["days"][number]; busy: boolean; onAnswer: (date: string, key: AnswerKey) => void }) {
  const current = answerOf(day);
  return (
    <div className="fcc-chips" role="group" aria-label={`${route.name} — ${dayLabel(day)}`}>
      {ANSWERS.map((a) => (
        <button key={a.key} type="button" disabled={busy} aria-pressed={current === a.key} className={`fcc-chip${current === a.key ? " fcc-chip--on" : ""}`} onClick={() => onAnswer(day.date, a.key)}>{a.label}</button>
      ))}
    </div>
  );
}

type TimingBody = DayTimingBody;

/** For a past day that had a ride: each leg's hour and minutes that day (the traffic of that hour). */
function DayTiming({ route, day, busy, onSave }: { route: FccCommuteRoute; day: FccCommuteRoute["days"][number]; busy: boolean; onSave: (body: TimingBody) => void }) {
  const [t, setT] = useState({ start: day.start_time ?? "", minutes: day.minutes_one_way ? String(day.minutes_one_way) : "", retStart: day.return_start_time ?? "", retMinutes: day.return_minutes ? String(day.return_minutes) : "" });
  const [error, setError] = useState<string | null>(null);
  if (day.outcome !== "yes") return null;
  const set = (k: keyof typeof t) => (e: React.ChangeEvent<HTMLInputElement>) => setT({ ...t, [k]: e.target.value });
  return (
    <div className="fcc-stack fcc-stack--tight">
      <div className="fcc-chips">
        <span className="fcc-loan__meta">הלוך</span>
        <input type="time" value={t.start} onChange={set("start")} className="boss-input" aria-label={`שעת יציאה הלוך — ${dayLabel(day)}`} />
        <input value={t.minutes} onChange={set("minutes")} inputMode="decimal" className="boss-input" aria-label={`דקות הלוך בפועל — ${dayLabel(day)}`} placeholder="דקות בפועל" />
      </div>
      <div className="fcc-chips">
        <span className="fcc-loan__meta">חזור</span>
        <input type="time" value={t.retStart} onChange={set("retStart")} className="boss-input" aria-label={`שעת יציאה חזור — ${dayLabel(day)}`} />
        <input value={t.retMinutes} onChange={set("retMinutes")} inputMode="decimal" className="boss-input" aria-label={`דקות חזור בפועל — ${dayLabel(day)}`} placeholder="דקות בפועל" />
        <button type="button" disabled={busy} className="fcc-chip" onClick={() => {
          const parsed = dayTimingBody(route.id, day, t);
          if ("error" in parsed) { setError(parsed.error); return; }
          setError(null);
          onSave(parsed.body);
        }}>שמירת שעה וזמן</button>
      </div>
      {error && <span className="fcc-goal__note" role="alert">{error}</span>}
    </div>
  );
}

function Field({ label, value, onChange, mode = "decimal" }: { label: string; value: string; onChange: (v: string) => void; mode?: "text" | "decimal" | "date" | "time" }) {
  return <label className="fcc-field"><span>{label}</span><input value={value} onChange={(e) => onChange(e.target.value)} inputMode={mode === "date" || mode === "time" ? undefined : mode} type={mode === "date" ? "date" : mode === "time" ? "time" : "text"} className="boss-input" /></label>;
}
function Select<T extends string>({ label, value, options, onChange }: { label: string; value: T; options: { value: T; label: string }[]; onChange: (v: T) => void }) {
  return <label className="fcc-field"><span>{label}</span><select value={value} onChange={(e) => onChange(e.target.value as T)} className="boss-input">{options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</select></label>;
}

function RouteFormView({ initial, submitLabel, busy, onSubmit }: { initial: RouteForm; submitLabel: string; busy: boolean; onSubmit: (form: RouteForm) => void }) {
  const [form, setForm] = useState<RouteForm>(initial);
  const set = <K extends keyof RouteForm>(k: K) => (v: RouteForm[K]) => setForm({ ...form, [k]: v });
  return (
    <form className="fcc-stack fcc-stack--tight" onSubmit={(e) => { e.preventDefault(); onSubmit(form); }}>
      <Field label={form.own ? "שם הנסיעה הקבועה שלי (למשל: עבודה)" : "שם המסלול"} value={form.name} onChange={set("name")} mode="text" />
      {!form.own && <Field label="מחיר ליום נסיעה (₪)" value={form.price} onChange={set("price")} />}
      <Field label={form.own ? 'ק"מ לכל כיוון (חד פעמי)' : 'הלוך — ק"מ (חד פעמי)'} value={form.km} onChange={set("km")} />
      <Field label={form.own ? "דקות לכל כיוון (בשעת היציאה הרגילה)" : "הלוך — דקות (בשעת היציאה הרגילה)"} value={form.minutes} onChange={set("minutes")} />
      <Field label={form.own ? "שעת יציאה רגילה" : "הלוך — שעת יציאה (למשל 07:30)"} value={form.start} onChange={set("start")} mode="time" />
      {!form.own && (
        <>
          <Select<CommuteLoad | ""> label="הלוך — מלא או ריק" value={form.outLoad} options={LOAD_OPTIONS} onChange={set("outLoad")} />
          <Field label='הלוך — ק"מ בלי תשלום (מהבית לאיסוף ומההורדה הביתה)' value={form.outUnpaidKm} onChange={set("outUnpaidKm")} />
          <Field label="הלוך — דקות בלי תשלום" value={form.outUnpaidMin} onChange={set("outUnpaidMin")} />
          <Field label='חזור — ק"מ (ריק = כמו בהלוך)' value={form.retKm} onChange={set("retKm")} />
          <Field label="חזור — דקות (ריק = כמו בהלוך)" value={form.retMinutes} onChange={set("retMinutes")} />
          <Field label="חזור — שעת יציאה (למשל 15:00)" value={form.retStart} onChange={set("retStart")} mode="time" />
          <Select<CommuteLoad | ""> label="חזור — מלא או ריק" value={form.retLoad} options={LOAD_OPTIONS} onChange={set("retLoad")} />
          <Field label='חזור — ק"מ בלי תשלום' value={form.retUnpaidKm} onChange={set("retUnpaidKm")} />
          <Field label="חזור — דקות בלי תשלום" value={form.retUnpaidMin} onChange={set("retUnpaidMin")} />
          <p className="fcc-loan__meta">הזמן בין שני הצדדים (למשל בין 7:30 ל-15:00) פנוי ולא נספר.</p>
        </>
      )}
      {!form.own && (
        <>
          <Field label="ימי נסיעה בשבוע" value={form.days} onChange={set("days")} />
          <Select label="סוג מחיר" value={form.cls} options={CLASS_OPTIONS} onChange={set("cls")} />
          <Select<CommuteReturn> label="חזרה" value={form.ret} options={RETURN_OPTIONS} onChange={set("ret")} />
          {form.ret === "waited" && <Field label="דקות המתנה ליום" value={form.waiting} onChange={set("waiting")} />}
        </>
      )}
      {form.own && (
        <div className="fcc-chips" role="group" aria-label="ימים בשבוע">
          {WEEKDAYS.map((d) => (
            <button key={d} type="button" aria-pressed={form.weekdays.includes(d)} className={`fcc-chip${form.weekdays.includes(d) ? " fcc-chip--on" : ""}`}
                    onClick={() => set("weekdays")(form.weekdays.includes(d) ? form.weekdays.filter((x) => x !== d) : [...form.weekdays, d])}>{d}</button>
          ))}
        </div>
      )}
      <button type="submit" disabled={busy} className="boss-button boss-button--primary">{submitLabel}</button>
    </form>
  );
}

function EvaluationView({ ev }: { ev: FccCommuteEvaluation }) {
  const e = evaluationModel(ev);
  const table = (rows: typeof e.rows) => rows.map((r) => <tr key={r.key}><th scope="row">{r.label}</th><td>{r.km}</td><td>{r.minutes}</td><td>{r.perKm}</td><td>{r.perHour}</td><td>{r.netPerHour}</td><td>{r.allowance}</td></tr>);
  return (
    <div className="fcc-stack fcc-stack--tight" role="status">
      {e.headline && <h4 className="fcc-pay__subhead">{e.headline}</h4>}
      <div className="fcc-table-scroll" role="region" tabIndex={0} aria-label="תרחישי חזרה">
        <table className="fcc-compare__table">
          <thead><tr><th>הדרך חזרה</th><th>ק״מ</th><th>זמן</th><th>לק״מ</th><th>לשעה</th><th>נטו לשעה</th><th>מהמכסה</th></tr></thead>
          <tbody>{table(e.rows)}{e.expected && table([e.expected])}</tbody>
        </table>
      </div>
      {e.basis && <p className="fcc-loan__meta">{e.basis}</p>}
      {e.vsAverage && <p className="fcc-loan__meta">{e.vsAverage}</p>}
      {e.typical && <p className="fcc-loan__meta">{e.typical}</p>}
      {e.place && <p className="fcc-loan__meta">{e.place}</p>}
      {e.stops && <p className="fcc-loan__meta">{e.stops}</p>}
      {e.allowance && <p className="fcc-loan__meta">{e.allowance}</p>}
      {e.notes.map((n) => <p key={n} className="fcc-goal__note">{n}</p>)}
    </div>
  );
}

function TripFormView({ today, ownTrips, busy, evaluation, onEvaluate, onSubmit }: {
  today: string; ownTrips: FccCommute["own_trips"]; busy: boolean; evaluation: FccCommuteEvaluation | null; onEvaluate: (form: TripForm) => void; onSubmit: (form: TripForm) => void;
}) {
  const [form, setForm] = useState<TripForm>(emptyTripForm(today));
  const set = <K extends keyof TripForm>(k: K) => (v: TripForm[K]) => setForm({ ...form, [k]: v });
  const onWay = form.onWay !== "";
  return (
    <form className="fcc-stack fcc-stack--tight" onSubmit={(e) => { e.preventDefault(); onEvaluate(form); }}>
      <Select<CommuteKind> label="סוג" value={form.kind} options={KIND_OPTIONS} onChange={set("kind")} />
      <Field label="עיר" value={form.city} onChange={set("city")} mode="text" />
      <Field label="אזור בעיר (למשל: כניסה לעיר / שכונה רחוקה)" value={form.area} onChange={set("area")} mode="text" />
      <Field label="יעד / תיאור" value={form.destination} onChange={set("destination")} mode="text" />
      <Field label="המחיר שהוצע / שקיבלת (₪)" value={form.price} onChange={set("price")} />
      <Field label="שעת יציאה (איך הפקקים משפיעים)" value={form.start} onChange={set("start")} mode="time" />
      {ownTrips.length > 0 && (
        <Select label="על הדרך של אחת הנסיעות הקבועות שלי?" value={form.onWay} options={[{ value: "", label: "לא — נסיעה ייעודית" }, ...ownTrips.map((o) => ({ value: o.name, label: o.name }))]} onChange={set("onWay")} />
      )}
      {onWay ? (
        <>
          <Field label='ק"מ עיקוף (מעבר למה שהיית נוסע בכל מקרה)' value={form.extraKm} onChange={set("extraKm")} />
          <Field label="דקות עיקוף (בפועל, עם הפקקים)" value={form.extraMinutes} onChange={set("extraMinutes")} />
        </>
      ) : (
        <>
          <Field label='ק"מ לכיוון אחד' value={form.km} onChange={set("km")} />
          <Field label="דקות לכיוון אחד (בפועל, עם הפקקים)" value={form.minutes} onChange={set("minutes")} />
          <Select<CommuteReturn | ""> label="הדרך חזרה" value={form.ret} options={TRIP_RETURN_OPTIONS} onChange={set("ret")} />
          {form.ret !== "empty" && form.ret !== "continuation" && <Field label="דקות המתנה אפשריות (לתרחיש המתנה)" value={form.waiting} onChange={set("waiting")} />}
        </>
      )}
      <Select label="מחיר ששולם" value={form.cls} options={CLASS_OPTIONS} onChange={set("cls")} />
      <details>
        <summary>תחנות נוספות בנסיעה</summary>
        <div className="fcc-stack fcc-stack--tight">
          <Field label="כמה תחנות נוספות" value={form.stops} onChange={set("stops")} />
          <Field label="כמה מהמחיר הוא התוספת על התחנות (₪)" value={form.stopsPrice} onChange={set("stopsPrice")} />
          <Field label='כמה ק"מ הוסיפו התחנות' value={form.stopsKm} onChange={set("stopsKm")} />
          <Field label="כמה דקות הוסיפו התחנות (עם הפקקים של אותה שעה)" value={form.stopsMinutes} onChange={set("stopsMinutes")} />
        </div>
      </details>
      <Field label="תאריך (לתיעוד נסיעה)" value={form.date} onChange={set("date")} mode="date" />
      <div className="fcc-chips">
        <button type="submit" disabled={busy} className="boss-button boss-button--primary">בדיקת כדאיות</button>
        <button type="button" disabled={busy} className="boss-button" onClick={() => onSubmit(form)}>קיבלתי — שמירה כנסיעה</button>
      </div>
      {evaluation && <EvaluationView ev={evaluation} />}
    </form>
  );
}

function PendingRowView({ row, busy, onReturn }: { row: ReturnType<typeof pendingRows>[number]; busy: boolean; onReturn: (tripId: string, status: CommuteReturn, waiting: string) => void }) {
  const [wait, setWait] = useState("");
  return (
    <li>
      <strong>{row.title}</strong>
      <div className="fcc-loan__meta">{row.detail}</div>
      <div className="fcc-chips" role="group" aria-label={`הדרך חזרה — ${row.title}`}>
        <button type="button" disabled={busy} className="fcc-chip" onClick={() => onReturn(row.id, "empty", "")}>חזרתי ריק</button>
        <button type="button" disabled={busy} className="fcc-chip" onClick={() => onReturn(row.id, "continuation", "")}>היה המשך</button>
      </div>
      <div className="fcc-chips">
        <input value={wait} onChange={(e) => setWait(e.target.value)} inputMode="decimal" className="boss-input" aria-label="דקות המתנה" placeholder="דקות המתנה" />
        <button type="button" disabled={busy} className="fcc-chip" onClick={() => onReturn(row.id, "waited", wait)}>ישבתי בצד</button>
      </div>
    </li>
  );
}

function SettingsFormView({ initial, busy, onSubmit }: { initial: SettingsForm; busy: boolean; onSubmit: (form: SettingsForm) => void }) {
  const [form, setForm] = useState<SettingsForm>(initial);
  const set = <K extends keyof SettingsForm>(k: K) => (v: string) => setForm({ ...form, [k]: v });
  return (
    <form className="fcc-stack fcc-stack--tight" onSubmit={(e) => { e.preventDefault(); onSubmit(form); }}>
      <Field label='מכסת ק"מ חינם בחודש' value={form.freeKm} onChange={set("freeKm")} />
      <Field label="מכסת דלק חינם בחודש (₪)" value={form.freeFuel} onChange={set("freeFuel")} />
      <Field label='עלות דלק לק"מ (₪) — להמרת מכסת הדלק לק"מ' value={form.fuelCost} onChange={set("fuelCost")} />
      <Field label='עלות כל ק"מ מעל המכסה (₪)' value={form.costPerKm} onChange={set("costPerKm")} />
      <Field label='ק"מ שכבר נסעת החודש בנסיעות אחרות' value={form.otherKm} onChange={set("otherKm")} />
      <button type="submit" disabled={busy} className="boss-button boss-button--primary">שמירת הגדרות</button>
    </form>
  );
}

function ProfitTable({ rows, label }: { rows: ProfitRow[]; label: string }) {
  return (
    <div className="fcc-table-scroll" role="region" tabIndex={0} aria-label={label}>
      <table className="fcc-compare__table">
        <thead><tr><th>{label}</th><th>נסיעות</th><th>מחיר ממוצע</th><th>לק״מ</th><th>לשעה</th><th>נטו לשעה</th></tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.key}>
              <th scope="row">{r.label}{r.extra && <small className="fcc-cell__split">{r.extra}</small>}</th>
              <td>{r.rides}</td><td>{r.avgPrice}</td><td>{r.perKm}</td><td>{r.perHour}</td><td>{r.netPerHour}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Presentational part (also rendered in tests): server numbers only. */
export function CommuteView({ data, busy, error, evaluation, onAnswer, onTiming, onSaveRoute, onSaveTrip, onSaveSettings, onEvaluate, onReturn }: {
  data: FccCommute; busy: boolean; error: string | null; evaluation: FccCommuteEvaluation | null; onAnswer: (routeId: string, date: string, key: AnswerKey) => void;
  onTiming: (body: TimingBody) => void;
  onSaveRoute: (form: RouteForm, routeId?: string) => void; onSaveTrip: (form: TripForm) => void; onSaveSettings: (form: SettingsForm) => void; onEvaluate: (form: TripForm) => void;
  onReturn: (tripId: string, status: CommuteReturn, waiting: string) => void;
}) {
  const summary = summaryModel(data);
  const trips = tripRows(data);
  const quota = quotaRows(data.quota);
  const profit = profitModel(data.profitability);
  const timing = timeModel(data.profitability);
  const place = placeModel(data.profitability);
  const stops = stopsModel(data.profitability);
  const pending = pendingRows(data.pending_updates);
  const back = returnModel(data.return_stats);
  return (
    <div className="fcc-stack">
      {error && <p className="fcc-goal__note" role="alert">{error}</p>}
      {(data.routes.length > 0 || data.one_off.trips > 0) && <div className="fcc-kpis">{summary.cards.map((c) => <KpiCard key={c.key} label={c.label} value={c.value} hint={c.hint} />)}</div>}

      <Surface variant="subtle" padding="compact" className="fcc-loans-goal fcc-refi" aria-label="הצעה לנסיעה">
        <h3 className="fcc-loans-goal__title">הצעה לנסיעה — כדאי?</h3>
        <p className="fcc-loan__meta">הזינו מחיר, ק״מ וזמן שהוצעו וקבלו את הכדאיות לפני שמחליטים. מה שלא ידוע עדיין (הדרך חזרה) מחושב בשלושה תרחישים, ומתעדכן אחרי הנסיעה.</p>
        <TripFormView today={data.today} ownTrips={data.own_trips} busy={busy} evaluation={evaluation} onEvaluate={onEvaluate} onSubmit={onSaveTrip} />
      </Surface>

      {pending.length > 0 && (
        <Surface variant="subtle" padding="compact" className="fcc-loans-goal fcc-refi" aria-label="ממתינות לעדכון">
          <h3 className="fcc-loans-goal__title">ממתינות לעדכון: איך חזרת?</h3>
          <p className="fcc-loan__meta">עד שתעדכנו, החישוב מניח הלוך ושוב בלי המתנה (הנחה שמרנית). זה לא מעכב את שאר החישובים.</p>
          <ul className="fcc-list">{pending.map((p) => <PendingRowView key={p.id} row={p} busy={busy} onReturn={onReturn} />)}</ul>
        </Surface>
      )}

      <Surface variant="subtle" padding="compact" className="fcc-loans-goal fcc-refi" aria-label="מכסת רכב הליסינג">
        <h3 className="fcc-loans-goal__title">מכסת הרכב (ק״מ ודלק חינם)</h3>
        {quota ? (
          <>
            <dl className="fcc-loans-goal__grid">{quota.rows.map((r) => <div key={r.label}><dt>{r.label}</dt><dd>{r.value}</dd></div>)}</dl>
            {quota.notes.map((n) => <p key={n} className="fcc-goal__note">{n}</p>)}
          </>
        ) : <p className="fcc-loan__meta">עוד לא הוגדרה מכסה — הזינו אותה בהגדרות הרכב למטה, וכך תראו כמה נותר ואילו נסיעות מנצלות אותה הכי טוב.</p>}
      </Surface>

      {data.routes.length === 0 && <ScreenState state="empty" title="אין נסיעה קבועה עדיין" message="הוסיפו אותה למטה — מחיר ליום, ק״מ וזמן לכל כיוון." />}

      {data.routes.map((r) => (
        <Surface key={r.id} variant="subtle" padding="compact" className="fcc-loans-goal fcc-refi" aria-label={r.name}>
          <h3 className="fcc-loans-goal__title">{r.name}{!r.active && " (מושהה)"}</h3>
          {r.days.length > 0 && (
            <>
              {r.days.filter((d) => d.is_tomorrow).map((d) => (
                <div key={d.date} className="fcc-stack fcc-stack--tight">
                  <h4 className="fcc-pay__subhead">{dayLabel(d)} — יש נסיעה?</h4>
                  <AnswerButtons route={r} day={d} busy={busy} onAnswer={(date, key) => onAnswer(r.id, date, key)} />
                </div>
              ))}
              <details>
                <summary>עדכון ימים אחרונים (תחנות, שעת יציאה, זמן בפועל)</summary>
                <div className="fcc-stack fcc-stack--tight">
                  {r.days.filter((d) => !d.is_tomorrow).map((d) => (
                    <div key={d.date}>
                      <div className="fcc-loan__meta">{dayLabel(d)}{d.outcome == null && (d.rest_day ? " · יום מנוחה" : " · לא עודכן")}{dayTiming(d) && ` · ${dayTiming(d)}`}</div>
                      <AnswerButtons route={r} day={d} busy={busy} onAnswer={(date, key) => onAnswer(r.id, date, key)} />
                      <DayTiming key={`${d.date}-${d.start_time}-${d.minutes_one_way}`} route={r} day={d} busy={busy} onSave={onTiming} />
                    </div>
                  ))}
                </div>
              </details>
            </>
          )}

          <h4 className="fcc-pay__subhead">החודש לפי שבועות</h4>
          {r.this_month.weeks.length === 0 ? <p className="fcc-loan__meta">עוד לא נרשמו ימי נסיעה החודש</p> : (
            <div className="fcc-table-scroll" role="region" tabIndex={0} aria-label="שבועות">
              <table className="fcc-compare__table">
                <thead><tr><th>שבוע</th><th>ימי נסיעה</th><th>הכנסה</th></tr></thead>
                <tbody>{weekRows(r).map((w) => <tr key={w.key}><th scope="row">{w.label}</th><td>{w.days}</td><td>{w.income}</td></tr>)}</tbody>
              </table>
            </div>
          )}
          {timedLine(r) && <p className="fcc-loan__meta">{timedLine(r)}</p>}
          {r.stops_note && <p className="fcc-goal__note">{r.stops_note}</p>}

          <h4 className="fcc-pay__subhead">שני הצדדים ביום רגיל</h4>
          <div className="fcc-table-scroll" role="region" tabIndex={0} aria-label="שני הצדדים">
            <table className="fcc-compare__table">
              <thead><tr><th>צד</th><th>יציאה</th><th>ק״מ</th><th>דקות</th><th>מלא/ריק</th><th>בלי תשלום</th></tr></thead>
              <tbody>{legRows(r).map((l) => <tr key={l.key}><th scope="row">{l.label}</th><td>{l.start}</td><td>{l.km}</td><td>{l.minutes}</td><td>{l.load}</td><td>{l.unpaid}</td></tr>)}</tbody>
            </table>
          </div>
          {(() => {
            const dec = decisionModel(r);
            return dec && (
              <>
                <h4 className="fcc-pay__subhead">החלטה לחודש: לשמור את הנסיעה?</h4>
                <dl className="fcc-loans-goal__grid">{dec.lines.map((x) => <div key={x.label}><dt>{x.label}</dt><dd>{x.value}</dd></div>)}</dl>
                {dec.legs.length > 0 && (
                  <ul className="fcc-list">{dec.legs.map((l) => <li key={l.key}><strong>{l.label}{l.slow ? " (האיטי יותר)" : ""}</strong><div className="fcc-loan__meta">ממוצע {l.avg} · {l.total} · {l.days}</div></li>)}</ul>
                )}
                {dec.note && <p className="fcc-loan__meta">{dec.note}</p>}
              </>
            );
          })()}

          <h4 className="fcc-pay__subhead">כדאיות ליום נסיעה</h4>
          <dl className="fcc-loans-goal__grid">
            {economicsRows(r).map((x) => <div key={x.label}><dt>{x.label}</dt><dd>{x.value}</dd></div>)}
          </dl>
          {economicsHint(r) && <p className="fcc-loan__meta">{economicsHint(r)}</p>}

          <details>
            <summary>עריכת המסלול</summary>
            <RouteFormView initial={formFromRoute(r)} submitLabel="שמירת שינויים" busy={busy} onSubmit={(f) => onSaveRoute(f, r.id)} />
          </details>
        </Surface>
      ))}

      <section className="fcc-section" aria-labelledby="commute-profit-heading">
        <h2 id="commute-profit-heading" className="fcc-section__heading">אילו נסיעות השתלמו</h2>
        {profit.destinations.length === 0 ? <p className="fcc-loan__meta">עוד אין נסיעות שנרשמו להשוואה</p> : (
          <>
            <ProfitTable rows={profit.destinations} label="יעד" />
            {profit.groups.length > 0 && <ProfitTable rows={profit.groups} label="לפי סוג" />}
            <p className="fcc-loan__meta">מסודר לפי ₪ לכל ק״מ מהמכסה, מהגבוה לנמוך. {profit.note}</p>
          </>
        )}
      </section>

      <section className="fcc-section" aria-labelledby="commute-place-heading">
        <h2 id="commute-place-heading" className="fcc-section__heading">לפי עיר ואזור</h2>
        {place.cities.length === 0 ? <p className="fcc-loan__meta">הוסיפו עיר ואזור לנסיעות — וכאן יוצג איפה כדאי יותר (כניסה לעיר מול שכונה רחוקה).</p> : (
          <div className="fcc-table-scroll" role="region" tabIndex={0} aria-label="ערים ואזורים">
            <table className="fcc-compare__table">
              <thead><tr><th>מקום</th><th>נסיעות</th><th>מחיר ממוצע</th><th>לק״מ</th><th>לשעה</th><th>מהממוצע (לק״מ)</th></tr></thead>
              <tbody>{[...place.cities.map((r) => ({ ...r, label: `${r.label} (כל העיר)` })), ...place.areas].map((r) => <tr key={r.key}><th scope="row">{r.label}</th><td>{r.rides}</td><td>{r.avgPrice}</td><td>{r.perKm}</td><td>{r.perHour}</td><td>{r.vsAverage}</td></tr>)}</tbody>
            </table>
          </div>
        )}
        {place.note && <p className="fcc-loan__meta">{place.note}</p>}
      </section>

      {stops && (
        <section className="fcc-section" aria-labelledby="commute-stops-heading">
          <h2 id="commute-stops-heading" className="fcc-section__heading">תחנות נוספות: האם הן משתלמות</h2>
          <dl className="fcc-loans-goal__grid">{stops.lines.map((l) => <div key={l.label}><dt>{l.label}</dt><dd>{l.value}</dd></div>)}</dl>
          {stops.bands.length > 0 && (
            <div className="fcc-table-scroll" role="region" tabIndex={0} aria-label="תחנות לפי שעות">
              <table className="fcc-compare__table">
                <thead><tr><th>שעות</th><th>נסיעות</th><th>דקות לתחנה</th><th>התחנות לשעה</th></tr></thead>
                <tbody>{stops.bands.map((b) => <tr key={b.key}><th scope="row">{b.label}</th><td>{b.rides}</td><td>{b.minutes}</td><td>{b.perHour}</td></tr>)}</tbody>
              </table>
            </div>
          )}
          {stops.note && <p className="fcc-goal__note">{stops.note}</p>}
        </section>
      )}

      <section className="fcc-section" aria-labelledby="commute-back-heading">
        <h2 id="commute-back-heading" className="fcc-section__heading">מה קורה בדרך חזרה</h2>
        {back.rows[0].known === "0" ? <p className="fcc-loan__meta">עוד לא תועדה דרך חזרה — עדכנו אחרי כל נסיעה והנתונים יצטברו.</p> : (
          <div className="fcc-table-scroll" role="region" tabIndex={0} aria-label="דרך חזרה">
            <table className="fcc-compare__table">
              <thead><tr><th>יעד</th><th>נסיעות מתועדות</th><th>חוזר ריק</th><th>יש המשך</th><th>המתנה</th></tr></thead>
              <tbody>{back.rows.map((r) => <tr key={r.key}><th scope="row">{r.label}</th><td>{r.known}</td><td>{r.empty}</td><td>{r.continuation}</td><td>{r.waited}</td></tr>)}</tbody>
            </table>
          </div>
        )}
        <p className="fcc-loan__meta">{back.note}</p>
      </section>

      <section className="fcc-section" aria-labelledby="commute-time-heading">
        <h2 id="commute-time-heading" className="fcc-section__heading">פקקים: איך שעת היציאה משנה את הנסיעה</h2>
        {timing.rows.length === 0 ? <p className="fcc-loan__meta">הוסיפו שעת יציאה ודקות בפועל לנסיעות — וכאן יוצג כמה זמן אותה נסיעה לוקחת בכל שעה ומה המחיר לשעה.</p> : (
          <>
            <div className="fcc-table-scroll" role="region" tabIndex={0} aria-label="שעות ביום">
              <table className="fcc-compare__table">
                <thead><tr><th>שעות</th><th>נסיעות</th><th>זמן ממוצע</th><th>לשעה</th><th>לק״מ</th></tr></thead>
                <tbody>{timing.rows.map((r) => <tr key={r.key}><th scope="row">{r.label}</th><td>{r.rides}</td><td>{r.avgMinutes}</td><td>{r.perHour}</td><td>{r.perKm}</td></tr>)}</tbody>
              </table>
            </div>
            {timing.insights.length > 0 && <ul className="fcc-list">{timing.insights.map((i) => <li key={i.key}><strong>{i.title}</strong><div className="fcc-loan__meta">{i.detail}</div></li>)}</ul>}
            {timing.insights.length === 0 && <p className="fcc-loan__meta">עוד אין מספיק נסיעות לאותו יעד בשעות שונות כדי להשוות (לפחות 2 בכל טווח שעות).</p>}
          </>
        )}
        {timing.note && <p className="fcc-loan__meta">{timing.note}</p>}
      </section>

      <section className="fcc-section" aria-labelledby="commute-trips-heading">
        <h2 id="commute-trips-heading" className="fcc-section__heading">טבלת נסיעות</h2>
        {trips.length === 0 ? <p className="fcc-loan__meta">עוד לא נרשמו נסיעות</p> : (
          <div className="fcc-table-scroll" role="region" tabIndex={0} aria-label="נסיעות">
            <table className="fcc-compare__table">
              <thead><tr><th>יום</th><th>מסלול / יעד</th><th>תוצאה</th><th>סכום</th><th>לק״מ</th></tr></thead>
              <tbody>{trips.map((t) => <tr key={t.key}><th scope="row">{t.date}</th><td>{t.route}{t.detail && <small className="fcc-cell__split">{t.detail}</small>}</td><td>{t.result}</td><td>{t.amount}</td><td>{t.perKm}</td></tr>)}</tbody>
            </table>
          </div>
        )}
      </section>

      <details>
        <summary>הנסיעות הקבועות שלי (לנצל על הדרך)</summary>
        {data.own_trips.length === 0 ? <p className="fcc-loan__meta">עוד לא הוזנו</p> : (
          <ul className="fcc-list">{data.own_trips.map((o) => <li key={o.id}><strong>{o.name}</strong><div className="fcc-loan__meta">{o.weekdays.join(", ") || "בלי ימים"} · {o.km_one_way == null ? "—" : `${o.km_one_way} ק״מ`} לכיוון</div></li>)}</ul>
        )}
        <RouteFormView initial={EMPTY_OWN_FORM} submitLabel="הוספת נסיעה קבועה שלי" busy={busy} onSubmit={(f) => onSaveRoute(f)} />
      </details>
      <details>
        <summary>הגדרות הרכב (מכסה ועלות)</summary>
        <SettingsFormView initial={formFromSettings(data.settings)} busy={busy} onSubmit={onSaveSettings} />
      </details>
      <details>
        <summary>הוספת מסלול קבוע בתשלום</summary>
        <RouteFormView initial={EMPTY_FORM} submitLabel="הוספת מסלול" busy={busy} onSubmit={(f) => onSaveRoute(f)} />
      </details>
      <p className="fcc-loan__meta">הכנסה = ימי נסיעה שסומנו × מחיר ליום + נסיעות ומשלוחים שהוזנו. מספר התחנות נרשם למעקב ואינו משנה את הסכום. ההכנסה נכנסת להכנסה החודשית בתזרים.</p>
    </div>
  );
}

/** The "נסיעות" tab: own call, own states (a 404 means the screen is not active for this user). Reloads each time the tab is opened (the panels stay mounted). */
export function CommuteSection({ active, reloadKey }: { active: boolean; reloadKey?: string | null }) {
  const [state, setState] = useState<State>({ status: "loading" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [seen, setSeen] = useState(false);
  const [evaluation, setEvaluation] = useState<FccCommuteEvaluation | null>(null);
  const load = useCallback((silent = false) => {
    if (!silent) setState({ status: "loading" });
    fetchFccCommute().then((data) => setState({ status: "ok", data })).catch((e: unknown) => { if (!silent) setState({ status: "error", code: (e as { status?: number }).status }); });
  }, []);
  useEffect(() => { if (active) { load(seen); setSeen(true); } }, [active, reloadKey]);      // eslint-disable-line react-hooks/exhaustive-deps

  const run = async (call: () => Promise<FccCommute>) => {
    setBusy(true); setError(null);
    try { setState({ status: "ok", data: await call() }); }
    catch (e) { setError((e as Error).message || "העדכון נכשל — אפשר לנסות שוב."); }
    finally { setBusy(false); }
  };
  if (!seen && !active) return null;
  if (state.status === "loading") return <ScreenState state="loading" title="טוען נסיעות" message="מחשב את החודש…" />;
  if (state.status === "error") {
    const hidden = state.code === 404 || state.code === 401 || state.code === 403;
    return (
      <ScreenState state="error" title={hidden ? "המסך אינו זמין" : "לא הצלחנו לטעון את הנסיעות"} message={hidden ? "המסך אישי ונגיש לבעל הרשומה בלבד." : "אפשר לנסות שוב בעוד רגע."}
                   action={!hidden && <button type="button" className="boss-button boss-button--primary boss-bubble--action" onClick={() => load()}>נסו שוב</button>} />
    );
  }
  return (
    <CommuteView data={state.data} busy={busy} error={error} evaluation={evaluation}
                 onEvaluate={(form) => {
                   const parsed = evaluateBody(form);
                   if ("error" in parsed) { setError(parsed.error); return; }
                   setBusy(true); setError(null);
                   postFccCommuteEvaluate(parsed.body).then(setEvaluation).catch((e: Error) => setError(e.message || "הבדיקה נכשלה")).finally(() => setBusy(false));
                 }}
                 onReturn={(tripId, status, waiting) => {
                   const parsed = returnBody(tripId, status, waiting);
                   if ("error" in parsed) { setError(parsed.error); return; }
                   void run(() => postFccCommuteTrip(parsed.body));
                 }}
                 onAnswer={(routeId, date, key) => void run(() => postFccCommuteDay(answerBody(routeId, date, key)))}
                 onTiming={(body) => void run(() => postFccCommuteDay(body))}
                 onSaveRoute={(form, routeId) => {
                   const parsed = routeBody(form, routeId);
                   if ("error" in parsed) { setError(parsed.error); return; }
                   void run(() => postFccCommuteRoute(parsed.body));
                 }}
                 onSaveTrip={(form) => {
                   const parsed = tripBody(form);
                   if ("error" in parsed) { setError(parsed.error); return; }
                   setEvaluation(null);
                   void run(() => postFccCommuteTrip(parsed.body));
                 }}
                 onSaveSettings={(form) => {
                   const parsed = settingsBody(form);
                   if ("error" in parsed) { setError(parsed.error); return; }
                   void run(() => postFccCommuteSettings(parsed.body));
                 }} />
  );
}
