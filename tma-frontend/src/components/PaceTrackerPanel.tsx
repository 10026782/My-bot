import { useRef, useState } from "react";
import { postFccPace } from "../api";
import type { PaceView } from "../types";
import {
  MISSING_LABEL, PACE_ACCOUNT_HEAD, PACE_CORRECTION_HEAD, PACE_CORRECTION_REASONS, PACE_SUMMARY_HEAD, ils, lineChartModel, paceAccountRows,
  paceCorrectionRows, paceForecastLines, paceSummaryRows,
} from "../lib/familyWealth";
import { LineChart } from "./PortfolioLabCharts";
import { ScreenState } from "./ui/ScreenState";
import { StatusBadge } from "./ui/StatusBadge";
import { Surface } from "./ui/Surface";

type State = { status: "idle" } | { status: "loading" } | { status: "ok"; view: PaceView } | { status: "error"; message: string; code?: number };

/** C4: "קצב צבירה בפועל מול התוכנית". On demand (it reads the owner's accounts): reported balances and deposits vs the plan, an updated
 *  assumption-based extrapolation and a neutral course-correction illustration. Every number is the server's; self-reported; missing = "חסר". */
export function PaceTrackerPanel({ assumptions }: { assumptions: { annual_return_pct: number; annual_fee_pct: number; inflation_pct: number } | null }) {
  const [state, setState] = useState<State>({ status: "idle" });
  const [years, setYears] = useState("10");
  const [formError, setFormError] = useState<string | null>(null);
  const latest = useRef(0);

  const load = () => {
    const n = Number(years);
    if (years.trim() === "" || !Number.isInteger(n)) { setFormError("אופק: יש להזין מספר שלם"); return; }
    setFormError(null);
    const id = ++latest.current;
    setState({ status: "loading" });
    postFccPace({ years: n, ...(assumptions ?? {}) })
      .then((view) => { if (id === latest.current) setState({ status: "ok", view }); })
      .catch((e: Error & { status?: number }) => { if (id === latest.current) setState({ status: "error", message: e.message, code: e.status }); });
  };

  return (
    <section className="fcc-section" aria-labelledby="pace-h">
      <h2 id="pace-h" className="fcc-section__heading">קצב צבירה בפועל מול התוכנית <StatusBadge tone="warning">דיווח עצמי</StatusBadge></h2>
      <Surface variant="subtle" padding="compact" role="note">
        היתרות וההפקדות הן דיווח עצמי שלך, לא מאומתות מול בנק. ההשוואה היא לתוכנית ההפקדה שהוזנה בחשבונות; התחזית המעודכנת היא אקסטרפולציה של הקצב בפועל לפי ההנחות
        של המעבדה — לא תחזית ולא המלצה. שום דבר כאן לא נשמר.
      </Surface>
      <div className="pl-grid">
        <label>אופק התחזית (שנים, 10–50)<input inputMode="numeric" value={years} onChange={(e) => setYears(e.target.value)} /></label>
      </div>
      <button type="button" className="boss-button boss-button--primary boss-bubble--action" disabled={state.status === "loading"} onClick={load}>
        {state.status === "loading" ? "טוען…" : "הצג קצב בפועל"}
      </button>
      {formError && <p className="fcc-quick__error" role="alert">⚠️ {formError}</p>}
      {state.status === "loading" && <ScreenState state="loading" title="טוען" message="קורא את היתרות וההפקדות שדווחו…" />}
      {state.status === "error" && (
        <ScreenState state="error" title={state.code === 404 ? "המסך עדיין לא פעיל" : state.code === 429 ? "יותר מדי בקשות" : "הטעינה נכשלה"}
                     message={state.code === 404 ? "מעקב הקצב אינו זמין בחשבון הזה." : state.code === 429 ? "אפשר לנסות שוב בעוד דקה." : state.message} />
      )}
      {state.status === "ok" && <PaceResult view={state.view} />}
    </section>
  );
}

