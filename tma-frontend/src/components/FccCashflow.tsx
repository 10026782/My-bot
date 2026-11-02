import { useCallback, useEffect, useState } from "react";
import { fetchFccCashflow } from "../api";
import type { FccCashflow } from "../types";
import { DEFAULT_RANGE, RANGES, cashflowModel, monthNav, recsModel } from "../lib/fccCashflow";
import { KpiCard } from "./FccKpiCard";
import { FccClassify } from "./FccClassify";
import { FccClassifyRules } from "./FccClassifyRules";
import { FccImport } from "./FccImport";
import { ScreenState } from "./ui/ScreenState";
import { StatusBadge } from "./ui/StatusBadge";

type State = { status: "loading" } | { status: "ok"; data: FccCashflow } | { status: "error"; code?: number };

/** Presentational part (also rendered in tests): server numbers only. */
export function CashflowView({ data, selected, onSelect, range, onRange }: {
  data: FccCashflow; selected: string; onSelect: (month: string) => void; range: number; onRange: (months: number) => void;
}) {
  const m = cashflowModel(data, selected);
  const recs = recsModel(data);
  const nav = monthNav(m.rows, m.selected);
  return (
    <div className="fcc-stack">
      <div className="fcc-chips" role="group" aria-label="טווח חודשים">
        {RANGES.map((r) => (
          <button key={r} type="button" aria-pressed={range === r} className={`fcc-chip ${range === r ? "fcc-chip--on" : ""}`} onClick={() => onRange(r)}>{r} חודשים</button>
        ))}
      </div>

      {m.detail && (
        <section className="fcc-section" aria-labelledby="cf-month-heading">
          <div className="fcc-chips" role="group" aria-label="מעבר בין חודשים">
            <button type="button" className="fcc-chip" disabled={!nav.older} onClick={() => nav.older && onSelect(nav.older.month)}>{nav.older ? `← ${nav.older.label}` : "← אין חודש קודם"}</button>
            <button type="button" className="fcc-chip" disabled={!nav.newer} onClick={() => nav.newer && onSelect(nav.newer.month)}>{nav.newer ? `${nav.newer.label} →` : "אין חודש הבא →"}</button>
          </div>
          <h2 id="cf-month-heading" className="fcc-section__heading">{m.detail.label}</h2>
          {m.detail.partialNote && <p className="fcc-goal__note">{m.detail.partialNote}</p>}
          <div className="fcc-kpis">{m.detail.kpis.map((k) => <KpiCard key={k.key} label={k.label} value={k.value} hint={k.hint} />)}</div>
          {m.detail.missingNote && <p className="fcc-goal__note">{m.detail.missingNote}</p>}

          <h3 className="fcc-section__heading">הכנסות לפי מקור</h3>
          {m.detail.sources.length === 0 ? <ScreenState state="empty" title="לא נרשמו הכנסות בחודש הזה" /> : (
            <div className="fcc-list">
              {m.detail.sources.map((s) => (
                <div key={s.key} className="fcc-event"><span>{s.name}</span><strong>{s.value}</strong>{s.hint && <span className="fcc-goal__note">{s.hint}</span>}</div>
              ))}
            </div>
          )}

          <h3 className="fcc-section__heading">הוצאות לפי קטגוריה</h3>
          {m.detail.categories.length === 0 ? <ScreenState state="empty" title="לא נרשמו הוצאות בחודש הזה" /> : (
            <div className="fcc-list">
              {m.detail.categories.map((c) => (
                <div key={c.key} className="fcc-cf-cat">
                  <div className="fcc-cf-cat__line">
                    <span>{c.label}{c.custom && " ✦"}</span>
                    <strong>{c.value}</strong>
                    {c.estimate && <StatusBadge tone="warning">הערכה</StatusBadge>}
                  </div>
                  <div className="fcc-goal__bar" role="progressbar" aria-label={c.label} aria-valuenow={c.pct} aria-valuemin={0} aria-valuemax={100}><span style={{ inlineSize: `${c.pct}%` }} /></div>
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      <section className="fcc-section" aria-labelledby="cf-recs-heading">
        <h2 id="cf-recs-heading" className="fcc-section__heading">הזדמנויות לחיסכון</h2>
        {recs.summary.map((l) => <p key={l} className="fcc-goal__note">{l}</p>)}
        {recs.empty ? <ScreenState state="empty" title="אין כרגע נקודות לבדיקה" message="סמנו התחייבויות לצמצום או רשמו עוד הוצאות עם קטגוריה." /> : (
          <div className="fcc-list">
            {recs.cards.map((c) => (
              <div key={c.id} className={`fcc-task fcc-rec fcc-rec--${c.tone}`}>
                <h3>{c.title}</h3>
                {c.amount && <StatusBadge tone={c.tone === "saving" ? "success" : c.tone === "estimate" ? "info" : "warning"}>{c.amount}</StatusBadge>}
                {c.facts.map((f) => <p key={f}>{f}</p>)}
                {c.hint && <p className="fcc-goal__note">{c.hint}</p>}
              </div>
            ))}
          </div>
        )}
        {recs.more && <p className="fcc-goal__note">{recs.more}</p>}
        <p className="fcc-goal__note">{recs.note}</p>
      </section>

      <section className="fcc-section" aria-labelledby="cf-months-heading">
        <h2 id="cf-months-heading" className="fcc-section__heading">חודש אחר חודש</h2>
        <div className="fcc-list">
          {m.rows.map((r) => (
            <button key={r.month} type="button" className={`fcc-cf-row fcc-cf-row--${r.tone} ${r.month === m.selected ? "fcc-cf-row--on" : ""}`}
                    aria-pressed={r.month === m.selected} onClick={() => onSelect(r.month)}>
              <span className="fcc-cf-row__month">{r.label}{r.tag && <small> · {r.tag}</small>}</span>
              <span>הכנסות {r.income}</span><span>הוצאות {r.expenses}</span><strong>יתרה {r.balance}</strong>
            </button>
          ))}
        </div>
      </section>

      {m.insights.length > 0 && (
        <section className="fcc-section" aria-labelledby="cf-insights-heading">
          <h2 id="cf-insights-heading" className="fcc-section__heading">שינויים וחריגות</h2>
          <div className="fcc-list">{m.insights.map((line) => <div key={line} className="fcc-task"><p>{line}</p></div>)}</div>
        </section>
      )}
      {m.notes.map((n) => <p key={n} className="fcc-goal__note">{n}</p>)}
    </div>
  );
}

/** The "תזרים" tab: own call, own states (a 404 means the screen is not active for this user). */
export function CashflowSection({ reloadKey }: { reloadKey?: string | null }) {
  const [range, setRange] = useState<number>(DEFAULT_RANGE);
  const [selected, setSelected] = useState<string>("");
  const [state, setState] = useState<State>({ status: "loading" });
  const [importTick, setImportTick] = useState(0);                      // moves after each completed import: the classification panels reload their queue
  const load = useCallback((months: number, silent = false) => {
    if (!silent) setState({ status: "loading" });
    fetchFccCashflow(months)
      .then((data) => { setState({ status: "ok", data }); if (!silent) setSelected(""); })
      .catch((e: unknown) => { if (!silent) setState({ status: "error", code: (e as { status?: number }).status }); });
  }, []);
  useEffect(() => { load(range); }, [load, range]);
  // a saved entry (the writer's receipt) refreshes the numbers in place: no loading screen, the selected month stays
  useEffect(() => { if (reloadKey) load(range, true); }, [reloadKey]);       // eslint-disable-line react-hooks/exhaustive-deps

  if (state.status === "loading") return <ScreenState state="loading" title="טוען תזרים חודשי" message="מחשב הכנסות והוצאות לפי חודש…" />;
  if (state.status === "error") {
    const hidden = state.code === 404 || state.code === 401 || state.code === 403;
    return (
      <ScreenState state="error" title={hidden ? "התזרים אינו זמין" : "לא הצלחנו לטעון את התזרים"} message={hidden ? "המסך אישי ונגיש לבעל הרשומה בלבד." : "אפשר לנסות שוב בעוד רגע."}
                   action={!hidden && <button type="button" className="boss-button boss-button--primary boss-bubble--action" onClick={() => load(range)}>נסו שוב</button>} />
    );
  }
  return (
    <div className="fcc-stack">
      <FccClassifyRules summary={state.data.rules_to_classify} refreshKey={importTick} onChanged={() => load(range, true)} />
      <FccClassify summary={state.data.to_classify} refreshKey={importTick} onChanged={() => load(range, true)} />
      <FccImport onImported={() => { setImportTick((t) => t + 1); load(range, true); }} />
      <CashflowView data={state.data} selected={selected} onSelect={setSelected} range={range} onRange={setRange} />
    </div>
  );
}
