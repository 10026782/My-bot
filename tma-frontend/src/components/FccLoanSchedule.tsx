import { useRef, useState } from "react";
import { postFccLoanSchedule } from "../api";
import { SCHEDULE_HELP, SCHEDULE_TITLE, schedulePreviewModel } from "../lib/fccLoanSchedule";
import type { FccLoanSchedulePreview } from "../types";
import { Surface } from "./ui/Surface";

interface Item { name: string; file: File; preview?: FccLoanSchedulePreview; loanId?: string; status: "reading" | "ready" | "saving" | "saved" | "error"; error?: string }

/** The lender's amortization schedule (Excel): read first (nothing written), then ONE confirm per file saves it on the chosen loan. */
export function LoanScheduleImport({ onSaved }: { onSaved?: () => void }) {
  const [items, setItems] = useState<Item[]>([]);
  const input = useRef<HTMLInputElement>(null);
  const patch = (i: number, p: Partial<Item>) => setItems((cur) => cur.map((x, k) => (k === i ? { ...x, ...p } : x)));

  const pick = async (files: FileList | null) => {
    if (!files?.length) return;
    const chosen = Array.from(files).map((file): Item => ({ name: file.name, file, status: "reading" }));
    const base = items.length;
    setItems((cur) => [...cur, ...chosen]);
    for (let k = 0; k < chosen.length; k += 1) {
      const form = new FormData();
      form.append("file", chosen[k].file);
      try {
        const preview = await postFccLoanSchedule(form);
        patch(base + k, { preview, status: "ready", loanId: preview.candidates?.length === 1 ? preview.candidates[0].id : undefined });
      } catch (e) {
        patch(base + k, { status: "error", error: (e as Error).message });
      }
    }
    if (input.current) input.current.value = "";
  };

  const save = async (i: number) => {
    const it = items[i];
    if (!it.preview?.digest || !it.loanId) return;
    patch(i, { status: "saving" });
    const form = new FormData();
    form.append("file", it.file);
    form.append("confirm", "1");
    form.append("loan_id", it.loanId);
    form.append("digest", it.preview.digest);
    try {
      const out = await postFccLoanSchedule(form);
      patch(i, { status: out.state === "saved" ? "saved" : "error", error: out.state === "saved" ? undefined : out.message ?? "השמירה נכשלה" });
      if (out.state === "saved") onSaved?.();
    } catch (e) {
      patch(i, { status: "error", error: (e as Error).message });
    }
  };

  return (
    <Surface variant="subtle" padding="compact" className="fcc-loans-goal" aria-label={SCHEDULE_TITLE}>
      <h3 className="fcc-loans-goal__title">{SCHEDULE_TITLE}</h3>
      <p className="fcc-loan__meta">{SCHEDULE_HELP}</p>
      <input ref={input} type="file" multiple accept=".xlsx" aria-label="בחירת קבצי לוח סילוקין" onChange={(e) => void pick(e.target.files)} />
      {items.map((it, i) => {
        const m = it.preview ? schedulePreviewModel(it.preview) : null;
        return (
          <div key={`${it.name}-${i}`} className="fcc-stack fcc-stack--tight">
            <p><strong>{it.name}</strong> {it.status === "reading" && "· קורא…"}{it.status === "saved" && "· נשמר ✓"}{it.status === "error" && `· ${it.error ?? "שגיאה"}`}</p>
            {m?.problems.map((p) => <p key={p} className="fcc-goal__note">{p}</p>)}
            {m && m.lines.map((l) => <p key={l} className="fcc-loan__meta">{l}</p>)}
            {m && m.canSave && it.status !== "saved" && (
              <div className="fcc-loan__actions">
                {m.needsChoice && (
                  <select aria-label="בחירת הלוואה" value={it.loanId ?? ""} onChange={(e) => patch(i, { loanId: e.target.value || undefined })}>
                    <option value="">בחר הלוואה…</option>
                    {m.candidates.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
                  </select>
                )}
                {!m.needsChoice && <span className="fcc-loan__meta">תישמר ב: {m.candidates[0].label}</span>}
                <button type="button" className="boss-button boss-button--quiet boss-bubble--action" disabled={!it.loanId || it.status === "saving"} onClick={() => void save(i)}>
                  {it.status === "saving" ? "שומר…" : "שמור לוח סילוקין"}
                </button>
              </div>
            )}
          </div>
        );
      })}
    </Surface>
  );
}
