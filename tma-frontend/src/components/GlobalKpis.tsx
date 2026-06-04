import type { GlobalKpis as TGlobalKpis } from "../types";

function KpiPill({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col items-center bg-white rounded-xl px-3 py-2 shadow-sm min-w-[72px]">
      <span className="text-base font-bold text-gray-800">{value}</span>
      <span className="text-[10px] text-gray-400 text-center leading-tight mt-0.5">{label}</span>
    </div>
  );
}

export function GlobalKpis({ kpis }: { kpis: TGlobalKpis }) {
  return (
    <div className="flex gap-2 overflow-x-auto pb-1 px-4">
      <KpiPill
        label="הכנסות החודש"
        value={`₪${kpis.income_this_month.toLocaleString("he-IL")}`}
      />
      <KpiPill
        label="תשלומים ממתינים"
        value={String(kpis.pending_payments_count)}
      />
      <KpiPill
        label="משימות באיחור"
        value={String(kpis.overdue_tasks)}
      />
      <KpiPill
        label="לידים חמים"
        value={String(kpis.hot_leads_count)}
      />
    </div>
  );
}
