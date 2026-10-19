import { useEffect, useRef, useState } from "react";
import { postPortfolioLabSimulate } from "../api";
import type { PortfolioLabView } from "../types";
import {
  CRISIS_DECLINES, CRISIS_TABLE_HEAD, DEFAULT_LAB_FORM, LAB_TABLE_HEAD, STRATEGY_OPTIONS, barChartModel, breakdownParts, comparisonLines, scenarioLines, scenarioRows, SCENARIO_TABLE_HEAD, crisisTableRows, intraYearLines, timingRows, TIMING_TABLE_HEAD, growthLines,
  ils, labKpiCards, paceAssumptions, labParams, labTableRows, lineChartModel, pct, CHART_COLORS, type LabForm,
} from "../lib/familyWealth";
import { BarChart, LineChart, StackBar } from "./PortfolioLabCharts";
import { PaceTrackerPanel } from "./PaceTrackerPanel";
import { KpiCard } from "./FccKpiCard";
import { ScreenState } from "./ui/ScreenState";
import { StatusBadge } from "./ui/StatusBadge";
import { Surface } from "./ui/Surface";

type State = { status: "idle" } | { status: "loading" } | { status: "ok"; view: PortfolioLabView } | { status: "error"; message: string; code?: number };

const DEMO = <StatusBadge tone="warning">הדגמה</StatusBadge>;

