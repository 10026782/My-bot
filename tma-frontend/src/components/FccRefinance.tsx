import { useState } from "react";
import { postFccRefinance } from "../api";
import { REFINANCE_HELP, REFINANCE_HOW, REFINANCE_TITLE, monthRows, offerBody, refinanceModel, totalsGroups, yearRows, type OfferInput, type RefinanceLine, type ScenarioTable } from "../lib/fccRefinance";
import type { FccRefinanceTotals } from "../types";
import type { FccRefinance } from "../types";
import { Surface } from "./ui/Surface";

function Lines({ lines }: { lines: RefinanceLine[] }) {
  return (
    <dl className="fcc-loans-goal__grid">
      {lines.map((l) => <div key={l.label}><dt>{l.label}</dt><dd className={l.tone === "good" ? "fcc-pay__saving" : l.tone === "bad" ? "fcc-unknown" : undefined}>{l.value}</dd></div>)}
    </dl>
  );
}

function Totals({ t, detail, onDetail }: { t: FccRefinanceTotals; detail?: boolean; onDetail?: () => void }) {
  const years = yearRows(t), months = monthRows(t);
  return (
    <>
      {totalsGroups(t).map((g) => (
        <section key={g.title} aria-label={g.title}>
          <h5 className="fcc-pay__subhead">{g.title}</h5>
          {g.hint && <p className="fcc-loan__meta">{g.hint}</p>}
          <Lines lines={g.lines} />
        </section>
      ))}
      {t.uses_estimates && <p className="fcc-goal__note">חלק מהחישוב בקירוב — הלוואות בלי לוח מהבנק: {(t.estimated_loans ?? []).join(", ")}</p>}
      {years.length > 0 && (
        <details>
          <summary>שנה אחרי שנה: כמה תשלם בכל חלופה</summary>
          <div className="fcc-table-scroll" role="region" tabIndex={0} aria-label="שנה אחרי שנה">
          <table className="fcc-compare__table fcc-pay__table">
            <thead><tr><th>שנה</th><th>היום</th><th>כמו היום</th><th>פריסה</th><th>הפרש בפריסה</th><th>מצטבר</th></tr></thead>
            <tbody>{years.map((y) => <tr key={y.year}><th scope="row">{y.year}</th><td>{y.today}</td><td>{y.keep}</td><td>{y.stretch}</td><td>{y.diff}</td><td className={y.tone === "good" ? "fcc-pay__saving" : y.tone === "bad" ? "fcc-unknown" : undefined}>{y.cum}</td></tr>)}</tbody>
          </table>
          </div>
          <p className="fcc-loan__meta">ההפרש הוא מה שאתה חוסך (פלוס) או משלם יותר (מינוס) ביחס להיום. בשנים שההלוואות המקוריות כבר נגמרו, ״היום״ הוא 0.</p>
          {onDetail && <button type="button" className="boss-button boss-button--quiet boss-bubble--action" onClick={onDetail}>{detail ? "הסתר תשלום אחרי תשלום" : "הצג תשלום אחרי תשלום"}</button>}
          {detail && months.length > 0 && (
            <div className="fcc-table-scroll" role="region" tabIndex={0} aria-label="תשלום אחרי תשלום">
              <table className="fcc-compare__table fcc-pay__table">
                <thead><tr><th>חודש</th><th>היום</th><th>כמו היום</th><th>פריסה</th></tr></thead>
                <tbody>{months.map((m) => <tr key={m.month}><th scope="row">{m.month}</th>{[m.today, m.keep, m.stretch].map((c, i) => <td key={i}>{c.pay}{c.split && <span className="fcc-cell__split">{c.split}</span>}</td>)}</tr>)}</tbody>
              </table>
            </div>
          )}
        </details>
      )}
    </>
  );
}

