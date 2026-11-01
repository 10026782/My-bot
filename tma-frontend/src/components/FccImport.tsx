import { useRef, useState } from "react";
import { postFccImportPreview, postFccImportRun } from "../api";
import type { FccImportPreview } from "../types";
import { IMPORT_NOTE, KIND_LABEL, START, advance, progressText, reviewOf, type Progress } from "../lib/fccImport";
import { ScreenState } from "./ui/ScreenState";
import { Surface } from "./ui/Surface";

type Phase = { name: "idle" } | { name: "checking" } | { name: "review"; preview: FccImportPreview } | { name: "running"; preview: FccImportPreview; progress: Progress }
  | { name: "error"; message: string };

const MAX_STEPS = 400;                        // a hard stop for the client loop (each step writes one chunk)

/** The import card of the "תזרים" tab: choose the statement, review exactly what would be written, confirm ONCE; the server writes it in chunks. */
export function FccImport({ onImported }: { onImported: () => void }) {
  const [open, setOpen] = useState(false);
  const [kind, setKind] = useState<"bank" | "card">("bank");
  const [label, setLabel] = useState("main");
  const [phase, setPhase] = useState<Phase>({ name: "idle" });
  const file = useRef<File | null>(null);
  const form = (digest?: string) => {
    const f = new FormData();
    f.append("kind", kind); f.append("label", label || "main"); f.append("file", file.current as File);
    if (digest) f.append("digest", digest);
    return f;
  };

  const check = async () => {
    if (!file.current) return;
    setPhase({ name: "checking" });
    try { setPhase({ name: "review", preview: await postFccImportPreview(form()) }); }
    catch (e) { setPhase({ name: "error", message: (e as Error).message || "לא הצלחנו לקרוא את הקובץ" }); }
  };

  const confirm = async (preview: FccImportPreview) => {
    if (!preview.digest || !file.current) return;
    let progress: Progress = START;
    for (let i = 0; i < MAX_STEPS; i += 1) {
      setPhase({ name: "running", preview, progress });
      try { progress = advance(progress, await postFccImportRun(form(preview.digest))); }
      catch (e) { progress = { ...progress, blocked: (e as Error).message || "הכתיבה נעצרה — אפשר לנסות שוב (מה שנכתב לא ייכתב פעמיים)" }; }
      if (progress.blocked || progress.done) break;
    }
    setPhase({ name: "running", preview, progress });
    if (progress.done) onImported();
  };

  const review = phase.name === "review" ? reviewOf(phase.preview) : phase.name === "running" ? reviewOf(phase.preview) : null;
  return (
    <section className="fcc-section" aria-labelledby="cf-import-heading">
      <h2 id="cf-import-heading" className="fcc-section__heading">ייבוא דוח</h2>
      <button type="button" className="boss-button boss-button--quiet boss-bubble--action" aria-expanded={open} onClick={() => setOpen(!open)}>
        {open ? "סגור" : "ייבוא דוח בנק / כרטיס אשראי"}
      </button>
      {open && (
        <Surface className="fcc-quick">
          <div className="fcc-chips" role="group" aria-label="סוג הדוח">
            {(Object.keys(KIND_LABEL) as ("bank" | "card")[]).map((k) => (
              <button key={k} type="button" aria-pressed={kind === k} className={`fcc-chip ${kind === k ? "fcc-chip--on" : ""}`}
                      onClick={() => { setKind(k); setPhase({ name: "idle" }); }}>{KIND_LABEL[k]}</button>
            ))}
          </div>
          {kind === "bank" && (
            <label className="fcc-goal__note">שם החשבון (קבוע בין ייבואים, למשל main): <input value={label} maxLength={20} onChange={(e) => setLabel(e.target.value)} /></label>
          )}
          <input type="file" accept={kind === "card" ? ".xlsx,.pdf" : ".pdf"} aria-label="קובץ הדוח"
                 onChange={(e) => { file.current = e.target.files?.[0] ?? null; setPhase({ name: "idle" }); }} />
          <button type="button" className="boss-button boss-button--primary boss-bubble--action" disabled={phase.name === "checking" || phase.name === "running"} onClick={() => void check()}>בדיקה (לא נכתב דבר)</button>
          <p className="fcc-goal__note">{IMPORT_NOTE}</p>
          {phase.name === "checking" && <ScreenState state="loading" title="קורא ומסווג את הדוח" message="אין כתיבה בשלב הזה." />}
          {phase.name === "error" && <ScreenState state="error" title="לא ניתן לייבא" message={phase.message} />}
          {review && (phase.name === "review" || phase.name === "running") && (
            <div className="fcc-stack">
              {review.blocked.map((b) => <p key={b} className="fcc-goal__note">⚠ {b}</p>)}
              <p><strong>{review.headline}</strong></p>
              <div className="fcc-list">
                {review.months.map((m) => <div key={m.month} className="fcc-event"><span>{m.label}</span><span>הוצאות {m.expenses}</span><span>הכנסות {m.income}</span><span>{m.events} רישומים</span></div>)}
              </div>
              {review.skipped.length > 0 && (
                <div className="fcc-list" aria-label="מה לא ייכתב">
                  {review.skipped.map((s) => <div key={s.key} className="fcc-event"><span>{s.label}</span><span>{s.count}</span><span>{s.total}</span></div>)}
                </div>
              )}
              {review.pendingNote && <p className="fcc-goal__note">{review.pendingNote}</p>}
              {review.pending.length > 0 && <ul>{review.pending.map((p) => <li key={p}>{p}</li>)}</ul>}
              {phase.name === "review" && review.canImport && (
                <button type="button" className="boss-button boss-button--primary boss-bubble--action" onClick={() => void confirm(phase.preview)}>{review.confirmLabel}</button>
              )}
              {phase.name === "running" && <p role="status">{progressText(phase.progress)}</p>}
              {phase.name === "running" && phase.progress.blocked && (
                <button type="button" className="boss-button boss-button--primary boss-bubble--action" onClick={() => void confirm(phase.preview)}>נסה שוב</button>
              )}
            </div>
          )}
        </Surface>
      )}
    </section>
  );
}
