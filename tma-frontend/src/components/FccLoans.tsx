import { useState } from "react";
import type { FccLoans } from "../types";
import {
  ARRANGEMENT_BUTTON, BALANCE_BUTTON, balanceCardModel, CLOSE_BUTTON, NEXT_ACTION_BUTTON, PARTIAL_BUTTON, PAYMENT_BUTTON, RECEIVED_BUTTON,
  FILTERS, RANK_MODES, STATUS_UNKNOWN, UNKNOWN, actionRows, compareRows, filterLoans, loanCardModel, loanGoalModel, loanHeaderCards,
  receivableCardModel, receivableItems, receivablesSummary, sortLoans, togglePick, canClose,
  type ActionRow, type LoanFilter, type RankMode,
} from "../lib/fccLoans";
import { STEP_ACTIONS } from "./FccAssets";
import { KpiCard } from "./FccKpiCard";
import { PayoffEngine, type LoadScenario } from "./FccPayoff";
import { ScreenState } from "./ui/ScreenState";
import { Surface } from "./ui/Surface";

/** Card actions run in the shared contextual composer: a button only names the intent + the loan. */
export interface LoanActions {
  onAction: (intent: string, loanId: string) => void;
  disabled: boolean;          // a draft is already open in the shared writer (one slot per person)
}

const BTN = "boss-button boss-button--quiet boss-bubble--action fcc-loan__actionbtn";

