import type { FccAssets } from "../types";
import { assetCardModel, assetsHeaderCards, debtLines, soldCardModel, soldNote } from "../lib/fccAssets";
import { UNKNOWN } from "../lib/fccLoans";
import { KpiCard } from "./FccKpiCard";
import { ScreenState } from "./ui/ScreenState";
import { Surface } from "./ui/Surface";

/** Card actions run in the shared contextual composer: a button only names the intent + the asset. */
export interface AssetActions {
  onAction: (intent: string, assetId: string) => void;
  disabled: boolean;          // a draft is already open in the shared writer (one slot per person)
}

export const ASSET_ACTIONS = [
  { intent: "asset.update_value", label: "עדכון שווי" },
  { intent: "asset.update_mortgage", label: "עדכון משכנתא" },
  { intent: "asset.next_step", label: "פעולה הבאה" },
  { intent: "asset.mark_sold", label: "נמכר" },          // a state transition: the review + a separate approval follow
] as const;

export function AssetsSection({ assets, actions }: { assets: FccAssets; actions?: AssetActions }) {
  const soldCount = assets.sold?.count ?? 0;
  if (assets.items.length === 0 && soldCount === 0) {
    return <ScreenState state="empty" title="אין נכסים" message="הנכסים נרשמים בטבלת Assets." />;
  }
  return (
    <section className="fcc-section" aria-labelledby="fcc-assets-heading">
      <h2 id="fcc-assets-heading" className="fcc-section__heading">נכסים והון</h2>
      <div className="fcc-stack fcc-stack--tight">
        <div className="fcc-kpis">
          {assetsHeaderCards(assets).map((c) => <KpiCard key={c.key} label={c.label} value={c.value} hint={c.hint} />)}
        </div>
        {soldNote(assets) && <p className="fcc-goal__note" role="note">{soldNote(assets)}</p>}
        <Surface variant="subtle" padding="compact" className="fcc-loans-goal">
          <h3 className="fcc-loans-goal__title">חוב ביחס לנכסים</h3>
          <dl className="fcc-loans-goal__grid">
            {debtLines(assets).map((l) => <div key={l.label}><dt>{l.label}</dt><dd className={l.value === UNKNOWN ? "fcc-unknown" : undefined}>{l.value}</dd></div>)}
          </dl>
          <p className="fcc-loan__meta">משכנתא רשומה והלוואות מקושרות עשויות לתאר את אותו חוב — הן מוצגות בנפרד ולא מחוברות.</p>
        </Surface>
        <div className="fcc-list fcc-list--tight">
          {assets.items.length === 0 && <ScreenState state="empty" title="אין נכסים פעילים" message="כל הנכסים הרשומים סומנו כנמכרו." />}
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
                {m.nextStep && <p className="fcc-asset__step"><strong>פעולה הבאה:</strong> {m.nextStep}</p>}
                {m.linkedLoans.length > 0 && (
                  <div className="fcc-asset__loans">
                    <p className="fcc-loan__meta"><strong>הלוואות מקושרות</strong></p>
                    {m.linkedLoans.map((l) => <p key={l.id} className="fcc-loan__meta">{l.text}</p>)}
                    {m.linkedDebtLine && <p className="fcc-pay__saving">{m.linkedDebtLine}</p>}
                  </div>
                )}
                {actions && m.actionable && (
                  <div className="fcc-loan__actions">
                    {ASSET_ACTIONS.map((a) => (
                      <button key={a.intent} type="button" className="boss-button boss-button--quiet boss-bubble--action fcc-loan__actionbtn"
                              disabled={actions.disabled} onClick={() => actions.onAction(a.intent, m.id)}>{a.label}</button>
                    ))}
                  </div>
                )}
              </article>
            );
          })}
        </div>
        {soldCount > 0 && (
          <details className="fcc-sold">
            <summary>נכסים שנמכרו ({soldCount})</summary>
            <div className="fcc-list fcc-list--tight">
              {(assets.sold?.items ?? []).map((i) => {
                const m = soldCardModel(i);
                return (
                  <article key={m.id} className="fcc-loan fcc-asset fcc-asset--sold">
                    <header className="fcc-loan__head"><div className="fcc-loan__titlebox"><h3 className="fcc-loan__title">{m.title}</h3>
                      <div className="fcc-loan__tags"><span className="fcc-tag fcc-tag--muted">נמכר</span></div></div></header>
                    <dl className="fcc-pay__figures">
                      {m.rows.map((r) => <div key={r.label}><dt>{r.label}</dt><dd className={r.value === UNKNOWN ? "fcc-unknown" : undefined}>{r.value}</dd></div>)}
                    </dl>
                    {m.openLoans.length > 0 && (
                      <div className="fcc-asset__loans">
                        <p className="fcc-loan__meta"><strong>הלוואות שעדיין פתוחות ומקושרות לנכס</strong></p>
                        {m.openLoans.map((t) => <p key={t} className="fcc-loan__meta">{t}</p>)}
                      </div>
                    )}
                  </article>
                );
              })}
            </div>
          </details>
        )}
      </div>
    </section>
  );
}