function PaceResult({ view }: { view: PaceView }) {
  const c = view.consolidated, f = view.forecast, cc = view.course_correction;
  const summary = paceSummaryRows(view), lines = paceForecastLines(view), corrections = paceCorrectionRows(view);
  return (
    <>
      <p className="fcc-goal__note">
        נכון ל-{view.as_of} · {c.accounts_with_plan} חשבונות מושווים לתוכנית
        {c.accounts_without_plan ? ` · ${c.accounts_without_plan} ללא הפקדה מתוכננת (${MISSING_LABEL})` : ""}
        {c.accounts_single_snapshot ? ` · ${c.accounts_single_snapshot} עם יתרה אחת בלבד` : ""}
        {c.accounts_without_snapshot ? ` · ${c.accounts_without_snapshot} ללא יתרה מדווחת` : ""}
        {c.window ? ` · תקופת ההשוואה ${c.window.from} עד ${c.window.to}` : ""}
      </p>
      {summary.length > 0 ? (
        <Surface padding="compact"><div className="pl-scroll"><table className="pl-table">
          <thead><tr>{PACE_SUMMARY_HEAD.map((h) => <th key={h}>{h}</th>)}</tr></thead>
          <tbody>{summary.map((r) => <tr key={r.key}>{r.cells.map((cell, i) => <td key={i} className={i ? "pl-num" : ""}>{cell}</td>)}</tr>)}</tbody>
        </table></div></Surface>
      ) : <p className="fcc-goal__note">אין עדיין חשבון עם שתי יתרות מדווחות ותוכנית הפקדה — אין מה להשוות ({MISSING_LABEL}).</p>}
      <Surface padding="compact"><div className="pl-scroll"><table className="pl-table">
        <thead><tr>{PACE_ACCOUNT_HEAD.map((h) => <th key={h}>{h}</th>)}</tr></thead>
        <tbody>{paceAccountRows(view).map((r) => (
          <tr key={r.key}>{r.cells.map((cell, i) => <td key={i} className={i === 2 || i === 3 || i === 4 ? "pl-num" : ""}>{cell}{i === 0 && r.missing ? <><br /><small>חסר: {r.missing}</small></> : null}</td>)}</tr>
        ))}</tbody>
      </table></div></Surface>

      {f.applied && lines.length > 0 && (
        <>
          <h3 className="fcc-section__heading">תחזית מעודכנת <StatusBadge tone="warning">אקסטרפולציה — לא תחזית</StatusBadge></h3>
          <p className="fcc-goal__note">
            {f.label}. התחלה: {ils(f.starting_value)} (סכום היתרות האחרונות); תשואה {f.assumptions?.annual_return_pct}% · דמי ניהול {f.assumptions?.annual_fee_pct}% ·
            אינפלציה {f.assumptions?.inflation_pct}% · אופק {f.horizon_years} שנים. {f.assumptions?.note}
          </p>
          <Surface padding="compact"><LineChart model={lineChartModel(lines)} xLabel="שנים" title="קצב מתוכנן מול קצב בפועל" /></Surface>
          <ul className="pl-list">
            {f.lines?.planned_pace && <li>קצב מתוכנן: {ils(f.lines.planned_pace.monthly_deposit)} לחודש → {ils(f.lines.planned_pace.final_nominal)}</li>}
            {f.lines?.actual_pace && <li>קצב בפועל (תנועות מתועדות נטו לחודש): {ils(f.lines.actual_pace.monthly_deposit)} → {ils(f.lines.actual_pace.final_nominal)}</li>}
            {f.lines?.goal_history_pace && <li>ממוצע הפקדות חודשי ביעד החיסכון: {ils(f.lines.goal_history_pace.monthly_deposit)} → {ils(f.lines.goal_history_pace.final_nominal)}</li>}
            {!f.lines?.actual_pace && <li>קו הקצב בפועל: {PACE_CORRECTION_REASONS[f.actual_pace_unavailable_reason ?? "no_actual_pace"] ?? MISSING_LABEL}</li>}
            {!f.lines?.planned_pace && <li>קו הקצב המתוכנן: {MISSING_LABEL} (אין הפקדה חודשית מתוכננת בחשבונות)</li>}
          </ul>
        </>
      )}
      {f.applied === false && <p className="fcc-goal__note">אין תחזית: {PACE_CORRECTION_REASONS[f.reason ?? "no_forecast"] ?? MISSING_LABEL}</p>}

      <h3 className="fcc-section__heading">תיקון מסלול — המחשה ניטרלית</h3>
      {cc.applied && corrections.length > 0 ? (
        <>
          <p className="fcc-goal__note">
            {cc.note}
            {cc.monthly_change_to_match_planned_end != null && ` שינוי בהפקדה החודשית הכוללת שהיה משווה את סוף האופק לקצב המתוכנן: ${cc.monthly_change_to_match_planned_end > 0 ? "+" : ""}${ils(cc.monthly_change_to_match_planned_end)}.`}
          </p>
          <Surface padding="compact"><div className="pl-scroll"><table className="pl-table">
            <thead><tr>{PACE_CORRECTION_HEAD.map((h) => <th key={h}>{h}</th>)}</tr></thead>
            <tbody>{corrections.map((r) => <tr key={r.key}>{r.cells.map((cell, i) => <td key={i} className="pl-num">{cell}</td>)}</tr>)}</tbody>
          </table></div></Surface>
        </>
      ) : <p className="fcc-goal__note">{PACE_CORRECTION_REASONS[cc.reason ?? "no_forecast"] ?? MISSING_LABEL}</p>}
      <Surface variant="subtle" padding="compact"><ul className="pl-list pl-list--small" dir="auto">{view.assumptions.map((a) => <li key={a}>{a}</li>)}</ul></Surface>
    </>
  );
}