function Table({ t }: { t: ScenarioTable }) {
  return (
    <div className="fcc-pay__scenario">
      <h5 className="fcc-pay__subhead">{t.title}</h5>
      <div className="fcc-table-scroll" role="region" tabIndex={0} aria-label={t.title}>
      <table className="fcc-compare__table fcc-pay__table">
        <thead><tr><th></th><th>היום</th><th>אחרי מחזור</th><th>הפרש</th></tr></thead>
        <tbody>
          {t.rows.map((r) => (
            <tr key={r.label}><th scope="row">{r.label}</th><td>{r.today}</td><td>{r.after}</td><td className={r.tone === "good" ? "fcc-pay__saving" : r.tone === "bad" ? "fcc-unknown" : undefined}>{r.diff}</td></tr>
          ))}
        </tbody>
      </table>
      </div>
    </div>
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
  const [detail, setDetail] = useState(false);                             // payment-by-payment rows for the selected loans (asked for on demand)

  const run = async (ids: string[] | null, withDetail: boolean = detail) => {
    const built = offerBody(input, ids, fees, withDetail);
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
  const toggleDetail = () => { const next = !detail; setDetail(next); void run(picked, next); };
  const set = (k: keyof OfferInput) => (e: React.ChangeEvent<HTMLInputElement>) => setInput((cur) => ({ ...cur, [k]: e.target.value }));
  const m = result ? refinanceModel(result) : null;
  const chosen = picked ?? result?.rows.map((r) => r.id) ?? [];

  return (
    <Surface variant="subtle" padding="compact" className="fcc-loans-goal fcc-refi" aria-label={REFINANCE_TITLE}>
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
                  <h4 className="fcc-pay__subhead">{m.recommendedPays ? `כדאי למחזר: ${m.recommendedNames.join(", ")}` : "בהצעה הזו המחזור לא משתלם"}</h4>
                  {result?.recommended && <Totals t={result.recommended} />}
                </section>
              )}
              {!m.recommended && <p className="fcc-goal__note">אין הלוואה שהמחזור שלה חוסך ריבית בהצעה הזו.</p>}
              {m.relief && (
                <section aria-label="הקלה בהחזר החודשי">
                  <h4 className="fcc-pay__subhead">אם המטרה היא להקל על ההחזר החודשי (מהזולה ליקרה): {m.reliefNames.join(", ")}</h4>
                  {result?.relief && <Totals t={result.relief} />}
                </section>
              )}
              {m.selected && (
                <section aria-label="ההלוואות שנבחרו">
                  <h4 className="fcc-pay__subhead">סיכום לפי ההלוואות שסימנת ({result?.selected?.loans})</h4>
                  {result?.selected && <Totals t={result.selected} detail={detail} onDetail={toggleDetail} />}
                </section>
              )}
              <div className="fcc-list fcc-list--tight">
                {m.rows.map((r) => (
                  <article key={r.id} className="fcc-loan">
                    <label className="fcc-loan__title"><input type="checkbox" checked={chosen.includes(r.id)} onChange={() => toggle(r.id)} /> {r.title} <span className={`fcc-tag fcc-tag--${r.tone === "good" ? "plain" : "muted"}`}>{r.verdict}</span></label>
                    {r.facts.map((l) => <p key={l} className="fcc-loan__meta">{l}</p>)}
                    {r.reason && <p className="fcc-goal__note">{r.reason}</p>}
                    {r.tables.length > 0 && (
                      <details>
                        <summary>לפני ואחרי המחזור</summary>
                        {r.tables.map((t) => <Table key={t.title} t={t} />)}
                      </details>
                    )}
                    {r.reliefLine && <p className="fcc-loan__meta">{r.reliefLine}</p>}
                    {r.needsFee && (
                      <label className="fcc-loan__meta">עמלת פירעון של ההלוואה (₪) <input inputMode="decimal" value={fees[r.id] ?? ""} onChange={(e) => setFees((cur) => ({ ...cur, [r.id]: e.target.value }))} onBlur={() => void run(picked)} /></label>
                    )}
                  </article>
                ))}
              </div>
              {m.notes.map((n) => <p key={n} className="fcc-loan__meta">{n}</p>)}
              <details>
                <summary>איך חישבתי?</summary>
                {REFINANCE_HOW.map((h) => <p key={h} className="fcc-loan__meta">{h}</p>)}
              </details>
            </>
          )}
        </div>
      </details>
    </Surface>
  );
}
