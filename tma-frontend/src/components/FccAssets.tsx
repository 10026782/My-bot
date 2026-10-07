import type { FccAssets } from "../types";
import { assetCardModel, assetsHeaderCards, debtLines } from "../lib/fccAssets";
import { UNKNOWN } from "../lib/fccLoans";
import { KpiCard } from "./FccKpiCard";
import { ScreenState } from "./ui/ScreenState";
import { Surface } from "./ui/Surface";

export function AssetsSection({ assets }: { assets: FccAssets }) {
  if (assets.items.length === 0) {
    return <ScreenState state="empty" title="אין נכסים" message="הנכסים נרשמים בטבלת Assets." />;
  }
  return (
    <section className="fcc-section" aria-labelledby="fcc-assets-heading">
      <h2 id="fcc-assets-heading" className="fcc-section__heading">נכסים והון</h2>
      <div className="fcc-stack fcc-stack--tight">
        <div className="fcc-kpis">
          {assetsHeaderCards(assets).map((c) => <KpiCard key={c.key} label={c.label} value={c.value} hint={c.hint} />)}
        </div>
        <Surface variant="subtle" padding="compact" className="fcc-loans-goal">
          <h3 className="fcc-loans-goal__title">חוב ביחס לנכסים</h3>
          <dl className="fcc-loans-goal__grid">
            {debtLines(assets).map((l) => <div key={l.label}><dt>{l.label}</dt><dd className={l.value === UNKNOWN ? "fcc-unknown" : undefined}>{l.value}</dd></div>)}
          </dl>
          <p className="fcc-loan__meta">משכנתא רשומה והלוואות מקושרות עשויות לתאר את אותו חוב — הן מוצגות בנפרד ולא מחוברות.</p>
        </Surface>
        <div className="fcc-list fcc-list--tight">
          {assets.items.map((i) => {
            const m = assetCardModel(i);
            return (
              <article key={m.id} className="fcc-loan fcc-asset">
                <header className="fcc-loan__head">
                  <div className="fcc-loan__titlebox">
                    <h3 className="fcc-loan__title">{m.title}</h3>
                    <div className="fcc-loan__tags">
                      <span className={`fcc-tag ${m.typeLabel === "לא סווג" ? "fcc-tag--muted" : "fcc-tag--plain"}`}>{m.typeLabel}</span>
                      {m.status && <span className="fcc-tag">{m.status}</span>}
                      {m.partial && <span className="fcc-tag fcc-tag--muted">נתונים חלקיים</span>}
                    </div>
                  </div>
                </header>
                <dl className="fcc-pay__figures">
                  {m.rows.map((r) => <div key={r.label}><dt>{r.label}</dt><dd className={r.value === UNKNOWN ? "fcc-unknown" : undefined}>{r.value}</dd></div>)}
                </dl>
                {m.linkedLoans.length > 0 && (
                  <div className="fcc-asset__loans">
                    <p className="fcc-loan__meta"><strong>הלוואות מקושרות</strong></p>
                    {m.linkedLoans.map((l) => <p key={l.id} className="fcc-loan__meta">{l.text}</p>)}
                    {m.linkedDebtLine && <p className="fcc-pay__saving">{m.linkedDebtLine}</p>}
                  </div>
                )}
              </article>
            );
          })}
        </div>
      </div>
    </section>
  );
}
