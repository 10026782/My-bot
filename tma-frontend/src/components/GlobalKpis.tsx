import type { GlobalKpis as TGlobalKpis } from "../types";
import { Surface } from "./ui/Surface";

function KpiStat({ label, value }: { label: string; value: string }) {
  return (
    <Surface variant="subtle" padding="compact" className="hub-kpi-stat">
      <p className="hub-kpi-stat__value">{value}</p>
      <p className="hub-kpi-stat__label">{label}</p>
    </Surface>
  );
}

export function GlobalKpis({ kpis }: { kpis: TGlobalKpis }) {
  return (
    <div className="hub-kpi-row">
      <KpiStat label="משימות באיחור" value={String(kpis.overdue_tasks)} />
      <KpiStat label="לידים חמים בפרויקטים פעילים" value={String(kpis.hot_leads_count)} />
    </div>
  );
}
