import { useEffect, useRef, useState } from "react";
import type { FccLoans } from "../types";
import {
  CLOSE_BUTTON, CLOSE_WORDS, FILTERS, RANK_MODES, STATUS_UNKNOWN, UNKNOWN, compareRows, filterLoans, loanCardModel, loanGoalModel, loanHeaderCards, sortLoans, togglePick, applyTurn, canClose, closeView,
  type CloseFlow, type LoanFilter, type RankMode,
} from "../lib/fccLoans";
import { KpiCard } from "./FccKpiCard";
import { PayoffEngine, type LoadScenario } from "./FccPayoff";
import type { FccTurn } from "../types";
import { ScreenState } from "./ui/ScreenState";
import { Surface } from "./ui/Surface";

/** Injected so the tested components never import api.ts: open = POST /loans/close (writes nothing), send = the shared
 *  /write conversation ("אשר" / "ערוך" / "בטל" / an answer), onDone = reload the overview after the writes landed. */
export interface LoanCloseApi {
  open: (loanId: string) => Promise<FccTurn>;
  send: (text: string) => Promise<FccTurn>;
  onDone: () => void;
}

export function LoansSection({ loans, loadScenario, closeApi }: { loans: FccLoans; loadScenario?: LoadScenario; closeApi?: LoanCloseApi }) {
  const [filter, setFilter] = useState<LoanFilter>("all");
  const [mode, setMode] = useState<RankMode>("high_interest");
  const [picked, setPicked] = useState<string[]>([]);
  const [closing, setClosing] = useState<CloseFlow | null>(null);
  const [closeBusy, setCloseBusy] = useState(false);
  const [closeError, setCloseError] = useState<string | null>(null);
  const visible = sortLoans(filterLoans(loans.items, filter), loans, mode);
  const goal = loanGoalModel(loans);
  const byId = (id: string) => loans.items.find((l) => l.id === id);
  const a = picked[0] ? byId(picked[0]) : undefined;
  const b = picked[1] ? byId(picked[1]) : undefined;

  const panelRef = useRef<HTMLDivElement | null>(null);
  // the panel sits above the list: bring it into view when a card's button opens it or the server answers
  useEffect(() => { panelRef.current?.scrollIntoView?.({ block: "start", behavior: "smooth" }); }, [closing?.turn, closing?.receipt]);
  const runClose = async (action: () => Promise<FccTurn>, base: CloseFlow) => {
    if (closeBusy || !closeApi) return;
    setCloseBusy(true);
    setCloseError(null);
    try {
      const next = applyTurn(base, await action());
      setClosing(next.flow);
      if (next.refresh) closeApi.onDone();
    } catch (e) {
      setCloseError((e as Error).message || "הפעולה נכשלה");
      if (!base.turn && !base.receipt) setClosing(null);        // opening failed: nothing is open, the buttons come back
    } finally {
      setCloseBusy(false);
    }
  };
  const startClose = (loanId: string) => {
    if (!closeApi || closing?.turn) return;               // one open closing flow at a time (a finished receipt does not block the next)
    const base: CloseFlow = { loanId, turn: null, receipt: null };
    setClosing(base);
    void runClose(() => closeApi.open(loanId), base);
  };

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
          {closeApi && closing && (closing.turn || closing.receipt) && (
            <div ref={panelRef}>
              <LoanClosePanel flow={closing} busy={closeBusy} error={closeError}
                              onSend={(text) => void runClose(() => closeApi.send(text), closing)}
                              onDismiss={() => { setClosing(null); setCloseError(null); }} />
            </div>
          )}
          {closeError && !(closing && (closing.turn || closing.receipt)) && <p className="fcc-quick__error" role="alert">⚠️ {closeError}</p>}
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
                    {closeApi && canClose(l) && (
                      <button type="button" className="boss-button boss-button--quiet boss-bubble--action fcc-loan__closebtn"
                              disabled={closeBusy || closing?.turn != null} onClick={() => startClose(l.id)}>{CLOSE_BUTTON}</button>
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


/** Server-driven close-loan panel under a loan card: renders the server's turn and sends the owner's next word. */
export function LoanClosePanel({ flow, busy, error, onSend, onDismiss }: {
  flow: CloseFlow; busy: boolean; error: string | null; onSend: (text: string) => void; onDismiss: () => void;
}) {
  const [text, setText] = useState("");
  const v = closeView(flow);
  const submit = () => { const value = text.trim(); if (value) { onSend(value); setText(""); } };
  return (
    <Surface className="fcc-quick fcc-loan__close" aria-label="סגירת הלוואה">
      <div className="fcc-quick__turn" role="status">
        <p className="fcc-quick__message">{v.message}</p>
      </div>
      {v.showInput && (
        <>
          <textarea className="fcc-quick__input" rows={2} value={text} aria-label="תשובה לסגירת ההלוואה"
                    placeholder="ענה כאן…" onChange={(e) => setText(e.target.value)} />
          <button type="button" className="boss-button boss-button--primary boss-bubble--action" disabled={busy || !text.trim()}
                  onPointerDown={(e) => e.preventDefault()} onMouseDown={(e) => e.preventDefault()} onClick={submit}>
            {busy ? "בודק…" : "שלח"}
          </button>
        </>
      )}
      <div className="fcc-quick__choices">
        {v.confirm && (
          <button type="button" className="boss-button boss-button--primary boss-bubble--action" disabled={busy}
                  onClick={() => onSend(CLOSE_WORDS.confirm)}>{v.confirm}</button>
        )}
        {v.canEdit && (
          <button type="button" className="boss-button boss-button--quiet boss-bubble--action" disabled={busy}
                  onClick={() => onSend(CLOSE_WORDS.edit)}>ערוך</button>
        )}
        {v.cancelsDraft && (
          <button type="button" className="boss-button boss-button--quiet boss-bubble--action" disabled={busy}
                  onClick={() => onSend(CLOSE_WORDS.cancel)}>בטל</button>
        )}
        {v.dismissOnly && (
          <button type="button" className="boss-button boss-button--quiet boss-bubble--action" onClick={onDismiss}>סגור</button>
        )}
      </div>
      {error && <p className="fcc-quick__error" role="alert">⚠️ {error}</p>}
    </Surface>
  );
}
