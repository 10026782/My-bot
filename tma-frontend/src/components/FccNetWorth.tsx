import type { FccNetWorth } from "../types";
import { netWorthModel } from "../lib/fccNetWorth";
import { KpiCard } from "./FccKpiCard";
import { ScreenState } from "./ui/ScreenState";
import { Surface } from "./ui/Surface";

export type NetWorthState = { status: "loading" } | { status: "ok"; data: FccNetWorth } | { status: "error"; code?: number };

/** Read-only net-worth card for the "החשבונות" tab. Own call, own states: a 404 (or no permission) shows nothing at all. */
export function NetWorthCard({ state, onRetry }: { state: NetWorthState; onRetry: () => void }) {
  if (state.status === "loading") return <ScreenState state="loading" title="טוען שווי נקי" message="מחבר חשבונות, נכסים והתחייבויות…" />;
  if (state.status === "error") {
    if (state.code === 404 || state.code === 401 || state.code === 403) return null;
    return (
      <ScreenState state="error" title="לא הצלחנו לטעון את השווי הנקי" message="אפשר לנסות שוב בעוד רגע."
                   action={<button type="button" className="boss-button boss-button--primary boss-bubble--action" onClick={onRetry}>נסו שוב</button>} />
    );
  }
  const m = netWorthModel(state.data);
  return (
    <section className="fcc-section" aria-label={m.net.label}>
      <div className="fcc-kpis">
        <KpiCard label={m.net.label} value={m.net.value} hint={m.net.hint} />
        {m.rows.map((r) => <KpiCard key={r.key} label={r.label} value={r.value} hint={r.hint} />)}
      </div>
      {m.receivables && (
        <Surface variant="subtle" padding="compact" className="fcc-kpi" aria-label={m.receivables.label}>
          <p className="fcc-kpi__label">{m.receivables.label}</p>
          <p className="fcc-kpi__value">{m.receivables.value}</p>
          <p className="fcc-kpi__hint">{m.receivables.hint}</p>
        </Surface>
      )}
      {m.notes.map((n) => <p key={n} className="fcc-goal__note">{n}</p>)}
    </section>
  );
}
