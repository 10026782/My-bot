import { useEffect, useRef, useState } from "react";
import { fetchFccRules, postFccRule } from "../api";
import type { FccRuleView } from "../types";
import { customCategory, refreshAction } from "../lib/fccClassify";
import { ruleConfirmLine, ruleModel } from "../lib/fccClassifyRules";
import { ScreenState } from "./ui/ScreenState";
import { Surface } from "./ui/Surface";

type Phase = { name: "closed" } | { name: "loading" } | { name: "open"; view: FccRuleView } | { name: "saving"; view: FccRuleView } | { name: "error"; message: string };

/** Descriptions waiting in the owner's rules table, one at a time: choose a category -> review line -> אשר. The answer becomes a decided rule (ONE patch of ONE
 *  rule through the same ceremony as every FCC write); the next import writes every row with that description already classified. */
export function FccClassifyRules({ summary, onChanged, refreshKey = 0 }: { summary: { total: number } | null | undefined; onChanged: () => void; refreshKey?: number }) {
  const [phase, setPhase] = useState<Phase>({ name: "closed" });
  const [skipped, setSkipped] = useState<string[]>([]);
  const [pick, setPick] = useState<{ key: string; label: string } | null>(null);
  const [custom, setCustom] = useState("");
  const [note, setNote] = useState<string | null>(null);
  const seenKey = useRef(refreshKey);

  const load = async (skip: string[]) => {
    setPhase({ name: "loading" }); setPick(null); setCustom("");
    try { setPhase({ name: "open", view: await fetchFccRules(skip) }); }
    catch (e) { setPhase({ name: "error", message: (e as Error).message || "לא הצלחנו לטעון" }); }
  };
  // a new statement was imported: an open panel loads the new rows by itself (no screen refresh needed)
  useEffect(() => {
    const action = refreshAction(phase.name, seenKey.current, refreshKey);
    seenKey.current = refreshKey;
    if (action === "reload") { setSkipped([]); setNote(null); void load([]); }
  }, [refreshKey]);                                                  // eslint-disable-line react-hooks/exhaustive-deps
  if (!summary || summary.total === 0) return null;
  const confirm = async (view: FccRuleView) => {
    if (!view.item || !pick) return;
    setPhase({ name: "saving", view });
    try {
      const next = await postFccRule({ rule_id: view.item.id, category: pick.key });
      setNote("נשמר — ייכנס לתוקף בייבוא הבא"); setPick(null); setCustom(""); onChanged();
      setPhase({ name: "open", view: next.item && skipped.includes(next.item.id) ? await fetchFccRules(skipped) : next });
    } catch (e) { setPhase({ name: "error", message: (e as Error).message || "הסיווג לא הושלם — אפשר לנסות שוב" }); }
  };

  const view = phase.name === "open" || phase.name === "saving" ? phase.view : null;
  const model = view ? ruleModel(view) : null;
  const typed = customCategory(custom);
  return (
    <section className="fcc-section" aria-labelledby="cf-rules-heading">
      <h2 id="cf-rules-heading" className="fcc-section__heading">תיאורים לסיווג</h2>
      <p className="fcc-goal__note">{summary.total} תיאורים (בתי עסק ותשלומים) ממתינים לקטגוריה. סיווג אחד מכסה את כל השורות עם אותו שם — בייבוא הבא ובכל ייבוא אחריו.</p>
      {phase.name === "closed" && (
        <button type="button" className="boss-button boss-button--primary boss-bubble--action" onClick={() => void load(skipped)}>סווג תיאור אחד-אחד</button>
      )}
      {phase.name === "loading" && <ScreenState state="loading" title="טוען תיאור לסיווג" />}
      {phase.name === "error" && (
        <ScreenState state="error" title="לא ניתן לסווג" message={phase.message}
                     action={<button type="button" className="boss-button boss-button--primary boss-bubble--action" onClick={() => void load(skipped)}>נסו שוב</button>} />
      )}
      {model && view && (
        <Surface className="fcc-quick">
          {note && <p role="status" className="fcc-goal__note">{note}</p>}
          <p className="fcc-goal__note">{model.header}</p>
          {model.empty || !model.item ? (
            <ScreenState state="empty" title={model.empty ? "הכול מסווג" : "דילגת על כל התיאורים שנותרו"} message={model.empty ? "ייבא שוב את הדוחות כדי שהשורות ייכנסו מסווגות." : "הם יחזרו בפעם הבאה."} />
          ) : (
            <div className="fcc-stack">
              <div className="fcc-event"><strong>{model.item.title}</strong><span className="fcc-goal__note">{model.item.meta}</span></div>
              {!pick ? (
                <>
                  <div className="fcc-chips" role="group" aria-label="קטגוריה">
                    {model.categories.map((c) => <button key={c.key} type="button" className="fcc-chip" onClick={() => setPick(c)}>{c.label}</button>)}
                  </div>
                  <label className="fcc-goal__note">קטגוריה חדשה: <input value={custom} maxLength={40} onChange={(e) => setCustom(e.target.value)} /></label>
                  {typed && <button type="button" className="boss-button boss-button--quiet boss-bubble--action" onClick={() => setPick({ key: typed, label: typed })}>+ {typed}</button>}
                  <button type="button" className="boss-button boss-button--quiet boss-bubble--action"
                          onClick={() => { const next = [...skipped, model.item!.id]; setSkipped(next); setNote(null); void load(next); }}>דלג</button>
                </>
              ) : (
                <>
                  <p role="status"><strong>{ruleConfirmLine(model, pick.label)}</strong></p>
                  <button type="button" className="boss-button boss-button--primary boss-bubble--action" disabled={phase.name === "saving"} onClick={() => void confirm(view)}>אשר סיווג</button>
                  <button type="button" className="boss-button boss-button--quiet boss-bubble--action" disabled={phase.name === "saving"} onClick={() => setPick(null)}>שנה</button>
                </>
              )}
            </div>
          )}
        </Surface>
      )}
    </section>
  );
}
