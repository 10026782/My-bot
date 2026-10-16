import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { fetchFccOverview, postFccIntent, postFccWrite } from "../api";
import type { FccTurn } from "../types";
import {
  COMPOSER, DEFAULT_TAB, FCC_TABS, WRITER_WORDS, chipsEnabled, inputVisible, nextWriterState, panelId, tabForKey, tabId, writerView,
  type ComposerChip, type ComposerConfig, type FccTabKey,
} from "../lib/fccTabs";
import { Surface } from "./ui/Surface";

/** The FCC tab strip; reused (with its own ``tabs`` / ``idPrefix`` / ``ariaLabel``) by other screens so tabs look and behave the same. */
export function FccTabBar<K extends string = FccTabKey>({ active, onChange, tabs, idPrefix = "fcc", ariaLabel = "אזורי המרכז הכלכלי" }: {
  active: K; onChange: (key: K) => void; tabs?: readonly { key: K; label: string }[]; idPrefix?: string; ariaLabel?: string;
}) {
  const list = (tabs ?? FCC_TABS) as unknown as readonly { key: K; label: string }[];
  // roving tabindex: only the selected tab is in the Tab order, so the arrows must reach the others
  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    const rtl = getComputedStyle(e.currentTarget).direction === "rtl";
    const next = tabForKey(active, e.key, rtl, list);
    if (!next) return;
    e.preventDefault();
    onChange(next);
    document.getElementById(tabId(next, idPrefix))?.focus();
  };
  return (
    <div className="fcc-tabs" role="tablist" aria-label={ariaLabel} onKeyDown={onKeyDown}>
      {list.map((t) => (
        <button key={t.key} type="button" role="tab" id={tabId(t.key, idPrefix)} aria-selected={active === t.key} aria-controls={panelId(t.key, idPrefix)}
                tabIndex={active === t.key ? 0 : -1} className={`fcc-tab ${active === t.key ? "fcc-tab--on" : ""}`}
                onClick={() => onChange(t.key)}>{t.label}</button>
      ))}
    </div>
  );
}

export interface ComposerTargets { goals: { id: string; title: string }[]; loans: { id: string; title: string }[]; assets: { id: string; title: string }[]; accounts?: { id: string; title: string }[] }

/** ONE writer for the whole screen, dressed per tab (title + chips). The draft/turn state lives in the parent — a single
 *  shared draft slot — so switching tabs never forks it. Chips and card actions only name an intent; every answer,
 *  review and confirmation is the server's (the same BusinessDraft flow as free text). */
export function ContextualComposer({ tab, config, turn, receipt, error, busy, targets, onStart, onSend, onDismiss }: {
  tab?: FccTabKey; config?: ComposerConfig; turn: FccTurn | null; receipt: string | null; error: string | null; busy: boolean; targets: ComposerTargets;
  onStart: (intent: string, entityId?: string) => void; onSend: (text: string, goalId?: string) => void; onDismiss: () => void;
}) {
  const cfg = config ?? COMPOSER[tab ?? DEFAULT_TAB];
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
  const options = picking?.pick === "loan" ? targets.loans : picking?.pick === "asset" ? targets.assets : picking?.pick === "account" ? (targets.accounts ?? []) : targets.goals;
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
            <p className="fcc-quick__message">{picking.pick === "loan" ? "איזו הלוואה?" : picking.pick === "asset" ? "איזה נכס?" : picking.pick === "account" ? "איזה חשבון?" : "איזה יעד?"}</p>
            {options.length === 0 ? (
              <p className="fcc-goal__note">{picking.pick === "loan" ? "אין הלוואות פעילות." : picking.pick === "asset" ? "אין נכסים לעדכון." : picking.pick === "account" ? "אין חשבונות פעילים לעדכון." : "אין יעדים פעילים."}</p>
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

/** The single shared writer state (one draft slot per person): the composer in every tab renders THIS, so a half-finished
 *  draft is never forked by a tab switch. All logic is the server's; this only calls it and keeps the latest turn. */
export function useFccWriter(initial: FccTurn | null, tab: string, onDone: () => void) {
  const [turn, setTurn] = useState<FccTurn | null>(initial);
  const [receipt, setReceipt] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [followUp, setFollowUp] = useState(false);
  const [followUpAsset, setFollowUpAsset] = useState<string | null>(null);
  // the overview (and a draft opened in chat) arrives after the first render: adopt it unless this screen is already showing something
  useEffect(() => { if (initial && !turn && !receipt) setTurn(initial); }, [initial]);   // eslint-disable-line react-hooks/exhaustive-deps

  const run = async (call: () => Promise<FccTurn>) => {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const result = await call();
      const next = nextWriterState(result);
      setTurn(next.turn);
      setReceipt(next.receipt);
      if (result.state === "partial_failure") setError(result.message);
      setFollowUp(result.state === "executed" && result.follow_up === "savings");
      setFollowUpAsset(result.state === "executed" ? result.follow_up_asset ?? null : null);
      if (next.refresh) onDone();
    } catch (e) {
      setError((e as Error).message || "הפעולה נכשלה");
    } finally {
      setBusy(false);
    }
  };
  const start = (intent: string, entityId?: string) => run(async () => {
    const result = await postFccIntent(intent, entityId);
    if (result.state !== "info" || !result.entity) return result;
    // another draft is already open: show IT (the server's own latest turn) instead of a dead-end message
    const open = await fetchFccOverview().then((o) => o.draft).catch(() => null);
    return open ?? result;
  });
  const send = (text: string, goalId?: string) => run(() => postFccWrite({ text, scope: tab, ...(goalId ? { goal_id: goalId } : {}) }));
  const dismiss = () => { setTurn(null); setReceipt(null); setError(null); };
  return { turn, receipt, error, busy, start, send, dismiss, followUp, clearFollowUp: () => setFollowUp(false),
           followUpAsset, clearFollowUpAsset: () => setFollowUpAsset(null) };
}