/** "מעבדת העתיד": inputs -> POST /api/portfolio-lab/simulate -> render. All numbers are the server's (portfolio_lab). */
export function PortfolioLabPanel() {
  const [form, setForm] = useState<LabForm>(DEFAULT_LAB_FORM);
  const [state, setState] = useState<State>({ status: "idle" });
  const [formError, setFormError] = useState<string | null>(null);
  const latest = useRef(0);
  const set = <K extends keyof LabForm>(key: K, value: LabForm[K]) => setForm((f) => ({ ...f, [key]: value }));

  const run = (f: LabForm) => {
    const parsed = labParams(f);
    if (!parsed.ok) { setFormError(parsed.error); return; }
    setFormError(null);
    const id = ++latest.current;                     // a slower, older answer must never overwrite a newer one
    setState({ status: "loading" });
    postPortfolioLabSimulate(parsed.params)
      .then((view) => { if (id === latest.current) setState({ status: "ok", view }); })
      .catch((e: Error & { status?: number }) => { if (id === latest.current) setState({ status: "error", message: e.message, code: e.status }); });
  };
  useEffect(() => { run(DEFAULT_LAB_FORM); }, []);   // eslint-disable-line react-hooks/exhaustive-deps

  const toggleStrategy = (key: string) =>
    set("strategies", form.strategies.includes(key) ? form.strategies.filter((s) => s !== key) : [...form.strategies, key]);

  return (
    <div className="fcc-stack">
      <Surface variant="subtle" padding="compact" className="pl-banner" role="note">
        <strong>נתוני הדגמה.</strong> כל הקלטים והתשואות הם הנחות (assumption-based) ולא נתוני שוק; התוצאות אינן תחזית ואינן המלצה.
        תוצאות מס, אם יוצגו, הן תיאורטיות בלבד אלא אם אומתו חיצונית. שום דבר כאן לא נשמר ואינו משנה את הנתונים שלך.
      </Surface>

      <form className="pl-form" onSubmit={(e) => { e.preventDefault(); run(form); }} aria-label="קלטי הסימולציה">
        <div className="pl-grid">
          <label>סכום התחלתי (₪)<input inputMode="decimal" value={form.initial} onChange={(e) => set("initial", e.target.value)} /></label>
          <label>הפקדה חודשית (₪)<input inputMode="decimal" value={form.monthly} onChange={(e) => set("monthly", e.target.value)} /></label>
          <label>מספר שנים (10–100)<input inputMode="numeric" value={form.years} onChange={(e) => set("years", e.target.value)} /></label>
          <label>תשואה שנתית ברוטו (%)<input inputMode="decimal" value={form.returnPct} onChange={(e) => set("returnPct", e.target.value)} /></label>
          <label>דמי ניהול שנתיים (%)<input inputMode="decimal" value={form.feePct} onChange={(e) => set("feePct", e.target.value)} /></label>
          <label>אינפלציה שנתית (%)<input inputMode="decimal" value={form.inflationPct} onChange={(e) => set("inflationPct", e.target.value)} /></label>
          <label>תזמון הפקדה
            <select value={form.timing} onChange={(e) => set("timing", e.target.value as LabForm["timing"])}>
              <option value="end">סוף חודש</option><option value="begin">תחילת חודש</option>
            </select>
          </label>
          <label className="pl-check"><input type="checkbox" checked={form.indexed} onChange={(e) => set("indexed", e.target.checked)} />הצמדת הפקדות לאינפלציה</label>
        </div>
        <fieldset>
          <legend>השוואת אסטרטגיות</legend>
          <div className="pl-grid">
            {STRATEGY_OPTIONS.map((s) => (
              <label key={s.key} className="pl-check"><input type="checkbox" checked={form.strategies.includes(s.key)} onChange={() => toggleStrategy(s.key)} />{s.label}</label>
            ))}
          </div>
          <label className="pl-base">אסטרטגיית בסיס (נכללת תמיד)
            <select value={form.baseline} onChange={(e) => set("baseline", e.target.value)}>
              {STRATEGY_OPTIONS.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
            </select>
          </label>
        </fieldset>
        <fieldset>
          <legend>תרחיש משבר (אופציונלי)</legend>
          <div className="pl-grid">
            <label className="pl-check"><input type="checkbox" checked={form.crisisOn} onChange={(e) => set("crisisOn", e.target.checked)} />הפעל תרחיש משבר</label>
            <label>ירידה
              <select value={form.crisisDecline} onChange={(e) => set("crisisDecline", e.target.value)}>
                {CRISIS_DECLINES.map((d) => <option key={d} value={d}>{d}%</option>)}
              </select>
            </label>
            <label>שנת המשבר<input inputMode="numeric" value={form.crisisYear} onChange={(e) => set("crisisYear", e.target.value)} /></label>
            <label>חודש בתוך השנה
              <select value={form.crisisMonth} onChange={(e) => set("crisisMonth", e.target.value)}>
                <option value="">ללא (מסלול שנתי)</option>
                {Array.from({ length: 12 }, (_, i) => <option key={i + 1} value={String(i + 1)}>חודש {i + 1}</option>)}
              </select>
            </label>
            <label>התאוששות
              <select value={form.crisisRecovery} onChange={(e) => set("crisisRecovery", e.target.value as LabForm["crisisRecovery"])}>
                <option value="fast">מהירה (שנה)</option><option value="prolonged">ממושכת (3 שנים)</option>
              </select>
            </label>
          </div>
        </fieldset>
        <fieldset>
          <legend>השוואת תרחישים (אופציונלי)</legend>
          <label className="pl-check"><input type="checkbox" checked={form.compareOn} onChange={(e) => set("compareOn", e.target.checked)} />השווה לסט הנחות שני</label>
          {form.compareOn && (
            <>
              <p className="fcc-goal__note">סט ב׳: מלאו רק את ההנחות שרוצים לשנות; שדה ריק = כמו בסט א׳. האופק והאסטרטגיה זהים.</p>
              <div className="pl-grid">
                <label>הפקדה חודשית (₪)<input inputMode="decimal" value={form.cmpMonthly} onChange={(e) => set("cmpMonthly", e.target.value)} /></label>
                <label>תשואה שנתית ברוטו (%)<input inputMode="decimal" value={form.cmpReturnPct} onChange={(e) => set("cmpReturnPct", e.target.value)} /></label>
                <label>דמי ניהול שנתיים (%)<input inputMode="decimal" value={form.cmpFeePct} onChange={(e) => set("cmpFeePct", e.target.value)} /></label>
                <label>אינפלציה שנתית (%)<input inputMode="decimal" value={form.cmpInflationPct} onChange={(e) => set("cmpInflationPct", e.target.value)} /></label>
              </div>
            </>
          )}
        </fieldset>
        <button type="submit" className="boss-button boss-button--primary boss-bubble--action" disabled={state.status === "loading"}>
          {state.status === "loading" ? "מחשב…" : "חשב"}
        </button>
        {formError && <p className="fcc-quick__error" role="alert">⚠️ {formError}</p>}
      </form>

      {state.status === "loading" && <ScreenState state="loading" title="מחשב" message="המנוע מריץ את הסימולציה…" />}
      {state.status === "error" && (
        <ScreenState state="error" title={state.code === 404 ? "המסך עדיין לא פעיל" : state.code === 429 ? "יותר מדי חישובים" : "החישוב נכשל"}
                     message={state.code === 404 ? "מעבדת העתיד אינה זמינה בחשבון הזה." : state.code === 429 ? "אפשר לנסות שוב בעוד דקה." : state.message} />
      )}
      {state.status === "ok" && <LabResult view={state.view} />}
      <PaceTrackerPanel assumptions={paceAssumptions(form)} />
    </div>
  );
}

function LabResult({ view }: { view: PortfolioLabView }) {
  const g = view.charts.growth;
  const sc = view.charts.sensitivity.monthly_contribution, sd = view.charts.sensitivity.duration;
  const pair = (rows: { final_nominal: number; final_real: number }[]) => [
    { name: "נומינלי", values: rows.map((r) => r.final_nominal), color: CHART_COLORS[0] },
    { name: "ריאלי", values: rows.map((r) => r.final_real), color: CHART_COLORS[2] },
  ];
  return (
    <>
      <section className="fcc-section" aria-labelledby="pl-kpis">
        <h2 id="pl-kpis" className="fcc-section__heading">תוצאות מרכזיות {DEMO}</h2>
        <div className="fcc-kpis">{labKpiCards(view).map((c) => <KpiCard key={c.key} label={c.label} value={c.value} hint={c.hint} />)}</div>
      </section>
      <section className="fcc-section"><h2 className="fcc-section__heading">צבירת הון לאורך זמן {DEMO}</h2>
        <Surface padding="compact"><LineChart model={lineChartModel(growthLines(view))} xLabel="שנים" title="צבירת הון לאורך זמן" />
          {g.crisis.applied && (
            <p className="fcc-goal__note">תרחיש משבר: הפרש בשווי הסופי {ils(g.crisis.delta_vs_no_crisis)}. {g.crisis.note}
              {g.crisis.recovery_truncated_by_horizon ? " ההתאוששות נחתכה בגלל אופק ההשקעה." : ""}</p>
          )}</Surface></section>
      {g.crisis.applied && g.crisis.intra_year && (
        <section className="fcc-section"><h2 className="fcc-section__heading">משבר תוך-שנתי: העיתוי מול ההפקדות {DEMO}</h2>
          <p className="fcc-goal__note">{g.crisis.intra_year.deposit_order_note} {g.crisis.intra_year.note}
            {g.crisis.intra_year.recovery_truncated_by_horizon ? " ההתאוששות נחתכה בגלל אופק ההשקעה." : ""}</p>
          <Surface padding="compact"><LineChart model={lineChartModel(intraYearLines(view))} xLabel="שנים" title="מסלול חודשי סביב המשבר" /></Surface>
          <Surface padding="compact"><div className="pl-scroll"><table className="pl-table">
            <thead><tr>{TIMING_TABLE_HEAD.map((h) => <th key={h}>{h}</th>)}</tr></thead>
            <tbody>{timingRows(view).map((r) => <tr key={r.key}>{r.cells.map((c, i) => <td key={i} className={i ? "pl-num" : ""}>{c}</td>)}</tr>)}</tbody>
          </table></div></Surface></section>
      )}
      {view.charts.scenario_comparison?.applied && (
        <section className="fcc-section"><h2 className="fcc-section__heading">השוואת תרחישים {DEMO}</h2>
          <p className="fcc-goal__note">{view.charts.scenario_comparison.note}</p>
          <Surface padding="compact"><ul className="pl-list">{(view.charts.scenario_comparison.changed_fields ?? []).map((f) => <li key={f.field}>{f.label}: סט א׳ {String(f.a)} · סט ב׳ {String(f.b)}</li>)}</ul></Surface>
          <Surface padding="compact"><LineChart model={lineChartModel(scenarioLines(view))} xLabel="שנים" title="השוואת תרחישים" /></Surface>
          <Surface padding="compact"><div className="pl-scroll"><table className="pl-table">
            <thead><tr>{SCENARIO_TABLE_HEAD.map((h) => <th key={h}>{h}</th>)}</tr></thead>
            <tbody>{scenarioRows(view).map((r) => <tr key={r.key}>{r.cells.map((c, i) => <td key={i} className={i ? "pl-num" : ""}>{c}</td>)}</tr>)}</tbody>
          </table></div></Surface></section>
      )}
      <section className="fcc-section"><h2 className="fcc-section__heading">השוואת אסטרטגיות {DEMO}</h2>
        <Surface padding="compact"><LineChart model={lineChartModel(comparisonLines(view))} xLabel="שנים" title="השוואת אסטרטגיות" /></Surface></section>
      {g.crisis.applied && crisisTableRows(view).length > 1 && (
        <section className="fcc-section"><h2 className="fcc-section__heading">תרחיש המשבר על כל האסטרטגיות {DEMO}</h2>
          <p className="fcc-goal__note">אותו משבר מוחל על כל אסטרטגיה בהשוואה. תוצאת מודל לפי ההנחות — לא תחזית.</p>
          <Surface padding="compact"><div className="pl-scroll"><table className="pl-table">
            <thead><tr>{CRISIS_TABLE_HEAD.map((h) => <th key={h}>{h}</th>)}</tr></thead>
            <tbody>{crisisTableRows(view).map((r) => <tr key={r.key}>{r.cells.map((c, i) => <td key={i} className={i ? "pl-num" : ""}>{c}</td>)}</tr>)}</tbody>
          </table></div></Surface></section>
      )}
      <section className="fcc-section"><h2 className="fcc-section__heading">חלוקת התוצאה {DEMO}</h2>
        <Surface padding="compact"><StackBar parts={breakdownParts(view)} formatValue={ils} formatShare={(s) => pct(s, 1)} /></Surface></section>
      <section className="fcc-section"><h2 className="fcc-section__heading">רגישות להפקדה חודשית {DEMO}</h2>
        <Surface padding="compact"><BarChart title="רגישות להפקדה חודשית" model={barChartModel(sc.map((r) => String(Math.round(r.monthly_contribution))), pair(sc))} /></Surface></section>
      <section className="fcc-section"><h2 className="fcc-section__heading">רגישות לאורך זמן {DEMO}</h2>
        <Surface padding="compact"><BarChart title="רגישות לאורך זמן" model={barChartModel(sd.map((r) => `${r.years} ש׳`), pair(sd))} /></Surface></section>
      <section className="fcc-section"><h2 className="fcc-section__heading">טבלת השוואה {DEMO}</h2>
        <p className="fcc-goal__note">תשואות רכיבי האסטרטגיות (פרט לקרן העולמית) הן הנחות להמחשה — לא דירוג של קרנות אמיתיות.</p>
        <Surface padding="compact"><div className="pl-scroll"><table className="pl-table">
          <thead><tr>{LAB_TABLE_HEAD.map((h) => <th key={h}>{h}</th>)}</tr></thead>
          <tbody>{labTableRows(view).map((r) => <tr key={r.key}>{r.cells.map((c, i) => <td key={i} className={i ? "pl-num" : ""}>{c}</td>)}</tr>)}</tbody>
        </table></div></Surface></section>
      <section className="fcc-section"><h2 className="fcc-section__heading">תובנות אוטומטיות {DEMO}</h2>
        <Surface padding="compact"><ul className="pl-list">{view.insights.map((i) => <li key={i.topic}>{i.text}</li>)}</ul></Surface></section>
      <section className="fcc-section"><h2 className="fcc-section__heading">הנחות ואזהרות</h2>
        <Surface padding="compact">
          <ul className="pl-list">{view.assumptions.map((a) => <li key={a.id}>{a.text}{a.assumption_based && <StatusBadge tone="warning">assumption-based</StatusBadge>}</li>)}</ul>
          <ul className="pl-list pl-list--small" dir="auto">{view.warnings.map((w) => <li key={w}>{w}</li>)}</ul>
          <p className="fcc-goal__note">מנוע portfolio_lab v{view.engine_version} · סוג תוצאה: {view.result_type} · digest {view.replay_digest.slice(0, 12)}</p>
        </Surface></section>
    </>
  );
}
