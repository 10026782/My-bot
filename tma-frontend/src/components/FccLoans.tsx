import { useState } from "react";
import type { FccLoans } from "../types";
import {
  CLOSE_BUTTON, FILTERS, RANK_MODES, STATUS_UNKNOWN, UNKNOWN, compareRows, filterLoans, loanCardModel, loanGoalModel, loanHeaderCards, sortLoans, togglePick, canClose,
  type LoanFilter, type RankMode,
} from "../lib/fccLoans";
import { KpiCard } from "./FccKpiCard";
import { PayoffEngine, type LoadScenario } from "./FccPayoff";
import { ScreenState } from "./ui/ScreenState";
import { Surface } from "./ui/Surface";

/** The close flow runs in the shared contextual composer (intent ``loan.close``): a card button only names the loan. */
export interface LoanCloseEntry {
  onClose: (loanId: string) => void;
  disabled: boolean;          // a draft is already open in the shared writer (one slot per person)
}

export function LoansSection({ loans, loadScenario, closeEntry }: { loans: FccLoans; loadScenario?: LoadScenario; closeEntry?: LoanCloseEntry }) {
  const [filter, setFilter] = useState<LoanFilter>("all");
  const [mode, setMode] = useState<RankMode>("high_interest");
  const [picked, setPicked] = useState<string[]>([]);
  const visible = sortLoans(filterLoans(loans.items, filter), loans, mode);
  const goal = loanGoalModel(loans);
  const byId = (id: string) => loans.items.find((l) => l.id === id);
  const a = picked[0] ? byId(picked[0]) : undefined;
  const b = picked[1] ? byId(picked[1]) : undefined;

  return (
    <section className="fcc-section" aria-labelledby="fcc-loans-heading">
      <h2 id="fcc-loans-heading" className="fcc-section__heading">הלוואות וחוב</h2>
      {loans.summary.total_active_loans === 0 ? (
        <ScreenState state="empty" title="אין הלוואות פעילות" message="הלוואות נרשמות בטבלת Loans." />
      ) : (
        <div className="fcc-stack fcc-stack--tight">
          <div className="fcc-kpis">
            {loanHeaderCards(loans).map((c) => <KpiCard key={c.key} label={c.label} value={c.value} hint={c.hint} />)}
          </div>
          {loans.summary.unknown_status_count > 0 && (
            <p className="fcc-goal__note">{loans.summary.unknown_status_count} הלוואות עם {STATUS_UNKNOWN} (Active Loan לא מסומן) — כלולות בסיכומים.</p>
          )}
          {goal && (
            <Surface variant="subtle" padding="compact" className="fcc-loans-goal">
              <div className="fcc-loans-goal__top">
                <h3 className="fcc-loans-goal__title">יעד סגירת חוב</h3>
                <span className="fcc-loans-goal__pct">{goal.pctLabel}</span>
              </div>
              {goal.pct != null && (
                <div className="fcc-goal__bar" role="progressbar" aria-label="התקדמות סגירת חוב" aria-valuenow={goal.pct} aria-valuemin={0} aria-valuemax={100}>
                  <span style={{ inlineSize: `${goal.pct}%` }} />
                </div>
              )}
              <dl className="fcc-loans-goal__grid">
                {goal.lines.map((m) => <div key={m.label}><dt>{m.label}</dt><dd className={m.value === UNKNOWN ? "fcc-unknown" : undefined}>{m.value}</dd></div>)}
              </dl>
            </Surface>
          )}
          <div className="fcc-chips" role="tablist" aria-label="סוג הלוואה">
            {FILTERS.map((f) => (
              <button key={f.key} type="button" role="tab" aria-selected={filter === f.key}
                      className={`fcc-chip ${filter === f.key ? "fcc-chip--on" : ""}`}
                      onClick={() => setFilter(f.key)}>{f.label}</button>
            ))}
          </div>
          <div className="fcc-chips" role="group" aria-label="סדר תצוגה">
            {RANK_MODES.map((m) => (
              <button key={m.key} type="button" aria-pressed={mode === m.key}
                      className={`fcc-chip ${mode === m.key ? "fcc-chip--on" : ""}`}
                      onClick={() => setMode(m.key)}>{m.label}</button>
            ))}
          </div>
          {visible.length === 0 ? (
            <ScreenState state="empty" title="אין הלוואות בסוג הזה" />
          ) : (
            <div className="fcc-list fcc-list--tight">
              {visible.map((l) => {
                const m = loanCardModel(l);
                const on = picked.includes(l.id);
                return (
                  <article key={l.id} className="fcc-loan">
                    <header className="fcc-loan__head">
                      <div className="fcc-loan__titlebox">
                        <h3 className="fcc-loan__title">{m.title}{m.lender && <span className="fcc-loan__lender"> · {m.lender}</span>}</h3>
                        <div className="fcc-loan__tags">
                          {m.tags.map((t) => <span key={t.text} className={`fcc-tag fcc-tag--${t.tone}`}>{t.text}</span>)}
                        </div>
                      </div>
                      <label className={`fcc-loan__pick ${on ? "fcc-loan__pick--on" : ""}`}>
                        <input type="checkbox" checked={on} onChange={() => setPicked((p) => togglePick(p, l.id))} />
                        <span>השוואה</span>
                      </label>
                    </header>
                    {m.assetLine && <p className="fcc-loan__asset">{m.assetLine}</p>}
                    <dl className="fcc-loan__key">
                      {m.keyRows.map((r, i) => (
                        <div key={r.label} className={i === 0 ? "fcc-loan__key-main" : undefined}><dt>{r.label}</dt><dd className={r.value === UNKNOWN ? "fcc-unknown" : undefined}>{r.value}</dd></div>
                      ))}
                    </dl>
                    <p className="fcc-loan__meta">{m.metaRows.map((r) => `${r.label}: ${r.value}`).join(" · ")}</p>
                    <p className={`fcc-loan__freed ${m.freedKnown ? "" : "fcc-loan__freed--unknown"}`}>{m.freedLine}</p>
                    {closeEntry && canClose(l) && (
                      <button type="button" className="boss-button boss-button--quiet boss-bubble--action fcc-loan__closebtn"
                              disabled={closeEntry.disabled} onClick={() => closeEntry.onClose(l.id)}>{CLOSE_BUTTON}</button>
                    )}
                  </article>
                );
              })}
            </div>
          )}
          {a && b ? (
            <Surface className="fcc-compare" aria-label="השוואת הלוואות">
              <table className="fcc-compare__table">
                <thead><tr><th></th><th>{a.name}</th><th>{b.name}</th></tr></thead>
                <tbody>
                  {compareRows(a, b).map((r) => <tr key={r.label}><th scope="row">{r.label}</th><td>{r.a}</td><td>{r.b}</td></tr>)}
                </tbody>
              </table>
              <p className="fcc-goal__note">ההשוואה מציגה נתונים בלבד — ההחלטה שלך.</p>
            </Surface>
          ) : picked.length === 1 ? <p className="fcc-goal__note">בחר הלוואה נוספת להשוואה (עד 2).</p> : null}
          <PayoffEngine loans={loans} loadScenario={loadScenario} />
        </div>
      )}
    </section>
  );
}

