import { useState } from "react";
import { postFccRefinance } from "../api";
import { REFINANCE_HELP, REFINANCE_TITLE, offerBody, refinanceModel, type OfferInput, type RefinanceLine } from "../lib/fccRefinance";
import type { FccRefinance } from "../types";
import { Surface } from "./ui/Surface";

function Lines({ lines }: { lines: RefinanceLine[] }) {
  return (
    <dl className="fcc-loans-goal__grid">
      {lines.map((l) => <div key={l.label}><dt>{l.label}</dt><dd className={l.tone === "good" ? "fcc-pay__saving" : l.tone === "bad" ? "fcc-unknown" : undefined}>{l.value}</dd></div>)}
    </dl>
  );
}

/** One typed offer -> which loans are worth rolling into it and what it changes. Read-only: nothing is saved. */
export function RefinanceSimulator() {
  const [input, setInput] = useState<OfferInput>({ rate: "", years: "", fees: "", insurance: "" });
  const [picked, setPicked] = useState<string[] | null>(null);          // null = all loans
  const [fees, setFees] = useState<Record<string, string>>({});
  const [result, setResult] = useState<FccRefinance | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async (ids: string[] | null) => {
    const built = offerBody(input, ids, fees);
    if ("error" in built) { setError(built.error); return; }
    setBusy(true); setError(null);
    try { setResult(await postFccRefinance(built.body)); } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };
  const toggle = (id: string) => {
    const all = result?.rows.map((r) => r.id) ?? [];
    const cur = picked ?? all;
    const next = cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id];
    setPicked(next);
    void run(next);
  };
  const set = (k: keyof OfferInput) => (e: React.ChangeEvent<HTMLInputElement>) => setInput((cur) => ({ ...cur, [k]: e.target.value }));
  const m = result ? refinanceModel(result) : null;
  const chosen = picked ?? result?.rows.map((r) => r.id) ?? [];

  return (
    <Surface variant="subtle" padding="compact" className="fcc-loans-goal" aria-label={REFINANCE_TITLE}>
      <details>
        <summary><strong>{REFINANCE_TITLE}</strong></summary>
        <div className="fcc-stack fcc-stack--tight">
          <p className="fcc-loan__meta">{REFINANCE_HELP}</p>
          <div className="fcc-loan__actions">
            <label>ריבית שנתית % <input inputMode="decimal" value={input.rate} onChange={set("rate")} /></label>
            <label>תקופה (שנים) <input inputMode="decimal" value={input.years} onChange={set("years")} /></label>
            <label>עלויות חד-פעמיות ₪ <input inputMode="decimal" value={input.fees} onChange={set("fees")} /></label>
            <label>ביטוח לחודש ₪ <input inputMode="decimal" value={input.insurance} onChange={set("insurance")} /></label>
            <button type="button" className="boss-button boss-button--quiet boss-bubble--action" disabled={busy} onClick={() => void run(picked)}>{busy ? "מחשב…" : "חשב"}</button>
          </div>
          {error && <p className="fcc-goal__note" role="alert">{error}</p>}
          {m && (
            <>
              {m.recommended && (
                <section aria-label="ההלוואות שכדאי לכלול">
                  <h4 className="fcc-pay__subhead">{m.recommendedPays ? `כדאי לכלול: ${m.recommendedNames.join(", ")}` : "במצב הזה המחזור לא משתלם"}</h4>
                  <Lines lines={m.recommended} />
                </section>
              )}
              {!m.recommended && <p className="fcc-goal__note">אף הלוואה לא חוסכת ריבית בהצעה הזו.</p>}
              {m.relief && (
                <section aria-label="הקלה בהחזר החודשי">
                  <h4 className="fcc-pay__subhead">אם המטרה היא להקל על ההחזר החודשי (הזול קודם): {m.reliefNames.join(", ")}</h4>
                  <Lines lines={m.relief} />
                </section>
              )}
              {m.selected && (
                <section aria-label="ההלוואות שנבחרו">
                  <h4 className="fcc-pay__subhead">לפי ההלוואות שסימנת ({result?.selected?.loans})</h4>
                  <Lines lines={m.selected} />
                </section>
              )}
              <div className="fcc-list fcc-list--tight">
                {m.rows.map((r) => (
                  <article key={r.id} className="fcc-loan">
                    <label className="fcc-loan__title"><input type="checkbox" checked={chosen.includes(r.id)} onChange={() => toggle(r.id)} /> {r.title} <span className={`fcc-tag fcc-tag--${r.tone === "good" ? "plain" : "muted"}`}>{r.verdict}</span></label>
                    {r.lines.map((l) => <p key={l} className="fcc-loan__meta">{l}</p>)}
                    {r.needsFee && (
                      <label className="fcc-loan__meta">עמלת פירעון ₪ <input inputMode="decimal" value={fees[r.id] ?? ""} onChange={(e) => setFees((cur) => ({ ...cur, [r.id]: e.target.value }))} onBlur={() => void run(picked)} /></label>
                    )}
                  </article>
                ))}
              </div>
              {m.notes.map((n) => <p key={n} className="fcc-loan__meta">{n}</p>)}
            </>
          )}
        </div>
      </details>
    </Surface>
  );
}
