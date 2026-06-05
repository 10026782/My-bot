import { useEffect, useState } from "react";
import { fetchFinancePulse } from "../api";
import type { FinancePulse as TFinancePulse } from "../types";

interface Props {
  onBack: () => void;
}

type State =
  | { status: "loading" }
  | { status: "ok"; data: TFinancePulse }
  | { status: "error"; message: string };

const MONTHS_HE = ["", "ינואר", "פברואר", "מרץ", "אפריל", "מאי", "יוני",
  "יולי", "אוגוסט", "ספטמבר", "אוקטובר", "נובמבר", "דצמבר"];

function formatPeriod(period: string): string {
  const [year, mon] = period.split("-");
  return `${MONTHS_HE[parseInt(mon)] ?? mon} ${year}`;
}

function fmt(amount: number): string {
  if (amount >= 1_000_000) return `₪${(amount / 1_000_000).toFixed(1)}M`;
  if (amount >= 1_000)     return `₪${(amount / 1_000).toFixed(0)}K`;
  return `₪${amount.toLocaleString("he-IL")}`;
}

interface KpiTileProps {
  label: string;
  amount: number;
  count?: number;
  icon: string;
  amountColor?: string;
}

function KpiTile({ label, amount, count, icon, amountColor = "text-gray-900" }: KpiTileProps) {
  return (
    <div className="bg-white rounded-xl shadow-sm p-4 flex flex-col gap-1">
      <div className="flex items-center gap-1.5 text-gray-400 text-xs">
        <span>{icon}</span>
        <span>{label}</span>
      </div>
      <p className={`text-2xl font-black ${amountColor}`}>{fmt(amount)}</p>
      {count !== undefined && (
        <p className="text-[11px] text-gray-400">{count} רשומות</p>
      )}
    </div>
  );
}

export function FinancePulse({ onBack }: Props) {
  const [state, setState] = useState<State>({ status: "loading" });

  useEffect(() => {
    fetchFinancePulse()
      .then((data) => setState({ status: "ok", data }))
      .catch((e: unknown) => setState({ status: "error", message: String(e) }));
  }, []);

  const d = state.status === "ok" ? state.data : null;

  return (
    <div className="min-h-screen bg-gray-100 pb-8">
      {/* Header */}
      <div className="bg-white px-4 pt-5 pb-4 mb-3 shadow-sm flex items-center gap-3">
        <button
          onClick={onBack}
          className="text-blue-500 text-xl font-medium leading-none"
          aria-label="חזרה"
        >
          ←
        </button>
        <div>
          <h1 className="text-lg font-black text-gray-900">פינאנס</h1>
          <p className="text-xs text-gray-400">
            {d ? formatPeriod(d.period) : "Finance Pulse"}
          </p>
        </div>
      </div>

      {state.status === "loading" && (
        <div className="flex justify-center pt-16">
          <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
        </div>
      )}

      {state.status === "error" && (
        <div className="mx-4 mt-4 bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700">
          {state.message}
        </div>
      )}

      {d && (
        <div className="flex flex-col gap-3 px-4">
          {/* KPI 2x2 grid */}
          <div className="grid grid-cols-2 gap-3">
            <KpiTile
              label="הכנסה החודש"
              amount={d.income.amount}
              count={d.income.count}
              icon="💰"
              amountColor="text-green-600"
            />
            <KpiTile
              label="ממתין לתשלום"
              amount={d.pending.amount}
              count={d.pending.count}
              icon="⏳"
              amountColor="text-yellow-600"
            />
            <KpiTile
              label="באיחור"
              amount={d.overdue.amount}
              count={d.overdue.count}
              icon="⚠️"
              amountColor={d.overdue.amount > 0 ? "text-red-600" : "text-gray-400"}
            />
            <KpiTile
              label="הוצאות החודש"
              amount={d.expenses.amount}
              count={d.expenses.count}
              icon="📉"
              amountColor="text-gray-700"
            />
          </div>

          {/* Net */}
          <div className={`rounded-xl p-4 flex items-center justify-between shadow-sm
            ${d.net >= 0 ? "bg-green-50 border border-green-100" : "bg-red-50 border border-red-100"}`}>
            <p className="text-sm font-medium text-gray-600">רווח נטו החודש</p>
            <p className={`text-2xl font-black ${d.net >= 0 ? "text-green-600" : "text-red-600"}`}>
              {d.net >= 0 ? "+" : ""}{fmt(d.net)}
            </p>
          </div>

          {/* Recent payments */}
          {d.recent.length > 0 && (
            <div className="bg-white rounded-xl shadow-sm p-4">
              <p className="text-xs text-gray-400 mb-3">תשלומים אחרונים</p>
              <div className="flex flex-col divide-y divide-gray-50">
                {d.recent.map((p, i) => (
                  <div key={i} className="flex items-center justify-between py-2 first:pt-0 last:pb-0">
                    <div>
                      <p className="text-sm text-gray-800 font-medium">{p.ref || "—"}</p>
                      <p className="text-xs text-gray-400">{p.date}</p>
                    </div>
                    <p className="text-sm font-bold text-green-600">{fmt(p.amount)}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
