import { useEffect, useRef, useState } from "react";
import { postLiquidityStress } from "../api";
import type { StressView } from "../types";
import { ils, lineChartModel } from "../lib/familyWealth";
import {
  DEFAULT_STRESS_FORM, STRESS_NOTE, STRESS_SEEDED_NOTE, STRESS_STALE_NOTE, applySeed, isStale, stressKey, type StressSeed, STRESS_PROTECTED_NOTE, STRESS_TITLE, burnRows, netWorthLines, stressHead, stressParams, stressRows, type StressForm,
} from "../lib/liquidityStress";
import { LineChart } from "./PortfolioLabCharts";
import { ScreenState } from "./ui/ScreenState";
import { StatusBadge } from "./ui/StatusBadge";
import { Surface } from "./ui/Surface";

type State = { status: "idle" } | { status: "loading" } | { status: "ok"; view: StressView } | { status: "error"; message: string; code?: number };

/** E1d: "מבחן לחץ נזילות". On demand: cushions of 0/12/24 months of NET burn under a crisis, with an optional loan, LTV and collateral call.
 *  Every number is the server's; a collateral call, a forced sale and a cash shortfall are three separate events. Nothing is stored. */
export function LiquidityStressPanel({ seed }: { seed?: StressSeed | null } = {}) {
  const [form, setForm] = useState<StressForm>(DEFAULT_STRESS_FORM);
  const [seeded, setSeeded] = useState(false);
  const [ranKey, setRanKey] = useState<string | null>(null);   // the request the shown answer belongs to
  const root = useRef<HTMLElement | null>(null);
  const [state, setState] = useState<State>({ status: "idle" });
  const [formError, setFormError] = useState<string | null>(null);
  const latest = useRef(0);
  const set = <K extends keyof StressForm>(key: K, value: StressForm[K]) => setForm((f) => ({ ...f, [key]: value }));
  const field = (key: keyof StressForm, label: string, mode: "decimal" | "numeric" = "decimal") => (
    <label>{label}<input inputMode={mode} value={String(form[key])} onChange={(e) => set(key, e.target.value as never)} /></label>
  );

  // E1e: a loan typed in the funding planner pre-fills the loan fields (a new hand-off replaces the old one and clears a stale answer)
  useEffect(() => {
    if (!seed) return;
    setForm((f) => applySeed(f, seed));
    setSeeded(true);
    setState({ status: "idle" });
    setRanKey(null);
    setFormError(null);
    latest.current += 1;                              // an answer still in flight belongs to the previous inputs
    if (typeof root.current?.scrollIntoView === "function") root.current.scrollIntoView({ block: "start" });
  }, [seed?.id]);                                      // eslint-disable-line react-hooks/exhaustive-deps

  const run = () => {
    const parsed = stressParams(form);
    if (!parsed.ok) { setFormError(parsed.error); return; }
    setFormError(null);
    const id = ++latest.current;                     // a slower, older answer must never overwrite a newer one
    setState({ status: "loading" });
    const key = stressKey(form);
    postLiquidityStress(parsed.params)
      .then((view) => { if (id === latest.current) { setState({ status: "ok", view }); setRanKey(key); } })
      .catch((e: Error & { status?: number }) => { if (id === latest.current) setState({ status: "error", message: e.message, code: e.status }); });
  };

  return (
    <section className="fcc-section" aria-labelledby="stress-h" ref={root}>
      <h2 id="stress-h" className="fcc-section__heading">{STRESS_TITLE} <StatusBadge tone="warning">הנחות</StatusBadge></h2>
      <Surface variant="subtle" padding="compact" role="note">{STRESS_NOTE}</Surface>
      {seeded && <Surface variant="subtle" padding="compact" role="status">{STRESS_SEEDED_NOTE}</Surface>}
      <form className="pl-form" onSubmit={(e) => { e.preventDefault(); run(); }} aria-label="קלטי מבחן הלחץ">
        <div className="pl-grid">
          {field("fundValue", "שווי הקרן (₪)")}
          <label>שלב
            <select value={form.phase} onChange={(e) => set("phase", e.target.value as StressForm["phase"])}>
              <option value="withdrawal">משיכות (תמיכה פעילה)</option><option value="accumulation">צבירה (הפקדות בלבד)</option>
            </select>
          </label>
          {field("deposit", "הפקדה חודשית (₪)")}
          {field("support", "תמיכה משפחתית חודשית (₪)")}
          {field("otherExpenses", "הוצאות נוספות בחודש (₪)")}
          {field("otherIncome", "הכנסות נוספות בחודש (₪)")}
          {field("returnPct", "תשואה שנתית (%)")}
          {field("feePct", "דמי ניהול שנתיים (%)")}
          {field("inflationPct", "אינפלציה שנתית (%)")}
          {field("horizonMonths", "אופק (חודשים, עד 360)", "numeric")}
        </div>
        <fieldset>
          <legend>משבר</legend>
          <label className="pl-check"><input type="checkbox" checked={form.crisisOn} onChange={(e) => set("crisisOn", e.target.checked)} />הפעל משבר</label>
          {form.crisisOn && <div className="pl-grid">
            {field("crisisDecline", "ירידה (%)")}{field("crisisStart", "חודש תחילת המשבר", "numeric")}{field("crisisRecoveryYears", "שנות התאוששות (1–10)", "numeric")}
          </div>}
        </fieldset>
        <fieldset>
          <legend>קופות מזומן והון ילדים</legend>
          <div className="pl-grid">
            {field("pledged", "מזומן משועבד (נספר כבטוחה, לא מממן תזרים) (₪)")}
            {field("earmarked", "מזומן להתחייבויות משפחתיות (לא מממן דבר) (₪)")}
            {field("protectedAmount", "הון ילדים (מוצג בלבד) (₪)")}
          </div>
          <p className="fcc-goal__note">{STRESS_PROTECTED_NOTE} הכרית (0 / 12 / 24 חודשי תזרים נטו) נלקחת מהמזומן החופשי של הקרן ואינה נספרת כבטוחה.</p>
        </fieldset>
        <fieldset>
          <legend>הלוואה (אופציונלי)</legend>
          <label className="pl-check"><input type="checkbox" checked={form.loanOn} onChange={(e) => set("loanOn", e.target.checked)} />כלול הלוואה כנגד הקרן</label>
          {form.loanOn && (
            <>
              <div className="pl-grid">
                {field("loanAmount", "סכום ההלוואה (₪)")}{field("loanRate", "ריבית שנתית (%)")}
                {field("loanMaxLtv", "סף LTV שהמלווה קבע (%) — חובה, אין ברירת מחדל")}
                <label className="pl-check"><input type="checkbox" checked={form.loanInterestOnly} onChange={(e) => set("loanInterestOnly", e.target.checked)} />ריבית בלבד (הקרן אינה נפרעת באופק)</label>
                {!form.loanInterestOnly && field("loanTerm", "תקופת ההלוואה (חודשים)", "numeric")}
                <label className="pl-check"><input type="checkbox" checked={form.loanVerified} onChange={(e) => set("loanVerified", e.target.checked)} />התנאים אומתו מול הבנק</label>
                <label>הבטוחה
                  <select value={form.collateral} onChange={(e) => set("collateral", e.target.value as StressForm["collateral"])}>
                    <option value="risky_and_pledged">נכס סיכון + משועבד</option><option value="risky_only">נכס סיכון בלבד</option>
                  </select>
                </label>
                <label>תיקון דרישת בטוחות
                  <select value={form.cureFirst} onChange={(e) => set("cureFirst", e.target.value as StressForm["cureFirst"])}>
                    <option value="cushion">קודם מזומן, אחר כך מכירה</option><option value="risky_sale">קודם מכירה, אחר כך מזומן</option>
                  </select>
                </label>
                <label>תמורת ההלוואה
                  <select value={form.proceeds} onChange={(e) => set("proceeds", e.target.value as StressForm["proceeds"])}>
                    <option value="none">הוצאה ללא תשואה</option><option value="asset_income">נכס מניב</option>
                  </select>
                </label>
                {form.proceeds === "asset_income" && field("proceedsIncome", "הכנסה חודשית מהנכס (₪)")}
                {form.proceeds === "asset_income" && field("proceedsValue", "שווי הנכס (₪, קבוע)")}
              </div>
            </>
          )}
        </fieldset>
        <button type="submit" className="boss-button boss-button--primary boss-bubble--action" disabled={state.status === "loading"}>
          {state.status === "loading" ? "מחשב…" : "הרץ מבחן לחץ"}
        </button>
        {formError && <p className="fcc-quick__error" role="alert">⚠️ {formError}</p>}
      </form>
      {state.status === "loading" && <ScreenState state="loading" title="מחשב" message="מריץ את מבחן הלחץ…" />}
      {state.status === "error" && (
        <ScreenState state="error" title={state.code === 404 ? "המסך עדיין לא פעיל" : state.code === 429 ? "יותר מדי חישובים" : "החישוב נכשל"}
                     message={state.code === 404 ? "מבחן הלחץ אינו זמין בחשבון הזה." : state.code === 429 ? "אפשר לנסות שוב בעוד דקה." : state.message} />
      )}
      {state.status === "ok" && isStale(form, ranKey) && <Surface variant="subtle" padding="compact" role="status">⚠️ {STRESS_STALE_NOTE}</Surface>}
      {state.status === "ok" && <StressResult view={state.view} />}
    </section>
  );
}

