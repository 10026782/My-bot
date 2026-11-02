import { useRef, useState } from "react";
import { postFccImportPreview, postFccImportRun } from "../api";
import { IMPORT_NOTE, KIND_LABEL, START, advance, batchConfirmLabel, batchTotals, checkedItem, itemLine, reviewOf, runnable, type BatchItem } from "../lib/fccImport";
import { ScreenState } from "./ui/ScreenState";
import { Surface } from "./ui/Surface";

const MAX_STEPS = 400;                        // a hard stop for the client loop of ONE file (each step writes one chunk)

/** One file's review: the months, what will not be written and why. */
function FileReview({ item }: { item: BatchItem }) {
  if (!item.preview || item.status === "error") return null;
  const review = reviewOf(item.preview);
  return (
    <details className="fcc-sold">
      <summary>פירוט</summary>
      <div className="fcc-stack">
        <div className="fcc-list">
          {review.months.map((m) => <div key={m.month} className="fcc-event"><span>{m.label}</span><span>הוצאות {m.expenses}</span><span>הכנסות {m.income}</span><span>{m.events} רישומים</span></div>)}
        </div>
        {review.skipped.length > 0 && (
          <div className="fcc-list" aria-label="מה לא ייכתב">
            {review.skipped.map((s) => <div key={s.key} className="fcc-event"><span>{s.label}</span><span>{s.count}</span><span>{s.total}</span></div>)}
          </div>
        )}
        {review.uncategorizedNote && <p className="fcc-goal__note">{review.uncategorizedNote}</p>}
        {review.pendingNote && <p className="fcc-goal__note">{review.pendingNote}</p>}
      </div>
    </details>
  );
}

