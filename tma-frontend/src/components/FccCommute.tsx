import { useCallback, useEffect, useState } from "react";
import { fetchFccCommute, postFccCommuteDay, postFccCommuteRoute } from "../api";
import type { FccCommute, FccCommuteRoute } from "../types";
import {
  ANSWERS, EMPTY_FORM, answerBody, answerOf, dayLabel, economicsHint, economicsRows, formFromRoute, routeBody, summaryModel, tripRows, weekRows,
  type AnswerKey, type RouteForm,
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

function RouteFormView({ initial, submitLabel, busy, onSubmit }: { initial: RouteForm; submitLabel: string; busy: boolean; onSubmit: (form: RouteForm) => void }) {
  const [form, setForm] = useState<RouteForm>(initial);
  const set = (k: keyof RouteForm) => (e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [k]: e.target.value });
  const field = (k: keyof RouteForm, label: string, mode: "text" | "decimal" = "decimal") => (
    <label className="fcc-field"><span>{label}</span><input value={form[k]} onChange={set(k)} inputMode={mode} className="boss-input" /></label>
  );
  return (
    <form className="fcc-stack fcc-stack--tight" onSubmit={(e) => { e.preventDefault(); onSubmit(form); }}>
      {field("name", "שם המסלול", "text")}
      {field("price", "מחיר ליום נסיעה (₪)")}
      {field("km", 'ק"מ לכל כיוון (חד פעמי)')}
      {field("minutes", "דקות לכל כיוון")}
      {field("cost", 'עלות רכב לק"מ (₪, לא חובה — בלי זה אין נטו)')}
      {field("days", "ימי נסיעה בשבוע")}
      <button type="submit" disabled={busy} className="boss-button boss-button--primary">{submitLabel}</button>
    </form>
  );
}

/** Presentational part (also rendered in tests): server numbers only. */
export function CommuteView({ data, busy, error, onAnswer, onSaveRoute }: {
  data: FccCommute; busy: boolean; error: string | null; onAnswer: (routeId: string, date: string, key: AnswerKey) => void; onSaveRoute: (form: RouteForm, routeId?: string) => void;
}) {
  const summary = summaryModel(data);
  const trips = tripRows(data);
  return (
    <div className="fcc-stack">
      {error && <p className="fcc-goal__note" role="alert">{error}</p>}
      {data.routes.length > 0 && <div className="fcc-kpis">{summary.cards.map((c) => <KpiCard key={c.key} label={c.label} value={c.value} hint={c.hint} />)}</div>}

      {data.routes.length === 0 && <ScreenState state="empty" title="אין מסלול עדיין" message="הוסיפו את הנסיעה הקבועה למטה — מחיר ליום, ק״מ וזמן לכל כיוון." />}

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
                <summary>עדכון ימים אחרונים</summary>
                <div className="fcc-stack fcc-stack--tight">
                  {r.days.filter((d) => !d.is_tomorrow).map((d) => (
                    <div key={d.date}>
                      <div className="fcc-loan__meta">{dayLabel(d)}{d.outcome == null && " · לא עודכן"}</div>
                      <AnswerButtons route={r} day={d} busy={busy} onAnswer={(date, key) => onAnswer(r.id, date, key)} />
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
          {r.stops_note && <p className="fcc-goal__note">{r.stops_note}</p>}

          <h4 className="fcc-pay__subhead">כדאיות ליום נסיעה</h4>
          <dl className="fcc-loans-goal__grid">
            {economicsRows(r).map((m) => <div key={m.label}><dt>{m.label}</dt><dd>{m.value}</dd></div>)}
          </dl>
          {economicsHint(r) && <p className="fcc-loan__meta">{economicsHint(r)}</p>}

          <details>
            <summary>עריכת המסלול</summary>
            <RouteFormView initial={formFromRoute(r)} submitLabel="שמירת שינויים" busy={busy} onSubmit={(f) => onSaveRoute(f, r.id)} />
          </details>
        </Surface>
      ))}

      <section className="fcc-section" aria-labelledby="commute-trips-heading">
        <h2 id="commute-trips-heading" className="fcc-section__heading">טבלת נסיעות</h2>
        {trips.length === 0 ? <p className="fcc-loan__meta">עוד לא נרשמו נסיעות</p> : (
          <div className="fcc-table-scroll" role="region" tabIndex={0} aria-label="נסיעות">
            <table className="fcc-compare__table">
              <thead><tr><th>יום</th><th>מסלול</th><th>תוצאה</th><th>סכום</th></tr></thead>
              <tbody>{trips.map((t) => <tr key={t.key}><th scope="row">{t.date}</th><td>{t.route}</td><td>{t.result}</td><td>{t.amount}</td></tr>)}</tbody>
            </table>
          </div>
        )}
      </section>

      <details>
        <summary>הוספת מסלול</summary>
        <RouteFormView initial={EMPTY_FORM} submitLabel="הוספת מסלול" busy={busy} onSubmit={(f) => onSaveRoute(f)} />
      </details>
      <p className="fcc-loan__meta">הכנסה = ימי נסיעה שסומנו × מחיר ליום. מספר התחנות נרשם למעקב ואינו משנה את הסכום. ההכנסה נכנסת להכנסה החודשית בתזרים.</p>
    </div>
  );
}

/** The "נסיעות" tab: own call, own states (a 404 means the screen is not active for this user). Reloads each time the tab is opened (the panels stay mounted). */
export function CommuteSection({ active, reloadKey }: { active: boolean; reloadKey?: string | null }) {
  const [state, setState] = useState<State>({ status: "loading" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [seen, setSeen] = useState(false);
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
    <CommuteView data={state.data} busy={busy} error={error}
                 onAnswer={(routeId, date, key) => void run(() => postFccCommuteDay(answerBody(routeId, date, key)))}
                 onSaveRoute={(form, routeId) => {
                   const parsed = routeBody(form, routeId);
                   if ("error" in parsed) { setError(parsed.error); return; }
                   void run(() => postFccCommuteRoute(parsed.body));
                 }} />
  );
}
