import { useState } from "react";
import { fetchFccClassify, postFccClassify } from "../api";
import type { FccClassifyView } from "../types";
import { classifyModel, confirmLine, customCategory, resultNote } from "../lib/fccClassify";
import { money } from "../lib/fccPresentation";
import { ScreenState } from "./ui/ScreenState";
import { Surface } from "./ui/Surface";

type Phase = { name: "closed" } | { name: "loading" } | { name: "open"; view: FccClassifyView } | { name: "saving"; view: FccClassifyView } | { name: "error"; message: string };

/** Imported expenses that have no category, one at a time: choose a category -> review line -> אשר. The server patches ONE field of ONE record per answer
 *  through the same ceremony as every other FCC write; "skip" only hides the row for this visit. */
export function FccClassify({ summary, onChanged }: { summary: { total: number; total_amount: number } | null | undefined; onChanged: () => void }) {
  const [phase, setPhase] = useState<Phase>({ name: "closed" });
  const [skipped, setSkipped] = useState<string[]>([]);
  const [pick, setPick] = useState<{ key: string; label: string } | null>(null);
  const [custom, setCustom] = useState("");
  const [applySame, setApplySame] = useState(true);
  const [note, setNote] = useState<string | null>(null);

  if (!summary || summary.total === 0) return null;
  const load = async (skip: string[]) => {
    setPhase({ name: "loading" }); setPick(null); setCustom("");
    try { setPhase({ name: "open", view: await fetchFccClassify(skip) }); }
    catch (e) { setPhase({ name: "error", message: (e as Error).message || "לא הצלחנו לטעון" }); }
  };
  const confirm = async (view: FccClassifyView) => {
    if (!view.item || !pick) return;
    setPhase({ name: "saving", view });
    try {
      const next = await postFccClassify({ event_id: view.item.id, category: pick.key, apply_same: applySame && view.item.same_count > 0 });
      setNote(resultNote(next)); setPick(null); setCustom(""); onChanged();
      setPhase({ name: "open", view: next.item && skipped.includes(next.item.id) ? await fetchFccClassify(skipped) : next });
    } catch (e) { setPhase({ name: "error", message: (e as Error).message || "הסיווג לא הושלם — אפשר לנסות שוב" }); }
  };

  const view = phase.name === "open" || phase.name === "saving" ? phase.view : null;
  const model = view ? classifyModel(view) : null;
  const typed = customCategory(custom);
  return (
    <section className="fcc-section" aria-labelledby="cf-classify-heading">
      <h2 id="cf-classify-heading" className="fcc-section__heading">הוצאות לסיווג</h2>
      <p className="fcc-goal__note">{summary.total} הוצאות יובאו בלי קטגוריה ({money(summary.total_amount)}). הן מופיעות כ״לא מסווג״ עד שתסווג.</p>
      {phase.name === "closed" && (
        <button type="button" className="boss-button boss-button--primary boss-bubble--action" onClick={() => void load(skipped)}>סווג הוצאה אחת-אחת</button>
      )}
      {phase.name === "loading" && <ScreenState state="loading" title="טוען הוצאה לסיווג" />}
      {phase.name === "error" && (
        <ScreenState state="error" title="לא ניתן לסווג" message={phase.message}
                     action={<button type="button" className="boss-button boss-button--primary boss-bubble--action" onClick={() => void load(skipped)}>נסו שוב</button>} />
      )}
      {model && view && (
        <Surface className="fcc-quick">
          {note && <p role="status" className="fcc-goal__note">{note}</p>}
          <p className="fcc-goal__note">{model.header}</p>
          {model.empty || !model.item ? (
            <ScreenState state="empty" title={model.empty ? "הכול מסווג" : "דילגת על כל ההוצאות שנותרו"} message={model.empty ? undefined : "הן יחזרו בפעם הבאה."} />
          ) : (
            <div className="fcc-stack">
              <div className="fcc-event"><strong>{model.item.title}</strong><span>{model.item.amount}</span><span className="fcc-goal__note">{model.item.meta}</span></div>
              {!pick ? (
                <>
                  <div className="fcc-chips" role="group" aria-label="קטגוריה">
                    {model.categories.map((c) => (
                      <button key={c.key} type="button" className="fcc-chip" onClick={() => setPick(c)}>{c.label}</button>
                    ))}
                  </div>
                  <label className="fcc-goal__note">קטגוריה חדשה: <input value={custom} maxLength={40} onChange={(e) => setCustom(e.target.value)} /></label>
                  {typed && <button type="button" className="boss-button boss-button--quiet boss-bubble--action" onClick={() => setPick({ key: typed, label: typed })}>+ {typed}</button>}
                  <button type="button" className="boss-button boss-button--quiet boss-bubble--action"
                          onClick={() => { const next = [...skipped, model.item!.id]; setSkipped(next); setNote(null); void load(next); }}>דלג</button>
                </>
              ) : (
                <>
                  <p role="status"><strong>{confirmLine(model, pick.label, applySame)}</strong></p>
                  {model.sameLabel && (
                    <label className="fcc-goal__note"><input type="checkbox" checked={applySame} onChange={(e) => setApplySame(e.target.checked)} /> {model.sameLabel}</label>
                  )}
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