/** The import card of the "תזרים" tab: choose one or several statements, review what each would write, confirm ONCE; the files are written one after the other. */
export function FccImport({ onImported }: { onImported: () => void }) {
  const [open, setOpen] = useState(false);
  const [kind, setKind] = useState<"bank" | "card">("bank");
  const [label, setLabel] = useState("main");
  const [items, setItems] = useState<BatchItem[]>([]);
  const [busy, setBusy] = useState(false);
  const [finished, setFinished] = useState(false);
  const files = useRef<File[]>([]);
  const form = (file: File, digest?: string) => {
    const f = new FormData();
    f.append("kind", kind); f.append("label", label || "main"); f.append("file", file);
    if (digest) f.append("digest", digest);
    return f;
  };
  const patch = (id: number, over: Partial<BatchItem>) => setItems((prev) => prev.map((i) => (i.id === id ? { ...i, ...over } : i)));

  const choose = (list: FileList | null) => {
    files.current = Array.from(list ?? []);
    setItems(files.current.map((f, id) => ({ id, name: f.name, status: "waiting" as const })));
    setFinished(false);
  };

  const check = async () => {
    if (files.current.length === 0) return;
    setBusy(true); setFinished(false);
    for (let id = 0; id < files.current.length; id += 1) {          // one file at a time: the server allows ONE import at a time
      patch(id, { status: "checking" });
      try {
        const preview = await postFccImportPreview(form(files.current[id]));
        setItems((prev) => prev.map((i) => (i.id === id ? checkedItem(i, preview) : i)));
      } catch (e) { patch(id, { status: "error", error: (e as Error).message || "לא הצלחנו לקרוא את הקובץ — לא נכתב דבר" }); }
    }
    setBusy(false);
  };

  const confirm = async () => {
    setBusy(true); setFinished(false);
    let wrote = false;
    for (const item of runnable(items)) {
      const digest = item.preview?.digest;
      if (!digest) continue;
      let progress = START;
      for (let step = 0; step < MAX_STEPS; step += 1) {
        patch(item.id, { status: "running", progress });
        try { progress = advance(progress, await postFccImportRun(form(files.current[item.id], digest))); }
        catch (e) { progress = { ...progress, blocked: (e as Error).message || "הכתיבה נעצרה — אפשר לנסות שוב (מה שנכתב לא ייכתב פעמיים)" }; }
        if (progress.blocked || progress.done) break;
      }
      patch(item.id, { status: progress.done ? "done" : "blocked", progress });
      if (progress.done || progress.written > 0) wrote = true;
    }
    setBusy(false); setFinished(true);
    if (wrote) onImported();
  };

  const totals = batchTotals(items);
  const checked = items.length > 0 && items.every((i) => i.status !== "waiting" && i.status !== "checking");
  const canConfirm = checked && !busy && totals.ready > 0 && runnable(items).length > 0;
  return (
    <section className="fcc-section" aria-labelledby="cf-import-heading">
      <h2 id="cf-import-heading" className="fcc-section__heading">ייבוא דוח</h2>
      <button type="button" className="boss-button boss-button--quiet boss-bubble--action" aria-expanded={open} onClick={() => setOpen(!open)}>
        {open ? "סגור" : "ייבוא דוחות בנק / כרטיס אשראי"}
      </button>
      {open && (
        <Surface className="fcc-quick">
          <div className="fcc-chips" role="group" aria-label="סוג הדוח">
            {(Object.keys(KIND_LABEL) as ("bank" | "card")[]).map((k) => (
              <button key={k} type="button" aria-pressed={kind === k} className={`fcc-chip ${kind === k ? "fcc-chip--on" : ""}`}
                      onClick={() => { setKind(k); setItems((prev) => prev.map((i) => ({ id: i.id, name: i.name, status: "waiting" as const }))); setFinished(false); }}>{KIND_LABEL[k]}</button>
            ))}
          </div>
          {kind === "bank" && (
            <label className="fcc-goal__note">שם החשבון (קבוע בין ייבואים, למשל main): <input value={label} maxLength={20} onChange={(e) => setLabel(e.target.value)} /></label>
          )}
          <input type="file" multiple accept={kind === "card" ? ".xlsx,.pdf" : ".pdf"} aria-label="קבצי הדוחות" disabled={busy}
                 onChange={(e) => choose(e.target.files)} />
          <p className="fcc-goal__note">אפשר לבחור כמה קבצים מאותו סוג בבת אחת — כל קובץ נבדק ונכתב בנפרד, ואישור אחד מכסה את כולם.</p>
          <button type="button" className="boss-button boss-button--primary boss-bubble--action" disabled={busy || items.length === 0} onClick={() => void check()}>בדיקה (לא נכתב דבר)</button>
          <p className="fcc-goal__note">{IMPORT_NOTE}</p>
          {items.length > 0 && (
            <div className="fcc-stack">
              <div className="fcc-list" aria-label="הקבצים">
                {items.map((i) => (
                  <div key={i.id} className="fcc-task">
                    <p><strong>{i.name}</strong></p>
                    <p className={i.status === "error" || i.status === "blocked" ? "fcc-goal__note" : undefined} role={i.status === "running" ? "status" : undefined}>
                      {i.status === "error" || i.status === "blocked" ? "⚠ " : i.status === "done" ? "✓ " : ""}{itemLine(i)}
                    </p>
                    <FileReview item={i} />
                  </div>
                ))}
              </div>
              {checked && !finished && totals.errors > 0 && <p className="fcc-goal__note">⚠ {totals.errors} קבצים לא ייכתבו (לא ניתן לקרוא או שהדוח אינו מתיישב) — השאר ייכתבו.</p>}
              {checked && !finished && totals.ready === 0 && <ScreenState state="empty" title="אין מה לכתוב" message="כל הקבצים כבר יובאו, או שלא ניתן לקרוא אותם." />}
              {canConfirm && (
                <button type="button" className="boss-button boss-button--primary boss-bubble--action" onClick={() => void confirm()}>
                  {finished ? "נסה שוב את מה שנעצר" : batchConfirmLabel(totals)}
                </button>
              )}
              {finished && !busy && runnable(items).length === 0 && <p role="status">הושלם: כל הקבצים נכתבו.</p>}
            </div>
          )}
        </Surface>
      )}
    </section>
  );
}
