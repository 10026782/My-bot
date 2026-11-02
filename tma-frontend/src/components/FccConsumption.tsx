import { useCallback, useEffect, useState } from "react";
import { fetchFccConsumption } from "../api";
import type { FccConsumption } from "../types";
import { DEFAULT_RANGE, RANGES } from "../lib/fccCashflow";
import { consumptionModel } from "../lib/fccConsumption";
import { KpiCard } from "./FccKpiCard";
import { ScreenState } from "./ui/ScreenState";

type State = { status: "loading" } | { status: "ok"; data: FccConsumption } | { status: "error"; code?: number };

/** Presentational part (also rendered in tests): server numbers only. */
export function ConsumptionView({ data, selected, onSelect, range, onRange }: {
  data: FccConsumption; selected: string; onSelect: (month: string) => void; range: number; onRange: (months: number) => void;
}) {
  const m = consumptionModel(data, selected);
  return (
    <div className="fcc-stack">
      <div className="fcc-chips" role="group" aria-label="טווח חודשים">
        {RANGES.map((r) => (
          <button key={r} type="button" aria-pressed={range === r} className={`fcc-chip ${range === r ? "fcc-chip--on" : ""}`} onClick={() => onRange(r)}>{r} חודשים</button>
        ))}
      </div>

      {m.detail && (
        <section className="fcc-section" aria-labelledby="cons-month-heading">
          <div className="fcc-chips" role="group" aria-label="מעבר בין חודשים">
            <button type="button" className="fcc-chip" disabled={!m.older} onClick={() => m.older && onSelect(m.older.month)}>{m.older ? `← ${m.older.label}` : "← אין חודש קודם"}</button>
            <button type="button" className="fcc-chip" disabled={!m.newer} onClick={() => m.newer && onSelect(m.newer.month)}>{m.newer ? `${m.newer.label} →` : "אין חודש הבא →"}</button>
          </div>
          <h2 id="cons-month-heading" className="fcc-section__heading">{m.detail.label}</h2>
          {m.detail.partialNote && <p className="fcc-goal__note">{m.detail.partialNote}</p>}
          <div className="fcc-kpis"><KpiCard label="צריכה" value={m.detail.total} hint={m.detail.installments ?? undefined} /></div>

          <h3 className="fcc-section__heading">צריכה לפי קטגוריה</h3>
          {m.detail.categories.length === 0 ? <ScreenState state="empty" title="לא נרשמה צריכה בחודש הזה" /> : (
            <div className="fcc-list">
              {m.detail.categories.map((c) => (
                <div key={c.key} className="fcc-cf-cat">
                  <div className="fcc-cf-cat__line"><span>{c.label}{c.custom && " ✦"}</span><strong>{c.value}</strong></div>
                  <div className="fcc-goal__bar" role="progressbar" aria-label={c.label} aria-valuenow={c.pct} aria-valuemin={0} aria-valuemax={100}><span style={{ inlineSize: `${c.pct}%` }} /></div>
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      <section className="fcc-section" aria-labelledby="cons-months-heading">
        <h2 id="cons-months-heading" className="fcc-section__heading">חודש אחר חודש</h2>
        <div className="fcc-list">
          {m.rows.map((r) => (
            <button key={r.month} type="button" className={`fcc-cf-row fcc-cf-row--${r.tone} ${r.month === m.selected ? "fcc-cf-row--on" : ""}`}
                    aria-pressed={r.month === m.selected} onClick={() => onSelect(r.month)}>
              <span className="fcc-cf-row__month">{r.label}{r.tag && <small> · {r.tag}</small>}</span>
              <strong>צריכה {r.total}</strong>
            </button>
          ))}
        </div>
      </section>

      {m.insights.length > 0 && (
        <section className="fcc-section" aria-labelledby="cons-insights-heading">
          <h2 id="cons-insights-heading" className="fcc-section__heading">שינויים וחריגות</h2>
          <div className="fcc-list">{m.insights.map((line) => <div key={line} className="fcc-task"><p>{line}</p></div>)}</div>
        </section>
      )}
      {m.notes.map((n) => <p key={n} className="fcc-goal__note">{n}</p>)}
    </div>
  );
}

/** The "צריכה" tab: own call, own states (a 404 means the screen is not active for this user). Reloads each time the tab is opened (the panels stay mounted). */
export function ConsumptionSection({ active, reloadKey }: { active: boolean; reloadKey?: string | null }) {
  const [range, setRange] = useState<number>(DEFAULT_RANGE);
  const [selected, setSelected] = useState<string>("");
  const [state, setState] = useState<State>({ status: "loading" });
  const load = useCallback((months: number, silent = false) => {
    if (!silent) setState({ status: "loading" });
    fetchFccConsumption(months)
      .then((data) => { setState({ status: "ok", data }); if (!silent) setSelected(""); })
      .catch((e: unknown) => { if (!silent) setState({ status: "error", code: (e as { status?: number }).status }); });
  }, []);
  const [seen, setSeen] = useState(false);
  useEffect(() => { if (active) { load(range, seen); setSeen(true); } }, [active, range, reloadKey]);       // eslint-disable-line react-hooks/exhaustive-deps

  if (!seen && !active) return null;
  if (state.status === "loading") return <ScreenState state="loading" title="טוען צריכה לפי חודש" message="מחשב לפי תאריך הקנייה…" />;
  if (state.status === "error") {
    const hidden = state.code === 404 || state.code === 401 || state.code === 403;
    return (
      <ScreenState state="error" title={hidden ? "המסך אינו זמין" : "לא הצלחנו לטעון את הצריכה"} message={hidden ? "המסך אישי ונגיש לבעל הרשומה בלבד." : "אפשר לנסות שוב בעוד רגע."}
                   action={!hidden && <button type="button" className="boss-button boss-button--primary boss-bubble--action" onClick={() => load(range)}>נסו שוב</button>} />
    );
  }
  return <ConsumptionView data={state.data} selected={selected} onSelect={setSelected} range={range} onRange={setRange} />;
}