export function StressResult({ view }: { view: StressView }) {
  return (
    <>
      <Surface padding="compact">
        <h3 className="fcc-section__heading">תזרים נטו נדרש בחודש: {ils(view.net_burn.net_burn_per_month)}</h3>
        <ul className="pl-list">{burnRows(view).map((r) => <li key={r.key}>{r.label}: {r.value}</li>)}</ul>
      </Surface>
      <Surface padding="compact"><div className="pl-scroll"><table className="pl-table pl-table--stress">
        <thead><tr>{stressHead(view).map((h) => <th key={h}>{h}</th>)}</tr></thead>
        <tbody>{stressRows(view).map((r) => <tr key={r.key}><th scope="row">{r.label}</th>{r.cells.map((c, i) => <td key={i} className="pl-num">{c}</td>)}</tr>)}</tbody>
      </table></div></Surface>
      <Surface padding="compact"><LineChart model={lineChartModel(netWorthLines(view))} xLabel="חודשים" title="שווי נקי לפי גודל הכרית" /></Surface>
      <Surface padding="compact">
        <p className="fcc-goal__note">{view.protected_capital.note}</p>
        <ul className="pl-list pl-list--small" dir="auto">{view.notes.map((n) => <li key={n}>{n}</li>)}</ul>
        <p className="fcc-goal__note">מנוע portfolio_lab v{view.engine_version} · סוג תוצאה: {view.result_type} · digest {view.replay_digest.slice(0, 12)}</p>
      </Surface>
    </>
  );
}
