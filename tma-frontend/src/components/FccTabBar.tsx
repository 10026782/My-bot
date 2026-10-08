import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import type { FccTurn } from "../types";
import {
  COMPOSER, FCC_TABS, WRITER_WORDS, chipsEnabled, inputVisible, panelId, tabForKey, tabId, writerView,
  type ComposerChip, type FccTabKey,
} from "../lib/fccTabs";
import { Surface } from "./ui/Surface";

export function FccTabBar({ active, onChange }: { active: FccTabKey; onChange: (key: FccTabKey) => void }) {
  // roving tabindex: only the selected tab is in the Tab order, so the arrows must reach the others
  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    const rtl = getComputedStyle(e.currentTarget).direction === "rtl";
    const next = tabForKey(active, e.key, rtl);
    if (!next) return;
    e.preventDefault();
    onChange(next);
    document.getElementById(tabId(next))?.focus();
  };
  return (
    <div className="fcc-tabs" role="tablist" aria-label="אזורי המרכז הכלכלי" onKeyDown={onKeyDown}>
      {FCC_TABS.map((t) => (
        <button key={t.key} type="button" role="tab" id={tabId(t.key)} aria-selected={active === t.key} aria-controls={panelId(t.key)}
                tabIndex={active === t.key ? 0 : -1} className={`fcc-tab ${active === t.key ? "fcc-tab--on" : ""}`}
                onClick={() => onChange(t.key)}>{t.label}</button>
      ))}
    </div>
  );
}

export interface ComposerTargets { goals: { id: string; title: string }[]; loans: { id: string; title: string }[] }

/** ONE writer for the whole screen, dressed per tab (title + chips). The draft/turn state lives in the parent — a single
 *  shared draft slot — so switching tabs never forks it. Chips and card actions only name an intent; every answer,
 *  review and confirmation is the server's (the same BusinessDraft flow as free text). */
export function ContextualComposer({ tab, turn, receipt, error, busy, targets, onStart, onSend, onDismiss }: {
  tab: FccTabKey; turn: FccTurn | null; receipt: string | null; error: string | null; busy: boolean; targets: ComposerTargets;
  onStart: (intent: string, entityId?: string) => void; onSend: (text: string, goalId?: string) => void; onDismiss: () => void;
}) {
  const cfg = COMPOSER[tab];
  const view = writerView(turn, receipt);
  const [text, setText] = useState("");
  const [picking, setPicking] = useState<ComposerChip | null>(null);
  const ref = useRef<HTMLElement | null>(null);
  const first = useRef(true);
  // the answer is shown above the input and pushes it down: bring the composer back into view when the server answers
  useEffect(() => {
    if (first.current) { first.current = false; return; }
    ref.current?.scrollIntoView?.({ block: "start", behavior: "smooth" });
  }, [turn, receipt, error]);
  useEffect(() => { if (turn) setPicking(null); }, [turn]);

  const canPick = chipsEnabled(view, busy);
  const options = picking?.pick === "loan" ? targets.loans : targets.goals;
  const active = turn != null || receipt != null || picking != null;     // compact while idle, expanded only for an active draft
  const submit = () => { const value = text.trim(); if (value) { onSend(value); setText(""); } };
  // mobile: a button press blurs the textarea, the keyboard closes and the click is lost — keep the focus
  const keepKeyboard = (e: { preventDefault: () => void }) => e.preventDefault();

  return (
    <section className={`fcc-section fcc-composer ${active ? "fcc-composer--open" : "fcc-composer--idle"}`} aria-labelledby="fcc-quick-heading" ref={ref}>
      <h2 id="fcc-quick-heading" className="fcc-section__heading">{cfg.title}</h2>
      <Surface className="fcc-quick">
        {cfg.chips.length > 0 && (
          <div className="fcc-chips" role="group" aria-label="סוג עדכון">
            {cfg.chips.map((c) => (
              <button key={c.intent} type="button" aria-pressed={picking?.intent === c.intent} disabled={!canPick}
                      className={`fcc-chip ${picking?.intent === c.intent ? "fcc-chip--on" : ""}`}
                      onClick={() => (c.pick ? setPicking(picking?.intent === c.intent ? null : c) : onStart(c.intent))}>{c.label}</button>
            ))}
          </div>
        )}
        {picking && (
          <div className="fcc-quick__turn">
            <p className="fcc-quick__message">{picking.pick === "loan" ? "איזו הלוואה?" : "איזה יעד?"}</p>
            {options.length === 0 ? (
              <p className="fcc-goal__note">{picking.pick === "loan" ? "אין הלוואות פעילות." : "אין יעדים פעילים."}</p>
            ) : (
              <div className="fcc-quick__choices">
                {options.map((o) => (
                  <button key={o.id} type="button" className="boss-button boss-button--quiet boss-bubble--action" disabled={busy}
                          onClick={() => onStart(picking.intent, o.id)}>{o.title}</button>
                ))}
              </div>
            )}
          </div>
        )}
        {(turn || receipt) && (
          <div className="fcc-quick__turn" role="status">
            <p className="fcc-quick__message">{view.message}</p>
            {view.choices.length > 0 && (
              <div className="fcc-quick__choices">
                {view.choices.map((c) => (
                  <button key={c.goal_id} type="button" className="boss-button boss-button--quiet boss-bubble--action" disabled={busy}
                          onClick={() => onSend(c.title || c.goal_id, c.goal_id)}>{c.title}</button>
                ))}
              </div>
            )}
            <div className="fcc-quick__choices">
              {view.confirm && (
                <button type="button" className="boss-button boss-button--primary boss-bubble--action" disabled={busy}
                        onClick={() => onSend(WRITER_WORDS.confirm)}>{view.confirm}</button>
              )}
              {view.canEdit && (
                <button type="button" className="boss-button boss-button--quiet boss-bubble--action" disabled={busy}
                        onClick={() => onSend(WRITER_WORDS.edit)}>ערוך</button>
              )}
              {view.cancelsDraft && (
                <button type="button" className="boss-button boss-button--quiet boss-bubble--action" disabled={busy}
                        onClick={() => onSend(WRITER_WORDS.cancel)}>בטל</button>
              )}
              {view.dismissOnly && (
                <button type="button" className="boss-button boss-button--quiet boss-bubble--action" onClick={onDismiss}>סגור</button>
              )}
            </div>
          </div>
        )}
        {inputVisible(cfg, view, picking != null) && (
          <>
            <textarea className="fcc-quick__input" rows={active ? 2 : 1} value={text} aria-label={cfg.title}
                      placeholder={view.showInput ? "ענה כאן…" : "כתוב עדכון כלכלי…"} onChange={(e) => setText(e.target.value)} />
            {(active || text.trim() !== "") && (
              <button type="button" className="boss-button boss-button--primary boss-bubble--action" disabled={busy || !text.trim()}
                    onPointerDown={keepKeyboard} onMouseDown={keepKeyboard} onClick={submit}>
              {busy ? "בודק…" : view.showInput ? "שלח" : "שלח עדכון"}
            </button>
            )}
          </>
        )}
        {!active && !cfg.freeText && <p className="fcc-goal__note">{cfg.hint}</p>}
        {error && <p className="fcc-quick__error" role="alert">⚠️ {error}</p>}
      </Surface>
    </section>
  );
}
