import { useState } from "react";
import type { FccLoans, FccScenarios, PayoffStrategy } from "../types";
import { orderedRows, parseBudget, payoffCardModel, presetBudget, scenarioDetail, scenarioRows, STRATEGY_TABS } from "../lib/fccPayoff";
import { UNKNOWN } from "../lib/fccLoans";
import { Surface } from "./ui/Surface";

/** Render-only: one budget's outcome for every strategy + the selected strategy's detail. */
export function ScenarioView({ scenarios, strategy }: { scenarios: FccScenarios; strategy: PayoffStrategy }) {
  const detail = scenarioDetail(scenarios.strategies[strategy]);
  const label = STRATEGY_TABS.find((t) => t.key === strategy)?.label;
  return (
    <div className="fcc-pay__scenario">
      <table className="fcc-compare__table fcc-pay__table">
        <thead><tr><th>אסטרטגיה</th><th>נסגרות</th><th>תזרים/חודש</th><th>נשאר</th></tr></thead>
        <tbody>
          {scenarioRows(scenarios).map((r) => (
            <tr key={r.key} className={r.key === strategy ? "fcc-pay__row--on" : undefined}>
              <th scope="row">{r.label}</th><td>{r.closed}</td><td className={r.released === UNKNOWN ? "fcc-unknown" : undefined}>{r.released}</td><td>{r.left}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <h4 className="fcc-pay__subhead">פירוט לפי אסטרטגיה: {label}</h4>
      <dl className="fcc-loans-goal__grid">
        {detail.lines.map((l) => <div key={l.label}><dt>{l.label}</dt><dd className={l.value === UNKNOWN ? "fcc-unknown" : undefined}>{l.value}</dd></div>)}
      </dl>
      {scenarios.strategies[strategy].closed.length > 0 && (
        <p className="fcc-loan__meta">נסגרות: {scenarios.strategies[strategy].closed.map((c) => c.name ?? UNKNOWN).join(", ")}</p>
      )}
      {detail.notes.map((n) => <p key={n} className="fcc-goal__note">{n}</p>)}
    </div>
  );
}

export type LoadScenario = (budget: number) => Promise<FccScenarios>;

export function PayoffEngine({ loans, loadScenario }: { loans: FccLoans; loadScenario?: LoadScenario }) {
  const [strategy, setStrategy] = useState<PayoffStrategy>("balanced");
  const [text, setText] = useState("");
  const [scenarios, setScenarios] = useState<FccScenarios | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const rows = orderedRows(loans, strategy);
  const preset = presetBudget(loans);
  if (!loans.payoff || rows.length === 0) return null;
  const basis = STRATEGY_TABS.find((t) => t.key === strategy)?.basis;

  const run = async (amount: number | null) => {
    if (amount == null) { setError("הזן סכום חיובי"); return; }
    setBusy(true); setError(null);
    try {
      if (!loadScenario) throw new Error("no loader");
      setScenarios(await loadScenario(amount));
    }
    catch { setError("הסימולציה נכשלה, נסה שוב"); }
    finally { setBusy(false); }
  };

  return (
    <section className="fcc-pay" aria-labelledby="fcc-pay-heading">
      <h3 id="fcc-pay-heading" className="fcc-section__heading">מנוע פרעון מוקדם</h3>
      <p className="fcc-goal__note">חישוב והשוואה בלבד — אין המלצה אוטומטית ואין ביצוע. יעילות פינוי תזרים היא תזרים שמתפנה לכל שקל סילוק, לא תשואה.</p>
      <div className="fcc-chips" role="tablist" aria-label="אסטרטגיית דירוג">
        {STRATEGY_TABS.map((t) => (
          <button key={t.key} type="button" role="tab" aria-selected={strategy === t.key}
                  className={`fcc-chip ${strategy === t.key ? "fcc-chip--on" : ""}`} onClick={() => setStrategy(t.key)}>{t.label}</button>
        ))}
      </div>
      <p className="fcc-loan__meta">מסודר לפי: {basis}</p>
      <div className="fcc-list fcc-list--tight">
        {rows.map((r, i) => {
          const m = payoffCardModel(r, strategy, i + 1);
          return (
            <article key={r.id} className="fcc-loan fcc-pay__card">
              <header className="fcc-loan__head">
                <h4 className="fcc-loan__title"><span className="fcc-pay__rank">{m.rank}</span>{m.title}</h4>
                {m.partial && <span className="fcc-tag fcc-tag--muted">נתונים חלקיים</span>}
              </header>
              <dl className="fcc-pay__figures">
                {m.figures.map((f) => <div key={f.label}><dt>{f.label}</dt><dd className={f.value === UNKNOWN ? "fcc-unknown" : undefined}>{f.value}</dd></div>)}
              </dl>
              <p className="fcc-loan__meta fcc-pay__score">{m.scoreLabel}{m.missingLabel ? ` · ${m.missingLabel}` : ""}</p>
              <p className="fcc-pay__why"><strong>למה כאן: </strong>{m.why}</p>
            </article>
          );
        })}
      </div>

      <Surface variant="subtle" padding="compact" className="fcc-pay__budget">
        <h4 className="fcc-pay__subhead">סימולציה לפי תקציב</h4>
        <p className="fcc-goal__note">יש לי סכום לפרעון מוקדם — אילו הלוואות נסגרות במלואן. סימולציה בלבד, בלי פרעון חלקי.</p>
        <div className="fcc-pay__input">
          <input type="text" inputMode="numeric" dir="ltr" placeholder="₪ סכום לפרעון" aria-label="סכום לפרעון מוקדם" value={text}
                 onChange={(e) => setText(e.target.value)} />
          <button type="button" className="fcc-chip fcc-chip--on" disabled={busy} onClick={() => void run(parseBudget(text))}>{busy ? "מחשב…" : "חשב"}</button>
        </div>
        {preset && (
          <button type="button" className="fcc-chip" disabled={busy} onClick={() => { setText(String(preset.amount)); void run(preset.amount); }}>{preset.label}</button>
        )}
        {preset && <p className="fcc-loan__meta">זו סימולציה מול יעד ה־Financial Goal, לא סכום שקיים כרגע במזומן.</p>}
        {error && <p className="fcc-quick__error" role="alert">⚠️ {error}</p>}
        {scenarios && <ScenarioView scenarios={scenarios} strategy={strategy} />}
      </Surface>
    </section>
  );
}