/** The OPEN next actions of one loan / debt; a click names the intent and the TASK id (never text) — review + אשר follow. */
function OpenActions({ rows, actions }: { rows: ActionRow[]; actions?: LoanActions }) {
  if (rows.length === 0) return null;
  return (
    <div className="fcc-asset__steps" aria-label="פעולות הבאות פתוחות">
      <p className="fcc-loan__meta"><strong>פעולות הבאות ({rows.length})</strong></p>
      {rows.map((a) => (
        <div key={a.id} className="fcc-asset__step">
          <p><strong>{a.title}</strong> <span className="fcc-tag fcc-tag--muted">{a.statusLabel}</span></p>
          {a.meta && <p className="fcc-loan__meta">{a.meta}</p>}
          {a.history.map((h) => <p key={h} className="fcc-loan__meta">{h}</p>)}
          {actions && (
            <div className="fcc-loan__actions">
              {STEP_ACTIONS.filter((x) => !("hideWhenInProgress" in x && x.hideWhenInProgress && a.inProgress)).map((x) => (
                <button key={x.intent} type="button" className={BTN} disabled={actions.disabled} onClick={() => actions.onAction(x.intent, a.id)}>{x.label}</button>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

/** The write actions every active debt has (own loan or owed to me); the loan itself is named, never typed. */
function DebtActions({ id, actions }: { id: string; actions: LoanActions }) {
  return (
    <>
      <button type="button" className={BTN} disabled={actions.disabled} onClick={() => actions.onAction("loan.partial_payment", id)}>{PARTIAL_BUTTON}</button>
      <button type="button" className={BTN} disabled={actions.disabled} onClick={() => actions.onAction("loan.arrangement", id)}>{ARRANGEMENT_BUTTON}</button>
      <button type="button" className={BTN} disabled={actions.disabled} onClick={() => actions.onAction("loan.next_step", id)}>{NEXT_ACTION_BUTTON}</button>
    </>
  );
}

function BalanceCard({ loans }: { loans: FccLoans }) {
  const m = balanceCardModel(loans);
  if (!m) return null;
  return (
    <Surface variant="subtle" padding="compact" className="fcc-loans-goal" aria-label="חייבים לי מול החובות שלי">
      <h3 className="fcc-loans-goal__title">חייבים לי מול החובות שלי</h3>
      <dl className="fcc-loans-goal__grid">
        {m.lines.map((l) => <div key={l.label}><dt>{l.label}</dt><dd className={l.value === UNKNOWN ? "fcc-unknown" : undefined}>{l.value}</dd></div>)}
      </dl>
      <p className={m.positive ? "fcc-pay__saving" : "fcc-goal__note"}>{m.verdict}</p>
      {m.notes.map((n) => <p key={n} className="fcc-loan__meta">{n}</p>)}
    </Surface>
  );
}

function ReceivablesSection({ loans, actions }: { loans: FccLoans; actions?: LoanActions }) {
  const items = receivableItems(loans);
  if (items.length === 0) return null;
  return (
    <section className="fcc-stack fcc-stack--tight" aria-labelledby="fcc-receivables-heading">
      <BalanceCard loans={loans} />
      <h3 id="fcc-receivables-heading" className="fcc-loans-goal__title">חובות שחייבים לי</h3>
      <p className="fcc-goal__note">{receivablesSummary(loans)} · לא נספרים בהתחייבויות שלך, ותשלום שמתקבל עליהם אינו הכנסה.</p>
      <div className="fcc-list fcc-list--tight">
        {items.map((l) => {
          const m = receivableCardModel(l);
          return (
            <article key={m.id} className="fcc-loan">
              <header className="fcc-loan__head"><div className="fcc-loan__titlebox"><h3 className="fcc-loan__title">{m.title}</h3></div></header>
              <dl className="fcc-loan__key"><div className="fcc-loan__key-main"><dt>יתרת החוב</dt><dd className={m.balance === UNKNOWN ? "fcc-unknown" : undefined}>{m.balance}</dd></div></dl>
              <p className={`fcc-loan__freed ${m.arrangementKnown ? "" : "fcc-loan__freed--unknown"}`}>{m.arrangement}</p>
              <OpenActions rows={m.actions} actions={actions} />
              {actions && (
                <div className="fcc-loan__actions">
                  <DebtActions id={l.id} actions={actions} />
                  <button type="button" className={BTN} disabled={actions.disabled} onClick={() => actions.onAction("loan.update_balance", l.id)}>{BALANCE_BUTTON}</button>
                  <button type="button" className="boss-button boss-button--quiet boss-bubble--action fcc-loan__closebtn"
                          disabled={actions.disabled} onClick={() => actions.onAction("loan.close", l.id)}>{RECEIVED_BUTTON}</button>
                </div>
              )}
            </article>
          );
        })}
      </div>
    </section>
  );
}

export function LoansSection({ loans, loadScenario, actions }: { loans: FccLoans; loadScenario?: LoadScenario; actions?: LoanActions }) {
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
      {loans.summary.total_active_loans === 0 && !(loans.receivables?.count) ? (
        <ScreenState state="empty" title="אין הלוואות פעילות" message="הלוואות נרשמות בטבלת Loans." />
      ) : loans.summary.total_active_loans === 0 ? (
        <ReceivablesSection loans={loans} actions={actions} />       // only debts owed to the owner: nothing of the liabilities tools applies
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
                    <OpenActions rows={actionRows(l)} actions={actions} />
                    {actions && canClose(l) && (
                      <div className="fcc-loan__actions">
                        <DebtActions id={l.id} actions={actions} />
                        <button type="button" className="boss-button boss-button--quiet boss-bubble--action fcc-loan__actionbtn"
                                disabled={actions.disabled} onClick={() => actions.onAction("loan.update_balance", l.id)}>{BALANCE_BUTTON}</button>
                        <button type="button" className="boss-button boss-button--quiet boss-bubble--action fcc-loan__actionbtn"
                                disabled={actions.disabled} onClick={() => actions.onAction("loan.update_payment", l.id)}>{PAYMENT_BUTTON}</button>
                        <button type="button" className="boss-button boss-button--quiet boss-bubble--action fcc-loan__closebtn"
                                disabled={actions.disabled} onClick={() => actions.onAction("loan.close", l.id)}>{CLOSE_BUTTON}</button>
                      </div>
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
          <ReceivablesSection loans={loans} actions={actions} />
          <PayoffEngine loans={loans} loadScenario={loadScenario} />
        </div>
      )}
    </section>
  );
}

